"""PERF-17: a replay's page carries its frames packed, and the browser rebuilds them.

Every frame of a replay restates every animated trace at full length, ~33 KB a
frame, so the demo's longest trial was a 12 MB page at the default 361 frames and
66 MB at the finest grid's 2,001. `plots.replay_page` leaves the frames out of
the figure the page serializes and prepends a decoder to the BUG-93 player: frame
0 whole, then only what changed since the frame before, rebuilt with
`Plotly.addFrames` before the player starts.

The figure itself keeps its frames, so the GIF/MP4 export and the API are
untouched. What has to hold is that the browser ends up with the *same* frames:
these tests run the real decoder under node (`fixtures/replay_frames_harness.js`)
and compare what it hands `Plotly.addFrames` with the frames `to_html` used to
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
    _packed_frames_script,
    animation_player_post_script,
    pack_replay_frames,
    replay_page,
)

NODE = shutil.which("node")
HARNESS = Path(__file__).parent / "fixtures" / "replay_frames_harness.js"
needs_node = pytest.mark.skipif(
    NODE is None, reason="needs node to run the replay page's JavaScript"
)

# The demo's longest reading (311 fixations, 81.6 s): 361 frames at the default grid.
LONGEST = ("l37_1129", "l37_1129_2_2_2_Adv_r0")


@functools.cache
def _demo():
    return api.load_sample_data()


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
        # The generic cases the replay builder happens not to produce today —
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
    """Review of #278: values whose `==` raises or lies must still be carried."""

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
        # 12 MB before PERF-17 (361 frames × ~33 KB). The bound leaves room for
        # a layer or two more, not for frames that restate their traces again.
        fig = _replay("longest")
        assert len(fig.frames) == 361
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
