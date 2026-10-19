# Contributing a dataset

This page explains how to ship a public corpus with Scanpath Studio, so that
every user finds it in the dataset picker. Two corpora ship with the app,
OneStop and PoTeC. This page lists what a new one needs.

!!! tip "You probably don't need this page"
    To load a corpus **you already have**, you need no code. See
    [Data Management](guides/loading-data/index.md). This page is only for making a
    corpus appear as a built-in dataset for everyone.

## Do you need an adapter?

If your corpus is two tables with recognizable column names, **no**. The generic
loader already takes a list or glob of files and auto-detects EyeLink, Gazepoint,
Tobii, SMI, Pupil Labs and snake_case columns.

An adapter handles what the generic loader can't guess. The two existing
adapters solve these problems:

| Corpus | The problem it solves |
| --- | --- |
| **OneStop** | Picking the right regime × part files out of the OSF release, and keeping the parts of one trial from colliding. The columns themselves are already fine. |
| **PoTeC** | 900 per-trial files to concatenate, word boxes with no participant column, and fixations with **no coordinates**. Their x/y is reconstructed from the character each fixation landed on. |

If your corpus has none of these problems, open an
[issue](https://github.com/lacclab/scanpath-studio/issues) that describes its
shape before you write code. The generic loader often handles it already.

## Where the data lives

No corpus-sized data goes into the installed package. A new corpus is either
**downloaded on demand** into a folder the user picks (PoTeC, OneStop) or
**read from a folder the user already has**. Both look the same to the user:
one picker entry and one `load_*` function.

## What an adapter provides

All of this goes in
[`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py),
which imports **no Streamlit**, because it has to work from a plain script.

**1. A raw-frames function.** This is the required entry point.

```python
def <corpus>_raw_frames(root, *, download=False, ...) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) (words, fixations) frames."""
```

It returns the two tables **before** normalization, under the corpus' column
names. The app runs them through the same auto-detect and normalize pipeline as
an upload, so the column mapping under **Data Management** → **Edit dataset** →
**Data tables & column mapping** still appears and stays editable. Read the
whole corpus, since the trial filters do the narrowing. Never write anything:
writing is the downloader's job.

When something is missing, raise `FileNotFoundError` with a message that says
what to do. The app shows the message as written on the **Data Management**
page, so it is the error the user sees.

**2. A normalized loader**, `load_<corpus>(root, ...)`, which calls
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data] with your raw
frames. Pass explicit schema dicts when the corpus' column names are stable;
omit them to let auto-detection run.

??? note "Schema dicts, and why auto-detection still has to work"
    PoTeC's are the model. `participant=None` marks the Words table as one
    layout shared by every participant, with no participant column:

    ```python
    POTEC_WORD_SCHEMA = dict(
        participant=None,
        trial="text_id",
        text_id="text_id",
        word_id="aoi",
        text="word",
        line="line",
        left="start_x",
        right="end_x",
        top="start_y",
        bottom="end_y",
    )
    ```

    By default your dicts bind only the **headless** loader. The app takes the
    raw frames and runs auto-detection, as for an upload. Detection has to find
    the same mapping, or your users open the corpus and have to fix the mapping
    by hand. Check it:

    ```python
    words, fixations = datasets.potec_raw_frames("data/PoTeC", texts=["b0"])
    assert data.validate_word_schema(data.propose_word_schema(words)) == []
    assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []
    ```

    If a column can't be guessed, add its name to the right `*_CANDIDATES` list
    in `data.py` instead of renaming it in your loader. That fixes it for every
    corpus that uses the same convention.

    When the column names can't give the right mapping, give the app's registry
    entry `declared_schemas=(word_schema, fix_schema)`, and the app maps through
    your dicts instead. PoTeC does this. A trial is one participant's reading of
    a text, so its fixations' Trial ID is `["reader_id", "text_id"]`, where
    detection would pick the text alone.

**3. Register any extra column you add.** Normalization builds a new frame and
drops, without a warning, any column it doesn't recognize. A corpus-specific
column, such as participant metadata, a stimulus image path or a genre, needs a
row in `data.WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS`:

```python
WORD_OPTIONAL_FIELDS = [
    # ... the existing rows ...
    ("stimulus_font_px", "stimulus_font_px", "numeric", "meta"),
    ("comprehension_questions", "comprehension_questions", "passthrough", "meta"),
]
```

Without the row, the column is gone by the first plot, with no error.

**4. A presence check**, `<corpus>_present(root)`. It only checks that paths
exist and reads no files, so the app can show found or missing before any slow
load. Make it **strict**. A lenient check passes a partial tree that then fails
during the load. A strict one lets the app offer the Download button that fixes
it.

**5. A downloader**, `download_<corpus>(root)`, if the data can be downloaded
publicly. Skip files already present. Download to `<name>.part` and rename it
into place, so an interrupted download never passes the presence check. Print
the URL, and download from the corpus' **own** host. Scanpath Studio does not
mirror anyone's data.

**6. The presentation monitor** as a constant, such as
`POTEC_MONITOR = (1680, 1050)`. It makes the plot true to scale.

## Wiring it into the app

Two additions to `app.py`: a loader `_load_<corpus>_source(...)` that renders the
corpus' controls and returns raw frames, and one entry in
`PUBLIC_DATASET_REGISTRY`, the dict that holds the corpora fixed at import
time:

```python
"PoTeC — Potsdam Textbook Corpus": dict(
    loader=_load_potec_source,
    files_present=_potec_files_present,  # the dataset table's Status
    downloadable=True,             # missing files read "Needs download"
    declared_schemas=(POTEC_WORD_SCHEMA, POTEC_FIX_SCHEMA),
    monitor=(1680, 1050),          # DELL P2210: the recording screen
    short="PoTeC",                 # what the picker shows
    language="German",
    size="75 participants · 12 texts",
    description="Potsdam Textbook Corpus: German experts and novices "
    "reading biology and physics textbook passages.",
    link="https://github.com/DiLi-Lab/PoTeC",
    published_counts={             # the row before anyone opens it
        "Participants": 75,
        "Texts": 12,
        "Trials": 900,
        "Words": 142125,
        "Fixations": 404420,
    },
    published_counts_source=(
        "PoTeC's README for participants, texts and trials. Words and "
        "fixations were measured from the released corpus."
    ),
    reading_note="Fixation positions are reconstructed, not recorded: "
    "PoTeC's release keeps no screen coordinates, so each fixation is drawn "
    "at the center of the character it landed on.",
),
```

`files_present` wraps your `<corpus>_present` check, and `downloadable` says
whether the app can fetch what is missing (*Needs download*) or the user has to
supply it (*Needs setup*).

**`published_counts` describes the corpus as published.** In
`published_counts_source`, say which published document each count came from,
and say so when you measured one yourself. The dataset list shows these counts
until the dataset is opened. Then it shows what loaded and flags any count
where the load exceeds the published one. `reading_note` is the one sentence
about the data's origin shown with the dataset on the **Data Management** page.
Use it for anything that changes how a figure is read, such as reconstructed
positions or synthesized samples.

Each entry is **one dataset in the picker**, listed with Kind *Public* beside
the bundled demo and the user's own datasets. Entries don't nest, and an entry
has no picker of its own. A corpus that ships in several variants gets one
entry per variant, named by what differs between them, as OneStop's reading
regimes are.

**Read the registry through `public_dataset_registry()`, not the dict.** The
function returns the static entries above *and* any entry built at runtime.
The dict holds only the fixed corpora, so code that reads it directly misses
the rest. Name `PUBLIC_DATASET_REGISTRY` only to *add* an entry to it, as
above.

Use the shared helpers in the loader so every corpus looks the same:
`_dataset_dir_input` (the folder box, the folder-picker button, and the
*Expected files* tree, which you write as a `_<CORPUS>_STRUCTURE_MD` constant) and
`_dataset_access_status` (found or missing, and the ⬇ Download button). Wrap
the read in a module-level `@st.cache_data` function keyed on plain strings.
When the data isn't there, `return load_sample_data()`, so the app stays
usable. Put the default directory in `constants.py` as `<CORPUS>_DEFAULT_DIR`.

## The other three surfaces

A dataset is a user-facing feature, so the project's rule to expose a feature
on every surface applies. The picker entry is one of four:

- **Headless API**: `load_<corpus>` plus a lazy re-export in `__init__.py`
  (`__all__` and `_DATASET_EXPORTS`), and a `:::` autodoc block in
  [`docs/api.md`](api.md).
- **CLI**: a `--<corpus> DIR` flag in `render`'s input group, added to the
  check that allows one input only, so it can't be combined with `--sample`.
- **Deep link / Share**: this comes with the registry entry.
  `?source=corpus&corpus=<slug>` names any entry `public_dataset_registry()`
  returns, by a slug made from the entry's `short`. Check that your `short`
  gives a slug no other entry has. A slug that two entries share is dropped
  from both, so neither can be shared by link. Register the source in
  `_SHAREABLE_SOURCES` only if it needs its **own** token, and add any
  per-corpus options (OneStop's variant / regime / parts) to
  `_apply_url_preset` / `_build_share_query`.

Then describe the corpus, and the modeling decisions your adapter makes, in
the Data Management guide beside
[OneStop](guides/loading-data/index.md#onestop).

## Licensing

The corpus must be publicly available under a license that permits what the
adapter does: reading it and, for a downloader, downloading it from its own
host for the user.

- **No corpus data is vendored into this repository.** The one exception is the
  bundled demo, a subset of OneStop under OneStop's own license, cited in the
  README and written into every bundle exported from it, so the attribution
  travels with the data.
- **Downloads point at the corpus' own host**, using the file IDs those
  projects publish.
- **Ported code is separate.** If your adapter ports logic from the corpus'
  tooling, add a `NOTICE` entry and check that the license is compatible with
  MIT. A GPL dependency isn't acceptable.

## Tests

Cover the loader against a tiny corpus-shaped tree built in `tmp_path` (see the
`potec_root` fixture in `tests/test_dataset_support.py`),
and assert the normalized output: IDs, word text, reconstructed coordinates
and durations. Also test the failure paths: an unknown text ID raises
`ValueError`, a missing file raises a `FileNotFoundError` whose message tells the
user what to do, and `<corpus>_present` returns `False` on a partial tree.

`tests/test_apptest.py` loops over the whole registry and checks that each
loader boots the app cleanly, so it picks up your entry. **Add your
`<CORPUS>_DEFAULT_DIR` to the tuple of constants it monkeypatches to an empty
`tmp_path`.** Without that, the test reads your real data directory, and its
result depends on what the machine has downloaded.

If your adapter merges side data (participant metadata, comprehension
questions, images), add one test per surface, including the case where the
file is absent and the column is missing.

Two rules hold for every test. **Tests never use the network**: monkeypatch
the downloader or build the tree directly. **Expected values are computed by
hand**, not copied from what the code printed.

## Reading PoTeC as a worked example

PoTeC is the smallest complete adapter. In `datasets.py`, read it in this order:
`download_potec` (download) → `potec_present` (check) → `_potec_words` (reads
`text_id` from the file name, and `line` by mapping word positions through the
character boxes) → `_potec_fixations` (concatenates the per-trial files and
places x/y at the character-box centers, which gives PoTeC its landing
positions) → `potec_raw_frames` → `load_potec`. Then `_load_potec_source`
in `app.py`, and the test tree in `tests/test_dataset_support.py`.

## Submitting it

Send one pull request with all of it: the adapter, any optional-field rows in
`data.py`, the loader and registry entry, the default directory, the CLI
flag, the API re-export, the tests, and the docs section. In the PR
description state the corpus' **license**, a **citation**, its **public URL**, and
its **on-disk size**.

Before you open it:

```bash
pip install -e ".[test,lint,docs]"
pytest
ruff check .
ruff format .
mkdocs build --strict          # if you edited the docs
```

Add a changelog entry as a file in `changelog.d/` (its README says how), and see
[Contributing](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md)
for the rest of the development setup.
