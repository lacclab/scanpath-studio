"""Tests for trial-level filtering helpers in data.py."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.data import filter_to_keys, filter_trials

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _words():
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["a", "b", "a", "b"],
            "question_preview": [True, False, True, False],
            "difficulty_level": ["Adv", "Ele", "Adv", "Ele"],
        }
    )


def _fixations():
    # Two fixations per trial.
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p1", "p2", "p2", "p2", "p2"],
            "trial_id": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "question_preview": [True, True, False, False, True, True, False, False],
            "difficulty_level": [
                "Adv",
                "Adv",
                "Ele",
                "Ele",
                "Adv",
                "Adv",
                "Ele",
                "Ele",
            ],
        }
    )


def test_filter_trials_by_participant():
    w, f = filter_trials(_words(), _fixations(), participants=["p1"])
    assert set(w["participant_id"]) == {"p1"}
    assert set(f["participant_id"]) == {"p1"}


def test_filter_trials_by_metadata_hunting():
    # question_preview True == Hunting.
    w, f = filter_trials(_words(), _fixations(), metadata={"question_preview": {True}})
    assert set(w["trial_id"]) == {"a"}  # only the Hunting trials
    assert set(f["trial_id"]) == {"a"}
    assert (w["question_preview"]).all()


def test_filter_trials_combined():
    w, f = filter_trials(
        _words(),
        _fixations(),
        participants=["p2"],
        metadata={"difficulty_level": {"Ele"}},
    )
    assert set(zip(w["participant_id"], w["trial_id"])) == {("p2", "b")}
    assert set(zip(f["participant_id"], f["trial_id"])) == {("p2", "b")}


def test_filter_trials_noop_when_empty_selection():
    w, f = filter_trials(_words(), _fixations(), participants=None, metadata={})
    assert len(w) == 4 and len(f) == 8


def test_filter_to_keys():
    keep = {("p1", "a"), ("p2", "b")}
    w, f = filter_to_keys(_words(), _fixations(), keep)
    assert set(zip(w["participant_id"], w["trial_id"])) == keep
    assert set(zip(f["participant_id"], f["trial_id"])) == keep


# -----------------------------------------------------------------------------
# CMP-8 §5.2 — the filter layer is prefix-scoped, so compare mode's scanpath B
# can be narrowed on its own dataset's columns without disturbing A.
# -----------------------------------------------------------------------------


def _filter_prefix_app():
    """Populate two independent filter sets, then clear only the default one."""
    import streamlit as st

    from scanpath_studio.controls import clear_trial_filters

    st.session_state["filter_participants"] = ["p1"]
    st.session_state["filter_text_id"] = ["t1"]
    st.session_state["_trial_filters"] = {"participants": ["p1"]}
    st.session_state["cmpfilter_participants"] = ["reader_03"]
    st.session_state["cmpfilter_text_id"] = ["potec_b0"]
    st.session_state["cmp_trial_filters"] = {"participants": ["reader_03"]}

    clear_trial_filters()  # A's "Clear all filters"
    st.session_state["_after_clear_a"] = {
        k: v for k, v in st.session_state.items() if "filter_" in str(k)
    }


def test_clearing_one_prefix_leaves_the_other_alone():
    """The sweep used to match every key starting with ``filter_``.

    ``"filter_"`` is a prefix of ``"cmpfilter_"`` in one direction only, so a
    naive forward match is fine for ``cmp`` and catastrophic for the default
    prefix: clearing A's filters would silently wipe B's too.
    """
    at = AppTest.from_function(_filter_prefix_app)
    at.run()
    assert not at.exception, at.exception
    remaining = at.session_state["_after_clear_a"]
    # A is gone...
    assert "filter_participants" not in remaining
    assert "filter_text_id" not in remaining
    # ...and B is untouched.
    assert remaining["cmpfilter_participants"] == ["reader_03"]
    assert remaining["cmpfilter_text_id"] == ["potec_b0"]
    assert at.session_state["cmp_trial_filters"] == {"participants": ["reader_03"]}
    assert "_trial_filters" not in at.session_state


def _filter_prefix_clear_b_app():
    import streamlit as st

    from scanpath_studio.controls import clear_trial_filters

    st.session_state["filter_participants"] = ["p1"]
    st.session_state["cmpfilter_participants"] = ["reader_03"]
    clear_trial_filters("cmp")
    st.session_state["_remaining"] = {
        k: v for k, v in st.session_state.items() if "filter_" in str(k)
    }


def test_clearing_the_compare_prefix_leaves_the_main_pool_alone():
    at = AppTest.from_function(_filter_prefix_clear_b_app)
    at.run()
    assert not at.exception, at.exception
    remaining = at.session_state["_remaining"]
    assert remaining["filter_participants"] == ["p1"]
    assert "cmpfilter_participants" not in remaining


def _metadata_keys_app():
    """`metadata_keys` must come back already-prefixed (UX-7's per-filter clear
    pops exactly the key it is given, so an unprefixed one silently no-ops)."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import _compute_trial_filters

    words = pd.DataFrame(
        {"participant_id": ["p1", "p2"], "text_id": ["t1", "t2"], "word_id": [0, 1]}
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "trial_id": ["a", "b"],
            "text_id": ["t1", "t2"],
            "x": [1.0, 2.0],
            "y": [1.0, 2.0],
            "duration_ms": [100, 100],
        }
    )
    st.session_state["cmpfilter_text_id"] = ["t1"]
    st.session_state["_result"] = _compute_trial_filters(words, fixations, prefix="cmp")


def test_metadata_keys_are_emitted_already_prefixed():
    at = AppTest.from_function(_metadata_keys_app)
    at.run()
    assert not at.exception, at.exception
    keys = at.session_state["_result"]["metadata_keys"]
    assert set(keys.values()) == {"cmpfilter_text_id"}
