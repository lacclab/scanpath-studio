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

Prefer `uv run pytest` over a hand-managed virtualenv's `pytest`: it resolves
the versions in `uv.lock`, which is what CI installs. A `.venv` that has drifted
to an older pandas passes tests that CI then fails — pandas 3.0's string
inference in particular changes real behaviour (a `None` sentinel in an
all-string object array becomes `NaN` unless you pass `dtype=object`).

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

Work items are tracked in [`tracker/data.js`](tracker/data.js) (open
[`tracker/index.html`](tracker/index.html) in a browser to read it) — if your
PR corresponds to a tracker item, update its status and write-up; the
conventions are in the tracker's *How this works* panel and `CLAUDE.md` →
*Tracking work*.

## Working together

The repo commits **directly to `main`** and its work queue is a file in the
repo, so two people (or two AI sessions) staying out of each other's way is a
matter of habit rather than tooling:

- **Claim the item before you start it.** Set the tracker item to
  `In progress` — and push that change — *before* writing code, not when you
  finish. That flip is the only signal the other person has that the item is
  taken. Same for a new item: create it, push it, then work on it.
- **Pull before you start, commit small, push often.** One commit per feature or
  fix, with the tracker edit in the same commit as the code it describes. A
  large uncommitted working tree is the thing that actually hurts here — it
  can't be pulled, reviewed, or built on, and merging it later is a marathon.
  Always `git pull` before you push.
- **`tracker/state.json` will conflict; merge it, never pick a side.** The file
  holds every status override and implementation brief, and the tracker server
  rewrites it whole on each save. Its `revision` counter changes on *every*
  save, so parallel work conflicts there almost every time. Resolve by keeping
  **both** sides' entries under `items` / `createdItems` and setting `revision`
  to one more than the higher of the two. Taking one side wholesale silently
  discards the other person's status changes and briefs. Reload the tracker page
  afterwards — it caches the revision it last read, and will refuse to save
  against a stale one ("The tracker changed in another tab").
- **`tracker/data.js` merges cleanly** as long as you add new items in the right
  group and never renumber an existing ID. Two people adding an item to the same
  group at the same moment will both reach for the same next free number — check
  the *How this works* panel again after pulling, and renumber **your own** new
  item if it collides.
- **Several AI sessions against one checkout is a special case.** They share one
  working tree, so two of them editing the same file clobber each other even in
  different regions. Have them enumerate their peers and agree on file ownership
  before editing, and keep `tracker/state.json` owned by one session — it is
  user-authored and its status override masks whatever `tracker/data.js` says.
- **In a shared working tree, `git add <file>` takes the whole file** — including
  whatever the other session wrote into it since you last looked. `CHANGELOG.md`
  and `tracker/data.js` are the two everyone touches, so read
  `git diff --cached` before committing either, and stage with `git add -p` when
  the file is one you agreed to share. Sweeping someone else's half into your
  commit isn't destructive, but it lands their work under your message and ahead
  of the code it describes; if you notice before pushing, say so in the message
  rather than unpicking it.

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
