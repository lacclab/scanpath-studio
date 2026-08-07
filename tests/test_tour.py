"""Tests for the welcome tour + the dataset-setup guide spotlight card.

The setup guide is now a bottom-right floating card (``tour_mode == "wizard"``)
rather than a modal, so the user can follow along while filling in the wizard.
These exercise the arming + rendering + dismissal without booting the whole app.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _wizard_guide_app():
    from scanpath_studio.tour import (
        maybe_show_wizard_guide,
        render_spotlight_wizard_guide,
    )

    maybe_show_wizard_guide()
    render_spotlight_wizard_guide()


def _wizard_guide_replay_app():
    import streamlit as st

    from scanpath_studio.tour import _arm_wizard_guide, render_spotlight_wizard_guide

    # Simulate a session that already saw the guide, then a replay-button arm.
    st.session_state["wizard_guide_seen"] = True
    if not st.session_state.get("_armed_once"):
        st.session_state["_armed_once"] = True
        _arm_wizard_guide()
    render_spotlight_wizard_guide()


class TestWizardGuideSpotlight:
    def test_auto_arms_and_renders_card(self):
        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["tour_mode"] == "wizard"
        assert at.session_state["wizard_guide_seen"] is True
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_next" in keys
        assert "wizard_sp_back" in keys

    def test_skip_dismisses(self):
        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        at.button(key="wizard_sp_exit").click()
        at.run()
        assert at.session_state["tour_mode"] is None
        assert not any(b.key == "wizard_sp_next" for b in at.button)

    def test_last_step_shows_done(self):
        from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        at.session_state["wizard_guide_step"] = len(_WIZARD_GUIDE_STEPS) - 1
        at.run()
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_done" in keys

    def test_replay_button_re_arms_after_seen(self):
        at = AppTest.from_function(_wizard_guide_replay_app)
        at.run()
        assert at.session_state["tour_mode"] == "wizard"
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_next" in keys


def _welcome_tour_app():
    from scanpath_studio.tour import maybe_show_welcome_tour, render_spotlight_tour

    maybe_show_welcome_tour()
    render_spotlight_tour()


def _welcome_tour_replay_app():
    import streamlit as st

    from scanpath_studio.tour import _arm_tour, render_spotlight_tour

    st.session_state["tour_seen"] = True
    if not st.session_state.get("_armed_once"):
        st.session_state["_armed_once"] = True
        _arm_tour()
    render_spotlight_tour()


class TestTourOptOut:
    """UX-12: "Don't show this again", persisted in the ``sps_tour_optout`` cookie."""

    def test_checkbox_on_welcome_step_defaults_off(self):
        at = AppTest.from_function(_welcome_tour_app)
        at.run()
        assert not at.exception, at.exception
        box = at.checkbox(key="tour_dont_show")
        assert box.value is False

    def test_ticking_suppresses_a_later_session(self):
        at = AppTest.from_function(_welcome_tour_app)
        at.run()
        at.checkbox(key="tour_dont_show").check().run()
        # Within the session the checkbox state is authoritative, so the gates
        # that decide whether to auto-open the tour both close.
        from scanpath_studio import tour

        assert at.session_state["tour_dont_show"] is True
        # A fresh session whose browser sends the cookie back never opens it.
        assert tour._tour_optout_script(True).count("max-age=0") == 0
        assert "sps_tour_optout=1" in tour._tour_optout_script(True)
        assert "max-age=0" in tour._tour_optout_script(False)

    def test_replay_ignores_the_opt_out(self):
        """ "Don't show again" stops the greeting, it doesn't remove the tutorial."""
        at = AppTest.from_function(_welcome_tour_replay_app)
        at.run()
        assert at.session_state["tour_mode"] == "spotlight"
        assert any(b.key == "tour_sp_next" for b in at.button)

    def test_opted_out_is_false_without_a_request_context(self):
        """Bare-mode / headless imports have no cookies — must not raise."""
        from scanpath_studio.tour import tour_opted_out

        assert tour_opted_out() is False


def test_welcome_tour_text_is_concise():
    """Every welcome/spotlight/wizard step body stays short (UI/UX: no walls of
    text). Guards against the steps creeping back to multi-paragraph blurbs."""
    from scanpath_studio.tour import (
        _SPOTLIGHT_STEPS,
        _STEPS,
        _WIZARD_GUIDE_STEPS,
    )

    for _title, body in _STEPS:
        assert len(body) <= 240, f"welcome dialog step too long: {body!r}"
    for step in _SPOTLIGHT_STEPS:
        assert len(step["body"]) <= 240, f"spotlight step too long: {step['body']!r}"
    for _title, body in _WIZARD_GUIDE_STEPS:
        assert len(body) <= 280, f"wizard guide step too long: {body!r}"


