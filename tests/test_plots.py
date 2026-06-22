"""Tests for plots.py module."""

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio.plots import (
    _image_to_data_uri,
    _png_pixel_size,
    _saccade_arrow_markers,
    _width_fit_font,
    _word_label_font_px,
    animation_playback_ms,
    build_critical_span_overlay,
    build_word_boxes,
    make_comparison_figure,
    make_scanpath_animation,
    make_scanpath_figure,
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
        assert len(fig.frames) == len(normalized_fixations_df)

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
        assert len(fig.frames) == len(normalized_fixations_df)

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

    def test_slider_declutters_long_reading_but_keeps_elapsed(
        self, normalized_words_df
    ):
        # A long reading must not draw a tick + time label per frame (illegible
        # smear). Every step keeps its real time label (so the "Elapsed" readout
        # updates on every frame and stays frame-accurate), while the per-step
        # ticks and labels are hidden — the readout is the one time display.
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
        assert len(slider.steps) == n  # every frame scrubbable
        # Every step labelled -> the Elapsed readout shows a time at any position.
        assert all(s.label for s in slider.steps)
        assert slider.currentvalue.visible
        # Tick ruler hidden, and per-step labels drawn transparent.
        assert slider.ticklen == 0
        assert slider.minorticklen == 0
        assert "0)" in slider.font.color or "rgba" in str(slider.font.color)


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
        # One frame per distinct fixation onset across both scanpaths.
        assert len(fig.frames) == 4
        # Both trails appear in the legend so the two readers are tellable apart.
        legend_names = [t.name for t in fig.data if t.showlegend]
        assert len(legend_names) == 2

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
        # Real-timestamp clock → onset of fixation 2 at 1.0s; a duration clock
        # would have shown 0.1s.
        assert labels == ["0.0s", "1.0s"], labels
        assert fig.layout.sliders[0].currentvalue.prefix == "Elapsed: "

    def test_dual_animation_identical_inputs(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Identical scanpaths share onsets, so the merged frame count collapses
        # to a single scanpath's fixation count.
        fig = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            fixations_b=normalized_fixations_df,
        )
        assert len(fig.frames) == len(normalized_fixations_df)

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
        assert len(fig.frames) == len(normalized_fixations_df)
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

    def test_frame_floor_clamps_tiny_gaps(self, normalized_words_df):
        # Gaps below the frame floor are clamped up so frames stay renderable
        # (browsers cap ~60fps); the Play frame duration is the floor itself.
        from scanpath_studio.plots import _ANIM_MIN_FRAME_MS

        fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t1", "t1"],
                "x": [100, 200, 300],
                "y": [50, 50, 50],
                "duration_ms": [5, 5, 5],
                "timestamp_ms": [0, 10, 20],  # 10 ms gaps, below the floor
                "order_in_trial": [1, 2, 3],
            }
        )
        fig = make_scanpath_animation(
            normalized_words_df,
            fix,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=1.0,
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

    def test_out_of_text_overlay_trace(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        # The synthetic trial has exactly one out-of-text fixation.
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, highlight_out_of_text=True
        )
        oot = [t for t in fig.data if t.name == "Out-of-text"]
        assert len(oot) == 1
        assert len(oot[0].x) == 1  # one off-text fixation

    def test_out_of_text_overlay_absent_by_default(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        fig = self._figure(synthetic_words_df, synthetic_fixations_df)
        assert not any(t.name == "Out-of-text" for t in fig.data)

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
