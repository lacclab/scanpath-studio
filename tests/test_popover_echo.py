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

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

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
