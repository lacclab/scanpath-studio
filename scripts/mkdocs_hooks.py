"""Small hermetic executable-fence hook used by the tutorials (UX-21).

Mark a fence ``python exec="true"``. During ``mkdocs build`` it is executed
against the bundled repository data and its real stdout is inserted immediately
below the highlighted source. Marked fences on a page share state, like notebook
cells. Network sockets are disabled and every cell has a short timeout.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

_EXEC_FENCE = re.compile(
    r"^(?P<indent>[ \t]*)```python\s+exec=(?:\"true\"|'true')\s*\n"
    r"(?P<code>.*?)\n(?P=indent)```",
    re.DOTALL | re.MULTILINE,
)
_ROOT = Path(__file__).resolve().parent.parent


def _run_cell(history: list[str], code: str, page_name: str) -> str:
    previous = "\n\n".join(history)
    script = f"""
import contextlib
import io
import socket

def _offline(*args, **kwargs):
    raise RuntimeError("network access is disabled while building tutorials")

socket.create_connection = _offline
socket.socket.connect = _offline

with contextlib.redirect_stdout(io.StringIO()):
    exec(compile({previous!r}, {page_name!r}, "exec"), globals())
exec(compile({code!r}, {page_name!r}, "exec"), globals())
"""
    env = dict(os.environ)
    env.update({"MPLBACKEND": "Agg", "PYTHONHASHSEED": "0"})
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Executable tutorial snippet failed in {page_name}:\n{result.stderr}"
        )
    return result.stdout.rstrip()


def on_page_markdown(markdown, page, config, files):
    """MkDocs hook: replace opt-in executable fences with source + live stdout."""
    history: list[str] = []

    def replace(match: re.Match) -> str:
        indent = match.group("indent")
        code = textwrap.dedent(match.group("code"))
        output = _run_cell(history, code, page.file.src_uri)
        history.append(code)
        rendered = f"```python\n{code}\n```"
        if output:
            rendered += f"\n\n```text\n{output}\n```"
        return "\n".join(
            indent + line if line else line for line in rendered.splitlines()
        )

    return _EXEC_FENCE.sub(replace, markdown)
