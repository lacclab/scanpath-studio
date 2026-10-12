"""ENG-37: the `render` metadata-attach surface, and the reports it prints.

DATA-20/DATA-29 made the participant, trial and text tables attachable
headlessly, and the *report* is most of why: a mistyped id column or a cohort
file from the wrong study is exactly what you want to hear about before
rendering three hundred figures. That reporting was the largest untested block
in `cli.py` — every branch of it writes to stderr and none of it was exercised,
so a silent regression in "0 matched" would have shipped unnoticed.

Everything here runs against the bundled demo, so no corpus is needed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import cli
from scanpath_studio.api import load_sample_data


@pytest.fixture(scope="module")
def sample():
    words, fixations = load_sample_data(names="canonical")[:2]
    return words, fixations


def _render(tmp_path, *extra):
    """Run a headless render of the bundled demo with `extra` flags."""
    cli.main(["render", "--sample", "-o", str(tmp_path / "out.html"), *extra])


class TestParticipantMetadata:
    def test_a_clean_join_reports_its_fields_and_readers(
        self, tmp_path, sample, capsys
    ):
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame(
            {
                "participant_id": readers,
                "age": [21 + i for i in range(len(readers))],
                "cohort": ["A"] * len(readers),
            }
        ).to_csv(path, index=False)

        _render(tmp_path, "--participant-metadata", str(path))

        err = capsys.readouterr().err
        assert f"for {len(readers)} participants" in err
        assert "2 fields" in err
        assert "age" in err and "cohort" in err

    def test_a_reader_the_table_forgot_is_named(self, tmp_path, sample, capsys):
        """The half that matters: the table is short, not wrong, and the render
        still succeeds — so the only signal is this line."""
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame({"participant_id": readers[:1], "age": [21]}).to_csv(
            path, index=False
        )

        _render(tmp_path, "--participant-metadata", str(path))

        err = capsys.readouterr().err
        assert "in the data, not the table" in err
        assert readers[1] in err

    def test_a_row_for_nobody_loaded_is_named_too(self, tmp_path, sample, capsys):
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame(
            {
                "participant_id": [*readers, "ghost_reader"],
                "age": [21] * (len(readers) + 1),
            }
        ).to_csv(path, index=False)

        _render(tmp_path, "--participant-metadata", str(path))

        err = capsys.readouterr().err
        assert "in the table, not the data" in err
        assert "ghost_reader" in err

    def test_duplicate_rows_that_disagree_are_dropped_and_named(
        self, tmp_path, sample, capsys
    ):
        """`metadata` never resolves a disagreement by taking the first row."""
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame(
            {
                "participant_id": [readers[0], readers[0], readers[1]],
                "age": [21, 44, 30],
            }
        ).to_csv(path, index=False)

        _render(tmp_path, "--participant-metadata", str(path))

        err = capsys.readouterr().err
        assert "rows that disagree" in err
        assert readers[0] in err

    def test_duplicate_rows_that_agree_are_combined_and_counted(
        self, tmp_path, sample, capsys
    ):
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        path = tmp_path / "readers.csv"
        pd.DataFrame(
            {
                "participant_id": [readers[0], readers[0]],
                "age": [21, None],
                "language": [None, "English"],
            }
        ).to_csv(path, index=False)

        _render(tmp_path, "--participant-metadata", str(path))

        err = capsys.readouterr().err
        assert "combined 2 compatible duplicate rows" in err
        assert "rows that disagree" not in err

    def test_a_missing_file_exits_rather_than_rendering(self, tmp_path):
        with pytest.raises(SystemExit):
            _render(tmp_path, "--participant-metadata", str(tmp_path / "nope.csv"))


class TestTrialMetadata:
    def test_keyed_by_trial_id_alone(self, tmp_path, sample, capsys):
        _words, fixations = sample
        trials = sorted(fixations["trial_id"].astype(str).unique())
        path = tmp_path / "trials.csv"
        pd.DataFrame({"trial_id": trials, "list_position": range(len(trials))}).to_csv(
            path, index=False
        )

        _render(tmp_path, "--trial-metadata", str(path))

        err = capsys.readouterr().err
        assert "keyed by trial id" in err
        assert f"for {len(trials)} trials" in err

    def test_keyed_by_reader_and_trial(self, tmp_path, sample, capsys):
        """A row describes one *reading* rather than a text — never inferred,
        because getting it wrong is silent: the table still joins."""
        _words, fixations = sample
        pairs = (
            fixations[["participant_id", "trial_id"]]
            .astype(str)
            .drop_duplicates()
            .reset_index(drop=True)
        )
        path = tmp_path / "readings.csv"
        pairs.assign(accuracy=1.0).to_csv(path, index=False)

        _render(
            tmp_path,
            "--trial-metadata",
            str(path),
            "--trial-metadata-reader-column",
            "participant_id",
        )

        err = capsys.readouterr().err
        assert "keyed by participant + trial" in err

    def test_the_reader_column_alone_is_refused(self, tmp_path):
        """It only means something with a table to key."""
        with pytest.raises(SystemExit):
            _render(tmp_path, "--trial-metadata-reader-column", "participant_id")

    def test_a_trial_with_no_row_is_named(self, tmp_path, sample, capsys):
        _words, fixations = sample
        trials = sorted(fixations["trial_id"].astype(str).unique())
        path = tmp_path / "trials.csv"
        pd.DataFrame({"trial_id": trials[:2], "list_position": [0, 1]}).to_csv(
            path, index=False
        )

        _render(tmp_path, "--trial-metadata", str(path))

        err = capsys.readouterr().err
        assert "in the data, not the table" in err

    def test_a_long_key_list_is_truncated_with_a_plain_ellipsis(
        self, tmp_path, sample, capsys
    ):
        """Windows consoles print a single-glyph ellipsis as a replacement mark,
        so the truncation marker is three dots."""
        _words, _fixations = sample
        path = tmp_path / "trials.csv"
        pd.DataFrame(
            {"trial_id": [f"ghost_{i}" for i in range(30)], "x": range(30)}
        ).to_csv(path, index=False)

        _render(tmp_path, "--trial-metadata", str(path))

        err = capsys.readouterr().err
        assert "in the table, not the data" in err
        assert ", ... (+10)" in err
        assert "…" not in err


class TestTextMetadata:
    def test_a_clean_join_reports_its_texts(self, tmp_path, sample, capsys):
        words, _fixations = sample
        texts = sorted(words["text_id"].astype(str).unique())
        path = tmp_path / "texts.csv"
        pd.DataFrame({"text_id": texts, "genre": ["news"] * len(texts)}).to_csv(
            path, index=False
        )

        _render(tmp_path, "--text-metadata", str(path))

        err = capsys.readouterr().err
        assert "Text metadata" in err
        assert "genre" in err

    def test_a_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            _render(tmp_path, "--text-metadata", str(tmp_path / "nope.csv"))


class TestSeveralFiles:
    """A metadata table split across files (one per session or per lab) is
    stacked into one, on the CLI as in the app's uploaders."""

    def test_two_participant_files_read_as_one_table(self, tmp_path, sample, capsys):
        _words, fixations = sample
        readers = sorted(fixations["participant_id"].astype(str).unique())
        half = len(readers) // 2 or 1
        paths = []
        for name, chunk in (("a.csv", readers[:half]), ("b.csv", readers[half:])):
            path = tmp_path / name
            pd.DataFrame({"participant_id": chunk, "age": 30}).to_csv(path, index=False)
            paths.append(str(path))

        _render(tmp_path, "--participant-metadata", *paths)

        assert f"for {len(readers)} participants" in capsys.readouterr().err


