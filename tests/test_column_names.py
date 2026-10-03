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


def test_compare_b_carries_a_stored_uploads_names():
    import streamlit as st

    from scanpath_studio import compare_source

    st.session_state.clear()
    st.session_state["_datasets"] = {"study": _stored_upload()}
    b = compare_source.load_secondary_dataset("study")
    assert b is not None
    assert b.column_names["fixations"].display("duration_ms") == (
        "CURRENT_FIX_DURATION"
    )


def test_a_mapped_text_id_names_unique_text_id_too():
    """A remap fills `unique_text_id` from the mapped Text ID
    (`data.remap_normalized_frame`); the record must say the same."""
    raw = pd.DataFrame(columns=["trial", "IA_ID", "x", "y", "width", "height", "art"])
    schema = {
        "trial": "trial",
        "word_id": "IA_ID",
        "text_id": "art",
        "x": "x",
        "y": "y",
        "width": "width",
        "height": "height",
    }
    names = from_schema("words", schema, raw.columns)
    assert names.display("unique_text_id") == "art"


def test_restricted_to_drops_columns_a_frame_does_not_have():
    names = ColumnNames({"a": SourceName(("A",)), "gone": SourceName(("G",))})
    assert names.restricted_to(["a", "b"]) == ColumnNames({"a": SourceName(("A",))})


def test_a_measure_cleared_on_edit_dataset_loses_its_name():
    """Clear *Total fixation duration* on ✏️ Edit dataset: the column leaves the
    frame, and the record must not keep naming it — a computed TFD filled in
    later would otherwise read as the user's."""
    import streamlit as st

    from scanpath_studio import tabs

    entry = _stored_upload()
    pending = {
        "words": dict(
            tabs._remap_proposed(
                entry["schemas"]["words"],
                entry["words"].columns,
                tabs._WORD_REMAP_CANON,
            ),
            measure_tfd=None,
        )
    }
    st.session_state.clear()
    st.session_state["data_source_choice"] = "study"
    st.session_state["_datasets"] = {"study": entry}
    st.session_state["_remap_pending_schemas"] = pending
    st.session_state["_remap_added_tables"] = []
    tabs._apply_remap()
    assert not st.session_state.get("_remap_problems")
    saved = st.session_state["_datasets"]["study"]
    assert "total_fixation_duration_ms" not in saved["words"].columns
    words = ColumnNames.from_payload(saved["column_names"]["words"])
    assert words.source("total_fixation_duration_ms") is None


class TestLabels:
    NAMES = ColumnNames(
        {
            "duration_ms": SourceName(("CURRENT_FIX_DURATION",)),
            "trial_id": SourceName(("TRIAL",)),
            "unique_trial_id": SourceName(("TRIAL",)),
            "fixation_id": SourceName((), cn.GENERATED, "1, 2, …"),
        }
    )

    def test_a_mapped_column_is_labelled_by_its_source(self):
        assert self.NAMES.label("duration_ms") == "CURRENT_FIX_DURATION"

    def test_an_app_made_column_says_so(self):
        assert self.NAMES.label("is_regression") == "Regression (computed)"
        assert self.NAMES.label("fixation_id").endswith(cn.COMPUTED_SUFFIX)

    def test_a_reading_measure_takes_its_full_name(self):
        assert cn.canonical_label("total_fixation_duration_ms") != (
            "total_fixation_duration_ms"
        )

    def test_a_carried_column_keeps_its_name(self):
        assert self.NAMES.label("gpt2_surprisal") == "gpt2_surprisal"

    def test_a_converted_column_is_labelled_by_what_it_holds(self):
        """A width read from two edges is their difference, not their sum."""
        raw = pd.DataFrame(columns=["T", "W", "L", "R", "TOP", "BOT"])
        schema = {
            "trial": "T",
            "word_id": "W",
            "left": "L",
            "right": "R",
            "top": "TOP",
            "bottom": "BOT",
        }
        names = from_schema("words", schema, raw.columns)
        assert names.label("width") == "R − L"
        assert names.label("x") == "L"
        # The identity stays the source columns — what later phases rename by.
        assert names.display("width") == "R + L"

    def test_option_labels_are_unique(self):
        labels = self.NAMES.option_labels(["trial_id", "unique_trial_id"])
        assert len(set(labels.values())) == 2
        assert labels["trial_id"].startswith("TRIAL")

    def test_the_users_columns_come_first_and_computed_last(self):
        ordered = self.NAMES.sort_options(
            ["is_regression", "(uniform)", "duration_ms", "gpt2_surprisal"],
            first=("(uniform)",),
        )
        assert ordered == [
            "(uniform)",
            "duration_ms",
            "gpt2_surprisal",
            "is_regression",
        ]

    def test_merged_prefers_its_own_entries(self):
        words = ColumnNames({"duration_ms": SourceName(("OTHER",))})
        assert self.NAMES.merged(words).label("duration_ms") == "CURRENT_FIX_DURATION"

    def test_active_reads_the_session(self):
        session = {cn.ACTIVE_COLUMN_NAMES_KEY: {"fixations": self.NAMES.to_payload()}}
        assert cn.active(session, "fixations") == self.NAMES
        assert cn.active({}, "fixations") == cn.EMPTY


