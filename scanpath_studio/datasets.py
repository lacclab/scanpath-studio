"""Loaders for public eye-tracking-while-reading corpora.

Currently: PoTeC (Potsdam Textbook Corpus, Jakobi et al. 2024,
https://github.com/DiLi-Lab/PoTeC) — a German corpus of 75 readers × 12
textbook texts — and MultiplEYE (https://multipleye.eu), a large multilingual
corpus whose per-session, filename-keyed shape :func:`load_multipleye` adapts
to the generic pipeline. Between them they exercise the two dataset shapes the
generic pipeline supports:

* **multi-file** — fixations ship as one TSV per reader × text
  (``reader0_b0_scanpath.tsv`` … 900 files), concatenated on load;
* **stimulus-level AoIs** — word bounding boxes ship once per *text* with no
  participant column, and are broadcast across readers
  (``data.broadcast_stimulus_words``).

PoTeC fixations carry no pixel coordinates — only the fixated character's
index. The loader reconstructs (x, y) as the center of that character's
bounding box from the per-text ``.ias`` AOI files, giving within-word landing
positions. (For AOI-sequence datasets *without* character AOIs, the generic
fallback places fixations at word-box centers instead.)

Typical use::

    from scanpath_studio.datasets import load_potec

    words, fixations = load_potec("data/PoTeC", download=True)
    fig = scanpath_studio.plot_scanpath(words, fixations, participant="0", trial="b0")
"""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd

# PoTeC text p3 contains the German word "null" — pandas' default NA list
# would turn it into NaN (see the PoTeC README), so every PoTeC table is read
# with keep_default_na=False and this explicit list.
_POTEC_NA_VALUES = [
    "#N/A",
    "#N/A N/A",
    "#NA",
    "-1.#IND",
    "-1.#QNAN",
    "-NaN",
    "-nan",
    "1.#IND",
    "1.#QNAN",
    "<NA>",
    "N/A",
    "NA",
    "NaN",
    "None",
    "n/a",
    "nan",
    "",
]

_POTEC_TEXTS = [f"{domain}{i}" for domain in ("b", "p") for i in range(6)]

# OSF storage ids from the PoTeC repo's download_data_files.py.
_POTEC_OSF_URL = "https://osf.io/download/{resource}"
_POTEC_OSF_RESOURCES = {
    "scanpaths": "thgv2",
    "fixations": "53zwb",
    "reading_measures": "g5jds",
}
_POTEC_RAW_URL = "https://raw.githubusercontent.com/DiLi-Lab/PoTeC/main/{path}"


def _read_potec_tsv(path) -> pd.DataFrame:
    return pd.read_csv(
        path, sep="\t", keep_default_na=False, na_values=_POTEC_NA_VALUES
    )


def download_potec(root, *, fixation_source: str = "scanpaths") -> Path:
    """Download the PoTeC files :func:`load_potec` needs into ``root``.

    Fetches the per-trial eye-tracking archive (~45 MB zip) from PoTeC's OSF
    repository and the 24 per-text AOI files (word boxes + character boxes)
    from the PoTeC GitHub repo. Skips anything already present, so it's safe
    to call repeatedly (and it's a no-op on a full clone of the PoTeC repo
    where ``download_data_files.py`` has been run).

    ``fixation_source`` is ``"scanpaths"`` (default; temporally ordered
    fixations with word indices) or ``"fixations"``.
    """
    if fixation_source not in _POTEC_OSF_RESOURCES:
        raise ValueError(
            f"fixation_source must be one of {sorted(_POTEC_OSF_RESOURCES)}, "
            f"got {fixation_source!r}"
        )
    root = Path(root)

    eyetracking_dir = root / "eyetracking_data" / fixation_source
    if not eyetracking_dir.is_dir():
        url = _POTEC_OSF_URL.format(resource=_POTEC_OSF_RESOURCES[fixation_source])
        print(f"Downloading PoTeC {fixation_source} from {url} …")
        with urllib.request.urlopen(url) as response:
            payload = response.read()
        (root / "eyetracking_data").mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = [
                m
                for m in archive.namelist()
                # The OSF zips carry macOS resource-fork cruft; keep only the
                # real per-trial TSVs.
                if m.startswith(f"{fixation_source}/") and m.endswith(".tsv")
            ]
            archive.extractall(root / "eyetracking_data", members=members)

    for text_id in _POTEC_TEXTS:
        for rel in (
            f"stimuli/word_aoi_texts/word_aoi_{text_id}.tsv",
            f"stimuli/aoi_texts/{text_id}.ias",
        ):
            dest = root / rel
            if dest.is_file():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = _POTEC_RAW_URL.format(path=rel)
            print(f"Downloading {url} …")
            with urllib.request.urlopen(url) as response:
                dest.write_bytes(response.read())
    return root


