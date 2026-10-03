"""Editing the authored text keeps the hand-placed fixations, and a destructive
edit can be undone one step.

Changing the stimulus used to replace every authored fixation with one default
fixation per word. Now the fixations stay — id, X/Y, order and duration — and
only a target word the edit changed is flagged. Regeneration is an explicit
action, and the draft it (or a deletion, a move, a restored file) replaced is
one click away. The editable draft also downloads as an authoring file that
loads back on the screen and through the API.
"""

from __future__ import annotations

import pandas as pd
from streamlit.testing.v1 import AppTest

from scanpath_studio.authoring import (
    destructive_change,
    layout_text,
    stale_target_words,
    unresolved_targets,
)


def authoring_app():
    import streamlit as st

    from scanpath_studio.app import _render_authoring_source
    from scanpath_studio.constants import AUTHOR_CHOICE

    st.session_state.setdefault("data_source_choice", AUTHOR_CHOICE)
    _words, fixations = _render_authoring_source()
    st.session_state["author_probe_fixations"] = fixations


def _custom_draft() -> AppTest:
    at = AppTest.from_function(authoring_app, default_timeout=30).run()
    events = at.session_state["_authored_events_frame"].head(2).copy()
    events.loc[0, ["x", "duration_ms"]] = [777.0, 987.0]
    at.session_state["_authored_events_frame"] = events
    revision = "_author_events_editor_revision"
    current = at.session_state[revision] if revision in at.session_state else 0
    at.session_state[revision] = current + 1
    return at.run()


def _fixations(at: AppTest) -> list[dict]:
    frame = at.session_state["author_probe_fixations"]
    return frame[["fixation_id", "x", "y", "duration_ms", "order_in_trial"]].to_dict(
        "records"
    )


def _button(at: AppTest, label: str):
    return next(button for button in at.button if button.label == label)


def test_a_punctuation_edit_keeps_every_authored_fixation():
    at = _custom_draft()
    before = _fixations(at)
    text = at.text_area(key="author_text")
    text.set_value(text.value + "!").run()
    assert not at.exception
    assert _fixations(at) == before
    assert before[0]["x"] == 777.0 and before[0]["duration_ms"] == 987.0
    assert not any("target word" in w.value for w in at.warning)


def test_a_reflow_flags_stale_targets_instead_of_moving_anything():
    at = _custom_draft()
    before = _fixations(at)
    at.text_area(key="author_text").set_value("Something else entirely").run()
    assert _fixations(at) == before
    warning = next(w.value for w in at.warning if "target word" in w.value)
    assert "fixation 1 → word 1" in warning and "fixation 2 → word 2" in warning
    _button(at, "Clear those target words").click().run()
    assert at.session_state["_authored_events_frame"]["word_id"].isna().all()
    assert not any("target word" in w.value for w in at.warning)
    assert _fixations(at) == before


def test_putting_the_text_back_resolves_the_flag():
    at = _custom_draft()
    original = at.text_area(key="author_text").value
    at.text_area(key="author_text").set_value("Something else entirely").run()
    assert any("target word" in w.value for w in at.warning)
    at.text_area(key="author_text").set_value(original).run()
    assert not any("target word" in w.value for w in at.warning)


def test_reset_is_explicit_and_restore_brings_the_draft_back():
    at = _custom_draft()
    before = _fixations(at)
    assert _button(at, "Restore previous draft").disabled
    _button(at, "Reset fixations to the text").click().run()
    reset = _fixations(at)
    assert len(reset) > 2 and all(row["duration_ms"] == 220 for row in reset)
    _button(at, "Restore previous draft").click().run()
    assert _fixations(at) == before
    # …and pressing it again returns to the reset draft.
    _button(at, "Restore previous draft").click().run()
    assert _fixations(at) == reset


def test_adding_a_fixation_is_not_a_destructive_edit():
    events = pd.DataFrame(
        {
            "fixation_id": [1],
            "order_in_trial": [1],
            "word_id": [None],
            "x": [10.0],
            "y": [20.0],
            "duration_ms": [200],
        }
    )
    added = pd.concat(
        [events, events.assign(fixation_id=2, order_in_trial=2)], ignore_index=True
    )
    assert not destructive_change(events, added)
    assert destructive_change(added, events)
    assert destructive_change(events, events.assign(x=11.0))
    assert not destructive_change(None, events)


def test_stale_targets_ignore_punctuation_and_case():
    old = layout_text("The cat sat.")
    events = pd.DataFrame(
        {
            "fixation_id": [1, 2, 3],
            "order_in_trial": [1, 2, 3],
            "word_id": [1, 2, 3],
            "x": [1.0, 2.0, 3.0],
            "y": [1.0, 1.0, 1.0],
            "duration_ms": [200, 200, 200],
        }
    )
    assert stale_target_words(old, layout_text("the cat sat!"), events) == {}
    stale = stale_target_words(old, layout_text("The dog"), events)
    assert stale == {2: (2, "cat"), 3: (3, "sat")}
    assert unresolved_targets(stale, layout_text("The dog"), events) == {2: 2, 3: 3}
    assert unresolved_targets(stale, old, events) == {}
