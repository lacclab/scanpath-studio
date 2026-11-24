"""A closed popover's echo cannot undo a change made outside it.

A widget inside a popover is mounted only while the popover is open. Once it
has been open, the browser sends back the value it last showed on every rerun,
and Streamlit runs the widget's callback whenever that differs from what the
server last wrote. A control that shows a value derived from another key is
drawn as a shadow (`controls.shadow_widget_key`): when the value changes
without it, the control moves to a fresh key, and the value the browser
remembers has nowhere to land. Each test changes the value outside the
control, then sends the old value back under the key the browser knew.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.session_keys import PLOT_CONFIG_SCHEMA_VERSION
from tests.conftest import APP_SCRIPT

STYLE = "global_critical_span_style"


def _shadow(widgets, stem: str):
    """The widget drawn under a shadow key with this stem."""
    return next(w for w in widgets if w.key.startswith(f"_{stem}__w"))


@pytest.mark.timeout(180)
def test_an_undone_word_highlight_holds_against_the_closed_menus_echo():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    assert at.session_state[STYLE] == "None"
    switch = _shadow(at.checkbox, "highlight_span_on")
    assert switch.value is False and not switch.disabled
    switch.check().run()
    assert at.session_state[STYLE] == "Mark text"
    _shadow(at.radio, "highlight_span_mode").set_value("Underline").run()
    assert at.session_state[STYLE] == "Underline"
    shown_on = _shadow(at.checkbox, "highlight_span_on").key
    shown_style = _shadow(at.radio, "highlight_span_mode").key

    at.button(key="viz_undo").click().run()
    at.button(key="viz_undo").click().run()
    assert at.session_state[STYLE] == "None"
    assert _shadow(at.checkbox, "highlight_span_on").value is False
    # The next run brings back what the closed menu last showed: the switch
    # on and Underline, under the keys the browser knew.
    at.session_state[shown_on] = True
    at.session_state[shown_style] = "Underline"
    at.run()
    at.run()
    assert not at.exception, at.exception
    assert at.session_state[STYLE] == "None"
    assert _shadow(at.checkbox, "highlight_span_on").value is False


@pytest.mark.timeout(180)
@pytest.mark.parametrize("change", ["view tile", "reset"])
def test_one_click_turns_the_highlight_on_after_a_design_change(change):
    """A view tile or Reset sets the highlight off without its controls. No
    widget sits on the style any more, so nothing echoes it and nothing holds
    it: the next click on the switch turns the highlight on."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    _shadow(at.checkbox, "highlight_span_on").check().run()
    _shadow(at.radio, "highlight_span_mode").set_value("Underline").run()
    assert at.session_state[STYLE] == "Underline"
    if change == "view tile":
        at.button(key="viz_view_heatmap").click().run()
    else:
        at.button(key="reset_viz_settings_btn").click().run()
        at.button(key="reset_viz_confirm").click().run()
    assert at.session_state[STYLE] == "None"
    # The click is the very next run, as in the browser.
    _shadow(at.checkbox, "highlight_span_on").check().run()
    assert not at.exception, at.exception
    expected = "Underline" if change == "view tile" else "Mark text"
    assert at.session_state[STYLE] == expected


@pytest.mark.timeout(180)
def test_the_style_chosen_while_on_is_kept_while_off():
    """Switching the highlight off and on again keeps its style."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    _shadow(at.checkbox, "highlight_span_on").check().run()
    _shadow(at.radio, "highlight_span_mode").set_value("Mark border").run()
    _shadow(at.checkbox, "highlight_span_on").uncheck().run()
    assert at.session_state[STYLE] == "None"
    assert _shadow(at.radio, "highlight_span_mode").value == "Mark border"
    _shadow(at.checkbox, "highlight_span_on").check().run()
    assert at.session_state[STYLE] == "Mark border"


@pytest.mark.timeout(180)
def test_a_palette_restored_elsewhere_holds_against_the_corpus_menus_echo():
    from scanpath_studio import controls
    from scanpath_studio.constants import _VIEW_CORPUS
    from tests.conftest import pin_view

    picked, restored = list(controls.PALETTES)[1:3]
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    pin_view(at, _VIEW_CORPUS)
    at.run()
    _shadow(at.selectbox, "corpus_palette").set_value(picked).run()
    at.run()  # the open menu's colour pickers take the palette's colours
    assert at.session_state["global_palette"] == picked
    echoed = _shadow(at.selectbox, "corpus_palette").key
    # A settings file restores another palette's colours.
    for key, value in controls.palette_state(restored, include_compare=True).items():
        at.session_state[key] = value
    at.run()
    assert at.session_state["global_palette"] == restored
    # The closed Figure style menu sends back the palette it last showed.
    at.session_state[echoed] = picked
    at.run()
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["global_palette"] == restored
    assert _shadow(at.selectbox, "corpus_palette").value == restored


def test_a_dataset_switch_reseeds_the_stimulus_fields_against_the_menus_echo(
    monkeypatch,
):
    """A dataset with other columns gets its own highlighted spans and context
    fields, though the closed ⚙ Fields menu keeps sending the last dataset's."""
    from scanpath_studio import controls, tabs

    state: dict = {}
    monkeypatch.setattr(tabs.st, "session_state", state)
    first = pd.DataFrame(
        {"word": ["a", "b"], "is_target": [True, False], "question": ["q", "q"]}
    )
    second = pd.DataFrame(
        {"word": ["a", "b"], "in_span": [False, True], "answer": ["x", "x"]}
    )
    spans, qa, *_ = tabs._stimulus_fields(first)
    assert (spans, qa) == (["is_target"], ["question"])
    # The next run: the user had the menu open; the dataset changes.
    controls.reassert_pending_writes()
    spans, qa, *_ = tabs._stimulus_fields(second)
    assert (spans, qa) == (["in_span"], ["answer"])
    # The run after: the closed menu sends the first dataset's columns back.
    state[tabs._STIMULUS_SPAN_KEY] = ["is_target"]
    state[tabs._STIMULUS_QA_KEY] = ["question"]
    controls.reassert_pending_writes()
    spans, qa, *_ = tabs._stimulus_fields(second)
    assert (spans, qa) == (["in_span"], ["answer"])


