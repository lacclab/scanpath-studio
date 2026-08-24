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
import logging
from copy import deepcopy
from pathlib import Path

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
    DEFAULT_ORDER_FONT_COLOR,
    EXPERIMENTAL_ENV_VAR,
    FONT_FAMILY,
    PALETTES,
    SACCADE_CLASS_ORDER,
    UNIFORM_COLOR_FIELD,
    drift_correction_enabled,
    palette_settings,
)
from .experimental_setup import Provenance, SetupSnapshot  # noqa: E402
from .export import annotate_figure  # noqa: E402
from .multipart import (  # noqa: E402
    SCREEN_ID,
    apply_trial_parts_manifest,
    extract_part,
    part_catalog,
    screen_canvas_size,
)
from .plots import (  # noqa: E402
    ANIMATION_FIGURE_OPTIONS,
    COMPARISON_FIGURE_OPTIONS,
    STATIC_FIGURE_OPTIONS,
    FigureSettings,
    add_illustration_label,
    animation_autoplay_frame_duration,
    animation_autoplay_post_script,
    make_comparison_figure,
    make_difference_profile_figure,
    make_distribution_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    make_word_profile_figure,
    split_scanpath_layers,
)


def build_authored_scanpath(
    text: str, events: pd.DataFrame | None = None, **layout_options
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build normalized word/fixation frames from hand-authored reading events.

    When ``events`` is omitted, one centered fixation per laid-out word is used.
    ``layout_options`` are forwarded to :func:`authoring.layout_text`.
    """
    from .authoring import authored_fixations, default_events, layout_text

    words = layout_text(text, **layout_options)
    if events is None:
        events = default_events(words)
    return words, authored_fixations(words, events)


def load_authored_scanpath(
    source: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load an authoring JSON path (or payload), including schema-1 migration."""
    from .authoring import parse_authoring_document

    raw = str(source)
    if raw.lstrip().startswith("{"):
        payload = raw
    else:
        payload = Path(source).read_text(encoding="utf-8")
    document = parse_authoring_document(payload)
    return build_authored_scanpath(
        document.text,
        document.events,
        **document.layout,
    )


TableLike = pd.DataFrame | str | Path
TablesLike = TableLike | list["TableLike"]

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
_FIGURE_CONTEXT_FIELDS = frozenset(
    {"canvas_width", "canvas_height", "base_font_size", "font_family"}
)
_STATIC_FIGURE_PARAMS = frozenset(STATIC_FIGURE_OPTIONS) - _FIGURE_CONTEXT_FIELDS
#: CMP-9. `layout`, `compare_stimulus`, `trial_labels` and `canvas_b` are named
#: parameters of `compare_scanpaths`, so they are not also loose keywords.
_COMPARISON_FIGURE_PARAMS = frozenset(COMPARISON_FIGURE_OPTIONS) - (
    _FIGURE_CONTEXT_FIELDS | {"layout", "compare_stimulus", "trial_labels", "canvas_b"}
)
_ANIMATION_FIGURE_PARAMS = (
    frozenset(ANIMATION_FIGURE_OPTIONS)
    - _FIGURE_CONTEXT_FIELDS
    - {"playback_speed", "autoplay"}
) | {"fixations_b", "words_b"}

_CANONICAL_OPTION_NAMES = {
    "show_words",
    "show_word_labels",
    "show_fixations",
    "show_order",
    "show_saccades",
    "show_saccade_arrows",
    "show_heatmap",
    "heatmap_style",
    "heatmap_norm",
    "x_field",
    "y_field",
    "color_by",
    "heatmap_metric",
    "marker_size_range",
    "order_font_size",
    "order_font_color",
    "show_colorbars",
    "fixation_color_range",
    "heatmap_range",
    "fixation_colorscale",
    "heatmap_colorscale",
    "critical_span_style",
    "highlight_column",
    "saccade_color",
    "saccade_style",
    "saccade_width",
    "saccade_color_mode",
    "saccade_class_colors",
    "saccade_type_legend",
    "saccade_classes",
    "saccade_render_mode",
    "fixation_snap_to_word",
    "fixation_color",
    "fixation_symbol",
    "fixation_opacity",
    "background_color",
    "color_by_line",
    "fit_to_monitor",
    "show_coordinate_grid",
    "coordinate_grid_spacing",
    "line_spacing",
    "scale_text_to_boxes",
    "background_image",
    "background_image_size",
    "background_image_origin",
    "background_image_opacity",
    "word_hover_fields",
    "fixation_hover_fields",
}

CANONICAL_FIGURE_DEFAULTS: dict = FigureSettings.defaults(
    _CANONICAL_OPTION_NAMES
) | dict(
    show_heatmap=True,
    heatmap_metric="duration_ms",
    order_font_color=DEFAULT_ORDER_FONT_COLOR,
    saccade_classes=list(SACCADE_CLASS_ORDER),
    fixation_opacity=0.7,
    background_color=DEFAULT_BACKGROUND_COLOR,
    fit_to_monitor=True,
    word_hover_fields=["text", "word_id", "line_idx", "total_fixation_duration_ms"],
    fixation_hover_fields=["order_in_trial", "duration_ms", "word_id"],
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


def _schema_columns(schema: dict) -> list[tuple[str, str]]:
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
    words: TablesLike | None = None,
    fixations: TablesLike | None = None,
    *,
    word_schema: dict | None = None,
    fix_schema: dict | None = None,
    trial_parts_manifest: dict | None = None,
    image_root: str | Path | None = None,
    image_pattern: str = "{text_id}.png",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and normalize a words/IA table and/or a fixations table.

    ``words`` / ``fixations`` may be DataFrames, paths to ``.csv`` / ``.tsv``
    / ``.parquet`` / ``.feather`` files, glob patterns, or lists of paths —
    multi-file datasets (one file per participant and/or text) are
    concatenated, with each file's stem kept in a ``source_file`` column.
    Column schemas are auto-detected (EyeLink, Gazepoint, and snake_case
    names); pass ``word_schema`` / ``fix_schema`` mappings (field → column
    name, see ``controls.WORD_FIELD_SPECS``) to override detection. For
    per-word reading measures, pass the result to :func:`compute_word_metrics`.

    ``trial_parts_manifest`` accepts a nested parent-trial/parts definition for
    datasets whose source tables identify screens through arbitrary selector
    columns; explicit ``screen_id`` / ``screen_index`` columns can instead be
    mapped directly in each schema. Either table may be omitted for datasets
    that ship only one report: the
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
        if trial_parts_manifest is not None:
            words_norm = apply_trial_parts_manifest(
                words_norm, words_df, trial_parts_manifest, kind="words"
            )
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
        if trial_parts_manifest is not None:
            fixations_norm = apply_trial_parts_manifest(
                fixations_norm,
                fixations_df,
                trial_parts_manifest,
                kind="fixations",
            )
    else:
        fixations_norm = _data.empty_fixations_frame()

    words_norm, fixations_norm = _data.harmonize_frames(words_norm, fixations_norm)
    if image_root is not None:
        words_norm = _data.resolve_stimulus_image_paths(
            words_norm, image_root, image_pattern
        )
        fixations_norm = _data.resolve_stimulus_image_paths(
            fixations_norm, image_root, image_pattern
        )
    return words_norm, fixations_norm


def load_participant_metadata(
    table: TablesLike,
    *,
    id_column: str | None = None,
    participants: pd.DataFrame | list | None = None,
):
    """Load a participant-level metadata table (DATA-20 milestone 1).

    ``table`` is a DataFrame or a path/glob to a CSV/TSV/Parquet/Excel file with
    **one row per reader**: an id column plus anything known about them
    (``native_language``, ``age``, a comprehension score). ``id_column``
    defaults to the first recognised spelling (``participant_id``, ``subject``,
    ``RECORDING_SESSION_LABEL``, …).

    Pass ``participants`` — a normalized frame or a list of ids — to have the
    join validated against the data you actually loaded; the returned object's
    ``.report`` then names the readers missing from either side.

    Returns a
    :class:`~scanpath_studio.metadata.ParticipantMetadata`: the cleaned frame,
    a field registry (name, label, grain, dtype, missingness), and the join
    report. Nothing is broadcast onto the words/fixations frames — use
    :func:`scanpath_studio.metadata.project` to attach chosen columns to a
    per-trial frame, or ``.values_for(pid)`` for one reader.

    >>> words, fixations = load_sample_data()
    >>> meta = load_participant_metadata(
    ...     "readers.csv", participants=fixations
    ... )  # doctest: +SKIP
    >>> meta.names  # doctest: +SKIP
    ('native_language', 'age')
    """
    from scanpath_studio import metadata as _metadata

    frame = _as_dataframe(table, "participant metadata")
    resolved = id_column or _metadata.infer_participant_id_column(frame)
    if not resolved or resolved not in frame.columns:
        raise ValueError(
            "Could not find the participant-id column in the metadata table. "
            f"Columns: {_column_preview(frame)}. Pass id_column= explicitly."
        )
    if isinstance(participants, pd.DataFrame):
        participants = _metadata.participant_ids(participants)
    return _metadata.build_participant_metadata(
        frame,
        resolved,
        source_name=getattr(table, "name", None) or "participant metadata",
        participants=participants,
    )


def load_trial_metadata(
    table: TablesLike,
    *,
    id_column: str | None = None,
    participant_column: str | None = None,
    trials: pd.DataFrame | None = None,
):
    """Load a trial-level metadata table (DATA-29 — milestone 2).

    The sibling of :func:`load_participant_metadata`, one grain down: ``table``
    has **one row per reading** — a trial-id column plus anything known about
    that reading (a list name, a condition, a per-trial comprehension score).

    **The key is yours to state, and it changes what the table means.** Keyed by
    trial id alone, a row describes a *text*, and every reader's reading of it
    inherits that row; pass ``participant_column`` to key by reader **and**
    trial, so a row describes one *reading*. Nothing in a file says which world
    a corpus is in, so this is never inferred — unlike ``id_column``, which
    defaults to the first recognised spelling (``trial_id``, ``item_id``,
    ``TRIAL_INDEX``, …).

    Pass ``trials`` — a normalized fixations/words frame, or any frame with
    ``participant_id`` + ``trial_id`` — to have the join validated against the
    data you actually loaded; the returned ``.report`` then names the trials
    missing from either side.

    Returns a :class:`~scanpath_studio.metadata.TrialMetadata`: the cleaned
    frame, a field registry, and the join report. As with the participant
    table, nothing is broadcast onto the words/fixations frames.

    >>> words, fixations = load_sample_data()
    >>> meta = load_trial_metadata(
    ...     "readings.csv", trials=fixations
    ... )  # doctest: +SKIP
    >>> meta.names  # doctest: +SKIP
    ('list_name', 'comprehension_score')
    """
    from scanpath_studio import metadata as _metadata

    frame = _as_dataframe(table, "trial metadata")
    resolved = id_column or _metadata.infer_trial_id_column(frame)
    if not resolved or resolved not in frame.columns:
        raise ValueError(
            "Could not find the trial-id column in the metadata table. "
            f"Columns: {_column_preview(frame)}. Pass id_column= explicitly."
        )
    if participant_column and participant_column not in frame.columns:
        raise ValueError(
            f"participant_column={participant_column!r} is not in the metadata "
            f"table. Columns: {_column_preview(frame)}."
        )
    keys = _metadata.trial_keys(trials) if trials is not None else None
    return _metadata.build_trial_metadata(
        frame,
        resolved,
        participant_column,
        source_name=getattr(table, "name", None) or "trial metadata",
        keys=keys,
    )


def load_sample_data() -> tuple[pd.DataFrame, pd.DataFrame]:
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


def trial_summary(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Exportable one-row-per-trial reading summary (AN-30)."""
    from .aggregation import trial_summary_table

    return trial_summary_table(words, fixations)


def reader_summary(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Exportable one-row-per-reader reading summary (AN-30)."""
    from .aggregation import reader_summary_table

    return reader_summary_table(words, fixations)


def preprocess_data(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    enabled: bool = False,
    short_policy: str = "Off",
    short_threshold_ms: float = 80.0,
    merge_distance_chars: float = 1.0,
    discard_blink_adjacent: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply the optional preprocessing stage and return words/fixations/QA."""
    if not enabled:
        return words, fixations, pd.DataFrame()

    from .measures import assign_fixations_to_words, enrich_fixations
    from .preprocessing import preprocess_fixations

    assigned = (
        enrich_fixations(assign_fixations_to_words(fixations, words), words)
        if not fixations.empty
        else fixations
    )
    processed, report = preprocess_fixations(
        assigned,
        words,
        settings={
            "enabled": enabled,
            "short_policy": short_policy,
            "short_threshold_ms": short_threshold_ms,
            "merge_distance_chars": merge_distance_chars,
            "discard_blink_adjacent": discard_blink_adjacent,
        },
    )
    return words, processed, report


def analysis_tables(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    pixels_per_degree: float | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Full measure family used by EXP-3 bulk/headless exports."""
    from .measures import assign_fixations_to_words, enrich_fixations
    from .preprocessing import (
        character_grid,
        cleaning_report,
        saccade_table,
        sentence_measures,
    )

    analysis_fixations = (
        enrich_fixations(assign_fixations_to_words(fixations, words), words)
        if not fixations.empty and not words.empty
        else fixations
    )
    measured_words = compute_word_metrics(words, fixations)
    return {
        "fixations": analysis_fixations,
        "saccades": saccade_table(
            analysis_fixations,
            pixels_per_degree=pixels_per_degree,
            raw_gaze=raw_gaze,
            words=words,
        ),
        "word_measures": measured_words,
        "sentence_measures": sentence_measures(measured_words, analysis_fixations),
        "trial_summary": trial_summary(measured_words, analysis_fixations),
        "reader_summary": reader_summary(measured_words, analysis_fixations),
        "characters": character_grid(words),
        "cleaning_qa": cleaning_report(analysis_fixations),
    }


def alignment_sensitivity(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    methods: tuple[str, ...] = ("attach", "slice", "consensus"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Word-measure sensitivity and correction QA across line algorithms.

    PRE-21: a derived surface of vertical drift correction, so it is gated with
    it and raises rather than returning something that looks like a result.
    """
    if not drift_correction_enabled():
        raise ValueError(
            "alignment_sensitivity is not available in this build (PRE-21: "
            "vertical drift correction is not fully integrated yet). Set "
            f"{EXPERIMENTAL_ENV_VAR}=1 to enable it."
        )
    from .preprocessing import measure_sensitivity

    return measure_sensitivity(words, fixations, methods)


def plot_corpus_figure(
    data: pd.DataFrame,
    *,
    kind: str,
    measure_label: str = "Value",
    series_col: str = "series",
    value_col: str = "value",
    colors: tuple[str, ...] | None = None,
    canvas_width: int = 1000,
    base_font_size: int = 14,
    font_family: str = FONT_FAMILY,
) -> go.Figure:
    """Headless corpus profile/distribution/difference plot with shared colours.

    ``profile`` expects ``word_id`` plus ``value_col`` (and optional ``lo`` /
    ``hi``); ``distribution`` expects ``value_col``; ``difference`` expects
    ``word_id`` and ``diff``. When ``series_col`` is present, it defines the
    overlaid profile/distribution series. This is the API counterpart of the
    Corpus Analysis in-view styling controls (AN-29).
    """
    kind = str(kind).lower()
    if kind == "profile":
        profiles = (
            {
                str(name): group.rename(columns={value_col: "value"})
                for name, group in data.groupby(series_col, sort=False)
            }
            if series_col in data
            else {measure_label: data.rename(columns={value_col: "value"})}
        )
        return make_word_profile_figure(
            profiles,
            measure_label=measure_label,
            canvas_width=canvas_width,
            base_font_size=base_font_size,
            font_family=font_family,
            colors=colors,
        )
    if kind == "distribution":
        groups = (
            {
                str(name): group[value_col].dropna().to_numpy()
                for name, group in data.groupby(series_col, sort=False)
            }
            if series_col in data
            else {measure_label: data[value_col].dropna().to_numpy()}
        )
        return make_distribution_figure(
            groups,
            metric_label=measure_label,
            canvas_width=canvas_width,
            base_font_size=base_font_size,
            font_family=font_family,
            colors=colors,
        )
    if kind == "difference":
        return make_difference_profile_figure(
            data,
            measure_label=measure_label,
            canvas_width=canvas_width,
            base_font_size=base_font_size,
            font_family=font_family,
            colors=colors,
        )
    raise ValueError("kind must be 'profile', 'distribution', or 'difference'.")


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


def list_parts(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None = None,
    trial: str | None = None,
) -> pd.DataFrame:
    """Ordered screens in multipart data, optionally narrowed to one parent.

    Legacy single-screen data returns an empty table: it has no synthetic
    exported screen row, so existing callers can distinguish recorded part
    identity from the compatibility default.
    """
    _require_normalized(words, "words")
    _require_normalized(fixations, "fixations")
    catalog = part_catalog(words, fixations)
    if participant is not None:
        catalog = catalog[catalog["participant_id"].astype(str) == str(participant)]
    if trial is not None:
        catalog = catalog[catalog["trial_id"].astype(str) == str(trial)]
    return catalog.reset_index(drop=True)


def _resolve_trial(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None,
    trial: str | None,
    *,
    default_first: bool = False,
) -> tuple[str, str]:
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
    participant: str | None,
    trial: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
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


def _select_part(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None,
    trial: str | None,
    screen: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str, str | None]:
    """Resolve one logical trial and, for multipart data, exactly one screen."""
    trial_words, trial_fixations, pid, tid = _select_trial(
        words, fixations, participant, trial
    )
    catalog = part_catalog(trial_words, trial_fixations)
    if catalog.empty:
        if screen is not None:
            raise ValueError("screen= was supplied for a single-screen trial.")
        return trial_words, trial_fixations, pid, tid, None
    available = catalog[SCREEN_ID].astype(str).tolist()
    selected = str(screen) if screen is not None else available[0]
    if selected not in available:
        raise ValueError(
            f"Unknown screen={selected!r} for participant={pid!r}, trial={tid!r}. "
            f"Available: {', '.join(repr(value) for value in available)}."
        )
    return (
        extract_part(trial_words, pid, tid, selected),
        extract_part(trial_fixations, pid, tid, selected),
        pid,
        tid,
        selected,
    )


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
        sps.plot_scanpath(w, f, palette="Default (colourblind-safe)", saccade_color="#000")

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
    :func:`animate_scanpath` (whose builder supports a subset), and
    ``kind="comparison"`` :func:`compare_scanpaths`. The values are
    the *effective* defaults — :data:`CANONICAL_FIGURE_DEFAULTS` where it sets
    one, the builder's own signature default otherwise — so a scripted caller
    can diff its intended settings against what it would get::

        {k: v for k, v in sps.api.figure_options().items() if k.startswith("show_")}
    """
    if kind == "static":
        params = _STATIC_FIGURE_PARAMS
        defaults = FigureSettings.defaults(params) | CANONICAL_FIGURE_DEFAULTS
    elif kind == "animation":
        params = _ANIMATION_FIGURE_PARAMS
        defaults = FigureSettings.defaults(params) | _animation_defaults()
    elif kind == "comparison":
        # CMP-9: `compare_scanpaths` validates against this set, and its TypeError
        # points the caller here — so it has to be answerable.
        params = _COMPARISON_FIGURE_PARAMS
        defaults = FigureSettings.defaults(params) | {
            key: value
            for key, value in CANONICAL_FIGURE_DEFAULTS.items()
            if key in _COMPARISON_FIGURE_PARAMS
        }
    else:
        raise ValueError(
            f"Unknown kind {kind!r}; use 'static', 'animation' or 'comparison'."
        )
    options = {}
    for name in sorted(params):
        if name in defaults:
            # Some public defaults are ordered field lists. Return an independent
            # value so callers can edit the option reference without changing the
            # canonical defaults used by every later plot.
            options[name] = deepcopy(defaults[name])
        else:  # pragma: no cover - every option is a FigureSettings field
            options[name] = None
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
    method: str | None,
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
    # PRE-21: raise rather than ignore. A share link degrades silently because a
    # human can see the figure and the rail; a script cannot, so quietly
    # returning uncorrected fixations under a stated `drift_correction=` would
    # be a wrong result with no signal. Name the env var so it is one step to fix.
    if not drift_correction_enabled():
        raise ValueError(
            "drift_correction is not available in this build (PRE-21: vertical "
            f"drift correction is not fully integrated yet). Set "
            f"{EXPERIMENTAL_ENV_VAR}=1 to enable it, or pass drift_correction=None."
        )
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
    participant: str | None = None,
    trial: str | None = None,
    *,
    screen: str | None = None,
    canvas_size: tuple[int, int] | None = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    raw_gaze: pd.DataFrame | None = None,
    drift_correction: str | None = None,
    drift_connectors: bool = False,
    fix_index_range: tuple[int, int] | None = None,
    illustration: bool = False,
    illustration_label: str = "auto",
    title: str = "",
    caption: str = "",
    **figure_overrides,
) -> go.Figure:
    """Build the canonical scanpath figure for one trial.

    ``words`` / ``fixations`` are normalized frames from
    :func:`load_scanpath_data`. ``participant`` / ``trial`` may be omitted when
    the frames contain exactly one combo. ``canvas_size`` is the monitor size
    in px; by default it is estimated from the data extents — pass the real
    monitor resolution (e.g. ``(2560, 1440)`` for OneStop) to keep coordinates
    true to scale. For a multipart trial, ``screen`` selects one child screen;
    omitting it selects the first recorded screen and never concatenates
    coordinate spaces. ``raw_gaze`` is a normalized frame (see
    :func:`data.normalize_raw_gaze`) and is filtered to the selected trial.

    ``drift_correction`` (PRE-3/PRE-17) names a method from
    ``alignment.ALGORITHMS``: the ten Carr et al. (2021) algorithms plus
    run-based ``"slice"`` and ``"consensus"``. Each fixation is snapped to its
    assigned text line and coloured by line, exactly as the app's *Drift
    correction* control does. ``drift_connectors=True`` also draws a faint line
    from each fixation's original y to its corrected one.

    ``fix_index_range=(start, end)`` (VIZ-7) draws only fixations ``start``
    through ``end`` (1-based, both inclusive) of the trial — the headless form of
    the app's fixation-index window. It is applied before the drift correction,
    like the app.

    ``title`` / ``caption`` (EXP-5) stamp a title/caption band onto the figure
    without shrinking the plot area, exactly like the rail's *Title & caption on
    the figure* control — literal text here, not the rail's ``{trial_id}``-style
    pattern, since the caller already knows which trial this is.

    Remaining keywords override the app's defaults and are forwarded to
    :func:`plots.make_scanpath_figure` (e.g. ``show_heatmap=False``,
    ``color_by="pass_index"``, ``x_field="order_in_trial"``); an unknown keyword
    raises a ``TypeError`` naming the closest valid options, and
    :func:`figure_options` lists them all with their defaults.
    """
    if illustration:
        figure_overrides = {
            "show_words": False,
            "show_word_labels": True,
            "show_fixations": True,
            "show_order": False,
            "show_saccades": True,
            "show_saccade_arrows": False,
            "show_heatmap": False,
            "color_by": UNIFORM_COLOR_FIELD,
            "saccade_color_mode": "Uniform",
            "saccade_render_mode": "Arc",
            "fixation_snap_to_word": True,
            "fixation_opacity": 1.0,
            **figure_overrides,
        }
    _reject_unknown_options(
        figure_overrides, _STATIC_FIGURE_PARAMS | {"palette"}, "plot_scanpath"
    )
    trial_words, trial_fixations, pid, tid, selected_screen = _select_part(
        words, fixations, participant, trial, screen
    )
    full_fix_range = None
    if not trial_fixations.empty and "order_in_trial" in trial_fixations.columns:
        order = pd.to_numeric(
            trial_fixations["order_in_trial"], errors="coerce"
        ).dropna()
        if not order.empty:
            full_fix_range = (int(order.min()), int(order.max()))
    if canvas_size is None:
        canvas_size = screen_canvas_size(trial_words)
        if canvas_size is None:
            canvas_size = screen_canvas_size(trial_fixations)
        if canvas_size is None:
            canvas_size = _data.compute_canvas_size(trial_words, trial_fixations)
    # Window first, correct second — the app's order (tabs._slice_fix_range runs
    # before alignment.correct), so a windowed correction sees only the kept
    # fixations.
    trial_fixations = _apply_fix_index_range(trial_fixations, fix_index_range, pid, tid)
    settings = _figure_kwargs(figure_overrides)
    label_mode = str(illustration_label).capitalize()
    if label_mode not in {"Auto", "Show", "Hide"}:
        raise ValueError("illustration_label must be 'auto', 'show', or 'hide'.")
    if "illustration_reasons" not in figure_overrides:
        from .illustration import illustration_reasons, resolve_label_reasons

        reasons = illustration_reasons(
            settings,
            fix_index_range=fix_index_range,
            full_fixation_range=full_fix_range,
            raw_gaze_only=trial_fixations.empty and raw_gaze is not None,
        )
        settings["illustration_reasons"] = resolve_label_reasons(label_mode, reasons)
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
        if selected_screen is not None and SCREEN_ID in raw_gaze.columns:
            raw_gaze = extract_part(raw_gaze, pid, tid, selected_screen)
        settings.setdefault("show_raw_gaze", True)
    render_settings = FigureSettings.from_mapping(
        settings,
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        base_font_size=int(base_font_size),
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
    )
    fig = make_scanpath_figure(
        trial_words,
        trial_fixations,
        settings=render_settings,
        raw_gaze=raw_gaze,
    )
    annotate_figure(fig, title=title, caption=caption)
    return fig


def animate_scanpath(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None = None,
    trial: str | None = None,
    *,
    screen: str | None = None,
    canvas_size: tuple[int, int] | None = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    playback_speed: float = 1.0,
    autoplay: bool = True,
    fix_index_range: tuple[int, int] | None = None,
    illustration_label: str = "auto",
    title: str = "",
    caption: str = "",
    **animation_overrides,
) -> go.Figure:
    """Build the animated scanpath replay for one trial.

    Same trial selection and canvas semantics as :func:`plot_scanpath`, including
    ``screen`` selection for multipart trials. The
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

    When ``playback_speed`` is not ``1``, the automatic Illustration label says
    the replay timing was changed. ``illustration_label`` accepts ``"auto"``,
    ``"show"``, or ``"hide"`` like :func:`plot_scanpath`.

    The animation builder accepts a subset of the static figure's options
    (``show_words``, ``show_word_labels``, ``show_saccades``, ``show_order``,
    styling, and second-scanpath overlays) — see ``figure_options("animation")``;
    an unsupported key raises a ``ValueError`` naming the valid ones rather than
    an opaque ``TypeError``. The shared options default to the same values as
    :func:`plot_scanpath` (:data:`CANONICAL_FIGURE_DEFAULTS`), so the replay
    matches the static figure. ``palette=`` (VIZ-18) works here too; the colours
    it implies that the animation doesn't support are dropped rather than
    raising, since the caller named a look, not those individual keys.

    ``title`` / ``caption`` (EXP-5) — same as :func:`plot_scanpath`.
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
    trial_words, trial_fixations, pid, tid, _selected_screen = _select_part(
        words, fixations, participant, trial, screen
    )
    full_fix_range = None
    if not trial_fixations.empty and "order_in_trial" in trial_fixations.columns:
        full_order = pd.to_numeric(
            trial_fixations["order_in_trial"], errors="coerce"
        ).dropna()
        if not full_order.empty:
            full_fix_range = (int(full_order.min()), int(full_order.max()))
    trial_fixations = _apply_fix_index_range(trial_fixations, fix_index_range, pid, tid)
    if canvas_size is None:
        canvas_size = screen_canvas_size(trial_words)
        if canvas_size is None:
            canvas_size = screen_canvas_size(trial_fixations)
        if canvas_size is None:
            canvas_size = _data.compute_canvas_size(trial_words, trial_fixations)
    fixations_b = animation_overrides.pop("fixations_b", None)
    words_b = animation_overrides.pop("words_b", None)
    label_mode = str(illustration_label).capitalize()
    if label_mode not in {"Auto", "Show", "Hide"}:
        raise ValueError("illustration_label must be 'auto', 'show', or 'hide'.")
    if "illustration_reasons" not in animation_overrides:
        from .illustration import illustration_reasons, resolve_label_reasons

        reasons = illustration_reasons(
            {**animation_overrides, "playback_speed": playback_speed},
            fix_index_range=fix_index_range,
            full_fixation_range=full_fix_range,
        )
        animation_overrides["illustration_reasons"] = resolve_label_reasons(
            label_mode, reasons
        )
    render_settings = FigureSettings.from_mapping(
        animation_overrides,
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        base_font_size=int(base_font_size),
        font_family=font_family,
        playback_speed=playback_speed,
        autoplay=autoplay,
    )
    fig = make_scanpath_animation(
        trial_words,
        trial_fixations,
        settings=render_settings,
        fixations_b=fixations_b,
        words_b=words_b,
    )
    add_illustration_label(fig, animation_overrides.get("illustration_reasons"))
    annotate_figure(fig, title=title, caption=caption)
    return fig


def render_parent_trial(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None = None,
    trial: str | None = None,
    *,
    animate: bool = False,
    transition_mode: str = "instant",
    **options,
) -> dict[str, go.Figure]:
    """Render every screen of one logical trial without stitching coordinates.

    The ordered mapping is keyed by ``screen_id``. Each value is the same figure
    returned by :func:`plot_scanpath` or :func:`animate_scanpath`; callers can
    save them into deterministic per-screen files. ``transition_mode`` is
    ``"instant"`` or ``"recorded"``. For animated output, each figure's
    ``layout.meta['transition_after_ms']`` records the delay before the next
    screen (zero for instant mode, or the observed parent-clock gap). No visual
    saccade is ever drawn across the boundary.
    """
    if transition_mode not in {"instant", "recorded"}:
        raise ValueError("transition_mode must be 'instant' or 'recorded'.")
    pid, tid = _resolve_trial(words, fixations, participant, trial)
    catalog = list_parts(words, fixations, pid, tid)
    if catalog.empty:
        renderer = animate_scanpath if animate else plot_scanpath
        return {"screen-1": renderer(words, fixations, pid, tid, **options)}

    screen_ids = catalog[SCREEN_ID].astype(str).tolist()
    rendered: dict[str, go.Figure] = {}
    for position, screen_id in enumerate(screen_ids):
        renderer = animate_scanpath if animate else plot_scanpath
        fig = renderer(words, fixations, pid, tid, screen=screen_id, **options)
        delay = 0.0
        if animate and transition_mode == "recorded" and position < len(screen_ids) - 1:
            current = extract_part(fixations, pid, tid, screen_id)
            following = extract_part(fixations, pid, tid, screen_ids[position + 1])
            if not current.empty and not following.empty:
                current_end = (
                    pd.to_numeric(current["timestamp_ms"], errors="coerce")
                    + pd.to_numeric(current["duration_ms"], errors="coerce").fillna(0)
                ).max()
                next_start = pd.to_numeric(
                    following["timestamp_ms"], errors="coerce"
                ).min()
                if pd.notna(current_end) and pd.notna(next_start):
                    delay = max(0.0, float(next_start - current_end))
        existing_meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
        fig.update_layout(
            meta={
                **existing_meta,
                "participant_id": pid,
                "trial_id": tid,
                "screen_id": screen_id,
                "screen_index": position + 1,
                "transition_mode": transition_mode,
                "transition_after_ms": delay,
            }
        )
        rendered[screen_id] = fig
    return rendered


#: Layout names `compare_scanpaths` accepts, mapped to the builder's spelling.
#: Hyphens are accepted so `cli.render --compare-layout side-by-side`, the share
#: link's `cmp_layout`, and this function all name the layout the same way.
_COMPARE_LAYOUTS = {
    "overlay": "overlay",
    "side_by_side": "side_by_side",
    "side-by-side": "side_by_side",
    "stacked": "stacked",
}


def _compare_setup(
    setup: SetupSnapshot | None,
    canvas_size: tuple[int, int] | None,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    side: str,
) -> SetupSnapshot:
    """One side's `SetupSnapshot`, from an explicit one, a canvas, or the data.

    The provenance is the point, because the overlay gate reads it: a canvas the
    caller *stated* is ``MEASURED``, one inferred from the data extents is
    ``ESTIMATED``. Both count as knowing the screen; neither claims a physical
    display, which a comparison never uses.
    """
    if setup is not None:
        if not isinstance(setup, SetupSnapshot):
            raise TypeError(
                f"{side} must be an experimental_setup.SetupSnapshot, got "
                f"{type(setup).__name__}."
            )
        return setup
    provenance = Provenance.MEASURED
    if canvas_size is None:
        provenance = Provenance.ESTIMATED
        canvas_size = screen_canvas_size(words) or screen_canvas_size(fixations)
        if canvas_size is None:
            canvas_size = _data.compute_canvas_size(words, fixations)
    return SetupSnapshot(
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        screen_provenance=provenance,
    )


def compare_scanpaths(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    trial_a: tuple[str, str],
    trial_b: tuple[str, str],
    *,
    words_b: pd.DataFrame | None = None,
    fixations_b: pd.DataFrame | None = None,
    dataset_b: str = "Dataset B",
    layout: str = "overlay",
    compare_stimulus: str = "both",
    setup: SetupSnapshot | None = None,
    setup_b: SetupSnapshot | None = None,
    canvas_size: tuple[int, int] | None = None,
    labels: tuple[str, str] | None = None,
    style_a: dict | None = None,
    style_b: dict | None = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    fix_index_range: tuple[int, int] | None = None,
    drift_correction: str | None = None,
    title: str = "",
    caption: str = "",
    **figure_overrides,
) -> go.Figure:
    """Build a two-scanpath comparison figure (CMP-9).

    The headless form of the app's **Compare** mode. ``trial_a`` / ``trial_b``
    are ``(participant, trial)`` pairs; ``layout`` is ``"overlay"``,
    ``"side_by_side"`` (``"side-by-side"`` also accepted) or ``"stacked"``.

    **Two datasets.** Pass ``words_b`` / ``fixations_b`` to draw B from a
    *different* corpus. Two corpora can hold the same ``(participant_id,
    trial_id)`` and the builder slices by exactly that pair, so B's participant
    ids are namespaced with ``dataset_b`` inside the throwaway merged frames —
    without it one reading would silently render as two. The frames you pass in
    are never modified, and nothing in the returned figure's data depends on the
    namespace beyond the trace labels.

    **The overlay gate.** Overlaying pools both readings into one axis range, so
    across datasets it is allowed only when both were recorded on the same known
    screen (`experimental_setup.setups_comparable`). Unlike the app — which
    resolves an incomparable overlay to side-by-side, because a user can see
    what they got — this **raises** ``ValueError``: silently returning a
    differently-shaped figure than the one a script asked for is the wrong
    failure mode headlessly. Ask for ``layout="side_by_side"`` to get the app's
    fallback. Nothing is ever rescaled or reprojected.

    ``setup`` / ``setup_b`` are :class:`experimental_setup.SetupSnapshot`
    values — what the gate reads. ``canvas_size`` covers A when you only have a
    resolution; omit both and the canvas is read off the data.

    ``compare_stimulus`` picks whose word boxes and text an **overlay** draws —
    ``"both"`` (default), ``"a"`` or ``"b"``. Two datasets' AOIs coincide only
    when the text is identical. Split layouts ignore it; each panel owns its own
    stimulus.

    Remaining keywords are forwarded to :func:`plots.make_comparison_figure`
    (e.g. ``show_words=False``, ``color_by="duration_ms"``); an unknown one
    raises ``TypeError`` naming the closest valid options. Which settings a
    comparison figure actually honours is the table in
    ``scanpath_studio/CLAUDE.md`` → *Which viz settings apply in which render
    path*.
    """
    from .experimental_setup import setups_comparable
    from .utils import align_compare_columns, extract_trial, qualify_for_compare

    resolved_layout = _COMPARE_LAYOUTS.get(str(layout).strip().lower())
    if resolved_layout is None:
        raise ValueError(
            f"Unknown compare layout {layout!r}; choose one of "
            f"{', '.join(sorted(set(_COMPARE_LAYOUTS.values())))}."
        )
    _reject_unknown_options(
        figure_overrides,
        _COMPARISON_FIGURE_PARAMS | {"palette"},
        "compare_scanpaths",
    )

    cross_dataset = words_b is not None or fixations_b is not None
    words_b = words if words_b is None else words_b
    fixations_b = fixations if fixations_b is None else fixations_b

    pid_a, tid_a = str(trial_a[0]), str(trial_a[1])
    pid_b, tid_b = str(trial_b[0]), str(trial_b[1])
    trial_words_a = extract_trial(words, pid_a, tid_a)
    trial_fix_a = extract_trial(fixations, pid_a, tid_a)
    trial_words_b = extract_trial(words_b, pid_b, tid_b)
    trial_fix_b = extract_trial(fixations_b, pid_b, tid_b)
    for frame, (pid, tid) in ((trial_fix_a, trial_a), (trial_fix_b, trial_b)):
        if frame.empty:
            raise ValueError(
                f"No fixations for participant={pid!r}, trial={tid!r}. "
                f"list_trials() shows what the frames contain."
            )

    setup_a = _compare_setup(
        setup, canvas_size, trial_words_a, trial_fix_a, side="setup"
    )
    resolved_setup_b = _compare_setup(
        setup_b, None, trial_words_b, trial_fix_b, side="setup_b"
    )
    if resolved_layout == "overlay" and cross_dataset:
        comparable, note = setups_comparable(setup_a, resolved_setup_b)
        if not comparable:
            raise ValueError(
                f"{note} Pass layout='side_by_side' (or 'stacked') to compare "
                f"them anyway, each panel drawn to its own screen."
            )
        if note:
            # The canvases match but at least one corpus never recorded a screen,
            # so the overlay is drawn with a caveat rather than refused. A script
            # has no caption to read it in, so it goes to the logger — loud enough
            # to appear in a pipeline's output, quiet enough not to be an error.
            logging.getLogger(__name__).warning("compare_scanpaths: %s", note)

    figure_pid_b = pid_b
    if cross_dataset:
        trial_words_b = qualify_for_compare(trial_words_b, dataset_b)
        trial_fix_b = qualify_for_compare(trial_fix_b, dataset_b)
        figure_pid_b = (
            str(trial_fix_b["participant_id"].iloc[0])
            if not trial_fix_b.empty
            else pid_b
        )
    trial_fix_a = _apply_fix_index_range(trial_fix_a, fix_index_range, pid_a, tid_a)
    trial_fix_b = _apply_fix_index_range(trial_fix_b, fix_index_range, pid_b, tid_b)
    if drift_correction:
        # PRE-21: same contract as plot_scanpath — raise, don't silently skip.
        if not drift_correction_enabled():
            raise ValueError(
                "drift_correction is not available in this build (PRE-21). Set "
                f"{EXPERIMENTAL_ENV_VAR}=1 to enable it, or pass "
                "drift_correction=None."
            )
        from .alignment import correct

        trial_fix_a, _ = correct(trial_fix_a, trial_words_a, drift_correction)
        trial_fix_b, _ = correct(trial_fix_b, trial_words_b, drift_correction)

    merged_words, merged_words_b, _ = align_compare_columns(
        trial_words_a, trial_words_b
    )
    merged_fix, merged_fix_b, _ = align_compare_columns(trial_fix_a, trial_fix_b)
    settings = _figure_kwargs(figure_overrides)
    settings.pop("illustration_reasons", None)
    render_settings = FigureSettings.from_mapping(
        {k: v for k, v in settings.items() if k in _COMPARISON_FIGURE_PARAMS},
        canvas_width=int(setup_a.canvas_width),
        canvas_height=int(setup_a.canvas_height),
        base_font_size=int(base_font_size),
        font_family=font_family,
        layout=resolved_layout,
        compare_stimulus=str(compare_stimulus),
        trial_labels=tuple(labels) if labels else None,
        style_a=style_a,
        style_b=style_b,
        # Only the split layouts read this; an overlay that got here has two
        # equal canvases anyway, so it is the same value either way.
        canvas_b=resolved_setup_b.canvas,
    )
    fig = make_comparison_figure(
        pd.concat([merged_words, merged_words_b], ignore_index=True),
        pd.concat([merged_fix, merged_fix_b], ignore_index=True),
        (pid_a, tid_a),
        (figure_pid_b, tid_b),
        settings=render_settings,
    )
    annotate_figure(fig, title=title, caption=caption)
    return fig


def save_figure(
    fig: go.Figure,
    path: str | Path,
    *,
    scale: int = 2,
    width: int | None = None,
    height: int | None = None,
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
    directory: str | Path,
    *,
    fmt: str = "svg",
    scale: int = 2,
    width: int | None = None,
    height: int | None = None,
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


def cache_status() -> dict:
    """Describe the on-device recovery cache a local app run keeps (ENG-30).

    The app stores completed uploaded datasets, column mappings, view settings
    and annotations under the user's cache directory so a refresh or restart
    resumes where it left off — on localhost/desktop only, never on a hosted
    deployment. This reports that store without launching the app: ``enabled``,
    ``directory``, ``datasets`` (name + per-frame row counts), ``rows``,
    ``annotations``, ``settings``, ``bytes``, ``saved_at``, plus ``exists`` /
    ``readable`` for a missing or unreadable manifest. Delete it with
    :func:`clear_cache`; the same information is in the app's 💾 Session → 🗄️ Recovery cache
    panel and in ``scanpath-studio cache``."""
    from .persistence import cache_status as _cache_status

    return _cache_status(url="http://localhost")


def clear_cache() -> dict:
    """Delete the on-device recovery cache and return its status afterwards.

    Removes only the files this app wrote (``manifest.json`` and the dataset
    Parquet files); anything else in the folder is left alone. A *running* local
    app writes its session back out at the end of its next run — use the app's
    **Forget saved session** button, or ``SCANPATH_STUDIO_PERSIST=0``, to stop
    that."""
    from .persistence import clear_local_state

    clear_local_state()
    return cache_status()