@pytest.mark.timeout(180)
def test_the_rail_shows_the_demos_own_column_names(demo_raw):
    """AppTest exposes a picker's *formatted* options — what a person sees."""
    from tests.conftest import APP_SCRIPT

    _, fixations = demo_raw
    duration = data.propose_fix_schema(fixations)["duration"]
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    color = at.selectbox(key="global_color_by")
    assert duration in color.options, color.options
    assert "duration_ms" not in color.options
    hover = at.multiselect(key="global_fixation_hover_fields")
    assert duration in hover.options, hover.options
    assert any(o.endswith(cn.COMPUTED_SUFFIX) for o in hover.options)
    # "Line" is the app's, so it sorts after the dataset's own fields.
    assert color.options[-1] == "Line" + cn.COMPUTED_SUFFIX
    metric = at.selectbox(key="global_heatmap_metric")
    assert metric.options == [duration, "Fixation count"]
    # The values are still canonical: links and saved configs are unchanged.
    assert at.session_state["global_heatmap_metric"] == "duration_ms"


def test_a_table_header_shows_the_users_name():
    from scanpath_studio import tabs

    names = ColumnNames({"duration_ms": SourceName(("CURRENT_FIX_DURATION",))})
    config = tabs.column_label_config(
        ["duration_ms", "is_regression", "my_extra"], names
    )
    assert config["duration_ms"]["label"] == "CURRENT_FIX_DURATION"
    assert config["is_regression"]["label"].endswith(cn.COMPUTED_SUFFIX)
    assert "my_extra" not in config  # already shown by its own name


@pytest.mark.timeout(240)
def test_the_keep_picker_lists_the_files_own_names(monkeypatch):
    """The add screen showed `reduced_pos` for a column the file calls
    `Reduced_POS` — a canonical name, before anything had been normalized."""
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    words = _UPLOAD_WORDS.assign(Reduced_POS=["NOUN", "VERB", "NOUN"])
    monkeypatch.setattr(
        app,
        "_read_uploaded_frame",
        lambda **kw: {
            "col_map_words": words,
            "col_map_fix": _UPLOAD_FIXATIONS,
        }.get(kw["state_prefix"], pd.DataFrame()),
    )
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
    at.run(timeout=180)
    assert not at.exception, at.exception
    keep = next(
        m for m in at.multiselect if str(m.key).startswith("wizard_keep_col_map_w")
    )
    assert "Reduced_POS" in keep.options, keep.options
    assert "reduced_pos" not in keep.options


def test_the_mapping_picker_takes_option_labels():
    """✏️ Edit dataset offers the stored *canonical* columns; it must show them
    by the user's names."""
    import inspect

    from scanpath_studio import controls

    assert "option_labels" in inspect.signature(controls.column_mapping_ui).parameters


@pytest.mark.timeout(240)
def test_the_edit_screen_offers_columns_by_their_users_names():
    """✏️ Edit dataset offers the stored frame's canonical columns; a person sees
    the names they uploaded (`CURRENT_FIX_DURATION`, not `duration_ms`)."""
    from scanpath_studio.constants import DATASET_EDITOR_OPEN_KEY
    from tests.conftest import APP_SCRIPT, pin_data_view

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["_datasets"] = {"study": _stored_upload()}
    at.session_state["data_source_choice"] = "study"
    at.session_state[DATASET_EDITOR_OPEN_KEY] = True
    pin_data_view(at)
    at.run(timeout=180)
    assert not at.exception, at.exception
    duration = at.selectbox(key="remap_study_fixations_duration")
    assert "CURRENT_FIX_DURATION" in duration.options, duration.options
    assert "duration_ms" not in duration.options
    assert duration.value == "duration_ms"  # the value is still canonical


