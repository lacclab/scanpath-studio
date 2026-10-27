"""A built-in source's mapping, read without drawing its panels.

The demo's and the public corpora's column-mapping panels are drawn only while
✏️ Edit dataset is open. Every other run reads their picks from session state
(`controls.column_mapping_from_state`), and that has to be the mapping the
panels would have produced — the same answer and the same keys left behind —
or a mapping changes the moment the user leaves the editor.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT, edit_builtin_mapping, open_dataset_editor

pytestmark = pytest.mark.timeout(240)


def _mapping_app():
    """Map the bundled demo's two raw tables, drawn or from state."""
    import streamlit as st

    from scanpath_studio.controls import (
        FIX_FIELD_SPECS,
        WORD_FIELD_SPECS,
        _mapped_columns_key,
        _mapping_state_keys,
        column_mapping_from_state,
        column_mapping_ui,
    )
    from scanpath_studio.data import (
        load_sample_data,
        propose_fix_schema,
        propose_word_schema,
    )

    words, fixations = load_sample_data()
    if st.session_state.get("_drop"):
        fixations = fixations.drop(columns=[st.session_state["_drop"]])
    dataset = st.session_state.get("_dataset", "demo")
    result, keys = {}, {}
    for name, df, prefix, specs, propose in (
        ("words", words, "col_map_words", WORD_FIELD_SPECS, propose_word_schema),
        ("fixations", fixations, "col_map_fix", FIX_FIELD_SPECS, propose_fix_schema),
    ):
        proposed = propose(df)
        if st.session_state["_mode"] == "ui":
            result[name] = column_mapping_ui(
                df,
                table_label=name,
                state_key_prefix=prefix,
                field_specs=specs,
                proposed=proposed,
                use_expander=False,
                columns_per_row=4,
                stack_labels=True,
                dataset=dataset,
            )
        else:
            result[name] = column_mapping_from_state(
                df, prefix, specs, proposed, dataset=dataset
            )
        for key in [*_mapping_state_keys(prefix, specs), _mapped_columns_key(prefix)]:
            if key in st.session_state:
                value = st.session_state[key]
                keys[key] = list(value) if isinstance(value, list) else value
    st.session_state["_result"] = result
    st.session_state["_keys"] = keys


#: Picks a user (or a restored settings file) left in the keys: an override,
#: a field cleared on purpose, a stale column, a composite Trial ID with one
#: part gone, a legacy ``"(none)"``, and the box switched to its other format.
_EDITED = {
    "col_map_fix_duration": "CURRENT_FIX_END",
    "col_map_words_text": None,
    "col_map_fix_x": "no_such_column",
    "col_map_fix_trial": ["participant_id", "TRIAL_INDEX", "gone"],
    "col_map_words_word_id": "(none)",
    "col_map_words_box_format": "Origin + size",
}

#: A word-box format that is no format at all, which the radio resets.
_BAD_FORMAT = {"col_map_words_box_format": "Corners"}

#: What a user can pick in panels that are already drawn: only real options.
_PICKED = {
    "col_map_fix_duration": "CURRENT_FIX_END",
    "col_map_words_text": None,
    "col_map_fix_trial": ["participant_id", "TRIAL_INDEX"],
    "col_map_words_box_format": "Origin + size",
}


def _run(mode: str, steps: list[dict]) -> tuple[dict, dict]:
    """Run the app through ``steps`` (session-state writes before each run)."""
    at = AppTest.from_function(_mapping_app, default_timeout=120)
    at.session_state["_mode"] = mode
    for step in steps:
        for key, value in step.items():
            at.session_state[key] = value
        at.run()
        assert not at.exception, at.exception
    return at.session_state["_result"], at.session_state["_keys"]


@pytest.mark.parametrize(
    "steps",
    [
        pytest.param([{}], id="fresh"),
        pytest.param([{}, {}], id="rerun"),
        pytest.param([_EDITED], id="edited-before-first-run"),
        pytest.param([_BAD_FORMAT], id="unknown-box-format"),
        pytest.param([{}, _PICKED], id="picked-after-first-run"),
        pytest.param([_EDITED, {"_dataset": "another"}], id="dataset-switch"),
        pytest.param([{}, _PICKED, {"_dataset": "another"}], id="picked-then-switch"),
        pytest.param([{}, _PICKED, {"_drop": "CURRENT_FIX_END"}], id="column-gone"),
    ],
)
def test_reading_the_mapping_from_state_matches_drawing_it(steps):
    drawn = _run("ui", steps)
    read = _run("state", steps)
    assert read[0] == drawn[0], "the resolved mapping differs from the panels'"
    assert read[1] == drawn[1], "the keys left behind differ from the panels'"


def _boot() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    return at


def _mapping_widgets(at) -> list[str]:
    return [
        w.key
        for group in (at.selectbox, at.multiselect, at.radio)
        for w in group
        if str(w.key).startswith(("col_map_words_", "col_map_fix_"))
    ]


def test_the_scanpath_view_draws_no_mapping_panels():
    at = _boot()
    assert _mapping_widgets(at) == []
    # …but the mapping they would have drawn is the one applied.
    assert at.session_state["col_map_fix_duration"] == "CURRENT_FIX_DURATION"


def test_the_panels_draw_in_the_editor():
    at = open_dataset_editor(_boot())
    assert not at.exception, at.exception
    assert "col_map_fix_duration" in _mapping_widgets(at)


def test_a_saved_mapping_keeps_applying_outside_the_editor():
    """A pick saved in the editor still drives the Scanpath view, where its
    widget is not drawn."""
    from scanpath_studio.constants import _VIEW_SCANPATH
    from tests.conftest import pin_view

    at = edit_builtin_mapping(
        _boot(), {"col_map_fix_duration": "CURRENT_FIX_END"}, timeout=180
    )
    assert not at.exception, at.exception
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception, at.exception
    assert _mapping_widgets(at) == []
    assert at.session_state["col_map_fix_duration"] == "CURRENT_FIX_END"
    held = at.session_state["_builtin_mapping_held"]["schemas"]["fixations"]
    assert held["duration"] == "CURRENT_FIX_END"
