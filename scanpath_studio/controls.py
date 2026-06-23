from __future__ import annotations

import math
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from streamlit_sortables import sort_items

from .annotations import known_tags
from .constants import (
    BACKGROUND_PRESETS,
    COLORSCALES,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_SACCADE_WIDTH,
    HIGHLIGHTED_TEXT_COLOR,
    OUT_OF_TEXT_COLOR,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    WORD_LABEL_COLOR,
    compare_palette_color,
)
from .data import frame_fingerprint

NONE_OPTION = "(none)"

# Static defaults for the keyed visualization widgets that the plot-config
# restore (app._restore_plot_config) can set. Seeded into session_state so those
# widgets render WITHOUT a `value=`/`index=` argument — that keeps their key
# programmatically settable without Streamlit's "default value but also set via
# Session State API" warning. Data-dependent defaults (color-by / axis fields /
# sizing / canvas) are seeded locally where they're computed.
_VIZ_WIDGET_DEFAULTS = {
    # First-load layers default to the *core scanpath* only — fixations, saccades
    # and the reading text — so a new user lands on a legible picture instead of
    # seven stacked encodings. The bounding-box grid and the density heatmap are
    # analytical overlays, off by default and one click (or one Quick view) away.
    "global_show_words": False,
    "global_show_labels": True,
    "global_show_fix": True,
    "global_show_order": False,
    "global_show_saccades": True,
    "global_show_saccade_arrows": False,
    "global_saccade_color": SACCADE_COLOR,
    "global_saccade_style": "Solid",
    "global_saccade_width": DEFAULT_SACCADE_WIDTH,
    # VIZ-6: fixation marker alpha. Default 0.7 so overlapping fixations show
    # through (the classic translucent scanpath look); drag to 1.0 for fully
    # opaque markers. This replaced the old binary `Hollow circles` toggle in the
    # UI — the `global_hollow_fixations` key is kept (no widget) so saved configs
    # / deep links that carry it still render hollow.
    "global_fixation_opacity": 0.7,
    "global_hollow_fixations": False,
    "global_highlight_text_color": HIGHLIGHTED_TEXT_COLOR,
    "global_show_heatmap": False,
    "global_show_raw_gaze": False,
    "global_show_stimulus_image": False,
    "global_heatmap_style": "Word boxes",
    "global_heatmap_metric": "duration_ms",
    "global_show_colorbars": False,
    # Frame the view to the whole presentation monitor (scanpath sits at its true
    # on-screen position) rather than cropping to the data extent. Default on.
    "global_fit_to_monitor": True,
    "global_order_font_color": "#111111",
    "global_order_font_size": 10,
    "global_fixation_colorscale": DEFAULT_FIXATION_COLORSCALE,
    "global_heatmap_colorscale": DEFAULT_HEATMAP_COLORSCALE,
    # Restorable by the Save & restore config too, so seed here (no inline
    # value=/index=) to avoid Streamlit's "default value but also set via
    # Session State API" warning when a restore pre-sets them.
    "global_critical_span_style": "Mark text",
    "global_span_border_color": "#000000",
    # Fixation classification (viz-only — PRE-2). SHORT / LONG / OUT-OF-BOUNDS
    # each get a mode (Off | Highlight | Discard); Highlight overlays a marker in
    # the chosen symbol+colour, Discard hides them from the plot only (reading
    # measures and export tables are untouched). Short/long thresholds in ms
    # follow eyekit's discard_short (~80) / discard_long (~800).
    "global_fixclass_short_mode": "Off",
    "global_fixclass_short_threshold_ms": 80,
    "global_fixclass_short_symbol": "triangle-up-open",
    "global_fixclass_short_color": "#ff7f0e",
    "global_fixclass_long_mode": "Off",
    "global_fixclass_long_threshold_ms": 800,
    "global_fixclass_long_symbol": "square-open",
    "global_fixclass_long_color": "#9467bd",
    "global_fixclass_oob_mode": "Off",
    "global_fixclass_oob_symbol": "x",
    "global_fixclass_oob_color": OUT_OF_TEXT_COLOR,
    # VIZ-7: single-trial fixation-index window (start, end over `order_in_trial`)
    # for the main scanpath plot. `None` = full trial; the real bounds depend on
    # the selected trial's fixation count, so `sidebar_controls` resolves/clamps
    # the concrete (1, max_fix) range at render time (mirroring `multi_fix_range`).
    "single_fix_range": None,
    # Show the A/B legend on the two-trial comparison overlay (CMP-2). Off by
    # default — the per-scanpath colours already tell the readings apart.
    "global_show_compare_legend": False,
    # Colour-bar styling (Axes & color bars expander).
    "global_colorbar_orientation": "Vertical",
    "global_colorbar_tickangle": 0,
    "global_colorbar_tickfont_size": 12,
}


# Out-of-text fixation marker options: Plotly symbol → emoji-prefixed label (the
# emoji makes each choice stand out in the dropdown).
_OUT_OF_TEXT_MARKERS = {
    "x": "✖️ Cross",
    "circle-open": "⭕ Circle",
    "diamond-open": "🔷 Diamond",
    "square-open": "🟦 Square",
    "star": "⭐ Star",
    "triangle-up-open": "🔺 Triangle",
    "triangle-down-open": "🔻 Triangle (down)",
}

# Fixation-classification modes (PRE-2): a category can be left alone, marked with
# an overlay marker, or hidden from the plot (viz-only — never changes measures).
_FIXCLASS_MODES = ("Off", "Highlight", "Discard")


def _render_fixclass_category(
    key_prefix: str, label: str, *, threshold_label: Optional[str] = None
) -> None:
    """Render one fixation-classification category (PRE-2) inside the Fixation popover.

    A mode radio (Off / Highlight / Discard); when not Off and ``threshold_label``
    is given, a ms threshold number input; when Highlight, a marker + colour picker.
    All values ride ``global_fixclass_{key_prefix}_*`` keys (seeded in
    ``_VIZ_WIDGET_DEFAULTS``)."""
    mode = st.radio(
        label,
        options=_FIXCLASS_MODES,
        horizontal=True,
        key=f"global_fixclass_{key_prefix}_mode",
        help="Highlight marks these fixations with an overlay marker; Discard hides "
        "them from the plot only (reading measures and exported tables are "
        "unchanged).",
    )
    if threshold_label is not None and mode != "Off":
        st.number_input(
            threshold_label,
            min_value=1,
            step=10,
            key=f"global_fixclass_{key_prefix}_threshold_ms",
        )
    if mode == "Highlight":
        st.selectbox(
            "Marker",
            options=list(_OUT_OF_TEXT_MARKERS),
            format_func=lambda s: _OUT_OF_TEXT_MARKERS[s],
            key=f"global_fixclass_{key_prefix}_symbol",
        )
        st.color_picker("Color", key=f"global_fixclass_{key_prefix}_color")


def _render_fixation_cleaning() -> None:
    """The PRE-2 'Classify fixations' block (short / long / out-of-bounds), rendered
    inside the ⚙ Fixation style popover. Viz-only: highlight or discard, with
    customizable short/long thresholds, all on the spot."""
    st.divider()
    st.caption("Classify fixations (visual only)")
    _render_fixclass_category(
        "short", "Short fixations", threshold_label="Short threshold (ms)"
    )
    _render_fixclass_category(
        "long", "Long fixations", threshold_label="Long threshold (ms)"
    )
    _render_fixclass_category("oob", "Out-of-bounds fixations")


def _collect_fixation_flags() -> Dict:
    """Build the ``fixation_flags`` dict the figure builder consumes from the
    ``global_fixclass_*`` session keys (PRE-2). One entry per category; ``oob`` has
    no threshold."""
    ss = st.session_state
    return {
        "short": {
            "mode": ss.get("global_fixclass_short_mode", "Off"),
            "threshold_ms": float(ss.get("global_fixclass_short_threshold_ms") or 80),
            "symbol": ss.get("global_fixclass_short_symbol") or "triangle-up-open",
            "color": ss.get("global_fixclass_short_color") or "#ff7f0e",
        },
        "long": {
            "mode": ss.get("global_fixclass_long_mode", "Off"),
            "threshold_ms": float(ss.get("global_fixclass_long_threshold_ms") or 800),
            "symbol": ss.get("global_fixclass_long_symbol") or "square-open",
            "color": ss.get("global_fixclass_long_color") or "#9467bd",
        },
        "oob": {
            "mode": ss.get("global_fixclass_oob_mode", "Off"),
            "symbol": ss.get("global_fixclass_oob_symbol") or "x",
            "color": ss.get("global_fixclass_oob_color") or OUT_OF_TEXT_COLOR,
        },
    }


