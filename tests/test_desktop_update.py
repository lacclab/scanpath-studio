"""The desktop app's own updater (#385)."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
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


def _tool(argv):
    """``argv`` with its program by name: the updater runs tools by absolute path."""
    return [os.path.basename(argv[0]), *argv[1:]]


def _codesign(team):
    """A fake `subprocess.run` answering `codesign -dv` with `team`."""

    def run(argv, **kwargs):
        if _tool(argv)[:2] == ["codesign", "-dv"]:
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
        named = _tool(argv)
        tool = named[0]
        if named[:2] == ["hdiutil", "attach"]:
            mount = Path(argv[argv.index("-mountpoint") + 1])
            exe = mount / "ScanpathStudio.app" / "Contents" / "MacOS" / "ScanpathStudio"
            exe.parent.mkdir(parents=True)
            exe.write_text("v2")
        elif tool == "ditto":
            shutil.copytree(argv[1], argv[2])
        elif named[:2] == ["codesign", "-dv"]:
            which = "staged" if "staged" in argv[-1] else "running"
            team = self.teams[which]
            line = f"TeamIdentifier={team}" if team else "TeamIdentifier=not set"
            return subprocess.CompletedProcess(argv, 0, "", line + "\n")
        elif tool == "spctl":
            return subprocess.CompletedProcess(argv, self.spctl, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def ran(self, *prefix):
        return any(_tool(call)[: len(prefix)] == list(prefix) for call in self.calls)


def test_stage_copies_the_app_out_of_the_dmg_and_checks_it(tmp_path):
    install = _install(tmp_path / "i", "darwin")
    fake = _FakeMac()
    root = du.stage(tmp_path / "a.dmg", tmp_path / "state", install, run=fake)
    assert root == tmp_path / "state" / "staged" / "ScanpathStudio.app"
    assert (root / "Contents" / "MacOS" / "ScanpathStudio").read_text() == "v2"
    assert fake.ran("codesign", "--verify", "--deep", "--strict")
    assert fake.ran("spctl", "--assess", "--type", "exec")
    assert fake.ran("hdiutil", "detach")
    # by absolute path, so nothing earlier on PATH stands in for a tool
    assert all(os.path.isabs(call[0]) for call in fake.calls), fake.calls


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


FAKE_APP = """
import os, sys, time
from pathlib import Path
state, mode = Path(sys.argv[1]), sys.argv[2]
with open(state / "launches", "a") as log:
    log.write(f"{os.getpid()}\\n")
if mode != "silent":
    (state / "started").write_text(str(os.getpid()))
if mode == "boot":
    (state / "booted").write_text("")
else:
    time.sleep(30)
