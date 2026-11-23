"""The primary figure controls and their detailed settings edit the same figure."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from scanpath_studio.constants import _VIEW_CORPUS
from tests.conftest import APP_SCRIPT, pin_view


def _details(at, label):
    return next(panel for panel in at.expander if panel.label == label)


def test_choose_axis_fields_and_restore_grid_spacing():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.checkbox(key="global_show_coordinate_grid").check().run()
    grid = _details(at, "Grid spacing and labels")
    grid.checkbox(key="global_coordinate_grid_auto").uncheck().run()
    at.number_input(key="global_coordinate_grid_spacing").set_value(180.0).run()

    fields = _details(at, "Choose axis fields")
    fields.selectbox(key="global_x_field").set_value("duration_ms").run()
    assert not at.exception
    assert at.selectbox(key="_plot_axis_preset").value is None
    assert at.session_state[SNIPPET_STATE_KEY].settings["x_field"] == "duration_ms"
    assert at.number_input(key="global_coordinate_grid_spacing").disabled

    at.selectbox(key="_plot_axis_preset").set_value("Screen X and Y").run()
    spacing = at.number_input(key="global_coordinate_grid_spacing")
    assert not spacing.disabled and spacing.value == 180.0


def test_title_and_legend_keep_their_styles_while_hidden():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.checkbox(key="global_show_title").check().run()
    at.text_input(key="global_title_pattern").set_value("Reading {trial_id}").run()
    appearance = _details(at, "Text size and color")
    appearance.number_input(key="global_title_font_size").set_value(32).run()
    assert at.session_state[SNIPPET_STATE_KEY].title.startswith("Reading ")
    assert at.session_state[SNIPPET_STATE_KEY].settings["title_font_size"] == 32
    at.checkbox(key="global_show_title").uncheck().run()
    assert at.number_input(key="global_title_font_size").disabled
    assert at.text_input(key="global_title_pattern").value == "Reading {trial_id}"

    at.checkbox(key="global_duration_size_legend").check().run()
    placement = _details(at, "Legend position and style")
    position_key = "global_legend_size_key_position"
    placement.selectbox(key=position_key).set_value("bottom-left-inside").run()
    at.checkbox(key="global_duration_size_legend").uncheck().run()
    assert at.selectbox(key=position_key).disabled
    at.button(key="viz_undo").click().run()
    assert not at.exception
    position = at.selectbox(key=position_key)
    assert not position.disabled and position.value == "bottom-left-inside"


def test_screen_background_is_available_without_stimulus_text():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.checkbox(key="global_show_labels").uncheck().run()
    at.selectbox(key="_plot_axis_preset").set_value("Duration by fixation index").run()
    screen = next(menu for menu in at.get("popover") if menu.key == "plot_menu_screen")
    background = screen.selectbox(key="global_bg_choice")
    assert not background.disabled
    background.set_value("Black").run()
    assert not at.exception
    assert at.session_state[SNIPPET_STATE_KEY].settings["background_color"] == "#000000"
    pin_view(at, _VIEW_CORPUS)
    at.run()
    assert not at.exception
    assert at.selectbox(key="global_bg_choice").value == "Black"
