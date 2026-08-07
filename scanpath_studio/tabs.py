"""Tab rendering functions for the Scanpath Studio app."""

from __future__ import annotations

import html
import json
import os
from typing import Any, Callable, Optional, Tuple

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
from scanpath_studio.annotations import render_trial_annotations
from scanpath_studio.constants import (
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_COLORSCALE,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_COLORSCALE,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_PALETTE,
    DEFAULT_SACCADE_WIDTH,
    DEMO_CHOICE,
    HIGHLIGHTED_TEXT_COLOR,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    WORD_LABEL_COLOR,
    compare_palette_color,
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    SUMMARY_CHIP_FIELDS,
    WORD_FIELD_SPECS,
    _collect_compare_styles,
    _filter_fields_for,
    _numeric_slider,
    column_mapping_ui,
    corpus_style_controls,
    render_narrow_by,
    render_trial_chip_picker,
    render_trial_filters,
    sidebar_controls,
)
from scanpath_studio.data import (
    compute_word_metrics,
    derive_trial_index,
    frame_fingerprint,
    has_explicit_trial_index,
    remap_normalized_frame,
    trial_mapping_columns,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from scanpath_studio.export import (
    ExportProgress,
    annotate_figure,
    bulk_export,
    pattern_fields,
    render_export_options,
    render_pattern,
)
from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.illustration import illustration_reasons, resolve_label_reasons
from scanpath_studio.plots import (
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
from scanpath_studio.similarity import (
    METRICS,
    compute_similarity_table,
    nld_by_fixation_index,
    nld_by_time,
)
from scanpath_studio.utils import (
    SAME_TEXT_MARKER,
    build_comparison_options,
    compute_trial_stats,
    extract_trial,
    friendly_trial_label,
    safe_summary,
    select_trial,
)

# -----------------------------------------------------------------------------
# Single Trial Tab
# -----------------------------------------------------------------------------


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


def _embed_html_iframe(html: str, *, height: int) -> None:
    """Backward-compatible local alias for the shared iframe helper."""
    embed_html_iframe(html, height=height)


def _render_true_scale_chart(
    fig, *, key: str, max_height: Optional[int] = None
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
    horizontal scrolling. It is only scaled down to fit (capped at 1×), so on a
    wide monitor it sits at true size with margin rather than being stretched.

    ``max_height`` caps the rendered (scaled) height in px — used for the small
    multiples in the *Multiple Comparison* grid, where the figure should also
    shrink to fit a fixed cell height (whichever of width/height binds), and the
    iframe is sized to that cap so panels don't leave a tall band of whitespace.
    """
    width = int(fig.layout.width or 900)
    height = int(fig.layout.height or 600)
    # VIZ-10: an animation built with autoplay on carries its per-frame duration on
    # the figure; kick off `Plotly.animate` at that speed after mount (Plotly's own
    # `auto_play` would ignore the configured speed). `None` for static figures or
    # autoplay-off animations → the built-in `auto_play=False` keeps them paused.
    autoplay_ms = animation_autoplay_frame_duration(fig)
    autoplay_script = (
        animation_autoplay_post_script(autoplay_ms) if autoplay_ms is not None else None
    )
    plot_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"responsive": False, "displaylogo": False},
        div_id=f"truescale-{key}",
        # to_html defaults to auto_play=True, which auto-runs an animated figure on
        # load at Plotly's default frame duration (ignoring the configured playback
        # speed). Start paused so the animation only plays — at the right speed —
        # either via the autoplay kickoff below or when the user presses Play. No
        # effect on static (frame-less) figures.
        auto_play=False,
        post_script=autoplay_script,
    )
    # Scale factor: shrink to the available width, and (when capped) also to the
    # cell height, never upscaling past 1×.
    if max_height is not None:
        scale_js = f"Math.min(1, avail / W, {int(max_height)} / H)"
        iframe_height = int(max_height) + 12
    else:
        scale_js = "Math.min(1, avail / W)"
        iframe_height = height + 12
    # Wrap the fixed-size plot and scale it to the available (iframe) width.
    # transform-origin top-left keeps it flush-left; the outer box height tracks
    # the scaled height so there's no dead space below.
    html = f"""
    <div id="fit-{key}" style="width:100%;overflow:hidden;">
      <div id="box-{key}" style="width:{width}px;height:{height}px;
           transform-origin:top left;">{plot_html}</div>
    </div>
    <script>
    (function() {{
      var W = {width}, H = {height};
      var outer = document.getElementById("fit-{key}");
      var box = document.getElementById("box-{key}");
      function fit() {{
        var avail = outer.clientWidth || W;
        var s = {scale_js};
        box.style.transform = "scale(" + s + ")";
        outer.style.height = Math.round(H * s) + "px";
      }}
      fit();
      window.addEventListener("resize", fit);
      setTimeout(fit, 150);
    }})();
    </script>
    """
    # Iframe height = full true height (or the cap); the script trims the
    # visible block to the scaled height.
    _embed_html_iframe(html, height=iframe_height)


def _trial_text_id(trial_words: pd.DataFrame) -> Optional[str]:
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
    # Stacked (not columned) so the controls fit the narrow side-panel "Export"
    # toggle they now live in.
    fmt = st.radio(
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
    generate = st.button(
        f"Render {fmt}",
        key=f"{key_prefix}_save_generate",
        help="Renders the image (needs Chrome/Kaleido); the download button "
        "appears once it's ready.",
    )
    if not generate:
        return

    fig_width = int(fig.layout.width or canvas_width)
    fig_height = int(fig.layout.height or canvas_height)
    try:
        data = fig.to_image(
            format=fmt.lower(),
            width=fig_width,
            height=fig_height,
            # The on-screen figure is sized to fit the column; render raster
            # PNG at 3x so saved figures stay paper-quality (SVG/PDF are
            # vector and unaffected).
            scale=3 if fmt == "PNG" else 1,
        )
    except Exception as exc:
        hint = (
            CHROME_INSTALL_HINT
            if not chrome_available()
            else "On Streamlit Cloud Chrome is installed via `packages.txt`; if it "
            "still fails, choose the **HTML** format above — it needs no browser."
        )
        st.warning(f"Could not render {fmt}: {exc}\n\n{hint}")
        return
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
    fmt = st.radio(
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

    scale = st.select_slider(
        "Resolution",
        options=[0.5, 0.75, 1.0, 1.5, 2.0],
        value=1.0,
        format_func=lambda s: f"{s:g}×",
        key="anim_export_scale",
        help="Render scale: 1× matches the on-screen size. Lower is smaller/faster; "
        "higher is crisper/larger.",
    )

    max_frames = None
    if n_frames > _ANIM_FRAME_CAP:
        if st.checkbox(
            f"Limit to {_ANIM_FRAME_CAP} frames for a faster render",
            value=True,
            key="anim_export_limit",
            help="This reading has many fixations. Capping the rendered frames keeps "
            "the export quick; the clip's total duration is unchanged (each kept "
            "frame is held a little longer).",
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
    sig = (file_stem, fmt, float(scale), max_frames, hash(fig.to_json()))
    cache = st.session_state.get("_anim_export_cache")

    if st.button(
        f"Render {fmt}",
        key="anim_export_generate",
        help="Renders each frame via Kaleido (headless Chrome); the download "
        "appears once it's ready.",
    ):
        bar = st.progress(0.0, text=f"Rendering 0/{render_frames} frames…")

        def _on_progress(done: int, total: int) -> None:
            bar.progress(done / total, text=f"Rendering {done}/{total} frames…")

        try:
            data = export_animation(
                fig,
                fmt=fmt.lower(),
                frame_duration_ms=frame_ms,
                scale=float(scale),
                max_frames=max_frames,
                progress_callback=_on_progress,
            )
        except AnimationExportError as exc:
            bar.empty()
            st.warning(
                f"Could not render {fmt}: {exc}\n\n"
                "GIF/MP4 export rasterizes each frame with a Chrome/Chromium browser "
                "(Kaleido). On Streamlit Cloud this is installed via `packages.txt`; "
                "if it still fails, use the **HTML** format above — it needs no browser."
            )
            cache = None
        else:
            bar.empty()
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
    "This trial" export, which round-trips the on-screen figure), so the chips,
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
    fix: pd.DataFrame, words: pd.DataFrame, algorithm: Optional[str]
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


def _marked_text_column(viz_settings: dict) -> Optional[str]:
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
    _words: pd.DataFrame, _fixations: pd.DataFrame, _build_kwargs: dict, fig_key
):
    """Build + cache a static single-trial scanpath figure.

    Frames and kwargs are passed un-hashed; ``fig_key`` (from
    ``_figure_input_key``) is the cache key, so a rerun with the same trial and
    settings reuses the figure instead of rebuilding all its traces/shapes."""
    return make_scanpath_figure(_words, _fixations, **_build_kwargs)


# CMP-6: how many same-text candidates the "Most similar / different" orderings
# score at most (NLD is O(len_A·len_B) per candidate; the cap bounds a
# high-cardinality corpus). Unscored candidates keep their default order after
# the scored ones, and a caption says so.
_CMP_MAX_SCORE = 100
# The candidate orderings for the compare-trial (B) selector. "Same text first"
# is the historical default (📄 group, then 👤, then the rest, in data order).
_CMP_ORDER_OPTIONS = (
    "Same text first",
    "Most similar",
    "Most different",
    "Most fixations",
    "Longest reading",
)


@st.cache_data(show_spinner=False)
def _c_compare_trial_stats(_fixations: pd.DataFrame, fingerprint) -> dict:
    """Per-(participant, trial) fixation count + total reading time (ms).

    Backs the CMP-6 "Most fixations" / "Longest reading" candidate orderings.
    Keyed by ``fingerprint`` (the filtered fixations' frame fingerprint), so it
    recomputes only when the trial pool changes."""
    if _fixations.empty or not {
        "participant_id",
        "trial_id",
        "duration_ms",
    } <= set(_fixations.columns):
        return {}
    agg = _fixations.groupby(["participant_id", "trial_id"], sort=False)[
        "duration_ms"
    ].agg(["size", "sum"])
    return {
        (str(p), str(t)): (int(row["size"]), float(row["sum"]))
        for (p, t), row in agg.iterrows()
    }


@st.cache_data(show_spinner="Scoring candidate similarity…")
def _c_compare_nld(
    _fixations: pd.DataFrame,
    _trial_words: pd.DataFrame,
    fingerprint,
    words_fingerprint,
    participant: str,
    trial: str,
    candidates: tuple,
) -> dict:
    """NLD of each same-text candidate scanpath against the selected one (CMP-6).

    ``candidates`` is a tuple of ``(participant_id, trial_id)`` pairs, all
    reading the SAME text as the selected trial, so the selected trial's word
    boxes serve as the shared AOI frame — exactly how the Comparisons subtab
    scores its grid (``compute_similarity_table``). Returns
    ``{(pid, tid): nld}`` with NaN where a sequence is empty. Cache key: the
    pool + word-box fingerprints + the selection + the candidate set."""
    from .similarity import normalized_levenshtein, ordered_word_ids

    ref_fix = extract_trial(_fixations, participant, trial)
    ref_seq = [int(w) for w in ordered_word_ids(ref_fix, _trial_words) if pd.notna(w)]
    scores: dict = {}
    for pid, tid in candidates:
        cand_fix = extract_trial(_fixations, pid, tid)
        cand_seq = [
            int(w) for w in ordered_word_ids(cand_fix, _trial_words) if pd.notna(w)
        ]
        if not ref_seq and not cand_seq:
            scores[(pid, tid)] = float("nan")
        else:
            scores[(pid, tid)] = normalized_levenshtein(ref_seq, cand_seq)
    return scores


def _order_compare_options(
    options: list,
    order: str,
    fixations_filtered: pd.DataFrame,
    trial_words: pd.DataFrame,
    selected_participant: str,
    selected_trial: str,
) -> tuple[list, Optional[str]]:
    """Reorder the compare-B candidate list per the CMP-6 ordering choice.

    Returns ``(options, note)`` where ``note`` is an optional caption explaining
    what the ordering did (e.g. that only same-text candidates carry a
    similarity score, or that scoring was capped). "Same text first" (the
    default) returns the list untouched."""
    if order == "Same text first" or len(options) < 2:
        return options, None
    fingerprint = frame_fingerprint(fixations_filtered)
    if order in ("Most similar", "Most different"):
        # NLD is only meaningful between readings of the same text, so score the
        # 📄 group and leave everyone else after it in default order.
        same_text = [o for o in options if SAME_TEXT_MARKER in o[3]]
        rest = [o for o in options if SAME_TEXT_MARKER not in o[3]]
        if not same_text:
            return options, "No same-text candidates to score — default order."
        scored = same_text[:_CMP_MAX_SCORE]
        overflow = same_text[_CMP_MAX_SCORE:]
        scores = _c_compare_nld(
            fixations_filtered,
            trial_words,
            fingerprint,
            frame_fingerprint(trial_words),
            str(selected_participant),
            str(selected_trial),
            tuple((str(o[0]), str(o[1])) for o in scored),
        )

        def _score(opt) -> float:
            v = scores.get((str(opt[0]), str(opt[1])))
            return float("nan") if v is None else v

        reverse = order == "Most different"
        # NaN-scored candidates go last within the scored group either way.
        scored = sorted(
            scored,
            key=lambda o: (
                pd.isna(_score(o)),
                -_score(o) if (reverse and pd.notna(_score(o))) else _score(o),
            ),
        )
        note = f"Same-text trials ordered by NLD ({order.lower()} to A first)"
        if overflow:
            note += f"; scored the first {_CMP_MAX_SCORE} of {len(same_text)}"
        if rest:
            note += "; other-text trials follow unscored"
        return scored + overflow + rest, note + "."
    if order in ("Most fixations", "Longest reading"):
        stats = _c_compare_trial_stats(fixations_filtered, fingerprint)
        idx = 0 if order == "Most fixations" else 1

        def _stat(opt) -> float:
            v = stats.get((str(opt[0]), str(opt[1])))
            return float(v[idx]) if v else -1.0

        return sorted(options, key=_stat, reverse=True), None
    return options, None


def _render_compare_selector(
    combos: pd.DataFrame,
    selection_mode: str,
    selected_participant: str,
    selected_trial: str,
    selected_text: Optional[str],
    animate: bool = False,
    fixations_filtered: Optional[pd.DataFrame] = None,
    trial_words: Optional[pd.DataFrame] = None,
) -> tuple[Optional[str], Optional[str]]:
    """The compare-trial (B) selector, rendered above the chips (CMP-1).

    Mirrors the main trial picker: a ``selectbox`` showing the trial id (+ 📄/👤
    markers) and a scrubbing ``select_slider`` showing ``"index/TOTAL · <trial
    id>"``, plus ◀ ▶ step buttons, plus a CMP-6 **Order by** picker that can
    rank the candidates by similarity to the selected trial (NLD), fixation
    count, or total reading time instead of data order. The overlay layout +
    A/B-legend config now live in the rail's **⚙️ Compare** popover (under the
    Compare toggle). Returns ``(participant, trial)``."""
    options = build_comparison_options(
        combos, selection_mode, selected_participant, selected_trial, selected_text
    )
    if not options:
        st.info("No other trials available for comparison.")
        return None, None

    # CMP-6: the candidate ordering is visually LAST in the picker row, after the
    # step buttons. It still executes before the selectbox/slider below, so a
    # change applies to their list on the same run. UI-only — it never travels in a
    # deep link or saved config (same call as `share_identity_mode`, DATA-16/S3).
    n = len(options)
    orderable = n > 2 and fixations_filtered is not None and trial_words is not None
    order_note = None
    order_col = None
    if n > 1:
        if orderable:
            sel_col, slider_col, prev_col, next_col, order_col = st.columns(
                [2.8, 3.9, 0.55, 0.55, 1.9], vertical_alignment="bottom"
            )
        else:
            sel_col, slider_col, prev_col, next_col = st.columns(
                [3, 5, 0.55, 0.55], vertical_alignment="bottom"
            )
    else:
        sel_col = st

    if orderable and order_col is not None:
        order = order_col.selectbox(
            "Order candidates by",
            options=list(_CMP_ORDER_OPTIONS),
            key="single_compare_order",
            label_visibility="collapsed",
            help="Order the candidate trials (B): **Same text first** — the "
            "default data order; **Most similar / Most different** — by NLD on "
            "the fixated-word sequence against the selected trial A (same-text "
            "trials only, others follow unscored); **Most fixations** / "
            "**Longest reading** — by size of the reading.",
        )
        options, order_note = _order_compare_options(
            options,
            order,
            fixations_filtered,
            trial_words,
            selected_participant,
            selected_trial,
        )

    labels = [opt[2] for opt in options]
    label_to_trial = {opt[2]: (opt[0], opt[1]) for opt in options}
    label_to_id = {opt[2]: str(opt[1]) for opt in options}

    sel_key = "single_compare_trial"
    pos_key = "single_compare_pos"
    current = st.session_state.get(sel_key)
    if current not in labels:
        current = labels[0]
        st.session_state[sel_key] = current

    if n > 1:
        idx_of = {lbl: i for i, lbl in enumerate(labels)}
        # Mirror the slider to the current selection before it renders.
        st.session_state[pos_key] = current

        def _on_compare_slider() -> None:
            st.session_state[sel_key] = st.session_state[pos_key]

        def _step_compare(delta: int) -> None:
            try:
                pos = labels.index(st.session_state.get(sel_key))
            except ValueError:
                pos = 0
            st.session_state[sel_key] = labels[max(0, min(pos + delta, n - 1))]

        current_idx = labels.index(current)

    selected_compare_label = sel_col.selectbox(
        "Compare with trial (B)",
        options=labels,
        key=sel_key,
        help="📄 = same text as the primary trial · 👤 = same participant."
        + (" Animated comparison overlays both on one clock." if animate else ""),
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
        prev_col.button(
            "◀",
            key="single_compare_prev",
            on_click=_step_compare,
            args=(-1,),
            disabled=current_idx == 0,
            help="Previous candidate",
            width="stretch",
        )
        next_col.button(
            "▶",
            key="single_compare_next",
            on_click=_step_compare,
            args=(1,),
            disabled=current_idx == n - 1,
            help="Next candidate",
            width="stretch",
        )

    if order_note:
        st.caption(order_note)
    if selected_compare_label:
        return label_to_trial[selected_compare_label]
    return None, None


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
_QA_NAME_HINTS = ("question", "answer", "correct", "response", "prompt")


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
        0,
        1,
        0.0,
        1.0,
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
    """Trial-level columns holding question / answer content.

    Matches columns whose name reads as question/answer/correct/… but excludes
    span-named columns and **per-word-varying boolean** columns: a boolean that
    differs across the trial's words (e.g. a per-word ``response`` mask) is
    span-like data, not a trial-level field, and rendering its first value as
    ``"Response: True"`` would be misleading. A *constant* boolean (e.g.
    ``is_correct``) is a legitimate trial-level field and is kept. Also excludes
    plain numeric columns (UX-32): a Q&A field is inherently text or boolean, so
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
    trial_words: pd.DataFrame, span_bg: Optional[dict] = None
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


def _first_str(df: pd.DataFrame, col: str) -> Optional[str]:
    """First non-null value of ``col`` as a string, or None."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            return str(vals.iloc[0])
    return None


def _first_num(df: pd.DataFrame, col: str) -> Optional[float]:
    """First non-null value of ``col`` as a float, or None when absent/empty."""
    if col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if not vals.empty:
            return float(vals.iloc[0])
    return None


def _first_bool(df: pd.DataFrame, col: str) -> Optional[bool]:
    """First non-null value of ``col`` as a bool, or None when absent/empty."""
    if col in df.columns:
        vals = df[col].dropna()
        if not vals.empty:
            return bool(vals.iloc[0])
    return None


def _span_fixated_note(
    trial_words: pd.DataFrame,
    trial_fixations: Optional[pd.DataFrame],
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
    trial_fixations: Optional[pd.DataFrame] = None,
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
    span_cols = _detect_span_columns(trial_words)
    span_bg = {c: _span_bg_for(c, i) for i, c in enumerate(span_cols)}
    qa_cols = _detect_question_columns(trial_words)

    container = (
        st.container()
        if bare
        else st.expander("Stimulus & questions", expanded=expanded)
    )
    with container:
        _render_paragraph_with_spans(trial_words, span_bg)

        # Breathing room between the stimulus text and the question block (generic
        # Q&A fields and/or MultiplEYE's structured comprehension questions).
        has_comprehension = bool(_first_str(trial_words, "comprehension_questions"))
        if qa_cols or has_comprehension:
            st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

        # MultiplEYE structured comprehension questions (target + distractors).
        _render_comprehension_questions(trial_words)

        # Question / answer fields, generically. Keep OneStop's combined
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
) -> Optional[str]:
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
    data_source: Optional[str],
    app_version: str,
    exported_at: str,
    compare_styles: Optional[list] = None,
) -> dict:
    """Build the "💾 Save & restore" JSON config dict (pure — no Streamlit).

    Schema 2 captures the full figure configuration (layers, colouring, sizing,
    text/highlighting, canvas, axes, trial selection), every per-trial
    annotation, and provenance (app version, export date, data source, column
    mapping)."""
    # ENG-11: PLOT_CONFIG_SCHEMA is the single source of truth for the version;
    # bump it (+ register a migration) in url_state when this layout changes.
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

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
        },
        "axes": {"x_field": x_field, "y_field": y_field},
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
        "annotations": annotation_records,
    }


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
    """Render the "💾 Save & restore" sidebar panel (DATA-9).

    Merges the former Plot-configuration and Annotations panels into one: a
    single JSON sidecar that captures the full figure configuration (layers,
    colouring, sizing, text/highlighting, canvas, axes, trial selection) PLUS
    every per-trial annotation, with a matching uploader to restore it all. So a
    reviewer can save, share, and reload the exact state behind a figure. The
    upload is *applied* in ``app._apply_uploaded_plot_config`` (it runs before
    the widgets render). ``slot`` is a keyed sidebar container reserved by
    ``app.main`` so the panel sits under the controls rather than after the tab.
    """
    from datetime import datetime

    from scanpath_studio import __version__, annotations

    container = slot if slot is not None else st.sidebar
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
    with container.expander("💾 Save & restore", expanded=False):
        n_anno = len(annotation_records)
        st.caption(
            "Save the full plot configuration **and** all annotations "
            f"({n_anno} trial{'s' if n_anno != 1 else ''}) — plus the data "
            "source and column mapping — to one JSON file, or restore them. "
            "Everything that fits the loaded data is re-applied."
        )
        st.download_button(
            "⬇ Download (JSON)",
            data=json.dumps(plot_config, indent=2),
            # General filename — the config spans the whole session, not one
            # trial.
            file_name="scanpath_studio_config.json",
            mime="application/json",
            key="plot_config_download",
            width="stretch",
        )
        # S3: unlike the Share link — which now lets you drop the ids — this
        # file always carries the selected participant/trial AND every note you
        # have typed, for every annotated trial. Say so before it is mailed on.
        st.caption(
            "⚠️ The file names the selected participant and trial, and includes "
            "the text of every annotation note you've written."
        )
        st.file_uploader(
            "Restore from JSON",
            type=["json"],
            key="plot_config_upload",
            help="Re-apply settings + annotations from a file saved here earlier. "
            "Anything that doesn't fit the loaded data is skipped.",
        )
        skipped = st.session_state.get("_plot_config_skipped")
        if skipped:
            st.caption(
                "⚠️ Not applied (no match in the current data): "
                + ", ".join(skipped)
                + "."
            )


def _ordered_trial_ids(combos: pd.DataFrame) -> list[str]:
    """Stable trial_id ordering used by the under-image Prev/Next buttons.

    Mirrors `_select_trial_none_mode`'s sort so the under-image nav lands on
    the same trial as the side-panel Prev/Next when both are present.
    """
    trial_col = "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
    return sorted(combos[trial_col].dropna().astype(str).unique().tolist())


def _build_compare_meta(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    selected_participant: str,
    selected_trial: str,
    compare_participant: Optional[str],
    compare_trial: Optional[str],
) -> Optional[dict]:
    """Build the second trial's words/fixations + column labels for the
    side-by-side metadata table, or None when no comparison is active."""
    if compare_participant is None or compare_trial is None:
        return None
    compare_words = extract_trial(words_filtered, compare_participant, compare_trial)
    compare_fix = extract_trial(fixations_filtered, compare_participant, compare_trial)
    # Short, distinct column headers: participant ids when comparing different
    # participants (the common same-text case), else the trial ids — the long
    # ids otherwise overflow the narrow panel.
    if str(selected_participant) != str(compare_participant):
        label_primary = str(selected_participant)
        label_compare = str(compare_participant)
    else:
        label_primary = str(selected_trial)
        label_compare = str(compare_trial)
    return {
        "words": compare_words,
        "fixations": compare_fix,
        "label_primary": label_primary,
        "label_compare": label_compare,
        "participant": compare_participant,
        "trial": compare_trial,
    }


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
    words_b: Optional[pd.DataFrame],
    fixations_b: Optional[pd.DataFrame],
    selected_participant: str,
    selected_trial: str,
    compare_participant: Optional[str],
    compare_trial: Optional[str],
    playback_speed: float,
    grid_step_ms: Optional[float] = None,
    max_frames: Optional[int] = None,
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
    else:
        st.info(
            f"Reading time: {reading_span_ms / 1000:.1f}s · "
            f"Playback at ×{playback_speed:g}: {playback_ms / 1000:.1f}s"
        )
    # VIZ-11 follow-up: state what the chosen grid actually produced. The cap
    # coarsening the step used to be invisible, which is the whole reason the
    # setting felt arbitrary.
    grid = (
        f"**{summary['n_frames']}** frames · one every "
        f"{summary['step_ms']:.0f} ms of reading"
    )
    if summary["coarsened"]:
        grid += (
            f" — coarsened from {summary['requested_step_ms']:.0f} ms to stay "
            f"under the {max_frames or 360}-frame cap"
        )
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
    combo_row: Optional[dict] = None,
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
    )
    title = render_pattern(title_pattern, fields) if title_pattern else ""
    caption = render_pattern(caption_pattern, fields) if caption_pattern else ""
    annotate_figure(fig, title=title, caption=caption)


def _resolve_compare_label(
    idx: int,
    participant: Optional[str],
    trial: Optional[str],
    trial_words: Optional[pd.DataFrame],
    trial_fixations: Optional[pd.DataFrame],
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
    )
    return render_pattern(pattern, fields) or default


def _build_and_render_animation(
    trial_words: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    words_b: Optional[pd.DataFrame],
    fixations_b: Optional[pd.DataFrame],
    selected_participant: str,
    selected_trial: str,
    compare_participant: Optional[str],
    compare_trial: Optional[str],
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    playback_speed: float,
    line_spacing: float,
    scale_text_to_boxes: bool,
    drift_corrected: bool = False,
    background_image: Optional[str] = None,
    background_image_size: Optional[Tuple[float, float]] = None,
    background_image_origin: Optional[Tuple[float, float]] = None,
    background_image_opacity: float = 1.0,
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
    fig = make_scanpath_animation(
        trial_words,
        trial_fixations,
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
        base_font_size=int(base_font_size),
        font_family=font_family,
        playback_speed=playback_speed,
        show_words=viz_settings["show_words"],
        show_word_labels=viz_settings["show_labels"],
        show_saccades=viz_settings["show_saccades"],
        show_saccade_arrows=viz_settings.get("show_saccade_arrows", False),
        show_order=viz_settings["show_order"],
        marker_size_range=viz_settings["marker_size_range"],
        order_font_size=viz_settings["order_font_size"],
        order_font_color=viz_settings["order_font_color"],
        color_by=viz_settings["color_by"],
        # Drift correction colours the replay by assigned line, exactly as the
        # static figure does once an algorithm is picked.
        color_by_line=bool(viz_settings.get("color_by_line", False) or drift_corrected),
        fixation_colorscale=viz_settings["fixation_colorscale"],
        fixation_color_range=viz_settings["fixation_color_range"],
        fixation_flags=viz_settings.get("fixation_flags"),
        show_colorbars=viz_settings["show_colorbars"],
        colorbar_orientation=viz_settings.get("colorbar_orientation", "Vertical"),
        colorbar_tickangle=viz_settings.get("colorbar_tickangle", 0),
        colorbar_tickfont_size=viz_settings.get("colorbar_tickfont_size", 12),
        saccade_color=viz_settings.get("saccade_color", SACCADE_COLOR),
        saccade_style=SACCADE_DASH_OPTIONS.get(
            viz_settings.get("saccade_style", "Solid"), "solid"
        ),
        saccade_width=viz_settings.get("saccade_width", DEFAULT_SACCADE_WIDTH),
        hollow_fixations=viz_settings.get("hollow_fixations", False),
        fixation_opacity=viz_settings.get("fixation_opacity", 1.0),
        fixation_color=viz_settings.get("fixation_color", DEFAULT_FIXATION_COLOR),
        fixation_symbol=viz_settings.get("fixation_symbol", DEFAULT_FIXATION_SYMBOL),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        # The replay marks the critical span in the word *labels* only — it has no
        # border-overlay layer — so gate on "Mark text" exactly as
        # `make_scanpath_figure` does internally for its text channel.
        highlight_column=_marked_text_column(viz_settings),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        word_hover_measure=viz_settings.get(
            "word_hover_measure", "total_fixation_duration_ms"
        ),
        word_hover_fields=viz_settings.get("word_hover_fields"),
        fixation_hover_fields=viz_settings.get("fixation_hover_fields"),
        background_color=viz_settings.get("background_color"),
        fit_to_monitor=viz_settings.get("fit_to_monitor", True),
        show_legend=viz_settings.get("show_compare_legend", False),
        fixations_b=fixations_b if dual else None,
        words_b=words_b if dual else None,
        # UX-31: an explicit `cmp{idx}_label_pattern` (set in the ⚙️ Compare
        # options popover, EXP-2-style) overrides the auto label.
        label_a=(
            _resolve_compare_label(
                0, selected_participant, selected_trial, trial_words, trial_fixations
            )
            if dual
            else "Scanpath A"
        ),
        label_b=(
            _resolve_compare_label(
                1, compare_participant, compare_trial, words_b, fixations_b
            )
            if dual
            else "Scanpath B"
        ),
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
        background_image=background_image,
        background_image_size=background_image_size,
        background_image_origin=background_image_origin,
        background_image_opacity=background_image_opacity,
        autoplay=viz_settings.get("anim_autoplay", True),
        anim_grid_step_ms=grid_step_ms,
        anim_max_frames=max_frames,
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


def _render_export_panel(
    displayed_fig,
    *,
    animate: bool,
    save_slug: str,
    playback_ms: Optional[float],
    file_stem: Optional[str],
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
) -> None:
    """Consolidated Export subtab: the currently-viewed figure on top, then a
    bulk multi-trial export below.

    Replaces both the old single-trial Export toggle and the standalone Bulk
    Export tab. "This trial" exports the live figure (static PNG/SVG/PDF/HTML, or
    the HTML/GIF/MP4 animation when animating) so the on-screen view — including
    a comparison or animation — round-trips exactly; the bulk section rebuilds
    static figures across many trials."""
    st.markdown("## This trial")
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

    st.divider()
    st.markdown("## Multiple trials")
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
    participant: Optional[str],
    fields,
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
    computed summary stats in the **Details** popover the caller renders from the
    returned list.

    ``fields`` is the configurable list of fields to surface (the ✏️ Edit chips
    popover). A data column that varies within the trial is shown (first value)
    but flagged with ⚠️.

    Returns the ``(label, value)`` summary stats for the Details popover; empty
    when the user has no summary chips selected."""
    primary: list[tuple[str, str]] = []  # identity + conditions (inline)
    summary: list[tuple[str, str]] = []  # computed stats (inside "More")
    summary_lookup: Optional[dict] = None  # computed once, only if a summary chip
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
    if primary:
        st.markdown(
            '<div class="sps-trial-chips">'
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
    """The **Details** popover beside the chip strip: the computed summary stats.

    UX-11 split the strip by *kind*: conditions are chips (short, colour-coded,
    scannable), while reading time / word count / fixation counts are derived
    numbers that read far better as a key→value list — and are the "on demand"
    half of the strip's job. Renders nothing when the user has no summary chips
    selected, so the control never appears empty.
    """
    if not summary:
        return
    with host.popover("Details", width="content", help="Summary stats for this trial."):
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
    raw_gaze: Optional[pd.DataFrame] = None,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    combos_all: Optional[pd.DataFrame] = None,
    words_all: Optional[pd.DataFrame] = None,
    fixations_all: Optional[pd.DataFrame] = None,
    share_renderer: Optional[Callable[[], None]] = None,
    # UX-25: renders the data-source picker into the "Filter by" row's first
    # column. Passed by ``app.main`` (which owns the source list + wizard hooks).
    data_source_renderer: Optional[Callable[[object], None]] = None,
    canvas_renderer: Optional[Callable[[Any], None]] = None,
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
    3. A full-width **subtab bar** below: 📝 Annotations · Stimulus & questions ·
       Export · 🔎 Data Inspection · 🔗 Share. Export folds in the former Bulk
       Export tab (``_render_export_panel``); Data Inspection (the former
       standalone view) renders inline here; Share (the former header popover)
       builds the deep link via ``share_renderer`` (passed by ``app.main``). The
       former Trial Info subtab was folded into the chips above the plot. Save &
       restore lives in the sidebar.

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
    # live in the left column; the per-trial subtabs render full-width below. The
    # rail is kept narrow (the plot is the hero).
    plot_col, rail_col = st.columns([4, 1], gap="large")
    with rail_col:
        rail = st.container(key="scanpath_rail")

    with plot_col:
        # Narrow-by row: [Data source] [Filter by] [Text multiselect]
        # [Participant multiselect] [More popover]. UX-25 put the data source
        # first, so the row reads left-to-right as *which dataset → how to narrow
        # it → which trial*. The Text/Participant multiselects narrow the pool;
        # "More" holds the condition + annotation filters. The specific trial is
        # picked on the row below (select_trial → selectbox + slider + ◀ ▶).
        # Keyed wrapper so the welcome tour can spotlight the selection row.
        with st.container(key="tour_grp_trial_select"):
            nb_source, nb_label, nb_text, nb_part, more_col = st.columns(
                [2.2, 0.9, 2.2, 2.2, 1.1], vertical_alignment="center"
            )
            # Rendered by app (it owns the entry list + the wizard hooks) — see
            # app.render_data_source_picker; passed in so this row owns the layout.
            if data_source_renderer is not None:
                data_source_renderer(nb_source)
            nb_label.markdown("**Filter by**")
            render_narrow_by(
                words_all, fixations_all, text_host=nb_text, part_host=nb_part
            )
            with more_col:
                more_pop = st.popover("More", width="content")
                more_pop.caption("More ways to narrow — conditions & annotations.")
                render_trial_filters(words_all, fixations_all, host=more_pop)
            # Trial picker (its own row of columns): selectbox + slider + ◀ ▶.
            # Pass the More-popover filter columns so composite components that are
            # also conditions (e.g. repeated_reading_trial) narrow there, not as a
            # dedicated trial selector — keeping the picker stable across datasets.
            selected_participant, selected_trial, selection_mode, selected_text = (
                select_trial(
                    combos,
                    key_prefix="single",
                    filter_cols=_filter_fields_for(words_all, fixations_all),
                    # UX-10: the frames `combos` was built from, so the ⇅ sort
                    # popover can offer computed keys (fixation count, reading
                    # time) alongside the reader / text / condition columns.
                    words=words_filtered,
                    fixations=fixations_filtered,
                )
            )
        # Slots filled once the selection is resolved (chips need the trial). The
        # compare-trial selector (CMP-1) sits above the chips, below the picker.
        # Keyed containers double as welcome-tour spotlight targets.
        compare_slot = st.container()
        chips_slot = st.container(key="tour_grp_chips")
        plot_slot = st.container(key="tour_grp_plot")

    if not (selected_participant and selected_trial):
        return

    # Remember the resolved selection so the header Share button can build a deep
    # link back to exactly this trial (app._build_share_query reads it).
    st.session_state["_share_selection"] = {
        "participant_id": selected_participant,
        "trial_id": selected_trial,
    }

    trial_words = extract_trial(words_filtered, selected_participant, selected_trial)
    trial_fixations = extract_trial(
        fixations_filtered, selected_participant, selected_trial
    )
    trial_raw_gaze = pd.DataFrame()
    if raw_gaze is not None and not raw_gaze.empty:
        trial_raw_gaze = extract_trial(raw_gaze, selected_participant, selected_trial)
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

    # Render the rail (view modes + viz controls) before the figure so it sees the
    # resolved Animate / Compare / viz settings; its right-side position is fixed
    # by the column split regardless of render order.
    with rail:
        with rail.container(key="tour_grp_view_modes"):
            st.markdown("## 🎬 View modes")
            # Animate styled like a layer: a toggle + a ⚙ popover for its config
            # (playback speed) — matching Compare and the visualization layers below.
            # Seeded, not `value=`-defaulted: `single_animate` is restored pre-widget
            # by a deep link / saved config (see session_keys), and passing both makes
            # Streamlit warn (BUG-17). `setdefault` suffices — this toggle renders on
            # every run, so it never first mounts late the way a popover-bound widget
            # can (that case needs `persist_state="session"`; see BUG-15/ENG-36).
            st.session_state.setdefault("single_animate", False)
            animate = st.toggle(
                "🎬 **Animate**",
                key="single_animate",
                persist_state="session",
                help="Replay the trial fixation by fixation; the play / pause / "
                "restart controls sit below the plot.",
            )
            # Reading-time / playback info box, filled below once playback speed + any
            # compare trial are known (lives inside the Playback popover).
            anim_info_slot = None
            # Playback speed shows only when animating a trial that has fixations.
            # Default ×4 — a brisk review pace (real-time ÷ 4).
            playback_speed = _ANIM_DEFAULT_SPEED
            if animate and not trial_fixations.empty:
                with st.popover("⚙️ Playback", width="stretch"):
                    st.session_state.setdefault(
                        "single_playback_speed", _ANIM_DEFAULT_SPEED
                    )
                    playback_speed = st.select_slider(
                        "Playback speed",
                        options=_ANIM_SPEED_OPTIONS,
                        format_func=lambda x: _ANIM_SPEED_LABELS[
                            _ANIM_SPEED_OPTIONS.index(x)
                        ],
                        help="Playback speed relative to the recorded fixation timings.",
                        key="single_playback_speed",
                        persist_state="session",
                    )
                    # UX-30: the reading-time / playback-duration box reads as a
                    # consequence of the speed picked above, so it sits right below it
                    # instead of at the foot of the popover. `anim_info_slot` is only a
                    # placeholder here — Streamlit lays containers out in creation
                    # order, so the actual fill (below, once fixations/compare are
                    # known) still lands in this spot.
                    anim_info_slot = st.container()
                    # VIZ-10: start the replay automatically on load (at the speed
                    # above). Off → the figure waits on the ▶ Play button.
                    st.checkbox(
                        "Autoplay on load",
                        key="global_anim_autoplay",
                        persist_state="session",
                        help="Start the replay automatically when the plot loads, at "
                        "the playback speed set above. Turn off to start paused (press "
                        "▶ Play to run it).",
                    )
                    st.divider()
                    # VIZ-11 follow-up: the frame grid is a real tradeoff — smoothness
                    # against frame count, which is what export size and render time
                    # are made of. It used to be decided for the user in two module
                    # constants, and the cap coarsened the grid silently.
                    st.caption("**Frame grid**")

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
                    st.segmented_control(
                        "Animation quality",
                        options=["Coarse", "Fine", "Custom"],
                        key="global_anim_quality",
                        persist_state="session",
                        on_change=_apply_anim_quality,
                        help="**Coarse** — 300 ms / 120 frames for fast drafts. "
                        "**Fine** — 40 ms / 900 frames for high-fidelity review. "
                        "**Custom** reveals the sliders below, pre-seeded with "
                        "whichever preset was active last.",
                    )

                    def _mark_anim_quality_custom() -> None:
                        st.session_state["global_anim_quality"] = "Custom"

                    if st.session_state["global_anim_quality"] == "Custom":
                        _numeric_slider(
                            st,
                            "Frame every (ms)",
                            key="global_anim_grid_step_ms",
                            persist_state="session",
                            min_value=20,
                            max_value=500,
                            step=10,
                            on_change=_mark_anim_quality_custom,
                            help="How often a frame is emitted along the reading "
                            "clock. Smaller is smoother and larger to export; the "
                            "slider scrubs linearly through seconds either way.",
                        )
                        _numeric_slider(
                            st,
                            "Max frames",
                            key="global_anim_max_frames",
                            persist_state="session",
                            min_value=30,
                            max_value=2000,
                            step=10,
                            on_change=_mark_anim_quality_custom,
                            help="Hard ceiling on the frame count. A long reading "
                            "coarsens the grid to stay under it rather than "
                            "emitting thousands of frames (which balloons the "
                            "GIF/MP4 export).",
                        )
            # Compare is a view mode (toggle here); the second-trial selector renders
            # above the chips in the plot column (compare_slot below), mirroring the
            # main trial picker (CMP-1).
            compare_enabled = st.toggle(
                "⚖️ **Compare**",
                value=False,
                key="single_compare_toggle",
                persist_state="session",
                help=(
                    "Co-animate a second reading on one clock."
                    if animate
                    else "Overlay another trial's scanpath or view them side by side."
                ),
            )
            # ENG-24: controls must gate against the mode the renderer can actually
            # enter, not merely the raw toggle. Compare needs at least one candidate;
            # Animate is resolved independently because it remains a distinct empty-
            # state when the selected trial has no fixations.
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
            # Compare config in the rail (moved out of the inline selector): the
            # overlay/side-by-side/stacked layout + the show-A/B-legend toggle. The
            # layout reaches the figure via session_state (`single_compare_layout`),
            # read into `compare_layout` below.
            if compare_enabled:
                with st.popover("⚙️ Compare options", width="stretch"):
                    if not animate:
                        # Seed so the control shows "Overlay" selected by default
                        # (the body reads this key to resolve compare_layout).
                        st.session_state.setdefault("single_compare_layout", "Overlay")
                        st.segmented_control(
                            "View",
                            options=["Overlay", "Side by side", "Stacked"],
                            key="single_compare_layout",
                            persist_state="session",
                            help="Stacked = trials shown one above the other.",
                        )
                    show_legend_now = st.checkbox(
                        "Show A/B legend",
                        key="global_show_compare_legend",
                        persist_state="session",
                        help="Show a legend naming the two scanpaths on the overlay "
                        "(off by default — the colours already tell A and B apart).",
                    )
                    if show_legend_now:
                        # UX-31: override the auto "participant · trial" label,
                        # EXP-2-style (same pattern language + live preview as
                        # the rail's title/caption). Empty = the auto label.
                        st.text_input(
                            "Label A",
                            key="cmp0_label_pattern",
                            persist_state="session",
                            help="Same fields as the title/caption pattern in "
                            "📐 Figure & axes. Leave empty for the default "
                            "`{participant_id} · {trial_id}`.",
                        )
                        st.text_input(
                            "Label B",
                            key="cmp1_label_pattern",
                            persist_state="session",
                            help="Leave empty for the default "
                            "`{participant_id} · {trial_id}`.",
                        )
        st.divider()
        st.markdown("## 🎨 Visualization")
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

    # Second-trial selector + layout/legend options, rendered above the chips in
    # the plot column (CMP-1). Filled after the rail so the per-scanpath compare
    # styles (cmp*_ keys) are already seeded — the A/B swatches then match the
    # figure exactly (CMP-3). Only shown when Compare is on.
    compare_participant, compare_trial = None, None
    # Layout comes from the rail's Compare-config popover via session_state; an
    # animated comparison always co-animates on one clock, so force overlay then.
    if animate:
        compare_layout = "overlay"
    else:
        compare_layout = {
            "Overlay": "overlay",
            "Side by side": "side_by_side",
            "Stacked": "stacked",
        }.get(st.session_state.get("single_compare_layout"), "overlay")
    if compare_enabled:
        with compare_slot:
            compare_participant, compare_trial = _render_compare_selector(
                combos,
                selection_mode,
                selected_participant,
                selected_trial,
                selected_text,
                animate=animate,
                # CMP-6: lets the selector order candidates by similarity to the
                # selected trial (NLD), fixation count, or reading time.
                fixations_filtered=fixations_filtered,
                trial_words=trial_words,
            )

    global_raw_toggle = bool(viz_settings.get("show_raw_gaze"))
    effective_show_raw_gaze = bool(global_raw_toggle and trial_has_raw_gaze)
    figure_settings = _build_figure_settings(viz_settings, effective_show_raw_gaze)
    figure_settings["raw_gaze"] = trial_raw_gaze if trial_has_raw_gaze else None
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
    compare_meta = _build_compare_meta(
        words_filtered,
        fixations_filtered,
        selected_participant,
        selected_trial,
        compare_participant,
        compare_trial,
    )
    comparing = compare_participant is not None and compare_trial is not None
    compare_fix = compare_meta["fixations"] if compare_meta else pd.DataFrame()

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
        viz_settings,
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
    cmp_fixations = fixations_filtered
    if comparing and (
        drift_corrected_primary or plot_compare_fix is not fig_compare_fix
    ):
        if (str(compare_participant), str(compare_trial)) == (
            str(selected_participant),
            str(selected_trial),
        ):
            cmp_fixations = plot_fixations
        else:
            cmp_fixations = pd.concat([plot_fixations, plot_compare_fix])

    # Condition chips above the plot — configurable via the sidebar picker
    # (`trial_chip_fields`); `Field = Value` for the chosen fields. When comparing,
    # a second labelled strip shows the compared trial too.
    with chips_slot:
        # Inline "Edit chips" popover at the right end of the chip row (UX-1) —
        # replaces the former sidebar 🏷️ Trial chips picker. Rendered before the
        # strip reads `trial_chip_fields` so an edit/reorder applies the same run.
        # UX-11: three columns on one row — the wrapping chip strip, then the
        # two controls. They're top-aligned, not centre-aligned: the strip can
        # now wrap to several lines, and a centred control would drift to the
        # middle of a tall strip instead of sitting on the first chip's line.
        # Kept at the top level rather than nesting the controls in one column,
        # so no `st.columns` nesting is involved.
        strip_col, details_col, edit_col = st.columns(
            [11, 1.6, 0.9], vertical_alignment="top"
        )
        with edit_col:
            # Keyed container so styles.py can shrink the popover trigger to chip
            # size and drop it onto the chip baseline.
            edit_box = st.container(key="chip_edit_box")
            with edit_box.popover(
                "✏️",
                help="Edit which fields show as chips above the plot, and drag to "
                "reorder them.",
                width="content",
            ):
                render_trial_chip_picker(words_all, fixations_all, host=st.container())
        chip_fields = st.session_state.get("trial_chip_fields") or []
        details_box = details_col.container(key="chip_details_box")
        with strip_col:
            # When comparing, label each chip strip with its trial id coloured to
            # match the scanpath in the overlay (A = primary colour, B = compared
            # colour) — replaces the old "■ A … ■ B compared with:" legend line.
            color_a = color_b = None
            if comparing and compare_meta:
                _ca, _cb = _collect_compare_styles()
                color_a = _ca.get("fix_color") or compare_palette_color(0)
                color_b = _cb.get("fix_color") or compare_palette_color(1)
                st.markdown(
                    f'<span style="color:{color_a};font-weight:700">'
                    f"{html.escape(str(compare_meta['label_primary']))}</span>",
                    unsafe_allow_html=True,
                )
            summary = _render_trial_condition_chips(
                trial_words, trial_fixations, selected_participant, chip_fields
            )
            if comparing and compare_meta:
                st.markdown(
                    f'<span style="color:{color_b};font-weight:700">'
                    f"{html.escape(str(compare_meta['label_compare']))}</span>",
                    unsafe_allow_html=True,
                )
                _render_trial_condition_chips(
                    compare_meta["words"],
                    compare_meta["fixations"],
                    compare_participant,
                    chip_fields,
                )
        # Rendered after the strip so it reads the *primary* trial's stats; the
        # compared trial's chips stay inline beside its own label.
        _render_trial_details_popover(summary, details_box)

    displayed_fig = None
    save_slug = f"{selected_participant}__{selected_trial}"
    anim_playback_ms = None
    anim_file_stem = None
    # Use the windowed second scanpath: a window that empties B falls back to a
    # single-trial animation (and info box).
    dual_anim = animate and comparing and not fig_compare_fix.empty

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
                        canvas_width=canvas_width,
                        canvas_height=canvas_height,
                        base_font_size=base_font_size,
                        font_family=font_family,
                        viz_settings=viz_settings,
                        playback_speed=playback_speed,
                        line_spacing=line_spacing,
                        scale_text_to_boxes=scale_text_to_boxes,
                        drift_corrected=drift_corrected_primary,
                        background_image=figure_settings.get("background_image"),
                        background_image_size=figure_settings.get(
                            "background_image_size"
                        ),
                        background_image_origin=figure_settings.get(
                            "background_image_origin"
                        ),
                        background_image_opacity=figure_settings.get(
                            "background_image_opacity", 1.0
                        ),
                    )
                )
            if comparing and compare_fix.empty:
                st.warning(
                    "The selected second scanpath has no fixations after "
                    "filtering — showing only the first scanpath."
                )
        elif comparing:
            displayed_fig = _render_comparison_figure(
                combos,
                words_filtered,
                cmp_fixations,
                selected_participant,
                selected_trial,
                selected_text,
                compare_participant,
                compare_trial,
                canvas_width,
                canvas_height,
                font_family,
                base_font_size,
                viz_settings,
                layout=compare_layout,
                line_spacing=line_spacing,
                scale_text_to_boxes=scale_text_to_boxes,
                fix_index_range=fix_range,
                background_image=figure_settings.get("background_image"),
                background_image_size=figure_settings.get("background_image_size"),
                background_image_origin=figure_settings.get("background_image_origin"),
                background_image_opacity=figure_settings.get(
                    "background_image_opacity", 1.0
                ),
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
            build_kwargs = dict(
                canvas_width=int(canvas_width),
                canvas_height=int(canvas_height),
                base_font_size=int(base_font_size),
                font_family=font_family,
                x_field=x_field,
                y_field=y_field,
                **figure_settings,
            )
            # Drift-correction overrides (color_by_line / connectors) win over the
            # base figure settings.
            build_kwargs.update(extra_settings)
            displayed_fig = _cached_scanpath_figure(
                trial_words,
                plot_fixations,
                build_kwargs,
                fig_key=_figure_input_key(trial_words, plot_fixations, build_kwargs),
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

    # Per-trial panels sit BELOW the plot as a single full-width subtab bar (they
    # must be created outside the columns to span the page width). Trial Info is
    # gone — the chip strip above the plot now carries the trial's identity,
    # conditions and summary stats (configurable via the sidebar 🏷️ Trial chips).
    # Keyed wrapper so the welcome tour can spotlight the per-trial subtab bar.
    with st.container(key="tour_grp_subtabs"):
        (
            tab_annot,
            tab_stim,
            tab_compare,
            tab_align,
            tab_export,
            tab_inspect,
            tab_share,
        ) = st.tabs(
            [
                "📝 Annotations",
                "Stimulus & questions",
                "🔬 Comparisons",
                "📐 Line assignment",
                "Export",
                "🔎 Data Inspection",
                "🔗 Share",
            ]
        )
    with tab_annot:
        render_trial_annotations(selected_participant, selected_trial, bare=True)
    with tab_stim:
        _render_paragraph_panel(trial_words, trial_fixations=trial_fixations, bare=True)
    with tab_compare:
        # ENG-8: Comparisons overlays the selected scanpath against other readings
        # of the SAME text, grouped by a chosen column (repeated readings, model
        # generations, …), scored by similarity. It uses the main scanpath
        # selection and renders no picker of its own. Line assignment is now its
        # own top-level subtab (tab_align), not nested here.
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
    with tab_align:
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
        )
    with tab_inspect:
        # The former Data Inspection view is now a subtab here (raw tables +
        # summary stats + column mapping). Uses the filtered frames in view.
        render_data_inspection_tab(
            words_filtered,
            fixations_filtered,
            raw_gaze if raw_gaze is not None else pd.DataFrame(),
        )
    with tab_share:
        # The former header Share popover, now a subtab. app.main passes the
        # renderer (it owns the deep-link builder + data source).
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
) -> None:
    """Render configurable bulk-export UI (artifact picker + run + download)."""
    options = render_export_options(
        st,
        combos,
        key_prefix="bulk_export",
        combos_all=combos_all,
        title_pattern=figure_settings.get("title_pattern", ""),
        caption_pattern=figure_settings.get("caption_pattern", ""),
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
    progress_bar = info_col.progress(0.0, text="Idle")
    if run:

        def on_progress(p: ExportProgress) -> None:
            frac = p.finished_trials / p.total_trials if p.total_trials else 1.0
            progress_bar.progress(
                min(max(frac, 0.0), 1.0),
                text=(
                    f"Exporting trial {p.finished_trials}/{p.total_trials} "
                    f"— {p.bytes_written / 1024:.0f} KB so far"
                ),
            )

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
            progress_callback=on_progress,
        )
        progress_bar.progress(1.0, text="Ready")
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
    selected_text: Optional[str],
    compare_participant: str,
    compare_trial: str,
    canvas_width: int,
    canvas_height: int,
    font_family: str,
    base_font_size: int,
    viz_settings: dict,
    layout: str = "overlay",
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
    fix_index_range=None,
    background_image: Optional[str] = None,
    background_image_size: Optional[Tuple[float, float]] = None,
    background_image_origin: Optional[Tuple[float, float]] = None,
    background_image_opacity: float = 1.0,
):
    """Render comparison figure for two trials.

    ``fix_index_range`` (VIZ-7) windows both scanpaths to a ``(start, end)``
    ``order_in_trial`` range; ``None`` shows the full readings. The
    ``background_image*`` group is the VIZ-4 stimulus-page layer, resolved by the
    caller (dataset image vs. upload, plus the manual nudge) and shared with the
    static + animation paths (VIZ-23).

    ``fixations_filtered`` may already carry PRE-3 drift-corrected ``y`` values —
    correction happens once, upstream of the render-mode split."""
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    # Window both compared trials to the chosen fixation-index range. Slicing the
    # whole frame is fine — make_comparison_figure only extracts the two trials.
    fixations_filtered = _slice_fix_range(fixations_filtered, fix_index_range)

    def _lookup_text_id(participant_id: str, trial_id: str) -> Optional[str]:
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
    compare_text_id = _lookup_text_id(compare_participant, compare_trial)
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
        )
    if st.session_state.get("cmp1_label_pattern"):
        compare_label = _resolve_compare_label(
            1,
            compare_participant,
            compare_trial,
            extract_trial(words_filtered, compare_participant, compare_trial),
            extract_trial(fixations_filtered, compare_participant, compare_trial),
        )

    fig_compare = make_comparison_figure(
        words_filtered,
        fixations_filtered,
        (selected_participant, selected_trial),
        (compare_participant, compare_trial),
        canvas_width=int(canvas_width),
        canvas_height=int(canvas_height),
        font_family=font_family,
        base_font_size=int(base_font_size),
        show_words=viz_settings["show_words"],
        show_word_labels=viz_settings["show_labels"],
        trial_labels=(primary_label, compare_label),
        layout=layout,
        style_a=viz_settings.get("compare_style_a"),
        style_b=viz_settings.get("compare_style_b"),
        marker_size_range=viz_settings.get("marker_size_range", (8, 24)),
        # CMP-7: the Fixations toggle reaches Compare too — two full sets of
        # markers bury the split-box heatmap the mode is there to show.
        show_fixations=viz_settings.get("show_fix", True),
        show_saccades=viz_settings.get("show_saccades", True),
        show_saccade_arrows=viz_settings.get("show_saccade_arrows", False),
        show_order=viz_settings.get("show_order", False),
        show_legend=viz_settings.get("show_compare_legend", False),
        order_font_size=viz_settings.get("order_font_size"),
        # "Color fixations by" (the metric → hue) applies in compare too.
        color_by=viz_settings.get("color_by"),
        fixation_colorscale=viz_settings.get(
            "fixation_colorscale", DEFAULT_FIXATION_COLORSCALE
        ),
        fixation_color_range=viz_settings.get("fixation_color_range"),
        # Marker *shape* is a global (the channel a greyscale print keeps); the
        # per-scanpath cmp{idx}_* styles own colour / size / opacity / hollow and
        # keep overriding the globals inside the builder.
        fixation_symbol=viz_settings.get("fixation_symbol", DEFAULT_FIXATION_SYMBOL),
        show_colorbars=viz_settings.get("show_colorbars", False),
        show_heatmap=viz_settings.get("show_heatmap", False),
        heatmap_metric=viz_settings.get("heatmap_metric", "duration_ms"),
        heatmap_colorscale=viz_settings.get(
            "heatmap_colorscale", DEFAULT_HEATMAP_COLORSCALE
        ),
        heatmap_range=viz_settings.get("heatmap_range"),
        heatmap_norm=viz_settings.get("heatmap_norm", "Linear"),
        colorbar_orientation=viz_settings.get("colorbar_orientation", "Vertical"),
        colorbar_tickangle=viz_settings.get("colorbar_tickangle", 0),
        colorbar_tickfont_size=viz_settings.get("colorbar_tickfont_size", 12),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        # No border-overlay layer here either — text marking only (see
        # `_marked_text_column`). Without it `highlight_text_color` was inert.
        highlight_column=_marked_text_column(viz_settings),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        background_color=viz_settings.get("background_color"),
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
        background_image=background_image,
        background_image_size=background_image_size,
        background_image_origin=background_image_origin,
        background_image_opacity=background_image_opacity,
        fit_to_monitor=viz_settings.get("fit_to_monitor", True),
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
    )
    _render_true_scale_chart(fig_compare, key="compare")
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
def _c_per_reader_word(_words, text_col, text_id, mkey, agg, normalize, fkey):
    return per_reader_word_measure(
        _words, text_col, text_id, MEASURES[mkey], agg=agg, normalize=normalize
    )


