"""UX-10: ordering the trial pool by reader / text / condition / computed stats."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

from scanpath_studio.utils import (  # noqa: E402
    TRIAL_SORT_DEFAULT,
    _merge_trial_level_sources,
    format_sort_value,
    sort_trial_options,
    trial_sort_keys,
)


def test_trial_metadata_merge_does_not_warn_on_its_first_source():
    source = {"condition": pd.Series(["easy"], index=["t1"])}
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        merged = _merge_trial_level_sources([source])
    assert merged["condition"].to_dict() == {"t1": "easy"}


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

    def test_discovers_metadata_before_the_combo_projection_drops_it(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "text_id": ["a", "b"],
            }
        )
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1", "p1"],
                "trial_id": ["t1", "t1", "t2", "t2"],
                "word_index": [1, 2, 1, 2],
                "difficulty_band": ["easy", "easy", "hard", "hard"],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t2", "t2"],
                "duration_ms": [100, 150, 200],
                "device_batch": [3, 7, 7],
            }
        )

        keys = trial_sort_keys(combos, "trial_id", words=words, fixations=fixations)

        assert keys["Difficulty band"].to_dict() == {"t1": "easy", "t2": "hard"}
        assert keys["Device batch"].to_dict() == {"t1": 3, "t2": 7}
        assert "Word index" not in keys
        assert "Duration ms" not in keys

    def test_participant_scope_prevents_repeated_trial_ids_from_colliding(self):
        # This mirrors the report: the picker has already been narrowed to p1,
        # while its source tables still contain another participant using the
        # same plain trial labels with different metadata.
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
            }
        )
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t2", "t1", "t2"],
                "condition": ["A", "B", "B", "A"],
            }
        )

        keys = trial_sort_keys(combos, "trial_id", words=words)

        assert keys["Condition"].to_dict() == {"t1": "A", "t2": "B"}
        assert sort_trial_options(["t1", "t2"], keys["Condition"]) == ["t1", "t2"]

    def test_matching_cross_table_metadata_is_merged_once(self):
        combos = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "trial_id": ["t1", "t2"]}
        )
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "session": ["s1", None],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "session": ["s1", "s2"],
            }
        )

        keys = trial_sort_keys(combos, "trial_id", words=words, fixations=fixations)

        assert list(keys).count("Session") == 1
        assert keys["Session"].to_dict() == {"t1": "s1", "t2": "s2"}

    def test_cross_table_conflict_is_not_silently_resolved(self):
        combos = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "trial_id": ["t1", "t2"]}
        )
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "genre": ["news", "fiction"],
            }
        )
        fixations = words.assign(genre=["news", "essay"])

        keys = trial_sort_keys(combos, "trial_id", words=words, fixations=fixations)

        assert "Genre" not in keys

    def test_unique_trial_identity_drives_metadata_and_computed_stats(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["u1", "u2"],
                "unique_trial_id": ["u1", "u2"],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["reused", "reused", "reused"],
                "unique_trial_id": ["u1", "u2", "u2"],
                "duration_ms": [100, 200, 300],
                "is_correct": [True, False, False],
            }
        )

        keys = trial_sort_keys(combos, "unique_trial_id", fixations=fixations)

        assert keys["Fixations (n)"].to_dict() == {"u1": 1.0, "u2": 2.0}
        assert keys["Is correct"].to_dict() == {"u1": True, "u2": False}

    def test_within_trial_variation_and_non_metadata_payloads_are_excluded(self):
        combos = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "trial_id": ["t1", "t2"]}
        )
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 4,
                "trial_id": ["t1", "t1", "t2", "t2"],
                "condition": ["A", "B", "C", "C"],
                "source_file": ["/private/a.csv"] * 2 + ["/private/b.csv"] * 2,
                "image_x": [100, 100, 200, 200],
                "notes": ["word " * 30] * 4,
            }
        )

        keys = trial_sort_keys(combos, "trial_id", words=words)

        assert "Condition" not in keys
        assert "Source file" not in keys
        assert "Image x" not in keys
        assert "Notes" not in keys


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


def _sortable_picker_app():
    """Render the trial picker over three trials with distinct fixation counts."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.utils import build_combo_options, select_trial

    rows = []
    for trial, n in (("t_a", 5), ("t_b", 12), ("t_c", 2)):
        rows += [
            {
                "participant_id": "p1",
                "trial_id": trial,
                "text_id": "x",
                "duration_ms": 200.0,
            }
        ] * n
    fixations = pd.DataFrame(rows)
    combos, _, _ = build_combo_options(fixations)
    select_trial(combos, key_prefix="single", fixations=fixations)
    st.session_state["_picker_rendered"] = True


