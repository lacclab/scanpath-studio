"""DATA-67: the add wizard's example tables, and *Available with this dataset*.

**Download example tables** gives a new user an AOI table and a fixation table
that import with no manual mapping, and a README naming every column's unit and
what the IDs mean. The pair is the synthetic trial (`synthetic.py`), so it adds
no committed files. Once a dataset is added, the *What's in…* section opens with
four lines saying what it supports: scanpaths, supplied reading measures, raw
gaze coverage and multipart screens.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio import data, synthetic
from scanpath_studio.tabs import dataset_capabilities


def _example_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The two CSVs exactly as a user gets them: unzipped and read back."""
    with zipfile.ZipFile(io.BytesIO(synthetic.example_import_zip())) as archive:
        assert sorted(archive.namelist()) == [
            "README.md",
            synthetic.EXAMPLE_AOI_FILE,
            synthetic.EXAMPLE_FIXATION_FILE,
        ]
        words = pd.read_csv(archive.open(synthetic.EXAMPLE_AOI_FILE))
        fixations = pd.read_csv(archive.open(synthetic.EXAMPLE_FIXATION_FILE))
        readme = archive.read("README.md").decode("utf-8")
    return words, fixations, readme


class TestTheExampleMapsItself:
    def test_every_column_is_auto_detected(self):
        words, fixations, _ = _example_frames()
        word_schema = data.infer_word_schema(words)
        fix_schema = data.infer_fix_schema(fixations)
        assert word_schema is not None and fix_schema is not None
        # Every column the files carry is claimed by a field: nothing is left
        # for the user to map, keep or drop by hand.
        assert set(words.columns) <= {v for v in word_schema.values() if v}
        assert set(fixations.columns) <= {v for v in fix_schema.values() if v}
        assert word_schema["measure_tfd"] == "total_fixation_duration_ms"
        assert word_schema["measure_ffd"] == "first_fixation_ms"

    def test_it_normalizes_to_the_hand_traced_trial(self):
        words, fixations, _ = _example_frames()
        norm_words = data.normalize_words(words, data.infer_word_schema(words))
        norm_fix = data.normalize_fixations(fixations, data.infer_fix_schema(fixations))
        assert data.trial_keys(norm_words) == data.trial_keys(norm_fix)
        assert len(norm_words) == 6 and len(norm_fix) == 9
        assert data.brought_reading_measures(norm_words) == [
            "total_fixation_duration_ms",
            "first_fixation_ms",
        ]
        tfd = norm_words.set_index("word_id")["total_fixation_duration_ms"]
        assert tfd.to_dict() == synthetic.EXPECTED["total_fixation_duration_ms"]

    def test_the_readme_explains_every_column_and_its_unit(self):
        words, fixations, readme = _example_frames()
        for column in [*words.columns, *fixations.columns]:
            assert f"`{column}`" in readme, column
        assert "pixels" in readme and "milliseconds" in readme
        assert "participant_id + trial_id" in readme


class TestAvailableWithThisDataset:
    def test_the_example_lists_its_measures(self):
        words, fixations, _ = _example_frames()
        lines = dataset_capabilities(
            data.normalize_words(words, data.infer_word_schema(words)),
            data.normalize_fixations(fixations, data.infer_fix_schema(fixations)),
            None,
        )
        assert len(lines) == 4
        assert "over the text, for 1 trial" in lines[0]
        assert "TFD, First fixation duration — FFD" in lines[1]
        assert lines[2].endswith("**Raw gaze:** none")
        assert lines[3].endswith("one per trial")

    def test_no_measures_and_raw_gaze_only(self):
        gaze = pd.DataFrame(
            {"participant_id": ["p", "p"], "trial_id": ["t", "t"], "x": [1, 2]}
        )
        lines = dataset_capabilities(None, None, gaze)
        assert "no fixations; raw gaze is drawn instead, for 1 trial" in lines[0]
        assert "none supplied" in lines[1]
        assert "1 of 1 trial" in lines[2]

    def test_multipart_screens_are_counted(self):
        words, fixations = synthetic.make_multipart_synthetic_data()
        lines = dataset_capabilities(words, fixations, None)
        assert lines[3].endswith("2 screens across 1 trial")


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(240)
class TestTheWizard:
    def _boot(self, monkeypatch, frames: dict):
        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        return at

    def test_the_download_sits_beside_the_import_guidance(self, monkeypatch):
        at = self._boot(monkeypatch, {})
        at.run(timeout=90)
        assert not at.exception, at.exception
        buttons = [
            b for b in at.get("download_button") if b.key == "wizard_example_download"
        ]
        assert buttons and buttons[0].proto.label == "Download example tables"

    def test_the_example_adds_with_no_manual_mapping(self, monkeypatch):
        from tests.conftest import answer_setup_step

        words, fixations, _ = _example_frames()
        at = self._boot(monkeypatch, {"col_map_words": words, "col_map_fix": fixations})
        answer_setup_step(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        # The pipeline accepted the proposed mapping as it stands.
        assert at.session_state["_wizard_problems_last"] == []
        assert at.session_state["col_map_words_measure_tfd"] == (
            "total_fixation_duration_ms"
        )
        finalize = next(b for b in at.button if b.key == "wizard_finalize")
        assert not finalize.disabled
        finalize.click()
        at.run(timeout=90)
        assert not at.exception, at.exception
        from tests.conftest import open_data_view

        open_data_view(at, timeout=90)
        assert not at.exception, at.exception
        text = " ".join(c.value for c in at.caption)
        assert "Available with this dataset" in text
        assert (
            "**Reading measures:** Total fixation duration — TFD, First fixation duration — FFD"
            in text
        )
