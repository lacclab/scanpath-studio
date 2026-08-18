"""DATA-29 — a trial-grain metadata table, the sibling of DATA-20's participant one.

The rules it inherits are the ones worth pinning: a table is never broadcast onto
the word/fixation frames, duplicate rows that *disagree* are dropped rather than
resolved, and an empty constraint is "no constraint" rather than "only the rows
this table happens to list".

What is new here is the **key**, which is the user's call: a trial id alone
(the table describes texts, and every reading of a text inherits its row) or a
reader *and* a trial id (the table describes readings).
"""

from __future__ import annotations

import pandas as pd

from scanpath_studio import metadata


def _table(**overrides) -> pd.DataFrame:
    base = pd.DataFrame(
        {
            "trial": ["t1", "t2"],
            "difficulty": ["easy", "hard"],
            "word_count": [120, 240],
        }
    )
    for column, values in overrides.items():
        base[column] = values
    return base


#: Two readers, two trials each — the pool a filter narrows.
KEYS = {("p1", "t1"), ("p1", "t2"), ("p2", "t1"), ("p2", "t2")}


class TestBuildingTheTable:
    def test_a_trial_keyed_table_registers_its_fields(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        assert built.keyed_by_participant is False
        assert built.names == ("difficulty", "word_count")
        assert built.field("difficulty").is_categorical
        assert built.field("word_count").is_numeric
        assert built.field("word_count").grain == metadata.GRAIN_TRIAL
        assert set(built.report.matched) == {"t1", "t2"}

    def test_a_reader_and_trial_keyed_table_keys_on_both(self):
        frame = pd.DataFrame(
            {
                "reader": ["p1", "p1", "p2"],
                "trial": ["t1", "t2", "t1"],
                "score": [0.9, 0.4, 0.5],
            }
        )
        built = metadata.build_trial_metadata(frame, "trial", "reader", keys=KEYS)
        assert built.keyed_by_participant is True
        assert built.key_columns == ("participant_id", "trial_id")
        assert set(built.report.matched) == {("p1", "t1"), ("p1", "t2"), ("p2", "t1")}
        # The reading the table forgot is named, not silently absent.
        assert built.report.only_in_data == (("p2", "t2"),)
        assert built.values_for("p1", "t2")["score"] == 0.4

    def test_disagreeing_duplicates_are_dropped_and_named(self):
        frame = pd.DataFrame(
            {"trial": ["t1", "t1", "t2"], "difficulty": ["easy", "hard", "hard"]}
        )
        built = metadata.build_trial_metadata(frame, "trial", keys=KEYS)
        assert built.report.conflicting == ("t1",)
        assert set(built.frame["trial_id"]) == {"t2"}

    def test_agreeing_duplicates_collapse_silently(self):
        frame = pd.DataFrame({"trial": ["t1", "t1"], "difficulty": ["easy", "easy"]})
        built = metadata.build_trial_metadata(frame, "trial", keys=KEYS)
        assert built.report.conflicting == ()
        assert len(built.frame) == 1


class TestFiltering:
    """`trials_matching` answers in the keys `data.filter_to_keys` already takes."""

    def test_no_constraint_is_none_not_the_listed_trials(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        assert metadata.trials_matching(built, {}, {}, keys=KEYS) is None

    def test_a_trial_keyed_selection_reaches_every_reading_of_it(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        matching = metadata.trials_matching(built, {"difficulty": ["easy"]}, keys=KEYS)
        assert matching == {("p1", "t1"), ("p2", "t1")}

    def test_a_reader_keyed_selection_narrows_to_that_reading(self):
        frame = pd.DataFrame(
            {
                "reader": ["p1", "p2"],
                "trial": ["t1", "t1"],
                "outcome": ["correct", "wrong"],
            }
        )
        built = metadata.build_trial_metadata(frame, "trial", "reader", keys=KEYS)
        matching = metadata.trials_matching(built, {"outcome": ["correct"]}, keys=KEYS)
        assert matching == {("p1", "t1")}

    def test_a_range_keeps_the_unmeasured(self):
        """UX-49's rule, one grain down: a range narrows, it does not exclude."""
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        keys = KEYS | {("p1", "t9"), ("p2", "t9")}
        matching = metadata.trials_matching(
            built, {}, {"word_count": (0.0, 150.0)}, keys=keys
        )
        # t1 is in range, t9 has no row at all — both kept; t2 is out of range.
        assert matching == {("p1", "t1"), ("p2", "t1"), ("p1", "t9"), ("p2", "t9")}

    def test_a_categorical_selection_excludes_the_unlisted(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        keys = KEYS | {("p1", "t9")}
        matching = metadata.trials_matching(built, {"difficulty": ["easy"]}, keys=keys)
        assert ("p1", "t9") not in matching


class TestProjection:
    def test_columns_land_on_combos_and_nowhere_else(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t1"],
            }
        )
        projected = metadata.project_trials(built, combos)
        assert list(projected["difficulty"]) == ["easy", "hard", "easy"]
        # The source frame is untouched — the projection is a copy.
        assert "difficulty" not in combos.columns

    def test_a_recorded_column_is_never_shadowed(self):
        built = metadata.build_trial_metadata(_table(), "trial", keys=KEYS)
        combos = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial_id": ["t1"],
                "difficulty": ["from the data"],
            }
        )
        projected = metadata.project_trials(built, combos)
        assert list(projected["difficulty"]) == ["from the data"]


class TestControlsAndRoundTrip:
    def test_options_and_bounds_come_from_the_loaded_trials(self):
        built = metadata.build_trial_metadata(
            _table(), "trial", keys={("p1", "t1"), ("p2", "t1")}
        )
        # t2 is in the table but not in the data, so it offers nothing.
        assert metadata.trial_options_for(built, "difficulty") == ["easy"]
        assert metadata.trial_bounds_for(built, "word_count") == (120.0, 120.0)

    def test_the_table_round_trips_through_save_and_restore(self):
        frame = pd.DataFrame({"reader": ["p1"], "trial": ["t1"], "score": [0.9]})
        built = metadata.build_trial_metadata(frame, "trial", "reader", keys=KEYS)
        restored = metadata.trial_from_payload(metadata.trial_to_payload(built))
        assert restored is not None
        assert restored.keyed_by_participant is True
        assert restored.names == ("score",)
        assert restored.values_for("p1", "t1")["score"] == 0.9

    def test_an_empty_payload_restores_to_nothing(self):
        assert metadata.trial_from_payload(None) is None
        assert metadata.trial_to_payload(None) is None
