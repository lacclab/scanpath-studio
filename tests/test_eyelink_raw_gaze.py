"""Raw gaze from EyeLink recordings, read on request (experimental)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

import scanpath_studio.api as sps
from scanpath_studio import cli, eyelink, persistence
from tests.eyelink_fixtures import EXPECTED, SESSION, write_experiment

RAW_GAZE_COLUMNS = [
    "participant_id",
    "trial_id",
    "screen_id",
    "screen_index",
    "x",
    "y",
    "timestamp_ms",
    "pupil_area",
    "eye",
]


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _tables(tmp_path: Path, **options) -> eyelink.SessionTables:
    asc = write_experiment(tmp_path, samples=True, **options)
    return eyelink.session_tables(asc, image_dir=tmp_path / "images", raw_gaze=True)


def _rows(frame: pd.DataFrame, pupil: str = "pupil_area") -> list[dict]:
    frame = frame.rename(columns={pupil: "pupil"})
    columns = list(EXPECTED["samples"][0])
    return frame[columns].astype({"trial_id": str}).to_dict("records")


def _same(rows: list[dict], expected: list[dict]) -> bool:
    """Equal, with a missing value equal to a missing value."""

    def key(row: dict) -> dict:
        return {
            k: "NaN" if isinstance(v, float) and np.isnan(v) else v
            for k, v in row.items()
        }

    return [key(r) for r in rows] == [key(r) for r in expected]


def test_samples_on_fixation_clock(tmp_path):
    t = _tables(tmp_path)
    assert list(t.raw_gaze.columns) == RAW_GAZE_COLUMNS
    assert set(t.raw_gaze["participant_id"]) == {SESSION}
    assert _same(_rows(t.raw_gaze), EXPECTED["samples"])
    # The fixations count from the same START line: trial 1's first fixation
    # (onset 1020) and its sample at 1100 are 80 ms apart.
    first_fix = t.fixations.iloc[0]["timestamp_ms"]
    first_sample = t.raw_gaze.iloc[0]["timestamp_ms"]
    assert (first_fix, first_sample) == (30, 110)


def test_lost_eye_pupil_missing(tmp_path):
    gaze = _tables(tmp_path).raw_gaze
    lost = gaze[gaze["x"].isna()]
    assert len(lost) == 1
    # EyeLink logged a 0 pupil for the tick it lost; that is no measurement.
    assert lost[["x", "y", "pupil_area"]].isna().all(axis=None)
    assert gaze.loc[gaze["x"].notna(), "pupil_area"].notna().all()


def test_samples_between_screens_dropped(tmp_path):
    asc = write_experiment(tmp_path, samples=True)
    recorded = eyelink.read_asc(asc, samples=True).samples
    gaze = eyelink.session_tables(
        asc, image_dir=tmp_path / "images", raw_gaze=True
    ).raw_gaze
    start = {"1": 990, "2": 3010}
    # 2500 is after trial 1's END (2000) and before trial 2's TRIALID (3000).
    assert 2500 in EXPECTED["samples_between_screens"]
    kept_ticks = set(gaze["timestamp_ms"] + gaze["trial_id"].map(start))
    between = set(EXPECTED["samples_between_screens"])
    assert between <= set(recorded["time"])
    assert not kept_ticks & between
    assert len(gaze) == len(recorded) - len(between)


def test_binocular_samples_keep_both_eyes(tmp_path):
    gaze = _tables(tmp_path, binocular=True).raw_gaze
    assert _same(_rows(gaze[gaze["eye"] == "R"]), EXPECTED["samples"])
    assert _same(_rows(gaze[gaze["eye"] == "L"]), EXPECTED["samples_left"])


def test_pupil_column_named_by_the_pupil_line(tmp_path):
    gaze = _tables(tmp_path, pupil="DIAMETER").raw_gaze
    assert "pupil_diameter" in gaze.columns and "pupil_area" not in gaze.columns
    assert _same(_rows(gaze, "pupil_diameter"), EXPECTED["samples"])


def test_events_only_session_has_no_raw_gaze(tmp_path):
    asc = write_experiment(tmp_path, samples=True)
    t = eyelink.session_tables(asc, image_dir=tmp_path / "images")
    assert t.raw_gaze is None


def test_events_only_recording_has_empty_raw_gaze(tmp_path):
    asc = write_experiment(tmp_path)
    t = eyelink.session_tables(asc, image_dir=tmp_path / "images", raw_gaze=True)
    assert t.raw_gaze.empty and "participant_id" in t.raw_gaze.columns
    assert any("no gaze samples" in note for note in t.notes)
    study_dir = tmp_path / "study"
    eyelink.import_eyelink(tmp_path / "exp", study_dir, workers=1, raw_gaze=True)
    # No empty file, whose plain ``pupil`` column would join other sessions'.
    assert not (study_dir / "raw_gaze" / f"{SESSION}.parquet").exists()
    manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sessions"][SESSION]["raw_gaze"] is True
    assert eyelink.load_eyelink(study_dir).raw_gaze is None


def test_edf_converted_with_samples_when_raw_gaze(tmp_path, monkeypatch):
    asc = write_experiment(tmp_path, samples=True)
    edf = asc.with_suffix(".edf")
    edf.write_bytes(b"EDF")
    calls = []

    def fake_convert(source, out_dir, *, samples=False):
        calls.append(samples)
        return asc

    monkeypatch.setattr(eyelink, "convert_edf", fake_convert)
    t = eyelink.session_tables(
        edf, image_dir=tmp_path / "images", session_dir=asc.parent, raw_gaze=True
    )
    assert calls == [True]
    assert len(t.raw_gaze) == len(EXPECTED["samples"])


def _add_session(experiment: Path, pid: str) -> None:
    results = experiment / "results"
    shutil.copytree(results / SESSION, results / pid)
    (results / pid / f"{SESSION}.asc").rename(results / pid / f"{pid}.asc")


def _experiment(tmp_path: Path, pids=("p02",)) -> Path:
    write_experiment(tmp_path, samples=True)
    experiment = tmp_path / "exp"
    for pid in pids:
        _add_session(experiment, pid)
    return experiment


def test_raw_gaze_parquet_row_groups_per_trial(tmp_path):
    experiment = _experiment(tmp_path, pids=())
    study_dir = tmp_path / "study"
    report = eyelink.import_eyelink(experiment, study_dir, workers=1, raw_gaze=True)
    assert report.imported == [SESSION]
    path = study_dir / "raw_gaze" / f"{SESSION}.parquet"
    parquet = pq.ParquetFile(path)
    groups = [
        parquet.read_row_group(i).to_pandas() for i in range(parquet.num_row_groups)
    ]
    assert [sorted(set(g["trial_id"])) for g in groups] == [["1"], ["2"]]
    frame = pd.read_parquet(path)
    assert frame.equals(
        frame.sort_values(["trial_id", "timestamp_ms"], kind="stable").reset_index(
            drop=True
        )
    )
    assert len(frame) == len(EXPECTED["samples"])
    manifest = json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sessions"][SESSION]["raw_gaze"] is True


def test_rerun_with_raw_gaze_redoes_sessions_without_it(tmp_path):
    experiment = _experiment(tmp_path)
    study_dir = tmp_path / "study"
    first = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert sorted(first.imported) == ["p01", "p02"]
    assert not (study_dir / "raw_gaze").exists() or not any(
        (study_dir / "raw_gaze").iterdir()
    )
    assert eyelink.load_eyelink(study_dir).raw_gaze is None

    again = eyelink.import_eyelink(experiment, study_dir, workers=1, raw_gaze=True)
    assert sorted(again.imported) == ["p01", "p02"] and again.skipped == []

    # Without raw gaze, a session that has it is unchanged and keeps it.
    third = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert third.imported == [] and sorted(third.skipped) == ["p01", "p02"]
    gaze = eyelink.load_eyelink(study_dir, participants=["p02"], raw_gaze=True).raw_gaze
    assert set(gaze["participant_id"]) == {"p02"}
    assert len(gaze) == len(EXPECTED["samples"])


def test_raw_gaze_reads_two_sessions_at_a_time_by_default(tmp_path, monkeypatch):
    experiment = _experiment(tmp_path)
    seen = []
    real = eyelink._read_sessions

    def spy(jobs, workers):
        seen.append(workers)
        return real(jobs, 1)

    monkeypatch.setattr(eyelink, "_read_sessions", spy)
    eyelink.import_eyelink(experiment, tmp_path / "study", raw_gaze=True)
    eyelink.import_eyelink(experiment, tmp_path / "events")
    assert eyelink.RAW_GAZE_WORKERS == 2
    assert seen[0] == min(2, max(1, (os.cpu_count() or 1) - 1))
    assert seen[1] == max(1, (os.cpu_count() or 1) - 1)


def test_load_eyelink_raw_gaze_choice(tmp_path):
    experiment = _experiment(tmp_path)
    study_dir = tmp_path / "study"
    eyelink.import_eyelink(experiment, study_dir, workers=1, raw_gaze=True)
    # Raw gaze is read only when asked for.
    assert eyelink.load_eyelink(study_dir).raw_gaze is None
    every = eyelink.load_eyelink(study_dir, raw_gaze=True).raw_gaze
    assert set(every["participant_id"]) == {"p01", "p02"}
    assert eyelink.load_eyelink(study_dir, raw_gaze=False).raw_gaze is None
    only = eyelink.load_eyelink(study_dir, raw_gaze=["p02"])
    assert set(only.raw_gaze["participant_id"]) == {"p02"}
    assert set(only.fixations["participant_id"]) == {"p01", "p02"}


@pytest.fixture
def cache_dir(tmp_path, monkeypatch) -> Path:
    """A private cache folder, with saving on: never the user's own."""
    root = tmp_path / "cache"
    monkeypatch.setenv(persistence.STATE_DIR_ENV_VAR, str(root))
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    return root


