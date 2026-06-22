"""Scanpath Studio Streamlit app.

This is the main entry point for the Streamlit application that visualizes
eye-tracking scanpaths over text.

Architecture:
    - Entry point: main() function configures Streamlit and orchestrates the UI
    - Data flow: CSV upload → schema inference → normalization → filtering → plotting
    - UI structure: Sidebar controls + tabbed views (Visualization, Generations,
      Data Inspection, Bulk Export)

Data Pipeline:
    1. Load raw CSVs (words + fixations + optional raw gaze)
    2. Infer schema via candidate column matching
    3. Normalize to canonical column names
    4. Apply participant/trial/text filters
    5. Build trial combinations for selection
    6. Render visualizations with user-controlled settings

Usage:
    # Development mode (watch for changes):
    $ streamlit run scanpath_studio/app.py

    # Package mode:
    $ python -m scanpath_studio
    # or
    $ scanpath-studio
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

# Allow running via `streamlit run scanpath_studio/app.py` by adding the
# repository root to sys.path when executed as a script instead of a package.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scanpath_studio.annotations import (
    filter_keys,
    restore_records,
)
from scanpath_studio.constants import (
    BACKGROUND_PRESETS,
    COLORSCALES,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIGURE_SIZE,
    DEFAULT_LINE_SPACING,
    FONT_FAMILY,
    SACCADE_DASH_OPTIONS,
    WORD_LABEL_COLOR,
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    NONE_OPTION,
    RAW_GAZE_FIELD_SPECS,
    WORD_FIELD_SPECS,
    _OUT_OF_TEXT_MARKERS,
    color_field_options,
    column_mapping_ui,
    data_dictionary_help_text,
    numeric_field_options,
    read_trial_filters,
    render_trial_chip_picker,
    viz_settings_from_state,
)
from scanpath_studio.data import (
    FILE_PART_PREFIX,
    FIX_OPTIONAL_FIELDS,
    PARTICIPANT_CANDIDATES,
    SOURCE_FILE_COLUMN,
    WORD_OPTIONAL_FIELDS,
    aggregate_char_boxes,
    categorize_columns,
    compute_canvas_size,
    compute_keep_columns,
    default_filters,
    empty_fixations_frame,
    empty_words_frame,
    extract_columns_from_source_file,
    filter_data,
    filter_raw_gaze,
    filter_to_keys,
    filter_trials,
    frame_fingerprint,
    harmonize_frames,
    infer_raw_gaze_schema,
    load_onestop_server_bundle,
    load_sample_data,
    load_sample_raw_gaze,
    normalize_fixations,
    normalize_raw_gaze,
    normalize_words,
    onestop_data_dir,
    onestop_full_bundle_exists,
    pick_column,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    read_table,
    read_tables,
    source_file_regex_collisions,
    split_source_file,
    trial_id_series,
    trial_mapping_columns,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from scanpath_studio.debug_log import install_log_capture, render_debug_panel
from scanpath_studio.styles import get_app_css
from scanpath_studio.tabs import (
    _build_figure_settings,
    _collect_column_mapping,
    _render_save_restore_expander,
    render_corpus_analysis_tab,
    render_data_inspection_tab,
    render_single_trial_tab,
)
from scanpath_studio.utils import extract_trial
from scanpath_studio.tour import (
    maybe_show_welcome_tour,
    maybe_show_wizard_guide,
    render_spotlight_tour,
    render_spotlight_wizard_guide,
    render_tour_replay_button,
    render_wizard_guide_button,
    spotlight_tour_pending,
)

from scanpath_studio.utils import build_combo_options

# Re-exported under a private alias so tests can import them from `app`; keep the
# F401 silence (they're not used by app.py itself).
from scanpath_studio.utils import (  # noqa: F401
    build_comparison_options as _build_comparison_options,
)
from scanpath_studio.utils import (  # noqa: F401
    friendly_trial_label as _friendly_trial_label,
)

UPLOAD_CHOICE = "Upload tables"
DEMO_CHOICE = "Bundled Demo"
# A tiny, fully-specified synthetic trial (scanpath_studio.synthetic)
# with known ground-truth reading measures — handy for sanity-checking the viz
# against documented expected values.
SYNTHETIC_CHOICE = "Synthetic test trial"
# Known public corpora with ready-made loaders (scanpath_studio.datasets) —
# datasets that can't be mapped through the generic Upload flow (e.g. PoTeC's
# trial/word ids live in filenames and its fixation coordinates come from a
# separate character-AoI file). Selecting this source reveals a dataset picker
# backed by PUBLIC_DATASET_REGISTRY (defined below the loader functions);
# adding a corpus = one registry entry + one loader.
PUBLIC_DATASETS_CHOICE = "Public datasets"
# Default PoTeC location + a small default subset so the first load is quick.
POTEC_DEFAULT_DIR = "data/PoTeC"
POTEC_TEXT_IDS = [f"{d}{i}" for d in ("b", "p") for i in range(6)]
# Default MultiplEYE location (the read-only ZH/Chinese Zurich sample).
MULTIPLEYE_DEFAULT_DIR = "data/MultiplEYE_ZH_CH_Zurich_1_2025"


def public_datasets_enabled() -> bool:
    """Whether the "Public datasets" source (PoTeC, MultiplEYE) is offered.

    Enabled by default; set ``SCANPATH_PUBLIC_DATASETS=0`` (or ``false`` / ``no``)
    to hide it. Read at call time so tests can toggle the env var."""
    raw = os.environ.get("SCANPATH_PUBLIC_DATASETS", "").strip().lower()
    return raw not in ("0", "false", "no")


# Server-side OneStop lacclab bundle. Only offered when $ONESTOP_DATA_DIR is
# set; selected automatically when the page is opened with `?source=onestop`
# in the URL. See data.load_onestop_server_bundle().
ONESTOP_CHOICE = "OneStop server bundle"

# URL query-param → session_state key map for the deep-link API. Used by
# `_apply_url_preset()` to preset widgets when the page is opened from an
# external tool with a deep link.
#
# Selection prefixes — every selectable tab (Scanpath Visualization,
# Generations, …) renders its own `select_trial` with a different `key_prefix`,
# so a URL deep link has to seed all of them or only the first tab lands on
# the requested trial. Keep this list in sync with the `key_prefix=` values
# passed to `select_trial` in tabs.py.
_SELECTION_PREFIXES = ("single", "multi")


def _coerce_bool(v) -> bool:
    return str(v).lower() not in {"0", "false", "no"}


def _parse_int_range(v) -> tuple:
    a, b = (int(float(x)) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


def _parse_float_range(v) -> tuple:
    a, b = (float(x) for x in str(v).split(",")[:2])
    return (min(a, b), max(a, b))


# --- Share-link parameter groups -------------------------------------------
# The Share link round-trips the *entire* Visualization-controls panel (plus the
# text/background settings from Experimental Setup), not just a handful of
# toggles. Each group maps a short URL key → the session_state key it reads/writes.
# `_build_share_query` (write) and `_apply_url_preset` (read) both iterate these,
# so the two sides can't drift. Data-dependent fields (color ranges, highlight
# column, axis/color-by fields) self-heal on load via the sidebar's _drop_stale /
# _clamp_range, so a link opened on a different trial degrades gracefully.
_SHARE_TOGGLE_PARAMS = {  # bool → "1"/"0"
    "show_words": "global_show_words",
    "show_labels": "global_show_labels",
    "show_fixations": "global_show_fix",
    "show_order": "global_show_order",
    "show_saccades": "global_show_saccades",
    "show_saccade_arrows": "global_show_saccade_arrows",
    "show_heatmap": "global_show_heatmap",
    "show_raw_gaze": "global_show_raw_gaze",
    "show_colorbars": "global_show_colorbars",
    "highlight_out_of_text": "global_highlight_out_of_text",
    "hollow_fixations": "global_hollow_fixations",
    "scale_text_to_boxes": "global_scale_text_to_boxes",
}
_SHARE_VALUE_PARAMS = {  # string / choice / color → str (emitted only when set)
    "color_by": "global_color_by",
    "heatmap_style": "global_heatmap_style",
    "heatmap_metric": "global_heatmap_metric",
    "critical_span_style": "global_critical_span_style",
    "highlight_column": "global_highlight_column",
    "x_field": "global_x_field",
    "y_field": "global_y_field",
    "saccade_style": "global_saccade_style",
    "fixation_colorscale": "global_fixation_colorscale",
    "heatmap_colorscale": "global_heatmap_colorscale",
    "saccade_color": "global_saccade_color",
    "order_font_color": "global_order_font_color",
    "text_color": "global_text_color",
    "highlight_text_color": "global_highlight_text_color",
    "bg_choice": "global_bg_choice",
    "bg_custom": "global_bg_custom",
    "font_family": "global_font_family",
}
_SHARE_INT_PARAMS = {"order_font_size": "global_order_font_size"}
_SHARE_FLOAT_PARAMS = {"line_spacing": "global_line_spacing"}
_SHARE_INT_RANGE_PARAMS = {"marker_size_range": "global_marker_size_range"}
_SHARE_FLOAT_RANGE_PARAMS = {
    "fixation_color_range": "global_fixation_color_range",
    "heatmap_color_range": "global_heatmap_color_range",
}

_URL_PRESETS = {
    # Booleans (read side of _SHARE_TOGGLE_PARAMS) + the legacy aliases.
    "hide_fixation_numbers": ("global_show_order", lambda v: not _coerce_bool(v)),
    **{k: (s, _coerce_bool) for k, s in _SHARE_TOGGLE_PARAMS.items()},
    # Strings / choices / colors.
    **{k: (s, str) for k, s in _SHARE_VALUE_PARAMS.items()},
    # Numbers + ranges.
    **{k: (s, int) for k, s in _SHARE_INT_PARAMS.items()},
    **{k: (s, float) for k, s in _SHARE_FLOAT_PARAMS.items()},
    **{k: (s, _parse_int_range) for k, s in _SHARE_INT_RANGE_PARAMS.items()},
    **{k: (s, _parse_float_range) for k, s in _SHARE_FLOAT_RANGE_PARAMS.items()},
}

# Widget bounds for the URL-restorable params that feed a min/max-bounded widget
# (slider / number_input). A hand-crafted link with an out-of-range value would
# otherwise crash the widget on render — Streamlit raises when a Session-State
# value falls outside the widget's range. Clamp on the way in. (Data-dependent
# colour ranges aren't here — the sidebar's `_clamp_range` handles those against
# the live data.)
_URL_BOUNDED = {
    "global_line_spacing": (1.0, 10.0),
    "global_order_font_size": (6, 72),
    "global_marker_size_range": (4, 40),
}


def _clamp_url_value(state_key: str, value):
    """Clamp a deep-linked value to its widget bounds (scalars and 2-tuples)."""
    bounds = _URL_BOUNDED.get(state_key)
    if bounds is None:
        return value
    lo, hi = bounds
    if isinstance(value, (tuple, list)) and len(value) == 2:
        a, b = max(lo, min(value[0], hi)), max(lo, min(value[1], hi))
        return (min(a, b), max(a, b))
    return max(lo, min(value, hi))


# data_choice → ?source= value, for the built-in sources a URL can fully rebuild.
# Sources absent here (uploaded tables, stored datasets, public corpora) can't be
# reconstructed from a link — the Share panel warns and shares the view settings
# only. Mirrors the `source` handling in `main()`.
_SHAREABLE_SOURCES = {
    DEMO_CHOICE: "demo",
    ONESTOP_CHOICE: "onestop",
    SYNTHETIC_CHOICE: "synthetic",
}


def _apply_url_preset() -> Optional[str]:
    """Read `st.query_params` and preset Streamlit session state for deep links.

    Returns the URL-requested `source` ("onestop"/"demo"/"upload") or `None`.
    Call this at the very top of `main()` — before any widgets render — so
    session_state values are picked up as the widgets' initial values.

    URL schema (all params optional):
        ?source=onestop          → force "OneStop server bundle" data source
                                   (also demo / synthetic / upload — see main())
        &participant=p001        → preselect participant (Participant mode)
        &trial=37                → preselect trial_index slider
        &trial_id=p001_3_Adv     → land on this exact trial id, any picker mode
                                   (applied after combos build — see
                                   _apply_url_trial_selection; emitted by Share)
        &tab=animation           → pre-tick the Animate toggle (legacy; there's
                                   no separate Animated Scanpath tab anymore)
        &heatmap_colorscale=Greens
        &hide_fixation_numbers=1
        &show_saccades=1
        &show_heatmap=1
        ...etc — see _URL_PRESETS above

    Bonus side-effect: when any colorscale is set via URL, also forces the
    "Advanced styling" sidebar expander open so the value is visible/editable.

    External tools can deep-link into this app via the URL schema above to
    land on a specific trial with the reviewer's preferred viz settings.
    """
    qp = st.query_params
    if not qp:
        return None

    # Seed selection state for every `select_trial` host (the prefixes in
    # `_SELECTION_PREFIXES`). `?participant=` + `?trial=` map onto Participant mode
    # with the matching participant / slider value. Seeding every prefix keeps a
    # non-first picker from defaulting to "Trial" mode and landing on the
    # alphabetically-first trial instead of the deep-linked one.
    if "participant" in qp or "trial" in qp:
        if "participant" in qp:
            # Capture the deep-link participant ONCE, in a dedicated key the live
            # selector never overwrites. The OneStop loader keys its per-pid shard
            # fast-path off this — so it loads one pid for an embedded review deep
            # link, while ordinary in-app participant switching just *filters*
            # already-loaded data instead of re-invoking the loader.
            st.session_state.setdefault("_deeplink_participant", str(qp["participant"]))
        for prefix in _SELECTION_PREFIXES:
            st.session_state.setdefault(f"{prefix}_select_trial_mode", "Participant")
            if "participant" in qp:
                st.session_state.setdefault(
                    f"{prefix}_participant", str(qp["participant"])
                )
            if "trial" in qp:
                try:
                    st.session_state.setdefault(f"{prefix}_slider", int(qp["trial"]))
                except (ValueError, TypeError):
                    st.warning(f"Ignored bad URL param ?trial={qp['trial']!r}")

    for url_key, (state_key, coerce) in _URL_PRESETS.items():
        if url_key not in qp:
            continue
        raw = qp[url_key]
        try:
            value = coerce(raw)
        except (ValueError, TypeError):
            st.warning(f"Ignored bad URL param ?{url_key}={raw!r}")
            continue
        # Clamp bounded widgets so a hand-crafted out-of-range link can't crash
        # the slider / number_input on render.
        value = _clamp_url_value(state_key, value)
        st.session_state.setdefault(state_key, value)

    # Heatmap / fixation colorscale only render under the Advanced expander —
    # auto-open it so the URL value is exposed in the sidebar.
    if "heatmap_colorscale" in qp or "fixation_colorscale" in qp:
        st.session_state.setdefault("global_advanced", True)

    # Animation is now a checkbox in the Scanpath Visualization tab (no separate
    # tab), so a legacy `?tab=animation` deep link just pre-ticks it.
    if (qp.get("tab") or "").lower() == "animation":
        st.session_state.setdefault("single_animate", True)

    source = qp.get("source")
    return source.lower() if source else None


# plot-config layer key → viz-control session_state key. The inverse of the
# `layers` block written by `tabs._render_plot_config_expander`.
_PLOT_CONFIG_LAYER_KEYS = {
    "words": "global_show_words",
    "word_labels": "global_show_labels",
    "fixations": "global_show_fix",
    "order_labels": "global_show_order",
    "saccades": "global_show_saccades",
    "saccade_arrows": "global_show_saccade_arrows",
    "heatmap": "global_show_heatmap",
    "raw_gaze": "global_show_raw_gaze",
    "stimulus_image": "global_show_stimulus_image",
    "full_monitor": "global_fit_to_monitor",
}
# Static widget bounds, mirrored from controls.sidebar_controls /
# render_sidebar_canvas_controls, so a restored value is clamped to a range the
# widget will accept.
_CANVAS_BOUNDS = (100, 10000)
_FONT_BOUNDS = (6, 72)
_MARKER_BOUNDS = (4, 40)


def _restore_selection(
    selection: dict, combos: pd.DataFrame, key_prefix: str = "single"
) -> bool:
    """Best-effort: point a tab's trial picker at the saved ``(participant,
    trial)``. Returns True when a matching trial is found in the current
    (filtered) data. Mirrors the key scheme of ``utils.select_trial`` for the
    given ``key_prefix`` — including its composite vs. single-dropdown branch —
    so the seeded keys land on the right selectors.

    The trial id is sufficient on its own: a missing/blank participant (e.g. a
    ``?trial_id=`` link with no ``?participant=``) falls through to the trial-id-
    alone match below, so the picker still lands on the trial."""
    pid = selection.get("participant_id")
    tid = selection.get("trial_id")
    if tid in (None, "") or combos.empty:
        return False
    pid, tid = str(pid), str(tid)
    match = combos[
        (combos["participant_id"].astype(str) == pid)
        & (combos["trial_id"].astype(str) == tid)
    ]
    if match.empty:  # participant absent/blank or filtered out — try trial id alone
        match = combos[combos["trial_id"].astype(str) == tid]
    if match.empty:
        return False
    row = match.iloc[0]
    st.session_state[f"{key_prefix}_select_trial_mode"] = "Trial"
    composite_cols = [
        c
        for c in (st.session_state.get("_composite_trial_columns") or [])
        if c in combos.columns
    ]
    if len(composite_cols) >= 2:
        for col in composite_cols:
            st.session_state[f"{key_prefix}_composite_{col}"] = str(row[col])
        st.session_state[f"{key_prefix}_composite_reading"] = str(row["trial_id"])
    else:
        # None/Trial mode renders a single dropdown keyed `<prefix>_trial_id`
        # whose *options* are the trial_field values (`unique_trial_id` when
        # present), so seed that one key with this row's option value — not a
        # `<prefix>_<trial_field>` key, which no widget reads.
        trial_field = (
            "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
        )
        st.session_state[f"{key_prefix}_trial_id"] = str(row[trial_field])
    return True


def _apply_url_trial_selection(combos: pd.DataFrame) -> None:
    """Apply a ``?trial_id=`` deep link to the trial picker — exactly once.

    Unlike ``?trial=`` (a slider *index*, seeded before any widget renders in
    ``_apply_url_preset``), ``?trial_id=`` carries the canonical trial id, so it
    lands on the exact trial regardless of which picker mode produced the share
    link — but it needs the built ``combos``, so it runs from ``main()`` after
    they exist. Reuses ``_restore_selection`` (the same seeding the plot-config
    restore uses), seeding *every* selection prefix so non-first tabs land on the
    trial too (mirrors the ``_SELECTION_PREFIXES`` loop in ``_apply_url_preset``).
    The Share button emits this param; see ``_build_share_query``.
    """
    if st.session_state.get("_url_trial_applied"):
        return
    trial_id = st.query_params.get("trial_id")
    if not trial_id:
        return
    selection = {
        "participant_id": st.query_params.get("participant"),
        "trial_id": trial_id,
    }
    # Stamp the once-flag only after the trial is actually found, so a rerun
    # where `combos` is still empty/partial (e.g. the OneStop shard is mid-load)
    # retries on the next rerun instead of losing the deep link. `_restore_selection`
    # only writes when it matches, so retrying never clobbers manual navigation.
    # Materialize (not a short-circuiting any()) so EVERY prefix is seeded, not
    # just up to the first match.
    results = [
        _restore_selection(selection, combos, key_prefix=prefix)
        for prefix in _SELECTION_PREFIXES
    ]
    if any(results):
        st.session_state["_url_trial_applied"] = True


def _seed_column_mapping(mapping, *, overwrite: bool = False) -> None:
    """Seed the ``col_map_*`` session keys from a saved config's ``column_mapping``
    so a restored config pre-fills the wizard mapping + kept-field choices (and
    the user skips re-mapping). Stale values that don't match the current data are
    tolerated by the mapping widgets (selectbox index fallback / multiselect
    cleanup). Old configs used ``*_paragraph`` keys (now ``*_text_id``) — these
    are translated for backward compatibility.

    ``overwrite`` controls the write semantics. The plot-config restore runs
    *before* any widget renders, so ``setdefault`` (overwrite=False) is correct —
    it never clobbers a value a later widget will set. The wizard's "Restore a
    saved setup" step, however, runs *after* the mapping widgets were created on a
    previous render, so those keys already exist; ``setdefault`` would be a no-op
    and the restore would silently do nothing. There, pass ``overwrite=True`` so
    an explicit restore wins (the step reruns afterwards, and it runs before the
    mapping widgets re-instantiate, so writing the keys is safe)."""
    if not isinstance(mapping, dict):
        return
    for raw_key, value in mapping.items():
        if (
            not isinstance(raw_key, str)
            or not raw_key.startswith("col_map_")
            or raw_key.endswith("_upload")
        ):
            continue
        key = raw_key
        if key.endswith("_paragraph"):
            key = key[: -len("_paragraph")] + "_text_id"
        if overwrite:
            st.session_state[key] = value
        else:
            st.session_state.setdefault(key, value)


def _restore_plot_config(
    config: dict, combos: pd.DataFrame, fixations: pd.DataFrame
) -> Tuple[int, list]:
    """Seed session_state from an uploaded plot-config dict so the sidebar
    widgets render with the saved settings. Returns ``(applied, skipped)`` where
    ``skipped`` lists human-readable labels that didn't fit the current data.

    Inverse of the config built in ``tabs._render_plot_config_expander``. Runs
    before any widget renders (see ``_apply_uploaded_plot_config``); data-
    dependent fields are validated against the loaded data and skipped when they
    don't apply, so a config shared with a different dataset degrades gracefully."""
    applied = 0
    skipped: list = []

    def section(name):
        """A config sub-section as a dict — empty if absent or the wrong type,
        so a hand-edited upload with a malformed section can't crash the rest."""
        value = config.get(name)
        return value if isinstance(value, dict) else {}

    def number(value):
        """Coerce a JSON scalar to float, or None for a non-numeric upload."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def put(key, value):
        nonlocal applied
        st.session_state[key] = value
        applied += 1

    def put_valid(valid, key, value, skip_label):
        """Apply ``value`` when ``valid``, else record ``skip_label``."""
        if valid:
            put(key, value)
        else:
            skipped.append(skip_label)

    def put_int(value, key, lo, hi, skip_label):
        """Apply an int clamped to ``[lo, hi]``; skip a non-numeric upload."""
        n = number(value)
        if n is None:
            skipped.append(skip_label)
        else:
            put(key, max(lo, min(int(n), hi)))

    # Re-apply the saved column mapping + kept-field choices (so restoring a
    # config skips re-mapping). Seeded before the mapping widgets render.
    _seed_column_mapping(config.get("column_mapping"))

    layers = section("layers")
    for cfg_key, state_key in _PLOT_CONFIG_LAYER_KEYS.items():
        if cfg_key in layers:
            put(state_key, bool(layers[cfg_key]))

    coloring = section("coloring")
    if "heatmap_style" in coloring:
        style = coloring["heatmap_style"]
        put_valid(
            style in ("Word boxes", "Interpolated"),
            "global_heatmap_style",
            style,
            "heatmap style",
        )
    if "color_by" in coloring:
        put_valid(
            coloring["color_by"] in color_field_options(fixations),
            "global_color_by",
            coloring["color_by"],
            "color-by field",
        )
    if "heatmap_metric" in coloring:
        put_valid(
            coloring["heatmap_metric"] in ("duration_ms", "counts"),
            "global_heatmap_metric",
            coloring["heatmap_metric"],
            "heatmap metric",
        )
    if "show_colorbars" in coloring:
        put("global_show_colorbars", bool(coloring["show_colorbars"]))
    for cfg_key, state_key in (
        ("fixation_colorscale", "global_fixation_colorscale"),
        ("heatmap_colorscale", "global_heatmap_colorscale"),
    ):
        val = coloring.get(cfg_key)
        if val is not None:
            put_valid(val in COLORSCALES, state_key, val, cfg_key.replace("_", " "))
    sac = coloring.get("saccade_color")
    if isinstance(sac, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sac):
        put("global_saccade_color", sac)
    if "saccade_style" in coloring:
        put_valid(
            coloring["saccade_style"] in SACCADE_DASH_OPTIONS,
            "global_saccade_style",
            coloring["saccade_style"],
            "saccade line style",
        )
    if "hollow_fixations" in coloring:
        put("global_hollow_fixations", bool(coloring["hollow_fixations"]))
    co = coloring.get("colorbar_orientation")
    if co is not None:
        put_valid(
            co in ("Vertical", "Horizontal"),
            "global_colorbar_orientation",
            co,
            "color bar orientation",
        )
    if "colorbar_tickangle" in coloring:
        put_int(
            coloring["colorbar_tickangle"],
            "global_colorbar_tickangle",
            -90,
            90,
            "color bar tick angle",
        )
    if "colorbar_tickfont_size" in coloring:
        put_int(
            coloring["colorbar_tickfont_size"],
            "global_colorbar_tickfont_size",
            6,
            20,
            "color bar tick size",
        )
    # Range sliders only render when colour bars are on; store them anyway —
    # the widgets clamp to the current data via `controls._clamp_range`.
    for cfg_key, state_key, label in (
        ("fixation_range", "global_fixation_color_range", "fixation color range"),
        ("heatmap_range", "global_heatmap_color_range", "heatmap color range"),
    ):
        rng = coloring.get(cfg_key)
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            lo, hi = number(rng[0]), number(rng[1])
            put_valid(lo is not None and hi is not None, state_key, (lo, hi), label)

    sizing = section("sizing")
    marker = sizing.get("marker_size_range")
    if isinstance(marker, (list, tuple)) and len(marker) == 2:
        lo, hi = number(marker[0]), number(marker[1])
        if lo is None or hi is None:
            skipped.append("marker size range")
        else:
            lo = max(_MARKER_BOUNDS[0], min(int(lo), _MARKER_BOUNDS[1]))
            hi = max(_MARKER_BOUNDS[0], min(int(hi), _MARKER_BOUNDS[1]))
            put("global_marker_size_range", (min(lo, hi), max(lo, hi)))
    if "order_font_size" in sizing:
        put_int(
            sizing["order_font_size"],
            "global_order_font_size",
            *_FONT_BOUNDS,
            "order label size",
        )
    color = sizing.get("order_font_color")
    if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        put("global_order_font_color", color)
    if "base_font_size" in sizing:
        put_int(
            sizing["base_font_size"],
            "global_base_font_size",
            *_FONT_BOUNDS,
            "figure font size",
        )

    canvas = section("canvas_px")
    if "width" in canvas:
        put_int(canvas["width"], "global_canvas_width", *_CANVAS_BOUNDS, "canvas width")
    if "height" in canvas:
        put_int(
            canvas["height"], "global_canvas_height", *_CANVAS_BOUNDS, "canvas height"
        )

    axes = section("axes")
    numeric = numeric_field_options(fixations)
    for cfg_key, state_key, label in (
        ("x_field", "global_x_field", "X axis field"),
        ("y_field", "global_y_field", "Y axis field"),
    ):
        val = axes.get(cfg_key)
        if val is not None:
            put_valid(val in numeric, state_key, val, label)

    text = section("text")
    if "scale_text_to_boxes" in text:
        put("global_scale_text_to_boxes", bool(text["scale_text_to_boxes"]))
    if "line_spacing" in text:
        n = number(text["line_spacing"])
        if n is None:
            skipped.append("line spacing")
        else:
            put("global_line_spacing", max(1.0, min(float(n), 10.0)))
    if isinstance(text.get("font_family"), str) and text["font_family"].strip():
        put("global_font_family", text["font_family"])
    tc = text.get("text_color")
    if isinstance(tc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", tc):
        put("global_text_color", tc)

    highlighting = section("highlighting")
    if "critical_span_style" in highlighting:
        css = highlighting["critical_span_style"]
        put_valid(
            css in ("Mark text", "Mark border", "None"),
            "global_critical_span_style",
            css,
            "text highlighting",
        )
    if (
        isinstance(highlighting.get("highlight_column"), str)
        and highlighting["highlight_column"]
    ):
        # The sidebar's `_drop_stale` clears this if it isn't a column in the
        # restored-onto data, so it needs no validation against words here.
        put("global_highlight_column", highlighting["highlight_column"])
    if "highlight_out_of_text" in highlighting:
        put("global_highlight_out_of_text", bool(highlighting["highlight_out_of_text"]))
    htc = highlighting.get("highlight_text_color")
    if isinstance(htc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", htc):
        put("global_highlight_text_color", htc)
    bg = highlighting.get("background_color")
    if isinstance(bg, str) and bg:
        # Map a saved colour back to a preset name, else fall to the custom slot.
        preset = next(
            (n for n, v in BACKGROUND_PRESETS.items() if str(v).lower() == bg.lower()),
            None,
        )
        if preset is not None:
            put("global_bg_choice", preset)
        else:
            put("global_bg_choice", "Custom…")
            put("global_bg_custom", bg)
    sym = highlighting.get("out_of_text_symbol")
    if sym is not None:
        put_valid(
            sym in _OUT_OF_TEXT_MARKERS,
            "global_out_of_text_symbol",
            sym,
            "out-of-text marker",
        )
    sbc = highlighting.get("span_border_color")
    if isinstance(sbc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sbc):
        put("global_span_border_color", sbc)

    # Per-scanpath comparison styling (cmp{idx}_*). A short or hand-edited list
    # degrades gracefully — a missing field just keeps the seeded default.
    compare = config.get("compare")
    if isinstance(compare, list):
        for idx, entry in enumerate(compare[:2]):
            if not isinstance(entry, dict):
                continue
            fc = entry.get("fix_color")
            if isinstance(fc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", fc):
                put(f"cmp{idx}_fix_color", fc)
            sc = entry.get("saccade_color")
            if isinstance(sc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", sc):
                put(f"cmp{idx}_saccade_color", sc)
            if "saccade_style" in entry:
                put_valid(
                    entry["saccade_style"] in SACCADE_DASH_OPTIONS,
                    f"cmp{idx}_saccade_style",
                    entry["saccade_style"],
                    f"scanpath {idx + 1} line style",
                )
            rng = entry.get("marker_size_range")
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                lo, hi = number(rng[0]), number(rng[1])
                if lo is None or hi is None:
                    skipped.append(f"scanpath {idx + 1} marker size")
                else:
                    lo = max(_MARKER_BOUNDS[0], min(int(lo), _MARKER_BOUNDS[1]))
                    hi = max(_MARKER_BOUNDS[0], min(int(hi), _MARKER_BOUNDS[1]))
                    put(f"cmp{idx}_marker_size_range", (min(lo, hi), max(lo, hi)))
            if "hollow" in entry:
                put(f"cmp{idx}_hollow", bool(entry["hollow"]))

    selection = section("selection")
    if selection:
        if _restore_selection(selection, combos):
            applied += 1
        else:
            skipped.append("trial selection")

    # Annotations travel with schema-2 configs (Save & restore). Only restore
    # when the key is present, so a plot-config-only file never clears them.
    if "annotations" in config and isinstance(config["annotations"], list):
        n_anno = restore_records(config["annotations"])
        applied += 1
        st.toast(f"Restored {n_anno} annotation(s) from config.", icon="📝")

    return applied, skipped


def _apply_uploaded_plot_config(combos: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Restore settings from a freshly uploaded plot-config JSON, once per file.

    Reads the file captured by the sidebar ``plot_config_upload`` uploader
    (persisted in session_state across reruns) and writes the saved settings
    into session_state *before* the sidebar widgets render — the same mechanism
    as ``_apply_url_preset``. Deduped by ``(name, size)`` so manual tweaks made
    after a restore aren't clobbered on every rerun. Call right after the trial
    combos are built, before the canvas/visualization controls."""
    uploaded = st.session_state.get("plot_config_upload")
    if uploaded is None:
        return
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("_plot_config_last_import") == signature:
        return
    # Stamp the signature up front so a malformed file isn't retried every rerun.
    st.session_state["_plot_config_last_import"] = signature
    st.session_state.pop("_plot_config_skipped", None)
    try:
        config = json.loads(uploaded.getvalue().decode("utf-8"))
        if not isinstance(config, dict):
            raise ValueError("expected a JSON object")
    except (ValueError, UnicodeDecodeError) as exc:
        st.toast(f"Couldn't read plot config: {exc}", icon="⚠️")
        return
    try:
        applied, skipped = _restore_plot_config(config, combos, fixations)
    except Exception as exc:  # backstop for an unexpectedly shaped config
        st.toast(f"Couldn't apply plot config: {exc}", icon="⚠️")
        return
    st.session_state["_plot_config_skipped"] = skipped
    if applied:
        st.toast(f"Restored {applied} setting(s) from plot config.", icon="✅")
    elif not skipped:
        st.toast("Plot config had no recognized settings.", icon="⚠️")


