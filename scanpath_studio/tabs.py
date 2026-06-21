"""Tab rendering functions for the Scanpath Studio app."""

from __future__ import annotations

import html
import json
from typing import Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from scanpath_studio.aggregation import (
    aggregate_word_measures_by_text,
    grouped_metric_values,
    metric_by_fixation_index,
    metric_by_trial_index,
    text_read_counts,
)
from scanpath_studio.animation_export import (
    AnimationExportError,
    export_animation,
    mime_for,
)
from scanpath_studio.annotations import render_trial_annotations
from scanpath_studio.constants import (
    DEFAULT_LINE_SPACING,
    HIGHLIGHTED_TEXT_COLOR,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    WORD_LABEL_COLOR,
)
from scanpath_studio.data import (
    compute_word_metrics,
    derive_trial_index,
    frame_fingerprint,
    has_explicit_trial_index,
)
from scanpath_studio.controls import (
    SUMMARY_CHIP_FIELDS,
    render_trial_filters,
    sidebar_controls,
)
from scanpath_studio.export import (
    ExportProgress,
    bulk_export,
    render_export_options,
)
from scanpath_studio.model_scanpaths import (
    DEFAULT_N_MODELS,
    generate_model_scanpaths,
)
from scanpath_studio.plots import (
    animation_playback_ms,
    make_aggregated_histogram,
    make_comparison_figure,
    make_metric_convergence_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    make_trend_figure,
)
from scanpath_studio.similarity import (
    METRICS,
    compute_similarity_table,
    nld_by_fixation_index,
    nld_by_time,
)
from scanpath_studio.utils import (
    build_comparison_options,
    compute_trial_stats,
    extract_trial,
    friendly_trial_label,
    safe_summary,
    select_trial,
    selection_modes,
)

# -----------------------------------------------------------------------------
# Single Trial Tab
# -----------------------------------------------------------------------------


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(text))


def _embed_html_iframe(html: str, *, height: int) -> None:
    """Render an HTML string (scripts included) inside a sandboxed iframe.

    ``st.iframe`` (Streamlit >= 1.56) supersedes ``st.components.v1.html``, which
    is deprecated and scheduled for removal. We need an *iframe* — not
    ``st.html`` — because the embedded block runs ``<script>`` (Plotly from the
    CDN plus the fit/scale script), which ``st.html`` strips. Fall back to the
    old API on older Streamlit so the app still runs against the pinned baseline.
    """
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height, scrolling=False)


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
    plot_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"responsive": False, "displaylogo": False},
        div_id=f"truescale-{key}",
        # to_html defaults to auto_play=True, which auto-runs an animated figure on
        # load at Plotly's default frame duration (ignoring the configured playback
        # speed). Start paused so the animation only plays — at the right speed —
        # when the user presses Play. No effect on static (frame-less) figures.
        auto_play=False,
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
        st.warning(
            f"Could not render {fmt}: {exc}\n\n"
            "Static image export (PNG/SVG/PDF) needs a Chrome/Chromium browser "
            "for Kaleido. On Streamlit Cloud this is installed via `packages.txt`; "
            "if it still fails, choose the **HTML** format above — it needs no browser."
        )
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
        html_bytes = fig.to_html(include_plotlyjs="cdn", full_html=True).encode("utf-8")
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
        hollow_fixations=viz_settings.get("hollow_fixations", False),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        color_by_line=viz_settings.get("color_by_line", False),
        highlight_out_of_text=viz_settings.get("highlight_out_of_text", False),
        out_of_text_symbol=viz_settings.get("out_of_text_symbol", "x"),
        span_border_color=viz_settings.get("span_border_color", "#000000"),
        colorbar_orientation=viz_settings.get("colorbar_orientation", "Vertical"),
        colorbar_tickangle=viz_settings.get("colorbar_tickangle", 0),
        colorbar_tickfont_size=viz_settings.get("colorbar_tickfont_size", 12),
        background_color=viz_settings.get("background_color"),
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


@st.cache_data(show_spinner=False)
def _cached_model_scanpaths(
    _words: pd.DataFrame,
    n_models: int,
    reference_trial_id: object,
    text_id: object,
    nonce: int,
    words_fp,
) -> dict:
    """Cache the (deterministic) synthetic model scanpaths for a trial so they
    aren't regenerated on every rerun — the Generations tab renders each time the
    app reruns, including while the user is on a different tab."""
    return generate_model_scanpaths(
        _words,
        n_models=n_models,
        reference_trial_id=reference_trial_id,
        text_id=text_id,
        nonce=nonce,
    )


