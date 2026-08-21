"""Tab rendering functions for the Scanpath Studio app."""

from __future__ import annotations

import contextlib
import html
import json
import os
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from scanpath_studio import alignment
from scanpath_studio.aggregation import (
    MEASURES,
    Measure,
    apply_group,
    available_features,
    available_measures,
    cohort_word_profile,
    ensure_fixation_enrichment,
    group_effect_size,
    group_word_difference,
    landing_positions,
    measure_values,
    metric_by_trial_index,
    metric_over_time,
    paired_group_summary,
    per_participant_trend,
    per_reader_word_measure,
    progressive_regressive_counts,
    reader_summary,
    reader_summary_table,
    reader_vs_cohort_values,
    saccade_vs_duration,
    text_read_counts,
    text_screen_options,
    trial_summary_table,
    two_group_values,
    two_group_word_profiles,
    word_box_aggregate,
    word_measure_vs_feature,
    word_rate_profile,
)
from scanpath_studio.animation_export import (
    CHROME_INSTALL_HINT,
    AnimationExportError,
    chrome_available,
    export_animation,
    mime_for,
)
from scanpath_studio.annotations import filter_keys, render_trial_annotations
from scanpath_studio.compare_source import (
    COMPARE_SOURCE_KEY,
    THIS_DATASET,
    SecondaryDataset,
    load_secondary_dataset,
    secondary_dataset_options,
    snapshot_for,
)
from scanpath_studio.constants import (
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_PALETTE,
    DEFAULT_SACCADE_WIDTH,
    DEMO_CHOICE,
    FOCUS_MAPPING_KEY,
    HIGHLIGHTED_TEXT_COLOR,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    SELECTOR_ROW_GRID,
    SELECTOR_ROW_TRIO,
    SELECTOR_ROW_WIDE_GRID,
    TRIAL_IDENTITY_FULL_KEY,
    WORD_LABEL_COLOR,
    compare_palette_color,
    drift_correction_enabled,
    preprocessing_enabled,
    similarity_enabled,
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    SUMMARY_CHIP_FIELDS,
    WORD_FIELD_SPECS,
    _collect_compare_styles,
    _drop_stale,
    _gated_help,
    _labeled,
    _numeric_slider,
    column_mapping_ui,
    corpus_style_controls,
    current_dataset_name,
    read_trial_filters,
    render_narrow_by,
    render_pattern_help,
    render_pattern_input,
    render_trial_chip_picker,
    render_trial_filters,
    render_viz_reset,
    sidebar_controls,
)
from scanpath_studio.data import (
    compute_word_metrics,
    derive_trial_index,
    filter_to_keys,
    filter_trials,
    frame_fingerprint,
    has_explicit_trial_index,
    remap_normalized_frame,
    trial_keys,
    trial_mapping_columns,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from scanpath_studio.debug_log import timed
from scanpath_studio.export import (
    ComparisonSide,
    ExportOptions,
    annotate_figure,
    bulk_export,
    pair_export,
    pattern_fields,
    render_export_options,
    render_pattern,
    render_static_figure_bytes,
)
from scanpath_studio.export_status import (
    EXPORTER_VERSION,
    ExportStage,
    ExportStatus,
    progress_caption,
    static_export_signature,
)
from scanpath_studio.fields import labeled, panel_field
from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.illustration import illustration_reasons, resolve_label_reasons
from scanpath_studio.multipart import (
    SCREEN_ID,
    extract_part,
    has_screen_identity,
    part_catalog,
    screen_canvas_size,
)
from scanpath_studio.plots import (
    STATIC_FIGURE_OPTIONS,
    FigureSettings,
    _discard_flagged_fixations,
    _png_pixel_size,
    add_illustration_label,
    animation_autoplay_frame_duration,
    animation_autoplay_post_script,
    animation_playback_ms,
    animation_timeline_summary,
    make_comparison_figure,
    make_density_scatter_figure,
    make_difference_profile_figure,
    make_distribution_figure,
    make_feature_scatter_figure,
    make_landing_curve_figure,
    make_metric_convergence_figure,
    make_paired_bars_figure,
    make_progression_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    make_small_multiples_figure,
    make_trend_figure,
    make_word_matrix_heatmap,
    make_word_profile_figure,
    make_word_rate_figure,
)
from scanpath_studio.session_keys import (
    PENDING_COMPARE_STATE_KEY,
    SETUP_PROVENANCE_STATE_KEY,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
)
from scanpath_studio.similarity import (
    METRICS,
    compute_similarity_table,
    nld_by_fixation_index,
    nld_by_time,
)
from scanpath_studio.styles import mapping_menu_css
from scanpath_studio.utils import (
    COMPARE_DATASET_SEP,
    COMPARE_OPTIONS_SNAPSHOT_KEY,
    COMPARE_STEP_LINK_KEY,
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
    safe_summary,
    select_trial,
    sort_trial_options,
    step_within,
    trial_options_snapshot_key,
    trial_sort_keys,
    unqualify_for_export,
)

# -----------------------------------------------------------------------------
# Single Trial Tab
# -----------------------------------------------------------------------------

#: The Scanpath view's subtab labels. Named because the set is no longer fixed:
#: PRE-21 offers 📐 Line assignment only while drift correction is exposed, so
#: the tabs are built as a list and mapped back by label. `tests/conftest.py`
#: imports these rather than repeating the strings.
SUBTAB_ANNOTATIONS = "📝 Annotations"
SUBTAB_STIMULUS = "📄 Stimulus & Context"
SUBTAB_COMPARISONS = "🔬 Comparisons"
SUBTAB_LINE_ASSIGNMENT = "📐 Line assignment"
SUBTAB_EXPORT = "📤 Export"
SUBTAB_SHARE = "🔗 Share"


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


def _step_screen(options: tuple[str, ...], delta: int) -> None:
    """Move the multipart navigator without touching the parent trial picker."""
    if not options:
        return
    current = str(st.session_state.get("single_screen_id", options[0]))
    position = options.index(current) if current in options else 0
    st.session_state["single_screen_id"] = options[
        max(0, min(len(options) - 1, position + delta))
    ]


def _on_screen_slider() -> None:
    """Mirror a scrub of the screen slider onto the canonical selectbox.

    ``single_screen_id`` stays the one selection every other reader consults
    (``_step_screen``, ``extract_part``); the slider is a second view of it, the
    same arrangement ``utils._select_trial_none_mode`` uses for the trial picker.
    """
    st.session_state["single_screen_id"] = st.session_state["single_screen_pos"]


def _render_screen_navigator(catalog: pd.DataFrame) -> str | None:
    """Select/scrub/step navigator for one logical multipart trial.

    **UX-47**: this row carries the same grammar as the trial picker directly
    above it (``utils._select_trial_none_mode``) — a ``[3, 5, 1.9]`` split with
    the selectbox, a scrubbing slider, then ◀ ▶ in a right-packed ``railbtn_*``
    cluster. It used to be ``[0.7, 5, 0.7]`` with the two steps *straddling* the
    selectbox as ``width="stretch"`` buttons outside the railbtn system, so the
    screen dropdown started ~11% in (against the trial dropdown's 0) at 78% wide
    (against 30%), and its steps rendered as wide rectangles beside the pill
    clusters on every neighbouring row.
    """
    if catalog.empty:
        st.session_state.pop("single_screen_id", None)
        st.session_state.pop("single_screen_pos", None)
        return None
    options = tuple(catalog[SCREEN_ID].astype(str))
    current = st.session_state.get("single_screen_id")
    if current not in options:
        st.session_state["single_screen_id"] = options[0]
    labels = {
        str(
            row.screen_id
        ): f"{int(row.screen_index)} of {len(catalog)} · {row.screen_id}"
        for row in catalog.itertuples()
    }
    sel_col, slider_col, trail_col = st.columns(
        SELECTOR_ROW_TRIO, vertical_alignment="bottom"
    )
    position = options.index(str(st.session_state["single_screen_id"]))
    selected = sel_col.selectbox(
        "**Screen**",
        options,
        key="single_screen_id",
        format_func=labels.get,
        help="One coordinate space at a time; the parent trial selection stays fixed.",
    )
    if len(options) > 1:
        # Mirror the canonical selection onto the slider BEFORE it renders, so
        # picking a screen in the dropdown (or stepping with ◀ ▶) moves the thumb
        # too; the drag callback writes back the other way, reconciling next run.
        st.session_state["single_screen_pos"] = str(
            st.session_state["single_screen_id"]
        )
        with slider_col:
            st.select_slider(
                "Screen position",
                options=options,
                key="single_screen_pos",
                on_change=_on_screen_slider,
                format_func=labels.get,
                help=f"Scrub through this trial's {len(options)} screens; the "
                "dropdown jumps straight to one.",
                label_visibility="collapsed",
            )
    # Both steps in ONE keyed container: styles.py lays every `railbtn_*` out as a
    # right-packed flex ROW, which is what puts them on the same edge, at the same
    # 3px spacing and in the same pill shape as the trial row's ◀ ▶ ⇅ above and
    # the chip strip below. `width="stretch"` is deliberately gone — it fought the
    # `width: auto` that makes the cluster content-sized.
    trail = trail_col.container(key="railbtn_single_screen_trail")
    trail.button(
        "◀",
        key="single_screen_previous",
        help="Previous screen in this logical trial",
        disabled=position == 0,
        on_click=_step_screen,
        args=(options, -1),
    )
    trail.button(
        "▶",
        key="single_screen_next",
        help="Next screen in this logical trial",
        disabled=position == len(options) - 1,
        on_click=_step_screen,
        args=(options, 1),
    )
    return str(selected)


def _part_catalog_for_display(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Use MultiplEYE's fixation-onset order if cached word order is stale."""
    try:
        return part_catalog(words, fixations)
    except ValueError as exc:
        if (
            str(exc) == "Multipart metadata 'screen_index' conflicts across tables."
            and "screen_kind" in fixations.columns
        ):
            return part_catalog(fixations)
        raise


def _embed_html_iframe(html: str, *, height: int) -> None:
    """Backward-compatible local alias for the shared iframe helper."""
    embed_html_iframe(html, height=height)


# VIZ-zoom (MVP): Plotly's own zoom only rescales the *axes*, so the word boxes
# and saccades spread apart while the fixation markers, label font and line
# widths stay pinned at the screen-pixel sizes they were built with — the plot
# stops being true to scale the moment you zoom. These modebar buttons are
# therefore removed and `dragmode` is switched off (below), and magnification is
# done by scaling the whole rendered block instead, exactly like the fit-to-column
# transform this function already applies.
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
<div id="wrap-__KEY__" style="position:relative;width:100%;">
  <div id="fit-__KEY__" style="width:100%;overflow:hidden;">
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
  var outer = document.getElementById("fit-__KEY__");
  var size = document.getElementById("size-__KEY__");
  var box = document.getElementById("box-__KEY__");
  var label = document.getElementById("zoomlabel-__KEY__");
  var zoom = 1, base = 1;

  function baseScale() {
    var avail = outer.clientWidth || W;
    return __SCALE_JS__;
  }
  // One uniform transform for fit x zoom: boxes, fixations, labels and stroke
  // widths all magnify together, so the figure stays true to scale.
  function render() {
    base = baseScale();
    var s = base * zoom;
    box.style.transform = "scale(" + s + ")";
    size.style.width = Math.round(W * s) + "px";
    size.style.height = Math.round(H * s) + "px";
    outer.style.height = Math.round(H * base) + "px";
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
  setTimeout(render, 150);

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

  // Switch off Plotly's own drag interactions so a drag on the plot pans this
  // block instead of box-zooming the axes (which is what broke the sizing).
  (function killNativeZoom() {
    var gd = document.getElementById("truescale-__KEY__");
    if (!window.Plotly || !gd || !gd._fullLayout) { setTimeout(killNativeZoom, 100); return; }
    window.Plotly.relayout(gd, {dragmode: false});
  })();
})();
</script>
"""

_ZOOM_TOOLBAR = """
  <div id="zoombar-__KEY__" style="position:absolute;top:4px;left:4px;z-index:5;
       display:flex;gap:2px;align-items:center;padding:2px 4px;
       font:11px/1.6 system-ui,sans-serif;color:#444;
       background:rgba(255,255,255,0.88);border:1px solid #ddd;border-radius:4px;">
    <button id="zoomout-__KEY__" title="Zoom out" style="__BTN__">&minus;</button>
    <span id="zoomlabel-__KEY__" style="min-width:34px;text-align:center;">100%</span>
    <button id="zoomin-__KEY__" title="Zoom in" style="__BTN__">+</button>
    <button id="zoomreset-__KEY__" title="Reset zoom" style="__BTN__">&#8635;</button>
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
) -> tuple[str, int]:
    """Wrap a fixed-size Plotly div in the fit-to-column (+ zoom) transform.

    Pure so the embed markup is testable without a Streamlit run. Returns the
    HTML and the iframe height to reserve for it.
    """
    if max_height is not None:
        scale_js = f"Math.min(1, avail / W, {int(max_height)} / H)"
        iframe_height = int(max_height) + 12
    else:
        scale_js = "Math.min(1, avail / W)"
        iframe_height = height + 12
    toolbar = (
        _ZOOM_TOOLBAR.replace("__BTN__", _ZOOM_BUTTON_CSS).replace("__KEY__", key)
        if zoomable
        else ""
    )
    html = (
        _TRUE_SCALE_TEMPLATE.replace("__TOOLBAR__", toolbar)
        .replace("__PLOT__", plot_html)
        .replace("__SCALE_JS__", scale_js)
        .replace("__ZOOMABLE__", "true" if zoomable else "false")
        .replace("__ZMAX__", str(_ZOOM_MAX))
        .replace("__W__", str(int(width)))
        .replace("__H__", str(int(height)))
        .replace("__KEY__", key)
    )
    return html, iframe_height


def _render_true_scale_chart(fig, *, key: str, max_height: int | None = None) -> None:
    """Display a spatial figure true-to-scale, fitted to the column width.

    ``st.plotly_chart`` pins the chart width to the column but keeps the layout
    height, re-laying-out the plot to an unknown scale — which breaks the
    data→pixel sizing the word labels were computed for (text over/under fills
    the boxes). Instead we render the figure at its exact pixel size, then scale
    that whole block *uniformly* with a CSS transform so it fills the column
    width. A uniform transform keeps boxes, fixations and text locked at one true
    scale (unlike a Plotly re-layout, which leaves the font fixed), so the plot
    stays faithful to the experiment at any column width — and never needs
    horizontal scrolling. It is only scaled down to fit, so on a wide monitor it
    sits at true size with margin rather than being stretched.

    **Zoom** rides on the same transform (MVP): the fit scale is multiplied by a
    zoom factor (1×–8×) driven by the small toolbar, Ctrl/Cmd + wheel and
    trackpad pinch, with drag-to-pan inside a fixed-height viewport. Plotly's own
    zoom/pan is removed from the modebar and ``dragmode`` is switched off,
    because an axis re-layout leaves markers, fonts and line widths at their
    original pixel sizes — the thing this whole function exists to avoid. Zoom is
    view-only: it never touches the figure, so exports and Share are unaffected.

    ``max_height`` caps the rendered (scaled) height in px — used for the small
    multiples in the *Multiple Comparison* grid, where the figure should also
    shrink to fit a fixed cell height (whichever of width/height binds), and the
    iframe is sized to that cap so panels don't leave a tall band of whitespace.
    Those panels stay zoom-free.
    """
    width = int(fig.layout.width or 900)
    height = int(fig.layout.height or 600)
    zoomable = max_height is None
    # VIZ-10: an animation built with autoplay on carries its per-frame duration on
    # the figure; kick off `Plotly.animate` at that speed after mount (Plotly's own
    # `auto_play` would ignore the configured speed). `None` for static figures or
    # autoplay-off animations → the built-in `auto_play=False` keeps them paused.
    autoplay_ms = animation_autoplay_frame_duration(fig)
    autoplay_script = (
        animation_autoplay_post_script(autoplay_ms) if autoplay_ms is not None else None
    )
    config: dict = {"responsive": False, "displaylogo": False}
    if zoomable:
        config["modeBarButtonsToRemove"] = list(_NATIVE_ZOOM_BUTTONS)
    plot_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config=config,
        div_id=f"truescale-{key}",
        # to_html defaults to auto_play=True, which auto-runs an animated figure on
        # load at Plotly's default frame duration (ignoring the configured playback
        # speed). Start paused so the animation only plays — at the right speed —
        # either via the autoplay kickoff below or when the user presses Play. No
        # effect on static (frame-less) figures.
        auto_play=False,
        post_script=autoplay_script,
    )
    html, iframe_height = _true_scale_html(
        plot_html,
        key=key,
        width=width,
        height=height,
        max_height=max_height,
        zoomable=zoomable,
    )
    # Iframe height = full true height (or the cap); the script trims the
    # visible block to the scaled height.
    _embed_html_iframe(html, height=iframe_height)


def _trial_text_id(trial_words: pd.DataFrame) -> str | None:
    """Best-available text identifier for a trial's words (for same-text checks)."""
    for col in ("unique_text_id", "text_id"):
        if col in trial_words.columns and not trial_words.empty:
            value = trial_words[col].iloc[0]
            if pd.notna(value):
                return str(value)
    return None


_MIME_FOR_FORMAT = {
    "PNG": "image/png",
    "SVG": "image/svg+xml",
    "PDF": "application/pdf",
    "HTML": "text/html",
}


