"""Unit tests for the setup-wizard's pure helper functions.

These are deterministic and dependency-light, so they're tested directly instead
of through the heavy AppTest path.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import app, wizard

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


class TestWideFrameWarning:
    def test_ordinary_selection_is_quiet(self):
        assert wizard.wide_frame_warning(20, 10_000) is None

    def test_many_columns_warn_even_on_small_frame(self):
        message = wizard.wide_frame_warning(50, 100)
        assert message and "50 additional fields" in message

    def test_large_cell_product_warns(self):
        assert wizard.wide_frame_warning(25, 250_000)


class TestDefaultTrialColumns:
    def test_composes_participant_and_paragraph_preferring_paragraph(self):
        # A trial is one reading of one passage → participant + the finest passage
        # grain (paragraph beats a coarser text id).
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["paragraph_id", "text_id", "participant_id"]
        assert wizard._default_trial_columns(proposed, present) == [
            "participant_id",
            "paragraph_id",
        ]

    def test_adds_repeated_reading_column_when_present(self):
        # OneStop: participant + paragraph alone would collapse the two readings;
        # the repeated-reading column keeps them distinct.
        proposed = {"trial": "unique_paragraph_id"}
        present = ["participant_id", "unique_paragraph_id", "repeated_reading_trial"]
        assert wizard._default_trial_columns(proposed, present) == [
            "participant_id",
            "unique_paragraph_id",
            "repeated_reading_trial",
        ]

    def test_uses_canonical_participant_candidates(self):
        # A non-standard participant name (reader_id) is in PARTICIPANT_CANDIDATES,
        # so it still composes the default trial id (not paragraph-only).
        proposed = {"trial": "unique_paragraph_id"}
        present = ["reader_id", "unique_paragraph_id"]
        assert wizard._default_trial_columns(proposed, present) == [
            "reader_id",
            "unique_paragraph_id",
        ]

    def test_falls_back_to_paragraph_and_text_without_participant(self):
        # OneStop-shaped upload with no participant column on the words table.
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["paragraph_id", "text_id"]
        assert wizard._default_trial_columns(proposed, present) == [
            "paragraph_id",
            "text_id",
        ]

    def test_prefers_single_unique_trial_over_redundant_composite(self):
        # OneStop-shaped upload: a precomputed unique_trial_id plus a paragraph id.
        # Pairing them would force opaque composite ids for no benefit.
        proposed = {"trial": "unique_trial_id", "text_id": "unique_paragraph_id"}
        present = ["unique_trial_id", "unique_paragraph_id", "participant_id"]
        assert wizard._default_trial_columns(proposed, present) == ["unique_trial_id"]

    def test_paragraph_only_falls_back_to_trial_proposal(self):
        proposed = {"trial": "trial_id", "text_id": None}
        present = ["trial_id", "participant_id"]
        assert wizard._default_trial_columns(proposed, present) == ["trial_id"]

    def test_restricted_to_present_columns(self):
        # A proposed trial column absent from the common columns is dropped.
        proposed = {"trial": "trial_id", "text_id": "text_id"}
        present = ["participant_id"]  # neither trial nor text present
        assert wizard._default_trial_columns(proposed, present) == []


class TestTrialIdValues:
    def test_single_column_mapping(self):
        raw = pd.DataFrame({"trial_id": ["a", "a", "b"]})
        assert wizard._trial_id_values(raw, {"trial": "trial_id"}) == {"a", "b"}

    def test_composite_mapping_joins_components(self):
        raw = pd.DataFrame({"p": ["x", "x"], "q": ["1", "2"]})
        assert wizard._trial_id_values(raw, {"trial": ["p", "q"]}) == {"x_1", "x_2"}

    def test_absent_column_returns_none(self):
        raw = pd.DataFrame({"trial_id": ["a"]})
        assert wizard._trial_id_values(raw, {"trial": "missing"}) is None

    def test_unmapped_trial_returns_none(self):
        raw = pd.DataFrame({"trial_id": ["a"]})
        assert wizard._trial_id_values(raw, {}) is None


class TestSafeDatasetName:
    def test_reserved_label_is_suffixed(self):
        assert (
            wizard._safe_dataset_name(app.DEMO_CHOICE)
            == f"{app.DEMO_CHOICE} (uploaded)"
        )

    def test_plain_name_passes_through_trimmed(self):
        assert wizard._safe_dataset_name("  My data  ") == "My data"


def _seed_overwrite_app():
    import streamlit as st

    from scanpath_studio.url_state import _seed_column_mapping

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

    from scanpath_studio.url_state import _seed_column_mapping

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
        # The wizard's setup restore must overwrite: setdefault no-ops on keys
        # the mapping widgets already created, so the restore would silently
        # do nothing.
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


def _setup_restore_app():
    """Drive ``_wizard_restore_config`` through a host whose uploader returns
    the seeded file (``_setup`` = None is a cleared uploader)."""
    import streamlit as st

    from scanpath_studio.wizard import _wizard_restore_config

    class _Upload:
        name = "setup.json"

        def __init__(self, data: bytes, file_id: str):
            self._data = data
            self.size = len(data)
            self.file_id = file_id

        def getvalue(self) -> bytes:
            return self._data

    class _Host:
        def file_uploader(self, *args, **kwargs):
            data = st.session_state["_setup"]
            if data is None:
                return None
            return _Upload(data.encode(), st.session_state["_file_id"])

        def warning(self, *args, **kwargs):
            st.warning(*args, **kwargs)

    _wizard_restore_config(_Host())


class TestRestoreSetupOncePerUpload:
    def test_a_same_size_replacement_applies(self):
        import json

        at = AppTest.from_function(_setup_restore_app)
        at.session_state["_setup"] = json.dumps({"data_source": "Lab A"})
        at.session_state["_file_id"] = "upload-1"
        at.run()
        assert at.session_state["_wizard_restored_meta"]["data_source"] == "Lab A"
        # Same name and byte count, different content: a different file.
        at.session_state["_setup"] = json.dumps({"data_source": "Lab B"})
        at.session_state["_file_id"] = "upload-2"
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["_wizard_restored_meta"]["data_source"] == "Lab B"

    def test_clearing_the_uploader_lets_the_same_file_apply_again(self):
        import json

        at = AppTest.from_function(_setup_restore_app)
        at.session_state["_setup"] = json.dumps({"data_source": "Lab A"})
        at.session_state["_file_id"] = "upload-1"
        at.run()
        # An ordinary rerun does not re-apply over the session's later state.
        at.session_state["_wizard_restored_meta"] = {"data_source": "edited"}
        at.run()
        assert at.session_state["_wizard_restored_meta"]["data_source"] == "edited"
        at.session_state["_setup"] = None
        at.run()
        assert "_wizard_config_last" not in at.session_state
        at.session_state["_setup"] = json.dumps({"data_source": "Lab A"})
        at.run()  # same file_id and bytes as before, but after a clear
        assert at.session_state["_wizard_restored_meta"]["data_source"] == "Lab A"


def _copy_setup_app():
    """*Start from → A dataset you added*: copy, then Undo."""
    import streamlit as st

    from scanpath_studio import wizard

    st.session_state["_datasets"] = {
        "Lab A": {
            "source_recipe": {
                "schemas": {
                    "fixations": {
                        "trial": "TRIAL_INDEX",
                        "participant": "RECORDING_SESSION_LABEL",
                        "x": "CURRENT_FIX_X",
                        "duration": "CURRENT_FIX_DURATION",
                    },
                    "words": {
                        "trial": ["RECORDING_SESSION_LABEL", "TRIAL_INDEX"],
                        "left": "IA_LEFT",
                        "right": "IA_RIGHT",
                    },
                }
            },
            "setup": {"canvas_width": 1920, "canvas_height": 1080},
            wizard.WIZARD_CHOICES_FIELD: {
                "keep_and_filter": {"wizard_keep_by_table": {"col_map_fix": ["eye"]}}
            },
        }
    }
    step = st.session_state.get("_step", 0)
    if step == 0:
        st.session_state["col_map_fix_x"] = "mine"
        st.session_state[wizard._COPY_FROM_KEY] = "Lab A"
        wizard._copy_dataset_setup()
    elif step == 1:
        wizard._undo_and_start_from_scratch()


class TestStartFromADataset:
    def test_copying_fills_the_mapping_and_undo_puts_it_back(self):
        from scanpath_studio import wizard

        at = AppTest.from_function(_copy_setup_app)
        at.run()
        assert not at.exception, at.exception
        state = at.session_state
        assert state["col_map_fix_x"] == "CURRENT_FIX_X"
        assert state["col_map_fix_trial"] == ["TRIAL_INDEX"]
        assert state["col_map_fix_participant"] == ["RECORDING_SESSION_LABEL"]
        assert state["col_map_words_trial"] == [
            "RECORDING_SESSION_LABEL",
            "TRIAL_INDEX",
        ]
        assert state["col_map_words_box_format"] == "Edges"
        assert state["wizard_keep_col_map_fix"] == ["eye"]
        assert state["_wizard_restored_setup"]["canvas_width"] == 1920
        meta = state["_wizard_restored_meta"]
        assert meta["kind"] == "dataset" and meta["data_source"] == "Lab A"
        assert "column mapping (Fixations, Words (interest areas))" in meta["applied"]
        assert (
            "1 kept field" in meta["applied"] and "recording setup" in meta["applied"]
        )

        at.session_state["_step"] = 1
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["col_map_fix_x"] == "mine"
        assert "col_map_words_trial" not in at.session_state
        assert "_wizard_restored_setup" not in at.session_state
        assert "_wizard_restored_meta" not in at.session_state
        assert at.session_state[wizard._START_FROM_KEY] == wizard._START_SCRATCH


class TestMappingKeysFromSchemas:
    def test_origin_size_boxes_and_raw_gaze_singles(self):
        from scanpath_studio.wizard import _mapping_keys_from_schemas

        keys = _mapping_keys_from_schemas(
            {
                "words": {"x": "x", "width": "w", "text_id": None},
                "raw_gaze": {"trial": "t", "participant": "p"},
            }
        )
        assert keys["col_map_words_box_format"] == "Origin + size"
        assert keys["col_map_words_text_id"] == []
        assert keys["col_map_raw_gaze_trial"] == ["t"]
        assert keys["col_map_raw_gaze_participant"] == "p"


def _empty_wizard_setup_app():
    """The add screen's Recording setup, with no table in yet."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.wizard import _wizard_setup_step

    st.session_state.setdefault("global_scale_text_to_boxes", True)
    st.session_state.setdefault("global_canvas_width", 1920)
    _wizard_setup_step(
        st.container(),
        pd.DataFrame(),
        pd.DataFrame(),
        False,
        estimate=lambda: (2560, 1440),
        has_data=False,
    )


