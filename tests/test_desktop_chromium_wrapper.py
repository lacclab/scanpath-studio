"""The frozen launcher stands in for choreographer's browser pipe wrapper.

On macOS and Linux, choreographer starts the browser that renders image exports
as ``sys.executable _unix_pipe_chromium_wrapper.py <browser> …``. In the desktop
bundle ``sys.executable`` is the launcher, so it has to act as that wrapper:
started as a second copy of the app instead, the GIF/PDF export would wait
forever.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from desktop import launcher

LAUNCHER = Path(launcher.__file__)
WRAPPER = "/somewhere/choreographer/browsers/_unix_pipe_chromium_wrapper.py"


def test_the_wrapper_call_is_recognised(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ScanpathStudio", WRAPPER, "chrome", "--x"])
    assert launcher._chromium_pipe_wrapper_cli() == ["chrome", "--x"]


@pytest.mark.parametrize(
    "argv",
    [
        ["ScanpathStudio"],
        ["ScanpathStudio", "--selfcheck"],
        ["ScanpathStudio", WRAPPER],
    ],
)
def test_an_ordinary_launch_is_not_the_wrapper(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    assert launcher._chromium_pipe_wrapper_cli() is None


@pytest.mark.skipif(sys.platform.startswith("win"), reason="the wrapper is POSIX-only")
def test_the_browser_gets_our_stdin_and_stdout_on_fds_3_and_4():
    """A stand-in browser reads the DevTools pipe on fd 3 and answers on fd 4."""
    browser = [
        sys.executable,
        "-c",
        "import os; os.write(4, os.read(3, 100).upper())",
    ]
    done = subprocess.run(
        [sys.executable, str(LAUNCHER), WRAPPER, *browser],
        input=b"devtools",
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == b"DEVTOOLS{bye}\n"
