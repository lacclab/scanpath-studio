from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from scanpath_studio import eyelink


@pytest.fixture
def experimental(monkeypatch):
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")


def _fake(tmp_path: Path, body: str | None = None) -> Path:
    """A stand-in edf2asc: writes ``<stem>.asc`` into the ``-p`` folder and
    records its argv, one argument per line."""
    script = tmp_path / "fake_edf2asc"
    argv_log = tmp_path / "argv.txt"
    body = body or (
        f'printf "%s\\n" "$@" > "{argv_log}"\n'
        'edf="$1"; out=""\n'
        'while [ $# -gt 0 ]; do [ "$1" = "-p" ] && out="$2"; shift; done\n'
        'stem=$(basename "$edf" .edf)\n'
        'echo "converted" > "$out/$stem.asc"\n'
    )
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _argv(tmp_path: Path) -> list[str]:
    return (tmp_path / "argv.txt").read_text().splitlines()


def test_find_uses_env_var(tmp_path, monkeypatch):
    fake = _fake(tmp_path)
    monkeypatch.setenv("SCANPATH_EDF2ASC", str(fake))
    assert eyelink.find_edf2asc() == fake


def test_find_missing_names_where_to_get_it(tmp_path, monkeypatch):
    monkeypatch.delenv("SCANPATH_EDF2ASC", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(eyelink, "KNOWN_EDF2ASC_PATHS", (tmp_path / "edf2asc",))
    with pytest.raises(eyelink.Edf2AscNotFoundError) as err:
        eyelink.find_edf2asc()
    assert "EyeLink Developers Kit" in str(err.value)
    assert "SCANPATH_EDF2ASC" in str(err.value)


def test_convert_events_only_args(tmp_path, monkeypatch, experimental):
    monkeypatch.setenv("SCANPATH_EDF2ASC", str(_fake(tmp_path)))
    edf = tmp_path / "s1.edf"
    edf.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    asc = eyelink.convert_edf(edf, out)
    assert asc == out / "s1.asc"
    assert _argv(tmp_path) == [
        str(edf),
        "-t",
        "-c",
        "-y",
        "-utf8",
        "-e",
        "-p",
        str(out),
    ]


def test_convert_with_samples_drops_e(tmp_path, monkeypatch, experimental):
    monkeypatch.setenv("SCANPATH_EDF2ASC", str(_fake(tmp_path)))
    edf = tmp_path / "s1.edf"
    edf.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    eyelink.convert_edf(edf, out, samples=True)
    assert "-e" not in _argv(tmp_path)


def test_bad_cpu_type_explains_rosetta(tmp_path, monkeypatch, experimental):
    monkeypatch.setenv("SCANPATH_EDF2ASC", str(_fake(tmp_path)))

    def boom(*args, **kwargs):
        raise OSError(86, "Bad CPU type in executable")

    monkeypatch.setattr(subprocess, "run", boom)
    edf = tmp_path / "s1.edf"
    edf.write_bytes(b"x")
    with pytest.raises(eyelink.Edf2AscError, match="softwareupdate --install-rosetta"):
        eyelink.convert_edf(edf, tmp_path)


def test_nonzero_exit_reports_output(tmp_path, monkeypatch, experimental):
    monkeypatch.setenv("SCANPATH_EDF2ASC", str(_fake(tmp_path, "echo boom\nexit 1\n")))
    edf = tmp_path / "s1.edf"
    edf.write_bytes(b"x")
    with pytest.raises(eyelink.Edf2AscError, match="boom"):
        eyelink.convert_edf(edf, tmp_path)


def test_gate_off_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)
    with pytest.raises(ValueError, match="SCANPATH_EXPERIMENTAL"):
        eyelink.convert_edf(tmp_path / "s1.edf", tmp_path)
