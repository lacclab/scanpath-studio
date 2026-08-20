# Contributing

Thanks for your interest in improving Scanpath Studio! This is a small
research tool; contributions, bug reports, and feature requests are welcome via
[issues](https://github.com/lacclab/scanpath-studio/issues) and pull
requests.

## Development setup

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
pip install -e ".[test]"          # or: uv sync
streamlit run streamlit_app.py    # run the app locally
```

Tested on Python 3.11–3.14.

Then start the work tracker — every open and finished item, searchable, with
`#ID` deep links — and leave that terminal running:

```bash
python3 tracker/server.py
```

On Windows, run `python tracker\server.py` (or double-click `tracker\start.bat`).
`python3` there is normally the Microsoft Store alias, which prints *"Python was
not found"* and exits without starting anything — and `start.command` is a zsh
script. A tracker page opened without its server can be read but not saved.

It opens at <http://127.0.0.1:8765/tracker/>; its **How this works** panel is
the short version of the conventions below. If a port is already taken, another
person or another editor session owns that server — start yours on a different
port (`--port` for the tracker, `--server.port` for Streamlit) rather than
killing theirs.

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
uv run pytest -n auto             # run the test suite (parallel — the AppTest
                                  # boots dominate runtime; CI runs it this way)
ruff check --exclude other_vis .  # lint
ruff format --exclude other_vis . # auto-format
```

Use **this project's ruff**, not whatever is on `PATH`: `pip install -e ".[lint]"`
(or `uv run ruff …`) installs the exact version CI runs, pinned in one place —
the `lint` extra in `pyproject.toml`, mirrored by `.github/workflows/ci.yml`. A
newer ruff on your machine will pass a file CI then rejects, and a newer one in
CI will red a branch that changed nothing. To take a new ruff, bump both
together and fix what its new rules find in the same commit.

Prefer `uv run pytest` over a bare `pytest` or `python -m pytest`: it resolves
the versions in `uv.lock`, which is what CI installs. There are two ways to get
a false green. A `.venv` that has drifted to an older pandas is the obvious one;
the easier one is a bare `python` that is not this project's at all — with conda
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

CI (`.github/workflows/ci.yml`) runs the same checks on every push and PR
across Python 3.11/3.12/3.13/3.14. See [AGENTS.md](AGENTS.md) and the package
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
corresponds to an issue, move its `status:*` label and keep the write-up in the
body current; the conventions — the `[VIZ-37]` title format, the four-section
body, and the rule that **closing an issue is the maintainer's sign-off**, not
yours — are in `CLAUDE.md` → *Tracking work*.

The in-repo tracker that preceded this (`tracker/`) is a read-only archive of
everything closed before 2026-08-20. Open `python3 tracker/server.py` to read it;
don't edit it.

## Working together

The repo commits **directly to `main`** and its work queue is a file in the
repo, so two people (or two AI sessions) staying out of each other's way is a
matter of habit rather than tooling.

Two situations, and they need opposite instincts. **Two clones** — the ordinary
case — is what git is for: you each have your own working tree, conflicts surface
at `pull`, and the discipline is pull/commit/push. **One checkout shared by
several editor or AI sessions** gets none of that: there is no second tree to
merge from, `git diff` is *already* the combined state of everyone's edits, and
`git pull` protects you from nothing. There the only defence is staging
selectively and reading what you staged.

Common to both:

- **Claim the issue before you start it.** `gh issue edit <n> --add-assignee @me
  --add-label status:in-progress --remove-label status:planned` *before* writing
  code, not when you finish. The assignee is the only signal the other person has
  that it is taken, and it is visible without pulling anything. Same for new
  work: `gh issue create` first, then work on it.
- **Commit small, push often.** One commit per feature or fix, with the tracker
  ID in the subject (`fix(viz): … (VIZ-37)`). A large uncommitted working
  tree is the thing that actually hurts — it can't be pulled, reviewed, or built
  on, and merging it later is a marathon. Between clones, always `git pull`
  before you push.
- **The work queue no longer merges, because it is no longer a file.** Statuses,
  assignees and write-ups live on GitHub now, so two people moving two issues
  cannot conflict at all — which was most of what this section used to be about.
  What still needs care is the **ID**: a new issue takes the next free number in
  its `area:*` prefix, and two people opening one at the same moment will reach
  for the same number. Check
  `gh issue list --state all --search "[DATA-"` again after creating, and
  renumber **your own** issue if it collides.
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
on push to `main` by `.github/workflows/docs.yml`):

```bash
pip install -e ".[docs]"
mkdocs serve                 # local preview
mkdocs build --strict        # the CI gate — fails on warnings and bad refs
```

A new page also needs a nav entry in [`mkdocs.yml`](mkdocs.yml). The API
reference is generated from `api.py` docstrings, so keep those current.

## Adding a public dataset

Corpora like OneStop, PoTeC, and MultiplEYE are built in: one entry in the
app's data-source picker, one `load_*` in the headless API, backed by an
adapter in [`scanpath_studio/datasets.py`](scanpath_studio/datasets.py).
Adding another is a documented contract — the loader entry points, the
canonical-column mapping, how it's registered, licence expectations,
download-on-demand vs. bundling, and the tests expected — written up in
[`docs/contributing-a-dataset.md`](docs/contributing-a-dataset.md).

Loading data you already have needs no code at all; that's
[`docs/bring-your-own-data.md`](docs/bring-your-own-data.md).

## Versioning

The version lives in **one** place — `__version__` in
[`scanpath_studio/__init__.py`](scanpath_studio/__init__.py).
`pyproject.toml` reads it dynamically, so bump only that file.

## Dependencies

- `pyproject.toml` carries the **library** dependency bounds (`>=`) used when
  installing the package with pip.
- `requirements.txt` is the **deployment manifest** for the Streamlit Cloud
  demo, using compatible-release pins (`~=`) so the live app stays on a
  known-good minor while still getting patch updates. Update both when you add
  or upgrade a dependency.

## Releasing

1. Roll the `[Unreleased]` notes into a new version section in
   [`CHANGELOG.md`](CHANGELOG.md).
2. Bump `__version__` in `scanpath_studio/__init__.py`.
3. Bump `version` + `date-released` in [`CITATION.cff`](CITATION.cff) to match
   (`tests/test_citation.py` enforces version parity, so a mismatch fails CI).
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
   `.github/workflows/publish.yml` builds and publishes to PyPI via trusted
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
