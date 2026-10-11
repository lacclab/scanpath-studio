"""Scanpath B survives a refresh, as scanpath A does.

A refresh is a new session, restored from the recovery cache. A's trial
(`single_trial_id`) was in the cache; B's was not, so a refresh in Compare
kept A and swapped B for the first candidate. B is remembered by identity
(CMP-13's `_compare_selected_identity`) and, with its dataset (`cmp_dataset`),
now goes into the cache too.
"""

from __future__ import annotations

import pytest

from scanpath_studio.persistence import restore_state, save_state
from scanpath_studio.session_keys import (
    COMPARE_IDENTITY_STATE_KEY,
    COMPARE_SOURCE_STATE_KEY,
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
