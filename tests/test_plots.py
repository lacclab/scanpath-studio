"""Tests for plots.py (matplotlib figure builders).

Figures are matplotlib ``Figure`` objects and the animation is a
``ScanpathAnimation``; artists are looked up by label (see ``tests/mpl_helpers``)
rather than by positional trace index, since matplotlib's add/z order differs
from the old Plotly trace order.
"""

import numpy as np
import pandas as pd
import pytest
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure

from tests import mpl_helpers as mh
from scanpath_studio.constants import COMPARISON_PALETTE
from scanpath_studio.plots import (
    ScanpathAnimation,
    _ANIM_MIN_FRAME_MS,
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


def _data_axes_box_px(fig):
    """The data Axes' pixel size — the matplotlib analog of the old Plotly
    plot region (figure minus the colorbar/legend reserve margins)."""
    ax = mh.data_axes(fig)
    fig.canvas.draw()
    bbox = ax.get_window_extent()
    return (round(bbox.width), round(bbox.height))


class TestDecorationDoesNotShrinkPlot:
    """A colorbar/legend must sit in reserved (extra) figure space, not steal
    space from the equal-aspect data axes."""

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
        assert _data_axes_box_px(on) == _data_axes_box_px(off)
        # The figure itself grew to hold the colorbar (it didn't shrink the plot).
        assert mh.figure_px(on)[0] > mh.figure_px(off)[0]

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
        assert _data_axes_box_px(on) == _data_axes_box_px(off)
        # The by-line legend is reserved above the plot, growing the figure height.
        assert mh.figure_px(on)[1] > mh.figure_px(off)[1]


class TestSaccadeColor:
    def test_saccade_color_threads_to_line_and_arrows(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_saccade_arrows=True, saccade_color="#123456"),
        )
        ax = mh.data_axes(fig)
        sac = mh.line_collection(ax, "saccades")
        assert sac is not None
        assert to_rgba(sac.get_color()[0]) == to_rgba("#123456")
        arrows = mh.quiver(ax, "saccade direction")
        assert arrows is not None
        assert to_rgba(arrows.get_facecolor()[0]) == to_rgba("#123456")


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
        # One line with two adjacent flagged words -> a single outline rectangle.
        assert len(build_critical_span_overlay(words, "my_flag")) == 1
        # The default column is absent -> nothing to outline.
        assert build_critical_span_overlay(words, "is_in_aspan") == []


class TestSaccadeArrowMarkers:
    """_saccade_arrow_markers returns (mid_x, mid_y, dir_x, dir_y) — unit
    direction vectors in data space (matplotlib's quiver + inverted y render them
    correctly on screen, so no angle convention is needed)."""

    def test_direction_vectors(self):
        # (0,0)->(10,0) is rightward (dir (1,0)); (10,0)->(10,10) goes to larger
        # data y, which is DOWN on the reversed y-axis (dir (0,1)).
        df = pd.DataFrame(
            {"x": [0, 10, 10], "y": [0, 0, 10], "timestamp_ms": [0, 1, 2]}
        )
        mid_x, mid_y, dir_x, dir_y = _saccade_arrow_markers(df, "x", "y")
        assert mid_x == [5.0, 10.0]
        assert mid_y == [0.0, 5.0]
        assert dir_x == pytest.approx([1.0, 0.0])
        assert dir_y == pytest.approx([0.0, 1.0])

    def test_single_fixation_yields_no_arrows(self):
        df = pd.DataFrame({"x": [1], "y": [2], "timestamp_ms": [0]})
        assert _saccade_arrow_markers(df, "x", "y") == ([], [], [], [])

    def test_zero_length_saccade_skipped(self):
        df = pd.DataFrame({"x": [5, 5], "y": [5, 5], "timestamp_ms": [0, 1]})
        assert _saccade_arrow_markers(df, "x", "y") == ([], [], [], [])

    def test_micro_saccade_below_threshold_skipped(self):
        # A large saccade then a sub-pixel refixation: only the large one gets an
        # arrow (the tiny one's heading would be noise).
        df = pd.DataFrame(
            {"x": [0, 100, 100.2], "y": [0, 0, 0], "timestamp_ms": [0, 1, 2]}
        )
        _mx, _my, dir_x, dir_y = _saccade_arrow_markers(df, "x", "y")
        assert dir_x == pytest.approx([1.0])
        assert dir_y == pytest.approx([0.0])


