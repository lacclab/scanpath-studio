"""Same-origin HTML iframe helper shared by plots, tours, and Share."""

from __future__ import annotations

import streamlit as st


def embed_html_iframe(html: str, *, height: int) -> None:
    """Render script-bearing HTML in an iframe without the deprecated API.

    ``st.iframe`` replaced the old components embed in Streamlit 1.58. Keeping
    this in one module prevents the plot, guided-tour, and Share surfaces from
    drifting onto different embed APIs.  The compatibility import is deliberately
    lazy so current Streamlit runs never import or call the deprecated function.
    """
    # Tiny script-only embeds need an explicit body. Streamlit's srcdoc
    # autosizing observer otherwise races the parser and tries to observe a null
    # body, producing a browser MutationObserver error even with a fixed height.
    # Full Plotly documents already supply their own body.
    source = html
    if "<body" not in html.lower():
        source = f"<!doctype html><html><body>{html}</body></html>"
    st.iframe(source, height=max(1, int(height)), tab_index=-1)
