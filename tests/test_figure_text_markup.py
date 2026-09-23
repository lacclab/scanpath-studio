"""BUG-75 (SEC6): a share link cannot put a clickable link in the recipient's figure.

Plotly draws a small HTML subset in a figure's title and caption, and ``<a href>``
is part of it, so ``?show_title_caption=1&title_pattern=<a href="https://…">Session
expired — sign in again</a>`` drew a working link to anywhere across the top of
the recipient's scanpath. Markup is stripped from figure text that arrives from
someone else — a link or a saved config; what a user types into the box
themselves is left alone.
"""

from __future__ import annotations

import pytest

from scanpath_studio.url_state import _strip_markup
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

_PHISH = (
    '<a href="https://evil.example/login">Session expired - sign in again</a>'
    "<img src=x onerror=alert(1)>"
)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        (_PHISH, "Session expired - sign in again"),
        ("<A HREF='x'>caps</A>", "caps"),
        ("<<b>a href='x'>split</a>", "split"),  # cannot reassemble itself
        ("{participant_id} · {trial_id}", "{participant_id} · {trial_id}"),
        ("a < b and c > d", "a < b and c > d"),
        ("left <-> right", "left <-> right"),
    ],
)
def test_strip_markup(raw, clean):
    assert _strip_markup(raw) == clean


def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_title"] = st.session_state.get("global_title_pattern")
    st.session_state["_caption"] = st.session_state.get("global_caption_pattern")


def test_a_linked_title_and_caption_lose_their_markup():
    at = AppTest.from_function(_link_app)
    at.query_params["title_pattern"] = _PHISH
    at.query_params["caption_pattern"] = "<b>{trial_id}</b>"
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_title"] == "Session expired - sign in again"
    assert at.session_state["_caption"] == "{trial_id}"


def _config_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _restore_plot_config

    phish = st.session_state["_phish"]
    _restore_plot_config(
        {
            "labels": {"show_title_caption": True, "title_pattern": phish},
            "compare": [{"label_pattern": phish}],
        },
        pd.DataFrame(),
        pd.DataFrame(),
    )


def test_a_restored_config_loses_its_markup_too():
    at = AppTest.from_function(_config_app)
    at.session_state["_phish"] = _PHISH
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["global_title_pattern"] == "Session expired - sign in again"
    assert at.session_state["cmp0_label_pattern"] == "Session expired - sign in again"


def test_the_recipients_figure_carries_no_link(monkeypatch):
    """End to end, as the audit's PoC: the embedded figure has no `href`."""
    import streamlit as st

    embedded: list[str] = []
    real_iframe = st.iframe

    def spy(src, *args, **kwargs):
        embedded.append(str(src))
        return real_iframe(src, *args, **kwargs)

    monkeypatch.setattr(st, "iframe", spy)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["source"] = "demo"
    at.query_params["show_title_caption"] = "1"
    at.query_params["title_pattern"] = _PHISH
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    figures = [html for html in embedded if "Session expired" in html]
    assert figures, "the titled figure was not embedded"
    assert not any("evil.example" in html for html in figures)
