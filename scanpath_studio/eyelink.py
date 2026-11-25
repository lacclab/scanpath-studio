"""EyeLink EDF import (experimental).

EDF recordings are converted to ASC with SR Research's ``edf2asc``, which is
found on the user's machine and never bundled or downloaded.
"""

from __future__ import annotations

import functools
import hashlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import warnings
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
from pandas.api.types import union_categoricals

from scanpath_studio import constants
from scanpath_studio import progress as progress_mod
from scanpath_studio.file_lock import file_lock

EDF2ASC_ENV = "SCANPATH_EDF2ASC"

# Where the EyeLink Developers Kit installs ``edf2asc``, checked after the
# environment variable and ``PATH``.
KNOWN_EDF2ASC_PATHS: tuple[Path, ...] = (
    Path("/usr/local/bin/edf2asc"),
    Path(r"C:\Program Files (x86)\SR Research\EyeLink\bin\edf2asc.exe"),
    Path(r"C:\Program Files\SR Research\EyeLink\bin\edf2asc.exe"),
    Path("/usr/bin/edf2asc"),
)


class Edf2AscNotFoundError(FileNotFoundError):
    """``edf2asc`` is not installed where the app can find it."""


class Edf2AscError(RuntimeError):
    """``edf2asc`` could not be run, or failed to convert a recording."""


def _require_enabled(entry: str) -> None:
    """Raise unless the experimental EyeLink import is switched on."""
    if not constants.eyelink_import_enabled():
        raise ValueError(
            f"{entry} is an experimental feature; set SCANPATH_EXPERIMENTAL=1 to use it."
        )


