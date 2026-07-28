"""Headless programmatic API for scanpath-studio.

The Streamlit app and this module share one pipeline (``data`` → ``measures``
→ ``plots``), so a figure produced here goes through the exact same builders as
the app and is pixel-identical *given the same settings*. The headless defaults
(``CANONICAL_FIGURE_DEFAULTS``) render the full canonical figure; the interactive
app instead opens on a more minimal first view (core scanpath only), so the two
*default* outputs differ in which layers are on — everything else (marker
opacity, index-label size, monitor framing …) is kept in sync with the app.
Typical use::

    import scanpath_studio as sps

    words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
    print(sps.list_trials(words, fixations))
    fig = sps.plot_scanpath(words, fixations, participant="p1", trial="t1")
    sps.save_figure(fig, "scanpath.html")   # or .png/.svg/.pdf (needs Chrome)

Every keyword accepted by :func:`plots.make_scanpath_figure` /
:func:`plots.make_scanpath_animation` can be overridden through
``plot_scanpath`` / ``animate_scanpath`` (e.g. ``show_heatmap=False``);
:func:`figure_options` lists them with their effective defaults. ``docs/agents.md``
is the task-oriented guide to this module for scripted / agent use.
"""

from __future__ import annotations

import difflib
import inspect
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import pandas as pd
import plotly.graph_objects as go

# Outside a Streamlit runtime the @st.cache_data decorators in `data` fall
# back to bare-mode caching and log a "No runtime found" warning per cached
# function — harmless but noisy for library/CLI users, so quiet those loggers.
# Order matters twice over: streamlit must be imported first (its get_logger()
# sets each module logger's level at import, clobbering anything set earlier),
# and `.data` must be imported after (its decorators fire the warnings at
# import time). Inside the app a runtime exists and these warnings never fire.
import streamlit as _st  # noqa: F401  (imported for its logging side effect)

for _name in (
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.scriptrunner_utils.script_run_context",
):
    logging.getLogger(_name).setLevel(logging.ERROR)

from . import data as _data  # noqa: E402
from .constants import (  # noqa: E402
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_ORDER_FONT_COLOR,
    DEFAULT_SACCADE_WIDTH,
    FONT_FAMILY,
    PALETTES,
    SACCADE_COLOR,
    UNIFORM_COLOR_FIELD,
    palette_settings,
)
from .plots import (  # noqa: E402
    animation_autoplay_frame_duration,
    animation_autoplay_post_script,
    make_scanpath_animation,
    make_scanpath_figure,
    split_scanpath_layers,
)

TableLike = Union[pd.DataFrame, str, Path]
TablesLike = Union[TableLike, "list[TableLike]"]

# The headless "canonical" rendering — every core layer on. (The interactive app
# instead starts minimal: word boxes / heatmap / fixation-index off by default —
# see controls._VIZ_WIDGET_DEFAULTS — so the app's *default* first view differs;
# override any layer via plot_scanpath kwargs.) `heatmap_metric="counts"` is
# translated to the figure-level `None` in _figure_kwargs, like
# tabs._build_figure_settings.
#
# Everything that is NOT a layer toggle tracks the app's own default
# (controls._VIZ_WIDGET_DEFAULTS → controls._collect_viz_settings →
# tabs._build_figure_settings), so the same call renders the same picture
# headless as on screen. `figure_options()` prints the merged result.
CANONICAL_FIGURE_DEFAULTS: dict = dict(
    show_words=True,
    show_word_labels=True,
    show_fixations=True,
    show_order=True,
    show_saccades=True,
    show_saccade_arrows=False,
    show_heatmap=True,
    heatmap_style="Word boxes",
    heatmap_norm="Linear",
    # Spatial fields: which fixation columns drive the axes. Defaults to the gaze
    # coordinates; `x_field="order_in_trial"` gives the time-ordered variant.
    x_field="x",
    y_field="y",
    # VIZ-17: no variable mapped to fixation hue by default. Marker *size* already
    # encodes duration, so the old `color_by="duration_ms"` spent the colour
    # channel restating it. Pass an explicit `color_by=` for a second variable.
    color_by=UNIFORM_COLOR_FIELD,
    heatmap_metric="duration_ms",
    marker_size_range=DEFAULT_MARKER_SIZE_RANGE,
    # Fixation-index labels: 10 px, matching the app's `global_order_font_size`
    # (and the animation builder's own default) — 16 px overflowed the markers.
    order_font_size=10,
    order_font_color=DEFAULT_ORDER_FONT_COLOR,
    show_colorbars=False,
    fixation_color_range=None,
    heatmap_range=None,
    fixation_colorscale=DEFAULT_FIXATION_COLORSCALE,
    heatmap_colorscale=DEFAULT_HEATMAP_COLORSCALE,
    critical_span_style="Mark text",
    highlight_column="is_in_aspan",
    saccade_color=SACCADE_COLOR,
    saccade_style="solid",
    saccade_width=DEFAULT_SACCADE_WIDTH,
    saccade_color_mode="Uniform",
    saccade_class_colors=None,
    saccade_type_legend=True,
    saccade_render_mode="Straight",
    fixation_snap_to_word=False,
    # VIZ-17 uniform fixation colour · VIZ-15 marker shape — the flat colour and
    # symbol every marker wears while `color_by` is the uniform sentinel.
    fixation_color=DEFAULT_FIXATION_COLOR,
    fixation_symbol=DEFAULT_FIXATION_SYMBOL,
    # VIZ-6: translucent markers so overlapping fixations show through, matching
    # the app's `global_fixation_opacity`. 1.0 = fully opaque.
    fixation_opacity=0.7,
    background_color=DEFAULT_BACKGROUND_COLOR,
    color_by_line=False,
    # Frame the whole presentation monitor (`canvas_size`) instead of cropping to
    # the data extent, so the scanpath sits at its true on-screen position — the
    # app's default. `fit_to_monitor=False` crops to the fixations + word boxes.
    fit_to_monitor=True,
    line_spacing=DEFAULT_LINE_SPACING,
    scale_text_to_boxes=True,
    background_image=None,
    background_image_size=None,
    background_image_origin=None,
    background_image_opacity=1.0,
)


