"""Reading only the columns normalization keeps (PERF-6).

An EyeLink IA report ships 174 columns and a fixation report 300; the mapping
plus the optional-field registry claim 27 and 17 of them, and ``normalize_*``
drops the rest on the next line. Parsing them anyway is the single largest cost
on the load path — so the read is planned from the header instead.

The contract these tests pin is *equality*: a planned read must normalize to
exactly the frame a full read normalizes to. Everything else here guards the two
ways that can quietly stop being true — a column the plan forgot, and EyeLink's
``.`` missing marker being declared missing somewhere it is real data.
"""

from __future__ import annotations

import zipfile
from unittest.mock import patch

import pandas as pd
import pytest

from scanpath_studio import data as data_module

from scanpath_studio.data import (
    WORD_OPTIONAL_FIELDS,
    normalize_words,
    plan_table_read,
    propose_word_schema,
    read_mapped_table,
    read_table,
    read_table_columns,
)

# One row per word of a two-word trial, in the shape of a lacclab IA export:
# the eight mapped columns, four the registry claims, and three it does not.
# `IA_DWELL_TIME` carries EyeLink's "." for a word that was never fixated, and
# the second word's text *is* a period — the case that makes a blanket
# `na_values="."` wrong.
MAPPED = {
    "RECORDING_SESSION_LABEL": ["l1_001", "l1_001"],
    "paragraph_id": ["p1", "p1"],
    "IA_ID": [1, 2],
    "IA_LABEL": ["Hello", "."],
    "IA_LEFT": [10, 60],
    "IA_RIGHT": [50, 70],
    "IA_TOP": [100, 100],
    "IA_BOTTOM": [130, 130],
}
CLAIMED = {
    "IA_DWELL_TIME": ["220", "."],
    "IA_FIXATION_COUNT": ["2", "0"],
    "IA_SKIP": ["0", "1"],
    "article_id": ["a1", "a1"],
}
UNCLAIMED = {
    "IA_AREA": [1200, 300],
    "NEXT_SAC_ANGLE": [12.5, -3.0],
    "DUMMY": [".", "."],
}


@pytest.fixture
def report(tmp_path):
    """A miniature IA report on disk, mapped + claimed + unclaimed columns."""
    path = tmp_path / "ia_mini.tsv"
    pd.DataFrame({**MAPPED, **CLAIMED, **UNCLAIMED}).to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def schema(report):
    """The auto-detected mapping, proposed from the header alone."""
    header = read_table_columns(report)
    return propose_word_schema(pd.DataFrame(columns=header))


class TestReadTableColumns:
    """The header pass — column names without parsing any rows."""

    def test_matches_a_full_read(self, report):
        assert read_table_columns(report) == list(read_table(report).columns)

    def test_matches_a_full_read_for_parquet(self, tmp_path):
        path = tmp_path / "ia_mini.parquet"
        pd.DataFrame({**MAPPED, **CLAIMED}).to_parquet(path)
        assert read_table_columns(path) == list(read_table(path).columns)

    def test_reads_a_zipped_report_header_without_unpacking_it(self, tmp_path):
        """OneStop ships `.csv.zip`; falling back to a full read here would
        unpack the whole 4 GB archive just to learn its column names."""
        path = tmp_path / "ia_mini.csv.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(
                "ia_mini.csv",
                pd.DataFrame({**MAPPED, **CLAIMED}).to_csv(index=False),
            )
        with patch.object(
            data_module, "_read_by_extension", side_effect=AssertionError("full read")
        ):
            assert read_table_columns(path) == list(MAPPED) + list(CLAIMED)


