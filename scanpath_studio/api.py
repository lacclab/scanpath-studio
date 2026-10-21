"""Headless programmatic API for scanpath-studio.

The Streamlit app and this module share one pipeline (``data`` → ``measures``
→ ``plots``), so a figure produced here goes through the exact same builders as
the app and is pixel-identical *given the same settings*. The headless defaults
(``CANONICAL_FIGURE_DEFAULTS``) are the app's default *Scanpath* design —
fixations, saccades and the text — so a bare call draws the figure the app
opens on.
Typical use::

    import scanpath_studio as sps

    words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
    print(sps.list_trials(words, fixations))
    fig = sps.plot_scanpath(words, fixations, participant="p1", trial="t1")
    sps.save_figure(fig, "scanpath.html")   # or .png/.svg/.pdf (needs Chrome)

Every keyword accepted by :func:`plots.make_scanpath_figure` /
:func:`plots.make_scanpath_animation` can be overridden through
``plot_scanpath`` / ``animate_scanpath`` (e.g. ``show_heatmap=True``);
:func:`figure_options` lists them with their effective defaults. ``docs/agents.md``
is the task-oriented guide to this module for scripted / agent use.
"""

from __future__ import annotations

import difflib
import logging
from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
from . import export as _export  # noqa: E402
from .build_info import BuildInfo  # noqa: E402
from .column_names import ColumnNames  # noqa: E402
from .constants import (  # noqa: E402
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_ORDER_FONT_COLOR,
    DEFAULT_STIMULUS_IMAGE_PATTERN,
    EXPERIMENTAL_ENV_VAR,
    FONT_FAMILY,
    PLOTLY_CONFIG,
    SACCADE_CLASS_ORDER,
    UNIFORM_COLOR_FIELD,
    computed_measures_enabled,
    drift_correction_enabled,
    palette_settings,
)
from .experimental_setup import Provenance, SetupSnapshot  # noqa: E402
from .export import annotate_figure, figure_text_style  # noqa: E402
from .file_citation import stamp_file  # noqa: E402
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
    FIGURE_OPTION_CHOICES,
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
    normalize_option_value,
    normalize_option_values,
    normalize_palette,
    replay_page,
    split_scanpath_layers,
)
from .updates import UpdateCheck  # noqa: E402

if TYPE_CHECKING:
    from .metadata import ParticipantMetadata, TextMetadata, TrialMetadata


def build_authored_scanpath(
    text: str, events: pd.DataFrame | None = None, **layout_options: Any
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build normalized Words and Fixations frames from a hand-drawn scanpath.

    Args:
        text: The text to lay out as word boxes. Explicit line breaks are kept.
        events: The fixations, one row each, with the columns the app's *Draw a
            scanpath* table has (``fixation_id``, ``order_in_trial``, ``word_id``,
            ``x``, ``y``, ``duration_ms``). Left out, each word gets one fixation at its
            center.
        **layout_options: Passed to `authoring.layout_text` (``canvas_width``,
            ``margin``, ``character_width``, ``word_height``, ``line_height``).

    Returns:
        The ``(words, fixations)`` frames, ready to plot.
    """
    from .authoring import authored_fixations, default_events, layout_text

    words = layout_text(text, **layout_options)
    if events is None:
        events = default_events(words)
    return words, authored_fixations(words, events)


def load_authored_scanpath(
    source: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a draft file as normalized Words and Fixations frames.

    Args:
        source: The JSON the app's **Download draft (JSON)** saves on *Draw a
            scanpath*: its path, or its text.

    Returns:
        The ``(words, fixations)`` frames, ready to plot.
    """
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

# The headless rendering is the app's default *Scanpath* design:
# fixations, saccades and the text, with word boxes, the heatmap and fixation
# numbers off (controls._VIZ_WIDGET_DEFAULTS), so a bare `plot_scanpath` /
# `render` draws the figure the app opens on. Turn a layer on with its keyword
# (`show_heatmap=True`). `heatmap_metric="counts"` is translated to the
# figure-level `None` in _figure_kwargs, like tabs._build_figure_settings.
#
# Every option tracks the app's own default (controls._VIZ_WIDGET_DEFAULTS →
# controls._collect_viz_settings → tabs._build_figure_settings), so the same
# call renders the same picture headless as on screen. `figure_options()`
# prints the merged result.
_FIGURE_CONTEXT_FIELDS = frozenset(
    {"canvas_width", "canvas_height", "base_font_size", "font_family"}
)
_STATIC_FIGURE_PARAMS = frozenset(STATIC_FIGURE_OPTIONS) - _FIGURE_CONTEXT_FIELDS
#: `layout`, `compare_stimulus`, `trial_labels` and `canvas_b` are named
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
    "legend_layout",
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
    "saccade_opacity",
    "saccade_color_mode",
    "saccade_class_colors",
    "saccade_type_legend",
    "show_color_legend",
    "show_highlight_legend",
    "saccade_classes",
    "saccade_render_mode",
    "fixation_snap_to_line",
    "fixation_snap_position",
    "fixation_color",
    "fixation_symbol",
    "fixation_opacity",
    "background_color",
    "color_by_line",
    "fit_to_monitor",
    "crop_margin",
    "show_coordinate_grid",
    "coordinate_grid_spacing",
    "line_spacing",
    "scale_text_to_boxes",
    "background_image",
    "background_image_size",
    "background_image_origin",
    "background_image_opacity",
    "show_stimulus_image",
    "word_hover_fields",
    "fixation_hover_fields",
    # Figure design settings.
    "fixation_colorbar_thickness",
    "fixation_colorbar_length",
    "heatmap_colorbar_thickness",
    "heatmap_colorbar_length",
    "heatmap_opacity",
    "saccade_arrow_size",
    "fixation_outline_width",
    "fixation_outline_color",
    "show_plot_frame",
    "plot_frame_color",
    "coordinate_grid_font_size",
    "title_font_size",
    "caption_font_size",
    "caption_color",
}

CANONICAL_FIGURE_DEFAULTS: dict = FigureSettings.defaults(
    _CANONICAL_OPTION_NAMES
) | dict(
    show_words=False,
    show_order=False,
    show_heatmap=False,
    heatmap_metric="duration_ms",
    order_font_color=DEFAULT_ORDER_FONT_COLOR,
    saccade_classes=list(SACCADE_CLASS_ORDER),
    fixation_opacity=0.7,
    background_color=DEFAULT_BACKGROUND_COLOR,
    fit_to_monitor=True,
    # The A/B legend is on, as in the app.
    show_legend=True,
    word_hover_fields=["text", "word_id", "line_idx", "total_fixation_duration_ms"],
    fixation_hover_fields=["order_in_trial", "duration_ms", "word_id"],
)