def _render_save_plot_button(
    fig,
    *,
    canvas_width: int,
    canvas_height: int,
    slug: str,
    key_prefix: str,
) -> None:
    """Download the currently displayed figure.

    HTML is cheap (no Kaleido/Chrome) so it downloads in a single click. PNG/SVG/
    PDF go through Kaleido, which spins up a headless Chrome — far too slow to run
    on every Streamlit rerun — so those keep a Render step and reveal the download
    only once the image is ready. Width/height come from the figure's own layout
    so stacked / multi-panel figures save at their on-screen size.
    """
    if fig is None:
        return
    file_stem = f"scanpath_{_safe_filename(slug)}"
    # UX-69: `label | field` rows. The pre-UX-43 note here said "stacked (not
    # columned) so the controls fit the narrow side-panel Export toggle" — that
    # toggle is long gone; this is a full-width subtab now, and the width the
    # stack was avoiding is exactly what the label column spends.
    fmt = panel_field(
        st,
        "radio",
        "Download format",
        # HTML is a browser-free fallback (no Kaleido/Chrome) — useful on
        # Streamlit Cloud where static image export needs a Chromium binary.
        options=["PNG", "SVG", "PDF", "HTML"],
        index=0,
        horizontal=True,
        key=f"{key_prefix}_save_format",
        help="PNG/SVG/PDF need a Chrome/Chromium browser (Kaleido). HTML "
        "is interactive and needs no browser.",
    )

    # HTML: one-click download — no expensive render to defer.
    if fmt == "HTML":
        html_bytes = fig.to_html(include_plotlyjs="cdn", full_html=True).encode("utf-8")
        st.download_button(
            "⬇ Download HTML",
            data=html_bytes,
            file_name=f"{file_stem}.html",
            mime=_MIME_FOR_FORMAT["HTML"],
            key=f"{key_prefix}_save_button_html",
        )
        return

    # PNG/SVG/PDF: render on click (Kaleido/Chrome), then reveal the download.
    # The signature includes the complete figure JSON and every exporter option,
    # so the durable result survives harmless reruns but can never leak across a
    # trial, format, scale, size, or visual-setting change (EXP-6).
    fig_width = int(fig.layout.width or canvas_width)
    fig_height = int(fig.layout.height or canvas_height)
    scale = 3 if fmt == "PNG" else 1
    sig = static_export_signature(
        fig,
        fmt=fmt,
        width=fig_width,
        height=fig_height,
        scale=scale,
    )
    cache_key = f"_{key_prefix}_static_export_cache"
    inflight_key = f"_{key_prefix}_static_export_inflight"
    cache = st.session_state.get(cache_key)
    if cache and cache.get("sig") != sig:
        st.session_state.pop(cache_key, None)
        cache = None

    generate = st.button(
        f"Render {fmt}",
        key=f"{key_prefix}_save_generate",
        help="Renders the image (needs Chrome/Kaleido); the download button "
        "appears once it's ready.",
        disabled=st.session_state.get(inflight_key) == sig,
    )
    if generate:
        status_box = st.status("Preparing export…", expanded=True)

        def _on_status(status: ExportStatus) -> None:
            elapsed = f" · {status.elapsed_s:.1f}s" if status.elapsed_s else ""
            state = (
                "complete"
                if status.stage == ExportStage.READY
                else "error"
                if status.stage == ExportStage.ERROR
                else "running"
            )
            status_box.update(label=f"{status.message}{elapsed}", state=state)

        st.session_state[inflight_key] = sig
        try:
            data = render_static_figure_bytes(
                fig,
                fmt=fmt.lower(),
                width=fig_width,
                height=fig_height,
                scale=scale,
                status_callback=_on_status,
            )
        except Exception as exc:
            st.session_state.pop(cache_key, None)
            hint = (
                CHROME_INSTALL_HINT
                if not chrome_available()
                else "On Streamlit Cloud Chrome is installed via `packages.txt`; if it "
                "still fails, choose the **HTML** format above — it needs no browser."
            )
            detail = str(exc)
            message = f"Could not render {fmt}: {detail}"
            # The renderer's missing-browser exception already contains the
            # actionable hint. Appending it again produced two identical yellow
            # paragraphs in the export panel (EXP-6 review feedback).
            if hint not in detail:
                message += f"\n\n{hint}"
            st.warning(message)
            cache = None
        else:
            cache = {"sig": sig, "data": data, "fmt": fmt}
            st.session_state[cache_key] = cache
        finally:
            st.session_state.pop(inflight_key, None)

    if cache and cache.get("sig") == sig:
        data = cache["data"]
        st.success(f"{fmt} ready · {len(data) / 1024:.0f} KB")
        st.download_button(
            f"⬇ Download {fmt}",
            data=data,
            file_name=f"{file_stem}.{fmt.lower()}",
            mime=_MIME_FOR_FORMAT[fmt],
            key=f"{key_prefix}_save_button",
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


def _render_animation_export(fig, *, file_stem: str, playback_ms: float) -> None:
    """Export the animated scanpath as interactive HTML or a rasterized GIF/MP4.

    HTML is one click (no browser needed to generate, keeps interactivity). GIF and
    MP4 rasterize every frame through Kaleido (headless Chrome) — too slow to run on
    every rerun — so they follow the same Render-then-download pattern as the static
    image export, with a progress bar and a result cached in session state so the
    download button survives reruns (and a re-render isn't needed unless an option
    changes). The clip reproduces the on-screen Play: every frame held for the same
    average duration, so its runtime equals the quoted playback time.
    """
    n_frames = len(fig.frames or ())
    fmt = panel_field(
        st,
        "radio",
        "Export format",
        options=["HTML", "GIF", "MP4"],
        index=0,
        horizontal=True,
        key="anim_export_format",
        help=(
            "HTML keeps the interactive play/slider and needs no browser to "
            "generate. GIF and MP4 are self-playing clips (great for slides or "
            "papers) rendered via Kaleido/Chrome — MP4 is far smaller than GIF."
        ),
    )

    if fmt == "HTML":
        # VIZ-10: the downloaded HTML must autoplay at the configured speed too
        # (Plotly's default auto_play ignores frame_duration), matching the live
        # embed + api.save_figure. Autoplay-off / static figures stay paused.
        autoplay_ms = animation_autoplay_frame_duration(fig)
        if autoplay_ms is not None:
            html = fig.to_html(
                include_plotlyjs="cdn",
                full_html=True,
                auto_play=False,
                post_script=animation_autoplay_post_script(autoplay_ms),
            )
        elif fig.frames:
            html = fig.to_html(include_plotlyjs="cdn", full_html=True, auto_play=False)
        else:
            html = fig.to_html(include_plotlyjs="cdn", full_html=True)
        html_bytes = html.encode("utf-8")
        st.download_button(
            "⬇ Download HTML",
            data=html_bytes,
            file_name=f"{file_stem}.html",
            mime="text/html",
            key="anim_export_html",
            help="Self-contained HTML you can open in any browser; keeps play/slider interactivity.",
        )
        return

    if n_frames == 0:
        st.info("Nothing to animate for this trial.")
        return

    # Pre-flight (ENG-10): GIF/MP4 need Chrome — warn before the user waits on a
    # render that can only fail, and point at the fix + the browser-free HTML.
    if not chrome_available():
        st.warning(f"{fmt} export can't run here. {CHROME_INSTALL_HINT}", icon="⚠️")

    frame_ms = playback_ms / n_frames if n_frames else 16.0
    clip_s = playback_ms / 1000.0

    scale = panel_field(
        st,
        "select_slider",
        "Resolution",
        options=[0.5, 0.75, 1.0, 1.5, 2.0],
        value=1.0,
        format_func=lambda s: f"{s:g}×",
        key="anim_export_scale",
        help="Render scale: 1× matches the on-screen size. Lower is smaller/faster; "
        "higher is crisper/larger.",
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
        help=f"Render at most {_ANIM_FRAME_CAP} frames. This reading has many "
        "fixations; capping them keeps the export quick, and the clip's total "
        "duration is unchanged (each kept frame is held a little longer).",
    ):
        max_frames = _ANIM_FRAME_CAP

    render_frames = min(n_frames, max_frames) if max_frames else n_frames
    est_s = render_frames * _ANIM_RENDER_S_PER_FRAME + _ANIM_RENDER_COLD_START_S
    note = f"{n_frames} frames · clip ≈ {clip_s:.1f}s · ~{est_s:.0f}s to render"
    if render_frames != n_frames:
        note += f" ({render_frames} frames rendered)"
    st.caption(note)
    if fmt == "GIF":
        st.caption(
            "GIF embeds anywhere but is large for long readings — prefer MP4, or "
            "lower the resolution, to shrink the file."
        )

    # Re-render only when an output-affecting input changes; otherwise reuse the
    # cached bytes so the download button persists across reruns. The figure's
    # own JSON fingerprints every visual choice that feeds the clip — trial,
    # playback speed, saccades/order/marker-size/background, true-to-scale text —
    # so toggling any of them invalidates a stale render instead of serving the
    # previous bytes. `scale`/`max_frames` are export-only (not in the figure),
    # so they're keyed separately.
    sig = static_export_signature(
        fig,
        fmt=fmt,
        width=int(fig.layout.width or 900),
        height=int(fig.layout.height or 600),
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
        help="Renders each frame via Kaleido (headless Chrome); the download "
        "appears once it's ready.",
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
                fig,
                fmt=fmt.lower(),
                frame_duration_ms=frame_ms,
                scale=float(scale),
                max_frames=max_frames,
                status_callback=_on_status,
            )
        except AnimationExportError as exc:
            progress_slot.empty()
            st.warning(
                f"Could not render {fmt}: {exc}\n\n"
                "GIF/MP4 export rasterizes each frame with a Chrome/Chromium browser "
                "(Kaleido). On Streamlit Cloud this is installed via `packages.txt`; "
                "if it still fails, use the **HTML** format above — it needs no browser."
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


def _slice_fix_range(fix: pd.DataFrame, fix_range) -> pd.DataFrame:
    """Keep only fixations whose 1-based ``order_in_trial`` is within ``fix_range``.

    ``fix_range`` is the single-trial fixation-index window (VIZ-7) — a
    ``(start, end)`` tuple, or ``None`` for the full trial. Applied only to the
    frame feeding the figure / animation / comparison builders (and thus the
    Current-figure export, which round-trips the on-screen figure), so the chips,
    panels and bulk multi-trial export keep the complete trial. A ``None`` window
    or a frame without ``order_in_trial`` is returned unchanged (the default path
    stays byte-identical)."""
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
    """PRE-3 vertical drift correction for one scanpath, or a true no-op.

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


def _marked_text_column(viz_settings: dict) -> str | None:
    """The critical-span column for builders whose only marking channel is *text*.

    ``make_scanpath_figure`` takes both ``highlight_column`` and
    ``critical_span_style`` and decides internally: "Mark text" recolours the word
    labels, "Mark border" instead draws a box overlay. The animation and
    comparison builders have no overlay layer, so they take ``highlight_column``
    alone — and must be handed ``None`` under any other style, or "Mark border"
    would silently turn into text marking there (VIZ-23)."""
    if viz_settings.get("critical_span_style", "Mark text") != "Mark text":
        return None
    return viz_settings.get("highlight_column", "is_in_aspan")


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
        duration_mass_sigma_chars=viz_settings.get("duration_mass_sigma_chars", 1.0),
        fit_to_monitor=viz_settings.get("fit_to_monitor", True),
        show_coordinate_grid=viz_settings.get("show_coordinate_grid", False),
        coordinate_grid_spacing=viz_settings.get("coordinate_grid_spacing"),
        show_raw_gaze=effective_show_raw_gaze,
        color_by=viz_settings["color_by"],
        heatmap_metric=(
            viz_settings["heatmap_metric"]
            if viz_settings["heatmap_metric"] != "counts"
            else None
        ),
        marker_size_range=viz_settings["marker_size_range"],
        order_font_size=viz_settings["order_font_size"],
        order_font_color=viz_settings["order_font_color"],
        show_colorbars=viz_settings["show_colorbars"],
        fixation_color_range=viz_settings["fixation_color_range"],
        heatmap_range=viz_settings["heatmap_range"],
        fixation_colorscale=viz_settings["fixation_colorscale"],
        heatmap_colorscale=viz_settings["heatmap_colorscale"],
        critical_span_style=viz_settings.get("critical_span_style", "Mark text"),
        highlight_column=viz_settings.get("highlight_column", "is_in_aspan"),
        saccade_color=viz_settings.get("saccade_color", SACCADE_COLOR),
        saccade_style=SACCADE_DASH_OPTIONS.get(
            viz_settings.get("saccade_style", "Solid"), "solid"
        ),
        saccade_width=viz_settings.get("saccade_width", DEFAULT_SACCADE_WIDTH),
        saccade_color_mode=viz_settings.get("saccade_color_mode", "Uniform"),
        saccade_class_colors=viz_settings.get("saccade_class_colors"),
        saccade_type_legend=viz_settings.get("saccade_type_legend", True),
        # VIZ-31: the reading-class filter (None / a full list = draw them all).
        saccade_classes=viz_settings.get("saccade_classes"),
        saccade_render_mode=viz_settings.get("saccade_render_mode", "Straight"),
        fixation_snap_to_word=viz_settings.get("fixation_snap_to_word", False),
        hollow_fixations=viz_settings.get("hollow_fixations", False),
        fixation_opacity=viz_settings.get("fixation_opacity", 1.0),
        fixation_color=viz_settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
        fixation_symbol=viz_settings.get("fixation_symbol", DEFAULT_FIXATION_SYMBOL),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        color_by_line=viz_settings.get("color_by_line", False),
        fixation_flags=viz_settings.get("fixation_flags"),
        span_border_color=viz_settings.get("span_border_color", "#000000"),
        colorbar_orientation=viz_settings.get("colorbar_orientation", "Vertical"),
        colorbar_tickangle=viz_settings.get("colorbar_tickangle", 0),
        colorbar_tickfont_size=viz_settings.get("colorbar_tickfont_size", 12),
        background_color=viz_settings.get("background_color"),
        word_hover_measure=viz_settings.get(
            "word_hover_measure", "total_fixation_duration_ms"
        ),
        word_hover_fields=viz_settings.get("word_hover_fields"),
        fixation_hover_fields=viz_settings.get("fixation_hover_fields"),
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
            parts.append((k, tuple(sorted((str(a), str(b)) for a, b in v.items()))))
        elif isinstance(v, (list, tuple)):
            parts.append((k, tuple(v)))
        else:
            try:
                hash(v)
                parts.append((k, v))
            except TypeError:
                parts.append((k, str(v)))
    return tuple(parts)


@st.cache_data(show_spinner="Rendering scanpath…")
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
    settings reuses the figure instead of rebuilding all its traces/shapes."""
    # UX-37: the single most expensive thing a rerun can do, and invisible from
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
    trial_ids = [str(option[1]) for option in options]
    ordered_ids = sort_trial_options(
        trial_ids,
        key_series,
        descending=descending if key_series is not None else False,
    )
    rank = {trial_id: idx for idx, trial_id in enumerate(ordered_ids)}
    return sorted(options, key=lambda option: rank.get(str(option[1]), len(rank)))


#: CMP-13: scanpath B remembered as ``(participant_id, trial_id)``. The picker's
#: own key holds a *label*, which is rebuilt relative to A every run, so it is
#: not a stable name for a trial — see ``_render_compare_selector``.
_COMPARE_IDENTITY_KEY = "_compare_selected_identity"

#: Key prefix for scanpath B's own filter set (CMP-8 §5.2). Must be one of
#: ``controls.FILTER_PREFIXES`` — that registry is what stops A's "Clear filters"
#: sweeping B's keys along with its own.
#: The trial-filter popover's trigger, on A's row and on B's. A funnel,
#: because the control filters the list rather than searching it; Unicode has
#: no funnel emoji, so this is Streamlit's Material icon.
_FILTER_ICON = ":material/filter_alt:"

_COMPARE_FILTER_PREFIX = "cmp"


def _compare_source_name() -> str | None:
    """The picked comparison dataset, or ``None`` for "This dataset".

    Read straight from the widget key rather than from a loaded source, because
    the rail's ⚙️ Compare options popover renders *before* the picker runs and
    still has to gate the Overlay layout (§5.3).
    """
    chosen = st.session_state.get(COMPARE_SOURCE_KEY)
    return None if not chosen or chosen == THIS_DATASET else str(chosen)


#: CMP-8 §5.2's filter result with nothing selected — the pool as it comes.
#: Used for the one run where B's stored filter result belongs to the dataset
#: the user just switched *away* from (see ``_resolve_compare_source``).
_NO_COMPARE_NARROWING: dict = {"participants": None, "metadata": {}, "ranges": {}}

#: The comparison dataset the last run resolved, so a switch can be told from a
#: re-render. Not a widget key — the picker's own key is the user's *pick*, and
#: this is what was actually loaded and filtered against.
_COMPARE_SOURCE_RESOLVED_KEY = "_compare_source_resolved"


def _compare_source_choices() -> tuple[list[str], dict[str, bool], dict[str, str]]:
    """The **Compare with** options: every dataset scanpath B could come from.

    Split out of the picker by UX-64. B's controls are one line now, and a line
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


def _resolve_compare_source(
    ready_by_name: dict[str, bool], reason_by_name: dict[str, str]
) -> tuple[SecondaryDataset | None, str]:
    """Load scanpath B's dataset (**CMP-8 §5.1**), narrowed by its own filters.

    Returns ``(source, notice)``. ``source`` is ``None`` for "This dataset" — the
    pre-CMP-8 behaviour, where B comes out of A's pool — and also for a source
    that is offered but not loadable (a public corpus whose location has never
    been set), in which case ``notice`` says why: silently falling back would
    look like the picker was ignored.

    §5.2's filters are **read from session state** rather than taken from the
    widgets, which now render inside this row's filter popover (UX-64) instead of
    above it. That is the same contract A has — ``render_trial_filters`` stashes
    its result, and every widget's ``on_change`` recomputes the stash before the
    rerun, so a filter change still applies on the run it happens.
    """
    chosen = str(st.session_state.get(COMPARE_SOURCE_KEY) or THIS_DATASET)
    if chosen == THIS_DATASET:
        return None, ""
    if not ready_by_name.get(chosen, False):
        return None, f"⚠️ {reason_by_name.get(chosen, '')}"
    source = load_secondary_dataset(chosen)
    if source is None:
        return None, f"⚠️ Couldn't load **{chosen}** as a comparison dataset."
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
    """The **Compare with** selectbox — B's line's leading cell (UX-64).

    Sits under A's dataset picker, on the same grid track, so the two control
    lines read down the page as *which dataset → which trial → scrub → act*.
    """
    # Lazy, like every other `app` reach from this module: app imports tabs, so
    # a module-level import would close the cycle.
    from scanpath_studio.app import mark_wip_if_benchmark as _mark_wip_if_benchmark

    host.selectbox(
        "**Compare with**",
        options=names,
        key=COMPARE_SOURCE_KEY,
        # ENG-36: this widget renders only in Compare mode on the Scanpath view,
        # and its key is deep-link-seeded (`?cmp_source=`). Without this, one
        # trip through Corpus Analysis prunes the key and the link's choice is
        # silently lost.
        persist_state="session",
        # Streamlit has no per-option disabling, so an unready corpus is marked
        # in the label and explains itself below once picked — offered but
        # honest, rather than absent and mysterious.
        format_func=lambda name: (
            _mark_wip_if_benchmark(name)
            if ready_by_name.get(name, True)
            else f"{_mark_wip_if_benchmark(name)} (needs setup)"
        ),
        help="Choose dataset and trial B. 📄 marks the same text; 👤 marks the "
        "same participant. Other datasets keep their own screen geometry.",
    )


def _render_compare_filters(host, source: SecondaryDataset) -> None:
    """Every way to narrow **B's** pool, behind one funnel — A's popover, for B.

    §5.2's *Filter B by* row and its **More** popover were two controls on a row
    of their own; UX-64 folded them into the one icon that closes B's line, so
    both lines end in the same cluster. The widgets and their ``cmp`` prefix are
    unchanged — only where they render is.
    """
    pop = host.popover(
        _FILTER_ICON, width="content", help=f"Filter {source.name}'s trials"
    )
    box = pop.container(key="cmp_narrow_by")
    box.caption(f"Narrow **{source.name}** — scanpath B only.")
    render_narrow_by(
        source.words,
        source.fixations,
        prefix=_COMPARE_FILTER_PREFIX,
        text_host=box,
        part_host=box,
    )
    render_trial_filters(
        source.words,
        source.fixations,
        prefix=_COMPARE_FILTER_PREFIX,
        host=box,
    )


def _narrow_secondary(
    source: SecondaryDataset, filters: dict, *, use_annotations: bool = False
) -> SecondaryDataset:
    """Apply B's own (``cmp``-prefixed) trial filters to a comparison source.

    Annotation filters apply only when ``use_annotations`` is true. Favorites
    and tags belong to the active dataset, so the same-dataset B pool can use
    them; a different corpus must never inherit matching-looking ids.
    """
    words, fixations = filter_trials(
        source.words,
        source.fixations,
        participants=filters["participants"],
        metadata=filters["metadata"],
        ranges=filters.get("ranges"),
    )
    selected_keys = filters.get("trial_keys")
    if selected_keys is not None:
        words, fixations = filter_to_keys(words, fixations, set(selected_keys))
    if use_annotations and (
        filters.get("favorites_only")
        or filters.get("required_tags")
        or filters.get("excluded_tags")
    ):
        present = trial_keys(words) | trial_keys(fixations)
        kept = set(
            filter_keys(
                list(present),
                favorites_only=bool(filters.get("favorites_only")),
                required_tags=list(filters.get("required_tags") or []),
                excluded_tags=list(filters.get("excluded_tags") or []),
            )
        )
        words, fixations = filter_to_keys(words, fixations, kept)
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
    trial_words: pd.DataFrame | None = None,
    words_filtered: pd.DataFrame | None = None,
    combos_all: pd.DataFrame | None = None,
    words_all: pd.DataFrame | None = None,
    fixations_all: pd.DataFrame | None = None,
) -> tuple[
    str | None,
    str | None,
    SecondaryDataset | None,
    SecondaryDataset | None,
]:
    """The compare-trial (B) selector, rendered above the chips (CMP-1).

    Mirrors the main trial picker: a ``selectbox`` showing the trial id (+ 📄/👤
    markers) and a scrubbing ``select_slider`` showing ``"index/TOTAL · <trial
    id>"``, plus ◀ ▶ step buttons and a CMP-6 sort picker. The sort picker uses
    the main trial picker's generated choices; only its default differs, keeping
    same-text trials first, then same-participant trials, then the rest. The
    overlay layout + A/B-legend config live in the rail's **⚙️ Compare** popover
    (under the Compare toggle).

    **CMP-8 §5.1** put a *dataset* picker above it: B may come from a different
    corpus entirely, in which case the candidate pool, the narrow-by filters and
    the screen geometry are all that dataset's own. Returns
    ``(participant, trial, source, pool)`` — ``source`` is ``None`` for the
    same-dataset case, while ``pool`` always carries the independently filtered
    B frames from which the selected trial must be extracted.

    **UX-64** made that one line rather than three: B's row is now A's row —
    ``[Compare with] [Compare To] [scrub slider] [◀ ▶ ⇅ filter]`` on the same
    ``SELECTOR_ROW_GRID`` — instead of a dataset row, a *Filter B by* row and a
    picker row stacked above the chips. The dataset is therefore resolved from
    session state *before* the row is drawn (``_resolve_compare_source``), since
    how many candidates B has is what decides whether the row has a slider."""
    names, ready_by_name, reason_by_name = _compare_source_choices()
    source, source_notice = _resolve_compare_source(ready_by_name, reason_by_name)
    filter_source = source
    comparison_pool = source
    if source is not None:
        # B's pool is its own dataset, narrowed by its own filters (§5.2), and
        # nothing about A applies to it — including the multipart screen scoping
        # below, which asks whether *this* corpus' trials share A's screen id.
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
        trial_words = None
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
        )
        same_filters = read_trial_filters(_COMPARE_FILTER_PREFIX)
        if st.session_state.get(_COMPARE_SOURCE_RESOLVED_KEY) != THIS_DATASET:
            same_filters = dict(_NO_COMPARE_NARROWING)
        st.session_state[_COMPARE_SOURCE_RESOLVED_KEY] = THIS_DATASET
        narrowed = _narrow_secondary(filter_source, same_filters, use_annotations=True)
        comparison_pool = narrowed
        combos = narrowed.combos
        words_filtered = narrowed.words
        fixations_filtered = narrowed.fixations
        options = build_comparison_options(
            combos, selection_mode, selected_participant, selected_trial, selected_text
        )
    active_screen = None
    if (
        trial_words is not None
        and not trial_words.empty
        and SCREEN_ID in trial_words.columns
    ):
        active_screen = str(trial_words[SCREEN_ID].iloc[0])
        screen_source = (
            fixations_filtered
            if fixations_filtered is not None
            and not fixations_filtered.empty
            and SCREEN_ID in fixations_filtered.columns
            else words_filtered
        )
        if (
            screen_source is None
            or screen_source.empty
            or SCREEN_ID not in screen_source.columns
        ):
            options = []
        else:
            candidates_with_screen = set(
                map(
                    tuple,
                    screen_source.loc[
                        screen_source[SCREEN_ID].astype(str) == active_screen,
                        ["participant_id", "trial_id"],
                    ]
                    .astype(str)
                    .drop_duplicates()
                    .to_numpy(),
                )
            )
            options = [
                option
                for option in options
                if (str(option[0]), str(option[1])) in candidates_with_screen
            ]
            if (
                fixations_filtered is not None
                and SCREEN_ID in fixations_filtered.columns
            ):
                fixations_filtered = fixations_filtered[
                    fixations_filtered[SCREEN_ID].astype(str) == active_screen
                ]
    # UX-64 — ONE row for scanpath B, the mirror of A's above it:
    # `[Compare with] [Compare To] [scrub slider] [◀ ▶ ⇅ filter]` on the same
    # `SELECTOR_ROW_GRID`, replacing the dataset row + *Filter B by* row + picker
    # row this used to stack above the chips. The dataset keeps a track of its
    # own and does not shrink — the label is what tells two compared corpora
    # apart — and a one-candidate pool drops the slider exactly as A's row does
    # (`st.select_slider` throws on a single option — BUG-23).
    #
    # Built BEFORE the "no candidates" notice below, so the dataset picker and
    # the filters that emptied the pool are still on screen to undo it.
    n = len(options)
    slider_col = None
    if n > 1:
        lead_col, sel_col, slider_col, trail_col = st.columns(
            SELECTOR_ROW_GRID, vertical_alignment="bottom"
        )
    else:
        lead_col, sel_col, trail_col = st.columns(
            SELECTOR_ROW_TRIO, vertical_alignment="bottom"
        )
    _render_compare_dataset_cell(lead_col, names, ready_by_name)
    trail = trail_col.container(key="railbtn_single_compare_trail")
    # CMP-6: candidate sorting is visually LAST in the row, after the step
    # buttons. It still executes before the selectbox/slider below, so a change
    # applies to their list on the same run. CMP-10 mirrors the main trial
    # picker: ◀ / ▶ / ⇅ share one right-packed `railbtn_*` pill cluster instead
    # of occupying three independent columns — UX-64 adds the filter to the
    # same cluster.
    # The sort is UI-only: it never travels in a deep link or saved config (same
    # call as `share_identity_mode`, DATA-16/S3).
    step_col = sort_col = None
    if n > 1:
        # Created in display order, then filled out of order: the ordering
        # popover has to run first because its result is the list the selectbox,
        # the slider and the ◀ ▶ steps all walk.
        step_col = trail.container(key="railbtn_single_compare_step")
        sort_col = trail.container(key="railbtn_single_compare_sort")
    # B always has its own filter set. For "This dataset" it starts from the
    # unfiltered active frames, so narrowing B never changes scanpath A.
    if filter_source is not None:
        _render_compare_filters(
            trail.container(key="railbtn_single_compare_filter"), filter_source
        )
    if source_notice:
        st.caption(source_notice)
    if not options:
        if source_notice:
            pass
        elif source is not None:
            st.info(f"No trials in **{source.name}** match its filters.")
        else:
            st.info(
                "No other trials match B's filters on this screen."
                if active_screen
                else "No other trials match B's filters."
            )
        return None, None, None, None

    sort_keys = trial_sort_keys(
        combos,
        "trial_id",
        words=words_filtered,
        fixations=fixations_filtered,
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
        with sort_col.popover("⇅", width="content", help="Sort the comparison trials"):
            sort_choice = _labeled(
                st,
                "selectbox",
                "Sort trials by",
                options=sort_options,
                key="single_compare_order",
                help="The default keeps related readings together: same text, then "
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
            # CMP-13 (follow-up: "still jumps around"). The default order is
            # computed *relative to A* — 📄 same-text candidates lead — so the
            # moment A crosses into another text, B's whole pool re-ranks and its
            # position readout leaps (10/23 → 22/23 in the report) even though
            # the linked step landed on exactly the right trial. Walking two
            # trials in lockstep only means anything against a track that holds
            # still, so linking pins the order to Trial ID for as long as it is
            # on. Resolved into a local, never written back to the widget key:
            # the user's chosen sort must survive un-linking (the same
            # don't-rewrite-a-gated-setting rule as `controls._mode_gate`).
            if compare_step_linked() and sort_choice == _CMP_SORT_DEFAULT:
                order_choice = TRIAL_SORT_DEFAULT
                st.caption(
                    "Sorted by **Trial ID** while *Step A + B* is on, so B keeps "
                    "its place in the list when A changes text."
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
    label_to_id = {opt[2]: str(opt[1]) for opt in options}

    sel_key = "single_compare_trial"
    pos_key = "single_compare_pos"
    identity_to_label = {(str(opt[0]), str(opt[1])): opt[2] for opt in options}
    # CMP-8 §7: a `?compare=<pid>:<trial>` deep link parked its ids in
    # `_apply_url_preset`; the labels only exist here, so this is where it lands.
    # Consumed once, and only when the pool can actually answer it — a request
    # for a trial the current filters exclude is dropped rather than left to
    # re-point the picker after some later filter change (the ENG-36 rule).
    pending = st.session_state.pop(PENDING_COMPARE_STATE_KEY, None)
    if isinstance(pending, dict):
        wanted = (str(pending.get("participant_id")), str(pending.get("trial_id")))
        if wanted in identity_to_label:
            st.session_state[sel_key] = identity_to_label[wanted]

    # CMP-13 (the "B suddenly skips to a different trial" report): the widget key
    # holds a *label*, and the labels are rebuilt relative to A — the 📄 same-text
    # and 👤 same-participant markers are computed against the selected trial. So
    # the moment A moves to a different text, B's stored label names nothing in
    # the new list and the picker used to silently fall back to the first
    # candidate. It happened on *any* A step, linked or not, which is why it read
    # as "at some point, not clear why".
    #
    # The fix is to remember B by identity and re-resolve its label each run.
    # Order matters: the user's live pick (a label that is still valid) wins over
    # the remembered identity, or selecting a new B would be undone by the
    # previous one on the very next run.
    current = st.session_state.get(sel_key)
    lost_identity = None
    if current not in labels:
        remembered = st.session_state.get(_COMPARE_IDENTITY_KEY)
        if isinstance(remembered, tuple) and remembered in identity_to_label:
            current = identity_to_label[remembered]
        elif remembered is not None and current is not None:
            # Genuinely gone from the pool — most often because A just moved
            # *onto* it, and a trial is never a candidate to compare with
            # itself. Say so rather than swapping the panel silently.
            lost_identity = remembered
            current = labels[0]
        else:
            current = labels[0]
        st.session_state[sel_key] = current
    st.session_state[_COMPARE_IDENTITY_KEY] = tuple(
        str(v) for v in label_to_trial[current]
    )
    if lost_identity is not None:
        st.caption(
            f"`{lost_identity[1]}` is no longer available to compare with — "
            "it is the selected trial now. Showing the first candidate instead."
        )

    # CMP-13: publish the candidates as rendered — label plus identity, because
    # the labels are rebuilt relative to A and only the identity survives A moving.
    st.session_state[COMPARE_OPTIONS_SNAPSHOT_KEY] = [
        (opt[2], str(opt[0]), str(opt[1])) for opt in options
    ]

    if n > 1:
        idx_of = {lbl: i for i, lbl in enumerate(labels)}
        # Mirror the slider to the current selection before it renders.
        st.session_state[pos_key] = current

        def _on_compare_slider() -> None:
            st.session_state[sel_key] = st.session_state[pos_key]

        def _step_compare(delta: int) -> None:
            step_within(labels, sel_key, delta)
            # CMP-13: the link works in both directions — B's ◀ ▶ move A too.
            # A's ids are stable (they don't depend on B), so this steps A's
            # canonical key straight from the list its picker last rendered.
            if compare_step_linked():
                step_within(
                    st.session_state.get(trial_options_snapshot_key("single")) or [],
                    "single_trial_id",
                    delta,
                )

        current_idx = labels.index(current)

    selected_compare_label = sel_col.selectbox(
        "Compare trial",
        options=labels,
        key=sel_key,
        label_visibility="collapsed",
    )
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
                help=f"Scrub through the {n} candidate trials.",
            )
        # CMP-13: mirror of the main picker — linked, a button dies only when
        # *both* lists have run out.
        linked = compare_step_linked()
        primary_options = (
            st.session_state.get(trial_options_snapshot_key("single")) or []
            if linked
            else []
        )
        step_help = " Linked: also steps the main trial." if linked else ""
        step_col.button(
            "◀",
            key="single_compare_prev",
            on_click=_step_compare,
            args=(-1,),
            disabled=current_idx == 0
            and (not linked or at_list_end(primary_options, "single_trial_id", -1)),
            help="Previous candidate." + step_help,
        )
        step_col.button(
            "▶",
            key="single_compare_next",
            on_click=_step_compare,
            args=(1,),
            disabled=current_idx == n - 1
            and (not linked or at_list_end(primary_options, "single_trial_id", 1)),
            help="Next candidate." + step_help,
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

# Friendly labels + fixed span colours for the known OneStop stimulus/question
# columns, so the OneStop experience is unchanged while the panel still works on
# arbitrary datasets (unknown columns get a humanized name + a palette colour).
_STIMULUS_FIELD_LABELS = {
    "question": "Question",
    "question_preview": "Question preview",
    "selected_answer": "Selected answer",
    "is_correct": "Correct",
    "is_in_aspan": "Answer (critical) span",
    "is_in_dspan": "Distractor span",
}
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


def _humanize_field(col: str) -> str:
    """Friendly display label for a stimulus/question column."""
    return _STIMULUS_FIELD_LABELS.get(col, col.replace("_", " ").strip().capitalize())


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


def _detect_span_columns(trial_words: pd.DataFrame) -> list[str]:
    """Per-word boolean columns that mark a highlightable span (generic).

    Known OneStop spans (``is_in_aspan``/``is_in_dspan``) come first so they keep
    their fixed colours; any further span-like boolean columns follow.
    """
    detected = [
        c
        for c in trial_words.columns
        if any(h in c.lower() for h in _SPAN_NAME_HINTS)
        and _is_boolish(trial_words[c])
        and bool(trial_words[c].fillna(False).astype(bool).any())
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
    plain numeric columns (UX-32): an automatically detected context field is
    text or boolean, so
    an unrelated numeric column that merely matches a name hint — e.g. a
    ``response_time_ms`` timing column on a generic upload — would otherwise
    render as a bogus "Response time ms: 120" line.
    """
    out = []
    for c in trial_words.columns:
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


#: Columns the Stimulus & Context field picker never offers (UX-32): the
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
#: for the deep link / CLI / headless API to carry (see the note on UX-32).
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
    so uncached it was ~15× what the two name-hint detectors it replaced cost.
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
    conservative (it is what produced the `response_time_ms` false positive), but
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
    for col in trial_words.columns:
        if col in _STIMULUS_FIELD_EXCLUDE:
            continue
        series = trial_words[col]
        varies = series.dropna().nunique() > 1
        if _is_boolish(series) and bool(series.fillna(False).astype(bool).any()):
            (spans if varies else qa).append(col)
        elif not varies:
            qa.append(col)
    return spans, qa


def _stimulus_fields(trial_words: pd.DataFrame) -> tuple[list[str], list[str]]:
    """The span + Q&A columns to render, honouring the user's picks (UX-32).

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

    UX-32 asked whether this panel is still effectively OneStop-specific. The
    honest answer was "generic when the column *names* cooperate" — a corpus
    whose critical span is called `focus_region`, or whose question column is
    `q_text`, got nothing. This is the escape hatch: name hints pick the
    defaults, and anything they miss (or wrongly include) is one click away.

    Takes the option pools rather than the frame: `_stimulus_fields` has already
    derived them for this run, and re-deriving here scanned the words frame a
    second time on every rerun.
    """
    if not span_options and not qa_options:
        return
    with host.popover("⚙️ Fields", width="content"):
        st.caption(
            "Which of this dataset's columns the panel highlights and lists. "
            "Detected by name to begin with — change them here when the naming "
            "doesn't match, or to add a field the detection skipped."
        )
        if span_options:
            labeled(
                st,
                "multiselect",
                "Highlighted spans",
                options=span_options,
                key=_STIMULUS_SPAN_KEY,
                persist_state="session",
                help="Per-word true/false columns. Each selected one tints its "
                "words in the stimulus text and gets a summary line below it.",
            )
        if qa_options:
            labeled(
                st,
                "multiselect",
                "Context fields",
                options=qa_options,
                key=_STIMULUS_QA_KEY,
                persist_state="session",
                help="Trial-level context such as a title, instruction, question, "
                "or answer.",
            )


def _render_comprehension_questions(trial_words: pd.DataFrame) -> None:
    """Render structured comprehension questions for the trial's stimulus.

    Parses the ``comprehension_questions`` JSON column (MultiplEYE) into a list of
    questions, each with the target (✓ reference answer) and distractors. The
    corpus records no per-reader answer, so the target is shown as the key only —
    not as a 'selected'/'correct' result. No-op when the column is absent or the
    JSON is empty/malformed."""
    raw = _first_str(trial_words, "comprehension_questions")
    if not raw:
        return
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return
    if not items:
        return
    st.markdown("**Comprehension questions**")
    for i, q in enumerate(items, 1):
        head = f"**Q{q.get('question_no') or i}**"
        cond = (q.get("condition") or "").strip()
        if cond and cond.lower() != "nan":
            head += f" · _{cond}_"
        st.markdown(f"{head}: {q.get('question', '')}")
        options = []
        target = (q.get("target") or "").strip()
        if target:
            options.append(f"- ✓ {target}")
        options += [f"- {d}" for d in q.get("distractors", []) if d]
        if options:
            st.markdown("\n".join(options))


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
    active = [c for c in span_bg if c in ordered.columns]
    if not active:
        st.write(" ".join(ordered["text"].astype(str).tolist()))
        return
    import html as _html

    texts = ordered["text"].astype(str).tolist()
    masks = {c: ordered[c].fillna(False).astype(bool).tolist() for c in active}
    parts: list[str] = []
    for i, raw_word in enumerate(texts):
        word = _html.escape(raw_word)
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
    mask = ordered[mask_col].fillna(False).astype(bool)
    return " ".join(ordered.loc[mask, "text"].astype(str).tolist())


def _first_str(df: pd.DataFrame, col: str) -> str | None:
    """First non-null value of ``col`` as a string, or None."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            return str(vals.iloc[0])
    return None


def _first_num(df: pd.DataFrame, col: str) -> float | None:
    """First non-null value of ``col`` as a float, or None when absent/empty."""
    if col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if not vals.empty:
            return float(vals.iloc[0])
    return None


def _first_bool(df: pd.DataFrame, col: str) -> bool | None:
    """First non-null value of ``col`` as a bool, or None when absent/empty."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            return bool(vals.iloc[0])
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
    span_words = trial_words[trial_words[mask_col].fillna(False).astype(bool)]
    if span_words.empty:
        return ""
    from scanpath_studio.measures import fixation_in_text_mask

    mask = fixation_in_text_mask(trial_fixations, span_words)
    n = int(mask.sum())
    if n == 0:
        return ' <span style="color:#dc3545;">— not fixated</span>'
    dwell = float(pd.to_numeric(trial_fixations.loc[mask, "duration_ms"]).sum())
    return f' <span style="color:#198754;">— {n} fixations, {dwell:.0f} ms</span>'


def _render_trial_header(
    participant: str,
    trial_id: str,
    trial_words: pd.DataFrame,
    prefix: str = "Trial:",
) -> None:
    """Render the trial id header with participant + text id stacked below it.

    The paragraph text / question / spans live in
    `_render_paragraph_panel` so they can sit under the figure (single tab)
    while the header stays in the side panel.
    """
    lines = [f"**{prefix}** `{trial_id}`", f"Participant: `{participant}`"]
    # The text/passage id may live under its canonical name or a pre-rename
    # source name (unique_paragraph_id etc.), which can also double as a composite
    # component — recognise all of them so the line reads "Text:" either way.
    text_cols = ("unique_text_id", "text_id", "unique_paragraph_id", "paragraph_id")
    text_id = None
    for col in text_cols:
        if col in trial_words.columns and not trial_words.empty:
            value = trial_words[col].iloc[0]
            if pd.notna(value):
                text_id = value
                break
    if text_id is not None:
        lines.append(f"Text: `{text_id}`")
    # When the trial id was composed from several columns, surface its remaining
    # parts on their own labeled lines too — the same way Participant and Text
    # are shown — so the opaque `a_b_c` id is spelled out. Participant and the
    # paragraph/text column are already covered above, so they're skipped.
    composite_cols = st.session_state.get("_composite_trial_columns") or []
    already_shown = {"participant_id", *text_cols}
    for col in composite_cols:
        if col in already_shown or col not in trial_words.columns or trial_words.empty:
            continue
        value = trial_words[col].iloc[0]
        if pd.notna(value):
            lines.append(f"{col.replace('_', ' ').capitalize()}: `{value}`")
    # Participant and Text sit on their own lines under the trial id (a markdown
    # hard line break is two trailing spaces + newline).
    st.markdown("  \n".join(lines))


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
    and span colours, so the OneStop view is unchanged. Each span is annotated
    with whether it was fixated when ``trial_fixations`` is given. Skips silently
    when no word text is available. ``bare=True`` drops the expander wrapper so
    the panel can sit directly inside a subtab."""
    if "text" not in trial_words.columns or trial_words.empty:
        return
    # UX-32: the name-hint detection supplies the defaults; the ⚙️ Fields popover
    # is what lets a corpus whose columns are named differently use the panel.
    span_cols, qa_cols, span_options, qa_options = _stimulus_fields(trial_words)
    span_bg = {c: _span_bg_for(c, i) for i, c in enumerate(span_cols)}

    container = (
        st.container() if bare else st.expander("Stimulus & Context", expanded=expanded)
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
        question_cols = [c for c in qa_cols if "question" in c.lower()]
        for col in question_cols:
            val = _first_str(trial_words, col)
            if val:
                st.markdown(f"**{_humanize_field(col)}:** {val}")

        rendered = set(question_cols)
        if "selected_answer" in qa_cols and "is_correct" in qa_cols:
            answer_val = _first_str(trial_words, "selected_answer")
            correct = _first_bool(trial_words, "is_correct")
            if answer_val or correct is not None:
                bits = []
                if answer_val:
                    bits.append(f"selected **{answer_val}**")
                if correct is not None:
                    bits.append(":green[✓ correct]" if correct else ":red[✗ incorrect]")
                st.markdown("**Answer:** " + " · ".join(bits))
            rendered.update({"selected_answer", "is_correct"})

        # Any remaining detected answer/correct columns, rendered generically.
        for col in qa_cols:
            if col in rendered:
                continue
            bval = _first_bool(trial_words, col) if "correct" in col.lower() else None
            if bval is not None:
                mark = ":green[✓ yes]" if bval else ":red[✗ no]"
                st.markdown(f"**{_humanize_field(col)}:** " + mark)
            else:
                val = _first_str(trial_words, col)
                if val:
                    st.markdown(f"**{_humanize_field(col)}:** {val}")

        # Each highlighted span's text + (optional) fixation note.
        for col in span_cols:
            span_str = _span_text(trial_words, col)
            if not span_str:
                continue
            note = _span_fixated_note(trial_words, trial_fixations, col)
            st.markdown(
                _span_summary_html(col, span_str, span_bg[col], note),
                unsafe_allow_html=True,
            )


def _span_summary_html(col: str, span_str: str, bg: str, note: str) -> str:
    """Markup for one "<span label>: <span text>" line in the stimulus panel.

    Split out of ``_render_paragraph_panel`` so the escaping is testable without
    a Streamlit runtime. Both data-derived values — the column name and the
    stimulus text joined out of the words table — are HTML-escaped (S7): this
    goes through ``unsafe_allow_html=True`` and Streamlit's markdown path runs
    no sanitizer, so a corpus containing markup would otherwise inject it into
    the page. ``note`` is tool-generated markup and ``bg`` comes from the fixed
    ``_SPAN_BG_PALETTE``, so both stay raw.
    """
    return (
        f'<span style="background-color:{bg};'
        f'color:{_HIGHLIGHT_TEXT_COLOR};padding:0 4px;border-radius:2px;">'
        f"<b>{html.escape(_humanize_field(col))}:</b></span> "
        f"{html.escape(span_str)}{note}"
    )


def _in_text_fixation_value(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> str | None:
    """Concise "in / total" count of fixations that landed inside a word box.

    Replaces the old free-text caption ("All 154 fixations landed inside word
    boxes.") with a compact value for the trial summary table. Returns None when
    there's nothing to count."""
    if trial_words.empty or trial_fixations.empty:
        return None
    from scanpath_studio.measures import fixation_in_text_mask

    mask = fixation_in_text_mask(trial_fixations, trial_words)
    n_total = len(mask)
    if n_total == 0:
        return None
    n_in = int(mask.sum())
    return f"{n_in} / {n_total}"


def _summary_rows(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> list[dict]:
    """Field/Value rows summarising a trial — totals + in-text fixation count.

    Folded into the metadata table (formerly the three `st.metric` cards plus
    the out-of-text caption), so a trial's headline numbers live in one place."""
    stats = compute_trial_stats(trial_words, trial_fixations)
    rows = [
        {
            "Field": "Total reading time (s)",
            "Value": f"{stats['total_reading_time_s']:.1f}",
        },
        {"Field": "Number of words", "Value": f"{stats['word_count']:,}"},
        {"Field": "Number of fixations", "Value": f"{stats['fixation_count']:,}"},
    ]
    in_text = _in_text_fixation_value(trial_words, trial_fixations)
    if in_text is not None:
        rows.append({"Field": "Fixations in word boxes", "Value": in_text})
    return rows


# Row-wise palette for the trial-metadata table. Picked light so the text
# stays readable. `is_correct` keeps the row background neutral but tints
# the value text green/red — adding a background there clashed with the
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
    annotation_records: list,
    column_mapping: dict,
    data_source: str | None,
    app_version: str,
    exported_at: str,
    compare_styles: list | None = None,
) -> dict:
    """Build the "💾 Save & restore" JSON config dict (pure — no Streamlit).

    Schema 2 captures the full figure configuration (layers, colouring, sizing,
    text/highlighting, canvas, axes, trial selection), every per-trial
    annotation, and provenance (app version, export date, data source, column
    mapping)."""
    # ENG-11: PLOT_CONFIG_SCHEMA is the single source of truth for the version;
    # bump it (+ register a migration) in url_state when this layout changes.
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

    def _setup_provenance_section() -> dict:
        # Lazy import: `wizard` imports `tabs._collect_column_mapping`, so a
        # module-level import here would close the cycle.
        from scanpath_studio.app import active_setup_snapshot

        snapshot = active_setup_snapshot()
        if snapshot is None:
            return {}
        return {"provenance": {g: str(p) for g, p in snapshot.provenance.items()}}

    return {
        # schema 2 = config + annotations + text/highlighting + provenance;
        # schema 1 (plot config only) still restores via the same reader.
        "schema": PLOT_CONFIG_SCHEMA,
        "app": {"name": "Scanpath Studio", "version": app_version},
        # When this config was saved (ISO 8601, local time) — provenance only,
        # surfaced when restoring (sidebar + the upload wizard's restore step).
        "exported_at": exported_at,
        "data_source": data_source,
        "column_mapping": column_mapping,
        "selection": {
            "participant_id": selected_participant,
            "trial_id": selected_trial,
            **(
                {"screen_id": str(st.session_state["single_screen_id"])}
                if st.session_state.get("single_screen_id") not in (None, "")
                else {}
            ),
        },
        "canvas_px": {"width": int(canvas_width), "height": int(canvas_height)},
        "experimental_setup": {
            "monitor_width_mm": float(
                st.session_state.get("global_monitor_width_mm", 597.0)
            ),
            "viewing_distance_mm": float(
                st.session_state.get("global_viewing_distance_mm", 800.0)
            ),
            "display_dpi": float(st.session_state.get("global_display_dpi", 96.0)),
            "stimulus_font_pt": float(
                st.session_state.get("global_stimulus_font_pt", 12.0)
            ),
            "use_stimulus_font_pt": bool(
                st.session_state.get("global_use_stimulus_font_pt", False)
            ),
            # DATA-22 §7 surface 3: how each group came to be known. Additive, so
            # per ENG-11 this is a documented no-op migration and
            # PLOT_CONFIG_SCHEMA stays put. Absent when the active source never
            # declared a setup — an omitted key reads as "unknown", which is
            # true; writing "assumed" there would invent a claim.
            **_setup_provenance_section(),
        },
        "axes": {
            "x_field": x_field,
            "y_field": y_field,
            "coordinate_grid": bool(figure_settings.get("show_coordinate_grid", False)),
            "coordinate_grid_auto": bool(
                viz_settings.get("coordinate_grid_auto", True)
            ),
            "coordinate_grid_spacing": float(
                st.session_state.get("global_coordinate_grid_spacing", 100.0)
            ),
        },
        "layers": {
            "words": figure_settings["show_words"],
            "word_labels": figure_settings["show_word_labels"],
            "fixations": figure_settings["show_fixations"],
            "order_labels": figure_settings["show_order"],
            "saccades": figure_settings["show_saccades"],
            "saccade_arrows": figure_settings.get("show_saccade_arrows", False),
            "heatmap": figure_settings["show_heatmap"],
            "raw_gaze": figure_settings["show_raw_gaze"],
            "stimulus_image": viz_settings.get("show_stimulus_image", False),
            "full_monitor": figure_settings.get("fit_to_monitor", True),
            # VIZ-10: autoplay the animated replay on load.
            "autoplay": bool(viz_settings.get("anim_autoplay", True)),
        },
        "illustration": {
            "label_mode": viz_settings.get("illustration_label", "Auto"),
            "reasons": list(viz_settings.get("illustration_reasons") or []),
        },
        "preprocessing": {
            "enabled": bool(st.session_state.get("global_preproc_enabled", False)),
            "short_policy": st.session_state.get("global_preproc_short_policy", "Off"),
            "short_threshold_ms": float(
                st.session_state.get("global_preproc_short_threshold_ms", 80.0)
            ),
            "merge_distance_chars": float(
                st.session_state.get("global_preproc_merge_distance_chars", 1.0)
            ),
            "discard_blink_adjacent": bool(
                st.session_state.get("global_preproc_blink_adjacent", True)
            ),
        },
        # VIZ-11 follow-up: the animation frame grid, so a restored config
        # reproduces the same smoothness / export size.
        "animation": {
            "grid_step_ms": int(viz_settings.get("anim_grid_step_ms", 100) or 100),
            "max_frames": int(viz_settings.get("anim_max_frames", 360) or 360),
        },
        "coloring": {
            "color_by": figure_settings["color_by"],
            "heatmap_metric": viz_settings["heatmap_metric"],
            "heatmap_style": figure_settings.get("heatmap_style", "Word boxes"),
            "duration_mass_sigma_chars": float(
                viz_settings.get("duration_mass_sigma_chars", 1.0)
            ),
            "heatmap_norm": figure_settings.get("heatmap_norm", "Linear"),
            "show_colorbars": figure_settings["show_colorbars"],
            "fixation_range": (
                list(figure_settings["fixation_color_range"])
                if figure_settings["fixation_color_range"]
                else None
            ),
            "heatmap_range": (
                list(figure_settings["heatmap_range"])
                if figure_settings["heatmap_range"]
                else None
            ),
            "fixation_colorscale": figure_settings["fixation_colorscale"],
            "heatmap_colorscale": figure_settings["heatmap_colorscale"],
            "saccade_color": figure_settings.get("saccade_color", SACCADE_COLOR),
            "saccade_style": viz_settings.get("saccade_style", "Solid"),
            "saccade_width": float(
                viz_settings.get("saccade_width", DEFAULT_SACCADE_WIDTH)
            ),
            # VIZ-8: colour-by-reading-type mode + per-class palette + legend.
            "saccade_color_mode": viz_settings.get("saccade_color_mode", "Uniform"),
            "saccade_type_legend": bool(viz_settings.get("saccade_type_legend", True)),
            "saccade_class_colors": dict(
                viz_settings.get("saccade_class_colors") or {}
            ),
            # VIZ-31: the reading-class filter (which classes are drawn at all).
            "saccade_classes": list(
                viz_settings.get("saccade_classes") or SACCADE_CLASS_ORDER
            ),
            # VIZ-9: linear-reading mode (arced saccades + snap fixations).
            "saccade_render_mode": viz_settings.get("saccade_render_mode", "Straight"),
            "fixation_snap_to_word": bool(
                viz_settings.get("fixation_snap_to_word", False)
            ),
            # PRE-3 drift correction (ENG-23): saved as the picker's own
            # spelling ("Off" or a title-cased algorithm) so it restores 1:1.
            "drift_correction": str(viz_settings.get("align_algorithm", "Off")),
            "drift_connectors": bool(viz_settings.get("align_connectors", False)),
            "hollow_fixations": bool(viz_settings.get("hollow_fixations", False)),
            "fixation_opacity": float(viz_settings.get("fixation_opacity", 1.0)),
            # VIZ-17 uniform fixation colour · VIZ-15 marker shape · VIZ-18 palette
            # (the palette's colours are already in the individual keys; the name
            # rides along so the picker restores onto the right entry).
            "fixation_color": viz_settings.get(
                "fixation_color", DEFAULT_FIXATION_COLOR
            ),
            "fixation_symbol": viz_settings.get(
                "fixation_symbol", DEFAULT_FIXATION_SYMBOL
            ),
            "palette": viz_settings.get("palette", DEFAULT_PALETTE),
            # VIZ-4: image-stimulus opacity + manual alignment (dataset + uploads).
            "stimulus_image_opacity": float(
                viz_settings.get("stimulus_image_opacity", 1.0)
            ),
            "stimulus_image_offset_x": float(
                viz_settings.get("stimulus_image_offset_x", 0.0)
            ),
            "stimulus_image_offset_y": float(
                viz_settings.get("stimulus_image_offset_y", 0.0)
            ),
            "stimulus_image_scale": float(
                viz_settings.get("stimulus_image_scale", 1.0)
            ),
            "colorbar_orientation": figure_settings.get(
                "colorbar_orientation", "Vertical"
            ),
            "colorbar_tickangle": int(figure_settings.get("colorbar_tickangle", 0)),
            "colorbar_tickfont_size": int(
                figure_settings.get("colorbar_tickfont_size", 12)
            ),
        },
        "sizing": {
            "marker_size_range": [int(s) for s in figure_settings["marker_size_range"]],
            "order_font_size": int(figure_settings["order_font_size"]),
            "order_font_color": figure_settings["order_font_color"],
            "base_font_size": int(base_font_size),
        },
        "text": {
            "scale_text_to_boxes": bool(
                figure_settings.get("scale_text_to_boxes", True)
            ),
            "line_spacing": float(
                figure_settings.get("line_spacing", DEFAULT_LINE_SPACING)
            ),
            "font_family": font_family,
            "text_color": figure_settings.get("text_color", WORD_LABEL_COLOR),
            "word_hover_fields": list(viz_settings.get("word_hover_fields") or []),
            "fixation_hover_fields": list(
                viz_settings.get("fixation_hover_fields") or []
            ),
        },
        # EXP-5: title/caption pattern, moved here from being Export-only.
        "labels": {
            "show_title_caption": bool(
                st.session_state.get("global_show_title_caption", False)
            ),
            "title_pattern": viz_settings.get("title_pattern", ""),
            "caption_pattern": viz_settings.get("caption_pattern", ""),
        },
        "highlighting": {
            "critical_span_style": figure_settings.get(
                "critical_span_style", "Mark text"
            ),
            "highlight_column": figure_settings.get("highlight_column", "is_in_aspan"),
            # Fixation classification (PRE-2): short/long/out-of-bounds highlight or
            # discard, saved verbatim so it restores 1:1.
            "fixation_flags": figure_settings.get("fixation_flags"),
            "highlight_text_color": figure_settings.get(
                "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
            ),
            "background_color": figure_settings.get("background_color"),
            "span_border_color": figure_settings.get("span_border_color", "#000000"),
        },
        "raw_gaze": {
            "available": not trial_raw_gaze.empty,
            "points": len(trial_raw_gaze) if not trial_raw_gaze.empty else 0,
        },
        # Per-scanpath styling for the two-trial comparison (None when the caller
        # didn't collect it). Each entry holds raw widget values so it restores 1:1.
        "compare": compare_styles,
        # CMP-11 — how the two scanpaths are arranged, and whose stimulus an
        # overlay draws. Separate from `compare` above, which is a two-entry list
        # of per-scanpath *styling*; these describe the view itself.
        "compare_view": {
            "layout": st.session_state.get(SINGLE_COMPARE_LAYOUT, "Overlay"),
            "stimulus": st.session_state.get(SINGLE_COMPARE_STIMULUS, "Both"),
        },
        "annotations": annotation_records,
        # DATA-20: the participant table travels with the saved session, so a
        # restored config brings back the metadata *and* the filters/chips that
        # refer to it — otherwise a restored `filter_meta_*` selection would
        # point at fields that no longer exist. Records, not a file path: the
        # JSON has to be portable between machines like everything else in it.
        "participant_metadata": _participant_metadata_payload(),
        # DATA-29: and the trial table, for exactly the same reason — a restored
        # `filter_trialmeta_*` selection has to land on fields that exist.
        "trial_metadata": _trial_metadata_payload(),
    }


def _participant_metadata_payload():
    from scanpath_studio import metadata as md

    return md.to_payload(active_participant_metadata())


def _trial_metadata_payload():
    from scanpath_studio import metadata as md

    return md.trial_to_payload(md.active_trials())


def _collect_column_mapping() -> dict:
    """The column-mapping selections from session_state, for config provenance.

    The upload boxes share the ``col_map_*`` prefix (``state_prefix="col_map_fix"``
    etc.), so their ``file_uploader`` widgets land in this sweep too. Their value
    is an ``UploadedFile`` (or list of them), which isn't JSON serializable and
    isn't part of the column mapping — so the ``_upload`` widget keys are
    excluded."""
    return {
        k: st.session_state[k]
        for k in sorted(st.session_state.keys())
        if isinstance(k, str) and k.startswith("col_map_") and not k.endswith("_upload")
    }


def _render_save_restore_expander(
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
    slot=None,
):
    """Render the "💾 Save & restore" menu panel (DATA-9).

    Merges the former Plot-configuration and Annotations panels into one: a
    single JSON sidecar that captures the full figure configuration (layers,
    colouring, sizing, text/highlighting, canvas, axes, trial selection) PLUS
    every per-trial annotation, with a matching uploader to restore it all. So a
    reviewer can save, share, and reload the exact state behind a figure. The
    upload is *applied* in ``app._apply_uploaded_plot_config`` (it runs before
    the widgets render). ``slot`` is the 💾 Save & restore popover ``app.main``
    reserves on the top menu bar, so the panel is reachable from every view
    instead of landing after whichever tab happened to render it.

    Renders bare into ``slot``: the popover trigger is the disclosure, and a
    popover nests no expander (see :mod:`scanpath_studio.menu`).
    """
    from datetime import datetime

    from scanpath_studio import __version__, annotations

    container = slot if slot is not None else st.container()
    annotation_records = annotations.current_records()
    # Provenance: which data source + how its columns were mapped +
    # the app version + when it was exported, so a saved config records the full
    # context behind the figure, not just the plot settings.
    column_mapping = _collect_column_mapping()
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
            # UX-31: the A/B legend label override ("" = the auto label).
            "label_pattern": st.session_state.get(f"cmp{idx}_label_pattern") or "",
        }
        for idx in range(2)
    ]
    plot_config = _build_studio_config(
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
        annotation_records=annotation_records,
        column_mapping=column_mapping,
        data_source=st.session_state.get("data_source_choice"),
        app_version=__version__,
        exported_at=datetime.now().isoformat(timespec="seconds"),
        compare_styles=compare_styles,
    )
    # (An "_open_save_restore" shortcut used to click this panel's menu trigger
    # from here via injected JS. Its last *setter* went with the annotations
    # panel that had it, and UX-100 removed the trigger it clicked — the panel
    # is a dialog now, armed by `app._arm_session`, which is what any future
    # shortcut should set.)
    with container:
        n_anno = len(annotation_records)
        st.download_button(
            "⬇ Download backup",
            help="Save plot settings, selection, source reference, column mapping "
            f"and annotations ({n_anno} trial{'s' if n_anno != 1 else ''}) as JSON.",
            data=json.dumps(plot_config, indent=2),
            file_name="scanpath_studio_backup.json",
            mime="application/json",
            key="plot_config_download",
            width="stretch",
        )
        st.file_uploader(
            "Restore backup",
            type=["json"],
            key="plot_config_upload",
            help="Re-apply settings and annotations. Items that do not match "
            "the loaded data are skipped.",
        )
        skipped = st.session_state.get("_plot_config_skipped")
        if skipped:
            st.caption(
                "⚠️ Not applied (no match in the current data): "
                + ", ".join(skipped)
                + "."
            )


#: Separator between a dataset name and a participant id in the *throwaway*
#: compare frames (CMP-8 §3). Chosen to be visible in a label and absent from
#: real ids; it never reaches an annotation key, an export slug or a deep link.
#: Defined in `utils.py` since CMP-9; aliased here for the existing call sites.
_COMPARE_DATASET_SEP = COMPARE_DATASET_SEP

#: Metric names that are safe across any two corpora (CMP-8 §5.4): canonical
#: fixation columns every normalized frame carries, plus the two synthetic
#: choices that are not columns at all.
_CROSS_DATASET_SAFE_METRICS = frozenset(
    {"line", "counts", "duration_ms", "order_in_trial", "timestamp_ms"}
)


def _compare_setups(
    compare_meta: dict | None,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    canvas_width: int,
    canvas_height: int,
) -> tuple[bool, str]:
    """CMP-11: may A and B be drawn in one coordinate space? Plus the reason.

    ``(True, "")`` for every *same-dataset* pair — one corpus is one screen, and
    that case must stay exactly as it was before CMP-11.

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
    from scanpath_studio.experimental_setup import setups_comparable

    if not compare_meta or not compare_meta.get("dataset"):
        return True, ""
    setup_b = compare_meta.get("setup")
    if setup_b is None:
        return False, (
            "The comparison dataset does not report a screen, so there is no way "
            "to tell whether these readings share one coordinate space. They are "
            "shown side by side instead."
        )
    active = str(st.session_state.get("data_source_choice") or "")
    setup_a = replace(
        snapshot_for(active, words, fixations),
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
    )
    return setups_comparable(setup_a, setup_b)


# CMP-9 promoted these four to `utils.py`: the app, `api.compare_scanpaths` and
# `cli.render --compare-*` all build cross-dataset comparison frames now, and the
# participant-namespacing rule must have exactly one definition. The private
# names stay as aliases so existing call sites and tests resolve unchanged.
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
    selected_screen: str | None = None,
    source: SecondaryDataset | None = None,
    primary_dataset: str | None = None,
) -> dict | None:
    """Build the second trial's words/fixations + column labels for the
    side-by-side metadata table, or None when no comparison is active.

    ``primary_dataset`` is A's own corpus name (CMP-15): a cross-dataset
    comparison names *both* sides above their chip strips, since naming only B
    reads as though A had no corpus at all.

    ``source`` (CMP-8 §3) makes B come out of a *different* dataset: the trial is
    extracted from that source's frames, namespaced by `_qualify_for_compare`,
    and the returned dict carries the qualified participant plus B's own
    ``dataset`` / ``text_id`` / ``setup`` — the last three because everything
    downstream would otherwise look them up in **A's** combos and geometry.
    """
    if compare_participant is None or compare_trial is None:
        return None
    if source is not None:
        # The multipart screen scoping below asks whether B contains *A's*
        # screen id, which is meaningless across corpora — a foreign dataset's
        # trial is compared whole.
        selected_screen = None
        words_filtered, fixations_filtered = source.words, source.fixations
    compare_words = extract_trial(words_filtered, compare_participant, compare_trial)
    compare_fix = extract_trial(fixations_filtered, compare_participant, compare_trial)
    if selected_screen is not None:
        if not compare_words.empty:
            if SCREEN_ID not in compare_words.columns:
                return None
            compare_words = extract_part(
                compare_words, compare_participant, compare_trial, selected_screen
            )
        if not compare_fix.empty:
            if SCREEN_ID not in compare_fix.columns:
                return None
            compare_fix = extract_part(
                compare_fix, compare_participant, compare_trial, selected_screen
            )
        if compare_words.empty and compare_fix.empty:
            return None
    # Short, distinct column headers: participant ids when comparing different
    # participants (the common same-text case), else the trial ids — the long
    # ids otherwise overflow the narrow panel. Across datasets the two readers
    # are never the same person, so the dataset name is the distinguishing half.
    #
    # CMP-15: across datasets that qualifier goes on **both** labels. B's name
    # comes free with the *Compare with* pick while A's source is implicit, so
    # labelling only B read as though one panel had a corpus and the other did
    # not. Same-dataset comparisons — the common case — stay bare on both sides:
    # repeating one corpus name twice says nothing.
    if source is not None:
        label_primary = str(selected_participant)
        if primary_dataset:
            label_primary = (
                f"{primary_dataset}{_COMPARE_DATASET_SEP}{selected_participant}"
            )
        label_compare = f"{source.name}{_COMPARE_DATASET_SEP}{compare_participant}"
    elif str(selected_participant) != str(compare_participant):
        label_primary = str(selected_participant)
        label_compare = str(compare_participant)
    else:
        label_primary = str(selected_trial)
        label_compare = str(compare_trial)
    figure_participant = compare_participant
    if source is not None:
        compare_words = _qualify_for_compare(compare_words, source.name)
        compare_fix = _qualify_for_compare(compare_fix, source.name)
        figure_participant = _qualified_participant(source.name, compare_participant)
    return {
        "words": compare_words,
        "fixations": compare_fix,
        "label_primary": label_primary,
        "label_compare": label_compare,
        # The id to slice the *merged* compare frames by — namespaced when B is
        # foreign. `raw_participant` is the real one, for export slugs, share
        # links and anything else that must name the reader as the corpus does.
        "participant": figure_participant,
        "raw_participant": compare_participant,
        "trial": compare_trial,
        "dataset": source.name if source is not None else None,
        "setup": source.setup if source is not None else None,
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
# Default playback speed — brisk enough for quick review (real-time ÷ 4) but
# still legible; the Playback popover's speed slider slows it down (to ×0.25).
_ANIM_DEFAULT_SPEED = 4.0
_ANIM_QUALITY_PRESETS = {
    # Fast enough for trial browsing and compact GIF/MP4 drafts.
    "Coarse": (300, 120),
    # High-fidelity review/export: noticeably smoother than the old 100 ms grid.
    "Fine": (40, 900),
}


def _render_anim_info_box(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    words_b: pd.DataFrame | None,
    fixations_b: pd.DataFrame | None,
    selected_participant: str,
    selected_trial: str,
    compare_participant: str | None,
    compare_trial: str | None,
    playback_speed: float,
    grid_step_ms: float | None = None,
    max_frames: int | None = None,
) -> float:
    """Render the animation reading-time / playback info box (+ overlay caveats),
    shown in the side panel under the Animate toggle. Returns the playback
    duration in ms; the box deliberately omits a redundant fixation count."""
    dual = fixations_b is not None and not fixations_b.empty
    summary = animation_timeline_summary(
        [trial_fixations] + ([fixations_b] if dual else []),
        playback_speed,
        grid_step_ms=grid_step_ms,
        max_frames=max_frames,
    )
    reading_span_ms = summary["reading_span_ms"]
    playback_ms = summary["playback_ms"]
    if dual:
        span_a = animation_playback_ms([trial_fixations], 1.0)[0]
        span_b = animation_playback_ms([fixations_b], 1.0)[0]
        st.info(
            f"**A** reading time {span_a / 1000:.1f}s · **B** {span_b / 1000:.1f}s "
            f"· Playback ×{playback_speed:g}: {playback_ms / 1000:.1f}s"
        )
        if (compare_participant, compare_trial) == (
            selected_participant,
            selected_trial,
        ):
            st.caption("⚠️ The second scanpath is the same trial as the first.")
        else:
            text_a = _trial_text_id(trial_words)
            text_b = _trial_text_id(words_b)
            if text_a is not None and text_b is not None and text_a != text_b:
                st.warning(
                    "The two scanpaths are **different texts**, so the shared "
                    "word boxes don't line up — the spatial overlay isn't "
                    "meaningful. Best for two readings of the same paragraph."
                )
    # VIZ-11 follow-up: state what the chosen grid actually produced. The cap
    # coarsening the step used to be invisible, which is the whole reason the
    # setting felt arbitrary. UX-30 folded it INTO the box below rather than
    # leaving it as a second, detached caption at the foot of the popover: the
    # frame count is part of the same "what will this replay be like?" answer.
    grid = (
        f"**{summary['n_frames']}** frames · one every "
        f"{summary['step_ms']:.0f} ms of reading"
    )
    if summary["coarsened"]:
        grid += ". Spacing was increased automatically to keep the animation manageable"
    if not dual:
        st.info(
            f"Reading time: {reading_span_ms / 1000:.1f}s · "
            f"Playback at ×{playback_speed:g}: {playback_ms / 1000:.1f}s\n\n"
            f"{grid}"
        )
    else:
        st.caption(grid)
    return playback_ms


def _apply_preprocessing_caption(fig, participant, trial) -> None:
    """Put PRE-15 cleaning provenance on-screen, in exports, and in metadata."""
    report = st.session_state.get("_preprocessing_report")
    if not isinstance(report, pd.DataFrame) or report.empty:
        return
    row = report[
        (report["participant_id"].astype(str) == str(participant))
        & (report["trial_id"].astype(str) == str(trial))
    ]
    if row.empty:
        return
    item = row.iloc[0]
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
    metadata["preprocessing"] = item.to_dict()
    fig.update_layout(meta=metadata)


def _apply_title_caption(
    fig,
    viz_settings: dict,
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str,
    trial: str,
    combo_row: dict | None = None,
    dataset_name: str | None = None,
    compare_row: dict | None = None,
) -> None:
    """EXP-5: stamp the rail's title/caption pattern onto ``fig``.

    Reuses EXP-2's pattern language (`export.pattern_fields`/`render_pattern`/
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
    title_pattern = viz_settings.get("title_pattern") or ""
    caption_pattern = viz_settings.get("caption_pattern") or ""
    if not title_pattern and not caption_pattern:
        return
    settings_summary_input = {
        "show_words": viz_settings.get("show_words", False),
        "show_word_labels": viz_settings.get("show_labels", True),
        "show_fixations": viz_settings.get("show_fix", True),
        "show_saccades": viz_settings.get("show_saccades", True),
        "show_heatmap": viz_settings.get("show_heatmap", False),
        "color_by": viz_settings.get("color_by"),
        "palette": viz_settings.get("palette"),
    }
    fields = pattern_fields(
        participant,
        trial,
        trial_words,
        trial_fixations,
        settings_summary_input,
        combo_row=combo_row,
        # VIZ-36: the name the dataset picker shows. `current_dataset_name()`
        # is the session default so the three in-app render paths (static,
        # animation, compare) all get it without each remembering to.
        dataset_name=current_dataset_name() if dataset_name is None else dataset_name,
        compare_row=compare_row,
    )
    title = render_pattern(title_pattern, fields) if title_pattern else ""
    caption = render_pattern(caption_pattern, fields) if caption_pattern else ""
    annotate_figure(fig, title=title, caption=caption)


#: The auto A/B legend label, written in the pattern language (UX-31). Kept as
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
    """UX-31: the A/B legend label for compare scanpath ``idx`` (0 or 1).

    An explicit ``cmp{idx}_label_pattern`` (⚙️ Compare options popover,
    EXP-2-style pattern + preview) overrides the plain ``participant · trial``
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
        # VIZ-36: side B can be a different corpus entirely (#CMP-8), so the
        # label resolves `{dataset_name}` against *its own* side rather than
        # the picker's — an A/B legend that named the same dataset twice would
        # be worse than no name at all.
        dataset_name=dataset_name or current_dataset_name(),
    )
    return render_pattern(pattern, fields) or default


def _compare_dataset_name(compare_meta: dict | None) -> str:
    """The dataset scanpath B is drawn from (VIZ-36).

    #CMP-8 lets B come from a second corpus, and `compare_meta["dataset"]`
    carries its name when it does; a same-dataset comparison leaves it unset and
    both sides are the picker's current source.
    """
    return str((compare_meta or {}).get("dataset") or current_dataset_name())


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
    settings: FigureSettings,
    viz_settings: dict,
    playback_speed: float,
    drift_corrected: bool = False,
    dataset_name_b: str = "",
):
    """Build + render the animation figure (single or dual co-animation) in the
    main column. Returns ``(fig, playback_ms, save_slug, file_stem)``.

    ``trial_fixations`` / ``fixations_b`` arrive already drift-corrected (PRE-3 is
    applied once by the caller for all three render paths); ``drift_corrected``
    just says so, so the single replay can force colour-by-line the way the static
    figure does. There is no connector layer here — see the note at the hoist."""
    dual = fixations_b is not None and not fixations_b.empty
    grid_step_ms = viz_settings.get("anim_grid_step_ms")
    max_frames = viz_settings.get("anim_max_frames")
    _reading_span_ms, playback_ms = animation_playback_ms(
        [trial_fixations] + ([fixations_b] if dual else []),
        playback_speed,
        grid_step_ms=grid_step_ms,
        max_frames=max_frames,
    )
    # The reading-time / playback info box renders in the side panel under the
    # Animate toggle (see _render_anim_info_box), not here.
    animation_settings = settings.with_overrides(
        playback_speed=playback_speed,
        # Drift correction colours the replay by assigned line, exactly as the
        # static figure does once an algorithm is picked.
        color_by_line=bool(settings.color_by_line or drift_corrected),
        # The replay has no border-overlay layer, so only the text-marking mode
        # carries a highlight column.
        highlight_column=_marked_text_column(viz_settings),
        show_legend=viz_settings.get("show_compare_legend", False),
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
    )
    fig = make_scanpath_animation(
        trial_words,
        trial_fixations,
        settings=animation_settings,
        fixations_b=fixations_b if dual else None,
        words_b=words_b if dual else None,
    )
    add_illustration_label(fig, viz_settings.get("illustration_reasons"))
    _apply_preprocessing_caption(fig, selected_participant, selected_trial)
    _apply_title_caption(
        fig,
        viz_settings,
        trial_words,
        trial_fixations,
        selected_participant,
        selected_trial,
        compare_row=(
            {
                "dataset_name": dataset_name_b or current_dataset_name(),
                "participant_id": compare_participant,
                "trial_id": compare_trial,
            }
            if dual
            else None
        ),
    )
    _render_true_scale_chart(fig, key="single_anim")
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
    return fig, playback_ms, save_slug, file_stem


def _render_pair_export(
    fig,
    sides: tuple,
    *,
    canvas_width: int,
    canvas_height: int,
    viz_settings: dict,
    line_spacing: float,
    scale_text_to_boxes: bool,
) -> None:
    """The **CMP-8 §6** pair bundle, beside the plain figure download.

    The figure alone is unreproducible — it names two readers and no way to find
    either again. This writes the pair as one trial folder: the figure, both
    scanpaths' tables with a ``dataset`` column, and a ``plot_config.json``
    whose ``datasets`` block records both sources and both recording setups.
    """
    side_a, side_b = sides
    with st.expander("⚖️ Download this comparison as a bundle", expanded=False):
        st.caption(
            "The figure plus both scanpaths' data and a manifest naming each "
            "side's dataset, trial and recording setup — so the comparison can "
            "be reproduced, which the image alone can't be."
        )
        fmt = panel_field(
            st,
            "selectbox",
            "Figure format",
            options=["png", "svg", "pdf", "html"],
            key="cmp_pair_export_format",
            help="PNG/SVG/PDF need a Chrome/Chromium browser (Kaleido); HTML "
            "needs none.",
        )
        table_fmt = panel_field(
            st,
            "selectbox",
            "Table format",
            options=["csv", "parquet"],
            key="cmp_pair_export_table_format",
        )
        if not st.button("Build bundle", key="cmp_pair_export_build"):
            return
        options = ExportOptions(
            include_png=fmt == "png",
            include_svg=fmt == "svg",
            include_pdf=fmt == "pdf",
            include_html=fmt == "html",
            include_fixations=True,
            include_measures=True,
            table_format=table_fmt,
        )
        settings = _build_figure_settings(viz_settings, False)
        settings["line_spacing"] = line_spacing
        settings["scale_text_to_boxes"] = scale_text_to_boxes
        settings["align_algorithm"] = viz_settings.get("align_algorithm", "Off")
        try:
            with st.spinner("Building the comparison bundle…"):
                data = pair_export(
                    fig,
                    side_a,
                    side_b,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    x_field=viz_settings.get("x_field", "x"),
                    y_field=viz_settings.get("y_field", "y"),
                    settings=settings,
                    options=options,
                )
        except (RuntimeError, ValueError) as exc:
            st.error(f"Couldn't build the bundle: {exc}")
            return
        st.download_button(
            "⬇ Download bundle (zip)",
            data=data,
            file_name=f"comparison_{side_a.slug}__vs__{side_b.slug}.zip",
            mime="application/zip",
            key="cmp_pair_export_download",
        )


def _render_export_panel(
    displayed_fig,
    *,
    animate: bool,
    save_slug: str,
    playback_ms: float | None,
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
    line_spacing: float,
    scale_text_to_boxes: bool,
    selected_participant: str,
    selected_trial: str,
    compare_export: tuple | None = None,
) -> None:
    """Consolidated Export subtab: the currently-viewed figure on top, then a
    bulk multi-trial export below.

    Replaces both the old single-trial Export toggle and the standalone Bulk
    Export tab. "Current figure" exports the live figure (static PNG/SVG/PDF/HTML, or
    the HTML/GIF/MP4 animation when animating) so the on-screen view — including
    a comparison or animation — round-trips exactly; the bulk section rebuilds
    static figures across many trials."""
    st.markdown("## Current figure")
    if displayed_fig is None:
        st.caption("Select a trial to export its figure.")
    elif animate:
        _render_animation_export(
            displayed_fig,
            file_stem=file_stem or "animation",
            playback_ms=playback_ms or 0.0,
        )
    else:
        _render_save_plot_button(
            displayed_fig,
            canvas_width=int(canvas_width),
            canvas_height=int(canvas_height),
            slug=save_slug,
            key_prefix="single",
        )
        if compare_export is not None:
            _render_pair_export(
                displayed_fig,
                compare_export,
                canvas_width=int(canvas_width),
                canvas_height=int(canvas_height),
                viz_settings=viz_settings,
                line_spacing=line_spacing,
                scale_text_to_boxes=scale_text_to_boxes,
            )

    st.divider()
    st.markdown("## Export bundle")
    bulk_settings = _build_figure_settings(viz_settings, False)
    bulk_settings["line_spacing"] = line_spacing
    bulk_settings["scale_text_to_boxes"] = scale_text_to_boxes
    # EXP-4 / VIZ-24: the bulk export rebuilds every figure from scratch, so the
    # PRE-3 drift correction must ride along or the batch silently differs from
    # the corrected figure on screen. Applied per trial inside `bulk_export`
    # (figures only — the exported tables stay uncorrected by design).
    bulk_settings["align_algorithm"] = viz_settings.get("align_algorithm", "Off")
    bulk_settings["align_connectors"] = bool(viz_settings.get("align_connectors"))
    # EXP-5: the rail's title/caption pattern is the single source of truth —
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
    from scanpath_studio.experimental_setup import pixels_per_degree

    try:
        bulk_settings["pixels_per_degree"] = pixels_per_degree(
            float(st.session_state.get("global_viewing_distance_mm", 800.0)),
            float(canvas_width),
            float(st.session_state.get("global_monitor_width_mm", 597.0)),
        )
    except (TypeError, ValueError):
        pass
    # DATA-20: ship the participant table with the bundle, as its own file.
    #
    # The **fingerprint** goes in the settings dict, not the frame. `sig` below
    # hashes `figure_settings` through `json.dumps(..., default=str)`, and
    # `default=str` on a DataFrame falls through to `repr(df)`, which pandas
    # truncates past 60 rows — so re-uploading a corrected table of the same
    # shape produced an identical signature and served the *stale* cached zip,
    # with the pre-edit `metadata/participants.csv` inside it. The frame itself
    # rides on a private key the exporter reads and the signature ignores.
    _attached = active_participant_metadata()
    if _attached is not None and not _attached.frame.empty:
        bulk_settings["participant_metadata_fingerprint"] = frame_fingerprint(
            _attached.frame
        )
        st.session_state["_export_participant_metadata"] = _attached.frame
    else:
        st.session_state.pop("_export_participant_metadata", None)
    _render_bulk_export(
        combos,
        words_filtered,
        fixations_filtered,
        combos_all,
        words_all,
        fixations_all,
        raw_gaze,
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


_CHIP_NEUTRAL_BG = "#EEF2F7"
# Friendly labels for the identity fields; everything else is humanized.
_CHIP_FIELD_LABELS = {
    "participant_id": "Participant",
    "unique_text_id": "Text",
    "text_id": "Text",
    "unique_paragraph_id": "Text",
    "paragraph_id": "Text",
    # MultiplEYE facets + reader metadata.
    "genre": "Genre",
    "session": "Session",
    "is_practice": "Practice",
    "trial_num": "Trial #",
    "pp_age": "Age",
    "pp_gender": "Gender",
    "pp_native_language": "Native language",
    "pp_years_education": "Years of education",
    "pp_education_level": "Education",
}


def _chip_field_label(col: str) -> str:
    """Friendly label for a chip field (summary / identity, else humanized)."""
    if col in SUMMARY_CHIP_FIELDS:
        return SUMMARY_CHIP_FIELDS[col]
    return _CHIP_FIELD_LABELS.get(col, _humanize_field(col))


def _chip_value_and_uniqueness(col, trial_words, trial_fixations, participant):
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
        if src is not None and not src.empty and col in src.columns:
            series = src[col]
            non_null = series.dropna()
            if non_null.empty:
                return (None, True)
            return (non_null.iloc[0], int(series.nunique(dropna=True)) <= 1)
    # DATA-20: not a recorded column — try the attached participant table. A
    # reader attribute is trivially constant within a trial, so it never earns
    # the ⚠️ "varies within this trial" flag. Checked *after* the frames, so a
    # real column of the same name always wins.
    attached = active_participant_metadata()
    if attached is not None and participant is not None:
        value = attached.values_for(participant).get(col)
        if value is not None and not pd.isna(value):
            return (value, True)
    return (None, True)


def _chip_color(col: str, value_str: str) -> str:
    """Background for a chip.

    UX-28: a user-picked colour (any field, any dataset — set via the ✏️ Edit
    chips popover's **Chip colours** section, `trial_chip_colors`) wins over
    everything below. Absent that, known OneStop conditions keep their
    metadata-table colour so the demo reads the same as before this was
    generalized; everything else is neutral.
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


def _render_trial_condition_chips(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    participant: str | None,
    fields,
    *,
    leading_chip: tuple[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Render the ``Field = Value`` chip strip above the plot — the trial's
    identity and experiment conditions, so "what am I looking at" is answered at
    a glance (these chips replaced the Trial Info subtab).

    **UX-11.** The strip used to be pinned to one line, clipping whatever didn't
    fit, with a **More** disclosure that re-listed *every* chip so the clipped
    ones stayed reachable — the same facts shown twice, because which chips fit
    is a live-width question Python can't answer. The fix is to stop asking: the
    strip is a wrapping flex row, so nothing is ever cut at any width or sidebar
    state, and the duplicate list has no reason to exist. What's left is split by
    *kind* rather than by what happened to fit — conditions inline here, the
    computed summary stats in the **Summary stats** popover the caller renders from the
    returned list.

    ``fields`` is the configurable list of fields to surface (the ✏️ Edit chips
    popover). A data column that varies within the trial is shown (first value)
    but flagged with ⚠️.

    Returns the ``(label, value)`` summary stats for that popover; empty
    when the user has no summary chips selected."""
    primary: list[tuple[str, str]] = []  # identity + conditions (inline)
    summary: list[tuple[str, str]] = []  # computed stats (inside "More")
    summary_lookup: dict | None = None  # computed once, only if a summary chip
    for col in fields or []:
        # Virtual summary fields (reading time / counts) — always trial-level,
        # computed once from `_summary_rows`; routed to the "More" disclosure.
        if col in SUMMARY_CHIP_FIELDS:
            if summary_lookup is None:
                summary_lookup = {
                    r["Field"]: r["Value"]
                    for r in _summary_rows(trial_words, trial_fixations)
                }
            label = SUMMARY_CHIP_FIELDS[col]
            value = summary_lookup.get(label)
            if value in (None, ""):
                continue  # e.g. "Fixations in word boxes" unavailable for this trial
            summary.append((label, str(value)))
            continue
        value, trial_level = _chip_value_and_uniqueness(
            col, trial_words, trial_fixations, participant
        )
        if value is None:
            continue
        value_str = str(value)
        # Skip empty / missing values (a "string" optional field coerces NaN to
        # the literal "nan", e.g. ET2 readers with no recorded gender).
        if value_str.strip().lower() in ("", "nan", "none", "<na>"):
            continue
        label = _chip_field_label(col)
        prefix = "" if trial_level else "⚠️ "
        primary.append((f"{prefix}{label} = {value_str}", _chip_color(col, value_str)))
    if primary or leading_chip:
        leading_html = ""
        if leading_chip is not None:
            leading_label, leading_color = leading_chip
            leading_html = (
                f'<span class="sps-chip" style="background:{leading_color};'
                f'color:#fff;">{html.escape(leading_label)}</span>'
            )
        st.markdown(
            '<div class="sps-trial-chips">'
            + leading_html
            + "".join(
                f'<span class="sps-chip" style="background:{bg};">'
                f"{html.escape(lbl)}</span>"
                for lbl, bg in primary
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    return summary


def _render_trial_details_popover(summary: list[tuple[str, str]], host) -> None:
    """The **Summary stats** popover beside the chip strip: the computed numbers.

    UX-11 split the strip by *kind*: conditions are chips (short, colour-coded,
    scannable), while reading time / word count / fixation counts are derived
    numbers that read far better as a key→value list — and are the "on demand"
    half of the strip's job. Renders nothing when the user has no summary chips
    selected, so the control never appears empty.
    """
    if not summary:
        return
    with host.popover(
        "Summary stats", width="content", help="Summary stats for this trial."
    ):
        st.markdown(
            "".join(
                '<div class="sps-stat">'
                f'<span class="sps-stat-name">{html.escape(name)}</span>'
                f'<span class="sps-stat-val">{html.escape(value)}</span>'
                "</div>"
                for name, value in summary
            ),
            unsafe_allow_html=True,
        )


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
    share_renderer: Callable[[], None] | None = None,
    # UX-25: renders the data-source picker into the "Filter by" row's first
    # column. Passed by ``app.main`` (which owns the source list + wizard hooks).
    data_source_renderer: Callable[[object], None] | None = None,
    canvas_renderer: Callable[[Any], None] | None = None,
) -> None:
    """Render the main Scanpath Visualization screen (static + animated).

    Layout, designed for use with the sidebar closed (everything needed is beside
    the plot, no scrolling):

    1. A compact **selection bar** above the plot — the trial picker + a 🔍 Filter
       expander, with a strip of experiment-condition chips below it (the trial's
       "what am I looking at" at a glance).
    2. A **plot + right rail** split: the scanpath plot on the left, and a control
       rail on the right carrying the **view modes** (Animate / Compare) and the
       **visualization controls** (formerly in the sidebar — see
       ``controls.sidebar_controls``, rendered here with ``host=``).
    3. A plot-width **subtab bar** directly below it: 📝 Annotations ·
       📄 Stimulus & Context · 🔬 Comparisons · 📤 Export · 🔗 Share. Export folds in the former Bulk
       Export tab (``_render_export_panel``); Share (the former header popover)
       builds the deep link via ``share_renderer`` (passed by ``app.main``). The
       former Trial Info subtab was folded into the chips above the plot, and
       **DATA-26** moved 🔎 Data Inspection off this bar onto the 🗂️ Data page.
       Save & restore is a popover on the top menu bar.

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

    # --- Plot (left) + control rail (right) -----------------------------------
    # Columns FIRST so the rail starts at the very top, beside the selection —
    # built for the sidebar-closed workflow. The selection menus + chips + plot all
    # live in the left column, including the per-trial subtabs directly below the
    # plot. The rail is kept narrow (the plot is the hero) and scrolls separately.
    plot_col, rail_col = st.columns([4, 1], gap="large")
    with rail_col:
        rail = st.container(key="scanpath_rail")

    with plot_col:
        # UX-64 — everything is on the picker row below now: the dataset, the
        # trial, the scrubber, ◀ ▶ ⇅ and a filter popover. The Narrow-by row
        # that used to sit here — [data source] [Filter by: Text, Participant]
        # [More] — is gone, and its two multiselects moved *inside* that filter
        # popover beside the condition/annotation filters, so there is one place
        # that narrows the pool instead of two.
        #
        # `tour_grp_data_source` and `tour_grp_narrow_by` still exist as sibling
        # spotlight targets (UX-42) — they are just the row's lead cell and the
        # filter popover's body rather than two thirds of a row of their own.
        def _render_dataset_cell(host) -> None:
            # No wrapper container here: `app.render_data_source_picker` makes
            # its own `tour_grp_data_source`, and a second one is a duplicate key.
            if data_source_renderer is not None:
                data_source_renderer(host)

        def _render_filters(host) -> None:
            """Every way to narrow the pool, behind one funnel (UX-64)."""
            pop = host.popover(
                _FILTER_ICON, width="content", help="Filter the trial list"
            )
            box = pop.container(key="tour_grp_narrow_by")
            render_narrow_by(words_all, fixations_all, text_host=box, part_host=box)
            render_trial_filters(words_all, fixations_all, host=box)

        # Trial picker (its own row of columns): selectbox + slider + ◀ ▶.
        with st.container(key="tour_grp_trial_picker"):
            selected_participant, selected_trial, selection_mode, selected_text = (
                select_trial(
                    combos,
                    key_prefix="single",
                    leading_renderer=_render_dataset_cell,
                    filter_renderer=_render_filters,
                    # UX-10: the frames `combos` was built from, so the ⇅ sort
                    # popover can offer computed keys (fixation count, reading
                    # time) alongside the reader / text / condition columns.
                    words=words_filtered,
                    fixations=fixations_filtered,
                )
            )
        screen_slot = st.container(key="tour_grp_screen_picker")
        # Slots filled once the selection is resolved (chips need the trial).
        # Keyed containers double as welcome-tour spotlight targets.
        #
        # CMP-16 — creation order *is* screen order, so these three reservations
        # are the whole layout: **both control lines first, then both chip
        # strips** (control A · control B · chips A · chips B). UX-75 had paired
        # them the other way — each reading's chips directly under the row that
        # chose it — which says whose chips are whose but puts the two control
        # lines a strip apart, so comparing the A and B selectors means reading
        # across an unrelated block. Grouping by kind puts them adjacent, and
        # #CMP-15 is what keeps the attribution: each chip strip names its own
        # dataset, so nothing depends on vertical adjacency any more. Keyed
        # containers double as welcome-tour spotlight targets — `compare_slot`
        # takes one too, for symmetry with the strip it now sits beside.
        compare_slot = st.container(key="tour_grp_compare_picker")
        chips_slot = st.container(key="tour_grp_chips")
        compare_chips_slot = st.container(key="tour_grp_compare_chips")
        plot_slot = st.container(key="tour_grp_plot")

    # UX-43: a second row repeats the 4:1 split and reserves only its left side
    # for the per-trial panels. Keeping the slot OUT of the plot/rail row means
    # an open Annotations (or any other) panel cannot make the rail taller than
    # the plot above it; the blank right cell preserves exact plot-column width.
    subtabs_col, _ = st.columns([4, 1], gap="large")
    subtabs_slot = subtabs_col.container(key="tour_grp_subtabs")

    if not (selected_participant and selected_trial):
        return

    # Remember the resolved selection so the header Share button can build a deep
    # link back to exactly this trial (app._build_share_query reads it).
    st.session_state["_share_selection"] = {
        "participant_id": selected_participant,
        "trial_id": selected_trial,
    }

    parent_words = extract_trial(words_filtered, selected_participant, selected_trial)
    parent_fixations = extract_trial(
        fixations_filtered, selected_participant, selected_trial
    )
    parent_raw_gaze = pd.DataFrame()
    if raw_gaze is not None and not raw_gaze.empty:
        parent_raw_gaze = extract_trial(raw_gaze, selected_participant, selected_trial)
    screens = _part_catalog_for_display(parent_words, parent_fixations)
    with screen_slot:
        selected_screen = _render_screen_navigator(screens)
    if selected_screen is not None:
        trial_words = extract_part(
            parent_words, selected_participant, selected_trial, selected_screen
        )
        trial_fixations = extract_part(
            parent_fixations, selected_participant, selected_trial, selected_screen
        )
        if not parent_raw_gaze.empty and SCREEN_ID in parent_raw_gaze.columns:
            trial_raw_gaze = extract_part(
                parent_raw_gaze,
                selected_participant,
                selected_trial,
                selected_screen,
            )
        else:
            trial_raw_gaze = pd.DataFrame()
            if not parent_raw_gaze.empty:
                screen_slot.warning(
                    "Raw gaze has no screen identity, so it is hidden for this "
                    "multipart trial rather than concatenated across screens."
                )
        st.session_state["_share_selection"]["screen_id"] = selected_screen
        per_screen_canvas = screen_canvas_size(trial_words) or screen_canvas_size(
            trial_fixations
        )
        if per_screen_canvas is not None:
            canvas_width, canvas_height = per_screen_canvas
    else:
        trial_words = parent_words
        trial_fixations = parent_fixations
        trial_raw_gaze = parent_raw_gaze
    trial_has_raw_gaze = not trial_raw_gaze.empty
    has_raw_gaze = raw_gaze is not None and not raw_gaze.empty

    # Stimulus-page background image (MultiplEYE): the per-trial image path lives
    # on the trial's rows (directory load only — uploads carry no path). The image
    # is offered only when it exists and its pixel size is readable. Its origin
    # (image_x/image_y, where the centered stimulus sits on the monitor) places it
    # to align with the fixations, which carry the same offset.
    trial_image_path = _first_str(trial_words, "image_path") or _first_str(
        trial_fixations, "image_path"
    )
    trial_image_size = (
        _png_pixel_size(trial_image_path)
        if trial_image_path and os.path.exists(trial_image_path)
        else None
    )
    has_stimulus_image = trial_image_size is not None
    trial_image_origin = (
        _first_num(trial_words, "image_x")
        or _first_num(trial_fixations, "image_x")
        or 0.0,
        _first_num(trial_words, "image_y")
        or _first_num(trial_fixations, "image_y")
        or 0.0,
    )

    # Condition chips above the plot are filled later (into chips_slot), once the
    # comparison selection is known — so a second chip strip can show the compared
    # trial too.

    # Render the rail (plot controls) before the figure so it sees the
    # resolved Animate / Compare / viz settings; its right-side position is fixed
    # by the column split regardless of render order.
    with rail:
        # UX-44: modes, presets, palette and layers are one control system, under
        # one heading. The scoped reset used to share this row as a compact pill;
        # BUG-24 moved it to the foot of the rail (see the end of this block) —
        # the rail is ~150px wide inside, which is not enough for a heading and a
        # trigger side by side at any ordinary window size.
        with st.container(key="plot_controls_header"):
            st.markdown("## 🎛️ Plot controls")
        with rail.container(key="tour_grp_view_modes"):
            # UX-68 — the mode and its settings are ONE control, laid out the way a
            # Zoom-style split button is: the toggle switches the mode on and off,
            # the ▾ beside it opens the settings. The horizontal container is what
            # puts them on one row; it wraps rather than overflowing, so on a rail
            # too narrow for both the ▾ simply drops to the line below (which is
            # where it used to live anyway). `gap=None` is load-bearing, not taste:
            # the toggles measure ~132 px (Animate) and ~137 px (Compare) against a
            # ~195 px rail, so any gap at all puts Compare over the edge once the ▾
            # is beside it — and zero is what the fused look wants anyway. The
            # `split_mode_*` key is the hook `styles.py` draws the shared outline
            # and the divider on, and it is also what shrinks the ▾ from Streamlit's
            # default ~55 px button to a glyph's worth, which is where the rest of
            # the room comes from. The trigger renders on every run — it greys out
            # rather than disappearing, because one that comes and goes reflows the
            # row under the cursor, and because what a mode offers is part of
            # deciding whether to turn it on (so the menu opens either way; the
            # controls inside are what go disabled).
            with st.container(
                horizontal=True,
                wrap=False,
                vertical_alignment="center",
                gap=None,
                key="split_mode_animate",
            ):
                # Animate styled like a layer: a toggle + a ▾ popover for its config
                # (playback speed) — matching Compare and the visualization layers
                # below. Seeded, not `value=`-defaulted: `single_animate` is restored
                # pre-widget by a deep link / saved config (see session_keys), and
                # passing both makes Streamlit warn (BUG-17). `setdefault` suffices —
                # this toggle renders on every run, so it never first mounts late the
                # way a popover-bound widget can (that case needs
                # `persist_state="session"`; see BUG-15/ENG-36).
                st.session_state.setdefault("single_animate", False)
                animate = st.toggle(
                    "🎬 **Animate**",
                    key="single_animate",
                    persist_state="session",
                )
                # The ▾ opens whether or not Animate is on — what a mode *offers* is
                # part of deciding whether to turn it on, and a menu that refuses to
                # open shows nothing. Off, every control inside is greyed instead
                # (`anim_gate`), which is the same "your value is kept" contract the
                # rail's own mode gating uses. Disabled or not, the body always runs,
                # which is what keeps `playback_speed` / `anim_info_slot` defined.
                anim_disabled = not animate or trial_fixations.empty
                anim_gate = (
                    ""
                    if not anim_disabled
                    else "⚠️ Turn on **Animate** to change playback."
                    if not animate
                    else "⚠️ This trial has no fixations to replay."
                )
                # UX-80 r2: no `icon=` — Streamlit already draws a chevron on a
                # popover trigger, so the material arrow beside it was a second
                # one. The toggle's `help` moved here for the same pass: on a
                # widget it renders as a `?` icon, on a trigger as a plain hover
                # tooltip.
                # BUG-37: an explicit key — a blank-label popover otherwise
                # relies on Streamlit's positional auto-key, which can shift
                # across reruns and drop the open state. See `_rail_section`
                # in controls.py for the full diagnosis; this row predates
                # that helper but shares its exact shape and its exposure.
                with st.popover(
                    "",
                    width="content",
                    key="split_mode_animate_popover",
                    help="Replay settings. Playback controls appear above the plot.",
                ):
                    st.session_state.setdefault(
                        "single_playback_speed", _ANIM_DEFAULT_SPEED
                    )
                    playback_speed = _labeled(
                        st,
                        "select_slider",
                        "Playback speed",
                        options=_ANIM_SPEED_OPTIONS,
                        format_func=lambda x: _ANIM_SPEED_LABELS[
                            _ANIM_SPEED_OPTIONS.index(x)
                        ],
                        help=_gated_help(
                            "Playback speed relative to the recorded fixation timings.",
                            anim_gate,
                        ),
                        key="single_playback_speed",
                        persist_state="session",
                        disabled=anim_disabled,
                    )
                    # VIZ-10: start the replay automatically on load (at the speed
                    # above). Off → the figure waits on the ▶ Play button. UX-30
                    # moved it up here: Autoplay and speed are both "how does it
                    # play", where the frame grid below is "how is it sampled".
                    _labeled(
                        st,
                        "checkbox",
                        "Autoplay on load",
                        key="global_anim_autoplay",
                        persist_state="session",
                        disabled=anim_disabled,
                        help=_gated_help(
                            "Start playing when the plot loads.",
                            anim_gate,
                        ),
                    )
                    st.divider()

                    # VIZ-11 follow-up: the frame grid is a real tradeoff — smoothness
                    # against frame count, which is what export size and render time
                    # are made of. It used to be decided for the user in two module
                    # constants, and the cap coarsened the grid silently.
                    def _apply_anim_quality() -> None:
                        preset = _ANIM_QUALITY_PRESETS.get(
                            st.session_state.get("global_anim_quality")
                        )
                        if preset is not None:
                            (
                                st.session_state["global_anim_grid_step_ms"],
                                st.session_state["global_anim_max_frames"],
                            ) = preset

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
                    # UX-30: gating the sliders behind Custom means picking Custom on
                    # the segmented control has to be "sticky" even while the grid
                    # still equals a Coarse/Fine preset exactly (the state right after
                    # switching, before either slider is touched) — otherwise this
                    # same re-inference would immediately snap it back to that preset's
                    # name and hide the sliders that were just revealed. Only fall back
                    # to inferring Coarse/Fine here when the mode isn't already Custom;
                    # a grid matching no preset at all is unambiguous either way.
                    previous_quality = st.session_state.get("global_anim_quality")
                    if matched_quality is None:
                        st.session_state["global_anim_quality"] = "Custom"
                    elif previous_quality != "Custom":
                        st.session_state["global_anim_quality"] = matched_quality
                    _labeled(
                        st,
                        "segmented_control",
                        "Animation smoothness",
                        options=["Coarse", "Fine", "Custom"],
                        key="global_anim_quality",
                        persist_state="session",
                        on_change=_apply_anim_quality,
                        disabled=anim_disabled,
                        help=_gated_help(
                            "Fine is smoother; Coarse renders faster. Custom sets "
                            "the spacing and limit.",
                            anim_gate,
                        ),
                    )

                    def _mark_anim_quality_custom() -> None:
                        st.session_state["global_anim_quality"] = "Custom"

                    if st.session_state["global_anim_quality"] == "Custom":
                        # UX-30 put these two side by side in half-width columns,
                        # because label-above made each of them two rows tall and
                        # stacking cost four. UX-51's `label | slider | box` row is
                        # one row either way, so they go back to full width: same
                        # height, and each slider gets a usable track instead of
                        # half the popover minus its own label.
                        _numeric_slider(
                            st,
                            "Frame every (ms)",
                            key="global_anim_grid_step_ms",
                            persist_state="session",
                            label_left=True,
                            min_value=20,
                            max_value=500,
                            step=10,
                            on_change=_mark_anim_quality_custom,
                            disabled=anim_disabled,
                            help=_gated_help(
                                "Time between frames. Smaller is smoother.",
                                anim_gate,
                            ),
                        )
                        _numeric_slider(
                            st,
                            "Max frames",
                            key="global_anim_max_frames",
                            persist_state="session",
                            label_left=True,
                            min_value=30,
                            max_value=2000,
                            step=10,
                            on_change=_mark_anim_quality_custom,
                            disabled=anim_disabled,
                            help=_gated_help(
                                "Maximum replay frames; long trials are spaced "
                                "automatically.",
                                anim_gate,
                            ),
                        )
                    # Filled later, once the selected comparison trial is known.
                    # Creating the slot here keeps the resulting frame count beside
                    # the smoothness control that determines it.
                    anim_info_slot = st.container()
            # Compare is a view mode (toggle here); the second-trial selector renders
            # above the chips in the plot column (compare_slot below), mirroring the
            # main trial picker (CMP-1).
            # UX-68: same split-button row as Animate above — toggle + ▾ settings.
            # Compare config lives in the rail (moved out of the inline selector):
            # the overlay/side-by-side/stacked layout + the show-A/B-legend toggle.
            # The layout reaches the figure via session_state
            # (`single_compare_layout`), read into `compare_layout` below.
            with st.container(
                horizontal=True,
                wrap=False,
                vertical_alignment="center",
                gap=None,
                key="split_mode_compare",
            ):
                # CMP-8 §7 made this key wire format (`?compare=` turns it on), so it
                # is seeded rather than given a `value=`: an explicit default fights
                # the deep link the same way it would fight a restored config.
                st.session_state.setdefault(SINGLE_COMPARE_TOGGLE, False)
                compare_enabled = st.toggle(
                    "⚖️ **Compare**",
                    key=SINGLE_COMPARE_TOGGLE,
                    persist_state="session",
                )
                # Opens either way; greyed inside while Compare is off — see the
                # Animate row above for why the menu does not refuse to open.
                cmp_disabled = not compare_enabled
                cmp_gate = (
                    "⚠️ Turn on **Compare** to change these." if cmp_disabled else ""
                )
                # UX-80 r2: see the Animate row above — one arrow, and the
                # toggle's `help` served as a tooltip here instead of a `?`.
                # BUG-37: see the Animate row above — an explicit key so a
                # blank-label popover keeps its open state across reruns.
                with st.popover(
                    "",
                    width="content",
                    key="split_mode_compare_popover",
                    help="Compare settings. "
                    + (
                        "Co-animate a second reading on one clock."
                        if animate
                        else "Overlay another trial's scanpath or view them side "
                        "by side."
                    ),
                ):
                    # CMP-13. Deliberately "step" and not "keep them in sync":
                    # the two pools have different sizes (B excludes A, and a
                    # cross-dataset B is another corpus), so their positions
                    # carry no shared meaning — the control advances each by the
                    # same ±1, nothing more. UX-99 cut the label to "Step A + B":
                    # the rail's fixed label column truncated the old sentence to
                    # "Step both trials toge…", and the help line under it says
                    # the rest anyway.
                    _labeled(
                        st,
                        "checkbox",
                        "Step A + B",
                        key=COMPARE_STEP_LINK_KEY,
                        persist_state="session",
                        disabled=cmp_disabled,
                        help=_gated_help(
                            "◀ ▶ moves both trial pickers by one.",
                            cmp_gate,
                        ),
                    )
                    if not animate:
                        # Seed so the control shows "Overlay" selected by default
                        # (the body reads this key to resolve compare_layout).
                        st.session_state.setdefault(SINGLE_COMPARE_LAYOUT, "Overlay")
                        _labeled(
                            st,
                            "segmented_control",
                            "View",
                            options=["Overlay", "Side by side", "Stacked"],
                            format_func=lambda value: (
                                "Top & bottom" if value == "Stacked" else value
                            ),
                            label_width=0.2,
                            width="stretch",
                            key=SINGLE_COMPARE_LAYOUT,
                            persist_state="session",
                            disabled=cmp_disabled,
                            help=_gated_help(
                                "Top & bottom places one plot above the other.",
                                cmp_gate,
                            ),
                        )
                        # CMP-8 §5.3 / CMP-11: overlay pools both trials into one
                        # axis range, so across datasets it is allowed only when
                        # both were recorded on the same known screen. This note
                        # stays generic — the popover renders before B is loaded,
                        # so it cannot see B's screen. The caption under the
                        # figure has the specific answer, and the resolve happens
                        # there too, *without* rewriting the key, so a
                        # same-dataset pair gets the user's Overlay back.
                        if (
                            _compare_source_name() is not None
                            and st.session_state.get(SINGLE_COMPARE_LAYOUT) == "Overlay"
                        ):
                            st.caption(
                                "Overlay needs one coordinate space, so across "
                                "datasets it applies only when both were recorded "
                                "on the same screen. The caption under the plot "
                                "says which you got."
                            )
                        # CMP-11: two datasets' AOIs coincide only when the text
                        # is identical, so an overlay can otherwise stack two
                        # offset sets of rectangles. Overlay-only — each panel of
                        # a split layout owns its own stimulus, and dropping one
                        # would just blank half the figure.
                        if st.session_state.get(SINGLE_COMPARE_LAYOUT) == "Overlay":
                            st.session_state.setdefault(SINGLE_COMPARE_STIMULUS, "Both")
                            _labeled(
                                st,
                                "segmented_control",
                                "Stimulus from",
                                options=["Both", "A", "B"],
                                key=SINGLE_COMPARE_STIMULUS,
                                persist_state="session",
                                disabled=cmp_disabled,
                                help=_gated_help(
                                    "Which reading supplies the word boxes and "
                                    "text. Across datasets the two rarely line up.",
                                    cmp_gate,
                                ),
                            )
                    show_legend_now = _labeled(
                        st,
                        "checkbox",
                        "Show A/B legend",
                        key="global_show_compare_legend",
                        persist_state="session",
                        disabled=cmp_disabled,
                        help=_gated_help(
                            "Name scanpaths A and B on the figure.",
                            cmp_gate,
                        ),
                    )
                    if show_legend_now:
                        # UX-31: override the auto "participant · trial" label,
                        # EXP-2-style (same pattern language + live preview as
                        # the rail's title/caption). Empty = the auto label.
                        # The field vocabulary is spelled out here rather than
                        # pointed at: "same fields as the title/caption pattern"
                        # only helps a user who has already found that control.
                        label_fields = pattern_fields(
                            "p01",
                            "t01",
                            pd.DataFrame(),
                            pd.DataFrame(),
                            {},
                            dataset_name=current_dataset_name(),
                        )
                        box = st.container()
                        for idx, side in ((0, "A"), (1, "B")):
                            render_pattern_input(
                                box,
                                f"Label {side}",
                                f"cmp{idx}_label_pattern",
                                label_fields,
                                # The auto label shows *in* the box, greyed, so
                                # what an empty box gives you is readable without
                                # hovering the tooltip (UX-31).
                                placeholder=DEFAULT_COMPARE_LABEL_PATTERN,
                                help=_gated_help(
                                    "Leave empty for the auto label.", cmp_gate
                                ),
                                label_left=True,
                                disabled=cmp_disabled,
                            )
                        render_pattern_help(box, label_fields)
            # ENG-24: controls must gate against the mode the renderer can actually
            # enter, not merely the raw toggle. Compare needs at least one candidate;
            # Animate is resolved independently because it remains a distinct empty-
            # state when the selected trial has no fixations. Written after the split
            # row rather than between its two halves (UX-68) — it renders nothing, and
            # anything between the toggle and its ▾ would land inside that row.
            st.session_state["_resolved_comparing"] = bool(
                compare_enabled
                and build_comparison_options(
                    combos,
                    selection_mode,
                    selected_participant,
                    selected_trial,
                    selected_text,
                )
            )
            st.session_state["_resolved_animating"] = bool(animate)
        # The visualization controls moved out of the sidebar into this rail
        # (host=rail) so they sit beside the plot with the sidebar closed.
        viz_settings = sidebar_controls(
            fixations_filtered,
            base_font_size,
            host=rail,
            has_raw_gaze=has_raw_gaze,
            has_stimulus_image=has_stimulus_image,
            words=words_filtered,
            # The selected trial's fixations size the VIZ-7 fixation-index window
            # slider (its max is this trial's fixation count).
            fix_range_fixations=trial_fixations,
            # VIZ-31: the canvas / text panel (monitor geometry, fonts, text
            # colour, background) renders inside the rail's group order rather
            # than in the sidebar. `app.main` passes it in already bound to the
            # frames + data source, since those are app-side concerns.
            canvas_renderer=canvas_renderer,
        )
        # BUG-24: the scoped reset closes the rail, below every control it
        # resets, rather than sharing the heading row. It is last in creation
        # order, so it lands at the foot of the rail's own scroll area.
        with st.container(key="plot_reset_footer"):
            render_viz_reset(st)

    # Second-trial selector + layout/legend options, rendered above the chips in
    # the plot column (CMP-1). Filled after the rail so the per-scanpath compare
    # styles (cmp*_ keys) are already seeded — the A/B swatches then match the
    # figure exactly (CMP-3). Only shown when Compare is on.
    compare_participant, compare_trial = None, None
    compare_source: SecondaryDataset | None = None
    compare_pool: SecondaryDataset | None = None
    # Layout comes from the rail's Compare-config popover via session_state; an
    # animated comparison always co-animates on one clock, so force overlay then.
    # CMP-11: the cross-dataset *resolve* is NOT done here. It needs B's screen,
    # which only exists once `_build_compare_meta` has loaded B — see
    # `_resolve_compare_layout` further down. Nothing between here and there
    # reads `compare_layout`.
    if animate:
        requested_layout = "overlay"
    else:
        requested_layout = {
            "Overlay": "overlay",
            "Side by side": "side_by_side",
            "Stacked": "stacked",
        }.get(st.session_state.get(SINGLE_COMPARE_LAYOUT), "overlay")
    if compare_enabled:
        with compare_slot:
            compare_participant, compare_trial, compare_source, compare_pool = (
                _render_compare_selector(
                    combos,
                    selection_mode,
                    selected_participant,
                    selected_trial,
                    selected_text,
                    animate=animate,
                    # CMP-6: lets the selector order candidates by the main
                    # picker's own sort keys (fixation count, reading time, …).
                    fixations_filtered=fixations_filtered,
                    trial_words=trial_words,
                    words_filtered=words_filtered,
                    combos_all=combos_all,
                    words_all=words_all,
                    fixations_all=fixations_all,
                )
            )

    global_raw_toggle = bool(viz_settings.get("show_raw_gaze"))
    effective_show_raw_gaze = bool(global_raw_toggle and trial_has_raw_gaze)
    figure_settings = _build_figure_settings(viz_settings, effective_show_raw_gaze)
    figure_raw_gaze = trial_raw_gaze if trial_has_raw_gaze else None
    # Stimulus-image background layer (VIZ-4) — only when toggled on. A
    # user-uploaded image WINS over the dataset's built-in one (VIZ-4 fix): the
    # upload is an explicit override, so it must beat the bundled demo's / a
    # MultiplEYE session's image. The upload is stretched to fill the monitor at
    # (0,0); the dataset image carries a precise per-trial origin/size (pass the
    # path — a small cache key; plots.py base64-encodes it). Either way the manual
    # nudge below lets the user fine-tune the fit to the text + fixations.
    upload_uri = viz_settings.get("stimulus_image_upload_uri")
    if viz_settings.get("show_stimulus_image") and upload_uri:
        base_image = upload_uri
        base_size = (float(canvas_width), float(canvas_height))
        base_origin = (0.0, 0.0)
    elif viz_settings.get("show_stimulus_image") and has_stimulus_image:
        base_image = trial_image_path
        base_size = trial_image_size
        base_origin = trial_image_origin
    else:
        base_image = None
        base_size = None
        base_origin = None
    # VIZ-4: manual alignment — nudge the image origin (dx, dy) and scale its size
    # so the user can line the stimulus up with the text boxes / fixations when the
    # data's coordinate frame doesn't match the image exactly.
    if base_image is not None and base_size is not None:
        dx = float(viz_settings.get("stimulus_image_offset_x", 0.0))
        dy = float(viz_settings.get("stimulus_image_offset_y", 0.0))
        scale = float(viz_settings.get("stimulus_image_scale", 1.0)) or 1.0
        ox, oy = base_origin or (0.0, 0.0)
        figure_settings["background_image"] = base_image
        figure_settings["background_image_size"] = (
            base_size[0] * scale,
            base_size[1] * scale,
        )
        figure_settings["background_image_origin"] = (ox + dx, oy + dy)
    else:
        figure_settings["background_image"] = None
        figure_settings["background_image_size"] = None
        figure_settings["background_image_origin"] = None
    # Opacity applies to whichever image is shown (dataset or uploaded); harmless
    # when no image is drawn.
    figure_settings["background_image_opacity"] = viz_settings.get(
        "stimulus_image_opacity", 1.0
    )
    # Carried into both the live figure and the bulk export so exported plots are
    # sized identically to what's on screen (true-to-scale reading text).
    figure_settings["line_spacing"] = line_spacing
    figure_settings["scale_text_to_boxes"] = scale_text_to_boxes
    x_field = viz_settings["x_field"]
    y_field = viz_settings["y_field"]

    # Second trial's words/fixations + labels for the comparison figure and the
    # side-by-side Trial Info / metadata table.
    # B owns an independent filter pool even when it comes from this dataset.
    # Extracting its selection from A's filtered frames makes a valid B choice
    # disappear whenever A's filters exclude it — exactly what the separate B
    # filters are meant to prevent. The source remains None for a local pool so
    # downstream labels, geometry and participant ids retain same-dataset rules.
    compare_words_pool = (
        compare_pool.words if compare_pool is not None else words_filtered
    )
    compare_fixations_pool = (
        compare_pool.fixations if compare_pool is not None else fixations_filtered
    )
    compare_meta = _build_compare_meta(
        compare_words_pool,
        compare_fixations_pool,
        selected_participant,
        selected_trial,
        compare_participant,
        compare_trial,
        selected_screen,
        source=compare_source,
        # CMP-15: A's corpus, so a cross-dataset pair names both sides.
        primary_dataset=str(st.session_state.get("data_source_choice") or ""),
    )
    comparing = compare_meta is not None
    # CMP-8 §7: publish B for the Share link, alongside A above. Always the
    # *real* ids, never the namespaced ones — a link names readers as their own
    # corpus does. `source` is None for a same-dataset comparison.
    share_selection = st.session_state.get("_share_selection")
    if isinstance(share_selection, dict):
        if comparing and compare_meta is not None:
            share_selection["compare"] = {
                "participant_id": compare_meta["raw_participant"],
                "trial_id": compare_meta["trial"],
                "source": compare_meta.get("dataset"),
            }
        else:
            share_selection.pop("compare", None)
    # CMP-8: from here on, B's *figure* id is the namespaced one — the merged
    # frames below carry it, and `make_comparison_figure` slices by exactly that.
    figure_compare_participant = (
        compare_meta["participant"] if compare_meta else compare_participant
    )
    cross_dataset = bool(compare_meta and compare_meta.get("dataset"))
    compare_fix = compare_meta["fixations"] if compare_meta else pd.DataFrame()
    # CMP-11: the one predicate both gates below consult. Computed here because
    # this is the first point B's screen is known.
    # The *trial's* frames, not the filtered corpus: A's canvas is overwritten with
    # the rendered one on the next line anyway, so the only thing that survives is
    # the provenance — which comes from the source→monitor table, not the data. The
    # fallback branch of `resolve_source_monitor` scans every row of whatever it is
    # given, which on a full corpus is tens of milliseconds per rerun for a value
    # that is then discarded.
    compare_comparable, compare_setup_note = _compare_setups(
        compare_meta, trial_words, trial_fixations, canvas_width, canvas_height
    )
    # Resolve, don't rewrite (CMP-8 §5.3): `single_compare_layout` is left alone,
    # so switching back to a same-dataset pair restores the user's Overlay.
    compare_layout = requested_layout
    if compare_layout == "overlay" and not compare_comparable:
        compare_layout = "side_by_side"
    # CMP-11: widget label -> the wire/settings vocabulary the builders take.
    compare_stimulus = {"Both": "both", "A": "a", "B": "b"}.get(
        str(st.session_state.get(SINGLE_COMPARE_STIMULUS) or "Both"), "both"
    )

    # Fixation-index window (VIZ-7): the frames that feed the figure / animation
    # are sliced to the chosen range; the full frames still drive the chips,
    # panels and exports. A None range leaves the frames untouched.
    fix_range = viz_settings.get("fix_index_range")
    fig_fixations = _slice_fix_range(trial_fixations, fix_range)
    fig_compare_fix = _slice_fix_range(compare_fix, fix_range)
    full_fix_range = None
    if not trial_fixations.empty and "order_in_trial" in trial_fixations.columns:
        order = pd.to_numeric(
            trial_fixations["order_in_trial"], errors="coerce"
        ).dropna()
        if not order.empty:
            full_fix_range = (int(order.min()), int(order.max()))
    detected_reasons = illustration_reasons(
        {
            **viz_settings,
            "playback_speed": playback_speed if animate else 1.0,
        },
        data_source=st.session_state.get("_active_data_source"),
        fix_index_range=fix_range,
        full_fixation_range=full_fix_range,
        raw_gaze_only=trial_fixations.empty
        and raw_gaze is not None
        and not raw_gaze.empty,
    )
    label_reasons = resolve_label_reasons(
        viz_settings.get("illustration_label", "Auto"), detected_reasons
    )
    viz_settings["illustration_reasons"] = label_reasons
    figure_settings["illustration_reasons"] = label_reasons
    render_settings = FigureSettings.from_mapping(
        figure_settings,
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
        base_font_size=int(base_font_size),
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
        # CMP-11: the dual animation draws ONE stimulus layer, so "B" is what
        # stops a cross-dataset co-animation running B's trace over A's text.
        # The comparison branch re-applies this through `with_overrides`.
        compare_stimulus=compare_stimulus,
    )

    # PRE-3 drift correction (VIZ-23) — hoisted ABOVE the render-mode split, so the
    # two Drift-correction controls apply on ALL THREE paths instead of the static
    # figure alone. Each scanpath is corrected against its OWN words frame, on the
    # already-windowed fixations (so the algorithm sees exactly what is drawn, as
    # the static path always did). What each builder can then do with it:
    #   • static     — snapped y + colour-by-line + optional original→corrected
    #                  connectors (it is the only builder with a connector layer);
    #   • animation  — snapped y + colour-by-line on the single replay. No
    #                  connectors: the replay reveals one growing trail, and a
    #                  full-length static "original position" layer standing there
    #                  from frame zero would misread as part of the scanpath.
    #   • comparison — snapped y for both scanpaths; that builder has neither a
    #                  colour-by-line nor a connector layer, so correction is the
    #                  whole of it.
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
    # `make_comparison_figure` pulls exactly the two selected trials out of the
    # frame it is handed (its shared colour range included), so a frame holding
    # just those two corrected scanpaths is equivalent to patching the whole
    # filtered corpus — and far cheaper. Untouched when correction is off.
    # CMP-8 §3: two corpora rarely ship the same columns, and a bare concat of
    # disjoint frames warns and churns dtypes — align onto the union first. The
    # shared numeric set feeds the §5.4 metric gate below.
    shared_numeric: frozenset[str] | None = None
    if comparing and compare_meta is not None:
        words_a, words_b, _ = _align_compare_columns(trial_words, compare_meta["words"])
        fix_a, fix_b, shared_fix = _align_compare_columns(
            plot_fixations, plot_compare_fix
        )
        cmp_words = pd.concat([words_a, words_b])
        cmp_fixations = pd.concat([fix_a, fix_b])
        if cross_dataset:
            shared_numeric = shared_fix
    else:
        cmp_words = trial_words
        cmp_fixations = plot_fixations

    # Condition chips above the plot — configurable via the sidebar picker
    # (`trial_chip_fields`); `Field = Value` for the chosen fields. When comparing,
    # a second labelled strip shows the compared trial too.
    # UX-75 — one line per reading: its **title on the left**, its chips filling
    # the rest, and the row's controls in the trailing track. The line takes
    # `SELECTOR_ROW_TRIO` — the control-line grid with the trial and scrub
    # tracks merged — so the title sits under the dataset picker, the chips
    # under the trial picker and scrubber, and **Summary stats** / ✏️ under ◀ ▶ ⇅.
    color_a = color_b = None
    if comparing and compare_meta:
        # Each title takes the colour of the scanpath it names (A = primary,
        # B = compared), which is what replaced the old "■ A … ■ B compared
        # with:" legend line.
        _ca, _cb = _collect_compare_styles()
        color_a = _ca.get("fix_color") or compare_palette_color(0)
        color_b = _cb.get("fix_color") or compare_palette_color(1)
    with chips_slot:
        # Inline "Edit chips" popover at the right end of the row (UX-1) —
        # replaces the former sidebar 🏷️ Trial chips picker. Rendered before the
        # strip reads `trial_chip_fields` so an edit/reorder applies the same run.
        # Top-aligned, not centre-aligned: the strip wraps to several lines
        # (UX-11), and a centred control would drift to the middle of a tall
        # strip instead of sitting on the first chip's line.
        # UX-27: **Summary stats** and ✏️ share ONE trailing column, as a `railbtn_*`
        # cluster — styles.py lays every such container out as a right-packed
        # flex row, so this row's pair ends flush with the ◀ ▶ ⇅ cluster above.
        # The Participant chip already identifies the reading. Do not repeat
        # the same id in a title cell; use that width for the chip strip in both
        # ordinary and Compare modes.
        strip_col, trail_col = st.columns(
            SELECTOR_ROW_WIDE_GRID, vertical_alignment="top"
        )
        trail = trail_col.container(key="railbtn_chip_trail")
        # Created in display order (Summary stats, then ✏️) but filled out of order:
        # the popover body needs `summary`, which the strip below computes.
        details_box = trail.container(key="railbtn_chip_details")
        edit_box = trail.container(key="railbtn_chip_edit")
        with edit_box.popover(
            "✏️",
            help="Edit which fields show as chips above the plot, and drag to "
            "reorder them.",
            width="content",
        ):
            render_trial_chip_picker(words_all, fixations_all, host=st.container())
        chip_fields = st.session_state.get("trial_chip_fields") or []
        with strip_col:
            summary = _render_trial_condition_chips(
                trial_words,
                trial_fixations,
                selected_participant,
                chip_fields,
                leading_chip=(f"Trial ID = {selected_trial}", color_a)
                if comparing and color_a
                else None,
            )
        # Rendered after the strip so it reads the *primary* trial's stats.
        _render_trial_details_popover(summary, details_box)
    if comparing and compare_meta:
        with compare_chips_slot:
            # B's own line, directly under B's control row. No ✏️ or **Summary stats**
            # of its own: the chip fields are one setting for both readings, and
            # the summary popover describes the trial the panels are anchored on.
            b_strip, _b_trail = st.columns(
                SELECTOR_ROW_WIDE_GRID, vertical_alignment="top"
            )
            with b_strip:
                _render_trial_condition_chips(
                    compare_meta["words"],
                    compare_meta["fixations"],
                    compare_participant,
                    chip_fields,
                    leading_chip=(f"Trial ID = {compare_trial}", color_b),
                )

    # CMP-8 §6: the two halves of the pair bundle, built from the *unqualified*
    # frames and real ids — the `dataset · pid` namespace is a figure-internal
    # device and must never reach an exported table. `None` unless comparing.
    compare_export_sides = None
    if comparing and compare_meta is not None:
        # Lazy: `app` imports `tabs`, so a module-level import closes the cycle.
        from scanpath_studio.app import active_setup_snapshot

        compare_export_sides = (
            ComparisonSide(
                participant=str(selected_participant),
                trial=str(selected_trial),
                words=trial_words,
                fixations=trial_fixations,
                dataset=None,
                setup=(
                    snapshot.to_dict()
                    if (snapshot := active_setup_snapshot()) is not None
                    else None
                ),
            ),
            ComparisonSide(
                participant=str(compare_meta["raw_participant"]),
                trial=str(compare_meta["trial"]),
                # Strip the namespacing back off: `_qualify_for_compare` rewrote
                # `participant_id` for the figure's benefit only.
                words=_unqualify_for_export(
                    compare_meta["words"], compare_meta["raw_participant"]
                ),
                fixations=_unqualify_for_export(
                    compare_meta["fixations"], compare_meta["raw_participant"]
                ),
                dataset=compare_meta.get("dataset"),
                setup=(
                    compare_meta["setup"].to_dict()
                    if compare_meta.get("setup") is not None
                    else None
                ),
            ),
        )

    displayed_fig = None
    save_slug = f"{selected_participant}__{selected_trial}"
    anim_playback_ms = None
    anim_file_stem = None
    # Use the windowed second scanpath: a window that empties B falls back to a
    # single-trial animation (and info box). A co-animation is an overlay on one
    # clock, so it needs one coordinate space — which is the same question the
    # overlay layout asks. CMP-11 therefore gates it on the same predicate
    # instead of refusing every cross-dataset pair outright (CMP-8 §5.3).
    dual_anim = (
        animate
        and comparing
        and not fig_compare_fix.empty
        and (not cross_dataset or compare_comparable)
    )

    # Animation info box, in its slot inside the rail's Playback popover.
    if animate and not fig_fixations.empty and anim_info_slot is not None:
        with anim_info_slot:
            # VIZ-25: quote the same timeline the replay draws. The animation
            # builder drops Discard-mode fixation classes internally; apply the
            # shared classifier here too so the info box cannot count hidden rows.
            info_fixations = _discard_flagged_fixations(
                fig_fixations,
                trial_words,
                viz_settings.get("fixation_flags"),
            )
            info_compare_fix = (
                _discard_flagged_fixations(
                    fig_compare_fix,
                    compare_meta["words"],
                    viz_settings.get("fixation_flags"),
                )
                if dual_anim
                else None
            )
            _render_anim_info_box(
                trial_words,
                info_fixations,
                compare_meta["words"] if dual_anim else None,
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
        if global_raw_toggle and not trial_has_raw_gaze:
            st.warning("Raw gaze not available for this trial.", icon="⚠️")
        if animate and trial_fixations.empty:
            st.info(
                "Animation needs a **fixations** table — there's nothing to "
                "animate for this selection."
            )
        elif animate:
            # Building the per-fixation animation frames takes a moment — show a
            # loading banner so the screen isn't blank meanwhile.
            with st.spinner("Building animation…"):
                displayed_fig, anim_playback_ms, save_slug, anim_file_stem = (
                    _build_and_render_animation(
                        trial_words,
                        plot_fixations,
                        compare_meta["words"] if dual_anim else None,
                        plot_compare_fix if dual_anim else None,
                        selected_participant,
                        selected_trial,
                        compare_participant,
                        compare_trial,
                        dataset_name_b=_compare_dataset_name(compare_meta),
                        settings=render_settings,
                        viz_settings=viz_settings,
                        playback_speed=playback_speed,
                        drift_corrected=drift_corrected_primary,
                    )
                )
            if comparing and cross_dataset and not compare_comparable:
                st.warning(
                    "An animated comparison replays both scanpaths on one clock "
                    f"in one coordinate space. {compare_setup_note} Showing "
                    "only the first scanpath.",
                    icon="⚠️",
                )
            elif comparing and compare_fix.empty:
                st.warning(
                    "The selected second scanpath has no fixations after "
                    "filtering — showing only the first scanpath."
                )
        elif comparing:
            displayed_fig = _render_comparison_figure(
                combos,
                cmp_words,
                cmp_fixations,
                selected_participant,
                selected_trial,
                selected_text,
                figure_compare_participant,
                compare_trial,
                render_settings,
                viz_settings,
                layout=compare_layout,
                compare_stimulus=compare_stimulus,
                fix_index_range=fix_range,
                compare_meta=compare_meta,
                shared_numeric=shared_numeric,
                setup_note=compare_setup_note,
            )
            save_slug = (
                f"{selected_participant}__{selected_trial}__vs__"
                f"{compare_participant}__{compare_trial}"
            )
        else:
            # PRE-3: the corrected frame (`plot_fixations`) was built above and is
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
            static_settings = render_settings.with_overrides(**extra_settings)
            build_inputs = static_settings.for_builder(STATIC_FIGURE_OPTIONS)
            build_inputs["raw_gaze"] = figure_raw_gaze
            displayed_fig = _cached_scanpath_figure(
                trial_words,
                plot_fixations,
                static_settings,
                figure_raw_gaze,
                fig_key=_figure_input_key(trial_words, plot_fixations, build_inputs),
            )
            _apply_preprocessing_caption(
                displayed_fig, selected_participant, selected_trial
            )
            _primary_combo = combos[
                (combos["participant_id"] == selected_participant)
                & (combos["trial_id"] == selected_trial)
            ]
            _apply_title_caption(
                displayed_fig,
                viz_settings,
                trial_words,
                plot_fixations,
                selected_participant,
                selected_trial,
                combo_row=(
                    _primary_combo.iloc[0].to_dict()
                    if not _primary_combo.empty
                    else None
                ),
            )
            _render_true_scale_chart(displayed_fig, key="single")

    # Per-trial panels sit directly BELOW the plot, in the next row's left column. Trial
    # Info is gone — the chip strip above the plot now carries the trial's identity,
    # conditions and summary stats (configurable via the ✏️ chip editor).
    # The reserved keyed slot remains the welcome-tour spotlight target.
    with subtabs_slot:
        # PRE-21: 📐 Line assignment is only offered while drift correction is
        # exposed. Built as a list rather than a fixed tuple for exactly that
        # reason — the tab count is now a function of the flag.
        subtab_labels = [SUBTAB_ANNOTATIONS, SUBTAB_STIMULUS, SUBTAB_COMPARISONS]
        if drift_correction_enabled():
            subtab_labels.append(SUBTAB_LINE_ASSIGNMENT)
        # DATA-26: 🔎 Data Inspection left this bar for the **Data** page —
        # inspecting a dataset is setting it up, and it was on the opposite side
        # of the app from the source picker and the column mapping.
        subtab_labels += [SUBTAB_EXPORT, SUBTAB_SHARE]
        _subtabs = st.tabs(
            subtab_labels,
            # PERF-3: `st.tabs` executes EVERY tab's body on every run — only the
            # display is client-side — so the four expensive panels below were
            # rebuilt on every rail tweak whether or not the user had ever opened
            # them. On the bundled demo that was 42% of a rerun (480ms → 277ms
            # with them stubbed out), and it scales with corpus size.
            #
            # Streamlit 1.61's keyed tabs are the native fix: with a `key` and
            # `on_change="rerun"`, each tab object exposes `.open`, so a body can
            # be rendered only when its tab is the selected one. The trade is that
            # switching tabs now costs a rerun instead of being instant — worth it
            # at ~0.3s, and the tab the user is actually looking at is the one
            # that stays fast.
            key="single_subtab",
            on_change="rerun",
        )
        by_label = dict(zip(subtab_labels, _subtabs))
        tab_annot = by_label[SUBTAB_ANNOTATIONS]
        tab_stim = by_label[SUBTAB_STIMULUS]
        tab_compare = by_label[SUBTAB_COMPARISONS]
        tab_align = by_label.get(SUBTAB_LINE_ASSIGNMENT)
        tab_export = by_label[SUBTAB_EXPORT]
        tab_share = by_label[SUBTAB_SHARE]
    with tab_annot, st.container(key="tutorial_annotations"):
        render_trial_annotations(
            selected_participant,
            selected_trial,
            screen_id=selected_screen,
            bare=True,
        )
    with tab_stim:
        _render_paragraph_panel(trial_words, trial_fixations=trial_fixations, bare=True)
    with tab_compare:
        # PERF-3: only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_compare.open:
            # UX-94: the chosen column selects other trials with the same value
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
                )

    # PRE-21: absent entirely while drift correction is gated off.
    with tab_align if tab_align is not None else contextlib.nullcontext():
        # PERF-3: only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_align is not None and tab_align.open:
            # PRE-3: the drift-correction algorithm comparison grid, on the same
            # selected trial. Unnested from Comparisons to its own subtab (ENG-8).
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
        # PERF-3: only the selected tab's body runs (see the st.tabs call).
        # Nothing to render when closed — a hidden panel is not on screen.
        if tab_export.open:
            with st.container(key="tutorial_export"):
                _render_export_panel(
                    displayed_fig,
                    animate=animate,
                    save_slug=save_slug,
                    playback_ms=anim_playback_ms,
                    file_stem=anim_file_stem,
                    combos=combos,
                    words_filtered=words_filtered,
                    fixations_filtered=fixations_filtered,
                    combos_all=combos_all,
                    words_all=words_all,
                    fixations_all=fixations_all,
                    raw_gaze=raw_gaze if raw_gaze is not None else pd.DataFrame(),
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    base_font_size=base_font_size,
                    font_family=font_family,
                    viz_settings=viz_settings,
                    line_spacing=line_spacing,
                    scale_text_to_boxes=scale_text_to_boxes,
                    selected_participant=selected_participant,
                    selected_trial=selected_trial,
                    compare_export=compare_export_sides,
                )

    # The former header Share popover, now a subtab. app.main passes the
    # renderer (it owns the deep-link builder + data source). Keyed wrapper →
    # the spotlight target for the publication-figure tutorial (UX-40).
    with tab_share, st.container(key="tutorial_share"):
        if share_renderer is not None:
            share_renderer()
        else:
            st.caption("Sharing is unavailable in this context.")

    # Save & restore (plot config + annotations) is rendered by app.main on every
    # view (it must stay reachable when a non-Scanpath view is active), sourcing
    # the trial selection from _share_selection.


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
) -> None:
    """Render configurable bulk-export UI (artifact picker + run + download)."""
    options = render_export_options(
        st,
        combos,
        key_prefix="bulk_export",
        combos_all=combos_all,
        title_pattern=figure_settings.get("title_pattern", ""),
        caption_pattern=figure_settings.get("caption_pattern", ""),
        selected_participant=selected_participant,
        selected_trial=selected_trial,
    )
    # Tick "Export the whole dataset" → export the unfiltered frames.
    if options.export_unfiltered:
        active_combos, active_words, active_fix = combos_all, words_all, fixations_all
    else:
        active_combos, active_words, active_fix = (
            combos,
            words_filtered,
            fixations_filtered,
        )
    run_col, info_col = st.columns([1, 3])
    with run_col:
        run = st.button(
            "Build export",
            type="primary",
            disabled=(
                active_combos.empty
                or not (
                    options.figure_formats()
                    or options.include_plot_config
                    or options.any_table()
                )
            ),
        )
    sig = (
        frame_fingerprint(active_combos),
        frame_fingerprint(active_words),
        frame_fingerprint(active_fix),
        frame_fingerprint(raw_gaze),
        int(canvas_width),
        int(canvas_height),
        int(base_font_size),
        str(font_family),
        str(x_field),
        str(y_field),
        json.dumps(figure_settings, sort_keys=True, default=str),
        repr(options),
        EXPORTER_VERSION,
    )
    cache = st.session_state.get("_bulk_export_cache")
    if cache and cache.get("sig") != sig:
        st.session_state.pop("_bulk_export_cache", None)
        cache = None

    if run:
        status_box = info_col.status("Preparing bulk export…", expanded=True)
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
                # PERF-6: over a real corpus this runs for hours, so the bar
                # carries the rate and the time left, not just the count.
                text = progress_caption(status)
                if progress_bar is None:
                    progress_bar = progress_slot.progress(status.fraction, text=text)
                else:
                    progress_bar.progress(status.fraction, text=text)

        try:
            zip_bytes, progress = bulk_export(
                active_combos,
                active_words,
                active_fix,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                base_font_size=base_font_size,
                font_family=font_family,
                x_field=x_field,
                y_field=y_field,
                settings=figure_settings,
                options=options,
                raw_gaze=raw_gaze,
                status_callback=on_status,
            )
        except Exception as exc:
            progress_slot.empty()
            status_box.update(label=f"Export failed: {exc}", state="error")
            st.session_state.pop("_bulk_export_cache", None)
            st.warning(f"Could not build export: {exc}")
            cache = None
        else:
            progress_slot.empty()
            cache = {"sig": sig, "data": zip_bytes, "progress": progress}
            st.session_state["_bulk_export_cache"] = cache

    if cache and cache.get("sig") == sig:
        zip_bytes = cache["data"]
        progress = cache["progress"]
        info_col.success(f"Ready · {len(zip_bytes) / 1_048_576:.1f} MB")
        if progress.errors:
            with st.expander("Export warnings"):
                for err in progress.errors:
                    st.write(err)
        st.download_button(
            "Download zip",
            data=zip_bytes,
            file_name=f"scanpath_export_{pd.Timestamp.now('UTC'):%Y%m%d_%H%M%S}.zip",
            mime="application/zip",
            type="primary",
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
    fix_index_range=None,
    compare_meta: dict | None = None,
    shared_numeric: frozenset[str] | None = None,
    setup_note: str = "",
):
    """Render comparison figure for two trials.

    ``fix_index_range`` (VIZ-7) windows both scanpaths to a ``(start, end)``
    ``order_in_trial`` range; ``None`` shows the full readings. Shared visual
    choices, canvas geometry, and the stimulus image arrive in ``settings``.

    ``fixations_filtered`` may already carry PRE-3 drift-corrected ``y`` values —
    correction happens once, upstream of the render-mode split.

    **CMP-8**: when ``compare_meta`` names a ``dataset``, B came from a different
    corpus. Its text id then comes from ``compare_meta`` rather than a lookup in
    A's ``combos`` (which cannot know a foreign trial), B's panel is drawn to B's
    own monitor (``canvas_b``), and a caption below the figure says so —
    panel sizes are not comparable when the two screens differ. ``shared_numeric``
    is §5.4's metric intersection; a ``color_by`` absent from one side would
    colour one panel and blank the other, so it is dropped with a note.

    **CMP-11**: ``setup_note`` is `experimental_setup.setups_comparable`'s
    sentence about the two screens — either why the pair could not be overlaid,
    or, on an overlay that *was* allowed, the caveat that the matching canvas is
    a shared default rather than a recorded screen. Empty when neither applies.
    It surfaces where the user is looking (a warning under an overlay, appended
    to the caption under a split layout) rather than only in the rail's
    popover."""
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    cross_dataset = bool(compare_meta and compare_meta.get("dataset"))
    # Window both compared trials to the chosen fixation-index range. Slicing the
    # whole frame is fine — make_comparison_figure only extracts the two trials.
    fixations_filtered = _slice_fix_range(fixations_filtered, fix_index_range)

    def _lookup_text_id(participant_id: str, trial_id: str) -> str | None:
        match = combos[
            (combos["participant_id"] == participant_id)
            & (combos["trial_id"] == trial_id)
        ]
        if match.empty or text_field not in match.columns:
            return None
        return str(match.iloc[0][text_field])

    label_pool: set[str] = set()
    primary_text_id = selected_text or _lookup_text_id(
        selected_participant, selected_trial
    )
    compare_text_id = (
        compare_meta.get("text_id")
        if cross_dataset
        else _lookup_text_id(compare_participant, compare_trial)
    )
    primary_label = friendly_trial_label(
        selected_participant, selected_trial, primary_text_id, label_pool
    )
    compare_label = friendly_trial_label(
        compare_participant, compare_trial, compare_text_id, label_pool
    )
    # UX-31: an explicit cmp{idx}_label_pattern overrides the auto label above.
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
            extract_trial(words_filtered, compare_participant, compare_trial),
            extract_trial(fixations_filtered, compare_participant, compare_trial),
            dataset_name=_compare_dataset_name(compare_meta),
        )

    overrides: dict = dict(
        trial_labels=(primary_label, compare_label),
        layout=layout,
        compare_stimulus=compare_stimulus,
        style_a=viz_settings.get("compare_style_a"),
        style_b=viz_settings.get("compare_style_b"),
        show_legend=viz_settings.get("show_compare_legend", False),
        # Comparison retains its count-vs-duration spelling; the static builder
        # translates "counts" to None internally.
        heatmap_metric=viz_settings.get("heatmap_metric", "duration_ms"),
        highlight_column=_marked_text_column(viz_settings),
    )
    dropped_metric = None
    if cross_dataset:
        # §4: B's panel is drawn to B's own monitor. Only the split layouts read
        # this; overlay never gets here (§5.3 resolves it away).
        setup_b = compare_meta.get("setup")
        if setup_b is not None:
            overrides["canvas_b"] = setup_b.canvas

        # §5.4: a metric only one corpus ships would colour one panel and blank
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
    fig_compare = make_comparison_figure(
        words_filtered,
        fixations_filtered,
        (selected_participant, selected_trial),
        (compare_participant, compare_trial),
        settings=comparison_settings,
    )
    add_illustration_label(fig_compare, viz_settings.get("illustration_reasons"))
    _apply_preprocessing_caption(fig_compare, selected_participant, selected_trial)
    _primary_combo = combos[
        (combos["participant_id"] == selected_participant)
        & (combos["trial_id"] == selected_trial)
    ]
    _apply_title_caption(
        fig_compare,
        viz_settings,
        extract_trial(words_filtered, selected_participant, selected_trial),
        extract_trial(fixations_filtered, selected_participant, selected_trial),
        selected_participant,
        selected_trial,
        combo_row=(
            _primary_combo.iloc[0].to_dict() if not _primary_combo.empty else None
        ),
        # VIZ-36: two readings in one figure, so `{dataset_name_b}` and friends
        # have a value to resolve against.
        compare_row={
            "dataset_name": _compare_dataset_name(compare_meta),
            "participant_id": compare_participant,
            "trial_id": compare_trial,
            "text_id": compare_text_id,
        },
    )
    _render_true_scale_chart(fig_compare, key="compare")
    if cross_dataset:
        # §5.3: the one thing a cross-dataset figure must never be is silent
        # about its own geometry. Each panel is true-to-scale on its *own*
        # monitor, so a box twice the size of the one beside it may be the same
        # physical size — naming both screens is what keeps that readable.
        active = st.session_state.get("data_source_choice") or "this dataset"
        setup_b = compare_meta.get("setup")
        canvas_a = (settings.canvas_width, settings.canvas_height)
        canvas_b = setup_b.canvas if setup_b is not None else canvas_a
        if layout == "overlay":
            # CMP-11: a cross-dataset pair only reaches the overlay on equal
            # canvases, so the caption states the ground it stands on. When
            # `setup_note` is non-empty the canvases matched but at least one
            # corpus never *recorded* a screen — the overlay is still drawn (the
            # user usually knows the two displays matched even when the data
            # can't say so), and the caveat is raised to a warning rather than
            # buried in the caption, because it qualifies what the figure means.
            st.caption(
                f"Overlaid across datasets — {active} and "
                f"{compare_meta['dataset']}, both at "
                f"{canvas_a[0]}×{canvas_a[1]}. Positions are comparable in "
                "screen pixels; nothing has been rescaled."
            )
            if setup_note:
                st.warning(setup_note, icon="⚠️")
        elif tuple(canvas_a) != tuple(canvas_b):
            st.caption(
                "Panels are drawn to each dataset's own screen — "
                f"{active} {canvas_a[0]}×{canvas_a[1]}, "
                f"{compare_meta['dataset']} {canvas_b[0]}×{canvas_b[1]}. "
                "Sizes are not comparable across panels."
                + (f" {setup_note}" if setup_note else "")
            )
        else:
            st.caption(
                f"Comparing across datasets — {active} and "
                f"{compare_meta['dataset']} — which happen to share a "
                f"{canvas_a[0]}×{canvas_a[1]} screen."
                + (f" {setup_note}" if setup_note else "")
            )
    if dropped_metric:
        st.caption(
            f"⚠️ **{dropped_metric}** isn't in both datasets, so it can't colour "
            "this comparison. Your choice is kept for same-dataset comparisons."
        )
    return fig_compare


# -----------------------------------------------------------------------------
# Corpus Analysis Tab  (Per text · Per reader · Groups subtabs)
# -----------------------------------------------------------------------------

# --- Cached analysis wrappers ------------------------------------------------
# Each wraps a pure ``aggregation`` helper with ``@st.cache_data`` keyed on a
# cheap frame *fingerprint* (``fkey``) + hashable scalars (the measure key,
# aggregation/spread, flags), mirroring the existing cached-aggregation pattern.
# Frames pass
# un-hashed (underscore args). Group views feed a pre-filtered frame, so its
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
def _c_word_box_aggregate(_words, text_col, text_id, mkey, agg, fkey, screen=None):
    return word_box_aggregate(
        _words, text_col, text_id, MEASURES[mkey], agg=agg, screen_id=screen
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


@st.cache_data(show_spinner=False)
def _c_enrich_fix(_fix, _words, ffkey, fwkey):
    return ensure_fixation_enrichment(_fix, _words)


# --- Cross-cutting analysis controls (AN-23 … AN-27) -------------------------

_AGG_OPTIONS = ["mean", "median", "sum"]
_SPREAD_OPTIONS = ["SD", "SEM", "IQR", "Bootstrap CI"]

# Friendly labels for the common condition columns the group pickers expose
# (mirrors controls._FILTER_FIELD_LABELS without importing it).
_GROUP_COL_LABELS = {
    "difficulty_level": "Difficulty",
    "question_preview": "Reading regime",
    "repeated_reading_trial": "Reading number",
    "is_correct": "Answer",
    "participant_id": "Participant",
    "genre": "Genre",
    "session": "Session",
    "pp_gender": "Gender",
}


def _pretty_col(col: str) -> str:
    """Friendly label for a raw column id (group-definition pickers).

    A ``meta:`` option is labelled with the field's own label and marked as
    coming from the attached participant table — the two provenances answer
    different questions ("this trial's condition" vs "this reader's language")
    and a picker that hid the difference would invite the wrong one.
    """
    name = _meta_field_name(col)
    if name is not None:
        from scanpath_studio import metadata as md

        # `metadata.field_label`, not the attached table's own `field.label`:
        # a `format_func` can be called when `md.active()` is out of reach (no
        # script run — Streamlit's own widget-state bookkeeping does this), and
        # a label that changes with the caller's context is a label that flickers.
        return f"👤 {md.field_label(name)}"
    return _GROUP_COL_LABELS.get(col, str(col).replace("_", " ").strip().title())


def _measure_picker(
    words, fixations, *, key, host=None, per_word_only=False, label="Measure"
) -> Measure | None:
    """The shared measure picker (AN-23) — TFD default, only present columns."""
    host = host or st
    ms = available_measures(words, fixations, per_word_only=per_word_only)
    if not ms:
        host.info("No aggregatable measures found in this dataset.")
        return None
    labels = {m.label: m.key for m in ms}
    options = list(labels)
    default = "Total fixation duration — TFD"
    index = options.index(default) if default in options else 0
    chosen = host.selectbox(
        label,
        options=options,
        index=index,
        key=key,
        help="The eye-movement measure every view in this section reads.",
    )
    return MEASURES[labels[chosen]]


def _normalize_toggle(host, *, key, disabled=False):
    """Z-score-within-reader toggle (AN-25)."""
    return bool(
        host.toggle(
            "Z-score within reader",
            value=False,
            key=key,
            disabled=disabled,
            help="Compare slow vs fast readers on shape, not absolute level.",
        )
    )


def _min_readers_input(host, *, key, label="Min readers per word", default=1):
    """Min-observations guard (AN-26)."""
    return int(
        host.number_input(
            label,
            min_value=1,
            max_value=999,
            value=default,
            step=1,
            key=key,
            help="Words backed by fewer observations are dropped.",
        )
    )


def _download_tidy(host, df, *, name, key, label="⬇ Download this table (CSV)"):
    """Per-view tidy-table download (AN-27)."""
    if df is None or getattr(df, "empty", True):
        return
    host.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=name,
        mime="text/csv",
        key=key,
    )


#: Cell text of the "open this trial" button. `st.column_config.ButtonColumn`
#: takes the button's label from the cell *value*, so this is data, not config.
_OPEN_TRIAL_LABEL = ":material/open_in_new: Open"


def _render_trials_with_open_button(
    trials: pd.DataFrame, participant: str | None, *, key: str
) -> None:
    """A per-trial summary table whose rows open the trial (ENG-36).

    Corpus Analysis lists a reader's trials with their numbers; acting on one
    meant reading its id off the table, switching to the Scanpath view and
    hunting it down in the picker. Streamlit 1.61's `ButtonColumn` puts the jump
    in the row it belongs to.

    The click arrives as a *callback*, before the script rebuilds ``combos``, so
    it can't seed the picker itself — it parks the request via
    ``url_state.request_trial`` and ``app.main`` applies it once the trial pool
    exists, the same hop a ``?trial_id=`` deep link takes.
    """
    if trials is None or trials.empty or "trial_id" not in trials.columns:
        st.dataframe(trials, width="stretch", hide_index=True)
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
            "Open": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="Show this trial's scanpath in the Scanpath view.",
                on_click=_open,
                key=click_key,
            )
        },
    )


