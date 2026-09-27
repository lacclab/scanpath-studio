"""Keep CITATION.cff in sync with the package version and the in-app DOI.

GitHub's "Cite this repository" button and the in-app About popover both
surface a citation; this guard makes the CFF version part of the release
bump so the two never drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path

from scanpath_studio import __version__

CFF_PATH = Path(__file__).resolve().parent.parent / "CITATION.cff"


def test_citation_cff_version_matches_package():
    text = CFF_PATH.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*[\"']?([^\s\"']+)", text, re.MULTILINE)
    assert match, "CITATION.cff is missing a `version:` field"
    assert match.group(1) == __version__, (
        f"CITATION.cff version {match.group(1)} != package {__version__} — "
        "bump CITATION.cff (version + date-released) alongside "
        "scanpath_studio/__init__.py"
    )


def test_citation_cff_doi_matches_in_app_citation():
    """ENG-75: the Zenodo concept DOI is written twice — CITATION.cff (GitHub's
    "Cite this repository") and `constants.CITATION` (the About BibTeX and the
    bulk-export README) — so a change to one must reach the other."""
    from scanpath_studio.constants import CITATION

    text = CFF_PATH.read_text(encoding="utf-8")
    match = re.search(r"^doi:\s*[\"']?([^\s\"']+)", text, re.MULTILINE)
    assert match, "CITATION.cff is missing its top-level `doi:` field"
    assert match.group(1) == CITATION["doi"], (
        f"CITATION.cff doi {match.group(1)} != constants.CITATION['doi'] "
        f"{CITATION['doi']}"
    )
    assert re.fullmatch(r"10\.5281/zenodo\.\d+", CITATION["doi"]), (
        "expected a Zenodo DOI (10.5281/zenodo.<record id>)"
    )
