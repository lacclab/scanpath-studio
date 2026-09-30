#!/usr/bin/env python3
"""Unreleased changelog entries, one file per item (ENG-86).

Usage:
    python scripts/changelog_fragments.py check
    python scripts/changelog_fragments.py preview
    python scripts/changelog_fragments.py release <version> [--date YYYY-MM-DD]

A pull request never edits ``CHANGELOG.md``. It adds a file to ``changelog.d/``
instead, so two open PRs never touch the same lines:

    changelog.d/VIZ-47.changed.md       -> - <the file's text> (VIZ-47)
    changelog.d/AN-32+UX-176.fixed.md   -> - <the file's text> (AN-32, UX-176)

The file name carries the item's ID(s) and its Keep a Changelog group; the file
holds one line of text. Two branches that take the same ID for the same group
create the same file, so git reports the clash instead of both merging.

``check`` validates every fragment, ``preview`` prints the unreleased section
they add up to, and ``release`` writes that section into ``CHANGELOG.md`` as
``## [<version>] - <date>`` and deletes the fragments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_DIR = ROOT / "changelog.d"
CHANGELOG = ROOT / "CHANGELOG.md"

#: Keep a Changelog's groups, in the order a section lists them.
GROUPS = ("added", "changed", "deprecated", "removed", "fixed", "security")

_ID = r"[A-Z]+-\d+"
_NAME = re.compile(rf"^(?P<ids>{_ID}(?:\+{_ID})*)\.(?P<group>[a-z]+)\.md$")


@dataclass(frozen=True)
class Fragment:
    ids: tuple[str, ...]
    group: str
    text: str

    @property
    def line(self) -> str:
        return f"- {self.text} ({', '.join(self.ids)})"


def _id_key(item_id: str) -> tuple[str, int]:
    prefix, _, number = item_id.partition("-")
    return prefix, int(number)


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
                f"{path.name}: expected <ID>[+<ID>...].<group>.md, e.g. VIZ-47.fixed.md"
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
        fragments.append(Fragment(tuple(match["ids"].split("+")), group, text))
    fragments.sort(key=lambda f: [_id_key(i) for i in f.ids])
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
