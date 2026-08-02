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
pytest -n auto                    # run the test suite (parallel — the AppTest
                                  # boots dominate runtime; CI runs it this way)
ruff check --exclude other_vis .  # lint
ruff format --exclude other_vis . # auto-format
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push and PR
across Python 3.11/3.12/3.13/3.14. See [AGENTS.md](AGENTS.md) and the package
[CLAUDE.md](scanpath_studio/CLAUDE.md) for an architectural overview.

Add a concise entry to the `[Unreleased]` section of
[`CHANGELOG.md`](CHANGELOG.md) — a line or two grouped under Added / Changed /
Fixed, not a per-tweak log.

If you add a user-facing feature, expose it on **every** surface — not just
visually, but also the deep link / Share, the CLI, and the headless API. See
*Exposing a feature on every surface* in [AGENTS.md](AGENTS.md).

Work items are tracked in [`tracker/data.js`](tracker/data.js) (open
[`tracker/index.html`](tracker/index.html) in a browser to read it) — if your
PR corresponds to a tracker item, update its status and write-up; the
conventions are in the tracker's *How this works* panel and `CLAUDE.md` →
*Tracking work*.

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
