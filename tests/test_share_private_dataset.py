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
    assert query["dataset_digest"][0].startswith("v1-")
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


def test_comparison_link_reopens_both_uploads_from_the_recovery_cache(
    monkeypatch, tmp_path
):
    import pandas as pd

    from scanpath_studio.constants import DATASET_ALIASES_KEY
    from scanpath_studio.dataset_identity import DATASET_IDS_KEY
    from scanpath_studio.persistence import (
        PERSIST_ENV_VAR,
        STATE_DIR_ENV_VAR,
        save_state,
    )
    from scanpath_studio.synthetic import make_synthetic_fixations, make_synthetic_words

    def dataset(trial):
        return {
            "words": make_synthetic_words().assign(trial_id=trial),
            "fixations": make_synthetic_fixations().assign(trial_id=trial),
            "raw_gaze": pd.DataFrame(),
        }

    monkeypatch.setenv(PERSIST_ENV_VAR, "1")
    monkeypatch.setenv(STATE_DIR_ENV_VAR, str(tmp_path / "sender"))
    a, b = dataset("reading A"), dataset("reading B")
    sender = AppTest.from_file(APP_SCRIPT)
    sender.session_state["_datasets"] = {"local-a": a, "local-b": b}
    sender.session_state["data_source_choice"] = "local-a"
    sender.session_state[DATASET_ALIASES_KEY] = {
        "local-a": "Corpus A",
        "local-b": "Corpus B",
    }
    sender.session_state["single_compare_toggle"] = True
    sender.session_state["cmp_dataset"] = "local-b"
    sender.run(timeout=90)
    assert not sender.exception, sender.exception
    query, notes = sender.session_state["_share_query_current"]
    params = {key: values[0] for key, values in parse_qs(query).items()}
    assert params["dataset"] == "Corpus A"
    assert params["cmp_dataset"] == "Corpus B"
    assert params["dataset_id"] != params["cmp_dataset_id"]
    assert any("Corpus B" in note and "import" in note for note in notes)

    def open_link(case, uploads, aliases, identifiers):
        root = tmp_path / case
        # Another comparison was active the last time this app closed.
        assert save_state(
            {
                "_datasets": uploads,
                DATASET_ALIASES_KEY: aliases,
                DATASET_IDS_KEY: identifiers,
                "data_source_choice": "Synthetic test trial",
                "single_compare_toggle": True,
                "cmp_dataset": "Bundled demo",
                "_compare_selected_identity": ("synthetic", "reading A"),
                "single_compare_screen_id": "old screen",
            },
            root,
        )
        monkeypatch.setenv(STATE_DIR_ENV_VAR, str(root))
        at = AppTest.from_file(APP_SCRIPT)
        at.query_params.update(params)
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert not at.error, at.error
        assert at.session_state["data_source_choice"] == "recipient-a"
        assert at.session_state["_share_selection"]["trial_id"] == "reading A"
        return at

    aliases = {"recipient-a": "Corpus A", "other": "Corpus B"}
    uploads = {"recipient-a": a, "other": b}
    by_id = open_link(
        "renamed",
        {**uploads, "renamed": b},
        {**aliases, "renamed": "Renamed on this computer"},
        {"renamed": params["cmp_dataset_id"]},
    )
    by_name = open_link("independent", uploads, aliases, {})
    for recipient, expected in [(by_id, "renamed"), (by_name, "other")]:
        selected = recipient.session_state["_share_selection"]["compare"]
        assert selected["source"] == expected
        assert selected["trial_id"] == "reading B"
        assert selected["participant_id"] == "synthetic"

    missing = open_link("missing", {"recipient-a": a}, aliases, {})
    assert missing.session_state["single_compare_toggle"] is False
    assert "compare" not in missing.session_state["_share_selection"]
    warnings = [w.value for w in missing.warning if "Corpus B" in w.value]
    assert len(warnings) == 1
    assert "Add dataset → Import files" in warnings[0]
    assert "reopen the link" in warnings[0]


@pytest.mark.parametrize(
    ("key", "value"),
    [("_pending_source_choice", "Another dataset"), ("single_compare_toggle", True)],
)
def test_missing_b_notice_retires_after_a_manual_selection(monkeypatch, key, value):
    import streamlit as st

    from scanpath_studio.url_state import resolve_link_compare_upload

    state = {"data_source_choice": "A", "single_compare_toggle": True}
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(
        st, "query_params", {"compare": "p:t", "cmp_dataset": "Missing"}
    )
    assert resolve_link_compare_upload("A")
    assert resolve_link_compare_upload("A")
    state[key] = value
    assert resolve_link_compare_upload("A") is None
    state.pop("_pending_source_choice", None)
    state["single_compare_toggle"] = False
    assert resolve_link_compare_upload("A") is None


def test_legacy_same_dataset_comparison_overrides_the_previous_b(monkeypatch, tmp_path):
    from scanpath_studio.persistence import (
        PERSIST_ENV_VAR,
        STATE_DIR_ENV_VAR,
        save_state,
    )
    from scanpath_studio.synthetic import TRIAL

    monkeypatch.setenv(PERSIST_ENV_VAR, "1")
    monkeypatch.setenv(STATE_DIR_ENV_VAR, str(tmp_path))
    assert save_state({"cmp_dataset": "Bundled demo"}, tmp_path)
    at = AppTest.from_file(APP_SCRIPT)
    at.query_params.update({"source": "synthetic", "compare": f"synthetic:{TRIAL}"})
    at.run(timeout=90)
    assert not at.exception, at.exception
    selection = at.session_state["_share_selection"]["compare"]
    assert selection["source"] is None
    assert selection["trial_id"] == TRIAL
