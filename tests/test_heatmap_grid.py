"""The Interpolated / Duration-mass heatmap's smoothing grid (review round 8)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio import plots


def _heatmap_trace(words: pd.DataFrame, fixations: pd.DataFrame, style: str):
    fig = plots.make_scanpath_figure(
        words,
        fixations,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        show_heatmap=True,
        heatmap_style=style,
        heatmap_metric="duration_ms",
    )
    return next(t for t in fig.data if isinstance(t, go.Heatmap))


def _fixations(xs, ys) -> pd.DataFrame:
    n = len(xs)
    return pd.DataFrame(
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "x": [float(x) for x in xs],
            "y": [float(y) for y in ys],
            "duration_ms": [200.0] * n,
            "timestamp_ms": [i * 250.0 for i in range(n)],
            "fixation_id": list(range(n)),
            "order_in_trial": list(range(n)),
        }
    )


def _single_line_words() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "text_id": "text",
            "word_id": [0, 1],
            "text": ["short", "line"],
            "line_idx": [0, 0],
            "x": [100.0, 200.0],
            "y": [100.0, 100.0],
            "width": [100.0, 100.0],
            "height": [20.0, 20.0],
        }
    )


class TestGaussianBlurShape:
    @pytest.mark.parametrize(
        ("shape", "sigma_rows", "sigma_cols"),
        [
            ((80, 240), 4.0, 6.0),  # ordinary
            ((10, 240), 25.0, 6.0),  # short: row kernel longer than the axis
            ((240, 3), 4.0, 50.0),  # narrow: column kernel longer than the axis
            ((1, 1), 30.0, 30.0),  # single cell
        ],
    )
    def test_output_keeps_input_shape(self, shape, sigma_rows, sigma_cols):
        grid = np.zeros(shape)
        grid[shape[0] // 2, shape[1] // 2] = 1.0
        out = plots._gaussian_blur_2d(grid, sigma_rows, sigma_cols)
        assert out.shape == shape

    @pytest.mark.parametrize(
        ("shape", "impulse", "sigma_rows", "sigma_cols"),
        [
            ((80, 240), (30, 100), 4.0, 6.0),
            ((10, 240), (3, 100), 25.0, 6.0),
            ((240, 7), (100, 2), 4.0, 50.0),
            ((5, 5), (1, 3), 40.0, 40.0),
        ],
    )
    def test_impulse_stays_at_its_cell(self, shape, impulse, sigma_rows, sigma_cols):
        grid = np.zeros(shape)
        grid[impulse] = 1.0
        out = plots._gaussian_blur_2d(grid, sigma_rows, sigma_cols)
        assert np.unravel_index(np.argmax(out), out.shape) == impulse

    def test_ordinary_grid_matches_same_mode_convolution(self):
        """Where the kernel fits, the result is the old ``mode="same"`` blur."""
        rng = np.random.default_rng(0)
        grid = rng.random((80, 240))
        expected = grid.copy()
        k = plots._gaussian_kernel_1d(4.5)
        expected = np.apply_along_axis(
            lambda v: np.convolve(v, k, mode="same"), 0, expected
        )
        k = plots._gaussian_kernel_1d(7.25)
        expected = np.apply_along_axis(
            lambda v: np.convolve(v, k, mode="same"), 1, expected
        )
        np.testing.assert_allclose(plots._gaussian_blur_2d(grid, 4.5, 7.25), expected)

    def test_trimmed_kernel_is_the_full_kernels_centre(self):
        full = plots._gaussian_kernel_1d(30.0)
        trimmed = plots._gaussian_kernel_1d(30.0, max_radius=4)
        centre = len(full) // 2
        np.testing.assert_allclose(trimmed, full[centre - 4 : centre + 5])


class TestHeatmapCoordinates:
    @pytest.mark.parametrize("style", ["Interpolated", "Duration mass"])
    def test_single_line_z_matches_its_coordinates(self, style):
        words = _single_line_words()
        trace = _heatmap_trace(words, _fixations([150, 250], [110, 110]), style)
        z = np.asarray(trace.z, dtype=float)
        assert z.shape == (len(trace.y), len(trace.x))

    def test_single_line_density_peaks_on_the_fixation_row(self):
        words = _single_line_words()
        trace = _heatmap_trace(
            words, _fixations([150, 250], [110, 110]), "Interpolated"
        )
        z = np.nan_to_num(np.asarray(trace.z, dtype=float))
        peak_row = np.unravel_index(np.argmax(z), z.shape)[0]
        step = trace.y[1] - trace.y[0]
        assert abs(trace.y[peak_row] - 110) <= step


_NO_WORDS = pd.DataFrame(
    columns=[
        "participant_id",
        "trial_id",
        "text_id",
        "word_id",
        "text",
        "line_idx",
        "x",
        "y",
        "width",
        "height",
    ]
)


class TestInterpolationGridBudget:
    @pytest.mark.parametrize(
        ("xs", "ys"),
        [
            ([100, 500], [100, 100]),  # horizontal, one row
            ([100, 100], [100, 500]),  # vertical, one column
            ([100, 101], [100, 50_000]),  # tall and narrow
            ([100, 100], [100, 100]),  # coincident
            ([100, 100.0001], [100, 100.0002]),  # near-coincident
        ],
    )
    def test_fixation_only_grid_stays_within_budget(self, xs, ys, monkeypatch):
        requested = {}
        real_histogram2d = np.histogram2d

        def spy(x, y, bins, **kwargs):
            requested["nx"], requested["ny"] = len(bins[0]) - 1, len(bins[1]) - 1
            return real_histogram2d(x, y, bins=bins, **kwargs)

        monkeypatch.setattr(plots.np, "histogram2d", spy)
        trace = _heatmap_trace(_NO_WORDS, _fixations(xs, ys), "Interpolated")
        nx, ny = requested["nx"], requested["ny"]
        assert max(nx, ny) == plots._INTERP_GRID
        assert min(nx, ny) >= plots._INTERP_MIN_CELLS
        assert nx * ny <= plots._INTERP_GRID**2
        z = np.asarray(trace.z, dtype=float)
        assert z.shape == (len(trace.y), len(trace.x)) == (ny, nx)
        # Every edge is distinct, so the blob has real extent on both axes.
        assert trace.x[-1] > trace.x[0] and trace.y[-1] > trace.y[0]

    def test_budget_goes_to_the_wider_axis(self):
        assert plots._interp_grid_shape(800.0, 200.0) == (240, 60)
        assert plots._interp_grid_shape(200.0, 800.0) == (60, 240)
        assert plots._interp_grid_shape(10_000.0, 1.0) == (240, 10)

    def test_coincident_fixations_peak_at_their_point(self):
        trace = _heatmap_trace(
            _NO_WORDS, _fixations([100, 100], [300, 300]), "Interpolated"
        )
        z = np.nan_to_num(np.asarray(trace.z, dtype=float))
        row, col = np.unravel_index(np.argmax(z), z.shape)
        assert abs(trace.x[col] - 100) <= trace.x[1] - trace.x[0]
        assert abs(trace.y[row] - 300) <= trace.y[1] - trace.y[0]