def _apply_min_readers(host, df, min_readers, *, key):
    """Drop under-supported word rows and caption the count (AN-26)."""
    if df is None or df.empty or "enough" not in df.columns or min_readers <= 1:
        return df
    dropped = int((~df["enough"]).sum())
    out = df[df["enough"]]
    if dropped:
        host.caption(f"⚠️ {dropped} word(s) backed by < {min_readers} readers hidden.")
    return out


# --- Group definition (AN-14 … AN-22) ----------------------------------------
# Two modes (the user asked for both): *split a field* — pick one categorical
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


#: A group field that lives on the attached participant table rather than on the
#: word/fixation frames (DATA-20). The prefix keeps one flat picker while making
#: the two provenances impossible to confuse — both in the UI and in the code
#: that has to translate one of them.
_META_FIELD_PREFIX = "meta:"


def _meta_field_name(option: str) -> str | None:
    """The metadata field behind a picker option, or ``None`` for a real column."""
    if isinstance(option, str) and option.startswith(_META_FIELD_PREFIX):
        return option[len(_META_FIELD_PREFIX) :]
    return None


def _metadata_group_fields() -> list[str]:
    """Prefixed picker options for the attached table's groupable fields.

    Categorical fields, plus a numeric one with few enough distinct values to
    read as a category (a birth year, a session number). A wide-ranging numeric
    field is a *range* question and belongs in the trial filters, which already
    have the slider for it.
    """
    from scanpath_studio import metadata as md

    meta = md.active()
    if meta is None or meta.frame.empty:
        return []
    out = []
    for field in meta.fields:
        values = md.options_for(meta, field.name)
        if 2 <= len(values) <= 60:
            out.append(f"{_META_FIELD_PREFIX}{field.name}")
    return out


