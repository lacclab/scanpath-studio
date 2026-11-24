"""Tab rendering functions for the Scanpath Studio app."""

from __future__ import annotations

import base64
import contextlib
import functools
import hashlib
import html
import io
import itertools
import json
import pickle
import re
import warnings
import zlib
from collections import Counter
from collections.abc import Callable, Hashable
from contextvars import ContextVar
from dataclasses import dataclass, replace
from dataclasses import fields as dataclass_fields
from functools import partial
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import plotly.io as pio
import streamlit as st

from scanpath_studio import (
    alignment,
    chart_axes,
    corpus_navigation,
    corpus_overview,
    dataset_credit,
    loading,
    progress,
    replay_frames,
    ui_mode,
)
from scanpath_studio import metadata as _metadata_mod
from scanpath_studio.aggregation import (
    MEASURES,
    RATE_SERIES,
    READING_TIME_ESTIMATED,
    GroupResolution,
    Measure,
    apply_group,
    available_features,
    available_measures,
    cohort_word_profile,
    corpus_text_column,
    distinct_group_labels,
    effective_spread,
    ensure_fixation_enrichment,
    group_mask,
    group_mean_difference,
    group_word_difference,
    landing_positions,
    measure_values,
    metric_by_trial_index,
    metric_over_time,
    on_reading_key,
    paired_group_summary,
    per_participant_trend,
    per_reader_word_measure,
    progressive_regressive_counts,
    reader_means,
    reader_summary,
    reader_summary_table,
    reader_vs_cohort_values,
    reading_word_contributions,
    resolve_group_spec,
    saccade_vs_duration,
    stimulus_revisions,
    text_read_counts,
    text_screen_options,
    trial_summary_table,
    two_group_values,
    two_group_word_profiles,
    within_reader_contrast,
    word_box_aggregate,
    word_measure_vs_feature,
    word_rate_profile,
)
from scanpath_studio.analysis_recipe import (
    REPLAYABLE_VIEWS,
    analysis_choices,
    build_analysis_recipe,
    group_definition,
    recipe_file_name,
    result_counts,
)
from scanpath_studio.animation_export import (
    CHROME_INSTALL_HINT,
    AnimationBudgetError,
    AnimationExportError,
    chrome_available,
    clip_frame_count,
    export_animation,
    mime_for,
)
from scanpath_studio.annotations import (
    filter_keys,
    render_trial_annotations,
)
from scanpath_studio.cite_button import render_cite_button
from scanpath_studio.code_snippet import (
    SNIPPET_STATE_KEY,
    UNPUBLISHED_SETTINGS,
    CompareTarget,
    FigureState,
)
from scanpath_studio.column_names import EMPTY as EMPTY_NAMES
from scanpath_studio.column_names import (
    ROLE_LABELS,
    ColumnNames,
    across_tables,
    active_all,
    active_figure_labels,
    as_written,
    from_schema,
    is_multipleye_entry,
    source_schema,
    stored_source_recipe,
)
from scanpath_studio.column_names import active as active_column_names
from scanpath_studio.compare_source import (
    COMPARE_SOURCE_KEY,
    COMPARE_SOURCE_RESOLVED_KEY,
    THIS_DATASET,
    SecondaryDataset,
    load_secondary_dataset,
    secondary_dataset_options,
    snapshot_for,
)
from scanpath_studio.computations import measure_description, measure_entry
from scanpath_studio.constants import (
    AUTHOR_CHOICE,
    DATA_INSPECTION_KEY,
    DATA_RUN_SHEETS_KEY,
    DATASET_EDITOR_OPEN_KEY,
    DEFAULT_DURATION_SIZE_LEGEND,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_DURATION_RANGE,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_MARKER_SIZE_SCALE,
    DEFAULT_SACCADE_WIDTH,
    DEFAULT_SNAP_POSITION,
    FIXATION_LABEL_OPTIONS,
    FIXATION_OPACITY,
    FOCUS_MAPPING_KEY,
    HIGHLIGHTED_TEXT_COLOR,
    ICONS,
    MANUAL_SAMPLE_CHOICE,
    PLOTLY_CONFIG,
    SACCADE_CLASS_COLORS,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    SELECTOR_ROW_GRID,
    SELECTOR_ROW_TRIO,
    SELECTOR_SCREEN_TRACK,
    SETUP_OVERRIDE_FOR_KEY,
    SUBTAB_ANNOTATIONS,
    SUBTAB_COMPARISONS,
    SUBTAB_EXPORT,
    SUBTAB_LINE_ASSIGNMENT,
    SUBTAB_MORE,
    SUBTAB_SHARE,
    SUBTAB_STIMULUS,
    SYNTHETIC_CHOICE,
    TRIAL_IDENTITY_CHECK_KEY,
    TRIAL_IDENTITY_FULL_KEY,
    UNIFORM_COLOR_FIELD,
    UPLOAD_FILE_TYPES,
    WORD_BOX_COLOR,
    WORD_BOX_FILL_COLOR,
    WORD_BOX_FILL_OPACITY,
    WORD_BOX_LINE_OPACITY,
    WORD_KEY,
    WORD_LABEL_COLOR,
    compare_palette_color,
    computed_measures_enabled,
    derived_analysis_tables_enabled,
    drift_correction_enabled,
    icon_html,
    md_literal,
    plural,
    preprocessing_enabled,
    sentence_analysis_enabled,
    similarity_enabled,
    spoken,
    upload_limit_mb,
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    SUMMARY_CHIP_FIELDS,
    TOUCHED_FIELDS_KEY,
    WORD_FIELD_SPECS,
    _check_row,
    _collect_compare_styles,
    _drop_stale,
    _gated_help,
    _labeled,
    _numeric_slider,
    _popover_rows,
    _text_field_and_frame,
    active_filter_items,
    chip_field_label,
    clear_trial_filters,
    column_mapping_ui,
    compare_b_filters,
    corpus_style_controls,
    current_dataset_name,
    field_help,
    format_filter_item,
    has_active_trial_filters,
    leave_animation,
    metadata_readings,
    on_animation_change,
    pin_word_heatmap_range,
    plot_popover_on_change,
    read_trial_filters,
    render_compare_filters,
    render_narrow_by,
    render_pattern_help,
    render_pattern_input,
    render_plot_controls,
    render_trial_chip_picker,
    render_trial_filters,
    render_viz_reset,
    selected_hover_text,
    shadow_widget_key,
    static_plot_view,
    write_through,
)
from scanpath_studio.data import (
    AOI_TRIAL_ID,
    IDENTITY_SCHEMA_FIELDS,
    READING_MEASURE_FIELDS,
    READING_MEASURE_KEYS,
    TEXT_ID_MAPPED,
    UNFIXATED_BLANK_MEASURES,
    ReadPlan,
    StimulusJoinWarning,
    aggregate_char_boxes,
    assign_derived,
    assign_fingerprint,
    brought_reading_measures,
    carries_mapped_text,
    coerce_bool_or_na,
    compute_word_metrics,
    derive_trial_index,
    distinct_key_codes,
    drop_internal_columns,
    empty_fixations_frame,
    empty_words_frame,
    filter_to_keys_cached,
    forget_frame_cache,
    frame_cache,
    frame_fingerprint,
    harmonize_frames_reporting,
    has_explicit_trial_index,
    hashable_key,
    identity_text_plan,
    normalize_fixations,
    normalize_raw_gaze,
    normalize_words,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    read_tables,
    remap_normalized_frame,
    repeat_bases,
    respell_reading,
    select_trials_cached,
    set_digest,
    shareable_frame,
    text_ids,
    timestamps_synthesized,
    trial_filter_conflict_note,
    trial_filter_params,
    trial_id_series,
    trial_keys,
    trial_mapping_columns,
    trial_order_label,
    unplaced_fixations_issue,
    user_columns,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
    verbatim_text_plan,
    with_onset_provenance,
)
from scanpath_studio.debug_log import timed
from scanpath_studio.export import (
    DEFAULT_PRINT_DPI,
    HTML_SELF_CONTAINED_KEY,
    BundleContents,
    ExportOptions,
    annotate_figure,
    apply_export_scope,
    bulk_export,
    bundle_contents,
    count_export,
    describe_plan,
    figure_text_style,
    html_plotlyjs,
    naming_example,
    pattern_fields,
    plan_from_counts,
    print_width_px,
    render_export_options,
    render_pattern,
    render_static_figure_bytes,
    screen_choices,
    strip_local_paths,
    summarize_export,
)
from scanpath_studio.export_archive import DiskBundle, build_download
from scanpath_studio.export_status import (
    EXPORTER_VERSION,
    ExportStage,
    ExportStatus,
    export_signature,
    progress_caption,
)
from scanpath_studio.fields import (
    LABEL_GAP,
    PANEL_LABEL_W,
    labeled,
    panel_field,
    row_label,
    switch,
)
from scanpath_studio.figure_views import STATIC_COMPARISON_LAYER_STYLES
from scanpath_studio.file_citation import png_text_chunks, stamp_html, svg_metadata
from scanpath_studio.html_embed import embed_html_iframe, plotlyjs_script
from scanpath_studio.illustration import illustration_reasons, resolve_label_reasons
from scanpath_studio.multipart import (
    SCREEN_ID,
    SCREEN_INDEX,
    extract_part,
    has_screen_identity,
    part_catalog,
    screen_canvas_size,
    screen_rows,
)
from scanpath_studio.plot_navigation import detail_section
from scanpath_studio.plots import (
    COLORBAR_DEFAULTS,
    COMPARE_FILTER_STYLE_KEYS,
    DESIGN_CHOICE_FIELDS,
    STATIC_FIGURE_OPTIONS,
    TEXT_STYLE_FIELDS,
    FigureSettings,
    _discard_flagged_fixations,
    _maybe_add_duration_key,
    add_illustration_label,
    animation_clip_frame_ms,
    animation_timeline_summary,
    apply_legend_layout,
    break_at_gaps,
    build_scanpath_replay,
    category_vocabulary,
    make_comparison_figure,
    make_density_scatter_figure,
    make_difference_profile_figure,
    make_distribution_figure,
    make_feature_scatter_figure,
    make_landing_curve_figure,
    make_metric_convergence_figure,
    make_paired_bars_figure,
    make_progression_figure,
    make_scanpath_figure,
    make_small_multiples_figure,
    make_trend_figure,
    make_word_matrix_heatmap,
    make_word_profile_figure,
    make_word_rate_figure,
    normalize_legend_layout,
    reading_stimulus_image,
    replay_page,
    replay_page_box,
    replay_size_key_range,
    set_replay_clock,
    stimulus_image_settings,
)
from scanpath_studio.session_keys import (
    COMPARE_IDENTITY_STATE_KEY,
    CORPUS_MEASURE,
    EXPORT_FIGURE_DPI,
    EXPORT_FIGURE_WIDTH,
    EXPORT_FIGURE_WIDTH_UNIT,
    PENDING_COMPARE_STATE_KEY,
    SETUP_PROVENANCE_STATE_KEY,
    SINGLE_ANIMATE,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
    SINGLE_SHOW_CHIPS,
    SINGLE_TRIAL_ID,
)
from scanpath_studio.similarity import (
    METRICS,
    compute_similarity_table,
    nld_by_fixation_index,
    nld_by_time,
)
from scanpath_studio.styles import mapping_menu_css, widen_menu
from scanpath_studio.utils import (
    COMPARE_DATASET_SEP,
    COMPARE_OPTIONS_SNAPSHOT_KEY,
    COMPARE_STEP_LINK_KEY,
    SAME_PARTICIPANT_MARKER,
    SAME_TEXT_MARKER,
    TRIAL_SORT_DATA_ORDER,
    TRIAL_SORT_DEFAULT,
    align_compare_columns,
    at_list_end,
    build_combo_options_for,
    build_comparison_options,
    compare_step_linked,
    compute_trial_stats,
    extract_trial,
    friendly_trial_label,
    qualified_participant,
    qualify_for_compare,
    reading_key,
    row_tail,
    safe_summary,
    select_trial,
    self_compare_participant,
    separate_self_compare,
    sort_trial_options,
    split_reading_key,
    step_within,
    trial_id_help,
    trial_id_layout,
    trial_id_shown,
    trial_options_snapshot_key,
    trial_sort_is_set,
    trial_sort_keys,
    unqualify_for_export,
)

if TYPE_CHECKING:
    import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# Single Trial Tab
# -----------------------------------------------------------------------------


#: Published section names for bookmarks, recipes and tutorial steps.
CORPUS_SUBTABS = ("Overview", "Per text", "Per sentence", "Per participant", "Groups")


def corpus_subtabs() -> tuple[str, ...]:
    """The published sections available in this build."""
    return tuple(
        name
        for name in CORPUS_SUBTABS
        if name != "Per sentence" or sentence_analysis_enabled()
    )


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


def _step_screen(key_prefix: str, options: tuple[str, ...], delta: int) -> None:
    """Move the multipart navigator without touching the parent trial picker."""
    if not options:
        return
    id_key = f"{key_prefix}_screen_id"
    current = str(st.session_state.get(id_key, options[0]))
    position = options.index(current) if current in options else 0
    st.session_state[id_key] = options[max(0, min(len(options) - 1, position + delta))]


def _render_screen_navigator(
    catalog: pd.DataFrame, *, key_prefix: str = "single", host=None
) -> str | None:
    """Pick/step navigator for one logical multipart trial.

    A compact cell at the trial row's right end — ``host`` is that cell,
    reserved by ``utils.select_trial``'s ``trailing_renderer`` — so the screens
    do not cost the plot a row per scanpath. A trial has few screens, with
    short names, so a narrow dropdown + ◀ ▶ is enough, and the dropdown's menu
    opens wider than the control (`styles.py`), so the names are still read in
    full.

    ``key_prefix`` (default ``"single"``, A's own) gives scanpath B in Compare
    mode its own independent navigator (``"single_compare"``) over its own
    multipart trial.
    """
    host = st if host is None else host
    id_key = f"{key_prefix}_screen_id"
    if catalog.empty:
        st.session_state.pop(id_key, None)
        return None
    options = tuple(catalog[SCREEN_ID].astype(str))
    current = st.session_state.get(id_key)
    if current not in options:
        st.session_state[id_key] = options[0]
    labels = {
        str(row.screen_id): f"{int(row.screen_index)}/{len(catalog)} · {row.screen_id}"
        for row in catalog.itertuples()
    }
    position = options.index(str(st.session_state[id_key]))
    cell = host.container(
        key=f"{key_prefix}_screen_cell",
        horizontal=True,
        vertical_alignment="bottom",
        gap="small",
    )
    selected = cell.selectbox(
        # B's says whose screen it is, like the rest of B's row.
        "**Screen B**" if key_prefix == "single_compare" else "**Screen**",
        options,
        key=id_key,
        format_func=labels.get,
        help="Which screen of this trial to draw. The trial stays selected.",
    )
    # Narrow, but its menu opens as wide as the longest screen name.
    widen_menu(id_key, labels.values())
    # Both steps in ONE keyed `railbtn_*` container, so they take the pill
    # shape and 3px spacing of the ◀ ▶ ⇅ cluster beside them.
    trail = cell.container(key=f"railbtn_{key_prefix}_screen_trail", width="content")
    # `spoken` names the glyph buttons for screen readers.
    trail.button(
        f"◀ {spoken('Previous screen')}",
        wrap=True,
        key=f"{key_prefix}_screen_previous",
        help="Previous screen of this trial",
        disabled=position == 0,
        on_click=_step_screen,
        args=(key_prefix, options, -1),
    )
    trail.button(
        f"▶ {spoken('Next screen')}",
        wrap=True,
        key=f"{key_prefix}_screen_next",
        help="Next screen of this trial",
        disabled=position == len(options) - 1,
        on_click=_step_screen,
        args=(key_prefix, options, 1),
    )
    return str(selected)


def _part_catalog_for_display(
    words: pd.DataFrame, fixations: pd.DataFrame, raw_gaze: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Use MultiplEYE's fixation-onset order if cached word order is stale."""
    try:
        return part_catalog(words, fixations, raw_gaze)
    except ValueError as exc:
        if (
            str(exc) == "Multipart metadata 'screen_index' conflicts across tables."
            and "screen_kind" in fixations.columns
        ):
            return part_catalog(fixations, raw_gaze)
        raise


def _screen_catalog_status(words, fixations, raw_gaze) -> tuple[pd.DataFrame, str]:
    try:
        return _part_catalog_for_display(words, fixations, raw_gaze), ""
    except ValueError as exc:
        return pd.DataFrame(), f"{exc} Check the screen mappings in Edit dataset."


def _embed_html_iframe(
    html: str, *, height: int, alt: str | None = None, focusable: bool = False
) -> None:
    """Local alias for the shared iframe helper."""
    embed_html_iframe(html, height=height, alt=alt, focusable=focusable)


def _figure_alt(fig, fallback: str) -> str:
    """The alt text of a rendered figure: its title as plain text, else ``fallback``.

    A figure whose title the user switched off still gets a description, which
    is what ``fallback`` names."""
    title = getattr(getattr(fig.layout, "title", None), "text", None)
    return _plain_title(title) or fallback


def _scanpath_alt(participant, text, n_fixations: int, figure=None) -> str:
    """Describe marks that the current layers and axes actually place on the figure."""

    def count(label, n):
        return f"{n:,} {label}{'' if n == 1 else 's'}"

    def coordinates(values):
        # The Streamlit cache can restore Plotly's typed-array encoding where
        # a freshly built figure holds an ndarray.
        if isinstance(values, dict) and "bdata" in values:
            return np.frombuffer(
                base64.b64decode(values["bdata"]), dtype=values["dtype"]
            )
        return pd.to_numeric(np.asarray(values), errors="coerce")

    name = f"Scanpath of participant {participant} on text {text}"
    if figure is None:
        return f"{name}: {count('fixation', n_fixations)}"
    axes = [
        getattr(getattr(figure.layout, axis).title, "text", None)
        for axis in ("xaxis", "yaxis")
    ]
    if all(axes):
        name = f"{_plain_title(axes[1])} by {_plain_title(axes[0])} for participant {participant} on text {text}"
    shown = {}
    for trace in figure.data:
        if (
            trace.name in ("Fixations", "Raw gaze")
            and trace.x is not None
            and trace.y is not None
        ):
            xs, ys = coordinates(trace.x), coordinates(trace.y)
            shown[trace.name] = int(np.count_nonzero(np.isfinite(xs) & np.isfinite(ys)))
    points = shown.get("Fixations", 0)
    if not n_fixations:
        fixation_text = "no fixations recorded"
    elif points == n_fixations:
        fixation_text = count("fixation", points)
    else:
        fixation_text = f"{count('fixation', points)} shown of {n_fixations:,} recorded"
    details = []
    if samples := shown.get("Raw gaze"):
        details.append(count("raw gaze sample", samples))
    details.append(fixation_text)
    return f"{name}: {', '.join(details)}"


def _plain_title(title: str | None) -> str:
    """A Plotly title as words for a screen reader: ``<br>`` / ``<sup>``
    markup and entities removed."""
    text = html.unescape(
        re.sub(r"<br\s*/?>", " — ", str(title or ""), flags=re.IGNORECASE)
    )
    return " ".join(re.sub(r"<[^>]+>", "", text).split())


# Plotly's own zoom only rescales the *axes*, so the word boxes and saccades
# spread apart while the fixation markers, label font and line widths stay
# pinned at the screen-pixel sizes they were built with — the plot stops being
# true to scale the moment you zoom. These modebar buttons are therefore
# removed and `dragmode` is switched off (in the template below), and
# magnification is done by scaling the whole rendered block instead, exactly
# like the fit-to-column transform `_render_true_scale_chart` applies.
_NATIVE_ZOOM_BUTTONS = (
    "zoom2d",
    "pan2d",
    "zoomIn2d",
    "zoomOut2d",
    "autoScale2d",
    "resetScale2d",
)

_ZOOM_MAX = 8.0

_TRUE_SCALE_TEMPLATE = """
<style>
  /* The frame is the figure's height + 12px; the browser's default 8px
     body margin, top and bottom, would make the page 4px taller than that,
     so a figure drawn at full size would scroll by 4px. */
  html, body { margin: 0; }
  /* A placeholder at the figure's size while plotly.js loads and the
     figure draws — seconds for a big replay. It fades in only after 300 ms, so
     a small figure never flickers, and goes on Plotly's first draw. Ahead of
     the markup on purpose: the figure (megabytes for a replay) sits between
     the placeholder and the script, and a rule parsed after it would leave
     the placeholder unstyled — invisible — for exactly that wait. */
  @keyframes sps-skel-in { to { opacity: 1; } }
  @keyframes sps-skel-pulse { 50% { opacity: 0.55; } }
  #skel-__KEY__ { position: absolute; inset: 0; z-index: 4; pointer-events: none;
    opacity: 0; border-radius: 8px; background: rgba(128, 128, 128, 0.10);
    animation: sps-skel-in .2s ease .3s forwards,
               sps-skel-pulse 1.6s ease-in-out .5s infinite; }
  @media (prefers-reduced-motion: reduce) {
    #skel-__KEY__ { animation: sps-skel-in .01s linear .3s forwards; } }
</style>
<div id="wrap-__KEY__" style="position:relative;width:100%;">
  __TRANSPORT__
  <div id="fit-__KEY__" style="width:100%;overflow:hidden;position:relative;">
    <div id="skel-__KEY__" aria-hidden="true"></div>
    <div id="size-__KEY__" style="width:__W__px;height:__H__px;">
      <div id="box-__KEY__" style="width:__W__px;height:__H__px;
           transform-origin:top left;">__PLOT__</div>
    </div>
  </div>
  __TOOLBAR__
</div>
<script>
(function() {
  var W = __W__, H = __H__, ZMAX = __ZMAX__, ZOOMABLE = __ZOOMABLE__;
  var GROW = __GROW__, FIT = __FIT__, FIT_MIN = __FIT_MIN__;
  // A replay's toolbar (`plots.REPLAY_TOOLBAR_PX`) sits above the figure, at
  // its own size: the figure is fitted to what is left under it.
  var BAR = __BAR__;
  var transport = document.getElementById("truescale-__KEY__-transport");
  var outer = document.getElementById("fit-__KEY__");
  var size = document.getElementById("size-__KEY__");
  var box = document.getElementById("box-__KEY__");
  var label = document.getElementById("zoomlabel-__KEY__");
  var wrap = document.getElementById("wrap-__KEY__");
  var zoom = 1, base = 1;
  // Fullscreen state. Declared up here because `baseScale` branches on
  // it, and `render()` runs before the fullscreen wiring below.
  var fsOn = false, fsSavedStyle = null, fsSavedZoom = 1, fsSavedOverflow = null;

  function baseScale() {
    var avail = outer.clientWidth || W;
    // Fullscreen fits *both* dimensions and is allowed above 1x — the
    // point of it is to use the screen, and on a large monitor the fit-to-width
    // rule below would leave the figure at true size in the middle of it. Still
    // the one uniform transform, so the aspect ratio holds and boxes, markers,
    // strokes and text keep the same relationship to each other they have at 1x.
    if (fsOn) {
      var availH = (window.innerHeight || H) - 8 - BAR;
      return Math.min(avail / W, availH / H);
    }
    return __SCALE_JS__;
  }
  // How tall the figure may grow above true size: most of the browser
  // window's height, so a figure scaled up to its column still fits on
  // screen. Never below 1 — the height only ever limits growing. A figure
  // that `FIT`s the window takes `fitRoom()` instead.
  function growCap() {
    var vh = 0;
    try { vh = window.parent.innerHeight; } catch (e) { vh = 0; }
    var room = FIT ? fitRoom(vh) - BAR : 0;
    if (room > 0) { return Math.max(room, Math.min(FIT_MIN, H)) / H; }
    return Math.max(1, ((vh || H) * 0.85 - BAR) / H);
  }
  // The Scanpath view's figure (`fit_window`): the height left between its
  // top and the window's bottom once the subtab bar under it (Annotations …
  // Export) and whatever sits between the two are kept in view — so the bar
  // is on screen without scrolling. Measured from the page's top, not the
  // viewport's, so scrolling never resizes it. It may go below true size
  // (as fitting the column's width already does), but not under `FIT_MIN`
  // px. 0 when there is nothing to measure.
  function fitRoom(vh) {
    var fr = null;
    try { fr = window.frameElement; } catch (e) { fr = null; }
    if (!fr || !vh) { return 0; }
    var doc = fr.ownerDocument, box = fr.getBoundingClientRect();
    var scrolled = 0;
    for (var p = fr.parentElement; p; p = p.parentElement) {
      scrolled += p.scrollTop || 0;
    }
    var below = 0, bars = doc.querySelectorAll('[role="tablist"]');
    for (var i = 0; i < bars.length; i++) {
      var bar = bars[i].getBoundingClientRect();
      if (bar.top >= box.bottom - 1) { below = bar.bottom - box.bottom; break; }
    }
    return vh - (box.top + scrolled) - below - 12 - 16;
  }
  // The frame follows the figure's fitted height, so a figure scaled down
  // leaves no band below it and one scaled up is not cut off. Not in
  // fullscreen, which owns the frame's box.
  function fitFrame() {
    if (!GROW || fsOn) { return; }
    var fr = null;
    try { fr = window.frameElement; } catch (e) { fr = null; }
    if (!fr) { return; }
    var want = Math.round(H * base) + 12 + BAR + "px";
    if (fr.style.height !== want) { fr.style.height = want; }
    // Streamlit sizes the frame's element container from the height it was
    // embedded at; it has to follow, or the frame spills over what is below.
    var holder = fr.parentElement;
    if (holder && holder.getAttribute("data-testid") === "stElementContainer" &&
        holder.style.height !== want) {
      holder.style.height = want;
    }
  }
  // One uniform transform for fit x zoom: boxes, fixations, labels and stroke
  // widths all magnify together, so the figure stays true to scale.
  function render() {
    base = baseScale();
    var s = base * zoom;
    box.style.transform = "scale(" + s + ")";
    size.style.width = Math.round(W * s) + "px";
    size.style.height = Math.round(H * s) + "px";
    // Centred in its column; a zoomed figure wider than the column starts
    // at its left edge, so the scroll reaches all of it.
    var left = Math.max(0, Math.round((outer.clientWidth - W * s) / 2));
    size.style.marginLeft = left + "px";
    var fitLeft = Math.max(0, Math.round((outer.clientWidth - W * base) / 2));
    var zb = wrap && wrap.querySelector("[data-toolbar]");
    if (zb && !(transport && transport.contains(zb))) {
      zb.style.left = fitLeft + 4 + "px";
    }
    // The toolbar spans the fitted figure, whatever the zoom.
    if (transport) {
      transport.style.marginLeft = fitLeft + "px";
      transport.style.width = Math.min(outer.clientWidth, Math.round(W * base)) + "px";
    }
    outer.style.height = Math.round(H * base) + "px";
    fitFrame();
    outer.style.overflow = zoom > 1.001 ? "auto" : "hidden";
    outer.style.cursor = zoom > 1.001 ? "grab" : "";
    if (label) { label.textContent = Math.round(zoom * 100) + "%"; }
  }
  // Zoom about a viewport-relative anchor so the point under the cursor (or the
  // centre, for the buttons) stays put.
  function setZoom(next, ax, ay) {
    next = Math.min(ZMAX, Math.max(1, next));
    if (Math.abs(next - zoom) < 1e-6) { return; }
    var prev = base * zoom;
    zoom = next;
    render();
    var ratio = (base * zoom) / prev;
    if (ax === undefined) { ax = outer.clientWidth / 2; ay = outer.clientHeight / 2; }
    outer.scrollLeft = (outer.scrollLeft + ax) * ratio - ax;
    outer.scrollTop = (outer.scrollTop + ay) * ratio - ay;
  }
  render();
  window.addEventListener("resize", render);
  // The column's width is the frame's own, but the height cap is the browser
  // window's, which can change without this frame resizing.
  // Removed when this document goes: the parent page outlives every figure a
  // rerun swaps into the frame, and would otherwise keep each one alive.
  if (GROW) {
    try {
      window.parent.addEventListener("resize", render);
      // A fitted figure also follows the page above and below it — a notice
      // appearing, the chips hidden — which moves it without a resize.
      if (FIT && window.ResizeObserver && window.frameElement) {
        var queued = false;
        var watch = new ResizeObserver(function() {
          if (queued) { return; }
          queued = true;
          requestAnimationFrame(function() { queued = false; render(); });
        });
        var main = window.frameElement.closest('[data-testid="stMain"]');
        watch.observe(main || window.frameElement.ownerDocument.body);
        window.addEventListener("pagehide", function() { watch.disconnect(); });
      }
      window.addEventListener("pagehide", function() {
        try { window.parent.removeEventListener("resize", render); } catch (e) {}
      });
    } catch (e) {}
  }
  setTimeout(render, 150);

  (function dropSkeleton() {
    var sk = document.getElementById("skel-__KEY__");
    if (!sk) { return; }
    var gd = document.getElementById("truescale-__KEY__");
    if (!gd || !gd._fullLayout) { setTimeout(dropSkeleton, 60); return; }
    sk.parentNode.removeChild(sk);
    // Tell the Streamlit page this figure has drawn: a trial change's card
    // waits for it (`loading.PLOT_DRAWN_EVENT`).
    try {
      window.parent.dispatchEvent(new window.parent.CustomEvent(
        "__DRAWN_EVENT__", { detail: window.frameElement }));
    } catch (e) {}
  })();

  if (!ZOOMABLE) { return; }

  // Trackpad pinch arrives as ctrl+wheel, so this covers pinch and Ctrl/Cmd +
  // scroll. A plain wheel is left alone: it scrolls (i.e. pans) the zoomed plot.
  outer.addEventListener("wheel", function(e) {
    if (!e.ctrlKey && !e.metaKey) { return; }
    e.preventDefault();
    var r = outer.getBoundingClientRect();
    setZoom(zoom * Math.exp(-e.deltaY * 0.0025), e.clientX - r.left, e.clientY - r.top);
  }, {passive: false});

  // Drag to pan once zoomed. Capture phase, because Plotly's drag layer sits on
  // top; the click is only swallowed once the pointer actually moves, so the
  // modebar and hover still work.
  var panning = false, moved = false, sx = 0, sy = 0, sl = 0, st = 0;
  outer.addEventListener("mousedown", function(e) {
    if (zoom <= 1.001 || e.button !== 0) { return; }
    panning = true; moved = false;
    sx = e.clientX; sy = e.clientY; sl = outer.scrollLeft; st = outer.scrollTop;
  }, true);
  document.addEventListener("mousemove", function(e) {
    if (!panning) { return; }
    var dx = e.clientX - sx, dy = e.clientY - sy;
    if (!moved && Math.abs(dx) + Math.abs(dy) < 3) { return; }
    moved = true;
    e.preventDefault();
    outer.style.cursor = "grabbing";
    outer.scrollLeft = sl - dx;
    outer.scrollTop = st - dy;
  }, true);
  document.addEventListener("mouseup", function() {
    panning = false;
    outer.style.cursor = zoom > 1.001 ? "grab" : "";
  }, true);

  function on(id, fn) {
    var el = document.getElementById(id + "-__KEY__");
    if (el) { el.addEventListener("click", fn); }
  }
  on("zoomin", function() { setZoom(zoom * 1.25); });
  on("zoomout", function() { setZoom(zoom / 1.25); });
  on("zoomreset", function() {
    zoom = 1; render(); outer.scrollLeft = 0; outer.scrollTop = 0;
  });

  // --- Fullscreen ---------------------------------------------------------
  // The plot lives in a same-origin iframe whose height Streamlit fixes, so
  // *the iframe element* is what has to grow — the figure alone cannot escape
  // it. Two ways up, tried in order: the real Fullscreen API on the frame, and
  // a fixed overlay for when a permissions policy blocks it (`st.iframe`
  // exposes no `allowfullscreen`, so that is a live possibility rather than a
  // theoretical one). Both leave the inside identical, so only `enter`/`exit`
  // differ; `applyFs` is the single place the view changes.
  var fsBtn = document.getElementById("fsbtn-__KEY__");

  function frameEl() { try { return window.frameElement; } catch (e) { return null; } }
  function parentDoc() { try { return window.parent.document; } catch (e) { return null; } }
  function nativeFs() {
    var pd = parentDoc();
    var fr = frameEl();
    return !!(pd && fr && pd.fullscreenElement === fr);
  }

  function applyFs(on) {
    if (fsOn === on) { return; }
    fsOn = on;
    // Zoom is reset on the way in and restored on the way out: "expand the
    // complete figure to the available screen" means the whole figure, and a
    // 3x zoom multiplied by the larger fullscreen fit would not be that.
    if (on) { fsSavedZoom = zoom; zoom = 1; } else { zoom = fsSavedZoom; }
    var b = document.body;
    b.style.margin = on ? "0" : "";
    b.style.height = on ? "100vh" : "";
    b.style.display = on ? "flex" : "";
    b.style.alignItems = on ? "center" : "";
    b.style.background = on ? "#fff" : "";
    if (wrap) { wrap.style.width = "100%"; }
    if (fsBtn) {
      fsBtn.innerHTML = on ? "&#10005;" : "&#9974;";
      fsBtn.title = on ? "Exit fullscreen (Esc)" : "Fullscreen";
    }
    render();
    outer.scrollLeft = 0; outer.scrollTop = 0;
    // Belt and braces, the way the initial mount already does it: the frame's
    // new box is not guaranteed to be laid out by the time the `render()` above
    // measures it, and a stale width fits the figure to the wrong viewport.
    if (window.requestAnimationFrame) { window.requestAnimationFrame(render); }
    setTimeout(render, 150);
  }

  function overlayOn(fr) {
    if (fsOn) { return; }
    var pd = parentDoc();
    fr.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;" +
      "z-index:2147483647;border:0;background:#fff;";
    if (pd && pd.body) {
      fsSavedOverflow = pd.body.style.overflow;
      pd.body.style.overflow = "hidden";
    }
    applyFs(true);
  }

  function overlayOff(fr) {
    fr.setAttribute("style", fsSavedStyle || "");
    var pd = parentDoc();
    if (pd && pd.body && fsSavedOverflow !== null) {
      pd.body.style.overflow = fsSavedOverflow;
      fsSavedOverflow = null;
    }
    applyFs(false);
  }

  function toggleFs() {
    var fr = frameEl();
    if (!fr) { return; }
    var pd = parentDoc();
    if (fsOn) {
      if (nativeFs() && pd.exitFullscreen) { pd.exitFullscreen(); }
      else { overlayOff(fr); }
      return;
    }
    fsSavedStyle = fr.getAttribute("style") || "";
    var req = fr.requestFullscreen || fr.webkitRequestFullscreen;
    if (!req) { overlayOn(fr); return; }
    try {
      var p = req.call(fr);
      if (p && p.catch) { p.catch(function() { overlayOn(fr); }); }
    } catch (e) { overlayOn(fr); return; }
    // A permissions policy can refuse *silently* rather than rejecting, which
    // would otherwise leave the button looking broken. If nothing happened by
    // the next few frames, take the overlay instead.
    setTimeout(function() { if (!fsOn && !nativeFs()) { overlayOn(fr); } }, 400);
  }

  if (fsBtn) { fsBtn.addEventListener("click", toggleFs); }

  // Native fullscreen is exited by Escape, the browser's own control, or our
  // button — all of which surface here, so the view follows the browser rather
  // than our idea of it.
  (function watchNative() {
    var pd = parentDoc();
    if (!pd) { return; }
    pd.addEventListener("fullscreenchange", function() {
      if (nativeFs()) { applyFs(true); }
      else if (fsOn && fsSavedStyle !== null) {
        var fr = frameEl();
        if (fr) { fr.setAttribute("style", fsSavedStyle); }
        applyFs(false);
      }
    });
  })();

  // The overlay has no browser-supplied Escape, so it needs its own — on both
  // documents, because focus may sit either side of the frame boundary.
  function onEsc(e) {
    if (e.key !== "Escape" || !fsOn || nativeFs()) { return; }
    var fr = frameEl();
    if (fr) { overlayOff(fr); }
  }
  document.addEventListener("keydown", onEsc);
  (function() {
    var pd = parentDoc();
    if (pd) { pd.addEventListener("keydown", onEsc); }
  })();

  // Switch off Plotly's own drag interactions so a drag on the plot pans this
  // block instead of box-zooming the axes (which would break the sizing).
  (function killNativeZoom() {
    var gd = document.getElementById("truescale-__KEY__");
    if (!window.Plotly || !gd || !gd._fullLayout) { setTimeout(killNativeZoom, 100); return; }
    window.Plotly.relayout(gd, {dragmode: false});
  })();
})();
</script>
"""

#: Where the zoom buttons sit: over the plot's top-left corner, or at the end
#: of a replay's toolbar row (`_true_scale_html`).
_ZOOM_TOOLBAR_FLOAT = "position:absolute;top:4px;left:4px;z-index:5;"
_ZOOM_TOOLBAR_IN_ROW = "order:99;flex:none;margin-left:auto;"

_ZOOM_TOOLBAR = """
  <div id="zoombar-__KEY__" data-toolbar style="position:absolute;top:4px;left:4px;z-index:5;
       display:flex;gap:2px;align-items:center;padding:2px 4px;
       font:11px/1.6 system-ui,sans-serif;color:#444;
       background:rgba(255,255,255,0.88);border:1px solid #ddd;border-radius:4px;">
    <button id="zoomout-__KEY__" title="Zoom out" aria-label="Zoom out" style="__BTN__">&minus;</button>
    <span id="zoomlabel-__KEY__" style="min-width:34px;text-align:center;">100%</span>
    <button id="zoomin-__KEY__" title="Zoom in" aria-label="Zoom in" style="__BTN__">+</button>
    <button id="zoomreset-__KEY__" title="Reset zoom" aria-label="Reset zoom" style="__BTN__">&#8635;</button>
    <button id="fsbtn-__KEY__" title="Fullscreen" aria-label="Fullscreen" style="__BTN__">&#9974;</button>
  </div>
"""

_ZOOM_BUTTON_CSS = (
    "border:1px solid #ddd;background:#fff;border-radius:3px;cursor:pointer;"
    "width:18px;height:18px;line-height:1;padding:0;color:#444;font-size:12px;"
)


def _true_scale_html(
    plot_html: str,
    *,
    key: str,
    width: int,
    height: int,
    max_height: int | None,
    zoomable: bool,
    fit_window: bool = False,
    toolbar: int = 0,
) -> tuple[str, int]:
    """Wrap a fixed-size Plotly div in the fit-to-column (+ zoom) transform.

    Pure so the embed markup is testable without a Streamlit run. Returns the
    HTML and the iframe height to reserve for it.

    ``fit_window`` (an uncapped figure only) sizes it to the window's height
    left under its top, keeping the subtab bar below it on screen (`fitRoom`).

    ``toolbar`` is the height in px of a replay's toolbar
    (`plots.replay_page_box`): a slot that tall goes above the figure, outside
    the transform, for the replay player to draw it in — at its own size,
    neither scaled nor zoomed with the figure.
    """
    toolbar = max(int(toolbar or 0), 0)
    if max_height is not None:
        scale_js = f"Math.min(1, avail / W, {int(max_height)} / H)"
        iframe_height = int(max_height) + 12 + toolbar
    else:
        # Fills the column's width — above true size too, while it still fits
        # the window's height (`growCap`); the script sizes the frame to match.
        scale_js = "Math.min(avail / W, growCap())"
        iframe_height = height + 12 + toolbar
    zoom_toolbar = (
        _ZOOM_TOOLBAR.replace("__BTN__", _ZOOM_BUTTON_CSS).replace("__KEY__", key)
        if zoomable
        else ""
    )
    transport = ""
    if toolbar:
        # The zoom buttons end the replay's toolbar row instead of floating
        # over the plot's top-left corner, where a title or legend sits.
        # `order` keeps them last whenever the player adds its controls.
        transport = (
            f'<div id="{_true_scale_plot_id(key)}-transport" '
            f'style="height:{toolbar}px;display:flex;align-items:center;">'
            + zoom_toolbar.replace(_ZOOM_TOOLBAR_FLOAT, _ZOOM_TOOLBAR_IN_ROW)
            + "</div>"
        )
        zoom_toolbar = ""
    # The plot goes in last, so the other substitutions scan the template, not a
    # replay's megabytes of JSON — and cannot rewrite a placeholder-like string
    # inside the figure.
    html = (
        _TRUE_SCALE_TEMPLATE.replace("__TOOLBAR__", zoom_toolbar)
        .replace("__TRANSPORT__", transport)
        .replace("__BAR__", str(toolbar))
        .replace("__SCALE_JS__", scale_js)
        .replace("__ZOOMABLE__", "true" if zoomable else "false")
        .replace("__GROW__", "true" if max_height is None else "false")
        .replace("__FIT__", "true" if fit_window and max_height is None else "false")
        .replace("__FIT_MIN__", str(_FIT_WINDOW_MIN_PX))
        .replace("__ZMAX__", str(_ZOOM_MAX))
        .replace("__W__", str(int(width)))
        .replace("__H__", str(int(height)))
        .replace("__KEY__", key)
        .replace("__DRAWN_EVENT__", loading.PLOT_DRAWN_EVENT)
        .replace("__PLOT__", plot_html)
    )
    return html, iframe_height


#: The shortest a `fit_window` figure is drawn, in px: under this, fitting the
#: subtab bar on screen would cost the plot more than a scroll does.
_FIT_WINDOW_MIN_PX = 420

#: The current figure's PNG — the Export subtab's and the plot camera's — is
#: raster, so it renders at 3× to stay crisp; SVG and PDF are vector and stay at
#: 1×. The bundles keep their own PNG-scale control.
_PNG_EXPORT_SCALE = 3


def _true_scale_plot_id(key: str) -> str:
    """The Plotly graph div's id inside a `_render_true_scale_chart` iframe."""
    return f"truescale-{key}"


def _render_true_scale_chart(
    fig,
    *,
    key: str,
    max_height: int | None = None,
    download_name: str | None = None,
    alt: str | None = None,
    fit_window: bool = False,
) -> None:
    """Display a spatial figure true-to-scale, fitted to the column width.

    ``st.plotly_chart`` pins the chart width to the column but keeps the layout
    height, re-laying-out the plot to an unknown scale — which breaks the
    data→pixel sizing the word labels were computed for (text over/under fills
    the boxes). Instead we render the figure at its exact pixel size, then scale
    that whole block *uniformly* with a CSS transform so it fills the column
    width. A uniform transform keeps boxes, fixations and text locked at one true
    scale (unlike a Plotly re-layout, which leaves the font fixed), so the plot
    stays faithful to the experiment at any column width — and never needs
    horizontal scrolling. It is centred in the column, and grows above true
    size to fill the column's width while it still fits the browser window's
    height, so a wide monitor's extra room is used. Uniform scaling keeps every
    proportion, so a larger figure is still faithful to the experiment's layout.

    ``fit_window`` — the Scanpath view's own figure (single, comparison,
    replay) — sizes it instead to the window's height left under its top once
    the subtab bar below it is kept on screen, so Export is a click away
    without scrolling; down to `_FIT_WINDOW_MIN_PX`, below which it scrolls.

    **Zoom** rides on the same transform: the fit scale is multiplied by a
    zoom factor (1×–8×) driven by the small toolbar, Ctrl/Cmd + wheel and
    trackpad pinch, with drag-to-pan inside a fixed-height viewport. Plotly's own
    zoom/pan is removed from the modebar and ``dragmode`` is switched off,
    because an axis re-layout leaves markers, fonts and line widths at their
    original pixel sizes — the thing this whole function exists to avoid. Zoom is
    view-only: it never touches the figure, so exports and Share are unaffected.

    ``max_height`` caps the rendered (scaled) height in px — used for the small
    multiples in the *Comparisons* grid, where the figure should also
    shrink to fit a fixed cell height (whichever of width/height binds), and the
    iframe is sized to that cap so panels don't leave a tall band of whitespace.
    Those panels stay zoom-free.

    The modebar's camera saves at the figure's own size and
    `_PNG_EXPORT_SCALE` instead of Plotly's 1×, and as ``download_name``.png
    when given — the Scanpath view's figures pass the Export subtab's file name,
    so the camera saves the same PNG. The others keep Plotly's ``newplot.png``.

    ``alt`` names the figure for assistive technology, in place of
    its title; a zoomable figure is also a Tab stop, so the keyboard reaches it
    and its zoom buttons.
    """
    zoomable = max_height is None
    width, height, toolbar = replay_page_box(fig)
    _render_true_scale_plot(
        _true_scale_plot_html(
            fig, key=key, download_name=download_name, zoomable=zoomable
        ),
        key=key,
        width=width,
        height=height,
        max_height=max_height,
        zoomable=zoomable,
        alt=alt or _figure_alt(fig, "Scanpath figure"),
        fit_window=fit_window,
        toolbar=toolbar,
    )


def _true_scale_plot_html(
    fig,
    *,
    key: str,
    download_name: str | None = None,
    zoomable: bool = True,
    figure_dict: dict | None = None,
) -> str:
    """The figure's own markup for `_render_true_scale_chart`: div, config, player.

    Everything but plotly.js itself, which `_render_true_scale_plot` loads on
    every run — so this string is what a replay's cached view keeps.
    ``figure_dict`` is ``fig.to_dict()`` when the caller already has it; it is
    serialized as is, skipping the deep copy `to_html` would make of ``fig``
    (2 s at 2,000 frames). The markup is byte-identical either way.

    The browser reconstructs each displayed replay frame on demand from the
    compact page written by `plots.replay_page`.
    """
    width, height, _toolbar = replay_page_box(
        fig if figure_dict is None else figure_dict
    )
    # An animated replay plays on the wall-clock player, never on Plotly's own
    # queue, which rounds every frame up to whole display ticks (Fine at ×1 would
    # run 25 % slow). The player also starts it on load when autoplay is on, and
    # reads the packed frames on demand. `None` for a static figure.
    page = replay_page(fig if figure_dict is None else figure_dict)
    player_script = None
    if page is not None:
        figure_dict, player_script = page
    config: dict = {
        **PLOTLY_CONFIG,
        "responsive": False,
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "width": width,
            "height": height,
            "scale": _PNG_EXPORT_SCALE,
        },
    }
    if download_name:
        config["toImageButtonOptions"]["filename"] = download_name
    if zoomable:
        config["modeBarButtonsToRemove"] = list(_NATIVE_ZOOM_BUTTONS)
    return pio.to_html(
        fig if figure_dict is None else figure_dict,
        validate=figure_dict is None,
        include_plotlyjs=False,
        full_html=False,
        config=config,
        div_id=_true_scale_plot_id(key),
        # to_html defaults to auto_play=True, which auto-runs an animated figure on
        # load at Plotly's default frame duration (ignoring the configured playback
        # speed). Start paused so the replay only plays — at the right speed — on
        # the player's clock, by autoplay or ▶ Play. No effect on static figures.
        auto_play=False,
        post_script=player_script,
    )


def _render_true_scale_plot(
    plot_html: str,
    *,
    key: str,
    width: int,
    height: int,
    max_height: int | None = None,
    zoomable: bool = True,
    alt: str | None = None,
    fit_window: bool = False,
    toolbar: int = 0,
) -> None:
    """Embed `_true_scale_plot_html`'s markup in the true-scale iframe.

    ``width`` / ``height`` are the figure's on the page and ``toolbar`` its
    replay toolbar's height (`plots.replay_page_box`)."""
    # The installed plotly's own plotly.min.js, served by this app's server —
    # not cdn.plot.ly, so the figure draws offline too.
    html, iframe_height = _true_scale_html(
        plotlyjs_script() + plot_html,
        key=key,
        width=width,
        height=height,
        max_height=max_height,
        zoomable=zoomable,
        fit_window=fit_window,
        toolbar=toolbar,
    )
    # Iframe height = full true height (or the cap); the script trims the
    # visible block to the scaled height. A zoomable figure is a Tab stop; the
    # small multiples (`max_height`) stay out of the tab order.
    _embed_html_iframe(html, height=iframe_height, alt=alt, focusable=zoomable)
    # The next figure under this key holds its area at this size.
    loading.record_plot_size(key, width, iframe_height)


def _different_texts_note(text_a: str | None, text_b: str | None) -> str | None:
    """The warning for an **overlay** of readings of two **different texts**.

    ``None`` when they match, or when either side's text id is unknown — a
    dataset without a text column must not be nagged about something it cannot
    answer.

    Only an overlay asks for it: it draws both scanpaths over **one** set of word
    boxes, so a mismatched pair is actively misleading — it invites you to read
    one reading's fixations against the other's words. A split layout gives each
    panel its own stimulus, where comparing two texts is an ordinary thing to
    want, so it says nothing.

    Rendered under the figure (both the static comparison and the animated
    co-replay) rather than inside the rail's popover: a caveat about what the
    figure *means* has to be where the figure is.
    """
    if not text_a or not text_b or str(text_a) == str(text_b):
        return None
    return (
        f"**A** reads `{text_a}` and **B** reads `{text_b}`. An overlay draws both "
        "scanpaths over one set of word boxes, so it doesn't show where each "
        "reader looked. Compare two trials of the same text, or set **View** to "
        "**Side by side**."
    )


_MIME_FOR_FORMAT = {
    "PNG": "image/png",
    "SVG": "image/svg+xml",
    "PDF": "application/pdf",
    "HTML": "text/html",
}


#: The formats Plotly.js can save from the figure the browser has already
#: drawn (`Plotly.toImage`, what the modebar's camera does). PDF is not one of
#: them, so it stays on Kaleido.
_BROWSER_IMAGE_FORMATS = ("PNG", "SVG")

_IMAGE_DOWNLOAD_HTML = """
<button type="button" class="sps-image-download"></button>
<div class="sps-image-download-note" role="status"></div>
"""

# Streamlit's secondary button, redrawn from the `--st-*` theme variables so it
# sits beside the st.download_button it replaces for PDF/HTML without a seam.
_IMAGE_DOWNLOAD_CSS = """
:host { display: block; font-family: var(--st-font); }
.sps-image-download {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 2.5rem; margin: 0; padding: 0.25rem 0.75rem;
  font-family: inherit; font-size: 0.875rem;
  font-weight: var(--st-base-font-weight); line-height: 1.6;
  color: var(--st-text-color); background: var(--st-background-color);
  /* Streamlit lifts a secondary button 2.5 points of lightness off the page,
     which only shows in a dark theme; white stays white. */
  background: hsl(from var(--st-background-color) h s min(l + 2.5, 100));
  border: 1px solid var(--st-border-color); border-radius: var(--st-button-radius);
  cursor: pointer; user-select: none;
}
.sps-image-download:hover { border-color: var(--st-primary-color);
  color: var(--st-primary-color); }
.sps-image-download:active { border-color: var(--st-primary-color);
  background: var(--st-primary-color); color: #fff; }
.sps-image-download:focus-visible { outline: none; border-color: var(--st-primary-color);
  box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--st-primary-color) 50%, transparent); }
.sps-image-download:disabled { cursor: progress; opacity: 0.6; }
.sps-image-download-note { margin-top: 0.35rem; font-size: 0.875rem;
  color: var(--st-red-text-color); }
.sps-image-download-note:empty { display: none; }
"""

_IMAGE_DOWNLOAD_JS = r"""
export default function (component) {
  const { data, parentElement } = component;
  const button = parentElement.querySelector('.sps-image-download');
  const note = parentElement.querySelector('.sps-image-download-note');
  button.textContent = data.label;
  note.textContent = '';

  // `_render_true_scale_chart` draws the figure in a same-origin srcdoc
  // iframe whose graph div has a known id, next to that iframe's own Plotly.
  const findPlot = () => {
    for (const frame of document.querySelectorAll('iframe')) {
      try {  // a cross-origin frame (an extension's, a host's) throws here
        const gd = frame.contentDocument && frame.contentDocument.getElementById(data.plot_id);
        const Plotly = gd && frame.contentWindow.Plotly;
        if (Plotly) return { Plotly, gd };
      } catch (err) { /* not ours */ }
    }
    return null;
  };

  // A print width's dpi goes into the PNG header (a `pHYs` chunk after IHDR),
  // as `export.set_png_dpi` does headless, so a layout program places the file
  // at its print size. The pixels are untouched.
  const crc32 = (bytes) => {
    let c = ~0;
    for (const b of bytes) {
      c ^= b;
      for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1));
    }
    return ~c >>> 0;
  };
  const afterHeader = (png, chunk) => {
    const at = 33;  // signature (8) + IHDR (25)
    const out = new Uint8Array(png.length + chunk.length);
    out.set(png.subarray(0, at));
    out.set(chunk, at);
    out.set(png.subarray(at), at + chunk.length);
    return out;
  };
  const withDpi = (png, dpi) => {
    if (!dpi) return png;
    const chunk = new Uint8Array(21);
    const view = new DataView(chunk.buffer);
    const ppm = Math.round(dpi / 0.0254);
    view.setUint32(0, 9);
    chunk.set([0x70, 0x48, 0x59, 0x73], 4);  // "pHYs"
    view.setUint32(8, ppm);
    view.setUint32(12, ppm);
    chunk[16] = 1;  // pixels per metre
    view.setUint32(17, crc32(chunk.subarray(4, 17)));
    return afterHeader(png, chunk);
  };
  // The citation, as `file_citation` writes it into every file the server
  // draws: PNG text chunks and an SVG <metadata> element, built in Python and
  // spliced in as they are.
  const fromBase64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
  const withCitation = (png) =>
    data.png_citation ? afterHeader(png, fromBase64(data.png_citation)) : png;
  const svgWithCitation = (svg) => data.svg_citation
    ? svg.replace(/<svg\b[^>]*>/, (root) => root + data.svg_citation)
    : svg;

  // Reassigned, not added: Streamlit reuses the component across reruns.
  button.onclick = async () => {
    const plot = findPlot();
    if (!plot) {
      note.textContent = 'The figure is still being drawn. Try again in a moment.';
      return;
    }
    button.disabled = true;
    note.textContent = '';
    try {
      // `imageDataOnly` hands back the SVG markup or the PNG's base64 rather
      // than a data URL, so neither is percent-encoded only to be decoded again.
      const image = await plot.Plotly.toImage(plot.gd, {
        format: data.format, width: data.width, height: data.height, scale: data.scale,
        imageDataOnly: true,
      });
      const blob = data.format === 'svg'
        ? new Blob([svgWithCitation(image)], { type: 'image/svg+xml;charset=utf-8' })
        : new Blob([withCitation(withDpi(fromBase64(image), data.dpi))],
                   { type: 'image/png' });
      const href = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = href;
      link.download = data.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 60000);
    } catch (err) {
      note.textContent = `Couldn't save the ${data.format.toUpperCase()} (${(err && err.message) || err}). Try again, or choose HTML.`;
    } finally {
      button.disabled = false;
    }
  };
}
"""


def _image_download_component() -> Any:
    """Register once per script run (the v2 registry is run-scoped in AppTest)."""
    return st.components.v2.component(
        "scanpath_image_download",
        html=_IMAGE_DOWNLOAD_HTML,
        css=_IMAGE_DOWNLOAD_CSS,
        js=_IMAGE_DOWNLOAD_JS,
    )


def _print_size_setting() -> dict:
    """Export → Current figure's print size: ``width`` (``None``
    for the screen size), its ``unit`` and ``dpi`` — the settings file's
    ``export`` section, read by `url_state._restore_plot_config`."""
    ss = st.session_state
    width = ss.get(EXPORT_FIGURE_WIDTH)
    return {
        "width": float(width) if width else None,
        "unit": ss.get(EXPORT_FIGURE_WIDTH_UNIT) or "mm",
        "dpi": int(ss.get(EXPORT_FIGURE_DPI) or DEFAULT_PRINT_DPI),
    }


def _png_scale(figure_width: int) -> float:
    """The PNG's ``scale``: the print width at its dpi, else the screen size at
    `_PNG_EXPORT_SCALE`."""
    size = _print_size_setting()
    if not size["width"]:
        return _PNG_EXPORT_SCALE
    return print_width_px(size["width"], size["unit"], size["dpi"]) / figure_width


def _render_print_size(fig_width: int, fig_height: int) -> None:
    """Width (mm or in) + DPI for the PNG. A blank width writes the figure at
    three times its screen size."""
    ss = st.session_state
    ss.setdefault(EXPORT_FIGURE_WIDTH, None)
    ss.setdefault(EXPORT_FIGURE_WIDTH_UNIT, "mm")
    ss.setdefault(EXPORT_FIGURE_DPI, DEFAULT_PRINT_DPI)
    label_col, field_col = st.columns(
        [PANEL_LABEL_W, 1.0 - PANEL_LABEL_W], gap=LABEL_GAP, vertical_alignment="center"
    )
    width_help = (
        "The PNG's print width. Leave it blank for three times the size on screen."
    )
    row_label(label_col, "Width", width_help)
    width_col, unit_col = field_col.columns([3, 2], vertical_alignment="center")
    width_col.number_input(
        "Width",
        value=None,
        min_value=1.0,
        max_value=2000.0,
        step=1.0,
        placeholder=f"{_PNG_EXPORT_SCALE}× screen size",
        key=EXPORT_FIGURE_WIDTH,
        help=width_help,
        label_visibility="collapsed",
        persist_state="session",
    )
    unit_col.segmented_control(
        "Width unit",
        options=["mm", "in"],
        key=EXPORT_FIGURE_WIDTH_UNIT,
        label_visibility="collapsed",
        persist_state="session",
    )
    if not ss.get(EXPORT_FIGURE_WIDTH_UNIT):
        ss[EXPORT_FIGURE_WIDTH_UNIT] = "mm"  # a deselected segment
    panel_field(
        st,
        "number_input",
        "DPI",
        min_value=50,
        max_value=2400,
        step=50,
        key=EXPORT_FIGURE_DPI,
        disabled=not ss.get(EXPORT_FIGURE_WIDTH),
        help="Pixels per inch of the print width; written into the PNG.",
        persist_state="session",
    )
    scale = _png_scale(fig_width)
    st.caption(f"{round(fig_width * scale):,} × {round(fig_height * scale):,} px")


def _render_save_plot_button(
    fig,
    *,
    canvas_width: int,
    canvas_height: int,
    slug: str,
    key_prefix: str,
    plot_key: str = "single",
) -> None:
    """Download the currently displayed figure in one click.

    PNG and SVG are saved by the browser from the plot already on screen
    (``plot_key`` names its `_render_true_scale_chart`), the way the modebar's
    camera saves one — instantly, and with no Chrome needed on the server. The
    image is the reader's browser's own drawing of the figure, so it is what they
    see; it can differ from Kaleido's (the API, the CLI and the bundles) wherever
    the fonts differ, or the browser is not Chromium-based.

    PDF and HTML are a `st.download_button` whose ``data`` is a callable
    (`_figure_download_data`), which Streamlit runs only when the button is
    pressed — on a worker thread, with a spinner on the button — rather than on
    every rerun.
    Width/height come from the figure's own layout so stacked / multi-panel
    figures save at their on-screen size.
    """
    if fig is None:
        return
    file_stem = f"scanpath_{_safe_filename(slug)}"
    # `label | field` rows: this is a full-width subtab, so there is room for
    # the label column.
    fmt = panel_field(
        st,
        "radio",
        "Download format",
        options=["PNG", "SVG", "PDF", "HTML"],
        index=0,
        horizontal=True,
        key=f"{key_prefix}_save_format",
        help="PNG and SVG are saved by your browser from the figure on screen. "
        "PDF is drawn with Chrome, Chromium or Edge. HTML is interactive and "
        "doesn't need Chrome.",
    )

    if fmt in _BROWSER_IMAGE_FORMATS:
        fig_width = int(fig.layout.width or canvas_width)
        fig_height = int(fig.layout.height or canvas_height)
        if fmt == "PNG":
            with st.expander("Print size and resolution"):
                _render_print_size(fig_width, fig_height)
        _image_download_component()(
            key=f"{key_prefix}_save_image",
            data={
                "plot_id": _true_scale_plot_id(plot_key),
                "format": fmt.lower(),
                "filename": f"{file_stem}.{fmt.lower()}",
                "width": fig_width,
                "height": fig_height,
                "scale": _png_scale(fig_width) if fmt == "PNG" else 1,
                # Only a set print width has a dpi to record.
                "dpi": _print_size_setting()["dpi"]
                if fmt == "PNG" and _print_size_setting()["width"]
                else None,
                "label": f"⬇ Download {fmt}",
                # The citation every server-drawn file carries, for the browser
                # to write into this one (`file_citation`).
                "png_citation": base64.b64encode(png_text_chunks()).decode()
                if fmt == "PNG"
                else None,
                "svg_citation": svg_metadata() if fmt == "SVG" else None,
            },
            height="content",
        )
        return

    # Pre-flight: a render that fails on the worker thread can only
    # surface as Streamlit's generic "Failed to generate file for download" —
    # nothing it raises reaches the page — so the one failure we can predict is
    # said up front, with the fix and the browser-free HTML fallback.
    if fmt == "HTML":
        _render_html_files_choice()
    no_browser = fmt == "PDF" and not chrome_available()
    if no_browser:
        st.warning(
            "PDF export needs Chrome, Chromium or Edge, and none was found. "
            "Choose **PNG**, **SVG** or **HTML** instead; they don't need it.",
            icon=ICONS["warning"],
        )
    st.download_button(
        f"⬇ Download {fmt}",
        data=_figure_download_data(
            fig,
            fmt,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            self_contained=_html_self_contained(),
        ),
        file_name=f"{file_stem}.{fmt.lower()}",
        mime=_MIME_FOR_FORMAT[fmt],
        key=f"{key_prefix}_save_button",
        # Downloading changes nothing on the page, so it needn't rerun the app.
        on_click="ignore",
        disabled=no_browser,
        help=None
        if fmt == "HTML"
        else "Draws the PDF with Chrome when you click (the first export can "
        "take a few seconds). If it fails, choose **PNG**, **SVG** or **HTML**.",
    )


def _html_self_contained() -> bool:
    """The current figure's *Self-contained HTML* choice
    (`_render_html_files_choice`)."""
    return bool(st.session_state.get(HTML_SELF_CONTAINED_KEY, False))


def _render_html_files_choice() -> None:
    """The current figure's (or replay's) HTML: embed the Plotly library, or
    load it from cdn.plot.ly when the file is opened. Drawn only while HTML is
    the chosen format; the export bundle asks its own (`render_export_options`).
    The scripted surfaces (`save_figure`, `render -o figure.html`) always embed
    it."""
    panel_field(
        st,
        "checkbox",
        "Self-contained HTML (opens offline, larger file)",
        display="Self-contained HTML",
        value=False,
        key=HTML_SELF_CONTAINED_KEY,
        persist_state="session",
        help=(
            "Include the plotting library so this HTML file opens offline (adds about"
            " 4.8 MB). Otherwise, an internet connection is needed when you open the "
            "file."
        ),
    )


def _figure_download_data(
    fig,
    fmt: str,
    *,
    canvas_width: int,
    canvas_height: int,
    self_contained: bool = False,
) -> Callable[[], str | bytes]:
    """The zero-argument callable `st.download_button` runs on click."""
    if fmt == "HTML":

        def page() -> str:
            return stamp_html(
                fig.to_html(
                    include_plotlyjs=html_plotlyjs(self_contained),
                    full_html=True,
                    config={**PLOTLY_CONFIG},
                )
            )

        return page
    return partial(
        render_static_figure_bytes,
        fig,
        fmt=fmt.lower(),
        width=int(fig.layout.width or canvas_width),
        height=int(fig.layout.height or canvas_height),
        scale=_PNG_EXPORT_SCALE if fmt == "PNG" else 1,
    )


# Above this many frames, offer to cap the rendered frame count: each frame is a
# headless-Chrome render (~0.1-0.25 s), so a long reading would otherwise spin for
# a minute or more. Capping holds each kept frame proportionally longer, so the
# clip's total duration is unchanged.
_ANIM_FRAME_CAP = 250
# Rough per-frame render cost (warm browser) + one-off browser cold start, for the
# "~Ns to render" estimate. Approximate by design.
_ANIM_RENDER_S_PER_FRAME = 0.18
_ANIM_RENDER_COLD_START_S = 3.0


def _animation_html(fig, *, self_contained: bool = False) -> str:
    """The animation as a standalone HTML page, as `api.save_figure` writes it.

    It replays on the same wall-clock player as the live embed, which also
    autoplays it at the configured speed when asked; Plotly's own
    ``auto_play`` stays off, since it ignores ``frame_duration``. The frames
    travel packed and are rebuilt in the browser. ``fig`` may also be a
    figure's ``to_dict()`` (a replay's cached view), serialized as is.
    ``self_contained`` embeds the Plotly library ahead of the player's script,
    as `api.save_figure` does, so the page replays offline.
    """
    options = dict(
        include_plotlyjs=html_plotlyjs(self_contained),
        full_html=True,
        auto_play=False,
        config={**PLOTLY_CONFIG},
    )
    page = replay_page(fig)
    if page is not None:
        # The frames travel packed; the script rebuilds them, then plays.
        figure_dict, script = page
        html = pio.to_html(figure_dict, validate=False, post_script=script, **options)
    else:
        html = pio.to_html(fig, validate=not isinstance(fig, dict), **options)
    return stamp_html(html)


def _render_animation_export(replay: _ReplayView, *, file_stem: str) -> None:
    """Export the animated scanpath as interactive HTML or a rasterized GIF/MP4.

    HTML is one click (no browser needed to generate, keeps interactivity). GIF and
    MP4 rasterize every frame through Kaleido (headless Chrome) — too slow to run on
    every rerun — so they follow a Render-then-download pattern, with a progress
    bar and a result cached in session state so the download button survives
    reruns (and a re-render isn't needed unless an option changes). The clip
    lasts what the on-screen replay does — the quoted playback time, spread evenly
    over its frames (fewer of them when the replay is faster than the format can
    show).

    A rerun reads only the cached view's frame count, clip length, size
    and signature; the figure itself is unpickled — 9 s at 2,000 frames — by the
    click that exports it.
    """
    n_frames = replay.n_frames
    fmt = panel_field(
        st,
        "radio",
        "Download format",
        options=["HTML", "GIF", "MP4"],
        index=0,
        horizontal=True,
        key="anim_export_format",
        help=(
            "HTML opens in your browser with interactive playback controls. GIF and "
            "MP4 are clips for slides and talks; creating them requires Chrome, "
            "Chromium or Edge. MP4 usually produces smaller files than GIF."
        ),
    )

    if fmt == "HTML":
        _render_html_files_choice()
        # Built on click, not per rerun — a long replay's HTML runs to
        # megabytes and about a second to serialize.
        st.download_button(
            "⬇ Download HTML",
            data=partial(
                _replay_page_html, replay, self_contained=_html_self_contained()
            ),
            file_name=f"{file_stem}.html",
            mime="text/html",
            key="anim_export_html",
            on_click="ignore",
            # A saved file has no app server to load plotly.js from, so it embeds
            # it or loads it from the CDN — the *Self-contained HTML* choice just
            # above.
            help="An HTML file you can open in any browser, with the Play button "
            "and slider. Tick *Self-contained HTML* above to open it offline.",
        )
        return

    if n_frames == 0:
        st.info("This replay has no frames, so there is nothing to export.")
        return

    # Pre-flight: GIF/MP4 need Chrome — warn before the user waits on a
    # render that can only fail, and point at the fix + the browser-free HTML.
    if not chrome_available():
        st.warning(
            f"{fmt} export can't run here. {CHROME_INSTALL_HINT}", icon=ICONS["warning"]
        )

    # The figure's own clock, so the clip lasts exactly what its replay
    # does — also when the Hide flags drop fixations, which the builder does.
    frame_ms = replay.clip_frame_ms
    clip_s = frame_ms * n_frames / 1000.0

    scale = panel_field(
        st,
        "select_slider",
        "Resolution",
        options=[0.5, 0.75, 1.0, 1.5, 2.0],
        value=1.0,
        format_func=lambda s: f"{s:g}×",
        key="anim_export_scale",
        help=(
            "At 1×, the export matches the on-screen size. Lower values make smaller "
            "files and export faster; higher values make sharper images and larger "
            "files."
        ),
    )

    max_frames = None
    # The label column is one ellipsized line, so the sentence this checkbox used
    # as its label becomes its hover and the column carries the short name.
    if n_frames > _ANIM_FRAME_CAP and panel_field(
        st,
        "checkbox",
        f"Limit to {_ANIM_FRAME_CAP} frames for a faster render",
        display="Frame cap",
        value=True,
        key="anim_export_limit",
        help=f"Render at most {_ANIM_FRAME_CAP} frames, so the export is quicker. "
        "The clip lasts as long as before; each kept frame is held a little "
        "longer.",
    ):
        max_frames = _ANIM_FRAME_CAP

    # A replay faster than the format can show renders fewer frames.
    render_frames = clip_frame_count(n_frames, frame_ms, fmt, max_frames)
    est_s = render_frames * _ANIM_RENDER_S_PER_FRAME + _ANIM_RENDER_COLD_START_S
    note = f"{n_frames} frames · clip ≈ {clip_s:.1f}s · ~{est_s:.0f}s to render"
    if render_frames != n_frames:
        note += f" ({render_frames} frames rendered)"
    st.caption(note)
    if fmt == "GIF":
        st.caption(
            "GIF files are large for long readings. Choose MP4 or a lower "
            "resolution for a smaller file."
        )

    # Re-render only when an output-affecting input changes; otherwise reuse the
    # cached bytes so the download button persists across reruns. The replay's
    # signature covers every visual choice that feeds the clip — trial, playback
    # speed, saccades/order/marker-size/background, true-to-scale text, labels —
    # so toggling any of them invalidates a stale render instead of serving the
    # previous bytes. It is built from those inputs, not from the figure's JSON,
    # which costs 12 s to write at 2,000 frames. `scale`/`max_frames`
    # are export-only (not in the figure), so they're keyed separately.
    sig = export_signature(
        replay.signature,
        fmt=fmt,
        width=replay.width,
        height=replay.height,
        scale=float(scale),
        exporter_version=(
            f"{EXPORTER_VERSION}:animation:{file_stem}:{max_frames}:{frame_ms:.12g}"
        ),
    )
    cache = st.session_state.get("_anim_export_cache")
    if cache and cache.get("sig") != sig:
        st.session_state.pop("_anim_export_cache", None)
        cache = None

    if st.button(
        f"Render {fmt}",
        key="anim_export_generate",
        help="Draws each frame with Chrome; the download appears once it's ready.",
    ):
        status_box = st.status("Preparing animation export…", expanded=True)
        progress_slot = st.empty()
        bar = None

        def _on_status(status: ExportStatus) -> None:
            nonlocal bar
            elapsed = f" · {status.elapsed_s:.1f}s" if status.elapsed_s else ""
            state = (
                "complete"
                if status.stage == ExportStage.READY
                else "error"
                if status.stage == ExportStage.ERROR
                else "running"
            )
            status_box.update(label=f"{status.message}{elapsed}", state=state)
            if status.fraction is not None:
                text = (
                    f"{status.completed}/{status.total} frames"
                    if status.stage == ExportStage.RASTERIZING
                    else status.message
                )
                if bar is None:
                    bar = progress_slot.progress(status.fraction, text=text)
                else:
                    bar.progress(status.fraction, text=text)

        try:
            data = export_animation(
                replay.figure(),
                fmt=fmt.lower(),
                frame_duration_ms=frame_ms,
                scale=float(scale),
                max_frames=max_frames,
                status_callback=_on_status,
            )
        except AnimationExportError as exc:
            progress_slot.empty()
            # An over-budget GIF is refused before Chrome starts, and its
            # message already says what to change — the browser advice would not.
            st.warning(
                f"Could not render {fmt}: {exc}"
                if isinstance(exc, AnimationBudgetError)
                else f"Could not render {fmt}: {exc}\n\n"
                "GIF and MP4 are drawn frame by frame with Chrome, Chromium or "
                "Edge. If one is installed and this still fails, choose **HTML** "
                "above, which doesn't need Chrome."
            )
            cache = None
            st.session_state.pop("_anim_export_cache", None)
        else:
            progress_slot.empty()
            cache = {"sig": sig, "data": data}
            st.session_state["_anim_export_cache"] = cache

    if cache and cache.get("sig") == sig:
        data = cache["data"]
        size = len(data)
        size_label = (
            f"{size / 1_048_576:.1f} MB"
            if size >= 1_048_576
            else f"{size / 1024:.0f} KB"
        )
        st.success(f"{fmt} ready · {size_label}")
        st.download_button(
            f"⬇ Download {fmt} ({size_label})",
            data=data,
            file_name=f"{file_stem}.{fmt.lower()}",
            mime=mime_for(fmt.lower()),
            key="anim_export_download",
        )


def _fix_window_note(
    window_a, full_a, window_b=None, full_b=None, *, essentials=False
) -> str:
    """Say so when an index window hides some of a trial's fixations.

    The window lives in the Filters & highlights popover, out of sight, so without
    this a figure missing most of its fixations would give no hint why.
    ``window_b`` / ``full_b`` only while comparing.
    """

    def _cut(window, full) -> str | None:
        if window is None or full is None or tuple(window) == tuple(full):
            return None
        lo, hi = (int(v) for v in window)
        shown = f"fixation {lo}" if lo == hi else f"fixations {lo}–{hi}"
        return f"{shown} of {int(full[0])}–{int(full[1])}"

    a, b = _cut(window_a, full_a), _cut(window_b, full_b)
    if not a and not b:
        return ""
    if b is None:
        what = f"Showing only {a}" if window_b is None else f"Scanpath A shows {a}"
    elif a is None:
        what = f"Scanpath B shows {b}"
    else:
        what = f"Scanpath A shows {a}, and B shows {b}"
    action = "Switch to Full to change it" if essentials else "Change it"
    return f"{what}. {action} with **Index range** in Filters & highlights."


def _slice_fix_range(fix: pd.DataFrame, fix_range) -> pd.DataFrame:
    """Keep only fixations whose 1-based ``order_in_trial`` is within ``fix_range``.

    ``fix_range`` is the single-trial fixation-index window — a
    ``(start, end)`` tuple, or ``None`` for the full trial. Applied only to the
    frame feeding the figure / animation / comparison builders (and thus the
    Current-figure export, which round-trips the on-screen figure), so the chips,
    panels and bulk multi-trial export keep the complete trial. A ``None`` window
    or a frame without ``order_in_trial`` returns the very same frame **object**,
    like `_drift_corrected`'s no-op path — the caller passes the result straight
    to the builders, so identity is what keeps the untouched default free of a
    boolean-mask copy and its cache keys byte-identical.

    The **untouched slider** is a `None` window here only because the call site
    tests it against the trial's own full range first; do not re-derive that
    range in here. `render_single_trial_tab` already computes it as
    ``full_fix_range`` — from the *unsliced* frame, which is also what the Share
    link's writer publishes — and a length-based shortcut would be wrong anyway:
    on a multipart trial ``order_in_trial`` is parent-global, so a later screen
    runs 509-578 and its full window does not start at 1."""
    if (
        isinstance(fix_range, (tuple, list))
        and len(fix_range) == 2
        and fix is not None
        and not fix.empty
        and "order_in_trial" in fix.columns
    ):
        lo, hi = fix_range
        return fix[(fix["order_in_trial"] >= lo) & (fix["order_in_trial"] <= hi)]
    return fix


def _drift_corrected(
    fix: pd.DataFrame, words: pd.DataFrame, algorithm: str | None
) -> pd.DataFrame:
    """Vertical drift correction for one scanpath, or a true no-op.

    Returns the very same frame **object** whenever no algorithm is selected
    (``None`` / ``"Off"`` — the default), or when there is nothing to correct
    (empty fixations or empty words). That identity matters: the caller uses
    ``result is fix`` to tell "corrected" from "untouched", and it guarantees the
    default path costs nothing and leaves every figure / cache key byte-identical.

    Otherwise :func:`alignment.correct` snaps each fixation's ``y`` to its
    assigned text line and a *copy* comes back — ``fix`` is never mutated, so the
    raw frame stays available for the connector layer and the panels."""
    if (
        not algorithm
        or str(algorithm) == "Off"
        or fix is None
        or fix.empty
        or words is None
        or words.empty
    ):
        return fix
    corrected, _ = alignment.correct(fix, words, method=str(algorithm).lower())
    return corrected


def _build_figure_settings(viz_settings: dict, effective_show_raw_gaze: bool) -> dict:
    """Convert viz_settings to figure-compatible settings dict."""
    return dict(
        show_words=viz_settings["show_words"],
        show_word_labels=viz_settings["show_labels"],
        show_fixations=viz_settings["show_fix"],
        show_order=viz_settings["show_order"],
        show_saccades=viz_settings["show_saccades"],
        show_saccade_arrows=viz_settings.get("show_saccade_arrows", False),
        show_heatmap=viz_settings["show_heatmap"],
        heatmap_style=viz_settings.get("heatmap_style", "Word boxes"),
        heatmap_norm=viz_settings.get("heatmap_norm", "Linear"),
        heatmap_sigma_px=viz_settings.get("heatmap_sigma_px"),
        fit_to_monitor=viz_settings.get("fit_to_monitor", True),
        crop_margin=viz_settings.get("crop_margin"),
        show_coordinate_grid=viz_settings.get("show_coordinate_grid", False),
        coordinate_grid_spacing=viz_settings.get("coordinate_grid_spacing"),
        show_raw_gaze=effective_show_raw_gaze,
        # Raw gaze's own style, from the rail; without these every figure would
        # draw the builder's defaults.
        raw_gaze_color=viz_settings.get("raw_gaze_color", "#888888"),
        raw_gaze_marker_size=viz_settings.get("raw_gaze_marker_size", 4.0),
        raw_gaze_opacity=viz_settings.get("raw_gaze_opacity", 0.6),
        illustration_text=str(viz_settings.get("illustration_text", "")),
        word_box_color=viz_settings.get("word_box_color", WORD_BOX_COLOR),
        word_box_line_opacity=viz_settings.get(
            "word_box_line_opacity", WORD_BOX_LINE_OPACITY
        ),
        word_box_fill_color=viz_settings.get(
            "word_box_fill_color", WORD_BOX_FILL_COLOR
        ),
        word_box_fill_opacity=viz_settings.get(
            "word_box_fill_opacity", WORD_BOX_FILL_OPACITY
        ),
        color_by=viz_settings["color_by"],
        heatmap_metric=(
            viz_settings["heatmap_metric"]
            if viz_settings["heatmap_metric"] != "counts"
            else None
        ),
        marker_size_range=viz_settings["marker_size_range"],
        marker_size_scale=viz_settings.get(
            "marker_size_scale", DEFAULT_MARKER_SIZE_SCALE
        ),
        marker_duration_range=tuple(
            viz_settings.get("marker_duration_range", DEFAULT_MARKER_DURATION_RANGE)
        ),
        duration_size_legend=viz_settings.get(
            "duration_size_legend", DEFAULT_DURATION_SIZE_LEGEND
        ),
        legend_layout=viz_settings.get("legend_layout"),
        **{
            name: viz_settings.get(name, option.default)
            for name, option in FIXATION_LABEL_OPTIONS.items()
        },
        **{
            key: viz_settings.get(key, default)
            for key, default in COLORBAR_DEFAULTS.items()
        },
        fixation_color_range=viz_settings["fixation_color_range"],
        heatmap_range=viz_settings["heatmap_range"],
        fixation_colorscale=viz_settings["fixation_colorscale"],
        heatmap_colorscale=viz_settings["heatmap_colorscale"],
        critical_span_style=viz_settings.get("critical_span_style", "Mark text"),
        highlight_column=viz_settings.get("highlight_column"),
        saccade_color=viz_settings.get("saccade_color", SACCADE_COLOR),
        saccade_style=SACCADE_DASH_OPTIONS.get(
            viz_settings.get("saccade_style", "Solid"), "solid"
        ),
        saccade_width=viz_settings.get("saccade_width", DEFAULT_SACCADE_WIDTH),
        saccade_opacity=viz_settings.get("saccade_opacity", 1.0),
        saccade_color_mode=viz_settings.get("saccade_color_mode", "One color"),
        saccade_class_colors=viz_settings.get("saccade_class_colors"),
        saccade_type_legend=viz_settings.get("saccade_type_legend", True),
        show_color_legend=viz_settings.get("show_color_legend", True),
        show_highlight_legend=viz_settings.get("show_highlight_legend", True),
        # The reading-class filter (None / a full list = draw them all).
        saccade_classes=viz_settings.get("saccade_classes"),
        saccade_render_mode=viz_settings.get("saccade_render_mode", "Straight"),
        fixation_snap_to_line=viz_settings.get("fixation_snap_to_line", False),
        fixation_snap_position=viz_settings.get(
            "fixation_snap_position", DEFAULT_SNAP_POSITION
        ),
        hollow_fixations=viz_settings.get("hollow_fixations", False),
        fixation_opacity=viz_settings.get("fixation_opacity", FIXATION_OPACITY.default),
        fixation_color=viz_settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
        fixation_symbol=viz_settings.get("fixation_symbol", DEFAULT_FIXATION_SYMBOL),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        redact_text=viz_settings.get("redact_text", False),
        color_by_line=viz_settings.get("color_by_line", False),
        fixation_flags=viz_settings.get("fixation_flags"),
        span_border_color=viz_settings.get("span_border_color", "#000000"),
        background_color=viz_settings.get("background_color"),
        word_hover_measure=viz_settings.get(
            "word_hover_measure", "total_fixation_duration_ms"
        ),
        word_hover_fields=viz_settings.get("word_hover_fields"),
        fixation_hover_fields=viz_settings.get("fixation_hover_fields"),
        # Optional design choices: unset, each is the builder's own default.
        **{
            key: viz_settings[key]
            for key in DESIGN_CHOICE_FIELDS
            if key in viz_settings
        },
    )


def _snippet_settings_at_api_defaults(settings: dict) -> dict:
    """Settings the rail materializes in full, normalized to the API's default.

    ``api.figure_options`` reports ``None`` for ``fixation_flags`` and
    ``saccade_class_colors``, while ``controls._collect_viz_settings`` always
    builds the full dict — four categories at *Off*, the stock class palette. The
    snippet diffs against the API's defaults, so without this an **untouched**
    figure would look changed in both, and the snippet would write two dicts
    nobody had asked for.

    Normalized here, at the snippet's own seam, rather than in
    ``_collect_viz_settings``: the builders read ``fixation_flags or {}`` and
    fall back to ``SACCADE_CLASS_COLORS``, so the two spellings draw the same
    figure — but only the snippet has a reason to prefer one.
    """
    out = dict(settings)
    flags = out.get("fixation_flags")
    if isinstance(flags, dict) and all(
        str((spec or {}).get("mode", "Off")) == "Off" for spec in flags.values()
    ):
        out["fixation_flags"] = None
    colors = out.get("saccade_class_colors")
    if isinstance(colors, dict) and all(
        str(colors.get(name, default)).lower() == str(default).lower()
        for name, default in SACCADE_CLASS_COLORS.items()
    ):
        out["saccade_class_colors"] = None
    return out


def _publish_snippet_state(
    kind: str,
    figure_settings: dict,
    viz_settings: dict,
    *,
    participant: str,
    trial: str,
    screen: str | None,
    canvas: tuple[int, int],
    base_font_size: int,
    font_family: str,
    title: str,
    caption: str,
    playback_speed: float,
    compare: CompareTarget | None,
    full_fix_range: tuple[int, int] | None = None,
    fix_index_range_b: tuple[int, int] | None = None,
    own_pages: dict | None = None,
) -> None:
    """Park the state the Share subtab's code snippet is written from.

    Published from the render path rather than re-read from the widgets, so the
    snippet is a serializer over the **figure's own input** — the same reason
    `_share_selection` is written here and not rebuilt inside the Share panel.
    A separate emitter reading `session_state` a second time could drift from
    the figure.

    ``full_fix_range`` is the trial's own ``(first, last)`` fixation index, and
    is what tells the fixation-index window apart from *no window*: the slider
    defaults to the whole trial the instant there are two fixations, so without
    it an untouched figure would publish ``fix_index_range=(1, 154)`` and both
    code forms would write a window nobody had chosen.

    ``own_pages`` is each reading's own stimulus page by image slot, so
    a page drawn unmoved is written as ``show_stimulus_image=True``; the
    branches that draw B's page add it (`_amend_snippet_own_pages`).
    """
    window = viz_settings.get("fix_index_range")
    if window and full_fix_range and tuple(window) == tuple(full_fix_range):
        window = None
    st.session_state[SNIPPET_STATE_KEY] = FigureState(
        kind=kind,
        settings=_snippet_settings_at_api_defaults(figure_settings),
        participant=str(participant),
        trial=str(trial),
        screen=None if screen is None else str(screen),
        canvas=(int(canvas[0]), int(canvas[1])),
        base_font_size=int(base_font_size),
        font_family=str(font_family),
        title=title,
        caption=caption,
        fix_index_range=window,
        fix_index_range_b=fix_index_range_b if compare is not None else None,
        # "Off" is the rail's word for no correction; the API's is None.
        drift_correction=(
            None
            if str(viz_settings.get("align_algorithm", "Off")) == "Off"
            else str(viz_settings["align_algorithm"])
        ),
        drift_connectors=bool(viz_settings.get("align_connectors")),
        # The rail's choice, not the reasons it resolved to: `illustration_reasons`
        # is derived, so a snippet that carried only that would re-derive at
        # "auto" and disagree with a figure whose disclosure was forced on/off.
        illustration_label=str(viz_settings.get("illustration_label", "Auto")).lower(),
        playback_speed=float(playback_speed or 1.0),
        autoplay=bool(viz_settings.get("anim_autoplay", True)),
        compare=compare,
        own_pages=dict(own_pages or {}),
    )


def _amend_snippet_own_pages(pages: dict) -> None:
    """Record the own page of each image slot a branch fills with B's:
    a split comparison's ``"_b"``, and ``""`` when an overlay or co-animation
    draws B's text — see `_publish_snippet_state`."""
    state = st.session_state.get(SNIPPET_STATE_KEY)
    if state is None:
        return
    st.session_state[SNIPPET_STATE_KEY] = replace(
        state, own_pages={**state.own_pages, **pages}
    )


def _amend_snippet_settings(settings, kind: str) -> None:
    """Correct the published snippet's settings to the ones the figure used.

    `_publish_snippet_state` runs above the three render branches and carries
    `_build_figure_settings`'s dict, but each branch then layers its own
    `with_overrides(...)` on top — the comparison's per-scanpath `style_a` /
    `style_b` / `show_legend` / `trial_labels`, the animation's frame budget —
    and *those* are what the figure is actually built from. `figure_kwargs`
    skips any key the published dict never carried, so without this the snippet
    would silently reproduce them at their defaults: a Compare figure
    hand-coloured in the rail would come back in the stock palette.

    Only keys the chosen builder accepts are merged, so this cannot widen the
    published dict into something `api` would reject. That `name in known`
    clause is also what keeps `words_b` / `fixations_b` out: they are
    `figure_options("animation")` entries but not ``FigureSettings`` fields, so
    without it every rerun of a two-reading animation would park two full trial
    frames in session state.

    The merge is normalized through :func:`_snippet_settings_at_api_defaults`
    for the same reason the publish is — the built ``FigureSettings`` carries
    the *materialized* `fixation_flags` / `saccade_class_colors`, so without it
    this step would put straight back what the publish had just normalized away.
    ``UNPUBLISHED_SETTINGS`` is dropped for the mirror-image reason:
    `connector_y` is a builder keyword *and* a ``FigureSettings``
    field, so it passes both filters above, but it is one float per fixation
    that `code_snippet` is guaranteed never to emit.
    """
    from . import api

    state = st.session_state.get(SNIPPET_STATE_KEY)
    if state is None:
        return
    known = {field.name for field in dataclass_fields(type(settings))}
    merged = {
        name: value
        for name, value in state.settings.items()
        if name not in UNPUBLISHED_SETTINGS
    }
    merged.update(
        {
            name: getattr(settings, name)
            for name in api.figure_options(kind)
            if name in known and name not in UNPUBLISHED_SETTINGS
        }
    )
    st.session_state[SNIPPET_STATE_KEY] = replace(
        state, settings=_snippet_settings_at_api_defaults(merged)
    )


def _amend_snippet_title_caption(title: str, caption: str) -> None:
    """Correct the published snippet's title/caption to what the figure carries.

    `_publish_snippet_state` runs *above* the three render branches (so a trial
    that draws nothing still gets a snippet), but the branches render the
    pattern against different context — the comparison path passes a
    `compare_row` and the unsliced trial, the animation path passes no
    `combo_row`. Rendering it once, context-free, would give a snippet whose
    `title=` disagrees with the figure — `{participant_id_b}` resolves to `""` in
    Compare mode. `_apply_title_caption` is the one place that knows the final
    text, so it hands it back here.
    """
    state = st.session_state.get(SNIPPET_STATE_KEY)
    if state is None:
        return
    st.session_state[SNIPPET_STATE_KEY] = replace(state, title=title, caption=caption)


def _amend_snippet_compare_labels(labels: tuple[str, str]) -> None:
    """Correct the published snippet's trace labels to the figure's own.

    The third of the three amenders, and it exists for `_amend_snippet_settings`'s
    reason applied to a value that one cannot carry: the labels are resolved in
    `_render_comparison_figure`, *below* `_publish_snippet_state`, because
    `cmp{idx}_label_pattern` is rendered against each side's own trial
    frames. `compare_scanpaths` takes them as a named `labels=` parameter rather
    than a loose keyword, so `api._COMPARISON_FIGURE_PARAMS` subtracts them and
    the settings merge can never see them — without this, a comparison the user
    labelled by hand in the rail would reproduce under the builder's auto labels.
    """
    state = st.session_state.get(SNIPPET_STATE_KEY)
    if state is None or state.compare is None:
        return
    st.session_state[SNIPPET_STATE_KEY] = replace(
        state, compare=replace(state.compare, labels=(str(labels[0]), str(labels[1])))
    )


def _figure_input_key(
    words: pd.DataFrame, fixations: pd.DataFrame, build_kwargs: dict
) -> tuple:
    """Complete, hashable cache key for a single-trial scanpath figure.

    Auto-derived from *all* build inputs — the frame fingerprints plus every
    kwarg — so changing any setting busts the cache. Deriving it mechanically
    (rather than listing settings by hand) means it can't drift out of sync with
    the figure builder and show a stale plot."""
    parts = [
        ("__words__", frame_fingerprint(words)),
        ("__fixations__", frame_fingerprint(fixations)),
    ]
    for k in sorted(build_kwargs):
        v = build_kwargs[k]
        if isinstance(v, pd.DataFrame):
            parts.append((k, frame_fingerprint(v)))
        elif isinstance(v, dict):
            # `repr`, not `str`: `{1: …}` and `{"1": …}` must not share a key.
            parts.append((k, tuple(sorted((repr(a), repr(b)) for a, b in v.items()))))
        elif isinstance(v, (list, tuple)):
            parts.append((k, tuple(v)))
        else:
            try:
                hash(v)
                parts.append((k, v))
            except TypeError:
                parts.append((k, str(v)))
    return tuple(parts)


@st.cache_data(show_spinner=False, max_entries=16)
def _c_category_vocabulary(
    column: str,
    _fixations: pd.DataFrame | None,
    _fixations_b: pd.DataFrame | None,
    frame_keys: tuple,
) -> tuple[str, ...] | None:
    """`plots.category_vocabulary`, cached on the frames' fingerprints."""
    return category_vocabulary(column, _fixations, _fixations_b)


def _dataset_color_categories(
    color_by: str | None,
    fixations: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None = None,
) -> tuple[str, ...] | None:
    """`FigureSettings.color_categories` for a figure coloured by ``color_by``:
    every label it takes in the whole dataset's ``fixations`` — unfiltered, so a
    trial filter moves no colour — and in a second dataset's for Compare."""
    if not color_by or color_by in (UNIFORM_COLOR_FIELD, "line"):
        return None
    return _c_category_vocabulary(
        str(color_by),
        fixations,
        fixations_b,
        tuple(
            None if frame is None else frame_fingerprint(frame)
            for frame in (fixations, fixations_b)
        ),
    )


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_scanpath_figure(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _settings: FigureSettings,
    _raw_gaze: pd.DataFrame | None,
    fig_key,
):
    """Build + cache a static single-trial scanpath figure.

    Frames and settings are passed un-hashed; ``fig_key`` (from
    ``_figure_input_key``) is the cache key, so a rerun with the same trial and
    settings reuses the figure instead of rebuilding all its traces/shapes.
    The cache is shared by every session of the server, so it keeps the most
    recent 32 figures, not every trial and setting ever drawn."""
    # The single most expensive thing a rerun can do, and invisible from
    # outside — a cache hit and a miss look identical on screen. The line only
    # appears on a miss, which is what makes it worth reading.
    with timed(
        "build scanpath figure (cache miss)",
        words=len(_words),
        fixations=len(_fixations),
    ):
        return make_scanpath_figure(
            _words, _fixations, settings=_settings, raw_gaze=_raw_gaze
        )


def _comparison_figure_key(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    settings: FigureSettings,
    raw_gaze: pd.DataFrame | None,
    trials: tuple,
) -> tuple:
    """Cache key for a comparison figure: both readings' frames, the two
    trials, the samples, and every field of its settings. Every field, not the
    comparison's own options: its layout, both styles, B's screen and page and
    the per-render overrides all live in the settings."""
    inputs = {
        field.name: getattr(settings, field.name)
        for field in dataclass_fields(settings)
    }
    return _figure_input_key(
        words, fixations, {**inputs, "raw_gaze": raw_gaze, "trials": trials}
    )


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_comparison_figure(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _trials: tuple,
    _settings: FigureSettings,
    _raw_gaze: pd.DataFrame | None,
    fig_key,
):
    """Build + cache a comparison figure, as `_cached_scanpath_figure` does for
    the static one, so a click that changes nothing in it reuses it."""
    with timed(
        "build comparison figure (cache miss)",
        words=len(_words),
        fixations=len(_fixations),
    ):
        return make_comparison_figure(
            _words, _fixations, *_trials, settings=_settings, raw_gaze=_raw_gaze
        )


@st.cache_data(show_spinner=False, max_entries=48)
def _cached_panel_figure(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _options: dict,
    fig_key,
):
    """Build + cache one panel of a grid of readings, as
    `_cached_scanpath_figure` does for the main figure. Enough entries for a
    few pages of `_GEN_PAGE_SIZE` panels, so paging back draws nothing new."""
    with timed(
        "build grid panel (cache miss)",
        words=len(_words),
        fixations=len(_fixations),
    ):
        return make_scanpath_figure(_words, _fixations, **_options)


def _panel_figure(words: pd.DataFrame, fixations: pd.DataFrame, options: dict):
    """A grid panel's static figure, keyed on its frames and every option."""
    return _cached_panel_figure(
        words,
        fixations,
        options,
        fig_key=_figure_input_key(words, fixations, options),
    )


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_scanpath_animation(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _settings: FigureSettings,
    _fixations_b: pd.DataFrame | None,
    _words_b: pd.DataFrame | None,
    anim_key,
):
    """Build + cache the animated scanpath, as ``_cached_scanpath_figure`` does
    for the static one. Returns ``(figure, frame_step_ms)``.

    The compact player stores a trace template and its reading timeline.
    ``anim_key`` is every
    ``FigureSettings`` field plus both scanpaths' fingerprints, so any change that
    reaches the builder still rebuilds — except the playback speed, autoplay and
    the Illustration reasons, which the caller fixes before building:
    the frames depend on none of them, and `set_replay_clock` stamps the real
    speed and autoplay onto the copy each hit returns.
    """
    with timed(
        "build scanpath animation (cache miss)",
        words=len(_words),
        fixations=len(_fixations),
    ):
        return build_scanpath_replay(
            _words,
            _fixations,
            settings=_settings,
            compact=True,
            fixations_b=_fixations_b,
            words_b=_words_b,
        )


@dataclass(frozen=True)
class _ReplayView:
    """A replay as a rerun shows it, cheap to take out of the cache.

    A cached `go.Figure` would be unpickled on every hit — plotly re-validates
    every frame, 9 s at 2,000 frames — and `to_html` would then write it into
    the page again, 12 s more. This keeps the embed's markup and
    the finished figure as compressed bytes. Its sole frame holds the final
    coordinates and styles. The HTML player reconstructs each frame using the
    recorded onsets, and a movie requests the complete figure on demand.
    ``signature`` names the clip that figure exports to.
    """

    plot_html_z: bytes
    figure_z: bytes
    width: int
    height: int
    n_frames: int
    #: The figure's height on its page and its toolbar's (`plots.replay_page_box`).
    plot_height: int
    toolbar: int
    clip_frame_ms: float | None
    signature: str

    @classmethod
    def from_figure(
        cls, fig, *, plot_key: str, download_name: str | None, signature: str
    ) -> _ReplayView:
        figure_dict = fig.to_dict()
        plot_html = _true_scale_plot_html(
            fig, key=plot_key, download_name=download_name, figure_dict=figure_dict
        )
        _width, plot_height, toolbar = replay_page_box(figure_dict)
        return cls(
            plot_html_z=zlib.compress(plot_html.encode("utf-8"), 1),
            figure_z=zlib.compress(
                pickle.dumps(figure_dict, pickle.HIGHEST_PROTOCOL), 1
            ),
            width=int(fig.layout.width or 900),
            height=int(fig.layout.height or 600),
            n_frames=len((fig.layout.meta or {}).get("scanpath_frame_times_ms", ())),
            plot_height=plot_height,
            toolbar=toolbar,
            clip_frame_ms=animation_clip_frame_ms(fig),
            signature=signature,
        )

    @property
    def plot_html(self) -> str:
        """The embed's markup, as `_true_scale_plot_html` wrote it."""
        return zlib.decompress(self.plot_html_z).decode("utf-8")

    def figure_dict(self) -> dict:
        """The finished replay's ``to_dict()``, unpickled afresh."""
        return pickle.loads(zlib.decompress(self.figure_z))

    def figure(self) -> go.Figure:
        """The finished replay as a figure — for an export, never a rerun: plotly
        re-validates every frame, 9 s at 2,000 frames."""
        import plotly.graph_objects as go

        return go.Figure(replay_frames.expand_figure(self.figure_dict()))


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_replay_view(
    clip_inputs,
    autoplay: bool,
    plot_key: str,
    download_name: str,
    _finished_figure: Callable[[], Any],
) -> _ReplayView:
    """The replay's `_ReplayView`, keyed on everything in the figure.

    ``clip_inputs`` is all that goes into a GIF/MP4 of it — the replay cache's
    own key (its frames), the playback speed, the Illustration reasons, the
    preprocessing report, the title and caption — and it names the clip
    (``signature``). ``autoplay`` reaches only the player, and ``plot_key`` /
    ``download_name`` only the embed; they are here to key the markup. On a miss
    ``_finished_figure`` builds the figure, through the replay cache; a hit
    never touches that cache, whose every hit unpickles the whole figure.
    Entries are small: the view is compressed. No spinner — the plot's loading
    card covers the build.
    """
    return _ReplayView.from_figure(
        _finished_figure(),
        plot_key=plot_key,
        download_name=download_name,
        signature=hashlib.sha256(repr(clip_inputs).encode("utf-8")).hexdigest(),
    )


def _replay_page_html(replay: _ReplayView, *, self_contained: bool = False) -> str:
    """The replay's standalone HTML page: `st.download_button` calls this on click.

    Written from the view's dict, so the click never builds a figure.
    """
    return _animation_html(replay.figure_dict(), self_contained=self_contained)


_CMP_SORT_DEFAULT = "Same text, then same participant"


def _order_compare_options(
    options: list,
    choice: str,
    sort_keys: dict[str, pd.Series],
    *,
    descending: bool = False,
) -> list:
    """Sort comparison candidates with the main trial picker's vocabulary.

    The comparison-specific default preserves ``build_comparison_options``'s
    relation priority: same text, then same participant, then everything else.
    Every other choice comes from ``utils.trial_sort_keys``, alongside its
    normal ``Trial ID`` default.
    """
    if choice == _CMP_SORT_DEFAULT or len(options) < 2:
        return options
    key_series = None if choice == TRIAL_SORT_DEFAULT else sort_keys.get(choice)
    # Per reading, as the sort keys are: two readers' trials of one id
    # each take their own value.
    keys = [reading_key(option[0], option[1]) for option in options]
    ordered = sort_trial_options(
        keys,
        key_series,
        descending=descending if key_series is not None else False,
    )
    rank = {key: idx for idx, key in enumerate(ordered)}
    return [
        option for _, option in sorted(zip(keys, options), key=lambda p: rank[p[0]])
    ]


#: Scanpath B remembered as ``(participant_id, trial_id)``. The picker's
#: own key holds a *label*, which is rebuilt relative to A every run, so it is
#: not a stable name for a trial — see ``_render_compare_selector``.
_COMPARE_IDENTITY_KEY = COMPARE_IDENTITY_STATE_KEY

#: Key prefix for scanpath B's own filter set. Must be one of
#: ``controls.FILTER_PREFIXES`` — that registry is what stops A's "Clear filters"
#: sweeping B's keys along with its own.
#: The trial-filter popover's trigger, on A's row and on B's. A funnel,
#: because the control filters the list rather than searching it; Unicode has
#: no funnel emoji, so this is Streamlit's Material icon.
_FILTER_ICON = ICONS["trial_filter"]

_COMPARE_FILTER_PREFIX = "cmp"


def _compare_source_name() -> str | None:
    """The picked comparison dataset, or ``None`` for "This dataset".

    Read straight from the widget key rather than from a loaded source, because
    the rail's ⚙️ Compare options popover renders *before* the picker runs and
    still has to gate the Overlay layout.
    """
    chosen = st.session_state.get(COMPARE_SOURCE_KEY)
    return None if not chosen or chosen == THIS_DATASET else str(chosen)


#: B's filter result with nothing selected — the pool as it comes.
#: Used for the one run where B's stored filter result belongs to the dataset
#: the user just switched *away* from (see ``_resolve_compare_source``).
_NO_COMPARE_NARROWING: dict = {"participants": None, "metadata": {}, "ranges": {}}

_COMPARE_SOURCE_RESOLVED_KEY = COMPARE_SOURCE_RESOLVED_KEY


def _compare_source_choices() -> tuple[list[str], dict[str, bool], dict[str, str]]:
    """The **Compare with** options: every dataset scanpath B could come from.

    B's controls are one line, and a line
    has to know how many candidate trials B has before it can pick its grid —
    which means resolving the dataset *before* any of the row's widgets render,
    the same order ``app.main`` resolves A's pool in.
    """
    options = secondary_dataset_options(
        exclude=st.session_state.get("data_source_choice")
    )
    ready_by_name = {name: ready for name, ready, _ in options}
    reason_by_name = {name: why for name, _, why in options}
    names = [THIS_DATASET, *(name for name, _, _ in options)]
    if st.session_state.get(COMPARE_SOURCE_KEY) not in names:
        st.session_state[COMPARE_SOURCE_KEY] = THIS_DATASET
    return names, ready_by_name, reason_by_name


def _cancel_compare_source(task_key: tuple) -> None:
    """Cancel on B's dataset card — compare within A's dataset again."""
    progress.cancel(task_key)
    st.session_state[COMPARE_SOURCE_KEY] = THIS_DATASET


#: The task Compare's B card was last opened for, held while B's
#: dataset loads and dropped once the card's block completes — the replay's
#: `ANIM_TASK_KEY`, for B. An ``_sps_*`` internal: never on the wire, never in
#: the recovery cache.
COMPARE_TASK_KEY = "_sps_compare_task"


def _claim_compare_task(task_key: tuple) -> None:
    """Cancel the load a run started for another dataset as B, then remember
    this one's.

    Two corpora never load at once for B either, as for A: once B is another
    dataset, the first is a load nobody is waiting for. The same key — B's own
    load still under way — joins it.
    """
    previous = st.session_state.get(COMPARE_TASK_KEY)
    if previous is not None and tuple(previous) != task_key:
        progress.cancel(tuple(previous))
    st.session_state[COMPARE_TASK_KEY] = task_key


def _second_dataset_load(token: str) -> dict:
    """`CompareTarget`'s ``schemas`` and ``caveats`` for B's dataset ``token``."""
    from scanpath_studio.url_state import second_dataset_load

    schemas, caveats = second_dataset_load(token)
    return {"schemas": schemas, "caveats": caveats}


def _dataset_label(token: str) -> str:
    """A dataset as its picker names it (Select Dataset's name)."""
    from scanpath_studio.app import _dataset_display_name

    return _dataset_display_name(token)


def _abandon_compare_task() -> None:
    """This run loads no second dataset for B — "This dataset", a corpus not
    set up yet, or Compare off: stop the one an earlier run left loading
    rather than let it run on for nothing on screen. Compare within
    <A>, the card's own Cancel, cancels its load itself (`_cancel_compare_source`).
    """
    previous = st.session_state.pop(COMPARE_TASK_KEY, None)
    if previous is not None:
        progress.cancel(tuple(previous))


def _release_compare_task(task_key: tuple) -> None:
    """B's dataset is loaded: nothing of it is left to cancel.

    Only its own key is dropped — a later run may already have claimed another.
    """
    if st.session_state.get(COMPARE_TASK_KEY) == task_key:
        st.session_state.pop(COMPARE_TASK_KEY, None)


def _resolve_compare_source(
    ready_by_name: dict[str, bool],
    reason_by_name: dict[str, str],
    *,
    loading_slot=None,
) -> tuple[SecondaryDataset | None, str]:
    """Load scanpath B's dataset, narrowed by its own filters.

    Returns ``(source, notice)``. ``source`` is ``None`` for "This dataset" —
    where B comes out of A's pool — and also for a source
    that is offered but not loadable (a public corpus whose location has never
    been set), in which case ``notice`` says why: silently falling back would
    look like the picker was ignored.

    B's filters are **read from session state** rather than taken from the
    widgets, which render inside this row's filter popover, after this runs.
    That is the same contract A has — ``render_trial_filters`` stashes
    its result, and every widget's ``on_change`` recomputes the stash before the
    rerun, so a filter change still applies on the run it happens.

    ``loading_slot`` gives B's own load a card, with a Cancel back to
    "This dataset" — the compare picker is a selectbox in the middle of the plot
    column, so ``None`` (the default) still loads B plain, with no card and no
    way to cancel it. With a card, the load is remembered while it runs
    (`COMPARE_TASK_KEY`), so picking another dataset for B mid-load — or one
    that loads nothing: "This dataset", a corpus not set up yet — stops it.
    """
    chosen = str(st.session_state.get(COMPARE_SOURCE_KEY) or THIS_DATASET)
    if chosen == THIS_DATASET:
        _abandon_compare_task()
        return None, ""
    if not ready_by_name.get(chosen, False):
        _abandon_compare_task()
        _forget_compare_narrowing()
        return None, f"{ICONS['warning']} {reason_by_name.get(chosen, '')}"
    if loading_slot is None:
        source = load_secondary_dataset(chosen)
    else:
        task_key = ("compare_dataset", loading.session_id(), chosen)
        _claim_compare_task(task_key)
        with loading.card(
            loading_slot,
            # This card's own key — deliberately not `COMPARE_SOURCE_KEY`
            # ("cmp_dataset"), which names the picker's persisted widget key.
            key="compare_dataset",
            title=f"Loading {_dataset_label(chosen)} for scanpath B",
            task_key=task_key,
            cancel=loading.Cancel(
                f"Compare within {md_literal(current_dataset_name())}",
                _cancel_compare_source,
                args=(task_key,),
            ),
            # B is resolved on every run with Compare on — a cache hit,
            # slow only in its checks on a big corpus — so the card waits for
            # one of its builds to report a miss.
            reveal_on_work=True,
        ):
            source = load_secondary_dataset(chosen)
        _release_compare_task(task_key)
    if source is None:
        _forget_compare_narrowing()
        return (
            None,
            f"{ICONS['warning']} Couldn't load **{md_literal(_dataset_label(chosen))}** "
            "for scanpath B.",
        )
    # The run that *switches* dataset ignores the stored result: it was computed
    # against the corpus just left, and applying one corpus' reader ids to
    # another empties the pool for a run with nothing on screen explaining it.
    # The widgets below re-seed against the new source and stash a fresh result,
    # so the following run filters normally.
    filters = read_trial_filters(_COMPARE_FILTER_PREFIX)
    if st.session_state.get(_COMPARE_SOURCE_RESOLVED_KEY) != chosen:
        filters = dict(_NO_COMPARE_NARROWING)
    st.session_state[_COMPARE_SOURCE_RESOLVED_KEY] = chosen
    return _narrow_secondary(source, filters), ""


def _render_compare_dataset_cell(
    host, names: list[str], ready_by_name: dict[str, bool]
) -> None:
    """The **Compare with** selectbox — B's line's leading cell.

    Sits under A's dataset picker, on the same grid track, so the two control
    lines read down the page as *which dataset → which trial → scrub → act*.
    """
    # Lazy, like every other `app` reach from this module: app imports tabs, so
    # a module-level import would close the cycle.
    labels = {
        token: _dataset_label(token)
        if ready_by_name.get(token, True)
        else f"{_dataset_label(token)} (needs setup)"
        for token in names
        if token != THIS_DATASET
    }
    same_label = "This dataset"
    if same_label in labels.values():
        same_label = "Same dataset as A"
        index = 2
        while same_label in labels.values():
            same_label = f"Same dataset as A ({index})"
            index += 1
    labels[THIS_DATASET] = same_label

    host.selectbox(
        "Dataset B",
        options=names,
        key=COMPARE_SOURCE_KEY,
        # This widget renders only in Compare mode on the Scanpath view,
        # and its key is deep-link-seeded (`?cmp_source=`). Without this, one
        # trip through Corpus Analysis prunes the key and the link's choice is
        # silently lost.
        persist_state="session",
        # Streamlit has no per-option disabling, so an unready corpus is marked
        # in the label and explains itself below once picked — offered but
        # honest, rather than absent and mysterious.
        format_func=labels.__getitem__,
        help="The dataset scanpath B comes from. A trial from another dataset is "
        "drawn on that dataset's screen.",
    )
    widen_menu(COMPARE_SOURCE_KEY, [labels[name] for name in names])


def _compare_label_display(
    label: str, trial_id: str, markers: str, id_display: dict[str, str]
) -> str:
    """A *Compare to* option as shown: its trial id spelled out part by part.

    The option's value stays ``build_comparison_options``' label (the widget key
    holds it), so only the id inside it is swapped for its display form.
    """
    prefix = f"{markers} " if markers else ""
    shown = id_display.get(trial_id)
    if not shown or not label.startswith(prefix + trial_id):
        return label
    # The marks follow the trial, so a narrow picker cuts the marks,
    # not the id.
    rest = label[len(prefix) + len(trial_id) :]
    return f"{shown}{rest} {markers}" if markers else shown + rest


def _render_compare_filters(host, source: SecondaryDataset) -> None:
    """Every way to narrow **B's** pool, behind one funnel — A's popover, for B.

    B's narrow-by row and its **More** filters sit behind the one icon that
    closes B's line, so both lines end in the same cluster. The widgets carry
    the ``cmp`` prefix.
    """
    pop = host.popover(
        "Filter scanpath B's trials",
        icon=_FILTER_ICON,
        width="content",
        help="Filter scanpath B's trials",
        key="iconpop_filter_compare",
    )
    box = pop.container(key="cmp_narrow_by")
    box.caption(
        f"Filter the trials of **{md_literal(_dataset_label(source.name))}**. "
        "These apply to scanpath B only."
    )
    render_narrow_by(
        source.words,
        source.fixations,
        source.raw_gaze,
        prefix=_COMPARE_FILTER_PREFIX,
        text_host=box,
        part_host=box,
    )
    render_trial_filters(
        source.words,
        source.fixations,
        source.raw_gaze,
        prefix=_COMPARE_FILTER_PREFIX,
        host=box,
        names=across_tables(source.column_names),
    )


#: The `frame_cache` slots `_narrow_secondary` keeps its copies of B's pool in.
COMPARE_NARROWING_SLOTS = (
    "cmp_trial_filters",
    "cmp_trial_metadata_filter",
    "cmp_annotation_filter_readings",
    "cmp_annotation_filter",
)


def _forget_compare_narrowing() -> None:
    """Drop B's narrowed copies of its pool once nothing narrows B: Compare is
    off, or B's dataset did not load."""
    for slot in COMPARE_NARROWING_SLOTS:
        forget_frame_cache(slot)


def _narrow_secondary(source: SecondaryDataset, filters: dict) -> SecondaryDataset:
    """Apply B's own (``cmp``-prefixed) trial filters to a comparison source.

    Its ⭐ / tag filters read B's own dataset's annotations
    (``annotations.store_for_prefix("cmp")``): the open dataset's for
    "This dataset", and another corpus' own when B comes from one — never A's,
    whose matching-looking ids name other trials.
    """
    # Each step names its new frames by its inputs and settings, as A's chain
    # in `app._run_app` does, so B's pool is not re-hashed per rerun. Decided
    # per reading across B's two tables, once per filter change — in a slot of
    # its own, or A's and B's would evict each other each run.
    selected = select_trials_cached(
        source.words, source.fixations, filters, slot="cmp_trial_filters"
    )
    words, fixations = selected.words, selected.fixations
    assign_derived(
        (words, fixations),
        "filter_trials",
        (source.words, source.fixations),
        trial_filter_params(filters),
    )
    words, fixations = filter_to_keys_cached(
        words, fixations, filters.get("trial_keys"), slot="cmp_trial_metadata_filter"
    )
    kept = None
    if (
        filters.get("favorites_only")
        or filters.get("required_tags")
        or filters.get("excluded_tags")
    ):
        present = frame_cache(
            "cmp_annotation_filter_readings",
            (frame_fingerprint(words), frame_fingerprint(fixations)),
            lambda: trial_keys(words) | trial_keys(fixations),
        )
        kept = set(
            filter_keys(
                list(present),
                favorites_only=bool(filters.get("favorites_only")),
                required_tags=list(filters.get("required_tags") or []),
                excluded_tags=list(filters.get("excluded_tags") or []),
                prefix=_COMPARE_FILTER_PREFIX,
            )
        )
    else:
        forget_frame_cache("cmp_annotation_filter_readings")
    words, fixations = filter_to_keys_cached(
        words, fixations, kept, slot="cmp_annotation_filter"
    )
    if fixations is source.fixations and words is source.words:
        return source
    combos, _, _ = build_combo_options_for(fixations, source.composite_trial_columns)
    return replace(source, words=words, fixations=fixations, combos=combos)


def _render_compare_selector(
    combos: pd.DataFrame,
    selection_mode: str,
    selected_participant: str,
    selected_trial: str,
    selected_text: str | None,
    animate: bool = False,
    fixations_filtered: pd.DataFrame | None = None,
    words_filtered: pd.DataFrame | None = None,
    combos_all: pd.DataFrame | None = None,
    words_all: pd.DataFrame | None = None,
    fixations_all: pd.DataFrame | None = None,
    loading_slot=None,
    screen_cells: dict | None = None,
    screen_track: bool = False,
) -> tuple[
    str | None,
    str | None,
    SecondaryDataset | None,
    SecondaryDataset | None,
]:
    """The compare-trial (B) selector, rendered above the chips.

    Mirrors the main trial picker: a ``selectbox`` showing the trial id (+ 📄/👤
    markers) and a scrubbing ``select_slider`` showing ``"index/TOTAL · <trial
    id>"``, plus ◀ ▶ step buttons and a sort picker. The sort picker uses
    the main trial picker's generated choices; only its default differs, keeping
    same-text trials first, then same-participant trials, then the rest. The
    overlay layout + A/B-legend config live in the rail's **⚙️ Compare** popover
    (under the Compare toggle).

    A *dataset* picker leads the row: B may come from a different
    corpus entirely, in which case the candidate pool, the narrow-by filters and
    the screen geometry are all that dataset's own. Returns
    ``(participant, trial, source, pool)`` — ``source`` is ``None`` for the
    same-dataset case, while ``pool`` always carries the independently filtered
    B frames from which the selected trial must be extracted.

    B's row is A's row — ``[Dataset B] [Trial B] [scrub slider] [◀ ▶ ⇅ filter]``
    on the same ``SELECTOR_ROW_GRID``. The dataset is therefore resolved from
    session state *before* the row is drawn (``_resolve_compare_source``), since
    how many candidates B has is what decides whether the row has a slider.

    ``loading_slot`` is threaded straight through to
    ``_resolve_compare_source`` so B's own load gets a card + Cancel there.

    The row ends in a screen cell — stored as ``screen_cells["b"]`` for B's
    screen navigator — when B's pool has screens or ``screen_track`` asks for
    one (A's row has one, so the two rows keep the same tracks).
    """
    names, ready_by_name, reason_by_name = _compare_source_choices()
    source, source_notice = _resolve_compare_source(
        ready_by_name, reason_by_name, loading_slot=loading_slot
    )
    filter_source = source
    comparison_pool = source
    if source is not None:
        # B's pool is its own dataset, narrowed by its own filters, and
        # nothing about A applies to it.
        options = build_comparison_options(
            source.combos,
            selection_mode,
            selected_participant,
            selected_trial,
            selected_text,
            cross_dataset=True,
        )
        words_filtered, fixations_filtered = source.words, source.fixations
        combos = source.combos
    elif str(st.session_state.get(COMPARE_SOURCE_KEY) or THIS_DATASET) != THIS_DATASET:
        # The requested external source is unavailable. Keep its picker and
        # notice on screen, but never fall back to trials from the active
        # dataset — that would make a failed dataset choice look successful.
        options = []
        filter_source = None
    else:
        # "This dataset" still gets an independent B filter. Build it from the
        # unfiltered frames (A's filters must not constrain B), then keep the
        # returned ``source`` as None so every downstream same-dataset geometry
        # and annotation path remains unchanged.
        full_words = words_all if words_all is not None else words_filtered
        full_fixations = (
            fixations_all if fixations_all is not None else fixations_filtered
        )
        full_combos = combos_all if combos_all is not None else combos
        if full_words is None:
            full_words = pd.DataFrame()
        if full_fixations is None:
            full_fixations = pd.DataFrame()
        current_name = str(st.session_state.get("data_source_choice") or THIS_DATASET)
        filter_source = SecondaryDataset(
            name=current_name,
            words=full_words,
            fixations=full_fixations,
            combos=full_combos,
            setup=snapshot_for(current_name, full_words, full_fixations),
            composite_trial_columns=tuple(
                st.session_state.get("_composite_trial_columns") or ()
            ),
            column_names={
                table: active_column_names(st.session_state, table)
                for table in ("fixations", "words", "raw_gaze")
            },
        )
        same_filters = read_trial_filters(_COMPARE_FILTER_PREFIX)
        if st.session_state.get(_COMPARE_SOURCE_RESOLVED_KEY) != THIS_DATASET:
            same_filters = dict(_NO_COMPARE_NARROWING)
        st.session_state[_COMPARE_SOURCE_RESOLVED_KEY] = THIS_DATASET
        narrowed = _narrow_secondary(filter_source, same_filters)
        comparison_pool = narrowed
        combos = narrowed.combos
        words_filtered = narrowed.words
        fixations_filtered = narrowed.fixations
        options = build_comparison_options(
            combos, selection_mode, selected_participant, selected_trial, selected_text
        )
    # Any multipart trial is a valid B candidate, whatever screen A has
    # selected: B chooses its own screen from its own navigator (rendered once
    # it's chosen), which is what narrows it to one coordinate space.
    # ONE row for scanpath B, the mirror of A's above it:
    # `[Dataset B] [Trial B] [scrub slider] [◀ ▶ ⇅ filter]` on the same
    # `SELECTOR_ROW_GRID`. The dataset keeps a track of its own and does not
    # shrink — the label is what tells two compared corpora apart — and a
    # one-candidate pool drops the slider exactly as A's row does
    # (`st.select_slider` throws on a single option).
    #
    # Built BEFORE the "no candidates" notice below, so the dataset picker and
    # the filters that emptied the pool are still on screen to undo it.
    n = len(options)
    slider_col = None
    screen_track = screen_track or any(
        frame is not None and SCREEN_ID in frame.columns
        for frame in (
            words_filtered,
            fixations_filtered,
            source.raw_gaze if source else None,
        )
    )
    extra_track = [SELECTOR_SCREEN_TRACK] if screen_track else []
    if n > 1:
        lead_col, sel_col, slider_col, trail_col, *extra = st.columns(
            SELECTOR_ROW_GRID + extra_track, vertical_alignment="bottom"
        )
    else:
        lead_col, sel_col, trail_col, *extra = st.columns(
            SELECTOR_ROW_TRIO + extra_track, vertical_alignment="bottom"
        )
    menus = None
    if extra:

        def _reserve(host) -> None:
            if screen_cells is not None:
                screen_cells["b"] = host.container(key="tour_grp_compare_screen_picker")

        menus = row_tail(extra[0], "single_compare", _reserve)
    _render_compare_dataset_cell(lead_col, names, ready_by_name)
    trail = trail_col.container(
        key=f"railbtn_single_compare_trail{'_steps' if menus else ''}"
    )
    # ⇅ and the filter close the row after B's screen cell when there is one.
    cluster = trail if menus is None else menus
    # Candidate sorting is visually LAST in the row, after the step buttons.
    # It still executes before the selectbox/slider below, so a change applies
    # to their list on the same run. As in the main trial picker, ◀ / ▶ / ⇅ and
    # the filter share one right-packed `railbtn_*` pill cluster.
    # The sort is UI-only: it never travels in a deep link or saved config.
    step_col = sort_col = None
    if n > 1:
        # Created in display order, then filled out of order: the ordering
        # popover has to run first because its result is the list the selectbox,
        # the slider and the ◀ ▶ steps all walk.
        step_col = trail.container(key="railbtn_single_compare_step")
        sort_col = cluster.container(key="railbtn_single_compare_sort")
    # B always has its own filter set. For "This dataset" it starts from the
    # unfiltered active frames, so narrowing B never changes scanpath A.
    if filter_source is not None:
        _render_compare_filters(
            cluster.container(key="railbtn_single_compare_filter"), filter_source
        )
    if source_notice:
        st.caption(source_notice)
    if not options:
        if source_notice:
            pass
        elif source is not None:
            st.info(
                f"No trials in **{md_literal(_dataset_label(source.name))}** match "
                "B's filters."
            )
        else:
            st.info("No trials match scanpath B's filters.")
        return None, None, None, None

    sort_keys = trial_sort_keys(
        combos,
        "trial_id",
        words=words_filtered,
        fixations=fixations_filtered,
        label_of=(
            across_tables(source.column_names)
            if source is not None
            else active_all(st.session_state)
        ).label,
    )
    sort_options = [_CMP_SORT_DEFAULT, TRIAL_SORT_DEFAULT, *sort_keys]

    sort_choice = _CMP_SORT_DEFAULT
    # What the list is actually ordered by, which linking can override — see the
    # note beside the popover below.
    order_choice = sort_choice
    sort_desc = False
    if sort_col is not None:
        if st.session_state.get("single_compare_order") not in sort_options:
            st.session_state["single_compare_order"] = _CMP_SORT_DEFAULT
        # Named for screen readers; `styles.py` draws ⇅ alone.
        with sort_col.popover(
            "Sort the comparison trials",
            width="content",
            wrap=True,
            help="Sort the comparison trials",
            key="iconpop_sort_compare",
        ):
            sort_choice = _labeled(
                st,
                "selectbox",
                "Sort trials by",
                options=sort_options,
                key="single_compare_order",
                help="The default keeps related trials together: same text, then "
                "the same participant, then all remaining trials. Other choices "
                "match the main trial picker's sort menu.",
            )
            sort_desc = _labeled(
                st,
                "checkbox",
                "Descending",
                key="single_compare_sort_desc",
                disabled=sort_choice in {_CMP_SORT_DEFAULT, TRIAL_SORT_DEFAULT},
            )
            # The default order is computed *relative to A* — 📄 same-text
            # candidates lead — so the moment A crosses into another text, B's
            # whole pool re-ranks and its position readout leaps (10/23 → 22/23)
            # even though the linked step landed on exactly the right trial.
            # Walking two trials in lockstep only means anything against a track
            # that holds still, so linking pins the order for as long as it is on,
            # to the order A walks by default — data order when the pool carries
            # it, else Trial ID. Resolved into a local, never written back to the
            # widget key: the user's chosen sort must survive un-linking (the same
            # don't-rewrite-a-gated-setting rule as `controls._mode_gate`).
            if compare_step_linked() and sort_choice == _CMP_SORT_DEFAULT:
                order_choice = (
                    TRIAL_SORT_DATA_ORDER
                    if TRIAL_SORT_DATA_ORDER in sort_keys
                    else TRIAL_SORT_DEFAULT
                )
                st.caption(
                    f"Sorted by **{order_choice}** while *Step · A and B together* "
                    "is on, so B keeps its place in the list when A changes text."
                )
            else:
                order_choice = sort_choice
        options = _order_compare_options(
            options,
            order_choice,
            sort_keys,
            descending=sort_desc,
        )

    labels = [opt[2] for opt in options]
    label_to_trial = {opt[2]: (opt[0], opt[1]) for opt in options}
    # B's trial ids spelled out part by part, as A's picker shows them.
    composite_b = (
        filter_source.composite_trial_columns if filter_source is not None else ()
    )
    id_display, id_part_names = trial_id_layout(combos, composite_cols=composite_b)
    label_to_id = {opt[2]: id_display.get(str(opt[1]), str(opt[1])) for opt in options}
    label_display = {
        opt[2]: _compare_label_display(opt[2], str(opt[1]), opt[3], id_display)
        for opt in options
    }

    sel_key = "single_compare_trial"
    pos_key = "single_compare_pos"
    identity_to_label = {(str(opt[0]), str(opt[1])): opt[2] for opt in options}
    # A `?compare=<pid>:<trial>` deep link parks its ids in
    # `_apply_url_preset`; the labels only exist here, so this is where it lands.
    # Consumed once, and only when the pool can actually answer it — a request
    # for a trial the current filters exclude is dropped rather than left to
    # re-point the picker after some later filter change.
    pending = st.session_state.pop(PENDING_COMPARE_STATE_KEY, None)
    if isinstance(pending, dict):
        wanted = (str(pending.get("participant_id")), str(pending.get("trial_id")))
        # An old link may spell a composite id without escaping a `_` in a part.
        wanted = respell_reading(*wanted, identity_to_label)
        if wanted in identity_to_label:
            st.session_state[sel_key] = identity_to_label[wanted]
        else:
            # A link or settings file named a B this pool cannot answer — say
            # so, rather than let the default candidate pass for the pair.
            st.warning(
                f"Couldn't restore scanpath B: participant {wanted[0]}'s trial "
                f"{wanted[1]} is not among B's trials. Showing another trial "
                "instead.",
                icon=ICONS["warning"],
            )

    # The widget key holds a *label*, and the labels are rebuilt relative to A —
    # the 📄 same-text and 👤 same-participant markers are computed against the
    # selected trial. So the moment A moves to a different text, B's stored label
    # names nothing in the new list, and the picker would silently fall back to
    # the first candidate on *any* A step, linked or not.
    #
    # So B is remembered by identity and its label re-resolved each run.
    # Order matters: the user's live pick (a label that is still valid) wins over
    # the remembered identity, or selecting a new B would be undone by the
    # previous one on the very next run.
    current = st.session_state.get(sel_key)
    lost_identity = None
    # A's own trial is in B's list, so the two readouts count the same
    # trials — but it is never the *default*: a fresh B is the first candidate
    # that is not A. Only a user's pick (or a link) lands B on A itself.
    primary_identity = (str(selected_participant), str(selected_trial))
    default_label = next(
        (
            opt[2]
            for opt in options
            if source is not None or (str(opt[0]), str(opt[1])) != primary_identity
        ),
        labels[0],
    )
    if current not in labels:
        remembered = st.session_state.get(_COMPARE_IDENTITY_KEY)
        if isinstance(remembered, list):  # as the recovery cache stores it
            remembered = tuple(str(v) for v in remembered)
        if isinstance(remembered, tuple) and remembered in identity_to_label:
            current = identity_to_label[remembered]
        elif remembered is not None and current is not None:
            # Genuinely gone from the pool — B's filters or dataset no longer
            # admit it. Say so rather than swapping the panel silently.
            lost_identity = remembered
            current = default_label
        else:
            current = default_label
        st.session_state[sel_key] = current
    st.session_state[_COMPARE_IDENTITY_KEY] = tuple(
        str(v) for v in label_to_trial[current]
    )
    if lost_identity is not None:
        st.caption(
            f"`{lost_identity[1]}` is no longer among B's trials. "
            "Showing another trial instead."
        )

    # Publish the candidates as rendered — label plus identity, because
    # the labels are rebuilt relative to A and only the identity survives A moving.
    st.session_state[COMPARE_OPTIONS_SNAPSHOT_KEY] = [
        (opt[2], str(opt[0]), str(opt[1])) for opt in options
    ]

    if n > 1:
        idx_of = {lbl: i for i, lbl in enumerate(labels)}
        # Mirror the slider to the current selection before it renders.
        st.session_state[pos_key] = current

        def _remember_compare_identity(label: str) -> None:
            # B is re-resolved by *identity* every run (see above),
            # because its labels are rebuilt relative to A and a stale label
            # string stops matching the moment A's move changes a 📄/👤
            # marker. That reconciliation reads `_COMPARE_IDENTITY_KEY` — so a
            # write here that only sets `sel_key` (the label) leaves it
            # pointing at the trial *before* the click, and the very next run
            # silently snaps back to it while A has already moved. Both
            # widget callbacks below write the identity alongside the label so
            # the reconciliation always names where the click actually landed.
            trial = label_to_trial.get(label)
            if trial is not None:
                st.session_state[_COMPARE_IDENTITY_KEY] = tuple(str(v) for v in trial)

        def _on_compare_slider() -> None:
            st.session_state[sel_key] = st.session_state[pos_key]
            _remember_compare_identity(st.session_state[pos_key])

        def _step_compare(delta: int) -> None:
            new_pos = step_within(labels, sel_key, delta)
            if new_pos is not None:
                _remember_compare_identity(labels[new_pos])
            # The link works in both directions — B's ◀ ▶ move A too.
            # A's ids are stable (they don't depend on B), so this steps A's
            # canonical key straight from the list its picker last rendered.
            if compare_step_linked():
                step_within(
                    st.session_state.get(trial_options_snapshot_key("single")) or [],
                    "single_trial_id",
                    delta,
                )

        current_idx = labels.index(current)

    # The label is shown, like A's *Select trial*, so its help "?" is there.
    selected_compare_label = sel_col.selectbox(
        "Trial B",
        options=labels,
        key=sel_key,
        format_func=lambda v: label_display.get(v, v),
        help=" ".join(
            filter(
                None,
                (
                    f"{SAME_TEXT_MARKER} the same text as the selected trial · "
                    f"{SAME_PARTICIPANT_MARKER} the same participant. "
                    "★ favorite · 🏷️ tagged · 📝 has notes.",
                    trial_id_help(id_part_names),
                ),
            )
        ),
    )
    widen_menu(sel_key, [label_display.get(v, v) for v in labels])
    if n > 1:
        with slider_col:
            st.select_slider(
                "Compare position",
                options=labels,
                key=pos_key,
                on_change=_on_compare_slider,
                label_visibility="collapsed",
                format_func=lambda v: (
                    f"{idx_of.get(v, 0) + 1}/{n} · {label_to_id.get(v, v)}"
                ),
                help=f"Move through the {n} trials scanpath B can show.",
            )
        # Mirror of the main picker — linked, a button dies only when
        # *both* lists have run out.
        linked = compare_step_linked()
        primary_options = (
            st.session_state.get(trial_options_snapshot_key("single")) or []
            if linked
            else []
        )
        step_help = (
            " With *A and B together* on, this also steps scanpath A." if linked else ""
        )
        step_col.button(
            f"◀ {spoken('Previous comparison trial')}",
            wrap=True,
            key="single_compare_prev",
            on_click=_step_compare,
            args=(-1,),
            disabled=current_idx == 0
            and (not linked or at_list_end(primary_options, "single_trial_id", -1)),
            help="Previous trial for scanpath B (Shift + Left arrow)." + step_help,
        )
        step_col.button(
            f"▶ {spoken('Next comparison trial')}",
            wrap=True,
            key="single_compare_next",
            on_click=_step_compare,
            args=(1,),
            disabled=current_idx == n - 1
            and (not linked or at_list_end(primary_options, "single_trial_id", 1)),
            help="Next trial for scanpath B (Shift + Right arrow)." + step_help,
        )

    if selected_compare_label:
        return (*label_to_trial[selected_compare_label], source, comparison_pool)
    return None, None, None, None


_CRITICAL_SPAN_BG = "#FCE7F3"  # light pink — critical-span words
_DISTRACTOR_SPAN_BG = "#E5E7EB"  # light grey — distractor-span words
# These highlight backgrounds are always light (they mirror the light stimulus),
# so pin a dark text color too — otherwise the inherited theme text color goes
# light in dark mode and the highlighted text is unreadable (light-on-light).
_HIGHLIGHT_TEXT_COLOR = "#212529"

# Fixed span colours for the known OneStop span columns; other span columns
# cycle through a palette, so the panel works on arbitrary datasets. A field
# is *named* by the dataset's own name for its column (`_field_label`).
_KNOWN_SPAN_BG = {"is_in_aspan": _CRITICAL_SPAN_BG, "is_in_dspan": _DISTRACTOR_SPAN_BG}
# Light backgrounds for any further detected span columns (cycled).
_SPAN_BG_PALETTE = ["#FEF3C7", "#DBEAFE", "#DCFCE7", "#FAE8FF", "#FFE4E6"]
# Substrings that mark a per-word boolean column as a highlightable span, and a
# trial-level column as question/answer content. Dataset-agnostic by design.
_SPAN_NAME_HINTS = ("span", "highlight", "critical", "target", "aoi_of_interest")
_QA_NAME_HINTS = (
    "question",
    "answer",
    "correct",
    "response",
    "prompt",
    "title",
    "instruction",
    "context",
    "heading",
    "subtitle",
)


def _field_label(col: str) -> str:
    """A stimulus / context field's name: the dataset's own for it."""
    return active_all(st.session_state).field_label(col)


def _is_boolish(series: pd.Series) -> bool:
    """True when a column holds only boolean-like values (per-word span flags).

    Accepts real booleans, numeric 0/1, and the string spellings ``True/False``.
    Deliberately excludes string ``"0"``/``"1"`` so a string-typed id column that
    happens to contain only ``"0"``/``"1"`` isn't mistaken for a span flag."""
    if pd.api.types.is_bool_dtype(series):
        return True
    vals = set(series.dropna().unique())
    return bool(vals) and vals <= {
        True,
        False,
        "True",
        "False",
        "true",
        "false",
    }


def _flag_mask(series: pd.Series) -> pd.Series:
    """A span / flag column as a plain mask: true only where the value means
    true — the string ``"False"`` is false, and an unknown spelling is not true
    (``astype(bool)`` would read every non-empty string as true)."""
    return coerce_bool_or_na(series).fillna(False).astype(bool)


def _detect_span_columns(trial_words: pd.DataFrame) -> list[str]:
    """Per-word boolean columns that mark a highlightable span (generic).

    Known OneStop spans (``is_in_aspan``/``is_in_dspan``) come first so they keep
    their fixed colours; any further span-like boolean columns follow.
    """
    detected = [
        c
        for c in user_columns(trial_words)
        if any(h in c.lower() for h in _SPAN_NAME_HINTS)
        and _is_boolish(trial_words[c])
        and bool(_flag_mask(trial_words[c]).any())
    ]
    known = [c for c in ("is_in_aspan", "is_in_dspan") if c in detected]
    rest = [c for c in detected if c not in known]
    return known + rest


def _detect_question_columns(trial_words: pd.DataFrame) -> list[str]:
    """Trial-level columns holding useful stimulus context.

    Matches columns whose name reads as question/answer/correct/… but excludes
    span-named columns and **per-word-varying boolean** columns: a boolean that
    differs across the trial's words (e.g. a per-word ``response`` mask) is
    span-like data, not a trial-level field, and rendering its first value as
    ``"Response: True"`` would be misleading. A *constant* boolean (e.g.
    ``is_correct``) is a legitimate trial-level field and is kept. Also excludes
    plain numeric columns: an automatically detected context field is
    text or boolean, so
    an unrelated numeric column that merely matches a name hint — e.g. a
    ``response_time_ms`` timing column on a generic upload — would otherwise
    render as a bogus "Response time ms: 120" line.
    """
    out = []
    for c in user_columns(trial_words):
        lc = c.lower()
        if c == "comprehension_questions":
            continue  # structured JSON, rendered by _render_comprehension_questions
        if not any(h in lc for h in _QA_NAME_HINTS) or _is_boolish_span(c):
            continue
        col = trial_words[c]
        boolish = _is_boolish(col)
        if boolish and col.dropna().nunique() > 1:
            continue  # per-word-varying boolean → not a trial-level Q&A field
        if not boolish and pd.api.types.is_numeric_dtype(col):
            continue  # a timing/count/id column, not question/answer text
        out.append(c)
    return out


#: Columns the Stimulus & context field picker never offers: the
#: stimulus text itself, word geometry, and the identity columns the trial chips
#: above the plot already carry.
_STIMULUS_FIELD_EXCLUDE = frozenset(
    {
        "text",
        "word_id",
        "line_idx",
        "x",
        "y",
        "width",
        "height",
        "participant_id",
        "trial_id",
        "text_id",
        "comprehension_questions",
    }
)
#: Session keys behind the picker. UI-only in the four-surface sense — they
#: choose what a *panel* lists, not anything a figure renders, so there is nothing
#: for the deep link / CLI / headless API to carry.
#:
#: They are still **widget** keys, though, which the trial-chip picker they
#: otherwise resemble is not (`controls.py` writes `trial_chip_fields` directly).
#: That difference is load-bearing: Streamlit drops a widget's key at the end of
#: any run in which the widget did not render, and this panel lives only in the
#: Scanpath view — so one trip through Corpus Analysis would prune both keys, and
#: the signature guard below (a plain key, which survives) would then never
#: re-seed them. Hence `persist_state="session"` on both multiselects, the same
#: rule as every `global_*` / `single_*` widget.
_STIMULUS_SPAN_KEY = "stimulus_span_fields"
_STIMULUS_QA_KEY = "stimulus_qa_fields"
_STIMULUS_SIG_KEY = "_stimulus_fields_signature"


@st.cache_data(show_spinner=False)
def _c_stimulus_field_candidates(
    _trial_words: pd.DataFrame, cache_key: tuple
) -> tuple[list[str], list[str]]:
    """Cached :func:`_stimulus_field_candidates` (house `_c_*` convention).

    The scan is per-column `dropna().nunique()`, which on a wide schema (OneStop
    ships ~60 columns) costs ~5 ms — small in isolation, but this panel renders
    on *every* rerun of the Scanpath view regardless of which subtab is showing,
    so uncached it would cost ~15× what the two name-hint detectors do.
    Keyed on the frame fingerprint like every other `_c_*` wrapper, so an edited
    or re-uploaded corpus re-derives.
    """
    return _stimulus_field_candidates(_trial_words)


def _stimulus_field_candidates(
    trial_words: pd.DataFrame,
) -> tuple[list[str], list[str]]:
    """(span candidates, Q&A candidates) the picker may offer for this trial.

    Wider than what :func:`_detect_span_columns` / :func:`_detect_question_columns`
    pick automatically, and deliberately so — auto-detection has to be
    conservative (a name hint alone would pick a `response_time_ms` column), but
    once the user is choosing explicitly the right pool is *everything shaped
    like* a span or a trial-level field, name hints aside.

    The split is by shape, not by name, and it turns on whether a column *varies
    across the trial's words*: a boolean that changes word to word marks a span,
    a boolean that is constant is a trial-level fact (``is_correct``) and belongs
    with the Q&A fields, exactly as :func:`_detect_question_columns` already
    treats it. Constant non-boolean columns are Q&A candidates too, numeric ones
    included — auto-detection refuses to guess at a numeric, but a deliberately
    picked timing column is a legitimate thing to want on screen.
    """
    spans, qa = [], []
    for col in user_columns(trial_words):
        if col in _STIMULUS_FIELD_EXCLUDE:
            continue
        series = trial_words[col]
        varies = series.dropna().nunique() > 1
        if _is_boolish(series) and bool(_flag_mask(series).any()):
            (spans if varies else qa).append(col)
        elif not varies:
            qa.append(col)
    return spans, qa


def _stimulus_fields(trial_words: pd.DataFrame) -> tuple[list[str], list[str]]:
    """The span + Q&A columns to render, honouring the user's picks.

    Auto-detection stays the *default*; the picker only overrides it. The stored
    choice is re-seeded whenever the dataset changes shape — switching to another
    corpus should go back to what that corpus auto-detects, rather than leaving
    the panel empty because none of the previous dataset's columns exist — but is
    left alone otherwise, so stepping through trials doesn't undo a choice.

    Returns ``(spans, qa)`` and also the option pools, so the picker beside it
    doesn't scan the frame a second time.
    """
    span_options, qa_options = _c_stimulus_field_candidates(
        trial_words, frame_fingerprint(trial_words)
    )
    # The signature is the *column set*, not the derived option pools. Those are
    # computed from this trial's slice, so a trial whose critical span happens to
    # be empty classifies that column differently — and keying the re-seed on
    # them would silently reset the user's picks on that trial, which is the
    # opposite of what the paragraph above promises.
    signature = tuple(map(str, trial_words.columns))
    # Re-seed on a changed candidate pool *or* on a missing key. The second case
    # should not happen — `persist_state="session"` is what keeps these alive
    # while the panel is unmounted — but the signature is a plain key and would
    # survive a pruning that took the widget keys with it, leaving the panel
    # permanently blank with nothing to trigger a recovery.
    if (
        st.session_state.get(_STIMULUS_SIG_KEY) != signature
        or _STIMULUS_SPAN_KEY not in st.session_state
        or _STIMULUS_QA_KEY not in st.session_state
    ):
        st.session_state[_STIMULUS_SIG_KEY] = signature
        st.session_state[_STIMULUS_SPAN_KEY] = _detect_span_columns(trial_words)
        st.session_state[_STIMULUS_QA_KEY] = _detect_question_columns(trial_words)
    spans = [
        c for c in st.session_state.get(_STIMULUS_SPAN_KEY, []) if c in span_options
    ]
    qa = [c for c in st.session_state.get(_STIMULUS_QA_KEY, []) if c in qa_options]
    return spans, qa, span_options, qa_options


def _render_stimulus_field_picker(host, span_options, qa_options) -> None:
    """The ⚙️ Fields popover: which columns this panel highlights and lists.

    Name hints alone make the panel generic only when the column *names*
    cooperate — a corpus whose critical span is called `focus_region`, or whose
    question column is `q_text`, would get nothing. This is the escape hatch:
    name hints pick the defaults, and anything they miss (or wrongly include) is
    one click away.

    Takes the option pools rather than the frame: `_stimulus_fields` has already
    derived them for this run, and re-deriving here would scan the words frame a
    second time on every rerun.
    """
    if not span_options and not qa_options:
        return
    with host.popover(f"{ICONS['settings']} Fields", width="content"):
        st.caption(
            "Choose which columns to show in this panel. Columns are selected "
            "automatically by name; add or remove them here."
        )
        if span_options:
            labeled(
                st,
                "multiselect",
                "Highlighted spans",
                options=span_options,
                format_func=_field_label,
                key=_STIMULUS_SPAN_KEY,
                persist_state="session",
                help="Choose true/false word columns. Each column highlights "
                "its matching words in the text and adds a summary below.",
            )
        if qa_options:
            labeled(
                st,
                "multiselect",
                "Context fields",
                options=qa_options,
                format_func=_field_label,
                key=_STIMULUS_QA_KEY,
                persist_state="session",
                help="Trial-level context such as a title, instruction, question, "
                "or answer.",
            )


_ANSWER_YES_COLOR = "#198754"
_ANSWER_NO_COLOR = "#dc3545"


def _literal(value: object) -> str:
    """A dataset value as literal text inside the panel's app-owned HTML.

    Interpolated into Markdown, a question, answer or context value such as
    ``![x](https://host/pixel)`` would fetch a remote image, and ``**answer**``
    would come out bold. Escaped into an HTML block they are inert —
    Markdown, Streamlit's ``:colour[…]`` / emoji / LaTeX syntax and tags all
    show as the characters they are. Line breaks become ``<br>``: a blank line
    would end the HTML block and hand the rest back to the Markdown parser.
    """
    text = html.escape(str(value)).replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "<br>")


def _context_block_html(lines: list[str]) -> str:
    """The Stimulus & context fields as one block, a line per field."""
    body = "".join(f'<div class="sps-context-line">{line}</div>' for line in lines)
    return f'<div class="sps-context" style="line-height:1.6">{body}</div>'


def _field_label_html(col: str) -> str:
    """``<b>name:</b>`` for a context field, with its description as a tooltip."""
    tip = field_help(col, active_all(st.session_state))
    title = f' title="{html.escape(tip)}"' if tip else ""
    return f"<b{title}>{_literal(_field_label(col))}:</b>"


def _context_html(body: str) -> None:
    """One app-owned line of the Stimulus & context panel (values `_literal`)."""
    st.markdown(f'<div class="sps-context-line">{body}</div>', unsafe_allow_html=True)


def _answer_mark(value: bool, yes: str, no: str) -> str:
    color, text = (_ANSWER_YES_COLOR, yes) if value else (_ANSWER_NO_COLOR, no)
    return f'<span style="color:{color};">{text}</span>'


@dataclass(frozen=True)
class _Question:
    """One structured comprehension question, every field already text."""

    number: str
    condition: str
    question: str
    target: str
    distractors: tuple[str, ...]


def _question_text(value: object) -> str | None:
    """A question field as text: ``""`` when absent, ``None`` when it is not a
    scalar (a list or an object where text belongs)."""
    if value is None:
        return ""
    if isinstance(value, float) and not np.isfinite(value):
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    return None


def _parse_comprehension_questions(raw: str) -> tuple[list[_Question], int]:
    """``comprehension_questions`` JSON → ``(questions, records skipped)``.

    The column is data, so its shape is checked rather than assumed (a JSON
    *object* would iterate as its keys and crash every rerun of the trial).
    The root must be a list; each record an object whose fields are
    scalars and whose ``distractors`` is a list of scalars. A record that is
    not is skipped and counted; a value that is not JSON at all counts as one.
    """
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return [], 1
    if items in (None, "", [], {}):
        return [], 0
    if not isinstance(items, list):
        return [], 1
    questions: list[_Question] = []
    skipped = 0
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            skipped += 1
            continue
        fields = {
            key: _question_text(item.get(key))
            for key in ("question_no", "condition", "question", "target")
        }
        distractors = item.get("distractors")
        if distractors is None:
            distractors = []
        texts = (
            [_question_text(d) for d in distractors]
            if isinstance(distractors, list)
            else [None]
        )
        if any(v is None for v in (*fields.values(), *texts)):
            skipped += 1
            continue
        condition = fields["condition"]
        questions.append(
            _Question(
                number=fields["question_no"] or str(i),
                condition="" if condition.lower() == "nan" else condition,
                question=fields["question"],
                target=fields["target"],
                distractors=tuple(t for t in texts if t),
            )
        )
    return questions, skipped


def _render_comprehension_questions(trial_words: pd.DataFrame) -> None:
    """Render structured comprehension questions for the trial's stimulus.

    Parses the ``comprehension_questions`` JSON column (MultiplEYE) into a list of
    questions, each with the target (✓ reference answer) and distractors. The
    corpus records no per-reader answer, so the target is shown as the key only —
    not as a 'selected'/'correct' result. No-op when the column is absent or
    empty; records it cannot read are skipped with one warning
    (:func:`_parse_comprehension_questions`)."""
    raw = _first_str(trial_words, "comprehension_questions")
    if not raw:
        return
    questions, skipped = _parse_comprehension_questions(raw)
    if skipped:
        st.warning(
            f"{plural(skipped, 'comprehension question record')} in this trial's "
            f"{md_literal(_field_label('comprehension_questions'))} could not be read "
            "and " + ("is" if skipped == 1 else "are") + " not shown.",
            icon=ICONS["warning"],
        )
    if not questions:
        return
    _context_html("<b>Comprehension questions</b>")
    for q in questions:
        head = f"<b>Q{_literal(q.number)}</b>"
        if q.condition:
            head += f" · <i>{_literal(q.condition)}</i>"
        options = []
        if q.target:
            options.append(f"<li>✓ {_literal(q.target)}</li>")
        options += [f"<li>{_literal(d)}</li>" for d in q.distractors]
        listed = f'<ul style="margin:0.2rem 0 0.6rem;">{"".join(options)}</ul>'
        _context_html(f"{head}: {_literal(q.question)}" + (listed if options else ""))


def _is_boolish_span(col: str) -> bool:
    """A name that reads as a span flag rather than a Q&A text field."""
    return any(h in col.lower() for h in _SPAN_NAME_HINTS)


def _span_bg_for(col: str, idx: int) -> str:
    """Background colour for a span column (fixed for OneStop, palette otherwise)."""
    if col in _KNOWN_SPAN_BG:
        return _KNOWN_SPAN_BG[col]
    return _SPAN_BG_PALETTE[idx % len(_SPAN_BG_PALETTE)]


def _ordered_words(trial_words: pd.DataFrame) -> pd.DataFrame:
    """Return trial_words sorted into reading order."""
    for col in ("word_id", "IA_ID"):
        if col in trial_words.columns:
            return trial_words.sort_values(col)
    return trial_words


def _render_paragraph_with_spans(
    trial_words: pd.DataFrame, span_bg: dict | None = None
) -> None:
    """Render the stimulus text with each detected span column highlighted.

    ``span_bg`` maps a per-word boolean span column → its highlight background
    (e.g. ``is_in_aspan`` → pink). When omitted, span columns are auto-detected.
    Falls back to plain text when no span columns are present, so it works on any
    dataset, not just OneStop."""
    if "text" not in trial_words.columns or trial_words.empty:
        return
    ordered = _ordered_words(trial_words)
    if span_bg is None:
        cols = _detect_span_columns(ordered)
        span_bg = {c: _span_bg_for(c, i) for i, c in enumerate(cols)}
    # Even with no span the text goes through the escaped HTML path: `st.write`
    # would read a word as Markdown.
    active = [c for c in span_bg if c in ordered.columns]
    texts = ordered["text"].fillna("").astype(str).tolist()
    masks = {c: _flag_mask(ordered[c]).tolist() for c in active}
    parts: list[str] = []
    for i, raw_word in enumerate(texts):
        word = html.escape(raw_word)
        bg = ""
        for col in active:  # first matching span wins (known spans listed first)
            if masks[col][i]:
                bg = span_bg[col]
                break
        if bg:
            parts.append(
                f'<span style="background-color:{bg};color:{_HIGHLIGHT_TEXT_COLOR};'
                f'padding:0 2px;border-radius:2px;">{word}</span>'
            )
        else:
            parts.append(word)
    html_body = " ".join(parts)
    st.markdown(
        f'<div style="line-height:1.6;">{html_body}</div>',
        unsafe_allow_html=True,
    )


def _span_text(trial_words: pd.DataFrame, mask_col: str) -> str:
    """Return the joined text of words where mask_col is True."""
    if mask_col not in trial_words.columns or "text" not in trial_words.columns:
        return ""
    ordered = _ordered_words(trial_words)
    mask = _flag_mask(ordered[mask_col])
    return " ".join(ordered.loc[mask, "text"].fillna("").astype(str).tolist())


def _first_str(df: pd.DataFrame, col: str) -> str | None:
    """First non-null value of ``col`` as a string, or None."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            return str(vals.iloc[0])
    return None


def _reading_stimulus_image(
    words: pd.DataFrame, fixations: pd.DataFrame, source: str | None = None
) -> tuple[str, tuple[int, int], tuple[float, float]] | None:
    """One reading's own stimulus page: ``(path, size, origin)``, or ``None``.

    `plots.reading_stimulus_image` — the resolver the headless
    ``show_stimulus_image`` uses too — vetted by `_servable_image_path`.
    ``source`` names the dataset the rows come from (``None``: the active one).
    """
    return reading_stimulus_image(
        words, fixations, allow=lambda path: _servable_image_path(path, source)
    )


def _servable_image_path(path: str | None, source: str | None = None) -> str | None:
    """``path`` if the server may read it into a figure, else ``None``.

    The stimulus layer reads the file off the *server's* disk and sends it to the
    browser as a data URI. On a local run that is the user's own disk, so any
    path goes. With local file access off (``SCANPATH_LOCAL_FS=0``, a shared
    deployment) an **uploaded** dataset's ``image_path`` is only a column someone
    typed — the image-folder step that fills it legitimately needs local access —
    so honouring it would let an upload read any PNG on the server. Paths the app
    resolved itself (the bundled demo, a server-side corpus) are unaffected.
    ``source`` is the dataset the path came from (``None``: the active one) —
    a comparison's B can come from another.
    """
    if not path:
        return None
    from scanpath_studio.app import local_filesystem_enabled

    if local_filesystem_enabled():
        return path
    from scanpath_studio.constants import UPLOAD_CHOICE

    if source is None:
        source = st.session_state.get("data_source_choice")
    if source == UPLOAD_CHOICE or source in (st.session_state.get("_datasets") or {}):
        return None
    return path


def _first_bool(df: pd.DataFrame, col: str) -> bool | None:
    """First non-null value of ``col`` as a bool, or None when absent, empty or
    not a true/false spelling (:func:`data.coerce_bool_or_na` — ``"False"`` is
    false)."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            flag = coerce_bool_or_na(vals.iloc[:1]).iloc[0]
            return None if pd.isna(flag) else bool(flag)
    return None


def _span_fixated_note(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame | None,
    mask_col: str,
) -> str:
    """Inline HTML note: was the span fixated, and for how long?

    Counts fixations falling inside any of the span's word boxes — a quick
    "did the reader actually look at the answer?" check tying the scanpath to
    comprehension. Returns "" when fixations or the span column are absent."""
    if (
        trial_fixations is None
        or trial_fixations.empty
        or mask_col not in trial_words.columns
    ):
        return ""
    span_words = trial_words[_flag_mask(trial_words[mask_col])]
    if span_words.empty:
        return ""
    from scanpath_studio.measures import fixation_in_text_mask

    mask = fixation_in_text_mask(trial_fixations, span_words)
    n = int(mask.sum())
    if n == 0:
        return ' <span style="color:#dc3545;">— not fixated</span>'
    dwell = float(pd.to_numeric(trial_fixations.loc[mask, "duration_ms"]).sum())
    fixed = plural(n, "fixation")
    return f' <span style="color:#198754;">— {fixed}, {dwell:.0f} ms</span>'


def _render_paragraph_panel(
    trial_words: pd.DataFrame,
    *,
    trial_fixations: pd.DataFrame | None = None,
    expanded: bool = True,
    bare: bool = False,
) -> None:
    """Render the stimulus-text + questions panel, generically.

    Detects the dataset's text-span columns (any boolean per-word column whose
    name reads as a span/highlight) and question/answer columns (any trial-level
    column whose name reads as question/answer/correct), so it works on any
    corpus — not just OneStop. Known OneStop columns keep their friendly labels
    and span colours. Each span is annotated
    with whether it was fixated when ``trial_fixations`` is given. Skips silently
    when no word text is available. ``bare=True`` drops the expander wrapper so
    the panel can sit directly inside a subtab."""
    if "text" not in trial_words.columns or trial_words.empty:
        if bare:
            # The subtab is on screen, so an empty body reads as broken.
            # The stimulus comes from the Words table — a raw-gaze-only or a
            # fixations-only trial has none.
            st.caption(
                f"{ICONS['info']} No stimulus text for this trial. The text comes "
                "from the Words table, which has no rows for this trial."
            )
        return
    # The name-hint detection supplies the defaults; the ⚙️ Fields popover
    # is what lets a corpus whose columns are named differently use the panel.
    span_cols, qa_cols, span_options, qa_options = _stimulus_fields(trial_words)
    span_bg = {c: _span_bg_for(c, i) for i, c in enumerate(span_cols)}

    container = (
        st.container() if bare else st.expander("Stimulus & context", expanded=expanded)
    )
    with container:
        text_col, picker_col = st.columns([9, 1.4], vertical_alignment="top")
        _render_stimulus_field_picker(picker_col, span_options, qa_options)
        with text_col:
            _render_paragraph_with_spans(trial_words, span_bg)

        # Breathing room between the stimulus text and the question block (generic
        # Q&A fields and/or MultiplEYE's structured comprehension questions).
        has_comprehension = bool(_first_str(trial_words, "comprehension_questions"))
        if qa_cols or has_comprehension:
            st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

        # MultiplEYE structured comprehension questions (target + distractors).
        _render_comprehension_questions(trial_words)

        # Trial context fields, generically. Keep OneStop's combined
        # "selected X · ✓ correct" answer line when both columns are present.
        # Every value goes in as literal text (`_literal`); only the labels,
        # marks and layout around it are the app's own markup. Every line goes
        # into ONE block — one element per line draws the lines on top of each
        # other.
        lines: list[str] = []
        question_cols = [c for c in qa_cols if "question" in c.lower()]
        for col in question_cols:
            val = _first_str(trial_words, col)
            if val:
                lines.append(f"{_field_label_html(col)} {_literal(val)}")

        rendered = set(question_cols)
        if "selected_answer" in qa_cols and "is_correct" in qa_cols:
            answer_val = _first_str(trial_words, "selected_answer")
            correct = _first_bool(trial_words, "is_correct")
            if answer_val or correct is not None:
                bits = []
                if answer_val:
                    bits.append(f"selected <b>{_literal(answer_val)}</b>")
                if correct is not None:
                    bits.append(_answer_mark(correct, "✓ correct", "✗ incorrect"))
                lines.append("<b>Answer:</b> " + " · ".join(bits))
            rendered.update({"selected_answer", "is_correct"})

        # Any remaining detected answer/correct columns, rendered generically.
        for col in qa_cols:
            if col in rendered:
                continue
            label = f"{_field_label_html(col)} "
            bval = _first_bool(trial_words, col) if "correct" in col.lower() else None
            if bval is not None:
                lines.append(label + _answer_mark(bval, "✓ yes", "✗ no"))
            else:
                val = _first_str(trial_words, col)
                if val:
                    lines.append(label + _literal(val))

        # Each highlighted span's text + (optional) fixation note.
        for col in span_cols:
            span_str = _span_text(trial_words, col)
            if not span_str:
                continue
            note = _span_fixated_note(trial_words, trial_fixations, col)
            lines.append(_span_summary_html(col, span_str, span_bg[col], note))
        if lines:
            st.markdown(_context_block_html(lines), unsafe_allow_html=True)


def _span_summary_html(col: str, span_str: str, bg: str, note: str) -> str:
    """Markup for one "<span label>: <span text>" line in the stimulus panel.

    Split out of ``_render_paragraph_panel`` so the escaping is testable without
    a Streamlit runtime. Both data-derived values — the column name and the
    stimulus text joined out of the words table — are HTML-escaped: this
    goes through ``unsafe_allow_html=True`` and Streamlit's markdown path runs
    no sanitizer, so a corpus containing markup would otherwise inject it into
    the page. ``note`` is tool-generated markup and ``bg`` comes from the fixed
    ``_SPAN_BG_PALETTE``, so both stay raw.
    """
    return (
        f'<span style="background-color:{bg};'
        f'color:{_HIGHLIGHT_TEXT_COLOR};padding:0 4px;border-radius:2px;">'
        f"{_field_label_html(col)}</span> "
        f"{html.escape(span_str)}{note}"
    )


def _in_text_fixation_value(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> str | None:
    """Concise "in / total" count of fixations that landed inside a word box.

    A compact value for the trial summary table. Returns None when there's
    nothing to count."""
    if trial_words.empty or trial_fixations.empty:
        return None
    from scanpath_studio.measures import fixation_in_text_mask

    mask = fixation_in_text_mask(trial_fixations, trial_words)
    n_total = len(mask)
    if n_total == 0:
        return None
    n_in = int(mask.sum())
    return f"{n_in} / {n_total}"


def _raw_gaze_missing_note(
    shown: bool,
    *,
    trial_has_raw_gaze: bool,
    comparing: bool = False,
    compare_has_raw_gaze: bool = False,
    screen: bool = False,
) -> str:
    """The warning for a 🔵 Raw gaze switch with nothing to draw, or ``""``.

    A comparison draws each reading's samples, so it names the reading
    that has none — and says nothing when both have some.

    Outside Compare it says the samples are missing *here* — the switch
    is live because the dataset has samples, on other trials or screens — so
    the layer does not look broken. ``screen`` names a multipart trial's screen.
    """
    if not shown:
        return ""
    if not comparing:
        where = "screen" if screen else "trial"
        return "" if trial_has_raw_gaze else f"No raw-gaze samples on this {where}."
    if trial_has_raw_gaze and compare_has_raw_gaze:
        return ""
    if not (trial_has_raw_gaze or compare_has_raw_gaze):
        return "Raw gaze not available for either trial."
    return f"Raw gaze not available for scanpath {'B' if trial_has_raw_gaze else 'A'}."


def _no_fixations_note(
    *,
    trial_has_fixations: bool,
    trial_has_raw_gaze: bool,
    raw_gaze_shown: bool,
    animate_requested: bool,
    compare_requested: bool,
    drawable_samples: bool = True,
) -> str:
    """What a trial with no fixations shows, and what it cannot.

    Said above the plot, because the rail alone can only grey a control: a
    raw-gaze-only trial draws its samples as recorded and nothing else of the
    scanpath, and "nothing is detected from the samples" is the fact that
    explains every greyed control at once. ``""`` for a trial with fixations,
    and for a words-only trial that asked for neither mode (its figure is its
    text, and nothing is missing from it that the rail does not already say).
    """
    if trial_has_fixations:
        return ""
    modes = [
        name
        for name, on in (
            ("Animation", animate_requested),
            ("Compare", compare_requested),
        )
        if on
    ]
    resolved = (
        f" {' and '.join(f'**{m}**' for m in modes)} "
        f"{'draw' if len(modes) > 1 else 'draws'} fixations, so the static figure "
        "is shown instead."
        if modes
        else ""
    )
    if not trial_has_raw_gaze:
        return (
            f"{ICONS['info']} This trial has no fixations.{resolved}" if modes else ""
        )
    shown = (
        "Its gaze samples are drawn as recorded."
        if raw_gaze_shown
        else f"Turn on {ICONS['raw_gaze']} **Raw gaze** to draw its gaze samples."
    )
    if not drawable_samples:
        shown = "None of its gaze samples have usable values on both selected axes."
    return (
        f"{ICONS['info']} **Raw gaze only.** There are no fixations in this "
        f"trial. {shown} "
        "Fixations, saccades, the replay and Compare need fixations, and "
        "Scanpath Studio does not detect fixations from gaze samples."
        f"{resolved}"
    )


def _full_screen_note(viz_settings: dict, canvas_width, canvas_height) -> str:
    """The caption under a figure *cropped* to its data, else ``""``: what is
    shown is part of the screen, and where to see all of it."""
    if viz_settings.get("fit_to_monitor", True):
        return ""
    try:
        width, height = int(canvas_width), int(canvas_height)
    except (TypeError, ValueError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    return (
        f"Cropped to the data. The full screen is {width}×{height}; turn off "
        "**Figure → Screen & framing → Crop to data** to show all of it."
    )


def _trial_duration_ms(trial_fixations: pd.DataFrame) -> float | None:
    """First fixation onset to last fixation offset, in ms — the span the
    replay's *Trial time* runs over.

    ``None`` unless the data recorded the onsets — the replay's own rule,
    `measures.fixation_clock`. A table with no onset column (PoTeC) is numbered
    0, 1, 2, … by normalization, and that span read as milliseconds would be a
    "trial" of a second beside a minute of fixations; laying the fixations end
    to end instead would only repeat *Total fixation time*."""
    from scanpath_studio.measures import fixation_clock

    if not {"timestamp_ms", "duration_ms"} <= set(trial_fixations.columns):
        return None
    ordered = trial_fixations.sort_values("timestamp_ms", kind="stable")
    onsets, recorded = fixation_clock(ordered)
    if not recorded:
        return None
    duration = pd.to_numeric(ordered["duration_ms"], errors="coerce").fillna(0)
    return float((onsets + duration.to_numpy(dtype=float)).max())


def _summary_rows(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    trial_raw_gaze: pd.DataFrame | None = None,
    *,
    gaze_samples: int | None = None,
) -> list[dict]:
    """Field/Value rows summarising a trial — totals + in-text fixation count.

    ``gaze_samples`` is the sample count when the caller has the count but not
    the samples — Compare's B, whose count is cached; it stands in for
    ``len(trial_raw_gaze)``.

    Part of the metadata table, so a trial's headline numbers live in one place.

    **A row is written only for a number that was measured** — otherwise a
    raw-gaze-only trial would read "Total fixation time (s) = 0.0 · Number of
    fixations = 0", two measured zeros for two things nobody measured, and a
    words-only one the same.
    Reading time needs a recorded dwell time or fixations to sum, the word count
    a words table, the fixation count fixations; a row with nothing behind it is
    left out, and the chip table skips a field with no row. The sample count is
    a raw-gaze trial's own headline number, so it is a row whenever the trial
    has samples."""
    stats = compute_trial_stats(trial_words, trial_fixations)
    has_words = trial_words is not None and not trial_words.empty
    has_fixations = trial_fixations is not None and not trial_fixations.empty
    recorded_dwell = (
        has_words
        and "trial_dwell_time_ms" in trial_words.columns
        and bool(
            pd.to_numeric(trial_words["trial_dwell_time_ms"], errors="coerce")
            .notna()
            .any()
        )
    )
    rows = []
    if recorded_dwell or has_fixations:
        rows.append(
            {
                "Field": SUMMARY_CHIP_FIELDS["@reading_time_s"],
                "Value": f"{stats['total_reading_time_s']:.1f}",
            }
        )
    duration_ms = _trial_duration_ms(trial_fixations) if has_fixations else None
    if duration_ms is not None:
        rows.append(
            {
                "Field": SUMMARY_CHIP_FIELDS["@trial_duration_s"],
                "Value": f"{duration_ms / 1000:.1f}",
            }
        )
    if has_words:
        rows.append({"Field": "Number of words", "Value": f"{stats['word_count']:,}"})
    if has_fixations:
        rows.append(
            {"Field": "Number of fixations", "Value": f"{stats['fixation_count']:,}"}
        )
    in_text = _in_text_fixation_value(trial_words, trial_fixations)
    if in_text is not None:
        rows.append({"Field": "Fixations in word boxes", "Value": in_text})
    if gaze_samples is None and trial_raw_gaze is not None:
        gaze_samples = len(trial_raw_gaze)
    if gaze_samples:
        rows.append(
            {
                "Field": SUMMARY_CHIP_FIELDS["@gaze_sample_count"],
                "Value": f"{gaze_samples:,}",
            }
        )
    return rows


# Row-wise palette for the trial-metadata table. Picked light so the text
# stays readable. `is_correct` keeps the row background neutral but tints
# the value text green/red — a background there would clash with the
# ✓ / ✗ color.
_DIFFICULTY_COLORS = {"ele": "#d4edda", "adv": "#fff3cd"}
_REPEAT_COLOR = "#cfe2ff"  # light blue — clearly distinct from the Ele/Adv tints
_PREVIEW_COLOR = "#DBEAFE"  # light blue — Hunting/preview trials


def _build_studio_config(
    *,
    selected_participant: str,
    selected_trial: str,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    figure_settings: dict,
    viz_settings: dict,
    base_font_size: int,
    trial_raw_gaze: pd.DataFrame,
    font_family: str,
    data_source: str | None,
    app_version: str,
    exported_at: str,
    compare_styles: list | None = None,
) -> dict:
    """Build Share's settings file using the bundle's serializer."""
    from scanpath_studio.app import active_setup_snapshot
    from scanpath_studio.plot_config import build_plot_config

    snapshot = active_setup_snapshot()
    return build_plot_config(
        selected_participant=selected_participant,
        selected_trial=selected_trial,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        x_field=x_field,
        y_field=y_field,
        figure_settings=figure_settings,
        viz_settings=viz_settings,
        base_font_size=base_font_size,
        trial_raw_gaze=trial_raw_gaze,
        font_family=font_family,
        data_source=_dataset_label(data_source) if data_source else None,
        app_version=app_version,
        exported_at=exported_at,
        compare_styles=compare_styles,
        state=st.session_state,
        setup_provenance=(
            {
                "provenance": {g: str(p) for g, p in snapshot.provenance.items()},
                "viewing_distance_provenance": snapshot.viewing_distance_provenance,
            }
            if snapshot is not None
            else None
        ),
        print_size=_print_size_setting(),
    )


def _current_figure_config(
    selected_participant: str,
    selected_trial: str,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    figure_settings: dict,
    viz_settings: dict,
    base_font_size: int,
    trial_raw_gaze: pd.DataFrame,
    *,
    font_family: str,
) -> dict:
    """The current figure and both readers' styles for Share and manuscript proofs."""
    from datetime import datetime

    from scanpath_studio import __version__

    # Per-scanpath comparison styling (cmp{idx}_* widget keys, seeded by
    # controls._seed_compare_styles). Save the RAW values so they restore 1:1 —
    # the saccade style stays the friendly label ("Solid"), not the resolved dash.
    compare_styles = [
        {
            "fix_color": st.session_state.get(f"cmp{idx}_fix_color"),
            "saccade_color": st.session_state.get(f"cmp{idx}_saccade_color"),
            "saccade_style": st.session_state.get(f"cmp{idx}_saccade_style", "Solid"),
            "saccade_width": float(
                st.session_state.get(f"cmp{idx}_saccade_width", DEFAULT_SACCADE_WIDTH)
            ),
            "marker_size_range": [
                int(s)
                for s in st.session_state.get(
                    f"cmp{idx}_marker_size_range", DEFAULT_MARKER_SIZE_RANGE
                )
            ],
            "hollow": bool(st.session_state.get(f"cmp{idx}_hollow", False)),
            "opacity": float(st.session_state.get(f"cmp{idx}_opacity", 1.0)),
            # The A/B legend label override ("" = the auto label).
            "label_pattern": st.session_state.get(f"cmp{idx}_label_pattern") or "",
            # The word-box outline override ("" = the scanpath's colour).
            "box_color": st.session_state.get(f"cmp{idx}_box_color") or "",
            # The word-box fill override ("" = the figure's fill).
            "box_fill_color": st.session_state.get(f"cmp{idx}_box_fill_color") or "",
            # The word-box opacities (None = the figure's).
            "box_line_opacity": st.session_state.get(f"cmp{idx}_box_line_opacity"),
            "box_fill_opacity": st.session_state.get(f"cmp{idx}_box_fill_opacity"),
            # The raw-gaze colour override ("" = the scanpath's colour).
            "raw_gaze_color": st.session_state.get(f"cmp{idx}_raw_gaze_color") or "",
            # The heatmap colour-scale override ("" = the figure's).
            "heatmap_colorscale": st.session_state.get(f"cmp{idx}_heatmap_colorscale")
            or "",
        }
        for idx in range(2)
    ]
    # B's own filters ride its entry (A's are the ordinary ones). Modes
    # and thresholds only — B draws a Highlight with A's marker and colour.
    b_filters = compare_b_filters()
    compare_styles[1]["fixation_flags"] = {
        cat: {k: v for k, v in spec.items() if k in ("mode", "threshold_ms")}
        for cat, spec in b_filters["fixation_flags"].items()
    }
    compare_styles[1]["saccade_classes"] = b_filters["saccade_classes"]
    return _build_studio_config(
        selected_participant=selected_participant,
        selected_trial=selected_trial,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        x_field=x_field,
        y_field=y_field,
        figure_settings=figure_settings,
        viz_settings=viz_settings,
        base_font_size=base_font_size,
        trial_raw_gaze=trial_raw_gaze,
        font_family=font_family,
        data_source=st.session_state.get("data_source_choice"),
        app_version=__version__,
        exported_at=datetime.now().isoformat(timespec="seconds"),
        compare_styles=compare_styles,
    )


def render_settings_file(
    selected_participant: str,
    selected_trial: str,
    canvas_width: int,
    canvas_height: int,
    x_field: str,
    y_field: str,
    figure_settings: dict,
    viz_settings: dict,
    base_font_size: int,
    trial_raw_gaze: pd.DataFrame,
    *,
    font_family: str,
) -> None:
    """Download the current figure settings and restore a previously saved file."""
    plot_config = _current_figure_config(
        selected_participant,
        selected_trial,
        canvas_width,
        canvas_height,
        x_field,
        y_field,
        figure_settings,
        viz_settings,
        base_font_size,
        trial_raw_gaze,
        font_family=font_family,
    )
    # The file's boundary, as `_build_studio_config` draws it — the
    # Corpus Analysis tutorial explains the excluded choices at more length.
    st.caption(
        "Includes the figure settings, recording setup and trial selection. "
        "Leaves out trial filters, cohort definitions, annotations, the column "
        "mapping and the data."
    )
    st.download_button(
        "Download settings",
        icon=ICONS["download"],
        data=json.dumps(plot_config, indent=2),
        file_name="scanpath_studio_settings.json",
        mime="application/json",
        key="plot_config_download",
    )
    st.file_uploader(
        "Restore settings",
        type=["json"],
        key="plot_config_upload",
        help="Re-apply a settings file. Settings that do not match the loaded "
        "data are skipped and listed here.",
        max_upload_size=upload_limit_mb(),
    )
    skipped = st.session_state.get("_plot_config_skipped")
    if skipped:
        st.caption(
            f"{ICONS['warning']} Not applied (no match in the current data): "
            + ", ".join(skipped)
            + "."
        )


#: Separator between a dataset name and a participant id in the *throwaway*
#: compare frames. Chosen to be visible in a label and absent from real ids;
#: it never reaches an annotation key, an export slug or a deep link.
#: Defined in `utils.py`; aliased here for this module's call sites.
_COMPARE_DATASET_SEP = COMPARE_DATASET_SEP

#: Metric names that are safe across any two corpora: canonical
#: fixation columns every normalized frame carries, plus the synthetic choices
#: that are not columns at all (``line``, ``counts``, and the uniform colour).
_CROSS_DATASET_SAFE_METRICS = frozenset(
    {
        "line",
        "counts",
        "duration_ms",
        "order_in_trial",
        "timestamp_ms",
        UNIFORM_COLOR_FIELD,
    }
)


def _compare_setups(
    compare_meta: dict | None,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    canvas_width: int,
    canvas_height: int,
) -> tuple[bool, str]:
    """May A and B be drawn in one coordinate space? Plus the reason.

    A *same-dataset* pair is ``(True, "")`` while B's screen (``compare_meta``'s
    ``"canvas"``, its selected screen's own canvas) matches the one A is drawn
    on; one dataset can hold screens of different sizes, so two that differ
    are refused with the same reason as two datasets' would be. Its
    provenance is one corpus's either way, so there is no caveat to add.

    For a cross-dataset pair both snapshots go through
    `compare_source.snapshot_for`, deliberately: A's live ``global_*`` canvas
    keys describe whichever dataset is active, so resolving A one way and B
    another would report different provenance for the *same* corpus depending on
    which side of the comparison it landed on — and the predicate gates on
    provenance, so the overlay would be legal one way round and illegal the
    other.

    A's canvas is then overridden with the one actually being rendered: the
    rail's 🖥️ Screen & geometry panel can override it, and the gate has to test
    the figure that is drawn, not the one the corpus declares.
    """
    from scanpath_studio.experimental_setup import SetupSnapshot, setups_comparable

    if not compare_meta:
        return True, ""
    if not compare_meta.get("dataset"):
        canvas_b = compare_meta.get("canvas")
        canvas_a = (int(canvas_width), int(canvas_height))
        if canvas_b is None or tuple(canvas_b) == canvas_a:
            return True, ""
        return setups_comparable(
            SetupSnapshot(canvas_width=canvas_a[0], canvas_height=canvas_a[1]),
            SetupSnapshot(
                canvas_width=int(canvas_b[0]), canvas_height=int(canvas_b[1])
            ),
        )
    setup_b = compare_meta.get("setup")
    if setup_b is None:
        # Why, not what happens next — like `setups_comparable`'s reason.
        return False, (
            "Scanpath B's dataset doesn't record its screen, so there's no way "
            "to tell whether the two trials share screen coordinates."
        )
    active = str(st.session_state.get("data_source_choice") or "")
    setup_a = replace(
        snapshot_for(active, words, fixations),
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
    )
    return setups_comparable(setup_a, setup_b)


# These four live in `utils.py`: the app, `api.compare_scanpaths` and
# `cli.render --compare-*` all build cross-dataset comparison frames, and the
# participant-namespacing rule must have exactly one definition. The private
# names are aliases for this module's call sites and its tests.
_qualify_for_compare = qualify_for_compare
_qualified_participant = qualified_participant
_unqualify_for_export = unqualify_for_export
_align_compare_columns = align_compare_columns


def _build_compare_meta(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    selected_participant: str,
    selected_trial: str,
    compare_participant: str | None,
    compare_trial: str | None,
    compare_screen: str | None = None,
    source: SecondaryDataset | None = None,
    primary_dataset: str | None = None,
    raw_gaze: pd.DataFrame | None = None,
    include_raw_gaze: bool = True,
    dataset_canvas: tuple[int, int] | None = None,
    screen_canvas: tuple[int, int] | None = None,
    elapsed_axis: bool = False,
) -> dict | None:
    """Build the second trial's words/fixations + column labels for the
    Compare's A/B chip table, or None when no comparison is active.

    ``"canvas"`` in the result is B's own screen: the selected screen's canvas
    when B's rows carry one, else its dataset's — ``source.setup`` for a second
    dataset, ``dataset_canvas`` (A's dataset canvas, before any per-screen
    override) for this one. One dataset can hold screens of different sizes, so
    dataset identity alone never makes B's screen A's. A second dataset's
    ``"setup"`` carries the same canvas.

    ``primary_dataset`` is A's own corpus name: a cross-dataset
    comparison names *both* sides, since naming only B
    reads as though A had no corpus at all.

    ``source`` makes B come out of a *different* dataset: the trial is
    extracted from that source's frames, namespaced by `_qualify_for_compare`,
    and the returned dict carries the qualified participant plus B's own
    ``dataset`` / ``text_id`` / ``setup`` — the last three because everything
    downstream would otherwise look them up in **A's** combos and geometry.

    ``compare_screen`` is **B's own** chosen screen id — from its own
    navigator, scoped to its own multipart trial — never A's, so it means the
    same thing whatever ``source`` is. A cross-dataset multipart B is cut to
    one screen too, never extracted whole with every one of its screens
    concatenated into one frame, since each is its own coordinate space.

    ``raw_gaze`` is A's dataset's samples; B's are cut from it, or from
    ``source.raw_gaze`` when B is foreign, to the same trial and screen, and
    returned under ``"raw_gaze"`` (empty when B has none) keyed as B's figure
    frames are. ``include_raw_gaze=False`` skips them, ``source``'s included.
    """
    if compare_participant is None or compare_trial is None:
        return None
    if source is not None:
        words_filtered, fixations_filtered = source.words, source.fixations
        raw_gaze = source.raw_gaze if include_raw_gaze else None
    compare_raw = pd.DataFrame()
    if raw_gaze is not None and not raw_gaze.empty:
        compare_raw = extract_trial(raw_gaze, compare_participant, compare_trial)
        if compare_screen is not None:
            compare_raw = (
                extract_part(
                    compare_raw, compare_participant, compare_trial, compare_screen
                )
                if SCREEN_ID in compare_raw.columns
                # No screen identity: hidden rather than concatenated across
                # screens, as A's are.
                else pd.DataFrame()
            )
    compare_words = extract_trial(words_filtered, compare_participant, compare_trial)
    compare_fix = extract_trial(fixations_filtered, compare_participant, compare_trial)
    compare_fix = with_onset_provenance(compare_fix)
    if elapsed_axis:
        compare_fix = chart_axes.with_origin(compare_fix)
    if compare_screen is not None:
        if not compare_words.empty:
            if SCREEN_ID not in compare_words.columns:
                return None
            compare_words = extract_part(
                compare_words, compare_participant, compare_trial, compare_screen
            )
        if not compare_fix.empty:
            if SCREEN_ID not in compare_fix.columns:
                return None
            compare_fix = extract_part(
                compare_fix, compare_participant, compare_trial, compare_screen
            )
        if compare_words.empty and compare_fix.empty:
            return None
    # Short, distinct column headers: participant ids when comparing different
    # participants (the common same-text case), else the trial ids — the long
    # ids otherwise overflow the narrow panel. Across datasets the two readers
    # are never the same person, so the dataset name is the distinguishing half.
    #
    # Across datasets that qualifier goes on **both** labels: B's name comes
    # free with the *Compare with* pick while A's source is implicit, so
    # labelling only B would read as though one panel had a corpus and the
    # other did not. Same-dataset comparisons — the common case — stay bare
    # on both sides: repeating one corpus name twice says nothing.
    if source is not None:
        label_primary = str(selected_participant)
        if primary_dataset:
            label_primary = (
                f"{primary_dataset}{_COMPARE_DATASET_SEP}{selected_participant}"
            )
        label_compare = (
            f"{_dataset_label(source.name)}{_COMPARE_DATASET_SEP}{compare_participant}"
        )
    elif str(selected_participant) != str(compare_participant):
        label_primary = str(selected_participant)
        label_compare = str(compare_participant)
    else:
        label_primary = str(selected_trial)
        label_compare = str(compare_trial)
    # B's screen, read before the participant ids are namespaced (they don't
    # touch the canvas columns, but this is B's data as its corpus has it).
    setup_b = source.setup if source is not None else None
    canvas_b = (
        screen_canvas_size(compare_words)
        or screen_canvas_size(compare_fix)
        or screen_canvas_size(compare_raw)
        or screen_canvas
    )
    if canvas_b is not None and setup_b is not None:
        setup_b = replace(setup_b, canvas_width=canvas_b[0], canvas_height=canvas_b[1])
    if canvas_b is None:
        if setup_b is not None:
            canvas_b = setup_b.canvas
        elif source is None and dataset_canvas is not None:
            canvas_b = (int(dataset_canvas[0]), int(dataset_canvas[1]))
    figure_participant = compare_participant
    if source is not None:
        compare_words = _qualify_for_compare(compare_words, source.name)
        compare_fix = _qualify_for_compare(compare_fix, source.name)
        compare_raw = _qualify_for_compare(compare_raw, source.name)
        figure_participant = _qualified_participant(source.name, compare_participant)
    return {
        "words": compare_words,
        "fixations": compare_fix,
        "raw_gaze": compare_raw,
        "label_primary": label_primary,
        "label_compare": label_compare,
        # The id to slice the *merged* compare frames by — namespaced when B is
        # foreign. `raw_participant` is the real one, for export slugs, share
        # links and anything else that must name the reader as the corpus does.
        "participant": figure_participant,
        "raw_participant": compare_participant,
        "trial": compare_trial,
        "dataset": source.name if source is not None else None,
        "setup": setup_b,
        "canvas": canvas_b,
        "text_id": _first_text_id(compare_words) if source is not None else None,
    }


def _first_text_id(words: pd.DataFrame) -> str | None:
    """The text id of a single-trial frame, for a trial A's combos can't answer for."""
    for col in ("unique_text_id", "text_id"):
        if col in words.columns and not words.empty:
            value = words[col].iloc[0]
            if pd.notna(value):
                return str(value)
    return None


# Playback-speed options shared by the animation control.
_ANIM_SPEED_OPTIONS = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0]
_ANIM_SPEED_LABELS = [
    "×0.25",
    "×0.5",
    "×1",
    "×1.5",
    "×2",
    "×2.5",
    "×3",
    "×4",
    "×6",
    "×8",
]
# Default playback speed — real time, so the replay a user first sees runs at
# the pace the reading was actually recorded at, and matches what the headless
# API / CLI produce by default (`api.animate_scanpath(playback_speed=1.0)`).
# The Playback popover's speed slider goes ×0.25 – ×8 from here.
_ANIM_DEFAULT_SPEED = 1.0
_ANIM_QUALITY_PRESETS = {
    # Fast enough for trial browsing and compact GIF/MP4 drafts.
    "Coarse": (300, 120),
    # The grid a fresh session, the API and `render` start on
    # (`global_anim_grid_step_ms` / `global_anim_max_frames`'s defaults), named
    # so a first look at the menu does not find *Custom* already picked.
    "Standard": (100, 360),
    # High-fidelity review/export: noticeably smoother than the 100 ms grid.
    "Fine": (40, 900),
}


def _render_anim_info(
    timing_host,
    frames_host,
    trial_fixations: pd.DataFrame,
    fixations_b: pd.DataFrame | None,
    selected_participant: str,
    selected_trial: str,
    compare_participant: str | None,
    compare_trial: str | None,
    playback_speed: float,
    grid_step_ms: float | None = None,
    max_frames: int | None = None,
) -> float:
    """Write the replay's timing and frame count into the Animate popover.

    The duration sits beside the playback controls. The frame count and
    effective interval follow the smoothness preset.
    Returns the playback duration in ms."""
    dual = fixations_b is not None and not fixations_b.empty
    summary = animation_timeline_summary(
        [trial_fixations] + ([fixations_b] if dual else []),
        playback_speed,
        grid_step_ms=grid_step_ms,
        max_frames=max_frames,
    )
    playback_ms = summary["playback_ms"]
    if dual:
        span = _replay_span_text(
            {
                "A": animation_timeline_summary([trial_fixations], 1.0),
                "B": animation_timeline_summary([fixations_b], 1.0),
            }
        )
    else:
        span = _replay_span_text({"": summary})
    timing_host.caption(f"{span} · Playback {playback_ms / 1000:.1f} s")
    # The different-texts caveat is under the figure
    # (`_different_texts_note`), where it is actually read.
    if dual and (compare_participant, compare_trial) == (
        selected_participant,
        selected_trial,
    ):
        timing_host.caption(
            f"{ICONS['warning']} Scanpath B is the same trial as scanpath A."
        )
    # State what the chosen grid actually produced — otherwise the frame cap
    # coarsening the step is invisible and the setting feels arbitrary — and
    # say which control decided it, in the controls' own numbers, so the
    # result never reads as contradicting them.
    grid = (
        f"**{summary['n_frames']}** frames, one every "
        f"{summary['step_ms']:.0f} ms of reading."
    )
    if summary["coarsened"]:
        grid += (
            f" The {summary['max_frames']}-frame limit widened the spacing "
            f"from {summary['requested_step_ms']:.0f} ms."
        )
    frames_host.caption(grid)
    return playback_ms


#: What a replay's span is called: the trial's duration only when the
#: data recorded the fixation onsets. Without them the replay lays the
#: fixations end to end, and that span is the summed fixation time — the chip
#: table's *Total fixation time* — not how long the trial took.
_REPLAY_SPAN_NAMES = {True: "Trial", False: "Fixation time"}
_NO_ONSETS_NOTE = "no onset times, so fixations play back to back"


def _replay_span_text(parts: dict[str, dict]) -> str:
    """The Animate popover's Duration row, before its playback time, from one
    `animation_timeline_summary` per scanpath keyed by its label — ``{"": s}``
    for one replay, ``{"A": a, "B": b}`` for a co-animation — each span named
    for what it measured."""
    recorded = {
        label: part["recorded_clock"] is not False for label, part in parts.items()
    }

    def span(label: str) -> str:
        return f"{parts[label]['reading_span_ms'] / 1000:.1f} s"

    if len(set(recorded.values())) > 1:
        # A mix (two datasets): each side's span under its own name.
        return " · ".join(
            f"**{label}** {_REPLAY_SPAN_NAMES[rec].lower()} {span(label)}"
            for label, rec in recorded.items()
        )
    rec = all(recorded.values())
    if list(parts) == [""]:
        text = f"{_REPLAY_SPAN_NAMES[rec]} {span('')}"
    else:
        text = f"{_REPLAY_SPAN_NAMES[rec]} " + " · ".join(
            f"**{label}** {span(label)}" for label in parts
        )
    return text if rec else f"{text} ({_NO_ONSETS_NOTE})"


def _apply_preprocessing_caption(fig, participant, trial) -> None:
    """Put the cleaning provenance on-screen, in exports, and in metadata."""
    _annotate_preprocessing(fig, _preprocessing_report_row(participant, trial))


def _preprocessing_report_row(participant, trial) -> dict | None:
    """This trial's preprocessing report, or ``None`` when there is none."""
    report = st.session_state.get("_preprocessing_report")
    if not isinstance(report, pd.DataFrame) or report.empty:
        return None
    row = report[
        (report["participant_id"].astype(str) == str(participant))
        & (report["trial_id"].astype(str) == str(trial))
    ]
    return None if row.empty else row.iloc[0].to_dict()


def _annotate_preprocessing(fig, item: dict | None) -> None:
    """Stamp one trial's cleaning report (`_preprocessing_report_row`) on ``fig``."""
    if item is None:
        return
    text = (
        f"Preprocessing · {int(item.get('n_excluded', 0))}/"
        f"{int(item.get('n_fixations_before', 0))} excluded "
        f"({float(item.get('excluded_pct', 0)):.1%}) · "
        f"{int(item.get('n_merged', 0))} merged"
    )
    fig.add_annotation(
        x=0,
        y=0,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="bottom",
        text=text,
        showarrow=False,
        font=dict(size=10, color="#5f6368"),
        bgcolor="rgba(255,255,255,0.82)",
        borderpad=3,
    )
    metadata = dict(fig.layout.meta or {})
    metadata["preprocessing"] = dict(item)
    fig.update_layout(meta=metadata)


def _combo_row(combos: pd.DataFrame, participant: str, trial: str) -> dict | None:
    """One trial's `combos` row as a plain dict, or None when the pool lacks it.

    The single definition of this mask: ~3.9 ms per scan of a full-OneStop-grain
    `combos` (~60k rows), on every widget toggle — including rail toggles that
    otherwise hit `_cached_scanpath_figure` and draw nothing new.

    Call it through `render_single_trial_tab`'s memoizing closure rather than
    directly, so the scan happens **once and only when something asks**: the
    consumer is the title/caption pattern, which is unset by default and whose
    renderer early-returns before ever looking at the row.
    """
    if combos is None or combos.empty:
        return None
    match = combos[
        (combos["participant_id"] == participant) & (combos["trial_id"] == trial)
    ]
    return match.iloc[0].to_dict() if not match.empty else None


def _rendered_title_caption(
    viz_settings: dict,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str,
    trial: str,
    combo_row: dict | Callable[[], dict | None] | None = None,
    dataset_name: str | None = None,
    compare_row: dict | None = None,
) -> tuple[str, str]:
    """The rail's title/caption **patterns rendered against this trial**.

    Split out of `_apply_title_caption` because the reproduction snippet has
    to pass the same literal strings to `api.plot_scanpath(title=…, caption=…)`
    that the figure on screen carries, and `plot_scanpath` takes literal text
    rather than the rail's `{trial_id}` pattern. Rendering it twice from the
    pattern could let the two drift apart."""
    title_pattern = viz_settings.get("title_pattern") or ""
    caption_pattern = viz_settings.get("caption_pattern") or ""
    if not title_pattern and not caption_pattern:
        return "", ""
    # `combo_row` may be a thunk, and it is resolved *here* — past the early
    # return above, which fires on the default (neither pattern set). The row
    # costs a mask over the whole `combos` frame; built eagerly as an argument
    # to this call it would cost that on every rerun, for a function that
    # usually returns before reading it.
    fields = _title_caption_fields(
        viz_settings,
        trial_words,
        trial_fixations,
        participant,
        trial,
        combo_row=combo_row,
        dataset_name=dataset_name,
        compare_row=compare_row,
    )
    return (
        render_pattern(title_pattern, fields) if title_pattern else "",
        render_pattern(caption_pattern, fields) if caption_pattern else "",
    )


def _title_caption_fields(
    viz_settings: dict,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str,
    trial: str,
    combo_row: dict | Callable[[], dict | None] | None = None,
    dataset_name: str | None = None,
    compare_row: dict | None = None,
) -> dict:
    """Every ``{field}`` the figure's title / caption can name, with this
    trial's values — what `_rendered_title_caption` renders with, and
    what the rail's *Available fields* list, validation and preview show."""
    if callable(combo_row):
        combo_row = combo_row()
    settings_summary_input = {
        "show_words": viz_settings.get("show_words", False),
        "show_word_labels": viz_settings.get("show_labels", True),
        "show_fixations": viz_settings.get("show_fix", True),
        "show_saccades": viz_settings.get("show_saccades", True),
        "show_heatmap": viz_settings.get("show_heatmap", False),
        "show_raw_gaze": viz_settings.get("caption_raw_gaze", False),
        "color_by": viz_settings.get("color_by"),
        "palette": viz_settings.get("palette"),
    }
    return pattern_fields(
        participant,
        trial,
        trial_words,
        trial_fixations,
        settings_summary_input,
        combo_row=combo_row,
        # The name the dataset picker shows. `_shown_dataset_name()` is the
        # session default so the three in-app render paths (static,
        # animation, compare) all get it without each remembering to.
        dataset_name=_shown_dataset_name() if dataset_name is None else dataset_name,
        compare_row=compare_row,
        # The dataset's own column names (`{CURRENT_FIX_DURATION}`) as well
        # as the canonical ones (`{duration_ms}`).
        column_names=active_all(st.session_state),
        # `{trials.font_size}` and the other tables' fields.
        metadata_rows=_metadata_mod.pattern_rows(
            participant, trial, (combo_row or {}).get("text_id")
        ),
    )


def _apply_title_caption(
    fig,
    viz_settings: dict,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str,
    trial: str,
    combo_row: dict | Callable[[], dict | None] | None = None,
    dataset_name: str | None = None,
    compare_row: dict | None = None,
) -> None:
    """Stamp the rail's title/caption pattern onto ``fig``.

    Reuses the export's pattern language (`export.pattern_fields`/`render_pattern`/
    `annotate_figure`) but against the trial on screen, so all three render
    paths — static, animation, compare — carry the same title/caption a bulk
    export would produce for this trial. The rail control is the single source
    of truth: `viz_settings["title_pattern"]`/`["caption_pattern"]` come from
    `controls._collect_viz_settings`, and the Export panel's bulk section reads
    the same two keys rather than keeping its own copy.

    Reads straight from `viz_settings` (`.get()`, tolerant of a minimal dict)
    rather than `_build_figure_settings`'s translated, all-keys-required shape
    — the `{settings}` placeholder only needs a handful of them, and the
    animation/comparison call sites don't otherwise need a full figure-builder
    settings dict at all."""
    title, caption = _rendered_title_caption(
        viz_settings,
        trial_words,
        trial_fixations,
        participant,
        trial,
        combo_row=combo_row,
        dataset_name=dataset_name,
        compare_row=compare_row,
    )
    # The snippet's `title=` / `caption=` must be *this* text, rendered
    # with this branch's frames / combo_row / compare_row — see
    # `_amend_snippet_title_caption`. Amended even when both are empty, so a
    # branch that renders to nothing clears the pre-published pair.
    _amend_snippet_title_caption(title, caption)
    if not title and not caption and not viz_settings.get("show_credit"):
        return
    annotate_figure(
        fig, title=title, caption=caption, **figure_text_style(viz_settings)
    )


#: The auto A/B legend label, written in the pattern language. Kept as
#: the pattern rather than the rendered text so the *same* string can be shown
#: as the Label A/B placeholder — an empty box and this pattern produce the same
#: label, which is exactly what the placeholder promises.
DEFAULT_COMPARE_LABEL_PATTERN = "{participant_id} · {trial_id}"


def _resolve_compare_label(
    idx: int,
    participant: str | None,
    trial: str | None,
    trial_words: pd.DataFrame | None,
    trial_fixations: pd.DataFrame | None,
    dataset_name: str = "",
) -> str:
    """The A/B legend label for compare scanpath ``idx`` (0 or 1).

    An explicit ``cmp{idx}_label_pattern`` (⚙️ Compare options popover,
    export-style pattern + preview) overrides the plain ``participant · trial``
    default; empty (the common case) falls through to it unchanged."""
    default = f"{participant} · {trial}"
    pattern = st.session_state.get(f"cmp{idx}_label_pattern") or ""
    if not pattern or not participant or not trial:
        return default
    fields = pattern_fields(
        participant,
        trial,
        trial_words if trial_words is not None else pd.DataFrame(),
        trial_fixations if trial_fixations is not None else pd.DataFrame(),
        {},
        # Side B can be a different corpus entirely, so the
        # label resolves `{dataset_name}` against *its own* side rather than
        # the picker's — an A/B legend that named the same dataset twice would
        # be worse than no name at all.
        dataset_name=dataset_name or _shown_dataset_name(),
    )
    return render_pattern(pattern, fields) or default


def _render_compare_reading_labels(
    host, readings: list[tuple], *, disabled: bool
) -> None:
    """Preview each label using the values from its own reading and dataset."""
    with host, _popover_rows("compare_labels"):
        st.caption(
            "These labels title the panels in split layouts and identify the readings "
            "in the comparison legend when it is shown."
        )
        available = {}
        for idx, (participant, trial, words, fixations, dataset_name) in enumerate(
            readings
        ):
            fields = (
                pattern_fields(
                    participant, trial, words, fixations, {}, dataset_name=dataset_name
                )
                if host.open
                and participant is not None
                and trial is not None
                and words is not None
                else {}
            )
            render_pattern_input(
                st,
                f"Label {'AB'[idx]}",
                f"cmp{idx}_label_pattern",
                fields,
                placeholder=DEFAULT_COMPARE_LABEL_PATTERN,
                help="Leave empty to use the automatic label.",
                label_left=True,
                disabled=disabled,
                preview=bool(fields),
            )
            available.update(fields)
        render_pattern_help(st, available)


def _shown_dataset_name(token: str | None = None) -> str:
    """``{dataset_name}`` in a figure: the name Select Dataset shows,
    not the stored token — a renamed or public dataset reads the same."""
    from scanpath_studio.app import _dataset_display_name

    return _dataset_display_name(token) if token else current_dataset_name()


def _compare_dataset_name(compare_meta: dict | None) -> str:
    """The dataset scanpath B is drawn from.

    B can come from a second corpus, and `compare_meta["dataset"]`
    carries its name when it does; a same-dataset comparison leaves it unset and
    both sides are the picker's current source.
    """
    return _shown_dataset_name((compare_meta or {}).get("dataset"))


def _cancel_animation(task_key: tuple) -> None:
    """Cancel on the animation card — back to the static plot."""
    progress.cancel(task_key)
    leave_animation()


#: The replay task this session's card was last opened for, held while
#: its build runs and dropped once the card's block completes. An ``_sps_*``
#: internal: never on the wire, never in the recovery cache.
ANIM_TASK_KEY = "_sps_anim_task"


def _animation_task_key(
    participant,
    trial,
    screen=None,
    *,
    compare: tuple | None = None,
    inputs: Hashable | None = None,
) -> tuple:
    """The replay's task key: what it is a replay *of* — its frames.

    Keyed by the session alone, a run that stepped to another trial mid-build
    would join the old build's task — two frame loops' counts interleaved on one
    card while the obsolete build ran on beside the new one at half the speed.
    A multipart replay covers one screen, so the screen is part of it (``None``
    for a trial with one); ``compare`` is B's ``(participant, trial, screen)``
    for a co-replay, and is passed only then — B steps through its own screens.
    ``inputs`` is the replay's input key (`_ReplayPlan.key`), so a
    setting that changes the frames — marker size, colours, saccades, the
    fixation flags or window, drift correction … — is another replay too,
    while the speed and autoplay, which the frames are built without, are not.
    """

    def _identity(who, what, where) -> tuple:
        return (str(who), str(what), None if where is None else str(where))

    key = ("anim", loading.session_id(), *_identity(participant, trial, screen))
    if compare is not None:
        key += _identity(*compare)
    if inputs is not None:
        key += (inputs,)
    return key


def _claim_animation_task(task_key: tuple) -> None:
    """Cancel the replay a run was building of other frames, then remember
    this one's.

    Another trial, screen or B, or a setting that changes the frames: that
    build is of a replay no longer wanted. The same key — nothing changed but
    the speed or autoplay, say — joins the build under way, which is exactly
    the one this run wants.
    """
    previous = st.session_state.get(ANIM_TASK_KEY)
    if previous is not None and tuple(previous) != task_key:
        progress.cancel(tuple(previous))
    st.session_state[ANIM_TASK_KEY] = task_key


def _abandon_animation_task() -> None:
    """This Scanpath run builds no replay: stop the one an earlier run left
    building — a static view selected mid-build, or
    a trial with nothing to animate — rather than let a replay of frames no
    longer wanted run on beside this run's figure. Show static plot cancels
    its build itself (`_cancel_animation`). A run on another view never gets
    here: a replay left building there lands in the cache for the way back."""
    previous = st.session_state.pop(ANIM_TASK_KEY, None)
    if previous is not None:
        progress.cancel(tuple(previous))


def _release_animation_task(task_key: tuple) -> None:
    """This run's replay is built: nothing of it is left to cancel.

    Only its own key is dropped — a later run may already have claimed another.
    """
    if st.session_state.get(ANIM_TASK_KEY) == task_key:
        st.session_state.pop(ANIM_TASK_KEY, None)


# The figure-wide marker and saccade look a co-animation never reads (each
# scanpath draws in its own style), at the builder's defaults.
_DUAL_UNREAD_STYLE = {
    field.name: field.default
    for field in dataclass_fields(FigureSettings)
    if field.name
    in {
        "fixation_color",
        "fixation_opacity",
        "hollow_fixations",
        "marker_size_range",
        "order_font_color",
        "saccade_color",
        "saccade_style",
        "saccade_width",
    }
}


def _replay_style(style: dict | None) -> dict | None:
    """A per-scanpath comparison style as the co-animation takes it: its look
    only, without the filters (`COMPARE_FILTER_STYLE_KEYS`) `_plan_replay`
    hands the replay another way, and without `box_color` / `box_fill_color` /
    the box opacities / `raw_gaze_color` / `heatmap_colorscale` — the replay
    draws one set of boxes
    in the figure's colours and no raw gaze or heatmap, so they would only split
    the cache key."""
    if not style:
        return None
    return {
        k: v
        for k, v in style.items()
        if k not in COMPARE_FILTER_STYLE_KEYS
        and k not in STATIC_COMPARISON_LAYER_STYLES
    }


@dataclass(frozen=True)
class _ReplayPlan:
    """What one replay is built from, worked out before its card opens.

    ``settings`` carries the real clock — speed and autoplay — for the player
    and the snippet; ``frame_settings`` is the same with the clock fixed,
    which with B's frames makes ``inputs``, and ``key`` is their
    fingerprint: the replay cache's key, and the part of the replay's task key
    (`_animation_task_key`'s ``inputs``) that names its frames.
    """

    settings: FigureSettings
    frame_settings: FigureSettings
    inputs: dict
    key: tuple


#: Design choices the replay's frames never read, at their defaults in
#: the frame key (`_plan_replay`).
_REPLAY_UNREAD_DESIGN = FigureSettings.defaults(
    (
        "heatmap_opacity",
        "heatmap_colorbar_thickness",
        "heatmap_colorbar_length",
        *TEXT_STYLE_FIELDS,
    )
)


def _plan_replay(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None,
    selected_participant: str,
    selected_trial: str,
    compare_participant: str | None,
    compare_trial: str | None,
    *,
    settings: FigureSettings,
    viz_settings: dict,
    playback_speed: float,
    drift_corrected: bool = False,
    dataset_name_b: str = "",
) -> _ReplayPlan:
    """The replay's `_ReplayPlan` — drawing nothing, so the call site can run it
    before the card opens: the replay's task is keyed by its frames.
    `_build_and_render_animation` builds from exactly this plan, so the key the
    task was named by and the key the frames are cached under are one value.

    ``trial_fixations`` / ``fixations_b`` arrive already drift-corrected (the
    caller applies it once for all three render paths); ``drift_corrected``
    just says so, so the single replay can force colour-by-line the way the static
    figure does. There is no connector layer here — see the note at the hoist."""
    dual = fixations_b is not None and not fixations_b.empty
    grid_step_ms = viz_settings.get("anim_grid_step_ms")
    max_frames = viz_settings.get("anim_max_frames")
    # The reading-time / playback info renders in the rail's Animate popover
    # (see `_render_anim_info`), not here.
    animation_settings = settings.with_overrides(
        playback_speed=playback_speed,
        # Drift correction colours the replay by assigned line, exactly as the
        # static figure does once an algorithm is picked. Not the co-animation:
        # it colours like the comparison figure, which keeps the rail's choice.
        color_by_line=bool(settings.color_by_line or (drift_corrected and not dual)),
        show_legend=viz_settings.get("show_compare_legend", True),
        label_a=(
            _resolve_compare_label(
                0, selected_participant, selected_trial, trial_words, trial_fixations
            )
            if dual
            else "Scanpath A"
        ),
        label_b=(
            _resolve_compare_label(
                1,
                compare_participant,
                compare_trial,
                words_b,
                fixations_b,
                dataset_name=dataset_name_b,
            )
            if dual
            else "Scanpath B"
        ),
        autoplay=viz_settings.get("anim_autoplay", True),
        anim_grid_step_ms=grid_step_ms,
        anim_max_frames=max_frames,
        # The co-animation wears the rail's per-scanpath styles, as the static
        # comparison does. Their filters are left behind: B's flags already
        # reach the replay as `fixation_flags_b`, and the replay has no
        # saccade-class filter — so they would only split the cache key.
        style_a=_replay_style(viz_settings.get("compare_style_a")) if dual else None,
        style_b=_replay_style(viz_settings.get("compare_style_b")) if dual else None,
    )
    # The frames depend on neither the speed nor autoplay, nor on the
    # Illustration reasons (the builder never reads them — but a non-1× speed
    # is one, so they change with it). Build and key the replay on fixed
    # values, then stamp the real speed and autoplay onto the copy the cache
    # hands back, so moving the speed slider rebuilds no frame.
    frame_settings = animation_settings.with_overrides(
        playback_speed=1.0,
        autoplay=True,
        illustration_reasons=None,
        # Stamped after the frames, by `finished_figure`; the view keys on it.
        illustration_text="",
        # The duration-size key is layout only — no frame draws it — so it is
        # stamped onto the cached replay in `finished_figure`, and toggling it
        # costs no frame rebuild.
        duration_size_legend=False,
        # Where the legends sit is layout only too: applied to the finished
        # figure in `finished_figure`, so moving a legend rebuilds no frame.
        legend_layout=None,
        # So is the saccades' opacity — a trace attribute no frame
        # restates — stamped in `finished_figure`, so dragging it rebuilds no
        # frame. And the replay never reads the static figure's Snap to line.
        saccade_opacity=1.0,
        fixation_snap_to_line=False,
        fixation_snap_position=DEFAULT_SNAP_POSITION,
        # Nor does it read the static figure's frame or the heatmap's
        # opacity, and the title/caption styling is applied to the finished
        # figure (`annotate_figure`) — pinned, so changing one rebuilds no frame.
        **_REPLAY_UNREAD_DESIGN,
        # B's flags only matter to a replay that draws B — the same rule
        # as `fixations_b` below, so a lone replay's key never carries them.
        **({} if dual else {"fixation_flags_b": None}),
        # A co-animation wears `style_a` / `style_b` (the rail always fills
        # every key), so the figure-wide look is never read — pinned, it can't
        # split the key over a value last set in another mode.
        **(
            _DUAL_UNREAD_STYLE
            if dual and animation_settings.style_a and animation_settings.style_b
            else {}
        ),
    )
    anim_inputs = {
        field.name: getattr(frame_settings, field.name)
        for field in dataclass_fields(frame_settings)
    }
    anim_inputs["fixations_b"] = fixations_b if dual else None
    anim_inputs["words_b"] = words_b if dual else None
    return _ReplayPlan(
        settings=animation_settings,
        frame_settings=frame_settings,
        inputs=anim_inputs,
        key=_figure_input_key(trial_words, trial_fixations, anim_inputs),
    )


def _build_and_render_animation(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None,
    selected_participant: str,
    selected_trial: str,
    compare_participant: str | None,
    compare_trial: str | None,
    *,
    viz_settings: dict,
    plan: _ReplayPlan,
    dataset_name_b: str = "",
):
    """Build + render the animation figure (single or dual co-animation) in the
    main column. Returns ``(view, save_slug, file_stem)`` — the replay's
    `_ReplayView`, whose ``figure()`` is the finished figure.

    ``plan`` is `_plan_replay`'s for these same arguments, worked out before the
    card opens because the replay's task is keyed by it — so the key
    the task carries and the key the build uses are one derivation."""
    dual = fixations_b is not None and not fixations_b.empty
    animation_settings = plan.settings
    frame_settings = plan.frame_settings
    anim_inputs = plan.inputs
    anim_key = plan.key
    _amend_snippet_settings(animation_settings, "animation")
    playback_speed = animation_settings.playback_speed
    autoplay = animation_settings.autoplay
    reasons = viz_settings.get("illustration_reasons")
    preprocessing = _preprocessing_report_row(selected_participant, selected_trial)
    # Rendered on every run, since the snippet takes this text
    # even when the figure comes out of the cache.
    title, caption = _rendered_title_caption(
        viz_settings,
        trial_words,
        trial_fixations,
        selected_participant,
        selected_trial,
        compare_row=(
            {
                "dataset_name": dataset_name_b or _shown_dataset_name(),
                "participant_id": compare_participant,
                "trial_id": compare_trial,
            }
            if dual
            else None
        ),
    )
    _amend_snippet_title_caption(title, caption)
    if dual:
        save_slug = (
            f"{selected_participant}__{selected_trial}__vs__"
            f"{compare_participant}__{compare_trial}"
        )
        file_stem = (
            f"animation_{_safe_filename(selected_participant)}__"
            f"{_safe_filename(selected_trial)}__vs__"
            f"{_safe_filename(compare_participant)}__"
            f"{_safe_filename(compare_trial)}"
        )
    else:
        save_slug = f"{selected_participant}__{selected_trial}"
        file_stem = (
            f"animation_{_safe_filename(selected_participant)}__"
            f"{_safe_filename(selected_trial)}"
        )
    plot_key = "single_anim"
    # The camera saves whichever frame is on screen, hence the `_frame` suffix.
    download_name = f"{file_stem}_frame"

    def finished_figure():
        fig, frame_step_ms = _cached_scanpath_animation(
            trial_words,
            trial_fixations,
            frame_settings,
            anim_inputs["fixations_b"],
            anim_inputs["words_b"],
            anim_key=anim_key,
        )
        # The frames exist; what is left is the player — the clock, the
        # labels and the 10 MB of markup `_ReplayView.from_figure` writes.
        progress.step_to(1)
        set_replay_clock(
            fig, frame_step_ms, playback_speed=playback_speed, autoplay=autoplay
        )
        apply_legend_layout(
            fig,
            animation_settings.legend_layout,
            comparing=anim_inputs["fixations_b"] is not None
            and not anim_inputs["fixations_b"].empty,
            show_colors=animation_settings.show_color_legend,
            show_highlight=animation_settings.show_highlight_legend,
        )
        add_illustration_label(
            fig, reasons, text=viz_settings.get("illustration_text", "")
        )
        # The frames were built at full opacity (`_plan_replay`).
        fig.update_traces(
            opacity=animation_settings.saccade_opacity,
            selector=dict(meta="saccades"),
        )
        # A co-animation whose two size ranges differ has no one key.
        key_range = replay_size_key_range(
            animation_settings, trial_fixations, anim_inputs["fixations_b"]
        )
        if key_range is not None:
            _maybe_add_duration_key(
                fig,
                animation_settings,
                key_range,
                trial_fixations,
                anim_inputs["fixations_b"],
            )
        _annotate_preprocessing(fig, preprocessing)
        if title or caption or viz_settings.get("show_credit"):
            annotate_figure(
                fig, title=title, caption=caption, **figure_text_style(viz_settings)
            )
        return fig

    # What goes into the clip — everything in the figure but autoplay,
    # which a GIF/MP4 does not carry — keys the view and names the export.
    clip_inputs = (
        anim_key,
        float(playback_speed),
        tuple(reasons or ()),
        str(viz_settings.get("illustration_text", "")),
        tuple(sorted((str(k), repr(v)) for k, v in (preprocessing or {}).items())),
        title,
        caption,
        bool(animation_settings.duration_size_legend),
        # Not in `anim_key` (the frames never read it), so the view keys on it.
        repr(normalize_legend_layout(animation_settings.legend_layout)),
        float(animation_settings.saccade_opacity),
        # The title/caption styling is pinned out of `anim_key` and
        # stamped in `finished_figure`, so the view keys on it.
        tuple(figure_text_style(viz_settings).items()),
    )
    view = _cached_replay_view(
        clip_inputs,
        bool(autoplay),
        plot_key,
        download_name,
        _finished_figure=finished_figure,
    )
    _render_true_scale_plot(
        view.plot_html,
        key=plot_key,
        width=view.width,
        height=view.plot_height,
        alt=": ".join(filter(None, ("Animated scanpath replay", _plain_title(title)))),
        fit_window=True,
        toolbar=view.toolbar,
    )
    return view, save_slug, file_stem


def _dataset_table_names() -> dict[str, ColumnNames]:
    """The open dataset's column-name map per table, as the exporters take it."""
    return {
        table: active_column_names(st.session_state, table)
        for table in ("fixations", "words", "raw_gaze")
    }


def subtab_labels_for(simple: bool, *, line_assignment: bool) -> list[str]:
    """The per-trial subtab bar's labels, in order, for the interface mode.

    Essentials keeps what a first-time viewer reaches for (the current figure's
    export and Share) plus a ＋ More list of what Full adds. Full adds
    📐 Line assignment only while ``line_assignment`` (drift correction) is
    offered. Dataset inspection is on the 🗂️ **Data** page, not this bar.
    """
    if simple:
        return [SUBTAB_EXPORT, SUBTAB_SHARE, SUBTAB_MORE]
    labels = [SUBTAB_ANNOTATIONS, SUBTAB_STIMULUS, SUBTAB_COMPARISONS]
    if line_assignment:
        labels.append(SUBTAB_LINE_ASSIGNMENT)
    return labels + [SUBTAB_EXPORT, SUBTAB_SHARE]


def _render_export_panel(
    displayed_fig,
    *,
    animate: bool,
    save_slug: str,
    file_stem: str | None,
    combos: pd.DataFrame,
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    combos_all: pd.DataFrame,
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    raw_gaze: pd.DataFrame,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    raw_gaze_all: pd.DataFrame | None = None,
    line_spacing: float,
    scale_text_to_boxes: bool,
    selected_participant: str,
    selected_trial: str,
    plot_key: str = "single",
    replay: _ReplayView | None = None,
    include_bundle: bool = True,
) -> None:
    """Consolidated Export subtab: the currently-viewed figure on top, then a
    bulk multi-trial export below (left out when ``include_bundle`` is false).

    "Current figure" exports the live figure (static PNG/SVG/PDF/HTML, or
    the HTML/GIF/MP4 animation when animating) so the on-screen view — including
    a comparison or animation — round-trips exactly; the bulk section rebuilds
    static figures across many trials."""
    st.markdown("## Current figure")
    if viz_settings.get("redact_text"):
        selected = selected_hover_text(
            words_filtered,
            fixations_filtered,
            viz_settings.get("word_hover_fields"),
            viz_settings.get("fixation_hover_fields"),
        )
        if selected:
            st.caption(
                "These selected tooltip fields can appear in saved HTML. Review them under Figure → Hover fields."
            )
            st.text(", ".join(selected))
        if viz_settings.get("show_stimulus_image"):
            st.caption(
                "The stimulus image can contain readable text. Turn it off under Stimulus to omit it."
            )
    quick_export = st.container()
    from . import publication_ui

    def figure_settings() -> dict:
        return _current_figure_config(
            selected_participant,
            selected_trial,
            canvas_width,
            canvas_height,
            viz_settings.get("x_field", "x"),
            viz_settings.get("y_field", "y"),
            _build_figure_settings(
                viz_settings, bool(viz_settings.get("show_raw_gaze"))
            ),
            viz_settings,
            base_font_size,
            raw_gaze,
            font_family=font_family,
        )

    reading = f"Participant {selected_participant} · Trial {selected_trial}"
    title = (
        _figure_alt(displayed_fig, reading) if displayed_fig is not None else reading
    )
    editing = publication_ui.render(
        displayed_fig,
        title=title,
        kind="replay" if animate else "scanpath",
        plot_id=_true_scale_plot_id(plot_key),
        replay=replay,
        settings_for=figure_settings,
    )

    if not editing:
        with quick_export:
            if animate and replay is not None:
                _render_animation_export(replay, file_stem=file_stem or "animation")
                render_cite_button(st, key="anim_export", what="this replay")
            elif animate or displayed_fig is None:
                st.caption("Select a trial to export its figure.")
            else:
                _render_save_plot_button(
                    displayed_fig,
                    canvas_width=int(canvas_width),
                    canvas_height=int(canvas_height),
                    slug=save_slug,
                    key_prefix="single",
                    plot_key=plot_key,
                )
                render_cite_button(st, key="single_export")
                if (displayed_fig.layout.meta or {}).get("scanpath_panels"):
                    from . import panel_proof_ui

                    panel_proof_ui.render(
                        displayed_fig, _print_size_setting(), figure_settings
                    )

    if not include_bundle:
        ui_mode.render_export_pointer(st)
        return
    st.divider()
    if editing:
        bundle = st.expander(
            "Export bundle", key="publication_bundle", on_change="rerun"
        )
        if not bundle.open:
            return
    else:
        bundle = st.expander("Export bundle")
    if animate or st.session_state.get(SINGLE_COMPARE_TOGGLE):
        bundle.caption("The bundle exports static, single-trial figures.")
    # The batch draws raw gaze when the rail does — forced off, a
    # raw-gaze-only dataset would export blank figures. Each trial's own
    # samples are handed to its figure inside `bulk_export`.
    bulk_settings = _build_figure_settings(
        viz_settings, bool(viz_settings.get("show_raw_gaze"))
    )
    bulk_settings["line_spacing"] = line_spacing
    bulk_settings["scale_text_to_boxes"] = scale_text_to_boxes
    bulk_settings.update(
        {
            key: viz_settings[key]
            for key in (
                "show_stimulus_image",
                "stimulus_image_upload_uri",
                "stimulus_image_opacity",
                "stimulus_image_offset_x",
                "stimulus_image_offset_y",
                "stimulus_image_scale",
                "illustration_label",
            )
            if key in viz_settings
        }
    )
    bulk_settings["data_source"] = st.session_state.get("data_source_choice")
    bulk_settings["data_source_label"] = current_dataset_name()
    bulk_settings["dataset_references"] = dataset_credit.references(st.session_state)
    bulk_settings["synthetic_source"] = bulk_settings["data_source"] in (
        AUTHOR_CHOICE,
        MANUAL_SAMPLE_CHOICE,
        SYNTHETIC_CHOICE,
    )
    # The bulk export rebuilds every figure from scratch, so the drift
    # correction must ride along or the batch silently differs from
    # the corrected figure on screen. Applied per trial inside `bulk_export`
    # (figures only — the exported tables stay uncorrected by design).
    bulk_settings["align_algorithm"] = viz_settings.get("align_algorithm", "Off")
    bulk_settings["align_connectors"] = bool(viz_settings.get("align_connectors"))
    # The rail's title/caption pattern is the single source of truth —
    # bulk export reads it back rather than keeping its own copy.
    bulk_settings["title_pattern"] = viz_settings.get("title_pattern", "")
    bulk_settings["caption_pattern"] = viz_settings.get("caption_pattern", "")
    bulk_settings["preprocessing"] = dict(
        st.session_state.get("_preprocessing_settings") or {}
    )
    report = st.session_state.get("_preprocessing_report")
    bulk_settings["preprocessing_report"] = (
        report.to_dict("records") if isinstance(report, pd.DataFrame) else []
    )
    # No `pixels_per_degree`: the export's saccade table gives amplitudes in px
    # only, with no visual-angle conversion.
    # Ship the participant table with the bundle, as its own file.
    #
    # The **fingerprint** goes in the settings dict, not the frame. `sig` below
    # hashes `figure_settings` through `json.dumps(..., default=str)`, and
    # `default=str` on a DataFrame falls through to `repr(df)`, which pandas
    # truncates past 60 rows — so re-uploading a corrected table of the same
    # shape would produce an identical signature and serve the *stale* cached
    # zip, with the pre-edit `metadata/participants.csv` inside it. The frame itself
    # rides on a private key the exporter reads and the signature ignores.
    _attached = _metadata_mod.active()
    if _attached is not None and not _attached.frame.empty:
        bulk_settings["participant_metadata_fingerprint"] = frame_fingerprint(
            _attached.frame
        )
        st.session_state["_export_participant_metadata"] = _attached.frame
    else:
        st.session_state.pop("_export_participant_metadata", None)
    # The trial table travels the same way, on its own key and its own
    # fingerprint — two tables can be attached, replaced or cleared
    # independently, so one shared signature would serve a stale zip whenever
    # only the other one changed.
    from scanpath_studio import metadata as _md

    _attached_trials = _md.active_trials()
    if _attached_trials is not None and not _attached_trials.frame.empty:
        bulk_settings["trial_metadata_fingerprint"] = frame_fingerprint(
            _attached_trials.frame
        )
        st.session_state["_export_trial_metadata"] = _attached_trials.frame
    else:
        st.session_state.pop("_export_trial_metadata", None)
    # And the text table, the third grain — same reasoning again.
    _attached_texts = _md.active_texts()
    if _attached_texts is not None and not _attached_texts.frame.empty:
        bulk_settings["text_metadata_fingerprint"] = frame_fingerprint(
            _attached_texts.frame
        )
        st.session_state["_export_text_metadata"] = _attached_texts.frame
    else:
        st.session_state.pop("_export_text_metadata", None)
    with bundle:
        _render_bulk_export(
            combos,
            words_filtered,
            fixations_filtered,
            combos_all,
            words_all,
            fixations_all,
            raw_gaze,
            raw_gaze_all=raw_gaze if raw_gaze_all is None else raw_gaze_all,
            canvas_width=int(canvas_width),
            canvas_height=int(canvas_height),
            base_font_size=int(base_font_size),
            font_family=font_family,
            x_field=viz_settings["x_field"],
            y_field=viz_settings["y_field"],
            figure_settings=bulk_settings,
            selected_participant=selected_participant,
            selected_trial=selected_trial,
        )
    render_cite_button(st, key="bulk_export", what="these figures and tables")


_CHIP_NEUTRAL_BG = "#EEF2F7"


def _chip_value_and_uniqueness(
    col, trial_words, trial_fixations, participant, trial_raw_gaze=None
):
    """``(value, is_trial_level)`` for ``col`` in the trial.

    ``value`` is the first non-null (words first, then fixations);
    ``participant_id`` resolves to the selected participant. ``is_trial_level`` is
    False when the column varies *within* this trial (so the single chip value is
    misleading) — a cheap ``nunique`` on the trial's own (small) rows, used only to
    warn. ``participant_id`` is trivially trial-level. Returns ``(None, True)``
    when nothing resolves."""
    if col == "participant_id":
        return (participant or None, True)
    for src in (trial_words, trial_fixations):
        if src is None or src.empty or col not in src.columns:
            continue
        series = src[col]
        non_null = series.dropna()
        if non_null.empty:
            # An empty column is not an answer: returning here would let a
            # recorded column that happens to be blank for this trial *block*
            # the attached metadata below, and a field the user had just added
            # to the chips would render nothing, with nothing on screen to say
            # why.
            continue
        return (non_null.iloc[0], int(series.nunique(dropna=True)) <= 1)
    # Not a recorded column — try the attached participant table. A
    # reader attribute is trivially constant within a trial, so it never earns
    # the ⚠️ "varies within this trial" flag. Checked *after* the frames, so a
    # real column of the same name always wins.
    attached = _metadata_mod.active()
    if attached is not None and participant is not None:
        value = attached.values_for(participant).get(col)
        if value is not None and not pd.isna(value):
            return (value, True)
    # Then the attached *trial* table, on the same terms. A trial
    # attribute is constant within its trial by definition, so it never earns
    # the warning either. The trial id comes off the frames rather than from an
    # argument: every caller already passes this trial's own rows, and the id is
    # on both of them.
    attached_trials = _metadata_mod.active_trials()
    if attached_trials is not None:
        trial_id = _first_value(
            "trial_id", trial_words, trial_fixations, trial_raw_gaze
        )
        if trial_id is not None:
            value = attached_trials.values_for(participant, trial_id).get(col)
            if value is not None and not pd.isna(value):
                return (value, True)
    # Resolve text fields by the same recording identity used by the join report.
    attached_texts = _metadata_mod.active_texts()
    if attached_texts is not None and col in attached_texts.names:
        text_id = _metadata_mod.trial_text_id(
            trial_fixations, trial_words, trial_raw_gaze
        )
        if text_id is not None:
            value = attached_texts.values_for(text_id).get(col)
            if value is not None and not pd.isna(value):
                return (value, True)
    return (None, True)


def _first_value(col: str, *frames):
    """First non-null ``col`` across ``frames``, or ``None``."""
    for src in frames:
        if src is not None and not src.empty and col in src.columns:
            non_null = src[col].dropna()
            if not non_null.empty:
                return non_null.iloc[0]
    return None


def _chip_color(col: str, value_str: str) -> str:
    """Background for a chip.

    A user-picked colour (any field, any dataset — set via the ✏️ Edit
    chips popover's **Chip colours** section, `trial_chip_colors`) wins over
    everything below. Absent that, known OneStop conditions keep their
    metadata-table colour; everything else is neutral.
    """
    override = (st.session_state.get("trial_chip_colors") or {}).get(col)
    if override:
        return override
    v = value_str.lower()
    if col == "difficulty_level":
        for prefix, color in _DIFFICULTY_COLORS.items():
            if v.startswith(prefix):
                return color
    elif col == "question_preview" and v in ("true", "1"):
        return _PREVIEW_COLOR
    elif col == "repeated_reading_trial" and v in ("true", "1"):
        return _REPEAT_COLOR
    elif col == "is_correct":
        if v in ("true", "1"):
            return "#d4edda"
        if v in ("false", "0"):
            return "#f8d7da"
    return _CHIP_NEUTRAL_BG


@dataclass(frozen=True)
class ChipEntry:
    """One chip's facts, before they are drawn as a chip or a table cell.

    ``label`` and ``value`` are plain text — escaped where they are drawn.
    ``trial_level`` is False for a column that varies within the trial (drawn
    with the warning mark); ``color`` is the chip's background (`_chip_color`).
    """

    col: str
    label: str
    value: str
    trial_level: bool = True
    color: str = _CHIP_NEUTRAL_BG
    tip: str = ""  # the header's tooltip: description, source column


def _trial_chip_entries(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str | None,
    fields,
    *,
    trial_raw_gaze: pd.DataFrame | None = None,
    gaze_samples: int | None = None,
    names: ColumnNames | None = None,
) -> list[ChipEntry]:
    """The chips one trial gets for ``fields``, in order, with nothing to show
    dropped — what the chip table draws, for one reading or two.

    ``gaze_samples`` is `_summary_rows`' count in place of the samples.
    ``names`` labels the fields: the open dataset's map by default,
    the reading's own dataset's for Compare's B."""
    if names is None:
        names = active_all(st.session_state)
    entries: list[ChipEntry] = []
    summary_lookup: dict | None = None  # computed once, only if a summary chip
    for col in fields or []:
        # Virtual summary fields (reading time / counts) — always trial-level,
        # computed once from `_summary_rows` rather than read off a column.
        if col in SUMMARY_CHIP_FIELDS:
            if summary_lookup is None:
                summary_lookup = {
                    r["Field"]: r["Value"]
                    for r in _summary_rows(
                        trial_words,
                        trial_fixations,
                        trial_raw_gaze,
                        gaze_samples=gaze_samples,
                    )
                }
            label = SUMMARY_CHIP_FIELDS[col]
            value = summary_lookup.get(label)
            if value in (None, ""):
                # Not measured for this trial: no fixations to count, no
                # words to count, no word boxes for "Fixations in word boxes".
                continue
            entries.append(
                ChipEntry(
                    col,
                    label,
                    str(value),
                    True,
                    _chip_color(col, str(value)),
                    field_help(col, names),
                )
            )
            continue
        value, trial_level = _chip_value_and_uniqueness(
            col, trial_words, trial_fixations, participant, trial_raw_gaze
        )
        if value is None:
            continue
        value_str = str(value)
        # Skip empty / missing values (a "string" optional field coerces NaN to
        # the literal "nan", e.g. ET2 readers with no recorded gender).
        if value_str.strip().lower() in ("", "nan", "none", "<na>"):
            continue
        entries.append(
            ChipEntry(
                col,
                chip_field_label(col, names),
                value_str,
                bool(trial_level),
                _chip_color(col, value_str),
                field_help(col, names),
            )
        )
    return entries


def _is_number(value: str) -> bool:
    """Whether a chip value reads as a number — ``2,233`` included."""
    try:
        float(value.replace(",", ""))
    except ValueError:
        return False
    return True


def _chip_table_html(
    *sides: tuple[str | None, str | None, list[ChipEntry]],
    order,
) -> str:
    """The chips above the plot as a table: one column per field, one row per
    reading — Compare's A/B table and, with one row, the single trial's.

    ``sides`` is ``(name, colour, entries)`` per row — A first. A side with no
    name gets no row label: the single trial's one row has nothing to tell apart,
    so it has no label column at all. ``order`` is the column order (the ✏️ chip
    order; Compare puts Trial ID first); a field that no side has gets no
    column. Deliberately *not* differences first: the columns would reshuffle
    every time ◀ ▶ steps to a trial that differs elsewhere.

    With two rows, a value both share is written in each row in a quieter
    weight, so what differs is what stands out. (Not once, in a cell spanning
    both rows: that reads as B's cell left blank.) A value one
    side lacks reads ``–``. Each value keeps its chip's tint, as a pill — the
    built-in condition colours and the ones picked in ✏️ — and a column
    whose values are all numbers is right-aligned so they line up.

    Built as one line of HTML: `st.markdown` would read an indented line as code.
    """
    by_side = [{e.col: e for e in entries} for _name, _color, entries in sides]
    columns = [col for col in order if any(col in side for side in by_side)]

    def cell(entry: ChipEntry | None, *, extra: str = "") -> str:
        classes = [extra] if extra else []
        if entry is None:
            classes.append("sps-ct-missing")
            body = "–"
        else:
            body = html.escape(entry.value)
            if entry.color != _CHIP_NEUTRAL_BG:
                # A pill around the value, not a filled cell: a whole tinted cell
                # glares in a dark theme. Chip tints are always light, so the
                # text is pinned dark, as on a chip.
                body = (
                    f'<span class="sps-ct-tint" style="background:'
                    f'{html.escape(entry.color)};color:#212529">{body}</span>'
                )
            if not entry.trial_level:
                body = f"{icon_html('warning')} {body}"
        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        return f"<td{class_attr}>{body}</td>"

    numeric = {
        col: all(_is_number(side[col].value) for side in by_side if col in side)
        for col in columns
    }
    labelled = any(name for name, _color, _entries in sides)
    shared = {
        col: len(sides) > 1
        and all(col in side for side in by_side)
        and len({side[col].value for side in by_side}) == 1
        for col in columns
    }
    num_class = ' class="sps-ct-num"'

    def header(col: str) -> str:
        entry = next(side[col] for side in by_side if col in side)
        tip = f' title="{html.escape(entry.tip)}"' if entry.tip else ""
        return (
            f'<th scope="col"{num_class if numeric[col] else ""}{tip}>'
            f"{html.escape(entry.label)}</th>"
        )

    head = "".join(header(col) for col in columns)
    rows = []
    for (name, color, _entries), side in zip(sides, by_side):
        cells = []
        for col in columns:
            num = "sps-ct-num" if numeric[col] else ""
            if not shared[col]:
                cells.append(cell(side.get(col), extra=num))
            else:
                # Any side's warning mark says the shared value varies somewhere.
                entry = side[col]
                if any(not s[col].trial_level for s in by_side):
                    entry = replace(entry, trial_level=False)
                cells.append(
                    cell(entry, extra=" ".join(filter(None, (num, "sps-ct-same"))))
                )
        label = ""
        if labelled:
            dot = (
                f'<span class="sps-ct-dot" style="background:{html.escape(color)}">'
                "</span>"
                if color
                else ""
            )
            label = (
                f'<th scope="row" class="sps-ct-side">{dot}'
                f"{html.escape(name or '')}</th>"
            )
        rows.append(f"<tr>{label}{''.join(cells)}</tr>")
    corner = '<td class="sps-ct-corner"></td>' if labelled else ""
    return (
        '<div class="sps-chip-table-wrap"><table class="sps-chip-table">'
        f"<thead><tr>{corner}{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


#: The Trial ID column Compare's table always leads with — not a chip field, so
#: it cannot collide with one (the ``trial_id`` field itself is left out there).
_TRIAL_ID_COLUMN = "@trial_id_shown"


@dataclass(frozen=True)
class ChipReading:
    """One row of a chip table — Compare's A/B table, or the Comparisons
    subtab's: a reading's own rows and its ids.

    ``raw_gaze`` is the reading's samples when the caller already holds them
    (A); ``gaze_samples`` is just their count (B — `_c_gaze_sample_count`)."""

    words: pd.DataFrame
    fixations: pd.DataFrame
    participant: str | None
    # `utils.trial_id_shown` — the id as the pickers show it; Compare's table
    # leads with it, the Comparisons subtab's rows are named instead.
    trial_shown: str = ""
    raw_gaze: pd.DataFrame | None = None
    gaze_samples: int | None = None
    names: ColumnNames | None = None  # its dataset's map, else the open one

    def entries(self, fields) -> list[ChipEntry]:
        """This reading's chips for ``fields`` (`_trial_chip_entries`)."""
        return _trial_chip_entries(
            self.words,
            self.fixations,
            self.participant,
            fields,
            trial_raw_gaze=self.raw_gaze,
            gaze_samples=self.gaze_samples,
            names=self.names,
        )


@st.cache_data(show_spinner=False, max_entries=256)
def _c_gaze_sample_count(
    _raw_gaze: pd.DataFrame, cache_key: tuple, participant, trial, screen
) -> int | None:
    """How many samples B has, for its gaze-sample chip in Compare.

    Cached as a number, so a rerun neither re-cuts B's samples nor unpickles
    the trial index (a frame cached here would be). ``cache_key`` is
    ``frame_fingerprint(_raw_gaze)``. ``None`` when there are none to count — a
    multipart B whose samples carry no screen id included, which A's own
    extraction hides rather than counting every screen's samples as one.
    """
    frame = extract_trial(_raw_gaze, participant, trial)
    if screen is not None:
        if SCREEN_ID not in frame.columns:
            return None
        frame = extract_part(frame, participant, trial, screen)
    return len(frame) or None


def _render_compare_chip_table(fields, *, a: ChipReading, b: ChipReading) -> None:
    """Draw Compare mode's A/B table — the chips of both readings.

    Each row is named in its scanpath's colour."""
    style_a, style_b = _collect_compare_styles()
    colors = (
        style_a.get("fix_color") or compare_palette_color(0),
        style_b.get("fix_color") or compare_palette_color(1),
    )
    sides = []
    for name, color, reading in zip("AB", colors, (a, b)):
        entries = reading.entries(fields)
        trial_id = ChipEntry(_TRIAL_ID_COLUMN, "Trial ID", reading.trial_shown)
        sides.append(
            (name, color, [trial_id, *(e for e in entries if e.col != "trial_id")])
        )
    st.markdown(
        _chip_table_html(*sides, order=[_TRIAL_ID_COLUMN, *(fields or [])]),
        unsafe_allow_html=True,
    )


def _render_matches_chip_table(fields, rows: list[tuple[str, ChipReading]]) -> None:
    """The Comparisons subtab's chip table: the selected trial and each
    match on the page, one row each, named as their panels are, under the
    fields the ✏️ chips menu picked — the table above the plot, one row per
    reading, so the matches compare down each column and a value they all
    share is written quieter."""
    sides = [(label, None, reading.entries(fields)) for label, reading in rows]
    if any(entries for _label, _color, entries in sides):
        st.markdown(
            _chip_table_html(*sides, order=list(fields or [])),
            unsafe_allow_html=True,
        )


def _match_gaze_samples(raw_gaze: pd.DataFrame | None, fix: pd.DataFrame):
    """How many samples a Comparisons match has, on the screen it is drawn on
    — its gaze-sample chip, cached like Compare's B."""
    if raw_gaze is None or raw_gaze.empty or fix.empty:
        return None
    first = fix.iloc[0]
    screen = str(first[SCREEN_ID]) if SCREEN_ID in fix.columns else None
    return _c_gaze_sample_count(
        raw_gaze,
        frame_fingerprint(raw_gaze),
        first["participant_id"],
        first["trial_id"],
        screen,
    )


def _render_trial_condition_chips(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str | None,
    fields,
    *,
    trial_raw_gaze: pd.DataFrame | None = None,
) -> None:
    """Render the chips above the plot — the trial's identity and experiment
    conditions, so "what am I looking at" is answered at a glance. They are a
    one-row table, a column per field.

    ``fields`` is the configurable list of fields to surface (the ✏️ Edit chips
    popover). A data column that varies within the trial is shown (first value)
    but flagged with ⚠️.

    **The computed summary stats are chips too** — reading time and the counts
    are picked, ordered and coloured in the ✏️ popover like every other field,
    so the two numbers most often wanted (total reading time, fixation count)
    cost no extra click. This returns nothing.

    It is drawn as `_chip_table_html`'s one-row table — the format of Compare's
    A/B table, so the two modes read alike."""
    entries = _trial_chip_entries(
        trial_words,
        trial_fixations,
        participant,
        fields,
        trial_raw_gaze=trial_raw_gaze,
    )
    if entries:
        st.markdown(
            _chip_table_html((None, None, entries), order=list(fields or [])),
            unsafe_allow_html=True,
        )


def _render_chip_menu(host, words: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """The ✏️ chips menu at the end of A's trial row: show or hide the chips
    above the plot, and pick and order their fields.

    Hiding keeps ``trial_chip_fields``, so showing them again restores the same
    row; it applies to Compare's A/B table too."""
    st.session_state.setdefault(SINGLE_SHOW_CHIPS, True)
    # Named for screen readers; `styles.py` clips the name, so the
    # pencil is still all that is drawn.
    with host.popover(
        "Trial summary above the plot",
        icon=ICONS["edit"],
        help="Show or hide the trial summary above the plot, and choose and "
        "reorder its fields.",
        width="content",
        wrap=True,
        key="iconpop_chip_fields",
    ):
        st.toggle(
            "Show the trial summary above the plot",
            key=SINGLE_SHOW_CHIPS,
            # Rendered on the Scanpath view only, and seeded by a link
            # (`?show_chips=`), so it must survive a trip to another view.
            persist_state="session",
            help="Hide it to give the plot more room. The fields you picked are kept.",
        )
        render_trial_chip_picker(words, fixations, host=st.container())


def render_single_trial_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    combos: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    raw_gaze: pd.DataFrame | None = None,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    combos_all: pd.DataFrame | None = None,
    words_all: pd.DataFrame | None = None,
    fixations_all: pd.DataFrame | None = None,
    raw_gaze_all: pd.DataFrame | None = None,
    share_renderer: Callable[[bool], None] | None = None,
    # Renders the data-source picker into the picker row's first cell.
    # Passed by ``app.main`` (which owns the source list + wizard hooks).
    data_source_renderer: Callable[[object], None] | None = None,
    canvas_renderer: Callable[[Any], None] | None = None,
    on_reading_selected: Callable[[bool], None] | None = None,
) -> None:
    """Render the main Scanpath Visualization screen (static + animated).

    Layout, with the plot and its panels beside the full-height controls:

    1. A compact **selection bar** above the plot — the dataset picker, the
       trial picker and a filter popover on one row, with the trial's
       experiment-condition chips below it (the trial's "what am I looking at"
       at a glance).
    2. A **plot + right rail** split: the scanpath plot on the left, and a control
       rail on the right carrying the **view modes** (Animate / Compare) and the
       **visualization controls** (``controls.render_plot_controls``, rendered
       here with ``host=``).
    3. A plot-width **subtab bar** directly below it: 📝 Annotations ·
       📄 Stimulus & context · 🔬 Comparisons · 📤 Export · 🔗 Share. Export
       (``_render_export_panel``) holds the current figure and the bulk export;
       Share builds the deep link via ``share_renderer`` (passed by
       ``app.main``) and is **Link · Code · File** — File is the settings file.
       The dataset inspection lives on the 🗂️ Data page.

    ``combos_all`` / ``words_all`` / ``fixations_all`` are the unfiltered frames
    the Export subtab's bulk section uses for its "whole dataset" scope; they
    fall back to the filtered frames when not supplied.
    """
    if combos_all is None:
        combos_all = combos
    if words_all is None:
        words_all = words_filtered
    if fixations_all is None:
        fixations_all = fixations_filtered
    # The dataset's canvas, before a multipart screen's own replaces it below —
    # a same-dataset B on a screen with no canvas of its own is drawn on this.
    dataset_canvas = (int(canvas_width), int(canvas_height))

    # --- Plot (left) + control rail (right) -----------------------------------
    # Columns FIRST so the rail starts at the very top, beside the selection —
    # built for the everything-beside-the-plot workflow. The selection menus +
    # chips + plot + per-trial subtabs live in the left column. The narrow rail
    # stays in page flow, so it can extend below a short plot without pushing
    # the subtabs away from the figure.
    with st.container(key="scanpath_workspace"):
        plot_col, rail_col = st.columns([4, 1], gap="large")
    # Rail containers filled after the rail itself (B's filters).
    rail_slots: dict = {}
    with rail_col:
        rail = st.container(key="scanpath_rail")

    with plot_col:
        # Everything is on the picker row below: the dataset, the trial, the
        # scrubber, ◀ ▶ ⇅ and a filter popover, which holds the Text /
        # Participant multiselects beside the condition/annotation filters, so
        # there is one place that narrows the pool.
        #
        # `tour_grp_data_source` and `tour_grp_narrow_by` are sibling spotlight
        # targets: the row's lead cell and the filter popover's body.
        def _render_dataset_cell(host) -> None:
            # No wrapper container here: `app.render_data_source_picker` makes
            # its own `tour_grp_data_source`, and a second one is a duplicate key.
            if data_source_renderer is not None:
                data_source_renderer(host)

        def _render_filters(host) -> None:
            """Every way to narrow the pool, behind one funnel.

            The funnel and the chips' menu are each their own Full-only
            container, so each stays a direct child of the ``railbtn_*``
            cluster and lays out as the cluster's other cells do. In Essentials
            they stay in the page, hidden, with their values, and a ＋ More
            list takes the cell."""
            pop = ui_mode.advanced_only(host, "trial_filters").popover(
                "Filter the trial list",
                icon=_FILTER_ICON,
                width="content",
                help="Select the whole readings available in the trial list.",
                key="iconpop_filter_trials",
            )
            box = pop.container(key="tour_grp_narrow_by")
            box.caption(
                "Select whole readings. Each selected reading keeps all of its fixations."
            )
            _render_pool_filters(box, words_all, fixations_all, raw_gaze_all)
            # The chips' menu closes A's cluster (◀ ▶ ⇅ 🔎 ✏️), so the chip
            # table below has the plot's whole width, and hiding it
            # leaves no row behind. Drawn here, before the table reads
            # `trial_chip_fields`, so an edit applies the same run.
            _render_chip_menu(
                ui_mode.advanced_only(host, "chip_fields"), words_all, fixations_all
            )
            ui_mode.render_more_popover(
                ui_mode.simple_only(host, "picker_more"),
                "picker",
                multiple_trials=len(combos) > 1,
            )

        # A dataset with screens gets the screen navigator at the trial row's
        # right end; the cell is reserved now and filled once the trial (and so
        # its screens) is resolved below.
        has_screens = any(
            frame is not None and SCREEN_ID in frame.columns
            for frame in (words_filtered, fixations_filtered, raw_gaze)
        )
        screen_cells: dict = {}

        def _reserve_screen_cell(host) -> None:
            screen_cells["a"] = host.container(key="tour_grp_screen_picker")

        # Trial picker (its own row of columns): selectbox + slider + ◀ ▶.
        with st.container(key="tour_grp_trial_picker"):
            selected_participant, selected_trial, selection_mode, selected_text = (
                select_trial(
                    combos,
                    key_prefix="single",
                    leading_renderer=_render_dataset_cell,
                    filter_renderer=_render_filters,
                    trailing_renderer=_reserve_screen_cell if has_screens else None,
                    # The frames `combos` was built from, so the ⇅ sort
                    # popover can offer computed keys (fixation count, reading
                    # time) alongside the reader / text / condition columns.
                    words=words_filtered,
                    fixations=fixations_filtered,
                )
            )
        screen_slot = screen_cells.get("a")
        # Slots filled once the selection is resolved (chips need the trial).
        #
        # Creation order *is* screen order, so these reservations are the whole
        # layout: **both control lines first, then the chips** (control A ·
        # control B · chips), so the A and B selectors sit together rather than
        # a strip apart. The chips of both readings are one A/B table in
        # `chips_slot`, its rows named in each scanpath's colour.
        # Keyed containers double as welcome-tour spotlight targets.
        compare_slot = st.container(key="tour_grp_compare_picker")
        # Full-only: Essentials hides the trial summary table (the wrapper is
        # drawn either way, so the figure keeps its position).
        chips_slot = ui_mode.advanced_only(st, ui_mode.TRIAL_CHIPS).container(
            key="tour_grp_chips"
        )
        # Notes about the figure that come *before* it sit above the
        # stage, so the figure is always the stage's second child and a figure
        # already on screen stays put while the next one is built.
        plot_notes_slot = st.container()
        plot_slot = st.container(key="tour_grp_plot")
        # The stage's first child: the size box + loading card (styles.py).
        plot_loading_slot = plot_slot.empty()

        # Keep the panels immediately below the plot even when the controls
        # extend farther down the right side.
        subtabs_slot = st.container(key="tour_grp_subtabs")

    # A dataset that fails its data checks badly (most fixations at 0 ms, most
    # positions missing) still draws a plausible figure; say so above it.
    render_data_health_notice(plot_notes_slot, words_all, fixations_all, raw_gaze_all)

    if not (selected_participant and selected_trial):
        if on_reading_selected is not None:
            on_reading_selected(False)
        return

    # Remember the resolved selection so the Share subtab can build a deep link
    # back to exactly this trial (`url_state._build_share_query` reads it).
    st.session_state["_share_selection"] = {
        "participant_id": selected_participant,
        "trial_id": selected_trial,
    }

    parent_words = extract_trial(words_filtered, selected_participant, selected_trial)
    parent_fixations = extract_trial(
        fixations_filtered, selected_participant, selected_trial
    )
    parent_fixations = with_onset_provenance(parent_fixations)
    elapsed_axis = chart_axes.ELAPSED in (
        st.session_state.get("global_x_field"),
        st.session_state.get("global_y_field"),
    )
    if elapsed_axis:
        parent_fixations = chart_axes.with_origin(parent_fixations)
    parent_raw_gaze = pd.DataFrame()
    if raw_gaze is not None and not raw_gaze.empty:
        parent_raw_gaze = extract_trial(raw_gaze, selected_participant, selected_trial)
    screens, screen_error = _screen_catalog_status(
        parent_words, parent_fixations, parent_raw_gaze
    )
    if screen_error:
        plot_notes_slot.warning(screen_error)
        return
    selected_screen = _render_screen_navigator(screens, host=screen_slot)
    from .annotations import render_disputed_note

    render_disputed_note(
        plot_notes_slot, selected_participant, selected_trial, selected_screen
    )
    if selected_screen is not None:
        trial_words = screen_rows(parent_words, selected_screen)
        trial_fixations = screen_rows(parent_fixations, selected_screen)
        trial_raw_gaze = screen_rows(parent_raw_gaze, selected_screen)
        # Named like the reading's slice, so its samples are not hashed per rerun.
        assign_derived(
            trial_raw_gaze, "screen_rows", parent_raw_gaze, str(selected_screen)
        )
        for label, parent in (
            ("Words", parent_words),
            ("Fixations", parent_fixations),
            ("Raw gaze", parent_raw_gaze),
        ):
            if not parent.empty and SCREEN_ID not in parent:
                plot_notes_slot.warning(
                    f"{label} has no Screen ID. Its rows cannot be placed on this screen."
                )
        st.session_state["_share_selection"]["screen_id"] = selected_screen
        per_screen_canvas = (
            screen_canvas_size(trial_words)
            or screen_canvas_size(trial_fixations)
            or screen_canvas_size(trial_raw_gaze)
        )
        if per_screen_canvas is not None:
            canvas_width, canvas_height = per_screen_canvas
    else:
        trial_words = parent_words
        trial_fixations = parent_fixations
        trial_raw_gaze = parent_raw_gaze
    trial_has_raw_gaze = not trial_raw_gaze.empty
    # The replay, Compare and the fixation / saccade layers are all made
    # of fixations, and nothing in the app derives fixations from samples — so a
    # trial without them (raw gaze only, or words only) draws the static figure,
    # with those controls greyed and the reason said above the plot.
    trial_has_fixations = not trial_fixations.empty
    if on_reading_selected is not None:
        on_reading_selected(trial_has_fixations)
    has_raw_gaze = raw_gaze is not None and not raw_gaze.empty

    # Stimulus-page background image (MultiplEYE): the trial's (screen's) own.
    trial_image = _reading_stimulus_image(trial_words, trial_fixations)
    has_stimulus_image = trial_image is not None
    trial_image_path, trial_image_size, trial_image_origin = trial_image or (
        None,
        None,
        None,
    )

    # The editor and the figure use the same comparison. B's picker resolves
    # its own dataset, trial filters and screen, including when A and B are the
    # same reading or B's filters leave no trial. Its row was reserved above.
    animate_requested = st.session_state.setdefault(SINGLE_ANIMATE, False)
    animate = animate_requested and trial_has_fixations
    compare_requested = st.session_state.setdefault(SINGLE_COMPARE_TOGGLE, False)
    compare_participant, compare_trial = None, None
    compare_source: SecondaryDataset | None = None
    compare_pool: SecondaryDataset | None = None
    selected_compare_screen: str | None = None
    compare_screen_canvas = None
    compare_screen_error = ""
    if compare_requested and trial_has_fixations:
        with compare_slot:
            compare_participant, compare_trial, compare_source, compare_pool = (
                _render_compare_selector(
                    combos,
                    selection_mode,
                    selected_participant,
                    selected_trial,
                    selected_text,
                    animate=animate,
                    # Lets the selector order candidates by the main
                    # picker's own sort keys (fixation count, reading time, …).
                    fixations_filtered=fixations_filtered,
                    words_filtered=words_filtered,
                    combos_all=combos_all,
                    words_all=words_all,
                    fixations_all=fixations_all,
                    loading_slot=plot_loading_slot,
                    screen_cells=screen_cells,
                    screen_track=has_screens,
                )
            )
        # B's own screen navigator, at the end of B's own row — built from
        # B's own trial (not A's), so B can pick any of its own screens
        # independently of whichever one A has selected.
        # `compare_words_pool`/`compare_fixations_pool` (also read further
        # down, at `_build_compare_meta`) are B's own filtered pool
        # (`compare_pool`, for "This dataset" too), else the frames A draws
        # from when the selector returns no pool.
        compare_words_pool = (
            compare_pool.words if compare_pool is not None else words_filtered
        )
        compare_fixations_pool = (
            compare_pool.fixations if compare_pool is not None else fixations_filtered
        )
        if compare_participant is not None and compare_trial is not None:
            compare_parent_words = extract_trial(
                compare_words_pool, compare_participant, compare_trial
            )
            compare_parent_fixations = extract_trial(
                compare_fixations_pool, compare_participant, compare_trial
            )
            compare_samples = (
                compare_source.raw_gaze
                if compare_source is not None
                else raw_gaze_all
                if raw_gaze_all is not None
                else raw_gaze
            )
            compare_screens, compare_screen_error = _screen_catalog_status(
                compare_parent_words,
                compare_parent_fixations,
                extract_trial(compare_samples, compare_participant, compare_trial)
                if compare_samples is not None and SCREEN_ID in compare_samples
                else None,
            )
            if compare_screen_error:
                plot_notes_slot.warning(compare_screen_error)
                compare_participant = compare_trial = None
        else:
            compare_screens = pd.DataFrame()
        selected_compare_screen = _render_screen_navigator(
            compare_screens, key_prefix="single_compare", host=screen_cells.get("b")
        )
        if selected_compare_screen is not None:
            compare_screen_canvas = screen_canvas_size(
                screen_rows(compare_screens, selected_compare_screen)
            )
    else:
        # Compare off loads no second dataset — stop the one an
        # earlier run left loading for B — and keeps no copy of B's pool.
        _abandon_compare_task()
        _forget_compare_narrowing()
        compare_words_pool = words_filtered
        compare_fixations_pool = fixations_filtered

    global_raw_toggle = bool(st.session_state.get("global_show_raw_gaze"))
    draw_compare_raw_gaze = global_raw_toggle and not animate
    compare_meta = _build_compare_meta(
        compare_words_pool,
        compare_fixations_pool,
        selected_participant,
        selected_trial,
        compare_participant,
        compare_trial,
        selected_compare_screen,
        source=compare_source,
        # A's corpus, so a cross-dataset pair names both sides.
        primary_dataset=current_dataset_name(),
        # Only the static comparison can draw B's samples. The *unfiltered*
        # samples: B's pool ignores A's filters, so A's `raw_gaze` can lack B.
        raw_gaze=(raw_gaze if raw_gaze_all is None else raw_gaze_all)
        if not animate
        else None,
        include_raw_gaze=not animate,
        dataset_canvas=dataset_canvas,
        screen_canvas=compare_screen_canvas,
        elapsed_axis=elapsed_axis,
    )
    comparing = compare_meta is not None
    compare_comparable, compare_setup_note = _compare_setups(
        compare_meta, trial_words, trial_fixations, canvas_width, canvas_height
    )
    rail_comparing = comparing and (
        not animate or (compare_comparable and not compare_meta["fixations"].empty)
    )
    st.session_state["_resolved_comparing"] = rail_comparing
    st.session_state["_resolved_animating"] = bool(animate)

    # Render the rail (plot controls) before the figure so it sees the
    # resolved Animate / Compare / viz settings; its right-side position is fixed
    # by the column split regardless of render order.
    with rail:
        # Modes, presets, palette and layers are one control system, under one
        # heading. The scoped reset sits at the foot of the rail (see the end of
        # this block), not beside the heading: the rail is ~150px wide inside,
        # which is not enough for a heading and a trigger side by side at any
        # ordinary window size.
        with st.container(key="plot_controls_header"):
            st.markdown(f"## {ICONS['plot_controls']} Plot controls")
        # Reserve the first block before resolving the detailed controls. Its
        # tiles need the defaults seeded by render_plot_controls further below.
        view_host = rail.container(key="rail_view_controls")
        modes = rail.container(key="tour_grp_view_modes")
        with modes:
            compare_host = modes.container(key="rail_compare")
            anim_disabled = not animate
            anim_gate = (
                ""
                if animate
                else f"{ICONS['warning']} This trial has no fixations to animate."
                if animate_requested
                else f"{ICONS['warning']} Turn on **Animation** to change playback."
            )
            animation_row = ui_mode.advanced_only(modes, "rail_animation").container(
                horizontal=True,
                wrap=False,
                vertical_alignment="center",
                gap=None,
                key="split_mode_animation",
            )
            animation_row.toggle(
                f"{ICONS['animate']} Animation",
                key=SINGLE_ANIMATE,
                persist_state="session",
                wrap=True,
                on_change=on_animation_change,
                help="Switch between the replay and the current static view.",
            )
            animation_settings = animation_row.popover(
                "Animation settings",
                width="content",
                key="plot_menu_animation",
                on_change=plot_popover_on_change(),
                help="Animation settings. Adjust playback speed, autoplay and frame timing.",
            )
            with animation_settings, _popover_rows("animation"):
                st.session_state.setdefault(
                    "single_playback_speed", _ANIM_DEFAULT_SPEED
                )
                if anim_gate:
                    st.caption(anim_gate)
                playback_speed = _labeled(
                    st,
                    "select_slider",
                    "Playback speed",
                    display="Speed",
                    options=_ANIM_SPEED_OPTIONS,
                    format_func=lambda x: _ANIM_SPEED_LABELS[
                        _ANIM_SPEED_OPTIONS.index(x)
                    ],
                    key="single_playback_speed",
                    persist_state="session",
                    disabled=anim_disabled,
                    help="At ×1 the replay follows the reading’s fixation timings.",
                )
                _check_row(
                    "Autoplay",
                    check_label="Play on load",
                    check_share=0.76,
                    key="global_anim_autoplay",
                    persist_state="session",
                    disabled=anim_disabled,
                    help="Start the replay when you open the reading.",
                )
                # The duration depends on both readings when comparing.
                anim_timing_slot = st.container() if animate else None

                # The frame grid is a real tradeoff — smoothness against frame
                # count, which is what export size and render time are made of —
                # so the user sets it, and `_render_anim_info` says when the
                # frame limit coarsened it.
                def _apply_anim_quality() -> None:
                    quality = st.session_state.get("global_anim_quality")
                    if quality == "Custom":
                        st.session_state["plot_detail_frame_timing"] = True
                    elif quality in _ANIM_QUALITY_PRESETS:
                        interval, limit = _ANIM_QUALITY_PRESETS[quality]
                        write_through("global_anim_grid_step_ms", interval)
                        write_through("global_anim_max_frames", limit)

                current_grid = (
                    int(st.session_state.get("global_anim_grid_step_ms", 100)),
                    int(st.session_state.get("global_anim_max_frames", 360)),
                )
                matched_quality = next(
                    (
                        name
                        for name, values in _ANIM_QUALITY_PRESETS.items()
                        if values == current_grid
                    ),
                    None,
                )
                # Picking Custom on the smoothness control has to be
                # "sticky" even while the grid still equals a preset
                # exactly (the state right after switching, before
                # either slider is touched) — otherwise this re-inference
                # would snap it straight back to that preset's name. Only
                # infer a preset when the mode isn't already Custom; a
                # grid matching no preset is unambiguous either way.
                previous_quality = st.session_state.get("global_anim_quality")
                if matched_quality is None:
                    st.session_state["global_anim_quality"] = "Custom"
                elif previous_quality != "Custom":
                    st.session_state["global_anim_quality"] = matched_quality
                presets_help = " ".join(
                    f"{name} uses a {step} ms interval with up to {cap} frames."
                    for name, (step, cap) in _ANIM_QUALITY_PRESETS.items()
                )
                _labeled(
                    st,
                    "selectbox",
                    "Animation smoothness",
                    display="Smoothness",
                    options=[*_ANIM_QUALITY_PRESETS, "Custom"],
                    key="global_anim_quality",
                    persist_state="session",
                    on_change=_apply_anim_quality,
                    disabled=anim_disabled,
                    help="More frames give smoother motion and take longer to build. "
                    + presets_help,
                )
                anim_frames_slot = st.container() if animate else None

                def _mark_anim_quality_custom() -> None:
                    write_through("global_anim_quality", "Custom")

                # Both values remain mounted inside the disclosure, including
                # when a preset changes them or a settings file restores them.
                with detail_section(
                    "Frame timing",
                    key="plot_detail_frame_timing",
                    expanded=st.session_state["global_anim_quality"] == "Custom",
                    track=True,
                ):
                    _numeric_slider(
                        st,
                        "Frame interval",
                        key="global_anim_grid_step_ms",
                        persist_state="session",
                        min_value=20,
                        max_value=500,
                        step=10,
                        slider_format="%d ms",
                        number_format="%d",
                        on_change=_mark_anim_quality_custom,
                        disabled=anim_disabled,
                        label_left=True,
                        help="Milliseconds of reading time between frames.",
                    )
                    _numeric_slider(
                        st,
                        "Frame limit",
                        key="global_anim_max_frames",
                        persist_state="session",
                        min_value=30,
                        max_value=2000,
                        step=10,
                        slider_format="%d frames",
                        number_format="%d",
                        on_change=_mark_anim_quality_custom,
                        disabled=anim_disabled,
                        label_left=True,
                        help="Longer readings use a wider frame interval to fit this limit.",
                    )
            with compare_host.container(
                horizontal=True,
                wrap=False,
                vertical_alignment="center",
                gap=None,
                key="split_mode_compare",
            ):
                # This key is wire format (`?compare=` turns it on), so it
                # is seeded rather than given a `value=`: an explicit default fights
                # the deep link the same way it would fight a restored config.
                compare_unavailable = (
                    not animate
                    and not st.session_state[SINGLE_COMPARE_TOGGLE]
                    and static_plot_view() == "illustration"
                )
                if compare_unavailable:
                    # On returning to an illustration, disabling the widget would
                    # discard the just-received click that switched comparison off.
                    st.session_state[SINGLE_COMPARE_TOGGLE] = False
                st.toggle(
                    f"{ICONS['compare']} Compare readings",
                    key=SINGLE_COMPARE_TOGGLE,
                    persist_state="session",
                    wrap=True,
                    disabled=compare_unavailable,
                    help="Choose Scanpath, Animation or Heatmap to compare readings."
                    if compare_unavailable
                    else "Add a second scanpath to the figure, overlaid or in a separate panel.",
                )
                cmp_disabled = not comparing
                if not compare_requested:
                    cmp_gate = f"{ICONS['warning']} Turn on **Compare readings** to change these."
                elif not trial_has_fixations:
                    cmp_gate = (
                        f"{ICONS['warning']} This trial has no fixations to compare."
                    )
                elif not comparing:
                    cmp_gate = (
                        f"{ICONS['warning']} Choose a second reading above the plot."
                    )
                else:
                    cmp_gate = ""
                with (
                    st.popover(
                        "Compare settings",
                        width="content",
                        key="split_mode_compare_popover",
                        on_change=plot_popover_on_change(),
                        help="Compare settings. "
                        + (
                            "Replay scanpath B in step with A."
                            if animate
                            else "Overlay another trial's scanpath or view them "
                            "side by side."
                        ),
                    ),
                    _popover_rows("compare"),
                ):
                    # Animate does not hide this block: hidden, it would read
                    # as "Compare has almost no settings" and hide one control
                    # (Stimulus from) that a co-replay honours perfectly
                    # well. Same contract as the two ▾ triggers
                    # themselves: what a mode offers stays on screen, and only
                    # what genuinely does not apply goes grey, with the reason
                    # in its tooltip.
                    if cmp_gate:
                        st.caption(cmp_gate)
                    layout_gate = cmp_gate or (
                        f"{ICONS['warning']} An animated comparison is always "
                        "an overlay."
                        if animate
                        else ""
                    )
                    # Seed so the control shows "Overlay" selected by default
                    # (the body reads this key to resolve compare_layout).
                    st.session_state.setdefault(SINGLE_COMPARE_LAYOUT, "Overlay")
                    chart_layout = not animate and (
                        st.session_state.get("global_x_field", "x"),
                        st.session_state.get("global_y_field", "y"),
                    ) != ("x", "y")
                    layout_key = SINGLE_COMPARE_LAYOUT
                    choices = ["Overlay", "Side by side", "Stacked"]
                    callback = {}
                    if chart_layout:
                        choices = choices[1:]
                        saved = st.session_state[SINGLE_COMPARE_LAYOUT]
                        layout_key = shadow_widget_key(
                            "chart_compare_layout",
                            saved if saved in choices else choices[0],
                        )

                        def choose_chart_layout():
                            write_through(
                                SINGLE_COMPARE_LAYOUT, st.session_state[layout_key]
                            )

                        callback["on_change"] = choose_chart_layout

                    _labeled(
                        st,
                        "segmented_control",
                        "Layout",
                        options=choices,
                        required=True,
                        format_func=lambda value: (
                            "Top & bottom" if value == "Stacked" else value
                        ),
                        # The three segments need the room a narrower title
                        # column leaves; at the popovers' width they wrap.
                        label_width=0.2,
                        width="stretch",
                        key=layout_key,
                        **callback,
                        persist_state="session",
                        disabled=cmp_disabled or animate,
                        help=_gated_help(
                            "Overlay both scanpaths, or give each its own panel.",
                            layout_gate,
                        ),
                    )
                    # "Resolve, don't rewrite": the stored layout is untouched
                    # while Animate holds the figure on overlay, so say where
                    # the user's own choice went instead of letting a greyed
                    # control show a layout the plot isn't in.
                    stored_layout = st.session_state.get(SINGLE_COMPARE_LAYOUT)
                    if animate and stored_layout != "Overlay":
                        st.caption(
                            "Overlaid in **Animation**. Your layout "
                            "comes back when you turn it off."
                        )
                    # Overlay pools both trials into one axis range, so
                    # across datasets it is allowed only when both were
                    # recorded on the same screen size. This note
                    # stays generic. The caption under the
                    # figure has the specific answer, and the resolve happens
                    # there too, *without* rewriting the key, so a
                    # same-dataset pair gets the user's Overlay back.
                    overlaid = animate or (
                        stored_layout == "Overlay" and not chart_layout
                    )
                    if _compare_source_name() is not None and overlaid:
                        st.caption(
                            "Across datasets, Overlay needs both to be recorded on "
                            "the same screen size."
                        )
                    # Two datasets' AOIs coincide only when the text
                    # is identical, so an overlay can otherwise stack two
                    # offset sets of rectangles. Overlay-only — each panel of
                    # a split layout owns its own stimulus, and dropping one
                    # would just blank half the figure, so there it greys. A
                    # co-replay *is* an overlay, and `make_scanpath_animation`
                    # reads `compare_stimulus` (it is what stops a
                    # cross-dataset replay running B's trace over A's text),
                    # so this one is live under Animate rather than greyed.
                    st.session_state.setdefault(SINGLE_COMPARE_STIMULUS, "Both")
                    _labeled(
                        st,
                        "segmented_control",
                        "Stimulus from",
                        display="Overlay text",
                        options=["Both", "A", "B"],
                        key=SINGLE_COMPARE_STIMULUS,
                        persist_state="session",
                        disabled=cmp_disabled or not overlaid,
                        help=_gated_help(
                            "Which trial's word boxes and text an overlay draws."
                            + (
                                " A replay draws one stimulus layer, so "
                                "**Both** means A's."
                                if animate
                                else ""
                            ),
                            cmp_gate,
                        ),
                    )
                    _check_row(
                        "Trial arrows",
                        key=COMPARE_STEP_LINK_KEY,
                        persist_state="session",
                        check_label="Step A and B together",
                        check_share=0.9,
                        disabled=cmp_disabled,
                        help="Move each trial picker by one reading when you use the arrows.",
                    )
                    # Both label previews use the fixation windows selected below.
                    compare_labels = detail_section(
                        "Reading labels", key="plot_detail_compare_labels", track=True
                    )
        # The selected trial's `combos` row, masked at most **once**
        # per rerun and only if something asks — the rail's title / caption
        # fields, the snippet publish, the static branch's
        # `_apply_title_caption` and two inside `_render_comparison_figure`.
        # Its only consumer is the title/caption pattern, unset by default,
        # whose renderers early-return before reading the row, so the thunk
        # keeps the default path free of the scan (~3.9 ms on a 60k-row
        # `combos`, on every widget toggle).
        _combo_row_memo: list = []

        def primary_combo_row() -> dict | None:
            if not _combo_row_memo:
                _combo_row_memo.append(
                    _combo_row(combos, selected_participant, selected_trial)
                )
            return _combo_row_memo[0]

        # The visualization controls render into this rail (host=rail) so they
        # sit beside the plot they drive.
        viz_settings = render_plot_controls(
            fixations_filtered,
            base_font_size,
            host=rail,
            view_host=view_host,
            # B's fixation window is rendered into its tab after the rail.
            slots=rail_slots,
            has_raw_gaze=trial_has_raw_gaze
            or (rail_comparing and not compare_meta["raw_gaze"].empty),
            compare_meta=compare_meta if rail_comparing else None,
            has_stimulus_image=has_stimulus_image,
            has_fixations=trial_has_fixations,
            has_words=chart_axes.has_word_boxes(trial_words),
            words=words_filtered,
            # The selected trial's fixations size the fixation-index window
            # slider (its max is this trial's fixation count).
            fix_range_fixations=trial_fixations,
            trial_samples=trial_raw_gaze,
            raw_gaze=raw_gaze,
            # The canvas / text panel (monitor geometry, fonts, text colour,
            # background) renders inside the rail's group order. `app.main`
            # passes it in already bound to the frames + data source, since
            # those are app-side concerns.
            canvas_renderer=canvas_renderer,
            # The title / caption fields the figure renders with — its
            # fixations within the fixation window, as `{n_fixations}` counts.
            title_fields=lambda settings: _title_caption_fields(
                {
                    **settings,
                    "caption_raw_gaze": bool(settings.get("show_raw_gaze"))
                    and not animate
                    and chart_axes.drawable_raw_samples(
                        (
                            settings.get("x_field") or "x",
                            settings.get("y_field") or "y",
                        ),
                        trial_raw_gaze,
                        trial_fixations,
                    ),
                },
                trial_words,
                _slice_fix_range(trial_fixations, settings.get("fix_index_range")),
                selected_participant,
                selected_trial,
                combo_row=primary_combo_row,
            ),
            # A trial without fixations draws its static view.
            animating=bool(animate),
        )
        # The scoped reset closes the rail, below every control it
        # resets, rather than sharing the heading row. It is last in creation
        # order, so it lands at the foot of the rail's own scroll area.
        # Full-only: Essentials' View tiles are its way back to a preset.
        with ui_mode.advanced_only(rail, "rail_reset"):
            plot_footer = st.container(key="plot_reset_footer")

    # Essentials hides the controls that Full sets, but they keep shaping the
    # figure; say which are in play. The container is drawn on every run, in
    # both modes and empty when there is nothing to say, so the notes below it
    # never change position.
    ui_mode.render_hidden_settings_note(
        plot_notes_slot.container(),
        ui_mode.hidden_settings_reasons(
            narrowed=len(combos) < len(combos_all),
            sorted_=trial_sort_is_set("single"),
            comparing=comparing,
            custom_view=st.session_state.get("_custom_plot_in_use", False),
            axes=(viz_settings.get("x_field", "x"), viz_settings.get("y_field", "y"))
            if not animate
            else ("x", "y"),
        )
        if ui_mode.is_simple()
        else [],
    )

    # A co-animation always overlays the readings on one clock. The static
    # layout is resolved against both screens below.
    if animate:
        requested_layout = "overlay"
    else:
        requested_layout = {
            "Overlay": "overlay",
            "Side by side": "side_by_side",
            "Stacked": "stacked",
        }.get(st.session_state.get(SINGLE_COMPARE_LAYOUT), "overlay")
    fields = (viz_settings.get("x_field", "x"), viz_settings.get("y_field", "y"))
    if animate:
        fields = ("x", "y")
    effective_show_raw_gaze = global_raw_toggle and chart_axes.raw_axes_available(
        fields, trial_raw_gaze
    )
    figure_settings = _build_figure_settings(viz_settings, effective_show_raw_gaze)
    figure_raw_gaze = trial_raw_gaze if trial_has_raw_gaze else None
    figure_settings.update(
        stimulus_image_settings(
            viz_settings,
            (canvas_width, canvas_height),
            (trial_image_path, trial_image_size, trial_image_origin)
            if has_stimulus_image
            else None,
        )
    )
    # Carried into both the live figure and the bulk export so exported plots are
    # sized identically to what's on screen (true-to-scale reading text).
    figure_settings["line_spacing"] = line_spacing
    figure_settings["scale_text_to_boxes"] = scale_text_to_boxes
    x_field = viz_settings["x_field"]
    y_field = viz_settings["y_field"]

    rail_slots["view_tiles"](comparing=comparing)
    # A conflicting screen mapping blocks the figure. Keep the controls and
    # B's picker available so the user can leave Compare or select another B.
    if compare_screen_error:
        return
    # Compare draws raw gaze too — each reading's own samples, so the
    # layer is on when either reading has some.
    compare_raw_gaze = (
        compare_meta["raw_gaze"] if compare_meta is not None else pd.DataFrame()
    )
    compare_shows_raw_gaze = bool(
        comparing
        and draw_compare_raw_gaze
        and (trial_has_raw_gaze or not compare_raw_gaze.empty)
    )
    viz_settings["caption_raw_gaze"] = (
        not animate
        and global_raw_toggle
        and (
            chart_axes.drawable_raw_samples(fields, trial_raw_gaze, trial_fixations)
            or (
                compare_shows_raw_gaze
                and chart_axes.drawable_raw_samples(
                    fields, compare_raw_gaze, compare_meta["fixations"]
                )
            )
        )
    )
    if compare_shows_raw_gaze:
        # Never while animating: `show_raw_gaze` is part of the replay's cache
        # key, and the replay draws no raw gaze.
        figure_settings["show_raw_gaze"] = True
    # Publish B for the Share link, alongside A above. Always the
    # *real* ids, never the namespaced ones — a link names readers as their own
    # corpus does. `source` is None for a same-dataset comparison.
    share_selection = st.session_state.get("_share_selection")
    if isinstance(share_selection, dict):
        if comparing and compare_meta is not None:
            from .dataset_identity import dataset_share_id

            source = compare_meta.get("dataset")
            source_id = dataset_share_id(st.session_state, source)
            share_selection["compare"] = {
                "participant_id": compare_meta["raw_participant"],
                "trial_id": compare_meta["trial"],
                "source": source,
                **(
                    {"source_id": source_id, "source_name": _dataset_label(source)}
                    if source_id
                    else {}
                ),
                # B's own screen (`cmp_screen=`), from its own navigator.
                "screen_id": selected_compare_screen,
            }
        else:
            share_selection.pop("compare", None)
    # From here on, B's *figure* id is the namespaced one — the merged
    # frames below carry it, and `make_comparison_figure` slices by exactly that.
    figure_compare_participant = (
        compare_meta["participant"] if compare_meta else compare_participant
    )
    cross_dataset = bool(compare_meta and compare_meta.get("dataset"))
    compare_fix = compare_meta["fixations"] if compare_meta else pd.DataFrame()
    # B's picker and frames are now resolved, so its filter tab can show
    # the fixation range for the reading actually on screen.
    if rail_comparing:
        render_compare_filters(
            rail_slots.get("compare_filter"),
            compare_fix,
            status=rail_slots.get("compare_filter_status"),
            words=compare_meta["words"],
        )
    elif "compare_filter" in rail_slots:
        rail_slots["compare_filter"].caption(
            "Choose a second reading above the plot to filter its fixations."
        )
    # Record the completed edit after both readings and their fixation windows
    # have resolved, in the slot already placed at the foot of the rail.
    render_viz_reset(plot_footer)
    # Resolve, don't rewrite: `single_compare_layout` is left alone,
    # so switching back to a same-dataset pair restores the user's Overlay.
    compare_layout = requested_layout
    chart_comparison = comparing and not animate and fields != ("x", "y")
    if compare_layout == "overlay" and (chart_comparison or not compare_comparable):
        compare_layout = "side_by_side"
    # Widget label -> the wire/settings vocabulary the builders take.
    compare_stimulus = {"Both": "both", "A": "a", "B": "b"}.get(
        str(st.session_state.get(SINGLE_COMPARE_STIMULUS) or "Both"), "both"
    )

    # Fixation-index window: the frames that feed the figure / animation
    # are sliced to the chosen range; the full frames still drive the chips,
    # panels and exports. A None range leaves the frames untouched.
    fix_range = viz_settings.get("fix_index_range")
    # The trial's own ``(first, last)`` fixation index. Computed *above* the
    # slice rather than after it (a) so the untouched slider — which sits at
    # exactly this range — skips the mask entirely, and (b) because the Share
    # link's writer needs what "the whole trial" is before it can tell a real
    # window from the slider's default. Published rather than re-derived in
    # `url_state`, because *this* is the frame the slider was bounded by: on a
    # multipart trial ``order_in_trial`` is parent-global, so a later screen's
    # full range starts at 509, not 1, and a second derivation from the
    # unsliced trial would disagree.
    full_fix_range = None
    if not trial_fixations.empty and "order_in_trial" in trial_fixations.columns:
        order = pd.to_numeric(
            trial_fixations["order_in_trial"], errors="coerce"
        ).dropna()
        if not order.empty:
            full_fix_range = (int(order.min()), int(order.max()))
    if full_fix_range is not None:
        selection = st.session_state.get("_share_selection")
        if isinstance(selection, dict):
            selection["full_fix_range"] = full_fix_range
    windowed = fix_range is not None and (
        full_fix_range is None or tuple(fix_range) != full_fix_range
    )
    fig_fixations = _slice_fix_range(trial_fixations, fix_range if windowed else None)
    # `fix_range` is A's own window: its bounds and default both come from A's
    # fixation count (`controls._render_fix_range_slider`). B is never windowed
    # by A's control: the window defaults to `(1, len(A's fixations))` the
    # instant A has ≥2 fixations, so slicing B by it would silently drop the
    # trailing fixations of any B with MORE fixations than A, whether or not
    # the slider was ever touched.
    #
    # B has a window of its own (`single_compare_fix_range`), bounded by
    # B's fixations and applied on exactly A's terms — its full range published
    # beside A's, so the Share link can tell a real window from the default.
    fig_compare_fix = compare_fix
    # What the snippet names as B's window: B's own when it has one — and B's
    # full range when only A is windowed, because the API's `fix_index_range`
    # windows *both* scanpaths where the app's A slider never cuts B.
    snippet_window_b = None
    # What the Illustration disclosure is told about B's window.
    window_b = full_b = None
    if comparing and not compare_fix.empty and "order_in_trial" in compare_fix:
        order_b = pd.to_numeric(compare_fix["order_in_trial"], errors="coerce").dropna()
        full_b = (int(order_b.min()), int(order_b.max())) if not order_b.empty else None
        selection = st.session_state.get("_share_selection")
        if full_b is not None and isinstance(selection, dict):
            selection["compare_full_fix_range"] = full_b
        window_b = st.session_state.get("single_compare_fix_range")
        if window_b is not None and (full_b is None or tuple(window_b) != full_b):
            fig_compare_fix = _slice_fix_range(compare_fix, window_b)
            snippet_window_b = tuple(int(v) for v in window_b)
        elif windowed and full_b is not None:
            snippet_window_b = full_b
    # The dual animation takes B's flags as a setting (the static comparison
    # reads them off B's style); set only while comparing, so a single-trial
    # figure's cache key is unchanged.
    if comparing:
        figure_settings["fixation_flags_b"] = compare_b_filters()["fixation_flags"]
    source_names = [st.session_state.get("data_source_choice")]
    if comparing and compare_source is not None:
        source_names.append(compare_source.name)
    detected_reasons = illustration_reasons(
        {
            **viz_settings,
            # The layers as the figure draws them, under the builders'
            # names — the snap and the arcs count only on a layer that is on.
            "show_fixations": figure_settings["show_fixations"],
            "show_saccades": figure_settings["show_saccades"],
            "playback_speed": playback_speed if animate else 1.0,
        },
        # …and only on the static figure, the one that draws them.
        static=not (animate or comparing),
        data_source=st.session_state.get("_active_data_source"),
        synthetic=any(
            source in (SYNTHETIC_CHOICE, MANUAL_SAMPLE_CHOICE, AUTHOR_CHOICE)
            or st.session_state.get("_datasets", {}).get(source, {}).get("authoring")
            for source in source_names
        ),
        fix_index_range=fix_range,
        full_fixation_range=full_fix_range,
        # B's own flags and window disclose as A's do.
        fixation_flags_b=figure_settings.get("fixation_flags_b"),
        fix_index_range_b=window_b,
        full_fixation_range_b=full_b,
    )
    label_reasons = resolve_label_reasons(
        viz_settings.get("illustration_label", "Auto"), detected_reasons
    )
    viz_settings["illustration_reasons"] = label_reasons
    figure_settings["illustration_reasons"] = label_reasons
    # No label drawn: the text is a no-op, so it must not bust the figure cache.
    if not label_reasons:
        figure_settings["illustration_text"] = ""
    render_settings = FigureSettings.from_mapping(
        figure_settings,
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
        base_font_size=int(base_font_size),
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
        # The dual animation draws ONE stimulus layer, so "B" is what
        # stops a cross-dataset co-animation running B's trace over A's text.
        # The comparison branch re-applies this through `with_overrides`.
        compare_stimulus=compare_stimulus,
        # The figure's text names columns as the dataset does. A's
        # names, Compare included — the rail that picks the columns is A's.
        column_labels=active_figure_labels(
            st.session_state,
            words=trial_words.columns,
            fixations=trial_fixations.columns,
            raw_gaze=trial_raw_gaze.columns,
        ),
        # A category's colour comes from every label in the dataset — both
        # datasets' for a cross-dataset Compare — so it is the same in every
        # trial, the replay, Compare and the bulk export.
        color_categories=_dataset_color_categories(
            figure_settings.get("color_by"),
            fixations_all,
            compare_source.fixations
            if comparing and cross_dataset and compare_source is not None
            else None,
        ),
    )

    # Drift correction — hoisted ABOVE the render-mode split, so the two
    # Drift-correction controls apply on ALL THREE paths. Each scanpath is
    # corrected against its OWN words frame, on the already-windowed fixations
    # (so the algorithm sees exactly what is drawn). What each builder can then
    # do with it:
    #   • static     — snapped y + colour-by-line + optional original→corrected
    #                  connectors (it is the only builder with a connector layer);
    #   • animation  — snapped y + colour-by-line on the single replay. No
    #                  connectors: the replay reveals one growing trail, and a
    #                  full-length static "original position" layer standing there
    #                  from frame zero would misread as part of the scanpath.
    #   • comparison — snapped y for both scanpaths; correction does not force
    #                  colour-by-line there (the rail's choice stands) and there
    #                  is no connector layer, so correction is the whole of it.
    # "Off" (the default) is a genuine no-op — `_drift_corrected` hands back the
    # same frame object, so no path changes and no figure cache entry is busted.
    align_algorithm = viz_settings.get("align_algorithm", "Off")
    plot_fixations = _drift_corrected(fig_fixations, trial_words, align_algorithm)
    drift_corrected_primary = plot_fixations is not fig_fixations
    plot_compare_fix = fig_compare_fix
    if comparing and compare_meta is not None:
        plot_compare_fix = _drift_corrected(
            fig_compare_fix, compare_meta["words"], align_algorithm
        )
    _render_compare_reading_labels(
        compare_labels,
        [
            (
                selected_participant,
                selected_trial,
                trial_words,
                plot_fixations,
                current_dataset_name(),
            ),
            (
                compare_meta["raw_participant"] if comparing else None,
                compare_trial,
                compare_meta["words"] if comparing else None,
                plot_compare_fix,
                _compare_dataset_name(compare_meta),
            ),
        ],
        disabled=not comparing,
    )
    # `make_comparison_figure` pulls exactly the two selected trials out of the
    # frame it is handed (its shared colour range included), so a frame holding
    # just those two corrected scanpaths is equivalent to patching the whole
    # filtered corpus — and far cheaper. Untouched when correction is off.
    # Two corpora rarely ship the same columns, and a bare concat of
    # disjoint frames warns and churns dtypes — align onto the union first. The
    # shared numeric set feeds the metric gate below.
    shared_numeric: frozenset[str] | None = None
    self_compare_figure_id: str | None = None
    cmp_raw_gaze: pd.DataFrame | None = None
    if comparing and compare_meta is not None:
        chart_fix_a, chart_raw_a = chart_axes.comparison_coordinates(
            plot_fixations, trial_raw_gaze, fields
        )
        chart_fix_b, chart_raw_b = chart_axes.comparison_coordinates(
            plot_compare_fix, compare_raw_gaze, fields
        )
        words_a, words_b, _ = _align_compare_columns(trial_words, compare_meta["words"])
        fix_a, fix_b, shared_fix = _align_compare_columns(chart_fix_a, chart_fix_b)
        if not cross_dataset and (
            str(figure_compare_participant),
            str(compare_trial),
        ) == (str(selected_participant), str(selected_trial)):
            # B is A's own trial. Rename B's copy apart for the figure
            # only — `make_comparison_figure` slices by (participant, trial).
            words_b = separate_self_compare(words_b, selected_participant)
            fix_b = separate_self_compare(fix_b, selected_participant)
            chart_raw_b = separate_self_compare(chart_raw_b, selected_participant)
            self_compare_figure_id = self_compare_participant(selected_participant)
        cmp_words = pd.concat([words_a, words_b])
        cmp_fixations = pd.concat([fix_a, fix_b])
        if compare_shows_raw_gaze:
            cmp_raw_gaze = pd.concat(
                _align_compare_columns(chart_raw_a, chart_raw_b)[:2]
            )
        if cross_dataset:
            shared_numeric = shared_fix
    else:
        cmp_words = trial_words
        cmp_fixations = plot_fixations

    # Condition chips above the plot — configurable via the ✏️ Edit chips picker
    # (`trial_chip_fields`); one column per chosen field. When comparing, both
    # readings share one A/B table, which puts B's value directly under A's
    # rather than at another offset on another line.
    with chips_slot:
        # The ✏️ menu that picks the fields — and hides the row — is
        # at the end of A's trial row (`_render_chip_menu`), so the table has
        # the plot's whole width.
        chip_fields = st.session_state.get("trial_chip_fields") or []
        if st.session_state.get(SINGLE_SHOW_CHIPS, True):
            if comparing and compare_meta:
                # B's gaze-sample count, only while that chip is shown. A
                # cross-dataset B counts its own dataset's samples; otherwise
                # read off the *unfiltered* samples: B's pool
                # ignores A's filters, so A's `raw_gaze` can lack B.
                b_samples = (
                    compare_source.raw_gaze
                    if compare_source is not None
                    else raw_gaze
                    if raw_gaze_all is None
                    else raw_gaze_all
                )
                b_gaze_samples = (
                    _c_gaze_sample_count(
                        b_samples,
                        frame_fingerprint(b_samples),
                        compare_participant,
                        compare_trial,
                        selected_compare_screen,
                    )
                    if "@gaze_sample_count" in chip_fields
                    and b_samples is not None
                    and not b_samples.empty
                    else None
                )
                _render_compare_chip_table(
                    chip_fields,
                    a=ChipReading(
                        words=trial_words,
                        fixations=trial_fixations,
                        raw_gaze=trial_raw_gaze,
                        participant=selected_participant,
                        trial_shown=trial_id_shown(
                            selected_trial,
                            trial_fixations,
                            trial_words,
                            composite_cols=st.session_state.get(
                                "_composite_trial_columns"
                            )
                            or (),
                        ),
                    ),
                    b=ChipReading(
                        words=compare_meta["words"],
                        fixations=compare_meta["fixations"],
                        gaze_samples=b_gaze_samples,
                        participant=compare_participant,
                        names=(
                            across_tables(compare_source.column_names)
                            if compare_source is not None
                            else None
                        ),
                        trial_shown=trial_id_shown(
                            compare_trial,
                            compare_meta["fixations"],
                            compare_meta["words"],
                            participant_id=compare_meta.get("raw_participant"),
                        ),
                    ),
                )
            else:
                _render_trial_condition_chips(
                    trial_words,
                    trial_fixations,
                    selected_participant,
                    chip_fields,
                    trial_raw_gaze=trial_raw_gaze,
                )

    displayed_fig = None
    # Which `_render_true_scale_chart` drew it — the Export subtab's PNG
    # and SVG are saved from that plot in the browser.
    displayed_plot_key = "single"
    save_slug = f"{selected_participant}__{selected_trial}"
    anim_file_stem = None
    anim_view = None
    # Use the windowed second scanpath: a window that empties B falls back to a
    # single-trial animation (and info box). A co-animation is an overlay on one
    # clock, so it needs one coordinate space — which is the same question the
    # overlay layout asks, so it is gated on the same predicate.
    dual_anim = (
        animate and comparing and not fig_compare_fix.empty and compare_comparable
    )

    # Publish the state the 🔗 Share subtab writes its reproduction
    # snippet from — the same `figure_settings` the builders below consume,
    # the same title/caption text `_apply_title_caption` will stamp on. Kept
    # above the three render branches so it is written whichever one draws,
    # and so an empty-fixations trial (which draws nothing) still has a
    # snippet for the settings on the rail.
    # The selected trial's `combos` row, masked at most **once** per rerun
    # and only if something asks. Four call sites want it — the snippet
    # publish just below, the static branch's `_apply_title_caption`, and two
    # inside `_render_comparison_figure` — at ~3.9 ms a mask on a 60k-row
    # `combos`, on every widget toggle. Its only
    # consumer is the title/caption pattern, unset by default, whose renderer
    # early-returns before reading the row, so the thunk is what keeps the
    # default path free of the scan entirely rather than merely down to one.
    _snippet_title, _snippet_caption = _rendered_title_caption(
        viz_settings,
        trial_words,
        plot_fixations,
        selected_participant,
        selected_trial,
        combo_row=primary_combo_row,
        # Every branch that draws overwrites this pair through
        # `_amend_snippet_title_caption`, so what is rendered here only survives
        # on the one path that draws nothing: animation on a trial with no
        # fixations. That path can still be *comparing*, and a `{…_b}`
        # placeholder left blank there is the same drift the amend exists to
        # stop — so B is named here too.
        compare_row=(
            {
                "dataset_name": _compare_dataset_name(compare_meta),
                "participant_id": compare_meta["raw_participant"],
                "trial_id": compare_meta["trial"],
            }
            if comparing and compare_meta is not None
            else None
        ),
    )
    snippet_kind = (
        "animation"
        if animate and not trial_fixations.empty
        else "comparison"
        if comparing
        else "static"
    )
    _publish_snippet_state(
        snippet_kind,
        figure_settings,
        viz_settings,
        participant=selected_participant,
        trial=selected_trial,
        screen=selected_screen,
        canvas=(canvas_width, canvas_height),
        base_font_size=base_font_size,
        font_family=font_family,
        title=_snippet_title,
        caption=_snippet_caption,
        playback_speed=playback_speed,
        full_fix_range=full_fix_range,
        fix_index_range_b=snippet_window_b,
        own_pages={"": trial_image} if trial_image is not None else None,
        compare=(
            CompareTarget(
                # The real ids, never the namespaced ones — a snippet
                # names readers the way their own corpus does, exactly as the
                # Share link does two blocks above.
                participant=str(compare_meta["raw_participant"]),
                trial=str(compare_meta["trial"]),
                # B's own screen, from its own navigator (`screen_b=`).
                screen=selected_compare_screen,
                layout=str(compare_layout),
                compare_stimulus=str(compare_stimulus)
                if compare_layout == "overlay"
                else "both",
                dataset=_dataset_label(compare_meta["dataset"])
                if compare_meta.get("dataset")
                else "",
                # B's own screen, which a second dataset's snippet
                # states (`setup_b=` / `--compare-canvas`).
                canvas=(
                    tuple(compare_meta["setup"].canvas)
                    if compare_meta.get("dataset")
                    and compare_meta.get("setup") is not None
                    else None
                ),
                # A second dataset's samples have no path the app can
                # name, so the snippet loads a placeholder for them.
                raw_gaze=(
                    ()
                    if compare_meta.get("dataset") and not compare_raw_gaze.empty
                    else None
                ),
                primary_raw_gaze=has_raw_gaze,
                # An uploaded B's column mapping, so the recipe reads B's
                # files as the app did, and what its add did that the
                # recipe cannot repeat.
                **(
                    _second_dataset_load(compare_meta["dataset"])
                    if compare_meta.get("dataset")
                    else {}
                ),
            )
            # An animation names B only when it co-animates B. Where it falls
            # back to A alone (B empty, or two screens), a snippet naming B
            # — `trial_b=` / `--compare-with` — would draw what the app doesn't.
            if comparing
            and compare_meta is not None
            and (snippet_kind != "animation" or dual_anim)
            else None
        ),
    )

    # The replay's timing and frame count, in their slots inside the rail's
    # Animate popover.
    if animate and not fig_fixations.empty and anim_timing_slot is not None:
        # Quote the same timeline the replay draws. The animation
        # builder drops Hide-mode fixation classes internally; apply the
        # shared classifier here too so the info cannot count hidden rows.
        info_fixations = _discard_flagged_fixations(
            fig_fixations,
            trial_words,
            viz_settings.get("fixation_flags"),
        )
        info_compare_fix = (
            _discard_flagged_fixations(
                fig_compare_fix,
                compare_meta["words"],
                figure_settings.get("fixation_flags_b"),
            )
            if dual_anim
            else None
        )
        _render_anim_info(
            anim_timing_slot,
            anim_frames_slot,
            info_fixations,
            info_compare_fix,
            selected_participant,
            selected_trial,
            compare_participant,
            compare_trial,
            playback_speed,
            grid_step_ms=viz_settings.get("anim_grid_step_ms"),
            max_frames=viz_settings.get("anim_max_frames"),
        )

    with plot_slot:
        if not animate:
            _abandon_animation_task()
        # The replay draws no raw gaze, and with no samples anywhere the rail
        # greys the switch, so neither has anything missing to say.
        any_samples = (
            trial_has_raw_gaze
            or (raw_gaze is not None and not raw_gaze.empty)
            or (comparing and not compare_raw_gaze.empty)
        )
        raw_gaze_missing = _raw_gaze_missing_note(
            global_raw_toggle and not animate and any_samples,
            trial_has_raw_gaze=trial_has_raw_gaze,
            comparing=comparing and not animate,
            compare_has_raw_gaze=not compare_raw_gaze.empty,
            screen=selected_screen is not None,
        )
        if raw_gaze_missing:
            plot_notes_slot.warning(raw_gaze_missing, icon=ICONS["warning"])
        no_fixations_note = _no_fixations_note(
            trial_has_fixations=trial_has_fixations,
            trial_has_raw_gaze=trial_has_raw_gaze,
            raw_gaze_shown=effective_show_raw_gaze,
            drawable_samples=trial_has_fixations
            or chart_axes.drawable_raw_samples(fields, trial_raw_gaze, trial_fixations),
            animate_requested=animate_requested,
            compare_requested=compare_requested,
        )
        if no_fixations_note:
            # Above the stage, like every other pre-figure note.
            plot_notes_slot.caption(no_fixations_note)
        window_note = _fix_window_note(
            fix_range if windowed else None,
            full_fix_range,
            window_b if comparing else None,
            full_b,
            essentials=ui_mode.is_simple(),
        )
        if window_note:
            plot_notes_slot.info(window_note, icon=ICONS["plot_filter"])
        if animate:
            replay_frames = (
                trial_words,
                plot_fixations,
                compare_meta["words"] if dual_anim else None,
                plot_compare_fix if dual_anim else None,
                selected_participant,
                selected_trial,
                compare_participant,
                compare_trial,
            )
            dataset_name_b = _compare_dataset_name(compare_meta)
            # Planned before the card opens, since the replay's task is
            # keyed by its frames — a setting that changes them cancels the
            # build under way — and the build below uses this very plan.
            replay_settings = render_settings
            if dual_anim and compare_stimulus == "b":
                # The replay's one page goes under the text it draws.
                replay_settings = render_settings.with_overrides(
                    **_page_under_text_b(render_settings, viz_settings, compare_meta)
                )
                _amend_snippet_own_pages({"": _own_page_b(viz_settings, compare_meta)})
            replay = _plan_replay(
                *replay_frames,
                settings=replay_settings,
                viz_settings=viz_settings,
                playback_speed=playback_speed,
                drift_corrected=drift_corrected_primary,
                dataset_name_b=dataset_name_b,
            )
            anim_task = _animation_task_key(
                selected_participant,
                selected_trial,
                selected_screen,
                compare=(
                    (compare_participant, compare_trial, selected_compare_screen)
                    if dual_anim
                    else None
                ),
                inputs=replay.key,
            )
            _claim_animation_task(anim_task)
            with loading.card(
                plot_loading_slot,
                key="single_anim",
                title="Building the animation",
                steps=("Building frames", "Preparing the player"),
                size=loading.plot_size(
                    "single_anim", canvas_width, canvas_height, animation=True
                ),
                task_key=anim_task,
                cancel=loading.Cancel(
                    "Show static plot", _cancel_animation, args=(anim_task,)
                ),
            ):
                anim_view, save_slug, anim_file_stem = _build_and_render_animation(
                    *replay_frames,
                    viz_settings=viz_settings,
                    plan=replay,
                    dataset_name_b=dataset_name_b,
                )
            _release_animation_task(anim_task)
            if comparing and not compare_comparable:
                # The replay has no split layout and shows A alone, so that is
                # what it says; the gate's reason (`compare_setup_note`) says
                # only why the pair cannot share a screen.
                st.warning(
                    "An animated comparison needs both trials on the same "
                    f"screen. {compare_setup_note} Only scanpath A is replayed.",
                    icon=ICONS["warning"],
                )
            elif comparing and compare_fix.empty:
                st.warning(
                    "Scanpath B has no fixations on its trial or screen, so only "
                    "scanpath A is replayed."
                )
            elif dual_anim:
                # A co-replay is always one coordinate space (`requested_layout`
                # is forced to overlay above), so the overlay wording applies.
                text_note = _different_texts_note(
                    _metadata_mod.trial_text_id(trial_fixations, trial_words),
                    _metadata_mod.trial_text_id(
                        compare_meta["fixations"], compare_meta["words"]
                    ),
                )
                if text_note:
                    st.warning(text_note, icon=ICONS["warning"])
        elif comparing:
            save_slug = (
                f"{selected_participant}__{selected_trial}__vs__"
                f"{compare_participant}__{compare_trial}"
            )
            displayed_plot_key = "compare"
            with loading.card(
                plot_loading_slot,
                key="compare",
                title="Drawing the comparison",
                size=loading.plot_size("compare", canvas_width, canvas_height),
            ):
                displayed_fig = _render_comparison_figure(
                    combos,
                    cmp_words,
                    cmp_fixations,
                    selected_participant,
                    selected_trial,
                    selected_text,
                    compare_participant,
                    compare_trial,
                    render_settings,
                    viz_settings,
                    layout=compare_layout,
                    compare_stimulus=compare_stimulus,
                    compare_meta=compare_meta,
                    shared_numeric=shared_numeric,
                    # The gate says why the pair cannot overlay; that it
                    # is drawn side by side instead is this surface's own
                    # resolve.
                    setup_note=(
                        f"{compare_setup_note} They are shown side by side instead."
                        if compare_layout != requested_layout and not chart_comparison
                        else compare_setup_note
                    ),
                    primary_combo_row=primary_combo_row,
                    download_name=f"scanpath_{_safe_filename(save_slug)}",
                    figure_participant_b=self_compare_figure_id
                    or figure_compare_participant,
                    raw_gaze=cmp_raw_gaze,
                )
        else:
            # The corrected frame (`plot_fixations`) was built above and is
            # shared with the animation + comparison paths. Only the static figure
            # can colour by line *and* draw the faint original→corrected
            # connectors, so those two overrides are derived here. The corrected
            # frame's snapped y already busts the figure cache; the extra kwargs
            # keep the key varying when only the algorithm/connectors change.
            extra_settings: dict = {}
            if drift_corrected_primary:
                extra_settings["color_by_line"] = True
                if viz_settings.get("align_connectors"):
                    extra_settings["show_connectors"] = True
                    extra_settings["connector_y"] = tuple(
                        pd.to_numeric(fig_fixations["y"], errors="coerce")
                    )
            with loading.card(
                plot_loading_slot,
                key="single",
                title="Drawing the scanpath",
                size=loading.plot_size("single", canvas_width, canvas_height),
            ):
                static_settings = render_settings.with_overrides(**extra_settings)
                build_inputs = static_settings.for_builder(STATIC_FIGURE_OPTIONS)
                # The builder never reads the title/caption styling —
                # `_apply_title_caption` stamps it on the copy after the cache —
                # so it keys no rebuild.
                for name in TEXT_STYLE_FIELDS:
                    build_inputs.pop(name, None)
                _amend_snippet_settings(static_settings, "static")
                build_inputs["raw_gaze"] = figure_raw_gaze
                if chart_axes.ELAPSED in (
                    static_settings.x_field,
                    static_settings.y_field,
                ):
                    origin = chart_axes.origin_ms(plot_fixations)
                    build_inputs["reading_origin_ms"] = (
                        None if pd.isna(origin) else origin
                    )
                # Not options, but the figure's text and its category colours.
                build_inputs["column_labels"] = static_settings.column_labels
                build_inputs["color_categories"] = static_settings.color_categories
                displayed_fig = _cached_scanpath_figure(
                    trial_words,
                    plot_fixations,
                    static_settings,
                    figure_raw_gaze,
                    fig_key=_figure_input_key(
                        trial_words, plot_fixations, build_inputs
                    ),
                )
                _apply_preprocessing_caption(
                    displayed_fig, selected_participant, selected_trial
                )
                _apply_title_caption(
                    displayed_fig,
                    viz_settings,
                    trial_words,
                    plot_fixations,
                    selected_participant,
                    selected_trial,
                    combo_row=primary_combo_row,
                )
                if (
                    static_settings.show_heatmap
                    and static_settings.heatmap_range is None
                ):
                    for trace in displayed_fig.data:
                        if trace.name == "heatmap colorbar" and trace.meta:
                            bounds = tuple(trace.meta["word_heatmap_range"])
                            plot_notes_slot.button(
                                "Use this heatmap range for other trials",
                                key="pin_word_heatmap_range",
                                on_click=pin_word_heatmap_range,
                                args=(bounds,),
                                help="Keep the raw values shown on this reading’s word-box legend as the fixed range.",
                            )
                            break
                preview_positions = False
                if (
                    "fixations snapped to lines" in detected_reasons
                    and not trial_words.empty
                ):
                    preview_scope = (
                        st.session_state.get("data_source_choice"),
                        selected_participant,
                        selected_trial,
                        selected_screen,
                    )
                    if st.session_state.get("_position_preview_scope") != preview_scope:
                        st.session_state.pop("preview_unsnapped_positions", None)
                        st.session_state["_position_preview_scope"] = preview_scope
                    preview_positions = plot_notes_slot.toggle(
                        "Show positions before snapping",
                        key="preview_unsnapped_positions",
                        help="Compare the illustration with the trial’s original fixation coordinates on identical axes. Imports with missing coordinates may use word-box centers.",
                    )
                panels = (
                    st.columns(2) if preview_positions else (contextlib.nullcontext(),)
                )
                with panels[0]:
                    if preview_positions:
                        st.caption("Illustration · figure selected for export")
                    _render_true_scale_chart(
                        displayed_fig,
                        key="single",
                        download_name=f"scanpath_{_safe_filename(save_slug)}",
                        alt=_scanpath_alt(
                            selected_participant,
                            _metadata_mod.trial_text_id(plot_fixations, trial_words)
                            or selected_trial,
                            len(trial_fixations),
                            displayed_fig,
                        ),
                        fit_window=True,
                    )
                if preview_positions:
                    reasons = [
                        reason
                        for reason in detected_reasons
                        if reason != "fixations snapped to lines"
                        and not reason.startswith("drift correction:")
                    ]
                    original = static_settings.with_overrides(
                        fixation_snap_to_line=False,
                        show_connectors=False,
                        illustration_reasons=tuple(
                            resolve_label_reasons(
                                viz_settings.get("illustration_label", "Auto"), reasons
                            )
                        ),
                    )
                    preview = _cached_scanpath_figure(
                        trial_words,
                        fig_fixations,
                        original,
                        figure_raw_gaze,
                        fig_key=_figure_input_key(
                            trial_words,
                            fig_fixations,
                            {
                                **original.for_builder(STATIC_FIGURE_OPTIONS),
                                "raw_gaze": figure_raw_gaze,
                                "column_labels": original.column_labels,
                                "color_categories": original.color_categories,
                            },
                        ),
                    )
                    preview.update_layout(
                        xaxis_range=displayed_fig.layout.xaxis.range,
                        yaxis_range=displayed_fig.layout.yaxis.range,
                        width=displayed_fig.layout.width,
                        height=displayed_fig.layout.height,
                    )
                    with panels[1]:
                        st.caption("Trial coordinates before snapping")
                        _render_true_scale_chart(
                            preview,
                            key="unsnapped_preview",
                            fit_window=True,
                            alt=f"Fixation positions before snapping for {selected_participant}, {selected_trial}.",
                        )
            note = _full_screen_note(viz_settings, canvas_width, canvas_height)
            if note and (static_settings.x_field, static_settings.y_field) == (
                "x",
                "y",
            ):
                st.caption(note)

    # Per-trial panels sit directly BELOW the plot, in the next row's left
    # column. The chips above the plot carry the trial's identity, conditions
    # and summary stats (configurable via the ✏️ chip editor).
    # The reserved keyed slot is the welcome-tour spotlight target.
    with subtabs_slot:
        simple = ui_mode.is_simple()
        subtab_labels = subtab_labels_for(
            simple, line_assignment=drift_correction_enabled()
        )
        # The bar's identity includes its labels, so a mode switch makes it a
        # new widget that would start on its first tab. Writing the selection
        # back before the bar is created carries it over, and a subtab the mode
        # lacks (a switch to Essentials from Comparisons, a tutorial step naming
        # one) falls back to the mode's first.
        if "single_subtab" in st.session_state:
            held = st.session_state["single_subtab"]
            st.session_state["single_subtab"] = (
                held if held in subtab_labels else subtab_labels[0]
            )
        _subtabs = st.tabs(
            subtab_labels,
            # A plain `st.tabs` executes EVERY tab's body on every run — only the
            # display is client-side — so the four expensive panels below would be
            # rebuilt on every rail tweak whether or not the user ever opened
            # them: 42% of a rerun on the bundled demo, and it scales with corpus
            # size.
            #
            # Keyed tabs fix that: with a `key` and `on_change="rerun"`, each tab
            # object exposes `.open`, so a body can be rendered only when its tab
            # is the selected one. The trade is that switching tabs costs a rerun
            # instead of being instant — worth it at ~0.3s, and the tab the user
            # is actually looking at is the one that stays fast.
            key="single_subtab",
            on_change="rerun",
        )
        by_label = dict(zip(subtab_labels, _subtabs))
        tab_annot = by_label.get(SUBTAB_ANNOTATIONS)
        tab_stim = by_label.get(SUBTAB_STIMULUS)
        tab_compare = by_label.get(SUBTAB_COMPARISONS)
        tab_align = by_label.get(SUBTAB_LINE_ASSIGNMENT)
        tab_export = by_label[SUBTAB_EXPORT]
        tab_share = by_label[SUBTAB_SHARE]
        tab_more = by_label.get(SUBTAB_MORE)
    # Annotations, Stimulus and Comparisons are absent entirely in Essentials mode.
    if tab_annot is not None:
        with tab_annot, st.container(key="tutorial_annotations"):
            render_trial_annotations(
                selected_participant,
                selected_trial,
                screen_id=selected_screen,
                bare=True,
            )
    if tab_stim is not None:
        with tab_stim:
            # Gated like the other keyed tabs — a hidden panel does no work,
            # and a trial whose context it cannot render costs only this tab.
            if tab_stim.open:
                _render_paragraph_panel(
                    trial_words, trial_fixations=trial_fixations, bare=True
                )
    with tab_compare if tab_compare is not None else contextlib.nullcontext():
        # Only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_compare is not None and tab_compare.open:
            # The chosen column selects other trials with the same value
            # as the main trial. A text field yields other readings of that text;
            # another field can intentionally cross texts.
            with st.container(key="tutorial_comparisons"):
                render_multiple_comparison_tab(
                    trial_words,
                    trial_fixations,
                    words_filtered,
                    fixations_filtered,
                    selected_participant=selected_participant,
                    selected_trial=selected_trial,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    base_font_size=base_font_size,
                    font_family=font_family,
                    viz_settings=viz_settings,
                    line_spacing=line_spacing,
                    scale_text_to_boxes=scale_text_to_boxes,
                    trial_raw_gaze=trial_raw_gaze,
                    raw_gaze=raw_gaze,
                    color_categories=_dataset_color_categories(
                        viz_settings.get("color_by"), fixations_all
                    ),
                )
        else:
            # Closed, the subtab keeps no copy of its matches.
            forget_frame_cache("comparison_matches")

    # Absent entirely while drift correction is gated off.
    with tab_align if tab_align is not None else contextlib.nullcontext():
        # Only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_align is not None and tab_align.open:
            # The drift-correction algorithm comparison grid, on the same
            # selected trial, in a subtab of its own.
            render_alignment_comparison_tab(
                trial_words,
                trial_fixations,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                base_font_size=base_font_size,
                font_family=font_family,
                viz_settings=viz_settings,
                line_spacing=line_spacing,
                scale_text_to_boxes=scale_text_to_boxes,
                selected_participant=selected_participant,
                selected_trial=selected_trial,
            )

    with tab_export:
        # Only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_export.open:
            with st.container(key="tutorial_export"):
                _render_export_panel(
                    displayed_fig,
                    animate=animate,
                    replay=anim_view,
                    save_slug=save_slug,
                    file_stem=anim_file_stem,
                    combos=combos,
                    words_filtered=words_filtered,
                    fixations_filtered=fixations_filtered,
                    combos_all=combos_all,
                    words_all=words_all,
                    fixations_all=fixations_all,
                    raw_gaze=raw_gaze if raw_gaze is not None else pd.DataFrame(),
                    raw_gaze_all=raw_gaze_all,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    base_font_size=base_font_size,
                    font_family=font_family,
                    viz_settings=viz_settings,
                    line_spacing=line_spacing,
                    scale_text_to_boxes=scale_text_to_boxes,
                    selected_participant=selected_participant,
                    selected_trial=selected_trial,
                    plot_key=displayed_plot_key,
                    include_bundle=not simple,
                )

    # The Share subtab. app.main passes the renderer (it owns the
    # deep-link builder + data source). Keyed wrapper → the spotlight
    # target for the publication-figure tutorial.
    with tab_share, st.container(key="tutorial_share"):
        if share_renderer is not None:
            # Whether the subtab is on screen. The Link keeps being
            # built every run (its query is read back through session state),
            # but File's settings file is only worth building when visible.
            share_renderer(tab_share.open)
        else:
            st.caption("Sharing is unavailable in this context.")

    # Essentials mode's last subtab: what Full adds below the plot.
    if tab_more is not None and tab_more.open:
        ui_mode.render_more_list(tab_more, "subtabs")


#: Set by Stop on a running bundle build, read (and dropped) by the next run
#: of the Export panel, which says the build was stopped. Internal: never on
#: the wire, never in the recovery cache.
_BULK_EXPORT_STOPPED = "_bulk_export_stopped"

#: The session's replaced disk bundle, which `DiskBundle.retire` keeps on disk
#: for a while so a download already under way can finish. One per session.
#: Internal: never on the wire, never in the recovery cache.
_BULK_EXPORT_RETIRED = "_bulk_export_retired"


def _retire_bulk_bundle(bundle) -> None:
    """Let go of a replaced bundle without cutting off its download.

    A disk bundle is deleted after a grace period, or at once when the session
    retires another. A bundle held in memory needs nothing."""
    if not isinstance(bundle, DiskBundle):
        return
    earlier = st.session_state.get(_BULK_EXPORT_RETIRED)
    if earlier is not None and earlier is not bundle:
        earlier.close()
    st.session_state[_BULK_EXPORT_RETIRED] = bundle
    bundle.retire()


def _drop_bulk_export_cache() -> None:
    """Forget the session's bundle; its download keeps working for a while."""
    cache = st.session_state.pop("_bulk_export_cache", None)
    if cache:
        _retire_bulk_bundle(cache["data"])


def _bulk_export_task_key() -> tuple:
    """The bundle build's progress task — one per session."""
    return ("bulk_export", loading.session_id())


def _stop_bulk_export(task_key: tuple, retry: bool = False) -> None:
    """Stop the build. A cancelled retry leaves its original download available."""
    progress.cancel(task_key)
    st.session_state[_BULK_EXPORT_STOPPED] = "retry" if retry else "build"
    if not retry:
        _drop_bulk_export_cache()


@st.cache_data(show_spinner=False, max_entries=16)
def _c_export_unit_count(
    _combos: pd.DataFrame,
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame | None,
    frame_keys: tuple,
    scope: tuple,
) -> tuple[int, int] | None:
    """``(trials, screen units)`` the bundle will export, for the plan line
    above Build export. Cached on the four frames' fingerprints
    (``frame_keys``) and the scope choice, since it walks every trial.

    ``None`` when screens contradict each other (Build export reports it) —
    returned, not raised, so that answer is cached too rather than re-walked
    on every rerun."""
    scope_name, participant, trial, text, screens = scope
    scoped = apply_export_scope(
        _combos,
        ExportOptions(
            scope=scope_name,
            scope_participant=participant,
            scope_trial=trial,
            scope_text=text,
        ),
    )
    try:
        return count_export(scoped, _words, _fixations, _raw_gaze, screens)
    except ValueError:
        return None


@st.cache_data(show_spinner=False, max_entries=4)
def _c_bundle_contents(
    _combos: pd.DataFrame,
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame | None,
    _options: ExportOptions,
    _settings: dict,
    _column_names: dict,
    _annotation_records: list | None,
    axes: tuple[str, str],
    frame_keys: tuple,
    key: tuple,
) -> BundleContents | str:
    """*Preview bundle contents*, which walks every reading and takes seconds
    over a large corpus for a custom path pattern. Cached on the four frames'
    fingerprints (``frame_keys``), the axes and ``key``: the options, the
    settings (with the attached metadata tables' fingerprints), the names of
    the metadata fields a pattern can use, the column names and the annotations.

    An invalid plan's message is returned, not raised, so it is cached too."""
    try:
        return bundle_contents(
            _combos,
            _words,
            _fixations,
            _raw_gaze,
            options=_options,
            settings=_settings,
            axes=axes,
            column_names=_column_names,
            metadata_rows_for=_metadata_mod.pattern_rows,
            annotation_records=_annotation_records,
        )
    except ValueError as error:
        return str(error)


@st.cache_data(show_spinner=False, max_entries=8)
def _c_export_screen_choices(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame | None,
    frame_keys: tuple,
) -> list[str]:
    """The Export panel's *Screens* options, cached on the frames' fingerprints."""
    return screen_choices(_words, _fixations, _raw_gaze)


def _render_bulk_export(
    combos: pd.DataFrame,
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    combos_all: pd.DataFrame,
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    raw_gaze: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    x_field: str,
    y_field: str,
    figure_settings: dict,
    selected_participant: str,
    selected_trial: str,
    raw_gaze_all: pd.DataFrame | None = None,
) -> None:
    """Render configurable bulk-export UI (artifact picker + run + download)."""
    # The whole dataset's screens, so the picker does not change with the scope.
    every_raw_gaze = raw_gaze_all if raw_gaze_all is not None else raw_gaze
    screen_options = _c_export_screen_choices(
        words_all,
        fixations_all,
        every_raw_gaze,
        (
            frame_fingerprint(words_all),
            frame_fingerprint(fixations_all),
            frame_fingerprint(every_raw_gaze),
        ),
    )

    def example_for(options: ExportOptions, scoped: pd.DataFrame):
        frames = (
            (words_all, fixations_all, every_raw_gaze)
            if options.export_unfiltered
            else (words_filtered, fixations_filtered, raw_gaze)
        )
        return naming_example(
            options,
            scoped,
            *frames,
            settings=figure_settings,
            axes=(x_field, y_field),
            column_names=active_all(st.session_state),
            metadata_rows_for=_metadata_mod.pattern_rows,
        )

    options = render_export_options(
        st,
        combos,
        key_prefix="bulk_export",
        combos_all=combos_all,
        title_pattern=figure_settings.get("title_pattern", ""),
        caption_pattern=figure_settings.get("caption_pattern", ""),
        selected_participant=selected_participant,
        selected_trial=selected_trial,
        screen_options=screen_options,
        example_for=example_for,
    )
    # Tick "Export the whole dataset" → export the unfiltered frames.
    active_raw_gaze = raw_gaze
    if options.export_unfiltered:
        active_combos, active_words, active_fix = combos_all, words_all, fixations_all
        # The whole dataset's samples too, or its samples-only trials
        # would reach `bulk_export` with nothing to draw and be skipped.
        if raw_gaze_all is not None:
            active_raw_gaze = raw_gaze_all
    else:
        active_combos, active_words, active_fix = (
            combos,
            words_filtered,
            fixations_filtered,
        )
    frame_keys = (
        frame_fingerprint(active_combos),
        frame_fingerprint(active_words),
        frame_fingerprint(active_fix),
        frame_fingerprint(active_raw_gaze),
    )
    counts = None
    if not active_combos.empty:
        # What Build export is about to write: a parent trial can hold many
        # screens, and each screen one file per format (and per layer).
        counts = _c_export_unit_count(
            active_combos,
            active_words,
            active_fix,
            active_raw_gaze,
            frame_keys,
            (
                options.scope,
                options.scope_participant,
                options.scope_trial,
                options.scope_text,
                options.screens,
            ),
        )
    run_col, info_col = st.columns([1, 3])
    with run_col:
        nothing_ticked = not (
            options.needs_figure()
            or options.include_plot_config
            or options.include_annotations
            or options.any_table()
        )
        blocked = (
            "Correct the file path pattern above."
            if not options.path_pattern
            else "Choose at least one file to include."
            if nothing_ticked
            else "No trial matches the selected scope and screens."
            if active_combos.empty or counts == (0, 0)
            else None
        )
        run = st.button(
            "Build export",
            type="primary",
            disabled=bool(blocked),
            help=blocked,
        )
        stop_slot = st.empty()
    task_key = _bulk_export_task_key()
    if not run and progress.running(task_key):
        # A build an earlier run left going — the user clicked something else
        # mid-build. That run can no longer hand its bundle over, so stop it.
        progress.cancel(task_key)
    if counts is not None:
        info_col.caption(describe_plan(plan_from_counts(*counts, options)))
    stopped = st.session_state.pop(_BULK_EXPORT_STOPPED, None)
    if stopped and not run:
        info_col.warning(
            "Retry stopped. The previous bundle is still available."
            if stopped == "retry"
            else "Export stopped, so no bundle was built. Click **Build export** to start again.",
            icon=ICONS["warning"],
        )
    # The session's annotations, only when the bundle asks for them —
    # and in the cache key then, so a note edited after a build is not served
    # from the stale zip.
    import scanpath_studio.annotations as _annotations_mod

    annotation_records = (
        _annotations_mod.current_records() if options.include_annotations else None
    )
    # The file names the dataset its annotations were made on, as the
    # one 🗂️ Data → Annotations exports does.
    annotation_owner = _annotations_mod.current_dataset(st.session_state)
    annotation_dataset = None
    if annotation_owner is not None:
        from scanpath_studio.app import _dataset_display_name

        annotation_dataset = _dataset_display_name(annotation_owner)
    settings_key = json.dumps(figure_settings, sort_keys=True, default=str)
    # The figure on screen assigns category colours over the whole dataset's
    # labels, whichever trials the bundle exports.
    color_categories = _dataset_color_categories(
        figure_settings.get("color_by"), fixations_all
    )
    annotations_key = json.dumps(annotation_records, sort_keys=True, default=str)
    table_names = _dataset_table_names()
    # A renamed column changes every table's header.
    names_key = json.dumps(
        {t: n.to_payload() for t, n in table_names.items()}, sort_keys=True
    )
    preview = st.expander(
        "Preview bundle contents", key="bulk_export_contents", on_change="rerun"
    )
    if preview.open and options.path_pattern:
        preview_settings = {
            **figure_settings,
            **{
                f"{grain}_metadata": st.session_state.get(f"_export_{grain}_metadata")
                for grain in ("participant", "trial", "text")
            },
        }
        # The settings carry the attached tables' fingerprints; a pattern can
        # also name a field the table declares.
        metadata_fields = tuple(
            None if table is None else table.names
            for table in (
                _metadata_mod.active(),
                _metadata_mod.active_trials(),
                _metadata_mod.active_texts(),
            )
        )
        contents = _c_bundle_contents(
            active_combos,
            active_words,
            active_fix,
            active_raw_gaze,
            options,
            preview_settings,
            table_names,
            annotation_records,
            (x_field, y_field),
            frame_keys,
            (repr(options), settings_key, metadata_fields, names_key, annotations_key),
        )
        if isinstance(contents, str):
            preview.error(contents)
        else:
            if options.print_width_mm and options.raster_formats():
                sizing = f"{options.print_width_mm:g} mm wide"
                if options.include_png or options.include_tiff:
                    sizing += f" · {options.print_dpi} dpi for raster figures"
                preview.caption(sizing)
            for note in contents.notes:
                preview.caption(note)
            preview.dataframe(pd.DataFrame(contents.files), hide_index=True)
    sig = (
        *frame_keys,
        int(canvas_width),
        int(canvas_height),
        int(base_font_size),
        str(font_family),
        str(x_field),
        str(y_field),
        settings_key,
        color_categories,
        repr(options),
        annotations_key,
        annotation_dataset,
        EXPORTER_VERSION,
        names_key,
    )
    cache = st.session_state.get("_bulk_export_cache")
    if cache and cache.get("sig") != sig:
        _drop_bulk_export_cache()
        cache = None

    retry = bool(
        st.session_state.pop("_bulk_retry_requested", False)
        and cache
        and cache["progress"].retryable_figures
    )
    if run or retry:
        status_box = info_col.status("Preparing the export bundle…", expanded=True)
        progress_slot = info_col.empty()
        progress_bar = None

        def on_status(status: ExportStatus) -> None:
            nonlocal progress_bar
            elapsed = f" · {status.elapsed_s:.1f}s" if status.elapsed_s else ""
            state = (
                "complete"
                if status.stage == ExportStage.READY
                else "error"
                if status.stage == ExportStage.ERROR
                else "running"
            )
            status_box.update(label=f"{status.message}{elapsed}", state=state)
            if status.fraction is not None:
                # Over a real corpus this runs for hours, so the bar
                # carries the rate and the time left, not just the count.
                text = progress_caption(status)
                if progress_bar is None:
                    progress_bar = progress_slot.progress(status.fraction, text=text)
                else:
                    progress_bar.progress(status.fraction, text=text)

        stop_slot.button(
            "Stop",
            key="bulk_export_stop",
            on_click=_stop_bulk_export,
            args=(task_key, retry),
            help="Stop this retry and keep the existing bundle."
            if retry
            else "Stop after the current reading or screen.",
        )
        try:
            with progress.task(task_key, title="Building the export bundle"):
                build = bulk_export
                if retry:
                    from scanpath_studio.export_retry import retry_failed_figures

                    build = functools.partial(retry_failed_figures, cache, sig)
                bundle, built_progress = build_download(
                    build,
                    active_combos,
                    active_words,
                    active_fix,
                    # Each trial's metadata rows, for `{table.field}`.
                    metadata_rows_for=_metadata_mod.pattern_rows,
                    annotation_records=annotation_records,
                    annotation_dataset=annotation_dataset,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    base_font_size=base_font_size,
                    font_family=font_family,
                    x_field=x_field,
                    y_field=y_field,
                    settings=figure_settings,
                    options=options,
                    raw_gaze=active_raw_gaze,
                    stimulus_image_resolver=_reading_stimulus_image,
                    status_callback=on_status,
                    # The tables go out under the dataset's own names.
                    column_names=_dataset_table_names(),
                    color_categories=color_categories,
                )
        except Exception as exc:
            stop_slot.empty()
            progress_slot.empty()
            status_box.update(label="Export failed", state="error")
            if not retry:
                _drop_bulk_export_cache()
                cache = None
            st.warning(f"Couldn't build the export bundle: {exc}")
        else:
            stop_slot.empty()
            progress_slot.empty()
            replaced = cache["data"] if cache else None
            cache = {"sig": sig, "data": bundle, "progress": built_progress}
            st.session_state["_bulk_export_cache"] = cache
            # A retry with nothing left to repair hands back the same bundle.
            if replaced is not bundle:
                _retire_bulk_bundle(replaced)
            # The status box's last word is the bundle's, not
            # "ready" over a zip whose figures failed.
            built = summarize_export(built_progress, len(bundle))
            status_box.update(
                label=built.message,
                state="error" if built.level == "error" else "complete",
                expanded=False,
            )

    if cache and cache.get("sig") == sig:
        bundle = cache["data"]
        built_progress = cache["progress"]
        # What was made and what failed; a partial zip still downloads.
        built = summarize_export(built_progress, len(bundle))
        getattr(info_col, built.level)(built.message, icon=ICONS[built.level])
        if built_progress.errors:
            with st.expander(
                f"Export errors ({len(built_progress.errors):,})",
                expanded=built.expand_errors,
            ):
                for err in built_progress.errors:
                    st.write(err)
        if built_progress.retryable_figures:
            st.button(
                "Retry failed figure files",
                on_click=st.session_state.__setitem__,
                args=("_bulk_retry_requested", True),
                help="Keep the successful files and retry the failed figures and layers.",
            )
        filename = (
            f"scanpath_export_{pd.Timestamp.now():%Y%m%d_%H%M%S}.zip"  # local time
        )
        if isinstance(bundle, DiskBundle):
            st.link_button(
                "⬇ Download bundle (zip)",
                bundle.download_url(filename),
                type="primary",
            )
        else:
            st.download_button(
                "⬇ Download bundle (zip)",
                data=bundle,
                file_name=filename,
                mime="application/zip",
                type="primary",
            )


def _comparison_image_b(
    settings: FigureSettings,
    viz_settings: dict,
    compare_meta: dict | None,
    *,
    same_page: bool,
) -> dict:
    """B's own stimulus page for a split comparison's B panel.

    Resolved from B's own trial and screen — never inherited from A because the
    two readings share a dataset, which says nothing about whether they share a
    page. A B without an image of its own gets none, so its panel stays blank
    rather than showing A's page.

    The one shared image is an **uploaded** one, and only on ``same_page`` — B
    reads the same text on the same screen of the same dataset as A. An upload
    stands in for A's page (it is stretched over A's screen), so it is B's page
    exactly then. Otherwise B shows its own dataset image, or none.

    The manual nudge (offset / scale) corrects one dataset's coordinate frame
    against its images, so it applies to a same-dataset B and not to another
    dataset's.
    """
    none = {
        "background_image_b": None,
        "background_image_size_b": None,
        "background_image_origin_b": None,
    }
    layer_on = bool(viz_settings.get("show_stimulus_image")) or (
        settings.background_image is not None
    )
    if not compare_meta or not layer_on:
        return none
    if viz_settings.get("stimulus_image_upload_uri") and same_page:
        if settings.background_image is None:
            return none
        return {
            "background_image_b": settings.background_image,
            "background_image_size_b": settings.background_image_size,
            "background_image_origin_b": settings.background_image_origin,
        }
    dataset = compare_meta.get("dataset")
    own = _reading_stimulus_image(
        compare_meta.get("words", pd.DataFrame()),
        compare_meta.get("fixations", pd.DataFrame()),
        source=dataset,
    )
    if own is None:
        return none
    path, (width, height), (ox, oy) = own
    if not dataset:
        scale = float(viz_settings.get("stimulus_image_scale", 1.0)) or 1.0
        width, height = width * scale, height * scale
        ox += float(viz_settings.get("stimulus_image_offset_x", 0.0))
        oy += float(viz_settings.get("stimulus_image_offset_y", 0.0))
    return {
        "background_image_b": path,
        "background_image_size_b": (float(width), float(height)),
        "background_image_origin_b": (float(ox), float(oy)),
    }


def _page_under_text_b(
    settings: FigureSettings, viz_settings: dict, compare_meta: dict | None
) -> dict:
    """The page an overlay or co-animation draws under B's text
    (``compare_stimulus="b"``): B's own, nudged as `_comparison_image_b`
    nudges it, or none. Never A's, which is a picture of another text; an
    uploaded image is the user's explicit choice and stays, as an explicit
    ``background_image`` does in `api.compare_scanpaths`."""
    if viz_settings.get("stimulus_image_upload_uri"):
        return {}
    image_b = _comparison_image_b(settings, viz_settings, compare_meta, same_page=False)
    return {key.removesuffix("_b"): value for key, value in image_b.items()}


def _own_page_b(viz_settings: dict, compare_meta: dict | None):
    """B's own page, unmoved — what `api` would place for it — or ``None``
    while the layer is off, or when B comes from a second dataset: the snippet
    loads that one's tables from placeholders, which hold no page to find
    again, so B's page keeps its path there."""
    if (
        not compare_meta
        or compare_meta.get("dataset")
        or not viz_settings.get("show_stimulus_image")
    ):
        return None
    return _reading_stimulus_image(
        compare_meta.get("words", pd.DataFrame()),
        compare_meta.get("fixations", pd.DataFrame()),
        source=compare_meta.get("dataset"),
    )


def _render_comparison_figure(
    combos: pd.DataFrame,
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    selected_participant: str,
    selected_trial: str,
    selected_text: str | None,
    compare_participant: str,
    compare_trial: str,
    settings: FigureSettings,
    viz_settings: dict,
    layout: str = "overlay",
    compare_stimulus: str = "both",
    compare_meta: dict | None = None,
    shared_numeric: frozenset[str] | None = None,
    setup_note: str = "",
    primary_combo_row: Callable[[], dict | None] | None = None,
    download_name: str = "scanpath",
    figure_participant_b: str | None = None,
    raw_gaze: pd.DataFrame | None = None,
):
    """Render comparison figure for two trials.

    ``raw_gaze`` is both readings' samples, keyed like the merged
    frames, or ``None`` when the layer is off or neither reading has any.

    ``figure_participant_b`` is the id B's rows carry in the merged
    frames. Cross-dataset and self-comparisons qualify that id so the two
    readings can be sliced independently. Labels keep the reader's own id.

    ``fixations_filtered`` carries both scanpaths, already resolved by the
    caller: each scanpath's own fixation-index window is applied upstream, and
    A's never cuts B — a window sized to A's own fixation count must never
    silently truncate a B with more fixations than A. Shared visual choices,
    canvas geometry, and the stimulus image arrive in ``settings``.

    ``fixations_filtered`` may already carry drift-corrected ``y`` values —
    correction happens once, upstream of the render-mode split.

    When ``compare_meta`` names a ``dataset``, B came from a different
    corpus. Its text id then comes from ``compare_meta`` rather than a lookup in
    A's ``combos`` (which cannot know a foreign trial), B's panel is drawn to B's
    own monitor (``canvas_b``), and a caption below the figure says so —
    panel sizes are not comparable when the two screens differ. ``shared_numeric``
    is the metric intersection of the two corpora; a ``color_by`` absent from one
    side would colour one panel and blank the other, so it is dropped with a note.

    ``setup_note`` is `experimental_setup.setups_comparable`'s
    sentence about the two screens — either why the pair could not be overlaid
    (plus, when an Overlay was asked for, that it is shown side by side instead
    — the caller's sentence), or, on an overlay that *was* allowed, the
    caveat that the matching canvas is a shared default rather than a recorded
    screen. Empty when neither applies.
    It surfaces where the user is looking (a warning under an overlay, appended
    to the caption under a split layout) rather than only in the rail's
    popover.

    ``primary_combo_row`` is the caller's memoized thunk for A's `combos` row
    (`render_single_trial_tab.primary_combo_row`) — passed in rather than
    re-masked here, so the scan runs at most once per rerun. It is optional only
    so this function stays callable on its own; without it the row is masked
    locally."""
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    cross_dataset = bool(compare_meta and compare_meta.get("dataset"))
    # A's row, from the caller's memo when there is one: both of this
    # function's consumers — A's text id just below and `_apply_title_caption`
    # at the end — read the same row. B's row is a different trial and is
    # looked up.
    _local_memo: list = []

    def _primary_row() -> dict | None:
        if primary_combo_row is not None:
            return primary_combo_row()
        if not _local_memo:
            _local_memo.append(_combo_row(combos, selected_participant, selected_trial))
        return _local_memo[0]

    def _lookup_text_id(participant_id: str, trial_id: str) -> str | None:
        row = _combo_row(combos, participant_id, trial_id)
        value = None if row is None else row.get(text_field)
        return None if value is None else str(value)

    label_pool: set[str] = set()
    primary_text_id = selected_text
    if not primary_text_id:
        row = _primary_row()
        value = None if row is None else row.get(text_field)
        primary_text_id = None if value is None else str(value)
    compare_text_id = (
        compare_meta.get("text_id")
        if cross_dataset
        else _lookup_text_id(compare_participant, compare_trial)
    )
    primary_label = friendly_trial_label(
        selected_participant, selected_trial, primary_text_id, label_pool
    )
    dataset_b = _compare_dataset_name(compare_meta)
    frame_participant_b = figure_participant_b or compare_participant
    compare_label = friendly_trial_label(
        compare_participant,
        compare_trial,
        compare_text_id,
        label_pool,
        prefix=f"{dataset_b}{_COMPARE_DATASET_SEP}" if cross_dataset else "",
    )
    # An explicit cmp{idx}_label_pattern overrides the auto label above.
    if st.session_state.get("cmp0_label_pattern"):
        primary_label = _resolve_compare_label(
            0,
            selected_participant,
            selected_trial,
            extract_trial(words_filtered, selected_participant, selected_trial),
            extract_trial(fixations_filtered, selected_participant, selected_trial),
            dataset_name=current_dataset_name(),
        )
    if st.session_state.get("cmp1_label_pattern"):
        compare_label = _resolve_compare_label(
            1,
            compare_participant,
            compare_trial,
            extract_trial(words_filtered, frame_participant_b, compare_trial),
            extract_trial(fixations_filtered, frame_participant_b, compare_trial),
            dataset_name=dataset_b,
        )

    _amend_snippet_compare_labels((primary_label, compare_label))

    overrides: dict = dict(
        trial_labels=(primary_label, compare_label),
        layout=layout,
        compare_stimulus=compare_stimulus,
        style_a=viz_settings.get("compare_style_a"),
        style_b=viz_settings.get("compare_style_b"),
        show_legend=viz_settings.get("show_compare_legend", True),
        # Comparison retains its count-vs-duration spelling; the static builder
        # translates "counts" to None internally.
        heatmap_metric=viz_settings.get("heatmap_metric", "duration_ms"),
    )
    dropped_metric = None
    canvas_a = (int(settings.canvas_width), int(settings.canvas_height))
    # B's panel is drawn to B's own screen — its selected screen's canvas,
    # else its dataset's (`_build_compare_meta`). Only the split layouts read
    # it; an overlay of two different screens never gets here (the caller
    # resolves it to a split layout), and that holds within one dataset as
    # much as across two.
    canvas_b = (compare_meta or {}).get("canvas")
    canvas_b = tuple(int(v) for v in canvas_b) if canvas_b is not None else None
    # Always stated, as `api.compare_scanpaths` states it: with no `canvas_b`
    # the builder hands B's panel A's stimulus image, and dataset identity is
    # no reason to think B read A's page. B's own image is resolved next.
    overrides["canvas_b"] = canvas_b or canvas_a
    own_b = _own_page_b(viz_settings, compare_meta)
    if layout in {"side_by_side", "stacked"}:
        # B's panel over B's page. Only a split layout draws that slot, so an
        # overlay leaves it empty rather than carry (and quote) a page it hides.
        overrides.update(
            _comparison_image_b(
                settings,
                viz_settings,
                compare_meta,
                same_page=(
                    not cross_dataset
                    and primary_text_id is not None
                    and primary_text_id == compare_text_id
                    and _first_str(
                        extract_trial(
                            words_filtered, selected_participant, selected_trial
                        ),
                        SCREEN_ID,
                    )
                    == _first_str(
                        (compare_meta or {}).get("words", pd.DataFrame()), SCREEN_ID
                    )
                ),
            )
        )
        _amend_snippet_own_pages({"_b": own_b})
    elif compare_stimulus == "b":
        # One page under the overlay's one stimulus layer — B's, since
        # B's text is the one drawn.
        overrides.update(_page_under_text_b(settings, viz_settings, compare_meta))
        _amend_snippet_own_pages({"": own_b})
    if cross_dataset:
        # A metric only one corpus ships would colour one panel and blank
        # the other. Fall back for *this render* — the stored choice is left
        # alone, so a same-dataset pair gets it straight back — and name what
        # was dropped rather than showing half a figure.
        def _unshared(value) -> bool:
            return (
                shared_numeric is not None
                and isinstance(value, str)
                and value not in _CROSS_DATASET_SAFE_METRICS
                and value not in shared_numeric
            )

        if _unshared(settings.color_by):
            dropped_metric = str(settings.color_by)
            overrides["color_by"] = None
        if _unshared(overrides["heatmap_metric"]):
            dropped_metric = str(overrides["heatmap_metric"])
            overrides["heatmap_metric"] = "duration_ms"
    comparison_settings = settings.with_overrides(**overrides)
    _amend_snippet_settings(comparison_settings, "comparison")
    trials = (
        (selected_participant, selected_trial),
        (frame_participant_b, compare_trial),
    )
    fig_compare = _cached_comparison_figure(
        words_filtered,
        fixations_filtered,
        trials,
        comparison_settings,
        raw_gaze,
        fig_key=_comparison_figure_key(
            words_filtered, fixations_filtered, comparison_settings, raw_gaze, trials
        ),
    )
    add_illustration_label(
        fig_compare,
        viz_settings.get("illustration_reasons"),
        text=viz_settings.get("illustration_text", ""),
    )
    _apply_preprocessing_caption(fig_compare, selected_participant, selected_trial)
    _apply_title_caption(
        fig_compare,
        viz_settings,
        extract_trial(words_filtered, selected_participant, selected_trial),
        extract_trial(fixations_filtered, selected_participant, selected_trial),
        selected_participant,
        selected_trial,
        combo_row=_primary_row,
        # Two readings in one figure, so `{dataset_name_b}` and friends
        # have a value to resolve against.
        compare_row={
            "dataset_name": dataset_b,
            "participant_id": compare_participant,
            "trial_id": compare_trial,
            "text_id": compare_text_id,
        },
    )
    _render_true_scale_chart(
        fig_compare, key="compare", download_name=download_name, fit_window=True
    )
    overlaid = layout == "overlay"
    # Only where the figure is misleading (see the note's docstring): a split
    # layout comparing two texts is a legitimate thing to do.
    text_note = (
        _different_texts_note(primary_text_id, compare_text_id) if overlaid else None
    )
    if text_note:
        st.warning(text_note, icon=ICONS["warning"])
    if cross_dataset and (settings.x_field, settings.y_field) == ("x", "y"):
        # The one thing a cross-dataset figure must never be is silent
        # about its own geometry. Each panel is true-to-scale on its *own*
        # monitor, so a box twice the size of the one beside it may be the same
        # physical size — naming both screens is what keeps that readable.
        active = md_literal(current_dataset_name() or "this dataset")
        other = md_literal(_compare_dataset_name(compare_meta))
        if canvas_b is None:
            canvas_b = canvas_a
        if layout == "overlay":
            # A cross-dataset pair only reaches the overlay on equal
            # canvases, so the caption states the ground it stands on. When
            # `setup_note` is non-empty the canvases matched but at least one
            # corpus never *recorded* a screen — the overlay is still drawn (the
            # user usually knows the two displays matched even when the data
            # can't say so), and the caveat is raised to a warning rather than
            # buried in the caption, because it qualifies what the figure means.
            st.caption(
                f"Overlaying {active} and {other}, both at "
                f"{canvas_a[0]}×{canvas_a[1]}. Positions are compared in screen "
                "pixels, without rescaling."
            )
            if setup_note:
                st.warning(setup_note, icon=ICONS["warning"])
        elif tuple(canvas_a) != tuple(canvas_b):
            st.caption(
                "Each panel is drawn at its dataset's screen size: "
                f"{active} {canvas_a[0]}×{canvas_a[1]}, "
                f"{other} {canvas_b[0]}×{canvas_b[1]}. "
                "Sizes are not comparable across panels."
                + (f" {setup_note}" if setup_note else "")
            )
        else:
            st.caption(
                f"Comparing {active} and {other}, which share "
                f"a {canvas_a[0]}×{canvas_a[1]} screen."
                + (f" {setup_note}" if setup_note else "")
            )
    elif (
        (settings.x_field, settings.y_field) == ("x", "y")
        and canvas_b is not None
        and canvas_b != canvas_a
    ):
        # One dataset, two screen sizes: each panel is drawn to its own screen,
        # and `setup_note` says why an Overlay could not be drawn.
        st.caption(
            "Each panel is drawn at its trial's screen size: "
            f"A {canvas_a[0]}×{canvas_a[1]}, B {canvas_b[0]}×{canvas_b[1]}. "
            "Sizes are not comparable across panels."
            + (f" {setup_note}" if setup_note else "")
        )
    if dropped_metric:
        st.caption(
            f"{ICONS['warning']} **{active_all(st.session_state).field_label(dropped_metric)}** "
            "isn't in both datasets, so this comparison is drawn without it. "
            "Your choice is kept for same-dataset comparisons."
        )
    return fig_compare


# -----------------------------------------------------------------------------
# Corpus Analysis Tab  (Per text · Per participant · Groups subtabs)
# -----------------------------------------------------------------------------

# --- Cached analysis wrappers ------------------------------------------------
# Each wraps a pure ``aggregation`` helper with ``@st.cache_data`` keyed on a
# cheap frame *fingerprint* (``fkey``) + hashable scalars (the measure key,
# aggregation/spread, flags), mirroring the existing cached-aggregation pattern.
# Frames pass un-hashed (underscore args). Group views feed a pre-filtered frame, so its
# fingerprint keys a separate cache entry automatically.


@st.cache_data(show_spinner=False)
def _c_per_reader_word(
    _words, text_col, text_id, mkey, agg, normalize, fkey, screen=None
):
    return per_reader_word_measure(
        _words,
        text_col,
        text_id,
        MEASURES[mkey],
        agg=agg,
        normalize=normalize,
        screen_id=screen,
    )


@st.cache_data(show_spinner=False)
def _c_cohort_profile(
    _words,
    text_col,
    text_id,
    mkey,
    agg,
    spread,
    normalize,
    min_readers,
    fkey,
    screen=None,
):
    return cohort_word_profile(
        _words,
        text_col,
        text_id,
        MEASURES[mkey],
        agg=agg,
        spread=spread,
        normalize=normalize,
        min_readers=min_readers,
        screen_id=screen,
    )


@st.cache_data(show_spinner=False)
def _c_stimulus_revisions(_words, text_col, text_id, fkey, screen=None):
    return stimulus_revisions(_words, text_col, text_id, screen)


@st.cache_data(show_spinner=False)
def _c_word_box_aggregate(
    _words, text_col, text_id, mkey, agg, fkey, screen=None, readings=None
):
    return word_box_aggregate(
        _words,
        text_col,
        text_id,
        MEASURES[mkey],
        agg=agg,
        screen_id=screen,
        readings=readings,
    )


@st.cache_data(show_spinner=False)
def _c_word_feature(
    _words, text_col, text_id, mkey, feature_col, agg, normalize, fkey, screen=None
):
    return word_measure_vs_feature(
        _words,
        text_col,
        text_id,
        MEASURES[mkey],
        feature_col,
        agg=agg,
        normalize=normalize,
        screen_id=screen,
    )


@st.cache_data(show_spinner=False)
def _c_word_rate(_words, text_col, text_id, min_readers, fkey, screen=None):
    return word_rate_profile(
        _words, text_col, text_id, min_readers=min_readers, screen_id=screen
    )


@st.cache_data(show_spinner=False)
def _c_cohort_summary(_words, _fix, fwkey, ffkey):
    return reader_summary_table(_words, _fix)


@st.cache_data(show_spinner=False)
def _c_trial_summary(_words, _fix, fwkey, ffkey):
    return trial_summary_table(_words, _fix)


@st.cache_data(show_spinner=False, max_entries=4)
def _c_enrich_fix(_fix, _words, ffkey, fwkey):
    return ensure_fixation_enrichment(_fix, _words)


def _enriched_corpus_fixations(
    fixations: pd.DataFrame, words: pd.DataFrame
) -> pd.DataFrame:
    enriched = _c_enrich_fix(
        fixations, words, frame_fingerprint(fixations), frame_fingerprint(words)
    )
    assign_derived(enriched, "enrich_fix", (fixations, words))
    return enriched


@st.cache_data(show_spinner=False)
def _c_trial_keys(_frame, fkey):
    """`data.trial_keys`, cached per frame — a trial-metadata group
    needs the loaded readings on every rerun, once per group per frame."""
    return trial_keys(_frame)


@st.cache_data(show_spinner=False, max_entries=16)
def _c_group_means(_frame, mkey, _readings, _specs, key):
    """Group means' two value arrays: one mean per participant, or every value
    when the frame names no participants.

    ``key`` is the frame's fingerprint and what selects each group — its
    readings, or its spec on a frame without the reading key
    (:func:`_group_means_key`).
    """
    measure = MEASURES[mkey]
    if not _frame.empty and set(_TRIAL_KEY_COLUMNS) <= set(_frame):
        # Each row's already-resolved reading, looked up on the frame's codes.
        codes, reading_keys = distinct_key_codes(_frame, _TRIAL_KEY_COLUMNS)
        masks = [reading_keys.isin(group)[codes] for group in _readings]
    else:
        masks = [group_mask(_frame, spec) for spec in _specs]
    values = reader_means if "participant_id" in _frame else measure_values
    columns = _frame.columns.intersection(["participant_id", measure.column])
    return tuple(values(_frame.loc[mask, columns], measure) for mask in masks)


def _group_means_key(frame, readings, specs) -> tuple:
    """`_c_group_means`'s key: the readings as exact, order-free digests
    (`data.set_digest`), or the specs when the frame has no reading key to
    look them up by."""
    if not frame.empty and set(_TRIAL_KEY_COLUMNS) <= set(frame):
        groups = tuple(set_digest(group) for group in readings)
    else:
        groups = hashable_key(specs)
    return (frame_fingerprint(frame), groups)


@st.cache_data(show_spinner=False, max_entries=4)
def _c_reader_vs_cohort(_frame, participant_id, mkey, normalize, fkey):
    return reader_vs_cohort_values(
        _frame, participant_id, MEASURES[mkey], normalize=normalize
    )


# --- Cross-cutting analysis controls -----------------------------------------

_AGG_OPTIONS = ["mean", "median", "sum"]

_SPREAD_OPTIONS = ["SD", "SEM", "IQR", "Bootstrap CI"]


def _pretty_col(col: str) -> str:
    """Friendly label for a raw column id (group-definition pickers).

    A metadata option (``meta:`` / ``trialmeta:`` / ``textmeta:``) is labelled
    with the field's own label and marked with the table it came from — the
    provenances answer different questions ("this trial's condition" vs "this
    reader's language" vs "this text's genre") and a picker that hid the
    difference would invite the wrong one.
    """
    meta = _meta_field(col)
    if meta is not None:
        from scanpath_studio import metadata as md

        grain, name = meta
        # `metadata.field_label`, not the attached table's own `field.label`:
        # a `format_func` can be called when `md.active()` is out of reach (no
        # script run — Streamlit's own widget-state bookkeeping does this), and
        # a label that changes with the caller's context is a label that flickers.
        return f"{_META_GRAIN_MARKS[grain]} {md.field_label(name)}"
    if isinstance(col, tuple):
        return " × ".join(_pretty_col(part) for part in col)
    # A mapped role is named by its role, as on the Scanpath view; its
    # source column goes in the picker's tooltip (`field_help`).
    return active_all(st.session_state).field_label(col)


def _measure_picker(
    words,
    fixations,
    *,
    key,
    host=None,
    per_word_only=False,
    fixation_only=False,
    label="Measure",
) -> Measure | None:
    """The shared measure picker — TFD default, only present columns.

    ``fixation_only`` offers just the per-fixation measures, for a view that
    plots fixations one by one."""
    host = host or st
    ms = available_measures(words, fixations, per_word_only=per_word_only)
    if fixation_only:
        ms = [m for m in ms if m.frame == "fixations"]
    if not ms:
        host.info("No aggregatable measures found in this dataset.")
        return None
    labels = {m.label: m.key for m in ms}
    options = list(labels)
    if (
        key in ("cmp_measure", "pgrp_measure")
        and st.session_state.get(key) not in options
    ):
        # A word profile cannot use a fixation measure carried into Groups.
        word_measure = MEASURES.get(st.session_state.get(CORPUS_MEASURE))
        if word_measure is not None and word_measure.label in labels:
            st.session_state[key] = word_measure.label
    _drop_stale(key, options)
    default = "Total fixation duration — TFD"
    index = options.index(default) if default in options else 0
    measure = MEASURES[labels[st.session_state.get(key) or options[index]]]
    entry = measure_entry(measure.column)
    unit = (entry.unit if entry else "") or measure.unit or "count"
    about = f"{measure_description(measure.column)} Unit: {unit}."
    if measure.column in UNFIXATED_BLANK_MEASURES:
        about += " Words the reader never fixated have no value."
    chosen = host.selectbox(
        label,
        options=options,
        index=index,
        key=key,
        persist_state="session",
        help=about,
    )
    return MEASURES[labels[chosen]]


#: Corpus Analysis views whose numbers the app computes from the fixations
#: (reading speed, regression rate, landing positions, the summary tables)
#: rather than reading them from the dataset. Shown only when
#: `constants.computed_measures_enabled`.
_COMPUTED_READER_VIEWS = frozenset(
    {
        "Reading summary",
        "Progressive vs regressive",
        "Landing-position curve",
        "Participant summary table",
    }
)


def _chart_settings(host):
    """The chart choice and options for the current detailed analysis."""
    return host.popover("Chart settings", icon=ICONS["settings"], on_change="rerun")


#: Appended to a measure note when the values are z-scored.
_Z_NOTE = " Values are in standard deviations from each participant’s mean."


def _observation(measure: Measure, normalize: bool = False) -> str:
    """What one value of a raw-value view (a distribution) is."""
    one = (
        "Each value is one fixation."
        if measure.frame == "fixations"
        else "Each value is one word in one trial."
    )
    return one + (_Z_NOTE if normalize and not measure.is_rate else "")


# What each error-bar choice shows, in one line: SD and IQR describe how the
# values vary, SEM and the bootstrap CI how precisely the center is known.
_SPREAD_NOTES = {
    "SD": "SD: how much the values vary (±1 standard deviation).",
    "SEM": "SEM: how precisely the center is known (SD ÷ √n).",
    "IQR": "IQR: the middle half of the values (25th to 75th percentile).",
    "Bootstrap CI": "Bootstrap CI: a 95% interval for the center, from "
    "resampling the values.",
}


def _spread_note(host, spread: str, agg: str | None = None) -> None:
    """One caption under an error-bar selector saying what the choice shows.

    With Aggregate = sum, SD, SEM and IQR are drawn as a bootstrap interval of
    the sum (`aggregation.spread_bounds`), so the note says that instead."""
    note = _SPREAD_NOTES.get(spread)
    if effective_spread(spread, agg) != spread:
        note = (
            "With Sum, SD, SEM and IQR are drawn as a 95% bootstrap interval "
            "of the sum."
        )
    if note:
        host.caption(note)


def _normalize_toggle(host, *, key, disabled=False):
    """Z-score-per-participant toggle."""
    enabled = host.toggle(
        "Z-score per participant",
        key=key,
        disabled=disabled,
        persist_state="session",
        help="Each participant's values minus their mean, divided by their "
        "SD. Compares participants' patterns with their overall level removed.",
    )
    return enabled and not disabled


def _min_readers_input(host, *, key, label="Min participants per word", default=1):
    """Min-observations guard."""
    return int(
        host.number_input(
            label,
            min_value=1,
            max_value=999,
            value=default,
            step=1,
            key=key,
            persist_state="session",
            help="Hide words that fewer participants than this have a value for.",
        )
    )


def _download_tidy(
    host, df, *, name, key, label="Download table (CSV)", recipe=None, in_panel=False
):
    """Per-view tidy-table download, with its recipe beside it.

    ``recipe`` is the view's own choices — the keyword arguments of
    `analysis_recipe.analysis_choices`, plus ``counts`` for what the view
    already counted. The recipe adds the page's dataset, trial filters and pool
    (`_RECIPE_CONTEXT`); outside the page, or with no ``recipe``, the CSV
    downloads alone.
    """
    if df is None or getattr(df, "empty", True):
        return
    downloads = host
    if not in_panel:
        downloads = host.popover(
            "Download results", icon=ICONS["download"], key=f"{key}_downloads"
        )
    context = _RECIPE_CONTEXT.get()
    # Written on click, not on every rerun: a words × readers table on a full
    # corpus takes most of a second to serialize. Under the dataset's own
    # names, as on screen — the map is read here, where the session is.
    names = active_all(st.session_state).identity()
    csv = partial(_tidy_csv, df, names)
    button = dict(data=csv, file_name=name, mime="text/csv", key=key, on_click="ignore")
    if recipe is None or context is None:
        downloads.download_button(label, **button)
        return
    recipe = dict(recipe)
    counts = result_counts(df, recipe.pop("counts", None))
    replayable = (context.get("section"), recipe.get("view")) in REPLAYABLE_VIEWS
    result_csv = None
    if replayable:
        entry = (st.session_state.get("_datasets") or {}).get(
            context.get("dataset", {}).get("source")
        )
        inputs = (
            stored_source_recipe(entry)
            if entry
            else {"schemas": st.session_state.get("_active_column_mapping") or {}}
        )
        # Only the mapping and file transformations travel. A local session-set path does not.
        tables = ("words", "fixations", "raw_gaze")
        mapping = {
            t: inputs["schemas"][t]
            for t in tables
            if (inputs.get("schemas") or {}).get(t)
        }
        choices = (entry or {}).get("wizard_choices") or {}
        derivations = choices.get("filename_derive") or {}
        keep = (choices.get("keep_and_filter") or {}).get("wizard_keep_extra") or []
        context = {
            **context,
            "inputs": {
                "schemas": mapping,
                "steps": inputs.get("steps") or [],
                "derive": derivations.get("applied")
                if (derivations.get("widgets") or {}).get("wizard_filename_split", True)
                else None,
                "keep_columns": keep,
            },
        }
        result_csv = csv
        # Record the app's headers even if the runner loads canonical tables.
        counts["headers"] = as_written(df.iloc[:0], names).columns.tolist()
    row = downloads.container(horizontal=True, gap="small")
    row.download_button(label, **button)
    if recipe.get("view") == "Cohort profile":
        from .cohort_audit import profile_methods

        row.download_button(
            "Methods draft",
            data=lambda: profile_methods(
                json.loads(_recipe_json(context, recipe, name, counts))
            ),
            file_name="cohort_methods.txt",
            mime="text/plain",
            key=f"{key}_methods",
            on_click="ignore",
        )
    row.download_button(
        "Download recipe (JSON)",
        data=partial(_recipe_json, context, recipe, name, counts, result_csv),
        file_name=recipe_file_name(name),
        mime="application/json",
        key=f"{key}_recipe",
        on_click="ignore",
        help="Reproduce this table with scanpath-studio recipe and the same source files."
        if replayable
        else (
            "A record of the dataset name, trial filters, analysis choices and counts"
            " used for this table. Keep your data separately; the recipe contains no "
            "data rows or figure settings."
        ),
    )


def _tidy_csv(df: pd.DataFrame, names: ColumnNames) -> bytes:
    """A tidy table's CSV, built when its download button is clicked."""
    return (
        as_written(df, names).to_csv(index=False, lineterminator="\n").encode("utf-8")
    )


def _recipe_json(
    context: dict, recipe: dict, name: str, counts: dict, result_csv=None
) -> str:
    """The recipe file's text, built when the button is clicked.

    ``recipe["groups"]`` holds ``(label, spec)`` pairs, resolved here: a
    trial-metadata cohort's spec lists every matching reading, too many to
    serialize on every rerun.
    """
    from datetime import datetime

    from scanpath_studio import __version__

    recipe = dict(recipe)
    if recipe.get("groups"):
        recipe["groups"] = [group_definition(*pair) for pair in recipe["groups"]]
    analysis = analysis_choices(section=context.get("section"), **recipe)
    if result_csv is not None:
        counts = {**counts, "sha256": hashlib.sha256(result_csv()).hexdigest()}

    return json.dumps(
        build_analysis_recipe(
            app_version=__version__,
            dataset=context.get("dataset") or {},
            inputs=context.get("inputs"),
            trial_filters=context.get("trial_filters") or [],
            pool=context.get("pool") or {},
            analysis=analysis,
            selection=context.get("selection")
            if (analysis.get("section"), analysis.get("view")) in REPLAYABLE_VIEWS
            else None,
            table_file=name,
            counts=counts,
            exported_at=datetime.now().isoformat(timespec="seconds"),
        ),
        indent=2,
    )


#: Cell text of the "open this trial" button. `st.column_config.ButtonColumn`
#: takes the button's label from the cell *value*, so this is data, not config.
_OPEN_TRIAL_LABEL = f"{ICONS['open']} Open"


def _render_trials_with_open_button(
    trials: pd.DataFrame, participant: str | None, *, key: str
) -> None:
    """A per-trial summary table whose rows open the trial.

    Corpus Analysis lists a reader's trials with their numbers; a
    `ButtonColumn` puts the jump to the Scanpath view in the row it belongs to,
    rather than leaving the user to find the id in the picker.

    The click arrives as a *callback*, before the script rebuilds ``combos``, so
    it can't seed the picker itself — it parks the request via
    ``url_state.request_trial`` and ``app.main`` applies it once the trial pool
    exists, the same hop a ``?trial_id=`` deep link takes.
    """
    # The identity columns under the dataset's own names.
    headers = (
        column_label_config(trials.columns, active_all(st.session_state).identity())
        if trials is not None
        else {}
    )
    if trials is None or trials.empty or "trial_id" not in trials.columns:
        st.dataframe(trials, width="stretch", hide_index=True, column_config=headers)
        return
    click_key = f"{key}_open_trial_click"
    # `click["row"]` is a position in the frame we hand to `st.dataframe`, not in
    # whatever order the user has clicked the table's headers into — the same
    # source-position semantics as dataframe *selections* (Streamlit's own
    # ButtonColumn example indexes `df.iloc[click["row"]]`). So a parallel list
    # built from that frame stays correct under client-side sorting.
    ids = trials["trial_id"].astype(str).tolist()

    def _open() -> None:
        # Imported at call time, like the PLOT_CONFIG_SCHEMA read above:
        # `url_state` imports nothing from here, and this keeps it that way.
        from scanpath_studio.url_state import request_trial

        click = st.session_state.get(click_key)
        row = click["row"] if click else None
        if row is not None and 0 <= row < len(ids):
            request_trial(participant, ids[row])

    shown = trials.copy()
    shown.insert(0, "Open", _OPEN_TRIAL_LABEL)
    st.dataframe(
        shown,
        width="stretch",
        hide_index=True,
        column_config={
            **headers,
            "Open": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="Show this trial's scanpath in the Scanpath View.",
                on_click=_open,
                key=click_key,
            ),
        },
    )


def _apply_min_readers(host, df, min_readers, *, key):
    """Drop under-supported word rows and caption the count."""
    if df is None or df.empty or "enough" not in df.columns or min_readers <= 1:
        return df
    dropped = int((~df["enough"]).sum())
    out = df[df["enough"]]
    if dropped:
        host.caption(
            f"{ICONS['warning']} {plural(dropped, 'word')} hidden: fewer than "
            f"{plural(min_readers, 'participant')} had a value."
        )
    else:
        host.caption(
            f"Every word meets the minimum of {plural(min_readers, 'participant')}."
        )
    return out


_RATE_NAMES = {"skip_rate": "skip rate", "regression_in_rate": "regression-in rate"}


def _apply_rate_min_readers(host, df, min_readers, *, key):
    """The min-readers guard for the per-word rates, one series at a time.

    Each rate has its own readers (`aggregation.word_rate_profile`): a word can
    have a well-supported skip rate and a regression-in rate from one reader.
    A rate below the guard is blanked, not the word, and a word is dropped only
    when neither rate is left; the caption counts each series."""
    if df is None or df.empty:
        return df
    out = df.copy()
    notes = []
    for rate, _n, enough in RATE_SERIES:
        if rate not in out.columns or enough not in out.columns:
            continue
        hidden = ~out[enough] & out[rate].notna()
        out[rate] = out[rate].where(out[enough])
        if min_readers > 1 and hidden.any():
            notes.append(f"{_RATE_NAMES[rate]} for {plural(int(hidden.sum()), 'word')}")
    out = out[out[[r for r, _n, _e in RATE_SERIES]].notna().any(axis=1)]
    if notes:
        host.caption(
            f"{ICONS['warning']} Hidden for having fewer than "
            f"{plural(min_readers, 'participant')}: {'; '.join(notes)}. Each rate "
            "counts only the participants with a value for it."
        )
    return out


# --- Group definition --------------------------------------------------------
# Two modes: *split a field* — pick one categorical
# column and assign its values to A vs B — and *independent filter sets* — a full
# participant/text/condition picker per group. Both reduce to a group ``spec``
# (``{column: [allowed values]}``) consumed by ``aggregation.group_mask``.

_GROUP_SPLIT_CANDIDATES = (
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    "genre",
    "session",
    "pp_gender",
    "participant_id",
)
_FILTER_SET_FIELDS = (
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    "genre",
    "session",
)


#: A group field that lives on an attached metadata table rather than on the
#: word/fixation frames — the participant, trial or text table. One prefix per
#: grain keeps one flat picker while making the provenances impossible to
#: confuse — both in the UI and in the code that has to translate one of them.
#: The participant prefix stays the bare ``meta:``: it is the value an
#: existing ``pgrp_field`` / ``cmp_field`` selectbox holds, and each grain's
#: own prefix mirrors its trial-filter key (``filter_meta_`` / ``filter_trialmeta_`` /
#: ``filter_textmeta_``), so a column name shared by two tables stays two options.
_META_FIELD_PREFIX = "meta:"
_TRIAL_META_FIELD_PREFIX = "trialmeta:"
_TEXT_META_FIELD_PREFIX = "textmeta:"
_META_PREFIXES = (
    (_metadata_mod.GRAIN_PARTICIPANT, _META_FIELD_PREFIX),
    (_metadata_mod.GRAIN_TRIAL, _TRIAL_META_FIELD_PREFIX),
    (_metadata_mod.GRAIN_TEXT, _TEXT_META_FIELD_PREFIX),
)
#: The mark `_pretty_col` puts before a metadata field — the `constants.ICONS`
#: concept each table already has (`participant` / `trial_metadata` /
#: `text_metadata`), as the emoji a `format_func`'s plain-text label can carry.
_META_GRAIN_MARKS = {
    _metadata_mod.GRAIN_PARTICIPANT: "👤",
    _metadata_mod.GRAIN_TRIAL: "📋",
    _metadata_mod.GRAIN_TEXT: "📄",
}
#: Each grain's accessor and value lister in `metadata`, looked up **by name**
#: at call time so the attached table is always the live one.
_META_GRAIN_API = {
    _metadata_mod.GRAIN_PARTICIPANT: ("active", "options_for"),
    _metadata_mod.GRAIN_TRIAL: ("active_trials", "trial_options_for"),
    _metadata_mod.GRAIN_TEXT: ("active_texts", "text_options_for"),
}
#: The spec key a trial-grain cohort resolves to: one reading is a reader *and*
#: a trial, which two independent column constraints cannot say (see
#: `aggregation.group_mask`'s composite keys).
_TRIAL_KEY_COLUMNS = ("participant_id", "trial_id")


def _meta_field(option) -> tuple[str, str] | None:
    """``(grain, field)`` behind a metadata picker option, ``None`` for a column."""
    if not isinstance(option, str):
        return None
    for grain, prefix in _META_PREFIXES:
        if option.startswith(prefix):
            return grain, option[len(prefix) :]
    return None


def _meta_table(grain: str):
    """The attached table of ``grain``, or ``None``."""
    return getattr(_metadata_mod, _META_GRAIN_API[grain][0])()


def _meta_options(grain: str, name: str) -> list[str]:
    """Distinct values of one attached field, over the *loaded* rows only."""
    return getattr(_metadata_mod, _META_GRAIN_API[grain][1])(_meta_table(grain), name)


def _metadata_group_fields() -> list[str]:
    """Prefixed picker options for the attached tables' groupable fields.

    Categorical fields, plus a numeric one with few enough distinct values to
    read as a category (a birth year, a session number). A wide-ranging numeric
    field is a *range* question and belongs in the trial filters, which already
    have the slider for it. Reader fields first, then trial, then text — the
    trial filters' *By reader / By trial / By text* order.
    """
    out = []
    for grain, prefix in _META_PREFIXES:
        table = _meta_table(grain)
        if table is None or table.frame.empty:
            continue
        for field in table.fields:
            if 2 <= len(_meta_options(grain, field.name)) <= 60:
                out.append(f"{prefix}{field.name}")
    return out


def _both_frame_values(words, fixations, col):
    """Distinct values of ``col`` — a frame column, or a metadata field."""
    meta = _meta_field(col)
    if meta is not None:
        return _meta_options(*meta)
    frames = [f for f in (fixations, words) if col in getattr(f, "columns", [])]
    if not frames:
        return []

    def choices():
        vals = set()
        for frame in frames:
            vals.update(frame[col].dropna().astype(str).unique())
        return sorted(vals)

    return frame_cache(
        f"corpus_field_values_{col}",
        tuple(frame_fingerprint(frame) for frame in frames),
        choices,
    )


def _group_text_column(words, fixations) -> str:
    """The frame column a text-grain cohort narrows — the *By text* filter's.

    `controls._text_field_and_frame`'s order (``unique_text_id`` before
    ``text_id``), which is also the id `utils.build_combo_options` copies into
    ``combos["text_id"]`` and so the one the text table was joined against.
    """
    empty = pd.DataFrame()
    field, _frame = _text_field_and_frame(
        words if words is not None else empty,
        fixations if fixations is not None else empty,
    )
    return field or "text_id"


def _group_spec(col: str, values, words=None, fixations=None) -> dict:
    """One ``{column: values}`` group spec — the metadata translation lives here.

    The rule is that a participant-grain constraint **is** a participant
    constraint: the table is never broadcast onto the word/fixation frames, so a
    group defined on "native language = Hebrew" resolves to the set of readers
    whose row says Hebrew, and the spec `aggregation.group_mask` sees is an
    ordinary ``participant_id`` one. Nothing downstream needs to know.

    The same rule applies one and two grains over, the way the Scanpath
    trial filters do: a **trial** field resolves through
    `metadata.trials_matching` to the ``(participant_id, trial_id)`` readings it
    describes (a composite spec key — a trial-id-keyed table expands to every
    reading of that trial, which is why the loaded keys come from ``words`` /
    ``fixations``), and a **text** field through `metadata.texts_matching` to
    text ids on the *By text* filter's column. Every resolution is an ordinary
    spec entry, so it ANDs with reader-level fields and frame columns alike.

    An empty selection is "no constraint" and returns ``{}``, matching the frame
    branch — but a selection that matches *nobody* must return an impossible
    spec rather than ``{}``, or a group that should be empty would silently
    select every row.
    """
    if not values:
        return {}
    meta = _meta_field(col)
    if meta is None:
        return {col: values}
    grain, name = meta
    table = _meta_table(grain)
    selection = {name: list(values)}
    if grain == _metadata_mod.GRAIN_TRIAL:
        column = _TRIAL_KEY_COLUMNS
        loaded = set()
        for frame in (words, fixations):
            if frame is not None and not frame.empty:
                loaded |= _c_trial_keys(frame, frame_fingerprint(frame))
        ids = _metadata_mod.trials_matching(table, selection, keys=loaded)
    elif grain == _metadata_mod.GRAIN_TEXT:
        column = _group_text_column(words, fixations)
        ids = _metadata_mod.texts_matching(table, selection)
    else:
        column = "participant_id"
        ids = _metadata_mod.participants_matching(table, selection)
    if ids is None:
        # No table (detached mid-run), so the field this group was defined on no
        # longer exists. Fail *closed*: silently widening a cohort to everyone is
        # the one outcome that produces a plausible, wrong comparison.
        return {column: [_no_match(column)]}
    return {column: sorted(ids) or [_no_match(column)]}


def _no_match(column):
    """A value no dataset can hold in ``column`` — see `_group_spec`."""
    if isinstance(column, tuple):
        return tuple(_NO_SUCH_PARTICIPANT for _ in column)
    return _NO_SUCH_PARTICIPANT


def _merge_spec(spec: dict, column, values) -> None:
    """Add one ``column: values`` constraint to ``spec``, intersecting a repeat.

    Two metadata fields (or a metadata field and an explicit pick) can land on
    the same column — two reader fields on ``participant_id``, a text field and
    the *Texts* pick on the text column — so they have to intersect rather than
    the later one overwriting the earlier. An empty intersection is the
    impossible-id sentinel, never ``[]``: `group_mask` reads an empty value list
    as "no constraint" and would select every row.
    """
    if column not in spec:
        spec[column] = values
        return

    def _norm(value):
        return tuple(map(str, value)) if isinstance(column, tuple) else str(value)

    merged = {_norm(v) for v in spec[column]} & {_norm(v) for v in values}
    spec[column] = sorted(merged) or [_no_match(column)]


#: A reader id no dataset can hold, so `group_mask` selects nothing. Used when a
#: metadata group matches nothing loaded — see `_group_spec`.
_NO_SUCH_PARTICIPANT = "\x00__no_such_participant__"


def _group_split_columns(words, fixations):
    """Categorical fields with 2…60 values in either table or its metadata."""
    text_col = corpus_text_column(words) or corpus_text_column(fixations)
    candidates = list(_GROUP_SPLIT_CANDIDATES) + ([text_col] if text_col else [])
    out = [
        col
        for col in dict.fromkeys(candidates)
        if 2 <= len(_both_frame_values(words, fixations, col)) <= 60
    ]
    return out + _metadata_group_fields()


def _join_label(values):
    vals = [str(v) for v in (values or [])]
    if not vals:
        return ""
    return vals[0] if len(vals) == 1 else f"{vals[0]} +{len(vals) - 1}"


def _group_name(col, values) -> str:
    """A split group's name: its field and values (a bare ``True`` or ``2``
    names nothing in a legend)."""
    joined = _join_label(values)
    return f"{_pretty_col(col)} = {joined}" if joined else ""


def _render_filter_set(words, fixations, *, key, default_label, host):
    """One independent group's filter-set picker → ``(spec, label)``."""
    spec = {}
    label = host.text_input(
        "Group name",
        placeholder=default_label,
        key=f"{key}_label",
        persist_state="session",
    )
    text_col = corpus_text_column(fixations) or corpus_text_column(words)
    for col, pretty in (
        ("participant_id", "Participants"),
        (text_col, "Texts"),
        *[(c, _pretty_col(c)) for c in _FILTER_SET_FIELDS],
        # The attached reader, trial and text tables' fields
        # are offered here too, translated to keys by `_group_spec`.
        *[(c, _pretty_col(c)) for c in _metadata_group_fields()],
    ):
        if not col:
            continue
        opts = _both_frame_values(words, fixations, col)
        if len(opts) < 2 or len(opts) > 400:
            continue
        sel = host.multiselect(
            pretty,
            opts,
            key=f"{key}_{col}",
            placeholder="All",
            persist_state="session",
            help=field_help(col, active_all(st.session_state)) or None,
        )
        for column, values in _group_spec(col, sel, words, fixations).items():
            _merge_spec(spec, column, values)
    return spec, (label or default_label)


def _cohort_reading_keys(
    fixations: pd.DataFrame | None, words: pd.DataFrame | None, spec=None
) -> pd.MultiIndex:
    """The readings in the cohort, in either table.

    A reading only one table has is the cohort's too — so an AOI-only dataset's
    cohort does not read "0 readers" beside charts drawn from its readers — and
    a field only one table carries selects the same readers from both. Read off
    the tables' distinct readings (`data.distinct_key_codes`, remembered per
    frame), not their rows, once ``spec`` is resolved to the reading key
    (`_resolve_cohort`).
    """
    readings = None
    for frame in (fixations, words):
        if frame is None or frame.empty or not set(_TRIAL_KEY_COLUMNS) <= set(frame):
            continue
        keys = distinct_key_codes(frame, _TRIAL_KEY_COLUMNS)[1]
        readings = keys if readings is None else readings.union(keys, sort=False)
    if readings is None:
        return pd.MultiIndex.from_arrays([[], []], names=_TRIAL_KEY_COLUMNS)
    if spec:
        mask = np.ones(len(readings), dtype=bool)
        for column, values in _resolve_cohort(spec, words, fixations).spec.items():
            if not values:
                continue
            if column == _TRIAL_KEY_COLUMNS:
                mask &= readings.isin({tuple(map(str, v)) for v in values})
            else:  # a participant pick — the one other reading-key constraint
                level = readings.get_level_values(column)
                mask &= level.isin({str(v) for v in values})
        readings = readings[mask]
    return readings


def _cohort_reader_ids(fixations, words, spec=None) -> set[str]:
    readings = _cohort_reading_keys(fixations, words, spec)
    return set(readings.get_level_values("participant_id"))


def _cohort_readers(
    fixations: pd.DataFrame | None, words: pd.DataFrame | None, spec=None
) -> int:
    """How many readers a cohort holds (see ``_cohort_reader_ids``)."""
    return len(_cohort_reader_ids(fixations, words, spec))


def _n_readers(count: int) -> str:
    return plural(count, "participant")


def _render_group_definition(words, fixations, *, key, two_groups, host=None):
    """Return each group's spec and label. An incomplete split has no spec.

    An empty filter set is a complete definition covering all selected trials.
    """
    host = host or st
    editor = "Edit groups" if two_groups else "Edit group"
    mode = host.radio(
        "Define groups by",
        ["Split a field", "Independent filter sets"],
        key=f"{key}_mode",
        persist_state="session",
        horizontal=True,
        help="Split one categorical column into groups, or build each group from "
        "a participant, text or condition filter.",
    )
    if mode == "Split a field":
        cols = _group_split_columns(words, fixations)
        if not cols:
            st.info(
                f"No field is available to split for these trials. Open **{editor}** and choose "
                "**Independent filter sets** to define a group using filters."
            )
            return (None, None, "Group A", "Group B") if two_groups else (None, "Group")
        # Detaching a metadata table removes its `meta:` options; without
        # this Streamlit falls back to the first option silently and the cohort
        # on screen changes with no notice (`controls._drop_stale`'s job).
        _drop_stale(f"{key}_field", cols)
        picked = st.session_state.get(f"{key}_field")
        col = host.selectbox(
            "Field",
            cols,
            key=f"{key}_field",
            format_func=_pretty_col,
            persist_state="session",
            help=field_help(
                picked if picked in cols else cols[0], active_all(st.session_state)
            )
            or None,
        )
        vals = _both_frame_values(words, fixations, col)
        if two_groups:
            a = host.multiselect(
                f"Group A — {_pretty_col(col)}",
                vals,
                default=None if f"{key}_a" in st.session_state else vals[:1],
                key=f"{key}_a",
                persist_state="session",
            )
            rest = [v for v in vals if v not in a]
            b = host.multiselect(
                f"Group B — {_pretty_col(col)}",
                vals,
                default=None if f"{key}_b" in st.session_state else rest[:1],
                key=f"{key}_b",
                persist_state="session",
            )
            if not a or not b:
                st.info(
                    "Open **Edit groups** and choose at least one value for each group to see the comparison."
                )
                return None, None, "Group A", "Group B"
            return (
                _group_spec(col, a, words, fixations),
                _group_spec(col, b, words, fixations),
                _group_name(col, a),
                _group_name(col, b),
            )
        sel = host.multiselect(
            f"Values for {_pretty_col(col)}",
            vals,
            default=None if f"{key}_g" in st.session_state else vals[:1],
            key=f"{key}_g",
            persist_state="session",
        )
        if not sel:
            st.info(
                "Open **Edit group** and choose at least one value to see its results."
            )
            return None, "Group"
        return _group_spec(col, sel, words, fixations), _group_name(col, sel)
    # Independent filter sets.
    host.caption("A group with no filters includes all selected trials.")
    if two_groups:
        first, second = host.tabs(["Group A", "Group B"])
        sa, la = _render_filter_set(
            words, fixations, key=f"{key}_setA", default_label="Group A", host=first
        )
        sb, lb = _render_filter_set(
            words, fixations, key=f"{key}_setB", default_label="Group B", host=second
        )
        return sa, sb, la, lb
    spec, label = _render_filter_set(
        words, fixations, key=f"{key}_set0", default_label="Group", host=host
    )
    return spec, label


def _resolve_cohort(spec, words, fixations) -> GroupResolution:
    """``spec`` resolved to readings (`aggregation.resolve_group_spec`).

    Resolved to readings, a field on the Words table constrains the fixation
    measures too, rather than the words alone. Resolved once per pool
    and group — a `frame_cache` holding A's and B's, so a rerun regroups
    nothing — and the readings stand in for the fields from here on.
    """
    if not any(v and not on_reading_key(c) for c, v in (spec or {}).items()):
        return resolve_group_spec(spec, words, fixations)
    key = (
        frame_fingerprint(words),
        frame_fingerprint(fixations),
        hashable_key(spec),
    )

    def _build() -> GroupResolution:
        progress.report()  # a miss is work: the Corpus card may show
        return resolve_group_spec(spec, words, fixations)

    return frame_cache("cohort_readings", key, _build, keep=3)


def _cohort_unavailable(host, cohorts) -> bool:
    """Say why a group cannot be formed, and what it leaves out; ``True`` = stop.

    ``cohorts`` are ``(label, GroupResolution)`` pairs. A field neither table
    carries makes the group unavailable rather than everyone; a reading the
    tables disagree on is left out of the group, and said so.
    """
    names = active_all(st.session_state)
    blocked = False
    for label, cohort in cohorts:
        if cohort.missing:
            blocked = True
            fields = ", ".join(_pretty_col(c) for c in cohort.missing)
            host.warning(
                f"**{label}** cannot be formed: {fields} is in neither the Words "
                "nor the Fixations table of the current pool. Pick another field."
            )
        if cohort.conflicts:
            host.warning(
                trial_filter_conflict_note(
                    cohort.conflicts, names.label, subject=f"**{label}**"
                )
            )
    return blocked


def _corpus_unavailable_notice(
    *, has_aoi_table: bool, has_raw_gaze: bool, can_remap_builtin: bool
) -> None:
    """The Corpus Analysis page when the dataset contains no reading measures.

    The page computes no measure of its own, so without an uploaded one there is
    nothing for any of its sections to show. It says so, points at where the
    measures are mapped, and draws its sections greyed so what it *would* offer
    stays visible.

    A dataset with **no Words table at all** — raw gaze only, or fixations
    only — has nowhere to map a measure, so it is told that instead, and a
    raw-gaze one is told that the samples carry no measures either."""
    stored = _active_stored_dataset() is not None
    can_map_measures = has_aoi_table and (stored or can_remap_builtin)
    if not has_aoi_table:
        where = (
            "Choose **Add a Words table** to attach it to this dataset."
            if stored
            else "Choose **Add dataset** to import a report that includes one."
        )
        samples = (
            " Raw gaze samples do not include per-word reading measures."
            if has_raw_gaze
            else ""
        )
        st.info(
            f"{ICONS['info']} **This dataset has no Words table.** "
            "To compare readings, add a Words table with per-word measures such as "
            f"total fixation duration.{samples} {where}"
        )
    else:
        where = (
            "Choose **Map reading measures**, then select the column that records "
            "a measure such as first fixation duration in your Words table."
            if can_map_measures
            else "This dataset is built in. Choose **Bundled demo** to try the analysis, "
            "or use **Add dataset** to import a Words table with per-word measures."
        )
        st.info(f"{ICONS['info']} **No reading measures are mapped.** {where}")
    if can_map_measures or stored:
        st.button(
            "Map reading measures" if has_aoi_table else "Add a Words table",
            icon=ICONS["edit"] if has_aoi_table else ICONS["add"],
            key="corpus_map_measures",
            on_click=_open_measure_mapping,
        )
    sections = "".join(
        f'<span class="sps-corpus-off-tab">{html.escape(name)}</span>'
        for name in corpus_navigation.destinations()
    )
    st.markdown(
        f'<div class="sps-corpus-off" aria-disabled="true">{sections}</div>',
        unsafe_allow_html=True,
    )


def _open_measure_mapping() -> None:
    """Take the user to ✏️ Edit dataset, where the measures are mapped."""
    from scanpath_studio.app import _open_mapping_editor
    from scanpath_studio.url_state import _go_data

    _open_mapping_editor()
    _go_data()


def _render_pool_filters(
    host,
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    raw_gaze_all: pd.DataFrame | None,
) -> None:
    """Every trial filter, into ``host`` — the one panel both views open.

    The Scanpath picker's funnel and Corpus Analysis' *Edit filters*
    draw the same widgets under the same ``filter_*`` keys; only one view runs
    per rerun, so the keys never meet.
    """
    words, fixations = pool_filter_frames(words_all, fixations_all, raw_gaze_all)
    render_narrow_by(words, fixations, raw_gaze_all, text_host=host, part_host=host)
    render_trial_filters(words, fixations, raw_gaze_all, host=host)


def pool_filter_frames(
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    raw_gaze_all: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The ``(words, fixations)`` the trial filters are offered from.

    A raw-gaze-only dataset's readers and trials are in its samples,
    so that is what the filters are offered from (and what `app.main` narrows
    with them); beside fixations or words the samples follow those tables'
    filters instead. Shared with the empty-pool panel's per-filter Clear,
    which re-derives the filters from the same frames.
    """
    if (
        words_all.empty
        and fixations_all.empty
        and raw_gaze_all is not None
        and not raw_gaze_all.empty
    ):
        return words_all, raw_gaze_all
    return words_all, fixations_all


def _count_noun(n: int, noun: str) -> str:
    return f"{n:,} {noun}{'' if n == 1 else 's'}"


def pool_count_text(
    trials: int, trials_total: int, readers: int, readers_total: int
) -> str:
    """``12 of 24 trials · 1 of 2 readers`` — the analysis pool against the
    dataset. An unnarrowed pool is just ``24 trials · 2 readers``; a
    dataset that names no readers leaves the reader half out."""
    whole = trials == trials_total and readers == readers_total
    parts = [(trials, trials_total, "trial")]
    if readers_total:
        parts.append((readers, readers_total, "participant"))
    return " · ".join(
        _count_noun(n, noun) if whole else f"{n:,} of {_count_noun(total, noun)}"
        for n, total, noun in parts
    )


def _n_unique_readers(combos: pd.DataFrame | None) -> int:
    if combos is None or combos.empty or "participant_id" not in combos:
        return 0
    return int(combos["participant_id"].astype(str).nunique())


def data_scope_text(
    combos: pd.DataFrame,
    combos_all: pd.DataFrame,
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
) -> str | None:
    """Explain an active Scanpath filter once, wherever its results are shown."""
    if not has_active_trial_filters():
        return None
    described = ", ".join(
        md_literal(format_filter_item(i))
        for i in active_filter_items(words_all, fixations_all)
    )
    count = f"{len(combos):,} of {plural(len(combos_all), 'trial')}"
    note = f"Scanpath filters include {count}."
    return f"{note} {described}" if described else note


def render_data_scope(text: str | None, *, key: str) -> None:
    """Draw `data_scope_text` as a caption over the counts it describes."""
    if text:
        st.container(key=key).caption(f"{ICONS['trial_filter']} {text}")


def render_analysis_pool_bar(
    host,
    *,
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    raw_gaze_all: pd.DataFrame | None,
    combos: pd.DataFrame,
    combos_all: pd.DataFrame,
    show_inclusion: Callable[[], None] | None = None,
) -> dict:
    """The pool Corpus Analysis reads, on one line, with its filters.

    Filters set on the Scanpath view narrow this page too, so it says so —
    otherwise a reader filtered out there would simply be missing here. The
    counts are the trial picker's pool (``combos``) against the Export subtab's *All*
    (``combos_all``), so all three views count the same trials, and **Edit
    filters** opens the Scanpath funnel's own panel.

    Returns what it showed — the filters and the counts — for the table recipes,
    so the file and the line on screen cannot disagree.
    """
    active = has_active_trial_filters()
    pool = {
        "trials": len(combos),
        "trials_in_dataset": len(combos_all),
        "readers": _n_unique_readers(combos),
        "readers_in_dataset": _n_unique_readers(combos_all),
    }
    counts = pool_count_text(
        pool["trials"],
        pool["trials_in_dataset"],
        pool["readers"],
        pool["readers_in_dataset"],
    )
    items = active_filter_items(words_all, fixations_all) if active else []
    described = " · ".join(md_literal(format_filter_item(i)) for i in items)
    text = f"**{counts}**"
    if described:
        text += f" · {described}"
    bar = host.container(
        key="corpus_pool_bar",
        horizontal=True,
        width="content",
        vertical_alignment="center",
        gap="small",
    )
    bar.markdown(text, width="content")
    pop = bar.popover(
        "Edit filters",
        icon=ICONS["trial_filter"],
        width="content",
        help="The same trial filters the Scanpath View uses.",
        key=_POOL_POPOVER_KEY,
        on_change="rerun",
    )
    if pop.open:
        _render_pool_filters(
            pop.container(key="corpus_pool_filters"),
            words_all,
            fixations_all,
            raw_gaze_all,
        )
        if show_inclusion is not None:
            with pop:
                show_inclusion()
    if active:
        bar.button(
            "Clear",
            icon=ICONS["close"],
            key="corpus_pool_clear",
            on_click=_clear_pool_filters,
            width="content",
            help="Clear all trial filters, here and on the Scanpath View.",
        )
    return {
        "trial_filters": items,
        "pool": pool,
        "selection": read_trial_filters().get("recipe_selection"),
    }


_POOL_POPOVER_KEY = "corpus_pool_popover"


def _clear_pool_filters() -> None:
    """Unmount the filter inputs as they clear, discarding the browser's old values."""
    clear_trial_filters()
    st.session_state[_POOL_POPOVER_KEY] = False


#: What every Corpus Analysis table's recipe shares: the dataset, the
#: trial filters and the pool (set by `render_corpus_analysis_tab`), plus the
#: section being drawn (`_recipe_section`). ``None`` outside the page, where
#: `_download_tidy` draws the CSV alone.
_RECIPE_CONTEXT: ContextVar[dict | None] = ContextVar(
    "corpus_recipe_context", default=None
)


@contextlib.contextmanager
def _recipe_section(section: str):
    """Name the Corpus Analysis subtab the recipes drawn inside belong to."""
    base = _RECIPE_CONTEXT.get()
    token = _RECIPE_CONTEXT.set(None if base is None else {**base, "section": section})
    try:
        yield
    finally:
        _RECIPE_CONTEXT.reset(token)


def render_corpus_analysis_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    canvas_renderer: Callable[[Any], None] | None = None,
    has_raw_gaze: bool = False,
    raw_gaze: pd.DataFrame | None = None,
    recipe_context: dict | None = None,
    dataset_words: pd.DataFrame | None = None,
    can_remap_builtin: bool = False,
) -> None:
    """Compare the filtered corpus, then inspect a text, participant or group.

    ``recipe_context`` — the dataset, trial filters and pool — is what each
    table's recipe records beside the view's own choices; without it the
    tables download as CSV alone.
    """
    token = _RECIPE_CONTEXT.set(dict(recipe_context) if recipe_context else None)
    try:
        _render_corpus_analysis_body(
            words_filtered,
            fixations_filtered,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            viz_settings=viz_settings,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
            canvas_renderer=canvas_renderer,
            has_raw_gaze=has_raw_gaze,
            dataset_words=words_filtered if dataset_words is None else dataset_words,
            can_remap_builtin=can_remap_builtin,
            raw_gaze=raw_gaze,
        )
    finally:
        _RECIPE_CONTEXT.reset(token)


def _render_corpus_analysis_body(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float,
    scale_text_to_boxes: bool,
    canvas_renderer: Callable[[Any], None] | None,
    has_raw_gaze: bool,
    dataset_words: pd.DataFrame,
    can_remap_builtin: bool,
    raw_gaze: pd.DataFrame | None = None,
) -> None:
    """The body of :func:`render_corpus_analysis_tab`."""
    # The page shows the reading measures the dataset *brought* and computes
    # none. Without one there is nothing to show.
    if words_filtered.empty and available_measures(
        dataset_words, None, per_word_only=True
    ):
        st.info(
            "These trials have no word rows. Open **Edit filters** to include readings with word measures."
        )
        return
    measures = available_measures(words_filtered, None, per_word_only=True)
    if not measures:
        _corpus_unavailable_notice(
            has_aoi_table=not dataset_words.empty,
            has_raw_gaze=has_raw_gaze,
            can_remap_builtin=can_remap_builtin,
        )
        return
    common = dict(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
    )
    has_text = corpus_text_column(words_filtered) is not None and carries_mapped_text(
        words_filtered
    )
    navigation = st.container(
        key="tutorial_corpus_subtabs",
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="bottom",
        gap="small",
    )
    destinations = navigation.container(
        horizontal=True, vertical_alignment="center", width="content", gap="xsmall"
    )
    section, group_by = corpus_navigation.render_chooser(
        destinations, has_text=has_text, measures=measures
    )
    figure_controls = navigation.container(
        horizontal=True, vertical_alignment="bottom", width="content", gap="xsmall"
    )
    if section == "Overview":
        measure_host = figure_controls.container(width=245)
    viz_settings = corpus_style_controls(
        fixations_filtered,
        base_font_size,
        words=words_filtered,
        host=figure_controls,
        raw_gaze=raw_gaze,
        # This view renders true-to-scale stimulus figures from the
        # canvas / typography settings, so it hosts that panel too — the rail
        # (its other home) doesn't exist here.
        canvas_renderer=canvas_renderer,
    )
    corpus_navigation.back_to_summary(destinations, section, has_text=has_text)
    if (
        section != "Overview"
        and AOI_TRIAL_ID in words_filtered
        and words_filtered[AOI_TRIAL_ID].notna().any()
    ):
        st.info(
            "The Words table includes shared stimulus values. Each matching reading displays "
            "a copy, so several participants can show the same source measurement."
        )
    with _recipe_section(section):
        if section == "Overview":
            corpus_overview.render_corpus_overview(
                words_filtered,
                group_by=group_by,
                profile_host=destinations,
                measure_host=measure_host,
                download=_download_tidy,
                canvas_width=canvas_width,
                base_font_size=base_font_size,
                font_family=font_family,
                colors=_corpus_series_colors(viz_settings),
            )
        elif section == "Per text":
            render_per_text_tab(
                words_filtered, fixations_filtered, viz_settings=viz_settings, **common
            )
        elif section == "Per participant":
            render_per_reader_tab(
                words_filtered,
                fixations_filtered,
                viz_settings=viz_settings,
                **common,
            )
        elif section == "Per sentence":
            _render_per_sentence_tab(words_filtered, fixations_filtered)
        elif section == "Groups":
            render_groups_tab(
                words_filtered,
                fixations_filtered,
                viz_settings=viz_settings,
                **common,
            )
    corpus_navigation.update_bookmark(has_text=has_text, measures=measures)


@st.cache_data(show_spinner="Computing sentence measures…", show_time=True)
def _c_sentence_measures(_words, _fix, fwkey, ffkey):
    from scanpath_studio.preprocessing import sentence_measures

    # Derived from the fixations, not the supplied word measures — why the
    # subtab is behind the experimental flag.
    return sentence_measures(_words, _fix)


#: Per sentence's measures, in picker order, with what each one says and its
#: unit — the columns of `preprocessing.sentence_measures`.
_SENTENCE_MEASURE_LABELS = {
    "total_dur": "Total fixation duration (ms)",
    "total_n_fixations": "Total fixations",
    "firstpass_dur": "First-pass duration (ms)",
    "firstpass_n_fixations": "First-pass fixations",
    "gopast": "Go-past duration (ms)",
    "gopast_sel": "Selective go-past duration (ms)",
    "firstpass_forward_dur": "First-pass forward reading (ms)",
    "firstpass_forward_n_fixations": "First-pass forward fixations",
    "firstpass_reread_dur": "First-pass rereading (ms)",
    "firstpass_reread_n_fixations": "First-pass rereading fixations",
    "lookback_dur": "Look-back to earlier sentences (ms)",
    "lookback_n_fixations": "Look-back fixations",
    "lookfrom_dur": "Later rereading (ms)",
    "lookfrom_n_fixations": "Later rereading fixations",
    "nrun": "Number of runs",
    "rate_wpm": "Reading rate (words/min)",
    "n_words": "Sentence length (words)",
}


def _render_per_sentence_tab(
    words_filtered: pd.DataFrame, fixations_filtered: pd.DataFrame
) -> None:
    """The Per sentence subtab: one measure per text/sentence, across readers."""
    sentence_table = _c_sentence_measures(
        words_filtered,
        fixations_filtered,
        frame_fingerprint(words_filtered),
        frame_fingerprint(fixations_filtered),
    )
    st.caption(
        "One measure per sentence, combined across participants for each "
        "text and sentence."
    )
    numeric = [
        column for column in _SENTENCE_MEASURE_LABELS if column in sentence_table
    ]
    if sentence_table.empty or not numeric:
        st.info("No sentence-level measures are available for this selection.")
    else:
        controls = st.columns(2)
        metric = controls[0].selectbox(
            "Sentence measure",
            numeric,
            format_func=_SENTENCE_MEASURE_LABELS.get,
            key="sentence_measure",
        )
        aggregate = controls[1].selectbox(
            "Aggregate", ["Mean", "Median"], key="sentence_aggregate"
        )
        # A sentence is identified within its screen. Sentence ids restart on
        # every screen of a multipart text, so grouping on the text and
        # sentence alone would average different sentences together.
        identity = [
            column
            for column in ("text_id", SCREEN_ID, "sentence_id")
            if column in sentence_table
        ]
        reducer = "mean" if aggregate == "Mean" else "median"
        label = _SENTENCE_MEASURE_LABELS[metric]
        summary = (
            sentence_table.groupby(identity, dropna=False)[metric]
            .agg(reducer)
            .reset_index(name=f"{aggregate} {label[0].lower()}{label[1:]}")
        )
        if SCREEN_ID in identity and SCREEN_INDEX in sentence_table:
            # Screens in reading order, not alphabetically.
            order = sentence_table.groupby(identity, dropna=False)[SCREEN_INDEX].min()
            summary = (
                summary.assign(_order=order.to_numpy())
                .sort_values(["_order" if c == SCREEN_ID else c for c in identity])
                .drop(columns="_order")
                .reset_index(drop=True)
            )
        # The text and screen ids under the dataset's own names.
        st.dataframe(
            summary,
            hide_index=True,
            width="stretch",
            column_config=column_label_config(identity, active_all(st.session_state)),
        )


# -----------------------------------------------------------------------------
# Question-oriented analysis subtabs
# -----------------------------------------------------------------------------


def _chart(fig) -> None:
    """Render a non-spatial Plotly figure stretched to the column width."""
    st.plotly_chart(
        fig,
        width="stretch",
        config={**PLOTLY_CONFIG},
        alt=_figure_alt(fig, "Corpus analysis chart"),
    )
    from . import publication_ui

    title = _figure_alt(fig, "Corpus chart")
    publication_ui.render(
        fig, title=title, kind="chart", key=publication_ui.chart_key(fig)
    )


def _corpus_series_colors(viz_settings: dict) -> tuple[str, str]:
    """Palette-derived primary/secondary colours shared by corpus builders."""
    return (
        viz_settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
        viz_settings.get("saccade_color", SACCADE_COLOR),
    )


#: The Scanpath trial whose text Per text last opened on.
_PTEXT_SEEDED_FROM = "_ptext_seeded_from"


def _scanpath_trial_text(words: pd.DataFrame, text_col: str):
    """The text of the trial the Scanpath view shows, while it is new to Per
    text — ``None`` once Per text has opened on it (so a text picked here is
    kept) or when the pool does not hold it."""
    selected = st.session_state.get(SINGLE_TRIAL_ID)
    if selected is None or st.session_state.get(_PTEXT_SEEDED_FROM) == selected:
        return None
    st.session_state[_PTEXT_SEEDED_FROM] = selected
    # A reading key; a trial id alone (an older saved session) names no
    # participant.
    participant, trial = split_reading_key(selected)
    for col in ("unique_trial_id", "trial_id"):
        if col in words.columns:
            ids = words[col]
            # Compare as the column stores it; a string copy of a corpus-sized
            # column is only made when the types differ.
            same = ids == trial
            if not same.any():
                same = ids.astype(str) == str(trial)
            same = same.to_numpy().copy()
            if participant is not None and "participant_id" in words.columns:
                # That reader's rows of the id only — read off the rows
                # the id matched, not the whole column.
                rows = np.flatnonzero(same)
                readers = words["participant_id"].iloc[rows].astype(str)
                same[rows] = readers.to_numpy() == participant
            texts = words.loc[same, text_col].dropna().unique()
            if len(texts):
                # A trial id alone that several participants share can name
                # different texts: then it is ambiguous here, so don't guess.
                return texts[0] if len(texts) == 1 else None
    return None


def _text_picker(
    words: pd.DataFrame,
    *,
    key: str,
    host=None,
    label: str = "Text",
    follow_scanpath: bool = False,
):
    """Pick one text that the readings in scope can identify in common.

    ``follow_scanpath`` opens on the text of the trial last viewed in Scanpath,
    when the pool holds it."""
    host = host or st
    text_col = corpus_text_column(words)
    if words.empty or "word_id" not in words.columns:
        st.info("These readings have no word rows with word IDs.")
        return None, None
    if not carries_mapped_text(words):
        host.caption(
            "These IDs come from Trial ID. Map a Text ID in the Words table to match passages across readers."
        )
    counts = text_read_counts(words, text_col)
    if not counts.empty:
        labels = {
            f"{row.text}  ({plural(row.n_participants, 'participant')})": row.text
            for row in counts.itertuples()
        }
        current = None
        if follow_scanpath:
            current = _scanpath_trial_text(words, text_col)
            current = st.session_state.pop(corpus_overview.PENDING_TEXT, current)
        if current is not None:
            wanted = next((k for k, v in labels.items() if v == current), None)
            if wanted is not None:
                st.session_state[key] = wanted
        _drop_stale(key, list(labels))
        chosen = host.selectbox(label, list(labels), key=key, persist_state="session")
        text_id = labels[chosen]
    else:
        vals = sorted(words[text_col].dropna().astype(str).unique()) if text_col else []
        if not vals:
            st.info(
                "These word rows have no text IDs. Map a Text ID or choose another dataset."
            )
            return None, None
        text_id = host.selectbox(label, vals, key=key, persist_state="session")
    if TEXT_ID_MAPPED in words and not words[TEXT_ID_MAPPED].fillna(False).all():
        readings = words.loc[
            words[text_col].eq(text_id),
            words.columns.intersection([*_TRIAL_KEY_COLUMNS, TEXT_ID_MAPPED]),
        ]
        if (
            not readings[TEXT_ID_MAPPED].fillna(False).all()
            and len(trial_keys(readings)) != 1
        ):
            st.info(
                "These readings share an ID, but their Words table does not identify a common text. "
                "Use **Edit filters** to isolate one reading, or map a **Text ID** to compare readings."
            )
            return None, None
    return text_col, text_id


def _screen_picker(words, text_col, text_id, *, key: str, host=None):
    """Pick which screen of a multipart text the per-text views describe.

    Returns the chosen ``screen_id``, or ``None`` when the text is a single
    screen — which is every dataset without screen identity, where no
    control renders and the aggregation helpers ignore the argument.

    It has to be a *pick*, not a pooled "all screens": a ``word_id`` is unique
    only within a screen, and the stimulus view draws word **boxes**, which are
    measured against their own screen's origin. Pooling would stack two canvases.
    """
    options = text_screen_options(words, text_col, text_id)
    if len(options) < 2:
        return options[0] if options else None
    host = host or st
    return host.selectbox(
        "Screen",
        options,
        key=key,
        help="This text spans several screens. Word ids restart on each one, so "
        "these views describe one screen at a time.",
    )


def _participant_picker(words, fixations, *, key, host=None, label="Participant"):
    host = host or st
    options = sorted(_cohort_reader_ids(fixations, words))
    if not options:
        return None
    _drop_stale(key, options)
    return host.selectbox(label, options, key=key, persist_state="session")


def _percentile_among_others(
    cohort: pd.DataFrame, participant_id, column: str, value
) -> tuple[float | None, int]:
    """Where ``value`` falls among the *other* readers' values of ``column``.

    Returns ``(percentile, n)``: the share (0–100) of the other readers with a
    value for this measure whose value is lower, and how many such readers
    there are. The selected reader is left out, so with nobody else to compare
    against the percentile is ``None`` (``n == 0``) rather than a rank against
    themselves.
    """
    if (
        cohort is None
        or column not in getattr(cohort, "columns", [])
        or "participant_id" not in cohort.columns
    ):
        return None, 0
    others = cohort.loc[
        cohort["participant_id"].astype(str) != str(participant_id), column
    ]
    others = pd.to_numeric(others, errors="coerce").dropna()
    if others.empty or value is None or pd.isna(value):
        return None, int(others.size)
    return float((others < value).mean() * 100.0), int(others.size)


def _ordinal(number: int) -> str:
    """``1`` → ``1st``, ``12`` → ``12th``, ``22`` → ``22nd``."""
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def render_per_text_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    viz_settings: dict,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """*What does this text look like?* — one text, many readers."""
    if words_filtered.empty or "word_id" not in words_filtered.columns:
        st.info("Per-text views need a Words table (word ids + reading measures).")
        return
    fkey = frame_fingerprint(words_filtered)
    multipart = has_screen_identity(words_filtered)
    top = st.columns(
        [2, 3, 1, 2] if multipart else [2, 3, 2], vertical_alignment="bottom"
    )
    text_col, text_id = _text_picker(
        words_filtered, key="ptext_text", host=top[0], follow_scanpath=True
    )
    if text_id is None:
        return
    screen_id = (
        _screen_picker(
            words_filtered, text_col, text_id, key="ptext_screen", host=top[2]
        )
        if multipart
        else None
    )
    options = _chart_settings(top[-1])
    view = options.selectbox(
        "View",
        [
            "Cohort profile",
            "Per-participant profiles",
            "Word × participant heatmap",
            "Measure on the stimulus",
            "Measure vs feature",
            "Skip / regression rate",
        ],
        key="ptext_view",
        persist_state="session",
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Skip / regression rate":  # no measure picker
        if not {"skip_flag", "regression_in_flag"} & set(words_filtered.columns):
            st.info(
                "This dataset maps no skip or regression-in flag, so there is no "
                "rate to show."
            )
            return
        rates = [
            name
            for column, name in (
                ("skip_flag", "Skip rate"),
                ("regression_in_flag", "Regression-in rate"),
            )
            if column in words_filtered
        ]
        top[1].markdown(" · ".join(rates))
        min_readers = _min_readers_input(options, key="ptext6_min")
        rate = _c_word_rate(
            words_filtered, text_col, text_id, min_readers, fkey, screen_id
        )
        rate = _apply_rate_min_readers(st, rate, min_readers, key="ptext6_min_note")
        _chart(make_word_rate_figure(rate, **fw))
        _download_tidy(
            st,
            rate,
            name=f"word_rates_{text_id}.csv",
            key="dl_ptext6",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                min_readers=min_readers,
            ),
        )
        return

    measure = _measure_picker(
        words_filtered,
        fixations_filtered,
        key="ptext_measure",
        host=top[1],
        per_word_only=True,
    )
    if measure is None:
        return
    agg = options.selectbox(
        "Aggregate",
        _AGG_OPTIONS,
        format_func=str.capitalize,
        key="ptext_agg",
        persist_state="session",
        help="How values are combined: a participant's repeated trials of this "
        "text, then each word's values across participants.",
    )
    # Normalization is per-reader; it doesn't apply to the single aggregate tint
    # of the stimulus view, so disable the toggle there rather than show an
    # inert control.
    normalize = _normalize_toggle(
        options,
        key="ptext_norm",
        disabled=measure.is_rate or view == "Measure on the stimulus",
    )
    st.caption(
        f"**{view}** · "
        + (
            f"Each value is one participant on one word (the {agg} of their "
            "trials of this text)."
            if view in ("Per-participant profiles", "Word × participant heatmap")
            else f"Each word's value is the {agg} across its participants."
        )
        + (_Z_NOTE if normalize and view != "Measure on the stimulus" else ""),
    )

    if view == "Per-participant profiles":
        overlay = options.checkbox(
            f"Cohort {agg}", value=True, key="ptext1_overlay", persist_state="session"
        )
        per = _c_per_reader_word(
            words_filtered,
            text_col,
            text_id,
            measure.key,
            agg,
            normalize,
            fkey,
            screen_id,
        )
        cohort = None
        if overlay:
            coh = _c_cohort_profile(
                words_filtered,
                text_col,
                text_id,
                measure.key,
                agg,
                "SD",
                normalize,
                1,
                fkey,
                screen_id,
            )
            cohort = coh[["word_id", "value"]] if not coh.empty else None
        _chart(
            make_small_multiples_figure(
                per,
                measure_label=measure.value_label(normalize),
                cohort=cohort,
                aggregate=agg,
                **fw,
            )
        )
        _download_tidy(
            st,
            per,
            name=f"per_reader_{measure.key}_{text_id}.csv",
            key="dl_ptext1",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                normalize=normalize,
            ),
        )
    elif view == "Word × participant heatmap":
        per = _c_per_reader_word(
            words_filtered,
            text_col,
            text_id,
            measure.key,
            agg,
            normalize,
            fkey,
            screen_id,
        )
        _chart(
            make_word_matrix_heatmap(
                per,
                row_col="participant_id",
                row_label=active_all(st.session_state).field_label("participant_id"),
                measure_label=measure.value_label(normalize),
                colorscale=viz_settings.get(
                    "heatmap_colorscale", DEFAULT_HEATMAP_COLORSCALE
                ),
                **fw,
            )
        )
        _download_tidy(
            st,
            per,
            name=f"word_reader_{measure.key}_{text_id}.csv",
            key="dl_ptext2",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                normalize=normalize,
            ),
        )
    elif view == "Cohort profile":
        spread = options.selectbox(
            "Spread",
            _SPREAD_OPTIONS,
            key="ptext3_spread",
            persist_state="session",
            help="The band drawn around each word's value across participants: "
            "SD, SEM, IQR or a 95% bootstrap confidence interval.",
        )
        _spread_note(options, spread, agg)
        min_readers = _min_readers_input(options, key="ptext3_min")
        prof = _c_cohort_profile(
            words_filtered,
            text_col,
            text_id,
            measure.key,
            agg,
            spread,
            normalize,
            min_readers,
            fkey,
            screen_id,
        )
        supported = _apply_min_readers(st, prof, min_readers, key="ptext3_min_note")
        if not supported.empty:
            supported = supported[supported["enough"]]
        if supported.empty:
            if prof.empty:
                st.info(
                    "There are no words with Word IDs in this selection. Choose another text or screen."
                )
            elif not prof["n"].gt(0).any():
                st.info(
                    f"No word has a recorded value for {measure.label} in this selection. Choose another measure or inspect the readings below."
                )
            else:
                st.info(
                    "No word meets **Min participants per word**. Lower it in **Chart settings** or include more readers with **Edit filters**."
                )
        else:
            _chart(
                make_word_profile_figure(
                    {
                        f"Cohort ({measure.value_label(True) if normalize and not measure.is_rate else measure.label})": prof
                    },
                    measure_label=measure.value_label(normalize),
                    spread_label="95% bootstrap CI"
                    if effective_spread(spread, agg) == "Bootstrap CI"
                    else spread,
                    aggregate=agg,
                    colors=_corpus_series_colors(viz_settings),
                    **fw,
                )
            )
        _download_tidy(
            st,
            supported,
            name=f"cohort_profile_{measure.key}_{text_id}.csv",
            key="dl_ptext3",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                normalize=normalize,
                spread=spread,
                min_readers=min_readers,
            ),
        )
        detail = st.expander(
            "Readings behind a word", key="ptext3_readings", on_change="rerun"
        )
        if detail.open and not prof.empty:
            labels = prof.set_index("word_id")["word_text"].to_dict()
            word = detail.selectbox(
                "Word to inspect",
                list(labels),
                format_func=lambda wid: f"{wid} · {labels[wid]}",
                key="ptext3_inspect_word",
            )
            contributions = reading_word_contributions(
                words_filtered,
                text_col,
                text_id,
                measure,
                normalize=normalize,
                screen_id=screen_id,
            )
            rows = contributions[contributions["word_id"].eq(word)].copy()
            reader_values = _c_per_reader_word(
                words_filtered,
                text_col,
                text_id,
                measure.key,
                agg,
                normalize,
                fkey,
                screen_id,
            )
            reader_values = reader_values[reader_values["word_id"].eq(word)].set_index(
                "participant_id"
            )["value"]
            rows["reader_value"] = rows["participant_id"].map(reader_values)
            detail.caption(
                f"Source values use {measure.unit or 'the recorded scale'}. Reader values combine repeated readings by {agg}."
            )
            detail.dataframe(rows, hide_index=True)
        audit = st.expander(
            "Compare profile revisions", key="ptext3_revisions", on_change="rerun"
        )
        if audit.open:
            from .cohort_audit import compare_profiles, profile_snapshot

            context = _RECIPE_CONTEXT.get() or {}
            inputs = reading_word_contributions(
                words_filtered,
                text_col,
                text_id,
                measure,
                normalize=normalize,
                screen_id=screen_id,
            )
            written = _tidy_csv(supported, active_all(st.session_state).identity())
            choices = analysis_choices(
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                normalize=normalize,
                spread=spread,
                min_readers=min_readers,
            )
            snapshot = profile_snapshot(
                inputs,
                supported,
                written,
                {**choices, "filters": context.get("trial_filters", [])},
            )
            audit.caption(
                "This file contains participant and reading IDs, words and individual observations."
            )
            audit.download_button(
                "Download profile snapshot",
                data=json.dumps(snapshot, ensure_ascii=False),
                file_name="cohort_snapshot.json",
                mime="application/json",
                on_click="ignore",
            )
            prior = audit.file_uploader(
                "Earlier profile snapshot",
                type=["json"],
                key="ptext3_earlier",
                max_upload_size=upload_limit_mb(),
            )
            if prior is not None:
                try:
                    changes, note = compare_profiles(
                        json.loads(prior.getvalue()), snapshot
                    )
                except (UnicodeError, ValueError) as exc:
                    audit.error(str(exc))
                else:
                    audit.caption(note)
                    if not changes.empty:
                        audit.dataframe(changes, hide_index=True)
                    else:
                        audit.caption(
                            "Reading membership and contributions are identical."
                        )
    elif view == "Measure on the stimulus":  # reads viz_settings
        revisions = _c_stimulus_revisions(
            words_filtered, text_col, text_id, fkey, screen_id
        )
        chosen = None
        if len(revisions) > 1:
            st.warning(
                "This text has different wording or word boxes across readings. Choose the version to include in the figure."
            )
            # A version chosen for another text or screen names no option here.
            _drop_stale("ptext_stimulus_revision", list(revisions))
            chosen = st.selectbox(
                "Stimulus version, by representative reading",
                list(revisions),
                index=None,
                format_func=lambda k: (
                    f"{' / '.join(map(str, k))} · {len(revisions[k])} reading(s)"
                ),
                key="ptext_stimulus_revision",
                persist_state="session",
            )
            if chosen is None:
                return
        agg_words = _c_word_box_aggregate(
            words_filtered,
            text_col,
            text_id,
            measure.key,
            agg,
            fkey,
            screen_id,
            tuple(revisions[chosen]) if chosen else None,
        )
        if agg_words.empty:
            st.info("This text has no word geometry to tint.")
            return
        fig = make_scanpath_figure(
            agg_words,
            pd.DataFrame(),
            canvas_width=int(canvas_width),
            canvas_height=int(canvas_height),
            base_font_size=int(base_font_size),
            font_family=font_family,
            x_field="x",
            y_field="y",
            column_labels=active_figure_labels(
                st.session_state, words=agg_words.columns
            ),
            show_words=True,
            show_word_labels=viz_settings.get("show_labels", True),
            show_fixations=False,
            show_order=False,
            show_saccades=False,
            show_heatmap=True,
            color_by="value",
            heatmap_metric=None,
            heatmap_style="Word boxes",
            heatmap_norm=viz_settings.get("heatmap_norm", "Linear"),
            marker_size_range=viz_settings.get(
                "marker_size_range", DEFAULT_MARKER_SIZE_RANGE
            ),
            **{
                name: viz_settings.get(name, option.default)
                for name, option in FIXATION_LABEL_OPTIONS.items()
            },
            **{
                key: viz_settings.get(key, default)
                for key, default in COLORBAR_DEFAULTS.items()
            },
            fixation_color_range=None,
            heatmap_range=None,
            heatmap_colorscale=viz_settings.get(
                "heatmap_colorscale", DEFAULT_HEATMAP_COLORSCALE
            ),
            text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
            redact_text=viz_settings.get("redact_text", False),
            background_color=viz_settings.get("background_color"),
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
            fit_to_monitor=viz_settings.get("fit_to_monitor", True),
            crop_margin=viz_settings.get("crop_margin"),
            word_heatmap_col="value",
            word_heatmap_title=measure.axis_label,
        )
        if chosen:
            fig.update_layout(
                meta={**(fig.layout.meta or {}), "representative_reading": list(chosen)}
            )
            st.caption(
                f"Stimulus layout from {md_literal(str(chosen[0]))} / {md_literal(str(chosen[1]))}."
            )
        _render_true_scale_chart(fig, key="ptext_stimulus")
        from . import publication_ui

        publication_ui.render(
            fig,
            title=f"{measure.axis_label} · {text_id}",
            kind="chart",
            key="ptext_stimulus",
        )
        values = agg_words[["word_id", "value"]]
        if chosen:
            values = values.assign(
                representative_participant=chosen[0], representative_trial=chosen[1]
            )
        _download_tidy(
            st,
            values,
            name=f"stimulus_{measure.key}_{text_id}.csv",
            key="dl_ptext4",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
            ),
        )
    elif view == "Measure vs feature":
        feats = available_features(words_filtered)
        if not feats:
            st.info(
                "No linguistic features in this dataset: the view reads "
                "`gpt2_surprisal`, `wordfreq_frequency`, `word_length` and "
                "`universal_pos`."
            )
            return
        feat_label = st.selectbox("Feature", list(feats), key="ptext5_feat")
        feature_col, categorical = feats[feat_label]
        df = _c_word_feature(
            words_filtered,
            text_col,
            text_id,
            measure.key,
            feature_col,
            agg,
            normalize,
            fkey,
            screen_id,
        )
        _chart(
            make_feature_scatter_figure(
                df,
                measure_label=measure.value_label(normalize),
                feature_label=feat_label,
                categorical=categorical,
                **fw,
            )
        )
        _download_tidy(
            st,
            df,
            name=f"feature_{measure.key}_{feature_col}_{text_id}.csv",
            key="dl_ptext5",
            recipe=dict(
                view=view,
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                normalize=normalize,
                feature=feat_label,
            ),
        )


def _render_reader_comparison(
    words, fixations, pid, colors, figure_settings, measure_host, settings
) -> None:
    measure = _measure_picker(words, fixations, key="prdr_measure", host=measure_host)
    if measure is None:
        return
    normalize = False
    if measure.is_rate:
        st.caption(
            "Each measured word counts once here. The participant summary gives each reading equal weight."
        )
    else:
        kind = settings.selectbox(
            "Plot",
            ["violin", "box"],
            key="prdr7_kind",
            format_func=str.capitalize,
            persist_state="session",
        )
        normalize = _normalize_toggle(settings, key="prdr7_norm")
        settings.caption(
            "Wider parts of a violin show where more values fall."
            if kind == "violin"
            else "The box covers the middle half of the values. Its center line marks the median."
        )
    frame = (
        _enriched_corpus_fixations(fixations, words)
        if measure.frame == "fixations"
        else words
    )
    groups = _c_reader_vs_cohort(
        frame, pid, measure.key, normalize, frame_fingerprint(frame)
    )
    participant = f"Participant {pid}"
    if not groups:
        st.info(
            "Nobody in the selected trials has a value for this measure. Choose another measure or change the trial filters."
        )
        return
    if "This participant" not in groups:
        st.info(
            f"{md_literal(participant)} has no recorded values for this measure. Choose another participant to compare."
        )
    elif "Cohort" not in groups:
        st.info(
            "No other participant has a value for this measure in the selected trials. Change the trial filters or choose another measure to compare participants."
        )
    labels = {"This participant": participant, "Cohort": "Other participants"}
    if measure.is_rate:
        for col, (name, values) in zip(
            st.columns(len(groups)), groups.items(), strict=True
        ):
            col.metric(md_literal(labels[name]), f"{values.mean():.1%}")
            col.caption(
                f"{int(np.count_nonzero(values)):,} of {len(values):,} word observations"
            )
        return
    note = _observation(measure, normalize)
    if "Cohort" in groups:
        note += " Other participants’ values are pooled across their selected readings."
    st.caption(note)
    _chart(
        make_distribution_figure(
            {labels[name]: values for name, values in groups.items()},
            metric_label=measure.value_label(normalize),
            kind=kind,
            colors=colors if "This participant" in groups else colors[1:],
            **figure_settings,
        )
    )


def render_per_reader_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    viz_settings: dict,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """*What does this participant look like?* — one participant, many
    trials."""
    views = [
        "Distribution vs cohort",
        "Reading summary",
        "Fixation duration over time",
        "Saccade vs fixation duration",
        "Progressive vs regressive",
        "Landing-position curve",
        "Per-trial trend",
    ]
    if not computed_measures_enabled():
        # Their numbers are worked out by the app from the fixations, not read
        # from the dataset, and stay behind the experimental flag until checked
        # by hand.
        views = [v for v in views if v not in _COMPUTED_READER_VIEWS]
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    # Keyed → the tutorial's "pick the reader, then the view" step.
    top = st.container(key="tutorial_per_reader_view").columns(
        [2, 3, 2], vertical_alignment="bottom"
    )
    pid = _participant_picker(
        words_filtered, fixations_filtered, key="prdr_pid", host=top[0]
    )
    if pid is None:
        st.info("No participant column found.")
        return
    if st.session_state.get("prdr_view") not in (None, *views):
        del st.session_state["prdr_view"]
    settings = _chart_settings(top[2])
    view = settings.selectbox(
        "View",
        views,
        key="prdr_view",
        persist_state="session",
        format_func=lambda name: (
            "Compare with other participants"
            if name == "Distribution vs cohort"
            else name
        ),
    )
    if (
        view in ("Fixation duration over time", "Saccade vs fixation duration")
        and fixations_filtered.empty
    ):
        st.info("This view needs fixations, and none are in scope.")
        return
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Distribution vs cohort":
        _render_reader_comparison(
            words_filtered,
            fixations_filtered,
            pid,
            _corpus_series_colors(viz_settings),
            fw,
            top[1],
            settings,
        )
        return
    fix_e = _enriched_corpus_fixations(fixations_filtered, words_filtered)
    if view == "Reading summary":
        summary = reader_summary(words_filtered, fix_e, pid)
        cohort = _c_cohort_summary(
            words_filtered,
            fix_e,
            frame_fingerprint(words_filtered),
            frame_fingerprint(fix_e),
        )
        speed_estimated = summary.get("reading_time_source") == READING_TIME_ESTIMATED
        if speed_estimated:
            st.caption(
                "This data has no fixation timestamps, so reading speed is "
                "estimated from the summed fixation durations, without the time "
                "between fixations."
            )
        # `st.metric(icon=…)`: six numbers in one row read as an
        # undifferentiated wall; the glyph is what lets you find "the speed one"
        # without reading every label. Chosen to say what the number *is*, not to
        # decorate — speed, duration, count, direction of travel.
        specs = [
            (
                "wpm",
                "Reading speed (estimate)" if speed_estimated else "Reading speed",
                "{:.0f} wpm",
                ICONS["reading_speed"],
            ),
            (
                "mean_fixation_ms",
                "Mean fixation",
                "{:.0f} ms",
                ICONS["fixation_duration"],
            ),
            ("n_fixations", "Fixations", "{:.0f}", ICONS["fixations"]),
            (
                "regression_rate",
                "Regression rate",
                "{:.0%}",
                ICONS["regressions"],
            ),
            ("skip_rate", "Skip rate", "{:.0%}", ICONS["skip_rate"]),
            (
                "mean_saccade_px",
                "Mean saccade",
                "{:.1f} px",
                ICONS["saccade_amplitude"],
            ),
        ]
        present = [s for s in specs if s[0] in summary]
        cols = st.columns(len(present)) if present else []
        for col, (skey, label, fmt, icon) in zip(cols, present):
            value = summary.get(skey)
            pct, n_others = _percentile_among_others(cohort, pid, skey, value)
            col.metric(
                label,
                fmt.format(value) if value is not None else "—",
                delta=(
                    f"{_ordinal(round(pct))} percentile of {n_others}"
                    if pct is not None
                    else None
                ),
                delta_color="off",
                icon=icon,
            )
        st.caption(
            f"**Reading summary** · Participant {md_literal(pid)} compared with the others in the selection. "
            "Each percentile shows the percentage of other participants with a "
            "lower value for that measure. The count includes only participants "
            "with a value; no percentile is shown when none are available."
        )
        trials = _c_trial_summary(
            words_filtered,
            fix_e,
            frame_fingerprint(words_filtered),
            frame_fingerprint(fix_e),
        )
        trials = trials[trials["participant_id"].astype(str) == str(pid)]
        with st.expander("Summary tables", expanded=False):
            reader_table, trial_table = st.tabs(["Participant", "Trials"])
            with reader_table:
                selected_reader = cohort[
                    cohort["participant_id"].astype(str) == str(pid)
                ]
                st.dataframe(
                    selected_reader,
                    width="stretch",
                    hide_index=True,
                    column_config=column_label_config(
                        selected_reader.columns, active_all(st.session_state).identity()
                    ),
                )
                _download_tidy(
                    st,
                    selected_reader,
                    name=f"reader_summary_{pid}.csv",
                    key="dl_prdr8_reader",
                    recipe=dict(view=view, reader=pid),
                )
            with trial_table:
                _render_trials_with_open_button(trials, pid, key="prdr8")
                _download_tidy(
                    st,
                    trials,
                    name=f"trial_summaries_{pid}.csv",
                    key="dl_prdr8_trials",
                    recipe=dict(view=view, reader=pid),
                )
    elif view == "Fixation duration over time":
        measure = _measure_picker(
            words_filtered, fix_e, key="prdr9_measure", host=top[1], fixation_only=True
        )
        if measure is None:
            return
        # Numbered fixations are not a time axis: without recorded onsets
        # `timestamp_ms` is 0, 1, 2, … and only the order is offered.
        x_options = ["order_in_trial"]
        if not timestamps_synthesized(fix_e):
            x_options.append("timestamp_ms")
        if st.session_state.get("prdr9_x") not in (None, *x_options):
            del st.session_state["prdr9_x"]
        names = active_all(st.session_state)
        by = settings.selectbox(
            "X axis",
            x_options,
            key="prdr9_x",
            persist_state="session",
            format_func=names.field_label,
        )
        st.caption(
            "Each point is this participant's mean over the fixations at that "
            "point in their trials.",
        )
        df = metric_over_time(fix_e, measure, participant_id=pid, by=by)
        _chart(
            make_trend_figure(
                df,
                x_col="x",
                x_label=names.field_label(by),
                y_label=measure.axis_label,
                title=f"{measure.label} over {names.field_label(by)} — {pid}",
                **fw,
            )
        )
        _download_tidy(
            st,
            df,
            name=f"over_time_{measure.key}_{pid}.csv",
            key="dl_prdr9",
            recipe=dict(view=view, reader=pid, measure=measure, x_axis=by),
        )
    elif view == "Saccade vs fixation duration":
        df = saccade_vs_duration(fix_e, participant_id=pid)
        _chart(
            make_density_scatter_figure(
                df,
                x_col="duration_ms",
                y_col="saccade_amplitude",
                x_label="Fixation duration (ms)",
                y_label="Incoming saccade amplitude (px)",
                **fw,
            )
        )
    elif view == "Progressive vs regressive":
        df = progressive_regressive_counts(fix_e, participant_id=pid)
        if df.empty:
            st.info(
                "This view needs fixations assigned to words to classify regressions."
            )
            return
        _chart(make_progression_figure(df, **fw))
        _download_tidy(
            st,
            df,
            name=f"progression_{pid}.csv",
            key="dl_prdr11",
            recipe=dict(view=view, reader=pid),
        )
    elif view == "Landing-position curve":
        vals = landing_positions(words_filtered, fix_e, participant_id=pid)
        if vals.size == 0:
            st.info(
                "This view needs first-fixation landing positions, which come "
                "from fixation positions and word boxes."
            )
            return
        _chart(make_landing_curve_figure(vals, **fw))
    elif view == "Per-trial trend":
        measure = _measure_picker(
            words_filtered, fix_e, key="prdr_measure", host=top[1]
        )
        if measure is None:
            return
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="prdr13_agg",
            persist_state="session",
            help="How the measure is combined within each trial (across its words / fixations).",
        )
        st.caption(
            f"Each point is one trial: the {agg} over its "
            f"{'fixations' if measure.frame == 'fixations' else 'words'}.",
        )
        frame = fix_e if measure.frame == "fixations" else words_filtered
        sub = frame[frame["participant_id"].astype(str) == str(pid)].copy()
        if not has_explicit_trial_index(sub):
            st.caption(
                f"{ICONS['info']} The data has no trial-order column, so this "
                "order is inferred and may not be the order trials were shown."
            )
        x_label = trial_order_label(sub)
        sub["trial_index"] = derive_trial_index(sub)
        df = metric_by_trial_index(sub, measure.column, agg=agg)
        _chart(
            make_trend_figure(
                df,
                x_col="trial_index",
                x_label=x_label,
                y_label=measure.axis_label,
                title=f"{measure.label} by trial order — {pid}",
                break_gaps=True,
                **fw,
            )
        )
        _download_tidy(
            st,
            df,
            name=f"trend_{measure.key}_{pid}.csv",
            key="dl_prdr13",
            recipe=dict(view=view, reader=pid, measure=measure, aggregation=agg),
        )


def render_groups_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    viz_settings: dict,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """Compare two groups or turn the comparison off to profile the first group."""
    toolbar = st.container(horizontal=True, vertical_alignment="bottom")
    common = dict(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
        toolbar=toolbar,
    )
    if _groups_compare_toggle(toolbar):
        render_group_comparison_tab(
            words_filtered,
            fixations_filtered,
            viz_settings=viz_settings,
            **common,
        )
    else:
        render_per_group_tab(
            words_filtered,
            fixations_filtered,
            viz_settings=viz_settings,
            **common,
        )


def _groups_compare_toggle(host=None) -> bool:
    """Keep the chosen group workflow when visiting another destination."""
    return (host or st).toggle(
        "Compare two groups",
        value=True,
        key="groups_compare",
        persist_state="session",
        on_change=corpus_overview.keep_first_group,
        help="Turn off to explore the first group on its own.",
    )


def render_per_group_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    viz_settings: dict,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    toolbar=None,
) -> None:
    """*What does this group look like?* — a cohort by the active filter.

    The one-group case of the Groups tab (wrapped by ``render_groups_tab``)."""
    views = [
        "Distributions",
        "Word profile",
        "Participant summary table",
        "Group trend",
    ]
    if not computed_measures_enabled():
        views = [v for v in views if v not in _COMPUTED_READER_VIEWS]
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    _drop_stale("pgrp_view", views)
    toolbar = toolbar or st.container(horizontal=True, vertical_alignment="bottom")
    measure_host = toolbar.container()
    editor = toolbar.popover("Edit group", icon=ICONS["edit"], on_change="rerun")
    settings = _chart_settings(toolbar)
    view = settings.selectbox("View", views, key="pgrp_view", persist_state="session")
    spec, label = _render_group_definition(
        words_filtered, fixations_filtered, key="pgrp", two_groups=False, host=editor
    )
    if spec is None:
        return
    # The group's fields resolved to readings, so its words and its
    # fixations are the same readings whichever table carries the field.
    cohort = _resolve_cohort(spec, words_filtered, fixations_filtered)
    if _cohort_unavailable(st, [(label, cohort)]):
        return
    words_g = apply_group(words_filtered, cohort.spec)
    # One `apply_group` call, not two: it returns `frame[mask]`, a new full-size
    # copy, so calling it again just to compute the cache key would build a
    # second corpus-sized frame that nothing else sees — and park it in the
    # fingerprint memo for the rest of the run.
    fix_in = apply_group(fixations_filtered, cohort.spec)
    # All three are new every rerun; each is named by what made it — both
    # tables, since the group's readings are decided across the two.
    pool = (words_filtered, fixations_filtered)
    assign_derived(words_g, "apply_group", pool, (0, spec or {}))
    assign_derived(fix_in, "apply_group", pool, (1, spec or {}))
    fix_g = _enriched_corpus_fixations(fix_in, words_g)
    n_readers = _cohort_readers(fix_g, words_g)
    n_fix = len(fix_g) if fix_g is not None else 0
    st.caption(
        f"**{view}** · {md_literal(label)} · {_n_readers(n_readers)}, {plural(n_fix, 'fixation')} in scope."
    )
    if (words_g is None or words_g.empty) and (fix_g is None or fix_g.empty):
        st.info("This group is empty. Widen its definition.")
        return
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Distributions":
        measure = _measure_picker(words_g, fix_g, key="pgrp_measure", host=measure_host)
        if measure is None:
            return
        kind = settings.selectbox(
            "Plot",
            ["violin", "box"],
            key="pgrp14_kind",
            format_func=str.capitalize,
            persist_state="session",
        )
        normalize = _normalize_toggle(
            settings, key="pgrp14_norm", disabled=measure.is_rate
        )
        st.caption(_observation(measure, normalize))
        frame = fix_g if measure.frame == "fixations" else words_g
        vals = measure_values(frame, measure, normalize=normalize)
        _chart(
            make_distribution_figure(
                {label: vals},
                metric_label=measure.value_label(normalize),
                kind=kind,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
    elif view == "Word profile":
        text_col, text_id = _text_picker(words_g, key="pgrp_text")
        if text_id is None:
            return
        measure = _measure_picker(
            words_g, fix_g, key="pgrp_measure", host=measure_host, per_word_only=True
        )
        if measure is None:
            return
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="pgrp15_agg",
            persist_state="session",
            help="How each word's value is combined across the group's participants.",
        )
        spread = settings.selectbox(
            "Spread", _SPREAD_OPTIONS, key="pgrp15_spread", persist_state="session"
        )
        st.caption(
            f"Each point shows the {agg} for one word across the group’s participants."
        )
        _spread_note(settings, spread, agg)
        min_readers = _min_readers_input(settings, key="pgrp15_min")
        # Same single-screen scoping as the Per text views. There is no
        # free column on this row for a picker, so the helper's default (the
        # first screen in reading order) stands and the caption names it — a
        # profile pooled across screens would be keyed on a `word_id` that means
        # a different word per screen.
        grp_screens = text_screen_options(words_g, text_col, text_id)
        prof = _c_cohort_profile(
            words_g,
            text_col,
            text_id,
            measure.key,
            agg,
            spread,
            False,
            min_readers,
            frame_fingerprint(words_g),
            grp_screens[0] if grp_screens else None,
        )
        if len(grp_screens) > 1:
            st.caption(
                f"This text spans {len(grp_screens)} screens; showing "
                f"**{grp_screens[0]}**. Word ids restart on each screen, so a "
                "profile across screens would mix different words."
            )
        supported = _apply_min_readers(st, prof, min_readers, key="pgrp15_note")
        _chart(
            make_word_profile_figure(
                {label: prof},
                measure_label=measure.axis_label,
                spread_label=effective_spread(spread, agg),
                aggregate=agg,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
        _download_tidy(
            st,
            supported,
            name=f"group_profile_{measure.key}_{text_id}.csv",
            key="dl_pgrp15",
            recipe=dict(
                view=view,
                groups=[(label, spec)],
                text=(text_col, text_id),
                screen=grp_screens[0] if grp_screens else None,
                measure=measure,
                aggregation=agg,
                normalize=False,
                spread=spread,
                min_readers=min_readers,
                counts={"group_readers": n_readers, "group_fixations": n_fix},
            ),
        )
    elif view == "Participant summary table":
        table = _c_cohort_summary(
            words_g, fix_g, frame_fingerprint(words_g), frame_fingerprint(fix_g)
        )
        if table.empty:
            st.info("No per-participant summaries for this group.")
            return
        trials = _c_trial_summary(
            words_g, fix_g, frame_fingerprint(words_g), frame_fingerprint(fix_g)
        )
        reader_tab, trial_tab = st.tabs(["Participants", "Trials"])
        with reader_tab:
            st.dataframe(
                table,
                width="stretch",
                hide_index=True,
                column_config=column_label_config(
                    table.columns, active_all(st.session_state).identity()
                ),
            )
            _download_tidy(
                st,
                table,
                name="group_reader_summaries.csv",
                key="dl_pgrp16",
                recipe=dict(
                    view=view,
                    groups=[(label, spec)],
                    counts={"group_readers": n_readers, "group_fixations": n_fix},
                ),
            )
        with trial_tab:
            st.dataframe(
                trials,
                width="stretch",
                hide_index=True,
                column_config=column_label_config(
                    trials.columns, active_all(st.session_state).identity()
                ),
            )
            _download_tidy(
                st,
                trials,
                name="group_trial_summaries.csv",
                key="dl_pgrp16_trials",
                recipe=dict(
                    view=view,
                    groups=[(label, spec)],
                    counts={"group_readers": n_readers, "group_fixations": n_fix},
                ),
            )
    elif view == "Group trend":
        measure = _measure_picker(words_g, fix_g, key="pgrp_measure", host=measure_host)
        if measure is None:
            return
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="pgrp17_agg",
            persist_state="session",
            help="How the measure is combined within each trial (across its words / fixations).",
        )
        show_readers = settings.checkbox(
            "Show each participant",
            value=False,
            key="pgrp17_readers",
            persist_state="session",
        )
        st.caption(
            f"Each trial gets the {agg} over its "
            f"{'fixations' if measure.frame == 'fixations' else 'words'}; each "
            "point is the mean of those values over the trials at that position.",
        )
        frame = fix_g if measure.frame == "fixations" else words_g
        sub = frame.copy()
        if not has_explicit_trial_index(sub):
            st.caption(
                f"{ICONS['info']} The data has no trial-order column, so this "
                "order is inferred and may not be the order trials were shown."
            )
        x_label = trial_order_label(sub)
        sub["trial_index"] = derive_trial_index(sub)
        df = metric_by_trial_index(sub, measure.column, agg=agg)
        fig = make_trend_figure(
            df,
            x_col="trial_index",
            x_label=x_label,
            y_label=measure.axis_label,
            title=f"{measure.label} by trial order — {label}",
            break_gaps=True,
            **fw,
        )
        if show_readers:
            per = per_participant_trend(sub, measure.column, agg=agg)
            for rdr, grp in per.groupby("participant_id"):
                grp = grp.sort_values("trial_index")
                gx, gy = break_at_gaps(grp["trial_index"], grp["value"])
                fig.add_scatter(
                    x=gx,
                    y=gy,
                    mode="lines",
                    line=dict(color="rgba(150,150,150,0.35)", width=1),
                    name=str(rdr),
                    showlegend=False,
                    hoverinfo="skip",
                )
        _chart(fig)
        _download_tidy(
            st,
            df,
            name=f"group_trend_{measure.key}.csv",
            key="dl_pgrp17",
            recipe=dict(
                view=view,
                groups=[(label, spec)],
                measure=measure,
                aggregation=agg,
                counts={"group_readers": n_readers, "group_fixations": n_fix},
            ),
        )


def _fmt_stat(value, digits: int = 2) -> str:
    """A summary number, or an em dash when there is none (NaN / None)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return f"{value:.{digits}f}"


def _group_difference_metric(host, label: str, value, measure: Measure) -> None:
    if measure.is_rate:
        host.metric(f"{label} in percentage points", _fmt_stat(value * 100, digits=1))
    else:
        text = _fmt_stat(value)
        host.metric(
            label, f"{text} {measure.unit}" if measure.unit and text != "—" else text
        )


def render_group_comparison_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    viz_settings: dict,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    toolbar=None,
) -> None:
    """*How do two groups differ?* — two cohorts side by side."""
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    toolbar = toolbar or st.container(horizontal=True, vertical_alignment="bottom")
    measure_host = toolbar.container()
    editor = toolbar.popover("Edit groups", icon=ICONS["edit"], on_change="rerun")
    settings = _chart_settings(toolbar)
    view = settings.selectbox(
        "View",
        [
            corpus_overview.GROUP_MEANS_VIEW,
            "Overlaid distributions",
            "Difference word profile",
            "Side-by-side summary bars",
            "Within-participant contrast",
            "Two-group word heatmap",
        ],
        key="cmp_view",
        persist_state="session",
    )
    spec_a, spec_b, label_a, label_b = _render_group_definition(
        words_filtered, fixations_filtered, key="cmp", two_groups=True, host=editor
    )
    if spec_a is None or spec_b is None:
        return
    # Every chart keys its series by label, so equal labels would merge A
    # into B; from here on both read apart, the caption included.
    label_a, label_b = distinct_group_labels(label_a, label_b)
    # Each group's fields resolved to readings before any measure reads
    # them, so a field the fixations lack does not pool every fixation into
    # both groups. The recipes keep the definitions (`spec_a` / `spec_b`).
    cohort_a = _resolve_cohort(spec_a, words_filtered, fixations_filtered)
    cohort_b = _resolve_cohort(spec_b, words_filtered, fixations_filtered)
    if _cohort_unavailable(st, [(label_a, cohort_a), (label_b, cohort_b)]):
        return
    use_a, use_b = cohort_a.spec, cohort_b.spec
    readings_a = _cohort_reading_keys(fixations_filtered, words_filtered, use_a)
    readings_b = _cohort_reading_keys(fixations_filtered, words_filtered, use_b)
    ids_a = set(readings_a.get_level_values("participant_id"))
    ids_b = set(readings_b.get_level_values("participant_id"))
    readers_a, readers_b = len(ids_a), len(ids_b)
    shared = len(ids_a & ids_b)
    if not readings_a.empty and readings_a.equals(readings_b):
        st.info(
            "Both groups contain the same readings. Change a group selection to compare different readings."
        )
    scope_a, scope_b = (
        group if name == group else f"{group} ({md_literal(name)})"
        for group, name in (("Group A", label_a), ("Group B", label_b))
    )
    st.caption(
        f"**{scope_a}**: {_n_readers(readers_a)} · **{scope_b}**: "
        f"{_n_readers(readers_b)}"
        + (
            f" · **{shared} in both**, so the two groups are not independent."
            if shared
            else " · no participant in both."
        )
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    # The text and screen pickers describe the union of the two groups'
    # readings. An unrelated reading's fallback ID cannot make theirs ambiguous.
    if (
        view in ("Difference word profile", "Two-group word heatmap")
        and not words_filtered.empty
        and use_a
        and use_b
    ):
        if not set(_TRIAL_KEY_COLUMNS) <= set(words_filtered):
            st.info(
                "To compare words across groups, map the participant and trial IDs in the Words table."
            )
            return
        codes, word_readings = distinct_key_codes(words_filtered, _TRIAL_KEY_COLUMNS)
        included = word_readings.isin(readings_a.union(readings_b, sort=False))
        if not included.all():
            scoped = words_filtered.loc[included[codes]]
            assign_derived(scoped, "corpus_group_texts", words_filtered, (use_a, use_b))
            words_filtered = scoped

    if view == "Overlaid distributions":
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="cmp_measure", host=measure_host
        )
        if measure is None:
            return
        kind = settings.selectbox(
            "Plot",
            ["violin", "box"],
            key="cmp18_kind",
            format_func=str.capitalize,
            persist_state="session",
        )
        normalize = _normalize_toggle(
            settings, key="cmp18_norm", disabled=measure.is_rate
        )
        st.caption(f"**{view}** · {_observation(measure, normalize)}")
        frame = fixations_filtered if measure.frame == "fixations" else words_filtered
        groups = two_group_values(
            frame,
            measure,
            use_a,
            use_b,
            label_a=label_a,
            label_b=label_b,
            normalize=normalize,
        )
        _chart(
            make_distribution_figure(
                groups,
                metric_label=measure.value_label(normalize),
                kind=kind,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
    elif view == "Difference word profile":
        text_col, text_id = _text_picker(words_filtered, key="cmp_text")
        if text_id is None:
            return
        # One screen for both groups, chosen before they are split.
        screen_id = _screen_picker(words_filtered, text_col, text_id, key="cmp_screen")
        measure = _measure_picker(
            words_filtered,
            fixations_filtered,
            key="cmp_measure",
            host=measure_host,
            per_word_only=True,
        )
        if measure is None:
            return
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="cmp19_agg",
            persist_state="session",
            help="How each word's value is combined across each group's participants, before A−B.",
        )
        min_readers = _min_readers_input(
            settings, key="cmp19_min", label="Min participants per group"
        )
        st.caption(
            f"**{view}** · Each point is one word: group A's {agg} across its participants "
            "minus group B's.",
        )
        diff = group_word_difference(
            words_filtered,
            text_col,
            text_id,
            measure,
            use_a,
            use_b,
            agg=agg,
            min_readers=min_readers,
            screen_id=screen_id,
        )
        if "word_text_b" in diff:
            st.warning(
                "The groups use different word text at one or more word IDs. The CSV includes both labels for those positions."
            )
        diff = _apply_min_readers(st, diff, min_readers, key="cmp19_note")
        _chart(
            make_difference_profile_figure(
                diff,
                measure_label=measure.axis_label,
                label_a=label_a,
                label_b=label_b,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
        _download_tidy(
            st,
            diff,
            name=f"difference_{measure.key}_{text_id}.csv",
            key="dl_cmp19",
            recipe=dict(
                view=view,
                groups=[
                    (label_a, spec_a),
                    (label_b, spec_b),
                ],
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                min_readers=min_readers,
                counts={"group_a_readers": readers_a, "group_b_readers": readers_b},
            ),
        )
    elif view == "Side-by-side summary bars":
        all_measures = available_measures(words_filtered, fixations_filtered)
        labels = {m.label: m.key for m in all_measures}
        default = [
            m.label for m in all_measures if m.key in ("fix_dur", "sacc_amp", "tfd")
        ]
        chosen = measure_host.multiselect(
            "Measures",
            list(labels),
            default=default or list(labels)[:3],
            key="cmp20_measures",
        )
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="cmp20_agg",
            persist_state="session",
            help="How each measure's values are combined within a group: all its "
            "words or fixations, pooled across participants.",
        )
        # No error bars: a spread over words pooled from the same few
        # participants overstates how precise a bar is.
        st.caption(
            f"**{view}** · Each bar is the {agg} of the group's values for that measure, with "
            "its words or fixations pooled across participants."
        )
        measures = [MEASURES[labels[m]] for m in chosen]
        if not measures:
            st.info("Pick at least one measure.")
            return
        df = paired_group_summary(
            fixations_filtered,
            measures,
            use_a,
            use_b,
            agg=agg,
            label_a=label_a,
            label_b=label_b,
            words=words_filtered,
            fixations=fixations_filtered,
        )
        _chart(make_paired_bars_figure(df, aggregate=agg, **fw))
        _download_tidy(
            st,
            df,
            name="paired_group_means.csv",
            key="dl_cmp20",
            recipe=dict(
                view=view,
                groups=[
                    (label_a, spec_a),
                    (label_b, spec_b),
                ],
                measures=measures,
                aggregation=agg,
                counts={"group_a_readers": readers_a, "group_b_readers": readers_b},
            ),
        )
    elif view == "Within-participant contrast":
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="cmp_measure", host=measure_host
        )
        if measure is None:
            return
        frame = fixations_filtered if measure.frame == "fixations" else words_filtered
        table = within_reader_contrast(
            apply_group(frame, use_a),
            apply_group(frame, use_b),
            measure,
            participants=ids_a | ids_b,
        )
        differences = table["difference_a_minus_b"].dropna()
        st.caption(
            f"**{view}** · A = {md_literal(label_a)}. B = {md_literal(label_b)}. Each cell is one participant’s "
            f"mean for {measure.value_label(False)}. {len(differences)} complete pairs. "
            f"{table['value_a'].isna().sum()} missing A and {table['value_b'].isna().sum()} missing B."
        )
        if not differences.empty:
            _group_difference_metric(
                st,
                "Mean within-participant difference (A − B)",
                differences.mean(),
                measure,
            )
        if measure.is_rate:
            st.dataframe(
                table.assign(difference_a_minus_b=100 * table["difference_a_minus_b"]),
                hide_index=True,
                column_config={
                    "value_a": st.column_config.NumberColumn(
                        "Group A", format="percent"
                    ),
                    "value_b": st.column_config.NumberColumn(
                        "Group B", format="percent"
                    ),
                    "difference_a_minus_b": st.column_config.NumberColumn(
                        "A − B (percentage points)", format="%.1f"
                    ),
                },
            )
        else:
            st.dataframe(table, hide_index=True)
        _download_tidy(
            st,
            table,
            name=f"within_participant_{measure.key}.csv",
            key="dl_cmp_within",
            recipe=dict(
                view=view,
                groups=[(label_a, spec_a), (label_b, spec_b)],
                measure=measure,
                aggregation="mean",
                counts={"complete_pairs": len(differences)},
            ),
        )
    elif view == corpus_overview.GROUP_MEANS_VIEW:  # descriptive only
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="cmp_measure", host=measure_host
        )
        if measure is None:
            return
        frame = fixations_filtered if measure.frame == "fixations" else words_filtered
        by_reader = "participant_id" in frame
        readings, specs = (readings_a, readings_b), (use_a, use_b)
        a, b = _c_group_means(
            frame,
            measure.key,
            readings,
            specs,
            _group_means_key(frame, readings, specs),
        )
        observations = "fixations" if measure.frame == "fixations" else "words"
        observation = (
            f"For each participant, the mean includes all {observations} with a value "
            "across their selected trials. Each participant then counts equally in the group mean."
            if by_reader
            else f"Participant IDs are missing, so the means pool all measured {observations}."
        )
        res = group_mean_difference(a, b)
        missing = [
            md_literal(label)
            for label, n in ((label_a, res["n_a"]), (label_b, res["n_b"]))
            if not n
        ]
        if missing:
            st.info(
                f"No recorded values for {measure.label} in {' or '.join(missing)}. Choose another measure or open **Edit groups**."
            )
        unit = "participants" if by_reader else "values"
        n_word = "participant" if by_reader else "observation"
        counted = " with a value" if by_reader else ""

        def _stat(value) -> str:
            if measure.is_rate:
                return f"{value:.1%}" if pd.notna(value) else "—"
            text = _fmt_stat(value)
            return f"{text} {measure.unit}" if measure.unit and text != "—" else text

        cols = st.columns(3)
        cols[0].metric(
            f"{md_literal(label_a)} mean",
            _stat(res["mean_a"]),
            delta=f"{plural(res['n_a'], n_word)}{counted}",
            delta_color="off",
            delta_arrow="off",
        )
        cols[1].metric(
            f"{md_literal(label_b)} mean",
            _stat(res["mean_b"]),
            delta=f"{plural(res['n_b'], n_word)}{counted}",
            delta_color="off",
            delta_arrow="off",
        )
        _group_difference_metric(
            cols[2], "Difference (A − B)", res["mean_diff"], measure
        )
        # Cohen's d pools the two groups' spreads as if they were separate
        # samples, so it is shown only when no reader is in both groups.
        show_d = by_reader and not shared
        settings.metric(
            "Standardized difference",
            _fmt_stat(res["cohen_d"]) if show_d else "—",
            help="Cohen’s d divides the difference by the pooled standard deviation. "
            "It needs two participants per group, separate groups and a nonzero pooled spread.",
        )
        st.caption(observation)
        if not show_d:
            settings.caption(
                "The standardized difference is not shown when participants overlap or participant IDs are missing."
            )
        _download_tidy(
            st,
            pd.DataFrame(
                {
                    "group": [label_a, label_b],
                    "mean": [res["mean_a"], res["mean_b"]],
                    "n": [res["n_a"], res["n_b"]],
                    "n_counts": [unit, unit],
                }
            ),
            name=f"group_means_{measure.key}.csv",
            key="dl_cmp21",
            recipe=dict(
                view=view,
                groups=[(label_a, spec_a), (label_b, spec_b)],
                measure=measure,
                aggregation="mean",
                counts={
                    "group_a_readers": readers_a,
                    "group_b_readers": readers_b,
                    "readers_in_both": shared,
                },
            ),
        )
    elif view == "Two-group word heatmap":
        text_col, text_id = _text_picker(words_filtered, key="cmp_text")
        if text_id is None:
            return
        # One screen for both groups, chosen before they are split.
        screen_id = _screen_picker(words_filtered, text_col, text_id, key="cmp_screen")
        measure = _measure_picker(
            words_filtered,
            fixations_filtered,
            key="cmp_measure",
            host=measure_host,
            per_word_only=True,
        )
        if measure is None:
            return
        agg = settings.selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            format_func=str.capitalize,
            key="cmp22_agg",
            persist_state="session",
            help="How each word's value is combined across each group's participants.",
        )
        st.caption(
            f"**{view}** · Each cell is one word in one group: the {agg} across that group's "
            "participants.",
        )
        long = two_group_word_profiles(
            words_filtered,
            text_col,
            text_id,
            measure,
            use_a,
            use_b,
            agg=agg,
            label_a=label_a,
            label_b=label_b,
            screen_id=screen_id,
        )
        _chart(
            make_word_matrix_heatmap(
                long,
                row_col="group",
                measure_label=measure.axis_label,
                row_order=[label_a, label_b],
                **fw,
            )
        )
        _download_tidy(
            st,
            long,
            name=f"two_group_{measure.key}_{text_id}.csv",
            key="dl_cmp22",
            recipe=dict(
                view=view,
                groups=[
                    (label_a, spec_a),
                    (label_b, spec_b),
                ],
                text=(text_col, text_id),
                screen=screen_id,
                measure=measure,
                aggregation=agg,
                counts={"group_a_readers": readers_a, "group_b_readers": readers_b},
            ),
        )


# -----------------------------------------------------------------------------
# Comparisons Tab  (Scanpath view subtab)
# -----------------------------------------------------------------------------


def _best_model_indices(table: pd.DataFrame) -> dict:
    """Row index of the best-scoring model per *real* metric column.

    Min when the metric is lower-is-better, max otherwise. Placeholder metrics
    (``fn is None``) and all-NaN columns are skipped, so they get no entry.
    """
    best_index: dict[str, object] = {}
    for metric in METRICS:
        if metric.fn is None or metric.label not in table.columns:
            continue
        col = pd.to_numeric(table[metric.label], errors="coerce")
        if col.notna().any():
            best_index[metric.label] = (
                col.idxmin() if metric.lower_is_better else col.idxmax()
            )
    return best_index


def _metric_arrow(metric) -> str:
    """Direction arrow for a metric header: ↓ when lower is more similar, ↑ when
    higher is."""
    return "↓" if metric.lower_is_better else "↑"


def _style_similarity_table(table: pd.DataFrame):
    """Format the similarity table and highlight the best model per metric.

    Each metric header gets a direction arrow (↓ lower-is-better / ↑
    higher-is-better) so it's clear which way means *more similar*. Placeholder
    metrics (all-NaN columns) render as "—"; for each real metric the
    best-scoring model's cell is tinted green.
    """
    # Header relabelling: "NLD" -> "NLD ↓", etc. Keep the original-label
    # best-index, then translate its keys to the arrowed headers for highlighting.
    header_map = {
        m.label: f"{m.label} {_metric_arrow(m)}"
        for m in METRICS
        if m.label in table.columns
    }
    best_index = _best_model_indices(table)
    best_by_header = {
        header_map[label]: idx
        for label, idx in best_index.items()
        if label in header_map
    }

    display = table.copy()
    for label in header_map:
        display[label] = display[label].map(
            lambda v: f"{v:.3f}" if pd.notna(v) else "—"
        )
    display = display.rename(columns=header_map)

    def _highlight(row: pd.Series) -> list[str]:
        styles = []
        for col in display.columns:
            style = ""
            if col in best_by_header and row.name == best_by_header[col]:
                style = "background-color: #d4edda; font-weight: 600;"
            styles.append(style)
        return styles

    return display.style.apply(_highlight, axis=1)


def render_alignment_comparison_tab(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float,
    scale_text_to_boxes: bool,
    selected_participant,
    selected_trial,
) -> None:
    """Side-by-side grid comparing the vertical drift-correction algorithms.

    One panel per algorithm (plus the uncorrected original), each snapping
    fixations to their assigned text line and colouring by line, so a researcher
    can see how the ten Carr et al. (2021) algorithms assign fixations for this
    trial. The in-place version (a single algorithm applied on the main plot)
    lives in the Fixations popover; this subtab is the all-at-once comparison.
    """
    from scanpath_studio.measures import assign_fixation_lines

    st.caption(
        "Each panel moves fixations onto the text line a vertical "
        "drift-correction algorithm assigns them to "
        "([Carr et al., 2021](https://doi.org/10.3758/s13428-021-01554-0)) and "
        "colors them by line. To use one on the main plot, pick it under "
        "**Fixations** ▾ → **Drift correction**."
    )
    with st.expander("Algorithm citations", expanded=False):
        st.markdown(
            "Primary source: Carr et al. (2021), *Behavior Research Methods*, "
            "[doi:10.3758/s13428-021-01554-0](https://doi.org/10.3758/s13428-021-01554-0)."
        )
        for method in alignment.ALGORITHMS:
            st.markdown(
                f"- **{alignment.method_label(method)}** — "
                f"{alignment.METHOD_CITATIONS[method]}"
            )

    if trial_fixations.empty or trial_words.empty:
        st.info("This trial has no fixations or no word boxes to align.")
        return

    # Building the 11-panel grid (each a true-scale Plotly figure) is
    # expensive, so gate it behind a toggle the user opts into. The toggle
    # state persists, so it stays on while browsing trials once enabled.
    if not panel_field(
        st,
        "toggle",
        "Show comparison grid",
        key="align_grid_show",
        help="Show all ten algorithms side by side for this trial, next to the "
        "uncorrected scanpath. Off by default because the grid is slow to build.",
    ):
        st.caption(
            "Turn on **Show comparison grid** to compare all ten algorithms side "
            "by side, or apply one on the main plot under **Fixations** ▾ → "
            "**Drift correction**."
        )
        return

    # The text lines we snap to (shared with the per-algorithm panels). Fewer than
    # two lines → nothing to correct, so just show the original.
    line_centers = alignment._line_centers(trial_words)
    single_line = len(line_centers) < 2
    if single_line:
        st.info(
            "This trial has only one text line, so there is no vertical drift to "
            "correct. Showing the original scanpath."
        )

    # Two `label | field` rows rather than two side-by-side stacks: the
    # rows below the grid toggle read as one form with it.
    n_cols = panel_field(
        st,
        "slider",
        "Panels per row",
        min_value=2,
        max_value=3,
        value=2,
        key="align_grid_ncols",
    )
    show_connectors = panel_field(
        st,
        "checkbox",
        "Show drift connectors",
        key="align_grid_connectors",
        help="Draw a faint line from each fixation's original position to its "
        "corrected (snapped) position in every panel.",
    )

    # Clean, comparable spatial view: pin axes to x/y, drop the heatmap / raw gaze
    # / labels / order numbers (illegible at grid scale), colour by line.
    base_settings = _build_figure_settings(viz_settings, False)
    base_settings["raw_gaze"] = None
    base_settings["line_spacing"] = line_spacing
    base_settings["scale_text_to_boxes"] = scale_text_to_boxes
    panel_settings = {
        **base_settings,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "show_word_labels": False,
        "show_order": False,
        "fixation_flags": None,
        "color_by_line": True,
    }

    def _make_fig(fix: pd.DataFrame, *, connectors=None):
        kwargs = dict(panel_settings)
        if connectors is not None:
            kwargs["show_connectors"] = True
            kwargs["connector_y"] = tuple(pd.to_numeric(connectors, errors="coerce"))
        return _panel_figure(
            trial_words,
            fix,
            {
                "canvas_width": int(canvas_width),
                "canvas_height": int(canvas_height),
                "base_font_size": int(base_font_size),
                "font_family": font_family,
                "x_field": "x",
                "y_field": "y",
                "column_labels": active_figure_labels(
                    st.session_state, words=trial_words.columns, fixations=fix.columns
                ),
                **kwargs,
            },
        )

    # Naive baseline (nearest-line) to count how many fixations each algorithm
    # moves relative to the current "color by line" behaviour.
    baseline = assign_fixation_lines(trial_fixations, trial_words)
    _, sensitivity_report = alignment.correction_sensitivity(
        trial_fixations, trial_words
    )
    st.dataframe(
        sensitivity_report.assign(
            algorithm=sensitivity_report["algorithm"].map(alignment.method_label)
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "algorithm": st.column_config.TextColumn("Algorithm"),
            "average_y_correction": st.column_config.NumberColumn(
                "Mean vertical correction", format="%.1f px"
            ),
            "max_y_correction": st.column_config.NumberColumn(
                "Largest vertical correction", format="%.1f px"
            ),
        },
    )
    st.caption(
        "Large mean corrections, or disagreement between methods, flag trials "
        "worth checking by hand."
    )

    # Build the panel list: original first, then the 10 algorithms (skipped when
    # there is only a single line, where they would all be no-ops).
    panels = [("Original (uncorrected)", None)]
    if not single_line:
        panels += [(alignment.method_label(a), a) for a in alignment.ALGORITHMS]

    # Estimate a uniform cell height so panels line up (mirrors the
    # Comparisons grid).
    probe = _make_fig(trial_fixations)
    fig_w = float(probe.layout.width or 900)
    fig_h = float(probe.layout.height or 600)
    aspect = fig_h / fig_w if fig_w else 0.5
    assumed_col_px = max(200, int(780 / max(1, n_cols)))
    cell_h = max(150, int(assumed_col_px * aspect) + 16)

    for start in range(0, len(panels), n_cols):
        row = panels[start : start + n_cols]
        grid_cols = st.columns(n_cols)
        for cell, (label, method) in zip(grid_cols, row):
            with cell:
                if method is None:
                    st.caption(
                        f"**{label}** · {plural(len(trial_fixations), 'fixation')}"
                    )
                    fig = _make_fig(trial_fixations)
                else:
                    corrected, line = alignment.correct(
                        trial_fixations, trial_words, method=method
                    )
                    n_lines_used = int(line.dropna().nunique())
                    moved = (
                        (line.fillna(-1) != baseline.fillna(-1)).sum()
                        if len(baseline) == len(line)
                        else 0
                    )
                    st.caption(
                        f"**{label}** · {n_lines_used} lines · {int(moved)} moved · "
                        f"mean |Δy| {corrected['y_correction'].abs().mean():.1f}px"
                    )
                    fig = _make_fig(
                        corrected,
                        connectors=trial_fixations["y"] if show_connectors else None,
                    )
                    moved_mask = corrected["y_correction"].abs().gt(0.5)
                    if moved_mask.any():
                        import plotly.graph_objects as go

                        fig.add_trace(
                            go.Scatter(
                                x=corrected.loc[moved_mask, "x"],
                                y=corrected.loc[moved_mask, "y"],
                                mode="markers",
                                marker=dict(
                                    symbol="circle-open",
                                    size=16,
                                    color="#d62728",
                                    line=dict(width=2, color="#d62728"),
                                ),
                                name="Moved by correction",
                                customdata=corrected.loc[
                                    moved_mask, "y_correction"
                                ].to_numpy(),
                                hovertemplate="Moved Δy %{customdata:.1f}px<extra></extra>",
                            )
                        )
                _render_true_scale_chart(
                    fig,
                    key=f"align_{label.replace(' ', '_').replace('(', '').replace(')', '')}",
                    max_height=cell_h,
                )


# Per-fixation continuous quantities cannot select whole comparison trials.
_GEN_COL_EXCLUDE = {
    "x",
    "y",
    "duration_ms",
    "timestamp_ms",
    "saccade_amplitude",
    "order_in_trial",
    "first_fix_x",
    "first_fix_y",
    "noise_flag",
    # Per-fixation identifiers — grouping by these would make one "generation"
    # per fixation / word, not per scanpath, so they're never generation columns.
    "word_id",
    "fixation_id",
}
#: The grid draws one page of matches at a time, and every match is a
#: figure, so a page is also the most figures the subtab builds in one run —
#: the hard bound, whatever the match count. 12 fills whole rows at 1–4
#: columns. The pager reaches the rest.
_GEN_PAGE_SIZE = 12
#: The pager above the grid and the one below it; either moves both.
_GEN_PAGE_KEYS = ("multi_gen_page", "multi_gen_page_end")
#: The match set the page number belongs to — another trial or field starts
#: again at page 1.
_GEN_PAGE_FOR_KEY = "_multi_gen_page_for"
# Score at most this many matches (bounds the NLD cost for a high-cardinality
# column like participant_id on a big corpus); the rest follow the ranked ones,
# unranked. Dead while similarity is gated off — nothing is scored.
_GEN_MAX_SCORE = 60


def _generation_column_options(fixations: pd.DataFrame) -> list:
    """Trial-level columns that can select a comparison set."""
    if fixations is None or fixations.empty:
        return []
    hints = (
        "generation",
        "model",
        "source",
        "system",
        "variant",
        "condition",
        "method",
        "decoding",
        "run",
        "sample",
    )
    cols = []
    for c in user_columns(fixations):
        if c in _GEN_COL_EXCLUDE:
            continue
        try:
            if fixations[c].nunique(dropna=True) < 2:
                continue
            # A comparison field selects whole trials. Per-fixation fields such
            # as saccade type are invalid even when they escaped the explicit
            # coordinate/id exclusions above.
            if {"participant_id", "trial_id"} <= set(fixations.columns):
                within_trial = fixations.groupby(
                    ["participant_id", "trial_id"], dropna=False
                )[c].nunique(dropna=True)
                if not within_trial.empty and within_trial.max() > 1:
                    continue
            cols.append(c)
        except TypeError:
            # A column holding unhashable values (e.g. a list / JSON column like
            # MultiplEYE's `comprehension_questions`) can't group scanpaths.
            continue

    def _rank(col: str) -> tuple:
        low = col.lower()
        if any(h in low for h in hints):
            return (0, col)
        if col in ("participant_id", "trial_id"):
            return (1, col)
        return (2, col)

    return sorted(cols, key=_rank)


@st.cache_data(show_spinner=False, max_entries=8)
def _c_generation_column_options(_fixations: pd.DataFrame, fixations_key) -> list:
    """`_generation_column_options`, once per pool: it groups the whole pool
    by reading for every field, so a rerun must not repeat it."""
    return _generation_column_options(_fixations)


#: The two Match choices that come before the dataset's fields.
_MATCH_SAME_TEXT = "@same_text"
_MATCH_SAME_PARTICIPANT = "@same_participant"
_MATCH_LABELS = {
    _MATCH_SAME_TEXT: "Same text — other participants",
    _MATCH_SAME_PARTICIPANT: "Same participant — other texts",
}
#: Ids and orderings the two choices above cover, or that select one trial:
#: never offered as a condition field of their own.
_MATCH_NOT_A_CONDITION = frozenset(
    {*ROLE_LABELS, "unique_paragraph_id", "TRIAL_INDEX", "trial_index"}
)


def _match_text_column(fixations: pd.DataFrame) -> str | None:
    """The column a trial's text is read from, for *Same text*."""
    return next(
        (
            column
            for column in ("unique_text_id", "text_id", "paragraph_id")
            if column in fixations.columns
        ),
        None,
    )


def _match_options(fixations: pd.DataFrame, names: ColumnNames) -> list[str]:
    """The Comparisons subtab's *Match* choices: *Same text — other
    participants*, *Same participant — other texts*, then one entry per
    condition field under the dataset's own name, none twice."""
    options = []
    if _match_text_column(fixations) and "participant_id" in fixations.columns:
        options += [_MATCH_SAME_TEXT, _MATCH_SAME_PARTICIPANT]
    seen: set[str] = set()
    text_col = _match_text_column(fixations)
    for column in _c_generation_column_options(fixations, frame_fingerprint(fixations)):
        if column in _MATCH_NOT_A_CONDITION or column == text_col:
            continue
        label = names.field_label(column)
        if label in seen:
            continue
        seen.add(label)
        options.append(column)
    return options


def _resolve_match(choice: str, fixations: pd.DataFrame) -> tuple[str, str | None]:
    """``(column to match, column that must differ)`` for a *Match* choice."""
    text_col = _match_text_column(fixations)
    if choice == _MATCH_SAME_TEXT and text_col:
        return text_col, "participant_id"
    if choice == _MATCH_SAME_PARTICIPANT and text_col:
        return "participant_id", text_col
    return choice, None


def _collect_generations(
    fixations_pool: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    gen_col: str,
    selected_participant,
    selected_trial,
    differ_col: str | None = None,
) -> dict[tuple, pd.DataFrame]:
    """Trials matching the selected trial's ``gen_col`` value.

    The comparison column is a selector, not a grouping dimension: choosing
    ``participant_id`` shows that reader's other trials, while choosing
    ``text_id`` shows other readings of the same text. Each returned item is one
    trial and the selected trial itself is always excluded. ``differ_col``
    also drops every trial that shares the selected trial's value there —
    *Same text — other participants* drops the participant's own rereading.

    Keyed by the ``(participant_id, trial_id)`` pair, never by a label:
    ids may contain the separator a label joins them with, so ``(p1, "t1 ·
    t2")`` and ``("p1 · t1", t2)`` would read alike and one would replace the
    other. Labels are made where they are shown (:func:`_reading_labels`).

    Every match, in :func:`_reading_order` — the grid pages through them,
    so nothing here is cut.
    """
    if (
        gen_col not in fixations_pool.columns
        or gen_col not in trial_fixations.columns
        or fixations_pool.empty
        or trial_fixations.empty
    ):
        return {}
    pool = fixations_pool
    if SCREEN_ID in trial_fixations.columns and not trial_fixations.empty:
        if SCREEN_ID not in pool.columns:
            return {}
        active_screen = str(trial_fixations[SCREEN_ID].iloc[0])
        pool = pool[pool[SCREEN_ID].astype(str) == active_screen]
    selected_values = trial_fixations[gen_col].dropna().unique()
    if len(selected_values) != 1:
        return {}
    pool = pool[pool[gen_col] == selected_values[0]]
    if differ_col is not None and differ_col in trial_fixations.columns:
        own = trial_fixations[differ_col].dropna().unique()
        if differ_col in pool.columns and len(own):
            pool = pool[~pool[differ_col].isin(own)]
    if {"participant_id", "trial_id"} <= set(pool.columns):
        pool = pool[
            ~(
                (pool["participant_id"] == selected_participant)
                & (pool["trial_id"] == selected_trial)
            )
        ]
    candidates: dict[tuple, pd.DataFrame] = {}
    for reading, group in pool.groupby(
        ["participant_id", "trial_id"], dropna=False, sort=False
    ):
        if group.empty:
            continue
        candidates[reading] = group
    return dict(sorted(candidates.items(), key=lambda item: _reading_order(item[0])))


def _all_read_the_selected_text(trial_fixations, frames, text_col) -> bool:
    """Whether every match reads the selected trial's one text — what the
    similarity scores need, since they compare word sequences."""
    if text_col is None:
        return False
    own = trial_fixations[text_col].dropna().astype(str).unique()
    return len(own) == 1 and all(
        text_col in fix.columns
        and fix[text_col].dropna().astype(str).nunique() == 1
        and str(fix[text_col].dropna().astype(str).iloc[0]) == str(own[0])
        for fix in frames
    )


def _sync_gen_pages(source: str) -> None:
    """``on_change`` for either pager: the grid has one page, so both show it."""
    page = st.session_state.get(source)
    for key in _GEN_PAGE_KEYS:
        if key != source:
            st.session_state[key] = page


def _gen_page_caption(first: int, last: int, total: int) -> str:
    """What the grid shows, and how to see the rest."""
    if total <= _GEN_PAGE_SIZE:
        return f"{total} match." if total == 1 else f"{total} matches."
    span = f"{first}–{last}" if last > first else f"{first}"
    return f"Showing {span} of {total} matches. Pick a page to see more."


def _render_gen_pager(
    ranked: list, *, top: bool, match_set: tuple = (), note: str = ""
) -> list:
    """The Comparisons grid's page of ``ranked``, and its pager.

    ``top`` draws the count line with a pager beside it and returns the page's
    readings; the second call, under the grid, draws only a pager. Each pager
    moves the other (`_sync_gen_pages`). A new ``match_set`` — another trial,
    field or screen — starts again at page 1. One page needs no pager.
    """
    n_pages = max(1, -(-len(ranked) // _GEN_PAGE_SIZE))
    if top:
        match_set = tuple(str(part) for part in match_set)
        if st.session_state.get(_GEN_PAGE_FOR_KEY) != match_set:
            st.session_state[_GEN_PAGE_FOR_KEY] = match_set
            for key in _GEN_PAGE_KEYS:
                st.session_state.pop(key, None)
        count_col, pager_host = st.columns([3, 2], vertical_alignment="center")
    elif n_pages == 1:
        return ranked
    else:
        pager_host = st
    page = 1
    if n_pages > 1:
        key = _GEN_PAGE_KEYS[0 if top else 1]
        page = pager_host.container(
            horizontal=True, horizontal_alignment="right"
        ).pagination(
            n_pages,
            key=key,
            on_change=_sync_gen_pages,
            args=(key,),
            persist_state="session",
        )
    first = (page - 1) * _GEN_PAGE_SIZE
    shown = ranked[first : first + _GEN_PAGE_SIZE]
    if top:
        count_col.caption(
            _gen_page_caption(first + 1, first + len(shown), len(ranked)) + note
        )
    return shown


_DIGIT_RUN = re.compile(r"([0-9]+)")


def _reading_order(reading: tuple) -> tuple:
    """A reading's place in the Comparisons grid: by participant, then trial,
    as text with its numbers read as numbers — participant 2 before 10,
    which matters once the grid pages. Ids of mixed types, or a missing one,
    still sort, and the text itself breaks a tie (``7`` / ``007``)."""

    return tuple(
        key for part in map(str, reading) for key in (_natural_key(part), part)
    )


#: Ids longer than this are split afresh each time rather than remembered, so
#: the process-wide memo below stays small whatever a dataset's ids look like.
_NATURAL_KEY_MEMO_MAX_LEN = 128


def _natural_key(text: str) -> tuple:
    """``text`` split into runs of digits (compared as numbers) and the rest.
    Remembered for ordinary ids: the grid re-sorts every match on each rerun,
    and the ids repeat."""
    if len(text) <= _NATURAL_KEY_MEMO_MAX_LEN:
        return _natural_key_memo(text)
    return _split_natural(text)


def _split_natural(text: str) -> tuple:
    return tuple(
        (0, int(run), "") if run[0] in "0123456789" else (1, 0, run)
        for run in _DIGIT_RUN.split(text)
        if run
    )


_natural_key_memo = functools.lru_cache(maxsize=16384)(_split_natural)


def _distinct_labels(labels: dict, qualify: Callable[[Hashable, str], str]) -> dict:
    """``labels`` with each one that several readings share made unique —
    ``qualify(reading, label)``, then a counter if even that is taken. A label
    only one reading has is kept, and no qualified one lands on it."""
    seen: dict[str, int] = {}
    for label in labels.values():
        seen[label] = seen.get(label, 0) + 1
    used = {label for label, n in seen.items() if n == 1}
    distinct = {}
    for reading, label in labels.items():
        if seen[label] > 1:
            qualified = candidate = qualify(reading, label)
            n = 2
            while candidate in used:
                candidate = f"{qualified} ({n})"
                n += 1
            label = candidate
        used.add(label)
        distinct[reading] = label
    return distinct


def _reading_labels(readings) -> dict:
    """``participant · trial`` for each ``(participant_id, trial_id)`` — the
    similarity table's rows and the convergence lines. Two readings whose ids
    join to the same text are spelled out instead."""
    return _distinct_labels(
        {reading: " · ".join(map(str, reading)) for reading in readings},
        lambda reading, _label: f"participant {reading[0]}, trial {reading[1]}",
    )


def _comparison_trial_words(
    words_pool: pd.DataFrame, trial_fixations: pd.DataFrame
) -> pd.DataFrame:
    """Word boxes for one comparison candidate, including its active screen."""
    if words_pool.empty or trial_fixations.empty:
        return words_pool.iloc[0:0]
    row = trial_fixations.iloc[0]
    screen = (
        str(row[SCREEN_ID])
        if SCREEN_ID in trial_fixations.columns and SCREEN_ID in words_pool.columns
        else None
    )
    return extract_part(
        words_pool,
        row["participant_id"],
        row["trial_id"],
        screen,
    )


def _comparison_panel_settings(base_settings: dict) -> dict:
    """Comparable grid settings without hiding the main plot's stimulus text."""
    settings = {
        **base_settings,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "color_by_line": False,
        "fixation_flags": None,
        "show_order": False,
    }
    # The builders read `color_by="line"` as colour-by-line too, so the
    # rail's "line" has to be neutralised here or the switch-off above is moot.
    if settings.get("color_by") == "line":
        settings["color_by"] = UNIFORM_COLOR_FIELD
    return settings


def _match_panel_caption(choice: str, fix: pd.DataFrame, text_col) -> str:
    """A Comparisons panel's name: what tells it apart under the
    *Match* choice — its participant for *Same text*, its text for *Same
    participant* — else the trial as the trial picker writes it."""
    first = fix.iloc[0]
    if choice == _MATCH_SAME_TEXT:
        return f"Participant {first['participant_id']}"
    if choice == _MATCH_SAME_PARTICIPANT and text_col in fix.columns:
        return f"Text {first[text_col]}"
    return trial_id_shown(first["trial_id"], fix)


def _panel_captions(choice: str, panels: dict, text_col, reading_labels: dict) -> dict:
    """:func:`_match_panel_caption` for each grid panel, made unique: a
    caption two panels share — one participant's two readings of a text, two
    readers' trials of one id — names its reading as well."""
    return _distinct_labels(
        {
            reading: _match_panel_caption(choice, fix, text_col)
            for reading, fix in panels.items()
        },
        lambda reading, caption: f"{caption} ({reading_labels[reading]})",
    )


def render_multiple_comparison_tab(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    selected_participant: str,
    selected_trial: str,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    trial_raw_gaze: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
    color_categories: tuple[str, ...] | None = None,
) -> None:
    """Render the **Comparisons** subtab.

    Shows other trials whose selected comparison-field value matches the main
    trial. The field decides the set: text id yields other readings of the text,
    participant id yields that reader's other texts, and so on.

    ``trial_raw_gaze`` / ``raw_gaze`` are the selected trial's samples and the
    filtered pool's, for the chip table's gaze-sample count.
    ``color_categories`` is the dataset's `FigureSettings.color_categories`, so
    each panel colours a category as the main figure does.
    """
    st.caption(
        "Browse related readings by selecting a field they share with this trial."
    )
    if trial_words.empty or trial_fixations.empty:
        st.info("This trial has no word boxes or no fixations. Pick another trial.")
        return

    names = active_all(st.session_state)
    match_options = _match_options(fixations_filtered, names)
    if not match_options:
        st.info("No field to match trials on.")
        return
    match_labels = {
        **names.option_labels(match_options, roles=True),
        **_MATCH_LABELS,
    }
    # A stored choice that is not among the options (an older session's
    # `participant_id`) is dropped.
    if st.session_state.get("multi_gen_col") not in match_options:
        st.session_state.pop("multi_gen_col", None)

    # One `label | field` row whose first label sits in the subtabs' own
    # label column (`PANEL_LABEL_W`); what *Match field* does is its hover help,
    # not a caption beside it repeating the same thing.
    match_label_col, match_col, cols_label_col, cols_col = st.columns(
        [PANEL_LABEL_W, 0.44, 0.09, 0.27],
        gap=LABEL_GAP,
        vertical_alignment="center",
    )
    match_help = "Shows the other trials that share the selected trial's value here."
    row_label(match_label_col, "Match field", match_help)
    choice = match_col.selectbox(
        "Match field",
        options=match_options,
        format_func=match_labels.__getitem__,
        key="multi_gen_col",
        help=match_help,
        label_visibility="collapsed",
    )
    cols_help = "Panels per row."
    row_label(cols_label_col, "Columns", cols_help)
    n_cols = cols_col.slider(
        "Columns",
        min_value=1,
        max_value=4,
        value=2,
        key="multi_n_cols",
        help=cols_help,
        label_visibility="collapsed",
    )
    gen_col, differ_col = _resolve_match(choice, fixations_filtered)

    # Masks and groups the whole pool, so the matches are kept until the pool,
    # the selected reading or the Match choice changes.
    candidates = frame_cache(
        "comparison_matches",
        (
            frame_fingerprint(fixations_filtered),
            frame_fingerprint(trial_fixations),
            gen_col,
            str(selected_participant),
            str(selected_trial),
            differ_col,
        ),
        lambda: _collect_generations(
            fixations_filtered,
            trial_fixations,
            gen_col,
            selected_participant,
            selected_trial,
            differ_col,
        ),
    )
    if not candidates:
        st.info(f"No other trial in the filters matches **{match_labels[choice]}**.")
        return

    # Reuse the user's viz toggles but force a clean, comparable spatial view: the
    # grid is inherently spatial, and a generation frame may lack the selected
    # trial's extra columns, so pin axes to x/y, colour by duration_ms (present in
    # every frame), and turn off heatmap / raw gaze / by-line / flags (they group
    # by (participant_id, trial_id) against trial_words and would mis-render).
    base_settings = _build_figure_settings(viz_settings, False)
    base_settings["raw_gaze"] = None
    base_settings["line_spacing"] = line_spacing
    base_settings["scale_text_to_boxes"] = scale_text_to_boxes
    panel_settings = _comparison_panel_settings(base_settings)

    def _make_fig(words: pd.DataFrame, fix: pd.DataFrame, settings: dict):
        return _panel_figure(
            words,
            fix,
            {
                "canvas_width": int(canvas_width),
                "canvas_height": int(canvas_height),
                "base_font_size": int(base_font_size),
                "font_family": font_family,
                "x_field": "x",
                "y_field": "y",
                "column_labels": active_figure_labels(
                    st.session_state, words=words.columns, fixations=fix.columns
                ),
                "color_categories": color_categories,
                **settings,
            },
        )

    with st.container():
        # Score the matches against the selected scanpath — at most
        # `_GEN_MAX_SCORE` of them. The NLD annotates each grid panel and orders
        # the grid and the table; the full table is shown beneath the grid.
        #
        # With similarity gated off (the experimental flag) nothing is scored,
        # and the grid is in `_reading_order`.
        text_col = next(
            (
                column
                for column in ("unique_text_id", "text_id", "paragraph_id")
                if column in trial_fixations.columns
            ),
            None,
        )
        # Scoring (experimental) only, and only the matches it would score:
        # the check is a Python loop, so walking every match would cost a
        # rerun seconds on a large corpus.
        head = (
            dict(itertools.islice(candidates.items(), _GEN_MAX_SCORE))
            if similarity_enabled()
            else {}
        )
        scoring = bool(head) and _all_read_the_selected_text(
            trial_fixations, head.values(), text_col
        )
        scored = head if scoring else {}
        table = (
            compute_similarity_table(trial_fixations, scored, trial_words)
            if scoring
            else pd.DataFrame()
        )
        nld_by_gen = (
            dict(zip(table["Model"], table["NLD"])) if "NLD" in table.columns else {}
        )

        # Rank by similarity (lowest NLD = most similar; unscored/NaN last).
        # Every key here is a `(participant_id, trial_id)` reading; the
        # labels below are only how it is written.
        if scoring:
            ranked = sorted(
                candidates,
                key=lambda n: (
                    pd.isna(nld_by_gen.get(n)),
                    nld_by_gen.get(n) if pd.notna(nld_by_gen.get(n)) else 0.0,
                ),
            )
        else:
            ranked = list(candidates)  # already in `_reading_order`
        reading_labels = _reading_labels(candidates)

        st.markdown("#### Matching trials")
        # One page of matches at a time — each is a figure.
        grid_names = _render_gen_pager(
            ranked,
            top=True,
            match_set=(selected_participant, selected_trial, gen_col, differ_col),
            note=(
                f" The first {_GEN_MAX_SCORE} are ranked by NLD; the rest follow."
                if scoring and len(candidates) > _GEN_MAX_SCORE
                else ""
            ),
        )
        captions = _panel_captions(
            choice,
            {name: candidates[name] for name in grid_names},
            text_col,
            reading_labels,
        )
        page_words = {
            name: _comparison_trial_words(words_filtered, candidates[name])
            for name in grid_names
        }
        # The chips above the plot, for the selected trial and the page's
        # matches — one row each, so they compare down each column.
        chip_fields = st.session_state.get("trial_chip_fields") or []
        if chip_fields:
            count_samples = "@gaze_sample_count" in chip_fields
            _render_matches_chip_table(
                chip_fields,
                [
                    (
                        "Selected",
                        ChipReading(
                            trial_words,
                            trial_fixations,
                            selected_participant,
                            raw_gaze=trial_raw_gaze,
                        ),
                    ),
                    *(
                        (
                            captions[name],
                            ChipReading(
                                page_words[name],
                                candidates[name],
                                name[0],
                                gaze_samples=(
                                    _match_gaze_samples(raw_gaze, candidates[name])
                                    if count_samples
                                    else None
                                ),
                            ),
                        )
                        for name in grid_names
                    ),
                ],
            )
        # Estimate a uniform cell height from the figure aspect + column count so
        # panels line up and don't leave a tall whitespace band below each.
        aspect = float(canvas_height) / float(canvas_width or 1)
        assumed_col_px = max(360, int(1200 / max(1, n_cols)))
        cell_h = max(280, int(assumed_col_px * aspect) + 24)

        for start in range(0, len(grid_names), n_cols):
            row_names = grid_names[start : start + n_cols]
            grid_cols = st.columns(n_cols)
            for offset, (cell, name) in enumerate(zip(grid_cols, row_names)):
                with cell:
                    fix = candidates[name]
                    nld = nld_by_gen.get(name)
                    trial_label = captions[name]
                    if nld is not None and pd.notna(nld):
                        st.caption(f"**{trial_label}** · NLD {nld:.2f}")
                    else:
                        st.caption(f"**{trial_label}**")
                    words = page_words[name]
                    # Key on the absolute panel index (dict order is stable), so two
                    # labels differing only by spaces can't collide on the iframe key.
                    _render_true_scale_chart(
                        _make_fig(words, fix, panel_settings),
                        key=f"multi_gen_{start + offset}",
                        max_height=cell_h,
                    )
        _render_gen_pager(ranked, top=False)

        # The scoring half of this panel — the similarity table (three of its
        # four metrics still read "Not yet computed") and the convergence
        # plots — is behind the experimental flag. The comparison grid above
        # stays; only the scoring comes off it.
        if not scoring:
            return

        st.markdown("#### Similarity")
        shown = table.assign(Model=[reading_labels[name] for name in table["Model"]])
        st.dataframe(
            _style_similarity_table(shown.rename(columns={"Model": "Trial"})),
            hide_index=True,
            width="stretch",
        )

        # Cumulative NLD convergence over the full scanpaths. Memoized on the
        # selection + comparison column + set + a content fingerprint so unrelated
        # reruns don't recompute the curves.
        st.markdown("#### Convergence")
        st.caption("Cumulative NLD by fixation and time. Lower is more similar.")
        if trial_fixations.empty:
            fix_fingerprint: tuple = (0,)
        else:
            fix_fingerprint = (
                len(trial_fixations),
                len(trial_words),
                round(float(pd.to_numeric(trial_fixations["x"]).sum()), 3),
                round(float(pd.to_numeric(trial_fixations["y"]).sum()), 3),
                round(float(pd.to_numeric(trial_fixations["duration_ms"]).sum()), 3),
            )
        # Convergence covers the page on screen, so it matches the grid and
        # stays bounded on a high-cardinality column.
        conv_gens = {name: candidates[name] for name in grid_names}
        conv_key = (
            str(selected_participant),
            str(selected_trial),
            str(gen_col),
            tuple(sorted(conv_gens, key=_reading_order)),
            fix_fingerprint,
        )
        if st.session_state.get("_multi_conv_key") != conv_key:
            st.session_state["_multi_conv_key"] = conv_key
            st.session_state["_multi_conv_fix"] = {
                name: nld_by_fixation_index(trial_fixations, g, trial_words)
                for name, g in conv_gens.items()
            }
            st.session_state["_multi_conv_time"] = {
                name: nld_by_time(trial_fixations, g, trial_words)
                for name, g in conv_gens.items()
            }
        fix_curves = {
            reading_labels[name]: curve
            for name, curve in st.session_state["_multi_conv_fix"].items()
        }
        time_curves = {
            reading_labels[name]: curve
            for name, curve in st.session_state["_multi_conv_time"].items()
        }

        conv_cols = st.columns(2)
        with conv_cols[0]:
            fig_idx = make_metric_convergence_figure(
                fix_curves,
                x_title="Cumulative fixation index",
                y_title="NLD",
                title="NLD vs fixation index",
                canvas_width=520,
                base_font_size=int(base_font_size),
                font_family=font_family,
            )
            st.plotly_chart(
                fig_idx,
                width="stretch",
                config={**PLOTLY_CONFIG, "responsive": True},
                alt=_figure_alt(fig_idx, "NLD convergence chart"),
            )
        with conv_cols[1]:
            fig_time = make_metric_convergence_figure(
                time_curves,
                x_title="Elapsed reading time (s)",
                y_title="NLD",
                title="NLD vs time",
                canvas_width=520,
                base_font_size=int(base_font_size),
                font_family=font_family,
            )
            st.plotly_chart(
                fig_time,
                width="stretch",
                config={**PLOTLY_CONFIG, "responsive": True},
                alt=_figure_alt(fig_time, "NLD convergence chart"),
            )


# -----------------------------------------------------------------------------
# Data Tables Tabs
# -----------------------------------------------------------------------------


def column_label_config(columns, names: ColumnNames) -> dict:
    """Header labels for a table of canonical columns.

    The user's own names, and the app's columns marked, for every column whose
    label differs from its name. The frame itself stays canonical, so sorting
    and the lazy stream are untouched.
    """
    labels = names.option_labels(list(columns))
    return {
        column: st.column_config.Column(label=label)
        for column, label in labels.items()
        if label != str(column)
    }


def _render_raw_table(
    df: pd.DataFrame, caption: str | None = None, *, table: str | None = None
) -> None:
    """Render one of the raw Data Inspection tables, whole.

    ``lazy=True``: Streamlit keeps the frame on the app server and streams only
    the rows in view, so the user scrolls and sorts across the *whole* corpus,
    and a rerun does not ship the visible page to the browser again. Passed
    explicitly rather than left to the default: the default only kicks in above
    150 000 rows, and these are exactly the frames worth streaming well below
    that.

    There is deliberately no download button here: these are the *raw* frames,
    which carry passthrough columns like ``image_path`` that hold an absolute
    local path. Bulk export is the supported way out, and it strips those at its
    single chokepoint (``export.strip_local_paths``).
    """
    from streamlit.dataframe_util import convert_pandas_df_to_arrow_table

    names = active_column_names(st.session_state, table) if table else EMPTY_NAMES

    def display_source():
        shown = shareable_frame(df, table=table)
        hidden = names.redundant_aliases(shown)
        order = [c for c in shown.columns if c not in hidden]
        # A lazy grid serves slices, but first needs the entire frame in Arrow
        # with a physical index. Keep that conversion for the three recordings.
        source = (
            convert_pandas_df_to_arrow_table(shown, preserve_index=True)
            if table
            else shown
        )
        return source, order

    if table:
        source, order = frame_cache(
            f"data_table_display_{table}",
            (frame_fingerprint(df), tuple(sorted(names.entries.items()))),
            display_source,
        )
    else:
        source, order = display_source()
    st.dataframe(
        source,
        hide_index=True,
        width="stretch",
        lazy=True,
        column_order=order,
        column_config=column_label_config(order, names),
    )
    if caption:
        st.caption(caption)


# Display order also determines the links at the top of Tables.
_RECORDING_TABLES = {
    "fixations": ("Fixations", "One row per fixation, with its position and duration."),
    "words": (
        "Words",
        "One row per word area, with its position and any supplied reading measures.",
    ),
    "raw_gaze": (
        "Raw gaze samples",
        "One row per eye-tracker sample, including samples with missing positions.",
    ),
}
_ENTITY_TABLES = {
    "participant": (
        "Participants",
        "One row per participant, with counts from their recordings.",
    ),
    "trial": (
        "Trials",
        "One row per participant and trial, with counts from that reading.",
    ),
    "text": (
        "Texts",
        "One row per text. Passages are assembled from the words when available.",
    ),
}


def _entity_counts(frames: list[pd.DataFrame], keys: list[str]) -> pd.DataFrame:
    """The distinct ``keys`` across ``frames`` — every frame that carries them."""
    parts = [
        f[keys].dropna().drop_duplicates()
        for f in frames
        if not f.empty and all(k in f.columns for k in keys)
    ]
    if not parts:
        return pd.DataFrame(columns=keys)
    return pd.concat(parts, ignore_index=True).drop_duplicates(ignore_index=True)


def _count_by(
    out: pd.DataFrame, frame: pd.DataFrame, keys: list[str], label: str, how
) -> pd.DataFrame:
    """Left-join one count column onto ``out``; 0 where ``frame`` has none."""
    if frame.empty or not all(k in frame.columns for k in keys):
        return out
    counts = how(frame.groupby(keys, dropna=True)).rename(label).reset_index()
    out = out.merge(counts, on=keys, how="left")
    out[label] = out[label].fillna(0).astype(int)
    return out


def _with_constants(
    out: pd.DataFrame, frames: list[pd.DataFrame], keys: list[str]
) -> pd.DataFrame:
    """Add every column that holds one value per ``keys`` row to ``out``.

    Per trial: conditions, answers, list or batch ids arrive repeated on each
    fixation (or AOI) row of their trial. Per reader: age, group, session or
    list arrive the same way. One value per row of ``out`` is what makes them
    facts about it. Fixations are read first, then the AOI rows for any column
    they do not carry. A column with the same value in every row says nothing
    about any one of them and is left out, as is one that repeats a column
    already shown (``unique_paragraph_id`` beside the text id). Local paths
    are cut to their file name.
    """
    shown = {tuple(out[c].astype("string").fillna("").tolist()) for c in out.columns}
    for frame in frames:
        if frame.empty or not all(k in frame.columns for k in keys):
            continue
        frame = shareable_frame(frame)
        candidates = [c for c in frame.columns if c not in out.columns]
        if not candidates:
            continue
        grouped = frame.groupby(keys, dropna=True, sort=False)
        constant = []
        for column in candidates:
            try:
                if grouped[column].nunique(dropna=True).max() <= 1:
                    constant.append(column)
            except TypeError:
                # Nested values in an extra Parquet column have no scalar group count.
                continue
        if not constant:
            continue
        values = strip_local_paths(grouped[constant].first().reset_index())
        values = out[keys].merge(values, on=keys, how="left")
        for column in constant:
            col = values[column]
            if col.nunique(dropna=True) <= 1:
                continue
            signature = tuple(col.astype("string").fillna("").tolist())
            if signature in shown:
                continue
            shown.add(signature)
            out[column] = col.to_numpy()
    return out


@st.cache_data(show_spinner=False)
def _ids_from_data(
    kind: str,
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    cache_key,
    _raw_gaze: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The participants / trials / texts the loaded data names, with counts.

    What the Participants/Trials/Texts tabs show when no separate table is
    attached: the ids are in the fixation and AOI rows either way, so an empty
    tab read as "this dataset has none". Counts only — distinct ids and row
    counts, nothing computed from the eye movements — and, on the trial rows,
    the data's own columns that hold one value per trial or per reader
    (:func:`_with_constants`).
    """
    recordings = [_fixations, _words]
    frames = [*recordings, _raw_gaze] if _raw_gaze is not None else recordings
    pid, tid, xid = "participant_id", "trial_id", "text_id"
    reading_texts = metadata_readings(_words, _fixations, _raw_gaze).dropna(
        subset=[xid]
    )
    if kind == "participant":
        out = _entity_counts(frames, [pid])
        if out.empty:
            return out
        trials = _entity_counts(frames, [pid, tid])
        out = _count_by(out, trials, [pid], "# Trials", lambda g: g.size())
        texts = reading_texts[[pid, xid]].drop_duplicates()
        out = _count_by(out, texts, [pid], "# Texts", lambda g: g.size())
        out = _count_by(out, _fixations, [pid], "# Fixations", lambda g: g.size())
        if _raw_gaze is not None:
            out = _count_by(out, _raw_gaze, [pid], "# Gaze samples", lambda g: g.size())
        out = _with_constants(out, recordings, [pid])
        return out.sort_values(pid, ignore_index=True).rename(
            columns={pid: "Participant ID"}
        )
    if kind == "trial":
        out = _entity_counts(frames, [pid, tid])
        if out.empty:
            return out
        texts = reading_texts
        if not texts.empty:
            texts = (
                texts.astype({xid: "string"})
                .groupby([pid, tid])[xid]
                .agg(lambda s: ", ".join(sorted(s.unique())))
                .reset_index()
            )
            out = out.merge(texts, on=[pid, tid], how="left")
        out = _count_by(out, _fixations, [pid, tid], "# Fixations", lambda g: g.size())
        if "word_id" in _words.columns:
            out = _count_by(out, _words, [pid, tid], "# Words", lambda g: g.size())
        if _raw_gaze is not None:
            out = _count_by(
                out, _raw_gaze, [pid, tid], "# Gaze samples", lambda g: g.size()
            )
        out = _with_constants(out, recordings, [pid, tid])
        return out.sort_values([pid, tid], ignore_index=True).rename(
            columns={pid: "Participant ID", tid: "Trial ID", xid: "Text ID"}
        )
    # A text can have recorded gaze or fixations without a Words table.
    out = reading_texts[[xid]].drop_duplicates().rename(columns={xid: "Text ID"})
    if out.empty:
        return out
    passages = _build_stimuli_table_cached(
        _words, cache_key, _reading_texts=reading_texts
    )
    if not passages.empty:
        out = out.merge(passages, on="Text ID", how="left")
    readers = (
        reading_texts[[xid, pid]].drop_duplicates().rename(columns={xid: "Text ID"})
    )
    out = _count_by(out, readers, ["Text ID"], "# Participants", lambda g: g.size())
    if "# Participants" in out.columns:
        first = ["Text ID", "# Participants"]
        out = out[first + [c for c in out.columns if c not in first]]
    return out


def _render_raw_metadata_tab(
    kind, attached, words, fixations, raw_gaze, *, filtered: bool
) -> None:
    """Show the supplied metadata file, or summarize the IDs in the recordings."""
    label, description = _ENTITY_TABLES[kind]
    if attached is not None and not attached.frame.empty:
        note = f"From **{md_literal(attached.source_name)}**. One row per {kind}."
        if filtered:
            note += " This file includes all rows, regardless of the Scanpath filters."
        st.caption(note)
        _render_raw_table(attached.frame)
        return
    derived = _ids_from_data(
        kind,
        words,
        fixations,
        _raw_gaze=raw_gaze,
        cache_key=(
            kind,
            *(frame_fingerprint(frame) for frame in (words, fixations, raw_gaze)),
        ),
    )
    if derived.empty:
        st.caption(
            f"No {label.lower()} in the selected trials."
            if filtered
            else f"No {label.lower()} found."
        )
        return
    st.caption(description)
    names = active_column_names(st.session_state, "fixations")
    st.dataframe(
        derived,
        hide_index=True,
        width="stretch",
        lazy=True,
        column_config=column_label_config(derived.columns, names),
    )


@st.cache_data(show_spinner="Building stimuli list…", show_time=True)
def _build_stimuli_table_cached(
    _words: pd.DataFrame, cache_key, *, _reading_texts: pd.DataFrame | None = None
) -> pd.DataFrame:
    """One row per Text ID, with the stimulus text reconstructed from its words.

    The word table carries one row per word per text (and, for per-participant
    tables, repeated once per reader). We collapse identical word rows across
    participants, then join each text's words in reading order (line, then word
    id) into a single passage string. Cached on a cheap content fingerprint of
    the words frame (the frame itself is passed un-hashed via the underscore
    arg) so a rerun that doesn't change the data reuses the result.

    A multipart text is read screen by screen, and its word ids (and lines)
    may start again on every screen: a word is ``(screen, word id)`` there, the
    screens go in their ``screen_index`` order (the earliest any reader saw
    each, since MultiplEYE shuffles question screens per reader), and every
    screen of a text with more than one opens with its own ``[screen id]``
    marker — naming the screen's kind when the data has one — with a
    *# Screens* column beside.
    """
    empty = pd.DataFrame(columns=["Text ID", "# Words", "Text"])
    if _words.empty or "text_id" not in _words.columns or "text" not in _words.columns:
        return empty

    multipart = SCREEN_ID in _words.columns
    cols = [
        c
        for c in (
            "text_id",
            "unique_text_id",
            SCREEN_ID,
            SCREEN_INDEX,
            "screen_kind",
            "word_id",
            "line_idx",
            "text",
        )
        if c in _words.columns
    ]
    if _reading_texts is None:
        sub = _words[cols].copy()
    else:
        # A text table uses the same identity as its participant and trial counts.
        # A default copied from the trial ID may be superseded by another table.
        identity = ["participant_id", "trial_id"]
        recorded = _metadata_mod.unambiguous_readings(_reading_texts).rename(
            columns={"text_id": "_recorded_text"}
        )
        sub = (
            _words[[*identity, *cols]]
            .astype(dict.fromkeys(identity, "str"))
            .merge(recorded, on=identity, how="left", validate="many_to_one")
        )
        own = sub.get("unique_text_id", sub["text_id"]).fillna(sub["text_id"])
        sub["text_id"] = sub.pop("_recorded_text").fillna(own)
    sub = sub.dropna(subset=["text_id"])
    if sub.empty:
        return empty

    if multipart:
        sub[SCREEN_ID] = sub[SCREEN_ID].astype("string").fillna("")
        # One position per screen of a text: the earliest any reader had it.
        position = (
            pd.to_numeric(sub[SCREEN_INDEX], errors="coerce")
            if SCREEN_INDEX in sub.columns
            else pd.Series(np.nan, index=sub.index)
        )
        sub["_screen_order"] = position.groupby(
            [sub["text_id"], sub[SCREEN_ID]], dropna=False
        ).transform("min")

    # Collapse identical word rows coming from multiple participants (stimulus
    # AoIs are shared by every reader; per-participant tables repeat them). On
    # a multipart text a word is only the same word on the same screen.
    word_key = ["text_id", *([SCREEN_ID] if multipart else [])]
    if "word_id" in sub.columns:
        sub = sub.drop_duplicates(subset=[*word_key, "word_id"])
    else:
        sub = sub.drop_duplicates(subset=[c for c in sub.columns if c != SCREEN_INDEX])

    screen_sort = ["_screen_order", SCREEN_ID] if multipart else []
    sort_cols = (
        ["text_id"]
        + screen_sort
        + [c for c in ("line_idx", "word_id") if c in sub.columns]
    )
    sub = sub.sort_values(sort_cols, kind="stable", na_position="last")

    # Only surface unique_text_id as its own column when it actually differs
    # from text_id (after the unique_paragraph_id fallback they're identical).
    has_unique = "unique_text_id" in sub.columns and not (
        sub["unique_text_id"].astype(str).eq(sub["text_id"].astype(str)).all()
    )

    def _words_of(frame: pd.DataFrame) -> list[str]:
        return [w for w in frame["text"].astype(str).tolist() if w and w != "nan"]

    def _screen_marker(screen_id: str, frame: pd.DataFrame) -> str:
        label = screen_id or "(no screen id)"
        if "screen_kind" in frame.columns:
            kinds = frame["screen_kind"].dropna().astype(str).unique().tolist()
            if len(kinds) == 1 and kinds[0].lower() not in label.lower():
                label = f"{label} · {kinds[0]}"
        return f"[{label}]"

    rows = []
    for text_id, grp in sub.groupby("text_id", sort=False):
        words_list = _words_of(grp)
        n_screens = grp[SCREEN_ID].nunique() if multipart else 1
        if n_screens > 1:
            text = " ".join(
                " ".join([_screen_marker(str(screen), page), *_words_of(page)])
                for screen, page in grp.groupby(SCREEN_ID, sort=False)
            )
        else:
            text = " ".join(words_list)
        row = {"Text ID": text_id, "# Words": len(words_list), "Text": text}
        if multipart:
            row["# Screens"] = n_screens
        if has_unique:
            uniques = grp["unique_text_id"].dropna().astype(str).unique().tolist()
            row["Unique Text ID"] = ", ".join(uniques)
        rows.append(row)

    result = pd.DataFrame(rows)
    ordered = ["Text ID"]
    if has_unique:
        ordered.append("Unique Text ID")
    if multipart:
        ordered.append("# Screens")
    ordered += ["# Words", "Text"]
    return result[[c for c in ordered if c in result.columns]]


def _render_data_provenance() -> None:
    """Show a 'source / cohort / date / file mtime' banner above the Raw Data
    sub-tabs so reviewers can verify which OneStop export they're looking at.

    Only renders when ONESTOP_DATA_DIR is set (i.e. the OneStop local export is
    the active data source). For uploads / bundled demo, falls through silently.
    """
    from datetime import datetime

    from .data import onestop_data_provenance

    # Honour the deep-link participant so the per-pid shard's mtime is shown.
    pid = st.session_state.get("single_participant")
    info = onestop_data_provenance(participant=pid)
    if not info:
        return

    def _fmt_mtime(ts):
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "—"

    cols = st.columns(4)
    cols[0].metric("Source", info.get("source", "—"))
    cols[1].metric("Cohort", info.get("cohort", "—"))
    cols[2].metric("Date", info.get("date", "—"))
    cols[3].metric("File last modified", _fmt_mtime(info.get("ia_shard_mtime")))

    with st.expander("Data provenance — full paths"):
        st.caption(f"`ONESTOP_DATA_DIR = {info.get('data_dir', '?')}`")
        st.caption(
            f"loaded from: **{info.get('loaded_from', '?')}**"
            + (f"  ·  participant `{pid}`" if pid else "")
        )
        if "ia_shard" in info:
            st.caption(
                f"IA file: `{info['ia_shard']}`  "
                f"·  modified `{_fmt_mtime(info.get('ia_shard_mtime'))}`"
            )
        if "fix_shard" in info:
            st.caption(
                f"Fixations file: `{info['fix_shard']}`  "
                f"·  modified `{_fmt_mtime(info.get('fix_shard_mtime'))}`"
            )


def _render_word_reading_measures(words: pd.DataFrame) -> None:
    measures = brought_reading_measures(words)
    if measures:
        labels = {column: label for _, column, label, *_ in READING_MEASURE_FIELDS}
        labels.update((m.column, m.label) for m in MEASURES.values())
        with st.expander(f"Reading measures in the Words table ({len(measures)})"):
            st.markdown("\n".join(f"- {labels[column]}" for column in measures))


def render_data_tables(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame,
    *,
    scope: str | None,
    whole_dataset: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Show all six tables together with direct links to their headings."""
    links = [
        f"[{label}](#data-table-{key})"
        for key, (label, _) in (*_RECORDING_TABLES.items(), *_ENTITY_TABLES.items())
    ]
    with st.container(key="data_table_links"):
        st.markdown("  ·  ".join(links))
    render_data_scope(scope, key="data_scope_tables")
    all_words, all_fixations, all_gaze = whole_dataset
    recordings = {
        "fixations": (fixations, all_fixations),
        "words": (words, all_words),
        "raw_gaze": (raw_gaze, all_gaze),
    }
    for key, (label, description) in _RECORDING_TABLES.items():
        frame, whole = recordings[key]
        with st.container(key=f"data_table_{key}"):
            st.subheader(label, anchor=f"data-table-{key}")
            if key == "words":
                _render_word_reading_measures(frame)
            if frame.empty:
                if whole.empty:
                    forget_frame_cache(f"data_table_display_{key}")
                st.caption(
                    "No rows match the Scanpath filters."
                    if not whole.empty
                    else "This dataset has no rows in this table."
                )
                continue
            st.caption(description)
            _render_raw_table(frame, table=key)
    attachments = (
        _metadata_mod.active(),
        _metadata_mod.active_trials(),
        _metadata_mod.active_texts(),
    )
    for (key, (label, _)), attached in zip(
        _ENTITY_TABLES.items(), attachments, strict=True
    ):
        with st.container(key=f"data_table_{key}"):
            st.subheader(label, anchor=f"data-table-{key}")
            _render_raw_metadata_tab(
                key, attached, words, fixations, raw_gaze, filtered=bool(scope)
            )
    if derived_analysis_tables_enabled():
        _render_derived_tables(words, fixations, raw_gaze)


# -----------------------------------------------------------------------------
# Statistics Tab
# -----------------------------------------------------------------------------


@st.cache_data(show_spinner="Computing dataset statistics…", show_time=True)
def _dataset_statistics(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    cache_key,
) -> dict:
    """Compute counts and averages for the same filtered set of readings."""
    frames = {"fixations": _fixations, "words": _words, "raw_gaze": _raw_gaze}
    keys = {table: trial_keys(frame) for table, frame in frames.items()}
    trials = set.union(*keys.values())
    per_reader = pd.Series(Counter(pid for pid, _ in trials), dtype=int)
    spread = []
    if trials:
        spread.append({"Metric": "Trials per participant", **safe_summary(per_reader)})
    for table, label in (
        ("fixations", "Fixations per trial"),
        ("words", "Words per trial"),
        ("raw_gaze", "Gaze samples per trial"),
    ):
        if not keys[table] or (table == "raw_gaze" and keys["fixations"]):
            continue
        # Average among trials with this table. The coverage column shows that denominator.
        counts = frames[table].groupby(["participant_id", "trial_id"]).size()
        spread.append({"Metric": label, **safe_summary(counts)})
    parts, screen_error = _screen_catalog_status(_words, _fixations, _raw_gaze)
    return {
        "parts": parts,
        "screen_error": screen_error,
        "n_participants": len(per_reader),
        "n_trials": len(trials),
        "n_texts": len(text_ids(_words, _fixations, _raw_gaze)),
        "recordings": {k: (len(frame), len(keys[k])) for k, frame in frames.items()},
        "fixations_without_words": len(keys["fixations"] - keys["words"]),
        "stats_df": pd.DataFrame(spread).rename(
            columns={"mean": "Mean", "std": "Std", "min": "Min", "max": "Max"}
        ),
    }


# Friendly field labels for the column-mapping summary, per source table. Box
# fields are spelled out so the words table reads clearly (e.g. "Box left").
_WORD_MAPPING_LABELS = {
    "participant": "Participant ID",
    "trial": "Trial ID",
    "word_id": "Word ID",
    "text": "Word text",
    "text_id": "Text ID",
    "line": "Line index",
    "left": "Box left",
    "right": "Box right",
    "top": "Box top",
    "bottom": "Box bottom",
    "x": "Box x",
    "y": "Box y",
    "width": "Box width",
    "height": "Box height",
}
_FIX_MAPPING_LABELS = {
    "participant": "Participant ID",
    "trial": "Trial ID",
    "x": "X coordinate",
    "y": "Y coordinate",
    "duration": "Duration (ms)",
    "timestamp": "Timestamp (ms)",
    "fixation_id": "Fixation ID",
    "text_id": "Text ID",
    "word_id": "Word ID",
}
_RAW_GAZE_MAPPING_LABELS = {spec["key"]: spec["label"] for spec in RAW_GAZE_FIELD_SPECS}
_MAPPING_TABLES = [
    ("Words (interest areas)", "words", _WORD_MAPPING_LABELS),
    ("Fixations", "fixations", _FIX_MAPPING_LABELS),
    ("Raw gaze", "raw_gaze", _RAW_GAZE_MAPPING_LABELS),
]


def _column_mapping_rows(mapping: dict) -> list[dict]:
    """Flatten the stashed per-table schemas into one ``Table / Field / Mapped
    column`` row list, dropping unmapped fields and joining composite trial ids."""
    rows: list[dict] = []
    for table_label, schema_key, labels in _MAPPING_TABLES:
        schema = mapping.get(schema_key)
        if not schema:
            continue
        for field_key, label in labels.items():
            col = schema.get(field_key)
            if col is None:
                continue
            if isinstance(col, (list, tuple)):
                col = " + ".join(str(c) for c in col)
            rows.append(
                {"Table": table_label, "Field": label, "Mapped column": str(col)}
            )
    return rows


def _render_readonly_mapping_grid(rows: list[dict]) -> None:
    """Show a built-in source mapping in the add-dataset screen's field grid.

    Built-in mappings cannot be edited, but presenting them as label-over-value
    cells keeps the same visual grammar as the editable setup and remap screens.
    """
    tables: dict[str, list[dict]] = {}
    for row in rows:
        tables.setdefault(str(row["Table"]), []).append(row)
    for table, fields in tables.items():
        st.markdown(
            f'<div class="sps-readonly-map-table">{html.escape(table)}</div>',
            unsafe_allow_html=True,
        )
        for start in range(0, len(fields), 4):
            chunk = fields[start : start + 4]
            cells = st.columns(4, gap="small")
            for cell, row in zip(cells, chunk):
                field = html.escape(str(row["Field"]))
                value = html.escape(str(row["Mapped column"]))
                cell.markdown(
                    '<div class="sps-readonly-map-cell">'
                    f'<div class="sps-readonly-map-label">{field}</div>'
                    f'<div class="sps-readonly-map-value">{value}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )


# Field-key → canonical post-normalization column for each table. The remap
# editor seeds from these (the normalized frame's columns ARE these names) so it
# opens showing the current mapping. The word box always seeds x/y/width/height
# because normalize_words converts edge coordinates to origin+size.
_WORD_REMAP_CANON = {
    "participant": "participant_id",
    "trial": "trial_id",
    "word_id": "word_id",
    "text": "text",
    "text_id": "text_id",
    "line": "line_idx",
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
    # Each reading measure is stored under its canonical column.
    **{key: column for key, column, *_ in READING_MEASURE_FIELDS},
}
_FIX_REMAP_CANON = {
    "participant": "participant_id",
    "trial": "trial_id",
    "x": "x",
    "y": "y",
    "duration": "duration_ms",
    "timestamp": "timestamp_ms",
    "fixation_id": "fixation_id",
    "text_id": "text_id",
    "word_id": "word_id",
}
_RAW_GAZE_REMAP_CANON = {
    "participant": "participant_id",
    "trial": "trial_id",
    "x": "x",
    "y": "y",
    "timestamp": "timestamp_ms",
    "text": "text",
    **{
        key: key
        for key in (
            "text_id",
            "word_id",
            "screen_id",
            "screen_index",
            "canvas_width",
            "canvas_height",
            "pupil_area",
            "pupil_diameter",
            "eye",
        )
    },
}
# (table_key, label, field_specs, canonical-map) for the editable remap form.
_REMAP_TABLES = [
    ("words", "Words (interest areas)", WORD_FIELD_SPECS, _WORD_REMAP_CANON),
    ("fixations", "Fixations", FIX_FIELD_SPECS, _FIX_REMAP_CANON),
    ("raw_gaze", "Raw gaze", RAW_GAZE_FIELD_SPECS, _RAW_GAZE_REMAP_CANON),
]
# Validators keyed by table — checked before a remap is applied.
_REMAP_VALIDATORS = {
    "words": validate_word_schema,
    "fixations": validate_fix_schema,
    "raw_gaze": validate_raw_gaze_schema,
}


def _active_stored_dataset() -> tuple | None:
    """``(name, entry)`` for the active source when it's a stored upload, else
    ``None`` — gates the editable remap form to stored datasets only."""
    name = st.session_state.get("data_source_choice")
    entry = st.session_state.get("_datasets", {}).get(name)
    return (name, entry) if entry is not None else None


def _remap_proposed(schema: dict | None, frame_columns, canon: dict) -> dict:
    """Seed the remap editor from the stored schema: each field the dataset had
    mapped → its canonical column (present in the now-normalized frame), else
    ``None``. The word box (canon ``_WORD_REMAP_CANON``) always seeds its four
    geometry keys since normalize collapses any edge format to x/y/width/height."""
    cols = set(frame_columns)
    schema = schema or {}
    is_word_box = canon is _WORD_REMAP_CANON
    proposed: dict = {}
    for key, canonical in canon.items():
        if canonical not in cols:
            proposed[key] = None
        elif is_word_box and key in ("x", "y", "width", "height"):
            proposed[key] = canonical
        elif key in READING_MEASURE_KEYS:
            # A stored measure column is what the dataset brought, even in a
            # dataset saved before measures had a mapping of their own.
            proposed[key] = canonical
        elif key == "text_id":
            # text_id always exists post-normalization (falls back to trial_id);
            # always seed it so a remap preserves text grouping instead of
            # collapsing every reading of a text into its own trial_id.
            proposed[key] = canonical
        elif key == "word_id" and schema.get(key) and WORD_KEY in cols:
            # Text Word IDs: the ids themselves, which the save numbers and
            # matches again, never the numbers the load gave them.
            proposed[key] = WORD_KEY
        else:
            proposed[key] = canonical if schema.get(key) else None
    return proposed


#: What a ✅ Save changes' stimulus join warned about (some readings
#: found no word boxes), shown under the success line on the screen the save
#: returns to. Not a `_remap_*` key: those are cleared when the save ends.
STIMULUS_JOIN_NOTICE_KEY = "_stimulus_join_notice"


def _harmonize_noting_join(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    rewrites: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``harmonize_frames``, keeping its ``StimulusJoinWarning`` for the page.

    ✅ Save changes runs in an ``on_click``, where a warning only reaches the
    server's terminal; this parks its text under ``STIMULUS_JOIN_NOTICE_KEY``
    instead. Any other warning is re-raised as it was. The columns
    whose values it changed (``data.Rewrite``) go into ``rewrites``."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        words, fixations, _join, changed = harmonize_frames_reporting(words, fixations)
        result = (words, fixations)
    if rewrites is not None:
        rewrites.extend(changed)
    notices = []
    for record in caught:
        if issubclass(record.category, StimulusJoinWarning):
            notices.append(str(record.message))
        else:
            warnings.warn_explicit(
                record.message, record.category, record.filename, record.lineno
            )
    if notices:
        st.session_state[STIMULUS_JOIN_NOTICE_KEY] = notices
    return result


def _reading_keys(frame, columns) -> set:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return set()
    if not set(columns) <= set(frame.columns):
        return set()
    # Deduplicated before the text conversion: a raw-gaze table is samples.
    rows = frame[list(columns)].drop_duplicates().dropna().astype(str)
    return set(map(tuple, rows.to_numpy()))


def raw_gaze_identity_problem(raw_gaze: pd.DataFrame, entry: dict) -> str | None:
    """Why a raw-gaze table cannot join this dataset, or ``None`` if it can.

    Samples are drawn under the scanpath of the reading — participant + trial,
    and the screen on a multipart dataset — they share, so a table that shares
    none with the dataset's fixations (else its word boxes) would attach and
    then never appear. Said before Save commits it, naming the fields to check.
    """
    parent = ["participant_id", "trial_id"]
    for table_key in ("fixations", "words"):
        frame = entry.get(table_key)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            break
    else:
        return None
    if not _reading_keys(raw_gaze, parent) & _reading_keys(frame, parent):
        return (
            "None of its trials match this dataset's: no sample has a "
            "participant and trial that appear in the "
            f"{_TABLE_LABELS[table_key].split()[0]} table. Check that "
            "**Participant ID** and **Trial ID** name the same participants and "
            "trials, spelled the same way."
        )
    gaze_screens = (
        "screen_id" in raw_gaze.columns and raw_gaze["screen_id"].notna().any()
    )
    data_screens = "screen_id" in frame.columns and frame["screen_id"].notna().any()
    if gaze_screens and not data_screens:
        return (
            "It maps a **Screen ID**, but this dataset has no screens. Clear "
            "Screen ID, or add the dataset again with its screens mapped."
        )
    if gaze_screens and not (
        _reading_keys(raw_gaze, [*parent, "screen_id"])
        & _reading_keys(frame, [*parent, "screen_id"])
    ):
        return (
            "Its trials match, but none of its screens do. Check that "
            "**Screen ID** names the same screens as the dataset's."
        )
    return None


def _apply_remap() -> None:
    """Re-derive the active stored dataset's frames under the edited mapping and
    overwrite the entry in place (the "Apply remapping" button's ``on_click``).

    Reads the per-table schemas captured during render in
    ``_remap_pending_schemas``; validates each present table; on success
    re-normalizes via ``data.remap_normalized_frame`` and recomputes the
    composite trial components. ``app.main``'s stored-dataset branch then
    re-publishes the new frames + mapping on the rerun this callback triggers."""
    st.session_state.pop(STIMULUS_JOIN_NOTICE_KEY, None)
    active = _active_stored_dataset()
    if active is None:
        return
    name, stored = active
    pending = st.session_state.get("_remap_pending_schemas") or {}
    # Tables uploaded on this screen because the dataset had none.
    # Validated on the same terms as the rest, and blocking Save the same way:
    # an incomplete mapping for a table being added must not attach half of it.
    added = [
        table_key
        for table_key in (st.session_state.get("_remap_added_tables") or [])
        if isinstance(
            st.session_state.get(_added_raw_key(name, table_key)), pd.DataFrame
        )
    ]
    problems: dict = {}
    for table_key in ("words", "fixations", "raw_gaze"):
        frame = stored.get(table_key)
        present = frame is not None and not frame.empty
        if (not present and table_key not in added) or table_key not in pending:
            continue
        probs = _REMAP_VALIDATORS[table_key](pending[table_key])
        if probs:
            problems[table_key] = probs
    if problems:
        st.session_state["_remap_problems"] = problems
        return
    st.session_state.pop("_remap_problems", None)

    new_entry = dict(stored)
    new_schemas = dict(stored.get("schemas") or {})
    # The save maps fields onto the stored frame's *canonical* columns; read
    # through the dataset's earlier record, the column-name map keeps the
    # user's names (built from `schemas` alone it would be the identity).
    new_names = dict(stored.get("column_names") or {})
    # Which stored trial ids are repeats of which, so a dataset
    # stored before the join recorded provenance folds a repeat's copy of the
    # boxes back into the trial it copied (`data.repeat_bases`).
    repeat_of = repeat_bases(stored.get("fixations"))
    # The columns the fixups below change the values of.
    rewrites: list = []
    # Share → Code's record of how a script loads this dataset's files: a
    # remap is restated in the files' own names, an added table is its own.
    recipe = stored_source_recipe(stored)
    recipe_schemas = dict(recipe.get("schemas") or {})
    unresolved = dict(recipe.get("unresolved") or {})
    steps = list(recipe.get("steps") or [])
    for table_key in ("words", "fixations", "raw_gaze"):
        frame = stored.get(table_key)
        if frame is None or frame.empty or table_key not in pending:
            continue
        schema = pending[table_key]
        try:
            new_entry[table_key] = remap_normalized_frame(
                frame, schema, kind=table_key, repeat_of=repeat_of
            )
        except Exception as exc:
            # A complete mapping the data does not fit (a Screen ID that maps
            # to two screen orders in one trial, say). Reported on the screen
            # like the added tables' failures below, never raised from this
            # `on_click`; nothing is saved — `new_entry` is only written back
            # at the end, so the tables remapped before this one stay as they
            # were too — and the draft stays open to be corrected.
            from scanpath_studio.app import mapping_failure_problem

            st.session_state["_remap_problems"] = {
                table_key: [mapping_failure_problem(exc)]
            }
            return
        new_schemas[table_key] = schema
        earlier = ColumnNames.from_payload(new_names.get(table_key))
        recipe_schemas[table_key], missing = source_schema(schema, earlier)
        unresolved[table_key] = list(missing)
        new_names[table_key] = (
            from_schema(table_key, schema, frame.columns)
            .through(earlier)
            # A field the edit cleared left the frame; its name goes with it.
            .restricted_to(new_entry[table_key].columns)
            .to_payload()
        )
    # …then the added ones, which are *raw*: they take the same normalization
    # the add-dataset screen runs, and then `harmonize_frames` — the
    # cross-frame fixups (id dtypes, the word-id offset, AoI-only
    # fixations placed at word-box centres) are exactly what makes a half
    # uploaded today line up with a half uploaded weeks ago. Both halves are
    # written back, because harmonizing can change either.
    harmonized = False
    # Raw gaze last, so it is matched against the fixations and boxes this save
    # ends with, including a table added beside it.
    for table_key in sorted(added, key=lambda key: key == "raw_gaze"):
        raw = st.session_state.get(_added_raw_key(name, table_key))
        if raw is None or raw.empty or table_key not in pending:
            continue
        schema = pending[table_key]
        try:
            if table_key == "raw_gaze":
                fresh = normalize_raw_gaze(raw, schema)
                if problem := raw_gaze_identity_problem(fresh, new_entry):
                    st.session_state["_remap_problems"] = {"raw_gaze": [problem]}
                    return
                new_entry["raw_gaze"] = fresh
            elif table_key == "words":
                # The add screen's aggregation, on the add-a-table
                # path. Runs on the RAW frame before normalization, which is the
                # only point it can: `normalize_words` expects one row per box.
                if st.session_state.get(aggregate_key(name)):
                    raw = aggregate_char_boxes(raw, schema)
                    steps.append("aggregate_char_boxes")
                fresh = normalize_words(raw, schema)
                other = new_entry.get("fixations")
                if not isinstance(other, pd.DataFrame) or other.empty:
                    other = empty_fixations_frame()
                fresh, other = _harmonize_noting_join(fresh, other, rewrites)
                new_entry["words"], new_entry["fixations"] = fresh, other
            else:
                fresh = normalize_fixations(raw, schema)
                other = new_entry.get("words")
                if not isinstance(other, pd.DataFrame) or other.empty:
                    other = empty_words_frame()
                other, fresh = _harmonize_noting_join(other, fresh, rewrites)
                new_entry["words"], new_entry["fixations"] = other, fresh
            harmonized = harmonized or table_key != "raw_gaze"
        except Exception as exc:
            # The mapping is complete but the pipeline rejects the combination
            # (`app.mapping_failure_problem` names the usual causes). Reported
            # like any other blocker rather than raised: this runs in an
            # `on_click`, where an exception is a red traceback over the page.
            from scanpath_studio.app import mapping_failure_problem

            st.session_state["_remap_problems"] = {
                table_key: [mapping_failure_problem(exc)]
            }
            return
        new_schemas[table_key] = schema
        recipe_schemas[table_key] = dict(schema)
        unresolved.pop(table_key, None)
        # An added table is raw: its names are its own.
        new_names[table_key] = from_schema(table_key, schema, raw.columns).to_payload()
    # The same cross-frame fixups for the tables this save *remapped*. A
    # remapped Words table with no Participant comes back stimulus-level (the
    # first reader's copy of each trial, on the "" placeholder reader), and
    # only `harmonize_frames` broadcasts it back onto the readers in the
    # fixations; without it no trial would find its word boxes, so every
    # scanpath would lose its AOIs and its text the moment ✅ Save changes is
    # pressed — which is what attaching a metadata table on this screen asks
    # for. Idempotent on frames that were already harmonized, so the ordinary
    # per-reader case saves them unchanged. After the added tables,
    # not before: a table added above has *already* been harmonized with these,
    # and harmonizing a stimulus-level words frame against the empty fixations
    # of a words-only dataset first would stamp it with the synthetic reader and
    # leave nothing for the added fixations to broadcast onto.
    before = new_entry.get("words")
    if (
        not harmonized
        and "words" in pending
        and isinstance(before, pd.DataFrame)
        and not before.empty
    ):
        fixations = new_entry.get("fixations")
        has_fixations = isinstance(fixations, pd.DataFrame) and not fixations.empty
        try:
            words, fixations = _harmonize_noting_join(
                before,
                fixations if has_fixations else empty_fixations_frame(),
                rewrites,
            )
        except Exception as exc:
            # Same reason as the added tables above: an `on_click` must report,
            # not raise — e.g. a changed Trial/Screen pick whose parts no longer
            # match the stored fixations (`validate_matching_parts`).
            from scanpath_studio.app import mapping_failure_problem

            st.session_state["_remap_problems"] = {
                "words": [mapping_failure_problem(exc)]
            }
            return
        # A stimulus-level table no reading can use never gets here: the
        # broadcast raises `StimulusJoinError` above, so the stored
        # boxes are never overwritten by nothing.
        new_entry["words"] = words
        if has_fixations:
            new_entry["fixations"] = fixations
    elif not harmonized and "fixations" in pending:
        # No Words table to harmonize with, so the refusal `harmonize_frames`
        # makes is made here: fixations whose only position is a text Word ID
        # have nothing to place them, and saving them would draw nothing.
        fixations = new_entry.get("fixations")
        if isinstance(fixations, pd.DataFrame) and (
            problem := unplaced_fixations_issue(empty_words_frame(), fixations)
        ):
            from scanpath_studio.app import MAPPING_FAILURE_LEAD

            st.session_state["_remap_problems"] = {
                "fixations": [f"{MAPPING_FAILURE_LEAD}: {problem}"]
            }
            return
    new_entry["schemas"] = new_schemas
    new_entry["column_names"] = {
        table: ColumnNames.from_payload(payload)
        .with_rewrites(table, rewrites)
        .to_payload()
        for table, payload in new_names.items()
    }
    new_entry["source_recipe"] = {
        **recipe,
        "schemas": recipe_schemas,
        "steps": list(dict.fromkeys(steps)),
        "unresolved": {t: f for t, f in unresolved.items() if f},
    }
    # Recompute the composite trial components from the new trial mapping so the
    # trial chips stay in sync (mirrors the wizard finalize).
    trial_schema = next(
        (
            new_schemas[t].get("trial")
            for t in ("fixations", "words", "raw_gaze")
            if new_schemas.get(t) and new_schemas[t].get("trial")
        ),
        None,
    )
    comp = trial_mapping_columns(trial_schema) if trial_schema else []
    new_entry["composite_trial_columns"] = comp if len(comp) > 1 else []
    setup_payload = st.session_state.get("_remap_pending_setup")
    if isinstance(setup_payload, dict):
        new_entry["setup"] = dict(setup_payload)
    st.session_state["_datasets"][name] = new_entry
    if isinstance(setup_payload, dict):
        from scanpath_studio.app import _apply_dataset_values, upload_setup_values

        # The saved setup shows at once when the figure holds this dataset's;
        # another dataset's figure is left alone, and this one's applies when
        # it is next opened (`app.seed_canvas_state`).
        if st.session_state.get(SETUP_OVERRIDE_FOR_KEY) == name and (
            values := upload_setup_values(name)
        ):
            _apply_dataset_values(name, values)
    from scanpath_studio.app import commit_editor_staging

    commit_editor_staging(name)
    requested = str(st.session_state.get(EDITOR_PENDING_NAME_KEY) or "").strip()
    if requested:
        from scanpath_studio.wizard import rename_dataset

        rename_dataset(name, requested)
    st.session_state["_remap_applied"] = name
    # Saving *is* the moment the Trial ID mapping is decided, so ask for the
    # trial-identity check's verdict on the frames this just re-derived.
    # `app.main` computes the report on the next run anyway; this only asks
    # it to be *said* — see
    # `app._trial_identity_alert_dialog`.
    st.session_state[TRIAL_IDENTITY_CHECK_KEY] = "edit"
    # Saving is the end of the edit, so it returns to 📂 Available
    # datasets the way ✅ Add dataset returns from the add screen. The success
    # line travels with it (`_remap_applied`, read above the dataset table);
    # printing it here would put it on a screen the user is leaving.
    #
    # Every `_remap_*` scratch key goes too. They describe an edit session:
    # what was uploaded but not yet attached, what was typed but not yet saved,
    # and what blocked the last attempt. Left behind, they would be read as the
    # *next* edit's starting point — of a different dataset, in the worst case.
    for key in [k for k in st.session_state if str(k).startswith("_remap_")]:
        if key != "_remap_applied":
            st.session_state.pop(key, None)
    discard_editor_widgets()
    st.session_state.pop(EDITOR_NAME_FIELD_KEY, None)
    # And the "use the current estimate" choice, which belongs to it.
    for key in [k for k in st.session_state if str(k).endswith("_setup_reestimate")]:
        st.session_state.pop(key, None)
    st.session_state.pop(DATASET_EDITOR_OPEN_KEY, None)
    st.session_state.pop(FOCUS_MAPPING_KEY, None)


#: The editor's field grid: the **same blocks the add-dataset screen
#: draws**: one block per table, read off `wizard.MAP_LINES` line by
#: line — its identity line first (what a row *is*: trial, reader, text,
#: screen), then the table's own fields — so the two screens' lines are the
#: same lines, at the same widths, to the pixel.
#:
#: ``(label, widths, fields, extra)`` per rendered line, ``fields`` being
#: ``("<table>", "<field>")`` pairs and ``extra`` naming a non-mapping control
#: that belongs under that line (the AOI block's char-aggregation
#: question, under the word box as on the add screen). A blank label continues
#: the block above it.
#:
#: Whatever a table's specs carry beyond these still lands on a trailing *More*
#: line, so a field can never be dropped by this list falling behind
#: ``*_FIELD_SPECS``.
def _edit_rows() -> tuple:
    from scanpath_studio.wizard import (
        _MAP_ROW_W,
        _META_ROW_W,
        MAP_LINES,
        MEASURE_ROW_W,
        MEASURE_ROWS,
    )

    def block(table: str, slug: str) -> tuple:
        return tuple(
            (
                _TABLE_LABELS[table] if index == 0 else "",
                _META_ROW_W if keys == ("box",) else _MAP_ROW_W,
                tuple((table, key) for key in keys),
                "aggregate" if keys == ("box",) else "",
            )
            for index, keys in enumerate(MAP_LINES[slug])
        )

    return (
        *block("fixations", "fix"),
        *block("words", "words"),
        # The reading measures, on the same two lines the add screen
        # gives them. Part of the AOI block, so no block gap above them.
        *(
            (
                "Reading measures" if line == 0 else "",
                MEASURE_ROW_W,
                tuple(("words", key) for key in keys),
                "measures",
            )
            for line, keys in enumerate(MEASURE_ROWS)
        ),
        *block("raw_gaze", "raw_gaze"),
    )


#: The trailing *More* line's grid: a name column and five equal cells.
_EDIT_ROW_W = (0.10, 0.18, 0.18, 0.18, 0.18, 0.18)

#: What each table is called down the editor's left-hand name column.
_TABLE_LABELS = {
    "fixations": "Fixations",
    "words": "Words (interest areas)",
    "raw_gaze": "Raw gaze",
}


#: The tables a stored dataset can be *missing* and later gain. A dataset
#: added from fixations alone is a complete dataset (the app draws a scanpath
#: with no text), and so is one added from word boxes alone (it draws a
#: heatmap from pre-aggregated measures); this gives either one its other
#: half without adding the whole dataset again. ``propose`` is
#: the auto-detect the add screen runs on a fresh upload.
_ADDABLE_TABLES = (
    (
        "fixations",
        "Add a fixations table",
        "Fixation table files, such as EyeLink's Fixation Report",
        propose_fix_schema,
    ),
    (
        "words",
        "Add a Words (interest areas) table",
        "Word table files, such as EyeLink's Interest Area Report",
        propose_word_schema,
    ),
    # The samples, for a dataset added from its
    # fixation / AOI reports before they were exported.
    (
        "raw_gaze",
        "Add a raw gaze table",
        "Raw gaze sample files",
        propose_raw_gaze_schema,
    ),
)


#: Each addable table's auto-detect, by table.
_ADDABLE_PROPOSERS = {key: propose for key, _h, _p, propose in _ADDABLE_TABLES}


def _added_raw_key(name: str, table_key: str) -> str:
    return f"_remap_add_raw_{name}_{table_key}"


def _render_missing_table_uploads(name: str, stored: dict, *, host=None) -> dict:
    """Uploaders for the tables this dataset has none of.

    Returns ``{table_key: raw_frame}`` for whatever has been uploaded, which
    :func:`_render_remap_fields` then maps with the *same* fields as a table
    that was there all along — the point being that adding the missing half
    is the same screen, not a second flow.

    The frame lives in session state rather than being re-read per rerun: an
    ``st.file_uploader`` hands back the same bytes on every run, and this page
    reruns on every keystroke in the mapping below it.
    """
    added: dict = {}
    host = host if host is not None else st
    for table_key, headline, prompt, _propose in _ADDABLE_TABLES:
        frame = stored.get(table_key)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            continue
        raw_key = _added_raw_key(name, table_key)
        box = host.container(border=True)
        box.markdown(f"**{headline}**")
        box.caption(
            "This dataset was added without one. Upload the file and map it "
            f"below. **{ICONS['confirm']} Save changes** adds it to the dataset."
        )
        uploads = box.file_uploader(
            prompt,
            type=list(UPLOAD_FILE_TYPES),
            accept_multiple_files=True,
            key=f"remap_add_upload_{name}_{table_key}",
            max_upload_size=upload_limit_mb(),
        )
        signature_key = f"_remap_add_file_{name}_{table_key}"
        if not uploads:
            # Clearing the uploader clears what it produced, or Save would
            # attach a table the user has just taken off the screen.
            st.session_state.pop(raw_key, None)
            st.session_state.pop(signature_key, None)
            continue
        # The files, and the columns read as literal text: a new Trial or text
        # pick can change those, and a value pandas has already turned into a
        # number or a missing cell cannot be recovered by a later mapping — so
        # the file is read again then, and only then (not when a pick names a
        # column that is already read as text, nor when the fields first seed
        # themselves with what auto-detection proposed).
        files = tuple(
            getattr(upload, "file_id", None)
            or (upload.name, getattr(upload, "size", None))
            for upload in uploads
        )
        held = st.session_state.get(signature_key)
        current = st.session_state.get(raw_key)
        stale = not (
            isinstance(held, tuple)
            and held[0] == files
            and isinstance(current, pd.DataFrame)
            and held[1] == _literal_columns(name, table_key, current.columns)
        )
        if stale:
            try:
                fresh = read_tables(
                    list(uploads),
                    plan_for=lambda header, table_key=table_key: _added_table_plan(
                        name, table_key, header
                    ),
                    # A zip of both EyeLink reports, read for one.
                    kind=table_key if table_key in ("words", "fixations") else None,
                )
                literal = _literal_columns(name, table_key, fresh.columns)
                # Named by what decides re-reading it, so the per-rerun
                # fingerprints (the editor's *Estimate from my data* above all)
                # never hash a table that can run to millions of rows.
                assign_fingerprint(
                    fresh, ("editor-added", name, table_key, files, literal)
                )
                st.session_state[raw_key] = fresh
                st.session_state[signature_key] = (files, literal)
            except Exception as exc:  # unreadable file — say so, keep the page
                st.session_state.pop(raw_key, None)
                box.error(
                    "Could not read that file. Check that it is a CSV, TSV, "
                    f"Parquet or Excel table with one header row. ({exc})"
                )
                continue
        raw = st.session_state.get(raw_key)
        if isinstance(raw, pd.DataFrame) and not raw.empty:
            box.caption(f"{len(raw):,} rows · {plural(len(raw.columns), 'column')}.")
            added[table_key] = raw
    return added


#: The mapping fields whose source columns are read as literal text: the ids
#: (`007` stays `007`) and the word text (`NA` stays a word).
_LITERAL_READ_FIELDS = (*IDENTITY_SCHEMA_FIELDS, "text")


def _added_table_picks(name: str, table_key: str) -> tuple:
    """What the user has picked so far for the literal-text fields of a table
    being added — the part of its mapping the file's read depends on."""
    prefix = f"remap_{name}_{table_key}_add"
    picks = []
    for field in _LITERAL_READ_FIELDS:
        key = f"{prefix}_{field}"
        if key in st.session_state:
            value = st.session_state[key]
            if isinstance(value, (list, tuple)):
                value = tuple(str(item) for item in value)
            picks.append((field, value))
    return tuple(picks)


def _added_table_plan(name: str, table_key: str, header) -> ReadPlan:
    """How to read a table being added on ✏️ Edit dataset — as the add screen does.

    The ids as text and the word text verbatim, decided before pandas infers
    anything (`data.verbatim_text_plan` / `identity_text_plan`): the columns
    the user has picked for those fields, else the ones auto-detection would
    propose from the header. Every column is still read — the editor decides
    what to keep only once the table is mapped.
    """
    names = [str(column) for column in header]
    schema = dict(_ADDABLE_PROPOSERS[table_key](pd.DataFrame(columns=names)))
    for field, value in _added_table_picks(name, table_key):
        schema[field] = list(value) if isinstance(value, tuple) else value
    if table_key == "words":
        return verbatim_text_plan(names, schema)
    return identity_text_plan(names, schema, kind=table_key)


def _literal_columns(name: str, table_key: str, header) -> tuple:
    """The columns `_added_table_plan` reads as literal text, for ``header``."""
    plan = _added_table_plan(name, table_key, header)
    return (tuple(sorted(plan.verbatim)), tuple(sorted(plan.identity)))


def aggregate_key(name: str) -> str:
    """Session key of the editor's char-AOI aggregation toggle."""
    return f"remap_{name}_aggregate_char_boxes"


def _render_aggregate_toggle(name: str, *, adding: bool) -> None:
    """The add screen's third AOI line, on the edit screen.

    Live only while a Words table is being **added**: aggregation collapses raw
    character rows into one box per word, and a table already in the dataset was
    normalized on the way in — its character rows no longer exist, so the
    honest answer for one is "upload the file again", not a toggle that would
    quietly do nothing. Rendered either way so the block keeps the add screen's
    shape, and disabled says which case you are in.
    """
    switch(
        st,
        "toggle",
        "Merge character boxes into word boxes",
        key=aggregate_key(name),
        disabled=not adding,
        # Read only by Save changes (`_apply_remap`), so a toggle needs no rerun.
        on_change="ignore",
        help="For Words tables with one row per *character*, as in some "
        "CJK corpora. Merges each word's characters (grouped by the Trial and "
        "Word ids above) into one bounding box."
        if adding
        else "Applies only to a Words table being added. This one was stored "
        "with one box per row. To merge character rows, add the dataset again "
        "with this on.",
    )


#: Why ✏️ Edit dataset's *Word box* format is fixed for a stored Words table.
STORED_BOX_FORMAT_REASON = (
    "Word boxes are stored as position + size. Edges were converted when the "
    "dataset was added."
)


def box_edges_note(stored: dict) -> str | None:
    """What ✏️ Edit dataset says under *Word box* when the dataset was added
    with each box's edges (EyeLink's ``IA_LEFT`` … ``IA_BOTTOM``).

    The editor maps the *stored* frame, which holds every box as its top-left
    corner and size — the edges were turned into a width and a height when the
    dataset was added, and are not columns of it any more. So the box shows as
    *Origin + size* here whatever the add screen showed; this says which
    edges it came from, so the two screens do not seem to disagree. ``None``
    when the box was read as x/y/width/height to begin with.
    """
    names = ColumnNames.from_payload((stored.get("column_names") or {}).get("words"))
    restated, _unresolved = source_schema(
        {"x": "x", "y": "y", "width": "width", "height": "height"}, names
    )
    edges = [(restated or {}).get(side) for side in ("left", "right", "top", "bottom")]
    if not all(isinstance(edge, str) for edge in edges):
        return None
    left, right, top, bottom = edges
    return (
        f"Added from each box's edges ({left}, {right}, {top}, {bottom}). It is "
        "stored, and edited here, as its top-left corner and size: Box width is "
        f"{right} − {left}, Box height {bottom} − {top}."
    )


def _render_remap_fields(
    name: str, stored: dict, problems: dict, composite: list, added: dict | None = None
) -> dict:
    """The stored dataset's mapping, laid out the way add-dataset lays it out.

    The editor looks like the add-dataset page: the controls are the same ones —
    ``controls.column_mapping_ui`` builds both screens — and so is the shape:
    rows named down a narrow left column (Fixations · AOI · Raw gaze), one field
    per cell, each title stacked over its select.

    The widget keys stay ``remap_<dataset>_<table>_*``. They are the editor's own
    namespace, and borrowing the wizard's ``col_map_*`` keys would make an open
    wizard and an open editor overwrite each other's answers.
    """
    frames, proposals, prefixes, specs_by_table = {}, {}, {}, {}
    for table_key, _label, specs, canon in _REMAP_TABLES:
        frame = stored.get(table_key)
        if frame is None or getattr(frame, "empty", True):
            continue
        # Bookkeeping columns are never a field to map.
        frames[table_key] = drop_internal_columns(frame)
        specs_by_table[table_key] = specs
        prefixes[table_key] = f"remap_{name}_{table_key}"
        proposals[table_key] = _remap_proposed(
            (stored.get("schemas") or {}).get(table_key), frame.columns, canon
        )
        # Composite trial id: pre-seed the multiselect with the preserved
        # component columns (column_mapping_ui's ``proposed`` carries only a
        # single default). Initial-seed only — never fight later user edits.
        if composite and all(c in frame.columns for c in composite):
            trial_key = f"{prefixes[table_key]}_trial"
            if trial_key not in st.session_state:
                st.session_state[trial_key] = list(composite)

    # A table being *added* joins the same grid as the ones already
    # here, so it goes into the same dicts. Two things differ, and only two: its
    # frame is raw rather than normalized, so the proposal is a fresh
    # auto-detect and the label says "detected" rather than "currently mapped";
    # and its widget keys carry an `_add` suffix, so uploading a table, changing
    # your mind and uploading a different one cannot leave a select pointing at
    # a column the new file does not have.
    detected_labels = dict.fromkeys(frames, "currently mapped")
    added = added or {}
    for table_key, _headline, _prompt, propose in _ADDABLE_TABLES:
        raw = added.get(table_key)
        if raw is None or raw.empty:
            continue
        specs = next(sp for key, _l, sp, _c in _REMAP_TABLES if key == table_key)
        frames[table_key] = raw
        specs_by_table[table_key] = specs
        prefixes[table_key] = f"remap_{name}_{table_key}_add"
        proposals[table_key] = propose(raw)
        detected_labels[table_key] = "detected"

    def _cell(host, table_key: str, field: str) -> dict:
        return column_mapping_ui(
            frames[table_key],
            table_label="",
            state_key_prefix=prefixes[table_key],
            field_specs=specs_by_table[table_key],
            proposed=proposals[table_key],
            # What blocked the last Save is listed once per table above
            # ✅ Save changes (`render_dataset_editor_footer`); handed to every
            # one-field cell here, it would print the same warning in each of them.
            problems=None,
            container=host,
            use_expander=False,
            only_keys=[field],
            header=False,
            columns_per_row=1,
            stack_labels=True,
            # For a table already in the dataset `proposed` is its saved
            # mapping (the frame is already normalized), not a fresh
            # auto-detect — say so. A table being added *is* auto-detected.
            detected_label=detected_labels.get(table_key, "currently mapped"),
            option_labels=stored_labels.get(table_key),
            # A stored Words table holds x/y/width/height only, so its box
            # cannot be mapped as edges; a table being added still can.
            box_format_lock=STORED_BOX_FORMAT_REASON
            if table_key == "words"
            and detected_labels.get(table_key) == "currently mapped"
            else None,
        )

    # A stored table's columns are canonical; offer them by the
    # dataset's own names. A table being added is raw — its names are its own.
    stored_names = stored.get("column_names") or {}
    stored_labels = {
        table_key: ColumnNames.from_payload(stored_names.get(table_key)).option_labels(
            user_columns(frame)
        )
        for table_key, frame in frames.items()
        if detected_labels.get(table_key) == "currently mapped"
    }

    pending: dict = {table: {} for table in frames}
    seen: set = set()
    drawn: set = set()
    for label, widths, fields, extra in _edit_rows():
        live = [
            (table, field)
            for table, field in fields
            if table in frames
            and any(spec["key"] == field for spec in specs_by_table[table])
        ]
        if not live:
            continue
        # A hairline between blocks, as on the add screen — a block is one
        # table read across two lines, and without the gap the six rows read as
        # one long grid whose left-hand names label the wrong things.
        if label and drawn and extra != "measures":
            st.markdown('<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True)
        drawn.add(label or "-")
        # The line's whole grid, filled from the left, so a line with fewer
        # fields keeps its cells under the ones above it.
        row = st.columns(list(widths), gap="small", vertical_alignment="bottom")
        row[0].markdown(
            f'<div class="sps-id-row-name sps-geo-row-name">{label}</div>',
            unsafe_allow_html=True,
        )
        for cell, (table, field) in zip(row[1:], live):
            pending[table].update(_cell(cell, table, field))
            seen.add((table, field))
        if extra == "aggregate" and "words" in frames:
            if "words" not in (added or {}):
                note = box_edges_note(stored)
                if note:
                    st.caption(f"{ICONS['info']} {note}")
            _render_aggregate_toggle(name, adding="words" in (added or {}))

    # Anything the rows above do not name — a field added to the specs since, or
    # one this editor never grouped — still has to render, or applying the
    # mapping would silently drop it.
    # ONE *More* heading for the whole leftover group, with each table's own
    # line named after the table — "More" down the left of every such line
    # would read as three headings for one idea on a three-table dataset.
    leftovers = [
        (
            table,
            [
                spec["key"]
                for spec in specs_by_table[table]
                if (table, spec["key"]) not in seen
            ],
        )
        for table in frames
    ]
    leftovers = [(table, rest) for table, rest in leftovers if rest]
    if leftovers:
        st.markdown('<div class="sps-wiz-subhead">More</div>', unsafe_allow_html=True)
    for table, rest in leftovers:
        row = st.columns(_EDIT_ROW_W, gap="small", vertical_alignment="bottom")
        row[0].markdown(
            f'<div class="sps-id-row-name sps-geo-row-name">{_TABLE_LABELS[table]}</div>',
            unsafe_allow_html=True,
        )
        for index, field in enumerate(rest):
            pending[table].update(_cell(row[1 + index % 5], table, field))
    # What `_apply_remap` has to treat differently: these frames are raw, so
    # they are *normalized* rather than remapped. Recorded here rather than
    # recomputed there because the callback runs before the next render, when
    # the uploader's own state is the only other witness — and that answers a
    # subtly different question ("is a file attached") than this one ("was it
    # mapped on the screen the user just pressed Save on").
    st.session_state["_remap_added_tables"] = sorted(added)
    return pending


def _pending_canvas_estimate(
    stored: dict, pending: dict, added: dict
) -> tuple[int, int]:
    """*Estimate from my data* on ✏️ Edit dataset: the screen the data **as it
    will be saved** needs — the pending mapping over the stored frames, and a
    table being added in place of the one the dataset lacks.

    The stored frames' own ``x``/``y`` are the *old* mapping's; estimating from
    them and saving a new coordinate column beside it would store a screen that
    does not hold the data saved with it. A dataset can only add a table it has
    none of, so each table comes from exactly one place. Reuses the add
    screen's cached estimate (`wizard._c_estimate_canvas`), which projects just
    the mapped geometry columns rather than normalizing anything.
    """
    from scanpath_studio.wizard import (
        _FIX_GEOMETRY_FIELDS,
        _WORD_GEOMETRY_FIELDS,
        _c_estimate_canvas,
        _geometry_key,
    )

    frames: dict = {}
    for table in ("words", "fixations"):
        frame = added.get(table)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            frame = stored.get(table)
        if isinstance(frame, pd.DataFrame) and not frame.empty and pending.get(table):
            frames[table] = frame
    words, fixations = frames.get("words"), frames.get("fixations")
    word_schema = pending.get("words") if words is not None else None
    fix_schema = pending.get("fixations") if fixations is not None else None
    return _c_estimate_canvas(
        words,
        word_schema,
        fixations,
        fix_schema,
        (frame_fingerprint(words), frame_fingerprint(fixations)),
        (
            _geometry_key(word_schema, _WORD_GEOMETRY_FIELDS),
            _geometry_key(fix_schema, _FIX_GEOMETRY_FIELDS),
        ),
    )


#: The fields the pending-change preview spells out: schema key → the stored
#: frame's canonical column, and whether the field is an id (else a coordinate).
_PREVIEW_CHANGE_FIELDS = (
    ("participant", "participant_id", True),
    ("trial", "trial_id", True),
    ("screen_id", "screen_id", True),
    ("text_id", "text_id", True),
    ("x", "x", False),
    ("y", "y", False),
)
_PREVIEW_FIELD_LABELS = {
    "participant": "Participant ID",
    "trial": "Trial ID",
    "screen_id": "Screen ID",
    "text_id": "Text ID",
    "x": "X",
    "y": "Y",
}
#: The rows the preview reads: enough to find a few distinct values.
_PREVIEW_HEAD = 200


def _pending_field_values(
    frame: pd.DataFrame, key: str, column, is_id: bool
) -> pd.Series:
    """What ``column`` gives field ``key`` on ``frame``'s rows, as text."""
    if not column:
        if key == "participant":
            return pd.Series("(one participant)", index=frame.index)
        if key == "text_id":
            # Normalization falls back to the trial id (`from_schema`).
            return pd.Series("(the trial id)", index=frame.index)
        return pd.Series("(none)", index=frame.index)
    columns = [str(c) for c in trial_mapping_columns(column)]
    if any(c not in frame.columns for c in columns):
        return pd.Series("(none)", index=frame.index)
    if is_id:
        return trial_id_series(frame, column).astype(str)
    values = pd.to_numeric(frame[columns[0]], errors="coerce")
    return values.map(lambda v: "—" if pd.isna(v) else f"{v:,.6g}")


def pending_value_changes(
    frame: pd.DataFrame, schema: dict, *, limit: int = 3
) -> list[dict]:
    """A few rows of what a pending remap does to ``frame``'s ids and
    coordinates — ``{"field", "now", "after"}`` per changed field, the values
    paired row by row (``now[i]`` becomes ``after[i]``).

    Pure, and cheap: it reads the head of the stored frame, whose canonical
    columns are what the dataset says now, through the pending mapping's
    columns (the same composition normalization uses, `data.trial_id_series`).
    A field whose pending column is its own canonical one is unchanged and
    left out, so an untouched editor previews nothing.
    """
    head = frame.head(_PREVIEW_HEAD)
    rows: list[dict] = []
    for key, canonical, is_id in _PREVIEW_CHANGE_FIELDS:
        if key not in schema:
            continue
        pending = schema.get(key)
        parts = [str(c) for c in trial_mapping_columns(pending)] if pending else []
        present = canonical in frame.columns
        if parts == ([canonical] if present else []):
            continue
        if key == "text_id" and not parts and not present:
            continue
        now = (
            _pending_field_values(head, key, canonical, is_id)
            if present
            else _pending_field_values(head, key, None, is_id)
        )
        after = _pending_field_values(head, key, pending, is_id)
        if now.equals(after):
            # Another spelling of the same values — a composite Trial ID the
            # editor seeds as its parts, say — changes nothing.
            continue
        pairs = pd.DataFrame({"now": now, "after": after}).drop_duplicates().head(limit)
        rows.append(
            {
                "field": key,
                "now": pairs["now"].tolist(),
                "after": pairs["after"].tolist(),
            }
        )
    return rows


def _pending_keys(frame: pd.DataFrame, schema: dict, fields: tuple) -> pd.DataFrame:
    """``frame``'s id columns as the pending mapping would build them."""
    return pd.DataFrame(
        {
            key: _pending_field_values(frame, key, schema.get(key), True)
            for key in fields
        }
    )


def _current_keys(frame: pd.DataFrame, fields: tuple) -> pd.DataFrame:
    canon = {key: column for key, column, _ in _PREVIEW_CHANGE_FIELDS}
    return pd.DataFrame(
        {
            key: (
                frame[canon[key]].astype(str)
                if canon[key] in frame.columns
                else pd.Series("(one participant)", index=frame.index)
            )
            for key in fields
        }
    )


@st.cache_data(show_spinner=False, max_entries=8)
def _c_pending_census(
    _frames: dict,
    _metadata: dict,
    pending_json: str,
    fingerprints: tuple,
) -> list[dict]:
    """``pending_census``, cached on the frames' fingerprints and the mapping."""
    return pending_census(_frames, json.loads(pending_json), _metadata)


def pending_census(frames: dict, pending: dict, metadata: dict) -> list[dict]:
    """Counts before and after a pending remap — ``{"what", "now", "after"}``.

    Trials (and screens, where the data has them) as the mapping would split
    them, and whether what hangs off those ids still finds them: the word boxes
    the fixations' trials point at, and an attached participant or trial table.
    Reads every row, which is why the editor runs it only on request.
    """
    rows: list[dict] = []
    fix = frames.get("fixations")
    words = frames.get("words")
    reading = fix if isinstance(fix, pd.DataFrame) and not fix.empty else words
    if not isinstance(reading, pd.DataFrame) or reading.empty:
        return rows
    table = "fixations" if reading is fix else "words"
    schema = pending.get(table) or {}
    trial_fields = ("participant", "trial")
    now = _current_keys(reading, trial_fields)
    after = _pending_keys(reading, schema, trial_fields)
    rows.append(
        {
            "what": "Trials",
            "now": len(now.drop_duplicates()),
            "after": len(after.drop_duplicates()),
        }
    )
    if "screen_id" in reading.columns or schema.get("screen_id"):
        screen_fields = (*trial_fields, "screen_id")
        rows.append(
            {
                "what": "Screens",
                "now": len(_current_keys(reading, screen_fields).drop_duplicates())
                if "screen_id" in reading.columns
                else len(now.drop_duplicates()),
                "after": len(
                    _pending_keys(reading, schema, screen_fields).drop_duplicates()
                ),
            }
        )
    if (
        table == "fixations"
        and isinstance(words, pd.DataFrame)
        and not words.empty
        and "trial_id" in words.columns
    ):
        word_schema = pending.get("words") or {}
        trials_now = set(now["trial"])
        boxes_now = set(words["trial_id"].astype(str))
        trials_after = set(after["trial"])
        boxes_after = (
            set(_pending_keys(words, word_schema, ("trial",))["trial"])
            if word_schema
            else boxes_now
        )
        rows.append(
            {
                "what": "Trials with word boxes",
                "now": f"{len(trials_now & boxes_now)} of {len(trials_now)}",
                "after": f"{len(trials_after & boxes_after)} of {len(trials_after)}",
            }
        )
    readers = metadata.get("participants")
    if isinstance(readers, pd.DataFrame) and "participant_id" in readers.columns:
        known = set(readers["participant_id"].astype(str))
        before, later = set(now["participant"]), set(after["participant"])
        rows.append(
            {
                "what": "Participants in the participant table",
                "now": f"{len(before & known)} of {len(before)}",
                "after": f"{len(later & known)} of {len(later)}",
            }
        )
    trials = metadata.get("trials")
    if isinstance(trials, pd.DataFrame) and "trial_id" in trials.columns:
        by_reader = "participant_id" in trials.columns
        cols = ["participant", "trial"] if by_reader else ["trial"]
        table_cols = ["participant_id", "trial_id"] if by_reader else ["trial_id"]
        known = set(map(tuple, trials[table_cols].astype(str).to_numpy()))
        before = set(map(tuple, now[cols].to_numpy()))
        later = set(map(tuple, after[cols].to_numpy()))
        rows.append(
            {
                "what": "Trials in the trial table",
                "now": f"{len(before & known)} of {len(before)}",
                "after": f"{len(later & known)} of {len(later)}",
            }
        )
    return rows


#: The editor asked for the pending-change census (a `_remap_*` key, so it ends
#: with the edit).
_PREVIEW_CENSUS_KEY = "_remap_preview_census"


def remap_reading_changes(frames, pending, annotations) -> pd.DataFrame:
    """Distinct current and proposed reading keys, including merges, splits and unmatched notes."""
    transitions = []
    for kind, frame in frames.items():
        if (
            frame is None
            or frame.empty
            or not {"participant_id", "trial_id"} <= set(frame)
        ):
            continue
        fields = ("participant", "trial")
        old = _current_keys(frame, fields).reset_index(drop=True)
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            **(pending.get(kind) or {}),
        }
        new = _pending_keys(frame, schema, fields).reset_index(drop=True)
        transitions.append(
            pd.concat(
                [old.add_prefix("old_"), new.add_prefix("new_")], axis=1
            ).drop_duplicates()
        )
    if not transitions:
        return pd.DataFrame()
    pairs = pd.concat(transitions, ignore_index=True).drop_duplicates()
    old_cols, new_cols = (
        ["old_participant", "old_trial"],
        ["new_participant", "new_trial"],
    )
    outs = pairs.groupby(old_cols).size()
    ins = pairs.groupby(new_cols).size()
    remaining = set(ins.index)
    notes = {}
    for key, entry in annotations.items():
        if key[:2] not in remaining:
            label = "Whole trial" if len(key) == 2 else f"Screen {key[2]}"
            notes.setdefault(key[:2], []).append(
                f"{label} · {entry.get('note') or ', '.join(entry.get('tags', [])) or 'Favorite'}"
            )
    changes = []
    for p, t, new_p, new_t in pairs.itertuples(index=False, name=None):
        old, new = (p, t), (new_p, new_t)
        split, merged = outs[old] > 1, ins[new] > 1
        if old != new or split or merged:
            kind = (
                "Split and merged"
                if split and merged
                else "Split"
                if split
                else "Merged"
                if merged
                else "Renamed"
            )
            changes.append([p, t, new_p, new_t, kind, "\n".join(notes.get(old, []))])
    return pd.DataFrame(
        changes,
        columns=[*old_cols, *new_cols, "change", "annotations losing their reading"],
    )


def _render_pending_change_preview(name: str, stored: dict, pending: dict) -> None:
    """What ✅ Save changes would do to the ids and coordinates — before it does.

    A changed pick is otherwise only a different column name in its select,
    and its effect (readings merged by a coarser Trial ID, a metadata table
    that no longer finds its readers) shows after the save. Shown only once a
    stored table's id or coordinate mapping differs from what is saved: a few
    rows of now → after (`pending_value_changes`), and on request the counts and
    joins (`pending_census`), which read every row.
    """
    names_by_table = stored.get("column_names") or {}
    changes = []
    for table in ("fixations", "words", "raw_gaze"):
        frame = stored.get(table)
        schema = pending.get(table)
        if not isinstance(frame, pd.DataFrame) or frame.empty or not schema:
            continue
        for row in pending_value_changes(frame, schema):
            changes.append((table, row))
    if not changes:
        st.session_state.pop(_PREVIEW_CENSUS_KEY, None)
        return
    box = st.container(border=True, key=f"remap_preview_{name}")
    box.markdown(f"**{ICONS['preview']} What Save changes will do**")
    lines = []
    for table, row in changes:
        names = ColumnNames.from_payload(names_by_table.get(table))
        column = (pending.get(table) or {}).get(row["field"])
        source = (
            " + ".join(names.display(c) for c in trial_mapping_columns(column))
            if column
            else "made by the app"
        )
        pairs = ", ".join(
            f"`{a}` → `{b}`" if a != b else f"`{a}`"
            for a, b in zip(row["now"], row["after"], strict=True)
        )
        lines.append(
            f"- **{_TABLE_LABELS[table]} · {_PREVIEW_FIELD_LABELS[row['field']]}** "
            f"from {source}: {pairs}"
        )
    box.markdown("\n".join(lines))
    signature = _editor_signature(pending, {})
    if st.session_state.get(_PREVIEW_CENSUS_KEY) != signature:
        box.button(
            f"{ICONS['search']} Count trials and check joins",
            key=f"remap_preview_census_{name}",
            on_click=lambda: st.session_state.__setitem__(
                _PREVIEW_CENSUS_KEY, signature
            ),
            help="Count the trials and screens this mapping makes, and check "
            "that the word boxes and any attached participant or trial table "
            "still find them. Reads every row.",
        )
        return
    from scanpath_studio import metadata as md

    frames = {
        table: stored.get(table)
        for table in ("words", "fixations")
        if isinstance(stored.get(table), pd.DataFrame)
    }
    participant_table = st.session_state.get(md.SESSION_KEY)
    trial_table = st.session_state.get(md.TRIAL_SESSION_KEY)
    metadata = {
        "participants": getattr(participant_table, "frame", None),
        "trials": getattr(trial_table, "frame", None),
    }
    census = _c_pending_census(
        frames,
        metadata,
        json.dumps(pending, sort_keys=True, default=str),
        (
            *(frame_fingerprint(f) for f in frames.values()),
            *(
                frame_fingerprint(f) if isinstance(f, pd.DataFrame) else None
                for f in metadata.values()
            ),
        ),
    )
    box.dataframe(
        pd.DataFrame(
            [
                {"": r["what"], "Now": str(r["now"]), "After saving": str(r["after"])}
                for r in census
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if any(r["what"] == "Trials" and int(r["after"]) < int(r["now"]) for r in census):
        box.warning(
            "This mapping makes fewer trials, so some separate readings would be "
            "merged into one scanpath.",
            icon=ICONS["warning"],
        )
    from .annotations import store_for

    affected = remap_reading_changes(
        {**frames, "raw_gaze": stored.get("raw_gaze")},
        pending,
        store_for(st.session_state, name),
    )
    if not affected.empty:
        box.caption(
            "Reading IDs after saving this mapping. Existing annotations stay under their original keys."
        )
        box.dataframe(affected, hide_index=True)


#: ✏️ Edit dataset's own widget namespace — ``remap_<dataset>_…``: every
#: mapping select, coordinate-format radio, aggregation toggle and table
#: uploader on the screen. Its mapping widgets persist across runs
#: (``persist_state="session"``, so a draft survives a visit to another view),
#: which is exactly why a finished edit has to clear them.
EDITOR_WIDGET_PREFIX = "remap_"


def discard_editor_widgets() -> None:
    """Forget every answer the editor's widgets hold.

    Run when an edit ends (✕ Cancel, ✅ Save changes) and when a fresh one
    opens: a mapping widget seeds itself from the saved dataset only when its
    key is absent, so a key left behind by a cancelled edit would reopen the
    editor on the abandoned pick — and the dirty baseline, captured from those
    picks, would then call it unchanged. The field-touch marks and the
    column-universe markers that go with those keys go too, and so does the
    Recording setup form's ``edit_*_setup_*`` keys. The add screen's
    ``col_map_*`` keys are a different namespace and are not touched.
    """
    session = st.session_state
    marker = f"_mapped_columns_{EDITOR_WIDGET_PREFIX}"
    for key in [
        k
        for k in list(session)
        if isinstance(k, str)
        and (
            k.startswith((EDITOR_WIDGET_PREFIX, marker))
            # The Recording setup form (`wizard._wizard_setup_step` under
            # ``edit_<dataset>`` / ``edit_src_<token>``) persists its widgets
            # too and seeds them with `setdefault`, so a cancelled setup edit
            # would come back the same way.
            or (k.startswith("edit_") and "_setup_" in k)
        )
    ]:
        del session[key]
    touched = session.get(TOUCHED_FIELDS_KEY)
    if touched:
        session[TOUCHED_FIELDS_KEY] = {
            key for key in touched if not str(key).startswith(EDITOR_WIDGET_PREFIX)
        }


def _render_remap_editor(
    name: str, stored: dict, uploads_host=None, setup_host=None
) -> None:
    """Editable column-mapping form for a stored dataset (the surviving columns).

    Renders one ``column_mapping_ui`` per present table seeded with the current
    mapping, a note listing columns dropped at import, and an Apply button. The
    widget keys are namespaced by dataset name so switching datasets never feeds
    a stale column to a selectbox (which would raise).

    The *Column mapping* heading is the page section's, rendered by
    ``app.main`` above whichever of the three modes applies — this function does
    not title itself. **Recording setup** renders into ``setup_host``, the
    editor's own numbered part, so this function draws mapping and nothing
    else. Without a host the setup renders here, under a ``##### `` heading
    after a rule."""
    if _REMAP_BASELINE_KEY not in st.session_state:
        # A fresh edit (the baseline is captured at the end of its first
        # render): start every field from the saved dataset, whatever an
        # earlier edit left in the widgets.
        discard_editor_widgets()
    # The dataset table's ✏️ Edit both opened this dataset and sent the
    # user here, so say so — otherwise the page has silently changed under them
    # and the mapping form is several screens down.
    if st.session_state.pop(FOCUS_MAPPING_KEY, None) == name:
        st.info(
            f"Editing **{md_literal(_dataset_label(name))}**. Its mapping and saved tables are below."
        )
    if is_multipleye_entry(stored):
        st.caption(
            "These tables were created from a MultiplEYE session set. Changes here "
            "apply within the app. Code copied from Share → Code reloads the original"
            " session set."
        )
    else:
        st.caption(
            "Choose which columns contain the IDs, positions and other values the app"
            " needs. Only columns kept during import are available. To use a column "
            "that is missing, remove the dataset and add it again from its files."
        )
    # The same wide option lists the add-dataset screen gets — this is
    # the same mapping, in the same shape.
    st.markdown(mapping_menu_css(), unsafe_allow_html=True)
    problems = st.session_state.get("_remap_problems") or {}
    composite = list(stored.get("composite_trial_columns") or [])
    # Before the grid, because Streamlit's creation order is screen order and
    # a table's fields cannot render above the file they map. It gets a slot of
    # its own at the **top of the page** — the add screen puts every upload
    # above the mapping, and "add the table this dataset is missing" is the
    # same kind of decision. Falls back to here when no slot is passed.
    added = _render_missing_table_uploads(
        name, stored, host=uploads_host if uploads_host is not None else st
    )
    pending: dict = _render_remap_fields(name, stored, problems, composite, added)
    st.session_state["_remap_pending_schemas"] = pending
    _render_pending_change_preview(name, stored, pending)

    # The add and edit flows share the same three-column Recording setup
    # renderer. Editing starts from the saved values and publishes only when
    # Save changes runs, so unfinished edits never leak into the plot.
    from scanpath_studio.experimental_setup import SetupSnapshot
    from scanpath_studio.wizard import _wizard_setup_step

    setup_box = st if setup_host is None else setup_host
    if setup_host is None:
        st.divider()
        st.markdown("##### Recording setup")
        st.caption(
            "Screen resolution, monitor dimensions, and the size and font of the "
            "reading text."
        )
    initial_setup = SetupSnapshot.from_dict(
        stored.get("setup") or {}, fallback=SetupSnapshot()
    )
    word_frame = stored.get("words")
    fixation_frame = stored.get("fixations")
    # The add screen offers *Scale to the word boxes* whenever
    # there is a Words table at all (`has_boxes=has_words`), not only when every
    # box column is mapped. This screen has to ask the same thing of **either**
    # source of a Words table: the one already stored, or one sitting in the
    # uploader above and not yet saved — added != {} the moment a table is
    # attached there, well before ✅ Save changes runs, and the option
    # disappearing until after the save would be backwards: it is exactly the
    # setup question you want answered *before* committing to a new table.
    has_boxes = bool(
        (isinstance(word_frame, pd.DataFrame) and not word_frame.empty)
        or (added or {}).get("words") is not None
    )
    setup = _wizard_setup_step(
        setup_box,
        word_frame if isinstance(word_frame, pd.DataFrame) else pd.DataFrame(),
        fixation_frame if isinstance(fixation_frame, pd.DataFrame) else pd.DataFrame(),
        has_boxes,
        key_prefix=f"edit_{name}",
        initial=initial_setup,
        publish=False,
        estimate=partial(_pending_canvas_estimate, stored, pending, added or {}),
    )
    st.session_state["_remap_pending_setup"] = setup.to_dict()
    # Is there anything to lose by leaving? A table uploaded here is
    # unsaved by definition; otherwise it is whether the mapping or the setup
    # reads differently from the moment the editor opened. Comparing against the
    # *opening* state rather than against the stored entry is what makes an
    # untouched editor read as clean: the seeds the pickers start from are not
    # always spelled the way the saved schema is, and the question ✕ Cancel asks
    # is "did you change anything", not "does this differ from disk".
    signature = _editor_signature(pending, setup.to_dict())
    baseline = st.session_state.get(_REMAP_BASELINE_KEY)
    if baseline is None:
        st.session_state[_REMAP_BASELINE_KEY] = baseline = signature
    renamed = str(st.session_state.get(EDITOR_PENDING_NAME_KEY) or "").strip()
    st.session_state[_REMAP_DIRTY_KEY] = (
        bool(added)
        or signature != baseline
        or (bool(renamed) and renamed != _dataset_label(name))
    )

    dropped = stored.get("dropped_columns") or {}
    flat = sorted({c for cols in dropped.values() for c in (cols or [])})
    if flat:
        # A popover keeps the (often long) dropped-column list out of the way —
        # zero footprint until opened, then a height-capped, searchable table.
        with st.popover(
            f"{ICONS['warning']} {plural(len(flat), 'column')} dropped at import"
        ):
            st.caption(
                "These columns were not kept when the dataset was added. Add the "
                "dataset again to keep them."
            )
            st.dataframe(
                pd.DataFrame({"Dropped column": flat}),
                hide_index=True,
                width="stretch",
                height=320,
            )
    # ✅ Save changes is not rendered here: it belongs at the foot of the
    # whole screen the way ✅ Add dataset does — this section is the first of
    # six, so a commit button at its end would sit in the middle of the page.
    # `render_dataset_editor_footer` draws it into a slot `app.main` reserves
    # last.


#: What the editor looked like when it opened, and whether it looks
#: different now. The baseline is captured on the editor's first render (every
#: `_remap_*` key is cleared when it opens or closes, so an absent baseline
#: *means* "just opened") and compared on every render after.
_REMAP_BASELINE_KEY = "_remap_baseline"
_REMAP_DIRTY_KEY = "_remap_dirty"
#: ✏️ Edit dataset's **Name** field, swept with the rest of the edit on
#: Cancel and on ✅ Save changes.
EDITOR_NAME_FIELD_KEY = "dataset_editor_name"
#: …and the name it holds for an upload, until ✅ Save changes applies it.
EDITOR_PENDING_NAME_KEY = "_remap_pending_name"


def _editor_signature(pending: dict, setup_payload: dict) -> str:
    """A stable, comparable rendering of everything ✅ Save changes would save.

    JSON with sorted keys rather than the dicts themselves: a mapping value may
    be a string or a list (a composite trial id), and Streamlit hands those back
    as new objects every run, so identity comparison is useless and `==` on
    nested structures is fragile about list-vs-tuple.
    """
    return json.dumps(
        {"schemas": pending, "setup": setup_payload}, sort_keys=True, default=str
    )


def dataset_editor_is_dirty() -> bool:
    """Whether the open editor holds anything ✅ Save changes has not saved.

    Read by ✕ Cancel, which asks for confirmation only when there is something
    to lose. **Biased towards dirty**: an unknown state (no baseline yet, a
    signature that cannot be built) counts as changed, because a wrong "clean"
    discards work in silence while a wrong "dirty" costs one extra click.
    """
    return bool(st.session_state.get(_REMAP_DIRTY_KEY, True)) or bool(
        st.session_state.get(_BUILTIN_SETUP_DIRTY_KEY)
    )


#: A built-in or public dataset's **Recording setup** on ✏️ Edit dataset — the
#: same form an upload gets, saved as the user's own setup for that dataset
#: (`app.save_dataset_setup_override`) rather than over the corpus' declared
#: one. ``_remap_*`` keys, so ✕ Cancel and ✅ Save changes sweep them with the
#: rest of the edit: which dataset's form is open (its widgets are forgotten
#: when a new edit opens, so a cancelled answer never comes back), what it
#: holds, what it held when it opened, a pending *Reset to the corpus's
#: setup*, and whether it differs.
_BUILTIN_SETUP_OPEN_KEY = "_remap_builtin_setup_open"
_BUILTIN_SETUP_PENDING_KEY = "_remap_builtin_setup_pending"
_BUILTIN_SETUP_BASELINE_KEY = "_remap_builtin_setup_baseline"
_BUILTIN_SETUP_RESET_KEY = "_remap_builtin_setup_reset"
_BUILTIN_SETUP_DIRTY_KEY = "_remap_builtin_setup_dirty"


def _builtin_setup_prefix(token: str) -> str:
    """The form's widget-key prefix — not ``edit_<name>``, an upload's."""
    return f"edit_src_{token}"


def _forget_builtin_setup_widgets(token: str) -> None:
    prefix = f"{_builtin_setup_prefix(token)}_setup_"
    for key in [k for k in st.session_state if str(k).startswith(prefix)]:
        st.session_state.pop(key, None)


def _reset_builtin_setup(token: str) -> None:
    """*Reset to the corpus's setup*: redraw the form at the corpus' own values.
    Nothing is dropped until ✅ Save changes (`commit_builtin_setup`)."""
    _forget_builtin_setup_widgets(token)
    st.session_state[_BUILTIN_SETUP_RESET_KEY] = token
    st.session_state.pop(_BUILTIN_SETUP_BASELINE_KEY, None)


def _setup_groups_differing(a, b) -> list[str]:
    """The setup groups whose values or provenance differ between two
    snapshots, by their on-screen names."""
    fields = {
        "screen": ("canvas_width", "canvas_height"),
        "geometry": ("monitor_width_mm", "viewing_distance_mm"),
        "text": (
            "base_font_size",
            "font_family",
            "line_spacing",
            "scale_text_to_boxes",
        ),
    }
    from scanpath_studio.experimental_setup import SETUP_GROUP_LABELS

    return [
        SETUP_GROUP_LABELS[group]
        for group, names in fields.items()
        if a.provenance[group] != b.provenance[group]
        or any(getattr(a, n) != getattr(b, n) for n in names)
    ]


def render_builtin_setup_editor(
    token: str,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    host,
) -> None:
    """Recording setup for a built-in or public dataset, editable.

    The upload's form (`wizard._wizard_setup_step`), started from the setup
    this dataset has now — the user's own, if they saved one, else what the
    corpus declares. ✅ Save changes keeps a changed form as this dataset's own
    setup (`commit_builtin_setup`); ✕ Cancel discards it. The corpus' declared
    values are never rewritten, so *Reset to the corpus's setup* can always go
    back.
    """
    from scanpath_studio.app import (
        cached_canvas_size,
        dataset_setup_override,
        source_setup_snapshot,
    )
    from scanpath_studio.wizard import _wizard_setup_step

    if st.session_state.get(_BUILTIN_SETUP_OPEN_KEY) != token:
        # A new edit: whatever an earlier, cancelled one typed is not this one.
        _forget_builtin_setup_widgets(token)
        st.session_state.pop(_BUILTIN_SETUP_BASELINE_KEY, None)
        st.session_state.pop(_BUILTIN_SETUP_RESET_KEY, None)
        st.session_state[_BUILTIN_SETUP_OPEN_KEY] = token
    resetting = st.session_state.get(_BUILTIN_SETUP_RESET_KEY) == token
    words = words if isinstance(words, pd.DataFrame) else pd.DataFrame()
    fixations = fixations if isinstance(fixations, pd.DataFrame) else pd.DataFrame()
    source = source_setup_snapshot(token, words, fixations)
    override = None if resetting else dataset_setup_override(token)
    note, action = host.columns([0.78, 0.22], vertical_alignment="center")
    if override is not None:
        changed = _setup_groups_differing(override, source)
        note.caption(
            f"{ICONS['edit']} **Your own setup** for this dataset"
            + (f". You changed: {', '.join(changed)}" if changed else "")
            + ". The corpus's own setup is kept; reset to go back to it."
        )
        action.button(
            f"{ICONS['reset']} Reset to the corpus's setup",
            key=f"{_builtin_setup_prefix(token)}_reset",
            on_click=_reset_builtin_setup,
            args=(token,),
            width="stretch",
            help="Show the setup this corpus declares. Nothing changes until you save.",
        )
    elif resetting:
        note.caption(
            "Showing the setup this corpus declares. Click **Save changes** to "
            "drop your own."
        )
    else:
        note.caption(
            "The setup this corpus declares. Change anything to save your own "
            "for this dataset; you can reset to the corpus's setup later."
        )
    setup = _wizard_setup_step(
        host,
        words,
        fixations,
        not words.empty,
        key_prefix=_builtin_setup_prefix(token),
        initial=override or source,
        publish=False,
        estimate=partial(cached_canvas_size, words, fixations),
    )
    payload = setup.to_dict()
    st.session_state[_BUILTIN_SETUP_PENDING_KEY] = {"token": token, "setup": payload}
    signature = _editor_signature({}, payload)
    baseline = st.session_state.get(_BUILTIN_SETUP_BASELINE_KEY)
    if baseline is None:
        st.session_state[_BUILTIN_SETUP_BASELINE_KEY] = baseline = signature
    st.session_state[_BUILTIN_SETUP_DIRTY_KEY] = resetting or signature != baseline


def commit_builtin_setup() -> None:
    """✅ Save changes' half for a built-in dataset's Recording setup.

    A form the user changed becomes the dataset's own setup; a *Reset to source
    setup* left as it was drops it; an untouched form changes nothing — saving
    the mapping must not turn the corpus' declared setup into an override.
    """
    from scanpath_studio.app import save_dataset_setup_override

    pending = st.session_state.get(_BUILTIN_SETUP_PENDING_KEY)
    if not isinstance(pending, dict) or not pending.get("token"):
        return
    token, payload = str(pending["token"]), pending.get("setup")
    changed = _editor_signature({}, payload) != st.session_state.get(
        _BUILTIN_SETUP_BASELINE_KEY
    )
    if changed and isinstance(payload, dict):
        save_dataset_setup_override(token, payload)
    elif st.session_state.get(_BUILTIN_SETUP_RESET_KEY) == token:
        save_dataset_setup_override(token, None)


#: The editor's own widget namespace → the add screen's. The two screens run the
#: same ``controls.column_mapping_ui`` over the same field specs, so a key is
#: ``<prefix>_<field>`` on both sides and the whole difference is the prefix —
#: which is what lets ⬇️ Download setup file write the *add* screen's file from the *edit*
#: screen's state. The namespaces are deliberately separate (see
#: ``_render_remap_fields``): an open wizard and an open editor must not
#: overwrite each other's answers.
_EDITOR_TO_WIZARD_PREFIX = {
    "words": "col_map_words",
    "fixations": "col_map_fix",
    "raw_gaze": "col_map_raw_gaze",
}

#: Scaffolding *substrings* under those prefixes that are not part of the
#: mapping: the per-cell confirm state (`<field>_cell_confirm`, so this cannot be
#: a suffix test), the uploader itself, and the stashed file header.
_EDITOR_KEY_NOISE = ("_cell", "_upload", "_header")


#: Each table's name in a setup-file note.
_SETUP_TABLE_NAMES = {
    "words": "Words table",
    "fixations": "Fixations table",
    "raw_gaze": "Raw gaze table",
}
_BOX_EDGE_KEYS = ("left", "right", "top", "bottom")
_BOX_ORIGIN_KEYS = ("x", "y", "width", "height")


def _setup_file_mapping(
    pending: dict,
    stored: dict,
    *,
    added=(),
    box_formats: dict | None = None,
) -> tuple[dict, list[str]]:
    """The editor's pending mapping as the add screen's ``col_map_*`` keys, in
    the **dataset's own files'** column names, plus what the file cannot carry.

    A table already in the dataset is mapped onto the stored frame's canonical
    columns (``x``, ``duration_ms``); restated through its column-name map
    (`column_names.source_schema`) each becomes the file column it was read
    from — a seconds column by its own name (the add screen converts it again),
    a composite id as its parts, a box stored as x/y/width/height but read from
    edges as those edges. A column the app *made* (a text id from the trial id)
    is written unmapped, so the add screen makes it again. A field that cannot
    be traced back is left out — the add screen then detects it — and named in
    the notes. A table being *added* is raw, so its mapping already speaks the
    file's names; only its widget namespace (``…_add``) differs, and the file
    uses the add screen's.
    """
    from scanpath_studio.controls import (
        _HIDDEN_MAPPING_KEYS,
        BOX_FORMAT_EDGES,
        BOX_FORMAT_ORIGIN,
    )

    box_formats = box_formats or {}
    names_by_table = stored.get("column_names") or {}
    recipe = stored.get("source_recipe") or {}
    derived = {str(c) for c in recipe.get("derived") or ()}
    specs = {table: spec for table, _label, spec, _canon in _REMAP_TABLES}
    mapping: dict = {}
    notes: list[str] = []
    for table, wizard_prefix in _EDITOR_TO_WIZARD_PREFIX.items():
        schema = pending.get(table)
        if not isinstance(schema, dict):
            continue
        label = _SETUP_TABLE_NAMES[table]
        if table in added:
            source: dict = dict(schema)
        else:
            names = ColumnNames.from_payload(names_by_table.get(table))
            if not names.entries:
                notes.append(
                    f"{label}: this dataset was added before the app recorded "
                    "your files' column names, so the setup file uses the app's "
                    "field names. Check them after restoring."
                )
            restated, unresolved = source_schema(schema, names)
            source = dict(restated or {})
            for key in unresolved:
                source.pop(key, None)
            if unresolved:
                shown = {s["key"]: s.get("label", s["key"]) for s in specs[table]}
                one = len(unresolved) == 1
                notes.append(
                    f"{label}: {', '.join(shown.get(k, k) for k in unresolved)} "
                    f"could not be matched to a column in your files and "
                    f"{'is' if one else 'are'} left out. Map "
                    f"{'it' if one else 'them'} after restoring."
                )
        multi = {spec["key"] for spec in specs[table] if spec.get("multi")}
        if table == "words":
            if any(source.get(k) for k in _BOX_EDGE_KEYS):
                box = BOX_FORMAT_EDGES
            elif any(source.get(k) for k in _BOX_ORIGIN_KEYS):
                box = BOX_FORMAT_ORIGIN
            else:
                box = box_formats.get(table)
            other = _BOX_ORIGIN_KEYS if box == BOX_FORMAT_EDGES else _BOX_EDGE_KEYS
            for key in other:
                source.pop(key, None)
            if box:
                mapping[f"{wizard_prefix}_box_format"] = box
        from_file_names: set = set()
        for key, value in source.items():
            if key in _HIDDEN_MAPPING_KEYS:
                continue  # never a widget: the add screen detects them
            if isinstance(value, (list, tuple)):
                value = [str(item) for item in value]
            elif value is not None:
                value = str(value)
            if key in multi and isinstance(value, str):
                value = [value]
            mapping[f"{wizard_prefix}_{key}"] = value
            for column in value if isinstance(value, list) else [value]:
                if column in derived:
                    from_file_names.add(column)
        if from_file_names:
            notes.append(
                f"{label}: {', '.join(sorted(from_file_names))} came from "
                "*Derive columns from text*. Set it up again after restoring."
            )
    return mapping, notes


def _editor_setup_config(name: str) -> dict:
    """The open editor's mapping + recording setup, in the add screen's setup
    format (``wizard._wizard_setup_config``).

    So ⬇️ Download setup file means the same thing on both screens, and a file saved from
    either is restored by the same *Start from → A setup file* uploader — over the
    **original files**, which is why the mapping is written in their column
    names rather than the stored frame's (`_setup_file_mapping`). What a
    restore cannot reproduce is listed under ``column_mapping_notes``, and the
    footer says it beside the button.
    """
    from datetime import datetime

    from scanpath_studio import __version__
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

    stored = (st.session_state.get("_datasets") or {}).get(name) or {}
    added = set(st.session_state.get("_remap_added_tables") or ())
    mapping, notes = _setup_file_mapping(
        st.session_state.get("_remap_pending_schemas") or {},
        stored,
        added=added,
        box_formats={
            table: st.session_state.get(f"remap_{name}_{table}_add_box_format")
            for table in added
        },
    )
    setup = st.session_state.get("_remap_pending_setup")
    # The steps the dataset's files went through, so *Start from → A setup
    # file* runs them again; a Words table being added goes by its own switch.
    steps = [
        step
        for step in (stored.get("source_recipe") or {}).get("steps") or ()
        if not ("words" in added and step == "aggregate_char_boxes")
    ]
    if "words" in added and st.session_state.get(aggregate_key(name)):
        steps.append("aggregate_char_boxes")
    return {
        "schema": PLOT_CONFIG_SCHEMA,
        "app": {"name": "Scanpath Studio", "version": __version__},
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": _dataset_label(name),
        "column_mapping": mapping,
        "column_mapping_notes": notes,
        "experimental_setup": dict(setup) if isinstance(setup, dict) else None,
        "steps": list(dict.fromkeys(steps)),
    }


def render_dataset_editor_footer(host) -> None:
    """⬇️ Download setup file · ✅ Save changes, at the foot of the ✏️ Edit dataset screen.

    The add screen's footer, for the screen that edits what it created: one
    line, matched widths, the same heavy divider above it, and the same two
    things you do with
    a finished mapping — take it away as JSON, or commit it. See
    ``wizard._wizard_footer``, whose widths this borrows so the two screens'
    last rows line up.

    ✅ Save changes is the one commit, and it is the last thing on the page,
    under everything it commits.

    It also prints what blocked the last attempt. `_apply_remap` records those
    in ``_remap_problems``, which also tint the offending selects; a mapping
    the pipeline *rejected* (rather than one with an empty required field) has
    no cell to tint, so without this line pressing Save would do nothing and
    say nothing.
    """
    import json

    from scanpath_studio.wizard import _FOOTER_ROW_W

    active = _active_stored_dataset()
    if active is None:
        return
    name, _stored = active
    problems = st.session_state.get("_remap_problems") or {}
    box = host.container()
    divider_host = box.container(key="wizard_footer_divider_edit")
    divider_host.divider()
    for table_key, messages in problems.items():
        label = _TABLE_LABELS.get(table_key, table_key)
        for message in messages:
            box.error(f"**{label}** — {message}", icon=ICONS["error"])
    row = box.container(key="wizard_footer_row_edit")
    save_col, apply_col, _rest = row.columns(
        _FOOTER_ROW_W, gap="small", vertical_alignment="center"
    )
    config = _editor_setup_config(name)
    if is_multipleye_entry(_stored):
        # A session set has no mapping of the user's files to save: whoever
        # loads it adds it again as a MultiplEYE session set.
        apply_col = save_col
    else:
        save_col.download_button(
            f"{ICONS['download']} Download setup file",
            data=json.dumps(config, indent=2),
            file_name="scanpath_studio_setup.json",
            mime="application/json",
            key=f"remap_setup_download_{name}",
            width="stretch",
            help="Save this dataset's column mapping and recording setup to "
            "reuse on similar data, or to send with the files. Whoever loads "
            "them can restore it with *Start from → A setup file* instead of "
            "mapping by hand.",
        )
    apply_col.button(
        # The add-dataset screen's ✅ Add dataset, for the screen that
        # edits one — same shape, same place, same filled blue.
        f"{ICONS['confirm']} Save changes",
        type="primary",
        key=f"remap_apply_{name}",
        on_click=_apply_remap,
        width="stretch",
        help="Save every change on this screen and reload the dataset with them.",
    )
    # What a restore over the original files will not reproduce on its own —
    # said before the file is sent, not discovered by whoever restores it.
    if config["column_mapping_notes"] and not is_multipleye_entry(_stored):
        box.caption(
            "**Some of the saved setup needs fixing after restoring.** "
            + " ".join(config["column_mapping_notes"])
        )


def _request_full_identity_scan() -> None:
    """Ask the trial-identity check for its census instead of its sample, from
    the next run.

    A callback rather than an inline handler: ``app.main`` reads the flag near
    the top of the run, well before this section renders, so setting it inline
    would leave the sampled report on screen for one more rerun.
    """
    st.session_state[TRIAL_IDENTITY_FULL_KEY] = True


def render_trial_identity_section() -> None:
    """The evidence behind "this trial id may cover several readings".

    Reads the report ``app.main`` computed on the **unfiltered** frames, so the
    verdict describes the dataset's mapping rather than whatever the current
    filters left. Renders an all-clear as well as a warning — "we checked and
    it's fine" is the more common answer and is worth stating, or the section
    reads as an error box that only appears when something is wrong.

    It is a **section** of the Data page (``app.main`` draws the heading into
    the slot below the column mapping): the verdict answers whether the Trial
    ID mapping is sufficient, and the fix it names is an edit to that mapping,
    so it sits beside the mapping rather than under the counts.
    """
    report = st.session_state.get("_trial_identity_report") or {}
    total = int(report.get("trials") or 0)
    if not total:
        st.caption("No trials loaded, so there is nothing to check.")
        return
    # On a large corpus the check screens a deterministic sample, so
    # every figure below is "out of `total`" — say so, and offer the census.
    sampled_from = report.get("sampled_from")
    scope = (
        plural(total, "trial") if not sampled_from else plural(total, "sampled trial")
    )
    affected = int(report.get("affected_trials") or 0)
    if not affected:
        st.success(
            f"Checked {scope}. No signs of merged readings were found.",
            icon=ICONS["success"],
        )
    else:
        st.warning(
            f"**{affected} of {scope} look like more than one reading.** "
            "When the Trial ID doesn't fully identify a reading, several readings "
            "are joined into one scanpath, which looks like an ordinary scanpath "
            "with many regressions. Add a column that tells the readings apart "
            "(a session or block id) to the Trial ID mapping on "
            f"{ICONS['edit']} Edit dataset.",
            icon=ICONS["warning"],
        )
    if sampled_from:
        st.caption(
            f"Checked {total:,} of this dataset's {int(sampled_from):,} trials. "
            "Choose **Check every trial** to check the whole dataset and get "
            "a complete count."
        )
        st.button(
            f"{ICONS['search']} Check every trial",
            key="trial_identity_full_scan_btn",
            on_click=_request_full_identity_scan,
            help=f"Run the check on all {int(sampled_from):,} trials. It is "
            "slower, and the result is kept for the rest of this session.",
        )
    rows = [
        {
            "Check": "Duplicated word rows",
            "Count": int(report.get("duplicate_word_rows") or 0),
            "What it means": "A word box appears more than once in one trial. "
            "Each word should have one row per trial.",
        },
        {
            "Check": "Trials with a repeated fixation id",
            "Count": int(report.get("repeated_fixation_id_trials") or 0),
            "What it means": "Two fixations in one trial share an id. This "
            "check needs no word boxes.",
        },
        {
            "Check": "Trials whose clock runs backwards",
            "Count": int(report.get("backwards_clock_trials") or 0),
            "What it means": "The timestamp jumps back mid-trial, which usually "
            "means a second recording started.",
        },
    ]
    # The verdict above is the answer and stays open; the three signals
    # behind it are evidence, and open by default only when they are the
    # explanation for a warning the user is already reading.
    multi = report.get("multi_valued_columns") or {}
    with st.expander("What was checked", expanded=bool(affected)):
        st.dataframe(rows, hide_index=True, width="stretch")
        if multi:
            st.markdown(
                "**Columns that should be constant within a trial but aren't.** "
                "Each may tell apart readings that the Trial ID merges."
            )
            st.dataframe(
                [
                    {"Column": col, "Trials with more than one value": count}
                    for col, count in multi.items()
                ],
                hide_index=True,
                width="stretch",
            )
        st.caption(
            "Checked on the whole dataset, before any filtering. Trials with "
            "several screens are checked screen by screen, since word ids restart "
            "on each screen."
        )


def _render_column_mapping_section(
    *,
    editor_rendered: bool = False,
    uploads_host=None,
    setup_host=None,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
) -> None:
    """The body of the Data page's **Column mapping** section.

    One section, three modes — a *presentation* merge, not a code merge. Two
    editors side by side on one page would read as a bug, but underneath they
    genuinely are two code paths: before normalization there are no canonical
    frames to remap, and after it there is no raw table to map from.

    * ``editor_rendered`` — mode **A**: the pre-normalization
      ``controls.column_mapping_ui`` panels belong to this section, drawn into
      it by ``app.prepare_data`` (a raw source with ``allow_override``) while
      ✏️ Edit dataset is open, so all that is left to add is the
      recording-setup note.
    * A stored uploaded dataset — mode **B**: the post-normalization
      ``_render_remap_editor``, offering only the columns that survived import.
    * Anything else — mode **C**: a read-only table built from the schemas the
      loaders stash under ``st.session_state['_active_column_mapping']``.

    The heading belongs to the page, not to any one mode — ``app.main`` renders
    it into a slot reserved above all three.

    ``setup_host`` is where the **Recording setup** block draws. All
    three modes end in one — editable in mode B, a read-only provenance summary
    in A and C — and on the ✏️ Edit dataset screen that block is a numbered part
    of its own, the way it is on the add screen, rather than a ``##### `` heading
    trailing the mapping form. Passed straight through, ``None`` included: a
    callee with no host renders inline under its own heading, and
    normalizing it to ``st`` here would silently drop that heading for every
    caller.

    In mode A the Recording setup is editable too while ✏️ Edit dataset is
    open (`render_builtin_setup_editor`, which reads ``words`` / ``fixations``
    for *Estimate from my data*): the demo and the public corpora have the
    editor's ✅ Save changes, and a declared setup can still be wrong for how
    someone uses the data — an assumed physical size, most often.
    """
    if editor_rendered:
        # The editable built-in mapping uses the same compact field grid as
        # Add dataset; widen its option menus just as the wizard does.
        st.markdown(mapping_menu_css(), unsafe_allow_html=True)
        token = str(st.session_state.get("data_source_choice") or "")
        if (
            setup_host is not None
            and token
            and st.session_state.get(DATASET_EDITOR_OPEN_KEY)
        ):
            render_builtin_setup_editor(token, words, fixations, setup_host)
        else:
            _render_setup_provenance_note(host=setup_host)
        return
    active = _active_stored_dataset()
    if active is not None:
        _render_remap_editor(*active, uploads_host=uploads_host, setup_host=setup_host)
        return
    mapping = st.session_state.get("_active_column_mapping") or {}
    rows = _column_mapping_rows(mapping)
    if not rows:
        st.info("No column mapping available for the current dataset.")
    else:
        _render_readonly_mapping_grid(rows)
        st.caption("Which of the dataset's columns fills each field the app reads.")
    # Not behind a `return` in that branch: the recording setup is a
    # *different* question from the mapping and a numbered part of its own —
    # leaving it undrawn would strand its headline over an empty body.
    _render_setup_provenance_note(host=setup_host)


def _render_setup_provenance_note(host=None) -> None:
    """How this dataset's recording setup is known.

    Data Inspection is where someone checks what the app did with their data, so
    it is where an *assumed* monitor has to be visible rather than inferred from
    a plausible-looking number elsewhere in the UI.

    ``host`` is the ✏️ Edit dataset screen's own **Recording setup**
    part. A caller that supplies one has already titled the block, so the
    ``##### `` heading is dropped rather than repeated under the part's headline;
    without one this renders inline, heading and all.
    """
    from scanpath_studio.app import active_setup_snapshot
    from scanpath_studio.experimental_setup import (
        SETUP_GROUP_LABELS,
        SETUP_GROUPS,
        Provenance,
    )

    # No host means "render inline", which is where the heading belongs; a
    # caller that hands one over has already titled the block itself.
    box = st if host is None else host
    snapshot = active_setup_snapshot()
    if snapshot is None:
        # Nothing to say — an uploaded dataset carries the wizard's snapshot and
        # a corpus that declares a monitor reports it, so this is a source that
        # claims neither (the synthetic trial). Inline that is silence.
        # Given a host it is not: this is the body of a *numbered* part, and a
        # headline standing over nothing reads as a section that failed to
        # render — the very thing contiguous numbering exists to prevent. So say
        # which of the two it is.
        if host is not None:
            box.caption(
                "This dataset doesn't state the screen it was recorded on, "
                "so none is assumed. Set it in "
                f"**{ICONS['figure']} Figure → {ICONS['screen']} Screen & framing** on the Scanpath "
                "view, or add the dataset yourself to record it here."
            )
        return
    if host is None:
        box.markdown("##### Recording setup")
    values = {
        "screen": f"{snapshot.canvas_width} × {snapshot.canvas_height} px",
        "geometry": (
            "—"
            if snapshot.geometry_provenance is Provenance.SKIPPED
            else f"{snapshot.monitor_width_mm:.0f} mm wide"
        ),
        "text": (
            "scaled to word boxes"
            if snapshot.scale_text_to_boxes
            else f"{snapshot.base_font_size} px · {snapshot.font_family}"
        ),
    }
    for cell, group in zip(box.columns(3, gap="medium"), SETUP_GROUPS):
        label = html.escape(SETUP_GROUP_LABELS[group])
        value = html.escape(values[group])
        provenance = html.escape(
            str(snapshot.provenance[group] or "not answered").capitalize()
        )
        cell.markdown(
            '<div class="sps-readonly-map-cell">'
            f'<div class="sps-readonly-map-label">{label}</div>'
            f'<div class="sps-readonly-map-value">{value}</div>'
            f'<div class="sps-readonly-map-note">{provenance}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    if snapshot.px_per_degree is not None:
        box.caption(
            f"{snapshot.px_per_degree:.2f} px per degree using a {snapshot.monitor_width_mm:g} mm "
            f"monitor width ({snapshot.geometry_provenance}) and a {snapshot.viewing_distance_mm:g} mm "
            f"viewing distance ({snapshot.viewing_distance_provenance or 'measurement status unknown'})."
        )
    _render_arrived_provenance_note(snapshot, host=box)


def _render_arrived_provenance_note(snapshot, *, host=None) -> None:
    """What the *sender* of a deep link said about their own setup.

    The `setup_prov` badge exists because a link carries the setup's **values**
    already: without it a recipient cannot tell a monitor the sender measured
    from one the app assumed on their behalf. That only works if it is *shown* —
    the table above is derived from the recipient's own source, so without this
    the arriving badge would be parsed, parked, and never read by anything.

    Shown only where it disagrees with what this session resolved; when the two
    agree it is noise.
    """
    from scanpath_studio.experimental_setup import SETUP_GROUP_LABELS, SETUP_GROUPS

    arrived = st.session_state.get(SETUP_PROVENANCE_STATE_KEY)
    if not isinstance(arrived, dict) or not arrived:
        return
    differing = [
        f"{SETUP_GROUP_LABELS[group]}: **{str(arrived[group]).capitalize()}**"
        for group in SETUP_GROUPS
        if group in arrived and arrived[group] != str(snapshot.provenance[group])
    ]
    if not differing:
        return
    (st if host is None else host).caption(
        "The link you opened was shared from a setup recorded differently ("
        + " · ".join(differing)
        + "). The table above shows the setup of the dataset open here."
    )


@st.cache_data(show_spinner="Building the derived analysis tables…", show_time=True)
def _c_derived_tables(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    words_fingerprint,
    fixations_fingerprint,
    raw_gaze_fingerprint,
    pixels_per_degree_value: float | None,
) -> dict:
    """The seven derived tables (stimuli, sentences, saccades, trial summary,
    participant summary, characters, cleaning report), built once per dataset.

    Reopening the derived tables reuses their results while the three frames
    and the recording setup's pixels-per-degree value agree.
    """
    from scanpath_studio.measures import assign_fixations_to_words, enrich_fixations
    from scanpath_studio.preprocessing import (
        character_grid,
        cleaning_report,
        saccade_table,
        sentence_measures,
    )

    measured_words = compute_word_metrics(_words, _fixations)
    analysis_fixations = (
        enrich_fixations(assign_fixations_to_words(_fixations, _words), _words)
        if not _fixations.empty and not _words.empty
        else _fixations
    )
    return {
        "Stimuli": _build_stimuli_table_cached(_words, words_fingerprint),
        "Sentences": sentence_measures(measured_words, _fixations),
        "Saccades": saccade_table(
            analysis_fixations,
            pixels_per_degree=pixels_per_degree_value,
            raw_gaze=_raw_gaze,
            words=_words,
        ),
        "Trial summary": trial_summary_table(measured_words, _fixations),
        "Participant summary": reader_summary_table(measured_words, _fixations),
        "Characters": character_grid(_words),
        "Cleaning report": cleaning_report(_fixations),
    }


def _format_spread_number(value, *, decimals: int = 2) -> str:
    """One spread figure, as a reader would write it.

    Whole numbers lose their decimals — "12 trials per participant" is the fact,
    and "12.00" spends three characters saying the data is not fractional. A
    missing value is an em dash rather than ``nan``: the row exists because the
    metric does, and an empty source frame is not a number.
    """
    if value is None or not isinstance(value, (int, float)) or pd.isna(value):
        return "—"
    number = float(value)
    if abs(number - round(number)) < 0.005:
        return f"{round(number):,}"
    return f"{number:,.{decimals}f}"


def _format_spread_mean(value) -> str:
    """The headline figure on a spread metric — rounded.

    All three metrics count things (trials, fixations, words), so "133.71
    fixations per trial" spends two decimals on a precision the quantity does
    not have. Below 10 one decimal is kept: a mean of 0.4 rounded to 0 reads as
    "none", which is a different claim.
    """
    if value is None or not isinstance(value, (int, float)) or pd.isna(value):
        return "—"
    number = float(value)
    if abs(number) < 10 and abs(number - round(number)) >= 0.005:
        return f"{number:,.1f}"
    return f"{round(number):,}"


def _spread_help(row: dict) -> str | None:
    """The spread behind one mean, for that metric's own ❔.

    On the card's hover rather than its face: the mean is what the row is read
    for, and the standard deviation and range are the follow-up question. Also
    where the caveat lives — the statistics describe what the current filters
    left, not the whole dataset.
    """
    std = _format_spread_number(row.get("Std"))
    low = _format_spread_number(row.get("Min"), decimals=0)
    high = _format_spread_number(row.get("Max"), decimals=0)
    pieces = []
    if std not in ("—", "0"):
        pieces.append(f"± {std} SD")
    if low != high and "—" not in (low, high):
        pieces.append(f"range {low}–{high}")
    spread = " · ".join(pieces) if pieces else "Same count in each group"
    grouping = {
        "Trials per participant": "Includes participants with a selected trial.",
        "Fixations per trial": "Includes trials with fixation rows.",
        "Words per trial": "Includes trials with word rows.",
        "Gaze samples per trial": "Includes trials with gaze samples.",
    }
    return f"{spread}. {grouping[row['Metric']]}"


def _render_spread_cards(spread: pd.DataFrame) -> None:
    if spread is None or spread.empty:
        return
    with st.container(key="data_averages"):
        st.markdown("#### Averages")
        grid = st.grid(3, min_column_width=135, gap="small")
        for row in spread.to_dict("records"):
            grid.metric(
                row["Metric"], _format_spread_mean(row["Mean"]), help=_spread_help(row)
            )


def _inspect_recording_table(table: str) -> None:
    st.session_state["_data_table_target"] = table
    st.session_state[DATA_INSPECTION_KEY] = "Tables"


def render_dataset_summary(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame,
    *,
    scope: str | None,
) -> None:
    """Overview of the selected trials, their typical size and their source tables."""
    stats = _dataset_statistics(
        words,
        fixations,
        raw_gaze,
        cache_key=tuple(
            frame_fingerprint(frame) for frame in (words, fixations, raw_gaze)
        ),
    )
    render_data_scope(scope, key="data_scope_stats")
    with st.container(key="data_totals"):
        size = st.grid(3, min_column_width=100, gap="small")
        for label, field, icon in (
            ("Participants", "n_participants", "participants"),
            ("Trials", "n_trials", "trials"),
            ("Texts", "n_texts", "texts"),
        ):
            size.metric(label, f"{stats[field]:,}", icon=ICONS[icon], border=True)
    _render_spread_cards(stats["stats_df"])
    with st.container(key="data_recording_tables"):
        st.markdown("#### Eye-tracking data")
        with st.container(key="data_recording_header"):
            st.markdown("**Table** :gray[Rows] :gray[Trials with data]")
        for table, (label, _) in _RECORDING_TABLES.items():
            rows, covered = stats["recordings"][table]
            coverage = (
                f"{covered:,} of {stats['n_trials']:,}" if stats["n_trials"] else "—"
            )
            st.button(
                f"**{label}** :gray[{rows:,}] :gray[{coverage}]",
                type="tertiary",
                width="stretch",
                key=f"data_inspect_{table}",
                on_click=_inspect_recording_table,
                args=(table,),
                help=f"Open the {label} table",
            )
        missing = stats["fixations_without_words"]
        if missing and stats["recordings"]["words"][1]:
            st.caption(f"{plural(missing, 'trial')} with fixations but no word rows.")
    if stats["screen_error"]:
        st.warning(stats["screen_error"])
    elif not stats["parts"].empty:
        with st.expander(f"Trial screens ({len(stats['parts']):,})"):
            st.caption("One row per screen within a participant’s trial.")
            st.dataframe(stats["parts"], hide_index=True, width="stretch")
    _render_data_provenance()


@st.cache_data(show_spinner=False, max_entries=8)
def _c_data_health(_words, _fixations, _raw_gaze, key) -> list:
    """`data_health.check_data_health`, once per dataset (keyed on fingerprints)."""
    from .data_health import check_data_health

    return check_data_health(_words, _fixations, _raw_gaze)


#: How a health finding names the rows of each table.
_HEALTH_ROW_NOUN = {"fixations": "fixation", "words": "word", "raw_gaze": "raw-gaze"}

#: A data check is worth a notice on the Scanpath view when it flags more
#: than this share of its table's rows. A few 0 ms fixations or a missing
#: position are ordinary in a recording, and stay on the Data page; most of a
#: table flagged is a column mapped to the wrong field or a broken export.
SERIOUS_HEALTH_SHARE = 0.5


def _dataset_health_findings(words, fixations, raw_gaze) -> list:
    """`_c_data_health` under the key the Data page's *Data checks* uses, so
    the Scanpath view and the Data page share one run."""
    return _c_data_health(
        words,
        fixations,
        raw_gaze,
        (
            frame_fingerprint(words),
            frame_fingerprint(fixations),
            frame_fingerprint(raw_gaze),
        ),
    )


def serious_health_lines(findings) -> list[str]:
    """One line per *warning* finding that flags most of its table's rows
    (`SERIOUS_HEALTH_SHARE`)."""
    lines = []
    for finding in findings:
        if finding.severity != "warning" or not finding.total_rows:
            continue
        if finding.rows <= SERIOUS_HEALTH_SHARE * finding.total_rows:
            continue
        noun = _HEALTH_ROW_NOUN.get(finding.table, finding.table)
        lines.append(
            f"**{finding.title}**: {finding.rows:,} of {finding.total_rows:,} "
            f"{noun} rows."
        )
    return lines


def render_data_health_notice(host, words, fixations, raw_gaze) -> None:
    """A notice on the Scanpath view when the dataset fails a data check badly.

    The figure is drawn either way, and looks plausible: a duration mapped to
    a column of words draws every fixation at the smallest size. So when a
    check flags most of a table (`serious_health_lines`), say so above the
    plot and point to 🗂️ Data Management → *Data checks*, where the rows are
    listed. ``host`` is a slot drawn on every run.
    """
    findings = _dataset_health_findings(words, fixations, raw_gaze)
    lines = serious_health_lines(findings)
    if not lines:
        return
    box = host.container(key="data_health_notice")
    box.warning(
        "Data checks found problems that may affect this figure.  \n"
        + "  \n".join(lines)
        + "  \nSee **Data Management → Data checks** for the rows. If a field "
        "is mapped to the wrong column, change it under **Edit dataset**, or "
        "remove the dataset and add its files again.",
        icon=ICONS["warning"],
    )
    from scanpath_studio.app import open_dataset_panel

    box.button(
        "Open Data checks",
        icon=ICONS["view_data"],
        key="data_health_notice_open",
        on_click=open_dataset_panel,
        args=("Data checks",),
    )


def _attach_run_sheet(dataset: str, widget: str) -> None:
    file = st.session_state.get(widget)
    if file is None:
        return
    try:
        expected = pd.read_csv(
            io.BytesIO(file.getvalue()),
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
    except (UnicodeError, ValueError) as exc:
        expected = str(exc)
    st.session_state.setdefault(DATA_RUN_SHEETS_KEY, {})[dataset] = (
        file.name,
        expected,
    )


def _render_run_sheet(sheet, dataset: str, frames: dict) -> None:
    from .study_checks import reconcile_run_sheet

    sheets = st.session_state.setdefault(DATA_RUN_SHEETS_KEY, {})
    if dataset not in sheets:
        sheet.markdown(
            "Compare the trials you planned with the ones in this dataset to find missing or unexpected recordings."
        )
        sheet.caption(
            "Upload a CSV with one row per planned trial and these two column names."
        )
        sheet.code("participant_id,trial_id\nP01,T01\nP01,T02", language="csv")
        widget = f"expected_readings_{dataset}"
        sheet.file_uploader(
            "Planned trials (CSV)",
            type=["csv"],
            key=widget,
            max_upload_size=upload_limit_mb(),
            help="For individual screens, add `screen_id`. For trials you planned to omit, add a reason in `planned_omission`.",
            on_change=_attach_run_sheet,
            args=(dataset, widget),
        )
        return
    name, expected = sheets[dataset]
    row = sheet.container(horizontal=True, vertical_alignment="center")
    row.markdown(md_literal(name), width="stretch")
    row.button(
        "Remove run sheet", key="remove_run_sheet", on_click=sheets.pop, args=(dataset,)
    )
    if isinstance(expected, str):
        sheet.error(f"Couldn’t read this CSV. {expected}")
        return
    try:
        report = reconcile_run_sheet(expected, frames)
    except ValueError as exc:
        sheet.error(str(exc))
        return
    counts = report["status"].value_counts()
    if not counts.empty:
        sheet.caption(
            " · ".join(f"{label} ({count:,})" for label, count in counts.items())
        )
    sheet.dataframe(report, hide_index=True)
    sheet.download_button(
        "Download comparison (CSV)",
        data=report.to_csv(index=False),
        file_name="run_sheet_reconciliation.csv",
        mime="text/csv",
        on_click="ignore",
    )


def render_data_health(
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    raw_gaze: pd.DataFrame | None,
    *,
    filtered: bool = False,
    dataset: str = "",
) -> None:
    """Checks on the current dataset for values that parsed but
    cannot be right — a fixation of 0 ms or less, a duration, onset or position
    that is not a finite number, a word box with no area, a per-screen screen
    size that cannot be used (`data_health`).

    Runs on the whole dataset, before the trial filters, cached per dataset, so
    a rerun costs a fingerprint lookup. Each finding names the dataset's own
    columns, counts rows and trials, quotes a few rows and says what
    the app does with them. Nothing is removed or changed.
    """
    from .column_names import active
    from .data_health import applicable_checks

    frames = {"words": words, "fixations": fixations, "raw_gaze": raw_gaze}
    checked = list(dict.fromkeys(c.topic for c in applicable_checks(frames)))
    findings = _dataset_health_findings(words, fixations, raw_gaze)
    with st.container(key="dataset_health"):
        results = st.container()
        sheet = st.expander(
            "Compare with planned trials (optional)",
            key="data_run_sheet",
            on_change="rerun",
        )
        if sheet.open:
            _render_run_sheet(
                sheet,
                dataset,
                frames,
            )
    with results:
        st.subheader("Recording quality checks", anchor=False)
        if not checked:
            st.info(
                "The available tables have no recording values that these checks can test."
            )
            return
        scope_note = (
            " These checks include trials hidden by the Scanpath filters."
            if filtered
            else ""
        )
        st.caption(
            "Checked "
            + (", ".join(checked[:-1]) + " and " if len(checked) > 1 else "")
            + checked[-1]
            + "."
            + scope_note
        )
        if not findings:
            st.success("No issues found in the values checked.")
            return
        lines: dict[str, list[str]] = {"warning": [], "note": []}
        for finding in findings:
            names = active(st.session_state, finding.table)
            columns = ", ".join(f"`{names.label(c)}`" for c in finding.columns)
            kinds = ", ".join(f"{n:,} {k}" for k, n in finding.breakdown.items())
            noun = _HEALTH_ROW_NOUN.get(finding.table, finding.table)
            trials = f"{finding.trials:,} trial" + ("" if finding.trials == 1 else "s")
            lines[finding.severity].append(
                f"**{finding.title}**: {finding.rows:,} of {finding.total_rows:,} "
                f"{noun} rows in {trials} ({kinds}). Columns: {columns}."
            )
        if lines["warning"]:
            st.warning("  \n".join(lines["warning"]), icon=ICONS["warning"])
        if lines["note"]:
            st.caption("  \n".join(lines["note"]))
        with st.expander("Examples and effects on the figure"):
            st.caption(
                "Flagged rows stay in the data. The examples show how each issue affects the figure."
            )
            for finding in findings:
                names = active(st.session_state, finding.table)
                st.markdown(f"**{finding.title}**")
                st.caption(finding.consequence)
                if finding.examples:
                    example = pd.DataFrame(list(finding.examples))
                    st.dataframe(
                        example.rename(columns=names.label),
                        hide_index=True,
                        width="stretch",
                    )
        reviewable = [f for f in findings if f.rows and f.trials]
        review = st.expander(
            "Review affected readings",
            key="data_health_readings",
            on_change="rerun",
        )
        if review.open and reviewable:
            from .data_health import affected_rows

            finding = review.selectbox(
                "Data check",
                reviewable,
                format_func=lambda f: f.title,
                key="health_review_check",
            )
            source = {"words": words, "fixations": fixations, "raw_gaze": raw_gaze}[
                finding.table
            ]
            rows = affected_rows(source, finding)
            keys = [c for c in ("participant_id", "trial_id", "screen_id") if c in rows]
            if keys and not rows.empty:
                groups = rows.groupby(keys, sort=False, dropna=False).indices
                readings = list(groups)
                key = f"health_review_reading_{finding.check}"
                selected = review.selectbox(
                    "Affected reading",
                    readings,
                    key=key,
                    format_func=lambda reading: " / ".join(map(str, reading)),
                )
                index = readings.index(selected)
                review.caption(
                    f"Reading {index + 1} of {len(readings)}. Values are in the normalized table's units."
                )
                review.dataframe(
                    rows.iloc[groups[selected]].rename(
                        columns=active(st.session_state, finding.table).label
                    ),
                    hide_index=True,
                )

                def move(position):
                    st.session_state[key] = readings[position]

                back, forward = review.columns(2)
                back.button(
                    "Previous affected reading",
                    disabled=index == 0,
                    on_click=move,
                    args=(index - 1,),
                )
                forward.button(
                    "Next affected reading",
                    disabled=index + 1 == len(readings),
                    on_click=move,
                    args=(index + 1,),
                )


def _render_derived_tables(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    raw_gaze_filtered: pd.DataFrame,
) -> None:
    """Build the experimental tables when their disclosure is opened."""
    panel = st.expander(
        "Derived analysis tables", key="data_derived_tables", on_change="rerun"
    )
    if not panel.open:
        return
    with panel:
        from scanpath_studio.experimental_setup import pixels_per_degree

        try:
            ppd = pixels_per_degree(
                float(st.session_state.get("global_viewing_distance_mm", 800.0)),
                float(st.session_state.get("global_canvas_width", 1200.0)),
                float(st.session_state.get("global_monitor_width_mm", 597.0)),
            )
        except (TypeError, ValueError):
            ppd = None
        derived = _c_derived_tables(
            words_filtered,
            fixations_filtered,
            raw_gaze_filtered,
            frame_fingerprint(words_filtered),
            frame_fingerprint(fixations_filtered),
            frame_fingerprint(raw_gaze_filtered),
            ppd,
        )
        # *Cleaning report* is the preprocessing pipeline's own provenance table
        # — one row per trial saying what that stage excluded and why — so it
        # is shown only while preprocessing is enabled. The other six are
        # plain analysis tables (some live in `preprocessing.py`); they are
        # unaffected.
        if not preprocessing_enabled():
            derived = {k: v for k, v in derived.items() if k != "Cleaning report"}
        for tab, (label, table) in zip(st.tabs(list(derived)), derived.items()):
            with tab:
                if table.empty:
                    st.caption(
                        f"No {label.lower()} table is available for this selection."
                    )
                else:
                    _render_raw_table(table)
