"""Tests for plots.py module."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio.constants import SACCADE_CLASS_COLORS, SACCADE_CLASS_LABELS
from scanpath_studio.plots import (
    _ANIM_MAX_FRAMES,
    _ANIM_MIN_FRAME_MS,
    _arch_points,
    _image_to_data_uri,
    _latin_advance,
    _line_pitch,
    _png_pixel_size,
    _saccade_arrow_markers,
    _width_fit_font,
    _word_label_font_px,
    animation_autoplay_frame_duration,
    animation_autoplay_post_script,
    animation_playback_ms,
    build_critical_span_overlay,
    build_word_boxes,
    make_comparison_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    split_scanpath_layers,
)

# A valid 1x1 RGBA PNG — header lets _png_pixel_size + base64 encoding work.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000100052301e20000000049454e44ae"
    "426082"
)


def _scanpath_kwargs(**overrides):
    """Baseline make_scanpath_figure kwargs for the decoration/colour tests."""
    base = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=12,
        font_family="Arial",
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
        order_font_color="#000000",
        show_colorbars=False,
        fixation_color_range=None,
        heatmap_range=None,
    )
    base.update(overrides)
    return base


def _plot_region(fig):
    """The plotting area (figure minus margins) — what scaleanchor sizes."""
    m = fig.layout.margin
    return (
        fig.layout.width - (m.l or 0) - (m.r or 0),
        fig.layout.height - (m.t or 0) - (m.b or 0),
    )


class TestDecorationDoesNotShrinkPlot:
    """A colorbar/legend must sit in reserved margin, not steal space from the
    equal-aspect plot region (the colorbar-shrinks-the-plot bug, TODO 2)."""

    def test_colorbar_keeps_plot_region(
        self, normalized_words_df, normalized_fixations_df
    ):
        off = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **_scanpath_kwargs()
        )
        on = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_colorbars=True),
        )
        assert _plot_region(on) == _plot_region(off)
        # The figure itself grew to hold the colorbar (it didn't shrink the plot).
        assert on.layout.width > off.layout.width

    def test_discrete_legend_keeps_plot_region(
        self, normalized_words_df, normalized_fixations_df
    ):
        off = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **_scanpath_kwargs()
        )
        on = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(color_by_line=True),
        )
        # Same plot region; the by-line legend is reserved above the plot.
        assert _plot_region(on) == _plot_region(off)
        assert on.layout.height > off.layout.height


class TestDriftConnectors:
    """PRE-3: the drift-connector overlay adds exactly one extra Scatter trace."""

    def test_connectors_add_one_trace(
        self, normalized_words_df, normalized_fixations_df
    ):
        off = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **_scanpath_kwargs()
        )
        connector_y = [float(y) + 25 for y in normalized_fixations_df["y"]]
        on = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_connectors=True, connector_y=connector_y),
        )
        assert len(on.data) == len(off.data) + 1

    def test_connectors_noop_without_connector_y(
        self, normalized_words_df, normalized_fixations_df
    ):
        off = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **_scanpath_kwargs()
        )
        # show_connectors on but no connector_y → nothing drawn.
        on = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_connectors=True),
        )
        assert len(on.data) == len(off.data)


class TestSaccadeColor:
    def test_saccade_color_threads_to_line_and_arrows(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_saccade_arrows=True, saccade_color="#123456"),
        )
        line = [t for t in fig.data if t.name == "saccades"]
        assert line and line[0].line.color == "#123456"
        arrows = [t for t in fig.data if t.name == "saccade direction"]
        assert arrows and arrows[0].marker.color == "#123456"

    def test_saccade_width_threads_to_line(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(saccade_width=5.5),
        )
        line = [t for t in fig.data if t.name == "saccades"]
        assert line and float(line[0].line.width) == 5.5


class TestSaccadeColorByType:
    """VIZ-8: colour each saccade by its reading class."""

    def test_uniform_mode_is_a_single_trace(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(),  # saccade_color_mode defaults to "Uniform"
        )
        assert [t for t in fig.data if t.name == "saccades"]
        assert not [t for t in fig.data if t.legendgroup == "saccade_type"]

    def test_by_type_splits_into_legended_class_traces(self):
        # A 2-line trial that exercises forward + return-sweep + regression, so
        # the by-type render must produce more than one class sub-trace.
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 6,
                "trial_id": ["t1"] * 6,
                "word_id": [1, 2, 3, 4, 5, 6],
                "text": ["the", "cat", "sat", "on", "the", "mat"],
                "x": [100, 200, 300, 100, 200, 300],
                "y": [50, 50, 50, 150, 150, 150],
                "width": [80, 80, 80, 80, 80, 80],
                "height": [40, 40, 40, 40, 40, 40],
            }
        )
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 5,
                "trial_id": ["t1"] * 5,
                "x": [140, 240, 340, 140, 240],
                "y": [70, 70, 70, 170, 170],
                "word_id": [1, 2, 3, 4, 5],  # forward, forward, return sweep, forward
                "duration_ms": [200, 200, 200, 200, 200],
                "timestamp_ms": [0, 200, 400, 600, 800],
                "order_in_trial": [1, 2, 3, 4, 5],
            }
        )
        fig = make_scanpath_figure(
            words, fix, **_scanpath_kwargs(saccade_color_mode="By type")
        )
        # No single "saccades" trace; instead one legended sub-trace per class.
        assert not [t for t in fig.data if t.name == "saccades"]
        by_type = [t for t in fig.data if t.legendgroup == "saccade_type"]
        assert len(by_type) >= 2
        assert all(t.showlegend for t in by_type)
        assert SACCADE_CLASS_LABELS["return_sweep"] in {t.name for t in by_type}
        # Legend order follows SACCADE_CLASS_ORDER (forward before return sweep).
        names = [t.name for t in by_type]
        assert names == sorted(
            names, key=lambda n: list(SACCADE_CLASS_LABELS.values()).index(n)
        )

    def test_by_type_honors_custom_palette(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                saccade_color_mode="By type",
                saccade_class_colors={**SACCADE_CLASS_COLORS, "forward": "#abcdef"},
            ),
        )
        fwd = [
            t
            for t in fig.data
            if t.name == SACCADE_CLASS_LABELS["forward"]
            and t.legendgroup == "saccade_type"
        ]
        assert fwd and fwd[0].line.color == "#abcdef"

    def test_other_class_stays_grey_with_ui_palette(self):
        # The UI supplies a 5-key palette (no "other"). An off-text fixation
        # produces an "other" saccade; it must still render its fixed grey, not
        # fall back to the uniform line colour (parity with CLI/API).
        from scanpath_studio.constants import SACCADE_CLASS_EDITABLE

        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3,
                "trial_id": ["t1"] * 3,
                "word_id": [1, 2, 3],
                "text": ["a", "b", "c"],
                "x": [100, 200, 300],
                "y": [50, 50, 50],
                "width": [80, 80, 80],
                "height": [40, 40, 40],
            }
        )
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3,
                "trial_id": ["t1"] * 3,
                "x": [140, 5000, 240],  # middle fixation is far off-text
                "y": [70, 5000, 70],
                "duration_ms": [200, 200, 200],
                "timestamp_ms": [0, 200, 400],
                "order_in_trial": [1, 2, 3],
            }
        )
        ui_palette = {c: SACCADE_CLASS_COLORS[c] for c in SACCADE_CLASS_EDITABLE}
        fig = make_scanpath_figure(
            words,
            fix,
            **_scanpath_kwargs(
                saccade_color="#ff0000",  # uniform colour, must NOT leak to "other"
                saccade_color_mode="By type",
                saccade_class_colors=ui_palette,
            ),
        )
        other = [
            t
            for t in fig.data
            if t.name == SACCADE_CLASS_LABELS["other"]
            and t.legendgroup == "saccade_type"
        ]
        assert other and other[0].line.color == SACCADE_CLASS_COLORS["other"]


class TestHeatmapNormalization:
    """VIZ-3: Linear vs Log heatmap colour scaling."""

    def test_apply_heatmap_norm_helper(self):
        from scanpath_studio.plots import _apply_heatmap_norm

        assert list(_apply_heatmap_norm([0, 1, 9, 99], "Linear")) == [0, 1, 9, 99]
        log = _apply_heatmap_norm([0, 1, 9, 99], "Log")
        # log1p: log(1)=0, log(2), log(10), log(100).
        assert log[0] == 0.0
        assert log[1] == pytest.approx(0.6931, rel=1e-3)
        # Negative values are clamped to 0 (log1p(0)=0), never NaN.
        assert _apply_heatmap_norm([-5.0], "Log")[0] == 0.0

    def _heat_kwargs(self, style, norm):
        return _scanpath_kwargs(
            show_words=False,
            show_word_labels=False,
            show_fixations=False,
            show_saccades=False,
            show_heatmap=True,
            heatmap_style=style,
            heatmap_norm=norm,
            heatmap_metric="duration_ms",
        )

    def test_word_box_log_changes_colours(
        self, normalized_words_df, normalized_fixations_df
    ):
        def box_colors(norm):
            fig = make_scanpath_figure(
                normalized_words_df,
                normalized_fixations_df,
                **self._heat_kwargs("Word boxes", norm),
            )
            return [s.fillcolor for s in fig.layout.shapes if s.layer == "below"]

        lin, log = box_colors("Linear"), box_colors("Log")
        assert lin and len(lin) == len(log)
        assert lin != log  # log scaling remaps the box tints

    def test_interpolated_log_changes_z(
        self, normalized_words_df, normalized_fixations_df
    ):
        def heat_z(norm):
            fig = make_scanpath_figure(
                normalized_words_df,
                normalized_fixations_df,
                **self._heat_kwargs("Interpolated", norm),
            )
            t = [t for t in fig.data if t.name == "Fixation heatmap"][0]
            import numpy as np

            return np.nan_to_num(np.array(t.z, dtype=float))

        import numpy as np

        assert not np.allclose(heat_z("Linear"), heat_z("Log"))

    def test_density_fallback_is_a_heatmap_trace(
        self, normalized_words_df, normalized_fixations_df
    ):
        # No words → density fallback; must render a go.Heatmap (so it honours
        # the norm) and mark the colour bar "(log)" in log mode.
        fig = make_scanpath_figure(
            normalized_words_df.iloc[0:0],
            normalized_fixations_df,
            **_scanpath_kwargs(
                show_words=False,
                show_word_labels=False,
                show_fixations=False,
                show_saccades=False,
                show_heatmap=True,
                heatmap_style="Word boxes",  # no words → density path
                heatmap_norm="Log",
                heatmap_metric="counts",
                show_colorbars=True,
            ),
        )
        heat = [t for t in fig.data if t.name == "Fixation heatmap"]
        assert heat and isinstance(heat[0], go.Heatmap)
        assert heat[0].colorbar.title.text.endswith("(log)")

    def test_word_box_range_endpoints_transform_with_values(self):
        # The core VIZ-3 contract: under Log the raw-unit heatmap_range keeps its
        # meaning because the endpoints are transformed alongside the values. So a
        # word AT an endpoint maps to the same colour under Linear and Log (both
        # land at colour position 0 or 1), while a mid-range word is compressed.
        # (Kills the mutation "compare transformed values against RAW endpoints".)
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3,
                "trial_id": ["t1"] * 3,
                "word_id": [1, 2, 3],
                "text": ["a", "b", "c"],
                "x": [100, 300, 500],
                "y": [50, 50, 50],
                "width": [80, 80, 80],
                "height": [40, 40, 40],
            }
        )
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3,
                "trial_id": ["t1"] * 3,
                "x": [140, 340, 540],  # one fixation centred in each box
                "y": [70, 70, 70],
                "duration_ms": [100.0, 500.0, 1000.0],  # → per-word summed weights
                "timestamp_ms": [0, 100, 200],
                "order_in_trial": [1, 2, 3],
            }
        )

        def box_colors(norm):
            fig = make_scanpath_figure(
                words,
                fix,
                **_scanpath_kwargs(
                    show_words=False,
                    show_word_labels=False,
                    show_fixations=False,
                    show_saccades=False,
                    show_heatmap=True,
                    heatmap_style="Word boxes",
                    heatmap_norm=norm,
                    heatmap_metric="duration_ms",
                    heatmap_range=(100.0, 1000.0),  # value 100 → pos 0, 1000 → pos 1
                ),
            )
            return [s.fillcolor for s in fig.layout.shapes if s.layer == "below"]

        lin, log = box_colors("Linear"), box_colors("Log")
        assert len(lin) == len(log) == 3
        assert lin[0] == log[0]  # value == range min → colour position 0.0 in both
        assert lin[2] == log[2]  # value == range max → colour position 1.0 in both
        assert lin[1] != log[1]  # mid-range word: log compresses it

    def _density_trace(self, norm, metric):
        empty_words = pd.DataFrame({"x": [], "y": [], "width": [], "height": []})
        # Five fixations stacked on one point + one elsewhere → an unambiguous hot
        # cell whose count / duration-sum and location are known. The cluster sits
        # at an ASYMMETRIC corner (low x, high y) so a dropped `grid.T` transpose
        # would misplace it (caught below).
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 6,
                "trial_id": ["t1"] * 6,
                "x": [200.0] * 5 + [800.0],
                "y": [700.0] * 5 + [300.0],
                "duration_ms": [10.0] * 6,
                "timestamp_ms": list(range(6)),
                "order_in_trial": list(range(6)),
            }
        )
        fig = make_scanpath_figure(
            empty_words,
            fix,
            **_scanpath_kwargs(
                show_words=False,
                show_word_labels=False,
                show_fixations=False,
                show_saccades=False,
                show_heatmap=True,
                heatmap_style="Word boxes",  # no words → density path
                heatmap_norm=norm,
                heatmap_metric=metric,
            ),
        )
        return [t for t in fig.data if t.name == "Fixation heatmap"][0]

    def test_density_linear_orientation_and_magnitude(self):
        import numpy as np

        # counts: the hottest cell holds the 5 stacked fixations…
        t = self._density_trace("Linear", "counts")
        z = np.array(t.z, dtype=float)
        assert np.nanmax(z) == 5.0
        # …and sits at the (x, y) they were placed at (pins the grid.T orientation:
        # cluster is at low-x / high-y, so a missing transpose flips it).
        row, col = np.unravel_index(np.nanargmax(z), z.shape)
        assert abs(float(t.x[col]) - 200.0) < abs(float(t.x[col]) - 800.0)
        assert abs(float(t.y[row]) - 700.0) < abs(float(t.y[row]) - 300.0)
        # duration-weighted: the same cell now holds the summed dwell (5 × 10 ms).
        tw = self._density_trace("Linear", "duration_ms")
        assert np.nanmax(np.array(tw.z, dtype=float)) == 50.0

    def test_density_log_is_log1p_of_linear(self):
        import numpy as np

        lin = np.array(self._density_trace("Linear", "counts").z, dtype=float)
        log = np.array(self._density_trace("Log", "counts").z, dtype=float)
        # Log density is exactly log1p of the linear grid (NaNs — empty cells —
        # stay NaN in both). Kills the "density ignores the norm" mutation.
        assert not np.allclose(np.nan_to_num(lin), np.nan_to_num(log))
        mask = ~np.isnan(lin)
        assert np.allclose(log[mask], np.log1p(lin[mask]))


class TestLinearReadingView:
    """VIZ-9: arced saccades + fixations snapped above their word."""

    def _trial(self):
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                "word_id": [1, 2],
                "text": ["the", "cat"],
                "x": [100, 300],
                "y": [50, 200],  # two different lines
                "width": [80, 80],
                "height": [40, 40],
            }
        )
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                # Inside each word box but OFF its centre (word centres are 140 /
                # 340) so the x-snap is observable, not a coincidental match.
                "x": [120.0, 320.0],
                "y": [75.0, 225.0],  # raw gaze, below each word's top edge
                "word_id": [1, 2],
                "duration_ms": [200.0, 200.0],
                "timestamp_ms": [0, 100],
                "order_in_trial": [1, 2],
            }
        )
        return words, fix

    def _kwargs(self, **over):
        return _scanpath_kwargs(
            show_words=False,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=True,
            show_heatmap=False,
            **over,
        )

    def test_arch_points_apex_is_above_chord(self):
        xs, ys = _arch_points(0.0, 100.0, 100.0, 100.0, 0.28)
        assert (xs[0], ys[0]) == (0.0, 100.0)  # endpoints preserved
        assert xs[-1] == pytest.approx(100.0) and ys[-1] == pytest.approx(100.0)
        assert min(ys) < 100.0  # apex rises above the chord (smaller y = up)
        # The rise scales with the HORIZONTAL span: doubling |dx| ~doubles the
        # bulge (pins `rise = frac*abs(x1-x0)`, not abs(y1-y0)).
        bulge_narrow = 100.0 - min(_arch_points(0.0, 100.0, 50.0, 100.0, 0.28)[1])
        bulge_wide = 100.0 - min(_arch_points(0.0, 100.0, 100.0, 100.0, 0.28)[1])
        assert bulge_wide == pytest.approx(2 * bulge_narrow, rel=1e-6)

    def test_arch_points_degenerate_cases(self):
        import numpy as np

        # Vertical saccade (x0==x1): rise = frac*|dx| = 0, so NO upward bulge past
        # the top endpoint (this fails if the rise used abs(y1-y0) instead).
        xs, ys = _arch_points(50.0, 0.0, 50.0, 100.0, 0.28)
        assert all(x == pytest.approx(50.0) for x in xs)
        assert min(ys) == pytest.approx(0.0, abs=1e-9)
        # Zero-length (refixation): collapses to a single point, no bulge.
        xs0, ys0 = _arch_points(10.0, 10.0, 10.0, 10.0, 0.28)
        assert min(ys0) == pytest.approx(10.0) and max(ys0) == pytest.approx(10.0)
        # A NaN endpoint propagates to NaN samples (Plotly skips them).
        xn, _ = _arch_points(float("nan"), 0.0, 100.0, 0.0, 0.28)
        assert any(np.isnan(v) for v in xn)

    def test_arc_mode_curves_the_saccade(self):
        words, fix = self._trial()
        straight = make_scanpath_figure(
            words, fix, **self._kwargs(saccade_render_mode="Straight")
        )
        arc = make_scanpath_figure(
            words, fix, **self._kwargs(saccade_render_mode="Arc")
        )
        s = [t for t in straight.data if t.name == "saccades"][0]
        a = [t for t in arc.data if t.name == "saccades"][0]
        # One segment: straight = 3 pts (p0, p1, None); arc = many sampled pts.
        assert len(s.x) == 3
        assert len(a.x) > 10

    def test_snap_moves_fixations_to_word_top_centre(self):
        words, fix = self._trial()
        base = make_scanpath_figure(
            words, fix, **self._kwargs(fixation_snap_to_word=False)
        )
        snapped = make_scanpath_figure(
            words, fix, **self._kwargs(fixation_snap_to_word=True)
        )
        raw = [t for t in base.data if t.mode == "markers"][0]
        snap = [t for t in snapped.data if t.mode == "markers"][0]
        assert list(raw.x) == [120.0, 320.0]  # raw gaze x (off the word centre)
        assert list(raw.y) == [75.0, 225.0]  # raw gaze y
        # Snapped to each word's top-centre: x = word centre (140/340, NOT the raw
        # 120/320), y = word top edge (50/200, NOT the raw 75/225).
        assert list(snap.x) == [140.0, 340.0]
        assert list(snap.y) == [50.0, 200.0]

    def test_arc_mode_reserves_headroom_so_apex_is_not_clipped(self):
        import numpy as np

        # A wide saccade along the top line arcs high; the view must grow upward so
        # the apex isn't clipped — while Straight mode leaves the range unchanged.
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                "word_id": [1, 2],
                "text": ["a", "b"],
                "x": [100, 900],
                "y": [50, 50],
                "width": [80, 80],
                "height": [40, 40],
            }
        )
        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                "x": [140.0, 940.0],
                "y": [70.0, 70.0],
                "duration_ms": [200.0, 200.0],
                "timestamp_ms": [0, 100],
                "order_in_trial": [1, 2],
            }
        )

        def top_and_apex(mode):
            fig = make_scanpath_figure(
                words, fix, **self._kwargs(saccade_render_mode=mode)
            )
            top = min(fig.layout.yaxis.range)  # smallest y = top edge
            sac = [t for t in fig.data if t.name == "saccades"][0]
            apex = float(np.nanmin([v for v in sac.y if v is not None]))
            return top, apex

        straight_top, _ = top_and_apex("Straight")
        arc_top, arc_apex = top_and_apex("Arc")
        assert arc_apex >= arc_top  # apex sits inside the view (not clipped)
        assert arc_top < straight_top  # Arc reserved extra headroom above

    def test_arc_mode_works_with_by_type_colouring(self):
        words, fix = self._trial()
        fig = make_scanpath_figure(
            words,
            fix,
            **self._kwargs(saccade_render_mode="Arc", saccade_color_mode="By type"),
        )
        by_type = [t for t in fig.data if t.legendgroup == "saccade_type"]
        assert by_type  # a class sub-trace exists…
        assert any(len(t.x) > 10 for t in by_type)  # …and it is arced, not straight


class TestHighlightColumn:
    def test_overlay_uses_chosen_column(self):
        words = pd.DataFrame(
            {
                "x": [0.0, 10.0, 20.0],
                "y": [0.0, 0.0, 0.0],
                "width": [10.0, 10.0, 10.0],
                "height": [10.0, 10.0, 10.0],
                "my_flag": [True, True, False],
            }
        )
        # One line with two adjacent flagged words → a single outline rectangle.
        assert len(build_critical_span_overlay(words, "my_flag")) == 1
        # The default column is absent → nothing to outline.
        assert build_critical_span_overlay(words, "is_in_aspan") == []


class TestSaccadeArrowMarkers:
    """Tests for _saccade_arrow_markers (direction-arrow geometry)."""

    def test_direction_angles_account_for_reversed_y(self):
        # (0,0)->(10,0) is rightward; (10,0)->(10,10) goes to larger data y,
        # which is DOWN on the reversed y-axis. marker.angle is clockwise from
        # up, so rightward=90 and screen-down=180.
        df = pd.DataFrame(
            {"x": [0, 10, 10], "y": [0, 0, 10], "timestamp_ms": [0, 1, 2]}
        )
        mid_x, mid_y, angles = _saccade_arrow_markers(df, "x", "y")
        assert mid_x == [5.0, 10.0]
        assert mid_y == [0.0, 5.0]
        assert angles == pytest.approx([90.0, 180.0])

    def test_single_fixation_yields_no_arrows(self):
        df = pd.DataFrame({"x": [1], "y": [2], "timestamp_ms": [0]})
        assert _saccade_arrow_markers(df, "x", "y") == ([], [], [])

    def test_zero_length_saccade_skipped(self):
        # Identical consecutive points produce no arrow (no direction).
        df = pd.DataFrame({"x": [5, 5], "y": [5, 5], "timestamp_ms": [0, 1]})
        assert _saccade_arrow_markers(df, "x", "y") == ([], [], [])

    def test_micro_saccade_below_threshold_skipped(self):
        # A large saccade then a sub-pixel refixation: only the large one gets an
        # arrow (the tiny one's heading would be noise).
        df = pd.DataFrame(
            {"x": [0, 100, 100.2], "y": [0, 0, 0], "timestamp_ms": [0, 1, 2]}
        )
        _mid_x, _mid_y, angles = _saccade_arrow_markers(df, "x", "y")
        assert angles == pytest.approx([90.0])


class TestBuildWordBoxes:
    """Tests for build_word_boxes function."""

    def test_build_word_boxes(self, normalized_words_df):
        shapes = build_word_boxes(normalized_words_df)
        assert len(shapes) == len(normalized_words_df)
        assert all(shape["type"] == "rect" for shape in shapes)
        assert all("x0" in shape for shape in shapes)
        assert all("y0" in shape for shape in shapes)

    def test_build_word_boxes_empty(self):
        empty_df = pd.DataFrame()
        shapes = build_word_boxes(empty_df)
        assert shapes == []


class TestMakeScanpathFigure:
    """Tests for make_scanpath_figure function."""

    def test_fit_to_monitor_spans_full_canvas(
        self, normalized_words_df, normalized_fixations_df
    ):
        """fit_to_monitor frames the whole virtual monitor; default crops to data."""
        common = dict(
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        cropped = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **common
        )
        full = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            fit_to_monitor=True,
            **common,
        )
        # Full-monitor view spans exactly the canvas (y inverted), so the scanpath
        # sits at its true on-screen position with the rest of the monitor around it.
        assert list(full.layout.xaxis.range) == [0, 800]
        assert list(full.layout.yaxis.range) == [600, 0]
        # The default view crops tightly to the data extent — strictly inside.
        assert cropped.layout.xaxis.range[0] > 0
        assert cropped.layout.xaxis.range[1] < 800

    def test_make_scanpath_figure_basic(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)
        # Figure now shrinks to the data's aspect ratio (see _fit_display_size);
        # dimensions are capped at the requested canvas, not pinned to it.
        assert 0 < fig.layout.width <= 800
        assert 0 < fig.layout.height <= 600

    def test_make_scanpath_figure_with_heatmap(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=False,
            show_heatmap=True,
            color_by="duration_ms",
            heatmap_metric="duration_ms",
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=True,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)

    def test_make_scanpath_figure_interpolated_heatmap(
        self, normalized_words_df, normalized_fixations_df
    ):
        """heatmap_style='Interpolated' adds a smooth go.Heatmap density trace."""
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=False,
            show_heatmap=True,
            heatmap_style="Interpolated",
            color_by="duration_ms",
            heatmap_metric="duration_ms",
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert any(isinstance(t, go.Heatmap) for t in fig.data)

    def test_make_scanpath_figure_saccade_arrows(
        self, normalized_words_df, normalized_fixations_df
    ):
        """show_saccade_arrows adds an arrow-marker trace with one angle/saccade."""
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=True,
            show_saccade_arrows=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        arrow_traces = [
            t
            for t in fig.data
            if isinstance(t, go.Scatter)
            and getattr(t.marker, "symbol", None) == "arrow"
        ]
        assert len(arrow_traces) == 1
        # Three fixations -> two saccade segments -> two arrowheads.
        assert len(arrow_traces[0].x) == 2

    def test_make_scanpath_figure_empty_fixations(self, normalized_words_df):
        empty_fixations = pd.DataFrame()
        fig = make_scanpath_figure(
            normalized_words_df,
            empty_fixations,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)

    def test_make_scanpath_figure_with_raw_gaze(
        self, normalized_words_df, normalized_fixations_df
    ):
        raw_gaze = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "x": [120, 125],
                "y": [70, 75],
                "timestamp_ms": [0, 1],
            }
        )
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
            raw_gaze=raw_gaze,
            show_raw_gaze=True,
        )
        assert isinstance(fig, go.Figure)

    def test_make_scanpath_figure_non_spatial_axes(self, normalized_fixations_df):
        # Test with non-spatial axes (e.g., timestamp vs duration)
        empty_words = pd.DataFrame()
        fig = make_scanpath_figure(
            empty_words,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="timestamp_ms",
            y_field="duration_ms",
            show_words=False,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=False,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)


class TestMakeScanpathAnimation:
    """Tests for make_scanpath_animation function."""

    def test_make_scanpath_animation_basic(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=1.0,
            show_words=True,
            show_word_labels=True,
            show_saccades=True,
            show_order=True,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
        )
        assert isinstance(fig, go.Figure)
        assert hasattr(fig, "frames")
        assert 1 <= len(fig.frames) <= _ANIM_MAX_FRAMES + 1

    def test_make_scanpath_animation_background_image_layer(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        # The stimulus-image background (MultiplEYE) must show in the animated
        # replay too — placed at its centered origin, below the traces, and
        # persisting across frames (a layout image, not per-frame data).
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=1920,
            canvas_height=1080,
            base_font_size=12,
            font_family="Arial",
            background_image=str(p),
            background_image_size=(1310, 991),
            background_image_origin=(305.0, 44.5),
        )
        assert len(fig.layout.images) == 1
        im = fig.layout.images[0]
        assert (im.x, im.y, im.sizex, im.sizey) == (305.0, 44.5, 1310, 991)
        assert im.layer == "below" and im.yanchor == "top"
        assert str(im.source).startswith("data:image/png;base64,")
        assert 1 <= len(fig.frames) <= _ANIM_MAX_FRAMES + 1

    def test_make_scanpath_animation_background_image_dual_overlay(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        # Compare + Animate is an overlay on the same axes, so the stimulus image
        # must show there too (a second scanpath via fixations_b must not drop it).
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            fixations_b=normalized_fixations_df,
            words_b=normalized_words_df,
            canvas_width=1920,
            canvas_height=1080,
            base_font_size=12,
            font_family="Arial",
            background_image=str(p),
            background_image_size=(1310, 991),
            background_image_origin=(305.0, 44.5),
        )
        assert len(fig.layout.images) == 1
        im = fig.layout.images[0]
        assert (im.x, im.y, im.sizex, im.sizey) == (305.0, 44.5, 1310, 991)
        assert im.layer == "below"

    def test_make_scanpath_animation_empty_fixations(self, normalized_words_df):
        empty_fixations = pd.DataFrame()
        fig = make_scanpath_animation(
            normalized_words_df,
            empty_fixations,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert isinstance(fig, go.Figure)

    def test_make_scanpath_animation_playback_speed(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=2.0,
        )
        assert isinstance(fig, go.Figure)

    def test_animation_colors_by_numeric_metric(
        self, normalized_words_df, normalized_fixations_df
    ):
        # The replay must honour the sidebar's color-by metric + colorscale like
        # the static figure does, with cmin/cmax pinned to the WHOLE trial so
        # colours don't renormalise as the trail grows frame by frame.
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            color_by="duration_ms",
            fixation_colorscale="Viridis",
        )
        # 0 = word labels, 1 = trail, 2 = order numbers, 3 = saccades, 4 = current
        trail = fig.data[1]
        assert trail.marker.colorscale is not None
        assert trail.marker.cmin == 180.0 and trail.marker.cmax == 250.0
        # Colours are stated at FULL length (one per fixation) in every frame; the
        # base reveals only the first fixation's POSITION (the rest are masked to
        # None x/y), but the colour array stays whole so cmin/cmax never
        # renormalise to the partial trail as it grows.
        assert list(trail.marker.color) == [200, 250, 180]
        assert list(trail.x) == [125, None, None]
        last = fig.frames[-1].data[0]
        assert list(last.marker.color) == [200, 250, 180]
        assert last.marker.cmin == 180.0 and last.marker.cmax == 250.0
        assert last.marker.colorscale is not None

    def test_animation_explicit_color_range_pins_cmin_cmax(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            color_by="duration_ms",
            fixation_color_range=(0.0, 500.0),
        )
        trail = fig.data[1]
        assert trail.marker.cmin == 0.0 and trail.marker.cmax == 500.0

    def test_animation_categorical_color_gets_legend(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            color_by="saccade_type",
        )
        trail = fig.data[1]
        # Per-fixation colours stated at full length (masked positions aren't
        # drawn); the base reveals only the first fixation's position.
        assert len(trail.marker.color) == 3
        assert list(trail.x) == [125, None, None]
        assert len(fig.frames[-1].data[0].marker.color) == 3
        legend_names = {t.name for t in fig.data if t.showlegend}
        assert legend_names == {"saccade_type: RIGHT", "saccade_type: LEFT"}

    def test_animation_default_keeps_flat_color(
        self, normalized_words_df, normalized_fixations_df
    ):
        from scanpath_studio.constants import COMPARISON_PALETTE

        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert fig.data[1].marker.color == COMPARISON_PALETTE[0]

    def test_order_numbers_never_glide_in_from_corner(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Regression: order numbers used to ride the growing markers+text trail,
        # so each new <text> node flashed at the (0,0) corner before snapping to
        # its fixation. They now live in their own FULL-LENGTH text trace whose
        # `text` strings are CONSTANT across every frame; a number is revealed by
        # un-masking its x/y from None straight to its fixation's true coordinate
        # (never an intermediate / origin position), so a label only ever turns
        # on in place — it never moves. (Full length + position-only change is
        # also what lets Play animate with redraw=False; see
        # _animation_play_buttons.)
        n = len(normalized_fixations_df)
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            show_order=True,
        )
        # 0 = word labels, 1 = trail (markers, hover only), 2 = order numbers.
        order = fig.data[2]
        assert order.mode == "text"
        assert "text" not in (fig.data[1].mode or "")  # trail draws no numbers
        const_text = tuple(str(j + 1) for j in range(n))
        # Every number is present in the trace from the first frame on; the text
        # never changes — only positions un-mask.
        assert tuple(str(v) for v in order.text) == const_text
        assert len(order.x) == n
        # True fixation coordinates: the last frame reveals all of them.
        true_x = tuple(fig.frames[-1].data[1].x)
        true_y = tuple(fig.frames[-1].data[1].y)
        assert None not in true_x  # fully revealed at the end

        prev_shown = 0
        for frame in fig.frames:
            # The order trace is the second per-spec entry in each frame.
            order_f = frame.data[1]
            assert tuple(str(v) for v in order_f.text) == const_text  # text fixed
            xs, ys = list(order_f.x), list(order_f.y)
            shown = sum(1 for x in xs if x is not None)
            # Revealed positions are a contiguous prefix sitting at the TRUE
            # fixation coordinates; the unreached tail is None (not the origin or
            # any intermediate) — labels turn on in place, they never move.
            assert tuple(xs[:shown]) == true_x[:shown]
            assert tuple(ys[:shown]) == true_y[:shown]
            assert all(x is None for x in xs[shown:])
            assert shown >= prev_shown  # monotonic reveal, never un-reveals
            prev_shown = shown
        assert prev_shown == n  # last frame shows the whole reading

    def test_slider_uniform_time_grid_bounded_and_labelled(self, normalized_words_df):
        # VIZ-11: frames sit on a uniform time grid, so the slider scrubs linearly
        # and every per-step label reads "elapsed / total s". A long reading
        # coarsens the grid instead of emitting one frame per fixation, so the step
        # count stays bounded (the GIF/MP4 export can't balloon). The per-step tick
        # ruler + labels are hidden — the single readout is the one time display.
        n = 60
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1"] * n,
                "trial_id": ["t1"] * n,
                "x": [100 + (i % 3) * 50 for i in range(n)],
                "y": [50] * n,
                "duration_ms": [100] * n,
                "timestamp_ms": list(range(0, n * 100, 100)),
                "word_id": [1] * n,
                "order_in_trial": list(range(1, n + 1)),
                "pass_index": [1] * n,
            }
        )
        fig = make_scanpath_animation(
            normalized_words_df,
            fixations,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
        )
        slider = fig.layout.sliders[0]
        assert 1 <= len(slider.steps) <= _ANIM_MAX_FRAMES + 1
        # "elapsed / total s" label on every step (meaningful for any reader count).
        assert all(" / " in s.label and s.label.endswith("s") for s in slider.steps)
        assert slider.currentvalue.visible
        # Tick ruler hidden, and per-step labels drawn transparent.
        assert slider.ticklen == 0
        assert slider.minorticklen == 0
        assert "0)" in slider.font.color or "rgba" in str(slider.font.color)

        # A very long reading coarsens the grid rather than exceeding the cap.
        long_n = 800
        long_fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * long_n,
                "trial_id": ["t1"] * long_n,
                "x": [100 + (i % 3) * 50 for i in range(long_n)],
                "y": [50] * long_n,
                "duration_ms": [100] * long_n,
                "timestamp_ms": list(range(0, long_n * 100, 100)),
                "word_id": [1] * long_n,
                "order_in_trial": list(range(1, long_n + 1)),
                "pass_index": [1] * long_n,
            }
        )
        long_fig = make_scanpath_animation(
            normalized_words_df,
            long_fix,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert len(long_fig.frames) <= _ANIM_MAX_FRAMES + 1 < long_n


class TestAnimationAutoplay:
    """VIZ-10: autoplay-on-load marker + the client-side kickoff script."""

    def _anim(self, words, fixations, **kw):
        return make_scanpath_animation(
            words,
            fixations,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=4.0,
            **kw,
        )

    def test_autoplay_on_by_default_stamps_frame_duration(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = self._anim(normalized_words_df, normalized_fixations_df)
        # The marker rides on layout.meta so every HTML embedder honors it.
        assert fig.layout.meta["scanpath_autoplay"] is True
        dur = animation_autoplay_frame_duration(fig)
        assert isinstance(dur, int) and dur >= _ANIM_MIN_FRAME_MS
        # The autoplay duration MUST equal the ▶ Play button's frame duration, so
        # the auto-started replay runs at the configured speed, not Plotly's
        # default. (Both come from _anim_timeline.)
        play = fig.layout.updatemenus[0].buttons[0]
        assert play.label.startswith("▶")
        assert play.args[1]["frame"]["duration"] == dur

    def test_autoplay_off_suppresses_kickoff(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = self._anim(normalized_words_df, normalized_fixations_df, autoplay=False)
        assert fig.layout.meta["scanpath_autoplay"] is False
        assert animation_autoplay_frame_duration(fig) is None

    def test_no_frames_never_autoplays(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Empty fixations → no frames → nothing to auto-start even with autoplay on.
        empty = normalized_fixations_df.iloc[0:0]
        fig = self._anim(normalized_words_df, empty, autoplay=True)
        assert fig.layout.meta["scanpath_autoplay"] is False
        assert animation_autoplay_frame_duration(fig) is None

    def test_static_figure_has_no_autoplay(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df, normalized_fixations_df, **_scanpath_kwargs()
        )
        assert animation_autoplay_frame_duration(fig) is None

    def test_post_script_is_plotly_animate_at_the_given_duration(self):
        script = animation_autoplay_post_script(123)
        # {plot_id} stays literal for Plotly to substitute at write time.
        assert "{plot_id}" in script
        assert "Plotly.animate" in script
        assert "123" in script
        assert "redraw:false" in script

    def test_post_script_reads_real_frame_location_and_starts_from_first(self):
        # VIZ-10 regression: Plotly stores frames on gd._transitionData._frames,
        # NOT gd.frames (which is undefined) — a guard that checks gd.frames alone
        # always bails, so autoplay never fires. The kickoff must poll the real
        # location and start a clean 0->end run (fromcurrent:false).
        script = animation_autoplay_post_script(100)
        assert "_transitionData" in script
        assert "_frames" in script
        assert "fromcurrent:false" in script
        # It polls (loops) rather than firing a single fixed-delay shot.
        assert "setTimeout" in script

    def test_post_script_floors_tiny_durations(self):
        # A sub-minimum duration is clamped so the kickoff can't request a 0ms grid.
        assert str(_ANIM_MIN_FRAME_MS) in animation_autoplay_post_script(0)


class TestStimulusImageOpacity:
    """VIZ-4: the stimulus-image layer honours an opacity (dataset + uploads)."""

    def test_static_figure_applies_opacity(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                background_image=str(p),
                background_image_size=(1310, 991),
                background_image_opacity=0.35,
            ),
        )
        assert len(fig.layout.images) == 1
        assert fig.layout.images[0].opacity == 0.35

    def test_static_figure_defaults_to_opaque(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                background_image=str(p), background_image_size=(1310, 991)
            ),
        )
        assert fig.layout.images[0].opacity == 1.0

    def test_animation_applies_opacity(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=1920,
            canvas_height=1080,
            base_font_size=12,
            font_family="Arial",
            background_image=str(p),
            background_image_size=(1310, 991),
            background_image_opacity=0.5,
        )
        assert fig.layout.images[0].opacity == 0.5

    def test_uploaded_data_uri_is_drawn(
        self, normalized_words_df, normalized_fixations_df
    ):
        # An uploaded image reaches the builder as a `data:` URI (controls encodes
        # it); it must be accepted straight through and stretched to the size given.
        import base64

        data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                background_image=data_uri,
                background_image_size=(1920, 1080),
                background_image_opacity=0.8,
            ),
        )
        assert str(fig.layout.images[0].source).startswith("data:image/png")
        assert (fig.layout.images[0].sizex, fig.layout.images[0].opacity) == (1920, 0.8)


class TestSplitScanpathLayers:
    """VIZ-5: split the figure into one registered figure per layer."""

    def _rich_figure(self, tmp_path, words, fixations):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        return make_scanpath_figure(
            words,
            fixations,
            **_scanpath_kwargs(
                show_word_labels=True,
                show_order=True,
                show_saccade_arrows=True,
                show_heatmap=True,
                heatmap_style="Word boxes",
                heatmap_metric="duration_ms",
                background_image=str(p),
                background_image_size=(1310, 991),
            ),
        )

    def test_partition_is_complete_and_disjoint(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        fig = self._rich_figure(tmp_path, normalized_words_df, normalized_fixations_df)
        layers = split_scanpath_layers(fig)
        # Every trace and shape lands in exactly one layer (no drops, no dupes).
        assert sum(len(g.data) for g in layers.values()) == len(fig.data)
        assert sum(len(g.layout.shapes or ()) for g in layers.values()) == len(
            fig.layout.shapes or ()
        )
        # The stimulus image lives on exactly one layer.
        total_imgs = sum(len(g.layout.images or ()) for g in layers.values())
        assert total_imgs == len(fig.layout.images)

    def test_layers_register_identically(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        # Same axis ranges + size across every layer ⇒ they stack in perfect
        # registration in a vector editor.
        fig = self._rich_figure(tmp_path, normalized_words_df, normalized_fixations_df)
        layers = split_scanpath_layers(fig)
        fingerprints = {
            (
                tuple(g.layout.xaxis.range),
                tuple(g.layout.yaxis.range),
                g.layout.width,
                g.layout.height,
            )
            for g in layers.values()
        }
        assert len(fingerprints) == 1

    def test_layers_have_transparent_background(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        fig = self._rich_figure(tmp_path, normalized_words_df, normalized_fixations_df)
        for g in split_scanpath_layers(fig).values():
            assert str(g.layout.paper_bgcolor) == "rgba(0,0,0,0)"
            assert str(g.layout.plot_bgcolor) == "rgba(0,0,0,0)"

    def test_elements_land_on_the_right_layer(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        fig = self._rich_figure(tmp_path, normalized_words_df, normalized_fixations_df)
        layers = split_scanpath_layers(fig)
        # Word boxes and heatmap rects are both fill rects but split apart.
        assert layers["word_boxes"].layout.shapes  # AOI rectangles
        assert layers["heatmap"].layout.shapes  # coloured heatmap rects
        assert all(
            "heatmap" not in (sh.name or "")
            for sh in layers["word_boxes"].layout.shapes
        )
        # Labels are the word-text trace; saccades carry the line + arrow traces.
        assert [tr.name for tr in layers["labels"].data] == ["words"]
        assert "saccades" in {tr.name for tr in layers["saccades"].data}
        assert len(layers["stimulus_image"].layout.images) == 1
        # Fixations layer holds the markers, not saccades/labels.
        assert any("Fixation" in (tr.name or "") for tr in layers["fixations"].data)

    def test_no_heatmap_layer_when_off(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_heatmap=False),
        )
        assert "heatmap" not in split_scanpath_layers(fig)


class TestDualScanpathAnimation:
    """Tests for the dual path of make_scanpath_animation (the fixations_b arg)."""

    @staticmethod
    def _second_fixations():
        # Onsets are recorded timestamps rebased to t=0: [0, 300]. Paired with
        # scanpath A's [0, 200, 450] the merged onset set is {0, 200, 300, 450}
        # → 4 frames.
        return pd.DataFrame(
            {
                "participant_id": ["p2", "p2"],
                "trial_id": ["t1", "t1"],
                "x": [130, 230],
                "y": [80, 80],
                "duration_ms": [300, 100],
                "timestamp_ms": [0, 300],
                "order_in_trial": [1, 2],
            }
        )

    def test_dual_animation_basic(self, normalized_words_df, normalized_fixations_df):
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=1.0,
            fixations_b=self._second_fixations(),
        )
        assert isinstance(fig, go.Figure)
        assert hasattr(fig, "frames")
        # Frames sit on a uniform time grid (VIZ-11), bounded regardless of the
        # onset pattern across the two overlaid scanpaths.
        assert 1 <= len(fig.frames) <= _ANIM_MAX_FRAMES + 1
        # A/B legend is off by default (CMP-2) — the flat colours already tell the
        # two readers apart.
        assert [t.name for t in fig.data if t.showlegend] == []

    def test_dual_animation_legend_when_enabled(
        self, normalized_words_df, normalized_fixations_df
    ):
        # With show_legend=True both trails appear in the legend (CMP-2).
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=self._second_fixations(),
            show_legend=True,
        )
        assert len([t.name for t in fig.data if t.showlegend]) == 2

    def test_dual_animation_ignores_color_by(
        self, normalized_words_df, normalized_fixations_df
    ):
        # In the overlay the flat A/B colours ARE the scanpath identity — a
        # metric colorscale would make the two readings indistinguishable.
        from scanpath_studio.constants import COMPARISON_PALETTE

        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            color_by="duration_ms",
            fixations_b=self._second_fixations(),
        )
        trail_colors = [
            t.marker.color
            for t in fig.data
            if t.marker is not None and t.marker.color in COMPARISON_PALETTE
        ]
        assert set(trail_colors) >= set(COMPARISON_PALETTE)

    def test_dual_animation_uses_real_timestamps(self, normalized_words_df):
        # The shared clock must come from recorded timestamp_ms (rebased), NOT
        # cumulative durations — otherwise readings with saccade/blink gaps
        # desync. Here fixation 2 starts at t=1000ms but lasts only 100ms, so a
        # duration-based clock would place its onset at 100ms. The elapsed-time
        # slider label proves which clock is used.
        fix_a = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "x": [120, 220],
                "y": [70, 70],
                "duration_ms": [100, 100],
                "timestamp_ms": [0, 1000],
                "order_in_trial": [1, 2],
            }
        )
        fig = make_scanpath_animation(
            normalized_words_df,
            fix_a,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=fix_a.iloc[:1].copy(),  # single fixation at t=0
        )
        labels = [s.label for s in fig.layout.sliders[0].steps]
        # Uniform time grid (VIZ-11): every label reads "elapsed / total s". The
        # *total* proves the clock — real timestamps span ~1.1s (fixation 2 onset
        # at 1.0s + 0.1s dwell); a duration-based clock would collapse it to 0.2s.
        total_s = float(labels[0].split("/")[1].strip().rstrip("s"))
        assert total_s >= 1.0, labels
        assert labels[0].startswith("0.0 / "), labels
        assert labels[-1].startswith(f"{total_s:.1f} / "), labels

    def test_dual_animation_identical_inputs(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Identical scanpaths animate on the same uniform time grid (VIZ-11).
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=normalized_fixations_df,
        )
        assert 1 <= len(fig.frames) <= _ANIM_MAX_FRAMES + 1

    def test_dual_animation_one_empty_falls_back(
        self, normalized_words_df, normalized_fixations_df
    ):
        # An empty second scanpath degrades to the single replay (no legend).
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=pd.DataFrame(),
        )
        assert isinstance(fig, go.Figure)
        assert 1 <= len(fig.frames) <= _ANIM_MAX_FRAMES + 1
        assert [t for t in fig.data if t.showlegend] == []

    def test_dual_animation_both_empty(self, normalized_words_df):
        fig = make_scanpath_animation(
            normalized_words_df,
            pd.DataFrame(),
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=pd.DataFrame(),
        )
        assert isinstance(fig, go.Figure)
        assert len(fig.frames) == 0


class TestAnimationFrameGrid:
    """VIZ-11 follow-up: the frame grid is the user's tradeoff to make, and the
    cap coarsening the requested step must be *reported*, not silent."""

    def _fix(self, n=200, gap_ms=100.0):
        import pandas as pd

        return pd.DataFrame(
            {
                "participant_id": ["p1"] * n,
                "trial_id": ["t1"] * n,
                "x": [100.0 + i for i in range(n)],
                "y": [100.0] * n,
                "duration_ms": [200.0] * n,
                "timestamp_ms": [i * gap_ms for i in range(n)],
                "order_in_trial": list(range(1, n + 1)),
            }
        )

    def test_a_finer_step_emits_more_frames(self):
        from scanpath_studio.plots import animation_timeline_summary

        # A cap high enough not to bind, so this isolates the step alone.
        fine = animation_timeline_summary(
            [self._fix()], 1.0, grid_step_ms=50, max_frames=10_000
        )
        coarse = animation_timeline_summary(
            [self._fix()], 1.0, grid_step_ms=400, max_frames=10_000
        )
        assert fine["n_frames"] > coarse["n_frames"]
        assert fine["step_ms"] == pytest.approx(50)
        assert coarse["step_ms"] == pytest.approx(400)
        assert not fine["coarsened"] and not coarse["coarsened"]

    def test_the_cap_coarsens_the_step_and_says_so(self):
        from scanpath_studio.plots import animation_timeline_summary

        summary = animation_timeline_summary(
            [self._fix()], 1.0, grid_step_ms=10, max_frames=25
        )
        assert summary["n_frames"] <= 26  # the exact end lands one extra frame
        assert summary["coarsened"] is True
        assert summary["requested_step_ms"] == pytest.approx(10)
        assert summary["step_ms"] > 10

    def test_the_defaults_reproduce_the_previous_behaviour(self):
        from scanpath_studio.plots import (
            _ANIM_GRID_STEP_MS,
            _ANIM_MAX_FRAMES,
            animation_timeline_summary,
        )

        fixations = self._fix()
        explicit = animation_timeline_summary(
            [fixations],
            1.0,
            grid_step_ms=_ANIM_GRID_STEP_MS,
            max_frames=_ANIM_MAX_FRAMES,
        )
        implicit = animation_timeline_summary([fixations], 1.0)
        assert implicit == explicit

    def test_the_figure_honours_the_grid(self, normalized_words_df):
        from scanpath_studio.plots import make_scanpath_animation

        fixations = self._fix()
        kwargs = dict(
            canvas_width=1920,
            canvas_height=1080,
            base_font_size=14,
            font_family="monospace",
        )
        fine = make_scanpath_animation(
            normalized_words_df, fixations, anim_grid_step_ms=50, **kwargs
        )
        capped = make_scanpath_animation(
            normalized_words_df,
            fixations,
            anim_grid_step_ms=50,
            anim_max_frames=20,
            **kwargs,
        )
        assert len(fine.frames) > len(capped.frames)
        assert len(capped.frames) <= 21


class TestAnimationPlaybackTiming:
    """The side panel must quote the *actual* animation runtime."""

    def test_playback_ms_matches_play_button(
        self, normalized_words_df, normalized_fixations_df
    ):
        # animation_playback_ms must equal what Play actually runs: Play advances
        # all frames at a single frame-duration, so runtime == n_frames * that.
        speed = 2.0
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=speed,
        )
        play_btn = fig.layout.updatemenus[0].buttons[0]
        frame_ms = play_btn.args[1]["frame"]["duration"]
        expected = len(fig.frames) * frame_ms
        _span, playback_ms = animation_playback_ms([normalized_fixations_df], speed)
        assert playback_ms == expected

    def test_playback_ms_empty(self):
        assert animation_playback_ms([], 1.0) == (0.0, 0.0)

    def test_frame_floor_clamps_fast_playback(self, normalized_words_df):
        # The Play frame duration floors at _ANIM_MIN_FRAME_MS so frames stay
        # renderable (browsers cap ~60fps). Under the uniform time grid (VIZ-11)
        # the per-frame duration is step / playback_speed, so a very high speed
        # would drive it below the floor — the clamp keeps it at the floor.
        from scanpath_studio.plots import _ANIM_MIN_FRAME_MS

        fix = pd.DataFrame(
            {
                "participant_id": ["p1"] * 10,
                "trial_id": ["t1"] * 10,
                "x": [100 + i * 10 for i in range(10)],
                "y": [50] * 10,
                "duration_ms": [100] * 10,
                "timestamp_ms": list(range(0, 1000, 100)),
                "order_in_trial": list(range(1, 11)),
            }
        )
        fig = make_scanpath_animation(
            normalized_words_df,
            fix,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=1000.0,  # step / speed << floor
        )
        play_ms = fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"]
        assert play_ms == _ANIM_MIN_FRAME_MS

    def test_fake_index_timestamps_fall_back_to_durations(self, normalized_words_df):
        # data.normalize_fixations synthesizes timestamp_ms = 0,1,2,... when the
        # source has no timestamp column. Those row indices must NOT be read as
        # milliseconds; the clock falls back to fixation durations laid out
        # back-to-back, so reading time ~ sum(durations), not a couple of ms.
        fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t1", "t1"],
                "x": [120, 220, 320],
                "y": [70, 70, 70],
                "duration_ms": [200, 250, 180],
                "timestamp_ms": [0, 1, 2],  # row-index sentinel, not real ms
                "order_in_trial": [1, 2, 3],
            }
        )
        span_ms, _playback = animation_playback_ms([fix], 1.0)
        assert span_ms == 630  # 200+250+180, NOT ~2 ms

    def test_single_mode_color_is_canonical_from_b_slot(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Degenerate direct call: only the second slot is populated. The lone
        # trail must still be the canonical single-replay blue, never the red
        # "B" colour.
        from scanpath_studio.constants import COMPARISON_PALETTE

        fig = make_scanpath_animation(
            normalized_words_df,
            pd.DataFrame(),
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=normalized_fixations_df,
        )
        marker_colors = [
            t.marker.color
            for t in fig.data
            if t.marker is not None and isinstance(t.marker.color, str)
        ]
        assert COMPARISON_PALETTE[0] in marker_colors
        assert COMPARISON_PALETTE[1] not in marker_colors

    def test_animation_transitions_are_zero(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Zero transition = labels/markers appear on their fixation instead of
        # gliding in from the corner, and the runtime stays exact.
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            show_order=True,
        )
        play_btn = fig.layout.updatemenus[0].buttons[0]
        assert play_btn.args[1]["transition"]["duration"] == 0
        assert fig.layout.sliders[0].transition.duration == 0


class TestMakeComparisonFigure:
    """Tests for make_comparison_figure function."""

    def test_make_comparison_figure(self, normalized_words_df, normalized_fixations_df):
        # Create data for two trials
        words_multi = pd.concat(
            [
                normalized_words_df.assign(participant_id="p1", trial_id="t1"),
                normalized_words_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fixations_multi = pd.concat(
            [
                normalized_fixations_df.assign(participant_id="p1", trial_id="t1"),
                normalized_fixations_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )

        fig = make_comparison_figure(
            words_multi,
            fixations_multi,
            trial_a=("p1", "t1"),
            trial_b=("p2", "t1"),
            canvas_width=800,
            canvas_height=600,
            font_family="Arial",
            base_font_size=12,
        )
        assert isinstance(fig, go.Figure)
        # Each trial contributes a saccade line trace + a fixation-marker trace.
        marker_traces = [t for t in fig.data if t.mode and "markers" in t.mode]
        assert len(marker_traces) == 2
        # Default per-scanpath colours come from the comparison palette.
        from scanpath_studio.constants import COMPARISON_PALETTE

        assert marker_traces[0].marker.color == COMPARISON_PALETTE[0]
        assert marker_traces[1].marker.color == COMPARISON_PALETTE[1]

    def test_comparison_per_scanpath_style(
        self, normalized_words_df, normalized_fixations_df
    ):
        """Per-scanpath style overrides (colour, hollow, dashed saccades) apply."""
        words_multi = pd.concat(
            [
                normalized_words_df.assign(participant_id="p1", trial_id="t1"),
                normalized_words_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fixations_multi = pd.concat(
            [
                normalized_fixations_df.assign(participant_id="p1", trial_id="t1"),
                normalized_fixations_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fig = make_comparison_figure(
            words_multi,
            fixations_multi,
            trial_a=("p1", "t1"),
            trial_b=("p2", "t1"),
            canvas_width=800,
            canvas_height=600,
            font_family="Arial",
            base_font_size=12,
            style_a={"fix_color": "#123456", "hollow": True},
            style_b={"saccade_color": "#abcdef", "saccade_style": "dash"},
        )
        marker_traces = [t for t in fig.data if t.mode and "markers" in t.mode]
        # Scanpath 1 is hollow: transparent fill, coloured outline.
        assert marker_traces[0].marker.color == "rgba(0,0,0,0)"
        assert marker_traces[0].marker.line.color == "#123456"
        # Scanpath 2 saccades are dashed in the requested colour.
        sac_traces = [t for t in fig.data if t.mode == "lines"]
        dashed = [t for t in sac_traces if t.line.dash == "dash"]
        assert dashed and dashed[0].line.color == "#abcdef"

    def test_comparison_per_scanpath_opacity(
        self, normalized_words_df, normalized_fixations_df
    ):
        """VIZ-6: a per-scanpath opacity < 1.0 sets that marker's alpha."""
        words_multi = pd.concat(
            [
                normalized_words_df.assign(participant_id="p1", trial_id="t1"),
                normalized_words_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fixations_multi = pd.concat(
            [
                normalized_fixations_df.assign(participant_id="p1", trial_id="t1"),
                normalized_fixations_df.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fig = make_comparison_figure(
            words_multi,
            fixations_multi,
            trial_a=("p1", "t1"),
            trial_b=("p2", "t1"),
            canvas_width=800,
            canvas_height=600,
            font_family="Arial",
            base_font_size=12,
            style_a={"opacity": 0.3},
            style_b={"opacity": 1.0},
        )
        marker_traces = [t for t in fig.data if t.mode and "markers" in t.mode]
        assert marker_traces[0].marker.opacity == 0.3
        # The opacity is always set explicitly, so a fully-opaque scanpath is 1.0
        # (overriding Plotly's ~0.7 variable-size-marker default).
        assert marker_traces[1].marker.opacity == 1.0


class TestPlotEnhancements:
    """Background color, out-of-text highlight, and color-by-line options."""

    def _figure(self, words, fixations, **overrides):
        kwargs = dict(
            canvas_width=500,
            canvas_height=300,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        kwargs.update(overrides)
        return make_scanpath_figure(words, fixations, **kwargs)

    def test_background_color_applied(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, background_color="#bdbdbd"
        )
        assert fig.layout.plot_bgcolor == "#bdbdbd"
        assert fig.layout.paper_bgcolor == "#bdbdbd"

    def test_background_color_default_is_none(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        # Default leaves the template's background untouched.
        fig = self._figure(synthetic_words_df, synthetic_fixations_df)
        assert fig.layout.plot_bgcolor is None

    def test_out_of_bounds_overlay_trace(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        # The synthetic trial has exactly one out-of-bounds fixation (PRE-2).
        fig = self._figure(
            synthetic_words_df,
            synthetic_fixations_df,
            fixation_flags={
                "oob": {"mode": "Highlight", "symbol": "x", "color": "#d62728"}
            },
        )
        oob = [t for t in fig.data if t.name == "Out of bounds"]
        assert len(oob) == 1
        assert len(oob[0].x) == 1  # one off-text fixation

    def test_out_of_bounds_discard_drops_fixation(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        # Discarding out-of-bounds fixations removes them from the marker trace
        # (viz-only) without adding a highlight overlay.
        base = self._figure(synthetic_words_df, synthetic_fixations_df)
        n_base = len([t for t in base.data if t.name == "Fixations"][0].x)
        fig = self._figure(
            synthetic_words_df,
            synthetic_fixations_df,
            fixation_flags={"oob": {"mode": "Discard"}},
        )
        n_kept = len([t for t in fig.data if t.name == "Fixations"][0].x)
        assert n_kept == n_base - 1
        assert not any(t.name == "Out of bounds" for t in fig.data)

    def test_fixation_flags_absent_by_default(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        fig = self._figure(synthetic_words_df, synthetic_fixations_df)
        assert not any(t.name in ("Out of bounds", "Short", "Long") for t in fig.data)

    def test_color_by_line_legend(self, synthetic_words_df, synthetic_fixations_df):
        # Two lines in the layout -> two "line:" legend entries.
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, color_by_line=True
        )
        line_traces = [t for t in fig.data if str(t.name).startswith("line:")]
        assert len(line_traces) == 2

    def test_hollow_fixations(self, synthetic_words_df, synthetic_fixations_df):
        # Hollow markers have a transparent fill and a visible outline.
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, hollow_fixations=True
        )
        fix = next(t for t in fig.data if t.name == "Fixations")
        assert fix.marker.color == "rgba(0,0,0,0)"
        assert float(fix.marker.line.width) >= 1.0

    def test_fixation_opacity(self, synthetic_words_df, synthetic_fixations_df):
        # VIZ-6: the opacity is set explicitly (even at the 1.0 default) so the
        # control overrides Plotly's ~0.7 default for variable-size markers — i.e.
        # "opacity at 1" really renders fully opaque.
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, fixation_opacity=0.4
        )
        fix = next(t for t in fig.data if t.name == "Fixations")
        assert fix.marker.opacity == 0.4
        default = self._figure(synthetic_words_df, synthetic_fixations_df)
        fix_default = next(t for t in default.data if t.name == "Fixations")
        assert fix_default.marker.opacity == 1.0

    def test_saccade_style_dash(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, saccade_style="dash"
        )
        sac = next(t for t in fig.data if t.name == "saccades")
        assert sac.line.dash == "dash"

    def test_text_color_applied(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df,
            synthetic_fixations_df,
            show_word_labels=True,
            text_color="#0a0b0c",
        )
        words = next(t for t in fig.data if t.name == "words")
        # No highlight column active -> a single base colour for all words.
        assert words.textfont.color == "#0a0b0c"


class TestTrueToScaleText:
    """Word-label text is sized true-to-scale from the box geometry.

    The reading text must track the word boxes (so it always fills the real
    line slot) instead of being a fixed screen-pixel size. See
    `plots._word_label_font_px`.
    """

    def _label_size(self, fig):
        """Pixel size of the word-label text trace in a scanpath figure."""
        trace = next(t for t in fig.data if t.name == "words")
        return float(trace.textfont.size)

    def _figure(self, words, fixations, **overrides):
        kwargs = dict(
            canvas_width=800,
            canvas_height=600,
            base_font_size=16,
            font_family="monospace",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=False,
            show_order=False,
            show_saccades=False,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#000000",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        kwargs.update(overrides)
        return make_scanpath_figure(words, fixations, **kwargs)

    # -- _word_label_font_px unit behaviour -------------------------------

    def test_autofit_uses_box_height_over_line_spacing(self, normalized_words_df):
        # 50px boxes; line_spacing 3 budgets 50/3 height. width_fit (5-char
        # words in 50px boxes) is the tighter bound here, so it wins — but the
        # result is always <= the height budget and scales linearly with `scale`.
        font = _word_label_font_px(
            normalized_words_df,
            scale=1.0,
            line_spacing=3.0,
            manual_font_px=99,
            scale_text_to_boxes=True,
        )
        assert 0 < font <= 50 / 3 + 1e-6
        # Linear in scale.
        font2 = _word_label_font_px(
            normalized_words_df,
            scale=2.0,
            line_spacing=3.0,
            manual_font_px=99,
            scale_text_to_boxes=True,
        )
        assert font2 == pytest.approx(2 * font)

    def test_autofit_shrinks_with_larger_line_spacing(self, normalized_words_df):
        # Past the point where the height budget is the binding constraint,
        # a bigger line spacing yields strictly smaller text.
        big = _word_label_font_px(
            normalized_words_df,
            scale=1.0,
            line_spacing=3.0,
            manual_font_px=0,
            scale_text_to_boxes=True,
        )
        bigger = _word_label_font_px(
            normalized_words_df,
            scale=1.0,
            line_spacing=10.0,
            manual_font_px=0,
            scale_text_to_boxes=True,
        )
        assert bigger < big
        assert bigger == pytest.approx(50 / 10)  # height budget binds

    def test_manual_mode_is_real_font_times_scale(self, normalized_words_df):
        # scale_text_to_boxes off -> manual font (monitor px) * display scale,
        # independent of line_spacing.
        font = _word_label_font_px(
            normalized_words_df,
            scale=0.5,
            line_spacing=3.0,
            manual_font_px=20,
            scale_text_to_boxes=False,
        )
        assert font == pytest.approx(10.0)

    def test_falls_back_to_manual_without_boxes(self):
        empty = pd.DataFrame()
        font = _word_label_font_px(
            empty,
            scale=0.5,
            line_spacing=3.0,
            manual_font_px=20,
            scale_text_to_boxes=True,
        )
        assert font == pytest.approx(10.0)

    def test_width_fit_recovers_per_char_advance(self, normalized_words_df):
        # 5-char words in 50px boxes -> 10px/char advance; /0.6 monospace aspect.
        wf = _width_fit_font(normalized_words_df)
        assert wf == pytest.approx(10 / 0.6 * 0.92, rel=1e-6)

    # -- integration through the figure builder ---------------------------

    def test_label_font_tracks_line_spacing(
        self, normalized_words_df, normalized_fixations_df
    ):
        small_spacing = self._figure(
            normalized_words_df, normalized_fixations_df, line_spacing=3.0
        )
        large_spacing = self._figure(
            normalized_words_df, normalized_fixations_df, line_spacing=10.0
        )
        assert self._label_size(large_spacing) < self._label_size(small_spacing)

    def test_label_font_independent_of_line_spacing_when_manual(
        self, normalized_words_df, normalized_fixations_df
    ):
        a = self._figure(
            normalized_words_df,
            normalized_fixations_df,
            scale_text_to_boxes=False,
            line_spacing=3.0,
        )
        b = self._figure(
            normalized_words_df,
            normalized_fixations_df,
            scale_text_to_boxes=False,
            line_spacing=10.0,
        )
        assert self._label_size(a) == pytest.approx(self._label_size(b))


class TestLinePitchAndScript:
    """Line-pitch budget + script-aware width cap for true-to-scale text.

    Word boxes that hug the glyph (MultiplEYE) have a height far smaller than the
    line slot, so the font is budgeted from the line *pitch*; and CJK/full-width
    corpora must not be width-capped as if their glyphs were narrow Latin.
    """

    def _two_line_boxes(self, *, height, pitch, n_chars=2, box_w=56, text="月球"):
        """Two stacked lines of word boxes with a given box height + line pitch."""
        rows = []
        for line, top in enumerate((50.0, 50.0 + pitch)):
            for w in range(2):
                rows.append(
                    {
                        "x": 100.0 + w * box_w,
                        "y": top,
                        "width": box_w,
                        "height": height,
                        "text": text,
                        "word_id": line * 2 + w,
                        "line_idx": line,
                    }
                )
        return pd.DataFrame(rows)

    def test_line_pitch_uses_line_gap_not_box_height(self):
        # Tight boxes (height 34) spaced 98.6 apart -> pitch is the line gap.
        words = self._two_line_boxes(height=34, pitch=98.6)
        assert _line_pitch(words) == pytest.approx(98.6)

    def test_line_pitch_equals_box_height_when_tiling(self, normalized_words_df):
        # OneStop-style tiling / single line -> pitch falls back to box height, so
        # existing OneStop sizing is unchanged.
        assert _line_pitch(normalized_words_df) == pytest.approx(50.0)

    def test_tight_boxes_size_from_pitch_not_height(self):
        # A glyph-tight box (34) would budget 34/3 ≈ 11px off its height; from the
        # 98.6 pitch it's 98.6/3 ≈ 33 — much closer to the real font.
        words = self._two_line_boxes(height=34, pitch=98.6)
        font = _word_label_font_px(
            words,
            scale=1.0,
            line_spacing=3.0,
            manual_font_px=0,
            scale_text_to_boxes=True,
        )
        assert font > 34 / 3 + 1  # strictly bigger than the old box-height budget

    def test_latin_advance_detects_cjk(self):
        cjk = pd.DataFrame({"text": ["月球是地球", "唯一卫星"]})
        latin = pd.DataFrame({"text": ["word", "another"]})
        assert _latin_advance(cjk) == pytest.approx(0.5)
        assert _latin_advance(latin) == pytest.approx(0.6)

    def test_width_fit_handles_mixed_cjk_and_latin(self):
        # A CJK-dominant page (so the font's Latin glyphs are half-width): a 12-glyph
        # full-width CJK word in 336px -> 28 em, beside a 10-char half-width Latin URL
        # in 140px -> also 28 em. Both recover ~28, so the line isn't sized down to
        # the narrow Latin run.
        words = pd.DataFrame(
            {
                "text": ["月球是地球唯一的天然卫星", "wikipedia."],
                "width": [336.0, 140.0],
            }
        )
        wf = _width_fit_font(words)
        assert wf == pytest.approx(28 * 0.92, rel=0.02)

    def test_width_fit_latin_only_unchanged(self, normalized_words_df):
        # No CJK -> identical to the historical (box_width / n) / 0.6 formula.
        wf = _width_fit_font(normalized_words_df)
        assert wf == pytest.approx(10 / 0.6 * 0.92, rel=1e-6)

    def test_nan_label_does_not_crash(self):
        # A missing word label (NaN) must not break sizing — with the Arrow `str`
        # dtype `.astype(str)` keeps NaN a float, so a naive char scan would raise.
        # The valid word is still measured; an all-NaN frame falls back cleanly.
        mixed = pd.DataFrame({"text": [float("nan"), "月球"], "width": [56.0, 56.0]})
        assert _latin_advance(mixed) == pytest.approx(0.5)
        assert _width_fit_font(mixed) == pytest.approx(28 * 0.92, rel=0.02)
        all_nan = pd.DataFrame({"text": [float("nan")], "width": [56.0]})
        assert _width_fit_font(all_nan) is None
        assert _latin_advance(all_nan) == pytest.approx(0.6)


class TestBackgroundImageLayer:
    """The stimulus-page background image layer (MultiplEYE)."""

    def test_png_size_and_data_uri(self, tmp_path):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        assert _png_pixel_size(str(p)) == (1, 1)
        assert _png_pixel_size(str(tmp_path / "missing.png")) is None
        uri = _image_to_data_uri(str(p))
        assert uri.startswith("data:image/png;base64,")
        assert _image_to_data_uri(str(tmp_path / "missing.png")) is None
        assert _image_to_data_uri(None) is None
        assert (
            _image_to_data_uri("data:image/png;base64,AAAA")
            == "data:image/png;base64,AAAA"
        )

    def test_layer_added_below_at_data_origin(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                background_image=str(p), background_image_size=(1310, 991)
            ),
        )
        assert len(fig.layout.images) == 1
        im = fig.layout.images[0]
        assert im.layer == "below"
        assert (im.x, im.y, im.sizex, im.sizey) == (0, 0, 1310, 991)
        assert im.yanchor == "top"  # reversed y-axis → top-left at data (0,0)
        assert str(im.source).startswith("data:image/png;base64,")

    def test_layer_honors_origin(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        # A centered stimulus (MultiplEYE) places the image at a non-zero origin.
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                background_image=str(p),
                background_image_size=(1310, 991),
                background_image_origin=(305.0, 44.5),
            ),
        )
        im = fig.layout.images[0]
        assert (im.x, im.y) == (305.0, 44.5)

    def test_no_layer_without_image_or_size(
        self, tmp_path, normalized_words_df, normalized_fixations_df
    ):
        p = tmp_path / "stim.png"
        p.write_bytes(_PNG_1x1)
        # No size → no image.
        assert (
            len(
                make_scanpath_figure(
                    normalized_words_df,
                    normalized_fixations_df,
                    **_scanpath_kwargs(background_image=str(p)),
                ).layout.images
            )
            == 0
        )
        # Missing file → no image (no crash).
        assert (
            len(
                make_scanpath_figure(
                    normalized_words_df,
                    normalized_fixations_df,
                    **_scanpath_kwargs(
                        background_image=str(tmp_path / "nope.png"),
                        background_image_size=(10, 10),
                    ),
                ).layout.images
            )
            == 0
        )
