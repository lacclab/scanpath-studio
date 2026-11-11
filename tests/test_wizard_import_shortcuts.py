"""The add screen's shortcuts for tables whose ids live in file names.

IDs derived from text fill the empty ID fields on Apply; a setup file carries
*Merge character boxes into word boxes*; the screen suggests that merge for a
Words table whose words have rows at different positions; and it says when the
two tables' IDs differ only in case.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import app
from scanpath_studio.data import words_with_several_boxes
from scanpath_studio.wizard import (
    _derived_id_proposals,
    case_only_matches,
    merge_boxes_hint,
)
from tests.conftest import APP_SCRIPT, answer_setup_step

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


# --- Words at several positions -------------------------------------------


def _char_rows(**extra) -> pd.DataFrame:
    """Two words, two characters each, side by side on one line."""
    return pd.DataFrame(
        {
            "trial_id": ["t"] * 4,
            "word_idx": [0, 0, 1, 1],
            "x": [80, 100, 140, 160],
            "y": [50] * 4,
            "width": [20] * 4,
            "height": [30] * 4,
            **extra,
        }
    )


_CHAR_SCHEMA = {
    "trial": "trial_id",
    "word_id": "word_idx",
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
}


class TestWordsWithSeveralBoxes:
    def test_one_row_per_character_counts_each_word(self):
        assert words_with_several_boxes(_char_rows(), _CHAR_SCHEMA) == 2

    def test_a_box_repeated_per_reader_is_not_counted(self):
        words = pd.concat([_char_rows().iloc[[0, 2]]] * 2)
        assert words_with_several_boxes(words, _CHAR_SCHEMA) == 0

    def test_a_mapped_screen_tells_the_rows_apart(self):
        words = _char_rows(page=[1, 2, 1, 2])
        assert words_with_several_boxes(words, _CHAR_SCHEMA) == 2
        schema = {**_CHAR_SCHEMA, "screen_id": "page"}
        assert words_with_several_boxes(words, schema) == 0

    def test_edges_read_like_origins(self):
        words = _char_rows().rename(columns={"x": "left", "y": "top"})
        schema = {**_CHAR_SCHEMA, "x": None, "y": None, "left": "left", "top": "top"}
        assert words_with_several_boxes(words, schema) == 2

    def test_nothing_to_say_without_a_word_id(self):
        schema = {**_CHAR_SCHEMA, "word_id": None}
        assert words_with_several_boxes(_char_rows(), schema) == 0

    def test_the_hint_names_screens_only_when_none_is_mapped(self):
        assert "Screen ID" in merge_boxes_hint(2, screen_mapped=False)
        assert "Screen ID" not in merge_boxes_hint(1, screen_mapped=True)
        assert "1 word has" in merge_boxes_hint(1, screen_mapped=True)


# --- IDs that differ only in case ------------------------------------------


class TestCaseOnlyMatches:
    def test_counts_ids_equal_ignoring_case(self):
        count, example = case_only_matches(
            {"Alpha", "Beta", "gamma"}, {"alpha", "beta"}
        )
        assert count == 2
        assert example == ("Alpha", "alpha")

    def test_an_exact_match_is_not_counted(self):
        assert case_only_matches({"alpha", "Beta"}, {"alpha", "beta", "Beta"}) == (
            0,
            None,
        )


# --- Derived columns detected as IDs -------------------------------------


class TestDerivedIdProposals:
    def test_detected_by_the_usual_names_one_field_per_column(self):
        proposals = _derived_id_proposals(
            {
                "Fixations": ["participant", "stimulus"],
                "Words table": ["stimulus"],
                "Raw gaze": ["session"],
            }
        )
        # `stimulus` names a trial and a text; the Trial ID takes it.
        assert proposals == {
            "col_map_fix": {"trial": "stimulus", "participant": "participant"},
            "col_map_words": {"trial": "stimulus"},
        }


# --- The add screen, end to end --------------------------------------------


_DERIVE_LINES = {
    "wizard_filename_split": True,
    "wizard_filename_line_count": 2,
    "wizard_filename_table": "Fixations",
    "wizard_filename_mode": "Extract with a regex",
    "wizard_filename_regex": r"(?P<participant>p\d+)_(?P<stimulus>[A-Za-z]+)_fix",
    "wizard_filename_table_1": "Words table",
    "wizard_filename_mode_1": "Extract with a regex",
    "wizard_filename_regex_1": r"(?P<stimulus>[A-Za-z]+)_aoi",
}


def _named_tables(monkeypatch, stimulus: str = "Alpha") -> None:
    """A Fixations and a Words upload whose ids are only in their file names:
    the scanpaths spell the stimulus ``stimulus``, the boxes ``alpha``."""
    fixations = pd.DataFrame(
        {
            "x": [90.0, 150.0, 95.0, 155.0],
            "y": [60.0] * 4,
            "duration": [200, 220, 180, 240],
            "source_file": [f"p1_{stimulus}_fix"] * 2 + [f"p2_{stimulus}_fix"] * 2,
        }
    )
    words = pd.DataFrame(
        {
            "word_id": [1, 2],
            "text": ["one", "two"],
            "x": [80, 140],
            "y": [50, 50],
            "width": [40, 40],
            "height": [30, 30],
            "source_file": ["alpha_aoi"] * 2,
        }
    )
    tables = {"col_map_fix": fixations, "col_map_words": words}
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: tables.get(kw["state_prefix"], pd.DataFrame()),
    )


def _wizard() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.session_state["_show_upload_wizard"] = True
    at.session_state["setup_complete"] = False
    answer_setup_step(at)
    for key, value in _DERIVE_LINES.items():
        at.session_state[key] = value
    return at


def _run(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, f"Streamlit exceptions: {at.exception}"
    return at


def _apply(at: AppTest) -> AppTest:
    next(b for b in at.button if b.key == "wizard_filename_apply").click()
    return _run(at)


def _case_hints(at: AppTest) -> list[str]:
    return [w.value for w in at.warning if "only when case is ignored" in w.value]


class TestApplyMapsDerivedIds:
    def test_apply_fills_the_empty_id_fields_it_can_name(self, monkeypatch):
        _named_tables(monkeypatch, stimulus="alpha")
        at = _run(_wizard())
        assert at.session_state["col_map_fix_participant"] == []
        _apply(at)
        state = at.session_state
        assert state["col_map_fix_trial"] == ["stimulus"]
        assert state["col_map_fix_participant"] == ["participant"]
        assert state["col_map_words_trial"] == ["stimulus"]
        # The Words table has no reader, and `stimulus` already is the trial.
        assert state["col_map_words_participant"] == []
        assert state["col_map_fix_text_id"] == []
        # Filled by detection, so marked as auto-detected until confirmed.
        keys = {b.key for b in at.button}
        assert "col_map_fix_participant_cell_confirm" in keys
        assert not _case_hints(at)
        next(b for b in at.button if b.key == "wizard_finalize").click()
        _run(at)
        entry = next(iter(at.session_state["_datasets"].values()))
        assert sorted(entry["fixations"]["participant_id"].unique()) == ["p1", "p2"]
        # The two shared word boxes reach both readings.
        assert entry["words"].groupby("participant_id").size().to_dict() == {
            "p1": 2,
            "p2": 2,
        }

    def test_a_field_marked_touched_by_the_browser_still_fills(self, monkeypatch):
        """In a browser, a change of columns re-checks the mapping and the empty
        Trial ID pickers echo back as touched, though nobody picked anything."""
        from scanpath_studio.controls import TOUCHED_FIELDS_KEY

        _named_tables(monkeypatch, stimulus="alpha")
        at = _run(_wizard())
        at.session_state[TOUCHED_FIELDS_KEY] = {
            "col_map_fix_trial",
            "col_map_words_trial",
        }
        _apply(at)
        assert at.session_state["col_map_fix_trial"] == ["stimulus"]
        assert at.session_state["col_map_words_trial"] == ["stimulus"]
        # Detected, not confirmed: the mark the echo left is gone.
        assert "col_map_fix_trial_cell_confirm" in {b.key for b in at.button}

    def test_a_field_cleared_by_hand_stays_empty(self, monkeypatch):
        _named_tables(monkeypatch, stimulus="alpha")
        at = _apply(_run(_wizard()))
        at.multiselect(key="col_map_fix_participant").set_value([])
        _run(at)
        _apply(at)
        assert at.session_state["col_map_fix_participant"] == []


class TestIdsThatDifferOnlyInCase:
    def test_the_hint_names_lowercase_and_goes_once_it_is_on(self, monkeypatch):
        _named_tables(monkeypatch, stimulus="Alpha")
        at = _apply(_run(_wizard()))
        hints = _case_hints(at)
        assert len(hints) == 1
        assert "'Alpha' and 'alpha'" in hints[0] and "Lowercase" in hints[0]
        at.session_state["wizard_filename_regex_lower"] = True
        _apply(_run(at))
        assert not _case_hints(at)


class TestTheMergeSuggestion:
    def test_shown_for_character_rows_until_the_merge_is_on(self, monkeypatch):
        words = _char_rows(word=["AA", "AA", "BB", "BB"])
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                words if kw["state_prefix"] == "col_map_words" else pd.DataFrame()
            ),
        )
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        _run(at)

        def suggested() -> bool:
            return any("rows at different positions" in c.value for c in at.caption)

        assert suggested()
        at.toggle(key="wizard_aggregate_char_boxes").set_value(True)
        _run(at)
        assert not suggested()


# --- The setup file carries the merge -------------------------------------


def _setup_file_app():
    """Save the add screen's setup, then apply ``_config`` from a file."""
    import streamlit as st

    from scanpath_studio import wizard

    if "_saved" not in st.session_state:
        st.session_state["wizard_aggregate_char_boxes"] = True
        st.session_state["_saved"] = wizard._wizard_setup_config()
        st.session_state["wizard_aggregate_char_boxes"] = False
    config = st.session_state.get("_config")
    if config is not None and not st.session_state.get("_applied"):
        st.session_state["_applied"] = True
        wizard._apply_setup_config(config, source="setup.json", kind="file")
    if st.session_state.get("_undo"):
        st.session_state["_undo"] = False
        wizard._undo_setup_restore()


