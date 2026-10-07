# #139 phase 1 — Build versions + *Check for updates* Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every build of Scanpath Studio reports its own PEP 440 version (`0.35.0.post3+g8f18219` between releases), and a user can ask — in Help → About, `scanpath-studio version --check` or `api.check_for_updates()` — whether a newer release is out and how to update their install.

**Architecture:** The hand-set release literal is renamed `__release__` (what `/release` bumps and `publish.yml` gates on); `__version__` becomes the exact build, resolved lazily by a new stdlib-only `build_info.py` from a git checkout, a desktop build stamp, or pip's `direct_url.json`, falling back to the release. A new stdlib-only `updates.py` reads GitHub's latest release on request and compares it with the build. The About dialog, a `version` CLI subcommand and two `api.py` functions are thin surfaces over those two modules.

**Tech Stack:** Python ≥3.11 stdlib (`subprocess`, `urllib.request`, `tomllib`, `json`), `packaging` (`Version`), Streamlit 1.65 (`st.dialog`, `st.cache_data`, `AppTest`), argparse, PyInstaller spec, GitHub Actions, MkDocs.

**Spec:** [`plans/139-build-versions-and-updates.md`](139-build-versions-and-updates.md) — Sections 1 and 2. Section 3 (one-click desktop update, #385) is a separate plan and PR.

## Global Constraints

- Work in the worktree `/Users/shubi/Projects/scanpath_studio/app/.claude/worktrees/build-versions-and-updates`, branch `build-versions-and-updates`. Never edit the main checkout.
- Toolchain: `uv run --extra test --extra lint …` for pytest and ruff (bare `python3`/`pytest`/`ruff` on PATH are a different interpreter and ruff version). Docs: `uv run --extra docs mkdocs build --strict` (no `-q`; check the exit code).
- `from __future__ import annotations` at the top of every new Python file.
- Run `uv run --extra lint ruff check --fix .` and `uv run --extra lint ruff format .` before every commit.
- Commit subjects carry `(#139)`. **No `Co-Authored-By` trailer** (repo rule).
- Icons drawn as chrome come from `constants.ICONS` — never a literal emoji or `:material/…:` in `app.py` (`tests/test_icons.py`).
- Version formats (exact): at the tag `0.35.0`; N commits after `0.35.0.postN+g<hash>`; plus `.dirty` in the local part for uncommitted tracked changes (`0.35.0.post3+g8f18219.dirty`, `0.35.0+g8f18219.dirty` at the tag); `pip install git+…` `0.35.0+g<7-char hash>`.
- The network is used **only** on an explicit request: the About button, `version --check`, `api.check_for_updates()`. Endpoint: `https://api.github.com/repos/lacclab/scanpath-studio/releases/latest`; timeout 5 s.
- The About button is hidden unless `persistence.server_bound_to_loopback()` (the hosted demo never shows it).
- The app never runs pip; it shows the command.
- Add the dependency `packaging>=26.3` (imported directly from now on).

---

### Task 1: `build_info.py` — which build this is

**Files:**
- Create: `scanpath_studio/build_info.py`
- Create: `tests/test_build_info.py`
- Modify: `pyproject.toml` (dependencies)
- Modify: `AGENTS.md` (architecture map), `scanpath_studio/CLAUDE.md` (Modules list)

**Interfaces:**
- Consumes: `scanpath_studio.__release__` (added in Task 2 — `build_info()` imports it lazily; Tasks 1's tests never call `build_info()`).
- Produces:
  - `BuildInfo(version: str, release: str, distance: int | None = 0, commit: str = "", dirty: bool = False, source: str = "release", vcs_url: str = "")` — frozen dataclass with `describe() -> str`.
  - `from_describe(output: str, source: str = "checkout") -> BuildInfo | None`
  - `read_checkout(root: Path = …, *, run=subprocess.run) -> BuildInfo | None`
  - `write_stamp(info: BuildInfo, path: Path) -> None`, `read_stamp(path: Path = …) -> BuildInfo | None`
  - `read_vcs_install(release: str, *, read_text=…) -> BuildInfo | None`
  - `resolve(release: str, *, root, stamp, run, read_text) -> BuildInfo`
  - `build_info() -> BuildInfo` (cached)
  - `install_kind(info=None, *, frozen=None, prefix=None, installer=None) -> str` — one of the keys of `INSTALL_KINDS`
  - `INSTALL_KINDS: dict[str, str]`, `DIST_NAME = "scanpath-studio"`, `STAMP_NAME = "_build.json"`

- [ ] **Step 1: Add the `packaging` dependency**

In `pyproject.toml`, in `dependencies = [ … ]`, directly after the `"streamlit>=1.65.0",` line, add:

```toml
    # Build versions sort and compare as PEP 440 (`build_info.py`, `updates.py`, #139).
    "packaging>=26.3",
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_build_info.py`:

```python
"""The build version (#139): which build of Scanpath Studio this is."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

from scanpath_studio import build_info as bi


def _project(root: Path, name: str = "scanpath-studio") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\n', encoding="utf-8"
    )
    return root


def _git(stdout: str = "", returncode: int = 0):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    run.calls = calls
    return run


def _dist(files: dict[str, str]):
    return lambda name: files.get(name)


@pytest.mark.parametrize(
    ("described", "expected"),
    [
        ("v0.35.0-0-g8f18219", "0.35.0"),
        ("v0.35.0-3-g8f18219", "0.35.0.post3+g8f18219"),
        ("v0.35.0-3-g8f18219-dirty", "0.35.0.post3+g8f18219.dirty"),
        ("v0.35.0-0-g8f18219-dirty", "0.35.0+g8f18219.dirty"),
        ("v0.36.0b1-2-gabcdef12", "0.36.0b1.post2+gabcdef12"),
    ],
)
def test_a_describe_line_becomes_a_pep440_build(described, expected):
    info = bi.from_describe(described + "\n")
    assert info.version == expected
    assert str(Version(expected)) == expected  # valid, and already normal form
    assert info.source == "checkout"


def test_a_describe_line_keeps_its_parts():
    info = bi.from_describe("v0.35.0-3-g8f18219-dirty")
    assert (info.release, info.distance, info.commit, info.dirty) == (
        "0.35.0",
        3,
        "8f18219",
        True,
    )


@pytest.mark.parametrize(
    "junk", ["", "8f18219", "release-1-gabc1234", "v0.35.0", "vnope-1-gabc1234"]
)
def test_anything_else_is_not_a_describe_line(junk):
    assert bi.from_describe(junk) is None


def test_builds_sort_between_releases():
    assert Version("0.35.0") < Version("0.35.0.post3+g8f18219") < Version("0.35.1")


def test_a_checkout_is_described_by_git(tmp_path):
    run = _git("v0.35.0-3-g8f18219\n")
    info = bi.read_checkout(_project(tmp_path), run=run)
    assert info.version == "0.35.0.post3+g8f18219"
    assert run.calls[0][:4] == ["git", "-C", str(tmp_path), "describe"]
    assert run.calls[0][-2:] == ["--match", "v[0-9]*"]


def test_a_venv_inside_someone_elses_repo_is_not_described(tmp_path):
    run = _git("v9.9.9-1-gabc1234\n")
    assert bi.read_checkout(_project(tmp_path, name="their-project"), run=run) is None
    assert run.calls == []


def test_without_a_git_dir_git_is_not_run(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "scanpath-studio"\n')
    run = _git("v0.35.0-0-gabc1234")
    assert bi.read_checkout(tmp_path, run=run) is None
    assert run.calls == []


@pytest.mark.parametrize(
    "failure", [FileNotFoundError("git"), subprocess.TimeoutExpired("git", 2)]
)
def test_git_missing_or_hung_falls_through(tmp_path, failure):
    def run(cmd, **kwargs):
        raise failure

    assert bi.read_checkout(_project(tmp_path), run=run) is None


def test_a_clone_without_tags_falls_through(tmp_path):
    assert bi.read_checkout(_project(tmp_path), run=_git("", returncode=128)) is None


def test_a_stamp_round_trips(tmp_path):
    path = tmp_path / "_build.json"
    bi.write_stamp(bi.from_describe("v0.35.0-3-g8f18219"), path)
    stamped = bi.read_stamp(path)
    assert stamped.version == "0.35.0.post3+g8f18219"
    assert stamped.source == "stamp"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        json.dumps([1]),
        json.dumps({"version": "1"}),
        json.dumps({"version": "not a version", "release": "0.35.0"}),
    ],
)
def test_a_missing_or_broken_stamp_is_ignored(tmp_path, content):
    path = tmp_path / "_build.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert bi.read_stamp(path) is None


def test_a_pip_install_from_git_names_its_commit():
    direct_url = json.dumps(
        {
            "url": "https://github.com/lacclab/scanpath-studio",
            "vcs_info": {"vcs": "git", "commit_id": "8f182193aa11bb22cc33dd44ee55ff66"},
        }
    )
    info = bi.read_vcs_install(
        "0.35.0", read_text=_dist({"direct_url.json": direct_url})
    )
    assert info.version == "0.35.0+g8f18219"
    assert (info.source, info.distance, info.commit, info.vcs_url) == (
        "vcs",
        None,
        "8f18219",
        "https://github.com/lacclab/scanpath-studio",
    )


@pytest.mark.parametrize(
    "direct_url",
    [
        None,
        "{",
        json.dumps({"url": "file:///src", "dir_info": {"editable": True}}),
        json.dumps({"url": "x", "vcs_info": {"vcs": "hg", "commit_id": "abc"}}),
    ],
)
def test_other_installs_are_not_vcs(direct_url):
    files = {} if direct_url is None else {"direct_url.json": direct_url}
    assert bi.read_vcs_install("0.35.0", read_text=_dist(files)) is None


def test_resolve_takes_the_first_source_that_knows(tmp_path):
    root = _project(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    stamp = tmp_path / "_build.json"
    bi.write_stamp(bi.from_describe("v0.34.0-5-gabcdef1"), stamp)
    no_stamp = tmp_path / "none.json"
    direct = _dist(
        {
            "direct_url.json": json.dumps(
                {"url": "u", "vcs_info": {"vcs": "git", "commit_id": "1234567890"}}
            )
        }
    )
    git = _git("v0.35.0-3-g8f18219")

    def source(**kwargs):
        args = {"root": root, "stamp": stamp, "run": git, "read_text": direct}
        return bi.resolve("0.35.0", **{**args, **kwargs}).source

    assert source() == "checkout"
    assert source(root=elsewhere) == "stamp"
    assert source(root=elsewhere, stamp=no_stamp) == "vcs"
    plain = bi.resolve(
        "0.35.0", root=elsewhere, stamp=no_stamp, run=git, read_text=_dist({})
    )
    assert plain == bi.BuildInfo("0.35.0", "0.35.0")


@pytest.mark.parametrize(
    ("info", "text"),
    [
        (bi.BuildInfo("0.35.0", "0.35.0"), "Release v0.35.0"),
        (
            bi.from_describe("v0.35.0-1-g8f18219"),
            "Development build — 1 commit after v0.35.0, at 8f18219",
        ),
        (
            bi.from_describe("v0.35.0-3-g8f18219-dirty"),
            "Development build — 3 commits after v0.35.0, at 8f18219, "
            "with uncommitted changes",
        ),
        (
            bi.from_describe("v0.35.0-0-g8f18219-dirty"),
            "v0.35.0 at 8f18219, with uncommitted changes",
        ),
        (
            bi.BuildInfo("0.35.0+g8f18219", "0.35.0", None, "8f18219", source="vcs"),
            "Installed from git at 8f18219, based on v0.35.0",
        ),
    ],
)
def test_describe_says_it_in_a_sentence(info, text):
    assert info.describe() == text


_RELEASE = bi.BuildInfo("0.35.0", "0.35.0")


@pytest.mark.parametrize(
    ("overrides", "kind"),
    [
        ({"frozen": True}, "desktop"),
        ({"info": bi.from_describe("v0.35.0-3-g8f18219")}, "checkout"),
        (
            {
                "info": bi.BuildInfo(
                    "0.35.0+gabc1234", "0.35.0", None, "abc1234", source="vcs"
                )
            },
            "vcs",
        ),
        ({"prefix": "/home/r/.local/share/uv/tools/scanpath-studio"}, "uv-tool"),
        ({"prefix": "/home/r/.local/share/pipx/venvs/scanpath-studio"}, "pipx"),
        ({"prefix": "/home/r/project/.venv", "installer": "uv\n"}, "uv"),
        ({"prefix": "/home/r/project/.venv", "installer": "pip"}, "pip"),
        ({"prefix": "/opt/conda/envs/eye", "installer": ""}, "pip"),
    ],
)
def test_install_kind(overrides, kind):
    args = {"info": _RELEASE, "frozen": False, "prefix": "/usr", "installer": "pip"}
    assert bi.install_kind(**{**args, **overrides}) == kind


def test_every_install_kind_has_a_name():
    assert set(bi.INSTALL_KINDS) == {
        "desktop",
        "checkout",
        "vcs",
        "uv-tool",
        "pipx",
        "uv",
        "pip",
    }
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --extra test --extra lint pytest tests/test_build_info.py -q`
Expected: collection ERROR — `ImportError: cannot import name 'build_info' from 'scanpath_studio'` (or `ModuleNotFoundError`).

- [ ] **Step 4: Write `scanpath_studio/build_info.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test --extra lint pytest tests/test_build_info.py -q`
Expected: all pass.

- [ ] **Step 6: Document the module**

In `AGENTS.md`, directly after the line beginning `├─ crash_report.py`, insert:

```text
├─ build_info.py     #139: which build this is — `__version__` is the hand-set `__release__` at a release, else a PEP 440 build (`0.35.0.post3+g8f18219`) from `git describe` in a checkout of this repo, a desktop bundle's `_build.json` stamp, or a `pip install git+…`'s `direct_url.json`; plus `install_kind` (desktop / checkout / vcs / uv-tool / pipx / uv / pip). Never raises, no network
```

In `scanpath_studio/CLAUDE.md`, directly after the bullet beginning `- [easter_egg.py](easter_egg.py)`, insert:

```markdown
- [build_info.py](build_info.py) — **#139** which build this is. `__version__` resolves lazily (the package `__getattr__`) to `build_info().version`: `git describe --tags --long --dirty --match "v[0-9]*"` when the package's parent is *this* repo's root (a `.git` and a `pyproject.toml` named `scanpath-studio` — never a venv that happens to sit inside another repo), else a `_build.json` beside the package (the desktop spec writes it), else pip's `direct_url.json` commit, else `__release__` exactly. Every failure falls through, so a shallow clone (CI's `fetch-depth: 1`, maybe Community Cloud) reports the release. `__release__` is what `/release` bumps, `pyproject.toml` builds with and `publish.yml` gates on; a test that compares versions must not assume a checkout has tags.
```

- [ ] **Step 7: Lint and commit**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add pyproject.toml scanpath_studio/build_info.py tests/test_build_info.py AGENTS.md scanpath_studio/CLAUDE.md
git commit -m "Work out the exact build version from git, a stamp or pip (#139)"
```

---

### Task 2: `__release__` + the build as `__version__`, everywhere the version is read

**Files:**
- Modify: `scanpath_studio/__init__.py`
- Modify: `pyproject.toml` (`[tool.setuptools.dynamic]`)
- Modify: `tests/test_citation.py`
- Modify: `tests/test_build_info.py` (wiring tests)
- Modify: `.github/workflows/publish.yml:26-28`
- Modify: `.github/workflows/desktop.yml` (build job checkout)
- Modify: `desktop/scanpath_studio.spec`, `desktop/launcher.py` (`selfcheck`)
- Modify: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.claude/skills/release/SKILL.md`
- Create: `changelog.d/139.changed.md`

**Interfaces:**
- Consumes: `build_info.build_info()`, `build_info.read_checkout(root)`, `build_info.write_stamp(info, path)`, `build_info.STAMP_NAME` (Task 1).
- Produces: `scanpath_studio.__release__: str` (literal); `scanpath_studio.__version__` → `build_info().version` (lazy).

- [ ] **Step 1: Write the failing wiring tests**

Append to `tests/test_build_info.py`:

```python
ROOT = Path(__file__).resolve().parents[1]


def test_dunder_version_is_the_build():
    import scanpath_studio

    assert scanpath_studio.__version__ == bi.build_info().version
    assert Version(scanpath_studio.__version__)  # always PEP 440


def test_the_release_literal_is_what_builds_and_gates_read():
    init = (ROOT / "scanpath_studio" / "__init__.py").read_text(encoding="utf-8")
    assert re.search(r'^__release__ = "[^"]+"$', init, re.MULTILINE)
    assert not re.search(r"^__version__ = ", init, re.MULTILINE)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'attr = "scanpath_studio.__release__"' in pyproject
    publish = (ROOT / ".github" / "workflows" / "publish.yml").read_text(
        encoding="utf-8"
    )
    assert "s/^__release__ = " in publish
```

And add `import re` to the file's imports (after `import json`).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra test --extra lint pytest tests/test_build_info.py -q -k "dunder or literal"`
Expected: FAIL — `__release__` is not in `__init__.py` (and `build_info()` raises `ImportError: cannot import name '__release__'`).

- [ ] **Step 3: Rename the literal and resolve `__version__` lazily**

In `scanpath_studio/__init__.py`, replace the line `__version__ = "0.35.0"` with:

```python
# The release this tree descends from: the number `/release` bumps (with
# CITATION.cff), `pyproject.toml` builds with, and publish.yml checks a tag
# against. `__version__` is the exact build, worked out from it lazily
# (build_info.py, #139) — "0.35.0" at the release itself,
# "0.35.0.post3+g8f18219" three commits after it.
__release__ = "0.35.0"
```

In the same file's `__getattr__`, add as its first branch:

```python
    if name == "__version__":
        from .build_info import build_info

        # Worked out once (it may run `git describe`), then a plain attribute.
        globals()["__version__"] = build_info().version
        return globals()["__version__"]
```

(`__all__` keeps `"__version__"`; `_API_EXPORTS` already subtracts it.)

- [ ] **Step 4: Point the build, the citation test and the publish gate at `__release__`**

`pyproject.toml`:

```toml
[tool.setuptools.dynamic]
# Single source of truth for the release number: scanpath_studio.__release__
# (`__version__` is the exact build, worked out from it at runtime — #139).
version = { attr = "scanpath_studio.__release__" }
```

`tests/test_citation.py`: change `from scanpath_studio import __version__` to `from scanpath_studio import __release__`, and in `test_citation_cff_version_matches_package` replace both uses of `__version__` with `__release__` (the assertion and its message).

`.github/workflows/publish.yml`, step *Tag matches the package version*:

```yaml
        run: |
          VERSION="$(sed -n 's/^__release__ = "\(.*\)"$/\1/p' scanpath_studio/__init__.py)"
          if [ "${GITHUB_REF_NAME#v}" != "$VERSION" ]; then
            echo "::error::Tag ${GITHUB_REF_NAME} does not match __release__ ${VERSION} — bump scanpath_studio/__init__.py (and CITATION.cff) before tagging."
            exit 1
          fi
```

- [ ] **Step 5: Run the version tests**

Run: `uv run --extra test --extra lint pytest tests/test_build_info.py tests/test_citation.py tests/test_cli.py -q -k "version or citation or dunder or literal"`
Expected: PASS (`test_cli.py::test_version` still holds — `--version` prints `__version__`).

- [ ] **Step 6: Stamp desktop bundles with the build**

`desktop/scanpath_studio.spec` — replace `from scanpath_studio import __version__` with:

```python
import tempfile
from pathlib import Path

from scanpath_studio import __release__
from scanpath_studio.build_info import STAMP_NAME, read_checkout, write_stamp
```

(keep `import os` / `re` / `sys` above it; move `import tempfile` / `from pathlib import Path` into the stdlib import block so ruff's isort is satisfied). After the `hiddenimports += ["streamlit_sortables", …]` line, add:

```python
# #139: the bundle reports the exact build it was made from. The spec runs in
# the repository (CI checks it out with fetch-depth 0, so the tag is visible)
# while `scanpath_studio` is imported from site-packages, so describe the
# checkout explicitly and ship the answer as _build.json, which build_info
# reads ahead of the release literal. A build from an exact tag stamps the
# release itself; no checkout (an sdist build) stamps nothing.
_build = read_checkout(Path(SPECPATH).parent)  # noqa: F821
if _build is not None:
    _stamp = Path(tempfile.mkdtemp(prefix="scanpath-build-")) / STAMP_NAME
    write_stamp(_build, _stamp)
    datas.append((str(_stamp), "scanpath_studio"))
```

and in the macOS block change `re.match(r"\d+(?:\.\d+){0,2}", __version__)` to `re.match(r"\d+(?:\.\d+){0,2}", __release__)`.

`desktop/launcher.py` `selfcheck()` — make the build visible in CI logs: change the final success line to

```python
from scanpath_studio import __version__

print(
    f"selfcheck ok: v{__version__}, {len(combos)} trials, figure HTML {len(html)} bytes"
)
```

`.github/workflows/desktop.yml`, `build` job, the first step `- uses: actions/checkout@v7` becomes:

```yaml
      - uses: actions/checkout@v7
        with:
          # #139: the spec stamps the bundle from `git describe`, which needs
          # the tags — a dispatched build of main then reports its own build.
          fetch-depth: 0
```

(Only the `build` job; the `release` job's checkout is unchanged.)

Check the spec still parses: `uv run python -c "import ast, pathlib; ast.parse(pathlib.Path('desktop/scanpath_studio.spec').read_text())"` → no output.

- [ ] **Step 7: Update the release instructions**

`AGENTS.md`:
- In the architecture tree, `├─ __init__.py       exposes __version__, main(), and lazy re-exports of the api.py surface` → `├─ __init__.py       exposes __release__ (the hand-set release), __version__ (the exact build, lazily — build_info.py), main(), and lazy re-exports of the api.py surface`.
- *Releasing* step 2 → ``2. Bump `__release__` in `scanpath_studio/__init__.py` — the single source of truth for the release number; `pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic]`). `__version__` is worked out from it at runtime (#139).``
- *Releasing* step 4: `does not match `__version__`, ENG-62` → `does not match `__release__`, ENG-62`.

`CLAUDE.md` *On release*: `bump `__version__` in` → `bump `__release__` in`.

`CONTRIBUTING.md`:
- *Versioning* paragraph becomes:

  ```markdown
  The release number lives in **one** place — `__release__` in
  [`scanpath_studio/__init__.py`](scanpath_studio/__init__.py).
  `pyproject.toml` reads it dynamically, so bump only that file.
  `scanpath_studio.__version__` is the exact build, worked out at runtime: the
  release itself, or between releases `0.35.0.post3+g8f18219` — three commits
  after v0.35.0, at commit `8f18219` (#139).
  ```
- *Releasing* step 2: `Bump `__version__` in` → `Bump `__release__` in`.
- *Releasing* step 4: `does not match\n   `__version__` (ENG-62)` → `does not match\n   `__release__` (ENG-62)`.

`.claude/skills/release/SKILL.md`: replace every `__version__` with `__release__` — four places: the `description:` line, *the current `__version__`* in the intro, step 3 *Version bump* (`set `__version__` in`), and step 9's ENG-62 sentence (`does not match `__version__``). Then `grep -n __version__ .claude/skills/release/SKILL.md` prints nothing.

- [ ] **Step 8: Changelog fragment**

Create `changelog.d/139.changed.md` (one line, no bullet):

```text
Every build now reports its own version: between releases it is a development build such as 0.35.0.post3+g8f18219 (three commits after 0.35.0), shown in About, scanpath-studio --version, crash reports and exports, and as scanpath_studio.__version__; the hand-set release number is scanpath_studio.__release__.
```

Run: `uv run python scripts/changelog_fragments.py check` → passes.

- [ ] **Step 9: Run the touched tests, lint, commit**

```bash
uv run --extra test --extra lint pytest tests/test_build_info.py tests/test_citation.py tests/test_cli.py tests/test_export.py -q -n auto
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add -A scanpath_studio/__init__.py pyproject.toml tests/test_citation.py tests/test_build_info.py .github/workflows/publish.yml .github/workflows/desktop.yml desktop/scanpath_studio.spec desktop/launcher.py AGENTS.md CLAUDE.md CONTRIBUTING.md .claude/skills/release/SKILL.md changelog.d/139.changed.md
git commit -m "Report the exact build as __version__; the release number is __release__ (#139)"
```

Expected: tests PASS.

---

### Task 3: `updates.py` — is there a newer release?

**Files:**
- Create: `scanpath_studio/updates.py`
- Create: `tests/test_updates.py`
- Modify: `AGENTS.md` (architecture map), `scanpath_studio/CLAUDE.md` (Modules list)

**Interfaces:**
- Consumes: `build_info.BuildInfo`, `build_info.build_info()`, `build_info.install_kind(info)`, `build_info.from_describe` (tests).
- Produces:
  - `Asset(name: str, url: str, size: int = 0, digest: str = "")`
  - `Release(version: str, tag: str, published_at: str, url: str, assets: tuple[Asset, ...] = ())` with `asset(name) -> Asset | None`
  - `UpdateCheck(status: str, current: str, message: str, latest: Release | None = None, install_kind: str = "pip", command: str = "", download: Asset | None = None)` — `status` ∈ `"up_to_date" | "update_available" | "ahead" | "error"`
  - `UpdateCheckError(Exception)`
  - `latest_release(timeout: float = TIMEOUT_S, *, opener=urllib.request.urlopen) -> Release` (raises `UpdateCheckError`)
  - `check_for_updates(timeout: float = TIMEOUT_S, *, latest: Callable[[], Release] | None = None, info: BuildInfo | None = None, kind: str | None = None) -> UpdateCheck` (never raises)
  - `update_command(kind: str, info: BuildInfo) -> str`, `desktop_archive(system=None, machine=None) -> str | None`
  - Constants `REPO`, `LATEST_RELEASE_API`, `RELEASES_PAGE`, `TIMEOUT_S = 5.0`, `UPDATE_COMMANDS`, `DESKTOP_ARCHIVES`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_updates.py`:

```python
"""Check for updates (#139): the GitHub lookup and the comparison."""

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

from scanpath_studio import updates
from scanpath_studio.build_info import BuildInfo, from_describe

RELEASE = BuildInfo("0.35.0", "0.35.0")
DEV = from_describe("v0.35.0-3-g8f18219")
ROOT = Path(__file__).resolve().parents[1]


def _payload(tag="v0.36.0", assets=()):
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/lacclab/scanpath-studio/releases/tag/{tag}",
        "published_at": "2026-10-09T10:00:00Z",
        "assets": [
            {
                "name": name,
                "browser_download_url": f"https://example.test/{name}",
                "size": 1024,
                "digest": "sha256:ab",
            }
            for name in assets
        ],
    }


def _opener(payload=None, error=None):
    seen = []

    def opener(request, timeout):
        seen.append((request, timeout))
        if error is not None:
            raise error
        return io.BytesIO(json.dumps(payload).encode())

    opener.seen = seen
    return opener


def _http_error(code, headers=None):
    hdrs = Message()
    for key, value in (headers or {}).items():
        hdrs[key] = value
    return urllib.error.HTTPError(updates.LATEST_RELEASE_API, code, "nope", hdrs, None)


def _latest(tag="v0.36.0", assets=()):
    # Parsed directly, not through `latest_release`, which some tests replace.
    release = updates._release_from(_payload(tag, assets))
    return lambda: release


def test_latest_release_reads_githubs_answer():
    opener = _opener(_payload(assets=["ScanpathStudio-macos-arm64.dmg"]))
    release = updates.latest_release(3.0, opener=opener)
    assert (release.version, release.tag) == ("0.36.0", "v0.36.0")
    assert release.asset("ScanpathStudio-macos-arm64.dmg").digest == "sha256:ab"
    assert release.asset("nothing.zip") is None
    request, timeout = opener.seen[0]
    assert request.full_url == updates.LATEST_RELEASE_API
    assert timeout == 3.0
    assert request.get_header("User-agent").startswith("scanpath-studio/")


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (urllib.error.URLError("no route"), "are you offline"),
        (TimeoutError("slow"), "are you offline"),
        (
            _http_error(
                403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1791500000"}
            ),
            "limit on checks",
        ),
        (_http_error(404), "no published release"),
        (_http_error(502), "HTTP 502"),
    ],
)
def test_a_failed_lookup_says_why(error, reason):
    with pytest.raises(updates.UpdateCheckError, match=reason):
        updates.latest_release(opener=_opener(error=error))


@pytest.mark.parametrize(
    "payload", [[], {"assets": []}, {"tag_name": "v1", "assets": [{"name": "x"}]}]
)
def test_an_unreadable_answer_is_an_error_not_a_crash(payload):
    with pytest.raises(updates.UpdateCheckError, match="can't read"):
        updates.latest_release(opener=_opener(payload))


@pytest.mark.parametrize(
    ("info", "tag", "status"),
    [
        (RELEASE, "v0.35.0", "up_to_date"),
        (RELEASE, "v0.36.0", "update_available"),
        (DEV, "v0.35.0", "ahead"),
        (DEV, "v0.35.1", "update_available"),
        (BuildInfo("0.36.0b1", "0.36.0b1"), "v0.35.0", "ahead"),
    ],
)
def test_the_build_is_compared_with_the_latest_release(info, tag, status):
    result = updates.check_for_updates(latest=_latest(tag), info=info, kind="pip")
    assert result.status == status
    assert result.current == info.version


def test_an_update_names_the_command_for_this_install():
    result = updates.check_for_updates(latest=_latest(), info=DEV, kind="checkout")
    assert result.command == "git pull"
    assert result.message == (
        "v0.36.0 is out (released 9 Oct 2026); this is v0.35.0.post3+g8f18219."
    )
    assert result.latest.url.endswith("/releases/tag/v0.36.0")


def test_a_development_build_past_the_release_says_so():
    result = updates.check_for_updates(
        latest=_latest("v0.35.0"), info=DEV, kind="checkout"
    )
    assert result.message == (
        "Development build — 3 commits after v0.35.0, at 8f18219. "
        "The latest release is v0.35.0."
    )


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        ("checkout", "git pull"),
        ("uv-tool", "uv tool upgrade scanpath-studio"),
        ("pipx", "pipx upgrade scanpath-studio"),
        ("uv", "uv pip install -U scanpath-studio"),
        ("pip", "pip install -U scanpath-studio"),
        ("desktop", ""),
    ],
)
def test_each_install_kind_has_its_command(kind, command):
    assert updates.update_command(kind, RELEASE) == command


