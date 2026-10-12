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


def test_a_cached_session_or_design_moves_the_renamed_keys():
    from scanpath_studio.session_keys import rename_legacy_keys

    out = rename_legacy_keys(
        {
            "global_show_colorbars": False,
            "global_colorbar_tickangle": 30,
            "global_show_title_caption": True,
            # A new key already there wins over the old one.
            "global_show_caption": False,
        }
    )
    assert "global_show_colorbars" not in out
    assert out["global_show_fixation_colorbar"] is False
    assert out["global_show_heatmap_colorbar"] is False
    assert out["global_heatmap_colorbar_tickangle"] == 30
    assert out["global_show_title"] is True
    assert out["global_show_caption"] is False


def test_a_cached_snap_above_words_becomes_snap_to_line():
    """#422: a recovery-cache session or a saved design that snapped still
    snaps."""
    from scanpath_studio.session_keys import rename_legacy_keys

    out = rename_legacy_keys({"global_fixation_snap_to_word": True})
    assert out == {"global_fixation_snap_to_line": True}


def test_the_schema_7_migration_moves_the_shared_settings():
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA, _migrate_plot_config

    migrated, note = _migrate_plot_config(
        {
            "schema": 6,
            "coloring": {"show_colorbars": True, "colorbar_tickfont_size": 9},
            "labels": {"show_title_caption": False},
        }
    )
    assert note is None
    assert migrated["schema"] == PLOT_CONFIG_SCHEMA
    assert migrated["coloring"] == {
        "show_fixation_colorbar": True,
        "show_heatmap_colorbar": True,
        "fixation_colorbar_tickfont_size": 9,
        "heatmap_colorbar_tickfont_size": 9,
    }
    assert migrated["labels"] == {"show_title": False, "show_caption": False}
