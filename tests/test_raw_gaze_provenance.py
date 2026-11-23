"""Raw-gaze provenance in exports and the recording shown on the demo plot."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.tabs import _raw_gaze_missing_note
from scanpath_studio.utils import reading_key
from tests.conftest import APP_SCRIPT


class TestTheMissingSamplesNote:
    def test_it_says_the_samples_are_missing_here(self):
        trial = _raw_gaze_missing_note(True, trial_has_raw_gaze=False)
        assert trial.startswith("No raw-gaze samples on this trial.")
        screen = _raw_gaze_missing_note(True, trial_has_raw_gaze=False, screen=True)
        assert screen.startswith("No raw-gaze samples on this screen.")
        assert _raw_gaze_missing_note(True, trial_has_raw_gaze=True) == ""


@pytest.mark.parametrize("synthesized", [False, True])
def test_the_bundle_plot_config_records_the_sample_provenance(synthesized):
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
        settings={
            "show_raw_gaze": True,
            **({"raw_gaze_synthesized": True} if synthesized else {}),
        },
        options=ExportOptions(include_png=False, include_svg=False, include_pdf=False),
        raw_gaze=raw,
    )
    assert progress.errors == []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("plot_config.json"))
        config = json.loads(zf.read(name))
    assert config["raw_gaze"] == {
        "available": True,
        "points": 2,
        "synthesized": synthesized,
        "color": "#888888",
        "marker_size": 4.0,
        "opacity": 0.6,
    }


def _demo(trial: str) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["participant"] = "l37_273"
    at.query_params["trial_id"] = trial
    at.query_params["show_raw_gaze"] = "1"
    return at.run()


def test_the_demo_shows_recorded_samples_at_the_plot():
    trial = "l37_273_2_2_2_Adv"
    at = _demo(trial)
    assert not at.exception, at.exception
    assert at.session_state["single_trial_id"] == reading_key("l37_273", trial)
    assert at.session_state["global_show_raw_gaze"] is True
    assert not any("Synthetic raw-gaze illustration" in c.value for c in at.caption)
    assert not any("No raw-gaze samples" in w.value for w in at.warning)
