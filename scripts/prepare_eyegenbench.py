#!/usr/bin/env python
"""Build Scanpath Studio bundles from EyeGenBench corpora.

Runs EyeGenBench's own `prepare_data()` unmodified, then -- while the raw
downloads are still on disk -- recovers screen geometry and writes an
app-native Parquet bundle. Run in a venv that has EyeGenBench installed:

    python -m venv .venv-eyegenbench
    .venv-eyegenbench/bin/pip install -e ../../EyeGenBench/code
    .venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --all
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from scanpath_studio.eyegenbench_geometry import (  # noqa: E402
    place_fixations,
    resolve_geometry,
)

MIN_FREE_GB = 15.0
MANIFEST_NAME = "manifest.json"

# The 39 loadable EyeGenBench datasets. `gazebasereading` is excluded -- still a
# NotImplementedError stub upstream.
DATASETS = [
    "adegbts",
    "bsc",
    "bscii",
    "celer",
    "cfiltcoreference",
    "cfiltessaygrading",
    "cfiltsarcasm",
    "cfiltscanpath",
    "cfiltsentiment",
    "chinesereading",
    "colagaze",
    "copco",
    "cuentos",
    "emtec",
    "etdd70",
    "eyevoicespan",
    "gaze4hate",
    "ggtg",
    "iitbhgc",
    "interead",
    "mecol1w1",
    "mecol1w2",
    "mecol2w1",
    "mecol2w2",
    "oasstetc",
    "onestop",
    "potec",
    "provo",
    "psc2",
    "psr",
    "raccoons",
    "readingbrain",
    "readingbrainl2",
    "rsc",
    "sbsat",
    "uclcorpus",
    "vqamhug",
    "zuco1",
    "zuco2",
]


# Licence + citation per corpus, so attribution travels into export bundles
# (spec §8). Populate from the "Data license" column of the UZH dataset review
# table (https://pub.cl.uzh.ch/projects/eyetracker/datasets.html -- the values
# are in the page's inline `const DATA` array, alongside a `const BIBTEX` map
# for the citations). Leave a corpus out rather than guessing: the default
# below tells the reader to consult the corpus itself.
CORPUS_INFO: dict[str, dict] = {
    "potec": {"license": "CC-BY-4.0", "citation": "Jakobi et al. 2024"},
    "onestop": {"license": "CC-BY-4.0", "citation": "Berzak et al. 2025"},
    "copco": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2022"},
    "provo": {"license": "CC-BY-4.0", "citation": "Luke & Christianson 2018"},
    "zuco1": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2018"},
    "zuco2": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2020"},
}


class OutOfDiskError(RuntimeError):
    """Raised when free space drops below MIN_FREE_GB."""


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024**3)


def check_free_space(path: Path) -> None:
    """Stop before filling the disk. Raw downloads are kept, never deleted."""
    free = _free_gb(path)
    if free < MIN_FREE_GB:
        raise OutOfDiskError(
            f"Only {free:.1f} GB free; need {MIN_FREE_GB:.0f} GB. "
            "Free space or move the raw downloads, then rerun."
        )


def _canonical_name(dataset: str) -> str:
    """EyeGenBench's CamelCase directory name for a lowercase dataset key.

    Falls back to the string it was passed when EyeGenBench (or its
    `DataModuleFactory`) is not importable, which is what keeps the
    pure-pandas tests -- which call `build_bundle("PoTeC", ...)` directly,
    with no EyeGenBench installation on the test's Python -- working.
    """
    try:
        from eyegenbench.data.utils.factory import DataModuleFactory  # noqa: PLC0415
    except ImportError:
        return str(dataset)

    for name in DataModuleFactory.datamodules:
        if name.lower() == str(dataset).lower():
            return name
    return str(dataset)


def _disambiguate_repeated_readings(
    fix_df: pd.DataFrame, words: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Give each reading its own ``unique_paragraph_id`` (R17).

    EyeGenBench keys `place_fixations`'s join on `unique_paragraph_id`, which
    is correct for the stimulus-word broadcast but loses repeated readings: a
    participant who read the same paragraph twice (e.g. OneStop's repeated
    reading condition) would otherwise have both readings collapse into one
    scanpath, since `data._disambiguate_repeated_readings` only reads a
    `TRIAL_INDEX` column EyeGenBench frames never carry.

    For a `(participant, paragraph)` pair with only one distinct
    `eyegenbench_trial_id`, nothing changes. Where there is more than one, the
    2nd and later readings (in a stable rank of the distinct trial ids) get
    `paragraph_id + "__r{n}"`, and that paragraph's word rows are duplicated
    under the new key so every reading keeps full geometry.

    Returns ``(fix_df, words, n_repeated)`` -- the fixation and words frames
    with the rewritten keys, and the number of readings that were rewritten
    (for the manifest's `repeated_readings` field).
    """
    fix_df = fix_df.copy()
    trial_col = "eyegenbench_trial_id"
    if trial_col not in fix_df.columns:
        return fix_df, words, 0

    distinct_trials = (
        fix_df.groupby(["unique_participant_id", "unique_paragraph_id"])[trial_col]
        .nunique()
        .rename("n_readings")
    )
    repeated_keys = distinct_trials[distinct_trials > 1].index
    if len(repeated_keys) == 0:
        return fix_df, words, 0

    new_paragraph_frames = []
    n_repeated = 0
    for participant, paragraph in repeated_keys:
        mask = (fix_df["unique_participant_id"] == participant) & (
            fix_df["unique_paragraph_id"] == paragraph
        )
        trial_ids = sorted(fix_df.loc[mask, trial_col].unique())
        for rank, trial_id in enumerate(trial_ids[1:], start=2):
            reading_mask = mask & (fix_df[trial_col] == trial_id)
            new_key = f"{paragraph}__r{rank}"
            fix_df.loc[reading_mask, "unique_paragraph_id"] = new_key
            paragraph_words = words[words["unique_paragraph_id"] == paragraph].copy()
            paragraph_words["unique_paragraph_id"] = new_key
            new_paragraph_frames.append(paragraph_words)
            n_repeated += 1

    if new_paragraph_frames:
        words = pd.concat([words, *new_paragraph_frames], ignore_index=True)
    return fix_df, words, n_repeated


