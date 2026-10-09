"""#412 — readers who share a Trial ID are each a trial in the picker.

Many datasets give every reader the same Trial IDs (`1`, `2`, … per session).
The Scanpath picker kept one row per Trial ID, so it offered only the first
reader's reading of each — and a link that named the second reader matched,
then opened the first reader's scanpath under it. Its options and its state
are readings now (``utils.reading_key``); a Trial ID several readers share is
labelled with the reader, and a link or saved selection that names the id
alone says it is ambiguous instead of picking one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.synthetic import make_synthetic_fixations, make_synthetic_words
from scanpath_studio.utils import reading_key, split_reading_key
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

pytestmark = pytest.mark.timeout(240)


def _picker_app() -> None:
    """The probe: two readers of one Trial ID, and a link to the second."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _match_selection, _restore_selection
    from scanpath_studio.utils import build_combo_options, select_trial

    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "trial_id": ["shared", "shared"],
            "text_id": ["text", "text"],
        }
    )
    combos, _, _ = build_combo_options(fixations)
    if not st.session_state.get("_linked"):
        st.session_state["_linked"] = True
        selection = {"participant_id": "p2", "trial_id": "shared"}
        assert _match_selection(selection, combos)[1] == ""
        assert _restore_selection(selection, combos)
    st.session_state["picked"] = select_trial(combos, key_prefix="single")[:2]


class TestThePicker:
    def test_both_readers_are_offered_and_the_link_opens_the_second(self):
        at = AppTest.from_function(_picker_app).run(timeout=30)
        assert not at.exception, at.exception
        picker = at.selectbox(key="single_trial_id")
        assert picker.options == ["shared [p1]", "shared [p2]"]
        assert at.session_state["picked"] == ("p2", "shared")
        # And after a rerun that touches nothing.
        at.run(timeout=30)
        assert at.session_state["picked"] == ("p2", "shared")
        assert at.session_state["single_trial_id"] == reading_key("p2", "shared")

    def test_stepping_and_choosing_visit_both_readings(self):
        at = AppTest.from_function(_picker_app).run(timeout=30)
        at.button(key="single_prev_trial").click().run(timeout=30)
        assert at.session_state["picked"] == ("p1", "shared")
        at.button(key="single_next_trial").click().run(timeout=30)
        assert at.session_state["picked"] == ("p2", "shared")
        at.selectbox(key="single_trial_id").select_index(0).run(timeout=30)
        assert at.session_state["picked"] == ("p1", "shared")


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two readers, each with trials `t1` and `t2` — the same ids."""
    words, fixations = make_synthetic_words(), make_synthetic_fixations()
    readings = [(p, t) for t in ("t1", "t2") for p in ("p1", "p2")]
    return (
        pd.concat(
            [
                words.assign(participant_id=p, trial_id=t, text_id=t)
                for p, t in readings
            ],
            ignore_index=True,
        ),
        pd.concat(
            [
                fixations.assign(participant_id=p, trial_id=t, text_id=t)
                for p, t in readings
            ],
            ignore_index=True,
        ),
    )


def _app(**query) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for name, value in query.items():
        at.query_params[name] = value
    words, fixations = _frames()
    at.session_state["_datasets"] = {
        "Shared": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = "Shared"
    return at


def _shown(at) -> tuple[str, str]:
    selection = at.session_state["_share_selection"]
    return selection["participant_id"], selection["trial_id"]


def _notices(at) -> str:
    return " ".join(str(w.value) for w in at.warning)


class TestTheApp:
    def test_a_link_opens_the_reader_it_names_and_keeps_it(self):
        at = _app(participant="p2", trial_id="t1").run()
        assert not at.exception, at.exception
        assert _shown(at) == ("p2", "t1")
        at.run()
        assert _shown(at) == ("p2", "t1")

    def test_stepping_visits_every_reading(self):
        at = _app().run()
        assert not at.exception, at.exception
        seen = [_shown(at)]
        while not at.button(key="single_next_trial").disabled:
            at.button(key="single_next_trial").click().run()
            seen.append(_shown(at))
        assert sorted(seen) == [(p, t) for p in ("p1", "p2") for t in ("t1", "t2")]

    def test_a_link_naming_a_shared_id_alone_says_it_is_ambiguous(self):
        at = _app(trial_id="t1").run()
        assert not at.exception, at.exception
        assert "trial t1 belongs to 2 participants" in _notices(at)
        # The link chose no reader: the picker is where it opens anyway.
        assert "_single_trial_chosen" not in at.session_state

    def test_a_shared_id_saved_alone_is_reported_not_guessed(self):
        """A recovery cache from before #412 holds a trial id alone."""
        at = _app()
        at.session_state["single_trial_id"] = "t2"
        at.run()
        assert not at.exception, at.exception
        assert "Couldn't reopen the last trial: trial t2" in _notices(at)
        # A trial id the pool lacks is not ambiguous: the picker opens as before.
        at = _app()
        at.session_state["single_trial_id"] = "nowhere"
        at.run()
        assert "Couldn't reopen" not in _notices(at)
        assert split_reading_key(at.session_state["single_trial_id"])[0] in {
            "p1",
            "p2",
        }
