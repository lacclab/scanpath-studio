"""The Scanpath view says when trial filters narrow its pool, and undoes them."""

from __future__ import annotations

import pytest

from scanpath_studio.constants import md_literal
from scanpath_studio.tabs import _funnel_state_css
from tests.conftest import APP_SCRIPT, pin_view

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _scope(at) -> list[str]:
    return [c.value for c in at.caption if "**Filtered:**" in c.value]


def test_funnel_css_marks_only_an_active_filter():
    assert "iconpop_filter_trials" in _funnel_state_css(True)
    assert "::after" in _funnel_state_css(True)
    # Still a style block when off, so the funnel's cell keeps its elements.
    assert _funnel_state_css(False) == "<style></style>"


@pytest.mark.timeout(240)
def test_scanpath_view_names_active_filters_and_clears_them():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    pin_view(at, "Scanpath")
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert not _scope(at)
    assert "trial_filter_scope_clear" not in {b.key for b in at.button}

    # Through the widget, whose callback publishes the filter for this run.
    at.multiselect(key="filter_participants").set_value(["l7_183"]).run(timeout=90)
    assert not at.exception, at.exception
    (line,) = _scope(at)
    assert "12 of 24 trials" in line
    assert md_literal("Participant: l7_183") in line

    at.button(key="trial_filter_scope_clear").click()
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert not _scope(at)
    assert at.session_state["_trial_filters"]["participants"] is None


@pytest.mark.timeout(240)
def test_empty_annotations_open_the_scanpath_annotations_subtab():
    from scanpath_studio.constants import (
        _VIEW_SCANPATH,
        DATA_INSPECTION_KEY,
        SUBTAB_ANNOTATIONS,
    )
    from tests.conftest import pin_data_view

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    pin_data_view(at)
    at.session_state[DATA_INSPECTION_KEY] = "Annotations"
    at.run(timeout=90)
    assert not at.exception, at.exception
    at.button(key="annotations_empty_open").click().run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state["main_nav"] == _VIEW_SCANPATH
    assert at.session_state["single_subtab"] == SUBTAB_ANNOTATIONS


def _held_clear_app():
    """A filter multiselect, its clear-from-outside button, and the hold."""
    import streamlit as st

    from scanpath_studio import controls

    # In this order, as a widget callback runs before the script's reassert.
    st.session_state["_echo_seen"] = controls._echoes_cleared_filter("")
    controls.reassert_pending_writes()
    st.multiselect("Level", ["Adv", "Ele"], default=["Adv", "Ele"], key="filter_lvl")
    controls.hold_cleared_filters()
    st.button("Clear", key="clear", on_click=controls.clear_trial_filters_from_outside)


def test_a_reset_from_outside_the_funnel_is_held_against_the_echo():
    """The browser echoes a closed popover's last value; the reset outlives it.

    The echo is simulated by writing the old value back, as the browser sends
    it with the next rerun."""
    from scanpath_studio.controls import _PENDING_WRITES_KEY

    at = streamlit_testing.AppTest.from_function(_held_clear_app).run()
    at.multiselect(key="filter_lvl").set_value(["Adv"]).run()
    at.button(key="clear").click().run()
    assert at.multiselect(key="filter_lvl").value == ["Adv", "Ele"]
    assert "filter_lvl" in at.session_state[_PENDING_WRITES_KEY]

    at.session_state["filter_lvl"] = ["Adv"]  # the closed popover's echo
    at.run()
    assert at.session_state["_echo_seen"] is True
    assert at.multiselect(key="filter_lvl").value == ["Adv", "Ele"]
