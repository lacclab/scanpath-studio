"""DATA-66 phase 1: the dataset's own column names, behind the canonical ones."""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import column_names as cn
from scanpath_studio import data
from scanpath_studio.column_names import ColumnNames, SourceName, from_schema


class TestColumnNames:
    def test_display_is_the_source_or_the_column_itself(self):
        names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
        assert names.display("duration_ms") == "CURRENT_FIX_DURATION"
        assert names.display("my_extra") == "my_extra"

    def test_a_composite_displays_its_parts(self):
        names = ColumnNames(
            {"trial_id": SourceName(("reader_id", "text_id"), cn.COMPOSITE)}
        )
        assert names.display("trial_id") == "reader_id + text_id"

    def test_kind_falls_back_to_computed_then_yours(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",))})
        assert names.kind_of("duration_ms") == cn.MAPPED
        assert names.kind_of("is_regression") == cn.COMPUTED
        assert names.kind_of("my_extra") == cn.YOURS

    def test_an_imported_measure_is_the_users_not_computed(self):
        names = ColumnNames(
            {"total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",))}
        )
        assert names.kind_of("total_fixation_duration_ms") == cn.MAPPED

    def test_to_canonical_reads_the_map_backwards(self):
        names = ColumnNames({"duration_ms": SourceName(("dur",), cn.CONVERTED)})
        assert names.to_canonical("dur") == "duration_ms"
        assert names.to_canonical("duration_ms") == "duration_ms"
        assert names.to_canonical("unknown") == "unknown"

    def test_payload_round_trips(self):
        names = ColumnNames(
            {
                "trial_id": SourceName(("a", "b"), cn.COMPOSITE),
                "fixation_id": SourceName((), cn.GENERATED, "1, 2, … per trial"),
            }
        )
        assert ColumnNames.from_payload(names.to_payload()) == names
        assert ColumnNames.from_payload(None) == cn.EMPTY
        assert ColumnNames.from_payload({"x": "not a dict"}) == cn.EMPTY

    def test_through_renames_sources_by_an_earlier_map(self):
        """An Edit-dataset save maps fields onto the stored *canonical* columns;
        read through the dataset's earlier map, they are the user's names again."""
        earlier = ColumnNames(
            {
                "trial_id": SourceName(("TRIAL",)),
                "text_id": SourceName(("PARAGRAPH",)),
                "timestamp_ms": SourceName((), cn.GENERATED, "order"),
                "total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",)),
            }
        )
        edit = ColumnNames(
            {
                "trial_id": SourceName(("text_id",)),
                "timestamp_ms": SourceName(("timestamp_ms",)),
            }
        )
        merged = edit.through(earlier)
        assert merged.display("trial_id") == "PARAGRAPH"
        assert merged.kind_of("timestamp_ms") == cn.GENERATED
        # What the edit did not touch keeps the earlier record.
        assert merged.display("total_fixation_duration_ms") == "IA_DWELL_TIME"


@pytest.fixture(scope="module")
def demo_raw():
    return data.load_sample_data()