def configure_page() -> None:
    """Streamlit page config + custom CSS.

    When loaded from an iframe with `?embed=true`, Streamlit's built-in embed
    mode already hides the header/menu — we additionally collapse the sidebar
    so the iframe is mostly the plot. Welcome-tour sessions also start with
    the sidebar closed: the centered welcome renders over a quiet page, and
    the tour's first sidebar step opens it (see tour.spotlight_tour_pending).
    """
    is_embed = (st.query_params.get("embed") or "").lower() in {"true", "1"}
    st.set_page_config(
        page_title="Scanpath Studio - Visualization of Eye Movements in Reading",
        page_icon="👀",
        layout="wide",
        initial_sidebar_state=(
            "collapsed" if (is_embed or spotlight_tour_pending()) else "auto"
        ),
    )
    st.markdown(get_app_css(), unsafe_allow_html=True)


def _render_about_panel() -> "DeltaGenerator":
    """Compact header: title + caption + a Share popover.

    Returns the header container reserved for the Share popover. Share is filled
    later by ``main()`` (via ``_render_share_panel``) because the link it builds
    needs the resolved data source / trial selection, which aren't known this
    early — but a keyed container holds its position in the header regardless of
    when it's filled. The **About** popover lives in the sidebar Help group now
    (``_render_about_sidebar``), keeping the header lean.
    """
    header = st.container(key="about_header")
    title_col, buttons_col = header.columns([5, 2], vertical_alignment="center")
    with title_col:
        st.title("Scanpath Studio")
        st.caption("Interactive visualization of eye movements in reading.")
    # The keyed wrapper right-aligns the content-sized Share trigger (see
    # `.st-key-share_btn` / `.st-key-header_buttons` in styles.py).
    button_row = buttons_col.container(key="header_buttons")
    share_slot = button_row.container(key="share_btn")
    return share_slot


def _render_about_sidebar() -> None:
    """Render the **About** popover in the sidebar Help group.

    Holds the version, authors, code link, and citation. Lives in the sidebar
    (next to **🎓 Show tutorial**) rather than the header so the header stays
    lean; Share remains in the header because the link it builds is contextual to
    the current trial/view."""
    from scanpath_studio import __version__
    from scanpath_studio.constants import CITATION

    bibtex = (
        "@software{Shubi_Scanpath_Studio_2026,\n"
        "author = {Shubi, Omer and Gruteke Klein, Keren and Berzak, Yevgeni},\n"
        "license = {MIT},\n"
        "month = jun,\n"
        "title = {{Scanpath Studio}},\n"
        f"url = {{{CITATION['url']}}},\n"
        f"version = {{{__version__}}},\n"
        "year = {2026}\n"
        "}"
    )
    with st.sidebar.popover("ℹ️ About", width="stretch"):
        st.markdown(
            f"""
**Scanpath Studio** v{__version__} — interactive visualization of eye
movements in reading.

Developed by [Omer Shubi](https://omershubi.github.io/),
[Keren Gruteke Klein](https://kerengruteke.github.io/),
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/),
and TBD at the [LaCC Lab]({CITATION["lab_url"]}), Technion.

💻 **Code** — [github.com/lacclab/scanpath-studio]({CITATION["url"]})
(MIT). Issues and contributions are welcome.

📖 **How to cite** — a paper is in preparation; until then:
"""
        )
        st.code(bibtex, language="bibtex", wrap_lines=True)
        st.markdown(
            """
If you use the bundled demo data, also cite
[OneStop Eye Movements](https://doi.org/10.1038/s41597-025-06272-2)
(Berzak et al., 2025, *Scientific Data*).

🧪 **More Works from Our Labs** —
[Language, Computation and Cognition (LaCC) Lab](https://lacclab.github.io/) ·
[Digital Linguistics](https://www.cl.uzh.ch/en/research-groups/digital-linguistics.html) ·
[ACL 2025 Tutorial: Eye Tracking and NLP](https://acl2025-eyetracking-and-nlp.github.io/)
"""
        )


