# Contributing a dataset

How to get a public corpus shipped with Scanpath Studio, so every user finds it
in the data-source picker. Three exist today — OneStop, PoTeC and MultiplEYE —
and this page is the contract for adding a fourth.

!!! tip "You probably don't need this page"
    To load a corpus **you already have**, no code is needed at all — see
    [Bring your own data](bring-your-own-data.md). This page is only for making a
    corpus appear as a built-in source for everyone.

## Do you need an adapter?

If your corpus is two tables with recognisable column names, **no**. The generic
loader already takes a list or glob of files and auto-detects EyeLink, Gazepoint
and snake_case columns.

Adapters exist for what the generic path *can't* guess. That's what the three
existing ones are for:

| Corpus | The problem it solves |
| --- | --- |
| **OneStop** | Picking the right regime × part files out of the OSF release, and keeping the parts of one trial from colliding. The columns themselves are already fine. |
| **PoTeC** | 900 per-trial files to concatenate; word AOIs with no participant column; and fixations with **no coordinates at all** — x/y has to be reconstructed from which character was fixated. |
| **MultiplEYE** | Participant, session, trial and stimulus exist only in folder and file names; AOIs are per-character and must be combined into words; each page of a stimulus reuses the same screen coordinates, so each page has to become its own trial. |

