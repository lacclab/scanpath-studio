"""Unreleased changelog entries are one file each in ``changelog.d/`` (ENG-86)."""

from __future__ import annotations

import importlib.util
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


def test_a_fragment_renders_under_its_group_with_its_ids(tmp_path):
    _write(tmp_path, "UX-10.fixed.md", "A fix")
    _write(tmp_path, "UX-9.added.md", "A feature")
    _write(tmp_path, "AN-32+UX-176.added.md", "Two IDs")
    fragments, errors = changelog_fragments.load(tmp_path)
    assert errors == []
    assert changelog_fragments.render(fragments) == (
        "### Added\n- Two IDs (AN-32, UX-176)\n- A feature (UX-9)\n\n"
        "### Fixed\n- A fix (UX-10)"
    )


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("UX-1.md", "no group"),
        ("UX-1.improved.md", "unknown group"),
        ("ux-1.fixed.md", "lower-case ID"),
        ("UX-1.fixed.md", ""),
        ("UX-1.fixed.md", "- a bullet"),
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
    _write(fragments, "UX-1.fixed.md", "A fix")
    _write(fragments, "README.md", "kept")

    assert changelog_fragments.release("1.1.0", "2026-02-02", changelog, fragments) == 1
    assert changelog.read_text() == (
        "# Changelog\n\nPreamble.\n\n## [1.1.0] - 2026-02-02\n\n"
        "### Fixed\n- A fix (UX-1)\n\n## [1.0.0] - 2026-01-01\n"
    )
    assert [p.name for p in fragments.iterdir()] == ["README.md"]
    with pytest.raises(SystemExit):
        changelog_fragments.release("1.1.0", "2026-02-02", changelog, fragments)
