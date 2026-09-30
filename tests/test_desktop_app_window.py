"""ENG-85: the desktop launcher opens the app in its own browser window.

Chrome / Edge / Brave / Chromium's ``--app=<url>`` gives a window with no tabs
and no address bar; without one of them the launcher keeps the old behaviour,
a tab in the default browser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from desktop import launcher

URL = "http://127.0.0.1:8501"


@pytest.fixture
def opened(monkeypatch):
    """Record what the launcher starts instead of starting it."""
    calls: dict[str, list] = {"popen": [], "webbrowser": []}

    def fake_popen(args, **kwargs):
        calls["popen"].append((args, kwargs))

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda url: calls["webbrowser"].append(url) or True,
    )
    monkeypatch.setattr(launcher, "_wait_for_server", lambda url: True)
    monkeypatch.delenv("SCANPATH_DESKTOP_BROWSER", raising=False)
    return calls


def _fake_browser(tmp_path: Path) -> Path:
    exe = tmp_path / "Google Chrome"
    exe.write_text("")
    return exe


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "app"),
        ("app", "app"),
        ("APP", "app"),
        ("default", "default"),
        ("tab", "default"),
    ],
)
def test_browser_mode(monkeypatch, raw, expected):
    monkeypatch.setenv("SCANPATH_DESKTOP_BROWSER", raw)
    assert launcher._browser_mode() == expected


def test_unknown_browser_mode_keeps_the_app_window(monkeypatch, capsys):
    monkeypatch.setenv("SCANPATH_DESKTOP_BROWSER", "firefox")
    assert launcher._browser_mode() == "app"
    assert "Ignoring invalid SCANPATH_DESKTOP_BROWSER" in capsys.readouterr().out


def test_opens_an_app_window_when_a_chromium_browser_is_installed(
    opened, monkeypatch, tmp_path
):
    exe = _fake_browser(tmp_path)
    monkeypatch.setattr(launcher, "_app_browser_candidates", lambda: [exe])
    launcher._open_browser_when_ready(8501)
    assert [args for args, _ in opened["popen"]] == [[str(exe), f"--app={URL}"]]
    assert opened["webbrowser"] == []


def test_the_app_window_is_detached_from_the_launcher(opened, monkeypatch, tmp_path):
    # The quit watcher ends this process with os._exit; the user's browser must
    # survive it.
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    exe = _fake_browser(tmp_path)
    assert launcher._open_app_window(exe, URL)
    _, kwargs = opened["popen"][0]
    assert kwargs["start_new_session"] is True
    assert kwargs["stdout"] is subprocess.DEVNULL


def test_falls_back_to_a_tab_without_a_chromium_browser(opened, monkeypatch, tmp_path):
    monkeypatch.setattr(
        launcher, "_app_browser_candidates", lambda: [tmp_path / "missing"]
    )
    launcher._open_browser_when_ready(8501)
    assert opened["popen"] == []
    assert opened["webbrowser"] == [URL]


def test_falls_back_to_a_tab_when_the_browser_will_not_start(
    opened, monkeypatch, tmp_path
):
    exe = _fake_browser(tmp_path)
    monkeypatch.setattr(launcher, "_app_browser_candidates", lambda: [exe])

    def broken_popen(args, **kwargs):
        raise PermissionError("not executable")

    monkeypatch.setattr(launcher.subprocess, "Popen", broken_popen)
    launcher._open_browser_when_ready(8501)
    assert opened["webbrowser"] == [URL]


def test_default_mode_skips_the_app_window(opened, monkeypatch, tmp_path):
    exe = _fake_browser(tmp_path)
    monkeypatch.setattr(launcher, "_app_browser_candidates", lambda: [exe])
    monkeypatch.setenv("SCANPATH_DESKTOP_BROWSER", "default")
    launcher._open_browser_when_ready(8501)
    assert opened["popen"] == []
    assert opened["webbrowser"] == [URL]


def test_macos_candidates_are_the_bundle_executables(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    candidates = [str(path) for path in launcher._app_browser_candidates()]
    assert candidates[0] == (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    assert (
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" in candidates
    )


def test_windows_candidates_include_edge(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    candidates = launcher._app_browser_candidates()
    assert any(path.name == "msedge.exe" for path in candidates)


def test_linux_candidates_come_from_path(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    monkeypatch.setattr(
        launcher.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "chromium" else None,
    )
    assert launcher._app_browser_candidates() == [Path("/usr/bin/chromium")]


def test_macos_brings_the_browser_to_the_front(monkeypatch):
    # A running browser takes the window but stays where it was, so the launcher
    # activates it — otherwise the window can open buried behind others.
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    ran = []
    monkeypatch.setattr(
        launcher.subprocess, "run", lambda args, **kwargs: ran.append(args)
    )
    launcher._bring_to_front(
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    )
    assert ran == [["open", "-a", "/Applications/Microsoft Edge.app"]]


def test_bringing_to_the_front_is_macos_only(monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    ran = []
    monkeypatch.setattr(
        launcher.subprocess, "run", lambda args, **kwargs: ran.append(args)
    )
    launcher._bring_to_front(Path("/usr/bin/chromium"))
    assert ran == []
