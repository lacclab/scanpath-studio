"""Troubleshooting and the GitHub support routes in Help and About."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from scanpath_studio import __version__, feedback, menu, persistence
from scanpath_studio.constants import CITATION

ROOT = Path(__file__).resolve().parents[1]


def _pending_dialog() -> None:
    from scanpath_studio import feedback

    feedback.maybe_show_feedback()


def _dialog_script() -> None:
    from scanpath_studio import feedback

    feedback._feedback_dialog()


@pytest.mark.parametrize("entry", ["help_faq", "help_feedback"])
def test_both_help_routes_open_the_same_answers(entry):
    at = AppTest.from_function(_pending_dialog).run()
    assert not at.expander
    with patch.object(st, "session_state", at.session_state):
        menu._arm_help_action(entry)
    at.run()
    assert not at.exception
    assert [problem.label for problem in at.expander] == [
        title for title, _answer in feedback.troubleshooting_items()
    ]
    assert at.button(key="help_report_bug").label == "Report a bug"


def test_contact_actions_and_bug_only_details():
    at = AppTest.from_function(_dialog_script).run()
    assert not at.exception
    assert {button.label: button.proto.url for button in at.link_button} == {
        "Ask a question ↗": CITATION["questions_url"],
        "Suggest an improvement ↗": CITATION["ideas_url"],
    }
    assert not at.code
    at.button(key="help_report_bug").click().run()
    assert not at.exception
    assert CITATION["bug_report_url"] in {b.proto.url for b in at.link_button}
    assert at.code[0].value == feedback.environment_details()
    template = CITATION["bug_report_url"].split("template=", 1)[1]
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / template).is_file()


@pytest.mark.parametrize("local", [True, False])
def test_environment_details_identify_the_computer_running_the_app(local, monkeypatch):
    monkeypatch.setattr(persistence, "server_bound_to_loopback", lambda: local)
    details = feedback.environment_details()
    assert f"Scanpath Studio {__version__}" in details
    assert f"Running on: {'this computer' if local else 'a server'}" in details
    assert "Python " in details and "Streamlit " in details


def test_answers_stay_short_and_use_edition_specific_links():
    from scanpath_studio.build_info import build_info

    items = feedback.troubleshooting_items()
    assert items
    for title, answer in items:
        assert title.endswith(("?", "."))
        assert len(answer) <= 480, title
    answers = " ".join(answer for _title, answer in items)
    for section in (
        "guides/loading-data/#tables",
        "guides/loading-data/#reading-measures",
        "guides/scanpath-visualization/controls/#under-the-plot",
        "about/#privacy",
        "faq/#export-fails",
    ):
        assert f"]({build_info().docs_url}{section})" in answers
    export = next(answer for title, answer in items if "PDF" in title)
    assert all(browser in export for browser in ("Chrome", "Chromium", "Edge"))


@pytest.mark.parametrize("local", [True, False])
@pytest.mark.parametrize("saving", [True, False])
def test_storage_answer_matches_the_actual_installation(local, saving, monkeypatch):
    monkeypatch.setattr(persistence, "server_bound_to_loopback", lambda: local)
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1" if saving else "0")
    answer = feedback._storage_answer()
    assert f"processed on this {'computer' if local else 'server'}" in answer
    if saving:
        assert "recovery copy keeps" in answer
        assert "Saved on this computer → Clear what is saved…" in answer
    else:
        assert "memory for this session" in answer
        assert "before refreshing" in answer.lower()


@pytest.mark.parametrize(
    ("session_key", "message"),
    [
        (persistence._PAUSED_KEY, "Recovery saving is paused"),
        (persistence.SAVE_CONFLICT_KEY, "unsaved edits are still in this tab"),
    ],
)
def test_recovery_answer_accounts_for_unsaved_session_changes(
    session_key, message, monkeypatch
):
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    at = AppTest.from_function(_dialog_script)
    at.session_state[session_key] = True
    at.run()
    assert not at.exception
    answers = " ".join(item.value for item in at.markdown)
    assert message in answers
    assert "export annotations" in answers
    assert "recovery copy keeps" not in answers


def test_about_says_where_data_goes_for_this_run():
    from scanpath_studio.app import _about_privacy_line

    for local, location in [(True, "on this computer"), (False, "on this server")]:
        saved = _about_privacy_line(local=local, saving=True)
        unsaved = _about_privacy_line(local=local, saving=False)
        assert location in saved and location in unsaved
        assert ("until you clear it" if local else "keeps a recovery copy") in saved
        assert "no recovery copy" in unsaved


def test_about_shows_the_line_for_a_hosted_run(monkeypatch):
    from scanpath_studio import app

    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "0")
    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: False)

    def about():
        from scanpath_studio import app

        app._about_dialog()

    at = AppTest.from_function(about).run()
    assert not at.exception
    details = next(tab for tab in at.tabs if tab.label == "App details")
    body = " ".join(md.value for md in details.markdown)
    assert "on this server" in body and "no recovery copy" in body
    assert f"{app.build_info().docs_url}about/#privacy" in body
