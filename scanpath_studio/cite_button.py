"""The **Cite** button drawn under every figure, replay and bundle download.

One popover with what a reader of the file needs to credit it: a sentence for a
figure caption, the APA reference, the BibTeX entry, and ``.bib`` / ``.ris``
files for a citation manager. When the trials come from a public corpus
(`citation.corpus_for` on the session's dataset), the corpus is cited alongside.

Nothing in it reruns the app: the entries are code blocks with Streamlit's own
copy button, and the two downloads pass ``on_click="ignore"``.
"""

from __future__ import annotations

import streamlit as st

from .citation import CORPORA, cite, corpus_for
from .constants import ICONS
from .session_keys import DATA_SOURCE_CHOICE


def session_corpus() -> str | None:
    """The `citation.CORPORA` key of the dataset on screen, if it is a public one."""
    return corpus_for(st.session_state.get(DATA_SOURCE_CHOICE))


def render_cite_button(host, *, key: str, what: str = "this figure") -> None:
    """Draw the **Cite** popover in ``host``; ``key`` keeps its two download
    buttons apart from another Cite button's on the same page, and ``what``
    names the thing being cited in its first line."""
    corpus = session_corpus()
    with host.popover(
        "Cite",
        icon=ICONS["cite"],
        help=f"How to credit Scanpath Studio when you use {what}.",
        width="content",
    ):
        data = f" and {CORPORA[corpus].name}, whose data it shows" if corpus else ""
        st.markdown(
            f"Using {what} in a paper, a poster or a talk? Please cite "
            f"Scanpath Studio{data}. Exported files already carry the citation "
            "in their metadata."
        )
        st.caption("Figure credit")
        st.code(cite("credit", corpus), language=None, wrap_lines=True)
        st.caption("APA")
        st.code(cite("apa", corpus), language=None, wrap_lines=True)
        st.caption("BibTeX")
        st.code(cite("bibtex", corpus), language="bibtex")
        row = st.container(horizontal=True)
        row.download_button(
            "BibTeX (.bib)",
            data=cite("bibtex", corpus) + "\n",
            file_name="scanpath_studio.bib",
            mime="application/x-bibtex",
            icon=ICONS["download"],
            key=f"{key}_cite_bib",
            on_click="ignore",
        )
        row.download_button(
            "RIS (.ris)",
            data=cite("ris", corpus) + "\n",
            file_name="scanpath_studio.ris",
            mime="application/x-research-info-systems",
            icon=ICONS["download"],
            key=f"{key}_cite_ris",
            on_click="ignore",
            help="For Zotero, Mendeley or EndNote.",
        )
