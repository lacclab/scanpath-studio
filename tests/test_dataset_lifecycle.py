"""Removing a dataset forgets it everywhere in the session.

A dataset's session state is spread over keys that different modules own: its
filters (`_filter_stash`), the reading each picker was last on
(`_trial_by_dataset`), its *Loaded* status, Compare B's pointer to it, its
annotations, metadata, description, credit, image folder and identity. A
removal that misses one leaves the token behind, and the next dataset to take
the same token (the wizard reuses a free name, "Dataset 1") inherits it: it
opens filtered, on another dataset's reading, marked Loaded.

So these tests drive the real flow (open, filter, compare, remove through the
confirmation's own button) and then search the whole session for the token. A
per-dataset key added later is created by the app in this flow, so it fails
here unless removing a dataset forgets it too.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import api, app
from scanpath_studio.constants import _VIEW_SCANPATH, DATA_LIBRARY
from tests.conftest import APP_SCRIPT, pin_data_view, pin_view

TOKEN = "Dataset 1"


@pytest.fixture(autouse=True)
def _confirmation_drawn_inline(monkeypatch):
    """AppTest does not run an `st.dialog` body; drawn inline, the real
    Remove button can be clicked."""
    monkeypatch.setattr(
        app, "_delete_confirmation_dialog", app._delete_confirmation_dialog.__wrapped__
    )


def _upload(text: str = "Read this short line") -> dict:
    """Two readers of one text: with one, the app draws no participant filter."""
    words, fixations = api.build_authored_scanpath(text)
    readers = ("reader", "second_reader")
    return {
        "words": pd.concat(
            [words.assign(participant_id=r, trial_id="t1") for r in readers],
            ignore_index=True,
        ),
        "fixations": pd.concat(
            [fixations.assign(participant_id=r, trial_id="t1") for r in readers],
            ignore_index=True,
        ),
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
    }


def _names(text: object, token: str) -> bool:
    """Whether `text` names `token`, alone or as one part of a composite key."""
    return isinstance(text, str) and bool(
        re.search(rf"(^|[|\x1f/]){re.escape(token)}($|[|\x1f/])", text)
    )


def _references(value, token: str, path: str) -> list[str]:
    """Every place inside `value` that names `token`."""
    if isinstance(value, str):
        return [path] if _names(value, token) else []
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if _names(key, token) or (isinstance(key, tuple) and token in key):
                found.append(f"{path}[{key!r}]")
            found += _references(item, token, f"{path}[{key!r}]")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            found += _references(item, token, f"{path}[{index}]")
    return found


def _remove(at: AppTest, token: str) -> None:
    """The Data page's Remove: arm the confirmation, then press its button."""
    pin_data_view(at, section=DATA_LIBRARY)
    at.run()
    at.session_state[app.PENDING_DELETE_KEY] = token
    at.run()
    at.button(key="dataset_delete_confirm").click().run()
    assert not at.exception, at.exception
    assert token not in at.session_state["_datasets"]


def _left_behind(at: AppTest, token: str) -> list[str]:
    return sorted(
        path
        for key in at.session_state
        for path in _references(at.session_state[key], token, str(key))
        + ([str(key)] if _names(key, token) else [])
    )


def _session(**state) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {TOKEN: _upload()}
    for key, value in state.items():
        at.session_state[key] = value
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.timeout(300)
def test_removing_the_open_dataset_leaves_no_trace():
    at = _session(data_source_choice=TOKEN)
    at.session_state["filter_participants"] = [
        "reader"
    ]  # a filter, as a user leaves it
    at.run()
    _remove(at, TOKEN)
    assert _left_behind(at, TOKEN) == []


@pytest.mark.timeout(300)
def test_removing_the_dataset_compare_b_shows_leaves_no_trace():
    at = _session(
        data_source_choice="Bundled demo", single_compare_toggle=True, cmp_dataset=TOKEN
    )
    _remove(at, TOKEN)
    assert _left_behind(at, TOKEN) == []


@pytest.mark.timeout(300)
def test_a_dataset_added_again_under_the_same_name_opens_unfiltered():
    """The wizard hands a removed dataset's free name to the next upload."""
    at = _session(data_source_choice=TOKEN)
    at.session_state["filter_participants"] = ["reader"]
    at.run()
    _remove(at, TOKEN)
    at.session_state["_datasets"][TOKEN] = _upload("A different study entirely")
    at.session_state["_pending_source_choice"] = TOKEN
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["data_source_choice"] == TOKEN
    assert not at.session_state["_trial_filters_raw"].get("filter_participants")

