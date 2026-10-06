"""#374 F13: what the add screen detects on an EyeLink export.

`item` is the Text ID of an EyeLink experiment whose trial order was
randomized; a condition column is kept by default so it can be filtered on; a
column already mapped (TRIAL_INDEX as the Trial ID) is never pre-kept again.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.data import (
    looks_like_condition,
    propose_fix_schema,
    propose_word_schema,
    read_table_sample,
)

_FIX_COLUMNS = [
    "RECORDING_SESSION_LABEL",
    "TRIAL_INDEX",
    "item",
    "condition",
    "CURRENT_FIX_INDEX",
    "CURRENT_FIX_X",
    "CURRENT_FIX_Y",
    "CURRENT_FIX_DURATION",
    "CURRENT_FIX_START",
    "CURRENT_FIX_INTEREST_AREA_ID",
]


def _fixations(n_trials: int = 4, per_trial: int = 6) -> pd.DataFrame:
    rows = []
    for t in range(1, n_trials + 1):
        for i in range(1, per_trial + 1):
            rows.append(
                [
                    "s01",
                    t,
                    f"2_{t}",
                    "Adv" if t % 2 else "Ele",
                    i,
                    100.5 * i,
                    200.25 + i,
                    180 + 7 * i,
                    10_000 * t + 300 * i,
                    i,
                ]
            )
    return pd.DataFrame(rows, columns=_FIX_COLUMNS)


def test_item_is_proposed_as_the_text_id():
    frame = pd.DataFrame(columns=_FIX_COLUMNS)
    assert propose_fix_schema(frame)["text_id"] == "item"
    words = pd.DataFrame(columns=["TRIAL_INDEX", "ITEM_ID", "IA_ID", "IA_LEFT"])
    assert propose_word_schema(words)["text_id"] == "ITEM_ID"


def test_a_named_text_column_still_wins_over_item():
    frame = pd.DataFrame(columns=["item", "paragraph_id", "TRIAL_INDEX"])
    assert propose_fix_schema(frame)["text_id"] == "paragraph_id"


def test_looks_like_condition():
    fixations = _fixations()
    assert looks_like_condition(fixations["condition"])
    assert looks_like_condition(fixations["item"])
    assert not looks_like_condition(fixations["CURRENT_FIX_X"])  # fractional
    assert not looks_like_condition(fixations["CURRENT_FIX_START"])  # one per row
    assert not looks_like_condition(fixations["RECORDING_SESSION_LABEL"])  # constant


def test_read_table_sample_reads_a_plain_file_and_a_zip_member():
    text = _fixations().to_csv(sep="\t", index=False)
    plain = io.BytesIO(text.encode())
    plain.name = "Fixation_report.txt"
    assert list(read_table_sample(plain, nrows=5).columns) == _FIX_COLUMNS
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("s01/Fixation_report.txt", text)
    archive.seek(0)
    archive.name = "per_participant.zip"
    sample = read_table_sample(archive, kind="fixations")
    assert len(sample) == 24 and "condition" in sample.columns
    workbook = io.BytesIO(b"")
    workbook.name = "report.parquet"
    assert read_table_sample(workbook).empty


@pytest.mark.timeout(240)
def test_extras_keep_conditions_and_never_a_mapped_column(monkeypatch):
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    fixations = _fixations()
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: (
            fixations if kw["state_prefix"] == "col_map_fix" else pd.DataFrame()
        ),
    )
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.run(timeout=180)
    assert not at.exception, at.exception
    kept = set(at.session_state["wizard_keep_col_map_fix"])
    assert "condition" in kept
    assert "TRIAL_INDEX" not in kept  # mapped as the Trial ID
    assert "item" not in kept  # mapped as the Text ID
    text_id = at.session_state["col_map_fix_text_id"]
    assert list(text_id) == ["item"]


def test_the_add_confirmation_counts_trials_and_participants():
    """#374 F30: ✅ Add dataset says what arrived."""
    from scanpath_studio.app import dataset_added_message

    fixations = pd.DataFrame(
        {"participant_id": ["s01", "s01", "s02"], "trial_id": ["1", "2", "1"]}
    )
    message = dataset_added_message("Dataset 1", pd.DataFrame(), fixations)
    assert message == "**Dataset 1** added — 3 trials, 2 participants."
    assert dataset_added_message("Gaze", None, None) == "**Gaze** added."
