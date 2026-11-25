#!/usr/bin/env python
"""Add EyeGenBench corpora, with the models' generated readings, to the app.

Reads EyeGenBench's processed tables and its models' ``model_fixations.csv``
read-only, and saves one dataset per corpus with `api.add_dataset`, so a local
``scanpath-studio`` lists it (as ➕ Add dataset would). Only what the benchmark
records is carried: which word each fixation landed on (word index and label),
its duration, its order and landing position. There are no screen positions or
word boxes, so the readings are drawn on reading charts (fixation order by
word), not over a stimulus.

Each dataset holds the human readings and every model's. A model's reading of a
trial is a trial of its own, ``"<trial> · <model>"``, by the reader
``"<reader> · <model>"``, so every trial id names one reading; ``source_trial``
names the human trial it was generated for, so matching on
``source_trial`` in the Comparisons tab shows a human trial beside every model's
version of it. ``scanpath_source`` says where a reading came from; a run that
covers only part of its corpus (a debug run) says so there too. ``run_type``
says how it was made: recorded (a human reading), benchmark run (one model run
over the benchmark's corpora together), per-corpus run, or debug run.

``regime`` says how the trial is held out, in the split the reading answers to:
a human reading and a benchmark run by the benchmark split
(``combined_benchmark/processed/folds.csv``: new reader, new text, new reader
and text, new corpus, ..., or train / validation); a per-corpus or debug run by
its corpus' own split, whose test fold 0 groups trials by participant, so a
reading generated there is a new reader. Each value names its split.

    python scripts/eyegenbench_to_studio.py --report
    python scripts/eyegenbench_to_studio.py --corpus CopCo
    python scripts/eyegenbench_to_studio.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from scanpath_studio import api

EYEGENBENCH = Path("/data/home/shubi/EyeGenBench")
#: Full benchmark runs, one model_fixations.csv per model over every benchmark
#: corpus, and the per-corpus matrix (debug runs for the trained models).
FULL_RUNS = EYEGENBENCH / "wt-run4" / "model_outputs"
MATRIX = EYEGENBENCH / "wt-matrix3" / "model_outputs"
WORK = Path("/data/home/shubi/scanpath-studio-data/eyegenbench-work")
PREFIX = "EyeGenBench · "

HUMAN = "Human"
RECORDED = "recorded"  # the run type of a human reading
#: The benchmark split's subsets, as ``regime`` names them.
BENCHMARK_SUBSETS = {
    "train": "train",
    "val": "validation",
    "test_participant": "new reader",
    "test_text": "new text",
    "test_both": "new reader and text",
    "test_corpus": "new corpus",
    "test_language": "new language",
    "test_zeroshot": "zero-shot corpus",
    "test_nontext_syllables": "non-text: syllables",
    "test_nontext_pseudowords": "non-text: pseudowords",
    "test_task_participant": "task reading, new reader",
    "test_task_text": "task reading, new text",
    "test_task_both": "task reading, new reader and text",
    "test_reread_participant": "rereading, new reader",
    "test_reread_text": "rereading, new text",
    "test_reread_both": "rereading, new reader and text",
}
#: A per-corpus run's test fold (fold 0 of a split grouped by participant).
PER_CORPUS_TEST_FOLD = 0
#: Model directory → the name shown for its readings.
MODELS = {
    "ezreader": "EZ-Reader",
    "swift": "SWIFT",
    "ob1reader": "OB1-Reader",
    "eyettentionii": "EyettentionII",
    "scandl2": "ScanDL 2.0",
    "next_word_baseline": "Next-word baseline",
    "train_distribution_baseline": "Train-distribution baseline",
    "human_resample": "Human resample",
}
#: Processed tables that are not one corpus.
NOT_A_CORPUS = {"combined_all", "combined_benchmark"}

FIX_SCHEMA = dict(
    participant="unique_participant_id",
    trial="unique_trial_id",
    text_id="unique_paragraph_id",
    duration="fix_duration",
    fixation_id="fix_index",
    word_id="ia_index",
    x=None,
    y=None,
)
KEEP = [
    "source_trial",
    "scanpath_source",
    "run_type",
    "regime",
    "ia_label",
    "fix_landing_position",
    "text_language",
    "dataset_name",
]
_HUMAN_COLUMNS = [
    "unique_trial_id",
    "unique_paragraph_id",
    "unique_participant_id",
    "fix_index",
    "ia_index",
    "ia_label",
    "fix_duration",
    "fix_landing_position",
    "dataset_name",
]
_MODEL_COLUMNS = [
    "unique_trial_id",
    "unique_paragraph_id",
    "unique_participant_id",
    "fix_index",
    "ia_index",
    "fix_duration",
]


@dataclass
class Run:
    """One model's readings of one corpus, and where they came from."""

    model: str
    rows: pd.DataFrame
    path: Path
    kind: str  # its run type: "benchmark run", "per-corpus run" or "debug run"
    note: str = ""  # e.g. "5 of 30 batches"
    dropped_draws: int = 0

    @property
    def source(self) -> str:
        label = MODELS[self.model]
        if self.kind == "debug run":
            return f"{label} (debug run{', ' + self.note if self.note else ''})"
        return label


