"""CMP-22: scanpath B's picker lists every trial, A's own included.

B used to drop the selected trial from its pool, so the two position readouts
counted different lists (1/24 next to 1/23) on the same, unfiltered data. A is
now a candidate like any other; it is only kept from being B's *default*.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import utils

_COMBOS = pd.DataFrame(
    {
        "participant_id": ["p1", "p1", "p2"],
        "trial_id": ["t1", "t2", "t1"],
        "text_id": ["x", "y", "x"],
    }
)


class TestThePoolIncludesTheSelectedTrial:
    def test_by_default_every_trial_is_a_candidate(self):
        options = utils.build_comparison_options(_COMBOS, "None", "p1", "t1", "x")
        assert {(o[0], o[1]) for o in options} == {
            ("p1", "t1"),
            ("p1", "t2"),
            ("p2", "t1"),
        }

    def test_the_selected_trial_keeps_its_relation_markers(self):
        options = utils.build_comparison_options(_COMBOS, "None", "p1", "t1", "x")
        markers = {(o[0], o[1]): o[3] for o in options}
        assert utils.SAME_TEXT_MARKER in markers[("p1", "t1")]
        assert utils.SAME_PARTICIPANT_MARKER in markers[("p1", "t1")]

    def test_include_primary_false_answers_is_there_anything_else(self):
        """The Compare gate's question — one trial compared with itself is not a
        comparison, so a single-trial pool must still read as empty there."""
        only = _COMBOS.iloc[[0]]
        assert utils.build_comparison_options(only, "None", "p1", "t1", "x")
        assert not utils.build_comparison_options(
            only, "None", "p1", "t1", "x", include_primary=False
        )


@pytest.mark.timeout(180)
class TestThePickerEndToEnd:
    """Driven through the real widgets on the bundled demo."""

    @staticmethod
    def _boot_compare():
        from tests.conftest import APP_SCRIPT

        streamlit_testing = pytest.importorskip("streamlit.testing.v1")
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.session_state["single_compare_toggle"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        return at

    @staticmethod
    def _a_identity(at):
        selection = at.session_state["_share_selection"]
        return (str(selection["participant_id"]), str(selection["trial_id"]))

    @staticmethod
    def _b_identity(at):
        compare = at.session_state["_share_selection"]["compare"]
        return (str(compare["participant_id"]), str(compare["trial_id"]))

    def test_a_and_b_count_the_same_trials(self):
        at = self._boot_compare()
        a_trials = at.session_state[utils.trial_options_snapshot_key("single")]
        b_rows = at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY]
        assert len(b_rows) == len(a_trials)
        assert self._a_identity(at) in {(row[1], row[2]) for row in b_rows}

    def test_b_does_not_default_to_a(self):
        at = self._boot_compare()
        assert self._b_identity(at) != self._a_identity(at)

    def test_b_can_be_set_to_a_itself(self):
        at = self._boot_compare()
        a_identity = self._a_identity(at)
        label = next(
            row[0]
            for row in at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY]
            if (row[1], row[2]) == a_identity
        )
        at.selectbox(key=utils.COMPARE_TRIAL_KEY).set_value(label).run(timeout=90)
        assert not at.exception, at.exception
        assert self._b_identity(at) == a_identity