def test_an_alias_of_the_same_source_column_is_hidden():
    """`unique_trial_id` mirrors `trial_id` (BUG-58): when both come from one
    column of the user's file, a table shows that column once."""
    names = ColumnNames(
        {
            "trial_id": SourceName(("unique_trial_id",)),
            "unique_trial_id": SourceName(("unique_trial_id",)),
            "text_id": SourceName(("PARAGRAPH",)),
            "unique_text_id": SourceName(("OTHER",)),
        }
    )
    columns = ["trial_id", "unique_trial_id", "text_id", "unique_text_id", "x"]
    assert names.aliases(columns) == {"unique_trial_id"}
    assert cn.EMPTY.aliases(columns) == set()


def test_the_axis_and_highlight_pickers_skip_internal_columns():
    from scanpath_studio import controls

    frame = pd.DataFrame({"x": [1.0], data.TEXT_ID_MAPPED: [True], "flag": [True]})
    assert data.TEXT_ID_MAPPED not in controls.numeric_field_options(frame)
    assert controls.highlight_column_options(frame) == ["flag"]


# --- Phase 2b: chips, filters, sort, figure text -----------------------------


def test_across_tables_prefers_fixations_then_words_then_raw_gaze():
    maps = {
        "raw_gaze": ColumnNames({"x": SourceName(("GAZE_X",))}),
        "words": ColumnNames(
            {"x": SourceName(("IA_LEFT",)), "text": SourceName(("IA_LABEL",))}
        ),
        "fixations": ColumnNames({"x": SourceName(("CURRENT_FIX_X",))}),
    }
    merged = cn.across_tables(maps)
    assert merged.label("x") == "CURRENT_FIX_X"
    assert merged.label("text") == "IA_LABEL"
    assert cn.across_tables({}) == cn.EMPTY


def test_active_all_reads_every_table_of_the_session():
    session = {
        cn.ACTIVE_COLUMN_NAMES_KEY: {
            "words": ColumnNames({"text": SourceName(("IA_LABEL",))}).to_payload(),
            "fixations": ColumnNames(
                {"duration_ms": SourceName(("DUR",))}
            ).to_payload(),
        }
    }
    names = cn.active_all(session)
    assert names.label("text") == "IA_LABEL"
    assert names.label("duration_ms") == "DUR"


def test_a_chip_is_named_as_the_dataset_names_its_column():
    from scanpath_studio import controls

    names = ColumnNames({"participant_id": SourceName(("RECORDING_SESSION_LABEL",))})
    assert (
        controls.chip_field_label("participant_id", names) == "RECORDING_SESSION_LABEL"
    )
    # A summary statistic is the app's and keeps its name.
    stat = next(iter(controls.SUMMARY_CHIP_FIELDS))
    assert controls.chip_field_label(stat, names) == controls.SUMMARY_CHIP_FIELDS[stat]


def test_the_trial_sort_lists_the_datasets_columns_before_the_computed_stats():
    from scanpath_studio.utils import trial_sort_keys

    fixations = pd.DataFrame(
        {
            "participant_id": ["p", "p", "p"],
            "trial_id": ["t1", "t1", "t2"],
            "duration_ms": [100.0, 200.0, 300.0],
            "cond": ["a", "a", "b"],
        }
    )
    combos = fixations[["participant_id", "trial_id", "cond"]].drop_duplicates()
    names = ColumnNames({"cond": SourceName(("CONDITION",))})
    keys = list(
        trial_sort_keys(combos, "trial_id", fixations=fixations, label_of=names.label)
    )
    assert "CONDITION" in keys
    computed = [k for k in keys if k.endswith(cn.COMPUTED_SUFFIX)]
    assert computed, keys
    assert keys.index("CONDITION") < min(keys.index(k) for k in computed)


def test_figure_labels_name_the_users_columns_and_leave_the_apps():
    names = ColumnNames(
        {
            "duration_ms": SourceName(("CURRENT_FIX_DURATION",)),
            "fixation_id": SourceName((), cn.GENERATED),
        }
    )
    labels = names.figure_labels(
        ["duration_ms", "gpt2_surprisal", "is_regression", "fixation_id"]
    )
    assert labels == {
        "duration_ms": "CURRENT_FIX_DURATION",
        "gpt2_surprisal": "gpt2_surprisal",
    }


