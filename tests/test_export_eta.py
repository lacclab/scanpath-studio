"""Telling the user how long an export still has (PERF-6).

A bulk export over OneStop is a job measured in hours — ~0.7 s a trial across
20,000 trials. "1,203 / 20,000" answers *where* it is; it does not answer the
only question anyone actually has, which is whether to wait or go to lunch.
"""

from __future__ import annotations

import pytest

from scanpath_studio.export_status import (
    ExportStage,
    ExportStatus,
    format_duration,
    progress_caption,
)


def _status(completed, total, elapsed):
    return ExportStatus(
        stage=ExportStage.RASTERIZING,
        message="Rendering figures",
        completed=completed,
        total=total,
        elapsed_s=elapsed,
    )


class TestRemaining:
    def test_estimates_from_the_rate_so_far(self):
        # 10 of 100 trials in 20 s -> 2 s each -> 180 s left.
        assert _status(10, 100, 20.0).remaining_s == pytest.approx(180.0)

    def test_is_unknown_before_the_first_trial_finishes(self):
        """Dividing by zero completed trials would invent a number."""
        assert _status(0, 100, 5.0).remaining_s is None

    def test_is_zero_when_everything_is_done(self):
        assert _status(100, 100, 200.0).remaining_s == pytest.approx(0.0)

    def test_is_unknown_without_counts(self):
        assert ExportStatus(ExportStage.PREPARING, "Preparing").remaining_s is None

    def test_is_unknown_without_a_clock(self):
        assert _status(10, 100, 0.0).remaining_s is None

    def test_rate_is_trials_per_second(self):
        assert _status(10, 100, 20.0).rate_per_s == pytest.approx(0.5)


class TestFormatDuration:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0.4, "under a second"),
            (9.0, "9s"),
            (75.0, "1m 15s"),
            (3600.0, "1h 0m"),
            (8130.0, "2h 15m"),
        ],
    )
    def test_reads_as_a_person_would_say_it(self, seconds, expected):
        assert format_duration(seconds) == expected


class TestProgressCaption:
    def test_names_the_count_the_rate_and_the_time_left(self):
        caption = progress_caption(_status(10, 100, 20.0))
        assert "10/100" in caption
        assert "0.5/s" in caption
        assert "3m 0s left" in caption

    def test_thousands_are_grouped(self):
        """Six digits of trials is exactly when a bare number stops being read."""
        assert "1,203/20,000" in progress_caption(_status(1203, 20000, 600.0))

    def test_omits_the_estimate_until_there_is_one(self):
        caption = progress_caption(_status(0, 100, 5.0))
        assert "left" not in caption
        assert "0/100" in caption

    def test_says_finishing_rather_than_zero_left(self):
        assert "finishing" in progress_caption(_status(100, 100, 50.0)).lower()
