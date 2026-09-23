"""VIZ-46 — the app's default colour ranges are per trial, like the API.

`api.plot_scanpath` leaves `fixation_color_range` / `heatmap_range` at `None`,
so every builder scales the figure to its own trial. The rail used to
`setdefault` both slider keys to the *whole dataset's* span the moment the
sliders rendered, so a default app figure never matched a headless one — the
heatmap sat on the dataset's longest single fixation while the API used the
trial's own per-word dwell. The user's call (ENG-63): make the app default per
trial.

The fix makes the canonical `global_*` key mean **explicit**: it exists only
once a range is chosen, and `None` reaches the builders otherwise. These tests
drive the real rail (`controls.render_plot_controls`) over the bundled demo,
because the bug lived in what *rendering* the slider did to session state — a
pure call of `_collect_viz_settings` never rendered it and passed on the old
code too.
"""

from __future__ import annotations

import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import plots, tabs

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

FIX_KEY = "global_fixation_color_range"
HEAT_KEY = "global_heatmap_color_range"
FIX_VIEW = "_fixation_color_range_view"
HEAT_VIEW = "_heatmap_color_range_view"
FIX_AUTO = "_fixation_color_range_auto"
HEAT_AUTO = "_heatmap_color_range_auto"
CANVAS = (2560, 1440)

#: Every layer whose colour range is in play: a duration-weighted word-box
#: heatmap and fixations coloured by their own duration.
COLOURED = {
    "global_show_heatmap": True,
    "global_heatmap_metric": "duration_ms",
    "global_color_by": "duration_ms",
    "global_show_colorbars": True,
}


@pytest.fixture(scope="module")
def demo():
    return sps.load_sample_data()


def _trial_frames(words, fixations, trial):
    pid, tid = trial
    return (
        words[(words["participant_id"] == pid) & (words["trial_id"] == tid)],
        fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ],
    )


@pytest.fixture(scope="module")
def two_trials(demo):
    """Two trials whose duration spans differ from each other and from the
    dataset's — so a dataset-wide default and a per-trial one cannot agree."""
    words, fixations = demo
    whole = (fixations["duration_ms"].min(), fixations["duration_ms"].max())
    picked, spans = [], set()
    for trial in sps.list_trials(words, fixations).itertuples(index=False):
        _, trial_fix = _trial_frames(words, fixations, tuple(trial))
        span = (trial_fix["duration_ms"].min(), trial_fix["duration_ms"].max())
        if span != whole and span not in spans:
            picked.append(tuple(trial))
            spans.add(span)
        if len(picked) == 2:
            return picked
    pytest.fail("the demo needs two trials with distinct duration spans")


