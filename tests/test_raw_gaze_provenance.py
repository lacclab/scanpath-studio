"""VIZ-50: synthesized raw gaze says so at the plot and in its exports, and a
raw-gaze switch with no samples on this trial says why it draws nothing."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import app
from scanpath_studio.constants import DEMO_CHOICE, MANUAL_SAMPLE_CHOICE
from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.tabs import _raw_gaze_missing_note, _synthetic_raw_gaze_plot_note
from scanpath_studio.utils import reading_key
from tests.conftest import APP_SCRIPT

#: The one demo trial the bundled (synthesized) samples cover, and one they don't.
PARTICIPANT = "l37_1129"
WITH_SAMPLES = "l37_1129_2_2_2_Adv_r0"
WITHOUT_SAMPLES = "l37_1129_2_2_1_Adv_r0"


class TestTheCatalogueFlag:
    def test_only_the_demo_is_synthesized(self):
        note = app.synthesized_raw_gaze_note(DEMO_CHOICE)
        assert "synthesized" in note
        # The note the 🗂️ Data page shows is the same sentence.
        assert note == app.dataset_about(DEMO_CHOICE)["reading_note"]
        assert app.synthesized_raw_gaze_note(MANUAL_SAMPLE_CHOICE) == ""
        assert app.synthesized_raw_gaze_note("My upload") == ""
        assert app.synthesized_raw_gaze_note(None) == ""

    def test_the_plot_note_needs_drawn_synthesized_samples(self):
        assert _synthetic_raw_gaze_plot_note(drawn_a=False, source_a=DEMO_CHOICE) == ""
        assert _synthetic_raw_gaze_plot_note(drawn_a=True, source_a="Upload") == ""
        note = _synthetic_raw_gaze_plot_note(drawn_a=True, source_a=DEMO_CHOICE)
        assert "Synthetic raw-gaze illustration" in note
        # Compare: B's samples from the demo, A's from an upload.
        assert _synthetic_raw_gaze_plot_note(
            drawn_a=True, source_a="Upload", drawn_b=True, source_b=DEMO_CHOICE
        )


class TestTheMissingSamplesNote:
    def test_it_says_the_samples_are_missing_here(self):
        trial = _raw_gaze_missing_note(True, trial_has_raw_gaze=False)
        assert trial.startswith("No raw-gaze samples on this trial.")
        screen = _raw_gaze_missing_note(True, trial_has_raw_gaze=False, screen=True)
        assert screen.startswith("No raw-gaze samples on this screen.")
        assert _raw_gaze_missing_note(True, trial_has_raw_gaze=True) == ""


def test_the_bundle_plot_config_records_synthesized_samples():
    words = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "text_id": ["x"],
            "word_id": [1],
            "text": ["the"],
            "line_idx": [1],
            "x": [100],
            "y": [50],
            "width": [80],
            "height": [40],
        }
    )
    raw = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "x": [110.0, 120.0],
            "y": [60.0, 61.0],
            "timestamp_ms": [0.0, 1.0],
        }
    )
    combos = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
    zip_bytes, progress = bulk_export(
        combos,
        words,
        pd.DataFrame(),
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings={"show_raw_gaze": True, "raw_gaze_synthesized": True},
        options=ExportOptions(include_png=False, include_svg=False, include_pdf=False),
        raw_gaze=raw,
    )
    assert progress.errors == []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("plot_config.json"))
        config = json.loads(zf.read(name))
    assert config["raw_gaze"] == {"points": 2, "synthesized": True}


def _demo(trial: str) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["participant"] = PARTICIPANT
    at.query_params["trial_id"] = trial
    at.query_params["show_raw_gaze"] = "1"
    return at.run()


@pytest.mark.parametrize(
    ("trial", "synthetic", "missing"),
    [(WITH_SAMPLES, True, False), (WITHOUT_SAMPLES, False, True)],
)
def test_the_demo_says_what_its_raw_gaze_is_at_the_plot(trial, synthetic, missing):
    at = _demo(trial)
    assert not at.exception, at.exception
    assert at.session_state["single_trial_id"] == reading_key(PARTICIPANT, trial)
    assert at.session_state["global_show_raw_gaze"] is True
    captions = " ".join(str(c.value) for c in at.caption)
    warnings = " ".join(str(w.value) for w in at.warning)
    assert ("Synthetic raw-gaze illustration" in captions) is synthetic
    assert ("No raw-gaze samples on this trial" in warnings) is missing