def _potec_words(root: Path, texts: Iterable[str]) -> pd.DataFrame:
    """Stimulus-level word table: one row per word per text, with boxes.

    PoTeC keys the text id in the AOI *filename* only; it becomes a regular
    ``text_id`` column here. Line indices come from the character-level
    ``.ias`` files (the word AOI files don't carry them) via the lines' y
    positions."""
    frames = []
    for text_id in texts:
        path = root / "stimuli" / "word_aoi_texts" / f"word_aoi_{text_id}.tsv"
        if not path.is_file():
            raise FileNotFoundError(
                f"PoTeC word AOI file not found: {path} — pass download=True "
                "or run PoTeC's download_data_files.py in a repo clone."
            )
        words = _read_potec_tsv(path)
        words["text_id"] = text_id

        ias = _read_potec_ias(root, text_id)
        # Character boxes on the same text line share start_y, so the char
        # AOIs give an exact y → line lookup for the word boxes.
        y_to_line = ias.drop_duplicates("start_y").set_index("start_y")["line"]
        words["line"] = words["start_y"].map(y_to_line)
        frames.append(words)
    return pd.concat(frames, ignore_index=True)


def _read_potec_ias(root: Path, text_id: str) -> pd.DataFrame:
    path = root / "stimuli" / "aoi_texts" / f"{text_id}.ias"
    if not path.is_file():
        raise FileNotFoundError(
            f"PoTeC character AOI file not found: {path} — pass download=True "
            "or run PoTeC's download_data_files.py in a repo clone."
        )
    return _read_potec_tsv(path)


def _potec_fixations(
    root: Path,
    texts: Iterable[str],
    readers: Optional[Iterable] = None,
) -> pd.DataFrame:
    """Concatenated per-trial fixation files with reconstructed coordinates.

    Prefers ``eyetracking_data/scanpaths/`` (fixations in temporal order, with
    word indices) and falls back to ``eyetracking_data/fixations/``. Each
    fixation's (x, y) is the center of the fixated character's box from the
    per-text ``.ias`` file — PoTeC discards the original screen coordinates."""
    base = root / "eyetracking_data"
    source = next((s for s in ("scanpaths", "fixations") if (base / s).is_dir()), None)
    if source is None:
        raise FileNotFoundError(
            f"No PoTeC fixation data under {base} — expected a 'scanpaths' or "
            "'fixations' folder. Pass download=True, or run PoTeC's "
            "download_data_files.py in a repo clone."
        )
    suffix = "scanpath" if source == "scanpaths" else "fixations"

    reader_set = None if readers is None else {str(r) for r in readers}
    frames = []
    for text_id in texts:
        char_boxes = _read_potec_ias(root, text_id)
        char_x = (char_boxes["start_x"] + char_boxes["end_x"]) / 2.0
        char_y = (char_boxes["start_y"] + char_boxes["end_y"]) / 2.0
        centers = pd.DataFrame(
            {"aoi": char_boxes["aoi"], "x": char_x, "y": char_y}
        ).drop_duplicates("aoi")

        for path in sorted((base / source).glob(f"reader*_{text_id}_{suffix}.tsv")):
            reader_id = path.stem.removeprefix("reader").split("_")[0]
            if reader_set is not None and reader_id not in reader_set:
                continue
            fixations = _read_potec_tsv(path)
            fixations = fixations.merge(centers, on="aoi", how="left")
            frames.append(fixations)
    if not frames:
        raise FileNotFoundError(
            f"No PoTeC fixation files matched the requested readers/texts "
            f"under {base / source}."
        )
    return pd.concat(frames, ignore_index=True, sort=False)


