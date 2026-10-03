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


def _missing_table_app(table_key: str, content: bytes, file_name: str) -> None:
    import io

    import pandas as pd
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator

    from scanpath_studio.app import _read_upload
    from scanpath_studio.tabs import _render_missing_table_uploads

    class Upload(io.BytesIO):
        name = file_name
        file_id = "probe-file"
        size = len(content)

    other = "fixations" if table_key == "words" else "words"
    original = DeltaGenerator.file_uploader
    DeltaGenerator.file_uploader = lambda *a, **k: [Upload(content)]
    try:
        added = _render_missing_table_uploads(
            "Probe", {other: pd.DataFrame({"x": [1]})}
        )
    finally:
        DeltaGenerator.file_uploader = original
    st.session_state["editor_read"] = added[table_key].to_dict("records")
    prefixes = {
        "words": "col_map_words",
        "fixations": "col_map_fix",
        "raw_gaze": "col_map_raw_gaze",
    }
    st.session_state["wizard_read"] = _read_upload(
        [Upload(content)], prefixes[table_key], multi=True, kind=table_key
    ).to_dict("records")


_AOI_CSV = (
    b"participant_id,trial_id,word_id,text,x,y,width,height\n"
    b"007,01,1,NA,10,20,30,20\n"
    b"007,01,2,001,40,20,30,20\n"
)
_FIX_CSV = (
    b"participant_id,trial_id,x,y,duration_ms\n007,01,10,20,200\n007,01,40,20,180\n"
)


class TestAnAddedTableIsReadLikeTheAddScreenReadsIt:
    def test_an_aoi_table_keeps_its_zeros_and_literal_words(self):
        at = AppTest.from_function(
            _missing_table_app, args=("words", _AOI_CSV, "aoi.csv")
        ).run()
        assert not at.exception
        editor = at.session_state["editor_read"]
        assert editor == at.session_state["wizard_read"]
        assert [row["participant_id"] for row in editor] == ["007", "007"]
        assert [row["trial_id"] for row in editor] == ["01", "01"]
        assert [row["text"] for row in editor] == ["NA", "001"]

    def test_a_pick_that_changes_nothing_does_not_read_the_file_again(self):
        at = AppTest.from_function(
            _missing_table_app, args=("words", _AOI_CSV, "aoi.csv")
        ).run()
        first = at.session_state["_remap_add_raw_Probe_words"]
        # The column auto-detection proposed — already read as text.
        at.session_state["remap_Probe_words_add_participant"] = "participant_id"
        at.run()
        assert at.session_state["_remap_add_raw_Probe_words"] is first

    def test_a_fixation_table_keeps_its_zeros(self):
        at = AppTest.from_function(
            _missing_table_app, args=("fixations", _FIX_CSV, "fix.csv")
        ).run()
        assert not at.exception
        editor = at.session_state["editor_read"]
        assert editor == at.session_state["wizard_read"]
        assert [row["participant_id"] for row in editor] == ["007", "007"]
        assert [row["trial_id"] for row in editor] == ["01", "01"]

    def test_unfamiliar_columns_are_read_again_once_they_are_mapped(self):
        content = (
            b"rdr,itm,wnum,wort,x,y,width,height\n"
            b"007,01,1,NA,10,20,30,20\n"
            b"007,01,2,001,40,20,30,20\n"
        )
        at = AppTest.from_function(
            _missing_table_app, args=("words", content, "aoi.csv")
        ).run()
        # Nothing names these columns yet, so nothing protects them.
        before = at.session_state["editor_read"]
        assert [row["rdr"] for row in before] == [7, 7]
        # Mapped by hand — the file is read again under the new plan.
        at.session_state["remap_Probe_words_add_participant"] = "rdr"
        at.session_state["remap_Probe_words_add_trial"] = ["itm"]
        at.session_state["remap_Probe_words_add_text"] = "wort"
        at.run()
        assert not at.exception
        after = at.session_state["editor_read"]
        assert [row["rdr"] for row in after] == ["007", "007"]
        assert [row["itm"] for row in after] == ["01", "01"]
        assert [row["wort"] for row in after] == ["NA", "001"]
        # Unmapped columns are all still there for the editor to offer.
        assert set(after[0]) >= {"rdr", "itm", "wnum", "wort", "x", "width"}


