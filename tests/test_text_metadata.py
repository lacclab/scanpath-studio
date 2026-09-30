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


class TestChips:
    """DATA-45: a text field put in the chips renders its value above the plot.

    `tabs._chip_value_and_uniqueness` fell back to the participant and trial
    tables but had no branch for the text table, so the value resolved to None
    and the chip was skipped without a word.
    """

    @staticmethod
    def _attach(monkeypatch, built):
        from scanpath_studio import tabs

        monkeypatch.setattr(tabs, "active_participant_metadata", lambda: None)
        monkeypatch.setattr(metadata, "active_trials", lambda: None)
        monkeypatch.setattr(metadata, "active_texts", lambda: built)
        return tabs

    def test_a_text_field_resolves_through_the_trial_s_text_id(self, monkeypatch):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        tabs = self._attach(monkeypatch, built)
        fixations = pd.DataFrame(
            {"participant_id": ["p1"] * 2, "trial_id": ["t1"] * 2, "text_id": "b"}
        )
        value, trial_level = tabs._chip_value_and_uniqueness(
            "genre", None, fixations, "p1"
        )
        assert (value, trial_level) == ("news", True)

    def test_unique_text_id_wins_like_the_by_text_filter(self, monkeypatch):
        """The id the *By text* filter and `combos["text_id"]` use."""
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        tabs = self._attach(monkeypatch, built)
        words = pd.DataFrame({"trial_id": ["t1"], "text_id": ["1"]})
        fixations = pd.DataFrame(
            {"trial_id": ["t1"], "text_id": ["1"], "unique_text_id": ["a"]}
        )
        value, _ = tabs._chip_value_and_uniqueness("genre", words, fixations, "p1")
        assert value == "fiction"

    def test_a_recorded_column_still_wins(self, monkeypatch):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        tabs = self._attach(monkeypatch, built)
        fixations = pd.DataFrame({"text_id": ["b"], "genre": ["poetry"]})
        value, _ = tabs._chip_value_and_uniqueness("genre", None, fixations, "p1")
        assert value == "poetry"

    def test_an_unlisted_text_renders_no_chip(self, monkeypatch):
        built = metadata.build_text_metadata(_table(), "text", keys=KEYS)
        tabs = self._attach(monkeypatch, built)
        fixations = pd.DataFrame({"text_id": ["zzz"]})
        chip = tabs._chip_value_and_uniqueness("genre", None, fixations, "p1")
        assert chip == (None, True)

    def test_the_chip_is_drawn_in_the_running_app(self):
        """End to end: attach a text table to the demo, pick its field."""
        from streamlit.testing.v1 import AppTest

        from tests.conftest import APP_SCRIPT

        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        texts = [str(t) for t in at.multiselect(key="filter_text_id").options]
        assert texts, "the demo should offer texts to narrow by"
        frame = pd.DataFrame({"text_id": texts, "genre": ["news"] * len(texts)})
        at.session_state[metadata.TEXT_SESSION_KEY] = metadata.build_text_metadata(
            frame, "text_id", source_name="texts.csv", keys=set(texts)
        )
        at.session_state[metadata.TEXT_RAW_SESSION_KEY] = frame
        at.run(timeout=90)
        assert not at.exception, at.exception

        at.session_state["trial_chip_fields"] = ["participant_id", "genre"]
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert "genre" in at.session_state["trial_chip_fields"]
        strip = " ".join(m.value for m in at.markdown)
        assert "Genre = news" in strip, strip[:400]
