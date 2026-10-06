"""Title and caption each have their own switch; the one they shared before
(`show_title_caption`) still reads, from a link or a saved config, as both."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT


def _open(**params) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["source"] = "demo"
    for key, value in params.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


@pytest.mark.timeout(240)
def test_each_switch_rides_the_link_on_its_own():
    at = _open(show_title="1", title_pattern="T")
    assert at.session_state["global_show_title"] is True
    assert at.session_state["global_show_caption"] is False


@pytest.mark.timeout(240)
def test_the_old_shared_switch_turns_both_on():
    at = _open(show_title_caption="1")
    assert at.session_state["global_show_title"] is True
    assert at.session_state["global_show_caption"] is True


def test_a_config_with_the_old_switch_restores_both():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _restore_plot_config

    config = {"schema": 6, "labels": {"show_title_caption": True}}
    st.session_state.clear()
    _restore_plot_config(config, pd.DataFrame(), pd.DataFrame())
    assert st.session_state.get("global_show_title") is True
    assert st.session_state.get("global_show_caption") is True
