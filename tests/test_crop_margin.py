"""#422 — Crop to data's margin is a setting, on every surface.

It used to be fixed: 5% of the data's extent on each axis, at least 20 px. That
stays the default (``crop_margin=None`` / *Auto*), so nothing changes unless a
margin is chosen; a number is that many screen px on every side.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio import api, cli
from scanpath_studio.plots import _compute_axis_ranges
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

_FIX = pd.DataFrame({"x": [100.0, 1100.0], "y": [200.0, 400.0]})


class TestTheRange:
    def test_auto_is_the_old_fixed_margin(self):
        x_range, y_range, *_ = _compute_axis_ranges(
            2560, 1440, (_FIX, "x", "y"), fit_to_monitor=False
        )
        # 5% of 1000 px wide, and the 20 px floor on 200 px tall.
        assert x_range == [50.0, 1150.0]
        assert y_range == [420.0, 180.0]

    def test_a_margin_is_that_many_px_on_every_side(self):
        x_range, y_range, *_ = _compute_axis_ranges(
            2560, 1440, (_FIX, "x", "y"), fit_to_monitor=False, crop_margin=30
        )
        assert x_range == [70.0, 1130.0]
        assert y_range == [430.0, 170.0]

    def test_zero_is_tight_and_the_whole_monitor_ignores_it(self):
        x_range, *_ = _compute_axis_ranges(
            2560, 1440, (_FIX, "x", "y"), fit_to_monitor=False, crop_margin=0
        )
        assert x_range == [100.0, 1100.0]
        x_range, *_ = _compute_axis_ranges(
            2560, 1440, (_FIX, "x", "y"), fit_to_monitor=True, crop_margin=30
        )
        assert x_range == [0, 2560]


def test_the_api_takes_it_and_defaults_to_auto():
    for kind in ("static", "animation", "comparison"):
        assert api.figure_options(kind)["crop_margin"] is None
    data = api.load_sample_data()
    words, fixations = data.words, data.fixations
    pid, tid = api.list_trials(words, fixations).iloc[0]

    def x_range(**options):
        fig = api.plot_scanpath(
            words, fixations, pid, tid, show_heatmap=False, **options
        )
        return tuple(fig.layout.xaxis.range)

    tight = x_range(fit_to_monitor=False, crop_margin=0)
    assert x_range(fit_to_monitor=False, crop_margin=30) == pytest.approx(
        (tight[0] - 30, tight[1] + 30)
    )
    # Auto is the 5% margin it always was; the whole monitor ignores a margin.
    auto = x_range(fit_to_monitor=False)
    width = tight[1] - tight[0]
    assert auto == pytest.approx((tight[0] - 0.05 * width, tight[1] + 0.05 * width))
    assert x_range(crop_margin=30) == x_range()


def test_the_cli_flag_reaches_the_builder_and_crops(monkeypatch, tmp_path):
    captured: list[dict] = []

    def fake_plot(*args, **kwargs):
        captured.append(kwargs)
        return go.Figure()

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **kwargs: Path(path))
    cli.main(
        ["render", "--sample", "--crop-margin", "30", "-o", str(tmp_path / "a.html")]
    )
    assert captured[0]["crop_margin"] == 30
    # A margin is only drawn around a cropped view.
    assert captured[0]["fit_to_monitor"] is False
    with pytest.raises(SystemExit):
        cli.main(
            ["render", "--sample", "--crop-margin", "-1", "-o", str(tmp_path / "b")]
        )


def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_crop"] = (
        st.session_state.get("global_crop_margin_auto"),
        st.session_state.get("global_crop_margin_px"),
    )


def _share_app():
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["global_fit_to_monitor"] = False
    st.session_state["global_crop_margin_auto"] = False
    st.session_state["global_crop_margin_px"] = 40.0
    st.session_state["_query"], _ = _build_share_query(DEMO_CHOICE)


def test_the_link_carries_it_both_ways():
    linked = AppTest.from_function(_link_app)
    linked.query_params["crop_margin_auto"] = "0"
    linked.query_params["crop_margin"] = "99999"  # clamped
    linked.run(timeout=30)
    assert not linked.exception, linked.exception
    assert linked.session_state["_crop"] == (False, 2000.0)

    shared = AppTest.from_function(_share_app).run(timeout=30)
    assert not shared.exception, shared.exception
    params = parse_qs(shared.session_state["_query"])
    assert params["crop_margin_auto"] == ["0"]
    assert params["crop_margin"] == ["40.0"]


@pytest.mark.timeout(180)
def test_the_rail_row_greys_until_cropping_and_reaches_the_figure():
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=60)
    assert not at.exception, at.exception

    def margin_box():
        return next(w for w in at.number_input if w.key == "global_crop_margin_px")

    def auto_box():
        return next(w for w in at.checkbox if w.key == "global_crop_margin_auto")

    # The whole monitor is shown by default: the margin has nothing to do.
    assert auto_box().disabled and margin_box().disabled
    next(w for w in at.checkbox if w.key == "_rail_crop_to_data").check().run(
        timeout=60
    )
    assert not auto_box().disabled
    assert margin_box().disabled  # Auto is on
    auto_box().uncheck().run(timeout=60)
    margin_box().set_value(30.0).run(timeout=60)
    assert not at.exception, at.exception

    assert at.session_state["global_crop_margin_px"] == 30.0
    assert at.session_state["global_crop_margin_auto"] is False
    assert at.session_state["global_fit_to_monitor"] is False


def _figure_settings_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import _collect_viz_settings
    from scanpath_studio.tabs import _build_figure_settings

    fixations = pd.DataFrame({"x": [1.0], "y": [2.0], "duration_ms": [100.0]})
    out = []
    for crop, auto in ((True, False), (False, True), (False, False)):
        st.session_state["global_fit_to_monitor"] = not crop
        st.session_state["global_crop_margin_auto"] = auto
        st.session_state["global_crop_margin_px"] = 30.0
        viz = _collect_viz_settings(
            fixations, None, numeric_fields=["x", "y"], highlight_options=[]
        )
        out.append(_build_figure_settings(viz, False)["crop_margin"])
    st.session_state["_margins"] = out


def test_the_app_hands_the_figure_a_margin_only_when_one_is_chosen():
    at = AppTest.from_function(_figure_settings_app).run(timeout=30)
    assert not at.exception, at.exception
    # Cropped + manual → 30; whole monitor, or Auto → None (the automatic one).
    assert at.session_state["_margins"] == [30.0, None, None]
