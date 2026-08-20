"""VIZ-23 / BUG-13: the three scanpath builders honour the same viz settings.

VIZ-21 mapped which viz setting reaches which builder; VIZ-23 turns the ❌ cells
into ✅. Two properties are pinned here:

1. **Parity.** Every option added to :func:`make_scanpath_animation` /
   :func:`make_comparison_figure` defaults to the builder's previous behaviour,
   so an existing caller that passes nothing gets the figure it got before —
   asserted on the concrete structure (trace inventory, marker symbols, colorbar
   dict, label colours) and, for the whole figure, by round-tripping the JSON.
2. **Effect.** Each new option demonstrably changes the figure when set.

Plus BUG-13: the Arc-mode headroom reservation now minimises ``y(t)`` over the
drawn Bézier instead of sampling its ``t = 0.5`` point, so a wide saccade whose
endpoints differ in ``y`` no longer clips against the top of the view.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.constants import (
    COMPARISON_PALETTE,
    HIGHLIGHTED_TEXT_COLOR,
    WORD_LABEL_COLOR,
)
from scanpath_studio.plots import (
    _ARCH_FRAC,
    _COLORBAR_BOTTOM_PX,
    _COLORBAR_RESERVE_PX,
    _CONTROLS_MARGIN_PX,
    COLORBAR_LEN_FRACTION,
    _arch_apex_y,
    _arch_points,
    _saccade_arrow_markers,
    make_comparison_figure,
    make_scanpath_animation,
    make_scanpath_figure,
)

# A 1x1 transparent PNG as a `data:` URI — `_image_to_data_uri` passes those
# straight through, so the background-image layer needs no file on disk.
_IMAGE_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Fixtures: a 6-word / 2-line trial, with a highlight column and one fixation
# parked outside every box (for the out-of-bounds flag).
# ---------------------------------------------------------------------------


def _words(participant: str = "p1", trial: str = "t1") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 6,
            "trial_id": [trial] * 6,
            "word_id": [0, 1, 2, 3, 4, 5],
            "x": [100.0, 200.0, 300.0, 100.0, 200.0, 300.0],
            "y": [50.0, 50.0, 50.0, 150.0, 150.0, 150.0],
            "width": [80.0] * 6,
            "height": [40.0] * 6,
            "text": ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"],
            "text_id": ["para1"] * 6,
            "is_in_aspan": [False, False, True, True, False, False],
            "total_fixation_duration_ms": [210.0, 180.0, 260.0, 300.0, 150.0, 190.0],
        }
    )


def _fixations(
    participant: str = "p1",
    trial: str = "t1",
    *,
    durations: list | None = None,
    out_of_bounds: bool = False,
) -> pd.DataFrame:
    ys = [70.0, 70.0, 70.0, 170.0, 170.0, 170.0]
    if out_of_bounds:
        # Fixation #4 (index 3) lands well below the last line of text.
        ys[3] = 360.0
    return pd.DataFrame(
        {
            "participant_id": [participant] * 6,
            "trial_id": [trial] * 6,
            "x": [120.0, 220.0, 320.0, 120.0, 220.0, 320.0],
            "y": ys,
            "duration_ms": durations or [200.0, 250.0, 180.0, 300.0, 220.0, 260.0],
            "timestamp_ms": [0.0, 300.0, 700.0, 1000.0, 1400.0, 1800.0],
            "order_in_trial": [1, 2, 3, 4, 5, 6],
            "word_id": [0, 1, 2, 3, 4, 5],
        }
    )


def _anim(words=None, fixations=None, **overrides):
    kwargs = dict(
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
        font_family="monospace",
    )
    kwargs.update(overrides)
    return make_scanpath_animation(
        _words() if words is None else words,
        _fixations() if fixations is None else fixations,
        **kwargs,
    )


def _compare(**overrides):
    words = pd.concat([_words("p1"), _words("p2")], ignore_index=True)
    fixations = pd.concat([_fixations("p1"), _fixations("p2")], ignore_index=True)
    kwargs = dict(
        canvas_width=800,
        canvas_height=400,
        font_family="monospace",
        base_font_size=12,
        show_word_labels=True,
    )
    kwargs.update(overrides)
    return make_comparison_figure(
        words, fixations, ("p1", "t1"), ("p2", "t1"), **kwargs
    )


def _static(**overrides):
    kwargs = dict(
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
        font_family="monospace",
        x_field="x",
        y_field="y",
        show_words=True,
        show_word_labels=True,
        show_fixations=True,
        show_order=False,
        show_saccades=True,
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
    words = overrides.pop("words", None)
    fixations = overrides.pop("fixations", None)
    kwargs.update(overrides)
    return make_scanpath_figure(
        _words() if words is None else words,
        _fixations() if fixations is None else fixations,
        **kwargs,
    )


def _labels(fig):
    return [t for t in fig.data if t.name == "words"]


def _trail(fig):
    return next(t for t in fig.data if t.name == "Scanpath A")


def _markers(fig):
    """The comparison figure's fixation-marker traces (one per scanpath)."""
    return [t for t in fig.data if t.mode and t.mode.startswith("markers")]