def _render_comparison_controls(
    combos: pd.DataFrame,
    selection_mode: str,
    selected_participant: str,
    selected_trial: str,
    selected_text: Optional[str],
    animate: bool = False,
) -> tuple[Optional[str], Optional[str], str]:
    """Render comparison toggle and trial selector, return (participant, trial, layout).

    When ``animate`` is on the layout is forced to "overlay" — an animated
    comparison co-animates both scanpaths on one clock, so side-by-side /
    stacked don't apply (TODO 1.17c) and the layout picker is hidden.

    Styled like a layer: a **toggle** plus a ⚙ **popover** for the configuration
    (the second-trial picker + the overlay/side-by-side/stacked layout).
    """
    compare_enabled = st.toggle(
        "**Compare**",
        value=False,
        key="single_compare_toggle",
        help=(
            "Co-animate a second reading on one clock."
            if animate
            else "Overlay another trial's scanpath or view them side by side."
        ),
    )

    if not compare_enabled:
        return None, None, "overlay"

    comparison_options = build_comparison_options(
        combos, selection_mode, selected_participant, selected_trial, selected_text
    )

    if not comparison_options:
        st.info("No other trials available for comparison.")
        return None, None, "overlay"

    option_labels = [opt[2] for opt in comparison_options]
    label_to_trial = {opt[2]: (opt[0], opt[1]) for opt in comparison_options}

    layout = "overlay"
    with st.popover("⚙️ Compare options", width="stretch"):
        selected_compare_label = st.selectbox(
            "Compare with trial",
            options=option_labels,
            key="single_compare_trial",
            help="★ indicates same text as primary trial."
            + (" Animated comparison overlays both on one clock." if animate else ""),
        )
        if not animate:
            layout_label = (
                st.segmented_control(
                    "View",
                    options=["Overlay", "Side by side", "Stacked"],
                    key="single_compare_layout",
                    help="Stacked = trials shown one above the other.",
                )
                or "Overlay"
            )
            layout = {
                "Overlay": "overlay",
                "Side by side": "side_by_side",
                "Stacked": "stacked",
            }.get(layout_label, "overlay")

    if selected_compare_label:
        participant, trial = label_to_trial[selected_compare_label]
        return participant, trial, layout
    return None, None, layout


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
    ``is_correct``) is a legitimate trial-level field and is kept.
    """
    out = []
    for c in trial_words.columns:
        lc = c.lower()
        if not any(h in lc for h in _QA_NAME_HINTS) or _is_boolish_span(c):
            continue
        col = trial_words[c]
        if _is_boolish(col) and col.dropna().nunique() > 1:
            continue  # per-word-varying boolean → not a trial-level Q&A field
        out.append(c)
    return out


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

        # Breathing room between the stimulus text and the question/answer block.
        if qa_cols:
            st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

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
                    bits.append("✓ correct" if correct else "✗ incorrect")
                st.markdown("**Answer:** " + " · ".join(bits))
            rendered.update({"selected_answer", "is_correct"})

        # Any remaining detected answer/correct columns, rendered generically.
        for col in qa_cols:
            if col in rendered:
                continue
            bval = _first_bool(trial_words, col) if "correct" in col.lower() else None
            if bval is not None:
                st.markdown(
                    f"**{_humanize_field(col)}:** " + ("✓ yes" if bval else "✗ no")
                )
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
                f'<span style="background-color:{span_bg[col]};'
                f'color:{_HIGHLIGHT_TEXT_COLOR};padding:0 4px;border-radius:2px;">'
                f"<b>{_humanize_field(col)}:</b></span> {span_str}{note}",
                unsafe_allow_html=True,
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
) -> dict:
    """Build the "💾 Save & restore" JSON config dict (pure — no Streamlit).

    Schema 2 captures the full figure configuration (layers, colouring, sizing,
    text/highlighting, canvas, axes, trial selection), every per-trial
    annotation, and provenance (app version, export date, data source, column
    mapping)."""
    return {
        # schema 2 = config + annotations + text/highlighting + provenance;
        # schema 1 (plot config only) still restores via the same reader.
        "schema": 2,
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
        },
        "coloring": {
            "color_by": figure_settings["color_by"],
            "heatmap_metric": viz_settings["heatmap_metric"],
            "heatmap_style": figure_settings.get("heatmap_style", "Word boxes"),
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
            "hollow_fixations": bool(viz_settings.get("hollow_fixations", False)),
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
        },
        "highlighting": {
            "critical_span_style": figure_settings.get(
                "critical_span_style", "Mark text"
            ),
            "highlight_column": figure_settings.get("highlight_column", "is_in_aspan"),
            "highlight_out_of_text": bool(
                figure_settings.get("highlight_out_of_text", False)
            ),
            "highlight_text_color": figure_settings.get(
                "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
            ),
            "background_color": figure_settings.get("background_color"),
        },
        "raw_gaze": {
            "available": not trial_raw_gaze.empty,
            "points": len(trial_raw_gaze) if not trial_raw_gaze.empty else 0,
        },
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
    """Render the "💾 Save & restore" sidebar panel (TODO 1.19).

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
    # Provenance (TODO 4.1): which data source + how its columns were mapped +
    # the app version + when it was exported, so a saved config records the full
    # context behind the figure, not just the plot settings.
    column_mapping = _collect_column_mapping()
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
            # trial (TODO 4.2).
            file_name="scanpath_studio_config.json",
            mime="application/json",
            key="plot_config_download",
            width="stretch",
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
) -> float:
    """Render the animation reading-time / playback info box (+ overlay caveats),
    shown in the side panel under the Animate toggle (TODO 3.1). Returns the
    playback duration in ms. No fixation count (TODO 1.17e)."""
    dual = fixations_b is not None and not fixations_b.empty
    reading_span_ms, playback_ms = animation_playback_ms(
        [trial_fixations] + ([fixations_b] if dual else []), playback_speed
    )
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
    return playback_ms


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
):
    """Build + render the animation figure (single or dual co-animation) in the
    main column. Returns ``(fig, playback_ms, save_slug, file_stem)``."""
    dual = fixations_b is not None and not fixations_b.empty
    _reading_span_ms, playback_ms = animation_playback_ms(
        [trial_fixations] + ([fixations_b] if dual else []), playback_speed
    )
    # The reading-time / playback info box renders in the side panel under the
    # Animate toggle (see _render_anim_info_box / TODO 3.1), not here.
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
        show_order=viz_settings["show_order"],
        marker_size_range=viz_settings["marker_size_range"],
        order_font_size=viz_settings["order_font_size"],
        order_font_color=viz_settings["order_font_color"],
        color_by=viz_settings["color_by"],
        color_by_line=viz_settings.get("color_by_line", False),
        fixation_colorscale=viz_settings["fixation_colorscale"],
        fixation_color_range=viz_settings["fixation_color_range"],
        show_colorbars=viz_settings["show_colorbars"],
        saccade_color=viz_settings.get("saccade_color", SACCADE_COLOR),
        saccade_style=SACCADE_DASH_OPTIONS.get(
            viz_settings.get("saccade_style", "Solid"), "solid"
        ),
        hollow_fixations=viz_settings.get("hollow_fixations", False),
        background_color=viz_settings.get("background_color"),
        fixations_b=fixations_b if dual else None,
        words_b=words_b if dual else None,
        label_a=(
            f"{selected_participant} · {selected_trial}" if dual else "Scanpath A"
        ),
        label_b=(f"{compare_participant} · {compare_trial}" if dual else "Scanpath B"),
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
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
    st.markdown("#### This trial")
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
    st.markdown("#### Multiple trials")
    bulk_settings = _build_figure_settings(viz_settings, False)
    bulk_settings["line_spacing"] = line_spacing
    bulk_settings["scale_text_to_boxes"] = scale_text_to_boxes
    _render_bulk_export(
        combos,
        words_filtered,
        fixations_filtered,
        combos_all,
        words_all,
        fixations_all,
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
    """Background for a chip — known conditions keep their metadata-table colour
    (so a condition reads the same everywhere), everything else is neutral."""
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
) -> None:
    """Render a compact, glanceable strip of ``Field = Value`` chips above the
    plot — the trial's identity, experiment conditions, and summary stats, so the
    key "what am I looking at" facts are visible at a glance (these chips replaced
    the Trial Info subtab).

    ``fields`` is the configurable list of fields to surface (sidebar
    ``trial_chip_fields``). The whole strip — identity/condition chips, a ``?``
    help marker, and an inline **More** disclosure — stays on **one line**; the
    computed summary stats live inside **More** (only fields not already shown), so
    the plot stays tall. A data column that varies within the trial is shown (first
    value) but flagged with ⚠️. Skips silently when nothing resolves."""
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
            summary.append((f"{label} = {value}", _CHIP_NEUTRAL_BG))
            continue
        value, trial_level = _chip_value_and_uniqueness(
            col, trial_words, trial_fixations, participant
        )
        if value is None:
            continue
        value_str = str(value)
        if not value_str:
            continue
        label = _chip_field_label(col)
        prefix = "" if trial_level else "⚠️ "
        primary.append((f"{prefix}{label} = {value_str}", _chip_color(col, value_str)))
    if not primary and not summary:
        return

    def _spans(items: list[tuple[str, str]]) -> str:
        return "".join(
            f'<span class="sps-chip" style="background:{bg};">{html.escape(lbl)}</span>'
            for lbl, bg in items
        )

    # A "?" marker pointing to the sidebar picker (native HTML title tooltip).
    help_span = (
        '<span class="sps-chip-help" title="Change which fields show here in the '
        'sidebar → 🏷️ Trial chips">?</span>'
    )
    # The summary stats sit inside an inline <details> "More" — only fields not
    # already shown inline — so the whole strip stays one line until expanded.
    more_html = ""
    if summary:
        more_html = (
            '<details class="sps-chip-more">'
            '<summary class="sps-chip sps-chip-more-summary">More</summary>'
            f'<div class="sps-trial-chips sps-chip-more-body">{_spans(summary)}</div>'
            "</details>"
        )
    st.markdown(
        f'<div class="sps-trial-chips">{_spans(primary)}{help_span}{more_html}</div>',
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
       Export (Export folds in the former Bulk Export tab — see
       ``_render_export_panel``). The former Trial Info subtab was folded into the
       configurable chips above the plot. Save & restore lives in the sidebar.

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

    modes = selection_modes(combos)
    multi_mode = len(modes) > 1
    with plot_col:
        # One selection line: [Browse by] [pills] [trial selectbox(s)] [Filter] —
        # the pills (mode_host) and selectbox(s) (picker_host) are filled by
        # select_trial; the scrubbing slider lands on the line below. Filter is a
        # content-width popover overlay (no plot shove). Vertically centered so the
        # label, pills, selectbox and button line up.
        if multi_mode:
            label_col, mode_host, picker_host, filter_col = st.columns(
                [1, 2.3, 3, 1.4], vertical_alignment="center"
            )
            label_col.markdown("**Browse by**")
        else:
            picker_host, filter_col = st.columns([3, 1.4], vertical_alignment="center")
            mode_host = None
        with filter_col:
            filt_pop = st.popover("🔍 Filter trials", width="content")
            filt_pop.caption("Narrow the trial pool shown in every view.")
            render_trial_filters(words_all, fixations_all, host=filt_pop)
        selected_participant, selected_trial, selection_mode, selected_text = (
            select_trial(
                combos,
                key_prefix="single",
                mode_host=mode_host,
                picker_host=picker_host,
            )
        )
        # Slots filled once the selection is resolved (chips need the trial).
        chips_slot = st.container()
        plot_slot = st.container()

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

    # Condition chips above the plot are filled later (into chips_slot), once the
    # comparison selection is known — so a second chip strip can show the compared
    # trial too.

    # Render the rail (view modes + viz controls) before the figure so it sees the
    # resolved Animate / Compare / viz settings; its right-side position is fixed
    # by the column split regardless of render order.
    with rail:
        st.markdown("##### 🎬 View modes")
        # Animate styled like a layer: a toggle + a ⚙ popover for its config
        # (playback speed) — matching Compare and the visualization layers below.
        animate = st.toggle(
            "**Animate**",
            value=False,
            key="single_animate",
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
                )
                anim_info_slot = st.container()
        compare_participant, compare_trial, compare_layout = (
            _render_comparison_controls(
                combos,
                selection_mode,
                selected_participant,
                selected_trial,
                selected_text,
                animate=animate,
            )
        )
        st.divider()
        st.markdown("##### 🎨 Visualization")
        # The visualization controls moved out of the sidebar into this rail
        # (host=rail) so they sit beside the plot with the sidebar closed.
        viz_settings = sidebar_controls(
            fixations_filtered,
            base_font_size,
            host=rail,
            has_raw_gaze=has_raw_gaze,
            words=words_filtered,
        )

    global_raw_toggle = bool(viz_settings.get("show_raw_gaze"))
    effective_show_raw_gaze = bool(global_raw_toggle and trial_has_raw_gaze)
    figure_settings = _build_figure_settings(viz_settings, effective_show_raw_gaze)
    figure_settings["raw_gaze"] = trial_raw_gaze if trial_has_raw_gaze else None
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

    # Condition chips above the plot — configurable via the sidebar picker
    # (`trial_chip_fields`); `Field = Value` for the chosen fields. When comparing,
    # a second labelled strip shows the compared trial too.
    chip_fields = st.session_state.get("trial_chip_fields") or []
    with chips_slot:
        if comparing and compare_meta:
            st.caption(f"**{compare_meta['label_primary']}**")
        _render_trial_condition_chips(
            trial_words, trial_fixations, selected_participant, chip_fields
        )
        if comparing and compare_meta:
            st.caption(f"**{compare_meta['label_compare']}** (compared)")
            _render_trial_condition_chips(
                compare_meta["words"],
                compare_meta["fixations"],
                compare_participant,
                chip_fields,
            )

    displayed_fig = None
    save_slug = f"{selected_participant}__{selected_trial}"
    anim_playback_ms = None
    anim_file_stem = None
    dual_anim = animate and comparing and not compare_fix.empty

    # Animation info box, in its slot inside the rail's Playback popover.
    if animate and not trial_fixations.empty and anim_info_slot is not None:
        with anim_info_slot:
            _render_anim_info_box(
                trial_words,
                trial_fixations,
                compare_meta["words"] if dual_anim else None,
                compare_fix if dual_anim else None,
                selected_participant,
                selected_trial,
                compare_participant,
                compare_trial,
                playback_speed,
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
                        trial_fixations,
                        compare_meta["words"] if dual_anim else None,
                        compare_fix if dual_anim else None,
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
                fixations_filtered,
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
            )
            save_slug = (
                f"{selected_participant}__{selected_trial}__vs__"
                f"{compare_participant}__{compare_trial}"
            )
        else:
            build_kwargs = dict(
                canvas_width=int(canvas_width),
                canvas_height=int(canvas_height),
                base_font_size=int(base_font_size),
                font_family=font_family,
                x_field=x_field,
                y_field=y_field,
                **figure_settings,
            )
            displayed_fig = _cached_scanpath_figure(
                trial_words,
                trial_fixations,
                build_kwargs,
                fig_key=_figure_input_key(trial_words, trial_fixations, build_kwargs),
            )
            _render_true_scale_chart(displayed_fig, key="single")

    # Per-trial panels sit BELOW the plot as a single full-width subtab bar (they
    # must be created outside the columns to span the page width). Trial Info is
    # gone — the chip strip above the plot now carries the trial's identity,
    # conditions and summary stats (configurable via the sidebar 🏷️ Trial chips).
    tab_annot, tab_stim, tab_export = st.tabs(
        ["📝 Annotations", "Stimulus & questions", "Export"]
    )
    with tab_annot:
        render_trial_annotations(selected_participant, selected_trial, bare=True)
    with tab_stim:
        _render_paragraph_panel(trial_words, trial_fixations=trial_fixations, bare=True)
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
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            viz_settings=viz_settings,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
        )

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
        st, combos, key_prefix="bulk_export", combos_all=combos_all
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
            file_name=f"scanpath_export_{pd.Timestamp.utcnow():%Y%m%d_%H%M%S}.zip",
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
):
    """Render comparison figure for two trials."""
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"

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
        show_saccades=viz_settings.get("show_saccades", True),
        show_saccade_arrows=viz_settings.get("show_saccade_arrows", False),
        show_order=viz_settings.get("show_order", False),
        order_font_size=viz_settings.get("order_font_size"),
        text_color=viz_settings.get("text_color", WORD_LABEL_COLOR),
        highlight_text_color=viz_settings.get(
            "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
        ),
        background_color=viz_settings.get("background_color"),
        line_spacing=line_spacing,
        scale_text_to_boxes=scale_text_to_boxes,
    )
    _render_true_scale_chart(fig_compare, key="compare")
    return fig_compare


