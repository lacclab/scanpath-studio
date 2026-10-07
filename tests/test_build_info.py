"""The build version (#139): which build of Scanpath Studio this is."""

from __future__ import annotations

import json
import re
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