def _build_share_query(data_choice: str) -> Tuple[str, list]:
    """Build the deep-link query string that reproduces the current view.

    Reads the resolved trial selection and visualization settings back out of
    ``st.session_state`` and encodes them with the same URL schema
    ``_apply_url_preset`` / ``_apply_url_trial_selection`` parse, so opening the
    link reopens the app on this trial with these settings.

    Returns ``(query_string, caveats)`` — ``caveats`` holds human-readable notes
    when the link can't fully reproduce the view (e.g. an uploaded data source
    a URL can't rebuild). The query string is URL-encoded and has no leading
    ``?``; the copy widget composes it onto the live origin client-side.
    """
    from urllib.parse import urlencode

    params: Dict[str, str] = {}
    caveats: list = []

    source = _SHAREABLE_SOURCES.get(data_choice)
    if source:
        params["source"] = source
    else:
        caveats.append(
            "This data source can't be rebuilt from a link — the recipient will "
            "need to load the same data. The view settings below are still shared."
        )

    selection = st.session_state.get("_share_selection") or {}
    participant = selection.get("participant_id")
    trial_id = selection.get("trial_id")
    if participant not in (None, ""):
        params["participant"] = str(participant)
    if trial_id not in (None, ""):
        params["trial_id"] = str(trial_id)

    # Visualization toggles — emit an explicit 0/1 so a layer the user turned
    # *off* is shared as off (the URL coercion reads "0" as False).
    for url_key, state_key in _SHARE_TOGGLE_PARAMS.items():
        if state_key in st.session_state:
            params[url_key] = "1" if st.session_state[state_key] else "0"
    # Strings / choices / colours / numbers — emit only when set.
    for url_key, state_key in {**_SHARE_VALUE_PARAMS, **_SHARE_INT_PARAMS}.items():
        value = st.session_state.get(state_key)
        if value not in (None, ""):
            params[url_key] = str(value)
    for url_key, state_key in _SHARE_FLOAT_PARAMS.items():
        value = st.session_state.get(state_key)
        if value is not None:
            params[url_key] = str(value)
    # Two-element ranges → "lo,hi".
    for url_key, state_key in {
        **_SHARE_INT_RANGE_PARAMS,
        **_SHARE_FLOAT_RANGE_PARAMS,
    }.items():
        value = st.session_state.get(state_key)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            params[url_key] = f"{value[0]},{value[1]}"
    if st.session_state.get("single_animate"):
        params["tab"] = "animation"

    return urlencode(params), caveats


def _render_share_link_widget(query: str) -> None:
    """Render the copyable share link (read-only field + Copy button).

    A same-origin ``components.html`` iframe (same trick as the tour — see
    ``tour.render_spotlight_tour``) composes the full URL from the *live* address:
    ``window.parent.location.origin + pathname`` + the query string built
    server-side. Doing the origin/path join client-side means the link is correct
    wherever the app is served (localhost, Streamlit Cloud, a reverse proxy)
    without the server having to know its own public URL. Copy uses the async
    Clipboard API with a ``document.execCommand`` fallback for insecure contexts.
    """
    payload = json.dumps(query)
    components.html(
        f"""
        <div class="sps-share">
          <div class="sps-share-row">
            <input id="sps-share-url" type="text" readonly
                   aria-label="Shareable link" />
            <button id="sps-share-copy" type="button">Copy link</button>
          </div>
          <div id="sps-share-status" class="sps-share-status"></div>
        </div>
        <style>
          .sps-share {{
            font-family: "Source Sans Pro", system-ui, sans-serif;
            color-scheme: light dark;
          }}
          .sps-share-row {{ display: flex; gap: 0.4rem; align-items: stretch; }}
          #sps-share-url {{
            flex: 1 1 auto; min-width: 0; padding: 0.45rem 0.6rem;
            border: 1px solid rgba(128, 128, 128, 0.5); border-radius: 8px;
            background: rgba(128, 128, 128, 0.08); color: inherit;
            font-size: 0.85rem; font-family: ui-monospace, monospace;
          }}
          #sps-share-copy {{
            flex: 0 0 auto; padding: 0.45rem 0.9rem; cursor: pointer;
            border: 1px solid #1f77b4; border-radius: 8px; white-space: nowrap;
            background: #1f77b4; color: #fff; font-weight: 600; font-size: 0.85rem;
          }}
          #sps-share-copy:hover {{ background: #185fa5; }}
          .sps-share-status {{
            min-height: 1.1rem; margin-top: 0.35rem; font-size: 0.8rem;
            color: #2e7d32; font-weight: 600;
          }}
        </style>
        <script>
        (function () {{
          const query = {payload};
          const loc = window.parent.location;
          const base = loc.origin + loc.pathname;
          const url = query ? base + "?" + query : base;
          const input = document.getElementById("sps-share-url");
          const status = document.getElementById("sps-share-status");
          const btn = document.getElementById("sps-share-copy");
          input.value = url;
          input.addEventListener("focus", function () {{ input.select(); }});
          function flash(msg) {{
            status.textContent = msg;
            setTimeout(function () {{ status.textContent = ""; }}, 2500);
          }}
          async function copy() {{
            try {{
              await navigator.clipboard.writeText(url);
              flash("✓ Link copied to clipboard");
            }} catch (err) {{
              input.focus();
              input.select();
              try {{
                document.execCommand("copy");
                flash("✓ Link copied to clipboard");
              }} catch (err2) {{
                flash("Press ⌘/Ctrl-C to copy the selected link");
              }}
            }}
          }}
          btn.addEventListener("click", copy);
        }})();
        </script>
        """,
        height=110,
    )


def _render_share_panel(data_choice: str) -> None:
    """Fill the header's Share slot with a popover that builds a deep link to the
    current view (data source + trial + visualization settings).

    The link is built **lazily** — only when the user clicks *Refresh link* (and
    once on first open so there's always something to copy). It is NOT rebuilt on
    every rerun, so tweaking an unrelated control doesn't silently rewrite a link
    the user is about to share; the link reflects the settings as of the last
    refresh."""
    with st.popover("Share", icon=":material/share:", width="content"):
        st.markdown(
            "**Share this view** — a link that reopens Scanpath Studio on the "
            "current trial with your visualization settings."
        )
        refresh = st.button(
            "🔄 Refresh link",
            key="share_refresh",
            type="primary",
            help="Rebuild the link from the current trial + settings.",
        )
        if refresh or st.session_state.get("_share_query_frozen") is None:
            st.session_state["_share_query_frozen"] = _build_share_query(data_choice)
        query, caveats = st.session_state["_share_query_frozen"]
        for note in caveats:
            st.caption("⚠️ " + note)
        _render_share_link_widget(query)
        st.caption("Reflects your settings as of the last refresh.")


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading PoTeC…")
def _cached_potec_raw_frames(
    root: str,
    readers: Optional[Tuple[int, ...]],
    texts: Tuple[str, ...],
    download: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw PoTeC frames (pre-normalization) for the GUI data source.

    Returns the same shape as an upload: raw frames the normal
    auto-detect → normalize → harmonize pipeline then handles. Cached on the
    selection so re-runs (toggling viz controls) don't re-read the files."""
    from scanpath_studio.datasets import potec_raw_frames

    return potec_raw_frames(
        root,
        readers=list(readers) if readers else None,
        texts=list(texts),
        download=download,
    )


def _load_potec_source() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the PoTeC corpus data source.

    PoTeC can't be loaded through the generic Upload flow (trial/word ids live
    in filenames, fixation coordinates come from a separate character-AoI
    file), so this dedicated source wraps ``datasets.potec_raw_frames``. The
    returned raw frames go through the same normalization as an upload, so the
    sidebar Column-mapping panels still appear and stay overridable.
    """
    cfg = st.sidebar.expander("PoTeC options", expanded=True)
    root = cfg.text_input(
        "Data directory",
        value=POTEC_DEFAULT_DIR,
        help="Folder holding (or to download) the PoTeC files. A clone of "
        "github.com/DiLi-Lab/PoTeC works, or any empty folder with Download on.",
    )
    download = cfg.checkbox(
        "Download if missing (~45 MB)",
        value=True,
        help="Fetch the PoTeC eye-tracking + AoI files into the directory on "
        "first use. Unticked, the files must already be present.",
    )
    texts = cfg.multiselect(
        "Texts",
        options=POTEC_TEXT_IDS,
        default=["b0"],
        help="Stimulus texts to load (b0–b5 biology, p0–p5 physics). Fewer "
        "texts load faster; the full corpus is 12 texts × 75 readers.",
    )
    readers_raw = cfg.text_input(
        "Readers (optional)",
        value="",
        help="Comma-separated reader ids to limit to (e.g. 0, 1, 2). Leave "
        "blank for all readers of the chosen texts.",
    )
    if not texts:
        st.sidebar.info("Pick at least one PoTeC text to load.")
        return load_sample_data()
    try:
        readers = tuple(int(part) for part in readers_raw.replace(",", " ").split())
    except ValueError:
        st.sidebar.error("Readers must be integers, e.g. `0, 1, 2`.")
        return load_sample_data()
    try:
        return _cached_potec_raw_frames(root, readers or None, tuple(texts), download)
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.sidebar.error(
            f"Couldn't load PoTeC from `{root}`: {exc} "
            "Tick **Download if missing**, or point at a PoTeC folder."
        )
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(show_spinner="Loading MultiplEYE…")
def _cached_multipleye_raw_frames(
    root: str,
    sessions: Optional[Tuple[str, ...]],
    stimuli: Optional[Tuple[str, ...]],
    fixation_source: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw MultiplEYE frames (pre-normalization) for the GUI data source.

    Same shape as an upload — the normal auto-detect → normalize → harmonize
    pipeline then handles them — cached on the selection so re-runs (toggling
    viz controls) don't re-read the files."""
    from scanpath_studio.datasets import multipleye_raw_frames

    return multipleye_raw_frames(
        root,
        sessions=list(sessions) if sessions else None,
        stimuli=list(stimuli) if stimuli else None,
        fixation_source=fixation_source,
    )


@st.cache_data(show_spinner=False)
def _cached_multipleye_inventory(
    root: str, fixation_source: str
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    from scanpath_studio.datasets import multipleye_inventory

    return multipleye_inventory(root, fixation_source=fixation_source)


def _load_multipleye_source() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the MultiplEYE corpus data source.

    MultiplEYE can't be loaded through the generic Upload flow (participant /
    trial / stimulus live only in the folder + file names), so this dedicated
    source wraps ``datasets.multipleye_raw_frames``. The returned raw frames go
    through the same normalization as an upload, so the sidebar Column-mapping
    panels still appear and stay overridable.
    """
    cfg = st.sidebar.expander("MultiplEYE options", expanded=True)
    root = cfg.text_input(
        "Data directory",
        value=MULTIPLEYE_DEFAULT_DIR,
        help="Folder holding a MultiplEYE session set, e.g. the read-only "
        "ZH-CH-Zurich sample (per-session subfolders under fixations/ and "
        "scanpaths/).",
    )
    fixation_source = cfg.radio(
        "Fixation source",
        options=["scanpaths", "fixations"],
        help="scanpaths/ fixations are pre-tagged with page + word index "
        "(richer); fixations/ are raw onset/duration/x/y with no word linkage.",
    )
    try:
        sessions_all, stimuli_all = _cached_multipleye_inventory(root, fixation_source)
    except (FileNotFoundError, OSError):
        sessions_all, stimuli_all = (), ()
    if not sessions_all:
        cfg.warning(
            "No MultiplEYE sessions found here — point at a session set folder "
            "(e.g. the ZH-CH-Zurich sample). Showing the demo meanwhile."
        )
        return load_sample_data()
    sessions = cfg.multiselect(
        "Sessions",
        options=list(sessions_all),
        default=list(sessions_all[:1]),
        help="Reader sessions to load (ET1/ET2 are distinct readers — they read "
        "different stimuli). Fewer sessions load faster.",
    )
    stimuli = cfg.multiselect(
        "Stimuli (optional)",
        options=list(stimuli_all),
        default=[],
        help="Limit to specific stimuli; leave blank for all stimuli the chosen "
        "sessions read.",
    )
    if not sessions:
        st.sidebar.info("Pick at least one MultiplEYE session to load.")
        return load_sample_data()
    try:
        return _cached_multipleye_raw_frames(
            root, tuple(sessions), tuple(stimuli) or None, fixation_source
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.sidebar.error(
            f"Couldn't load MultiplEYE from `{root}`: {exc} "
            "Point at a MultiplEYE session set folder."
        )
        return pd.DataFrame(), pd.DataFrame()


# Registry behind the "Public datasets" source: label → loader (renders its
# own sidebar options and returns raw, pre-normalization frames) + the
# corpus' presentation-monitor size (canvas default for true-to-scale
# rendering; None to estimate from data extents). To add a corpus: write a
# loader in datasets.py, wrap it in a `_load_*_source` sidebar function above,
# and add one entry here.
PUBLIC_DATASET_REGISTRY: dict = {
    "PoTeC — Potsdam Textbook Corpus": dict(
        loader=_load_potec_source,
        monitor=(1680, 1050),  # DELL P2210
    ),
    "MultiplEYE — multilingual reading (ZH-CH sample)": dict(
        loader=_load_multipleye_source,
        monitor=(1920, 1080),  # MultiplEYE physical screen (coords offset to it)
    ),
}


def _load_public_dataset() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Dataset picker + dispatch for the "Public datasets" source."""
    chosen = st.sidebar.radio(
        "Dataset",
        options=list(PUBLIC_DATASET_REGISTRY),
        key="public_dataset_choice",
        help="Public eye-tracking-while-reading corpora with ready-made "
        "loaders (downloaded on demand). More datasets coming.",
    )
    return PUBLIC_DATASET_REGISTRY[chosen]["loader"]()


def _public_dataset_monitor(data_choice: str) -> Optional[Tuple[int, int]]:
    """The selected public corpus' real monitor size, or None.

    None when another data source is active, or when the selected dataset
    doesn't declare a monitor (canvas then defaults to data extents)."""
    if data_choice != PUBLIC_DATASETS_CHOICE:
        return None
    spec = PUBLIC_DATASET_REGISTRY.get(
        st.session_state.get("public_dataset_choice", "")
    )
    return spec.get("monitor") if spec else None


