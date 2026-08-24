"""Release notes must fit where they are posted.

`v0.29.0`'s changelog section is 172,795 characters — six months of work in one
release — and GitHub rejects a release body over 125,000, so the tag published
to PyPI and then failed to produce a release. Slack's ceiling is lower still.

The changelog's two-tier shape (ENG-34) is what makes this recoverable: a
headline list per group, then a `### Details` subsection. The headlines are the
half written to be pasted somewhere, so when the whole section will not fit,
they are what survives.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "changelog_notes",
    Path(__file__).resolve().parents[1] / "scripts" / "changelog_notes.py",
)
changelog_notes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(changelog_notes)
extract = changelog_notes.extract

DETAIL = "  Something worth saying at length about the change. " * 40
CHANGELOG = f"""# Changelog

## [9.9.0] - 2026-08-21

### Added
- **A short headline** (ABC-1)
- **Another headline** (ABC-2)

### Details

#### Added
- **A short headline** (ABC-1) — {DETAIL}
- **Another headline** (ABC-2) — {DETAIL}

## [9.8.0] - 2026-08-01

### Added
- **An older release** (ABC-0)
"""


class TestNoCap:
    def test_returns_the_whole_section_by_default(self):
        notes = extract(CHANGELOG, "9.9.0", "markdown")
        assert "### Details" in notes
        assert DETAIL.strip()[:30] in notes

    def test_stops_at_the_next_release(self):
        assert "An older release" not in extract(CHANGELOG, "9.9.0", "markdown")


class TestCap:
    def test_a_section_under_the_cap_is_untouched(self):
        assert extract(CHANGELOG, "9.9.0", "markdown", max_chars=1_000_000) == extract(
            CHANGELOG, "9.9.0", "markdown"
        )

    def test_an_oversized_section_drops_the_details_half(self):
        notes = extract(CHANGELOG, "9.9.0", "markdown", max_chars=2000)
        assert "### Details" not in notes
        assert "**A short headline** (ABC-1)" in notes
        assert "**Another headline** (ABC-2)" in notes

    def test_the_result_fits(self):
        assert len(extract(CHANGELOG, "9.9.0", "markdown", max_chars=2000)) <= 2000

    def test_it_says_where_the_rest_went(self):
        notes = extract(CHANGELOG, "9.9.0", "markdown", max_chars=2000)
        assert "changelog" in notes.lower()

    def test_it_links_the_full_changelog_when_given_a_url(self):
        notes = extract(
            CHANGELOG,
            "9.9.0",
            "markdown",
            max_chars=2000,
            details_url="https://x/CHANGELOG.md",
        )
        assert "https://x/CHANGELOG.md" in notes

    def test_a_section_with_no_details_half_is_truncated_to_fit(self):
        flat = f"""# Changelog

## [9.9.0] - 2026-08-21

### Added
- **Only headlines here, but very many of them** — {DETAIL}
- **And another** — {DETAIL}
"""
        notes = extract(flat, "9.9.0", "markdown", max_chars=500)
        assert len(notes) <= 500

    def test_truncation_keeps_whole_lines(self):
        flat = f"""# Changelog

## [9.9.0] - 2026-08-21

### Added
- **First** — {DETAIL}
- **Second** — {DETAIL}
"""
        notes = extract(flat, "9.9.0", "markdown", max_chars=600)
        body = [ln for ln in notes.splitlines() if ln.startswith("- ")]
        for line in body:
            assert line in flat, "a line was cut mid-way through"

    def test_slack_output_is_capped_too(self):
        notes = extract(CHANGELOG, "9.9.0", "slack", max_chars=2000)
        assert len(notes) <= 2000
        assert (
            "*A short headline*" in notes
        )  # mrkdwn bold, so it went through slack fmt