def build_bundle(dataset, fix_df, text_df, participant_df, raw_fix_df, out_root):
    """Write one dataset's bundle and return its manifest entry."""
    from scanpath_studio.eyegenbench_geometry import display_spec_for

    words, report = resolve_geometry(dataset, text_df, raw_fix_df)

    # R16: EyeGenBench's own (finer-grained, per-reading) trial id must not be
    # emitted as `unique_trial_id` -- `data.normalize_fixations` hardcodes
    # that exact name to `trial_id`, overriding EYEGENBENCH_FIX_SCHEMA and
    # breaking the stimulus-word broadcast join.
    fix_df = fix_df.rename(columns={"unique_trial_id": "eyegenbench_trial_id"})

    # R17: give each repeated reading of a paragraph its own paragraph key,
    # and duplicate that paragraph's word rows under each new key, before
    # placing fixations.
    fix_df, words, repeated_readings = _disambiguate_repeated_readings(fix_df, words)

    fixations = place_fixations(fix_df, words)

    # R11: stamp fixations with their *paragraph's* geometry tier, not a
    # single dataset-level value -- carry the per-paragraph `geometry_source`
    # already on `words` across the join explicitly, since `place_fixations`
    # does not bring it along.
    paragraph_geometry = words.drop_duplicates("unique_paragraph_id").set_index(
        "unique_paragraph_id"
    )["geometry_source"]
    fixations["geometry_source"] = fixations["unique_paragraph_id"].map(
        paragraph_geometry
    )

    name = _canonical_name(dataset)
    directory = Path(out_root) / name
    directory.mkdir(parents=True, exist_ok=True)
    words.to_parquet(directory / "words.parquet", index=False)
    fixations.to_parquet(directory / "fixations.parquet", index=False)
    if participant_df is None:
        participant_df = pd.DataFrame({"unique_participant_id": []})
    participant_df.to_parquet(directory / "participants.parquet", index=False)

    spec = display_spec_for(dataset)
    languages = sorted(set(text_df["text_language"].astype(str)))
    info = CORPUS_INFO.get(str(dataset).lower(), {})
    return {
        "name": name,
        "language": ", ".join(languages),
        "monitor": [spec.width_px, spec.height_px],
        "n_readers": int(fix_df["unique_participant_id"].nunique()),
        "n_texts": int(text_df["unique_paragraph_id"].nunique()),
        "n_fixations": int(len(fixations)),
        # Spec §8: attribution travels with the data into export bundles.
        "license": info.get("license", "unknown - consult the corpus"),
        "citation": info.get("citation", ""),
        # R5: provenance for how far to trust a reconstructed layout --
        # true-to-scale when monospaced, not otherwise.
        "monospaced": spec.monospaced,
        # R17: how many readings were disambiguated by a repeated-reading
        # suffix, so the docs page can be honest about partial coverage.
        "repeated_readings": repeated_readings,
        **report,
    }


