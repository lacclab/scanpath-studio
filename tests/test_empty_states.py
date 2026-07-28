"""UX-7: empty states that name the cause and offer the next action.

(a) The filters emptied the trial pool — which filter, and how many trials it
drops on its own. (b) A public corpus isn't on disk yet.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.data import count_trials, diagnose_filters, filter_trials


@pytest.fixture
def pool() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Six trials: 3 participants × 2 difficulty levels."""
    rows = [
        {"participant_id": p, "trial_id": f"{p}_{d}", "difficulty_level": d, "x": 1.0}
        for p in ("p1", "p2", "p3")
        for d in ("Adv", "Ele")
    ]
    frame = pd.DataFrame(rows)
    return frame, frame


class TestCountTrials:
    def test_counts_distinct_participant_trial_pairs(self, pool):
        assert count_trials(*pool) == 6

    def test_unions_both_frames(self, pool):
        words, _ = pool
        empty = pd.DataFrame()
        assert count_trials(words, empty) == 6
        assert count_trials(empty, words) == 6

    def test_empty_everywhere_is_zero(self):
        assert count_trials(pd.DataFrame(), pd.DataFrame()) == 0

    def test_frames_without_the_key_columns_are_skipped(self):
        assert count_trials(pd.DataFrame({"x": [1, 2]}), pd.DataFrame()) == 0


class TestDiagnoseFilters:
    def test_names_the_filter_that_empties_the_pool_on_its_own(self, pool):
        words, fixations = pool
        report = diagnose_filters(
            words,
            fixations,
            [
                ("Participant", lambda w, f: filter_trials(w, f, participants=["p1"])),
                (
                    "Difficulty",
                    lambda w, f: filter_trials(
                        w, f, metadata={"difficulty_level": {"Nope"}}
                    ),
                ),
            ],
        )
        by_label = {row["label"]: row for row in report}
        assert by_label["Participant"]["kept"] == 2
        assert by_label["Participant"]["empties"] is False
        assert by_label["Difficulty"]["kept"] == 0
        assert by_label["Difficulty"]["empties"] is True

    def test_each_filter_is_measured_against_the_unfiltered_pool(self, pool):
        """Not cumulatively — otherwise the report blames whichever ran last."""
        words, fixations = pool
        report = diagnose_filters(
            words,
            fixations,
            [
                ("A", lambda w, f: filter_trials(w, f, participants=["p1"])),
                ("B", lambda w, f: filter_trials(w, f, participants=["p2"])),
            ],
        )
        assert [row["kept"] for row in report] == [2, 2]
        assert [row["dropped"] for row in report] == [4, 4]

    def test_a_lethal_combination_leaves_every_step_non_empty(self, pool):
        """p1 ∩ Ele is fine; p1 ∩ 'no such difficulty' is the empties case above.
        Here each step keeps trials, so the caller reports the intersection."""
        words, fixations = pool
        report = diagnose_filters(
            words,
            fixations,
            [
                ("Participant", lambda w, f: filter_trials(w, f, participants=["p1"])),
                (
                    "Difficulty",
                    lambda w, f: filter_trials(
                        w, f, metadata={"difficulty_level": {"Adv"}}
                    ),
                ),
            ],
        )
        assert not any(row["empties"] for row in report)

    def test_no_steps_is_an_empty_report(self, pool):
        assert diagnose_filters(*pool, []) == []

    def test_a_step_carries_the_session_keys_that_reset_it(self, pool):
        """So the panel can offer "clear just this filter" — the report is the
        only place that knows which filter a given row *is*."""
        words, fixations = pool
        (row,) = diagnose_filters(
            words,
            fixations,
            [
                (
                    "Participant",
                    lambda w, f: filter_trials(w, f, participants=["p1"]),
                    ("filter_participants",),
                )
            ],
        )
        assert row["keys"] == ("filter_participants",)

    def test_a_step_without_keys_still_works(self, pool):
        (row,) = diagnose_filters(
            *pool, [("A", lambda w, f: filter_trials(w, f, participants=["p1"]))]
        )
        assert row["keys"] == ()


