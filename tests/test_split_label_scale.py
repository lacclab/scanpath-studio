"""Split comparisons size each panel's word labels from its final subplot space.

Round-8 review, finding 5: the side-by-side / stacked builder sized each
panel's labels from a preliminary fit, then gave the figure the widest /
tallest fit of the pair. With two different screens the smaller one renders
its boxes at a larger scale than its text was sized for — A at 800×600 and B
at 1600×1200 both got 8 px labels, though A's boxes were drawn at twice B's
scale. The labels now follow the scale each panel's axes actually get.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import plots

BASE_FONT = 16


def _frames(pid: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    words = pd.DataFrame(
        {
            "participant_id": [pid, pid],
            "trial_id": ["t", "t"],
            "text_id": ["text", "text"],
            "word_id": [1, 2],
            "text": ["One", "Two"],
            "x": [100.0, 200.0],
            "y": [100.0, 100.0],
            "width": [50.0, 50.0],
            "height": [20.0, 20.0],
            "line_idx": [0, 0],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": [pid, pid],
            "trial_id": ["t", "t"],
            "text_id": ["text", "text"],
            "x": [110.0, 210.0],
            "y": [110.0, 110.0],
            "duration_ms": [100.0, 200.0],
            "timestamp_ms": [1000.0, 1100.0],
            "fixation_id": [1, 2],
            "order_in_trial": [1, 2],
            "word_id": [1, 2],
        }
    )
    return words, fixations


def _figure(layout: str, canvas_b: tuple[int, int], **overrides):
    wa, fa = _frames("p")
    wb, fb = _frames("q")
    settings = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=BASE_FONT,
        show_words=True,
        show_word_labels=True,
        scale_text_to_boxes=False,
        duration_size_legend=False,
        fit_to_monitor=True,
        layout=layout,
        canvas_b=canvas_b,
    )
    settings.update(overrides)
    return plots.make_comparison_figure(
        pd.concat([wa, wb], ignore_index=True),
        pd.concat([fa, fb], ignore_index=True),
        ("p", "t"),
        ("q", "t"),
        settings=plots.FigureSettings(**settings),
    )


def _panel_scale(fig, idx: int) -> float:
    """Screen px per data unit of panel ``idx`` in the figure as laid out:
    its domain's share of the plot area, under the equal-aspect constraint."""
    layout = fig.layout
    margin = layout.margin
    plot_w = layout.width - (margin.l or 0) - (margin.r or 0)
    plot_h = layout.height - (margin.t or 0) - (margin.b or 0)
    suffix = "" if idx == 0 else str(idx + 1)
    xaxis, yaxis = layout[f"xaxis{suffix}"], layout[f"yaxis{suffix}"]
    x_span = xaxis.range[1] - xaxis.range[0]
    y_span = yaxis.range[0] - yaxis.range[1]
    return min(
        (xaxis.domain[1] - xaxis.domain[0]) * plot_w / x_span,
        (yaxis.domain[1] - yaxis.domain[0]) * plot_h / y_span,
    )


def _label_fonts(fig) -> list[float]:
    fonts = {t.xaxis: t.textfont.size for t in fig.data if t.name == "words"}
    return [fonts["x"], fonts["x2"]]


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
@pytest.mark.parametrize(
    "canvas_b",
    [(1600, 1200), (1200, 400), (800, 600)],
    ids=["larger-screen", "other-aspect", "same-screen"],
)
def test_manual_font_follows_each_panels_final_scale(layout, canvas_b):
    fig = _figure(layout, canvas_b)
    fonts = _label_fonts(fig)
    for idx in (0, 1):
        assert fonts[idx] == pytest.approx(BASE_FONT * _panel_scale(fig, idx))


def test_the_reviewed_pair_keeps_each_panels_text_to_its_boxes():
    """The review's case: the same 20-px AOI renders 19.2 px high in A and
    9.6 px in B, so A's 16-px font is drawn twice the size of B's."""
    fig = _figure("side_by_side", (1600, 1200))
    assert (fig.layout.width, fig.layout.height) == (1600, 600)
    fonts = _label_fonts(fig)
    assert fonts[0] == pytest.approx(2 * fonts[1])
    # 15.36 / 7.68 on the full height; the A/B panel titles' band (#374 F26)
    # takes a little of it.
    assert fonts[0] == pytest.approx(15.36, rel=0.03)


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
@pytest.mark.parametrize("canvas_b", [(1600, 1200), (1200, 400)])
def test_box_fitted_font_keeps_its_share_of_each_panels_boxes(layout, canvas_b):
    fig = _figure(layout, canvas_b, scale_text_to_boxes=True)
    words, _ = _frames("p")
    fig_line_spacing = plots.FigureSettings(
        canvas_width=800, canvas_height=600, base_font_size=BASE_FONT
    ).line_spacing
    fitted_data_px = plots._word_label_font_px(
        words,
        scale=1.0,
        line_spacing=fig_line_spacing,
        manual_font_px=BASE_FONT,
        scale_text_to_boxes=True,
    )
    fonts = _label_fonts(fig)
    for idx in (0, 1):
        # Text to its own (identical, 20-px) boxes in the same proportion.
        box_px = 20.0 * _panel_scale(fig, idx)
        assert fonts[idx] / box_px == pytest.approx(fitted_data_px / 20.0)


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
@pytest.mark.parametrize("orientation", ["Vertical", "Horizontal"])
@pytest.mark.parametrize("heatmap", [False, True], ids=["one-bar", "two-bars"])
def test_colorbars_and_grid_reserve_room_instead_of_shrinking_the_panels(
    layout, orientation, heatmap
):
    fig = _figure(
        layout,
        (1600, 1200),
        color_by="duration_ms",
        show_fixation_colorbar=True,
        show_heatmap_colorbar=True,
        fixation_colorbar_orientation=orientation,
        heatmap_colorbar_orientation=orientation,
        show_heatmap=heatmap,
        show_coordinate_grid=True,
        show_legend=True,
    )
    margin = fig.layout.margin
    if orientation == "Vertical":
        # A vertical bar hangs off the right edge: that band is reserved, so
        # Plotly's automargin has nothing left to take from the panels.
        assert margin.r >= plots._COLORBAR_RESERVE_PX
    else:
        assert margin.b >= plots._COLORBAR_BOTTOM_PX + plots._GRID_BOTTOM_RESERVE_PX
    assert margin.l == plots._GRID_LEFT_RESERVE_PX
    fonts = _label_fonts(fig)
    for idx in (0, 1):
        assert fonts[idx] == pytest.approx(BASE_FONT * _panel_scale(fig, idx))
    # B's screen is twice A's in each direction: A's text draws twice the size.
    assert fonts[0] / fonts[1] == pytest.approx(2.0)