def _both_frame_values(words, fixations, col):
    """Distinct values of ``col`` — a frame column, or a metadata field."""
    name = _meta_field_name(col)
    if name is not None:
        from scanpath_studio import metadata as md

        return md.options_for(md.active(), name)
    frames = [f for f in (fixations, words) if col in getattr(f, "columns", [])]
    vals = set()
    for f in frames:
        vals |= set(f[col].astype(str).dropna().unique())
    return sorted(vals)


def _group_spec(col: str, values) -> dict:
    """One ``{column: values}`` group spec — the metadata translation lives here.

    DATA-20's rule is that a participant-grain constraint **is** a participant
    constraint: the table is never broadcast onto the word/fixation frames, so a
    group defined on "native language = Hebrew" resolves to the set of readers
    whose row says Hebrew, and the spec `aggregation.group_mask` sees is an
    ordinary ``participant_id`` one. Nothing downstream needs to know.

    An empty selection is "no constraint" and returns ``{}``, matching the frame
    branch — but a selection that matches *nobody* must return an impossible
    spec rather than ``{}``, or a group that should be empty would silently
    select every row.
    """
    if not values:
        return {}
    name = _meta_field_name(col)
    if name is None:
        return {col: values}
    from scanpath_studio import metadata as md

    ids = md.participants_matching(md.active(), {name: list(values)})
    if ids is None:
        # No table (detached mid-run), so the field this group was defined on no
        # longer exists. Fail *closed*: silently widening a cohort to everyone is
        # the one outcome that produces a plausible, wrong comparison.
        return {"participant_id": [_NO_SUCH_PARTICIPANT]}
    return {"participant_id": sorted(ids) or [_NO_SUCH_PARTICIPANT]}