def test_a_git_install_reinstalls_from_its_own_url():
    info = BuildInfo(
        "0.35.0+gabc1234",
        "0.35.0",
        None,
        "abc1234",
        source="vcs",
        vcs_url="https://github.com/someone/fork",
    )
    assert (
        updates.update_command("vcs", info)
        == 'pip install -U "git+https://github.com/someone/fork"'
    )


def test_the_desktop_app_gets_its_archive(monkeypatch):
    monkeypatch.setattr(
        updates, "desktop_archive", lambda: "ScanpathStudio-macos-arm64.dmg"
    )
    result = updates.check_for_updates(
        latest=_latest(
            assets=[
                "ScanpathStudio-macos-arm64.dmg",
                "ScanpathStudio-windows-x86_64.zip",
            ]
        ),
        info=RELEASE,
        kind="desktop",
    )
    assert result.download.name == "ScanpathStudio-macos-arm64.dmg"
    assert result.command == ""


def test_a_desktop_archive_not_yet_uploaded_says_so(monkeypatch):
    monkeypatch.setattr(
        updates, "desktop_archive", lambda: "ScanpathStudio-macos-arm64.dmg"
    )
    result = updates.check_for_updates(latest=_latest(), info=RELEASE, kind="desktop")
    assert result.status == "update_available"
    assert result.download is None
    assert "isn't on the release page yet" in result.message


