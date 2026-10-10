"""The fixed duration scale for fixation marker sizes.

A fixation's marker size used to be interpolated between the shortest and the
longest duration of whatever was drawn beside it, so one duration was a
different size in every trial, on each side of a comparison and after a filter.
The fixed scale (√ by default, EyeLink Data Viewer's convention of an absolute
mapping) maps one duration range onto the size range for every figure. These
tests pin that: same duration → same size across trials whose durations differ
widely, across comparison sides, replay frames and bulk exports; clamping; the
key; and the migration that keeps older links and settings files relative.
"""

from __future__ import annotations

import io
import json
import math
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import scanpath_studio as sps
from scanpath_studio import api, cli
from scanpath_studio import export as export_mod
from scanpath_studio.constants import (
    DEFAULT_MARKER_DURATION_RANGE,
    DEFAULT_MARKER_SIZE_RANGE,
    DEFAULT_MARKER_SIZE_SCALE,
)
from scanpath_studio.plots import _compute_marker_sizes
from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA, _migrate_plot_config

LO_SIZE, HI_SIZE = DEFAULT_MARKER_SIZE_RANGE


def _size(duration: float, **kwargs) -> float:
    return float(_compute_marker_sizes(pd.Series([duration]), **kwargs)[0])


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


def test_default_is_fixed_sqrt_50_to_600():
    assert DEFAULT_MARKER_SIZE_SCALE == "sqrt"
    assert tuple(DEFAULT_MARKER_DURATION_RANGE) == (50, 600)
    options = api.figure_options("static")
    assert options["marker_size_scale"] == "sqrt"
    assert tuple(options["marker_duration_range"]) == (50, 600)
    assert options["duration_size_legend"] is True
    for kind in ("animation", "comparison"):
        assert api.figure_options(kind)["marker_size_scale"] == "sqrt"


@pytest.mark.parametrize("scale", ["sqrt", "linear", "log"])
def test_a_duration_has_one_size_whatever_surrounds_it(scale):
    alone = _size(200, scale=scale)
    for context in ([10, 200], [200, 5000], [190, 200, 210], [200] * 4):
        sizes = _compute_marker_sizes(pd.Series(context), scale=scale)
        assert sizes[context.index(200)] == pytest.approx(alone)


@pytest.mark.parametrize("scale", ["sqrt", "linear", "log"])
def test_bounds_map_to_the_size_range_and_beyond_them_clamp(scale):
    assert _size(50, scale=scale) == pytest.approx(LO_SIZE)
    assert _size(600, scale=scale) == pytest.approx(HI_SIZE)
    assert _size(5, scale=scale) == pytest.approx(LO_SIZE)
    assert _size(4000, scale=scale) == pytest.approx(HI_SIZE)
    # A missing duration is the smallest marker, never a NaN size.
    assert _size(float("nan"), scale=scale) == pytest.approx(LO_SIZE)
    grid = _compute_marker_sizes(pd.Series(np.linspace(50, 600, 12)), scale=scale)
    assert np.all(np.diff(grid) > 0)


def test_the_curves_differ_as_documented():
    # √: the duration whose square root is midway draws the midway diameter.
    mid = ((math.sqrt(50) + math.sqrt(600)) / 2) ** 2
    assert _size(mid, scale="sqrt") == pytest.approx((LO_SIZE + HI_SIZE) / 2)
    assert _size(325, scale="linear") == pytest.approx((LO_SIZE + HI_SIZE) / 2)
    assert _size(math.sqrt(50 * 600), scale="log") == pytest.approx(
        (LO_SIZE + HI_SIZE) / 2
    )
    # At 200 ms log > √ > linear: the more compressive curve grows sooner.
    assert (
        _size(200, scale="log") > _size(200, scale="sqrt") > _size(200, scale="linear")
    )


def test_custom_bounds_and_size_range():
    kwargs = dict(size_range=(4, 40), duration_range=(100, 1000))
    assert _size(100, scale="linear", **kwargs) == pytest.approx(4)
    assert _size(550, scale="linear", **kwargs) == pytest.approx(22)
    assert _size(2000, scale="linear", **kwargs) == pytest.approx(40)


def test_relative_is_the_old_per_set_stretch():
    sizes = _compute_marker_sizes(pd.Series([100, 200, 300]), scale="relative")
    assert list(sizes) == pytest.approx([LO_SIZE, 16, HI_SIZE])
    flat = _compute_marker_sizes(pd.Series([150, 150]), scale="relative")
    assert list(flat) == pytest.approx([16, 16])


