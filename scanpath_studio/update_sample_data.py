"""Build a small, representative demo subset from the OneStop eye-tracking exports.

The bundled sample data ships with the wheel and powers the "Bundled demo"
mode. We aim for a corpus that lets users actually exercise every feature
without uploading their own data: a handful of participants reading the same
paragraphs at both Adv and Ele difficulty levels.

The default slice is two readers in the published L1 cohort who read twelve
paragraphs. Each reading keeps every screen the reader saw — the article's
title (first paragraph only), the question preview, the paragraph, the
question, the answers and the feedback — read from the full release's per-part
interest-area and fixation reports, each part one screen of its trial as
`datasets.load_onestop` makes it. Their raw gaze comes from the OneStop EyeLink
ASC recordings: the fixation reports supply each screen's interest period and
the origin of its trial clock.

Each screen's stimulus is the experiment's own: the images the Experiment
Builder project drew, placed where its DataViewer draw list (``VC_<n>.vcl``)
put them on the 2560x1440 display, which is what DataViewer shows behind the
trial.
"""

from __future__ import annotations

import argparse
import io
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO

import pandas as pd
from PIL import Image

from .datasets import (
    _ONESTOP_PARTS,
    _onestop_parts_as_screens,
)

DATA_DIR = Path(__file__).parent
DEFAULT_SOURCE_DIR = DATA_DIR / "OneStop"
DEFAULT_OUTPUT_DIR = DATA_DIR / "sample_data"
DEMO_PARTICIPANTS = ("l37_273", "l7_183")
DEMO_ARTICLES = ((2, 1), (2, 2))

#: The screens of a OneStop trial the demo keeps, in presentation order: every
#: part of the full release but QA, which is the Questions and Answers screens
#: again as one interest period (`datasets.onestop_regime_parts`). A reading has
#: the screens its reports hold — only an article's first paragraph has a title,
#: only the information-seeking regimes a question preview.
DEMO_PARTS = tuple(part for part in _ONESTOP_PARTS if part != "QA")

#: OneStop's display (``DISPLAY_COORDS 0 0 2559 1439``), the surface every draw
#: list is drawn on.
SCREEN_SIZE = (2560, 1440)

#: How far, in ms, a screen's onset in its draw list may sit from its part's
#: interest-period start in the report. The two agree to a few ms; a trial's
#: screens are hundreds of ms apart.
ONSET_TOLERANCE_MS = 20

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


def load_parts(
    source_dir: Path,
    kind: str,
    preferred_columns: Iterable[str],
    participants: Iterable[str],
) -> pd.DataFrame:
    """Every ``DEMO_PARTS`` report of ``kind`` for ``participants``, stamped ``part``.

    ``kind`` is ``"ia"`` or ``"fixations"``; each part's report is
    ``<kind>_<Part>.csv`` (or ``.csv.zip``), as the full release names them."""
    columns, readers = list(preferred_columns), list(participants)
    return pd.concat(
        [
            load_participants(
                source_dir / f"{kind}_{part}.csv", columns, readers
            ).assign(part=part)
            for part in DEMO_PARTS
        ],
        ignore_index=True,
        sort=False,
    )