#: A reader id no dataset can hold, so `group_mask` selects nothing. Used when a
#: metadata group matches no loaded reader — see `_group_spec`.
_NO_SUCH_PARTICIPANT = "\x00__no_such_participant__"


def _group_split_columns(words, fixations):
    """Categorical fields with 2…60 values, from both frames or the metadata."""
    out = []
    text_col = _text_column(words) or _text_column(fixations)
    candidates = list(_GROUP_SPLIT_CANDIDATES) + ([text_col] if text_col else [])
    for col in dict.fromkeys(candidates):
        if col in words.columns and col in fixations.columns:
            n = words[col].astype(str).nunique()
            if 2 <= n <= 60:
                out.append(col)
    return out + _metadata_group_fields()


def _join_label(values):
    vals = [str(v) for v in (values or [])]
    if not vals:
        return ""
    return vals[0] if len(vals) == 1 else f"{vals[0]} +{len(vals) - 1}"


def _render_filter_set(words, fixations, *, key, default_label):
    """One independent group's filter-set picker → ``(spec, label)``."""
    spec = {}
    label = st.text_input("Label", value=default_label, key=f"{key}_label")
    text_col = _text_column(fixations) or _text_column(words)
    for col, pretty in (
        ("participant_id", "Participants"),
        (text_col, "Texts"),
        *[(c, _pretty_col(c)) for c in _FILTER_SET_FIELDS],
        # DATA-20: the attached participant table's fields are offered here too,
        # translated to reader ids by `_group_spec`.
        *[(c, _pretty_col(c)) for c in _metadata_group_fields()],
    ):
        if not col:
            continue
        opts = _both_frame_values(words, fixations, col)
        if len(opts) < 2 or len(opts) > 400:
            continue
        sel = st.multiselect(pretty, opts, key=f"{key}_{col}", placeholder="All")
        # Two metadata fields (or a metadata field and an explicit Participants
        # pick) both land on `participant_id`, so they have to intersect rather
        # than the later one overwriting the earlier. An empty intersection is
        # the impossible-id sentinel, never `[]` — `group_mask` reads an empty
        # value list as "no constraint" and would select every row.
        for column, values in _group_spec(col, sel).items():
            if column in spec:
                merged = sorted(
                    set(map(str, spec[column])) & set(map(str, values))
                ) or [_NO_SUCH_PARTICIPANT]
                spec[column] = merged
            else:
                spec[column] = values
    return spec, (label or default_label)


