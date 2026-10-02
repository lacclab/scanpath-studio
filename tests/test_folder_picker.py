"""BUG-98 — the 📁 folder picker runs in a child process, never in the server."""

from __future__ import annotations

import subprocess
import sys

import pytest

from scanpath_studio import app


@pytest.fixture
def platform(monkeypatch):
    """Pretend to be ``name`` with only ``tools`` on PATH."""

    def _set(name: str, *tools: str, frozen: bool = False):
        monkeypatch.setattr(app.sys, "platform", name)
        monkeypatch.setattr(
            app.shutil, "which", lambda tool: f"/bin/{tool}" if tool in tools else None
        )
        if frozen:
            monkeypatch.setattr(app.sys, "frozen", True, raising=False)
        else:
            monkeypatch.delattr(app.sys, "frozen", raising=False)

    return _set


def test_macos_uses_its_own_dialog(platform):
    platform("darwin", "osascript")
    command = app._folder_picker_command()
    assert command[:2] == ["osascript", "-e"] and "choose folder" in command[2]


def test_windows_uses_powershell_in_a_single_threaded_apartment(platform):
    platform("win32", "powershell")
    command = app._folder_picker_command()
    assert command[0] == "/bin/powershell" and "-STA" in command
    assert "FolderBrowserDialog" in command[-1]


def test_linux_prefers_zenity_then_kdialog(platform):
    platform("linux", "zenity", "kdialog")
    assert app._folder_picker_command()[0] == "zenity"
    platform("linux", "kdialog")
    assert app._folder_picker_command()[0] == "kdialog"


def test_tkinter_is_only_a_fallback_and_never_in_process(platform):
    platform("linux")
    command = app._folder_picker_command()
    assert command[:2] == [sys.executable, "-c"] and "tkinter" in command[2]


def test_the_desktop_bundle_never_relaunches_itself(platform):
    """Frozen, `sys.executable` is the app, and the bundle ships no tkinter."""
    platform("linux", frozen=True)
    assert app._folder_picker_command() is None


def _fake_run(monkeypatch, *, returncode=0, stdout="", raises=None):
    seen = {}

    def run(command, **kwargs):
        seen["command"] = command
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    monkeypatch.setattr(app.subprocess, "run", run)
    monkeypatch.setattr(app, "_folder_picker_command", lambda: ["picker"])
    return seen


def test_a_pick_comes_back_without_osascripts_trailing_slash(monkeypatch):
    seen = _fake_run(monkeypatch, stdout="/Users/me/corpora/\n")
    assert app._pick_directory_dialog() == "/Users/me/corpora"
    assert seen["command"] == ["picker"]


def test_a_bare_root_stays_a_root(monkeypatch):
    _fake_run(monkeypatch, stdout="/")
    assert app._pick_directory_dialog() == "/"


@pytest.mark.parametrize(
    "outcome",
    [
        {"returncode": 1},  # cancelled (osascript, zenity, kdialog)
        {"stdout": ""},  # cancelled (PowerShell, tkinter)
        {"raises": subprocess.TimeoutExpired("picker", 600)},
        {"raises": OSError("no display")},
    ],
)
def test_no_pick_is_none_and_never_raises(monkeypatch, outcome):
    _fake_run(monkeypatch, **outcome)
    assert app._pick_directory_dialog() is None


def test_no_picker_at_all_is_none(monkeypatch):
    monkeypatch.setattr(app, "_folder_picker_command", lambda: None)
    assert app._pick_directory_dialog() is None
