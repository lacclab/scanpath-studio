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
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

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

from . import column_names as _cn  # noqa: E402
from . import data as _data  # noqa: E402
from .column_names import ColumnNames  # noqa: E402
from .constants import (  # noqa: E402
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ORDER_FONT_COLOR,
    EXPERIMENTAL_ENV_VAR,
    FONT_FAMILY,
    PALETTES,
    PLOTLY_CONFIG,
    SACCADE_CLASS_ORDER,
    UNIFORM_COLOR_FIELD,
    computed_measures_enabled,
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
    _resolve_trial_display_name,
    add_illustration_label,
    make_comparison_figure,
    make_difference_profile_figure,
    make_distribution_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    make_word_profile_figure,
    replay_page,
    split_scanpath_layers,
)


def build_authored_scanpath(
    text: str, events: pd.DataFrame | None = None, **layout_options
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build normalized word/fixation frames from hand-authored reading events.

    When ``events`` is omitted, one centered fixation per laid-out word is used.
    ``layout_options`` are forwarded to `authoring.layout_text`.
    """
    from .authoring import authored_fixations, default_events, layout_text

    words = layout_text(text, **layout_options)
    if events is None:
        events = default_events(words)
    return words, authored_fixations(words, events)


def load_authored_scanpath(
    source: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a scanpath-author JSON file (or its text) as normalized word/fixation frames."""
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
    "illustration_text",
    "word_box_color",
    "word_box_line_opacity",
    "word_box_fill_color",
    "word_box_fill_opacity",
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
    "marker_size_scale",
    "marker_duration_range",
    "duration_size_legend",
    "order_font_size",
    "order_font_color",
    "show_fixation_colorbar",
    "fixation_colorbar_orientation",
    "fixation_colorbar_tickangle",
    "fixation_colorbar_tickfont_size",
    "show_heatmap_colorbar",
    "heatmap_colorbar_orientation",
    "heatmap_colorbar_tickangle",
    "heatmap_colorbar_tickfont_size",
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


def _as_dataframe(table: TablesLike, label: str, *, plan_for=None) -> pd.DataFrame:
    if isinstance(table, pd.DataFrame):
        # DATA-66: a frame this API returned under the dataset's own names goes
        # back to the internal names it was normalized under, so loading it
        # again is the round-trip it was before (a converted width sits beside
        # a renamed left edge, which no detection would pair up).
        return _cn.to_canonical_frame(table)
    items = _data.expand_table_inputs(table)
    for item in items:
        if not isinstance(item, pd.DataFrame) and not Path(item).is_file():
            raise FileNotFoundError(f"{label} table not found: {item}")
    return _data.read_tables(items, plan_for=plan_for)


def _metadata_id_plan(id_column, infer, *extra):
    """``plan_for`` for a metadata table: read its id column(s) as text.

    The same protection the data tables get — read as numbers, readers ``1``
    and ``01`` become one reader before the metadata ever sees them. The id
    column is the caller's, else the one ``infer`` would pick from the header.
    """

    def plan(header) -> _data.ReadPlan:
        names = [str(name) for name in header]
        # `infer_*` treats a row-less frame as "no table" — give it one row.
        resolved = id_column or infer(
            pd.DataFrame([[None] * len(names)], columns=names)
        )
        columns = [*_data.trial_mapping_columns(resolved or []), *extra]
        return _data.ReadPlan(
            identity=tuple(c for c in dict.fromkeys(columns) if c and c in names)
        )

    return plan


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


class SchemaError(ValueError):
    """A table whose columns don't resolve onto the canonical fields.

    Still a ``ValueError`` with the same message, so ``except ValueError``
    callers are unaffected. The parts are kept apart for the CLI, whose
    users cannot pass ``word_schema=``: it keeps :attr:`detail` and replaces
    :attr:`hint` — the API-vocabulary "pass ``word_schema={…}``" line — with its
    own ``--word-schema`` one, built from :attr:`mapping` (the mapping skeleton,
    ``None`` when the fix is to correct a mapping rather than write one)."""

    def __init__(
        self, lines: list[str], hint: str, *, param: str, mapping: dict | None = None
    ) -> None:
        self.detail = "\n".join(lines)
        self.hint = hint
        self.param = param
        self.mapping = mapping
        super().__init__(f"{self.detail}\n{hint}")


def _schema_skeleton_mapping(kind: str, schema: dict) -> dict:
    """What was detected, ``'<column>'`` for the rest. An explicit schema
    replaces auto-detection wholesale, so every required key has to be in it —
    not just the ones that failed."""
    spec = _SCHEMA_SPECS[kind]
    keys = [key for key, _, _ in spec["required"]]
    if spec["groups"]:
        # Suggest whichever coordinate convention is closest to complete.
        best = min(
            spec["groups"],
            key=lambda group: sum(1 for key in group if not schema.get(key)),
        )
        keys += [key for key in best if key not in keys]
    return {key: schema[key] if schema.get(key) else "<column>" for key in keys}


def _schema_skeleton(kind: str, schema: dict) -> str:
    """:func:`_schema_skeleton_mapping` as a copy-pasteable Python literal."""
    items = ", ".join(
        f"{key!r}: {value!r}"
        for key, value in _schema_skeleton_mapping(kind, schema).items()
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
    picks columns that exist. Without this check a mistyped mapping raises a
    bare ``KeyError: '<column>'`` from inside ``normalize_*``. (It could also be
    silently ignored until BUG-58: ``normalize_words`` used to prefer a literal
    ``unique_trial_id`` column over the mapped trial id; the mapping wins now.)"""
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
    raise SchemaError(
        lines,
        f"api.propose_schema(table, {kind!r}) returns the auto-detected mapping to "
        "start from.",
        param=spec["param"],
    )


def _schema_error(
    kind: str, frame: pd.DataFrame, schema: dict, problems: list, explicit: bool = False
) -> SchemaError:
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
            "and takes the first candidate that matches; failing that, a vendor "
            "prefix or suffix on a known name (AOI_LEFT, LEFT_px) is tried next, "
            "accepted only when exactly one column qualifies."
        )
    hint = (
        f"An explicit {param} replaces auto-detection wholesale, so it needs every "
        f"required key, e.g. {param}={_schema_skeleton(kind, schema)} — "
        f"api.propose_schema(df, {kind!r}) returns the auto-detected mapping."
        if explicit
        else f"To override auto-detection pass the full mapping, e.g. "
        f"{param}={_schema_skeleton(kind, schema)} — "
        f"api.propose_schema(df, {kind!r}) returns what was detected."
    )
    return SchemaError(
        lines, hint, param=param, mapping=_schema_skeleton_mapping(kind, schema)
    )


def propose_schema(table: TablesLike, kind: str = "words") -> dict:
    """Auto-detected column mapping for a **raw** (un-normalized) table.

    ``kind`` is ``"words"``, ``"fixations"`` or ``"raw_gaze"``. Returns
    ``{canonical field: source column or None}`` — the same mapping
    [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] infers internally,
    so it's the place to start when detection got a field wrong or couldn't find one:
    edit the dict and pass it back as ``word_schema=`` / ``fix_schema=``::

        from scanpath_studio import api

        schema = api.propose_schema("ia.csv", "words")
        schema["trial"] = "TRIAL_LABEL"
        words, fixations = api.load_scanpath_data("ia.csv", "fix.csv",
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


#: DATA-66: the column vocabularies a loader can return frames in.
NAMES_SOURCE = "source"
NAMES_CANONICAL = "canonical"


class ScanpathData(tuple):
    """What [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]
    returns: the ``(words, fixations)`` frames — so
    ``words, fixations = load_scanpath_data(…)`` unpacks it — plus
    ``column_names``, the dataset's own name for every canonical column, per
    table (``{"words": ColumnNames, "fixations": ColumnNames}``).

    With ``names="source"`` (the default) the frames' columns are the dataset's
    own names and each frame carries its map, so any API function takes it —
    sliced, filtered or merged — and the names it writes are yours. With
    ``names="canonical"`` they are the internal names, the same for every
    dataset."""

    def __new__(cls, words, fixations, column_names=None):
        data = super().__new__(cls, (words, fixations))
        data.column_names = dict(column_names or {})
        return data

    def __getnewargs__(self):
        return (self[0], self[1], self.column_names)

    @property
    def words(self) -> pd.DataFrame:
        return self[0]

    @property
    def fixations(self) -> pd.DataFrame:
        return self[1]


def _check_names_choice(names: str) -> None:
    if names not in (NAMES_SOURCE, NAMES_CANONICAL):
        raise ValueError(
            f'names must be "{NAMES_SOURCE}" (the dataset\'s own column names) '
            f'or "{NAMES_CANONICAL}" (the internal ones), got {names!r}.'
        )


def _named_in(
    frame, label: str, *, optional: bool = False
) -> tuple[pd.DataFrame, ColumnNames | None]:
    """DATA-66: ``(canonical frame, its map)`` for a frame handed to the API.

    A frame :func:`load_scanpath_data` returned under the dataset's own names
    carries its map (`column_names.attach`); it is renamed back here, and the
    map is returned for the call's options, figure text and output frames. A
    canonical frame passes as it is, with no map. ``optional`` takes ``None``
    as the empty table."""
    found = _cn.frame_names(frame)
    frame = _cn.to_canonical_frame(frame)
    frame = (
        _optional_frame(frame, label) if optional else _require_normalized(frame, label)
    )
    return frame, (found[1] if found else None)


def _named_out(frame, table: str, names: ColumnNames | None):
    """An output frame in the names its inputs carried: a table that
    is the dataset's own under its whole map, else (``names`` already
    restricted by the caller) only its ids. Canonical inputs, canonical out."""
    if names is None or frame is None or not isinstance(frame, pd.DataFrame):
        return frame
    return _cn.attach(frame, table, names)


def _call_names(
    given: dict | None = None, **maps: ColumnNames | None
) -> ColumnNames | None:
    """One map across the frames of a call (fixations', then words', then raw
    gaze's), or ``None`` when every frame was canonical. ``given`` is a
    ``column_names=`` argument (``ScanpathData.column_names``), which names
    canonical frames and wins over what the frames carry."""
    if given:
        return _cn.across_tables(
            {
                table: names
                if isinstance(names, ColumnNames)
                else ColumnNames.from_payload(names)
                for table, names in given.items()
            }
        )
    present = {table: names for table, names in maps.items() if names is not None}
    return _cn.across_tables(present) if present else None


def _table_names(
    given: dict | None, table: str, carried: ColumnNames | None
) -> ColumnNames | None:
    """``table``'s own map for a call — from ``column_names=`` when given, else
    what its frame carried. A word option is read in the words table's names
    first: the merged map gives a shared column (``word_id``) the fixations'."""
    if given:
        names = given.get(table)
        if names is None:
            return None
        return (
            names if isinstance(names, ColumnNames) else ColumnNames.from_payload(names)
        )
    return carried


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
    # DATA-66: a frame under the dataset's own names is processed canonically.
    frame = _cn.to_canonical_frame(frame)
    missing = [col for col in _NORMALIZED_ID_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(
            f"{label} frame is not normalized: missing the canonical column(s) "
            f"{', '.join(missing)}. Its columns are: {_column_preview(frame)}. "
            "Pass the frames returned by load_scanpath_data(...) (raw tables have "
            "to go through it first). A frame it returned under the dataset's own "
            "names loses that map when merged or concatenated with another table "
            "(pandas drops DataFrame.attrs there): pass the result through "
            "load_scanpath_data(...) again, or load with names='canonical'."
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
    keep_columns: Iterable[str] | None = None,
    names: str = NAMES_SOURCE,
) -> ScanpathData:
    """Load and normalize a words/IA table and/or a fixations table.

    The columns keep the names your files give them:
    ``CURRENT_FIX_DURATION``, not ``duration_ms``. A column Scanpath Studio
    built, converted, computed or changed keeps its internal name, and
    ``data.column_names`` (a [`ScanpathData`][scanpath_studio.api.ScanpathData])
    records what every column was called. Every API function takes these
    frames, and every column option (``color_by=``, hover fields …) takes
    either name. ``names="canonical"`` returns the internal names instead —
    the same for every dataset, for code that works across them.

    ``words`` / ``fixations`` may be DataFrames, paths to ``.csv`` / ``.tsv`` /
    ``.txt`` / ``.tab`` / ``.parquet`` / ``.feather`` / ``.xlsx`` / ``.xls`` files (or
    a ``.zip`` of them), glob patterns, or lists of paths — multi-file datasets (one
    file per participant and/or text) are concatenated, with each file's stem kept in
    a ``source_file`` column. Column schemas are auto-detected (EyeLink, Gazepoint,
    Tobii, SMI, Pupil Labs, and snake_case names); pass ``word_schema`` /
    ``fix_schema`` mappings (field → column name; see
    [`propose_schema`][scanpath_studio.api.propose_schema])
    to override detection.

    ``trial_parts_manifest`` accepts a nested parent-trial/parts definition for
    datasets whose source tables identify screens through arbitrary selector
    columns; explicit ``screen_id`` / ``screen_index`` columns can instead be
    mapped directly in each schema. Either table may be omitted for datasets
    that ship only one report: the
    missing side comes back as an empty canonical frame and the plots simply
    skip that layer. Words without a participant column (stimulus-level AoIs)
    are copied onto every reading in the fixations — each reading matched by
    its trial id, else the trial id it had before a repeat's ``_r2`` suffix,
    else its ``text_id`` (trial ids that embed the reader), with a
    ``data.StimulusJoinWarning`` (a ``UserWarning``) when some readings match
    none — and fixations without x/y but with a word/AoI ID are placed at
    word-box centers. Columns named in ``data.INTERNAL_COLUMNS`` are the
    pipeline's bookkeeping (``data.drop_internal_columns`` removes them).

    Normalization keeps the mapped fields and the recognised optional ones
    (eye, EyeLink's interest-area measures, linguistic features …) and drops the
    rest. ``keep_columns`` names further columns of your own to carry through
    under their own names — a pupil size, a detection confidence — from
    whichever table has them, so a figure can colour, hover or plot by them
    (the app's *Keep columns*; ``render --keep-columns`` on the command line).

    Returns the normalized ``(words, fixations)`` frames the plotting
    functions expect. Raises ``ValueError`` if a required field can't be found —
    the message names the canonical field, the column names auto-detection
    looked for, and the columns the table actually has — and
    ``data.StimulusJoinError`` (a ``ValueError``) when a stimulus-level words
    table shares neither a trial id nor a ``text_id`` with any reading (or,
    multipart, with every screen a reading has fixations on).
    """
    _check_names_choice(names)
    if words is None and fixations is None:
        raise ValueError("Provide at least one of words= or fixations=.")
    # DATA-66: a frame this API already named is loaded under its internal
    # names; its own map then renames the new one back to the user's.
    prior = {
        table: found[1]
        for table, frame in (("words", words), ("fixations", fixations))
        if (found := _cn.frame_names(frame)) is not None
    }

    if words is not None:
        # BUG-53: a word spelled "None" or "NA" is a word, not a missing cell.
        words_df = _as_dataframe(
            words,
            "words/IA",
            plan_for=lambda header: _data.verbatim_text_plan(header, word_schema),
        )
        explicit = word_schema is not None
        word_schema = word_schema or _data.propose_word_schema(words_df)
        _check_mapped_columns("words", words_df, word_schema)
        problems = _data.validate_word_schema(word_schema)
        if problems:
            raise _schema_error("words", words_df, word_schema, problems, explicit)
        words_norm = _data.normalize_words(
            words_df,
            word_schema,
            keep_columns=_with_optional_fields(
                keep_columns, _data.WORD_OPTIONAL_FIELDS
            ),
        )
        if trial_parts_manifest is not None:
            words_norm = apply_trial_parts_manifest(
                words_norm, words_df, trial_parts_manifest, kind="words"
            )
    else:
        words_norm = _data.empty_words_frame()

    if fixations is not None:
        fixations_df = _as_dataframe(
            fixations,
            "fixations",
            plan_for=lambda header: _data.identity_text_plan(header, fix_schema),
        )
        explicit = fix_schema is not None
        fix_schema = fix_schema or _data.propose_fix_schema(fixations_df)
        _check_mapped_columns("fixations", fixations_df, fix_schema)
        problems = _data.validate_fix_schema(fix_schema)
        if problems:
            raise _schema_error(
                "fixations", fixations_df, fix_schema, problems, explicit
            )
        fixations_norm = _data.normalize_fixations(
            fixations_df,
            fix_schema,
            keep_columns=_with_optional_fields(keep_columns, _data.FIX_OPTIONAL_FIELDS),
        )
        if trial_parts_manifest is not None:
            fixations_norm = apply_trial_parts_manifest(
                fixations_norm,
                fixations_df,
                trial_parts_manifest,
                kind="fixations",
            )
    else:
        fixations_norm = _data.empty_fixations_frame()

    words_norm, fixations_norm, _join, rewrites = _data.harmonize_frames_reporting(
        words_norm, fixations_norm
    )
    if image_root is not None:
        words_norm = _data.resolve_stimulus_image_paths(
            words_norm, image_root, image_pattern
        )
        fixations_norm = _data.resolve_stimulus_image_paths(
            fixations_norm, image_root, image_pattern
        )
    # DATA-66: what each column was called in these files — from the schemas
    # and raw columns normalization read, with the columns the fixups rewrote
    # marked converted.
    maps = {
        table: ColumnNames.from_payload(payload)
        for table, payload in _cn.for_tables(
            {"words": word_schema, "fixations": fix_schema},
            {
                "words": words_df if words is not None else None,
                "fixations": fixations_df if fixations is not None else None,
            },
            rewrites=rewrites,
        ).items()
    }
    maps = {
        table: names_map.through(prior[table]) if table in prior else names_map
        for table, names_map in maps.items()
    }
    if names == NAMES_SOURCE:
        words_norm = _cn.attach(words_norm, "words", maps.get("words"))
        fixations_norm = _cn.attach(fixations_norm, "fixations", maps.get("fixations"))
    return ScanpathData(words_norm, fixations_norm, maps)


def _with_optional_fields(
    keep_columns: Iterable[str] | None, registry: list
) -> set | None:
    """``keep_columns`` as the normalizers take it: ``None`` (every recognised
    optional field, nothing else) when none are named, else those names *plus*
    every optional field — a non-``None`` set would otherwise limit them."""
    if not keep_columns:
        return None
    if isinstance(keep_columns, str):
        keep_columns = [keep_columns]
    return {str(c) for c in keep_columns} | {entry[0] for entry in registry}


def load_participant_metadata(
    table: TablesLike,
    *,
    id_column: str | None = None,
    participants: pd.DataFrame | list | None = None,
):
    """Load a participant-level metadata table.

    ``table`` is a DataFrame or a path/glob to a CSV/TSV/Parquet/Excel file with
    **one row per reader**: an id column plus anything known about them
    (``native_language``, ``age``, a comprehension score). ``id_column``
    defaults to the first recognised spelling (``participant_id``, ``subject``,
    ``RECORDING_SESSION_LABEL``, …).

    Pass ``participants`` — a normalized frame or a list of ids — to have the
    join validated against the data you actually loaded; the returned object's
    ``.report`` then names the readers missing from either side.

    Returns a
    `ParticipantMetadata`: the cleaned frame,
    a field registry (name, label, grain, dtype, missingness), and the join
    report. Nothing is broadcast onto the words/fixations frames — use
    `scanpath_studio.metadata.project` to attach chosen columns to a
    per-trial frame, or ``.values_for(pid)`` for one reader.

    >>> words, fixations = load_sample_data()
    >>> meta = load_participant_metadata(
    ...     "readers.csv", participants=fixations
    ... )  # doctest: +SKIP
    >>> meta.names  # doctest: +SKIP
    ('native_language', 'age')
    """
    from scanpath_studio import metadata as _metadata

    frame = _as_dataframe(
        table,
        "participant metadata",
        plan_for=_metadata_id_plan(id_column, _metadata.infer_participant_id_column),
    )
    resolved = id_column or _metadata.infer_participant_id_column(frame)
    if not resolved or resolved not in frame.columns:
        raise ValueError(
            "Could not find the participant-id column in the metadata table. "
            f"Columns: {_column_preview(frame)}. Pass id_column= explicitly."
        )
    if isinstance(participants, pd.DataFrame):
        participants = _metadata.participant_ids(_cn.to_canonical_frame(participants))
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
    """Load a trial-level metadata table.

    The sibling of
    [`load_participant_metadata`][scanpath_studio.api.load_participant_metadata], one
    grain down: ``table`` has **one row per reading** — a trial-id column plus anything
    known about that reading (a list name, a condition, a per-trial comprehension
    score).

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

    Returns a `TrialMetadata`: the cleaned
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

    frame = _as_dataframe(
        table,
        "trial metadata",
        plan_for=_metadata_id_plan(
            id_column, _metadata.infer_trial_id_column, participant_column
        ),
    )
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
    keys = (
        _metadata.trial_keys(_cn.to_canonical_frame(trials))
        if trials is not None
        else None
    )
    return _metadata.build_trial_metadata(
        frame,
        resolved,
        participant_column,
        source_name=getattr(table, "name", None) or "trial metadata",
        keys=keys,
    )


def load_text_metadata(
    table: TablesLike,
    *,
    id_column: str | list[str] | None = None,
    texts: pd.DataFrame | list | None = None,
):
    """Load a text-level metadata table — the third grain.

    ``table`` has **one row per text** — a text-id column plus anything known about that
    text (genre, difficulty, a stimulus-level comprehension score). Flat grain, like
    [`load_participant_metadata`][scanpath_studio.api.load_participant_metadata]: never
    keyed by reader, since a text is a stimulus rather than something one reader owns.
    ``id_column`` defaults to the first recognised spelling (``text_id``,
    ``paragraph_id``, ``stimulus_id``, …) and may be several columns to build a
    composite id, the same way the uploaded data's own Text ID mapping does.

    Pass ``texts`` — a normalized fixations/words frame, or any iterable of
    text ids — to have the join validated against the data you actually
    loaded; the returned ``.report`` then names the texts missing from either
    side.

    Returns a `TextMetadata`: the cleaned
    frame, a field registry, and the join report. As with the other two
    grains, nothing is broadcast onto the words/fixations frames.

    >>> words, fixations = load_sample_data()
    >>> meta = load_text_metadata(
    ...     "texts.csv", texts=words
    ... )  # doctest: +SKIP
    >>> meta.names  # doctest: +SKIP
    ('genre', 'difficulty')
    """
    from scanpath_studio import metadata as _metadata

    frame = _as_dataframe(
        table,
        "text metadata",
        plan_for=_metadata_id_plan(id_column, _metadata.infer_text_id_column),
    )
    resolved = id_column or _metadata.infer_text_id_column(frame)
    if not resolved or any(
        c not in frame.columns for c in _metadata.trial_mapping_columns(resolved)
    ):
        raise ValueError(
            "Could not find the text-id column in the metadata table. "
            f"Columns: {_column_preview(frame)}. Pass id_column= explicitly."
        )
    if isinstance(texts, pd.DataFrame):
        texts = _metadata.text_keys(_cn.to_canonical_frame(texts))
    return _metadata.build_text_metadata(
        frame,
        resolved,
        source_name=getattr(table, "name", None) or "text metadata",
        keys=texts,
    )


def load_sample_data(*, names: str = NAMES_SOURCE) -> ScanpathData:
    """Return the bundled OneStop demo, normalized and ready to plot: two
    readers, twelve paragraphs each, every one of them with fixations. Under
    the demo's own column names; ``names="canonical"`` for the internal ones
    (see [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data])."""
    return load_scanpath_data(*_data.load_sample_data(), names=names)


def load_raw_gaze(
    table: TablesLike,
    *,
    raw_gaze_schema: dict | None = None,
    names: str = NAMES_SOURCE,
) -> pd.DataFrame:
    """Load and normalize a raw (sample-level) gaze table for ``raw_gaze=``.

    The third table [`plot_scanpath`][scanpath_studio.api.plot_scanpath] can draw, under
    the fixations: one row per eye-tracker sample, with a participant, a trial, ``x`` /
    ``y`` and usually a timestamp. ``table`` is a DataFrame, path, glob or list of
    paths, like [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]'s, and
    the columns are auto-detected the same way; pass ``raw_gaze_schema`` (field →
    column, see ``api.propose_schema(table, "raw_gaze")``) to override the detection.
    ``plot_scanpath`` keeps only the plotted trial's (and screen's) samples, so one
    table can serve a whole corpus::

        raw_gaze = sps.load_raw_gaze("gaze_samples.csv")
        fig = sps.plot_scanpath(words, fixations, "p1", "t3", raw_gaze=raw_gaze)

    Under the table's own column names, like ``load_scanpath_data``'s;
    ``names="canonical"`` for the internal ones.
    """
    _check_names_choice(names)
    frame = _as_dataframe(
        table,
        "raw gaze",
        plan_for=lambda header: _data.identity_text_plan(
            header, raw_gaze_schema, kind="raw_gaze"
        ),
    )
    explicit = raw_gaze_schema is not None
    schema = raw_gaze_schema or _data.propose_raw_gaze_schema(frame)
    _check_mapped_columns("raw_gaze", frame, schema)
    problems = _data.validate_raw_gaze_schema(schema)
    if problems:
        raise _schema_error("raw_gaze", frame, schema, problems, explicit)
    normalized = _data.normalize_raw_gaze(frame, schema)
    if names == NAMES_CANONICAL:
        return normalized
    return _cn.attach(
        normalized, "raw_gaze", _cn.from_schema("raw_gaze", schema, frame.columns)
    )


def load_sample_raw_gaze(*, names: str = NAMES_SOURCE) -> pd.DataFrame:
    """The bundled demo's raw gaze, normalized — what the app overlays on it.

    OneStop ships no sample-level gaze, so this is **synthesized** from one of
    the demo's real trials and covers that trial alone."""
    return load_raw_gaze(_data.load_sample_raw_gaze(), names=names)


def check_data_health(
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Values that loaded as numbers but cannot be right — the Data page's *Data checks*.

    Checks the normalized tables (from
    [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] /
    [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze]) for fixations lasting
    0 ms or less or with an infinite duration or onset, fixations and raw-gaze
    samples whose position is missing or infinite, word boxes with no area or no
    finite position, and per-screen screen sizes that are not finite and
    positive. One row per check that found
    anything: ``table``, ``check``, ``problem``, the ``columns`` it read (in the
    names the frames carry),
    ``rows`` of ``of_rows``, the ``trials`` they fall in, a ``breakdown`` by
    kind, ``severity`` (``"note"`` for raw-gaze gaps, which blinks and track
    loss make ordinary), ``what_happens`` to those rows in the app, and a few
    ``examples``. An empty frame means every check passed. Nothing is changed
    or dropped::

        words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
        print(sps.check_data_health(words, fixations))
    """
    from .data_health import findings_frame

    return findings_frame(_health_findings(words, fixations, raw_gaze))


def _health_findings(words, fixations, raw_gaze) -> list:
    """`data_health.check_data_health` on frames in either naming, its findings
    naming the columns as the frames did. The CLI's ``check`` prints
    these; :func:`check_data_health` tabulates them."""
    from dataclasses import replace

    from .data_health import check_data_health as _check

    named = {}
    for table, frame in (
        ("words", words),
        ("fixations", fixations),
        ("raw_gaze", raw_gaze),
    ):
        found = _cn.frame_names(frame) if frame is not None else None
        named[table] = (
            _cn.to_canonical_frame(frame) if frame is not None else None,
            found[1] if found else None,
        )
    findings = _check(*(frame for frame, _names in named.values()))

    def _in_own_names(finding):
        # DATA-66: name the columns and example fields as the frames did.
        names = named[finding.table][1]
        if names is None:
            return finding
        return replace(
            finding,
            columns=tuple(names.display(c) for c in finding.columns),
            examples=tuple(
                {names.display(k): v for k, v in row.items()}
                for row in finding.examples
            ),
        )

    return [_in_own_names(f) for f in findings]


def _require_computed_measures(name: str) -> None:
    """Refuse a held-back computation, naming the switch that enables it.

    These values are computed by Scanpath Studio rather than read from the
    dataset, and each needs checking by hand before it is released. A script
    gets an error rather than an unchecked number.
    """
    if not computed_measures_enabled():
        raise ValueError(
            f"{name} is not available in this release: its values are computed "
            "by Scanpath Studio and have not been validated yet. Set "
            f"{EXPERIMENTAL_ENV_VAR}=1 to use it anyway."
        )


def compute_word_metrics(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Per-word reading measures (FFD/FPRT/RPD/TFD, skips, regressions, …).

    Experimental: raises unless ``SCANPATH_EXPERIMENTAL=1``. Pre-aggregated
    columns in ``words`` (EyeLink IA exports) are preserved; anything missing is
    computed from fixations + word bounding boxes. Takes the normalized frames
    from [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data], and
    answers in the names they carry."""
    _require_computed_measures("compute_word_metrics")
    words, word_names = _named_in(words, "words")
    fixations, _fix_names = _named_in(fixations, "fixations")
    return _named_out(_data.compute_word_metrics(words, fixations), "words", word_names)


def trial_summary(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Exportable one-row-per-trial reading summary.

    Experimental: raises unless ``SCANPATH_EXPERIMENTAL=1``."""
    _require_computed_measures("trial_summary")
    from .aggregation import trial_summary_table

    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    names = _call_names(fixations=fix_names, words=word_names)
    return _named_out(
        trial_summary_table(words, fixations),
        "trial_summary",
        names.identity() if names else None,
    )


def reader_summary(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """Exportable one-row-per-reader reading summary.

    Experimental: raises unless ``SCANPATH_EXPERIMENTAL=1``."""
    _require_computed_measures("reader_summary")
    from .aggregation import reader_summary_table

    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    names = _call_names(fixations=fix_names, words=word_names)
    return _named_out(
        reader_summary_table(words, fixations),
        "reader_summary",
        names.identity() if names else None,
    )


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
    """Apply the optional preprocessing stage and return words/fixations/QA.

    Experimental: raises unless ``SCANPATH_EXPERIMENTAL=1``."""
    _require_computed_measures("preprocess_data")
    if not enabled:
        return words, fixations, pd.DataFrame()

    from .measures import assign_fixations_to_words, enrich_fixations
    from .preprocessing import preprocess_fixations

    given_words = words
    words, _word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)

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
    # The QA report is derived: it names its ids as the fixations do.
    return (
        given_words,
        _named_out(processed, "fixations", fix_names),
        _named_out(report, "cleaning_qa", fix_names.identity() if fix_names else None),
    )


def analysis_tables(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    pixels_per_degree: float | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """The tables ``scanpath-studio analyze`` writes, as a dict of frames.

    Experimental: raises unless ``SCANPATH_EXPERIMENTAL=1``.

    ``fixations``, ``saccades``, ``word_measures``, ``sentence_measures``,
    ``trial_summary``, ``reader_summary``, ``characters`` and ``cleaning_qa``.

    ``word_measures`` is the words table with the reading measures it
    *brought*: none are computed here, and a words table that carries none
    leaves ``word_measures`` out.
    """
    _require_computed_measures("analysis_tables")
    from .aggregation import reader_summary_table, trial_summary_table
    from .measures import assign_fixations_to_words, enrich_fixations
    from .preprocessing import (
        character_grid,
        cleaning_report,
        saccade_table,
        sentence_measures,
    )

    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    if raw_gaze is not None:
        raw_gaze, _gaze_names = _named_in(raw_gaze, "raw_gaze")
    analysis_fixations = (
        enrich_fixations(assign_fixations_to_words(fixations, words), words)
        if not fixations.empty and not words.empty
        else fixations
    )
    tables = {
        "fixations": analysis_fixations,
        "saccades": saccade_table(
            analysis_fixations,
            pixels_per_degree=pixels_per_degree,
            raw_gaze=raw_gaze,
            words=words,
        ),
        "word_measures": words,
        "sentence_measures": sentence_measures(words, analysis_fixations),
        "trial_summary": trial_summary_table(words, analysis_fixations),
        "reader_summary": reader_summary_table(words, analysis_fixations),
        "characters": character_grid(words),
        "cleaning_qa": cleaning_report(analysis_fixations),
    }
    if not _data.brought_reading_measures(words):
        del tables["word_measures"]
    # DATA-66: in the names the frames carried — the two tables that are the
    # dataset's own under their whole map, the derived ones by their ids only
    # (the export bundle's rule, `export._ARTIFACT_TABLE`).
    names = _call_names(fixations=fix_names, words=word_names)
    if names is None:
        return tables
    own = {"fixations": fix_names, "word_measures": word_names}
    return {
        artifact: _named_out(
            table,
            artifact,
            own[artifact] if artifact in own else names.identity(),
        )
        for artifact, table in tables.items()
    }


def alignment_sensitivity(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    methods: tuple[str, ...] = ("attach", "slice", "consensus"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Word-measure sensitivity and correction QA across line algorithms.

    A derived surface of vertical drift correction, so it is gated with
    it and raises rather than returning something that looks like a result.
    """
    if not drift_correction_enabled():
        raise ValueError(
            "alignment_sensitivity is not available in this release (vertical "
            "drift correction is not fully integrated yet). Set "
            f"{EXPERIMENTAL_ENV_VAR}=1 to enable it."
        )
    from .preprocessing import measure_sensitivity

    words, word_names = _named_in(words, "words")
    fixations, fix_names = _named_in(fixations, "fixations")
    names = _call_names(fixations=fix_names, words=word_names)
    tables = measure_sensitivity(words, fixations, methods)
    if names is None:
        return tables
    return tuple(
        _named_out(table, "alignment_sensitivity", names.identity()) for table in tables
    )


#: The columns each corpus-figure kind reads; ``"<value>"`` stands for
#: ``value_col``. EXP-13: without the check a table lacking one surfaced as a
#: bare ``KeyError: 'value'`` from inside the builder.
_CORPUS_COLUMNS = {
    "profile": ("word_id", "<value>"),
    "distribution": ("<value>",),
    # EXP-16: the builder draws its "no data" placeholder for a table with no
    # `diff` — right for the app's empty states, but headlessly it meant a
    # figure with nothing on it and an exit code of 0.
    "difference": ("word_id", "diff"),
}


def _require_corpus_columns(data: pd.DataFrame, kind: str, value_col: str) -> None:
    required = [
        value_col if column == "<value>" else column
        for column in _CORPUS_COLUMNS.get(kind, ())
    ]
    missing = [column for column in required if column not in data.columns]
    if not missing:
        return
    hint = (
        f" Name the measure column with value_col= (--value-col on the CLI); "
        f"it is {value_col!r} now."
        if value_col in missing
        else ""
    )
    raise ValueError(
        f"A {kind!r} corpus figure reads the column(s) "
        f"{', '.join(repr(column) for column in missing)}, which the table doesn't "
        f"have. Columns present ({len(data.columns)}): {_column_preview(data)}.{hint}"
    )


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
    overlaid profile/distribution series. A table missing a column its ``kind``
    reads raises ``ValueError`` naming it and the columns present.
    """
    kind = str(kind).lower()
    _require_corpus_columns(data, kind, value_col)
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


def _optional_frame(frame, label: str) -> pd.DataFrame:
    """``frame`` checked as normalized, or the empty canonical frame for ``None``.

    A dataset recorded as raw gaze alone has no words or fixations
    table, so the plotting entry points take ``None`` for either — the same
    empty canonical frame `load_scanpath_data` returns for a table it was not
    given."""
    if frame is None:
        return (
            _data.empty_words_frame()
            if label == "words"
            else _data.empty_fixations_frame()
        )
    return _require_normalized(frame, label)


def list_trials(
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    *,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Plottable ``(participant_id, trial_id)`` combos.

    Combos present in both frames when both are loaded; for single-report
    datasets (words-only or fixations-only), combos from whichever frame has
    data. ``raw_gaze`` (a frame from
    [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze]) adds the trials that
    only its samples cover — every trial, for a dataset recorded as raw gaze
    alone (pass ``None`` for ``words`` and ``fixations`` then). The id columns
    take the names the frames carry."""
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    gaze_names = None
    if raw_gaze is not None:
        raw_gaze, gaze_names = _named_in(raw_gaze, "raw_gaze")
    names = _call_names(fixations=fix_names, words=word_names, raw_gaze=gaze_names)
    cols = ["participant_id", "trial_id"]
    if words.empty or fixations.empty:
        present = fixations if words.empty else words
        combos = present[cols].drop_duplicates()
    else:
        combos = words[cols].drop_duplicates().merge(fixations[cols].drop_duplicates())
    if raw_gaze is not None and not raw_gaze.empty:
        # The app's rule (`utils.combo_source`): a trial is listed when it has
        # fixations — or, in a dataset without any, words — or when it has raw
        # gaze. So a trial with words and samples but no fixations is listed,
        # while one the intersection above drops for having fixations but no
        # words stays dropped: its samples add nothing the rule is about.
        known = _data.trial_keys(fixations if not fixations.empty else words)
        samples = raw_gaze[cols].drop_duplicates()
        extra = samples[
            [
                (str(p), str(t)) not in known
                for p, t in zip(samples["participant_id"], samples["trial_id"])
            ]
        ]
        combos = pd.concat([combos, extra], ignore_index=True)
    combos = combos.sort_values(cols).reset_index(drop=True)
    return _named_out(combos, "trials", names.identity() if names else None)


def list_parts(
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    participant: str | None = None,
    trial: str | None = None,
    *,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Ordered screens in multipart data, optionally narrowed to one parent.

    Single-screen data returns an empty table. A trial recorded as raw gaze
    alone takes its screens from ``raw_gaze`` (its ``screen_id``), decided per
    trial — so a samples-only trial keeps its screens in a dataset whose other
    trials have fixations.
    """
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    gaze_names = None
    if raw_gaze is not None:
        raw_gaze, gaze_names = _named_in(raw_gaze, "raw_gaze")
    names = _call_names(fixations=fix_names, words=word_names, raw_gaze=gaze_names)
    catalog = part_catalog(words, fixations)
    if raw_gaze is not None and SCREEN_ID in raw_gaze.columns:
        # Per trial, as `_select_part` and the app decide it: a trial neither
        # words nor fixations cover takes its screens from its samples.
        samples = part_catalog(raw_gaze)
        covered = _data.trial_keys(words) | _data.trial_keys(fixations)
        own = [
            (str(p), str(t)) not in covered
            for p, t in zip(samples["participant_id"], samples["trial_id"])
        ]
        if any(own):
            catalog = pd.concat([catalog, samples[own]], ignore_index=True)
    if participant is not None or trial is not None:
        # An id spelled before composite ids escaped a `_` inside a part.
        participant, trial = (
            None if participant is None else str(participant),
            None if trial is None else str(trial),
        )
        respelled = _data.respell_reading(
            participant or "",
            trial or "",
            zip(catalog["participant_id"], catalog["trial_id"], strict=True),
        )
        participant = respelled[0] if participant is not None else None
        trial = respelled[1] if trial is not None else None
    if participant is not None:
        catalog = catalog[catalog["participant_id"].astype(str) == str(participant)]
    if trial is not None:
        catalog = catalog[catalog["trial_id"].astype(str) == str(trial)]
    return _named_out(
        catalog.reset_index(drop=True), "parts", names.identity() if names else None
    )


def _resolve_trial(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    participant: str | None,
    trial: str | None,
    *,
    default_first: bool = False,
    raw_gaze: pd.DataFrame | None = None,
) -> tuple[str, str]:
    """Resolve to one (participant_id, trial_id), validating what was given.

    A nonexistent participant/trial always raises — naming which of the two ids
    is unknown, a few valid values and the closest spellings. An underspecified
    selection matching several trials raises too, unless ``default_first`` picks
    the first match (the CLI's behavior, mirroring the app's default selection).
    ``raw_gaze`` makes the trials only its samples cover selectable.
    """
    combos = _cn.to_canonical_frame(list_trials(words, fixations, raw_gaze=raw_gaze))
    if combos.empty:
        raise ValueError("No (participant, trial) combo exists in the data.")
    scoped = combos
    # Ids written before composite ids escaped a `_` inside a part
    # (`data.compose_id`) still find their reading when that is unambiguous.
    readings = list(zip(combos["participant_id"], combos["trial_id"], strict=True))
    if participant is not None:
        participant = _data.respell_reading(
            participant, trial if trial is not None else "", readings
        )[0]
        scoped = scoped[scoped["participant_id"] == str(participant)]
        if scoped.empty:
            raise ValueError(
                f"No trial matches participant={participant!r}: that participant "
                f"id is not in the data. {_value_hint(combos, 'participant_id', participant)}"
            )
    if trial is not None:
        trial = _data.respell_reading(
            participant if participant is not None else "", trial, readings
        )[1]
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
            f"{fix} list_trials(words, fixations, raw_gaze=…) lists all "
            f"{len(combos)} combos."
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
    *,
    raw_gaze: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
    pid, tid = _resolve_trial(words, fixations, participant, trial, raw_gaze=raw_gaze)
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
    *,
    raw_gaze: pd.DataFrame | None = None,
    screen_param: str = "screen",
) -> tuple[pd.DataFrame, pd.DataFrame, str, str, str | None]:
    """Resolve one logical trial and, for multipart data, exactly one screen.

    ``screen_param`` is the keyword the caller took the screen as, so an error
    names the one to fix (``screen_b=`` for a comparison's second reading)."""
    trial_words, trial_fixations, pid, tid = _select_trial(
        words, fixations, participant, trial, raw_gaze=raw_gaze
    )
    catalog = part_catalog(trial_words, trial_fixations)
    if (
        catalog.empty
        and trial_words.empty
        and trial_fixations.empty
        and raw_gaze is not None
        and SCREEN_ID in raw_gaze.columns
    ):
        # VIZ-45: a trial recorded as raw gaze alone takes its screens from the
        # samples, so one screen's coordinate space is drawn at a time — as for
        # words and fixations — rather than every screen stacked into one.
        catalog = part_catalog(_data.filter_raw_gaze(raw_gaze, [pid], [tid]))
    if catalog.empty:
        if screen is not None:
            raise ValueError(
                f"{screen_param}= was supplied for a single-screen trial "
                f"(participant={pid!r}, trial={tid!r})."
            )
        return trial_words, trial_fixations, pid, tid, None
    available = catalog[SCREEN_ID].astype(str).tolist()
    selected = str(screen) if screen is not None else available[0]
    if selected not in available:
        raise ValueError(
            f"Unknown {screen_param}={selected!r} for participant={pid!r}, "
            f"trial={tid!r}. "
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
    """Window the trial to fixations ``start..end`` of ``order_in_trial``.

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
    """Expand a ``palette=`` override into the colour kwargs it stands for.

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


#: Figure options whose value names a column → (the table it is read from, its
#: CLI flag, the values that are not columns, what to do instead). EXP-17: the
#: builders look the column up and draw *nothing* when it is missing, so a
#: misspelling rendered a flat-coloured / unmarked figure without a word.
_COLUMN_OPTIONS = {
    "color_by": (
        "fixations",
        "--color-by",
        (UNIFORM_COLOR_FIELD, "line"),
        f"Use {UNIFORM_COLOR_FIELD!r} for one flat colour, 'line' to colour by "
        "text line, or one of the columns below.",
    ),
    "highlight_column": (
        "words",
        "--highlight-column",
        (),
        "It names the boolean words column marking the text to highlight; pass "
        "None ('' on the CLI) to highlight nothing.",
    ),
}


#: DATA-66: the figure options whose value names one column, and those naming a
#: list of them — each takes the dataset's own name as well as the internal one.
_ONE_COLUMN_OPTIONS = (
    "color_by",
    "highlight_column",
    "heatmap_metric",
    "word_hover_measure",
    "word_heatmap_col",
    "x_field",
    "y_field",
)
_COLUMN_LIST_OPTIONS = ("word_hover_fields", "fixation_hover_fields")
#: …and of those, the ones naming a column of the words table.
_WORD_OPTIONS = frozenset(
    ("highlight_column", "word_hover_measure", "word_heatmap_col", "word_hover_fields")
)


def _canonical_options(
    overrides: dict,
    names: ColumnNames | None,
    *,
    words: ColumnNames | None = None,
) -> dict:
    """``overrides`` with every column it names in the internal vocabulary —
    a word option in the words table's names (``words``) before the merged
    map's.

    ``heatmap_metric`` is checked here too: the heatmap weights by the fixation
    duration or counts fixations, and any other value used to count silently —
    which, once the dataset's own names are accepted, a misspelt name would."""
    out = dict(overrides)

    def canonical(option: str, value) -> str:
        if words is not None and option in _WORD_OPTIONS:
            found = words.to_canonical(value)
            if found != str(value):
                return found
        return names.to_canonical(value) if names is not None else value

    if names is not None or words is not None:
        for option in _ONE_COLUMN_OPTIONS:
            if isinstance(out.get(option), str):
                out[option] = canonical(option, out[option])
        for option in _COLUMN_LIST_OPTIONS:
            if out.get(option) is not None and not isinstance(out[option], str):
                out[option] = [canonical(option, value) for value in out[option]]
    metric = out.get("heatmap_metric")
    if metric not in (None, "duration_ms", "counts"):
        duration = (
            names.label("duration_ms")
            if names is not None and names.source("duration_ms")
            else "duration_ms"
        )
        raise ValueError(
            f"heatmap_metric={metric!r} (--heatmap-metric on the CLI) must be "
            f"the fixation duration ({duration!r}) or 'counts'."
        )
    return out


def _column_labels(
    names: ColumnNames | None,
    word_frame,
    fixation_frame,
    *,
    words: ColumnNames | None = None,
) -> dict | None:
    """`FigureSettings.column_labels` for frames that carried names — the
    figure's text in the dataset's own names, as the app writes it, a word
    column also under the words table's own name (`table_figure_labels`)."""
    if names is None:
        return None
    labels = names.figure_labels(
        [
            column
            for frame in (word_frame, fixation_frame)
            if frame is not None
            for column in frame
        ]
    )
    if words is not None and word_frame is not None:
        for column, label in words.figure_labels(word_frame.columns).items():
            if labels.get(column) != label:
                labels[f"words:{column}"] = label
    return labels


def _check_column_options(
    overrides: dict, *, words: pd.DataFrame, fixations: pd.DataFrame
) -> None:
    """Raise when an option the caller *named* points at no column.

    Only explicit values are checked: ``highlight_column`` defaults to OneStop's
    ``is_in_aspan``, which most corpora do not have and which the builder then
    rightly skips. An empty table is not checked — there is nothing to colour."""
    frames = {"words": words, "fixations": fixations}
    for name, (kind, flag, synthetic, advice) in _COLUMN_OPTIONS.items():
        value = overrides.get(name)
        if value is None or value == "" or value in synthetic:
            continue
        frame = frames[kind]
        present = [str(column) for column in frame.columns]
        if frame.empty or str(value) in present:
            continue
        close = difflib.get_close_matches(str(value), present, n=3, cutoff=0.6)
        hint = f" Closest: {', '.join(repr(c) for c in close)}." if close else ""
        raise ValueError(
            f"{name}={value!r} ({flag} on the CLI) names no column of the "
            f"{kind} table.{hint} {advice} Columns present ({len(present)}): "
            f"{_column_preview(frame)}."
        )


def figure_options(kind: str = "static") -> dict:
    """Every figure keyword a builder accepts → the default it renders with.

    ``kind="static"`` covers [`plot_scanpath`][scanpath_studio.api.plot_scanpath],
    ``kind="animation"`` [`animate_scanpath`][scanpath_studio.api.animate_scanpath]
    (whose builder supports a subset), and ``kind="comparison"``
    [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths]. The values are the
    *effective* defaults — `CANONICAL_FIGURE_DEFAULTS` where it sets one, the builder's
    default otherwise — so a scripted caller can diff its intended
    settings against what it would get::

        {k: v for k, v in sps.figure_options().items() if k.startswith("show_")}
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
    """Snap fixations to their assigned text line, in place of the raw y.

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
            "drift_correction is not available in this release (vertical "
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
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
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
    column_names: dict | None = None,
    **figure_overrides,
) -> go.Figure:
    """Build the canonical scanpath figure for one trial.

    ``words`` / ``fixations`` are normalized frames from
    [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]. ``participant`` /
    ``trial`` may be omitted when the frames contain exactly one combo. ``canvas_size``
    is the monitor size in px; by default it is estimated from the data extents — pass
    the real monitor resolution (e.g. ``(2560, 1440)`` for OneStop) to keep coordinates
    true to scale. For a multipart trial, ``screen`` selects one child screen; omitting
    it selects the first recorded screen and never concatenates coordinate spaces.
    ``raw_gaze`` is a frame from [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze],
    filtered to the selected trial and drawn as recorded. It can be the only table:
    for a dataset recorded as raw gaze alone pass ``None`` for ``words`` and
    ``fixations`` (``plot_scanpath(raw_gaze=samples, trial=…)``) — the trial is
    looked up in the samples, the canvas is estimated from their extent, and the
    figure is the samples alone. Nothing is derived from them: no fixations are
    detected, so the fixation, saccade and heatmap layers stay empty.

    ``drift_correction`` / ``drift_connectors`` are experimental: without
    ``SCANPATH_EXPERIMENTAL=1`` any ``drift_correction`` other than ``None`` /
    ``"off"`` raises ``ValueError``.

    ``fix_index_range=(start, end)`` draws only fixations ``start``
    through ``end`` (1-based, both inclusive) of the trial — the headless form of
    the app's fixation-index window.

    ``title`` / ``caption`` stamp a title/caption band onto the figure
    without shrinking the plot area, exactly like the rail's *Title* / *Caption*
    rows — literal text here, not the rail's ``{trial_id}``-style
    pattern, since the caller already knows which trial this is.

    Remaining keywords override the app's defaults and are forwarded to
    `plots.make_scanpath_figure` (e.g. ``show_heatmap=False``,
    ``color_by="pass_index"``, ``x_field="order_in_trial"``); an unknown keyword raises
    a ``TypeError`` naming the closest valid options, and
    [`figure_options`][scanpath_studio.api.figure_options] lists them all with their
    defaults. A ``color_by`` / ``highlight_column`` naming a column the trial's table
    doesn't have raises a ``ValueError`` naming the closest ones, rather than drawing
    without it.

    Frames under the dataset's own column names (what ``load_scanpath_data``
    returns by default) are read through the map they carry, and an option naming
    a column takes either name. ``column_names`` is that map for frames loaded with
    ``names="canonical"`` (``data.column_names``): the options then take the
    dataset's names too, and the figure's text uses them.
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
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    gaze_names = None
    if raw_gaze is not None:
        raw_gaze, gaze_names = _named_in(raw_gaze, "raw_gaze")
    names = _call_names(
        column_names, fixations=fix_names, words=word_names, raw_gaze=gaze_names
    )
    word_side = _table_names(column_names, "words", word_names)
    figure_overrides = _canonical_options(figure_overrides, names, words=word_side)
    trial_words, trial_fixations, pid, tid, selected_screen = _select_part(
        words, fixations, participant, trial, screen, raw_gaze=raw_gaze
    )
    if raw_gaze is not None:
        raw_gaze = _data.filter_raw_gaze(raw_gaze, [pid], [tid])
        if selected_screen is not None and SCREEN_ID in raw_gaze.columns:
            raw_gaze = extract_part(raw_gaze, pid, tid, selected_screen)
    _check_column_options(
        figure_overrides, words=trial_words, fixations=trial_fixations
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
            # VIZ-45: a trial with no fixations is sized from its samples, as the
            # app sizes a raw-gaze-only dataset's canvas.
            canvas_size = _data.compute_canvas_size(
                trial_words,
                trial_fixations
                if not trial_fixations.empty or raw_gaze is None
                else raw_gaze,
            )
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
        settings.setdefault("show_raw_gaze", True)
    render_settings = FigureSettings.from_mapping(
        settings,
        canvas_width=int(canvas_size[0]),
        canvas_height=int(canvas_size[1]),
        base_font_size=int(base_font_size),
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
        column_labels=_column_labels(
            names, trial_words, trial_fixations, words=word_side
        ),
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
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    participant: str | None = None,
    trial: str | None = None,
    *,
    screen: str | None = None,
    screen_b: str | None = None,
    canvas_size: tuple[int, int] | None = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    playback_speed: float = 1.0,
    autoplay: bool = True,
    fix_index_range: tuple[int, int] | None = None,
    fix_index_range_b: tuple[int, int] | None = None,
    illustration_label: str = "auto",
    title: str = "",
    caption: str = "",
    column_names: dict | None = None,
    trial_b: tuple[str, str] | None = None,
    dataset_b: str | None = None,
    setup: SetupSnapshot | None = None,
    setup_b: SetupSnapshot | None = None,
    **animation_overrides,
) -> go.Figure:
    """Build the animated scanpath replay for one trial.

    Same trial selection, canvas and column-name semantics as
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath] (``column_names`` included),
    and ``screen`` selection for multipart trials. The replay takes the reading time divided by
    ``playback_speed``: save it as interactive HTML with
    [`save_figure`][scanpath_studio.api.save_figure], whose page keeps that clock
    itself, or rasterize it to GIF/MP4 with `animation_export.export_animation`, which
    lasts as long. (`fig.show()` plays it on Plotly's own frame queue, which runs
    slow.) ``fix_index_range=(start, end)`` replays only that window of the trial's
    fixations (1-based, inclusive), like
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath].

    With ``autoplay`` (default ``True``) the saved interactive HTML auto-starts
    the replay on load *at ``playback_speed``* —
    [`save_figure`][scanpath_studio.api.save_figure] honors the marker the builder
    stamps on the figure. Pass ``autoplay=False`` to save a figure that opens paused
    (press ▶ Play to run it). Autoplay only affects the interactive HTML; a GIF/MP4
    always plays from its first frame.

    When ``playback_speed`` is not ``1``, the automatic Illustration label says
    the replay timing was changed. ``illustration_label`` accepts ``"auto"``,
    ``"show"``, or ``"hide"`` like [`plot_scanpath`][scanpath_studio.api.plot_scanpath].

    In a co-animation ``fix_index_range`` windows A only (the app's
    rule — A's slider never cuts B), ``fix_index_range_b`` windows B, and
    ``fixation_flags_b`` gives B flags of its own (``None``: A's
    ``fixation_flags``, or the ``fixation_flags`` of ``style_b`` when it
    names some).

    ``style_a`` / ``style_b`` style the two scanpaths of a co-animation as they
    style [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths]' — the
    same keys (``fix_color``, ``marker_size_range``, ``opacity``, ``hollow``,
    ``saccade_color``, ``saccade_style``, ``saccade_width``), resolved the same
    way, so the replay and the static comparison draw each reading alike. The
    replay has no saccade-class filter, so a style naming ``saccade_classes``
    raises ``ValueError``. A lone replay ignores both.

    ``trial_b=(participant, trial)`` co-animates a second reading on the same
    clock, like the app's Animate + Compare. It is looked up in ``words_b`` /
    ``fixations_b`` when given, else in ``words`` / ``fixations`` — the way
    [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes it.
    Without ``trial_b``, ``words_b`` / ``fixations_b`` must hold one trial; B
    frames holding several raise ``ValueError`` rather than drawing them all. A
    multipart B is drawn at ``screen_b`` — looked up in B's own trial — or at
    its first recorded screen without it, as A is with ``screen``.

    **Two datasets.** Both readings are drawn in A's coordinates, so a
    co-animation is an overlay, and a reading from another dataset has to share
    A's screen. Name that dataset with ``dataset_b`` (or give its ``setup_b``)
    and the pair is checked the way `compare_scanpaths` checks an overlay: two
    different canvases raise ``IncomparableScreensError``, a ``ValueError``,
    rather than draw. ``setup`` / ``setup_b`` are
    `experimental_setup.SetupSnapshot` values; a side without one is read off
    its data — the extent of that one trial, which rarely spans the whole
    screen, so state both when you know them — and ``canvas_size`` covers A
    when you only have a resolution. ``dataset_b`` also prefixes B's
    participant ids with the dataset's name, as `compare_scanpaths` does, so a
    hover says whose reader it is. ``words_b`` / ``fixations_b`` passed without
    either are taken to be from A's dataset, as `render` passes them for
    ``--compare-with`` alone, and are not checked: two readings of one corpus
    can span different extents, and inferring a canvas from each would refuse
    pairs that shared a screen.

    The animation builder accepts a subset of the static figure's options
    (``show_words``, ``show_word_labels``, ``show_saccades``, ``show_order``, styling,
    and second-scanpath overlays) — see ``figure_options("animation")``; an unsupported
    key raises a ``ValueError`` naming the valid ones. The shared options default to the same values as
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath] (`CANONICAL_FIGURE_DEFAULTS`),
    so the replay matches the static figure. ``palette=`` works here too; the
    colours it implies that the animation doesn't support are dropped rather than
    raising, since the caller named a look, not those individual keys.

    ``title`` / ``caption`` — same as
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath].

    The replay is made of fixations, so a trial without any — one recorded as
    raw gaze alone, or a words-only one — raises ``ValueError`` rather than
    returning an empty replay, and ``raw_gaze=`` is refused: the replay draws no
    raw-gaze layer, and nothing detects fixations from samples. Draw samples with
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath]`(raw_gaze=…)`.
    """
    if "raw_gaze" in animation_overrides:
        raise ValueError(
            "animate_scanpath replays fixations and has no raw-gaze layer, and "
            "Scanpath Studio does not detect fixations from gaze samples. Draw the "
            "samples with plot_scanpath(..., raw_gaze=...) instead."
        )
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
    for side in ("style_a", "style_b"):
        style = animation_overrides.get(side)
        if isinstance(style, dict) and style.get("saccade_classes") is not None:
            raise ValueError(
                f"{side}['saccade_classes'] filters a comparison figure's "
                "saccades; the co-animation has no saccade-class filter. Drop "
                "it, or draw the pair with compare_scanpaths."
            )
    named = {k: v for k, v in animation_overrides.items() if k in explicit}
    # Same defaults as the static figure for every option both builders share, so
    # `plot_scanpath` and `animate_scanpath` don't render the same trial
    # differently (the app feeds both from one settings dict).
    animation_overrides = {**_animation_defaults(), **animation_overrides}
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    names = _call_names(column_names, fixations=fix_names, words=word_names)
    word_side = _table_names(column_names, "words", word_names)
    animation_overrides = _canonical_options(
        animation_overrides, names, words=word_side
    )
    named = _canonical_options(named, names, words=word_side)
    trial_words, trial_fixations, pid, tid, _selected_screen = _select_part(
        words, fixations, participant, trial, screen
    )
    if trial_fixations.empty:
        raise ValueError(
            f"participant={pid!r}, trial={tid!r} has no fixations to replay — the "
            "replay is built from fixations. A trial recorded as raw gaze alone "
            "can be drawn with plot_scanpath(..., raw_gaze=...); its samples are "
            "not turned into fixations."
        )
    _check_column_options(named, words=trial_words, fixations=trial_fixations)
    full_fix_range = None
    if not trial_fixations.empty and "order_in_trial" in trial_fixations.columns:
        full_order = pd.to_numeric(
            trial_fixations["order_in_trial"], errors="coerce"
        ).dropna()
        if not full_order.empty:
            full_fix_range = (int(full_order.min()), int(full_order.max()))
    trial_fixations = _apply_fix_index_range(trial_fixations, fix_index_range, pid, tid)
    # A's screen: a stated `setup`, else `canvas_size`, else read off the data —
    # the order `compare_scanpaths` resolves it in, and what CMP-21's gate reads.
    setup_a = _compare_setup(
        setup, canvas_size, trial_words, trial_fixations, side="setup"
    )
    passed_b = (
        animation_overrides.pop("words_b", None),
        animation_overrides.pop("fixations_b", None),
    )
    second_dataset = dataset_b is not None or setup_b is not None
    if second_dataset and all(frame is None for frame in passed_b):
        raise ValueError(
            "dataset_b / setup_b describe scanpath B's own dataset, but neither "
            "words_b nor fixations_b was passed. Pass B's frames too, or leave "
            "both out to draw trial_b from these frames."
        )
    if screen_b is not None and trial_b is None and all(f is None for f in passed_b):
        raise ValueError(
            "screen_b= picks scanpath B's screen, but there is no scanpath B. "
            "Pass trial_b=(participant, trial) too."
        )
    words_b, fixations_b = _second_reading(
        words, fixations, *passed_b, trial_b, screen_b=screen_b
    )
    if second_dataset and fixations_b is not None and not fixations_b.empty:
        _refuse_co_animation_across_screens(
            setup_a,
            setup_b,
            words_b,
            fixations_b,
            a_inferred=setup is None and canvas_size is None,
        )
    elif fixations_b is not None and not fixations_b.empty:
        # One dataset, two screen sizes it knows of: refused as the app and
        # `compare_scanpaths`' overlay refuse them.
        same_b = _same_dataset_setup_b(
            setup_a,
            setup_b,
            a_known=setup is not None or canvas_size is not None,
            words_a=trial_words,
            fixations_a=trial_fixations,
            words_b=words_b,
            fixations_b=fixations_b,
        )
        if same_b is not None:
            _refuse_co_animation_across_screens(
                setup_a, same_b, words_b, fixations_b, a_inferred=False
            )
    full_fix_range_b = None
    if (
        fixations_b is not None
        and not fixations_b.empty
        and "order_in_trial" in fixations_b.columns
    ):
        order_b = pd.to_numeric(fixations_b["order_in_trial"], errors="coerce").dropna()
        if not order_b.empty:
            full_fix_range_b = (int(order_b.min()), int(order_b.max()))
    if fix_index_range_b is not None and fixations_b is not None:
        pid_b, tid_b = (str(v) for v in (trial_b or ("B", "B")))
        fixations_b = _apply_fix_index_range(
            fixations_b, fix_index_range_b, pid_b, tid_b
        )
    if dataset_b is not None:
        # As `compare_scanpaths` and the app do: B's readers carry their
        # dataset's name, so a hover says whose reader it is.
        from .utils import qualify_for_compare

        words_b, fixations_b = (
            None if frame is None else qualify_for_compare(frame, dataset_b)
            for frame in (words_b, fixations_b)
        )
    label_mode = str(illustration_label).capitalize()
    if label_mode not in {"Auto", "Show", "Hide"}:
        raise ValueError("illustration_label must be 'auto', 'show', or 'hide'.")
    if "illustration_reasons" not in animation_overrides:
        from .illustration import illustration_reasons, resolve_label_reasons

        reasons = illustration_reasons(
            {**animation_overrides, "playback_speed": playback_speed},
            fix_index_range=fix_index_range,
            full_fixation_range=full_fix_range,
            # CMP-24: B's own flags and window, when it co-animates.
            fixation_flags_b=animation_overrides.get("fixation_flags_b")
            if fixations_b is not None
            else None,
            fix_index_range_b=fix_index_range_b,
            full_fixation_range_b=full_fix_range_b,
        )
        animation_overrides["illustration_reasons"] = resolve_label_reasons(
            label_mode, reasons
        )
    render_settings = FigureSettings.from_mapping(
        animation_overrides,
        canvas_width=int(setup_a.canvas_width),
        canvas_height=int(setup_a.canvas_height),
        base_font_size=int(base_font_size),
        font_family=font_family,
        playback_speed=playback_speed,
        autoplay=autoplay,
        column_labels=_column_labels(
            names, trial_words, trial_fixations, words=word_side
        ),
    )
    fig = make_scanpath_animation(
        trial_words,
        trial_fixations,
        settings=render_settings,
        fixations_b=fixations_b,
        words_b=words_b,
    )
    add_illustration_label(
        fig,
        animation_overrides.get("illustration_reasons"),
        text=render_settings.illustration_text,
    )
    annotate_figure(fig, title=title, caption=caption)
    return fig


def _second_reading(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None,
    trial_b: tuple[str, str] | None,
    *,
    screen_b: str | None = None,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Scanpath B's frames for a co-animation, cut to one reading.

    The animation builder draws every row it is handed, so frames passed the
    way `compare_scanpaths` takes them — B's whole corpus — drew every fixation
    in it. ``trial_b`` picks the reading, in B's own frames when given and A's
    otherwise, as `compare_scanpaths` does; without it B's frames must hold one
    trial, since guessing among several would draw somebody else's reading.
    A multipart B keeps one screen, never all of them — each is its own
    coordinate space: ``screen_b``, else its first, as A without ``screen=``
    and the app's B navigator start.
    """
    if trial_b is None:
        source = fixations_b if fixations_b is not None else words_b
        if source is None or source.empty:
            return words_b, fixations_b
        label = "fixations_b" if fixations_b is not None else "words_b"
        pairs = _require_normalized(source, label)[
            ["participant_id", "trial_id"]
        ].drop_duplicates()
        if len(pairs) > 1:
            raise ValueError(
                f"{label} holds {len(pairs)} trials, so the second scanpath is "
                "ambiguous. Pass trial_b=(participant, trial) to pick one — "
                "compare_scanpaths takes it the same way."
            )
        pid_b, tid_b = (str(value) for value in pairs.iloc[0])
    else:
        pid_b, tid_b = str(trial_b[0]), str(trial_b[1])
        words_b = words if words_b is None else words_b
        fixations_b = fixations if fixations_b is None else fixations_b

    def one_reading(frame: pd.DataFrame | None, label: str) -> pd.DataFrame | None:
        # `extract_part` masks afresh, as `_select_trial` slices A. Not
        # `utils.extract_trial`: its position cache is keyed by the frame's
        # identity, so an in-place edit between two calls handed back somebody
        # else's rows.
        if frame is None or frame.empty:
            return frame
        return extract_part(_require_normalized(frame, label), pid_b, tid_b)

    trial_words_b = one_reading(words_b, "words_b")
    trial_fix_b = one_reading(fixations_b, "fixations_b")
    if trial_b is not None and (trial_fix_b is None or trial_fix_b.empty):
        raise ValueError(
            f"No fixations for the second scanpath participant={pid_b!r}, "
            f"trial={tid_b!r}. list_trials() shows what the frames contain."
        )
    catalog = part_catalog(trial_words_b, trial_fix_b)
    if catalog.empty:
        if screen_b is not None:
            raise ValueError(
                "screen_b= was supplied for a single-screen trial "
                f"(participant={pid_b!r}, trial={tid_b!r})."
            )
    else:
        available = catalog[SCREEN_ID].astype(str).tolist()
        if screen_b is not None and str(screen_b) not in available:
            raise ValueError(
                f"Unknown screen_b={str(screen_b)!r} for participant={pid_b!r}, "
                f"trial={tid_b!r}. "
                f"Available: {', '.join(repr(value) for value in available)}."
            )
        screen_b = str(screen_b) if screen_b is not None else available[0]
        trial_words_b, trial_fix_b = (
            extract_part(frame, pid_b, tid_b, screen_b)
            if frame is not None and SCREEN_ID in frame.columns
            else frame
            for frame in (trial_words_b, trial_fix_b)
        )
    return trial_words_b, trial_fix_b


def _inferred_screen_hint(*, a_inferred: bool, b_inferred: bool) -> str:
    """How to state a screen that a refusal only read off the data.

    `setups_comparable` says the readings were *recorded* on different screens,
    but a screen nobody stated is the extent of that trial's data, which rarely
    spans the whole display — so the refusal names the parameter that states it.
    """
    if a_inferred and b_inferred:
        return (
            " Neither screen was stated, so both were read off the data, which "
            "rarely spans the whole screen; if they were shown on one, pass it as "
            "setup= and setup_b=."
        )
    if a_inferred:
        return (
            " A's screen was read off its data, which rarely spans the whole "
            "screen; if both were shown on one, pass A's as setup= or canvas_size=."
        )
    if b_inferred:
        return (
            " B's screen was read off its data, which rarely spans the whole "
            "screen; if both were shown on one, pass B's as setup_b=."
        )
    return ""


def _same_dataset_setup_b(
    setup_a: SetupSnapshot,
    setup_b: SetupSnapshot | None,
    *,
    a_known: bool,
    words_a: pd.DataFrame | None,
    fixations_a: pd.DataFrame | None,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None,
) -> SetupSnapshot | None:
    """B's screen when it is known to differ from A's, within one dataset.

    One dataset can hold screens of different sizes, so a same-dataset pair is
    gated too — but only on screens either side actually *knows*: a stated
    setup, or the selected screen's own canvas columns. Two data extents say
    nothing (two readings of one screen rarely span the same area). Returns
    B's snapshot when both are known and the canvases differ — the pair an
    overlay or co-animation must refuse — else ``None``. ``a_known`` is whether
    the caller stated A's screen.
    """
    own_b = screen_canvas_size(words_b) or screen_canvas_size(fixations_b)
    a_known = (
        a_known
        or screen_canvas_size(words_a) is not None
        or screen_canvas_size(fixations_a) is not None
    )
    if setup_b is not None:
        resolved = setup_b
    elif own_b is not None:
        resolved = replace(
            setup_a, canvas_width=int(own_b[0]), canvas_height=int(own_b[1])
        )
    else:
        return None
    if not a_known or resolved.canvas == setup_a.canvas:
        return None
    return resolved


def _refuse_co_animation_across_screens(
    setup_a: SetupSnapshot,
    setup_b: SetupSnapshot | None,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame,
    *,
    a_inferred: bool,
) -> None:
    """Refuse a co-animation of two datasets shown on different screens.

    A co-animation draws both readings on one clock in A's coordinates, which
    makes it an overlay, so it is held to `compare_scanpaths`'s overlay gate: the
    same `setups_comparable` predicate and the same error, with B's screen read
    off its data when the caller did not state it.
    """
    from .experimental_setup import IncomparableScreensError, setups_comparable

    resolved_b = _compare_setup(
        setup_b,
        None,
        words_b if words_b is not None else pd.DataFrame(),
        fixations_b,
        side="setup_b",
    )
    comparable, note = setups_comparable(setup_a, resolved_b)
    if not comparable:
        hint = _inferred_screen_hint(a_inferred=a_inferred, b_inferred=setup_b is None)
        raise IncomparableScreensError(
            f"{note} A co-animation replays both readings on one clock in one "
            "coordinate space, so none was drawn; compare them with "
            "compare_scanpaths(layout='side_by_side') (or 'stacked'), each drawn "
            f"to its own screen.{hint}",
            reason=note,
        )
    if note:
        # As in `compare_scanpaths`: matching canvases, but at least one screen
        # was never recorded — drawn, with the caveat where a script can see it.
        logging.getLogger(__name__).warning("animate_scanpath: %s", note)


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
    returned by [`plot_scanpath`][scanpath_studio.api.plot_scanpath] or
    [`animate_scanpath`][scanpath_studio.api.animate_scanpath]; callers can save them
    into deterministic per-screen files. ``transition_mode`` is ``"instant"`` or
    ``"recorded"``. For animated output, each figure's
    ``layout.meta['transition_after_ms']`` records the delay before the next screen
    (zero for instant mode, or the observed parent-clock gap). No visual saccade is ever
    drawn across the boundary.
    """
    if transition_mode not in {"instant", "recorded"}:
        raise ValueError("transition_mode must be 'instant' or 'recorded'.")
    raw_gaze = options.get("raw_gaze")
    pid, tid = _resolve_trial(
        _cn.to_canonical_frame(words),
        _cn.to_canonical_frame(fixations),
        participant,
        trial,
        raw_gaze=_cn.to_canonical_frame(raw_gaze),
    )
    # Read here under the internal names; the renderers take the frames as
    # given and name their figures as they were named (DATA-66).
    catalog = _cn.to_canonical_frame(
        list_parts(words, fixations, pid, tid, raw_gaze=raw_gaze)
    )
    canonical_fixations = _cn.to_canonical_frame(fixations)
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
            current = extract_part(canonical_fixations, pid, tid, screen_id)
            following = extract_part(
                canonical_fixations, pid, tid, screen_ids[position + 1]
            )
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
    screen: str | None = None,
    screen_b: str | None = None,
    words_b: pd.DataFrame | None = None,
    fixations_b: pd.DataFrame | None = None,
    dataset_b: str = "Dataset B",
    raw_gaze: pd.DataFrame | None = None,
    raw_gaze_b: pd.DataFrame | None = None,
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
    fix_index_range_b: tuple[int, int] | None = None,
    drift_correction: str | None = None,
    title: str = "",
    caption: str = "",
    column_names: dict | None = None,
    **figure_overrides,
) -> go.Figure:
    """Build a two-scanpath comparison figure.

    The headless form of the app's **Compare** mode. ``trial_a`` / ``trial_b``
    are ``(participant, trial)`` pairs; ``layout`` is ``"overlay"``,
    ``"side_by_side"`` (``"side-by-side"`` also accepted) or ``"stacked"``.

    **Multipart trials.** Each scanpath is one screen, never a whole multipart
    trial: every screen is its own coordinate space, so pooling them would draw
    saccades across page boundaries. ``screen`` picks A's screen and
    ``screen_b`` B's, independently — B's is looked up in B's own frames, so it
    may be a later page or another dataset's. Either one left out is that
    trial's first recorded screen, as in
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath];
    ``list_parts()`` lists them. A screen named for a single-screen trial, or
    one the trial does not have, raises ``ValueError``.

    **Two datasets.** Pass ``words_b`` / ``fixations_b`` to draw B from a
    *different* corpus. Two corpora can hold the same ``(participant_id,
    trial_id)`` and the builder slices by exactly that pair, so B's participant
    ids are namespaced with ``dataset_b`` inside the throwaway merged frames —
    without it one reading would silently render as two. The frames you pass in
    are never modified, and nothing in the returned figure's data depends on the
    namespace beyond the trace labels.

    **The overlay gate.** Across datasets an overlay needs both canvases to be
    the same size; otherwise this raises ``ValueError`` (the app falls back to
    side by side). One dataset can hold screens of different sizes too, so a
    same-dataset pair is refused the same way when the two selected screens
    carry different canvases (``canvas_width`` / ``canvas_height`` columns) or
    ``setup_b`` states another screen. Pass ``layout="side_by_side"`` or
    ``"stacked"`` to compare readings from different screens; each panel is
    then drawn to its own. Nothing is rescaled.

    ``setup`` / ``setup_b`` are `experimental_setup.SetupSnapshot`
    values — what the gate reads. ``canvas_size`` covers A when you only have a
    resolution; omit both and the canvas is read off the data.

    **Stimulus images.** ``background_image`` is A's page. A split layout draws
    B's panel over ``background_image_b`` (with ``background_image_size_b`` /
    ``background_image_origin_b``) and over nothing without it — never A's,
    since sharing a dataset says nothing about sharing a page.

    ``compare_stimulus`` picks whose word boxes and text an **overlay** draws —
    ``"both"`` (default), ``"a"`` or ``"b"``. Two datasets' AOIs coincide only
    when the text is identical. Split layouts ignore it; each panel owns its own
    stimulus.

    **Per-scanpath style.** ``style_a`` / ``style_b`` restyle one scanpath:
    ``fix_color``, ``marker_size_range``, ``opacity``, ``hollow``,
    ``saccade_color``, ``saccade_style``, ``saccade_width``, ``box_color`` —
    the outline of that reading's word boxes, its ``fix_color`` when left out —
    ``box_fill_color``, their fill, ``word_box_fill_color`` when left out — and
    ``raw_gaze_color``, that reading's raw-gaze samples, its ``fix_color`` when
    left out. These three are this figure's only: the co-animation draws one set
    of boxes, in ``word_box_color`` / ``word_box_fill_color``, and no raw gaze,
    and ignores them.

    **Filters, per scanpath.** ``fixation_flags`` and
    ``saccade_classes`` filter both scanpaths, as they filter
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath]'s one; the same two keys
    in ``style_a`` / ``style_b`` give that scanpath its own, overriding them —
    e.g. ``style_b={"fixation_flags": {"short": {"mode": "Discard",
    "threshold_ms": 80}}, "saccade_classes": ["regression"]}``. The app's
    Compare mode draws A under the rail's filters and B under B's own.
    ``fix_index_range`` windows both scanpaths; ``fix_index_range_b`` gives B a
    window of its own (the app's B slider).

    **Raw gaze.** ``raw_gaze`` is a frame from
    [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze]; each reading's samples
    are drawn under its scanpath, in that scanpath's colour (``raw_gaze_marker_size``
    / ``raw_gaze_opacity`` style them). It serves both readings of a
    same-dataset comparison; across datasets it is A's, and ``raw_gaze_b`` is
    B's. Passing either turns the layer on; ``show_raw_gaze=False`` keeps it off.

    Remaining keywords are forwarded to `plots.make_comparison_figure`
    (e.g. ``show_words=False``, ``color_by="duration_ms"``); an unknown one
    raises ``TypeError`` naming the closest valid options;
    ``figure_options("comparison")`` lists the accepted keywords. Column names
    follow [`plot_scanpath`][scanpath_studio.api.plot_scanpath]'s rule: A's
    names (or ``column_names``) name the options and the figure's text, and
    either dataset's frames may come under their own names.
    """
    from .experimental_setup import IncomparableScreensError, setups_comparable
    from .utils import (
        align_compare_columns,
        qualify_for_compare,
        self_compare_participant,
        separate_self_compare,
    )

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
    # DATA-66: A's names name the figure's text and its options; every frame,
    # A's or B's, is processed under the internal names.
    carried = {
        table: found[1]
        for table, frame in (("fixations", fixations), ("words", words))
        if (found := _cn.frame_names(frame)) is not None
    }
    names = _call_names(column_names, **carried)
    word_side = _table_names(column_names, "words", carried.get("words"))
    figure_overrides = _canonical_options(figure_overrides, names, words=word_side)
    words, fixations, words_b, fixations_b = (
        _cn.to_canonical_frame(frame)
        for frame in (words, fixations, words_b, fixations_b)
    )
    words_b = words if words_b is None else words_b
    fixations_b = fixations if fixations_b is None else fixations_b
    if raw_gaze is not None:
        raw_gaze = _require_normalized(raw_gaze, "raw_gaze")
    if raw_gaze_b is not None:
        raw_gaze_b = _require_normalized(raw_gaze_b, "raw_gaze_b")
    if raw_gaze_b is None and not cross_dataset:
        raw_gaze_b = raw_gaze

    # Ids written before composite ids escaped a `_` inside a part still name
    # their reading when that is unambiguous (`data.respell_reading`).
    pid_a, tid_a = _data.respell_reading(*trial_a, _data.trial_keys(fixations))
    pid_b, tid_b = _data.respell_reading(*trial_b, _data.trial_keys(fixations_b))
    # One screen per side, each resolved in its own frames — the same contract
    # as `plot_scanpath`'s `screen`. Extracting whole parent trials pooled every
    # page of a multipart reading into one scanpath, saccades across pages and all.
    trial_words_a, trial_fix_a, pid_a, tid_a, _screen_a = _select_part(
        words, fixations, str(pid_a), str(tid_a), screen
    )
    trial_words_b, trial_fix_b, pid_b, tid_b, _screen_b = _select_part(
        words_b,
        fixations_b,
        str(pid_b),
        str(tid_b),
        screen_b,
        screen_param="screen_b",
    )
    trial_raw_a = _compare_raw_gaze(raw_gaze, pid_a, tid_a, trial_fix_a)
    trial_raw_b = _compare_raw_gaze(raw_gaze_b, pid_b, tid_b, trial_fix_b)
    for frame, (pid, tid) in ((trial_fix_a, trial_a), (trial_fix_b, trial_b)):
        if frame.empty:
            raise ValueError(
                f"No fixations for participant={pid!r}, trial={tid!r}. "
                f"list_trials() shows what the frames contain."
            )
    # Either reading may carry the column (two corpora need not share them), so
    # it is looked for across both.
    _check_column_options(
        figure_overrides,
        words=pd.concat([trial_words_a, trial_words_b], ignore_index=True),
        fixations=pd.concat([trial_fix_a, trial_fix_b], ignore_index=True),
    )

    setup_a = _compare_setup(
        setup, canvas_size, trial_words_a, trial_fix_a, side="setup"
    )
    resolved_setup_b = _compare_setup(
        setup_b, None, trial_words_b, trial_fix_b, side="setup_b"
    )
    gate = cross_dataset
    if not cross_dataset:
        same_b = _same_dataset_setup_b(
            setup_a,
            setup_b,
            a_known=setup is not None or canvas_size is not None,
            words_a=trial_words_a,
            fixations_a=trial_fix_a,
            words_b=trial_words_b,
            fixations_b=trial_fix_b,
        )
        gate = same_b is not None
        if same_b is not None:
            resolved_setup_b = same_b
        elif setup_b is None:
            # Not refused: B's split panel is drawn to its own screen's canvas,
            # else A's known one, else (neither known) its own data's extent.
            own_b = screen_canvas_size(trial_words_b) or screen_canvas_size(trial_fix_b)
            if own_b is None and (
                setup is not None
                or canvas_size is not None
                or screen_canvas_size(trial_words_a) is not None
                or screen_canvas_size(trial_fix_a) is not None
            ):
                resolved_setup_b = setup_a
            elif own_b is not None:
                resolved_setup_b = replace(
                    setup_a, canvas_width=int(own_b[0]), canvas_height=int(own_b[1])
                )
    if resolved_layout == "overlay" and gate:
        comparable, note = setups_comparable(setup_a, resolved_setup_b)
        if not comparable:
            # BUG-85: the reason says why; this says what happened here and how
            # to ask for the split in Python. `render` rewords it in its flags.
            hint = (
                _inferred_screen_hint(
                    a_inferred=setup is None and canvas_size is None,
                    b_inferred=setup_b is None,
                )
                if cross_dataset
                else ""
            )
            raise IncomparableScreensError(
                f"{note} So no overlay was drawn; pass layout='side_by_side' (or "
                f"'stacked') to compare them in separate panels, each drawn to "
                f"its own screen.{hint}",
                reason=note,
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
        trial_raw_b = qualify_for_compare(trial_raw_b, dataset_b)
        figure_pid_b = (
            str(trial_fix_b["participant_id"].iloc[0])
            if not trial_fix_b.empty
            else pid_b
        )
    trial_fix_a = _apply_fix_index_range(trial_fix_a, fix_index_range, pid_a, tid_a)
    trial_fix_b = _apply_fix_index_range(
        trial_fix_b,
        fix_index_range if fix_index_range_b is None else fix_index_range_b,
        pid_b,
        tid_b,
    )
    if drift_correction:
        # PRE-21: same contract as plot_scanpath — raise, don't silently skip.
        if not drift_correction_enabled():
            raise ValueError(
                "drift_correction is not available in this release. Set "
                f"{EXPERIMENTAL_ENV_VAR}=1 to enable it, or pass "
                "drift_correction=None."
            )
        from .alignment import correct

        trial_fix_a, _ = correct(trial_fix_a, trial_words_a, drift_correction)
        trial_fix_b, _ = correct(trial_fix_b, trial_words_b, drift_correction)

    if not cross_dataset and (pid_a, tid_a) == (pid_b, tid_b):
        # CMP-22: a trial compared with itself — rename B's copy apart, or the
        # figure's (participant, trial) slice hands each side both copies.
        # The renamed id is for slicing only, so B's default legend name is
        # resolved here from the real one.
        if not labels:
            labels = tuple(
                _resolve_trial_display_name(pid_a, tid_a, trial_words_a, None, idx)
                for idx in (0, 1)
            )
        trial_words_b = separate_self_compare(trial_words_b, pid_b)
        trial_fix_b = separate_self_compare(trial_fix_b, pid_b)
        trial_raw_b = separate_self_compare(trial_raw_b, pid_b)
        figure_pid_b = self_compare_participant(pid_b)
    merged_words, merged_words_b, _ = align_compare_columns(
        trial_words_a, trial_words_b
    )
    merged_fix, merged_fix_b, _ = align_compare_columns(trial_fix_a, trial_fix_b)
    merged_raw = None
    if not (trial_raw_a.empty and trial_raw_b.empty):
        merged_raw = pd.concat(align_compare_columns(trial_raw_a, trial_raw_b)[:2])
    settings = _figure_kwargs(figure_overrides)
    settings.pop("illustration_reasons", None)
    if raw_gaze is not None or raw_gaze_b is not None:
        settings.setdefault("show_raw_gaze", True)
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
        column_labels=_column_labels(
            names, trial_words_a, trial_fix_a, words=word_side
        ),
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
        raw_gaze=merged_raw,
    )
    annotate_figure(fig, title=title, caption=caption)
    return fig


def _compare_raw_gaze(
    raw_gaze: pd.DataFrame | None, pid: str, tid: str, trial_fix: pd.DataFrame
) -> pd.DataFrame:
    """One comparison reading's samples — its trial's, and its screen's when the
    reading is one screen of a multipart trial."""
    if raw_gaze is None or raw_gaze.empty:
        return pd.DataFrame()
    samples = _data.filter_raw_gaze(raw_gaze, [pid], [tid])
    if SCREEN_ID in samples.columns and SCREEN_ID in trial_fix.columns:
        screens = trial_fix[SCREEN_ID].dropna().unique()
        if len(screens) == 1:
            samples = extract_part(samples, pid, tid, screens[0])
    return samples


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
        # BUG-93: an animation replays on the wall-clock player, which also
        # autoplays it at the configured speed when asked (VIZ-10). Plotly's own
        # `auto_play` stays off — it ignores the frame duration. PERF-17: the
        # frames are written packed and rebuilt by the page's own script, so a
        # long replay writes a fraction of the bytes. Static figures write
        # unchanged.
        page = replay_page(fig)
        if page is not None:
            figure_dict, script = page
            pio.write_html(
                figure_dict,
                str(path),
                validate=False,
                auto_play=False,
                post_script=script,
                config={**PLOTLY_CONFIG},
            )
        elif fig.frames:
            fig.write_html(str(path), auto_play=False, config={**PLOTLY_CONFIG})
        else:
            fig.write_html(str(path), config={**PLOTLY_CONFIG})
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
    """Split a scanpath figure into its layers and save one file per layer.

    Writes ``<directory>/<layer>.<fmt>`` for each *visible* layer (word boxes /
    fixations / saccades / heatmap / labels / stimulus image / frame) and returns
    ``{layer: Path}``. Each layer is the full figure with only that layer's elements
    and a transparent background, at the same size and axis ranges — so the files
    register perfectly when stacked in Illustrator / Inkscape. ``fmt`` is any
    [`save_figure`][scanpath_studio.api.save_figure] extension without the dot
    (``svg`` / ``pdf`` are vector and best for editing; ``png`` / ``html`` also
    work). ``scale`` / ``width`` / ``height`` are forwarded to
    [`save_figure`][scanpath_studio.api.save_figure]."""
    directory = Path(directory)
    # ENG-54: a failed render (most often Kaleido with no Chrome) used to leave
    # an empty `<output>_layers/` behind, which reads as "exported, but lost".
    # Whatever this call created is removed again if nothing was written to it.
    created = [path for path in (directory, *directory.parents) if not path.exists()]
    directory.mkdir(parents=True, exist_ok=True)
    written: dict = {}
    try:
        for layer, layer_fig in split_scanpath_layers(fig).items():
            path = directory / f"{layer}.{fmt.lstrip('.')}"
            written[layer] = save_figure(
                layer_fig, path, scale=scale, width=width, height=height
            )
    except Exception:
        for path in created:  # deepest first
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        raise
    return written


def figure_code(
    *,
    kind: str = "static",
    source: str = "demo",
    source_options: dict | None = None,
    participant: str = "",
    trial: str = "",
    screen: str | None = None,
    compare: tuple[str, str] | None = None,
    compare_screen: str | None = None,
    compare_layout: str = "overlay",
    compare_stimulus: str = "both",
    compare_dataset: str = "",
    compare_canvas: tuple[int, int] | None = None,
    compare_labels: tuple[str, str] | None = None,
    canvas_size: tuple[int, int] | None = None,
    base_font_size: int = 16,
    font_family: str = FONT_FAMILY,
    title: str = "",
    caption: str = "",
    fix_index_range: tuple[int, int] | None = None,
    illustration_label: str = "auto",
    drift_correction: str | None = None,
    drift_connectors: bool = False,
    playback_speed: float = 1.0,
    autoplay: bool = True,
    flavor: str = "python",
    explicit: bool = False,
    output: str | None = None,
    **figure_overrides,
) -> str:
    """The API or CLI code that reproduces a figure.

    The headless twin of the app's 🔗 Share → *Reproduce this figure in code* block: give
    it the same arguments you would give
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath] (``kind="static"``),
    [`animate_scanpath`][scanpath_studio.api.animate_scanpath] (``"animation"``) or
    [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] (``"comparison"``) and
    it returns the snippet that rebuilds that figure, rather than the figure::

        print(sps.figure_code(participant="l7_1090", trial="l7_1090_2_1_1_Ele_r0",
                              show_heatmap=False, flavor="cli"))

    ``source`` names how the data is loaded — ``"demo"``, ``"synthetic"``, ``"files"``,
    ``"potec"``, ``"onestop"``, ``"multipleye"``, ``"benchmark"``, ``"author"``, or
    ``"unknown"`` for data a snippet can't name — with ``source_options`` carrying that
    loader's arguments (``{"root": …}``, ``{"words": [...], "fixations": [...]}``, and
    so on). With ``show_raw_gaze=True`` the raw-gaze table is read too: the demo's own,
    or the path(s) given as ``source_options["raw_gaze"]`` (plus an optional
    ``"raw_gaze_schema"``) — [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze] in the
    Python form, ``--raw-gaze`` in the CLI one. ``source="raw_gaze"`` is a dataset
    recorded as raw gaze alone: the samples at ``source_options["raw_gaze"]`` are the
    data, and ``plot_scanpath`` is handed ``None`` for the words and fixations.

    ``screen`` / ``compare_screen`` are A's and B's screens of a multipart trial
    (``screen=`` / ``screen_b=``, ``--screen`` / ``--compare-screen``).

    ``compare_dataset`` names the corpus scanpath B was loaded from when it is a
    *second* one. B's participant id belongs to that corpus rather than
    the one the snippet loads, so both forms then load B's own tables and name
    B in them — ``words_b=`` / ``fixations_b=`` / ``dataset_b=``, and
    ``--compare-words`` / ``--compare-fixations`` beside ``--compare-with`` —
    from the placeholder paths ``B_WORDS`` / ``B_FIXATIONS``, which you point
    at its files. ``compare_canvas`` is B's screen, ``(width, height)``, when
    you know it: written as ``setup_b=`` and ``--compare-canvas``, which a
    co-animation across datasets needs.

    ``compare_labels`` is the pair you would pass
    [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] as ``labels=`` — the
    two trace labels, when they are not the composed defaults. Both forms
    carry them: ``labels=`` in the Python snippet, ``--label-a`` / ``--label-b`` in the
    CLI one.

    With ``participant`` / ``trial`` left empty the snippet renders the first
    available trial, as ``render`` does. ``canvas_size`` defaults to the screen
    ``render`` assumes for the source (the demo's 2560×1440, PoTeC's 1680×1050,
    …), so both flavours draw the same figure; ``output`` defaults to
    ``scanpath.html`` for an animation — ``render --animate`` writes only HTML —
    and to a PNG otherwise.

    Only the options that differ from
    [`figure_options`][scanpath_studio.api.figure_options] are written, so the snippet
    stays readable; ``explicit=True`` emits every option at its current value.
    ``flavor`` is ``"python"``, ``"cli"``, or ``"both"`` (the two separated by a blank
    line). Anything neither form can reproduce — a raw-gaze table with no path to
    name, an uploaded stimulus image, B's rows from a second corpus — follows as
    ``# Note:`` comments, matching the ⚠️ captions the app shows and the ``Note:`` lines
    `render --print-code` writes to stderr. See `code_snippet.ReproductionCode` for the
    structured form.
    """
    from . import code_snippet as _snippet

    if flavor not in ("python", "cli", "both"):
        raise ValueError(f"flavor must be 'python', 'cli' or 'both', got {flavor!r}.")
    _reject_unknown_options(
        figure_overrides,
        set(figure_options(kind)) | {"palette"},
        "figure_code",
    )
    if canvas_size is None:
        # EXP-14: `render` snaps these sources to their recorded screen while
        # `plot_scanpath` estimates one from the data, so leaving the canvas
        # unnamed made the two flavours of one recipe disagree.
        canvas_size = _snippet.source_canvas(source)
    state = _snippet.FigureState(
        kind=kind,
        settings={**figure_options(kind), **_expand_palette(figure_overrides)},
        participant=participant,
        trial=trial,
        screen=screen,
        canvas=canvas_size,
        base_font_size=base_font_size,
        font_family=font_family,
        title=title,
        caption=caption,
        fix_index_range=fix_index_range,
        illustration_label=illustration_label,
        drift_correction=drift_correction,
        drift_connectors=drift_connectors,
        playback_speed=playback_speed,
        autoplay=autoplay,
        compare=(
            _snippet.CompareTarget(
                participant=str(compare[0]),
                trial=str(compare[1]),
                screen=None if compare_screen is None else str(compare_screen),
                layout=compare_layout,
                compare_stimulus=compare_stimulus,
                dataset=str(compare_dataset),
                canvas=(
                    (int(compare_canvas[0]), int(compare_canvas[1]))
                    if compare_canvas and compare_dataset
                    else None
                ),
                labels=(
                    (str(compare_labels[0]), str(compare_labels[1]))
                    if compare_labels
                    else None
                ),
            )
            if compare is not None
            else None
        ),
    )
    code = _snippet.reproduction_code(
        _snippet.SnippetSource(
            kind=source, label=source, options=dict(source_options or {})
        ),
        state,
        explicit=explicit,
        output=output or _snippet.DEFAULT_OUTPUT.get(kind, "scanpath.png"),
    )
    cli = code.cli
    if code.cli_unsupported:
        cli += "\n# No `render` flag for: " + ", ".join(code.cli_unsupported)
    # The caveats apply to *both* snippets, so on "both" they are appended once
    # at the end rather than to each half — two identical blocks would read as
    # two different warnings.
    notes = "".join(f"\n# Note: {note}" for note in code.caveats)
    if flavor == "python":
        return code.python + notes
    if flavor == "cli":
        return cli + notes
    return f"{code.python}\n\n{cli}{notes}"


def cache_status() -> dict:
    """Describe the on-device recovery cache a local app run keeps.

    The app stores completed uploaded datasets, column mappings, view settings and
    annotations under the user's cache directory so a refresh or restart resumes
    where it left off — on localhost/desktop only, never on a hosted deployment. This
    reports that store without launching the app: ``enabled``, ``directory``,
    ``datasets`` (name + per-frame row counts), ``rows``, ``annotations``,
    ``settings``, ``bytes``, ``saved_at``, plus ``exists`` / ``readable`` for a
    missing or unreadable manifest, ``damaged`` (name + reason) for a stored
    dataset whose entry or files are broken — the app restores the others and
    keeps that one in the cache rather than dropping it — and
    ``damaged_metadata``, the reason the stored metadata tables would not
    restore (``""`` when they would). Delete it with
    [`clear_cache`][scanpath_studio.api.clear_cache]; the same information is in the
    app's 🗂️ Data Management → *Saved on this computer* section and in
    ``scanpath-studio cache``."""
    from .persistence import cache_status as _cache_status

    return _cache_status(url="http://localhost")


def clear_cache() -> dict:
    """Delete the on-device recovery cache and return its status afterwards.

    Removes only the files this app wrote (``manifest.json`` and the dataset
    Parquet files); anything else in the folder is left alone. A *running* local
    app writes its session back out at the end of its next change — start it
    with ``scanpath-studio run --no-persist`` or ``SCANPATH_STUDIO_PERSIST=0`` to
    stop that."""
    from .persistence import clear_local_state

    clear_local_state()
    return cache_status()
