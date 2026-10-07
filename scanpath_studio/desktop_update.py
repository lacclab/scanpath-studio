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
