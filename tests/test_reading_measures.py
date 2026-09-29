"""AN-32 — Corpus Analysis shows the reading measures a dataset brings.

The page computes no FFD, TFD, … of its own. Each measure is an optional field
of the AOI table, mapped on ➕ Add dataset and ✏️ Edit dataset (two lines under
the word box), auto-detected from EyeLink's interest-area report names. With
none mapped the page says so and greys its sections.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import data
from scanpath_studio.data import (
    READING_MEASURE_FIELDS,
    READING_MEASURE_KEYS,
    normalize_words,
    propose_word_schema,
)


def _ia() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "IA_ID": [1, 2],
            "IA_LABEL": ["a", "b"],
            "IA_LEFT": [0, 10],
            "IA_RIGHT": [10, 20],
            "IA_TOP": [0, 0],
            "IA_BOTTOM": [10, 10],
            "IA_DWELL_TIME": [250, 0],
            "IA_FIRST_FIXATION_DURATION": [200, None],
            "IA_SKIP": [0, 1],
        }
    )


class TestTheMapping:
    def test_eyelink_names_are_auto_detected(self):
        schema = propose_word_schema(_ia())
        assert schema["measure_tfd"] == "IA_DWELL_TIME"
        assert schema["measure_ffd"] == "IA_FIRST_FIXATION_DURATION"
        assert schema["measure_skip"] == "IA_SKIP"
        assert schema["measure_rpd"] is None

    def test_the_bundled_eyelink_report_maps_its_measures(self):
        words, _ = data.load_sample_data()
        schema = propose_word_schema(words)
        mapped = {key for key in READING_MEASURE_KEYS if schema[key]}
        assert {"measure_tfd", "measure_ffd", "measure_fprt", "measure_rpd"} <= mapped

    def test_a_mapped_measure_lands_under_its_canonical_column(self):
        raw = _ia().rename(columns={"IA_DWELL_TIME": "dwell"})
        schema = {**propose_word_schema(raw), "measure_tfd": "dwell"}
        out = normalize_words(raw, schema)
        assert out["total_fixation_duration_ms"].tolist() == [250, 0]
        assert out["skip_flag"].tolist() == [False, True]

    def test_a_cleared_measure_is_absent_even_where_the_report_has_it(self):
        schema = {**propose_word_schema(_ia()), "measure_tfd": None}
        out = normalize_words(_ia(), schema)
        assert "total_fixation_duration_ms" not in out.columns
        assert "first_fixation_ms" in out.columns

    def test_a_schema_from_before_keeps_the_passthrough(self):
        schema = {
            k: v
            for k, v in propose_word_schema(_ia()).items()
            if k not in READING_MEASURE_KEYS
        }
        out = normalize_words(_ia(), schema)
        assert "total_fixation_duration_ms" in out.columns

    def test_every_measure_is_a_corpus_measure(self):
        from scanpath_studio.aggregation import MEASURES

        columns = {m.column for m in MEASURES.values() if m.per_word}
        assert {column for _k, column, *_ in READING_MEASURE_FIELDS} == columns

    def test_the_editor_seeds_stored_measures(self):
        from scanpath_studio.tabs import _WORD_REMAP_CANON, _remap_proposed

        frame = pd.DataFrame(
            columns=["participant_id", "trial_id", "total_fixation_duration_ms"]
        )
        # A schema saved before AN-32 names no measure key; the column is
        # still what the dataset brought.
        proposed = _remap_proposed(
            {"trial": "trial_id"}, frame.columns, _WORD_REMAP_CANON
        )
        assert proposed["measure_tfd"] == "total_fixation_duration_ms"
        assert proposed["measure_ffd"] is None


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(240)
class TestThePages:
    def test_the_add_screen_shows_the_measures_on_two_lines(self, monkeypatch):
        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        words, fixations = app.load_sample_data()
        frames = {"col_map_words": words, "col_map_fix": fixations}
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=90)
        assert not at.exception, at.exception
        keys = {s.key for s in at.selectbox}
        assert {f"col_map_words_{key}" for key in READING_MEASURE_KEYS} <= keys
        assert at.session_state["col_map_words_measure_tfd"] == "IA_DWELL_TIME"

    def test_no_measures_greys_the_corpus_page(self):
        from tests.test_apptest import _make_apptest

        at = _make_apptest(synthetic=True)
        at.session_state["main_nav"] = "Corpus Analysis"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert any("No reading measures" in i.value for i in at.info)
        assert "ptext_measure" not in {s.key for s in at.selectbox}
        assert "corpus_map_measures" in {b.key for b in at.button}

    def test_the_demo_shows_only_what_it_uploaded(self):
        from tests.test_apptest import _make_apptest

        at = _make_apptest()
        at.session_state["main_nav"] = "Corpus Analysis"
        at.run(timeout=90)
        assert not at.exception, at.exception
        picker = next(s for s in at.selectbox if s.key == "ptext_measure")
        # The demo's report has no single-fixation or landing measures, and
        # the page no longer derives them.
        labels = " ".join(picker.options)
        assert "Total fixation duration" in labels
        assert "Single-fixation" not in labels and "landing" not in labels.lower()


class TestTheKeepPicker:
    """AN-32 follow-up: a measure mapped on the *Reading measures* lines was
    also offered — and pre-kept — as an extra field under its canonical name."""

    def test_a_mapped_measure_is_not_an_extra_field(self):
        words, _ = data.load_sample_data()
        schema = propose_word_schema(words)
        cats = data.categorize_columns(words, schema, data.WORD_OPTIONAL_FIELDS)
        offered = {d["source"] for d in cats["detected_optional"]}
        assert "IA_DWELL_TIME" not in offered
        assert "IA_FIRST_FIXATION_DURATION" not in offered

    def test_a_source_listed_twice_is_offered_once(self):
        raw = pd.DataFrame(
            columns=["IA_SECOND_RUN_DWELL_TIME", "IA_REGRESSION_IN_COUNT"]
        )
        cats = data.categorize_columns(raw, {}, data.WORD_OPTIONAL_FIELDS)
        sources = [d["source"] for d in cats["detected_optional"]]
        assert sorted(sources) == sorted(set(sources))

    def test_leftover_measures_are_not_kept_by_default(self, monkeypatch):
        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        words, fixations = app.load_sample_data()
        frames = {"col_map_words": words, "col_map_fix": fixations}
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=90)
        assert not at.exception, at.exception
        kept = set(at.session_state["wizard_keep_col_map_words"])
        assert not kept & {
            "IA_DWELL_TIME",
            "IA_LAST_RUN_DWELL_TIME",
            "TRIAL_DWELL_TIME",
        }
        # A linguistic feature the Corpus page uses is still pre-kept.
        if "word_length" in words.columns:
            assert "word_length" in kept
