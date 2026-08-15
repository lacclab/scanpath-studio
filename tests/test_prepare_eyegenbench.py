from __future__ import annotations

import importlib.util
import json
import os
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


# --- Round 3 fixes -----------------------------------------------------

# A text_df carrying real box columns (one row per (paragraph, ia_index), as
# real EyeGenBench frames do -- see the R23/R24 tests in
# test_eyegenbench_geometry.py) whose coordinates exceed a hypothetical
# 1920x1080 default screen, for an UNKNOWN corpus (no DISPLAY_SPECS entry).
TEXT_LARGE_REAL_BOXES = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1", "p1"],
        "ia_index": [0, 1],
        "text": ["ab cd", "ab cd"],
        "text_language": ["en", "en"],
        "ia_list": [["ab", "cd"], ["ab", "cd"]],
        "start_x": [10.0, 2400.0],
        "start_y": [20.0, 20.0],
        "end_x": [60.0, 2500.0],
        "end_y": [40.0, 40.0],
    }
)


def test_monitor_is_published_when_a_display_spec_exists(tmp_path):
    """Item 2 / R26, case 1: a published spec is itself a measurement."""
    entry = prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    assert entry["monitor_source"] == "published"
    assert entry["monitor"] == [1680, 1050]
    words = pd.read_parquet(tmp_path / "PoTeC" / "words.parquet")
    assert (words["end_x"] <= entry["monitor"][0]).all()
    assert (words["end_y"] <= entry["monitor"][1]).all()


def test_monitor_is_derived_from_real_boxes_when_no_spec_is_published(tmp_path):
    """Item 2 / R26, case 2: no published spec, real boxes exceeding the
    1920x1080 default -- the monitor must expand to cover them, never crop.
    """
    entry = prep.build_bundle(
        "cfiltsarcasm", FIX, TEXT_LARGE_REAL_BOXES, PARTS, None, tmp_path
    )
    assert entry["geometry_source"] == "real"
    assert entry["monitor_source"] == "derived-from-boxes"
    assert entry["monitor"][0] >= 2500
    words = pd.read_parquet(tmp_path / "cfiltsarcasm" / "words.parquet")
    assert (words["end_x"] <= entry["monitor"][0]).all()
    assert (words["end_y"] <= entry["monitor"][1]).all()


def test_monitor_falls_back_to_the_default_when_nothing_is_known(tmp_path):
    """Item 2 / R26, case 3: no spec, no real boxes -- the reconstructed
    (here: synthesized, since the corpus is unknown) fallback.
    """
    entry = prep.build_bundle("cfiltsarcasm", FIX, TEXTS, PARTS, None, tmp_path)
    assert entry["geometry_source"] == "synthesized"
    assert entry["monitor_source"] == "default"
    assert entry["monitor"] == [1920, 1080]
    words = pd.read_parquet(tmp_path / "cfiltsarcasm" / "words.parquet")
    assert (words["end_x"] <= entry["monitor"][0]).all()
    assert (words["end_y"] <= entry["monitor"][1]).all()


def test_monospaced_is_omitted_for_real_geometry(tmp_path):
    """Item 3 / R25: `monospaced` describes a reconstructed-layout spec that
    was never built for a real-geometry corpus -- must not be asserted.
    """
    entry = prep.build_bundle(
        "cfiltsarcasm", FIX, TEXT_LARGE_REAL_BOXES, PARTS, None, tmp_path
    )
    assert entry["geometry_source"] == "real"
    assert "monospaced" not in entry


def test_monospaced_is_present_for_reconstructed_geometry(tmp_path):
    """R5 (round 1), pinned: still present when the geometry isn't real."""
    entry = prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    assert entry["geometry_source"] == "reconstructed"
    assert entry["monospaced"] is True


