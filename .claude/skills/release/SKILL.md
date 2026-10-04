---
name: release
description: Cut a Scanpath Studio release — roll the changelog, bump __version__ and CITATION.cff in lockstep, verify parity, land the bump through a PR (main is protected), then tag v<version> on main and push the tag.
disable-model-invocation: true
---

# Release checklist

Cut a release of scanpath-studio. Argument (optional): the target version
(e.g. `1.4.0`). If omitted, propose the next version from the current
`__version__` and the nature of the unreleased entries in `changelog.d/`
(semver: features → minor, fixes only → patch), and confirm with the user
before proceeding.

Work from the repository root (the directory containing `pyproject.toml`), in
the project's own environment — `uv run --extra test --extra lint …`, or a venv
with `pip install -e ".[test,lint]"`; never a bare `pytest` / `ruff` from `PATH`.

**`main` is protected** (a ruleset: no deletion, no force-push, and changes land
through pull requests). The version bump therefore goes through a branch + PR
like any other change, and the tag is cut on `main` *after* that PR merges.

## Pre-flight (abort if any fails)

1. `git status` — the working tree must be clean. `git fetch origin` and start
   from an up-to-date `origin/main`. Stop and report if not.
2. `ruff check .` and `ruff format --check .`
   must pass (CI's Lint job gates on both).
3. `python scripts/changelog_fragments.py check` passes and `changelog.d/`
   holds fragments — a release with none is almost always a mistake; confirm
   with the user if empty.

## Steps

1. **Branch** — `git switch -c release-v<version> origin/main`.
2. **Changelog** — `python scripts/changelog_fragments.py release <version>`
   writes the `changelog.d/` fragments into a `## [<version>] - <today>`
   section of `CHANGELOG.md` and deletes them (ENG-86). A fragment named by a
   slug is cited by the PR whose squash-merge added it, read from `git log`; if
   the script refuses one ("no merged PR found"), it did not land through a
   PR — rename it to the issue or PR it belongs to. Read the section it wrote;
   tidy wording there if needed.
3. **Version bump** — set `__version__` in `scanpath_studio/__init__.py`. This
   is the single source of truth; `pyproject.toml` reads it dynamically — do
   NOT edit a version in `pyproject.toml`.
4. **Citation** — set `version` and `date-released` (today, ISO format) in
   `CITATION.cff` to match.
5. **Verify parity** — run `pytest tests/test_citation.py` (it enforces
   version parity between `__init__.py` and `CITATION.cff`).
6. **Full test run** — `pytest -n auto`. Stop and report failures; do not
   release a failing tree.
7. **Commit + PR** — commit the changes (the three files plus the deleted fragments) with message `Release v<version>`
   (no AI co-author trailer — repo rule), push the branch, and open a PR to
   `main`, and turn on auto-merge so it lands once CI is green. Do not tag the
   branch.
8. **Hand off** — stop here and end your turn with the PR link and this ask
   to the user, since the tag push is theirs to approve:

   > **Your call:** once the PR has merged, tell me and I'll tag
   > `v<version>` on `origin/main` and push the tag. Pushing it publishes to
   > PyPI and builds the desktop apps.

   Don't poll CI or wait on the merge in the meantime.
9. **Tag on main** — when the user says go: `git fetch origin`, check that
   the PR has merged and that
   `origin/main`'s `scanpath_studio/__init__.py` holds the new version, then
   `git tag v<version> origin/main` and `git push origin v<version>`. The
   user's go-ahead from step 8 is the confirmation: pushing a `v*` tag triggers the
   `Publish to PyPI` workflow (`.github/workflows/publish.yml`, Trusted
   Publishing) and the `Desktop builds` workflow
   (`.github/workflows/desktop.yml`), which attaches per-OS bundles to the
   GitHub release. `publish.yml` refuses a tag that does not match
   `__version__` (ENG-62) — which is why the tag goes on the merged commit, not
   on a commit from before the bump.

## After

Report the tag pushed and link the GitHub Actions runs to watch
(`Publish to PyPI`, `Desktop builds`).
