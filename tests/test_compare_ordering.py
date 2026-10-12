"""CMP-6/CMP-10: comparison picker sorting mirrors the main trial picker."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.tabs import _CMP_SORT_DEFAULT, _order_compare_options
from scanpath_studio.utils import SAME_TEXT_MARKER, TRIAL_SORT_DEFAULT, reading_key


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
    # Keyed by reading, as `trial_sort_keys` gives them (#412).
    diff, same, long = (
        reading_key("p3", "c-diff"),
        reading_key("p2", "c-same"),
        reading_key("p4", "c-long"),
    )
    return {
        "Fixations (n)": pd.Series(
            {diff: 6, same: 4, long: 8, reading_key("p5", "c-other"): 2}
        ),
        # Missing values must remain last even for a descending sort.
        "Reading time (s)": pd.Series({diff: 1.2, same: 0.8, long: 3.5}),
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

    def test_readers_of_one_trial_id_sort_by_their_own_values(self):
        """#412: B's candidates are readings, so a shared id is two of them."""
        options = [("p1", "t", "t [p1]", ""), ("p2", "t", "t [p2]", "")]
        keys = {"n": pd.Series({reading_key("p1", "t"): 5, reading_key("p2", "t"): 1})}
        ordered = _order_compare_options(options, "n", keys)
        assert [option[0] for option in ordered] == ["p2", "p1"]

    def test_single_candidate_is_untouched(self, options, sort_keys):
        assert (
            _order_compare_options(
                options[:1], "Fixations (n)", sort_keys, descending=True
            )
            == options[:1]
        )


def test_comparison_labels_stay_unique_when_the_qualified_form_is_taken():
    """Round 11 #6: ``x [p2]`` as a real trial id must not swallow p2's ``x``."""
    import pandas as pd

    from scanpath_studio.utils import build_comparison_options

    combos = pd.DataFrame(
        [
            {"participant_id": "p1", "trial_id": "x [p2]", "text_id": "a"},
            {"participant_id": "p1", "trial_id": "x", "text_id": "b"},
            {"participant_id": "p2", "trial_id": "x", "text_id": "c"},
            {"participant_id": "p2", "trial_id": "x [p2]", "text_id": "d"},
            {"participant_id": "p3", "trial_id": "x [p2] (2)", "text_id": "e"},
        ]
    )
    options = build_comparison_options(
        combos,
        "All trials",
        primary_participant="primary",
        primary_trial="primary",
        primary_text="primary",
    )
    labels = [opt[2] for opt in options]
    assert len(set(labels)) == len(options)
    label_to_trial = {opt[2]: (opt[0], opt[1]) for opt in options}
    assert set(label_to_trial.values()) == {
        (p, t)
        for p, t in combos[["participant_id", "trial_id"]].itertuples(index=False)
    }


def test_friendly_labels_stay_unique():
    from scanpath_studio.utils import friendly_trial_label

    used: set[str] = set()
    labels = [
        friendly_trial_label("p", "t", None, used),
        friendly_trial_label("p", "t", None, used),
        friendly_trial_label("p", "t", None, used),
    ]
    assert len(set(labels)) == 3
