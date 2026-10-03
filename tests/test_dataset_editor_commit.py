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
