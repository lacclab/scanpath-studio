"""Smoke test for the frozen desktop bundle (ENG-15).

Usage:
    python desktop/smoke_test.py [path/to/ScanpathStudio[.exe]]

Without an argument it looks for ``dist/ScanpathStudio/ScanpathStudio`` (with
``.exe`` on Windows) relative to the repo root. Two phases:

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
from launcher import _free_port  # noqa: E402

BOOT_TIMEOUT_S = 180.0
SELFCHECK_TIMEOUT_S = 300.0


def _default_binary() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    name = "ScanpathStudio.exe" if sys.platform.startswith("win") else "ScanpathStudio"
    return repo_root / "dist" / "ScanpathStudio" / name


def _run_selfcheck(binary: Path) -> None:
    print(f"[smoke] selfcheck: {binary}")
    result = subprocess.run(
        [str(binary), "--selfcheck"],
        capture_output=True,
        text=True,
        timeout=SELFCHECK_TIMEOUT_S,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"[smoke] selfcheck FAILED (exit {result.returncode})")
    print("[smoke] selfcheck passed")


def _verify_macos_signature(binary: Path) -> None:
    """Require the CI's ENG-19 ad-hoc signature on macOS bundles."""
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


def _get(url: str, timeout: float = 5.0):
    return urllib.request.urlopen(url, timeout=timeout)


def _run_boot_test(binary: Path) -> None:
    port = _free_port()
    env = dict(os.environ)
    env["SCANPATH_DESKTOP_NO_BROWSER"] = "1"
    env["SCANPATH_DESKTOP_PORT"] = str(port)

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
    binary = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_binary()
    if not binary.exists():
        raise SystemExit(f"[smoke] binary not found: {binary}")
    _verify_macos_signature(binary)
    _run_selfcheck(binary)
    _run_boot_test(binary)
    print("[smoke] all checks passed")


if __name__ == "__main__":
    main()
