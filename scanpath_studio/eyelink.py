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
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Trials, screens and the session files Experiment Builder writes
# ---------------------------------------------------------------------------

# An interest-area group belongs to the display that begins within this many
# ms of it.  Experiment Builder logs a group up to 3 ms off its display (OneStop
# sessions: -2 to +3 ms), and two displays are hundreds of ms apart.
IAS_MATCH_MS = 5

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
    ``skipped`` keeps the lines that draw something this reader does not.
    """

    offset: int
    background: tuple[int, int, int]
    images: list[tuple[Path, int, int, int | None, int | None]]
    skipped: list[str] = field(default_factory=list)


def _read_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return []


def _session_path(name: str, session: Path | None) -> Path:
    """A ``!V`` path, which is relative to the session folder."""
    path = Path(name)
    if session is None or path.is_absolute():
        return path
    return Path(os.path.normpath(session / path))


def _image(args: list[str], session: Path | None):
    """``TOP_LEFT <path> x y [w h]`` as an ``images`` entry, else ``None``."""
    if len(args) < 4 or args[0] != "TOP_LEFT":
        return None
    rest = args[1:]
    for size in (4, 2):
        tail = rest[-size:]
        if len(rest) > size and all(re.fullmatch(r"-?\d+", v) for v in tail):
            numbers = [int(v) for v in tail] + [None, None]
            path = _session_path(" ".join(rest[:-size]), session)
            return (path, numbers[0], numbers[1], numbers[2], numbers[3])
    return None


def _colour(args: list[str]) -> tuple[int, int, int] | None:
    """``CLEAR``'s ``r g b`` arguments, else ``None``."""
    if len(args) < 3 or not all(re.fullmatch(r"\d+", v) for v in args[:3]):
        return None
    r, g, b = (int(v) for v in args[:3])
    return r, g, b


def parse_vcl(path: Path, *, session: Path | None = None) -> list[Display]:
    """The displays of a ``.vcl`` draw list: a new one at each ``CLEAR``.

    Image paths in a ``.vcl`` are relative to the session folder (the one the
    recording was made in), not to the ``.vcl``'s own; they are resolved
    against ``session`` when given and kept as written otherwise.
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
        image = _image(args, session) if command == "IMGLOAD" else None
        if image is not None:
            displays[-1].images.append(image)
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
    return pd.DataFrame(rows, columns=["trial_id", "start", "begin", "end"]).astype(
        {"start": "int64", "begin": "int64", "end": "int64"}
    )


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


def trial_vars(rec: AscRecording) -> pd.DataFrame:
    """``trial_id`` and one column per ``!V TRIAL_VAR name value``, in the
    order the names first appear; values are strings."""
    rows, names = [], {}
    for trial, messages in _trial_messages(rec, trial_table(rec)):
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
            image = _image(parts[2:], None)
            name = str(image[0]) if image else None
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
        if candidate is not None and any(
            (Path(candidate) / name).is_file() for name in names
        ):
            return Path(candidate)
    return None


def _session_file(
    name: str, session: Path | None, trial_id: str, lacks: str, notes: list[str]
) -> Path | None:
    """The session file a message names, or ``None`` (noted when the session
    folder is known but lacks it)."""
    if session is None:
        return None
    path = _session_path(name, session)
    if path.is_file():
        return path
    notes.append(f"{name} was not found in {session}; trial {trial_id} {lacks}.")
    return None


def _trial_displays(trial, messages: pd.DataFrame, session: Path | None, notes):
    """The trial's displays as ``(begin, display)``, ``display`` ``None`` for
    a draw list whose ``.vcl`` is missing, and its interest-area groups as
    ``(time, boxes, .ias path, .ias name)``."""
    displays: list[tuple[int, Display | None]] = []
    groups: list[tuple[int, pd.DataFrame, Path | None, str | None]] = []
    inline: dict[int, Display] = {}
    inline_boxes: dict[int, list] = {}
    for time, text in zip(messages["time"], messages["text"]):
        parts = text.split()
        if parts[:2] == ["!V", "DRAW_LIST"] and len(parts) > 2:
            name = text.split(None, 2)[2].strip()
            lacks = "has no stimulus for that draw list"
            path = _session_file(name, session, trial.trial_id, lacks, notes)
            if path is None:
                displays.append((time, None))
                continue
            for display in parse_vcl(path, session=session):
                displays.append((time - display.offset, display))
                notes.extend(f"{name}: skipped {line}" for line in display.skipped)
        elif parts[:3] == ["!V", "IAREA", "FILE"] and len(parts) > 3:
            name = text.split(None, 3)[3].strip()
            lacks = "has no words from it"
            path = _session_file(name, session, trial.trial_id, lacks, notes)
            if path is None:
                continue
            boxes = parse_ias(path)
            notes.extend(f"{name}: skipped {line}" for line in boxes.attrs["skipped"])
            for offset, group in boxes.groupby("offset", sort=False):
                group = group[_BOX_COLUMNS].reset_index(drop=True)
                groups.append((time - int(offset), group, path, name))
        elif parts[:2] == ["!V", "CLEAR"] and _colour(parts[2:]):
            inline[time] = Display(0, _colour(parts[2:]), [])
        elif parts[:2] == ["!V", "IMGLOAD"]:
            image = _image(parts[2:], session)
            display = inline.setdefault(time, Display(0, _WHITE, []))
            if image is None:
                display.skipped.append(text)
                notes.append(f"Trial {trial.trial_id}: skipped {text}")
            else:
                display.images.append(image)
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
        groups.append((time, pd.DataFrame(rows, columns=_BOX_COLUMNS), None, None))
    return displays, groups


def screen_table(
    rec: AscRecording, trials: pd.DataFrame, session: Path | None
) -> tuple[pd.DataFrame, list[str]]:
    """One row per screen of each trial, and notes on what could not be read.

    A screen is a display: each ``CLEAR`` of a ``DRAW_LIST``'s ``.vcl``,
    beginning at the message's time minus the line's offset, or the
    ``!V CLEAR`` / ``!V IMGLOAD`` messages logged at one time.  It lasts until
    the next display or the trial's end; a trial without one is one screen.
    ``boxes`` holds the interest areas (``.ias`` groups or ``!V IAREA
    RECTANGLE`` messages) logged within ``IAS_MATCH_MS`` of its begin, and
    ``ias`` the file they came from.  A draw list whose ``.vcl`` is missing
    still starts a screen, with no ``display``.
    """
    notes: list[str] = []
    rows = []
    for trial, messages in _trial_messages(rec, trials):
        displays, groups = _trial_displays(trial, messages, session, notes)
        displays = [
            (begin, display)
            for begin, display in sorted(displays, key=lambda d: d[0])
            if trial.begin <= begin < trial.end
        ] or [(trial.begin, None)]
        begins = [begin for begin, _ in displays]
        ends = begins[1:] + [trial.end]
        boxes: dict[int, list[pd.DataFrame]] = {}
        sources: dict[int, Path | None] = {}
        for time, group, path, name in groups:
            i = min(range(len(begins)), key=lambda k: abs(begins[k] - time))
            if abs(begins[i] - time) > IAS_MATCH_MS:
                where = f"in {name} " if name else ""
                notes.append(
                    f"Trial {trial.trial_id}: interest areas {where}at {time} ms "
                    "match no display; they were left out."
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
