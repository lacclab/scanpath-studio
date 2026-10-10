"""BUG-9: direction arrowheads must sit on the drawn saccade, arc or straight.

In VIZ-9's ``saccade_render_mode="Arc"`` each saccade is drawn as an upward
quadratic Bézier arch (``plots._arch_points``), but the arrowheads used to come
from the straight chord, so they floated below the curve. ``_saccade_arrow_markers``
now takes the same ``arch_frac`` the segment builders take.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio.data import (
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)
from scanpath_studio.plots import (
    _ARCH_FRAC,
    _arch_points,
    _saccade_arrow_markers,
    make_scanpath_figure,
)


def _two_fixations(x0: float, y0: float, x1: float, y1: float) -> pd.DataFrame:
    """Minimal two-fixation trial: one saccade from (x0,y0) to (x1,y1)."""
    return pd.DataFrame(
        {
            "x": [x0, x1],
            "y": [y0, y1],
            "timestamp_ms": [0.0, 100.0],
            "duration_ms": [200.0, 200.0],
        }
    )


# Hand-traced for the (100,200) -> (300,260) saccade below.
#   chord midpoint          = (200, 230)
#   angle (clockwise from up, y-axis reversed)
#                           = degrees(atan2(dx, -dy)) = degrees(atan2(200, -60))
#                           = 106.6992...
_CHORD_MID = (200.0, 230.0)
_CHORD_ANGLE = 106.69924423399361
# arch: rise = 0.28 * |dx| = 56 -> control point (200, 200 - 56) = (200, 144)
#   B(0.5).y = 0.25*200 + 0.5*144 + 0.25*260 = 187
_ARCH_MID = (200.0, 187.0)


class TestStraightUnchanged:
    def test_chord_midpoint_and_angle_pinned(self):
        fix = _two_fixations(100.0, 200.0, 300.0, 260.0)
        mx, my, ang = _saccade_arrow_markers(fix, "x", "y")
        assert (mx[0], my[0]) == pytest.approx(_CHORD_MID)
        assert ang[0] == pytest.approx(_CHORD_ANGLE)

    def test_horizontal_saccade_points_right(self):
        fix = _two_fixations(100.0, 200.0, 300.0, 200.0)
        mx, my, ang = _saccade_arrow_markers(fix, "x", "y")
        # 90 deg clockwise from "up" == pointing right.
        assert (mx[0], my[0]) == pytest.approx((200.0, 200.0))
        assert ang[0] == pytest.approx(90.0)

    def test_arch_frac_none_is_the_default(self):
        fix = _two_fixations(100.0, 200.0, 300.0, 260.0)
        assert _saccade_arrow_markers(fix, "x", "y") == _saccade_arrow_markers(
            fix, "x", "y", None
        )


class TestArcAware:
    def test_marker_sits_on_the_arc_not_the_chord(self):
        fix = _two_fixations(100.0, 200.0, 300.0, 260.0)
        mx, my, _ = _saccade_arrow_markers(fix, "x", "y", _ARCH_FRAC)
        assert (mx[0], my[0]) == pytest.approx(_ARCH_MID)
        # Same x as the chord midpoint (the arch's x is linear in t), but lifted
        # onto the curve — smaller y is higher on the reversed screen axis.
        assert my[0] != pytest.approx(_CHORD_MID[1])
        assert my[0] < _CHORD_MID[1]

    def test_marker_lies_on_the_drawn_polyline(self):
        """The rendered arc is `_arch_points`; the marker must be on it."""
        x0, y0, x1, y1 = 100.0, 200.0, 340.0, 120.0
        fix = _two_fixations(x0, y0, x1, y1)
        mx, my, ang = _saccade_arrow_markers(fix, "x", "y", _ARCH_FRAC)
        axs, ays = _arch_points(x0, y0, x1, y1, _ARCH_FRAC)
        axs, ays = np.asarray(axs), np.asarray(ays)
        # Locate the drawn segment spanning the marker's x and interpolate it.
        i = int(np.searchsorted(axs, mx[0]) - 1)
        assert 0 <= i < len(axs) - 1
        t = (mx[0] - axs[i]) / (axs[i + 1] - axs[i])
        y_on_line = ays[i] + t * (ays[i + 1] - ays[i])
        span = float(np.hypot(x1 - x0, y1 - y0))
        assert abs(my[0] - y_on_line) < 0.001 * span
        # ...and points along that drawn segment.
        seg_ang = float(
            np.degrees(np.arctan2(axs[i + 1] - axs[i], -(ays[i + 1] - ays[i])))
        )
        assert ang[0] == pytest.approx(seg_ang, abs=0.5)

    def test_angle_matches_the_arc_tangent(self):
        """The tangent at the arch's parameter midpoint IS the chord direction.

        B'(0.5) == P1 - P0 for any quadratic Bézier, whatever the control point,
        so the arc-aware arrowhead keeps the straight-chord angle by construction
        (it is the *position* that was wrong) — for the horizontal saccade whose
        apex tangent is plainly horizontal, and for a vertically-offset one too.
        """
        for x0, y0, x1, y1 in [
            (100.0, 200.0, 300.0, 200.0),  # horizontal: apex tangent horizontal
            (100.0, 200.0, 300.0, 260.0),  # vertical offset
            (300.0, 260.0, 100.0, 200.0),  # right-to-left regression
        ]:
            fix = _two_fixations(x0, y0, x1, y1)
            _, _, straight = _saccade_arrow_markers(fix, "x", "y")
            _, _, arced = _saccade_arrow_markers(fix, "x", "y", _ARCH_FRAC)
            assert arced[0] == pytest.approx(straight[0])

    def test_vertical_offset_moves_the_marker(self):
        """A vertically-offset saccade's arrowhead is displaced by the arch."""
        fix = _two_fixations(100.0, 200.0, 300.0, 260.0)
        sx, sy, _ = _saccade_arrow_markers(fix, "x", "y")
        ax, ay, _ = _saccade_arrow_markers(fix, "x", "y", _ARCH_FRAC)
        assert ax[0] == pytest.approx(sx[0])
        assert ay[0] != pytest.approx(sy[0])


