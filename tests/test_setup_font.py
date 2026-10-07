"""Recording setup's *Font* question: which typeface the text was shown in.

The word labels are drawn in the dataset's font. Asked beside the screen, the
physical size and the text size, on the add wizard and on ✏️ Edit dataset alike
(one step, `wizard._wizard_setup_step`). "I don't know" is an answer — a generic
monospace, as before — so the question never holds up *Add dataset*.
"""

from __future__ import annotations

import pytest

from scanpath_studio.constants import FONT_FAMILY
from scanpath_studio.wizard import stimulus_font_css, stimulus_font_name

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


class TestTheFontValue:
    def test_a_listed_font_falls_back_to_its_own_family(self):
        assert stimulus_font_css("Courier New") == "'Courier New', monospace"
        assert stimulus_font_css("Times New Roman") == "'Times New Roman', serif"
        assert stimulus_font_css("Arial") == "'Arial', sans-serif"

    def test_an_unlisted_font_falls_back_to_monospace(self):
        assert stimulus_font_css("Source Code Pro") == "'Source Code Pro', monospace"

    def test_nothing_named_is_the_generic_font(self):
        assert stimulus_font_css("") == FONT_FAMILY
        assert stimulus_font_css("monospace") == FONT_FAMILY

    @pytest.mark.parametrize(
        ("css", "name"),
        [
            ("'Courier New', monospace", "Courier New"),
            ('"Consolas", monospace', "Consolas"),
            ("monospace", None),
            ("", None),
            (None, None),
        ],
    )
    def test_the_name_is_read_back(self, css, name):
        assert stimulus_font_name(css) == name


def _setup_app():
    import streamlit as st

    from scanpath_studio.wizard import _wizard_setup_step

    snapshot = _wizard_setup_step(
        st.container(), None, None, True, estimate=lambda: (1920, 1080)
    )
    st.session_state["_font"] = snapshot.font_family


def _run(**state):
    at = AppTest.from_function(_setup_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


def test_it_starts_on_i_dont_know_and_draws_the_generic_font():
    at = _run()
    assert at.session_state["_font"] == FONT_FAMILY
    assert at.session_state["global_font_family"] == FONT_FAMILY


def test_a_known_font_is_the_labels_font():
    at = _run(
        wizard_setup_font_mode="I know the font",
        wizard_setup_font_name="Courier New",
    )
    assert at.session_state["_font"] == "'Courier New', monospace"
    assert at.session_state["global_font_family"] == "'Courier New', monospace"


def test_another_font_can_be_typed():
    at = _run(
        wizard_setup_font_mode="I know the font",
        wizard_setup_font_name="Other…",
        wizard_setup_font_other="Source Code Pro",
    )
    assert at.session_state["_font"] == "'Source Code Pro', monospace"


def test_the_font_does_not_depend_on_the_text_size_answer():
    """Scaling to the word boxes and a known font go together."""
    at = _run(
        wizard_setup_text_mode="Scale to the word boxes",
        wizard_setup_font_mode="I know the font",
        wizard_setup_font_name="Consolas",
    )
    assert at.session_state["_font"] == "'Consolas', monospace"
    assert at.session_state["global_scale_text_to_boxes"] is True