# -----------------------------------------------------------------------------
# Corpus Analysis Tab  (parent of Generations + Aggregated Views)
# -----------------------------------------------------------------------------

# Aggregated-views metric registry: label → (frame, column, supports_fixation_trend).
# ``frame`` is "fixations" (per-fixation) or "words" (per-word reading measure).
_AGG_METRICS = {
    "Fixation duration (ms)": ("fixations", "duration_ms", True),
    "Saccade amplitude (px)": ("fixations", "saccade_amplitude", True),
    "First fixation duration — FFD (ms)": ("words", "first_fixation_ms", False),
    "First-pass gaze — FPRT (ms)": ("words", "first_pass_gaze_duration_ms", False),
    "Regression-path — RPD (ms)": ("words", "regression_path_duration_ms", False),
    "Total fixation duration — TFD (ms)": (
        "words",
        "total_fixation_duration_ms",
        False,
    ),
    "Fixations per word": ("words", "n_fixations", False),
}


def _text_column(frame: pd.DataFrame) -> Optional[str]:
    """Canonical text/passage id column, if any."""
    for col in ("unique_text_id", "text_id", "unique_paragraph_id", "paragraph_id"):
        if col in frame.columns:
            return col
    return None


@st.cache_data(show_spinner=False)
def _agg_with_trial_index(_frame: pd.DataFrame, metric: str, fkey) -> pd.DataFrame:
    """Per-trial-index trend, cached on a frame fingerprint (``fkey``)."""
    f = _frame.copy()
    f["trial_index"] = derive_trial_index(f)
    return metric_by_trial_index(f, metric)


