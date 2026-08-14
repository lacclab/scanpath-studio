import json
import shutil

import pandas as pd
import pytest

from scanpath_studio import data, eyegenbench


@pytest.fixture
def bundle(tmp_path):
    """A minimal two-word, two-fixation EyeGenBench bundle."""
    root = tmp_path / "EyeGenBench"
    ds = root / "PoTeC"
    ds.mkdir(parents=True)
    pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "ia_label": ["ab", "cd"],
            "line": [0, 0],
            "start_x": [10.0, 70.0],
            "end_x": [60.0, 120.0],
            "start_y": [20.0, 20.0],
            "end_y": [40.0, 40.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "words.parquet")
    pd.DataFrame(
        {
            # Not `unique_trial_id`: that literal name would override
            # EYEGENBENCH_FIX_SCHEMA's trial mapping inside
            # data.normalize_fixations (see eyegenbench.py's module
            # docstring). EyeGenBench's finer-grained per-reading id, if
            # carried at all, lives under this name instead.
            "eyegenbench_trial_id": ["t1", "t1"],
            "unique_participant_id": ["r1", "r1"],
            "unique_paragraph_id": ["p1", "p1"],
            "fix_index": [0, 1],
            "ia_index": [0, 1],
            "fix_duration": [200, 180],
            "x": [35.0, 95.0],
            "y": [30.0, 30.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "fixations.parquet")
    pd.DataFrame(
        {"unique_participant_id": ["r1"], "participant_language": ["de"]}
    ).to_parquet(ds / "participants.parquet")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "name": "PoTeC",
                        "language": "German",
                        "geometry_source": "real",
                        "monitor": [1680, 1050],
                        "n_readers": 1,
                        "n_texts": 1,
                        "n_fixations": 2,
                        "interpolated_fraction": 0.0,
                        "display_source": "pymovements:potec",
                    }
                ]
            }
        )
    )
    return root


def test_present_is_true_for_a_complete_bundle(bundle):
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is True


def test_present_is_false_when_a_parquet_is_missing(bundle):
    (bundle / "PoTeC" / "fixations.parquet").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_present_is_false_without_a_manifest(bundle):
    (bundle / "manifest.json").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_present_with_no_dataset_checks_the_whole_bundle(bundle):
    assert eyegenbench.eyegenbench_present(bundle) is True


def test_present_is_case_insensitive(bundle):
    assert eyegenbench.eyegenbench_present(bundle, "potec") is True
    assert eyegenbench.eyegenbench_present(bundle, "POTEC") is True


def test_present_is_false_for_a_directory_not_in_the_manifest(bundle):
    # A directory holding all three Parquet files under a name the manifest
    # doesn't list -- present() must not say True for a name load() would
    # reject.
    shutil.copytree(bundle / "PoTeC", bundle / "GhostCorpus")
    assert eyegenbench.eyegenbench_present(bundle, "GhostCorpus") is False


def test_datasets_lists_the_manifest_entries(bundle):
    names = [d["name"] for d in eyegenbench.eyegenbench_datasets(bundle)]
    assert names == ["PoTeC"]


def test_monitor_comes_from_the_manifest(bundle):
    assert eyegenbench.eyegenbench_monitor(bundle, "PoTeC") == (1680, 1050)


def test_raw_frames_returns_both_tables(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert list(words["ia_label"]) == ["ab", "cd"]
    assert len(fixations) == 2


def test_auto_detection_agrees_with_our_schemas(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert data.validate_word_schema(data.propose_word_schema(words)) == []
    assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []


def test_load_normalizes_and_broadcasts_to_the_reader(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["participant_id"]) == {"r1"}
    assert set(["x", "y", "width", "height"]) <= set(words.columns)
    assert fixations.loc[0, "duration_ms"] == 200


@pytest.mark.xfail(reason="geometry_source registered in Task 7", strict=True)
def test_geometry_source_survives_normalization(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["geometry_source"]) == {"real"}
    assert set(fixations["geometry_source"]) == {"real"}


def test_unknown_dataset_raises_value_error(bundle):
    with pytest.raises(ValueError, match="not in the bundle"):
        eyegenbench.eyegenbench_raw_frames(bundle, dataset="NoSuchCorpus")


def test_missing_bundle_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="prepare_eyegenbench.py"):
        eyegenbench.eyegenbench_raw_frames(tmp_path, dataset="PoTeC")