def load_words_and_fixations(
    data_choice: str,
    participant: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw word + fixation frames for the **non-upload** data sources.

    The Upload source is handled separately by the setup wizard
    (``_render_data_setup``), which groups each table's upload box with its
    mapping; this covers the bundled demo, synthetic trial, public datasets, and
    the OneStop server bundle.

    Args:
        data_choice: ``DEMO_CHOICE`` ("Bundled Demo") / ``SYNTHETIC_CHOICE`` /
            ``PUBLIC_DATASETS_CHOICE`` / ``ONESTOP_CHOICE``. The Upload source and
            stored uploaded datasets are handled by ``main`` directly, not here.
        participant: Lowercased participant_id from the URL deep link. When set
            AND `data_choice == ONESTOP_CHOICE`, the OneStop loader fast-paths
            to just that pid's Parquet shard — sub-second instead of ~3 min.
            Ignored for the other data sources.

    Returns:
        Tuple of (words_df, fixations_df) as raw DataFrames before normalization.
    """
    if data_choice == SYNTHETIC_CHOICE:
        from scanpath_studio.synthetic import load_synthetic_data

        return load_synthetic_data()
    if data_choice == PUBLIC_DATASETS_CHOICE:
        return _load_public_dataset()
    # The Upload source is handled separately by the setup wizard
    # (`_render_data_setup`), which renders each table's upload + mapping; see main().
    if data_choice == ONESTOP_CHOICE:
        words, fixations = load_onestop_server_bundle(participant=participant)
        if words.empty or fixations.empty:
            st.sidebar.warning(
                "OneStop bundle unavailable — falling back to demo data."
            )
            return load_sample_data()
        return words, fixations
    return load_sample_data()


def _schema_key(schema: Optional[Dict]) -> Optional[tuple]:
    """Hashable, stable representation of a column-mapping schema dict.

    Values may be strings, ``None``, or a list of column names (composite trial
    id). Used as part of the normalization cache key so an override that changes
    the mapping (without changing the raw frame) correctly busts the cache.
    """
    if schema is None:
        return None
    return tuple(
        (k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(schema.items())
    )


@st.cache_data(show_spinner="Normalizing data…")
def _normalize_pair_cached(
    _words_df: pd.DataFrame,
    _word_schema: Optional[Dict],
    _fixations_df: pd.DataFrame,
    _fix_schema: Optional[Dict],
    cache_key,
    _keep_words: Optional[set] = None,
    _keep_fix: Optional[set] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Pure normalize + harmonize, cached on a cheap fingerprint of the inputs.

    The raw frames are passed un-hashed (underscore args); ``cache_key`` carries
    a ``frame_fingerprint`` + schema signature + the keep-column selection
    instead, so a trial change (which re-runs the script but feeds byte-identical
    raw frames) hits the cache and skips re-normalizing the whole corpus, while
    changing the kept columns correctly busts it.
    """
    words_norm = (
        normalize_words(_words_df, _word_schema, keep_columns=_keep_words)
        if _word_schema is not None
        else empty_words_frame()
    )
    fixations_norm = (
        normalize_fixations(_fixations_df, _fix_schema, keep_columns=_keep_fix)
        if _fix_schema is not None
        else empty_fixations_frame()
    )
    return harmonize_frames(words_norm, fixations_norm)


def _normalize_pair(
    words_df: pd.DataFrame,
    word_schema: Optional[Dict],
    fixations_df: pd.DataFrame,
    fix_schema: Optional[Dict],
    keep_words: Optional[set] = None,
    keep_fix: Optional[set] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize a *validated* (words, fixations) pair to canonical columns and
    run the cross-frame fixups (``harmonize_frames``).

    A ``None`` schema means that table is absent (single-report dataset) → a
    canonical empty frame. Records the composite-trial component columns (when
    the trial id is built from several columns) so the trial picker can offer one
    cascading selector per component. Shared by the upload and non-upload paths.

    The heavy normalization is delegated to the cached ``_normalize_pair_cached``
    so it doesn't re-run on every rerun (e.g. selecting a different trial); only
    the lightweight session-state bookkeeping below runs each time.
    """
    trial_mapping = (word_schema or fix_schema)["trial"]
    trial_cols = trial_mapping_columns(trial_mapping)
    st.session_state["_composite_trial_columns"] = (
        trial_cols if len(trial_cols) > 1 else None
    )
    cache_key = (
        frame_fingerprint(words_df),
        _schema_key(word_schema),
        frame_fingerprint(fixations_df),
        _schema_key(fix_schema),
        tuple(sorted(keep_words)) if keep_words is not None else None,
        tuple(sorted(keep_fix)) if keep_fix is not None else None,
    )
    return _normalize_pair_cached(
        words_df,
        word_schema,
        fixations_df,
        fix_schema,
        cache_key,
        _keep_words=keep_words,
        _keep_fix=keep_fix,
    )


def _reset_active_mapping() -> None:
    """Clear the stashed column mapping at the start of each data load, so a new
    source doesn't inherit the previous one's mapping in the Data Inspection tab."""
    st.session_state["_active_column_mapping"] = {}


def _stash_active_mapping(table: str, schema: Optional[Dict]) -> None:
    """Record the schema (field → source column) actually used for ``table`` so
    ``tabs.render_data_inspection_tab`` can show how columns were mapped. ``table``
    is one of ``"words" / "fixations" / "raw_gaze"``."""
    mapping = st.session_state.setdefault("_active_column_mapping", {})
    mapping[table] = dict(schema) if schema else None


def prepare_data(
    words_df: pd.DataFrame,
    fixations_df: pd.DataFrame,
    allow_override: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame, list]:
    """Infer schemas and normalize incoming dataframes to canonical column names.

    When ``allow_override`` is True, render sidebar expanders that let the user
    pick the exact column names for each field (pre-filled with auto-detection).
    Otherwise just auto-detect.

    Returns ``(words_norm, fixations_norm, problems)``. ``problems`` is a list
    of human-readable strings; when it's non-empty the column mapping isn't
    usable yet (a required field is unmapped) — the normalized frames come back
    empty and the caller shows the raw uploaded data so the user can pick the
    right columns instead of the whole app halting (which used to hide the very
    data needed to decide the mapping).

    Either frame may arrive empty (single-report datasets: only an IA report,
    or only a fixation report) — the missing side becomes a canonical empty
    frame and its mapping UI is skipped. Cross-frame fixups (stimulus-level
    words broadcast across participants, AOI-only fixations placed at word-box
    centers) run at the end via ``harmonize_frames``.
    """
    has_words = not words_df.empty
    has_fixations = not fixations_df.empty
    word_schema = None
    fix_schema = None
    problems: list = []

    if has_words:
        word_proposed = propose_word_schema(words_df)
        if allow_override:
            word_schema = column_mapping_ui(
                words_df,
                table_label="Words/IA",
                state_key_prefix="col_map_words",
                field_specs=WORD_FIELD_SPECS,
                proposed=word_proposed,
                problems=validate_word_schema(word_proposed),
            )
        else:
            word_schema = word_proposed
        word_problems = validate_word_schema(word_schema)
        if word_problems:
            problems.append("Words/IA: " + "; ".join(word_problems))

    if has_fixations:
        fix_proposed = propose_fix_schema(fixations_df)
        if allow_override:
            fix_schema = column_mapping_ui(
                fixations_df,
                table_label="Fixations",
                state_key_prefix="col_map_fix",
                field_specs=FIX_FIELD_SPECS,
                proposed=fix_proposed,
                problems=validate_fix_schema(fix_proposed),
            )
        else:
            fix_schema = fix_proposed
        fix_problems = validate_fix_schema(fix_schema)
        if fix_problems:
            problems.append("Fixations: " + "; ".join(fix_problems))

    if problems:
        # Mapping not ready — let the caller surface the raw data instead of
        # plotting. Clear any stale composite-trial state so the picker doesn't
        # reference columns from a previous, valid dataset.
        st.session_state["_composite_trial_columns"] = None
        return empty_words_frame(), empty_fixations_frame(), problems

    # Record the mapping actually used so the Data Inspection tab can show it.
    _stash_active_mapping("words", word_schema if has_words else None)
    _stash_active_mapping("fixations", fix_schema if has_fixations else None)

    words_norm, fixations_norm = _normalize_pair(
        words_df, word_schema, fixations_df, fix_schema
    )
    return words_norm, fixations_norm, problems


# Labels of the top-level tab strip, shared by the real tabs, the
# unmapped-data placeholder view, and the tab-persistence script so they can't
# drift apart.
# Bulk export is no longer a top-level tab — it's folded into the Scanpath
# Visualization tab's "Export" subtab (see tabs._render_export_panel).
_MAIN_TAB_LABELS = [
    "Scanpath Visualization",
    "Corpus Analysis",
    "Data Inspection",
]


def _render_main_nav() -> str:
    """Render the primary navigation in the sidebar and return the active view.

    Replaces the former top tab strip. A keyed ``st.radio`` persists the active
    view in session_state across reruns automatically — so this needs none of
    the brittle client-side ``sessionStorage`` re-selection the old ``st.tabs``
    required (st.tabs exposes no key). The keyed container is the spotlight-tour
    target (``.st-key-tour_grp_nav``)."""
    nav = st.sidebar.container(key="tour_grp_nav")
    choice = nav.radio(
        "View",
        options=_MAIN_TAB_LABELS,
        key="main_nav",
        label_visibility="collapsed",
    )
    nav.divider()
    return choice or _MAIN_TAB_LABELS[0]


def _render_raw_preview(label: str, df: pd.DataFrame) -> None:
    """Show one uploaded table's columns + a sample so the user can map it."""
    if df is None or df.empty:
        return
    st.markdown(f"#### {label} — {len(df):,} rows × {df.shape[1]} columns")
    st.caption("Columns: " + ", ".join(str(c) for c in df.columns))
    st.dataframe(df.head(200), width="stretch", height=320)


def _render_unmapped_view(
    raw_words_df: pd.DataFrame,
    raw_fixations_df: pd.DataFrame,
    problems: list,
    active_view: str,
) -> None:
    """Show the raw uploaded data while the column mapping is incomplete.

    Only the **Data Inspection** view has content (the uploaded tables,
    unmodified) — the other views point back to the sidebar. Lets the user
    inspect column names and values to fill in the *Column mapping* panels
    without the app halting. ``active_view`` is the sidebar nav selection.
    """
    st.warning(
        "**Finish the column mapping to draw scanpaths.** Map the missing "
        "field(s) in the **Column mapping** panel below each upload box in the "
        "sidebar — the raw uploaded data is shown in the **Data Inspection** view "
        "to help you choose. Still needed:\n\n" + "\n".join(f"- {p}" for p in problems)
    )
    if active_view == "Data Inspection":
        if (raw_words_df is None or raw_words_df.empty) and (
            raw_fixations_df is None or raw_fixations_df.empty
        ):
            st.info("No data loaded yet.")
        _render_raw_preview("Words / IA", raw_words_df)
        _render_raw_preview("Fixations", raw_fixations_df)
    else:
        st.info("Complete the column mapping in the sidebar to see this view.")


# File types accepted by every upload box. ``zip`` covers single-member
# archives wrapping any of the others (e.g. ``data.csv.zip``).
_UPLOAD_TYPES = ["csv", "tsv", "parquet", "feather", "zip", "xlsx", "xls"]


def _uploaded_file_key(uploaded) -> tuple:
    """Stable cache key for an uploaded file across reruns.

    ``st.file_uploader`` keeps the same ``UploadedFile`` (and ``file_id``) for a
    given upload until it's replaced, so keying on it lets us parse the file
    *once* instead of on every rerun."""
    return (
        getattr(uploaded, "file_id", None),
        getattr(uploaded, "name", None),
        getattr(uploaded, "size", None),
    )


@st.cache_data(show_spinner="Reading uploaded data…")
def _read_uploaded_table_cached(_uploaded, file_key) -> pd.DataFrame:
    try:
        _uploaded.seek(0)
    except Exception:
        pass
    return read_table(_uploaded)


@st.cache_data(show_spinner="Reading uploaded data…")
def _read_uploaded_tables_cached(_uploaded_list, file_keys) -> pd.DataFrame:
    for f in _uploaded_list:
        try:
            f.seek(0)
        except Exception:
            pass
    return read_tables(list(_uploaded_list))


def _read_uploaded_frame(
    *,
    uploader_label: str,
    upload_help: str,
    state_prefix: str,
    multi: bool,
    container=None,
) -> pd.DataFrame:
    """Render one upload box and return its (concatenated) frame.

    Renders in the sidebar by default; pass ``container`` (the setup wizard's
    main-area container) to render it there. Empty frame when nothing is
    uploaded. The file parse is cached on the upload's identity (see
    ``_uploaded_file_key``) so a large uploaded table is read once, not re-parsed
    on every rerun. Isolated from the mapping render so tests can inject frames
    without a real upload (AppTest can't drive ``st.file_uploader``)."""
    host = container if container is not None else st.sidebar
    uploaded = host.file_uploader(
        uploader_label,
        type=_UPLOAD_TYPES,
        accept_multiple_files=multi,
        key=f"{state_prefix}_upload",
        help=upload_help,
    )
    if not uploaded:
        return pd.DataFrame()
    if multi:
        return _read_uploaded_tables_cached(
            uploaded, tuple(_uploaded_file_key(f) for f in uploaded)
        )
    return _read_uploaded_table_cached(uploaded, _uploaded_file_key(uploaded))


class _UploadResult(NamedTuple):
    """Result of the grouped-upload flow.

    ``words``/``fixations``/``raw_gaze`` are normalized (empty when absent or, for
    words/fixations, when the mapping is incomplete). ``raw_words``/``raw_fixations``
    are the pre-normalization frames shown by ``_render_unmapped_view`` when
    ``problems`` is non-empty."""

    words: pd.DataFrame
    fixations: pd.DataFrame
    raw_gaze: pd.DataFrame
    raw_words: pd.DataFrame
    raw_fixations: pd.DataFrame
    problems: list


def load_raw_gaze_data(data_choice: str) -> pd.DataFrame:
    """Load and normalize optional raw gaze data (millisecond-level eye positions).

    Raw gaze data provides finer temporal resolution than fixation-level data
    and enables overlay visualizations showing continuous gaze paths.

    Args:
        data_choice: The selected data source (e.g. ``DEMO_CHOICE`` loads the
            bundled sample gaze; other built-in sources have none). The Upload
            source and stored datasets carry their own raw gaze, so ``main``
            doesn't call this for them.

    Returns:
        Normalized raw gaze DataFrame with canonical columns, or empty DataFrame
        if not available or schema inference fails

    Canonical Columns (raw gaze):
        participant_id, trial_id, x, y, timestamp_ms (optional: text)

    UI Effects:
        - Renders optional file uploader for "Upload csv tables" mode
        - Shows warning if schema inference fails
        - Shows info message if sample data unavailable
    """
    raw_gaze_df = pd.DataFrame()

    if data_choice in (SYNTHETIC_CHOICE, PUBLIC_DATASETS_CHOICE):
        # Neither the synthetic trial nor the public corpora ship raw gaze;
        # skip the uploader entirely.
        return raw_gaze_df

    if data_choice == DEMO_CHOICE:
        raw_gaze_df = load_sample_raw_gaze()
        if not raw_gaze_df.empty:
            raw_gaze_schema = infer_raw_gaze_schema(raw_gaze_df)
            if raw_gaze_schema:
                _stash_active_mapping("raw_gaze", raw_gaze_schema)
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)
            else:
                st.sidebar.warning("Could not infer raw gaze schema from sample data")
                raw_gaze_df = pd.DataFrame()
    else:
        uploaded_raw_gaze = st.sidebar.file_uploader(
            "Raw gaze table (optional)",
            type=["csv", "parquet", "feather", "zip"],
            help="Optional: millisecond-level gaze with participant_id, trial_id, x, y.",
        )
        if uploaded_raw_gaze:
            raw_gaze_df = read_table(uploaded_raw_gaze)
            proposed = propose_raw_gaze_schema(raw_gaze_df)
            initial_problems = validate_raw_gaze_schema(proposed)
            raw_gaze_schema = column_mapping_ui(
                raw_gaze_df,
                table_label="Raw gaze",
                state_key_prefix="col_map_raw_gaze",
                field_specs=RAW_GAZE_FIELD_SPECS,
                proposed=proposed,
                problems=initial_problems,
            )
            problems = validate_raw_gaze_schema(raw_gaze_schema)
            if problems:
                st.sidebar.warning("Raw gaze ignored — " + "; ".join(problems))
                raw_gaze_df = pd.DataFrame()
            else:
                _stash_active_mapping("raw_gaze", raw_gaze_schema)
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)

    return raw_gaze_df


# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------


def _sidebar_group(title: str) -> None:
    """Render a section title that groups the toggles below it in the sidebar."""
    st.sidebar.markdown(f"### {title}")


def _reset_wizard_widgets() -> None:
    """Clear the wizard's per-table mapping + keep-field widgets so 'Add data'
    starts a fresh dataset."""
    for key in [
        k
        for k in list(st.session_state.keys())
        if isinstance(k, str) and k.startswith("col_map_")
    ]:
        del st.session_state[key]
    for key in (
        "wizard_dataset_name",
        "wizard_dataset_format",
        "wizard_config_restore",
        "_wizard_config_last",
        "_wizard_restored_meta",
        "_composite_trial_columns",
        "wizard_filter_fields",
        "wizard_filter_by",
        "wizard_keep_extra",
        "wizard_trial_per_table",
        "wizard_participant_per_table",
        "wizard_text_id_per_table",
        # MultiplEYE preset uploads + generic filename-derivation / aggregation.
        "mpe_fix_upload",
        "mpe_aoi_upload",
        "mpe_questions_upload",
        "mpe_participant_upload",
        "wizard_filename_split",
        "wizard_filename_mode",
        "wizard_filename_regex",
        "wizard_filename_regex_lower",
        "wizard_aggregate_char_boxes",
    ):
        st.session_state.pop(key, None)


def _default_dataset_name() -> str:
    """A unique 'Dataset N' name not already taken by a stored dataset."""
    existing = st.session_state.get("_datasets", {})
    n = len(existing) + 1
    while f"Dataset {n}" in existing:
        n += 1
    return f"Dataset {n}"


# Built-in data-source labels a user dataset must not shadow (else the radio gets
# a duplicate option and the stored entry hijacks the built-in source's branch).
_RESERVED_SOURCE_NAMES = frozenset(
    {
        DEMO_CHOICE,
        ONESTOP_CHOICE,
        PUBLIC_DATASETS_CHOICE,
        SYNTHETIC_CHOICE,
        UPLOAD_CHOICE,
    }
)


def _safe_dataset_name(name: Optional[str]) -> str:
    """A non-empty dataset name that collides with neither a built-in source label
    nor an already-stored dataset (suffixed ``(2)``, ``(3)``… rather than silently
    overwriting an existing entry's frames)."""
    name = (name or "").strip() or _default_dataset_name()
    if name in _RESERVED_SOURCE_NAMES:
        name = f"{name} (uploaded)"
    existing = st.session_state.get("_datasets", {})
    if name in existing:
        base, n = name, 2
        while f"{base} ({n})" in existing:
            n += 1
        name = f"{base} ({n})"
    return name


def _finalize_wizard_dataset() -> None:
    """Store the wizard's normalized frames as a named dataset and switch to it.

    Runs as the "✅ Add dataset" button's ``on_click`` callback. A callback —
    not an inline ``if button:`` handler — is required because a real
    ``st.file_uploader`` in the wizard can swallow an inline button click (the
    click triggers a rerun in which the uploader re-renders and the handler is
    never reached), leaving the dataset unstored. The callback fires as part of
    the click event, before the rerun, so it always runs. The frames were stashed
    in ``_wizard_finalize_payload`` on the render that drew the button."""
    payload = st.session_state.pop("_wizard_finalize_payload", None)
    if payload is None:
        return
    ds_name = _safe_dataset_name(st.session_state.get("wizard_dataset_name"))
    store = st.session_state.setdefault("_datasets", {})
    store[ds_name] = payload
    # Apply the source switch through the plain pending key that
    # render_sidebar_data_source consumes before the radio instantiates, and
    # leave the wizard.
    st.session_state["_pending_source_choice"] = ds_name
    st.session_state["_show_upload_wizard"] = False
    st.session_state["setup_complete"] = True
    # Flag the transition so main() paints a "loading" bridge over the wizard
    # while the new dataset's first figure builds — otherwise the wizard lingers
    # on screen (stale DOM) for the seconds the heavy first render takes.
    st.session_state["_wizard_finalizing"] = True


def _remove_dataset(name: str) -> None:
    """Remove a previously added dataset (the ✕ button's ``on_click`` callback).

    Pops it from the ``_datasets`` store and, if it was the selected source,
    switches back to the bundled demo via ``_pending_source_choice`` (applied
    before the radio re-instantiates, like the wizard finalize/cancel switch)."""
    store = st.session_state.get("_datasets", {})
    store.pop(name, None)
    if st.session_state.get("data_source_choice") == name:
        st.session_state["_pending_source_choice"] = DEMO_CHOICE


def _enter_add_data_wizard() -> None:
    """Open the upload wizard (the "➕ Add data" button's ``on_click`` callback).

    Tracks the wizard in a *plain* ``_show_upload_wizard`` flag rather than
    stuffing ``UPLOAD_CHOICE`` into the ``data_source_choice`` radio key. The
    radio isn't rendered while the wizard is open, and Streamlit garbage-collects
    a not-rendered widget key after a couple of reruns — which used to silently
    drop ``data_source_choice`` mid-wizard (more so for a composite trial id,
    which needs more interactions/reruns) and bounce the user back to the main
    app. The flag is never GC'd, and the radio's value stays a real source."""
    st.session_state["_prev_source"] = st.session_state.get(
        "data_source_choice", DEMO_CHOICE
    )
    st.session_state["_show_upload_wizard"] = True
    st.session_state["setup_complete"] = False
    _reset_wizard_widgets()


def render_sidebar_data_source() -> str:
    """Render the data-source picker in the sidebar.

    Returns the selected source: ``DEMO_CHOICE`` ("Bundled Demo"), a stored
    uploaded dataset's name, ``ONESTOP_CHOICE`` / ``PUBLIC_DATASETS_CHOICE`` when
    available, ``SYNTHETIC_CHOICE`` if already selected, or ``UPLOAD_CHOICE``
    while the "➕ Add data" wizard is active. Switching to a stored dataset reloads
    it from session (no re-upload); the synthetic source is no longer offered
    fresh and "Public Datasets" shows grayed-out until the feature flag is on.
    """
    # Keyed wrapper → stable `.st-key-…` selector for the spotlight tour.
    source = st.sidebar.container(key="tour_grp_data_source").expander(
        "Data source", expanded=True
    )

    # Apply a programmatic source switch (the wizard's finalize / Cancel) BEFORE
    # any widget reads data_source_choice. It rides a plain key, not the radio's
    # widget value, so the browser never reconciles it away — assigning
    # data_source_choice inline and rerunning is unreliable because the radio's
    # frontend value can overwrite it on the rerun (works in AppTest, not in a
    # real browser). Applying it here, before the radio instantiates, is the safe
    # equivalent of an on_click callback.
    pending = st.session_state.pop("_pending_source_choice", None)
    if pending is not None:
        st.session_state["data_source_choice"] = pending
        # A real source was chosen (finalize / cancel) → leave the wizard.
        st.session_state["_show_upload_wizard"] = False

    # The upload wizard is tracked by a plain flag, not by parking UPLOAD_CHOICE
    # in the radio key (which Streamlit would garbage-collect mid-wizard — see
    # _enter_add_data_wizard). The legacy ``data_source_choice == UPLOAD_CHOICE``
    # is still honoured so AppTests / `?source=upload` deep links can open the
    # wizard directly. While it's open, don't render the radio; offer a way out.
    if (
        st.session_state.get("_show_upload_wizard")
        or st.session_state.get("data_source_choice") == UPLOAD_CHOICE
    ):
        source.caption("➕ Adding a dataset — fill in the setup wizard →")
        if source.button("✕ Cancel", key="cancel_add_data"):
            st.session_state["_pending_source_choice"] = st.session_state.get(
                "_prev_source", DEMO_CHOICE
            )
            st.session_state["_show_upload_wizard"] = False
            st.session_state["setup_complete"] = True
            st.rerun()
        return UPLOAD_CHOICE

    options = []
    if onestop_data_dir() is not None:
        options.append(ONESTOP_CHOICE)
    options.append(DEMO_CHOICE)
    # Datasets the user has uploaded become first-class, switchable sources.
    options.extend(st.session_state.get("_datasets", {}).keys())
    if public_datasets_enabled():
        options.append(PUBLIC_DATASETS_CHOICE)
    # The synthetic trial is no longer offered fresh (it's a tiny demo variant),
    # but stays selectable when something already chose it (e.g. tests).
    cur = st.session_state.get("data_source_choice")
    if cur == SYNTHETIC_CHOICE and SYNTHETIC_CHOICE not in options:
        options.append(SYNTHETIC_CHOICE)

    # Heal a stale/invalid selection (e.g. a removed dataset) so the radio never
    # errors, then let the session value drive it — no `index=`, which would clash
    # with the Session-State-backed key and can ignore a programmatic switch.
    if st.session_state.get("data_source_choice") not in options:
        st.session_state["data_source_choice"] = options[0]
    choice = source.radio(
        "Data source",
        options,
        help=data_dictionary_help_text(),
        key="data_source_choice",
        label_visibility="collapsed",
    )
    # Let the user remove datasets they added earlier (✕ next to each). Selecting
    # the removed one falls back to the demo (see _remove_dataset).
    added = list(st.session_state.get("_datasets", {}).keys())
    if added:
        source.caption("Remove an added dataset")
        for name in added:
            name_col, x_col = source.columns([5, 1])
            name_col.write(name)
            x_col.button(
                "✕",
                key=f"remove_dataset_{name}",
                on_click=_remove_dataset,
                args=(name,),
                help=f"Remove '{name}'",
            )
    if not public_datasets_enabled():
        source.radio(
            "Public Datasets",
            options=list(PUBLIC_DATASET_REGISTRY),
            index=None,
            disabled=True,
            key="public_datasets_preview",
            help="Curated public corpora — coming soon.",
        )
    # The state change runs in an on_click callback (before widgets instantiate)
    # so it can reassign the data_source_choice radio key — see
    # _enter_add_data_wizard. The callback fires, then Streamlit reruns into the
    # wizard branch above.
    source.button(
        "➕ Add data",
        key="add_data_btn",
        on_click=_enter_add_data_wizard,
        help="Upload your own eye-tracking tables.",
    )
    return choice


