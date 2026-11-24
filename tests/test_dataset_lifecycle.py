"""Removing a dataset forgets it everywhere in the session.

A dataset's session state is spread over keys that different modules own: its
filters (`_filter_stash`), the reading each picker was last on
(`_trial_by_dataset`), its *Loaded* status, Compare B's pointer to it, the
editor open on it, its annotations, metadata, description, credit, image
folder and identity. A removal that misses one leaves the token behind, and
the next dataset to take the same token (the wizard reuses a free name)
inherits it: it opens filtered, on another dataset's reading, marked Loaded.

So these tests drive the real flow (open, filter, compare, edit, remove
through the confirmation's own button) and then search the whole session for
the token. A per-dataset key these steps create is caught here when it is
added, unless removing a dataset forgets it too.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import api, app
from scanpath_studio.constants import (
    _VIEW_SCANPATH,
    DATA_LIBRARY,
    DATASET_EDITOR_OPEN_KEY,
    DEMO_CHOICE,
)
from scanpath_studio.utils import reading_key
from tests.conftest import APP_SCRIPT, pin_data_view, pin_view

#: Distinctive, so no default name or label in the app matches it by chance.
TOKEN = "Pilot study 7"


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


def _left_behind(at: AppTest, token: str) -> list[str]:
    return sorted(
        path
        for key in at.session_state
        for path in _references(at.session_state[key], token, str(key))
        + ([str(key)] if _names(key, token) else [])
    )


def _remove(at: AppTest, token: str) -> None:
    """The Data page's Remove: arm the confirmation, then press its button.
    The token must be all over the session first, or the walk proves nothing."""
    assert len(_left_behind(at, token)) > 3, "the dataset never took hold"
    pin_data_view(at, section=DATA_LIBRARY)
    at.run()
    at.session_state[app.PENDING_DELETE_KEY] = token
    at.run()
    at.button(key="dataset_delete_confirm").click().run()
    assert not at.exception, at.exception
    assert token not in at.session_state["_datasets"]


def _session(**state) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {TOKEN: _upload()}
    for key, value in state.items():
        at.session_state[key] = value
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    return at


def _back_on_scanpath(at: AppTest) -> None:
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    at.run()
    assert not at.exception, at.exception


@pytest.mark.timeout(300)
def test_removing_the_open_dataset_leaves_no_trace():
    at = _session(data_source_choice=TOKEN)
    at.session_state["filter_participants"] = ["reader"]  # as a user leaves it
    at.run()
    design = at.session_state["_quick_view_selection"]
    _remove(at, TOKEN)
    assert _left_behind(at, TOKEN) == []
    # The design in force stays highlighted on the dataset that opens next.
    _back_on_scanpath(at)
    assert at.session_state["_quick_view_selection"] == design


@pytest.mark.timeout(300)
def test_removing_a_dataset_opened_earlier_leaves_no_trace():
    """Opened, filtered, then left for another: its filters wait in the stash."""
    at = _session(data_source_choice=TOKEN)
    at.session_state["filter_participants"] = ["reader"]
    at.run()
    at.session_state["_pending_source_choice"] = DEMO_CHOICE
    at.run()
    assert (TOKEN, None) in at.session_state["_filter_stash"]
    _remove(at, TOKEN)
    assert _left_behind(at, TOKEN) == []


@pytest.mark.timeout(300)
def test_removing_the_dataset_compare_b_shows_leaves_no_trace():
    at = _session(
        data_source_choice=DEMO_CHOICE, single_compare_toggle=True, cmp_dataset=TOKEN
    )
    at.run()
    assert at.session_state["_compare_source_resolved"] == TOKEN
    _remove(at, TOKEN)
    assert _left_behind(at, TOKEN) == []


@pytest.mark.timeout(300)
def test_removing_the_dataset_being_edited_closes_the_editor():
    """Left open, the editor would sit on the next dataset with this one's
    name, and ✅ Save changes would rename that dataset."""
    at = _session(data_source_choice=TOKEN)
    at.session_state[DATASET_EDITOR_OPEN_KEY] = True
    pin_data_view(at)
    at.run()
    assert not at.exception, at.exception
    _remove(at, TOKEN)
    assert DATASET_EDITOR_OPEN_KEY not in at.session_state, "the editor stayed open"
    assert _left_behind(at, TOKEN) == []


@pytest.mark.timeout(300)
def test_a_dataset_added_again_under_the_same_name_starts_clean():
    """The wizard hands a removed dataset's free name to the next upload; it
    opens unfiltered and on its own first trial."""
    at = _session(
        data_source_choice=TOKEN, single_trial_id=reading_key("second_reader", "t1")
    )
    at.session_state["filter_participants"] = ["reader", "second_reader"]
    at.run()
    _remove(at, TOKEN)
    at.session_state["_datasets"][TOKEN] = _upload("A different study entirely")
    at.session_state["_pending_source_choice"] = TOKEN
    _back_on_scanpath(at)
    assert at.session_state["data_source_choice"] == TOKEN
    assert not at.session_state["_trial_filters_raw"].get("filter_participants")
    assert "second_reader" not in str(at.session_state["single_trial_id"])


class _FakeSt:
    """The slice of `streamlit` that saving a drawing touches."""

    def __init__(self, session: dict) -> None:
        self.session_state = session


def test_saving_a_drawing_takes_its_annotations_and_metadata_along(monkeypatch):
    """A draft's notes and attached tables were made on the scanpath being
    saved, so the saved dataset owns them, and the next draft starts without."""
    import scanpath_studio.annotations as annotations_mod
    from scanpath_studio import metadata, wizard
    from scanpath_studio.authoring import authoring_json, layout_text, sample_draft
    from scanpath_studio.constants import AUTHOR_CHOICE

    session: dict = {"data_source_choice": AUTHOR_CHOICE, "draft_name": "Pilot"}
    fake = _FakeSt(session)
    monkeypatch.setattr(app, "st", fake)
    monkeypatch.setattr(wizard, "st", fake)
    annotations_mod.activate_dataset(session, AUTHOR_CHOICE)
    session["trial_annotations"] = {
        ("p1", "t1"): {"star": True, "tags": [], "note": ""}
    }
    metadata.activate_dataset(session, AUTHOR_CHOICE)
    session[metadata.SESSION_KEY] = metadata.build_participant_metadata(
        pd.DataFrame({"participant_id": ["p1"], "age": [31]}),
        "participant_id",
        source_name="readers.csv",
    )
    text, layout, events = sample_draft()
    session["_author_save_payload"] = {
        "words": layout_text(text, **layout),
        "fixations": pd.DataFrame({"duration_ms": [200]}),
        "authoring": authoring_json(text, events, layout=layout),
        "setup": {"canvas_width": 800, "canvas_height": 400},
    }

    app._save_authored_dataset("draft_name")
    saved = session["_pending_source_choice"]
    assert saved != AUTHOR_CHOICE

    annotations_mod.activate_dataset(session, saved)
    assert session["trial_annotations"][("p1", "t1")]["star"] is True
    metadata.activate_dataset(session, saved)
    assert session[metadata.SESSION_KEY].source_name == "readers.csv"
    metadata.activate_dataset(session, AUTHOR_CHOICE)
    assert metadata.SESSION_KEY not in session, "the next draft inherits the table"
def _other_study() -> dict:
    """A one-reader upload with none of the demo's measure columns."""
    words, fixations = api.build_authored_scanpath("A different study entirely")
    return {
        "words": words.assign(participant_id="r1", trial_id="t1"),
        "fixations": fixations.assign(participant_id="r1", trial_id="t1"),
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
    }


