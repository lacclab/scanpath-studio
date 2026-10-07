"""The README and docs link each desktop bundle directly (ENG-76).

``releases/latest/download/<name>`` resolves only while the release carries an
asset of exactly that name, and the names come from the ``archive:`` (and
Windows' ``installer:``) entries of ``.github/workflows/desktop.yml``. Rename one
there (a ``.dmg`` for macOS, say) and the download button 404s with no error
anywhere — so pin the two together.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = "https://github.com/lacclab/scanpath-studio/releases/latest/download/"
PAGES = ["README.md", "docs/getting-started.md"]


def _published_assets(key: str = "archive|installer") -> set[str]:
    workflow = (ROOT / ".github/workflows/desktop.yml").read_text(encoding="utf-8")
    return set(re.findall(rf"^\s*(?:{key}):\s*(\S+)\s*$", workflow, re.MULTILINE))


def _linked_archives(page: str) -> set[str]:
    body = (ROOT / page).read_text(encoding="utf-8")
    return set(re.findall(re.escape(DOWNLOAD) + r"([^)\s]+)", body))


def _os(asset: str) -> str:
    return asset.split("-")[1]


def test_the_workflow_still_names_its_assets():
    assert len(_published_assets("archive")) == 3
    assert _published_assets("installer") == {"ScanpathStudio-windows-x86_64-setup.exe"}


@pytest.mark.parametrize("page", PAGES)
def test_every_link_names_an_asset_the_workflow_publishes(page):
    assert _linked_archives(page) <= _published_assets(), page


@pytest.mark.parametrize("page", PAGES)
def test_every_os_has_a_download_link(page):
    linked = {_os(a) for a in _linked_archives(page)}
    assert linked == {_os(a) for a in _published_assets()}, page


def test_getting_started_links_every_asset():
    assert _linked_archives("docs/getting-started.md") == _published_assets()
