"""A link that opens the Comparisons subtab on a *Match field* (`?match=`).

Booted headless on the bundled demo in Full (`conftest` pins ``?ui=full``),
except where a test names Essentials itself.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.session_keys import (
    MATCH_LINK_STATE_KEY,
    MATCH_SHARE_STATE_KEY,
    MULTI_VIEW,
    PARAM_MATCH,
    PARAM_MATCH_VIEW,
)
from tests.conftest import APP_SCRIPT, SUBTAB_KEY

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

pytestmark = pytest.mark.timeout(400)


def _boot(match: str, **query: str) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=240)
    at.query_params[PARAM_MATCH] = match
    for key, value in query.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _picker(at: AppTest):
    return next(s for s in at.selectbox if s.key == "multi_gen_col")


def _link_warnings(at: AppTest) -> list[str]:
    return [w.value for w in at.warning if "match=" in w.value]


def _shared_match(at: AppTest) -> str | None:
    query, _caveats = at.session_state["_share_query_current"]
    return parse_qs(query).get(PARAM_MATCH, [None])[0]


@pytest.mark.parametrize(
    ("match", "choice"),
    [
        ("same_participant", "@same_participant"),
        ("@same_text", "@same_text"),
        ("difficulty_level", "difficulty_level"),
        # The demo's eye column, by the name its files give it.
        ("EYE_TRACKED", "eye"),
    ],
)
def test_a_match_link_opens_comparisons_on_that_field(match, choice):
    at = _boot(match)
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_COMPARISONS
    assert _picker(at).value == choice
    assert _link_warnings(at) == []
    # Read once: the user's next pick and subtab stay theirs.
    other = next(o for o in _picker(at).options if o != _picker(at).value)
    _picker(at).set_value(other).run()
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_EXPORT
    at.run()
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_EXPORT


def test_a_field_the_dataset_lacks_is_dropped_with_a_notice():
    at = _boot("no_such_field")
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_COMPARISONS
    assert _link_warnings(at) == ["Ignored the link's invalid match=no_such_field."]
    assert _picker(at).value == "@same_text"
    at.run()
    assert _link_warnings(at) == ["Ignored the link's invalid match=no_such_field."]


def test_share_writes_match_only_from_comparisons():
    """The link copied after opening Comparisons reopens it on the same field,
    spelled as the dataset names it; one copied after another subtab carries
    none."""
    at = _boot("same_participant")
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    assert _shared_match(at) == "same_participant"
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_COMPARISONS
    at.run()
    _picker(at).set_value("eye").run()
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    assert _shared_match(at) == "EYE_TRACKED"
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_EXPORT
    at.run()
    assert MATCH_SHARE_STATE_KEY not in at.session_state
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    assert _shared_match(at) is None


def test_essentials_says_where_comparisons_is_then_full_opens_it():
    at = _boot("same_participant", ui="essentials")
    notes = [i.value for i in at.info if "Comparisons" in i.value]
    assert notes == [
        "This link opens the Comparisons subtab, which only Full shows. "
        "Switch to Full to see it."
    ]
    assert at.session_state[MATCH_LINK_STATE_KEY] == {"value": "same_participant"}
    at.segmented_control(key="ui_mode_switch").set_value("full").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_COMPARISONS
    assert _picker(at).value == "@same_participant"
    assert not [i.value for i in at.info if "Switch to Full" in i.value]


def test_a_kept_column_is_matched_by_its_own_name():
    """A column a dataset kept as it was named (`add_dataset(keep_columns=…)`)
    is a Match field a link names as the dataset does."""
    from scanpath_studio.synthetic import make_multipart_synthetic_data

    words, fixations = make_multipart_synthetic_data()
    fixations = pd.concat(
        [
            fixations.assign(participant_id="reader1", source_trial="a"),
            fixations.assign(participant_id="reader2", source_trial="b"),
        ],
        ignore_index=True,
    )
    words = pd.concat(
        [words.assign(participant_id=r) for r in ("reader1", "reader2")],
        ignore_index=True,
    )
    at = AppTest.from_file(APP_SCRIPT, default_timeout=240)
    at.session_state["_datasets"] = {
        "Two readers": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = "Two readers"
    at.query_params[PARAM_MATCH] = "source_trial"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_COMPARISONS
    assert _link_warnings(at) == []
    assert _picker(at).value == "source_trial"
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    assert _shared_match(at) == "source_trial"


def test_a_match_link_opens_comparisons_in_its_overlay_and_share_keeps_it():
    at = _boot("same_text", match_view="overlay")
    assert at.session_state[SUBTAB_KEY] == tabs.SUBTAB_COMPARISONS
    assert at.session_state[MULTI_VIEW] == "Overlay"
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    query, _caveats = at.session_state["_share_query_current"]
    assert parse_qs(query).get(PARAM_MATCH_VIEW) == ["overlay"]


def test_the_grid_writes_no_view():
    at = _boot("same_text")
    at.session_state[SUBTAB_KEY] = tabs.SUBTAB_SHARE
    at.run()
    query, _caveats = at.session_state["_share_query_current"]
    assert PARAM_MATCH_VIEW not in parse_qs(query)


def test_a_view_the_comparisons_tab_lacks_is_dropped_with_a_notice():
    at = _boot("same_text", match_view="pile")
    assert any("match_view=" in w.value for w in at.warning)
    assert at.session_state[MULTI_VIEW] == "Grid"
