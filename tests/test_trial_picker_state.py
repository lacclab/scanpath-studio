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