@st.cache_data(show_spinner=False)
def _agg_by_fixation_index(_fixations: pd.DataFrame, metric: str, fkey) -> pd.DataFrame:
    return metric_by_fixation_index(_fixations, metric)


@st.cache_data(show_spinner=False)
def _agg_word_heatmap(
    _words: pd.DataFrame, text_col: str, text_id, fkey
) -> pd.DataFrame:
    return aggregate_word_measures_by_text(_words, text_col, text_id)


def render_corpus_analysis_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    combos: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """Corpus Analysis tab — corpus-level views beyond a single trial.

    Two subtabs: **Generations (WIP)** (the real-vs-model scanpath comparison)
    and **Aggregated Views** (trial-index / fixation-index trends, per-text
    heatmaps, and grouped metric distributions across many trials).
    """
    gen_tab, agg_tab = st.tabs(["Generations (WIP)", "Aggregated Views"])
    with gen_tab:
        render_multiple_comparison_tab(
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
    with agg_tab:
        render_aggregated_views_tab(
            words_filtered,
            fixations_filtered,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
        )


def render_aggregated_views_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """Aggregated views over the (filtered) corpus: trends, per-text heatmaps,
    and grouped metric distributions."""
    st.caption(
        "Corpus-level summaries across the **filtered** trials — narrow the "
        "sidebar *Filter trials* panel to scope these. Trends average a metric "
        "over the session's trial order and the within-trial fixation index; the "
        "heatmap pools a text's readers; the histogram pools a metric by group."
    )
    if fixations_filtered.empty and words_filtered.empty:
        st.info("No data after filtering.")
        return

    # Metric picker — only metrics whose column is actually present.
    def _metric_available(spec) -> bool:
        frame_name, col, _ = spec
        frame = fixations_filtered if frame_name == "fixations" else words_filtered
        return col in frame.columns

    metric_options = [m for m, spec in _AGG_METRICS.items() if _metric_available(spec)]
    if not metric_options:
        st.info("No aggregatable metrics found in this dataset.")
        return
    metric_label = st.selectbox(
        "Metric",
        options=metric_options,
        key="agg_metric",
        help="Eye-movement measure to summarise across trials.",
    )
    frame_name, metric_col, supports_fix_trend = _AGG_METRICS[metric_label]
    metric_frame = fixations_filtered if frame_name == "fixations" else words_filtered

    # --- Trial-index + within-trial fixation-index trends --------------------
    st.markdown("#### Trends")
    if not has_explicit_trial_index(metric_frame):
        st.caption(
            "ℹ️ No `trial_index` column in the data — trial order is derived from "
            "each participant's fixation timestamps."
        )
    trial_df = _agg_with_trial_index(
        metric_frame, metric_col, frame_fingerprint(metric_frame)
    )
    cols = st.columns(2) if supports_fix_trend else [st.container()]
    with cols[0]:
        fig_trial = make_trend_figure(
            trial_df,
            x_col="trial_index",
            y_label=metric_label,
            title=f"Average {metric_label} by trial index",
            canvas_width=int(canvas_width * 0.46)
            if supports_fix_trend
            else canvas_width,
            base_font_size=base_font_size,
            font_family=font_family,
        )
        st.plotly_chart(fig_trial, width="stretch")
    if supports_fix_trend:
        fix_df = _agg_by_fixation_index(
            fixations_filtered, metric_col, frame_fingerprint(fixations_filtered)
        )
        with cols[1]:
            fig_fix = make_trend_figure(
                fix_df,
                x_col="fixation_index",
                y_label=metric_label,
                title=f"Average {metric_label} by fixation index",
                canvas_width=int(canvas_width * 0.46),
                base_font_size=base_font_size,
                font_family=font_family,
            )
            st.plotly_chart(fig_fix, width="stretch")

    # --- Per-text aggregated heatmap -----------------------------------------
    text_col = _text_column(words_filtered)
    if text_col is not None and "word_id" in words_filtered.columns:
        st.markdown("#### Per-text heatmap")
        counts = text_read_counts(words_filtered, text_col)
        if not counts.empty:
            labels = {
                f"{row.text}  ({row.n_participants} readers)": row.text
                for row in counts.itertuples()
            }
            chosen = st.selectbox(
                "Text",
                options=list(labels),
                key="agg_heatmap_text",
                help="Aggregate a word-level measure over everyone who read this text.",
            )
            weight = st.radio(
                "Heatmap weight",
                options=["Total fixation duration", "Fixation count"],
                horizontal=True,
                key="agg_heatmap_weight",
            )
            agg_words = _agg_word_heatmap(
                words_filtered,
                text_col,
                labels[chosen],
                frame_fingerprint(words_filtered),
            )
            heatmap_metric = (
                "duration_ms" if weight == "Total fixation duration" else None
            )
            measure_col = (
                "total_fixation_duration_ms"
                if heatmap_metric == "duration_ms"
                else "n_fixations"
            )
            if not agg_words.empty and measure_col in agg_words.columns:
                fig_heat = make_scanpath_figure(
                    agg_words,
                    pd.DataFrame(),
                    canvas_width=int(canvas_width),
                    canvas_height=int(canvas_height),
                    base_font_size=int(base_font_size),
                    font_family=font_family,
                    x_field="x",
                    y_field="y",
                    show_words=True,
                    show_word_labels=True,
                    show_fixations=False,
                    show_order=False,
                    show_saccades=False,
                    show_heatmap=True,
                    # No fixations here (words-only heatmap), so color_by is never
                    # read; point it at a real column anyway for defensiveness.
                    color_by=measure_col,
                    heatmap_metric=heatmap_metric,
                    heatmap_style="Word boxes",
                    marker_size_range=(8, 24),
                    order_font_size=10,
                    order_font_color="#111111",
                    show_colorbars=True,
                    fixation_color_range=None,
                    heatmap_range=None,
                    line_spacing=line_spacing,
                    scale_text_to_boxes=scale_text_to_boxes,
                )
                _render_true_scale_chart(fig_heat, key="agg_heatmap")
            else:
                st.info(
                    "This text has no aggregatable word-level measures "
                    "(needs total fixation duration / fixation counts per word)."
                )

    # --- Grouped metric distribution -----------------------------------------
    st.markdown("#### Distribution")
    group_specs = {"All data": None}
    if text_col is not None:
        group_specs["By text"] = text_col
    if "participant_id" in metric_frame.columns:
        group_specs["By participant"] = "participant_id"
    for field in ("question_preview", "repeated_reading_trial", "difficulty_level"):
        if field in metric_frame.columns:
            group_specs[f"By {field}"] = field
    grouping = st.selectbox(
        "Group by",
        options=list(group_specs),
        key="agg_hist_group",
        help="Split the distribution into one histogram per group.",
    )
    group_col = group_specs[grouping]
    groups, dropped = grouped_metric_values(metric_frame, metric_col, group_col)
    if dropped:
        st.caption(f"Showing the 12 largest groups; {dropped} smaller group(s) hidden.")
    fig_hist = make_aggregated_histogram(
        groups,
        metric_label=metric_label,
        canvas_width=canvas_width,
        base_font_size=base_font_size,
        font_family=font_family,
    )
    st.plotly_chart(fig_hist, width="stretch")


# -----------------------------------------------------------------------------
# Generations (WIP) Tab  (formerly "Multiple Comparison")
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


def render_multiple_comparison_tab(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    combos: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    viz_settings: dict,
    line_spacing: float = DEFAULT_LINE_SPACING,
    scale_text_to_boxes: bool = True,
) -> None:
    """Render the Generations (WIP) tab.

    Shows the real scanpath for the selected trial on top, then a configurable
    grid of model-generated scanpaths over the SAME text, and a similarity
    table scoring each model against the real reading (NLD plus placeholder
    metrics). The model scanpaths are synthetic placeholders until real model
    outputs are connected — see :mod:`scanpath_studio.model_scanpaths`. Work in
    progress.
    """
    st.caption(
        "Compare a real scanpath with several **model-generated** scanpaths over "
        "the same text, and score how close each model is to the real reading. "
        "⚠️ The model scanpaths are **synthetic placeholders** (reproducible, "
        "reading-like random paths) until real model outputs are connected."
    )

    col_side, col_main = st.columns([3, 7], gap="medium")

    with col_side:
        selected_participant, selected_trial, _mode, _text = select_trial(
            combos, key_prefix="multi"
        )
    if not (selected_participant and selected_trial):
        return

    trial_words = extract_trial(words_filtered, selected_participant, selected_trial)
    trial_fixations = extract_trial(
        fixations_filtered, selected_participant, selected_trial
    )
    if trial_words.empty or trial_fixations.empty:
        with col_main:
            st.info(
                "Generations needs a **words + fixations** table for the "
                "selected trial — it scores model scanpaths against the real "
                "reading over the text."
            )
        return

    with col_side:
        # The number of models is inferred from the model-scanpath data. Until
        # real model outputs are connected we generate a fixed set of example
        # scanpaths behind the scenes — so there's no user control for it.
        n_models = DEFAULT_N_MODELS
        n_cols = st.slider(
            "Grid columns",
            min_value=1,
            max_value=4,
            value=3,
            key="multi_n_cols",
            help="Columns in the model grid (rows fill automatically).",
        )
        if st.button(
            "🎲 Regenerate",
            key="multi_regen",
            help="Re-draw the synthetic model scanpaths with a fresh random seed.",
        ):
            st.session_state["multi_nonce"] = (
                int(st.session_state.get("multi_nonce", 0)) + 1
            )
        nonce = int(st.session_state.get("multi_nonce", 0))

        text_id = _trial_text_id(trial_words)
        models = _cached_model_scanpaths(
            trial_words,
            n_models,
            selected_trial,
            text_id,
            nonce,
            words_fp=frame_fingerprint(trial_words),
        )

        # Fixation-index window: restrict which fixations are drawn (and scored
        # in the snapshot table) for the real scanpath and every model.
        max_fix = max([len(trial_fixations)] + [len(m) for m in models.values()])
        if max_fix >= 2:
            # The slider value persists across trial / model-count changes, which
            # shift max_fix. Seed/clamp it via session_state *only* (no value=
            # arg), so the stored value is always inside [1, max_fix] — passing
            # both a value= and a session-state value raises a Streamlit warning,
            # and an out-of-range stored value would otherwise raise outright.
            stored = st.session_state.get("multi_fix_range")
            if isinstance(stored, (tuple, list)) and len(stored) == 2:
                lo = max(1, min(int(stored[0]), int(max_fix)))
                hi = max(lo, min(int(stored[1]), int(max_fix)))
                st.session_state["multi_fix_range"] = (lo, hi)
            else:
                st.session_state["multi_fix_range"] = (1, int(max_fix))
            fix_start, fix_end = st.slider(
                "Fixation index range",
                min_value=1,
                max_value=int(max_fix),
                key="multi_fix_range",
                help="Plot (and score, in the table) only fixations whose index "
                "falls in this range — applied to the real scanpath and every "
                "model. The convergence plots below always span the full reading.",
            )
        else:
            fix_start, fix_end = 1, int(max_fix)

        _render_trial_header(
            selected_participant,
            selected_trial,
            trial_words,
            prefix="Real scanpath:",
        )
        _render_paragraph_panel(
            trial_words, trial_fixations=trial_fixations, expanded=False
        )

    def _slice_range(fix: pd.DataFrame) -> pd.DataFrame:
        """Keep only fixations whose 1-based order index is in [start, end]."""
        if "order_in_trial" in fix.columns and not fix.empty:
            return fix[
                (fix["order_in_trial"] >= fix_start)
                & (fix["order_in_trial"] <= fix_end)
            ]
        return fix

    # Reuse the user's viz toggles, but force a clean comparison view (no
    # heatmap / raw gaze). The small model panels additionally drop word labels
    # and order numbers, which are illegible at grid scale.
    #
    # Normalize to a clean, comparable spatial view regardless of the sidebar
    # choices. The grid is an inherently spatial scanpath view, and the synthetic
    # model frames only carry the canonical fixation columns with *synthetic*
    # participant ids — so any option that (a) reads a real-only column or (b)
    # routes through a (participant_id, trial_id) groupby against the real
    # trial_words would either KeyError or silently mis-render the model panels:
    #   - x/y axes + color_by: a real-only column (saccade_amplitude, surprisal…)
    #     KeyErrors / falls back to a flat colour → pin axes to x/y, colour by
    #     duration_ms (present in every frame);
    #   - color_by_line / highlight_out_of_text: call measures helpers that group
    #     by (participant_id, trial_id); the model frames' "Model N" id never
    #     matches trial_words, so every model fixation would land off-line /
    #     out-of-text → pin both off.
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
        "highlight_out_of_text": False,
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

    # Sliced (windowed) frames feed the spatial figures and the snapshot table;
    # the convergence plots below use the FULL scanpaths.
    sliced_real = _slice_range(trial_fixations)
    sliced_models = {name: _slice_range(m) for name, m in models.items()}
    windowed = fix_start > 1 or fix_end < max_fix

    with col_main:
        st.markdown("#### Real scanpath")
        if windowed:
            st.caption(
                f"Showing fixations **{fix_start}–{fix_end}** of up to {max_fix}."
            )
        real_fig = _make_fig(sliced_real, real_settings)
        _render_true_scale_chart(real_fig, key="multi_real")

        # Compute the similarity table once up front: the per-model NLD annotates
        # each grid panel below, and the full table is shown beneath the grid.
        table = compute_similarity_table(sliced_real, sliced_models, trial_words)
        nld_by_model = (
            dict(zip(table["Model"], table["NLD"])) if "NLD" in table.columns else {}
        )

        st.markdown("#### Model-generated scanpaths")
        # Estimate a uniform cell height from the figure aspect + column count
        # so panels line up and don't leave a tall whitespace band below each.
        fig_w = float(real_fig.layout.width or 900)
        fig_h = float(real_fig.layout.height or 600)
        aspect = fig_h / fig_w if fig_w else 0.5
        assumed_col_px = max(200, int(780 / max(1, n_cols)))
        cell_h = max(150, int(assumed_col_px * aspect) + 16)

        names = list(models.keys())
        for start in range(0, len(names), n_cols):
            row_names = names[start : start + n_cols]
            grid_cols = st.columns(n_cols)
            for cell, name in zip(grid_cols, row_names):
                with cell:
                    fix = sliced_models[name]
                    nld = nld_by_model.get(name)
                    if nld is not None and pd.notna(nld):
                        st.caption(f"**{name}** · NLD {nld:.2f} · {len(fix)} fix")
                    else:
                        st.caption(f"**{name}** · {len(fix)} fix")
                    _render_true_scale_chart(
                        _make_fig(fix, panel_settings),
                        key=f"multi_model_{name.replace(' ', '_')}",
                        max_height=cell_h,
                    )

        st.markdown("#### Similarity to the real scanpath")
        st.dataframe(_style_similarity_table(table), hide_index=True, width="stretch")

        # Cumulative metric convergence over the full scanpaths. Memoized so
        # dragging the fixation slider — which does NOT change these curves —
        # doesn't recompute the per-prefix NLDs. The key includes a fingerprint
        # of the real fixation content (not just the participant/trial id
        # strings), so a different dataset that happens to reuse the same ids
        # (e.g. two uploads both labelled participant "1") can't serve stale
        # curves.
        st.markdown("#### Metric convergence")
        st.caption(
            "NLD between the real scanpath and each model, computed cumulatively "
            "over the first *k* fixations (left) and the first *t* seconds of "
            "reading (right). Lower = more similar; computed on the full reading "
            "regardless of the fixation-range slider."
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
        conv_key = (
            str(selected_participant),
            str(selected_trial),
            int(nonce),
            int(n_models),
            fix_fingerprint,
        )
        if st.session_state.get("_multi_conv_key") != conv_key:
            st.session_state["_multi_conv_key"] = conv_key
            st.session_state["_multi_conv_fix"] = {
                name: nld_by_fixation_index(trial_fixations, m, trial_words)
                for name, m in models.items()
            }
            st.session_state["_multi_conv_time"] = {
                name: nld_by_time(trial_fixations, m, trial_words)
                for name, m in models.items()
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
                highlight_x_range=(fix_start, fix_end) if windowed else None,
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
    download_name: Optional[str] = None,
    show_info: bool = True,
) -> None:
    """Render a dataframe with pagination, optional caption + download buttons.

    ``caption`` and ``download_name`` are skipped when falsy, and ``show_info``
    suppresses the blue "Showing N rows with pagination" banner — the Data
    Inspection tab uses this to keep the raw tables uncluttered.
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

    if download_name and not df.empty:
        _render_download_buttons(df, key, download_name)


# Above this many rows, serializing the *whole* frame for the download buttons
# on every rerun (st.download_button evaluates its ``data`` eagerly) is a top
# cost on large corpora — a multi-million-row CSV/Parquet rebuilt each render.
# Past the threshold we defer it behind an explicit button instead.
_EAGER_DOWNLOAD_MAX_ROWS = 50_000


@st.cache_data(show_spinner="Preparing download…")
def _frame_to_csv_bytes(_df: pd.DataFrame, cache_key) -> bytes:
    return _df.to_csv(index=False).encode("utf-8")


@st.cache_data(show_spinner="Preparing download…")
def _frame_to_parquet_bytes(_df: pd.DataFrame, cache_key) -> Optional[bytes]:
    import io as _io

    buf = _io.BytesIO()
    try:
        _df.to_parquet(buf, index=False)
        return buf.getvalue()
    except Exception:
        return None


def _render_download_buttons(df: pd.DataFrame, key: str, download_name: str) -> None:
    """CSV/Parquet download buttons whose serialization is cached and (for large
    frames) deferred behind a button, so it isn't rebuilt on every rerun."""
    fp = frame_fingerprint(df)
    prepared_key = f"{key}_download_ready"
    if len(df) > _EAGER_DOWNLOAD_MAX_ROWS and not st.session_state.get(prepared_key):
        st.button(
            f"Prepare downloads ({len(df):,} rows)",
            key=f"{key}_prepare_download",
            help="Serialize the full table to CSV/Parquet for download.",
            on_click=lambda: st.session_state.__setitem__(prepared_key, True),
        )
        st.caption(
            "Large table — downloads are prepared on demand to keep the app responsive."
        )
        return

    col_csv, col_parquet, _ = st.columns([1, 1, 4])
    with col_csv:
        st.download_button(
            "Download CSV",
            data=_frame_to_csv_bytes(df, cache_key=fp),
            file_name=f"{download_name}.csv",
            mime="text/csv",
            key=f"{key}_csv_download",
        )
    with col_parquet:
        parquet_bytes = _frame_to_parquet_bytes(df, cache_key=fp)
        if parquet_bytes is not None:
            st.download_button(
                "Download Parquet",
                data=parquet_bytes,
                file_name=f"{download_name}.parquet",
                mime="application/octet-stream",
                key=f"{key}_parquet_download",
            )


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


def _render_column_mapping_section() -> None:
    """Show how each source column was mapped to the app's canonical fields.

    Reads the schemas stashed by the data-loading paths in ``app`` under
    ``st.session_state['_active_column_mapping']``."""
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