def _render_group_definition(words, fixations, *, key, two_groups, host=None):
    """Group-definition UI → one ``spec``/``(spec, label)`` or two ``(a, b, la, lb)``."""
    host = host or st
    mode = host.radio(
        "Define group(s) by",
        ["Split a field", "Independent filter sets"],
        key=f"{key}_mode",
        horizontal=True,
        help="Split one categorical column into groups, or build each group from "
        "its own participant/text/condition filter.",
    )
    if mode == "Split a field":
        cols = _group_split_columns(words, fixations)
        if not cols:
            host.info(
                "No categorical field with ≥2 values shared by both tables — use "
                "*Independent filter sets* instead."
            )
            return (None, None, "Group A", "Group B") if two_groups else (None, "Group")
        # Detaching the participant table removes its `meta:` options; without
        # this Streamlit falls back to the first option silently and the cohort
        # on screen changes with no notice (`controls._drop_stale`'s job).
        _drop_stale(f"{key}_field", cols)
        col = host.selectbox("Field", cols, key=f"{key}_field", format_func=_pretty_col)
        vals = _both_frame_values(words, fixations, col)
        if two_groups:
            c = host.columns(2)
            a = c[0].multiselect(
                f"Group A — {_pretty_col(col)}", vals, default=vals[:1], key=f"{key}_a"
            )
            rest = [v for v in vals if v not in a]
            b = c[1].multiselect(
                f"Group B — {_pretty_col(col)}", vals, default=rest[:1], key=f"{key}_b"
            )
            return (
                _group_spec(col, a),
                _group_spec(col, b),
                _join_label(a) or "Group A",
                _join_label(b) or "Group B",
            )
        sel = host.multiselect(
            f"{_pretty_col(col)} =", vals, default=vals[:1], key=f"{key}_g"
        )
        return _group_spec(col, sel), (_join_label(sel) or "All")
    # Independent filter sets.
    if two_groups:
        c = host.columns(2)
        with c[0]:
            st.markdown("**Group A**")
            sa, la = _render_filter_set(
                words, fixations, key=f"{key}_setA", default_label="Group A"
            )
        with c[1]:
            st.markdown("**Group B**")
            sb, lb = _render_filter_set(
                words, fixations, key=f"{key}_setB", default_label="Group B"
            )
        return sa, sb, la, lb
    spec, label = _render_filter_set(
        words, fixations, key=f"{key}_set0", default_label="Group"
    )
    return spec, label


def _warn_word_only_group_fields(host, fixations, *specs) -> None:
    """Warn when a group is defined on a field absent from the fixation table.

    ``group_mask`` filters per frame, so a word-only spec column leaves the
    fixation frame unfiltered — the *fixation-level* views (distributions for a
    per-fixation measure, paired bars, effect size) would then silently compare
    all-vs-all. Surfacing it beats a misleading comparison.
    """
    missing = sorted(
        {
            col
            for spec in specs
            for col, vals in (spec or {}).items()
            if vals and col not in getattr(fixations, "columns", [])
        }
    )
    if missing:
        host.warning(
            "Group field(s) "
            + ", ".join(_pretty_col(c) for c in missing)
            + " aren't in the fixation table, so the fixation-level views "
            "(distributions for a per-fixation measure, paired bars, effect "
            "size) can't split on them. Use a field present in both tables for "
            "those views."
        )


def _text_column(frame: pd.DataFrame) -> str | None:
    """Canonical text/passage id column, if any."""
    for col in ("unique_text_id", "text_id", "unique_paragraph_id", "paragraph_id"):
        if col in frame.columns:
            return col
    return None


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
) -> None:
    """Corpus Analysis tab — question-oriented analysis sections.

    Replaces the single *Aggregated Views* subtab with one subtab per question —
    **Per text** (one text, many readers), **Per reader** (one reader, many
    trials), and **Groups** (profile one cohort, or flip a toggle to compare two).
    Every section obeys the active trial filters and reads the shared measure
    picker / aggregation / spread / normalization controls. (**Generations** moved
    to the Scanpath view's **Comparisons** subtab — ENG-8.)
    """
    viz_settings = corpus_style_controls(
        fixations_filtered,
        base_font_size,
        words=words_filtered,
        host=st,
        # VIZ-31: this view renders true-to-scale stimulus figures from the
        # canvas / typography settings, so it hosts that panel too — the rail
        # (its other home) doesn't exist here.
        canvas_renderer=canvas_renderer,
    )
    common = dict(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
    )
    # Keyed → the `.st-key-…` selector the "Explore a corpus question" tutorial
    # spotlights when it names the subtab to open (UX-40). The tab bar carries no
    # widget key, so a tutorial can only *point* at it, never switch it.
    with st.container(key="tutorial_corpus_subtabs"):
        text_tab, sentence_tab, reader_tab, groups_tab = st.tabs(
            ["Per text", "Per sentence", "Per reader", "Groups"]
        )
    with text_tab:
        render_per_text_tab(
            words_filtered, fixations_filtered, viz_settings=viz_settings, **common
        )
    with reader_tab:
        render_per_reader_tab(
            words_filtered,
            fixations_filtered,
            viz_settings=viz_settings,
            **common,
        )
    with sentence_tab:
        from scanpath_studio.preprocessing import sentence_measures

        sentence_table = sentence_measures(
            compute_word_metrics(words_filtered, fixations_filtered),
            fixations_filtered,
        )
        st.caption(
            "Sentence is a first-class aggregation unit: combine one measure "
            "across readers for each text/sentence pair."
        )
        numeric = [
            column
            for column in sentence_table.select_dtypes(include="number").columns
            if column not in {"sentence_id"}
        ]
        if sentence_table.empty or not numeric:
            st.info("No sentence-level measures are available for this selection.")
        else:
            controls = st.columns(2)
            metric = controls[0].selectbox(
                "Sentence measure", numeric, key="sentence_measure"
            )
            aggregate = controls[1].selectbox(
                "Aggregate", ["Mean", "Median"], key="sentence_aggregate"
            )
            identity = [
                column
                for column in ("text_id", "sentence_id")
                if column in sentence_table
            ]
            reducer = "mean" if aggregate == "Mean" else "median"
            summary = (
                sentence_table.groupby(identity, dropna=False)[metric]
                .agg(reducer)
                .reset_index(name=f"{reducer}_{metric}")
            )
            st.dataframe(summary, hide_index=True, width="stretch")
    with groups_tab:
        render_groups_tab(
            words_filtered,
            fixations_filtered,
            viz_settings=viz_settings,
            **common,
        )


# -----------------------------------------------------------------------------
# Question-oriented analysis subtabs (AN-1 … AN-22)
# -----------------------------------------------------------------------------


def _chart(fig) -> None:
    """Render a non-spatial Plotly figure stretched to the column width."""
    st.plotly_chart(fig, width="stretch")


def _corpus_series_colors(viz_settings: dict) -> tuple[str, str]:
    """Palette-derived primary/secondary colours shared by corpus builders."""
    return (
        viz_settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
        viz_settings.get("saccade_color", SACCADE_COLOR),
    )


def _text_picker(words: pd.DataFrame, *, key: str, host=None, label: str = "Text"):
    """Pick one text/passage; returns ``(text_col, text_id)`` (``None`` if none)."""
    host = host or st
    text_col = _text_column(words)
    if text_col is None or "word_id" not in words.columns:
        return None, None
    counts = text_read_counts(words, text_col)
    if not counts.empty:
        labels = {
            f"{row.text}  ({row.n_participants} readers)": row.text
            for row in counts.itertuples()
        }
        chosen = host.selectbox(label, list(labels), key=key)
        return text_col, labels[chosen]
    vals = sorted(words[text_col].astype(str).unique())
    if not vals:
        return text_col, None
    return text_col, host.selectbox(label, vals, key=key)


