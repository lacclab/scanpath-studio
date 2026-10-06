"""PERF-15: a speed or autoplay change re-times the replay instead of rebuilding it.

Since BUG-93 the frames of a replay depend on neither its playback speed nor its
autoplay switch: only ▶ Play's own frame duration and the clock on
``layout.meta`` do. `plots.build_scanpath_replay` returns the figure with the grid
step that duration is made from, and `plots.set_replay_clock` stamps a speed and
autoplay onto it — so the app caches one build per frame content and re-times
the copy each cache hit hands back.
"""

from __future__ import annotations

import pickle

import pandas as pd
import pytest

from scanpath_studio import plots, tabs
from scanpath_studio.plots import (
    build_scanpath_replay,
    make_scanpath_animation,
    set_replay_clock,
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


def _fixations(n: int = 30) -> pd.DataFrame:
    # Onsets 137.3 ms apart: a reading span no grid step divides evenly, so a
    # capped grid coarsens to a fractional step.
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * n,
            "trial_id": ["t1"] * n,
            "x": [110.0 + 7 * i for i in range(n)],
            "y": [60.0] * n,
            "duration_ms": [101.7] * n,
            "timestamp_ms": [i * 137.3 for i in range(n)],
            "order_in_trial": list(range(1, n + 1)),
        }
    )


_CLOCK = ("scanpath_autoplay", "scanpath_frame_times_ms", "scanpath_playback_speed")
_CANVAS = dict(
    canvas_width=800, canvas_height=600, base_font_size=12, font_family="Arial"
)
# A fine grid the cap leaves alone, and one it coarsens to a fractional step.
_GRIDS = [(40, 900), (10, 25)]


class TestRetimingIsByteIdentical:
    @pytest.mark.parametrize(("grid_step_ms", "max_frames"), _GRIDS)
    @pytest.mark.parametrize("autoplay", [True, False])
    @pytest.mark.parametrize("speed", [0.25, 1.0, 1.5, 3.0, 8.0])
    def test_retiming_matches_building_at_that_speed(
        self, grid_step_ms, max_frames, autoplay, speed
    ):
        grid = dict(anim_grid_step_ms=grid_step_ms, anim_max_frames=max_frames)
        built = make_scanpath_animation(
            _words(),
            _fixations(),
            playback_speed=speed,
            autoplay=autoplay,
            **grid,
            **_CANVAS,
        )
        fig, frame_step_ms = build_scanpath_replay(
            _words(), _fixations(), playback_speed=1.0, autoplay=True, **grid, **_CANVAS
        )
        set_replay_clock(fig, frame_step_ms, playback_speed=speed, autoplay=autoplay)
        # Equal bytes, not just equal values: what the app shows, exports and
        # signs is then exactly the figure the API builds at that speed.
        assert fig.to_json() == built.to_json()

    @pytest.mark.parametrize("speed", [0.5, 2.0])
    def test_retiming_a_cache_hit_matches_the_old_cache_hit(self, speed):
        # `st.cache_data` hands back an unpickled copy, whose JSON already differs
        # from a freshly built figure's (plotly rebuilds it from `to_dict()`), so
        # pin the comparison the app makes: a re-timed hit against the hit the
        # old code got by caching the build at that speed. The export signature
        # hashes this JSON.
        grid = dict(anim_grid_step_ms=10, anim_max_frames=25)
        old_hit = pickle.loads(
            pickle.dumps(
                make_scanpath_animation(
                    _words(), _fixations(), playback_speed=speed, **grid, **_CANVAS
                )
            )
        )
        cached = pickle.dumps(
            build_scanpath_replay(_words(), _fixations(), **grid, **_CANVAS)
        )
        fig, frame_step_ms = pickle.loads(cached)
        set_replay_clock(fig, frame_step_ms, playback_speed=speed, autoplay=True)
        assert fig.to_json() == old_hit.to_json()

    def test_the_illustration_reasons_do_not_reach_the_frames(self):
        # The app builds on `illustration_reasons=None` whatever the rail says
        # (a non-1× speed is one): that is only sound while the builder ignores
        # them. The label is stamped on after the cache, like the clock.
        plain = make_scanpath_animation(_words(), _fixations(), **_CANVAS)
        reasoned = make_scanpath_animation(
            _words(),
            _fixations(),
            illustration_reasons=["playback speed ×2", "drift correction"],
            **_CANVAS,
        )
        assert reasoned.to_json() == plain.to_json()

    def test_the_illustration_text_does_not_reach_the_frames(self):
        # Same for the label's text: the app pins it to "" for the frames and
        # stamps it with the label afterwards, so editing it rebuilds nothing.
        plain = make_scanpath_animation(_words(), _fixations(), **_CANVAS)
        texted = make_scanpath_animation(
            _words(), _fixations(), illustration_text="Schematic", **_CANVAS
        )
        assert texted.to_json() == plain.to_json()

    def test_the_app_keys_the_frames_without_the_text(self):
        import inspect

        from scanpath_studio import tabs

        source = inspect.getsource(tabs._plan_replay)
        assert 'illustration_text=""' in source

    def test_a_replay_with_no_frames_stays_without_controls(self):
        empty = _fixations().iloc[0:0]
        built = make_scanpath_animation(
            _words(), empty, playback_speed=2.0, autoplay=True, **_CANVAS
        )
        fig, frame_step_ms = build_scanpath_replay(
            _words(), empty, playback_speed=1.0, autoplay=False, **_CANVAS
        )
        set_replay_clock(fig, frame_step_ms, playback_speed=2.0, autoplay=True)
        assert fig.to_json() == built.to_json()
        assert not fig.layout.updatemenus
        assert fig.layout.meta["scanpath_autoplay"] is False

    def test_retiming_keeps_the_rest_of_the_meta(self):
        # The app stamps the Illustration label's keys onto `layout.meta` too; a
        # re-time must change the clock and leave those alone, whatever the order.
        fig, frame_step_ms = build_scanpath_replay(_words(), _fixations(), **_CANVAS)
        plots.add_illustration_label(fig, ["playback speed ×2"])
        labelled = dict(fig.layout.meta)
        set_replay_clock(fig, frame_step_ms, playback_speed=2.0, autoplay=False)
        meta = fig.layout.meta
        assert meta["scanpath_playback_speed"] == 2.0
        assert meta["scanpath_autoplay"] is False
        for key in set(labelled) - set(_CLOCK):
            assert meta[key] == labelled[key]

    def test_make_scanpath_animation_is_the_replay_build(self):
        fig, _step = build_scanpath_replay(
            _words(), _fixations(), playback_speed=2.5, **_CANVAS
        )
        built = make_scanpath_animation(
            _words(), _fixations(), playback_speed=2.5, **_CANVAS
        )
        assert fig.to_json() == built.to_json()


