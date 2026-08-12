"""CMP-13: one ◀ ▶ that advances both compared trials.

The link is "advance both", not "keep them aligned" — the two pools have
different sizes, so the tests here pin the *increment* semantics (same ±1 on each
side, each clamped on its own) rather than any relationship between the two
positions.
"""

from __future__ import annotations

import pytest
import streamlit as st

from scanpath_studio import utils
from scanpath_studio.session_keys import PENDING_COMPARE_STATE_KEY


@pytest.fixture(autouse=True)
def clean_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


class TestStepWithin:
    def test_moves_one_place(self):
        st.session_state["k"] = "b"
        assert utils.step_within(["a", "b", "c"], "k", 1) == 2
        assert st.session_state["k"] == "c"

    def test_clamps_at_each_end(self):
        st.session_state["k"] = "c"
        assert utils.step_within(["a", "b", "c"], "k", 1) == 2
        assert st.session_state["k"] == "c"
        st.session_state["k"] = "a"
        utils.step_within(["a", "b", "c"], "k", -1)
        assert st.session_state["k"] == "a"

    def test_an_unknown_selection_starts_from_the_top(self):
        st.session_state["k"] = "gone"
        utils.step_within(["a", "b", "c"], "k", 1)
        assert st.session_state["k"] == "b"

    def test_an_empty_list_is_a_no_op(self):
        assert utils.step_within([], "k", 1) is None
        assert "k" not in st.session_state


class TestAtListEnd:
    def test_reports_each_end(self):
        st.session_state["k"] = "a"
        assert utils.at_list_end(["a", "b"], "k", -1) is True
        assert utils.at_list_end(["a", "b"], "k", 1) is False

    def test_an_unknown_list_answers_false_so_the_button_stays_live(self):
        """A click that turns out to be a no-op beats a button greyed out while
        the other scanpath could still move."""
        st.session_state["k"] = "a"
        assert utils.at_list_end([], "k", 1) is False
        st.session_state["k"] = "not in the list"
        assert utils.at_list_end(["a", "b"], "k", 1) is False


class TestTheLinkIsArmedOnlyInCompareMode:
    def test_needs_both_the_toggle_and_the_checkbox(self):
        assert utils.compare_step_linked() is False
        st.session_state[utils.COMPARE_STEP_LINK_KEY] = True
        # Streamlit drops the checkbox's key only at end-of-run, so a stale True
        # must not steer the main picker once compare mode is off.
        assert utils.compare_step_linked() is False
        st.session_state["single_compare_toggle"] = True
        assert utils.compare_step_linked() is True


class TestSteppingBWritesAnIdentity:
    """B's labels are rebuilt relative to A (📄 / 👤 markers, and the ordering),
    so once A moves, neither B's index nor its label names the same trial. The
    step therefore parks the *identity* in the pending slot the `?compare=` deep
    link already uses, and the rebuilt picker re-finds it."""

    def test_it_parks_the_next_candidates_identity(self):
        st.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY] = [
            ("📄 t1", "p1", "t1"),
            ("📄 t2", "p2", "t2"),
            ("t3", "p3", "t3"),
        ]
        st.session_state[utils.COMPARE_TRIAL_KEY] = "📄 t2"
        utils.step_linked_compare(1)
        assert st.session_state[PENDING_COMPARE_STATE_KEY] == {
            "participant_id": "p3",
            "trial_id": "t3",
        }

    def test_b_stays_put_at_the_end_of_its_own_list(self):
        """Settled call (3): no clamping of the *pair* — the side that has run
        out simply stops while the other keeps stepping."""
        st.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY] = [
            ("t1", "p1", "t1"),
            ("t2", "p2", "t2"),
        ]
        st.session_state[utils.COMPARE_TRIAL_KEY] = "t2"
        utils.step_linked_compare(1)
        assert st.session_state[PENDING_COMPARE_STATE_KEY] == {
            "participant_id": "p2",
            "trial_id": "t2",
        }

    def test_no_snapshot_is_a_no_op(self):
        utils.step_linked_compare(1)
        assert PENDING_COMPARE_STATE_KEY not in st.session_state


@pytest.mark.timeout(180)
class TestTheLinkedStepEndToEnd:
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

    def test_the_checkbox_is_offered_in_compare_options(self):
        at = self._boot_compare()
        boxes = [c for c in at.checkbox if c.key == utils.COMPARE_STEP_LINK_KEY]
        assert boxes, "the 'Step both trials together' checkbox is missing"
        assert boxes[0].value is False, "the link must default off"

    @staticmethod
    def _compare_identity(at):
        """B's *identity*, not its label. The label is rebuilt relative to A."""
        compare = at.session_state["_share_selection"]["compare"]
        return (str(compare["participant_id"]), str(compare["trial_id"]))

    @staticmethod
    def _next_candidate(at, delta=1):
        """The candidate one place along in the list as currently rendered."""
        snapshot = at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY]
        labels = [row[0] for row in snapshot]
        pos = labels.index(at.session_state[utils.COMPARE_TRIAL_KEY])
        row = snapshot[max(0, min(pos + delta, len(snapshot) - 1))]
        return (row[1], row[2])

    def test_linked_the_main_step_moves_both(self):
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        assert not at.exception, at.exception
        before_a = at.session_state["single_trial_id"]
        expected_b = self._next_candidate(at)

        at.button(key="single_next_trial").click().run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["single_trial_id"] != before_a
        # The identity resolved against the pre-step list — which is the whole
        # point: after A moved, B's list is re-ordered and re-labelled, so an
        # index or a label would have named a different trial.
        assert self._compare_identity(at) == expected_b

    def test_the_link_works_from_the_compare_pickers_arrows_too(self):
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        options = at.session_state[utils.trial_options_snapshot_key("single")]
        expected_a = options[options.index(at.session_state["single_trial_id"]) + 1]

        at.button(key="single_compare_next").click().run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["single_trial_id"] == expected_a