def _frame_trace(fig, frame, base_index):
    """The frame's update for the base trace at ``base_index``."""
    return frame.data[list(frame.traces).index(base_index)]


def _trace_index(fig, name):
    return next(i for i, t in enumerate(fig.data) if t.name == name)


def _t_half_apex(x0, y0, x1, y1, frac):
    """The pre-BUG-13 headroom estimate: the arch's Bézier value at t = 0.5."""
    return 0.25 * (y0 + y1) + 0.5 * (min(y0, y1) - frac * abs(x1 - x0))


# ---------------------------------------------------------------------------
# Animation — parity
# ---------------------------------------------------------------------------


class TestAnimationParity:
    """`make_scanpath_animation` without the new options renders as before."""

    def test_explicit_defaults_reproduce_the_figure_byte_for_byte(self):
        base = _anim()
        same = _anim(
            show_saccade_arrows=False,
            fixation_flags=None,
            text_color=WORD_LABEL_COLOR,
            highlight_column=None,
            highlight_text_color=HIGHLIGHTED_TEXT_COLOR,
            word_hover_measure=None,
            colorbar_orientation="Vertical",
            colorbar_tickangle=0,
            colorbar_tickfont_size=12,
        )
        assert same.to_json() == base.to_json()

    def test_word_labels_keep_the_flat_base_colour_and_plain_hover(self):
        # The words frame carries `is_in_aspan`, but nothing asked for it.
        label = _labels(_anim())[0]
        assert label.textfont.color == WORD_LABEL_COLOR  # one colour, not a list
        assert "Word #" in label.hovertemplate
        assert "Total fixation" not in label.hovertemplate

    def test_trace_inventory_is_unchanged(self):
        fig = _anim()
        assert [t.name for t in fig.data] == [
            "words",
            "Scanpath A",
            None,
            None,
            None,
        ]
        # labels + trail + order numbers + saccades + the current-fixation dot
        assert len(fig.data) == 5
        # …and every frame updates exactly those four animated traces.
        assert all(len(fr.traces) == 4 for fr in fig.frames)
        assert not [t for t in fig.data if t.name == "saccade direction"]

    def test_transport_controls_are_above_the_plot(self):
        fig = _anim()
        assert fig.layout.updatemenus[0].y == 1
        assert fig.layout.updatemenus[0].yanchor == "bottom"
        assert fig.layout.sliders[0].y == 1
        assert fig.layout.sliders[0].yanchor == "bottom"
        assert fig.layout.margin.t == _CONTROLS_MARGIN_PX

    def test_colorbar_keeps_its_placement_and_reserve(self):
        fig = _anim(color_by="duration_ms", show_colorbars=True)
        cb = _trail(fig).marker.colorbar
        assert cb.title.text == "Duration Ms"
        assert cb.lenmode == "fraction"
        assert cb.len == pytest.approx(COLORBAR_LEN_FRACTION)
        assert (cb.y, cb.yanchor) == (0.5, "middle")
        assert cb.orientation in (None, "v")
        assert fig.layout.margin.r == _COLORBAR_RESERVE_PX
        assert fig.layout.margin.t == _CONTROLS_MARGIN_PX
        assert fig.layout.margin.b == 0

    def test_colorbar_is_now_the_static_figures_styled_one(self):
        """Deliberate VIZ-23 change: both builders share `_colorbar_dict`."""
        anim_cb = _trail(
            _anim(color_by="duration_ms", show_colorbars=True)
        ).marker.colorbar
        static = _static(show_colorbars=True)
        static_cb = next(
            t for t in static.data if t.name == "Fixations"
        ).marker.colorbar
        assert anim_cb.thickness == static_cb.thickness
        assert anim_cb.tickfont.size == static_cb.tickfont.size
        assert anim_cb.tickangle == static_cb.tickangle
        assert anim_cb.outlinewidth == static_cb.outlinewidth