@st.cache_data(show_spinner=False)
def _c_cohort_profile(
    _words, text_col, text_id, mkey, agg, spread, normalize, min_readers, fkey
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
    )


@st.cache_data(show_spinner=False)
def _c_word_box_aggregate(_words, text_col, text_id, mkey, agg, fkey):
    return word_box_aggregate(_words, text_col, text_id, MEASURES[mkey], agg=agg)


@st.cache_data(show_spinner=False)
def _c_word_feature(_words, text_col, text_id, mkey, feature_col, agg, normalize, fkey):
    return word_measure_vs_feature(
        _words,
        text_col,
        text_id,
        MEASURES[mkey],
        feature_col,
        agg=agg,
        normalize=normalize,
    )


@st.cache_data(show_spinner=False)
def _c_word_rate(_words, text_col, text_id, min_readers, fkey):
    return word_rate_profile(_words, text_col, text_id, min_readers=min_readers)


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
    """Friendly label for a raw column id (group-definition pickers)."""
    return _GROUP_COL_LABELS.get(col, str(col).replace("_", " ").strip().title())


def _measure_picker(
    words, fixations, *, key, host=None, per_word_only=False, label="Measure"
) -> Optional["Measure"]:
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


def _both_frame_values(words, fixations, col):
    frames = [f for f in (fixations, words) if col in getattr(f, "columns", [])]
    vals = set()
    for f in frames:
        vals |= set(f[col].astype(str).dropna().unique())
    return sorted(vals)


