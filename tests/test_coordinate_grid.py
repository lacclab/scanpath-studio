"""VIZ-34 monitor-pixel coordinate grid across every rendering surface."""

from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import parse_qs

import plotly.graph_objects as go
import pytest

import scanpath_studio as sps
from scanpath_studio import api, cli, plots
from scanpath_studio.export import _plot_config_dict


@pytest.fixture(scope="module")
def sample():
    return sps.load_sample_data()


def test_ticks_are_zero_anchored_for_full_cropped_negative_and_inverted_ranges():
    full = plots.coordinate_grid_ticks(
        [0, 1919], [1079, 0], spacing=200, monitor_bounds=(0, 1919, 0, 1079)
    )
    assert full.x_values == tuple(float(v) for v in range(0, 2000, 200))
    assert full.y_values == tuple(float(v) for v in range(0, 1200, 200))
    assert full.major_spacing == 200
    assert full.minor_spacing == 40

    cropped = plots.coordinate_grid_ticks([-45, 315], [255, -55], spacing=100)
    assert cropped.x_values == (0.0, 100.0, 200.0, 300.0)
    assert cropped.y_values == (0.0, 100.0, 200.0)


def test_auto_spacing_uses_nice_intervals_and_thins_overlapping_labels():
    ticks = plots.coordinate_grid_ticks(
        [0, 2560], [1440, 0], rendered_width=400, rendered_height=220
    )
    scaled = ticks.major_spacing / 10 ** math.floor(math.log10(ticks.major_spacing))
    assert scaled in {1.0, 2.0, 5.0, 10.0}
    dense = plots.coordinate_grid_ticks(
        [0, 1000], [500, 0], spacing=10, rendered_width=200, rendered_height=100
    )
    assert "" in dense.x_labels
    assert len(dense.x_values) == len(dense.x_labels)


def test_invalid_manual_spacing_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        plots.coordinate_grid_ticks([0, 100], [100, 0], spacing=0)


def test_off_state_is_identical_and_on_state_preserves_geometry(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    kwargs = dict(
        canvas_size=(2560, 1440),
        show_heatmap=False,
        show_words=True,
        fit_to_monitor=True,
    )
    baseline = sps.plot_scanpath(words, fixations, pid, tid, **kwargs)
    explicit_off = sps.plot_scanpath(
        words, fixations, pid, tid, show_coordinate_grid=False, **kwargs
    )
    assert baseline.to_json() == explicit_off.to_json()

    grid = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_coordinate_grid=True,
        coordinate_grid_spacing=500,
        **kwargs,
    )
    assert tuple(grid.layout.xaxis.range) == tuple(baseline.layout.xaxis.range)
    assert tuple(grid.layout.yaxis.range) == tuple(baseline.layout.yaxis.range)
    assert (
        go.Figure(data=grid.data).to_json() == go.Figure(data=baseline.data).to_json()
    )
    assert (
        go.Figure(layout={"shapes": grid.layout.shapes}).to_json()
        == go.Figure(layout={"shapes": baseline.layout.shapes}).to_json()
    )
    assert grid.layout.width == baseline.layout.width + 52
    assert grid.layout.height == baseline.layout.height + 36
    assert list(grid.layout.xaxis.tickvals) == [0, 500, 1000, 1500, 2000, 2500]
    assert grid.layout.xaxis.minor.dtick == 100
    assert grid.layout.xaxis.tickfont.size == 18


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_static_animation_and_all_comparison_layouts_share_coordinates(sample, layout):
    words, fixations = sample
    combos = sps.list_trials(words, fixations)
    trial_a = tuple(combos.iloc[0])
    trial_b = tuple(combos.iloc[1])
    pid, tid = trial_a
    common = dict(
        canvas_width=2560,
        canvas_height=1440,
        base_font_size=16,
        show_coordinate_grid=True,
        coordinate_grid_spacing=500,
        fit_to_monitor=True,
        show_heatmap=False,
    )
    settings = plots.FigureSettings.from_mapping(common, layout=layout)
    static = plots.make_scanpath_figure(
        words[
            (words["participant_id"].astype(str) == str(pid))
            & (words["trial_id"].astype(str) == str(tid))
        ],
        fixations[
            (fixations["participant_id"].astype(str) == str(pid))
            & (fixations["trial_id"].astype(str) == str(tid))
        ],
        settings=settings,
    )
    animation = plots.make_scanpath_animation(
        words[
            (words["participant_id"].astype(str) == str(pid))
            & (words["trial_id"].astype(str) == str(tid))
        ],
        fixations[
            (fixations["participant_id"].astype(str) == str(pid))
            & (fixations["trial_id"].astype(str) == str(tid))
        ],
        settings=settings,
    )
    comparison = plots.make_comparison_figure(
        words,
        fixations,
        trial_a,
        trial_b,
        settings=settings,
    )
    expected = [0, 500, 1000, 1500, 2000, 2500]
    assert list(static.layout.xaxis.tickvals) == expected
    assert list(animation.layout.xaxis.tickvals) == expected
    assert list(comparison.layout.xaxis.tickvals) == expected
    if layout != "overlay":
        assert list(comparison.layout.xaxis2.tickvals) == expected