class TestAnimationWordLabels:
    def test_text_color_applies(self):
        assert _labels(_anim(text_color="#123456"))[0].textfont.color == "#123456"

    def test_highlight_column_tints_only_the_flagged_words(self):
        fig = _anim(highlight_column="is_in_aspan", highlight_text_color="#ff0000")
        base = WORD_LABEL_COLOR
        assert list(_labels(fig)[0].textfont.color) == [
            base,
            base,
            "#ff0000",
            "#ff0000",
            base,
            base,
        ]

    def test_highlight_text_color_needs_the_column(self):
        # Same defence the static figure has: no column named, no tinting.
        label = _labels(_anim(highlight_text_color="#ff0000"))[0]
        assert label.textfont.color == WORD_LABEL_COLOR

    def test_word_hover_measure_adds_its_line(self):
        label = _labels(_anim(word_hover_measure="total_fixation_duration_ms"))[0]
        assert "Total fixation" in label.hovertemplate
        assert label.customdata.shape[1] == 3  # word_id, line, measure


class TestAnimationSaccadeArrows:
    def test_arrows_reveal_with_their_saccades(self):
        fig = _anim(show_saccade_arrows=True)
        arrows = [t for t in fig.data if t.name == "saccade direction"]
        assert len(arrows) == 1
        mid_x, mid_y, angles = _saccade_arrow_markers(_fixations(), "x", "y")
        assert list(arrows[0].marker.angle) == pytest.approx(angles)
        assert arrows[0].marker.symbol == "arrow"
        # Frame zero: only the first fixation exists, so no saccade and no arrow.
        assert all(v is None for v in arrows[0].x)

        idx = _trace_index(fig, "saccade direction")
        revealed = [
            sum(v is not None for v in _frame_trace(fig, fr, idx).x)
            for fr in fig.frames
        ]
        assert revealed[0] == 0
        assert revealed[-1] == len(mid_x)
        assert revealed == sorted(revealed)  # never un-reveals
        last = _frame_trace(fig, fig.frames[-1], idx)
        assert [v for v in last.x if v is not None] == pytest.approx(mid_x)
        assert [v for v in last.y if v is not None] == pytest.approx(mid_y)

    def test_arrows_follow_the_saccade_layer_toggle(self):
        fig = _anim(show_saccades=False, show_saccade_arrows=True)
        assert not [t for t in fig.data if t.name == "saccade direction"]


class TestAnimationFixationFlags:
    _SHORT = {"short": {"mode": "Discard", "threshold_ms": 80}}
    _OOB_HIGHLIGHT = {"oob": {"mode": "Highlight", "symbol": "x", "color": "#00ff00"}}

    def test_discard_drops_the_fixation_from_the_replay(self):
        fixations = _fixations(durations=[200.0, 30.0, 180.0, 300.0, 220.0, 260.0])
        assert len(_trail(_anim(fixations=fixations)).x) == 6
        trail = _trail(_anim(fixations=fixations, fixation_flags=self._SHORT))
        assert len(trail.x) == 5

    def test_discard_does_not_re_frame_the_view(self):
        """Like the static figure, the axes are computed before the filter."""
        fixations = _fixations(out_of_bounds=True)
        flags = {"oob": {"mode": "Discard"}}
        plain = _anim(fixations=fixations)
        filtered = _anim(fixations=fixations, fixation_flags=flags)
        assert tuple(filtered.layout.yaxis.range) == tuple(plain.layout.yaxis.range)
        static_plain = _static(fixations=fixations)
        static_filtered = _static(fixations=fixations, fixation_flags=flags)
        assert tuple(static_filtered.layout.yaxis.range) == tuple(
            static_plain.layout.yaxis.range
        )

    def test_highlight_overlays_reveal_with_the_replay(self):
        fixations = _fixations(out_of_bounds=True)
        fig = _anim(fixations=fixations, fixation_flags=self._OOB_HIGHLIGHT)
        overlay = [t for t in fig.data if t.name == "Out of bounds"]
        assert len(overlay) == 1
        assert overlay[0].marker.symbol == "x"
        assert overlay[0].marker.color == "#00ff00"
        assert overlay[0].showlegend
        # Exactly one fixation is flagged, and it is not the first — so nothing
        # shows at frame zero and exactly one point shows at the end.
        idx = _trace_index(fig, "Out of bounds")
        assert sum(v is not None for v in overlay[0].x) == 0
        last = _frame_trace(fig, fig.frames[-1], idx)
        assert [v for v in last.y if v is not None] == pytest.approx([360.0])
        # The overlay legend gets the same floating key as the A/B legend.
        assert fig.layout.legend.bgcolor == "rgba(255,255,255,0.7)"

    def test_no_flags_adds_no_overlay(self):
        fig = _anim(fixations=_fixations(out_of_bounds=True))
        assert not [t for t in fig.data if t.name in ("Short", "Long", "Out of bounds")]


