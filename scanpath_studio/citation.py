"""How to cite Scanpath Studio: the BibTeX and APA entries.

One builder for every place the citation is shown — ❓ Help → About in the app
and the docs site's *Cite* section (``scripts/docs_support.py``) — so the two
print the same entry. It reads ``constants.CITATION`` / ``CITATION_AUTHORS`` and
the package's ``__release__``, which ``tests/test_citation.py`` keeps equal to
``CITATION.cff`` (the file behind GitHub's *Cite this repository* and the Zenodo
record); the installed package has no ``CITATION.cff`` to read.
"""

from __future__ import annotations

import unicodedata

from scanpath_studio.constants import CITATION, CITATION_AUTHORS

#: Combining mark → the BibTeX accent command that spells it, so the entry
#: compiles under classic BibTeX as well as biber.
_BIBTEX_ACCENTS = {
    "̀": "`",  # grave
    "́": "'",  # acute
    "̂": "^",  # circumflex
    "̃": "~",  # tilde
    "̈": '"',  # diaeresis
    "̊": "r",  # ring
    "̌": "v",  # caron
    "̧": "c",  # cedilla
}


def bibtex_text(text: str) -> str:
    """``Jäger`` → ``J{\\"a}ger``: every accented letter as an escaped group."""
    out: list[str] = []
    for char in unicodedata.normalize("NFD", text):
        accent = _BIBTEX_ACCENTS.get(char)
        if accent and out:
            base = out.pop()
            sep = " " if accent.isalpha() else ""
            out.append(f"{{\\{accent}{sep}{base}}}")
        else:
            out.append(char)
    return unicodedata.normalize("NFC", "".join(out))


def _initials(given: str) -> str:
    """``Deborah N.`` → ``D. N.``; ``Jean-Paul`` → ``J.-P.`` (APA 7)."""
    parts = []
    for name in given.split():
        if name.endswith(".") and len(name) <= 3:
            parts.append(name)
        else:
            parts.append("-".join(f"{piece[0]}." for piece in name.split("-")))
    return " ".join(parts)


def _release() -> str:
    from scanpath_studio import __release__

    return __release__


def software_bibtex() -> str:
    """The software's BibTeX entry, citing the Zenodo concept DOI."""
    year = CITATION["year"]
    doi = CITATION["doi"]
    # One author per line, so the entry fits a code block without scrolling.
    authors = " and\n             ".join(
        f"{bibtex_text(family)}, {bibtex_text(given)}"
        for given, family in CITATION_AUTHORS
    )
    return "\n".join(
        [
            f"@software{{Shubi_Scanpath_Studio_{year},",
            f"  author  = {{{authors}}},",
            f"  title   = {{{{{CITATION['title']}}}}},",
            f"  year    = {{{year}}},",
            f"  version = {{{_release()}}},",
            f"  doi     = {{{doi}}},",
            f"  url     = {{https://doi.org/{doi}}},",
            f"  license = {{{CITATION['license']}}},",
            "}",
        ]
    )


def software_apa() -> str:
    """The software's APA 7 reference, in Markdown (the title in italics)."""
    names = [f"{family}, {_initials(given)}" for given, family in CITATION_AUTHORS]
    listed = ", ".join(names[:-1]) + f", & {names[-1]}" if len(names) > 1 else names[0]
    return (
        f"{listed} ({CITATION['year']}). *{CITATION['title']}* "
        f"(Version {_release()}) [Computer software]. "
        f"https://doi.org/{CITATION['doi']}"
    )
