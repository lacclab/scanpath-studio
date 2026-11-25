from __future__ import annotations

import gc
import json
import os
import shutil
import weakref
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import eyelink, progress
from tests.eyelink_fixtures import EXPECTED, SESSION, write_experiment

PIDS = ["p01", "p02", "p03"]
# A fixation line no reader can parse.
CORRUPT_LINE = "EFIX\tR\tbroken\n"


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _add_session(experiment: Path, pid: str) -> Path:
    """A copy of the fixture's session as ``results/<pid>/<pid>.asc``."""
    results = experiment / "results"
    target = results / pid
    shutil.copytree(results / SESSION, target)
    (target / f"{SESSION}.asc").rename(target / f"{pid}.asc")
    return target / f"{pid}.asc"


@pytest.fixture
def study(tmp_path) -> tuple[Path, Path]:
    """Three sessions in one experiment folder, and the study folder to write."""
    write_experiment(tmp_path)
    experiment = tmp_path / "exp"
    for pid in PIDS[1:]:
        _add_session(experiment, pid)
    return experiment, tmp_path / "study"


def _manifest(study_dir: Path) -> dict:
    return json.loads((study_dir / "manifest.json").read_text(encoding="utf-8"))


def _bump_mtime(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))


def test_import_writes_layout_and_manifest(study):
    experiment, study_dir = study
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert report.study_dir == study_dir.resolve()
    assert sorted(report.imported) == PIDS
    assert report.skipped == [] and report.failed == {}
    for table in ("fixations", "words", "trial_metadata"):
        assert sorted(p.name for p in (study_dir / table).iterdir()) == [
            f"{pid}.parquet" for pid in PIDS
        ]
    assert not (study_dir / "raw_gaze").exists()
    assert not (study_dir / "asc").exists()
    fixations = pd.read_parquet(study_dir / "fixations" / "p02.parquet")
    assert (fixations["participant_id"] == "p02").all()
    assert len(fixations) == len(EXPECTED["fixations"])
    # Image paths are relative to the study folder, and every one is there.
    images = set(fixations["image_path"].dropna())
    assert images and all(p.startswith("images/") for p in images)
    assert all((study_dir / p).is_file() for p in images)
    manifest = _manifest(study_dir)
    assert manifest["version"] == 1
    assert manifest["display"] == list(EXPECTED["display"])
    entry = manifest["sessions"]["p02"]
    source = experiment / "results" / "p02" / "p02.asc"
    assert entry["source"] == str(source.resolve())
    assert entry["size"] == source.stat().st_size
    assert entry["mtime_ns"] == source.stat().st_mtime_ns
    assert entry["parser_version"] == eyelink.PARSER_VERSION
    assert entry["raw_gaze"] is False
    assert entry["status"] == "ok" and entry["error"] is None
    assert entry["notes"] == []


def test_rerun_skips_unchanged(study):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    written = (study_dir / "fixations" / "p01.parquet").stat().st_mtime_ns
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert report.imported == [] and report.failed == {}
    assert sorted(report.skipped) == PIDS
    assert (study_dir / "fixations" / "p01.parquet").stat().st_mtime_ns == written
    rebuilt = eyelink.import_eyelink(experiment, study_dir, workers=1, rebuild=True)
    assert sorted(rebuilt.imported) == PIDS


def test_rerun_redoes_changed_and_new(study):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    _bump_mtime(experiment / "results" / "p02" / "p02.asc")
    _add_session(experiment, "p04")
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert sorted(report.imported) == ["p02", "p04"]
    assert sorted(report.skipped) == ["p01", "p03"]
    assert sorted(_manifest(study_dir)["sessions"]) == [*PIDS, "p04"]


def test_parser_version_change_redoes_all(study, monkeypatch):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    monkeypatch.setattr(eyelink, "PARSER_VERSION", eyelink.PARSER_VERSION + 1)
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert sorted(report.imported) == PIDS


def test_failed_session_reported_and_retried(study):
    experiment, study_dir = study
    asc = experiment / "results" / "p02" / "p02.asc"
    good = asc.read_bytes()
    asc.write_bytes(good + CORRUPT_LINE.encode())
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert sorted(report.imported) == ["p01", "p03"]
    assert list(report.failed) == ["p02"] and report.failed["p02"]
    entry = _manifest(study_dir)["sessions"]["p02"]
    assert entry["status"] == "failed"
    assert entry["error"] == report.failed["p02"]
    assert not (study_dir / "fixations" / "p02.parquet").exists()
    # The failed session is not part of the study until it imports.
    assert eyelink.load_eyelink(study_dir).fixations[
        "participant_id"
    ].unique().tolist() == [
        "p01",
        "p03",
    ]

    asc.write_bytes(good)
    _bump_mtime(asc)
    retried = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert retried.imported == ["p02"] and retried.failed == {}
    assert sorted(retried.skipped) == ["p01", "p03"]
    assert _manifest(study_dir)["sessions"]["p02"]["status"] == "ok"