class TestBuildWordBoxes:
    """build_word_boxes returns backend-neutral rect specs (shared, testable
    without a backend; the builders turn them into Rectangle patches)."""

    def test_build_word_boxes(self, normalized_words_df):
        shapes = build_word_boxes(normalized_words_df)
        assert len(shapes) == len(normalized_words_df)
        assert all(shape["type"] == "rect" for shape in shapes)
        assert all("x0" in shape for shape in shapes)
        assert all("y0" in shape for shape in shapes)

    def test_build_word_boxes_empty(self):
        assert build_word_boxes(pd.DataFrame()) == []


class TestMakeScanpathFigure:
    def test_make_scanpath_figure_basic(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_order=True),
        )
        assert isinstance(fig, Figure)
        # Figure shrinks to the data's aspect ratio, capped at the requested canvas.
        w, h = mh.figure_px(fig)
        assert 0 < w <= 800
        assert 0 < h <= 600
        # Word boxes are Rectangle patches; fixations a single PathCollection.
        assert len(mh.rectangles(fig)) > 0
        assert mh.path_collection(fig, "Fixations") is not None

    def test_make_scanpath_figure_with_heatmap(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                show_word_labels=False,
                show_order=False,
                show_saccades=False,
                show_heatmap=True,
                heatmap_metric="duration_ms",
                show_colorbars=True,
            ),
        )
        assert isinstance(fig, Figure)

    def test_make_scanpath_figure_interpolated_heatmap(
        self, normalized_words_df, normalized_fixations_df
    ):
        """heatmap_style='Interpolated' adds a smooth density image."""
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(
                show_word_labels=False,
                show_order=False,
                show_saccades=False,
                show_heatmap=True,
                heatmap_style="Interpolated",
                heatmap_metric="duration_ms",
            ),
        )
        assert mh.has_axes_image(fig)

    def test_make_scanpath_figure_saccade_arrows(
        self, normalized_words_df, normalized_fixations_df
    ):
        """show_saccade_arrows adds exactly one Quiver with one arrow/saccade."""
        fig = make_scanpath_figure(
            normalized_words_df,
            normalized_fixations_df,
            **_scanpath_kwargs(show_saccade_arrows=True),
        )
        ax = mh.data_axes(fig)
        arrows = mh.quivers(ax)
        assert len(arrows) == 1
        # Three fixations -> two saccade segments -> two arrowheads.
        assert len(arrows[0].get_offsets()) == 2

    def test_make_scanpath_figure_empty_fixations(self, normalized_words_df):
        fig = make_scanpath_figure(
            normalized_words_df,
            pd.DataFrame(),
            **_scanpath_kwargs(show_word_labels=True, show_order=True),
        )
        assert isinstance(fig, Figure)

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
            **_scanpath_kwargs(show_word_labels=True, show_order=True),
            raw_gaze=raw_gaze,
            show_raw_gaze=True,
        )
        assert isinstance(fig, Figure)
        rg = mh.path_collection(fig, "Raw gaze")
        assert rg is not None and len(rg.get_offsets()) == 2

    def test_make_scanpath_figure_non_spatial_axes(self, normalized_fixations_df):
        fig = make_scanpath_figure(
            pd.DataFrame(),
            normalized_fixations_df,
            **_scanpath_kwargs(
                x_field="timestamp_ms",
                y_field="duration_ms",
                show_words=False,
                show_word_labels=False,
                show_saccades=False,
            ),
        )
        assert isinstance(fig, Figure)


def _anim_kwargs(**overrides):
    base = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=12,
        font_family="Arial",
    )
    base.update(overrides)
    return base


def _order_number_texts(ax):
    """The fixation order-number Text artists (digit strings, not word labels)."""
    return [
        t
        for t in mh.data_axes(ax).texts
        if t.get_text().isdigit() and t.get_label() != "words"
    ]