class TestFigureText:
    """`FigureSettings.column_labels` reaches the figure's own text."""

    @pytest.fixture
    def demo(self, synthetic_words_df, synthetic_fixations_df):
        return synthetic_words_df, synthetic_fixations_df

    def _figure(self, demo, **settings):
        from scanpath_studio import plots

        words, fixations = demo
        return plots.make_scanpath_figure(
            words,
            fixations,
            canvas_width=2560,
            canvas_height=1440,
            base_font_size=16,
            **settings,
        )

    def test_the_colour_bar_takes_the_datasets_name(self, demo):
        fig = self._figure(
            demo,
            color_by="duration_ms",
            show_colorbars=True,
            column_labels={"duration_ms": "CURRENT_FIX_DURATION"},
        )
        titles = [
            trace.marker.colorbar.title.text
            for trace in fig.data
            if getattr(trace, "marker", None) is not None
            and trace.marker.colorbar is not None
            and trace.marker.colorbar.title.text
        ]
        assert "CURRENT_FIX_DURATION" in titles, titles

    def test_a_hover_row_takes_the_datasets_name(self, demo):
        fig = self._figure(
            demo,
            fixation_hover_fields=("duration_ms",),
            column_labels={"duration_ms": "CURRENT_FIX_DURATION"},
        )
        templates = " ".join(str(t.hovertemplate) for t in fig.data)
        assert "CURRENT_FIX_DURATION: " in templates

    def test_without_labels_a_figure_is_unchanged(self, demo):
        """The API passes none (phase 4), and its figures keep today's text."""
        assert (
            self._figure(demo, color_by="duration_ms").to_json()
            == self._figure(demo, color_by="duration_ms", column_labels={}).to_json()
        )

    def test_a_hover_row_never_writes_its_unit_twice(self):
        from scanpath_studio import plots

        assert plots._hover_label("total_fixation_duration_ms") == "Total fixation"
        assert plots._hover_label("my_measure_ms") == "My Measure"
        assert plots._column_title("my_measure_ms") == "My Measure (ms)"


def test_the_trial_sort_offers_an_alias_of_the_same_column_once():
    """`text_id` and `unique_text_id` read from one column sort alike."""
    from scanpath_studio.utils import trial_sort_keys

    combos = pd.DataFrame(
        {
            "participant_id": ["p", "p"],
            "trial_id": ["t1", "t2"],
            "text_id": ["a", "b"],
            "unique_text_id": ["a", "b"],
            "line_idx": [1, 1],
        }
    )
    names = ColumnNames(
        {
            "text_id": SourceName(("PARAGRAPH",)),
            "unique_text_id": SourceName(("PARAGRAPH",)),
            "line_idx": SourceName((), cn.GENERATED),
        }
    )
    keys = list(trial_sort_keys(combos, "trial_id", label_of=names.label))
    assert keys.count("PARAGRAPH") == 1
    assert not any(k.startswith("PARAGRAPH (") for k in keys)
    # A column the app made sorts after the dataset's own.
    if "Line (computed)" in keys:
        assert keys.index("Line (computed)") > keys.index("PARAGRAPH")


def test_a_converted_duration_is_named_by_its_source_in_a_figure():
    """The hover row writes "ms" after the value; "…, in ms" would say it twice."""
    names = ColumnNames(
        {
            "duration_ms": SourceName(("FPOGD",), cn.CONVERTED, "FPOGD, in ms"),
            "width": SourceName(("R", "L"), cn.CONVERTED, "R − L"),
        }
    )
    labels = names.figure_labels(["duration_ms", "width", "_text_id_mapped"])
    assert labels == {"duration_ms": "FPOGD", "width": "R − L"}


def test_a_column_called_like_a_fixed_sort_option_names_its_column():
    from scanpath_studio.utils import TRIAL_SORT_DEFAULT, trial_sort_keys

    combos = pd.DataFrame(
        {
            "participant_id": ["p", "p"],
            "trial_id": ["t1", "t2"],
            "trial_no": [2, 1],
        }
    )
    names = ColumnNames({"trial_no": SourceName((TRIAL_SORT_DEFAULT,))})
    keys = trial_sort_keys(combos, "trial_id", label_of=names.label)
    assert TRIAL_SORT_DEFAULT not in keys
    assert f"{TRIAL_SORT_DEFAULT} (trial_no)" in keys


def test_the_word_matrix_names_its_rows_as_the_dataset_does():
    from scanpath_studio import plots

    df = pd.DataFrame(
        {"participant_id": ["p1", "p2"], "word_id": [0, 0], "value": [1.0, 2.0]}
    )
    fig = plots.make_word_matrix_heatmap(
        df,
        row_col="participant_id",
        row_label="RECORDING_SESSION_LABEL",
        measure_label="TFD",
        canvas_width=800,
        base_font_size=12,
        font_family="sans-serif",
    )
    assert fig.layout.yaxis.title.text == "RECORDING_SESSION_LABEL"
    default = plots.make_word_matrix_heatmap(
        df,
        row_col="participant_id",
        measure_label="TFD",
        canvas_width=800,
        base_font_size=12,
        font_family="sans-serif",
    )
    assert default.layout.yaxis.title.text == "Participant Id"