class TestASetupFileCarriesTheMerge:
    def test_saved_and_restored(self):
        at = AppTest.from_function(_setup_file_app)
        at.run()
        saved = at.session_state["_saved"]
        assert saved["steps"] == ["aggregate_char_boxes"]
        at.session_state["_config"] = saved
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["wizard_aggregate_char_boxes"] is True
        assert (
            "character-box merge"
            in at.session_state["_wizard_restored_meta"]["applied"]
        )
        at.session_state["_undo"] = True
        at.run()
        assert at.session_state["wizard_aggregate_char_boxes"] is False

    def test_a_file_without_steps_leaves_the_switch(self):
        at = AppTest.from_function(_setup_file_app)
        at.session_state["_config"] = {"data_source": "older"}
        at.session_state["_saved"] = {}
        at.session_state["wizard_aggregate_char_boxes"] = True
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["wizard_aggregate_char_boxes"] is True

    def test_steps_that_are_not_a_list_are_skipped(self):
        from scanpath_studio.wizard import _clean_setup_config

        assert "steps" not in _clean_setup_config({"steps": "aggregate_char_boxes"})


def _copy_merged_dataset_app():
    """*Start from → A dataset you added*, from one added with the merge."""
    import streamlit as st

    from scanpath_studio import wizard

    st.session_state["_datasets"] = {
        "Characters": {
            "source_recipe": {"schemas": {}, "steps": ["aggregate_char_boxes"]}
        }
    }
    st.session_state[wizard._COPY_FROM_KEY] = "Characters"
    wizard._copy_dataset_setup()


def _editor_setup_file_app():
    """✏️ Edit dataset's setup file for a dataset added with the merge."""
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state["_datasets"] = {
        "Characters": {
            "source_recipe": {"schemas": {}, "steps": ["aggregate_char_boxes"]}
        }
    }
    st.session_state["_out"] = tabs._editor_setup_config("Characters")


class TestEveryWriterRecordsTheMerge:
    def test_copying_a_dataset_turns_it_on(self):
        at = AppTest.from_function(_copy_merged_dataset_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["wizard_aggregate_char_boxes"] is True

    def test_the_edit_screens_file_carries_it(self):
        at = AppTest.from_function(_editor_setup_file_app)
        at.run()
        assert not at.exception, at.exception
        out = at.session_state["_out"]
        assert out["steps"] == ["aggregate_char_boxes"]
        assert not any(
            "Merge character boxes" in n for n in out["column_mapping_notes"]
        )
