"""Loaders for public eye-tracking-while-reading corpora.

PoTeC (Potsdam Textbook Corpus, Jakobi et al. 2024,
https://github.com/DiLi-Lab/PoTeC) — a German corpus of 75 readers × 12
textbook texts — and OneStop Eye Movements (:func:`load_onestop`). PoTeC
exercises the two dataset shapes the generic pipeline supports:

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
    fig = scanpath_studio.plot_scanpath(words, fixations, participant="0", trial="0_b0")
"""

from __future__ import annotations

import contextlib
import http.client
import io
import logging
import shutil
import ssl
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import truststore

from . import progress

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

#: One OSF file version, pinned. ``osf.io/download/<id>`` with no version
#: serves whatever was uploaded last, and PoTeC's own files have been replaced
#: several times (the scanpaths archive is at version 5), so an unpinned
#: download could hand two users two corpora under one name — and the dataset
#: table's published figures would describe neither. A pin is the file's
#: version *and* its size in bytes, which the download is checked against.
_OSF_DOWNLOAD_URL = "https://osf.io/download/{resource}/?version={version}"


@dataclass(frozen=True)
class OsfFile:
    """One pinned OSF file: its storage id, version and size in bytes."""

    resource: str
    version: int
    size: int

    @property
    def url(self) -> str:
        return _OSF_DOWNLOAD_URL.format(resource=self.resource, version=self.version)


def _check_download_size(got: int, pin: OsfFile, detail: str) -> None:
    """Refuse a download that is not the pinned file."""
    if got != pin.size:
        raise OSError(
            f"{detail}: OSF sent a different file ({got:,} bytes, expected "
            f"{pin.size:,}). Try again later."
        )


# OSF storage ids from the PoTeC repo's download_data_files.py, each pinned to
# one version.
_POTEC_OSF_RESOURCES = {
    "scanpaths": OsfFile("thgv2", 5, 9_796_046),
    "fixations": OsfFile("53zwb", 2, 6_456_542),
    "reading_measures": OsfFile("g5jds", 6, 3_326_244),
}
#: The AOI files come from the PoTeC repo itself — pinned to a commit,
#: not ``main``, for the same reason as the OSF versions above.
_POTEC_REPO_COMMIT = "46247ca2aea5876311acf6b59338880d0bf5449d"
_POTEC_RAW_URL = (
    f"https://raw.githubusercontent.com/DiLi-Lab/PoTeC/{_POTEC_REPO_COMMIT}/{{path}}"
)


def _read_potec_tsv(path) -> pd.DataFrame:
    return pd.read_csv(
        path, sep="\t", keep_default_na=False, na_values=_POTEC_NA_VALUES
    )


#: Download in reads of at most this size, reporting bytes after each — the
#: progress the card shows, and the checkpoint a Cancel stops at. Each is a
#: `read1`, which returns whatever has arrived: a `read` would wait for the
#: whole MiB, so on a 100 KB/s line Stop would take ~10 s to act.
_DOWNLOAD_CHUNK = 1 << 20
#: Seconds a download may wait on the network — to connect, or for its next
#: bytes — before giving up. Without it a stalled connection would block its
#: read forever, and Stop, which acts between reads, never could; the timeout
#: surfaces as an `OSError`, which both ⬇ Download buttons already report.
_DOWNLOAD_TIMEOUT_S = 60


def _content_length(response) -> int | None:
    value = response.headers.get("Content-Length")
    return int(value) if value and str(value).isdigit() else None


def _read_body(response, write: Callable[[bytes], object], *, detail: str) -> None:
    """Hand ``response``'s body to ``write`` as it arrives, with progress.

    Only a body that arrives whole returns. `read1` returns ``b""`` on
    an early EOF — a server, proxy or load balancer closing the connection
    mid-body — exactly as at the real end, so a body shorter than its
    ``Content-Length`` is a `ConnectionError`; so is a chunked body cut short,
    which `http.client` raises as an `IncompleteRead` (an `HTTPException`, not
    an `OSError`). Both ⬇ Download buttons report an `OSError`, and a caller
    must never commit what was read.
    """
    total = _content_length(response)
    done = 0
    try:
        while chunk := response.read1(_DOWNLOAD_CHUNK):
            write(chunk)
            done += len(chunk)
            progress.report(done, total, unit="bytes", detail=detail)
    except http.client.HTTPException as exc:
        raise ConnectionError(
            f"the download stopped after {done:,} bytes; try again"
        ) from exc
    if total is not None and done < total:
        raise ConnectionError(
            f"the download stopped at {done:,} of {total:,} bytes; try again"
        )


