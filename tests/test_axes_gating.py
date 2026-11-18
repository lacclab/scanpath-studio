"""When the X / Y fields (and what depends on them) can be changed.

The static and the Compare figures take `x_field` / `y_field`; Animate always
plots screen x / y, so the fields grey there and their hover says how to get
them back. On any other axes the static and Compare figures are a plain chart
of the fixations, so the framing and the grid, which only mean something on
screen coordinates, grey in turn.
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


def _rail(**state) -> AppTest:
    """The plot rail alone, over a tiny trial — Compare needs no second
    reading for the rail to gate on it."""
    from tests.test_rail_mode_choices import _rail_app

    at = AppTest.from_function(_rail_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def test_compare_takes_the_fields():
    at = _rail(single_compare_toggle=True)
    for key in ("global_x_field", "global_y_field"):
        assert not _widget(at.selectbox, key).disabled, key


def test_compare_on_chart_axes_greys_the_frame_and_the_grid_and_says_so():
    at = _rail(
        single_compare_toggle=True,
        global_x_field="order_in_trial",
        global_y_field="word_id",
    )
    assert at.session_state["_viz"]["x_field"] == "order_in_trial"
    for key in ("_rail_crop_to_data", "global_show_coordinate_grid"):
        assert _widget(at.checkbox, key).disabled, key
    assert any("straight saccade lines" in c.value for c in at.caption)


@pytest.mark.parametrize(
    "state",
    [{"single_animate": True}, {"single_animate": True, "single_compare_toggle": True}],
)
def test_animate_greys_the_fields_with_or_without_compare(state):
    at = _rail(global_x_field="order_in_trial", **state)
    x_field = _widget(at.selectbox, "global_x_field")
    assert x_field.disabled
    assert "Turn **Animate** off" in x_field.help
    assert "Compare" not in x_field.help
    # The stored choice is kept for when Animate is off again.
    assert at.session_state["global_x_field"] == "order_in_trial"


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_the_app_draws_a_compare_chart(layout):
    """The whole Scanpath view, Compare on chart axes: it renders cleanly."""
    at = _app(
        single_compare_toggle=True,
        single_compare_layout=layout,
        global_x_field="order_in_trial",
        global_y_field="word_id",
    )
    assert at.error == [], [e.value for e in at.error]
    assert not _widget(at.selectbox, "global_x_field").disabled
    assert at.session_state["global_x_field"] == "order_in_trial"
