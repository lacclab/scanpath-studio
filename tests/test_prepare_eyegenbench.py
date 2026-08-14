from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_eyegenbench.py"
spec = importlib.util.spec_from_file_location("prepare_eyegenbench", SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

TEXTS = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1"],
        "text": ["ab cd"],
        "text_language": ["en"],
        "ia_list": [["ab", "cd"]],
    }
)
FIX = pd.DataFrame(
    {
        "unique_trial_id": ["t1", "t1"],
        "unique_participant_id": ["r1", "r1"],
        "unique_paragraph_id": ["p1", "p1"],
        "fix_index": [0, 1],
        "ia_index": [0, 1],
        "fix_duration": [200, 180],
        "fix_landing_position": [0.5, 0.5],
    }
)
PARTS = pd.DataFrame({"unique_participant_id": ["r1"], "participant_language": ["de"]})


def test_build_bundle_writes_three_parquets_and_an_entry(tmp_path):
    entry = prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    for table in ("words", "fixations", "participants"):
        assert (tmp_path / "PoTeC" / f"{table}.parquet").is_file()
    assert entry["name"] == "PoTeC"
    assert entry["geometry_source"] == "reconstructed"
    assert entry["n_readers"] == 1 and entry["n_fixations"] == 2
    assert entry["monitor"] == [1680, 1050]


def test_build_bundle_places_fixations_inside_their_boxes(tmp_path):
    prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    words = pd.read_parquet(tmp_path / "PoTeC" / "words.parquet")
    fixations = pd.read_parquet(tmp_path / "PoTeC" / "fixations.parquet")
    box = words[words["ia_index"] == 0].iloc[0]
    placed = fixations[fixations["ia_index"] == 0].iloc[0]
    assert box["start_x"] <= placed["x"] <= box["end_x"]


def test_write_manifest_merges_entries_across_runs(tmp_path):
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [1, 2]}])
    prep.write_manifest(tmp_path, [{"name": "B", "monitor": [3, 4]}])
    names = [
        d["name"]
        for d in json.loads((tmp_path / "manifest.json").read_text())["datasets"]
    ]
    assert sorted(names) == ["A", "B"]


def test_write_manifest_replaces_a_rerun_dataset(tmp_path):
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [1, 2]}])
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [9, 9]}])
    datasets = json.loads((tmp_path / "manifest.json").read_text())["datasets"]
    assert len(datasets) == 1 and datasets[0]["monitor"] == [9, 9]


def test_free_space_guard_stops_before_filling_the_disk(monkeypatch):
    monkeypatch.setattr(prep, "_free_gb", lambda path: 10.0)
    with pytest.raises(prep.OutOfDiskError, match="15 GB"):
        prep.check_free_space(Path("."))


def _two_readings(
    participant: str, first_trial: str, second_trial: str
) -> pd.DataFrame:
    """Four fixation rows: two readings of p1 (ia_index 0, 1) by one reader."""
    return pd.DataFrame(
        {
            "unique_trial_id": [first_trial] * 2 + [second_trial] * 2,
            "unique_participant_id": [participant] * 4,
            "unique_paragraph_id": ["p1"] * 4,
            "fix_index": [0, 1, 0, 1],
            "ia_index": [0, 1, 0, 1],
            "fix_duration": [200, 180, 190, 170],
            "fix_landing_position": [0.5, 0.5, 0.5, 0.5],
        }
    )


def test_repeated_readings_do_not_inflate_fixations_across_participants(tmp_path):
    """Two readers, each reading p1 twice -- R17 regression (round 1 fix).

    Word rows are stimulus-level (one shared layout, not one per reader), so
    the 2nd-reading key must get exactly ONE words copy, not one per
    participant -- otherwise place_fixations' inner join multiplies every
    2nd-reading fixation by the number of participants who repeated.
    """
    fix = pd.concat(
        [_two_readings("r1", "r1t1", "r1t2"), _two_readings("r2", "r2t1", "r2t2")],
        ignore_index=True,
    )
    parts = pd.DataFrame(
        {"unique_participant_id": ["r1", "r2"], "participant_language": ["de", "de"]}
    )

    entry = prep.build_bundle("PoTeC", fix, TEXTS, parts, None, tmp_path)

    assert entry["n_fixations"] == 8
    fixations = pd.read_parquet(tmp_path / "PoTeC" / "fixations.parquet")
    words = pd.read_parquet(tmp_path / "PoTeC" / "words.parquet")
    assert len(fixations) == 8
    assert words.duplicated(["unique_paragraph_id", "ia_index"]).sum() == 0


def test_disambiguate_repeated_readings_gives_each_reading_its_own_key():
    fix_df = pd.DataFrame(
        {
            "unique_participant_id": ["r1", "r1", "r1", "r1"],
            "unique_paragraph_id": ["p1", "p1", "p1", "p1"],
            "eyegenbench_trial_id": ["t1", "t1", "t2", "t2"],
            "ia_index": [0, 1, 0, 1],
        }
    )
    words = pd.DataFrame({"unique_paragraph_id": ["p1", "p1"], "ia_index": [0, 1]})

    new_fix, new_words, n_repeated = prep._disambiguate_repeated_readings(fix_df, words)

    assert n_repeated == 1
    assert set(new_fix["unique_paragraph_id"]) == {"p1", "p1__r2"}
    assert (
        new_fix.loc[new_fix["eyegenbench_trial_id"] == "t1", "unique_paragraph_id"]
        == "p1"
    ).all()
    assert (
        new_fix.loc[new_fix["eyegenbench_trial_id"] == "t2", "unique_paragraph_id"]
        == "p1__r2"
    ).all()
    assert set(new_words["unique_paragraph_id"]) == {"p1", "p1__r2"}
    assert len(new_words[new_words["unique_paragraph_id"] == "p1"]) == 2
    assert len(new_words[new_words["unique_paragraph_id"] == "p1__r2"]) == 2


def test_disambiguate_repeated_readings_is_a_noop_for_single_readings():
    fix_df = pd.DataFrame(
        {
            "unique_participant_id": ["r1", "r1"],
            "unique_paragraph_id": ["p1", "p1"],
            "eyegenbench_trial_id": ["t1", "t1"],
            "ia_index": [0, 1],
        }
    )
    words = pd.DataFrame({"unique_paragraph_id": ["p1", "p1"], "ia_index": [0, 1]})

    new_fix, new_words, n_repeated = prep._disambiguate_repeated_readings(fix_df, words)

    assert n_repeated == 0
    assert new_fix["unique_paragraph_id"].tolist() == ["p1", "p1"]
    assert set(new_words["unique_paragraph_id"]) == {"p1"}
