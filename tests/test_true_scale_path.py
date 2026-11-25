"""Spatial figures draw at true scale, never through `st.plotly_chart`.

`st.plotly_chart` pins the chart's width to its column but keeps the layout's
height, which mis-scales the pixel-sized word labels; spatial figures go
through `tabs._render_true_scale_chart` (and the replay through the same
embed, `_render_true_scale_plot`), which draws the figure's HTML at its
exact size and scales it with CSS (AGENTS.md, Figures). Here the Scanpath view
is drawn in each figure mode, and Corpus Analysis's *Measure on the stimulus*
view once, and each is checked.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import tabs
from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view


def _count_true_scale_draws(monkeypatch) -> list:
    """Record the key of every figure drawn through the true-scale embed."""
    drawn: list = []
    real = tabs._render_true_scale_plot

    def counting(*args, **kwargs):
        drawn.append(kwargs.get("key"))
        return real(*args, **kwargs)

    monkeypatch.setattr(tabs, "_render_true_scale_plot", counting)
    return drawn


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ({}, "static"),
        ({"single_animate": True}, "animation"),
        ({"single_compare_toggle": True}, "comparison"),
    ],
    ids=["static", "replay", "compare"],
)
def test_the_scanpath_view_draws_at_true_scale(mode, kind, monkeypatch):
    """The embed every true-scale figure ends in, the replay's included, must
    run; `st.plotly_chart` must not."""
    drawn = _count_true_scale_draws(monkeypatch)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    for key, value in mode.items():
        at.session_state[key] = value
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    assert drawn, "the view drew no figure at true scale"
    # The figure of that mode drew, B's scanpath included in Compare.
    assert at.session_state[SNIPPET_STATE_KEY].kind == kind
    assert not at.get("plotly_chart"), (
        "the Scanpath view drew a figure through st.plotly_chart, which "
        "mis-scales its word labels; use tabs._render_true_scale_chart"
    )


@pytest.mark.timeout(300)
def test_the_corpus_measure_on_the_stimulus_draws_at_true_scale(monkeypatch):
    """Corpus Analysis's *Measure on the stimulus* tints the words on the
    stimulus, a spatial figure with word labels, so it takes the embed too."""
    drawn = _count_true_scale_draws(monkeypatch)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    pin_view(at, _VIEW_CORPUS)
    at.session_state["corpus_subtab"] = "Per text"
    at.session_state["ptext_view"] = "Measure on the stimulus"
    at.run()
    assert not at.exception, at.exception
    assert at.selectbox(key="ptext_view").value == "Measure on the stimulus"
    assert "ptext_stimulus" in drawn, (
        "Measure on the stimulus drew no figure at true scale"
    )
    assert not at.get("plotly_chart"), (
        "Measure on the stimulus drew a figure through st.plotly_chart, which "
        "mis-scales its word labels; use tabs._render_true_scale_chart"
    )