def corpora(root: Path) -> list[str]:
    data = root / "code" / "data"
    return sorted(
        d.name
        for d in data.iterdir()
        if (d / "processed" / "fixations.feather").is_file()
        and d.name not in NOT_A_CORPUS
    )


def human_fixations(root: Path, corpus: str) -> pd.DataFrame:
    path = root / "code" / "data" / corpus / "processed" / "fixations.feather"
    return pd.read_feather(path, columns=_HUMAN_COLUMNS)


def word_table(root: Path, corpus: str) -> pd.DataFrame:
    """One row per word: its paragraph, index, label and the text's language.

    Read from each paragraph's ``ia_list``, which every corpus' texts table
    has; a fixation's ``ia_index`` is the 0-based position in that list."""
    path = root / "code" / "data" / corpus / "processed" / "texts.csv"
    texts = pd.read_csv(
        path,
        usecols=["unique_paragraph_id", "ia_list", "text_language"],
        dtype=str,
        keep_default_na=False,
    ).drop_duplicates("unique_paragraph_id")
    words = texts.assign(ia_label=texts["ia_list"].map(json.loads)).explode("ia_label")
    words["ia_index"] = words.groupby("unique_paragraph_id").cumcount()
    return words.drop(columns="ia_list").dropna(subset=["ia_label"])