def render_sidebar_canvas_controls(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    data_choice: Optional[str] = None,
    slot=None,
    expanded: bool = False,
    title: str = "Experimental Setup",
) -> Tuple[int, int, int, str, float, bool]:
    """Render canvas dimension and font controls in sidebar.

    These controls allow users to match the visualization to their experimental
    display setup, ensuring spatial accuracy and proper word box alignment.

    Args:
        words_filtered: Filtered words dataframe (used to compute default dimensions)
        fixations_filtered: Filtered fixations dataframe (used for coordinate ranges)
        data_choice: Currently selected data source. When it's the OneStop server
            bundle or the bundled demo (a OneStop subset), defaults to the
            OneStop monitor resolution (2560x1440, Dell U2715H — OneStopL1 paper
            §Monitor). Otherwise defaults are derived from data extents.

    Returns:
        Tuple of (canvas_width, canvas_height, base_font_size, font_family,
        line_spacing, scale_text_to_boxes). The text-sizing pair keeps the reading
        text true-to-scale: see `plots._word_label_font_px`.
    """
    # OneStop server bundle + bundled demo share the same experimental setup
    # (Dell U2715H, 2560x1440). Data-derived extents undershoot — text only
    # fills part of the screen — so hard-default to the real monitor here.
    # ``monitor_is_authoritative`` = the source declares a real presentation
    # monitor (OneStop/demo or a public-dataset registry entry), so the canvas
    # should snap to it rather than to data-derived extents.
    monitor_is_authoritative = False
    if data_choice in (ONESTOP_CHOICE, DEMO_CHOICE):
        default_canvas_w, default_canvas_h = 2560, 1440
        monitor_is_authoritative = True
    elif (monitor := _public_dataset_monitor(data_choice)) is not None:
        default_canvas_w, default_canvas_h = monitor
        monitor_is_authoritative = True
    elif data_choice is None or data_choice == UPLOAD_CHOICE:
        # Uploaded data (the setup wizard passes data_choice=None) defaults to a
        # common 1440p monitor — data-derived extents undershoot the real screen,
        # and the user can fine-tune it right here.
        default_canvas_w, default_canvas_h = DEFAULT_FIGURE_SIZE
    else:
        default_canvas_w, default_canvas_h = compute_canvas_size(
            words_filtered, fixations_filtered
        )
    canvas_width = min(max(default_canvas_w, 100), 10000)
    canvas_height = min(max(default_canvas_h, 100), 10000)
    # Seed the data-derived defaults so the inputs render without a `value=`
    # argument — that keeps the keys assignable by the plot-config restore
    # (app._restore_plot_config) without Streamlit's "default value but also set
    # via Session State API" warning.
    #
    # For a source with an authoritative monitor, snap the canvas to it whenever
    # that source *changes* (selecting a public dataset, switching PoTeC↔MultiplEYE,
    # or a public dataset whose registered monitor was updated): a plain
    # ``setdefault`` would let a previously-seeded canvas stick, so a returning
    # session would keep the old monitor and render the corpus off-scale. Manual
    # canvas edits and plot-config restores within the same source are preserved
    # (the key is unchanged, so the snap doesn't re-fire).
    source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    if monitor_is_authoritative and st.session_state.get("_canvas_seeded_for") != (
        source_key
    ):
        st.session_state["global_canvas_width"] = canvas_width
        st.session_state["global_canvas_height"] = canvas_height
        st.session_state["_canvas_seeded_for"] = source_key
    st.session_state.setdefault("global_canvas_width", canvas_width)
    st.session_state.setdefault("global_canvas_height", canvas_height)

    # The display-setup panel (``title``, default "Experimental Setup") lives
    # under the 📂 Data group (TODO 5), rendered into a slot reserved there by
    # `main`; falls back to the sidebar when unset. The setup wizard renders the
    # very same controls inline under its own numbered heading (Group A), passing
    # a more specific title so it doesn't echo that heading.
    display = (slot if slot is not None else st.sidebar).expander(
        title, expanded=expanded
    )
    canvas_width = display.number_input(
        "Monitor width (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor width in pixels to keep coordinates true to scale.",
        key="global_canvas_width",
    )
    canvas_height = display.number_input(
        "Monitor height (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor height in pixels to keep coordinates true to scale.",
        key="global_canvas_height",
    )
    # Reading text is true-to-scale by default: it auto-sizes to the word boxes
    # (text height = box_height / line_spacing) and scales with the figure, so it
    # always fills the real line slot. Untick to fall back to a fixed font size.
    # Keyed (+ seeded) so the Save & restore panel can capture/reapply them.
    st.session_state.setdefault("global_scale_text_to_boxes", True)
    scale_text_to_boxes = display.checkbox(
        "Scale text to boxes",
        key="global_scale_text_to_boxes",
        help="Size the reading text from the word boxes (height = box height ÷ "
        "line spacing) so it stays true to the real experiment at any zoom. "
        "Untick to use the fixed 'Figure font size' below instead.",
    )
    st.session_state.setdefault("global_line_spacing", float(DEFAULT_LINE_SPACING))
    line_spacing = display.number_input(
        "Line spacing",
        min_value=1.0,
        max_value=10.0,
        step=0.5,
        disabled=not scale_text_to_boxes,
        key="global_line_spacing",
        help="Line slots per line of text. OneStop rendered one blank line above "
        "and one below each text line, so the box spans 3 line heights → 3.",
    )
    st.session_state.setdefault("global_base_font_size", 16)
    base_font_size = display.number_input(
        "Figure font size (px)",
        min_value=6,
        max_value=72,
        step=1,
        help="Real (monitor-pixel) font size, scaled true-to-scale with the "
        "figure. Used for the reading text when 'Scale text to boxes' is off or "
        "the data has no word boxes, and always for axis/legend chrome.",
        key="global_base_font_size",
    )
    st.session_state.setdefault("global_font_family", FONT_FAMILY)
    font_family = display.text_input(
        "Text font",
        key="global_font_family",
        help="Font for the word labels. Use the exact font from your experiment "
        "(e.g. 'Courier New') or a CSS fallback stack.",
    )
    # Base reading-text colour (highlighted-text colour lives in Visualization
    # controls). Read back into viz_settings by controls.sidebar_controls.
    st.session_state.setdefault("global_text_color", WORD_LABEL_COLOR)
    display.color_picker(
        "Text color",
        key="global_text_color",
        help="Colour of the reading text drawn over the stimulus.",
    )

    # Plot background lives here (Experimental Setup) rather than under
    # Visualization; sidebar_controls reads the chosen value from session state.
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    if st.session_state.get("global_bg_choice") not in bg_options:
        st.session_state.pop("global_bg_choice", None)
    st.session_state.setdefault("global_bg_choice", bg_options[0])
    display.selectbox(
        "Plot background",
        options=bg_options,
        key="global_bg_choice",
        help="Background of the plotting area (and exported figures).",
    )
    if st.session_state.get("global_bg_choice") == "Custom…":
        display.color_picker(
            "Custom background color",
            value=DEFAULT_BACKGROUND_COLOR,
            key="global_bg_custom",
        )

    return (
        int(canvas_width),
        int(canvas_height),
        int(base_font_size),
        font_family,
        float(line_spacing),
        bool(scale_text_to_boxes),
    )


# -----------------------------------------------------------------------------
# Setup wizard (hybrid: main-area on first load → collapsed panel afterward)
# -----------------------------------------------------------------------------


def _map_section(raw, specs, proposed, prefix, host, keys) -> Dict:
    """Render a subset of a table's mapping fields (the wizard renders the core
    fields in grouped, ordered steps). Returns the partial mapping for ``keys``."""
    if raw is None or getattr(raw, "empty", True):
        return {}
    return column_mapping_ui(
        raw,
        table_label="",
        state_key_prefix=prefix,
        field_specs=specs,
        proposed=proposed,
        container=host,
        use_expander=False,
        only_keys=keys,
        header=False,
    )


def _default_trial_columns(proposed: Dict, present_cols) -> list:
    """Default trial-id mapping for the wizard, restricted to ``present_cols`` (the
    columns common to every table).

    A *trial* is one reading of one passage, so the default composes the
    participant with the finest passage identifier present (paragraph preferred
    over a coarser text id), plus a repeated-reading column when the data has one
    — otherwise the two readings of the same paragraph would collapse into one
    trial (OneStop's own ``unique_trial_id`` is participant + paragraph +
    repeated reading). When that composite can't be built, prefer a single
    precomputed unique trial id over a redundant composite (e.g. don't pair
    ``unique_trial_id`` with the paragraph id it already encodes)."""
    cols_frame = pd.DataFrame(columns=list(present_cols))
    # Use the canonical candidate lists so non-standard names (reader_id,
    # recording_session_label, …) are matched here too, not just by the schema
    # auto-detect.
    participant = pick_column(cols_frame, PARTICIPANT_CANDIDATES)
    paragraph = pick_column(cols_frame, ["unique_paragraph_id", "paragraph_id"])
    text = pick_column(cols_frame, ["unique_text_id", "text_id"])
    # Finest passage grain first: a paragraph is one trial; a text/article may
    # span several paragraphs.
    passage = paragraph or text
    repeated = pick_column(cols_frame, ["repeated_reading_trial", "reread"])
    trial = proposed.get("trial")
    trial_present = bool(trial) and trial in set(present_cols)
    # A precomputed unique trial id that isn't just the passage we'd otherwise
    # compose wins outright (no benefit composing).
    if trial_present and trial not in (paragraph, text):
        return [trial]
    if participant and passage:
        return [c for c in (participant, passage, repeated) if c]
    if paragraph and text:
        return [paragraph, text]
    if trial_present:
        return [trial]
    # No usable composite/trial — fall back to whatever passage component we
    # have (never a lone participant, which isn't a trial), else leave empty so
    # the user picks.
    return list(dict.fromkeys(c for c in (passage,) if c))


def _trial_id_values(raw, schema) -> Optional[set]:
    """Set of distinct trial-id strings for a raw frame + its trial mapping
    (composite mappings are joined, mirroring ``data.trial_id_series``). ``None``
    when the trial isn't mapped or its columns are absent."""
    if raw is None or getattr(raw, "empty", True) or not schema.get("trial"):
        return None
    cols = trial_mapping_columns(schema["trial"])
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return set(trial_id_series(raw, schema["trial"]).unique())


def _render_unified_identifier(
    field_key: str,
    label: str,
    help_text: str,
    toggle_label: str,
    body,
    raw_words,
    raw_fix,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
    common_cols: list,
    default_cols: list,
) -> None:
    """Shared identifier picker for trial / participant / text.

    One unified multiselect over the columns common to every present table by
    default, with an opt-in *Different … per table* toggle. The per-table
    override inherits the unified pick (so flipping it on never reverts to
    nothing — the old behaviour). Several columns compose an id (joined with
    ``_`` like the trial id). Writes ``schema[field_key]`` (str / list / None)
    into ``word_schema`` / ``fix_schema`` in place, mirroring into the per-table
    ``col_map_<tbl>_<field>`` keys for save/restore + a later per-table toggle.
    """
    fix_key, words_key = f"col_map_fix_{field_key}", f"col_map_words_{field_key}"
    unified_key = f"col_map_{field_key}_unified"

    def _mapping(chosen):
        if not chosen:
            return None
        return chosen[0] if len(chosen) == 1 else list(chosen)

    def _seed(key: str, options: list, fallback: list) -> None:
        """Seed a multiselect's session value, dropping columns absent from
        ``options`` (a new upload changes the column universe), like
        ``column_mapping_ui`` — so the stale-reset never fights a default arg."""
        stored = st.session_state.get(key)
        if stored is None:
            st.session_state[key] = list(fallback)
            return
        valid = [c for c in stored if c in options]
        if len(valid) != len(stored):
            st.session_state[key] = valid or list(fallback)

    per_table = False
    if has_words and has_fix:
        st.session_state.setdefault(f"wizard_{field_key}_per_table", False)
        per_table = body.toggle(
            toggle_label,
            key=f"wizard_{field_key}_per_table",
            help="Most datasets name it the same way in every table, so one "
            "shared mapping is used. Turn this on only if Words and Fixations "
            "name it differently.",
        )

    if per_table:
        # Inherit the unified pick so flipping per-table on doesn't start empty.
        inherited = list(st.session_state.get(unified_key) or [])
        if has_fix:
            if inherited and not st.session_state.get(fix_key):
                st.session_state[fix_key] = list(inherited)
            body.caption("Fixations")
            _seed(fix_key, list(raw_fix.columns), inherited)
            chosen_f = body.multiselect(
                label,
                options=list(raw_fix.columns),
                key=fix_key,
                help=help_text,
                label_visibility="collapsed",
            )
            fix_schema[field_key] = _mapping(chosen_f)
        if has_words:
            if inherited and not st.session_state.get(words_key):
                st.session_state[words_key] = list(inherited)
            body.caption("Words/IA")
            _seed(words_key, list(raw_words.columns), inherited)
            chosen_w = body.multiselect(
                label,
                options=list(raw_words.columns),
                key=words_key,
                help=help_text,
                label_visibility="collapsed",
            )
            word_schema[field_key] = _mapping(chosen_w)
    else:
        # One multiselect over the columns common to every present table; its
        # value is mirrored into each table's schema + the per-table widget keys
        # (so the save/restore round-trip and a later per-table toggle both start
        # from this choice). On first render, inherit a restored/seeded per-table
        # mapping when the tables agree, else fall back to ``default_cols``.
        stored = st.session_state.get(unified_key)
        if stored is None:
            inherited = None
            for k in (fix_key, words_key):
                v = st.session_state.get(k)
                if (
                    isinstance(v, (list, tuple))
                    and v
                    and all(c in common_cols for c in v)
                ):
                    inherited = list(v)
                    break
            st.session_state[unified_key] = (
                inherited if inherited else list(default_cols)
            )
        else:
            valid = [c for c in stored if c in common_cols]
            if len(valid) != len(stored):
                st.session_state[unified_key] = valid or list(default_cols)
        chosen = body.multiselect(
            label, options=common_cols, key=unified_key, help=help_text
        )
        mapping = _mapping(chosen)
        if has_fix:
            fix_schema[field_key] = mapping
            st.session_state[fix_key] = list(chosen)
        if has_words:
            word_schema[field_key] = mapping
            st.session_state[words_key] = list(chosen)


def _wizard_filename_derive(body, raw_words, raw_fix, raw_gaze):
    """Optional step: derive columns from the captured ``source_file`` so a trial
    / participant id that lives only in the file name can be mapped.

    Two modes: split into positional ``file_part_N`` columns on a delimiter, or
    extract *named groups* with a regex (robust to variable-length parts, e.g. a
    stimulus name whose length varies). Returns the (possibly augmented) frames so
    the identifier pickers below see the new columns. No-op unless enabled."""
    body.caption(
        "When identity lives in the file name (no column carries it), the "
        "uploaded filename is captured as `source_file` — derive columns from it "
        "to map as the Trial or Participant id below."
    )
    if not body.toggle(
        "Derive columns from the filename",
        key="wizard_filename_split",
        help="Adds columns parsed from source_file (e.g. session, stimulus) you "
        "can then map as ids.",
    ):
        return raw_words, raw_fix, raw_gaze

    mode = body.radio(
        "How",
        ["Split on a delimiter", "Regex named groups"],
        key="wizard_filename_mode",
        horizontal=True,
    )
    pattern = ""
    if mode == "Split on a delimiter":
        delimiter = (
            body.text_input(
                "Delimiter",
                value="_",
                key="wizard_filename_delim",
                max_chars=8,
                help="Character(s) to split the filename on — e.g. "
                "`reader0_b0_scanpath` → reader0 / b0 / scanpath.",
            )
            or "_"
        )
        out = [
            split_source_file(fr, delimiter=delimiter) if not fr.empty else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]
    else:
        pattern = body.text_input(
            "Regex (named groups)",
            value="",
            key="wizard_filename_regex",
            help=r"e.g. `(?P<session>\d+_\w+_ET\d)_.*_(?P<stimulus>.+)_scanpath` — "
            "each named group becomes a column.",
        )
        lower = body.toggle(
            "Lowercase extracted values",
            key="wizard_filename_regex_lower",
            help="Fold case so a value matches across tables (e.g. CamelCase "
            "scanpath names vs lowercase AOI names).",
        )
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                body.error(f"Invalid regex: {exc}")
                return raw_words, raw_fix, raw_gaze
            # A group named after an existing column would be skipped (real data
            # wins) — flag it so the user renames the group instead of silently
            # getting the original column.
            collisions = sorted(
                {
                    c
                    for fr in (raw_words, raw_fix, raw_gaze)
                    if not fr.empty
                    for c in source_file_regex_collisions(fr, pattern)
                }
            )
            if collisions:
                body.warning(
                    "These group names already exist as columns and were left "
                    f"untouched: {', '.join(collisions)}. Rename the group(s) to "
                    "extract them."
                )
        out = [
            extract_columns_from_source_file(fr, pattern, lowercase=lower)
            if not fr.empty
            else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]

    raw_words, raw_fix, raw_gaze = out
    preview = raw_fix if not raw_fix.empty else raw_words
    if mode == "Split on a delimiter":
        new_cols = [c for c in preview.columns if c.startswith(FILE_PART_PREFIX)]
    elif pattern:
        new_cols = [c for c in re.compile(pattern).groupindex if c in preview.columns]
    else:
        new_cols = []
    if new_cols:
        body.caption("Derived columns (first rows) — map them as ids below:")
        body.dataframe(
            preview[[SOURCE_FILE_COLUMN, *new_cols]].drop_duplicates().head(),
            width="stretch",
            hide_index=True,
        )
    return raw_words, raw_fix, raw_gaze


