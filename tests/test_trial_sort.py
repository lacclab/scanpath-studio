"""UX-10: ordering the trial pool by reader / text / condition / computed stats."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.utils import (
    TRIAL_SORT_DEFAULT,
    sort_trial_options,
    trial_sort_keys,
)


@pytest.fixture
def combos() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "participant_id": "p2",
                "trial_id": "t1",
                "text_id": "b",
                "is_correct": True,
            },
            {
                "participant_id": "p1",
                "trial_id": "t2",
                "text_id": "a",
                "is_correct": False,
            },
            {
                "participant_id": "p3",
                "trial_id": "t3",
                "text_id": "c",
                "is_correct": True,
            },
        ]
    )


@pytest.fixture
def fixations() -> pd.DataFrame:
    """t1: 1 fixation (100 ms) · t2: 3 (600 ms total) · t3: 2 (500 ms total)."""
    rows = (
        [("p2", "t1", 100.0)]
        + [("p1", "t2", d) for d in (100.0, 200.0, 300.0)]
        + [("p3", "t3", d) for d in (200.0, 300.0)]
    )
    return pd.DataFrame(rows, columns=["participant_id", "trial_id", "duration_ms"])


class TestTrialSortKeys:
    def test_computed_stats_are_offered_when_the_frame_is_there(
        self, combos, fixations
    ):
        keys = trial_sort_keys(combos, "trial_id", fixations=fixations)
        assert "Fixations (n)" in keys
        assert "Reading time (s)" in keys
        assert keys["Fixations (n)"]["t2"] == 3
        assert keys["Reading time (s)"]["t2"] == pytest.approx(0.6)
        assert keys["Mean fixation (ms)"]["t3"] == pytest.approx(250.0)

    def test_computed_stats_are_dropped_without_their_frame(self, combos):
        keys = trial_sort_keys(combos, "trial_id")
        assert "Fixations (n)" not in keys
        assert "Words (n)" not in keys

    def test_trial_level_columns_are_offered(self, combos, fixations):
        keys = trial_sort_keys(combos, "trial_id", fixations=fixations)
        assert keys["Participant id"]["t1"] == "p2"
        assert keys["Text id"]["t2"] == "a"
        assert bool(keys["Is correct"]["t3"]) is True

    def test_a_column_that_varies_within_a_trial_is_not_offered(self, fixations):
        """Two rows for the same trial disagreeing on a column can't order it."""
        combos = pd.DataFrame(
            [
                {"participant_id": "p1", "trial_id": "t1", "text_id": "a"},
                {"participant_id": "p1", "trial_id": "t1", "text_id": "b"},
            ]
        )
        assert "Text id" not in trial_sort_keys(combos, "trial_id")

    def test_empty_combos_still_returns_the_computed_stats(self, fixations):
        keys = trial_sort_keys(pd.DataFrame(), "trial_id", fixations=fixations)
        assert "Fixations (n)" in keys
        assert "Participant id" not in keys


class TestSortTrialOptions:
    def test_default_is_id_order(self, combos, fixations):
        assert sort_trial_options(["t3", "t1", "t2"], None) == ["t1", "t2", "t3"]

    def test_sorts_by_a_numeric_key(self, combos, fixations):
        keys = trial_sort_keys(combos, "trial_id", fixations=fixations)
        options = ["t1", "t2", "t3"]
        assert sort_trial_options(options, keys["Fixations (n)"]) == ["t1", "t3", "t2"]
        assert sort_trial_options(options, keys["Fixations (n)"], descending=True) == [
            "t2",
            "t3",
            "t1",
        ]

    def test_sorts_by_a_text_key(self, combos, fixations):
        keys = trial_sort_keys(combos, "trial_id", fixations=fixations)
        assert sort_trial_options(["t1", "t2", "t3"], keys["Text id"]) == [
            "t2",
            "t1",
            "t3",
        ]

    def test_unranked_trials_sort_last_in_both_directions(self):
        key = pd.Series({"t1": 5.0, "t2": 1.0})
        options = ["t1", "t2", "t9"]
        assert sort_trial_options(options, key) == ["t2", "t1", "t9"]
        assert sort_trial_options(options, key, descending=True) == ["t1", "t2", "t9"]

    def test_nan_counts_as_unranked(self):
        key = pd.Series({"t1": 5.0, "t2": float("nan")})
        assert sort_trial_options(["t1", "t2"], key) == ["t1", "t2"]

    def test_ties_break_on_the_trial_id_so_the_order_is_stable(self):
        key = pd.Series({"tb": 1.0, "ta": 1.0, "tc": 1.0})
        assert sort_trial_options(["tc", "tb", "ta"], key) == ["ta", "tb", "tc"]

    def test_mixed_numeric_and_text_values_do_not_raise(self):
        key = pd.Series({"t1": 3, "t2": "later", "t3": 1})
        assert sort_trial_options(["t1", "t2", "t3"], key) == ["t3", "t1", "t2"]


def test_default_label_is_stable():
    """The picker seeds its state to this string; renaming it silently resets."""
    assert TRIAL_SORT_DEFAULT == "Trial id"
