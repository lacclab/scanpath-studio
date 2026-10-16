"""The identity pickers show auto-detection like every other field.

Trial, Participant and Text ID are multiselects (several columns can compose an
id), not selects, so they need their own path to the selects' amber tint and ✨
confirm button — without it an auto-detected id reads exactly like one somebody
has checked. An auto-detected id is amber with a ✨ button until it is confirmed
or changed, on the add screen and in the ✏️ Edit dataset grid alike.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _boot(monkeypatch):
    from scanpath_studio import app

    words, fixations = app.load_sample_data()
    frames = {"col_map_words": words, "col_map_fix": fixations}
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(240)
def test_an_auto_detected_id_offers_a_confirm_button(monkeypatch):
    at = _boot(monkeypatch)
    keys = {b.key for b in at.button}
    assert "col_map_words_trial_cell_confirm" in keys
    assert "col_map_fix_participant_cell_confirm" in keys


@pytest.mark.timeout(240)
def test_confirming_it_clears_the_mark(monkeypatch):
    from scanpath_studio.controls import TOUCHED_FIELDS_KEY

    at = _boot(monkeypatch)
    at.button(key="col_map_words_trial_cell_confirm").click().run(timeout=90)
    assert not at.exception, at.exception
    assert "col_map_words_trial" in at.session_state[TOUCHED_FIELDS_KEY]
    assert "col_map_words_trial_cell_confirm" not in {b.key for b in at.button}
