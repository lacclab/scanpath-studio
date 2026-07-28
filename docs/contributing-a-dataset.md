# Contributing a dataset

Scanpath Studio ships three ready-made corpus adapters — OneStop, PoTeC, and
MultiplEYE. Each shows up as an entry in the app's data-source picker and as a
`load_*` function in the headless API. This page is the contract for adding a
fourth.

It is about getting a **public corpus shipped with the app**, so that in a
future release every user finds it in the picker. Two things it is *not*:

- Loading a corpus you already have on disk needs no code at all — see
  [Bring your own data](bring-your-own-data.md).
- The canonical column names and table shapes are in
  [Data format](data-format.md); this page doesn't repeat them.

## What "built-in" means

Three levels, and the built-in data sources use all three:

| Level | Where the data lives | Precedent |
| --- | --- | --- |
| **Bundled in the wheel** | inside the installed package, under `scanpath_studio/sample_data/` | Only the demo — a 3-reader / 36-trial OneStop subset (4.4 MB). |
| **Download on demand** | fetched from the corpus' own host into a folder the user picks, then cached on disk | PoTeC (~45 MB), OneStop (OSF reports, tens to a few hundred MB each). |
| **Local directory** | a tree the user already has; the adapter only reads it | MultiplEYE (no public download URL). |

Only the first is literally bundled, and in practice a new corpus lands at level
2 or 3 — nothing corpus-scale goes into the wheel (see *Bundled in the wheel vs.
download on demand* below). All three levels are equally "built-in" from the
user's side: one entry in the picker, one `load_*` in the API.

## The adapters that exist today