def _open_url(url: str):
    """Open ``url`` for a download, trusting what the operating system trusts.

    Python's own `ssl` defaults read OpenSSL's CA list, which a python.org
    install on macOS ships empty until *Install Certificates.command* is run,
    and which never holds the root a TLS-inspecting campus or company proxy
    re-signs with. Either way every download would fail with
    ``CERTIFICATE_VERIFY_FAILED``. `truststore` verifies against the macOS
    Keychain / Windows certificate store / the system bundle instead, as the
    browser does.
    """
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_S, context=context)


def _fetch_bytes(url: str, *, detail: str) -> bytes:
    """``url``'s body, read as it arrives with progress — all of it, or
    a `ConnectionError` (`_read_body`)."""
    with _open_url(url) as response:
        buffer = io.BytesIO()
        _read_body(response, buffer.write, detail=detail)
        return buffer.getvalue()


def _fetch_to_file(url: str, dest: Path, *, detail: str) -> None:
    """Stream ``url`` into ``dest`` through a ``.part`` file.

    The ``.part`` → final rename keeps an interrupted fetch from passing for a
    complete file, and it happens only once the whole body has arrived
    (`_read_body`); a cancel (or any failure) deletes the partial file — and a
    cleanup that fails in turn never masks the error that caused it.
    """
    tmp = dest.with_name(dest.name + ".part")
    try:
        with (
            _open_url(url) as response,
            tmp.open("wb") as out,
        ):
            _read_body(response, out.write, detail=detail)
        tmp.replace(dest)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise


