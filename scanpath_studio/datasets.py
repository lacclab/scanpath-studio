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
import json
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
            # Write to a temp file and atomically rename into place, so an
            # interrupted fetch never leaves a truncated AOI file that
            # `dest.is_file()` / `potec_present` would then treat as complete —
            # mirroring download_onestop.
            tmp = dest.with_name(dest.name + ".part")
            with urllib.request.urlopen(url) as response:
                tmp.write_bytes(response.read())
            tmp.replace(dest)
    return root


def potec_present(root) -> bool:
    """True when ``root`` already holds the full PoTeC corpus a load needs.

    The app loads *every* text, so this requires the per-text word + character
    AOI files for **all** texts (exactly what :func:`download_potec` fetches),
    plus a populated eye-tracking folder. A lenient "any AOI file" check would
    pass a partial tree and then crash mid-load (`_potec_words` raises on the
    first missing text) with no way to recover; requiring all of them instead
    lets the app offer the Download button, which self-heals the gap. Cheap
    (path stats only), so the status shows without reading any CSV."""
    root = Path(root)
    base = root / "eyetracking_data"
    has_fixations = any(
        (base / s).is_dir() and any((base / s).glob("*.tsv"))
        for s in ("scanpaths", "fixations")
    )
    word_dir = root / "stimuli" / "word_aoi_texts"
    char_dir = root / "stimuli" / "aoi_texts"
    has_all_aoi = all(
        (word_dir / f"word_aoi_{text_id}.tsv").is_file()
        and (char_dir / f"{text_id}.ias").is_file()
        for text_id in _POTEC_TEXTS
    )
    return has_fixations and has_all_aoi


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
# OneStop Eye Movements — 360-participant English corpus (Berzak et al. 2025,
# https://github.com/lacclab/OneStop-Eye-Movements). Distributed on OSF as
# paragraph-level interest-area (word) + fixation reports, split by reading
# regime. The reports share the bundled demo's schema (the demo is a 3-pid
# subset of OneStop), so the generic auto-detect → normalize pipeline handles
# them with no dataset-specific column mapping — this loader only fetches and
# reads the two CSV.zips. Distinct from the env-var "OneStop server bundle"
# source (``data.load_onestop_server_bundle``), which serves a local lacclab
# export and its per-pid shards for review-app deep links.
# ---------------------------------------------------------------------------

# OSF file ids from the OneStop repo's download_data_files.py, per reading
# regime: the paragraph-level interest-area and fixation reports (same columns
# as the bundled OneStop demo). Keep the keys ("ia"/"fixations") aligned with
# the report filename prefixes.
_ONESTOP_OSF_URL = "https://osf.io/download/{resource}"
_ONESTOP_REGIMES = {
    "ordinary": dict(ia="xkgfz", fixations="ne4az"),
    "information_seeking": dict(ia="yxzte", fixations="bznfk"),
    "repeated": dict(ia="dwfk4", fixations="83ctd"),
    "information_seeking_repeated": dict(ia="ygjup", fixations="paqn8"),
}


def _onestop_report_path(root: Path, kind: str, regime: str) -> Path:
    """Local path of a OneStop report CSV.zip (matches the OSF filenames)."""
    return root / f"{kind}_Paragraph_{regime}.csv.zip"


def onestop_present(root, *, regime: str = "ordinary") -> bool:
    """True when ``root`` already holds the two OneStop reports for ``regime``.

    Lets the app show a *found vs. download* status before any (large) read."""
    root = Path(root)
    return (
        _onestop_report_path(root, "ia", regime).is_file()
        and _onestop_report_path(root, "fixations", regime).is_file()
    )


def download_onestop(root, *, regime: str = "ordinary") -> Path:
    """Download a OneStop regime's paragraph IA + fixation reports into ``root``.

    Fetches the two CSV.zip reports for ``regime`` from OneStop's OSF release
    into ``root``, skipping any already present, so it's safe to call
    repeatedly. The reports are large (tens to hundreds of MB); caching them on
    disk means only the first load pays the download.

    ``regime`` is one of ``ordinary``, ``information_seeking``, ``repeated``,
    ``information_seeking_repeated``.
    """
    if regime not in _ONESTOP_REGIMES:
        raise ValueError(
            f"regime must be one of {sorted(_ONESTOP_REGIMES)}, got {regime!r}"
        )
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for kind, resource in _ONESTOP_REGIMES[regime].items():
        dest = _onestop_report_path(root, kind, regime)
        if dest.is_file():
            continue
        url = _ONESTOP_OSF_URL.format(resource=resource)
        print(f"Downloading OneStop {regime} {kind} report from {url} …")
        # Write to a temp file and atomically rename into place, so an
        # interrupted write (killed process / full disk) never leaves a
        # truncated .csv.zip that `dest.is_file()` would then skip forever —
        # forcing a manual delete. The reports are large, so that window is real.
        tmp = dest.with_name(dest.name + ".part")
        with urllib.request.urlopen(url) as response:
            tmp.write_bytes(response.read())
        tmp.replace(dest)
    return root


