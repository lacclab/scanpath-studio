"""Session-state keys that carry an **external contract** — a wire format.

These strings are not local variable names. Each one appears in at least one of
three places that outlive the running process:

* the **deep link / Share URL** (``url_state._URL_PRESETS`` on the read side,
  ``url_state._build_share_query`` on the write side) — links live in other
  people's bookmarks, papers, issue trackers and embedded review apps;
* the **💾 Save & restore JSON** (written by ``tabs._build_studio_config`` /
  ``wizard._wizard_setup_config``, read by ``url_state._restore_plot_config``) —
  config files sit on disk for months;
* the **pre-widget seeding** both of the above rely on: values are written into
  ``st.session_state`` *before* the widget exists, so the key is the only thing
  connecting the stored value to the control it drives.

**Renaming one of these strings breaks existing share links and saved configs,
and nothing fails loudly** — the link still opens, the config still restores,
they just silently drop the setting. That is why they are pinned here and in
``tests/test_session_key_contract.py``: a rename now fails a test instead of a
user's old link.

Scope is deliberately narrow (ENG-6). This module does **not** try to name all
~270 ``session_state`` keys in the app — a key with no external contract is just
a local variable and can be renamed freely. Only the contract keys live here.

Adding a key to the wire format? Add the constant **and** put it in the frozen
grouping below in the same commit; the contract test tells you so by name.
Changing the *meaning* or encoding of an existing key is the same kind of break
as renaming it — take a new key instead.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

# ---------------------------------------------------------------------------
# Visualization settings — the `global_*` keys the sidebar/rail widgets own.
# Every one of these round-trips through BOTH the share link and the saved
# config (or, below the divider, through the saved config only).
# ---------------------------------------------------------------------------
GLOBAL_SHOW_WORDS = "global_show_words"
GLOBAL_SHOW_LABELS = "global_show_labels"
GLOBAL_SHOW_FIX = "global_show_fix"
GLOBAL_SHOW_ORDER = "global_show_order"
GLOBAL_SHOW_SACCADES = "global_show_saccades"
GLOBAL_SHOW_SACCADE_ARROWS = "global_show_saccade_arrows"
GLOBAL_SACCADE_TYPE_LEGEND = "global_saccade_type_legend"
GLOBAL_FIXATION_SNAP_TO_WORD = "global_fixation_snap_to_word"
GLOBAL_ANIM_AUTOPLAY = "global_anim_autoplay"
GLOBAL_SHOW_HEATMAP = "global_show_heatmap"
GLOBAL_SHOW_RAW_GAZE = "global_show_raw_gaze"
GLOBAL_SHOW_COLORBARS = "global_show_colorbars"
GLOBAL_HOLLOW_FIXATIONS = "global_hollow_fixations"
GLOBAL_SCALE_TEXT_TO_BOXES = "global_scale_text_to_boxes"
GLOBAL_COLOR_BY = "global_color_by"
GLOBAL_HEATMAP_STYLE = "global_heatmap_style"
GLOBAL_HEATMAP_NORM = "global_heatmap_norm"
GLOBAL_HEATMAP_METRIC = "global_heatmap_metric"
GLOBAL_CRITICAL_SPAN_STYLE = "global_critical_span_style"
GLOBAL_HIGHLIGHT_COLUMN = "global_highlight_column"
GLOBAL_X_FIELD = "global_x_field"
GLOBAL_Y_FIELD = "global_y_field"
GLOBAL_SACCADE_STYLE = "global_saccade_style"
GLOBAL_SACCADE_RENDER_MODE = "global_saccade_render_mode"
# PRE-3 vertical drift correction (ENG-23 put it on the link + the config).
GLOBAL_ALIGN_ALGORITHM = "global_align_algorithm"
GLOBAL_ALIGN_CONNECTORS = "global_align_connectors"
GLOBAL_FIXATION_SYMBOL = "global_fixation_symbol"
GLOBAL_FIXATION_COLOR = "global_fixation_color"
GLOBAL_PALETTE = "global_palette"
GLOBAL_FIXATION_COLORSCALE = "global_fixation_colorscale"
GLOBAL_HEATMAP_COLORSCALE = "global_heatmap_colorscale"
GLOBAL_SACCADE_COLOR = "global_saccade_color"
GLOBAL_SACCADE_COLOR_MODE = "global_saccade_color_mode"
GLOBAL_SACCADE_CLASS_COLOR_FORWARD = "global_saccade_class_color_forward"
GLOBAL_SACCADE_CLASS_COLOR_SKIP = "global_saccade_class_color_skip"
GLOBAL_SACCADE_CLASS_COLOR_REFIXATION = "global_saccade_class_color_refixation"
GLOBAL_SACCADE_CLASS_COLOR_RETURN_SWEEP = "global_saccade_class_color_return_sweep"
GLOBAL_SACCADE_CLASS_COLOR_REGRESSION = "global_saccade_class_color_regression"
GLOBAL_ORDER_FONT_COLOR = "global_order_font_color"
GLOBAL_TEXT_COLOR = "global_text_color"
GLOBAL_HIGHLIGHT_TEXT_COLOR = "global_highlight_text_color"
GLOBAL_BG_CHOICE = "global_bg_choice"
GLOBAL_BG_CUSTOM = "global_bg_custom"
GLOBAL_FONT_FAMILY = "global_font_family"
GLOBAL_WORD_HOVER_MEASURE = "global_word_hover_measure"
GLOBAL_WORD_HOVER_FIELDS = "global_word_hover_fields"
GLOBAL_FIXATION_HOVER_FIELDS = "global_fixation_hover_fields"
GLOBAL_ORDER_FONT_SIZE = "global_order_font_size"
GLOBAL_ANIM_GRID_STEP_MS = "global_anim_grid_step_ms"
GLOBAL_ANIM_MAX_FRAMES = "global_anim_max_frames"
GLOBAL_LINE_SPACING = "global_line_spacing"
GLOBAL_SACCADE_WIDTH = "global_saccade_width"
GLOBAL_FIXATION_OPACITY = "global_fixation_opacity"
GLOBAL_STIMULUS_IMAGE_OPACITY = "global_stimulus_image_opacity"
GLOBAL_STIMULUS_IMAGE_OFFSET_X = "global_stimulus_image_offset_x"
GLOBAL_STIMULUS_IMAGE_OFFSET_Y = "global_stimulus_image_offset_y"
GLOBAL_STIMULUS_IMAGE_SCALE = "global_stimulus_image_scale"
GLOBAL_MARKER_SIZE_RANGE = "global_marker_size_range"
GLOBAL_FIXATION_COLOR_RANGE = "global_fixation_color_range"
GLOBAL_HEATMAP_COLOR_RANGE = "global_heatmap_color_range"
GLOBAL_SHOW_STIMULUS_IMAGE = "global_show_stimulus_image"
GLOBAL_FIT_TO_MONITOR = "global_fit_to_monitor"

# --- Saved-config-only settings (no share-link param) ----------------------
GLOBAL_BASE_FONT_SIZE = "global_base_font_size"
GLOBAL_CANVAS_WIDTH = "global_canvas_width"
GLOBAL_CANVAS_HEIGHT = "global_canvas_height"
GLOBAL_MONITOR_WIDTH_MM = "global_monitor_width_mm"
GLOBAL_VIEWING_DISTANCE_MM = "global_viewing_distance_mm"
GLOBAL_DISPLAY_DPI = "global_display_dpi"
GLOBAL_STIMULUS_FONT_PT = "global_stimulus_font_pt"
GLOBAL_USE_STIMULUS_FONT_PT = "global_use_stimulus_font_pt"
GLOBAL_COLORBAR_ORIENTATION = "global_colorbar_orientation"
GLOBAL_COLORBAR_TICKANGLE = "global_colorbar_tickangle"
GLOBAL_COLORBAR_TICKFONT_SIZE = "global_colorbar_tickfont_size"
GLOBAL_SPAN_BORDER_COLOR = "global_span_border_color"
# PRE-2 fixation classification: one (mode, threshold, symbol, colour) group per
# category. `oob` has no threshold — it is a geometry test, not a duration one.
GLOBAL_FIXCLASS_SHORT_MODE = "global_fixclass_short_mode"
GLOBAL_FIXCLASS_SHORT_THRESHOLD_MS = "global_fixclass_short_threshold_ms"
GLOBAL_FIXCLASS_SHORT_SYMBOL = "global_fixclass_short_symbol"
GLOBAL_FIXCLASS_SHORT_COLOR = "global_fixclass_short_color"
GLOBAL_FIXCLASS_LONG_MODE = "global_fixclass_long_mode"
GLOBAL_FIXCLASS_LONG_THRESHOLD_MS = "global_fixclass_long_threshold_ms"
GLOBAL_FIXCLASS_LONG_SYMBOL = "global_fixclass_long_symbol"
GLOBAL_FIXCLASS_LONG_COLOR = "global_fixclass_long_color"
GLOBAL_FIXCLASS_OOB_MODE = "global_fixclass_oob_mode"
GLOBAL_FIXCLASS_OOB_SYMBOL = "global_fixclass_oob_symbol"
GLOBAL_FIXCLASS_OOB_COLOR = "global_fixclass_oob_color"

# --- Trial-picker keys a link / config seeds (utils.select_trial owns them) --
# `_SELECTION_PREFIXES` in url_state is ("single",); these are that prefix's
# widget keys, seeded before the picker renders.
SINGLE_SELECT_TRIAL_MODE = "single_select_trial_mode"
SINGLE_TRIAL_ID = "single_trial_id"
SINGLE_PARTICIPANT = "single_participant"
SINGLE_SLIDER = "single_slider"
SINGLE_ANIMATE = "single_animate"

# --- Public-OneStop source options that ride the deep link (DATA-3) ---------
ONESTOP_VARIANT = "onestop_variant"
ONESTOP_REGIME = "onestop_regime"
ONESTOP_PARTS = "onestop_parts"

# --- Infrastructure keys the URL / config paths read or stamp ---------------
DEEPLINK_PARTICIPANT = "_deeplink_participant"
GLOBAL_ADVANCED = "global_advanced"
# Per-trial annotations travel inside the schema-2 config; the store key is
# owned by annotations.py (pinned equal to it by the contract test).
TRIAL_ANNOTATIONS = "trial_annotations"
# Saved column mapping is seeded key-by-key from the config's `column_mapping`
# section; the prefix is the contract, the suffixes are data-dependent.
COLUMN_MAPPING_PREFIX = "col_map_"

# --- Per-scanpath comparison styling (config `compare` list) ----------------
# Templates, not keys: the list index is substituted at read/write time.
CMP_FIX_COLOR = "cmp{idx}_fix_color"
CMP_SACCADE_COLOR = "cmp{idx}_saccade_color"
CMP_SACCADE_STYLE = "cmp{idx}_saccade_style"
CMP_SACCADE_WIDTH = "cmp{idx}_saccade_width"
CMP_MARKER_SIZE_RANGE = "cmp{idx}_marker_size_range"
CMP_HOLLOW = "cmp{idx}_hollow"
CMP_OPACITY = "cmp{idx}_opacity"

# ---------------------------------------------------------------------------
# URL query-parameter names that are NOT viz settings — the selection half of a
# deep link, plus one legacy alias kept alive for old links.
# ---------------------------------------------------------------------------
PARAM_SOURCE = "source"
PARAM_PARTICIPANT = "participant"
PARAM_TRIAL = "trial"  # slider index (read-only; Share emits `trial_id`)
PARAM_TRIAL_ID = "trial_id"
PARAM_TAB = "tab"
PARAM_ONESTOP_VARIANT = "onestop_variant"
PARAM_ONESTOP_REGIME = "onestop_regime"
PARAM_ONESTOP_PARTS = "onestop_parts"
# Legacy inverse of `show_order`, still parsed so pre-Share links keep working.
PARAM_HIDE_FIXATION_NUMBERS = "hide_fixation_numbers"

# ---------------------------------------------------------------------------
# Frozen groupings — `url_key -> session_state key`, one mapping per encoding.
# The GROUP a param sits in is part of the wire format too: it decides how the
# value is written into the URL and coerced back out ("1"/"0", str, int, float,
# "lo,hi"). Moving a param between groups changes the encoding, so the contract
# test pins the groups separately rather than one flat set.
# ---------------------------------------------------------------------------
# bool -> "1"/"0"
SHARE_TOGGLE_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "show_words": GLOBAL_SHOW_WORDS,
        "show_labels": GLOBAL_SHOW_LABELS,
        "show_fixations": GLOBAL_SHOW_FIX,
        "show_order": GLOBAL_SHOW_ORDER,
        "show_saccades": GLOBAL_SHOW_SACCADES,
        "show_saccade_arrows": GLOBAL_SHOW_SACCADE_ARROWS,
        "saccade_type_legend": GLOBAL_SACCADE_TYPE_LEGEND,
        "snap_fixations": GLOBAL_FIXATION_SNAP_TO_WORD,
        "align_connectors": GLOBAL_ALIGN_CONNECTORS,
        "anim_autoplay": GLOBAL_ANIM_AUTOPLAY,
        "show_heatmap": GLOBAL_SHOW_HEATMAP,
        "show_raw_gaze": GLOBAL_SHOW_RAW_GAZE,
        "show_colorbars": GLOBAL_SHOW_COLORBARS,
        "hollow_fixations": GLOBAL_HOLLOW_FIXATIONS,
        "scale_text_to_boxes": GLOBAL_SCALE_TEXT_TO_BOXES,
    }
)

# string / choice / colour
SHARE_VALUE_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "color_by": GLOBAL_COLOR_BY,
        "heatmap_style": GLOBAL_HEATMAP_STYLE,
        "heatmap_norm": GLOBAL_HEATMAP_NORM,
        "heatmap_metric": GLOBAL_HEATMAP_METRIC,
        "critical_span_style": GLOBAL_CRITICAL_SPAN_STYLE,
        "highlight_column": GLOBAL_HIGHLIGHT_COLUMN,
        "x_field": GLOBAL_X_FIELD,
        "y_field": GLOBAL_Y_FIELD,
        "saccade_style": GLOBAL_SACCADE_STYLE,
        "saccade_render_mode": GLOBAL_SACCADE_RENDER_MODE,
        "align_algorithm": GLOBAL_ALIGN_ALGORITHM,
        "fixation_symbol": GLOBAL_FIXATION_SYMBOL,
        "fixation_color": GLOBAL_FIXATION_COLOR,
        "palette": GLOBAL_PALETTE,
        "fixation_colorscale": GLOBAL_FIXATION_COLORSCALE,
        "heatmap_colorscale": GLOBAL_HEATMAP_COLORSCALE,
        "saccade_color": GLOBAL_SACCADE_COLOR,
        "saccade_color_mode": GLOBAL_SACCADE_COLOR_MODE,
        "saccade_color_forward": GLOBAL_SACCADE_CLASS_COLOR_FORWARD,
        "saccade_color_skip": GLOBAL_SACCADE_CLASS_COLOR_SKIP,
        "saccade_color_refixation": GLOBAL_SACCADE_CLASS_COLOR_REFIXATION,
        "saccade_color_return_sweep": GLOBAL_SACCADE_CLASS_COLOR_RETURN_SWEEP,
        "saccade_color_regression": GLOBAL_SACCADE_CLASS_COLOR_REGRESSION,
        "order_font_color": GLOBAL_ORDER_FONT_COLOR,
        "text_color": GLOBAL_TEXT_COLOR,
        "highlight_text_color": GLOBAL_HIGHLIGHT_TEXT_COLOR,
        "bg_choice": GLOBAL_BG_CHOICE,
        "bg_custom": GLOBAL_BG_CUSTOM,
        "font_family": GLOBAL_FONT_FAMILY,
        "word_hover_measure": GLOBAL_WORD_HOVER_MEASURE,
        "word_hover_fields": GLOBAL_WORD_HOVER_FIELDS,
        "fixation_hover_fields": GLOBAL_FIXATION_HOVER_FIELDS,
    }
)

# int
SHARE_INT_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "order_font_size": GLOBAL_ORDER_FONT_SIZE,
        "anim_grid_step_ms": GLOBAL_ANIM_GRID_STEP_MS,
        "anim_max_frames": GLOBAL_ANIM_MAX_FRAMES,
    }
)

# float
SHARE_FLOAT_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "line_spacing": GLOBAL_LINE_SPACING,
        "saccade_width": GLOBAL_SACCADE_WIDTH,
        "fixation_opacity": GLOBAL_FIXATION_OPACITY,
        "stimulus_image_opacity": GLOBAL_STIMULUS_IMAGE_OPACITY,
        "stimulus_image_offset_x": GLOBAL_STIMULUS_IMAGE_OFFSET_X,
        "stimulus_image_offset_y": GLOBAL_STIMULUS_IMAGE_OFFSET_Y,
        "stimulus_image_scale": GLOBAL_STIMULUS_IMAGE_SCALE,
    }
)

# (int, int) -> "lo,hi"
SHARE_INT_RANGE_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "marker_size_range": GLOBAL_MARKER_SIZE_RANGE,
    }
)

# (float, float) -> "lo,hi"
SHARE_FLOAT_RANGE_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        "fixation_color_range": GLOBAL_FIXATION_COLOR_RANGE,
        "heatmap_color_range": GLOBAL_HEATMAP_COLOR_RANGE,
    }
)

# Saved-config `layers` key -> session key (the config's own naming,
# deliberately different from the URL params above).
PLOT_CONFIG_LAYER_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "words": GLOBAL_SHOW_WORDS,
        "word_labels": GLOBAL_SHOW_LABELS,
        "fixations": GLOBAL_SHOW_FIX,
        "order_labels": GLOBAL_SHOW_ORDER,
        "saccades": GLOBAL_SHOW_SACCADES,
        "saccade_arrows": GLOBAL_SHOW_SACCADE_ARROWS,
        "heatmap": GLOBAL_SHOW_HEATMAP,
        "raw_gaze": GLOBAL_SHOW_RAW_GAZE,
        "stimulus_image": GLOBAL_SHOW_STIMULUS_IMAGE,
        "full_monitor": GLOBAL_FIT_TO_MONITOR,
        "autoplay": GLOBAL_ANIM_AUTOPLAY,
    }
)

# Every viz-setting param, in every encoding — the settings half of a link.
SHARE_PARAMS: Mapping[str, str] = MappingProxyType(
    {
        **SHARE_TOGGLE_PARAMS,
        **SHARE_VALUE_PARAMS,
        **SHARE_INT_PARAMS,
        **SHARE_FLOAT_PARAMS,
        **SHARE_INT_RANGE_PARAMS,
        **SHARE_FLOAT_RANGE_PARAMS,
    }
)

# Params `_apply_url_preset` / `_apply_url_trial_selection` accept but that are
# not viz settings (the data source + which trial to land on).
URL_SELECTION_PARAMS = frozenset(
    {
        PARAM_SOURCE,
        PARAM_PARTICIPANT,
        PARAM_TRIAL,
        PARAM_TRIAL_ID,
        PARAM_TAB,
        PARAM_ONESTOP_VARIANT,
        PARAM_ONESTOP_REGIME,
        PARAM_ONESTOP_PARTS,
    }
)

# The exact key set of `url_state._URL_PRESETS` — every param a deep link can
# carry that presets a widget.
URL_PRESET_PARAMS = frozenset(SHARE_PARAMS) | {PARAM_HIDE_FIXATION_NUMBERS}

# The exact param set `_build_share_query` emits for a fully-populated session
# on a shareable source. `trial` is absent on purpose: Share writes the
# canonical `trial_id` instead of a slider index.
SHARE_QUERY_PARAMS = frozenset(SHARE_PARAMS) | (URL_SELECTION_PARAMS - {PARAM_TRIAL})

# Session keys `_URL_BOUNDED` clamps on the way in (a hand-crafted link with an
# out-of-range value would otherwise crash the widget on render).
URL_BOUNDED_STATE_KEYS = frozenset(
    {
        GLOBAL_LINE_SPACING,
        GLOBAL_SACCADE_WIDTH,
        GLOBAL_ORDER_FONT_SIZE,
        GLOBAL_ANIM_GRID_STEP_MS,
        GLOBAL_ANIM_MAX_FRAMES,
        GLOBAL_MARKER_SIZE_RANGE,
        GLOBAL_FIXATION_OPACITY,
        GLOBAL_STIMULUS_IMAGE_OPACITY,
        GLOBAL_STIMULUS_IMAGE_OFFSET_X,
        GLOBAL_STIMULUS_IMAGE_OFFSET_Y,
        GLOBAL_STIMULUS_IMAGE_SCALE,
    }
)

# Session keys a deep link seeds beyond the viz settings: the trial picker, the
# public-OneStop source options, and the two side-effect keys (`global_advanced`
# opens the Advanced expander when a colorscale is linked; `_deeplink_participant`
# is the one-shot capture the OneStop shard fast-path keys off).
URL_SEEDED_STATE_KEYS = frozenset(
    {
        SINGLE_SELECT_TRIAL_MODE,
        SINGLE_PARTICIPANT,
        SINGLE_SLIDER,
        SINGLE_ANIMATE,
        ONESTOP_VARIANT,
        ONESTOP_REGIME,
        ONESTOP_PARTS,
        DEEPLINK_PARTICIPANT,
        GLOBAL_ADVANCED,
    }
)

# ---------------------------------------------------------------------------
# 💾 Save & restore
# ---------------------------------------------------------------------------
# The JSON schema version stamped by both writers and understood by the reader.
# Bumping it in url_state without registering a migration (or without updating
# this constant) is the failure the contract test catches.
PLOT_CONFIG_SCHEMA_VERSION = 2

# `cmp{idx}_*` templates the config's `compare` list restores, per entry.
COMPARE_STATE_KEY_TEMPLATES = frozenset(
    {
        CMP_FIX_COLOR,
        CMP_SACCADE_COLOR,
        CMP_SACCADE_STYLE,
        CMP_SACCADE_WIDTH,
        CMP_MARKER_SIZE_RANGE,
        CMP_HOLLOW,
        CMP_OPACITY,
    }
)

# Every `global_*` session key `_restore_plot_config` writes from a complete,
# fully-valid saved config. Anything missing here that the reader writes (or
# vice versa) means the saved-config format moved.
PLOT_CONFIG_STATE_KEYS = frozenset(
    {
        # layers
        GLOBAL_SHOW_WORDS,
        GLOBAL_SHOW_LABELS,
        GLOBAL_SHOW_FIX,
        GLOBAL_SHOW_ORDER,
        GLOBAL_SHOW_SACCADES,
        GLOBAL_SHOW_SACCADE_ARROWS,
        GLOBAL_SHOW_HEATMAP,
        GLOBAL_SHOW_RAW_GAZE,
        GLOBAL_SHOW_STIMULUS_IMAGE,
        GLOBAL_FIT_TO_MONITOR,
        GLOBAL_ANIM_AUTOPLAY,
        # coloring
        GLOBAL_PALETTE,
        GLOBAL_COLOR_BY,
        GLOBAL_HEATMAP_STYLE,
        GLOBAL_HEATMAP_NORM,
        GLOBAL_HEATMAP_METRIC,
        GLOBAL_SHOW_COLORBARS,
        GLOBAL_FIXATION_COLORSCALE,
        GLOBAL_HEATMAP_COLORSCALE,
        GLOBAL_FIXATION_COLOR_RANGE,
        GLOBAL_HEATMAP_COLOR_RANGE,
        GLOBAL_SACCADE_COLOR,
        GLOBAL_SACCADE_STYLE,
        GLOBAL_SACCADE_WIDTH,
        GLOBAL_SACCADE_RENDER_MODE,
        GLOBAL_SACCADE_COLOR_MODE,
        GLOBAL_SACCADE_TYPE_LEGEND,
        GLOBAL_SACCADE_CLASS_COLOR_FORWARD,
        GLOBAL_SACCADE_CLASS_COLOR_SKIP,
        GLOBAL_SACCADE_CLASS_COLOR_REFIXATION,
        GLOBAL_SACCADE_CLASS_COLOR_RETURN_SWEEP,
        GLOBAL_SACCADE_CLASS_COLOR_REGRESSION,
        GLOBAL_FIXATION_SNAP_TO_WORD,
        GLOBAL_ALIGN_ALGORITHM,
        GLOBAL_ALIGN_CONNECTORS,
        GLOBAL_FIXATION_SYMBOL,
        GLOBAL_FIXATION_COLOR,
        GLOBAL_HOLLOW_FIXATIONS,
        GLOBAL_FIXATION_OPACITY,
        GLOBAL_STIMULUS_IMAGE_OPACITY,
        GLOBAL_STIMULUS_IMAGE_OFFSET_X,
        GLOBAL_STIMULUS_IMAGE_OFFSET_Y,
        GLOBAL_STIMULUS_IMAGE_SCALE,
        GLOBAL_COLORBAR_ORIENTATION,
        GLOBAL_COLORBAR_TICKANGLE,
        GLOBAL_COLORBAR_TICKFONT_SIZE,
        # sizing
        GLOBAL_MARKER_SIZE_RANGE,
        GLOBAL_ORDER_FONT_SIZE,
        GLOBAL_ORDER_FONT_COLOR,
        GLOBAL_BASE_FONT_SIZE,
        # animation
        GLOBAL_ANIM_GRID_STEP_MS,
        GLOBAL_ANIM_MAX_FRAMES,
        # canvas_px + axes
        GLOBAL_CANVAS_WIDTH,
        GLOBAL_CANVAS_HEIGHT,
        GLOBAL_MONITOR_WIDTH_MM,
        GLOBAL_VIEWING_DISTANCE_MM,
        GLOBAL_DISPLAY_DPI,
        GLOBAL_STIMULUS_FONT_PT,
        GLOBAL_USE_STIMULUS_FONT_PT,
        GLOBAL_X_FIELD,
        GLOBAL_Y_FIELD,
        # text
        GLOBAL_SCALE_TEXT_TO_BOXES,
        GLOBAL_LINE_SPACING,
        GLOBAL_FONT_FAMILY,
        GLOBAL_TEXT_COLOR,
        GLOBAL_WORD_HOVER_FIELDS,
        GLOBAL_FIXATION_HOVER_FIELDS,
        # highlighting
        GLOBAL_CRITICAL_SPAN_STYLE,
        GLOBAL_HIGHLIGHT_COLUMN,
        GLOBAL_HIGHLIGHT_TEXT_COLOR,
        GLOBAL_BG_CHOICE,
        GLOBAL_BG_CUSTOM,
        GLOBAL_SPAN_BORDER_COLOR,
        GLOBAL_FIXCLASS_SHORT_MODE,
        GLOBAL_FIXCLASS_SHORT_THRESHOLD_MS,
        GLOBAL_FIXCLASS_SHORT_SYMBOL,
        GLOBAL_FIXCLASS_SHORT_COLOR,
        GLOBAL_FIXCLASS_LONG_MODE,
        GLOBAL_FIXCLASS_LONG_THRESHOLD_MS,
        GLOBAL_FIXCLASS_LONG_SYMBOL,
        GLOBAL_FIXCLASS_LONG_COLOR,
        GLOBAL_FIXCLASS_OOB_MODE,
        GLOBAL_FIXCLASS_OOB_SYMBOL,
        GLOBAL_FIXCLASS_OOB_COLOR,
    }
)

# Non-`global_*` keys the same restore writes: the trial picker (`selection`)
# and the annotation store (`annotations`). The `col_map_*` keys it seeds are
# data-dependent — `COLUMN_MAPPING_PREFIX` is the contract there.
PLOT_CONFIG_OTHER_STATE_KEYS = frozenset(
    {
        SINGLE_SELECT_TRIAL_MODE,
        SINGLE_TRIAL_ID,
        TRIAL_ANNOTATIONS,
    }
)


def compare_state_keys(index: int) -> frozenset:
    """The `cmp{index}_*` session keys one `compare` config entry restores."""
    return frozenset(t.format(idx=index) for t in COMPARE_STATE_KEY_TEMPLATES)