def test_a_computer_with_no_desktop_build_is_told_so(monkeypatch):
    monkeypatch.setattr(updates, "desktop_archive", lambda: None)
    result = updates.check_for_updates(latest=_latest(), info=RELEASE, kind="desktop")
    assert "no desktop build for this computer" in result.message


@pytest.mark.parametrize(
    ("system", "machine", "name"),
    [
        ("darwin", "arm64", "ScanpathStudio-macos-arm64.dmg"),
        ("darwin", "x86_64", None),
        ("win32", "AMD64", "ScanpathStudio-windows-x86_64.zip"),
        ("linux", "x86_64", "ScanpathStudio-linux-x86_64.tar.gz"),
        ("linux", "aarch64", None),
    ],
)
def test_desktop_archive_per_computer(system, machine, name):
    assert updates.desktop_archive(system, machine) == name


def test_the_archive_names_are_the_ones_desktop_yml_builds():
    workflow = (ROOT / ".github" / "workflows" / "desktop.yml").read_text(
        encoding="utf-8"
    )
    for name in set(updates.DESKTOP_ARCHIVES.values()):
        assert f"archive: {name}" in workflow


def test_a_failed_check_is_a_result_not_an_exception():
    def offline():
        raise updates.UpdateCheckError(
            "Couldn't reach GitHub to check — are you offline?"
        )

    result = updates.check_for_updates(latest=offline, info=RELEASE, kind="pip")
    assert (result.status, result.latest) == ("error", None)
    assert "offline" in result.message
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra test --extra lint pytest tests/test_updates.py -q`
Expected: collection ERROR — `ImportError: cannot import name 'updates'`.

- [ ] **Step 3: Write `scanpath_studio/updates.py`**

```python
"""Is there a newer Scanpath Studio than this build? (#139)

Asked only when someone clicks *Check for updates* (Help → About), runs
``scanpath-studio version --check`` or calls ``api.check_for_updates`` — never
on its own (docs/privacy.md → *Network activity*). One source serves every
install: GitHub's latest release, which leaves out drafts and pre-releases and
lists each desktop archive with its sha256. :func:`check_for_updates` never
raises; a check that could not be made says why in ``UpdateCheck.message``.
"""

