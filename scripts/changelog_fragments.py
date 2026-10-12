#!/usr/bin/env python3
"""Unreleased changelog entries, one file per item (ENG-86).

Usage:
    python scripts/changelog_fragments.py check
    python scripts/changelog_fragments.py preview
    python scripts/changelog_fragments.py release <version> [--date YYYY-MM-DD]

A pull request never edits ``CHANGELOG.md``. It adds a file to ``changelog.d/``
instead, so two open PRs never touch the same lines. The file name is what the
entry cites — an issue (or PR) number, or a short slug when there is no issue —
plus its Keep a Changelog group; the file holds one line of text:

    changelog.d/341.fixed.md                -> - <the file's text> ([#341](…))
    changelog.d/340+341.changed.md          -> - <the file's text> ([#340](…), [#341](…))
    changelog.d/trial-picker-ids.changed.md -> - <the file's text> ([#327](…))

A slug becomes the number of the pull request that added it, read from the
squash-merge subject on ``main`` (``… (#327)``), so nothing has to be allocated
up front and parallel branches cannot collide on a number. Before that PR has
merged, ``preview`` prints the entry without one; ``release`` refuses it.

``check`` validates every fragment, ``preview`` prints the unreleased section
they add up to, and ``release`` writes that section into ``CHANGELOG.md`` as
``## [<version>] - <date>`` and deletes the fragments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_DIR = ROOT / "changelog.d"
CHANGELOG = ROOT / "CHANGELOG.md"
ISSUES_URL = "https://github.com/lacclab/scanpath-studio/issues"

#: Keep a Changelog's groups, in the order a section lists them.
GROUPS = ("added", "changed", "deprecated", "removed", "fixed", "security")

_NUMBERS = r"\d+(?:\+\d+)*"
_SLUG = r"[A-Za-z0-9][A-Za-z0-9_-]*"
_NAME = re.compile(rf"^(?P<ref>{_NUMBERS}|{_SLUG})\.(?P<group>[a-z]+)\.md$")
_MERGED_PR = re.compile(r"\(#(\d+)\)\s*$")
#: GitHub's subject for a PR landed as a merge commit rather than squashed.
_MERGE_COMMIT_PR = re.compile(r"^Merge pull request #(\d+) ")


@dataclass(frozen=True)
class Fragment:
    numbers: tuple[int, ...]
    group: str
    text: str
    #: The file's name when it is a slug, kept for the error that names it.
    slug: str = ""

    @property
    def line(self) -> str:
        if not self.numbers:
            return f"- {self.text}"
        refs = ", ".join(f"[#{n}]({ISSUES_URL}/{n})" for n in self.numbers)
        return f"- {self.text} ({refs})"


def merged_pr(path: Path) -> int | None:
    """The PR that merged *path*, or ``None`` before it merges.

    Read from the squash-merge subject of the commit that added it, or — for a
    PR landed as a merge commit — from the oldest "Merge pull request #N" on
    the current branch's first-parent line that brought that commit in.
    Follows renames, so a fragment that was renamed after it landed still
    resolves to the PR that first added it.
    """

    def git(*args: str) -> list[str]:
        return subprocess.run(
            ["git", *args],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()

    try:
        added = git(
            "log", "--follow", "--diff-filter=A", "--format=%H %s", "--", str(path)
        )
        if not added:
            return None
        # git log lists newest first; the first add is the one that counts.
        commit, _, subject = added[-1].partition(" ")
        match = _MERGED_PR.search(subject)
        if match:
            return int(match[1])
        # Every PR merge commit on this branch's own line, oldest first; the
        # first that contains the commit is the PR that brought it in.
        for line in reversed(
            git("log", "--first-parent", "--merges", "--format=%H %s")
        ):
            merge, _, subject = line.partition(" ")
            match = _MERGE_COMMIT_PR.match(subject)
            if match and _contains(path.parent, merge, commit):
                return int(match[1])
    except (OSError, subprocess.CalledProcessError):
        return None
    return None


def _contains(cwd: Path, merge: str, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, merge],
            cwd=cwd,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def load(directory: Path = FRAGMENT_DIR) -> tuple[list[Fragment], list[str]]:
    """Every fragment in *directory*, and a message per file that is not one."""
    fragments: list[Fragment] = []
    errors: list[str] = []
    if not directory.is_dir():
        return fragments, errors
    for path in sorted(directory.iterdir()):
        if path.name in {"README.md", ".gitkeep"}:
            continue
        match = _NAME.match(path.name)
        if match is None:
            errors.append(
                f"{path.name}: expected <issue>[+<issue>...].<group>.md or "
                "<slug>.<group>.md, e.g. 341.fixed.md or trial-picker-ids.fixed.md"
            )
            continue
        group = match["group"]
        if group not in GROUPS:
            errors.append(f"{path.name}: group must be one of {', '.join(GROUPS)}")
            continue
        text = " ".join(path.read_text(encoding="utf-8").split())
        if not text:
            errors.append(f"{path.name}: is empty")
            continue
        if text.startswith("- "):
            errors.append(f"{path.name}: write the text alone, without a '- ' bullet")
            continue
        ref = match["ref"]
        if re.fullmatch(_NUMBERS, ref):
            numbers = tuple(int(n) for n in ref.split("+"))
            fragments.append(Fragment(numbers, group, text))
        else:
            pr = merged_pr(path)
            numbers = (pr,) if pr is not None else ()
            fragments.append(Fragment(numbers, group, text, slug=path.name))
    # Numbered entries in issue order; the not-yet-merged ones last.
    fragments.sort(key=lambda f: (not f.numbers, f.numbers, f.slug))
    return fragments, errors


def render(fragments: list[Fragment]) -> str:
    """The group headings and bullets a release section is made of."""
    blocks = []
    for group in GROUPS:
        lines = [f.line for f in fragments if f.group == group]
        if lines:
            blocks.append("\n".join([f"### {group.capitalize()}", *lines]))
    return "\n\n".join(blocks)


def release(
    version: str, date: str, changelog: Path = CHANGELOG, directory: Path = FRAGMENT_DIR
) -> int:
    """Write the fragments into *changelog* as *version*'s section; delete them."""
    fragments, errors = load(directory)
    if errors:
        raise SystemExit("\n".join(errors))
    if not fragments:
        raise SystemExit(f"no fragments in {directory}")
    unmerged = [f.slug for f in fragments if not f.numbers]
    if unmerged:
        raise SystemExit(
            "no merged PR found for "
            + ", ".join(unmerged)
            + " — release from an up-to-date main, or name the file by its issue"
        )
    text = changelog.read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.MULTILINE):
        raise SystemExit(f"CHANGELOG.md already has a {version} section")
    first = re.search(r"^## \[", text, re.MULTILINE)
    at = first.start() if first else len(text)
    section = f"## [{version}] - {date}\n\n{render(fragments)}\n\n"
    changelog.write_text(text[:at] + section + text[at:], encoding="utf-8")
    for path in directory.iterdir():
        if _NAME.match(path.name):
            path.unlink()
    return len(fragments)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate every fragment")
    sub.add_parser("preview", help="print the unreleased section")
    rel = sub.add_parser("release", help="write the section into CHANGELOG.md")
    rel.add_argument("version")
    rel.add_argument(
        "--date", default=dt.datetime.now().astimezone().date().isoformat()
    )
    ns = parser.parse_args(argv[1:])

    if ns.command == "release":
        count = release(re.sub(r"^v", "", ns.version), ns.date)
        print(f"wrote {count} entries into CHANGELOG.md")
        return 0
    fragments, errors = load()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if ns.command == "preview":
        print(render(fragments))
    else:
        print(f"{len(fragments)} fragments OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
