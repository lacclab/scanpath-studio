"""The commit gate logs what a session actually ran, not what it read about.

`.claude/hooks/commit-gate.sh` runs before every `git commit` and logs whether
the message has a `Verified:` trailer and whether the session ran the harness
or the tests. The project instructions mention `scripts/verify_change.py` and
`pytest`, and they are part of every session's transcript, so the log must
count only the commands the session ran.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "commit-gate.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("sh") is None,
    reason="the hook needs sh and jq",
)


def _user_text(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _bash_call(command: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": command}}
            ],
        },
    }


def _run_gate(tmp_path: Path, events: list[dict], command: str) -> str:
    """Run the hook on ``command`` with ``events`` as the transcript; return the log line."""
    (tmp_path / ".claude").mkdir(exist_ok=True)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    payload = {
        "session_id": "test-session",
        "transcript_path": str(transcript),
        "tool_input": {"command": command},
    }
    subprocess.run(
        ["sh", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        check=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "CLAUDE_PROJECT_DIR": str(tmp_path),
        },
    )
    return (
        (tmp_path / ".claude" / "commit-gate.log")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )


COMMIT = "git commit -m 'Fix a thing\n\nVerified: tests'"
INSTRUCTIONS = (
    "Run `uv run --extra test python scripts/verify_change.py` and "
    "`uv run --extra test pytest -n auto` before calling it done."
)


def test_instruction_text_is_not_a_run(tmp_path):
    line = _run_gate(tmp_path, [_user_text(INSTRUCTIONS)], COMMIT)
    assert line.endswith("ran=none")


@pytest.mark.parametrize(
    "command",
    [
        "uv run --extra test python scripts/verify_change.py",
        "cd app && uv run --extra test python scripts/verify_change.py --ui essentials",
        ".venv/bin/python scripts/verify_change.py --out-dir out",
    ],
)
def test_a_harness_command_counts(tmp_path, command):
    events = [_user_text(INSTRUCTIONS), _bash_call(command)]
    assert _run_gate(tmp_path, events, COMMIT).endswith("ran=harness")


@pytest.mark.parametrize(
    "command",
    [
        "uv run --extra test pytest tests/test_data.py -q",
        "SCANPATH_STUDIO_PERSIST=0 /usr/bin/time -p uv run --extra test pytest -n auto",
        ".venv/bin/python -m pytest tests/test_data.py",
        "pytest -q",
    ],
)
def test_a_pytest_command_counts_as_tests(tmp_path, command):
    assert _run_gate(tmp_path, [_bash_call(command)], COMMIT).endswith("ran=tests")


@pytest.mark.parametrize(
    "command",
    [
        "wc -l scripts/verify_change.py",
        'grep -n "pytest\\|ruff" .github/workflows/ci.yml',
        "sed -n 1,40p tests/conftest.py | grep pytest",
        "cat .claude/skills/verify/SKILL.md",
    ],
)
def test_reading_about_a_tool_is_not_running_it(tmp_path, command):
    assert _run_gate(tmp_path, [_bash_call(command)], COMMIT).endswith("ran=none")


def test_the_commit_command_itself_is_not_a_run(tmp_path):
    """The commit being checked is already in the transcript, and its message
    may name what ran."""
    events = [_bash_call("git commit -m 'x\n\nVerified: pytest, verify_change.py'")]
    assert _run_gate(tmp_path, events, COMMIT).endswith("ran=none")


@pytest.mark.parametrize(
    ("command", "trailer"),
    [(COMMIT, "trailer=yes"), ("git commit -m 'Fix a thing'", "trailer=no")],
)
def test_the_trailer_is_detected(tmp_path, command, trailer):
    assert f"\t{trailer}\t" in _run_gate(tmp_path, [], command)