@pytest.fixture(scope="module")
def normalized_demo():
    """Load + normalize the bundled OneStop sample data once per test module."""
    words_raw, fixations_raw = load_sample_data()
    word_schema = infer_word_schema(words_raw)
    fix_schema = infer_fix_schema(fixations_raw)
    assert word_schema is not None and fix_schema is not None
    return normalize_words(words_raw, word_schema), normalize_fixations(
        fixations_raw, fix_schema
    )


class TestArcFigureSmoke:
    def test_arc_mode_builds_a_single_saccade_trace(self, normalized_demo):
        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        assert len(tf) >= 5
        fig = make_scanpath_figure(
            tw,
            tf,
            canvas_width=1024,
            canvas_height=600,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=True,
            show_saccade_arrows=True,
            saccade_render_mode="Arc",
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#111111",
            show_fixation_colorbar=False,
            show_heatmap_colorbar=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)
        saccades = [t for t in fig.data if t.name == "saccades"]
        arrows = [t for t in fig.data if t.name == "saccade direction"]
        assert len(saccades) == 1, "arcs must stay one trace (perf regression)"
        assert len(arrows) == 1
        # Every arrowhead is lifted onto its arc: same x, strictly higher on the
        # reversed screen axis than the straight-chord placement.
        straight = _saccade_arrow_markers(tf, "x", "y")
        arced = _saccade_arrow_markers(tf, "x", "y", _ARCH_FRAC)
        assert list(arrows[0].x) == pytest.approx(arced[0])
        assert list(arrows[0].y) == pytest.approx(arced[1])
        assert arced[0] == pytest.approx(straight[0])
        assert np.all(np.asarray(arced[1]) < np.asarray(straight[1]))


# ---------------------------------------------------------------------------
# Arc + Snap to line: the headroom follows the coordinates the arc is drawn from
# ---------------------------------------------------------------------------