class TestPlanTableRead:
    """What the plan decides to parse, and what it declares missing."""

    def test_keeps_mapped_and_registry_columns(self, report, schema):
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        assert set(MAPPED) <= set(plan.columns)
        assert set(CLAIMED) <= set(plan.columns)

    def test_drops_columns_nothing_claims(self, report, schema):
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        assert set(plan.columns).isdisjoint(UNCLAIMED)

    def test_keeps_user_chosen_filter_fields(self, report, schema):
        plan = plan_table_read(
            read_table_columns(report),
            schema,
            WORD_OPTIONAL_FIELDS,
            filter_fields=["NEXT_SAC_ANGLE"],
        )
        assert "NEXT_SAC_ANGLE" in plan.columns
        assert "IA_AREA" not in plan.columns

    def test_declares_the_eyelink_dot_missing_for_numeric_columns(self, report, schema):
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        assert plan.na_values["IA_DWELL_TIME"] == ["."]

    def test_leaves_text_columns_alone(self, report, schema):
        """A word whose text is "." is data, not a missing marker."""
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        assert "IA_LABEL" not in plan.na_values
        assert "article_id" not in plan.na_values

    def test_reads_everything_when_no_column_is_claimed(self, report):
        """An unmapped table has no plan to make — parse it whole."""
        plan = plan_table_read(read_table_columns(report), {}, ())
        assert plan.columns is None


class TestPlannedReadEquivalence:
    """The contract: planning the read must not change the normalized frame."""

    def test_normalizes_identically_to_a_full_read(self, report, schema):
        full = normalize_words(read_table(report), schema, keep_columns=None)
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        planned = normalize_words(
            read_table(report, plan=plan), schema, keep_columns=None
        )
        pd.testing.assert_frame_equal(full, planned, check_dtype=True)

    def test_a_period_stays_a_word(self, report, schema):
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        words = normalize_words(
            read_table(report, plan=plan), schema, keep_columns=None
        )
        assert list(words["text"]) == ["Hello", "."]

    def test_an_unfixated_word_reads_as_missing_not_as_a_string(self, report, schema):
        plan = plan_table_read(read_table_columns(report), schema, WORD_OPTIONAL_FIELDS)
        words = normalize_words(
            read_table(report, plan=plan), schema, keep_columns=None
        )
        assert words["total_fixation_duration_ms"].dtype.kind == "f"
        assert words["total_fixation_duration_ms"].isna().tolist() == [False, True]


class TestReadMappedTable:
    """The one call a loader makes: plan the read and do it, in one step."""

    def test_normalizes_identically_to_a_full_read(self, report, schema):
        full = normalize_words(read_table(report), schema, keep_columns=None)
        mapped = read_mapped_table(report, kind="words")
        pd.testing.assert_frame_equal(
            full, normalize_words(mapped, schema, keep_columns=None), check_dtype=True
        )

    def test_parses_only_the_claimed_columns(self, report):
        assert set(read_mapped_table(report, kind="words").columns).isdisjoint(
            UNCLAIMED
        )

    def test_keeps_columns_the_caller_asks_to_filter_on(self, report):
        frame = read_mapped_table(report, kind="words", filter_fields=["IA_AREA"])
        assert "IA_AREA" in frame.columns

    def test_a_fixation_table_uses_the_fixation_registry(self, tmp_path):
        """The `kind` picks both the proposal and the registry, not just one."""
        path = tmp_path / "fix_mini.tsv"
        pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["l1_001"],
                "paragraph_id": ["p1"],
                "CURRENT_FIX_INDEX": [1],
                "CURRENT_FIX_START": [100],
                "CURRENT_FIX_DURATION": [220],
                "CURRENT_FIX_X": [30.0],
                "CURRENT_FIX_Y": [115.0],
                "CURRENT_FIX_INTEREST_AREA_ID": [1],
                "NEXT_SAC_DIRECTION": ["RIGHT"],
                "NEXT_FIX_PUPIL": [900],
            }
        ).to_csv(path, sep="\t", index=False)
        frame = read_mapped_table(path, kind="fixations")
        assert "NEXT_SAC_DIRECTION" in frame.columns  # the registry claims it
        assert "NEXT_FIX_PUPIL" not in frame.columns  # nothing does

    def test_rejects_a_kind_it_has_no_registry_for(self, report):
        with pytest.raises(ValueError, match="kind"):
            read_mapped_table(report, kind="raw_gaze")
