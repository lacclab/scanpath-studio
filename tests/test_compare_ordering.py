"""CMP-6: ordering of the compare-trial (B) selector candidates."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.tabs import _order_compare_options
from scanpath_studio.utils import SAME_TEXT_MARKER


@pytest.fixture
def trial_words():
    # One line, four words — enough for word-id sequences (the fixations carry
    # their own word_id, so no geometric assignment is needed).
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1"] * 4,
            "word_id": [1, 2, 3, 4],
            "text": ["the", "cat", "sat", "down"],
            "line_idx": [1, 1, 1, 1],
            "x": [100, 200, 300, 400],
            "y": [50, 50, 50, 50],
            "width": [80, 80, 80, 80],
            "height": [40, 40, 40, 40],
        }
    )


def _trial_fix(pid, tid, word_ids, dur=100.0):
    n = len(word_ids)
    return pd.DataFrame(
        {
            "participant_id": [pid] * n,
            "trial_id": [tid] * n,
            "word_id": list(word_ids),
            "x": [140 + 100 * (w - 1) for w in word_ids],
            "y": [70.0] * n,
            "duration_ms": [dur] * n,
            "timestamp_ms": [i * 200 for i in range(n)],
        }
    )


@pytest.fixture
def fixations_pool():
    # Selected trial p1/t1 reads 1-2-3-4. Candidate c-same is identical;
    # c-diff reads backwards; c-long has the most fixations / reading time;
    # c-other is a different text (no 📄 marker in the options below).
    return pd.concat(
        [
            _trial_fix("p1", "t1", [1, 2, 3, 4]),
            _trial_fix("p2", "c-same", [1, 2, 3, 4]),
            _trial_fix("p3", "c-diff", [4, 3, 2, 1, 1, 4]),
            _trial_fix("p4", "c-long", [1, 1, 2, 2, 3, 3, 4, 4], dur=300.0),
            _trial_fix("p5", "c-other", [1, 2]),
        ],
        ignore_index=True,
    )


@pytest.fixture
def options():
    # (participant_id, trial_id, label, markers) — as build_comparison_options
    # returns them; c-other is another text, so it carries no 📄 marker.
    return [
        ("p3", "c-diff", "📄 c-diff", SAME_TEXT_MARKER),
        ("p2", "c-same", "📄 c-same", SAME_TEXT_MARKER),
        ("p4", "c-long", "📄 c-long", SAME_TEXT_MARKER),
        ("p5", "c-other", "c-other", ""),
    ]


def _ids(opts):
    return [o[1] for o in opts]


class TestOrderCompareOptions:
    def test_default_order_is_untouched(self, options, fixations_pool, trial_words):
        ordered, note = _order_compare_options(
            options, "Same text first", fixations_pool, trial_words, "p1", "t1"
        )
        assert ordered == options
        assert note is None

    def test_most_similar_puts_identical_reading_first(
        self, options, fixations_pool, trial_words
    ):
        ordered, note = _order_compare_options(
            options, "Most similar", fixations_pool, trial_words, "p1", "t1"
        )
        assert _ids(ordered)[0] == "c-same"  # NLD 0 — identical sequence
        # The other-text candidate is unscored and stays last.
        assert _ids(ordered)[-1] == "c-other"
        assert note and "NLD" in note

    def test_most_different_reverses_the_scored_group(
        self, options, fixations_pool, trial_words
    ):
        ordered, _ = _order_compare_options(
            options, "Most different", fixations_pool, trial_words, "p1", "t1"
        )
        scored = [t for t in _ids(ordered) if t != "c-other"]
        assert scored[0] != "c-same"
        assert scored[-1] == "c-same"
        assert _ids(ordered)[-1] == "c-other"

    def test_most_fixations_and_longest_reading(
        self, options, fixations_pool, trial_words
    ):
        by_count, _ = _order_compare_options(
            options, "Most fixations", fixations_pool, trial_words, "p1", "t1"
        )
        assert _ids(by_count)[0] == "c-long"  # 8 fixations
        by_time, _ = _order_compare_options(
            options, "Longest reading", fixations_pool, trial_words, "p1", "t1"
        )
        assert _ids(by_time)[0] == "c-long"  # 8 × 300 ms

    def test_two_options_pass_through(self, fixations_pool, trial_words):
        short = [
            ("p2", "c-same", "📄 c-same", SAME_TEXT_MARKER),
            ("p3", "c-diff", "📄 c-diff", SAME_TEXT_MARKER),
        ]
        ordered, note = _order_compare_options(
            short, "Most similar", fixations_pool, trial_words, "p1", "t1"
        )
        # len < 2 guard doesn't apply (2 options), so ordering still runs;
        # identical reading leads either way.
        assert _ids(ordered)[0] == "c-same"
