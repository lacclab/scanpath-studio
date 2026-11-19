"""A Share link to a dataset the sender added.

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
    # The sender is pointed at where Download setup file lives for an existing dataset.
    assert "Edit dataset → Download setup file" in caveat
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
    assert "Edit dataset → Download setup file" in message
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
    # …and the trial-pool miss is not shown instead.
    assert not any("couldn't be opened" in w.value for w in at.warning)
    # The notice stays on the next run (the link's params are gone by then).
    at.run(timeout=120)
    assert any("Dataset 1" in w.value for w in at.warning)


def test_shared_upload_opens_after_rename_or_independent_import(monkeypatch):
    import streamlit as st

    from scanpath_studio import url_state
    from scanpath_studio.constants import DATASET_ALIASES_KEY
    from scanpath_studio.dataset_identity import dataset_share_id

    session = {
        "_datasets": {"Original": {}},
        DATASET_ALIASES_KEY: {"Original": "Study"},
    }
    monkeypatch.setattr(st, "session_state", session)
    encoded, _ = url_state._build_share_query("Original")
    params = {k: v[0] for k, v in parse_qs(encoded).items()}
    assert params["dataset"] == "Study"
    assert params["dataset_id"] == dataset_share_id(session, "Original")
    monkeypatch.setattr(st, "query_params", params)
    # The sender renamed the study again and reused its old label for a new upload.
    session["_datasets"]["Other"] = {}
    session[DATASET_ALIASES_KEY] = {"Original": "Follow-up", "Other": "Study"}
    assert url_state.resolve_link_dataset(set(), None) == "Original"
    # A colleague has a different dataset under the sender's original store key.
    recipient = {
        "_datasets": {"Original": {}, "Independent": {}},
        DATASET_ALIASES_KEY: {"Independent": "Study"},
    }
    monkeypatch.setattr(st, "session_state", recipient)
    assert url_state.resolve_link_dataset(set(), None) == "Independent"


def test_compare_settings_resolve_named_upload_across_sessions(monkeypatch):
    import pandas as pd
    import streamlit as st

    from scanpath_studio import url_state
    from scanpath_studio.constants import DATASET_ALIASES_KEY

    session = {
        "_datasets": {"A": {}, "Recipient B": {}},
        "data_source_choice": "A",
        DATASET_ALIASES_KEY: {"Recipient B": "Named B"},
    }
    monkeypatch.setattr(st, "session_state", session)
    from scanpath_studio import compare_source

    monkeypatch.setattr(
        compare_source,
        "secondary_dataset_options",
        lambda **kw: [("Recipient B", True, "")],
    )
    selection = {
        "source": "Named B",
        "source_id": "42" * 16,
        "participant_id": "p",
        "trial_id": "t",
    }
    assert url_state._compare_b_problem(selection, pd.DataFrame()) == (
        "Recipient B",
        "",
    )
    session[DATASET_ALIASES_KEY].clear()
    source, reason = url_state._compare_b_problem(selection, pd.DataFrame())
    assert source is None and "not available" in reason