# Column mappings from the raw PoTeC frames to the canonical schema. Explicit
# (rather than relying on auto-detection) so the loader stays stable even if
# PoTeC adds columns. No participant on words: the word boxes are
# stimulus-level and get broadcast across readers. Shared by load_potec and
# the app's PoTeC data source (which auto-detects, but these document intent).
POTEC_WORD_SCHEMA = dict(
    participant=None,
    trial="text_id",
    word_id="aoi",
    text="word",
    line="line",
    left="start_x",
    right="end_x",
    top="start_y",
    bottom="end_y",
)
POTEC_FIX_SCHEMA = dict(
    participant="reader_id",
    trial="text_id",
    duration="fixation_duration",
    x="x",
    y="y",
    fixation_id="fixation_index",
    word_id="word_index_in_text",
)

# PoTeC presentation monitor (DELL P2210, 60 Hz). Pass as ``canvas_size`` to
# plot_scanpath for true-to-scale rendering.
POTEC_MONITOR = (1680, 1050)


def potec_raw_frames(
    root,
    *,
    readers: Optional[Iterable] = None,
    texts: Optional[Iterable[str]] = None,
    download: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) PoTeC ``(words, fixations)`` frames.

    Same inputs as :func:`load_potec`, but returns the frames *before* schema
    normalization — for callers that run their own auto-detection / column
    mapping (e.g. the Streamlit app's PoTeC data source). Word boxes are
    stimulus-level (one row per word per text, ``text_id`` column, no
    participant); fixations carry reconstructed ``x``/``y`` from the fixated
    character's box center. Use :func:`load_potec` for the normalized,
    ready-to-plot frames.
    """
    root = Path(root)
    if download:
        download_potec(root)
    texts = list(texts) if texts is not None else list(_POTEC_TEXTS)
    unknown = sorted(set(texts) - set(_POTEC_TEXTS))
    if unknown:
        raise ValueError(f"Unknown PoTeC text ids: {unknown} (valid: {_POTEC_TEXTS})")
    return _potec_words(root, texts), _potec_fixations(root, texts, readers)


def load_potec(
    root,
    *,
    readers: Optional[Iterable] = None,
    texts: Optional[Iterable[str]] = None,
    download: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load PoTeC as normalized ``(words, fixations)`` frames, ready to plot.

    ``root`` is a clone of the PoTeC repo (with the eye-tracking data
    downloaded) or any folder; with ``download=True`` the needed files are
    fetched into it on first use (~45 MB). Narrow the load with ``readers``
    (e.g. ``[0, 1]``) and/or ``texts`` (e.g. ``["b0", "p3"]``) — the full
    corpus is 75 readers × 12 texts = 900 trials.

    Participants are PoTeC reader ids (as strings), trials are text ids
    (``b0``–``b5`` biology, ``p0``–``p5`` physics)::

        words, fixations = load_potec("data/PoTeC", readers=[0], texts=["b0"])
        fig = scanpath_studio.plot_scanpath(words, fixations)

    The PoTeC monitor was 1680×1050 (DELL P2210, 60 Hz); pass that as
    ``canvas_size`` to :func:`scanpath_studio.plot_scanpath` for true-to-scale
    rendering.
    """
    words_raw, fixations_raw = potec_raw_frames(
        root, readers=readers, texts=texts, download=download
    )

    from . import api

    return api.load_scanpath_data(
        words=words_raw,
        fixations=fixations_raw,
        word_schema=dict(POTEC_WORD_SCHEMA),
        fix_schema=dict(
            POTEC_FIX_SCHEMA,
            word_id=(
                "word_index_in_text"
                if "word_index_in_text" in fixations_raw.columns
                else None
            ),
        ),
    )


# ---------------------------------------------------------------------------
# MultiplEYE — multilingual eye-tracking-while-reading corpus
# (https://multipleye.eu). Tested against the read-only ZH/Chinese Zurich
# sample under ``data/MultiplEYE_ZH_CH_Zurich_1_2025``.
# ---------------------------------------------------------------------------
#
# Why a dedicated loader (the generic Upload flow can't do this on its own):
#
# * **Identity is in the path, not the columns.** Per-session folders
#   ``{pid}_ZH_CH_1_ET{1|2}/`` (under ``fixations/`` and ``scanpaths/``) hold
#   one comma-CSV per trial; none of the files carry a participant / trial /
#   stimulus column. We parse all four from the folder + file name.
# * **ET1 and ET2 read disjoint stimuli**, so a *reader* is the whole session
#   string — ``participant_id = "001_ZH_CH_1_ET1"`` — not the bare pid.
# * **One stimulus spans several screens** ``page_1..page_N`` that all reuse the
#   *same* on-screen coordinates. Combining them would stack every page's word
#   boxes and fixations at the same pixels, so each (stimulus, page) is its own
#   trial (``trial_id = "<stimulus>__<page>"``). ``text_id`` stays the stimulus
#   so stimulus-level merges (comprehension Q&A, images, grouping) still work.
#   Non-reading screens (``question_*`` / ``familiarity_rating_screen_*`` /
#   ``subject_difficulty_screen``) are dropped.
# * **Word boxes ship once per stimulus** (no participant) as *character*-level
#   AOI files ``stimuli_*/aoi_stimuli_*/<stimulus>_aoi.csv``. We aggregate chars
#   to one bounding box per (page, word_idx). ``word_idx`` is unique within a
#   page — hence within a per-page trial — so it is the word id directly.
#
# Fixation source: ``scanpaths/`` (preferred — already page/word-tagged and
# filtered to reading pages) or ``fixations/`` (raw onset/duration/x/y/page,
# no word linkage).

MULTIPLEYE_FIXATION_SOURCES = ("scanpaths", "fixations")

# Presentation monitor (px) for the ZH-CH-Zurich sample, from its lab config
# (``Monitor_resolution_in_px`` / ``RESOLUTION``). Pass as ``canvas_size`` to
# :func:`scanpath_studio.plot_scanpath` for true-to-scale rendering.
MULTIPLEYE_MONITOR = (1920, 1080)

# Separator between the stimulus and the page in a per-page ``trial_id``. Two
# underscores keep it visually distinct from the single underscores already in
# stimulus names (``Lit_Alchemist_4``) while staying filename-safe for export.
_MULTIPLEYE_PAGE_SEP = "__"

# Per-trial file name: ``<session>_[PRACTICE_]trial_<n>_<stimulus>_<kind>``
# e.g. ``001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4_fixation`` or
#      ``001_ZH_CH_1_ET1_PRACTICE_trial_1_Enc_WikiMoon_13_scanpath``.
_MULTIPLEYE_TRIAL_RE = re.compile(
    r"^(?P<session>\d+_[A-Za-z]{2}_[A-Za-z]{2}_\d+_ET\d+)_"
    r"(?:(?P<practice>PRACTICE)_)?trial_(?P<trial_num>\d+)_"
    r"(?P<stimulus>.+)_(?P<kind>fixation|scanpath)$"
)


def _multipleye_parse_filename(stem: str) -> Optional[dict]:
    """Parse a per-trial file stem into its identity parts, or ``None``."""
    match = _MULTIPLEYE_TRIAL_RE.match(stem)
    return match.groupdict() if match else None


def _multipleye_aoi_dir(root: Path) -> Path:
    """Locate the per-stimulus character-AOI directory under ``root``."""
    for aoi_dir in sorted(root.glob("stimuli_*/aoi_stimuli_*")):
        if aoi_dir.is_dir():
            return aoi_dir
    raise FileNotFoundError(
        f"No MultiplEYE AOI directory found under {root} — expected "
        "stimuli_*/aoi_stimuli_*/<stimulus>_aoi.csv files."
    )


def _multipleye_word_boxes(aoi_dir: Path, stimuli: Iterable[str]) -> pd.DataFrame:
    """Stimulus-level word boxes: chars aggregated to one box per (page, word).

    One row per (stimulus, page, word_idx) with the bounding box of that word's
    characters (``top_left_x/y`` + ``width/height``). No participant column —
    the boxes are stimulus-level and get broadcast across the readers who read
    each (stimulus, page) trial (``data.broadcast_stimulus_words``)."""
    frames = []
    for stimulus in sorted(set(stimuli)):
        path = aoi_dir / f"{stimulus.lower()}_aoi.csv"
        if not path.is_file():
            raise FileNotFoundError(
                f"MultiplEYE AOI file not found for stimulus {stimulus!r}: {path}"
            )
        chars = pd.read_csv(path)
        chars = chars[chars["page"].astype(str).str.startswith("page_")].copy()
        chars["_right"] = chars["top_left_x"] + chars["width"]
        chars["_bottom"] = chars["top_left_y"] + chars["height"]
        boxes = (
            chars.groupby(["page", "word_idx"], sort=False)
            .agg(
                left=("top_left_x", "min"),
                top=("top_left_y", "min"),
                right=("_right", "max"),
                bottom=("_bottom", "max"),
                line_idx=("line_idx", "min"),
                word=("word", "first"),
            )
            .reset_index()
        )
        boxes["stimulus"] = stimulus
        # `text_id` (= stimulus) so both the explicit schema and the app's
        # auto-detect path key stimulus-level grouping on the stimulus, not the
        # per-page trial id.
        boxes["text_id"] = stimulus
        boxes["genre"] = stimulus.split("_")[0]
        boxes["trial_id"] = stimulus + _MULTIPLEYE_PAGE_SEP + boxes["page"].astype(str)
        frames.append(boxes)
    return pd.concat(frames, ignore_index=True)


def _multipleye_fixations(
    root: Path,
    source: str,
    sessions: Optional[Iterable[str]],
    stimuli: Optional[Iterable[str]],
) -> pd.DataFrame:
    """Concatenated per-trial fixations, tagged with parsed identity columns.

    Reading-page rows only (``page_*``); identity (participant/session/stimulus/
    page → per-page ``trial_id``) comes from the folder + file name. Prefers the
    word-tagged ``scanpaths/`` files; ``fixations/`` works too (no word_idx)."""
    base = root / source
    suffix = "scanpath" if source == "scanpaths" else "fixation"
    session_filter = None if sessions is None else {str(s) for s in sessions}
    stim_filter = None if stimuli is None else {str(s) for s in stimuli}

    frames = []
    for session_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if session_filter is not None and session_dir.name not in session_filter:
            continue
        for path in sorted(session_dir.glob(f"*_{suffix}.csv")):
            info = _multipleye_parse_filename(path.stem)
            if info is None:
                continue
            stimulus = info["stimulus"]
            if stim_filter is not None and stimulus not in stim_filter:
                continue
            df = pd.read_csv(path)
            df = df[df["page"].astype(str).str.startswith("page_")]
            if "name" in df.columns:  # scanpaths tag each row; keep fixations only
                df = df[df["name"] == "fixation"]
            if df.empty:
                continue
            df = df.copy()
            df["participant_id"] = info["session"]
            df["participant"] = info["session"].split("_", 1)[0]  # bare pid
            df["session"] = info["session"].rsplit("_", 1)[-1]  # ET1 / ET2
            df["stimulus"] = stimulus
            df["text_id"] = stimulus  # stimulus-level grouping key (see word boxes)
            df["genre"] = stimulus.split("_")[0]
            df["is_practice"] = bool(info["practice"])
            df["trial_num"] = int(info["trial_num"])
            df["trial_id"] = stimulus + _MULTIPLEYE_PAGE_SEP + df["page"].astype(str)
            frames.append(df)
    if not frames:
        raise FileNotFoundError(
            f"No MultiplEYE {source} files matched under {base} "
            f"(sessions={sessions}, stimuli={stimuli})."
        )
    return pd.concat(frames, ignore_index=True, sort=False)


# Explicit schemas from the raw MultiplEYE frames to the canonical schema (no
# participant on words — stimulus-level boxes broadcast across readers).
MULTIPLEYE_WORD_SCHEMA = dict(
    participant=None,
    trial="trial_id",
    text_id="text_id",
    word_id="word_idx",
    text="word",
    line="line_idx",
    left="left",
    right="right",
    top="top",
    bottom="bottom",
)
MULTIPLEYE_FIX_SCHEMA = dict(
    participant="participant_id",
    trial="trial_id",
    text_id="text_id",
    duration="duration",
    timestamp="onset",
    x="location_x",
    y="location_y",
    word_id="word_idx",
)


def multipleye_inventory(
    root, *, fixation_source: str = "scanpaths"
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """(sessions, stimuli) available under a MultiplEYE ``root``.

    Cheap directory scan (filenames only, no CSV reads) for the app's
    session/stimulus pickers. Returns sorted tuples; empties if ``root`` has no
    recognizable per-trial files."""
    root = Path(root)
    base = root / fixation_source
    if not base.is_dir():
        base = root / next(
            (s for s in MULTIPLEYE_FIXATION_SOURCES if (root / s).is_dir()), ""
        )
    sessions: set = set()
    stimuli: set = set()
    if base.is_dir():
        for session_dir in (p for p in base.iterdir() if p.is_dir()):
            for path in session_dir.glob("*.csv"):
                info = _multipleye_parse_filename(path.stem)
                if info is None:
                    continue
                sessions.add(info["session"])
                stimuli.add(info["stimulus"])
    return tuple(sorted(sessions)), tuple(sorted(stimuli))


def multipleye_raw_frames(
    root,
    *,
    sessions: Optional[Iterable[str]] = None,
    stimuli: Optional[Iterable[str]] = None,
    fixation_source: str = "scanpaths",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) MultiplEYE ``(words, fixations)`` frames.

    Same inputs as :func:`load_multipleye`, but returns the frames *before*
    schema normalization — for callers that run their own auto-detection /
    column mapping (e.g. the Streamlit app's MultiplEYE data source). Word boxes
    are stimulus-level (one row per (stimulus, page, word), ``stimulus`` column,
    no participant); fixations carry parsed ``participant_id`` (the session),
    per-page ``trial_id``, and pixel ``location_x/y``. Use
    :func:`load_multipleye` for the normalized, ready-to-plot frames.
    """
    root = Path(root)
    if fixation_source not in MULTIPLEYE_FIXATION_SOURCES:
        raise ValueError(
            f"fixation_source must be one of {list(MULTIPLEYE_FIXATION_SOURCES)}, "
            f"got {fixation_source!r}"
        )
    if not (root / fixation_source).is_dir():
        # Fall back to whichever per-trial source folder exists.
        alt = next(
            (s for s in MULTIPLEYE_FIXATION_SOURCES if (root / s).is_dir()), None
        )
        if alt is None:
            raise FileNotFoundError(
                f"No MultiplEYE fixation data under {root} — expected a "
                f"'scanpaths' or 'fixations' folder of per-session subfolders."
            )
        fixation_source = alt

    fixations = _multipleye_fixations(root, fixation_source, sessions, stimuli)
    words = _multipleye_word_boxes(
        _multipleye_aoi_dir(root), fixations["stimulus"].unique()
    )
    return words, fixations


def load_multipleye(
    root,
    *,
    sessions: Optional[Iterable[str]] = None,
    stimuli: Optional[Iterable[str]] = None,
    fixation_source: str = "scanpaths",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load MultiplEYE as normalized ``(words, fixations)`` frames, ready to plot.

    ``root`` is a MultiplEYE session set (e.g.
    ``data/MultiplEYE_ZH_CH_Zurich_1_2025``). Narrow the load with ``sessions``
    (full session ids, e.g. ``["001_ZH_CH_1_ET1"]``) and/or ``stimuli`` (e.g.
    ``["Lit_Alchemist_4"]``).

    Participants are session ids (ET1 and ET2 read disjoint stimuli, so each is
    a distinct reader); a trial is one stimulus *page*
    (``trial_id = "Lit_Alchemist_4__page_1"``), since pages reuse the same
    screen coordinates. ``text_id`` is the stimulus for stimulus-level merges::

        words, fixations = load_multipleye(
            "data/MultiplEYE_ZH_CH_Zurich_1_2025", stimuli=["Lit_Alchemist_4"]
        )
        fig = scanpath_studio.plot_scanpath(
            words, fixations, canvas_size=MULTIPLEYE_MONITOR
        )

    ``fixation_source`` is ``"scanpaths"`` (default; fixations pre-tagged with
    page + word index) or ``"fixations"`` (raw, no word linkage).
    """
    words_raw, fixations_raw = multipleye_raw_frames(
        root, sessions=sessions, stimuli=stimuli, fixation_source=fixation_source
    )

    from . import api

    return api.load_scanpath_data(
        words=words_raw,
        fixations=fixations_raw,
        word_schema=dict(MULTIPLEYE_WORD_SCHEMA),
        fix_schema=dict(
            MULTIPLEYE_FIX_SCHEMA,
            word_id="word_idx" if "word_idx" in fixations_raw.columns else None,
        ),
    )
