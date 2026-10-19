"""The settings-file serializer shared by Share and export bundles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields

import pandas as pd

from .constants import (
    DEFAULT_CROP_MARGIN_PX,
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_HEATMAP_SIGMA_PX,
    DEFAULT_LINE_SPACING,
    DEFAULT_MARKER_DURATION_RANGE,
    DEFAULT_MARKER_SIZE_SCALE,
    DEFAULT_PALETTE,
    DEFAULT_SACCADE_WIDTH,
    DEFAULT_SNAP_POSITION,
    HIGHLIGHTED_TEXT_COLOR,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    WORD_BOX_COLOR,
    WORD_BOX_FILL_COLOR,
    WORD_BOX_FILL_OPACITY,
    WORD_BOX_LINE_OPACITY,
    WORD_LABEL_COLOR,
    drift_correction_enabled,
)
from .plots import COLORBAR_DEFAULTS, FigureSettings, normalize_legend_layout
from .session_keys import (
    DESIGN_COLOR_PARAMS,
    DESIGN_FLOAT_PARAMS,
    DESIGN_INT_PARAMS,
    DESIGN_TOGGLE_PARAMS,
    SINGLE_ANIMATE,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
    SINGLE_PLAYBACK_SPEED,
)


def build_plot_config(
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
    state: Mapping,
    setup_provenance: dict | None = None,
    print_size: dict | None = None,
    raw_gaze_synthesized: bool = False,
) -> dict:
    """Build the 🔗 Share → **File** settings JSON (pure — no Streamlit).

    The full figure configuration (layers, colouring, sizing, text and
    highlighting, canvas, screen geometry, axes, comparison styling, trial
    selection) plus provenance (app version, export date, data source).

    The file describes a figure and nothing else. The annotations, the column
    mapping and the metadata tables each have their own file where they are
    edited — 🗂️ Data → Annotations → *Export*, ✏️ Edit dataset → *Download setup
    file*, and the tables you attached. (Files older than schema 4 carried
    them too; the reader ignores them.)"""
    # PLOT_CONFIG_SCHEMA is the single source of truth for the version; bump
    # it (+ register a migration) in url_state when this layout changes.
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

    # Schema 6: the *requested* mode (the switches), as a link records it.
    animate_on = bool(state.get(SINGLE_ANIMATE, False))
    compare_on = bool(state.get(SINGLE_COMPARE_TOGGLE, False))
    published = (state.get("_share_selection") or {}).get("compare")
    compare_b = (
        {
            "participant_id": str(published["participant_id"]),
            "trial_id": str(published["trial_id"]),
            "source": published.get("source") or None,
            "screen_id": (
                str(published["screen_id"])
                if published.get("screen_id") not in (None, "")
                else None
            ),
        }
        if compare_on
        and isinstance(published, dict)
        and published.get("trial_id") not in (None, "")
        else None
    )

    return {
        # Schema 4 and later = the figure only; older files still restore
        # through the same reader, which ignores what they carry beyond it.
        "schema": PLOT_CONFIG_SCHEMA,
        "app": {"name": "Scanpath Studio", "version": app_version},
        # When this config was saved (ISO 8601, local time) — provenance only,
        # surfaced when restoring (Share → File + the upload wizard's restore step).
        "exported_at": exported_at,
        "data_source": data_source,
        "selection": {
            "participant_id": selected_participant,
            "trial_id": selected_trial,
            **(
                {"screen_id": str(state["single_screen_id"])}
                if state.get("single_screen_id") not in (None, "")
                else {}
            ),
            # Schema 6: scanpath B by identity — reader, trial, dataset (None
            # = A's) and screen — as the figure last published it for Share.
            **({"compare": compare_b} if compare_b else {}),
        },
        # Schema 6: the mode the figure was saved in. Written both ways, so a
        # static file restores as static rather than leaving a replay running.
        "mode": {"animate": animate_on, "compare": compare_on},
        "canvas_px": {"width": int(canvas_width), "height": int(canvas_height)},
        "experimental_setup": {
            "monitor_width_mm": float(state.get("global_monitor_width_mm", 597.0)),
            "viewing_distance_mm": float(
                state.get("global_viewing_distance_mm", 800.0)
            ),
            "display_dpi": float(state.get("global_display_dpi", 96.0)),
            "stimulus_font_pt": float(state.get("global_stimulus_font_pt", 12.0)),
            "use_stimulus_font_pt": bool(
                state.get("global_use_stimulus_font_pt", False)
            ),
            # How each group came to be known. Additive, so it needs no
            # migration and PLOT_CONFIG_SCHEMA stays put. Absent when the active
            # source never declared a setup — an omitted key reads as
            # "unknown", which is true; writing "assumed" there would invent a
            # claim.
            **(setup_provenance or {}),
        },
        "axes": {
            "x_field": x_field,
            "y_field": y_field,
            "coordinate_grid": bool(figure_settings.get("show_coordinate_grid", False)),
            "coordinate_grid_auto": bool(
                viz_settings.get("coordinate_grid_auto", True)
            ),
            "coordinate_grid_spacing": float(
                state.get("global_coordinate_grid_spacing", 100.0)
            ),
            # Crop to data's margin (applies while cropping).
            "crop_margin_auto": bool(state.get("global_crop_margin_auto", True)),
            "crop_margin_px": float(
                state.get("global_crop_margin_px", DEFAULT_CROP_MARGIN_PX)
            ),
        },
        "layers": {
            "words": figure_settings["show_words"],
            "word_labels": figure_settings["show_word_labels"],
            # The 📄 Stimulus master switch — like the other section
            # switches (fixations/saccades/heatmap/raw_gaze) this is the raw
            # widget value, not something `_collect_viz_settings` gates.
            "stimulus": bool(state.get("global_show_stimulus", True)),
            "fixations": figure_settings["show_fixations"],
            "order_labels": figure_settings["show_order"],
            "saccades": figure_settings["show_saccades"],
            "saccade_arrows": figure_settings.get("show_saccade_arrows", False),
            "heatmap": figure_settings["show_heatmap"],
            # The switch, not the figure's *effective* raw gaze (switch AND
            # this trial has samples), so saving on a trial without raw gaze
            # still records the layer as on.
            "raw_gaze": bool(viz_settings.get("show_raw_gaze", False)),
            "stimulus_image": viz_settings.get("show_stimulus_image", False),
            "full_monitor": figure_settings.get("fit_to_monitor", True),
            # Autoplay the animated replay on load.
            "autoplay": bool(viz_settings.get("anim_autoplay", True)),
        },
        "illustration": {
            "label_mode": viz_settings.get("illustration_label", "Auto"),
            "text": str(viz_settings.get("illustration_text", "")),
            "reasons": list(viz_settings.get("illustration_reasons") or []),
        },
        "preprocessing": {
            "enabled": bool(state.get("global_preproc_enabled", False)),
            "short_policy": state.get("global_preproc_short_policy", "Off"),
            "short_threshold_ms": float(
                state.get("global_preproc_short_threshold_ms", 80.0)
            ),
            "merge_distance_chars": float(
                state.get("global_preproc_merge_distance_chars", 1.0)
            ),
            "discard_blink_adjacent": bool(
                state.get("global_preproc_blink_adjacent", True)
            ),
        },
        # The animation frame grid, so a restored config reproduces the same
        # smoothness / export size.
        "animation": {
            "grid_step_ms": int(viz_settings.get("anim_grid_step_ms", 100) or 100),
            "max_frames": int(viz_settings.get("anim_max_frames", 360) or 360),
            # The replay speed — a non-1× speed is an Illustration.
            "playback_speed": float(state.get(SINGLE_PLAYBACK_SPEED, 1.0) or 1.0),
        },
        # Export → Current figure's print size (a blank width is the
        # screen-size PNG).
        "export": (print_size or {}),
        "coloring": {
            "color_by": "line"
            if figure_settings.get("color_by_line")
            else figure_settings["color_by"],
            "color_by_line": bool(figure_settings.get("color_by_line")),
            "heatmap_metric": viz_settings["heatmap_metric"],
            "heatmap_style": figure_settings.get("heatmap_style", "Word boxes"),
            # The Smoothed blur: Auto, and the fixed σ kept for when it is off.
            "heatmap_sigma_auto": bool(state.get("global_heatmap_sigma_auto", True)),
            "heatmap_sigma_px": float(
                state.get("global_heatmap_sigma_px", DEFAULT_HEATMAP_SIGMA_PX)
            ),
            "heatmap_norm": figure_settings.get("heatmap_norm", "Linear"),
            **{
                key: bool(figure_settings.get(key, default))
                for key, default in COLORBAR_DEFAULTS.items()
                if key.startswith("show_")
            },
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
            "saccade_opacity": float(viz_settings.get("saccade_opacity", 1.0)),
            # Colour-by-reading-type mode + per-class palette + legend.
            "saccade_color_mode": viz_settings.get("saccade_color_mode", "One color"),
            "saccade_type_legend": bool(viz_settings.get("saccade_type_legend", True)),
            "show_color_legend": bool(viz_settings.get("show_color_legend", True)),
            "show_highlight_legend": bool(
                viz_settings.get("show_highlight_legend", True)
            ),
            "saccade_class_colors": dict(
                viz_settings.get("saccade_class_colors") or {}
            ),
            # The reading-class filter (which classes are drawn at all).
            "saccade_classes": list(
                viz_settings.get("saccade_classes") or SACCADE_CLASS_ORDER
            ),
            # Linear-reading mode (arced saccades + snap to line).
            "saccade_render_mode": viz_settings.get("saccade_render_mode", "Straight"),
            "fixation_snap_to_line": bool(
                viz_settings.get("fixation_snap_to_line", False)
            ),
            "fixation_snap_position": float(
                viz_settings.get("fixation_snap_position", DEFAULT_SNAP_POSITION)
            ),
            # Drift correction: saved as the picker's own spelling ("Off" or
            # a title-cased algorithm) so it restores 1:1.
            "drift_correction": str(viz_settings.get("align_algorithm", "Off")),
            "drift_connectors": bool(viz_settings.get("align_connectors", False)),
            "hollow_fixations": bool(viz_settings.get("hollow_fixations", False)),
            "fixation_opacity": float(viz_settings.get("fixation_opacity", 1.0)),
            # Uniform fixation colour · marker shape · palette (the palette's
            # colours are already in the individual keys; the name rides along
            # so the picker restores onto the right entry).
            "fixation_color": viz_settings.get(
                "fixation_color", DEFAULT_FIXATION_COLOR
            ),
            "fixation_symbol": viz_settings.get(
                "fixation_symbol", DEFAULT_FIXATION_SYMBOL
            ),
            "palette": viz_settings.get("palette", DEFAULT_PALETTE),
            # Image-stimulus opacity + manual alignment (dataset + uploads).
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
            **{
                key: figure_settings.get(key, default)
                for key, default in COLORBAR_DEFAULTS.items()
                if not key.startswith("show_")
            },
        },
        "sizing": {
            "marker_size_range": [int(s) for s in figure_settings["marker_size_range"]],
            "marker_size_scale": str(
                figure_settings.get("marker_size_scale", DEFAULT_MARKER_SIZE_SCALE)
            ),
            "marker_duration_range": [
                int(s)
                for s in figure_settings.get(
                    "marker_duration_range", DEFAULT_MARKER_DURATION_RANGE
                )
            ],
            "duration_size_legend": bool(
                figure_settings.get("duration_size_legend", True)
            ),
            "order_font_size": int(figure_settings["order_font_size"]),
            "order_font_color": figure_settings["order_font_color"],
            "base_font_size": int(base_font_size),
        },
        # Figure & canvas → Legends: every legend, Auto included, so a file
        # restores the placement it was saved with rather than leaving a
        # moved legend where the receiving session had it.
        "legends": normalize_legend_layout(figure_settings.get("legend_layout")),
        "text": {
            "scale_text_to_boxes": bool(
                figure_settings.get("scale_text_to_boxes", True)
            ),
            "line_spacing": float(
                figure_settings.get("line_spacing", DEFAULT_LINE_SPACING)
            ),
            "font_family": font_family,
            "text_color": figure_settings.get("text_color", WORD_LABEL_COLOR),
            "redact_text": bool(figure_settings.get("redact_text", False)),
            "word_hover_fields": list(viz_settings.get("word_hover_fields") or []),
            "fixation_hover_fields": list(
                viz_settings.get("fixation_hover_fields") or []
            ),
        },
        # The figure's title and caption: switches and patterns.
        "labels": {
            "show_title": bool(state.get("global_show_title", False)),
            "show_caption": bool(state.get("global_show_caption", False)),
            "title_pattern": viz_settings.get("title_pattern", ""),
            "caption_pattern": viz_settings.get("caption_pattern", ""),
        },
        "highlighting": {
            "critical_span_style": figure_settings.get(
                "critical_span_style", "Mark text"
            ),
            "highlight_column": figure_settings.get("highlight_column"),
            # Fixation classification: short/long/outside-the-text highlight or
            # discard, saved verbatim so it restores 1:1.
            "fixation_flags": figure_settings.get("fixation_flags"),
            "highlight_text_color": figure_settings.get(
                "highlight_text_color", HIGHLIGHTED_TEXT_COLOR
            ),
            "background_color": figure_settings.get("background_color"),
            "span_border_color": figure_settings.get("span_border_color", "#000000"),
        },
        # The rail's finer design choices (`DESIGN_*_PARAMS`: outlines, arrow
        # size, colour-bar size, title/caption fonts …), as the rail holds them
        # (an Auto box stays ticked, its number kept) so they restore 1:1.
        "design": {
            param: state[key]
            for group in (
                DESIGN_TOGGLE_PARAMS,
                DESIGN_COLOR_PARAMS,
                DESIGN_INT_PARAMS,
                DESIGN_FLOAT_PARAMS,
            )
            for param, key in group.items()
            if state.get(key) is not None
        },
        "raw_gaze": {
            "available": not trial_raw_gaze.empty,
            "points": len(trial_raw_gaze) if not trial_raw_gaze.empty else 0,
            # The dataset's samples are made up (the bundled demo's) —
            # provenance, like the two keys above, and not read back.
            "synthesized": raw_gaze_synthesized,
            # The layer's own style — the keys above describe the trial the
            # config was saved on and are not read back.
            "color": viz_settings.get("raw_gaze_color", "#888888"),
            "marker_size": float(viz_settings.get("raw_gaze_marker_size", 4.0)),
            "opacity": float(viz_settings.get("raw_gaze_opacity", 0.6)),
        },
        # The ⬚ Word boxes section's style (its switch is `layers.words`).
        "word_boxes": {
            "color": viz_settings.get("word_box_color", WORD_BOX_COLOR),
            "line_opacity": float(
                viz_settings.get("word_box_line_opacity", WORD_BOX_LINE_OPACITY)
            ),
            "fill_color": viz_settings.get("word_box_fill_color", WORD_BOX_FILL_COLOR),
            "fill_opacity": float(
                viz_settings.get("word_box_fill_opacity", WORD_BOX_FILL_OPACITY)
            ),
        },
        # Per-scanpath styling for the two-trial comparison (None when the caller
        # didn't collect it). Each entry holds raw widget values so it restores 1:1.
        "compare": compare_styles,
        # How the two scanpaths are arranged, and whose stimulus an
        # overlay draws. Separate from `compare` above, which is a two-entry list
        # of per-scanpath *styling*; these describe the view itself.
        "compare_view": {
            "layout": state.get(SINGLE_COMPARE_LAYOUT, "Overlay"),
            "stimulus": state.get(SINGLE_COMPARE_STIMULUS, "Both"),
            # The A/B legend, the one compare setting that is a switch.
            "legend": bool(viz_settings.get("show_compare_legend", True)),
        },
    }


def render_plot_config(
    settings: Mapping,
    *,
    participant: str,
    trial: str,
    canvas_width: int,
    canvas_height: int,
    base_font_size: int,
    font_family: str,
    x_field: str,
    y_field: str,
    screen_id: str | None = None,
    setup: dict | None = None,
) -> dict:
    """Serialize an exported static figure in Share's restorable format."""
    from .build_info import build_info

    names = {f.name for f in fields(FigureSettings)}
    figure = FigureSettings.from_mapping(
        {k: v for k, v in settings.items() if k in names},
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        base_font_size=base_font_size,
        font_family=font_family,
        x_field=x_field,
        y_field=y_field,
    )
    values = figure.for_builder(names)
    viz = {
        **values,
        "heatmap_metric": figure.heatmap_metric or "counts",
        "saccade_style": next(
            (
                label
                for label, dash in SACCADE_DASH_OPTIONS.items()
                if dash == figure.saccade_style
            ),
            "Solid",
        ),
        "illustration_label": settings.get("illustration_label", "Auto"),
        "align_algorithm": settings.get("align_algorithm", "Off"),
        "align_connectors": bool(settings.get("align_connectors")),
        "show_stimulus_image": bool(figure.background_image),
        "coordinate_grid_auto": figure.coordinate_grid_spacing is None,
        **{
            k: settings[k]
            for k in (
                "stimulus_image_opacity",
                "stimulus_image_offset_x",
                "stimulus_image_offset_y",
                "stimulus_image_scale",
                "title_pattern",
                "caption_pattern",
            )
            if k in settings
        },
    }
    state = {f"global_{k}": v for k, v in values.items() if v is not None}
    state.update(
        {
            "single_screen_id": screen_id,
            "global_show_title": bool(settings.get("title_pattern")),
            "global_show_caption": bool(settings.get("caption_pattern")),
            "global_crop_margin_auto": figure.crop_margin is None,
            "global_crop_margin_px": (
                DEFAULT_CROP_MARGIN_PX
                if figure.crop_margin is None
                else figure.crop_margin
            ),
            "global_heatmap_sigma_auto": figure.heatmap_sigma_px is None,
            "global_heatmap_sigma_px": figure.heatmap_sigma_px
            or DEFAULT_HEATMAP_SIGMA_PX,
            "global_heatmap_opacity_auto": figure.heatmap_opacity is None,
        }
    )
    for bar in ("fixation", "heatmap"):
        length = getattr(figure, f"{bar}_colorbar_length")
        state[f"global_{bar}_colorbar_length_auto"] = length is None
    for name, value in (settings.get("preprocessing") or {}).items():
        key = "blink_adjacent" if name == "discard_blink_adjacent" else name
        state[f"global_preproc_{key}"] = value
    config = build_plot_config(
        selected_participant=participant,
        selected_trial=trial,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        x_field=x_field,
        y_field=y_field,
        figure_settings=values,
        viz_settings=viz,
        base_font_size=base_font_size,
        font_family=font_family,
        trial_raw_gaze=pd.DataFrame(),
        data_source=settings.get("data_source"),
        app_version=build_info().version,
        exported_at="",
        state=state,
    )
    config.pop("exported_at")
    if not drift_correction_enabled():
        config["coloring"].pop("drift_correction", None)
        config["coloring"].pop("drift_connectors", None)
    if setup is None:
        config.pop("experimental_setup")
    else:
        config["experimental_setup"] = setup
    return config