def test_a_script_write_over_a_held_value_holds_against_the_older_echo(
    monkeypatch,
):
    """A view tile holds two values; before the browser answers, a settings
    file changes one and leaves the other. The closed menus still send back
    what they showed before the tile, so both must hold against that."""
    from scanpath_studio import controls

    state: dict = {
        "global_saccade_style": "Solid",
        "global_order_label_position": "top",
    }
    monkeypatch.setattr(controls.st, "session_state", state)
    # The tile's callback.
    controls.write_through("global_saccade_style", "Dashed")
    controls.write_through("global_order_label_position", "below")
    controls.reassert_pending_writes()
    # The next run: the closed menus echo, the hold puts the tile back, and a
    # settings file then changes the style alone.
    state["global_saccade_style"] = "Solid"
    state["global_order_label_position"] = "top"
    controls.reassert_pending_writes()
    before = controls.design_state()
    state["global_saccade_style"] = "Dotted"
    controls.hold_script_writes(before)
    # The run after: the menus echo what they showed before the tile.
    state["global_saccade_style"] = "Solid"
    state["global_order_label_position"] = "top"
    controls.reassert_pending_writes()
    assert state["global_saccade_style"] == "Dotted"
    assert state["global_order_label_position"] == "below"


@pytest.mark.timeout(180)
def test_a_datasets_text_sizing_holds_against_the_text_menus_echo():
    """Switching to an added dataset puts its own text sizing on the figure,
    in the script; the closed Text menu then sends back what it showed for the
    dataset before, and must not undo it."""
    from scanpath_studio.experimental_setup import SetupSnapshot
    from scanpath_studio.synthetic import make_multipart_synthetic_data

    keys = (
        "global_base_font_size",
        "global_line_spacing",
        "global_scale_text_to_boxes",
    )
    words, fixations = make_multipart_synthetic_data()
    sized = SetupSnapshot().to_dict() | {
        "base_font_size": 31,
        "line_spacing": 2.5,
        "scale_text_to_boxes": False,
    }
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {
        "Sized": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
            "setup": sized,
        }
    }
    at.run()
    shown = {key: at.session_state[key] for key in keys}
    assert shown == {
        "global_base_font_size": 16,
        "global_line_spacing": 3.0,
        "global_scale_text_to_boxes": True,
    }
    at.session_state["_pending_source_choice"] = "Sized"
    at.run()
    expected = {
        "global_base_font_size": 31,
        "global_line_spacing": 2.5,
        "global_scale_text_to_boxes": False,
    }
    assert {key: at.session_state[key] for key in keys} == expected
    for key, value in shown.items():
        at.session_state[key] = value
    at.run()
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["data_source_choice"] == "Sized"
    assert {key: at.session_state[key] for key in keys} == expected


class _SettingsFile:
    """What `st.file_uploader` holds after Share → File: bytes and an id."""

    def __init__(self, config: dict):
        self._data = json.dumps(config).encode("utf-8")
        self.name = "scanpath_studio_settings.json"
        self.size = len(self._data)
        self.file_id = "settings-1"

    def getvalue(self) -> bytes:
        return self._data


@pytest.mark.timeout(180)
@pytest.mark.parametrize("staged", [False, True], ids=["plain", "preprocessing"])
def test_a_settings_file_holds_against_a_closed_menus_echo(staged, monkeypatch):
    """A settings file writes the rail's values in the script, before the
    widgets draw. A menu the user had open sends back the value it last showed
    on the next run, and must not undo the file. With preprocessing settings
    staged (an experimental panel), the restore runs the script once more
    before the browser answers."""
    if staged:
        monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    assert at.session_state["global_saccade_style"] == "Solid"
    width = at.session_state["global_saccade_width"]
    config = {
        "schema": PLOT_CONFIG_SCHEMA_VERSION,
        "coloring": {"saccade_style": "Dashed", "saccade_width": width + 2},
    }
    if staged:
        config["preprocessing"] = {"short_policy": "Merge"}
    at.session_state["plot_config_upload"] = _SettingsFile(config)
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["global_saccade_style"] == "Dashed"
    if staged:
        assert at.session_state["global_preproc_short_policy"] == "Merge"
    # The next run brings back what the closed Saccades menu last showed.
    at.session_state["global_saccade_style"] = "Solid"
    at.session_state["global_saccade_width"] = width
    at.run()
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["global_saccade_style"] == "Dashed"
    assert at.session_state["global_saccade_width"] == width + 2
