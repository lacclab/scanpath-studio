"""Unit tests for the setup-wizard's pure helper functions (Group B/C).

These are deterministic and dependency-light, so they're tested directly instead
of through the heavy AppTest path.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from scanpath_studio import app, wizard, wizard_shell

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


class TestWizardAccordion:
    """DATA-22 replaced DATA-19's one-shot ``_wizard_keep_open`` marker with a
    shell that owns the open flag outright. These cover the shell's contract;
    the "an edit inside a step doesn't collapse it" half is a *frontend*
    property (AppTest never echoes an expander's open state back — a programmatic
    write reverts on the very next bare rerun regardless of app code), so it is
    verified in a real browser instead of here."""

    def test_go_to_step_opens_exactly_one(self):
        import streamlit as st

        target = wizard_shell.STEPS[0].id
        wizard_shell.go_to_step(target)
        opened = {
            s.id: st.session_state[wizard_shell.open_key(s.id)]
            for s in wizard_shell.STEPS
        }
        assert opened[target] is True
        assert not any(v for k, v in opened.items() if k != target)

    def test_open_keys_stay_clear_of_the_column_mapping_sweep(self):
        # tabs._collect_column_mapping sweeps every `col_map_*` key into the
        # saved config; an accordion flag must never land in a user's config.
        assert all(
            not wizard_shell.open_key(s.id).startswith("col_map_")
            for s in wizard_shell.STEPS
        )

    def test_a_changing_header_would_collapse_a_keyed_expander(self):
        """Why the status badge is not on the step header.

        Streamlit remounts a keyed expander at its default — collapsed — on the
        next run after its **label or icon** changes, whatever its key holds.
        With the badge passed as ``icon=``, an upload flipped step 1 from
        *action* to *done* and the step slammed shut the instant the file
        finished parsing: the DATA-19 symptom arriving through a new door,
        invisible to every test that only checked who *writes* the flag.

        The control case (a stable header) is what makes this a real finding
        rather than the known AppTest blind spot: it survives the run the
        varying one dies on. It still flips a run later, because AppTest has no
        frontend to echo the open state back — see the class docstring.
        """
        varying = AppTest.from_function(_varying_header_expander_app)
        stable = AppTest.from_function(_stable_header_expander_app)
        seen = {"varying": [], "stable": []}
        for name, at in (("varying", varying), ("stable", stable)):
            for _ in range(2):
                at.run()
                assert not at.exception, at.exception
                seen[name].append(at.session_state["wiz_open_probe"])

        assert seen["varying"] == [True, False], seen
        # Same two runs, header untouched → still open. The difference between
        # the two lists IS the bug.
        assert seen["stable"] == [True, True], seen

    def test_the_active_step_header_never_carries_the_status(self):
        """Structural guard for the above: `step_panel`'s expander call must not
        pass a status-derived ``icon=`` or interpolate the badge into its label."""
        source = pathlib.Path(wizard_shell.__file__).read_text(encoding="utf-8")
        body = source.split("def step_panel(", 1)[1].split("\ndef ", 1)[0]
        call = body.split("host.expander(", 1)[1]
        assert "icon=" not in call, "a changing icon remounts the expander closed"
        assert "badge(" not in call, "a changing label remounts the expander closed"

    def test_no_step_body_writes_an_open_flag(self):
        """The single rule the fix rests on: only the shell moves the accordion.

        A step body that wrote ``wiz_open_*`` would reintroduce exactly the
        DATA-19 bug (a step collapsing in response to its own edit), so this is
        asserted structurally rather than left to review.
        """
        source = pathlib.Path(wizard.__file__).read_text(encoding="utf-8")
        offenders = [
            stripped
            for line in source.splitlines()
            for stripped in [line.strip()]
            # Comments may name the key; only real code is an offender.
            if wizard_shell.OPEN_KEY_PREFIX in stripped
            and not stripped.startswith("#")
            and "wizard_shell." not in stripped
        ]
        assert not offenders, f"wizard.py writes accordion keys directly: {offenders}"


def _varying_header_expander_app():
    """A keyed expander whose icon changes on run 2 — the shipped-then-fixed bug."""
    import streamlit as st

    n = st.session_state.get("_n", 0) + 1
    st.session_state["_n"] = n
    if n == 1:
        st.session_state["wiz_open_probe"] = True
    st.expander(
        "1. Your data",
        key="wiz_open_probe",
        icon="🔵" if n == 1 else "✅",
        on_change="rerun",
    )


def _stable_header_expander_app():
    """The control: identical, but the header never changes."""
    import streamlit as st

    n = st.session_state.get("_n", 0) + 1
    st.session_state["_n"] = n
    if n == 1:
        st.session_state["wiz_open_probe"] = True
    st.expander("1. Your data", key="wiz_open_probe", on_change="rerun")


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
        # Regression: the wizard's setup restore silently did nothing
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
    """*Start from → A dataset you added*: copy, then Undo (2026-10-09)."""
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