class TestMakeScanpathAnimation:
    def test_make_scanpath_animation_basic(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(
                playback_speed=1.0,
                show_words=True,
                show_word_labels=True,
                show_saccades=True,
                show_order=True,
                marker_size_range=(8, 24),
                order_font_size=10,
                order_font_color="#000000",
            ),
        )
        assert isinstance(anim, ScanpathAnimation)
        assert isinstance(anim.figure, Figure)
        # One frame per fixation onset (== n fixations for a single normal trial).
        assert len(anim.frames) == len(normalized_fixations_df)

    def test_make_scanpath_animation_empty_fixations(self, normalized_words_df):
        anim = make_scanpath_animation(
            normalized_words_df, pd.DataFrame(), **_anim_kwargs()
        )
        assert isinstance(anim, ScanpathAnimation)
        assert len(anim.frames) == 0

    def test_make_scanpath_animation_playback_speed(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(playback_speed=2.0),
        )
        assert isinstance(anim, ScanpathAnimation)

    def test_animation_colors_by_numeric_metric(
        self, normalized_words_df, normalized_fixations_df
    ):
        # The replay honours color-by + colorscale like the static figure, with
        # the colour normalisation pinned to the WHOLE trial so colours don't
        # renormalise as the trail grows frame by frame.
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(color_by="duration_ms", fixation_colorscale="Viridis"),
        )
        trail = anim.trails[0]
        # A fixed Normalize pinned to the whole trial's duration range.
        assert trail.norm.vmin == 180.0 and trail.norm.vmax == 250.0
        # The full-length scalar colour array is stated once and never changes.
        assert list(np.ma.getdata(trail.get_array())) == [200, 250, 180]
        # Frame 0 reveals only the first fixation's POSITION (the rest masked
        # off), but the colour array / norm stay whole.
        offs = trail.get_offsets()
        assert offs[0][0] == 125
        assert np.ma.getmaskarray(offs)[1:].all()
        # Last frame: positions all revealed, colour array + norm unchanged.
        anim.draw_frame(len(anim.frames) - 1)
        assert list(np.ma.getdata(trail.get_array())) == [200, 250, 180]
        assert trail.norm.vmin == 180.0 and trail.norm.vmax == 250.0
        assert not np.ma.getmaskarray(trail.get_offsets()).any()

    def test_animation_explicit_color_range_pins_norm(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(color_by="duration_ms", fixation_color_range=(0.0, 500.0)),
        )
        trail = anim.trails[0]
        assert trail.norm.vmin == 0.0 and trail.norm.vmax == 500.0

    def test_animation_categorical_color_gets_legend(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(color_by="saccade_type"),
        )
        trail = anim.trails[0]
        # Per-fixation discrete colours stated at full length.
        assert len(trail.get_facecolor()) == 3
        offs = trail.get_offsets()
        assert offs[0][0] == 125 and np.ma.getmaskarray(offs)[1:].all()
        assert mh.legend_labels(anim.figure) == {
            "saccade_type: RIGHT",
            "saccade_type: LEFT",
        }

    def test_animation_default_keeps_flat_color(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df, normalized_fixations_df, **_anim_kwargs()
        )
        assert to_rgba(anim.trails[0].get_facecolor()[0]) == to_rgba(
            COMPARISON_PALETTE[0]
        )

    def test_order_numbers_never_glide_in_from_corner(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Order numbers live in their own per-fixation Text artists, fixed at the
        # true fixation coordinate; a number is revealed by toggling visibility,
        # never by moving — so it only ever turns on in place.
        n = len(normalized_fixations_df)
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(show_order=True),
        )
        ax = mh.data_axes(anim.figure)
        order = _order_number_texts(ax)
        assert [t.get_text() for t in order] == [str(j + 1) for j in range(n)]

        # Positions never change across frames (they never glide).
        anim.draw_frame(0)
        pos_first = [t.get_position() for t in order]
        anim.draw_frame(n - 1)
        pos_last = [t.get_position() for t in order]
        assert pos_first == pos_last

        prev_shown = 0
        for k in range(n):
            anim.draw_frame(k)
            vis = [t.get_visible() for t in order]
            shown = sum(vis)
            # Visible numbers are a contiguous prefix; the tail is hidden.
            assert vis == [True] * shown + [False] * (n - shown)
            assert shown >= prev_shown  # monotonic reveal
            prev_shown = shown
        assert prev_shown == n  # last frame shows the whole reading

    def test_elapsed_readout_per_frame(self, normalized_words_df):
        # Every frame carries a frame-accurate elapsed-time label, and the
        # on-screen readout shows it (the matplotlib analog of the old slider's
        # decluttered "Elapsed: X.Xs").
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
        anim = make_scanpath_animation(normalized_words_df, fixations, **_anim_kwargs())
        assert len(anim.elapsed_labels) == n
        assert all(s.endswith("s") for s in anim.elapsed_labels)
        ax = mh.data_axes(anim.figure)
        readout = [t for t in ax.texts if t.get_text().startswith("Elapsed:")]
        assert len(readout) == 1
        anim.draw_frame(5)
        assert anim.elapsed_labels[5] in readout[0].get_text()