def download_potec(root, *, fixation_source: str = "scanpaths") -> Path:
    """Download the PoTeC files :func:`load_potec` needs into ``root``.

    Fetches the per-trial eye-tracking archive (~10 MB zip) from PoTeC's OSF
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
        pin = _POTEC_OSF_RESOURCES[fixation_source]
        print(f"Downloading PoTeC {fixation_source} from {pin.url} …")
        detail = f"PoTeC {fixation_source} archive"
        payload = _fetch_bytes(pin.url, detail=detail)
        _check_download_size(len(payload), pin, detail)
        target = root / "eyetracking_data"
        target.mkdir(parents=True, exist_ok=True)
        # Unpack into a staging folder and rename it into place only
        # when complete. A cancel mid-unpack would otherwise leave a partial
        # `scanpaths/` that `potec_present`'s "any .tsv" check accepts.
        staging = target / f".{fixation_source}.part"
        shutil.rmtree(staging, ignore_errors=True)
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [
                    m
                    for m in archive.namelist()
                    # The OSF zips carry macOS resource-fork cruft; keep only the
                    # real per-trial TSVs.
                    if m.startswith(f"{fixation_source}/") and m.endswith(".tsv")
                ]
                if not members:
                    # Say what is wrong, not that the staging folder is missing.
                    raise ValueError(
                        f"The PoTeC archive from {pin.url} holds no "
                        f"{fixation_source}/*.tsv files; its layout may have changed."
                    )
                for index, member in enumerate(members, start=1):
                    archive.extract(member, staging)
                    progress.report(
                        index,
                        len(members),
                        unit="files",
                        detail="Unpacking the archive",
                    )
            (staging / fixation_source).replace(eyetracking_dir)
        except zipfile.BadZipFile as exc:
            # A damaged archive — opened or extracted — is a data error
            # both ⬇ Download buttons report, not a raw traceback.
            raise ValueError(
                "The downloaded PoTeC archive is damaged; download it again."
            ) from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

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
            _fetch_to_file(url, dest, detail=f"AOI file {rel.rsplit('/', 1)[-1]}")
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
    # Gather the files first, so the card can say "312 of 900 files".
    jobs: list[tuple[Path, pd.DataFrame]] = []
    for text_id in texts:
        char_boxes = _read_potec_ias(root, text_id)
        char_x = (char_boxes["start_x"] + char_boxes["end_x"]) / 2.0
        char_y = (char_boxes["start_y"] + char_boxes["end_y"]) / 2.0
        # A box with no AOI index places nothing: the merge below would match
        # it to every fixation with none (pandas joins NaN to NaN).
        centers = (
            pd.DataFrame({"aoi": char_boxes["aoi"], "x": char_x, "y": char_y})
            .dropna(subset=["aoi"])
            .drop_duplicates("aoi")
        )
        for path in sorted((base / source).glob(f"reader*_{text_id}_{suffix}.tsv")):
            reader_id = path.stem.removeprefix("reader").split("_")[0]
            if reader_set is not None and reader_id not in reader_set:
                continue
            jobs.append((path, centers))
    # "0 of N" before the first file, so a gated card is armed from the
    # start — a report only after each file would hide the first one.
    progress.report(0, len(jobs), unit="files")
    frames = []
    for index, (path, centers) in enumerate(jobs, start=1):
        fixations = _read_potec_tsv(path)
        frames.append(fixations.merge(centers, on="aoi", how="left"))
        progress.report(index, len(jobs), unit="files")
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
# the app's PoTeC data source, which declares them over its auto-detection.
#
# A trial is one reader's reading of one text, so the fixations' Trial ID is
# the composite ``reader_id`` + ``text_id`` (``"0_b0"``): the text name alone
# repeats across all 75 readers. The word boxes stay keyed by text, and each
# reading finds its text's boxes through the Text ID both tables map.
POTEC_WORD_SCHEMA = dict(
    participant=None,
    trial="text_id",
    text_id="text_id",
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
    trial=["reader_id", "text_id"],
    text_id="text_id",
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
    root: str | Path,
    *,
    readers: Iterable | None = None,
    texts: Iterable[str] | None = None,
    download: bool = False,
    names: str = "source",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load PoTeC as normalized ``(words, fixations)`` frames, ready to plot.

    A participant is a PoTeC reader id, as a string. A trial is one reader's reading of
    one text, ``<reader>_<text>`` (``"0_b0"``), and its ``text_id`` is the text:
    ``b0``–``b5`` are biology, ``p0``–``p5`` physics. The full corpus is 75 readers × 12
    texts = 900 trials.

    PoTeC's monitor was 1680×1050 (DELL P2210, 60 Hz). Pass that as ``canvas_size`` to
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath] for true-to-scale rendering.

    Args:
        root: A clone of the PoTeC repository with its eye-tracking data downloaded, or
            any folder to download into.
        readers: Load only these readers (``[0, 1]``).
        texts: Load only these texts (``["b0", "p3"]``).
        download: Fetch the files the load needs into ``root`` on first use, about 10
            MB.
        names: ``"source"`` for PoTeC's own column names, ``"canonical"`` for the
            internal ones (see `api.load_scanpath_data`).

    Returns:
        The normalized ``(words, fixations)`` frames.

    Examples:
        ```python
        import scanpath_studio as sps

        words, fixations = sps.load_potec("data/PoTeC", readers=[0], texts=["b0"])
        fig = sps.plot_scanpath(words, fixations, "0", "0_b0", canvas_size=(1680, 1050))
        ```
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
        names=names,
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
# Distinct from the env-var "OneStop (local export)" source
# (``data.load_onestop_server_bundle``), which serves a lacclab export via
# ``$ONESTOP_DATA_DIR`` and its per-pid shards for review-app deep links.
# ---------------------------------------------------------------------------

#: Every OneStop report is at OSF version 1 (2025-05-28); id → size in bytes,
#: the pin `download_onestop` checks against.
_ONESTOP_OSF_VERSION = 1
_ONESTOP_OSF_SIZES = {
    # all-regimes full release, interest areas
    "u7f9b": 8_287_933,
    "zn473": 23_885_174,
    "zhywq": 397_501_066,
    "tcv9h": 43_745_513,
    "q3shp": 130_794_114,
    "3j8av": 151_191_442,
    "t6n8v": 12_472_761,
    # all-regimes full release, fixations
    "uwz2e": 17_724_147,
    "7a3md": 41_597_351,
    "tbxdc": 597_284_698,
    "cmx6k": 64_566_806,
    "ax4md": 185_658_405,
    "fg7se": 207_300_032,
    "e76vz": 25_763_786,
    # per-regime Paragraph reports
    "xkgfz": 177_291_322,
    "ne4az": 288_349_184,
    "yxzte": 165_756_770,
    "bznfk": 245_787_943,
    "dwfk4": 28_875_267,
    "83ctd": 36_529_359,
    "ygjup": 25_606_136,
    "paqn8": 26_657_407,
}

# The seven trial parts (interest periods), in presentation order. Each maps to
# one interest-area + one fixation OSF report in the ``onestop-full`` release
# (all-regimes). Paragraph is the reading passage; the others are the surrounding
# screens (title, the pre/post question, its four answers, the correctness
# feedback) — except QA, which is not a screen: it is the Questions and Answers
# interest periods taken together (the corpus gives its page as "3+4"), so its
# fixations are theirs again. All share the Paragraph report schema
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

# What makes a trial belong to a regime, as the corpus records it on
# every report — ``(question_preview, repeated_reading_trial)``. The per-regime
# Paragraph files are exactly these slices (checked against the OSF ordinary
# file: every row is ``(False, False)``), and the all-regimes reports of the
# other parts carry the same two columns, so they are cut to the regime by the
# same rule instead of handing every regime's trials to each one.
_ONESTOP_REGIME_FLAGS: dict[str, tuple[bool, bool]] = {
    "ordinary": (False, False),
    "information_seeking": (True, False),
    "repeated": (False, True),
    "information_seeking_repeated": (True, True),
}
_ONESTOP_REGIME_COLUMNS: tuple[str, ...] = (
    "question_preview",
    "repeated_reading_trial",
)


def onestop_regime_parts(regime: str) -> list[str]:
    """Every screen a reader in ``regime`` saw, in presentation order.

    The parts other than QA, and of those the question-preview screen only for
    the information-seeking regimes — its report holds no trial of the others,
    so loading it there would download a file to keep none of it. QA is left
    out: it repeats the Questions and Answers screens' fixations as
    one interest period, so loading it beside them counts each fixation twice
    and shows that stretch of the trial as a further screen. ``parts=["QA"]``
    still loads it on request.
    """
    if regime not in _ONESTOP_REGIME_FLAGS:
        raise ValueError(
            f"regime must be one of {sorted(_ONESTOP_REGIME_FLAGS)}, got {regime!r}"
        )
    preview, _ = _ONESTOP_REGIME_FLAGS[regime]
    return [
        p for p in _ONESTOP_PARTS if p != "QA" and (preview or p != "Question_Preview")
    ]


def _keep_onestop_regime(frame: pd.DataFrame, regime: str) -> pd.DataFrame:
    """The rows of an all-regimes report that belong to ``regime``.

    A frame without the two flag columns is returned untouched: there is
    nothing to tell its regimes apart by.
    """
    from . import data

    if not set(_ONESTOP_REGIME_COLUMNS) <= set(frame.columns):
        return frame
    preview, repeated = _ONESTOP_REGIME_FLAGS[regime]
    mask = (data.coerce_flag(frame["question_preview"]) == preview) & (
        data.coerce_flag(frame["repeated_reading_trial"]) == repeated
    )
    return frame.loc[mask].reset_index(drop=True)


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

    Paragraph uses the ``<kind>_Paragraph_<regime>.csv.zip`` name
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


#: What the download progress calls each OneStop report kind.
_ONESTOP_REPORT_NAMES = {"ia": "interest-area", "fixations": "fixation"}


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
            pin = OsfFile(resource, _ONESTOP_OSF_VERSION, _ONESTOP_OSF_SIZES[resource])
            print(f"Downloading OneStop {regime} {part} {kind} report from {pin.url} …")
            # Write to a temp file and atomically rename into place, so an
            # interrupted write (killed process / full disk) never leaves a
            # truncated .csv.zip that `dest.is_file()` would then skip forever —
            # forcing a manual delete. The reports are large, so the window is real.
            detail = f"{part} {_ONESTOP_REPORT_NAMES[kind]} report"
            _fetch_to_file(pin.url, dest, detail=detail)
            try:
                _check_download_size(dest.stat().st_size, pin, detail)
            except OSError:
                dest.unlink(missing_ok=True)
                raise
    return root


# The public OSF release ships **no** ``unique_paragraph_id``, so the only
# text identity on its reports is ``paragraph_id`` — the paragraph's index
# *within its article*, 1..7. On its own that would make paragraph 3 of
# article 1 and paragraph 3 of article 27 the same "text" (162 paragraphs read
# as 7), and because the same id would then repeat dozens of times per reader,
# ``data._disambiguate_repeated_readings`` would rank the collisions apart into
# trial ids like ``3_r17`` — an order, not an identity.
#
# So compose the ids the corpus's own tooling writes, in the same field order
# ``update_sample_data.add_unique_ids`` uses for the bundled demo. The demo is a
# subset of this corpus, so a trial must not change identity depending on which
# of the two was opened. The level is part of the *text* id there, and stays
# one here: OneStop's Advanced and Elementary renderings of a paragraph are
# different texts, not two views of one.
_ONESTOP_PARAGRAPH_ID_PARTS: tuple[str, ...] = (
    "article_batch",
    "article_id",
    "paragraph_id",
    "difficulty_level",
)
_ONESTOP_TRIAL_ID_PARTS: tuple[str, ...] = ("participant_id", "repeated_reading_trial")
#: Every source column the composition needs — handed to the planned read so
#: narrowing it can never quietly cost us the ids.
_ONESTOP_ID_COLUMNS: tuple[str, ...] = (
    _ONESTOP_PARAGRAPH_ID_PARTS + _ONESTOP_TRIAL_ID_PARTS
)


def _compose_onestop_ids(frame: pd.DataFrame) -> pd.DataFrame:
    """Give an OneStop report the ``unique_paragraph_id`` / ``unique_trial_id``
    the public release omits.

    Each id is composed only when the frame does not already carry it: the
    lacclab export ships its own ``unique_paragraph_id`` (in its own field
    order), and that is the publisher's identity — the trial id is composed
    *under* it rather than over it. A frame missing any of the composing
    columns is returned untouched: there is nothing to invent an id from.
    """
    from . import data

    columns = set(frame.columns)
    if "unique_paragraph_id" not in columns:
        if not set(_ONESTOP_PARAGRAPH_ID_PARTS) <= columns:
            return frame
        frame = frame.copy()
        frame["unique_paragraph_id"] = _join_ids(frame, _ONESTOP_PARAGRAPH_ID_PARTS)
        columns = set(frame.columns)
    if "unique_trial_id" not in columns:
        if not set(_ONESTOP_TRIAL_ID_PARTS) <= columns:
            return frame
        frame = frame.copy()
        reading = data.coerce_flag(frame["repeated_reading_trial"]).astype(int)
        frame["unique_trial_id"] = (
            frame["participant_id"].astype(str)
            + "_"
            + frame["unique_paragraph_id"].astype(str)
            + "_r"
            + reading.astype(str)
        )
    return frame


def _join_ids(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    """``"_"``-joined string form of ``columns`` — one composed id per row.

    Each part goes through ``stable_id``, not a plain ``.astype(str)``
    — several of OneStop's own id components (``paragraph_id``, ``article_id``)
    are whole numbers, and one blank cell anywhere else in that CSV column is
    enough for pandas to read the whole thing as ``float64``. Left uncorrected
    here, the composed id would embed a ``.0`` that a plain string column on
    the other side of a join never has.
    """
    from . import data

    parts = [data.stable_id(frame[column]) for column in columns]
    joined = parts[0]
    for part in parts[1:]:
        joined = joined + "_" + part
    return joined


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
    # Read via data.read_mapped_table (not pd.read_csv directly): the OSF
    # .csv.zip archives wrap the CSV alongside macOS __MACOSX resource-fork
    # entries, which pandas' zip reader rejects ("Multiple files found in ZIP").
    # read_table's zip path filters that cruft and reads with low_memory=False —
    # and the planned read parses only the columns normalization keeps,
    # which is most of what a multi-gigabyte report costs.
    frame = data.read_mapped_table(
        path,
        kind="words" if kind == "ia" else "fixations",
        filter_fields=_ONESTOP_ID_COLUMNS + _ONESTOP_REGIME_COLUMNS,
    )
    # Only Paragraph is regime-split on OSF; every other public part
    # holds all four regimes' trials, so cut it to the one asked for.
    if variant == "public" and part != "Paragraph":
        frame = _keep_onestop_regime(frame, regime)
    frame = _compose_onestop_ids(frame)
    frame["part"] = part
    if part == "QA":
        frame = frame.drop_duplicates()
    return frame


def _onestop_parts_as_screens(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Make each part a *screen* of its trial, in presentation order.

    Every part of a reading shares its ``unique_trial_id`` — the title, the
    passage and the question screens are one trial, shown one after another —
    so the trial is left whole and the part is its screen: the ``part`` column
    is auto-detected as ``screen_id`` (`data.SCREEN_ID_CANDIDATES`), and
    ``screen_index`` numbers the screens a trial *has* 1..N in `_ONESTOP_PARTS`
    order. Per trial, because the Screen picker reads it as "n of N": not every
    reading has every part (only an article's first paragraph has a title
    screen, only the information-seeking regimes a question preview), and a
    fixed per-part number would read "3 of 6" on the second screen. Words and
    fixations are numbered from the screens both hold, so the two agree. Each
    screen keeps its own coordinate space and word boxes (`multipart.py`). A
    frame without the ``part`` / ``unique_trial_id`` columns is returned
    untouched.
    """
    keys = ["participant_id", "unique_trial_id"]
    needed = {*keys, "part"}
    if words.empty or not needed <= set(words.columns):
        return words, fixations
    order = {part: index for index, part in enumerate(_ONESTOP_PARTS)}
    screens = words[[*keys, "part"]].drop_duplicates().astype(str)
    screens["_order"] = screens["part"].map(order)
    screens = screens.sort_values([*keys, "_order"], kind="stable")
    screens["screen_index"] = screens.groupby(keys, sort=False).cumcount() + 1
    screens = screens.drop(columns="_order")

    def _stamp(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or not needed <= set(frame.columns):
            return frame
        probe = frame[[*keys, "part"]].astype(str)
        index = probe.merge(screens, on=[*keys, "part"], how="left")["screen_index"]
        frame = frame.copy()
        frame["screen_index"] = index.to_numpy()
        return frame

    return _stamp(words), _stamp(fixations)


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

    ``parts`` is any subset of the seven trial parts (default: Paragraph;
    :func:`onestop_regime_parts` lists every part of a regime). A public part
    other than Paragraph is cut to ``regime`` by its ``question_preview`` /
    ``repeated_reading_trial`` flags. Each part is a *screen* of its
    trial (``part`` → ``screen_id``, plus a ``screen_index`` in presentation
    order), so a reading's title, passage and question screens are one trial.
    ``variant`` is
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

    reports = [(kind, part) for kind in ("ia", "fixations") for part in part_list]
    # "0 of N" first — one report here is a whole IA or fixation file,
    # so a report only after it would hide most of the load from a gated card.
    progress.report(0, len(reports), unit="reports")
    word_frames, fix_frames = [], []
    for index, (kind, part) in enumerate(reports, start=1):
        frame = _read_onestop_part(root, kind, regime, part, variant)
        (word_frames if kind == "ia" else fix_frames).append(frame)
        progress.report(index, len(reports), unit="reports")
    words = pd.concat(word_frames, ignore_index=True, sort=False)
    fixations = pd.concat(fix_frames, ignore_index=True, sort=False)
    if len(part_list) > 1:
        words, fixations = _onestop_drop_unmatched_screens(words, fixations)
    return _onestop_parts_as_screens(words, fixations)


def _onestop_drop_unmatched_screens(
    words: pd.DataFrame, fixations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only the screens both reports have, loudly.

    Several parts make each part a screen, and ``multipart.validate_matching_parts``
    rejects a screen present in one report and absent from the other — which
    the OSF release has: its *Answers* fixation report holds 31 fixations of
    ``l55_519``'s first reading of ``2_9_2_Ele`` that its interest-area report
    has no row for. One such gap would otherwise abort the whole load. A frame
    without the identity columns is returned untouched.
    """
    keys = ["participant_id", "unique_trial_id", "part"]
    if not (set(keys) <= set(words.columns) and set(keys) <= set(fixations.columns)):
        return words, fixations
    word_keys = pd.MultiIndex.from_frame(words[keys].astype(str))
    fix_keys = pd.MultiIndex.from_frame(fixations[keys].astype(str))
    shared = word_keys.unique().intersection(fix_keys.unique())
    keep_words = word_keys.isin(shared)
    keep_fix = fix_keys.isin(shared)
    for name, frame, keep in (
        ("word box", words, keep_words),
        ("fixation", fixations, keep_fix),
    ):
        if not keep.all():
            dropped = frame.loc[~keep, keys].drop_duplicates()
            _LOGGER.warning(
                "OneStop: dropped %d %s row(s) on %d screen(s) the other report "
                "does not have (e.g. %s).",
                int((~keep).sum()),
                name,
                len(dropped),
                ", ".join(
                    "/".join(map(str, row)) for row in dropped.head(3).to_numpy()
                ),
            )
    # A fresh index: later steps align on it, and a gapped one is how a
    # positional assignment quietly lands on the wrong rows.
    return (
        words.loc[keep_words].reset_index(drop=True),
        fixations.loc[keep_fix].reset_index(drop=True),
    )


def load_onestop(
    root: str | Path,
    *,
    regime: str = "ordinary",
    parts: Iterable[str] | None = None,
    variant: str = "public",
    download: bool = False,
    names: str = "source",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load OneStop as normalized ``(words, fixations)`` frames, ready to plot.

    OneStop's presentation monitor was 2560×1440 px (Dell U2715H; Berzak et al. 2025,
    Methods → Apparatus). Pass that as ``canvas_size`` to
    [`plot_scanpath`][scanpath_studio.api.plot_scanpath] for true-to-scale rendering.
    The reports already match the bundled demo's schema, so they load through the same
    auto-detection as any other data.

    Args:
        root: A folder holding the OneStop reports, or (public variant only) to download
            them into.
        regime: ``"ordinary"``, ``"information_seeking"``, ``"repeated"`` or
            ``"information_seeking_repeated"``.
        parts: Any subset of ``Title``, ``Question_Preview``, ``Paragraph``,
            ``Questions``, ``Answers``, ``QA`` and ``Feedback``. Left out,
            ``Paragraph``.
        variant: ``"public"`` for the OSF release, ``"lacclab"`` for the lab's local
            export.
        download: Fetch the chosen regime and parts into ``root`` on first use. The
            public reports are large.
        names: ``"source"`` for OneStop's own column names, ``"canonical"`` for the
            internal ones (see `api.load_scanpath_data`).

    Returns:
        The normalized ``(words, fixations)`` frames.

    Examples:
        ```python
        import scanpath_studio as sps

        words, fixations = sps.load_onestop(
            "data/OneStop", regime="ordinary", parts=["Paragraph"], download=True
        )
        pid, tid = sps.list_trials(words, fixations).iloc[0]  # one reading
        fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
        ```
    """
    words_raw, fixations_raw = onestop_raw_frames(
        root, regime=regime, parts=parts, variant=variant, download=download
    )

    from . import api

    return api.load_scanpath_data(words=words_raw, fixations=fixations_raw, names=names)