def _wizard_trial_step(
    body,
    raw_words,
    raw_fix,
    prop_w,
    prop_f,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
) -> None:
    """Trial-identifier wizard step: a unified picker shared across tables by
    default (the participant+text default composite), an opt-in per-table
    override, and a per-table trial-count check that flags mismatches.
    Mutates ``word_schema`` / ``fix_schema`` in place."""
    body.caption(
        "Which column(s) identify a single trial (one reading of one text)? "
        "Pick several to compose an id — by default the participant and text ids."
    )

    # Core tables present (raw-gaze keeps its own mapping in its own step).
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default_trial = _default_trial_columns(prop_primary, common_cols)
    _render_unified_identifier(
        "trial",
        "Trial ID *",
        "Pick the column holding your unique trial ID — or several to build one "
        "on the fly (values joined with '_'), e.g. participant + text. The same "
        "mapping is applied to every table.",
        "Different trial-id columns per table",
        body,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        common_cols,
        default_trial,
    )

    # Per-table trial-id sets. Equal → one clean count. Differing but overlapping
    # is usually benign (one table simply covers extra trials, e.g. words for a
    # paragraph with no fixations) → emphasise the difference without implying a
    # mapping error. Differing AND disjoint means the ids don't line up at all.
    sets = {}
    if has_fix:
        sets["Fixations"] = _trial_id_values(raw_fix, fix_schema)
    if has_words:
        sets["Words/IA"] = _trial_id_values(raw_words, word_schema)
    present = {k: v for k, v in sets.items() if v is not None}
    if present:
        values = list(present.values())
        counts_str = ", ".join(f"{k}: **{len(v):,}**" for k, v in present.items())
        if all(v == values[0] for v in values):
            body.success(
                f"✓ **{len(values[0]):,}** trials detected — make sure this is the "
                "number of trials you expect to see."
            )
        elif set.intersection(*values):
            body.info(
                f"ℹ️ Trial coverage differs per table — {counts_str}. They share "
                f"**{len(set.intersection(*values)):,}** trials; some appear in "
                "only one table."
            )
        else:
            body.warning(
                f"⚠️ No trial ids are shared across tables — {counts_str}. Check "
                "the trial-id mapping lines up (try *Different trial-id columns "
                "per table*)."
            )


def _distinct_id_count(raw, mapping) -> Optional[int]:
    """Distinct values of a single-column or composite identifier mapping."""
    if raw is None or getattr(raw, "empty", True) or not mapping:
        return None
    cols = trial_mapping_columns(mapping)
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return int(trial_id_series(raw, mapping).nunique())


def _wizard_participant_text_step(
    field_key: str,
    label: str,
    noun: str,
    help_text: str,
    body,
    raw_words,
    raw_fix,
    prop_w,
    prop_f,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
) -> None:
    """Optional participant- or text-identifier step, in the same shape as the
    Trial identifier (unified picker + per-table toggle + composite support),
    followed by a distinct-value count. Mutates the schemas in place."""
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default = prop_primary.get(field_key)
    default_cols = [default] if default in common_cols else []
    _render_unified_identifier(
        field_key,
        label,
        help_text,
        f"Different {noun} columns per table",
        body,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        common_cols,
        default_cols,
    )
    pp, pp_schema = (raw_fix, fix_schema) if has_fix else (raw_words, word_schema)
    n = _distinct_id_count(pp, pp_schema.get(field_key))
    if n is not None:
        body.success(
            f"✓ **{n:,}** {noun} — make sure this is the number of {noun} you "
            "expect to see."
        )


def _clean_multiselect_state(key: str, valid) -> None:
    """Drop session values for a multiselect that aren't valid options (e.g. a
    restored config from different data), so Streamlit doesn't raise on render."""
    stored = st.session_state.get(key)
    if isinstance(stored, (list, tuple)):
        valid_set = set(valid)
        cleaned = [v for v in stored if v in valid_set]
        if len(cleaned) != len(stored):
            st.session_state[key] = cleaned


def _wizard_keep_and_filter(tables: list, filter_host, keep_host) -> Tuple[dict, list]:
    """Render ONE cross-table *Filter trials by* picker (``filter_host``) and ONE
    *Additional fields to keep* picker (``keep_host``) — instead of duplicating
    both per table, which was confusing.

    ``tables`` is a list of ``(raw, schema, registry, prefix)``. Returns
    ``(keep_by_prefix, filter_dest_fields)``: the source columns to retain per
    table (fed to ``compute_keep_columns(keep_columns=…)``), and the trial-level
    condition fields the Filter panel should offer."""
    cat_by_prefix: dict = {}
    for raw, schema, registry, prefix in tables:
        if raw is None or raw.empty or schema is None:
            continue
        cat_by_prefix[prefix] = categorize_columns(raw, schema, registry)

    # --- Filter trials by: trial-level condition (meta) fields, cross-table ---
    # dest field -> [(prefix, source), …] so the chosen field's source column is
    # kept in the table(s) that carry it.
    filter_map: dict = {}
    for prefix, cats in cat_by_prefix.items():
        for d in cats["detected_optional"]:
            if d["category"] == "meta":
                filter_map.setdefault(d["dest"], []).append((prefix, d["source"]))
    filter_dest_fields: list = []
    if filter_map:
        opts = sorted(filter_map)
        _clean_multiselect_state("wizard_filter_by", opts)
        filter_dest_fields = filter_host.multiselect(
            "Filter trials by",
            options=opts,
            default=opts,
            key="wizard_filter_by",
            help="Trial-level conditions (Hunting/Gathering, difficulty, …). Each "
            "becomes a value picker in the sidebar Filter panel.",
        )

    # --- Additional fields to keep: non-meta detected + unclaimed, cross-table ---
    keep_map: dict = {}
    keep_labels: dict = {}
    keep_default: list = []
    for prefix, cats in cat_by_prefix.items():
        for d in cats["detected_optional"]:
            if d["category"] == "meta":
                continue  # handled by the Filter picker above
            keep_map.setdefault(d["source"], []).append((prefix, d["source"]))
            keep_labels[d["source"]] = f"{d['dest']}  ·  {d['category']}"
            if d["source"] not in keep_default:
                keep_default.append(d["source"])  # measures/linguistic kept by default
        for col in cats["unclaimed"]:
            keep_map.setdefault(col, []).append((prefix, col))
            keep_labels.setdefault(col, f"{col}  ·  extra")
    chosen_keep: set = set()
    if keep_map:
        opts = list(keep_map)
        _clean_multiselect_state("wizard_keep_extra", opts)
        chosen_keep = set(
            keep_host.multiselect(
                "Additional fields to keep",
                options=opts,
                # Detected reading measures / linguistic features kept by default;
                # unrecognised extras stay off until opted in.
                default=keep_default,
                format_func=lambda s: keep_labels.get(s, s),
                key="wizard_keep_extra",
                help="Reading measures, linguistic features and any other columns "
                "to retain (to colour or filter by). Fewer columns is faster.",
            )
        )

    # Map both pickers' choices back to the per-table source columns to keep.
    keep_by_prefix: dict = {prefix: set() for prefix in cat_by_prefix}
    for dest in filter_dest_fields:
        for prefix, source in filter_map.get(dest, []):
            keep_by_prefix[prefix].add(source)
    for key in chosen_keep:
        for prefix, source in keep_map.get(key, []):
            keep_by_prefix[prefix].add(source)
    return keep_by_prefix, list(filter_dest_fields)


def _wizard_restore_config(host) -> None:
    """Step 1 of the wizard: optionally restore a previously saved setup, seeding
    the column mapping + kept-field choices so the user skips re-mapping. Applied
    once per uploaded file; reruns so the mapping widgets pick up the values."""
    uploaded = host.file_uploader(
        "Restore a saved setup (optional)",
        type=["json"],
        key="wizard_config_restore",
        help="Re-apply a column mapping + field choices you exported earlier "
        "(from the 💾 Save & restore panel).",
    )
    if uploaded is None:
        return
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("_wizard_config_last") == signature:
        return
    st.session_state["_wizard_config_last"] = signature
    try:
        config = json.loads(uploaded.getvalue().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        host.warning(f"Couldn't read config: {exc}")
        return
    if isinstance(config, dict):
        # Overwrite: the wizard's mapping widgets were already created on a prior
        # render, so their keys exist — setdefault would no-op and the restore
        # would silently fail. This step runs before the widgets re-instantiate
        # this pass, so writing the keys is safe, and it reruns afterwards.
        _seed_column_mapping(config.get("column_mapping"), overwrite=True)
        # Remember the restored config's provenance so the caller can show which
        # dataset (and when) it was exported from, below the upload box (9.1).
        st.session_state["_wizard_restored_meta"] = {
            "data_source": config.get("data_source"),
            "exported_at": config.get("exported_at"),
        }
        st.toast("Restored the saved mapping — review it below.", icon="✅")
        st.rerun()


def _render_restored_config_caption(host) -> None:
    """Below the restore box: name the dataset the restored setup came from (and
    when it was exported), so the user can confirm they loaded the right one."""
    meta = st.session_state.get("_wizard_restored_meta")
    if not meta:
        return
    source = meta.get("data_source")
    exported = meta.get("exported_at")
    bits = []
    if source:
        bits.append(f"from **{source}**")
    if exported:
        try:
            from datetime import datetime

            bits.append(f"exported {datetime.fromisoformat(exported):%Y-%m-%d %H:%M}")
        except (ValueError, TypeError):
            bits.append(f"exported {exported}")
    detail = " · ".join(bits) if bits else "from a saved file"
    host.caption(f"✓ Restored setup {detail} — review the mapping below.")


def _wizard_setup_config() -> dict:
    """The current wizard setup as a JSON-able dict: the column mapping plus
    provenance, in the schema the restore step (``_wizard_restore_config``) reads
    back. Lets a user save their mapping and re-apply it to similar data later."""
    from datetime import datetime

    from scanpath_studio import __version__

    return {
        # schema 2 = the shared Save & restore format; the restore step only
        # needs ``column_mapping`` + provenance, but keep the shape compatible.
        "schema": 2,
        "app": {"name": "Scanpath Studio", "version": __version__},
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": (st.session_state.get("wizard_dataset_name") or "").strip()
        or None,
        "column_mapping": _collect_column_mapping(),
    }


def _render_setup_download(host) -> None:
    """Export the current column mapping as a JSON setup file, so it can be
    re-applied later via the wizard's *Restore a saved setup* step. Rendered just
    above the **Add dataset** button."""
    host.download_button(
        "⬇️ Download setup (JSON)",
        data=json.dumps(_wizard_setup_config(), indent=2),
        file_name="scanpath_studio_setup.json",
        mime="application/json",
        key="wizard_setup_download",
        help="Save this column mapping to re-use on similar data — restore it "
        "from *Restore a saved setup* at the top of Column mapping.",
    )


def _render_wizard_progress(body) -> None:
    """A native step indicator at the top of the active setup wizard.

    Read-only, driven by the *actual* wizard state (uploads present + whether
    last run's column mapping validated) rather than an independent counter — so
    the bar tracks real progression. ``_wizard_problems_last`` is written near the
    end of ``_render_data_setup`` once this run's validation `problems` are known.
    """
    name_done = bool(st.session_state.get("wizard_dataset_name"))
    uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
        or st.session_state.get("col_map_raw_gaze_upload")
    )
    # No problems last run (and something uploaded) ⇒ the mapping validates.
    # Default to "not yet" until a run has actually computed problems.
    mapped = uploaded and not st.session_state.get("_wizard_problems_last", ["pending"])
    steps = [("Name", name_done), ("Upload", uploaded), ("Map columns", mapped)]
    done_n = sum(1 for _, ok in steps if ok)
    body.progress(done_n / len(steps), text=f"Setup progress — {done_n} / {len(steps)}")
    body.caption(
        " · ".join(f"{'✅' if ok else '⬜'} {lbl}" for lbl, ok in steps)
        + " · 🏁 Add dataset"
    )


def _render_multipleye_upload(body, active: bool) -> _UploadResult:
    """MultiplEYE preset for the Add-dataset wizard (the "MultiplEYE" format).

    Skips the generic column-mapping steps: the user uploads the corpus's
    scanpath/fixation CSVs (+ optional word-AOI CSVs) and the recipe
    (``datasets.multipleye_frames_from_uploads``) parses participant / session /
    trial / stimulus from the file names, makes each stimulus *page* a trial,
    aggregates character AOIs into word boxes, and case-matches the (lowercase)
    AOI file names to the (CamelCase) stimuli. Produces the same normalized frames
    + ``_wizard_finalize_payload`` as a finished generic upload, so finalize /
    reload behave identically."""
    from scanpath_studio.datasets import (
        MULTIPLEYE_FIX_SCHEMA,
        MULTIPLEYE_MONITOR,
        MULTIPLEYE_WORD_SCHEMA,
        multipleye_frames_from_uploads,
    )

    if active:
        body.caption(
            "Upload the MultiplEYE **scanpath** (or fixation) CSVs and, for word "
            "boxes, the **AOI** CSVs — identity is read from the file names, each "
            "stimulus page becomes a trial, and character AOIs are aggregated into "
            "word boxes automatically."
        )
        # Seed the MultiplEYE presentation monitor (true-to-scale default).
        st.session_state.setdefault("global_canvas_width", MULTIPLEYE_MONITOR[0])
        st.session_state.setdefault("global_canvas_height", MULTIPLEYE_MONITOR[1])
        render_sidebar_canvas_controls(
            empty_words_frame(),
            empty_fixations_frame(),
            data_choice=None,
            slot=body,
            expanded=False,
            title="Monitor, font & text scaling",
        )

    fix_df = _read_uploaded_frame(
        uploader_label="Scanpath / fixation CSVs",
        upload_help="The per-trial *_scanpath.csv (preferred — they carry the word "
        "index) or *_fixation.csv files. Drop in as many as you like.",
        state_prefix="mpe_fix",
        multi=True,
        container=body,
    )
    aoi_df = _read_uploaded_frame(
        uploader_label="Word AOI CSVs (optional)",
        upload_help="The per-stimulus *_aoi.csv files (character interest areas). "
        "Optional — without them you get fixations and no word boxes.",
        state_prefix="mpe_aoi",
        multi=True,
        container=body,
    )
    questions_df = _read_uploaded_frame(
        uploader_label="Comprehension questions (optional)",
        upload_help="The multipleye_comprehension_questions_*.xlsx workbook — "
        "adds the questions to the Stimulus & questions panel.",
        state_prefix="mpe_questions",
        multi=False,
        container=body,
    )
    participant_df = _read_uploaded_frame(
        uploader_label="participant_data.csv (optional)",
        upload_help="Reader metadata (age / gender / languages…) → Trial Info chips.",
        state_prefix="mpe_participant",
        multi=False,
        container=body,
    )

    if fix_df.empty:
        if active:
            body.info("⬆️ Upload MultiplEYE scanpath / fixation CSVs to begin.")
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            ["Upload MultiplEYE scanpath / fixation CSVs to begin."],
        )

    words_raw, fix_raw = multipleye_frames_from_uploads(
        fix_df,
        aoi_df if not aoi_df.empty else None,
        questions_df=questions_df if not questions_df.empty else None,
        participant_meta_df=participant_df if not participant_df.empty else None,
    )
    if fix_raw.empty:
        problem = (
            "No MultiplEYE-shaped file names recognized — expected "
            "`<session>_…_trial_N_<stimulus>_<scanpath|fixation>.csv` (e.g. "
            "`001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4_scanpath.csv`). "
            "Browser uploads keep the file name but drop the folder, so the "
            "name must carry the session + stimulus."
        )
        if active:
            body.error(problem)
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            words_raw,
            fix_raw,
            [problem],
        )

    has_words = not words_raw.empty
    word_schema = dict(MULTIPLEYE_WORD_SCHEMA) if has_words else None
    fix_schema = dict(
        MULTIPLEYE_FIX_SCHEMA,
        word_id="word_idx" if "word_idx" in fix_raw.columns else None,
    )
    # Carry MultiplEYE's trial-level facets + side-data through normalization
    # (the upload path passes a keep-set, so registered meta fields must be named
    # here to survive — the directory path uses keep=None and keeps them all).
    keep_fix = compute_keep_columns(
        fix_schema,
        keep_columns={
            "genre",
            "session",
            "participant",
            "is_practice",
            "trial_num",
            "comprehension_questions",
            "pp_age",
            "pp_gender",
            "pp_native_language",
            "pp_years_education",
            "pp_education_level",
        },
    )
    keep_words = (
        compute_keep_columns(
            word_schema, keep_columns={"genre", "comprehension_questions"}
        )
        if has_words
        else None
    )
    # _normalize_pair sets _composite_trial_columns from the (single-column)
    # trial mapping → None, exactly what the reload branch expects.
    words_norm, fixations_norm = _normalize_pair(
        words_raw if has_words else empty_words_frame(),
        word_schema,
        fix_raw,
        fix_schema,
        keep_words=keep_words,
        keep_fix=keep_fix,
    )
    filter_fields = ["genre", "session", "is_practice"]
    st.session_state["wizard_filter_fields"] = filter_fields
    schemas = {"words": word_schema, "fixations": fix_schema, "raw_gaze": None}
    _stash_active_mapping("words", word_schema)
    _stash_active_mapping("fixations", fix_schema)

    if active:
        boxes_msg = (
            f" · **{len(words_norm):,}** word boxes"
            if has_words
            else " · no AOI boxes (upload *_aoi.csv for word boxes)"
        )
        body.success(
            f"✓ **{fixations_norm['participant_id'].nunique()}** readers · "
            f"**{fixations_norm['trial_id'].nunique()}** page-trials" + boxes_msg
        )
        st.session_state["_wizard_finalize_payload"] = {
            "words": words_norm,
            "fixations": fixations_norm,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": filter_fields,
            "composite_trial_columns": [],
            "schemas": schemas,
        }
        body.button(
            "✅ Add dataset",
            type="primary",
            key="wizard_finalize",
            on_click=_finalize_wizard_dataset,
        )

    return _UploadResult(
        words_norm, fixations_norm, pd.DataFrame(), words_raw, fix_raw, []
    )


