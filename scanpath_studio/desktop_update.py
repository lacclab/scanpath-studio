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

import base64
import hashlib
import http.client
import json
import math
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

from . import progress, updates
from .updates import Asset, Release, UpdateCheck, UpdateCheckError

APP_NAME = "ScanpathStudio"
#: The macOS tools the updater trusts, by absolute path so nothing earlier on
#: ``PATH`` can stand in for them.
CODESIGN = "/usr/bin/codesign"
SPCTL = "/usr/sbin/spctl"
HDIUTIL = "/usr/bin/hdiutil"
DITTO = "/usr/bin/ditto"
OPEN = "/usr/bin/open"
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

# The marker files below, the keys of ``pending.json`` and ``result.json``,
# ``state_dir``'s paths and ``_ours``' root matching are a wire format between
# releases: the helper an *old* version starts waits on what the *new*
# version's launcher writes. Never change one without a migration
# (``tests/test_desktop_update.py::test_the_update_marker_contract_is_pinned``).
#: The attempt under way: ``root``, ``version``, ``previous``, ``at``.
PENDING = "pending.json"
#: The relaunched launcher's pid, written at launch (:func:`note_start`).
STARTED = "started"
#: Written once the relaunched server answers (:func:`note_boot`).
BOOTED = "booted"
#: How the attempt ended: ``status``, ``version``, ``previous``, ``reason``, ``pid``.
RESULT = "result.json"
#: The helper's first act, which :func:`start_swap` waits for before the app quits.
HELPER_STARTED = "helper-started"

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
            errors="replace",
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
            [CODESIGN, "-dv", "--verbose=2", str(app)],
            capture_output=True,
            text=True,
            errors="replace",
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
    # Ad-hoc and unsigned code says "TeamIdentifier=not set", which the
    # pattern (one token, then the end of the line) never matches.
    if result.returncode != 0 or found is None:
        return None
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
    # A start in the future is a clock that moved, not an attempt to wait on.
    if abs(time.time() - started) > STALE_AFTER_S:
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
            HDIUTIL,
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
            [DITTO, str(mount / f"{APP_NAME}.app"), str(app)],
            "The new version couldn't be copied out of the disk image.",
        )
    finally:
        try:
            run(
                [HDIUTIL, "detach", str(mount), "-force"],
                capture_output=True,
                text=True,
                errors="replace",
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
        [CODESIGN, "--verify", "--deep", "--strict", str(staged_app)],
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
        [SPCTL, "--assess", "--type", "exec", str(staged_app)],
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


#: How long the relaunched version has to answer before the old one is put
#: back. The relaunched launcher itself waits up to its ``HEALTH_TIMEOUT_S``
#: (180 s — Windows' first-launch scan of a new bundle) for its server before
#: it reports in, so this must leave room beyond that.
BOOT_TIMEOUT_S = 240
#: How long :func:`start_swap` waits for the helper's first sign of life.
HANDSHAKE_TIMEOUT_S = 15
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
_ATTEMPT_FILES = (PENDING, STARTED, BOOTED, RESULT, HELPER_STARTED)


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
    return (OPEN, "-n", *forwarded, str(install.root))


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
TRACK_LAUNCH=@@TRACK_LAUNCH@@
LAUNCHED_PID=""

# First, before anything can fail: the app waits for this before it quits.
: > "$STATE/helper-started"

result() {
  printf '{"status": "%s", "version": "%s", "previous": "%s", "reason": "%s", "pid": %s}\n' \
    "$1" "$VERSION" "$PREVIOUS" "$2" "${3:-null}" > "$STATE/result.json.tmp" &&
    mv -f "$STATE/result.json.tmp" "$STATE/result.json"
}

# The launched process, for the rollback of a version that never wrote
# `started` — except through macOS's `open`, whose $! exits at once: a pid to
# kill later could by then be some other process's.
relaunch() {
  nohup @@RELAUNCH@@ >/dev/null 2>&1 &
  if [ "$TRACK_LAUNCH" = 1 ]; then
    LAUNCHED_PID=$!
  fi
}

# The old version is (or is not) in place and the attempt is over: say so,
# forget the attempt so the app does not report in for nobody, start it again.
give_up() {
  result failed "$1"
  rm -f "$STATE/@@PENDING@@" "$STATE/started" "$STATE/booted" "$STATE/helper-started"
  relaunch
  exit 1
}

# Move every entry from $1 to $2; on a failure put back what moved. An entry
# that already exists at the destination is a failure, never nested into.
move_all() {
  moved=""
  for entry in $ENTRIES; do
    if [ ! -e "$2/$entry" ] && mv "$1/$entry" "$2/$entry"; then
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
    # The old version is still running, so nothing is relaunched; forget the
    # attempt so a retry isn't refused as one already under way.
    result failed "the app did not quit"
    rm -f "$STATE/@@PENDING@@" "$STATE/started" "$STATE/booted" "$STATE/helper-started"
    exit 1
  fi
  sleep 0.5
  ticks=$((ticks + 1))
done

rm -rf "$STATE/old" "$STATE/failed"
rm -f "$STATE/started" "$STATE/booted"
if ! mkdir "$STATE/old" "$STATE/failed"; then
  give_up "the update folder could not be prepared"
fi
if ! move_all "$ROOT" "$STATE/old"; then
  give_up "the old version could not be moved aside"
fi
if ! move_all "$NEW" "$ROOT"; then
  if move_all "$STATE/old" "$ROOT"; then
    give_up "the new version could not be moved into place"
  fi
  give_up "the new version could not be moved into place, and the old one could not be put back"
fi
touch "$ROOT"
relaunch

ticks=0
while [ ! -e "$STATE/booted" ]; do
  if [ "$ticks" -ge "$BOOT_TICKS" ]; then
    new_pid=$(cat "$STATE/started" 2>/dev/null)
    # A version that hung before writing `started` is still the process we launched.
    [ -n "$new_pid" ] || new_pid=$LAUNCHED_PID
    if [ -n "$new_pid" ]; then
      kill "$new_pid" 2>/dev/null
      sleep 2
      kill -9 "$new_pid" 2>/dev/null
    fi
    rm -f "$STATE/@@PENDING@@" "$STATE/started" "$STATE/helper-started"
    cleanup=1
    if move_all "$ROOT" "$STATE/failed"; then
      if move_all "$STATE/old" "$ROOT"; then
        result rolled_back "the new version did not start within $BOOT_TIMEOUT seconds"
      else
        # Never leave the install empty, and keep the new version's files.
        move_all "$STATE/failed" "$ROOT"
        result failed "the new version did not start, and the old one could not be put back"
        cleanup=0
      fi
    else
      result failed "the new version did not start, and could not be removed"
      cleanup=0
    fi
    touch "$ROOT"
    relaunch
    if [ "$cleanup" = 1 ]; then
      rm -rf "$STATE/old" "$STATE/failed" "$STATE/staged" "$STATE/download"
    fi
    exit 1
  fi
  sleep 0.5
  ticks=$((ticks + 1))
done

new_pid=$(cat "$STATE/started" 2>/dev/null)
result updated "" "${new_pid:-null}"
rm -rf "$STATE/old" "$STATE/failed" "$STATE/staged" "$STATE/download"
rm -f "$STATE/@@PENDING@@" "$STATE/started" "$STATE/booted" "$STATE/helper-started"
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
$script:Launched = $null

# First, before anything can fail: the app waits for this before it quits.
[IO.File]::WriteAllText((Join-Path $State 'helper-started'), '')

function Write-Result($Status, $Reason, $NewPid) {
  $record = [ordered]@{ status = $Status; version = $Version; previous = $Previous; reason = $Reason; pid = $NewPid }
  $tmp = Join-Path $State 'result.json.tmp'
  [IO.File]::WriteAllText($tmp, ($record | ConvertTo-Json -Compress))
  Move-Item -LiteralPath $tmp -Destination (Join-Path $State 'result.json') -Force
}

# Keeps the started process, for the rollback of a version that never wrote
# `started`; assigned, so nothing reaches the pipeline.
function Start-App {
  $rest = @($Relaunch | Select-Object -Skip 1 | ForEach-Object { '"' + $_ + '"' })
  if ($rest.Count) {
    $script:Launched = Start-Process -FilePath $Relaunch[0] -ArgumentList $rest -WorkingDirectory $Root -PassThru
  } else {
    $script:Launched = Start-Process -FilePath $Relaunch[0] -WorkingDirectory $Root -PassThru
  }
}

# The old version is (or is not) in place and the attempt is over: say so,
# forget the attempt so the app does not report in for nobody, start it again.
function Stop-Update($Reason) {
  Write-Result 'failed' $Reason $null
  foreach ($name in $Pending, 'started', 'booted', 'helper-started') {
    Remove-Item -LiteralPath (Join-Path $State $name) -Force -ErrorAction SilentlyContinue
  }
  Start-App
  exit 1
}

# Move every entry from $From to $To, retrying while antivirus holds a file;
# on a failure put back what moved. An entry that already exists at the
# destination is a failure, never nested into.
function Move-All($From, $To) {
  $moved = @()
  foreach ($entry in $Entries) {
    $done = $false
    $target = Join-Path $To $entry
    if (-not (Test-Path -LiteralPath $target)) {
      for ($try = 0; $try -lt 60 -and -not $done; $try++) {
        try {
          Move-Item -LiteralPath (Join-Path $From $entry) -Destination $target -ErrorAction Stop
          $done = $true
        } catch {
          Start-Sleep -Milliseconds 500
        }
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
  # The old version is still running, so nothing is relaunched; forget the
  # attempt so a retry isn't refused as one already under way.
  Write-Result 'failed' 'the app did not quit' $null
  foreach ($name in $Pending, 'started', 'booted', 'helper-started') {
    Remove-Item -LiteralPath (Join-Path $State $name) -Force -ErrorAction SilentlyContinue
  }
  exit 1
}

foreach ($name in 'old', 'failed') {
  $path = Join-Path $State $name
  try {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop }
    [IO.Directory]::CreateDirectory($path) | Out-Null
  } catch {
    Stop-Update 'the update folder could not be prepared'
  }
}
foreach ($name in 'started', 'booted') {
  Remove-Item -LiteralPath (Join-Path $State $name) -Force -ErrorAction SilentlyContinue
}
if (-not (Move-All $Root (Join-Path $State 'old'))) {
  Stop-Update 'the old version could not be moved aside'
}
if (-not (Move-All $New $Root)) {
  if (Move-All (Join-Path $State 'old') $Root) {
    Stop-Update 'the new version could not be moved into place'
  }
  Stop-Update 'the new version could not be moved into place, and the old one could not be put back'
}
Start-App

$ticks = 0
while (-not (Test-Path -LiteralPath (Join-Path $State 'booted'))) {
  if ($ticks -ge $BootTicks) {
    $newPid = Read-NewPid
    # A version that hung before writing `started` is still the process we launched.
    if (-not $newPid -and $script:Launched) { $newPid = $script:Launched.Id }
    if ($newPid) {
      Stop-Process -Id $newPid -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 2
    }
    foreach ($name in $Pending, 'started', 'helper-started') {
      Remove-Item -LiteralPath (Join-Path $State $name) -Force -ErrorAction SilentlyContinue
    }
    $cleanup = $true
    if (Move-All $Root (Join-Path $State 'failed')) {
      if (Move-All (Join-Path $State 'old') $Root) {
        Write-Result 'rolled_back' "the new version did not start within $BootTimeout seconds" $null
      } else {
        # Never leave the install empty, and keep the new version's files.
        Move-All (Join-Path $State 'failed') $Root | Out-Null
        Write-Result 'failed' 'the new version did not start, and the old one could not be put back' $null
        $cleanup = $false
      }
    } else {
      Write-Result 'failed' 'the new version did not start, and could not be removed' $null
      $cleanup = $false
    }
    Start-App
    if ($cleanup) {
      foreach ($name in 'old', 'failed', 'staged', 'download') {
        Remove-Item -LiteralPath (Join-Path $State $name) -Recurse -Force -ErrorAction SilentlyContinue
      }
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
foreach ($name in 'old', 'failed', 'staged', 'download', $Pending, 'started', 'booted', 'helper-started') {
  Remove-Item -LiteralPath (Join-Path $State $name) -Recurse -Force -ErrorAction SilentlyContinue
}
"""

_PLAIN_VERSION = re.compile(r"[0-9A-Za-z.+!_-]+")


#: What PowerShell reads as a single quote: the ASCII one and four typographic
#: ones. Inside a single-quoted string each is escaped by doubling it.
_PS_SINGLE_QUOTES = re.compile("['\u2018\u2019\u201a\u201b]")
_PLACEHOLDER = re.compile(r"@@([A-Z_]+)@@")


def _ps_quote(text: str) -> str:
    return "'" + _PS_SINGLE_QUOTES.sub(lambda m: m.group(0) * 2, str(text)) + "'"


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
            # `open` exits at once, so its pid may be reused before a rollback.
            "TRACK_LAUNCH": "0" if _is_open(plan.relaunch) else "1",
            "PENDING": PENDING,
        }
        template = _SH_HELPER
    # One pass, so a value that itself reads `@@NAME@@` stays as it is.
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def _is_open(relaunch: tuple[str, ...]) -> bool:
    """Whether ``relaunch`` goes through macOS's ``open``."""
    return bool(relaunch) and os.path.basename(relaunch[0]) == "open"


def _powershell() -> str:
    """Windows PowerShell 5.1, by absolute path rather than whatever ``PATH`` finds."""
    return os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )


def helper_command(script: Path, system: str) -> list[str]:
    """How to run the helper script on ``system``.

    On Windows the script travels as ``-EncodedCommand`` (its text in
    UTF-16-LE, base64): Group Policy can set an execution policy that
    refuses ``-File`` scripts, and ``-ExecutionPolicy Bypass`` does not
    override a policy set by Group Policy, whereas the policy does not apply
    to ``-EncodedCommand``. The ~5 KB script stays far under the 32,767
    character command-line limit.
    """
    if system == "win32":
        text = script.read_text(encoding="utf-8-sig")
        encoded = base64.b64encode(text.encode("utf-16-le")).decode("ascii")
        return [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-EncodedCommand",
            encoded,
        ]
    return ["/bin/sh", str(script)]


def start_swap(
    plan: SwapPlan,
    *,
    popen: Callable = subprocess.Popen,
    handshake_timeout_s: float = HANDSHAKE_TIMEOUT_S,
) -> None:
    """Record the attempt and start the helper, detached; the caller then exits.

    The helper's output goes to ``helper.log`` in the state folder, which
    stays after the attempt for a bug report. The script is written first and
    the attempt recorded after it, so nothing that can fail is left behind
    as an attempt "already under way". Returns only once the helper has
    written ``HELPER_STARTED``, its first act: a helper that antivirus
    stopped or that didn't parse would otherwise leave the app gone, nothing
    relaunched and the attempt blocking a retry. Then the helper is killed
    (if it is running at all) and the attempt forgotten, and the app stays.
    """
    pending = plan.state / PENDING
    marker = plan.state / HELPER_STARTED
    windows = plan.install.system == "win32"
    script = plan.state / ("helper.ps1" if windows else "helper.sh")
    if windows:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200
        )
        detach = {"creationflags": flags}
    else:
        detach = {"start_new_session": True}
    try:
        marker.unlink(missing_ok=True)
        # With a BOM: a human running helper.ps1 to diagnose it gets the same
        # reading in Windows PowerShell 5.1, which assumes the ANSI code page.
        script.write_text(
            helper_script(plan), encoding="utf-8-sig" if windows else "utf-8"
        )
        _write_json(
            pending,
            {
                "root": str(plan.install.root),
                "version": plan.version,
                "previous": plan.previous,
                "at": time.time(),
            },
        )
        with open(plan.state / "helper.log", "w", encoding="utf-8") as log:
            helper = popen(
                helper_command(script, plan.install.system),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=child_env(),
                **detach,
            )
    except (OSError, ValueError) as error:
        pending.unlink(missing_ok=True)
        raise UpdateFailed(
            "The helper that swaps the versions couldn't be started."
        ) from error
    if not _helper_started(marker, helper, handshake_timeout_s):
        try:
            helper.kill()
        except Exception:
            pass
        pending.unlink(missing_ok=True)
        raise UpdateFailed(
            "The helper that swaps the versions didn't start, so nothing was changed."
        )


def _helper_started(marker: Path, helper: object, timeout_s: float) -> bool:
    """Wait up to ``timeout_s`` for the helper's marker; stop early if it exited."""
    deadline = time.monotonic() + timeout_s
    while True:
        if marker.exists():
            return True
        poll = getattr(helper, "poll", None)
        exited = poll is not None and poll() is not None
        if exited or time.monotonic() >= deadline:
            return marker.exists()  # it may have written it on its way out
        time.sleep(0.05)


def clear_attempt(state: Path) -> None:
    """Remove what an earlier attempt left, keeping only ``helper.log``."""
    for name in _ATTEMPT_FOLDERS:
        shutil.rmtree(state / name, ignore_errors=True)
    for name in _ATTEMPT_FILES:
        (state / name).unlink(missing_ok=True)


def _same_root(recorded: object, root: Path) -> bool:
    """Whether ``pending.json``'s root names ``root`` — through a symlink or
    a firmlink too, so a relaunch by another spelling still reports in."""
    if not isinstance(recorded, str) or not recorded:
        return False
    try:
        if os.path.exists(recorded) and os.path.exists(root):
            return os.path.samefile(recorded, root)
    except OSError:
        pass
    return os.path.normcase(os.path.realpath(recorded)) == os.path.normcase(
        os.path.realpath(root)
    )


def _ours(state: Path, install: Install) -> bool:
    pending = _pending(state)
    return pending is not None and _same_root(pending.get("root"), install.root)


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
            (state / STARTED).write_text(
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
            (state / BOOTED).write_text("", encoding="utf-8")
            return
        cutoff = time.time() - STALE_AFTER_S
        for name in (*_ATTEMPT_FOLDERS, PENDING, STARTED, BOOTED, HELPER_STARTED):
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
        data = _read_json(state / RESULT)
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


def _short_reason(error: BaseException, limit: int = 160) -> str:
    """One sentence for people: the OS's own words (and the file) for an
    ``OSError``, else ``str(error)``, on one line and ending in a stop."""
    reason = getattr(error, "strerror", None)
    filename = getattr(error, "filename", None)
    if reason and filename:
        reason = f"{reason} ({os.path.basename(str(filename)) or filename})"
    reason = " ".join(str(reason or error or type(error).__name__).split())
    if len(reason) > limit:
        reason = reason[: limit - 1] + "…"
    return reason if reason.endswith((".", "…", "!", "?")) else reason + "."


#: The steps the About card and ``--update`` name, in order.
STEPS = ("Downloading", "Checking it", "Testing the new version", "Restarting")


def prepare(
    check: UpdateCheck,
    install: Install | None,
    *,
    allow_file: bool = False,
    run: Callable = subprocess.run,
    opener: Callable | None = None,
    machine: str | None = None,
    on_step: Callable[[str], None] | None = None,
) -> SwapPlan:
    """Steps 1-4: refuse, download, stage and self-test — the swap is the caller's.

    Raises :class:`UpdateFailed` (the install untouched) or, from inside a
    progress task that was cancelled, ``progress.Cancelled``. Anything else
    that goes wrong on the way — a folder that can't be written, a file that
    can't be read — is an :class:`UpdateFailed` too, never a raw exception.
    """
    reason = refusal(check, install, run=run, machine=machine)
    if reason is not None:
        raise UpdateFailed(reason)

    def step(index: int) -> None:
        progress.step_to(index)
        if on_step is not None:
            on_step(STEPS[index])

    try:
        state = state_dir(install)
        asset = asset_for(check, install, machine=machine)
        clear_attempt(state)
        step(0)
        archive = download(
            asset, state / "download", allow_file=allow_file, opener=opener
        )
        step(1)
        staged = stage(archive, state, install, run=run)
        step(2)
        self_test(staged, install.system, run=run)
    except (OSError, ValueError) as error:  # UnicodeDecodeError is a ValueError
        raise UpdateFailed(
            f"Preparing the update failed: {_short_reason(error)}"
        ) from error
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