from __future__ import annotations

import json
import platform
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from packaging.version import InvalidVersion, Version

from .build_info import BuildInfo, build_info, install_kind

REPO = "lacclab/scanpath-studio"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
TIMEOUT_S = 5.0

#: The shell command that updates each kind of install (``build_info.INSTALL_KINDS``);
#: ``vcs`` is built from the URL pip recorded, and the desktop app downloads.
UPDATE_COMMANDS = {
    "checkout": "git pull",
    "uv-tool": "uv tool upgrade scanpath-studio",
    "pipx": "pipx upgrade scanpath-studio",
    "uv": "uv pip install -U scanpath-studio",
    "pip": "pip install -U scanpath-studio",
}

#: Each release's desktop archive per (platform, machine) — the names
#: ``.github/workflows/desktop.yml`` gives them. There is no Intel Mac build.
DESKTOP_ARCHIVES = {
    ("darwin", "arm64"): "ScanpathStudio-macos-arm64.dmg",
    ("win32", "amd64"): "ScanpathStudio-windows-x86_64.zip",
    ("win32", "x86_64"): "ScanpathStudio-windows-x86_64.zip",
    ("linux", "x86_64"): "ScanpathStudio-linux-x86_64.tar.gz",
}

_UNREADABLE = (
    "GitHub sent an answer this version of the app can't read; try again later."
)


