"""Which build of Scanpath Studio this is (#139).

Releases are cut by hand: ``scanpath_studio.__release__`` is the number
``/release`` bumps and ``publish.yml`` checks a tag against. Between releases
every merge to ``main`` is a different program, so ``__version__`` — and
everything that shows it (About, ``--version``, crash reports, export READMEs,
saved configs) — reports the exact build, worked out from the first source that
knows:

1. a git checkout of this repository (``git describe``);
2. a ``_build.json`` stamp beside the package, which the desktop spec writes;
3. the commit pip recorded for a ``pip install git+…`` (PEP 610);
4. otherwise the release itself — also the answer whenever one of the above
   fails, so a missing ``git`` or a clone without tags breaks nothing.

The result is a PEP 440 version, so builds sort between releases:
``0.35.0 < 0.35.0.post3+g8f18219 < 0.35.1``. Standard library and
``packaging`` only; nothing here touches the network.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

from packaging.version import InvalidVersion, Version

DIST_NAME = "scanpath-studio"
STAMP_NAME = "_build.json"
GIT_TIMEOUT_S = 2.0
_PACKAGE_DIR = Path(__file__).resolve().parent
# `git describe --tags --long --dirty`: v<release>-<distance>-g<hash>[-dirty]
_DESCRIBE = re.compile(
    r"^v(?P<release>.+)-(?P<distance>\d+)-g(?P<commit>[0-9a-f]+)(?P<dirty>-dirty)?$"
)

#: How each kind of install is named to people (``scanpath-studio version``).
INSTALL_KINDS = {
    "desktop": "the desktop app",
    "checkout": "a git checkout",
    "vcs": "pip, from git",
    "uv-tool": "uv tool",
    "pipx": "pipx",
    "uv": "uv pip",
    "pip": "pip",
}


@dataclass(frozen=True)
class BuildInfo:
    """One build: its PEP 440 ``version`` and how that was worked out.

    ``release`` is the release it descends from, ``distance`` the commits since
    (``None`` when unknown), ``commit`` the abbreviated hash, ``dirty`` whether
    tracked files had uncommitted changes, and ``source`` one of
    ``"checkout"``, ``"stamp"``, ``"vcs"`` or ``"release"``. ``vcs_url`` is the
    repository a ``pip install git+…`` came from.
    """

    version: str
    release: str
    distance: int | None = 0
    commit: str = ""
    dirty: bool = False
    source: str = "release"
    vcs_url: str = ""

    def describe(self) -> str:
        """The build in a sentence, relative to its release."""
        if self.source == "vcs":
            return f"Installed from git at {self.commit}, based on v{self.release}"
        if self.distance:
            commits = "commit" if self.distance == 1 else "commits"
            text = (
                f"Development build — {self.distance} {commits} after "
                f"v{self.release}, at {self.commit}"
            )
        elif self.dirty:
            text = f"v{self.release} at {self.commit}"
        else:
            return f"Release v{self.release}"
        return text + (", with uncommitted changes" if self.dirty else "")


def _compose(release: str, distance: int, commit: str, dirty: bool) -> str:
    version = f"{release}.post{distance}" if distance else release
    local = [f"g{commit}"] if (distance or dirty) else []
    if dirty:
        local.append("dirty")
    return version + ("+" + ".".join(local) if local else "")


def from_describe(output: str, source: str = "checkout") -> BuildInfo | None:
    """Read one ``git describe --tags --long --dirty`` line; ``None`` if it isn't one."""
    match = _DESCRIBE.match(output.strip())
    if not match:
        return None
    release, commit = match["release"], match["commit"]
    distance, dirty = int(match["distance"]), bool(match["dirty"])
    version = _compose(release, distance, commit, dirty)
    try:
        Version(version)
    except InvalidVersion:
        return None
    return BuildInfo(version, release, distance, commit, dirty, source)


def _is_this_project(root: Path) -> bool:
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle).get("project")
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return isinstance(project, dict) and project.get("name") == DIST_NAME