def _as_dataframe(table: TablesLike, label: str) -> pd.DataFrame:
    if isinstance(table, pd.DataFrame):
        return table
    items = _data.expand_table_inputs(table)
    for item in items:
        if not isinstance(item, pd.DataFrame) and not Path(item).is_file():
            raise FileNotFoundError(f"{label} table not found: {item}")
    return _data.read_tables(items)


# ---------------------------------------------------------------------------
# Schema diagnostics
#
# `data.validate_*_schema` says *what* is missing ("missing Trial ID"). A caller
# scripting against an unfamiliar table also needs *why*: which column names
# auto-detection looked for, which columns the table actually has, and the exact
# override to pass. These tables mirror `data.propose_*_schema` field for field —
# add a field there, add it here.
# ---------------------------------------------------------------------------

_SCHEMA_SPECS: dict = {
    "words": {
        "title": "Words/IA",
        "noun": "words/IA",
        "param": "word_schema",
        # (schema key, human label, candidate column names) — the fields whose
        # absence makes `validate_word_schema` fail.
        "required": (
            ("trial", "Trial ID", _data.TRIAL_CANDIDATES),
            ("word_id", "Word/IA ID", _data.WORD_ID_CANDIDATES),
        ),
        # …plus one "either group A or group B" requirement.
        "group_label": "Word box",
        "groups": (("x", "y", "width", "height"), ("left", "right", "top", "bottom")),
        "group_candidates": {
            "x": _data.WORD_X_CANDIDATES,
            "y": _data.WORD_Y_CANDIDATES,
            "width": _data.WORD_WIDTH_CANDIDATES,
            "height": _data.WORD_HEIGHT_CANDIDATES,
            "left": _data.WORD_LEFT_CANDIDATES,
            "right": _data.WORD_RIGHT_CANDIDATES,
            "top": _data.WORD_TOP_CANDIDATES,
            "bottom": _data.WORD_BOTTOM_CANDIDATES,
        },
        "propose": _data.propose_word_schema,
    },
    "fixations": {
        "title": "Fixations",
        "noun": "fixations",
        "param": "fix_schema",
        "required": (
            ("trial", "Trial ID", _data.TRIAL_CANDIDATES),
            ("duration", "Duration", _data.FIX_DURATION_CANDIDATES),
        ),
        "group_label": "Fixation location",
        "groups": (("x", "y"), ("word_id",)),
        "group_candidates": {
            "x": _data.FIX_X_CANDIDATES,
            "y": _data.FIX_Y_CANDIDATES,
            "word_id": _data.FIX_WORD_ID_CANDIDATES,
        },
        "propose": _data.propose_fix_schema,
    },
    "raw_gaze": {
        "title": "Raw gaze",
        "noun": "raw gaze",
        "param": "raw_gaze_schema",
        "required": (
            ("trial", "Trial ID", _data.TRIAL_CANDIDATES),
            ("x", "X", _data.RAW_GAZE_X_CANDIDATES),
            ("y", "Y", _data.RAW_GAZE_Y_CANDIDATES),
        ),
        "group_label": None,
        "groups": (),
        "group_candidates": {},
        "propose": _data.propose_raw_gaze_schema,
    },
}


def _column_preview(frame: pd.DataFrame, limit: int = 40) -> str:
    """Comma-separated column names, truncated so a 100-column IA report stays
    readable in a traceback."""
    cols = [str(c) for c in frame.columns]
    shown = ", ".join(cols[:limit])
    if len(cols) > limit:
        shown += f", … (+{len(cols) - limit} more)"
    return shown


def _schema_skeleton(kind: str, schema: dict) -> str:
    """A copy-pasteable mapping literal: what was detected, ``'<column>'`` for
    the rest. An explicit schema replaces auto-detection wholesale, so every
    required key has to be in it — not just the ones that failed."""
    spec = _SCHEMA_SPECS[kind]
    keys = [key for key, _, _ in spec["required"]]
    if spec["groups"]:
        # Suggest whichever coordinate convention is closest to complete.
        best = min(
            spec["groups"],
            key=lambda group: sum(1 for key in group if not schema.get(key)),
        )
        keys += [key for key in best if key not in keys]
    items = ", ".join(
        f"{key!r}: {schema[key]!r}" if schema.get(key) else f"{key!r}: '<column>'"
        for key in keys
    )
    return "{" + items + "}"


def _schema_columns(schema: dict) -> "list[tuple[str, str]]":
    """``(schema key, column name)`` for every column a mapping names.

    Multi-column (composite) mappings — the trial / participant / text id may be
    a list, see :func:`data.trial_id_series` — expand to one pair per column."""
    pairs: list = []
    for key, value in schema.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            pairs.extend((key, str(col)) for col in value)
        else:
            pairs.append((key, str(value)))
    return pairs