def _switch(at: AppTest, dataset: str) -> None:
    at.session_state["_pending_source_choice"] = dataset
    at.run()
    at.run()
    assert not at.exception, at.exception


#: A user's choice of columns only the demo has.
_DEMO_ONLY_CHOICES = {
    "global_color_by": "next_saccade_amplitude_deg",
    "global_word_hover_fields": ["text", "gpt2_surprisal", "word_id"],
}


@pytest.mark.timeout(300)
def test_a_trip_to_another_dataset_keeps_choices_it_cannot_show():
    """Colour by a column, or hover a field, that the next dataset lacks: the
    control falls back there, and the choice is back on returning."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {"Other": _other_study()}
    for key, value in _DEMO_ONLY_CHOICES.items():
        at.session_state[key] = value
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    at.run()
    assert not at.exception, at.exception
    _switch(at, "Other")
    assert at.session_state["global_color_by"] != "next_saccade_amplitude_deg"
    _switch(at, "Bundled demo")
    for key, value in _DEMO_ONLY_CHOICES.items():
        assert at.session_state[key] == value, key


@pytest.mark.timeout(300)
def test_a_choice_made_on_the_other_dataset_wins():
    """Set aside is not forced back: a control changed while away keeps the
    new choice."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {"Other": _other_study()}
    at.session_state["global_word_hover_fields"] = ["text", "gpt2_surprisal"]
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    _switch(at, "Other")
    at.session_state["global_word_hover_fields"] = ["word_id"]
    at.run()
    _switch(at, "Bundled demo")
    assert at.session_state["global_word_hover_fields"] == ["word_id"]
