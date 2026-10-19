"""A replay's page carries its frames packed, and the browser rebuilds them.

Every frame of a replay restates every animated trace at full length, ~33 KB a
frame, so unpacked the demo's longest trial would be a 12 MB page at the default
361 frames and 66 MB at the finest grid's 2,001. `plots.replay_page` leaves the
frames out of the figure the page serializes and prepends a decoder to the
wall-clock replay player: frame 0 whole, then only what changed since the frame
before, rebuilt with `Plotly.addFrames` before the player starts.

The figure itself keeps its frames, so the GIF/MP4 export and the API are
untouched. What has to hold is that the browser ends up with the *same* frames:
these tests run the real decoder under node (`fixtures/replay_frames_harness.js`)
and compare what it hands `Plotly.addFrames` with the frames `to_html` would
write.
"""

from __future__ import annotations

import copy
import functools
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from plotly.io.json import to_json_plotly

from scanpath_studio import api, tabs
from scanpath_studio.plots import (
    _CONTROLS_MARGIN_PX,
    _CONTROLS_SAFETY_PX,
    REPLAY_TOOLBAR_PX,
    _packed_frames_script,
    animation_player_post_script,
    pack_replay_frames,
    replay_page,
    replay_page_box,
)

NODE = shutil.which("node")
HARNESS = Path(__file__).parent / "fixtures" / "replay_frames_harness.js"
needs_node = pytest.mark.skipif(
    NODE is None, reason="needs node to run the replay page's JavaScript"
)

# The demo's longest reading (311 fixations, 81.6 s): 360 frames at the default grid.
LONGEST = ("l37_1129", "l37_1129_2_2_2_Adv")


@functools.cache
def _demo():
    return api.load_sample_data(names="canonical")


@functools.cache
def _replay(kind: str):
    words, fixations = _demo()
    pid, tid = LONGEST
    if kind == "longest":
        return api.animate_scanpath(words, fixations, pid, tid)
    if kind == "single":
        # Every layer the single replay animates: the trail (coloured by a
        # metric), index labels, saccades + arrowheads, the current-fixation ring
        # and a Highlight flag overlay — on a Fine grid.
        return api.animate_scanpath(
            words,
            fixations,
            pid,
            tid,
            fix_index_range=(1, 40),
            show_order=True,
            show_saccade_arrows=True,
            color_by="duration_ms",
            fixation_flags={"short": {"mode": "Highlight", "threshold_ms": 150}},
            anim_grid_step_ms=40,
            anim_max_frames=900,
        )
    # The Animate + Compare co-animation: two trails on one clock.
    other = api.list_trials(words, fixations)
    pid_b, tid_b = other[other.participant_id != pid].iloc[0]
    return api.animate_scanpath(
        words,
        fixations,
        pid,
        tid,
        fix_index_range=(1, 30),
        trial_b=(pid_b, tid_b),
        fix_index_range_b=(1, 30),
        show_saccade_arrows=True,
    )


