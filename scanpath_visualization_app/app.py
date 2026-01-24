"""Scanpath Visualization Streamlit app.

This is the main entry point for the Streamlit application that visualizes
eye-tracking scanpaths over text.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd
import streamlit as st

# Allow running via `streamlit run scanpath_visualization_app/app.py` by adding the
# repository root to sys.path when executed as a script instead of a package.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scanpath_visualization_app.constants import FONT_FAMILY
from scanpath_visualization_app.controls import data_dictionary_help_text, sidebar_controls
from scanpath_visualization_app.data import (
    compute_canvas_size,
    default_filters,
    filter_data,
    filter_raw_gaze,
    infer_fix_schema,
    infer_raw_gaze_schema,
    infer_word_schema,
    load_sample_data,
    load_sample_raw_gaze,
    normalize_fixations,
    normalize_raw_gaze,
    normalize_words,
)
from scanpath_visualization_app.styles import get_app_css
from scanpath_visualization_app.tabs import (
    render_animation_tab,
    render_data_statistics_tab,
    render_raw_data_tab,
    render_single_trial_tab,
)
from scanpath_visualization_app.utils import build_combo_options

# Re-export utility functions for backward compatibility with tests/imports
from scanpath_visualization_app.utils import (  # noqa: F401
    build_comparison_options as _build_comparison_options,
    compute_trial_stats,
    friendly_trial_label as _friendly_trial_label,
    gather_trial_metadata,
)


def clamp_canvas_size(words: pd.DataFrame, fixations: pd.DataFrame) -> Tuple[int, int]:
    """Clamp canvas dimensions to reasonable bounds (backward compat wrapper)."""
    default_canvas_w, default_canvas_h = compute_canvas_size(words, fixations)
    return (
        min(max(default_canvas_w, 100), 10000),
        min(max(default_canvas_h, 100), 10000),
    )


# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------


def configure_page() -> None:
    """Set up Streamlit page configuration and custom CSS."""
    st.set_page_config(
        page_title="Scanpath Visualization",
        page_icon="👀",
        layout="wide",
    )
    st.markdown(get_app_css(), unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------


def load_words_and_fixations(data_choice: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return uploaded CSVs or fall back to bundled demo data."""
    if data_choice == "Upload csv tables":
        uploaded_words = st.sidebar.file_uploader("Words/IA csv", type=["csv"])
        uploaded_fixations = st.sidebar.file_uploader("Fixations csv", type=["csv"])
        if uploaded_words and uploaded_fixations:
            return pd.read_csv(uploaded_words), pd.read_csv(uploaded_fixations)
        st.sidebar.info("Upload both files or switch to demo data.")
        return load_sample_data()
    return load_sample_data()