class TestFromSchema:
    def test_the_demo_words_keep_their_eyelink_names(self, demo_raw):
        words, _ = demo_raw
        names = from_schema("words", data.propose_word_schema(words), words.columns)
        assert names.display("word_id") == "IA_ID"
        assert names.display("text") == "IA_LABEL"
        assert names.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
        assert names.kind_of("width") == cn.CONVERTED
        assert "IA_RIGHT" in names.source("width").note

    def test_the_demo_fixations_keep_their_eyelink_names(self, demo_raw):
        _, fixations = demo_raw
        schema = data.propose_fix_schema(fixations)
        names = from_schema("fixations", schema, fixations.columns)
        assert names.display("duration_ms") == schema["duration"]
        assert names.display("x") == schema["x"]
        assert names.kind_of("order_in_trial") == cn.COMPUTED

    def test_every_canonical_column_has_a_name_or_is_computed(self, demo_raw):
        words, fixations = demo_raw
        for table, raw, canonical in (
            ("words", words, data.WORDS_CANONICAL_COLUMNS),
            ("fixations", fixations, data.FIX_CANONICAL_COLUMNS),
        ):
            schema = (
                data.propose_word_schema(raw)
                if table == "words"
                else data.propose_fix_schema(raw)
            )
            names = from_schema(table, schema, raw.columns)
            for column in canonical:
                assert names.source(column) is not None or (
                    names.kind_of(column) == cn.COMPUTED
                ), (table, column)

    def test_missing_fields_are_generated_not_named(self):
        raw = pd.DataFrame(columns=["trial", "dur", "px", "py"])
        schema = {"trial": "trial", "duration": "dur", "x": "px", "y": "py"}
        names = from_schema("fixations", schema, raw.columns)
        for column in ("participant_id", "fixation_id", "timestamp_ms", "text_id"):
            assert names.kind_of(column) == cn.GENERATED, column
            assert names.display(column) == column

    def test_a_unit_conversion_is_said(self):
        raw = pd.DataFrame(columns=["trial", "FPOGD", "FPOGX", "FPOGY"])
        schema = {"trial": "trial", "duration": "FPOGD", "x": "FPOGX", "y": "FPOGY"}
        names = from_schema("fixations", schema, raw.columns)
        assert names.kind_of("duration_ms") == cn.CONVERTED
        assert names.display("duration_ms") == "FPOGD"

    def test_a_composite_trial_id_names_every_part(self):
        raw = pd.DataFrame(columns=["reader", "item", "dur", "x", "y"])
        schema = {
            "participant": "reader",
            "trial": ["reader", "item"],
            "duration": "dur",
            "x": "x",
            "y": "y",
        }
        names = from_schema("fixations", schema, raw.columns)
        assert names.kind_of("trial_id") == cn.COMPOSITE
        assert names.display("trial_id") == "reader + item"

    def test_keep_columns_limit_the_registry(self):
        """A registry rename (`Reduced_POS` → `reduced_pos`) is named only when
        normalization carried it — every field by default, the kept ones when
        the wizard narrowed the read."""
        raw = pd.DataFrame(
            columns=[
                "trial",
                "IA_ID",
                "IA_LABEL",
                "x",
                "y",
                "width",
                "height",
                "Reduced_POS",
            ]
        )
        schema = {
            "trial": "trial",
            "word_id": "IA_ID",
            "text": "IA_LABEL",
            "x": "x",
            "y": "y",
            "width": "width",
            "height": "height",
        }
        assert from_schema("words", schema, raw.columns).display("reduced_pos") == (
            "Reduced_POS"
        )
        kept_none = from_schema("words", schema, raw.columns, keep_columns=set())
        assert kept_none.source("reduced_pos") is None

    def test_a_cleared_reading_measure_has_no_name(self, demo_raw):
        words, _ = demo_raw
        schema = dict(data.propose_word_schema(words), measure_tfd=None)
        names = from_schema("words", schema, words.columns)
        assert names.source("total_fixation_duration_ms") is None

    def test_for_tables_skips_absent_tables(self, demo_raw):
        words, fixations = demo_raw
        payloads = cn.for_tables(
            {"words": data.propose_word_schema(words), "fixations": None},
            {"words": words, "fixations": fixations},
        )
        assert set(payloads) == {"words"}
        assert ColumnNames.from_payload(payloads["words"]).display("text") == "IA_LABEL"


def test_every_column_the_measures_add_is_known_as_computed(
    normalized_words_df, normalized_fixations_df
):
    """A column `measures.py` starts adding must be classed as computed, or it
    would be shown as if it were the user's."""
    from scanpath_studio import measures

    fixations = measures.enrich_fixations(
        measures.assign_fixations_to_words(
            normalized_fixations_df, normalized_words_df
        ),
        normalized_words_df,
    )
    added = set(fixations.columns) - set(normalized_fixations_df.columns)
    words = measures.compute_per_word_measures(
        normalized_fixations_df, normalized_words_df
    )
    added |= set(words.columns) - set(normalized_words_df.columns)
    assert added - cn.COMPUTED_COLUMNS - {"word_id"} == set()


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(180)
def test_the_demo_is_opened_with_its_own_column_names():
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    stashed = at.session_state[app.ACTIVE_COLUMN_NAMES_KEY]
    words = ColumnNames.from_payload(stashed["words"])
    assert words.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
    assert ColumnNames.from_payload(stashed["fixations"]).display("x") != "x"
    assert "raw_gaze" in stashed  # the demo ships raw gaze


