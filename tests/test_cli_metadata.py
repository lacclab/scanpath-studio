"""The `render` metadata-attach surface, and the reports it prints.

The participant, trial and text tables can be attached headlessly, and the
*report* matters most: a mistyped id column or a cohort file from the wrong
study is exactly what you want to hear about before rendering three hundred
figures. Every branch of that report writes to stderr, so a regression in
"0 matched" would otherwise go unnoticed.

Tests use the bundled demo and small local tables.
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


def test_metadata_reports_and_trial_listing_use_all_recording_tables(tmp_path, capsys):
    tables = {
        "words": "participant_id,trial_id,text_id,word_id,word,x,y,width,height\np1,t1,a,1,One,10,10,20,10\n",
        "fixations": "participant_id,trial_id,text_id,x,y,duration_ms\np2,t2,b,10,20,200\n",
        "raw-gaze": "participant_id,trial_id,text_id,x,y,timestamp_ms\np3,t3,c,10,20,0\n",
        "participant-metadata": "participant_id,cohort\np1,A\np2,B\np3,C\n",
        "trial-metadata": "trial_id,session\nt1,s1\nt2,s2\nt3,s3\n",
        "text-metadata": "text_id,genre\na,poem\nb,story\nc,essay\n",
    }
    args = ["render", "--list-trials"]
    for flag, csv in tables.items():
        path = tmp_path / f"{flag}.csv"
        path.write_text(csv, encoding="utf-8")
        args.extend([f"--{flag}", str(path)])

    cli.main(args)
    out, err = capsys.readouterr()
    assert "for 3 participants" in err
    assert "for 3 trials" in err
    assert "for 3 texts" in err
    assert [line.split() for line in out.splitlines()] == [
        ["participant_id", "trial_id", "cohort", "session", "text_id", "genre"],
        ["p1", "t1", "A", "s1", "a", "poem"],
        ["p2", "t2", "B", "s2", "b", "story"],
        ["p3", "t3", "C", "s3", "c", "essay"],
    ]


def test_mapped_text_owns_the_join_even_if_other_tables_supply_text_ids(
    tmp_path, capsys
):
    tables = {
        "words": "participant_id,trial_id,text_id,word_id,word,x,y,width,height\np1,t1,recorded,1,One,10,10,20,10\n",
        "fixations": "participant_id,trial_id,x,y,duration_ms\np1,t1,10,20,200\n",
        "raw-gaze": "participant_id,trial_id,x,y,timestamp_ms\np1,t1,10,20,0\n",
        "participant-metadata": "participant_id,text_id\np1,survey\n",
        "text-metadata": "text_id,genre\nrecorded,poem\n",
    }
    args = ["render", "--list-trials"]
    for flag, csv in tables.items():
        path = tmp_path / f"{flag}.csv"
        path.write_text(csv, encoding="utf-8")
        args.extend([f"--{flag}", str(path)])
    cli.main(args)
    out, err = capsys.readouterr()
    assert "in the data, not the table" not in err
    assert [line.split() for line in out.splitlines()] == [
        ["participant_id", "trial_id", "text_id", "genre"],
        ["p1", "t1", "recorded", "poem"],
    ]


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
    """`metadata_editor._read_metadata_uploads`: what the three metadata uploaders read."""

    @staticmethod
    def _upload(name: str, text: str):
        import io

        upload = io.BytesIO(text.encode("utf-8"))
        upload.name = name
        upload.file_id = name
        return upload

    def test_files_are_stacked_with_their_columns_aligned(self):
        from scanpath_studio.metadata_editor import (
            _metadata_upload_name,
            _read_metadata_uploads,
        )

        uploads = [
            self._upload("a.csv", "participant_id,age\np1,30\n"),
            self._upload("b.csv", "participant_id,group\np2,B\n"),
        ]
        frame = _read_metadata_uploads(uploads)
        assert frame["participant_id"].astype(str).tolist() == ["p1", "p2"]
        assert set(frame.columns) == {"participant_id", "age", "group"}
        assert _metadata_upload_name(uploads) == "a.csv + 1 more file"

    @pytest.mark.parametrize(
        ("grain", "mapping"),
        [
            ("participant", ("subject_code",)),
            ("trial", ("subject_code", "item")),
            ("text", ("subject_code", "item")),
        ],
    )
    def test_mapped_columns_keep_their_original_identity(self, grain, mapping):
        from scanpath_studio.metadata_editor import _read_metadata_uploads

        upload = self._upload(
            "codes.csv", "subject_code,item,age\n1,02,19\n01,2,30\nNA,02,31\n"
        )
        frame = _read_metadata_uploads([upload], grain, mapping)
        assert frame["subject_code"].tolist() == ["1", "01", "NA"]
        assert frame["age"].tolist() == [19, 30, 31]
        if "item" in mapping:
            assert frame["item"].tolist() == ["02", "2", "02"]

    def test_an_unreadable_file_is_named(self):
        from scanpath_studio.metadata_editor import (
            _MetadataReadError,
            _read_metadata_uploads,
        )

        uploads = [
            self._upload("a.csv", "participant_id,age\np1,30\n"),
            self._upload("broken.parquet", "not parquet"),
        ]
        with pytest.raises(_MetadataReadError, match="broken.parquet"):
            _read_metadata_uploads(uploads)