def test_duplicate_stems_refused(study):
    experiment, study_dir = study
    other = experiment.parent / "elsewhere"
    other.mkdir()
    shutil.copy(experiment / "results" / "p02" / "p02.asc", other / "p02.asc")
    with pytest.raises(ValueError, match="p02"):
        eyelink.import_eyelink([experiment, other], study_dir, workers=1)
    assert not study_dir.exists()


def test_folder_search_prefers_edf_over_its_asc(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()
    for name in ("a.edf", "a.asc", "b.asc", "notes.txt"):
        (folder / name).write_bytes(b"")
    assert [p.name for p in eyelink.study_sources(folder)] == ["a.edf", "b.asc"]


def test_session_dir_refused_with_several_sources(study):
    experiment, study_dir = study
    with pytest.raises(ValueError, match="experiment_dir"):
        eyelink.import_eyelink(
            experiment, study_dir, session_dir=experiment / "results" / "p01"
        )


def test_entries_are_gated(study, monkeypatch):
    experiment, study_dir = study
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL")
    with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
        eyelink.import_eyelink(experiment, study_dir)
    with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
        eyelink.load_eyelink(study_dir)


def test_load_eyelink_round_trip_and_participants_filter(study):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    data = eyelink.load_eyelink(study_dir)
    assert sorted(data.fixations["participant_id"].unique()) == PIDS
    assert len(data.fixations) == 3 * len(EXPECTED["fixations"])
    assert sorted(data.trial_metadata["participant_id"].unique()) == PIDS
    assert data.display == EXPECTED["display"]
    assert data.raw_gaze is None
    assert data.notes == {pid: [] for pid in PIDS}
    for frame in (data.fixations, data.words):
        paths = frame["image_path"].dropna()
        assert all(Path(p).is_absolute() and Path(p).is_file() for p in paths)

    # The frames match the session read directly, image paths aside.
    direct = eyelink.session_tables(
        experiment / "results" / "p02" / "p02.asc", image_dir=study_dir / "images"
    )
    for got, want in ((data.fixations, direct.fixations), (data.words, direct.words)):
        got = got[got["participant_id"] == "p02"].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            got.drop(columns="image_path"),
            want.drop(columns="image_path"),
            check_dtype=False,
        )
        assert [Path(p).resolve() for p in got["image_path"].dropna()] == [
            Path(p).resolve() for p in want["image_path"].dropna()
        ]

    some = eyelink.load_eyelink(study_dir, participants=["p03", "p01"])
    assert sorted(some.fixations["participant_id"].unique()) == ["p01", "p03"]
    assert sorted(some.notes) == ["p01", "p03"]
    with pytest.raises(ValueError, match="p09"):
        eyelink.load_eyelink(study_dir, participants=["p09"])


def test_different_displays_leave_the_study_without_one(study):
    experiment, study_dir = study
    asc = experiment / "results" / "p03" / "p03.asc"
    asc.write_text(
        asc.read_text(encoding="utf-8").replace(
            "DISPLAY_COORDS 0 0 1279 1023", "DISPLAY_COORDS 0 0 1919 1079"
        ),
        encoding="utf-8",
    )
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert _manifest(study_dir)["display"] is None
    assert any("1920×1080" in note for note in report.notes["p03"])
    assert report.notes["p01"] == []
    data = eyelink.load_eyelink(study_dir)
    assert data.display is None
    assert any("1920×1080" in note for note in data.notes["p03"])
    # Read alone, the session's display is the study's.
    assert eyelink.load_eyelink(study_dir, participants=["p03"]).display == (1920, 1080)


def test_parallel_matches_serial(study, tmp_path):
    experiment, study_dir = study
    serial_dir = tmp_path / "serial"
    eyelink.import_eyelink(experiment, serial_dir, workers=1)
    report = eyelink.import_eyelink(experiment, study_dir, workers=2)
    assert sorted(report.imported) == PIDS
    serial = eyelink.load_eyelink(serial_dir)
    parallel = eyelink.load_eyelink(study_dir)
    for name in ("fixations", "words", "trial_metadata"):
        a = getattr(serial, name).drop(columns="image_path", errors="ignore")
        b = getattr(parallel, name).drop(columns="image_path", errors="ignore")
        pd.testing.assert_frame_equal(a, b)
    assert sorted(p.name for p in (serial_dir / "images").iterdir()) == sorted(
        p.name for p in (study_dir / "images").iterdir()
    )


