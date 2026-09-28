"""EXP-22 — title / caption patterns can name a table's fields as ``{table.field}``.

The metadata tables' fields (``{trials.font_size}``) and each data table's saved
fields that hold one value per trial (``{fixations.condition}``) join the
pattern vocabulary under their table's name, so two tables' ``font_size`` stay
apart. The plain field names are exactly what they were, and the *Available
fields* list shows the new names under a heading per table, after them.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import metadata as md
from scanpath_studio.export import (
    pattern_error,
    pattern_fields,
    render_pattern,
    table_pattern_fields,
)


def _trial():
    words = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [0, 1, 2],
            "text": ["a", "b", "c"],
            "x": [0.0, 10.0, 20.0],
            "surprisal": [1.0, 2.0, 3.0],  # varies within the trial
            "font_size": [18, 18, 18],  # a recorded, trial-constant column
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"] * 2,
            "trial_id": ["t1"] * 2,
            "x": [1.0, 2.0],
            "duration_ms": [200.0, 250.0],
            "condition": ["gathering", "gathering"],
            "_internal": [1, 1],
        }
    )
    return words, fixations


_ROWS = {"trials": {"font_size": 24, "block": 3}, "participants": {"age": 31}}


class TestTheQualifiedFields:
    def test_each_table_names_its_own_fields(self):
        words, fixations = _trial()
        tables = table_pattern_fields(words, fixations, _ROWS)
        assert tables["trials"] == {"trials.font_size": 24, "trials.block": 3}
        assert tables["participants"] == {"participants.age": 31}
        assert tables["fixations"] == {"fixations.condition": "gathering"}
        # A field that varies within the trial has no one value for a title,
        # and the table's identity and geometry are the plain fields' job.
        assert tables["words"] == {"words.font_size": 18}

    def test_the_same_name_in_two_tables_stays_apart(self):
        words, fixations = _trial()
        fields = pattern_fields("p1", "t1", words, fixations, {}, metadata_rows=_ROWS)
        assert render_pattern("{trials.font_size} / {words.font_size}", fields) == (
            "24 / 18"
        )
        assert pattern_error("{trials.font_size}", fields) is None

    def test_the_plain_fields_are_unchanged(self):
        words, fixations = _trial()
        before = pattern_fields("p1", "t1", words, fixations, {})
        after = pattern_fields("p1", "t1", words, fixations, {}, metadata_rows=_ROWS)
        plain = {name for name in after if "." not in name}
        assert plain == {name for name in before if "." not in name}

    def test_an_unattached_table_adds_nothing(self):
        fields = pattern_fields("p1", "t1", pd.DataFrame(), pd.DataFrame(), {})
        assert not any(name.startswith("trials.") for name in fields)


class TestPatternRows:
    def test_a_trial_the_table_does_not_mention_still_names_its_fields(
        self, monkeypatch
    ):
        trials = md.build_trial_metadata(
            pd.DataFrame({"trial_id": ["t1"], "font_size": [24]}),
            trial_column="trial_id",
            source_name="trials.csv",
        )
        monkeypatch.setattr(
            md,
            "attached_for",
            lambda grain, prefix="": trials if grain == md.GRAIN_TRIAL else None,
        )
        assert md.pattern_rows("p1", "t1") == {"trials": {"font_size": 24}}
        assert md.pattern_rows("p1", "t9") == {"trials": {"font_size": None}}


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _help_app():
    import streamlit as st

    from scanpath_studio.controls import render_pattern_help

    render_pattern_help(
        st,
        {"participant_id": 1, "trial_id": 1, "trials.font_size": 24, "words.x": 1},
    )


def test_the_list_heads_each_tables_fields():
    at = streamlit_testing.AppTest.from_function(_help_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    text = at.markdown[0].value
    plain, _, tables = text.partition("**Trials table**")
    assert "{participant_id}" in plain and "{trials.font_size}" not in plain
    assert "{trials.font_size}" in tables
    # Only the known tables are grouped; any other dotted name stays plain.
    assert "{words.x}" in text and "**AOI table**" in text


def _share_app():
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    st.session_state["global_show_title_caption"] = True
    st.session_state["global_title_pattern"] = st.session_state["_pattern"]
    _query, caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_caveats"] = caveats


@pytest.mark.parametrize(
    ("pattern", "warned"),
    [("{trials.font_size}", True), ("{trial_id}", False)],
)
def test_the_link_says_a_metadata_field_does_not_travel(pattern, warned):
    at = streamlit_testing.AppTest.from_function(_share_app)
    at.session_state["_pattern"] = pattern
    at.run(timeout=30)
    assert not at.exception, at.exception
    said = any("Metadata tables" in c for c in at.session_state["_caveats"])
    assert said is warned