def _snap_trial(
    word_x: list[float],
    word_y: list[float],
    word_w: list[float],
    fix_x: list[float],
    fix_y: list[float],
    word_ids: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Words + one fixation per word (or ``word_ids``), in reading order."""
    n_words = len(word_x)
    words = pd.DataFrame(
        {
            "participant_id": ["p"] * n_words,
            "trial_id": ["t"] * n_words,
            "text_id": ["text"] * n_words,
            "word_id": list(range(1, n_words + 1)),
            "text": [f"w{i}" for i in range(n_words)],
            "x": word_x,
            "y": word_y,
            "width": word_w,
            "height": [20.0] * n_words,
            "line_idx": [0] * n_words,
        }
    )
    n_fix = len(fix_x)
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"] * n_fix,
            "trial_id": ["t"] * n_fix,
            "text_id": ["text"] * n_fix,
            "x": fix_x,
            "y": fix_y,
            "duration_ms": [200.0] * n_fix,
            "timestamp_ms": [100.0 * i for i in range(n_fix)],
            "fixation_id": list(range(1, n_fix + 1)),
            "order_in_trial": list(range(1, n_fix + 1)),
            "word_id": word_ids if word_ids is not None else list(range(1, n_fix + 1)),
        }
    )
    return words, fixations


def _arc_figure(words, fixations, **overrides) -> go.Figure:
    kwargs = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        show_words=True,
        scale_text_to_boxes=False,
        duration_size_legend=False,
        saccade_render_mode="Arc",
    )
    kwargs.update(overrides)
    return make_scanpath_figure(words, fixations, **kwargs)


def _curve_top(fig: go.Figure) -> float:
    """Smallest drawn y (highest point — the axis is inverted) of the saccades."""
    curve = next(t for t in fig.data if t.name == "saccades")
    return min(float(y) for y in curve.y if y is not None)


def _view_top(fig: go.Figure) -> float:
    return float(fig.layout.yaxis.range[1])


class TestSnappedArcFitsTheView:
    """Arc + Snap used to reserve headroom from the recorded fixations but draw
    from the snapped ones, so the apex left the plot (round-8 review, finding 3)."""

    def test_wide_boxes_near_shared_edge(self):
        # The review's repro: two 250-px boxes, fixations 2 px apart at their
        # shared edge. #422: the snap keeps their x and lifts both to the line's
        # top edge.
        words, fix = _snap_trial(
            [100.0, 350.0], [100.0, 100.0], [250.0, 250.0], [349.0, 351.0], [110, 110]
        )
        fig = _arc_figure(words, fix, fixation_snap_to_line=True)
        assert _curve_top(fig) >= _view_top(fig)

    def test_different_endpoint_heights(self):
        # Two lines of wide words: the snap lifts each endpoint to its line's top
        # edge, so the steep arc crests above the higher one.
        words, fix = _snap_trial(
            [50.0, 450.0], [100.0, 160.0], [300.0, 300.0], [345.0, 455.0], [118, 178]
        )
        fig = _arc_figure(words, fix, fixation_snap_to_line=True)
        assert _curve_top(fig) >= _view_top(fig)

    def test_unsnapped_arc_is_unchanged(self):
        # Snap off: the headroom still comes from the recorded positions — a
        # 2-px saccade barely arches, so Arc reserves only its 2 % margin.
        words, fix = _snap_trial(
            [100.0, 350.0], [100.0, 100.0], [250.0, 250.0], [349.0, 351.0], [110, 110]
        )
        fig = _arc_figure(words, fix)
        straight = _arc_figure(words, fix, saccade_render_mode="Straight")
        assert _curve_top(fig) >= _view_top(fig)
        margin = 0.02 * abs(straight.layout.yaxis.range[0] - _view_top(straight))
        apex = _curve_top(fig)
        assert _view_top(fig) == pytest.approx(
            min(_view_top(straight), apex - margin), abs=0.5
        )

    def test_unassigned_fixations_take_the_nearest_line(self):
        # word_id NaN and outside every box: #422 snaps each onto the line
        # nearest its y (here the one line, top edge 100) and keeps its x; the
        # arc's headroom follows the snapped ends.
        words, fix = _snap_trial(
            [100.0, 350.0],
            [100.0, 100.0],
            [250.0, 250.0],
            [20.0, 700.0],
            [130, 150],
            word_ids=[np.nan, np.nan],
        )
        snapped = _arc_figure(words, fix, fixation_snap_to_line=True)
        markers = next(t for t in snapped.data if t.name == "Fixations")
        assert list(markers.x) == [20.0, 700.0]
        assert list(markers.y) == pytest.approx([100.0, 100.0])
        assert _curve_top(snapped) >= _view_top(snapped)

    def test_whole_monitor_shows_the_screen_and_never_clips_the_arc(self):
        # Words on the screen's first line: the snapped arc rises past the top
        # edge, so the whole-monitor view grows above 0 instead of cutting it.
        words, fix = _snap_trial(
            [0.0, 400.0], [10.0, 10.0], [400.0, 400.0], [100.0, 700.0], [20, 20]
        )
        fig = _arc_figure(words, fix, fixation_snap_to_line=True, fit_to_monitor=True)
        assert fig.layout.yaxis.range[0] == 600
        assert _view_top(fig) < 0
        assert _curve_top(fig) >= _view_top(fig)
        assert list(fig.layout.xaxis.range) == [0, 800]