def _raw_gaze_app(content: bytes) -> None:
    import io

    import pandas as pd
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator

    from scanpath_studio.app import _close_dataset_editor, _edit_open_dataset
    from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY
    from scanpath_studio.data import normalize_fixations
    from scanpath_studio.tabs import _apply_remap, _render_remap_editor

    class Upload(io.BytesIO):
        name = "gaze.csv"
        file_id = "probe-gaze"
        size = len(content)

    name = "Probe"
    if "_datasets" not in st.session_state:
        raw = pd.DataFrame(
            {
                "participant_id": ["007", "007"],
                "trial_id": ["t1", "t1"],
                "x": [100, 110],
                "y": [200, 210],
                "duration_ms": [250, 260],
            }
        )
        schema = {
            "participant": "participant_id",
            "trial": "trial_id",
            "x": "x",
            "y": "y",
            "duration": "duration_ms",
        }
        st.session_state["_datasets"] = {
            name: {
                "fixations": normalize_fixations(raw.astype({"x": int}), schema),
                "schemas": {"fixations": schema},
                "setup": {
                    "canvas_width": 1280,
                    "canvas_height": 1024,
                    "monitor_width_mm": 500.0,
                    "viewing_distance_mm": 700.0,
                    "base_font_size": 16,
                    "font_family": "monospace",
                    "line_spacing": 3.0,
                    "scale_text_to_boxes": True,
                    "provenance": {
                        "screen": "measured",
                        "geometry": "measured",
                        "text": "measured",
                    },
                },
            }
        }
        st.session_state["data_source_choice"] = name
        _edit_open_dataset(name)
    st.button("Close", on_click=_close_dataset_editor)
    st.button("Save", on_click=_apply_remap)
    if st.session_state.get(DATASET_EDITOR_OPEN_KEY):
        original = DeltaGenerator.file_uploader

        def uploader(self, label, *args, key=None, **kwargs):
            if key and "raw_gaze" in key and st.session_state.get("attach", True):
                return [Upload(content)]
            return original(self, label, *args, key=key, **kwargs)

        DeltaGenerator.file_uploader = uploader
        try:
            _render_remap_editor(name, st.session_state["_datasets"][name])
        finally:
            DeltaGenerator.file_uploader = original


_GAZE_CSV = (
    b"participant_id,trial_id,x,y,timestamp_ms\n"
    b"007,t1,101,201,0\n007,t1,102,202,1\n007,t1,103,203,2\n"
)


class TestAnExistingDatasetGainsRawGaze:
    def test_raw_gaze_is_added_and_matched(self):
        at = AppTest.from_function(_raw_gaze_app, args=(_GAZE_CSV,)).run()
        assert not at.exception
        assert at.session_state["_remap_dirty"]
        at.button[1].click().run()
        assert not at.exception
        assert "_remap_problems" not in at.session_state
        entry = at.session_state["_datasets"]["Probe"]
        gaze = entry["raw_gaze"]
        assert len(gaze) == 3
        assert set(gaze["participant_id"].astype(str)) == {"007"}
        assert gaze["x"].tolist() == [101, 102, 103]
        assert entry["schemas"]["raw_gaze"]["x"] == "x"
        # The rest of the dataset is as it was.
        assert entry["fixations"]["x"].tolist() == [100, 110]
        assert entry["setup"]["canvas_width"] == 1280

    def test_cancel_leaves_the_dataset_without_it(self):
        at = AppTest.from_function(_raw_gaze_app, args=(_GAZE_CSV,)).run()
        at.button[0].click().run()
        assert not at.exception
        assert "raw_gaze" not in at.session_state["_datasets"]["Probe"]
        assert not any(
            str(key).startswith("_remap_add_raw_") for key in at.session_state
        )

    def test_samples_of_other_readers_are_refused(self):
        content = b"participant_id,trial_id,x,y,timestamp_ms\n7,t1,101,201,0\n"
        at = AppTest.from_function(_raw_gaze_app, args=(content,)).run()
        at.button[1].click().run()
        assert not at.exception
        problem = at.session_state["_remap_problems"]["raw_gaze"][0]
        assert "Participant ID" in problem
        assert "raw_gaze" not in at.session_state["_datasets"]["Probe"]

    def test_screens_have_to_match_on_a_multipart_dataset(self):
        import pandas as pd

        from scanpath_studio.tabs import raw_gaze_identity_problem

        fixations = pd.DataFrame(
            {"participant_id": ["p1"], "trial_id": ["t1"], "screen_id": ["a"]}
        )
        gaze = fixations.assign(screen_id=["z"])
        problem = raw_gaze_identity_problem(gaze, {"fixations": fixations})
        assert problem and "Screen ID" in problem
        assert raw_gaze_identity_problem(fixations, {"fixations": fixations}) is None
        problem = raw_gaze_identity_problem(
            gaze, {"fixations": fixations.drop(columns="screen_id")}
        )
        assert problem and "no screens" in problem


