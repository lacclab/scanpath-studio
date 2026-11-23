"""Build a small, representative demo subset from the OneStop eye-tracking exports.

The bundled sample data ships with the wheel and powers the "Bundled demo"
mode. We aim for a corpus that lets users actually exercise every feature
without uploading their own data: a handful of participants reading the same
paragraphs at both Adv and Ele difficulty levels.

The default slice is two readers in the published L1 cohort who read the twelve
paragraph versions pictured in ``sample_data/images/``. Their raw gaze comes
from the OneStop EyeLink ASC recordings. The fixation report supplies each
paragraph's interest period and the origin of its trial clock.

Paragraph PNGs are rendered separately. Each is placed at the experiment's
``IMGLOAD`` origin (368, 186) so its text aligns with the recorded word boxes.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO

import pandas as pd

DATA_DIR = Path(__file__).parent
DEFAULT_SOURCE_DIR = DATA_DIR / "OneStop"
DEFAULT_OUTPUT_DIR = DATA_DIR / "sample_data"
DEMO_PARTICIPANTS = ("l37_273", "l7_183")
DEMO_ARTICLES = ((2, 1), (2, 2))

# Search for the demo slice in at most this many rows of each giant source CSV;
# large enough to span many participants and trials while staying
# memory-friendly. The readers it picks are then read in full.
DEFAULT_MAX_ROWS = 300_000

IA_KEEP_COLUMNS = [
    "participant_id",
    "TRIAL_INDEX",
    "trial_index",
    "article_batch",
    "article_id",
    "paragraph_id",
    "difficulty_level",
    "repeated_reading_trial",
    "article_title",
    "question",
    "selected_answer",
    "is_correct",
    "IA_ID",
    "IA_LABEL",
    "IA_LEFT",
    "IA_RIGHT",
    "IA_TOP",
    "IA_BOTTOM",
    "IA_DWELL_TIME",
    "IA_FIRST_FIXATION_DURATION",
    "IA_FIRST_RUN_DWELL_TIME",
    "IA_SECOND_RUN_DWELL_TIME",
    "IA_LAST_RUN_DWELL_TIME",
    "IA_FIXATION_COUNT",
    "IA_SKIP",
    "IA_REGRESSION_IN",
    "IA_REGRESSION_IN_COUNT",
    "IA_REGRESSION_OUT",
    "IA_REGRESSION_OUT_COUNT",
    "IA_REGRESSION_PATH_DURATION",
    "TRIAL_DWELL_TIME",
    "TRIAL_FIXATION_COUNT",
    "TRIAL_IA_COUNT",
    "word_length",
    "word_length_no_punctuation",
    "wordfreq_frequency",
    "subtlex_frequency",
    "gpt2_surprisal",
    "universal_pos",
    "ptb_pos",
    "Reduced_POS",
    "dependency_relation",
    "head_word_index",
    "distance_to_head",
    "morphological_features",
    "entity_type",
    # The published report labels each word and gives all span ranges. Some
    # exports also include separate boolean flags and the first range's bounds.
    "question_preview",
    "auxiliary_span_type",
    "is_in_aspan",
    "is_in_dspan",
    "aspan_ind_start",
    "aspan_ind_end",
    "dspan_ind_start",
    "dspan_ind_end",
    "critical_span_indices",
    "distractor_span_indices",
]

FIXATION_KEEP_COLUMNS = [
    "participant_id",
    "TRIAL_INDEX",
    "trial_index",
    "article_batch",
    "article_id",
    "paragraph_id",
    "difficulty_level",
    "repeated_reading_trial",
    "article_title",
    "question",
    "selected_answer",
    "is_correct",
    "CURRENT_FIX_INDEX",
    "TRIAL_START_TIME",
    "IP_START_TIME",
    "IP_END_TIME",
    "CURRENT_FIX_START",
    "CURRENT_FIX_END",
    "CURRENT_FIX_DURATION",
    "CURRENT_FIX_X",
    "CURRENT_FIX_Y",
    "CURRENT_FIX_INTEREST_AREA_ID",
    "CURRENT_FIX_INTEREST_AREA_LABEL",
    "CURRENT_FIX_VALIDITY",
    "NEXT_SAC_DIRECTION",
    "NEXT_SAC_AMPLITUDE",
    "EYE_TRACKED",
    "question_preview",  # needed by normalize_fixations so trial-level Hunting flag survives
]


def _resolve_csv_path(source_csv: Path) -> Path:
    """Accept either `foo.csv` or `foo.csv.zip` — fall back to the zipped
    variant when the plain CSV isn't on disk. Lacclab exports ship zipped."""
    if source_csv.exists():
        return source_csv
    zipped = source_csv.with_suffix(source_csv.suffix + ".zip")
    if zipped.exists():
        return zipped
    raise FileNotFoundError(f"Neither {source_csv} nor {zipped} found.")