# Quick-view presets: one click sets the *layer* toggles to a focused subset, so
# a user lands on a legible picture instead of toggling layers one by one. Only
# the ``global_show_*`` on/off keys are set — per-layer styling (colours, sizes,
# colorscales) is deliberately left untouched. Keys not listed in a preset keep
# their current value, so e.g. "Heatmap" leaves the bounding-box grid off.
_VIEW_PRESETS: Dict[str, Dict[str, bool]] = {
    "scanpath": {
        "global_show_fix": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": False,
        "global_show_labels": True,
        "global_show_order": False,
        "global_show_heatmap": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "heatmap": {
        "global_show_heatmap": True,
        "global_show_labels": True,
        "global_show_fix": False,
        "global_show_saccades": False,
        "global_show_order": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "reading_order": {
        "global_show_fix": True,
        "global_show_order": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": True,
        "global_show_labels": True,
        "global_show_heatmap": False,
        "global_show_words": False,
        "global_show_raw_gaze": False,
    },
    "everything": {
        "global_show_words": True,
        "global_show_labels": True,
        "global_show_fix": True,
        "global_show_saccades": True,
        "global_show_saccade_arrows": True,
        "global_show_heatmap": True,
        "global_show_order": False,
        "global_show_raw_gaze": False,
    },
}


def _apply_view_preset(name: str) -> None:
    """Apply a Quick-view preset's layer toggles.

    Runs as a button ``on_click`` callback, i.e. *before* the next rerun
    instantiates the layer checkboxes — so writing their ``global_show_*`` keys
    here is picked up cleanly (no "set after widget instantiated" warning)."""
    for key, value in _VIEW_PRESETS[name].items():
        st.session_state[key] = value


# Help text for the (multi-capable) Trial ID mapping, shared by all tables.
_TRIAL_MAPPING_HELP = (
    "Pick the column holding your unique trial ID — or pick SEVERAL columns "
    "to build one on the fly (values joined with '_'), e.g. participant + "
    "paragraph + repeated-reading when no single column identifies a trial. "
    "Use the same columns for every uploaded table so trials line up."
)

# Word-box geometry is one rectangle in two interchangeable encodings. The
# mapping UI shows a format picker plus four fields instead of all eight at once;
# both encodings normalize to canonical x/y/width/height in
# ``data.normalize_words``, so the returned schema still carries all eight keys.
BOX_FORMAT_EDGES = "Edges"
BOX_FORMAT_ORIGIN = "Origin + size"
_BOX_SUBFIELDS: Dict[str, List[tuple]] = {
    BOX_FORMAT_EDGES: [
        ("left", "Box left"),
        ("right", "Box right"),
        ("top", "Box top"),
        ("bottom", "Box bottom"),
    ],
    BOX_FORMAT_ORIGIN: [
        ("x", "Box x (top-left)"),
        ("y", "Box y (top-left)"),
        ("width", "Box width"),
        ("height", "Box height"),
    ],
}
_ALL_BOX_KEYS = [key for fields in _BOX_SUBFIELDS.values() for key, _ in fields]


def _default_box_format(proposed: Dict[str, Optional[str]]) -> str:
    """Which box encoding to show first, from what auto-detect found.

    Edges if all four edge columns were detected, else origin+size if those four
    were, else edges."""
    if all(proposed.get(k) for k in ("left", "right", "top", "bottom")):
        return BOX_FORMAT_EDGES
    if all(proposed.get(k) for k in ("x", "y", "width", "height")):
        return BOX_FORMAT_ORIGIN
    return BOX_FORMAT_EDGES


WORD_FIELD_SPECS: List[Dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": False,
        "help": "Which reader produced this row. Splits scanpaths per "
        "participant; omit for stimulus-level word boxes shared across all readers.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "word_id",
        "label": "Word/IA ID",
        "required": True,
        "help": "Identifier of each word / interest-area — the key fixations "
        "attach to, and the order of words within a trial.",
    },
    {
        "key": "text",
        "label": "Word text/label",
        "required": False,
        "help": "The word's text; drawn on the stimulus and shown in tooltips.",
    },
    {
        "key": "text_id",
        "label": "Text ID",
        "required": False,
        "help": "Groups words by the text/passage they belong to, for filtering "
        "and selection; falls back to the trial id.",
    },
    {
        "key": "line",
        "label": "Line index",
        "required": False,
        "help": "Line number of the word on screen; used for color-by-line "
        "(otherwise inferred from box Y).",
    },
    {
        "key": "box",
        "kind": "box",
        "label": "Word box",
        "required": True,
        "help": "Bounding box per word/AOI. Edges = left/right/top/bottom (EyeLink IA_*); origin+size = x/y/width/height.",
    },
]

FIX_FIELD_SPECS: List[Dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": True,
        "help": "Which reader produced this fixation. Splits scanpaths per participant.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "x",
        "label": "X coordinate",
        "required": False,
        "help": "Fixation pixel X. Leave empty for AOI-only data and map "
        "Word/IA ID instead — those fixations are placed at word-box centers.",
    },
    {
        "key": "y",
        "label": "Y coordinate",
        "required": False,
        "help": "Fixation pixel Y. Leave empty for AOI-only data (map Word/IA ID instead).",
    },
    {
        "key": "duration",
        "label": "Duration (ms)",
        "required": True,
        "help": "Fixation length in milliseconds; drives marker size and "
        "dwell-time / reading measures.",
    },
    {
        "key": "timestamp",
        "label": "Timestamp (ms)",
        "required": False,
        "help": "Fixation onset time (ms); orders fixations and drives the "
        "animation clock. Defaults to row order.",
    },
    {
        "key": "fixation_id",
        "label": "Fixation ID",
        "required": False,
        "help": "Sequential fixation number within a trial. Defaults to row order.",
    },
    {
        "key": "text_id",
        "label": "Text ID",
        "required": False,
        "help": "Groups fixations by the text/passage they belong to, for "
        "filtering and selection.",
    },
    {
        "key": "word_id",
        "label": "Word/IA ID",
        "required": False,
        "help": "Which word/AOI each fixation landed on. Authoritative when "
        "present (overrides geometric assignment), and supplies the location "
        "when X/Y are absent.",
    },
    # pass_index / saccade_type / saccade_amplitude / eye are no longer explicit
    # mapping fields — they're auto-detected and offered under "fields to keep"
    # (see data.FIX_OPTIONAL_FIELDS), so they don't clutter the wizard and aren't
    # hardcoded as schema. noise_flag was removed (it silently dropped fixations
    # with no UI to undo); saccade_amplitude is recomputed from X/Y by measures.
]

RAW_GAZE_FIELD_SPECS: List[Dict] = [
    {
        "key": "participant",
        "label": "Participant ID",
        "required": True,
        "help": "Which reader produced this gaze sample.",
    },
    {
        "key": "trial",
        "label": "Trial ID",
        "required": True,
        "multi": True,
        "help": _TRIAL_MAPPING_HELP,
    },
    {
        "key": "x",
        "label": "X coordinate",
        "required": True,
        "help": "Gaze pixel X at this timepoint.",
    },
    {
        "key": "y",
        "label": "Y coordinate",
        "required": True,
        "help": "Gaze pixel Y at this timepoint.",
    },
    {
        "key": "timestamp",
        "label": "Timestamp (ms)",
        "required": False,
        "help": "Sample time (ms); orders the continuous gaze path. "
        "Defaults to row order.",
    },
    {
        "key": "text",
        "label": "Word text/label",
        "required": False,
        "help": "Optional word/label associated with the sample.",
    },
]


def column_mapping_ui(
    df: pd.DataFrame,
    table_label: str,
    state_key_prefix: str,
    field_specs: List[Dict],
    proposed: Dict[str, Optional[str]],
    expand_on_problem: bool = True,
    problems: Optional[List[str]] = None,
    container=None,
    use_expander: bool = True,
    only_keys: Optional[List[str]] = None,
    header: bool = True,
    detected_label: str = "auto-detected",
) -> Dict[str, Optional[str]]:
    """Render a column-mapping expander letting users override the inferred mapping.

    Renders in the sidebar by default; pass ``container`` (e.g. a main-area
    container from the setup wizard) to render it there instead.

    Returns a mapping {field_key: column_name_or_None}. Fields marked
    ``multi: True`` (Trial ID) render as a multiselect: picking several columns
    yields a list, meaning "build this ID on the fly by joining the columns'
    values" (see ``data.trial_id_series``); a single pick stays a plain string.
    A field marked ``kind: "box"`` (the word box) renders a coordinate-format
    radio plus the four sub-fields for that format, and expands into all eight
    box keys (the four inactive ones set to None) so the returned schema keeps
    its fixed shape.
    """
    options = [NONE_OPTION] + list(df.columns)
    expanded = bool(expand_on_problem and problems)

    def _selectbox(field_key: str, field_label: str, help_text=None) -> Optional[str]:
        default = proposed.get(field_key)
        index = options.index(default) if default in options else 0
        chosen = st.selectbox(
            field_label,
            options=options,
            index=index,
            key=f"{state_key_prefix}_{field_key}",
            help=help_text,
        )
        # Surface what auto-detection found for this field (ENG-9) — and flag when
        # the user has overridden it — so the mapping isn't silently inferred.
        if default and default in df.columns:
            if chosen != default and chosen != NONE_OPTION:
                st.caption(f"✨ {detected_label} `{default}` · overridden")
            else:
                st.caption(f"✨ {detected_label} `{default}`")
        return None if chosen == NONE_OPTION else chosen

    host = container if container is not None else st.sidebar
    # Render inside an expander by default; ``use_expander=False`` renders inline
    # (the collapsed wizard panel already lives in an expander — Streamlit forbids
    # nesting expanders).
    section = (
        host.expander(f"Column mapping — {table_label}", expanded=expanded)
        if use_expander
        else host.container()
    )
    with section:
        if not use_expander and header:
            st.markdown(f"**Column mapping — {table_label}**")
        if header:
            st.caption(
                "Auto-detected from your CSV. Override any row if your column "
                "names differ."
            )
        if problems:
            st.warning(
                "Fix these before the app can use this table: " + "; ".join(problems)
            )
        mapping: Dict[str, Optional[str]] = {}
        for spec in field_specs:
            key = spec["key"]
            # When ``only_keys`` is given, render just that subset (the wizard
            # renders fields in grouped, ordered steps).
            if only_keys is not None and key not in only_keys:
                continue
            default = proposed.get(key)
            label = spec["label"] + (" *" if spec.get("required") else "")
            if spec.get("kind") == "box":
                fmt_key = f"{state_key_prefix}_box_format"
                if fmt_key not in st.session_state:
                    # Seed via session state (no `index=`) so it survives reruns
                    # and never fights a default arg — same pattern as the
                    # multiselect below.
                    st.session_state[fmt_key] = _default_box_format(proposed)
                star = " \\*" if spec.get("required") else ""
                st.markdown(f"**{spec['label']}**{star}")
                if spec.get("help"):
                    st.caption(spec["help"])
                fmt = st.radio(
                    "Coordinate format",
                    options=list(_BOX_SUBFIELDS),
                    key=fmt_key,
                    horizontal=True,
                    label_visibility="collapsed",
                )
                # Always emit all eight box keys; only the active format's four
                # get a column, the rest stay None.
                mapping.update({box_key: None for box_key in _ALL_BOX_KEYS})
                for sub_key, sub_label in _BOX_SUBFIELDS[fmt]:
                    mapping[sub_key] = _selectbox(sub_key, sub_label)
                continue
            if spec.get("multi"):
                state_key = f"{state_key_prefix}_{key}"
                proposed_default = [default] if default in df.columns else []
                stored = st.session_state.get(state_key)
                if stored is None:
                    # Seed via session state instead of `default=` so the
                    # stale-column reset below never fights a default arg.
                    st.session_state[state_key] = proposed_default
                else:
                    # A new upload changes the column universe — silently
                    # keeping stale picks would leave the field empty (the
                    # selectboxes self-heal via their index fallback; a
                    # multiselect doesn't). Drop unknown columns and fall
                    # back to the auto-proposal when nothing survives.
                    valid = [c for c in stored if c in df.columns]
                    if len(valid) != len(stored):
                        st.session_state[state_key] = valid or proposed_default
                chosen_cols = st.multiselect(
                    label,
                    options=list(df.columns),
                    key=state_key,
                    help=spec.get("help"),
                )
                if default and default in df.columns:
                    st.caption(f"✨ {detected_label} `{default}`")
                if not chosen_cols:
                    mapping[key] = None
                elif len(chosen_cols) == 1:
                    mapping[key] = chosen_cols[0]
                else:
                    mapping[key] = list(chosen_cols)
                continue
            mapping[key] = _selectbox(key, label, spec.get("help"))
    return mapping


