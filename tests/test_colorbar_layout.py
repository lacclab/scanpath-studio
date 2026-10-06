"""Several colour bars each get a place of their own (round-7 review, finding 16).

A word heatmap's scale and the fixations' numeric colour scale used to share
`_colorbar_dict`'s one position, so their gradients, titles and ticks were
drawn over each other.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import plots
from scanpath_studio.plots import _COLORBAR_RESERVE_PX, _colorbar_owners


def _frames(participant: str = "p"):
    words = pd.DataFrame(
        {
            "participant_id": [participant] * 2,
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
            "participant_id": [participant] * 4,
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


def _options(orientation: str, heatmap: bool = True) -> dict:
    return dict(
        show_heatmap=heatmap,
        heatmap_style="Word boxes",
        color_by="timestamp_ms",
        fixation_colorscale="Plasma",
        show_fixation_colorbar=True,
        show_heatmap_colorbar=True,
        fixation_colorbar_orientation=orientation,
        heatmap_colorbar_orientation=orientation,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
    )


def _plot_size(fig) -> tuple[float, float]:
    m = fig.layout.margin
    return (
        fig.layout.width - (m.l or 0) - (m.r or 0),
        fig.layout.height - (m.t or 0) - (m.b or 0),
    )


def _bars(fig) -> list:
    return [owner.colorbar for owner in _colorbar_owners(fig)]


class TestTheStaticFigure:
    def test_vertical_bars_stand_side_by_side(self):
        words, fixations = _frames()
        one = plots.make_scanpath_figure(
            words, fixations, **_options("Vertical", heatmap=False)
        )
        two = plots.make_scanpath_figure(words, fixations, **_options("Vertical"))
        bars = _bars(two)
        assert len(bars) == 2
        assert bars[0].x == pytest.approx(1.02)
        assert bars[1].x > bars[0].x + 0.1
        assert len({bar.y for bar in bars}) == 1
        # The figure grows to hold the second bar; the plot keeps its size.
        assert two.layout.margin.r > one.layout.margin.r
        assert _plot_size(two) == _plot_size(one)

    def test_horizontal_bars_stack_below(self):
        words, fixations = _frames()
        one = plots.make_scanpath_figure(
            words, fixations, **_options("Horizontal", heatmap=False)
        )
        two = plots.make_scanpath_figure(words, fixations, **_options("Horizontal"))
        bars = _bars(two)
        assert len(bars) == 2
        assert bars[0].y == pytest.approx(-0.04)
        assert bars[1].y < bars[0].y - 0.1
        assert two.layout.margin.b > one.layout.margin.b
        assert _plot_size(two) == _plot_size(one)

    @pytest.mark.parametrize("orientation", ["Vertical", "Horizontal"])
    def test_one_bar_keeps_its_geometry(self, orientation):
        words, fixations = _frames()
        fig = plots.make_scanpath_figure(
            words, fixations, **_options(orientation, heatmap=False)
        )
        (bar,) = _bars(fig)
        expected = plots._colorbar_dict("Timestamp (ms)", orientation=orientation)
        assert (bar.x, bar.y, bar.len) == (
            expected["x"],
            expected["y"],
            expected["len"],
        )
        if orientation == "Vertical":
            assert fig.layout.margin.r == _COLORBAR_RESERVE_PX


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
@pytest.mark.parametrize("orientation", ["Vertical", "Horizontal"])
def test_a_comparison_separates_its_bars(layout, orientation):
    words_a, fix_a = _frames("p")
    words_b, fix_b = _frames("q")
    fig = plots.make_comparison_figure(
        pd.concat([words_a, words_b], ignore_index=True),
        pd.concat([fix_a, fix_b], ignore_index=True),
        ("p", "t"),
        ("q", "t"),
        layout=layout,
        **{**_options(orientation), "color_by": "duration_ms"},
    )
    bars = _bars(fig)
    assert len(bars) == 2
    positions = {(bar.x, bar.y) for bar in bars}
    assert len(positions) == 2
    if orientation == "Vertical":
        assert fig.layout.margin.r >= _COLORBAR_RESERVE_PX


def test_the_word_heatmap_bar_names_dwell_not_fixation_duration():
    words, fixations = _frames()
    options = {
        **_options("Vertical"),
        "color_by": "duration_ms",
        "heatmap_metric": "duration_ms",
    }
    fig = plots.make_scanpath_figure(words, fixations, **options)
    titles = sorted(bar.title.text for bar in _bars(fig))
    assert titles == ["Duration (ms)", "Dwell time per word (ms)"]
    log = plots.make_scanpath_figure(
        words, fixations, **{**options, "heatmap_norm": "Log"}
    )
    assert "Dwell time per word (ms) (log)" in [b.title.text for b in _bars(log)]


class TestEachBarIsItsOwn:
    """The fixations' bar and the heatmap's have their own switch and style."""

    def test_one_switch_leaves_the_other_bar(self):
        words, fixations = _frames()
        fig = plots.make_scanpath_figure(
            words,
            fixations,
            **{**_options("Vertical"), "show_fixation_colorbar": False},
        )
        (bar,) = _bars(fig)
        assert "Timestamp" not in str(bar.title.text)

    def test_a_vertical_and_a_horizontal_bar_each_get_their_margin(self):
        words, fixations = _frames()
        alone = plots.make_scanpath_figure(
            words, fixations, **_options("Vertical", heatmap=False)
        )
        fig = plots.make_scanpath_figure(
            words,
            fixations,
            **{**_options("Vertical"), "heatmap_colorbar_orientation": "Horizontal"},
        )
        bars = _bars(fig)
        assert sorted(bar.orientation == "h" for bar in bars) == [False, True]
        # Each bar alone in its orientation keeps its own spot.
        vertical = next(bar for bar in bars if bar.orientation != "h")
        horizontal = next(bar for bar in bars if bar.orientation == "h")
        assert vertical.x == pytest.approx(1.02)
        assert horizontal.y == pytest.approx(-0.04)
        assert fig.layout.margin.r == _COLORBAR_RESERVE_PX
        assert fig.layout.margin.b > alone.layout.margin.b
        assert _plot_size(fig) == _plot_size(alone)

    def test_each_bar_takes_its_own_tick_style(self):
        words, fixations = _frames()
        fig = plots.make_scanpath_figure(
            words,
            fixations,
            **{
                **_options("Vertical"),
                "fixation_colorbar_tickangle": 45,
                "heatmap_colorbar_tickfont_size": 9,
            },
        )
        angles = sorted(int(bar.tickangle or 0) for bar in _bars(fig))
        sizes = sorted(int(bar.tickfont.size) for bar in _bars(fig))
        assert angles == [0, 45]
        assert sizes == [9, 12]