def _check_mapped_columns(kind: str, frame: pd.DataFrame, schema: dict) -> None:
    """Reject a schema that maps a column the table doesn't have.

    Only reachable with a caller-supplied schema — auto-detection only ever
    picks columns that exist. Without this check a mistyped mapping either
    raises a bare ``KeyError: '<column>'`` from inside ``normalize_*``, or is
    **silently ignored**: ``normalize_words`` prefers a literal
    ``unique_trial_id`` column over the mapped one, so a typo'd ``'trial'``
    would come back keyed on a column the caller never asked for."""
    spec = _SCHEMA_SPECS[kind]
    present = {str(c) for c in frame.columns}
    missing = [(key, col) for key, col in _schema_columns(schema) if col not in present]
    if not missing:
        return
    plural = "" if len(missing) == 1 else "s"
    lines = [
        f"{spec['title']} schema maps {len(missing)} column name{plural} the "
        f"{spec['noun']} table doesn't have:"
    ]
    for key, column in missing:
        close = difflib.get_close_matches(column, sorted(present), n=3, cutoff=0.6)
        hint = f" (closest: {', '.join(repr(c) for c in close)})" if close else ""
        lines.append(f"  - {spec['param']}[{key!r}] = {column!r}: no such column{hint}")
    lines.append(
        f"Columns present in the {spec['noun']} table ({len(frame.columns)}): "
        f"{_column_preview(frame)}"
    )
    lines.append(
        f"api.propose_schema(table, {kind!r}) returns the auto-detected mapping to "
        "start from."
    )
    raise ValueError("\n".join(lines))


def _schema_error(
    kind: str, frame: pd.DataFrame, schema: dict, problems: list, explicit: bool = False
) -> ValueError:
    """Build the ``ValueError`` for a table whose canonical fields don't resolve.

    Names every canonical field that could not be resolved, the candidate column
    names auto-detection tried for it, the columns the table actually has, and
    the explicit mapping to pass instead. ``explicit`` marks a schema the caller
    supplied — nothing was auto-detected, so the message points at the keys
    missing from *their* mapping rather than at failed detection."""
    spec = _SCHEMA_SPECS[kind]
    param = spec["param"]
    lines = [f"{spec['title']} schema problems: {'; '.join(problems)}"]

    if explicit:
        bullets = [
            f"  - {label} ({param} key {key!r}): not set in the {param} you passed. "
            f"Auto-detection (used when {param} is omitted) looks for: "
            f"{', '.join(candidates)}"
            for key, label, candidates in spec["required"]
            if not schema.get(key)
        ]
    else:
        bullets = [
            f"  - {label} ({param} key {key!r}): no column matched. "
            f"Looked for: {', '.join(candidates)}"
            for key, label, candidates in spec["required"]
            if not schema.get(key)
        ]
    groups_missing = [
        (group, [key for key in group if not schema.get(key)])
        for group in spec["groups"]
    ]
    # A group requirement only fails when *every* alternative is incomplete.
    if groups_missing and all(missing for _, missing in groups_missing):
        alternatives = " or ".join(
            f"({', '.join(group)})" for group, _ in groups_missing
        )
        detail = "; ".join(
            f"({', '.join(group)}) is missing {', '.join(missing)}"
            for group, missing in groups_missing
        )
        unresolved = dict.fromkeys(
            key for _, missing in groups_missing for key in missing
        )
        looked = " | ".join(
            f"{key}: {', '.join(spec['group_candidates'][key])}" for key in unresolved
        )
        looked_label = "Auto-detection looks for" if explicit else "Looked for"
        bullets.append(
            f"  - {spec['group_label']} ({param} keys): need either {alternatives} "
            f"— {detail}.\n      {looked_label} → {looked}"
        )
    if bullets:
        lines.append(
            f"Missing from the {param} you passed:"
            if explicit
            else f"Could not infer these canonical fields from the {spec['noun']} table:"
        )
        lines.extend(bullets)
    resolved = ", ".join(
        f"{key}={value!r}" for key, value in schema.items() if value is not None
    )
    lines.append(
        f"Fields the {param} does set: {resolved or '(none)'}"
        if explicit
        else f"Fields that did resolve: {resolved or '(none)'}"
    )
    lines.append(
        f"Columns present in the {spec['noun']} table ({len(frame.columns)}): "
        f"{_column_preview(frame)}"
    )
    if not explicit:
        lines.append(
            "Matching ignores case and separators (IA_LEFT == ia_left == 'Ia Left') "
            "and takes the first candidate that matches."
        )
    lines.append(
        f"An explicit {param} replaces auto-detection wholesale, so it needs every "
        f"required key, e.g. {param}={_schema_skeleton(kind, schema)} — "
        f"api.propose_schema(df, {kind!r}) returns the auto-detected mapping."
        if explicit
        else f"To override auto-detection pass the full mapping, e.g. "
        f"{param}={_schema_skeleton(kind, schema)} — "
        f"api.propose_schema(df, {kind!r}) returns what was detected."
    )
    return ValueError("\n".join(lines))


