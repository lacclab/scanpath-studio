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
import logging
import os
import re
import urllib.request
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

_LOGGER = logging.getLogger(__name__)

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
    readers: Iterable | None = None,
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
    readers: Iterable | None = None,
    texts: Iterable[str] | None = None,
    download: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    readers: Iterable | None = None,
    texts: Iterable[str] | None = None,
    download: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
# interest-area (word) + fixation reports, split by reading **regime** and by
# trial **part** (which screen of a trial — title / question preview /
# paragraph / questions / answers / QA / feedback). The reports share the
# bundled demo's schema (the demo is a 3-pid subset of the Paragraph part), so
# the generic auto-detect → normalize pipeline handles every part with no
# part-specific column mapping — this loader only fetches, reads, and (when more
# than one part is loaded) folds the part into the trial identity so the parts
# don't collide.
#
# Two **variants**:
#   * ``public`` — the OSF download-on-demand release (this module fetches it).
#   * ``lacclab`` — a lab-processed local export with ~40 extra derived columns
#     (``unique_paragraph_id``, span indices, normalized dwell, …); a superset
#     of the public schema, so it flows through the same pipeline (and its
#     ``unique_paragraph_id`` wins in normalization). No download — a local path.
#
# Distinct from the env-var "OneStop server bundle" source
# (``data.load_onestop_server_bundle``), which serves a lacclab export via
# ``$ONESTOP_DATA_DIR`` and its per-pid shards for review-app deep links.
# ---------------------------------------------------------------------------

_ONESTOP_OSF_URL = "https://osf.io/download/{resource}"

# The seven trial parts (interest periods), in presentation order. Each maps to
# one interest-area + one fixation OSF report in the ``onestop-full`` release
# (all-regimes). Paragraph is the reading passage; the others are the surrounding
# screens (title, the pre/post question, its four answers, the combined QA
# screen, the correctness feedback). All share the Paragraph report schema
# (IA_LEFT/RIGHT/TOP/BOTTOM boxes, IA_LABEL word text, per-word reading measures),
# so every part renders as a scanpath. Keep the display order = presentation order.
_ONESTOP_PARTS: tuple[str, ...] = (
    "Title",
    "Question_Preview",
    "Paragraph",
    "Questions",
    "Answers",
    "QA",
    "Feedback",
)
ONESTOP_DEFAULT_PARTS: tuple[str, ...] = ("Paragraph",)

# OSF ids for the all-regimes **full** release (every part), from the OneStop
# repo's download_data_files.py "onestop-full" group. kind → part → OSF id.
_ONESTOP_FULL_OSF = {
    "ia": {
        "Title": "u7f9b",
        "Question_Preview": "zn473",
        "Paragraph": "zhywq",
        "Questions": "tcv9h",
        "Answers": "q3shp",
        "QA": "3j8av",
        "Feedback": "t6n8v",
    },
    "fixations": {
        "Title": "uwz2e",
        "Question_Preview": "7a3md",
        "Paragraph": "tbxdc",
        "Questions": "cmx6k",
        "Answers": "ax4md",
        "QA": "fg7se",
        "Feedback": "e76vz",
    },
}

# OSF ids for the per-regime **Paragraph-only** releases (the four reading
# regimes each ship just the paragraph reports, filtered to that regime), from
# the "ordinary"/"information_seeking"/"repeated"/"information_seeking_repeated"
# groups. regime → kind → OSF id. Only the Paragraph part is regime-split on OSF;
# the other parts come from the all-regimes full release (see _ONESTOP_FULL_OSF).
_ONESTOP_REGIMES = {
    "ordinary": dict(ia="xkgfz", fixations="ne4az"),
    "information_seeking": dict(ia="yxzte", fixations="bznfk"),
    "repeated": dict(ia="dwfk4", fixations="83ctd"),
    "information_seeking_repeated": dict(ia="ygjup", fixations="paqn8"),
}

ONESTOP_VARIANTS = ("public", "lacclab")


def _onestop_osf_resource(kind: str, part: str, regime: str) -> str | None:
    """OSF id for a (kind, part, regime), or None when not published.

    Paragraph is regime-split (four separate downloads); every other part only
    exists in the all-regimes full release, so it uses the full-release id
    regardless of regime."""
    if part == "Paragraph" and regime in _ONESTOP_REGIMES:
        return _ONESTOP_REGIMES[regime].get(kind)
    return _ONESTOP_FULL_OSF.get(kind, {}).get(part)


def _onestop_report_path(
    root: Path, kind: str, regime: str, part: str = "Paragraph"
) -> Path:
    """Local path of a public-variant OneStop report CSV.zip.

    Paragraph keeps the historical ``<kind>_Paragraph_<regime>.csv.zip`` name
    (per-regime download). Other parts are all-regimes, so they use
    ``<kind>_<Part>.csv.zip`` (matching the OSF full-release filenames)."""
    if part == "Paragraph":
        return root / f"{kind}_Paragraph_{regime}.csv.zip"
    return root / f"{kind}_{part}.csv.zip"


def _onestop_lacclab_report_path(root: Path, kind: str, part: str) -> Path:
    """Local path of a lacclab-variant OneStop report CSV.zip.

    The lacclab export names files plainly by part (no regime suffix) — e.g.
    ``ia_Paragraph.csv.zip`` / ``fixations_Paragraph.csv.zip`` — since a lacclab
    export folder holds one regime's reports."""
    return root / f"{kind}_{part}.csv.zip"


def _onestop_part_paths(
    root: Path, kind: str, regime: str, part: str, variant: str
) -> Path:
    """Dispatch to the public or lacclab path convention for one report."""
    if variant == "lacclab":
        return _onestop_lacclab_report_path(root, kind, part)
    return _onestop_report_path(root, kind, regime, part)


def _normalize_onestop_parts(parts: Iterable[str] | None) -> list:
    """Validate + order a requested parts selection (defaults to Paragraph)."""
    if not parts:
        return list(ONESTOP_DEFAULT_PARTS)
    requested = {str(p) for p in parts}
    unknown = sorted(requested - set(_ONESTOP_PARTS))
    if unknown:
        raise ValueError(
            f"Unknown OneStop parts: {unknown} (valid: {list(_ONESTOP_PARTS)})"
        )
    # Keep presentation order regardless of how they were passed.
    return [p for p in _ONESTOP_PARTS if p in requested]


def onestop_present(
    root,
    *,
    regime: str = "ordinary",
    parts: Iterable[str] | None = None,
    variant: str = "public",
) -> bool:
    """True when ``root`` holds the IA + fixation reports for every chosen part.

    Lets the app show a *found vs. download* status before any (large) read.
    ``variant`` selects the file-name convention (public OSF vs lacclab local)."""
    root = Path(root)
    for part in _normalize_onestop_parts(parts):
        for kind in ("ia", "fixations"):
            if not _onestop_part_paths(root, kind, regime, part, variant).is_file():
                return False
    return True


def download_onestop(
    root,
    *,
    regime: str = "ordinary",
    parts: Iterable[str] | None = None,
) -> Path:
    """Download a OneStop regime + parts' IA + fixation reports into ``root``.

    Fetches the two CSV.zip reports for each chosen ``part`` from OneStop's OSF
    release into ``root``, skipping any already present, so it's safe to call
    repeatedly. The reports are large (tens to hundreds of MB each); caching them
    on disk means only the first load pays the download.

    ``regime`` is one of ``ordinary``, ``information_seeking``, ``repeated``,
    ``information_seeking_repeated``. ``parts`` is any subset of
    ``Title / Question_Preview / Paragraph / Questions / Answers / QA /
    Feedback`` (default: just Paragraph). Only Paragraph is regime-split on OSF;
    the other parts come from the all-regimes full release.

    (Download is a *public*-variant operation — the lacclab variant is a local
    export with no download URL.)
    """
    if regime not in _ONESTOP_REGIMES:
        raise ValueError(
            f"regime must be one of {sorted(_ONESTOP_REGIMES)}, got {regime!r}"
        )
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for part in _normalize_onestop_parts(parts):
        for kind in ("ia", "fixations"):
            dest = _onestop_report_path(root, kind, regime, part)
            if dest.is_file():
                continue
            resource = _onestop_osf_resource(kind, part, regime)
            if resource is None:
                continue
            url = _ONESTOP_OSF_URL.format(resource=resource)
            print(f"Downloading OneStop {regime} {part} {kind} report from {url} …")
            # Write to a temp file and atomically rename into place, so an
            # interrupted write (killed process / full disk) never leaves a
            # truncated .csv.zip that `dest.is_file()` would then skip forever —
            # forcing a manual delete. The reports are large, so the window is real.
            tmp = dest.with_name(dest.name + ".part")
            with urllib.request.urlopen(url) as response:
                tmp.write_bytes(response.read())
            tmp.replace(dest)
    return root


