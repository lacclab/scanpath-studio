"""Headless file imports keep zero-padded ids distinct.

Two readers named ``1`` and ``01``, both reading trial ``01``: read as numbers,
a CSV makes them one reader of trial ``1``. Loading the files must give the
same readings as loading the equivalent string-typed DataFrames. A test with
only one padded id cannot catch the merge — both have to coexist.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api, cli

READERS = [("1", 100), ("01", 700)]


def _words() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "participant_id": pid,
                "trial_id": "01",
                "text_id": "01",
                "word_id": 1,
                "text": "test",
                "x": 100,
                "y": 100,
                "width": 50,
                "height": 20,
            }
            for pid, _ in READERS
        ]
    )


def _fixations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "participant_id": pid,
                "trial_id": "01",
                "text_id": "01",
                "word_id": 1,
                "x": 110,
                "y": 110,
                "duration_ms": duration,
                "timestamp_ms": 0,
            }
            for pid, duration in READERS
        ]
    )


def _readings(frame: pd.DataFrame) -> list[tuple[str, str]]:
    pairs = frame[["participant_id", "trial_id"]].drop_duplicates()
    return sorted(map(tuple, pairs.astype(str).to_numpy().tolist()))


@pytest.fixture
def files(tmp_path):
    words_path, fix_path = tmp_path / "words.csv", tmp_path / "fixations.csv"
    _words().to_csv(words_path, index=False)
    _fixations().to_csv(fix_path, index=False)
    return words_path, fix_path


EXPECTED = [("01", "01"), ("1", "01")]


def test_files_and_frames_give_the_same_readings(files):
    from_files = api.load_scanpath_data(*files)
    from_frames = api.load_scanpath_data(_words(), _fixations())
    for loaded, frame in zip(from_files, from_frames, strict=True):
        assert _readings(loaded) == _readings(frame) == EXPECTED
    durations = from_files[1].groupby("participant_id")["duration_ms"].sum()
    assert durations.to_dict() == {"1": 100, "01": 700}


def test_an_explicit_schema_keeps_them_too(files):
    words, fixations = api.load_scanpath_data(
        *files,
        word_schema=api.propose_schema(_words(), "words"),
        fix_schema=api.propose_schema(_fixations(), "fixations"),
    )
    assert _readings(words) == _readings(fixations) == EXPECTED


def test_a_composite_trial_id_keeps_its_parts(tmp_path):
    words = _words().rename(columns={"trial_id": "block"}).assign(item="02")
    fixations = _fixations().rename(columns={"trial_id": "block"}).assign(item="02")
    words.to_csv(tmp_path / "w.csv", index=False)
    fixations.to_csv(tmp_path / "f.csv", index=False)
    word_schema = api.propose_schema(words, "words") | {"trial": ["block", "item"]}
    fix_schema = api.propose_schema(fixations, "fixations") | {
        "trial": ["block", "item"]
    }
    from_files = api.load_scanpath_data(
        tmp_path / "w.csv",
        tmp_path / "f.csv",
        word_schema=word_schema,
        fix_schema=fix_schema,
    )
    from_frames = api.load_scanpath_data(
        words, fixations, word_schema=word_schema, fix_schema=fix_schema
    )
    for loaded, frame in zip(from_files, from_frames, strict=True):
        assert _readings(loaded) == _readings(frame)
        assert sorted(loaded["participant_id"].unique()) == ["01", "1"]


def test_raw_gaze_keeps_them(tmp_path):
    gaze = pd.DataFrame(
        {
            "participant_id": ["1", "01"],
            "trial_id": ["01", "01"],
            "x": [1.0, 2.0],
            "y": [1.0, 2.0],
            "timestamp_ms": [0, 0],
        }
    )
    gaze.to_csv(tmp_path / "gaze.csv", index=False)
    loaded = api.load_raw_gaze(tmp_path / "gaze.csv")
    assert _readings(loaded) == EXPECTED


def test_participant_metadata_keeps_them(tmp_path):
    table = pd.DataFrame({"participant_id": ["1", "01"], "age": [20, 30]})
    table.to_csv(tmp_path / "readers.csv", index=False)
    meta = api.load_participant_metadata(
        tmp_path / "readers.csv", participants=["1", "01"]
    )
    assert meta.values_for("1") == {"age": 20}
    assert meta.values_for("01") == {"age": 30}


def test_the_cli_reads_its_own_files_through_the_fix(files, tmp_path, monkeypatch):
    seen: list = []
    real = api.load_scanpath_data

    def spy(*args, **kwargs):
        result = real(*args, **kwargs)
        seen.append(result)
        return result

    monkeypatch.setattr(api, "load_scanpath_data", spy)
    words_path, fix_path = files
    cli.main(
        [
            "analyze",
            "--words",
            str(words_path),
            "--fixations",
            str(fix_path),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert seen, "analyze did not load through the API"
    assert _readings(seen[0][1]) == EXPECTED