def propose_schema(table: TablesLike, kind: str = "words") -> dict:
    """Auto-detected column mapping for a **raw** (un-normalized) table.

    ``kind`` is ``"words"``, ``"fixations"`` or ``"raw_gaze"``. Returns
    ``{canonical field: source column or None}`` — the same mapping
    :func:`load_scanpath_data` infers internally, so it's the place to start when
    detection got a field wrong or couldn't find one: edit the dict and pass it
    back as ``word_schema=`` / ``fix_schema=``::

        schema = sps.api.propose_schema("ia.csv", "words")
        schema["trial"] = "TRIAL_LABEL"
        words, fixations = sps.load_scanpath_data("ia.csv", "fix.csv",
                                                  word_schema=schema)

    ``table`` is a DataFrame, path, glob or list of paths, like the loader's.
    """
    if kind not in _SCHEMA_SPECS:
        raise ValueError(
            f"Unknown kind {kind!r}; choose one of {', '.join(_SCHEMA_SPECS)}."
        )
    frame = _as_dataframe(table, _SCHEMA_SPECS[kind]["noun"])
    return _SCHEMA_SPECS[kind]["propose"](frame)


_NORMALIZED_ID_COLUMNS = ("participant_id", "trial_id")


def _require_normalized(frame, label: str) -> pd.DataFrame:
    """Guard the plotting entry points against raw / wrongly-typed input.

    The builders consume the *normalized* frames :func:`load_scanpath_data`
    returns; handing them a path or a raw table otherwise fails deep inside with
    a ``KeyError: 'participant_id'``."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(
            f"{label} must be the normalized pandas DataFrame returned by "
            f"load_scanpath_data(), got {type(frame).__name__}. "
            "Call words, fixations = load_scanpath_data(words=…, fixations=…) "
            "first — it reads paths/globs and normalizes column names."
        )
    missing = [col for col in _NORMALIZED_ID_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(
            f"{label} frame is not normalized: missing the canonical column(s) "
            f"{', '.join(missing)}. Its columns are: {_column_preview(frame)}. "
            "Pass the frames returned by load_scanpath_data(...) (raw tables have "
            "to go through it first)."
        )
    return frame


def load_scanpath_data(
    words: Optional[TablesLike] = None,
    fixations: Optional[TablesLike] = None,
    *,
    word_schema: Optional[dict] = None,
    fix_schema: Optional[dict] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load and normalize a words/IA table and/or a fixations table.

    ``words`` / ``fixations`` may be DataFrames, paths to ``.csv`` / ``.tsv``
    / ``.parquet`` / ``.feather`` files, glob patterns, or lists of paths —
    multi-file datasets (one file per participant and/or text) are
    concatenated, with each file's stem kept in a ``source_file`` column.
    Column schemas are auto-detected (EyeLink, Gazepoint, and snake_case
    names); pass ``word_schema`` / ``fix_schema`` mappings (field → column
    name, see ``controls.WORD_FIELD_SPECS``) to override detection. For
    per-word reading measures, pass the result to :func:`compute_word_metrics`.

    Either table may be omitted for datasets that ship only one report: the
    missing side comes back as an empty canonical frame and the plots simply
    skip that layer. Words without a participant column (stimulus-level AoIs)
    are broadcast across the participants found in the fixations, and
    fixations without x/y but with a word/AoI ID are placed at word-box
    centers.

    Returns the normalized ``(words, fixations)`` frames the plotting
    functions expect. Raises ``ValueError`` if a required field can't be found —
    the message names the canonical field, the column names auto-detection
    looked for, and the columns the table actually has.
    """
    if words is None and fixations is None:
        raise ValueError("Provide at least one of words= or fixations=.")

    if words is not None:
        words_df = _as_dataframe(words, "words/IA")
        explicit = word_schema is not None
        word_schema = word_schema or _data.propose_word_schema(words_df)
        _check_mapped_columns("words", words_df, word_schema)
        problems = _data.validate_word_schema(word_schema)
        if problems:
            raise _schema_error("words", words_df, word_schema, problems, explicit)
        words_norm = _data.normalize_words(words_df, word_schema)
    else:
        words_norm = _data.empty_words_frame()

    if fixations is not None:
        fixations_df = _as_dataframe(fixations, "fixations")
        explicit = fix_schema is not None
        fix_schema = fix_schema or _data.propose_fix_schema(fixations_df)
        _check_mapped_columns("fixations", fixations_df, fix_schema)
        problems = _data.validate_fix_schema(fix_schema)
        if problems:
            raise _schema_error(
                "fixations", fixations_df, fix_schema, problems, explicit
            )
        fixations_norm = _data.normalize_fixations(fixations_df, fix_schema)
    else:
        fixations_norm = _data.empty_fixations_frame()

    return _data.harmonize_frames(words_norm, fixations_norm)


def load_sample_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return the bundled OneStop demo, normalized and ready to plot.

    Three readers' word boxes ship with the package but only two of them have
    fixations, so :func:`list_trials` reports the two plottable readers."""
    return load_scanpath_data(*_data.load_sample_data())


def compute_word_metrics(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Per-word reading measures (FFD/FPRT/RPD/TFD, skips, regressions, …).

    Pre-aggregated columns in ``words`` (EyeLink IA exports) are preserved;
    anything missing is computed from fixations + word bounding boxes. Takes
    the normalized frames from :func:`load_scanpath_data`."""
    _require_normalized(words, "words")
    _require_normalized(fixations, "fixations")
    return _data.compute_word_metrics(words, fixations)


