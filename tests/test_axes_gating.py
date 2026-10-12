"""#422 — when the X / Y fields (and what depends on them) can be changed.

Only the static figure takes `x_field` / `y_field`; Animate and Compare always
plot screen x / y, so the fields grey there and their hover says how to get
them back. On any other axes the static figure is a plain chart of the
fixations, so the framing and the grid, which only mean something on screen
coordinates, grey in turn.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

pytestmark = pytest.mark.timeout(180)


def _app(**state) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _widget(widgets, key):
    return next(w for w in widgets if w.key == key)


def test_the_fields_are_live_on_the_static_figure():
    at = _app()
    assert not _widget(at.selectbox, "global_x_field").disabled
    assert not _widget(at.checkbox, "_rail_crop_to_data").disabled
    assert not _widget(at.checkbox, "global_show_coordinate_grid").disabled


def test_animate_greys_the_fields_and_says_how_to_get_them_back():
    at = _app(single_animate=True)
    x_field = _widget(at.selectbox, "global_x_field")
    assert x_field.disabled
    assert "Turn **Animate** off" in x_field.help
    # The frame and the grid still apply to the replay.
    assert not _widget(at.checkbox, "_rail_crop_to_data").disabled


def test_chart_axes_grey_the_frame_and_the_grid():
    at = _app(global_x_field="duration_ms")
    assert not _widget(at.selectbox, "global_x_field").disabled
    for key in ("_rail_crop_to_data", "global_show_coordinate_grid"):
        assert _widget(at.checkbox, key).disabled, key
