"""The metadata filter controls, drawn by the real widgets.

A numeric metadata field with one value over the loaded data has no range to
pick. Streamlit refuses a slider whose ends are equal, and a trial table built
that way — a one-row table, or a pilot whose trials share a value — used to stop
the whole Scanpath view. Each grain must draw such a field without a slider.
"""

from __future__ import annotations

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import metadata as md


def _constant_field_app() -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio import metadata as md
    from scanpath_studio.controls import (
        _render_participant_metadata_filters,
        _render_text_metadata_filters,
        _render_trial_metadata_filters,
    )

    grain = st.query_params.get("grain", "trial")
    case = st.query_params.get("case", "repeated")
    values = {
        "one_row": [20],
        "repeated": [20, 20],
        "among_missing": [20, None, None],
        "varying": [20, 30],
    }[case]
    ids = [f"t{i + 1}" for i in range(len(values))]
    if grain == "participant":
        table = md.build_participant_metadata(
            pd.DataFrame({"reader": ids, "value": values}), "reader", participants=ids
        )
        render = _render_participant_metadata_filters
    elif grain == "trial":
        table = md.build_trial_metadata(
            pd.DataFrame({"trial": ids, "value": values}),
            "trial",
            keys={("p1", tid) for tid in ids},
        )
        render = _render_trial_metadata_filters
    else:
        table = md.build_text_metadata(
            pd.DataFrame({"text": ids, "value": values}), "text", keys=ids
        )
        render = _render_text_metadata_filters
    st.session_state[md.grain_keys(grain)[0]] = table
    render(st, prefix="", on_change=lambda: None)


GRAINS = ("participant", "trial", "text")


@pytest.mark.parametrize("grain", GRAINS)
@pytest.mark.parametrize("case", ["one_row", "repeated", "among_missing"])
def test_a_constant_numeric_field_draws_no_slider(grain, case):
    at = AppTest.from_function(_constant_field_app)
    at.query_params["grain"] = grain
    at.query_params["case"] = case
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.slider) == 0


@pytest.mark.parametrize("grain", GRAINS)
def test_a_varying_numeric_field_still_gets_its_slider(grain):
    at = AppTest.from_function(_constant_field_app)
    at.query_params["grain"] = grain
    at.query_params["case"] = "varying"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.slider) == 1
    assert at.slider[0].min == 20 and at.slider[0].max == 30


def test_the_full_app_survives_a_one_row_trial_table():
    """The review's reproduction: a one-row trial table for the open reading."""
    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    assert not at.exception, at.exception
    selection = at.session_state["_share_selection"]
    participant, trial = selection["participant_id"], selection["trial_id"]
    table = md.build_trial_metadata(
        pd.DataFrame({"trial": [trial], "difficulty_score": [20]}),
        "trial",
        keys={(participant, trial)},
    )
    md.mark_restored(at.session_state, "trial", table)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert md.trial_bounds_for(table, "difficulty_score") is None