def test_api_option_registry_exposes_grid_on_static_and_animation():
    assert api.figure_options()["show_coordinate_grid"] is False
    assert api.figure_options()["coordinate_grid_spacing"] is None
    assert api.figure_options("animation")["show_coordinate_grid"] is False


def test_cli_forwards_grid_and_manual_spacing_to_static_and_animation(
    monkeypatch, tmp_path
):
    captured: list[dict] = []

    def fake_plot(*args, **kwargs):
        captured.append(kwargs)
        return go.Figure()

    def fake_animation(*args, **kwargs):
        captured.append(kwargs)
        return go.Figure()

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "animate_scanpath", fake_animation)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **kwargs: Path(path))
    cli.main(
        [
            "render",
            "--sample",
            "--coordinate-grid-spacing",
            "250",
            "-o",
            str(tmp_path / "static.html"),
        ]
    )
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--coordinate-grid",
            "-o",
            str(tmp_path / "animation.html"),
        ]
    )
    assert captured[0]["show_coordinate_grid"] is True
    assert captured[0]["coordinate_grid_spacing"] == 250
    assert captured[1]["show_coordinate_grid"] is True
    assert captured[1]["coordinate_grid_spacing"] is None


def _link_grid_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_grid"] = (
        st.session_state.get("global_show_coordinate_grid"),
        st.session_state.get("global_coordinate_grid_auto"),
        st.session_state.get("global_coordinate_grid_spacing"),
    )


def _share_grid_app():
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["global_show_coordinate_grid"] = True
    st.session_state["global_coordinate_grid_auto"] = False
    st.session_state["global_coordinate_grid_spacing"] = 250.0
    st.session_state["_query"], _ = _build_share_query(DEMO_CHOICE)


def test_deep_link_and_share_round_trip_grid():
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    linked = AppTest.from_function(_link_grid_app)
    linked.query_params["coordinate_grid"] = "1"
    linked.query_params["coordinate_grid_auto"] = "0"
    linked.query_params["coordinate_grid_spacing"] = "250"
    linked.run(timeout=30)
    assert not linked.exception, linked.exception
    assert linked.session_state["_grid"] == (True, False, 250.0)

    shared = AppTest.from_function(_share_grid_app).run(timeout=30)
    assert not shared.exception, shared.exception
    params = parse_qs(shared.session_state["_query"])
    assert params["coordinate_grid"] == ["1"]
    assert params["coordinate_grid_auto"] == ["0"]
    assert params["coordinate_grid_spacing"] == ["250.0"]


def test_bulk_manifest_records_grid_settings():
    config = _plot_config_dict(
        "p1",
        "t1",
        1920,
        1080,
        "x",
        "y",
        {"show_coordinate_grid": True, "coordinate_grid_spacing": 250.0},
    )
    assert config["axes"] == {
        "x_field": "x",
        "y_field": "y",
        "coordinate_grid": True,
        "coordinate_grid_auto": False,
        "coordinate_grid_spacing": 250.0,
    }


def _saved_grid_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.tabs import _build_studio_config
    from scanpath_studio.url_state import _restore_plot_config

    figure_settings = {
        "show_words": True,
        "show_word_labels": True,
        "show_fixations": True,
        "show_order": True,
        "show_saccades": True,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "show_coordinate_grid": True,
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
    viz_settings = {
        "heatmap_metric": "duration_ms",
        "coordinate_grid_auto": False,
    }
    st.session_state["global_coordinate_grid_spacing"] = 250.0
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
        exported_at="2026-08-11T00:00:00",
    )
    st.session_state["_saved_axes"] = config["axes"]
    combos = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "x": [1.0],
            "y": [2.0],
            "duration_ms": [100.0],
        }
    )
    _restore_plot_config(config, combos, fixations)
    st.session_state["_restored_grid"] = (
        st.session_state.get("global_show_coordinate_grid"),
        st.session_state.get("global_coordinate_grid_auto"),
        st.session_state.get("global_coordinate_grid_spacing"),
    )


def test_saved_config_round_trips_grid():
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    at = AppTest.from_function(_saved_grid_app).run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_saved_axes"] == {
        "x_field": "x",
        "y_field": "y",
        "coordinate_grid": True,
        "coordinate_grid_auto": False,
        "coordinate_grid_spacing": 250.0,
    }
    assert at.session_state["_restored_grid"] == (True, False, 250.0)