class TestClearOneTrialFilter:
    """UX-7 follow-up: clearing a single culprit, not everything."""

    def test_drops_only_the_named_key(self):
        import streamlit as st

        from scanpath_studio.controls import clear_trial_filter

        st.session_state["filter_participants"] = ["p1"]
        st.session_state["filter_difficulty_level"] = ["Adv"]
        st.session_state["_trial_filters"] = {"participants": ["p1"]}

        clear_trial_filter("filter_participants")

        assert "filter_participants" not in st.session_state
        assert st.session_state["filter_difficulty_level"] == ["Adv"]
        # The derived cache must go too, or the same run keeps filtering.
        assert "_trial_filters" not in st.session_state

    def test_an_absent_key_is_not_an_error(self):
        from scanpath_studio.controls import clear_trial_filter

        clear_trial_filter("filter_never_set")  # must not raise


class TestFilterResetKeys:
    """The Narrow-by *Text* multiselect lands in `metadata` under the text
    column but lives under `filter_text_id` — so the reset key can't be derived
    from the column name, and the filter result has to carry it."""

    def test_metadata_keys_maps_each_column_to_its_widget_key(self):
        import streamlit as st

        from scanpath_studio.app import _filter_diagnosis_steps

        st.session_state.clear()
        steps = _filter_diagnosis_steps(
            {
                "participants": ["p1"],
                "metadata": {"paragraph_id": {"1"}, "difficulty_level": {"Adv"}},
                "metadata_keys": {"paragraph_id": "filter_text_id"},
                "favorites_only": True,
                "required_tags": ["good"],
                "excluded_tags": ["bad"],
            }
        )
        assert [s[2] for s in steps] == [
            ("filter_participants",),
            ("filter_text_id",),  # NOT filter_paragraph_id
            ("filter_difficulty_level",),  # falls back to the column name
            ("filter_favorites",),
            ("filter_req_tags",),
            ("filter_exc_tags",),
        ]


class TestClearTrialFilters:
    def test_drops_every_filter_key_and_the_derived_results(self):
        import streamlit as st

        from scanpath_studio.controls import clear_trial_filters

        st.session_state["filter_participants"] = ["p1"]
        st.session_state["filter_difficulty_level"] = ["Adv"]
        st.session_state["filter_favorites"] = True
        st.session_state["_trial_filters"] = {"participants": ["p1"]}
        st.session_state["_trial_filters_raw"] = {"filter_participants": ["p1"]}
        st.session_state["global_show_fix"] = True  # unrelated — must survive

        clear_trial_filters()

        assert not [k for k in st.session_state if str(k).startswith("filter_")]
        assert "_trial_filters" not in st.session_state
        assert "_trial_filters_raw" not in st.session_state
        assert st.session_state["global_show_fix"] is True


class TestDatasetUnavailableState:
    """UX-7(b): a missing corpus is recorded for the main-area empty state."""

    def test_missing_download_corpus_offers_the_download_inline(self):
        import streamlit as st

        from scanpath_studio import app

        st.session_state.pop(app._UNAVAILABLE_KEY, None)
        ready = app._dataset_access_status(
            st,
            root="/nowhere",
            present=False,
            download=lambda root: None,
            size_hint="~45 MB",
            key_prefix="potec",
            label="PoTeC",
        )
        note = st.session_state[app._UNAVAILABLE_KEY]
        assert ready is False
        assert note["label"] == "PoTeC"
        assert note["size_hint"] == "~45 MB"
        assert note["download"] is not None

    def test_non_downloadable_corpus_explains_the_folder_instead(self):
        import streamlit as st

        from scanpath_studio import app

        st.session_state.pop(app._UNAVAILABLE_KEY, None)
        app._dataset_access_status(
            st, root="/nowhere", present=False, label="MultiplEYE"
        )
        note = st.session_state[app._UNAVAILABLE_KEY]
        assert note["download"] is None
        assert "Expected files" in note["action"]

    def test_a_present_corpus_records_nothing(self):
        import streamlit as st

        from scanpath_studio import app

        st.session_state.pop(app._UNAVAILABLE_KEY, None)
        assert app._dataset_access_status(st, root="/here", present=True) is True
        assert app._UNAVAILABLE_KEY not in st.session_state
