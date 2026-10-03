"""Raw gaze imported without a clock is numbered, never given a time.

A samples table with coordinates but no timestamp used to be stamped
``timestamp_ms = 0, 1, 2, …`` — a 1000 Hz sampling rate nothing in the data
stated — which then reached the plot's colour scale and hover (``t: 2 ms``) and
the exported table. It now keeps the order as ``sample_index`` (1, 2, … per
trial) and has no ``timestamp_ms`` at all; a mapped clock is unchanged.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api, data, plots
from scanpath_studio.column_names import GENERATED, from_schema
from scanpath_studio.constants import SAMPLE_INDEX

SCHEMA = {"participant": "reader", "trial": "trial", "x": "x", "y": "y"}


def _samples(**extra) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "reader": ["p1"] * 5,
            "trial": ["t1", "t1", "t1", "t2", "t2"],
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [6.0, 7.0, 8.0, 9.0, 10.0],
            **extra,
        }
    )


@pytest.fixture
def clockless() -> pd.DataFrame:
    return data.normalize_raw_gaze(_samples(), SCHEMA)


class TestNormalize:
    def test_no_clock_means_no_time_and_a_sample_number(self, clockless):
        assert "timestamp_ms" not in clockless.columns
        assert clockless[SAMPLE_INDEX].tolist() == [1, 2, 3, 1, 2]

    def test_a_mapped_clock_is_unchanged(self):
        frame = data.normalize_raw_gaze(
            _samples(t=[10, 12, 14, 0, 2]), {**SCHEMA, "timestamp": "t"}
        )
        assert frame["timestamp_ms"].tolist() == [10, 12, 14, 0, 2]
        assert SAMPLE_INDEX not in frame.columns

    def test_a_clock_in_seconds_is_still_converted(self):
        frame = data.normalize_raw_gaze(
            _samples(**{"time [s]": [0.5, 0.502, 0.504, 1.0, 1.002]}),
            {**SCHEMA, "timestamp": "time [s]"},
        )
        assert frame["timestamp_ms"].round(3).tolist() == [
            500.0,
            502.0,
            504.0,
            1000.0,
            1002.0,
        ]

    def test_a_kept_extra_named_timestamp_ms_is_not_read_as_a_clock(self):
        # The user cleared the Timestamp mapping (✏️ Edit dataset keeps every
        # stored column): the old column must not come back as the clock.
        frame = data.normalize_raw_gaze(
            _samples(timestamp_ms=[0, 1, 2, 0, 1]),
            SCHEMA,
            keep_columns={"timestamp_ms"},
        )
        assert "timestamp_ms" not in frame.columns
        assert frame[SAMPLE_INDEX].tolist() == [1, 2, 3, 1, 2]

    def test_the_public_table_carries_the_sample_number(self, clockless):
        public = data.shareable_frame(clockless)
        assert SAMPLE_INDEX in public.columns
        assert "timestamp_ms" not in public.columns

    def test_column_names_say_it_was_made_and_is_no_time(self):
        names = from_schema("raw_gaze", SCHEMA, ["reader", "trial", "x", "y"])
        assert names.kind_of(SAMPLE_INDEX) == GENERATED
        assert "timestamp_ms" not in names.entries

    def test_the_api_loader_has_no_invented_time(self):
        frame = api.load_raw_gaze(_samples(), raw_gaze_schema=SCHEMA)
        assert "timestamp_ms" not in frame.columns
        assert frame[SAMPLE_INDEX].tolist() == [1, 2, 3, 1, 2]


def _raw_gaze_trace(fig):
    return next(t for t in fig.data if t.name == "Raw gaze")


class TestPlot:
    def test_coloured_by_sample_order_and_labelled_so(self, clockless):
        fig = plots.make_scanpath_figure(
            pd.DataFrame(),
            data.empty_fixations_frame(),
            raw_gaze=clockless,
            show_raw_gaze=True,
            canvas_width=800,
            canvas_height=600,
            base_font_size=16,
        )
        trace = _raw_gaze_trace(fig)
        assert list(trace.marker.color) == [1, 2, 3, 1, 2]
        assert trace.legendgrouptitle.text == "Sample order"
        assert "sample %{customdata}" in trace.hovertemplate
        assert "ms" not in trace.hovertemplate
        assert list(trace.customdata) == [1, 2, 3, 1, 2]

    def test_a_real_clock_still_reads_as_time(self):
        timed = data.normalize_raw_gaze(
            _samples(t=[10, 12, 14, 0, 2]), {**SCHEMA, "timestamp": "t"}
        )
        fig = plots.make_scanpath_figure(
            pd.DataFrame(),
            data.empty_fixations_frame(),
            raw_gaze=timed,
            show_raw_gaze=True,
            canvas_width=800,
            canvas_height=600,
            base_font_size=16,
        )
        trace = _raw_gaze_trace(fig)
        assert "t: %{customdata} ms" in trace.hovertemplate
        assert trace.legendgrouptitle.text is None

    def test_the_comparison_trace_says_sample_too(self, clockless):
        fig = plots.go.Figure()
        settings = plots.FigureSettings(
            canvas_width=800, canvas_height=600, base_font_size=16
        )
        plots._add_comparison_raw_gaze_trace(fig, clockless, "A", "#123456", settings)
        assert "sample %{customdata}" in fig.data[0].hovertemplate
        assert " ms" not in fig.data[0].hovertemplate
