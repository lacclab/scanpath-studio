"""EyeLink EDF import (experimental).

EDF recordings are converted to ASC with SR Research's ``edf2asc``, which is
found on the user's machine and never bundled or downloaded.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scanpath_studio import constants

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


_MISSING_PYMOVEMENTS = (
    'Reading EyeLink recordings needs pymovements: pip install "scanpath-studio[edf]"'
)
# pymovements warns about every header an events-only ASC lacks.
_QUIET_PYMOVEMENTS = (r"No .* found", r"Missing start marker")
_MESSAGE_OFFSET = re.compile(r"^(-?\d+)\s+(.*)$", re.DOTALL)
_DISPLAY_COORDS = re.compile(r"^DISPLAY_COORDS\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)")
_EYE_LETTER = {"left": "L", "right": "R"}


def _parse_asc(path: Path):
    try:
        import pymovements as pm
    except ImportError as exc:
        raise ImportError(_MISSING_PYMOVEMENTS) from exc
    for encoding in ("utf-8", "latin-1"):
        try:
            with warnings.catch_warnings():
                for pattern in _QUIET_PYMOVEMENTS:
                    warnings.filterwarnings("ignore", message=pattern)
                gaze = pm.gaze.from_asc(
                    path, events=True, messages=True, encoding=encoding
                )
            return gaze, encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path.name} is not readable as UTF-8 or latin-1 text.")


def _scan_lines(path: Path, encoding: str):
    """The facts pymovements does not keep: each EFIX line's position and
    duration, the START / END lines, and the eyes recorded."""
    efix: dict[tuple[str, int], tuple[int, float, float]] = {}
    order: list[tuple[str, int]] = []
    eyes: tuple[str, ...] = ()
    with open(path, encoding=encoding, newline="") as handle:
        for line in handle:
            if line.startswith("EFIX"):
                f = line.split()
                efix[(f[1], int(f[2]))] = (int(f[4]), float(f[5]), float(f[6]))
            elif line.startswith("START"):
                f = line.split()
                time = int(f[1])
                order.append(("start", time))
                if not eyes:
                    eyes = tuple(
                        _EYE_LETTER[t.lower()]
                        for t in f[2:]
                        if t.lower() in _EYE_LETTER
                    )
            elif line.startswith("END"):
                f = line.split()
                order.append(("end", int(f[1])))
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
    return efix, blocks, eyes


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
    columns = ["time", "x", "y", "pupil", "eye"]
    if frame.height == 0 or not eyes:
        return pd.DataFrame(columns=columns)
    time = frame["time"].to_numpy()
    pixel = np.array(frame["pixel"].to_list(), dtype=float)
    pupil = np.array(frame["pupil"].to_list(), dtype=float).reshape(len(time), -1)
    parts = []
    for i, eye in enumerate(eyes):
        x, y = pixel[:, 2 * i], pixel[:, 2 * i + 1]
        p = pupil[:, i].copy()
        p[np.isnan(x) | np.isnan(y)] = np.nan
        parts.append(
            pd.DataFrame({"time": time, "x": x, "y": y, "pupil": p, "eye": eye})
        )
    return pd.concat(parts, ignore_index=True)[columns].sort_values(
        ["time", "eye"], kind="stable", ignore_index=True
    )


def read_asc(path: Path, *, samples: bool = False) -> AscRecording:
    """Read an EyeLink ASC file: its fixation events, messages, recording blocks
    and display size, and with ``samples`` its raw gaze samples."""
    _require_enabled("read_asc")
    path = Path(path)
    gaze, encoding = _parse_asc(path)
    efix, blocks, eyes = _scan_lines(path, encoding)
    messages = _message_frame(gaze.messages)
    return AscRecording(
        fixations=_fixation_frame(gaze.events.frame, efix),
        messages=messages,
        blocks=pd.DataFrame(blocks, columns=["start", "end"]).astype(
            {"start": "int64", "end": "Int64"}
        ),
        samples=_sample_frame(gaze.samples, eyes) if samples else None,
        display=_display_size(messages),
    )