# -----------------------------------------------------------------------------
# FAQ (UX-15)
# -----------------------------------------------------------------------------


def _faq_app():
    """Mirrors app.main's ordering: serve the dialog early, render the button late.

    The button only arms the dialog (``on_click``) so the modal doesn't wait on
    the heavy data/plot work it renders after — see ``tour.maybe_show_faq``.
    """
    from scanpath_studio.tour import maybe_show_faq, render_faq_button

    maybe_show_faq()
    render_faq_button()


class TestFaq:
    """The in-app FAQ dialog (UX-15) and its links out to the docs site."""

    def test_button_opens_a_dialog_with_every_item(self):
        from scanpath_studio.tour import _FAQ_ITEMS

        at = AppTest.from_function(_faq_app)
        at.run()
        assert any(b.key == "faq_open" for b in at.sidebar.button)
        assert not at.error

        at.sidebar.button(key="faq_open").click().run()
        assert not at.error
        assert len(at.expander) == len(_FAQ_ITEMS)

    def test_button_only_arms_the_dialog(self):
        """The click must set a flag, not open the dialog from its return value.

        The button renders at the bottom of ``app.main``; opening the dialog
        there made it wait out the whole rerun (~10 s of plot embeds). Rendering
        the button *alone* must therefore produce no dialog — the early
        ``maybe_show_faq`` call is what serves it.
        """

        def _button_only():
            from scanpath_studio.tour import render_faq_button

            render_faq_button()

        at = AppTest.from_function(_button_only)
        at.run()
        at.sidebar.button(key="faq_open").click().run()
        assert not at.error
        assert not at.expander, "the button opened the dialog itself"
        assert at.session_state["_faq_dialog_requested"] is True

    def test_docs_links_point_at_the_published_pages(self):
        """The FAQ is the app's help-context route into the docs — if these
        drift from the mkdocs nav the buttons 404."""
        from scanpath_studio.constants import CITATION
        from scanpath_studio.tour import DOCS_FAQ_URL, DOCS_TUTORIALS_URL

        assert DOCS_FAQ_URL == f"{CITATION['docs_url']}faq/"
        assert DOCS_TUTORIALS_URL == f"{CITATION['docs_url']}tutorials/"

    def test_answers_stay_short(self):
        """Same rule as the tour steps: the long version lives in docs/faq.md."""
        from scanpath_studio.tour import _FAQ_ITEMS

        assert _FAQ_ITEMS, "the FAQ must not be empty"
        for question, answer in _FAQ_ITEMS:
            assert question.endswith(("?", ".")), f"not a question: {question!r}"
            assert len(answer) <= 480, f"FAQ answer too long: {question!r}"


class TestSpotlightSelectorsResolve:
    """Every spotlight step must point at a container that actually exists.

    ``scanpath_studio/CLAUDE.md`` says to keep ``_SPOTLIGHT_STEPS`` in sync with
    the ``tour_grp_*`` wrappers, but nothing enforced it: a renamed or removed
    container leaves the step silently un-highlighted — the card still advances,
    it just points at nothing, which no other test would notice.
    """

    def _keyed_containers(self) -> set[str]:
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "scanpath_studio"
        source = "".join(
            (root / f"{module}.py").read_text()
            for module in ("tabs", "app", "controls", "annotations")
        )
        return set(re.findall(r'key="([\w]+)"', source))

    def test_every_selector_has_a_container(self):
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        keys = self._keyed_containers()
        missing = [
            step["selector"]
            for step in _SPOTLIGHT_STEPS
            if step.get("selector")
            and step["selector"].removeprefix(".st-key-") not in keys
        ]
        assert not missing, (
            "these tour steps point at containers that no longer exist — the step "
            f"will highlight nothing: {missing}"
        )

    def test_no_two_steps_spotlight_the_same_area(self):
        """UX-34: two steps sharing a selector lit up both areas at once.

        The "narrow the pool" and "pick a trial" steps both targeted the wrapper
        around *both* rows, so each highlighted the other's subject too.
        """
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        selectors = [s["selector"] for s in _SPOTLIGHT_STEPS if s.get("selector")]
        duplicates = {s for s in selectors if selectors.count(s) > 1}
        assert not duplicates, f"steps share a spotlight target: {duplicates}"
