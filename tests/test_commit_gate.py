"""The commit gate logs what a session actually ran, not what it read about.

`.claude/hooks/commit-gate.sh` runs before every `git commit` and logs whether
the message has a `Verified:` trailer and whether the session ran the harness
or the tests. The project instructions mention `scripts/verify_change.py` and
`pytest`, and they are part of every session's transcript, so the log must
count only the commands the session ran.
"""

from __future__ import annotations

import json
import os
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


def _write_transcript(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _run_gate(
    tmp_path: Path,
    events: list[dict],
    command: str,
    *,
    subagent_events: list[dict] | None = None,
) -> str:
    """Run the hook on ``command`` with ``events`` as the transcript; return the log line."""
    (tmp_path / ".claude").mkdir(exist_ok=True)
    transcript = tmp_path / "session.jsonl"
    _write_transcript(transcript, events)
    if subagent_events is not None:
        _write_transcript(
            tmp_path / "session" / "subagents" / "agent-1.jsonl", subagent_events
        )
    payload = {
        "session_id": "test-session",
        "transcript_path": str(transcript),
        "tool_input": {"command": command},
    }
    # The hook needs jq wherever this machine keeps it.
    path = os.pathsep.join(
        [os.path.dirname(shutil.which("jq")), "/usr/bin", "/bin", "/usr/local/bin"]
    )
    subprocess.run(
        ["sh", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        check=True,
        env={"PATH": path, "CLAUDE_PROJECT_DIR": str(tmp_path)},
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
        'S="$(mktemp -d)" uv run --extra test pytest -q',
        "uv run --extra=test pytest",
        "timeout 900 uv run pytest -x",
        "python -X dev -m pytest",
        "uv run --env-file .env pytest",
        "uv --directory app run pytest",
        "cd app\nuv run --extra test \\\n  pytest -n auto",
        'git commit -m "don\'t"; uv run pytest -q; echo "that\'s it"',
        "for f in a b; do uv run pytest $f; done",
        "if uv run pytest; then echo ok; fi",
        "! uv run pytest",
        "{ uv run pytest; }",
        "exec uv run pytest",
        "env -u PYTHONPATH uv run pytest",
        "nice -n 5 uv run pytest",
        "ls tests | xargs -n1 uv run pytest",
        "uv run -p 3.12 pytest",
    ],
)
def test_a_pytest_command_counts_as_tests(tmp_path, command):
    assert _run_gate(tmp_path, [_bash_call(command)], COMMIT).endswith("ran=tests")


def test_a_truncated_line_does_not_hide_the_rest(tmp_path):
    """A transcript can be cut mid-line while it is written; later lines count."""
    (tmp_path / ".claude").mkdir(exist_ok=True)
    transcript = tmp_path / "session.jsonl"
    lines = [json.dumps(_user_text("hi")), '{"type": "assistant", "mess']
    lines.append(json.dumps(_bash_call("uv run pytest -q")))
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "session_id": "s",
        "transcript_path": str(transcript),
        "tool_input": {"command": COMMIT},
    }
    path = os.pathsep.join([os.path.dirname(shutil.which("jq")), "/usr/bin", "/bin"])
    subprocess.run(
        ["sh", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        check=True,
        env={"PATH": path, "CLAUDE_PROJECT_DIR": str(tmp_path)},
    )
    log = (tmp_path / ".claude" / "commit-gate.log").read_text(encoding="utf-8")
    assert log.splitlines()[-1].endswith("ran=tests")


@pytest.mark.parametrize(
    "command",
    ["git -C app commit -m 'Fix'", "git -c user.name=x commit -m 'Fix'"],
)
def test_a_commit_in_another_directory_is_logged(tmp_path, command):
    assert "\ttrailer=no\t" in _run_gate(tmp_path, [], command)


def test_a_run_in_a_subagent_counts(tmp_path):
    """A subagent's commands are in its own transcript, beside the session's."""
    line = _run_gate(
        tmp_path,
        [_user_text(INSTRUCTIONS)],
        COMMIT,
        subagent_events=[_bash_call("uv run --extra test pytest tests/x.py")],
    )
    assert line.endswith("ran=tests")


@pytest.mark.parametrize(
    "command",
    [
        "wc -l scripts/verify_change.py",
        'grep -n "pytest\\|ruff" .github/workflows/ci.yml',
        "sed -n 1,40p tests/conftest.py | grep pytest",
        "cat .claude/skills/verify/SKILL.md",
        "grep -E 'foo|pytest -n auto' notes.md",
        "cat > run.sh <<'EOF'\npytest -q\nEOF",
        "gh pr create --title t --body 'Ran:\npytest -n auto'",
        "cat \\\n  scripts/verify_change.py",
        "printf '%s\\n' 'x' '(pytest -q)' > msg.txt",
        "gh pr create --body \"It's ok\" && gh pr comment --body 'Ran (pytest -q)'",
    ],
)
def test_reading_about_a_tool_is_not_running_it(tmp_path, command):
    assert _run_gate(tmp_path, [_bash_call(command)], COMMIT).endswith("ran=none")


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x\n\nVerified: pytest, verify_change.py'",
        "git -C app commit -m 'x\npytest -n auto'",
    ],
)
def test_the_commit_command_itself_is_not_a_run(tmp_path, command):
    """The commit being checked is already in the transcript, and its message
    may name what ran."""
    assert _run_gate(tmp_path, [_bash_call(command)], COMMIT).endswith("ran=none")


@pytest.mark.parametrize(
    ("command", "trailer"),
    [(COMMIT, "trailer=yes"), ("git commit -m 'Fix a thing'", "trailer=no")],
)
def test_the_trailer_is_detected(tmp_path, command, trailer):
    assert f"\t{trailer}\t" in _run_gate(tmp_path, [], command)