def test_add_eyelink_dataset_raw_gaze_participants_only(tmp_path, cache_dir):
    experiment = _experiment(tmp_path)
    study_dir = tmp_path / "study"
    eyelink.import_eyelink(experiment, study_dir, workers=1, raw_gaze=True)
    sps.add_eyelink_dataset("Gaze", study_dir, raw_gaze_participants=["p02"])
    session: dict = {}
    assert persistence.restore_state(session, cache_dir)
    entry = session["_datasets"]["Gaze"]
    gaze = entry["raw_gaze"]
    assert set(gaze["participant_id"].astype(str)) == {"p02"}
    # Trimmed to the screens kept for fixations: trial 1's question screen has
    # no words, so its samples go with its fixations.
    kept = [s for s in EXPECTED["samples"] if s["screen_id"] == "screen_1"]
    assert len(gaze) == len(kept)
    assert set(entry["fixations"]["participant_id"].astype(str)) == {"p01", "p02"}

    sps.add_eyelink_dataset("No gaze", study_dir)
    session = {}
    assert persistence.restore_state(session, cache_dir)
    # add_dataset stores an empty raw-gaze table for a dataset without one.
    assert session["_datasets"]["No gaze"]["raw_gaze"].empty


def test_import_eyelink_cli_raw_gaze(tmp_path, cache_dir, capsys, monkeypatch):
    # On a 2-CPU machine raw gaze is read one session at a time.
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    experiment = _experiment(tmp_path, pids=())
    study_dir = tmp_path / "study"
    cli.main(
        [
            "import-eyelink",
            str(experiment),
            "--study-dir",
            str(study_dir),
            "--raw-gaze",
            "--add",
            "Gaze CLI",
            "--raw-gaze-participants",
            SESSION,
        ]
    )
    captured = capsys.readouterr()
    assert "[1/1] p01 ok" in captured.out and "Added 'Gaze CLI'" in captured.out
    assert "Reading 1 session at a time" in captured.err
    assert (study_dir / "raw_gaze" / f"{SESSION}.parquet").is_file()