def load_subset(
    source_csv: Path, preferred_columns: Iterable[str], max_rows: int
) -> pd.DataFrame:
    source_csv = _resolve_csv_path(source_csv)
    available_cols = pd.read_csv(source_csv, nrows=0, low_memory=False).columns
    use_cols = [col for col in preferred_columns if col in available_cols]
    missing_core = [
        col
        for col in ["participant_id", "TRIAL_INDEX", "repeated_reading_trial"]
        if col not in use_cols
    ]
    if missing_core:
        raise RuntimeError(f"Missing required columns {missing_core} in {source_csv}")
    return pd.read_csv(source_csv, usecols=use_cols, nrows=max_rows, low_memory=False)


def load_participants(
    source_csv: Path,
    preferred_columns: Iterable[str],
    participants: Iterable[str],
    chunksize: int = 500_000,
) -> pd.DataFrame:
    """Every row of ``participants`` in ``source_csv``, read in chunks.

    ``load_subset``'s row cap bounds the *search* for a demo slice; the slice
    itself has to be read whole. Capped, the IA and fixation reports stop at
    different readers — an IA row per word, a fixation row per fixation — so a
    reader could land inside one cap and outside the other, leaving the demo a
    reader with word boxes and no fixations."""
    source_csv = _resolve_csv_path(source_csv)
    available_cols = pd.read_csv(source_csv, nrows=0, low_memory=False).columns
    use_cols = [col for col in preferred_columns if col in available_cols]
    wanted = {str(p) for p in participants}
    parts = [
        chunk[chunk["participant_id"].astype(str).isin(wanted)]
        for chunk in pd.read_csv(
            source_csv, usecols=use_cols, chunksize=chunksize, low_memory=False
        )
    ]
    return pd.concat(parts, ignore_index=True)


