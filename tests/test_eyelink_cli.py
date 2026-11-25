"""`scanpath-studio import-eyelink` and `render --eyelink-study` (experimental)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scanpath_studio import cli, eyelink, persistence
from tests.eyelink_fixtures import write_experiment
from tests.test_eyelink_study import CORRUPT_LINE


@pytest.fixture(autouse=True)
def _experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


@pytest.fixture
def cache_dir(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "cache"
    monkeypatch.setenv(persistence.STATE_DIR_ENV_VAR, str(root))
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    return root


@pytest.fixture
def experiment(tmp_path) -> Path:
    write_experiment(tmp_path)
    return tmp_path / "exp"


def _import(experiment: Path, study: Path, *extra: str) -> None:
    cli.main(
        ["import-eyelink", str(experiment), "--study-dir", str(study), "--workers", "1"]
        + list(extra)
    )


def test_import_eyelink_cli_summary_and_exit_code(experiment, tmp_path, capsys):
    study = tmp_path / "study"
    _import(experiment, study)
    out = capsys.readouterr().out
    assert "[1/1] p01 ok" in out
    assert f"Imported 1, skipped 0, failed 0 → {study.resolve()}" in out

    _import(experiment, study)
    out = capsys.readouterr().out
    assert "[1/1] p01 skipped" in out
    assert "Imported 0, skipped 1, failed 0" in out

    asc = experiment / "results" / "p01" / "p01.asc"
    asc.write_bytes(asc.read_bytes() + CORRUPT_LINE.encode())
    with pytest.raises(SystemExit) as exc:
        _import(experiment, study, "--rebuild")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "[1/1] p01 failed:" in out and "failed 1" in out


def test_import_eyelink_cli_add(experiment, tmp_path, cache_dir, capsys):
    study = tmp_path / "study"
    _import(experiment, study, "--add", "Pilot EL")
    assert "Added 'Pilot EL'" in capsys.readouterr().out
    from scanpath_studio import api

    names = [r["name"] for r in api.cache_status()["datasets"]]
    assert "Pilot EL" in names


def test_render_eyelink_study_writes_png_or_html(experiment, tmp_path, capsys):
    study = tmp_path / "study"
    _import(experiment, study)
    capsys.readouterr()
    out = tmp_path / "fig.html"
    data = eyelink.load_eyelink(study)
    row = data.fixations.iloc[0]
    cli.main(
        [
            "render",
            "--eyelink-study",
            str(study),
            "-p",
            str(row["participant_id"]),
            "-t",
            str(row["trial_id"]),
            "--screen",
            str(row["screen_id"]),
            "-o",
            str(out),
        ]
    )
    assert out.is_file() and out.stat().st_size > 1000


def test_hidden_when_gate_off(monkeypatch, capsys):
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)
    cli.main(["--help"])
    assert "import-eyelink" not in capsys.readouterr().out
    assert "import-eyelink" not in cli._commands()
    with pytest.raises(SystemExit) as exc:
        cli.main(["import-eyelink", "x", "--study-dir", "y"])
    assert exc.value.code == 2
    assert "SCANPATH_EXPERIMENTAL" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        cli.main(["render", "--eyelink-study", "x", "-o", "o.html"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        cli.main(["render", "--help"])
    assert "--eyelink-study" not in capsys.readouterr().out