_UPLOAD_WORDS = pd.DataFrame(
    {
        "participant_id": ["r0"] * 3,
        "trial_id": ["t0"] * 3,
        "IA_ID": [0, 1, 2],
        "IA_LABEL": ["one", "two", "three"],
        "IA_LEFT": [0.0, 50.0, 100.0],
        "IA_RIGHT": [50.0, 100.0, 150.0],
        "IA_TOP": [10.0] * 3,
        "IA_BOTTOM": [30.0] * 3,
        "IA_DWELL_TIME": [200.0, 180.0, 240.0],
    }
)
_UPLOAD_FIXATIONS = pd.DataFrame(
    {
        "participant_id": ["r0"] * 3,
        "trial_id": ["t0"] * 3,
        "CURRENT_FIX_DURATION": [200.0, 180.0, 240.0],
        "CURRENT_FIX_X": [15.0, 65.0, 115.0],
        "CURRENT_FIX_Y": [24.0] * 3,
    }
)


@pytest.mark.timeout(240)
def test_an_upload_stores_its_column_names(monkeypatch):
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {
            "col_map_words": _UPLOAD_WORDS,
            "col_map_fix": _UPLOAD_FIXATIONS,
        }.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.run(timeout=180)
    assert not at.exception, at.exception
    payload = at.session_state["_wizard_finalize_payload"]
    fixations = ColumnNames.from_payload(payload["column_names"]["fixations"])
    assert fixations.display("duration_ms") == "CURRENT_FIX_DURATION"
    words = ColumnNames.from_payload(payload["column_names"]["words"])
    assert words.display("total_fixation_duration_ms") == "IA_DWELL_TIME"
    # …and the wizard's own live view has it too.
    stashed = at.session_state[app.ACTIVE_COLUMN_NAMES_KEY]
    assert stashed["fixations"] == payload["column_names"]["fixations"]


def _stored_upload() -> dict:
    """A stored upload as the wizard leaves it, with its column-name record."""
    from scanpath_studio import api

    word_schema = data.propose_word_schema(_UPLOAD_WORDS)
    fix_schema = data.propose_fix_schema(_UPLOAD_FIXATIONS)
    words, fixations = api.load_scanpath_data(
        _UPLOAD_WORDS, _UPLOAD_FIXATIONS, word_schema=word_schema, fix_schema=fix_schema
    )
    return {
        "words": words,
        "fixations": fixations,
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
        "schemas": {"words": word_schema, "fixations": fix_schema},
        "column_names": cn.for_tables(
            {"words": word_schema, "fixations": fix_schema},
            {"words": _UPLOAD_WORDS, "fixations": _UPLOAD_FIXATIONS},
        ),
    }


def test_an_edit_dataset_save_keeps_the_users_names():
    """✏️ Edit dataset maps fields onto the stored canonical columns; the save
    used to overwrite the dataset's record of its own names with that identity."""
    import streamlit as st

    from scanpath_studio import tabs

    entry = _stored_upload()
    pending = {
        "fixations": tabs._remap_proposed(
            entry["schemas"]["fixations"],
            entry["fixations"].columns,
            tabs._FIX_REMAP_CANON,
        )
    }
    st.session_state.clear()
    st.session_state["data_source_choice"] = "study"
    st.session_state["_datasets"] = {"study": entry}
    st.session_state["_remap_pending_schemas"] = pending
    st.session_state["_remap_added_tables"] = []
    tabs._apply_remap()
    assert not st.session_state.get("_remap_problems")
    saved = st.session_state["_datasets"]["study"]["column_names"]
    fixations = ColumnNames.from_payload(saved["fixations"])
    assert fixations.display("duration_ms") == "CURRENT_FIX_DURATION"
    assert fixations.display("x") == "CURRENT_FIX_X"
    # The words table was not edited: its record is unchanged.
    assert saved["words"] == entry["column_names"]["words"]


def test_a_changed_field_is_named_by_its_new_source():
    """Swap X and Y on ✏️ Edit dataset: the record follows the edit, still in
    the user's names — never the canonical column the editor offered."""
    import streamlit as st

    from scanpath_studio import tabs

    entry = _stored_upload()
    pending = {
        "fixations": dict(
            tabs._remap_proposed(
                entry["schemas"]["fixations"],
                entry["fixations"].columns,
                tabs._FIX_REMAP_CANON,
            ),
            x="y",
            y="x",
        )
    }
    st.session_state.clear()
    st.session_state["data_source_choice"] = "study"
    st.session_state["_datasets"] = {"study": entry}
    st.session_state["_remap_pending_schemas"] = pending
    st.session_state["_remap_added_tables"] = []
    tabs._apply_remap()
    assert not st.session_state.get("_remap_problems")
    saved = st.session_state["_datasets"]["study"]["column_names"]
    fixations = ColumnNames.from_payload(saved["fixations"])
    assert fixations.display("x") == "CURRENT_FIX_Y"
    assert fixations.display("y") == "CURRENT_FIX_X"