If none of that sounds like your corpus, open an
[issue](https://github.com/lacclab/scanpath-studio/issues) describing its shape
before writing code — the answer is often "the generic loader already handles
this".

## Where the data lives

Nothing corpus-scale goes into the installed package: it's ~1.3 MB of Python plus
4.4 MB of demo data, and that's the whole budget. So in practice a new corpus is
either **downloaded on demand** into a folder the user picks (PoTeC, OneStop) or
**read from a directory the user already has** (MultiplEYE). Both look identical
from the user's side — one picker entry, one `load_*` function.

## What an adapter provides

All of this goes in
[`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py),
which is pandas plus the standard library and imports **no Streamlit** — it has to
work from a plain script.

**1. A raw-frames function** — the required entry point.

```python
def <corpus>_raw_frames(root, *, download=False, ...) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) (words, fixations) frames."""
```

It returns the two tables **before** normalization, in the corpus' own column
names. That's deliberate: the app runs them through the same auto-detect →
normalize pipeline as an upload, so the sidebar **Column mapping** panels still
appear and stay editable. Read the whole corpus (the global trial filters do the
narrowing), and never write anything — that's the downloader's job.

When something's missing, raise `FileNotFoundError` with a message that says what
to do. The app prints it verbatim in the sidebar, so your message *is* the error UI.

**2. A normalized loader** — `load_<corpus>(root, ...)`, which calls
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] with your raw
frames. Pass explicit schema dicts when the corpus' column names are stable;
omit them to let auto-detection run.

??? note "Schema dicts, and why auto-detection still has to work"
    PoTeC's are the model — note `participant=None`, which is what marks the
    word table as one shared layout rather than one row per reader:

    ```python
    POTEC_WORD_SCHEMA = dict(
        participant=None, trial="text_id", word_id="aoi", text="word",
        line="line", left="start_x", right="end_x",
        top="start_y", bottom="end_y",
    )
    ```

    Your dicts bind the **headless** loader only. The app never sees them — it
    takes the raw frames and runs auto-detection, exactly as for an upload. So
    detection has to land on the same answer, or your users open the corpus and
    have to fix the mapping by hand. Check it:

    ```python
    words, fixations = datasets.potec_raw_frames("data/PoTeC", texts=["b0"])
    assert data.validate_word_schema(data.propose_word_schema(words)) == []
    assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []
    ```

    If a column can't be guessed, add its name to the right `*_CANDIDATES` list
    in `data.py` rather than renaming it in your loader — that fixes it for
    every corpus using the same convention.

**3. Register any extra column you add.** Normalization builds a *fresh* frame and
silently drops anything it doesn't recognise. A corpus-specific extra — reader
metadata, a stimulus image path, a genre facet — needs a row in
`data.WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS`:

```python
("stimulus_font_px", "stimulus_font_px", "numeric", "meta"),
("comprehension_questions", "comprehension_questions", "passthrough", "meta"),
```

Skip this and your enrichment work vanishes between the loader and the first
plot, with no error.

**4. A presence check** — `<corpus>_present(root)`, path stats only, no file
reads, so the app can show found/missing before any expensive load. Be **strict**:
a lenient check passes a partial tree and then crashes mid-load, whereas a strict
one lets the app offer the Download button that fixes it.

**5. A downloader**, if the data is publicly fetchable — `download_<corpus>(root)`.
Skip anything already present, fetch to `<name>.part` and rename into place (an
interrupted fetch must never look complete to the presence check), print the URL,
and fetch from the corpus' **own** host. Scanpath Studio never mirrors anyone's
data.

**6. The presentation monitor** as a constant — `POTEC_MONITOR = (1680, 1050)`.
It's what makes the plot true-to-scale.

## Wiring it into the app

Two additions to `app.py`: a loader `_load_<corpus>_source(...)` that renders the
corpus' controls and returns raw frames, and one entry in
`PUBLIC_DATASET_REGISTRY` — the literal home of the corpora that are fixed at
import time:

```python
"PoTeC — Potsdam Textbook Corpus": dict(
    loader=_load_potec_source,
    monitor=(1680, 1050),          # DELL P2210 — the canvas snaps to this
    short="PoTeC",                 # what the picker shows
    language="German",
    size="75 readers · 12 texts",
    description="German reading of biology & physics textbook passages "
    "(expert/novice readers).",
    link="https://github.com/DiLi-Lab/PoTeC",
),
```

Each entry is **one top-level source in the picker**, tagged 🌐 and searchable
beside the demo and the uploads — there is no category to nest under and no
sub-picker inside an entry. A corpus that ships in several variants gets several
entries, told apart by the property that actually differs.

**Read the registry through `public_dataset_registry()`, never the dict.** That
function is what every consumer calls: it returns the static entries above
*plus* one entry per corpus discovered at runtime (each prepared corpus in a
local benchmark bundle is composed in there, since it depends on a directory the
user can change mid-session). The dict answers for the fixed corpora only, so a
consumer reading it directly silently ignores everything discovered — the reason
to touch `PUBLIC_DATASET_REGISTRY` by name is to *add* an entry to it, as above.
A corpus discovered from a manifest declares `monitor` only when the manifest
records a real one; an invented default must not snap the canvas, and
`eyegenbench.declared_monitor(entry)` is the single rule the app and the CLI both
apply.

Use the shared helpers in the loader so every corpus looks the same:
`_dataset_dir_input` (the directory box, folder-picker button, and *Expected
files* tree — write yours as a `_<CORPUS>_STRUCTURE_MD` constant) and
`_dataset_access_status` (found-vs-missing plus the ⬇ Download button). Wrap the
actual read in a module-level `@st.cache_data` function keyed on plain strings,
and when the data isn't there, `return load_sample_data()` — the app has to stay
usable. Put the default directory in `constants.py` as `<CORPUS>_DEFAULT_DIR`.

## The other three surfaces

A dataset is a user-facing feature, so the project's *expose it everywhere* rule
applies — the picker entry is one surface out of four:

- **Headless API** — `load_<corpus>` plus a lazy re-export in `__init__.py`
  (`__all__` and `_DATASET_EXPORTS`), and a `:::` autodoc block in
  [`docs/api.md`](api.md).
- **CLI** — a `--<corpus> DIR` flag in `render`'s input group, added to the
  exactly-one-input check so it can't be combined with `--sample`.
- **Deep link / Share** — register the source in `_SHAREABLE_SOURCES` and any
  per-corpus options in `_apply_url_preset` / `_build_share_query`. Only OneStop
  does this today. Skipping it works, but a shared link can't reopen your corpus.

Then add a docs page under **Datasets** describing the corpus and the modelling
decisions your adapter makes ([OneStop](onestop.md) and
[MultiplEYE](multipleye.md) are the templates), and list it in `mkdocs.yml`'s
`nav:` — a page that isn't in the nav still builds, but nothing links to it.

## Licensing

The corpus must be publicly available under a licence that permits what the
adapter does: reading it, and — for a downloader — fetching it from its own host
on the user's behalf.

- **No corpus data is vendored into this repository.** The one exception is the
  bundled demo, a subset of OneStop under OneStop's own licence, cited in the
  README and written into every export bundle so the attribution travels with the
  data.
- **Downloads point at the corpus' own host**, reusing the file IDs those projects
  publish.
- **Ported code is separate.** If your adapter ports logic from the corpus'
  tooling, add a `NOTICE` entry and check the licence is compatible with MIT — a
  GPL dependency isn't acceptable, which is why the drift-correction algorithms in
  `alignment.py` are a native port rather than a dependency.

## Tests

Cover the loader against a tiny corpus-shaped tree built in `tmp_path` (see the
`potec_root` / `multipleye_root` fixtures in `tests/test_dataset_support.py`),
asserting the normalized output exactly — IDs, word text, reconstructed
coordinates, durations — plus the failure paths: an unknown text ID raises
`ValueError`, a missing file raises a `FileNotFoundError` whose message tells the
user what to do, and `<corpus>_present` returns `False` on a partial tree.

`tests/test_apptest.py` already loops over the whole registry and checks each
loader boots the app cleanly, so your entry is picked up automatically — **but add
your `<CORPUS>_DEFAULT_DIR` to the tuple of constants it monkeypatches to an empty
`tmp_path`**. Without that the test reads your real data directory, so it passes
or fails depending on what the dev machine happens to have downloaded.

If your adapter merges side data (reader metadata, comprehension questions,
images), add one test per surface including the "file absent → column simply isn't
there" case; `tests/test_multipleye_enrichment.py` is the model.

Two hard rules: **tests never hit the network** (monkeypatch the downloader or
build the tree directly), and **expectations are hand-computed**, not snapshots of
whatever the code emitted.

## Reading PoTeC as a worked example

PoTeC is the smallest complete adapter. In `datasets.py`, read it in this order:
`download_potec` (fetch) → `potec_present` (check) → `_potec_words` (recovers
`text_id` from the filename and `line` by mapping word positions through the
character AOIs) → `_potec_fixations` (concatenates the per-trial files and
synthesizes x/y from character-box centres — the step that gives PoTeC landing
positions at all) → `potec_raw_frames` → `load_potec`. Then `_load_potec_source`
in `app.py`, and the test tree in `tests/test_dataset_support.py`.

## Submitting it

One pull request with all of it: the adapter, any optional-field rows in
`data.py`, the sidebar loader and registry entry, the default directory, the CLI
flag, the API re-export, the tests, and a docs page plus its nav line. In the PR
description state the corpus' **licence**, a **citation**, its **public URL**, and
its **on-disk size**.

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
