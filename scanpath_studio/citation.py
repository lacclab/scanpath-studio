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
from dataclasses import dataclass

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
    return (
        f"{_apa_names(CITATION_AUTHORS)} ({CITATION['year']}). *{CITATION['title']}* "
        f"(Version {_release()}) [Computer software]. "
        f"https://doi.org/{CITATION['doi']}"
    )


def _apa_names(authors) -> str:
    names = [f"{family}, {_initials(given)}" for given, family in authors]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f", & {names[-1]}"


def _short_authors(authors, year) -> str:
    """``Shubi et al., 2026`` — the in-text form a figure credit carries."""
    family = authors[0][1]
    if len(authors) == 2:
        family = f"{family} & {authors[1][1]}"
    elif len(authors) > 2:
        family = f"{family} et al."
    return f"{family}, {year}"


def _plain(markdown: str) -> str:
    """The APA reference without its Markdown italics, for plain-text files."""
    return markdown.replace("*", "")


def software_ris() -> str:
    """The software as an RIS record, which Zotero, Mendeley and EndNote import."""
    lines = ["TY  - COMP"]
    lines += [f"AU  - {family}, {given}" for given, family in CITATION_AUTHORS]
    lines += [
        f"TI  - {CITATION['title']}",
        f"PY  - {CITATION['year']}",
        f"ET  - {_release()}",
        f"DO  - {CITATION['doi']}",
        f"UR  - https://doi.org/{CITATION['doi']}",
        "ER  - ",
    ]
    return "\n".join(lines)


def software_csl_json() -> str:
    """The software as CSL-JSON, the format citation managers exchange."""
    import json

    record = {
        "id": f"Shubi_Scanpath_Studio_{CITATION['year']}",
        "type": "software",
        "title": CITATION["title"],
        "author": [
            {"family": family, "given": given} for given, family in CITATION_AUTHORS
        ],
        "issued": {"date-parts": [[CITATION["year"]]]},
        "version": _release(),
        "DOI": CITATION["doi"],
        "URL": f"https://doi.org/{CITATION['doi']}",
    }
    return json.dumps([record], indent=2, ensure_ascii=False)


def software_credit() -> str:
    """A one-sentence figure credit, ready to paste into a caption."""
    return (
        f"Made with {CITATION['title']} {_release()} "
        f"({_short_authors(CITATION_AUTHORS, CITATION['year'])}; "
        f"https://doi.org/{CITATION['doi']})."
    )


#: The short credit drawn on a figure when its credit line is on.
CREDIT_LINE = f"Made with {CITATION['title']}"


# --- Built-in corpora ---------------------------------------------------------


@dataclass(frozen=True)
class CorpusCitation:
    """How to cite a public corpus the app ships or downloads (a journal article)."""

    key: str
    name: str
    authors: tuple[tuple[str, str], ...]
    title: str
    year: int
    journal: str
    volume: int
    number: int
    pages: str
    doi: str

    def bibtex(self) -> str:
        authors = " and\n             ".join(
            f"{bibtex_text(family)}, {bibtex_text(given)}"
            for given, family in self.authors
        )
        # Braces keep the proper nouns' capitals under a sentence-case style.
        title = self.title
        for word in (self.name.split()[0], "English", "German"):
            title = title.replace(word, f"{{{word}}}")
        return "\n".join(
            [
                f"@article{{{self.key},",
                f"  author  = {{{authors}}},",
                f"  title   = {{{title}}},",
                f"  journal = {{{self.journal}}},",
                f"  year    = {{{self.year}}},",
                f"  volume  = {{{self.volume}}},",
                f"  number  = {{{self.number}}},",
                f"  pages   = {{{self.pages}}},",
                f"  doi     = {{{self.doi}}},",
                "}",
            ]
        )

    def apa(self) -> str:
        """APA 7, in Markdown (journal and volume in italics)."""
        return (
            f"{_apa_names(self.authors)} ({self.year}). {self.title}. "
            f"*{self.journal}*, *{self.volume}*({self.number}), {self.pages}. "
            f"https://doi.org/{self.doi}"
        )

    def ris(self) -> str:
        lines = ["TY  - JOUR"]
        lines += [f"AU  - {family}, {given}" for given, family in self.authors]
        lines += [
            f"TI  - {self.title}",
            f"JO  - {self.journal}",
            f"PY  - {self.year}",
            f"VL  - {self.volume}",
            f"IS  - {self.number}",
            f"SP  - {self.pages}",
            f"DO  - {self.doi}",
            "ER  - ",
        ]
        return "\n".join(lines)

    def csl(self) -> dict:
        return {
            "id": self.key,
            "type": "article-journal",
            "title": self.title,
            "author": [
                {"family": family, "given": given} for given, family in self.authors
            ],
            "issued": {"date-parts": [[self.year]]},
            "container-title": self.journal,
            "volume": str(self.volume),
            "issue": str(self.number),
            "page": self.pages,
            "DOI": self.doi,
        }

    def credit(self) -> str:
        return f"Data: {self.name} ({_short_authors(self.authors, self.year)})."


