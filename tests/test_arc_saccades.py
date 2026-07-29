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
            show_colorbars=False,
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
