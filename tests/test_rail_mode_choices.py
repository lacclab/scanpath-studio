"""Rail choices that must mean the same thing on every layer and in every mode.

Each test drives the real plot rail (`controls.render_plot_controls`) under
AppTest over a tiny two-word trial, then builds the figure the Scanpath view
would build from what the rail returned — so a gate in the collector, not just
in the builder, is what is under test.
"""

from __future__ import annotations

import pytest

from scanpath_studio import plots, tabs

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

#: A 1×1 PNG — a stand-in stimulus screenshot.
PIXEL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="
)


def _frames():
    import pandas as pd

    words = pd.DataFrame(
        {
            "participant_id": ["p"] * 2,
            "trial_id": ["t"] * 2,
            "text_id": ["text"] * 2,
            "word_id": [1, 2],
            "text": ["One", "Two"],
            "line_idx": [0, 0],
            "x": [100, 200],
            "y": [100, 100],
            "width": [80, 80],
            "height": [20, 20],
            "flag": [True, False],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"] * 4,
            "trial_id": ["t"] * 4,
            "text_id": ["text"] * 4,
            "x": [110, 120, 210, 220],
            "y": [110] * 4,
            "duration_ms": [100, 200, 300, 300],
            "timestamp_ms": [0, 100, 300, 600],
            "order_in_trial": [1, 2, 3, 4],
            "fixation_id": [1, 2, 3, 4],
            "word_id": [1, 1, 2, 2],
            "eye": ["L", "R", "L", "R"],
            "pupil_size": [2.1, 2.2, 2.3, 2.4],
        }
    )
    return words, fixations


def _rail_app():
    import streamlit as st

    from scanpath_studio import controls
    from tests.test_rail_mode_choices import _frames

    words, fixations = _frames()
    st.session_state["_viz"] = controls.render_plot_controls(
        fixations, 16, words=words, fix_range_fixations=fixations
    )


def _rail(**state) -> AppTest:
    at = AppTest.from_function(_rail_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _rerun(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _settings(viz: dict, **overrides) -> plots.FigureSettings:
    return plots.FigureSettings.from_mapping(
        tabs._build_figure_settings(viz, False),
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        **overrides,
    )


def _static(at: AppTest, **overrides):
    words, fixations = _frames()
    viz = at.session_state["_viz"]
    return plots.make_scanpath_figure(
        words, fixations, settings=_settings(viz, **overrides)
    )


def _span_outlines(fig) -> list:
    """The span outline shapes — drawn in the border colour, unlike the frame."""
    return [
        s
        for s in fig.layout.shapes or ()
        if s.type == "rect" and s.line.color == "#123456"
    ]


# --- Highlight → Mark border is its own layer --------------------------------

BORDER = {
    "global_show_stimulus": True,
    "global_show_labels": False,
    "global_show_words": False,
    "global_highlight_column": "flag",
    "global_critical_span_style": "Mark border",
    "global_span_border_color": "#123456",
}


def test_mark_border_draws_with_text_and_word_boxes_off():
    at = _rail(**BORDER)
    viz = at.session_state["_viz"]
    assert viz["highlight_column"] == "flag"
    assert len(_span_outlines(_static(at))) == 1


def test_mark_border_draws_over_a_screenshot():
    at = _rail(**BORDER)
    fig = _static(at, background_image=PIXEL, background_image_size=(800, 600))
    assert fig.layout.images, "the screenshot layer is drawn"
    assert len(_span_outlines(fig)) == 1


def test_stimulus_master_switch_suppresses_and_restores_the_border():
    at = _rail(**{**BORDER, "global_show_stimulus": False})
    assert at.session_state["_viz"]["highlight_column"] is None
    assert _span_outlines(_static(at)) == []
    at.session_state["global_show_stimulus"] = True
    _rerun(at)
    assert len(_span_outlines(_static(at))) == 1


def test_mark_text_stays_inactive_while_text_is_hidden():
    at = _rail(**{**BORDER, "global_critical_span_style": "Mark text"})
    assert at.session_state["_viz"]["highlight_column"] is None
    at.session_state["global_show_labels"] = True
    _rerun(at)
    assert at.session_state["_viz"]["highlight_column"] == "flag"