def list_trials(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Plottable ``(participant_id, trial_id)`` combos.

    Combos present in both frames when both are loaded; for single-report
    datasets (words-only or fixations-only), combos from whichever frame has
    data."""
    _require_normalized(words, "words")
    _require_normalized(fixations, "fixations")
    cols = ["participant_id", "trial_id"]
    if words.empty or fixations.empty:
        present = fixations if words.empty else words
        combos = present[cols].drop_duplicates()
    else:
        combos = words[cols].drop_duplicates().merge(fixations[cols].drop_duplicates())
    return combos.sort_values(cols).reset_index(drop=True)


def _resolve_trial(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: Optional[str],
    trial: Optional[str],
    *,
    default_first: bool = False,
) -> Tuple[str, str]:
    """Resolve to one (participant_id, trial_id), validating what was given.

    A nonexistent participant/trial always raises — naming which of the two ids
    is unknown, a few valid values and the closest spellings. An underspecified
    selection matching several trials raises too, unless ``default_first`` picks
    the first match (the CLI's behavior, mirroring the app's default selection).
    """
    combos = list_trials(words, fixations)
    if combos.empty:
        raise ValueError("No (participant, trial) combo exists in the data.")
    scoped = combos
    if participant is not None:
        scoped = scoped[scoped["participant_id"] == str(participant)]
        if scoped.empty:
            raise ValueError(
                f"No trial matches participant={participant!r}: that participant "
                f"id is not in the data. {_value_hint(combos, 'participant_id', participant)}"
            )
    if trial is not None:
        narrowed = scoped[scoped["trial_id"] == str(trial)]
        if narrowed.empty:
            if participant is None:
                raise ValueError(
                    f"No trial matches trial={trial!r}: that trial id is not in "
                    f"the data. {_value_hint(combos, 'trial_id', trial)}"
                )
            raise ValueError(
                f"No trial matches participant={participant!r}, trial={trial!r}: "
                f"participant {str(participant)!r} has {len(scoped)} trial(s), none "
                f"of them {str(trial)!r}. {_value_hint(scoped, 'trial_id', trial)}"
            )
        scoped = narrowed
    if len(scoped) > 1 and not default_first:
        preview = ", ".join(
            f"({pid!r}, {tid!r})"
            for pid, tid in scoped.head(5).itertuples(index=False, name=None)
        )
        if participant is None and trial is None:
            fix = "Pass participant= and trial=."
        elif participant is None:
            fix = (
                f"Trial {str(trial)!r} was read by {scoped['participant_id'].nunique()} "
                "participants — pass participant= too."
            )
        else:
            fix = (
                f"Participant {str(participant)!r} has {len(scoped)} trials — pass "
                "trial= too."
            )
        raise ValueError(
            f"Ambiguous selection: {len(scoped)} trials match "
            f"participant={participant!r}, trial={trial!r} (first few: {preview}). "
            f"{fix} list_trials(words, fixations) lists all {len(combos)} combos."
        )
    row = scoped.iloc[0]
    return str(row["participant_id"]), str(row["trial_id"])


def _value_hint(combos: pd.DataFrame, column: str, wanted, limit: int = 5) -> str:
    """ "Closest / available ids" tail for a failed trial lookup."""
    values = [str(v) for v in combos[column].drop_duplicates()]
    close = difflib.get_close_matches(str(wanted), values, n=3, cutoff=0.6)
    shown = ", ".join(repr(v) for v in values[:limit])
    more = f", … (+{len(values) - limit} more)" if len(values) > limit else ""
    hint = f"Available: {shown}{more}."
    if close:
        hint += f" Closest: {', '.join(repr(v) for v in close)}."
    return hint


def _select_trial(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: Optional[str],
    trial: Optional[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, str, str]:
    pid, tid = _resolve_trial(words, fixations, participant, trial)
    trial_words, trial_fixations = _data.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    if not trial_fixations.empty and trial_fixations["x"].isna().all():
        # AOI-sequence fixations whose coordinates couldn't be reconstructed:
        # either no words table was given, or the word/AoI ids matched no box.
        raise ValueError(
            f"Fixations for participant={pid!r}, trial={tid!r} have no usable "
            "coordinates. AOI-sequence datasets (no x/y) need a words table "
            "whose word/AoI ids match the fixations' so fixations can be "
            "placed at word-box centers."
        )
    return trial_words, trial_fixations, pid, tid


def _apply_fix_index_range(
    trial_fixations: pd.DataFrame, fix_index_range, pid: str, tid: str
) -> pd.DataFrame:
    """Window the trial to fixations ``start..end`` of ``order_in_trial`` (VIZ-7).

    The headless form of the app's fixation-index slider: both bounds inclusive,
    1-based, and applied only to the frame that feeds the figure. Raises rather
    than silently drawing an empty scanpath when the window misses the trial."""
    if fix_index_range is None:
        return trial_fixations
    if not isinstance(fix_index_range, (tuple, list)) or len(fix_index_range) != 2:
        raise ValueError(
            f"fix_index_range must be a (start, end) pair of 1-based fixation "
            f"indices, got {fix_index_range!r}."
        )
    try:
        lo, hi = int(fix_index_range[0]), int(fix_index_range[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"fix_index_range bounds must be integers, got {fix_index_range!r}."
        ) from exc
    if lo > hi:
        raise ValueError(
            f"fix_index_range={fix_index_range!r} is empty: start {lo} is after end {hi}."
        )
    if trial_fixations.empty:
        return trial_fixations
    if "order_in_trial" not in trial_fixations.columns:
        raise ValueError(
            "fix_index_range needs the 'order_in_trial' column, which "
            "load_scanpath_data() adds during normalization — pass the frames it "
            "returns."
        )
    order = trial_fixations["order_in_trial"]
    windowed = trial_fixations[(order >= lo) & (order <= hi)]
    if windowed.empty:
        raise ValueError(
            f"fix_index_range=({lo}, {hi}) selects no fixations: participant={pid!r}, "
            f"trial={tid!r} has {len(trial_fixations)} fixations "
            f"(order_in_trial {int(order.min())}–{int(order.max())})."
        )
    return windowed


def _figure_kwargs(overrides: dict) -> dict:
    settings = {**CANONICAL_FIGURE_DEFAULTS, **_expand_palette(overrides)}
    if settings.get("heatmap_metric") == "counts":
        settings["heatmap_metric"] = None
    return settings


def _expand_palette(overrides: dict) -> dict:
    """Expand a ``palette=`` override into the colour kwargs it stands for (VIZ-18).

    ``palette`` names a set of colour defaults tuned for a medium — screen,
    colourblind viewers, a black & white print, a projector. It's a *preset*, so
    any colour the caller also passes explicitly wins over it::

        sps.plot_scanpath(w, f, palette="Print / greyscale")
        sps.plot_scanpath(w, f, palette="Colourblind-safe", saccade_color="#000")

    The palette itself isn't a figure kwarg, so it's consumed here rather than
    forwarded. Raises on an unknown name — a silent fallback to the default
    palette would quietly produce the wrong figure for a print run.
    """
    name = overrides.get("palette")
    if name is None:
        return overrides
    if name not in PALETTES:
        raise ValueError(
            f"Unknown palette {name!r}; choose one of {', '.join(PALETTES)}."
        )
    expanded = dict(overrides)
    expanded.pop("palette")
    # `word_label_color` is `text_color` on the figure builders.
    settings = palette_settings(name)
    settings["text_color"] = settings.pop("word_label_color")
    for key, value in settings.items():
        expanded.setdefault(key, value)
    return expanded


# Figure keywords each builder accepts, minus the ones the wrappers own (frames,
# canvas, fonts, playback). Derived from the signatures so they can't drift.
_BUILDER_OWNED = frozenset(
    {"words", "fixations", "canvas_width", "canvas_height", "base_font_size"}
)
_STATIC_FIGURE_PARAMS = (
    frozenset(inspect.signature(make_scanpath_figure).parameters)
    - _BUILDER_OWNED
    - {"font_family", "raw_gaze"}
)
_ANIMATION_FIGURE_PARAMS = (
    frozenset(inspect.signature(make_scanpath_animation).parameters)
    - _BUILDER_OWNED
    - {"font_family", "playback_speed", "autoplay"}
)


def _reject_unknown_options(overrides: dict, valid, func_name: str) -> None:
    """Fail on a misspelled/unsupported keyword, naming the closest valid ones.

    Forwarding blindly would surface as ``make_scanpath_figure() got an
    unexpected keyword argument`` — an internal name the caller never typed."""
    unknown = sorted(set(overrides) - set(valid))
    if not unknown:
        return
    parts = []
    for key in unknown:
        close = difflib.get_close_matches(key, sorted(valid), n=3, cutoff=0.6)
        suffix = (
            f" (did you mean {', '.join(repr(c) for c in close)}?)" if close else ""
        )
        parts.append(f"{key!r}{suffix}")
    raise TypeError(
        f"{func_name}() got an unexpected keyword argument: {', '.join(parts)}. "
        f"Valid figure options: {', '.join(sorted(valid))}. "
        f"api.figure_options() lists them with their defaults."
    )


def figure_options(kind: str = "static") -> dict:
    """Every figure keyword a builder accepts → the default it renders with.

    ``kind="static"`` covers :func:`plot_scanpath`, ``kind="animation"``
    :func:`animate_scanpath` (whose builder supports a subset). The values are
    the *effective* defaults — :data:`CANONICAL_FIGURE_DEFAULTS` where it sets
    one, the builder's own signature default otherwise — so a scripted caller
    can diff its intended settings against what it would get::

        {k: v for k, v in sps.api.figure_options().items() if k.startswith("show_")}
    """
    if kind == "static":
        params = _STATIC_FIGURE_PARAMS
        signature = inspect.signature(make_scanpath_figure)
        defaults = CANONICAL_FIGURE_DEFAULTS
    elif kind == "animation":
        params = _ANIMATION_FIGURE_PARAMS
        signature = inspect.signature(make_scanpath_animation)
        defaults = _animation_defaults()
    else:
        raise ValueError(f"Unknown kind {kind!r}; use 'static' or 'animation'.")
    options = {}
    for name in sorted(params):
        if name in defaults:
            options[name] = defaults[name]
        else:
            fallback = signature.parameters[name].default
            options[name] = None if fallback is inspect.Parameter.empty else fallback
    return options


def _animation_defaults() -> dict:
    """The canonical defaults the animation builder can actually take."""
    return {
        key: value
        for key, value in CANONICAL_FIGURE_DEFAULTS.items()
        if key in _ANIMATION_FIGURE_PARAMS
    }


def _apply_drift_correction(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    settings: dict,
    method: Optional[str],
    connectors: bool,
    explicit: dict,
) -> pd.DataFrame:
    """Snap fixations to their assigned text line (PRE-3), in place of the raw y.

    Mirrors what the app does on the static plot (``tabs.render_single_trial_tab``):
    run ``alignment.correct``, colour the corrected fixations by line, and
    optionally draw original→corrected connectors. Returns the fixations to plot.
    """
    if method is None or str(method).lower() == "off":
        return trial_fixations
    from . import alignment as _alignment  # local: pulls in scipy

    name = str(method).lower()
    if name not in _alignment.ALGORITHMS:
        raise ValueError(
            f"Unknown drift_correction {method!r}; choose one of "
            f"{', '.join(_alignment.ALGORITHMS)} (or None to leave the fixations "
            "uncorrected)."
        )
    if trial_fixations.empty or trial_words.empty:
        return trial_fixations
    original_y = tuple(pd.to_numeric(trial_fixations["y"], errors="coerce"))
    corrected, _ = _alignment.correct(trial_fixations, trial_words, method=name)
    # Colouring by line is what makes the correction legible; an explicit
    # `color_by_line=` still wins.
    if "color_by_line" not in explicit:
        settings["color_by_line"] = True
    if connectors:
        settings["show_connectors"] = True
        settings["connector_y"] = original_y
    return corrected


def plot_scanpath(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: Optional[str] = None,
    trial: Optional[str] = None,
    *,
    canvas_size: Optional[Tuple[int, int]] = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    raw_gaze: Optional[pd.DataFrame] = None,
    drift_correction: Optional[str] = None,
    drift_connectors: bool = False,
    fix_index_range: Optional[Tuple[int, int]] = None,
    **figure_overrides,
) -> go.Figure:
    """Build the canonical scanpath figure for one trial.

    ``words`` / ``fixations`` are normalized frames from
    :func:`load_scanpath_data`. ``participant`` / ``trial`` may be omitted when
    the frames contain exactly one combo. ``canvas_size`` is the monitor size
    in px; by default it is estimated from the data extents — pass the real
    monitor resolution (e.g. ``(2560, 1440)`` for OneStop) to keep coordinates
    true to scale. ``raw_gaze`` is a normalized frame (see
    :func:`data.normalize_raw_gaze`) and is filtered to the selected trial.

    ``drift_correction`` (PRE-3) names one of the ten Carr et al. (2021)
    line-assignment algorithms (``alignment.ALGORITHMS``: ``"attach"``,
    ``"chain"``, ``"cluster"``, ``"compare"``, ``"merge"``, ``"regress"``,
    ``"segment"``, ``"split"``, ``"stretch"``, ``"warp"``); each fixation is
    snapped to its assigned text line and coloured by line, exactly as the app's
    *Drift correction* control does. ``drift_connectors=True`` also draws a faint
    line from each fixation's original y to its corrected one.

    ``fix_index_range=(start, end)`` (VIZ-7) draws only fixations ``start``
    through ``end`` (1-based, both inclusive) of the trial — the headless form of
    the app's fixation-index window. It is applied before the drift correction,
    like the app.

    Remaining keywords override the app's defaults and are forwarded to
    :func:`plots.make_scanpath_figure` (e.g. ``show_heatmap=False``,
    ``color_by="pass_index"``, ``x_field="order_in_trial"``); an unknown keyword
    raises a ``TypeError`` naming the closest valid options, and
    :func:`figure_options` lists them all with their defaults.
    """
    _reject_unknown_options(
        figure_overrides, _STATIC_FIGURE_PARAMS | {"palette"}, "plot_scanpath"
    )
    trial_words, trial_fixations, pid, tid = _select_trial(
        words, fixations, participant, trial
    )
    if canvas_size is None:
        canvas_size = _data.compute_canvas_size(trial_words, trial_fixations)
    # Window first, correct second — the app's order (tabs._slice_fix_range runs
    # before alignment.correct), so a windowed correction sees only the kept
    # fixations.
    trial_fixations = _apply_fix_index_range(trial_fixations, fix_index_range, pid, tid)
    settings = _figure_kwargs(figure_overrides)
    # Spatial fields are explicit kwargs of make_scanpath_figure, so they can't
    # ride along in **settings without a "multiple values" TypeError.
    x_field = settings.pop("x_field", "x")
    y_field = settings.pop("y_field", "y")
    trial_fixations = _apply_drift_correction(
        trial_words,
        trial_fixations,
        settings,
        drift_correction,
        drift_connectors,
        figure_overrides,
    )
    if raw_gaze is not None:
        _require_normalized(raw_gaze, "raw_gaze")
        raw_gaze = _data.filter_raw_gaze(raw_gaze, [pid], [tid])
        settings.setdefault("show_raw_gaze", True)
    return make_scanpath_figure(
        trial_words,
        trial_fixations,
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        base_font_size=int(base_font_size),
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
        raw_gaze=raw_gaze,
        **settings,
    )


def animate_scanpath(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: Optional[str] = None,
    trial: Optional[str] = None,
    *,
    canvas_size: Optional[Tuple[int, int]] = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    playback_speed: float = 1.0,
    autoplay: bool = True,
    fix_index_range: Optional[Tuple[int, int]] = None,
    **animation_overrides,
) -> go.Figure:
    """Build the animated scanpath replay for one trial.

    Same trial selection and canvas semantics as :func:`plot_scanpath`. The
    returned Plotly figure plays in real reading time scaled by
    ``playback_speed``; save it as interactive HTML with :func:`save_figure`,
    or rasterize to GIF/MP4 with :func:`animation_export.export_animation`.
    ``fix_index_range=(start, end)`` replays only that window of the trial's
    fixations (1-based, inclusive), like :func:`plot_scanpath`.

    With ``autoplay`` (default ``True``, VIZ-10) the saved interactive HTML
    auto-starts the replay on load *at ``playback_speed``* — :func:`save_figure`
    honors the marker the builder stamps on the figure. Pass ``autoplay=False``
    to save a figure that opens paused (press ▶ Play to run it). Autoplay only
    affects the interactive HTML; GIF/MP4 rasterization renders every frame
    regardless.

    The animation builder accepts a subset of the static figure's options
    (``show_words``, ``show_word_labels``, ``show_saccades``, ``show_order``,
    styling, and second-scanpath overlays) — see ``figure_options("animation")``;
    an unsupported key raises a ``ValueError`` naming the valid ones rather than
    an opaque ``TypeError``. The shared options default to the same values as
    :func:`plot_scanpath` (:data:`CANONICAL_FIGURE_DEFAULTS`), so the replay
    matches the static figure. ``palette=`` (VIZ-18) works here too; the colours
    it implies that the animation doesn't support are dropped rather than
    raising, since the caller named a look, not those individual keys.
    """
    valid = set(_ANIMATION_FIGURE_PARAMS)
    explicit = set(animation_overrides) - {"palette"}
    animation_overrides = _expand_palette(animation_overrides)
    # Only the keys the caller named are held to the "is this supported?" rule;
    # a palette's extras (heatmap colorscale, highlight text colour, …) that the
    # animation has no parameter for are simply dropped.
    animation_overrides = {
        k: v for k, v in animation_overrides.items() if k in valid or k in explicit
    }
    unknown = explicit - valid
    if unknown:
        raise ValueError(
            f"Options not supported by the animation: {sorted(unknown)}. "
            f"Valid overrides: {sorted(valid)}."
        )
    # Same defaults as the static figure for every option both builders share, so
    # `plot_scanpath` and `animate_scanpath` don't render the same trial
    # differently (the app feeds both from one settings dict).
    animation_overrides = {**_animation_defaults(), **animation_overrides}
    trial_words, trial_fixations, pid, tid = _select_trial(
        words, fixations, participant, trial
    )
    trial_fixations = _apply_fix_index_range(trial_fixations, fix_index_range, pid, tid)
    if canvas_size is None:
        canvas_size = _data.compute_canvas_size(trial_words, trial_fixations)
    return make_scanpath_animation(
        trial_words,
        trial_fixations,
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        base_font_size=int(base_font_size),
        font_family=font_family,
        playback_speed=playback_speed,
        autoplay=autoplay,
        **animation_overrides,
    )


def save_figure(
    fig: go.Figure,
    path: Union[str, Path],
    *,
    scale: int = 2,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Path:
    """Save a figure by extension: ``.html`` (interactive, browser-free) or
    ``.png``/``.svg``/``.pdf`` (static via Kaleido — needs a Chrome/Chromium;
    run ``plotly_get_chrome -y`` once if missing). ``width`` / ``height`` set the
    raster output size in px (overriding the figure's intrinsic layout size);
    both ignored for ``.html``. Returns the written path."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".html":
        # VIZ-10: an autoplay animation carries its per-frame duration; kick off
        # `Plotly.animate` at that speed on load (Plotly's own `auto_play` ignores
        # it). Any animation is otherwise saved paused so it doesn't run at the
        # wrong default speed; static figures write unchanged.
        autoplay_ms = animation_autoplay_frame_duration(fig)
        if autoplay_ms is not None:
            fig.write_html(
                str(path),
                auto_play=False,
                post_script=animation_autoplay_post_script(autoplay_ms),
            )
        elif fig.frames:
            fig.write_html(str(path), auto_play=False)
        else:
            fig.write_html(str(path))
        return path
    if suffix in (".png", ".svg", ".pdf"):
        try:
            fig.write_image(str(path), scale=scale, width=width, height=height)
        except OSError:
            raise  # filesystem problem — the original error says it best
        except Exception as exc:  # Kaleido raises various types
            raise RuntimeError(
                f"Static {suffix} export failed: {exc} — if Kaleido can't find "
                "a Chrome/Chromium binary, run `plotly_get_chrome -y` once, or "
                "save as .html instead."
            ) from exc
        return path
    raise ValueError(
        f"Unsupported extension {suffix!r} — use .html, .png, .svg, or .pdf."
    )


def save_figure_layers(
    fig: go.Figure,
    directory: Union[str, Path],
    *,
    fmt: str = "svg",
    scale: int = 2,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> dict:
    """Split a scanpath figure into its layers and save one file per layer (VIZ-5).

    Writes ``<directory>/<layer>.<fmt>`` for each *visible* layer (word boxes /
    fixations / saccades / heatmap / labels / stimulus image / frame) and returns
    ``{layer: Path}``. Each layer is the full figure with only that layer's
    elements and a transparent background, at the same size and axis ranges — so
    the files register perfectly when stacked in Illustrator / Inkscape. ``fmt``
    is any :func:`save_figure` extension without the dot (``svg`` / ``pdf`` are
    vector and best for editing; ``png`` / ``html`` also work). ``scale`` /
    ``width`` / ``height`` are forwarded to :func:`save_figure`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict = {}
    for layer, layer_fig in split_scanpath_layers(fig).items():
        path = directory / f"{layer}.{fmt.lstrip('.')}"
        written[layer] = save_figure(
            layer_fig, path, scale=scale, width=width, height=height
        )
    return written