def write_manifest(out_root: Path, entries: list) -> None:
    """Merge ``entries`` into the manifest, replacing any rerun dataset."""
    path = Path(out_root) / MANIFEST_NAME
    existing = json.loads(path.read_text())["datasets"] if path.is_file() else []
    merged = {e["name"]: e for e in existing}
    merged.update({e["name"]: e for e in entries})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"datasets": sorted(merged.values(), key=lambda e: e["name"])}, indent=1
        )
    )


def run_prepare_data(dataset: str, eyegenbench_root: Path):
    """Run EyeGenBench's pipeline; return (fix, text, participant, raw_fix).

    `load_dataset` resolves its config and data paths *relative to the
    EyeGenBench repo root*, so we chdir there for the call. Raw downloads land
    in `<eyegenbench_root>/data/<Name>/`, which is also where we look for the
    interim file that still carries the real interest-area boxes.
    """
    import os  # noqa: PLC0415

    import eyegenbench.data  # noqa: F401, PLC0415 - registers every datamodule
    from eyegenbench.data.utils.load import load_dataset  # noqa: PLC0415

    previous = Path.cwd()
    try:
        os.chdir(eyegenbench_root)
        fix_df, text_df, participant_df = load_dataset(dataset)
    finally:
        os.chdir(previous)

    raw = None
    interim = eyegenbench_root / "data" / _canonical_name(dataset) / "interim"
    for candidate in sorted(interim.glob("*.csv")) if interim.is_dir() else []:
        try:
            head = pd.read_csv(candidate, nrows=0)
        except Exception:  # noqa: BLE001 - a non-CSV in interim is not fatal
            continue
        if "CURRENT_FIX_INTEREST_AREA_DATA" in head.columns:
            raw = pd.read_csv(candidate)
            break
    return fix_df, text_df, participant_df, raw


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", help="Repeatable.")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--eyegenbench-root",
        default="../EyeGenBench/code",
        help="Checkout of github.com/EyeBench/EyeGenBench. Raw downloads land "
        "in its data/ directory and are kept, never deleted.",
    )
    parser.add_argument("--out", default="data/EyeGenBench")
    args = parser.parse_args(argv)

    names = DATASETS if args.all else (args.dataset or [])
    if not names:
        parser.error("pass --dataset NAME (repeatable) or --all")

    eyegenbench_root = Path(args.eyegenbench_root).resolve()
    if not (eyegenbench_root / "eyegenbench").is_dir():
        parser.error(f"{eyegenbench_root} is not an EyeGenBench checkout")
    out_root = Path(args.out)
    entries, skipped = [], []
    for name in names:
        try:
            check_free_space(eyegenbench_root)
            fix, text, parts, raw = run_prepare_data(name, eyegenbench_root)
            entry = build_bundle(name, fix, text, parts, raw, out_root)
            # R2/manifest contract: a skipped or failed dataset must not get a
            # manifest entry -- write_manifest only ever sees a dataset whose
            # three Parquet files are already on disk, so a run interrupted
            # halfway still passes eyegenbench_present.
            write_manifest(out_root, [entry])
            entries.append(entry)
            print(
                f"[ok]   {name}: {entry['geometry_source']}, "
                f"{entry['n_fixations']} fixations, {entry['n_readers']} readers"
            )
        except OutOfDiskError as exc:
            print(f"[stop] {exc}")
            break
        except Exception as exc:  # noqa: BLE001 - one corpus must not stop the run
            skipped.append((name, str(exc)))
            print(f"[skip] {name}: {exc}")

    print(f"\nPrepared {len(entries)}; skipped {len(skipped)}.")
    for name, reason in skipped:
        print(f"  {name}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
