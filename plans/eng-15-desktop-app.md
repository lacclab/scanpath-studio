# ENG-15 — Standalone desktop application (ADR + design)

**Status:** accepted 2026-07-15 · **Tracker:** `IMPROVEMENTS.md → ENG-15`

## Context

Scanpath Studio's entry points today are the PyPI package (`pip install
scanpath-studio` + a terminal command) and the hosted Streamlit Community Cloud
demo. Both exclude a real audience: reading researchers who don't have a Python
toolchain and can't (or shouldn't) upload private eye-tracking data to a hosted
app. A double-clickable desktop build closes that gap and keeps all data local.

## Decision

**PyInstaller `onedir` bundle + the system default browser**, built per-OS on
GitHub Actions.

- A small launcher ([`desktop/launcher.py`](../desktop/launcher.py)) starts the
  Streamlit server on a free localhost port (branded theme flags reused from
  `cli._theme_cli_flags`, file-watcher off, usage stats off) and opens the
  user's default browser once the server answers its health check.
- The PyInstaller spec ([`desktop/scanpath_studio.spec`](../desktop/scanpath_studio.spec))
  freezes the launcher with the whole `scanpath_studio` package — including the
  package *source* files (Streamlit re-execs `app.py` from disk, so `.py`
  sources must ship as data, not only as compiled modules in the archive) and
  `sample_data/` — plus the data/metadata of the asset-heavy dependencies
  (streamlit, plotly, streamlit-sortables, kaleido, imageio-ffmpeg).
- `onedir`, not `onefile`: starts in seconds instead of unpacking a huge
  archive on every launch, and trips antivirus heuristics far less. CI archives
  the directory (`.tar.gz` on Linux/macOS to keep the executable bit, `.zip` on
  Windows).
- Console stays visible (`console=True`) in v1 so server logs and errors are
  observable; a windowed/native-window build is a follow-up (below).

## Alternatives considered

- **stlite (Pyodide/WASM) desktop** — rejected: the app depends on `scipy`,
  `pyarrow`/Parquet, and Chrome-based Kaleido image + GIF/MP4 export, which
  don't (fully) run under WASM; performance on full corpora would also regress.
- **Electron/Tauri wrapper around a bundled server** — rejected for v1: adds a
  JS build toolchain and a second packaging system for what amounts to a
  browser window; the launcher + default browser gets the same UX with zero new
  toolchains. Tauri remains attractive later for a signed, windowed shell.
- **conda constructor / BeeWare briefcase** — rejected: installer-style UX
  (multi-step install, larger download) rather than "unzip and double-click",
  and briefcase would still need the same Streamlit-under-freeze work.

## Gotchas addressed (from the ENG-15 scope)

- **Theme from any launch dir (BUG-6):** the launcher passes
  `cli._theme_cli_flags()` explicitly, so the frozen app never depends on a
  `.streamlit/config.toml` relative to the launch directory.
- **`importlib.resources` under freezing:** the launcher resolves `app.py` via
  `scanpath_studio.__file__` next to the collected package sources; the spec
  collects the package with `include_py_files=True` so `sample_data/`, fonts,
  and the sources all land under the bundle.
- **Streamlit development-mode detection:** frozen Streamlit can resolve
  `global.developmentMode=true` (which then rejects `--server.port`); the
  launcher forces `--global.developmentMode=false`.
- **Chrome/Kaleido (ENG-10):** PNG/SVG/PDF and GIF/MP4 export still need a
  Chrome/Chromium on the machine — same as the pip install. Kaleido v1 finds a
  system Chrome or downloads one to the user cache dir; HTML export remains the
  browser-free fallback. Documented in `docs/getting-started.md`.
- **`st.cache_data` / temp paths:** unaffected — caches are in-process and
  temp files go through `tempfile`, not paths relative to the bundle.

## Verification

`desktop/smoke_test.py` runs against the built bundle in CI (and locally):

1. `ScanpathStudio --selfcheck` — inside the frozen process: load the bundled
   sample, resolve a trial, build the scanpath figure, render HTML. Catches
   missing hidden imports / data files without needing a browser.
2. Boot test — launch with `SCANPATH_DESKTOP_NO_BROWSER=1` on a pinned port,
   poll `/_stcore/health` until `ok`, `GET /` must be HTTP 200, then terminate.

## CI / distribution

[`.github/workflows/desktop.yml`](../.github/workflows/desktop.yml): matrix
over `ubuntu-latest` / `macos-latest` / `windows-latest`, `pip install .
pyinstaller`, build from the spec, run the smoke test, upload the archive as a
workflow artifact; on a `v*` tag the archives are attached to the GitHub
release. Runs on tags and `workflow_dispatch` (not per-PR — a 3-OS ~15-min
build is release infrastructure, not a PR gate).

Icons are generated once by `desktop/make_icons.py` (a scanpath motif — text
lines + fixation dots + saccade arcs) and committed under `desktop/icons/`
(`.ico` for Windows, `.icns` for macOS, `.png` master).

## Follow-ups (out of scope for v1)

- Native window (pywebview) or Tauri shell instead of a browser tab.
- Code signing / notarization (macOS Gatekeeper and Windows SmartScreen will
  warn on unsigned builds — documented in the download instructions).
- A proper macOS `.app` bundle + `.dmg`, and a Windows installer (Inno Setup).
