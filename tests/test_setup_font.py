"""Recording setup's *Font* question: which typeface the text was shown in.

The word labels are drawn in the dataset's font. Asked beside the screen, the
physical size and the text size, on the add wizard and on ✏️ Edit dataset alike
(one step, `wizard._wizard_setup_step`). "I don't know" is an answer — a generic
monospace, as before — so the question never holds up *Add dataset*.
"""

from __future__ import annotations

import pytest

from scanpath_studio.constants import FONT_FAMILY
from scanpath_studio.experimental_setup import stimulus_font_css, stimulus_font_name

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


# --- #422: one vocabulary for the Recording setup and 📄 Stimulus → Text -------


class TestSharedFontVocabulary:
    def test_a_css_stack_is_kept_as_typed(self):
        assert stimulus_font_css("'Fira Code', serif") == "'Fira Code', serif"

    @pytest.mark.parametrize(
        ("css", "choice"),
        [
            ("monospace", "Generic monospace"),
            ("", "Generic monospace"),
            ("'Courier New', monospace", "Courier New"),
            ("'Source Code Pro', monospace", "Other…"),
            ("Arial", "Other…"),
        ],
    )
    def test_a_font_maps_back_to_its_choice(self, css, choice):
        from scanpath_studio.experimental_setup import font_choice

        assert font_choice(css) == choice

    def test_every_choice_round_trips(self):
        from scanpath_studio.experimental_setup import (
            FONT_CHOICES,
            OTHER_FONT,
            font_choice,
            font_choice_css,
        )

        for choice in FONT_CHOICES:
            if choice != OTHER_FONT:
                assert font_choice(font_choice_css(choice)) == choice

    def test_the_typed_box_shows_a_name_or_the_stack(self):
        from scanpath_studio.experimental_setup import font_other_text

        assert font_other_text("'Source Code Pro', monospace") == "Source Code Pro"
        assert font_other_text("Fira, serif") == "Fira, serif"
        assert font_other_text("monospace") == ""

    def test_a_point_size_converts_or_reads_as_pixels(self):
        from scanpath_studio.experimental_setup import font_size_px

        assert font_size_px(12, "pt", 96.0) == 16
        assert font_size_px(12, "pt", None) == 12  # no physical size
        assert font_size_px(20, "px", 96.0) == 20
        assert font_size_px(500, "px", None) == 72  # clamped

    def test_both_screens_offer_the_same_fonts(self):
        """The add / edit screens list the rail's fonts, less the generic one,
        which is their *Not sure*."""
        from scanpath_studio.experimental_setup import FONT_CHOICES, GENERIC_FONT
        from scanpath_studio.wizard import _KNOWN_FONT_CHOICES

        assert [GENERIC_FONT, *_KNOWN_FONT_CHOICES] == list(FONT_CHOICES)


def test_the_multilingual_stack_is_a_known_font():
    from scanpath_studio.experimental_setup import (
        MULTILINGUAL_FONT,
        MULTILINGUAL_FONT_STACK,
    )

    at = _run(
        wizard_setup_font_mode="I know the font",
        wizard_setup_font_name=MULTILINGUAL_FONT,
    )
    assert at.session_state["_font"] == MULTILINGUAL_FONT_STACK


def test_a_size_can_be_given_in_pixels():
    at = _run(
        wizard_setup_text_mode="I know the font size",
        wizard_setup_font_unit="px",
        wizard_setup_font_px=20,
    )
    assert at.session_state["global_base_font_size"] == 20
    assert at.session_state["global_scale_text_to_boxes"] is False


def test_a_point_size_is_read_as_pixels_without_a_physical_size():
    at = _run(
        wizard_setup_text_mode="I know the font size",
        wizard_setup_font_unit="pt",
        wizard_setup_font_pt=14.0,
    )
    # Physical size starts Off: there is no DPI to convert through.
    assert at.session_state["global_base_font_size"] == 14


def test_fit_to_word_boxes_records_its_line_spacing():
    at = _run(
        wizard_setup_text_mode="Scale to the word boxes",
        wizard_setup_line_spacing=1.5,
    )
    assert at.session_state["global_line_spacing"] == 1.5
    assert at.session_state["global_scale_text_to_boxes"] is True


def test_a_setup_size_turns_the_figures_point_size_off():
    """Left on, the figure's point size would replace the dataset's px size."""
    at = _run(
        global_use_stimulus_font_pt=True,
        wizard_setup_text_mode="I know the font size",
        wizard_setup_font_unit="px",
        wizard_setup_font_px=22,
    )
    assert at.session_state["global_use_stimulus_font_pt"] is False
    assert at.session_state["global_base_font_size"] == 22


# --- the rail's Font row -------------------------------------------------------


def _rail_font_app():
    import streamlit as st

    from scanpath_studio.app import _font_rows

    st.session_state.setdefault("global_font_family", "monospace")
    a, b = st.columns(2)
    _font_rows(a, b, disabled=False)


def _run_rail(**state) -> AppTest:
    at = AppTest.from_function(_rail_font_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


def test_the_rail_lists_the_setup_fonts_and_shows_the_one_in_use():
    from scanpath_studio.experimental_setup import FONT_CHOICES

    at = _run_rail(global_font_family="'Georgia', serif")
    assert list(at.selectbox[0].options) == list(FONT_CHOICES)
    assert at.selectbox[0].value == "Georgia"
    assert at.text_input[0].disabled  # greyed unless Other…


def test_picking_a_font_in_the_rail_sets_the_figures_font():
    at = _run_rail()
    at.selectbox[0].set_value("Courier New").run(timeout=30)
    assert at.session_state["global_font_family"] == "'Courier New', monospace"


def test_other_in_the_rail_takes_a_typed_font():
    at = _run_rail(global_font_family="'Courier New', monospace")
    at.selectbox[0].set_value("Other…").run(timeout=30)
    assert at.selectbox[0].value == "Other…"
    assert not at.text_input[0].disabled
    # The font in use is filled in, ready to edit.
    assert at.text_input[0].value == "Courier New"
    at.text_input[0].set_value("Source Code Pro").run(timeout=30)
    assert at.session_state["global_font_family"] == "'Source Code Pro', monospace"
    assert at.selectbox[0].value == "Other…"


def test_a_font_set_elsewhere_moves_the_rail():
    at = _run_rail(global_font_family="'Courier New', monospace")
    at.session_state["global_font_family"] = "'Arial', sans-serif"
    at.run(timeout=30)
    assert at.selectbox[0].value == "Arial"
