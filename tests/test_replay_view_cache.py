"""PERF-16: with 🎬 Animate on, a rerun shows the replay without reloading it.

PERF-13 cached the replay as a `go.Figure`, so every rerun still paid to unpickle
it — plotly re-validates every frame, 9 s at 2,000 frames — and then to serialize
it into the page with `to_html`, 12 s more; with the Export tab on GIF/MP4 the
export signature added `fig.to_json()`, 12 s again. `tabs._cached_replay_view`
now caches what a rerun shows: the embed's HTML and the finished figure as
compressed bytes, keyed on everything that goes into the figure. The figure is
unpickled only when an export needs it, and the export is signed from those
inputs rather than from the figure's JSON.
"""

from __future__ import annotations

import json

import re

import pandas as pd
import pytest

from scanpath_studio import plots, tabs


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


_CANVAS = dict(
    canvas_width=800, canvas_height=600, base_font_size=12, font_family="Arial"
)


@pytest.fixture
def page(monkeypatch):
    """Cold replay caches, plus a record of what reached the page and the cache."""
    tabs._cached_replay_view.clear()
    tabs._cached_scanpath_animation.clear()
    record = {"embeds": [], "replay_loads": 0}

    def embed(html, *, height):
        record["embeds"].append(html)

    real = tabs._cached_scanpath_animation

    def replay_cache(*args, **kwargs):
        record["replay_loads"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(tabs, "_embed_html_iframe", embed)
    monkeypatch.setattr(tabs, "_cached_scanpath_animation", replay_cache)
    return record


def _render(speed: float = 1.0, *, autoplay: bool = True, **viz):
    frames = (_words(), _fixations(), None, None, "p1", "t1", None, None)
    viz_settings = {"anim_autoplay": autoplay, "critical_span_style": "None", **viz}
    plan = tabs._plan_replay(
        *frames,
        settings=plots.FigureSettings.from_mapping({}, **_CANVAS),
        viz_settings=viz_settings,
        playback_speed=speed,
    )
    view, _slug, _stem = tabs._build_and_render_animation(
        *frames, viz_settings=viz_settings, plan=plan
    )
    return view


class TestARerunShowsTheCachedView:
    def test_a_rerun_neither_rebuilds_nor_reloads_the_replay(self, page):
        _render()
        _render()
        # The second rerun never reached the replay cache, whose every hit
        # unpickles the whole figure.
        assert page["replay_loads"] == 1
        assert page["embeds"][0] == page["embeds"][1]

    def test_a_hit_embeds_exactly_what_the_old_path_did(self, page, monkeypatch):
        finished = []
        real = tabs._true_scale_plot_html

        def spy(fig, **kwargs):
            finished.append(fig)
            return real(fig, **kwargs)

        monkeypatch.setattr(tabs, "_true_scale_plot_html", spy)
        _render()
        _render()
        # What PERF-13's path embedded for that same finished figure.
        tabs._render_true_scale_chart(
            finished[0], key="single_anim", download_name="animation_p1__t1_frame"
        )
        assert page["embeds"][1] == page["embeds"][2]

    @pytest.mark.parametrize(
        ("change", "shows"),
        [
            (dict(speed=2.0), '"scanpath_playback_speed":2.0'),
            (dict(autoplay=False), '"scanpath_autoplay":false'),
            (dict(title_pattern="Reading {participant_id}"), "Reading p1"),
            (dict(illustration_reasons=["playback speed ×2"]), "playback speed ×2"),
        ],
    )
    def test_a_change_to_the_figure_is_a_new_view(self, page, change, shows):
        _render()
        _render(**change)
        assert page["embeds"][1] != page["embeds"][0]
        assert _shown(shows, page["embeds"][1])
        assert not _shown(shows, page["embeds"][0])


def _shown(text: str, embed: str) -> bool:
    """``text`` in the page, as written either way: plotly's JSON engine keeps
    "×" as is with ``orjson`` installed and escapes it (``\u00d7``) without —
    CI installs no ``orjson``. The browser reads both the same."""
    return text in embed or json.dumps(text)[1:-1] in embed


class TestTheExportReadsTheView:
    def test_the_figure_is_the_finished_replay(self, page):
        view = _render(speed=2.0)
        fig = view.figure()
        assert view.n_frames == len(fig.frames)
        assert view.clip_frame_ms == pytest.approx(plots.animation_clip_frame_ms(fig))
        assert (view.width, view.height) == (fig.layout.width, fig.layout.height)
        assert fig.layout.meta["scanpath_playback_speed"] == 2.0

    def test_the_html_download_needs_no_figure(self, page, monkeypatch):
        # The page is written straight from the view's dict: building a figure
        # would re-validate every frame first (9 s at 2,000 frames).
        view = _render(speed=2.0)

        def no_figure(self):
            raise AssertionError("the HTML download built a figure")

        monkeypatch.setattr(tabs._ReplayView, "figure", no_figure)
        page_html = tabs._replay_page_html(view)
        assert page_html.startswith("<!doctype html>")  # a whole page
        assert "cdn.plot.ly" in page_html
        assert "plotly_buttonclicked" in page_html  # the replay player
        assert '"scanpath_playback_speed":2.0' in page_html

    def test_a_self_contained_replay_page_keeps_its_player(self, page):
        """Embedded, the library is written ahead of the player's script, so
        the page replays offline exactly as the CDN one does."""
        page_html = tabs._replay_page_html(_render(), self_contained=True)
        assert not re.search(r'<script[^>]*\ssrc="https?://', page_html)
        library = page_html.index("plotly.js v")
        player = page_html.index("plotly_buttonclicked")
        assert library < player

    def test_the_signature_follows_the_clip_not_autoplay(self, page):
        base = _render().signature
        # A GIF/MP4 carries no autoplay (the raster base strips the meta), so
        # flipping it keeps a rendered clip; anything drawn into it does not.
        assert _render(autoplay=False).signature == base
        assert _render(speed=2.0).signature != base
        assert _render(title_pattern="Reading {participant_id}").signature != base
        assert _render().signature == base
