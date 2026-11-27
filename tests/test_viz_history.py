"""Undo and redo through the same controls a reader uses."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from tests.conftest import APP_SCRIPT


def _click(at, key):
    button = at.button(key=key)
    assert not button.disabled, key
    button.click().run()
    assert not at.exception


def _axis_pair(at):
    return tuple(at.selectbox(key=f"global_{axis}_field").value for axis in ("x", "y"))


@pytest.mark.parametrize(
    ("menu", "browser_title", "expected"),
    [
        pytest.param("grid", True, False, id="closed-title-menu-echo"),
        pytest.param("labels", False, False, id="reopen-without-editing"),
        pytest.param("labels", True, True, id="reopen-and-edit-together"),
    ],
)
def test_title_edit_on_the_same_rerun_as_opening_a_menu(menu, browser_title, expected):
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.query_params["source"] = "synthetic"
    at.run()
    at.checkbox(key="global_show_title").check().run()
    pattern = at.text_input(key="global_title_pattern").value
    title = at.session_state[SNIPPET_STATE_KEY].title
    assert pattern and title
    _click(at, "viz_undo")
    assert not at.checkbox(key="global_show_title").value

    # Streamlit can combine a menu opening and the next click into one
    # rerun. A closed checkbox can send its old value on that same message.
    at.session_state[f"plot_menu_{menu}"] = True
    at.checkbox(key="global_show_title").set_value(browser_title).run()
    assert not at.exception
    assert at.checkbox(key="global_show_title").value is expected
    assert at.text_input(key="global_title_pattern").value == (
        pattern if expected else ""
    )
    assert at.session_state[SNIPPET_STATE_KEY].title == (title if expected else "")


@pytest.mark.parametrize(
    ("menu", "accepted"),
    [
        pytest.param("stim", True, id="open-text-menu-and-edit-together"),
        pytest.param("grid", False, id="closed-text-menu-echo"),
    ],
)
def test_font_size_edit_on_the_same_rerun_as_opening_its_menu(menu, accepted):
    """The text rows are drawn into Stimulus → Text after that menu's own rows,
    and opening it still releases the value Undo put back."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    before = at.number_input(key="global_base_font_size").value
    at.number_input(key="global_base_font_size").set_value(before + 4).run()
    _click(at, "viz_undo")
    assert at.number_input(key="global_base_font_size").value == before

    at.session_state[f"plot_menu_{menu}"] = True
    at.number_input(key="global_base_font_size").set_value(before + 4).run()
    assert not at.exception
    expected = before + 4 if accepted else before
    assert at.number_input(key="global_base_font_size").value == expected
    assert at.session_state["global_base_font_size"] == expected


def test_undo_names_the_restored_value_after_navigating_to_another_trial():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.checkbox(key="global_show_order").check().run()
    _click(at, "single_next_trial")
    held = at.selectbox(key="single_trial_id").value
    undo = at.button(key="viz_undo")
    assert "Undo fixation index labels change, restore off" in undo.label
    assert "restore off" in undo.proto.help
    _click(at, "viz_undo")
    assert (
        "Redo fixation index labels change, restore on"
        in at.button(key="viz_redo").label
    )
    assert held == at.selectbox(key="single_trial_id").value


def test_presets_reset_and_edits_round_trip_on_the_current_trial():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    assert at.button(key="viz_undo").disabled and at.button(key="viz_redo").disabled
    initial_trial = at.selectbox(key="single_trial_id").value
    preset = next(s for s in at.selectbox if s.label == "Axis layout")
    preset.set_value("Elapsed time by fixation index").run()
    custom = ("order_in_trial", "@elapsed_seconds")
    assert _axis_pair(at) == custom
    at.checkbox(key="global_show_order").check().run()
    _click(at, "viz_view_heatmap")
    _click(at, "reset_viz_settings_btn")
    _click(at, "reset_viz_confirm")
    assert at.button(key="viz_view_scanpath").proto.type == "primary"
    _click(at, "viz_undo")
    assert at.button(key="viz_view_heatmap").proto.type == "primary"
    _click(at, "viz_undo")
    assert _axis_pair(at) == custom and at.checkbox(key="global_show_order").value
    for mode in ("essentials", "full"):
        at.segmented_control(key="ui_mode_switch").set_value(mode).run()
    _click(at, "single_next_trial")
    other = at.selectbox(key="single_trial_id").value
    assert other != initial_trial
    _click(at, "viz_redo")
    assert at.button(key="viz_view_heatmap").proto.type == "primary"
    _click(at, "viz_redo")
    assert at.button(key="viz_view_scanpath").proto.type == "primary"
    assert at.selectbox(key="single_trial_id").value == other
    assert at.button(key="viz_redo").disabled

    _click(at, "viz_undo")
    _click(at, "viz_view_illustration")
    assert at.button(key="viz_redo").disabled
    _click(at, "viz_undo")
    _click(at, "viz_undo")
    _click(at, "viz_undo")
    assert not at.checkbox(key="global_show_order").value and _axis_pair(at) == custom
    _click(at, "viz_undo")
    assert at.button(key="viz_undo").disabled and _axis_pair(at) == ("x", "y")