All three live in
[`scanpath_studio/datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py).

| Corpus | Data comes from | Entry points | Why it needs an adapter |
| --- | --- | --- | --- |
| **OneStop** | OSF release (`public` variant) or a local lab export (`lacclab`) | `onestop_raw_frames` · `load_onestop` · `download_onestop` · `onestop_present` | Not the columns — the reports already match the bundled demo's EyeLink schema. The adapter picks the right regime × part files, filters the OSF zips' `__MACOSX` cruft, and folds the trial *part* into the trial id so parts don't collide. |
| **PoTeC** | OSF archive (fixations) + the DiLi-Lab GitHub repo (AOI files) | `potec_raw_frames` · `load_potec` · `download_potec` · `potec_present` | 900 per-trial TSVs to concatenate; stimulus-level word AOIs with no participant column; fixations with **no coordinates** at all — x/y is reconstructed from the fixated character's box centre in the per-text `.ias` files. |
| **MultiplEYE** | a local session tree (also a browser-upload path) | `multipleye_raw_frames` · `load_multipleye` · `multipleye_inventory` · `multipleye_frames_from_uploads` | Participant, session, trial, and stimulus exist only in folder and file names; character AOIs must be aggregated into word boxes; the pages of one stimulus reuse the same screen coordinates, so each page has to become its own trial. |

If your corpus is just two tables with recognizable column names, you probably
don't need an adapter: the generic loader already accepts a list or glob of
files and auto-detects EyeLink / Gazepoint / snake_case columns. Adapters exist
for the parts the generic path *cannot* guess — identity hidden in filenames,
coordinates that have to be reconstructed, AOIs at the wrong granularity, a
download step.

## What an adapter must provide

`datasets.py` is the only module that knows about a specific corpus. It is
pandas plus the standard library (`pathlib`, `urllib`, `zipfile`, …) and
imports **no Streamlit**. Keep it that way: it has to be importable from a
plain script, and everything app-facing lives in `app.py`.

### 1. A raw-frames function — the required entry point

```python
def <corpus>_raw_frames(
    root, *, download: bool = False, ...
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) ``(words, fixations)`` frames."""
```

It returns the two tables **before** normalization, in whatever column names
the corpus uses. That is deliberate: the app feeds them through the same
auto-detect → normalize → harmonize pipeline as an upload, so the sidebar
**Column mapping** panels still appear and stay overridable. A loader that
returned already-normalized frames would bypass them.

Requirements:

- **Read the whole corpus.** There is no per-source participant/text narrowing
  in the app any more — the global **Narrow by** trial filters scope it. Keep
  `readers=` / `texts=` / `sessions=` keyword arguments for the headless
  callers, but let them default to everything.
- **Concatenate multi-file corpora yourself**, or hand the paths to
  `data.read_tables`, which tags each row with its `source_file` stem — the way
  to recover identity that lives only in a filename.
- **Raise `FileNotFoundError` with a message that says what to do** (PoTeC's
  names the missing path and points at `download=True`). The app's loader
  catches it and prints it in the sidebar — `Couldn't load PoTeC from
  <root>: <your message>` — so the message is the whole error UI.
- **Read only.** The raw-frames function must not write anything: no caches, no
  rewritten source files, and never anything inside the installed package.
  Writing to disk is the downloader's job alone, and it writes only into the
  root the user pointed at.

### 2. A normalized loader

```python
def load_<corpus>(root, ...) -> Tuple[pd.DataFrame, pd.DataFrame]:
    words_raw, fixations_raw = <corpus>_raw_frames(root, ...)

    from . import api

    return api.load_scanpath_data(
        words=words_raw,
        fixations=fixations_raw,
        word_schema=dict(<CORPUS>_WORD_SCHEMA),
        fix_schema=dict(<CORPUS>_FIX_SCHEMA),
    )
```

[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] validates the
schemas, normalizes, and then harmonizes: stimulus-level word boxes (no
participant column) are broadcast across the participants found in the
fixations, and fixations with a word id but no coordinates are placed at their
word box's centre.

Pass **explicit schema dicts** when the corpus' column names are stable and you
want the loader to keep working if the corpus adds columns; omit them to let
auto-detection run (OneStop does, because its reports already match the demo's
schema). PoTeC's are the model — note `participant=None`, which is what marks
the word table as stimulus-level:

```python
POTEC_WORD_SCHEMA = dict(
    participant=None, trial="text_id", word_id="aoi", text="word", line="line",
    left="start_x", right="end_x", top="start_y", bottom="end_y",
)
POTEC_FIX_SCHEMA = dict(
    participant="reader_id", trial="text_id", duration="fixation_duration",
    x="x", y="y", fixation_id="fixation_index", word_id="word_index_in_text",
)
```

The full key sets are whatever `data.propose_word_schema` /
`data.propose_fix_schema` return:

- **Words** — `participant`, `trial`, `text_id`, `word_id`, `text`, `line`, and
  the box as either `x`/`y`/`width`/`height` **or**
  `left`/`right`/`top`/`bottom`. Validation blocks without `trial`, `word_id`,
  and one complete box form.
- **Fixations** — `participant`, `trial`, `text_id`, `fixation_id`,
  `timestamp`, `duration`, `x`, `y`, `word_id`. Validation blocks without
  `trial`, `duration`, and either `(x, y)` or `word_id`.

Your explicit dicts bind the **headless** loader only. The app never sees them:
it takes the raw frames from `<corpus>_raw_frames` and runs
`data.propose_word_schema` / `propose_fix_schema` over them, exactly as it would
for an upload. So auto-detection has to land on the same answer, or the user
opens your corpus and has to fix the mapping by hand. Check it before you ship —
on PoTeC's raw frames, detection returns `trial="text_id"`, `word_id="aoi"`,
`left="start_x"` …, `duration="fixation_duration"`, matching
`POTEC_WORD_SCHEMA` / `POTEC_FIX_SCHEMA`:

```python
from scanpath_studio import data, datasets

words, fixations = datasets.potec_raw_frames("data/PoTeC", texts=["b0"])
assert data.validate_word_schema(data.propose_word_schema(words)) == []
assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []
```

If a column can't be guessed, add its name to the right `*_CANDIDATES` list in
`data.py` rather than renaming it in the loader — that fixes it for every
dataset using the same convention.

### 3. Registration for any extra column you stamp

Normalization does not carry your columns along. `data.normalize_words` /
`normalize_fixations` build a **fresh** frame holding the canonical fields plus
whatever matches `data.WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS` (matched on
the *exact* source column name); everything else is dropped silently. So a
corpus-specific extra — reader metadata, a stimulus-image path, the stimulus
typeface, a genre facet — needs a `(source, dest, kind, category)` row there,
with `kind` ∈ `numeric | string | boolean | passthrough` and `category` ∈
`measure | linguistic | meta`:

```python
("stimulus_font_px", "stimulus_font_px", "numeric", "meta"),
("comprehension_questions", "comprehension_questions", "passthrough", "meta"),
```

That is how MultiplEYE's `image_path` / `image_x` / `image_y`,
`stimulus_font_px` / `stimulus_font_family`, `comprehension_questions`, and
`pp_*` reader metadata reach the app. Entries are inert for corpora that don't
emit the column, so adding yours costs other datasets nothing — but skipping it
means your enrichment work vanishes between the loader and the first plot, with
no error.

### 4. A presence check

```python
def <corpus>_present(root) -> bool:
```

Path stats only — no file reads — so the app can show a found/missing status
before any expensive load. Be **strict**: return `True` only when everything a
whole-corpus load needs is there. `potec_present` requires all twelve texts'
word *and* character AOI files, because a lenient "any AOI file" check would
pass a partial tree and then crash mid-load with no way for the user to
recover; requiring all of them lets the app offer the Download button, which
self-heals the gap.

### 5. A downloader, if the data is publicly fetchable

```python
def download_<corpus>(root, ...) -> Path:
```

Follow what `download_potec` / `download_onestop` do:

- **Skip anything already present**, so it is safe to call repeatedly and a
  second load never touches the network.
- **Write atomically** — fetch to `<dest>.part`, then `Path.replace` into
  place. An interrupted fetch must never leave a truncated file that the
  presence check then treats as complete; with hundred-MB reports that window
  is real. (An archive you extract can't use that trick — `download_potec`
  extracts the OSF zip in one go and gates the whole step on the target folder
  not existing yet.)
- **Print what it is fetching**, with the URL.
- **Fetch from the corpus' canonical host.** Both existing downloaders reuse
  the file ids from the corpus' own `download_data_files.py`. Scanpath Studio
  never mirrors or re-hosts anyone's data.

### 6. Constants worth exporting

At minimum the presentation monitor (`POTEC_MONITOR = (1680, 1050)`,
`MULTIPLEYE_MONITOR = (1920, 1080)`), which is what makes the plot
true-to-scale. Also export the valid text / regime / part lists you validate
against, so the CLI and the app can build their pickers from them instead of
re-typing the strings.

## Registering it in the app

Two additions to
[`app.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/app.py).

**A sidebar loader.**

```python
def _load_<corpus>_source(
    options_host=None, location_host=None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
```

It renders the corpus' controls and returns *raw* frames. The two hosts are the
sidebar sub-slots: source options (variant, regime, fixation source) go in
`options_host`, the data location in `location_host`. Use the shared helpers so
every corpus looks the same:

- `_dataset_dir_input(loc, default_dir=…, dir_help=…, structure_md=…, key_prefix=…)`
  — the *Data directory* text box, a **📁** button opening a native folder
  dialog (silently unavailable on a headless host, where the text box is the
  only control), and an *Expected files* expander. It returns the directory
  already resolved, so hand its return value — not the raw text — to your
  presence check. Write the layout tree as a `_<CORPUS>_STRUCTURE_MD` constant
  next to the existing ones; it is what tells a user who already has the data
  where to drop it.
- `_dataset_access_status(loc, root=…, present=…, download=…, size_hint=…, key_prefix=…, label=…)`
  — "Found in `<root>`" versus "Not downloaded yet (~45 MB)" plus a **⬇
  Download** button. It also records the main-area *this corpus isn't here yet*
  state, so a user who picks a corpus they haven't downloaded doesn't silently
  get demo scanpaths.
- When it isn't ready, `return load_sample_data()` — the app has to stay usable.
- Wrap the actual read in a module-level `@st.cache_data` function keyed on
  plain strings (`_cached_potec_raw_frames(root)`), so toggling a viz control
  doesn't re-read hundreds of files.
- Catch `(FileNotFoundError, ValueError, OSError)` around the read and surface
  it with `loc.error(...)`, returning empty frames.

**One registry entry**, in `PUBLIC_DATASET_REGISTRY`:

```python
"PoTeC — Potsdam Textbook Corpus": dict(
    loader=_load_potec_source,
    monitor=(1680, 1050),          # DELL P2210 — canvas snaps to this
    short="PoTeC",                 # what the picker shows
    language="German",
    size="75 readers · 12 texts",
    description="Potsdam Textbook Corpus — German reading of biology & "
    "physics textbook passages (expert/novice readers).",
    link="https://github.com/DiLi-Lab/PoTeC",
),
```

The dict key is the entry's token in the flat data-source picker (tagged 🌐);
`short` is the label shown, and `language` / `size` / `description` / `link`
become the caption, blurb, and *Dataset home ↗* link under it. `monitor` is the
real presentation screen — the canvas snaps to it on a source switch so the
scanpath renders at true scale. Put the default data directory in
`constants.py` as a `<CORPUS>_DEFAULT_DIR` — `_resolve_data_dir` anchors a
relative path to the project root (`scanpath_studio/`'s parent), not the
process cwd, so `data/PoTeC` means the same folder however the server was
launched.

Public datasets are enabled by default; `SCANPATH_PUBLIC_DATASETS=0` hides the
whole group.

## The other three surfaces

A dataset is a user-facing feature, so the project's *Exposing a feature on
every surface* rule applies — the picker entry is one surface out of four:

- **Headless API** — `load_<corpus>` plus a lazy re-export in `__init__.py`
  (add the name to `__all__` and to `_DATASET_EXPORTS`), so
  `sps.load_<corpus>(...)` works, and a `:::` autodoc block in
  [`docs/api.md`](api.md).
- **CLI** — a flag in `render`'s *input* argument group in `cli.py`, added to
  the exactly-one-input check at the top of `render()` so it can't be combined
  with `--sample` or `--words/--fixations`. PoTeC and OneStop use
  `--potec DIR` / `--onestop DIR` (with
  `--onestop-regime` / `--onestop-part` / `--onestop-variant` for the options);
  MultiplEYE currently rides `--source multipleye --export DIR`. Prefer the
  `--<corpus> DIR` shape.
- **Deep link / Share** — register the source in `_SHAREABLE_SOURCES` in
  `url_state.py`, and any per-corpus options in `_apply_url_preset` (read) and
  `_build_share_query` (write). Of the three built-in corpora only OneStop does
  this today: a shared link carries
  `?source=onestop_public&onestop_variant=…&onestop_regime=…&onestop_parts=…`.
  Note that `url_state.py` must not import `app.py`'s registry (that would be an
  import cycle), so a shareable corpus needs its picker key as a `constants.py`
  constant — `ONESTOP_PUBLIC_CHOICE` is the precedent. A corpus that skips all
  this still works, but a shared link can't reopen it (the Share panel says so).

Finally, add a page under **Datasets** in the docs describing the corpus and
the modelling decisions your adapter makes — [OneStop](onestop.md) and
[MultiplEYE](multipleye.md) are the templates — and list it in `mkdocs.yml`'s
`nav:` under `Datasets`. A page that isn't in the nav still builds, but nothing
links to it.

## Licence expectations

The bar: the corpus must be publicly available under a licence that permits
what the adapter does with it — reading it, and, for a downloader, fetching it
from its own host on the user's behalf.

How the existing adapters handle it:

- **No corpus data is vendored into this repository**, with one exception: the
  bundled demo, a subset of OneStop used under OneStop's own licence, cited in
  the README and carried in `constants.CITATION["corpus_note"]` — which
  `export.bulk_export` writes into every export bundle's `README.md`, so the
  attribution travels with the data a user takes away.
- **Downloads point at the corpus' own host** — PoTeC's OSF archive and its
  GitHub repo, OneStop's OSF release — reusing the file ids those projects
  publish. Nothing is mirrored.
- **Attribution rides in the registry entry** (`link` → *Dataset home ↗*) and
  in the corpus' docs page.
- **Ported code is a separate question.** Third-party code carries a `NOTICE`
  entry — the ten drift-correction algorithms in `alignment.py` are a native
  port of Carr et al. (2021), CC BY 4.0, attributed there. If your adapter
  ports logic from the corpus' own tooling, add a NOTICE entry, and check the
  licence is compatible with this project's MIT licence (a GPL dependency is
  not acceptable — that is why `alignment.py` is a native port rather than a
  dependency).

So the PR has to state the corpus' licence, its citation, and a stable public
URL (see *Submitting it* below for the rest of the checklist).

## Bundled in the wheel vs. download on demand

The installed package is about 1.3 MB of Python and 4.4 MB of `sample_data/` —
the demo is most of the wheel. That is the whole budget. A corpus that would
add more than a couple of MB is download-on-demand or local-directory, never
bundled, and in practice that rules out every complete corpus: PoTeC's
eye-tracking archive alone is ~45 MB, and a single OneStop report runs from
tens to a few hundred MB.

What ships is declared in two places that must be updated together —
`MANIFEST.in` (sdist) and `[tool.setuptools.package-data]` in `pyproject.toml`
(wheel). Both are restricted to `sample_data/`: the `.csv` / `.parquet` /
`.feather` tables and the demo stimulus `images/`.

Download-on-demand, as it works today:

1. The user picks a folder (seeded from the corpus' `<CORPUS>_DEFAULT_DIR`);
   nothing is ever written into the package.
2. `<corpus>_present(root)` decides found vs. missing from path stats alone.
3. `_dataset_access_status` shows the status and, when missing, a **⬇
   Download** button with a size hint — and records the main-area "isn't
   available yet" state explaining that what's on screen is the demo.
4. `download_<corpus>` fetches only what's absent, writing atomically.
5. From then on the corpus is on disk: `present` is `True`, and the loader
   never touches the network again.

## Sample size, and `update_sample_data.py`

`python -m scanpath_studio.update_sample_data` regenerates the bundled demo
from the full OneStop exports. Its flags are the sample-size policy in
executable form: `--participants` (3), `--articles` (2, each spanning the
Advanced and Elementary version), `--seed`, `--max-rows` (cap on rows read from
each multi-GB source CSV), `--source-dir`, `--output-dir`. It writes
`ia` and `fixations` as both CSV and Parquet, then synthesizes the `raw_gaze`
overlay from the fixations of one bundled trial (`--raw-gaze-only` rebuilds
just that). The result: 3 readers, 12 trials each (36 in all), 3,922
interest-area rows, 3,209 fixation rows.

That is the size a bundled sample is meant to be — large enough to exercise
every feature (several readers of the same paragraph, both difficulty levels,
pre-computed per-word measures, a raw-gaze overlay, stimulus images) and small
enough to disappear into the wheel. If a proposal ever adds to or replaces the
bundled sample, it needs an equivalent re-runnable script: the demo has to be
reproducible from its source corpus, not a hand-curated blob.

Stimulus images are *not* produced by that script — the demo PNGs come from a
separate render step and are placed at data origin `(image_x=358,
image_y=184)`; `tests/test_smoke.py::TestStimulusImageAlignment` asserts that
origin keeps every rendered line on its word boxes.

## Tests a new adapter needs

| File | What it must cover |
| --- | --- |
| `tests/test_dataset_support.py` | The loader itself, against a tiny corpus-shaped tree built under `tmp_path` — see the `potec_root` / `multipleye_root` fixtures and `_fake_onestop_reports`. Assert the normalized output exactly: participant and trial ids, word text, reconstructed coordinates, durations, word links. Plus the failure paths: unknown text/regime/part → `ValueError`, missing files → a `FileNotFoundError` whose message tells the user what to do, and `<corpus>_present` on a partial tree. |
| `tests/test_apptest.py` | The app wiring. `test_each_public_dataset_loader_ui_renders` loops over the whole `PUBLIC_DATASET_REGISTRY` and requires each loader to boot the app with no exception, no `st.error`, and a *Data directory* text input. A new entry is picked up by the loop automatically — **but add your `<CORPUS>_DEFAULT_DIR` to the tuple of constants it monkeypatches to an empty `tmp_path`**. Without that the test reads your real default directory, so it passes or fails depending on what the dev machine happens to have downloaded, and a present corpus makes it read the whole thing and blow the timeout. `test_public_dataset_canvas_snaps_to_its_monitor` covers the `monitor` field. |
| `tests/test_cli.py` | The new `render` flag: that it conflicts with the other inputs (`--potec` + `--sample` → *exactly one input*), and that it renders. |
| `tests/test_app.py` | Only if you made the source shareable: the deep-link round-trip (build the query → apply it into a fresh session → the options come back), and that a hand-edited link with junk options is ignored rather than seeding a bad widget value. |
| `tests/test_<corpus>_enrichment.py` | If the adapter merges side data (reader metadata, comprehension questions, pre-computed reading measures, stimulus images), one test per surface, including the "file absent → column simply not there" case. `tests/test_multipleye_enrichment.py` is the model. |

Two hard rules: **tests never hit the network** — monkeypatch the downloader
(as the `onestop_offline` fixture does) or build the tree directly — and
**expectations are hand-computed**, not snapshots of whatever the code emitted.
`test_load_potec` asserting `x == [104.0, 156.5, 86.5]` (the centres of the
character boxes the fixations landed on) is the standard.

## Worked example: PoTeC, end to end

PoTeC is the smallest complete adapter; read it in this order.

1. **Understand the shape.** Fixations ship as 900 per-trial TSVs
   (`eyetracking_data/scanpaths/reader<N>_<text>_scanpath.tsv`), word AOIs once
   per text with no participant column
   (`stimuli/word_aoi_texts/word_aoi_<text>.tsv`), and character AOIs per text
   (`stimuli/aoi_texts/<text>.ias`). Fixations carry the fixated character's
   AOI index, no pixels.
2. **Fetch — `download_potec(root, *, fixation_source="scanpaths")`.** Pulls
   the eye-tracking zip from OSF (`_POTEC_OSF_RESOURCES`), keeping only the
   real `.tsv` members (the OSF zips carry macOS resource-fork cruft), then the
   24 AOI files from GitHub raw, each written to `<name>.part` and renamed into
   place. Everything already on disk is skipped.
3. **Check — `potec_present(root)`.** A non-empty
   `eyetracking_data/scanpaths/` *or* `eyetracking_data/fixations/` folder
   (at least one `.tsv`), *and* both AOI files for all twelve texts
   (`_POTEC_TEXTS` = `b0`–`b5`, `p0`–`p5`). `is_dir` / `is_file` / one `glob`
   — no file is opened.
4. **Build the word table — `_potec_words`.** Reads each text's word AOI TSV,
   adds `text_id` (which lives only in the filename), and recovers `line` by
   mapping each word's `start_y` through the character AOIs, which share a
   `start_y` per line. Every table is read with `keep_default_na=False` and an
   explicit NA list, because PoTeC text `p3` contains the German word "null".
5. **Build the fixation table — `_potec_fixations`.** Concatenates the matching
   per-trial TSVs, and merges each fixation's `aoi` against the character-box
   centres to synthesize `x`/`y` — this is the step that gives PoTeC
   within-word landing positions at all.
6. **Expose it raw — `potec_raw_frames(root, *, readers, texts, download)`.**
   Downloads if asked, rejects unknown text ids with a `ValueError` naming the
   valid ones, returns `(words, fixations)` unnormalized.
7. **Expose it normalized —
   [`load_potec`][scanpath_studio.datasets.load_potec].** Calls
   `api.load_scanpath_data` with `POTEC_WORD_SCHEMA` / `POTEC_FIX_SCHEMA`. The
   stimulus-level word boxes get broadcast across readers here, so a trial that
   started as one row per word per *text* ends up as one row per word per
   *(reader, text)*.
8. **Wire the app — `_load_potec_source`** (`app.py`): a `_dataset_dir_input`
   with `_POTEC_STRUCTURE_MD`, a `_dataset_access_status` with
   `download=datasets.download_potec` and `size_hint="~45 MB"`, then
   `_cached_potec_raw_frames(root)`. One `PUBLIC_DATASET_REGISTRY` entry names
   it, gives its DELL P2210 monitor `(1680, 1050)`, and links the GitHub repo.
9. **Wire the other surfaces.** `--potec DIR` in `cli.py`; `load_potec` in
   `__all__` / `_DATASET_EXPORTS` in `__init__.py` and autodoc'd in
   [`docs/api.md`](api.md).
10. **Test it.** `tests/test_dataset_support.py` builds a two-word, two-reader
    PoTeC tree in `tmp_path` (including the literal word "null", to guard the
    NA handling) and asserts the broadcast word table, the reconstructed
    coordinates, the reader subset, and both error messages.

## Submitting it

One pull request containing all of it: the adapter in `datasets.py`, any
optional-field rows in `data.py`, the sidebar loader plus registry entry in
`app.py`, the default directory in `constants.py`, the CLI flag, the API
re-export, the tests, and a docs page under **Datasets** (plus its `mkdocs.yml`
nav line). In the PR description, state the corpus' **licence**, a
**citation**, its **public URL**, and its **on-disk size** (which determines
download-on-demand vs. local directory).

Before you open it:

```bash
pip install -e ".[test,docs]"
pytest
ruff check --exclude other_vis .
ruff format --exclude other_vis .
mkdocs build --strict          # if you added or edited a docs page
```

Add a line under `[Unreleased]` in `CHANGELOG.md`, and see
[Contributing](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md)
for the rest of the development setup.

If you're not sure whether your corpus is a good fit, open an
[issue](https://github.com/lacclab/scanpath-studio/issues) describing its shape
first — the answer is usually either "the generic loader already handles this"
or a short list of the specific things an adapter would have to reconstruct.
