---
name: release
description: Cut a Scanpath Studio release — roll the changelog, bump __version__ and CITATION.cff in lockstep, verify parity, then commit + tag v<version> and push the tag.
disable-model-invocation: true
---

# Release checklist

Cut a release of scanpath-studio. Argument (optional): the target version
(e.g. `1.4.0`). If omitted, propose the next version from the current
`__version__` and the nature of the `[Unreleased]` changelog entries
(semver: features → minor, fixes only → patch), and confirm with the user
before proceeding.

Work from the repository root (the directory containing `pyproject.toml`).

## Pre-flight (abort if any fails)

1. `git status` — the working tree must be clean and on the release branch
   (normally `main`). Stop and report if not.
2. `ruff check --exclude other_vis .` and `ruff format --check --exclude other_vis .`
   must pass (CI's Lint job gates on both).
3. `CHANGELOG.md` must have content under `[Unreleased]` — a release with an
   empty changelog is almost always a mistake; confirm with the user if empty.

## Steps

1. **Changelog** — roll the `[Unreleased]` notes in `CHANGELOG.md` into a new
   `v<version>` section dated today (keep the one-line-per-item style; leave a
   fresh empty `[Unreleased]` section on top).
2. **Version bump** — set `__version__` in `scanpath_studio/__init__.py`. This
   is the single source of truth; `pyproject.toml` reads it dynamically — do
   NOT edit a version in `pyproject.toml`.
3. **Citation** — set `version` and `date-released` (today, ISO format) in
   `CITATION.cff` to match.
4. **Verify parity** — run `pytest tests/test_citation.py` (it enforces
   version parity between `__init__.py` and `CITATION.cff`).
5. **Full test run** — `pytest -n auto`. Stop and report failures; do not tag
   a failing tree.
6. **Commit + tag** — commit the three files with message `Release v<version>`
   (no AI co-author trailer — repo rule), tag `v<version>`, then push the
   branch and the tag. Confirm with the user immediately before the push:
   pushing the tag triggers the `Publish to PyPI` workflow (Trusted
   Publishing) and the `Desktop builds` workflow
   (`.github/workflows/desktop.yml`), which attaches per-OS bundles to the
   GitHub release.

## After

Report the tag pushed and link the GitHub Actions runs to watch
(`Publish to PyPI`, `Desktop builds`).
