"""What follows ✅ Add dataset: a dialog offering Open in Scanpath View or Add
another, and an **Open in Scanpath View** button beside **Add dataset** on the Data
page for whichever dataset the list marks Current."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT, NAV_KEY, iframe_sources, pin_data_view


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
    assert button.label == "Open in Scanpath View"
    assert "Bundled demo" in button.help

    button.click().run(timeout=90)
    assert not data_page.exception, data_page.exception
    assert data_page.session_state[NAV_KEY] == _VIEW_SCANPATH


def _added_dialog_app():
    """The ✅ Add dataset dialog, raised on every run as if not yet closed."""
    from scanpath_studio import app

    app._dataset_added_dialog("**Lab** added: 2 trials, 1 participant.")


def test_the_dialog_offers_both_next_steps():
    from scanpath_studio.menu import _VIEW_SCANPATH

    at = AppTest.from_function(_added_dialog_app).run()
    assert not at.exception, at.exception
    assert "**Lab** added: 2 trials, 1 participant." in [m.value for m in at.markdown]
    at.button(key="dataset_added_open").click().run()
    assert not at.exception, at.exception
    assert at.session_state[NAV_KEY] == _VIEW_SCANPATH

    at = AppTest.from_function(_added_dialog_app).run()
    at.button(key="dataset_added_again").click().run()
    assert not at.exception, at.exception
    assert at.session_state["_show_upload_wizard"] is True


def test_the_next_step_dialogs_act_on_return_values():
    """A dialog body is a fragment: a button callback in one would rerun only
    the modal and leave the page behind it where it was. The two dialogs that
    move the page — after ✅ Add dataset and after the Trial ID check — act on
    each button's return value and rerun the whole app."""
    from scanpath_studio import app

    tree = ast.parse(Path(app.__file__).read_text(encoding="utf-8"))
    names = {"_dataset_added_dialog", "_trial_identity_alert_dialog"}
    dialogs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {d.name for d in dialogs} == names
    for dialog in dialogs:
        assert any(
            isinstance(d, ast.Call) and ast.unparse(d.func) == "st.dialog"
            for d in dialog.decorator_list
        ), dialog.name
        calls = [node for node in ast.walk(dialog) if isinstance(node, ast.Call)]
        callbacks = [
            kw.arg
            for call in calls
            for kw in call.keywords
            if kw.arg in ("on_click", "on_change")
        ]
        assert not callbacks, dialog.name
        reruns = [call for call in calls if ast.unparse(call.func) == "st.rerun"]
        assert reruns, dialog.name
        for call in reruns:
            assert [(kw.arg, ast.literal_eval(kw.value)) for kw in call.keywords] == [
                ("scope", "app")
            ], dialog.name


def _added_app(trial_columns=None):
    """The 🗂️ Data page on the run after ✅ Add dataset added "Lab", with the
    Trial ID check asked for, as the add screen asks for it."""
    from scanpath_studio.constants import DATASET_ADDED_KEY, TRIAL_IDENTITY_CHECK_KEY
    from tests.test_trial_identity import demo_dataset_app

    at = demo_dataset_app(trial_columns)
    at.session_state[DATASET_ADDED_KEY] = "Lab"
    at.session_state[TRIAL_IDENTITY_CHECK_KEY] = "add"
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(240)
def test_main_raises_the_dialog_after_an_add():
    from scanpath_studio import app
    from scanpath_studio.constants import DATA_OVERVIEW_KEY

    at = _added_app()
    keys = {b.key for b in at.button}
    assert {"dataset_added_open", "dataset_added_again"} <= keys
    assert "trial_identity_alert_edit" not in keys
    assert any(m.value.startswith("**Lab** added: ") for m in at.markdown)
    assert not at.toast
    # The list of datasets, the new one Current in it, is scrolled back to.
    scroll = app._scroll_to_section_script(DATA_OVERVIEW_KEY)
    assert any(scroll in doc for doc in iframe_sources(at._tree))


@pytest.mark.timeout(240)
def test_the_trial_id_verdict_keeps_the_dialog_and_the_counts_become_a_toast():
    at = _added_app(["article_id", "article_batch"])
    keys = {b.key for b in at.button}
    assert "trial_identity_alert_edit" in keys
    assert "dataset_added_open" not in keys
    assert [t.value for t in at.toast if t.value.startswith("**Lab** added: ")]


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
    assert "Open in Scanpath View" in text