def _render_data_setup(active: bool) -> _UploadResult:
    """Hybrid data-setup surface for the Upload source.

    On first load (``active``) it's a guided wizard: dataset name + display setup
    at the top, a collapsible **Upload your data** subsection (one toggle per
    table, each showing its row count), a **Column mapping** subsection (one
    toggle per part — restore, trial id, participants, texts, fixations, text &
    interest areas, more mappings), then filter/keep pickers and the **Add
    dataset** button. Only the step you still need to fill stays open; finished /
    auto-detected steps collapse (auto-advance). After finishing it becomes a
    compact collapsed **Data & mapping** panel. Returns the normalized frames (or
    empties + ``problems``)."""
    if active:
        st.header("📂 Set up your dataset")
        st.caption(
            "Name your dataset, upload your tables, then map a few columns — only "
            "the step you still need to fill stays open."
        )
        # Step-by-step guide: a bottom-right card that auto-opens once per session
        # and is replayable via the button. Arm it (auto/first-visit) then render
        # the card early so it streams before the heavy upload/normalize work.
        maybe_show_wizard_guide()
        render_spotlight_wizard_guide()
        render_wizard_guide_button(st)
        body = st.container()
        _render_wizard_progress(body)
    else:
        panel = st.expander("📋 Data & mapping", expanded=False)
        body = panel
        if panel.button(
            "⚙️ Change dataset / mapping",
            key="wizard_reconfigure",
            help="Re-open the setup wizard.",
        ):
            st.session_state["setup_complete"] = False
            st.rerun()

    # Auto-advance: the first not-done step opens; finished + optional steps
    # collapse. In the collapsed panel everything renders inline (Streamlit
    # forbids nesting an expander inside the panel's own expander).
    flow = {"claimed": False}

    def toggle(title: str, *, done: bool = True, expanded: Optional[bool] = None):
        if not active:
            body.markdown(f"**{title}**")
            return body
        if expanded is None:
            if done:
                expanded = False
            else:
                expanded = not flow["claimed"]
                if expanded:
                    flow["claimed"] = True
        return body.expander(title, expanded=expanded)

    def subsection(title: str, number: Optional[int] = None) -> None:
        # Numbered headings (1., 2., …) only in the active wizard, where they make
        # the order to work through explicit. The collapsed review panel drops the
        # numbers (its first two steps aren't re-rendered, so 3.,4.,5. would orphan).
        if not active:
            body.markdown(f"**{title}**")
        elif number is not None:
            body.markdown(f"#### {number}. {title}")
        else:
            body.markdown(f"#### {title}")

    def mapped(prefix: str, field: str) -> bool:
        """Best-effort 'this field is mapped' from last run's session state."""
        v = st.session_state.get(f"{prefix}_{field}")
        if isinstance(v, (list, tuple)):
            return bool(v)
        return bool(v) and v != NONE_OPTION

    # === 1. Dataset name + format ===
    if active:
        subsection("Dataset name", number=1)
        st.session_state.setdefault("wizard_dataset_name", _default_dataset_name())
        body.text_input(
            "Dataset name",
            key="wizard_dataset_name",
            label_visibility="collapsed",
            help="Shown in the Data source list so you can switch back to it.",
        )
        body.segmented_control(
            "Dataset format",
            ["Generic", "MultiplEYE"],
            key="wizard_dataset_format",
            default="Generic",
            help="**Generic**: map your own columns. **MultiplEYE**: upload the "
            "corpus's scanpath/fixation + AOI CSVs and the app parses identity "
            "from the file names (no column mapping needed).",
        )

    # A dedicated dataset format (e.g. MultiplEYE) runs its own tailored flow and
    # bypasses the generic mapping steps below. Read from state so the collapsed
    # review panel (active=False) branches the same way.
    if st.session_state.get("wizard_dataset_format", "Generic") == "MultiplEYE":
        return _render_multipleye_upload(body, active)

    # === 2. Experimental setup ===
    if active:
        subsection("Experimental setup", number=2)
        body.caption(
            "Match the screen the data was recorded on so word boxes and "
            "fixations stay true to scale — open the panel to set monitor size, "
            "font, and text scaling."
        )
        # render_sidebar_canvas_controls renders its own collapsible panel — that
        # IS the display-setup toggle. Seed it on empty frames up front (uploads
        # default to a 2560x1440 monitor; tweak it any time).
        render_sidebar_canvas_controls(
            empty_words_frame(),
            empty_fixations_frame(),
            data_choice=None,
            slot=body,
            expanded=False,
            title="Monitor, font & text scaling",
        )

    # === 3. Upload your data — one toggle per table, with row counts ===
    subsection("Upload your data", number=3)
    core_uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
    )
    # Getting-started guidance at the top of the step, shown only before anything
    # is uploaded (and only in the active wizard): the call to action plus a tip
    # to run locally for large datasets, which is faster and keeps data private.
    already_uploaded = core_uploaded or bool(
        st.session_state.get("col_map_raw_gaze_upload")
    )
    if active and not already_uploaded:
        body.info("⬆️ Upload a **Fixations** and/or **Words/IA** table to begin.")
        body.markdown(
            "💡 **Working with a large dataset?** It's faster — and keeps your "
            "data on your own machine — to run Scanpath Studio locally:\n\n"
            "```bash\npip install scanpath-studio\nscanpath-studio\n```"
        )

    def upload_box(title, *, label, help_text, prefix, multi, noun, expanded):
        # Keep a table's box open once it has an upload, so its row count and
        # head preview stay visible instead of collapsing out of sight.
        has_upload = bool(st.session_state.get(f"{prefix}_upload"))
        box = toggle(title, expanded=expanded or has_upload)
        col = box.columns([0.7, 0.3])[0] if active else box
        frame = _read_uploaded_frame(
            uploader_label=label,
            upload_help=help_text,
            state_prefix=prefix,
            multi=multi,
            container=col,
        )
        if not frame.empty:
            box.success(
                f"✓ **{len(frame):,}** {noun} detected — make sure this is the "
                "number you expect to see."
            )
            if active:
                # Show the first rows so the user can eyeball the columns before
                # mapping them (a quick is-this-the-right-table sanity check).
                box.caption("Preview — first rows:")
                box.dataframe(frame.head(), width="stretch", hide_index=True)
        return frame

    # Order: raw gaze, then fixations, then words. Raw gaze is optional → starts
    # collapsed (auto-opens once it has a file); the core tables stay open so
    # their counts + previews remain visible after uploading.
    raw_gaze = upload_box(
        "Raw gaze (optional)",
        label="Raw gaze table",
        help_text="Optional millisecond-level gaze overlay (one file).",
        prefix="col_map_raw_gaze",
        multi=False,
        noun="gaze points",
        expanded=False,
    )
    raw_fix = upload_box(
        "Fixations",
        label="Fixations table(s)",
        help_text="One or more files (e.g. one per participant); concatenated.",
        prefix="col_map_fix",
        multi=True,
        noun="fixations",
        expanded=True,
    )
    raw_words = upload_box(
        "Words / Interest Areas",
        label="Words / IA table(s)",
        help_text="One or more files (e.g. one per text); concatenated.",
        prefix="col_map_words",
        multi=True,
        noun="words",
        expanded=True,
    )

    if raw_words.empty and raw_fix.empty and raw_gaze.empty:
        # The "upload to begin" prompt now lives at the top of this subsection.
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            raw_words,
            raw_fix,
            [],
        )

    prop_w = propose_word_schema(raw_words) if not raw_words.empty else {}
    prop_f = propose_fix_schema(raw_fix) if not raw_fix.empty else {}
    prop_g = propose_raw_gaze_schema(raw_gaze) if not raw_gaze.empty else {}
    word_schema: Dict = {}
    fix_schema: Dict = {}
    has_words, has_fix = not raw_words.empty, not raw_fix.empty

    # === 4. Column mapping ===
    subsection("Column mapping", number=4)

    # Restore a saved setup (optional, collapsed).
    restore_box = toggle("Restore a saved setup (optional)", done=True)
    _wizard_restore_config(restore_box)
    _render_restored_config_caption(restore_box)

    # Derive ids from the filename (optional) — must run *before* the trial /
    # participant pickers so the split-out file_part_N columns are mappable.
    if (has_words or has_fix) and any(
        SOURCE_FILE_COLUMN in fr.columns for fr in (raw_fix, raw_words) if not fr.empty
    ):
        derive_box = toggle("Derive ids from filename (optional)", done=True)
        raw_words, raw_fix, raw_gaze = _wizard_filename_derive(
            derive_box, raw_words, raw_fix, raw_gaze
        )

    # Trial identifier (required → opens first if not yet mapped).
    if has_words or has_fix:
        trial_done = bool(
            st.session_state.get("col_map_trial_unified")
            or st.session_state.get("col_map_fix_trial")
            or st.session_state.get("col_map_words_trial")
        )
        tbox = toggle("Trial identifier", done=trial_done)
        _wizard_trial_step(
            tbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )

    # Participants (optional, same shape as the trial id).
    if has_words or has_fix:
        pbox = toggle("Participants (optional)", done=True)
        pbox.caption(
            "Which column(s) identify the reader? Leave blank for a single "
            "anonymous reader."
        )
        _wizard_participant_text_step(
            "participant",
            "Participant ID",
            "participants",
            "Pick the reader column — or several to compose an id. Leave empty "
            "for a single anonymous reader.",
            pbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )

    # Texts (optional).
    if has_words or has_fix:
        txbox = toggle("Texts (optional)", done=True)
        txbox.caption(
            "Which column(s) identify the text/passage? Leave blank for a single text."
        )
        _wizard_participant_text_step(
            "text_id",
            "Text ID",
            "texts",
            "Pick the text column — or several to compose an id. Leave empty to "
            "fall back to the trial id.",
            txbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )

    # Column mapping: Fixations — required fields (coordinates + duration) plus
    # the fixation id.
    if has_fix:
        fix_done = mapped("col_map_fix", "duration") and (
            mapped("col_map_fix", "x") or mapped("col_map_fix", "word_id")
        )
        fbox = toggle("Fixations", done=fix_done)
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                fbox,
                ["x", "y", "duration", "fixation_id"],
            )
        )
        fbox.caption(
            "Leave X/Y blank for AOI-only data and map the Word/IA ID under "
            "*More fixation mappings* instead."
        )

    # Column mapping: Text & Interest Areas — required word fields.
    if has_words:
        words_done = mapped("col_map_words", "word_id") and (
            mapped("col_map_words", "left") or mapped("col_map_words", "x")
        )
        wbox = toggle("Text & Interest Areas", done=words_done)
        word_schema.update(
            _map_section(
                raw_words,
                WORD_FIELD_SPECS,
                prop_w,
                "col_map_words",
                wbox,
                ["word_id", "text", "box"],
            )
        )
        wbox.toggle(
            "Aggregate character AOIs into word boxes",
            key="wizard_aggregate_char_boxes",
            help="For interest-area tables with one row per *character* (e.g. CJK "
            "corpora): collapse the characters of each word (grouped by the Trial "
            "+ Word/IA id above) into one bounding box.",
        )

    # More text mappings (line index) — optional.
    if has_words:
        mtbox = toggle("More text mappings (optional)", done=True)
        word_schema.update(
            _map_section(
                raw_words, WORD_FIELD_SPECS, prop_w, "col_map_words", mtbox, ["line"]
            )
        )
        mtbox.caption("Line index enables colouring fixations/words by reading line.")

    # More fixation mappings (word id, timestamp) — optional.
    if has_fix:
        mfbox = toggle("More fixation mappings (optional)", done=True)
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                mfbox,
                ["word_id", "timestamp"],
            )
        )

    # Raw gaze overlay mapping (its own table); required only for a raw-gaze-only
    # upload, else an optional overlay.
    if not raw_gaze.empty:
        rg_required = not has_words and not has_fix
        rg_done = not rg_required or (
            mapped("col_map_raw_gaze", "trial")
            and mapped("col_map_raw_gaze", "x")
            and mapped("col_map_raw_gaze", "y")
        )
        rgbox = toggle(
            "Raw gaze overlay" if rg_required else "Raw gaze overlay (optional)",
            done=rg_done,
        )
        raw_gaze_schema = _map_section(
            raw_gaze,
            RAW_GAZE_FIELD_SPECS,
            prop_g,
            "col_map_raw_gaze",
            rgbox,
            ["participant", "trial", "x", "y", "timestamp", "text"],
        )
    else:
        raw_gaze_schema = {}

    words_problems = validate_word_schema(word_schema) if has_words else []
    fix_problems = validate_fix_schema(fix_schema) if has_fix else []
    raw_gaze_problems = (
        validate_raw_gaze_schema(raw_gaze_schema) if not raw_gaze.empty else []
    )
    problems: list = []
    if words_problems:
        problems.append("Words/IA: " + "; ".join(words_problems))
    if fix_problems:
        problems.append("Fixations: " + "; ".join(fix_problems))
    # A raw-gaze-ONLY upload: an incomplete raw-gaze mapping is the only thing
    # blocking a usable dataset — fold it into `problems` so finalize is gated.
    if not has_words and not has_fix and raw_gaze_problems:
        problems.append("Raw gaze: " + "; ".join(raw_gaze_problems))
    # Feed the wizard step indicator (read at the top of the next run).
    st.session_state["_wizard_problems_last"] = list(problems)

    # === 5. Filter & keep — one cross-table picker each (not per table) ===
    subsection("Filter & keep (optional)", number=5)
    keep_tables: list = []
    if has_words:
        keep_tables.append(
            (raw_words, word_schema, WORD_OPTIONAL_FIELDS, "col_map_words")
        )
    if has_fix:
        keep_tables.append((raw_fix, fix_schema, FIX_OPTIONAL_FIELDS, "col_map_fix"))
    filter_box = toggle("Filter trials by (optional)", done=True)
    keep_box = toggle("Additional fields to keep (optional)", done=True)
    keep_by_prefix, filter_fields = _wizard_keep_and_filter(
        keep_tables, filter_box, keep_box
    )
    st.session_state["wizard_filter_fields"] = list(filter_fields)

    if problems:
        if active:
            _render_setup_download(body)
            body.button("✅ Add dataset", disabled=True, key="wizard_finalize")
            body.warning(
                "Map the required field(s) above (marked \\*) to continue:\n\n"
                + "\n".join(f"- {p}" for p in problems)
            )
        st.session_state["_composite_trial_columns"] = None
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            raw_words,
            raw_fix,
            problems,
        )

    # Record the mapping so the Data Inspection tab shows it once the wizard is
    # collapsed (active=False) and the tabs render with this upload.
    wizard_schemas = {
        "words": dict(word_schema) if has_words else None,
        "fixations": dict(fix_schema) if has_fix else None,
        "raw_gaze": dict(raw_gaze_schema) if not raw_gaze.empty else None,
    }
    for table, schema in wizard_schemas.items():
        _stash_active_mapping(table, schema)

    # Char→word aggregation (optional generic power): collapse character-level
    # AOIs to one box per word using the final word mapping, before normalization
    # (which expects one row per word box). Only fires when the user toggled it on
    # in the Text & Interest Areas step and the words mapping is complete.
    if has_words and st.session_state.get("wizard_aggregate_char_boxes"):
        raw_words = aggregate_char_boxes(raw_words, word_schema)

    keep_words = (
        compute_keep_columns(
            word_schema, keep_columns=keep_by_prefix.get("col_map_words", set())
        )
        if has_words
        else None
    )
    keep_fix = (
        compute_keep_columns(
            fix_schema, keep_columns=keep_by_prefix.get("col_map_fix", set())
        )
        if has_fix
        else None
    )
    if has_words or has_fix:
        words_norm, fixations_norm = _normalize_pair(
            raw_words,
            word_schema if has_words else None,
            raw_fix,
            fix_schema if has_fix else None,
            keep_words=keep_words,
            keep_fix=keep_fix,
        )
    else:
        # Raw-gaze-only dataset — record composite-trial columns from the raw-gaze
        # mapping so the trial picker still offers one selector per component.
        words_norm, fixations_norm = empty_words_frame(), empty_fixations_frame()
        rg_trial_cols = (
            trial_mapping_columns(raw_gaze_schema["trial"])
            if raw_gaze_schema and raw_gaze_schema.get("trial")
            else []
        )
        st.session_state["_composite_trial_columns"] = (
            rg_trial_cols if len(rg_trial_cols) > 1 else None
        )

    raw_gaze_norm = pd.DataFrame()
    if not raw_gaze.empty:
        if raw_gaze_problems:
            body.warning("Raw gaze ignored — " + "; ".join(raw_gaze_problems))
        else:
            raw_gaze_norm = normalize_raw_gaze(raw_gaze, raw_gaze_schema)

    if active:
        # Stash the assembled, already-normalized dataset so the finalize callback
        # can store it. The callback (not an inline `if button:` handler) is what
        # makes "Add dataset" reliable: a real st.file_uploader in the wizard can
        # swallow an inline button click (the click reruns, the uploader
        # re-renders, and the handler is never reached), so the dataset would
        # never get stored. on_click runs as part of the click event, before the
        # rerun — exactly like the "➕ Add data" button.
        st.session_state["_wizard_finalize_payload"] = {
            "words": words_norm,
            "fixations": fixations_norm,
            "raw_gaze": raw_gaze_norm,
            "filter_fields": list(st.session_state.get("wizard_filter_fields", [])),
            # Persist the composite trial-id components (session-only state, not in
            # the frames) so switching back restores the cascading picker.
            "composite_trial_columns": list(
                st.session_state.get("_composite_trial_columns") or []
            ),
            # Persist the column mapping so reselecting this stored dataset can
            # repopulate the Data Inspection tab's mapping table.
            "schemas": wizard_schemas,
        }
        _render_setup_download(body)
        body.button(
            "✅ Add dataset",
            type="primary",
            key="wizard_finalize",
            on_click=_finalize_wizard_dataset,
        )

    return _UploadResult(
        words_norm, fixations_norm, raw_gaze_norm, raw_words, raw_fix, []
    )


# -----------------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------------


