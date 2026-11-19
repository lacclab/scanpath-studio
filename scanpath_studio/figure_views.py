"""Which accepted figure options affect each scanpath view."""

from __future__ import annotations

HEATMAP_OPTIONS = (
    "show_heatmap",
    "heatmap_style",
    "heatmap_metric",
    "heatmap_colorscale",
    "heatmap_norm",
    "heatmap_range",
    "heatmap_opacity",
    "heatmap_sigma_px",
    "word_heatmap_col",
    "word_heatmap_title",
    "show_heatmap_colorbar",
    "heatmap_colorbar_orientation",
    "heatmap_colorbar_length",
    "heatmap_colorbar_thickness",
    "heatmap_colorbar_tickangle",
    "heatmap_colorbar_tickfont_size",
)
RAW_GAZE_OPTIONS = (
    "show_raw_gaze",
    "raw_gaze_color",
    "raw_gaze_marker_size",
    "raw_gaze_opacity",
)

# Two-scanpath figures take these values from each scanpath's style.
STYLE_KEYS_FOR_TWO_SCANPATHS = {
    "order_font_color": "fix_color",
    "fixation_color": "fix_color",
    "fixation_opacity": "opacity",
    "hollow_fixations": "hollow",
    "saccade_color": "saccade_color",
    "saccade_style": "saccade_style",
    "saccade_width": "saccade_width",
}


# Compare uses spatial axes, per-reading box outlines and word-box heatmaps.
_INACTIVE_IN_COMPARISON = frozenset(
    {
        "x_field",
        "y_field",
        "raw_gaze_color",
        "word_box_color",
        "critical_span_style",
        "span_border_color",
        "saccade_render_mode",
        "saccade_color_mode",
        "saccade_class_colors",
        "saccade_type_legend",
        "fixation_snap_to_line",
        "fixation_snap_position",
        "heatmap_style",
        "heatmap_sigma_px",
        "word_heatmap_col",
        "word_heatmap_title",
        "illustration_reasons",
        "illustration_text",
        "show_connectors",
        "connector_y",
        *STYLE_KEYS_FOR_TWO_SCANPATHS,
    }
)

# A replay draws one set of boxes with the figure-wide style, and no heatmap or gaze.
STATIC_COMPARISON_LAYER_STYLES = frozenset(
    {
        "box_color",
        "box_fill_color",
        "box_line_opacity",
        "box_fill_opacity",
        "raw_gaze_color",
        "heatmap_colorscale",
    }
)

SECOND_SCANPATH_OPTIONS = frozenset(
    {
        "label_a",
        "label_b",
        "words_b",
        "fixations_b",
        "fixation_flags_b",
        "show_legend",
        "style_a",
        "style_b",
        "compare_stimulus",
    }
)


def options_for_view(names, kind: str, *, comparing: bool = False) -> set[str]:
    """The options from names that can change this view or its replay frames."""
    names = set(names)
    if kind == "comparison":
        return names - _INACTIVE_IN_COMPARISON
    if kind == "animation":
        names.difference_update(RAW_GAZE_OPTIONS, HEATMAP_OPTIONS)
        names.difference_update(
            STYLE_KEYS_FOR_TWO_SCANPATHS if comparing else SECOND_SCANPATH_OPTIONS
        )
    return names
