"""Smoke test for the frozen desktop bundle (ENG-15).

Usage:
    python desktop/smoke_test.py [path/to/ScanpathStudio[.app|.exe]]

Without an argument it looks for the artifact CI actually ships, relative to the
repo root: ``dist/ScanpathStudio.app`` on macOS, else
``dist/ScanpathStudio/ScanpathStudio`` (with ``.exe`` on Windows). Taking the
``.app`` matters — PyInstaller's onedir ``COLLECT`` leaves
``dist/ScanpathStudio/`` in place *beside* the bundle it builds from it, so a
path-based default that ignores the ``.app`` would verify and boot the copy that
is never released, and pass. Two phases:

1. ``--selfcheck``: the frozen process loads the bundled sample and builds a
   figure headless — catches missing hidden imports / data files.
2. Boot: launch the server with the browser suppressed, poll the Streamlit
   health endpoint until it answers ``ok``, require HTTP 200 on ``/``.

Exit code 0 = both passed. Stdlib only (runs on the bare CI runners; the
``launcher`` import is the sibling module, itself stdlib-only at import time).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from launcher import _env_flag, _free_port

BOOT_TIMEOUT_S = 180.0
SELFCHECK_TIMEOUT_S = 300.0


def _default_binary() -> Path:
    """The artifact CI ships: the ``.app`` on macOS, else the onedir executable."""
    repo_root = Path(__file__).resolve().parent.parent
    dist = repo_root / "dist"
    if sys.platform == "darwin":
        return dist / "ScanpathStudio.app"
    name = "ScanpathStudio.exe" if sys.platform.startswith("win") else "ScanpathStudio"
    return dist / "ScanpathStudio" / name


def _executable(target: Path) -> Path:
    """The runnable binary inside ``target`` — which is a bundle on macOS.

    Run directly rather than through ``open``: the child then inherits this
    process's stdout and is reaped by ``proc.kill()``, neither of which holds for
    a Launch Services hand-off.
    """
    if target.suffix == ".app":
        return target / "Contents" / "MacOS" / target.stem
    if target.is_dir():
        # A onedir folder, not a bundle. Running it would fail inside Popen with
        # a bare PermissionError; name the real problem instead.
        raise SystemExit(
            f"[smoke] {target} is a directory but not a .app bundle — "
            "pass the executable inside it, or the .app itself."
        )
    return target


def _child_env(**overrides: str) -> dict[str, str]:
    """Environment for a launched bundle, with the .app's own behaviours off.

    Both phases run the executable *inside* the bundle, which is precisely the
    launcher's cue to redirect output to ``~/Library/Logs`` and to arm the
    idle-exit watcher (ENG-21). Neither belongs in a test: the redirect would
    swallow the very output a failure is diagnosed from, and it would also write
    into a developer's real log directory on a local run.
    """
    env = dict(os.environ)
    env["SCANPATH_DESKTOP_NO_LOG_FILE"] = "1"
    env["SCANPATH_DESKTOP_IDLE_EXIT_S"] = "0"
    env.update(overrides)
    return env


def _run_selfcheck(binary: Path) -> None:
    print(f"[smoke] selfcheck: {binary}")
    result = subprocess.run(
        [str(binary), "--selfcheck"],
        capture_output=True,
        text=True,
        timeout=SELFCHECK_TIMEOUT_S,
        # Same reason as the boot test below, and easy to miss here: the binary
        # is the one *inside* the .app, so the launcher would redirect to
        # ~/Library/Logs before reaching the --selfcheck branch — and
        # capture_output makes stdout a pipe, so the isatty() escape does not
        # fire. The traceback this phase exists to surface would land in a file
        # on a throwaway runner, leaving a red CI run with no reason attached.
        env=_child_env(),
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"[smoke] selfcheck FAILED (exit {result.returncode})")
    print("[smoke] selfcheck passed")


def _verify_macos_signature(binary: Path) -> None:
    """Require a valid signature on macOS bundles — ad-hoc or Developer ID.

    ``--deep`` is right here and wrong for *signing*: verification of a bundle
    should walk the nested code, which is most of the 500 MB.
    """
    if sys.platform != "darwin":
        return
    print(f"[smoke] verifying macOS code signature: {binary}")
    result = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(binary)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "[smoke] macOS signature FAILED:\n" + result.stdout + result.stderr
        )
    print("[smoke] macOS signature passed")


def _verify_notarization(bundle: Path) -> None:
    """Assert the ticket is stapled and Gatekeeper accepts it (ENG-21).

    Behind ``SCANPATH_EXPECT_NOTARIZED`` rather than automatic: an unsigned fork
    or local build has no ticket and must still pass the rest of this test. CI
    sets it exactly on the leg that has the signing secrets.

    ``stapler validate`` is the load-bearing check — it proves a ticket is
    physically attached, which is what makes a first launch work offline.
    ``spctl`` is weaker than it looks on the build machine (no quarantine xattr,
    and the local ticket database may already know the app), so it is a
    corroboration, not the proof.
    """
    if sys.platform != "darwin" or not _env_flag("SCANPATH_EXPECT_NOTARIZED"):
        return
    print(f"[smoke] validating stapled notarization ticket: {bundle}")
    stapled = subprocess.run(
        ["xcrun", "stapler", "validate", str(bundle)],
        capture_output=True,
        text=True,
    )
    if stapled.returncode != 0:
        raise SystemExit(
            "[smoke] stapler validate FAILED:\n" + stapled.stdout + stapled.stderr
        )

    assessed = subprocess.run(
        ["spctl", "--assess", "--type", "exec", "-vvv", str(bundle)],
        capture_output=True,
        text=True,
    )
    output = assessed.stdout + assessed.stderr
    if assessed.returncode != 0:
        raise SystemExit("[smoke] spctl rejected the bundle:\n" + output)
    if "Notarized Developer ID" not in output:
        raise SystemExit(
            "[smoke] spctl accepted the bundle but not as notarized:\n" + output
        )
    print("[smoke] notarization validated (stapled, Notarized Developer ID)")


def _get(url: str, timeout: float = 5.0):
    return urllib.request.urlopen(url, timeout=timeout)


def _run_boot_test(binary: Path) -> None:
    port = _free_port()
    env = _child_env(
        SCANPATH_DESKTOP_NO_BROWSER="1",
        SCANPATH_DESKTOP_PORT=str(port),
    )

    print(f"[smoke] booting server on port {port}: {binary}")
    # Server output goes to a file, not a PIPE: an undrained pipe would block
    # the server once its buffer fills, and the output must survive a kill so
    # a failed boot is diagnosable in CI.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(
            [str(binary)],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def server_log() -> str:
            log.flush()
            log.seek(0)
            return log.read()

        try:
            deadline = time.monotonic() + BOOT_TIMEOUT_S
            health_url = f"http://127.0.0.1:{port}/_stcore/health"
            while True:
                if proc.poll() is not None:
                    raise SystemExit(
                        f"[smoke] server exited early (exit {proc.returncode}):\n"
                        f"{server_log()}"
                    )
                if time.monotonic() > deadline:
                    raise SystemExit(
                        f"[smoke] server not healthy after {BOOT_TIMEOUT_S:.0f}s:\n"
                        f"{server_log()}"
                    )
                try:
                    with _get(health_url) as response:
                        if response.status == 200 and b"ok" in response.read().lower():
                            break
                except OSError:
                    pass
                time.sleep(1.0)
            print("[smoke] health endpoint answered ok")

            with _get(f"http://127.0.0.1:{port}/") as response:
                if response.status != 200:
                    raise SystemExit(f"[smoke] GET / returned HTTP {response.status}")
            print("[smoke] root page served (HTTP 200)")
        finally:
            proc.kill()
            proc.wait(timeout=30)


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_binary()
    if not target.exists():
        raise SystemExit(f"[smoke] build artifact not found: {target}")
    # Signature and ticket belong to the *bundle*; running belongs to the
    # executable inside it. Off macOS the two are the same path.
    _verify_macos_signature(target)
    _verify_notarization(target)
    binary = _executable(target)
    if not binary.exists():
        raise SystemExit(f"[smoke] executable not found: {binary}")
    _run_selfcheck(binary)
    _run_boot_test(binary)
    print("[smoke] all checks passed")


if __name__ == "__main__":
    main()
