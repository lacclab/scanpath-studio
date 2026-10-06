"""A pinned colour range is the user's endpoints (round-7 review, findings 10-12).

With *Auto* off, the rail's colour ranges pin one mapping across trials. These
tests drive the real rail (`controls.render_plot_controls`) over a small
hand-built pool, so the pool can be narrowed between runs exactly as a trial
filter narrows it in the app.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import plots, tabs

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

FIX_KEY = "global_fixation_color_range"
HEAT_KEY = "global_heatmap_color_range"
FIX_VIEW = "_fixation_color_range_view"
HEAT_VIEW = "_heatmap_color_range_view"
CANVAS = (800, 600)


def _frames():
    """Two words; four fixations of 100/200/300/300 ms → 300 and 600 ms of
    dwell, the review's example."""
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
        }
    )
    return words, fixations


def _rail_app():
    from urllib.parse import parse_qs

    import pandas as pd
    import streamlit as st

    from scanpath_studio import controls
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query
    from tests.test_color_range_pinned import _frames

    words, fixations = _frames()
    pool = fixations
    if st.session_state.get("_wide"):
        # Another reading, holding the pool's one 1000-ms fixation.
        other = fixations.iloc[[0]].copy()
        other["trial_id"] = "other"
        other["duration_ms"] = 1000
        pool = pd.concat([fixations, other], ignore_index=True)
    st.session_state["_viz"] = controls.render_plot_controls(
        pool, 16, words=words, fix_range_fixations=fixations
    )
    st.session_state["_share_selection"] = {"participant_id": "p", "trial_id": "t"}
    query, _caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_params"] = parse_qs(query)


def _rail(**state) -> AppTest:
    at = AppTest.from_function(_rail_app)
    for key, value in state.items():
        at.session_state[key] = value
    return _rerun(at)