def find_edf2asc() -> Path:
    """The ``edf2asc`` executable: ``SCANPATH_EDF2ASC``, then ``PATH``, then the
    Developers Kit's install folders."""
    override = os.environ.get(EDF2ASC_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
        raise Edf2AscNotFoundError(
            f"{EDF2ASC_ENV} points to {path}, which is not a file."
        )
    on_path = shutil.which("edf2asc")
    if on_path:
        return Path(on_path)
    for candidate in KNOWN_EDF2ASC_PATHS:
        if candidate.is_file():
            return candidate
    raise Edf2AscNotFoundError(
        "edf2asc was not found. It ships with SR Research's EyeLink Developers Kit "
        "(https://www.sr-research.com/support/); install it, or set "
        f"{EDF2ASC_ENV} to the executable's path."
    )


def convert_edf(edf: Path, out_dir: Path, *, samples: bool = False) -> Path:
    """Convert ``edf`` to ``<stem>.asc`` in ``out_dir`` and return that path.

    Events only unless ``samples`` is set, which keeps the raw gaze samples.
    """
    _require_enabled("convert_edf")
    edf, out_dir = Path(edf), Path(out_dir)
    exe = find_edf2asc()
    args = [str(exe), str(edf), "-t", "-c", "-y", "-utf8"]
    if not samples:
        args.append("-e")
    args += ["-p", str(out_dir)]
    try:
        run = subprocess.run(
            args, capture_output=True, text=True, errors="replace", check=False
        )
    except OSError as exc:
        hint = ""
        if exc.errno == 86 or "bad cpu type" in str(exc).lower():
            hint = (
                " edf2asc is an Intel-only program; on an Apple-silicon Mac install "
                "Rosetta with: softwareupdate --install-rosetta --agree-to-license"
            )
        raise Edf2AscError(f"Could not run {exe}: {exc}.{hint}") from exc
    asc = out_dir / f"{edf.stem}.asc"
    if run.returncode != 0 or not asc.is_file():
        output = ((run.stdout or "") + (run.stderr or "")).strip()
        raise Edf2AscError(
            f"edf2asc failed on {edf.name} (exit {run.returncode}): {output or 'no output'}"
        )
    return asc


@dataclass(frozen=True)
class AscRecording:
    """What an EyeLink ASC file holds, before it is read as a study.

    Times are tracker milliseconds.  ``eye`` is ``"L"`` or ``"R"``.
    """

    # EyeLink's own fixation events: eye, onset, offset, duration_ms, x, y
    # (x / y are the EFIX line's average gaze position).
    fixations: pd.DataFrame
    # MSG lines: time (the offset in the line already applied) and text.
    messages: pd.DataFrame
    # START / END line times of each recording block; ``end`` is missing for a
    # block that has no END line.
    blocks: pd.DataFrame
    # One row per eye per sample (time, x, y, pupil, eye), or None when not asked for.
    samples: pd.DataFrame | None
    # Width and height of the tracker's display, from DISPLAY_COORDS.
    display: tuple[int, int] | None
    # What the samples' pupil values measure, from the PUPIL line: "area" or
    # "diameter" (None when the file does not say).
    pupil: str | None = None
    # The eyes each recording block tracks, each set once in file order.  A
    # sample line does not name its eyes, so when blocks differ the samples
    # are left out (``samples`` is empty).
    eyes: tuple[tuple[str, ...], ...] = ()

    @property
    def eyes_switched(self) -> bool:
        """Whether recording blocks track different eyes."""
        return len(self.eyes) > 1


_MISSING_PYMOVEMENTS = (
    'Reading EyeLink recordings needs pymovements: pip install "scanpath-studio[edf]"'
)
# pymovements warns about every header an events-only ASC lacks.
_QUIET_PYMOVEMENTS = (r"No .* found", r"Missing start marker")
_MESSAGE_OFFSET = re.compile(r"^(-?\d+)\s+(.*)$", re.DOTALL)
_DISPLAY_COORDS = re.compile(r"^DISPLAY_COORDS\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)")
_EYE_LETTER = {"left": "L", "right": "R"}


# A byte that is not part of UTF-8, as ``surrogateescape`` decodes it.
_ESCAPED_BYTE = re.compile("[\udc80-\udcff]")


# A long message's id is not always a number (OneStop logs ``50a``), and an id
# is used again by later messages.
_LONG_START = re.compile(rb"!V LONGMS_ST_(\S+) ")
# A sample line: it begins with its tick's time.
_SAMPLE_LINE = re.compile(rb"(?m)^[0-9][^\n]*(?:\n|$)")


def _line_end(data: bytes, at: int) -> int:
    end = data.find(b"\n", at)
    return len(data) if end < 0 else end


def _payload(data: bytes, start: int, end: int) -> bytes:
    """``data[start:end]`` without the line's ``\\r``, if it ends in one."""
    if end > start and data[end - 1 : end] == b"\r":
        end -= 1
    return data[start:end]


def _join_long_messages(data: bytes) -> bytes:
    """``data`` with each message Experiment Builder split into chunks joined
    back into one line.

    A message too long for one ``MSG`` line is logged as ``!V LONGMS_ST_<id>
    <chunk>`` followed by ``!V LONGMS_CONT_<id> <chunk>`` lines.  Each chunk
    is everything after the one space following its tag (a chunk may begin
    with a space of the message), and the chunks are cut at byte counts, so a
    UTF-8 character can straddle two of them: they are joined as bytes, with
    nothing between them, before any line is decoded.  The joined line keeps
    the first line's ``MSG <time>`` and drops the tags.
    """
    if b"!V LONGMS_ST_" not in data:
        return data
    out, done = [], 0
    for match in _LONG_START.finditer(data):
        begin = data.rfind(b"\n", 0, match.start()) + 1
        if match.start() < done or not data.startswith(b"MSG", begin):
            continue
        end = _line_end(data, match.end())
        chunks = [_payload(data, match.end(), end)]
        tag = b"!V LONGMS_CONT_" + match.group(1) + b" "
        following = end + 1
        while following < len(data) and data.startswith(b"MSG", following):
            stop = _line_end(data, following)
            at = data.find(tag, following, stop)
            if at < 0:
                break
            chunks.append(_payload(data, at + len(tag), stop))
            following = stop + 1
        out += [data[done : match.start()], *chunks, b"\n"]
        done = following
    out.append(data[done:])
    return b"".join(out)


def _asc_lines(path: Path, *, samples: bool = True) -> list[str]:
    """The file's lines, each ending in ``\\n``, with Experiment Builder's
    long messages joined back into one line (`_join_long_messages`).  Without
    ``samples`` the sample lines (those beginning with their tick's time) are
    left out: they are nearly all of a recording, and events need none.

    Each line is decoded as UTF-8, or as latin-1 (which decodes any bytes)
    when that one line is not UTF-8: ``edf2asc -utf8`` writes UTF-8, and a
    stray byte of another encoding in one message must not garble every UTF-8
    character of the file.
    """
    data = _join_long_messages(path.read_bytes())
    if not samples:
        # Dropped before decoding, in one pass over the bytes.
        data = _SAMPLE_LINE.sub(b"", data)
    try:
        text, clean = data.decode("utf-8"), True
    except UnicodeDecodeError:
        text, clean = data.decode("utf-8", "surrogateescape"), False
    del data
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    # The line each stray byte is on.
    rows, line, done = set(), 0, 0
    for at in [] if clean else (m.start() for m in _ESCAPED_BYTE.finditer(text)):
        line += text.count("\n", done, at)
        done = at
        rows.add(line)
    lines = text.split("\n")
    del text
    for row in rows:
        lines[row] = lines[row].encode("utf-8", "surrogateescape").decode("latin-1")
    if lines and lines[-1] == "":
        lines.pop()
    for i in range(len(lines)):
        lines[i] += "\n"
    return lines


class _DecodedLines(io.TextIOBase):
    """Lines already decoded, read as a text stream: pymovements parses the
    same list the line scan reads, so the file is read and decoded once."""

    def __init__(self, lines: list[str], name: str) -> None:
        super().__init__()
        self._lines = lines
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def readable(self) -> bool:
        return True

    def readlines(self, hint: int = -1) -> list[str]:
        return self._lines

    def __iter__(self) -> Iterator[str]:
        return iter(self._lines)

    def read(self, size: int | None = -1) -> str:
        """The whole text; a read of part of it is not supported."""
        if size is not None and size > 0:
            raise io.UnsupportedOperation("read(size) is not supported")
        return "" if size == 0 else "".join(self._lines)


def _parse_asc(lines: list[str], name: str):
    try:
        import pymovements as pm
    except ImportError as exc:
        raise ImportError(_MISSING_PYMOVEMENTS) from exc
    with warnings.catch_warnings():
        for pattern in _QUIET_PYMOVEMENTS:
            warnings.filterwarnings("ignore", message=pattern)
        return pm.gaze.from_asc(_DecodedLines(lines, name), events=True, messages=True)


def _scan_lines(lines: list[str]):
    """The facts pymovements does not keep: each EFIX line's position and
    duration, the START / END lines, the eyes each START line records (in
    order, each set once) and what the ``PUPIL`` line says the samples' pupil
    values measure (``"area"`` / ``"diameter"``)."""
    efix: dict[tuple[str, int], tuple[int, float, float]] = {}
    order: list[tuple[str, int]] = []
    eyes: list[tuple[str, ...]] = []
    pupil: str | None = None
    for line in lines:
        if line.startswith("EFIX"):
            f = line.split()
            efix[(f[1], int(f[2]))] = (int(f[4]), float(f[5]), float(f[6]))
        elif line.startswith("START"):
            f = line.split()
            time = int(f[1])
            order.append(("start", time))
            recorded = tuple(
                _EYE_LETTER[t.lower()] for t in f[2:] if t.lower() in _EYE_LETTER
            )
            if recorded and recorded not in eyes:
                eyes.append(recorded)
        elif line.startswith("END"):
            f = line.split()
            order.append(("end", int(f[1])))
        elif pupil is None and line.startswith("PUPIL"):
            f = line.split()
            if len(f) > 1 and f[1].lower() in ("area", "diameter"):
                pupil = f[1].lower()
    blocks: list[tuple[int, int | None]] = []
    open_start: int | None = None
    for kind, time in order:
        if kind == "start":
            if open_start is not None:
                blocks.append((open_start, None))
            open_start = time
        elif open_start is not None:
            blocks.append((open_start, time))
            open_start = None
    if open_start is not None:
        blocks.append((open_start, None))
    return efix, blocks, eyes, pupil


def _fixation_frame(events, efix) -> pd.DataFrame:
    rows = []
    for row in events.iter_rows(named=True):
        if row["name"] != "fixation_eyelink":
            continue
        letter = _EYE_LETTER[row["eye"]]
        onset, offset = row["onset"], row["offset"]
        # The EFIX line's own duration counts both end samples, which the
        # difference of its times does not.
        line_duration, x, y = efix.get(
            (letter, onset), (row["duration"], np.nan, np.nan)
        )
        rows.append((letter, onset, offset, line_duration, x, y))
    return pd.DataFrame(
        rows, columns=["eye", "onset", "offset", "duration_ms", "x", "y"]
    ).astype({"onset": "int64", "offset": "int64", "duration_ms": "int64"})


def _message_frame(messages) -> pd.DataFrame:
    rows = []
    for time, content in messages.iter_rows():
        match = _MESSAGE_OFFSET.match(content)
        offset, text = (int(match.group(1)), match.group(2)) if match else (0, content)
        rows.append((int(time) - offset, text.strip()))
    return pd.DataFrame(rows, columns=["time", "text"]).astype({"time": "int64"})


def _display_size(messages: pd.DataFrame) -> tuple[int, int] | None:
    for text in messages["text"]:
        match = _DISPLAY_COORDS.match(text)
        if match:
            left, top, right, bottom = map(int, match.groups())
            return right - left + 1, bottom - top + 1
    return None


def _sample_frame(frame, eyes: tuple[str, ...]) -> pd.DataFrame:
    """The samples as one row per eye per tick; a tick the tracker lost has a
    missing position and a missing (not EyeLink's 0) pupil."""
    import polars as pl

    columns = ["time", "x", "y", "pupil", "eye"]
    if frame.height == 0 or not eyes:
        return pd.DataFrame(columns=columns)
    time = frame["time"].to_numpy()
    nested_pupil = isinstance(frame.schema["pupil"], pl.List)

    def numbers(expr) -> np.ndarray:
        return frame.select(expr.cast(pl.Float64)).to_series().to_numpy()

    parts = []
    for i, eye in enumerate(eyes):
        x = numbers(pl.col("pixel").list.get(2 * i))
        y = numbers(pl.col("pixel").list.get(2 * i + 1))
        p = numbers(pl.col("pupil").list.get(i) if nested_pupil else pl.col("pupil"))
        if not p.flags.writeable:
            p = p.copy()
        p[np.isnan(x) | np.isnan(y)] = np.nan
        parts.append(
            pd.DataFrame({"time": time, "x": x, "y": y, "pupil": p, "eye": eye})
        )
    if len(parts) == 1:
        return parts[0]
    return pd.concat(parts, ignore_index=True).sort_values(
        ["time", "eye"], kind="stable", ignore_index=True
    )


def read_asc(path: Path, *, samples: bool = False) -> AscRecording:
    """Read an EyeLink ASC file: its fixation events, messages, recording blocks
    and display size, and with ``samples`` its raw gaze samples."""
    _require_enabled("read_asc")
    path = Path(path)
    lines = _asc_lines(path, samples=samples)
    gaze = _parse_asc(lines, str(path))
    efix, blocks, eyes, pupil = _scan_lines(lines)
    del lines
    messages = _message_frame(gaze.messages)
    frame = None
    if samples:
        # Each sample is labelled with the eyes of the blocks; when blocks
        # track different eyes, no label would be right.
        frame = _sample_frame(gaze.samples, eyes[0] if len(eyes) == 1 else ())
    return AscRecording(
        fixations=_fixation_frame(gaze.events.frame, efix),
        messages=messages,
        blocks=pd.DataFrame(blocks, columns=["start", "end"]).astype(
            {"start": "int64", "end": "Int64"}
        ),
        samples=frame,
        display=_display_size(messages),
        pupil=pupil,
        eyes=tuple(eyes),
    )


# ---------------------------------------------------------------------------
# Trials, screens and the session files Experiment Builder writes
# ---------------------------------------------------------------------------

# An interest-area group belongs to the display that begins within this many
# ms of it.  Experiment Builder logs a group up to 3 ms off its display (OneStop
# sessions: -2 to +3 ms), and two displays are hundreds of ms apart.
IAS_MATCH_MS = 5
# An ``.ias`` file's group offsets count from the same onset as its draw list's
# displays, but the ``IAREA FILE`` message that anchors them can be logged up to
# one 60 Hz refresh away from that onset (OneStop's older experiments: 6 to 12
# ms, every group of the file alike).  A file's groups may therefore move
# together by one shift of at most this many ms, when it matches them all.
IAS_SHIFT_MS = 17

_WHITE = (255, 255, 255)
_BOX_COLUMNS = ["word_id", "x", "y", "width", "height", "text"]
# DataViewer drawing commands the stimulus composer does not draw.
_UNDRAWN_COMMANDS = ("DRAWLINE", "DRAWBOX", "FILLBOX", "FIXPOINT")


@dataclass
class Display:
    """One display of a draw list: what the screen showed from ``offset`` on.

    ``offset`` is the ``.vcl`` line's leading number (0 for a display logged
    in messages); the display begins at the draw list's message time minus it.
    ``images`` holds ``(path, x, y, width, height)`` placed by their top-left
    corner, ``width`` / ``height`` ``None`` for the picture's own size.
    ``skipped`` keeps the lines that draw something this reader does not, and
    ``refused`` the image paths that lead out of the experiment folder.
    """

    offset: int
    background: tuple[int, int, int]
    images: list[tuple[Path, int, int, int | None, int | None]]
    skipped: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


def _read_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return []


def _experiment_root(session: Path, experiment_dir: Path | None = None) -> Path:
    """The folder a session's ``!V`` paths are confined to.

    In Experiment Builder's layout, ``<experiment>/results/<session>/``, it is
    the session folder's grandparent; otherwise ``experiment_dir`` when given,
    else the session folder itself.
    """
    session = Path(session).resolve()
    if session.parent.name == "results":
        return session.parent.parent
    if experiment_dir is not None:
        return Path(experiment_dir).resolve()
    return session


def _session_path(
    name: str, session: Path | None, root: Path | None = None
) -> Path | None:
    """A ``!V`` / ``.vcl`` path, which is relative to the session folder.

    The recording names these paths, so they are confined to ``root`` (by
    default the session's `_experiment_root`): an absolute path, or one that
    leads out of it (symbolic links followed), is ``None``.  Without a session
    folder the path is kept as written.
    """
    path = Path(name)
    if session is None:
        return path
    if path.is_absolute():
        return None
    root = _experiment_root(session) if root is None else root
    resolved = (session / path).resolve()
    return resolved if resolved.is_relative_to(root) else None


def _refused(name: str, root: Path) -> str:
    return f"{name} is outside the experiment folder {root}; it was not read."


def _image(args: list[str]):
    """``TOP_LEFT <path> x y [w h]`` as ``(path, x, y, w, h)``, the path as
    written, else ``None``."""
    if len(args) < 4 or args[0] != "TOP_LEFT":
        return None
    rest = args[1:]
    for size in (4, 2):
        tail = rest[-size:]
        if len(rest) > size and all(re.fullmatch(r"-?\d+", v) for v in tail):
            numbers = [int(v) for v in tail] + [None, None]
            return (" ".join(rest[:-size]), *numbers[:4])
    return None


def _colour(args: list[str]) -> tuple[int, int, int] | None:
    """``CLEAR``'s ``r g b`` arguments, else ``None``."""
    if len(args) < 3 or not all(re.fullmatch(r"\d+", v) for v in args[:3]):
        return None
    r, g, b = (int(v) for v in args[:3])
    return r, g, b


def parse_vcl(
    path: Path, *, session: Path | None = None, root: Path | None = None
) -> list[Display]:
    """The displays of a ``.vcl`` draw list: a new one at each ``CLEAR``.

    Image paths in a ``.vcl`` are relative to the session folder (the one the
    recording was made in), not to the ``.vcl``'s own; they are resolved
    against ``session`` when given and kept as written otherwise.  With a
    session folder, a path outside the experiment folder (``root``, by default
    the session's `_experiment_root`) is not kept as an image but listed in the
    display's ``refused``.
    """
    displays: list[Display] = []
    for line in _read_lines(Path(path)):
        parts = line.split()
        if not parts:
            continue
        try:
            offset = int(parts[0])
        except ValueError:
            offset = None
        command, args = (parts[1], parts[2:]) if len(parts) > 1 else ("", [])
        background = _colour(args) if command == "CLEAR" else None
        if offset is not None and background is not None:
            displays.append(Display(offset, background, []))
            continue
        if offset is not None and not displays:
            displays.append(Display(offset, _WHITE, []))
        image = _image(args) if command == "IMGLOAD" else None
        if image is not None and displays:
            path = _session_path(image[0], session, root)
            if path is None:
                displays[-1].refused.append(image[0])
            else:
                displays[-1].images.append((path, *image[1:]))
        elif displays:
            displays[-1].skipped.append(line.strip())
    return displays


def _box(parts: list[str]):
    """``RECTANGLE id left top right bottom [label]`` as a box row."""
    if len(parts) < 6 or parts[0] != "RECTANGLE":
        return None
    try:
        word_id, left, top, right, bottom = (int(v) for v in parts[1:6])
    except ValueError:
        return None
    text = parts[6].strip() if len(parts) > 6 else ""
    return word_id, left, top, right - left, bottom - top, text


def parse_ias(path: Path) -> pd.DataFrame:
    """The rectangles of an ``.ias`` interest-area file, one row per box with
    its line's ``offset``.  Other shapes are left out and listed in
    ``attrs["skipped"]``."""
    rows, skipped = [], []
    for line in _read_lines(Path(path)):
        parts = line.strip().split(None, 7)
        if not parts:
            continue
        box = None
        if re.fullmatch(r"-?\d+", parts[0]):
            box = _box(parts[1:])
        if box is None:
            skipped.append(line.strip())
        else:
            rows.append((int(parts[0]), *box))
    frame = pd.DataFrame(rows, columns=["offset", *_BOX_COLUMNS]).astype(
        {c: "int64" for c in ["offset", "word_id", "x", "y", "width", "height"]}
    )
    frame.attrs["skipped"] = skipped
    return frame


def _sorted_messages(rec: AscRecording) -> pd.DataFrame:
    return rec.messages.sort_values("time", kind="stable", ignore_index=True)


def _last_time(rec: AscRecording) -> int:
    times = [rec.messages["time"], rec.fixations["offset"], rec.blocks["start"]]
    times.append(rec.blocks["end"].dropna())
    if rec.samples is not None:
        times.append(rec.samples["time"])
    return int(max(s.max() for s in times if len(s)))


def _trial_block(blocks: list, begin: int, following: int | None):
    """The recording block of the trial whose TRIALID is at ``begin``."""
    for block in blocks:
        if block.start >= begin and (following is None or block.start < following):
            return block
    for block in blocks:
        if block.start <= begin and (pd.isna(block.end) or begin <= block.end):
            return block
    return None


def trial_table(rec: AscRecording) -> pd.DataFrame:
    """One row per ``TRIALID``: ``trial_id`` (its value), ``start`` (the START
    line of its recording), ``begin`` (the TRIALID message) and ``end``.

    A ``TRIALID`` value seen before gets ``_r2``, ``_r3``, … in file order;
    ``attrs["repeated"]`` maps each repeated value to the ids it was given.

    A trial ends at its ``TRIAL_RESULT``, else at the next ``TRIALID``, else
    at its recording's ``END``, else at the file's last event.  Its recording
    is the first that starts between its TRIALID and the next (Experiment
    Builder logs TRIALID before START), else the one under way at the TRIALID.
    """
    messages = _sorted_messages(rec)
    text = messages["text"]
    ids = messages[text.str.match(r"TRIALID(\s|$)")]
    results = messages.loc[text.str.match(r"TRIAL_RESULT(\s|$)"), "time"].tolist()
    blocks = list(rec.blocks.itertuples(index=False))
    begins = ids["time"].tolist()
    rows = []
    for i, (begin, label) in enumerate(zip(begins, ids["text"])):
        following = begins[i + 1] if i + 1 < len(begins) else None
        block = _trial_block(blocks, begin, following)
        result = next(
            (t for t in results if t >= begin and (following is None or t < following)),
            None,
        )
        if result is not None:
            end = result
        elif following is not None:
            end = following
        elif block is not None and not pd.isna(block.end):
            end = int(block.end)
        else:
            end = _last_time(rec)
        start = block.start if block is not None else begin
        rows.append((label.removeprefix("TRIALID").strip(), start, begin, end))
    table = pd.DataFrame(rows, columns=["trial_id", "start", "begin", "end"]).astype(
        {"start": "int64", "begin": "int64", "end": "int64"}
    )
    # A TRIALID logged again is a repeated reading: its second occurrence is
    # ``<id>_r2``, its third ``<id>_r3``, as the app names repeated readings;
    # a number some TRIALID already is (``1, 1, 1_r2``) is passed over.
    logged = table["trial_id"].tolist()
    logged_ids = set(logged)
    taken, seen = set(logged), Counter()
    repeated: dict[str, list[str]] = {}
    passed_over: dict[str, list[str]] = {}
    ids = []
    for trial_id in logged:
        seen[trial_id] += 1
        if seen[trial_id] == 1:
            ids.append(trial_id)
            continue
        n = max(seen[trial_id], 2)
        while f"{trial_id}_r{n}" in taken:
            # Noted only when a TRIALID is logged under that name; one an
            # earlier repeat was given needs no note.
            if f"{trial_id}_r{n}" in logged_ids:
                passed_over.setdefault(trial_id, []).append(f"{trial_id}_r{n}")
            n += 1
        taken.add(f"{trial_id}_r{n}")
        ids.append(f"{trial_id}_r{n}")
        repeated.setdefault(trial_id, []).append(f"{trial_id}_r{n}")
    table["trial_id"] = ids
    table.attrs["repeated"] = repeated
    table.attrs["passed_over"] = passed_over
    return table


def _trial_messages(rec: AscRecording, trials: pd.DataFrame):
    """Each trial with its messages: from its TRIALID to its end, and before
    the next trial's TRIALID."""
    messages = _sorted_messages(rec)
    begins = trials["begin"].tolist()
    for i, trial in enumerate(trials.itertuples(index=False)):
        stop = begins[i + 1] if i + 1 < len(begins) else None
        inside = (messages["time"] >= trial.begin) & (messages["time"] <= trial.end)
        if stop is not None:
            inside &= messages["time"] < stop
        yield trial, messages[inside]


def trial_vars(rec: AscRecording, trials: pd.DataFrame | None = None) -> pd.DataFrame:
    """``trial_id`` and one column per ``!V TRIAL_VAR name value``, in the
    order the names first appear; values are strings.  ``trials`` is the
    recording's `trial_table`, built when not given."""
    if trials is None:
        trials = trial_table(rec)
    rows, names = [], {}
    for trial, messages in _trial_messages(rec, trials):
        row = {"trial_id": trial.trial_id}
        for text in messages["text"]:
            if text.startswith("!V TRIAL_VAR "):
                parts = text.split(None, 3)
                if len(parts) >= 3:
                    row[parts[2]] = parts[3].strip() if len(parts) > 3 else ""
                    names.setdefault(parts[2], None)
        rows.append(row)
    table = pd.DataFrame(rows, columns=["trial_id", *names], dtype=object)
    return table.where(table.notna(), None)


def _named_files(rec: AscRecording) -> list[str]:
    """The session-folder paths the messages name, in order."""
    names = []
    for text in rec.messages["text"]:
        parts = text.split()
        name = None
        if parts[:2] == ["!V", "DRAW_LIST"] and len(parts) > 2:
            name = text.split(None, 2)[2].strip()
        elif parts[:3] == ["!V", "IAREA", "FILE"] and len(parts) > 3:
            name = text.split(None, 3)[3].strip()
        elif parts[:2] == ["!V", "IMGLOAD"]:
            image = _image(parts[2:])
            name = image[0] if image else None
        if name and name not in names:
            names.append(name)
    return names


def resolve_session_dir(
    source: Path,
    rec: AscRecording,
    *,
    session_dir: Path | None = None,
    experiment_dir: Path | None = None,
) -> Path | None:
    """The folder the recording's ``!V`` paths are relative to: the first of
    ``session_dir``, the source's own folder and
    ``experiment_dir/results/<source stem>`` that holds any file they name."""
    source = Path(source)
    candidates = [session_dir, source.parent]
    if experiment_dir is not None:
        candidates.append(Path(experiment_dir) / "results" / source.stem)
    names = _named_files(rec)
    for candidate in candidates:
        if candidate is None:
            continue
        root = _experiment_root(Path(candidate), experiment_dir)
        paths = (_session_path(name, Path(candidate), root) for name in names)
        if any(path is not None and path.is_file() for path in paths):
            return Path(candidate)
    return None


def _session_file(
    name: str,
    session: Path | None,
    root: Path | None,
    trial_id: str,
    lacks: str,
    notes: list[str],
) -> Path | None:
    """The session file a message names, or ``None`` (noted when the session
    folder is known but lacks it, or the path leads out of the experiment)."""
    if session is None:
        return None
    path = _session_path(name, session, root)
    if path is None:
        notes.append(f"Trial {trial_id}: {_refused(name, root)}")
        return None
    if path.is_file():
        return path
    notes.append(f"{name} was not found in {session}; trial {trial_id} {lacks}.")
    return None


def _trial_displays(
    trial, messages: pd.DataFrame, session: Path | None, root: Path | None, notes
):
    """The trial's displays as ``(begin, display)``, ``display`` ``None`` for
    a draw list whose ``.vcl`` is missing, and its interest-area groups as
    ``(time, boxes, .ias path, .ias name, file)``; ``file`` numbers the
    ``IAREA FILE`` message a group came from, ``None`` for inline boxes."""
    displays: list[tuple[int, Display | None]] = []
    groups: list[tuple[int, pd.DataFrame, Path | None, str | None, int | None]] = []
    files = 0
    inline: dict[int, Display] = {}
    inline_boxes: dict[int, list] = {}
    for time, text in zip(messages["time"], messages["text"]):
        parts = text.split()
        if parts[:2] == ["!V", "DRAW_LIST"] and len(parts) > 2:
            name = text.split(None, 2)[2].strip()
            lacks = "has no stimulus for that draw list"
            path = _session_file(name, session, root, trial.trial_id, lacks, notes)
            if path is None:
                displays.append((time, None))
                continue
            for display in parse_vcl(path, session=session, root=root):
                displays.append((time - display.offset, display))
                notes.extend(f"{name}: skipped {line}" for line in display.skipped)
                notes.extend(
                    f"{name}: {_refused(image, root)}" for image in display.refused
                )
        elif parts[:3] == ["!V", "IAREA", "FILE"] and len(parts) > 3:
            name = text.split(None, 3)[3].strip()
            lacks = "has no words from it"
            path = _session_file(name, session, root, trial.trial_id, lacks, notes)
            if path is None:
                continue
            boxes = parse_ias(path)
            notes.extend(f"{name}: skipped {line}" for line in boxes.attrs["skipped"])
            for offset, group in boxes.groupby("offset", sort=False):
                group = group[_BOX_COLUMNS].reset_index(drop=True)
                groups.append((time - int(offset), group, path, name, files))
            files += 1
        elif parts[:2] == ["!V", "CLEAR"] and _colour(parts[2:]):
            inline[time] = Display(0, _colour(parts[2:]), [])
        elif parts[:2] == ["!V", "IMGLOAD"]:
            image = _image(parts[2:])
            display = inline.setdefault(time, Display(0, _WHITE, []))
            path = None if image is None else _session_path(image[0], session, root)
            if image is None:
                display.skipped.append(text)
                notes.append(f"Trial {trial.trial_id}: skipped {text}")
            elif path is None:
                display.refused.append(image[0])
                notes.append(f"Trial {trial.trial_id}: {_refused(image[0], root)}")
            else:
                display.images.append((path, *image[1:]))
        elif parts[:3] == ["!V", "IAREA", "RECTANGLE"]:
            box = _box(text.split(None, 8)[2:])
            if box is None:
                notes.append(f"Trial {trial.trial_id}: skipped {text}")
            else:
                inline_boxes.setdefault(time, []).append(box)
        elif len(parts) > 1 and parts[0] == "!V" and parts[1] in _UNDRAWN_COMMANDS:
            notes.append(f"Trial {trial.trial_id}: skipped {text}")
    displays += sorted(inline.items())
    for time, rows in inline_boxes.items():
        frame = pd.DataFrame(rows, columns=_BOX_COLUMNS)
        groups.append((time, frame, None, None, None))
    return displays, groups


def _nearest(begins: list[int], time: int) -> int:
    """The index of the display whose begin is nearest ``time``."""
    return min(range(len(begins)), key=lambda k: abs(begins[k] - time))


def _match(begins: list[int], time: int) -> int | None:
    """The display ``time`` falls within `IAS_MATCH_MS` of, else ``None``."""
    i = _nearest(begins, time)
    return i if abs(begins[i] - time) <= IAS_MATCH_MS else None


def _ias_shift(begins: list[int], times: list[int]) -> tuple[int, bool]:
    """The shift a file's group times move by, and whether the file's timing
    was ambiguous.

    0 when every group matches as logged.  Otherwise a non-zero shift within
    `IAS_SHIFT_MS` is taken only when it matches every group of the file and
    leaves each group that matched as logged on that same display; when such
    shifts disagree on which display a group belongs to, the timing is
    ambiguous and the file is not moved.
    """
    logged = [_match(begins, t) for t in times]
    if all(i is not None for i in logged):
        return 0, False
    fits: dict[tuple[int, ...], int] = {}
    # The shifts that match the groups to one set of displays form a range
    # whose ends are some ``b - t ± IAS_MATCH_MS``, so trying those finds every
    # set a shift can reach.  A shift that lands a group on its display's
    # onset (``b - t``) is preferred, then the smallest.
    exact = {b - t for b in begins for t in times}
    edges = {s + d for s in exact for d in (-IAS_MATCH_MS, IAS_MATCH_MS)}
    candidates = [
        s
        for s in sorted(exact, key=lambda s: (abs(s), s))
        + sorted(edges - exact, key=lambda s: (abs(s), s))
        if 0 < abs(s) <= IAS_SHIFT_MS
    ]
    for shift in candidates:
        moved = [_match(begins, t + shift) for t in times]
        if any(i is None for i in moved):
            continue
        if any(i is not None and i != j for i, j in zip(logged, moved)):
            continue
        fits.setdefault(tuple(moved), shift)
    if len(fits) == 1:
        return next(iter(fits.values())), False
    return 0, len(fits) > 1


def screen_table(
    rec: AscRecording,
    trials: pd.DataFrame,
    session: Path | None,
    *,
    experiment_dir: Path | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """One row per screen of each trial, and notes on what could not be read.

    A screen is a display: each ``CLEAR`` of a ``DRAW_LIST``'s ``.vcl``,
    beginning at the message's time minus the line's offset, or the
    ``!V CLEAR`` / ``!V IMGLOAD`` messages logged at one time.  It lasts until
    the next display or the trial's end; a trial without one is one screen.
    ``boxes`` holds the interest areas (``.ias`` groups or ``!V IAREA
    RECTANGLE`` messages) logged within ``IAS_MATCH_MS`` of its begin, and
    ``ias`` the file they came from.  When the groups of one ``.ias`` file do
    not all match as logged, they may move together by one shift
    (`_ias_shift`, at most ``IAS_SHIFT_MS``), since the message anchoring the
    file can be logged off its displays' onset.  A group still matching no
    display is noted with the reason.  A draw list whose ``.vcl`` is missing
    still starts a screen, with no ``display``.  The files and images the
    recording names are confined to the session's `_experiment_root`.
    """
    notes: list[str] = []
    rows = []
    root = None if session is None else _experiment_root(session, experiment_dir)
    for trial, messages in _trial_messages(rec, trials):
        displays, groups = _trial_displays(trial, messages, session, root, notes)
        displays = [
            (begin, display)
            for begin, display in sorted(displays, key=lambda d: d[0])
            if trial.begin <= begin < trial.end
        ] or [(trial.begin, None)]
        begins = [begin for begin, _ in displays]
        ends = begins[1:] + [trial.end]
        boxes: dict[int, list[pd.DataFrame]] = {}
        sources: dict[int, Path | None] = {}
        shifts = {
            file: _ias_shift(begins, [g[0] for g in groups if g[4] == file])
            for file in {g[4] for g in groups if g[4] is not None}
        }
        for time, group, path, name, file in groups:
            shift, ambiguous = shifts.get(file, (0, False))
            i = _match(begins, time + shift)
            if i is None:
                where = f"in {name} " if name else ""
                away = abs(begins[_nearest(begins, time)] - time)
                why = f"the nearest begins {away} ms away"
                if ambiguous:
                    why += (
                        "; the file's timing is ambiguous, since shifting its "
                        "groups together fits more than one set of displays"
                    )
                elif file is not None and away <= IAS_SHIFT_MS + IAS_MATCH_MS:
                    why += ", and no one shift of the file's groups matches them all"
                notes.append(
                    f"Trial {trial.trial_id}: interest areas {where}at {time} ms "
                    f"match no display ({why}); they were left out."
                )
                continue
            boxes.setdefault(i, []).append(group)
            if path is not None:
                sources.setdefault(i, path)
        for i, ((begin, display), end) in enumerate(zip(displays, ends)):
            frame = pd.concat(boxes[i], ignore_index=True) if i in boxes else None
            rows.append(
                (
                    trial.trial_id,
                    i + 1,
                    f"screen_{i + 1}",
                    begin,
                    end,
                    display,
                    sources.get(i),
                    frame,
                )
            )
    if session is None:
        named = _named_files(rec)
        if named:
            notes.append(
                "The session folder was not found, so the screens have no stimulus "
                f"images or words ({', '.join(named)})."
            )
    columns = [
        "trial_id",
        "screen_index",
        "screen_id",
        "begin",
        "end",
        "display",
        "ias",
        "boxes",
    ]
    table = pd.DataFrame(rows, columns=columns).astype(
        {"screen_index": "int64", "begin": "int64", "end": "int64"}
    )
    return table, notes


# ---------------------------------------------------------------------------
# One session's tables and stimulus images
# ---------------------------------------------------------------------------

FIXATION_COLUMNS = [
    "participant_id",
    "trial_id",
    "text_id",
    "screen_id",
    "screen_index",
    "fixation_id",
    "x",
    "y",
    "duration_ms",
    "timestamp_ms",
    "eye",
    "image_path",
]
# ``pupil`` is named by what the recording's PUPIL line says it measures:
# ``pupil_area`` or ``pupil_diameter``.
RAW_GAZE_COLUMNS = [
    "participant_id",
    "trial_id",
    "screen_id",
    "screen_index",
    "x",
    "y",
    "timestamp_ms",
    "pupil",
    "eye",
]
WORD_COLUMNS = [
    "participant_id",
    "trial_id",
    "text_id",
    "screen_id",
    "screen_index",
    "word_id",
    "text",
    "x",
    "y",
    "width",
    "height",
    "image_path",
]


@dataclass
class SessionTables:
    """One recording session read as the app's tables.

    ``words`` and ``fixations`` carry the canonical columns (multipart, with
    ``screen_id`` / ``screen_index`` and each screen's composed stimulus as
    ``image_path``); ``trial_metadata`` has one row per trial with its
    ``TRIAL_VAR`` values; ``raw_gaze``, when asked for, has one row per eye
    per sample shown on a screen (`RAW_GAZE_COLUMNS`); ``display`` is the
    tracker's display size; ``notes`` says what could not be read or was left
    out; ``session_dir`` is the session folder its files were read from
    (`resolve_session_dir`), ``None`` when none was found.
    """

    words: pd.DataFrame
    fixations: pd.DataFrame
    trial_metadata: pd.DataFrame
    raw_gaze: pd.DataFrame | None
    display: tuple[int, int] | None
    notes: list[str]
    session_dir: Path | None = None


def compose_display(display: Display, out_dir: Path, size: tuple[int, int]) -> Path:
    """Draw ``display`` on a canvas of ``size`` and save it as a PNG in ``out_dir``.

    The canvas is the display's background colour; each image is pasted with
    its top-left corner at its ``x`` / ``y``, resized only when the draw list
    gives its width and height.  The file is named by the first 16 hex digits
    of its bytes' SHA-256, so identical screens share one file.
    """
    from PIL import Image

    canvas = Image.new("RGB", tuple(size), display.background)
    for path, x, y, width, height in display.images:
        with Image.open(path) as picture:
            layer = picture.convert("RGBA")
        if width is not None and height is not None:
            layer = layer.resize((width, height))
        canvas.paste(layer, (x, y), layer)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    data = buffer.getvalue()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{hashlib.sha256(data).hexdigest()[:16]}.png"
    if not out.is_file():
        # Sessions are read in parallel into one folder: each writer writes
        # its own file aside, then moves it into place, so a reader never sees
        # a partial one.
        with tempfile.NamedTemporaryFile(
            dir=out_dir, prefix=f".{out.stem}.", suffix=".partial", delete=False
        ) as partial:
            partial.write(data)
        os.replace(partial.name, out)
    return out


def _screen_images(
    screens: pd.DataFrame,
    size: tuple[int, int] | None,
    image_dir: Path,
    notes: list[str],
) -> list[str | None]:
    """Each screen's composed stimulus image, or ``None`` when it has no display."""
    from PIL import Image

    paths: list[str | None] = []
    composed: dict[tuple, str | None] = {}
    missing: set[Path] = set()
    if size is None and screens["display"].notna().any():
        notes.append(
            "The recording gives no display size (DISPLAY_COORDS), so the screens "
            "have no stimulus images."
        )
    for display in screens["display"]:
        if display is None or size is None:
            paths.append(None)
            continue
        key = (display.background, tuple(display.images))
        if key not in composed:
            found = [image for image in display.images if image[0].is_file()]
            for image in display.images:
                if not image[0].is_file() and image[0] not in missing:
                    missing.add(image[0])
                    notes.append(
                        f"{image[0]} was not found; the screens that show it are "
                        "drawn without it."
                    )
            drawn = Display(display.offset, display.background, found)
            try:
                composed[key] = str(compose_display(drawn, image_dir, size))
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                notes.append(f"A stimulus screen could not be drawn: {exc}")
                composed[key] = None
        paths.append(composed[key])
    return paths


def _text_id(boxes: pd.DataFrame) -> str:
    """``ias_`` and the first 12 hex digits of the SHA-256 of ``boxes``' rows
    (word id, text and box, in order): the same words in the same places get
    the same id in every session, whatever their file is called."""
    digest = hashlib.sha256()
    for row in boxes[["word_id", "text", "x", "y", "width", "height"]].itertuples(
        index=False, name=None
    ):
        digest.update("\x1f".join(map(str, row)).encode("utf-8") + b"\x1e")
    return f"ias_{digest.hexdigest()[:12]}"


def _text_ids(screens: pd.DataFrame) -> dict[str, str]:
    """Each trial's ``text_id``: `_text_id` of the interest areas of its
    screen with the most of them (the first such screen on a tie), else
    ``trial_<id>``.

    The screen with the most words is the passage read: a question shown
    before it (OneStop's preview) has fewer, so two readings of one paragraph
    under different questions share an id.  Experiment Builder numbers a
    session's ``.ias`` files as it writes them, so one file name holds
    different texts in different sessions: the id comes from what the file
    holds, not its name.
    """
    most: dict[str, pd.DataFrame] = {}
    for trial_id, boxes in zip(screens["trial_id"], screens["boxes"]):
        if boxes is not None and len(boxes) > len(most.get(trial_id, ())):
            most[trial_id] = boxes
    ids = {trial_id: _text_id(boxes) for trial_id, boxes in most.items()}
    for trial_id in screens["trial_id"]:
        ids.setdefault(trial_id, f"trial_{trial_id}")
    return ids


def _fixation_table(
    rec: AscRecording, trials: pd.DataFrame, screens: pd.DataFrame, notes: list[str]
) -> pd.DataFrame:
    """The fixations of each trial, each on the screen shown at its onset.

    A fixation that begins before its trial's first screen, or outside every
    trial (calibration, drift checks), is left out and counted in ``notes``.
    """
    fixations = rec.fixations.sort_values(["onset", "eye"], kind="stable")
    onsets = fixations["onset"].to_numpy()
    parts, early = [], 0
    by_trial = dict(tuple(screens.groupby("trial_id", sort=False)))
    for trial in trials.itertuples(index=False):
        lo, hi = np.searchsorted(onsets, [trial.begin, trial.end], side="left")
        inside = fixations.iloc[lo:hi]
        own = by_trial[trial.trial_id]
        begins = own["begin"].to_numpy()
        index = np.searchsorted(begins, inside["onset"].to_numpy(), side="right") - 1
        early += int((index < 0).sum())
        inside, index = inside[index >= 0], index[index >= 0]
        shown = own.iloc[index]
        parts.append(
            pd.DataFrame(
                {
                    "trial_id": trial.trial_id,
                    "screen_id": shown["screen_id"].to_numpy(),
                    "screen_index": shown["screen_index"].to_numpy(),
                    "fixation_id": np.arange(1, len(inside) + 1),
                    "x": inside["x"].to_numpy(),
                    "y": inside["y"].to_numpy(),
                    "duration_ms": inside["duration_ms"].to_numpy(),
                    "timestamp_ms": inside["onset"].to_numpy() - trial.start,
                    "eye": inside["eye"].to_numpy(),
                    "image_path": shown["image_path"].to_numpy(),
                }
            )
        )
    kept = sum(len(part) for part in parts)
    outside = len(fixations) - kept - early
    left_out = []
    if early:
        left_out.append(f"{early} before their trial's first screen")
    if outside:
        left_out.append(f"{outside} outside every trial")
    if left_out:
        notes.append(f"Fixations left out: {', '.join(left_out)}.")
    if not parts:
        return pd.DataFrame(columns=FIXATION_COLUMNS)
    return pd.concat(parts, ignore_index=True)


def _pupil_column(rec: AscRecording, notes: list[str]) -> str:
    if rec.pupil is None:
        if not len(rec.samples):
            notes.append(
                "The recording has no gaze samples (it was converted events only)."
            )
            return "pupil"
        notes.append(
            "The recording does not say whether its pupil values are areas or "
            "diameters (no PUPIL line); they are kept as pupil."
        )
        return "pupil"
    return f"pupil_{rec.pupil}"


def _raw_gaze_table(
    rec: AscRecording, trials: pd.DataFrame, screens: pd.DataFrame, notes: list[str]
) -> pd.DataFrame:
    """The samples of each trial shown on one of its screens, on the fixations'
    clock (``timestamp_ms`` from the trial's ``START``).

    A sample between a trial's TRIALID and its first screen, or outside every
    trial, belongs to no screen and is left out.  A sample the tracker lost
    keeps its row with a missing position and pupil.
    """
    samples = rec.samples
    pupil = _pupil_column(rec, notes)
    columns = [pupil if c == "pupil" else c for c in RAW_GAZE_COLUMNS]
    columns.remove("participant_id")
    time = samples["time"].to_numpy()
    by_trial = dict(tuple(screens.groupby("trial_id", sort=False)))
    parts = []
    # In ``trial_id`` order, the order the study folder stores them in.
    ordered = trials.sort_values("trial_id", kind="stable")
    for trial in ordered.itertuples(index=False):
        own = by_trial[trial.trial_id]
        begins, ends = own["begin"].to_numpy(), own["end"].to_numpy()
        lo, hi = np.searchsorted(time, [begins[0], ends[-1]], side="left")
        inside = samples.iloc[lo:hi]
        ticks = time[lo:hi]
        # ``lo`` is at the first screen's begin, so every tick has a screen
        # begun before it; it is on that screen until the screen ends.
        index = np.searchsorted(begins, ticks, side="right") - 1
        on_screen = ticks < ends[index]
        inside, index = inside[on_screen], index[on_screen]
        shown = own.iloc[index]
        parts.append(
            pd.DataFrame(
                {
                    "trial_id": trial.trial_id,
                    "screen_id": shown["screen_id"].to_numpy(),
                    "screen_index": shown["screen_index"].to_numpy(),
                    "x": inside["x"].to_numpy(),
                    "y": inside["y"].to_numpy(),
                    "timestamp_ms": inside["time"].to_numpy() - trial.start,
                    pupil: inside["pupil"].to_numpy(),
                    "eye": inside["eye"].to_numpy(),
                },
                columns=columns,
            )
        )
    kept = sum(len(part) for part in parts)
    if len(samples) > kept:
        notes.append(
            f"Raw gaze samples left out: {len(samples) - kept} shown on no "
            "screen of a trial."
        )
    if not kept:
        return pd.DataFrame(columns=columns)
    return pd.concat([part for part in parts if len(part)], ignore_index=True)


def _word_table(screens: pd.DataFrame) -> pd.DataFrame:
    parts = [
        boxes.assign(
            trial_id=screen.trial_id,
            screen_id=screen.screen_id,
            screen_index=screen.screen_index,
            image_path=screen.image_path,
        )
        for screen in screens.itertuples(index=False)
        if (boxes := screen.boxes) is not None
    ]
    if not parts:
        return pd.DataFrame(columns=WORD_COLUMNS)
    return pd.concat(parts, ignore_index=True)


def session_tables(
    source: Path,
    *,
    image_dir: Path,
    session_dir: Path | None = None,
    experiment_dir: Path | None = None,
    raw_gaze: bool = False,
    asc_dir: Path | None = None,
) -> SessionTables:
    """Read one recording session (``.edf`` or ``.asc``) as the app's tables.

    An ``.edf`` is converted with ``edf2asc`` into ``asc_dir`` (a temporary
    folder when ``None``).  The session folder holding its draw lists and
    interest areas is found by `resolve_session_dir`; each screen's stimulus is
    composed into ``image_dir`` (`compose_display`).  ``participant_id`` is the
    file's stem, and ``timestamp_ms`` counts from the trial's ``START`` line.
    ``raw_gaze`` also reads the recorded samples (`_raw_gaze_table`); an
    ``.edf`` is then converted with them.
    """
    _require_enabled("session_tables")
    source = Path(source)
    if source.suffix.lower() == ".edf":
        if asc_dir is None:
            with tempfile.TemporaryDirectory() as tmp:
                asc = convert_edf(source, Path(tmp), samples=raw_gaze)
                rec = read_asc(asc, samples=raw_gaze)
        else:
            asc = convert_edf(source, Path(asc_dir), samples=raw_gaze)
            rec = read_asc(asc, samples=raw_gaze)
    else:
        rec = read_asc(source, samples=raw_gaze)
    session = resolve_session_dir(
        source, rec, session_dir=session_dir, experiment_dir=experiment_dir
    )
    if session is not None:
        session = session.resolve()
    trials = trial_table(rec)
    screens, notes = screen_table(rec, trials, session, experiment_dir=experiment_dir)
    passed_over = trials.attrs.get("passed_over", {})
    for trial_id, ids in trials.attrs.get("repeated", {}).items():
        note = (
            f"TRIALID {trial_id} is logged more than once; its later readings "
            f"are {', '.join(ids)}"
        )
        if trial_id in passed_over:
            taken = list(dict.fromkeys(passed_over[trial_id]))
            what = (
                "is a TRIALID of its own"
                if len(taken) == 1
                else "are TRIALIDs of their own"
            )
            note += f" ({', '.join(taken)} {what})"
        notes.append(note + ".")
    image_paths = _screen_images(screens, rec.display, Path(image_dir), notes)
    screens = screens.assign(image_path=image_paths)
    participant = source.stem
    text_ids = _text_ids(screens)

    def _finish(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        frame = frame.assign(
            participant_id=participant, text_id=frame["trial_id"].map(text_ids)
        )
        return frame[columns].reset_index(drop=True)

    fixations = _finish(_fixation_table(rec, trials, screens, notes), FIXATION_COLUMNS)
    words = _finish(_word_table(screens), WORD_COLUMNS)
    metadata = trial_vars(rec, trials)
    metadata.insert(0, "participant_id", participant)
    gaze = None
    if raw_gaze and rec.eyes_switched:
        switch = ", then ".join("+".join(eyes) for eyes in rec.eyes)
        notes.append(
            f"The recording tracks different eyes in different blocks ({switch}), "
            "so its samples cannot be told apart by eye; its raw gaze was left out."
        )
        gaze = pd.DataFrame(columns=RAW_GAZE_COLUMNS)
    elif raw_gaze:
        gaze = _raw_gaze_table(rec, trials, screens, notes)
        gaze.insert(0, "participant_id", participant)
    return SessionTables(
        words=words,
        fixations=fixations,
        trial_metadata=metadata,
        raw_gaze=gaze,
        display=rec.display,
        notes=notes,
        session_dir=session,
    )


# ---------------------------------------------------------------------------
# A study: every session in one folder of per-participant Parquet files
# ---------------------------------------------------------------------------

#: Bumped whenever the tables read from the same recording change, so that a
#: study folder reads every session again.
PARSER_VERSION = 5
MANIFEST_VERSION = 1
_MANIFEST = "manifest.json"
# The per-participant tables of a study folder, one subfolder each.
_STUDY_TABLES = ("fixations", "words", "trial_metadata", "raw_gaze")
#: Sessions read at once by default with raw gaze: reading one session's
#: samples takes about 2 GB at its peak (a OneStop session, 1000 Hz).
RAW_GAZE_WORKERS = 2
_RECORDING_SUFFIXES = (".edf", ".asc")


@dataclass
class StudyReport:
    """What one `import_eyelink` run did: the participants it read, those it
    skipped as unchanged, those it could not read (with the error), and the
    notes on each participant it read or whose display sets it apart."""

    study_dir: Path
    imported: list[str]
    skipped: list[str]
    failed: dict[str, str]
    notes: dict[str, list[str]]


@dataclass
class EyeLinkData:
    """A study folder's tables, as `load_eyelink` reads them back.

    ``image_path`` is absolute; ``display`` is ``None`` when the sessions'
    displays differ in size (a note on each session that differs says so);
    ``notes`` maps each participant to what could not be read.
    """

    words: pd.DataFrame
    fixations: pd.DataFrame
    trial_metadata: pd.DataFrame
    raw_gaze: pd.DataFrame | None
    display: tuple[int, int] | None
    notes: dict[str, list[str]]


def study_sources(paths: str | Path | Iterable[str | Path]) -> list[Path]:
    """The recordings ``paths`` name, resolved.

    A file is taken as given; a folder is searched through for ``.edf`` files
    and for ``.asc`` files whose stem no ``.edf`` found there has (an ``.asc``
    converted beside its ``.edf``).  A recording's stem is its participant, so
    two recordings with one stem raise ``ValueError``.
    """
    _require_enabled("study_sources")
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    sources: list[Path] = []
    for path in map(Path, paths):
        if path.is_dir():
            found = sorted(
                p
                for p in path.rglob("*")
                if p.suffix.lower() in _RECORDING_SUFFIXES and p.is_file()
            )
            edfs = {p.stem for p in found if p.suffix.lower() == ".edf"}
            sources += [
                p for p in found if p.suffix.lower() == ".edf" or p.stem not in edfs
            ]
        elif path.is_file() and path.suffix.lower() in _RECORDING_SUFFIXES:
            sources.append(path)
        elif path.exists():
            raise ValueError(f"{path} is not an .edf or .asc recording.")
        else:
            raise FileNotFoundError(f"{path} does not exist.")
    sources = list(dict.fromkeys(p.resolve() for p in sources))
    if not sources:
        raise ValueError("No .edf or .asc recordings were found.")
    by_stem: dict[str, list[Path]] = {}
    for source in sources:
        _check_participant(source.stem, f"the name of {source}")
        by_stem.setdefault(source.stem, []).append(source)
    clashes = [
        f"{stem} ({', '.join(map(str, files))})"
        for stem, files in by_stem.items()
        if len(files) > 1
    ]
    if clashes:
        raise ValueError(
            "A recording's file name is its participant id, so two recordings "
            f"cannot share one: {'; '.join(clashes)}."
        )
    return sources


def _check_participant(pid: str, where: str) -> str:
    """``pid``, which names the session's files, when it is one plain file name."""
    if (
        not pid
        or pid in (".", "..")
        or "/" in pid
        or os.sep in pid
        or (os.altsep is not None and os.altsep in pid)
        or pid != Path(pid).name
    ):
        raise ValueError(
            f"{pid!r} ({where}) cannot be a participant id: it names the "
            "session's files, so it must be a plain file name."
        )
    return pid


def _read_manifest(study_dir: Path) -> dict:
    path = study_dir / _MANIFEST
    if not path.is_file():
        return {"version": MANIFEST_VERSION, "display": None, "sessions": {}}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(
            f"{path} has manifest version {manifest.get('version')}; this version "
            f"of Scanpath Studio reads version {MANIFEST_VERSION}."
        )
    for pid in manifest.get("sessions", {}):
        _check_participant(pid, f"a session in {path}")
    return manifest


def _replace_atomically(path: Path, write: Callable[[str], None]) -> None:
    """Write ``path`` aside with ``write`` and move it into place, so a reader
    sees the old file or the new one, never part of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, partial = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".partial"
    )
    os.close(handle)
    try:
        write(partial)
        os.replace(partial, path)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise


def _write_manifest(study_dir: Path, manifest: dict) -> None:
    def write(partial: str) -> None:
        Path(partial).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    _replace_atomically(study_dir / _MANIFEST, write)


def _unchanged(entry: dict | None, key: dict, raw_gaze: bool) -> bool:
    """Whether a session's manifest entry still holds for its recording and
    the folders it is read with (``key``, `_session_key`).  An entry left
    ``"writing"`` by an import that stopped part way never holds."""
    return (
        entry is not None
        and entry.get("status") == "ok"
        and all(entry.get(name) == value for name, value in key.items())
        and (bool(entry.get("raw_gaze")) or not raw_gaze)
    )


def _session_key(
    source: Path,
    stat: os.stat_result,
    session_dir: Path | None,
    experiment_dir: Path | None,
) -> dict:
    """What a session's tables are read from: its recording (path, size and
    modification time), the folders given to find its session files in and
    the parser version.  A change in any of them reads it again."""
    return {
        "source": str(source),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "session_dir": None if session_dir is None else str(session_dir),
        "experiment_dir": None if experiment_dir is None else str(experiment_dir),
        "parser_version": PARSER_VERSION,
    }


def _ok_sessions(sessions: dict) -> list[str]:
    return [pid for pid, entry in sessions.items() if entry.get("status") == "ok"]


def _failure(exc: BaseException) -> str:
    message = str(exc)
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def default_workers(*, raw_gaze: bool) -> int:
    """The sessions `import_eyelink` reads at once by default: one fewer than
    the CPUs, and with ``raw_gaze`` at most `RAW_GAZE_WORKERS`."""
    spare = max(1, (os.cpu_count() or 1) - 1)
    return min(RAW_GAZE_WORKERS, spare) if raw_gaze else spare


def _check_dependencies(sources: Iterable[Path]) -> None:
    """Raise once, before any session is read, when what reading them needs
    is missing: pymovements, and ``edf2asc`` for an ``.edf``."""
    try:
        import pymovements  # noqa: F401
    except ImportError as exc:
        raise ImportError(_MISSING_PYMOVEMENTS) from exc
    if any(source.suffix.lower() == ".edf" for source in sources):
        find_edf2asc()


def _read_session(job: dict) -> SessionTables | str:
    """One session's tables, or the message of the error that stopped them.

    Run in a worker process, so the error comes back as text: a failed session
    is reported and the others go on.
    """
    try:
        return session_tables(**job)
    except Exception as exc:
        return _failure(exc)


@contextmanager
def _main_hidden() -> Iterator[None]:
    """Start spawned workers without re-running the parent's ``__main__``.

    A spawned process imports the parent's main script before it runs a task.
    The workers need only this module, and that script may be a Streamlit app,
    a notebook kernel or a script with no ``if __name__ == "__main__"`` guard,
    so a bare ``__main__`` (no file, no spec) stands in while workers start.
    """
    main = sys.modules.get("__main__")
    sys.modules["__main__"] = types.ModuleType("__main__")
    try:
        yield
    finally:
        if main is None:
            del sys.modules["__main__"]
        else:
            sys.modules["__main__"] = main


def _read_sessions(jobs: list[dict], workers: int) -> Iterator[tuple[int, object]]:
    """``(index, result)`` for each job as it finishes: in this process with
    one worker, else in a pool of ``workers`` spawned processes."""
    if workers == 1 or len(jobs) <= 1:
        for i, job in enumerate(jobs):
            yield i, _read_session(job)
        return
    import multiprocessing
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    workers = min(workers, len(jobs))
    pool = ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    )
    # A finished future holds its session's tables, so only a window of jobs
    # is submitted at a time and each future is dropped once its result is
    # taken: the parent holds a few sessions, not the whole study.
    queued = iter(enumerate(jobs))
    running: dict = {}
    try:
        while True:
            # The pool starts its worker processes inside ``submit``.
            with _main_hidden():
                for i, job in itertools.islice(queued, 2 * workers - len(running)):
                    running[pool.submit(_read_session, job)] = i
            if not running:
                return
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            while finished:
                future = finished.pop()
                i = running.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # the worker process itself died
                    result = _failure(exc)
                del future
                yield i, result
                del result
    finally:
        # A cancelled import stops queued sessions instead of reading them all.
        pool.shutdown(wait=True, cancel_futures=True)


def _map_paths(values: pd.Series, convert: Callable) -> pd.Categorical:
    """``convert`` applied to each distinct value of ``values`` once, as a
    categorical: a session's tables name a few image files over thousands of
    rows.  A missing value, or one ``convert`` makes ``None``, is missing."""
    codes, uniques = pd.factorize(values, use_na_sentinel=True)
    converted = [convert(value) for value in uniques]
    categories = list(dict.fromkeys(c for c in converted if c is not None))
    position = {c: i for i, c in enumerate(categories)}
    lookup = np.array(
        [-1 if c is None else position[c] for c in converted] + [-1], dtype=np.int64
    )
    # A missing value's code is -1, the lookup's last entry.
    return pd.Categorical.from_codes(lookup[codes], categories=categories)


def _relative_image(path, study_dir: Path) -> str | None:
    return Path(path).resolve().relative_to(study_dir).as_posix()


def _write_by_trial(frame: pd.DataFrame, path: str) -> None:
    """Write ``frame`` as Parquet sorted by ``trial_id`` and ``timestamp_ms``,
    one row group per trial, so a reader can take one trial's rows alone."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    trial = frame["trial_id"].to_numpy()
    time = frame["timestamp_ms"].to_numpy()
    same = trial[1:] == trial[:-1]
    ordered = frame["trial_id"].is_monotonic_increasing and bool(
        (time[1:][same] >= time[:-1][same]).all()
    )
    if not ordered:
        frame = frame.sort_values(
            ["trial_id", "timestamp_ms"], kind="stable", ignore_index=True
        )
        trial = frame["trial_id"].to_numpy()
    starts = [0, *(np.flatnonzero(trial[1:] != trial[:-1]) + 1).tolist()]
    stops = [*starts[1:], len(frame)]
    # Converted one trial at a time, so the whole frame is never held twice.
    schema = pa.Schema.from_pandas(frame.iloc[:0], preserve_index=False)
    with pq.ParquetWriter(path, schema) as writer:
        for start, stop in zip(starts, stops):
            part = pa.Table.from_pandas(
                frame.iloc[start:stop], schema=schema, preserve_index=False
            )
            writer.write_table(part, max(stop - start, 1))


def _write_session(study_dir: Path, pid: str, tables: SessionTables) -> None:
    for name in _STUDY_TABLES:
        frame = getattr(tables, name)
        path = study_dir / name / f"{pid}.parquet"
        # A session read with raw gaze whose recording has no samples (one
        # converted events only) writes none.
        if frame is None or (name == "raw_gaze" and frame.empty):
            path.unlink(missing_ok=True)
            continue
        if "image_path" in frame.columns:
            frame = frame.assign(
                image_path=_map_paths(
                    frame["image_path"], lambda p: _relative_image(p, study_dir)
                )
            )
        if name == "raw_gaze":
            write = functools.partial(_write_by_trial, frame)
        else:
            write = functools.partial(frame.to_parquet, index=False)
        _replace_atomically(path, write)


def _study_display(
    sessions: dict, pids: Iterable[str]
) -> tuple[tuple[int, int] | None, dict[str, list[str]]]:
    """The display size the sessions ``pids`` share, and a note on each one
    whose display differs from the most common when they do not share one."""
    displays = {
        pid: (int(d[0]), int(d[1]))
        for pid in pids
        if (d := sessions[pid].get("display"))
    }
    counts = Counter(displays.values())
    if len(counts) <= 1:
        return next(iter(counts), None), {}
    common = counts.most_common(1)[0][0]
    sizes = ", ".join(f"{w}×{h}" for w, h in counts)
    return None, {
        pid: [
            f"This session's display is {w}×{h}, most sessions' {common[0]}×"
            f"{common[1]}; with displays of several sizes ({sizes}) the study "
            "has no single display size."
        ]
        for pid, (w, h) in displays.items()
        if (w, h) != common
    }


def import_eyelink(
    paths: str | Path | Iterable[str | Path],
    study_dir: str | Path,
    *,
    session_dir: str | Path | None = None,
    experiment_dir: str | Path | None = None,
    raw_gaze: bool = False,
    workers: int | None = None,
    rebuild: bool = False,
    keep_asc: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> StudyReport:
    """Read EyeLink recordings into the study folder ``study_dir``.

    ``paths`` is an ``.edf`` / ``.asc`` file, a folder (`study_sources`), or a
    list of them.  Each session is read by `session_tables` and written as
    ``fixations/``, ``words/`` and ``trial_metadata/<participant>.parquet``,
    its stimulus screens into ``images/``, with ``image_path`` relative to the
    study folder; ``manifest.json`` records each session as it finishes.
    ``raw_gaze`` also writes each session's samples to
    ``raw_gaze/<participant>.parquet``, one row group per trial.  A session
    whose recording (path, size, modification time), ``session_dir``,
    ``experiment_dir`` and parser version are unchanged since it was read is
    skipped, unless ``rebuild`` -- also when it was read with raw gaze and
    ``raw_gaze`` is off (it keeps its raw gaze), but not when ``raw_gaze`` asks
    for raw gaze it was read without.  One that fails is reported and the
    others go on; one whose files were being written when an import stopped is
    read again.  A participant the folder holds from another recording file is
    refused (``ValueError``) unless ``rebuild``.  pymovements, and ``edf2asc``
    when there is an ``.edf`` to read, are checked once before any session is
    read.

    ``session_dir`` is the session folder of a single recording; for several,
    ``experiment_dir`` finds each in ``results/<participant>/``.  Sessions are
    read by ``workers`` processes (default: `default_workers`; ``1`` reads
    them in this process).
    ``keep_asc`` keeps the ASC converted from an ``.edf`` in ``asc/``.  ``progress(done, total, participant)`` is called
    as each session to read finishes.
    """
    _require_enabled("import_eyelink")
    sources = study_sources(paths)
    if session_dir is not None and len(sources) != 1:
        raise ValueError(
            "session_dir is one session's folder, so it takes one recording; for "
            f"{len(sources)} recordings pass experiment_dir, the folder whose "
            "results/<participant>/ holds each session."
        )
    if workers is None:
        workers = default_workers(raw_gaze=raw_gaze)
    if workers < 1:
        raise ValueError(f"workers must be at least 1, not {workers}.")
    session_dir = None if session_dir is None else Path(session_dir).resolve()
    experiment_dir = None if experiment_dir is None else Path(experiment_dir).resolve()
    study_dir = Path(study_dir).resolve()
    study_dir.mkdir(parents=True, exist_ok=True)
    with file_lock(study_dir / ".lock"):
        manifest = _read_manifest(study_dir)
        sessions = manifest["sessions"]
        report = StudyReport(study_dir, [], [], {}, {})
        pending: list[tuple[str, Path, dict]] = []
        for source in sources:
            pid = source.stem
            key = _session_key(source, source.stat(), session_dir, experiment_dir)
            stored = sessions.get(pid, {}).get("source")
            if stored is not None and stored != key["source"] and not rebuild:
                raise ValueError(
                    f"The study folder {study_dir} holds participant {pid} read "
                    f"from {stored}, not {source}. A recording's file name is its "
                    "participant id; rename one of them, or pass rebuild=True "
                    "(--rebuild) to read this one in its place."
                )
            written = (study_dir / "fixations" / f"{pid}.parquet").is_file()
            if written and not rebuild and _unchanged(sessions.get(pid), key, raw_gaze):
                report.skipped.append(pid)
            else:
                pending.append((pid, source, key))
        if pending:
            _check_dependencies(source for _, source, _ in pending)
        asc_dir = study_dir / "asc" if keep_asc else None
        if asc_dir is not None and any(
            s.suffix.lower() == ".edf" for _, s, _ in pending
        ):
            asc_dir.mkdir(exist_ok=True)
        jobs = [
            {
                "source": source,
                "image_dir": study_dir / "images",
                "session_dir": session_dir,
                "experiment_dir": experiment_dir,
                "raw_gaze": raw_gaze,
                "asc_dir": asc_dir if source.suffix.lower() == ".edf" else None,
            }
            for _, source, _ in pending
        ]
        for done, (i, result) in enumerate(_read_sessions(jobs, workers), start=1):
            pid, source, key = pending[i]
            entry = {
                **key,
                "session_folder": None,
                "raw_gaze": False,
                "status": "failed",
                "error": None,
                "notes": [],
                "display": None,
            }
            if isinstance(result, SessionTables):
                # Marked before its files are written: an import that stops
                # part way through them leaves an entry that is read again.
                sessions[pid] = {**entry, "status": "writing"}
                _write_manifest(study_dir, manifest)
                try:
                    _write_session(study_dir, pid, result)
                except Exception as exc:
                    result = _failure(exc)
            if isinstance(result, SessionTables):
                found = result.session_dir
                entry.update(
                    session_folder=None if found is None else str(found),
                    raw_gaze=result.raw_gaze is not None,
                    status="ok",
                    notes=list(result.notes),
                    display=None if result.display is None else list(result.display),
                )
                report.imported.append(pid)
            else:
                for name in _STUDY_TABLES:
                    (study_dir / name / f"{pid}.parquet").unlink(missing_ok=True)
                entry["error"] = result
                report.failed[pid] = result
            report.notes[pid] = list(entry["notes"])
            sessions[pid] = entry
            del result
            display, _ = _study_display(sessions, _ok_sessions(sessions))
            manifest["display"] = None if display is None else list(display)
            _write_manifest(study_dir, manifest)
            if progress is not None:
                progress(done, len(jobs), pid)
            progress_mod.report(done, len(jobs), unit="sessions", detail=pid)
        for pid, notes in _study_display(sessions, _ok_sessions(sessions))[1].items():
            report.notes.setdefault(pid, []).extend(notes)
    return report


def _concat(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    # Empty sessions are left out so that they do not turn the columns' types
    # into ``object``.
    filled = [frame for frame in frames if len(frame)]
    if not filled:
        return frames[0] if frames else pd.DataFrame(columns=columns)
    joined = pd.concat(filled, ignore_index=True)
    # Sessions show different images, and concat makes categoricals whose
    # categories differ ``object``: their union keeps one shared copy of each.
    if "image_path" in joined.columns and all(
        isinstance(frame["image_path"].dtype, pd.CategoricalDtype) for frame in filled
    ):
        joined["image_path"] = union_categoricals(
            [frame["image_path"] for frame in filled], ignore_order=True
        )
    return joined


def _absolute_image(stored, study_dir: Path) -> str | None:
    """A stored image path made absolute, or ``None`` when it is not a path
    relative to the study folder that stays inside it."""
    path = (study_dir / str(stored)).resolve()
    if Path(str(stored)).is_absolute() or not path.is_relative_to(study_dir):
        return None
    return str(path)


def _absolute_images(
    frame: pd.DataFrame, study_dir: Path, notes: list[str]
) -> pd.DataFrame:
    """``frame`` with each ``image_path`` made absolute, a categorical.  A
    stored path must be relative and lead to a file inside the study folder;
    any other is dropped and noted."""
    if "image_path" not in frame.columns:
        return frame
    outside = set()

    def convert(stored) -> str | None:
        path = _absolute_image(stored, study_dir)
        if path is None:
            outside.add(str(stored))
        return path

    paths = _map_paths(frame["image_path"], convert)
    for p in sorted(outside):
        note = f"The image path {p} leads outside the study folder; it was dropped."
        if note not in notes:
            notes.append(note)
    return frame.assign(image_path=paths)


def load_eyelink(
    study_dir: str | Path,
    *,
    participants: Iterable[str] | None = None,
    raw_gaze: bool | Iterable[str] = False,
) -> EyeLinkData:
    """Read back a study folder `import_eyelink` wrote: every session it read,
    or only ``participants``'.  Sessions that failed are not part of it.

    ``raw_gaze`` is the sessions whose raw gaze is read, of those read: none
    (``False``, the default, since raw gaze is millions of rows per session),
    all of them (``True``), or the participants it names.
    ``EyeLinkData.raw_gaze`` is ``None`` when none of them has raw gaze.

    The frames carry the study's own columns, not yet normalized: pass them
    through `api.load_scanpath_data` before drawing them, or add the study to
    the app with `api.add_eyelink_dataset`::

        data = load_eyelink("study", participants=["p01"])
        words, fixations = load_scanpath_data(data.words, data.fixations)
    """
    _require_enabled("load_eyelink")
    study_dir = Path(study_dir).resolve()
    if not (study_dir / _MANIFEST).is_file():
        raise FileNotFoundError(
            f"{study_dir} is not an EyeLink study folder: it has no {_MANIFEST}."
        )
    if not isinstance(raw_gaze, bool):
        raw_gaze = {str(p) for p in raw_gaze}
    with file_lock(study_dir / ".lock", reading=True):
        return _load_study(study_dir, participants, raw_gaze)


def study_participants(study_dir: str | Path, *, trial: str | None = None) -> list[str]:
    """The participants of a study folder whose sessions were read, sorted;
    with ``trial``, only the first of them whose fixations have that trial
    (an empty list when none has), found by reading each one's ``trial_id``
    column in turn, never the whole study."""
    _require_enabled("study_participants")
    study_dir = Path(study_dir).resolve()
    if not (study_dir / _MANIFEST).is_file():
        raise FileNotFoundError(
            f"{study_dir} is not an EyeLink study folder: it has no {_MANIFEST}."
        )
    with file_lock(study_dir / ".lock", reading=True):
        pids = sorted(_ok_sessions(_read_manifest(study_dir)["sessions"]))
        if trial is None:
            return pids
        for pid in pids:
            path = study_dir / "fixations" / f"{pid}.parquet"
            if not path.is_file():
                continue
            trials = pd.read_parquet(path, columns=["trial_id"])["trial_id"]
            if (trials.astype(str) == str(trial)).any():
                return [pid]
        return []


class SharedScreens(NamedTuple):
    """`shared_screens`' result: the rows kept, how many screens were left
    out and how many fixations were on them."""

    words: pd.DataFrame
    fixations: pd.DataFrame
    raw_gaze: pd.DataFrame | None
    screens_left_out: int
    fixations_left_out: int


_SCREEN_KEYS = ["participant_id", "trial_id", "screen_id"]


def _screen_index(frame: pd.DataFrame) -> pd.MultiIndex:
    """Each row's ``(participant_id, trial_id, screen_id)``, as stored."""
    return pd.MultiIndex.from_arrays([frame[key] for key in _SCREEN_KEYS])


def shared_screens(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    raw_gaze: pd.DataFrame | None = None,
) -> SharedScreens:
    """The rows of the screens both ``words`` and ``fixations`` have, as the
    app shows a screen only when both tables do; ``raw_gaze`` keeps the
    samples of those screens.  When either table is empty, everything is kept
    (a study without word boxes loads its fixations alone).  A frame nothing
    is left out of is returned as it is, not copied.
    """
    _require_enabled("shared_screens")
    if words.empty or fixations.empty:
        return SharedScreens(words, fixations, raw_gaze, 0, 0)
    word_keys, fix_keys = _screen_index(words), _screen_index(fixations)
    shared = word_keys.unique().intersection(fix_keys.unique())
    kept_words, kept_fix = word_keys.isin(shared), fix_keys.isin(shared)
    left_out = len(fix_keys[~kept_fix].unique().union(word_keys[~kept_words].unique()))
    if raw_gaze is not None and not raw_gaze.empty and "screen_id" in raw_gaze:
        kept_gaze = _screen_index(raw_gaze).isin(shared)
        if not kept_gaze.all():
            raw_gaze = raw_gaze[kept_gaze]
    return SharedScreens(
        words if kept_words.all() else words[kept_words],
        fixations if kept_fix.all() else fixations[kept_fix],
        raw_gaze,
        left_out,
        int((~kept_fix).sum()),
    )


def _load_study(
    study_dir: Path, participants: Iterable[str] | None, raw_gaze: bool | set[str]
) -> EyeLinkData:
    sessions = _read_manifest(study_dir)["sessions"]
    ok = sorted(_ok_sessions(sessions))
    if participants is None:
        pids = ok
    else:
        pids = list(dict.fromkeys(str(p) for p in participants))
        unknown = [pid for pid in pids if pid not in ok]
        if unknown:
            raise ValueError(
                f"These participants were not imported into {study_dir}: "
                f"{', '.join(unknown)}."
            )
    display, display_notes = _study_display(sessions, pids)
    notes = {
        pid: [*sessions[pid].get("notes", []), *display_notes.get(pid, [])]
        for pid in pids
    }
    frames: dict[str, list[pd.DataFrame]] = {name: [] for name in _STUDY_TABLES}
    for pid in pids:
        for name in _STUDY_TABLES:
            if name == "raw_gaze" and (
                raw_gaze is False or (raw_gaze is not True and pid not in raw_gaze)
            ):
                continue
            path = study_dir / name / f"{pid}.parquet"
            if path.is_file():
                frame = pd.read_parquet(path)
                frames[name].append(_absolute_images(frame, study_dir, notes[pid]))
    return EyeLinkData(
        words=_concat(frames["words"], WORD_COLUMNS),
        fixations=_concat(frames["fixations"], FIXATION_COLUMNS),
        trial_metadata=_concat(
            frames["trial_metadata"], ["participant_id", "trial_id"]
        ),
        raw_gaze=_concat(frames["raw_gaze"], []) if frames["raw_gaze"] else None,
        display=display,
        notes=notes,
    )
