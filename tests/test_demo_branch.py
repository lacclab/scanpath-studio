"""Advance the demo without overwriting deployment-only commits."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/advance_demo_branch.sh"


def _git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


@pytest.mark.parametrize("deployment_commit", [False, True, "conflict"])
def test_demo_keeps_deployment_changes(tmp_path, deployment_commit):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(tmp_path, "clone", str(remote), str(repo))
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "app.txt").write_text("old")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Initial release")
    _git(repo, "branch", "stable")
    _git(repo, "push", "origin", "stable")
    if deployment_commit:
        _git(repo, "switch", "stable")
        file_name = "app.txt" if deployment_commit == "conflict" else "deployment.txt"
        (repo / file_name).write_text("keep me")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "Deployment setup")
        _git(repo, "push", "origin", "stable")
        _git(repo, "switch", "-")
    previous = _git(repo, "rev-parse", "origin/stable")
    (repo / "app.txt").write_text("new")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "New release")
    release = _git(repo, "rev-parse", "HEAD")
    result = subprocess.run(
        ["sh", str(SCRIPT), release], cwd=repo, check=False, capture_output=True
    )
    if deployment_commit == "conflict":
        assert result.returncode != 0
        assert _git(remote, "rev-parse", "stable") == previous
        return
    assert result.returncode == 0, result.stderr
    assert _git(remote, "show", "stable:app.txt") == "new"
    for parent in (previous, release):
        _git(remote, "merge-base", "--is-ancestor", parent, "stable")
    if deployment_commit:
        assert _git(remote, "show", "stable:deployment.txt") == "keep me"