class TestAnimationColorbarStyle:
    def test_orientation_tickangle_and_tickfont_apply(self):
        fig = _anim(
            color_by="duration_ms",
            show_colorbars=True,
            colorbar_orientation="Horizontal",
            colorbar_tickangle=45,
            colorbar_tickfont_size=9,
        )
        cb = _trail(fig).marker.colorbar
        assert cb.orientation == "h"
        assert cb.tickangle == 45
        assert cb.tickfont.size == 9
        # A horizontal bar takes bottom reserve while transport stays above.
        assert cb.y < 0
        assert fig.layout.margin.r == 0
        assert fig.layout.margin.t == _CONTROLS_MARGIN_PX
        assert fig.layout.margin.b == _COLORBAR_BOTTOM_PX


# ---------------------------------------------------------------------------
# Comparison — parity
# ---------------------------------------------------------------------------


class TestComparisonParity:
    def test_explicit_defaults_reproduce_the_figure_byte_for_byte(self):
        base = _compare()
        same = _compare(
            fixation_symbol="circle",
            highlight_column=None,
            highlight_text_color=HIGHLIGHTED_TEXT_COLOR,
            background_image=None,
            background_image_size=None,
            background_image_origin=None,
            background_image_opacity=1.0,
            colorbar_orientation="Vertical",
            colorbar_tickangle=0,
            colorbar_tickfont_size=12,
        )
        assert same.to_json() == base.to_json()

    def test_markers_are_still_palette_coloured_circles(self):
        markers = _markers(_compare())
        assert len(markers) == 2
        assert [m.marker.color for m in markers] == list(COMPARISON_PALETTE[:2])
        # Plotly's unset default was already "circle"; it is now stated outright.
        assert [m.marker.symbol for m in markers] == ["circle", "circle"]

    def test_word_labels_stay_flat_without_a_highlight_column(self):
        fig = _compare(highlight_text_color="#ff0000")
        assert _labels(fig)
        for label in _labels(fig):
            assert label.textfont.color == WORD_LABEL_COLOR

    def test_no_background_image_and_no_bottom_reserve_by_default(self):
        fig = _compare()
        assert not fig.layout.images
        assert fig.layout.margin.b == 0


class TestComparisonFixationSymbol:
    def test_symbol_reaches_both_scanpaths(self):
        markers = _markers(_compare(fixation_symbol="square"))
        assert [m.marker.symbol for m in markers] == ["square", "square"]

    def test_symbol_reaches_the_metric_coloured_branch(self):
        markers = _markers(_compare(fixation_symbol="diamond", color_by="duration_ms"))
        assert [m.marker.symbol for m in markers] == ["diamond", "diamond"]
        assert markers[0].marker.colorscale  # still the metric fill

    def test_glyph_shapes_fall_back_to_the_default(self):
        # ♥ is drawn as text in the static figure; a Plotly marker can't take it.
        markers = _markers(_compare(fixation_symbol="heart"))
        assert [m.marker.symbol for m in markers] == ["circle", "circle"]

    @pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
    def test_symbol_reaches_the_split_layouts(self, layout):
        markers = _markers(_compare(layout=layout, fixation_symbol="square"))
        assert markers
        assert all(m.marker.symbol == "square" for m in markers)


