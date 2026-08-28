"""ENG-37: `metadata.py`'s three grains, through their pure helpers.

`tests/test_metadata.py` drives the participant table end to end. What was
untested is the surface each of the three grains exposes to the rest of the app
— id inference, key extraction, the option/bounds readers the filter widgets are
built from, the payload round-trip that save & restore rides, and `rejoin_*`,
which re-derives a report against a *different* pool.

These matter more than their size suggests: `infer_*_id_column` decides what a
table joins on before the user sees a picker, and `*_options_for` decides which
values a filter can even offer — a wrong answer there produces a filter that can
only empty the pool, with no error anywhere.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import metadata as md


def _combos():
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2"],
            "trial_id": ["t1", "t2", "t1"],
            "text_id": ["x1", "x2", "x1"],
        }
    )


class TestKeyExtraction:
    def test_trial_keys_are_reader_and_trial_pairs(self):
        assert md.trial_keys(_combos()) == {("p1", "t1"), ("p1", "t2"), ("p2", "t1")}

    def test_text_keys_are_distinct_text_ids(self):
        assert md.text_keys(_combos()) == {"x1", "x2"}

    @pytest.mark.parametrize("frame", [None, pd.DataFrame()])
    def test_nothing_in_nothing_out(self, frame):
        assert md.trial_keys(frame) == set()
        assert md.text_keys(frame) == set()

    def test_a_frame_without_the_key_columns_yields_nothing(self):
        """Not an error — a raw frame simply cannot answer yet."""
        assert md.trial_keys(pd.DataFrame({"other": [1]})) == set()
        assert md.text_keys(pd.DataFrame({"other": [1]})) == set()

    def test_participant_ids_are_sorted_strings_across_frames(self):
        a = pd.DataFrame({"participant_id": ["p2", "p1"]})
        b = pd.DataFrame({"participant_id": ["p3", "p1"]})
        assert md.participant_ids(a, b, None, pd.DataFrame()) == ["p1", "p2", "p3"]


class TestIdInference:
    """The first guess the UI shows — and, headlessly, the only guess."""

    @pytest.mark.parametrize(
        "infer, column",
        [
            (md.infer_trial_id_column, "trial_id"),
            (md.infer_text_id_column, "text_id"),
            (md.infer_participant_id_column, "participant_id"),
        ],
    )
    def test_the_canonical_name_is_found(self, infer, column):
        assert infer(pd.DataFrame({column: ["a"], "other": [1]})) == column

    @pytest.mark.parametrize(
        "infer, column",
        [
            (md.infer_trial_id_column, "TRIAL_ID"),
            (md.infer_text_id_column, "Text_ID"),
            (md.infer_participant_id_column, "Participant_ID"),
        ],
    )
    def test_matching_ignores_case(self, infer, column):
        assert infer(pd.DataFrame({column: ["a"]})) == column

    @pytest.mark.parametrize(
        "infer",
        [
            md.infer_trial_id_column,
            md.infer_text_id_column,
            md.infer_participant_id_column,
        ],
    )
    def test_no_plausible_column_is_none_not_a_guess(self, infer):
        assert infer(pd.DataFrame({"height_cm": [1]})) is None
        assert infer(pd.DataFrame()) is None
        assert infer(None) is None


def _participants():
    return md.build_participant_metadata(
        pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "age": [21, 44],
                "cohort": ["A", "B"],
            }
        ),
        "participant_id",
        participants=["p1", "p2"],
    )


class TestTheFilterReaders:
    """What a filter widget is built from. `None` metadata must answer safely —
    the panels render before a table is attached."""

    def test_categorical_options_are_sorted_strings(self):
        assert md.options_for(_participants(), "cohort") == ["A", "B"]

    def test_numeric_bounds_come_back_as_a_pair(self):
        assert md.bounds_for(_participants(), "age") == (21.0, 44.0)

    def test_an_unknown_field_answers_empty(self):
        assert md.options_for(_participants(), "nope") == []
        assert md.bounds_for(_participants(), "nope") is None

    def test_no_table_answers_empty(self):
        assert md.options_for(None, "cohort") == []
        assert md.bounds_for(None, "age") is None

    def test_options_are_dtype_agnostic_the_field_registry_picks_the_widget(self):
        """`options_for` answers for any field; which *control* to build comes
        from `MetadataField.is_numeric`, not from this function refusing."""
        table = _participants()
        assert md.options_for(table, "age") == ["21", "44"]
        assert table.field("age").is_numeric
        assert not table.field("cohort").is_numeric

    def test_a_constant_numeric_field_has_no_bounds(self):
        """min == max is not a range: a slider over it cannot be moved, and the
        filter it builds can only be a no-op or an empty pool."""
        table = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "p2"], "age": [30, 30]}),
            "participant_id",
            participants=["p1", "p2"],
        )
        assert md.bounds_for(table, "age") is None

    def test_options_come_from_the_loaded_readers_only(self):
        """A value belonging to a reader the report just called "not in the
        data" would build a filter that can only empty the pool."""
        table = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "ghost"], "cohort": ["A", "Z"]}),
            "participant_id",
            participants=["p1"],
        )
        assert md.options_for(table, "cohort") == ["A"]
        assert "ghost" in set(table.report.only_in_table)


