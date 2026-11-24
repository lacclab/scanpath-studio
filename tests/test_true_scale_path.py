"""The Scanpath view draws its spatial figures at true scale, never through
`st.plotly_chart`.

`st.plotly_chart` pins the chart's width to its column but keeps the layout's
height, which mis-scales the pixel-sized word labels; spatial figures go
through `tabs._render_true_scale_chart` (and the replay through the same
embed, `_render_true_scale_plot`), which draws the figure's HTML at its
exact size and scales it with CSS (AGENTS.md, Figures). Reviewers enforced
this; here the view is drawn in each figure mode and checked.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import tabs
from scanpath_studio.constants import _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    "mode",
    [{}, {"single_animate": True}, {"single_compare_toggle": True}],
    ids=["static", "replay", "compare"],
)
def test_the_scanpath_view_draws_at_true_scale(mode, monkeypatch):
    """The embed every true-scale figure ends in, the replay's included, must
    run; `st.plotly_chart` must not."""
    drawn: list = []
    real = tabs._render_true_scale_plot

    def counting(*args, **kwargs):
        drawn.append(kwargs.get("key"))
        return real(*args, **kwargs)

    monkeypatch.setattr(tabs, "_render_true_scale_plot", counting)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    for key, value in mode.items():
        at.session_state[key] = value
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    assert drawn, "the view drew no figure at true scale"
    assert not at.get("plotly_chart"), (
        "the Scanpath view drew a figure through st.plotly_chart, which "
        "mis-scales its word labels; use tabs._render_true_scale_chart"
    )