class TestNameDescriptionAndMetadataWaitForSave:
    """Improvement A — the parts of an edit the editor's widgets do not hold
    (the metadata tables) are noted when it opens and put back on Cancel; the
    name and description are drafts until Save."""

    @staticmethod
    def _session(monkeypatch) -> dict:
        from scanpath_studio import app

        state: dict = {}
        monkeypatch.setattr(app.st, "session_state", state)
        return state

    @staticmethod
    def _table(ids):
        import pandas as pd

        from scanpath_studio import metadata as md

        raw = pd.DataFrame({"participant_id": ids, "age": [30] * len(ids)})
        return raw, md.build_participant_metadata(raw, "participant_id")

    def _attach(self, state, ids, file_sig):
        from scanpath_studio import metadata as md

        raw, table = self._table(ids)
        state[md.SESSION_KEY] = table
        state[md.RAW_SESSION_KEY] = raw
        state[md.FILE_SESSION_KEY] = file_sig
        state["participant_metadata_upload"] = object()
        return table

    def test_a_table_attached_during_a_cancelled_edit_is_detached(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio import metadata as md

        state = self._session(monkeypatch)
        state[md.OWNER_KEY] = "Probe"
        app.hold_editor_staging("Probe")
        assert not app.editor_staging_dirty()
        self._attach(state, ["p1"], "file-1")
        assert app.editor_staging_dirty()
        app._discard_editor_staging()
        app.apply_editor_restore()
        for key in (md.SESSION_KEY, md.RAW_SESSION_KEY, md.FILE_SESSION_KEY):
            assert key not in state
        assert "participant_metadata_upload" not in state

    def test_a_table_replaced_during_a_cancelled_edit_comes_back(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio import metadata as md

        state = self._session(monkeypatch)
        state[md.OWNER_KEY] = "Probe"
        original = self._attach(state, ["p1"], "file-1")
        app.hold_editor_staging("Probe")
        self._attach(state, ["p2"], "file-2")
        assert app.editor_staging_dirty()
        app._discard_editor_staging()
        app.apply_editor_restore()
        assert state[md.SESSION_KEY] is original
        # Its file is no longer in the uploader: it is back as a restored table.
        assert md.is_restored(state, "participant")
        assert "participant_metadata_upload" not in state

    def test_an_untouched_table_is_left_alone(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio import metadata as md

        state = self._session(monkeypatch)
        state[md.OWNER_KEY] = "Probe"
        self._attach(state, ["p1"], "file-1")
        upload = state["participant_metadata_upload"]
        app.hold_editor_staging("Probe")
        # Rebuilt by the section on the next run: a new object, same content.
        state[md.SESSION_KEY] = self._table(["p1"])[1]
        assert not app.editor_staging_dirty()
        app._discard_editor_staging()
        app.apply_editor_restore()
        assert state[md.FILE_SESSION_KEY] == "file-1"
        assert state["participant_metadata_upload"] is upload

    def test_save_keeps_what_is_attached(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio import metadata as md

        state = self._session(monkeypatch)
        state[md.OWNER_KEY] = "Probe"
        app.hold_editor_staging("Probe")
        table = self._attach(state, ["p1"], "file-1")
        app.commit_editor_staging("Probe")
        app._discard_editor_staging()
        app.apply_editor_restore()
        assert state[md.SESSION_KEY] is table

    def test_a_description_is_a_draft_until_save(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_DESCRIPTIONS_KEY

        state = self._session(monkeypatch)
        state["_datasets"] = {"Probe": {}}
        app.hold_editor_staging("Probe")
        state[app._description_field_key("Probe")] = "A pilot."
        assert app.editor_staging_dirty()
        assert DATASET_DESCRIPTIONS_KEY not in state
        app.commit_editor_staging("Probe")
        assert state[DATASET_DESCRIPTIONS_KEY]["Probe"] == "A pilot."
        assert app._description_field_key("Probe") not in state

    def test_a_cancelled_description_is_dropped(self, monkeypatch):
        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_DESCRIPTIONS_KEY

        state = self._session(monkeypatch)
        app.hold_editor_staging("Probe")
        state[app._description_field_key("Probe")] = "Not this."
        app._discard_editor_staging()
        assert app._description_field_key("Probe") not in state
        assert DATASET_DESCRIPTIONS_KEY not in state
