"""DATA-66 phase 1: the dataset's own column names, behind the canonical ones."""

from __future__ import annotations

from scanpath_studio import column_names as cn
from scanpath_studio.column_names import ColumnNames, SourceName


class TestColumnNames:
    def test_display_is_the_source_or_the_column_itself(self):
        names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
        assert names.display("duration_ms") == "CURRENT_FIX_DURATION"
        assert names.display("my_extra") == "my_extra"

    def test_a_composite_displays_its_parts(self):
        names = ColumnNames(
            {"trial_id": SourceName(("reader_id", "text_id"), cn.COMPOSITE)}
        )
        assert names.display("trial_id") == "reader_id + text_id"

    def test_kind_falls_back_to_computed_then_yours(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",))})
        assert names.kind_of("duration_ms") == cn.MAPPED
        assert names.kind_of("is_regression") == cn.COMPUTED
        assert names.kind_of("my_extra") == cn.YOURS

    def test_an_imported_measure_is_the_users_not_computed(self):
        names = ColumnNames(
            {"total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",))}
        )
        assert names.kind_of("total_fixation_duration_ms") == cn.MAPPED

    def test_to_canonical_reads_the_map_backwards(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",), cn.CONVERTED)})
        assert names.to_canonical("dur") == "duration_ms"
        assert names.to_canonical("duration_ms") == "duration_ms"
        assert names.to_canonical("unknown") == "unknown"

    def test_payload_round_trips(self):
        names = ColumnNames(
            {
                "trial_id": SourceName(("a", "b"), cn.COMPOSITE),
                "fixation_id": SourceName((), cn.GENERATED, "1, 2, … per trial"),
            }
        )
        assert ColumnNames.from_payload(names.to_payload()) == names
        assert ColumnNames.from_payload(None) == cn.EMPTY
        assert ColumnNames.from_payload({"x": "not a dict"}) == cn.EMPTY

    def test_through_renames_sources_by_an_earlier_map(self):
        """An Edit-dataset save maps fields onto the stored *canonical* columns;
        read through the dataset's earlier map, they are the user's names again."""
        earlier = ColumnNames(
            {
                "trial_id": SourceName(("TRIAL",)),
                "text_id": SourceName(("PARAGRAPH",)),
                "timestamp_ms": SourceName((), cn.GENERATED, "order"),
                "total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",)),
            }
        )
        edit = ColumnNames(
            {
                "trial_id": SourceName(("text_id",)),
                "timestamp_ms": SourceName(("timestamp_ms",)),
            }
        )
        merged = edit.through(earlier)
        assert merged.display("trial_id") == "PARAGRAPH"
        assert merged.kind_of("timestamp_ms") == cn.GENERATED
        # What the edit did not touch keeps the earlier record.
        assert merged.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
