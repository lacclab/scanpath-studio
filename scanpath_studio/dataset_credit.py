"""A lab's optional dataset credit, shared by the dataset editor and exports."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .citation import CORPORA, bibtex_text, cite, corpus_for
from .constants import DATASET_ALIASES_KEY
from .session_keys import DATA_SOURCE_CHOICE, SINGLE_COMPARE_TOGGLE

STORE_KEY = "_dataset_credits"
FIELDS = {
    "title": "Dataset title",
    "authors": "Authors or lab",
    "version": "Dataset version",
    "doi": "Dataset DOI",
    "credit": "Preferred credit",
}


def clean_credit(value) -> dict[str, str]:
    """Retain supplied fields only. An empty form has no citation."""
    if not isinstance(value, Mapping):
        return {}
    credit = {
        key: text.strip()
        for key in FIELDS
        if isinstance(text := value.get(key), str) and text.strip()
    }
    if doi := credit.get("doi"):
        credit["doi"] = re.sub(
            r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.IGNORECASE
        )
    return credit


def form_credit(state, prefix: str) -> dict[str, str]:
    return clean_credit({key: state.get(f"{prefix}_{key}") for key in FIELDS})


def save_credit(state, token: str, values: dict) -> None:
    credits = dict(state.get(STORE_KEY) or {})
    if clean := clean_credit(values):
        credits[token] = clean
    else:
        credits.pop(token, None)
    state[STORE_KEY] = credits


def credit_fields(host, state, prefix: str, initial: dict | None = None) -> None:
    """Edit a draft; Add dataset and Save changes decide when it is committed."""
    with host.expander("Dataset citation (optional)") as box:
        for key, label in FIELDS.items():
            widget = f"{prefix}_{key}"
            state.setdefault(widget, (initial or {}).get(key, ""))
            if key in ("authors", "credit"):
                box.text_area(
                    label,
                    key=widget,
                    height=68,
                    persist_state="session",
                    on_change="ignore",
                    help=(
                        "Enter one author or lab per line."
                        if key == "authors"
                        else "The wording you want a coauthor to use, including for an unpublished pilot."
                    ),
                )
            else:
                box.text_input(
                    label, key=widget, persist_state="session", on_change="ignore"
                )


def references(state) -> list[dict]:
    """References for the dataset shown, and B only while a second source is shown."""
    first = state.get(DATA_SOURCE_CHOICE)
    comparison = (state.get("_share_selection") or {}).get("compare") or {}
    second = comparison.get("source") if state.get(SINGLE_COMPARE_TOGGLE) else None
    credited = []
    for side, token in (("A", first), ("B", second)):
        if not token or (side == "B" and second == first):
            continue
        corpus = corpus_for(token)
        own = clean_credit((state.get(STORE_KEY) or {}).get(token))
        if not corpus and not own:
            continue
        if corpus and any(ref.get("corpus") == corpus for ref in credited):
            continue
        name = (state.get(DATASET_ALIASES_KEY) or {}).get(token, token)
        credited.append({"side": side, "name": name, "corpus": corpus, "fields": own})
    return credited


def _bib_value(value: str) -> str:
    # User-entered braces and TeX special characters are data in a BibTeX field.
    escaped = {"\\": r"\textbackslash{}", **{c: "\\" + c for c in "{}%#&_$"}}
    return bibtex_text("".join(escaped.get(c, c) for c in " ".join(value.split())))


def reference_text(ref: dict, format: str) -> str:
    if ref.get("corpus") in CORPORA:
        return getattr(CORPORA[ref["corpus"]], format)()
    fields = clean_credit(ref.get("fields"))
    title = fields.get("title") or ref["name"]
    authors = (fields.get("authors") or "").splitlines()
    version, doi, preferred = (fields.get(key) for key in ("version", "doi", "credit"))
    if format == "bibtex":
        values = {
            "title": title,
            "author": " and ".join(authors),
            "version": version,
            "doi": doi,
            "note": preferred,
        }
        entries = [
            f"  {key} = {{{_bib_value(value)}}},"
            for key, value in values.items()
            if value
        ]
        return "\n".join(
            [f"@misc{{scanpath-dataset-{ref['side'].lower()},", *entries, "}"]
        )
    if format == "ris":
        lines = ["TY  - DATA", f"TI  - {' '.join(title.split())}"]
        lines.extend(f"AU  - {author}" for author in authors if author.strip())
        lines.extend(
            f"{key}  - {' '.join(value.split())}"
            for key, value in (("ET", version), ("DO", doi), ("N1", preferred))
            if value
        )
        return "\n".join([*lines, "ER  - "])
    if preferred:
        return preferred
    text = f"{', '.join(authors)}. {title}" if authors else title
    if version:
        text += f" (version {version})"
    if doi:
        text += f". https://doi.org/{doi}"
    return text


def cited_text(format: str, refs: list[dict]) -> str:
    separator = " " if format == "credit" else "\n\n"
    texts = [cite(format)]
    for ref in refs:
        text = reference_text(ref, format)
        if format == "apa" and ref.get("corpus"):
            text = text.replace("*", "")
        texts.append(text)
    return separator.join(texts)
