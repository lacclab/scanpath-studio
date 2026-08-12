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

    def test_stepping_the_main_trial_does_not_skip_the_compared_one(self):
        """The reported bug: B "suddenly skips to a different trial".

        B's picker is keyed on a *label*, and the labels are rebuilt relative to
        A (📄 same-text / 👤 same-participant markers are computed against the
        selected trial). So the moment A moved to another text, B's stored label
        matched nothing and the picker fell back to the first candidate. B is now
        remembered by identity and its label re-resolved each run.
        """
        at = self._boot_compare()
        before = self._compare_identity(at)
        first_label = at.session_state["single_compare_trial"]
        relabelled = False

        # Walk A several trials — enough to cross a text boundary, which is what
        # re-labels B's pool.
        for _ in range(4):
            at.button(key="single_next_trial").click().run(timeout=90)
            assert not at.exception, at.exception
            after = self._compare_identity(at)
            if after != before:
                raise AssertionError(
                    f"the compared trial changed on its own: {before} → {after}"
                )
            relabelled |= at.session_state["single_compare_trial"] != first_label
        # …and prove the walk actually exercised the failure mode: B kept the
        # same trial while its *label* changed underneath it.
        assert relabelled, "B's label never changed — the regression wasn't exercised"

    def test_a_users_pick_wins_over_the_remembered_identity(self):
        """The other half of the same fix: re-resolving must not undo a fresh
        selection on the next run."""
        at = self._boot_compare()
        picker = at.selectbox(key="single_compare_trial")
        other = next(o for o in picker.options if o != picker.value)
        at = picker.set_value(other).run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["single_compare_trial"] == other

    def test_the_link_works_from_the_compare_pickers_arrows_too(self):
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        options = at.session_state[utils.trial_options_snapshot_key("single")]
        expected_a = options[options.index(at.session_state["single_trial_id"]) + 1]

        at.button(key="single_compare_next").click().run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["single_trial_id"] == expected_a

    # -- CMP-13 follow-up: "still jumps around" ------------------------------
    # Identity stepping was already correct — B landed on the right trial every
    # time. What leapt (10/23 → 22/23 in the report) was its *position*: the
    # default order ranks B's pool relative to A, 📄 same-text first, so A
    # crossing into another text re-lays the whole track. Linking now pins the
    # order to Trial ID, which is the only thing that makes "one notch along"
    # mean anything.

    @staticmethod
    def _compare_position(at):
        snapshot = at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY]
        labels = [row[0] for row in snapshot]
        return labels.index(at.session_state[utils.COMPARE_TRIAL_KEY])

    def test_linked_puts_the_pool_in_trial_id_order(self):
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        assert not at.exception, at.exception
        ids = [row[2] for row in at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY]]
        assert ids == utils.sort_trial_options(ids, None)

    def test_unlinked_the_relation_ranking_still_leads(self):
        """The pin is scoped to linking — 📄-first is what makes B easy to
        *pick*, and it stays the default the rest of the time."""
        at = self._boot_compare()
        first_label = at.session_state[utils.COMPARE_OPTIONS_SNAPSHOT_KEY][0][0]
        assert first_label.startswith(utils.SAME_TEXT_MARKER), first_label

    def test_the_pin_does_not_rewrite_the_users_chosen_sort(self):
        """Same rule as a mode-gated control: resolve, never write back, or
        un-linking would silently leave the user on a sort they never picked."""
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        from scanpath_studio.tabs import _CMP_SORT_DEFAULT

        assert at.session_state["single_compare_order"] == _CMP_SORT_DEFAULT

    def test_bs_position_holds_still_while_a_walks_across_texts(self):
        at = self._boot_compare()
        at.checkbox(key=utils.COMPARE_STEP_LINK_KEY).set_value(True).run(timeout=90)
        before = self._compare_position(at)
        for _ in range(4):
            at.button(key="single_next_trial").click().run(timeout=90)
            assert not at.exception, at.exception
            after = self._compare_position(at)
            # One notch for the linked step, at most one more for A leaving the
            # pool and its predecessor rejoining it. The bug was a leap of 12.
            assert abs(after - before) <= 2, f"B's position jumped {before} → {after}"
            before = after