def _group_split_columns(words, fixations):
    """Categorical columns present in BOTH frames with 2…60 values."""
    out = []
    text_col = _text_column(words) or _text_column(fixations)
    candidates = list(_GROUP_SPLIT_CANDIDATES) + ([text_col] if text_col else [])
    for col in dict.fromkeys(candidates):
        if col in words.columns and col in fixations.columns:
            n = words[col].astype(str).nunique()
            if 2 <= n <= 60:
                out.append(col)
    return out


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
    ):
        if not col:
            continue
        opts = _both_frame_values(words, fixations, col)
        if len(opts) < 2 or len(opts) > 400:
            continue
        sel = st.multiselect(pretty, opts, key=f"{key}_{col}", placeholder="All")
        if sel:
            spec[col] = sel
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
                ({col: a} if a else {}),
                ({col: b} if b else {}),
                _join_label(a) or "Group A",
                _join_label(b) or "Group B",
            )
        sel = host.multiselect(
            f"{_pretty_col(col)} =", vals, default=vals[:1], key=f"{key}_g"
        )
        return ({col: sel} if sel else {}), (_join_label(sel) or "All")
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


def _text_column(frame: pd.DataFrame) -> Optional[str]:
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
    canvas_renderer: Optional[Callable[[Any], None]] = None,
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


