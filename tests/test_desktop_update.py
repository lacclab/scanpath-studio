"""The desktop app's own updater (#385)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from scanpath_studio import desktop_update as du
from scanpath_studio import updates

ROOT = Path(__file__).resolve().parents[1]


def _install(tmp_path, system="linux"):
    """A fake installed bundle under tmp_path, the way `install_at` sees it."""
    if system == "darwin":
        app = tmp_path / "Applications" / "ScanpathStudio.app"
        exe = app / "Contents" / "MacOS" / "ScanpathStudio"
    else:
        name = "ScanpathStudio.exe" if system == "win32" else "ScanpathStudio"
        exe = tmp_path / "opt" / "ScanpathStudio" / name
        (exe.parent / "_internal").mkdir(parents=True)
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("v1")
    return du.install_at(exe, system)


def _check(version="99.0.0", *, assets=None, digest="sha256:" + "0" * 64, size=1000):
    names = (
        assets
        if assets is not None
        else [
            "ScanpathStudio-linux-x86_64.tar.gz",
            "ScanpathStudio-windows-x86_64.zip",
            "ScanpathStudio-macos-arm64.dmg",
        ]
    )
    release = updates.Release(
        version=version,
        tag=f"v{version}",
        published_at="2026-10-09T10:00:00Z",
        url=f"https://github.com/lacclab/scanpath-studio/releases/tag/v{version}",
        assets=tuple(
            updates.Asset(name, f"{du.REPO_DOWNLOADS}v{version}/{name}", size, digest)
            for name in names
        ),
    )
    return updates.UpdateCheck(
        "update_available",
        "0.36.0",
        f"v{version} is out.",
        latest=release,
        install_kind="desktop",
    )


@pytest.fixture
def cache_home(tmp_path, monkeypatch):
    """Point every per-user state folder into tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path


def test_install_at_reads_each_os_layout():
    mac = du.install_at(
        Path("/Applications/ScanpathStudio.app/Contents/MacOS/ScanpathStudio"),
        "darwin",
    )
    assert mac.root == Path("/Applications/ScanpathStudio.app")
    assert mac.payload == ("Contents",)
    win = du.install_at(Path("C:/Apps/Scanpath Studio/ScanpathStudio.exe"), "win32")
    assert win.root == Path("C:/Apps/Scanpath Studio")
    assert win.payload == ("ScanpathStudio.exe", "_internal")
    linux = du.install_at(Path("/opt/ScanpathStudio/ScanpathStudio"), "linux")
    assert linux.payload == ("ScanpathStudio", "_internal")
    assert du.install_at(Path("/usr/bin/python3"), "linux") is None
    assert du.install_at(Path("/tmp/x/MacOS/ScanpathStudio"), "darwin") is None


def test_outside_the_frozen_app_there_is_no_install():
    assert du.current_install() is None


def test_executable_in_each_os():
    assert du.executable_in(Path("/s/ScanpathStudio.app"), "darwin") == Path(
        "/s/ScanpathStudio.app/Contents/MacOS/ScanpathStudio"
    )
    assert du.executable_in(Path("/s/ScanpathStudio"), "win32").name == (
        "ScanpathStudio.exe"
    )
    assert du.executable_in(Path("/s/ScanpathStudio"), "linux").name == "ScanpathStudio"


@pytest.mark.parametrize(
    ("system", "machine", "name"),
    [
        ("darwin", "arm64", "ScanpathStudio-macos-arm64.dmg"),
        ("win32", "AMD64", "ScanpathStudio-windows-x86_64.zip"),
        ("linux", "x86_64", "ScanpathStudio-linux-x86_64.tar.gz"),
        ("linux2", "x86_64", "ScanpathStudio-linux-x86_64.tar.gz"),
        ("darwin", "x86_64", None),
    ],
)
def test_update_archive_per_computer(system, machine, name):
    assert du.update_archive(system, machine) == name


def test_the_update_archives_are_the_ones_desktop_yml_builds():
    workflow = (ROOT / ".github/workflows/desktop.yml").read_text(encoding="utf-8")
    for name in set(du.UPDATE_ARCHIVES.values()):
        assert f"archive: {name}" in workflow, name


