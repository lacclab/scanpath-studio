# Copilot Instructions — Scanpath Studio

This file is deliberately short: a second copy of the house rules drifts. The
sources of truth are

- [`AGENTS.md`](../AGENTS.md) — the architecture map: modules, pipeline,
  canonical columns, code style, the "adding a new …" recipes, releasing;
- [`CLAUDE.md`](../CLAUDE.md) — the working agreements: commits, changelog,
  tracking work, the approval gate;
- [`scanpath_studio/CLAUDE.md`](../scanpath_studio/CLAUDE.md) — the per-module
  reference and gotchas;
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — setup and the checks CI gates on.

Read them before changing code. The rules most worth repeating:

- **Use the project's toolchain**, not whatever is on `PATH`:
  `pip install -e ".[test,lint]"` or `uv sync --extra test --extra lint`. CI
  runs pandas 3 and ruff pinned in the `lint` extra.
- **Run the app on loopback**: `scanpath-studio`, or
  `streamlit run streamlit_app.py --server.address 127.0.0.1`.
- **Before every commit**: `ruff check .` and `ruff format .` (CI gates on both),
  and `pytest -n auto`.
- **A user-facing feature reaches every surface** — the UI, the deep link /
  Share, the CLI and the headless API (`AGENTS.md` → *Exposing a feature on
  every surface*).
- **Never rename the `global_*` / `single_*` / `filter_*` widget keys** — deep
  links and saved configs depend on them — and keep the spatial plot on
  `tabs._render_true_scale_chart`, never `st.plotly_chart`.
- **Every item has a stable ID** (`VIZ-37`), cited in the commit subject and a
  two-tier `CHANGELOG.md` entry. Take the next number from `CHANGELOG.md`, the
  GitHub issues, `tracker/data.js` *and* the open PRs (`CLAUDE.md` → *Tracking
  work*).
- **`main` is protected** — land work through a branch and a pull request. No AI
  co-author trailers in commit messages.
- **Don't edit** `tracker/` (a frozen archive), `uv.lock`, `site/` or
  `*.egg-info`.
