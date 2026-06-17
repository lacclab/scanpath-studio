"""Unit tests for the setup-wizard's pure helper functions (Group B/C).

These are deterministic and dependency-light, so they're tested directly instead
of through the heavy AppTest path.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import app

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


class TestDefaultTrialColumns:
    def test_composes_participant_and_paragraph_preferring_paragraph(self):
        # A trial is one reading of one passage → participant + the finest passage
        # grain (paragraph beats a coarser text id).
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["paragraph_id", "text_id", "participant_id"]
        assert app._default_trial_columns(proposed, present) == [
            "participant_id",
            "paragraph_id",
        ]

    def test_adds_repeated_reading_column_when_present(self):
        # OneStop: participant + paragraph alone would collapse the two readings;
        # the repeated-reading column keeps them distinct.
        proposed = {"trial": "unique_paragraph_id"}
        present = ["participant_id", "unique_paragraph_id", "repeated_reading_trial"]
        assert app._default_trial_columns(proposed, present) == [
            "participant_id",
            "unique_paragraph_id",
            "repeated_reading_trial",
        ]

    def test_uses_canonical_participant_candidates(self):
        # A non-standard participant name (reader_id) is in PARTICIPANT_CANDIDATES,
        # so it still composes the default trial id (not paragraph-only).
        proposed = {"trial": "unique_paragraph_id"}
        present = ["reader_id", "unique_paragraph_id"]
        assert app._default_trial_columns(proposed, present) == [
            "reader_id",
            "unique_paragraph_id",
        ]

    def test_falls_back_to_paragraph_and_text_without_participant(self):
        # OneStop-shaped upload with no participant column on the words table.
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["paragraph_id", "text_id"]
        assert app._default_trial_columns(proposed, present) == [
            "paragraph_id",
            "text_id",
        ]

    def test_prefers_single_unique_trial_over_redundant_composite(self):
        # OneStop-shaped upload: a precomputed unique_trial_id plus a paragraph id.
        # Pairing them would force opaque composite ids for no benefit.
        proposed = {"trial": "unique_trial_id", "text_id": "unique_paragraph_id"}
        present = ["unique_trial_id", "unique_paragraph_id", "participant_id"]
        assert app._default_trial_columns(proposed, present) == ["unique_trial_id"]

    def test_paragraph_only_falls_back_to_trial_proposal(self):
        proposed = {"trial": "trial_id", "text_id": None}
        present = ["trial_id", "participant_id"]
        assert app._default_trial_columns(proposed, present) == ["trial_id"]

    def test_restricted_to_present_columns(self):
        # A proposed trial column absent from the common columns is dropped.
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["participant_id"]  # neither trial nor text present
        assert app._default_trial_columns(proposed, present) == []


class TestTrialIdValues:
    def test_single_column_mapping(self):
        raw = pd.DataFrame({"trial_id": ["a", "a", "b"]})
        assert app._trial_id_values(raw, {"trial": "trial_id"}) == {"a", "b"}

    def test_composite_mapping_joins_components(self):
        raw = pd.DataFrame({"p": ["x", "x"], "q": ["1", "2"]})
        assert app._trial_id_values(raw, {"trial": ["p", "q"]}) == {"x_1", "x_2"}

    def test_absent_column_returns_none(self):
        raw = pd.DataFrame({"trial_id": ["a"]})
        assert app._trial_id_values(raw, {"trial": "missing"}) is None

    def test_unmapped_trial_returns_none(self):
        raw = pd.DataFrame({"trial_id": ["a"]})
        assert app._trial_id_values(raw, {}) is None


class TestSafeDatasetName:
    def test_reserved_label_is_suffixed(self):
        assert (
            app._safe_dataset_name(app.DEMO_CHOICE) == f"{app.DEMO_CHOICE} (uploaded)"
        )

    def test_plain_name_passes_through_trimmed(self):
        assert app._safe_dataset_name("  My data  ") == "My data"


def _seed_overwrite_app():
    import streamlit as st

    from scanpath_studio.app import _seed_column_mapping

    # A widget already created these keys on a prior render of the wizard.
    st.session_state["col_map_trial_unified"] = ["default_col"]
    st.session_state["col_map_fix_x"] = "OLD_X"
    # The wizard restore must WIN over the already-set widget keys.
    _seed_column_mapping(
        {
            "col_map_trial_unified": ["restored_a", "restored_b"],
            "col_map_fix_x": "NEW_X",
        },
        overwrite=True,
    )


def _seed_setdefault_app():
    import streamlit as st

    from scanpath_studio.app import _seed_column_mapping

    st.session_state["col_map_fix_x"] = "OLD_X"
    # The plot-config path runs before widgets render → must not clobber.
    _seed_column_mapping({"col_map_fix_x": "NEW_X"})


def _remove_dataset_app():
    import streamlit as st

    from scanpath_studio.app import _remove_dataset

    st.session_state["_datasets"] = {"DS1": {"x": 1}, "DS2": {"y": 2}}
    st.session_state["data_source_choice"] = "DS1"
    _remove_dataset("DS1")


class TestWizardRestoreSeeding:
    def test_overwrite_replaces_existing_widget_keys(self):
        # Regression: the wizard "Restore a saved setup" silently did nothing
        # because setdefault no-ops on keys the mapping widgets already created.
        at = AppTest.from_function(_seed_overwrite_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["col_map_trial_unified"] == [
            "restored_a",
            "restored_b",
        ]
        assert at.session_state["col_map_fix_x"] == "NEW_X"

    def test_setdefault_does_not_clobber(self):
        at = AppTest.from_function(_seed_setdefault_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["col_map_fix_x"] == "OLD_X"


class TestRemoveDataset:
    def test_removes_and_falls_back_to_demo_when_selected(self):
        at = AppTest.from_function(_remove_dataset_app)
        at.run()
        assert not at.exception, at.exception
        assert "DS1" not in at.session_state["_datasets"]
        assert "DS2" in at.session_state["_datasets"]
        assert at.session_state["_pending_source_choice"] == app.DEMO_CHOICE