#: Every corpus the app can load by name, keyed by ``corpus_for`` below.
CORPORA = {
    "onestop": CorpusCitation(
        key="berzak2025onestop",
        name="OneStop Eye Movements",
        authors=(
            ("Yevgeni", "Berzak"),
            ("Jonathan", "Malmaud"),
            ("Omer", "Shubi"),
            ("Yoav", "Meiri"),
            ("Ella", "Lion"),
            ("Roger P.", "Levy"),
        ),
        title=(
            "OneStop: A 360-participant English eye-tracking dataset with "
            "different reading regimes"
        ),
        year=2025,
        journal="Scientific Data",
        volume=12,
        number=1,
        pages="1995",
        doi="10.1038/s41597-025-06272-2",
    ),
    "potec": CorpusCitation(
        key="jakobi2025potec",
        name="PoTeC",
        authors=(
            ("Deborah N.", "Jakobi"),
            ("Thomas", "Kern"),
            ("David R.", "Reich"),
            ("Patrick", "Haller"),
            ("Lena A.", "Jäger"),
        ),
        title="PoTeC: A German naturalistic eye-tracking-while-reading corpus",
        year=2025,
        journal="Behavior Research Methods",
        volume=57,
        number=8,
        pages="211",
        doi="10.3758/s13428-024-02536-8",
    ),
}


def corpus_for(source: str | None) -> str | None:
    """The `CORPORA` key of the public corpus a data source is, else ``None``.

    ``source`` is the dataset picker's label (``data_source_choice``): the
    bundled demo and every OneStop dataset are OneStop's, PoTeC is PoTeC's. A
    dataset the user added is their own, so it has none.
    """
    from .constants import (
        DEMO_CHOICE,
        ONESTOP_CHOICE,
        ONESTOP_REGIME_CHOICES,
        POTEC_CHOICE,
    )

    if source in (DEMO_CHOICE, ONESTOP_CHOICE, *ONESTOP_REGIME_CHOICES.values()):
        return "onestop"
    if source == POTEC_CHOICE:
        return "potec"
    return None


#: The ``format`` values ``cite`` takes, in the order the app offers them.
FORMATS = ("bibtex", "apa", "ris", "csl-json", "credit")


def cite(format: str = "bibtex", corpus: str | None = None) -> str:
    """The software's citation in ``format``, followed by ``corpus``'s.

    ``format`` is one of `FORMATS`; ``corpus`` a key of `CORPORA` (``onestop``,
    ``potec``) or ``None``. APA comes as plain text here, without the Markdown
    italics the app draws.
    """
    if format not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(FORMATS)}; got {format!r}")
    data = None
    if corpus is not None:
        if corpus not in CORPORA:
            raise ValueError(
                f"corpus must be one of {', '.join(CORPORA)}; got {corpus!r}"
            )
        data = CORPORA[corpus]
    if format == "csl-json":
        import json

        records = json.loads(software_csl_json())
        if data is not None:
            records.append(data.csl())
        return json.dumps(records, indent=2, ensure_ascii=False)
    software = {
        "bibtex": software_bibtex,
        "apa": lambda: _plain(software_apa()),
        "ris": software_ris,
        "credit": software_credit,
    }[format]()
    if data is None:
        return software
    other = {
        "bibtex": data.bibtex,
        "apa": lambda: _plain(data.apa()),
        "ris": data.ris,
        "credit": data.credit,
    }[format]()
    return f"{software} {other}" if format == "credit" else f"{software}\n\n{other}"


def file_metadata() -> dict[str, str]:
    """The text every exported file carries about where it came from.

    ``Software`` names the tool and its release, ``Source`` the DOI to cite it
    by, and ``Comment`` the full reference — so a figure found later on its own
    still says how to cite it (``exiftool``, an image viewer's *Info*, a PDF's
    *Document properties*).
    """
    return {
        "Software": f"{CITATION['title']} {_release()}",
        "Source": f"https://doi.org/{CITATION['doi']}",
        "Comment": f"Made with {CITATION['title']}. Please cite: "
        f"{_plain(software_apa())}",
    }
