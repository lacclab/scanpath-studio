# #385 — One-click *Update & restart* in the desktop app: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the desktop app, About → *Check for updates* → **Update & restart** downloads the new release, verifies it, tests it, swaps it in with a detached helper, relaunches it, and rolls back if it never starts. `ScanpathStudio --update` does the same headlessly. CI proves the swap end to end on all three OSes.

**Architecture:** A new Streamlit-free module, `scanpath_studio/desktop_update.py` (stdlib + `packaging`), owns the whole flow:
- `refusal` decides whether this install can update itself.
- `download`, `stage` and `self_test` produce a verified copy beside the install.
- `start_swap` writes a POSIX `sh` or PowerShell helper and starts it detached. After the app quits, the helper swaps the *payload entries* inside the install (macOS `Contents`; elsewhere the executable plus `_internal`) and relaunches.
- `note_start` / `note_boot` are the relaunched launcher's report-ins.

The About dialog and `desktop/launcher.py` are thin callers. `desktop/update_e2e.py` plus a `desktop.yml` step exercise the real bundles.

**Tech Stack:** Python 3.11+ stdlib (`hashlib`, `zipfile`, `tarfile`, `subprocess`, `urllib`), `packaging`, POSIX `sh`, Windows PowerShell 5.1, macOS `hdiutil` / `ditto` / `codesign` / `spctl` / `open`, Streamlit (About dialog only), PyInstaller 6.22.3, GitHub Actions.

**Spec:** [`plans/139-build-versions-and-updates.md`](139-build-versions-and-updates.md) → *Section 3* (the design the user approved on 2026-10-07), as amended by the rulings below, which this plan's first commit also writes into Section 3.

## Rulings against the design (made while planning)

1. **Swap the payload entries, not the whole folder, on Windows and Linux too.** The design said to swap the `ScanpathStudio` folder. Since then, #388's Inno Setup installer puts `unins000.exe` / `unins000.dat` in that folder, and a whole-folder swap would delete them. So every OS swaps the entries inside the install root:
   - macOS: `Contents` (as designed).
   - Windows: `ScanpathStudio.exe` and `_internal`.
   - Linux: `ScanpathStudio` and `_internal`.

   The installer already lists `{app}\_internal` under `[UninstallDelete]`, so an updated install still uninstalls cleanly. On Windows, the helper also updates the uninstall entry's `DisplayVersion` (HKCU, AppId `{6F1C9A52-3B7E-4D21-9C8A-5E2F4B7D1A93}`), best effort.
2. **The updater downloads the Windows `.zip`, not the `-setup.exe`.** `updates.DESKTOP_ARCHIVES` keeps pointing *Download* at the installer. `desktop_update.UPDATE_ARCHIVES` maps Windows to `ScanpathStudio-windows-x86_64.zip`, as the #139 ruling anticipated.
3. **The state folder holds everything.** The download, the staged copy, the moved-aside old payload, the markers and the result all live in one folder on the install's volume, so every move is a rename:
   - preferred: the per-user cache (`~/Library/Caches/Scanpath Studio/update`, `%LOCALAPPDATA%\Scanpath Studio\update`, `$XDG_CACHE_HOME/scanpath-studio/update`);
   - if that is on another volume: `.ScanpathStudio-update` beside the install;
   - if neither works, the update is refused.