def prepare_data(
    words_df: pd.DataFrame, fixations_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Infer schemas and normalize incoming dataframes."""
    word_schema = infer_word_schema(words_df)
    fix_schema = infer_fix_schema(fixations_df)
    if not word_schema or not fix_schema:
        st.stop()
    return normalize_words(words_df, word_schema), normalize_fixations(
        fixations_df, fix_schema
    )


def load_raw_gaze_data(data_choice: str) -> pd.DataFrame:
    """Load and normalize raw gaze data if available."""
    raw_gaze_df = pd.DataFrame()

    if data_choice == "Use bundled demo":
        raw_gaze_df = load_sample_raw_gaze()
        if not raw_gaze_df.empty:
            raw_gaze_schema = infer_raw_gaze_schema(raw_gaze_df)
            if raw_gaze_schema:
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)
            else:
                st.sidebar.warning("Could not infer raw gaze schema from sample data")
                raw_gaze_df = pd.DataFrame()
        else:
            st.sidebar.info("No sample raw gaze data available")
    else:
        uploaded_raw_gaze = st.sidebar.file_uploader(
            "Raw gaze csv (optional)",
            type=["csv"],
            help="Optional: millisecond-level gaze data with participant_id, trial_id, x, y columns.",
        )
        if uploaded_raw_gaze:
            raw_gaze_df = pd.read_csv(uploaded_raw_gaze)
            raw_gaze_schema = infer_raw_gaze_schema(raw_gaze_df)
            if raw_gaze_schema:
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)
            else:
                raw_gaze_df = pd.DataFrame()

    return raw_gaze_df


# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------


def render_sidebar_data_source() -> str:
    """Render the data source selection in sidebar."""
    st.sidebar.header("Experimental Setup")
    return st.sidebar.radio(
        "Data source",
        ["Use bundled demo", "Upload csv tables"],
        index=0,
        help=data_dictionary_help_text(),
    )


def render_sidebar_canvas_controls(
    words_filtered: pd.DataFrame, fixations_filtered: pd.DataFrame
) -> Tuple[int, int, int, str]:
    """Render canvas dimension and font controls in sidebar."""
    default_canvas_w, default_canvas_h = compute_canvas_size(
        words_filtered, fixations_filtered
    )
    canvas_width = min(max(default_canvas_w, 100), 10000)
    canvas_height = min(max(default_canvas_h, 100), 10000)

    canvas_width = st.sidebar.number_input(
        "Monitor width (px)",
        min_value=100,
        max_value=10000,
        value=canvas_width,
        step=10,
        help="Use the real monitor width in pixels to keep coordinates true to scale.",
    )
    canvas_height = st.sidebar.number_input(
        "Monitor height (px)",
        min_value=100,
        max_value=10000,
        value=canvas_height,
        step=10,
        help="Use the real monitor height in pixels to keep coordinates true to scale.",
    )
    base_font_size = st.sidebar.number_input(
        "Figure font size (px)",
        min_value=6,
        max_value=72,
        value=16,
        step=1,
        help="Match the font size used in your experiment to keep bounding boxes aligned.",
    )
    font_family = st.sidebar.text_input(
        "Word label font family",
        value=FONT_FAMILY,
        help="Use the exact font from the experiment (e.g., 'Arial' or a fall-back stack).",
    )
    st.sidebar.divider()

    return int(canvas_width), int(canvas_height), int(base_font_size), font_family


# -----------------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------------


def main() -> None:
    """Main application entry point."""
    configure_page()

    st.title("Scanpath Visualization")
    st.caption("Visualize eye-tracking-while-reading scanpaths!")

    # Data source selection
    data_choice = render_sidebar_data_source()

    # Load and prepare data
    words_df, fixations_df = load_words_and_fixations(data_choice)
    words_df, fixations_df = prepare_data(words_df, fixations_df)
    raw_gaze_df = load_raw_gaze_data(data_choice)

    # Apply filters
    filters = default_filters(words_df, fixations_df)
    words_filtered, fixations_filtered = filter_data(words_df, fixations_df, filters)

    # Filter raw gaze data
    if not raw_gaze_df.empty:
        raw_gaze_filtered = filter_raw_gaze(
            raw_gaze_df,
            filters.get("participants", []),
            filters.get("trials", []),
        )
        if raw_gaze_filtered.empty:
            st.sidebar.warning(
                f"Raw gaze data was filtered out. "
                f"Original: {len(raw_gaze_df)} rows, After filter: 0 rows"
            )
    else:
        raw_gaze_filtered = pd.DataFrame()

    # Check for empty data
    if words_filtered.empty or fixations_filtered.empty:
        st.warning(
            "No data after filtering. Try selecting more participants or trials."
        )
        return

    # Build trial combinations
    combos, _, _ = build_combo_options(fixations_filtered)

    # Canvas and visualization controls
    canvas_width, canvas_height, base_font_size, font_family = (
        render_sidebar_canvas_controls(words_filtered, fixations_filtered)
    )

    has_raw_gaze = not raw_gaze_filtered.empty
    viz_settings = sidebar_controls(
        fixations_filtered, base_font_size, has_raw_gaze=has_raw_gaze
    )

    # Render tabs
    tab_single, tab_animation, tab_raw, tab_stats = st.tabs(
        ["Interactive Plot", "Animated Scanpath", "Raw Data", "Data Statistics"]
    )

    with tab_single:
        render_single_trial_tab(
            words_filtered,
            fixations_filtered,
            combos,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            viz_settings=viz_settings,
            raw_gaze=raw_gaze_filtered,
        )

    with tab_animation:
        render_animation_tab(
            words_filtered,
            fixations_filtered,
            combos,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            viz_settings=viz_settings,
        )

    with tab_raw:
        render_raw_data_tab(words_filtered, fixations_filtered, raw_gaze_filtered)

    with tab_stats:
        render_data_statistics_tab(
            words_filtered, fixations_filtered, raw_gaze_filtered
        )


if __name__ == "__main__":
    main()