def data_dictionary_help_text() -> str:
    return (
        "Data dictionary / expected columns:\n"
        "The app auto-detects column names from csv tables using common conventions.\n"
        "- Words/IA: tries `participant_id`/`subject_id`, `unique_trial_id`/`trial_id`/`unique_paragraph_id`, "
        "`IA_ID`/`word_id`, optional `IA_LABEL`/`text`, paragraph ids, and bounding boxes via either "
        "edges `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)` or origin+size `(x, y, width, height)` — "
        "pick which in the *Word box* selector.\n"
        "- Fixations: tries `participant_id`/`subject_id`, `unique_trial_id`/`trial_id`/`unique_paragraph_id`, "
        "`CURRENT_FIX_DURATION`, `CURRENT_FIX_X`/`CURRENT_FIX_Y`, and optionally `CURRENT_FIX_START`, "
        "`IA_ID`, and a fixation id. X/Y are optional when `IA_ID` is mapped "
        "(AOI-only fixations are placed at word-box centers). Extra fixation "
        "columns (`pass_index`/`reread`, `saccade_type`, `saccade_amplitude`, "
        "`eye`, …) are auto-detected and offered under *fields to keep*.\n"
        "- Raw gaze (optional): millisecond-level data with `participant_id`, `trial_id`, `x`, `y`. "
        "Each row represents one timepoint.\n"
        "If your columns are named differently, after uploading expand the "
        "*Column mapping* sections in the sidebar to map each field to your column.\n"
        "No single column uniquely identifies a trial? Map *Trial ID* to several "
        "columns (e.g. participant + paragraph + repeated reading) and the app "
        "builds a combined unique trial ID on the fly.\n"
        "Multi-file datasets: upload several files at once (e.g. one per "
        "participant or text) and they're concatenated, each row tagged by its "
        "`source_file`.\n"
        "Single-report datasets: upload only a words/IA table OR only a "
        "fixations table — the missing layer is skipped. A words-only table "
        "still draws a heatmap from its pre-aggregated reading measures.\n"
        "Stimulus-level word boxes (no participant column) are shared across "
        "every participant who read that trial; fixations with a word/AoI id "
        "but no x/y are placed at the matching word-box centers.\n"
        "Only fields present in your data are used for filters, coloring, and tooltips.\n"
        "Areas of interest (word boxes) are taken from your data, not computed; "
        "fixations are tied to words by bounding-box containment with a small "
        "nearest-word fallback, and fixations outside every box are flagged out-of-text."
    )


# Field-option helpers — shared by the sidebar selectors and the plot-config
# restore path (`app._restore_plot_config`) so both agree on what's valid for
# the current data.
def color_field_options(trial_fixations: pd.DataFrame) -> List[str]:
    """Columns offered in the 'Color fixations by' selector — a preferred order
    intersected with what's present, falling back to ``['duration_ms']``."""
    preferred_color_fields = [
        "duration_ms",
        "pass_index",
        "eye",
        "saccade_type",
        "saccade_amplitude",
        "word_id",
        "timestamp_ms",
        "is_regression",
        "progression",
        "gpt2_surprisal",
        "wordfreq_frequency",
        "subtlex_frequency",
        "universal_pos",
        "ptb_pos",
    ]
    fields = [f for f in preferred_color_fields if f in trial_fixations.columns]
    fields = fields or ["duration_ms"]
    # "line" is a synthetic option (not a real column): colour each fixation by
    # the text line it lands on, lines inferred from word geometry. Folded in
    # from the former standalone "Color fixations by line" checkbox.
    return fields + ["line"]


def numeric_field_options(trial_fixations: pd.DataFrame) -> List[str]:
    """Numeric columns offered as X/Y axis fields."""
    return [
        col
        for col in trial_fixations.columns
        if pd.api.types.is_numeric_dtype(trial_fixations[col])
    ]


# Word columns that look like a per-word boolean flag the user might want to
# highlight on the text (the OneStop answer/distractor spans first, then any
# other boolean column).
_PREFERRED_HIGHLIGHT_FIELDS = ["is_in_aspan", "is_in_dspan"]


def highlight_column_options(words: Optional[pd.DataFrame]) -> List[str]:
    """Boolean word columns offered in the 'Highlight words by' selector.

    The OneStop answer/distractor spans lead, followed by any other boolean
    column in the words frame. Empty when there's nothing to highlight."""
    if words is None or words.empty:
        return []
    cols = [c for c in _PREFERRED_HIGHLIGHT_FIELDS if c in words.columns]
    for col in words.columns:
        if col not in cols and pd.api.types.is_bool_dtype(words[col]):
            cols.append(col)
    return cols


def _drop_stale(state_key: str, options: list) -> None:
    """Clear a persisted selectbox value that isn't valid for the current
    ``options`` (e.g. after switching datasets, or restoring a config built on
    different data) so ``st.selectbox`` falls back to its ``index=`` default
    instead of raising. Mirrors the guard in ``utils._select_trial_composite_mode``."""
    if state_key in st.session_state and st.session_state[state_key] not in options:
        del st.session_state[state_key]


def _clamp_range(state_key: str, lo: float, hi: float) -> None:
    """Clamp a persisted ``(min, max)`` range-slider value into ``[lo, hi]`` so a
    restored value built on different data can't fall outside the slider bounds
    and raise. Drops anything that isn't a 2-tuple."""
    val = st.session_state.get(state_key)
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        st.session_state.pop(state_key, None)
        return
    try:
        a, b = float(val[0]), float(val[1])
    except (TypeError, ValueError):
        del st.session_state[state_key]
        return
    a, b = max(lo, min(a, hi)), max(lo, min(b, hi))
    st.session_state[state_key] = (min(a, b), max(a, b))


def _clamped_pair(val, lo: float, hi: float) -> Optional[tuple]:
    """Pure twin of ``_clamp_range``: clamp a stored ``(min, max)`` into ``[lo,
    hi]`` and return it, or ``None`` for a malformed/missing value — WITHOUT
    touching session_state. Used by ``_collect_viz_settings`` (the non-rendering
    reader) so a colour range stored on differently-scaled data is clamped the
    same way the rendered slider clamps it, instead of leaking out-of-bounds into
    the Corpus / Save-&-restore figures."""
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        return None
    try:
        a, b = float(val[0]), float(val[1])
    except (TypeError, ValueError):
        return None
    a, b = max(lo, min(a, hi)), max(lo, min(b, hi))
    return (min(a, b), max(a, b))


_COMPARE_SCANPATHS = ((0, "Scanpath 1"), (1, "Scanpath 2"))


def _seed_compare_styles() -> None:
    """Seed the per-scanpath comparison styling keys (so the collected dicts have
    values even when the relevant layer popover isn't open this run).

    The two COLOUR keys (``cmp{idx}_fix_color`` / ``cmp{idx}_saccade_color``) are
    intentionally NOT seeded here: a conditionally-rendered ``st.color_picker``
    that relies on a pre-seeded key (no ``value=``) desyncs to **black** on its
    first appearance, then writes that black back on the next interaction (the
    "fixations turn black when making changes" bug). Those pickers instead pass an
    explicit ``value=`` (see ``_render_compare_fix_styles`` /
    ``_render_compare_saccade_styles``)."""
    for idx, _ in _COMPARE_SCANPATHS:
        st.session_state.setdefault(f"cmp{idx}_saccade_style", "Solid")
        st.session_state.setdefault(f"cmp{idx}_saccade_width", DEFAULT_SACCADE_WIDTH)
        st.session_state.setdefault(
            f"cmp{idx}_marker_size_range", DEFAULT_MARKER_SIZE_RANGE
        )
        # VIZ-6: per-scanpath marker alpha (replaces the per-scanpath hollow
        # checkbox). Default 0.7 matches the single-trial default so overlapping
        # fixations show through. `cmp{idx}_hollow` kept seeded for saved-config /
        # deep-link backward compatibility (no widget renders it anymore).
        st.session_state.setdefault(f"cmp{idx}_opacity", 0.7)
        st.session_state.setdefault(f"cmp{idx}_hollow", False)


def _render_compare_fix_styles() -> None:
    """Per-scanpath *fixation* styling for the two-trial comparison — rendered
    inside the Fixation-style popover (when comparing), beside the single-trial
    fixation controls."""
    st.caption("Per-scanpath (comparison)")
    for idx, name in _COMPARE_SCANPATHS:
        key = f"cmp{idx}_fix_color"
        # Explicit value= (not a pre-seed) so a conditionally-rendered colour
        # picker shows its real colour instead of desyncing to black.
        st.color_picker(
            f"{name} — fixation color",
            value=st.session_state.get(key, compare_palette_color(idx)),
            key=key,
        )
        st.slider(
            f"{name} — marker size range", 4, 40, key=f"cmp{idx}_marker_size_range"
        )
        st.slider(
            f"{name} — opacity",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            format="%.2f",
            key=f"cmp{idx}_opacity",
            help="Marker opacity for this scanpath (1.0 = fully opaque).",
        )