@dataclass(frozen=True)
class Asset:
    """One file attached to a release; ``digest`` is ``"sha256:<hex>"`` or ``""``."""

    name: str
    url: str
    size: int = 0
    digest: str = ""


@dataclass(frozen=True)
class Release:
    """A published release: ``version`` is the tag without its ``v``, ``url`` its page."""

    version: str
    tag: str
    published_at: str
    url: str
    assets: tuple[Asset, ...] = ()

    def asset(self, name: str) -> Asset | None:
        """The attached file called ``name``, if the release has it yet."""
        return next((asset for asset in self.assets if asset.name == name), None)


@dataclass(frozen=True)
class UpdateCheck:
    """The answer to "is there a newer release than this build?".

    ``status`` is ``"up_to_date"``, ``"update_available"``, ``"ahead"`` (a
    development build past the latest release) or ``"error"`` (the check could
    not be made); ``message`` says it in a sentence. With an update available,
    ``command`` is the shell command that updates this install or, in the
    desktop app, ``download`` is this computer's archive (``None`` until the
    release's desktop builds are uploaded).
    """

    status: str
    current: str
    message: str
    latest: Release | None = None
    install_kind: str = "pip"
    command: str = ""
    download: Asset | None = None


class UpdateCheckError(Exception):
    """A check that could not be made; ``str()`` is the reason, for people."""


def latest_release(
    timeout: float = TIMEOUT_S, *, opener: Callable = urllib.request.urlopen
) -> Release:
    """GitHub's latest release of Scanpath Studio. Raises :class:`UpdateCheckError`."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"scanpath-studio/{build_info().version}",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise UpdateCheckError(_http_reason(error)) from error
    except OSError as error:  # URLError, a refused connection, a timeout
        raise UpdateCheckError(
            "Couldn't reach GitHub to check — are you offline?"
        ) from error
    except ValueError as error:
        raise UpdateCheckError(_UNREADABLE) from error
    return _release_from(payload)


def _http_reason(error: urllib.error.HTTPError) -> str:
    headers = error.headers or {}
    if (
        error.code in (403, 429)
        and str(headers.get("X-RateLimit-Remaining", "")) == "0"
    ):
        try:
            reset = datetime.fromtimestamp(int(headers.get("X-RateLimit-Reset")))
            when = f" after {reset:%H:%M}"
        except (TypeError, ValueError, OverflowError, OSError):
            when = " later"
        return (
            f"GitHub's limit on checks from this network is used up; try again{when}."
        )
    if error.code == 404:
        return "GitHub lists no published release of Scanpath Studio."
    return f"GitHub answered with an error (HTTP {error.code}); try again later."


def _release_from(payload: object) -> Release:
    try:
        tag = str(payload["tag_name"])
        assets = tuple(
            Asset(
                name=str(item["name"]),
                url=str(item["browser_download_url"]),
                size=int(item.get("size") or 0),
                digest=str(item.get("digest") or ""),
            )
            for item in payload.get("assets") or ()
        )
        return Release(
            version=tag.removeprefix("v"),
            tag=tag,
            published_at=str(payload.get("published_at") or ""),
            url=str(payload.get("html_url") or RELEASES_PAGE),
            assets=assets,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise UpdateCheckError(_UNREADABLE) from error


def desktop_archive(
    system: str | None = None, machine: str | None = None
) -> str | None:
    """This computer's desktop archive name, or ``None`` where there is no build."""
    system = sys.platform if system is None else system
    machine = (platform.machine() if machine is None else machine).lower()
    if system.startswith("linux"):
        system = "linux"
    return DESKTOP_ARCHIVES.get((system, machine))


def update_command(kind: str, info: BuildInfo) -> str:
    """The shell command that updates this kind of install; ``""`` for the desktop app."""
    if kind == "vcs":
        url = info.vcs_url or f"https://github.com/{REPO}"
        return f'pip install -U "git+{url}"'
    return UPDATE_COMMANDS.get(kind, "")


def _released_on(iso: str) -> str:
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"{when.day} {when:%b %Y}"


