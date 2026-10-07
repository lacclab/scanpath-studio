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


def _started_pid(state: Path) -> int | None:
    """The pid a relaunched launcher last wrote to ``started``, if any is left."""
    try:
        return int((state / desktop_update.STARTED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
    try:
        ran = subprocess.run(
            [str(executable), "--update"], env=env, timeout=UPDATE_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"[update-e2e] --update did not finish within {UPDATE_TIMEOUT_S:.0f}s; "
            "helper log:\n" + _helper_log(state)
        ) from None
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
            # Best effort: the helper relaunched the old version, which the
            # smoke test after this must not find holding the port or files.
            _stop(_started_pid(state))
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
