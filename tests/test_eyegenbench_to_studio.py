"""The EyeGenBench → app script on a small EyeGenBench-shaped tree."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import api

_SCRIPT = Path(__file__).parents[1] / "scripts" / "eyegenbench_to_studio.py"


@pytest.fixture
def script(monkeypatch):
    spec = importlib.util.spec_from_file_location("eyegenbench_to_studio", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Its dataclass resolves the module by name while the module runs.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _human(corpus: str) -> pd.DataFrame:
    rows = []
    for reader in ("r1", "r2"):
        for i, word in enumerate([0, 2, 1]):
            rows.append(
                dict(
                    unique_trial_id=f"{corpus}_{reader}_p1",
                    unique_paragraph_id=f"{corpus}_p1",
                    unique_participant_id=f"{corpus}_{reader}",
                    fix_index=i,
                    ia_index=word,
                    ia_label=["the", "quick", "fox"][word],
                    fix_duration=200.0 + i,
                    fix_landing_position=0.5,
                    dataset_name=corpus,
                )
            )
    return pd.DataFrame(rows)


def _model(trial: str, paragraph: str, reader: str, words, **extra) -> pd.DataFrame:
    return pd.DataFrame(
        dict(
            fix_index=range(len(words)),
            fix_duration=[150.0] * len(words),
            ia_index=words,
            unique_paragraph_id=paragraph,
            unique_participant_id=reader,
            unique_trial_id=trial,
            **extra,
        )
    )


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "EyeGenBench"
    for corpus in ("Alpha", "Beta"):
        processed = root / "code" / "data" / corpus / "processed"
        processed.mkdir(parents=True)
        _human(corpus).to_feather(processed / "fixations.feather")
        pd.DataFrame(
            dict(
                unique_paragraph_id=[f"{corpus}_p1"],
                text="the quick fox",
                text_language="en",
                ia_list=[json.dumps(["the", "quick", "fox"])],
                dataset_name=corpus,
            )
        ).to_csv(processed / "texts.csv", index=False)
        # The corpus' own split: r2 is in the test fold (0), r1 in training.
        pd.DataFrame(
            dict(
                unique_trial_id=[f"{corpus}_r1_p1", f"{corpus}_r2_p1"],
                fold=[3, 0],
            )
        ).to_csv(processed / "folds.csv", index=False)
    # The benchmark split.
    benchmark = root / "code" / "data" / "combined_benchmark" / "processed"
    benchmark.mkdir(parents=True)
    pd.DataFrame(
        dict(
            unique_trial_id=["Alpha_r1_p1", "Alpha_r2_p1", "Beta_r1_p1", "Beta_r2_p1"],
            subset=["test_participant", "train", "test_text", "val"],
        )
    ).to_csv(benchmark / "folds.csv", index=False)
    # A combined table is not a corpus.
    combined = root / "code" / "data" / "combined_all" / "processed"
    combined.mkdir(parents=True)
    _human("Alpha").to_feather(combined / "fixations.feather")

    full = tmp_path / "full"
    run = full / "ezreader" / "benchmark"
    run.mkdir(parents=True)
    pd.concat(
        [
            # Two draws of Alpha r1's trial: only the first is kept.
            _model("Alpha_r1_p1", "Alpha_p1", "Alpha_r1", [0, 1, 2], draw=0),
            _model("Alpha_r1_p1", "Alpha_p1", "Alpha_r1", [2, 2], draw=1),
            # A trial no corpus has.
            _model("Gone_r9_p1", "Gone_p1", "Gone_r9", [0], draw=0),
        ]
    ).to_csv(run / "model_fixations.csv", index=False)

    matrix = tmp_path / "matrix"
    # Beta has no full run: its matrix cell is used, and a debug one says so.
    cell = matrix / "scandl2" / "Beta" / "trainer=debug"
    cell.mkdir(parents=True)
    _model("Beta_r2_p1", "Beta_p1", "Beta_r2", [1, 0]).to_csv(
        cell / "model_fixations.csv", index=False
    )
    pd.DataFrame(dict(n_batches=[5], n_batches_available=[30], partial=[True])).to_csv(
        cell / "generation_summary.csv", index=False
    )
    # Alpha's EZ-Reader cell is ignored: the full run covers Alpha.
    other = matrix / "ezreader" / "Alpha"
    other.mkdir(parents=True)
    _model("Alpha_r2_p1", "Alpha_p1", "Alpha_r2", [0]).to_csv(
        other / "model_fixations.csv", index=False
    )
    return root, full, matrix, tmp_path / "work"


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")


def _run(script, tree, *corpora):
    root, full, matrix, work = tree
    args = ["--eyegenbench", str(root), "--full-runs", str(full)]
    args += ["--matrix", str(matrix), "--work", str(work)]
    for corpus in corpora:
        args += ["--corpus", corpus]
    assert script.main(args) == 0
    return json.loads((work / "added.json").read_text())


def test_corpora_leave_out_combined_tables(script, tree):
    assert script.corpora(tree[0]) == ["Alpha", "Beta"]


def test_a_full_run_keeps_one_draw_per_trial_under_its_human_trial(script, tree, cache):
    added = _run(script, tree, "Alpha")
    (model,) = added["Alpha"]["models"]
    assert (model["source"], model["kind"]) == ("EZ-Reader", "benchmark run")
    assert (model["trials"], model["unmatched_trials"]) == (1, 0)
    assert model["dropped_draw_rows"] == 2
    full_runs = json.loads((tree[3] / "full_runs.json").read_text())
    assert full_runs["ezreader"]["unmatched_rows"] == 1

    root, _, matrix, work = tree
    fixations, _ = script.build_fixations(
        script.human_fixations(root, "Alpha"),
        script.word_table(root, "Alpha"),
        script.model_runs("Alpha", work, full_runs, matrix),
        script.benchmark_regimes(root),
        script.corpus_regimes(root, "Alpha"),
    )
    generated = fixations[fixations["scanpath_source"] == "EZ-Reader"]
    assert set(generated["unique_participant_id"]) == {"Alpha_r1 · EZ-Reader"}
    assert set(generated["source_trial"]) == {"Alpha_r1_p1"}
    # A model's reading is a trial of its own.
    assert set(generated["unique_trial_id"]) == {"Alpha_r1_p1 · EZ-Reader"}
    readers = fixations.groupby("unique_trial_id")["unique_participant_id"].nunique()
    assert (readers == 1).all()
    assert set(generated["run_type"]) == {"benchmark run"}
    # A benchmark run's reading is held out as the benchmark split holds it out.
    assert set(generated["regime"]) == {"benchmark: new reader"}
    human = fixations[fixations["scanpath_source"] == script.HUMAN]
    assert set(human["run_type"]) == {"recorded"}
    assert dict(zip(human["unique_trial_id"], human["regime"])) == {
        "Alpha_r1_p1": "benchmark: new reader",
        "Alpha_r2_p1": "benchmark: train",
    }
    assert model["regimes"] == {"benchmark: new reader": 1}
    # Labels come from the paragraph's word list, by 0-based index.
    assert list(generated["ia_label"]) == ["the", "quick", "fox"]
    assert set(fixations["text_language"]) == {"en"}


def test_a_debug_matrix_cell_says_so_in_its_source(script, tree, cache):
    added = _run(script, tree, "Beta")
    (model,) = added["Beta"]["models"]
    assert model["source"] == "ScanDL 2.0 (debug run, 5 of 30 batches)"
    assert model["kind"] == "debug run"
    # A per-corpus run tests on its corpus' fold 0: new readers.
    assert model["regimes"] == {"per-corpus: new reader": 1}


def test_the_dataset_reaches_the_apps_list_without_word_boxes(script, tree, cache):
    _run(script, tree, "Alpha", "Beta")
    names = {d["name"]: d for d in api.cache_status()["datasets"]}
    assert set(names) == {"EyeGenBench · Alpha", "EyeGenBench · Beta"}
    assert names["EyeGenBench · Alpha"]["rows"] == {
        "fixations": 6 + 3,
        "raw_gaze": 0,
        "words": 0,
    }