def _screen_picker(words, text_col, text_id, *, key: str, host=None):
    """Pick which screen of a multipart text the per-text views describe (BUG-26).

    Returns the chosen ``screen_id``, or ``None`` when the text is a single
    screen — which is every dataset without DATA-21 screen identity, where no
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


def _participant_picker(words, fixations, *, key, host=None, label="Reader"):
    host = host or st
    for frame in (fixations, words):
        if frame is not None and not frame.empty and "participant_id" in frame.columns:
            opts = sorted(frame["participant_id"].astype(str).unique())
            if opts:
                return host.selectbox(label, opts, key=key)
    return None


def _percentile(series: pd.Series, value) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty or value is None or pd.isna(value):
        return None
    return float((s < value).mean() * 100.0)


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
    """*What does this text look like?* — one text, many readers (AN-1…6)."""
    st.caption(
        "One **text**, all its readers. Pick a text, a measure, then a view: "
        "per-reader word profiles, a word × reader heatmap, the cohort profile, "
        "word difficulty on the stimulus, a linguistic-feature scatter, or skip / "
        "regression rates. Obeys the active trial filters."
    )
    if words_filtered.empty or "word_id" not in words_filtered.columns:
        st.info("Per-text views need a word-level table (word ids + reading measures).")
        return
    fkey = frame_fingerprint(words_filtered)
    # BUG-26: a multipart corpus needs a third control — word ids restart on each
    # screen. The *frame* decides the layout (known before any picker runs); the
    # picker itself only renders once the chosen text turns out to span more than
    # one screen.
    multipart = has_screen_identity(words_filtered)
    top = st.columns([3, 2, 2] if multipart else [3, 2])
    text_col, text_id = _text_picker(words_filtered, key="ptext_text", host=top[0])
    if text_col is None or text_id is None:
        st.info("No text/passage column found.")
        return
    screen_id = (
        _screen_picker(
            words_filtered, text_col, text_id, key="ptext_screen", host=top[2]
        )
        if multipart
        else None
    )
    view = top[1].selectbox(
        "View",
        [
            "Per-reader profiles",
            "Word × reader heatmap",
            "Cohort profile",
            "Word difficulty on stimulus",
            "Measure vs feature",
            "Skip / regression rate",
        ],
        key="ptext_view",
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Skip / regression rate":  # AN-6 — no measure picker
        min_readers = _min_readers_input(st, key="ptext6_min")
        rate = _c_word_rate(
            words_filtered, text_col, text_id, min_readers, fkey, screen_id
        )
        rate = _apply_min_readers(st, rate, min_readers, key="ptext6_min_note")
        _chart(make_word_rate_figure(rate, **fw))
        _download_tidy(st, rate, name=f"word_rates_{text_id}.csv", key="dl_ptext6")
        return

    c = st.columns([3, 1, 1, 1])
    measure = _measure_picker(
        words_filtered,
        fixations_filtered,
        key="ptext_measure",
        host=c[0],
        per_word_only=True,
    )
    if measure is None:
        return
    agg = c[1].selectbox(
        "Aggregate",
        _AGG_OPTIONS,
        key="ptext_agg",
        help="How each word's value is combined across readers (e.g. the mean per word).",
    )
    # Normalization is per-reader; it doesn't apply to the single aggregate tint
    # of the stimulus view (AN-4), so disable the toggle there rather than show an
    # inert control.
    normalize = _normalize_toggle(
        c[3],
        key="ptext_norm",
        disabled=measure.is_rate or view == "Word difficulty on stimulus",
    )

    if view == "Per-reader profiles":  # AN-1
        overlay = c[2].checkbox("Cohort mean", value=True, key="ptext1_overlay")
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
                per, measure_label=measure.axis_label, cohort=cohort, **fw
            )
        )
        _download_tidy(
            st, per, name=f"per_reader_{measure.key}_{text_id}.csv", key="dl_ptext1"
        )
    elif view == "Word × reader heatmap":  # AN-2
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
                measure_label=measure.axis_label,
                colorscale=viz_settings.get(
                    "heatmap_colorscale", DEFAULT_HEATMAP_COLORSCALE
                ),
                **fw,
            )
        )
        _download_tidy(
            st, per, name=f"word_reader_{measure.key}_{text_id}.csv", key="dl_ptext2"
        )
    elif view == "Cohort profile":  # AN-3
        spread = c[2].selectbox(
            "Spread",
            _SPREAD_OPTIONS,
            key="ptext3_spread",
            help="Band around each word's mean across readers — SD, SEM, IQR, "
            "or a 95% bootstrap confidence interval.",
        )
        min_readers = _min_readers_input(st, key="ptext3_min")
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
        prof = _apply_min_readers(st, prof, min_readers, key="ptext3_min_note")
        _chart(
            make_word_profile_figure(
                {f"Cohort ({measure.label})": prof},
                measure_label=measure.axis_label,
                spread_label=spread,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
        _download_tidy(
            st,
            prof,
            name=f"cohort_profile_{measure.key}_{text_id}.csv",
            key="dl_ptext3",
        )
    elif view == "Word difficulty on stimulus":  # AN-4 (+ AN-28: reads viz_settings)
        agg_words = _c_word_box_aggregate(
            words_filtered, text_col, text_id, measure.key, agg, fkey, screen_id
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
            order_font_size=viz_settings.get("order_font_size", 10),
            order_font_color=viz_settings.get("order_font_color", "#111111"),
            show_colorbars=viz_settings.get("show_colorbars", True),
            fixation_color_range=None,
            heatmap_range=None,
            heatmap_colorscale=viz_settings.get(
                "heatmap_colorscale", DEFAULT_HEATMAP_COLORSCALE
            ),
            text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
            background_color=viz_settings.get("background_color"),
            colorbar_orientation=viz_settings.get("colorbar_orientation", "Vertical"),
            colorbar_tickangle=viz_settings.get("colorbar_tickangle", 0),
            colorbar_tickfont_size=viz_settings.get("colorbar_tickfont_size", 12),
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
            fit_to_monitor=viz_settings.get("fit_to_monitor", True),
            word_heatmap_col="value",
            word_heatmap_title=measure.axis_label,
        )
        _render_true_scale_chart(fig, key="ptext_stimulus")
        _download_tidy(
            st,
            agg_words[["word_id", "value"]],
            name=f"stimulus_{measure.key}_{text_id}.csv",
            key="dl_ptext4",
        )
    elif view == "Measure vs feature":  # AN-5
        feats = available_features(words_filtered)
        if not feats:
            st.info(
                "No bundled linguistic features (surprisal / frequency / length / "
                "POS) in this dataset."
            )
            return
        feat_label = c[2].selectbox("Feature", list(feats), key="ptext5_feat")
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
                measure_label=measure.axis_label,
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
    """*What does this reader look like?* — one reader, many trials (AN-7…13)."""
    st.caption(
        "One **reader**, all their trials, against the cohort behind. Distributions, "
        "a reading-speed summary, within-trial dynamics, the oculomotor scatter, "
        "progressive/regressive saccades, the landing-position curve, and this "
        "reader's per-trial trend."
    )
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    # Keyed → the tutorial's "pick the reader, then the view" step (UX-40).
    top = st.container(key="tutorial_per_reader_view").columns([2, 3])
    pid = _participant_picker(
        words_filtered, fixations_filtered, key="prdr_pid", host=top[0]
    )
    if pid is None:
        st.info("No participant column found.")
        return
    fix_e = _c_enrich_fix(
        fixations_filtered,
        words_filtered,
        frame_fingerprint(fixations_filtered),
        frame_fingerprint(words_filtered),
    )
    view = top[1].selectbox(
        "View",
        [
            "Distribution vs cohort",
            "Reading summary",
            "Fixation duration over time",
            "Saccade vs fixation duration",
            "Progressive vs regressive",
            "Landing-position curve",
            "Per-trial trend",
        ],
        key="prdr_view",
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Distribution vs cohort":  # AN-7
        c = st.columns([3, 1, 1])
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="prdr_measure", host=c[0]
        )
        if measure is None:
            return
        kind = c[1].selectbox("Plot", ["violin", "box"], key="prdr7_kind")
        normalize = _normalize_toggle(c[2], key="prdr7_norm", disabled=measure.is_rate)
        frame = fix_e if measure.frame == "fixations" else words_filtered
        groups = reader_vs_cohort_values(frame, pid, measure, normalize=normalize)
        _chart(
            make_distribution_figure(
                groups,
                metric_label=measure.axis_label,
                kind=kind,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
    elif view == "Reading summary":  # AN-8
        summary = reader_summary(words_filtered, fix_e, pid)
        cohort = _c_cohort_summary(
            words_filtered,
            fix_e,
            frame_fingerprint(words_filtered),
            frame_fingerprint(fix_e),
        )
        # ENG-36: `st.metric(icon=…)` (1.61). Six numbers in one row read as an
        # undifferentiated wall; the glyph is what lets you find "the speed one"
        # without reading every label. Chosen to say what the number *is*, not to
        # decorate — speed, duration, count, direction of travel.
        specs = [
            ("wpm", "Reading speed", "{:.0f} wpm", ":material/speed:"),
            ("mean_fixation_ms", "Mean fixation", "{:.0f} ms", ":material/timer:"),
            ("n_fixations", "Fixations", "{:.0f}", ":material/blur_on:"),
            (
                "regression_rate",
                "Regression rate",
                "{:.0%}",
                ":material/keyboard_backspace:",
            ),
            ("skip_rate", "Skip rate", "{:.0%}", ":material/fast_forward:"),
            ("mean_saccade_px", "Mean saccade", "{:.1f} px", ":material/arrow_range:"),
        ]
        present = [s for s in specs if s[0] in summary]
        cols = st.columns(len(present)) if present else []
        for col, (skey, label, fmt, icon) in zip(cols, present):
            value = summary.get(skey)
            pct = (
                _percentile(cohort[skey], value)
                if skey in getattr(cohort, "columns", [])
                else None
            )
            col.metric(
                label,
                fmt.format(value) if value is not None else "—",
                delta=(f"{pct:.0f}th pct" if pct is not None else None),
                delta_color="off",
                icon=icon,
            )
        st.caption(
            f"Reader **{pid}** vs the {max(len(cohort) - 1, 0)} other readers "
            "in scope (percentiles)."
        )
        trials = _c_trial_summary(
            words_filtered,
            fix_e,
            frame_fingerprint(words_filtered),
            frame_fingerprint(fix_e),
        )
        trials = trials[trials["participant_id"].astype(str) == str(pid)]
        with st.expander("Summary tables", expanded=False):
            reader_table, trial_table = st.tabs(["Reader", "Trials"])
            with reader_table:
                selected_reader = cohort[
                    cohort["participant_id"].astype(str) == str(pid)
                ]
                st.dataframe(selected_reader, width="stretch", hide_index=True)
                _download_tidy(
                    st,
                    selected_reader,
                    name=f"reader_summary_{pid}.csv",
                    key="dl_prdr8_reader",
                )
            with trial_table:
                _render_trials_with_open_button(trials, pid, key="prdr8")
                _download_tidy(
                    st,
                    trials,
                    name=f"trial_summaries_{pid}.csv",
                    key="dl_prdr8_trials",
                )
    elif view == "Fixation duration over time":  # AN-9
        c = st.columns([3, 2])
        measure = _measure_picker(words_filtered, fix_e, key="prdr_measure", host=c[0])
        if measure is None or measure.frame != "fixations":
            c[0].info("Pick a per-fixation measure (duration / saccade amplitude).")
            return
        by = c[1].selectbox(
            "X axis",
            ["order_in_trial", "timestamp_ms"],
            key="prdr9_x",
            format_func=lambda s: s.replace("_", " "),
        )
        df = metric_over_time(fix_e, measure, participant_id=pid, by=by)
        _chart(
            make_trend_figure(
                df,
                x_col="x",
                y_label=measure.axis_label,
                title=f"{measure.label} over {by.replace('_', ' ')} — {pid}",
                **fw,
            )
        )
        _download_tidy(
            st, df, name=f"over_time_{measure.key}_{pid}.csv", key="dl_prdr9"
        )
    elif view == "Saccade vs fixation duration":  # AN-10
        df = saccade_vs_duration(fix_e, participant_id=pid)
        _chart(
            make_density_scatter_figure(
                df,
                x_col="duration_ms",
                y_col="saccade_amplitude",
                x_label="Fixation duration (ms)",
                y_label="Saccade amplitude (px)",
                **fw,
            )
        )
    elif view == "Progressive vs regressive":  # AN-11
        df = progressive_regressive_counts(fix_e, participant_id=pid)
        if df.empty:
            st.info("Needs fixation→word assignment to classify regressions.")
            return
        _chart(make_progression_figure(df, **fw))
        _download_tidy(st, df, name=f"progression_{pid}.csv", key="dl_prdr11")
    elif view == "Landing-position curve":  # AN-12
        vals = landing_positions(words_filtered, fix_e, participant_id=pid)
        if vals.size == 0:
            st.info(
                "Needs first-fixation landing positions (first_fix_x or fixation "
                "x + word boxes)."
            )
            return
        _chart(make_landing_curve_figure(vals, **fw))
    elif view == "Per-trial trend":  # AN-13
        c = st.columns([3, 1])
        measure = _measure_picker(words_filtered, fix_e, key="prdr_measure", host=c[0])
        if measure is None:
            return
        agg = c[1].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="prdr13_agg",
            help="How the measure is combined within each trial (across its words / fixations).",
        )
        frame = fix_e if measure.frame == "fixations" else words_filtered
        sub = frame[frame["participant_id"].astype(str) == str(pid)].copy()
        if not has_explicit_trial_index(sub):
            st.caption("ℹ️ Trial order derived from fixation timestamps.")
        sub["trial_index"] = derive_trial_index(sub)
        df = metric_by_trial_index(sub, measure.column, agg=agg)
        _chart(
            make_trend_figure(
                df,
                x_col="trial_index",
                y_label=measure.axis_label,
                title=f"{measure.label} by trial index — {pid}",
                **fw,
            )
        )
        _download_tidy(st, df, name=f"trend_{measure.key}_{pid}.csv", key="dl_prdr13")


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
    """*Groups* — profile one cohort, or compare two.

    One group answers "what does this group look like?"; flip **Compare a second
    group** to define Group B and get the two-cohort comparison views. A single
    group is just the one-group case of a comparison, so both live in one tab.
    """
    common = dict(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
    )
    compare = st.toggle(
        "Compare a second group",
        value=False,
        key="groups_compare",
        help="Off: profile a single group. On: define a second group and compare "
        "A vs B — difference profile, paired bars, effect size, and more.",
    )
    if compare:
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
) -> None:
    """*What does this group look like?* — a cohort by the active filter.

    The one-group case of the Groups tab (wrapped by ``render_groups_tab``)."""
    st.caption(
        "Define a **group** (split a field or build a filter set), then pool its "
        "readers: distribution summaries, the cohort word profile, a per-reader "
        "summary table, and the group's trend."
    )
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    with st.expander("Group", expanded=True):
        spec, label = _render_group_definition(
            words_filtered, fixations_filtered, key="pgrp", two_groups=False
        )
    _warn_word_only_group_fields(st, fixations_filtered, spec)
    words_g = apply_group(words_filtered, spec or {})
    # One `apply_group` call, not two: it returns `frame[mask]`, a new full-size
    # copy, so calling it again just to compute the cache key built a second
    # corpus-sized frame that nothing else ever saw — and (since PERF-3) parked
    # it in the fingerprint memo for the rest of the run.
    fix_in = apply_group(fixations_filtered, spec or {})
    fix_g = _c_enrich_fix(
        fix_in,
        words_g,
        frame_fingerprint(fix_in),
        frame_fingerprint(words_g),
    )
    n_readers = (
        fix_g["participant_id"].nunique()
        if "participant_id" in getattr(fix_g, "columns", [])
        else 0
    )
    st.caption(f"**{label}** — {n_readers} reader(s), {len(fix_g)} fixations in scope.")
    if (words_g is None or words_g.empty) and (fix_g is None or fix_g.empty):
        st.info("This group is empty — widen the definition.")
        return
    view = st.selectbox(
        "View",
        ["Distributions", "Word profile", "Reader summary table", "Group trend"],
        key="pgrp_view",
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Distributions":  # AN-14
        c = st.columns([3, 1, 1])
        measure = _measure_picker(words_g, fix_g, key="pgrp_measure", host=c[0])
        if measure is None:
            return
        kind = c[1].selectbox("Plot", ["violin", "box"], key="pgrp14_kind")
        normalize = _normalize_toggle(c[2], key="pgrp14_norm", disabled=measure.is_rate)
        frame = fix_g if measure.frame == "fixations" else words_g
        vals = measure_values(frame, measure, normalize=normalize)
        _chart(
            make_distribution_figure(
                {label: vals},
                metric_label=measure.axis_label,
                kind=kind,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
    elif view == "Word profile":  # AN-15
        c = st.columns([3, 1, 1, 1])
        text_col, text_id = _text_picker(words_g, key="pgrp_text", host=c[0])
        if text_col is None or text_id is None:
            st.info("No word-level data for this group.")
            return
        measure = _measure_picker(
            words_g, fix_g, key="pgrp_measure", host=c[1], per_word_only=True
        )
        if measure is None:
            return
        agg = c[2].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="pgrp15_agg",
            help="How each word's value is combined across the group's readers.",
        )
        spread = c[3].selectbox("Spread", _SPREAD_OPTIONS, key="pgrp15_spread")
        min_readers = _min_readers_input(st, key="pgrp15_min")
        # BUG-26: same single-screen scoping as the Per text views. There is no
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
                "profile across them would not describe one word axis."
            )
        prof = _apply_min_readers(st, prof, min_readers, key="pgrp15_note")
        _chart(
            make_word_profile_figure(
                {label: prof},
                measure_label=measure.axis_label,
                spread_label=spread,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
        _download_tidy(
            st, prof, name=f"group_profile_{measure.key}_{text_id}.csv", key="dl_pgrp15"
        )
    elif view == "Reader summary table":  # AN-16
        table = _c_cohort_summary(
            words_g, fix_g, frame_fingerprint(words_g), frame_fingerprint(fix_g)
        )
        if table.empty:
            st.info("No per-reader summaries for this group.")
            return
        trials = _c_trial_summary(
            words_g, fix_g, frame_fingerprint(words_g), frame_fingerprint(fix_g)
        )
        reader_tab, trial_tab = st.tabs(["Readers", "Trials"])
        with reader_tab:
            st.dataframe(table, width="stretch", hide_index=True)
            _download_tidy(
                st, table, name="group_reader_summaries.csv", key="dl_pgrp16"
            )
        with trial_tab:
            st.dataframe(trials, width="stretch", hide_index=True)
            _download_tidy(
                st, trials, name="group_trial_summaries.csv", key="dl_pgrp16_trials"
            )
    elif view == "Group trend":  # AN-17
        c = st.columns([3, 1, 1])
        measure = _measure_picker(words_g, fix_g, key="pgrp_measure", host=c[0])
        if measure is None:
            return
        agg = c[1].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="pgrp17_agg",
            help="How the measure is combined within each trial (across its words / fixations).",
        )
        show_readers = c[2].checkbox(
            "Per-reader behind", value=False, key="pgrp17_readers"
        )
        frame = fix_g if measure.frame == "fixations" else words_g
        sub = frame.copy()
        sub["trial_index"] = derive_trial_index(sub)
        df = metric_by_trial_index(sub, measure.column, agg=agg)
        fig = make_trend_figure(
            df,
            x_col="trial_index",
            y_label=measure.axis_label,
            title=f"{measure.label} by trial index — {label}",
            **fw,
        )
        if show_readers:
            per = per_participant_trend(sub, measure.column, agg=agg)
            for rdr, grp in per.groupby("participant_id"):
                grp = grp.sort_values("trial_index")
                fig.add_scatter(
                    x=grp["trial_index"],
                    y=grp["value"],
                    mode="lines",
                    line=dict(color="rgba(150,150,150,0.35)", width=1),
                    name=str(rdr),
                    showlegend=False,
                    hoverinfo="skip",
                )
        _chart(fig)
        _download_tidy(st, df, name=f"group_trend_{measure.key}.csv", key="dl_pgrp17")


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
) -> None:
    """*How do two groups differ?* — two cohorts side by side (AN-18…22)."""
    st.caption(
        "Define **two groups** and compare them: overlaid distributions, the "
        "per-word difference profile, paired summary bars, an effect size + test, "
        "and a stacked two-group word heatmap. Exploratory — not pre-registered."
    )
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return
    with st.expander("Groups A & B", expanded=True):
        spec_a, spec_b, label_a, label_b = _render_group_definition(
            words_filtered, fixations_filtered, key="cmp", two_groups=True
        )
    spec_a = spec_a or {}
    spec_b = spec_b or {}
    _warn_word_only_group_fields(st, fixations_filtered, spec_a, spec_b)
    na = apply_group(fixations_filtered, spec_a)
    nb = apply_group(fixations_filtered, spec_b)
    st.caption(
        f"**{label_a}**: {na['participant_id'].nunique() if 'participant_id' in na else 0}"
        f" reader(s) · **{label_b}**: "
        f"{nb['participant_id'].nunique() if 'participant_id' in nb else 0} reader(s)."
    )
    view = st.selectbox(
        "View",
        [
            "Overlaid distributions",
            "Difference word profile",
            "Paired summary bars",
            "Effect size + test",
            "Two-group word heatmap",
        ],
        key="cmp_view",
    )
    fw = dict(
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )

    if view == "Overlaid distributions":  # AN-18
        c = st.columns([3, 1, 1])
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="cmp_measure", host=c[0]
        )
        if measure is None:
            return
        kind = c[1].selectbox("Plot", ["violin", "box"], key="cmp18_kind")
        normalize = _normalize_toggle(c[2], key="cmp18_norm", disabled=measure.is_rate)
        frame = fixations_filtered if measure.frame == "fixations" else words_filtered
        groups = two_group_values(
            frame,
            measure,
            spec_a,
            spec_b,
            label_a=label_a,
            label_b=label_b,
            normalize=normalize,
        )
        _chart(
            make_distribution_figure(
                groups,
                metric_label=measure.axis_label,
                kind=kind,
                colors=_corpus_series_colors(viz_settings),
                **fw,
            )
        )
    elif view == "Difference word profile":  # AN-19
        c = st.columns([3, 1, 1, 1])
        text_col, text_id = _text_picker(words_filtered, key="cmp_text", host=c[0])
        if text_col is None or text_id is None:
            st.info("No word-level data.")
            return
        measure = _measure_picker(
            words_filtered,
            fixations_filtered,
            key="cmp_measure",
            host=c[1],
            per_word_only=True,
        )
        if measure is None:
            return
        agg = c[2].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="cmp19_agg",
            help="How each word's value is combined across each group's readers, before A−B.",
        )
        min_readers = _min_readers_input(c[3], key="cmp19_min", label="Min/grp")
        diff = group_word_difference(
            words_filtered,
            text_col,
            text_id,
            measure,
            spec_a,
            spec_b,
            agg=agg,
            min_readers=min_readers,
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
            st, diff, name=f"difference_{measure.key}_{text_id}.csv", key="dl_cmp19"
        )
    elif view == "Paired summary bars":  # AN-20
        all_measures = available_measures(words_filtered, fixations_filtered)
        labels = {m.label: m.key for m in all_measures}
        default = [
            m.label for m in all_measures if m.key in ("fix_dur", "sacc_amp", "tfd")
        ]
        chosen = st.multiselect(
            "Measures",
            list(labels),
            default=default or list(labels)[:3],
            key="cmp20_measures",
        )
        c = st.columns(2)
        agg = c[0].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="cmp20_agg",
            help="How each measure is combined across each group's readers.",
        )
        spread = c[1].selectbox(
            "Error bars", _SPREAD_OPTIONS, index=1, key="cmp20_spread"
        )
        measures = [MEASURES[labels[m]] for m in chosen]
        if not measures:
            st.info("Pick at least one measure.")
            return
        df = paired_group_summary(
            fixations_filtered,
            measures,
            spec_a,
            spec_b,
            agg=agg,
            spread=spread,
            label_a=label_a,
            label_b=label_b,
            words=words_filtered,
            fixations=fixations_filtered,
        )
        _chart(make_paired_bars_figure(df, **fw))
        _download_tidy(st, df, name="paired_group_means.csv", key="dl_cmp20")
    elif view == "Effect size + test":  # AN-21
        c = st.columns([3, 2])
        measure = _measure_picker(
            words_filtered, fixations_filtered, key="cmp_measure", host=c[0]
        )
        if measure is None:
            return
        test = c[1].selectbox("Test", ["Mann–Whitney", "t-test"], key="cmp21_test")
        frame = fixations_filtered if measure.frame == "fixations" else words_filtered
        a = measure_values(apply_group(frame, spec_a), measure)
        b = measure_values(apply_group(frame, spec_b), measure)
        res = group_effect_size(a, b, test=test)
        cols = st.columns(4)
        cols[0].metric(
            f"{label_a} mean",
            f"{res['mean_a']:.2f}",
            delta=f"n={res['n_a']}",
            delta_color="off",
        )
        cols[1].metric(
            f"{label_b} mean",
            f"{res['mean_b']:.2f}",
            delta=f"n={res['n_b']}",
            delta_color="off",
        )
        cols[2].metric("Mean difference", f"{res['mean_diff']:.2f}")
        cols[3].metric("Cohen's d", f"{res['cohen_d']:.3f}")
        p = res.get("p_value")
        p_txt = (
            "—"
            if p is None or (isinstance(p, float) and np.isnan(p))
            else ("< 0.001" if p < 0.001 else f"{p:.3f}")
        )
        st.markdown(
            f"**{test}** — statistic = {res['statistic']:.3g}, p = {p_txt}. "
            f"_Exploratory, not pre-registered._"
        )
    elif view == "Two-group word heatmap":  # AN-22
        c = st.columns([3, 1, 1])
        text_col, text_id = _text_picker(words_filtered, key="cmp_text", host=c[0])
        if text_col is None or text_id is None:
            st.info("No word-level data.")
            return
        measure = _measure_picker(
            words_filtered,
            fixations_filtered,
            key="cmp_measure",
            host=c[1],
            per_word_only=True,
        )
        if measure is None:
            return
        agg = c[2].selectbox(
            "Aggregate",
            _AGG_OPTIONS,
            key="cmp22_agg",
            help="How each word's value is combined across each group's readers.",
        )
        long = two_group_word_profiles(
            words_filtered,
            text_col,
            text_id,
            measure,
            spec_a,
            spec_b,
            agg=agg,
            label_a=label_a,
            label_b=label_b,
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
            st, long, name=f"two_group_{measure.key}_{text_id}.csv", key="dl_cmp22"
        )


# -----------------------------------------------------------------------------
# Comparisons Tab  (Scanpath view subtab; formerly "Generations" / "Multiple Comparison")
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
    """PRE-3 · Side-by-side grid comparing the vertical drift-correction algorithms.

    One panel per algorithm (plus the uncorrected original), each snapping
    fixations to their assigned text line and colouring by line, so a researcher
    can see how the ten Carr et al. (2021) algorithms assign fixations for this
    trial. The in-place version (a single algorithm applied on the main plot)
    lives in the Fixations popover; this subtab is the all-at-once comparison.
    """
    from scanpath_studio.measures import assign_fixation_lines

    st.caption(
        "Each panel snaps fixations to the text line assigned by a vertical "
        "drift-correction algorithm "
        "([Carr et al., 2021](https://doi.org/10.3758/s13428-021-01554-0)) and "
        "colours them by line. Pick one to apply on the main plot via "
        "**Fixations ⚙️ → Drift correction**."
    )
    with st.expander("Algorithm citations", expanded=False):
        st.markdown(
            "Primary source: Carr et al. (2021), *Behavior Research Methods*, "
            "[doi:10.3758/s13428-021-01554-0](https://doi.org/10.3758/s13428-021-01554-0)."
        )
        for method in alignment.ALGORITHMS:
            st.markdown(f"- **{method}** — {alignment.METHOD_CITATIONS[method]}")

    if trial_fixations.empty or trial_words.empty:
        st.info("No fixations / word boxes for this trial to align.")
        return

    # Building the 11-panel grid (each a true-scale Plotly figure) is expensive,
    # and Streamlit renders every subtab on each rerun — so gate it behind a
    # toggle the user opts into. The toggle state persists, so it stays on while
    # browsing trials once enabled.
    if not panel_field(
        st,
        "toggle",
        "Show comparison grid",
        key="align_grid_show",
        help="Build a side-by-side grid comparing all ten algorithms for this "
        "trial. Off by default — building eleven figures is slow.",
    ):
        st.caption(
            "Turn on **Show comparison grid** to compare all ten algorithms side "
            "by side, or apply one directly via **Fixations ⚙️ → Drift "
            "correction** on the main plot."
        )
        return

    # The text lines we snap to (shared with the per-algorithm panels). Fewer than
    # two lines → nothing to correct, so just show the original.
    line_centers = alignment._line_centers(trial_words)
    single_line = len(line_centers) < 2
    if single_line:
        st.info(
            "This trial has only one text line — there is no vertical drift to "
            "correct. Showing the original scanpath."
        )

    # Two `label | field` rows rather than two side-by-side stacks (UX-69): the
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
        return make_scanpath_figure(
            trial_words,
            fix,
            canvas_width=int(canvas_width),
            canvas_height=int(canvas_height),
            base_font_size=int(base_font_size),
            font_family=font_family,
            x_field="x",
            y_field="y",
            **kwargs,
        )

    # Naive baseline (nearest-line) to count how many fixations each algorithm
    # moves relative to the current "color by line" behaviour.
    baseline = assign_fixation_lines(trial_fixations, trial_words)
    _, sensitivity_report = alignment.correction_sensitivity(
        trial_fixations, trial_words
    )
    st.dataframe(
        sensitivity_report,
        hide_index=True,
        width="stretch",
        column_config={
            "average_y_correction": st.column_config.NumberColumn(format="%.1f px"),
            "max_y_correction": st.column_config.NumberColumn(format="%.1f px"),
        },
    )
    st.caption(
        "Sensitivity QA: large mean corrections or disagreement between methods "
        "identify trials whose measures deserve manual review."
    )

    # Build the panel list: original first, then the 10 algorithms (skipped when
    # there is only a single line, where they would all be no-ops).
    panels = [("Original (uncorrected)", None)]
    if not single_line:
        panels += [(a.title(), a) for a in alignment.ALGORITHMS]

    # Estimate a uniform cell height so panels line up (mirrors the multiple-
    # comparison grid).
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
                    st.caption(f"**{label}** · {len(trial_fixations)} fix")
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
# The grid shows at most this many generation panels (readability). When more
# than this exist they're ranked by similarity to the selected scanpath and the
# *closest* ones are shown — never an arbitrary label-sorted subset.
_GEN_MAX_PANELS = 24
# PRE-21: with similarity gated off there is no ranking, so the 24 cap loses its
# reason to exist — it was there to keep a *ranked* grid readable, not to bound
# rendering cost. Raised, but still finite and still stated in the caption, so
# the grid never silently truncates.
_GEN_MAX_PANELS_UNRANKED = 60
# Score at most this many candidates (bounds the NLD cost for a high-cardinality
# column like participant_id on a big corpus). A safety budget above the grid cap
# so the "most similar" ranking still sees more candidates than it displays.
# Dead while similarity is gated off — nothing is scored — which is why
# `_collect_generations` only applies it when it is on.
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
    for c in fixations.columns:
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


def _collect_generations(
    fixations_pool: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    gen_col: str,
    selected_participant,
    selected_trial,
) -> tuple:
    """Trials matching the selected trial's ``gen_col`` value.

    The comparison column is a selector, not a grouping dimension: choosing
    ``participant_id`` shows that reader's other trials, while choosing
    ``text_id`` shows other readings of the same text. Each returned item is one
    trial and the selected trial itself is always excluded.
    """
    if (
        gen_col not in fixations_pool.columns
        or gen_col not in trial_fixations.columns
        or fixations_pool.empty
        or trial_fixations.empty
    ):
        return {}, 0
    pool = fixations_pool
    if SCREEN_ID in trial_fixations.columns and not trial_fixations.empty:
        if SCREEN_ID not in pool.columns:
            return {}, 0
        active_screen = str(trial_fixations[SCREEN_ID].iloc[0])
        pool = pool[pool[SCREEN_ID].astype(str) == active_screen]
    selected_values = trial_fixations[gen_col].dropna().unique()
    if len(selected_values) != 1:
        return {}, 0
    pool = pool[pool[gen_col] == selected_values[0]]
    if {"participant_id", "trial_id"} <= set(pool.columns):
        pool = pool[
            ~(
                (pool["participant_id"] == selected_participant)
                & (pool["trial_id"] == selected_trial)
            )
        ]
    candidates: dict = {}
    for (participant, trial), group in pool.groupby(
        ["participant_id", "trial_id"], dropna=False, sort=True
    ):
        if group.empty:
            continue
        label = f"{participant} · {trial}"
        candidates[label] = group
    n_total = len(candidates)
    # Cap the SCORING budget only (the grid/ranking cut to _GEN_MAX_PANELS by
    # similarity happens in the tab, after scoring). Sorted for determinism.
    # PRE-21: it is a *scoring* budget, so with similarity gated off it would
    # only drop panels for no reason — the grid's own cap is what applies then.
    budget = _GEN_MAX_SCORE if similarity_enabled() else _GEN_MAX_PANELS_UNRANKED
    ordered = dict(sorted(candidates.items())[:budget])
    return ordered, n_total


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
    return {
        **base_settings,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "color_by_line": False,
        "fixation_flags": None,
        "show_order": False,
    }


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
) -> None:
    """Render the **Comparisons** subtab.

    Shows other trials whose selected comparison-field value matches the main
    trial. The field decides the set: text id yields other readings of the text,
    participant id yields that reader's other texts, and so on.
    """
    if trial_words.empty or trial_fixations.empty:
        st.info("Choose a trial with words and fixations.")
        return

    gen_cols = _generation_column_options(fixations_filtered)
    if not gen_cols:
        st.info("No trial-level field is available for matching.")
        return

    intro_col, field_col, grid_col = st.columns(
        [4.6, 3.2, 2.2], gap="medium", vertical_alignment="center"
    )
    with intro_col:
        st.caption("Show trials matching the selected trial on one field.")
    with field_col:
        gen_col = labeled(
            st,
            "selectbox",
            "Match field",
            options=gen_cols,
            key="multi_gen_col",
            help="Show trials with the same value as the selected trial.",
        )
    with grid_col:
        n_cols = labeled(
            st,
            "slider",
            "Grid columns",
            min_value=1,
            max_value=4,
            value=3,
            key="multi_n_cols",
            help="Number of panels per row.",
        )

    candidates, n_total = _collect_generations(
        fixations_filtered,
        trial_fixations,
        gen_col,
        selected_participant,
        selected_trial,
    )
    if not candidates:
        st.info(f"No other filtered trial matches **{gen_col}**.")
        return
    # More scanpaths of this text exist than we score (very high-cardinality
    # column); the ones we do score are ranked by similarity below.
    scored_capped = n_total > len(candidates)

    if scored_capped:
        st.caption(f"Showing {len(candidates)} of {n_total} matches.")

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
        return make_scanpath_figure(
            words,
            fix,
            canvas_width=int(canvas_width),
            canvas_height=int(canvas_height),
            base_font_size=int(base_font_size),
            font_family=font_family,
            x_field="x",
            y_field="y",
            **settings,
        )

    # The full readings feed the spatial figures, the snapshot table, and the
    # convergence plots (ENG-8 removed the local fixation-index window).
    sliced_real = trial_fixations
    sliced_gens = candidates

    with st.container():
        # Score every collected generation against the selected scanpath. The
        # per-generation NLD annotates each grid panel and orders both the grid and
        # the table; the full table is shown beneath the grid.
        #
        # PRE-21: with similarity gated off nothing is scored, so the grid orders
        # alphabetically by the comparison-column value and shows more panels —
        # the 24 cap existed to keep the *ranked* grid readable, and there is no
        # ranking left to keep.
        text_col = next(
            (
                column
                for column in ("unique_text_id", "text_id", "paragraph_id")
                if column in trial_fixations.columns
            ),
            None,
        )
        selected_text_values = (
            trial_fixations[text_col].dropna().astype(str).unique()
            if text_col is not None
            else []
        )
        same_text = len(selected_text_values) == 1 and all(
            text_col in fix.columns
            and fix[text_col].dropna().astype(str).nunique() == 1
            and str(fix[text_col].dropna().astype(str).iloc[0])
            == str(selected_text_values[0])
            for fix in sliced_gens.values()
        )
        scoring = similarity_enabled() and same_text
        table = (
            compute_similarity_table(sliced_real, sliced_gens, trial_words)
            if scoring
            else pd.DataFrame()
        )
        nld_by_gen = (
            dict(zip(table["Model"], table["NLD"])) if "NLD" in table.columns else {}
        )

        # Rank by similarity (lowest NLD = most similar; unscored/NaN last) and show
        # the closest _GEN_MAX_PANELS in the grid — never an arbitrary label subset.
        if scoring:
            ranked = sorted(
                sliced_gens,
                key=lambda n: (
                    pd.isna(nld_by_gen.get(n)),
                    nld_by_gen.get(n) if pd.notna(nld_by_gen.get(n)) else 0.0,
                ),
            )
        else:
            ranked = sorted(sliced_gens)
        panel_cap = _GEN_MAX_PANELS if scoring else _GEN_MAX_PANELS_UNRANKED
        grid_names = ranked[:panel_cap]

        st.markdown("#### Matching trials")
        # Estimate a uniform cell height from the figure aspect + column count so
        # panels line up and don't leave a tall whitespace band below each.
        aspect = float(canvas_height) / float(canvas_width or 1)
        assumed_col_px = max(360, int(1200 / max(1, n_cols)))
        cell_h = max(280, int(assumed_col_px * aspect) + 24)

        names = grid_names
        for start in range(0, len(names), n_cols):
            row_names = names[start : start + n_cols]
            grid_cols = st.columns(n_cols)
            for offset, (cell, name) in enumerate(zip(grid_cols, row_names)):
                with cell:
                    fix = sliced_gens[name]
                    nld = nld_by_gen.get(name)
                    trial_label = str(fix["trial_id"].iloc[0])
                    if nld is not None and pd.notna(nld):
                        st.caption(f"**{trial_label}** · NLD {nld:.2f}")
                    else:
                        st.caption(f"**{trial_label}**")
                    words = _comparison_trial_words(words_filtered, fix)
                    # Key on the absolute panel index (dict order is stable), so two
                    # labels differing only by spaces can't collide on the iframe key.
                    _render_true_scale_chart(
                        _make_fig(words, fix, panel_settings),
                        key=f"multi_gen_{start + offset}",
                        max_height=cell_h,
                    )

        # PRE-21: the scoring half of this panel — the similarity table (where
        # three of the four metrics still read "Not yet computed", the clearest
        # instance of the not-fully-integrated smell driving the gate) and the
        # convergence plots. The comparison grid above stays; only the scoring
        # comes off it.
        if not scoring:
            return

        st.markdown("#### Similarity")
        st.dataframe(
            _style_similarity_table(table.rename(columns={"Model": "Trial"})),
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
        # Convergence covers the grid subset (the shown, most-similar trials),
        # so it matches the grid and stays bounded on a high-cardinality column.
        conv_gens = {name: candidates[name] for name in grid_names}
        conv_key = (
            str(selected_participant),
            str(selected_trial),
            str(gen_col),
            tuple(sorted(conv_gens.keys())),
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
        fix_curves = st.session_state["_multi_conv_fix"]
        time_curves = st.session_state["_multi_conv_time"]

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
            st.plotly_chart(fig_idx, width="stretch", config={"responsive": True})
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
            st.plotly_chart(fig_time, width="stretch", config={"responsive": True})


# -----------------------------------------------------------------------------
# Data Tables Tabs
# -----------------------------------------------------------------------------


def _render_raw_table(df: pd.DataFrame, caption: str | None = None) -> None:
    """Render one of the raw Data Inspection tables, whole.

    ``lazy=True`` (ENG-36 — Streamlit 1.61) replaced a hand-rolled pager: a
    **Page** number box, a `.iloc` slice and a "rows 1,001 – 2,000 of 4,300,000"
    caption. Streamlit now keeps the frame on the app server and streams only the
    rows in view, which is both less code and a better table — the user scrolls
    and sorts across the *whole* corpus instead of one thousand rows at a time,
    and a rerun no longer ships the visible page to the browser again. Passing it
    explicitly rather than leaving the default: the default only kicks in above
    150 000 rows, and these are exactly the frames worth streaming well below
    that.

    There is deliberately no download button here: these are the *raw* frames,
    which carry passthrough columns like ``image_path`` that hold an absolute
    local path. Bulk export is the supported way out, and it strips those at its
    single chokepoint (``export.strip_local_paths``).
    """
    st.dataframe(df, hide_index=True, width="stretch", lazy=True)
    if caption:
        st.caption(caption)


def render_metrics_tab(
    words_filtered: pd.DataFrame, fixations_filtered: pd.DataFrame
) -> None:
    """Render word-level metrics tab."""
    st.markdown("##### Word-level data")
    metrics = compute_word_metrics(words_filtered, fixations_filtered)
    _render_raw_table(metrics)


def render_fixations_tab(fixations_filtered: pd.DataFrame) -> None:
    """Render fixation-level data tab."""
    st.markdown("##### Fixation-level data")
    _render_raw_table(fixations_filtered)


def render_raw_gaze_tab(raw_gaze_filtered: pd.DataFrame) -> None:
    """Render raw gaze data tab."""
    st.markdown("##### Raw gaze data")
    if raw_gaze_filtered.empty:
        st.info("No raw gaze data available after filtering.")
        return
    # DATA-15: the bundled demo's raw gaze is synthesized from the fixation
    # report — a table that looks like recorded samples must say it isn't.
    if st.session_state.get("data_source_choice") == DEMO_CHOICE:
        st.caption(
            "⚠️ The demo's raw gaze is **synthesized** from its fixations for "
            "illustration — it is not recorded eye-tracker output."
        )
    _render_raw_table(raw_gaze_filtered)


@st.cache_data(show_spinner="Building stimuli list…")
def _build_stimuli_table_cached(_words: pd.DataFrame, cache_key) -> pd.DataFrame:
    """One row per Text ID, with the stimulus text reconstructed from its words.

    The word table carries one row per word per text (and, for per-participant
    tables, repeated once per reader). We collapse identical word rows across
    participants, then join each text's words in reading order (line, then word
    id) into a single passage string. Cached on a cheap content fingerprint of
    the words frame (the frame itself is passed un-hashed via the underscore
    arg) so a rerun that doesn't change the data reuses the result.
    """
    empty = pd.DataFrame(columns=["Text ID", "# Words", "Text"])
    if _words.empty or "text_id" not in _words.columns or "text" not in _words.columns:
        return empty

    cols = [
        c
        for c in ("text_id", "unique_text_id", "word_id", "line_idx", "text")
        if c in _words.columns
    ]
    sub = _words[cols].copy()
    sub = sub.dropna(subset=["text_id"])
    if sub.empty:
        return empty

    # Collapse identical word rows coming from multiple participants (stimulus
    # AoIs are shared by every reader; per-participant tables repeat them).
    if "word_id" in sub.columns:
        sub = sub.drop_duplicates(subset=["text_id", "word_id"])
    else:
        sub = sub.drop_duplicates()

    sort_cols = ["text_id"] + [c for c in ("line_idx", "word_id") if c in sub.columns]
    sub = sub.sort_values(sort_cols, kind="stable")

    # Only surface unique_text_id as its own column when it actually differs
    # from text_id (after the unique_paragraph_id fallback they're identical).
    has_unique = "unique_text_id" in sub.columns and not (
        sub["unique_text_id"].astype(str).eq(sub["text_id"].astype(str)).all()
    )

    rows = []
    for text_id, grp in sub.groupby("text_id", sort=False):
        words_list = [w for w in grp["text"].astype(str).tolist() if w and w != "nan"]
        row = {
            "Text ID": text_id,
            "# Words": len(words_list),
            "Text": " ".join(words_list),
        }
        if has_unique:
            uniques = grp["unique_text_id"].dropna().astype(str).unique().tolist()
            row["Unique Text ID"] = ", ".join(uniques)
        rows.append(row)

    result = pd.DataFrame(rows)
    ordered = ["Text ID"]
    if has_unique:
        ordered.append("Unique Text ID")
    ordered += ["# Words", "Text"]
    return result[[c for c in ordered if c in result.columns]]


def render_stimuli_tab(words_filtered: pd.DataFrame) -> None:
    """Render the stimuli subtab — one reconstructed passage per Text ID."""
    st.markdown("##### Stimuli")
    if words_filtered.empty:
        st.info("No word data available after filtering.")
        return
    stimuli = _build_stimuli_table_cached(
        words_filtered, cache_key=frame_fingerprint(words_filtered)
    )
    if stimuli.empty:
        st.info(
            "No stimulus text could be reconstructed — check the Word text and "
            "Text ID column mappings."
        )
        return
    _render_raw_table(stimuli)


def _render_data_provenance() -> None:
    """Show a 'source / cohort / date / file mtime' banner above the Raw Data
    sub-tabs so reviewers can verify which OneStop export they're looking at.

    Only renders when ONESTOP_DATA_DIR is set (i.e. OneStop server bundle is
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
    cols[3].metric("File mtime", _fmt_mtime(info.get("ia_shard_mtime")))

    with st.expander("Data provenance — full paths"):
        st.caption(f"`ONESTOP_DATA_DIR = {info.get('data_dir', '?')}`")
        st.caption(
            f"loaded from: **{info.get('loaded_from', '?')}**"
            + (f"  ·  participant `{pid}`" if pid else "")
        )
        if "ia_shard" in info:
            st.caption(
                f"IA file: `{info['ia_shard']}`  "
                f"·  mtime `{_fmt_mtime(info.get('ia_shard_mtime'))}`"
            )
        if "fix_shard" in info:
            st.caption(
                f"Fixations file: `{info['fix_shard']}`  "
                f"·  mtime `{_fmt_mtime(info.get('fix_shard_mtime'))}`"
            )


def render_raw_data_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    raw_gaze_filtered: pd.DataFrame,
) -> None:
    """Render the raw data tab with sub-tabs.

    UX-52 folds this whole block into a collapsed expander, so the provenance
    banner moved out to its caller (it owns an expander, which cannot nest) —
    see ``render_data_inspection_tab``.
    """
    labels = ["Stimuli", "Word-level", "Fixation-level", "Raw gaze"]
    # DATA-20: the participant table is a *source* table, so it is shown
    # losslessly beside the others — and only when one is attached, rather than
    # as a permanently empty tab.
    attached = active_participant_metadata()
    if attached is not None and not attached.frame.empty:
        labels.append("Participants")
    tabs = st.tabs(labels)
    with tabs[0]:
        render_stimuli_tab(words_filtered)
    with tabs[1]:
        render_metrics_tab(words_filtered, fixations_filtered)
    with tabs[2]:
        render_fixations_tab(fixations_filtered)
    with tabs[3]:
        render_raw_gaze_tab(raw_gaze_filtered)
    if len(tabs) > 4:
        with tabs[4]:
            st.markdown("##### Participant metadata")
            st.caption(
                f"From **{attached.source_name}**, joined on `participant_id`. "
                "Kept as its own table — it is not copied onto the word or "
                "fixation rows."
            )
            _render_raw_table(attached.frame)


# -----------------------------------------------------------------------------
# Statistics Tab
# -----------------------------------------------------------------------------


@st.cache_data(show_spinner="Computing dataset statistics…")
def _dataset_statistics(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    cache_key,
) -> dict:
    """Compute the Data Inspection tab's summary aggregates.

    Pure function of the (filtered) frames, cached on a cheap fingerprint so the
    full-corpus ``groupby``/``unique``/``mean`` scans don't re-run on every rerun
    (e.g. when the user merely selects a different trial)."""
    participant_ids = set(_words["participant_id"].unique()) | set(
        _fixations["participant_id"].unique()
    )
    trial_ids = set(_words["trial_id"].unique()) | set(_fixations["trial_id"].unique())
    if "participant_id" in _raw_gaze.columns:
        participant_ids |= set(_raw_gaze["participant_id"].unique())
        trial_ids |= set(_raw_gaze["trial_id"].unique())
    text_col = "unique_text_id" if "unique_text_id" in _words.columns else "text_id"
    text_ids = set(_words[text_col].unique()) if text_col in _words.columns else set()

    trial_source = _fixations if not _fixations.empty else _words
    trials_per_participant = (
        trial_source.groupby("participant_id")["trial_id"].nunique()
        if not trial_source.empty
        else pd.Series(dtype=float)
    )
    fixations_per_trial = (
        _fixations.groupby(["participant_id", "trial_id"]).size()
        if not _fixations.empty
        else pd.Series(dtype=float)
    )
    words_per_trial = (
        _words.groupby(["participant_id", "trial_id"]).size()
        if not _words.empty
        else pd.Series(dtype=float)
    )
    stats_df = pd.DataFrame(
        [
            {
                "Metric": "Trials per participant",
                **safe_summary(trials_per_participant),
            },
            {"Metric": "Fixations per trial", **safe_summary(fixations_per_trial)},
            {"Metric": "Words per trial", **safe_summary(words_per_trial)},
        ]
    ).rename(
        columns={
            "mean": "Mean",
            "std": "Std",
            "min": "Min",
            "median": "Median",
            "max": "Max",
        }
    )

    return {
        "n_participants": len(participant_ids),
        "n_texts": len(text_ids),
        "n_trials": len(trial_ids),
        "n_fixations": len(_fixations),
        "n_words": len(_words),
        "n_gaze": len(_raw_gaze),
        "stats_df": stats_df,
    }


