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
