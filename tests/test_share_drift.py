"""ENG-23: drift correction (PRE-3) on the deep-link / Share / saved-config surface.

ENG-22 added the CLI leg, leaving the URL contract as the last gap: a
drift-corrected view could not be linked to, shared or saved, so the recipient
of a link silently got the *uncorrected* figure — and since VIZ-23 the
correction applies on all three render paths, so the difference is visible
everywhere, not just on the static plot.

These tests drive the three code paths that carry the setting: the reader
(``_apply_url_preset``), the writer (``_build_share_query``), and the saved
config (``tabs._build_studio_config`` → ``_restore_plot_config``).
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


# Same shape as the other AppTest fixtures: numeric x/y/duration for the axis +
# colour-by options, trial_id doubling as unique_trial_id.
_FIX_COLUMNS = {
    "participant_id": ["p1", "p1", "p2"],
    "trial_id": ["t1", "t2", "t1"],
    "unique_trial_id": ["t1", "t2", "t1"],
    "paragraph_id": ["pA", "pB", "pA"],
    "x": [1.0, 2.0, 3.0],
    "y": [4.0, 5.0, 6.0],
    "duration_ms": [100, 200, 300],
    "pass_index": [1, 1, 2],
}


def _link_app():
    """Apply whatever deep link the test seeded into ``query_params``."""
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_algorithm"] = st.session_state.get("global_align_algorithm")
    st.session_state["_connectors"] = st.session_state.get("global_align_connectors")


def _run_link(**params):
    at = AppTest.from_function(_link_app)
    for key, value in params.items():
        at.query_params[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


class TestDeepLink:
    def test_algorithm_and_connectors_are_seeded(self):
        at = _run_link(align_algorithm="Warp", align_connectors="1")
        assert at.session_state["_algorithm"] == "Warp"
        assert at.session_state["_connectors"] is True
        assert [w.value for w in at.warning] == []

    def test_algorithm_name_is_case_insensitive(self):
        """`?align_algorithm=warp` must land on the picker's own spelling.

        The rail stores the title-cased name, and the selectbox rejects anything
        outside its options — so a lower-case link (or one copied from the CLI's
        `--drift-correction warp`) has to be normalized, not passed through.
        """
        assert _run_link(align_algorithm="warp").session_state["_algorithm"] == "Warp"

    def test_off_is_a_real_value(self):
        at = _run_link(align_algorithm="Off")
        assert at.session_state["_algorithm"] == "Off"
        assert [w.value for w in at.warning] == []

    def test_unknown_algorithm_is_rejected_with_a_warning(self):
        """A hand-edited link must not wedge the picker on an unknown name."""
        at = _run_link(align_algorithm="teleport")
        assert at.session_state["_algorithm"] is None
        assert any("align_algorithm" in w.value for w in at.warning)


def _share_app():
    """Build a Share link from a corrected view."""
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["global_align_algorithm"] = "Regress"
    st.session_state["global_align_connectors"] = True
    st.session_state["_query"], _ = _build_share_query(DEMO_CHOICE)


def test_share_link_carries_the_correction():
    at = AppTest.from_function(_share_app)
    at.run(timeout=30)
    assert not at.exception, at.exception

    params = parse_qs(at.session_state["_query"])
    assert params["align_algorithm"] == ["Regress"]
    assert params["align_connectors"] == ["1"]


def _config_roundtrip_app():
    """Write the saved config from a corrected view, then read it back."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.tabs import _build_studio_config
    from scanpath_studio.url_state import _restore_plot_config
    from scanpath_studio.utils import build_combo_options

    viz_settings = {
        "heatmap_metric": "duration_ms",
        "align_algorithm": "Cluster",
        "align_connectors": True,
    }
    figure_settings = {
        "show_words": True,
        "show_word_labels": True,
        "show_fixations": True,
        "show_order": True,
        "show_saccades": True,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "color_by": "duration_ms",
        "show_colorbars": True,
        "fixation_color_range": None,
        "heatmap_range": None,
        "fixation_colorscale": "Blues",
        "heatmap_colorscale": "Greens",
        "marker_size_range": (8, 24),
        "order_font_size": 12,
        "order_font_color": "#000000",
    }
    config = _build_studio_config(
        selected_participant="p1",
        selected_trial="t1",
        canvas_width=1000,
        canvas_height=800,
        x_field="x",
        y_field="y",
        figure_settings=figure_settings,
        viz_settings=viz_settings,
        base_font_size=14,
        trial_raw_gaze=pd.DataFrame(),
        font_family="Arial",
        annotation_records=[],
        column_mapping={},
        data_source="demo",
        app_version="0.0.0",
        exported_at="2026-08-02T00:00:00",
    )
    st.session_state["_saved"] = {
        "drift_correction": config["coloring"]["drift_correction"],
        "drift_connectors": config["coloring"]["drift_connectors"],
    }

    fixations = pd.DataFrame(st.session_state["_fix"])
    combos, _, _ = build_combo_options(fixations)
    _, skipped = _restore_plot_config(config, combos, fixations)
    st.session_state["_skipped"] = skipped
    st.session_state["_algorithm"] = st.session_state.get("global_align_algorithm")
    st.session_state["_connectors"] = st.session_state.get("global_align_connectors")


def test_saved_config_round_trips_the_correction():
    """The 💾 Save & restore JSON carries the correction, not just the link."""
    at = AppTest.from_function(_config_roundtrip_app)
    at.session_state["_fix"] = _FIX_COLUMNS
    at.run(timeout=30)
    assert not at.exception, at.exception

    assert at.session_state["_saved"] == {
        "drift_correction": "Cluster",
        "drift_connectors": True,
    }
    assert at.session_state["_skipped"] == []
    assert at.session_state["_algorithm"] == "Cluster"
    assert at.session_state["_connectors"] is True