def _render_compare_saccade_styles() -> None:
    """Per-scanpath *saccade* styling for the two-trial comparison — rendered
    inside the Saccade-style popover (when comparing)."""
    st.caption("Per-scanpath (comparison)")
    style_labels = list(SACCADE_DASH_OPTIONS.keys())
    for idx, name in _COMPARE_SCANPATHS:
        key = f"cmp{idx}_saccade_color"
        st.color_picker(
            f"{name} — saccade color",
            value=st.session_state.get(key, compare_palette_color(idx)),
            key=key,
        )
        st.selectbox(
            f"{name} — line style", options=style_labels, key=f"cmp{idx}_saccade_style"
        )
        st.slider(
            f"{name} — line width",
            min_value=SACCADE_WIDTH_BOUNDS[0],
            max_value=SACCADE_WIDTH_BOUNDS[1],
            step=0.5,
            format="%.1f px",
            key=f"cmp{idx}_saccade_width",
        )


def _collect_compare_styles() -> tuple[dict, dict]:
    """Build the ``(style_a, style_b)`` dicts the comparison figure consumes from
    the ``cmp{idx}_*`` session keys (rendered under each layer's popover)."""
    styles: list[dict] = []
    for idx, _ in _COMPARE_SCANPATHS:
        default_color = compare_palette_color(idx)
        styles.append(
            dict(
                # `or default_color` so a falsy ("" / None) value can never escape
                # as a colour (defensive against the color-picker black desync).
                fix_color=st.session_state.get(f"cmp{idx}_fix_color") or default_color,
                saccade_color=(
                    st.session_state.get(f"cmp{idx}_saccade_color") or default_color
                ),
                saccade_style=SACCADE_DASH_OPTIONS.get(
                    st.session_state.get(f"cmp{idx}_saccade_style", "Solid"), "solid"
                ),
                saccade_width=float(
                    st.session_state.get(
                        f"cmp{idx}_saccade_width", DEFAULT_SACCADE_WIDTH
                    )
                ),
                marker_size_range=tuple(
                    st.session_state.get(
                        f"cmp{idx}_marker_size_range", DEFAULT_MARKER_SIZE_RANGE
                    )
                ),
                hollow=bool(st.session_state.get(f"cmp{idx}_hollow", False)),
                opacity=float(st.session_state.get(f"cmp{idx}_opacity", 1.0)),
            )
        )
    return styles[0], styles[1]


def _fix_range_max(fixations: Optional[pd.DataFrame]) -> int:
    """Highest 1-based fixation index in ``fixations`` (0 when none)."""
    if (
        fixations is None
        or fixations.empty
        or "order_in_trial" not in fixations.columns
    ):
        return 0
    top = pd.to_numeric(fixations["order_in_trial"], errors="coerce").max()
    return int(top) if pd.notna(top) else 0


def _render_fix_range_slider(fixations: Optional[pd.DataFrame]) -> None:
    """Render the VIZ-7 fixation-index window slider (``single_fix_range``).

    Mirrors the Generations tab's ``multi_fix_range``: the slider value persists
    across trial changes (which shift ``max_fix``), so it is seeded/clamped via
    session_state *only* (no ``value=`` arg) to stay inside ``[1, max_fix]`` — a
    stored out-of-range value would otherwise raise. A trial with fewer than two
    fixations can't host a range slider (a one-value slider throws in the
    browser), so the window is cleared to ``None`` (the full, unsliced trial)."""
    if fixations is None:
        return
    max_fix = _fix_range_max(fixations)
    if max_fix < 2:
        # Nothing meaningful to window — clear any stale stored range so the
        # plot isn't filtered by a window the slider can no longer show.
        if st.session_state.get("single_fix_range") is not None:
            st.session_state["single_fix_range"] = None
        return
    stored = st.session_state.get("single_fix_range")
    if isinstance(stored, (tuple, list)) and len(stored) == 2:
        lo = max(1, min(int(stored[0]), max_fix))
        hi = max(lo, min(int(stored[1]), max_fix))
        st.session_state["single_fix_range"] = (lo, hi)
    else:
        st.session_state["single_fix_range"] = (1, max_fix)
    st.slider(
        "Fixation index range",
        min_value=1,
        max_value=max_fix,
        key="single_fix_range",
        help="Draw only fixations whose index falls in this range (their "
        "saccades follow). The chips and panels still describe the full trial; "
        "the bulk (multiple-trial) export is unaffected.",
    )


def _seed_viz_state(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    words: Optional[pd.DataFrame],
) -> tuple[List[str], List[str], List[str]]:
    """Seed every viz widget's session_state default (pure — renders nothing).

    Both ``sidebar_controls`` (which renders the widgets) and
    ``viz_settings_from_state`` (the non-rendering reader used by the Corpus view
    and the Save & restore panel) call this first, so the controls and their
    consumers can't drift. The widgets render WITHOUT a ``value=``/``index=``
    argument and rely on these defaults, which keeps their keys programmatically
    settable (deep links / plot-config restore) without Streamlit's "default
    value but also set via Session State API" warning. ``setdefault`` leaves any
    URL-preset / restored value in place. Returns ``(color_fields,
    numeric_fields, highlight_options)`` for the caller to reuse.
    """
    for _key, _default in _VIZ_WIDGET_DEFAULTS.items():
        st.session_state.setdefault(_key, _default)
    st.session_state.setdefault("global_marker_size_range", (8, 24))
    _seed_compare_styles()

    color_fields = color_field_options(trial_fixations)
    _drop_stale("global_color_by", color_fields)
    st.session_state.setdefault(
        "global_color_by",
        "duration_ms" if "duration_ms" in color_fields else color_fields[0],
    )

    numeric_fields = numeric_field_options(trial_fixations)
    if numeric_fields:
        x_default = "x" if "x" in numeric_fields else numeric_fields[0]
        y_default = (
            "y"
            if "y" in numeric_fields
            else numeric_fields[min(1, len(numeric_fields) - 1)]
        )
        _drop_stale("global_x_field", numeric_fields)
        st.session_state.setdefault("global_x_field", x_default)
        _drop_stale("global_y_field", numeric_fields)
        st.session_state.setdefault("global_y_field", y_default)

    # Highlight-column default + stale-clear run every time (even when the Text
    # styling popover isn't rendered this run) so a restored config on data with
    # no boolean columns can't carry a dangling pick.
    highlight_options = highlight_column_options(words)
    _drop_stale("global_highlight_column", highlight_options)
    if highlight_options:
        st.session_state.setdefault(
            "global_highlight_column",
            "is_in_aspan"
            if "is_in_aspan" in highlight_options
            else highlight_options[0],
        )
    return color_fields, numeric_fields, highlight_options


def _collect_viz_settings(
    trial_fixations: pd.DataFrame,
    words: Optional[pd.DataFrame],
    *,
    numeric_fields: Optional[List[str]] = None,
    highlight_options: Optional[List[str]] = None,
) -> Dict:
    """Build the viz-settings dict from session_state (pure — renders nothing).

    The single source of truth for the dict the figure builders consume, so the
    rendered controls (``sidebar_controls``) and the non-rendering reader
    (``viz_settings_from_state``) return identical shapes. Conditionally-applied
    fields (colour ranges, the highlight column, saccade arrows) are gated here
    exactly as the widgets gate them, so a stored value for an off layer doesn't
    leak into the figure. ``compare_style_a``/``_b`` are ``None``; the rendering
    path fills them in when the comparison toggle is on.
    """
    ss = st.session_state
    if highlight_options is None:
        highlight_options = highlight_column_options(words)

    show_fix = bool(ss.get("global_show_fix"))
    show_saccades = bool(ss.get("global_show_saccades"))
    show_heatmap = bool(ss.get("global_show_heatmap"))
    show_labels = bool(ss.get("global_show_labels"))
    color_by = ss.get("global_color_by")

    # Fixation colour range only applies when fixations are shown AND coloured by
    # a numeric column with a valid spread — mirror the widget's gate.
    fixation_color_range = None
    if (
        show_fix
        and color_by in trial_fixations.columns
        and pd.api.types.is_numeric_dtype(trial_fixations[color_by])
    ):
        cmin, cmax = trial_fixations[color_by].min(), trial_fixations[color_by].max()
        if pd.notna(cmin) and pd.notna(cmax):
            # Clamp to the same [floor(min), ceil(max)] bounds the rendered slider
            # uses, so the non-rendering reader can't leak a stale out-of-bounds
            # range (cmax_eff mirrors the slider's `cmax if cmax > cmin else +1`).
            lo = float(math.floor(cmin))
            hi = float(math.ceil(cmax))
            hi = hi if hi > lo else lo + 1.0
            fixation_color_range = _clamped_pair(
                ss.get("global_fixation_color_range"), lo, hi
            )

    # Heatmap colour range only applies for the duration-weighted heatmap.
    heatmap_range = None
    if (
        show_heatmap
        and ss.get("global_heatmap_metric") == "duration_ms"
        and "duration_ms" in trial_fixations.columns
    ):
        heat = trial_fixations["duration_ms"]
        if len(heat) > 0 and pd.notna(heat.min()) and pd.notna(heat.max()):
            lo = float(math.floor(heat.min()))
            hi = float(math.ceil(heat.max()))
            hi = hi if hi > lo else lo + 1.0
            heatmap_range = _clamped_pair(ss.get("global_heatmap_color_range"), lo, hi)

    # Fixation-index window (VIZ-7): a (start, end) tuple over `order_in_trial`,
    # or None for the full trial. Read straight from the slider's session key;
    # the rendering path clamps it to the trial's fixation count, and the
    # non-rendering Corpus reader simply leaves it None (it never windows).
    fix_index_range = None
    _fr = ss.get("single_fix_range")
    if isinstance(_fr, (tuple, list)) and len(_fr) == 2:
        fix_index_range = (int(_fr[0]), int(_fr[1]))

    # Highlight column only applies when Text is shown and a span style is active.
    critical_span_style = ss.get("global_critical_span_style", "Mark text")
    highlight_column = None
    if show_labels and critical_span_style != "None" and highlight_options:
        candidate = ss.get("global_highlight_column")
        highlight_column = candidate if candidate in highlight_options else None

    # Background colour comes from the Experimental Setup picker (read here so it
    # flows into the figure via viz_settings).
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    bg_choice = ss.get("global_bg_choice", bg_options[0])
    if bg_choice == "Custom…":
        background_color = ss.get("global_bg_custom", DEFAULT_BACKGROUND_COLOR)
    else:
        background_color = BACKGROUND_PRESETS.get(
            bg_choice, BACKGROUND_PRESETS[bg_options[0]]
        )

    return dict(
        show_words=bool(ss.get("global_show_words")),
        show_labels=show_labels,
        show_fix=show_fix,
        show_order=bool(ss.get("global_show_order")),
        show_saccades=show_saccades,
        # Arrows are a saccade sub-layer: never report them on when saccades off.
        show_saccade_arrows=bool(ss.get("global_show_saccade_arrows"))
        and show_saccades,
        show_heatmap=show_heatmap,
        # `or default` (not get-default) so a segmented_control deselect → None
        # falls back instead of propagating None into the figure builders.
        heatmap_style=ss.get("global_heatmap_style") or "Word boxes",
        show_raw_gaze=bool(ss.get("global_show_raw_gaze")),
        show_stimulus_image=bool(ss.get("global_show_stimulus_image")),
        color_by=color_by,
        heatmap_metric=ss.get("global_heatmap_metric") or "duration_ms",
        x_field=ss.get("global_x_field"),
        y_field=ss.get("global_y_field"),
        marker_size_range=tuple(ss.get("global_marker_size_range", (8, 24))),
        order_font_size=ss.get("global_order_font_size"),
        order_font_color=ss.get("global_order_font_color"),
        show_colorbars=bool(ss.get("global_show_colorbars")),
        fit_to_monitor=bool(ss.get("global_fit_to_monitor")),
        fixation_color_range=fixation_color_range,
        heatmap_range=heatmap_range,
        fixation_colorscale=ss.get("global_fixation_colorscale")
        or DEFAULT_FIXATION_COLORSCALE,
        heatmap_colorscale=ss.get("global_heatmap_colorscale")
        or DEFAULT_HEATMAP_COLORSCALE,
        critical_span_style=critical_span_style,
        highlight_column=highlight_column,
        saccade_color=ss.get("global_saccade_color", SACCADE_COLOR),
        saccade_style=ss.get("global_saccade_style") or "Solid",
        saccade_width=float(ss.get("global_saccade_width") or DEFAULT_SACCADE_WIDTH),
        hollow_fixations=bool(ss.get("global_hollow_fixations")),
        fixation_opacity=float(ss.get("global_fixation_opacity", 1.0)),
        fix_index_range=fix_index_range,
        highlight_text_color=ss.get("global_highlight_text_color"),
        text_color=ss.get("global_text_color", WORD_LABEL_COLOR),
        color_by_line=color_by == "line",
        # Fixation classification (PRE-2) + compare-overlay legend (CMP-2).
        fixation_flags=_collect_fixation_flags(),
        show_compare_legend=bool(ss.get("global_show_compare_legend")),
        span_border_color=ss.get("global_span_border_color", "#000000"),
        colorbar_orientation=ss.get("global_colorbar_orientation") or "Vertical",
        colorbar_tickangle=int(ss.get("global_colorbar_tickangle") or 0),
        colorbar_tickfont_size=int(ss.get("global_colorbar_tickfont_size") or 12),
        background_color=background_color,
        compare_style_a=None,
        compare_style_b=None,
    )


