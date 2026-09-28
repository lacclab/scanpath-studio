"""CMP-24 — in Compare, each scanpath is filtered by its own filters.

Before this, the rail's 🧹 Filter section reached scanpath A alone: the
fixation-index window was A's (B was never windowed), and the short / long /
out-of-bounds / blink flags and the saccade-type filter were greyed out in
Compare because the comparison builders took neither. Now A keeps the rail's
ordinary filters, B gets a "· B" block of its own, and every surface carries
B's: the builders (a per-scanpath style entry), the Share link and saved config
(`cmp_b_*`), `render` (`--compare-*`) and the API (`style_b` /
`fix_index_range_b`).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio import api, cli
from scanpath_studio.plots import FigureSettings, make_comparison_figure
from tests.conftest import APP_SCRIPT


def _words(participant: str, trial: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 3,
            "trial_id": [trial] * 3,
            "text_id": ["t1"] * 3,
            "word_id": [0, 1, 2],
            "text": ["the", "quick", "fox"],
            "x": [100.0, 200.0, 300.0],
            "y": [50.0, 50.0, 50.0],
            "width": [90.0, 90.0, 90.0],
            "height": [40.0, 40.0, 40.0],
        }
    )


def _fixations(participant: str, trial: str) -> pd.DataFrame:
    # Fixation 2 is short (40 ms); fixation 4 regresses to the first word.
    return pd.DataFrame(
        {
            "participant_id": [participant] * 4,
            "trial_id": [trial] * 4,
            "text_id": ["t1"] * 4,
            "x": [120.0, 220.0, 320.0, 130.0],
            "y": [70.0, 70.0, 70.0, 70.0],
            "duration_ms": [200.0, 40.0, 180.0, 220.0],
            "timestamp_ms": [0.0, 200.0, 250.0, 450.0],
            "order_in_trial": [1, 2, 3, 4],
            "word_id": [0, 1, 2, 0],
        }
    )


def _pair():
    words = pd.concat([_words("p1", "a"), _words("p2", "b")], ignore_index=True)
    fixations = pd.concat(
        [_fixations("p1", "a"), _fixations("p2", "b")], ignore_index=True
    )
    return words, fixations


_DISCARD_SHORT = {"short": {"mode": "Discard", "threshold_ms": 80}}


def _markers(fig, name_prefix: str) -> int:
    """How many fixation markers the trace named ``name_prefix`` draws."""
    for trace in fig.data:
        if (trace.name or "").startswith(name_prefix) and "markers" in (
            trace.mode or ""
        ):
            if getattr(trace.marker, "symbol", None) == "arrow":
                continue
            return len(trace.x)
    raise AssertionError(f"no marker trace named {name_prefix!r}")


def _saccade_points(fig, name: str) -> int:
    trace = next(t for t in fig.data if t.name == name and t.mode == "lines")
    return sum(v is not None for v in trace.x)


def _figure(**settings):
    words, fixations = _pair()
    return make_comparison_figure(
        words,
        fixations,
        ("p1", "a"),
        ("p2", "b"),
        settings=FigureSettings.from_mapping(
            {"trial_labels": ("A", "B"), **settings},
            canvas_width=800,
            canvas_height=200,
            base_font_size=16,
        ),
    )


class TestTheBuilder:
    def test_the_figure_flags_filter_both_scanpaths(self):
        fig = _figure(fixation_flags=_DISCARD_SHORT)
        assert _markers(fig, "A") == 3
        assert _markers(fig, "B") == 3

    def test_a_style_entry_gives_b_its_own(self):
        fig = _figure(style_b={"fixation_flags": _DISCARD_SHORT})
        assert _markers(fig, "A") == 4
        assert _markers(fig, "B") == 3

    def test_an_empty_style_entry_lifts_the_figures_filter_off_b(self):
        fig = _figure(fixation_flags=_DISCARD_SHORT, style_b={"fixation_flags": {}})
        assert _markers(fig, "A") == 3
        assert _markers(fig, "B") == 4

    @pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
    def test_b_draws_only_its_own_saccade_classes(self, layout):
        fig = _figure(layout=layout, style_b={"saccade_classes": ["regression"]})
        # Three saccades each; B keeps its one regression (two points).
        assert _saccade_points(fig, "A") == 6
        assert _saccade_points(fig, "B") == 2

    def test_highlight_overlays_the_flagged_fixation(self):
        fig = _figure(
            style_b={
                "fixation_flags": {"short": {"mode": "Highlight", "threshold_ms": 80}}
            }
        )
        overlays = [t for t in fig.data if (t.name or "").startswith("B · Short")]
        assert len(overlays) == 1 and len(overlays[0].x) == 1


class TestTheApi:
    def test_fix_index_range_b_windows_b_alone(self):
        words, fixations = _pair()
        fig = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "a"),
            ("p2", "b"),
            labels=("A", "B"),
            fix_index_range_b=(1, 2),
        )
        assert _markers(fig, "A") == 4
        assert _markers(fig, "B") == 2

    def test_fix_index_range_alone_still_windows_both(self):
        words, fixations = _pair()
        fig = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "a"),
            ("p2", "b"),
            labels=("A", "B"),
            fix_index_range=(1, 3),
        )
        assert _markers(fig, "A") == 3
        assert _markers(fig, "B") == 3


class TestTheCli:
    def test_the_compare_flags_reach_b_only(self, tmp_path, monkeypatch):
        seen = {}

        def fake_compare(*args, **kwargs):
            seen.update(kwargs)
            return go.Figure()

        monkeypatch.setattr(api, "compare_scanpaths", fake_compare)
        cli.main(
            [
                "render",
                "--sample",
                "-p",
                "l37_1129",
                "-t",
                "l37_1129_2_1_1_Ele_r0",
                "--compare-with",
                "l37_1129:l37_1129_2_1_3_Adv_r0",
                "--compare-fixation-flag",
                "short=discard,threshold_ms=90",
                "--compare-saccade-classes",
                "regression",
                "--compare-fix-index-range",
                "2:9",
                "-o",
                str(tmp_path / "cmp.html"),
            ]
        )
        assert seen["style_b"]["fixation_flags"]["short"]["mode"] == "Discard"
        assert seen["style_b"]["saccade_classes"] == ["regression"]
        assert seen["fix_index_range_b"] == (2, 9)
        assert "fixation_flags" not in seen  # A is left alone

    def test_the_compare_flags_need_a_comparison(self, tmp_path):
        with pytest.raises(SystemExit, match="--compare-with"):
            cli.main(
                [
                    "render",
                    "--sample",
                    "-p",
                    "l37_1129",
                    "-t",
                    "l37_1129_2_1_1_Ele_r0",
                    "--compare-saccade-classes",
                    "regression",
                    "-o",
                    str(tmp_path / "x.html"),
                ]
            )


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _boot_compare():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.session_state["single_compare_toggle"] = True
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(240)
class TestTheRail:
    def test_b_has_its_own_filter_block_and_as_is_live(self):
        at = _boot_compare()
        keys = {w.key for w in at.selectbox} | {w.key for w in at.multiselect}
        assert {"cmp1_fixclass_short_mode", "cmp1_saccade_classes"} <= keys
        assert "single_compare_fix_range" in {s.key for s in at.slider}
        # A's flags used to be greyed out in Compare.
        assert not at.selectbox(key="global_fixclass_short_mode").disabled
        assert not at.multiselect(key="global_saccade_classes").disabled

    def test_bs_filters_reach_bs_style(self):
        at = _boot_compare()
        at.selectbox(key="cmp1_fixclass_short_mode").set_value("Discard")
        at.multiselect(key="cmp1_saccade_classes").set_value(["regression"])
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["cmp1_fixclass_short_mode"] == "Discard"
        # A's own filter is untouched by B's.
        assert at.session_state["global_fixclass_short_mode"] == "Off"


class TestTheShareLink:
    def test_bs_window_travels_only_once_chosen(self):
        from urllib.parse import parse_qs

        at = streamlit_testing.AppTest.from_function(_share_app)
        at.session_state["_user_set"] = False
        at.run(timeout=30)
        assert "cmp_b_fix_range" not in parse_qs(at.session_state["_query"])

        at = streamlit_testing.AppTest.from_function(_share_app)
        at.session_state["_user_set"] = True
        at.run(timeout=30)
        assert parse_qs(at.session_state["_query"])["cmp_b_fix_range"] == ["2,5"]


def _share_app():
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": {"participant_id": "p2", "trial_id": "t2"},
        "compare_full_fix_range": (1, 9),
    }
    st.session_state["single_compare_fix_range"] = (2, 5)
    st.session_state["single_compare_fix_range_user_set"] = st.session_state[
        "_user_set"
    ]
    query, _caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_query"] = query


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_the_compare_legend_reads_larger_than_the_body(layout):
    """UX-172: the A/B legend is 1.3x the figure's base font."""
    fig = _figure(layout=layout, show_legend=True)
    assert fig.layout.legend.font.size == round(16 * 1.3)


def test_bs_own_filters_disclose_like_as():
    """Review of #251: B's Discard flags and B's window alter the figure as much
    as A's do, so they reach the Illustration disclosure too."""
    from scanpath_studio.illustration import illustration_reasons

    assert illustration_reasons({}) == []
    assert illustration_reasons({}, fixation_flags_b=_DISCARD_SHORT) == [
        "flagged fixations hidden"
    ]
    assert illustration_reasons(
        {}, fix_index_range_b=(1, 2), full_fixation_range_b=(1, 4)
    ) == ["fixation subset"]
