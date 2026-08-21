"""Edge cases in the planned read (PERF-6 review follow-ups).

Planning the read is an *optimization*, so every one of these is the same rule
stated three ways: it must never change what comes back, never fail on input the
whole-file read handled, and never weaken a guard the whole-file read enforced.
"""

from __future__ import annotations

import zipfile

import pandas as pd
import pytest

from scanpath_studio import data as data_module
from scanpath_studio.data import (
    WORD_OPTIONAL_FIELDS,
    ReadPlan,
    plan_table_read,
    propose_word_schema,
    read_table,
    read_table_columns,
)

CORE = {
    "RECORDING_SESSION_LABEL": ["p1"],
    "paragraph_id": ["t1"],
    "IA_ID": [1],
    "IA_LABEL": ["Hello"],
    "IA_LEFT": [10],
    "IA_RIGHT": [50],
    "IA_TOP": [100],
    "IA_BOTTOM": [130],
}


def _plan(header):
    return plan_table_read(
        header, propose_word_schema(pd.DataFrame(columns=header)), WORD_OPTIONAL_FIELDS
    )


class TestZipDecompressionLimits:
    """DATA-16/S6: the header read must not be a way around the size guard."""

    def test_an_oversized_archive_is_refused(self, tmp_path, monkeypatch):
        path = tmp_path / "big.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.csv", pd.DataFrame(CORE).to_csv(index=False))
        monkeypatch.setattr(data_module, "ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES", 4)
        monkeypatch.setattr(data_module, "ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", 4)
        with pytest.raises(ValueError, match="limit"):
            read_table_columns(path)

    def test_the_same_archive_is_refused_by_the_full_read(self, tmp_path, monkeypatch):
        """The guard the header read has to match."""
        path = tmp_path / "big.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.csv", pd.DataFrame(CORE).to_csv(index=False))
        monkeypatch.setattr(data_module, "ZIP_MAX_MEMBER_UNCOMPRESSED_BYTES", 4)
        monkeypatch.setattr(data_module, "ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES", 4)
        with pytest.raises(ValueError, match="limit"):
            read_table(path)


class TestHeterogeneousZipMembers:
    """A zip may hold several tables whose columns differ."""

    def test_a_member_missing_a_planned_column_still_reads(self, tmp_path):
        path = tmp_path / "pair.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(
                "a.csv",
                pd.DataFrame({**CORE, "IA_DWELL_TIME": [220]}).to_csv(index=False),
            )
            zf.writestr("b.csv", pd.DataFrame(CORE).to_csv(index=False))
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert len(frame) == 2
        assert "IA_DWELL_TIME" in frame.columns
        assert frame["IA_DWELL_TIME"].isna().tolist() == [False, True]

    def test_it_matches_what_an_unplanned_read_returns(self, tmp_path):
        path = tmp_path / "pair.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(
                "a.csv",
                pd.DataFrame({**CORE, "IA_DWELL_TIME": [220]}).to_csv(index=False),
            )
            zf.writestr("b.csv", pd.DataFrame(CORE).to_csv(index=False))
        planned = read_table(path, plan=_plan(read_table_columns(path)))
        full = read_table(path)
        assert len(planned) == len(full)
        # `assert_series_equal`, not `==`: the whole point of this fixture is a
        # column one member lacks, and NaN never equals NaN.
        for column in planned.columns:
            pd.testing.assert_series_equal(planned[column], full[column])


class TestEmptyPlan:
    """An empty column tuple has to mean the same thing on every reader."""

    def test_csv_reads_everything(self, tmp_path):
        path = tmp_path / "a.csv"
        pd.DataFrame(CORE).to_csv(path, index=False)
        assert list(read_table(path, plan=ReadPlan(columns=())).columns) == list(CORE)

    def test_parquet_reads_everything(self, tmp_path):
        path = tmp_path / "a.parquet"
        pd.DataFrame(CORE).to_parquet(path)
        assert list(read_table(path, plan=ReadPlan(columns=())).columns) == list(CORE)
