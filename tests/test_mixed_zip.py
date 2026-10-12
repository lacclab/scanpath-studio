"""#374 F3: a ZIP holding both EyeLink reports gives each table its own.

The common lab layout is one folder per participant, each with an Interest Area
Report and a Fixation Report. Read whole, the archive concatenated both into
whichever table it was uploaded as — a "fixation" at every word centre. These
tests pin the split: each row reads only its kind, says what it left out, and
the trial-identity warning no longer recommends `source_file` for it.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from scanpath_studio import api
from scanpath_studio.data import (
    diagnose_trial_identity,
    normalize_fixations,
    normalize_words,
    propose_fix_schema,
    propose_word_schema,
    read_table,
    read_table_columns,
    read_tables,
    table_kind_of_columns,
    trial_identity_warning,
    zip_member_split,
)

_IA_HEADER = (
    "RECORDING_SESSION_LABEL\tTRIAL_INDEX\titem\tIA_ID\tIA_LABEL\t"
    "IA_LEFT\tIA_RIGHT\tIA_TOP\tIA_BOTTOM\tIA_DWELL_TIME"
)
_FIX_HEADER = (
    "RECORDING_SESSION_LABEL\tTRIAL_INDEX\titem\tCURRENT_FIX_INDEX\t"
    "CURRENT_FIX_X\tCURRENT_FIX_Y\tCURRENT_FIX_DURATION\tCURRENT_FIX_START\t"
    "CURRENT_FIX_INTEREST_AREA_ID"
)


def _ia_report(pid: str) -> str:
    rows = [
        f"{pid}\t1\tA\t{w}\tw{w}\t{100 * w}\t{100 * w + 100}\t100\t150\t200"
        for w in range(1, 4)
    ]
    return "\n".join([_IA_HEADER, *rows]) + "\n"


def _fix_report(pid: str) -> str:
    rows = [
        f"{pid}\t1\tA\t{i}\t{100 * i + 50}\t125\t200\t{300 * i}\t{i}"
        for i in range(1, 6)
    ]
    return "\n".join([_FIX_HEADER, *rows]) + "\n"


def _mixed_zip(*, with_ia: bool = True) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for pid in ("s01", "s02"):
            if with_ia:
                zf.writestr(f"{pid}/{pid}_IA_report.txt", _ia_report(pid))
            zf.writestr(f"{pid}/{pid}_Fixation_report.txt", _fix_report(pid))
    buf.seek(0)
    buf.name = "per_participant.zip"
    return buf


def test_table_kind_of_eyelink_reports():
    assert table_kind_of_columns(_IA_HEADER.split("\t")) == "words"
    assert table_kind_of_columns(_FIX_HEADER.split("\t")) == "fixations"
    assert table_kind_of_columns(["a", "b"]) is None


def test_each_row_reads_only_its_kind():
    fixations = read_table(_mixed_zip(), kind="fixations")
    words = read_table(_mixed_zip(), kind="words")
    assert len(fixations) == 10 and "IA_LEFT" not in fixations.columns
    assert len(words) == 6 and "CURRENT_FIX_X" not in words.columns
    # Both files of the kind are kept, each tagged with its own source.
    assert fixations["source_file"].nunique() == 2
    # The header pass agrees with the read.
    assert "IA_LEFT" not in read_table_columns(_mixed_zip(), kind="fixations")
    assert len(read_tables([_mixed_zip()], kind="words")) == 6


def test_without_a_kind_the_archive_is_read_whole():
    assert len(read_table(_mixed_zip())) == 16


def test_one_kind_zip_is_untouched():
    split = zip_member_split(_mixed_zip(with_ia=False), "words")
    assert not split.mixed and split.message() == ""
    assert len(read_table(_mixed_zip(with_ia=False), kind="words")) == 10


def test_the_row_says_what_it_left_out():
    message = zip_member_split(_mixed_zip(), "fixations").message()
    assert message == (
        "Using the 2 fixation reports in this ZIP; 2 interest-area reports were "
        "left out — add the ZIP to the Words row too."
    )
    other = zip_member_split(_mixed_zip(), "words").message()
    assert other.startswith("Using the 2 interest-area reports")
    assert other.endswith("add the ZIP to the Fixations row too.")


def test_api_load_splits_the_same_zip(tmp_path):
    path = tmp_path / "per_participant.zip"
    path.write_bytes(_mixed_zip().getvalue())
    words, fixations = api.load_scanpath_data(words=path, fixations=path)
    assert len(fixations) == 10
    assert len(words) == 6


def test_identity_warning_names_mixed_files_not_source_file():
    raw = read_table(_mixed_zip())
    fixations = normalize_fixations(
        raw, propose_fix_schema(raw), keep_columns=list(raw.columns)
    )
    words = normalize_words(
        raw, propose_word_schema(raw), keep_columns=list(raw.columns)
    )
    report = diagnose_trial_identity(words, fixations)
    assert report["mixed_source_shapes"]
    message = trial_identity_warning(report)
    assert "source_file" not in message
    assert "its own row" in message


def test_same_shape_files_keep_the_source_file_advice():
    frame = pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1"] * 4,
            "word_id": [1, 2, 1, 2],
            "source_file": ["a", "a", "b", "b"],
        }
    )
    report = diagnose_trial_identity(frame, pd.DataFrame())
    assert not report["mixed_source_shapes"]
    assert "source_file" in trial_identity_warning(report)


class TestNonTableMembers:
    """A README or notes file shipped beside the data is not a table: it was
    read as one, its first line taken for a header, and the whole upload failed
    with a tokenizing error (2026-10-09)."""

    @staticmethod
    def _zip(members: dict[str, str]) -> io.BytesIO:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            for name, text in members.items():
                archive.writestr(name, text)
        buf.seek(0)
        buf.name = "data.zip"
        return buf

    def test_a_readme_is_skipped(self):
        archive = self._zip(
            {
                "README.md": "# My data\n\nSome notes, with, commas.\n",
                "p1_fix.tsv": _fix_report("p1"),
            }
        )
        frame = read_table(archive, kind="fixations")
        assert len(frame) == 5
        assert "CURRENT_FIX_X" in frame.columns
        archive.seek(0)
        assert "CURRENT_FIX_X" in read_table_columns(archive, kind="fixations")

    def test_a_zip_of_notes_only_holds_no_table(self):
        import pytest

        archive = self._zip({"README.md": "# notes\n", "LICENSE": "MIT\n"})
        with pytest.raises(ValueError, match="holds no table file"):
            read_table(archive, kind="fixations")