def test_navigating_trials_drops_only_the_local_fixation_window_edit():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    # The Paragraph screen has room for an eight-fixation window. Its
    # fixations are numbered after the earlier screens' in the reading.
    at.query_params["screen"] = "Paragraph"
    at.run()
    at.checkbox(key="global_show_order").check().run()
    window = next(s for s in at.slider if s.label == "Fixation index range")
    picked = (window.min + 4, window.min + 11)
    window.set_range(*picked).run()
    _click(at, "viz_undo")
    assert not at.session_state["single_fix_range_user_set"]
    _click(at, "viz_redo")
    assert tuple(at.session_state["single_fix_range"]) == picked
    _click(at, "single_next_trial")
    _click(at, "viz_undo")
    assert not at.checkbox(key="global_show_order").value
    assert not at.session_state["single_fix_range_user_set"]
    assert at.button(key="viz_undo").disabled


def test_compare_and_animate_accept_an_edit_immediately_after_undo():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    at.checkbox(key="global_show_order").check().run()
    _click(at, "viz_undo")
    assert at.toggle(key="single_compare_toggle").value
    assert not at.checkbox(key="global_show_order").value
    _click(at, "viz_undo")
    at.toggle(key="single_animate").set_value(True).run()
    _click(at, "viz_undo")
    at.toggle(key="single_animate").set_value(True).run()
    assert at.session_state["single_animate"] and at.button(key="viz_redo").disabled


def test_linked_axes_and_window_survive_undo_and_a_reset_round_trip():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    # The window lies within the eight fixations of the first reading's
    # title screen.
    at.query_params.update(
        x_field="order_in_trial",
        y_field="@elapsed_seconds",
        fix_range="2,6",
        screen="Title",
    )
    at.run()
    link = dict(at.query_params)
    at.checkbox(key="global_show_order").check().run()
    _click(at, "viz_undo")
    assert dict(at.query_params) == link
    _click(at, "reset_viz_settings_btn")
    _click(at, "reset_viz_confirm")
    assert "x_field" not in at.query_params
    _click(at, "viz_undo")
    assert dict(at.query_params) == link
    assert tuple(at.session_state["single_fix_range"]) == (2, 6)
    _click(at, "viz_redo")
    assert "x_field" not in at.query_params
    assert _axis_pair(at) == ("x", "y")


def test_redo_then_custom_cannot_bring_a_local_window_to_another_reading():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.checkbox(key="global_show_order").check().run()
    next(s for s in at.slider if s.label == "Fixation index range").set_range(
        5, 12
    ).run()
    _click(at, "viz_view_heatmap")
    _click(at, "single_next_trial")
    _click(at, "viz_undo")
    _click(at, "viz_redo")
    _click(at, "viz_view_custom")
    assert not at.session_state["single_fix_range_user_set"]


def test_switching_comparison_readers_discards_bs_old_window():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    next(s for s in at.slider if s.label == "B fixation index range").set_range(
        3, 8
    ).run()
    picker = at.selectbox(key="single_compare_trial")
    previous = picker.value
    picker.select_index((picker.index + 1) % len(picker.options)).run()
    other = at.selectbox(key="single_compare_trial").value
    assert previous != other
    _click(at, "viz_undo")
    assert not at.toggle(key="single_compare_toggle").value
    _click(at, "viz_redo")
    assert at.selectbox(key="single_compare_trial").value == other
    assert not at.session_state["single_compare_fix_range_user_set"]


def test_new_dataset_starts_with_empty_history():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    _click(at, "viz_view_illustration")
    assert not at.button(key="viz_undo").disabled
    picker = at.selectbox(key="data_source_picker")
    picker.select_index(
        next(i for i, label in enumerate(picker.options) if "Hand-drawn" in label)
    ).run()
    assert not at.exception
    assert at.button(key="viz_undo").disabled and at.button(key="viz_redo").disabled


def test_renaming_an_upload_preserves_undo_and_redo(monkeypatch):
    from scanpath_studio import controls
    from scanpath_studio.constants import DATASET_ALIASES_KEY
    from scanpath_studio.dataset_identity import forget_dataset_identity

    state = {
        "_datasets": {"local-key": {}},
        "data_source_choice": "local-key",
        DATASET_ALIASES_KEY: {"local-key": "First name"},
        "global_show_order": False,
    }
    monkeypatch.setattr(controls.st, "session_state", state)
    monkeypatch.setattr(controls.st, "query_params", {})
    controls._record_plot_edit()
    state["global_show_order"] = True
    controls._record_plot_edit()
    state[DATASET_ALIASES_KEY]["local-key"] = "New name"
    controls._record_plot_edit()
    controls._step_plot_history(redo=False)
    assert state["global_show_order"] is False
    controls._step_plot_history(redo=True)
    assert state["global_show_order"] is True
    # Remove the upload and import a replacement under the same key and label.
    forget_dataset_identity(state, "local-key")
    state["_datasets"]["local-key"] = {}
    state[DATASET_ALIASES_KEY]["local-key"] = "New name"
    assert not controls._record_plot_edit().past


def test_enabling_all_trials_does_not_make_past_local_edits_global():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()

    def window():
        return next(s for s in at.slider if s.label == "Fixation index range")

    window().set_range(5, 12).run()
    window().set_range(1, window().max).run()
    at.checkbox(key="single_fix_range_all_trials").check().run()
    _click(at, "single_next_trial")
    _click(at, "viz_undo")
    assert not at.checkbox(key="single_fix_range_all_trials").value
    assert tuple(at.session_state["single_fix_range"]) != (5, 12)
    assert at.button(key="viz_undo").disabled
