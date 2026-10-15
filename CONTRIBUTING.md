# Contributing

Issues and pull requests are welcome. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md); report security problems through
[SECURITY.md](SECURITY.md), not a public issue.

## Setup

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
uv sync --extra test --extra lint     # or: pip install -e ".[test,lint]"
uv run streamlit run streamlit_app.py --server.address 127.0.0.1
```

Python 3.11–3.14. Bind to `127.0.0.1`: the on-device recovery cache is off on a
server other machines can reach.

The architecture map is [AGENTS.md](AGENTS.md); the per-module reference and
gotchas are in [scanpath_studio/CLAUDE.md](scanpath_studio/CLAUDE.md). AI
coding assistants pick both up via [CLAUDE.md](CLAUDE.md).

### If a code change doesn't show up

Streamlit doesn't reload imported modules on rerun, and `@st.cache_data`
doesn't hash the helpers a cached function calls. **Restart the server** — a
rerun or "Clear cache" isn't enough. If a fresh launch still shows the old app,
an old server holds the port (`lsof -nP -iTCP:8501 -sTCP:LISTEN`).

## Before you open a PR

```bash
uv run --extra test pytest -n auto
uv run --extra lint ruff check .
uv run --extra lint ruff format .
```

- **Use the project's toolchain** (`uv run`), not a bare `python`/`ruff` on
  `PATH`: CI resolves the newest pandas the bounds allow and pins ruff exactly,
  so another interpreter can pass what CI rejects.
- **Add a changelog fragment**, never edit `CHANGELOG.md`: one line of plain
  text in `changelog.d/<issue>.<group>.md` (or `<slug>.<group>.md` with no
  issue) — see [changelog.d/README.md](changelog.d/README.md).
- **Expose a user-facing feature on every surface** — the UI, the deep link /
  Share, the CLI and the headless API (AGENTS.md → *Exposing a feature on every
  surface*).

## Working together

- Work is tracked in [GitHub Issues](https://github.com/lacclab/scanpath-studio/issues)
  and cited by `#N`. Claim an issue (`gh issue edit <n> --add-assignee @me`)
  before starting it; closing it is the maintainer's sign-off, not yours.
  Conventions: CLAUDE.md → *Tracking work*.
- `main` is protected: land work as a branch + PR, one commit per feature or
  fix, with the issue in the subject (`fix(viz): … (#341)`).
- Several sessions sharing one checkout: agree who owns which file, stage
  selectively, and read `git diff --cached` before committing.

## Docs site

User docs live in `docs/` (MkDocs Material), published per release tag.

```bash
uv run --extra docs mkdocs serve
uv run --extra docs mkdocs build --strict   # the CI gate
```

New pages need a `mkdocs.yml` nav entry. Generated parts (gallery, references)
come from `scripts/docs_support.py` at build time; the API
reference comes from the `api.py` docstrings, so keep those current.

## More

- **Adding a public dataset:** [docs/contributing-a-dataset.md](docs/contributing-a-dataset.md).
- **Dependencies** are declared only in `pyproject.toml`. Don't commit a
  `uv.lock`: the hosted demo would silently switch onto it.
- **Releasing:** AGENTS.md → *Releasing* (or the `/release` skill).

By contributing, you agree your contributions are licensed under the
[MIT License](LICENSE).
