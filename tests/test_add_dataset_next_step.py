"""What follows ✅ Add dataset: a dialog offering Open in Scanpath or Add
another, and an **Open in Scanpath** button beside **Add dataset** on the Data
page for whichever dataset the list marks Current."""

from __future__ import annotations

import inspect

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT, NAV_KEY, pin_data_view


@pytest.fixture
def data_page() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    assert not at.exception, at.exception
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


def test_the_data_page_offers_open_in_scanpath(data_page):
    from scanpath_studio.menu import _VIEW_DATA, _VIEW_SCANPATH

    assert data_page.session_state[NAV_KEY] == _VIEW_DATA
    button = data_page.button(key="data_open_in_scanpath")
    assert button.label == "Open in Scanpath"
    assert "Bundled demo" in button.help

    button.click().run(timeout=90)
    assert not data_page.exception, data_page.exception
    assert data_page.session_state[NAV_KEY] == _VIEW_SCANPATH


def test_the_dialog_offers_both_next_steps_by_return_value():
    from scanpath_studio import app

    source = inspect.getsource(app._dataset_added_dialog)
    assert "dataset_added_open" in source
    assert "dataset_added_again" in source
    # A dialog body is a fragment: a callback would rerun only the modal and
    # leave the page behind it where it was.
    assert "on_click=" not in source
    assert "_go_scanpath()" in source
    assert "_enter_add_data_wizard()" in source
    assert 'st.rerun(scope="app")' in source


def test_main_raises_the_dialog_and_keeps_the_toast_as_the_fallback():
    from scanpath_studio import app

    source = inspect.getsource(app._run_app)
    assert "_dataset_added_dialog(message)" in source
    # The Trial ID verdict keeps priority over the run's one dialog; the
    # counts then still arrive, as a toast.
    assert source.index("_trial_identity_alert_dialog(") < source.index(
        "_dataset_added_dialog(message)"
    )
    assert "st.toast(message" in source
    assert "_scroll_to_section_script(DATA_OVERVIEW_KEY)" in source


def test_the_section_scroll_targets_the_key_it_is_given():
    from scanpath_studio import app

    script = app._scroll_to_section_script("data_overview")
    assert '.st-key-data_overview"' in script
    assert "__SECTION_KEY__" not in script
    assert '.st-key-data_dataset_editor"' in app._SCROLL_TO_EDITOR_SCRIPT


def test_the_setup_guide_no_longer_promises_to_open_the_dataset():
    from scanpath_studio import tour

    text = " ".join(str(step.get("body", "")) for step in tour._WIZARD_GUIDE_STEPS)
    assert "saves the dataset and opens it" not in text
    assert "Open in Scanpath" in text