def check_fixations_cover_words(ia: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """Raise unless the word boxes and the fixations cover the same screens.

    A screen with word boxes and no fixations has no scanpath to show, and one
    with fixations and no word boxes is refused as a multipart pair; a demo that
    ships either is a broken demo, so the build stops instead of writing it.
    Without a ``part`` column a trial is one screen."""
    keys = ["participant_id", "unique_trial_id"]
    if "part" in ia.columns and "part" in fixations.columns:
        keys.append("part")
    have = set(map(tuple, fixations[keys].astype(str).drop_duplicates().to_numpy()))
    need = set(map(tuple, ia[keys].astype(str).drop_duplicates().to_numpy()))
    for gap, what in (
        (need - have, "word boxes but no fixations"),
        (have - need, "fixations but no word boxes"),
    ):
        if gap:
            raise RuntimeError(
                f"{len(gap)} demo screen(s) have {what}, e.g. {sorted(gap)[:3]}."
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
    """Expose the demo's highlight flags and first-range bounds from the report.

    The spans are ranges of the paragraph's words. The other screens' reports
    carry the same labels by word position — the fourth word of a title is
    "critical" when the span starts at the paragraph's fourth — so only the
    Paragraph screen's words are flagged."""
    if "auxiliary_span_type" not in words:
        return words
    words = words.copy()
    passage = (
        words["part"].eq("Paragraph")
        if "part" in words
        else pd.Series(True, index=words.index)
    )
    for prefix, label in (("aspan", "critical"), ("dspan", "distractor")):
        words[f"is_in_{prefix}"] = words["auxiliary_span_type"].eq(label) & passage
        indices = f"{label}_span_indices"
        if indices in words:
            # Preserve the endpoints of the first range exactly as published.
            # Each word's label above covers the full list of ranges.
            bounds = words[indices].str.extract(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
            words[[f"{prefix}_ind_start", f"{prefix}_ind_end"]] = bounds.astype(
                "Int64"
            ).where(passage)
    return words


@dataclass(frozen=True)
class DrawnImage:
    """One ``IMGLOAD TOP_LEFT`` of a draw list: an image file and its corner."""

    name: str
    x: int
    y: int
    size: tuple[int, int] | None


@dataclass
class DrawnScreen:
    """One screen of a draw list: what a ``CLEAR`` starts, ``onset_ms`` after
    the list's first screen."""

    onset_ms: int
    background: tuple[int, int, int]
    images: list[DrawnImage] = field(default_factory=list)


def read_draw_list(path: Path) -> list[DrawnScreen]:
    """The screens of one DataViewer ``.vcl`` draw list, in display order.

    Each ``CLEAR <r> <g> <b>`` starts a screen, and each ``IMGLOAD TOP_LEFT
    <file> <x> <y> [<width> <height>]`` after it draws an image with its
    top-left corner at ``(x, y)``. A line's first field is EyeLink's message
    offset — negative for later — so a screen's onset is its negated offset.
    Any other command stops the build: a screen drawn without it would show
    less than the display did."""
    screens: list[DrawnScreen] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        command = fields[1] if len(fields) > 1 else ""
        if command == "CLEAR" and len(fields) == 5:
            background = (int(fields[2]), int(fields[3]), int(fields[4]))
            screens.append(DrawnScreen(-int(fields[0]), background))
        elif command == "IMGLOAD" and screens and fields[2] == "TOP_LEFT":
            name = fields[3].replace("\\", "/").rsplit("/", 1)[-1]
            size = (int(fields[6]), int(fields[7])) if len(fields) >= 8 else None
            screens[-1].images.append(
                DrawnImage(name, int(fields[4]), int(fields[5]), size)
            )
        else:
            raise ValueError(f"{path}:{number}: unsupported draw command {line!r}")
    return screens


def match_screens(
    onsets: Mapping[str, int], screens: Sequence[DrawnScreen], *, reading: str
) -> dict[str, DrawnScreen]:
    """Each part's screen in a reading's draw list, matched by onset.

    ``onsets`` are the parts' interest-period starts, in tracker ms. A draw
    list counts from its own first screen, so the tracker time it starts at is
    the one that puts the most parts within ``ONSET_TOLERANCE_MS`` of a screen
    (the smaller total gap breaking a tie); every part must then land on a
    screen of its own."""
    best: tuple[tuple[int, int], dict[str, DrawnScreen]] | None = None
    candidates = sorted({t - s.onset_ms for t in onsets.values() for s in screens})
    for start in candidates:
        pairs: dict[str, DrawnScreen] = {}
        gap = 0
        for part, onset in onsets.items():
            screen = min(screens, key=lambda s: abs(start + s.onset_ms - onset))
            distance = abs(start + screen.onset_ms - onset)
            if distance <= ONSET_TOLERANCE_MS:
                pairs[part] = screen
                gap += distance
        score = (len(pairs), -gap)
        if best is None or score > best[0]:
            best = (score, pairs)
    pairs = best[1] if best else {}
    unmatched = sorted(set(onsets) - set(pairs))
    if unmatched or len({id(s) for s in pairs.values()}) < len(pairs):
        raise ValueError(
            f"{reading}: the draw list has no screen of its own starting at the "
            f"interest period of {unmatched or sorted(pairs)}."
        )
    return pairs


def compose_screen(
    screen: DrawnScreen, image_dir: Path
) -> tuple[Image.Image, int, int]:
    """A screen as the display showed it, cut to the region its images cover.

    Each image is drawn at its top-left corner over the screen's background —
    its transparent pixels show the background, as on the display — and an
    image drawn wholly off the display is left out. Returns the cut and its
    top-left corner on the display."""
    width, height = SCREEN_SIZE
    canvas = Image.new("RGB", SCREEN_SIZE, screen.background)
    left, top, right, bottom = width, height, 0, 0
    for drawn in screen.images:
        with Image.open(image_dir / drawn.name) as source:
            image = source.convert("RGBA")
        if drawn.size is not None and drawn.size != image.size:
            raise ValueError(
                f"{drawn.name} is {image.size[0]}x{image.size[1]}, but the draw "
                f"list draws it at {drawn.size[0]}x{drawn.size[1]}."
            )
        x0, y0 = max(drawn.x, 0), max(drawn.y, 0)
        x1 = min(drawn.x + image.width, width)
        y1 = min(drawn.y + image.height, height)
        if x0 >= x1 or y0 >= y1:
            continue
        canvas.paste(image, (drawn.x, drawn.y), image)
        left, top = min(left, x0), min(top, y0)
        right, bottom = max(right, x1), max(bottom, y1)
    if left >= right:
        raise ValueError("The screen draws no image on the display.")
    return canvas.crop((left, top, right, bottom)), left, top


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_list_projects(
    participants: Iterable[str], experiment_dirs: Sequence[Path]
) -> dict[str, Path]:
    """The ``runtime`` folder of the Experiment Builder project each reader ran.

    A project keeps each session's DataViewer files under
    ``runtime/dataviewer/<reader>/``; a reader found in no project, or in
    several, stops the build."""
    found: dict[str, Path] = {}
    for participant in sorted(set(participants)):
        runtimes = [
            graphics.parent.parent.parent
            for root in experiment_dirs
            for graphics in root.glob(f"**/runtime/dataviewer/{participant}/graphics")
        ]
        if len(runtimes) != 1:
            raise FileNotFoundError(
                f"Expected one Experiment Builder project holding "
                f"runtime/dataviewer/{participant}/graphics under "
                f"{[str(d) for d in experiment_dirs]}, found {len(runtimes)}."
            )
        found[participant] = runtimes[0]
    return found


def stimulus_images(
    fixations: pd.DataFrame, experiment_dirs: Sequence[Path]
) -> tuple[pd.DataFrame, dict[str, bytes]]:
    """Every demo screen's stimulus, from the project its reader ran.

    A reading's draw list is ``runtime/dataviewer/<reader>/graphics/
    VC_<TRIAL_INDEX>.vcl`` — the file its recording names in ``!V DRAW_LIST``
    — and the images it draws are that project's ``runtime/images``. Returns
    one row per ``(participant_id, unique_trial_id, part)`` with its
    ``image_path`` (relative to the sample data) and ``image_x`` /
    ``image_y`` corner, and each file's bytes by its path: the PNGs, and
    ``images/manifest.csv``, which records where each screen came from — its
    draw list, the screen's onset in it, and every image drawn there with its
    corner. A paragraph's screen is one file when every reader saw the same
    pixels there, and one per reading otherwise."""
    projects = _draw_list_projects(fixations["participant_id"], experiment_dirs)
    keys = ["participant_id", "unique_trial_id", "unique_paragraph_id", "TRIAL_INDEX"]
    periods = fixations[[*keys, "part", "IP_START_TIME"]].drop_duplicates()
    if periods.duplicated([*keys, "part"]).any():
        raise ValueError("A demo screen has more than one interest period.")
    shown = []
    for (participant, trial, paragraph, index), screens in periods.groupby(
        keys, sort=True
    ):
        runtime = projects[participant]
        drawn = read_draw_list(
            runtime / "dataviewer" / participant / "graphics" / f"VC_{index}.vcl"
        )
        onsets = dict(zip(screens["part"], screens["IP_START_TIME"].astype(int)))
        for part, screen in match_screens(onsets, drawn, reading=trial).items():
            image, x, y = compose_screen(screen, runtime / "images")
            source = "; ".join(f"{i.name} at ({i.x}, {i.y})" for i in screen.images)
            shown.append(
                (
                    participant,
                    trial,
                    paragraph,
                    part,
                    _png_bytes(image),
                    x,
                    y,
                    *image.size,
                    f"{participant}/graphics/VC_{index}.vcl",
                    screen.onset_ms,
                    source,
                )
            )
    table = pd.DataFrame(
        shown,
        columns=[
            "participant_id",
            "unique_trial_id",
            "unique_paragraph_id",
            "part",
            "png",
            "image_x",
            "image_y",
            "width",
            "height",
            "draw_list",
            "onset_ms",
            "drawn_images",
        ],
    )
    shared = table.groupby(["unique_paragraph_id", "part"])[
        ["png", "image_x", "image_y"]
    ].transform(lambda column: column.nunique() == 1)
    one_file = shared.all(axis=1)
    owner = table["unique_paragraph_id"].where(one_file, table["unique_trial_id"])
    table["image_path"] = "images/" + owner + "__" + table["part"].str.lower() + ".png"
    files = dict(zip(table["image_path"], table["png"]))
    columns = ["participant_id", "unique_trial_id", "part", "image_path"]
    manifest = table[
        [*columns, "image_x", "image_y", "width", "height"]
        + ["draw_list", "onset_ms", "drawn_images"]
    ]
    files["images/manifest.csv"] = manifest.to_csv(index=False).encode()
    return table[[*columns, "image_x", "image_y"]], files


def with_stimulus_images(frame: pd.DataFrame, images: pd.DataFrame) -> pd.DataFrame:
    """``frame`` with each row's screen's ``image_path`` / ``image_x`` / ``image_y``."""
    keys = ["participant_id", "unique_trial_id", "part"]
    placed = frame.drop(
        columns=["image_path", "image_x", "image_y"], errors="ignore"
    ).merge(images, on=keys, how="left", validate="many_to_one")
    if placed["image_path"].isna().any():
        missing = placed.loc[placed["image_path"].isna(), keys].drop_duplicates()
        raise ValueError(f"No stimulus image for {missing.head(3).to_numpy().tolist()}")
    placed.index = frame.index
    return placed


#: Tables shipped as Parquet alone. The app reads the Parquet, and a CSV copy of
#: every 1 kHz sample would triple the wheel's size.
PARQUET_ONLY_TABLES = frozenset({"raw_gaze"})


def write_tables(
    output_dir: Path,
    images: Mapping[str, bytes] | None = None,
    **tables: pd.DataFrame,
) -> None:
    """Finish every table and image before replacing the packaged data.

    Each table ships as CSV and Parquet, except ``PARQUET_ONLY_TABLES``, whose
    CSV an older build may have left is removed. ``images`` maps each file's
    path under ``output_dir`` (``images/<name>``) to its bytes; given, they
    replace every file in ``images/``, so a screen the demo no longer has leaves
    no file behind.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir) as temp:
        staged = Path(temp)
        for name, frame in tables.items():
            if name not in PARQUET_ONLY_TABLES:
                frame.to_csv(staged / f"{name}.csv", index=False)
            frame.to_parquet(staged / f"{name}.parquet", index=False)
        for relative, data in (images or {}).items():
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if images is not None:
            image_dir = output_dir / "images"
            image_dir.mkdir(exist_ok=True)
            for stale in image_dir.iterdir():
                if stale.is_file() and not stale.name.startswith("."):
                    stale.unlink()
            for image in (staged / "images").iterdir():
                image.replace(image_dir / image.name)
        for artifact in staged.iterdir():
            if artifact.is_file():
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


def _trial_samples(asc: BinaryIO, trial, periods: pd.DataFrame) -> pd.DataFrame:
    """Read one matching ASC recording block's samples in ``periods``.

    ``periods`` holds the trial's screens' interest periods (``IP_START_TIME``
    inclusive, ``IP_END_TIME`` exclusive, tracker ms) and the screen columns to
    stamp on their samples. Times go on the fixation report's clock: tracker
    time less ``TRIAL_START_TIME``."""
    periods = periods.sort_values("IP_START_TIME", kind="stable")
    starts = periods["IP_START_TIME"].to_numpy()
    stops = periods["IP_END_TIME"].to_numpy()
    if (
        (starts < trial.TRIAL_START_TIME).any()
        or (starts >= stops).any()
        or (starts[1:] < stops[:-1]).any()
    ):
        raise ValueError(f"Invalid interest periods for {trial.unique_trial_id}")
    eye = trial.EYE_TRACKED.upper().encode("ascii")
    first, last = int(starts.min()), int(stops.max())
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
            if int(line.split()[1]) < last or not rows:
                raise ValueError(f"Incomplete recording for {trial.unique_trial_id}")
            break
        elif line.startswith(b"START"):
            raise ValueError(
                f"Missing END in the recording for {trial.unique_trial_id}"
            )
        elif line[:1].isdigit():
            fields = line.split()
            time = int(fields[0])
            if first <= time < last:
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
                rows.append((time, x, y, pupil))
    else:
        raise ValueError(f"Missing END in the recording for {trial.unique_trial_id}")
    samples = pd.DataFrame(rows, columns=["time", "x", "y", pupil_field])
    # The screen whose period holds each sample; samples between periods
    # (fixation targets, blank screens) belong to no screen and are dropped.
    period = starts.searchsorted(samples["time"].to_numpy(), side="right") - 1
    inside = samples["time"].to_numpy() < stops[period]
    samples, period = samples.loc[inside], period[inside]
    screen_columns = [c for c in ("part", "screen_index") if c in periods]
    frame = pd.DataFrame(
        {
            "participant_id": trial.participant_id,
            "unique_trial_id": trial.unique_trial_id,
            "unique_paragraph_id": trial.unique_paragraph_id,
            **{c: periods[c].to_numpy()[period] for c in screen_columns},
            "x": samples["x"].to_numpy(),
            "y": samples["y"].to_numpy(),
            "timestamp_ms": samples["time"].to_numpy() - trial.TRIAL_START_TIME,
            pupil_field: samples[pupil_field].to_numpy(),
            "eye": trial.EYE_TRACKED,
        }
    )
    return frame


def extract_raw_gaze(fixations: pd.DataFrame, asc_dir: Path) -> pd.DataFrame:
    """Every ASC sample in the bundled readings' interest periods.

    The report's TRIAL_START_TIME identifies the ASC START block exactly. Each
    screen (``part``) of a reading has its own interest period, IP_START_TIME
    inclusive and IP_END_TIME exclusive, in tracker ms; its samples carry the
    screen's ``part`` and ``screen_index``.
    """
    trial_columns = [
        "participant_id",
        "unique_trial_id",
        "unique_paragraph_id",
        "TRIAL_START_TIME",
        "EYE_TRACKED",
    ]
    screen_columns = [c for c in ("part", "screen_index") if c in fixations]
    periods = fixations[
        [*trial_columns, *screen_columns, "IP_START_TIME", "IP_END_TIME"]
    ].drop_duplicates()
    trials = periods[trial_columns].drop_duplicates()
    screen_keys = ["participant_id", "unique_trial_id", *screen_columns[:1]]
    if (
        trials.empty
        or periods.drop(columns="screen_index", errors="ignore").isna().any().any()
        or periods.duplicated(screen_keys).any()
        or any(
            trials.duplicated(["participant_id", key]).any()
            for key in ("unique_trial_id", "TRIAL_START_TIME")
        )
    ):
        raise ValueError(
            "Each demo reading needs one distinct recording block and tracked "
            "eye, and each of its screens one interest period."
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
        mine = periods[periods["participant_id"].eq(participant)]
        pending = {r.TRIAL_START_TIME: r for r in readings.itertuples(index=False)}
        with path.open("rb") as asc:
            for line in asc:
                if line.startswith(b"START"):
                    trial = pending.pop(int(line.split()[1]), None)
                    if trial is not None:
                        screens = mine[
                            mine["unique_trial_id"].eq(trial.unique_trial_id)
                        ]
                        samples.append(_trial_samples(asc, trial, screens))
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
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory of the full release's per-part reports, "
        "ia_<Part>.csv and fixations_<Part>.csv (or .csv.zip).",
    )
    parser.add_argument(
        "--asc-dir",
        type=Path,
        help="Directory of OneStop .asc or _clean.asc files (default: SOURCE_DIR/asc).",
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        action="append",
        help="A folder holding the Experiment Builder project the demo readers "
        "ran (its runtime/images and runtime/dataviewer/<reader>/graphics); "
        "repeat for several (default: SOURCE_DIR/experiment).",
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
        load_parts(args.source_dir, "ia", IA_KEEP_COLUMNS, participants)
    )
    fix_full = add_unique_ids(
        load_parts(args.source_dir, "fixations", FIXATION_KEEP_COLUMNS, participants)
    )

    ia_sample = with_span_fields(filter_demo(ia_full, participants, articles))
    fix_sample = filter_demo(fix_full, participants, articles)
    check_fixations_cover_words(ia_sample, fix_sample)
    ia_sample, fix_sample = _onestop_parts_as_screens(ia_sample, fix_sample)

    if set(fix_sample["participant_id"]) != set(participants):
        raise ValueError("The OneStop reports are missing a selected demo participant.")
    images, image_files = stimulus_images(
        fix_sample, args.experiment_dir or [args.source_dir / "experiment"]
    )
    raw_gaze = extract_raw_gaze(fix_sample, asc_dir)
    write_tables(
        args.output_dir,
        images=image_files,
        ia=with_stimulus_images(ia_sample, images),
        fixations=with_stimulus_images(fix_sample, images),
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
        f"  screens: {len(images):,} ({len(image_files) - 1:,} images)\n"
        f"  gaze samples: {len(raw_gaze):,}\n"
        f"  output: {args.output_dir}"
    )


if __name__ == "__main__":
    main()
