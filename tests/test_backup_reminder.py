"""UX-199: the first upload on a deployment that saves nothing says so, in the
notices strip on every view, until it is dismissed for the session."""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import app
from scanpath_studio.app import BACKUP_GUIDE_URL, BACKUP_REMINDER_KEY
from scanpath_studio.persistence import PERSIST_ENV_VAR
from tests.conftest import APP_SCRIPT


@pytest.fixture
def session():
    import streamlit as st

    st.session_state.clear()
    yield st.session_state
    st.session_state.clear()


class TestArming:
    def test_an_upload_arms_it_where_nothing_is_saved(self, monkeypatch, session):
        monkeypatch.setenv(PERSIST_ENV_VAR, "0")
        app.arm_backup_reminder()
        assert session[BACKUP_REMINDER_KEY] == "show"

    def test_not_where_the_recovery_cache_is_on(self, monkeypatch, session):
        monkeypatch.setenv(PERSIST_ENV_VAR, "1")
        app.arm_backup_reminder()
        assert BACKUP_REMINDER_KEY not in session

    def test_a_dismissal_holds_for_the_session(self, monkeypatch, session):
        monkeypatch.setenv(PERSIST_ENV_VAR, "0")
        session[BACKUP_REMINDER_KEY] = "dismissed"
        app.arm_backup_reminder()
        assert session[BACKUP_REMINDER_KEY] == "dismissed"

    def test_adding_a_dataset_arms_it(self, monkeypatch, session):
        from scanpath_studio import wizard

        monkeypatch.setenv(PERSIST_ENV_VAR, "0")
        words = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial_id": ["t1"],
                "word_id": [1],
                "text": ["a"],
                "x": [0.0],
                "y": [0.0],
                "width": [10.0],
                "height": [10.0],
            }
        )
        session["_wizard_finalize_payload"] = {
            "words": words,
            "fixations": pd.DataFrame(),
            "raw_gaze": pd.DataFrame(),
        }
        session["wizard_dataset_name"] = "My corpus"
        wizard._finalize_wizard_dataset()
        assert session[BACKUP_REMINDER_KEY] == "show"


def test_the_reminder_shows_until_dismissed(monkeypatch):
    monkeypatch.setenv(PERSIST_ENV_VAR, "0")
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state[BACKUP_REMINDER_KEY] = "show"
    at.run()
    assert not at.exception, at.exception
    text = " ".join(str(m.value) for m in at.markdown)
    assert "This deployment saves nothing." in text
    assert BACKUP_GUIDE_URL in text
    assert "Data → Annotations" in text
    # Opened on Scanpath, so it offers the way to the Data page too.
    assert [b for b in at.button if b.key == "sps_backup_reminder_go"]

    next(b for b in at.button if b.key == "sps_backup_reminder_dismiss").click()
    at.run()
    assert at.session_state[BACKUP_REMINDER_KEY] == "dismissed"
    text = " ".join(str(m.value) for m in at.markdown)
    assert "This deployment saves nothing." not in text
