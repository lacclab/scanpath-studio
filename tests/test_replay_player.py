"""The animated replay runs on the wall clock, not on Plotly's frame queue.

Plotly's own ▶ Play holds every frame until the first display tick *after* its
duration and starts the next frame's clock from there, so each hold rounds up to
whole ticks and the rounding piles up: on a 60 Hz screen a 40 ms frame (Fine, ×1)
lasts 50 ms, and a 20.8 s reading replays in 26 s. The HTML surfaces therefore
carry `plots.animation_player_post_script`, which shows whichever frame the
elapsed wall time has reached. These tests run that script under node against a
fake Plotly on a simulated 60 Hz display (`fixtures/replay_player_harness.js`)
and check when every frame reaches the screen.
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio.plots import (
    REPLAY_TOOLBAR_PX,
    animation_player_post_script,
    make_scanpath_animation,
    replay_page,
)

NODE = shutil.which("node")
HARNESS = Path(__file__).parent / "fixtures" / "replay_player_harness.js"
TICK_MS = 1000 / 60

pytestmark = pytest.mark.skipif(
    NODE is None, reason="needs node to run the replay player's JavaScript"
)


def _fixations(n: int = 53, gap_ms: float = 400.0) -> pd.DataFrame:
    # Onsets 0, 400, …, 20 800 ms, each 200 ms long: a 21 s reading.
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * n,
            "trial_id": ["t1"] * n,
            "x": [100.0 + 10 * i for i in range(n)],
            "y": [100.0] * n,
            "duration_ms": [200.0] * n,
            "timestamp_ms": [i * gap_ms for i in range(n)],
            "order_in_trial": list(range(1, n + 1)),
        }
    )


def _words() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [1, 2, 3],
            "x": [100, 200, 300],
            "y": [50, 50, 50],
            "width": [50, 50, 50],
            "height": [50, 50, 50],
            "text": ["word1", "word2", "word3"],
            "text_id": ["para1"] * 3,
            "line_idx": [1, 1, 1],
        }
    )


# Built once per (speed, autoplay): 526 frames take a couple of seconds, and no
# test changes the figure.
@functools.cache
def _replay(*, speed: float = 1.0, autoplay: bool = True):
    """A Fine-quality replay (40 ms grid) of the 21 s reading."""
    return make_scanpath_animation(
        _words(),
        _fixations(),
        canvas_width=800,
        canvas_height=600,
        base_font_size=12,
        font_family="Arial",
        playback_speed=speed,
        autoplay=autoplay,
        anim_grid_step_ms=40,
        anim_max_frames=900,
    )


def _run(fig, steps, tmp_path) -> dict:
    config = {
        "script": animation_player_post_script(fig),
        "meta": fig.layout.meta,
        "frames": len(fig.frames),
        "steps": steps,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    done = subprocess.run(
        [NODE, str(HARNESS), str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(done.stdout)


def _run_page(fig, steps, tmp_path, *, slot: bool = False) -> dict:
    """`_run` on the layout `plots.replay_page` gives the page: the figure's
    own controls hidden, and the player's toolbar in their place."""
    page, _script = replay_page(fig)
    layout = page["layout"]
    config = {
        "script": animation_player_post_script(fig),
        "meta": layout["meta"],
        "updatemenus": layout["updatemenus"],
        "sliders": layout["sliders"],
        "frames": len(fig.frames),
        "steps": steps,
        "slot": slot,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    done = subprocess.run(
        [NODE, str(HARNESS), str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(done.stdout)


def _times(fig) -> list[float]:
    return fig.layout.meta["scanpath_frame_times_ms"]


def _first_shown(log) -> dict[int, float]:
    first: dict[int, float] = {}
    for name, at in log["shown"]:
        first.setdefault(int(name), at)
    return first


class TestRealTime:
    def test_a_fine_replay_at_x1_takes_the_reading_time(self, tmp_path):
        fig = _replay()
        times = _times(fig)
        span = times[-1]
        log = _run(fig, [["run_until", span * 1.5]], tmp_path)
        first = _first_shown(log)
        # Every frame is shown, in order, within one display tick of the moment
        # its reading time is reached. Plotly's own queue shows frame k at
        # k × 50 ms here — 25 % late, and later with every frame.
        assert sorted(first) == list(range(len(times)))
        for k, at in first.items():
            assert times[k] - 1e-6 <= at < times[k] + TICK_MS + 1e-6, (k, at)
        # So the whole replay lasts the reading span, not 1.25 × it.
        assert first[len(times) - 1] == pytest.approx(span, abs=TICK_MS)

    @pytest.mark.parametrize("speed", [1.5, 2.0, 8.0])
    def test_every_speed_ends_on_time(self, tmp_path, speed):
        fig = _replay(speed=speed)
        times = _times(fig)
        log = _run(fig, [["run_until", times[-1] / speed + 1000]], tmp_path)
        first = _first_shown(log)
        for k, at in first.items():
            assert times[k] / speed - 1e-6 <= at < times[k] / speed + TICK_MS + 1e-6
        assert first[len(times) - 1] == pytest.approx(times[-1] / speed, abs=TICK_MS)
        # Frames only ever move forward.
        order = [int(name) for name, _ in log["shown"]]
        assert order == sorted(order)

    def test_a_replay_faster_than_the_screen_skips_frames(self, tmp_path):
        # ×8 on a 40 ms grid is a frame every 5 ms — three per display tick. The
        # screen can't show them all, so the clock skips ahead rather than fall
        # behind (Plotly's queue shows all of them and takes 5× too long).
        fig = _replay(speed=8.0)
        log = _run(fig, [["run_until", _times(fig)[-1] / 8 + 1000]], tmp_path)
        assert len(log["shown"]) < len(fig.frames)


class TestPlayTakesOverPlotlysQueue:
    def test_play_no_longer_runs_plotlys_own_command(self, tmp_path):
        fig = _replay(autoplay=False)
        log = _run(fig, [["click", "play"], ["run_until", 2000]], tmp_path)
        assert log["relayouts"] == [{"updatemenus[0].buttons[0].execute": False}]
        assert "play" not in log["native"]
        assert log["shown"], "Play started the replay"

    def test_without_autoplay_nothing_moves_until_play(self, tmp_path):
        fig = _replay(autoplay=False)
        times = _times(fig)
        log = _run(
            fig,
            [["run_until", 3010], ["click", "play"], ["run_until", 30000]],
            tmp_path,
        )
        first = _first_shown(log)
        assert min(first.values()) >= 3010
        assert first[len(times) - 1] == pytest.approx(3010 + times[-1], abs=TICK_MS)


class TestTransport:
    def test_pause_holds_and_play_resumes_where_it_stopped(self, tmp_path):
        fig = _replay()
        times = _times(fig)
        log = _run(
            fig,
            [
                ["run_until", 5010],
                ["click", "pause"],
                ["run_until", 9010],
                ["click", "play"],
                ["run_until", 30000],
            ],
            tmp_path,
        )
        paused_on = max(int(n) for n, at in log["shown"] if at <= 5010)
        assert not [at for _, at in log["shown"] if 5010 < at < 9010]
        # The rest of the reading takes the rest of its time, from where it was.
        resumed = [(int(n), at) for n, at in log["shown"] if at >= 9010]
        assert resumed[0][0] == paused_on
        end = 9010 + times[-1] - times[paused_on]
        assert resumed[-1] == (len(times) - 1, pytest.approx(end, abs=TICK_MS))

    def test_play_while_playing_keeps_the_clock(self, tmp_path):
        # A second ▶ mid-replay must not re-anchor on the frame on screen, which
        # would push the rest of the replay back by up to one frame.
        fig = _replay()
        span = _times(fig)[-1]
        log = _run(
            fig,
            [["run_until", 5030], ["click", "play"], ["run_until", span + 1000]],
            tmp_path,
        )
        assert log["shown"][-1] == [
            str(len(fig.frames) - 1),
            pytest.approx(span, abs=TICK_MS),
        ]
        order = [int(name) for name, _ in log["shown"]]
        assert order == sorted(set(order))  # nothing re-shown, nothing repeated

    def test_play_at_the_end_starts_over(self, tmp_path):
        fig = _replay()
        span = _times(fig)[-1]
        pressed = span + 1010
        log = _run(
            fig,
            [["run_until", pressed], ["click", "play"], ["run_until", 3 * span]],
            tmp_path,
        )
        again = [(int(n), at) for n, at in log["shown"] if at >= pressed]
        assert again[0] == (0, pressed)
        assert again[-1][1] == pytest.approx(pressed + span, abs=TICK_MS)

    def test_restart_goes_to_the_start_and_stops(self, tmp_path):
        fig = _replay()
        log = _run(
            fig,
            [["run_until", 5010], ["click", "restart"], ["run_until", 12010]],
            tmp_path,
        )
        after = [(int(n), at) for n, at in log["shown"] if at >= 5010]
        assert after == [(0, 5010)]

    def test_scrubbing_stops_the_clock(self, tmp_path):
        fig = _replay()
        times = _times(fig)
        log = _run(
            fig,
            [
                ["run_until", 3010],
                ["slider", 300],
                ["run_until", 8010],
                ["click", "play"],
                ["run_until", 30000],
            ],
            tmp_path,
        )
        between = [(int(n), at) for n, at in log["shown"] if 3010 <= at < 8010]
        assert between == [(300, 3010)]
        end = 8010 + times[-1] - times[300]
        assert log["shown"][-1] == [
            str(len(times) - 1),
            pytest.approx(end, abs=TICK_MS),
        ]

    def test_a_background_tab_pauses_the_replay(self, tmp_path):
        # A hidden tab gets no display ticks; the replay picks up where it was
        # rather than jumping ahead by however long the tab was away.
        fig = _replay()
        times = _times(fig)
        log = _run(
            fig,
            [
                ["run_until", 4010],
                ["hide"],
                ["run_until", 10010],
                ["show"],
                ["run_until", 40000],
            ],
            tmp_path,
        )
        hidden_on = max(int(n) for n, at in log["shown"] if at <= 4010)
        assert not [at for _, at in log["shown"] if 4010 < at < 10010]
        end = 10010 + times[-1] - times[hidden_on]
        assert log["shown"][-1] == [
            str(len(times) - 1),
            pytest.approx(end, abs=TICK_MS),
        ]

    def test_a_plot_that_leaves_the_page_stops_and_lets_go(self, tmp_path):
        # The docs site swaps pages without reloading, so a replay whose plot is
        # gone must stop animating it and drop its document listener, or every
        # visit would keep one plot alive.
        fig = _replay()
        log = _run(
            fig,
            [
                ["run_until", 3010],
                ["detach"],
                ["run_until", 8010],
                ["hide"],
                ["show"],
                ["run_until", 30000],
            ],
            tmp_path,
        )
        assert not [at for _, at in log["shown"] if at > 3010 + TICK_MS]
        assert log["listeners"] == 0


class TestToolbar:
    """A page from `plots.replay_page` hides the figure's own controls; the
    player draws one row above the figure and drives the replay from it."""

    def test_the_toolbar_carries_the_figures_own_labels(self, tmp_path):
        fig = _replay(autoplay=False)
        log = _run_page(fig, [["run_until", 100]], tmp_path)
        bar = log["toolbar"]
        assert bar is not None
        # No slot on the page: it goes straight above the plot, as wide.
        assert not bar["in_slot"] and bar["inserted"] == 1
        assert bar["width"] == "960px"
        assert bar["height"] == f"{REPLAY_TOOLBAR_PX}px"
        assert bar["attributes"]["aria-label"] == "Replay controls"
        assert bar["buttons"] == [b.label for b in fig.layout.updatemenus[0].buttons]
        assert bar["font"] == fig.layout.updatemenus[0].font.family
        slider = fig.layout.sliders[0]
        assert bar["range"]["max"] == str(len(fig.frames) - 1)
        assert bar["readout"] == slider.currentvalue.prefix + slider.steps[0].label
        assert bar["range"]["attributes"]["aria-valuetext"] == bar["readout"]
        assert not log["shown"], "nothing plays without autoplay"

    def test_an_embedders_slot_takes_the_toolbar(self, tmp_path):
        log = _run_page(_replay(), [["run_until", 100]], tmp_path, slot=True)
        assert log["toolbar"]["in_slot"] and log["toolbar"]["inserted"] == 0

    def test_play_keeps_real_time_and_the_readout_follows(self, tmp_path):
        fig = _replay(autoplay=False)
        times = _times(fig)
        log = _run_page(
            fig, [["toolbar", "play"], ["run_until", times[-1] + 1000]], tmp_path
        )
        first = _first_shown(log)
        assert sorted(first) == list(range(len(times)))
        assert first[len(times) - 1] == pytest.approx(times[-1], abs=TICK_MS)
        slider = fig.layout.sliders[0]
        assert log["toolbar"]["range"]["value"] == str(len(times) - 1)
        assert log["toolbar"]["readout"] == (
            slider.currentvalue.prefix + slider.steps[-1].label
        )

    def test_pause_holds_and_play_resumes(self, tmp_path):
        fig = _replay()
        log = _run_page(
            fig,
            [
                ["run_until", 5010],
                ["toolbar", "pause"],
                ["run_until", 9010],
                ["toolbar", "play"],
                ["run_until", 10010],
            ],
            tmp_path,
        )
        paused_on = max(int(n) for n, at in log["shown"] if at <= 5010)
        assert not [at for _, at in log["shown"] if 5010 < at < 9010]
        resumed = [int(n) for n, at in log["shown"] if at >= 9010]
        assert resumed[0] == paused_on and resumed[-1] > paused_on

    def test_restart_goes_to_the_start_and_stops(self, tmp_path):
        log = _run_page(
            _replay(),
            [["run_until", 5010], ["toolbar", "restart"], ["run_until", 12010]],
            tmp_path,
        )
        assert [(int(n), at) for n, at in log["shown"] if at >= 5010] == [(0, 5010)]
        assert log["toolbar"]["range"]["value"] == "0"

    def test_seeking_shows_that_frame_and_stops_the_clock(self, tmp_path):
        fig = _replay()
        log = _run_page(
            fig,
            [["run_until", 3010], ["seek", 300], ["run_until", 8010]],
            tmp_path,
        )
        assert [(int(n), at) for n, at in log["shown"] if at >= 3010] == [(300, 3010)]
        slider = fig.layout.sliders[0]
        assert log["toolbar"]["range"]["value"] == "300"
        assert log["toolbar"]["readout"] == (
            slider.currentvalue.prefix + slider.steps[300].label
        )

    def test_a_figure_drawing_its_own_controls_gets_no_toolbar(self, tmp_path):
        log = _run(_replay(), [["run_until", 100]], tmp_path)
        assert log["toolbar"] is None