def _as_dataframe(
    table: TablesLike, label: str, *, plan_for=None, kind: str | None = None
) -> pd.DataFrame:
    if isinstance(table, pd.DataFrame):
        # A frame this API returned under the dataset's own names goes back to
        # the internal names it was normalized under, so loading it again
        # round-trips (a converted width sits beside a renamed left edge, which
        # no detection would pair up).
        return _cn.to_canonical_frame(table)
    items = _data.expand_table_inputs(table)
    for item in items:
        if not isinstance(item, pd.DataFrame) and not Path(item).is_file():
            raise FileNotFoundError(
                f"{label} table not found: {item} (looked in {Path.cwd()})"
            )
    # A zip holding both EyeLink reports gives each table its own.
    return _data.read_tables(items, plan_for=plan_for, kind=kind)


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
        "title": "Words",
        "noun": "words",
        "param": "word_schema",
        # (schema key, human label, candidate column names) — the fields whose
        # absence makes `validate_word_schema` fail.
        "required": (
            ("trial", "Trial ID", _data.TRIAL_CANDIDATES),
            ("word_id", "Word ID", _data.WORD_ID_CANDIDATES),
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
    bare ``KeyError: '<column>'`` from inside ``normalize_*``."""
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


def _known_schema_keys(kind: str, frame: pd.DataFrame) -> set:
    """Every key a ``kind`` column mapping can set."""
    spec = _SCHEMA_SPECS[kind]
    keys = set(spec["propose"](frame.iloc[:0])) | {"block"}
    keys |= {key for key, _, _ in spec["required"]}
    keys |= {key for group in spec["groups"] for key in group}
    return keys


def _unknown_schema_keys(kind: str, frame: pd.DataFrame, schema: dict) -> list:
    """The keys of ``schema`` that name no field (``x_pos`` for ``x``)."""
    known = _known_schema_keys(kind, frame)
    return [key for key in schema if key not in known]


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
    lines = [f"{spec['title']} column mapping problems: {'; '.join(problems)}"]
    unknown = _unknown_schema_keys(kind, frame, schema) if explicit else []
    if unknown:
        import difflib

        known = sorted(_known_schema_keys(kind, frame))
        for key in unknown:
            close = difflib.get_close_matches(key, known, n=1) or [
                k for k in known if key.startswith(f"{k}_") or key.endswith(f"_{k}")
            ]
            hint = f" — did you mean {close[0]!r}?" if close else ""
            lines.append(f"{param} has a key that is not a field: {key!r}{hint}")
        lines.append(f"Fields: {', '.join(known)}")

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
            else f"Could not find these columns in the {spec['noun']} table:"
        )
        lines.extend(bullets)
    resolved = ", ".join(
        f"{key}={value!r}"
        for key, value in schema.items()
        if value is not None and key not in unknown
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
    """Find the column mapping auto-detection would use for a raw table.

    It is the mapping [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]
    infers, so it is the place to start when detection got a field wrong or could not
    find one: edit the dict and pass it back as ``word_schema=`` or ``fix_schema=``.

    Args:
        table: A raw, not yet normalized table: a DataFrame, a path, a glob or a list of
            paths, as the loader takes.
        kind: ``"words"``, ``"fixations"`` or ``"raw_gaze"``.

    Returns:
        ``{canonical field: source column}``, with ``None`` for a field it could not
            find.

    Examples:
        ```python
        schema = sps.propose_schema("ia.csv", "words")
        schema["trial"] = "TRIAL_LABEL"
        words, fixations = sps.load_scanpath_data(
            "ia.csv", "fix.csv", word_schema=schema
        )
        ```
    """
    if kind not in _SCHEMA_SPECS:
        raise ValueError(
            f"Unknown kind {kind!r}; choose one of {', '.join(_SCHEMA_SPECS)}."
        )
    frame = _as_dataframe(
        table,
        _SCHEMA_SPECS[kind]["noun"],
        kind=kind if kind in ("words", "fixations") else None,
    )
    return _SCHEMA_SPECS[kind]["propose"](frame)


_NORMALIZED_ID_COLUMNS = ("participant_id", "trial_id")


#: The column vocabularies a loader can return frames in.
NAMES_SOURCE = "source"
NAMES_CANONICAL = "canonical"


class ScanpathData(tuple):
    """The ``(words, fixations)`` frames ``load_scanpath_data`` returns, with their names.

    It is a tuple, so ``words, fixations = load_scanpath_data(…)`` unpacks it, and
    ``.words`` / ``.fixations`` name the two frames. ``column_names`` holds the
    dataset's own name for every canonical column, per table: ``{"words": ColumnNames,
    "fixations": ColumnNames}``.

    With ``names="source"`` (the default) the frames' columns are the dataset's own
    names and each frame carries its map, so any API function takes it, sliced, filtered
    or merged, and the names it writes are yours. With ``names="canonical"`` they are
    the internal names, the same for every dataset.
    """

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
    """``(canonical frame, its map)`` for a frame handed to the API.

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
    # A frame under the dataset's own names is processed canonically.
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
    image_pattern: str = DEFAULT_STIMULUS_IMAGE_PATTERN,
    keep_columns: Iterable[str] | None = None,
    names: str = NAMES_SOURCE,
) -> ScanpathData:
    """Load and normalize a Words table, a Fixations table, or both.

    Columns keep the names your files give them: ``CURRENT_FIX_DURATION``, not
    ``duration_ms``. A column Scanpath Studio built, converted, computed or changed
    keeps its internal name, and ``data.column_names`` records what every column was
    called. Every API function takes these frames, and every column option
    (``color_by=``, the hover fields …) takes either name.

    Columns are auto-detected from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and
    snake_case names. Normalization keeps the mapped fields and the recognized optional
    ones (eye, EyeLink's interest-area measures, linguistic features …) and drops the
    rest, unless ``keep_columns`` names them.

    - **One table is enough.** Leave out the table a dataset doesn't have: it comes back
      as an empty frame, and the plots skip that layer.
    - **Stimulus-level words.** A Words table without a participant column holds each
      text's word boxes once, and they are copied onto every trial in the fixations.
      Each trial is matched by its trial ID, else the trial ID it had before a repeat's
      ``_r2`` suffix, else its ``text_id`` (for trial IDs that embed the participant).
      Trials that match none raise a ``data.StimulusJoinWarning`` (a ``UserWarning``).
    - **Fixations without x/y** but with a word ID are placed at the centers of their
      word boxes.
    - **Bookkeeping columns.** Columns named in ``data.INTERNAL_COLUMNS`` are the
      pipeline's own; ``data.drop_internal_columns`` removes them.

    Args:
        words: The Words table, one word box per row: a DataFrame; a ``.csv``, ``.tsv``, ``.txt``,
            ``.tab``, ``.parquet``, ``.feather``, ``.xlsx`` or ``.xls`` file, or a
            ``.zip`` of them; a glob pattern; or a list of paths. Several files (one per
            participant and/or text) are concatenated, with each file's stem in a
            ``source_file`` column.
        fixations: The Fixations table, in any form ``words`` takes.
        word_schema: A mapping from field to column name for the Words table, replacing
            auto-detection. Start from
            [`propose_schema`][scanpath_studio.api.propose_schema].
        fix_schema: The same for the Fixations table.
        trial_parts_manifest: A nested parent-trial/parts definition, for datasets whose
            tables identify screens through arbitrary selector columns. Explicit
            ``screen_id`` / ``screen_index`` columns can instead be mapped in each
            schema.
        image_root: A local folder of stimulus images, one page per trial (or screen).
            Each row the pattern finds a file for gets it as its ``image_path``; a row
            without one keeps the ``image_path`` it had. ``show_stimulus_image=True``
            then draws the page under the figure.
            [`attach_stimulus_images`][scanpath_studio.api.attach_stimulus_images] does
            the same for frames already loaded.
        image_pattern: The file to look for under ``image_root``, with
            ``{placeholders}`` naming the rows' canonical columns: ``"{text_id}.png"``,
            ``"{participant_id}/{trial_id}.png"``.
        keep_columns: Further columns of your own to carry through under their own
            names, such as a pupil size or a detection confidence, from whichever table
            has them, so a figure can color, hover or plot by them. The app's *Extra
            fields to keep*; ``render --keep-columns``.
        names: ``"source"`` keeps the dataset's column names; ``"canonical"`` returns
            the internal names, the same for every dataset, for code that works across
            datasets.

    Returns:
        The normalized ``(words, fixations)`` frames, as a
            [`ScanpathData`][scanpath_studio.api.ScanpathData].

    Raises:
        ValueError: A required field can't be found. The message names the field, the
            column names auto-detection looked for, and the columns the table has.
        ValueError: ``image_root`` does not exist, or ``image_pattern`` is absolute or
            climbs out of it.
        data.StimulusJoinError: A stimulus-level Words table shares neither a trial ID
            nor a ``text_id`` with any trial (or, multipart, with every screen a trial
            has fixations on). A ``ValueError``.
        data.UnplacedFixationsError: The fixations map no x/y and their word ID column
            holds no numbers, so none could be placed. A ``ValueError``.
    """
    _check_names_choice(names)
    if words is None and fixations is None:
        raise ValueError("Provide at least one of words= or fixations=.")
    if image_root is not None:
        _require_image_folder(image_root)
    # A frame this API already named is loaded under its internal names; its
    # own map then renames the new one back to the user's.
    prior = {
        table: found[1]
        for table, frame in (("words", words), ("fixations", fixations))
        if (found := _cn.frame_names(frame)) is not None
    }

    if words is not None:
        # A word spelled "None" or "NA" is a word, not a missing cell.
        words_df = _as_dataframe(
            words,
            "words",
            plan_for=lambda header: _data.verbatim_text_plan(header, word_schema),
            kind="words",
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
            kind="fixations",
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
    # What each column was called in these files — from the schemas
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


def _require_image_folder(image_root: str | Path) -> None:
    """Refuse a folder that is not there: a mistyped one would match nothing and
    draw no page, without a word."""
    folder = Path(image_root).expanduser()
    if not folder.is_dir():
        raise ValueError(
            f"image_root={str(image_root)!r} is not a folder"
            + (" (it is a file)." if folder.exists() else " (it does not exist).")
            + " Point it at the folder that holds the stimulus images."
        )


def attach_stimulus_images(
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    image_root: str | Path,
    image_pattern: str = DEFAULT_STIMULUS_IMAGE_PATTERN,
) -> ScanpathData:
    """Fill ``image_path`` from a folder of stimulus images, on frames already loaded.

    It is [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]'s
    ``image_root`` / ``image_pattern``, for frames that came from somewhere else, such
    as a corpus loader, which takes no folder. The rules are the same: the placeholders
    name the rows' canonical columns, and a row the pattern finds no file for keeps the
    ``image_path`` it had.

    Args:
        words: The words frame, or ``None``.
        fixations: The fixations frame, or ``None``.
        image_root: The folder of stimulus images.
        image_pattern: The file to look for under ``image_root``, as in
            ``load_scanpath_data``.

    Returns:
        New ``(words, fixations)`` frames, under the names they came in. The frames
            passed in are not modified.

    Raises:
        ValueError: ``image_root`` does not exist, or ``image_pattern`` is absolute or
            climbs out of it.

    Examples:
        ```python
        words, fixations = sps.attach_stimulus_images(
            *sps.load_potec("data/PoTeC", readers=[0], texts=["b0"]),
            "pages/",
            "{text_id}.png",
        )
        sps.plot_scanpath(words, fixations, show_stimulus_image=True)
        ```
    """
    _require_image_folder(image_root)
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    words = _data.resolve_stimulus_image_paths(words, image_root, image_pattern)
    fixations = _data.resolve_stimulus_image_paths(fixations, image_root, image_pattern)
    return ScanpathData(
        _named_out(words, "words", word_names),
        _named_out(fixations, "fixations", fix_names),
        {
            table: names
            for table, names in (("words", word_names), ("fixations", fix_names))
            if names is not None
        },
    )


def _with_optional_fields(
    keep_columns: Iterable[str] | None, registry: list
) -> set | None:
    """``keep_columns`` as the normalizers take it: ``None`` (every recognized
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
) -> ParticipantMetadata:
    """Load a participant-level metadata table: one row per participant.

    Nothing is broadcast onto the words or fixations frames. Use
    `scanpath_studio.metadata.project` to attach chosen columns to a per-trial frame, or
    ``.values_for(pid)`` for one participant.

    Args:
        table: A DataFrame, or a path or glob to a CSV, TSV, Parquet or Excel file, or a
            list of them, stacked into one table. It holds an ID column plus anything
            known about each participant (``native_language``, ``age``, a comprehension
            score).
        id_column: The participant ID column. Defaults to the first recognized spelling
            (``participant_id``, ``subject``, ``RECORDING_SESSION_LABEL``, …).
        participants: A normalized frame or a list of IDs to validate the join against.
            The result's ``.report`` then names the participants missing from either
            side.

    Returns:
        A `ParticipantMetadata`: the cleaned frame, a field registry (name, label,
            grain, dtype, missingness) and the join report.

    Examples:
        ```python
        words, fixations = sps.load_sample_data()
        meta = sps.load_participant_metadata("participants.csv", participants=fixations)
        meta.names  # ('native_language', 'age')
        ```
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
) -> TrialMetadata:
    """Load a trial-level metadata table: one row per trial.

    The sibling of
    [`load_participant_metadata`][scanpath_studio.api.load_participant_metadata], one
    grain down. Nothing is broadcast onto the words or fixations frames.

    **The key is yours to state, and it changes what the table means.** Keyed by trial
    ID alone, a row describes a *text*, and every trial of it inherits that row. Keyed
    by participant **and** trial (``participant_column``), a row describes one *trial*.
    Nothing in a file says which a corpus is, so this is never inferred.

    Args:
        table: A DataFrame or file(s), as `load_participant_metadata` takes, stacked
            into one table. It holds a trial ID column plus anything known about each
            trial (a list name, a condition, a per-trial comprehension score).
        id_column: The trial ID column. Defaults to the first recognized spelling
            (``trial_id``, ``item_id``, ``TRIAL_INDEX``, …).
        participant_column: The participant ID column, to key each row by participant
            and trial. Left out, rows are keyed by trial ID alone.
        trials: A normalized fixations or words frame, or any frame with
            ``participant_id`` and ``trial_id``, to validate the join against. The
            result's ``.report`` then names the trials missing from either side.

    Returns:
        A `TrialMetadata`: the cleaned frame, a field registry and the join report.

    Examples:
        ```python
        words, fixations = sps.load_sample_data()
        meta = sps.load_trial_metadata("readings.csv", trials=fixations)
        meta.names  # ('list_name', 'comprehension_score')
        ```
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
) -> TextMetadata:
    """Load a text-level metadata table: one row per text.

    A text is a stimulus, not something one participant owns, so the table is never
    keyed by participant. Nothing is broadcast onto the words or fixations frames.

    Args:
        table: A DataFrame or file(s), as `load_participant_metadata` takes, stacked
            into one table. It holds a text ID column plus anything known about each
            text (genre, difficulty, a stimulus-level comprehension score).
        id_column: The text ID column, or several columns that build a composite ID, as
            the Text ID mapping can. Defaults to the first recognized
            spelling (``text_id``, ``paragraph_id``, ``stimulus_id``, …).
        texts: A normalized fixations or words frame, or any iterable of text IDs, to
            validate the join against. The result's ``.report`` then names the texts
            missing from either side.

    Returns:
        A `TextMetadata`: the cleaned frame, a field registry and the join report.

    Examples:
        ```python
        words, fixations = sps.load_sample_data()
        meta = sps.load_text_metadata("texts.csv", texts=words)
        meta.names  # ('genre', 'difficulty')
        ```
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
    """Load the bundled demo, normalized and ready to plot.

    The bundled demo is a subset of OneStop: two participants, twelve trials each, every
    one with fixations. The frames carry the
    demo's recorded screen (OneStop's 2560×1440), so ``plot_scanpath`` draws them on it
    without a ``canvas_size``, as ``scanpath-studio render --sample`` does.

    Args:
        names: ``"source"`` for the demo's own column names, ``"canonical"`` for the
            internal ones (see
            [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]).

    Returns:
        The ``(words, fixations)`` frames, as a
            [`ScanpathData`][scanpath_studio.api.ScanpathData].
    """
    from .code_snippet import SOURCE_DEMO, source_canvas

    data = load_scanpath_data(*_data.load_sample_data(), names=names)
    screen = source_canvas(SOURCE_DEMO)
    for frame in data:
        frame.attrs[RECORDED_SCREEN_ATTR] = screen
    return data


