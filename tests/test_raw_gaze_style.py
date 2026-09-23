"""VIZ-43: raw gaze's colour, marker size and opacity reach the figure — and last.

UX-86 gave the 🔵 Raw gaze layer its own style controls, and the headless API
has always honoured the three settings, but `tabs._build_figure_settings` never
handed them on: every app figure drew the builder's ``#888888`` / 4 / 0.6
whatever the rail said. They were also missing from the saved config, and so from
the recovery cache, which saves exactly the keys the config restores.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import persistence, session_keys
from scanpath_studio.plots import FigureSettings, make_scanpath_figure
from scanpath_studio.tabs import _build_figure_settings

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

_STYLE = {
    "raw_gaze_color": "#FF00FF",
    "raw_gaze_marker_size": 7.5,
    "raw_gaze_opacity": 0.25,
}


def _viz_settings(**extra) -> dict:
    """The keys `_build_figure_settings` indexes without a default."""
    return {
        "show_words": True,
        "show_labels": True,
        "show_fix": True,
        "show_order": False,
        "show_saccades": True,
        "show_heatmap": False,
        "color_by": "(uniform)",
        "heatmap_metric": "duration_ms",
        "marker_size_range": (8, 24),
        "order_font_size": 12,
        "order_font_color": "#000000",
        "show_colorbars": False,
        "fixation_color_range": None,
        "heatmap_range": None,
        "fixation_colorscale": "Viridis",
        "heatmap_colorscale": "Viridis",
        **extra,
    }


def test_the_figure_settings_carry_the_rails_raw_gaze_style():
    settings = _build_figure_settings(_viz_settings(**_STYLE), True)
    for key, value in _STYLE.items():
        assert settings[key] == value, key


def test_the_raw_gaze_trace_is_drawn_in_that_style(
    normalized_words_df, normalized_fixations_df
):
    raw = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "x": [110.0, 120.0, 130.0],
            "y": [72.0, 74.0, 76.0],
        }
    )
    settings = FigureSettings.from_mapping(
        {
            **_build_figure_settings(_viz_settings(**_STYLE), True),
            "canvas_width": 800,
            "canvas_height": 600,
            "base_font_size": 12,
        }
    )
    fig = make_scanpath_figure(
        normalized_words_df, normalized_fixations_df, settings=settings, raw_gaze=raw
    )
    trace = next(t for t in fig.data if t.name == "Raw gaze")
    assert trace.marker.color == "#FF00FF"
    assert trace.marker.size == 7.5
    assert trace.marker.opacity == 0.25


def test_the_recovery_cache_carries_them():
    # The cache writes `PLOT_CONFIG_STATE_KEYS`, so pinning them there is what
    # makes a restart keep the style.
    style_keys = {
        session_keys.GLOBAL_RAW_GAZE_COLOR,
        session_keys.GLOBAL_RAW_GAZE_MARKER_SIZE,
        session_keys.GLOBAL_RAW_GAZE_OPACITY,
    }
    assert style_keys <= session_keys.PLOT_CONFIG_STATE_KEYS
    assert style_keys <= persistence._SESSION_KEYS


def test_the_cache_clamps_a_stored_opacity_it_cannot_draw(tmp_path):
    persistence.save_state(
        {"global_raw_gaze_opacity": 7, "global_raw_gaze_color": "#123456"}, tmp_path
    )
    restored: dict = {}
    assert persistence.restore_state(restored, tmp_path)
    assert restored["global_raw_gaze_opacity"] == 1.0
    assert restored["global_raw_gaze_color"] == "#123456"


def _config_roundtrip_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.tabs import _build_studio_config
    from scanpath_studio.url_state import _restore_plot_config

    viz_settings = {
        "heatmap_metric": "duration_ms",
        "raw_gaze_color": "#FF00FF",
        "raw_gaze_marker_size": 7.5,
        "raw_gaze_opacity": 0.25,
    }
    figure_settings = {
        "show_words": True,
        "show_word_labels": True,
        "show_fixations": True,
        "show_order": True,
        "show_saccades": True,
        "show_heatmap": False,
        "show_raw_gaze": True,
        "color_by": "duration_ms",
        "show_colorbars": False,
        "fixation_color_range": None,
        "heatmap_range": None,
        "fixation_colorscale": "Blues",
        "heatmap_colorscale": "Greens",
        "marker_size_range": (8, 24),
        "order_font_size": 12,
        "order_font_color": "#000000",
    }
    config = _build_studio_config(
        selected_participant="p1",
        selected_trial="t1",
        canvas_width=1000,
        canvas_height=800,
        x_field="x",
        y_field="y",
        figure_settings=figure_settings,
        viz_settings=viz_settings,
        base_font_size=14,
        trial_raw_gaze=pd.DataFrame(),
        font_family="Arial",
        annotation_records=[],
        column_mapping={},
        data_source="demo",
        app_version="0.0.0",
        exported_at="2026-09-23T00:00:00",
    )
    st.session_state["_saved"] = dict(config["raw_gaze"])
    _restore_plot_config(config, pd.DataFrame(), pd.DataFrame())
    st.session_state["_restored"] = {
        key: st.session_state.get(f"global_{key}")
        for key in ("raw_gaze_color", "raw_gaze_marker_size", "raw_gaze_opacity")
    }


def test_the_saved_config_round_trips_them():
    at = AppTest.from_function(_config_roundtrip_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    saved = at.session_state["_saved"]
    assert (saved["color"], saved["marker_size"], saved["opacity"]) == (
        "#FF00FF",
        7.5,
        0.25,
    )
    assert at.session_state["_restored"] == _STYLE
