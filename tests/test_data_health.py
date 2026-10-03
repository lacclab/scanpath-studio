"""The Data page's *Data checks*: values that parsed but cannot be right.

Negative or zero fixation durations, positions that are not finite numbers
(fixations and raw gaze) and word boxes with no area are counted, quoted and
explained — under the dataset's own column names — and never removed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import scanpath_studio as sps
from scanpath_studio import api
from scanpath_studio.data_health import check_data_health


def _fixations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t1", "t2"],
            "x": [10.0, np.inf, 30.0, 40.0, np.nan],
            "y": [5.0, 5.0, 5.0, -np.inf, 5.0],
            "duration_ms": [200.0, -40.0, 0.0, 180.0, 210.0],
        }
    )


def _words() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [1, 2, 3],
            "x": [0.0, 50.0, 100.0],
            "y": [0.0, 0.0, 0.0],
            "width": [40.0, 0.0, 30.0],
            "height": [20.0, 20.0, -3.0],
        }
    )


def _raw_gaze() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1"] * 4,
            "x": [1.0, np.nan, 3.0, 4.0],
            "y": [1.0, 2.0, np.nan, 4.0],
        }
    )


def _by_check(findings):
    return {f.check: f for f in findings}


class TestChecks:
    def test_durations_of_zero_or_less(self):
        found = _by_check(check_data_health(None, _fixations()))["fixation_duration"]
        assert (found.rows, found.total_rows, found.trials) == (2, 5, 1)
        assert found.breakdown == {"negative": 1, "zero": 1}
        assert [e["duration_ms"] for e in found.examples] == [-40.0, 0.0]
        assert found.examples[0]["participant_id"] == "p1"
        assert found.severity == "warning"

    def test_positions_that_are_not_finite(self):
        found = _by_check(check_data_health(None, _fixations()))["fixation_position"]
        assert (found.rows, found.trials) == (3, 3)
        assert found.breakdown == {"infinite": 2, "missing": 1}
        assert found.columns == ("x", "y")

    def test_word_boxes_with_no_area(self):
        found = _by_check(check_data_health(_words(), None))["word_box_size"]
        assert (found.rows, found.trials) == (2, 1)
        assert found.breakdown == {"width ≤ 0": 1, "height ≤ 0": 1}

    def test_raw_gaze_gaps_are_a_note_and_infinity_a_warning(self):
        found = _by_check(check_data_health(None, None, _raw_gaze()))
        assert found["raw_gaze_position"].severity == "note"
        infinite = _raw_gaze().assign(x=[1.0, np.inf, 3.0, 4.0])
        found = _by_check(check_data_health(None, None, infinite))
        assert found["raw_gaze_position"].severity == "warning"
        assert found["raw_gaze_position"].breakdown == {"infinite": 1, "missing": 1}

    def test_nothing_is_changed_or_dropped(self):
        words, fixations, raw = _words(), _fixations(), _raw_gaze()
        check_data_health(words, fixations, raw)
        pd.testing.assert_frame_equal(words, _words())
        pd.testing.assert_frame_equal(fixations, _fixations())
        pd.testing.assert_frame_equal(raw, _raw_gaze())

    def test_every_finding_says_what_happens_to_its_rows(self):
        findings = check_data_health(_words(), _fixations(), _raw_gaze())
        assert len(findings) == 4
        assert all("stay in" in f.consequence for f in findings)

    def test_the_bundled_demo_is_clean(self):
        words, fixations = api.load_sample_data()
        assert check_data_health(words, fixations, api.load_sample_raw_gaze()) == []

    def test_a_table_without_the_columns_is_not_checked(self):
        assert check_data_health(pd.DataFrame({"a": [1]}), pd.DataFrame()) == []


class TestApi:
    def test_one_row_per_finding(self):
        table = sps.check_data_health(_words(), _fixations(), _raw_gaze())
        assert list(table["check"]) == [
            "fixation_duration",
            "fixation_position",
            "raw_gaze_position",
            "word_box_size",
        ]
        assert table.loc[0, "rows"] == 2 and table.loc[0, "of_rows"] == 5
        assert table.loc[2, "severity"] == "note"

    def test_clean_data_gives_an_empty_table_with_its_columns(self):
        words, fixations = api.load_sample_data()
        table = api.check_data_health(words, fixations)
        assert table.empty
        assert {"table", "check", "rows", "what_happens"} <= set(table.columns)


def _health_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.column_names import ACTIVE_COLUMN_NAMES_KEY
    from scanpath_studio.tabs import render_data_health

    st.session_state[ACTIVE_COLUMN_NAMES_KEY] = {
        "fixations": {
            "duration_ms": {"sources": ["CURRENT_FIX_DURATION"], "kind": "mapped"},
        }
    }
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "x": [1.0, 2.0],
            "y": [1.0, 2.0],
            "duration_ms": [-5.0, 100.0],
        }
    )
    clean = st.query_params.get("clean") == "1"
    if clean:
        fixations["duration_ms"] = [90.0, 100.0]
    render_data_health(pd.DataFrame(), fixations, None)


@pytest.mark.parametrize("clean", [False, True])
def test_the_data_page_names_the_dataset_s_own_columns(clean):
    at = AppTest.from_function(_health_app)
    at.query_params["clean"] = "1" if clean else "0"
    at.run()
    assert not at.exception
    if clean:
        assert not at.warning
        assert any("finite number" in c.value for c in at.caption)
        return
    (warning,) = at.warning
    assert "Fixations lasting 0 ms or less" in warning.value
    assert "1 of 2 fixation rows, in 1 trial (1 negative)" in warning.value
    assert "`CURRENT_FIX_DURATION`" in warning.value
    assert any("Nothing is removed or changed" in c.value for c in at.caption)