def _decode(script: str, tmp_path) -> dict:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"script": script}), encoding="utf-8")
    done = subprocess.run(
        [NODE, str(HARNESS), str(path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(done.stdout)


def _same(a, b) -> bool:
    """JSON-value equality as JavaScript sees it: ``1 == 1.0``, ``True != 1``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _as_written(frames) -> list:
    """The frames as `to_html` wrote them into the page, read back."""
    return json.loads(to_json_plotly(frames))


class TestTheBrowserGetsTheSameFrames:
    @needs_node
    @pytest.mark.parametrize("kind", ["single", "dual"])
    def test_decoded_frames_equal_the_frames_the_page_used_to_carry(
        self, kind, tmp_path
    ):
        fig = _replay(kind)
        _page, script = replay_page(fig)
        decoded = _decode(script, tmp_path)
        expected = _as_written(fig.to_dict()["frames"])
        assert decoded["calls"] == 1
        assert len(decoded["frames"]) == len(expected) > 50
        assert _same(decoded["frames"], expected)

    @needs_node
    def test_every_kind_of_change_survives_the_round_trip(self, tmp_path):
        # The generic cases the replay builder happens not to produce —
        # a key that appears or goes, a type that changes, a bool that must not
        # become 1, a patched and a resized array, an ndarray, a frame without
        # `traces`, a frame-level key, unicode and markup in strings.
        frames = [
            {
                "name": "0",
                "traces": [3, 5],
                "data": [
                    {"x": [1, None, None], "marker": {"size": 4, "line": {"w": 1}}},
                    {"text": ["a", "b"], "visible": True},
                ],
            },
            {
                "name": "1",
                "traces": [3, 5],
                "data": [
                    {"x": [1, 2, None], "marker": {"size": 4}},
                    {"text": ["a", "</script>"], "visible": 1},
                ],
            },
            {
                "name": "2",
                "traces": [5, 3],
                "data": [
                    {"text": None, "extra": {"k": [1.5]}},
                    {"x": [1, 2, 3, 4], "marker": {"size": [4, 5]}},
                ],
            },
            {
                "name": "3",
                "group": "g",
                "data": [
                    {"customdata": np.array([[1, 2.5], [3, 4.0]])},
                    {"text": ["{plot_id}", "ü → 😀"]},
                ],
            },
            {
                "name": "4",
                "data": [
                    {"customdata": np.array([[1, 2.5], [3, 9.0]])},
                    {"text": ["{plot_id}", "ü → 😀"]},
                ],
            },
            {"name": "5"},
        ]
        decoded = _decode(_packed_frames_script(frames), tmp_path)
        assert _same(decoded["frames"], _as_written(frames))


class TestValuesTheEncoderMustNotMisjudge:
    """Values whose `==` raises or lies must still be carried."""

    def test_pd_na_against_none_is_carried_not_raised(self):
        # A nullable (`Int64`) fixation column reaches a frame as `pd.NA`, where
        # the frame before held `None`; `None != pd.NA` raises TypeError.
        frames = [
            {"data": [{"x": [1, None]}]},
            {"data": [{"x": [1, pd.NA]}]},
            {"data": [{"x": pd.NA}]},
            {"data": [{"x": None}]},
        ]
        packed = pack_replay_frames(frames)
        assert packed[1]["p"][0] is not None
        assert packed[2]["p"][0] is not None
        assert packed[3]["p"][0] is not None

    def test_a_zero_that_changes_sign_is_carried(self):
        frames = [
            {"data": [{"x": [0.0, 1.0], "y": 0.0}]},
            {"data": [{"x": [-0.0, 1.0], "y": -0.0}]},
            {"data": [{"x": [-0.0, 1.0], "y": -0.0}]},
        ]
        packed = pack_replay_frames(frames)
        changed = packed[1]["p"][0][1]
        assert math.copysign(1.0, changed["y"][1]) == -1.0
        assert math.copysign(1.0, changed["x"][1][0]) == -1.0
        assert packed[2]["p"][0] is None

    def test_a_null_data_key_is_kept(self):
        packed = pack_replay_frames([{"name": "0", "data": None}])
        assert packed == [{"name": "0", "data": None}]

    def test_typed_array_traces_travel_unpacked_on_the_player(self):
        fig_dict = _replay("single").to_dict()
        for frame in fig_dict["frames"]:
            frame["traces"] = {"dtype": "i1", "bdata": "AQI="}
        figure, script = replay_page(fig_dict)
        assert figure["frames"] is fig_dict["frames"]
        assert script == animation_player_post_script(fig_dict)


class TestThePageIsSmall:
    def test_the_longest_demo_trial_is_a_small_page(self):
        # 12 MB unpacked (361 frames × ~33 KB). The bound leaves room for
        # a layer or two more, not for frames that restate their traces again.
        fig = _replay("longest")
        assert len(fig.frames) == 360
        markup = tabs._true_scale_plot_html(fig, key="k", figure_dict=fig.to_dict())
        assert len(markup.encode()) < 500_000
        assert "Plotly.addFrames('" not in markup  # plotly.py's own, unpacked

    def test_a_frame_that_changes_nothing_costs_next_to_nothing(self):
        fig = _replay("single")
        frames = fig.to_dict()["frames"]
        packed = pack_replay_frames(frames)
        later = len(to_json_plotly(packed[1:])) / (len(packed) - 1)
        first = len(to_json_plotly(packed[:1]))
        assert later < first / 20


class TestTheFigureIsUntouched:
    def test_the_figure_dict_keeps_its_frames(self):
        # The cached view hands the same dict to the GIF/MP4 export afterwards.
        fig = _replay("single")
        figure_dict = fig.to_dict()
        before = copy.deepcopy(figure_dict)
        page, script = replay_page(figure_dict)
        assert "frames" not in page
        assert figure_dict["frames"] and _same(
            _as_written(figure_dict), _as_written(before)
        )
        assert {k: v for k, v in before.items() if k != "frames"}.keys() == page.keys()
        assert script.endswith(animation_player_post_script(fig))

    def test_a_static_figure_has_no_page_of_its_own(self):
        words, fixations = _demo()
        static = api.plot_scanpath(words, fixations, *LONGEST)
        assert replay_page(static) is None
        assert replay_page(static.to_dict()) is None


class TestEverySurfaceCarriesThePackedFrames:
    def test_the_embed_the_download_and_save_figure(self, tmp_path):
        fig = _replay("single")
        _page, script = replay_page(fig)
        embed = tabs._true_scale_plot_html(fig, key="k")
        download = tabs._animation_html(fig)
        path = api.save_figure(fig, tmp_path / "replay.html")
        saved = path.read_text(encoding="utf-8")
        for html in (embed, download, saved):
            assert "var packed = [" in html
            assert "Plotly.addFrames('" not in html
            # One replay, one serialization: the three carry the same frames.
            packed = re.search(r"var packed = (\[.*?\]);\n", html).group(1)
            assert packed == re.search(r"var packed = (\[.*?\]);\n", script).group(1)
        # The cached view's dict path writes the same markup as the figure path.
        assert (
            tabs._true_scale_plot_html(fig, key="k", figure_dict=fig.to_dict()) == embed
        )
        # A full page names its div with a fresh uuid each time.
        uuid = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        )
        assert uuid.sub("id", tabs._animation_html(fig.to_dict())) == uuid.sub(
            "id", download
        )


class TestThePageDrawsTheToolbarAboveTheFigure:
    """The figure keeps Plotly's own transport controls in a band above the
    plot, for `fig.show()`. A page hides them, takes the band back — so the
    replay's plot is the static figure's size — and the player draws its
    compact toolbar above the figure instead."""

    def test_the_page_is_the_static_figures_size(self):
        words, fixations = _demo()
        static = api.plot_scanpath(words, fixations, *LONGEST)
        fig = _replay("longest")
        page, _script = replay_page(fig)
        layout = page["layout"]
        assert (layout["width"], layout["height"]) == (
            static.layout.width,
            static.layout.height,
        )
        assert layout["margin"]["t"] == (static.layout.margin.t or 0)
        assert [m["visible"] for m in layout["updatemenus"]] == [False]
        assert [s["visible"] for s in layout["sliders"]] == [False]
        assert layout["meta"]["scanpath_toolbar"] == REPLAY_TOOLBAR_PX
        assert replay_page_box(fig) == (
            static.layout.width,
            static.layout.height,
            REPLAY_TOOLBAR_PX,
        )
        assert replay_page_box(fig.to_dict()) == replay_page_box(fig)
        # The figure itself keeps its controls and its band, for fig.show().
        assert fig.layout.height == static.layout.height + (
            _CONTROLS_MARGIN_PX + _CONTROLS_SAFETY_PX
        )
        assert fig.layout.updatemenus[0].visible is not False
        assert "scanpath_toolbar" not in fig.layout.meta

    def test_a_title_stays_above_the_plot(self):
        words, fixations = _demo()
        fig = api.animate_scanpath(words, fixations, *LONGEST, title="A title")
        page, _script = replay_page(fig)
        layout = page["layout"]
        assert layout["title"]["text"] == "A title"
        assert layout["margin"]["t"] == fig.layout.margin.t - _CONTROLS_MARGIN_PX > 0
        assert layout["height"] == fig.layout.height - (
            _CONTROLS_MARGIN_PX + _CONTROLS_SAFETY_PX
        )

    def test_a_legend_above_the_plot_keeps_its_own_room(self):
        # A legend moved above the plot grows the figure past the controls'
        # band, so the page, which takes the band back, still has room for it.
        words, fixations = _demo()
        pid_b, tid_b = "l7_1090", "l7_1090_2_2_2_Adv"
        kwargs = dict(trial_b=(pid_b, tid_b), fix_index_range=(1, 20))
        plain = api.animate_scanpath(words, fixations, *LONGEST, **kwargs)
        above = api.animate_scanpath(
            words,
            fixations,
            *LONGEST,
            legend_layout={
                "compare": {
                    "position": "top-center-outside",
                    "arrangement": "stacked",
                    "size": 40,
                }
            },
            **kwargs,
        )
        grown = above.layout.margin.t - plain.layout.margin.t
        assert grown > 0
        page, _script = replay_page(above)
        assert page["layout"]["margin"]["t"] == pytest.approx(grown)

    def test_toolbar_false_keeps_the_figures_own_controls(self):
        fig = _replay("longest")
        page, _script = replay_page(fig, toolbar=False)
        layout = page["layout"]
        assert layout["height"] == fig.layout.height
        assert "visible" not in layout["updatemenus"][0]
        assert "scanpath_toolbar" not in layout["meta"]

    def test_the_app_embed_leaves_a_slot_above_the_figure(self):
        fig = _replay("longest")
        width, height, toolbar = replay_page_box(fig)
        html, iframe_height = tabs._true_scale_html(
            "<div></div>",
            key="k",
            width=width,
            height=height,
            max_height=None,
            zoomable=True,
            fit_window=True,
            toolbar=toolbar,
        )
        slot = html.index('<div id="truescale-k-transport" style="height:32px;')
        fit = html.index('id="fit-k"')
        # The zoom buttons end the toolbar row, not float over the plot's
        # top-left, where the title or the legend is.
        zoom = html.index('id="zoombar-k"')
        assert slot < zoom < fit
        assert "order:99;" in html[zoom : html.index(">", zoom)]
        assert "position:absolute" not in html[zoom : html.index(">", zoom)]
        assert "var BAR = 32;" in html
        assert iframe_height == height + 12 + REPLAY_TOOLBAR_PX
        static_html, static_height = tabs._true_scale_html(
            "<div></div>",
            key="k",
            width=width,
            height=height,
            max_height=None,
            zoomable=True,
        )
        assert '<div id="truescale-k-transport"' not in static_html
        assert "var BAR = 0;" in static_html
        zoom = static_html.index('id="zoombar-k"')
        assert "position:absolute" in static_html[zoom : static_html.index(">", zoom)]
        assert static_height == height + 12

    def test_a_first_replay_reserves_the_toolbar_not_the_band(self):
        from scanpath_studio import loading

        width, height = loading.estimate_plot_size(2560, 1440)
        assert loading.estimate_plot_size(2560, 1440, animation=True) == (
            width,
            height + REPLAY_TOOLBAR_PX,
        )
