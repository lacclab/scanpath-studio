"""Scanpath B survives a refresh, as scanpath A does.

A refresh is a new session, restored from the recovery cache. A's trial
(`single_trial_id`) goes into the cache, and so does B's: B is remembered by
identity (`_compare_selected_identity`) together with its dataset
(`cmp_dataset`), so a refresh in Compare keeps B rather than swapping it for
the first candidate.
"""

from __future__ import annotations

import pytest

from scanpath_studio.persistence import restore_state, save_state
from scanpath_studio.session_keys import (
    COMPARE_IDENTITY_STATE_KEY,
    COMPARE_SOURCE_STATE_KEY,
    SINGLE_COMPARE_SCREEN_ID,
    SINGLE_SCREEN_ID,
)


def test_bs_trial_and_dataset_round_trip_through_the_cache(tmp_path):
    session = {
        COMPARE_SOURCE_STATE_KEY: "Bundled Demo",
        COMPARE_IDENTITY_STATE_KEY: ("p7", "t3"),
    }
    assert save_state(session, tmp_path)
    restored: dict = {}
    assert restore_state(restored, tmp_path)
    assert restored[COMPARE_SOURCE_STATE_KEY] == "Bundled Demo"
    assert restored[COMPARE_IDENTITY_STATE_KEY] == ("p7", "t3")


def test_both_screens_round_trip_through_the_cache(tmp_path):
    """On a trial recorded over several screens, a refresh keeps A's and B's
    screens too, rather than sending both back to screen 1."""
    session = {SINGLE_SCREEN_ID: "page_3", SINGLE_COMPARE_SCREEN_ID: "question_7"}
    assert save_state(session, tmp_path)
    restored: dict = {}
    assert restore_state(restored, tmp_path)
    assert restored[SINGLE_SCREEN_ID] == "page_3"
    assert restored[SINGLE_COMPARE_SCREEN_ID] == "question_7"


def test_a_malformed_identity_is_dropped(tmp_path):
    assert save_state({COMPARE_IDENTITY_STATE_KEY: ["only one"]}, tmp_path)
    restored: dict = {}
    restore_state(restored, tmp_path)
    assert COMPARE_IDENTITY_STATE_KEY not in restored


@pytest.mark.timeout(240)
def test_a_refresh_keeps_the_compared_trial(tmp_path):
    from tests.conftest import APP_SCRIPT

    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    def identity(at):
        compare = at.session_state["_share_selection"]["compare"]
        return (str(compare["participant_id"]), str(compare["trial_id"]))

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["single_compare_toggle"] = True
    at.run(timeout=90)
    assert not at.exception, at.exception
    default_b = identity(at)
    picker = at.selectbox(key="single_compare_trial")
    other = next(i for i in range(len(picker.options)) if i not in (picker.index, 0))
    at = picker.select_index(other).run(timeout=90)
    assert not at.exception, at.exception
    picked_b = identity(at)
    assert picked_b != default_b

    # The refresh: what the cache keeps, restored into a new session.
    kept = {
        key: at.session_state[key]
        for key in (
            "single_compare_toggle",
            "single_trial_id",
            COMPARE_IDENTITY_STATE_KEY,
        )
    }
    assert save_state(kept, tmp_path)
    restored: dict = {}
    assert restore_state(restored, tmp_path)

    fresh = AppTest.from_file(APP_SCRIPT)
    for key, value in restored.items():
        fresh.session_state[key] = value
    fresh.run(timeout=90)
    assert not fresh.exception, fresh.exception
    assert identity(fresh) == picked_b


def _navigator_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio import tabs

    catalog = pd.DataFrame({"screen_id": ["s1", "s2", "s3"], "screen_index": [1, 2, 3]})
    st.session_state["_picked"] = (
        tabs._render_screen_navigator(catalog),
        tabs._render_screen_navigator(catalog, key_prefix="single_compare"),
    )


@pytest.mark.parametrize(
    ("restored", "shown"),
    [(("s2", "s3"), ("s2", "s3")), (("gone", "s3"), ("s1", "s3"))],
)
def test_the_screen_pickers_open_on_the_restored_screens(restored, shown):
    """A restored screen is the one shown; one the trial does not have falls
    back to its first."""
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    at = AppTest.from_function(_navigator_app)
    at.session_state[SINGLE_SCREEN_ID] = restored[0]
    at.session_state[SINGLE_COMPARE_SCREEN_ID] = restored[1]
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert at.session_state["_picked"] == shown
