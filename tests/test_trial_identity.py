"""VAL-7: warn when a trial id is under-specified.

The inverse of BUG-23. A Trial ID mapping that doesn't fully identify a reading
concatenates several readings into one `trial_id`, and the result renders as an
ordinary scanpath with a lot of regressions — plausible, and wrong. These tests
pin the three signals, the column that names the fix, and the two ways the check
must *not* fire: on correct data, and on a legitimate multipart trial.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.data import (
    diagnose_trial_identity,
    trial_identity_key,
    trial_identity_warning,
)


def _clean_words(n_trials=2):
    rows = []
    for t in range(n_trials):
        for w in range(3):
            rows.append(
                {
                    "participant_id": "p1",
                    "trial_id": f"t{t}",
                    "word_id": w,
                    "TRIAL_INDEX": t + 1,
                    "difficulty_level": "Adv",
                }
            )
    return pd.DataFrame(rows)


def _clean_fixations(n_trials=2):
    rows = []
    fid = 0
    for t in range(n_trials):
        for i in range(3):
            fid += 1
            rows.append(
                {
                    "participant_id": "p1",
                    "trial_id": f"t{t}",
                    "fixation_id": fid,
                    "timestamp_ms": 100 * fid,
                    "TRIAL_INDEX": t + 1,
                    "difficulty_level": "Adv",
                }
            )
    return pd.DataFrame(rows)


def _merged(frame):
    """Collapse two readings into one trial id — the failure under test."""
    return frame.assign(trial_id="t0")


class TestCorrectDataIsQuiet:
    def test_no_signal_fires(self):
        report = diagnose_trial_identity(_clean_words(), _clean_fixations())
        assert report["affected_trials"] == 0
        assert report["duplicate_word_rows"] == 0
        assert report["repeated_fixation_id_trials"] == 0
        assert report["backwards_clock_trials"] == 0
        assert report["multi_valued_columns"] == {}

    def test_there_is_no_warning_to_show(self):
        assert (
            trial_identity_warning(
                diagnose_trial_identity(_clean_words(), _clean_fixations())
            )
            is None
        )

    def test_empty_frames_are_an_all_clear_not_an_error(self):
        report = diagnose_trial_identity(pd.DataFrame(), pd.DataFrame())
        assert report["trials"] == 0
        assert trial_identity_warning(report) is None


class TestAMergedTrialIsCaught:
    @pytest.fixture
    def report(self):
        return diagnose_trial_identity(
            _merged(_clean_words()), _merged(_clean_fixations())
        )

    def test_the_words_table_shows_duplicate_rows(self, report):
        """The only *structural* signal: one row per word per reading is an
        invariant of the stimulus, not a heuristic — and it needs no clock."""
        assert report["duplicate_word_rows"] == 6  # three words, twice over

    def test_a_fixation_id_repeats(self, report):
        # Ids stay unique here, so this signal is quiet — see the dedicated test.
        assert report["repeated_fixation_id_trials"] == 0

    def test_a_column_that_should_be_constant_names_the_fix(self, report):
        assert report["multi_valued_columns"]["TRIAL_INDEX"] == 1

    def test_the_warning_leads_with_that_column(self, report):
        message = trial_identity_warning(report)
        assert "TRIAL_INDEX" in message
        assert "Trial ID mapping" in message

    def test_it_counts_readings_not_rows(self, report):
        assert report["affected_trials"] == 1
        assert report["trials"] == 1


class TestTheTwoFixationSignals:
    def test_a_repeated_fixation_id_is_caught(self):
        fixations = _clean_fixations()
        fixations.loc[3:, "fixation_id"] = [1, 2, 3]
        report = diagnose_trial_identity(pd.DataFrame(), _merged(fixations))
        assert report["repeated_fixation_id_trials"] == 1

    def test_a_backwards_clock_is_caught(self):
        """A clock jumping back mid-trial is a second recording starting, not a
        regression — which is what makes it say *what* merged."""
        fixations = _clean_fixations()
        fixations.loc[3:, "timestamp_ms"] = [100, 200, 300]
        report = diagnose_trial_identity(pd.DataFrame(), _merged(fixations))
        assert report["backwards_clock_trials"] == 1

    def test_they_work_without_a_words_table(self):
        report = diagnose_trial_identity(pd.DataFrame(), _merged(_clean_fixations()))
        assert report["duplicate_word_rows"] == 0
        assert report["multi_valued_columns"]["TRIAL_INDEX"] == 1


class TestMultipartIsNotAFalsePositive:
    """The gotcha that decides the implementation: a legitimate two-screen trial
    restarts `word_id` per screen, so the words signal reports duplicates that
    are correct data when the key is only (participant, trial)."""

    def _two_screens(self):
        rows = []
        for screen in ("s1", "s2"):
            for w in range(3):
                rows.append(
                    {
                        "participant_id": "p1",
                        "trial_id": "t0",
                        "screen_id": screen,
                        "word_id": w,
                    }
                )
        return pd.DataFrame(rows)

    def test_the_key_includes_the_screen(self):
        assert trial_identity_key(self._two_screens()) == [
            "participant_id",
            "trial_id",
            "screen_id",
        ]

    def test_restarted_word_ids_are_not_flagged(self):
        report = diagnose_trial_identity(self._two_screens(), pd.DataFrame())
        assert report["duplicate_word_rows"] == 0
        assert report["affected_trials"] == 0

    def test_grouping_by_trial_alone_would_have_flagged_them(self):
        """Pins the reason for the screen in the key — drop it and the same data
        reports three spurious duplicates."""
        without_screen = self._two_screens().drop(columns=["screen_id"])
        report = diagnose_trial_identity(without_screen, pd.DataFrame())
        assert report["duplicate_word_rows"] == 6


class TestOnTheBundledDemo:
    """The measurement the item was written from, as a regression."""

    @staticmethod
    def _normalized(trial_columns=None):
        from scanpath_studio.data import (
            harmonize_frames,
            load_sample_data,
            normalize_fixations,
            normalize_words,
            propose_fix_schema,
            propose_word_schema,
        )

        raw_words, raw_fixations, *_ = load_sample_data()
        word_schema = propose_word_schema(raw_words)
        fix_schema = propose_fix_schema(raw_fixations)
        if trial_columns is not None:
            word_schema["trial"] = list(trial_columns)
            fix_schema["trial"] = list(trial_columns)
        words = normalize_words(raw_words, word_schema)
        fixations = normalize_fixations(raw_fixations, fix_schema)
        return harmonize_frames(words, fixations)

    def test_the_correct_mapping_is_clean(self):
        words, fixations = self._normalized()
        report = diagnose_trial_identity(words, fixations)
        assert trial_identity_warning(report) is None, report

    def test_an_under_specified_mapping_is_caught(self):
        """Drop the columns that separate the readings from the Trial ID —
        a composite mapping, which `_disambiguate_repeated_readings` treats as
        authoritative and does *not* rescue — and every signal lights up."""
        words, fixations = self._normalized(["article_id", "article_batch"])
        report = diagnose_trial_identity(words, fixations)
        assert report["duplicate_word_rows"] > 0
        assert report["repeated_fixation_id_trials"] > 0
        assert report["backwards_clock_trials"] > 0
        assert "TRIAL_INDEX" in report["multi_valued_columns"]
        # The numerator can never exceed the denominator: both are counted over
        # the union of trial keys across the two frames.
        assert report["affected_trials"] <= report["trials"]
        assert trial_identity_warning(report)


@pytest.mark.timeout(120)
def test_data_inspection_reports_the_verdict():
    """The all-clear renders too — a section that only appears when something is
    wrong reads as an error box, and "we checked and it's fine" is the answer
    the user gets most of the time."""
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from tests.conftest import APP_SCRIPT, pin_data_view

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    assert not at.exception, at.exception
    # Computed on the unfiltered frames, before the view renders.
    assert at.session_state["_trial_identity_report"]["trials"] > 0

    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    # UX-52 round 3 promoted this back to a section of its own on the Data page
    # (round 1 had demoted it to an h5 inside "What's in this dataset"): it
    # carries a verdict, and the fix it names is an edit to the Column mapping
    # section right above it. The evidence table stays folded into "What was
    # checked"; the verdict itself is in the open.
    headings = [h.value for h in at.subheader]
    assert any("Trial identity" in h for h in headings), headings
    assert any("single reading" in s.value for s in at.success)
    assert any(e.label == "What was checked" for e in at.expander)


class TestTheVerdictIsRaisedWhereTheMappingIsChosen:
    """The verdict used to ride a page-wide ⚠️ banner, above every view, on every
    run, for as long as the dataset stayed loaded — a permanent warning about a
    decision that is made exactly twice: when a dataset is added, and when its
    mapping is edited. It is now a modal raised at those two moments.
    """

    def test_adding_a_dataset_asks_for_the_check(self):
        import streamlit as st

        from scanpath_studio import wizard
        from scanpath_studio.constants import TRIAL_IDENTITY_CHECK_KEY

        st.session_state.clear()
        st.session_state["_wizard_finalize_payload"] = {
            "words": _clean_words(),
            "fixations": _clean_fixations(),
            "raw_gaze": pd.DataFrame(),
        }
        st.session_state["wizard_dataset_name"] = "My corpus"
        wizard._finalize_wizard_dataset()

        assert st.session_state[TRIAL_IDENTITY_CHECK_KEY] == "add"
        st.session_state.clear()

    def test_saving_an_edited_mapping_asks_for_the_check(self):
        """Source-level: `_apply_remap` needs a whole stored dataset and the
        editor's pending schemas to run. What must not silently regress is that
        saving still asks."""
        import inspect

        from scanpath_studio.tabs import _apply_remap

        source = inspect.getsource(_apply_remap)
        assert 'st.session_state[TRIAL_IDENTITY_CHECK_KEY] = "edit"' in source

    def test_main_raises_the_modal_and_no_longer_writes_a_banner(self):
        import inspect

        from scanpath_studio import app

        source = inspect.getsource(app.main)
        assert "_trial_identity_alert_dialog(" in source
        assert "TRIAL_IDENTITY_CHECK_KEY" in source
        # The banner it replaced.
        assert "menu.notices.warning" not in source

    def test_the_modal_offers_the_mapping_and_a_way_to_keep_it(self):
        import inspect

        from scanpath_studio import app

        source = inspect.getsource(app._trial_identity_alert_dialog)
        assert "trial_identity_alert_edit" in source
        assert "trial_identity_alert_keep" in source
        # Return values, never `on_click`: a dialog body is a fragment, so a
        # callback here would rerun the modal and leave the page behind it
        # untouched (the BUG-36 trap `_leave_dataset_editor_dialog` fell into).
        assert "on_click=" not in source
        # Editing means the ✏️ Edit dataset screen, focused on the mapping.
        assert "_open_mapping_editor()" in source

    def test_opening_the_editor_focuses_the_open_datasets_mapping(self):
        import streamlit as st

        from scanpath_studio import app
        from scanpath_studio.constants import (
            DATASET_EDITOR_OPEN_KEY,
            FOCUS_MAPPING_KEY,
        )

        st.session_state.clear()
        st.session_state["data_source_choice"] = "My corpus"
        app._open_mapping_editor()

        assert st.session_state[DATASET_EDITOR_OPEN_KEY] is True
        assert st.session_state[FOCUS_MAPPING_KEY] == "My corpus"
        st.session_state.clear()
