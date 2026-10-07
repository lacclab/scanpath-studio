"""The desktop app's own updater (#385)."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

import pytest

from scanpath_studio import desktop_update as du
from scanpath_studio import progress, updates

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


def _asset(data: bytes, *, url=None, digest=None):
    return updates.Asset(
        "ScanpathStudio-linux-x86_64.tar.gz",
        url or f"{du.REPO_DOWNLOADS}v99.0.0/ScanpathStudio-linux-x86_64.tar.gz",
        len(data),
        digest if digest is not None else "sha256:" + hashlib.sha256(data).hexdigest(),
    )


def _serving(data: bytes):
    seen = []

    def opener(request, timeout):
        seen.append(request.full_url)
        return io.BytesIO(data)

    opener.seen = seen
    return opener


def test_download_checks_the_digest(tmp_path):
    data = b"x" * (3 * du.CHUNK + 5)
    path = du.download(_asset(data), tmp_path, opener=_serving(data))
    assert path.read_bytes() == data
    assert not list(tmp_path.glob("*.part"))


def test_a_download_that_does_not_match_is_thrown_away(tmp_path):
    data = b"payload"
    with pytest.raises(du.UpdateFailed, match="doesn't match"):
        du.download(
            _asset(data, digest="sha256:" + "0" * 64), tmp_path, opener=_serving(data)
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("digest", ["", "md5:abc", "sha256:"])
def test_a_download_without_a_sha256_is_refused(tmp_path, digest):
    with pytest.raises(du.UpdateFailed, match="checksum"):
        du.download(_asset(b"x", digest=digest), tmp_path, opener=_serving(b"x"))


def test_only_the_projects_own_releases_are_fetched(tmp_path):
    opener = _serving(b"x")
    with pytest.raises(du.UpdateFailed, match="own releases"):
        du.download(
            _asset(b"x", url="https://evil.test/a.tar.gz"), tmp_path, opener=opener
        )
    with pytest.raises(du.UpdateFailed, match="own releases"):
        du.download(_asset(b"x", url="file:///etc/passwd"), tmp_path, opener=opener)
    assert opener.seen == []


def test_the_feed_may_serve_a_local_file(tmp_path):
    source = tmp_path / "src.tar.gz"
    source.write_bytes(b"local")
    asset = _asset(b"local", url=source.as_uri())
    path = du.download(asset, tmp_path / "dl", allow_file=True)
    assert path.read_bytes() == b"local"


def test_a_dropped_download_is_an_update_failure(tmp_path):
    def opener(request, timeout):
        raise OSError("connection reset")

    with pytest.raises(du.UpdateFailed, match="stopped"):
        du.download(_asset(b"x"), tmp_path, opener=opener)
    assert not list(tmp_path.glob("*.part"))


def test_a_cancelled_download_leaves_nothing(tmp_path):
    data = b"x" * (2 * du.CHUNK)
    with progress.task(("test", "update"), title="Updating") as task:
        task.cancel()
        with pytest.raises(progress.Cancelled):
            du.download(_asset(data), tmp_path, opener=_serving(data))
    assert not list(tmp_path.iterdir())


def _zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def _tar(path, members):
    with tarfile.open(path, "w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(data))
    return path


def test_stage_unpacks_the_windows_zip(tmp_path):
    install = _install(tmp_path / "i", "win32")
    archive = _zip(
        tmp_path / "a.zip",
        {"ScanpathStudio/ScanpathStudio.exe": b"v2", "ScanpathStudio/_internal/x": b""},
    )
    root = du.stage(archive, tmp_path / "state", install)
    assert root == tmp_path / "state" / "staged" / "ScanpathStudio"
    assert (root / "ScanpathStudio.exe").read_bytes() == b"v2"


def test_stage_unpacks_the_linux_tarball_keeping_the_executable_bit(tmp_path):
    install = _install(tmp_path / "i", "linux")
    archive = _tar(
        tmp_path / "a.tar.gz",
        {"ScanpathStudio/ScanpathStudio": b"v2", "ScanpathStudio/_internal/x": b""},
    )
    root = du.stage(archive, tmp_path / "state", install)
    assert (root / "ScanpathStudio").stat().st_mode & 0o100


def test_a_tarball_reaching_outside_is_refused(tmp_path):
    install = _install(tmp_path / "i", "linux")
    archive = _tar(tmp_path / "a.tar.gz", {"../evil": b"x"})
    with pytest.raises(du.UpdateFailed, match="unpacked"):
        du.stage(archive, tmp_path / "state", install)


def test_an_archive_without_the_app_is_refused(tmp_path):
    install = _install(tmp_path / "i", "win32")
    archive = _zip(tmp_path / "a.zip", {"something/else.txt": b""})
    with pytest.raises(du.UpdateFailed, match="doesn't contain"):
        du.stage(archive, tmp_path / "state", install)


class _FakeMac:
    """`subprocess.run` for the macOS staging tools, over real temp folders."""

    def __init__(self, *, staged_team="T1", running_team="T1", spctl=0):
        self.calls = []
        self.teams = {"staged": staged_team, "running": running_team}
        self.spctl = spctl

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        tool = argv[0]
        if argv[:2] == ["hdiutil", "attach"]:
            mount = Path(argv[argv.index("-mountpoint") + 1])
            exe = mount / "ScanpathStudio.app" / "Contents" / "MacOS" / "ScanpathStudio"
            exe.parent.mkdir(parents=True)
            exe.write_text("v2")
        elif tool == "ditto":
            shutil.copytree(argv[1], argv[2])
        elif argv[:2] == ["codesign", "-dv"]:
            which = "staged" if "staged" in argv[-1] else "running"
            team = self.teams[which]
            line = f"TeamIdentifier={team}" if team else "TeamIdentifier=not set"
            return subprocess.CompletedProcess(argv, 0, "", line + "\n")
        elif tool == "spctl":
            return subprocess.CompletedProcess(argv, self.spctl, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def ran(self, *prefix):
        return any(call[: len(prefix)] == list(prefix) for call in self.calls)


def test_stage_copies_the_app_out_of_the_dmg_and_checks_it(tmp_path):
    install = _install(tmp_path / "i", "darwin")
    fake = _FakeMac()
    root = du.stage(tmp_path / "a.dmg", tmp_path / "state", install, run=fake)
    assert root == tmp_path / "state" / "staged" / "ScanpathStudio.app"
    assert (root / "Contents" / "MacOS" / "ScanpathStudio").read_text() == "v2"
    assert fake.ran("codesign", "--verify", "--deep", "--strict")
    assert fake.ran("spctl", "--assess", "--type", "exec")
    assert fake.ran("hdiutil", "detach")


@pytest.mark.parametrize(
    ("fake", "says"),
    [
        (lambda: _FakeMac(staged_team="OTHER"), "same developers"),
        (lambda: _FakeMac(spctl=3), "Gatekeeper"),
    ],
)
def test_a_dmg_app_from_elsewhere_is_refused(tmp_path, fake, says):
    install = _install(tmp_path / "i", "darwin")
    fake = fake()
    with pytest.raises(du.UpdateFailed, match=says):
        du.stage(tmp_path / "a.dmg", tmp_path / "state", install, run=fake)
    assert fake.ran("hdiutil", "detach")


def test_self_test_runs_the_staged_selfcheck_in_a_fresh_environment(tmp_path):
    seen = {}

    def run(argv, **kwargs):
        seen["argv"], seen["env"] = argv, kwargs["env"]
        return subprocess.CompletedProcess(argv, 0, "selfcheck ok", "")

    du.self_test(tmp_path / "ScanpathStudio", "linux", run=run)
    assert seen["argv"] == [
        str(tmp_path / "ScanpathStudio" / "ScanpathStudio"),
        "--selfcheck",
    ]
    assert seen["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert seen["env"]["SCANPATH_DESKTOP_NO_LOG_FILE"] == "1"


def test_a_failed_self_test_refuses_the_update(tmp_path):
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "boom")

    with pytest.raises(du.UpdateFailed, match="self-test"):
        du.self_test(tmp_path, "linux", run=run)