def onestop_raw_frames(
    root,
    *,
    regime: str = "ordinary",
    download: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) OneStop ``(words, fixations)`` frames for a regime.

    Reads the paragraph-level interest-area + fixation reports for ``regime``
    from ``root`` (fetching them from OSF first when ``download=True``). The
    reports already match the bundled demo's schema, so the returned frames go
    through the same auto-detect → normalize path as an upload — no
    OneStop-specific column mapping is needed here.
    """
    if regime not in _ONESTOP_REGIMES:
        raise ValueError(
            f"regime must be one of {sorted(_ONESTOP_REGIMES)}, got {regime!r}"
        )
    root = Path(root)
    if download:
        download_onestop(root, regime=regime)
    ia_path = _onestop_report_path(root, "ia", regime)
    fix_path = _onestop_report_path(root, "fixations", regime)
    for path, label in ((ia_path, "interest-area"), (fix_path, "fixation")):
        if not path.is_file():
            raise FileNotFoundError(
                f"OneStop {regime} {label} report not found: {path} — pass "
                "download=True to fetch it from OSF."
            )
    # Read via data.read_table (not pd.read_csv directly): the OSF .csv.zip
    # archives wrap the CSV alongside macOS __MACOSX resource-fork entries, which
    # pandas' zip reader rejects ("Multiple files found in ZIP"). read_table's
    # zip path filters that cruft and reads with low_memory=False.
    from . import data

    words = data.read_table(ia_path)
    fixations = data.read_table(fix_path)
    return words, fixations


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
# (``Monitor_resolution_in_px`` / ``RESOLUTION``) — the physical screen the data
# was recorded on; pass as ``canvas_size`` to :func:`scanpath_studio.plot_scanpath`
# for true-to-scale rendering.
MULTIPLEYE_MONITOR = (1920, 1080)

# The stimulus image is smaller than the screen (config ``IMAGE_WIDTH/HEIGHT_PX``)
# and was shown **centered**. The raw AOI/fixation coords are image-relative
# (text starts at the image's 81/88 px margins), so the loader shifts them by the
# centering offset below → they land where the participant actually saw them on
# the full monitor, and the page-image background sits at that same origin.
MULTIPLEYE_IMAGE_SIZE = (1310, 991)
_MULTIPLEYE_IMAGE_ORIGIN = (
    (MULTIPLEYE_MONITOR[0] - MULTIPLEYE_IMAGE_SIZE[0]) / 2,  # 305.0
    (MULTIPLEYE_MONITOR[1] - MULTIPLEYE_IMAGE_SIZE[1]) / 2,  # 44.5
)

# Separator between the stimulus and the page in a per-page ``trial_id``. Two
# underscores keep it visually distinct from the single underscores already in
# stimulus names (``Lit_Alchemist_4``) while staying filename-safe for export.
_MULTIPLEYE_PAGE_SEP = "__"


def _multipleye_page_label(page) -> str:
    """Zero-padded page token for a sortable ``trial_id`` (``page_1`` → ``page_01``).

    The per-page ``trial_id`` (``Lit_Alchemist_4__page_01``) is what the trial
    picker sorts on, so the page number must zero-pad to sort numerically
    (otherwise page_10 falls between page_1 and page_2). Non-``page_N`` values
    pass through unchanged."""
    text = str(page)
    if text.startswith("page_") and text[5:].isdigit():
        return f"page_{int(text[5:]):02d}"
    return text


def _multipleye_trial_id(stimulus: str, page) -> pd.Series:
    """Per-page ``trial_id`` for a page Series (zero-padded for numeric sort)."""
    return stimulus + _MULTIPLEYE_PAGE_SEP + page.map(_multipleye_page_label)


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


# The stimulus images were rendered by the MultiplEYE pipeline with the FONT_SIZE
# (monitor px) + FONT declared in the stimulus config (``stimuli_*/config/
# config_*.py``). Carrying these onto the data lets the app reproduce the exact
# reading text true-to-scale instead of guessing the size from box geometry and
# rendering CJK in a generic fallback font. Known font files → a CSS family stack
# (the actual installed family name + sensible fallbacks); unknown ones get a
# humanised name + a monospace (and CJK, when the name says so) fallback.
_MULTIPLEYE_FONT_CSS = {
    "notosansmonocjksc": "'Noto Sans Mono CJK SC', 'Noto Sans CJK SC', monospace",
    "notosansmonocjktc": "'Noto Sans Mono CJK TC', 'Noto Sans CJK TC', monospace",
    "notosansmonocjkjp": "'Noto Sans Mono CJK JP', 'Noto Sans CJK JP', monospace",
    "notosansmonocjkkr": "'Noto Sans Mono CJK KR', 'Noto Sans CJK KR', monospace",
    "notosansmono": "'Noto Sans Mono', monospace",
}
_FONT_NAME_DROP = ("vf", "variable", "regular", "bold", "italic", "medium")
_FONT_SIZE_RE = re.compile(r"^\s*FONT_SIZE\s*=\s*([0-9]+(?:\.[0-9]+)?)", re.MULTILINE)
_FONT_FILE_RE = re.compile(r"^\s*FONT\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def _multipleye_config_path(root: Path) -> Optional[Path]:
    """The stimulus-generation config (``stimuli_*/config/config_*.py``), or None."""
    return next(iter(sorted(root.glob("stimuli_*/config/config_*.py"))), None)


def _multipleye_font_css(font_file: str) -> str:
    """CSS font-family stack for a config ``FONT`` path (e.g. a ``.ttf`` filename)."""
    stem = re.sub(r"[^a-z0-9]", "", Path(font_file).stem.lower())
    for drop in _FONT_NAME_DROP:
        if stem.endswith(drop):
            stem = stem[: -len(drop)]
    if stem in _MULTIPLEYE_FONT_CSS:
        return _MULTIPLEYE_FONT_CSS[stem]
    # Unknown font: humanise the file stem (spaces at case/digit boundaries) and
    # append a monospace fallback, plus a CJK fallback when the name implies CJK.
    raw = Path(font_file).stem
    human = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", raw).strip()
    tail = "'Noto Sans CJK SC', monospace" if "cjk" in stem else "monospace"
    return f"'{human}', {tail}" if human else tail


def _multipleye_font_config(root: Path) -> Tuple[Optional[float], Optional[str]]:
    """``(font_px, css_font_family)`` from the stimulus config, or ``(None, None)``.

    Reads ``FONT_SIZE`` (monitor px the images were rendered at) and ``FONT`` (the
    typeface) from ``config_*.py`` by regex — the file imports lab-specific paths,
    so we never exec it. Returns ``(None, None)`` when no config / no FONT_SIZE.
    """
    path = _multipleye_config_path(root)
    if path is None:
        return None, None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    size_m = _FONT_SIZE_RE.search(text)
    if size_m is None:
        return None, None
    font_px = float(size_m.group(1))
    file_m = _FONT_FILE_RE.search(text)
    family = _multipleye_font_css(file_m.group(1)) if file_m else None
    return font_px, family


def _multipleye_word_boxes_from_frame(
    chars: pd.DataFrame, stimulus: str
) -> pd.DataFrame:
    """Aggregate one stimulus' character-level AOI rows to one box per (page, word).

    Reading pages only (``page_*``). ``stimulus`` is the (CamelCase-canonical)
    name stamped into ``stimulus`` / ``text_id`` / ``genre`` / ``trial_id`` so the
    boxes' per-page trial ids line up with the fixations'. Emits *edge* columns
    (``left/right/top/bottom``) to match ``MULTIPLEYE_WORD_SCHEMA`` (no participant
    — stimulus-level boxes broadcast across readers). Shared by the directory
    loader and the upload recipe; returns an empty frame if no reading-page rows
    (or no ``page`` column at all — e.g. a stray / question-AOI upload)."""
    if "page" not in chars.columns:
        return chars.iloc[0:0]
    chars = chars[chars["page"].astype(str).str.startswith("page_")].copy()
    if chars.empty:
        return chars
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
    # Shift image-relative coords to where the centered stimulus appeared on the
    # full monitor (so they're true-to-scale on MULTIPLEYE_MONITOR).
    off_x, off_y = _MULTIPLEYE_IMAGE_ORIGIN
    boxes["left"] += off_x
    boxes["right"] += off_x
    boxes["top"] += off_y
    boxes["bottom"] += off_y
    boxes["stimulus"] = stimulus
    # `text_id` (= stimulus) so both the explicit schema and the app's auto-detect
    # path key stimulus-level grouping on the stimulus, not the per-page trial id.
    boxes["text_id"] = stimulus
    boxes["genre"] = stimulus.split("_")[0]
    boxes["trial_id"] = _multipleye_trial_id(stimulus, boxes["page"])
    return boxes


def _multipleye_word_boxes(aoi_dir: Path, stimuli: Iterable[str]) -> pd.DataFrame:
    """Stimulus-level word boxes from per-stimulus AOI files under ``aoi_dir``.

    One row per (stimulus, page, word_idx); raises if a stimulus' AOI file is
    missing (the directory loader knows exactly which file each stimulus needs)."""
    frames = []
    for stimulus in sorted(set(stimuli)):
        path = aoi_dir / f"{stimulus.lower()}_aoi.csv"
        if not path.is_file():
            raise FileNotFoundError(
                f"MultiplEYE AOI file not found for stimulus {stimulus!r}: {path}"
            )
        frames.append(_multipleye_word_boxes_from_frame(pd.read_csv(path), stimulus))
    return pd.concat(frames, ignore_index=True)


def _stamp_multipleye_fixations(df: pd.DataFrame, info: dict) -> pd.DataFrame:
    """Filter to reading pages and stamp identity columns parsed from a filename.

    ``info`` is a ``_multipleye_parse_filename`` dict. Returns the reading-page
    (``page_*``; ``name == 'fixation'`` when the column is present) fixation rows
    with the canonical identity columns, or an empty frame if none remain (or the
    upload has no ``page`` column at all). Shared by the directory loader (one
    file) and the upload recipe (one source_file group)."""
    if "page" not in df.columns:
        return df.iloc[0:0]
    df = df[df["page"].astype(str).str.startswith("page_")]
    if "name" in df.columns:  # scanpaths tag each row; keep fixations only
        df = df[df["name"] == "fixation"]
    if df.empty:
        return df
    df = df.copy()
    session = info["session"]
    stimulus = info["stimulus"]
    # Shift image-relative fixation coords to the centered on-screen position.
    off_x, off_y = _MULTIPLEYE_IMAGE_ORIGIN
    df["location_x"] = pd.to_numeric(df["location_x"], errors="coerce") + off_x
    df["location_y"] = pd.to_numeric(df["location_y"], errors="coerce") + off_y
    df["participant_id"] = session
    df["participant"] = session.split("_", 1)[0]  # bare pid
    df["session"] = session.rsplit("_", 1)[-1]  # ET1 / ET2
    df["stimulus"] = stimulus
    df["text_id"] = stimulus  # stimulus-level grouping key (see word boxes)
    df["genre"] = stimulus.split("_")[0]
    df["is_practice"] = bool(info["practice"])
    df["trial_num"] = int(info["trial_num"])
    df["trial_id"] = _multipleye_trial_id(stimulus, df["page"])
    return df


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
            if stim_filter is not None and info["stimulus"] not in stim_filter:
                continue
            stamped = _stamp_multipleye_fixations(pd.read_csv(path), info)
            if not stamped.empty:
                frames.append(stamped)
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
# When per-reader reading measures are attached, the word boxes carry a real
# ``participant_id`` (per reader) and the per-reader IA_* measures, so they take
# the participant branch in ``normalize_words`` (no stimulus-level broadcast).
MULTIPLEYE_WORD_SCHEMA_PER_READER = dict(
    MULTIPLEYE_WORD_SCHEMA, participant="participant_id"
)


# --- Side data: questions / reader metadata / reading measures / page images ---

# Reader-metadata columns carried from participant_data.csv → namespaced ``pp_*``.
MULTIPLEYE_PARTICIPANT_META_COLS = {
    "age": "pp_age",
    "gender": "pp_gender",
    "native_language_1": "pp_native_language",
    "years_education": "pp_years_education",
    "level_education": "pp_education_level",
}

# MultiplEYE reading-measure column → the canonical EyeLink IA_* name the app
# already recognizes (``data.WORD_OPTIONAL_FIELDS``) and prefers over recomputed
# measures. Regression in/out *flags* are derived from the counts (RR is
# "re-reading", not a regression flag, so it is intentionally not mapped).
MULTIPLEYE_RM_MAP = {
    "FFD": "IA_FIRST_FIXATION_DURATION",
    "FPRT": "IA_FIRST_RUN_DWELL_TIME",  # first-pass / gaze duration
    "TFT": "IA_DWELL_TIME",  # total fixation time
    "TFC": "IA_FIXATION_COUNT",
    "RPD_inc": "IA_REGRESSION_PATH_DURATION",
    "TRC_in": "IA_REGRESSION_IN_COUNT",
    "TRC_out": "IA_REGRESSION_OUT_COUNT",
    "skipped": "IA_SKIP",
}

# Reading-measures file name: the stimulus part has NO trailing ``_<id>``.
_MULTIPLEYE_RM_RE = re.compile(
    r"^(?P<session>\d+_[A-Za-z]{2}_[A-Za-z]{2}_\d+_ET\d+)_"
    r"(?:PRACTICE_)?trial_\d+_(?P<stim_name>.+)_reading_measures$"
)


def _multipleye_questions_path(root: Path) -> Optional[Path]:
    """The comprehension-questions workbook under ``root``, or None."""
    return next(
        iter(sorted(root.glob("stimuli_*/multipleye_comprehension_questions_*.xlsx"))),
        None,
    )


def _multipleye_image_dir(root: Path) -> Optional[Tuple[Path, str]]:
    """``(stimulus-images dir, language tag)`` or None.

    The language is read from the directory name (``stimuli_images_zh_ch_1`` →
    ``zh``), never hardcoded, so other MultiplEYE languages work."""
    for d in sorted(root.glob("stimuli_*/stimuli_images_*")):
        if d.is_dir():
            parts = d.name.removeprefix("stimuli_images_").split("_")
            return d, (parts[0] if parts and parts[0] else "")
    return None


def _multipleye_questions_from_frame(qs: pd.DataFrame) -> dict:
    """``{stimulus -> JSON list of comprehension questions}`` from a questions
    frame (workbook sheet 0), joined by ``stimulus_name + "_" + stimulus_id``."""
    if (
        qs is None
        or qs.empty
        or not {"stimulus_name", "stimulus_id"} <= set(qs.columns)
    ):
        return {}
    sort_cols = [c for c in ("condition_no", "question_no") if c in qs.columns]
    out: dict = {}
    for (name, sid), group in qs.groupby(["stimulus_name", "stimulus_id"]):
        if sort_cols:
            group = group.sort_values(sort_cols)
        items = []
        for _, r in group.iterrows():
            distractors = [
                str(r[c]).strip()
                for c in ("distractor_a", "distractor_b", "distractor_c")
                if c in qs.columns
                and str(r.get(c, "nan")).strip().lower() not in ("", "nan")
            ]
            items.append(
                {
                    "question": str(r.get("question", "")),
                    "target": str(r.get("target", "")),
                    "distractors": distractors,
                    "condition": str(r.get("condition_name", "")),
                    "question_no": (
                        int(r["question_no"])
                        if "question_no" in qs.columns
                        and pd.notna(r.get("question_no"))
                        else None
                    ),
                }
            )
        out[f"{name}_{int(sid)}"] = json.dumps(items, ensure_ascii=False)
    return out


def _multipleye_questions_by_stimulus(xlsx_path: Path) -> dict:
    """Read the comprehension workbook and return ``{stimulus -> questions JSON}``."""
    return _multipleye_questions_from_frame(pd.read_excel(xlsx_path, sheet_name=0))


def _normalize_multipleye_participant_meta(
    df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Select + namespace reader-metadata columns from a participant_data frame.

    One row per ``(participant_id:Int64, session:str)``; None if the join keys
    are absent. Used by both the directory loader and the upload path."""
    if df is None or not {"participant_id", "session"} <= set(df.columns):
        return None
    keep = {
        src: dest
        for src, dest in MULTIPLEYE_PARTICIPANT_META_COLS.items()
        if src in df.columns
    }
    out = df[["participant_id", "session", *keep]].copy()
    out["participant_id"] = pd.to_numeric(
        out["participant_id"], errors="coerce"
    ).astype("Int64")
    out["session"] = out["session"].astype(str)
    return out.rename(columns=keep).drop_duplicates(["participant_id", "session"])


