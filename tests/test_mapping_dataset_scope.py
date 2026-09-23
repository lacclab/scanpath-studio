"""BUG-32 — a column mapping does not carry over between two datasets.

`controls.forget_mapping_for_other_table` decided whether a stored `col_map_*`
pick still applied by the table's **column universe** alone. Two datasets that
share an AOI file — or an upload in the same EyeLink/OneStop format as the
bundled demo — have identical headers by construction, so the second silently
inherited the first one's picks, and nothing was cleared or said because every
pick still named a real column. The user's call (2026-09-02, #111): scope the
signature to the dataset too, and keep DATA-24's within-dataset behaviour.

The reproduction the fix is built on is the first test: the add-dataset wizard
maps its tables under the same `col_map_*` keys the 🗂️ Data page uses for the
demo, its field widgets persist, and going back to the demo did not reset them
(`_colmap_seeded_for` still named the demo) — so a Duration picked for the
upload became the demo's Duration.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.conftest import APP_SCRIPT, answer_setup_step, open_data_view

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


@pytest.mark.timeout(240)
def test_a_pick_made_while_adding_a_dataset_does_not_carry_into_the_demo(
    monkeypatch,
):
    from scanpath_studio import app, data
    from scanpath_studio.constants import DEMO_CHOICE

    # The upload is the demo's own two tables, so every header matches — the
    # shape of the report (one AOI file shared by two datasets).
    raw_words, raw_fix = data.load_sample_data()
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: (
            raw_words
            if kw["state_prefix"] == "col_map_words"
            else raw_fix
            if kw["state_prefix"] == "col_map_fix"
            else pd.DataFrame()
        ),
    )
    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=120)
    assert not at.exception, at.exception
    detected = at.session_state["col_map_fix_duration"]
    assert detected == "CURRENT_FIX_DURATION"

    open_data_view(at)
    next(b for b in at.button if b.key == "add_data_btn").click()
    at.run(timeout=120)
    # A deliberate, different choice for the new dataset.
    at.selectbox(key="col_map_fix_duration").set_value("CURRENT_FIX_END")
    at.run(timeout=120)
    answer_setup_step(at)
    at.run(timeout=120)
    next(b for b in at.button if b.key == "wizard_finalize").click()
    at.run(timeout=120)
    assert not at.exception, at.exception
    name = at.session_state["data_source_choice"]
    stored = at.session_state["_datasets"][name]["schemas"]["fixations"]
    assert stored["duration"] == "CURRENT_FIX_END"

    at.selectbox(key="data_source_picker").set_value(DEMO_CHOICE)
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert at.session_state["data_source_choice"] == DEMO_CHOICE
    assert at.session_state["col_map_fix_duration"] == detected, (
        "the demo inherited the Duration picked for the uploaded dataset"
    )
    # The upload keeps its own mapping.
    stored = at.session_state["_datasets"][name]["schemas"]["fixations"]
    assert stored["duration"] == "CURRENT_FIX_END"


# ---------------------------------------------------------------------------
# The mechanism, one call at a time
# ---------------------------------------------------------------------------
def _mapping_app():
    """Render the fixations mapping for the seeded (dataset, frame), after an
    optional restore — the three things these tests vary."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import FIX_FIELD_SPECS, column_mapping_ui
    from scanpath_studio.data import propose_fix_schema
    from scanpath_studio.url_state import _seed_column_mapping

    columns = {
        "participant_id": ["p1"],
        "trial": ["t1"],
        "CURRENT_FIX_X": [1.0],
        "CURRENT_FIX_Y": [2.0],
        "CURRENT_FIX_DURATION": [100],
        "CURRENT_FIX_END": [300],
    }
    if st.session_state.get("_grown"):
        columns["file_part_1"] = ["x"]
    df = pd.DataFrame(columns)
    restore = st.session_state.pop("_restore", None)
    if restore is not None:
        _seed_column_mapping(
            restore, overwrite=True, dataset=st.session_state.pop("_restore_for")
        )
    st.session_state["_mapping"] = column_mapping_ui(
        df,
        table_label="Fixations",
        state_key_prefix="col_map_fix",
        field_specs=FIX_FIELD_SPECS,
        proposed=propose_fix_schema(df),
        dataset=st.session_state["_dataset"],
    )


def _mapped(dataset: str) -> AppTest:
    at = AppTest.from_function(_mapping_app)
    at.session_state["_dataset"] = dataset
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_mapping"]["duration"] == "CURRENT_FIX_DURATION"
    at.selectbox(key="col_map_fix_duration").set_value("CURRENT_FIX_END")
    at.run(timeout=30)
    assert at.session_state["_mapping"]["duration"] == "CURRENT_FIX_END"
    return at


def _rerun(at: AppTest) -> dict:
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at.session_state["_mapping"]


def test_another_dataset_with_the_same_headers_starts_from_detection():
    at = _mapped("dataset A")
    at.session_state["_dataset"] = "dataset B"
    assert _rerun(at)["duration"] == "CURRENT_FIX_DURATION"


def test_the_same_dataset_keeps_the_pick():
    at = _mapped("dataset A")
    assert _rerun(at)["duration"] == "CURRENT_FIX_END"


def test_the_same_dataset_growing_a_column_keeps_the_pick():
    """DATA-24's case: the wizard appends `file_part_N` to its own frame."""
    at = _mapped("dataset A")
    at.session_state["_grown"] = True
    assert _rerun(at)["duration"] == "CURRENT_FIX_END"


def test_a_mapping_restored_for_a_dataset_is_kept_by_it():
    """The cost the user accepted — restored configs breaking — is not paid:
    the restore claims the keys for the dataset it is restoring into, so that
    dataset's first table keeps them instead of clearing them as another's."""
    at = _mapped("dataset A")
    at.session_state["_dataset"] = "dataset B"
    at.session_state["_restore"] = {"col_map_fix_duration": "CURRENT_FIX_END"}
    at.session_state["_restore_for"] = "dataset B"
    assert _rerun(at)["duration"] == "CURRENT_FIX_END"


def test_a_mapping_restored_for_one_dataset_is_dropped_by_another():
    """➕ Add dataset → *Restore a saved setup* → ✕ Cancel before any upload:
    the restored keys were claimed for the dataset being added, so the demo,
    meeting them first, does not adopt them."""
    at = _mapped("demo")
    at.session_state["_restore"] = {"col_map_fix_duration": "CURRENT_FIX_END"}
    at.session_state["_restore_for"] = "add-dataset wizard"
    # The wizard's table never arrives; the demo re-renders instead.
    assert _rerun(at)["duration"] == "CURRENT_FIX_DURATION"


def test_entering_the_wizard_claims_the_mapping_for_the_new_dataset():
    """A setup restored in the wizard before its first upload must survive that
    upload, and nothing the wizard seeds may reach the demo after ✕ Cancel —
    so the reset that starts a new dataset claims the keys for it."""

    def _enter():
        import streamlit as st

        from scanpath_studio.wizard import _reset_wizard_widgets

        st.session_state["_mapped_columns_col_map_fix"] = ("demo", ("a",))
        _reset_wizard_widgets()
        st.session_state["_marker"] = st.session_state["_mapped_columns_col_map_fix"]

    from scanpath_studio.wizard import WIZARD_MAPPING_DATASET

    at = AppTest.from_function(_enter)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_marker"] == (WIZARD_MAPPING_DATASET, None)