def main() -> None:
    """Main application entry point.

    Orchestrates the full application workflow:
        1. Configure Streamlit page and custom CSS
        2. Render title and caption
        3. Load and normalize data (words, fixations, optional raw gaze)
        4. Apply user-selected filters (participants, trials, texts)
        5. Render sidebar controls (canvas, fonts, visualization settings)
        6. Render tabbed UI (Visualization, Generations, Data Inspection, Bulk Export)

    Data Flow:
        CSV upload → schema inference → normalization → filtering →
        trial combination building → visualization rendering

    UI Structure:
        Sidebar: Data source, filters, canvas settings, viz controls
        Main area: 4 tabs for different views of the data

    Error Handling:
        - Stops execution if schema inference fails
        - Shows warning if filtering eliminates all data
        - Handles missing raw gaze data gracefully
    """
    configure_page()
    # Start capturing log records into the in-app debug buffer before any data
    # or plot work runs, so the debug panel (?debug=1) sees this run's logs.
    install_log_capture()
    # The header reserves a slot for the Share popover; it's filled at the end of
    # main(), once the resolved trial + viz settings the link encodes are known.
    share_slot = _render_about_panel()

    # Apply deep-link presets BEFORE any widget renders — see _apply_url_preset
    # for the full URL schema. External tools can deep-link into this app with
    # `?source=...&participant=...&trial=...&...` to land on a specific trial
    # with the reviewer's preferred viz settings.
    url_source = _apply_url_preset()
    if url_source == "onestop" and onestop_data_dir() is not None:
        st.session_state.setdefault("data_source_choice", ONESTOP_CHOICE)
    elif url_source == "demo":
        st.session_state.setdefault("data_source_choice", DEMO_CHOICE)
    elif url_source == "synthetic":
        st.session_state.setdefault("data_source_choice", SYNTHETIC_CHOICE)
    elif url_source == "upload":
        st.session_state.setdefault("_show_upload_wizard", True)

    # First-visit welcome tour. After the URL presets, so embeds and
    # deep-linked sessions can suppress it — but BEFORE the heavy data/plot
    # work, so the welcome streams to the browser immediately instead of
    # after the full first render. Replay clicks arm the tour in the button's
    # on_click callback, which runs before this point in the rerun.
    maybe_show_welcome_tour()
    render_spotlight_tour()

    # Primary navigation lives at the top of the sidebar (replaces the former top
    # tab strip). Read here so the dispatch below — and the unmapped-data view —
    # render only the active view.
    active_view = _render_main_nav()

    # Data source selection (sidebar)
    _sidebar_group("📂 Data")
    data_choice = render_sidebar_data_source()
    # Drop a stale share/save selection when the data source changes — its trial
    # id won't exist in the new dataset, so a Share link or saved config must not
    # carry it over. The active view rewrites _share_selection for the new source.
    if st.session_state.get("_share_selection_source") != data_choice:
        st.session_state.pop("_share_selection", None)
        st.session_state["_share_selection_source"] = data_choice
    # Just-finalized upload: paint a "loading" bridge into the main area now so it
    # repaints over the wizard (instead of the wizard lingering until the slow
    # first figure finishes). Cleared just before the tabs render below.
    _finalizing_bridge = None
    if st.session_state.pop("_wizard_finalizing", False):
        _finalizing_bridge = st.empty()
        _finalizing_bridge.info("✅ Dataset added — loading your scanpaths…", icon="⏳")
    # Reserve the "Experimental Setup" slot under the 📂 Data group (TODO 5);
    # the canvas/monitor/font controls fill it later (they need the filtered
    # data), but it renders here — beside the data source it describes.
    experimental_setup_slot = st.sidebar.container()
    # Reserve the "Trial chips" picker slot here too (under 📂 Data, the setup
    # area) — filled once the filtered columns are known; see render_trial_chip_picker.
    chip_picker_slot = st.sidebar.container()

    # Load + map core data. The **Upload** source renders each table as an
    # [upload box → mapping] group in the sidebar (words, fixations, raw gaze) and
    # normalizes inline; every other source auto-detects (or, for public datasets,
    # renders standalone mapping panels) via prepare_data. Keep the raw frames
    # around so we can show them if the mapping isn't ready.
    #
    # Decide which participant (if any) the OneStop loader should fast-path to.
    #   1. A URL deep link (?participant=) → load just that pid's shard (embedded
    #      review use case); captured once so the live selector can't change it.
    #   2. Otherwise, if the full CSV bundle exists → load the whole corpus once
    #      (participant=None) and let in-app participant switching just *filter*
    #      it — so changing participant is instant instead of re-invoking the
    #      loader on every change.
    #   3. Shards-only setup with no full bundle → fall back to lazy per-pid
    #      loading driven by the selector (the ~60 GB corpus can't be held whole).
    deeplink_pid = st.session_state.get("_deeplink_participant")
    if deeplink_pid:
        deep_link_pid = deeplink_pid
    elif data_choice == ONESTOP_CHOICE and not onestop_full_bundle_exists():
        deep_link_pid = st.session_state.get("single_participant")
    else:
        deep_link_pid = None
    raw_gaze_df: Optional[pd.DataFrame] = None
    # Start each load with a clean column-mapping stash; each branch below
    # records the schema it used for the Data Inspection tab.
    _reset_active_mapping()
    if data_choice == UPLOAD_CHOICE:
        # Hybrid setup wizard: a main-area guided flow on first load, then a
        # compact collapsed "Data & mapping" panel. While the wizard is active
        # (setup not finalized) it owns the page — return before rendering tabs.
        wizard_active = not st.session_state.get("setup_complete", False)
        setup = _render_data_setup(active=wizard_active)
        words_df, fixations_df = setup.words, setup.fixations
        raw_gaze_df = setup.raw_gaze
        raw_words_df, raw_fixations_df = setup.raw_words, setup.raw_fixations
        mapping_problems = setup.problems
        if wizard_active:
            return
    elif data_choice in st.session_state.get("_datasets", {}):
        # A dataset the user uploaded earlier and named — its frames were
        # normalized once by the wizard and stored in session, so switching back
        # to it is instant (no re-upload, no re-mapping). See _render_data_setup's
        # finalize and render_sidebar_data_source.
        stored = st.session_state["_datasets"][data_choice]
        words_df, fixations_df = stored["words"], stored["fixations"]
        raw_gaze_df = stored["raw_gaze"]
        raw_words_df, raw_fixations_df = words_df, fixations_df
        mapping_problems = []
        # Re-publish this dataset's chosen filter fields so the sidebar
        # "Filter trials" panel offers the same dynamic conditions.
        st.session_state["wizard_filter_fields"] = list(stored.get("filter_fields", []))
        # Restore the composite trial-id components (session-only state) so the
        # trial picker offers one cascading selector per part — every other load
        # path sets this, but the stored branch doesn't re-normalize. Without it
        # the picker would inherit whatever source was loaded last.
        composite = list(stored.get("composite_trial_columns") or [])
        st.session_state["_composite_trial_columns"] = composite or None
        # Re-publish the stored column mapping so the Data Inspection tab shows
        # how this dataset's columns were mapped (the wizard isn't re-run here).
        for table, schema in (stored.get("schemas") or {}).items():
            _stash_active_mapping(table, schema)
    else:
        # Built-in sources (demo / synthetic / OneStop / public) auto-detect
        # their mapping, so they skip the wizard entirely. Drop any wizard filter
        # fields left over from a prior upload so the sidebar falls back to the
        # built-in default conditions for these sources.
        st.session_state.pop("wizard_filter_fields", None)
        # Re-propose the column mapping when the monitor-defining source changes.
        # The `col_map_*` widget keys persist across reruns, so a previous corpus'
        # mapping sticks to the next one — e.g. PoTeC maps Trial → `text_id`, and
        # since MultiplEYE *also* has a `text_id` column the stale-column reset
        # (which only fires when a mapped column vanishes) wouldn't catch it, so
        # MultiplEYE's per-page `trial_id` was ignored and every page collapsed
        # into one stimulus-level trial. Clearing on source change lets each
        # corpus auto-detect its own mapping; same-source reruns (and restores)
        # keep their keys. Mirrors the canvas re-seed in render_sidebar_canvas_controls.
        source_key = (data_choice, st.session_state.get("public_dataset_choice"))
        if st.session_state.get("_colmap_seeded_for") != source_key:
            for stale in [
                k
                for k in list(st.session_state)
                if isinstance(k, str) and k.startswith("col_map_")
            ]:
                del st.session_state[stale]
            st.session_state["_colmap_seeded_for"] = source_key
        raw_words_df, raw_fixations_df = load_words_and_fixations(
            data_choice, participant=deep_link_pid
        )
        words_df, fixations_df, mapping_problems = prepare_data(
            raw_words_df,
            raw_fixations_df,
            allow_override=(data_choice == PUBLIC_DATASETS_CHOICE),
        )
    if mapping_problems:
        # A required column is still unmapped. Rather than halt the whole app
        # (which hid the data the user needs to choose the mapping), show the
        # raw uploaded tables; the sidebar Column-mapping panels stay editable.
        _render_unmapped_view(
            raw_words_df, raw_fixations_df, mapping_problems, active_view
        )
        return

    # Optional raw gaze: the Upload source already mapped + normalized it above;
    # every other source loads it here (bundled demo sample, OneStop uploader).
    if raw_gaze_df is None:
        raw_gaze_df = load_raw_gaze_data(data_choice)

    # Whole-dataset frames, captured BEFORE the sidebar "Filter trials" panel —
    # the Bulk Export tab's "Export the whole dataset" option exports these,
    # ignoring the current filters (TODO 1.7).
    words_all, fixations_all = words_df, fixations_df

    # Trial-level filtering / grouping: narrow by participant, by condition
    # (Hunting/Gathering, difficulty, first/repeated reading, correctness), and by
    # annotation state (favorites / tags) before anything downstream sees the
    # data. The controls now live in the Scanpath tab's Trial Selection panel
    # (rendered there via render_trial_filters); here we just read the last
    # selection from session_state so filtering stays global across every view.
    trial_filters = read_trial_filters()
    words_df, fixations_df = filter_trials(
        words_df,
        fixations_df,
        participants=trial_filters["participants"],
        metadata=trial_filters["metadata"],
    )
    if (
        trial_filters["favorites_only"]
        or trial_filters["required_tags"]
        or trial_filters["excluded_tags"]
    ) and not (fixations_df.empty and words_df.empty):
        # Trials live in fixations normally; for words-only datasets fall back
        # to the words frame.
        keys_frame = words_df if fixations_df.empty else fixations_df
        present_keys = {
            (str(p), str(t))
            for p, t in zip(keys_frame["participant_id"], keys_frame["trial_id"])
        }
        kept = set(
            filter_keys(
                list(present_keys),
                favorites_only=trial_filters["favorites_only"],
                required_tags=trial_filters["required_tags"],
                excluded_tags=trial_filters["excluded_tags"],
            )
        )
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, kept)

    # Apply filters (participant/trial/text selection). For a raw-gaze-only
    # dataset (no words/fixations) derive the participant/trial options from the
    # raw gaze so it isn't filtered away (filter_raw_gaze drops on empty lists).
    filters = default_filters(
        words_df, fixations_df if not fixations_df.empty else raw_gaze_df
    )
    words_filtered, fixations_filtered = filter_data(words_df, fixations_df, filters)

    # Filter raw gaze data to match selected participants/trials
    if not raw_gaze_df.empty:
        raw_gaze_filtered = filter_raw_gaze(
            raw_gaze_df,
            filters.get("participants", []),
            filters.get("trials", []),
        )
        if raw_gaze_filtered.empty:
            # Informational, not an error: the loaded raw-gaze samples just
            # don't cover any trial in the current filter (raw gaze typically
            # exists for only a subset of trials). The overlay is optional.
            st.sidebar.caption(
                f"ℹ️ The loaded raw-gaze samples ({len(raw_gaze_df):,} rows) don't "
                "overlap the current trial filter, so the raw-gaze overlay is "
                "unavailable here."
            )
    else:
        raw_gaze_filtered = pd.DataFrame()

    # Check for empty data after filtering. A single empty frame is fine
    # (words-only / fixations-only / raw-gaze-only datasets); all empty means the
    # filters removed everything.
    if words_filtered.empty and fixations_filtered.empty and raw_gaze_filtered.empty:
        st.warning(
            "No data after filtering. Loosen the **Filter trials** panel "
            "(participants, condition, or annotation filters) in the sidebar."
        )
        return

    # Build trial combinations for selection UI — from fixations normally, then
    # words (words-only datasets), then raw gaze (raw-gaze-only datasets).
    combos, _, _ = build_combo_options(
        fixations_filtered
        if not fixations_filtered.empty
        else words_filtered
        if not words_filtered.empty
        else raw_gaze_filtered
    )

    # Land a shared/deep link on its exact `?trial_id=` (once) now that combos
    # exist — see _apply_url_trial_selection. Runs before the sidebar/tab widgets
    # render so the seeded selection is picked up as their initial value.
    _apply_url_trial_selection(combos)

    # Restore settings + annotations from an uploaded config JSON BEFORE the
    # sidebar widgets render, so they pick up the saved values (see
    # _apply_url_preset for the same preset-then-render mechanism). The uploader
    # lives in the "💾 Save & restore" panel below; its file persists across reruns.
    _apply_uploaded_plot_config(combos, fixations_filtered)

    # Canvas and visualization controls (sidebar). For a raw-gaze-only dataset,
    # size the canvas from the gaze extent and default the raw-gaze overlay on —
    # it's the only layer there, so the plot would otherwise be blank.
    raw_gaze_only = words_filtered.empty and fixations_filtered.empty
    if raw_gaze_only and "global_show_raw_gaze" not in st.session_state:
        st.session_state["global_show_raw_gaze"] = True
    # "Experimental Setup" (monitor/font/text-scaling) renders into its reserved
    # slot under the 📂 Data group (TODO 5), not under 🎨 Visualization.
    (
        canvas_width,
        canvas_height,
        base_font_size,
        font_family,
        line_spacing,
        scale_text_to_boxes,
    ) = render_sidebar_canvas_controls(
        words_filtered,
        fixations_filtered if not fixations_filtered.empty else raw_gaze_filtered,
        data_choice,
        slot=experimental_setup_slot,
    )
    # The visualization controls moved out of the sidebar into the Scanpath
    # screen's right-hand rail (tabs.render_single_trial_tab renders them via
    # controls.sidebar_controls with host=rail). The other views — and the Save &
    # restore panel below — still need the resolved settings, so read them from
    # session_state without rendering any widgets; the rail's widgets are the
    # source of truth and write the same keys.
    viz_settings = viz_settings_from_state(
        fixations_filtered, base_font_size, words=words_filtered
    )

    # Fill the "Trial chips" picker (reserved under 📂 Data above) now that the
    # filtered columns are known — it sets `trial_chip_fields`, read by the
    # Scanpath screen's condition-chip strip.
    render_trial_chip_picker(
        words_filtered,
        fixations_filtered,
        host=chip_picker_slot.expander("🏷️ Trial chips", expanded=False),
    )

    # Reserve the "💾 Save & restore" slot here (a keyed container so the
    # spotlight tour can target it); the active view fills it later (it needs the
    # live selection + figure settings for the download). See
    # tabs._render_save_restore_expander. This single panel merges the former
    # Plot-configuration and Annotations sidebar panels (TODO 1.19).
    save_restore_slot = st.sidebar.container(key="tour_grp_save_restore")

    # Whole-dataset combos for the Bulk Export tab's "Export the whole dataset"
    # option, mirroring how `combos` is built from the filtered frames.
    combos_all, _, _ = build_combo_options(
        fixations_all
        if not fixations_all.empty
        else words_all
        if not words_all.empty
        else raw_gaze_df
    )

    # Clear the post-finalize "loading" bridge now that the real content is about
    # to render in its place.
    if _finalizing_bridge is not None:
        _finalizing_bridge.empty()

    # Render tabbed interface. Animation is now a checkbox inside the Scanpath
    # Visualization tab (no separate Animated Scanpath tab); Bulk Export has its
    # own tab. Raw Data + Data Statistics are merged into Data Inspection.
    # Dispatch the active view (sidebar nav). Only one view body renders per run
    # — the keyed nav widget persists the selection across reruns, so no JS hack
    # is needed (unlike st.tabs). render_single_trial_tab writes _share_selection
    # and fills the Save & restore slot when it's the active view.
    if active_view == "Corpus Analysis":
        render_corpus_analysis_tab(
            words_filtered,
            fixations_filtered,
            combos,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            viz_settings=viz_settings,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
        )
    elif active_view == "Data Inspection":
        render_data_inspection_tab(
            words_filtered, fixations_filtered, raw_gaze_filtered
        )
    else:
        # The Scanpath view renders the viz controls itself (right rail) and
        # writes the global_* keys; re-read them below so Save & restore captures
        # any edits the user just made in the rail.
        render_single_trial_tab(
            words_filtered,
            fixations_filtered,
            combos,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            raw_gaze=raw_gaze_filtered,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
            combos_all=combos_all,
            words_all=words_all,
            fixations_all=fixations_all,
        )

    # Re-resolve viz settings from session_state AFTER the dispatch so the Save &
    # restore panel reflects any edits made in the Scanpath rail this run (the
    # widgets there write the global_* keys during render).
    viz_settings = viz_settings_from_state(
        fixations_filtered, base_font_size, words=words_filtered
    )

    # Save & restore (plot config + annotations) renders on EVERY view so it stays
    # reachable when a non-Scanpath view is active (it's a sidebar panel). The
    # trial selection comes from _share_selection (written by the Scanpath view;
    # blank before any trial has been resolved this session).
    _sr_sel = st.session_state.get("_share_selection") or {}
    _sr_pid = str(_sr_sel.get("participant_id") or "")
    _sr_trial = str(_sr_sel.get("trial_id") or "")
    _sr_raw_gaze = (
        extract_trial(raw_gaze_filtered, _sr_pid, _sr_trial)
        if _sr_pid and _sr_trial and not raw_gaze_filtered.empty
        else pd.DataFrame()
    )
    _sr_figure_settings = _build_figure_settings(viz_settings, not _sr_raw_gaze.empty)
    _sr_figure_settings["raw_gaze"] = _sr_raw_gaze if not _sr_raw_gaze.empty else None
    _sr_figure_settings["line_spacing"] = line_spacing
    _sr_figure_settings["scale_text_to_boxes"] = scale_text_to_boxes
    _render_save_restore_expander(
        _sr_pid,
        _sr_trial,
        canvas_width,
        canvas_height,
        viz_settings["x_field"],
        viz_settings["y_field"],
        _sr_figure_settings,
        viz_settings,
        base_font_size,
        _sr_raw_gaze,
        font_family=font_family,
        slot=save_restore_slot,
    )

    # Fill the header's Share popover now — after the view dispatch, so the
    # resolved trial (_share_selection, written by render_single_trial_tab when
    # the Scanpath view is active; persisted from the last visit otherwise, and
    # cleared on a data-source switch) and the live viz settings are all current.
    with share_slot:
        _render_share_panel(data_choice)

    # Sidebar Help group (bottom): replay the welcome tour (the tour itself
    # renders early in this function — see the maybe_show_welcome_tour call) and
    # the About popover (moved here from the header).
    _sidebar_group("❓ Help")
    render_tour_replay_button()
    _render_about_sidebar()

    # Developer debug panel — hidden unless the URL carries ?debug=1, which
    # reveals a "🐛 Debug mode" toggle that opens the captured-log view.
    render_debug_panel()


if __name__ == "__main__":
    main()