class TestComparisonHighlightColumn:
    _EXPECTED = [
        WORD_LABEL_COLOR,
        WORD_LABEL_COLOR,
        "#ff0000",
        "#ff0000",
        WORD_LABEL_COLOR,
        WORD_LABEL_COLOR,
    ]

    def test_overlay_labels_take_the_highlight_colour(self):
        fig = _compare(highlight_column="is_in_aspan", highlight_text_color="#ff0000")
        assert _labels(fig)
        for label in _labels(fig):
            assert list(label.textfont.color) == self._EXPECTED

    @pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
    def test_split_labels_take_the_highlight_colour(self, layout):
        fig = _compare(
            layout=layout,
            highlight_column="is_in_aspan",
            highlight_text_color="#ff0000",
        )
        assert _labels(fig)
        for label in _labels(fig):
            assert list(label.textfont.color) == self._EXPECTED


class TestComparisonBackgroundImage:
    def test_overlay_gains_the_stimulus_image(self):
        fig = _compare(
            background_image=_IMAGE_URI,
            background_image_size=(800.0, 400.0),
            background_image_opacity=0.4,
        )
        assert len(fig.layout.images) == 1
        image = fig.layout.images[0]
        assert image.source == _IMAGE_URI
        assert image.layer == "below"
        assert (image.sizex, image.sizey) == (800.0, 400.0)
        assert image.opacity == pytest.approx(0.4)
        assert (image.x, image.y) == (0.0, 0.0)

    def test_overlay_honours_the_origin(self):
        fig = _compare(
            background_image=_IMAGE_URI,
            background_image_size=(400.0, 200.0),
            background_image_origin=(305.0, 44.5),
        )
        image = fig.layout.images[0]
        assert (image.x, image.y) == (305.0, 44.5)

    @pytest.mark.parametrize(
        "layout,refs",
        [("side_by_side", ["x", "x2"]), ("stacked", ["x", "x2"])],
    )
    def test_split_layouts_get_one_image_per_panel(self, layout, refs):
        fig = _compare(
            layout=layout,
            background_image=_IMAGE_URI,
            background_image_size=(800.0, 400.0),
        )
        assert [i.xref for i in fig.layout.images] == refs

    def test_missing_size_draws_nothing(self):
        fig = _compare(background_image=_IMAGE_URI)
        assert not fig.layout.images


class TestComparisonColorbarStyle:
    def _colorbar(self, fig):
        bars = [m.marker.colorbar for m in _markers(fig) if m.marker.showscale]
        assert len(bars) == 1  # one shared bar, on the first scanpath
        return bars[0]

    def test_default_is_the_shared_styled_bar(self):
        cb = self._colorbar(_compare(color_by="duration_ms", show_colorbars=True))
        assert cb.title.text == "Duration Ms"
        assert cb.thickness == 14
        assert cb.tickfont.size == 12
        assert cb.orientation in (None, "v")

    def test_orientation_tickangle_and_tickfont_apply(self):
        fig = _compare(
            color_by="duration_ms",
            show_colorbars=True,
            colorbar_orientation="Horizontal",
            colorbar_tickangle=30,
            colorbar_tickfont_size=9,
        )
        cb = self._colorbar(fig)
        assert cb.orientation == "h"
        assert cb.tickangle == 30
        assert cb.tickfont.size == 9
        # …and the figure grows a band for it instead of overlapping the plot.
        assert fig.layout.margin.b == _COLORBAR_BOTTOM_PX

    def test_split_layout_reserves_the_same_band(self):
        fig = _compare(
            layout="side_by_side",
            color_by="duration_ms",
            show_colorbars=True,
            colorbar_orientation="Horizontal",
        )
        assert fig.layout.margin.b == _COLORBAR_BOTTOM_PX
        assert self._colorbar(fig).orientation == "h"


# ---------------------------------------------------------------------------
# BUG-13 — Arc headroom uses the curve's real apex
# ---------------------------------------------------------------------------


