"""✏️ Edit dataset's commit boundary: what Cancel discards and Save commits.

Each test drives the real editor (``tabs._render_remap_editor``) and its
lifecycle callbacks (``app._edit_open_dataset`` / ``_close_dataset_editor`` /
``tabs._apply_remap``) in an isolated ``AppTest`` over a small stored dataset.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _editor_app(kind: str = "fixations") -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio.app import (
        _close_dataset_editor,
        _edit_open_dataset,
    )
    from scanpath_studio.column_names import from_schema
    from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY
    from scanpath_studio.data import normalize_fixations, normalize_words
    from scanpath_studio.tabs import _apply_remap, _render_remap_editor

    name = "Probe"
    if "_datasets" not in st.session_state:
        fix_raw = pd.DataFrame(
            {
                "reader": ["p1", "p1"],
                "item": ["t1", "t1"],
                "block": ["b1", "b1"],
                "fx": [100, 110],
                "fy": [200, 210],
                "dwell": [250, 260],
                "alternative": [333, 343],
            }
        )
        fix_schema = {
            "participant": "reader",
            "trial": ["item", "block"],
            "x": "fx",
            "y": "fy",
            "duration": "dwell",
        }
        entry = {
            "fixations": normalize_fixations(
                fix_raw, fix_schema, keep_columns={"alternative", "block", "item"}
            ),
            "schemas": {"fixations": fix_schema},
            "column_names": {
                "fixations": from_schema(
                    "fixations", fix_schema, fix_raw.columns
                ).to_payload()
            },
            "composite_trial_columns": ["item", "block"],
        }
        if kind == "words":
            word_raw = pd.DataFrame(
                {
                    "reader": ["p1", "p1"],
                    "item": ["t1", "t1"],
                    "block": ["b1", "b1"],
                    "wid": [1, 2],
                    "txt": ["Hi", "there"],
                    "L": [0.0, 50.0],
                    "R": [40.0, 90.0],
                    "T": [0.0, 0.0],
                    "B": [20.0, 20.0],
                    "IA_DWELL_TIME": [100, 200],
                }
            )
            word_schema = {
                "participant": "reader",
                "trial": ["item", "block"],
                "word_id": "wid",
                "text": "txt",
                "left": "L",
                "right": "R",
                "top": "T",
                "bottom": "B",
                "measure_tfd": "IA_DWELL_TIME",
            }
            entry["words"] = normalize_words(
                word_raw, word_schema, keep_columns={"item", "block"}
            )
            entry["schemas"]["words"] = word_schema
        st.session_state["_datasets"] = {name: entry}
        st.session_state["data_source_choice"] = name
        _edit_open_dataset(name)
    st.button("Close", on_click=_close_dataset_editor)
    st.button("Reopen", on_click=_edit_open_dataset, args=(name,))
    st.button("Save", on_click=_apply_remap)
    if st.session_state.get(DATASET_EDITOR_OPEN_KEY):
        _render_remap_editor(name, st.session_state["_datasets"][name])
        st.session_state["pending_probe"] = st.session_state["_remap_pending_schemas"]


def _close_and_reopen(at: AppTest) -> AppTest:
    at.button[0].click().run()
    at.button[1].click().run()
    assert not at.exception
    return at


class TestCancelledMappingDoesNotReturn:
    def test_a_cancelled_x_pick_reopens_on_the_saved_column(self):
        at = AppTest.from_function(_editor_app).run()
        at.selectbox(key="remap_Probe_fixations_x").set_value("alternative").run()
        assert at.session_state["_remap_dirty"]
        _close_and_reopen(at)
        assert at.selectbox(key="remap_Probe_fixations_x").value == "x"
        assert at.session_state["pending_probe"]["fixations"]["x"] == "x"
        assert not at.session_state["_remap_dirty"]
        # Saving the untouched reopened editor keeps the stored values.
        at.button[2].click().run()
        stored = at.session_state["_datasets"]["Probe"]["fixations"]
        assert stored["x"].tolist() == [100, 110]

    def test_a_draft_survives_reruns_within_one_edit(self):
        at = AppTest.from_function(_editor_app).run()
        at.selectbox(key="remap_Probe_fixations_x").set_value("alternative").run()
        at.run()
        assert at.selectbox(key="remap_Probe_fixations_x").value == "alternative"
        assert at.session_state["_remap_dirty"]

    def test_a_cancelled_composite_trial_id_comes_back_composed(self):
        at = AppTest.from_function(_editor_app).run()
        trial = at.multiselect(key="remap_Probe_fixations_trial")
        assert list(trial.value) == ["item", "block"]
        trial.set_value(["item"]).run()
        _close_and_reopen(at)
        trial = at.multiselect(key="remap_Probe_fixations_trial")
        assert list(trial.value) == ["item", "block"]
        assert not at.session_state["_remap_dirty"]

    def test_a_cancelled_measure_clear_and_box_format_come_back(self):
        at = AppTest.from_function(_editor_app, kwargs={"kind": "words"}).run()
        assert not at.exception
        measure = at.selectbox(key="remap_Probe_words_measure_tfd")
        assert measure.value == "total_fixation_duration_ms"
        measure.set_value(None).run()
        box = at.radio(key="remap_Probe_words_box_format")
        original_format = box.value
        other = next(option for option in box.options if option != original_format)
        box.set_value(other).run()
        assert at.session_state["_remap_dirty"]
        _close_and_reopen(at)
        assert (
            at.selectbox(key="remap_Probe_words_measure_tfd").value
            == "total_fixation_duration_ms"
        )
        assert at.radio(key="remap_Probe_words_box_format").value == original_format
        assert not at.session_state["_remap_dirty"]

    def test_touch_marks_from_a_cancelled_edit_are_dropped(self):
        from scanpath_studio.controls import TOUCHED_FIELDS_KEY

        at = AppTest.from_function(_editor_app).run()
        at.selectbox(key="remap_Probe_fixations_x").set_value("alternative").run()
        assert "remap_Probe_fixations_x" in at.session_state[TOUCHED_FIELDS_KEY]
        _close_and_reopen(at)
        touched = at.session_state[TOUCHED_FIELDS_KEY]
        assert not any(str(key).startswith("remap_") for key in touched)


def _invalid_mapping_app() -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio.data import normalize_fixations, normalize_words
    from scanpath_studio.tabs import _apply_remap, render_dataset_editor_footer

    if "_datasets" not in st.session_state:
        fix_raw = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "screen_id": ["a", "b"],
                "screen_index": [1, 2],
                "block": ["same", "same"],
                "x": [10, 20],
                "y": [20, 30],
                "duration_ms": [200, 250],
            }
        )
        fix_schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "screen_id": "screen_id",
            "screen_index": "screen_index",
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
        }
        word_raw = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "screen_id": ["a", "b"],
                "screen_index": [1, 2],
                "word_id": [1, 2],
                "text": ["Hi", "there"],
                "alt_text": ["Yo", "you"],
                "x": [0.0, 50.0],
                "y": [0.0, 0.0],
                "width": [40.0, 40.0],
                "height": [20.0, 20.0],
            }
        )
        word_schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "screen_id": "screen_id",
            "screen_index": "screen_index",
            "word_id": "word_id",
            "text": "text",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        st.session_state["_datasets"] = {
            "Probe": {
                "fixations": normalize_fixations(
                    fix_raw, fix_schema, keep_columns={"block"}
                ),
                "words": normalize_words(
                    word_raw, word_schema, keep_columns={"alt_text"}
                ),
                "schemas": {"fixations": fix_schema, "words": word_schema},
            }
        }
        st.session_state["data_source_choice"] = "Probe"
        st.session_state["fix_schema"] = fix_schema
        st.session_state["word_schema"] = word_schema
    st.session_state["_remap_pending_schemas"] = {
        "words": {**st.session_state["word_schema"], "text": "alt_text"},
        "fixations": {
            **st.session_state["fix_schema"],
            "screen_id": st.session_state.get("screen_pick", "block"),
        },
    }
    st.button("Save", on_click=_apply_remap)
    render_dataset_editor_footer(st.container())


class TestAnInvalidStoredMappingIsReportedNotRaised:
    def test_the_failure_is_an_editor_problem_and_nothing_is_saved(self):
        at = AppTest.from_function(_invalid_mapping_app).run()
        at.button[0].click().run()
        assert not at.exception
        problems = at.session_state["_remap_problems"]
        assert list(problems) == ["fixations"]
        assert "screen_index" in problems["fixations"][0]
        # Shown at the foot of the editor, named after its table.
        assert any(
            "Fixations" in error.value and "screen_index" in error.value
            for error in at.error
        )
        stored = at.session_state["_datasets"]["Probe"]
        assert stored["fixations"]["screen_id"].tolist() == ["a", "b"]
        # The AOI table remapped before it is not committed either.
        assert stored["words"]["text"].tolist() == ["Hi", "there"]

    def test_a_blocked_save_is_not_repeated_in_every_field(self):
        at = AppTest.from_function(_editor_app).run()
        at.selectbox(key="remap_Probe_fixations_x").set_value(None).run()
        at.button[2].click().run()
        assert at.session_state["_remap_problems"]["fixations"]
        assert not any("Fix these" in warning.value for warning in at.warning)

    def test_a_corrected_mapping_then_saves(self):
        at = AppTest.from_function(_invalid_mapping_app).run()
        at.button[0].click().run()
        at.session_state["screen_pick"] = "screen_id"
        at.run()
        at.button[0].click().run()
        assert not at.exception
        assert "_remap_problems" not in at.session_state
        stored = at.session_state["_datasets"]["Probe"]
        assert stored["words"]["text"].tolist() == ["Yo", "you"]
