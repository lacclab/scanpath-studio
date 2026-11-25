"""EyeLink EDF import (experimental).

EDF recordings are converted to ASC with SR Research's ``edf2asc``, which is
found on the user's machine and never bundled or downloaded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

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
