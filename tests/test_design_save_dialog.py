"""My designs → 💾: the dialog that names the settings on screen (VIZ-39, #422)."""

from __future__ import annotations

import pytest

from scanpath_studio import controls

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _designs_app() -> None:
    import streamlit as st

    from scanpath_studio import controls

    controls._render_saved_designs(st.container())


def _open_dialog(designs: dict | None = None):
    at = AppTest.from_function(_designs_app, default_timeout=30)
    if designs is not None:
        at.session_state[controls.DESIGN_PRESETS_KEY] = designs
    at.session_state[controls._DESIGN_SAVE_PENDING_KEY] = True
    at.run()
    assert not at.exception, at.exception
    return at


def _library(at) -> dict:
    if controls.DESIGN_PRESETS_KEY not in at.session_state:
        return {}
    return at.session_state[controls.DESIGN_PRESETS_KEY] or {}


def _pending(at) -> bool:
    return bool(
        controls._DESIGN_SAVE_PENDING_KEY in at.session_state
        and at.session_state[controls._DESIGN_SAVE_PENDING_KEY]
    )


def test_the_name_field_is_not_required():
    """#422: a required field blocks every submit button of its form until it
    has a value — Cancel too. The check is the browser's, so AppTest cannot
    click into it; the proto is what reaches the browser."""
    at = _open_dialog()
    assert at.text_input(key=controls._DESIGN_NEW_NAME_KEY).proto.required is False


def test_cancel_with_an_empty_name_closes_and_saves_nothing():
    at = _open_dialog()
    at.text_input(key=controls._DESIGN_NEW_NAME_KEY).set_value("")
    at.button(key="design_save_cancel").click().run()
    assert not at.exception, at.exception
    assert not _pending(at)
    assert controls._DESIGN_NEW_NAME_KEY not in at.session_state
    assert not _library(at)


def test_cancel_discards_a_typed_name():
    at = _open_dialog()
    at.text_input(key=controls._DESIGN_NEW_NAME_KEY).set_value("Draft")
    at.button(key="design_save_cancel").click().run()
    assert not at.exception, at.exception
    assert controls._DESIGN_NEW_NAME_KEY not in at.session_state
    assert not _pending(at)
    assert "Draft" not in _library(at)


def test_save_with_an_empty_name_is_refused_and_stays_open():
    at = _open_dialog()
    at.text_input(key=controls._DESIGN_NEW_NAME_KEY).set_value("")
    at.button(key="design_save_go").click().run()
    assert not at.exception, at.exception
    assert _pending(at)
    assert any("name first" in e.value for e in at.error)
    assert not _library(at)
