"""Reproducible timing profile of the VAL-5 computation register.

Walks the pipeline in dependency order — normalize → assign → measure →
preprocess → aggregate, then the per-trial similarity, drift-correction and
figure builders — and times each stage against a real corpus, mapping every
stage back to the ``computations.py`` entry ids it exercises so the output can
be read next to ``docs/computations.md``.

The default run uses the bundled demo. The numbers that matter come from a big
corpus: point it at the OneStop EyeLink reports and cap the participant count,
and the reader stops after that many participants instead of parsing the whole
multi-gigabyte export.

    python benchmarks/computation_benchmark.py \\
        --words  /path/to/ia_P.tsv \\
        --fixations /path/to/fixations_P.tsv \\
        --participants 16 --json profile-16.json

``--participants`` on its own is the scale knob: run it at 1, 4, 16, 64 and the
growth exponent of each stage falls out of the JSON. ``--skip`` drops stages by
name substring, which is how a run gets past a stage that is too slow to
finish at the scale being measured.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd
import psutil

from scanpath_studio import (
    aggregation,
    alignment,
    data as data_module,
    experimental_setup,
    illustration,
    measures,
    preprocessing,
    similarity,
)

PROCESS = psutil.Process()
DELIMITED_SUFFIXES = {".csv", ".tsv", ".txt"}


@dataclass
class Measurement:
    """One timed stage, tagged with the register entries it covers."""

    stage: str
    computation_ids: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    rss_delta_mib: float = 0.0
    rss_after_mib: float = 0.0
    rows_in: int = 0
    scope: str = "corpus"
    note: str = ""
    error: str = ""


def _rss_mib() -> float:
    return PROCESS.memory_info().rss / (1024 * 1024)


class Profiler:
    """Times callables and keeps the measurements in call order."""

    def __init__(self, skip: Sequence[str] = ()) -> None:
        self.measurements: list[Measurement] = []
        self.skip = tuple(skip)

    def run(
        self,
        stage: str,
        computation_ids: Sequence[str],
        operation: Callable[[], Any],
        *,
        rows_in: int = 0,
        scope: str = "corpus",
        note: str = "",
    ) -> Any:
        """Time ``operation``, record it, and return its result (None on error).

        A stage that raises is recorded rather than propagated — at corpus
        scale, "this one cannot run" is a result, and the stages after it are
        still worth measuring.
        """
        if any(pattern in stage for pattern in self.skip):
            print(f"  {stage:<42s} {'skipped':>9s}", flush=True)
            return None

        gc.collect()
        before = _rss_mib()
        started = time.perf_counter()
        result: Any = None
        error = ""
        try:
            result = operation()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        after = _rss_mib()

        self.measurements.append(
            Measurement(
                stage=stage,
                computation_ids=list(computation_ids),
                elapsed_s=round(elapsed, 4),
                rss_delta_mib=round(after - before, 1),
                rss_after_mib=round(after, 1),
                rows_in=rows_in,
                scope=scope,
                note=note,
                error=error,
            )
        )
        suffix = f"  !! {error}" if error else ""
        print(
            f"  {stage:<42s} {elapsed:9.3f}s  ΔRSS {after - before:+8.1f} MiB"
            f"  RSS {after:8.1f} MiB{suffix}",
            flush=True,
        )
        return result


def read_table(path: Path, participants: int | None) -> pd.DataFrame:
    """Read a words/fixations table, optionally stopping after N participants.

    EyeLink exports are grouped by recording session, so a chunked read can
    peel off a participant prefix without parsing the rest of a multi-gigabyte
    file. Values are left exactly as pandas sees them — the "." missing marker
    included — because that is what the app gets from an upload.
    """
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
    elif participants is None or suffix not in DELIMITED_SUFFIXES:
        sep = "\t" if suffix == ".tsv" else ","
        frame = pd.read_csv(path, sep=sep, low_memory=False)
    else:
        sep = "\t" if suffix == ".tsv" else ","
        chunks: list[pd.DataFrame] = []
        seen: list[str] = []
        column: str | None = None
        for chunk in pd.read_csv(path, sep=sep, chunksize=250_000, low_memory=False):
            chunk.columns = [str(name).lstrip("﻿") for name in chunk.columns]
            if column is None:
                column = data_module.pick_column(
                    chunk, data_module.PARTICIPANT_CANDIDATES
                )
                if column is None:
                    raise SystemExit(f"{path.name}: no participant column found")
            labels = chunk[column].astype(str)
            for label in labels.unique():
                if label not in seen:
                    seen.append(label)
            keep = labels.isin(seen[:participants])
            chunks.append(chunk[keep])
            if len(seen) > participants:
                break
        frame = pd.concat(chunks, ignore_index=True)
        return frame

    frame.columns = [str(name).lstrip("﻿") for name in frame.columns]
    if participants is not None:
        column = data_module.pick_column(frame, data_module.PARTICIPANT_CANDIDATES)
        if column is not None:
            keep = frame[column].astype(str).unique()[:participants]
            frame = frame[frame[column].astype(str).isin(keep)]
    return frame


def _sample_paths() -> tuple[Path, Path]:
    sample_dir = Path(data_module.__file__).parent / "sample_data"
    return sample_dir / "ia.parquet", sample_dir / "fixations.parquet"


def profile(
    words_path: Path,
    fixations_path: Path,
    *,
    participants: int | None,
    skip: Sequence[str],
) -> dict[str, Any]:
    """Run every register stage once and return the JSON-ready payload."""
    profiler = Profiler(skip)

    print("== load ==", flush=True)
    words_raw = profiler.run(
        "io.read_words", [], lambda: read_table(words_path, participants)
    )
    fixations_raw = profiler.run(
        "io.read_fixations", [], lambda: read_table(fixations_path, participants)
    )
    if words_raw is None or fixations_raw is None:
        raise SystemExit("could not read the input tables")
    print(
        f"  raw words {words_raw.shape[0]:,} x {words_raw.shape[1]}   "
        f"raw fixations {fixations_raw.shape[0]:,} x {fixations_raw.shape[1]}",
        flush=True,
    )

    word_schema = profiler.run(
        "infer_word_schema",
        [],
        lambda: data_module.infer_word_schema(words_raw),
        rows_in=len(words_raw),
    )
    fix_schema = profiler.run(
        "infer_fix_schema",
        [],
        lambda: data_module.infer_fix_schema(fixations_raw),
        rows_in=len(fixations_raw),
    )
    if not word_schema or not fix_schema:
        raise SystemExit("schema inference failed on these tables")

    words = profiler.run(
        "normalize_words",
        ["norm.words", "norm.box_edges", "norm.flags"],
        lambda: data_module.normalize_words(words_raw, word_schema),
        rows_in=len(words_raw),
    )
    fixations = profiler.run(
        "normalize_fixations",
        ["norm.fixations", "norm.trial_id_composite"],
        lambda: data_module.normalize_fixations(fixations_raw, fix_schema),
        rows_in=len(fixations_raw),
    )
    if words is None or fixations is None:
        raise SystemExit("normalization failed")
    harmonized = profiler.run(
        "harmonize_frames",
        ["norm.stimulus_broadcast", "norm.aoi_center_placement"],
        lambda: data_module.harmonize_frames(words, fixations),
        rows_in=len(words) + len(fixations),
    )
    if harmonized is not None:
        words, fixations = harmonized
    words_raw = fixations_raw = None  # let the wide source frames go
    gc.collect()

    trial_keys = ["participant_id", "trial_id"]
    n_trials = fixations.groupby(trial_keys, observed=True).ngroups
    print(
        f"  normalized words {words.shape[0]:,} x {words.shape[1]}   "
        f"fixations {fixations.shape[0]:,} x {fixations.shape[1]}   "
        f"trials {n_trials:,}",
        flush=True,
    )

    print("\n== assignment / classification ==", flush=True)
    assigned = profiler.run(
        "assign_fixations_to_words",
        ["assign.fixation_to_word"],
        lambda: measures.assign_fixations_to_words(fixations, words, overwrite=True),
        rows_in=len(fixations),
    )
    if assigned is not None:
        fixations = assigned
    profiler.run(
        "fixation_in_text_mask",
        ["assign.in_text"],
        lambda: measures.fixation_in_text_mask(fixations, words),
        rows_in=len(fixations),
    )
    profiler.run(
        "cluster_word_lines",
        ["assign.line_cluster"],
        lambda: measures.cluster_word_lines(words),
        rows_in=len(words),
    )
    profiler.run(
        "materialize_runs",
        ["assign.runs"],
        lambda: measures.materialize_runs(fixations),
        rows_in=len(fixations),
    )
    enriched = profiler.run(
        "enrich_fixations",
        ["assign.progression", "fix.saccade_amplitude", "fix.angles"],
        lambda: measures.enrich_fixations(fixations, words),
        rows_in=len(fixations),
    )
    if enriched is not None:
        fixations = enriched
    profiler.run(
        "classify_saccades",
        ["assign.saccade_class"],
        lambda: measures.classify_saccades(fixations, words),
        rows_in=len(fixations),
    )

    print("\n== scientific measures ==", flush=True)
    per_word = profiler.run(
        "compute_per_word_measures",
        [
            "measure.ffd",
            "measure.fprt",
            "measure.rpd",
            "measure.tfd",
            "measure.nfix",
            "measure.skip",
            "measure.regressions",
            "measure.landing_position",
            "measure.landing_distance",
            "measure.second_pass",
            "measure.single_fix",
            "measure.reg_in_count",
        ],
        lambda: measures.compute_per_word_measures(fixations, words),
        rows_in=len(words),
    )

    print("\n== geometry ==", flush=True)
    profiler.run(
        "word_box_space_px",
        ["geom.word_box_space_px"],
        lambda: measures.word_box_space_px(words),
        rows_in=len(words),
    )
    profiler.run(
        "word_box_bounds",
        ["geom.word_box_bounds"],
        lambda: measures.word_box_bounds(words),
        rows_in=len(words),
    )
    profiler.run(
        "word_char_advance",
        ["geom.word_char_advance"],
        lambda: measures.word_char_advance(words),
        rows_in=len(words),
    )
    profiler.run(
        "pixels_per_degree",
        ["geom.pixels_per_degree"],
        lambda: experimental_setup.pixels_per_degree(600.0, 1920.0, 530.0),
    )
    profiler.run(
        "font_pt_to_px",
        ["geom.font_pt_to_px"],
        lambda: experimental_setup.font_pt_to_px(14.0, 96.0),
    )

    print("\n== preprocessing ==", flush=True)
    profiler.run(
        "merge_short_fixations",
        ["pre.merge_short"],
        lambda: preprocessing.merge_short_fixations(fixations, words),
        rows_in=len(fixations),
    )
    profiler.run(
        "preprocess_fixations",
        ["pre.exclude_short", "pre.blink_adjacent"],
        lambda: preprocessing.preprocess_fixations(
            fixations,
            words,
            settings={
                "enabled": True,
                "short_policy": "Merge",
                "discard_blink_adjacent": True,
            },
        ),
        rows_in=len(fixations),
    )
    profiler.run(
        "cleaning_report",
        ["pre.cleaning_report"],
        lambda: preprocessing.cleaning_report(fixations),
        rows_in=len(fixations),
    )
    profiler.run(
        "character_grid",
        ["pre.character_grid"],
        lambda: preprocessing.character_grid(words),
        rows_in=len(words),
    )
    labels = words["text"].head(50_000)
    profiler.run(
        "detect_right_to_left",
        ["pre.rtl"],
        lambda: [preprocessing.detect_right_to_left(str(text)) for text in labels],
        rows_in=len(labels),
        note="per word label, capped at 50k",
    )
    profiler.run(
        "sentence_measures",
        ["pre.sentence_measures"],
        lambda: preprocessing.sentence_measures(words, fixations),
        rows_in=len(words),
    )
    profiler.run(
        "saccade_table",
        ["pre.saccade_table"],
        lambda: preprocessing.saccade_table(fixations, words=words),
        rows_in=len(fixations),
    )
    profiler.run(
        "measure_sensitivity",
        ["pre.sensitivity"],
        lambda: preprocessing.measure_sensitivity(words, fixations),
        rows_in=len(words),
    )

    print("\n== aggregation ==", flush=True)
    frame = per_word if per_word is not None else words
    measure = aggregation.MEASURES["tfd"]
    readers = list(pd.unique(frame["participant_id"]))
    half = max(1, len(readers) // 2)
    spec_a = {"participant_id": readers[:half]}
    spec_b = {"participant_id": readers[half:] or readers[:half]}
    text_id = frame["text_id"].iloc[0]

    profiler.run(
        "trial_summary_table",
        ["agg.trial_summary"],
        lambda: aggregation.trial_summary_table(words, fixations),
        rows_in=len(fixations),
    )
    profiler.run(
        "reader_summary_table",
        ["agg.reader_summary"],
        lambda: aggregation.reader_summary_table(words, fixations),
        rows_in=len(fixations),
    )
    values = profiler.run(
        "measure_values",
        ["agg.measure_values"],
        lambda: aggregation.measure_values(frame, measure),
        rows_in=len(frame),
    )
    if values is not None and len(values):
        profiler.run(
            "aggregate_value",
            ["agg.aggregate_value"],
            lambda: aggregation.aggregate_value(values, "mean"),
            rows_in=len(values),
        )
        profiler.run(
            "bootstrap_ci",
            ["agg.bootstrap_ci"],
            lambda: aggregation.bootstrap_ci(values),
            rows_in=len(values),
            note="allocates n_boot x len(values) float64",
        )
        profiler.run(
            "spread_bounds",
            ["agg.spread"],
            lambda: aggregation.spread_bounds(values, float(values.mean()), "SD"),
            rows_in=len(values),
        )
    profiler.run(
        "group_mask",
        ["agg.group_mask"],
        lambda: aggregation.group_mask(frame, spec_a),
        rows_in=len(frame),
    )
    profiler.run(
        "cohort_word_profile",
        ["agg.word_profile"],
        lambda: aggregation.cohort_word_profile(frame, "text_id", text_id, measure),
        rows_in=len(frame),
        note=f"one text ({text_id})",
    )
    profiler.run(
        "word_rate_profile",
        ["agg.word_rates"],
        lambda: aggregation.word_rate_profile(frame, "text_id", text_id),
        rows_in=len(frame),
        note=f"one text ({text_id})",
    )
    profiler.run(
        "add_normalized_column",
        ["agg.normalize"],
        lambda: aggregation.add_normalized_column(frame.copy(), measure.column),
        rows_in=len(frame),
    )
    groups = profiler.run(
        "two_group_values",
        [],
        lambda: aggregation.two_group_values(frame, measure, spec_a, spec_b),
        rows_in=len(frame),
    )
    if groups:
        profiler.run(
            "group_effect_size",
            ["agg.effect_size"],
            lambda: aggregation.group_effect_size(groups["Group A"], groups["Group B"]),
            rows_in=len(groups["Group A"]) + len(groups["Group B"]),
        )
    # Both of these take the *fixation* frame, not the measured word frame —
    # `landing_positions(words, fixations)` and `metric_over_time(fixations, …)`.
    profiler.run(
        "landing_positions",
        ["agg.landing_curve"],
        lambda: aggregation.landing_positions(frame, fixations),
        rows_in=len(frame) + len(fixations),
    )
    # `tfd` lives on the words frame; this one needs a fixation-grain measure or
    # it walks an empty path and times nothing.
    over_time_measure = aggregation.MEASURES["fix_dur"]
    profiler.run(
        "metric_over_time",
        ["agg.over_time"],
        lambda: aggregation.metric_over_time(fixations, over_time_measure),
        rows_in=len(fixations),
        note=f"measure={over_time_measure.label}",
    )

    sizes = fixations.groupby(trial_keys, observed=True).size().sort_values()
    participant_id, trial_id = sizes.index[-1]
    trial_words = words[
        (words.participant_id == participant_id) & (words.trial_id == trial_id)
    ]
    trial_fixations = fixations[
        (fixations.participant_id == participant_id) & (fixations.trial_id == trial_id)
    ]
    print(
        f"\n== per trial ({participant_id}/{trial_id}: "
        f"{len(trial_fixations)} fixations, {len(trial_words)} words) ==",
        flush=True,
    )

    profiler.run(
        "rebased_fixation_onsets",
        ["fix.rebased_onsets"],
        lambda: measures.rebased_fixation_onsets(trial_fixations),
        rows_in=len(trial_fixations),
        scope="trial",
    )
    sequence = profiler.run(
        "aoi_sequence",
        ["sim.aoi_sequence"],
        lambda: similarity.aoi_sequence(trial_fixations, trial_words),
        rows_in=len(trial_fixations),
        scope="trial",
    )
    if sequence:
        profiler.run(
            "normalized_levenshtein",
            ["sim.nld"],
            lambda: similarity.normalized_levenshtein(sequence, sequence[::-1]),
            rows_in=len(sequence),
            scope="trial",
        )
        profiler.run(
            "nld_by_fixation_index",
            ["sim.windowed"],
            lambda: similarity.nld_by_fixation_index(
                trial_fixations, trial_fixations, trial_words
            ),
            rows_in=len(trial_fixations),
            scope="trial",
        )
    for algorithm in alignment.ALGORITHMS:
        profiler.run(
            f"alignment.correct[{algorithm}]",
            ["align.algorithms"],
            lambda name=algorithm: alignment.correct(
                trial_fixations, trial_words, name
            ),
            rows_in=len(trial_fixations),
            scope="trial",
        )

    print("\n== display ==", flush=True)
    import scanpath_studio as sps

    profiler.run(
        "illustration_reasons",
        ["disp.illustration"],
        lambda: illustration.illustration_reasons({}),
        scope="trial",
    )
    profiler.run(
        "plot_scanpath",
        ["disp.marker_sizes", "disp.axis_ranges"],
        lambda: sps.plot_scanpath(words, fixations, participant_id, trial_id),
        rows_in=len(trial_fixations),
        scope="trial",
    )
    profiler.run(
        "animate_scanpath",
        ["disp.animation_timing"],
        lambda: sps.animate_scanpath(words, fixations, participant_id, trial_id),
        rows_in=len(trial_fixations),
        scope="trial",
    )

    corpus_total = sum(
        m.elapsed_s
        for m in profiler.measurements
        if m.scope == "corpus" and not m.error
    )
    print(
        f"\n== corpus-wide total {corpus_total:.1f}s   peak RSS "
        f"{max(m.rss_after_mib for m in profiler.measurements):.0f} MiB ==",
        flush=True,
    )

    return {
        "participants": int(words["participant_id"].nunique()),
        "n_words": int(len(words)),
        "n_fixations": int(len(fixations)),
        "n_trials": int(n_trials),
        "corpus_total_s": round(corpus_total, 3),
        "measurements": [asdict(m) for m in profiler.measurements],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", default="", help="words / IA table")
    parser.add_argument("--fixations", default="", help="fixation table")
    parser.add_argument(
        "--participants",
        type=int,
        default=None,
        help="stop after this many participants (the scale knob)",
    )
    parser.add_argument(
        "--skip", default="", help="comma-separated stage-name substrings to skip"
    )
    parser.add_argument("--json", default="", help="write the payload here")
    args = parser.parse_args()

    if args.participants is not None and args.participants <= 0:
        parser.error("--participants must be greater than zero")

    if bool(args.words) != bool(args.fixations):
        parser.error("--words and --fixations go together")
    if args.words:
        words_path, fixations_path = Path(args.words), Path(args.fixations)
    else:
        words_path, fixations_path = _sample_paths()

    payload = profile(
        words_path,
        fixations_path,
        participants=args.participants,
        skip=[part for part in args.skip.split(",") if part],
    )
    payload["words_path"] = str(words_path)
    payload["fixations_path"] = str(fixations_path)

    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
