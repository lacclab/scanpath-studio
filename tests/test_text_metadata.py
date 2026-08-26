"""A text-grain metadata table — the third grain, sibling of DATA-20's
participant table and DATA-29's trial table.

Flat like the participant table (one dimension, ``text_id``, never paired with
a reader — a text is a stimulus, not something one reader owns), but its id
can be composite like the trial table's, built the same way
(``data.trial_id_series``, joined with ``_``). The core rules — never
broadcast onto words/fixations, disagreeing duplicates dropped and named
rather than resolved, an empty constraint is "no constraint" — are the same
ones pinned in ``test_metadata.py``/``test_trial_metadata.py``.
"""

from __future__ import annotations

import pandas as pd

from scanpath_studio import metadata


def _table(**overrides) -> pd.DataFrame:
    base = pd.DataFrame(
        {
            "text": ["a", "b"],
            "genre": ["fiction", "news"],
            "word_count": [800, 400],
        }
    )
    for column, values in overrides.items():
        base[column] = values
    return base


#: Three texts in the loaded data — the pool a filter narrows.
KEYS = {"a", "b", "c"}


class TestBuildingTheTable:
    def test_a_text_keyed_table_registers_its_fields(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        assert built.names == ("genre", "word_count")
        assert built.field("genre").is_categorical
        assert built.field("word_count").is_numeric
        assert built.field("word_count").grain == metadata.GRAIN_TEXT
        assert set(built.report.matched) == {"a", "b"}
        assert built.report.only_in_data == ("c",)

    def test_a_composite_id_is_built_like_the_trial_table_s(self):
        frame = pd.DataFrame(
            {"batch": ["1", "1", "2"], "item": ["1", "2", "1"], "v": [10, 20, 30]}
        )
        built = metadata.build_text_metadata(frame, ["batch", "item"])
        assert list(built.frame["text_id"]) == ["1_1", "1_2", "2_1"]
        assert built.text_column == "batch + item"

    def test_disagreeing_duplicates_are_dropped_and_named(self):
        frame = pd.DataFrame(
            {"text": ["a", "a", "b"], "genre": ["fiction", "news", "news"]}
        )
        built = metadata.build_text_metadata(frame, "text", keys=KEYS)
        assert built.report.conflicting == ("a",)
        assert set(built.frame["text_id"]) == {"b"}

    def test_agreeing_duplicates_collapse_silently(self):
        frame = pd.DataFrame({"text": ["a", "a"], "genre": ["fiction", "fiction"]})
        built = metadata.build_text_metadata(frame, "text", keys=KEYS)
        assert built.report.conflicting == ()
        assert len(built.frame) == 1

    def test_nothing_matched_still_names_both_sides(self):
        built = metadata.build_text_metadata(_table(), "text", keys={"z"})
        assert built.report.matched == ()
        assert set(built.report.only_in_data) == {"z"}
        assert set(built.report.only_in_table) == {"a", "b"}

    def test_no_id_column_returns_the_empty_sentinel(self):
        built = metadata.build_text_metadata(_table(), "missing_column", keys=KEYS)
        assert built.fields == ()
        assert built.frame.empty


class TestFiltering:
    def test_no_constraint_is_none_not_the_listed_texts(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        assert metadata.texts_matching(built, {}, {}) is None

    def test_a_categorical_selection_narrows_to_matching_texts(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        matching = metadata.texts_matching(built, {"genre": ["fiction"]})
        assert matching == {"a"}

    def test_a_range_keeps_the_unmeasured(self):
        """UX-49's rule, this grain too: a range narrows, it does not exclude."""
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        matching = metadata.texts_matching(built, {}, {"word_count": (0.0, 500.0)})
        # b is in range; c has no row at all — both kept; a is out of range.
        assert matching == {"b", "c"}


class TestProjection:
    def test_columns_land_on_combos_and_nowhere_else(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        combos = pd.DataFrame({"text_id": ["a", "b"]})
        projected = metadata.project_texts(built, combos)
        assert list(projected["genre"]) == ["fiction", "news"]
        # The source frame is untouched — the projection is a copy.
        assert "genre" not in combos.columns

    def test_a_recorded_column_is_never_shadowed(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        combos = pd.DataFrame({"text_id": ["a"], "genre": ["from the data"]})
        projected = metadata.project_texts(built, combos)
        assert list(projected["genre"]) == ["from the data"]


class TestControlsAndRoundTrip:
    def test_options_and_bounds_come_from_the_loaded_texts(self):
        built = metadata.build_text_metadata(_table(), "text", keys={"a"})
        # b is in the table but not in the data, so it offers nothing.
        assert metadata.text_options_for(built, "genre") == ["fiction"]
        assert metadata.text_bounds_for(built, "word_count") is None

    def test_the_table_round_trips_through_save_and_restore(self):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        restored = metadata.text_from_payload(metadata.text_to_payload(built))
        assert restored is not None
        assert restored.names == ("genre", "word_count")
        assert restored.values_for("a")["genre"] == "fiction"

    def test_an_empty_payload_restores_to_nothing(self):
        assert metadata.text_from_payload(None) is None
        assert metadata.text_to_payload(None) is None
