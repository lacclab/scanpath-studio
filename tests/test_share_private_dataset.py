"""#374 F14: a Share link to a dataset the sender added.

Its files can't travel in a URL, so the link names the dataset (`?dataset=`).
A recipient who holds a dataset of that name lands on it; one who doesn't is
told which dataset is missing and how to get it — and the link's view is not
applied to whatever else they had open.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _share_added_app():
    import streamlit as st

    from scanpath_studio.url_state import _build_share_query

    st.session_state["_datasets"] = {"Dataset 1": {}}
    st.session_state["_share_selection"] = {"participant_id": "s01", "trial_id": "44"}
    query, caveats = _build_share_query("Dataset 1")
    st.session_state["_query"] = query
    st.session_state["_caveats"] = caveats


def test_the_link_names_the_added_dataset():
    at = AppTest.from_function(_share_added_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    query = parse_qs(at.session_state["_query"])
    assert query["dataset"] == ["Dataset 1"]
    assert "source" not in query
    (caveat,) = at.session_state["_caveats"]
    # The sender is pointed at where Save setup lives for an existing dataset.
    assert "Edit dataset → Save setup" in caveat
    assert "Add dataset → Import files" in caveat


def _resolve_app():
    import streamlit as st

    from scanpath_studio.url_state import resolve_link_dataset

    st.session_state["_datasets"] = {"Mine": {}}
    st.session_state["_resolved"] = resolve_link_dataset(set(), None)


def test_a_dataset_the_recipient_holds_is_opened():
    at = AppTest.from_function(_resolve_app)
    at.query_params["dataset"] = "Mine"
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_resolved"] == "Mine"


def test_the_missing_message_names_the_dataset_and_the_way_to_get_it():
    from scanpath_studio.url_state import missing_dataset_message

    message = missing_dataset_message("Dataset 1", "s01", "44")
    assert "trial 44 of participant s01 in **Dataset 1**" in message
    assert "Edit dataset → Save setup" in message
    assert "Add dataset → Import files" in message
    assert "**Dataset 1**, which" in missing_dataset_message("Dataset 1")


@pytest.mark.timeout(240)
def test_a_missing_dataset_is_named_and_the_view_is_not_applied():
    control = AppTest.from_file(APP_SCRIPT)
    control.run(timeout=120)
    assert not control.exception, control.exception
    before = control.session_state["data_source_choice"]

    at = AppTest.from_file(APP_SCRIPT)
    at.query_params["dataset"] = "Dataset 1"
    at.query_params["participant"] = "s01"
    at.query_params["trial_id"] = "44"
    at.query_params["heatmap_colorscale"] = "Greens"
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert at.session_state["data_source_choice"] == before
    named = [w.value for w in at.warning if "Dataset 1" in w.value]
    assert named, [w.value for w in at.warning]
    assert "trial 44 of participant s01" in named[0]
    # The sender's styling did not land on the recipient's own dataset.
    colorscale = (
        at.session_state["global_heatmap_colorscale"]
        if "global_heatmap_colorscale" in at.session_state
        else None
    )
    assert colorscale != "Greens"
    # …and the trial-pool miss it used to fall into is not shown instead.
    assert not any("couldn't be opened" in w.value for w in at.warning)
    # The notice stays on the next run (the link's params are gone by then).
    at.run(timeout=120)
    assert any("Dataset 1" in w.value for w in at.warning)
