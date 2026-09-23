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


class TestWordTextIsReadVerbatim:
    """BUG-53: "None", "NA", "null" and a blank cell are words, not missing.

    pandas' default NA spellings turned each into NaN at read time, pandas 3's
    `astype(str)` kept the NaN, and the load then died in a `" ".join` over the
    trial's text — reported by the wizard as "this column mapping doesn't work".
    """

    WORDS = ["None", "NA", "null", "", "fox"]

    def _table(self):
        n = len(self.WORDS)
        return pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["p1"] * n,
                "paragraph_id": ["t1"] * n,
                "IA_ID": list(range(1, n + 1)),
                "IA_LABEL": self.WORDS,
                "IA_LEFT": [10 * i for i in range(n)],
                "IA_RIGHT": [10 * i + 9 for i in range(n)],
                "IA_TOP": [100] * n,
                "IA_BOTTOM": [".", 130, 130, 130, 130],
            }
        )

    def test_a_planned_csv_read_keeps_the_words(self, tmp_path):
        path = tmp_path / "ia.tsv"
        self._table().to_csv(path, sep="\t", index=False)
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == self.WORDS
        # The numeric columns still read EyeLink's "." as missing.
        assert frame["IA_BOTTOM"].isna().tolist() == [True] + [False] * 4

    def test_an_excel_read_keeps_the_words(self, tmp_path):
        path = tmp_path / "ia.xlsx"
        self._table().to_excel(path, index=False)
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == self.WORDS

    def test_the_headless_api_loads_them(self, tmp_path):
        from scanpath_studio import api

        path = tmp_path / "ia.tsv"
        self._table().to_csv(path, sep="\t", index=False)
        words, _ = api.load_scanpath_data(words=str(path))
        assert words["text"].tolist() == self.WORDS

    def test_a_hand_mapped_text_column_is_the_one_kept(self):
        from scanpath_studio.app import upload_read_plan

        header = [*self._table().columns, "word_form"]
        plan = upload_read_plan(header, "words", text_column="word_form")
        assert plan.verbatim == ("word_form",)
        assert "word_form" in plan.columns

    def test_a_missing_word_normalizes_to_an_empty_string(self):
        """A frame read without a plan (a parquet null, a DataFrame passed in)
        still normalizes and harmonizes instead of raising."""
        table = self._table()
        table.loc[0, "IA_LABEL"] = None
        schema = propose_word_schema(table)
        words = data_module.normalize_words(table, schema)
        assert words["text"].tolist()[0] == ""
        data_module.harmonize_frames(words, data_module.empty_fixations_frame())


class TestFilesTheReadersUsedToRefuse:
    """BUG-55: an Excel-named text export, a non-UTF-8 CSV and an empty file.

    Each used to escape the wizard as a raw traceback over the whole page.
    """

    def _tsv(self, **extra) -> bytes:
        return pd.DataFrame({**CORE, **extra}).to_csv(sep="\t", index=False).encode()

    def test_a_tab_separated_export_named_xls_reads_as_text(self, tmp_path):
        """EyeLink Data Viewer's "Excel" export is tab-separated text."""
        path = tmp_path / "fix_report.xls"
        path.write_bytes(self._tsv())
        assert read_table_columns(path) == list(CORE)
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == ["Hello"]

    def test_a_legacy_workbook_is_refused_with_the_fix(self, tmp_path):
        path = tmp_path / "old.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 512)
        with pytest.raises(ValueError, match=r"save it as \.xlsx or \.csv"):
            read_table(path)

    def test_a_windows_encoded_csv_reads(self, tmp_path):
        path = tmp_path / "fix_latin1.csv"
        path.write_bytes(
            pd.DataFrame({**CORE, "IA_LABEL": ["Straße"]})
            .to_csv(index=False)
            .encode("cp1252")
        )
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == ["Straße"]

    def test_a_windows_encoded_csv_inside_a_zip_reads(self, tmp_path):
        """A zip member cannot be rewound, so it is retried from memory."""
        path = tmp_path / "words.zip"
        body = pd.DataFrame({**CORE, "IA_LABEL": ["Straße"]}).to_csv(index=False)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("words.csv", body.encode("cp1252"))
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == ["Straße"]

    def test_an_empty_file_says_it_is_empty(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_bytes(b"")
        with pytest.raises(ValueError, match="'empty.csv' is empty"):
            read_table_columns(path)
        with pytest.raises(ValueError, match="'empty.csv' is empty"):
            read_table(path)

    def test_the_upload_box_reports_it_instead_of_crashing(self):
        from streamlit.testing.v1 import AppTest

        def script():
            import io

            import streamlit as st

            from scanpath_studio import app

            class Upload(io.BytesIO):
                name, size, file_id = "empty.csv", 0, "empty"

            class Host:
                def file_uploader(self, *args, **kwargs):
                    return Upload(b"")

                def error(self, body):
                    st.error(body)

            frame = app._read_uploaded_frame(
                uploader_label="Fixations",
                upload_help="",
                state_prefix="col_map_fix",
                multi=False,
                container=Host(),
                kind="fixations",
            )
            st.write(f"rows={len(frame)}")

        at = AppTest.from_function(script).run(timeout=60)
        assert not at.exception
        assert any("Couldn't read **empty.csv**" in e.value for e in at.error)


class TestTheDelimiterIsReadOffTheHeader:
    """DATA-41: a `;`-separated CSV and a tab-separated `.txt` both loaded as
    one column holding the whole line."""

    def test_a_semicolon_csv_with_decimal_commas(self, tmp_path):
        path = tmp_path / "words_euro.csv"
        pd.DataFrame({**CORE, "IA_LEFT": [10.5]}).to_csv(
            path, sep=";", decimal=",", index=False
        )
        assert read_table_columns(path) == list(CORE)
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        words = data_module.normalize_words(frame, propose_word_schema(frame))
        assert words["x"].tolist() == [10.5]

    def test_a_tab_separated_txt(self, tmp_path):
        path = tmp_path / "ia_report.txt"
        path.write_text(pd.DataFrame(CORE).to_csv(sep="\t", index=False))
        assert read_table_columns(path) == list(CORE)
        assert read_table(path)["IA_LABEL"].tolist() == ["Hello"]

    def test_a_semicolon_csv_inside_a_zip(self, tmp_path):
        path = tmp_path / "words.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("words.csv", pd.DataFrame(CORE).to_csv(sep=";", index=False))
        assert read_table_columns(path) == list(CORE)
        frame = read_table(path, plan=_plan(read_table_columns(path)))
        assert frame["IA_LABEL"].tolist() == ["Hello"]

    def test_a_delimiter_inside_a_quoted_name_does_not_count(self, tmp_path):
        path = tmp_path / "a.csv"
        path.write_text('"a;b;c",d\n1,2\n')
        assert read_table_columns(path) == ["a;b;c", "d"]

    def test_a_one_column_csv_keeps_the_comma(self, tmp_path):
        path = tmp_path / "ids.csv"
        path.write_text("participant_id\np1\np2\n")
        assert read_table(path)["participant_id"].tolist() == ["p1", "p2"]
