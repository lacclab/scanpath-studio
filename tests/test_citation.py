"""Keep CITATION.cff and the package's own citation saying the same thing.

GitHub's "Cite this repository" button and Zenodo read CITATION.cff; ❓ Help →
About and the docs' *Cite* section print ``citation.software_bibtex``, built
from ``constants.CITATION`` / ``CITATION_AUTHORS`` and ``__release__`` because
the installed package has no CITATION.cff. These guards make the CFF's version,
release year, authors, title, license and DOI part of every change to either.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from scanpath_studio import __release__
from scanpath_studio.constants import CITATION, CITATION_AUTHORS

CFF_PATH = Path(__file__).resolve().parent.parent / "CITATION.cff"


def test_citation_cff_version_matches_package():
    text = CFF_PATH.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*[\"']?([^\s\"']+)", text, re.MULTILINE)
    assert match, "CITATION.cff is missing a `version:` field"
    assert match.group(1) == __release__, (
        f"CITATION.cff version {match.group(1)} != package {__release__} — "
        "bump CITATION.cff (version + date-released) alongside "
        "scanpath_studio/__init__.py"
    )


def test_citation_cff_doi_matches_in_app_citation():
    """The Zenodo concept DOI is written twice — CITATION.cff (GitHub's
    "Cite this repository") and `constants.CITATION` (the About BibTeX and the
    bulk-export README) — so a change to one must reach the other."""
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


def _cff_field(name: str) -> str:
    text = CFF_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^{name}:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
    assert match, f"CITATION.cff is missing a top-level `{name}:` field"
    return match.group(1)


def _cff_authors() -> list[tuple[str, str]]:
    """The ``authors`` list as ``(given-names, family-names)``, in order."""
    text = CFF_PATH.read_text(encoding="utf-8")
    block = re.search(r"^authors:\n((?:[ -].*\n)+)", text, re.MULTILINE).group(1)
    authors = []
    for entry in re.split(r"^  - ", block, flags=re.MULTILINE)[1:]:
        fields = dict(
            re.findall(r"^\s*([\w-]+):\s*\"?(.*?)\"?\s*$", entry, re.MULTILINE)
        )
        authors.append((fields["given-names"], fields["family-names"]))
    return authors


def test_citation_cff_authors_title_and_license_match_the_package():
    assert _cff_authors() == list(CITATION_AUTHORS), (
        "CITATION.cff `authors` and constants.CITATION_AUTHORS disagree"
    )
    assert _cff_field("title") == CITATION["title"]
    assert _cff_field("license") == CITATION["license"]


def test_citation_year_is_the_cff_release_year():
    released = _cff_field("date-released")
    assert str(CITATION["year"]) == released[:4], (
        f"CITATION.cff date-released {released} is not in "
        f"constants.CITATION['year'] {CITATION['year']} — bump the year with the "
        "first release of a new year"
    )


def test_about_shows_the_docs_bibtex(monkeypatch):
    """❓ Help → About prints exactly the entry the docs' *Cite* section does."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app

    sys.path.insert(0, str(CFF_PATH.parent / "scripts"))
    import docs_support

    page = docs_support.software_citation()
    fenced = re.search(r"```bibtex\n(.*?)\n\s*```", page, re.DOTALL).group(1)
    docs_bibtex = "\n".join(line.removeprefix("    ") for line in fenced.splitlines())

    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: False)
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    shown = [code.value for code in at.code if code.language == "bibtex"]
    assert shown == [docs_bibtex]
    assert f"version = {{{__release__}}}" in docs_bibtex
    assert f"url     = {{https://doi.org/{CITATION['doi']}}}" in docs_bibtex
    assert "month" not in docs_bibtex


def _about_script():
    from scanpath_studio import app

    app._about_dialog()