def test_n_readers_excludes_a_reader_whose_every_fixation_was_dropped(tmp_path):
    """Item 5b: count what was actually written, not the input frame.

    `r_dropped`'s only fixation targets an out-of-range ia_index that no word
    box covers, so place_fixations' inner join drops it entirely -- it must
    not still be counted as a reader in the bundle.
    """
    fix_with_a_fully_dropped_reader = pd.concat(
        [
            FIX,
            pd.DataFrame(
                {
                    "unique_trial_id": ["t9"],
                    "unique_participant_id": ["r_dropped"],
                    "unique_paragraph_id": ["p1"],
                    "fix_index": [0],
                    "ia_index": [99],
                    "fix_duration": [150],
                    "fix_landing_position": [0.5],
                }
            ),
        ],
        ignore_index=True,
    )

    entry = prep.build_bundle(
        "PoTeC", fix_with_a_fully_dropped_reader, TEXTS, PARTS, None, tmp_path
    )

    fixations = pd.read_parquet(tmp_path / "PoTeC" / "fixations.parquet")
    assert "r_dropped" not in set(fixations["unique_participant_id"])
    assert entry["n_readers"] == 1


def test_n_texts_counts_distinct_texts_not_reading_instances(tmp_path):
    """R27 regression: one text, read twice by each of 2 readers.

    R17 gives the 2nd reading its own `p1__r2` paragraph key so it keeps its
    own geometry in `words.parquet` -- but that key is a reading instance,
    not a new text. `n_texts` must strip the suffix before counting: the
    corpus has exactly one distinct text, and `repeated_readings` (2) already
    carries the reading count separately.
    """
    fix = pd.concat(
        [_two_readings("r1", "r1t1", "r1t2"), _two_readings("r2", "r2t1", "r2t2")],
        ignore_index=True,
    )
    parts = pd.DataFrame(
        {"unique_participant_id": ["r1", "r2"], "participant_language": ["de", "de"]}
    )

    entry = prep.build_bundle("PoTeC", fix, TEXTS, parts, None, tmp_path)

    words = pd.read_parquet(tmp_path / "PoTeC" / "words.parquet")
    assert words["unique_paragraph_id"].nunique() == 2  # "p1" and "p1__r2"
    assert entry["n_texts"] == 1
    assert entry["repeated_readings"] == 2


def test_n_texts_is_unaffected_when_there_are_no_repeated_readings(tmp_path):
    """A corpus with no repeated readings must not be touched by the R27
    suffix-stripping -- n_texts still equals the plain distinct-paragraph
    count, and repeated_readings stays 0.
    """
    entry = prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)

    assert entry["n_texts"] == 1
    assert entry["repeated_readings"] == 0


def test_write_manifest_is_atomic_and_leaves_the_original_on_failure(
    tmp_path, monkeypatch
):
    """Item 5a / R21: an interrupted write must not truncate a good manifest."""
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [1, 2]}])
    original = (tmp_path / "manifest.json").read_text()

    def _boom(*args, **kwargs):
        raise OSError("simulated failure")

    monkeypatch.setattr(prep.os, "replace", _boom)
    with pytest.raises(OSError, match="simulated failure"):
        prep.write_manifest(tmp_path, [{"name": "B", "monitor": [3, 4]}])

    assert (tmp_path / "manifest.json").read_text() == original
    assert list(tmp_path.glob(".manifest-*")) == []


def test_git_over_https_sets_env_vars_and_restores_absence(monkeypatch):
    """Item 4 / R22: the four env vars are set during the block and fully
    cleared afterward when they weren't present before -- never leaked.
    """
    for key in prep._GIT_HTTPS_REWRITE_ENV:
        monkeypatch.delenv(key, raising=False)

    with prep._git_over_https():
        assert os.environ["GIT_CONFIG_COUNT"] == "1"
        assert os.environ["GIT_CONFIG_KEY_0"] == "url.https://github.com/.insteadOf"
        assert os.environ["GIT_CONFIG_VALUE_0"] == "git@github.com:"
        assert os.environ["GIT_TERMINAL_PROMPT"] == "0"

    for key in prep._GIT_HTTPS_REWRITE_ENV:
        assert key not in os.environ


def test_git_over_https_restores_a_preexisting_value(monkeypatch):
    """Item 4 / R22: a value present before the block is restored, not cleared."""
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "1")

    with prep._git_over_https():
        assert os.environ["GIT_TERMINAL_PROMPT"] == "0"

    assert os.environ["GIT_TERMINAL_PROMPT"] == "1"
