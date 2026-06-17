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