def test_an_unknown_scale_is_refused():
    with pytest.raises(ValueError, match="marker_size_scale"):
        _size(200, scale="cubic")


# ---------------------------------------------------------------------------
# Every figure path
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample():
    return api.load_sample_data(names="canonical")


def _trial(fixations, pid, tid):
    sel = fixations[
        (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
    ]
    return sel.sort_values("timestamp_ms")


@pytest.fixture(scope="module")
def contrasting_trials(sample):
    """Two readings whose duration ranges differ the most in the demo."""
    _, fixations = sample
    spans = (
        fixations.groupby(["participant_id", "trial_id"])["duration_ms"]
        .agg(["min", "max"])
        .reset_index()
    )
    low = spans.sort_values("max").iloc[0]
    high = spans.sort_values("max").iloc[-1]
    assert high["max"] - low["max"] > 300  # the premise: very different ranges
    return (low["participant_id"], low["trial_id"]), (
        high["participant_id"],
        high["trial_id"],
    )


def _marker_trace(fig, name="Fixations"):
    (trace,) = [t for t in fig.data if t.name == name]
    return trace


def _assert_one_size_per_duration(pairs):
    by_duration = defaultdict(set)
    for duration, size in pairs:
        by_duration[float(duration)].add(round(float(size), 9))
    shared = [d for d, sizes in by_duration.items() if len(sizes) > 1]
    assert not shared, f"durations drawn at several sizes: {shared[:5]}"
    for duration, (size,) in by_duration.items():
        assert size == pytest.approx(_size(duration))


def test_static_figures_share_the_scale_across_trials(sample, contrasting_trials):
    words, fixations = sample
    pairs = []
    for pid, tid in contrasting_trials:
        fig = sps.plot_scanpath(words, fixations, pid, tid)
        sizes = _marker_trace(fig).marker.size
        durations = _trial(fixations, pid, tid)["duration_ms"]
        assert len(sizes) == len(durations)
        pairs += list(zip(durations, sizes))
    _assert_one_size_per_duration(pairs)
    # Some duration actually occurs in both, so the check above compared them.
    (a, b) = (set(_trial(fixations, *t)["duration_ms"]) for t in contrasting_trials)
    assert a & b


def test_relative_scale_still_differs_across_trials(sample, contrasting_trials):
    """The control: the old scale does rescale per trial — which is what the
    fixed one exists to stop, and what proves the test above can fail."""
    words, fixations = sample
    pairs = []
    for pid, tid in contrasting_trials:
        fig = sps.plot_scanpath(
            words, fixations, pid, tid, marker_size_scale="relative"
        )
        pairs += list(
            zip(
                _trial(fixations, pid, tid)["duration_ms"],
                _marker_trace(fig).marker.size,
            )
        )
    by_duration = defaultdict(set)
    for duration, size in pairs:
        by_duration[float(duration)].add(round(float(size), 6))
    assert any(len(sizes) > 1 for sizes in by_duration.values())


def test_a_fixation_filter_does_not_rescale(sample, contrasting_trials):
    words, fixations = sample
    pid, tid = contrasting_trials[1]
    flags = {"long": {"mode": "Discard", "threshold_ms": 400.0}}
    fig = sps.plot_scanpath(words, fixations, pid, tid, fixation_flags=flags)
    kept = _trial(fixations, pid, tid)
    kept = kept[kept["duration_ms"] <= 400]
    sizes = _marker_trace(fig).marker.size
    assert len(sizes) == len(kept)
    _assert_one_size_per_duration(zip(kept["duration_ms"], sizes))


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_both_comparison_sides_share_the_scale(sample, contrasting_trials, layout):
    words, fixations = sample
    (pa, ta), (pb, tb) = contrasting_trials
    fig = sps.compare_scanpaths(words, fixations, (pa, ta), (pb, tb), layout=layout)
    marker_traces = [
        t
        for t in fig.data
        if t.mode
        and "markers" in t.mode
        and t.marker.size is not None
        and np.ndim(t.marker.size) == 1
        and len(t.marker.size) > 1
    ]
    assert len(marker_traces) == 2
    pairs = []
    for trace, (pid, tid) in zip(marker_traces, contrasting_trials):
        durations = _trial(fixations, pid, tid)["duration_ms"]
        assert len(trace.marker.size) == len(durations)
        pairs += list(zip(durations, trace.marker.size))
    _assert_one_size_per_duration(pairs)


def _replay_trail(fig):
    """The last frame's fixation trail — every fixation, in reading order."""
    last = fig.frames[-1].data
    return max(
        (t for t in last if t.mode == "markers" and np.ndim(t.marker.size) == 1),
        key=lambda t: len(t.marker.size),
    )


def test_replays_share_the_scale_single_and_co_animated(sample, contrasting_trials):
    words, fixations = sample
    pairs = []
    for pid, tid in contrasting_trials:
        fig = sps.animate_scanpath(words, fixations, pid, tid)
        trail = _replay_trail(fig)
        durations = _trial(fixations, pid, tid)["duration_ms"]
        assert len(trail.marker.size) == len(durations)
        pairs += list(zip(durations, trail.marker.size))
        # Every frame draws a fixation at the size it has in the last one.
        for frame in fig.frames[1:-1:40]:
            for trace in frame.data:
                if trace.mode == "markers" and np.ndim(trace.marker.size) == 1:
                    n = len(trace.marker.size)
                    if 1 < n <= len(durations):
                        assert list(trace.marker.size) == pytest.approx(
                            list(trail.marker.size[:n])
                        )
    _assert_one_size_per_duration(pairs)


def test_bulk_export_figures_share_the_scale(sample, contrasting_trials, monkeypatch):
    words, fixations = sample
    built = []
    real = export_mod.make_scanpath_figure

    def spy(trial_words, trial_fixations, **kwargs):
        fig = real(trial_words, trial_fixations, **kwargs)
        built.append((trial_fixations.sort_values("timestamp_ms"), fig))
        return fig

    monkeypatch.setattr(export_mod, "make_scanpath_figure", spy)
    combos = pd.DataFrame(
        [{"participant_id": p, "trial_id": t} for p, t in contrasting_trials]
    )
    settings = {
        "show_fixations": True,
        "show_saccades": False,
        "marker_size_range": DEFAULT_MARKER_SIZE_RANGE,
        "marker_size_scale": "sqrt",
        "marker_duration_range": DEFAULT_MARKER_DURATION_RANGE,
        "duration_size_legend": False,
    }
    options = export_mod.ExportOptions(
        include_png=False, include_svg=False, include_html=True
    )
    zip_bytes, progress = export_mod.bulk_export(
        combos,
        words,
        fixations,
        canvas_width=2560,
        canvas_height=1440,
        base_font_size=24,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=settings,
        options=options,
    )
    assert progress.errors == []
    assert len(built) == 2
    pairs = []
    for trial_fix, fig in built:
        pairs += list(zip(trial_fix["duration_ms"], _marker_trace(fig).marker.size))
    _assert_one_size_per_duration(pairs)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        configs = [n for n in zf.namelist() if n.endswith("plot_config.json")]
        assert configs
        for name in configs:
            sizing = json.loads(zf.read(name))["sizing"]
            assert sizing["marker_size_scale"] == "sqrt"
            assert sizing["marker_duration_range"] == [50, 600]
            assert sizing["duration_size_legend"] is False


# ---------------------------------------------------------------------------
# The key
# ---------------------------------------------------------------------------


def _key_labels(fig):
    return [a.text for a in fig.layout.annotations if a.name == "duration_size_key"]


def test_the_key_labels_the_bounds_and_round_durations(sample, contrasting_trials):
    words, fixations = sample
    pid, tid = contrasting_trials[0]
    fig = sps.plot_scanpath(words, fixations, pid, tid)
    assert _key_labels(fig) == ["≤50", "100", "200", "400", "≥600 ms"]
    circles = [s for s in fig.layout.shapes if s.type == "circle"]
    diameters = [s.x1 - s.x0 for s in circles]
    assert diameters == pytest.approx(
        list(_compute_marker_sizes(pd.Series([50, 100, 200, 400, 600])))
    )
    assert all(s.xsizemode == "pixel" and s.ysizemode == "pixel" for s in circles)


def test_the_key_is_on_every_fixed_scale_figure_and_toggles(sample, contrasting_trials):
    words, fixations = sample
    (pa, ta), (pb, tb) = contrasting_trials
    assert _key_labels(sps.animate_scanpath(words, fixations, pa, ta))
    assert _key_labels(sps.compare_scanpaths(words, fixations, (pa, ta), (pb, tb)))
    for off in (
        dict(duration_size_legend=False),
        dict(marker_size_scale="relative"),
        dict(show_fixations=False),
    ):
        assert not _key_labels(sps.plot_scanpath(words, fixations, pa, ta, **off))
    # Two scanpaths at different px ranges have no single key to share.
    split = sps.compare_scanpaths(
        words,
        fixations,
        (pa, ta),
        (pb, tb),
        style_b={"marker_size_range": (4, 12)},
    )
    assert not _key_labels(split)


def _illustration_stamp(fig):
    (stamp,) = [a for a in fig.layout.annotations if a.name == "illustration_label"]
    return stamp


def test_the_illustration_stamp_sits_above_the_key(sample, contrasting_trials):
    from scanpath_studio.plots import _add_duration_size_key, add_illustration_label

    words, fixations = sample
    pid, tid = contrasting_trials[0]
    key_top = HI_SIZE + 8 + 16  # pad + label row + the largest circle

    # Key first, stamp after.
    fig = sps.plot_scanpath(words, fixations, pid, tid)
    assert _key_labels(fig)
    add_illustration_label(fig, ["schematic"])
    assert _illustration_stamp(fig).yshift >= key_top

    # Stamp first, key after (the app's replay order).
    fig = sps.plot_scanpath(words, fixations, pid, tid, duration_size_legend=False)
    add_illustration_label(fig, ["schematic"])
    assert not _illustration_stamp(fig).yshift
    _add_duration_size_key(
        fig, DEFAULT_MARKER_SIZE_RANGE, "sqrt", DEFAULT_MARKER_DURATION_RANGE
    )
    assert _illustration_stamp(fig).yshift >= key_top


# ---------------------------------------------------------------------------
# Saved settings files and Share links
# ---------------------------------------------------------------------------


def test_an_older_settings_file_keeps_the_relative_scale():
    old = {"schema": 4, "sizing": {"marker_size_range": [8, 24]}, "layers": {}}
    migrated, note = _migrate_plot_config(old)
    assert note is None
    assert migrated["schema"] == PLOT_CONFIG_SCHEMA == 8
    assert migrated["sizing"]["marker_size_scale"] == "relative"
    assert "marker_size_scale" not in old["sizing"]  # the caller's dict is untouched
    # A schema-1 file walks the whole chain to the same answer.
    v1, _ = _migrate_plot_config({"sizing": {"marker_size_range": [8, 24]}})
    assert v1["sizing"]["marker_size_scale"] == "relative"


def test_the_migration_leaves_current_and_annotation_only_files_alone():
    current = {"schema": 5, "sizing": {"marker_size_scale": "log"}}
    assert _migrate_plot_config(current)[0]["sizing"]["marker_size_scale"] == "log"
    notes_only = {"schema": 4, "annotations": []}
    assert "sizing" not in _migrate_plot_config(notes_only)[0]


def test_a_design_file_from_before_the_scale_keeps_the_relative_scale():
    from scanpath_studio import controls

    old = json.dumps(
        {
            "kind": controls.DESIGNS_FILE_KIND,
            "schema": 1,
            "designs": {
                "Paper": {"global_show_fix": True},
                "Chosen": {"global_marker_size_scale": "log"},
            },
        }
    )
    designs = controls.designs_from_json(old)
    assert designs["Paper"]["global_marker_size_scale"] == "relative"
    assert designs["Chosen"]["global_marker_size_scale"] == "log"
    # A current file is read as written: a design saved now carries the key.
    current = controls.designs_to_json({"New": {"global_show_fix": True}})
    assert json.loads(current)["schema"] == controls.DESIGNS_FILE_SCHEMA == 2
    assert controls.designs_from_json(current) == {"New": {"global_show_fix": True}}


def test_a_cached_session_from_before_the_scale_keeps_the_relative_scale():
    from scanpath_studio.persistence import _restorable_session
    from scanpath_studio.session_keys import DESIGN_PRESETS

    restored = _restorable_session(
        {
            "global_show_fix": True,
            DESIGN_PRESETS: {"Old": {"global_show_heatmap": True}},
        }
    )
    assert restored["global_marker_size_scale"] == "relative"
    assert restored[DESIGN_PRESETS]["Old"]["global_marker_size_scale"] == "relative"
    # A session saved since carries its own scale; one with no plot settings
    # gains none.
    assert (
        _restorable_session({"global_marker_size_scale": "sqrt"})[
            "global_marker_size_scale"
        ]
        == "sqrt"
    )
    assert "global_marker_size_scale" not in _restorable_session(
        {"main_nav": "scanpath"}
    )


def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_seen"] = {
        key: st.session_state.get(key)
        for key in (
            "global_marker_size_scale",
            "global_marker_duration_range",
            "global_duration_size_legend",
        )
    }