def test_progress_callback_counts(study, monkeypatch):
    experiment, study_dir = study
    calls, reported = [], []
    monkeypatch.setattr(
        progress,
        "report",
        lambda done, total, *, unit, detail: reported.append(
            (done, total, unit, detail)
        ),
    )
    eyelink.import_eyelink(
        experiment,
        study_dir,
        workers=1,
        progress=lambda done, total, pid: calls.append((done, total, pid)),
    )
    assert [(done, total) for done, total, _ in calls] == [(1, 3), (2, 3), (3, 3)]
    assert sorted(pid for _, _, pid in calls) == PIDS
    assert reported == [(d, t, "sessions", pid) for d, t, pid in calls]


def test_failure_message_names_the_error(study):
    experiment, study_dir = study
    asc = experiment / "results" / "p02" / "p02.asc"
    asc.write_bytes(asc.read_bytes() + CORRUPT_LINE.encode())
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert report.failed["p02"].startswith("IndexError: ")


def test_corrupt_session_fails_alone_in_the_pool(study):
    experiment, study_dir = study
    asc = experiment / "results" / "p02" / "p02.asc"
    asc.write_bytes(asc.read_bytes() + CORRUPT_LINE.encode())
    report = eyelink.import_eyelink(experiment, study_dir, workers=2)
    assert sorted(report.imported) == ["p01", "p03"]
    assert list(report.failed) == ["p02"]


def test_pool_keeps_no_finished_session(study, monkeypatch):
    """Each session's tables are released once written, so a study's memory
    does not grow with its size."""
    experiment, study_dir = study
    _add_session(experiment, "p04")
    _add_session(experiment, "p05")
    written = []
    real = eyelink._write_session

    def write(study_dir, pid, tables):
        gc.collect()
        assert [ref() for ref in written] == [None] * len(written)
        written.append(weakref.ref(tables))
        real(study_dir, pid, tables)

    monkeypatch.setattr(eyelink, "_write_session", write)
    report = eyelink.import_eyelink(experiment, study_dir, workers=2)
    assert len(report.imported) == 5 and len(written) == 5


def test_write_error_fails_only_that_session(study, monkeypatch):
    experiment, study_dir = study
    real = eyelink._replace_atomically

    def replace(path, write):
        if path.name == "p02.parquet" and path.parent.name == "words":
            raise OSError("disk full")
        real(path, write)

    monkeypatch.setattr(eyelink, "_replace_atomically", replace)
    report = eyelink.import_eyelink(experiment, study_dir, workers=1)
    assert sorted(report.imported) == ["p01", "p03"]
    assert report.failed == {"p02": "OSError: disk full"}
    assert not list(study_dir.rglob("p02.parquet"))
    assert _manifest(study_dir)["sessions"]["p02"]["status"] == "failed"


def test_unsafe_participant_ids_refused(study, tmp_path):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    manifest = _manifest(study_dir)
    manifest["sessions"]["../evil"] = manifest["sessions"]["p01"]
    (study_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.\./evil"):
        eyelink.load_eyelink(study_dir)

    folder = tmp_path / "dots"
    folder.mkdir()
    shutil.copy(experiment / "results" / "p01" / "p01.asc", folder / "..asc")
    with pytest.raises(ValueError, match="participant id"):
        eyelink.import_eyelink(folder, tmp_path / "other", workers=1)


def test_image_paths_outside_the_study_dropped(study):
    experiment, study_dir = study
    eyelink.import_eyelink(experiment, study_dir, workers=1)
    path = study_dir / "fixations" / "p01.parquet"
    frame = pd.read_parquet(path)
    secret = study_dir.parent / "secret.png"
    frame.loc[0, "image_path"] = str(secret)
    frame.loc[1, "image_path"] = "../secret.png"
    frame.to_parquet(path, index=False)
    data = eyelink.load_eyelink(study_dir, participants=["p01"])
    paths = data.fixations["image_path"]
    assert pd.isna(paths.iloc[0]) and pd.isna(paths.iloc[1])
    assert all(
        Path(p).resolve().is_relative_to(study_dir.resolve()) for p in paths.dropna()
    )
    dropped = [n for n in data.notes["p01"] if "outside the study folder" in n]
    assert len(dropped) == 2