def read_checkout(
    root: Path = _PACKAGE_DIR.parent, *, run: Callable = subprocess.run
) -> BuildInfo | None:
    """``git describe`` the checkout at ``root``, when it is this project's.

    Only this repository's own root counts — a ``.git`` there and a
    ``pyproject.toml`` naming ``scanpath-studio`` — so an install in a venv that
    happens to sit inside some other repository is never described by it.
    """
    if not (root / ".git").exists() or not _is_this_project(root):
        return None
    try:
        done = run(
            [
                "git",
                "-C",
                str(root),
                "describe",
                "--tags",
                "--long",
                "--dirty",
                "--match",
                "v[0-9]*",
            ],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return from_describe(done.stdout) if done.returncode == 0 else None


def write_stamp(info: BuildInfo, path: Path) -> None:
    """Write ``info`` where :func:`read_stamp` finds it (the desktop spec's step)."""
    path.write_text(json.dumps(asdict(info)), encoding="utf-8")


def read_stamp(path: Path = _PACKAGE_DIR / STAMP_NAME) -> BuildInfo | None:
    """The build a desktop bundle was made from, as its spec stamped it."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        info = BuildInfo(**{**data, "source": "stamp"})
        Version(info.version)
    except (OSError, ValueError, TypeError):
        return None
    return info


def _dist_text(name: str) -> str | None:
    """A file from this distribution's installed metadata, or ``None``."""
    from importlib import metadata

    try:
        return metadata.distribution(DIST_NAME).read_text(name)
    except metadata.PackageNotFoundError:
        return None


def read_vcs_install(
    release: str, *, read_text: Callable[[str], str | None] = _dist_text
) -> BuildInfo | None:
    """The commit pip recorded for ``pip install git+…`` (``direct_url.json``)."""
    try:
        data = json.loads(read_text("direct_url.json") or "")
    except ValueError:
        return None
    vcs = data.get("vcs_info") if isinstance(data, dict) else None
    if not isinstance(vcs, dict) or vcs.get("vcs") != "git" or not vcs.get("commit_id"):
        return None
    commit = str(vcs["commit_id"])[:7]
    return BuildInfo(
        f"{release}+g{commit}",
        release,
        None,
        commit,
        False,
        "vcs",
        str(data.get("url") or ""),
    )


def resolve(
    release: str,
    *,
    root: Path = _PACKAGE_DIR.parent,
    stamp: Path = _PACKAGE_DIR / STAMP_NAME,
    run: Callable = subprocess.run,
    read_text: Callable[[str], str | None] = _dist_text,
) -> BuildInfo:
    """The first source that knows this build; the release itself otherwise."""
    return (
        read_checkout(root, run=run)
        or read_stamp(stamp)
        or read_vcs_install(release, read_text=read_text)
        or BuildInfo(release, release)
    )


@cache
def build_info() -> BuildInfo:
    """This process's build, worked out once — ``scanpath_studio.__version__``."""
    from scanpath_studio import __release__

    return resolve(__release__)


def install_kind(
    info: BuildInfo | None = None,
    *,
    frozen: bool | None = None,
    prefix: str | None = None,
    installer: str | None = None,
) -> str:
    """How this copy was installed — a key of :data:`INSTALL_KINDS`.

    It decides the update instruction (``updates.update_command``). The desktop
    bundle is frozen; a checkout or a ``pip install git+…`` says so through
    ``info``; ``uv tool`` and pipx are recognised by where their environments
    live; uv by the ``INSTALLER`` file it records; anything else is pip.
    """
    if getattr(sys, "frozen", False) if frozen is None else frozen:
        return "desktop"
    info = build_info() if info is None else info
    if info.source in ("checkout", "vcs"):
        return info.source
    where = Path(sys.prefix if prefix is None else prefix).as_posix().lower()
    if "/uv/tools/" in where:
        return "uv-tool"
    if "/pipx/venvs/" in where:
        return "pipx"
    if installer is None:
        installer = _dist_text("INSTALLER") or ""
    return "uv" if installer.strip().lower() == "uv" else "pip"