# Friendly field labels for the column-mapping summary, per source table. Box
# fields are spelled out so the words table reads clearly (e.g. "Box left").
_WORD_MAPPING_LABELS = {
    "participant": "Participant ID",
    "trial": "Trial ID",
    "word_id": "Word/IA ID",
    "text": "Word text/label",
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
    "word_id": "Word/IA ID",
}
_RAW_GAZE_MAPPING_LABELS = {
    "participant": "Participant ID",
    "trial": "Trial ID",
    "x": "X coordinate",
    "y": "Y coordinate",
    "timestamp": "Timestamp (ms)",
    "text": "Word text/label",
}
_MAPPING_TABLES = [
    ("Words/IA", "words", _WORD_MAPPING_LABELS),
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
}
# (table_key, label, field_specs, canonical-map) for the editable remap form.
_REMAP_TABLES = [
    ("words", "Words/IA", WORD_FIELD_SPECS, _WORD_REMAP_CANON),
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


def _rename_active_dataset(old: str) -> None:
    """DATA-23: apply the rename (the ✅ Rename button's ``on_click`` callback).

    A callback, not an inline ``if button:`` handler, because the rename reassigns
    ``data_source_choice`` — a widget key — and that only lands reliably when it
    happens before the widgets instantiate (see ``wizard._enter_add_data_wizard``).
    """
    from scanpath_studio.wizard import rename_dataset

    requested = str(st.session_state.get(f"dataset_rename_{old}", "") or "").strip()
    if not requested:
        st.session_state["_dataset_rename_note"] = ("warning", "Enter a dataset name.")
        return
    renamed = rename_dataset(old, requested)
    if renamed is None:
        st.session_state["_dataset_rename_note"] = (
            "info",
            f"Already named “{old}”.",
        )
        return
    note = f"Renamed “{old}” to “{renamed}”."
    if renamed != requested:
        # _safe_dataset_name resolved a clash with a built-in source label or
        # another stored dataset — say so rather than let the picker show a name
        # the user did not type.
        note += f" “{requested}” was already taken."
    st.session_state["_dataset_rename_note"] = ("success", note)


# The file name the attached table came from, for the "from **X**" captions.
# Separate from the file *identity* (`md.FILE_SESSION_KEY`), which is now an
# opaque `file_id` rather than something readable.
_PM_NAME_KEY = "_participant_metadata_name"


def active_participant_metadata():
    """The attached participant table for this session, or ``None`` (DATA-20)."""
    from scanpath_studio import metadata as md

    return md.active()


def _clear_participant_metadata() -> None:
    from scanpath_studio import metadata as md

    for key in (md.SESSION_KEY, md.RAW_SESSION_KEY, md.FILE_SESSION_KEY, _PM_NAME_KEY):
        st.session_state.pop(key, None)
    # And the uploader's own key: without it the widget still holds the file on
    # the next run, the (now absent) signature check reads as "new file", and
    # the table re-attaches itself immediately. Safe in an `on_click` callback,
    # which runs before the widgets instantiate.
    st.session_state.pop("participant_metadata_upload", None)


def render_participant_metadata_section(participants, *, host=None) -> None:
    """DATA-20 §1 — attach a participant-level table and report the join.

    Two homes, one body. The **upload wizard**'s *About your readers* step is the
    main one (the user's call): a first-time uploader is answering exactly this
    question and would otherwise never meet the feature. The 🗂️ **Data page**
    section is the other, because "which readers are these" is a question about
    the demo and a public corpus too, and the wizard runs only for an upload.

    They never render together: while the wizard is active ``app.main`` returns
    before the page's slot is filled, and the collapsed *Data & mapping* review
    panel skips this step's body entirely — two live copies would be two widgets
    on one key.

    Nothing is guessed. The id column is offered pre-filled but overridable, and
    the join is reported in full before the fields go anywhere — unmatched on
    both sides, duplicated rows, and rows that disagree with themselves.
    """
    if host is not None:
        with host:
            _participant_metadata_body(participants)
        return
    _participant_metadata_body(participants)


def _participant_metadata_body(participants) -> None:
    from scanpath_studio import metadata as md
    from scanpath_studio.data import read_table

    # UX-53 r5: the paragraph that used to print here now rides the uploader's
    # own label as a tooltip — descriptive prose on this page is hover-only.
    upload = st.file_uploader(
        "Participant metadata table (optional)",
        type=["csv", "tsv", "txt", "parquet", "feather", "xlsx", "zip"],
        key="participant_metadata_upload",
        # No `persist_state` — `st.file_uploader` does not take it. It does not
        # need it either: the parsed frame is kept in session state under
        # `md.RAW_SESSION_KEY`, so the attached table survives even if the
        # uploader widget itself is ever reset.
        help="One row per reader, with a `participant_id` column. The columns "
        "then behave like fields in the data: filters, chips, trial sorting, "
        "inspection and export. CSV / TSV / Parquet / Excel.",
    )
    if upload is None:
        if active_participant_metadata() is None:
            return
    else:
        # `file_id`, not (name, size): re-uploading a corrected file of the
        # same name and byte length must be read again (VIZ-4 precedent in
        # `controls._uploaded_image_data_uri`).
        signature = getattr(upload, "file_id", None) or (
            upload.name,
            getattr(upload, "size", None),
        )
        if st.session_state.get(md.FILE_SESSION_KEY) != signature:
            try:
                st.session_state[md.RAW_SESSION_KEY] = read_table(upload)
                st.session_state[md.FILE_SESSION_KEY] = signature
                st.session_state[_PM_NAME_KEY] = upload.name
                st.session_state.pop("participant_metadata_id_column", None)
            except Exception as exc:  # unreadable file — say so, keep the page
                st.error(f"Could not read {upload.name}: {exc}")
                return

    raw = st.session_state.get(md.RAW_SESSION_KEY)
    if raw is None or raw.empty:
        return

    columns = [str(column) for column in raw.columns]
    inferred = md.infer_participant_id_column(raw)
    id_column = st.selectbox(
        "Participant ID column",
        columns,
        index=columns.index(inferred) if inferred in columns else 0,
        key="participant_metadata_id_column",
        persist_state="session",
        help="Which column holds the reader id that joins to your data.",
    )
    attached = md.build_participant_metadata(
        raw,
        id_column,
        source_name=str(st.session_state.get(_PM_NAME_KEY) or "participant table"),
        participants=participants,
    )
    st.session_state[md.SESSION_KEY] = attached

    report = attached.report
    if not attached.fields:
        st.warning(
            "That table has no columns besides the id, so there is nothing to add.",
            icon="⚠️",
        )
        return
    matched = len(report.matched)
    if report.is_clean:
        st.success(f"Joined to all {matched} readers.", icon="✅")
    else:
        st.info(f"Joined to {matched} readers.", icon="🔗")
    if report.conflicting:
        st.warning(
            f"**{len(report.conflicting)} reader(s) have rows that disagree** "
            f"({_id_list(report.conflicting)}). Their fields are left empty "
            "rather than resolved by taking the first row.",
            icon="⚠️",
        )
    if report.only_in_data:
        st.caption(
            f"No row for {len(report.only_in_data)} loaded reader(s): "
            f"{_id_list(report.only_in_data)}. Their fields read as missing."
        )
    if report.only_in_table:
        st.caption(
            f"{len(report.only_in_table)} row(s) describe readers that are not "
            f"loaded: {_id_list(report.only_in_table)}. Ignored."
        )

    with st.expander(f"👤 {len(attached.fields)} field(s) added", expanded=False):
        st.dataframe(
            [
                {
                    "Field": field.label,
                    "Column": field.name,
                    "Grain": field.grain,
                    "Type": field.dtype,
                    "Distinct": field.n_unique,
                    "Missing": field.n_missing,
                }
                for field in attached.fields
            ],
            hide_index=True,
            width="stretch",
        )
        st.dataframe(attached.frame, hide_index=True, width="stretch")
    st.button(
        "✕ Detach this table",
        key="participant_metadata_clear",
        on_click=_clear_participant_metadata,
        help="Remove the participant metadata from this session.",
    )


#: DATA-29 — the trial table's display name, like `_PM_NAME_KEY` for readers.
_TM_NAME_KEY = "_trial_metadata_name"


def _clear_trial_metadata() -> None:
    """Detach the trial table (the ✕ button's ``on_click``) — DATA-29."""
    from scanpath_studio import metadata as md

    for key in (
        md.TRIAL_SESSION_KEY,
        md.TRIAL_RAW_SESSION_KEY,
        md.TRIAL_FILE_SESSION_KEY,
        _TM_NAME_KEY,
    ):
        st.session_state.pop(key, None)


def render_trial_metadata_section(combos, *, host=None) -> None:
    """DATA-29 — attach a trial-level table and report the join.

    The sibling of :func:`render_participant_metadata_section`, and deliberately
    the same shape: nothing is guessed, the key columns are offered pre-filled
    but overridable, and the join is reported in full before the fields go
    anywhere.

    **The key is the user's call, not an inference.** A table keyed by trial id
    alone describes a *text*, and every reading of that text inherits its row; a
    table keyed by reader *and* trial describes one *reading*. Nothing in a file
    says which world a corpus is in, so the reader column is a picker with an
    explicit *(none)* — defaulting to unset, the trial-grain reading, rather
    than auto-filling from any plausible column, because guessing wrong here
    silently changes what every filter built on it means.
    """
    if host is not None:
        with host:
            _trial_metadata_body(combos)
        return
    _trial_metadata_body(combos)


_TRIAL_META_NONE = "(none — one row per trial)"


def _trial_metadata_body(combos) -> None:
    from scanpath_studio import metadata as md
    from scanpath_studio.data import read_table

    upload = st.file_uploader(
        "Trial metadata table (optional)",
        type=["csv", "tsv", "txt", "parquet", "feather", "xlsx", "zip"],
        key="trial_metadata_upload",
        help="One row per trial, with a trial-id column. The columns then "
        "behave like fields in the data: filters, chips, trial sorting, "
        "inspection and export. CSV / TSV / Parquet / Excel.",
    )
    if upload is None:
        if md.active_trials() is None:
            return
    else:
        signature = getattr(upload, "file_id", None) or (
            upload.name,
            getattr(upload, "size", None),
        )
        if st.session_state.get(md.TRIAL_FILE_SESSION_KEY) != signature:
            try:
                st.session_state[md.TRIAL_RAW_SESSION_KEY] = read_table(upload)
                st.session_state[md.TRIAL_FILE_SESSION_KEY] = signature
                st.session_state[_TM_NAME_KEY] = upload.name
                st.session_state.pop("trial_metadata_id_column", None)
                st.session_state.pop("trial_metadata_participant_column", None)
            except Exception as exc:  # unreadable file — say so, keep the page
                st.error(f"Could not read {upload.name}: {exc}")
                return

    raw = st.session_state.get(md.TRIAL_RAW_SESSION_KEY)
    if raw is None or raw.empty:
        return

    columns = [str(column) for column in raw.columns]
    inferred = md.infer_trial_id_column(raw)
    left, right = st.columns(2)
    trial_column = left.selectbox(
        "Trial ID column",
        columns,
        index=columns.index(inferred) if inferred in columns else 0,
        key="trial_metadata_id_column",
        persist_state="session",
        help="Which column holds the trial id that joins to your data. "
        "Required — it is what makes this a trial table.",
    )
    participant_choice = right.selectbox(
        "Reader ID column",
        [_TRIAL_META_NONE, *columns],
        key="trial_metadata_participant_column",
        persist_state="session",
        help="Optional. Leave unset when each row describes a **text** and "
        "every reading of it inherits the row. Set it when each row describes "
        "one **reading** by one reader.",
    )
    participant_column = (
        None if participant_choice == _TRIAL_META_NONE else participant_choice
    )
    attached = md.build_trial_metadata(
        raw,
        trial_column,
        participant_column,
        source_name=str(st.session_state.get(_TM_NAME_KEY) or "trial table"),
        keys=md.trial_keys(combos),
    )
    st.session_state[md.TRIAL_SESSION_KEY] = attached

    report = attached.report
    if not attached.fields:
        st.warning(
            "That table has no columns besides the key, so there is nothing to add.",
            icon="⚠️",
        )
        return
    grain = "reading" if attached.keyed_by_participant else "trial"
    matched = len(report.matched)
    if report.is_clean:
        st.success(f"Joined to all {matched} {grain}s.", icon="✅")
    else:
        st.info(f"Joined to {matched} {grain}s.", icon="🔗")
    if report.conflicting:
        st.warning(
            f"**{len(report.conflicting)} {grain}(s) have rows that disagree** "
            f"({_id_list(report.conflicting)}). Their fields are left empty "
            "rather than resolved by taking the first row.",
            icon="⚠️",
        )
    if report.only_in_data:
        st.caption(
            f"No row for {len(report.only_in_data)} loaded {grain}(s): "
            f"{_id_list(report.only_in_data)}. Their fields read as missing."
        )
    if report.only_in_table:
        st.caption(
            f"{len(report.only_in_table)} row(s) describe {grain}s that are not "
            f"loaded: {_id_list(report.only_in_table)}. Ignored."
        )

    with st.expander(f"🗂️ {len(attached.fields)} field(s) added", expanded=False):
        st.dataframe(
            [
                {
                    "Field": field.label,
                    "Column": field.name,
                    "Grain": field.grain,
                    "Type": field.dtype,
                    "Distinct": field.n_unique,
                    "Missing": field.n_missing,
                }
                for field in attached.fields
            ],
            hide_index=True,
            width="stretch",
        )
        st.dataframe(attached.frame, hide_index=True, width="stretch")
    st.button(
        "✕ Detach this table",
        key="trial_metadata_clear",
        on_click=_clear_trial_metadata,
        help="Remove the trial metadata from this session.",
    )


def _id_list(ids, limit: int = 6) -> str:
    """``p1, p2, p3 …`` — enough to act on without flooding the page."""
    shown = ", ".join(f"`{value}`" for value in list(ids)[:limit])
    extra = len(ids) - limit
    return f"{shown} +{extra} more" if extra > 0 else shown


def _render_dataset_rename() -> None:
    """DATA-23: rename the active dataset, for datasets the user added.

    Only a stored upload can be renamed — every other source's name is the app's
    (the demo, the synthetic trial) or the corpus' own (the public registry), and
    is what the load path dispatches on. Lives here because Data Inspection is the
    page about *this dataset*, and the wizard's naming step is a one-shot the user
    can't get back to without uploading again.
    """
    active = _active_stored_dataset()
    if active is None:
        return
    name, _ = active
    label, rename = st.columns([5, 1.4], vertical_alignment="bottom")
    label.markdown(f"**Dataset:** {name}")
    editor = rename.popover("✏️ Rename", width="stretch", help="Rename this dataset.")
    editor.text_input(
        "Dataset name",
        value=name,
        # Keyed by the dataset so switching sources reseeds the box rather than
        # carrying the previous dataset's half-typed name into it.
        key=f"dataset_rename_{name}",
        # DATA-26 put this on the 🗂️ Data page, so it renders only while that
        # view is active — and Streamlit drops the key of a widget that did not
        # render, which would silently reset a half-typed name to the current
        # one (`value=name`) on the way back. Same rule as ENG-36's rail widgets.
        persist_state="session",
        help="Shown in the Data source list.",
    )
    editor.button(
        "✅ Rename",
        key=f"dataset_rename_apply_{name}",
        on_click=_rename_active_dataset,
        args=(name,),
        width="stretch",
    )
    kind, message = st.session_state.pop("_dataset_rename_note", (None, ""))
    if kind is not None:
        getattr(st, kind)(message)


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
        elif key == "text_id":
            # text_id always exists post-normalization (falls back to trial_id);
            # always seed it so a remap preserves text grouping instead of
            # collapsing every reading of a text into its own trial_id.
            proposed[key] = canonical
        else:
            proposed[key] = canonical if schema.get(key) else None
    return proposed


def _apply_remap() -> None:
    """Re-derive the active stored dataset's frames under the edited mapping and
    overwrite the entry in place (the "Apply remapping" button's ``on_click``).

    Reads the per-table schemas captured during render in
    ``_remap_pending_schemas``; validates each present table; on success
    re-normalizes via ``data.remap_normalized_frame`` and recomputes the
    composite trial components. ``app.main``'s stored-dataset branch then
    re-publishes the new frames + mapping on the rerun this callback triggers."""
    active = _active_stored_dataset()
    if active is None:
        return
    name, stored = active
    pending = st.session_state.get("_remap_pending_schemas") or {}
    problems: dict = {}
    for table_key in ("words", "fixations", "raw_gaze"):
        frame = stored.get(table_key)
        if frame is None or frame.empty or table_key not in pending:
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
    for table_key in ("words", "fixations", "raw_gaze"):
        frame = stored.get(table_key)
        if frame is None or frame.empty or table_key not in pending:
            continue
        schema = pending[table_key]
        new_entry[table_key] = remap_normalized_frame(frame, schema, kind=table_key)
        new_schemas[table_key] = schema
    new_entry["schemas"] = new_schemas
    # Recompute the composite trial components from the new trial mapping so the
    # cascading trial picker stays in sync (mirrors the wizard finalize).
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
        from scanpath_studio.experimental_setup import SetupSnapshot

        new_entry["setup"] = dict(setup_payload)
        setup = SetupSnapshot.from_dict(setup_payload, fallback=SetupSnapshot())
        # Apply the saved dataset facts to the live figure immediately. These
        # are the same wire keys the add flow publishes on finalize.
        st.session_state.update(
            {
                "global_canvas_width": setup.canvas_width,
                "global_canvas_height": setup.canvas_height,
                "global_monitor_width_mm": setup.monitor_width_mm,
                "global_viewing_distance_mm": setup.viewing_distance_mm,
                "global_base_font_size": setup.base_font_size,
                "global_font_family": setup.font_family,
                "global_line_spacing": setup.line_spacing,
                "global_scale_text_to_boxes": setup.scale_text_to_boxes,
            }
        )
    st.session_state["_datasets"][name] = new_entry
    st.session_state["_remap_applied"] = name


#: UX-54 r2 — the editor's field groups, in the add-dataset screen's order and
#: shape: what a row *is*, then where the eyes landed, then what the AOI says.
#: ``("<table>", "<field>")`` pairs, one tuple per rendered line. Whatever a
#: table's specs carry beyond these lands on a trailing *More* line, so a field
#: can never be dropped by this list falling behind ``*_FIELD_SPECS``.
_EDIT_ROWS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Fixations",
        (
            ("fixations", "trial"),
            ("fixations", "participant"),
            ("fixations", "text_id"),
            ("fixations", "screen_id"),
            ("fixations", "screen_index"),
        ),
    ),
    (
        "AOI",
        (
            ("words", "trial"),
            ("words", "participant"),
            ("words", "text_id"),
            ("words", "screen_id"),
            ("words", "screen_index"),
        ),
    ),
    (
        "Fixations",
        (
            ("fixations", "x"),
            ("fixations", "y"),
            ("fixations", "timestamp"),
            ("fixations", "duration"),
        ),
    ),
    ("", (("fixations", "fixation_id"), ("fixations", "screen_fixation_id"))),
    (
        "AOI",
        (
            ("fixations", "word_id"),
            ("words", "word_id"),
            ("words", "text"),
            ("words", "line"),
        ),
    ),
    ("", (("words", "box"),)),
    (
        "Raw gaze",
        (
            ("raw_gaze", "trial"),
            ("raw_gaze", "participant"),
            ("raw_gaze", "x"),
            ("raw_gaze", "y"),
        ),
    ),
    ("", (("raw_gaze", "timestamp"), ("raw_gaze", "screen_id"), ("raw_gaze", "text"))),
)

#: The editor's row grid: a narrow name column, then five equal picker cells —
#: ``wizard._ID_ROW_W``, so the two screens' rows line up with one another.
_EDIT_ROW_W = (0.10, 0.18, 0.18, 0.18, 0.18, 0.18)


def _render_remap_fields(
    name: str, stored: dict, problems: dict, composite: list
) -> dict:
    """The stored dataset's mapping, laid out the way add-dataset lays it out.

    **UX-54 r2**: "duplicate the add-dataset page so it looks the same when
    someone wants to edit the dataset." The controls are already the same ones —
    ``controls.column_mapping_ui`` builds both screens — so only the shape
    differed, and this gives the editor the wizard's: rows named down a narrow
    left column (Fixations · AOI · Raw gaze), one field per cell, each title
    stacked over its select, in place of one stacked expander per table.

    The widget keys stay ``remap_<dataset>_<table>_*``. They are the editor's own
    namespace, and borrowing the wizard's ``col_map_*`` keys would make an open
    wizard and an open editor overwrite each other's answers.
    """
    frames, proposals, prefixes, specs_by_table = {}, {}, {}, {}
    for table_key, _label, specs, canon in _REMAP_TABLES:
        frame = stored.get(table_key)
        if frame is None or getattr(frame, "empty", True):
            continue
        frames[table_key] = frame
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

    def _cell(host, table_key: str, field: str) -> dict:
        return column_mapping_ui(
            frames[table_key],
            table_label="",
            state_key_prefix=prefixes[table_key],
            field_specs=specs_by_table[table_key],
            proposed=proposals[table_key],
            problems=problems.get(table_key),
            container=host,
            use_expander=False,
            only_keys=[field],
            header=False,
            columns_per_row=1,
            stack_labels=True,
            # Here `proposed` is the dataset's current saved mapping (the frame
            # is already normalized), not a fresh auto-detect — say so.
            detected_label="currently mapped",
        )

    pending: dict = {table: {} for table in frames}
    seen: set = set()
    for label, fields in _EDIT_ROWS:
        live = [
            (table, field)
            for table, field in fields
            if table in frames
            and any(spec["key"] == field for spec in specs_by_table[table])
        ]
        if not live:
            continue
        row = st.columns(
            _EDIT_ROW_W[: len(live) + 1], gap="small", vertical_alignment="bottom"
        )
        row[0].markdown(
            f'<div class="sps-id-row-name sps-geo-row-name">{label}</div>',
            unsafe_allow_html=True,
        )
        for cell, (table, field) in zip(row[1:], live):
            pending[table].update(_cell(cell, table, field))
            seen.add((table, field))

    # Anything the rows above do not name — a field added to the specs since, or
    # one this editor never grouped — still has to render, or applying the
    # mapping would silently drop it.
    for table in frames:
        rest = [
            spec["key"]
            for spec in specs_by_table[table]
            if (table, spec["key"]) not in seen
        ]
        if not rest:
            continue
        row = st.columns(_EDIT_ROW_W, gap="small", vertical_alignment="bottom")
        row[0].markdown(
            '<div class="sps-id-row-name sps-geo-row-name">More</div>',
            unsafe_allow_html=True,
        )
        for index, field in enumerate(rest):
            pending[table].update(_cell(row[1 + index % 5], table, field))
    return pending


def _render_remap_editor(name: str, stored: dict) -> None:
    """Editable column-mapping form for a stored dataset (the surviving columns).

    Renders one ``column_mapping_ui`` per present table seeded with the current
    mapping, a note listing columns dropped at import, and an Apply button. The
    widget keys are namespaced by dataset name so switching datasets never feeds
    a stale column to a selectbox (which would raise).

    DATA-26: the *Column mapping* heading is the page section's, rendered by
    ``app.main`` above whichever of the three modes applies — this one no longer
    titles itself."""
    # UX-54: the dataset table's ✏️ Edit both opened this dataset and sent the
    # user here, so say so — otherwise the page has silently changed under them
    # and the mapping form is several screens down.
    if st.session_state.pop(FOCUS_MAPPING_KEY, None) == name:
        st.info(f"Editing **{name}** — its mapping and saved tables are below.")
    st.caption(
        "Change how this dataset's columns map to the app's canonical fields. "
        "Only columns that survived the original import are available."
    )
    # UX-71: the same wide option lists the add-dataset screen gets — this is
    # the same mapping, in the same shape (UX-54 r2).
    st.markdown(mapping_menu_css(), unsafe_allow_html=True)
    if st.session_state.pop("_remap_applied", None) == name:
        st.success("Dataset updated — mapping and recording setup saved.")
    problems = st.session_state.get("_remap_problems") or {}
    composite = list(stored.get("composite_trial_columns") or [])
    pending: dict = _render_remap_fields(name, stored, problems, composite)
    st.session_state["_remap_pending_schemas"] = pending

    # The add and edit flows now share the same three-column Recording setup
    # renderer. Editing starts from the saved values and publishes only when
    # Save changes runs, so unfinished edits never leak into the plot.
    from scanpath_studio.experimental_setup import SetupSnapshot
    from scanpath_studio.wizard import _wizard_setup_step

    st.divider()
    st.markdown("##### Recording setup")
    st.caption("Screen, physical geometry and reading-text setup for this dataset.")
    initial_setup = SetupSnapshot.from_dict(
        stored.get("setup") or {}, fallback=SetupSnapshot()
    )
    word_frame = stored.get("words")
    fixation_frame = stored.get("fixations")
    has_boxes = bool(
        isinstance(word_frame, pd.DataFrame)
        and not word_frame.empty
        and {"x", "y", "width", "height"} <= set(word_frame.columns)
    )
    setup = _wizard_setup_step(
        st,
        word_frame if isinstance(word_frame, pd.DataFrame) else pd.DataFrame(),
        fixation_frame if isinstance(fixation_frame, pd.DataFrame) else pd.DataFrame(),
        has_boxes,
        key_prefix=f"edit_{name}",
        initial=initial_setup,
        publish=False,
    )
    st.session_state["_remap_pending_setup"] = setup.to_dict()

    dropped = stored.get("dropped_columns") or {}
    flat = sorted({c for cols in dropped.values() for c in (cols or [])})
    if flat:
        # A popover keeps the (often long) dropped-column list out of the way —
        # zero footprint until opened, then a height-capped, searchable table.
        with st.popover(f"⚠️ {len(flat)} columns dropped at import"):
            st.caption(
                "Dropped during the original import — re-upload the file to remap them."
            )
            st.dataframe(
                pd.DataFrame({"Dropped column": flat}),
                hide_index=True,
                width="stretch",
                height=320,
            )
    st.button(
        # UX-54 r2: the add-dataset screen's ✅ Add dataset, for the screen that
        # edits one — same shape, same place, same filled blue.
        "✅ Save changes",
        type="primary",
        key=f"remap_apply_{name}",
        on_click=_apply_remap,
        help="Save the mapping and recording setup, then re-derive the dataset.",
    )


def _request_full_identity_scan() -> None:
    """Ask for VAL-7's census instead of its sample, from the next run (PERF-6).

    A callback rather than an inline handler: ``app.main`` reads the flag near
    the top of the run, well before this section renders, so setting it inline
    would leave the sampled report on screen for one more rerun.
    """
    st.session_state[TRIAL_IDENTITY_FULL_KEY] = True


def render_trial_identity_section() -> None:
    """VAL-7: the evidence behind "this trial id may cover several readings".

    Reads the report ``app.main`` computed on the **unfiltered** frames, so the
    verdict describes the dataset's mapping rather than whatever the current
    filters left. Renders an all-clear as well as a warning — "we checked and
    it's fine" is the more common answer and is worth stating, or the section
    reads as an error box that only appears when something is wrong.

    UX-52 round 3 promoted this to a **section** of the Data page (``app.main``
    draws the heading into the slot below the column mapping), from an ``#####``
    item at the foot of "What's in this dataset". The verdict answers whether the
    Trial ID mapping is sufficient, and the fix it names is an edit to that
    mapping — a level below the counts was the wrong place for both.
    """
    report = st.session_state.get("_trial_identity_report") or {}
    total = int(report.get("trials") or 0)
    if not total:
        st.caption("No trials loaded, so there is nothing to check.")
        return
    # PERF-6: on a large corpus the check screens a deterministic sample, so
    # every figure below is "out of `total`" — say so, and offer the census.
    sampled_from = report.get("sampled_from")
    scope = f"{total} trials" if not sampled_from else f"{total} sampled trials"
    affected = int(report.get("affected_trials") or 0)
    if not affected:
        st.success(f"Each of the {scope} looks like a single reading.", icon="✅")
    else:
        st.warning(
            f"**{affected} of {scope} look like more than one reading.** "
            "A Trial ID that doesn't fully identify a reading concatenates "
            "several into one scanpath — which renders perfectly happily, as an "
            "ordinary scanpath with a lot of regressions. Add the column named "
            "below to the Trial ID mapping to separate them.",
            icon="⚠️",
        )
    if sampled_from:
        st.caption(
            f"Checked {total:,} of this dataset's {int(sampled_from):,} trials. A "
            "Trial ID that under-specifies does so in every reading it merges, "
            "so a sample of this size finds it — the full check is here for when "
            "you want the exact count."
        )
        st.button(
            "🔎 Check every trial",
            key="trial_identity_full_scan_btn",
            on_click=_request_full_identity_scan,
            help=f"Run the check across all {int(sampled_from):,} trials. Slower, "
            "and the result is kept for the rest of this session.",
        )
    rows = [
        {
            "Signal": "Duplicated word rows",
            "Count": int(report.get("duplicate_word_rows") or 0),
            "What it means": "A word box appears more than once in one trial. "
            "One row per word per reading is a property of the stimulus, so this "
            "is structural evidence rather than a heuristic.",
        },
        {
            "Signal": "Trials with a repeated fixation id",
            "Count": int(report.get("repeated_fixation_id_trials") or 0),
            "What it means": "Two fixations in one trial share an id — an "
            "independent cross-check that needs no word boxes.",
        },
        {
            "Signal": "Trials whose clock runs backwards",
            "Count": int(report.get("backwards_clock_trials") or 0),
            "What it means": "The timestamp jumps back mid-trial. That is a "
            "second recording starting, not a regression.",
        },
    ]
    # UX-52: the verdict above is the answer and stays open; the three signals
    # behind it are evidence, and open by default only when they are the
    # explanation for a warning the user is already reading.
    multi = report.get("multi_valued_columns") or {}
    with st.expander("What was checked", expanded=bool(affected)):
        st.dataframe(rows, hide_index=True, width="stretch")
        if multi:
            st.markdown(
                "**Columns that should be constant within a trial, but aren't** — "
                "each names a distinction the Trial ID is currently ignoring:"
            )
            st.dataframe(
                [
                    {"Column": col, "Trials with >1 value": count}
                    for col, count in multi.items()
                ],
                hide_index=True,
                width="stretch",
            )
        st.caption(
            "Checked on the whole dataset, before any filtering, using "
            "(participant, trial, screen) — a multipart trial restarts word ids "
            "per screen, so grouping by trial alone would report duplicates that "
            "are correct data."
        )


def _render_column_mapping_section(*, editor_rendered: bool = False) -> None:
    """The body of the Data page's **Column mapping** section (DATA-26).

    One section, three modes — a *presentation* merge, not a code merge. Two
    editors side by side on one page would read as a bug, but underneath they
    genuinely are two code paths: before normalization there are no canonical
    frames to remap, and after it there is no raw table to map from.

    * ``editor_rendered`` — mode **A**: the pre-normalization
      ``controls.column_mapping_ui`` panels were already drawn into this section
      by ``app.prepare_data`` (a raw source with ``allow_override``), so all
      that is left to add is the recording-setup note.
    * A stored uploaded dataset — mode **B**: the post-normalization
      ``_render_remap_editor``, offering only the columns that survived import.
    * Anything else — mode **C**: a read-only table built from the schemas the
      loaders stash under ``st.session_state['_active_column_mapping']``.

    The heading belongs to the page, not to any one mode — ``app.main`` renders
    it into a slot reserved above all three.
    """
    if editor_rendered:
        # The editable built-in mapping now uses the same compact field grid as
        # Add dataset; widen its option menus just as the wizard does.
        st.markdown(mapping_menu_css(), unsafe_allow_html=True)
        _render_setup_provenance_note()
        return
    active = _active_stored_dataset()
    if active is not None:
        _render_remap_editor(*active)
        return
    mapping = st.session_state.get("_active_column_mapping") or {}
    rows = _column_mapping_rows(mapping)
    if not rows:
        st.info("No column mapping available for the current data source.")
        return
    _render_readonly_mapping_grid(rows)
    st.caption("How each source column maps to the app's canonical fields.")
    _render_setup_provenance_note()


def _render_setup_provenance_note() -> None:
    """DATA-22 §7 surface 1: how this dataset's recording setup is known.

    Data Inspection is where someone checks what the app did with their data, so
    it is where an *assumed* monitor has to be visible rather than inferred from
    a plausible-looking number elsewhere in the UI.
    """
    from scanpath_studio.app import active_setup_snapshot
    from scanpath_studio.experimental_setup import (
        SETUP_GROUP_LABELS,
        SETUP_GROUPS,
        Provenance,
    )

    snapshot = active_setup_snapshot()
    if snapshot is None:
        return
    st.markdown("##### Recording setup")
    values = {
        "screen": f"{snapshot.canvas_width} × {snapshot.canvas_height} px",
        "geometry": (
            "—"
            if snapshot.geometry_provenance is Provenance.SKIPPED
            else f"{snapshot.monitor_width_mm:.0f} mm wide, "
            f"{snapshot.viewing_distance_mm:.0f} mm away"
        ),
        "text": (
            "scaled to word boxes"
            if snapshot.scale_text_to_boxes
            else f"{snapshot.base_font_size} px · {snapshot.font_family}"
        ),
    }
    labels = {"screen": "Screen", "geometry": "Physical size", "text": "Text size"}
    for cell, group in zip(st.columns(3, gap="medium"), SETUP_GROUPS):
        label = html.escape(labels.get(group, SETUP_GROUP_LABELS[group]))
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
    if snapshot.geometry_provenance is Provenance.SKIPPED:
        st.caption(
            "Visual-angle units are hidden for this dataset — the physical size "
            "was skipped, so there is nothing honest to derive them from."
        )
    elif snapshot.px_per_degree is not None:
        st.caption(f"≈ **{snapshot.px_per_degree:.1f} px** per degree of visual angle.")
    _render_arrived_provenance_note(snapshot)


def _render_arrived_provenance_note(snapshot) -> None:
    """What the *sender* of a deep link said about their own setup.

    The `setup_prov` badge exists because a link carries the setup's **values**
    already: without it a recipient cannot tell a monitor the sender measured
    from one the app assumed on their behalf. That only works if it is *shown* —
    the table above is derived from the recipient's own source, so on its own the
    arriving badge was parsed, parked, and never read by anything.

    Shown only where it disagrees with what this session resolved; when the two
    agree it is noise.
    """
    from scanpath_studio.experimental_setup import SETUP_GROUP_LABELS, SETUP_GROUPS

    arrived = st.session_state.get(SETUP_PROVENANCE_STATE_KEY)
    if not isinstance(arrived, dict) or not arrived:
        return
    differing = [
        f"{SETUP_GROUP_LABELS[group]}: **{arrived[group]}**"
        for group in SETUP_GROUPS
        if group in arrived and arrived[group] != str(snapshot.provenance[group])
    ]
    if not differing:
        return
    st.caption(
        "The link you opened was shared from a setup recorded differently — "
        + " · ".join(differing)
        + ". The table above describes *this* session's data source."
    )


@st.cache_data(show_spinner="Building the derived analysis tables…")
def _c_derived_tables(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    words_fingerprint,
    fixations_fingerprint,
    raw_gaze_fingerprint,
    pixels_per_degree_value: float | None,
) -> dict:
    """The six PRE-11/12/15/19 + AN-30 derived tables, built once per dataset.

    PERF-3: **Data Inspection is a subtab**, and Streamlit renders every subtab's
    body on every run — only the *display* is client-side. So this ran in full on
    every rerun of the Scanpath view, whether or not the user had ever opened the
    tab; a cosmetic colour change on the rail paid for the whole preprocessing
    suite. Nothing here depends on any viz setting, so it is keyed on the three
    frame fingerprints plus the one scalar that does matter (pixels-per-degree,
    from the experimental setup).
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
        "Sentences": sentence_measures(measured_words, _fixations),
        "Saccades": saccade_table(
            analysis_fixations,
            pixels_per_degree=pixels_per_degree_value,
            raw_gaze=_raw_gaze,
            words=_words,
        ),
        "Trials": trial_summary_table(measured_words, _fixations),
        "Readers": reader_summary_table(measured_words, _fixations),
        "Characters": character_grid(_words),
        "Cleaning QA": cleaning_report(_fixations),
    }


def render_data_inspection_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    raw_gaze_filtered: pd.DataFrame,
) -> None:
    """Render the *What's in this dataset* section of the 🗂️ Data page.

    Combines the former **Raw Data** and **Data Statistics** tabs: the dataset's
    name (renamable when the user added it — DATA-23), the headline dataset
    counts, every raw-data table, the per-metric summary statistics, and the
    trial-identity check — in that order.

    UX-52 gave it one level of hierarchy instead of five equally-weighted
    ``st.subheader`` + ``st.divider()`` pairs: **the answer stays open** (the
    dataset's name, the counts, the provenance banner, and the trial-identity
    verdict) and **the appendix folds away** (raw tables, derived tables,
    summary statistics, the identity evidence table). The tables were the bulk
    of the page's scroll and, per DATA-26, are "not checked that often".

    Every expander body still renders on every run — collapse is client-side, so
    no widget key is dropped. The one thing that could not simply be wrapped is
    ``_render_data_provenance``: it owns an expander of its own, and Streamlit
    nests neither expander-in-expander nor popover-in-popover. It is a
    whole-dataset fact rather than a raw-table one, so it moved *up* beside the
    counts instead of down inside the fold.
    """
    stats = _dataset_statistics(
        words_filtered,
        fixations_filtered,
        raw_gaze_filtered,
        cache_key=(
            frame_fingerprint(words_filtered),
            frame_fingerprint(fixations_filtered),
            frame_fingerprint(raw_gaze_filtered),
        ),
    )

    # 1. Headline dataset counts — under the dataset's own name, which DATA-23
    # makes editable here for a dataset the user added. No heading of its own
    # (UX-52): the counts *are* the opening answer of "what's in this dataset",
    # and a second same-weight subheader under the section's own only flattened
    # the hierarchy it was supposed to create.
    _render_dataset_rename()
    # ENG-36: icons (1.61) so the six counts are scannable rather than a row of
    # equally-weighted numbers — one glyph per *kind* of thing being counted.
    parts = part_catalog(words_filtered, fixations_filtered)
    top_cols = st.columns(7 if not parts.empty else 6)
    top_cols[0].metric(
        "Participants", f"{stats['n_participants']:,}", icon=":material/group:"
    )
    top_cols[1].metric("Texts", f"{stats['n_texts']:,}", icon=":material/article:")
    top_cols[2].metric("Trials", f"{stats['n_trials']:,}", icon=":material/list_alt:")
    top_cols[3].metric(
        "Fixations", f"{stats['n_fixations']:,}", icon=":material/blur_on:"
    )
    top_cols[4].metric("Words", f"{stats['n_words']:,}", icon=":material/abc:")
    top_cols[5].metric(
        "Gaze points",
        f"{stats['n_gaze']:,}" if stats["n_gaze"] else "0",
        help="Counts raw gaze samples if provided.",
        icon=":material/scatter_plot:",
    )
    if not parts.empty:
        top_cols[6].metric(
            "Screens", f"{len(parts):,}", icon=":material/view_carousel:"
        )
        with st.expander("Multipart trial screens", expanded=False):
            st.caption(
                "Recorded parent/child identity and per-screen geometry. Each row is "
                "one coordinate space; analysis and export retain this child key."
            )
            st.dataframe(parts, hide_index=True, width="stretch")

    # Provenance is a fact about the *dataset*, so it sits with the counts —
    # and it has to, because it owns an expander and cannot nest inside one.
    # Silent for every source but a OneStop server bundle.
    _render_data_provenance()

    # 2. Every raw-data table (Stimuli / Word-level / Fixation-level / Raw gaze).
    with st.expander("📋 Raw data — stimuli, words, fixations, gaze", expanded=False):
        render_raw_data_tab(words_filtered, fixations_filtered, raw_gaze_filtered)

    # PRE-11/12/15/19 + AN-30: first-class derived tables, all exportable.
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
    # PRE-22: *Cleaning QA* is the preprocessing pipeline's own provenance table
    # (PRE-15) — one row per trial saying what that stage excluded and why — so
    # it goes with the stage while the feature is held back from the release.
    # The other five are plain analysis tables that happen to live in
    # `preprocessing.py`; they are unaffected.
    if not preprocessing_enabled():
        derived = {k: v for k, v in derived.items() if k != "Cleaning QA"}
    with st.expander(
        "🧮 Derived analysis tables — " + " · ".join(derived), expanded=False
    ):
        for tab, (label, table) in zip(st.tabs(list(derived)), derived.items()):
            with tab:
                if table.empty:
                    st.caption(
                        f"No {label.lower()} table is available for this selection."
                    )
                else:
                    _render_raw_table(table)

    # 3. Per-metric summary statistics.
    with st.expander("📊 Summary statistics", expanded=False):
        st.dataframe(
            stats["stats_df"],
            hide_index=True,
            width="stretch",
            column_config={
                col: st.column_config.NumberColumn(format="%.2f")
                for col in ["Mean", "Std", "Min", "Median", "Max"]
            },
        )
        st.caption(
            "Statistics computed after filtering; missing values indicate empty "
            "source data."
        )

    # UX-52 round 3 — VAL-7's "does one trial_id cover several readings?" used to
    # close this panel. It is now its own Data-page section, rendered by
    # `app.main` beside the mapping whose Trial ID it judges.

    # DATA-26: the column mapping is no longer the last thing on this panel — it
    # is its own section *above* it on the Data page, next to the source and its
    # location, where the question is actually asked. `app.main` renders it.