def _participant_picker(words, fixations, *, key, host=None, label="Reader"):
    host = host or st
    for frame in (fixations, words):
        if frame is not None and not frame.empty and "participant_id" in frame.columns:
            opts = sorted(frame["participant_id"].astype(str).unique())
            if opts:
                return host.selectbox(label, opts, key=key)
    return None


def _percentile(series: pd.Series, value) -> Optional[float]:
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
    top = st.columns([3, 2])
    text_col, text_id = _text_picker(words_filtered, key="ptext_text", host=top[0])
    if text_col is None or text_id is None:
        st.info("No text/passage column found.")
        return
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
        rate = _c_word_rate(words_filtered, text_col, text_id, min_readers, fkey)
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
            words_filtered, text_col, text_id, measure.key, agg, normalize, fkey
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
            words_filtered, text_col, text_id, measure.key, agg, normalize, fkey
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
            words_filtered, text_col, text_id, measure.key, agg, fkey
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
    top = st.columns([2, 3])
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
        specs = [
            ("wpm", "Reading speed", "{:.0f} wpm"),
            ("mean_fixation_ms", "Mean fixation", "{:.0f} ms"),
            ("n_fixations", "Fixations", "{:.0f}"),
            ("regression_rate", "Regression rate", "{:.0%}"),
            ("skip_rate", "Skip rate", "{:.0%}"),
            ("mean_saccade_px", "Mean saccade", "{:.1f} px"),
        ]
        present = [s for s in specs if s[0] in summary]
        cols = st.columns(len(present)) if present else []
        for col, (skey, label, fmt) in zip(cols, present):
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
                st.dataframe(trials, width="stretch", hide_index=True)
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
    fix_g = _c_enrich_fix(
        apply_group(fixations_filtered, spec or {}),
        words_g,
        frame_fingerprint(apply_group(fixations_filtered, spec or {})),
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
    if not st.toggle(
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

    ctrl_cols = st.columns([1, 1])
    with ctrl_cols[0]:
        n_cols = st.slider(
            "Panels per row",
            min_value=2,
            max_value=3,
            value=2,
            key="align_grid_ncols",
        )
    with ctrl_cols[1]:
        show_connectors = st.checkbox(
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


# Per-fixation continuous quantities can't group scanpaths into generations, so
# they're never offered as a generation identifier.
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
# Score at most this many generations (bounds the NLD cost for a high-cardinality
# column like participant_id on a big corpus). A safety budget above the grid cap
# so the "most similar" ranking still sees more candidates than it displays.
_GEN_MAX_SCORE = 60


def _generation_column_options(fixations: pd.DataFrame) -> list:
    """Columns that can identify the different generations of a scanpath.

    A generation column splits a text's scanpaths into comparable variants (a
    model / condition / reading id), so we offer the non-coordinate columns that
    actually vary and rank the most generation-like first (a name hit, then the
    reader / trial ids, then everything else)."""
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
            if fixations[c].nunique(dropna=True) >= 2:
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


def _n_readings(fix: pd.DataFrame) -> int:
    """How many distinct (participant, trial) readings a generation group holds.

    CMP-5: a high-level grouping column (a condition, a regime) can lump several
    readings into one "generation"; the panels say so instead of drawing the
    concatenation as if it were one scanpath."""
    if {"participant_id", "trial_id"} <= set(fix.columns):
        return int(len(fix[["participant_id", "trial_id"]].drop_duplicates()))
    return 1


def _panel_identity(fix: pd.DataFrame, gen_col: str, k: int) -> str:
    """CMP-5 panel suffix naming the trial(s) behind a generation panel.

    ``k`` is the group's reading count (from ``_n_readings``, computed once per
    rerun by the tab). A single-reading group is labelled with its
    ``participant · trial`` identity (unless the grouping column IS one of
    those, where the group label already says it); a multi-reading group is
    flagged with its reading count."""
    if k > 1:
        return f" · ⚠️ {k} readings"
    if gen_col in ("participant_id", "trial_id"):
        return ""
    if {"participant_id", "trial_id"} <= set(fix.columns) and not fix.empty:
        row = fix.iloc[0]
        return f" · {row['participant_id']} · {row['trial_id']}"
    return ""


def _collect_generations(
    fixations_pool: pd.DataFrame,
    trial_fixations: pd.DataFrame,
    gen_col: str,
    selected_participant,
    selected_trial,
) -> tuple:
    """Same-text scanpaths grouped by ``gen_col``, minus the selected trial.

    Scopes the pool to the selected trial's **text** so only variants of the SAME
    text are compared (using the best-available text identifier — normalized
    fixations use ``text_id`` / ``unique_text_id``, not always ``paragraph_id``),
    drops the selected (participant, trial) so it isn't scored against itself,
    groups the rest by ``gen_col`` → ``{label: fixations}``, and caps the panel
    count. Returns ``(generations, n_total)`` where ``n_total`` is the count
    before the cap."""
    if gen_col not in fixations_pool.columns or fixations_pool.empty:
        return {}, 0
    pool = fixations_pool
    # Match the canonical text-column priority used elsewhere (utils / pickers):
    # the first present on the fixations frame identifies the text.
    text_col = next(
        (
            c
            for c in (
                "unique_text_id",
                "text_id",
                "unique_paragraph_id",
                "paragraph_id",
            )
            if c in pool.columns
        ),
        None,
    )
    if text_col is not None and not trial_fixations.empty:
        text_val = trial_fixations[text_col].iloc[0]
        if pd.notna(text_val):
            pool = pool[pool[text_col] == text_val]
    if {"participant_id", "trial_id"} <= set(pool.columns):
        pool = pool[
            ~(
                (pool["participant_id"] == selected_participant)
                & (pool["trial_id"] == selected_trial)
            )
        ]
    generations: dict = {}
    for value, group in pool.groupby(gen_col, dropna=True):
        if group.empty:
            continue
        label = str(value)
        # Two distinct values that stringify the same (e.g. int 1 and str "1" in
        # a mixed object column) must not collapse — disambiguate so neither group
        # is silently lost and n_total stays accurate.
        if label in generations:
            label = f"{label} ({value!r})"
        generations[label] = group
    n_total = len(generations)
    # Cap the SCORING budget only (the grid/ranking cut to _GEN_MAX_PANELS by
    # similarity happens in the tab, after scoring). Sorted for determinism.
    ordered = dict(sorted(generations.items())[:_GEN_MAX_SCORE])
    return ordered, n_total


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

    Compares the scanpath for the *selected* trial (from the main trial picker)
    against other scanpaths of the same text — grouped by a user-chosen column (a
    reading regime, repeated-reading id, model generation, …) — and scores each
    against the selected reading (NLD plus placeholder metrics). The selection
    comes from the main scanpath picker; there's no separate picker here (ENG-8).
    """
    st.caption(
        "Compare the **selected** scanpath (from the main trial picker above) with "
        "other scanpaths of the same text — grouped by a column you choose (a "
        "reading regime, repeated-reading id, model generation, …) — and score how "
        "close each is to the selected reading."
    )
    if trial_words.empty or trial_fixations.empty:
        st.info(
            "Comparisons needs a **words + fixations** table for the selected "
            "trial — pick a trial with fixations in the main picker above."
        )
        return

    gen_cols = _generation_column_options(fixations_filtered)
    if not gen_cols:
        st.info(
            "No column in the fixations table can distinguish several scanpaths of "
            "the same text. Load data whose fixations carry a regime / condition / "
            "reading-id column (or use `participant_id` / `trial_id`) to compare "
            "several scanpaths over the same text here."
        )
        return

    col_side, col_main = st.columns([3, 7], gap="medium")

    with col_side:
        gen_col = st.selectbox(
            "Comparison column",
            options=gen_cols,
            key="multi_gen_col",
            help="Which column identifies the scanpaths to compare. Each distinct "
            "value — over the SAME text as the selected trial — becomes one "
            "comparison scanpath, scored against the selected reading.",
        )
        n_cols = st.slider(
            "Grid columns",
            min_value=1,
            max_value=4,
            value=3,
            key="multi_n_cols",
            help="Columns in the comparison grid (rows fill automatically).",
        )

    generations, n_total = _collect_generations(
        fixations_filtered,
        trial_fixations,
        gen_col,
        selected_participant,
        selected_trial,
    )
    if not generations:
        with col_main:
            st.info(
                f"No other scanpaths of this text found for **{gen_col}** in the "
                "current filter — only the selected scanpath matches. Widen the "
                "trial filters or pick a different comparison column."
            )
        return
    # More scanpaths of this text exist than we score (very high-cardinality
    # column); the ones we do score are ranked by similarity below.
    scored_capped = n_total > len(generations)

    with col_side:
        # ENG-8: no local fixation-index slider (it duplicated the main rail's
        # Fixations → index-range control) and no stimulus-text panel (the
        # top-level "Stimulus & questions" subtab already shows it). The grid and
        # table score the full readings; the rail control still windows the main
        # plot above.
        _render_trial_header(
            selected_participant,
            selected_trial,
            trial_words,
            prefix="Selected scanpath:",
        )
        if scored_capped:
            # CMP-5: say exactly what was dropped and how the kept ones were
            # chosen — the cap keeps the first _GEN_MAX_SCORE in label order.
            st.caption(
                f"{n_total} scanpaths of this text — more than the scoring "
                f"budget. Scoring the first {len(generations)} by "
                f"**{gen_col}** label order; the rest are not shown."
            )

    # Reuse the user's viz toggles but force a clean, comparable spatial view: the
    # grid is inherently spatial, and a generation frame may lack the selected
    # trial's extra columns, so pin axes to x/y, colour by duration_ms (present in
    # every frame), and turn off heatmap / raw gaze / by-line / flags (they group
    # by (participant_id, trial_id) against trial_words and would mis-render).
    base_settings = _build_figure_settings(viz_settings, False)
    base_settings["raw_gaze"] = None
    base_settings["line_spacing"] = line_spacing
    base_settings["scale_text_to_boxes"] = scale_text_to_boxes
    real_settings = {
        **base_settings,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "color_by": "duration_ms",
        "color_by_line": False,
        "fixation_flags": None,
    }
    panel_settings = {**real_settings, "show_word_labels": False, "show_order": False}

    def _make_fig(fix: pd.DataFrame, settings: dict):
        return make_scanpath_figure(
            trial_words,
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
    sliced_gens = generations

    with col_main:
        # CMP-5: name the reference prominently — it comes from the main trial
        # picker on a different part of the page, so the tab must say which
        # reading everything below is scored against.
        st.markdown(
            f"#### Selected scanpath — `{selected_participant}` · `{selected_trial}`"
        )
        real_fig = _make_fig(sliced_real, real_settings)
        _render_true_scale_chart(real_fig, key="multi_real")

        # Score every collected generation against the selected scanpath. The
        # per-generation NLD annotates each grid panel and orders both the grid and
        # the table; the full table is shown beneath the grid.
        table = compute_similarity_table(sliced_real, sliced_gens, trial_words)
        nld_by_gen = (
            dict(zip(table["Model"], table["NLD"])) if "NLD" in table.columns else {}
        )

        # Rank by similarity (lowest NLD = most similar; unscored/NaN last) and show
        # the closest _GEN_MAX_PANELS in the grid — never an arbitrary label subset.
        ranked = sorted(
            sliced_gens,
            key=lambda n: (
                pd.isna(nld_by_gen.get(n)),
                nld_by_gen.get(n) if pd.notna(nld_by_gen.get(n)) else 0.0,
            ),
        )
        grid_names = ranked[:_GEN_MAX_PANELS]
        grid_capped = len(sliced_gens) > _GEN_MAX_PANELS

        st.markdown("#### Other scanpaths")
        # CMP-5: state the grouping and the ranking rule in the tab itself —
        # one panel per value of the chosen column, ranked by similarity.
        rank_note = (
            f"One panel per **{gen_col}** value over the same text, ranked by "
            "NLD similarity to the selected scanpath above (most similar first)."
        )
        if grid_capped:
            rank_note += (
                f" Showing the **{_GEN_MAX_PANELS} most similar** of "
                f"{len(sliced_gens)} scored."
            )
        st.caption(rank_note)
        # CMP-5: a value that groups several readings draws them concatenated in
        # one panel — flag it rather than letting it pass as one scanpath. The
        # counts are computed once per rerun and reused by the panel captions.
        reading_counts = {name: _n_readings(g) for name, g in sliced_gens.items()}
        if any(k > 1 for k in reading_counts.values()):
            st.caption(
                "⚠️ A value grouping **several readings** (marked on its panel) "
                "shows them concatenated and scores them as one sequence — pick "
                "a finer comparison column (e.g. `participant_id`) to see them "
                "separately."
            )
        # Estimate a uniform cell height from the figure aspect + column count so
        # panels line up and don't leave a tall whitespace band below each.
        fig_w = float(real_fig.layout.width or 900)
        fig_h = float(real_fig.layout.height or 600)
        aspect = fig_h / fig_w if fig_w else 0.5
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
                    # CMP-5: every panel names its group value AND the trial it
                    # is (or its reading count when the value lumps several).
                    identity = _panel_identity(
                        fix, gen_col, reading_counts.get(name, 1)
                    )
                    if nld is not None and pd.notna(nld):
                        st.caption(
                            f"**{name}** · NLD {nld:.2f} · {len(fix)} fix{identity}"
                        )
                    else:
                        st.caption(f"**{name}** · {len(fix)} fix{identity}")
                    # Key on the absolute panel index (dict order is stable), so two
                    # labels differing only by spaces can't collide on the iframe key.
                    _render_true_scale_chart(
                        _make_fig(fix, panel_settings),
                        key=f"multi_gen_{start + offset}",
                        max_height=cell_h,
                    )

        st.markdown("#### Similarity to the selected scanpath")
        st.dataframe(
            _style_similarity_table(table.rename(columns={"Model": "Generation"})),
            hide_index=True,
            width="stretch",
        )

        # Cumulative NLD convergence over the full scanpaths. Memoized on the
        # selection + comparison column + set + a content fingerprint so unrelated
        # reruns don't recompute the curves.
        st.markdown("#### Metric convergence")
        st.caption(
            "NLD between the selected scanpath and each comparison scanpath, "
            "computed cumulatively over the first *k* fixations (left) and the "
            "first *t* seconds of reading (right). Lower = more similar; computed "
            "on the full reading."
        )
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
        # Convergence covers the grid subset (the shown, most-similar generations),
        # so it matches the grid and stays bounded on a high-cardinality column.
        conv_gens = {name: generations[name] for name in grid_names}
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


def _render_paginated_dataframe(
    df: pd.DataFrame,
    page_size: int,
    key: str,
    caption: Optional[str] = None,
    show_info: bool = True,
) -> None:
    """Render a dataframe with pagination and an optional caption.

    ``caption`` is skipped when falsy, and ``show_info`` suppresses the blue
    "Showing N rows with pagination" banner — the Data Inspection tab uses this
    to keep the raw tables uncluttered.

    There is deliberately no download button here: the Data Inspection tables
    are the *raw* frames, which carry passthrough columns like ``image_path``
    that hold an absolute local path. Bulk export is the supported way out, and
    it strips those at its single chokepoint (``export.strip_local_paths``).
    """
    total_rows = len(df)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    if total_rows > page_size:
        if show_info:
            st.info(
                f"Showing {total_rows:,} rows with pagination ({page_size:,} per page)."
            )
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            key=key,
            help=f"Total pages: {total_pages:,}",
        )
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_rows)
        display_df = df.iloc[start_idx:end_idx]
        st.caption(f"Showing rows {start_idx + 1:,} – {end_idx:,} of {total_rows:,}")
    else:
        display_df = df

    st.dataframe(display_df, hide_index=True, width="stretch")
    if caption:
        st.caption(caption)


def render_metrics_tab(
    words_filtered: pd.DataFrame, fixations_filtered: pd.DataFrame
) -> None:
    """Render word-level metrics tab."""
    st.subheader("Word-level data")
    metrics = compute_word_metrics(words_filtered, fixations_filtered)
    _render_paginated_dataframe(metrics, 1000, "metrics_page", show_info=False)


def render_fixations_tab(fixations_filtered: pd.DataFrame) -> None:
    """Render fixation-level data tab."""
    st.subheader("Fixation-level data")
    _render_paginated_dataframe(
        fixations_filtered, 1000, "fixations_page", show_info=False
    )


def render_raw_gaze_tab(raw_gaze_filtered: pd.DataFrame) -> None:
    """Render raw gaze data tab."""
    st.subheader("Raw gaze data")
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
    _render_paginated_dataframe(
        raw_gaze_filtered, 1000, "raw_gaze_page", show_info=False
    )


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
    st.subheader("Stimuli")
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
    _render_paginated_dataframe(stimuli, 100, "stimuli_page", show_info=False)


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
    """Render the raw data tab with sub-tabs."""
    _render_data_provenance()
    stimuli_tab, word_tab, fixation_tab, raw_gaze_tab = st.tabs(
        ["Stimuli", "Word-level", "Fixation-level", "Raw gaze"]
    )
    with stimuli_tab:
        render_stimuli_tab(words_filtered)
    with word_tab:
        render_metrics_tab(words_filtered, fixations_filtered)
    with fixation_tab:
        render_fixations_tab(fixations_filtered)
    with raw_gaze_tab:
        render_raw_gaze_tab(raw_gaze_filtered)


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


def _active_stored_dataset() -> Optional[tuple]:
    """``(name, entry)`` for the active source when it's a stored upload, else
    ``None`` — gates the editable remap form to stored datasets only."""
    name = st.session_state.get("data_source_choice")
    entry = st.session_state.get("_datasets", {}).get(name)
    return (name, entry) if entry is not None else None


def _remap_proposed(schema: Optional[dict], frame_columns, canon: dict) -> dict:
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
    st.session_state["_datasets"][name] = new_entry
    st.session_state["_remap_applied"] = name


def _render_remap_editor(name: str, stored: dict) -> None:
    """Editable column-mapping form for a stored dataset (the surviving columns).

    Renders one ``column_mapping_ui`` per present table seeded with the current
    mapping, a note listing columns dropped at import, and an Apply button. The
    widget keys are namespaced by dataset name so switching datasets never feeds
    a stale column to a selectbox (which would raise)."""
    st.subheader("Column mapping")
    st.caption(
        "Change how this dataset's columns map to the app's canonical fields. "
        "Only columns that survived the original import are available."
    )
    if st.session_state.pop("_remap_applied", None) == name:
        st.success("Mapping updated — the dataset was re-derived.")
    problems = st.session_state.get("_remap_problems") or {}
    composite = list(stored.get("composite_trial_columns") or [])
    pending: dict = {}
    for table_key, label, specs, canon in _REMAP_TABLES:
        frame = stored.get(table_key)
        if frame is None or frame.empty:
            continue
        prefix = f"remap_{name}_{table_key}"
        proposed = _remap_proposed(
            (stored.get("schemas") or {}).get(table_key), frame.columns, canon
        )
        # Composite trial id: pre-seed the multiselect with the preserved
        # component columns (column_mapping_ui's ``proposed`` carries only a
        # single default). Initial-seed only — never fight later user edits.
        if composite and all(c in frame.columns for c in composite):
            trial_key = f"{prefix}_trial"
            if trial_key not in st.session_state:
                st.session_state[trial_key] = list(composite)
        pending[table_key] = column_mapping_ui(
            frame,
            label,
            prefix,
            specs,
            proposed,
            problems=problems.get(table_key),
            use_expander=True,
            # Here `proposed` is the dataset's current saved mapping (the frame is
            # already normalized), not a fresh auto-detect — label it truthfully.
            detected_label="currently mapped",
        )
    st.session_state["_remap_pending_schemas"] = pending

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
        "Apply remapping",
        type="primary",
        key=f"remap_apply_{name}",
        on_click=_apply_remap,
        help="Re-derive this dataset's frames with the new mapping (overwrites it).",
    )


def _render_column_mapping_section() -> None:
    """Show how each source column was mapped to the app's canonical fields.

    For a stored uploaded dataset the mapping is **editable** — the user can
    remap among the columns that survived normalization (``_render_remap_editor``).
    Every other source is read-only, built from the schemas stashed by the
    data-loading paths in ``app`` under ``st.session_state['_active_column_mapping']``."""
    active = _active_stored_dataset()
    if active is not None:
        _render_remap_editor(*active)
        return
    st.subheader("Column mapping")
    mapping = st.session_state.get("_active_column_mapping") or {}
    rows = _column_mapping_rows(mapping)
    if not rows:
        st.info("No column mapping available for the current data source.")
        return
    st.dataframe(
        pd.DataFrame(rows, columns=["Table", "Field", "Mapped column"]),
        hide_index=True,
        width="stretch",
    )
    st.caption("How each source column maps to the app's canonical fields.")


def render_data_inspection_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    raw_gaze_filtered: pd.DataFrame,
) -> None:
    """Render the merged Data Inspection tab.

    Combines the former **Raw Data** and **Data Statistics** tabs: the headline
    dataset counts, every raw-data table, the per-metric summary statistics, and
    the active column mapping — in that order.
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

    # 1. Headline dataset counts.
    st.subheader("Dataset statistics")
    top_cols = st.columns(6)
    top_cols[0].metric("Participants", f"{stats['n_participants']:,}")
    top_cols[1].metric("Texts", f"{stats['n_texts']:,}")
    top_cols[2].metric("Trials", f"{stats['n_trials']:,}")
    top_cols[3].metric("Fixations", f"{stats['n_fixations']:,}")
    top_cols[4].metric("Words", f"{stats['n_words']:,}")
    top_cols[5].metric(
        "Gaze points",
        f"{stats['n_gaze']:,}" if stats["n_gaze"] else "0",
        help="Counts raw gaze samples if provided.",
    )

    st.divider()

    # 2. Every raw-data table (Stimuli / Word-level / Fixation-level / Raw gaze).
    st.subheader("Raw data")
    render_raw_data_tab(words_filtered, fixations_filtered, raw_gaze_filtered)

    st.divider()

    # PRE-11/12/15/19 + AN-30: first-class derived tables, all exportable.
    st.subheader("Derived analysis tables")
    from scanpath_studio.preprocessing import (
        character_grid,
        cleaning_report,
        saccade_table,
        sentence_measures,
    )
    from scanpath_studio.experimental_setup import pixels_per_degree
    from scanpath_studio.measures import assign_fixations_to_words, enrich_fixations

    measured_words = compute_word_metrics(words_filtered, fixations_filtered)
    analysis_fixations = (
        enrich_fixations(
            assign_fixations_to_words(fixations_filtered, words_filtered),
            words_filtered,
        )
        if not fixations_filtered.empty and not words_filtered.empty
        else fixations_filtered
    )
    try:
        ppd = pixels_per_degree(
            float(st.session_state.get("global_viewing_distance_mm", 800.0)),
            float(st.session_state.get("global_canvas_width", 1200.0)),
            float(st.session_state.get("global_monitor_width_mm", 597.0)),
        )
    except (TypeError, ValueError):
        ppd = None
    derived = {
        "Sentences": sentence_measures(measured_words, fixations_filtered),
        "Saccades": saccade_table(
            analysis_fixations,
            pixels_per_degree=ppd,
            raw_gaze=raw_gaze_filtered,
            words=words_filtered,
        ),
        "Trials": trial_summary_table(measured_words, fixations_filtered),
        "Readers": reader_summary_table(measured_words, fixations_filtered),
        "Characters": character_grid(words_filtered),
        "Cleaning QA": cleaning_report(fixations_filtered),
    }
    for tab, (label, table) in zip(st.tabs(list(derived)), derived.items()):
        with tab:
            if table.empty:
                st.caption(f"No {label.lower()} table is available for this selection.")
            else:
                _render_paginated_dataframe(
                    table,
                    1000,
                    f"derived_{label.lower().replace(' ', '_')}",
                    show_info=False,
                )

    st.divider()

    # 3. Per-metric summary statistics.
    st.subheader("Summary statistics")
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
        "Statistics computed after filtering; missing values indicate empty source data."
    )

    st.divider()

    # 4. The active column mapping (data source → canonical fields).
    _render_column_mapping_section()