class TestAnEmptyAddScreenLeavesTheFigureAlone:
    """Opening ➕ Add dataset and cancelling must not leave the dataset you
    came from with the setup lines' own starting answers."""

    def test_its_starting_answers_write_no_figure_setting(self):
        at = AppTest.from_function(_empty_wizard_setup_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["global_scale_text_to_boxes"] is True
        assert at.session_state["global_canvas_width"] == 1920


def _restore_then_words_app():
    """A setup whose text fits the boxes, applied before any Words table."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.experimental_setup import SetupSnapshot
    from scanpath_studio.wizard import _apply_restored_setup, _wizard_setup_step

    if not st.session_state.get("_restored"):
        st.session_state["_restored"] = True
        snap = SetupSnapshot.from_dict(
            {
                "canvas_width": 1920,
                "canvas_height": 1080,
                "scale_text_to_boxes": True,
                "provenance": {
                    "screen": "measured",
                    "geometry": "skipped",
                    "text": "measured",
                },
            }
        )
        st.session_state["_wizard_restored_setup"] = snap.to_dict()
        _apply_restored_setup(snap)
    _wizard_setup_step(
        st.container(),
        pd.DataFrame(),
        pd.DataFrame(),
        bool(st.session_state.get("_has_words")),
        estimate=lambda: (800, 600),
        has_data=bool(st.session_state.get("_has_words")),
    )


class TestASetupAppliedBeforeTheWords:
    def test_fit_to_the_boxes_comes_back_when_they_arrive(self):
        from scanpath_studio.wizard import _SETUP_MODE_KEYS, _TEXT_BOXES, _TEXT_DEFAULT

        at = AppTest.from_function(_restore_then_words_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state[_SETUP_MODE_KEYS["text"]] == _TEXT_DEFAULT
        at.session_state["_has_words"] = True
        at.run()
        assert not at.exception, at.exception
        assert at.session_state[_SETUP_MODE_KEYS["text"]] == _TEXT_BOXES


class TestAMalformedSetupFile:
    def test_bad_sections_are_skipped(self):
        from scanpath_studio.wizard import _applied_summary, _clean_setup_config

        config = _clean_setup_config(
            {
                "data_source": "x",
                "column_mapping": 5,
                "filename_derive": ["not", "a", "dict"],
                "keep_and_filter": {"wizard_keep_by_table": "x"},
            }
        )
        assert "column_mapping" not in config
        assert "filename_derive" not in config
        assert "wizard_keep_by_table" not in config["keep_and_filter"]
        assert _applied_summary(config) == "nothing this screen uses"
