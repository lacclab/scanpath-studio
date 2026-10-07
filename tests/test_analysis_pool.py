"""UX-198 — Corpus Analysis names the pool it reads and the filters behind it.

The trial filters set on the Scanpath view narrow Corpus Analysis too; before
this the page said neither how far nor why. The pure parts (the count line and
the filter descriptions) are tested as units, and one ``AppTest`` flow pins the
bar on the bundled demo: 2 readers × 12 trials.
"""

from __future__ import annotations

import pytest

from scanpath_studio.controls import (
    active_filter_keys,
    describe_filter_keys,
    format_filter_item,
)
from scanpath_studio.tabs import pool_count_text
from tests.conftest import APP_SCRIPT, pin_view


class TestPoolCountText:
    def test_a_narrowed_pool_reads_against_the_dataset(self):
        assert pool_count_text(12, 24, 1, 2) == "12 of 24 trials · 1 of 2 participants"

    def test_a_whole_pool_is_just_its_counts(self):
        assert pool_count_text(24, 24, 2, 2) == "24 trials · 2 participants"

    def test_both_halves_say_of_once_either_narrows(self):
        assert pool_count_text(12, 24, 2, 2) == "12 of 24 trials · 2 of 2 participants"

    def test_no_reader_column_leaves_readers_out(self):
        assert pool_count_text(1, 1, 0, 0) == "1 trial"


class TestFilterDescriptions:
    def test_keys_follow_the_result_in_panel_order(self):
        result = {
            "participants": ["p1"],
            "participant_filter_keys": ("filter_meta_language",),
            "metadata": {"difficulty_level": {"Adv"}},
            "metadata_keys": {
                "difficulty_level": "filter_difficulty_level",
                "TRIAL_INDEX": "filter_TRIAL_INDEX_range",
            },
            "favorites_only": True,
            "required_tags": ["good"],
            "excluded_tags": [],
        }
        assert active_filter_keys(result) == [
            "filter_participants",
            "filter_meta_language",
            "filter_difficulty_level",
            "filter_TRIAL_INDEX_range",
            "filter_favorites",
            "filter_req_tags",
        ]

    def test_no_constraint_lists_nothing(self):
        assert active_filter_keys({"participants": None}) == []

    def test_values_ranges_and_flags(self):
        items = describe_filter_keys(
            [
                "filter_participants",
                "filter_TRIAL_INDEX_range",
                "filter_favorites",
                "filter_text_id",
            ],
            {
                "filter_participants": ["p1"],
                "filter_TRIAL_INDEX_range": (3, 10),
                "filter_favorites": True,
                # An emptied multiselect no longer narrows — not listed.
                "filter_text_id": [],
            },
            lambda key: key.removeprefix("filter_"),
        )
        assert items == [
            {"field": "participants", "values": ["p1"]},
            {"field": "TRIAL_INDEX_range", "range": [3.0, 10.0], "unknown": "kept"},
            {"field": "favorites"},
        ]

    def test_a_range_names_what_it_does_with_unknown_values(self):
        """Keep unknown values off: the range item says so, and a constant
        field — no range to slide — is listed by that choice alone."""
        items = describe_filter_keys(
            ["filter_score_range", "filter_trialmeta_level"],
            {
                "filter_score_range": (80, 100),
                "filter_keepunknown_score_range": False,
                "filter_keepunknown_trialmeta_level": False,
            },
            lambda key: key.removeprefix("filter_"),
        )
        assert items == [
            {"field": "score_range", "range": [80.0, 100.0], "unknown": "excluded"},
            {"field": "trialmeta_level", "unknown": "excluded"},
        ]
        assert format_filter_item(items[0]) == (
            "score_range: 80–100 (unknown values excluded)"
        )
        assert format_filter_item(items[1]) == (
            "trialmeta_level: unknown values excluded"
        )

    def test_a_two_value_categorical_list_is_not_a_range(self):
        items = describe_filter_keys(
            ["filter_session"], {"filter_session": [1, 2]}, lambda k: "Session"
        )
        assert items == [{"field": "Session", "values": ["1", "2"]}]

    def test_formatting(self):
        assert format_filter_item({"field": "Participant", "values": ["p1"]}) == (
            "Participant: p1"
        )
        assert format_filter_item({"field": "Trial index", "range": [3.0, 10.5]}) == (
            "Trial index: 3–10.5"
        )
        assert format_filter_item({"field": "Favorites only"}) == "Favorites only"
        assert (
            format_filter_item({"field": "Text", "values": list("abcde")})
            == "Text: a, b, c +2 more"
        )


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _pool_line(at) -> str:
    bar = [m.value for m in at.markdown if "trials" in m.value and m.value[:2] == "**"]
    assert bar, "the analysis-pool line was not drawn"
    return bar[0]


@pytest.mark.timeout(180)
def test_corpus_analysis_names_the_filtered_pool_and_clears_it():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    reader = "l7_1090"
    # Set on the Scanpath view, where the filter panel publishes the result
    # `app.main` filters with on the following run.
    at.session_state["filter_participants"] = [reader]
    at.run(timeout=90)

    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    assert not at.exception, at.exception
    line = _pool_line(at)
    assert line.startswith("**12 of 24 trials · 1 of 2 participants**")
    assert "Participant: l7\\_1090" in line
    # The Scanpath funnel's own panel, under the same keys.
    assert at.multiselect(key="filter_participants").value == [reader]
    clear = at.button(key="corpus_pool_clear")
    assert not clear.disabled

    clear.click()
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert _pool_line(at) == "**24 trials · 2 participants** · no filters"
    assert at.button(key="corpus_pool_clear").disabled
    assert at.session_state["_trial_filters"]["participants"] is None


@pytest.mark.timeout(240)
def test_a_cleared_filter_stays_cleared_across_views():
    """Clear on the pool line must not come back on the next view."""
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    at.session_state["filter_participants"] = ["l7_1090"]
    at.run(timeout=90)
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    at.button(key="corpus_pool_clear").click()
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    for view in ("Data", "Scanpath", "Corpus Analysis"):
        pin_view(at, view)
        at.run(timeout=90)
        assert not at.exception, at.exception
    assert _pool_line(at) == "**24 trials · 2 participants** · no filters"