class TestDualScanpathAnimation:
    @staticmethod
    def _second_fixations():
        # Onsets rebased to t=0: [0, 300]. With A's [0, 200, 450] the merged onset
        # set is {0, 200, 300, 450} -> 4 frames.
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
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(playback_speed=1.0),
            fixations_b=self._second_fixations(),
        )
        assert isinstance(anim, ScanpathAnimation)
        assert len(anim.frames) == 4  # one frame per distinct onset across both
        # Both trails appear in the legend so the readers are tellable apart.
        assert len(mh.legend_labels(anim.figure)) == 2
        assert len(anim.trails) == 2

    def test_dual_animation_ignores_color_by(
        self, normalized_words_df, normalized_fixations_df
    ):
        # The flat A/B colours ARE the scanpath identity in the overlay.
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(color_by="duration_ms"),
            fixations_b=self._second_fixations(),
        )
        trail_colors = {to_rgba(t.get_facecolor()[0]) for t in anim.trails}
        assert trail_colors == {to_rgba(c) for c in COMPARISON_PALETTE}

    def test_dual_animation_uses_real_timestamps(self, normalized_words_df):
        # The shared clock comes from recorded timestamp_ms (rebased), NOT
        # cumulative durations. Fixation 2 starts at t=1000ms; a duration clock
        # would place it at 0.1s.
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
        anim = make_scanpath_animation(
            normalized_words_df,
            fix_a,
            **_anim_kwargs(),
            fixations_b=fix_a.iloc[:1].copy(),
        )
        assert anim.elapsed_labels == ["0.0s", "1.0s"]
        ax = mh.data_axes(anim.figure)
        readout = [t for t in ax.texts if t.get_text().startswith("Elapsed:")]
        assert readout and readout[0].get_text().startswith("Elapsed: ")

    def test_dual_animation_identical_inputs(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(),
            fixations_b=normalized_fixations_df,
        )
        assert len(anim.frames) == len(normalized_fixations_df)

    def test_dual_animation_one_empty_falls_back(
        self, normalized_words_df, normalized_fixations_df
    ):
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(),
            fixations_b=pd.DataFrame(),
        )
        assert isinstance(anim, ScanpathAnimation)
        assert len(anim.frames) == len(normalized_fixations_df)
        assert mh.legend_labels(anim.figure) == set()  # no legend in single replay

    def test_dual_animation_both_empty(self, normalized_words_df):
        anim = make_scanpath_animation(
            normalized_words_df,
            pd.DataFrame(),
            **_anim_kwargs(),
            fixations_b=pd.DataFrame(),
        )
        assert isinstance(anim, ScanpathAnimation)
        assert len(anim.frames) == 0


class TestAnimationPlaybackTiming:
    def test_playback_ms_matches_runtime(
        self, normalized_words_df, normalized_fixations_df
    ):
        # animation_playback_ms equals what the player runs: every frame advances
        # at the average frame duration, so runtime == n_frames * avg.
        speed = 2.0
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            **_anim_kwargs(playback_speed=speed),
        )
        expected = len(anim.frames) * anim.avg_frame_duration
        _span, playback_ms = animation_playback_ms([normalized_fixations_df], speed)
        assert playback_ms == expected

    def test_playback_ms_empty(self):
        assert animation_playback_ms([], 1.0) == (0.0, 0.0)

    def test_frame_floor_clamps_tiny_gaps(self, normalized_words_df):
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
        anim = make_scanpath_animation(
            normalized_words_df, fix, **_anim_kwargs(playback_speed=1.0)
        )
        assert anim.avg_frame_duration == _ANIM_MIN_FRAME_MS

    def test_fake_index_timestamps_fall_back_to_durations(self, normalized_words_df):
        # Synthesized timestamp_ms = 0,1,2,... must NOT be read as milliseconds;
        # the clock falls back to back-to-back durations.
        fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t1", "t1"],
                "x": [120, 220, 320],
                "y": [70, 70, 70],
                "duration_ms": [200, 250, 180],
                "timestamp_ms": [0, 1, 2],  # row-index sentinel
                "order_in_trial": [1, 2, 3],
            }
        )
        span_ms, _playback = animation_playback_ms([fix], 1.0)
        assert span_ms == 630  # 200+250+180, NOT ~2 ms

    def test_single_mode_color_is_canonical(
        self, normalized_words_df, normalized_fixations_df
    ):
        # Degenerate call: only the B slot is populated. The lone trail must still
        # be the canonical single-replay blue, never the red "B" colour.
        anim = make_scanpath_animation(
            normalized_words_df,
            pd.DataFrame(),
            **_anim_kwargs(),
            fixations_b=normalized_fixations_df,
        )
        assert len(anim.trails) == 1
        face = to_rgba(anim.trails[0].get_facecolor()[0])
        assert face == to_rgba(COMPARISON_PALETTE[0])
        assert face != to_rgba(COMPARISON_PALETTE[1])


