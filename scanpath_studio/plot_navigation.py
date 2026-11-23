"""Find the plot editor that owns a setting."""

from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from .constants import ICONS

# Search the terms researchers see on the figure as well as the menu names.
# A destination without a tab lives beside the shared view controls.
_DESTINATIONS = {
    "Fixation color, size, opacity and numbers": ("Layers", "plot_menu_fix", None),
    "Fixation marker shape, outline and number position": (
        "Layers",
        "plot_menu_fix",
        "plot_detail_fix_marker",
    ),
    "Scale fixation size by duration": (
        "Layers",
        "plot_menu_fix",
        "plot_detail_fix_duration",
    ),
    "Fixation color range and color bar": (
        "Layers",
        "plot_menu_fix",
        "plot_detail_fix_colors",
    ),
    "Snap fixations to text lines": (
        "Layers",
        "plot_menu_fix",
        "plot_detail_fix_position",
    ),
    "Saccade color, width and direction arrows": ("Layers", "plot_menu_sac", None),
    "Saccade shape, dash, opacity and arrow size": (
        "Layers",
        "plot_menu_sac",
        "plot_detail_sac_line",
    ),
    "Show or redact stimulus text": ("Layers", "plot_menu_stim", None),
    "Text font, size and color": ("Layers", "plot_menu_stim", "plot_detail_stim_text"),
    "Highlight words in the text": (
        "Layers",
        "plot_menu_stim",
        "plot_detail_stim_highlight",
    ),
    "Stimulus image size, position and opacity": (
        "Layers",
        "plot_menu_stim",
        "plot_detail_stim_image",
    ),
    "Word box outline, fill and opacity": ("Layers", "plot_menu_boxes", None),
    "Heatmap measure, colors and opacity": ("Layers", "plot_menu_heatmap", None),
    "Heatmap smoothing and scale": (
        "Layers",
        "plot_menu_heatmap",
        "plot_detail_heat_scale",
    ),
    "Heatmap color bar": ("Layers", "plot_menu_heatmap", "plot_detail_heat_bar"),
    "Raw gaze sample size and opacity": ("Layers", "plot_menu_rawgaze", None),
    "Raw gaze sample colors": ("Layers", "plot_menu_rawgaze", "plot_detail_raw_color"),
    "Filter fixations and saccades by range, duration or class": (
        "Layers",
        "plot_menu_filter",
        None,
    ),
    "Marker shapes and colors for highlighted fixations": (
        "Layers",
        "plot_menu_filter",
        "plot_detail_highlight_markers",
    ),
    "Axes · fixation index, time and position": ("Axes", None, None),
    "Choose horizontal and vertical axis fields": (
        "Axes",
        None,
        "plot_detail_axis_fields",
    ),
    "Coordinate grid spacing and labels": (
        "Axes",
        "plot_menu_grid",
        "plot_detail_grid_spacing",
    ),
    "Screen framing, background and crop": ("Figure", "plot_menu_screen", None),
    "Figure margins and border color": (
        "Figure",
        "plot_menu_screen",
        "plot_detail_frame_style",
    ),
    "Figure title and caption": ("Figure", "plot_menu_labels", None),
    "Title and caption appearance": (
        "Figure",
        "plot_menu_labels",
        "plot_detail_text_style",
    ),
    "Illustration label": (
        "Figure",
        "plot_menu_labels",
        "plot_detail_illustration_label",
    ),
    "Hover tooltips for words and fixations": ("Figure", "plot_menu_hover", None),
    "Show or hide legends": ("Figure", "plot_menu_legends", None),
    "Legend position, arrangement and text size": (
        "Figure",
        "plot_menu_legends",
        "plot_detail_legend_layout",
    ),
    "Animation speed, autoplay and smoothness": (None, "plot_menu_animation", None),
    "Replay frame timing and frame limit": (
        None,
        "plot_menu_animation",
        "plot_detail_frame_timing",
    ),
    "Compare layout and stimulus": (None, "split_mode_compare_popover", None),
    "Compare panel titles and legend labels": (
        None,
        "split_mode_compare_popover",
        "plot_detail_compare_labels",
    ),
}


def detail_section(
    label: str, *, key: str, expanded: bool = False, track: bool = False
) -> DeltaGenerator:
    """A native disclosure the setting finder can open along with its menu."""
    return st.expander(
        label,
        key=key,
        expanded=expanded,
        on_change="rerun"
        if track or st.session_state.get("_plot_finder_used")
        else "ignore",
    )


def _open_setting() -> None:
    ss = st.session_state
    choice = ss.get("plot_setting_finder")
    if choice is None:
        return
    tab, menu, detail = _DESTINATIONS[choice]
    ss["_plot_finder_used"] = True
    for _, key, _ in _DESTINATIONS.values():
        if key and ss.get(key):
            ss[key] = False
    if tab:
        ss["plot_editor_tabs"] = tab
    if menu:
        ss[menu] = True
    if detail:
        ss[detail] = True
        if detail == "plot_detail_highlight_markers":
            ss["plot_filter_readings"] = "Reading A"
    ss["plot_setting_finder"] = None


def render_setting_finder(host) -> None:
    host.selectbox(
        "Find a plot setting",
        list(_DESTINATIONS),
        index=None,
        placeholder="Find a setting…",
        icon=ICONS["search"],
        key="plot_setting_finder",
        label_visibility="collapsed",
        on_change=_open_setting,
    )
