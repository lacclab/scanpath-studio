"""CMP-6/CMP-10: comparison picker sorting mirrors the main trial picker."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.tabs import _CMP_SORT_DEFAULT, _order_compare_options
from scanpath_studio.utils import SAME_TEXT_MARKER, TRIAL_SORT_DEFAULT


@pytest.fixture
def options():
    # build_comparison_options already puts related trials first. Deliberately
    # leave the ids out of alphabetical/stat order so each sort is observable.
    return [
        ("p3", "c-diff", "📄 c-diff", SAME_TEXT_MARKER),
        ("p2", "c-same", "📄 c-same", SAME_TEXT_MARKER),
        ("p4", "c-long", "📄 c-long", SAME_TEXT_MARKER),
        ("p5", "c-other", "c-other", ""),
    ]


@pytest.fixture
def sort_keys():
    return {
        "Fixations (n)": pd.Series(
            {"c-diff": 6, "c-same": 4, "c-long": 8, "c-other": 2}
        ),
        # Missing values must remain last even for a descending sort.
        "Reading time (s)": pd.Series({"c-diff": 1.2, "c-same": 0.8, "c-long": 3.5}),
    }


def _ids(ordered):
    return [option[1] for option in ordered]


class TestOrderCompareOptions:
    def test_relation_default_preserves_candidate_priority(self, options, sort_keys):
        ordered = _order_compare_options(options, _CMP_SORT_DEFAULT, sort_keys)
        assert ordered == options

    def test_trial_id_matches_the_main_picker_default(self, options, sort_keys):
        ordered = _order_compare_options(options, TRIAL_SORT_DEFAULT, sort_keys)
        assert _ids(ordered) == ["c-diff", "c-long", "c-other", "c-same"]

    def test_generated_stat_key_sorts_ascending_or_descending(self, options, sort_keys):
        ascending = _order_compare_options(options, "Fixations (n)", sort_keys)
        descending = _order_compare_options(
            options, "Fixations (n)", sort_keys, descending=True
        )
        assert _ids(ascending) == ["c-other", "c-same", "c-diff", "c-long"]
        assert _ids(descending) == ["c-long", "c-diff", "c-same", "c-other"]

    def test_unranked_trial_stays_last_when_descending(self, options, sort_keys):
        ordered = _order_compare_options(
            options, "Reading time (s)", sort_keys, descending=True
        )
        assert _ids(ordered) == ["c-long", "c-diff", "c-same", "c-other"]

    def test_single_candidate_is_untouched(self, options, sort_keys):
        assert (
            _order_compare_options(
                options[:1], "Fixations (n)", sort_keys, descending=True
            )
            == options[:1]
        )
