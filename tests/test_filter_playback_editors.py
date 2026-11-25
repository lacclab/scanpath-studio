"""The reading-specific filter, label and replay controls on a real scanpath."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import tabs
from tests.conftest import APP_SCRIPT


def _smoothness(at: AppTest):
    """The replay's Smoothness selectbox, drawn under a shadow key that moves."""
    return next(box for box in at.selectbox if box.key.startswith("_anim_quality__w"))


def test_comparison_highlight_can_be_styled_when_only_reading_b_uses_it():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    tabs = {tab.label: tab for tab in at.tabs}
    a, b = tabs["Reading A"], tabs["Reading B"]
    assert a.selectbox(key="global_fixclass_short_mode").options == [
        "Show",
        "Highlight",
        "Hide",
    ]
    assert b.selectbox(key="cmp1_fixclass_short_mode").value == "Off"
    assert a.selectbox(key="global_fixclass_short_symbol").disabled
    b.selectbox(key="cmp1_fixclass_short_mode").set_value("Highlight").run()
    assert not at.selectbox(key="global_fixclass_short_symbol").disabled
    assert at.number_input(key="global_fixclass_short_threshold_ms").disabled
    assert not at.number_input(key="cmp1_fixclass_short_threshold_ms").disabled
    at.selectbox(key="global_fixclass_short_symbol").set_value("diamond-open").run()
    assert not at.exception
    assert at.session_state["cmp1_fixclass_short_mode"] == "Highlight"
    assert at.session_state["global_fixclass_short_mode"] == "Off"
    assert at.session_state["global_fixclass_short_symbol"] == "diamond-open"


@pytest.mark.parametrize("layout", ["Side by side", "Stacked"])
def test_comparison_labels_preview_and_title_split_panels_with_the_legend_hidden(
    monkeypatch, layout
):
    figures = []
    render_chart = tabs._render_true_scale_chart

    def capture_chart(fig, **kwargs):
        figures.append(fig)
        return render_chart(fig, **kwargs)

    monkeypatch.setattr(tabs, "_render_true_scale_chart", capture_chart)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    at.segmented_control(key="single_compare_layout").set_value(layout)
    at.checkbox(key="global_show_compare_legend").uncheck().run()
    at.session_state["plot_detail_compare_labels"] = True
    for idx in (0, 1):
        label = at.text_input(key=f"cmp{idx}_label_pattern")
        assert not label.disabled
        label.set_value("{participant_id} · {n_fixations}")
    window_b = next(s for s in at.slider if s.label == "B fixation index range")
    window_b.set_range(window_b.min + 1, window_b.min + 4).run()
    assert not at.exception
    selection = at.session_state["_share_selection"]
    n_a = selection["full_fix_range"][1] - selection["full_fix_range"][0] + 1
    captions = [c.value for c in at.caption]
    titles = {a.text for a in figures[-1].layout.annotations}
    for side, label in (
        ("A", f"{selection['participant_id']} · {n_a}"),
        ("B", f"{selection['compare']['participant_id']} · 4"),
    ):
        assert f"Label {side} preview — **{label}**" in captions
        assert f"{side} · {label}" in titles


def test_replay_smoothness_and_frame_timing_edit_the_same_settings():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_animate").set_value(True).run()
    _smoothness(at).set_value("Fine").run()
    assert at.slider(key="global_anim_grid_step_ms").value == 40
    assert at.number_input(key="global_anim_max_frames__num").value == 900
    at.number_input(key="global_anim_grid_step_ms__num").set_value(80).run()
    assert _smoothness(at).value == "Custom"
    at.toggle(key="single_animate").set_value(False).run()
    assert _smoothness(at).disabled
    at.toggle(key="single_animate").set_value(True).run()
    assert not at.exception
    assert at.slider(key="global_anim_grid_step_ms").value == 80
    assert _smoothness(at).value == "Custom"


def test_an_undone_smoothness_holds_against_the_closed_menus_echo():
    """Undo puts the frame grid back, and with it the Smoothness. A browser
    that showed the control keeps sending the quality it last showed; the
    control moves to a fresh key, so that value has nowhere to land and
    cannot apply its preset over the Undo."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_animate").set_value(True).run()

    def grid() -> tuple:
        ss = at.session_state
        return ss["global_anim_grid_step_ms"], ss["global_anim_max_frames"]

    shown = _smoothness(at)
    assert shown.value == "Standard" and grid() == (100, 360)
    shown.set_value("Fine").run()
    assert grid() == (40, 900)
    echoed = _smoothness(at).key
    at.button(key="viz_undo").click().run()
    assert grid() == (100, 360)
    assert _smoothness(at).value == "Standard"
    assert _smoothness(at).key != echoed
    # On the next run the closed menu sends back what it last showed: the
    # quality under the key it knew, and 40 ms on the Frame interval slider,
    # whose own callback runs on that value. Neither is the user's change.
    at.session_state[echoed] = "Fine"
    at.slider(key="global_anim_grid_step_ms").set_value(40).run()
    assert not at.exception, at.exception
    assert grid() == (100, 360)
    assert _smoothness(at).value == "Standard"
    at.run()
    assert grid() == (100, 360)
    assert _smoothness(at).value == "Standard"