def test_eye_switch_keeps_fixations_and_drops_raw_gaze(tmp_path):
    """A session whose second recording block tracks the other eye: its
    samples cannot be told apart by eye, so its raw gaze is left out and said
    so; its fixations, each an event of its own eye, stay."""
    asc = write_experiment(tmp_path, samples=True)
    text = asc.read_text(encoding="utf-8").replace(
        "START\t3010 \tRIGHT\tSAMPLES\tEVENTS", "START\t3010 \tLEFT\tSAMPLES\tEVENTS"
    )
    text = text.replace("EFIX\tR\t3050", "EFIX\tL\t3050").replace(
        "EFIX\tR\t3260", "EFIX\tL\t3260"
    )
    asc.write_text(text, encoding="utf-8")
    rec = eyelink.read_asc(asc, samples=True)
    assert rec.eyes_switched and rec.samples is not None and rec.samples.empty
    t = eyelink.session_tables(asc, image_dir=tmp_path / "images", raw_gaze=True)
    assert t.raw_gaze is not None and t.raw_gaze.empty
    assert (
        "The recording tracks different eyes in different blocks (R, then L), "
        "so its samples cannot be told apart by eye; its raw gaze was left out."
    ) in t.notes
    by_trial = t.fixations.groupby("trial_id")["eye"].unique().to_dict()
    assert list(by_trial["1"]) == ["R"] and list(by_trial["2"]) == ["L"]