def _rerun(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _settings(viz: dict) -> plots.FigureSettings:
    return plots.FigureSettings.from_mapping(
        tabs._build_figure_settings(viz, False),
        canvas_width=CANVAS[0],
        canvas_height=CANVAS[1],
        base_font_size=16,
    )


def _static(viz: dict):
    words, fixations = _frames()
    return plots.make_scanpath_figure(words, fixations, settings=_settings(viz))


def _comparison(viz: dict):
    words, fixations = _frames()
    w_b, f_b = words.copy(), fixations.copy()
    w_b["participant_id"] = "q"
    f_b["participant_id"] = "q"
    return plots.make_comparison_figure(
        pd.concat([words, w_b], ignore_index=True),
        pd.concat([fixations, f_b], ignore_index=True),
        ("p", "t"),
        ("q", "t"),
        settings=_settings(viz),
    )


def _marker_scales(fig) -> list:
    return sorted(
        (t.name, t.marker.cmin, t.marker.cmax)
        for t in fig.data
        if getattr(t, "marker", None) is not None
        and t.marker.colorscale is not None
        and t.marker.cmin is not None
    )


def _heat_fills(fig) -> list:
    return [
        s.fillcolor for s in fig.layout.shapes or () if "heatmap" in str(s.name or "")
    ]


def _config(viz: dict) -> dict:
    return tabs._build_studio_config(
        selected_participant="p",
        selected_trial="t",
        canvas_width=CANVAS[0],
        canvas_height=CANVAS[1],
        x_field="x",
        y_field="y",
        figure_settings=tabs._build_figure_settings(viz, False),
        viz_settings=viz,
        base_font_size=16,
        trial_raw_gaze=pd.DataFrame(),
        font_family="Arial",
        data_source=None,
        app_version="test",
        exported_at="2026-10-03",
    )


class TestAPinnedRangeSurvivesANarrowerPool:
    """Finding 10: filtering out the trial with the extreme value must not move
    a pinned mapping — the same duration keeps the same colour."""

    def test_the_fixation_colour_range(self):
        at = _rail(_wide=True, global_color_by="duration_ms", **{FIX_KEY: (100, 1000)})
        wide = _marker_scales(_static(at.session_state["_viz"]))
        at.session_state["_wide"] = False
        _rerun(at)
        viz = at.session_state["_viz"]
        assert viz["fixation_color_range"] == (100.0, 1000.0)
        assert _marker_scales(_static(viz)) == wide == [("Fixations", 100.0, 1000.0)]
        # Auto stays off, and the slider holds the pinned endpoint although no
        # fixation left in the pool reaches it.
        assert at.checkbox(key="_fixation_color_range_auto").value is False
        slider = at.slider(key=FIX_VIEW)
        assert slider.value == (100.0, 1000.0)
        assert slider.proto.max >= 1000

    def test_it_reaches_compare_share_and_the_settings_file(self):
        at = _rail(global_color_by="duration_ms", **{FIX_KEY: (50, 1000)})
        viz = at.session_state["_viz"]
        scales = _marker_scales(_comparison(viz))
        assert scales and {(lo, hi) for _, lo, hi in scales} == {(50.0, 1000.0)}
        assert at.session_state["_params"]["fixation_color_range"] == ["50,1000"]
        assert _config(viz)["coloring"]["fixation_range"] == [50.0, 1000.0]

    def test_the_heatmap_range(self):
        at = _rail(
            _wide=True,
            global_show_heatmap=True,
            global_heatmap_metric="duration_ms",
            **{HEAT_KEY: (100, 1000)},
        )
        wide = _heat_fills(_static(at.session_state["_viz"]))
        at.session_state["_wide"] = False
        _rerun(at)
        viz = at.session_state["_viz"]
        assert viz["heatmap_range"] == (100.0, 1000.0)
        assert _heat_fills(_static(viz)) == wide

    def test_auto_still_follows_the_trial(self):
        at = _rail(_wide=True, global_color_by="duration_ms")
        assert at.session_state["_viz"]["fixation_color_range"] is None
        assert FIX_KEY not in at.session_state


WORD_HEAT = {
    "global_show_heatmap": True,
    "global_heatmap_style": "Word boxes",
    "global_heatmap_metric": "duration_ms",
}


class TestTheWordHeatmapRangeIsInDwell:
    """Finding 11: a word box maps its summed dwell, so the range's bounds are
    per-word dwell — 300 and 600 ms here — not the 100-300 ms of the single
    fixations, which pinned both words to one colour."""

    def test_unticking_auto_pins_the_dwell_span_and_keeps_the_words_apart(self):
        at = _rail(**WORD_HEAT)
        auto_fills = _heat_fills(_static(at.session_state["_viz"]))
        at.checkbox(key="_heatmap_color_range_auto").uncheck()
        _rerun(at)
        viz = at.session_state["_viz"]
        # The scale starts at 0, as the figure's auto range does.
        assert viz["heatmap_range"] == (0.0, 600.0)
        fills = _heat_fills(_static(viz))
        assert fills == auto_fills
        assert len(set(fills)) == 2

    def test_an_endpoint_beyond_the_observed_dwell_can_be_typed(self):
        at = _rail(**WORD_HEAT)
        at.number_input(key=f"{HEAT_VIEW}__num_lo").set_value(0)
        at.number_input(key=f"{HEAT_VIEW}__num_hi").set_value(900)
        _rerun(at)
        assert at.session_state["_viz"]["heatmap_range"] == (0.0, 900.0)
        slider = at.slider(key=HEAT_VIEW)
        assert slider.value == (0.0, 900.0)
        assert slider.proto.max >= 900
        # Both words keep distinct colours on the wider scale.
        assert len(set(_heat_fills(_static(at.session_state["_viz"])))) == 2

    def test_compare_and_log_keep_the_distinction_on_a_0_600_scale(self):
        at = _rail(**WORD_HEAT, **{HEAT_KEY: (0, 600)})
        viz = at.session_state["_viz"]
        assert len(set(_heat_fills(_comparison(viz)))) == 2
        log = _settings(viz).with_overrides(heatmap_norm="Log")
        words, fixations = _frames()
        fig = plots.make_scanpath_figure(words, fixations, settings=log)
        assert len(set(_heat_fills(fig))) == 2

    def test_counts_get_a_range_from_zero(self):
        at = _rail(**{**WORD_HEAT, "global_heatmap_metric": "counts"})
        assert at.session_state["_viz"]["heatmap_range"] is None  # auto
        slider = at.slider(key=HEAT_VIEW)
        assert slider.proto.min == 0
        assert slider.proto.max >= 2
        assert "Fixations per word" in slider.proto.help


class TestHeatmapValueBounds:
    def test_repeated_fixations_sum_per_word(self):
        from scanpath_studio.controls import heatmap_value_bounds

        words, fixations = _frames()
        assert heatmap_value_bounds(fixations, words) == (300.0, 600.0)
        # A second reading of word 2 counts toward its dwell.
        reread = pd.concat([fixations, fixations.iloc[[3]]], ignore_index=True)
        assert heatmap_value_bounds(reread, words) == (300.0, 900.0)

    def test_without_word_ids_a_reading_bounds_it(self):
        from scanpath_studio.controls import heatmap_value_bounds

        words, fixations = _frames()
        assert heatmap_value_bounds(fixations.drop(columns="word_id"), words) == (
            100.0,
            900.0,
        )

    def test_words_only_data_maps_its_own_dwell(self):
        from scanpath_studio.controls import heatmap_value_bounds

        words, _ = _frames()
        words["total_fixation_duration_ms"] = [250.0, 0.0]
        assert heatmap_value_bounds(pd.DataFrame(), words) == (250.0, 250.0)
        assert heatmap_value_bounds(pd.DataFrame(), words.iloc[:0]) is None


class TestASmoothedHeatmapOffersNoRange:
    """Finding 12: Interpolated scales its density to its own peak, so the range is greyed for them — kept, not cleared — and the
    code snippet does not present it as pinning anything."""

    @pytest.mark.parametrize("style", ["Interpolated"])
    def test_the_range_is_greyed_and_kept(self, style):
        at = _rail(**{**WORD_HEAT, "global_heatmap_style": style, HEAT_KEY: (0, 600)})
        assert at.slider(key=HEAT_VIEW).proto.disabled
        assert at.checkbox(key="_heatmap_color_range_auto").proto.disabled
        assert "own peak" in at.slider(key=HEAT_VIEW).proto.help
        assert at.session_state[HEAT_KEY] == (0, 600)
        # Back on Word boxes the same range is live again.
        at.session_state["global_heatmap_style"] = "Word boxes"
        _rerun(at)
        assert not at.slider(key=HEAT_VIEW).proto.disabled
        assert at.session_state["_viz"]["heatmap_range"] == (0.0, 600.0)

    def test_compare_draws_word_boxes_so_the_range_stays_live(self):
        at = _rail(
            **{**WORD_HEAT, "global_heatmap_style": "Interpolated", HEAT_KEY: (0, 600)},
            single_compare_toggle=True,
        )
        assert not at.slider(key=HEAT_VIEW).proto.disabled

    def test_the_code_snippet_omits_it_for_a_smoothed_style(self):
        from scanpath_studio.code_snippet import figure_kwargs

        settings = {"heatmap_range": (0.0, 600.0), "show_heatmap": True}
        assert "heatmap_range" in figure_kwargs(
            {**settings, "heatmap_style": "Word boxes"}
        )
        smoothed = {**settings, "heatmap_style": "Interpolated"}
        assert "heatmap_range" not in figure_kwargs(smoothed)
        assert "heatmap_range" in figure_kwargs(smoothed, "comparison")


class TestHeatmapBoundsOnlyWhenShown:
    """The dwell groupby behind the heatmap range runs only while the heatmap
    is shown; switched off, the greyed range is drawn from the single
    fixations, and words reach the cache key only when they are read."""

    def _counting(self, monkeypatch):
        from scanpath_studio import controls

        calls = []
        real = controls.heatmap_value_bounds

        def counting(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(controls, "heatmap_value_bounds", counting)
        controls._heatmap_value_bounds_cached.clear()
        return calls

    def test_off_draws_the_range_without_the_groupby(self, monkeypatch):
        calls = self._counting(monkeypatch)
        at = _rail(**{**WORD_HEAT, "global_show_heatmap": False})
        assert calls == []
        slider = at.slider(key=HEAT_VIEW)
        assert (slider.proto.min, slider.proto.max) == (0, 300)

    def test_on_bounds_it_by_dwell(self, monkeypatch):
        calls = self._counting(monkeypatch)
        at = _rail(**WORD_HEAT)
        assert len(calls) == 1
        slider = at.slider(key=HEAT_VIEW)
        assert (slider.proto.min, slider.proto.max) == (0, 600)

    def test_words_key_the_cache_only_on_the_words_only_fallback(self, monkeypatch):
        from scanpath_studio import controls

        seen = []
        monkeypatch.setattr(
            controls,
            "_heatmap_value_bounds_cached",
            lambda fix, words, counts, key: seen.append((words, key)),
        )
        words, fixations = _frames()
        controls._heatmap_bounds_for_rail(fixations, words)
        assert seen[-1][0] is None and seen[-1][1][1] is None
        controls._heatmap_bounds_for_rail(pd.DataFrame(), words)
        assert seen[-1][0] is words and seen[-1][1][1] is not None