def _read_onestop_part(
    root: Path, kind: str, regime: str, part: str, variant: str
) -> pd.DataFrame:
    """Read one part's report and stamp a ``part`` column onto it.

    QA repeats the question words in the answer region with the *same* IA_ID, so
    its per-trial word ids aren't unique — drop the exact-duplicate rows so the
    fixation→word assignment (which keys on word id) keeps one box per word."""
    from . import data

    path = _onestop_part_paths(root, kind, regime, part, variant)
    if not path.is_file():
        raise FileNotFoundError(
            f"OneStop {regime} {part} {kind} report not found: {path} — pass "
            "download=True to fetch it from OSF (public variant), or point at a "
            "folder holding the lacclab reports."
        )
    # Read via data.read_table (not pd.read_csv directly): the OSF .csv.zip
    # archives wrap the CSV alongside macOS __MACOSX resource-fork entries, which
    # pandas' zip reader rejects ("Multiple files found in ZIP"). read_table's
    # zip path filters that cruft and reads with low_memory=False.
    frame = data.read_table(path)
    frame["part"] = part
    if part == "QA":
        frame = frame.drop_duplicates()
    return frame


def _fold_onestop_part_into_identity(
    words: pd.DataFrame, fixations: pd.DataFrame, parts: list
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """When >1 part is loaded, prefix the paragraph id with the part.

    Every part of a trial shares the same ``paragraph_id`` / ``TRIAL_INDEX``, so
    loading e.g. Paragraph + Title together would collapse them into one trial
    (and fight over word boxes). Prefix ``unique_paragraph_id`` /
    ``paragraph_id`` / ``unique_trial_id`` with the part so each part becomes its
    own trial — ``Paragraph::1`` vs ``Title::1``. A single-part load is untouched
    (the historical trial ids are preserved)."""
    if len(parts) <= 1:
        return words, fixations

    def _prefix(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or "part" not in frame.columns:
            return frame
        frame = frame.copy()
        part = frame["part"].astype(str)
        for col in ("unique_paragraph_id", "paragraph_id", "unique_trial_id"):
            if col in frame.columns:
                frame[col] = part + "::" + frame[col].astype(str)
        return frame

    return _prefix(words), _prefix(fixations)


def onestop_raw_frames(
    root,
    *,
    regime: str = "ordinary",
    parts: Iterable[str] | None = None,
    variant: str = "public",
    download: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) OneStop ``(words, fixations)`` frames.

    Reads the interest-area + fixation reports for each chosen ``part`` of
    ``regime`` from ``root`` (fetching the public reports from OSF first when
    ``download=True``). The reports already match the bundled demo's schema, so
    the returned frames go through the same auto-detect → normalize path as an
    upload — no OneStop-specific column mapping is needed here.

    ``parts`` is any subset of the seven trial parts (default: Paragraph). When
    more than one is chosen, each part becomes its own trial (the part is folded
    into the paragraph/trial id so they don't collide). ``variant`` is
    ``"public"`` (OSF release) or ``"lacclab"`` (a local lab-processed export;
    superset schema, no download).
    """
    if regime not in _ONESTOP_REGIMES:
        raise ValueError(
            f"regime must be one of {sorted(_ONESTOP_REGIMES)}, got {regime!r}"
        )
    if variant not in ONESTOP_VARIANTS:
        raise ValueError(
            f"variant must be one of {list(ONESTOP_VARIANTS)}, got {variant!r}"
        )
    part_list = _normalize_onestop_parts(parts)
    root = Path(root)
    if download and variant == "public":
        download_onestop(root, regime=regime, parts=part_list)

    word_frames = [
        _read_onestop_part(root, "ia", regime, part, variant) for part in part_list
    ]
    fix_frames = [
        _read_onestop_part(root, "fixations", regime, part, variant)
        for part in part_list
    ]
    words = pd.concat(word_frames, ignore_index=True, sort=False)
    fixations = pd.concat(fix_frames, ignore_index=True, sort=False)
    return _fold_onestop_part_into_identity(words, fixations, part_list)


def load_onestop(
    root,
    *,
    regime: str = "ordinary",
    parts: Iterable[str] | None = None,
    variant: str = "public",
    download: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load OneStop as normalized ``(words, fixations)`` frames, ready to plot.

    ``root`` is a folder holding (or to download into, public variant only) the
    OneStop reports. Narrow the load with ``regime`` (``ordinary`` /
    ``information_seeking`` / ``repeated`` / ``information_seeking_repeated``),
    ``parts`` (any subset of ``Title / Question_Preview / Paragraph / Questions /
    Answers / QA / Feedback`` — default Paragraph), and ``variant`` (``public``
    OSF release or ``lacclab`` local export). The public OSF reports are large;
    pass ``download=True`` to fetch the chosen regime + parts into ``root`` on
    first use::

        words, fixations = load_onestop(
            "data/OneStop", regime="ordinary", parts=["Paragraph"], download=True
        )
        fig = scanpath_studio.plot_scanpath(
            words, fixations, canvas_size=(2560, 1440)
        )

    OneStop's presentation monitor was 2560×1440 (Dell U2715H); pass that as
    ``canvas_size`` to :func:`scanpath_studio.plot_scanpath` for true-to-scale
    rendering. The reports already match the bundled demo's schema, so this reuses
    the generic auto-detect → normalize path (no OneStop-specific column mapping).
    """
    words_raw, fixations_raw = onestop_raw_frames(
        root, regime=regime, parts=parts, variant=variant, download=download
    )

    from . import api

    return api.load_scanpath_data(words=words_raw, fixations=fixations_raw)


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
# * **One stimulus spans several screens** ``page_1..page_N`` (plus the
#   comprehension-question screens that follow them) which all reuse the *same*
#   on-screen coordinates. DATA-24 models that directly: one reading of one
#   stimulus is **one trial** (``trial_id == text_id == "<stimulus>"``) whose
#   screens are the corpus's own ``page`` values — ``screen_id = "page_1"`` /
#   ``"question_4111"`` — each its own coordinate space (``multipart.py``).
#   ``screen_index`` is ranked from **that reader's own fixation onsets**, never
#   from the screen name: reading pages are shown in page order but the question
#   order is *shuffled per reader*. ``screen_kind`` (``reading`` | ``question``)
#   labels the two. ``familiarity_rating_screen_*`` / ``subject_difficulty_screen``
#   stay out: the corpus ships no AOI file for them, and
#   ``multipart.validate_matching_parts`` rejects word-box-less screens by design.
# * **Word boxes ship once per stimulus** (no participant) as *character*-level
#   AOI files ``stimuli_*/aoi_stimuli_*/<stimulus>_aoi.csv``. We aggregate chars
#   to one bounding box per (page, word_idx). ``word_idx`` is unique within a
#   page — hence within a screen — so it is the word id directly. The
#   **question** screens' boxes come from ``<stimulus>_aoi_questions.csv``, whose
#   rows are per *answer-layout version*: which version a reader saw is looked up
#   in ``stimuli_*/config/stimulus_order_versions_*.csv`` by their bare pid, so
#   question boxes are always per reader.
#
# Fixation source: ``scanpaths/`` (preferred — already page/word-tagged) or
# ``fixations/`` (raw onset/duration/x/y/page, no word linkage). The
# ``scanpaths/`` export is pre-filtered to reading pages, so **question screens
# are always read from ``fixations/``** whatever ``fixation_source`` says; the
# resulting mixed provenance inside one trial is visible as ``screen_kind``.

MULTIPLEYE_FIXATION_SOURCES = ("scanpaths", "fixations")

# The screen kinds a MultiplEYE trial is modelled from, in presentation order.
MULTIPLEYE_SCREEN_KINDS = ("reading", "question")

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


def _multipleye_screen_kind(page) -> str:
    """``"reading"`` / ``"question"`` for a corpus ``page`` value, else ``""``.

    The empty string is what excludes a screen from the load — the rating and
    difficulty screens ship no AOI file, so they would be word-box-less screens
    and ``multipart.validate_matching_parts`` rejects those by design."""
    text = str(page)
    if text.startswith("page_"):
        return "reading"
    if text.startswith("question_"):
        return "question"
    return ""


def _multipleye_page_number(page) -> int | None:
    """The 1-based page number of a ``page_N`` screen, or None."""
    text = str(page)
    return int(text[5:]) if text.startswith("page_") and text[5:].isdigit() else None


# The question id inside a screen name. It appears **unpadded** on the fixations
# (``question_4111``) and **zero-padded to the stimulus id's width** in the AOI
# file (``Lit_Alchemist_4_question_04111_target``), so the two only ever join on
# ``int(question_id)`` — a string match silently finds nothing.
_MULTIPLEYE_QUESTION_RE = re.compile(r"question_(?P<qid>\d+)(?:_(?P<block>.+))?$")


def _multipleye_question_parts(page) -> tuple[int, str] | None:
    """``(question_id, aoi_block)`` for a question screen / AOI page, or None.

    ``question_4111`` → ``(4111, "stem")`` (the fixations' name and the AOI's
    stem block); ``Lit_Alchemist_4_question_04111_target`` → ``(4111, "target")``.
    """
    match = _MULTIPLEYE_QUESTION_RE.search(str(page))
    if match is None:
        return None
    return int(match.group("qid")), (match.group("block") or "stem")


def _multipleye_question_screen_id(question_id: int) -> str:
    """The ``screen_id`` for a question screen — the fixations' own unpadded name."""
    return f"question_{question_id}"


def _multipleye_bare_pid(participant_id) -> int | None:
    """The integer pid inside a session string (``001_ZH_CH_1_ET1`` → 1)."""
    head = str(participant_id).split("_", 1)[0]
    return int(head) if head.isdigit() else None


# Per-trial file name: ``<session>_[PRACTICE_]trial_<n>_<stimulus>_<kind>``
# e.g. ``001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4_fixation`` or
#      ``001_ZH_CH_1_ET1_PRACTICE_trial_1_Enc_WikiMoon_13_scanpath``.
_MULTIPLEYE_TRIAL_RE = re.compile(
    r"^(?P<session>\d+_[A-Za-z]{2}_[A-Za-z]{2}_\d+_ET\d+)_"
    r"(?:(?P<practice>PRACTICE)_)?trial_(?P<trial_num>\d+)_"
    r"(?P<stimulus>.+)_(?P<kind>fixation|scanpath)$"
)


def _multipleye_parse_filename(stem: str) -> dict | None:
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


def _multipleye_config_path(root: Path) -> Path | None:
    """The stimulus-generation config (``stimuli_*/config/config_*.py``), or None."""
    return next(iter(sorted(root.glob("stimuli_*/config/config_*.py"))), None)


def _multipleye_font_css(font_file: str) -> str:
    """CSS font-family stack for a config ``FONT`` path (e.g. a ``.ttf`` filename)."""
    stem = re.sub(r"[^a-z0-9]", "", Path(font_file).stem.lower())
    for drop in _FONT_NAME_DROP:
        stem = stem.removesuffix(drop)
    if stem in _MULTIPLEYE_FONT_CSS:
        return _MULTIPLEYE_FONT_CSS[stem]
    # Unknown font: humanise the file stem (spaces at case/digit boundaries) and
    # append a monospace fallback, plus a CJK fallback when the name implies CJK.
    raw = Path(font_file).stem
    human = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", raw).strip()
    tail = "'Noto Sans CJK SC', monospace" if "cjk" in stem else "monospace"
    return f"'{human}', {tail}" if human else tail


def _multipleye_font_config(root: Path) -> tuple[float | None, str | None]:
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


def _multipleye_char_boxes(chars: pd.DataFrame, group: list) -> pd.DataFrame:
    """Aggregate character AOI rows to one bounding box per ``group``.

    Emits *edge* columns (``left/right/top/bottom``) already shifted onto the
    centered stimulus' on-screen position, so they are true-to-scale on
    ``MULTIPLEYE_MONITOR``. Groups keep first-appearance order (the caller sorts
    the characters into reading order first)."""
    chars = chars.copy()
    chars["_right"] = chars["top_left_x"] + chars["width"]
    chars["_bottom"] = chars["top_left_y"] + chars["height"]
    boxes = (
        chars.groupby(group, sort=False)
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
    off_x, off_y = _MULTIPLEYE_IMAGE_ORIGIN
    boxes["left"] += off_x
    boxes["right"] += off_x
    boxes["top"] += off_y
    boxes["bottom"] += off_y
    return boxes


def _multipleye_stamp_box_identity(boxes: pd.DataFrame, stimulus: str) -> pd.DataFrame:
    """Stamp the stimulus-level identity columns shared by every word box."""
    boxes["stimulus"] = stimulus
    # One reading of one stimulus is one trial; the screens inside it are the
    # corpus's own `page` values (mapped to `screen_id` by the schemas below).
    boxes["trial_id"] = stimulus
    boxes["text_id"] = stimulus
    boxes["genre"] = stimulus.split("_")[0]
    return boxes


def _multipleye_word_boxes_from_frame(
    chars: pd.DataFrame, stimulus: str
) -> pd.DataFrame:
    """Aggregate one stimulus' character-level AOI rows to one box per (page, word).

    Reading pages only (``page_*``) — question screens come from the sibling
    ``_aoi_questions`` file (:func:`_multipleye_question_boxes_from_frame`), whose
    layout is reader-specific. ``stimulus`` is the (CamelCase-canonical) name
    stamped into ``stimulus`` / ``text_id`` / ``genre`` / ``trial_id``. Emits
    *edge* columns (``left/right/top/bottom``) to match ``MULTIPLEYE_WORD_SCHEMA``
    (no participant — stimulus-level boxes broadcast across readers). Shared by
    the directory loader and the upload recipe; returns an empty frame if no
    reading-page rows (or no ``page`` column at all — e.g. a stray upload)."""
    if "page" not in chars.columns:
        return chars.iloc[0:0]
    chars = chars[chars["page"].astype(str).str.startswith("page_")].copy()
    if chars.empty:
        return chars
    boxes = _multipleye_char_boxes(chars, ["page", "word_idx"])
    boxes["screen_kind"] = "reading"
    return _multipleye_stamp_box_identity(boxes, stimulus)


def _multipleye_word_boxes(aoi_dir: Path, stimuli: Iterable[str]) -> pd.DataFrame:
    """Stimulus-level reading-page word boxes from the AOI files under ``aoi_dir``.

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


# --- Question screens: layout version → AOI blocks → per-screen word boxes ---


def _multipleye_versions_path(root: Path) -> Path | None:
    """The answer-layout version table under ``root``, or None."""
    return next(
        iter(sorted(root.glob("stimuli_*/config/stimulus_order_versions_*.csv"))),
        None,
    )


def _multipleye_layout_versions(frame: pd.DataFrame | None) -> dict:
    """``{bare pid -> question-image layout version}`` from a versions table.

    ``stimulus_order_versions_*.csv`` has one row per ``version_number`` with an
    optional ``participant_id``; only the assigned rows matter. The file keys on
    the *participant*, not the session, so ET1 and ET2 share one version."""
    if frame is None or getattr(frame, "empty", True):
        return {}
    if not {"version_number", "participant_id"} <= set(frame.columns):
        return {}
    pid = pd.to_numeric(frame["participant_id"], errors="coerce")
    version = pd.to_numeric(frame["version_number"], errors="coerce")
    keep = pid.notna() & version.notna()
    return {int(p): int(v) for p, v in zip(pid[keep], version[keep])}


def _multipleye_read_layout_versions(root: Path) -> dict:
    """Read the versions table under ``root`` (empty map when absent/unreadable)."""
    path = _multipleye_versions_path(root)
    if path is None:
        return {}
    try:
        frame = pd.read_csv(path)
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ):
        return {}
    return _multipleye_layout_versions(frame)


_QUESTION_KEY = ["_question_id", "_aoi_block"]


def _multipleye_question_block_order(chars: pd.DataFrame) -> pd.DataFrame:
    """``_block_order`` per (question, AOI block), by first-character geometry.

    The five blocks of a question screen (``stem`` + ``target`` + three
    distractors) are laid out around the screen, so reading order is the order of
    their first character: top, then left."""
    firsts = chars.groupby(_QUESTION_KEY, sort=False).head(1)
    firsts = firsts.sort_values(
        ["_question_id", "top_left_y", "top_left_x"], kind="stable"
    )
    order = firsts[_QUESTION_KEY].copy()
    order["_block_order"] = order.groupby("_question_id", sort=False).cumcount()
    return order


def _multipleye_question_boxes_from_frame(
    chars: pd.DataFrame, stimulus: str, version: int | None
) -> pd.DataFrame:
    """Question-screen word boxes for one stimulus at one answer-layout version.

    ``chars`` is a ``<stimulus>_aoi_questions.csv`` frame, whose ``page`` values
    name the AOI block (``Lit_Alchemist_4_question_04111_target``) or the question
    stem (``question_04111``) with the stimulus id **zero-padded** — the join back
    to the fixations' ``question_4111`` is therefore on ``int(question_id)``.

    Every block restarts ``word_idx`` at 0, so ``word_idx`` alone cannot be the
    word id: the blocks are put in reading order and one counter runs across
    them, with ``line_idx`` densely re-ranked the same way, so both are unique
    within the screen. The block name survives as ``aoi_block``, a genuinely
    useful per-word facet. Returns an empty frame when the file / version yields
    nothing."""
    if chars is None or getattr(chars, "empty", True) or "page" not in chars.columns:
        return pd.DataFrame()
    if "question_image_version" in chars.columns:
        if version is None:
            return pd.DataFrame()
        wanted = f"question_images_version_{int(version)}"
        # Filter BEFORE copying: the file holds every layout version (250 in the
        # ZH-CH sample), so this keeps well under 1% of the rows.
        chars = chars[chars["question_image_version"].astype(str) == wanted]
    parsed = chars["page"].map(_multipleye_question_parts)
    chars = chars[parsed.notna()].copy()
    if chars.empty:
        return pd.DataFrame()
    parsed = parsed[parsed.notna()]
    chars["_question_id"] = [int(value[0]) for value in parsed]
    chars["_aoi_block"] = [str(value[1]) for value in parsed]

    order = _multipleye_question_block_order(chars)
    sort_by = [
        column
        for column in ("line_idx", "char_idx_in_line", "char_idx")
        if column in chars.columns
    ]
    if sort_by:
        chars = chars.sort_values(_QUESTION_KEY + sort_by, kind="stable")
    # One aggregation for the whole stimulus/version rather than one per block:
    # the groups are ~10 rows each, so per-call pandas overhead dominated.
    out = _multipleye_char_boxes(chars, _QUESTION_KEY + ["word_idx"])
    out = out.merge(order, on=_QUESTION_KEY, how="left").sort_values(
        ["_question_id", "_block_order", "line_idx", "word_idx"], kind="stable"
    )
    per_question = out.groupby("_question_id", sort=False)
    out["word_idx"] = per_question.cumcount()
    # Dense per-screen line ids: the group codes run in the sorted order above, so
    # subtracting each question's first code rebases them to 0.
    codes = out.groupby(_QUESTION_KEY[:1] + ["_block_order", "line_idx"], sort=False)
    line_key = codes.ngroup()
    out["line_idx"] = line_key - line_key.groupby(out["_question_id"]).transform("min")
    out["page"] = [_multipleye_question_screen_id(q) for q in out["_question_id"]]
    out = out.rename(columns={"_question_id": "question_id", "_aoi_block": "aoi_block"})
    out["screen_kind"] = "question"
    out = out.drop(columns=["_block_order"]).reset_index(drop=True)
    return _multipleye_stamp_box_identity(out, stimulus)


def _stamp_multipleye_fixations(
    df: pd.DataFrame, info: dict, *, kinds: tuple[str, ...] = ("reading",)
) -> pd.DataFrame:
    """Filter to the wanted screen kinds and stamp identity parsed from a filename.

    ``info`` is a ``_multipleye_parse_filename`` dict; ``kinds`` selects which
    screens survive (``reading`` and/or ``question`` — see
    :func:`_multipleye_screen_kind`; every other screen is always dropped). Rows
    keep the corpus's own ``page`` as the ``screen_id`` and gain ``screen_kind``;
    ``trial_id`` is the stimulus, since one reading of a stimulus is one trial.
    ``name == 'fixation'`` filtering applies to the ``scanpaths`` export, which
    tags each row. Returns an empty frame if nothing remains (or the upload has no
    ``page`` column at all). Shared by the directory loader (one file) and the
    upload recipe (one source_file group)."""
    if "page" not in df.columns:
        return df.iloc[0:0]
    screen_kind = df["page"].map(_multipleye_screen_kind)
    df = df[screen_kind.isin(kinds)]
    if "name" in df.columns:  # scanpaths tag each row; keep fixations only
        df = df[df["name"] == "fixation"]
    if df.empty:
        return df
    df = df.copy()
    df["screen_kind"] = screen_kind.loc[df.index]
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
    df["trial_id"] = stimulus
    # The presentation monitor, so `multipart.screen_canvas_size` reports the real
    # screen for every screen instead of inferring one from the data's extent.
    df["canvas_width"] = MULTIPLEYE_MONITOR[0]
    df["canvas_height"] = MULTIPLEYE_MONITOR[1]
    return df


def _multipleye_fixations(
    root: Path,
    source: str,
    sessions: Iterable[str] | None,
    stimuli: Iterable[str] | None,
    *,
    include_question_screens: bool = True,
) -> pd.DataFrame:
    """Concatenated per-trial fixations, tagged with parsed identity columns.

    Identity (participant / session / stimulus → ``trial_id``, plus the screen)
    comes from the folder + file name. Reading pages come from ``source``
    (the word-tagged ``scanpaths/`` by preference; ``fixations/`` works too, with
    no ``word_idx``). **Question screens always come from ``fixations/``** — the
    ``scanpaths/`` export is pre-filtered to reading pages — so a default load
    keeps its word-tagged reading fixations and still shows the question screens;
    ``screen_kind`` marks the resulting mixed provenance."""
    base = root / source
    suffix = "scanpath" if source == "scanpaths" else "fixation"
    session_filter = None if sessions is None else {str(s) for s in sessions}
    stim_filter = None if stimuli is None else {str(s) for s in stimuli}
    raw_base = root / "fixations"
    want_questions = include_question_screens and (
        source == "fixations" or raw_base.is_dir()
    )
    kinds = (
        ("reading", "question")
        if source == "fixations" and want_questions
        else ("reading",)
    )

    def _wanted(path: Path) -> dict | None:
        info = _multipleye_parse_filename(path.stem)
        if info is None:
            return None
        if stim_filter is not None and info["stimulus"] not in stim_filter:
            return None
        return info

    frames = []
    for session_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        if session_filter is not None and session_dir.name not in session_filter:
            continue
        for path in sorted(session_dir.glob(f"*_{suffix}.csv")):
            info = _wanted(path)
            if info is None:
                continue
            stamped = _stamp_multipleye_fixations(pd.read_csv(path), info, kinds=kinds)
            if not stamped.empty:
                frames.append(stamped)
    if not frames:
        raise FileNotFoundError(
            f"No MultiplEYE {source} files matched under {base} "
            f"(sessions={sessions}, stimuli={stimuli})."
        )
    if want_questions and source != "fixations":
        for session_dir in sorted(p for p in raw_base.iterdir() if p.is_dir()):
            if session_filter is not None and session_dir.name not in session_filter:
                continue
            for path in sorted(session_dir.glob("*_fixation.csv")):
                info = _wanted(path)
                if info is None:
                    continue
                stamped = _stamp_multipleye_fixations(
                    pd.read_csv(path), info, kinds=("question",)
                )
                if not stamped.empty:
                    frames.append(stamped)
    return pd.concat(frames, ignore_index=True, sort=False)


# --- Screen ordering: the reader's own onsets, never the screen name ----------


def _multipleye_screen_order(
    fixations: pd.DataFrame, *, by_onset: bool
) -> pd.DataFrame:
    """One row per ``(participant_id, trial_id, page)`` with its 1-based order.

    ``by_onset`` ranks the screens by that reader's **first fixation onset**,
    which is the only correct order: reading pages are shown in page order, but
    the *question order is shuffled per reader* (``001_ZH_CH_1_ET1`` saw
    ``question_4132`` before ``question_4131``). The page-number fallback exists
    for the reading-pages-only load, where the word boxes stay stimulus-level and
    so must carry the same, reader-independent index the fixations do.

    Also returns ``_screen_onset`` — each screen's first onset, which re-zeroes
    ``onset`` into the per-screen clock (``onset`` itself stays parent-global)."""
    keys = ["participant_id", "trial_id", "page"]
    onsets = (
        fixations.assign(_onset=pd.to_numeric(fixations["onset"], errors="coerce"))
        .groupby(keys, sort=False)["_onset"]
        .min()
        .reset_index()
        .rename(columns={"_onset": "_screen_onset"})
    )
    numbers = onsets["page"].map(_multipleye_page_number)
    if not by_onset and numbers.notna().all():
        onsets["screen_index"] = numbers.astype(int)
    else:
        onsets["screen_index"] = (
            onsets.groupby(["participant_id", "trial_id"])["_screen_onset"]
            .rank(method="first")
            .astype(int)
        )
    return onsets


# Explicit schemas from the raw MultiplEYE frames to the canonical schema (no
# participant on words — stimulus-level boxes broadcast across readers). The
# corpus's own ``page`` is the ``screen_id``, so one trial keeps every screen of
# a reading in its own coordinate space (``data._copy_screen_fields`` already
# accepts all of these keys, so nothing in data.py needs plumbing for them).
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
    screen_id="page",
    screen_index="screen_index",
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
    screen_id="page",
    screen_index="screen_index",
    # `onset` stays the parent-global clock; this is it re-zeroed per screen.
    screen_timestamp="screen_timestamp_ms",
    canvas_width="canvas_width",
    canvas_height="canvas_height",
)
# When per-reader reading measures or question screens are present, the word
# boxes carry a real ``participant_id`` (per reader) and the per-reader IA_*
# measures, so they take the participant branch in ``normalize_words`` (no
# stimulus-level broadcast).
MULTIPLEYE_WORD_SCHEMA_PER_READER = dict(
    MULTIPLEYE_WORD_SCHEMA, participant="participant_id"
)


def multipleye_word_schema(words: pd.DataFrame) -> dict:
    """The word schema matching a raw MultiplEYE word frame's shape.

    Per-reader boxes (reading measures and/or question screens attached) carry a
    ``participant_id`` and must NOT be broadcast; stimulus-level boxes must."""
    return dict(
        MULTIPLEYE_WORD_SCHEMA_PER_READER
        if "participant_id" in getattr(words, "columns", ())
        else MULTIPLEYE_WORD_SCHEMA
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


def _multipleye_questions_path(root: Path) -> Path | None:
    """The comprehension-questions workbook under ``root``, or None."""
    return next(
        iter(sorted(root.glob("stimuli_*/multipleye_comprehension_questions_*.xlsx"))),
        None,
    )


def _multipleye_image_dir(root: Path) -> tuple[Path, str] | None:
    """``(stimulus-images dir, language tag)`` or None.

    The language is read from the directory name (``stimuli_images_zh_ch_1`` →
    ``zh``), never hardcoded, so other MultiplEYE languages work."""
    for d in sorted(root.glob("stimuli_*/stimuli_images_*")):
        if d.is_dir():
            parts = d.name.removeprefix("stimuli_images_").split("_")
            return d, (parts[0] if parts and parts[0] else "")
    return None


def _multipleye_question_image_dir(root: Path) -> tuple[Path, str] | None:
    """``(question-images dir, language tag)`` or None.

    Holds one ``question_images_version_<N>/`` per answer layout; the images are
    1310x991 — the same size as a page image — so the underlay origin is
    ``_MULTIPLEYE_IMAGE_ORIGIN`` for question screens too."""
    for d in sorted(root.glob("stimuli_*/question_images_*")):
        if d.is_dir():
            parts = d.name.removeprefix("question_images_").split("_")
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
    """Read the comprehension workbook and return ``{stimulus -> questions JSON}``.

    Comprehension questions are optional enrichment (a per-stimulus JSON column);
    reading the ``.xlsx`` needs the optional ``openpyxl`` dependency. If it isn't
    installed, skip the enrichment (empty map) rather than failing the whole load
    — the scanpaths/word-boxes don't depend on it."""
    try:
        frame = pd.read_excel(xlsx_path, sheet_name=0)
    except ImportError:
        return {}
    return _multipleye_questions_from_frame(frame)


def _normalize_multipleye_participant_meta(
    df: pd.DataFrame | None,
) -> pd.DataFrame | None:
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


def _multipleye_participant_meta(root: Path) -> pd.DataFrame | None:
    """Reader metadata from ``participant_data.csv`` (namespaced ``pp_*``), or None."""
    path = root / "participant_data.csv"
    return (
        _normalize_multipleye_participant_meta(pd.read_csv(path))
        if path.is_file()
        else None
    )


def _merge_multipleye_participant_meta(
    fixations: pd.DataFrame, meta: pd.DataFrame | None
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
    sessions: Iterable[str] | None,
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
    stim_boxes: pd.DataFrame,
    rm: pd.DataFrame,
    fixations: pd.DataFrame,
    question_boxes: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Reading-page boxes per reader, scoped to the screens they actually fixated.

    The stimulus-level boxes are replicated onto the ``(reader, stimulus, page)``
    triples present in that reader's fixations — an **inner** join, so a page the
    reader skipped never becomes an orphan screen for
    ``multipart.validate_matching_parts`` to reject. That reader's pre-aggregated
    reading measures merge on ``(participant, stimulus, page, word_idx)``
    (``word_idx`` restarts per page, so page MUST be in the key). Question-screen
    boxes are already per reader and are appended as they are."""
    if stim_boxes.empty:
        words = stim_boxes
    else:
        pairs = fixations[["participant_id", "stimulus", "page"]].drop_duplicates()
        words = pairs.merge(stim_boxes, on=["stimulus", "page"], how="inner")
    if not rm.empty:
        words = words.merge(
            rm, on=["participant_id", "stimulus", "page", "word_idx"], how="left"
        )
    if question_boxes is not None and not question_boxes.empty:
        words = pd.concat([words, question_boxes], ignore_index=True, sort=False)
    return words


def _multipleye_question_word_boxes(
    aoi_source, fixations: pd.DataFrame, versions: dict
) -> pd.DataFrame:
    """Per-(reader, stimulus) question-screen word boxes.

    ``aoi_source`` is either the corpus AOI directory (files are read on demand)
    or a ``{stimulus -> question-AOI frame}`` map (the upload path). Which answer
    layout a reader saw is looked up in ``versions`` by their **bare pid**, so a
    reader with no assigned version — or a stimulus with no question-AOI rows —
    contributes no boxes, and the caller drops those question screens rather than
    guessing a layout that would draw plausible boxes in the wrong places."""
    if fixations.empty or "screen_kind" not in fixations.columns:
        return pd.DataFrame()
    wanted = fixations[fixations["screen_kind"] == "question"]
    if wanted.empty:
        return pd.DataFrame()
    if not versions:
        _LOGGER.warning(
            "MultiplEYE: no answer-layout version table, so the %d question "
            "screen(s) are skipped (their AOI layout is reader-specific).",
            wanted[["participant_id", "trial_id", "page"]].drop_duplicates().shape[0],
        )
        return pd.DataFrame()

    # Two memos, because they have different granularities: the corpus assigns a
    # DISTINCT layout version to every participant, so a per-(stimulus, version)
    # box cache almost never hits — but the file it parses is per stimulus and is
    # the expensive part (~15 MB each), so that read is memoized separately.
    files: dict = {}
    cache: dict = {}
    frames = []
    for (reader, stimulus), group in wanted.groupby(
        ["participant_id", "stimulus"], sort=False
    ):
        stimulus = str(stimulus)
        version = versions.get(_multipleye_bare_pid(reader))
        key = (stimulus, version)
        if key not in cache:
            if version is None:
                # No assigned layout: don't even read the file for it.
                cache[key] = pd.DataFrame()
            else:
                if stimulus not in files:
                    files[stimulus] = _multipleye_question_aoi_frame(
                        aoi_source, stimulus
                    )
                cache[key] = _multipleye_question_boxes_from_frame(
                    files[stimulus], stimulus, version
                )
        boxes = cache[key]
        if boxes.empty:
            _LOGGER.warning(
                "MultiplEYE: no question AOI rows for reader %s on %s "
                "(layout version %s) — its question screens are skipped.",
                reader,
                stimulus,
                version,
            )
            continue
        seen = set(group["page"].astype(str))
        boxes = boxes[boxes["page"].isin(seen)].copy()
        boxes["participant_id"] = reader
        frames.append(boxes)
    return (
        pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    )


def _multipleye_question_aoi_frame(aoi_source, stimulus: str) -> pd.DataFrame | None:
    """One stimulus' question-AOI rows, from a directory or an uploaded map."""
    if isinstance(aoi_source, dict):
        return aoi_source.get(stimulus.lower())
    path = Path(aoi_source) / f"{stimulus.lower()}_aoi_questions.csv"
    return pd.read_csv(path) if path.is_file() else None


def _multipleye_drop_screens_without_boxes(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> pd.DataFrame:
    """Drop fixations on screens that have no word boxes, loudly.

    ``multipart.validate_matching_parts`` rejects a screen present in one report
    and absent from the other, so a screen we could not build boxes for (a
    question screen whose layout version is unknown, a stimulus whose AOI file
    was not uploaded) must be dropped here rather than crashing the whole load
    inside ``data.harmonize_frames``."""
    if words.empty or fixations.empty or "page" not in words.columns:
        return fixations
    keys = ["trial_id", "page"]
    if "participant_id" in words.columns:
        keys.insert(0, "participant_id")
    present = words[keys].drop_duplicates().astype(str)
    present["_has_boxes"] = True
    probe = fixations[keys].astype(str)
    merged = probe.merge(present, on=keys, how="left")
    keep = merged["_has_boxes"].notna().to_numpy(dtype=bool)
    if not keep.all():
        dropped = fixations.loc[~keep, ["trial_id", "page"]].drop_duplicates()
        _LOGGER.warning(
            "MultiplEYE: dropped %d fixation(s) on %d screen(s) with no word "
            "boxes (e.g. %s).",
            int((~keep).sum()),
            len(dropped),
            ", ".join(f"{t}/{p}" for t, p in dropped.head(3).to_numpy()),
        )
    return fixations.loc[keep]


def _multipleye_apply_screen_order(
    words: pd.DataFrame, fixations: pd.DataFrame, *, by_onset: bool
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stamp ``screen_index`` (+ the per-screen clock) on both frames.

    Ranks only the **included** screens, so the indices stay a contiguous 1..N
    once the rating / difficulty screens are gone. Per-reader word boxes take the
    reader's own ranking; stimulus-level boxes (reading pages only, no
    participant column to key on) take the page number, which is the same order
    for every reader and — crucially — the same value the fixations get, so
    ``multipart.part_catalog`` sees no conflict between the two reports."""
    order = _multipleye_screen_order(fixations, by_onset=by_onset)
    keys = ["participant_id", "trial_id", "page"]
    fixations = fixations.merge(order, on=keys, how="left")
    fixations["screen_timestamp_ms"] = (
        pd.to_numeric(fixations["onset"], errors="coerce") - fixations["_screen_onset"]
    )
    fixations = fixations.drop(columns=["_screen_onset"])
    if words.empty or "page" not in words.columns:
        return words, fixations
    if "participant_id" in words.columns:
        words = words.merge(order.drop(columns=["_screen_onset"]), on=keys, how="left")
    else:
        numbers = words["page"].map(_multipleye_page_number)
        if numbers.notna().all():
            words = words.assign(screen_index=numbers.astype(int))
    return words, fixations


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
    """Stamp the per-(stimulus, reading page) stimulus-image path onto a frame.

    ``Lit_Alchemist_4`` + ``page_3`` → ``…/lit_alchemist_id4_page_3_<lang>.png``.
    Question screens are left blank here — their image lives in a per-reader
    layout directory (:func:`_multipleye_stamp_question_image_path`)."""
    if df.empty or not {"stimulus", "page"} <= set(df.columns):
        return df
    df = df.copy()
    stim = df["stimulus"].astype(str)
    name = stim.str.rsplit("_", n=1).str[0].str.lower()
    sid = stim.str.rsplit("_", n=1).str[1]
    page = df["page"].astype(str)
    pnum = page.str.replace("page_", "", regex=False)
    df["image_path"] = (
        f"{image_dir}/" + name + "_id" + sid + "_page_" + pnum + f"_{lang}.png"
    ).where(page.str.startswith("page_"))
    # Where the (centered) image sits on the monitor — matches the coordinate
    # offset applied to the fixations/boxes, so the image aligns with the data.
    df["image_x"] = _MULTIPLEYE_IMAGE_ORIGIN[0]
    df["image_y"] = _MULTIPLEYE_IMAGE_ORIGIN[1]
    return df


def _multipleye_stamp_question_image_path(
    df: pd.DataFrame, image_dir: Path, lang: str, versions: dict
) -> pd.DataFrame:
    """Fill ``image_path`` for question screens from the reader's layout version.

    ``Lit_Alchemist_4`` + ``question_4111`` for a reader on version 71 →
    ``…/question_images_version_71/Lit_Alchemist_id4_question_04111_<lang>.png``.
    The stimulus name keeps its CamelCase here (unlike the lowercase page images)
    and the question id is zero-padded to five digits, as the corpus writes it."""
    needed = {"stimulus", "page", "participant_id"}
    if df.empty or not needed <= set(df.columns) or not versions:
        return df
    df = df.copy()
    keys = ["participant_id", "stimulus", "page"]
    triples = df.loc[
        df["page"].astype(str).str.startswith("question_"), keys
    ].drop_duplicates()
    if triples.empty:
        return df
    resolved = []
    for reader, stimulus, page in triples.astype(str).to_numpy():
        version = versions.get(_multipleye_bare_pid(reader))
        parts = _multipleye_question_parts(page)
        if version is None or parts is None:
            continue
        name, _, sid = str(stimulus).rpartition("_")
        resolved.append(
            {
                "participant_id": reader,
                "stimulus": stimulus,
                "page": page,
                "_question_image": (
                    f"{image_dir}/question_images_version_{int(version)}/"
                    f"{name}_id{sid}_question_{parts[0]:05d}_{lang}.png"
                ),
            }
        )
    if "image_path" not in df.columns:
        df["image_path"] = pd.NA
    if resolved:
        lookup = pd.DataFrame(resolved)
        probe = df[keys].astype(str).merge(lookup, on=keys, how="left")
        found = probe["_question_image"].notna().to_numpy()
        df.loc[found, "image_path"] = probe.loc[found, "_question_image"].to_numpy()
    df["image_x"] = _MULTIPLEYE_IMAGE_ORIGIN[0]
    df["image_y"] = _MULTIPLEYE_IMAGE_ORIGIN[1]
    return df


def _multipleye_stamp_font(
    df: pd.DataFrame, font_px: float | None, family: str | None
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
) -> tuple[tuple[str, ...], tuple[str, ...]]:
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
    sessions: Iterable[str] | None = None,
    stimuli: Iterable[str] | None = None,
    fixation_source: str = "scanpaths",
    attach_reading_measures: bool = True,
    include_question_screens: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) MultiplEYE ``(words, fixations)`` frames.

    Same inputs as :func:`load_multipleye`, but returns the frames *before*
    schema normalization — for callers that run their own auto-detection /
    column mapping (e.g. the Streamlit app's MultiplEYE data source). Fixations
    carry parsed ``participant_id`` (the session), ``trial_id`` (the stimulus),
    the screen (``page`` + ``screen_index`` + ``screen_kind``), pixel
    ``location_x/y``, the trial-level facets (``genre`` / ``session`` /
    ``is_practice`` / ``trial_num``), and any reader metadata
    (``pp_*`` from participant_data.csv), comprehension questions, and stimulus
    image path that the corpus ships.

    Word boxes are stimulus-level (no participant → broadcast) *unless*
    ``reading_measures/`` exists and ``attach_reading_measures`` is on, or
    question screens are included — in which case the boxes are emitted **per
    reader**, with the corpus's pre-aggregated reading measures merged in as
    ``IA_*`` columns (the app then prefers them over recomputed metrics) and the
    reader's own question-screen boxes appended. ``include_question_screens``
    (on by default) opts out of the comprehension-question screens; they are
    also skipped when the answer-layout version table is missing, since guessing
    a layout would draw entirely plausible boxes in the wrong places. Use
    :func:`load_multipleye` for normalized frames.
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

    fixations = _multipleye_fixations(
        root,
        fixation_source,
        sessions,
        stimuli,
        include_question_screens=include_question_screens,
    )
    # Reader metadata (age/gender/languages…) merged onto every fixation row.
    fixations = _merge_multipleye_participant_meta(
        fixations, _multipleye_participant_meta(root)
    )

    aoi_dir = _multipleye_aoi_dir(root)
    stim_boxes = _multipleye_word_boxes(aoi_dir, fixations["stimulus"].unique())
    versions = _multipleye_read_layout_versions(root)
    question_boxes = (
        _multipleye_question_word_boxes(aoi_dir, fixations, versions)
        if include_question_screens
        else pd.DataFrame()
    )
    # Pre-aggregated reading measures → per-reader word boxes (skips the
    # stimulus-level broadcast). Only when the corpus ships reading_measures/.
    # Question screens force the same shape: their layout is reader-specific.
    per_reader = attach_reading_measures and (root / "reading_measures").is_dir()
    if per_reader or not question_boxes.empty:
        rm = pd.DataFrame()
        if per_reader:
            namemap = {s.rsplit("_", 1)[0]: s for s in fixations["stimulus"].unique()}
            rm = _multipleye_read_reading_measures(root, sessions, namemap)
        words = _multipleye_words_per_reader(stim_boxes, rm, fixations, question_boxes)
    else:
        words = stim_boxes

    # Screens we could not build boxes for would be orphans in harmonize_frames,
    # so drop them (loudly) before the screen order is ranked — that keeps the
    # index a contiguous 1..N over exactly the screens that survive.
    fixations = _multipleye_drop_screens_without_boxes(words, fixations)
    words, fixations = _multipleye_apply_screen_order(
        words, fixations, by_onset="participant_id" in words.columns
    )

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
    question_image = _multipleye_question_image_dir(root)
    if question_image is not None:
        image_dir, lang = question_image
        words = _multipleye_stamp_question_image_path(words, image_dir, lang, versions)
        fixations = _multipleye_stamp_question_image_path(
            fixations, image_dir, lang, versions
        )
    # Reading typeface (size + family) from the stimulus config → the app renders
    # the text true-to-scale at the exact font the images were drawn with.
    font_px, font_family = _multipleye_font_config(root)
    words = _multipleye_stamp_font(words, font_px, font_family)
    fixations = _multipleye_stamp_font(fixations, font_px, font_family)
    return words, fixations


def load_multipleye(
    root,
    *,
    sessions: Iterable[str] | None = None,
    stimuli: Iterable[str] | None = None,
    fixation_source: str = "scanpaths",
    include_question_screens: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load MultiplEYE as normalized ``(words, fixations)`` frames, ready to plot.

    ``root`` is a MultiplEYE session set (e.g.
    ``data/MultiplEYE_ZH_CH_Zurich_1_2025``). Narrow the load with ``sessions``
    (full session ids, e.g. ``["001_ZH_CH_1_ET1"]``) and/or ``stimuli`` (e.g.
    ``["Lit_Alchemist_4"]``).

    Participants are session ids (ET1 and ET2 read disjoint stimuli, so each is
    a distinct reader). A trial is **one reading of one stimulus**
    (``trial_id == text_id == "Lit_Alchemist_4"``), and its screens — the reading
    pages ``page_1…page_N`` plus the comprehension-question screens — are
    ``screen_id`` values in presentation order (``screen_index``, ranked from
    that reader's own fixation onsets, since the question order is shuffled per
    reader). ``screen_kind`` is ``reading`` or ``question``::

        words, fixations = load_multipleye(
            "data/MultiplEYE_ZH_CH_Zurich_1_2025", stimuli=["Lit_Alchemist_4"]
        )
        fig = scanpath_studio.plot_scanpath(
            words, fixations, screen="page_1", canvas_size=MULTIPLEYE_MONITOR
        )

    ``fixation_source`` is ``"scanpaths"`` (default; fixations pre-tagged with
    page + word index) or ``"fixations"`` (raw, no word linkage); question
    screens always come from ``fixations/``, which is the only export that keeps
    them. ``include_question_screens=False`` loads the reading pages alone.
    """
    words_raw, fixations_raw = multipleye_raw_frames(
        root,
        sessions=sessions,
        stimuli=stimuli,
        fixation_source=fixation_source,
        include_question_screens=include_question_screens,
    )

    from . import api

    return api.load_scanpath_data(
        words=words_raw,
        fixations=fixations_raw,
        word_schema=multipleye_word_schema(words_raw),
        fix_schema=dict(
            MULTIPLEYE_FIX_SCHEMA,
            word_id="word_idx" if "word_idx" in fixations_raw.columns else None,
        ),
    )


MULTIPLEYE_DATA_DIR_ENV = "MULTIPLEYE_DATA_DIR"
MULTIPLEYE_BUNDLE_FIXATION_SOURCE = "scanpaths"


def multipleye_bundle_dir() -> Path | None:
    """Resolve the configured MultiplEYE raw-export root, if any."""
    raw = os.environ.get(MULTIPLEYE_DATA_DIR_ENV, "").strip()
    if not raw:
        from .constants import MULTIPLEYE_BUNDLE_DEFAULT_DIR

        raw = MULTIPLEYE_BUNDLE_DEFAULT_DIR.strip()
    return Path(raw) if raw else None


def _resolve_multipleye_session(
    root: Path, participant: str, fixation_source: str
) -> str | None:
    """Match a case-insensitive deep-link participant to its session id."""
    sessions, _ = multipleye_inventory(root, fixation_source=fixation_source)
    wanted = participant.strip().lower()
    return next((session for session in sessions if session.lower() == wanted), None)


def load_multipleye_server_bundle(
    participant: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the configured raw MultiplEYE export for the app review source.

    A participant narrows the load to its case-insensitively matched session;
    omitting it loads the full export. Missing roots return empty frames, while
    malformed exports and unknown named sessions raise a descriptive error for
    the UI boundary to display.
    """
    root = multipleye_bundle_dir()
    if root is None or not root.is_dir():
        return pd.DataFrame(), pd.DataFrame()
    sessions = None
    if participant:
        session = _resolve_multipleye_session(
            root, participant, MULTIPLEYE_BUNDLE_FIXATION_SOURCE
        )
        if session is None:
            raise ValueError(
                f"No MultiplEYE session matching participant {participant!r} "
                f"under {root / MULTIPLEYE_BUNDLE_FIXATION_SOURCE}."
            )
        sessions = [session]
    return multipleye_raw_frames(
        root,
        sessions=sessions,
        stimuli=None,
        fixation_source=MULTIPLEYE_BUNDLE_FIXATION_SOURCE,
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


def _multipleye_is_versions_upload(stem: str, group: pd.DataFrame) -> bool:
    """Whether an uploaded file group is the answer-layout version table."""
    if "stimulus_order_versions" in str(stem).lower():
        return True
    return "version_number" in group.columns and "page" not in group.columns


def _multipleye_fixations_from_frame(
    fixations_df: pd.DataFrame, *, include_question_screens: bool = True
) -> pd.DataFrame:
    """Identity-stamped fixations from a concatenated UPLOAD frame.

    Rows must carry a ``source_file`` column (the uploaded filename stem). Each
    file group is parsed with ``_multipleye_parse_filename``; groups whose name
    isn't MultiplEYE-shaped are skipped. When both a ``_scanpath`` and a
    ``_fixation`` file are uploaded for the same (session, trial), the **reading**
    pages come from the scanpath one (it carries word indices) and the **question**
    screens from the fixation one — mirroring the directory loader, whose
    ``scanpaths/`` export is pre-filtered to reading pages. Returns an empty frame
    if nothing matched (the wizard then surfaces a problem rather than
    crashing)."""
    from .data import SOURCE_FILE_COLUMN

    if SOURCE_FILE_COLUMN not in fixations_df.columns:
        return pd.DataFrame()
    groups: dict = {}
    for stem, group in fixations_df.groupby(SOURCE_FILE_COLUMN, sort=False):
        info = _multipleye_parse_filename(str(stem))
        if info is None:
            continue
        key = (info["session"], info["trial_num"], info["stimulus"])
        groups.setdefault(key, {})[info["kind"]] = (info, group)

    frames = []
    for by_kind in groups.values():
        reading = by_kind.get("scanpath") or by_kind.get("fixation")
        # Question screens only ever survive in the raw fixation export.
        question = by_kind.get("fixation") if include_question_screens else None
        for source, kinds in ((reading, ("reading",)), (question, ("question",))):
            if source is None:
                continue
            stamped = _stamp_multipleye_fixations(source[1], source[0], kinds=kinds)
            if not stamped.empty:
                frames.append(stamped)
    return (
        pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    )


def multipleye_frames_from_uploads(
    fixations_df: pd.DataFrame,
    aoi_df: pd.DataFrame | None = None,
    *,
    questions_df: pd.DataFrame | None = None,
    participant_meta_df: pd.DataFrame | None = None,
    versions_df: pd.DataFrame | None = None,
    include_question_screens: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw MultiplEYE ``(words, fixations)`` frames from UPLOADED files.

    The browser-upload analogue of :func:`multipleye_raw_frames`: identity is
    parsed from each row's ``source_file`` (the uploaded filename stem) instead of
    the directory tree, since browser uploads drop folders. ``fixations_df`` is
    the concatenated scanpath/fixation CSVs; ``aoi_df`` the concatenated AOI CSVs
    (optional — without it you get fixations and no word boxes), which may mix the
    per-stimulus ``*_aoi.csv`` reading boxes, the ``*_aoi_questions.csv``
    question boxes, and ``stimulus_order_versions_*.csv`` — each is routed by its
    filename. AOI filenames are lowercase (``lit_alchemist_4_aoi``) while scanpath
    filenames are CamelCase, so each AOI group's stimulus is relabeled to the
    CamelCase name seen in the fixations before building ``trial_id`` — otherwise
    the stimulus-words broadcast (which inner-joins on ``trial_id``) drops every
    box.

    **Question screens need both** the ``*_aoi_questions.csv`` of their stimulus
    **and** the versions table (as ``versions_df`` or inside ``aoi_df``): which
    answer layout a reader saw is otherwise unknowable, and picking an arbitrary
    one would draw entirely plausible boxes in the wrong places. Without it the
    question screens are dropped with a warning. ``questions_df`` (the
    comprehension workbook) and ``participant_meta_df`` (participant_data.csv) are
    merged when provided. Reading measures + stimulus images need the directory
    tree, so they are not available on this path. Feed the result through
    :func:`load_multipleye_uploads`."""
    from .data import SOURCE_FILE_COLUMN

    fixations = _multipleye_fixations_from_frame(
        fixations_df, include_question_screens=include_question_screens
    )
    fixations = _merge_multipleye_participant_meta(
        fixations, _normalize_multipleye_participant_meta(participant_meta_df)
    )
    qmap = (
        _multipleye_questions_from_frame(questions_df)
        if questions_df is not None
        else {}
    )
    fixations = _multipleye_stamp_questions(fixations, qmap)

    has_aoi = aoi_df is not None and not getattr(aoi_df, "empty", True)
    if fixations.empty or not has_aoi or SOURCE_FILE_COLUMN not in aoi_df.columns:
        if not fixations.empty:
            fixations = _multipleye_apply_screen_order(
                pd.DataFrame(), fixations, by_onset=True
            )[1]
        return pd.DataFrame(), fixations

    # CamelCase canonical per lowercased stimulus, taken from the fixations.
    casemap: dict = {}
    for stim in fixations["stimulus"].unique():
        casemap.setdefault(str(stim).lower(), str(stim))

    frames = []
    question_aoi: dict = {}
    versions = _multipleye_layout_versions(versions_df)
    for stem, group in aoi_df.groupby(SOURCE_FILE_COLUMN, sort=False):
        if _multipleye_is_versions_upload(str(stem), group):
            versions = versions or _multipleye_layout_versions(group)
            continue
        lower_stim = _multipleye_aoi_stimulus_from_source(str(stem))
        canonical = casemap.get(lower_stim.lower(), lower_stim)
        if str(stem).lower().endswith("_aoi_questions"):
            question_aoi[canonical.lower()] = group
            continue
        boxes = _multipleye_word_boxes_from_frame(group, canonical)
        if not boxes.empty:
            frames.append(boxes)
    words = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    question_boxes = (
        _multipleye_question_word_boxes(question_aoi, fixations, versions)
        if include_question_screens and question_aoi
        else pd.DataFrame()
    )
    if not question_boxes.empty:
        words = _multipleye_words_per_reader(
            words, pd.DataFrame(), fixations, question_boxes
        )
    words = _multipleye_stamp_questions(words, qmap)
    fixations = _multipleye_drop_screens_without_boxes(words, fixations)
    words, fixations = _multipleye_apply_screen_order(
        words, fixations, by_onset="participant_id" in words.columns
    )
    return words, fixations


def load_multipleye_uploads(
    fixations_df: pd.DataFrame,
    aoi_df: pd.DataFrame | None = None,
    *,
    questions_df: pd.DataFrame | None = None,
    participant_meta_df: pd.DataFrame | None = None,
    versions_df: pd.DataFrame | None = None,
    include_question_screens: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalized ``(words, fixations)`` from UPLOADED MultiplEYE files.

    Like :func:`load_multipleye`, but for in-memory uploaded frames (identity from
    each row's ``source_file``; see :func:`multipleye_frames_from_uploads`).
    ``words`` is an empty frame when no AOI files were uploaded; the fixations then
    plot at their own ``location_x/y`` with no word boxes. Optional
    ``questions_df`` / ``participant_meta_df`` add the comprehension panel + reader
    metadata, and ``versions_df`` (or a versions table inside ``aoi_df``) unlocks
    the question screens. Raises ``ValueError`` (via
    :func:`api.load_scanpath_data`) if the fixations frame has no
    MultiplEYE-shaped filenames."""
    words_raw, fix_raw = multipleye_frames_from_uploads(
        fixations_df,
        aoi_df,
        questions_df=questions_df,
        participant_meta_df=participant_meta_df,
        versions_df=versions_df,
        include_question_screens=include_question_screens,
    )

    from . import api

    return api.load_scanpath_data(
        words=words_raw if not words_raw.empty else None,
        fixations=fix_raw if not fix_raw.empty else None,
        word_schema=multipleye_word_schema(words_raw) if not words_raw.empty else None,
        fix_schema=(
            dict(
                MULTIPLEYE_FIX_SCHEMA,
                word_id="word_idx" if "word_idx" in fix_raw.columns else None,
            )
            if not fix_raw.empty
            else None
        ),
    )
