"""A link or a saved config written while the fixations' and the heatmap's
colour bars shared one set of settings still opens: each old setting sets both."""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT


@pytest.mark.timeout(240)
def test_an_old_link_sets_both_bars():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["source"] = "demo"
    at.query_params["show_colorbars"] = "0"
    at.query_params["colorbar_orientation"] = "Horizontal"
    at.query_params["colorbar_tickangle"] = "45"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    for bar in ("fixation", "heatmap"):
        assert at.session_state[f"global_show_{bar}_colorbar"] is False
        assert at.session_state[f"global_{bar}_colorbar_orientation"] == "Horizontal"
        assert at.session_state[f"global_{bar}_colorbar_tickangle"] == 45


def test_an_old_config_sets_both_bars():
    import streamlit as st

    from scanpath_studio.url_state import _restore_plot_config

    st.session_state.clear()
    config = {
        "schema": 6,
        "coloring": {
            "show_colorbars": False,
            "colorbar_orientation": "Horizontal",
            "colorbar_tickfont_size": 9,
        },
    }
    _restore_plot_config(config, pd.DataFrame(), pd.DataFrame())
    for bar in ("fixation", "heatmap"):
        assert st.session_state[f"global_show_{bar}_colorbar"] is False
        assert st.session_state[f"global_{bar}_colorbar_orientation"] == "Horizontal"
        assert st.session_state[f"global_{bar}_colorbar_tickfont_size"] == 9