def _rail_app():
    """Apply any deep link, render the real rail for one trial, and publish."""
    from urllib.parse import parse_qs

    import streamlit as st

    from scanpath_studio import api, controls
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    _apply_url_preset()  # app.main's order: the link, then the widgets
    words, fixations = api.load_sample_data()
    pid, tid = st.session_state["_trial"]
    trial_fix = fixations[
        (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
    ]
    st.session_state["_viz"] = controls.render_plot_controls(
        fixations, 16, words=words, fix_range_fixations=trial_fix
    )
    st.session_state["_share_selection"] = {"participant_id": pid, "trial_id": tid}
    query, _caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_params"] = parse_qs(query)


def _rail(trial, **state) -> AppTest:
    at = AppTest.from_function(_rail_app)
    at.session_state["_trial"] = trial
    for key, value in {**COLOURED, **state}.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _rerun(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _app_settings(viz: dict) -> plots.FigureSettings:
    """The render contract the Scanpath view builds from the rail's dict."""
    values = tabs._build_figure_settings(viz, False)
    values.update(x_field=viz["x_field"], y_field=viz["y_field"])
    return plots.FigureSettings.from_mapping(
        values,
        canvas_width=CANVAS[0],
        canvas_height=CANVAS[1],
        base_font_size=16,
    )


def _colour_scales(fig) -> dict:
    """The colour mapping a figure actually draws with.

    A marker with no ``cmin``/``cmax`` is Plotly-autoscaled over its own colour
    array, so the *effective* span is that array's min/max. The word-box
    heatmap is drawn as shapes, whose fills are the scale in effect."""
    markers = []
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if marker is None or marker.colorscale is None:
            continue
        values = marker.color
        if marker.cmin is not None and marker.cmax is not None:
            markers.append((trace.name, float(marker.cmin), float(marker.cmax)))
        elif values is not None and not isinstance(values, str) and len(values):
            markers.append((trace.name, float(min(values)), float(max(values))))
    fills = [
        shape.fillcolor
        for shape in fig.layout.shapes
        if "heatmap" in str(shape.name or "")
    ]
    return {"markers": sorted(markers), "heatmap_fills": fills}


class TestTheDefaultIsTheApis:
    def test_a_default_figure_is_scaled_per_trial_like_the_api(self, demo, two_trials):
        words, fixations = demo
        scales = []
        for trial in two_trials:
            viz = _rail(trial).session_state["_viz"]
            # The builders get the API's own `None`, not a number.
            assert viz["fixation_color_range"] is None
            assert viz["heatmap_range"] is None

            trial_words, trial_fix = _trial_frames(words, fixations, trial)
            app_fig = plots.make_scanpath_figure(
                trial_words, trial_fix, settings=_app_settings(viz)
            )
            api_fig = sps.plot_scanpath(
                words,
                fixations,
                *trial,
                canvas_size=CANVAS,
                show_heatmap=True,
                heatmap_metric="duration_ms",
                color_by="duration_ms",
                show_colorbars=True,
            )
            app_scales = _colour_scales(app_fig)
            assert app_scales["markers"] and app_scales["heatmap_fills"]
            assert app_scales == _colour_scales(api_fig)
            scales.append(app_scales)
        # And "per trial" is real: the two trials are not on one scale.
        assert scales[0]["markers"] != scales[1]["markers"]

    def test_rendering_the_rail_pins_no_range(self, two_trials):
        at = _rail(two_trials[0])
        assert FIX_KEY not in at.session_state
        assert HEAT_KEY not in at.session_state
        assert at.session_state[FIX_AUTO] is True
        assert at.session_state[HEAT_AUTO] is True

    def test_a_comparison_shares_one_scale_across_a_and_b_like_the_api(
        self, demo, two_trials
    ):
        """Compare hands the builder the same `None`, which derives one span
        across A and B — the rule `api.compare_scanpaths` uses."""
        words, fixations = demo
        viz = _rail(two_trials[0], single_compare_toggle=True).session_state["_viz"]
        assert viz["fixation_color_range"] is None
        assert viz["heatmap_range"] is None
        app_fig = plots.make_comparison_figure(
            words, fixations, *two_trials, settings=_app_settings(viz)
        )
        api_fig = sps.compare_scanpaths(
            words,
            fixations,
            *two_trials,
            canvas_size=CANVAS,
            show_heatmap=True,
            heatmap_metric="duration_ms",
            color_by="duration_ms",
            show_colorbars=True,
        )
        assert _colour_scales(app_fig)["markers"] == _colour_scales(api_fig)["markers"]


class TestAnExplicitRange:
    def test_dragging_makes_it_explicit_and_sticky_across_trials(self, two_trials):
        at = _rail(two_trials[0])
        lo, hi = at.slider(key=HEAT_VIEW).value
        chosen = (lo + 10.0, hi - 10.0)
        at.slider(key=HEAT_VIEW).set_value(chosen)
        _rerun(at)
        assert at.session_state[HEAT_KEY] == chosen
        assert at.session_state["_viz"]["heatmap_range"] == chosen
        assert at.session_state[HEAT_AUTO] is False

        at.session_state["_trial"] = two_trials[1]
        _rerun(at)
        assert at.session_state[HEAT_KEY] == chosen
        assert at.session_state["_viz"]["heatmap_range"] == chosen
        assert at.slider(key=HEAT_VIEW).value == chosen
        # The fixation range was never touched, so it is still auto.
        assert FIX_KEY not in at.session_state

    def test_ticking_auto_puts_it_back_to_per_trial(self, two_trials):
        at = _rail(two_trials[0], **{HEAT_KEY: (100.0, 400.0)})
        assert at.session_state[HEAT_AUTO] is False
        at.checkbox(key=HEAT_AUTO).check()
        _rerun(at)
        assert HEAT_KEY not in at.session_state
        assert at.session_state["_viz"]["heatmap_range"] is None

    def test_unticking_auto_pins_the_dataset_wide_scale(self, two_trials):
        """The old default is one click away: comparable trials on one scale."""
        at = _rail(two_trials[0])
        bounds = at.slider(key=FIX_VIEW).value
        at.checkbox(key=FIX_AUTO).uncheck()
        _rerun(at)
        assert at.session_state[FIX_KEY] == bounds
        assert at.session_state["_viz"]["fixation_color_range"] == bounds

    def test_picking_another_colour_column_resets_it(self, demo, two_trials):
        """A range in ms means nothing for another column — it would clamp to a
        one-value span — so choosing another column goes back to auto."""
        _words, fixations = demo
        at = _rail(two_trials[0], **{FIX_KEY: (100.0, 400.0)})
        other = next(
            column
            for column in at.selectbox(key="global_color_by").options
            if column in fixations.columns
            and column != "duration_ms"
            and pd.api.types.is_numeric_dtype(fixations[column])
        )
        at.selectbox(key="global_color_by").set_value(other)
        _rerun(at)
        assert FIX_KEY not in at.session_state
        assert at.session_state["_viz"]["fixation_color_range"] is None


class TestTheLink:
    def test_a_default_figure_puts_no_range_on_the_link(self, two_trials):
        params = _rail(two_trials[0]).session_state["_params"]
        assert "fixation_color_range" not in params
        assert "heatmap_color_range" not in params

    def test_an_explicit_range_travels_and_reopens_as_explicit(self, two_trials):
        at = _rail(two_trials[0])
        lo, hi = at.slider(key=HEAT_VIEW).value
        chosen = (lo + 10.0, hi - 10.0)
        at.slider(key=HEAT_VIEW).set_value(chosen)
        _rerun(at)
        param = at.session_state["_params"]["heatmap_color_range"]
        assert param == [f"{chosen[0]},{chosen[1]}"]

        # The recipient: a fresh session opened from that link.
        opened = AppTest.from_function(_rail_app)
        opened.session_state["_trial"] = two_trials[1]
        for key, value in COLOURED.items():
            opened.session_state[key] = value
        opened.query_params["heatmap_color_range"] = param[0]
        _rerun(opened)
        assert opened.session_state[HEAT_AUTO] is False
        assert opened.session_state["_viz"]["heatmap_range"] == chosen
        assert opened.session_state["_params"]["heatmap_color_range"] == param

    def test_an_old_link_carrying_the_dataset_span_keeps_it(self, two_trials):
        """Every link written before VIZ-46 carried the dataset-wide span the
        rail seeded. It still means "this explicit range"."""
        probe = _rail(two_trials[0])
        bounds = probe.slider(key=FIX_VIEW).value
        opened = AppTest.from_function(_rail_app)
        opened.session_state["_trial"] = two_trials[0]
        for key, value in COLOURED.items():
            opened.session_state[key] = value
        opened.query_params["fixation_color_range"] = f"{bounds[0]},{bounds[1]}"
        _rerun(opened)
        assert opened.session_state[FIX_AUTO] is False
        assert opened.session_state["_viz"]["fixation_color_range"] == bounds

    def test_auto_on_a_linked_page_is_not_undone_by_the_link(self, two_trials):
        """`_apply_url_preset` re-seeds from the query string every rerun, so
        going back to auto has to take the param with it."""
        opened = AppTest.from_function(_rail_app)
        opened.session_state["_trial"] = two_trials[0]
        for key, value in COLOURED.items():
            opened.session_state[key] = value
        opened.query_params["heatmap_color_range"] = "100.0,400.0"
        _rerun(opened)
        assert opened.session_state[HEAT_AUTO] is False
        opened.checkbox(key=HEAT_AUTO).check()
        _rerun(opened)
        _rerun(opened)
        assert HEAT_KEY not in opened.session_state
        assert opened.session_state["_viz"]["heatmap_range"] is None


def _restore_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _restore_plot_config

    st.session_state["_restored"] = _restore_plot_config(
        st.session_state["_config"], pd.DataFrame(), pd.DataFrame()
    )


class TestTheSavedConfig:
    def _restore(self, config: dict, **state) -> AppTest:
        at = AppTest.from_function(_restore_app)
        at.session_state["_config"] = config
        for key, value in state.items():
            at.session_state[key] = value
        return _rerun(at)

    def test_a_config_with_a_range_restores_it_as_explicit(self):
        at = self._restore({"coloring": {"heatmap_range": [120.0, 280.0]}})
        assert at.session_state[HEAT_KEY] == (120.0, 280.0)

    def test_a_config_saved_on_auto_restores_auto(self):
        """`null` is what the writer records for an auto range, so restoring it
        must not keep whatever range this session happened to hold."""
        at = self._restore(
            {"coloring": {"fixation_range": None, "heatmap_range": None}},
            **{FIX_KEY: (1.0, 2.0), HEAT_KEY: (3.0, 4.0)},
        )
        assert FIX_KEY not in at.session_state
        assert HEAT_KEY not in at.session_state

    def test_a_config_without_the_field_leaves_the_range_alone(self):
        at = self._restore(
            {"coloring": {"color_by": "duration_ms"}}, **{HEAT_KEY: (3.0, 4.0)}
        )
        assert at.session_state[HEAT_KEY] == (3.0, 4.0)

    def test_the_writer_records_an_auto_range_as_null(self, two_trials):
        viz = _rail(two_trials[0]).session_state["_viz"]
        config = tabs._build_studio_config(
            selected_participant=two_trials[0][0],
            selected_trial=two_trials[0][1],
            canvas_width=CANVAS[0],
            canvas_height=CANVAS[1],
            x_field="x",
            y_field="y",
            figure_settings=tabs._build_figure_settings(viz, False),
            viz_settings=viz,
            base_font_size=16,
            trial_raw_gaze=pd.DataFrame(),
            font_family="Arial",
            annotation_records=[],
            column_mapping={},
            data_source=None,
            app_version="test",
            exported_at="2026-09-23",
        )
        assert config["coloring"]["fixation_range"] is None
        assert config["coloring"]["heatmap_range"] is None
