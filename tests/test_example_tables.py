"""Import the example tables and inspect the resulting dataset coverage."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from scanpath_studio import data, synthetic
from scanpath_studio.tabs import _dataset_statistics


def _example_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The two tables as files would give them: written as CSV, read back."""
    words, fixations = synthetic.example_import_tables()
    return (
        pd.read_csv(io.StringIO(words.to_csv(index=False))),
        pd.read_csv(io.StringIO(fixations.to_csv(index=False))),
    )


class TestTheExampleMapsItself:
    def test_every_column_is_auto_detected(self):
        words, fixations = _example_frames()
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
        words, fixations = _example_frames()
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


class TestAvailableWithThisDataset:
    def test_gaze_only_trials_have_their_own_average(self):
        gaze = pd.DataFrame({"participant_id": ["p", "p"], "trial_id": ["t", "t"]})
        stats = _dataset_statistics(
            pd.DataFrame(), pd.DataFrame(), gaze, ("gaze-only",)
        )
        assert stats["recordings"] == {
            "fixations": (0, 0),
            "words": (0, 0),
            "raw_gaze": (2, 1),
        }
        means = stats["stats_df"].set_index("Metric")["Mean"].to_dict()
        assert means == {"Trials per participant": 1, "Gaze samples per trial": 2}

    def test_coverage_counts_each_trial_once_and_averages_only_recorded_rows(self):
        words, fixations = synthetic.make_multipart_synthetic_data()
        gaze = pd.concat([fixations, fixations.assign(trial_id="samples-only")])
        stats = _dataset_statistics(words, fixations, gaze, ("mixed-coverage",))
        assert stats["n_trials"] == 2
        assert stats["recordings"]["fixations"] == (len(fixations), 1)
        assert stats["recordings"]["raw_gaze"] == (len(gaze), 2)
        assert len(stats["parts"]) == 4
        assert stats["stats_df"].set_index("Metric").at[
            "Fixations per trial", "Mean"
        ] == len(fixations)


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

    def test_the_wizard_offers_no_example_download(self, monkeypatch):
        """The add screen offers no example download."""
        at = self._boot(monkeypatch, {})
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert not [b for b in at.download_button if b.key == "wizard_example_download"]

    def test_the_example_adds_with_no_manual_mapping(self, monkeypatch):
        from tests.conftest import answer_setup_step

        words, fixations = _example_frames()
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
        assert any("Eye-tracking data" in m.value for m in at.markdown)
        at.button(key="data_inspect_words").click().run(timeout=90)
        assert not at.exception, at.exception
        measures = next(
            panel for panel in at.expander if panel.label.startswith("Reading measures")
        )
        text = "\n".join(m.value for m in measures.markdown)
        assert "- Total fixation duration — TFD" in text
        assert "- First fixation duration — FFD" in text