def test_state_dir_is_the_user_cache_on_the_same_volume(tmp_path, cache_home):
    install = _install(tmp_path)
    assert du.state_dir(install) == tmp_path / "cache" / "scanpath-studio" / "update"


def test_state_dir_falls_back_beside_the_install_on_another_volume(
    tmp_path, cache_home, monkeypatch
):
    install = _install(tmp_path)
    monkeypatch.setattr(du, "_device", lambda path: 1 if "cache" in str(path) else 2)
    assert du.state_dir(install) == install.root.parent / ".ScanpathStudio-update"


def test_a_newer_release_with_a_digest_can_be_installed(tmp_path, cache_home):
    install = _install(tmp_path)
    assert du.refusal(_check(), install, machine="x86_64") is None


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (lambda c: None, "Only the desktop app"),
        (
            lambda c: updates.UpdateCheck("up_to_date", "0.36.0", "", c.latest),
            "no newer release",
        ),
        (lambda c: _check("99.0.0rc1"), "pre-release"),
        (lambda c: _check(assets=[]), "no update for this computer"),
        (lambda c: _check(digest=""), "no checksum"),
        (lambda c: _check(size=10**15), "free"),
    ],
)
def test_each_refusal_says_why(tmp_path, cache_home, change, says):
    install = _install(tmp_path)
    check = change(_check())
    reason = du.refusal(
        check if check is not None else _check(),
        install if check is not None else None,
        machine="x86_64",
    )
    assert reason is not None and says in reason, reason


def test_a_read_only_install_is_refused(tmp_path, cache_home, monkeypatch):
    install = _install(tmp_path)
    monkeypatch.setattr(du.os, "access", lambda path, mode: Path(path) != install.root)
    assert "can't change" in du.refusal(_check(), install, machine="x86_64")


def test_a_translocated_mac_app_is_refused(tmp_path, cache_home):
    app = tmp_path / "AppTranslocation" / "X" / "d" / "ScanpathStudio.app"
    exe = app / "Contents" / "MacOS" / "ScanpathStudio"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    install = du.install_at(exe, "darwin")
    reason = du.refusal(_check(), install, machine="arm64", run=_codesign("T1"))
    assert "Applications" in reason


def test_an_update_already_under_way_is_refused(tmp_path, cache_home):
    install = _install(tmp_path)
    state = du.state_dir(install)
    state.mkdir(parents=True)
    du._write_json(state / du.PENDING, {"root": str(install.root), "at": time.time()})
    assert "already" in du.refusal(_check(), install, machine="x86_64")


def _codesign(team):
    """A fake `subprocess.run` answering `codesign -dv` with `team`."""

    def run(argv, **kwargs):
        if argv[:2] == ["codesign", "-dv"]:
            line = f"TeamIdentifier={team}" if team else "TeamIdentifier=not set"
            return subprocess.CompletedProcess(argv, 0, "", f"Identifier=x\n{line}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return run


def test_team_id_reads_codesign(tmp_path):
    assert du.team_id(tmp_path, run=_codesign("ABCDE12345")) == "ABCDE12345"
    assert du.team_id(tmp_path, run=_codesign(None)) is None


def test_an_ad_hoc_signed_mac_app_is_refused(tmp_path, cache_home):
    install = _install(tmp_path, "darwin")
    reason = du.refusal(_check(), install, machine="arm64", run=_codesign(None))
    assert "isn't signed" in reason


def test_child_env_starts_the_next_bundle_fresh():
    env = du.child_env({"LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/usr/x"})
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert env["LD_LIBRARY_PATH"] == "/usr/x"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_feed_release_reads_githubs_shape(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps(
            {
                "tag_name": "v99.0.0",
                "assets": [
                    {
                        "name": "a.zip",
                        "browser_download_url": "file:///a.zip",
                        "size": 3,
                        "digest": "sha256:ab",
                    }
                ],
            }
        )
    )
    release = du.feed_release(feed)
    assert release.version == "99.0.0"
    assert release.asset("a.zip").digest == "sha256:ab"
    with pytest.raises(updates.UpdateCheckError):
        du.feed_release(tmp_path / "missing.json")