def check_for_updates(
    timeout: float = TIMEOUT_S,
    *,
    latest: Callable[[], Release] | None = None,
    info: BuildInfo | None = None,
    kind: str | None = None,
) -> UpdateCheck:
    """Compare this build with GitHub's latest release. Never raises.

    ``latest`` replaces the GitHub request (the app passes a cached one, tests a
    fake); ``info`` and ``kind`` default to this process's build and install.
    """
    info = build_info() if info is None else info
    kind = install_kind(info) if kind is None else kind
    try:
        release = latest() if latest is not None else latest_release(timeout)
    except UpdateCheckError as error:
        return UpdateCheck("error", info.version, str(error), install_kind=kind)
    try:
        newest, current = Version(release.version), Version(info.version)
    except InvalidVersion:
        return UpdateCheck(
            "error",
            info.version,
            f"GitHub's latest release, {release.tag}, isn't a version this app "
            "can compare.",
            latest=release,
            install_kind=kind,
        )
    if newest == current:
        return UpdateCheck(
            "up_to_date",
            info.version,
            f"v{release.version} is the latest release.",
            latest=release,
            install_kind=kind,
        )
    if newest < current:
        return UpdateCheck(
            "ahead",
            info.version,
            f"{info.describe()}. The latest release is v{release.version}.",
            latest=release,
            install_kind=kind,
        )
    released = _released_on(release.published_at)
    message = (
        f"v{release.version} is out"
        + (f" (released {released})" if released else "")
        + f"; this is v{info.version}."
    )
    if kind != "desktop":
        return UpdateCheck(
            "update_available",
            info.version,
            message,
            latest=release,
            install_kind=kind,
            command=update_command(kind, info),
        )
    name = desktop_archive()
    download = release.asset(name) if name else None
    if download is None:
        message += (
            " Its download for this computer isn't on the release page yet; "
            "desktop builds are uploaded up to an hour after a release."
            if name
            else " There is no desktop build for this computer; see the release page."
        )
    return UpdateCheck(
        "update_available",
        info.version,
        message,
        latest=release,
        install_kind=kind,
        download=download,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --extra test --extra lint pytest tests/test_updates.py -q`
Expected: all pass.

- [ ] **Step 5: Document the module**

`AGENTS.md`, directly after the `├─ build_info.py` line added in Task 1:

```text
├─ updates.py        #139: *Check for updates* — GitHub's latest release (`latest_release`) compared with the build (`check_for_updates` → `UpdateCheck`: up_to_date / update_available / ahead / error), with the update command per install kind (`update_command`) or the desktop archive (`desktop_archive`). Asked only on a click (About), `version --check` or `api.check_for_updates`; stdlib + packaging, never raises
```

`scanpath_studio/CLAUDE.md`, directly after the `build_info.py` bullet added in Task 1:

```markdown
- [updates.py](updates.py) — **#139** *Check for updates*. One source for every install: `https://api.github.com/repos/lacclab/scanpath-studio/releases/latest` (drafts and pre-releases excluded; each desktop archive with its sha256 `digest`, which #385's updater verifies). **Network only on an explicit request** — About's button, `version --check`, `api.check_for_updates` — which is what `docs/privacy.md` promises; never add an automatic check without changing that page. `check_for_updates` never raises (`status="error"` + a plain reason: offline, rate limit with its reset time, HTTP code, unreadable answer). It never runs pip — `update_command` returns the command for `install_kind`. `DESKTOP_ARCHIVES` must match `desktop.yml`'s `archive:` names (a test reads the workflow).
```

- [ ] **Step 6: Lint and commit**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/updates.py tests/test_updates.py AGENTS.md scanpath_studio/CLAUDE.md
git commit -m "Compare the build with GitHub's latest release (#139)"
```

---

### Task 4: the CLI and API surfaces

**Files:**
- Modify: `scanpath_studio/api.py` (imports; two functions after `clear_cache`)
- Modify: `scanpath_studio/__init__.py` (`__all__`)
- Modify: `scanpath_studio/cli.py` (`_HELP`, `_COMMANDS`, `_version_parser`, `version`, `main`)
- Modify: `scripts/docs_support.py` (`_parsers`)
- Modify: `docs/api.md`, `docs/cli.md`
- Modify: `tests/test_cli.py`, `tests/test_docs_support.py`, `tests/test_updates.py`

**Interfaces:**
- Consumes: `build_info.build_info()`, `build_info.install_kind(info)`, `build_info.INSTALL_KINDS`, `build_info.BuildInfo` (Task 1); `updates.check_for_updates(timeout)`, `updates.UpdateCheck`, `updates.Release`, `updates.latest_release`, `updates.UpdateCheckError`, `updates.TIMEOUT_S` (Task 3).
- Produces: `api.version_info() -> BuildInfo`, `api.check_for_updates(timeout: float = 5.0) -> UpdateCheck` (also `scanpath_studio.version_info` / `scanpath_studio.check_for_updates`); `cli._version_parser() -> argparse.ArgumentParser`; `cli.version(argv: list[str]) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_version_command_names_the_build_and_install(capsys):
    from scanpath_studio.build_info import INSTALL_KINDS, build_info, install_kind

    cli.main(["version"])
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"scanpath-studio {__version__}"
    assert out[1] == f"Build:      {build_info().describe()}"
    assert out[2] == f"Installed:  {INSTALL_KINDS[install_kind()]}"
    assert len(out) == 3  # no --check, no network


def test_version_check_prints_the_answer(capsys, monkeypatch):
    from scanpath_studio import updates

    release = updates.Release(
        "99.0.0",
        "v99.0.0",
        "2026-10-09T10:00:00Z",
        "https://github.com/lacclab/scanpath-studio/releases/tag/v99.0.0",
    )
    monkeypatch.setattr(updates, "latest_release", lambda timeout=5.0: release)
    cli.main(["version", "--check"])
    out = capsys.readouterr().out
    assert "v99.0.0 is out (released 9 Oct 2026)" in out
    assert "Update:     " in out
    assert (
        "What's new: https://github.com/lacclab/scanpath-studio/releases/tag/v99.0.0"
        in out
    )


def test_a_failed_version_check_exits_1(capsys, monkeypatch):
    from scanpath_studio import updates

    def offline(timeout=5.0):
        raise updates.UpdateCheckError(
            "Couldn't reach GitHub to check — are you offline?"
        )

    monkeypatch.setattr(updates, "latest_release", offline)
    with pytest.raises(SystemExit) as exited:
        cli.main(["version", "--check"])
    assert exited.value.code == 1
    assert "offline" in capsys.readouterr().err


def test_version_is_a_listed_command(capsys):
    cli.main(["--help"])
    assert "scanpath-studio version [--check]" in capsys.readouterr().out
```

In `tests/test_docs_support.py`, add `("version", cli._version_parser),` to the `test_the_cli_reference_lists_every_flag` parametrize list (after the `cache` entry).

Append to `tests/test_updates.py`:

```python
def test_the_api_reports_the_build_and_checks(monkeypatch):
    import scanpath_studio as sps
    from scanpath_studio.build_info import build_info

    assert sps.version_info() == build_info()
    assert {"version_info", "check_for_updates"} <= set(sps.__all__)
    monkeypatch.setattr(
        updates, "latest_release", lambda timeout=5.0: _latest("v99.0.0")()
    )
    result = sps.check_for_updates(timeout=2.0)
    assert result.status == "update_available"
    assert result.latest.version == "99.0.0"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra test --extra lint pytest tests/test_cli.py tests/test_docs_support.py tests/test_updates.py -q -k "version or api_reports or every_flag"`
Expected: FAIL — `scanpath-studio: unknown command 'version'` / `AttributeError: … has no attribute '_version_parser'` / `version_info`.

- [ ] **Step 3: Add the API functions**

`scanpath_studio/api.py` — among the relative `# noqa: E402` imports, add (ruff `--fix` will sort them):

```python
from .build_info import BuildInfo  # noqa: E402
from .updates import UpdateCheck  # noqa: E402
```

After `def clear_cache() -> dict: …` add:

```python
def version_info() -> BuildInfo:
    """Which build of Scanpath Studio this is — no network access.

    ``version`` is what ``scanpath_studio.__version__`` holds: the release itself
    (``"0.35.0"``), or between releases a PEP 440 version that sorts after it —
    ``"0.35.0.post3+g8f18219"`` is three commits after v0.35.0, at commit
    ``8f18219``, and it ends ``.dirty`` with uncommitted changes. ``release`` is
    the release it descends from (``scanpath_studio.__release__``), ``distance``
    the commits since (``None`` when unknown), ``commit``, ``dirty``, and
    ``source`` — how it was worked out: ``"checkout"`` (``git describe``),
    ``"stamp"`` (a desktop bundle's build stamp), ``"vcs"`` (a
    ``pip install git+…``) or ``"release"``. ``describe()`` says it in a
    sentence. The same is in Help → About and ``scanpath-studio version``."""
    from .build_info import build_info

    return build_info()


def check_for_updates(timeout: float = 5.0) -> UpdateCheck:
    """Ask GitHub whether a newer release than this build is out.

    The one call here that uses the network, and only when made: it reads the
    latest release from ``api.github.com`` (drafts and pre-releases excluded)
    and compares it with [`version_info`][scanpath_studio.api.version_info]. It
    never raises. ``status`` is ``"up_to_date"``, ``"update_available"``,
    ``"ahead"`` (a development build past the latest release) or ``"error"``
    (offline, no answer within ``timeout`` seconds, rate-limited, …), and
    ``message`` says it in a sentence. With an update available, ``command`` is
    the shell command that updates this install (``pip install -U
    scanpath-studio``, ``uv tool upgrade scanpath-studio``, ``git pull``, …),
    ``latest.url`` the release notes, and in the desktop app ``download`` the
    archive for this computer. The same check is Help → About → *Check for
    updates* and ``scanpath-studio version --check``."""
    from .updates import check_for_updates as _check

    return _check(timeout)
```

`scanpath_studio/__init__.py` `__all__`: insert `"check_for_updates",` after `"check_data_health",` and `"version_info",` after `"save_figure_layers",` (the list stays sorted; both route to `api` through `_API_EXPORTS`).

`docs/api.md`: directly after the line `::: scanpath_studio.api.clear_cache`, insert:

```markdown

## Version and updates

::: scanpath_studio.api.version_info

::: scanpath_studio.api.check_for_updates
```

- [ ] **Step 4: Add the `version` subcommand**

`scanpath_studio/cli.py`:

In `_HELP`, replace the line `  scanpath-studio --version        print the version` with:

```text
  scanpath-studio version [--check]
                                   show this build and how it was installed;
                                   --check asks GitHub whether a newer
                                   release is out
  scanpath-studio --version        print the version
```

`_COMMANDS = ("run", "render", "analyze", "corpus", "check", "cache", "version")`.

After the `cache()` function, add:

```python
def _version_parser() -> argparse.ArgumentParser:
    """The `version` parser (see `_analyze_parser`)."""
    parser = _ShortErrorParser(
        prog="scanpath-studio version",
        description="Show which build of Scanpath Studio this is and how it was "
        "installed. With --check, also ask GitHub whether a newer release is out "
        "and how to update — the only time this command uses the network.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Ask GitHub for the latest release and say how to update this install.",
    )
    return parser


def version(argv: list[str]) -> None:
    """Print which build this is, and with ``--check`` whether a newer release is out (#139).

    The terminal counterpart of Help → About and ``api.check_for_updates``.
    Exits 1 only when the check itself could not be made.
    """
    args = _version_parser().parse_args(argv)
    from .build_info import INSTALL_KINDS, build_info, install_kind

    info = build_info()
    print(f"scanpath-studio {info.version}")
    print(f"Build:      {info.describe()}")
    print(f"Installed:  {INSTALL_KINDS[install_kind(info)]}")
    if not args.check:
        return
    from .updates import check_for_updates

    result = check_for_updates()
    if result.status == "error":
        print(result.message, file=sys.stderr)
        raise SystemExit(1)
    print()
    print(result.message)
    if result.command:
        print(f"Update:     {result.command}")
    if result.download is not None:
        print(f"Download:   {result.download.url}")
    if result.status == "update_available" and result.latest is not None:
        print(f"What's new: {result.latest.url}")
```

In `main()`, before `elif argv[0] in ("-h", "--help"):`, add:

```python
    elif argv[0] == "version":
        version(argv[1:])
```

`scripts/docs_support.py` `_parsers()`: add `"version": cli._version_parser,` after the `"cache"` entry.

`docs/cli.md`: insert before `## Full reference`:

````markdown
## Version and updates

`scanpath-studio --version` prints the version. `version` says which build it
is and how it was installed; `--check` also asks GitHub whether a newer release
is out and prints the command that updates your install — the only time the
command uses the network:

```bash
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

Between releases the version names the build: `0.35.0.post3+g8f18219` is three
commits after 0.35.0, at commit `8f18219`. The same check is
**:material/help: Help → :material/info: About → :material/update: Check for updates**
in the app, and `check_for_updates()` in the [API](api.md#version-and-updates).

```python exec="true"
from docs_support import cli_reference

print(cli_reference("version"))
```
````

and change the sentence after the last `??? note` block from ``  `corpus` and `check` are listed in full in their own sections above.`` to ``  `corpus`, `check` and `version` are listed in full in their own sections above.``

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra test --extra lint pytest tests/test_cli.py tests/test_docs_support.py tests/test_updates.py tests/test_api.py -q -n auto`
Expected: PASS (including `test_api.py`'s check that every `::: scanpath_studio.api.X` in `docs/api.md` is a root export).

- [ ] **Step 6: Lint and commit**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/api.py scanpath_studio/__init__.py scanpath_studio/cli.py scripts/docs_support.py docs/api.md docs/cli.md tests/test_cli.py tests/test_docs_support.py tests/test_updates.py
git commit -m "Add scanpath-studio version [--check] and api.check_for_updates (#139)"
```

---

### Task 5: Help → About → *Check for updates*

**Files:**
- Modify: `scanpath_studio/constants.py` (`ICONS`)
- Modify: `scanpath_studio/app.py` (imports, `maybe_show_about`, `_about_dialog`, four new helpers)
- Modify: `tests/test_updates.py` (AppTests)
- Modify: `docs/getting-started.md`, `docs/privacy.md`
- Create: `changelog.d/139.added.md`

**Interfaces:**
- Consumes: `build_info.build_info()` / `BuildInfo.describe()` (Task 1); `updates.latest_release()`, `updates.check_for_updates(latest=…)`, `updates.UpdateCheck`, `updates.Release` (Task 3); `persistence.server_bound_to_loopback`, `persistence.human_size` (existing).
- Produces: `app._UPDATE_CHECK_KEY = "_about_update_check"`, `app._update_check_offered() -> bool`, `app._latest_release_cached() -> updates.Release` (`st.cache_data`, ttl 600), `app._render_build_and_updates() -> None`, `app._render_update_result(result) -> None`; widget key `about_check_updates`.

- [ ] **Step 1: Write the failing AppTests**

Append to `tests/test_updates.py`:

```python
def _about_script():
    from scanpath_studio import app

    app._about_dialog()


def _local_run(monkeypatch, tag="v99.0.0"):
    """About on a loopback server, with GitHub answering `tag`."""
    from scanpath_studio import app

    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: True)
    monkeypatch.setattr(updates, "latest_release", lambda timeout=5.0: _latest(tag)())
    app._latest_release_cached.clear()


def test_about_offers_check_for_updates_on_a_local_run(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _local_run(monkeypatch)
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert any("v99.0.0 is out" in info.value for info in at.info)
    assert at.code[0].value  # the command that updates this install
    assert any("What's new in v99.0.0" in md.value for md in at.markdown)


def test_about_says_when_this_is_the_latest(monkeypatch):
    from streamlit.testing.v1 import AppTest

    _local_run(monkeypatch)
    # Whether this tree is a release or a dev build depends on the checkout's
    # tags, so pin the answer rather than the comparison (covered above).
    monkeypatch.setattr(
        updates,
        "check_for_updates",
        lambda **kw: updates.UpdateCheck(
            "up_to_date", "0.35.0", "v0.35.0 is the latest release."
        ),
    )
    at = AppTest.from_function(_about_script).run()
    at.button(key="about_check_updates").click().run()
    assert not at.exception, at.exception
    assert any("is the latest release" in ok.value for ok in at.success)


def test_about_has_no_update_check_on_a_hosted_server(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import app

    monkeypatch.setattr(app, "server_bound_to_loopback", lambda: False)
    at = AppTest.from_function(_about_script).run()
    assert not at.exception, at.exception
    assert not [button for button in at.button if button.key == "about_check_updates"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra test --extra lint pytest tests/test_updates.py -q -k about`
Expected: FAIL — `AttributeError: … _latest_release_cached` / no button `about_check_updates`.

- [ ] **Step 3: Add the icon**

`scanpath_studio/constants.py`, in `ICONS` under the `# About dialog.` group, after `"ai": ":material/smart_toy:",` add:

```python
    "update": ":material/update:",
```

- [ ] **Step 4: Wire the About dialog**

`scanpath_studio/app.py`:

Imports — next to the other `from scanpath_studio import …` module imports, add `from scanpath_studio import updates as update_check` (the alias keeps the name free of any local `updates` variable). `human_size` and `server_bound_to_loopback` are already imported from `scanpath_studio.persistence`.

Above `def maybe_show_about()`, add:

```python
#: #139 — the last *Check for updates* answer, shown under the button until the
#: dialog is opened again. A plain session key, not in the recovery cache's
#: allowlist, so it is never written to disk.
_UPDATE_CHECK_KEY = "_about_update_check"
```

In `maybe_show_about`, open the dialog fresh:

```python
    if st.session_state.pop("_about_dialog_requested", False):
        st.session_state.pop(_UPDATE_CHECK_KEY, None)
        _about_dialog()
```

In `_about_dialog`, split the first `st.markdown(f"""…""")` so the build line and the check sit right under the version. Replace the block that starts `st.markdown(\n        f"""\n**Scanpath Studio** v{__version__} — interactive visualization of eye` and ends before the `# UX-16:` comment with:

```python
    st.markdown(
        f"**Scanpath Studio** v{__version__} — interactive visualization of eye "
        "movements in reading."
    )
    _render_build_and_updates()
    st.markdown(
        f"""
Developed by [Omer Shubi](https://omershubi.github.io/),
[Keren Gruteke Klein](https://kerengruteke.github.io/),
[Maya Grossman](https://www.linkedin.com/in/maya-harram-32b547292/),
[Ella Lion](https://ella-lion.github.io/),
[Deborah N. Jakobi]({_DILI}/lab-members/jakobi.html),
[David R. Reich]({_DILI}/lab-members/reich.html),
[Lena Jäger]({_DILI}/group-leader/jaeger.html), and
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/).

{ICONS["docs"]} [Documentation]({CITATION["docs_url"]}) ↗ ·
{ICONS["code"]} [Code]({CITATION["url"]}) ↗ ·
{ICONS["doi"]} [DOI](https://doi.org/{CITATION["doi"]}) ↗
"""
    )
```

(The author list and links are copied unchanged from the current block — diff it to confirm nothing else moved.)

After `_about_dialog`, add:

```python
def _update_check_offered() -> bool:
    """#139: *Check for updates* only where updating means something — a local
    run or the desktop app, i.e. a server on loopback alone. The hosted demo
    runs the `stable` branch, and its visitors have nothing to update."""
    return server_bound_to_loopback()


@st.cache_data(ttl=600, show_spinner=False)
def _latest_release_cached() -> update_check.Release:
    """GitHub's latest release, kept ten minutes: a second click, or a second
    session on this machine, doesn't spend another of the 60 anonymous requests
    an hour. A failure raises, and `st.cache_data` keeps no failed result."""
    return update_check.latest_release()


def _render_build_and_updates() -> None:
    """#139: which build this is, and — on a local run — *Check for updates*."""
    from scanpath_studio.build_info import build_info

    info = build_info()
    if info.version != info.release:
        st.caption(info.describe())
    if not _update_check_offered():
        return
    if st.button(
        "Check for updates",
        icon=ICONS["update"],
        key="about_check_updates",
        help="Asks GitHub for the latest release — the only time the app goes "
        "online for this.",
    ):
        with st.spinner("Asking GitHub…"):
            st.session_state[_UPDATE_CHECK_KEY] = update_check.check_for_updates(
                latest=_latest_release_cached
            )
    result = st.session_state.get(_UPDATE_CHECK_KEY)
    if result is not None:
        _render_update_result(result)


def _render_update_result(result: update_check.UpdateCheck) -> None:
    """One *Check for updates* answer: the sentence, then what to do about it."""
    if result.status == "up_to_date":
        st.success(result.message, icon=ICONS["success"])
        return
    if result.status == "ahead":
        st.info(result.message, icon=ICONS["info"])
        return
    if result.status == "error":
        st.warning(result.message, icon=ICONS["warning"])
        return
    st.info(result.message, icon=ICONS["update"])
    if result.download is not None:
        st.link_button(
            f"Download {result.download.name} ({human_size(result.download.size)})",
            result.download.url,
            icon=ICONS["download"],
        )
    elif result.command:
        st.code(result.command, language="bash")
        st.caption("Then restart the app.")
    if result.latest is not None:
        st.markdown(f"[What's new in v{result.latest.version}]({result.latest.url}) ↗")
```

- [ ] **Step 5: Run the About tests and the existing About/Debug test**

Run: `uv run --extra test --extra lint pytest tests/test_updates.py tests/test_debug_log.py tests/test_icons.py -q -n auto`
Expected: PASS.

- [ ] **Step 6: Docs and changelog**

`docs/getting-started.md`, insert before `## Next steps`:

```markdown
## Updating { #updating }

**:material/help: Help → :material/info: About** shows the version you are
running. On your own computer — the desktop app or a pip install —
**:material/update: Check for updates** asks GitHub whether a newer release is
out; it is the only time the app goes online for this. If there is one, it
shows the command that updates your install (`pip install -U scanpath-studio`
for pip) or, in the desktop app, a button that downloads the new version.
`scanpath-studio version --check` does the same from a terminal.

Between releases the version names the exact build: `0.35.0.post3+g8f18219` is
three commits after release 0.35.0, at commit `8f18219`, and `.dirty` at the
end means it has uncommitted changes. Quote the whole version in a bug report.
```

`docs/privacy.md` → *Network activity*: after the first paragraph's sentence ending ``…runs against a folder that doesn't have it yet.``, add:

```markdown
**Check for updates** (Help → About, or `scanpath-studio version --check`) asks
GitHub's API (`api.github.com`) for the latest release, only when you click it;
the request carries nothing but the app's version, in its User-Agent.
```

Create `changelog.d/139.added.md`:

```text
Help → About can check for updates: it shows whether a newer release is out and the command that updates your install, or the download for the desktop app; also scanpath-studio version --check and api.check_for_updates(), and only ever when asked.
```

Run: `uv run python scripts/changelog_fragments.py check` → passes.

- [ ] **Step 7: Lint and commit**

```bash
uv run --extra lint ruff check --fix . && uv run --extra lint ruff format .
git add scanpath_studio/constants.py scanpath_studio/app.py tests/test_updates.py docs/getting-started.md docs/privacy.md changelog.d/139.added.md
git commit -m "Add Check for updates to Help → About (#139)"
```

---

### Task 6: Verify, review, open the PR, hand back for review

**Files:** none new (fixes go to whichever file a check flags).

**Interfaces:**
- Consumes: everything above.
- Produces: an open PR to `main` from `build-versions-and-updates`; #139 at board Status **Review** with a `### ⚖ Waiting on you` entry.

- [ ] **Step 1: Full suite, lint, docs**

```bash
uv run --extra test --extra lint pytest -n auto
uv run --extra lint ruff check . && uv run --extra lint ruff format --check .
uv run --extra docs mkdocs build --strict; echo "mkdocs exit: $?"
```

Expected: all tests pass; ruff clean; `mkdocs exit: 0`. Say in the report that the suite ran under the worktree's `uv` environment (pandas 3).

- [ ] **Step 2: Check the build version end to end**

```bash
uv run scanpath-studio --version
uv run scanpath-studio version
SCANPATH_STUDIO_PERSIST=0 uv run scanpath-studio version --check
```

Expected: `--version` prints `0.35.0.postN+g<hash>` (N ≥ 5 on this branch; `.dirty` if the tree is dirty); `version` prints `Build: Development build — N commits after v0.35.0, at <hash>` and `Installed: a git checkout`; `--check` prints `… The latest release is v0.35.0.` (ahead) — or a plain network reason with exit 1 if offline.

- [ ] **Step 3: House reviewers**

Dispatch the `surface-parity-reviewer` and `perf-reviewer` subagents on `git diff origin/main...HEAD`. Tell both: do not start the app or any server; do not use the Browser pane or Claude in Chrome; do not run `scanpath-studio cache --clear` or `api.clear_cache`. Fix what they confirm; commit each fix with `(#139)`.

- [ ] **Step 4: Push and open the PR**

```bash
git push
gh pr create --base main --head build-versions-and-updates \
  --title "Build versions + Check for updates (#139)" \
  --body-file /private/tmp/claude-501/-Users-shubi-Projects-scanpath-studio-app/aa2ffd9a-80b4-497c-acfa-7dfcf1679def/scratchpad/pr-139.md
```

Write that file first. The PR body: summary of the two sections, the decisions (labels-only, runtime-from-git, click-only, GitHub latest release), the surfaces (About / `version --check` / `api.check_for_updates`; deep link N/A), test evidence (suite + interpreter, mkdocs), and that #385 builds on it. End with the harness's PR footer. Then bind the PR with `mcp__ccd_pr__get_status` / `bind_pr`.

- [ ] **Step 5: Validate a desktop build of the branch**

`gh workflow run desktop.yml --ref build-versions-and-updates`. When it finishes, check each OS's *Smoke test* log prints `selfcheck ok: v0.35.0.postN+g<hash>, …` — the stamp reached the bundle. (Dispatch runs build and smoke-test only; they attach nothing to any release.)

- [ ] **Step 6: Hand #139 back for review**

Update #139's body (`gh issue edit 139 --body-file …`): *What was done* lists what shipped with blob links on the branch; *What's left* says "Nothing."; add `### ⚖ Waiting on you` with the review ask — open Help → About on a local run and click *Check for updates*; run `scanpath-studio version --check`; judgement calls to check: `__release__` naming, `ahead` wording, button hidden on non-loopback servers, `Exit 1 only on a failed check`. Add the `waiting-on-you` label; move the board Status to **Review** (project `PVT_kwDOBWtHfs4Bg-gS`, Status field `PVTSSF_lADOBWtHfs4Bg-gSzhf7_0o`, option Review `2d6ed3eb`, item `PVTI_lADOBWtHfs4Bg-gSzg35-_w`). Do not close the issue.
