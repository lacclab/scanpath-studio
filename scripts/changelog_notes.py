#!/usr/bin/env python3
"""Print one release's notes from CHANGELOG.md.

Usage:
    python scripts/changelog_notes.py <version> [changelog_path] [--format FMT]
        [--max-chars N] [--details-url URL]

Extracts the ``## [<version>] - ...`` section (Keep a Changelog format). With
``--format slack`` (the default) Markdown is rewritten to Slack mrkdwn
(``**bold**`` -> ``*bold*``, ``### Heading`` -> ``*Heading*``); with
``--format markdown`` the section is emitted verbatim (for GitHub releases).
Prints nothing and exits 0 if the version has no section or the file is
missing, so the release workflow can fall back to a plain message.

``--max-chars`` bounds the output. GitHub rejects a release body over 125,000
characters and Slack's ceiling is lower still, and a release that bundles
months of work overruns both — v0.29.0's section was 172,795 characters, which
published to PyPI and then failed to create a release. The changelog's two-tier
shape (ENG-34) is what makes that recoverable: the headline list per group is
the half written to be pasted somewhere, so it is the half that survives, with
``--details-url`` pointing at the rest.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Stop a section at the next release header or the bottom-of-file link refs.
_NEXT = re.compile(r"^## \[|^\[[^\]]+\]:\s", re.MULTILINE)


def extract(
    changelog: str,
    version: str,
    fmt: str = "slack",
    *,
    max_chars: int = 0,
    details_url: str = "",
) -> str:
    """Return *version*'s changelog section, or "".

    ``fmt="markdown"`` returns the section verbatim; ``fmt="slack"`` rewrites it
    to Slack mrkdwn. ``max_chars`` (0 = unbounded) shortens the result to fit
    wherever it is being posted — see :func:`_fit`.
    """
    header = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n", changelog, re.MULTILINE
    )
    if header is None:
        return ""
    rest = changelog[header.end() :]
    end = _NEXT.search(rest)
    notes = (rest[: end.start()] if end else rest).strip()
    if fmt == "slack":
        notes = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", notes)  # **bold** -> *bold*
        notes = re.sub(
            r"^### (.*)$", r"*\1*", notes, flags=re.MULTILINE
        )  # ### H -> *H*
    return _fit(notes, max_chars, details_url)


#: Where the two-tier changelog splits: everything from here down is the long
#: half, one paragraph per item (ENG-34). Matched in both output formats, since
#: the Slack rewrite has already turned ``### Details`` into ``*Details*``.
_DETAILS = re.compile(r"^(?:### Details|\*Details\*)\s*$", re.MULTILINE)


def _fit(notes: str, max_chars: int, details_url: str) -> str:
    """Shorten *notes* to ``max_chars``, keeping the part written to be read.

    Two steps, in order of how much they lose: drop the ``### Details`` half —
    which is the point of having two tiers — and, only if the headlines alone
    still overrun, truncate them at a line boundary. A cut is always announced,
    so a short release note never reads as the whole story.
    """
    if max_chars <= 0 or len(notes) <= max_chars:
        return notes
    pointer = "\n\n_Truncated. The full changelog is "
    pointer += f"[here]({details_url})._" if details_url else "in `CHANGELOG.md`._"
    budget = max_chars - len(pointer)
    split = _DETAILS.search(notes)
    if split is not None:
        headlines = notes[: split.start()].rstrip()
        if len(headlines) <= budget:
            return headlines + pointer
        notes = headlines
    kept: list[str] = []
    used = 0
    for line in notes.splitlines():
        if used + len(line) + 1 > budget:
            break
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept).rstrip() + pointer


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("changelog_path", nargs="?", default="CHANGELOG.md")
    parser.add_argument(
        "--format", choices=("slack", "markdown"), default="slack", dest="fmt"
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=0,
        dest="max_chars",
        help="bound the output (0 = unbounded); drops the Details half first",
    )
    parser.add_argument(
        "--details-url",
        default="",
        dest="details_url",
        help="link offered for the dropped half",
    )
    ns = parser.parse_args(argv[1:])
    version = re.sub(r"^v", "", ns.version)
    path = Path(ns.changelog_path)
    if path.is_file():
        sys.stdout.write(
            extract(
                path.read_text(encoding="utf-8"),
                version,
                ns.fmt,
                max_chars=ns.max_chars,
                details_url=ns.details_url,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