def check_fixations_cover_words(ia: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Raise unless every ``(participant, trial)`` in ``ia`` has fixations.

    A trial with word boxes and no fixations has no scanpath to show; a demo
    that ships one is a broken demo, so the build stops instead of writing it."""
    keys = ["participant_id", "unique_trial_id"]
    have = set(map(tuple, fixations[keys].astype(str).drop_duplicates().to_numpy()))
    need = set(map(tuple, ia[keys].astype(str).drop_duplicates().to_numpy()))
    missing = sorted(need - have)
    if missing:
        raise RuntimeError(
            f"{len(missing)} demo trial(s) have word boxes but no fixations, "
            f"e.g. {missing[:3]}."
        )


def normalize_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["repeated_reading_trial"] = (
        df["repeated_reading_trial"].fillna(False).astype(bool)
    )
    return df


def add_unique_ids(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "article_batch",
        "article_id",
        "paragraph_id",
        "difficulty_level",
        "participant_id",
        "repeated_reading_trial",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns for id creation: {missing}")
    df = normalize_flags(df)
    df["unique_paragraph_id"] = (
        df["article_batch"].astype(str)
        + "_"
        + df["article_id"].astype(str)
        + "_"
        + df["paragraph_id"].astype(str)
        + "_"
        + df["difficulty_level"].astype(str)
    )
    # The demo keeps first readings only (`filter_demo`), so a reader reads each
    # paragraph once and reader + paragraph is the whole trial identity — the
    # same id `datasets._compose_onestop_ids` gives that trial in the corpus.
    df["unique_trial_id"] = (
        df["participant_id"].astype(str) + "_" + df["unique_paragraph_id"]
    )
    return df


def pick_demo_slice(
    ia_df: pd.DataFrame,
    n_participants: int,
    n_articles: int,
    seed: int,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Pick participants + articles so each participant reads every article,
    and across participants both Adv and Ele appear for each article.

    Reading-research observation: in OneStop each participant reads a given
    article at exactly one difficulty. To still demo Adv/Ele contrasts, we
    need different participants reading the same article at different levels.
    """
    rng_seed = seed
    first_reading = ia_df[~ia_df["repeated_reading_trial"].astype(bool)].copy()
    first_reading["article"] = list(
        zip(first_reading["article_batch"], first_reading["article_id"])
    )

    # Participant → set of (article, difficulty) tuples
    pa_diffs = (
        first_reading.groupby(["participant_id", "article", "difficulty_level"])
        .size()
        .reset_index(name="n_paragraphs")
    )

    # Greedy search: try random participant samples, pick the one whose joint
    # article coverage spans both difficulties on the most articles.
    candidates = sorted(first_reading["participant_id"].astype(str).unique())
    # Prefer participants who have at least one Hunting (preview) trial — the
    # demo is the only way for someone without OneStop access to exercise the
    # critical-span overlay, and only Hunting trials trigger it. ~43% of L2
    # pids have Hunting, so this leaves plenty of search room. Falls back to
    # the full candidate pool if `question_preview` isn't in the data.
    if "question_preview" in first_reading.columns:
        hunters = set(
            first_reading[first_reading["question_preview"].fillna(False).astype(bool)][
                "participant_id"
            ]
            .astype(str)
            .unique()
        )
        candidates = [c for c in candidates if c in hunters] or candidates
    if len(candidates) < n_participants:
        raise RuntimeError(
            f"Only {len(candidates)} participants in slice; need {n_participants}."
        )

    rng = pd.Series(candidates)
    best_score = -1
    best_participants: list[str] = []
    best_articles: list = []
    for trial in range(200):
        sample = rng.sample(n=n_participants, random_state=rng_seed + trial).tolist()
        sample_diffs = pa_diffs[pa_diffs["participant_id"].isin(sample)]
        # For each article, how many distinct difficulties appear in this sample?
        per_article = sample_diffs.groupby("article")["difficulty_level"].nunique()
        spanning = per_article[per_article >= 2]
        # Articles all sample participants read (joint coverage)
        per_p_articles = sample_diffs.groupby("participant_id")["article"].apply(set)
        if len(per_p_articles) < n_participants:
            continue
        joint = set.intersection(*per_p_articles.values)
        useful = [a for a in joint if a in spanning.index]
        score = len(useful)
        if score > best_score:
            best_score = score
            best_participants = sorted(sample)
            best_articles = sorted(useful)
        if best_score >= n_articles:
            break

    if best_score < n_articles:
        raise RuntimeError(
            f"Could not find {n_participants} participants jointly reading "
            f"{n_articles} articles that span Adv+Ele. Best found: {best_score}. "
            "Try increasing --max-rows or relaxing constraints."
        )

    return best_participants, list(best_articles[:n_articles])


def filter_demo(
    df: pd.DataFrame,
    participants: list[str],
    articles: list[tuple[int, int]],
) -> pd.DataFrame:
    article_tuples = set(articles)
    mask = df["participant_id"].isin(participants) & (
        ~df["repeated_reading_trial"].astype(bool)
    )
    df = df[mask].copy()
    df["_article"] = list(zip(df["article_batch"], df["article_id"]))
    df = df[df["_article"].isin(article_tuples)].drop(columns=["_article"])
    return df


def with_span_fields(words: pd.DataFrame) -> pd.DataFrame:
    """Expose the demo's highlight flags and first-range bounds from the report."""
    if "auxiliary_span_type" not in words:
        return words
    words = words.copy()
    for prefix, label in (("aspan", "critical"), ("dspan", "distractor")):
        words[f"is_in_{prefix}"] = words["auxiliary_span_type"].eq(label)
        indices = f"{label}_span_indices"
        if indices in words:
            # Preserve the endpoints of the first range exactly as published.
            # Each word's label above covers the full list of ranges.
            bounds = words[indices].str.extract(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
            words[[f"{prefix}_ind_start", f"{prefix}_ind_end"]] = bounds.astype("Int64")
    return words


def with_stimulus_images(frame: pd.DataFrame, image_dir: Path) -> pd.DataFrame:
    images = {
        p.name.removesuffix("__paragraph.png"): f"images/{p.name}"
        for p in image_dir.glob("*__paragraph.png")
    }
    paths = frame["unique_paragraph_id"].map(images)
    return frame.assign(
        image_path=paths,
        image_x=pd.Series(368, index=frame.index).where(paths.notna()),
        image_y=pd.Series(186, index=frame.index).where(paths.notna()),
    )


#: Tables shipped as Parquet alone. The app reads the Parquet, and a CSV copy of
#: every 1 kHz sample would triple the wheel's size.
PARQUET_ONLY_TABLES = frozenset({"raw_gaze"})


def write_tables(output_dir: Path, **tables: pd.DataFrame) -> None:
    """Finish every table before replacing the packaged data.

    Each table ships as CSV and Parquet, except ``PARQUET_ONLY_TABLES``, whose
    CSV an older build may have left is removed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir) as temp:
        for name, frame in tables.items():
            if name not in PARQUET_ONLY_TABLES:
                frame.to_csv(Path(temp) / f"{name}.csv", index=False)
            frame.to_parquet(Path(temp) / f"{name}.parquet", index=False)
        for artifact in Path(temp).iterdir():
            artifact.replace(output_dir / artifact.name)
    for name in PARQUET_ONLY_TABLES & tables.keys():
        (output_dir / f"{name}.csv").unlink(missing_ok=True)


def without_lost_pupil(x: float, y: float, pupil: float) -> float:
    """A sample's pupil value, missing when the tracker lost the eye.

    EyeLink writes a pupil size of 0 for a sample it has no position for: it
    measured nothing, and a 0 would read as a real, tiny pupil.
    """
    if pupil == 0 and (math.isnan(x) or math.isnan(y)):
        return math.nan
    return pupil


def _paragraph_samples(asc: BinaryIO, trial) -> pd.DataFrame:
    """Read one matching ASC recording block on the fixation report's clock."""
    start, stop = trial.IP_START_TIME, trial.IP_END_TIME
    if not trial.TRIAL_START_TIME <= start < stop:
        raise ValueError(f"Invalid paragraph interval for {trial.unique_trial_id}")
    eye = trial.EYE_TRACKED.upper().encode("ascii")
    rows = []
    gaze_header = False
    pupil_field = None
    for line in asc:
        if line.startswith(b"PUPIL"):
            pupil_field = {b"AREA": "pupil_area", b"DIAMETER": "pupil_diameter"}.get(
                line.split()[1]
            )
        elif line.startswith(b"SAMPLES"):
            # Each OneStop session records one eye. A binocular or HREF export
            # would give the first two numbers a different meaning.
            if line.split()[1:4] != [b"GAZE", eye, b"RATE"]:
                raise ValueError(
                    f"Expected monocular GAZE {eye.decode()} for {trial.unique_trial_id}"
                )
            gaze_header = True
        elif line.startswith(b"END"):
            if int(line.split()[1]) < stop or not rows:
                raise ValueError(
                    f"Incomplete paragraph recording for {trial.unique_trial_id}"
                )
            break
        elif line.startswith(b"START"):
            raise ValueError(
                f"Missing END in the recording for {trial.unique_trial_id}"
            )
        elif line[:1].isdigit():
            fields = line.split()
            time = int(fields[0])
            if start <= time < stop:
                if not gaze_header:
                    raise ValueError(
                        f"Missing GAZE sample header for {trial.unique_trial_id}"
                    )
                if pupil_field is None:
                    raise ValueError(
                        f"Missing pupil measurement type for {trial.unique_trial_id}"
                    )
                x, y, pupil = (
                    float(v) if v != b"." else float("nan") for v in fields[1:4]
                )
                pupil = without_lost_pupil(x, y, pupil)
                rows.append((x, y, time - trial.TRIAL_START_TIME, pupil))
    else:
        raise ValueError(f"Missing END in the recording for {trial.unique_trial_id}")
    frame = pd.DataFrame(rows, columns=["x", "y", "timestamp_ms", pupil_field])
    frame["eye"] = trial.EYE_TRACKED
    frame.insert(0, "unique_paragraph_id", trial.unique_paragraph_id)
    frame.insert(0, "unique_trial_id", trial.unique_trial_id)
    frame.insert(0, "participant_id", trial.participant_id)
    return frame


def extract_raw_gaze(fixations: pd.DataFrame, asc_dir: Path) -> pd.DataFrame:
    """Every ASC sample in the bundled readings' paragraph intervals.

    The report's TRIAL_START_TIME identifies the ASC START block exactly.
    IP_START_TIME is inclusive and IP_END_TIME is exclusive, in tracker ms.
    """
    columns = [
        "participant_id",
        "unique_trial_id",
        "unique_paragraph_id",
        "TRIAL_START_TIME",
        "IP_START_TIME",
        "IP_END_TIME",
        "EYE_TRACKED",
    ]
    trials = fixations[columns].drop_duplicates()
    if (
        trials.empty
        or trials.isna().any().any()
        or any(
            trials.duplicated(["participant_id", key]).any()
            for key in ("unique_trial_id", "TRIAL_START_TIME")
        )
    ):
        raise ValueError(
            "Each demo reading needs one distinct recording block, paragraph interval and tracked eye."
        )
    files = {path.name.lower(): path for path in asc_dir.iterdir() if path.is_file()}
    samples = []
    for participant, readings in trials.groupby("participant_id", sort=False):
        stem = participant.lower()
        path = files.get(f"{stem}_clean.asc") or files.get(f"{stem}.asc")
        if path is None:
            raise FileNotFoundError(
                f"No OneStop ASC recording for {participant} in {asc_dir}"
            )
        pending = {r.TRIAL_START_TIME: r for r in readings.itertuples(index=False)}
        with path.open("rb") as asc:
            for line in asc:
                if line.startswith(b"START"):
                    trial = pending.pop(int(line.split()[1]), None)
                    if trial is not None:
                        samples.append(_paragraph_samples(asc, trial))
                        if not pending:
                            break
        if pending:
            missing = ", ".join(r.unique_trial_id for r in pending.values())
            raise ValueError(
                f"{path.name} has no matching recording block for {missing}"
            )
    return pd.concat(samples, ignore_index=True)


def _read_bundle(output_dir: Path, name: str) -> pd.DataFrame:
    """Load a bundled sample table, preferring Parquet over CSV."""
    parquet = output_dir / f"{name}.parquet"
    csv = output_dir / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv, low_memory=False)
    raise FileNotFoundError(f"Neither {parquet} nor {csv} found.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--participants",
        type=int,
        help="Search for a custom slice with this many participants.",
    )
    parser.add_argument(
        "--articles",
        type=int,
        help="Search for a custom slice with this many articles.",
    )
    parser.add_argument("--seed", type=int, help="Random seed for a custom slice.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help="Cap on rows read from each source CSV while searching for the "
        "slice; the picked readers are then read in full.",
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument(
        "--asc-dir",
        type=Path,
        help="Directory of OneStop .asc or _clean.asc files (default: SOURCE_DIR/asc).",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--raw-gaze-only",
        action="store_true",
        help="Skip the source rebuild; only regenerate raw_gaze.parquet "
        "from the ASC recordings and the bundled fixation report.",
    )
    args = parser.parse_args()

    asc_dir = args.asc_dir or args.source_dir / "asc"
    if args.raw_gaze_only:
        gaze = extract_raw_gaze(_read_bundle(args.output_dir, "fixations"), asc_dir)
        write_tables(args.output_dir, raw_gaze=gaze)
        print(f"Written {len(gaze):,} gaze samples.")
        return

    participants, articles = list(DEMO_PARTICIPANTS), list(DEMO_ARTICLES)
    if any(
        value is not None for value in (args.participants, args.articles, args.seed)
    ):
        ia_search = add_unique_ids(
            load_subset(
                args.source_dir / "ia_Paragraph.csv", IA_KEEP_COLUMNS, args.max_rows
            )
        )
        fix_search = load_subset(
            args.source_dir / "fixations_Paragraph.csv",
            FIXATION_KEEP_COLUMNS,
            args.max_rows,
        )
        participants, articles = pick_demo_slice(
            ia_search[ia_search["participant_id"].isin(fix_search["participant_id"])],
            args.participants if args.participants is not None else 3,
            args.articles if args.articles is not None else 2,
            args.seed if args.seed is not None else 20260520,
        )
    ia_full = add_unique_ids(
        load_participants(
            args.source_dir / "ia_Paragraph.csv", IA_KEEP_COLUMNS, participants
        )
    )
    fix_full = add_unique_ids(
        load_participants(
            args.source_dir / "fixations_Paragraph.csv",
            FIXATION_KEEP_COLUMNS,
            participants,
        )
    )

    ia_sample = with_span_fields(filter_demo(ia_full, participants, articles))
    fix_sample = filter_demo(fix_full, participants, articles)
    check_fixations_cover_words(ia_sample, fix_sample)

    if set(fix_sample["participant_id"]) != set(participants):
        raise ValueError("The OneStop reports are missing a selected demo participant.")
    image_dir = args.output_dir / "images"
    raw_gaze = extract_raw_gaze(fix_sample, asc_dir)
    write_tables(
        args.output_dir,
        ia=with_stimulus_images(ia_sample, image_dir),
        fixations=with_stimulus_images(fix_sample, image_dir),
        raw_gaze=raw_gaze,
    )

    # Remove any *_full CSVs an older build left behind, so they don't bloat
    # the wheel.
    for legacy in [
        args.output_dir / "ia_full.csv",
        args.output_dir / "fixations_full.csv",
    ]:
        if legacy.exists():
            legacy.unlink()

    print(
        "Demo slice written:\n"
        f"  participants: {participants}\n"
        f"  articles: {articles}\n"
        f"  ia rows: {len(ia_sample):,}\n"
        f"  fixation rows: {len(fix_sample):,}\n"
        f"  gaze samples: {len(raw_gaze):,}\n"
        f"  output: {args.output_dir}"
    )


if __name__ == "__main__":
    main()
