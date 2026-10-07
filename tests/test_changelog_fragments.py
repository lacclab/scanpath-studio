"""Unreleased changelog entries are one file each in ``changelog.d/`` (ENG-86)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "changelog_fragments", ROOT / "scripts" / "changelog_fragments.py"
)
changelog_fragments = importlib.util.module_from_spec(_SPEC)
# Registered before it runs: its dataclass looks its own module up.
sys.modules["changelog_fragments"] = changelog_fragments
_SPEC.loader.exec_module(changelog_fragments)


def test_every_fragment_in_the_repository_is_well_formed():
    _, errors = changelog_fragments.load()
    assert errors == []


def _write(directory: Path, name: str, text: str) -> None:
    (directory / name).write_text(text + "\n", encoding="utf-8")


def _link(number: int) -> str:
    return f"[#{number}](https://github.com/lacclab/scanpath-studio/issues/{number})"


def test_a_fragment_renders_under_its_group_with_its_issues(tmp_path):
    _write(tmp_path, "10.fixed.md", "A fix")
    _write(tmp_path, "9.added.md", "A feature")
    _write(tmp_path, "3+12.added.md", "Two issues")
    fragments, errors = changelog_fragments.load(tmp_path)
    assert errors == []
    assert changelog_fragments.render(fragments) == (
        f"### Added\n- Two issues ({_link(3)}, {_link(12)})\n"
        f"- A feature ({_link(9)})\n\n### Fixed\n- A fix ({_link(10)})"
    )


def test_a_slug_fragment_cites_the_pr_that_merged_it(tmp_path, monkeypatch):
    _write(tmp_path, "trial-picker-ids.changed.md", "Merged")
    _write(tmp_path, "UX-190.changed.md", "Named the old way")
    _write(tmp_path, "pending.changed.md", "Not merged yet")
    merged = {"trial-picker-ids.changed.md": 327, "UX-190.changed.md": 301}
    monkeypatch.setattr(changelog_fragments, "merged_pr", lambda p: merged.get(p.name))
    fragments, errors = changelog_fragments.load(tmp_path)
    assert errors == []
    assert changelog_fragments.render(fragments) == (
        f"### Changed\n- Named the old way ({_link(301)})\n"
        f"- Merged ({_link(327)})\n- Not merged yet"
    )


def test_merged_pr_reads_the_squash_merge_subject(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    _write(tmp_path, "a-change.fixed.md", "A fix")
    git("add", ".")
    git("commit", "-qm", "Fix the thing (#42)")
    assert changelog_fragments.merged_pr(tmp_path / "a-change.fixed.md") == 42
    _write(tmp_path, "unmerged.fixed.md", "Another")
    git("add", ".")
    git("commit", "-qm", "work in progress")
    assert changelog_fragments.merged_pr(tmp_path / "unmerged.fixed.md") is None


def test_merged_pr_reads_a_pr_landed_as_a_merge_commit(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    _write(tmp_path, "README", "x")
    git("add", ".")
    git("commit", "-qm", "start")
    git("checkout", "-qb", "feature")
    _write(tmp_path, "a-change.fixed.md", "A fix")
    git("add", ".")
    git("commit", "-qm", "Fix the thing")
    git("checkout", "-q", "main")
    git(
        "merge",
        "-q",
        "--no-ff",
        "-m",
        "Merge pull request #397 from x/feature",
        "feature",
    )
    # a later merge of main into some branch is a merge too, and not the PR
    git("checkout", "-qb", "later")
    _write(tmp_path, "other", "y")
    git("add", ".")
    git("commit", "-qm", "other work")
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #400 from x/later", "main")
    assert changelog_fragments.merged_pr(tmp_path / "a-change.fixed.md") == 397


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("12.md", "no group"),
        ("12.improved.md", "unknown group"),
        ("-slug.fixed.md", "leading dash"),
        ("12+.fixed.md", "dangling plus"),
        ("12.fixed.md", ""),
        ("12.fixed.md", "- a bullet"),
    ],
)
def test_a_malformed_fragment_is_reported(tmp_path, name, text):
    _write(tmp_path, name, text)
    fragments, errors = changelog_fragments.load(tmp_path)
    assert fragments == [] and len(errors) == 1


def test_release_writes_the_section_above_the_last_release_and_clears_the_fragments(
    tmp_path,
):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\nPreamble.\n\n## [1.0.0] - 2026-01-01\n")
    fragments = tmp_path / "changelog.d"
    fragments.mkdir()
    _write(fragments, "1.fixed.md", "A fix")
    _write(fragments, "README.md", "kept")

    assert changelog_fragments.release("1.1.0", "2026-02-02", changelog, fragments) == 1
    assert changelog.read_text() == (
        "# Changelog\n\nPreamble.\n\n## [1.1.0] - 2026-02-02\n\n"
        f"### Fixed\n- A fix ({_link(1)})\n\n## [1.0.0] - 2026-01-01\n"
    )
    assert [p.name for p in fragments.iterdir()] == ["README.md"]
    with pytest.raises(SystemExit):
        changelog_fragments.release("1.1.0", "2026-02-02", changelog, fragments)


def test_release_refuses_a_slug_with_no_merged_pr(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n")
    fragments = tmp_path / "changelog.d"
    fragments.mkdir()
    _write(fragments, "not-merged.fixed.md", "A fix")
    with pytest.raises(SystemExit, match="not-merged.fixed.md"):
        changelog_fragments.release("1.1.0", "2026-02-02", changelog, fragments)
    assert (fragments / "not-merged.fixed.md").exists()
