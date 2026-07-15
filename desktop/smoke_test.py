"""Smoke test for the frozen desktop bundle (ENG-15).

Usage:
    python desktop/smoke_test.py [path/to/ScanpathStudio[.exe]]

Without an argument it looks for ``dist/ScanpathStudio/ScanpathStudio`` (with
``.exe`` on Windows) relative to the repo root. Two phases:

1. ``--selfcheck``: the frozen process loads the bundled sample and builds a
   figure headless — catches missing hidden imports / data files.
2. Boot: launch the server with the browser suppressed, poll the Streamlit
   health endpoint until it answers ``ok``, require HTTP 200 on ``/``.

Exit code 0 = both passed. Stdlib only (runs on the bare CI runners).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BOOT_TIMEOUT_S = 180.0
SELFCHECK_TIMEOUT_S = 300.0


def _default_binary() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    name = "ScanpathStudio.exe" if sys.platform.startswith("win") else "ScanpathStudio"
    return repo_root / "dist" / "ScanpathStudio" / name


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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


def _get(url: str, timeout: float = 5.0):
    return urllib.request.urlopen(url, timeout=timeout)


def _run_boot_test(binary: Path) -> None:
    port = _free_port()
    env = dict(os.environ)
    env["SCANPATH_DESKTOP_NO_BROWSER"] = "1"
    env["SCANPATH_DESKTOP_PORT"] = str(port)

    print(f"[smoke] booting server on port {port}: {binary}")
    proc = subprocess.Popen(
        [str(binary)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        health_url = f"http://127.0.0.1:{port}/_stcore/health"
        while True:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise SystemExit(
                    f"[smoke] server exited early (exit {proc.returncode}):\n{out}"
                )
            if time.monotonic() > deadline:
                raise SystemExit(
                    f"[smoke] server not healthy after {BOOT_TIMEOUT_S:.0f}s"
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
    _run_selfcheck(binary)
    _run_boot_test(binary)
    print("[smoke] all checks passed")


if __name__ == "__main__":
    main()