def _open_link(params: dict) -> dict:
    at = AppTest.from_function(_link_app)
    for key, value in params.items():
        at.query_params[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert [w.value for w in at.warning] == []
    return at.session_state["_seen"]


def test_a_link_that_predates_the_scale_reopens_relative():
    seen = _open_link({"trial_id": "t1", "show_fixations": "1", "show_saccades": "1"})
    assert seen["global_marker_size_scale"] == "relative"


def test_a_link_with_the_scale_reopens_on_it():
    seen = _open_link(
        {
            "show_fixations": "1",
            "marker_size_scale": "log",
            "marker_duration_range": "80,900",
            "duration_size_legend": "0",
        }
    )
    assert seen == {
        "global_marker_size_scale": "log",
        "global_marker_duration_range": (80, 900),
        "global_duration_size_legend": False,
    }


def test_the_size_key_toggle_alone_does_not_mark_an_old_link():
    # `duration_size_legend` came in with the scale, so it cannot mean the
    # link predates it.
    seen = _open_link({"trial_id": "t1", "duration_size_legend": "0"})
    assert seen["global_marker_size_scale"] is None  # the seeded default
    assert seen["global_duration_size_legend"] is False


def test_a_bare_trial_link_gets_the_new_default():
    seen = _open_link({"trial_id": "t1"})
    assert seen["global_marker_size_scale"] is None  # left to the seeded default


def test_a_hand_written_out_of_range_link_is_clamped():
    seen = _open_link({"marker_size_scale": "sqrt", "marker_duration_range": "1,99999"})
    assert seen["global_marker_duration_range"] == (10, 3000)


def _round_trip_app():
    from urllib.parse import parse_qs

    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    st.session_state["global_show_fix"] = True
    st.session_state["global_marker_size_scale"] = "linear"
    st.session_state["global_marker_duration_range"] = (70, 800)
    st.session_state["global_duration_size_legend"] = False
    query, _ = _build_share_query(DEMO_CHOICE)
    st.session_state["_query"] = query
    for key in (
        "global_marker_size_scale",
        "global_marker_duration_range",
        "global_duration_size_legend",
    ):
        del st.session_state[key]
    st.query_params.clear()
    for key, values in parse_qs(query).items():
        st.query_params[key] = values[0]
    _apply_url_preset()


def test_the_share_link_round_trips_the_scale():
    at = AppTest.from_function(_round_trip_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert "marker_size_scale=linear" in at.session_state["_query"]
    assert at.session_state["global_marker_size_scale"] == "linear"
    assert at.session_state["global_marker_duration_range"] == (70, 800)
    assert at.session_state["global_duration_size_legend"] is False


# ---------------------------------------------------------------------------
# API ↔ CLI
# ---------------------------------------------------------------------------


def test_the_cli_draws_what_the_api_draws(monkeypatch, sample, contrasting_trials):
    words, fixations = sample
    pid, tid = contrasting_trials[1]
    drawn = []
    real = api.plot_scanpath

    def spy(*args, **kwargs):
        fig = real(*args, **kwargs)
        drawn.append(fig)
        return fig

    monkeypatch.setattr(api, "plot_scanpath", spy)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **kwargs: path)
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            pid,
            "-t",
            tid,
            "--marker-size-scale",
            "log",
            "--marker-duration-range",
            "80",
            "900",
            "--no-duration-size-legend",
            "-o",
            "unused.html",
        ]
    )
    (rendered,) = drawn
    expected = real(
        words,
        fixations,
        pid,
        tid,
        marker_size_scale="log",
        marker_duration_range=(80, 900),
        duration_size_legend=False,
    )
    sizes = _marker_trace(rendered).marker.size
    assert list(sizes) == pytest.approx(list(_marker_trace(expected).marker.size))
    durations = _trial(fixations, pid, tid)["duration_ms"]
    assert list(sizes) == pytest.approx(
        list(_compute_marker_sizes(durations, scale="log", duration_range=(80, 900)))
    )
    assert not _key_labels(rendered)