#: The `DataFrame.attrs` key a frame carries its dataset's recorded screen in,
#: ``(width, height)`` px — read when no ``canvas_size`` is passed.
RECORDED_SCREEN_ATTR = "scanpath_studio.recorded_screen"


def _recorded_screen(*frames) -> tuple[int, int] | None:
    """The recorded screen one of ``frames`` carries (`load_sample_data`)."""
    for frame in frames:
        screen = getattr(frame, "attrs", {}).get(RECORDED_SCREEN_ATTR)
        if screen:
            return int(screen[0]), int(screen[1])
    return None


def load_raw_gaze(
    table: TablesLike,
    *,
    raw_gaze_schema: dict | None = None,
    names: str = NAMES_SOURCE,
) -> pd.DataFrame:
    """Load and normalize a raw, sample-level gaze table, for ``raw_gaze=``.

    Raw gaze is the third table [`plot_scanpath`][scanpath_studio.api.plot_scanpath] can
    draw, under the fixations: one row per eye-tracker sample, with a participant, a
    trial, ``x`` / ``y`` and usually a timestamp. ``plot_scanpath`` keeps only the
    plotted trial's (and screen's) samples, so one table can serve a whole corpus.

    Args:
        table: A DataFrame, path, glob or list of paths, as
            [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] takes.
            Columns are auto-detected the same way.
        raw_gaze_schema: A mapping from field to column, replacing auto-detection. Start
            from ``propose_schema(table, "raw_gaze")``.
        names: ``"source"`` keeps the table's column names; ``"canonical"`` returns the
            internal ones.

    Returns:
        The normalized samples.

    Examples:
        ```python
        raw_gaze = sps.load_raw_gaze("gaze_samples.csv")
        fig = sps.plot_scanpath(words, fixations, "p1", "t3", raw_gaze=raw_gaze)
        ```
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
    """Load the bundled demo's raw gaze: what the app overlays on it.

    OneStop ships no sample-level gaze, so this is **synthesized** from one of the
    demo's real trials, and covers that trial alone.

    Args:
        names: ``"source"`` or ``"canonical"``, as
            [`load_sample_data`][scanpath_studio.api.load_sample_data] takes.

    Returns:
        The normalized samples.
    """
    return load_raw_gaze(_data.load_sample_raw_gaze(), names=names)


def check_data_health(
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Find values that loaded as numbers but cannot be right: the app's *Data checks*.

    The checks look for fixations lasting 0 ms or less or with an infinite duration or
    onset, fixations and raw-gaze samples whose position is missing or infinite, word
    boxes with no area or no finite position, and per-screen screen sizes that are not
    finite and positive. Nothing is changed or dropped.

    Each row of the result is one check that found something:

    | Column | What it holds |
    | --- | --- |
    | ``table``, ``check``, ``problem`` | Where it looked, and what it found |
    | ``columns`` | The columns it read, in the names the frames carry |
    | ``rows``, ``of_rows`` | How many rows, of how many |
    | ``trials`` | The trials those rows fall in |
    | ``breakdown`` | The rows by kind |
    | ``severity`` | ``"note"`` for raw-gaze gaps, which blinks and track loss make ordinary |
    | ``what_happens`` | What the app does with those rows |
    | ``examples`` | A few of them |

    Args:
        words: A normalized words frame from
            [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data].
        fixations: A normalized fixations frame.
        raw_gaze: A normalized raw-gaze frame from
            [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze].

    Returns:
        The findings; an empty frame when every check passed.

    Examples:
        ```python
        words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
        print(sps.check_data_health(words, fixations))
        ```
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
        # Name the columns and example fields as the frames did.
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
    """Refuse an experimental computation, naming the switch that enables it.

    These values are computed by Scanpath Studio rather than read from the
    dataset, and none is validated by hand yet. A script gets an error rather
    than an unchecked number.
    """
    if not computed_measures_enabled():
        raise ValueError(
            f"{name} is experimental and off by default: its values are computed "
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
    # In the names the frames carried — the two tables that are the
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
            "alignment_sensitivity is experimental and off by default (vertical "
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
#: ``value_col``. Without the check a table lacking one would surface as a
#: bare ``KeyError: 'value'`` from inside the builder.
_CORPUS_COLUMNS = {
    "profile": ("word_id", "<value>"),
    "distribution": ("<value>",),
    # The builder draws its "no data" placeholder for a table with no `diff` —
    # right for the app's empty states, but headless it would mean a figure
    # with nothing on it and an exit code of 0.
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
    """Plot a corpus profile, distribution or difference figure from a tidy table.

    The headless form of Corpus Analysis's figures, in the same colors.

    Args:
        data: The tidy table. ``kind="profile"`` reads ``word_id`` and ``value_col``
            (and optional ``lo`` / ``hi``), ``"distribution"`` reads ``value_col``, and
            ``"difference"`` reads ``word_id`` and ``diff``.
        kind: ``"profile"``, ``"distribution"`` or ``"difference"``.
        measure_label: The measure's label, and the series' name when the table has no
            ``series_col``.
        series_col: The column naming each overlaid profile or distribution series, when
            the table has it.
        value_col: The column holding the values.
        colors: The series' colors, in order. Left out, the app's palette.
        canvas_width: The figure's width in px.
        base_font_size: The base font size in px.
        font_family: The font family.

    Returns:
        The figure.

    Raises:
        ValueError: The table lacks a column its ``kind`` reads (the message names it
            and the columns present), or ``kind`` is unknown.
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
    """List every plottable trial: one row per participant and trial.

    Every trial **any** table has, whether the words, the fixations or the raw gaze,
    appears once. The app's trial picker, ``render --list-trials`` and the export bundle
    list the same set. A trial a table lacks plots without that layer: one with words
    but no fixations draws its text alone, one with fixations but no words its scanpath
    over no word boxes.

    Args:
        words: The words frame, or ``None`` when the dataset has none.
        fixations: The fixations frame, or ``None``. Pass ``None`` for both for a
            dataset recorded as raw gaze alone.
        raw_gaze: A frame from [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze].

    Returns:
        The participant and trial IDs, sorted by participant, then trial, under the
            names the frames carry.
    """
    words, word_names = _named_in(words, "words", optional=True)
    fixations, fix_names = _named_in(fixations, "fixations", optional=True)
    gaze_names = None
    if raw_gaze is not None:
        raw_gaze, gaze_names = _named_in(raw_gaze, "raw_gaze")
    names = _call_names(fixations=fix_names, words=word_names, raw_gaze=gaze_names)
    cols = ["participant_id", "trial_id"]
    combos = _data.trial_pool(fixations, words, raw_gaze)
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
    """List the ordered screens of multipart data, optionally for one trial.

    A trial recorded as raw gaze alone takes its screens from ``raw_gaze`` (its
    ``screen_id``). That is decided per trial, so a samples-only trial keeps its screens
    in a dataset whose other trials have fixations.

    Args:
        words: The words frame, or ``None``.
        fixations: The fixations frame, or ``None``.
        participant: Narrow to this participant's trials.
        trial: Narrow to this trial.
        raw_gaze: A frame from [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze].

    Returns:
        One row per screen, in order; an empty table for single-screen data.
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
    the first match (the CLI's behavior, mirroring the app's default selection)
    — but never for a trial id that several participants share: the
    app's picker and its links refuse to guess the reader, so the CLI does too.
    ``raw_gaze`` makes the trials only its samples cover selectable.
    """
    combos = _cn.to_canonical_frame(list_trials(words, fixations, raw_gaze=raw_gaze))
    if combos.empty:
        raise ValueError(
            "The data holds no trial with both a participant and a trial id."
        )
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
                f"participant {str(participant)!r} has {len(scoped)} "
                f"trial{'' if len(scoped) == 1 else 's'}, none of them {str(trial)!r}. {_value_hint(scoped, 'trial_id', trial)}"
            )
        scoped = narrowed
    if len(scoped) > 1 and not (default_first and trial is None):
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
            f"{fix} list_trials(words, fixations) lists all "
            f"{len(combos)} trials."
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
            "whose word/AOI ids match the fixations', so each fixation can be "
            "placed at its word box's center."
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
    names the one to fix (``screen_b=`` for a comparison's second trial)."""
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
        # A trial recorded as raw gaze alone takes its screens from the
        # samples, so one screen's coordinate space is drawn at a time — as for
        # words and fixations — rather than every screen stacked into one.
        catalog = part_catalog(_data.filter_raw_gaze(raw_gaze, [pid], [tid]))
    if catalog.empty:
        if screen is not None:
            raise ValueError(
                f"{screen_param}= names a screen, but participant={pid!r}, "
                f"trial={tid!r} has only one; leave {screen_param}= out."
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


def resolve_palette(value: object) -> str:
    """The `constants.PALETTES` name ``value`` stands for: the app's name
    (``"Print / grayscale"``) or its short name (``"print"``), any case.
    Raises ``ValueError`` otherwise."""
    return normalize_palette(value)


def _check_colorscales(overrides: dict) -> None:
    """Name the option when Plotly doesn't know a color scale, rather than let
    Plotly raise its own lower-cased ``PlotlyError`` from inside the builder."""
    from plotly.colors import get_colorscale
    from plotly.exceptions import PlotlyError

    for key in ("heatmap_colorscale", "fixation_colorscale"):
        value = overrides.get(key)
        if not isinstance(value, str):
            continue
        try:
            get_colorscale(value)
        except PlotlyError:
            raise ValueError(
                f"{key}={value!r} is not a Plotly color scale. Any named scale "
                "works, e.g. Viridis, Greens, Blues, Cividis; append _r to "
                "reverse one."
            ) from None


def _expand_palette(overrides: dict) -> dict:
    """Expand a ``palette=`` override into the color kwargs it stands for.

    ``palette`` names a set of color defaults tuned for a medium — screen,
    colorblind viewers, a black & white print, a projector. It's a *preset*, so
    any color the caller also passes explicitly wins over it::

        sps.plot_scanpath(w, f, palette="Print / grayscale")
        sps.plot_scanpath(w, f, palette="Default (colorblind-safe)", saccade_color="#000")

    The palette itself isn't a figure kwarg, so it's consumed here rather than
    forwarded. Raises on an unknown name — a silent fallback to the default
    palette would quietly produce the wrong figure for a print run.

    Every enumerated option is read here too (`plots.normalize_option_values`):
    ``heatmap_norm="log"`` is ``"Log"``, and a value that is none of the
    choices raises rather than drawing the default.
    """
    overrides = normalize_option_values(overrides)
    _check_colorscales(overrides)
    name = overrides.get("palette")
    if name is None:
        return overrides
    name = resolve_palette(name)  # "print", "high-contrast", any case or spelling
    expanded = dict(overrides)
    expanded.pop("palette")
    # `word_label_color` is `text_color` on the figure builders.
    settings = palette_settings(name)
    settings["text_color"] = settings.pop("word_label_color")
    for key, value in settings.items():
        expanded.setdefault(key, value)
    return expanded


_NAMED_FIGURE_PARAMS = frozenset(
    {
        "canvas_size",
        "base_font_size",
        "font_family",
        "title",
        "caption",
        "screen",
        "raw_gaze",
        "illustration",
        "illustration_label",
        "fix_index_range",
        "column_names",
    }
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
        # The builders' named parameters too: `canvas=` means `canvas_size=`.
        close = difflib.get_close_matches(
            key, sorted(set(valid) | _NAMED_FIGURE_PARAMS), n=3, cutoff=0.6
        )
        suffix = (
            f" (did you mean {', '.join(repr(c) for c in close)}?)" if close else ""
        )
        parts.append(f"{key!r}{suffix}")
    raise TypeError(
        f"{func_name}() got an unexpected keyword argument: {', '.join(parts)}. "
        f"help({func_name}) lists its parameters and figure_options() the "
        "figure options with their defaults."
    )


#: Figure options whose value names a column → (the table it is read from, its
#: CLI flag, the values that are not columns, what to do instead). The
#: builders look the column up and draw *nothing* when it is missing, so
#: without this check a misspelling would render a flat-coloured / unmarked
#: figure without a word.
_COLUMN_OPTIONS = {
    "color_by": (
        "fixations",
        "--color-by",
        (UNIFORM_COLOR_FIELD, "line"),
        f"Use {UNIFORM_COLOR_FIELD!r} for one flat color, 'line' to color by "
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


#: The figure options whose value names one column, and those naming a
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
    duration or counts fixations, and any other value — a misspelled column
    name, say — would silently count."""
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

    Only explicit values are checked. An empty table is not checked — there is
    nothing to color."""
    frames = {"words": words, "fixations": fixations}
    for name, (kind, flag, synthetic, advice) in _COLUMN_OPTIONS.items():
        value = overrides.get(name)
        if value is None or value == "" or value in synthetic:
            continue
        frame = frames[kind]
        present = [str(column) for column in frame.columns]
        if frame.empty or str(value) in present:
            continue
        # Internal helper columns (`_text_id_mapped`) are not the user's to name.
        visible = [column for column in present if not column.startswith("_")]
        close = difflib.get_close_matches(str(value), visible, n=3, cutoff=0.6)
        hint = f" Closest: {', '.join(repr(c) for c in close)}." if close else ""
        raise ValueError(
            f"{name}={value!r} ({flag} on the CLI) names no column of the "
            f"{kind} table.{hint} {advice} Columns present ({len(visible)}): "
            f"{_column_preview(frame[visible])}."
        )


def figure_options(kind: str = "static", *, choices: bool = False) -> dict:
    """List every figure keyword a builder takes, with the default it renders with.

    The defaults are what a call actually renders with, the app's Scanpath design, so a
    script can diff its intended settings against what it would get. The *Figure
    options* section of the API reference lists them by section, with their ``render``
    flags.

    Args:
        kind: ``"static"`` for [`plot_scanpath`][scanpath_studio.api.plot_scanpath],
            ``"animation"`` for
            [`animate_scanpath`][scanpath_studio.api.animate_scanpath] (which takes a
            subset), or ``"comparison"`` for
            [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths].
        choices: Map each name to ``{"default": …, "choices": …}`` instead. ``choices``
            is the tuple of values an enumerated option takes (``heatmap_norm``:
            ``("Linear", "Log")``), or ``None`` for a free one. An enumerated option
            takes any spelling of a choice, ignoring case, spaces, ``-`` and ``_``, so
            the CLI's ``"log"`` and ``"mark-border"`` work, and raises ``ValueError``
            listing them for anything else.

    Returns:
        ``{name: default}``, sorted by name.

    Raises:
        ValueError: An unknown ``kind``.

    Examples:
        ```python
        {k: v for k, v in sps.figure_options().items() if k.startswith("show_")}
        ```
    """
    if kind == "static":
        params = _STATIC_FIGURE_PARAMS
        defaults = FigureSettings.defaults(params) | CANONICAL_FIGURE_DEFAULTS
    elif kind == "animation":
        params = _ANIMATION_FIGURE_PARAMS
        defaults = FigureSettings.defaults(params) | _animation_defaults()
    elif kind == "comparison":
        # `compare_scanpaths` validates against this set, and its TypeError
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
    if choices:
        return {
            name: {"default": default, "choices": FIGURE_OPTION_CHOICES.get(name)}
            for name, default in options.items()
        }
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
    run ``alignment.correct``, color the corrected fixations by line, and
    optionally draw original→corrected connectors. Returns the fixations to plot.
    """
    if method is None or str(method).lower() == "off":
        return trial_fixations
    # Raise rather than ignore. A share link degrades silently because a
    # human can see the figure and the rail; a script cannot, so quietly
    # returning uncorrected fixations under a stated `drift_correction=` would
    # be a wrong result with no signal. Name the env var so it is one step to fix.
    if not drift_correction_enabled():
        raise ValueError(
            "drift_correction is experimental and off by default (vertical "
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


def _check_canvas_size(canvas_size) -> None:
    """Require a ``(width, height)`` pair: a string such as ``"1920x1080"`` would
    be read character by character into a 1 x 9 px canvas and draw an empty
    figure."""
    if canvas_size is None:
        return
    try:
        pair = not isinstance(canvas_size, str) and len(tuple(canvas_size)) == 2
    except TypeError:
        pair = False
    if not pair:
        raise ValueError(
            "canvas_size must be a (width, height) pair in pixels, e.g. "
            f"(2560, 1440); got {canvas_size!r} (--canvas WxH on the CLI)."
        )


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
    **figure_overrides: Any,
) -> go.Figure:
    """Build one trial's scanpath figure, by default in the app's Scanpath design.

    Every figure option is a keyword (``show_heatmap=True``, ``color_by="pass_index"``,
    ``x_field="order_in_trial"``), and
    [`figure_options`][scanpath_studio.api.figure_options] lists them with their
    defaults. An option naming a column takes either name: frames under the dataset's
    own column names, as ``load_scanpath_data`` returns them by default, are read
    through the map they carry.

    Args:
        words: A normalized words frame from
            [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data], or ``None``
            for a dataset recorded as raw gaze alone.
        fixations: The normalized fixations frame, or ``None`` likewise.
        participant: The participant ID. It may be left out when the frames hold one
            trial.
        trial: The trial ID. It may be left out when the frames hold one trial.
        screen: The screen of a multipart trial to draw. Left out, the first recorded
            screen; coordinate spaces are never concatenated.
        canvas_size: The monitor size in px, ``(width, height)``. Estimated from the
            data's extent by default; pass the real resolution (``(2560, 1440)`` for
            OneStop) to keep coordinates true to scale.
        base_font_size: The base font size in px.
        font_family: The font family.
        raw_gaze: Samples from [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze],
            filtered to the trial and drawn as recorded, under the fixations. It can be
            the only table: with ``words`` and ``fixations`` ``None``, the trial is
            looked up in the samples, the canvas is estimated from their extent, and the
            figure is the samples alone. No fixations are detected from them, so the
            fixation, saccade and heatmap layers stay empty.
        drift_correction: Experimental. Without ``SCANPATH_EXPERIMENTAL=1``, anything
            but ``None`` or ``"off"`` raises ``ValueError``.
        drift_connectors: Experimental, with ``drift_correction``.
        fix_index_range: ``(start, end)``: draw only fixations ``start`` to ``end`` of
            the trial, 1-based and both inclusive. The app's **Filters & highlights** →
            **Fixations** → *Index range*.
        illustration: Apply the Illustration design: fixations snapped to their lines,
            arced saccades, one color for the fixations and one for the saccades, no
            heatmap or word boxes. Keywords you pass
            still win.
        illustration_label: ``"auto"`` labels the figure an illustration when it no
            longer shows the data as recorded; ``"show"`` and ``"hide"`` decide it.
        title: A title band stamped onto the figure without shrinking the plot, like the
            app's *Title & labels*. Literal text, not the app's ``{trial_id}``-style
            pattern, since you know which trial it is.
        caption: A caption band, likewise.
        column_names: The column map for frames loaded with ``names="canonical"``
            (``data.column_names``). The options then take the dataset's names too, and
            the figure's text uses them.
        **figure_overrides: Any figure option, in place of the app's default. Three take
            a word of explanation:

            - ``palette=`` (``"default"``, ``"print"`` or ``"high-contrast"``, or the
              app's names) sets a group of colors at once. A color you pass explicitly
              wins.
            - ``show_stimulus_image=True`` draws the trial's own stimulus page under the
              scanpath, as the app's **Stimulus** → **Image** does: the ``image_path`` its
              rows carry (from ``load_scanpath_data(image_root=…)`` or
              [`attach_stimulus_images`][scanpath_studio.api.attach_stimulus_images];
              the bundled demo ships its pages), at its ``image_x`` / ``image_y``. A
              ``background_image=`` you pass wins.
            - ``fixation_snap_to_line=True`` moves each fixation up or down onto its
              text line, keeping its x: its word's line, else the nearest.
              ``fixation_snap_position`` says where, in line heights from the line's
              middle (default −0.5, its top edge). The saccades' ends move with the
              markers, and it does nothing with ``show_fixations=False``.

    Returns:
        The Plotly figure.

    Raises:
        TypeError: An unknown keyword. The message names the closest valid ones.
        ValueError: A value an enumerated option does not take, or a ``color_by`` /
            ``highlight_column`` naming a column the trial's table doesn't have. The
            message names the closest ones.

    Warns:
        UserWarning: ``show_stimulus_image=True`` on a trial with no readable page (a
            PNG). The figure draws none.
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
            "saccade_color_mode": "One color",
            "saccade_render_mode": "Arc",
            "fixation_snap_to_line": True,
            "fixation_opacity": 1.0,
            **figure_overrides,
        }
    _reject_unknown_options(
        figure_overrides, _STATIC_FIGURE_PARAMS | {"palette"}, "plot_scanpath"
    )
    _check_canvas_size(canvas_size)
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
            canvas_size = _recorded_screen(words, fixations)
        if canvas_size is None:
            # A trial with no fixations is sized from its samples, as the
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
    annotate_figure(
        fig, title=title, caption=caption, **figure_text_style(render_settings)
    )
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
    **animation_overrides: Any,
) -> go.Figure:
    """Build the animated replay of one trial's scanpath, or of two on one clock.

    Save it as interactive HTML with [`save_figure`][scanpath_studio.api.save_figure],
    whose page keeps the replay's timing, or render it to GIF or MP4 with
    `animation_export.export_animation`, which keeps the same timing. ``fig.show()``
    plays it on Plotly's frame queue, which runs slower than the reading did.

    The replay takes a subset of [`plot_scanpath`][scanpath_studio.api.plot_scanpath]'s
    options (``figure_options("animation")``), and the ones they share default alike, so
    the replay matches the static figure. The replay is made of fixations: it draws no
    raw gaze, and nothing detects fixations from samples.

    **Two scanpaths.** ``trial_b`` co-animates a second trial, like the app's Animate +
    Compare. Both readings are drawn in A's coordinates, so a co-animation is an
    overlay, and a trial from another dataset has to share A's screen. Name that dataset
    with ``dataset_b`` (or give its ``setup_b``), and the pair is checked the way
    [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] checks an overlay. B's
    frames passed without either are taken to be from A's dataset, as ``render`` passes
    them for ``--compare-with`` alone, and are not checked: two readings of one corpus
    can span different extents, and inferring a canvas from each would refuse pairs that
    shared a screen.

    Args:
        words: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        fixations: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        participant: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        trial: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        screen: A's screen of a multipart trial, as in
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        screen_b: B's screen, looked up in B's own trial. Left out, its first recorded
            screen.
        canvas_size: A's monitor size, as in
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        base_font_size: The base font size in px.
        font_family: The font family.
        playback_speed: The replay lasts the reading time divided by this. Any other
            value than ``1`` makes the automatic Illustration label say the timing was
            changed.
        autoplay: Start the saved HTML's replay when it opens, at ``playback_speed``.
            ``False`` saves it paused, to start with ▶ Play. A GIF or MP4 always plays
            from its first frame.
        fix_index_range: ``(start, end)``: replay only that window of the trial's
            fixations, 1-based and inclusive. In a co-animation it windows A only, as in
            the app, where A's slider never cuts B.
        fix_index_range_b: B's window, in a co-animation.
        illustration_label: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        title: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        caption: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        column_names: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        trial_b: B's ``(participant, trial)``. It is looked up in ``words_b`` /
            ``fixations_b`` when they are given, else in ``words`` / ``fixations``, as
            [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes it.
        dataset_b: The name of B's dataset, when it is another one. The pair is then
            checked as an overlay, and B's participant IDs are prefixed with it, so a
            hover says which dataset the participant is from.
        setup: A's `experimental_setup.SetupSnapshot`, the screen the overlay check
            reads. A side without one is read off its data: the extent of that one
            trial, which rarely spans the whole screen, so state both when you know
            them.
        setup_b: B's.
        **animation_overrides: Any figure option the replay takes. Also:

            - ``words_b`` / ``fixations_b``: B's frames. Without ``trial_b`` they must
              hold one trial.
            - ``style_a`` / ``style_b``: each scanpath's style, with the keys
              [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes for
              markers and saccades (``fix_color``, ``marker_size_range``, ``opacity``,
              ``hollow``, ``saccade_color``, ``saccade_style``, ``saccade_width``), so
              the replay and the static comparison draw each trial alike. A lone replay
              ignores them.
            - ``fixation_flags_b``: B's own fixation flags. ``None`` uses A's
              ``fixation_flags``, or ``style_b``'s when it names some.
            - ``show_stimulus_image=True`` draws the trial's own page, as in
              [`plot_scanpath`][scanpath_studio.api.plot_scanpath]. A co-animation draws
              one page, under the text it draws: B's when ``compare_stimulus="b"``, else
              A's.
            - ``palette=`` works here too. Colors it implies that the replay doesn't
              take are dropped rather than raising, since you named a look, not those
              keys.

    Returns:
        The animated Plotly figure.

    Raises:
        ValueError: The trial has no fixations (one recorded as raw gaze alone, or a
            words-only one). Also for ``raw_gaze=``; draw samples with
            ``plot_scanpath(raw_gaze=…)``.
        ValueError: An option the replay does not take (the message names the valid
            ones), a style naming ``saccade_classes`` (the replay has no saccade-class
            filter), or B frames holding several trials without ``trial_b``.
        IncomparableScreensError: B's dataset has a different canvas from A's. A
            ``ValueError``.
    """
    _check_canvas_size(canvas_size)
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
            f"animate_scanpath() does not support: {', '.join(sorted(unknown))}. "
            "figure_options('animation') lists the options it takes."
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
            "replay is built from fixations. Draw it with plot_scanpath(...): its "
            "words alone, or, for a trial recorded as raw gaze, with raw_gaze=... "
            "(its samples are not turned into fixations)."
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
    # the order `compare_scanpaths` resolves it in, and what the screen gate
    # below reads.
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
            # The replay draws neither the snap nor the arcs.
            static=False,
            fix_index_range=fix_index_range,
            full_fixation_range=full_fix_range,
            # B's own flags and window, when it co-animates.
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
    annotate_figure(
        fig, title=title, caption=caption, **figure_text_style(render_settings)
    )
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
        # identity, so an in-place edit between two calls would hand back
        # somebody else's rows.
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
            f"{note} A co-animation replays both trials on one clock in one "
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
    screens: Sequence[str] | None = None,
    **options: Any,
) -> dict[str, go.Figure]:
    """Render every screen of one multipart trial, each in its own coordinates.

    No saccade is ever drawn across a screen boundary.

    Args:
        words: The normalized words frame.
        fixations: The normalized fixations frame.
        participant: The participant ID.
        trial: The parent trial's ID.
        animate: Build replays with
            [`animate_scanpath`][scanpath_studio.api.animate_scanpath] instead of
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath]'s figures.
        transition_mode: ``"instant"`` or ``"recorded"``. Each animated figure's
            ``layout.meta['transition_after_ms']`` records the delay before the next
            screen: zero for ``"instant"``, the observed parent-clock gap for
            ``"recorded"``.
        screens: Only these screen IDs (one may be given as a string), in the trial's
            order, as the app's **Export** → *Screens* does. ``None`` renders them all.
            Each figure's ``screen_index`` meta stays the screen's place in the trial.
        **options: Passed to [`plot_scanpath`][scanpath_studio.api.plot_scanpath] or
            [`animate_scanpath`][scanpath_studio.api.animate_scanpath].

    Returns:
        ``{screen_id: figure}`` in the trial's order, ready to save as per-screen files.
            A single-screen trial gives ``{"screen-1": figure}``.

    Raises:
        ValueError: A screen ID the trial does not have, or ``screens`` for a trial with
            no screens to choose from.
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
    # given and name their figures as they were named.
    catalog = _cn.to_canonical_frame(
        list_parts(words, fixations, pid, tid, raw_gaze=raw_gaze)
    )
    canonical_fixations = _cn.to_canonical_frame(fixations)
    if catalog.empty:
        if screens is not None:
            raise ValueError(
                f"Trial {tid!r} of participant {pid!r} has no screens to choose from."
            )
        renderer = animate_scanpath if animate else plot_scanpath
        return {"screen-1": renderer(words, fixations, pid, tid, **options)}

    screen_ids = catalog[SCREEN_ID].astype(str).tolist()
    if isinstance(screens, str):
        screens = [screens]
    if screens is not None:
        missing = [str(s) for s in screens if str(s) not in screen_ids]
        if missing:
            raise ValueError(
                f"Trial {tid!r} of participant {pid!r} has no screen "
                f"{', '.join(map(repr, missing))}; its screens are "
                f"{', '.join(screen_ids)}."
            )
    chosen = None if screens is None else {str(s) for s in screens}
    # The screens drawn, in the trial's order; a recorded transition runs to
    # the next one *drawn*, and the last drawn has none.
    drawn = [s for s in screen_ids if chosen is None or s in chosen]
    rendered: dict[str, go.Figure] = {}
    for position, screen_id in enumerate(drawn):
        renderer = animate_scanpath if animate else plot_scanpath
        fig = renderer(words, fixations, pid, tid, screen=screen_id, **options)
        delay = 0.0
        if animate and transition_mode == "recorded" and position < len(drawn) - 1:
            current = extract_part(canonical_fixations, pid, tid, screen_id)
            following = extract_part(canonical_fixations, pid, tid, drawn[position + 1])
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
                "screen_index": screen_ids.index(screen_id) + 1,
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
        canvas_size = _recorded_screen(words, fixations)
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
    **figure_overrides: Any,
) -> go.Figure:
    """Build a figure comparing two scanpaths: the app's **Compare** mode.

    **Multipart trials.** Each scanpath is one screen, never a whole multipart trial:
    every screen is its own coordinate space, so pooling them would draw saccades across
    page boundaries. ``list_parts()`` lists the screens.

    **Two datasets.** ``words_b`` / ``fixations_b`` draw B from a *different* dataset.
    Two datasets can hold the same ``(participant_id, trial_id)``, so B's participant
    IDs are prefixed with ``dataset_b`` inside the merged frames. Without that, the
    figure could draw the wrong reading, or rows of both mixed into one. The frames you
    pass in are not modified, and only the trace labels show the prefix.

    **The overlay gate.** An overlay needs both readings on screens of the same size, or
    it raises ``ValueError`` (the app falls back to side by side). That holds across
    datasets, and within one when the two screens carry different ``canvas_width`` /
    ``canvas_height`` or ``setup_b`` states another screen. Pass
    ``layout="side_by_side"`` or ``"stacked"`` to compare readings from different
    screens; each panel is then drawn to its own. Nothing is rescaled.

    **Per-scanpath style.** ``style_a`` / ``style_b`` restyle one scanpath with these
    keys:

    | Key | What it sets | Left out |
    | --- | --- | --- |
    | ``fix_color``, ``saccade_color`` | The scanpath's colors | Its default |
    | ``marker_size_range``, ``opacity``, ``hollow`` | Its fixation markers | Its default |
    | ``saccade_style``, ``saccade_width`` | Its saccade lines | Its default |
    | ``box_color`` | The outline of that reading's word boxes | Its ``fix_color`` |
    | ``box_fill_color`` | Their fill | ``word_box_fill_color`` |
    | ``box_line_opacity``, ``box_fill_opacity`` | Their outline's and fill's opacity, 0–1 (0 hides it) | ``word_box_line_opacity``, ``word_box_fill_opacity`` |
    | ``raw_gaze_color`` | That reading's raw-gaze samples | Its ``fix_color`` |
    | ``heatmap_colorscale`` | That reading's word-box heatmap color scale, on the range both share; two different scales get a color bar each | ``heatmap_colorscale`` |
    | ``fixation_flags``, ``saccade_classes`` | That scanpath's own filters, in place of the figure's | The figure's |

    The box keys and ``raw_gaze_color`` are this figure's only: the co-animation draws
    one set of boxes and no raw gaze, and ignores them.

    Args:
        words: The words frame holding both trials, or A's when ``words_b`` is given.
        fixations: The fixations frame, likewise.
        trial_a: A's ``(participant, trial)``.
        trial_b: B's ``(participant, trial)``.
        screen: A's screen of a multipart trial. Left out, its first recorded screen, as
            in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        screen_b: B's screen, looked up in B's own frames, so it may be a later page or
            another dataset's.
        words_b: B's words frame, to draw B from another dataset.
        fixations_b: B's fixations frame, likewise.
        dataset_b: The name B's participant IDs are prefixed with.
        raw_gaze: Samples from [`load_raw_gaze`][scanpath_studio.api.load_raw_gaze],
            drawn under each reading's scanpath in its color. It serves both readings of
            one dataset; across datasets it is A's. Passing it turns the layer on;
            ``show_raw_gaze=False`` keeps it off.
        raw_gaze_b: B's samples, across datasets.
        layout: ``"overlay"``, ``"side_by_side"`` (``"side-by-side"`` also works) or
            ``"stacked"``.
        compare_stimulus: Whose word boxes and text an overlay draws: ``"both"``,
            ``"a"`` or ``"b"``. Two datasets' boxes coincide only when the text is
            identical. Split layouts ignore it, since each panel draws its own.
        setup: A's `experimental_setup.SetupSnapshot`, the screen the overlay gate
            reads.
        setup_b: B's.
        canvas_size: A's monitor size, when you only have a resolution. Left out with
            ``setup``, the canvas is read off the data.
        labels: The two trace labels, when not the composed defaults.
        style_a: A's style, with the keys above.
        style_b: B's style.
        base_font_size: The base font size in px.
        font_family: The font family.
        fix_index_range: ``(start, end)``: draw only that window of both scanpaths'
            fixations.
        fix_index_range_b: B's own window, as the app's B slider sets it.
        drift_correction: Experimental, as in
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        title: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        caption: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        column_names: As in [`plot_scanpath`][scanpath_studio.api.plot_scanpath]. A's
            names, or ``column_names``, name the options and the figure's text; either
            dataset's frames may come under their own names.
        **figure_overrides: Any figure option a comparison takes
            (``figure_options("comparison")``). Some act per scanpath:

            - ``fixation_flags`` and ``saccade_classes`` filter both scanpaths, unless a
              style gives one its own.
            - ``background_image`` is A's page. A split layout draws B's panel over
              ``background_image_b`` (with ``background_image_size_b`` /
              ``background_image_origin_b``), and over nothing without it, never A's,
              since sharing a dataset says nothing about sharing a page.
            - ``show_stimulus_image=True`` takes each reading's own page from its rows:
              a split layout draws A's and B's, each in its panel, and an overlay the
              page of the text it draws (B's for ``compare_stimulus="b"``, else A's). An
              image passed explicitly wins.

    Returns:
        The Plotly figure.

    Raises:
        ValueError: An overlay of two different screens (see the overlay gate), or a
            ``screen`` / ``screen_b`` the trial does not have or that names a screen of
            a single-screen trial.
        TypeError: An unknown keyword. The message names the closest valid ones.
    """
    _check_canvas_size(canvas_size)
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
    # A's names name the figure's text and its options; every frame,
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

    for side, pair in (("trial_a", trial_a), ("trial_b", trial_b)):
        if isinstance(pair, str) or len(tuple(pair)) != 2:
            raise ValueError(
                f"{side} must be a (participant, trial) pair, e.g. "
                f"('l37_1129', 'l37_1129_2_1_1_Ele'); got {pair!r}. "
                "list_trials(words, fixations) lists the pairs."
            )
    # Ids written before composite ids escaped a `_` inside a part still name
    # their reading when that is unambiguous (`data.respell_reading`).
    pid_a, tid_a = _data.respell_reading(*trial_a, _data.trial_keys(fixations))
    pid_b, tid_b = _data.respell_reading(*trial_b, _data.trial_keys(fixations_b))
    # One screen per side, each resolved in its own frames — the same contract
    # as `plot_scanpath`'s `screen`. Extracting whole parent trials would pool
    # every page of a multipart reading into one scanpath, saccades across pages
    # and all.
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
                f"No fixations for participant={pid!r}, trial={tid!r}: a "
                "comparison draws two scanpaths, so each trial needs fixations. "
                "list_trials() also lists the trials only the words or the raw "
                "gaze has; draw one of those with plot_scanpath()."
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
            # The reason says why; this says what happened here and how
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
        # Same contract as plot_scanpath — raise, don't silently skip.
        if not drift_correction_enabled():
            raise ValueError(
                "drift_correction is experimental and off by default. Set "
                f"{EXPERIMENTAL_ENV_VAR}=1 to enable it, or pass "
                "drift_correction=None."
            )
        from .alignment import correct

        trial_fix_a, _ = correct(trial_fix_a, trial_words_a, drift_correction)
        trial_fix_b, _ = correct(trial_fix_b, trial_words_b, drift_correction)

    if not cross_dataset and (pid_a, tid_a) == (pid_b, tid_b):
        # A trial compared with itself — rename B's copy apart, or the
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
        compare_stimulus=normalize_option_value("compare_stimulus", compare_stimulus),
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
    annotate_figure(
        fig, title=title, caption=caption, **figure_text_style(render_settings)
    )
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
    scale: float = 2,
    width: int | None = None,
    height: int | None = None,
    width_mm: float | None = None,
    width_in: float | None = None,
    dpi: int | None = None,
) -> Path:
    """Save a figure, in the format its file extension names.

    The file carries the citation of Scanpath Studio in its metadata — PNG text
    chunks, an SVG ``<metadata>`` element, the PDF's document properties, the
    HTML page's ``<head>`` — so a figure found later on its own still says how to
    cite it ([`cite`][scanpath_studio.api.cite] prints it). Nothing is drawn.

    Args:
        fig: The figure.
        path: The file to write: ``.html`` (interactive), or ``.png``, ``.svg`` or
            ``.pdf`` (static, through Kaleido; see the [export
            FAQ](https://lacclab.github.io/scanpath-studio/faq/#export-fails) for its
            setup).
        scale: The static image's scale factor.
        width: The image width in px, overriding the figure's own. Ignored for
            ``.html``.
        height: The image height in px, likewise.
        width_mm: A PNG's print width in mm, as the app's Export → *Current figure* sets
            it: 180 mm at 600 dpi is a 4,252 px wide PNG, its height following the
            figure's aspect, with the dpi written into the file. It replaces ``scale``.
        width_in: The same in inches.
        dpi: The resolution for ``width_mm`` / ``width_in``. Default 300.

    Returns:
        The path written.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".html", ".png", ".svg", ".pdf"):
        raise ValueError(
            f"save_figure writes .html, .png, .svg or .pdf, not {suffix or path.name!r}. "
            "For a GIF or MP4 replay, use "
            "scanpath_studio.animation_export.export_animation."
        )
    if not path.parent.is_dir():
        raise FileNotFoundError(
            f"Can't write {path}: the folder {path.parent} does not exist."
        )
    if width_mm is not None or width_in is not None:
        if width_mm is not None and width_in is not None:
            raise ValueError("Pass width_mm or width_in, not both.")
        if suffix != ".png":
            raise ValueError(
                "width_mm / width_in / dpi size a PNG; save as .png, or set "
                "width / height / scale for other formats."
            )
        dpi = int(dpi or _export.DEFAULT_PRINT_DPI)
        unit, value = ("mm", width_mm) if width_mm is not None else ("in", width_in)
        base = int(width or fig.layout.width or 700)
        scale = _export.print_scale(base, float(value), unit, dpi)
    elif dpi is not None:
        raise ValueError(
            "dpi is the resolution of a print width: pass width_mm or width_in too."
        )
    if suffix == ".html":
        # An animation replays on the wall-clock player, which also autoplays
        # it at the configured speed when asked. Plotly's own `auto_play` stays
        # off — it ignores the frame duration. The frames are written packed
        # and rebuilt by the page's own script, so a long replay writes a
        # fraction of the bytes. Static figures are written as they are.
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
        stamp_file(path)
        return path
    if suffix in (".png", ".svg", ".pdf"):
        try:
            fig.write_image(str(path), scale=scale, width=width, height=height)
            if dpi is not None:
                _export.set_png_dpi(path, dpi)
            stamp_file(path)
        except OSError:
            raise  # filesystem problem — the original error says it best
        except Exception as exc:  # Kaleido raises various types
            raise RuntimeError(
                f"Static {suffix} export failed ({exc}). Kaleido needs Chrome, "
                "Chromium or Edge — install one, or run `plotly_get_chrome -y` "
                "once — or save as .html, which needs no browser."
            ) from exc
    return path


def save_figure_layers(
    fig: go.Figure,
    directory: str | Path,
    *,
    fmt: str = "svg",
    scale: int = 2,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Save a scanpath figure as one file per layer, for editing.

    Each *visible* layer (stimulus image, heatmap, word boxes, saccades, fixations, raw
    gaze, labels, frame) is the full figure with only that layer's elements, on a
    transparent background, at the same size and axis ranges. The files line up when
    stacked in Illustrator or Inkscape. The app's Export bundle writes the same files
    under *Layers as separate files*.

    Args:
        fig: A scanpath figure.
        directory: The folder to write ``<layer>.<fmt>`` into.
        fmt: Any [`save_figure`][scanpath_studio.api.save_figure] extension without the
            dot. ``svg`` and ``pdf`` are vector and the best to edit; ``png`` and
            ``html`` work too.
        scale: Passed to [`save_figure`][scanpath_studio.api.save_figure].
        width: Passed to [`save_figure`][scanpath_studio.api.save_figure].
        height: Passed to [`save_figure`][scanpath_studio.api.save_figure].

    Returns:
        ``{layer: Path}`` for each file written.
    """
    directory = Path(directory)
    # A failed render (most often Kaleido with no Chrome) must not leave an
    # empty `<output>_layers/` behind, which reads as "exported, but lost":
    # whatever this call created is removed again if nothing was written to it.
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
    **figure_overrides: Any,
) -> str:
    """Write the API or CLI code that reproduces a figure.

    The headless form of the app's **Share** → **Code**. Give
    it the arguments you would give [`plot_scanpath`][scanpath_studio.api.plot_scanpath]
    (``kind="static"``), [`animate_scanpath`][scanpath_studio.api.animate_scanpath]
    (``"animation"``) or [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths]
    (``"comparison"``), and it returns the snippet that rebuilds that figure. Only the
    options that differ from [`figure_options`][scanpath_studio.api.figure_options] are
    written, so the snippet stays readable. `code_snippet.ReproductionCode` is the
    structured form.

    Args:
        kind: ``"static"``, ``"animation"`` or ``"comparison"``: the builder the snippet
            calls.
        source: How the data is loaded: ``"demo"``, ``"synthetic"``, ``"files"``,
            ``"potec"``, ``"onestop"``, ``"author"``, ``"raw_gaze"`` (a dataset recorded
            as raw gaze alone, whose samples at ``source_options["raw_gaze"]`` are the
            data), or ``"unknown"`` for data a snippet can't name.
        source_options: That loader's arguments: ``{"root": …}``, ``{"words": [...],
            "fixations": [...]}`` and so on. With ``show_raw_gaze=True``, ``"raw_gaze"``
            (and an optional ``"raw_gaze_schema"``) names the raw-gaze files; the demo
            uses its own.
        participant: The participant ID. Left empty, the snippet renders the first
            available trial, as ``render`` does.
        trial: The trial ID, likewise.
        screen: A's screen of a multipart trial (``screen=``, ``--screen``).
        compare: B's ``(participant, trial)``, for a comparison or a co-animation.
        compare_screen: B's screen (``screen_b=``, ``--compare-screen``).
        compare_layout: The comparison's layout, as
            [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes it.
        compare_stimulus: Whose stimulus an overlay draws, as
            [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes it.
        compare_dataset: The dataset B was loaded from, when it is a second one. Both
            forms then load B's own tables, from the placeholder paths ``B_WORDS`` /
            ``B_FIXATIONS`` that you point at its files (``words_b=`` / ``fixations_b=``
            / ``dataset_b=``, and ``--compare-words`` / ``--compare-fixations``).
        compare_canvas: B's screen, ``(width, height)``, with ``compare_dataset``:
            written as ``setup_b=`` and ``--compare-canvas``, which a co-animation
            across datasets needs.
        compare_labels: The two trace labels, when they are not the composed defaults:
            ``labels=`` and ``--label-a`` / ``--label-b``.
        canvas_size: The monitor size. Defaults to the screen ``render`` assumes for the
            source (the bundled demo's 2560×1440, PoTeC's 1680×1050, …), so both forms draw the
            same figure.
        base_font_size: As the builders take it.
        font_family: As the builders take it.
        title: As the builders take it.
        caption: As the builders take it.
        fix_index_range: As the builders take it.
        illustration_label: As the builders take it.
        drift_correction: Experimental, as in
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        drift_connectors: Experimental, as in
            [`plot_scanpath`][scanpath_studio.api.plot_scanpath].
        playback_speed: As [`animate_scanpath`][scanpath_studio.api.animate_scanpath]
            takes it.
        autoplay: As [`animate_scanpath`][scanpath_studio.api.animate_scanpath] takes
            it.
        flavor: ``"python"``, ``"cli"``, or ``"both"`` (separated by a blank line).
        explicit: Write every option at its current value, not only the ones that differ
            from the defaults.
        output: The file the snippet saves. Defaults to ``scanpath.html`` for an
            animation (``render --animate`` writes only HTML) and to a PNG otherwise.
        **figure_overrides: The figure options, as the builder takes them.

    Returns:
        The snippet. Anything neither form can reproduce (a raw-gaze table with no path
            to name, an uploaded stimulus image, B's rows from a second corpus) follows
            as ``# Note:`` comments, as the app's ⚠️ captions and the ``Note:`` lines
            ``render --print-code`` writes to stderr say it.

    Raises:
        ValueError: An unknown ``flavor``.
        TypeError: An option the builder does not take.

    Examples:
        ```python
        print(
            sps.figure_code(
                participant="l7_1090",
                trial="l7_1090_2_1_1_Ele",
                show_heatmap=True,
                flavor="cli",
            )
        )
        ```
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
        # `render` snaps these sources to their recorded screen while
        # `plot_scanpath` estimates one from the data, so leaving the canvas
        # unnamed would make the two flavours of one recipe disagree.
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
    """Describe the recovery cache a local run keeps, without launching the app.

    A local or desktop app stores completed uploaded datasets, column mappings, view
    settings, saved designs, metadata tables and annotations under your cache folder, so
    a refresh or a restart resumes where it left off. A hosted deployment, such as the
    online demo, keeps none. The same information is on the app's **Data Management**
    page under *Saved on this computer*, and in ``scanpath-studio cache``.

    | Key | What it holds |
    | --- | --- |
    | ``enabled``, ``directory`` | Whether caching is on, and where |
    | ``exists``, ``readable`` | Whether its manifest is there and can be read |
    | ``datasets`` | Each stored dataset's name and per-frame row counts |
    | ``rows``, ``bytes``, ``saved_at`` | The totals, and when it was last written |
    | ``annotations``, ``designs``, ``metadata``, ``settings`` | What else is stored |
    | ``damaged`` | Each stored dataset whose entry or files are broken, with the reason. The app restores the others and keeps that one rather than dropping it |
    | ``damaged_metadata`` | Why the stored metadata tables would not restore; ``""`` when they would |

    Returns:
        The status, as a dict with the keys above. Delete the cache with
            [`clear_cache`][scanpath_studio.api.clear_cache].
    """
    from .persistence import cache_status as _cache_status

    return _cache_status(url="http://localhost")


def clear_cache() -> dict:
    """Delete the recovery cache.

    Removes only the files the app wrote (``manifest.json`` and the datasets' Parquet
    files); anything else in the folder is left alone. A *running* local app writes its
    session back out at its next change, so start it with ``scanpath-studio run
    --no-persist`` or ``SCANPATH_STUDIO_PERSIST=0`` to stop that.

    Returns:
        The cache's status afterwards, as
            [`cache_status`][scanpath_studio.api.cache_status] gives it.
    """
    from .persistence import clear_local_state

    clear_local_state()
    return cache_status()


def version_info() -> BuildInfo:
    """Say which build of Scanpath Studio this is, without using the network.

    The same is in the app's Help → About, and in ``scanpath-studio version``.

    | Field | What it holds |
    | --- | --- |
    | ``version`` | ``scanpath_studio.__version__``: the release itself (``"0.35.0"``), or between releases a PEP 440 version that sorts after it. ``"0.35.0.post3+g8f18219"`` is three commits after v0.35.0, at commit ``8f18219``; it ends ``.dirty`` with uncommitted changes |
    | ``release`` | The release it descends from (``scanpath_studio.__release__``) |
    | ``distance`` | The commits since, ``None`` when unknown |
    | ``commit``, ``dirty`` | The commit, and whether there were uncommitted changes |
    | ``source`` | How it was worked out: ``"checkout"`` (``git describe``), ``"stamp"`` (a desktop bundle's build stamp), ``"vcs"`` (a ``pip install git+…``) or ``"release"`` |

    Returns:
        The build, as a `BuildInfo`. Its ``describe()`` says it in a sentence.
    """
    from .build_info import build_info

    return build_info()


def check_for_updates(timeout: float = 5.0) -> UpdateCheck:
    """Ask GitHub whether a newer release than this build is out.

    The one call here that uses the network, and only when made. It reads the latest
    release from ``api.github.com`` (drafts and pre-releases excluded), compares it with
    [`version_info`][scanpath_studio.api.version_info], and never raises. The same check
    is the app's Help → About → *Check for updates*, and ``scanpath-studio version
    --check``.

    | Field | What it holds |
    | --- | --- |
    | ``status`` | ``"up_to_date"``, ``"update_available"``, ``"ahead"`` (a development build past the latest release) or ``"error"`` (offline, no answer within ``timeout`` seconds, rate-limited, …) |
    | ``message`` | The status, in a sentence |
    | ``command`` | With an update available, the shell command that updates this install: ``pip install -U scanpath-studio``, ``uv tool upgrade scanpath-studio``, ``git pull``, … |
    | ``latest.url`` | The release notes |
    | ``download`` | In the desktop app, the archive for this computer |

    Args:
        timeout: How long to wait for GitHub, in seconds.

    Returns:
        The answer, as an `UpdateCheck`.
    """
    from .updates import check_for_updates as _check

    return _check(timeout)


def cite(format: str = "bibtex", corpus: str | None = None) -> str:
    """How to cite Scanpath Studio — and, optionally, the corpus you used.

    The same entries as the app's Help → About and *Cite* buttons, and
    ``scanpath-studio cite``. Every figure, replay and page `save_figure` writes
    also carries the citation in its file metadata.

    ```python
    print(sps.cite())                       # BibTeX
    print(sps.cite("apa", corpus="onestop"))  # APA, plus OneStop's reference
    ```

    Args:
        format: ``"bibtex"``, ``"apa"``, ``"ris"`` (Zotero, Mendeley, EndNote),
            ``"csl-json"``, or ``"credit"`` — one sentence to paste into a figure
            caption.
        corpus: ``"onestop"`` or ``"potec"`` to add that corpus's citation after
            the software's; ``None`` for the software alone.

    Returns:
        The citation as text (APA without Markdown).

    Raises:
        ValueError: For an unknown ``format`` or ``corpus``.
    """
    from .citation import cite as _cite

    return _cite(format, corpus)
