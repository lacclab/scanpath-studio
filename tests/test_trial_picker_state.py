"""#374 — the Scanpath trial picker keeps its trial.

F10: annotating a trial renamed its option in the picker (★ 🏷️ 📝 marks), and
the browser, which names the picked option by its label, still held the label
from before. The next rerun matched nothing and the view fell back to trial 1,
so the next note was typed into trial 1.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

pytestmark = pytest.mark.timeout(180)

TRIAL_KEY = "single_trial_id"


def _boot():
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.run()
    assert not at.exception
    return at


def _picker(at):
    return at.selectbox(key=TRIAL_KEY)


def test_the_browser_is_told_the_current_label_every_run():
    """The label the browser holds must be this run's, marks included, so the
    next run can read it back whatever the annotations did meanwhile."""
    at = _boot()
    for _ in range(3):
        at.button(key="single_next_trial").click().run()
    trial = _picker(at).value
    star = next(c for c in at.checkbox if c.key and c.key.startswith("annotrial_star_"))
    star.check().run()
    at.run()  # a rerun that touches nothing
    picker = _picker(at)
    assert picker.value == trial
    assert picker.proto.set_value
    assert "★" in picker.proto.raw_value
    assert picker.proto.raw_value == picker.format_func(trial)


def test_switching_datasets_away_and_back_restores_the_trial():
    """F34: Dataset → another → back lands on the trial you left, not trial 1."""
    from scanpath_studio.constants import DEMO_CHOICE

    at = _boot()
    for _ in range(3):
        at.button(key="single_next_trial").click().run()
    trial = _picker(at).value
    picker = at.selectbox(key="data_source_picker")
    assert picker.value == DEMO_CHOICE
    other = next(i for i, o in enumerate(picker.options) if "Hand-drawn" in o)
    picker.select_index(other).run()
    assert not at.exception
    assert at.selectbox(key="data_source_picker").value != DEMO_CHOICE
    at.selectbox(key="data_source_picker").select_index(0).run()
    assert not at.exception
    assert _picker(at).value == trial


def _two_dataset_picker_app():
    """The picker alone, over two datasets that reuse the same trial ids."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.annotations import OWNER_KEY
    from scanpath_studio.utils import select_trial

    st.session_state[OWNER_KEY] = st.session_state.get("_test_dataset", "A")
    combos = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1"],
            "trial_id": ["t1", "t2", "t3"],
            "text_id": ["x1", "x2", "x3"],
        }
    )
    select_trial(combos, key_prefix="single")


def test_a_link_naming_the_remembered_trial_is_not_overridden():
    """A link that switches dataset and names a trial whose id equals the one
    remembered for the dataset left behind still opens that trial."""
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_function(_two_dataset_picker_app)
    at.run()
    at.session_state["single_trial_id"] = "t3"
    at.run()  # dataset A remembers t3
    at.session_state["_test_dataset"] = "B"
    at.session_state["single_trial_id"] = "t2"
    at.run()  # dataset B remembers t2
    # A link back to A that names t2 — the id B was left on.
    at.session_state["_test_dataset"] = "A"
    at.session_state["single_trial_id"] = "t2"
    at.session_state["_single_trial_chosen"] = "t2"
    at.run()
    assert not at.exception
    assert at.session_state["single_trial_id"] == "t2"
