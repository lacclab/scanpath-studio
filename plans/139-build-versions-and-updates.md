# #139 / #385 — Build versions, *Check for updates*, and one-click desktop updates (design)

**Status:** agreed with the user 2026-10-07 · **Tracker:**
[#139](https://github.com/lacclab/scanpath-studio/issues/139) (sections 1–2, first PR) ·
[#385](https://github.com/lacclab/scanpath-studio/issues/385) (section 3, second PR) ·
*What's new* split out to [#386](https://github.com/lacclab/scanpath-studio/issues/386)

## Context

The user asked, on 2026-10-07, for three things:

1. Versions finer than releases — *"smaller version numbers e.g. when merging
   into main so that it is easier to differentiate versions"*.
2. A **Check for updates** button, so a user can see their version against the
   latest.
3. If not too complicated, **in-app updating** of the desktop app.

Today the version is one hand-set literal, `__version__ = "0.35.0"` in
`scanpath_studio/__init__.py`. `pyproject.toml` reads it
(`[tool.setuptools.dynamic]`), `publish.yml` refuses a tag that does not match
it (ENG-62), `tests/test_citation.py` pins `CITATION.cff` to it, and the
desktop spec derives `CFBundleShortVersionString` from it. A tag is the only
thing that publishes: PyPI, the three desktop bundles, a Zenodo version, Slack,
and the demo's `stable` branch. Between tags every build reports the last
release — at the time of writing `main` is `v0.35.0-3-g8f182193` and says
"0.35.0" everywhere.

## Decisions

| Question | Call | Why |
| --- | --- | --- |
| Are per-merge versions installable releases? | **No — labels only.** | Publishing per merge would cut a PyPI release, ~75 min of desktop builds, a Zenodo DOI version and a demo redeploy on every merge. |
| Who computes the build version? | **The app, at runtime, from git** (approach B). Not setuptools-scm. | scm needs tag history in every build checkout — every CI workflow, and the Community Cloud demo's clone of `stable`, which is unverified and would fail or show `0+unknown` without tags. Editable installs would freeze the number at install time. B leaves the tag gate, CITATION parity and `/release` alone. Cost: a `main` wheel's metadata still says the release. |
| When does the app go online to check? | **Only on click.** | `docs/privacy.md` promises network activity only on an explicit action; one line is added rather than the promise changed. Answers #139's first 2026-09-02 question (option b). |
| Where is "latest" read from? | **GitHub's latest release**, one source for every install kind. | It carries the version, date, notes link and each desktop archive with its sha256 `digest`. Anonymous rate limit (60/h per IP) is ample for a click. |
| Does the app run pip? | **No.** It shows the command for the detected install. | uv environments have no pip, conda/system Pythons can be externally managed, and the server would need a restart anyway (Streamlit never reloads imported modules). |
| Desktop in-app update | **One-click *Update & restart* on all three OSes**, second PR (#385). | Feasible; the cost is testing, which a CI end-to-end step covers (section 3). |

## Section 1 — the build version (#139)

### The literal

`scanpath_studio/__init__.py` keeps one hand-set literal, renamed
**`__release__ = "0.35.0"`** — the release this tree descends from. It is what
`pyproject.toml` (`attr = "scanpath_studio.__release__"`), `publish.yml`'s
tag gate, `tests/test_citation.py`, the desktop spec's
`CFBundleShortVersionString` and the `/release` skill read and bump.

**`__version__` becomes the build version**, resolved lazily through the
module's existing `__getattr__` (so `import scanpath_studio` stays cheap) and
cached. Every current reader of `__version__` — About, `--version`, the CLI
help, crash reports, the export bundle README, saved configs and recipes —
therefore reports the build without being touched.

### Resolution order (`build_info.py`)

First source that applies wins:

1. **Git checkout** — only when the package's parent directory is this repo's
   root (`.git` and a `pyproject.toml` naming `scanpath-studio` both present),
   so a venv that happens to live inside some other repo is never described.
   `git describe --tags --long --dirty --match "v[0-9]*"`, 2 s timeout.
2. **Build stamp** — a `_build.json` next to the package, written by the
   desktop spec at build time (desktop builds dispatched from `main`).
3. **VCS install** — `direct_url.json` (PEP 610) with `vcs_info.commit_id`, as
   `pip install git+…` records it.
4. **Otherwise** — the release literal, exactly. This is also the fallback for
   every failure (no git on PATH, no reachable tag, a shallow clone), so the
   demo can never break on it.

### Format (PEP 440, so it sorts)

| Situation | `__version__` |
| --- | --- |
| at the tag, clean | `0.35.0` |
| 3 commits after the tag | `0.35.0.post3+g8f18219` |
| … with uncommitted edits | `0.35.0.post3+g8f18219.dirty` |
| at the tag, with edits | `0.35.0+g8f18219.dirty` |
| `pip install git+…` (distance unknown) | `0.35.0+g8f18219` |

`0.35.0 < 0.35.0.post3+g… < 0.35.1`. On `main` the distance counts merges
(every PR lands as one squash commit); on a feature branch it counts commits.

`BuildInfo` (frozen dataclass): `version`, `release`, `distance`, `commit`,
`dirty`, `source` (`checkout` / `stamp` / `vcs` / `release`), and a one-line
`describe()` for humans: "development build — 3 commits after v0.35.0, at
8f18219".

### Install kind (used by section 2)

`install_kind()`: `desktop` (frozen) · `checkout` · `vcs` · `uv-tool`
(prefix under uv's tool dir) · `pipx` (prefix under `pipx/venvs`) · `uv`
(`INSTALLER` = `uv`) · `pip` (anything else).

### Desktop spec

`desktop/scanpath_studio.spec` describes the repo it sits in (via
`build_info`'s checkout reader), writes `_build.json` into the build
directory and adds it to `datas` under `scanpath_studio/`.
`CFBundleShortVersionString` reads `__release__`. `desktop.yml`'s checkout
gains `fetch-depth: 0` so a dispatched build from `main` can see its tag.

## Section 2 — *Check for updates* (#139)

### `updates.py` (pure, stdlib-only, no Streamlit)

- `fetch_latest_release(timeout=5.0, fetch=…)` → `Release(version, tag,
  published_at, url, assets)`, `Asset(name, url, size, digest)`. Reads
  `https://api.github.com/repos/lacclab/scanpath-studio/releases/latest`
  (which already excludes drafts and pre-releases) with a
  `scanpath-studio/<version>` User-Agent. The fetcher is injectable; tests
  never touch the network.
- `check_for_updates(...)` → `UpdateCheck(status, current, latest, message,
  command, download)` with `status` one of:
  - `up_to_date` — "v0.35.0 — the latest release."
  - `update_available` — "v0.36.0 is out (released 9 Oct 2026)", with the
    release-notes link, and `command` / `download` for this install.
  - `ahead` — "Development build — 3 commits after v0.35.0, the latest
    release."
  - `error` — offline, timeout, rate-limited (with the reset time) or an
    unexpected response, in plain words. Never raises.
- Update instruction per install kind: `checkout` → `git pull` ·
  `uv-tool` → `uv tool upgrade scanpath-studio` · `pipx` →
  `pipx upgrade scanpath-studio` · `uv` → `uv pip install -U scanpath-studio`
  · `pip` → `pip install -U scanpath-studio` · `vcs` → `pip install -U
  "git+<recorded url>"` · `desktop` → this platform's archive
  (`ScanpathStudio-macos-arm64.dmg` / `-windows-x86_64.zip` /
  `-linux-x86_64.tar.gz`). A release whose desktop archive has not been
  uploaded yet (up to ~75 min after the tag) says so and links the release
  page; an Intel Mac, which has no build, gets the release page too.

### Surfaces

- **UI** — ❓ Help → About: the version line spells out the build
  (`BuildInfo.describe()`), followed by a **Check for updates** button. The
  result renders under it; commands use `st.code` (copy button), the desktop
  download is a link button. The fetch is wrapped in `st.cache_data(ttl=600)`
  in the app layer. The button is hidden unless
  `persistence.server_bound_to_loopback()` — the hosted demo runs `stable`, and
  "how to update" means nothing to its visitors.
- **CLI** — `scanpath-studio --version` prints the build version (unchanged
  code path). New `scanpath-studio version` prints the build details and
  install kind; `version --check` adds the network check and the instruction.
  Exit 1 only when the check itself fails. Added to `_COMMANDS`, `_HELP`, and
  `scripts/docs_support.py`'s parser map for the generated CLI reference.
- **API** — `api.version_info() -> BuildInfo` and
  `api.check_for_updates(timeout=5.0) -> UpdateCheck`, in `__all__`.
- **Deep link / Share** — do not apply: a version check is not state you link
  to.

### Docs

- `docs/getting-started.md` — an *Updating* section: About → Check for
  updates, `scanpath-studio version --check`, and what a
  `0.35.0.post3+g…` version means.
- `docs/privacy.md` → *Network activity* — *Check for updates* contacts
  api.github.com only when clicked, and sends nothing but the request (the
  User-Agent carries the app version).
- `AGENTS.md`, `CLAUDE.md` (*On release*), `CONTRIBUTING.md` (*Releasing*) and
  `.claude/skills/release/SKILL.md` — bump `__release__` instead of
  `__version__`. Architecture map gains `build_info.py` / `updates.py`.
- Two changelog fragments: `changelog.d/139.changed.md` (the build version)
  and `changelog.d/139.added.md` (*Check for updates*).

## Section 3 — one-click *Update & restart* in the desktop app (#385)

### Flow

About → *Check for updates* → "v0.36.0 is out" → **Update & restart** (with
*Download instead* beside it). A loading card (UX-165 `loading.card`, with its
Cancel) runs: downloading (MB of MB) → checking → testing the new version →
"Restarting into v0.36.0". The new version opens in a fresh window; the
recovery cache (ENG-26) restores the loaded datasets and settings. Any failure
names the step and the reason, leaves the install untouched, and offers the
download link.

### `desktop_update.py` (stdlib only, no Streamlit)

1. **`can_update()`** → `None` or a refusal reason: not frozen; no archive for
   this platform; macOS app translocated (path under `/AppTranslocation/` — it
   was never moved out of the `.dmg` or Downloads); install location not
   writable; not enough free disk (≈3× the archive).
2. **Download** the asset over HTTPS from the hard-coded repo's release, with
   `progress.report()` ticks and the cancel checkpoint; then **verify sha256**
   against the asset's `digest`. A missing digest refuses.
3. **Stage** in a scratch folder on the same volume as the install:
   - macOS — `hdiutil attach -nobrowse -readonly -mountpoint <tmp>`, `ditto`
     the `.app` out, detach; require `codesign --verify --deep --strict`, a
     `TeamIdentifier` equal to the running app's, and `spctl -a -t exec`
     acceptance.
   - Windows — `zipfile` extract.
   - Linux — `tarfile` extract with `filter="data"`.
4. **Self-test** — run the staged executable's `--selfcheck`; non-zero refuses.
5. **Swap** — write a helper (POSIX `sh` on macOS/Linux, PowerShell on
   Windows) to the scratch folder and start it detached
   (`start_new_session=True` / `DETACHED_PROCESS`), then quit the app the way
   the idle watcher does (`os._exit`, after the "Restarting" message has been
   sent). The helper waits for the app's PID to exit, moves the old version
   aside and the new one into place, and relaunches (`open -n` on macOS).
   - macOS swaps the `.app`'s `Contents` rather than the bundle, because the
     user owns the `.app` they dragged in even on a standard account.
   - Windows/Linux swap the executable and `_internal` inside the
     `ScanpathStudio` folder, not the folder itself, so the Windows
     installer's `unins000.*` beside them survive (amended while planning —
     see below).
6. **Roll back** — the relaunched launcher writes a "booted" marker once its
   server answers the health check. If none appears within 180 s (Windows'
   first-launch Defender scan needs that long), the helper restores the old
   version and relaunches it. The next good launch deletes the old copy and
   any scratch files.

Never downgrades, never installs a pre-release, touches nothing outside its
own install.

### Surfaces

- **UI** — the About button above (desktop only; the pip channels keep
  section 2's command).
- **Launcher** — `ScanpathStudio --update`, a headless run of the same flow
  beside `--selfcheck` (also what CI drives).
- **CLI / API / deep link** — do not apply: updating replaces the frozen
  bundle, which only the bundle itself can do.

### Testing

- Unit tests: download + digest (good, bad, missing), each refusal, staging
  per OS on synthetic archives, helper-script generation, rollback logic.
- **End-to-end in `desktop.yml`, all three OSes, every tag:** copy the fresh
  build to an "installed" location; point a test-only feed override
  (`SCANPATH_UPDATE_FEED`, a local JSON file whose asset is the same fresh
  archive, labelled as a newer version) at it; run `--update`; assert the swap,
  the relaunch and the booted marker; then run `desktop/smoke_test.py` against
  the swapped install. This proves the mechanics before a user depends on the
  first release that ships the updater.
- What CI cannot reproduce — Gatekeeper / SmartScreen on a real machine, and
  Windows' unsigned-`.pyd` blocking from #121 — goes in #385's Review checklist
  as one real v(N) → v(N+1) update per OS.

### Known constraints

- macOS builds are signed and notarized (v0.35.0's signing and notarization
  steps both ran), which is what makes the Team-ID check possible.
- Windows builds are unsigned (#121): the digest is the only trust anchor, and
  the updater inherits #121's field-test problem rather than fixing it.

### Amendments made while planning (2026-10-07)

The implementation plan, [`385-desktop-updater.md`](385-desktop-updater.md),
settles what this section left open or what changed after it was written
(#388's Windows installer):

- **Payload entries, not folders.** Every OS swaps entries inside the install
  root: `Contents`, or the executable plus `_internal`. The Inno Setup
  uninstaller stays, and its uninstall entry's `DisplayVersion` is updated.
- **Windows updates from the `.zip`.** *Download* still offers the
  `-setup.exe`.
- **One state folder** on the install's volume holds the download, the staged
  copy, the old payload, the markers and `result.json`. It is the per-user
  cache when that shares the volume, else `.ScanpathStudio-update` beside the
  install; otherwise the update is refused.
- **The relaunch reports in by install root, not version** (`pending.json` →
  `started` → `booted`). That lets CI offer the same build as `v99.0.0`
  through `SCANPATH_UPDATE_FEED`, which only `--update` honours.
- **Child processes start fresh** (`PYINSTALLER_RESET_ENVIRONMENT=1`, the
  user's `LD_LIBRARY_PATH`).
- **An ad-hoc-signed macOS build is refused**, since the Team ID is the trust
  anchor.
- **The outcome survives the restart:** About shows a rolled-back or failed
  update as a warning, and a successful one as "Updated from v…".

## Out of scope

- *What's new* — reading the release notes inside the app (#386, on hold).
- An automatic or periodic check — rejected (privacy).
- Publishing per-merge builds anywhere.