4. **The new launcher reports in by install, not by version.** It writes `started` (its PID) at launch and `booted` once its server answers, but only if the folder's `pending.json` names *its* install root. Matching on the root means CI can offer the same build under a fake version.
5. **Child processes get a clean environment** (`child_env`): `PYINSTALLER_RESET_ENVIRONMENT=1` and the original `LD_LIBRARY_PATH`. Without them, the staged copy's `--selfcheck` and the relaunch would inherit this bundle's PyInstaller state.
6. **A macOS build without a Developer ID team is refused** (ad-hoc or unsigned forks), because the Team-ID check is the trust anchor there.
7. **The outcome survives the restart.** The helper writes `result.json` (`updated` / `rolled_back` / `failed`). About then shows a warning when the last attempt didn't go through, or "Updated from v…" when it did.
8. **`SCANPATH_UPDATE_FEED`** (a local JSON file in GitHub's release shape) is honoured only by `--update`, and only it may use `file:` download URLs. Everything else must come from `https://github.com/lacclab/scanpath-studio/releases/download/`.

## Global Constraints

- Never downgrades and never installs a pre-release: update only when `check_for_updates(...).status == "update_available"` (strictly newer) and the latest version is not a pre-release.
- Downloads come only from the hard-coded repo's release URLs (`https://github.com/lacclab/scanpath-studio/releases/download/`). The sha256 must equal the asset's `digest` (`"sha256:<hex>"`); a missing digest refuses.
- Any failure before the helper starts leaves the install untouched and raises `UpdateFailed`, whose `str()` is a plain sentence for people.
- `desktop_update.py` imports no Streamlit. The launcher imports it lazily, inside functions: `desktop/launcher.py` must stay stdlib-only at import time, because `smoke_test.py` imports it.
- `note_start` / `note_boot` never raise and never block launching.
- The PowerShell helper must run on **Windows PowerShell 5.1**: no `??`, no `&&` / `||` between commands, no `$IsWindows`. Write it as UTF-8 **with** BOM (`encoding="utf-8-sig"`), or 5.1 misreads non-ASCII paths.
- Network only on an explicit click / `--update` (the `docs/privacy.md` promise).
- Toolchain:
  - tests: `uv run --extra test --extra lint pytest …`;
  - lint: `uv run --extra lint ruff check .` and `uv run --extra lint ruff format .`;
  - docs: `uv run --extra docs mkdocs build --strict`.

  Bare `python3` / `pytest` / `ruff` are the wrong toolchain.
- Commits:
  - one per task, subject ending `(#385)`;
  - **no `Co-Authored-By` trailer** (the user's rule overrides any default);
  - never edit `uv.lock`;
  - don't push.
- No network in tests. Don't start the app or a server. Never run `scanpath-studio cache --clear` / `api.clear_cache`.
- `from __future__ import annotations` at the top of every Python file; ruff-clean; match the surrounding comment density and plain-English docstrings.
- When appended test code opens with imports, merge them into the file's import block at the top (ruff's isort and E402 enforce it); don't repeat an import that is already there.

## File map

| File | Responsibility |
|---|---|
| `scanpath_studio/desktop_update.py` (new) | The whole updater: install model, refusals, download + digest, staging + macOS signature checks, self-test, swap plan + helper scripts, boot markers, result. |
| `desktop/launcher.py` | `--update` flag; `note_start` at launch; `note_boot` once healthy. |
| `scanpath_studio/app.py` | About: **Update & restart** / *Download instead*, the loading card, the restart message, the last-update notice. |
| `desktop/update_e2e.py` (new) | CI driver: feed → `--update` → wait for `result.json` → assert the swap. |
| `.github/workflows/desktop.yml` | One *End-to-end update* step per OS. |
| `tests/test_desktop_update.py` (new) | Unit tests, including running the real `sh` / `pwsh` helpers on temp folders. |
| `tests/test_desktop_bundle.py` | Launcher `--update` and boot-hook tests. |
| `tests/test_updates.py` | About AppTests for the new button. |
| Docs | `docs/getting-started.md` *Updating*, `docs/privacy.md` *Network activity*, `desktop/README.md`, `AGENTS.md`, `scanpath_studio/CLAUDE.md`, `changelog.d/385.added.md`, `plans/139-build-versions-and-updates.md` Section 3. |

---

### Task 1: The install model and refusals

**Files:**
- Create: `scanpath_studio/desktop_update.py`
- Test: `tests/test_desktop_update.py`

**Interfaces:**
- Consumes (from #139, already on this branch): `updates.Asset`, `updates.Release`, `updates.UpdateCheck`, `updates.UpdateCheckError`, `updates._release_from(payload)`, `updates.REPO`.
- Produces:
  - `APP_NAME = "ScanpathStudio"`, `UPDATE_ARCHIVES`, `update_archive(system=None, machine=None) -> str | None`
  - `Install(root: Path, payload: tuple[str, ...], executable: Path, system: str)` (frozen dataclass), `install_at(executable: Path, system: str | None = None) -> Install | None`, `current_install() -> Install | None`, `executable_in(root: Path, system: str) -> Path`
  - `state_dir(install: Install, *, env: Mapping[str, str] | None = None) -> Path`
  - `asset_for(check: UpdateCheck, install: Install, *, machine: str | None = None) -> Asset | None`
  - `class UpdateFailed(Exception)`
  - `refusal(check, install, *, state=None, run=subprocess.run, machine=None) -> str | None`
  - `team_id(app: Path, *, run=subprocess.run) -> str | None`
  - `child_env(base: Mapping[str, str] | None = None) -> dict[str, str]`
  - `feed_release(path: Path) -> Release`, `FEED_ENV = "SCANPATH_UPDATE_FEED"`
  - private helpers later tasks use: `_run(run, argv, failure, *, timeout=600, env=None) -> str`, `_read_json(path) -> dict | None`, `_write_json(path, data) -> None`, `_device(path) -> int | None`
  - constants: `REPO_DOWNLOADS`, `DISK_FACTOR = 3`, `STALE_AFTER_S = 3600`, `PENDING = "pending.json"`

- [ ] **Step 1: Write the failing tests** in `tests/test_desktop_update.py`:

```python
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
```

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: collection error, `cannot import name 'desktop_update'`.

- [ ] **Step 3: Write `scanpath_studio/desktop_update.py`:**

```python
"""One-click *Update & restart* for the desktop app (#385).

Only the frozen bundle can replace itself, so this belongs to the desktop app
alone: Help → About → *Check for updates* → **Update & restart**, or
``ScanpathStudio --update`` headless. The design is Section 3 of
``plans/139-build-versions-and-updates.md``:

1. :func:`refusal` — can this install update itself at all?
2. :func:`download` the release's archive and check its sha256 against the
   ``digest`` GitHub publishes for it.
3. :func:`stage` it on the install's own volume, so the swap is a rename; on
   macOS require the running app's Developer ID team and Gatekeeper's yes.
4. :func:`self_test` the staged copy with the launcher's ``--selfcheck``.
5. :func:`start_swap` — a detached helper waits for this process to exit,
   swaps the payload, relaunches, and puts the old version back if the new
   one never reports in (:func:`note_start`, :func:`note_boot`).

Everything before step 5 leaves the install untouched. Stdlib and
``packaging`` only, no Streamlit: the launcher calls it with no server running.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

from . import updates
from .updates import Asset, Release, UpdateCheck, UpdateCheckError

APP_NAME = "ScanpathStudio"
#: Where every update must come from; the test-only feed may use ``file:``.
REPO_DOWNLOADS = f"https://github.com/{updates.REPO}/releases/download/"
#: A local JSON file in GitHub's release shape that ``--update`` reads instead
#: of the API — what the CI end-to-end run offers the fresh build through.
FEED_ENV = "SCANPATH_UPDATE_FEED"
#: Free space wanted on the state folder's volume: the download, the staged
#: copy, and room to move the old version aside.
DISK_FACTOR = 3
#: An attempt this old with no helper behind it is abandoned.
STALE_AFTER_S = 3600
PENDING = "pending.json"

#: The archive the updater installs per (platform, machine) — the names
#: ``.github/workflows/desktop.yml`` gives them. Windows takes the ``.zip``,
#: not the installer *Download* offers: the updater swaps files itself.
UPDATE_ARCHIVES = {
    ("darwin", "arm64"): "ScanpathStudio-macos-arm64.dmg",
    ("win32", "amd64"): "ScanpathStudio-windows-x86_64.zip",
    ("win32", "x86_64"): "ScanpathStudio-windows-x86_64.zip",
    ("linux", "x86_64"): "ScanpathStudio-linux-x86_64.tar.gz",
}


class UpdateFailed(Exception):
    """An update that could not go ahead; ``str()`` says why, for people.

    Raised only before the swap begins, so the install is always untouched.
    """


@dataclass(frozen=True)
class Install:
    """Where the running desktop app lives, and what an update replaces.

    ``root`` is the ``.app`` on macOS and the folder holding the executable
    elsewhere. ``payload`` is what an update swaps inside it: ``Contents`` on
    macOS (the user owns the ``.app`` they dragged in, even on a standard
    account), else the executable and ``_internal`` — so the Windows
    installer's ``unins000.*`` beside them survive an update.
    """

    root: Path
    payload: tuple[str, ...]
    executable: Path
    system: str


def _system(system: str | None) -> str:
    system = sys.platform if system is None else system
    return "linux" if system.startswith("linux") else system


def update_archive(system: str | None = None, machine: str | None = None) -> str | None:
    """The archive name the updater installs on this computer, or ``None``."""
    machine = (platform.machine() if machine is None else machine).lower()
    return UPDATE_ARCHIVES.get((_system(system), machine))


def executable_in(root: Path, system: str) -> Path:
    """The launcher executable inside a bundle rooted at ``root``."""
    if system == "darwin":
        return root / "Contents" / "MacOS" / APP_NAME
    return root / (f"{APP_NAME}.exe" if system == "win32" else APP_NAME)


def install_at(executable: Path, system: str | None = None) -> Install | None:
    """The install whose launcher is ``executable`` — ``None`` if it isn't one."""
    system = _system(system)
    executable = Path(executable)
    if system == "darwin":
        contents = executable.parent.parent
        app = contents.parent
        if (
            executable.name != APP_NAME
            or executable.parent.name != "MacOS"
            or contents.name != "Contents"
            or app.suffix != ".app"
        ):
            return None
        return Install(app, ("Contents",), executable, system)
    if executable != executable_in(executable.parent, system):
        return None
    return Install(
        executable.parent, (executable.name, "_internal"), executable, system
    )


def current_install() -> Install | None:
    """The running bundle's install, or ``None`` outside the frozen app."""
    if not getattr(sys, "frozen", False):
        return None
    return install_at(Path(os.path.abspath(sys.executable)))


def _user_state_dir(system: str, env: Mapping[str, str]) -> Path:
    home = Path(env["HOME"]) if env.get("HOME") else Path.home()
    if system == "darwin":
        return home / "Library" / "Caches" / "Scanpath Studio" / "update"
    if system == "win32":
        base = (
            Path(env["LOCALAPPDATA"])
            if env.get("LOCALAPPDATA")
            else (home / "AppData" / "Local")
        )
        return base / "Scanpath Studio" / "update"
    base = (
        Path(env["XDG_CACHE_HOME"]) if env.get("XDG_CACHE_HOME") else (home / ".cache")
    )
    return base / "scanpath-studio" / "update"


def _device(path: Path) -> int | None:
    """The volume ``path`` is on — read from its nearest existing ancestor."""
    for candidate in (path, *path.parents):
        try:
            return candidate.stat().st_dev
        except OSError:
            continue
    return None


def state_dir(install: Install, *, env: Mapping[str, str] | None = None) -> Path:
    """The folder an update stages in, swaps through and leaves its markers in.

    On the install's own volume, so every move is a rename: the per-user cache
    folder when it shares the volume, else a hidden folder beside the install.
    The relaunched launcher calls this too, so it must stay deterministic.
    """
    env = os.environ if env is None else env
    user = _user_state_dir(install.system, env)
    if _device(user) == _device(install.root):
        return user
    return install.root.parent / f".{APP_NAME}-update"


def asset_for(
    check: UpdateCheck, install: Install, *, machine: str | None = None
) -> Asset | None:
    """The release file the updater would install here, if the release has it."""
    name = update_archive(install.system, machine)
    if check.latest is None or name is None:
        return None
    return check.latest.asset(name)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict) -> None:
    """Write atomically: a reader sees the old file or the new, never half."""
    partial = path.with_name(path.name + ".tmp")
    partial.write_text(json.dumps(data), encoding="utf-8")
    os.replace(partial, path)


def _run(
    run: Callable,
    argv: list[str],
    failure: str,
    *,
    timeout: float = 600,
    env: Mapping[str, str] | None = None,
) -> str:
    """Run one tool; any failure becomes :class:`UpdateFailed` with ``failure``."""
    try:
        result = run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise UpdateFailed(failure) from error
    if result.returncode != 0:
        raise UpdateFailed(failure)
    return (result.stdout or "") + (result.stderr or "")


def team_id(app: Path, *, run: Callable = subprocess.run) -> str | None:
    """The Developer ID team that signed ``app`` — ``None`` if ad-hoc or unsigned."""
    try:
        result = run(
            ["codesign", "-dv", "--verbose=2", str(app)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    found = re.search(
        r"^TeamIdentifier=(\S+)$",
        (result.stdout or "") + (result.stderr or ""),
        re.MULTILINE,
    )
    if result.returncode != 0 or found is None or found.group(1) == "not":
        return None  # "TeamIdentifier=not set": ad-hoc
    return found.group(1)


def _pending(state: Path) -> dict | None:
    """The attempt under way in ``state``, unless it is stale."""
    pending = _read_json(state / PENDING)
    if pending is None:
        return None
    try:
        started = float(pending.get("at") or 0)
    except (TypeError, ValueError):
        return None
    if time.time() - started > STALE_AFTER_S:
        return None
    return pending


def refusal(
    check: UpdateCheck,
    install: Install | None,
    *,
    state: Path | None = None,
    run: Callable = subprocess.run,
    machine: str | None = None,
) -> str | None:
    """Why this app can't update itself to ``check.latest`` — ``None`` if it can.

    Cheap enough for every render of About: no download, and on macOS one
    ``codesign`` call.
    """
    if install is None:
        return "Only the desktop app can update itself."
    if check.status != "update_available" or check.latest is None:
        return "There is no newer release to update to."
    try:
        prerelease = Version(check.latest.version).is_prerelease
    except InvalidVersion:
        return f"{check.latest.tag} isn't a version this app can install."
    if prerelease:
        return f"v{check.latest.version} is a pre-release; it is never installed automatically."
    asset = asset_for(check, install, machine=machine)
    if asset is None:
        if update_archive(install.system, machine) is None:
            return "There is no desktop build for this computer."
        return (
            "This release has no update for this computer yet; desktop builds "
            "are uploaded up to an hour after a release."
        )
    if not asset.digest.startswith("sha256:"):
        return (
            "This release's download has no checksum to verify it against, so "
            "it can't be installed automatically."
        )
    if "/AppTranslocation/" in install.root.as_posix():
        return (
            "macOS is running Scanpath Studio from a temporary copy. Move it to "
            "Applications, open it from there, and try again."
        )
    if not os.access(install.root, os.W_OK):
        return (
            f"This account can't change {install.root}; whoever installed "
            "Scanpath Studio has to update it."
        )
    state = state_dir(install) if state is None else state
    nowhere = (
        f"There's nowhere on this disk beside {install.root} to prepare the update."
    )
    try:
        state.mkdir(parents=True, exist_ok=True)
    except OSError:
        return nowhere
    if not os.access(state, os.W_OK) or _device(state) != _device(install.root):
        return nowhere
    if _pending(state) is not None:
        return "An update is already under way."
    free = shutil.disk_usage(state).free
    if asset.size and free < DISK_FACTOR * asset.size:
        return (
            f"Updating needs about {DISK_FACTOR * asset.size / 1e6:,.0f} MB free; "
            f"this disk has {free / 1e6:,.0f} MB."
        )
    if install.system == "darwin" and team_id(install.root, run=run) is None:
        return (
            "This copy of Scanpath Studio isn't signed by its developers, so an "
            "update can't be checked against it."
        )
    return None


def child_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment for another bundle this one starts.

    PyInstaller's bootloader leaves its own state in the environment (and, on
    Linux, points ``LD_LIBRARY_PATH`` into this bundle). The staged copy and
    the relaunched app must start as fresh top-level apps:
    ``PYINSTALLER_RESET_ENVIRONMENT`` tells their bootloader so, and the
    library path the user had is put back.
    """
    env = dict(os.environ if base is None else base)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    meipass = getattr(sys, "_MEIPASS", None)
    if original is not None:
        env["LD_LIBRARY_PATH"] = original
    elif meipass and env.get("LD_LIBRARY_PATH", "").startswith(meipass):
        del env["LD_LIBRARY_PATH"]
    return env


def feed_release(path: Path) -> Release:
    """A release read from a local JSON file in GitHub's shape (``FEED_ENV``)."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise UpdateCheckError(f"The update feed {path} couldn't be read.") from error
    return updates._release_from(payload)
```

- [ ] **Step 4: Run the tests; they pass.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: all pass. If `test_each_refusal_says_why`'s `"free"` case meets a disk with more than a petabyte free, raise `size`.

- [ ] **Step 5: Lint and commit.**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/desktop_update.py tests/test_desktop_update.py
git commit -m "Desktop updater: the install model and refusals (#385)"
```

---

### Task 2: Download, digest, staging and the self-test

**Files:**
- Modify: `scanpath_studio/desktop_update.py` (append)
- Test: `tests/test_desktop_update.py` (append)

**Interfaces:**
- Consumes: Task 1's `Install`, `UpdateFailed`, `REPO_DOWNLOADS`, `_run`, `team_id`, `child_env`, `executable_in`, `APP_NAME`; `updates._urlopen(request, timeout)` (certifi TLS); `progress.report(done, total, unit="bytes")` and `progress.Cancelled`.
- Produces:
  - `download(asset: Asset, folder: Path, *, allow_file: bool = False, opener: Callable | None = None, timeout: float = 30.0) -> Path`
  - `stage(archive: Path, state: Path, install: Install, *, run: Callable = subprocess.run) -> Path` — the staged root: `<state>/staged/ScanpathStudio.app`, or `<state>/staged/ScanpathStudio`
  - `verify_signature(staged_app: Path, running_app: Path, *, run=subprocess.run) -> None`
  - `self_test(staged_root: Path, system: str, *, run=subprocess.run) -> None`
  - `SELFCHECK_TIMEOUT_S = 300`, `CHUNK = 1 << 20`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_desktop_update.py`):

```python
import hashlib
import io
import tarfile
import zipfile

from scanpath_studio import progress


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
```

Add `import shutil` to the test file's imports.

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: `AttributeError: module 'scanpath_studio.desktop_update' has no attribute 'download'` (and likewise for `stage` and the rest).

- [ ] **Step 3: Implement** (append to `desktop_update.py`; add `hashlib`, `http.client`, `tarfile`, `urllib.request` and `zipfile` to the imports, and `from . import progress`):

```python
CHUNK = 1 << 20
#: The staged copy's ``--selfcheck``. Windows' first scan of a fresh bundle
#: can take minutes, like the smoke test's budget.
SELFCHECK_TIMEOUT_S = 300


def _allowed(url: str, *, allow_file: bool) -> bool:
    return url.startswith(REPO_DOWNLOADS) or (allow_file and url.startswith("file:"))


def download(
    asset: Asset,
    folder: Path,
    *,
    allow_file: bool = False,
    opener: Callable | None = None,
    timeout: float = 30.0,
) -> Path:
    """Fetch ``asset`` into ``folder`` and check it against its sha256 digest.

    Reports bytes to the active progress task, whose cancel checkpoint this
    loop therefore is. A partial or mismatched file is deleted, never kept.
    """
    if not _allowed(asset.url, allow_file=allow_file):
        raise UpdateFailed(
            "The download isn't from Scanpath Studio's own releases, so it was "
            "not fetched."
        )
    algorithm, _, expected = asset.digest.partition(":")
    if algorithm != "sha256" or not expected:
        raise UpdateFailed(
            "This release's download has no checksum to verify it against, so "
            "it can't be installed automatically."
        )
    from .build_info import build_info

    opener = updates._urlopen if opener is None else opener
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / asset.name
    partial = target.with_name(target.name + ".part")
    request = urllib.request.Request(
        asset.url, headers={"User-Agent": f"scanpath-studio/{build_info().version}"}
    )
    digest = hashlib.sha256()
    done = 0
    finished = False
    try:
        progress.report(0, asset.size or None, unit="bytes")
        with opener(request, timeout=timeout) as response, open(partial, "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                progress.report(done, asset.size or None, unit="bytes")
        finished = True
    except (OSError, http.client.HTTPException) as error:
        raise UpdateFailed(
            "The download stopped before it finished; are you offline?"
        ) from error
    finally:
        if not finished:
            partial.unlink(missing_ok=True)
    if digest.hexdigest() != expected.lower():
        partial.unlink(missing_ok=True)
        raise UpdateFailed(
            "The download doesn't match the checksum GitHub published for it, "
            "so it was thrown away."
        )
    os.replace(partial, target)
    return target


def _stage_dmg(dmg: Path, target: Path, *, run: Callable) -> Path:
    """Copy the ``.app`` out of the disk image, read-only and unseen by Finder."""
    mount = target / "mount"
    mount.mkdir()
    _run(
        run,
        [
            "hdiutil",
            "attach",
            "-nobrowse",
            "-readonly",
            "-mountpoint",
            str(mount),
            str(dmg),
        ],
        "The downloaded disk image couldn't be opened.",
    )
    app = target / f"{APP_NAME}.app"
    try:
        if not (mount / f"{APP_NAME}.app").is_dir():
            raise UpdateFailed(
                "The download doesn't contain Scanpath Studio where it should."
            )
        _run(
            run,
            ["ditto", str(mount / f"{APP_NAME}.app"), str(app)],
            "The new version couldn't be copied out of the disk image.",
        )
    finally:
        try:
            run(
                ["hdiutil", "detach", str(mount), "-force"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    return app


def verify_signature(
    staged_app: Path, running_app: Path, *, run: Callable = subprocess.run
) -> None:
    """The staged ``.app`` must be intact, from this app's team, and pass Gatekeeper."""
    _run(
        run,
        ["codesign", "--verify", "--deep", "--strict", str(staged_app)],
        "The new version's signature is broken, so it was not installed.",
    )
    expected = team_id(running_app, run=run)
    if expected is None or team_id(staged_app, run=run) != expected:
        raise UpdateFailed(
            "The new version isn't signed by the same developers as this one, so "
            "it was not installed."
        )
    _run(
        run,
        ["spctl", "--assess", "--type", "exec", str(staged_app)],
        "macOS's Gatekeeper rejected the new version, so it was not installed.",
    )


def stage(
    archive: Path, state: Path, install: Install, *, run: Callable = subprocess.run
) -> Path:
    """Unpack ``archive`` into ``<state>/staged``; return the new copy's root."""
    target = state / "staged"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    try:
        if install.system == "darwin":
            root = _stage_dmg(archive, target, run=run)
            verify_signature(root, install.root, run=run)
        elif install.system == "win32":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(target)
            root = target / APP_NAME
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(target, filter="data")
            root = target / APP_NAME
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as error:
        raise UpdateFailed("The download couldn't be unpacked.") from error
    if not executable_in(root, install.system).is_file():
        raise UpdateFailed(
            "The download doesn't contain Scanpath Studio where it should."
        )
    return root


def self_test(
    staged_root: Path, system: str, *, run: Callable = subprocess.run
) -> None:
    """Run the staged copy's ``--selfcheck``: it must load and draw before it replaces this one."""
    env = child_env()
    env["SCANPATH_DESKTOP_NO_LOG_FILE"] = "1"
    _run(
        run,
        [str(executable_in(staged_root, system)), "--selfcheck"],
        "The new version failed its self-test, so it was not installed.",
        timeout=SELFCHECK_TIMEOUT_S,
        env=env,
    )
```

Note: `stage` catches `OSError` around the unpacking, but `UpdateFailed` raised inside `_stage_dmg` / `verify_signature` is not an `OSError`, so it passes through unchanged.

- [ ] **Step 4: Run the tests; they pass.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: all pass.

- [ ] **Step 5: Lint and commit.**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/desktop_update.py tests/test_desktop_update.py
git commit -m "Desktop updater: download, digest, staging and self-test (#385)"
```

---

### Task 3: The swap helpers, boot markers and the result

**Files:**
- Modify: `scanpath_studio/desktop_update.py` (append)
- Test: `tests/test_desktop_update.py` (append)

**Interfaces:**
- Consumes: Task 1's `Install`, `state_dir`, `_read_json`, `_write_json`, `_pending`, `PENDING`, `STALE_AFTER_S`, `child_env`, `UpdateFailed`, `current_install`.
- Produces:
  - `SwapPlan(pid: int, install: Install, staged: Path, state: Path, version: str, previous: str, relaunch: tuple[str, ...], boot_timeout_s: float = BOOT_TIMEOUT_S, quit_timeout_s: float = QUIT_TIMEOUT_S)` (frozen dataclass)
  - `relaunch_command(install: Install, env: Mapping[str, str] | None = None) -> tuple[str, ...]`
  - `helper_script(plan: SwapPlan) -> str`
  - `helper_command(script: Path, system: str) -> list[str]`
  - `start_swap(plan: SwapPlan, *, popen: Callable = subprocess.Popen) -> None`
  - `clear_attempt(state: Path) -> None`
  - `note_start(install: Install | None = None, *, state: Path | None = None, pid: int | None = None) -> None`
  - `note_boot(install: Install | None = None, *, state: Path | None = None) -> None`
  - `UpdateResult(status: str, version: str, previous: str, reason: str = "", pid: int | None = None)`
  - `last_result(install: Install | None = None, *, state: Path | None = None) -> UpdateResult | None`
  - `exit_soon(delay: float = RESTART_DELAY_S) -> None`
  - constants: `BOOT_TIMEOUT_S = 180`, `QUIT_TIMEOUT_S = 60`, `RESTART_DELAY_S = 2.0`, `FORWARDED_ENV`, `UNINSTALL_KEY`

- [ ] **Step 1: Write the failing tests** (append). The two `run_*_helper` tests *execute* the real scripts on temp folders, with a fake app standing in for the relaunch:

```python
import os
import sys
import time

FAKE_APP = """
import os, sys, time
from pathlib import Path
state, mode = Path(sys.argv[1]), sys.argv[2]
with open(state / "launches", "a") as log:
    log.write(f"{os.getpid()}\\n")
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


def _swap_fixture(tmp_path, system, mode, boot_timeout_s=30.0):
    """An installed v1, a staged v2, and a plan whose relaunch is the fake app."""
    install = _install(tmp_path / "i", system)
    for entry in install.payload:
        path = install.root / entry
        if entry == "_internal":
            (path / "old.txt").write_text("v1")
    state = tmp_path / "state"
    staged = state / "staged" / "ScanpathStudio"
    for entry in install.payload:
        if entry == "_internal":
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
        for leftover in ("old", "failed", "staged", du.PENDING, "started", "booted"):
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
        "open",
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
    for name in (du.PENDING, "started", "booted", "result.json", "helper.log"):
        (state / name).write_text("x")
    du.clear_attempt(state)
    assert sorted(path.name for path in state.iterdir()) == ["helper.log"]
```

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: `AttributeError: ... has no attribute 'SwapPlan'`.

- [ ] **Step 3: Implement** (append; add `math`, `shlex` and `threading` to the imports):

```python
#: How long the relaunched version has to answer before the old one is put
#: back — Windows' first-launch scan of a new bundle can take that long.
BOOT_TIMEOUT_S = 180
#: How long the helper waits for this process to exit before giving up.
QUIT_TIMEOUT_S = 60
#: Between "Restarting into vX" and the exit, so the message reaches the browser.
RESTART_DELAY_S = 2.0
#: Launch settings the relaunched app keeps; ``open -n`` starts it with a
#: fresh environment, so on macOS they are passed on explicitly.
FORWARDED_ENV = (
    "SCANPATH_DESKTOP_PORT",
    "SCANPATH_DESKTOP_NO_BROWSER",
    "SCANPATH_DESKTOP_BROWSER",
    "SCANPATH_DESKTOP_NO_LOG_FILE",
    "SCANPATH_DESKTOP_IDLE_EXIT_S",
)
#: The Windows installer's uninstall entry (desktop/windows_installer.iss's
#: AppId), whose DisplayVersion the helper brings up to date.
UNINSTALL_KEY = (
    "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
    "{6F1C9A52-3B7E-4D21-9C8A-5E2F4B7D1A93}_is1"
)
#: What one attempt leaves in the state folder; ``helper.log`` stays for a bug report.
_ATTEMPT_FOLDERS = ("download", "staged", "old", "failed")
_ATTEMPT_FILES = (PENDING, "started", "booted", "result.json")


@dataclass(frozen=True)
class SwapPlan:
    """Everything the helper needs: whom to wait for, what to swap, how to relaunch."""

    pid: int
    install: Install
    staged: Path
    state: Path
    version: str
    previous: str
    relaunch: tuple[str, ...]
    boot_timeout_s: float = BOOT_TIMEOUT_S
    quit_timeout_s: float = QUIT_TIMEOUT_S


@dataclass(frozen=True)
class UpdateResult:
    """How the last update ended: ``updated``, ``rolled_back`` or ``failed``."""

    status: str
    version: str
    previous: str
    reason: str = ""
    pid: int | None = None


def relaunch_command(
    install: Install, env: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """How the helper starts the app again: through Launch Services on macOS."""
    if install.system != "darwin":
        return (str(install.executable),)
    env = os.environ if env is None else env
    forwarded = [
        item
        for name in FORWARDED_ENV
        if name in env
        for item in ("--env", f"{name}={env[name]}")
    ]
    return ("open", "-n", *forwarded, str(install.root))


_SH_HELPER = r"""#!/bin/sh
# Scanpath Studio's update helper (#385), written by desktop_update.helper_script.
# Waits for the app to quit, swaps the new version in, relaunches it, and puts
# the old version back if the new one never reports in.
APP_PID=@@PID@@
ROOT=@@ROOT@@
STATE=@@STATE@@
NEW=@@NEW@@
ENTRIES=@@ENTRIES@@
QUIT_TICKS=@@QUIT_TICKS@@
BOOT_TICKS=@@BOOT_TICKS@@
BOOT_TIMEOUT=@@BOOT_TIMEOUT@@
VERSION=@@VERSION@@
PREVIOUS=@@PREVIOUS@@

result() {
  printf '{"status": "%s", "version": "%s", "previous": "%s", "reason": "%s", "pid": %s}\n' \
    "$1" "$VERSION" "$PREVIOUS" "$2" "${3:-null}" > "$STATE/result.json.tmp" &&
    mv -f "$STATE/result.json.tmp" "$STATE/result.json"
}

relaunch() {
  nohup @@RELAUNCH@@ >/dev/null 2>&1 &
}

# Move every entry from $1 to $2; on a failure put back what moved.
move_all() {
  moved=""
  for entry in $ENTRIES; do
    if mv "$1/$entry" "$2/$entry"; then
      moved="$moved $entry"
    else
      for back in $moved; do mv "$2/$back" "$1/$back"; done
      return 1
    fi
  done
}

ticks=0
while kill -0 "$APP_PID" 2>/dev/null; do
  if [ "$ticks" -ge "$QUIT_TICKS" ]; then
    result failed "the app did not quit"
    exit 1
  fi
  sleep 0.5
  ticks=$((ticks + 1))
done

rm -rf "$STATE/old" "$STATE/failed"
rm -f "$STATE/started" "$STATE/booted"
if ! mkdir "$STATE/old" "$STATE/failed"; then
  result failed "the update folder could not be prepared"
  relaunch
  exit 1
fi
if ! move_all "$ROOT" "$STATE/old"; then
  result failed "the old version could not be moved aside"
  relaunch
  exit 1
fi
if ! move_all "$NEW" "$ROOT"; then
  move_all "$STATE/old" "$ROOT"
  result failed "the new version could not be moved into place"
  relaunch
  exit 1
fi
touch "$ROOT"
relaunch

ticks=0
while [ ! -e "$STATE/booted" ]; do
  if [ "$ticks" -ge "$BOOT_TICKS" ]; then
    new_pid=$(cat "$STATE/started" 2>/dev/null)
    if [ -n "$new_pid" ]; then
      kill "$new_pid" 2>/dev/null
      sleep 2
      kill -9 "$new_pid" 2>/dev/null
    fi
    rm -f "$STATE/@@PENDING@@" "$STATE/started"
    if move_all "$ROOT" "$STATE/failed" && move_all "$STATE/old" "$ROOT"; then
      result rolled_back "the new version did not start within $BOOT_TIMEOUT seconds"
    else
      result failed "the new version did not start, and the old one could not be put back"
    fi
    touch "$ROOT"
    relaunch
    rm -rf "$STATE/failed" "$STATE/staged" "$STATE/download"
    exit 1
  fi
  sleep 0.5
  ticks=$((ticks + 1))
done

new_pid=$(cat "$STATE/started" 2>/dev/null)
result updated "" "${new_pid:-null}"
rm -rf "$STATE/old" "$STATE/failed" "$STATE/staged" "$STATE/download"
rm -f "$STATE/@@PENDING@@" "$STATE/started" "$STATE/booted"
"""

_PS_HELPER = r"""# Scanpath Studio's update helper (#385), written by desktop_update.helper_script.
# Waits for the app to quit, swaps the new version in, relaunches it, and puts
# the old version back if the new one never reports in. Windows PowerShell 5.1.
$AppPid = @@PID@@
$Root = @@ROOT@@
$State = @@STATE@@
$New = @@NEW@@
$Entries = @(@@ENTRIES@@)
$QuitTimeoutMs = @@QUIT_MS@@
$BootTicks = @@BOOT_TICKS@@
$BootTimeout = @@BOOT_TIMEOUT@@
$Version = @@VERSION@@
$Previous = @@PREVIOUS@@
$Relaunch = @(@@RELAUNCH@@)
$UninstallKey = @@UNINSTALL_KEY@@
$Pending = @@PENDING@@

function Write-Result($Status, $Reason, $NewPid) {
  $record = [ordered]@{ status = $Status; version = $Version; previous = $Previous; reason = $Reason; pid = $NewPid }
  $tmp = Join-Path $State 'result.json.tmp'
  [IO.File]::WriteAllText($tmp, ($record | ConvertTo-Json -Compress))
  Move-Item -LiteralPath $tmp -Destination (Join-Path $State 'result.json') -Force
}

function Start-App {
  $rest = @($Relaunch | Select-Object -Skip 1 | ForEach-Object { '"' + $_ + '"' })
  if ($rest.Count) {
    Start-Process -FilePath $Relaunch[0] -ArgumentList $rest -WorkingDirectory $Root
  } else {
    Start-Process -FilePath $Relaunch[0] -WorkingDirectory $Root
  }
}

# Move every entry from $From to $To, retrying while antivirus holds a file;
# on a failure put back what moved.
function Move-All($From, $To) {
  $moved = @()
  foreach ($entry in $Entries) {
    $done = $false
    for ($try = 0; $try -lt 60 -and -not $done; $try++) {
      try {
        Move-Item -LiteralPath (Join-Path $From $entry) -Destination (Join-Path $To $entry) -ErrorAction Stop
        $done = $true
      } catch {
        Start-Sleep -Milliseconds 500
      }
    }
    if (-not $done) {
      foreach ($back in $moved) {
        Move-Item -LiteralPath (Join-Path $To $back) -Destination (Join-Path $From $back) -ErrorAction SilentlyContinue
      }
      return $false
    }
    $moved += $entry
  }
  return $true
}

function Read-NewPid {
  $file = Join-Path $State 'started'
  if (Test-Path -LiteralPath $file) { return [int](Get-Content -LiteralPath $file -Raw).Trim() }
  return $null
}

$app = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
if ($app -and -not $app.WaitForExit($QuitTimeoutMs)) {
  Write-Result 'failed' 'the app did not quit' $null
  exit 1
}

foreach ($name in 'old', 'failed') {
  $path = Join-Path $State $name
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
  New-Item -ItemType Directory -Path $path | Out-Null
}
foreach ($name in 'started', 'booted') {
  Remove-Item -LiteralPath (Join-Path $State $name) -Force -ErrorAction SilentlyContinue
}
if (-not (Move-All $Root (Join-Path $State 'old'))) {
  Write-Result 'failed' 'the old version could not be moved aside' $null
  Start-App
  exit 1
}
if (-not (Move-All $New $Root)) {
  Move-All (Join-Path $State 'old') $Root | Out-Null
  Write-Result 'failed' 'the new version could not be moved into place' $null
  Start-App
  exit 1
}
Start-App

$ticks = 0
while (-not (Test-Path -LiteralPath (Join-Path $State 'booted'))) {
  if ($ticks -ge $BootTicks) {
    $newPid = Read-NewPid
    if ($newPid) {
      Stop-Process -Id $newPid -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 2
    }
    Remove-Item -LiteralPath (Join-Path $State $Pending), (Join-Path $State 'started') -Force -ErrorAction SilentlyContinue
    if ((Move-All $Root (Join-Path $State 'failed')) -and (Move-All (Join-Path $State 'old') $Root)) {
      Write-Result 'rolled_back' "the new version did not start within $BootTimeout seconds" $null
    } else {
      Write-Result 'failed' 'the new version did not start, and the old one could not be put back' $null
    }
    Start-App
    foreach ($name in 'failed', 'staged', 'download') {
      Remove-Item -LiteralPath (Join-Path $State $name) -Recurse -Force -ErrorAction SilentlyContinue
    }
    exit 1
  }
  Start-Sleep -Milliseconds 500
  $ticks++
}

Write-Result 'updated' '' (Read-NewPid)
if ($env:OS -eq 'Windows_NT' -and (Test-Path -LiteralPath $UninstallKey)) {
  try {
    $location = (Get-ItemProperty -LiteralPath $UninstallKey).InstallLocation
    if ($location -and $location.TrimEnd('\') -eq $Root.TrimEnd('\')) {
      Set-ItemProperty -LiteralPath $UninstallKey -Name DisplayVersion -Value $Version
    }
  } catch { }
}
foreach ($name in 'old', 'failed', 'staged', 'download', $Pending, 'started', 'booted') {
  Remove-Item -LiteralPath (Join-Path $State $name) -Recurse -Force -ErrorAction SilentlyContinue
}
"""

_PLAIN_VERSION = re.compile(r"[0-9A-Za-z.+!_-]+")


def _ps_quote(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def helper_script(plan: SwapPlan) -> str:
    """The helper for ``plan``: PowerShell on Windows, POSIX ``sh`` elsewhere.

    Values are substituted quoted for their shell. The two versions also
    land inside the result JSON unescaped, so they must be plain version
    strings.
    """
    for version in (plan.version, plan.previous):
        if not _PLAIN_VERSION.fullmatch(version):
            raise ValueError(f"not a plain version: {version!r}")
    boot_ticks = math.ceil(plan.boot_timeout_s * 2)
    if plan.install.system == "win32":
        values = {
            "PID": str(plan.pid),
            "ROOT": _ps_quote(plan.install.root),
            "STATE": _ps_quote(plan.state),
            "NEW": _ps_quote(plan.staged),
            "ENTRIES": ", ".join(_ps_quote(entry) for entry in plan.install.payload),
            "QUIT_MS": str(math.ceil(plan.quit_timeout_s * 1000)),
            "BOOT_TICKS": str(boot_ticks),
            "BOOT_TIMEOUT": str(math.ceil(plan.boot_timeout_s)),
            "VERSION": _ps_quote(plan.version),
            "PREVIOUS": _ps_quote(plan.previous),
            "RELAUNCH": ", ".join(_ps_quote(arg) for arg in plan.relaunch),
            "UNINSTALL_KEY": _ps_quote(UNINSTALL_KEY),
            "PENDING": _ps_quote(PENDING),
        }
        template = _PS_HELPER
    else:
        values = {
            "PID": str(plan.pid),
            "ROOT": shlex.quote(str(plan.install.root)),
            "STATE": shlex.quote(str(plan.state)),
            "NEW": shlex.quote(str(plan.staged)),
            "ENTRIES": shlex.quote(" ".join(plan.install.payload)),
            "QUIT_TICKS": str(math.ceil(plan.quit_timeout_s * 2)),
            "BOOT_TICKS": str(boot_ticks),
            "BOOT_TIMEOUT": str(math.ceil(plan.boot_timeout_s)),
            "VERSION": shlex.quote(plan.version),
            "PREVIOUS": shlex.quote(plan.previous),
            "RELAUNCH": " ".join(shlex.quote(arg) for arg in plan.relaunch),
            "PENDING": PENDING,
        }
        template = _SH_HELPER
    for name, value in values.items():
        template = template.replace(f"@@{name}@@", value)
    return template


def helper_command(script: Path, system: str) -> list[str]:
    """How to run the helper script on ``system``."""
    if system == "win32":
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ]
    return ["/bin/sh", str(script)]


def start_swap(plan: SwapPlan, *, popen: Callable = subprocess.Popen) -> None:
    """Record the attempt and start the helper, detached; the caller then exits.

    The helper's output goes to ``helper.log`` in the state folder, which
    stays after the attempt for a bug report.
    """
    pending = plan.state / PENDING
    _write_json(
        pending,
        {
            "root": str(plan.install.root),
            "version": plan.version,
            "previous": plan.previous,
            "at": time.time(),
        },
    )
    windows = plan.install.system == "win32"
    script = plan.state / ("helper.ps1" if windows else "helper.sh")
    # Windows PowerShell 5.1 reads a file without a BOM in the ANSI code page,
    # which would garble a non-ASCII user folder.
    script.write_text(helper_script(plan), encoding="utf-8-sig" if windows else "utf-8")
    if windows:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200
        )
        detach = {"creationflags": flags}
    else:
        detach = {"start_new_session": True}
    try:
        with open(plan.state / "helper.log", "w", encoding="utf-8") as log:
            popen(
                helper_command(script, plan.install.system),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=child_env(),
                **detach,
            )
    except OSError as error:
        pending.unlink(missing_ok=True)
        raise UpdateFailed(
            "The helper that swaps the versions couldn't be started."
        ) from error


def clear_attempt(state: Path) -> None:
    """Remove what an earlier attempt left, keeping only ``helper.log``."""
    for name in _ATTEMPT_FOLDERS:
        shutil.rmtree(state / name, ignore_errors=True)
    for name in _ATTEMPT_FILES:
        (state / name).unlink(missing_ok=True)


def _ours(state: Path, install: Install) -> bool:
    pending = _pending(state)
    return pending is not None and pending.get("root") == str(install.root)


def note_start(
    install: Install | None = None,
    *,
    state: Path | None = None,
    pid: int | None = None,
) -> None:
    """At launch: if a helper is waiting for this install, say which process we are.

    Never raises: a launch must not fail over an update's bookkeeping.
    """
    try:
        install = current_install() if install is None else install
        if install is None:
            return
        state = state_dir(install) if state is None else state
        if _ours(state, install):
            (state / "started").write_text(
                str(os.getpid() if pid is None else pid), encoding="utf-8"
            )
    except Exception:
        pass


def note_boot(install: Install | None = None, *, state: Path | None = None) -> None:
    """Once the server answers: confirm a pending update, or clear an abandoned one.

    Never raises. An attempt is abandoned when no helper is waiting on it
    and its files are older than ``STALE_AFTER_S``: a cancelled download, a
    failed self-test, or a helper that died.
    """
    try:
        install = current_install() if install is None else install
        if install is None:
            return
        state = state_dir(install) if state is None else state
        if _ours(state, install):
            (state / "booted").write_text("", encoding="utf-8")
            return
        cutoff = time.time() - STALE_AFTER_S
        for name in (*_ATTEMPT_FOLDERS, PENDING, "started", "booted"):
            path = state / name
            if path.exists() and path.stat().st_mtime < cutoff:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
    except Exception:
        pass


def last_result(
    install: Install | None = None, *, state: Path | None = None
) -> UpdateResult | None:
    """How the last update on this install ended — ``None`` if there is no record."""
    try:
        if state is None:
            install = current_install() if install is None else install
            if install is None:
                return None
            state = state_dir(install)
        data = _read_json(state / "result.json")
        if data is None:
            return None
        pid = data.get("pid")
        return UpdateResult(
            status=str(data["status"]),
            version=str(data["version"]),
            previous=str(data["previous"]),
            reason=str(data.get("reason") or ""),
            pid=int(pid) if pid not in (None, "") else None,
        )
    except Exception:
        return None


def exit_soon(delay: float = RESTART_DELAY_S) -> None:
    """Quit this process ``delay`` seconds from now, the way the idle watcher does.

    The server runs in this process and owns the main thread, so
    ``os._exit`` from a timer is the only way out; the delay lets the
    "Restarting" message reach the browser first.
    """
    timer = threading.Timer(delay, os._exit, args=(0,))
    timer.daemon = True
    timer.start()
```

- [ ] **Step 4: Run the tests; they pass.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q`. Expected: all pass, with the `pwsh` tests skipped if PowerShell isn't installed. Ubuntu runners have `pwsh`, so CI runs them. If `pwsh` is available locally (`brew install powershell` is not required), check that they pass.

- [ ] **Step 5: Lint and commit.**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/desktop_update.py tests/test_desktop_update.py
git commit -m "Desktop updater: swap helpers, boot markers and the result (#385)"
```

---

### Task 4: `prepare` and the launcher's `--update`

**Files:**
- Modify: `scanpath_studio/desktop_update.py` (append `STEPS` and `prepare`)
- Modify: `desktop/launcher.py`: module docstring; new `update()`, `_confirm_boot_when_ready()` and `_note_update_start()`; hooks in `main()`
- Test: `tests/test_desktop_update.py`, `tests/test_desktop_bundle.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3; `updates.check_for_updates(latest=…)`; `progress.step_to(index)`.
- Produces:
  - `STEPS = ("Downloading", "Checking it", "Testing the new version", "Restarting")`
  - `prepare(check, install, *, allow_file=False, run=subprocess.run, opener=None, machine=None, on_step=None) -> SwapPlan`
  - in `launcher`: `update() -> int`, `_confirm_boot_when_ready(port: int) -> None`

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_desktop_update.py`:

```python
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
```

Append to `tests/test_desktop_bundle.py` (add `from types import SimpleNamespace` to its imports):

```python
def _desktop_check(status="update_available"):
    from scanpath_studio import updates

    return updates.UpdateCheck(status, "0.36.0", f"{status} message")


def test_update_flag_prepares_and_starts_the_swap(monkeypatch, capsys):
    from scanpath_studio import desktop_update, updates

    calls = []
    monkeypatch.setattr(updates, "check_for_updates", lambda **kw: _desktop_check())
    monkeypatch.setattr(desktop_update, "current_install", lambda: "INSTALL")
    plan = SimpleNamespace(version="99.0.0", state=Path("/state"))
    monkeypatch.setattr(
        desktop_update,
        "prepare",
        lambda check, install, **kw: calls.append(("prepare", install, kw)) or plan,
    )
    monkeypatch.setattr(
        desktop_update, "start_swap", lambda plan: calls.append(("swap", plan))
    )
    monkeypatch.delenv(desktop_update.FEED_ENV, raising=False)
    assert launcher.update() == 0
    assert calls[0][:2] == ("prepare", "INSTALL")
    assert calls[0][2]["allow_file"] is False
    assert calls[1] == ("swap", plan)
    assert "update ok" in capsys.readouterr().out


def test_update_flag_with_nothing_newer_exits_cleanly(monkeypatch, capsys):
    from scanpath_studio import desktop_update, updates

    monkeypatch.setattr(
        updates, "check_for_updates", lambda **kw: _desktop_check("up_to_date")
    )
    monkeypatch.setattr(
        desktop_update, "prepare", lambda *a, **k: pytest.fail("prepared")
    )
    assert launcher.update() == 0
    monkeypatch.setattr(
        updates, "check_for_updates", lambda **kw: _desktop_check("error")
    )
    assert launcher.update() == 1


def test_update_flag_reports_a_refusal(monkeypatch, capsys):
    from scanpath_studio import desktop_update, updates

    def refuse(*args, **kwargs):
        raise desktop_update.UpdateFailed("nope, and why")

    monkeypatch.setattr(updates, "check_for_updates", lambda **kw: _desktop_check())
    monkeypatch.setattr(desktop_update, "prepare", refuse)
    assert launcher.update() == 1
    assert "update FAILED: nope, and why" in capsys.readouterr().out


def test_update_flag_reads_the_test_feed(monkeypatch, tmp_path):
    from scanpath_studio import desktop_update, updates

    feed = tmp_path / "feed.json"
    feed.write_text('{"tag_name": "v99.0.0", "assets": []}')
    monkeypatch.setenv(desktop_update.FEED_ENV, str(feed))
    seen = {}

    def check(latest=None, **kw):
        seen["release"] = latest()
        return _desktop_check("up_to_date")

    monkeypatch.setattr(updates, "check_for_updates", check)
    assert launcher.update() == 0
    assert seen["release"].version == "99.0.0"


def test_the_boot_is_confirmed_once_the_server_answers(monkeypatch):
    from scanpath_studio import desktop_update

    noted = []
    monkeypatch.setattr(launcher, "_wait_for_server", lambda url, timeout_s=0: True)
    monkeypatch.setattr(desktop_update, "note_boot", lambda: noted.append(True))
    launcher._confirm_boot_when_ready(1234)
    assert noted == [True]
    monkeypatch.setattr(launcher, "_wait_for_server", lambda url, timeout_s=0: False)
    launcher._confirm_boot_when_ready(1234)
    assert noted == [True]


def test_the_launcher_stays_stdlib_only_at_import():
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    header = source.split("\ndef ", 1)[0]
    assert "scanpath_studio" not in header.split('"""', 2)[-1]
```

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py tests/test_desktop_bundle.py -q`. Expected: `AttributeError` on `du.prepare`, `du.STEPS`, `launcher.update` and `launcher._confirm_boot_when_ready`.

- [ ] **Step 3a: Implement `prepare`** (append to `desktop_update.py`):

```python
#: The steps the About card and ``--update`` name, in order.
STEPS = ("Downloading", "Checking it", "Testing the new version", "Restarting")


def prepare(
    check: UpdateCheck,
    install: Install,
    *,
    allow_file: bool = False,
    run: Callable = subprocess.run,
    opener: Callable | None = None,
    machine: str | None = None,
    on_step: Callable[[str], None] | None = None,
) -> SwapPlan:
    """Steps 1–4: refuse, download, stage and self-test — the swap is the caller's.

    Raises :class:`UpdateFailed` (the install untouched) or, from inside a
    progress task that was cancelled, ``progress.Cancelled``.
    """
    reason = refusal(check, install, run=run, machine=machine)
    if reason is not None:
        raise UpdateFailed(reason)
    state = state_dir(install)
    asset = asset_for(check, install, machine=machine)
    clear_attempt(state)

    def step(index: int) -> None:
        progress.step_to(index)
        if on_step is not None:
            on_step(STEPS[index])

    step(0)
    archive = download(asset, state / "download", allow_file=allow_file, opener=opener)
    step(1)
    staged = stage(archive, state, install, run=run)
    step(2)
    self_test(staged, install.system, run=run)
    step(3)
    return SwapPlan(
        pid=os.getpid(),
        install=install,
        staged=staged,
        state=state,
        version=check.latest.version,
        previous=check.current,
        relaunch=relaunch_command(install),
    )
```

- [ ] **Step 3b: Wire the launcher.** In `desktop/launcher.py`:

  1. Add to the module docstring, after the `--selfcheck` paragraph:

     ```
     ``--update`` is About's *Update & restart*, headless (#385): check GitHub
     (or ``SCANPATH_UPDATE_FEED``, a local JSON release CI uses), download,
     verify, stage and self-test the new version, then hand the swap to a
     detached helper and exit. The helper relaunches the app; the relaunched
     launcher reports in (``started`` at launch, ``booted`` once its server
     answers), and the helper puts the old version back if it never does.
     ```

  2. Add these functions after `selfcheck()`:

```python
def update() -> int:
    """``--update``: About's *Update & restart*, headless (#385); an exit code."""
    from scanpath_studio import desktop_update, updates

    feed = os.environ.get(desktop_update.FEED_ENV, "").strip()
    latest = (lambda: desktop_update.feed_release(Path(feed))) if feed else None
    check = updates.check_for_updates(latest=latest)
    print(check.message)
    if check.status != "update_available":
        return 1 if check.status == "error" else 0
    try:
        plan = desktop_update.prepare(
            check,
            desktop_update.current_install(),
            # Only the test feed may hand over a local file.
            allow_file=bool(feed),
            on_step=lambda step: print(f"update: {step}…"),
        )
        desktop_update.start_swap(plan)
    except desktop_update.UpdateFailed as error:
        print(f"update FAILED: {error}")
        return 1
    print(
        f"update ok: swapping in v{plan.version}; the helper restarts the app "
        f"(log: {plan.state / 'helper.log'})"
    )
    return 0


def _note_update_start() -> None:
    """Tell a waiting update helper that this launch is the new version (#385)."""
    try:
        from scanpath_studio import desktop_update

        desktop_update.note_start()
    except Exception:
        pass  # an update's bookkeeping must never stop a launch


def _confirm_boot_when_ready(port: int) -> None:
    """Once the server answers, confirm a pending update (#385) — even with no
    browser to open, so a headless relaunch confirms too."""
    if not _wait_for_server(f"http://127.0.0.1:{port}/_stcore/health"):
        return
    try:
        from scanpath_studio import desktop_update

        desktop_update.note_boot()
    except Exception:
        pass
```

  3. In `main()`, right after the `--selfcheck` branch:

```python
    if "--update" in sys.argv[1:]:
        sys.exit(update())

    _note_update_start()
```

     After `port = _resolve_port()`:

```python
    threading.Thread(target=_confirm_boot_when_ready, args=(port,), daemon=True).start()
```

- [ ] **Step 4: Run the tests; they pass.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py tests/test_desktop_bundle.py tests/test_desktop_app_window.py -q`. Expected: all pass.

- [ ] **Step 5: Lint and commit.**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/desktop_update.py desktop/launcher.py tests/test_desktop_update.py tests/test_desktop_bundle.py
git commit -m "Desktop updater: prepare, and the launcher's --update (#385)"
```

---

### Task 5: About — **Update & restart**

**Files:**
- Modify: `scanpath_studio/app.py`:
  - import `desktop_update` at module top, beside `updates as update_check`;
  - `_render_build_and_updates` gets the last-update notice;
  - `_render_update_result` gets the desktop branch;
  - new `_render_last_update`, `_render_desktop_update`, `_run_desktop_update` and `_stop_desktop_update`.
- Test: `tests/test_updates.py` (append)

**Interfaces:**
- Consumes:
  - `desktop_update.current_install()`, `refusal(check, install)`, `prepare(check, install)`, `start_swap(plan)`, `exit_soon()`, `last_result()`, `STEPS`, `UpdateFailed`, `SwapPlan`, `UpdateResult`;
  - `loading.card(...)`, `loading.Cancel`, `loading.session_id()`;
  - `progress.cancel(key)`;
  - `human_size(n)` (already imported in `app.py`).
- Produces: widget key `about_update_restart` (primary button). The desktop branch otherwise keeps the existing `st.link_button` download.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_updates.py`):

```python
def _desktop_update_check(version="99.0.0"):
    release = updates._release_from(
        _payload(
            f"v{version}",
            [
                "ScanpathStudio-macos-arm64.dmg",
                "ScanpathStudio-windows-x86_64.zip",
                "ScanpathStudio-windows-x86_64-setup.exe",
                "ScanpathStudio-linux-x86_64.tar.gz",
            ],
        )
    )
    return updates.UpdateCheck(
        "update_available",
        "0.36.0",
        f"v{version} is out; this is v0.36.0.",
        latest=release,
        install_kind="desktop",
        download=release.assets[0],
    )


def _desktop_about(monkeypatch, *, refusal=None):
    from scanpath_studio import desktop_update

    _local_run(monkeypatch)
    monkeypatch.setattr(
        updates, "check_for_updates", lambda **kw: _desktop_update_check()
    )
    monkeypatch.setattr(desktop_update, "current_install", lambda: "INSTALL")
    monkeypatch.setattr(desktop_update, "refusal", lambda check, install: refusal)
    monkeypatch.setattr(desktop_update, "last_result", lambda: None)


def test_the_desktop_app_offers_update_and_restart(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch)
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert at.button(key="about_update_restart").label == "Update & restart"


def test_a_refused_update_says_why_and_still_offers_the_download(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _desktop_about(monkeypatch, refusal="This account can't change /Applications.")
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert not [b for b in at.button if b.key == "about_update_restart"]
    assert any("can't change" in caption.value for caption in at.caption)


def test_update_and_restart_swaps_then_quits(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import desktop_update

    _desktop_about(monkeypatch)
    calls = []
    monkeypatch.setattr(
        desktop_update,
        "prepare",
        lambda check, install: (
            calls.append("prepare")
            or desktop_update.SwapPlan(
                1, None, Path("/s"), Path("/st"), "99.0.0", "0.36.0", ("x",)
            )
        ),
    )
    monkeypatch.setattr(desktop_update, "start_swap", lambda plan: calls.append("swap"))
    monkeypatch.setattr(desktop_update, "exit_soon", lambda: calls.append("exit"))
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    at.button(key="about_update_restart").click().run()
    assert not at.exception, at.exception
    assert calls == ["prepare", "swap", "exit"]
    assert any("Restarting into v99.0.0" in ok.value for ok in at.success)


def test_a_failed_update_changes_nothing_and_says_so(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import desktop_update

    _desktop_about(monkeypatch)

    def fail(check, install):
        raise desktop_update.UpdateFailed("The download stopped before it finished.")

    monkeypatch.setattr(desktop_update, "prepare", fail)
    monkeypatch.setattr(desktop_update, "exit_soon", lambda: pytest.fail("quit"))
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    at.button(key="about_update_restart").click().run()
    assert not at.exception, at.exception
    assert any("stopped before it finished" in e.value for e in at.error)
    assert any("Nothing was changed" in e.value for e in at.error)


@pytest.mark.parametrize(
    ("result", "where", "says"),
    [
        (
            ("rolled_back", "the new version did not start within 180 seconds"),
            "warning",
            "didn't go through",
        ),
        (("updated", ""), "caption", "Updated from v0.35.0"),
    ],
)
def test_about_reports_how_the_last_update_ended(monkeypatch, result, where, says):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app, desktop_update
    from scanpath_studio.build_info import BuildInfo

    _local_run(monkeypatch)
    status, reason = result
    monkeypatch.setattr(
        desktop_update,
        "last_result",
        lambda: desktop_update.UpdateResult(status, "0.36.0", "0.35.0", reason),
    )
    monkeypatch.setattr(app, "_build_info", lambda: BuildInfo("0.36.0", "0.36.0"))
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    assert any(says in element.value for element in getattr(at, where))
```

The last test needs a seam for the build. If `_render_build_and_updates` calls `build_info()` directly, add a module-level `_build_info()` wrapper in `app.py` that returns `build_info()`. Use it in `_render_build_and_updates`, so the test can pin the version.

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_updates.py -q`. Expected: the new tests fail; there is no `about_update_restart` button yet.

- [ ] **Step 3: Implement in `scanpath_studio/app.py`.**

  1. Top-level imports: add `from scanpath_studio import desktop_update` beside the existing `updates as update_check` import. Check that `loading` and `progress` are already imported; `loading` is, and `progress` too (`_stop_download` uses it).

  2. Replace `_render_build_and_updates`'s first lines and add the notice:

```python
def _build_info():
    """This process's build (a seam the About tests pin)."""
    from scanpath_studio.build_info import build_info

    return build_info()


def _render_build_and_updates() -> None:
    """#139: which build this is, and — on a local run — *Check for updates*."""
    info = _build_info()
    if info.version != info.release:
        st.caption(info.describe())
    # #385: how the desktop app's last update ended — None anywhere else.
    last = desktop_update.last_result()
    if last is not None:
        _render_last_update(last, info.version)
    if not _update_check_offered():
        return
    # …the rest of the function is unchanged…
```

  3. Add `_render_last_update`:

```python
def _render_last_update(last: desktop_update.UpdateResult, current: str) -> None:
    """#385: the outcome the update helper left behind, across the restart."""
    if last.status == "updated":
        if last.version == current:
            st.caption(f"Updated from v{last.previous}.")
        return
    st.warning(
        f"The update to v{last.version} didn't go through: {last.reason}. "
        f"v{last.previous} is still installed.",
        icon=ICONS["warning"],
    )
```

  4. In `_render_update_result`, replace the `if result.download is not None: … elif result.command:` block with:

```python
    if result.install_kind == "desktop":
        _render_desktop_update(result)
    elif result.command:
        st.code(result.command, language="bash")
        st.caption("Then restart the app.")
```

  5. Add the desktop branch:

```python
def _render_desktop_update(result: update_check.UpdateCheck) -> None:
    """#385: **Update & restart** when this app can update itself, and the
    download either way — beside the button, or instead of it with the reason."""
    install = desktop_update.current_install()
    reason = desktop_update.refusal(result, install)
    clicked = False
    if reason is None:
        clicked = st.button(
            "Update & restart",
            type="primary",
            icon=ICONS["update"],
            key="about_update_restart",
            help="Downloads the new version, checks and tests it, then restarts "
            "into it. Your datasets and settings come back with it.",
        )
    else:
        st.caption(reason)
    if result.download is not None:
        label = (
            "Download instead"
            if reason is None
            else f"Download {result.download.name} ({human_size(result.download.size)})"
        )
        st.link_button(label, result.download.url, icon=ICONS["download"])
    if clicked:
        _run_desktop_update(result, install)


def _stop_desktop_update(task_key: tuple) -> None:
    """#385: Cancel on the update card — the download stops at its next chunk."""
    progress.cancel(task_key)


def _run_desktop_update(
    result: update_check.UpdateCheck, install: desktop_update.Install
) -> None:
    """Download, check and test under a card, then hand over to the helper and quit."""
    task_key = ("desktop_update", loading.session_id())
    try:
        with loading.card(
            st.empty(),
            key="desktop_update",
            title=f"Updating to v{result.latest.version}",
            steps=desktop_update.STEPS,
            step_list=True,
            task_key=task_key,
            cancel=loading.Cancel(
                "Cancel update", _stop_desktop_update, args=(task_key,)
            ),
        ):
            plan = desktop_update.prepare(result, install)
        desktop_update.start_swap(plan)
    except desktop_update.UpdateFailed as error:
        st.error(f"{error} Nothing was changed.", icon=ICONS["error"])
        return
    st.success(
        f"Restarting into v{plan.version}. A new window opens when it's ready "
        "(on Windows that can take a minute or two); you can close this one.",
        icon=ICONS["update"],
    )
    desktop_update.exit_soon()
```

  Leave `progress.Cancelled` uncaught, exactly as `_download_with_card` does: `loading.run_scope` turns it into a stopped run. If the AppTests show that `loading.card` cannot open inside the dialog under AppTest, keep the card but note it in the report. Don't replace it with `st.spinner`: the design calls for a card with Cancel.

- [ ] **Step 4: Run the tests; they pass.** Run `uv run --extra test --extra lint pytest tests/test_updates.py tests/test_icons.py tests/test_crash_report.py -q`. `test_icons` / `test_crash_report` guard the icon and `@guarded` conventions. Expected: all pass.

- [ ] **Step 5: Lint and commit.**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/app.py tests/test_updates.py
git commit -m "About: Update & restart in the desktop app (#385)"
```

---

### Task 6: The end-to-end CI run, docs and changelog

**Files:**
- Create: `desktop/update_e2e.py`
- Modify:
  - `.github/workflows/desktop.yml`
  - `desktop/README.md`
  - `docs/getting-started.md` (*Updating*)
  - `docs/privacy.md` (*Network activity*)
  - `AGENTS.md` (architecture map)
  - `scanpath_studio/CLAUDE.md` (module bullet)
- Create: `changelog.d/385.added.md`
- Test: `tests/test_desktop_update.py` (two workflow checks)

**Interfaces:**
- Consumes: `desktop_update.install_at`, `state_dir`, `update_archive`, `last_result`, `FEED_ENV`; `launcher._free_port`.
- Produces: `python desktop/update_e2e.py <installed .app or executable> <archive>`. It exits non-zero with the helper log on any failure.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_desktop_update.py`):

```python
def test_ci_runs_the_end_to_end_update_on_every_os():
    workflow = (ROOT / ".github/workflows/desktop.yml").read_text(encoding="utf-8")
    assert workflow.count("desktop/update_e2e.py") == 3


def test_the_e2e_driver_is_stdlib_plus_the_package():
    source = (ROOT / "desktop/update_e2e.py").read_text(encoding="utf-8")
    assert "from scanpath_studio import desktop_update" in source
    assert "import streamlit" not in source
```

- [ ] **Step 2: Run them; they fail.** Run `uv run --extra test --extra lint pytest tests/test_desktop_update.py -q -k "e2e or end_to_end"`. Expected: FileNotFoundError, or count 0.

- [ ] **Step 3: Write `desktop/update_e2e.py`:**

```python
"""End-to-end test of the desktop app's own updater (#385).

Usage:
    python desktop/update_e2e.py <installed ScanpathStudio.app | executable> <archive>

Offers ``archive`` — this very build — back to the installed copy as a newer
release, through a local feed (``SCANPATH_UPDATE_FEED``), and runs
``--update`` on it. Then it requires what a real update does: the helper swaps
the payload, relaunches the app, and the relaunched launcher reports in
(``result.json`` says ``updated``); the old copy is cleaned away; and on
Windows the installer's uninstaller survives. The relaunched app is stopped at
the end so ``smoke_test.py`` can boot the installed copy next. What CI cannot
reproduce — Gatekeeper and SmartScreen on a real machine — is a manual check
in #385's review.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from launcher import _free_port

from scanpath_studio import desktop_update

#: --update itself: copy the archive, unpack it, run the staged --selfcheck.
UPDATE_TIMEOUT_S = 900.0
#: Then the helper: the old process quits, the swap, the relaunch's boot.
RESULT_TIMEOUT_S = desktop_update.BOOT_TIMEOUT_S + desktop_update.QUIT_TIMEOUT_S + 120.0
FAKE_VERSION = "99.0.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _helper_log(state: Path) -> str:
    try:
        return (state / "helper.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no helper.log)"


def _stop(pid: int | None) -> None:
    if not pid:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def main() -> None:
    target, archive = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    executable = (
        desktop_update.executable_in(target, "darwin")
        if target.suffix == ".app"
        else target
    )
    install = desktop_update.install_at(executable)
    if install is None:
        raise SystemExit(f"[update-e2e] {target} isn't an installed Scanpath Studio")
    if archive.name != desktop_update.update_archive():
        raise SystemExit(
            f"[update-e2e] {archive.name} isn't this computer's update archive "
            f"({desktop_update.update_archive()})"
        )
    state = desktop_update.state_dir(install)
    feed = archive.parent / "update-feed.json"
    feed.write_text(
        json.dumps(
            {
                "tag_name": f"v{FAKE_VERSION}",
                "html_url": "https://github.com/lacclab/scanpath-studio/releases",
                "published_at": "2026-01-01T00:00:00Z",
                "assets": [
                    {
                        "name": archive.name,
                        "browser_download_url": archive.as_uri(),
                        "size": archive.stat().st_size,
                        "digest": f"sha256:{_sha256(archive)}",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = install.root / install.payload[0]
    before = payload.stat().st_ino
    uninstaller = install.root / "unins000.exe"
    had_uninstaller = uninstaller.exists()
    env = dict(
        os.environ,
        **{
            desktop_update.FEED_ENV: str(feed),
            "SCANPATH_DESKTOP_NO_BROWSER": "1",
            "SCANPATH_DESKTOP_NO_LOG_FILE": "1",
            "SCANPATH_DESKTOP_IDLE_EXIT_S": "0",
            "SCANPATH_DESKTOP_PORT": str(_free_port()),
        },
    )
    print(
        f"[update-e2e] {executable} --update  (offered: v{FAKE_VERSION} = {archive.name})"
    )
    ran = subprocess.run(
        [str(executable), "--update"], env=env, timeout=UPDATE_TIMEOUT_S
    )
    if ran.returncode != 0:
        raise SystemExit(f"[update-e2e] --update exited {ran.returncode}")

    deadline = time.monotonic() + RESULT_TIMEOUT_S
    while (result := desktop_update.last_result(state=state)) is None:
        if time.monotonic() > deadline:
            raise SystemExit(
                f"[update-e2e] no result after {RESULT_TIMEOUT_S:.0f}s; helper log:\n"
                + _helper_log(state)
            )
        time.sleep(2)
    print(f"[update-e2e] result: {result}")
    try:
        if result.status != "updated":
            raise SystemExit(
                "[update-e2e] update did not succeed; helper log:\n"
                + _helper_log(state)
            )
        for _ in range(60):  # the helper cleans up just after writing the result
            if not (state / "old").exists():
                break
            time.sleep(1)
        else:
            raise SystemExit(
                "[update-e2e] the old version was left behind in " + str(state)
            )
        if payload.stat().st_ino == before:
            raise SystemExit(f"[update-e2e] {payload} was not swapped")
        if had_uninstaller and not uninstaller.exists():
            raise SystemExit(
                "[update-e2e] the update removed the installer's uninstaller"
            )
    finally:
        _stop(result.pid)
    time.sleep(3)  # let the stopped app release its files before the smoke test
    print("[update-e2e] swapped, relaunched and confirmed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add the workflow steps** to `.github/workflows/desktop.yml`.

  Insert the three steps, in this order, right after *Build the installer* and before *Smoke test the installer*. By then every leg's archive exists: the `.dmg` (built, signed and stapled earlier), the `.tar.gz` and the `.zip`. All three steps come before *Upload the installer* / *Upload artifact*.

```yaml
      # #385: the in-app updater, end to end. Install this build, offer it back
      # as a newer release through a local feed, run `--update`, and require
      # the swap, the relaunch and the new copy's "booted" report — then
      # smoke-test what is installed now. macOS needs the Developer ID team the
      # updater checks the download against, so it runs where signing does.
      - name: End-to-end update (Linux)
        if: runner.os == 'Linux'
        run: |
          set -euo pipefail
          mkdir -p "$RUNNER_TEMP/opt"
          tar -C "$RUNNER_TEMP/opt" -xzf ${{ matrix.archive }}
          python desktop/update_e2e.py "$RUNNER_TEMP/opt/ScanpathStudio/ScanpathStudio" ${{ matrix.archive }}
          python desktop/smoke_test.py "$RUNNER_TEMP/opt/ScanpathStudio/ScanpathStudio"

      - name: End-to-end update (macOS)
        if: runner.os == 'macOS' && steps.signing.outputs.enabled == 'true'
        run: |
          set -euo pipefail
          mkdir -p "$RUNNER_TEMP/Applications"
          ditto "$APP" "$RUNNER_TEMP/Applications/ScanpathStudio.app"
          python desktop/update_e2e.py "$RUNNER_TEMP/Applications/ScanpathStudio.app" ${{ matrix.archive }}
          python desktop/smoke_test.py "$RUNNER_TEMP/Applications/ScanpathStudio.app"

      # Installed the way users install it (per-user, the default folder), so
      # the update must leave the installer's uninstaller working.
      - name: End-to-end update (Windows)
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          $ErrorActionPreference = 'Stop'
          $p = Start-Process -Wait -PassThru '.\${{ matrix.installer }}' `
            -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
          if ($p.ExitCode) { throw "installer exited with $($p.ExitCode)" }
          $dir = Join-Path $env:LOCALAPPDATA 'Programs\Scanpath Studio'
          python desktop/update_e2e.py (Join-Path $dir 'ScanpathStudio.exe') ${{ matrix.archive }}
          if ($LASTEXITCODE) { exit $LASTEXITCODE }
          python desktop/smoke_test.py (Join-Path $dir 'ScanpathStudio.exe')
          if ($LASTEXITCODE) { exit $LASTEXITCODE }
          $p = Start-Process -Wait -PassThru (Join-Path $dir 'unins000.exe') `
            -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
          if ($p.ExitCode) { throw "uninstaller exited with $($p.ExitCode)" }
          for ($i = 0; $i -lt 30 -and (Test-Path (Join-Path $dir '_internal')); $i++) { Start-Sleep 2 }
          if (Test-Path (Join-Path $dir '_internal')) { throw "uninstall after the update left $dir\_internal behind" }
```

  The Windows e2e installs to the installer's default per-user folder, not the `$RUNNER_TEMP` folder *Smoke test the installer* uses, and uninstalls before that step runs, so the two don't collide.

- [ ] **Step 5: Docs.**

  1. `docs/getting-started.md` → *Updating*: after the paragraph ending "`scanpath-studio version --check` does the same from a terminal.", add:

     ```markdown
     In the desktop app, **:material/update: Update & restart** does the rest:
     it downloads the new version, checks it against the checksum GitHub
     publishes (on macOS also that it is signed by the same developers), tests
     it, and restarts into it — your datasets and settings come back with it. If
     the new version doesn't start within three minutes, the app puts the old
     one back and says so in About. It needs to be able to write where the app
     is installed; when it can't (for example, on a shared Mac where an
     administrator installed it), About says why and offers the download
     instead.
     ```

  2. `docs/privacy.md` → *Network activity*: after the sentence ending "…in its User-Agent.", add:

     ```markdown
     In the desktop app, **Update & restart** then downloads that release's
     archive for your computer from GitHub (`github.com`, which serves it from
     `objects.githubusercontent.com`) — only when you click it.
     ```

  3. `desktop/README.md`:
     - In the `launcher.py` bullet, add "`--update` runs About's *Update & restart* headless (#385)".
     - Add `SCANPATH_UPDATE_FEED` (a local JSON release in GitHub's shape, only for `--update`; CI's end-to-end run) to the environment-variables bullet.
     - Add a bullet: "`update_e2e.py` — CI's end-to-end check of the in-app updater: offers the fresh build back as a newer release and requires the swap, the relaunch and the boot report (#385)."

  4. `AGENTS.md` architecture map: add a line after `├─ updates.py …`:

     ```
     ├─ desktop_update.py #385: the desktop app's own *Update & restart* — `refusal` (frozen only; newer, not a pre-release; sha256 digest; not translocated; install writable; same-volume state folder; disk; macOS Developer ID team), `download` (repo release URLs only, sha256-checked), `stage` (dmg → codesign/Team ID/spctl; zip; tar `filter="data"`), `self_test` (`--selfcheck`), `start_swap` (detached sh/PowerShell helper swapping the payload entries — `Contents`, or the executable + `_internal` so `unins000.*` survive — relaunch, roll back after `BOOT_TIMEOUT_S`), and the launcher's `note_start`/`note_boot`; stdlib + packaging, no Streamlit
     ```

  5. `scanpath_studio/CLAUDE.md`: add a bullet after the `updates.py` one:

     ```markdown
     - [desktop_update.py](desktop_update.py) — **#385** the desktop app's one-click update. Surfaces: About's **Update & restart** (only when `refusal` is `None`; *Download* stays beside it) and the launcher's `--update`; CLI/API don't apply (only the frozen bundle can replace itself). Everything lives in `state_dir(install)` — on the install's volume so every move is a rename — and the relaunched launcher reports in through `pending.json` (by install root, not version, so CI can offer the same build as `v99.0.0` via `SCANPATH_UPDATE_FEED`). Gotchas: the swap moves *payload entries* (`Contents`; `ScanpathStudio[.exe]` + `_internal`), never the whole folder, or the Windows installer's uninstaller goes; children get `child_env()` (`PYINSTALLER_RESET_ENVIRONMENT=1`); the PowerShell helper targets Windows PowerShell 5.1 and is written with a BOM; `UPDATE_ARCHIVES` must match `desktop.yml`'s `archive:` names (a test reads it).
     ```

  6. `changelog.d/385.added.md`, one line:

     ```
     The desktop app updates itself: Help → About → Check for updates → Update & restart downloads, checks and tests the new version, then restarts into it, and puts the old one back if it doesn't start.
     ```

- [ ] **Step 6: Run everything.**

```bash
uv run --extra test --extra lint pytest -n auto -q
uv run --extra lint ruff check . && uv run --extra lint ruff format --check .
uv run --extra docs mkdocs build --strict
```

  Expected: the suite passes (pwsh tests may skip locally), ruff is clean, and the docs build exits 0.

- [ ] **Step 7: Commit.**

```bash
git add desktop/update_e2e.py .github/workflows/desktop.yml desktop/README.md docs/getting-started.md docs/privacy.md AGENTS.md scanpath_studio/CLAUDE.md changelog.d/385.added.md tests/test_desktop_update.py
git commit -m "Desktop updater: end-to-end CI run, docs and changelog (#385)"
```

---

## After the tasks (controller, not an implementer)

- Run the `surface-parity-reviewer` and `perf-reviewer` subagents over the branch diff. The final whole-branch review comes first.
- Push `desktop-updater` and open a PR stacked on `build-versions-and-updates` (base: that branch until PR #390 merges, then `main`).
- Dispatch `desktop.yml` on the branch. The three *End-to-end update* steps are the proof; macOS needs the signing secrets, which a dispatch in this repo has.
- Move #385 to **Review** with a `⚖ Waiting on you` checklist:
  - try it on a real machine per OS, v(N) → v(N+1), once a release ships the updater. Gatekeeper / SmartScreen / App Management can't be reproduced in CI;
  - the rulings above.