class TestMakeComparisonFigure:
    @staticmethod
    def _two_trials(words, fixations):
        words_multi = pd.concat(
            [
                words.assign(participant_id="p1", trial_id="t1"),
                words.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        fix_multi = pd.concat(
            [
                fixations.assign(participant_id="p1", trial_id="t1"),
                fixations.assign(participant_id="p2", trial_id="t1"),
            ]
        )
        return words_multi, fix_multi

    def test_make_comparison_figure(self, normalized_words_df, normalized_fixations_df):
        words_multi, fix_multi = self._two_trials(
            normalized_words_df, normalized_fixations_df
        )
        fig = make_comparison_figure(
            words_multi,
            fix_multi,
            trial_a=("p1", "t1"),
            trial_b=("p2", "t1"),
            canvas_width=800,
            canvas_height=600,
            font_family="Arial",
            base_font_size=12,
        )
        assert isinstance(fig, Figure)
        ax = mh.data_axes(fig)
        marker_colls = [c for c in ax.collections if isinstance(c, PathCollection)]
        assert len(marker_colls) == 2  # one fixation collection per trial
        assert to_rgba(marker_colls[0].get_facecolor()[0]) == to_rgba(
            COMPARISON_PALETTE[0]
        )
        assert to_rgba(marker_colls[1].get_facecolor()[0]) == to_rgba(
            COMPARISON_PALETTE[1]
        )

    def test_comparison_per_scanpath_style(
        self, normalized_words_df, normalized_fixations_df
    ):
        words_multi, fix_multi = self._two_trials(
            normalized_words_df, normalized_fixations_df
        )
        fig = make_comparison_figure(
            words_multi,
            fix_multi,
            trial_a=("p1", "t1"),
            trial_b=("p2", "t1"),
            canvas_width=800,
            canvas_height=600,
            font_family="Arial",
            base_font_size=12,
            style_a={"fix_color": "#123456", "hollow": True},
            style_b={"saccade_color": "#abcdef", "saccade_style": "dash"},
        )
        ax = mh.data_axes(fig)
        marker_colls = [c for c in ax.collections if isinstance(c, PathCollection)]
        # Scanpath 1 is hollow: transparent fill, coloured outline.
        assert marker_colls[0].get_facecolor()[0][3] == 0.0
        assert to_rgba(marker_colls[0].get_edgecolor()[0]) == to_rgba("#123456")
        # Scanpath 2 saccades are dashed in the requested colour.
        line_colls = [c for c in ax.collections if isinstance(c, LineCollection)]
        dashed = [
            c for c in line_colls if to_rgba(c.get_color()[0]) == to_rgba("#abcdef")
        ]
        assert dashed
        # A dashed linestyle has a non-None dash pattern (solid is None).
        assert dashed[0].get_linestyle()[0][1] is not None


class TestPlotEnhancements:
    def _figure(self, words, fixations, **overrides):
        kwargs = _scanpath_kwargs(
            canvas_width=500,
            canvas_height=300,
            show_order=True,
        )
        kwargs.update(overrides)
        return make_scanpath_figure(words, fixations, **kwargs)

    def test_background_color_applied(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, background_color="#bdbdbd"
        )
        ax = mh.data_axes(fig)
        assert to_rgba(ax.get_facecolor()) == to_rgba("#bdbdbd")
        assert to_rgba(fig.get_facecolor()) == to_rgba("#bdbdbd")

    def test_background_color_default_is_white(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        fig = self._figure(synthetic_words_df, synthetic_fixations_df)
        assert to_rgba(mh.data_axes(fig).get_facecolor()) == to_rgba("white")

    def test_out_of_text_overlay(self, synthetic_words_df, synthetic_fixations_df):
        # The synthetic trial has exactly one out-of-text fixation.
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, highlight_out_of_text=True
        )
        oot = mh.path_collection(fig, "Out-of-text")
        assert oot is not None
        assert len(oot.get_offsets()) == 1

    def test_out_of_text_overlay_absent_by_default(
        self, synthetic_words_df, synthetic_fixations_df
    ):
        fig = self._figure(synthetic_words_df, synthetic_fixations_df)
        assert mh.path_collection(fig, "Out-of-text") is None

    def test_color_by_line_legend(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, color_by_line=True
        )
        line_entries = [lbl for lbl in mh.legend_labels(fig) if lbl.startswith("line:")]
        assert len(line_entries) == 2

    def test_hollow_fixations(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, hollow_fixations=True
        )
        fix = mh.path_collection(fig, "Fixations")
        assert fix.get_facecolor()[0][3] == 0.0  # transparent fill
        assert fix.get_linewidths()[0] >= 1.0  # visible outline

    def test_saccade_style_dash(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df, synthetic_fixations_df, saccade_style="dash"
        )
        sac = mh.line_collection(mh.data_axes(fig), "saccades")
        assert sac.get_linestyle()[0][1] is not None  # dashed, not solid

    def test_text_color_applied(self, synthetic_words_df, synthetic_fixations_df):
        fig = self._figure(
            synthetic_words_df,
            synthetic_fixations_df,
            show_word_labels=True,
            text_color="#0a0b0c",
        )
        words = mh.word_label_texts(mh.data_axes(fig))
        assert words and to_rgba(words[0].get_color()) == to_rgba("#0a0b0c")


class TestTrueToScaleText:
    """Word-label text is sized true-to-scale from the box geometry."""

    def _figure(self, words, fixations, **overrides):
        kwargs = _scanpath_kwargs(
            base_font_size=16,
            font_family="monospace",
            show_fixations=False,
            show_order=False,
            show_saccades=False,
        )
        kwargs.update(overrides)
        return make_scanpath_figure(words, fixations, **kwargs)

    # -- _word_label_font_px unit behaviour (pure helper) -----------------
    def test_autofit_uses_box_height_over_line_spacing(self, normalized_words_df):
        font = _word_label_font_px(
            normalized_words_df,
            scale=1.0,
            line_spacing=3.0,
            manual_font_px=99,
            scale_text_to_boxes=True,
        )
        assert 0 < font <= 50 / 3 + 1e-6
        font2 = _word_label_font_px(
            normalized_words_df,
            scale=2.0,
            line_spacing=3.0,
            manual_font_px=99,
            scale_text_to_boxes=True,
        )
        assert font2 == pytest.approx(2 * font)

    def test_autofit_shrinks_with_larger_line_spacing(self, normalized_words_df):
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
        font = _word_label_font_px(
            normalized_words_df,
            scale=0.5,
            line_spacing=3.0,
            manual_font_px=20,
            scale_text_to_boxes=False,
        )
        assert font == pytest.approx(10.0)

    def test_falls_back_to_manual_without_boxes(self):
        font = _word_label_font_px(
            pd.DataFrame(),
            scale=0.5,
            line_spacing=3.0,
            manual_font_px=20,
            scale_text_to_boxes=True,
        )
        assert font == pytest.approx(10.0)

    def test_width_fit_recovers_per_char_advance(self, normalized_words_df):
        wf = _width_fit_font(normalized_words_df)
        assert wf == pytest.approx(10 / 0.6 * 0.92, rel=1e-6)

    # -- integration through the figure builder ---------------------------
    def test_label_font_tracks_line_spacing(
        self, normalized_words_df, normalized_fixations_df
    ):
        small = self._figure(
            normalized_words_df, normalized_fixations_df, line_spacing=3.0
        )
        large = self._figure(
            normalized_words_df, normalized_fixations_df, line_spacing=10.0
        )
        assert mh.word_label_px(large) < mh.word_label_px(small)

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
        assert mh.word_label_px(a) == pytest.approx(mh.word_label_px(b))