class TestThePayloadRoundTrip:
    """Save & restore carries the table itself, so the round trip has to be
    lossless — a dropped field is a filter that silently stops working."""

    def test_a_participant_table_survives(self):
        original = _participants()
        restored = md.from_payload(md.to_payload(original))
        assert restored is not None
        assert restored.names == original.names
        assert restored.values_for("p2") == original.values_for("p2")

    def test_a_trial_table_survives(self):
        original = md.build_trial_metadata(
            pd.DataFrame({"trial_id": ["t1", "t2"], "list_position": [1, 2]}),
            "trial_id",
            keys=md.trial_keys(_combos()),
        )
        restored = md.trial_from_payload(md.trial_to_payload(original))
        assert restored is not None
        assert restored.names == original.names
        assert restored.keyed_by_participant == original.keyed_by_participant

    def test_a_text_table_survives(self):
        original = md.build_text_metadata(
            pd.DataFrame({"text_id": ["x1", "x2"], "genre": ["news", "news"]}),
            "text_id",
            keys=md.text_keys(_combos()),
        )
        restored = md.text_from_payload(md.text_to_payload(original))
        assert restored is not None
        assert restored.names == original.names
        assert restored.values_for("x1") == original.values_for("x1")

    @pytest.mark.parametrize(
        "to_payload, from_payload",
        [
            (md.to_payload, md.from_payload),
            (md.trial_to_payload, md.trial_from_payload),
            (md.text_to_payload, md.text_from_payload),
        ],
    )
    def test_no_table_round_trips_as_no_table(self, to_payload, from_payload):
        assert to_payload(None) is None
        assert from_payload(None) is None
        assert from_payload({}) is None


class TestRejoin:
    """Re-deriving the report against a different pool — what happens when the
    trial filters narrow what is loaded after a table was attached."""

    def test_narrowing_the_pool_moves_rows_to_not_in_the_data(self):
        table = md.build_text_metadata(
            pd.DataFrame({"text_id": ["x1", "x2"], "genre": ["news", "opinion"]}),
            "text_id",
            keys={"x1", "x2"},
        )
        assert set(table.report.matched) == {"x1", "x2"}

        narrowed = md.rejoin_texts(table, {"x1"})
        assert set(narrowed.report.matched) == {"x1"}
        assert set(narrowed.report.only_in_table) == {"x2"}
        # The frame itself is untouched — rejoin re-reports, it does not filter.
        assert narrowed.names == table.names

    def test_a_key_with_no_row_is_reported_as_only_in_data(self):
        table = md.build_text_metadata(
            pd.DataFrame({"text_id": ["x1"], "genre": ["news"]}),
            "text_id",
            keys={"x1"},
        )
        widened = md.rejoin_texts(table, {"x1", "x9"})
        assert set(widened.report.only_in_data) == {"x9"}