def viz_settings_from_state(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    words: Optional[pd.DataFrame] = None,
) -> Dict:
    """Resolve the viz-settings dict from session_state WITHOUT rendering widgets.

    Used by the views that consume the settings but don't host the controls — the
    Corpus Analysis figures and the Save & restore panel — so they stay in sync
    with the scanpath rail (which renders the actual widgets via
    ``sidebar_controls``) on whatever the user last set.
    """
    _, numeric_fields, highlight_options = _seed_viz_state(
        trial_fixations, base_font_size, words
    )
    return _collect_viz_settings(
        trial_fixations,
        words,
        numeric_fields=numeric_fields,
        highlight_options=highlight_options,
    )


def sidebar_controls(
    trial_fixations: pd.DataFrame,
    base_font_size: int,
    *,
    host=None,
    has_raw_gaze: bool = False,
    has_stimulus_image: bool = False,
    words: Optional[pd.DataFrame] = None,
    fix_range_fixations: Optional[pd.DataFrame] = None,
) -> Dict:
    """Render the visualization controls and return the resolved settings dict.

    Layout (cognitive-overload-conscious):
      1. Quick-view presets up top — one click for a focused picture.
      2. Layer on/off toggles. The layer's detailed styling lives in a per-layer
         popover shown only while the layer is on, so the panel stays compact
         (it now sits in a fixed rail beside the plot, not the scrollable
         sidebar) — fixations keep their primary "Color by" control inline.
      3. Global axes / colour bars in a collapsed expander.

    ``host`` is the container to render into; it defaults to ``st.sidebar`` for
    backwards compatibility, but the app passes the scanpath rail
    (``tabs.render_single_trial_tab``). The returned dict is built by
    ``_collect_viz_settings`` (shared with ``viz_settings_from_state``) so the
    rendered controls and the non-rendering readers can't drift.

    ``fix_range_fixations`` is the *selected trial's* fixations, used only to size
    the VIZ-7 fixation-index window slider (its max is that trial's fixation
    count). When omitted, the slider isn't rendered (e.g. the non-rendering
    Corpus reader, which never windows).
    """
    color_fields, numeric_fields, highlight_options = _seed_viz_state(
        trial_fixations, base_font_size, words
    )
    if not numeric_fields:
        st.error("No numeric fields found in fixations to map axes.")
        st.stop()

    # The keyed container is the spotlight-tour target
    # (`.st-key-tour_grp_viz_controls`). Values for controls not rendered this run
    # are read back from session_state by `_collect_viz_settings`, so the returned
    # dict always carries every key the figure builders depend on.
    viz = (host if host is not None else st.sidebar).container(
        key="tour_grp_viz_controls"
    )

    # --- Quick views ------------------------------------------------------
    # Two presets only (keeps the rail short); the Reading-order / Everything
    # presets are still reachable by toggling layers. The remaining preset keys
    # (`reading_order`, `everything`) stay in `_VIEW_PRESETS` for any deep link.
    viz.caption("Quick views")
    # Side by side to keep the rail short.
    _qv = viz.columns(2)
    _qv[0].button(
        "👁️ Scanpath",
        key="viz_view_scanpath",
        width="stretch",
        help="Fixations + saccades over the text — the core scanpath.",
        on_click=_apply_view_preset,
        args=("scanpath",),
    )
    _qv[1].button(
        "🔥 Heatmap",
        key="viz_view_heatmap",
        width="stretch",
        help="Fixation-density heatmap over the text, nothing else.",
        on_click=_apply_view_preset,
        args=("heatmap",),
    )

    viz.divider()

    # Each main layer is an `st.toggle`; the layer's detailed styling lives in a
    # per-layer popover shown only while the layer is on — so the rail shows just
    # the toggles (plus, for fixations, the primary "Color by" control), and the
    # fiddly knobs open in an overlay instead of growing the rail past the plot.
    # Values for off layers are read back from session_state by
    # `_collect_viz_settings`, so the returned dict always carries every key.

    # In compare mode the overlay uses flat per-scanpath colours, so the global
    # fixation/saccade appearance controls are dead — hide them and show only the
    # per-scanpath controls (CMP-4). Shared toggles (Fixation index, Direction
    # arrows) stay.
    comparing = bool(st.session_state.get("single_compare_toggle"))

    # --- Fixations --------------------------------------------------------
    show_fix = viz.toggle("**Fixations**", key="global_show_fix")
    if show_fix:
        with viz.popover("⚙️ Fixation style", width="stretch"):
            # The metric that maps to fixation HUE — applies in single AND compare
            # mode (in compare it colours both scanpaths by the metric; the
            # per-scanpath flat colour below is a separate field used as the A/B
            # marker outline).
            color_by = st.selectbox(
                "Color fixations by",
                options=color_fields,
                key="global_color_by",
                help="The metric mapped to fixation marker hue. Pick a column, or "
                "'line' to tint each fixation by the text line it lands on. In "
                "compare mode it colours both scanpaths by this metric.",
            )
            # Fixation-index window (VIZ-7): restrict which fixations (and their
            # saccades) are drawn on the main plot. Shared across single + compare
            # (it's a data window, not appearance), so it sits above the
            # appearance controls. The max is this trial's fixation count.
            _render_fix_range_slider(fix_range_fixations)
            if not comparing:
                st.slider(
                    "Size",
                    4,
                    40,
                    key="global_marker_size_range",
                    help="Fixation marker size (px).",
                )
                st.slider(
                    "Opacity",
                    min_value=0.1,
                    max_value=1.0,
                    step=0.05,
                    format="%.2f",
                    key="global_fixation_opacity",
                    help="Fixation marker opacity. Lower it so overlapping "
                    "fixations show through (1.0 = fully opaque).",
                )
            st.selectbox(
                "Colorscale",
                options=COLORSCALES,
                key="global_fixation_colorscale",
                help="Colour palette for fixation markers when colouring by "
                "numeric values.",
            )
            raw_cmin = (
                trial_fixations[color_by].min()
                if color_by in trial_fixations.columns
                and pd.api.types.is_numeric_dtype(trial_fixations[color_by])
                else None
            )
            raw_cmax = trial_fixations[color_by].max() if raw_cmin is not None else None
            if pd.notna(raw_cmin) and pd.notna(raw_cmax):
                # Integer bounds + step so the range reads as whole numbers
                # (durations, surprisal, … all read cleaner as ints); values
                # stay floats so a restored config on different data clamps in.
                cmin = float(math.floor(raw_cmin))
                cmax = float(math.ceil(raw_cmax))
                cmax_eff = cmax if cmax > cmin else cmin + 1.0
                _clamp_range("global_fixation_color_range", cmin, cmax_eff)
                st.session_state.setdefault(
                    "global_fixation_color_range", (cmin, cmax_eff)
                )
                st.slider(
                    "Fixation color range",
                    min_value=cmin,
                    max_value=cmax_eff,
                    step=1.0,
                    format="%d",
                    key="global_fixation_color_range",
                )
            show_order = st.checkbox("Fixation index", key="global_show_order")
            if show_order:
                st.color_picker(
                    "Index label color",
                    key="global_order_font_color",
                    help="Fixation-index label colour.",
                )
                st.slider(
                    "Index label size",
                    6,
                    72,
                    key="global_order_font_size",
                    help="Fixation-index label size (figure pixels; the plot is "
                    "then scaled to fit the column, so on-screen it is a touch "
                    "smaller). Default 10.",
                )
            # Fixation classification (PRE-2): short / long / out-of-bounds, each
            # highlight-or-discard with on-the-spot thresholds. Single-figure only,
            # so hidden in compare mode.
            if not comparing:
                _render_fixation_cleaning()
            # When comparing two trials, the per-scanpath fixation styling lives
            # here (under the Fixation settings), not in a separate panel.
            if comparing:
                _render_compare_fix_styles()

    # --- Saccades ---------------------------------------------------------
    show_saccades = viz.toggle("**Saccades**", key="global_show_saccades")
    if show_saccades:
        with viz.popover("⚙️ Saccade style", width="stretch"):
            st.checkbox(
                "Direction arrows",
                key="global_show_saccade_arrows",
                help="Draw an arrowhead on each saccade pointing in the gaze "
                "direction.",
            )
            if not comparing:
                st.color_picker(
                    "Saccade color",
                    key="global_saccade_color",
                    help="Colour of the saccade lines and direction arrows.",
                )
                st.segmented_control(
                    "Saccade line style",
                    options=list(SACCADE_DASH_OPTIONS.keys()),
                    key="global_saccade_style",
                    help="Line style for the saccade traces.",
                )
                st.slider(
                    "Saccade line width",
                    min_value=SACCADE_WIDTH_BOUNDS[0],
                    max_value=SACCADE_WIDTH_BOUNDS[1],
                    step=0.5,
                    format="%.1f px",
                    key="global_saccade_width",
                    help="Thickness of the saccade lines. Default 2.",
                )
            # Per-scanpath saccade styling for the two-trial comparison.
            if comparing:
                _render_compare_saccade_styles()

    # --- Text -------------------------------------------------------------
    show_labels = viz.toggle("**Text**", key="global_show_labels")
    if show_labels:
        with viz.popover("⚙️ Text & highlight", width="stretch"):
            # "Highlight a span" is an on/off toggle; the Mark-text / Mark-border
            # choice appears only when it's on (no "None" option). The canonical
            # value stays in `global_critical_span_style` ("Mark text" |
            # "Mark border" | "None") so deep-links / Share / restore are
            # unchanged — the toggle + mode widgets are derived from it each run,
            # and their callbacks write it back on interaction.
            canonical = st.session_state.get("global_critical_span_style", "Mark text")

            def _on_span_toggle():
                st.session_state["global_critical_span_style"] = (
                    st.session_state.get("global_highlight_span_mode", "Mark text")
                    if st.session_state["global_highlight_span_on"]
                    else "None"
                )

            def _on_span_mode():
                st.session_state["global_critical_span_style"] = st.session_state[
                    "global_highlight_span_mode"
                ]

            st.session_state["global_highlight_span_on"] = canonical != "None"
            if canonical in ("Mark text", "Mark border"):
                st.session_state["global_highlight_span_mode"] = canonical
            else:
                st.session_state.setdefault("global_highlight_span_mode", "Mark text")

            span_on = st.toggle(
                "Highlight a span",
                key="global_highlight_span_on",
                on_change=_on_span_toggle,
                help="Highlight a per-word span (e.g. the answer span) on the text.",
            )
            if span_on:
                # Which column defines the span first, then how to mark it.
                if highlight_options:
                    st.selectbox(
                        "Highlight words by",
                        options=highlight_options,
                        key="global_highlight_column",
                        help="Which per-word column to highlight on the text (words "
                        "where it is true). Defaults to the OneStop answer span.",
                    )
                critical_span_style = st.radio(
                    "Style",
                    options=["Mark text", "Mark border"],
                    horizontal=True,
                    key="global_highlight_span_mode",
                    on_change=_on_span_mode,
                    help="Mark text: colour the span's words. Mark border: draw a "
                    "thin outline around the span.",
                )
            else:
                critical_span_style = "None"
            st.session_state["global_critical_span_style"] = critical_span_style
            if critical_span_style == "Mark text":
                st.color_picker(
                    "Highlighted text color",
                    key="global_highlight_text_color",
                    help="Colour of the highlighted reading text (used with "
                    "'Mark text').",
                )
            elif critical_span_style == "Mark border":
                st.color_picker(
                    "Border color",
                    key="global_span_border_color",
                    help="Colour of the span outline (used with 'Mark border').",
                )

    # --- Heatmap ----------------------------------------------------------
    show_heatmap = viz.toggle("**Heatmap**", key="global_show_heatmap")
    if show_heatmap:
        with viz.popover("⚙️ Heatmap style", width="stretch"):
            # A radio (not segmented_control) so the active style is always shown
            # selected from the seeded default — segmented_control could render
            # with nothing selected on first open.
            st.radio(
                "Heatmap style",
                options=["Word boxes", "Interpolated"],
                horizontal=True,
                key="global_heatmap_style",
                help=(
                    "Word boxes: tint each word box by fixation count / duration. "
                    "Interpolated: a smooth Gaussian density over the fixations "
                    "themselves, independent of the word boxes (classic "
                    "eye-movement heatmap)."
                ),
            )
            st.selectbox(
                "Heatmap colorscale",
                options=COLORSCALES,
                help="Colour palette for the density heatmap overlay.",
                key="global_heatmap_colorscale",
            )
            heatmap_metric = st.selectbox(
                "Heatmap metric",
                options=["duration_ms", "counts"],
                help="Heatmap can be raw counts or weighted by fixation duration.",
                key="global_heatmap_metric",
            )
            heat_data = (
                trial_fixations["duration_ms"]
                if heatmap_metric == "duration_ms"
                and "duration_ms" in trial_fixations.columns
                else None
            )
            if (
                heat_data is not None
                and len(heat_data) > 0
                and pd.notna(heat_data.min())
                and pd.notna(heat_data.max())
            ):
                hmin = float(math.floor(heat_data.min()))
                hmax = float(math.ceil(heat_data.max()))
                hmax_eff = hmax if hmax > hmin else hmin + 1.0
                _clamp_range("global_heatmap_color_range", hmin, hmax_eff)
                st.session_state.setdefault(
                    "global_heatmap_color_range", (hmin, hmax_eff)
                )
                st.slider(
                    "Heatmap color range",
                    min_value=hmin,
                    max_value=hmax_eff,
                    step=1.0,
                    format="%d",
                    key="global_heatmap_color_range",
                    help="Min/max heatmap value mapped to the two ends of the "
                    "colorscale (the metric above — fixation duration or count; "
                    "for Interpolated, the smoothed density of those values). "
                    "Lower the max for more contrast; raise it to compress.",
                )

    # --- Bounding boxes / Stimulus image / Raw gaze (no extra styling) ----
    viz.toggle("**Bounding boxes**", key="global_show_words")
    viz.toggle(
        "**Stimulus image**",
        help="Show the rendered stimulus page as a background image (exact "
        "coordinates — sidesteps font issues for CJK / RTL scripts). "
        + ("" if has_stimulus_image else "(No stimulus image for this trial)"),
        disabled=not has_stimulus_image,
        key="global_show_stimulus_image",
    )
    viz.toggle(
        "**Raw gaze data**",
        help="Display millisecond-level gaze positions as small dots. "
        + ("" if has_raw_gaze else "(No raw gaze data loaded)"),
        disabled=not has_raw_gaze,
        key="global_show_raw_gaze",
    )

    # --- Axes & color bars (global plot settings, rarely changed) ---------
    axes = viz.expander("Axes & color bars", expanded=False)
    axes.toggle(
        "**Show full monitor**",
        key="global_fit_to_monitor",
        help="Frame the whole presentation monitor so the scanpath sits where it "
        "appeared on screen. Turn off to crop the view tightly to the data.",
    )
    show_colorbars = axes.checkbox("Show color bars", key="global_show_colorbars")
    if show_colorbars:
        axes.radio(
            "Color bar orientation",
            options=["Vertical", "Horizontal"],
            horizontal=True,
            key="global_colorbar_orientation",
            help="Vertical bar on the right, or a horizontal bar below the plot.",
        )
        axes.slider(
            "Tick label angle",
            min_value=-90,
            max_value=90,
            step=15,
            key="global_colorbar_tickangle",
            help="Rotate the color-bar tick labels (degrees).",
        )
        axes.slider(
            "Tick label size",
            min_value=6,
            max_value=20,
            key="global_colorbar_tickfont_size",
            help="Color-bar tick-label font size (px).",
        )
    axes.selectbox("X axis field", options=numeric_fields, key="global_x_field")
    axes.selectbox("Y axis field", options=numeric_fields, key="global_y_field")

    # Build the dict from session_state so it matches viz_settings_from_state
    # exactly; then fill in the per-scanpath comparison styling, shown only when
    # the Compare toggle (rail view-modes section) is on, so all styling sits here.
    settings = _collect_viz_settings(
        trial_fixations,
        words,
        numeric_fields=numeric_fields,
        highlight_options=highlight_options,
    )
    # The per-scanpath comparison styling is rendered inline under each layer's
    # popover (Fixation / Saccade) above; here we just collect it from the keys.
    if st.session_state.get("single_compare_toggle"):
        settings["compare_style_a"], settings["compare_style_b"] = (
            _collect_compare_styles()
        )
    return settings


