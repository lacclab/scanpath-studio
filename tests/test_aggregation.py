"""Unit tests for the Corpus Analysis → Aggregated Views aggregation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tests import mpl_helpers as mh

from scanpath_studio.aggregation import (
    aggregate_word_measures_by_text,
    grouped_metric_values,
    metric_by_fixation_index,
    metric_by_trial_index,
    text_read_counts,
)
from scanpath_studio.data import derive_trial_index, has_explicit_trial_index


class TestDeriveTrialIndex:
    def test_uses_explicit_column(self):
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t1"],
                "trial_index": [5, 6, 1],
            }
        )
        assert has_explicit_trial_index(df)
        out = derive_trial_index(df)
        assert list(out) == [5.0, 6.0, 1.0]

    def test_derives_from_timestamp_per_participant(self):
        # p1 reads t2 (ts 0) before t1 (ts 100) → t2=1, t1=2.
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1", "p1", "p2"],
                "trial_id": ["t1", "t1", "t2", "t2", "tX"],
                "timestamp_ms": [100, 150, 0, 50, 999],
            }
        )
        assert not has_explicit_trial_index(df)
        out = derive_trial_index(df)
        # rows for t1 → 2, t2 → 1, p2 tX → 1
        assert list(out) == [2.0, 2.0, 1.0, 1.0, 1.0]

    def test_single_trial_per_participant(self):
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "timestamp_ms": [0, 10],
            }
        )
        assert list(derive_trial_index(df)) == [1.0, 1.0]

    def test_empty(self):
        out = derive_trial_index(pd.DataFrame())
        assert out.empty


class TestMetricByTrialIndex:
    def test_averages_per_trial_then_per_index(self):
        # Two trials at index 1 (means 100 and 200) → index-1 value = 150.
        df = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "tA", "tA"],
                "trial_index": [1, 1, 1, 1],
                "duration_ms": [50, 150, 100, 300],
            }
        )
        out = metric_by_trial_index(df, "duration_ms")
        assert list(out["trial_index"]) == [1]
        assert out.iloc[0]["value"] == 150.0
        assert out.iloc[0]["n_trials"] == 2

    def test_missing_metric_returns_empty(self):
        df = pd.DataFrame(
            {"participant_id": ["p1"], "trial_id": ["t1"], "trial_index": [1]}
        )
        assert metric_by_trial_index(df, "nope").empty


class TestMetricByFixationIndex:
    def test_groups_by_order_in_trial(self):
        fix = pd.DataFrame(
            {
                "order_in_trial": [1, 1, 2, 2],
                "duration_ms": [100, 200, 50, 50],
            }
        )
        out = metric_by_fixation_index(fix, "duration_ms")
        assert list(out["fixation_index"]) == [1, 2]
        assert list(out["value"]) == [150.0, 50.0]

    def test_respects_max_index(self):
        fix = pd.DataFrame({"order_in_trial": [1, 2, 3], "duration_ms": [10, 20, 30]})
        out = metric_by_fixation_index(fix, "duration_ms", max_index=2)
        assert list(out["fixation_index"]) == [1, 2]


class TestGroupedMetricValues:
    def test_all_data_single_group(self):
        df = pd.DataFrame({"duration_ms": [1.0, 2.0, 3.0]})
        groups, dropped = grouped_metric_values(df, "duration_ms")
        assert set(groups) == {"All"}
        assert dropped == 0
        np.testing.assert_array_equal(groups["All"], np.array([1.0, 2.0, 3.0]))

    def test_groups_by_column_and_caps(self):
        df = pd.DataFrame(
            {
                "duration_ms": list(range(20)),
                "g": [f"g{i}" for i in range(20)],  # 20 distinct groups
            }
        )
        groups, dropped = grouped_metric_values(df, "duration_ms", "g", max_groups=12)
        assert len(groups) == 12
        assert dropped == 8


class TestPerTextAggregates:
    def _words(self):
        return pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "t2", "t2"],
                "text_id": ["A", "A", "A", "A"],
                "word_id": [0, 1, 0, 1],
                "x": [0, 10, 0, 10],
                "y": [0, 0, 0, 0],
                "width": [10, 10, 10, 10],
                "height": [10, 10, 10, 10],
                "text": ["the", "cat", "the", "cat"],
                "total_fixation_duration_ms": [100, 200, 300, 400],
                "n_fixations": [1, 2, 3, 4],
            }
        )

    def test_aggregate_word_measures_by_text(self):
        out = aggregate_word_measures_by_text(self._words(), "text_id", "A")
        assert len(out) == 2  # one row per word_id
        word0 = out[out["word_id"] == 0].iloc[0]
        assert word0["total_fixation_duration_ms"] == 200.0  # mean(100, 300)
        assert {"x", "y", "width", "height", "text"} <= set(out.columns)

    def test_text_read_counts(self):
        counts = text_read_counts(self._words(), "text_id")
        assert list(counts["text"]) == ["A"]
        assert list(counts["n_participants"]) == [2]


class TestAggregatedFigures:
    def test_trend_figure_has_traces(self):
        from matplotlib.figure import Figure

        from scanpath_studio.plots import make_trend_figure

        df = pd.DataFrame(
            {"trial_index": [1, 2, 3], "value": [10.0, 20.0, 15.0], "sem": [1, 2, 1]}
        )
        fig = make_trend_figure(
            df,
            x_col="trial_index",
            y_label="Duration",
            title="Trend",
            canvas_width=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert isinstance(fig, Figure)
        # The trend line is drawn (matplotlib analog of "has a trace").
        ax = mh.data_axes(fig)
        assert len(ax.lines) >= 1
        # ...and the ±SEM band adds a shaded PolyCollection via fill_between.
        from matplotlib.collections import PolyCollection

        assert any(isinstance(c, PolyCollection) for c in ax.collections)

    def test_histogram_renders_bars(self):
        from matplotlib.figure import Figure

        from scanpath_studio.plots import make_aggregated_histogram

        fig = make_aggregated_histogram(
            {"All": np.arange(100, dtype=float)},
            metric_label="Duration",
            canvas_width=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert isinstance(fig, Figure)
        # The histogram bars are Rectangle patches on the data axes.
        ax = mh.data_axes(fig)
        assert len(ax.patches) >= 1

    def test_empty_inputs_render_no_data(self):
        from scanpath_studio.plots import make_aggregated_histogram, make_trend_figure

        f1 = make_trend_figure(
            pd.DataFrame(),
            x_col="trial_index",
            y_label="X",
            title="Trend",
            canvas_width=600,
            base_font_size=12,
            font_family="Arial",
        )
        f2 = make_aggregated_histogram(
            {},
            metric_label="d",
            canvas_width=600,
            base_font_size=12,
            font_family="Arial",
        )
        assert "no data" in (mh.data_axes(f1).get_title() or "").lower()
        assert "no data" in (mh.data_axes(f2).get_title() or "").lower()
