"""When the X / Y fields (and what depends on them) can be changed.

Static figures and comparisons can use numeric axes. Replays use screen
coordinates. Screen framing and the coordinate grid apply to spatial figures.
"""

from __future__ import annotations

import pytest

from scanpath_studio.chart_axes import GAZE_OVER_TIME
from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from scanpath_studio.constants import DEMO_CHOICE
from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY
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
    assert "Animation uses screen coordinates" in x_field.help
    # The frame and the grid still apply to the replay.
    assert not _widget(at.checkbox, "_rail_crop_to_data").disabled


def test_chart_axes_grey_the_frame_and_the_grid():
    at = _app(global_x_field="duration_ms")
    assert not _widget(at.selectbox, "global_x_field").disabled
    for key in ("_rail_crop_to_data", "global_show_coordinate_grid"):
        assert _widget(at.checkbox, key).disabled, key


def test_comparison_controls_follow_reading_b_even_when_a_has_only_one_trial():
    at = _app()
    at.button(key="viz_view_gaze_over_time").click().run()
    at.toggle(key="single_compare_toggle").set_value(True).run()

    def check_figure(kind):
        assert not at.exception
        assert at.session_state[SNIPPET_STATE_KEY].kind == kind
        comparing = kind == "comparison"
        assert at.button(key="viz_view_illustration").disabled == comparing
        assert not at.button(key="viz_view_gaze_over_time").disabled
        for key in ("_plot_axis_preset", "global_x_field", "global_y_field"):
            assert not at.selectbox(key=key).disabled
        assert at.checkbox(key="global_show_coordinate_grid").disabled
        assert (
            at.session_state["global_x_field"],
            at.session_state["global_y_field"],
        ) == GAZE_OVER_TIME

    check_figure("comparison")
    share = at.session_state["_share_selection"]
    assert share["compare"]["trial_id"] == share["trial_id"]

    at.selectbox(key=COMPARE_SOURCE_STATE_KEY).set_value(DEMO_CHOICE).run()
    check_figure("comparison")
    assert at.session_state["_share_selection"]["compare"]["source"] == DEMO_CHOICE

    at.checkbox(key="cmpfilter_favorites").check().run()
    check_figure("static")
    assert "compare" not in at.session_state["_share_selection"]
    assert at.selectbox(key=COMPARE_SOURCE_STATE_KEY).value == DEMO_CHOICE
    at.checkbox(key="cmpfilter_favorites").uncheck().run()
    check_figure("comparison")


def test_conflicting_b_sample_canvas_keeps_the_dataset_and_mode_switches_available():
    from scanpath_studio import api
    from scanpath_studio.synthetic import make_multipart_synthetic_data

    words, fixations = make_multipart_synthetic_data()
    samples = api.load_raw_gaze(
        fixations.assign(canvas_width=fixations.canvas_width + 1), names="canonical"
    )
    at = _app(
        _datasets={
            "Conflicting screens": {
                "words": words,
                "fixations": fixations,
                "raw_gaze": samples,
            }
        }
    )
    at.button(key="viz_view_gaze_over_time").click().run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    at.selectbox(key=COMPARE_SOURCE_STATE_KEY).set_value("Conflicting screens").run()
    assert not at.exception
    assert any("conflicts across tables" in warning.value for warning in at.warning)
    assert "compare" not in at.session_state["_share_selection"]
    assert at.toggle(key="single_compare_toggle").value

    at.selectbox(key=COMPARE_SOURCE_STATE_KEY).set_value(DEMO_CHOICE).run()
    assert not at.exception
    assert not any("conflicts across tables" in warning.value for warning in at.warning)
    assert at.session_state[SNIPPET_STATE_KEY].kind == "comparison"
    assert at.session_state["_share_selection"]["compare"]["source"] == DEMO_CHOICE
    at.toggle(key="single_compare_toggle").set_value(False).run()
    assert at.button(key="viz_view_gaze_over_time").proto.type == "primary"


@pytest.mark.parametrize(
    ("heat", "saccades", "live"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_hidden_markers_leave_window_for_fixation_derived_layers(heat, saccades, live):
    at = _app(
        global_show_fix=False, global_show_heatmap=heat, global_show_saccades=saccades
    )
    window = next(w for w in at.slider if w.label == "Fixation index range")
    assert window.disabled == (not live)
    assert at.multiselect(key="global_fixation_hover_fields").disabled
    if live:
        window.set_range(1, 2).run()
        assert tuple(at.session_state["single_fix_range"]) == (1, 2)


def test_outline_and_word_only_controls_follow_the_current_marks():
    at = _app(global_fixation_outline_width=0.0, global_show_stimulus=False)
    assert at.color_picker(key="global_fixation_outline_color").disabled
    assert at.checkbox(key="global_show_labels").disabled
    assert at.checkbox(key="global_scale_text_to_boxes").disabled
    assert at.multiselect(key="global_word_hover_fields").disabled
    assert not at.number_input(key="global_base_font_size").disabled
    at.toggle(key="global_show_stimulus").set_value(True).run()
    assert at.checkbox(key="global_show_labels").value
    assert not at.multiselect(key="global_word_hover_fields").disabled


def test_numeric_compare_restores_layout_and_disables_a_mismatched_size_key():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.session_state["single_compare_toggle"] = True
    at.session_state["global_x_field"] = "order_in_trial"
    at.session_state["cmp1_marker_size_range"] = (5, 30)
    at.session_state["global_duration_size_legend"] = True
    at.run()
    assert not at.exception
    view = next(w for w in at.segmented_control if w.label == "Layout")
    assert view.value == "Side by side"
    assert not at.selectbox(key="global_x_field").disabled
    assert at.segmented_control(key="single_compare_stimulus").disabled
    assert at.checkbox(key="global_duration_size_legend").disabled
    assert at.selectbox(key="global_legend_size_key_position").disabled
    assert at.session_state["global_duration_size_legend"]
    at.selectbox(key="global_x_field").set_value("x").run()
    assert not at.exception
    assert at.segmented_control(key="single_compare_layout").value == "Overlay"
    assert not at.segmented_control(key="single_compare_stimulus").disabled


def test_shared_highlight_marker_requires_the_rule_on_a_displayed_reading():
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = load_synthetic_data()
    at = _app(
        single_compare_toggle=True,
        cmp1_fixclass_blink_mode="Highlight",
        _datasets={
            "Blink events": {
                "words": words,
                "fixations": fixations.assign(blink_after=True),
            }
        },
    )
    assert at.selectbox(key="cmp1_fixclass_blink_mode").disabled
    assert at.color_picker(key="global_fixclass_blink_color").disabled
    at.selectbox(key=COMPARE_SOURCE_STATE_KEY).set_value("Blink events").run()
    assert not at.exception
    assert not at.selectbox(key="cmp1_fixclass_blink_mode").disabled
    assert not at.color_picker(key="global_fixclass_blink_color").disabled
    assert at.selectbox(key="global_fixclass_blink_mode").disabled