class TestTheAppReusesItsFrames:
    def _render(self, settings, viz, speed):
        frames = (_words(), _fixations(), None, None, "p1", "t1", None, None)
        plan = tabs._plan_replay(
            *frames, settings=settings, viz_settings=viz, playback_speed=speed
        )
        view, *_ = tabs._build_and_render_animation(
            *frames, viz_settings=viz, plan=plan
        )
        return view.figure()

    def test_a_speed_or_autoplay_change_reuses_the_cached_frames(self, monkeypatch):
        builds: list[plots.FigureSettings] = []
        real = plots.build_scanpath_replay

        def spy(words, fixations, **kwargs):
            builds.append(kwargs["settings"])
            return real(words, fixations, **kwargs)

        monkeypatch.setattr(tabs, "build_scanpath_replay", spy)
        monkeypatch.setattr(tabs, "_embed_html_iframe", lambda *a, **k: None)
        tabs._cached_scanpath_animation.clear()
        tabs._cached_replay_view.clear()
        base = plots.FigureSettings.from_mapping({}, **_CANVAS)

        shown = {}
        for speed, autoplay in [(1.0, True), (2.0, True), (4.0, False), (1.0, True)]:
            # As in the app: a non-1× speed is a reason for the Illustration
            # label, so the settings the replay is built from change with it.
            reasons = [] if speed == 1.0 else [f"playback speed ×{speed:g}"]
            settings = base.with_overrides(illustration_reasons=reasons)
            viz = {
                "anim_autoplay": autoplay,
                "illustration_reasons": reasons,
                "critical_span_style": "None",
            }
            shown[speed, autoplay] = self._render(settings, viz, speed)

        assert len(builds) == 1, f"the replay was rebuilt {len(builds)} times"
        for (speed, autoplay), fig in shown.items():
            # Each view carries its own clock — what a direct build at that
            # speed and autoplay would carry.
            direct = make_scanpath_animation(
                _words(),
                _fixations(),
                settings=builds[0].with_overrides(
                    playback_speed=speed, autoplay=autoplay
                ),
            )
            # (The app adds the Illustration label's keys to the meta on top.)
            assert {key: fig.layout.meta[key] for key in _CLOCK} == direct.layout.meta
            assert fig.layout.updatemenus == direct.layout.updatemenus