def _multipleye_participant_meta(root: Path) -> Optional[pd.DataFrame]:
    """Reader metadata from ``participant_data.csv`` (namespaced ``pp_*``), or None."""
    path = root / "participant_data.csv"
    return (
        _normalize_multipleye_participant_meta(pd.read_csv(path))
        if path.is_file()
        else None
    )


def _merge_multipleye_participant_meta(
    fixations: pd.DataFrame, meta: Optional[pd.DataFrame]
) -> pd.DataFrame:
    """Left-merge reader metadata onto fixations by ``(int(participant), session)``.

    The bare pid is zero-padded text on the fixations (``001``) but an integer in
    participant_data (``1``) — join on the int-coerced value, never the string."""
    if meta is None or fixations.empty:
        return fixations
    fixations = fixations.copy()
    fixations["_pid_int"] = pd.to_numeric(
        fixations["participant"], errors="coerce"
    ).astype("Int64")
    meta = meta.rename(columns={"participant_id": "_pid_int"})
    merged = fixations.merge(meta, on=["_pid_int", "session"], how="left")
    return merged.drop(columns=["_pid_int"])


def _multipleye_read_reading_measures(
    root: Path,
    sessions: Optional[Iterable[str]],
    stim_namemap: dict,
) -> pd.DataFrame:
    """Per-(reader, page, word) reading measures, columns renamed to IA_*.

    ``stim_namemap`` resolves the id-stripped file-name stimulus (``Lit_Alchemist``)
    to the full stimulus (``Lit_Alchemist_4``). Empty frame if none found."""
    base = root / "reading_measures"
    session_filter = None if sessions is None else {str(s) for s in sessions}
    keep_src = list(MULTIPLEYE_RM_MAP)
    frames = []
    for session_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if session_filter is not None and session_dir.name not in session_filter:
            continue
        for path in sorted(session_dir.glob("*_reading_measures.csv")):
            m = _MULTIPLEYE_RM_RE.match(path.stem)
            if m is None:
                continue
            stimulus = stim_namemap.get(m.group("stim_name"))
            if stimulus is None:  # a stimulus not in this load (stimuli filter)
                continue
            df = pd.read_csv(path)
            if "page" not in df.columns or "word_idx" not in df.columns:
                continue
            cols = ["page", "word_idx"] + [c for c in keep_src if c in df.columns]
            df = df[cols].rename(columns=MULTIPLEYE_RM_MAP)
            if "IA_REGRESSION_IN_COUNT" in df.columns:
                df["IA_REGRESSION_IN"] = (df["IA_REGRESSION_IN_COUNT"] > 0).astype(int)
            if "IA_REGRESSION_OUT_COUNT" in df.columns:
                df["IA_REGRESSION_OUT"] = (df["IA_REGRESSION_OUT_COUNT"] > 0).astype(
                    int
                )
            df["participant_id"] = m.group("session")
            df["stimulus"] = stimulus
            frames.append(df)
    return (
        pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    )


