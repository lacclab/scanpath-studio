"""The rail's foldable sections: Presets, Palette, Modes and Customize."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from scanpath_studio import controls
from tests.conftest import APP_SCRIPT


def _boot() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_every_section_has_a_chevron_and_starts_open():
    at = _boot()
    for name in controls.RAIL_SECTIONS:
        assert "Hide" in at.button(key=f"rail_{name}_fold").label
    assert at.session_state[controls._RAIL_FOLDED_KEY] == frozenset()


def test_folding_is_kept_and_unfolding_clears_it():
    at = _boot()
    at.button(key="rail_modes_fold").click().run()
    assert not at.exception, at.exception
    assert at.session_state[controls._RAIL_FOLDED_KEY] == {"modes"}
    assert at.session_state[controls._RAIL_FOLD_CHOSEN_KEY] is True
    assert "Show" in at.button(key="rail_modes_fold").label
    at.button(key="rail_modes_fold").click().run()
    assert at.session_state[controls._RAIL_FOLDED_KEY] == frozenset()


def test_a_folded_section_keeps_its_widgets():
    """Folding hides by CSS only, so the controls inside keep rendering."""
    at = _boot()
    at.button(key="rail_view_fold").click().run()
    assert at.button(key="viz_view_scanpath")


def test_a_running_guide_shows_every_section_without_unfolding_them():
    at = _boot()
    at.button(key="rail_modes_fold").click().run()
    at.session_state["tutorial_active"] = "compare_readings"
    at.run()
    assert "Hide" in at.button(key="rail_modes_fold").label
    assert at.session_state[controls._RAIL_FOLDED_KEY] == {"modes"}


def test_the_cookie_script_keeps_the_folds_for_a_year():
    script = controls.rail_fold_cookie_script({"customize", "view"})
    assert f"{controls.RAIL_FOLD_COOKIE}=view.customize;" in script
    assert f"max-age={365 * 24 * 60 * 60}" in script
    assert "SameSite=Lax" in script
