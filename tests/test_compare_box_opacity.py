"""Compare's word boxes: each scanpath's own outline and fill opacity.

The *Scanpath A* / *Scanpath B* rows of the ⬚ Word boxes popover carry an
opacity each for line and fill. Like their colours, they follow the figure's
opacity until one is set, and setting the figure's value again goes back to
following it — so a session that never touches them draws both scanpaths at
the figure's opacity.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _rows_app():
    import streamlit as st

    from scanpath_studio import controls

    with st.popover("Word boxes"):
        controls._render_compare_box_groups("fill help")
    st.session_state["_styles"] = controls._collect_compare_styles()


def _run(**state):
    at = AppTest.from_function(_rows_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _slider(at, key):
    """The shadow slider for ``cmp{idx}_box_{part}_opacity`` — its key moves
    with each new value (`controls.shadow_widget_key`)."""
    name = key.removesuffix("__pick")
    return next(s for s in at.slider if s.key.startswith(f"_{name}_pick__w"))


def test_untouched_they_follow_the_figure():
    at = _run(global_word_box_line_opacity=0.4, global_word_box_fill_opacity=0.2)
    assert _slider(at, "cmp1_box_line_opacity__pick").value == pytest.approx(0.4)
    assert _slider(at, "cmp1_box_fill_opacity__pick").value == pytest.approx(0.2)
    _style_a, style_b = at.session_state["_styles"]
    assert style_b["box_line_opacity"] is None
    assert style_b["box_fill_opacity"] is None


def test_setting_one_is_that_scanpaths_alone():
    at = _run(global_word_box_fill_opacity=0.2)
    _slider(at, "cmp1_box_fill_opacity__pick").set_value(0.6).run()
    assert at.session_state["cmp1_box_fill_opacity"] == pytest.approx(0.6)
    assert "cmp0_box_fill_opacity" not in at.session_state
    style_a, style_b = at.session_state["_styles"]
    assert style_a["box_fill_opacity"] is None
    assert style_b["box_fill_opacity"] == pytest.approx(0.6)


def test_zero_is_kept():
    at = _run(global_word_box_line_opacity=0.5)
    _slider(at, "cmp0_box_line_opacity__pick").set_value(0.0).run()
    assert at.session_state["cmp0_box_line_opacity"] == 0.0


def test_the_figures_value_goes_back_to_following_it():
    at = _run(global_word_box_fill_opacity=0.2, cmp1_box_fill_opacity=0.6)
    _slider(at, "cmp1_box_fill_opacity__pick").set_value(0.2).run()
    assert "cmp1_box_fill_opacity" not in at.session_state