def _multipleye_words_per_reader(
    stim_boxes: pd.DataFrame, rm: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Stimulus boxes replicated per reader who read each stimulus, with that
    reader's reading measures merged by ``(page, word_idx)`` (word_idx restarts
    per page, so page MUST be in the join key)."""
    pairs = fixations[["participant_id", "stimulus"]].drop_duplicates()
    words = pairs.merge(stim_boxes, on="stimulus", how="inner")
    if not rm.empty:
        words = words.merge(
            rm, on=["participant_id", "stimulus", "page", "word_idx"], how="left"
        )
    return words


def _multipleye_stamp_questions(df: pd.DataFrame, questions: dict) -> pd.DataFrame:
    """Stamp the per-stimulus comprehension-questions JSON onto a frame."""
    if df.empty or not questions or "stimulus" not in df.columns:
        return df
    df = df.copy()
    df["comprehension_questions"] = df["stimulus"].map(questions)
    return df


def _multipleye_stamp_image_path(
    df: pd.DataFrame, image_dir: Path, lang: str
) -> pd.DataFrame:
    """Stamp the per-(stimulus, page) stimulus-image path onto a frame.

    ``Lit_Alchemist_4`` + ``page_3`` → ``…/lit_alchemist_id4_page_3_<lang>.png``."""
    if df.empty or not {"stimulus", "page"} <= set(df.columns):
        return df
    df = df.copy()
    stim = df["stimulus"].astype(str)
    name = stim.str.rsplit("_", n=1).str[0].str.lower()
    sid = stim.str.rsplit("_", n=1).str[1]
    pnum = df["page"].astype(str).str.replace("page_", "", regex=False)
    df["image_path"] = (
        f"{image_dir}/" + name + "_id" + sid + "_page_" + pnum + f"_{lang}.png"
    )
    # Where the (centered) image sits on the monitor — matches the coordinate
    # offset applied to the fixations/boxes, so the image aligns with the data.
    df["image_x"] = _MULTIPLEYE_IMAGE_ORIGIN[0]
    df["image_y"] = _MULTIPLEYE_IMAGE_ORIGIN[1]
    return df


def _multipleye_stamp_font(
    df: pd.DataFrame, font_px: Optional[float], family: Optional[str]
) -> pd.DataFrame:
    """Stamp the stimulus typeface (``stimulus_font_px`` / ``stimulus_font_family``).

    The values are dataset-constant (read once from the stimulus config); the app
    snaps its font controls to them so the reading text renders at the exact size
    and typeface the stimulus images were drawn with."""
    if df.empty or font_px is None:
        return df
    df = df.copy()
    df["stimulus_font_px"] = float(font_px)
    if family:
        df["stimulus_font_family"] = family
    return df


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
    attach_reading_measures: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) MultiplEYE ``(words, fixations)`` frames.

    Same inputs as :func:`load_multipleye`, but returns the frames *before*
    schema normalization — for callers that run their own auto-detection /
    column mapping (e.g. the Streamlit app's MultiplEYE data source). Fixations
    carry parsed ``participant_id`` (the session), per-page ``trial_id``, pixel
    ``location_x/y``, the trial-level facets (``genre`` / ``session`` /
    ``is_practice`` / ``trial_num``), and any reader metadata
    (``pp_*`` from participant_data.csv), comprehension questions, and stimulus
    image path that the corpus ships.

    Word boxes are stimulus-level (no participant → broadcast) *unless*
    ``reading_measures/`` exists and ``attach_reading_measures`` is on, in which
    case the boxes are emitted **per reader** with the corpus's pre-aggregated
    reading measures merged in as ``IA_*`` columns (the app then prefers them over
    recomputed metrics). Use :func:`load_multipleye` for normalized frames.
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
    # Reader metadata (age/gender/languages…) merged onto every fixation row.
    fixations = _merge_multipleye_participant_meta(
        fixations, _multipleye_participant_meta(root)
    )

    stim_boxes = _multipleye_word_boxes(
        _multipleye_aoi_dir(root), fixations["stimulus"].unique()
    )
    # Pre-aggregated reading measures → per-reader word boxes (skips the
    # stimulus-level broadcast). Only when the corpus ships reading_measures/.
    if attach_reading_measures and (root / "reading_measures").is_dir():
        stim_namemap = {s.rsplit("_", 1)[0]: s for s in fixations["stimulus"].unique()}
        rm = _multipleye_read_reading_measures(root, sessions, stim_namemap)
        words = _multipleye_words_per_reader(stim_boxes, rm, fixations)
    else:
        words = stim_boxes

    # Comprehension questions + stimulus images, stamped on both frames.
    qpath = _multipleye_questions_path(root)
    if qpath is not None:
        qmap = _multipleye_questions_by_stimulus(qpath)
        words = _multipleye_stamp_questions(words, qmap)
        fixations = _multipleye_stamp_questions(fixations, qmap)
    image = _multipleye_image_dir(root)
    if image is not None:
        image_dir, lang = image
        words = _multipleye_stamp_image_path(words, image_dir, lang)
        fixations = _multipleye_stamp_image_path(fixations, image_dir, lang)
    # Reading typeface (size + family) from the stimulus config → the app renders
    # the text true-to-scale at the exact font the images were drawn with.
    font_px, font_family = _multipleye_font_config(root)
    words = _multipleye_stamp_font(words, font_px, font_family)
    fixations = _multipleye_stamp_font(fixations, font_px, font_family)
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

    # Per-reader word boxes (reading measures attached) carry a participant_id, so
    # they take the participant branch in normalize_words (no broadcast);
    # stimulus-level boxes (no participant_id) broadcast across readers.
    word_schema = dict(
        MULTIPLEYE_WORD_SCHEMA_PER_READER
        if "participant_id" in words_raw.columns
        else MULTIPLEYE_WORD_SCHEMA
    )
    return api.load_scanpath_data(
        words=words_raw,
        fixations=fixations_raw,
        word_schema=word_schema,
        fix_schema=dict(
            MULTIPLEYE_FIX_SCHEMA,
            word_id="word_idx" if "word_idx" in fixations_raw.columns else None,
        ),
    )


# --- Browser-upload path -----------------------------------------------------
# Loading MultiplEYE through the Add-dataset wizard: the browser strips folders,
# so identity is recovered from each row's ``source_file`` (the uploaded filename
# stem, tagged by ``data.read_tables``) instead of the directory tree.


def _multipleye_aoi_stimulus_from_source(stem: str) -> str:
    """Stimulus name from an AOI filename stem, stripping a trailing ``_aoi``.

    ``lit_alchemist_4_aoi`` → ``lit_alchemist_4`` (still lowercase; the caller
    canonicalizes the case). ``_aoi_questions`` files (question/option AOIs, whose
    rows aren't ``page_*`` and so produce no word boxes) are handled too."""
    s = str(stem)
    for suffix in ("_aoi_questions", "_aoi"):
        if s.lower().endswith(suffix):
            return s[: -len(suffix)]
    return s


def _multipleye_fixations_from_frame(fixations_df: pd.DataFrame) -> pd.DataFrame:
    """Identity-stamped reading-page fixations from a concatenated UPLOAD frame.

    Rows must carry a ``source_file`` column (the uploaded filename stem). Each
    file group is parsed with ``_multipleye_parse_filename``; groups whose name
    isn't MultiplEYE-shaped are skipped. When both a ``_scanpath`` and a
    ``_fixation`` file are uploaded for the same (session, trial), the scanpath
    one wins (it carries word indices), mirroring the directory loader's source
    preference. Returns an empty frame if nothing matched (the wizard then
    surfaces a problem rather than crashing)."""
    from .data import SOURCE_FILE_COLUMN

    if SOURCE_FILE_COLUMN not in fixations_df.columns:
        return pd.DataFrame()
    # Prefer scanpath over fixation per (session, trial, stimulus) so uploading
    # both kinds of a trial doesn't double its rows.
    chosen: dict = {}
    for stem, group in fixations_df.groupby(SOURCE_FILE_COLUMN, sort=False):
        info = _multipleye_parse_filename(str(stem))
        if info is None:
            continue
        key = (info["session"], info["trial_num"], info["stimulus"])
        prev = chosen.get(key)
        if prev is None or (
            info["kind"] == "scanpath" and prev[0]["kind"] != "scanpath"
        ):
            chosen[key] = (info, group)
    frames = [
        stamped
        for info, group in chosen.values()
        if not (stamped := _stamp_multipleye_fixations(group, info)).empty
    ]
    return (
        pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    )


def multipleye_frames_from_uploads(
    fixations_df: pd.DataFrame,
    aoi_df: Optional[pd.DataFrame] = None,
    *,
    questions_df: Optional[pd.DataFrame] = None,
    participant_meta_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw MultiplEYE ``(words, fixations)`` frames from UPLOADED files.

    The browser-upload analogue of :func:`multipleye_raw_frames`: identity is
    parsed from each row's ``source_file`` (the uploaded filename stem) instead of
    the directory tree, since browser uploads drop folders. ``fixations_df`` is
    the concatenated scanpath/fixation CSVs; ``aoi_df`` the concatenated
    character-level AOI CSVs (optional — without it you get fixations and no word
    boxes). AOI filenames are lowercase (``lit_alchemist_4_aoi``) while scanpath
    filenames are CamelCase, so each AOI group's stimulus is relabeled to the
    CamelCase name seen in the fixations before building ``trial_id`` — otherwise
    the stimulus-words broadcast (which inner-joins on ``trial_id``) drops every
    box. ``questions_df`` (the comprehension workbook) and ``participant_meta_df``
    (participant_data.csv) are merged when provided. Reading measures + stimulus
    images need the directory tree, so they are not available on this path. Feed
    the result through :func:`load_multipleye_uploads`."""
    from .data import SOURCE_FILE_COLUMN

    fixations = _multipleye_fixations_from_frame(fixations_df)
    fixations = _merge_multipleye_participant_meta(
        fixations, _normalize_multipleye_participant_meta(participant_meta_df)
    )
    qmap = (
        _multipleye_questions_from_frame(questions_df)
        if questions_df is not None
        else {}
    )
    fixations = _multipleye_stamp_questions(fixations, qmap)

    if fixations.empty or aoi_df is None or getattr(aoi_df, "empty", True):
        return pd.DataFrame(), fixations
    if SOURCE_FILE_COLUMN not in aoi_df.columns:
        return pd.DataFrame(), fixations

    # CamelCase canonical per lowercased stimulus, taken from the fixations.
    casemap: dict = {}
    for stim in fixations["stimulus"].unique():
        casemap.setdefault(str(stim).lower(), str(stim))

    frames = []
    for stem, group in aoi_df.groupby(SOURCE_FILE_COLUMN, sort=False):
        lower_stim = _multipleye_aoi_stimulus_from_source(str(stem))
        canonical = casemap.get(lower_stim.lower(), lower_stim)
        boxes = _multipleye_word_boxes_from_frame(group, canonical)
        if not boxes.empty:
            frames.append(boxes)
    words = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    words = _multipleye_stamp_questions(words, qmap)
    return words, fixations


def load_multipleye_uploads(
    fixations_df: pd.DataFrame,
    aoi_df: Optional[pd.DataFrame] = None,
    *,
    questions_df: Optional[pd.DataFrame] = None,
    participant_meta_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normalized ``(words, fixations)`` from UPLOADED MultiplEYE files.

    Like :func:`load_multipleye`, but for in-memory uploaded frames (identity from
    each row's ``source_file``; see :func:`multipleye_frames_from_uploads`).
    ``words`` is an empty frame when no AOI files were uploaded; the fixations then
    plot at their own ``location_x/y`` with no word boxes. Optional
    ``questions_df`` / ``participant_meta_df`` add the comprehension panel + reader
    metadata. Raises ``ValueError`` (via :func:`api.load_scanpath_data`) if the
    fixations frame has no MultiplEYE-shaped filenames."""
    words_raw, fix_raw = multipleye_frames_from_uploads(
        fixations_df,
        aoi_df,
        questions_df=questions_df,
        participant_meta_df=participant_meta_df,
    )

    from . import api

    return api.load_scanpath_data(
        words=words_raw if not words_raw.empty else None,
        fixations=fix_raw if not fix_raw.empty else None,
        word_schema=dict(MULTIPLEYE_WORD_SCHEMA) if not words_raw.empty else None,
        fix_schema=(
            dict(
                MULTIPLEYE_FIX_SCHEMA,
                word_id="word_idx" if "word_idx" in fix_raw.columns else None,
            )
            if not fix_raw.empty
            else None
        ),
    )