def _participant_scoped_metadata_picker_app():
    """Narrow to p1 while the source frames retain p2's repeated trial ids."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.utils import build_combo_options, select_trial

    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t2", "t1", "t2"],
            "duration_ms": [100.0, 100.0, 100.0, 100.0],
        }
    )
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t2", "t1", "t2"],
            "condition": ["B", "A", "A", "B"],
        }
    )
    combos, _, _ = build_combo_options(fixations)
    narrowed = combos[combos["participant_id"] == "p1"]
    select_trial(
        narrowed,
        key_prefix="single",
        words=words,
        fixations=fixations,
    )
    st.session_state["_picker_rendered"] = True


class TestSortValueIsVisibleInThePicker:
    """UX-10 follow-up: sorting with the key hidden just looks shuffled."""

    def _picker(self, at):
        return next(s for s in at.selectbox if s.label.startswith("**Select Trial**"))

    def test_unsorted_shows_plain_ids_and_a_plain_label(self):
        at = AppTest.from_function(_sortable_picker_app)
        at.run(timeout=20)
        assert not at.exception, at.exception
        picker = self._picker(at)
        assert picker.label == "**Select Trial**"
        assert [picker.format_func(o) for o in picker.options] == ["t_a", "t_b", "t_c"]

    def test_sorting_puts_the_value_on_every_option_and_names_the_key(self):
        at = AppTest.from_function(_sortable_picker_app)
        at.run(timeout=20)
        at.selectbox(key="single_trial_sort").set_value("Fixations (n)")
        at.run(timeout=20)
        assert not at.exception, at.exception
        picker = self._picker(at)
        # The label says what the order *is* — ascending by fixation count.
        assert picker.label == "**Select Trial**  ·  by Fixations (n) ↑"
        assert [picker.format_func(o) for o in picker.options] == [
            "t_c  ·  2",
            "t_a  ·  5",
            "t_b  ·  12",
        ]

    def test_descending_flips_the_order_and_the_arrow(self):
        at = AppTest.from_function(_sortable_picker_app)
        at.run(timeout=20)
        at.selectbox(key="single_trial_sort").set_value("Fixations (n)")
        at.run(timeout=20)
        at.checkbox(key="single_trial_sort_desc").check()
        at.run(timeout=20)
        picker = self._picker(at)
        assert picker.label.endswith("↓")
        assert [picker.format_func(o) for o in picker.options] == [
            "t_b  ·  12",
            "t_a  ·  5",
            "t_c  ·  2",
        ]

    def test_participant_narrowing_keeps_metadata_sort_fields(self):
        at = AppTest.from_function(_participant_scoped_metadata_picker_app)
        at.run(timeout=20)
        assert not at.exception, at.exception
        sorter = at.selectbox(key="single_trial_sort")
        assert "Condition" in sorter.options

        sorter.set_value("Condition")
        at.run(timeout=20)

        picker = self._picker(at)
        assert [picker.format_func(o) for o in picker.options] == [
            "t2  ·  A",
            "t1  ·  B",
        ]


def test_default_label_is_stable():
    """The picker seeds its state to this string; renaming it silently resets."""
    assert TRIAL_SORT_DEFAULT == "Trial ID"


class TestFormatSortValue:
    """An ordering whose key is invisible just looks shuffled, so every picker
    option carries its value — which means the formatting has to stay short."""

    def test_a_whole_number_keeps_a_thousands_separator(self):
        assert format_sort_value(1204) == "1,204"
        assert format_sort_value(1204.0) == "1,204"

    def test_a_fraction_gets_one_decimal(self):
        assert format_sort_value(23.456) == "23.5"

    def test_a_boolean_reads_as_words(self):
        assert format_sort_value(True) == "Yes"
        assert format_sort_value(False) == "No"

    def test_missing_is_an_em_dash_not_nan(self):
        assert format_sort_value(None) == "—"
        assert format_sort_value(float("nan")) == "—"

    def test_text_passes_through(self):
        assert format_sort_value("Adv") == "Adv"