class TestTheAppReadsSeveralUploads:
    """`tabs._read_metadata_uploads`: what the three metadata uploaders read."""

    @staticmethod
    def _upload(name: str, text: str):
        import io

        upload = io.BytesIO(text.encode("utf-8"))
        upload.name = name
        upload.file_id = name
        return upload

    def test_files_are_stacked_with_their_columns_aligned(self):
        from scanpath_studio.tabs import _metadata_upload_name, _read_metadata_uploads

        uploads = [
            self._upload("a.csv", "participant_id,age\np1,30\n"),
            self._upload("b.csv", "participant_id,group\np2,B\n"),
        ]
        frame = _read_metadata_uploads(uploads)
        assert frame["participant_id"].astype(str).tolist() == ["p1", "p2"]
        assert set(frame.columns) == {"participant_id", "age", "group"}
        assert _metadata_upload_name(uploads) == "a.csv + 1 more file"

    def test_an_unreadable_file_is_named(self):
        from scanpath_studio.tabs import _MetadataReadError, _read_metadata_uploads

        uploads = [
            self._upload("a.csv", "participant_id,age\np1,30\n"),
            self._upload("broken.parquet", "not parquet"),
        ]
        with pytest.raises(_MetadataReadError, match="broken.parquet"):
            _read_metadata_uploads(uploads)
