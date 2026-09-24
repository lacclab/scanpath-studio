"""The README and docs link each desktop bundle directly (ENG-76).

``releases/latest/download/<name>`` resolves only while the release carries an
asset of exactly that name, and the names come from the ``archive:`` entries of
``.github/workflows/desktop.yml``. Rename one there (a ``.dmg`` for macOS, say)
and the download button 404s with no error anywhere — so pin the two together.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = "https://github.com/lacclab/scanpath-studio/releases/latest/download/"
PAGES = ["README.md", "docs/getting-started.md", "docs/desktop.md"]


def _published_archives() -> set[str]:
    workflow = (ROOT / ".github/workflows/desktop.yml").read_text(encoding="utf-8")
    return set(re.findall(r"^\s*archive:\s*(\S+)\s*$", workflow, re.MULTILINE))


def _linked_archives(page: str) -> set[str]:
    body = (ROOT / page).read_text(encoding="utf-8")
    return set(re.findall(re.escape(DOWNLOAD) + r"([^)\s]+)", body))


def test_the_workflow_still_names_its_archives():
    assert len(_published_archives()) == 3


@pytest.mark.parametrize("page", PAGES)
def test_every_bundle_is_linked_by_the_name_the_workflow_publishes(page):
    assert _linked_archives(page) == _published_archives(), page