# Cached option-list scans for the sidebar filter panel. These run on every
# rerun to populate the multiselects; caching them on a cheap frame fingerprint
# keeps them off the hot path on large corpora (full-column unique() scans).
@st.cache_data(show_spinner=False)
def _participant_options(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> List[str]:
    return sorted(
        set(_words["participant_id"].dropna().astype(str))
        | set(_fixations["participant_id"].dropna().astype(str))
    )


@st.cache_data(show_spinner=False)
def _column_unique_strs(_df: pd.DataFrame, column: str, cache_key) -> List[str]:
    if column not in _df.columns:
        return []
    # Drop missing values, including the literal "nan" a string-coerced optional
    # field leaves for NaN (e.g. ET2 readers with no recorded gender) — a "nan"
    # filter option would be meaningless.
    values = _df[column].dropna().astype(str).unique()
    return sorted(v for v in values if v.strip().lower() not in ("nan", "none", "<na>"))


@st.cache_data(show_spinner=False)
def _column_present_bools(_df: pd.DataFrame, column: str, cache_key) -> frozenset:
    if column not in _df.columns:
        return frozenset()
    return frozenset(
        bool(v) for v in pd.Series(_df[column]).dropna().astype(bool).unique()
    )


def _bool_metadata_filter(
    label: str,
    col: str,
    df: pd.DataFrame,
    true_label: str,
    false_label: str,
    key: str,
    host,
    on_change=None,
) -> None:
    """Render a friendly multiselect for a boolean metadata column.

    Rendering only — the narrowing value is derived from the widget key by
    ``_compute_trial_filters``. Renders nothing when the column is absent or has
    fewer than two classes."""
    if col not in df.columns:
        return
    present = _column_present_bools(df, col, cache_key=(frame_fingerprint(df), col))
    label_to_val = {true_label: True, false_label: False}
    options = [lbl for lbl, val in label_to_val.items() if val in present]
    if len(options) < 2:
        return
    _seed_filter_widget(key, options, options)
    host.multiselect(label, options=options, key=key, on_change=on_change)


def _bool_filter_narrowing(
    col: str, df: pd.DataFrame, true_label: str, false_label: str, key: str
) -> Optional[set]:
    """The set of raw bool values to keep for a boolean metadata column, read
    from its widget key — or None when absent / fewer than two classes / the user
    kept everything (no narrowing). The read-side twin of ``_bool_metadata_filter``."""
    if col not in df.columns:
        return None
    present = _column_present_bools(df, col, cache_key=(frame_fingerprint(df), col))
    label_to_val = {true_label: True, false_label: False}
    options = [lbl for lbl, val in label_to_val.items() if val in present]
    if len(options) < 2:
        return None
    chosen = st.session_state.get(key)
    if not chosen or set(chosen) == set(options):
        return None
    vals = {label_to_val[c] for c in chosen if c in label_to_val}
    return vals or None


# Friendly labels for well-known trial-level condition columns. Any other field
# the user picks as a filter just uses its column name + raw values.
_FILTER_FIELD_LABELS = {
    "question_preview": {
        "label": "Reading regime",
        "true": "Hunting",
        "false": "Gathering",
    },
    "repeated_reading_trial": {
        "label": "Reading number",
        "true": "Repeated",
        "false": "First",
    },
    "is_correct": {"label": "Answer", "true": "Correct", "false": "Incorrect"},
    "difficulty_level": {"label": "Difficulty"},
}

# Built-in sources (no wizard) auto-offer these known trial-level conditions when
# present; the Upload source uses the fields the user chose in the wizard.
_DEFAULT_FILTER_FIELDS = [
    "question_preview",
    "difficulty_level",
    "repeated_reading_trial",
    "is_correct",
    # MultiplEYE facets (present only when that corpus is loaded).
    "genre",
    "session",
    "is_practice",
]


_EMPTY_TRIAL_FILTERS: Dict = {
    "participants": None,
    "metadata": {},
    "favorites_only": False,
    "required_tags": [],
    "excluded_tags": [],
}


def read_trial_filters() -> Dict:
    """The trial-filter selections to apply this run.

    Computed last run by ``render_trial_filters`` and stashed in a *plain*
    session_state value (not a widget key), so it survives runs where the filter
    panel itself isn't rendered — e.g. when a non-Scanpath view is active under
    the sidebar nav. ``main()`` reads this *before* the tab renders, so filtering
    stays global even though the controls now live in the Trial Selection panel.
    """
    return dict(st.session_state.get("_trial_filters", _EMPTY_TRIAL_FILTERS))


# --- Trial summary chips (the "Field = Value" strip above the plot) ----------
_CHIP_TEXT_ID_COLS = (
    "unique_text_id",
    "text_id",
    "unique_paragraph_id",
    "paragraph_id",
)
# Sensible default chips: trial identity + the common OneStop conditions + the
# computed trial-level summary stats (which the chips replaced the Trial Info tab
# with). The "@"-prefixed keys are virtual fields computed per trial in
# `tabs._render_trial_condition_chips` (see SUMMARY_CHIP_FIELDS).
_CHIP_DEFAULT_CONDITIONS = [
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    # MultiplEYE facets + reader metadata (present only for that corpus).
    "genre",
    "session",
    "pp_age",
    "pp_gender",
]
# Virtual chip fields → label. These are computed per trial (not data columns),
# always trial-level, and folded in from the former Trial Info tab's summary.
SUMMARY_CHIP_FIELDS = {
    "@reading_time_s": "Total reading time (s)",
    "@word_count": "Number of words",
    "@fixation_count": "Number of fixations",
    "@in_text_fixations": "Fixations in word boxes",
}


def _trial_level_columns(words: pd.DataFrame, fixations: pd.DataFrame) -> set:
    """Columns that are constant within a trial (so a single chip value is
    meaningful), sampled from the first trial only — cheap, and trial-level-ness
    is essentially a property of the dataset, not the specific trial. A column
    counts as trial-level when it has ≤1 distinct value within that sample trial.
    """
    level: set = set()
    src = fixations if (fixations is not None and not fixations.empty) else words
    if (
        src is None
        or src.empty
        or "participant_id" not in src.columns
        or "trial_id" not in src.columns
    ):
        return level
    pid, tid = str(src["participant_id"].iloc[0]), str(src["trial_id"].iloc[0])
    for frame in (words, fixations):
        if (
            frame is None
            or frame.empty
            or "participant_id" not in frame.columns
            or "trial_id" not in frame.columns
        ):
            continue
        sub = frame[
            (frame["participant_id"].astype(str) == pid)
            & (frame["trial_id"].astype(str) == tid)
        ]
        if sub.empty:
            continue
        for col in sub.columns:
            if sub[col].nunique(dropna=True) <= 1:
                level.add(col)
    return level


def _chip_field_options(words, fixations, trial_level: set) -> List[str]:
    """Pickable chip fields: participant + a text id + the data's *trial-level*
    columns + the computed summary fields. Non-trial-level columns (per-word /
    per-fixation) are intentionally excluded — a single chip value for them would
    be misleading."""
    cols: List[str] = []

    def add(c: str) -> None:
        if c and c not in cols:
            cols.append(c)

    if "participant_id" in words.columns or "participant_id" in fixations.columns:
        add("participant_id")
    add(next((c for c in _CHIP_TEXT_ID_COLS if c in words.columns), ""))
    for c in list(words.columns) + list(fixations.columns):
        if c in trial_level:
            add(c)
    cols.extend(SUMMARY_CHIP_FIELDS)
    return cols


def _chip_option_label(col: str) -> str:
    """Display label for a chip-field option (identity / virtual / humanized)."""
    if col in SUMMARY_CHIP_FIELDS:
        return SUMMARY_CHIP_FIELDS[col]
    if col == "participant_id":
        return "Participant"
    if col in _CHIP_TEXT_ID_COLS:
        return "Text"
    return col.replace("_", " ").strip().capitalize()


def _default_chip_fields(available: List[str]) -> List[str]:
    text_col = next((c for c in _CHIP_TEXT_ID_COLS if c in available), None)
    wanted = (
        ["participant_id"]
        + ([text_col] if text_col else [])
        + _CHIP_DEFAULT_CONDITIONS
        + list(SUMMARY_CHIP_FIELDS)
    )
    return [f for f in wanted if f in available]


def render_trial_chip_picker(
    words: pd.DataFrame, fixations: pd.DataFrame, host
) -> None:
    """Render the inline **Edit chips** control: choose which ``Field = Value``
    chips appear above the scanpath and **drag to reorder** them (UX-1 / UX-1a).

    Two drag buckets — *Shown* (in display order) and *Available* — via
    ``streamlit_sortables.sort_items``: drag a field between buckets to show / hide
    it, and within *Shown* to reorder. The resulting order is written to the plain
    session key ``trial_chip_fields`` (read by ``tabs._render_trial_condition_chips``).

    Only *trial-level* fields are offered (constant within a trial) plus the
    computed summary stats, so a chip never shows a per-word column whose single
    value would mislead. The trial-level set is computed once (sampling the first
    trial) and cached per column-signature; a **Refresh** button recomputes it.
    Default seeded once (participant + text + common conditions + summary)."""
    # Cache the trial-level field set per column-signature (stable across trials /
    # filters within a dataset), recomputed on a dataset/column change or Refresh.
    signature = (tuple(words.columns), tuple(fixations.columns))
    cache = st.session_state.get("_trial_level_cache")
    if not cache or cache.get("signature") != signature:
        cache = {
            "signature": signature,
            "fields": _trial_level_columns(words, fixations),
        }
        st.session_state["_trial_level_cache"] = cache

    available = _chip_field_options(words, fixations, cache["fields"])
    if not available:
        return

    # Display labels must be unique to stay invertible: some fields humanize to the
    # same text (e.g. two text-id columns both read "Text"), so disambiguate.
    label_to_key: Dict[str, str] = {}
    key_to_label: Dict[str, str] = {}
    for key in available:
        base = _chip_option_label(key)
        label = base if base not in label_to_key else f"{base} ({key})"
        label_to_key[label] = key
        key_to_label[key] = label

    # Current selection/order, pruned to what's available + seeded once.
    if "trial_chip_fields" in st.session_state:
        st.session_state["trial_chip_fields"] = [
            f for f in st.session_state["trial_chip_fields"] if f in available
        ]
    st.session_state.setdefault("trial_chip_fields", _default_chip_fields(available))
    selected = list(st.session_state["trial_chip_fields"])
    hidden = [k for k in available if k not in selected]

    host.caption(
        "Drag fields between **Shown** and **Available**, and reorder within "
        "**Shown** — these chips appear above the scanpath."
    )
    buckets = [
        {
            "header": "Shown · drag to reorder",
            "items": [key_to_label[k] for k in selected],
        },
        {"header": "Available", "items": [key_to_label[k] for k in hidden]},
    ]
    with host:
        # Key varies with the field universe so the component re-mounts (rather than
        # keeping a stale drag order) when the dataset / columns change.
        result = sort_items(
            buckets,
            multi_containers=True,
            direction="vertical",
            key=f"trial_chip_sort_{abs(hash(signature))}",
        )
    shown_labels = result[0]["items"] if result else []
    st.session_state["trial_chip_fields"] = [
        label_to_key[lbl] for lbl in shown_labels if lbl in label_to_key
    ]
    host.button(
        "🔄 Refresh fields",
        key="trial_chip_refresh",
        help="Re-scan which fields are trial-level (if the offered list looks off "
        "for the current data).",
        on_click=lambda: st.session_state.pop("_trial_level_cache", None),
    )


def _seed_filter_widget(key: str, options: list, default: list) -> None:
    """Pre-seed a filter widget's state from the persistent mirror.

    Filter controls live in the Scanpath tab body, which doesn't render on every
    run (other views under the sidebar nav). Streamlit clears a not-rendered
    widget's key, so on return we re-seed it from ``_trial_filters_raw`` (the last
    selections), dropping any value no longer in ``options`` (e.g. after a dataset
    switch). Setting the key *before* the widget renders avoids the
    default-plus-session-state warning."""
    if key in st.session_state:
        return
    mirror = st.session_state.get("_trial_filters_raw", {})
    if key in mirror:
        kept = [v for v in mirror[key] if v in options]
        st.session_state[key] = kept if kept else list(default)
    else:
        st.session_state[key] = list(default)


def _filter_fields_for(words: pd.DataFrame, fixations: pd.DataFrame) -> list:
    """Trial-level condition columns to offer as filters (wizard-chosen for an
    upload, else the built-in defaults present in the data)."""
    filter_fields = st.session_state.get("wizard_filter_fields")
    if filter_fields is None:
        filter_fields = [
            c
            for c in _DEFAULT_FILTER_FIELDS
            if c in words.columns or c in fixations.columns
        ]
    return filter_fields


def _compute_trial_filters(words: pd.DataFrame, fixations: pd.DataFrame) -> Dict:
    """Derive the narrowing filter result from the live filter-widget values.

    Reads the widget keys (filter_participants / filter_<col> / filter_favorites /
    filter_req_tags / filter_exc_tags) — which Streamlit has already updated on the
    rerun the user changed a filter — so the filter applies on the SAME run. The
    on_change callbacks in ``render_trial_filters`` call this *before* the rerun;
    it also runs at the end of that function for no-change runs. Only narrowing
    selections feed the result.
    """
    result: Dict = {
        "participants": None,
        "metadata": {},
        "favorites_only": False,
        "required_tags": [],
        "excluded_tags": [],
    }
    parts = _participant_options(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )
    if len(parts) > 1:
        sel = st.session_state.get("filter_participants")
        if sel and len(sel) < len(parts):
            result["participants"] = list(sel)
    # Text narrowing (the "Narrow by → Text" multiselect). Like a categorical
    # condition, but the text id isn't in the condition list, so handle it here.
    text_field, text_frame = _text_field_and_frame(words, fixations)
    if text_field is not None:
        text_vals = _column_unique_strs(
            text_frame,
            text_field,
            cache_key=(frame_fingerprint(text_frame), text_field),
        )
        sel = st.session_state.get("filter_text_id")
        if sel and len(text_vals) > 1 and len(sel) < len(text_vals):
            result["metadata"][text_field] = set(sel)
    for col in _filter_fields_for(words, fixations):
        frame = words if col in words.columns else fixations
        if col not in frame.columns:
            continue
        spec = _FILTER_FIELD_LABELS.get(col, {})
        if pd.api.types.is_bool_dtype(frame[col]):
            vals = _bool_filter_narrowing(
                col,
                frame,
                spec.get("true", "Yes"),
                spec.get("false", "No"),
                f"filter_{col}",
            )
            if vals is not None:
                result["metadata"][col] = vals
        else:
            values = _column_unique_strs(
                frame, col, cache_key=(frame_fingerprint(frame), col)
            )
            sel = st.session_state.get(f"filter_{col}")
            if sel and len(values) > 1 and len(sel) < len(values):
                result["metadata"][col] = set(sel)
    result["favorites_only"] = bool(st.session_state.get("filter_favorites", False))
    result["required_tags"] = list(st.session_state.get("filter_req_tags") or [])
    result["excluded_tags"] = list(st.session_state.get("filter_exc_tags") or [])
    return result


def _text_field_and_frame(words: pd.DataFrame, fixations: pd.DataFrame):
    """The text/passage id column to narrow by + the frame it lives on (prefer
    fixations, where trials live). ``(None, fixations)`` when no text column."""
    for field in ("unique_text_id", "text_id"):
        if field in fixations.columns:
            return field, fixations
        if field in words.columns:
            return field, words
    return None, fixations


def render_narrow_by(
    words: pd.DataFrame, fixations: pd.DataFrame, *, text_host=None, part_host=None
) -> None:
    """Inline **Narrow by** multiselects — Text + Participant — that narrow the
    trial pool feeding the picker (the former Browse-by Text/Participant modes, now
    filters). They write the same ``filter_*`` keys the "More" popover uses and
    recompute via ``_compute_trial_filters``, so narrowing applies the same run.
    Start empty = no narrowing; pick values to narrow."""

    def _apply() -> None:
        st.session_state["_trial_filters"] = _compute_trial_filters(words, fixations)

    th = text_host if text_host is not None else st
    ph = part_host if part_host is not None else st

    text_field, text_frame = _text_field_and_frame(words, fixations)
    if text_field is not None:
        text_vals = _column_unique_strs(
            text_frame,
            text_field,
            cache_key=(frame_fingerprint(text_frame), text_field),
        )
        if len(text_vals) > 1:
            _seed_filter_widget("filter_text_id", text_vals, [])
            th.multiselect(
                "Text",
                options=text_vals,
                key="filter_text_id",
                on_change=_apply,
                placeholder="All texts",
                label_visibility="collapsed",
            )

    parts = _participant_options(
        words,
        fixations,
        cache_key=(frame_fingerprint(words), frame_fingerprint(fixations)),
    )
    if len(parts) > 1:
        _seed_filter_widget("filter_participants", parts, [])
        ph.multiselect(
            "Participant",
            options=parts,
            key="filter_participants",
            on_change=_apply,
            placeholder="All participants",
            label_visibility="collapsed",
        )


def render_trial_filters(
    words: pd.DataFrame, fixations: pd.DataFrame, *, host=None
) -> Dict:
    """Render the trial-filter controls into ``host`` and persist the selections.

    Lets the user narrow the trial pool by participant and by categorical
    condition (Hunting/Gathering, difficulty, first/repeated reading,
    correctness) plus annotation state (favorites / tags). Renders into ``host``
    (the Trial Selection panel; defaults to the sidebar). The narrowing result is
    derived by ``_compute_trial_filters`` and stashed in session_state
    (`_trial_filters`); each widget's ``on_change`` recomputes it *before* the
    rerun so ``main()``'s ``read_trial_filters`` applies the change on the same
    run. The persisted value also survives runs where this panel isn't rendered
    (a non-Scanpath view under the sidebar nav).
    """
    if host is None:
        host = st.sidebar

    def _apply() -> None:
        st.session_state["_trial_filters"] = _compute_trial_filters(words, fixations)

    # Text + Participant narrowing now lives in the inline "Narrow by" row
    # (``render_narrow_by``); this popover keeps the condition + annotation filters.
    for col in _filter_fields_for(words, fixations):
        frame = words if col in words.columns else fixations
        if col not in frame.columns:
            continue
        spec = _FILTER_FIELD_LABELS.get(col, {})
        label = spec.get("label", col.replace("_", " ").strip().title())
        if pd.api.types.is_bool_dtype(frame[col]):
            _bool_metadata_filter(
                label,
                col,
                frame,
                spec.get("true", "Yes"),
                spec.get("false", "No"),
                f"filter_{col}",
                host,
                on_change=_apply,
            )
        else:
            values = _column_unique_strs(
                frame, col, cache_key=(frame_fingerprint(frame), col)
            )
            if len(values) > 1:
                _seed_filter_widget(f"filter_{col}", values, values)
                host.multiselect(
                    label, options=values, key=f"filter_{col}", on_change=_apply
                )

    host.markdown("**By annotation**")
    if "filter_favorites" not in st.session_state:
        st.session_state["filter_favorites"] = bool(
            st.session_state.get("_trial_filters_raw", {}).get(
                "filter_favorites", False
            )
        )
    host.checkbox("⭐ Favorites only", key="filter_favorites", on_change=_apply)
    tags = known_tags()
    if tags:
        _seed_filter_widget("filter_req_tags", tags, [])
        host.multiselect(
            "With any of these tags",
            options=tags,
            key="filter_req_tags",
            on_change=_apply,
        )
        _seed_filter_widget("filter_exc_tags", tags, [])
        host.multiselect(
            "Excluding tags",
            options=tags,
            key="filter_exc_tags",
            on_change=_apply,
            help="e.g. hide everything tagged 'To exclude'.",
        )

    # Mirror the rendered widget values so _seed_filter_widget can restore them on
    # a run where this panel isn't shown (the keys get cleared); then publish the
    # derived result for read_trial_filters (covers no-change runs).
    keys = [
        "filter_participants",
        "filter_text_id",
        "filter_req_tags",
        "filter_exc_tags",
    ] + [f"filter_{c}" for c in _filter_fields_for(words, fixations)]
    st.session_state["_trial_filters_raw"] = {
        k: st.session_state[k] for k in keys if k in st.session_state
    }
    result = _compute_trial_filters(words, fixations)
    st.session_state["_trial_filters"] = result
    return result
