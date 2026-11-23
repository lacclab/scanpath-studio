"""The published L1 demo readings share one clock with their EyeLink samples."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.update_sample_data import DEFAULT_OUTPUT_DIR, extract_raw_gaze


def _report():
    return pd.DataFrame(
        {
            "participant_id": ["reader"],
            "unique_trial_id": ["reader_p"],
            "unique_paragraph_id": ["p"],
            "TRIAL_START_TIME": [1000],
            "IP_START_TIME": [1010],
            "IP_END_TIME": [1014],
            "EYE_TRACKED": ["Left"],
        }
    )


_ASC = """START 900 LEFT SAMPLES EVENTS
SAMPLES GAZE LEFT RATE 1000.00
901 11.1 12.3 500 ...
END 950 SAMPLES EVENTS
START 1000 LEFT SAMPLES EVENTS
PUPIL AREA
SAMPLES GAZE LEFT RATE 1000.00
1009 1.1 2.2 500 ...
1010 9.3 71.2 501 ...
1011 . . 0 ...
1012 3.2 . 0 ...
1013 -3.1 208.8 502 ...
1014 2.2 3.3 500 ...
END 1020 SAMPLES EVENTS
"""


@pytest.mark.parametrize(
    ("declared", "column"), [("AREA", "pupil_area"), ("DIAMETER", "pupil_diameter")]
)
def test_extracts_the_report_interval_on_the_trial_clock(tmp_path, declared, column):
    (tmp_path / "reader_clean.asc").write_text(
        _ASC.replace("PUPIL AREA", f"PUPIL {declared}")
    )
    gaze = extract_raw_gaze(_report(), tmp_path)
    assert gaze["timestamp_ms"].tolist() == [10, 11, 12, 13]
    np.testing.assert_equal(gaze["x"].to_numpy(), [9.3, np.nan, 3.2, -3.1])
    np.testing.assert_equal(gaze["y"].to_numpy(), [71.2, np.nan, np.nan, 208.8])
    assert gaze[column].tolist() == [501, 0, 0, 502]
    assert set(gaze["eye"]) == {"Left"}


@pytest.mark.parametrize(
    ("asc", "problem"),
    [
        (_ASC.replace("START 1000", "START 999"), "no matching recording block"),
        (_ASC.replace("GAZE LEFT", "GAZE RIGHT"), "monocular GAZE LEFT"),
        (_ASC.replace("GAZE LEFT", "HREF LEFT"), "monocular GAZE LEFT"),
        (_ASC.replace("PUPIL AREA", "PUPIL UNKNOWN"), "pupil measurement type"),
        (_ASC.replace("END 1020 SAMPLES EVENTS", ""), "Missing END"),
    ],
)
def test_mismatched_or_incomplete_recordings_stop_the_build(tmp_path, asc, problem):
    (tmp_path / "reader.asc").write_text(asc)
    with pytest.raises(ValueError, match=problem):
        extract_raw_gaze(_report(), tmp_path)


def test_bundled_samples_match_the_public_recordings_and_report_windows():
    raw = pd.read_parquet(DEFAULT_OUTPUT_DIR / "raw_gaze.parquet")
    pd.testing.assert_frame_equal(raw, pd.read_csv(DEFAULT_OUTPUT_DIR / "raw_gaze.csv"))
    fixes = pd.read_parquet(DEFAULT_OUTPUT_DIR / "fixations.parquet")
    words = pd.read_parquet(DEFAULT_OUTPUT_DIR / "ia.parquet")
    keys = ["participant_id", "unique_trial_id"]
    readings = fixes.groupby(keys)
    gaze = raw.groupby(keys)
    assert set(gaze.groups) == set(readings.groups) == set(words.groupby(keys).groups)
    assert len(gaze) == 24
    assert raw["unique_paragraph_id"].nunique() == 12
    assert (
        gaze["unique_paragraph_id"]
        .first()
        .equals(readings["unique_paragraph_id"].first())
    )
    bounds = readings[["IP_START_TIME", "IP_END_TIME", "TRIAL_START_TIME"]].first()
    times = gaze["timestamp_ms"].agg(["min", "max"])
    assert (times["min"] >= bounds["IP_START_TIME"] - bounds["TRIAL_START_TIME"]).all()
    assert (times["max"] < bounds["IP_END_TIME"] - bounds["TRIAL_START_TIME"]).all()
    assert gaze["timestamp_ms"].diff().dropna().eq(1).all()
    assert gaze.size().equals(bounds["IP_END_TIME"] - bounds["IP_START_TIME"])
    assert len(raw) == 401_200
    assert raw[["x", "y"]].isna().any(axis=1).sum() == 14_628
    assert gaze["eye"].first().equals(readings["EYE_TRACKED"].first())
    # First paragraph sample for each reader, transcribed from the two ASCs.
    first = raw.groupby("participant_id", sort=True).first()
    assert list(first.itertuples(name=None)) == [
        (
            "l37_273",
            "l37_273_2_2_1_Adv",
            "2_2_1_Adv",
            381.6,
            208.8,
            5835,
            1362,
            "Right",
        ),
        ("l7_183", "l7_183_2_2_1_Adv", "2_2_1_Adv", 369.9, 208.5, 7165, 1501, "Left"),
    ]


def test_demo_highlights_match_the_released_per_word_labels():
    words = pd.read_parquet(DEFAULT_OUTPUT_DIR / "ia.parquet")
    assert set(words["auxiliary_span_type"]) == {"critical", "distractor", "outside"}
    for flag, label in (("is_in_aspan", "critical"), ("is_in_dspan", "distractor")):
        assert words[flag].equals(words["auxiliary_span_type"].eq(label))