class TestArchApex:
    def test_level_saccade_matches_the_old_midpoint_formula(self):
        for x0, x1 in [(100.0, 500.0), (500.0, 100.0)]:
            assert _arch_apex_y(x0, 200.0, x1, 200.0, _ARCH_FRAC) == pytest.approx(
                _t_half_apex(x0, 200.0, x1, 200.0, _ARCH_FRAC)
            )

    def test_sloped_saccade_peaks_above_the_midpoint_sample(self):
        x0, y0, x1, y1 = 100.0, 300.0, 600.0, 120.0
        apex = _arch_apex_y(x0, y0, x1, y1, _ARCH_FRAC)
        # Smaller y is higher on the reversed screen axis: the real peak is
        # ABOVE the point the old formula reserved for.
        assert apex < _t_half_apex(x0, y0, x1, y1, _ARCH_FRAC)

    def test_apex_bounds_the_drawn_curve(self):
        for x0, y0, x1, y1 in [
            (100.0, 300.0, 600.0, 120.0),
            (600.0, 120.0, 100.0, 300.0),
            (100.0, 200.0, 500.0, 200.0),
            (100.0, 100.0, 140.0, 400.0),
        ]:
            apex = _arch_apex_y(x0, y0, x1, y1, _ARCH_FRAC)
            _, ys = _arch_points(x0, y0, x1, y1, _ARCH_FRAC, n=4001)
            assert apex <= min(ys) + 1e-9  # nothing drawn above the apex
            assert apex == pytest.approx(min(ys), abs=1e-3)

    def test_degenerate_saccades(self):
        # Zero horizontal span: no rise, so the apex is the higher endpoint.
        assert _arch_apex_y(100.0, 200.0, 100.0, 260.0, _ARCH_FRAC) == 200.0
        assert _arch_apex_y(100.0, 200.0, 100.0, 200.0, _ARCH_FRAC) == 200.0


class TestArcHeadroom:
    """The reserved view must cover the true peak of a sloped arc."""

    _WORDS = pd.DataFrame(
        {
            "participant_id": ["p1"] * 2,
            "trial_id": ["t1"] * 2,
            "word_id": [0, 1],
            "text": ["a", "b"],
            "x": [100.0, 900.0],
            "y": [50.0, 250.0],
            "width": [80.0, 80.0],
            "height": [40.0, 40.0],
        }
    )

    def _fix(self, y1: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                "x": [140.0, 940.0],
                "y": [70.0, y1],
                "duration_ms": [200.0, 200.0],
                "timestamp_ms": [0.0, 100.0],
                "order_in_trial": [1, 2],
            }
        )

    def _figure(self, y1: float, mode: str = "Arc"):
        return _static(
            words=self._WORDS,
            fixations=self._fix(y1),
            saccade_render_mode=mode,
            show_word_labels=False,
        )

    def _reserved_top(self, y1: float, apex: float) -> float:
        """What the builder reserves for ``apex``: 2% of the un-arced span."""
        straight = self._figure(y1, "Straight").layout.yaxis.range
        bottom, top_pre = float(straight[0]), float(straight[1])
        return min(top_pre, apex - 0.02 * abs(bottom - top_pre))

    def test_sloped_arc_is_not_clipped(self):
        y1 = 270.0
        fig = self._figure(y1)
        top = min(fig.layout.yaxis.range)
        saccades = next(t for t in fig.data if t.name == "saccades")
        drawn_apex = float(np.nanmin([v for v in saccades.y if v is not None]))
        assert top <= drawn_apex  # the apex sits inside the view
        # …and the old t=0.5 estimate sat BELOW the real peak, so the reservation
        # it produced clipped the top of the arc.
        old_estimate = _t_half_apex(140.0, 70.0, 940.0, y1, _ARCH_FRAC)
        assert old_estimate > drawn_apex
        assert self._reserved_top(y1, old_estimate) > drawn_apex
        # The new reservation is the true Bézier apex, plus the 2% margin.
        true_apex = _arch_apex_y(140.0, 70.0, 940.0, y1, _ARCH_FRAC)
        assert top == pytest.approx(self._reserved_top(y1, true_apex))

    def test_level_arc_reserves_exactly_what_it_did_before(self):
        y1 = 70.0
        top = min(self._figure(y1).layout.yaxis.range)
        old_estimate = _t_half_apex(140.0, 70.0, 940.0, y1, _ARCH_FRAC)
        assert _arch_apex_y(140.0, 70.0, 940.0, y1, _ARCH_FRAC) == pytest.approx(
            old_estimate
        )
        assert top == pytest.approx(self._reserved_top(y1, old_estimate))