def one_draw(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """One generated scanpath per trial: the first draw where a run has several.

    Returns the rows and how many rows of other draws were left out."""
    if "draw" in rows and rows.groupby("unique_trial_id")["draw"].nunique().gt(1).any():
        first = rows.groupby("unique_trial_id")["draw"].transform("min")
        kept = rows[rows["draw"] == first]
        return kept, len(rows) - len(kept)
    return rows, 0


def _require_one_scanpath_per_trial(rows: pd.DataFrame, where: str) -> None:
    if rows.duplicated(["unique_trial_id", "fix_index"]).any():
        raise ValueError(f"{where}: a trial repeats a fix_index after one draw each")


def _full_run_csv(model_dir: Path) -> Path | None:
    found = sorted((model_dir / "benchmark").rglob("model_fixations.csv"))
    if len(found) > 1:
        raise ValueError(f"several full runs under {model_dir}: {found}")
    return found[0] if found else None


def split_full_runs(full_root: Path, trial_corpus: dict[str, str], work: Path) -> dict:
    """Split each model's full benchmark run by corpus into ``work``.

    Rows go to the corpus whose human trials hold their ``unique_trial_id``;
    rows matching no human trial are counted, not kept. Returns
    ``{model: {"path", "unmatched_rows", "dropped_draws"}}``."""
    report = {}
    for model, label in MODELS.items():
        csv = _full_run_csv(full_root / model)
        if csv is None:
            continue
        usecols = lambda c: c in {*_MODEL_COLUMNS, "draw"}
        rows = pd.read_csv(csv, usecols=usecols, dtype={"unique_trial_id": str})
        before = rows["unique_trial_id"].map(trial_corpus).value_counts()
        rows, dropped = one_draw(rows)
        _require_one_scanpath_per_trial(rows, str(csv))
        corpus = rows["unique_trial_id"].map(trial_corpus)
        after = corpus.value_counts()
        for name, part in rows[corpus.notna()].groupby(corpus[corpus.notna()]):
            target = work / "full" / model / f"{name}.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            part.drop(columns="draw", errors="ignore").to_parquet(target, index=False)
        report[model] = {
            "path": str(csv),
            "unmatched_rows": int(corpus.isna().sum()),
            "dropped_draws": dropped,
            "dropped_draws_by_corpus": {
                name: int(count - after.get(name, 0))
                for name, count in before.items()
                if count != after.get(name, 0)
            },
        }
        print(f"  {label}: {len(rows):,} rows from {csv}", flush=True)
    return report


def _matrix_run(matrix_root: Path, model: str, corpus: str) -> Run | None:
    found = sorted((matrix_root / model / corpus).rglob("model_fixations.csv"))
    if not found:
        return None
    if len(found) > 1:
        raise ValueError(f"several matrix runs for {model} on {corpus}: {found}")
    csv = found[0]
    summary_path = csv.parent / "generation_summary.csv"
    summary = pd.read_csv(summary_path).iloc[0] if summary_path.is_file() else None
    partial = bool(summary is not None and summary.get("partial", False))
    debug = partial or "trainer=debug" in str(csv)
    note = ""
    if (
        summary is not None
        and "n_batches" in summary
        and "n_batches_available" in summary
    ):
        note = f"{int(summary['n_batches'])} of {int(summary['n_batches_available'])} batches"
    usecols = lambda c: c in {*_MODEL_COLUMNS, "draw"}
    rows = pd.read_csv(csv, usecols=usecols, dtype={"unique_trial_id": str})
    rows, dropped = one_draw(rows)
    _require_one_scanpath_per_trial(rows, str(csv))
    return Run(
        model,
        rows.drop(columns="draw", errors="ignore"),
        csv,
        "debug run" if debug else "per-corpus run",
        note if debug else "",
        dropped,
    )


def model_runs(
    corpus: str, work: Path, full_meta: dict, matrix_root: Path
) -> list[Run]:
    """One run per model: the full benchmark run where it covers the corpus,
    else the corpus' matrix cell. Never both."""
    runs = []
    for model in MODELS:
        part = work / "full" / model / f"{corpus}.parquet"
        if part.is_file():
            meta = full_meta[model]
            runs.append(
                Run(
                    model,
                    pd.read_parquet(part),
                    Path(meta["path"]),
                    "benchmark run",
                    dropped_draws=meta.get("dropped_draws_by_corpus", {}).get(
                        corpus, 0
                    ),
                )
            )
        elif (run := _matrix_run(matrix_root, model, corpus)) is not None:
            runs.append(run)
    return runs


def benchmark_regimes(root: Path) -> pd.Series:
    """Each trial's subset in the benchmark split, as ``regime`` names it."""
    folds = pd.read_csv(
        root / "code" / "data" / "combined_benchmark" / "processed" / "folds.csv"
    )
    unknown = set(folds["subset"]) - set(BENCHMARK_SUBSETS)
    if unknown:
        raise ValueError(f"Benchmark subsets without a regime name: {sorted(unknown)}")
    return "benchmark: " + folds.set_index("unique_trial_id")["subset"].map(
        BENCHMARK_SUBSETS
    )


def corpus_regimes(root: Path, corpus: str) -> pd.Series:
    """Each trial's place in its corpus' own split, as ``regime`` names it."""
    folds = pd.read_csv(root / "code" / "data" / corpus / "processed" / "folds.csv")
    held_out = folds.set_index("unique_trial_id")["fold"].eq(PER_CORPUS_TEST_FOLD)
    return held_out.map({True: "per-corpus: new reader", False: "per-corpus: train"})


def build_fixations(
    human: pd.DataFrame,
    words: pd.DataFrame,
    runs: list[Run],
    benchmark: pd.Series,
    per_corpus: pd.Series,
) -> tuple[pd.DataFrame, list[dict]]:
    """The corpus' fixation table: human rows, then each run's, and coverage.

    ``benchmark`` and ``per_corpus`` are each trial's ``regime`` in the
    benchmark split and in the corpus' own split."""
    language = words.drop_duplicates("unique_paragraph_id").set_index(
        "unique_paragraph_id"
    )["text_language"]
    labels = words.set_index(["unique_paragraph_id", "ia_index"])["ia_label"]
    labels = labels[~labels.index.duplicated()]
    human_trials = set(human["unique_trial_id"])
    frames = [
        human.assign(
            source_trial=human["unique_trial_id"],
            scanpath_source=HUMAN,
            run_type=RECORDED,
            regime=human["unique_trial_id"].map(benchmark),
        )
    ]
    coverage = []
    dataset_name = str(human["dataset_name"].iloc[0]) if len(human) else ""
    for run in runs:
        rows = run.rows
        matched = rows["unique_trial_id"].isin(human_trials)
        rows = rows[matched]
        key = pd.MultiIndex.from_arrays([rows["unique_paragraph_id"], rows["ia_index"]])
        regime = rows["unique_trial_id"].map(
            benchmark if run.kind == "benchmark run" else per_corpus
        )
        frames.append(
            rows.assign(
                unique_participant_id=rows["unique_participant_id"].astype(str)
                + f" · {MODELS[run.model]}",
                unique_trial_id=rows["unique_trial_id"].astype(str)
                + f" · {MODELS[run.model]}",
                source_trial=rows["unique_trial_id"],
                scanpath_source=run.source,
                run_type=run.kind,
                regime=regime,
                ia_label=labels.reindex(key).to_numpy(),
                dataset_name=dataset_name,
            )
        )
        coverage.append(
            {
                "model": MODELS[run.model],
                "source": run.source,
                "kind": run.kind,
                "run": str(run.path),
                "trials": int(rows["unique_trial_id"].nunique()),
                "human_trials": len(human_trials),
                "unmatched_trials": int(
                    run.rows.loc[~matched, "unique_trial_id"].nunique()
                ),
                "dropped_draw_rows": run.dropped_draws,
                # Trials per regime: a run's trials should all be held out.
                "regimes": {
                    str(k): int(v)
                    for k, v in regime[~rows["unique_trial_id"].duplicated()]
                    .fillna("unknown")
                    .value_counts()
                    .items()
                },
            }
        )
    fixations = pd.concat(frames, ignore_index=True)
    readers = fixations.groupby("unique_trial_id")["unique_participant_id"].nunique()
    if (readers > 1).any():
        raise ValueError(
            "Trial ids shared by several readers: "
            f"{readers[readers > 1].index[:5].tolist()}"
        )
    fixations["text_language"] = fixations["unique_paragraph_id"].map(language)
    return fixations, coverage


def describe(corpus: str, coverage: list[dict]) -> str:
    parts = [
        f"EyeGenBench {corpus}: the human readings"
        + (" and " + ", ".join(c["source"] for c in coverage) if coverage else "")
        + ". Fixations by word (index and label), duration, order and landing "
        "position only: no screen positions or word boxes, so view them on a "
        "reading chart such as Fixation order by Word ID. Match on source_trial "
        "in Comparisons to see a human trial beside each model's version of it."
    ]
    for c in coverage:
        parts.append(
            f"{c['source']}: {c['kind']}, {c['trials']:,} of {c['human_trials']:,} "
            f"trials ({c['run']})."
        )
    return " ".join(parts)


def add_corpus(
    corpus: str, root: Path, work: Path, full_meta: dict, matrix_root: Path
) -> dict:
    started = time.monotonic()
    human = human_fixations(root, corpus)
    words = word_table(root, corpus)
    runs = model_runs(corpus, work, full_meta, matrix_root)
    fixations, coverage = build_fixations(
        human,
        words,
        runs,
        benchmark_regimes(root),
        corpus_regimes(root, corpus),
    )
    name = api.add_dataset(
        PREFIX + corpus,
        None,
        fixations,
        fix_schema=FIX_SCHEMA,
        keep_columns=KEEP,
        description=describe(corpus, coverage),
        select=False,
        replace=True,
    )
    return {
        "corpus": corpus,
        "dataset": name,
        "human_fixations": len(human),
        "fixations": len(fixations),
        "models": coverage,
        "seconds": round(time.monotonic() - started, 1),
    }


def trial_corpus_map(root: Path, names: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for corpus in names:
        path = root / "code" / "data" / corpus / "processed" / "fixations.feather"
        trials = pd.read_feather(path, columns=["unique_trial_id"])["unique_trial_id"]
        for trial in trials.astype(str).unique():
            if mapping.setdefault(trial, corpus) != corpus:
                raise ValueError(f"trial {trial!r} is in {mapping[trial]} and {corpus}")
    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", action="append", default=[], help="Repeatable.")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--eyegenbench", type=Path, default=EYEGENBENCH)
    parser.add_argument("--full-runs", type=Path, default=FULL_RUNS)
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument(
        "--split-full-runs",
        action="store_true",
        help="Re-split the full benchmark runs by corpus (otherwise reuse --work).",
    )
    parser.add_argument("--report", action="store_true", help="List corpora and runs.")
    args = parser.parse_args(argv)

    available = corpora(args.eyegenbench)
    if args.report:
        for corpus in available:
            cells = [m for m in MODELS if (args.matrix / m / corpus).is_dir()]
            print(f"{corpus}: matrix {', '.join(MODELS[m] for m in cells) or '-'}")
        return 0
    names = available if args.all else args.corpus
    unknown = sorted(set(names) - set(available))
    if unknown or not names:
        parser.error(f"choose --all or --corpus from {available}; unknown: {unknown}")

    meta_path = args.work / "full_runs.json"
    if args.split_full_runs or not meta_path.is_file():
        print("Splitting the full benchmark runs by corpus…", flush=True)
        full_meta = split_full_runs(
            args.full_runs, trial_corpus_map(args.eyegenbench, available), args.work
        )
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(full_meta, indent=1), encoding="utf-8")
    full_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    results = []
    for corpus in names:
        result = add_corpus(corpus, args.eyegenbench, args.work, full_meta, args.matrix)
        results.append(result)
        print(
            f"{result['dataset']}: {result['fixations']:,} fixations "
            f"({result['human_fixations']:,} human), "
            f"{len(result['models'])} model runs, {result['seconds']} s",
            flush=True,
        )
        for c in result["models"]:
            print(
                f"    {c['source']:<45} {c['kind']:<15} {c['trials']:>7,} / "
                f"{c['human_trials']:,} trials, {c['unmatched_trials']:,} unmatched",
                flush=True,
            )
    report = args.work / "added.json"
    previous = (
        json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    )
    previous.update({r["corpus"]: r for r in results})
    report.write_text(json.dumps(previous, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
