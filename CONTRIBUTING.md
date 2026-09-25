# Contributing

Thanks for your interest in improving Scanpath Studio! This is a small
research tool; contributions, bug reports, and feature requests are welcome via
[issues](https://github.com/lacclab/scanpath-studio/issues) and pull
requests.

## Development setup

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
pip install -e ".[test,lint]"     # or: uv sync --extra test --extra lint
streamlit run streamlit_app.py --server.address 127.0.0.1   # run the app locally
```

`--server.address 127.0.0.1` keeps the server on your own machine; it is also
what turns the on-device recovery cache on (ENG-56 gates it on the server's bind
address, and a bare `streamlit run` listens on every interface).

Tested on Python 3.11–3.14.

Then find the work. Every open and finished item is a
[GitHub issue](https://github.com/lacclab/scanpath-studio/issues), arranged on
the [Scanpath Studio board](https://github.com/orgs/lacclab/projects/5):

```bash
gh issue list                       # what's open
gh project item-list 5 --owner lacclab   # the board, with Status and Priority
```

Everything closed before 2026-08-20 is in the in-repo `tracker/` archive
instead — see [*Before you open a PR*](#before-you-open-a-pr) below for how to
read it.

If you use an AI coding assistant, it picks the project's conventions up on its
own: [`CLAUDE.md`](CLAUDE.md) (working agreements) imports
[`AGENTS.md`](AGENTS.md) (architecture map), and
[`scanpath_studio/CLAUDE.md`](scanpath_studio/CLAUDE.md) loads when it works
inside the package. Point it at a tracker ID and it will find the write-up.

### If a code change doesn't show up

Streamlit re-runs only the top-level script on rerun — it does **not** reload
imported modules, and nearly all of this app's logic lives in imported modules
(`app.py`, `plots.py`, `data.py`, …). `@st.cache_data` also doesn't hash
transitively-called helpers, so a cached loader keeps serving stale results
after you edit a helper it calls. **Restart the server process** to pick up a
change — a browser rerun or "Clear cache" isn't enough. If a fresh launch still
shows the old app, an old server is holding the port: find it with
`lsof -nP -iTCP:8501 -sTCP:LISTEN` (it may run as `python -m scanpath_studio`,
so grep `scanpath_studio`, not just `streamlit`).

## Before you open a PR

```bash
uv run --extra test pytest -n auto   # run the test suite (parallel — the AppTest
                                     # boots dominate runtime; CI runs it this way)
uv run --extra lint ruff check .     # lint
uv run --extra lint ruff format .    # auto-format
```

Use **this project's ruff**, not whatever is on `PATH`: the `lint` extra
(`pip install -e ".[lint]"`, or `uv sync --extra lint` / `uv run --extra lint …`
— a plain `uv sync` installs no extras) holds the exact version CI runs, pinned
in one place — the `lint` extra in `pyproject.toml`, mirrored by
`.github/workflows/ci.yml`. A
newer ruff on your machine will pass a file CI then rejects, and a newer one in
CI will red a branch that changed nothing. To take a new ruff, bump both
together and fix what its new rules find in the same commit.

Prefer `uv run --extra test pytest` over a bare `pytest` or `python -m pytest`:
it runs this project's own environment. CI does not read a lock file — `uv.lock`
is gitignored, generated locally — it resolves afresh on every run
(`uv pip install --system -e ".[test]"`), so it gets the newest releases
`pyproject.toml` allows; keep your environment there too
(`uv sync --upgrade --extra test --extra lint`). There are two ways to get a
false green. A `.venv` (or a local `uv.lock`) that has drifted to an older
pandas is the obvious one; the easier one is a bare `python` that is not this project's at all — with conda
or Homebrew earlier in `PATH`, `python -m pytest` silently runs a different
interpreter against a different pandas. pandas 3.0's string inference in
particular changes real behaviour (a `None` sentinel in an all-string object
array becomes `NaN` unless you pass `dtype=object`), so a suite that is green
under pandas 2 is red in CI.

**A "the suite is green" claim should name the interpreter it came from** — one
line settles it, and it costs less than the round trip when two people disagree
about the state of `main`:

```bash
uv run python -c "import sys, pandas; print(sys.version.split()[0], pandas.__version__)"
```

CI (`.github/workflows/ci.yml`) runs the same checks on every pull request to
`main`, across Python 3.11/3.12/3.13/3.14. See [AGENTS.md](AGENTS.md) and the package
[CLAUDE.md](scanpath_studio/CLAUDE.md) for an architectural overview.

Add a concise entry to the `[Unreleased]` section of
[`CHANGELOG.md`](CHANGELOG.md), in its two-tier shape (ENG-34): a headline
`- **Bold lead** (ID)` line under Added / Changed / Fixed, plus a one-paragraph
`### Details` entry under the matching `#### <Group>` heading — not a per-tweak
log.

If you add a user-facing feature, expose it on **every** surface — not just
visually, but also the deep link / Share, the CLI, and the headless API. See
*Exposing a feature on every surface* in [AGENTS.md](AGENTS.md).

Work items are tracked in
[GitHub Issues](https://github.com/lacclab/scanpath-studio/issues). If your PR
corresponds to an issue, move its Status on the board and keep the write-up in the
body current; the conventions — the `[VIZ-37]` title format, the four-section
body, and the rule that **closing an issue is the maintainer's sign-off**, not
yours — are in `CLAUDE.md` → *Tracking work*.

The in-repo tracker that preceded this (`tracker/`) is a read-only archive of
everything closed before 2026-08-20, with the full write-ups. Read it with
`python3 tracker/server.py` — it opens at <http://127.0.0.1:8765/tracker/> — and
don't edit it. On Windows run `python tracker\server.py` (or double-click
`tracker\start.bat`); `python3` there is normally the Microsoft Store alias,
which prints *"Python was not found"* and exits without starting anything, and
`start.command` is a zsh script. If the port is already taken, another person or
editor session owns that server — start yours on a different port (`--port` for
the archive, `--server.port` for Streamlit) rather than killing theirs.

## Working together

`main` is protected — work lands as a branch and a pull request, never a direct
push — but two people (or two AI sessions) staying out of each other's way is
still a matter of habit rather than tooling.

Two situations, and they need opposite instincts. **Two clones** — the ordinary
case — is what git is for: you each have your own working tree, conflicts surface
at `pull`, and the discipline is pull/commit/push. **One checkout shared by
several editor or AI sessions** gets none of that: there is no second tree to
merge from, `git diff` is *already* the combined state of everyone's edits, and
`git pull` protects you from nothing. There the only defence is staging
selectively and reading what you staged.

Common to both:

- **Claim the issue before you start it.** `gh issue edit <n> --add-assignee @me`
  and drag it to *In progress* on the
  [board](https://github.com/orgs/lacclab/projects/5) *before* writing code, not
  when you finish. The assignee is the only signal the other person has that it
  is taken, and it is visible without pulling anything. New work always gets
  an ID first; it gets an issue when it needs one — when it reaches *Review*,
  is blocked on the maintainer, or is carried across sessions (`CLAUDE.md` →
  *Tracking work*).
- **Commit small, push often.** One commit per feature or fix, with the tracker
  ID in the subject (`fix(viz): … (VIZ-37)`). A large uncommitted working
  tree is the thing that actually hurts — it can't be pulled, reviewed, or built
  on, and merging it later is a marathon. Between clones, always `git pull`
  (or rebase your branch on `main`) before you push.
- **The work queue no longer merges, because it is no longer a file.** Statuses,
  assignees and write-ups live on GitHub now, so two people moving two issues
  cannot conflict at all — which was most of what this section used to be about.
  What still needs care is the **ID**: a new item takes the next free number in
  its `area:*` prefix, and most IDs live in only one place. Check all four —
  `CHANGELOG.md` (where most are allocated), `gh issue list --state all --search
  "[DATA-"`, the archive's `tracker/data.js`, and the **open PRs**, whose
  unmerged changelogs the other three cannot see
  (`gh pr list --state open`, then `gh pr diff <n> -- CHANGELOG.md`) — as
  `CLAUDE.md` → *Tracking work* spells out. Two people reaching for a number at
  the same moment will still collide: check again after creating, and renumber
  **your own** item if it does.
- **Moving a card needs the `project` scope**, once per machine:
  `gh auth refresh -s project`. Without it the board is read-only from the CLI
  (the web UI still works).
Only when several sessions share one checkout:

- **Agree on file ownership before editing.** Two sessions writing one file
  clobber each other even in different regions, because an edit is a
  read-modify-write of the whole file. Have them enumerate their peers, say which
  files they hold, and honour it.
- **`git add <file>` takes the whole file**, including whatever the other session
  wrote into it since you last looked — and `git pull` will not save you, because
  their edits are not on a remote, they are already in your working tree.
  `CHANGELOG.md` is the one everyone touches. Stage
  selectively and **read `git diff --cached` before committing**: it is the only
  view that shows what your commit will actually contain. To take one hunk of a
  shared file non-interactively, `git diff -- <file>`, keep the hunk you want
  with its `diff`/`---`/`+++` header, and `git apply --cached` it.
- **Sweeping someone else's half in isn't destructive**, but it lands their work
  under your commit message and possibly ahead of the code it describes. If you
  catch it before pushing, amend the message to say so rather than unpicking the
  content.

### Docs site

User-facing docs live in `docs/` (MkDocs Material, published to GitHub Pages
on push to `main` by `.github/workflows/docs.yml`; every pull request runs the
same strict build in `ci.yml`):

```bash
pip install -e ".[docs]"
mkdocs serve                 # local preview
mkdocs build --strict        # the CI gate — fails on warnings, bad links and bad anchors
```

A new page also needs a nav entry in [`mkdocs.yml`](mkdocs.yml). Keep to what
the release does and we stand behind — not how it came to be, and not
anything a reader cannot use (ENG-80).

Parts of the site are generated when it builds, so they cannot drift:

- `` ```python exec="true" `` fences run during the build (markdown-exec): the
  Gallery's figures, printed example output, the CLI and figure-option
  references, the in-app tutorial steps, and the Cite and Changelog pages, all
  through [`scripts/docs_support.py`](scripts/docs_support.py). A fence that
  raises fails the build.
- The API reference is generated from the `api.py` docstrings, so keep those
  current.
- The app screenshots in `docs/assets/screenshots/` are re-captured with
  `uv run --with playwright python scripts/capture_docs_screenshots.py`, which
  starts its own app with the recovery cache off; `scripts/record_app_demo.py`
  re-records the README's GIF and the home page's video the same way.
- Link-preview images render only with `SOCIAL_CARDS=true`, which needs Cairo;
  the deploy sets it.

## Adding a public dataset

Corpora like OneStop, PoTeC, and MultiplEYE are built in: one entry in the
app's data-source picker, one `load_*` in the headless API, backed by an
adapter in [`scanpath_studio/datasets.py`](scanpath_studio/datasets.py).
Adding another is a documented contract — the loader entry points, the
canonical-column mapping, how it's registered, licence expectations,
download-on-demand vs. bundling, and the tests expected — written up in
[`docs/contributing-a-dataset.md`](docs/contributing-a-dataset.md).

Loading data you already have needs no code at all; that's
[`docs/guides/loading-data.md`](docs/guides/loading-data.md).

## Versioning

The version lives in **one** place — `__version__` in
[`scanpath_studio/__init__.py`](scanpath_studio/__init__.py).
`pyproject.toml` reads it dynamically, so bump only that file.

## Dependencies

- `pyproject.toml` is the **one** place dependencies are declared (`>=`
  bounds). Add or bump a dependency there and nowhere else.
- The Streamlit Community Cloud demo installs from `environment.yml`, which
  pip-installs this package, so it follows `pyproject.toml` onto the latest
  releases with nothing to keep in sync. Community Cloud uses the first
  dependency file it finds — `uv.lock`, `Pipfile`, `environment.yml`,
  `requirements.txt`, `pyproject.toml` — so committing a `uv.lock` (it is
  gitignored) would silently switch the demo onto it.

## Releasing

1. Roll the `[Unreleased]` notes into a new version section in
   [`CHANGELOG.md`](CHANGELOG.md).
2. Bump `__version__` in `scanpath_studio/__init__.py`.
3. Bump `version` + `date-released` in [`CITATION.cff`](CITATION.cff) to match
   (`tests/test_citation.py` enforces version parity, so a mismatch fails CI).
4. `main` is protected, so commit these on a branch and merge them through a
   PR. Then tag the merged commit on `main` and push the tag:
   `git fetch origin && git tag vX.Y.Z origin/main && git push origin vX.Y.Z`.
   `.github/workflows/publish.yml` refuses a tag that does not match
   `__version__` (ENG-62), then builds and publishes to PyPI via trusted
   publishing, and `.github/workflows/desktop.yml` builds the per-OS
   standalone desktop bundles and attaches them to the GitHub release for
   the tag — check both workflows succeeded.
5. Optionally create a GitHub Release with the changelog notes.

## Regenerating the demo assets

Both scripts render through Kaleido, which needs a Chrome/Chromium binary
(`plotly_get_chrome -y` once, locally):

```bash
python assets/render_dual_scanpath.py   # README dual-reader still
                                        # (assets/demo_dual_scanpath.png) +
                                        # docs GIF (docs/assets/demo_dual_scanpath.gif)
python scripts/make_hero_gif.py         # README hero GIF (assets/scanpath_animation.gif)
```

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