"""


def _dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _swap_fixture(tmp_path, system, mode, boot_timeout_s=30.0, skip_staged=None):
    """An installed v1, a staged v2, and a plan whose relaunch is the fake app."""
    install = _install(tmp_path / "i", system)
    for entry in install.payload:
        path = install.root / entry
        if entry == "_internal":
            (path / "old.txt").write_text("v1")
    state = tmp_path / "state"
    staged = state / "staged" / "ScanpathStudio"
    for entry in install.payload:
        if entry == skip_staged:
            staged.mkdir(parents=True, exist_ok=True)
        elif entry == "_internal":
            (staged / entry).mkdir(parents=True)
            (staged / entry / "new.txt").write_text("v2")
        else:
            staged.mkdir(parents=True, exist_ok=True)
            (staged / entry).write_text("v2")
    fake = tmp_path / "fake_app.py"
    fake.write_text(FAKE_APP)
    plan = du.SwapPlan(
        pid=_dead_pid(),
        install=install,
        staged=staged,
        state=state,
        version="99.0.0",
        previous="0.36.0",
        relaunch=(sys.executable, str(fake), str(state), mode),
        boot_timeout_s=boot_timeout_s,
        quit_timeout_s=5.0,
    )
    du._write_json(state / du.PENDING, {"root": str(install.root), "at": time.time()})
    return plan


def _kill_launched(state):
    for line in (
        (state / "launches").read_text().split()
        if (state / "launches").exists()
        else []
    ):
        try:
            os.kill(int(line), 9)
        except OSError:
            pass


def _wait_for(path, seconds=20.0):
    deadline = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)


def _run_helper(plan, argv):
    script = plan.state / (
        "helper.ps1" if plan.install.system == "win32" else "helper.sh"
    )
    script.write_text(
        du.helper_script(plan),
        encoding="utf-8-sig" if plan.install.system == "win32" else "utf-8",
    )
    return subprocess.run([*argv, str(script)], timeout=120, check=False)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_swaps_relaunches_and_cleans_up(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    try:
        done = _run_helper(plan, ["/bin/sh"])
        assert done.returncode == 0
        root = plan.install.root
        assert (root / "ScanpathStudio").read_text() == "v2"
        assert (root / "_internal" / "new.txt").exists()
        result = du.last_result(state=plan.state)
        assert result.status == "updated" and result.version == "99.0.0"
        assert result.pid is not None
        for leftover in (
            "old",
            "failed",
            "staged",
            du.PENDING,
            du.STARTED,
            du.BOOTED,
            du.HELPER_STARTED,
        ):
            assert not (plan.state / leftover).exists(), leftover
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_rolls_back_when_the_new_version_never_boots(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "hang", boot_timeout_s=2.0)
    try:
        done = _run_helper(plan, ["/bin/sh"])
        assert done.returncode == 1
        root = plan.install.root
        assert (root / "ScanpathStudio").read_text() == "v1"
        assert (root / "_internal" / "old.txt").exists()
        result = du.last_result(state=plan.state)
        assert result.status == "rolled_back"
        assert "did not start" in result.reason
        # the old version was relaunched after the rollback
        _wait_for(plan.state / "started")
        assert len((plan.state / "launches").read_text().split()) == 2
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_puts_the_old_version_back_when_the_swap_fails(tmp_path):
    # The staged copy lacks `_internal`, so moving the new version in fails.
    plan = _swap_fixture(tmp_path, "linux", "boot", skip_staged="_internal")
    try:
        done = _run_helper(plan, ["/bin/sh"])
        assert done.returncode == 1
        root = plan.install.root
        assert (root / "ScanpathStudio").read_text() == "v1"
        assert (root / "_internal" / "old.txt").exists()
        result = du.last_result(state=plan.state)
        assert result.status == "failed"
        assert "moved into place" in result.reason
        assert "could not be put back" not in result.reason
        # nothing waits on this attempt any more, and the old app is running again
        assert not (plan.state / du.PENDING).exists()
        _wait_for(plan.state / "launches")
        assert len((plan.state / "launches").read_text().split()) == 1
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_stops_a_new_version_that_never_wrote_started(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "silent", boot_timeout_s=2.0)
    try:
        done = _run_helper(plan, ["/bin/sh"])
        assert done.returncode == 1
        assert (plan.install.root / "ScanpathStudio").read_text() == "v1"
        assert du.last_result(state=plan.state).status == "rolled_back"
        first = int((plan.state / "launches").read_text().split()[0])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                os.kill(first, 0)
            except OSError:
                break
            time.sleep(0.1)
        with pytest.raises(OSError):
            os.kill(first, 0)
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_never_nests_into_an_existing_entry(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    # something already sits where the old `_internal` would be moved aside to
    (plan.state / "old").mkdir()
    done = subprocess.run(
        [
            "/bin/sh",
            "-c",
            'ENTRIES="_internal"; ' + _move_all_source() + ' move_all "$1" "$2"',
            "sh",
            str(plan.install.root),
            str(plan.state / "old"),
        ],
        check=False,
    )
    assert done.returncode == 0  # an empty destination moves fine
    assert (plan.state / "old" / "_internal" / "old.txt").exists()
    # now the destination holds one already: a failure, and nothing nested
    (plan.install.root / "_internal").mkdir()
    (plan.install.root / "_internal" / "again.txt").write_text("x")
    done = subprocess.run(
        [
            "/bin/sh",
            "-c",
            'ENTRIES="_internal"; ' + _move_all_source() + ' move_all "$1" "$2"',
            "sh",
            str(plan.install.root),
            str(plan.state / "old"),
        ],
        check=False,
    )
    assert done.returncode == 1
    assert not (plan.state / "old" / "_internal" / "_internal").exists()
    assert (plan.install.root / "_internal" / "again.txt").exists()


def _move_all_source():
    """The helper's own `move_all` function, lifted out of the template."""
    text = du._SH_HELPER
    start = text.index("move_all() {")
    return text[start : text.index("\n}\n", start) + 3]


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_puts_the_old_version_back_when_the_swap_fails(tmp_path):
    plan = _swap_fixture(tmp_path, "win32", "boot", skip_staged="_internal")
    try:
        done = _run_helper(plan, ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        assert done.returncode == 1
        assert (plan.install.root / "ScanpathStudio.exe").read_text() == "v1"
        assert du.last_result(state=plan.state).status == "failed"
        assert not (plan.state / du.PENDING).exists()
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_swaps_relaunches_and_cleans_up(tmp_path):
    plan = _swap_fixture(tmp_path, "win32", "boot")
    try:
        done = _run_helper(plan, ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        assert done.returncode == 0
        assert (plan.install.root / "ScanpathStudio.exe").read_text() == "v2"
        assert du.last_result(state=plan.state).status == "updated"
        assert not (plan.state / "old").exists()
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_rolls_back(tmp_path):
    plan = _swap_fixture(tmp_path, "win32", "hang", boot_timeout_s=2.0)
    try:
        done = _run_helper(plan, ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        assert done.returncode == 1
        assert (plan.install.root / "ScanpathStudio.exe").read_text() == "v1"
        assert du.last_result(state=plan.state).status == "rolled_back"
    finally:
        _kill_launched(plan.state)


def test_the_sh_helper_quotes_awkward_paths(tmp_path):
    plan = _swap_fixture(tmp_path / "it's a dir", "linux", "boot")
    script = tmp_path / "helper.sh"
    script.write_text(du.helper_script(plan))
    if shutil.which("sh"):
        assert subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0
    assert "'\"'\"'" in script.read_text()  # shlex.quote's escape of the '


def test_the_powershell_helper_quotes_awkward_paths(tmp_path):
    plan = _swap_fixture(tmp_path / "it's a dir", "win32", "boot")
    text = du.helper_script(plan)
    assert "it''s a dir" in text
    assert du.UNINSTALL_KEY in text


def test_a_plan_that_cannot_make_a_script_leaves_no_attempt(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    (plan.state / du.PENDING).unlink()
    bad = du.SwapPlan(**{**plan.__dict__, "version": '1"; rm -rf /'})
    started = []
    with pytest.raises(du.UpdateFailed):
        du.start_swap(bad, popen=lambda *a, **k: started.append(a))
    assert not (plan.state / du.PENDING).exists()
    assert not started


def test_windows_runs_the_helper_as_an_encoded_command(tmp_path):
    script = tmp_path / "helper.ps1"
    text = "Write-Output 'caf\u00e9'\n"
    script.write_text(text, encoding="utf-8-sig")
    argv = du.helper_command(script, "win32")
    # Windows PowerShell by absolute path, never whatever PATH finds first
    assert argv[0].endswith("powershell.exe")
    assert "System32" in argv[0] and "WindowsPowerShell" in argv[0]
    assert "-File" not in argv and "-ExecutionPolicy" not in argv
    assert argv[-2] == "-EncodedCommand"
    decoded = base64.b64decode(argv[-1]).decode("utf-16-le")
    assert decoded == text and not decoded.startswith("\ufeff")


def test_helper_versions_must_be_plain(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    bad = du.SwapPlan(**{**plan.__dict__, "version": '1"; rm -rf /'})
    with pytest.raises(ValueError):
        du.helper_script(bad)


def test_relaunch_command_per_os(tmp_path):
    mac = du.install_at(
        Path("/Applications/ScanpathStudio.app/Contents/MacOS/ScanpathStudio"), "darwin"
    )
    env = {"SCANPATH_DESKTOP_NO_BROWSER": "1", "UNRELATED": "x"}
    assert du.relaunch_command(mac, env) == (
        "/usr/bin/open",
        "-n",
        "--env",
        "SCANPATH_DESKTOP_NO_BROWSER=1",
        "/Applications/ScanpathStudio.app",
    )
    linux = du.install_at(Path("/opt/ScanpathStudio/ScanpathStudio"), "linux")
    assert du.relaunch_command(linux, env) == ("/opt/ScanpathStudio/ScanpathStudio",)


def test_start_swap_records_the_attempt_and_detaches(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    (plan.state / du.PENDING).unlink()
    seen = {}

    def popen(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        (plan.state / du.HELPER_STARTED).write_text("")  # the helper's first act
        return _FakeHelper()

    du.start_swap(plan, popen=popen)
    assert du._read_json(plan.state / du.PENDING)["root"] == str(plan.install.root)
    assert seen["argv"] == ["/bin/sh", str(plan.state / "helper.sh")]
    assert seen["kwargs"]["start_new_session"] is True
    assert seen["kwargs"]["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_a_helper_that_cannot_start_leaves_no_attempt(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")

    def popen(argv, **kwargs):
        raise OSError("no sh")

    with pytest.raises(du.UpdateFailed):
        du.start_swap(plan, popen=popen)
    assert not (plan.state / du.PENDING).exists()


def test_the_relaunched_app_reports_in_for_its_own_install(tmp_path):
    install = _install(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    du._write_json(state / du.PENDING, {"root": str(install.root), "at": time.time()})
    du.note_start(install, state=state, pid=4242)
    assert (state / "started").read_text() == "4242"
    du.note_boot(install, state=state)
    assert (state / "booted").exists()


def test_another_installs_attempt_is_left_alone(tmp_path):
    install = _install(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    du._write_json(state / du.PENDING, {"root": "/somewhere/else", "at": time.time()})
    du.note_start(install, state=state, pid=1)
    du.note_boot(install, state=state)
    assert not (state / "started").exists() and not (state / "booted").exists()


def test_an_abandoned_attempt_is_cleared_at_boot(tmp_path):
    install = _install(tmp_path)
    state = tmp_path / "state"
    (state / "staged").mkdir(parents=True)
    (state / "download").mkdir()
    old = time.time() - du.STALE_AFTER_S - 10
    os.utime(state / "staged", (old, old))
    os.utime(state / "download", (old, old))
    du._write_json(
        state / "result.json", {"status": "failed", "version": "1", "previous": "0"}
    )
    du.note_boot(install, state=state)
    assert not (state / "staged").exists() and not (state / "download").exists()
    assert (state / "result.json").exists()


def test_a_recent_attempt_is_not_cleared(tmp_path):
    install = _install(tmp_path)
    state = tmp_path / "state"
    (state / "staged").mkdir(parents=True)
    du.note_boot(install, state=state)
    assert (state / "staged").exists()


def test_the_boot_hooks_never_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(du, "state_dir", lambda install: 1 / 0)
    install = _install(tmp_path)
    du.note_start(install)
    du.note_boot(install)
    assert du.last_result(install) is None


def test_clear_attempt_keeps_only_the_log(tmp_path):
    state = tmp_path / "state"
    for folder in ("download", "staged", "old", "failed"):
        (state / folder).mkdir(parents=True)
    for name in (du.PENDING, *du._ATTEMPT_FILES, "helper.log"):
        (state / name).write_text("x")
    du.clear_attempt(state)
    assert sorted(path.name for path in state.iterdir()) == ["helper.log"]


def test_prepare_downloads_stages_tests_and_plans_the_swap(tmp_path, cache_home):
    install = _install(tmp_path, "linux")
    archive = _tar(
        tmp_path / "a.tar.gz",
        {"ScanpathStudio/ScanpathStudio": b"v2", "ScanpathStudio/_internal/x": b""},
    )
    data = archive.read_bytes()
    check = _check(digest="sha256:" + hashlib.sha256(data).hexdigest(), size=len(data))
    steps = []

    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "selfcheck ok", "")

    plan = du.prepare(
        check,
        install,
        run=run,
        opener=_serving(data),
        machine="x86_64",
        on_step=steps.append,
    )
    assert steps == list(du.STEPS)
    assert plan.staged == du.state_dir(install) / "staged" / "ScanpathStudio"
    assert plan.version == "99.0.0" and plan.previous == "0.36.0"
    assert plan.relaunch == (str(install.executable),)
    assert plan.pid == os.getpid()


def test_prepare_refuses_before_downloading(tmp_path, cache_home):
    install = _install(tmp_path, "linux")
    opener = _serving(b"")
    with pytest.raises(du.UpdateFailed, match="checksum"):
        du.prepare(_check(digest=""), install, opener=opener, machine="x86_64")
    assert opener.seen == []


def test_ci_runs_the_end_to_end_update_on_every_os():
    workflow = (ROOT / ".github/workflows/desktop.yml").read_text(encoding="utf-8")
    assert workflow.count("desktop/update_e2e.py") == 3


def test_the_e2e_driver_is_stdlib_plus_the_package():
    source = (ROOT / "desktop/update_e2e.py").read_text(encoding="utf-8")
    assert "from scanpath_studio import desktop_update" in source
    assert "import streamlit" not in source


# --- final review fixes ------------------------------------------------------


class _FakeHelper:
    """What `popen` returns for the helper: still running unless ``exits``."""

    def __init__(self, *, exits=False):
        self.exits = exits
        self.killed = False

    def poll(self):
        return 1 if self.exits else None

    def kill(self):
        self.killed = True


def test_a_helper_that_never_reports_in_leaves_no_attempt(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    (plan.state / du.PENDING).unlink()
    # a marker left by an earlier attempt must not pass for this helper's
    (plan.state / du.HELPER_STARTED).write_text("")
    helper = _FakeHelper()
    with pytest.raises(du.UpdateFailed, match="didn't start, so nothing was changed"):
        du.start_swap(plan, popen=lambda *a, **k: helper, handshake_timeout_s=0.3)
    assert helper.killed
    assert not (plan.state / du.PENDING).exists()


def test_a_helper_that_exits_at_once_is_not_waited_for(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    helper = _FakeHelper(exits=True)
    began = time.monotonic()
    with pytest.raises(du.UpdateFailed, match="didn't start"):
        du.start_swap(plan, popen=lambda *a, **k: helper, handshake_timeout_s=30)
    assert time.monotonic() - began < 5
    assert not (plan.state / du.PENDING).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_start_swap_returns_once_the_real_helper_has_started(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    (plan.state / du.PENDING).unlink()
    try:
        du.start_swap(plan)  # the real Popen and the real template
        assert (plan.state / du.HELPER_STARTED).exists() or (
            plan.state / du.RESULT
        ).exists()
        _wait_for(plan.state / du.RESULT)
        assert du.last_result(state=plan.state).status == "updated"
    finally:
        _wait_for(plan.state / "launches")
        _kill_launched(plan.state)


def test_the_update_marker_contract_is_pinned(tmp_path, cache_home):
    # An old version's helper waits on what the new version's launcher
    # writes: none of these may change without a migration.
    assert du.PENDING == "pending.json"
    assert (du.STARTED, du.BOOTED, du.RESULT, du.HELPER_STARTED) == (
        "started",
        "booted",
        "result.json",
        "helper-started",
    )
    for name in (du.STARTED, du.BOOTED, du.RESULT, du.HELPER_STARTED):
        assert f'"$STATE/{name}' in du._SH_HELPER, name
        assert f"'{name}'" in du._PS_HELPER, name
    for template in (du._SH_HELPER, du._PS_HELPER):
        assert "@@PENDING@@" in template
    # pending.json's keys
    plan = _swap_fixture(tmp_path, "linux", "boot")

    def popen(argv, **kwargs):
        (plan.state / du.HELPER_STARTED).write_text("")
        return _FakeHelper()

    du.start_swap(plan, popen=popen)
    pending = du._read_json(plan.state / du.PENDING)
    assert set(pending) == {"root", "version", "previous", "at"}
    assert pending["root"] == str(plan.install.root)
    # result.json's keys, as both helpers write them
    for key in ("status", "version", "previous", "reason", "pid"):
        assert f'"{key}": ' in du._SH_HELPER, key
        assert f"{key} = $" in du._PS_HELPER, key
    # the per-user state folders, and the fallback beside the install
    env = {
        "HOME": "/h",
        "LOCALAPPDATA": "C:/L",
        "XDG_CACHE_HOME": "/x",
    }
    assert du._user_state_dir("darwin", env) == Path(
        "/h/Library/Caches/Scanpath Studio/update"
    )
    assert du._user_state_dir("win32", env) == Path("C:/L/Scanpath Studio/update")
    assert du._user_state_dir("linux", env) == Path("/x/scanpath-studio/update")
    install = _install(tmp_path / "other")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(du, "_device", lambda path: 1 if "cache" in str(path) else 2)
        assert du.state_dir(install) == install.root.parent / ".ScanpathStudio-update"


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(13, "Permission denied", "/state/staged"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_prepare_turns_any_os_or_value_error_into_an_update_failure(
    tmp_path, cache_home, monkeypatch, error
):
    install = _install(tmp_path, "linux")
    data = b"archive"
    check = _check(digest="sha256:" + hashlib.sha256(data).hexdigest(), size=len(data))

    def stage(*args, **kwargs):
        raise error

    monkeypatch.setattr(du, "stage", stage)
    with pytest.raises(du.UpdateFailed, match="^Preparing the update failed: .+\\.$"):
        du.prepare(check, install, opener=_serving(data), machine="x86_64")
    assert (install.root / "ScanpathStudio").read_text() == "v1"


def test_a_cancelled_prepare_is_still_a_cancel(tmp_path, cache_home):
    install = _install(tmp_path, "linux")
    data = b"archive"
    check = _check(digest="sha256:" + hashlib.sha256(data).hexdigest(), size=len(data))
    with progress.task(("test", "prepare"), title="Updating") as task:
        task.cancel()
        with pytest.raises(progress.Cancelled):
            du.prepare(check, install, opener=_serving(data), machine="x86_64")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sh helper")
def test_the_sh_helper_forgets_the_attempt_when_the_app_does_not_quit(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    app = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        stuck = du.SwapPlan(**{**plan.__dict__, "pid": app.pid, "quit_timeout_s": 1.0})
        done = _run_helper(stuck, ["/bin/sh"])
        assert done.returncode == 1
        result = du.last_result(state=plan.state)
        assert result.status == "failed" and result.reason == "the app did not quit"
        assert not (plan.state / du.PENDING).exists()
        # the old version is still running: nothing was relaunched or swapped
        assert not (plan.state / "launches").exists()
        assert (plan.install.root / "ScanpathStudio").read_text() == "v1"
    finally:
        app.kill()
        app.wait()


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_forgets_the_attempt_when_the_app_does_not_quit(
    tmp_path,
):
    plan = _swap_fixture(tmp_path, "win32", "boot")
    app = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        stuck = du.SwapPlan(**{**plan.__dict__, "pid": app.pid, "quit_timeout_s": 1.0})
        done = _run_helper(stuck, ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        assert done.returncode == 1
        assert du.last_result(state=plan.state).reason == "the app did not quit"
        assert not (plan.state / du.PENDING).exists()
        assert not (plan.state / "launches").exists()
    finally:
        app.kill()
        app.wait()


def test_an_attempt_dated_in_the_future_is_stale(tmp_path, cache_home):
    install = _install(tmp_path)
    state = du.state_dir(install)
    state.mkdir(parents=True)
    du._write_json(
        state / du.PENDING,
        {"root": str(install.root), "at": time.time() + du.STALE_AFTER_S + 60},
    )
    assert du.refusal(_check(), install, machine="x86_64") is None


@pytest.mark.parametrize("system", ["linux", "win32"])
def test_a_value_that_looks_like_a_placeholder_is_left_alone(tmp_path, system):
    plan = _swap_fixture(tmp_path / "x@@STATE@@y", system, "boot")
    text = du.helper_script(plan)
    quote = du._ps_quote if system == "win32" else (lambda v: shlex.quote(str(v)))
    paths = (plan.install.root, plan.state, plan.staged, *plan.relaunch)
    values = [quote(value) for value in paths]
    for value in sorted(set(values), key=len, reverse=True):  # staged under state
        assert value in text
        text = text.replace(value, "")
    assert "@@" not in text


def test_the_powershell_helper_doubles_every_kind_of_single_quote(tmp_path):
    quotes = "'\u2018\u2019\u201a\u201b"
    assert du._ps_quote("a" + quotes + "b") == (
        "'a" + "".join(quote * 2 for quote in quotes) + "b'"
    )
    plan = _swap_fixture(tmp_path / "it\u2019s a dir", "win32", "boot")
    text = du.helper_script(plan)
    assert "it\u2019\u2019s a dir" in text
    assert "it\u2019s a dir" not in text


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_runs_under_a_typographic_quote(tmp_path):
    plan = _swap_fixture(tmp_path / "it\u2019s a dir", "win32", "boot")
    try:
        done = _run_helper(plan, ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        assert done.returncode == 0
        assert (plan.install.root / "ScanpathStudio.exe").read_text() == "v2"
        assert du.last_result(state=plan.state).status == "updated"
    finally:
        _kill_launched(plan.state)


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="needs PowerShell")
def test_the_powershell_helper_never_nests_into_an_existing_entry(tmp_path):
    source = du._PS_HELPER
    start = source.index("function Move-All(")
    function = source[start : source.index("\n}\n", start) + 3]
    script = tmp_path / "move_all.ps1"
    script.write_text(
        "param($From, $To)\n$Entries = @('_internal')\n"
        + function
        + "if (Move-All $From $To) { exit 0 } else { exit 1 }\n",
        encoding="utf-8-sig",
    )
    source_dir, target = tmp_path / "from", tmp_path / "to"
    (source_dir / "_internal").mkdir(parents=True)
    (source_dir / "_internal" / "new.txt").write_text("x")
    (target / "_internal").mkdir(parents=True)  # already there
    done = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)]
        + [str(source_dir), str(target)],
        timeout=60,
        check=False,
    )
    assert done.returncode == 1
    assert not (target / "_internal" / "_internal").exists()
    assert (source_dir / "_internal" / "new.txt").exists()


def test_the_sh_helper_never_kills_the_pid_of_macos_open(tmp_path):
    plan = _swap_fixture(tmp_path, "linux", "boot")
    mac = du.SwapPlan(
        **{**plan.__dict__, "relaunch": ("/usr/bin/open", "-n", "/A.app")}
    )
    assert "\nTRACK_LAUNCH=0\n" in du.helper_script(mac)
    assert "\nTRACK_LAUNCH=1\n" in du.helper_script(plan)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks")
def test_a_relaunch_through_a_symlinked_root_still_reports_in(tmp_path):
    real = _install(tmp_path / "real")
    link = tmp_path / "link"
    link.symlink_to(real.root, target_is_directory=True)
    via_link = du.install_at(link / "ScanpathStudio", "linux")
    assert via_link.root != real.root
    state = tmp_path / "state"
    state.mkdir()
    # recorded by the real path, relaunched through the link — and the reverse
    for recorded, running in ((real, via_link), (via_link, real)):
        du.clear_attempt(state)
        du._write_json(
            state / du.PENDING, {"root": str(recorded.root), "at": time.time()}
        )
        du.note_start(running, state=state, pid=7)
        assert (state / du.STARTED).read_text() == "7"


def test_the_boot_timeout_outlasts_the_relaunched_launchers_own_wait():
    from desktop import launcher

    assert du.BOOT_TIMEOUT_S > launcher.HEALTH_TIMEOUT_S
