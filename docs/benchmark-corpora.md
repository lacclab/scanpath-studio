# Harmonised benchmark corpora

Thirty public eye-tracking-while-reading corpora, re-derived into one common
schema by the [EyeGenBench](https://github.com/EyeBench/EyeGenBench) pipeline,
prepared into a local bundle and offered in Scanpath Studio. They are what makes
cross-corpus comparison practical: the same columns, the same trial model and the
same reading measures across German textbook passages, Chinese newspaper
sentences, Persian narratives and English benchmark suites.

**Each prepared corpus is its own top-level data source.** There is no
"EyeGenBench" source to pick first and no corpus sub-picker inside one — a
prepared corpus sits in the flat picker tagged 🌐, searchable beside the bundled
demo and this app's own public corpora. EyeGenBench is *provenance and tooling*:
it names the pipeline that harmonised the data, the prep script, and the CLI
flag, and it appears in a corpus's description — never as the name of something
you select.

There is **no download** for the bundle. You build it locally (see
[Preparing a bundle](#preparing-a-bundle)), which is also what makes the geometry
recovery below possible: it reads the raw files the pipeline downloaded.

## Using a corpus

1. Open 🗂️ **Data → Data source** and pick a corpus. Each prepared corpus is one
   🌐 entry under its own name (*Provo*, *ZuCo1*, …).
2. Set **Data directory** to your bundle (default `data/EyeGenBench`). One
   directory serves every corpus, so pointing any entry somewhere else moves them
   all. The *Expected files* panel shows the layout it looks for:

    ```text
    <dir>/
    ├─ manifest.json              # one entry per prepared corpus
    └─ <corpus name>/             # e.g. PoTeC, Provo, …
       ├─ words.parquet
       ├─ fixations.parquet
       └─ participants.parquet
    ```

3. The whole corpus loads. Use **Narrow by** and the **More** filters to scope it
   — several of these corpora are large (ChineseReading is 1,718 readers).

A caption under the picker states the corpus's geometry provenance, and the
description carries its licence and citation. If the bundle isn't where you
pointed, the app says so and keeps the bundled demo loaded rather than failing.

With **no** corpora discovered the picker offers a single entry,
*Harmonised benchmark corpora — set up a local bundle*, which exists only to
carry the directory input; it disappears as soon as a bundle is found. As with
every public corpus, `SCANPATH_PUBLIC_DATASETS=0` hides them all.

Two corpora ship **both** natively and harmonised — PoTeC and OneStop — and both
entries are kept on purpose. The harmonised copy is labelled
*(harmonised benchmark)* in the picker. They are not interchangeable: the
harmonised OneStop, for instance, has no documented screen in the benchmark's
metadata and lays its text out on defaults, while this app's own OneStop entry
declares the corpus's 2560×1440 presentation monitor. Pick the publisher's
release to study that corpus; pick the harmonised one to compare it with the
other 29.

## The catalogue

Thirty corpora, ~13.9 million fixations, 21,894 distinct texts. This table is
generated from `data/EyeGenBench/manifest.json`, which is the authoritative
record of what a bundle holds; your own bundle's manifest is the authority for
your machine. Languages are the ISO codes the manifest records — the picker
renders them as names (`de` → German).

| Corpus | Language(s) | Readers | Texts | Fixations | Geometry | Declared screen |
| --- | --- | ---: | ---: | ---: | --- | --- |
| ADEGBTS | `zh` | 50 | 100 | 1,070,289 | synthesized | — |
| BSC | `zh` | 60 | 150 | 92,701 | reconstructed | 1024×768 |
| BSCII | `zh` | 70 | 150 | 82,738 | synthesized | — |
| ChineseReading | `zh` | 1,718 | 8,982 | 1,334,563 | reconstructed | 1024×768 |
| CoLAGaze | `en` | 36 | 306 | 9,552 | reconstructed | 1280×1024 |
| CopCo | `da` | 57 | 452 | 359,788 | reconstructed | 1920×1080 |
| Cuentos | `es` | 113 | 31 | 233,738 | reconstructed | 1920×1080 |
| EMTeC | `en` | 107 | 588 | 413,885 | reconstructed | 1280×1024 |
| EyeVoiceSpan | `de` | 63 | 144 | 108,971 | reconstructed | 1280×960 |
| GGTG | `en` | 23 | 80 | 46,429 | reconstructed | 1100×900 |
| Gaze4Hate | `de` | 43 | 90 | 46,102 | reconstructed | 2560×1440 |
| IITBHGC | `en` | 5 | 500 | 155,327 | reconstructed | 1920×1080 |
| InteRead | `en` | 50 | 28 | 235,097 | reconstructed | 1920×1080 |
| MECOL1W1 | `de, el, en, es, fi, he, it, ko, nl, no, ru, tr` | 528 | 144 | 1,087,905 | synthesized | — |
| MECOL1W2 | `da, de, en, es, eu, hi, is, no, pt, ru, sr, tr` | 577 | 144 | 1,782,491 | synthesized | — |
| MECOL2W1 | `en` | 542 | 12 | 1,221,387 | synthesized | — |
| MECOL2W2 | `en` | 659 | 12 | 1,406,213 | reconstructed | 1920×1080 |
| OASSTETC | `en` | 24 | 656 | 51,841 | synthesized | — |
| OneStop | `en` | 360 | 345 | 2,259,082 | synthesized | — |
| PSC2 | `de` | 149 | 144 | 71,830 | synthesized | — |
| PSR | `fa` | 60 | 99 | 107,821 | reconstructed | 1024×768 |
| PoTeC | `de` | 75 | 12 | 404,420 | **real** | 1680×1050 |
| Provo | `en` | 84 | 55 | 219,556 | reconstructed | 1600×900 |
| RSC | `ru` | 114 | 144 | 171,535 | synthesized | — |
| RaCCooNS | `nl` | 37 | 6,506 | 108,933 | reconstructed | 1920×1080 |
| ReadingBrain | `en` | 52 | 148 | 94,839 | synthesized | — |
| ReadingBrainL2 | `en` | 56 | 148 | 126,743 | synthesized | — |
| SBSAT | `en` | 49 | 22 | 121,025 | reconstructed | 1024×768 |
| ZuCo1 | `en` | 12 | 1,039 | 266,193 | reconstructed | 1920×1080 |
| ZuCo2 | `en` | 18 | 663 | 247,394 | reconstructed | 1920×1080 |

Six carry an explicit CC-BY-4.0 licence (CopCo, OneStop, PoTeC, Provo, ZuCo1,
ZuCo2). The other 24 read *unknown — consult the corpus*: the bundle does not
guess a licence it cannot verify, and neither should you. Three carry repeated
readings of the same text by the same reader (OneStop, ZuCo1, ZuCo2); each
reading gets its own trial rather than being merged into one scanpath.

### What is not in the bundle

The pipeline exposes **39** loadable corpora (a 40th, `gazebasereading`, is an
unimplemented stub upstream). Thirty prepare and ship. The remaining nine are two
distinct situations, neither of them "broken":

**Seven need manual acquisition** — EyeGenBench declares no automatic download
for them, because the publisher gates access:

`celer` · `cfiltcoreference` · `cfiltessaygrading` · `cfiltsarcasm` ·
`cfiltscanpath` · `cfiltsentiment` · `vqamhug`

Request the data from its publisher, then place the files where the pipeline
expects them and rerun the prep script for that corpus. The script's own
`[skip] <corpus>: …` line names the exact path it looked for, which is the fastest
way to find out where that is.

**Two were only blocked on disk space** — `uclcorpus` and `etdd70`. Nothing is
wrong with either; the sweep stopped on its own free-space guard
(`Only 3.7 GB free; need 15 GB`) before reaching them. Free some space and rerun,
and they prepare with no code change.

## Where the word boxes come from

EyeGenBench harmonises the *data* but discards screen geometry, so Scanpath
Studio recovers it during preparation. Recovery has four tiers, first hit wins:

1. **Measured boxes carried on the corpus's own text table** — some corpora
   (verified: PoTeC) ship EyeLink's coordinates there directly.
2. **Measured boxes parsed out of the raw EyeLink export** the pipeline
   downloaded (`CURRENT_FIX_INTEREST_AREA_DATA`). This is why the raw downloads
   are kept.
3. **A layout reconstructed from the corpus's published display parameters** —
   screen size, font size, character width, line pitch and margin, taken from
   what the corpus documents.
4. **A synthesized layout on generic defaults**, when nothing is published.

The first two collapse into `geometry_source: real` in the manifest, the third
into `reconstructed`, the fourth into `synthesized`. Today's catalogue: **1 real**
(PoTeC), **18 reconstructed**, **11 synthesized**.

Real boxes only exist for interest areas somebody actually fixated, so gaps
inside an otherwise-measured paragraph are interpolated from their neighbours and
the fraction is reported (`interpolated_fraction`; 0.16% on PoTeC, zero
everywhere else).

Two consequences worth understanding before you publish a figure:

**The corpus-level tier is the best tier *any* paragraph reached.** It is stamped
per paragraph and summarised per corpus, so a corpus labelled `real` may hold
paragraphs that fell back to a reconstructed layout — a paragraph nobody fixated
at all contributes no measured box. The app therefore never prints a bare
"✅ Real" when coverage is partial; it prints *measured word boxes for N of M
texts; the rest fall back to reconstructed layout*. The distinction matters: on
measured geometry you can trust absolute positions (where on the screen a reader
looked, how far a saccade travelled in pixels); on a reconstructed or synthesized
layout you can trust reading order and relative structure, but the coordinates
are a plausible rendering of the text, not the one the reader saw. PoTeC is
uniformly measured (no text falls back), so the qualifier does not currently fire
for any corpus in the catalogue.

**A corpus with no documented screen declares no monitor at all.** Eleven of the
thirty document no display, and the fallback layout is drawn on a generic
1920×1080 — an invented number. Declaring it as the corpus's screen would present
a made-up geometry as a measurement, so the app declines: those entries carry no
monitor, and the canvas falls back to the data's own extents. `eyegenbench.declared_monitor`
is the single implementation of that rule, read by **both** the app and
`render --eyegenbench`, so a corpus renders at the same scale whichever surface
you ask. `geometry_source` and `monitor_source` move together across all 30 rows:
a corpus with a documented screen is the same corpus whose layout could be
reconstructed from it.

## Preparing a bundle

The prep script runs EyeGenBench's own pipeline unmodified, then — while the raw
downloads are still on disk — recovers geometry and writes the app-native bundle.
It needs EyeGenBench installed, which is why it runs in a **separate virtualenv**:

```bash
git clone https://github.com/EyeBench/EyeGenBench   # somewhere alongside this repo
python -m venv .venv-eyegenbench
.venv-eyegenbench/bin/pip install -e ../../EyeGenBench/code

# every corpus, into data/EyeGenBench/
.venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --all

# or just the ones you want
.venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py \
    --dataset potec --dataset provo
```

`--eyegenbench-root` points at the EyeGenBench checkout (default
`../../EyeGenBench/code`) and `--out` at the bundle directory (default
`data/EyeGenBench`).

Two things that surprise people:

- **The raw downloads are kept, never deleted.** That is deliberate — tier 2 of
  the geometry recovery reads them, so a run that cleaned up after itself would
  throw away the measured boxes. They stay in the EyeGenBench checkout's `data/`
  directory.
- **The corpus set is large, and the script guards on free space.** Before each
  corpus it checks for 15 GB free and stops the whole sweep if there is less,
  rather than filling the disk. Rerunning after freeing space picks up where it
  left off: each corpus's manifest entry is written as soon as its three Parquet
  files are on disk, so an interrupted run leaves a valid, smaller bundle.

One corpus at a time is prepared and recorded, and a corpus that fails is skipped
with its reason printed rather than taking the sweep down.

## The other surfaces

**Deep link / Share.** A share link names the corpus, never its data:
`?source=corpus&corpus=<slug>`. This one token covers every public corpus —
built-in and prepared alike. The slug comes from the entry's stable identifier,
not its display label: a prepared corpus is `harmonised-` plus its manifest name
lowercased (`harmonised-provo`, `harmonised-potec`), a built-in is its short name
(`potec`, `onestop`). The prefix is what keeps the two PoTeCs and the two
OneStops apart. If two entries would ever claim one slug, the link scheme
**refuses** it on both sides rather than guessing which corpus you meant.

A recipient without that corpus prepared is the common case, not an edge case:
the link says which corpus it names, tells them how to point at a bundle, and
leaves their data source exactly where it was. The bundle *directory* never
travels on the link — it is a local path, and it is the sender's.

**CLI.**

```bash
scanpath-studio render --eyegenbench data/EyeGenBench --eyegenbench-dataset Provo \
    --list-trials

scanpath-studio render --eyegenbench data/EyeGenBench --eyegenbench-dataset PoTeC \
    -p PoTeC_0 -t PoTeC_b0 -o potec.png
```

`--eyegenbench-dataset` is required alongside `--eyegenbench` and names the
corpus as the manifest spells it (`PoTeC`, `Provo`, `ZuCo1`; matching is
case-insensitive). The canvas resolves through the same `declared_monitor` rule
as the app, so it falls back to data extents for a corpus with no documented
screen instead of an invented 1920×1080. See the [CLI reference](cli.md).

**Python API.**

```python
import scanpath_studio as sps
from scanpath_studio.eyegenbench import eyegenbench_datasets

for entry in eyegenbench_datasets("data/EyeGenBench"):
    print(entry["name"], entry["geometry_source"], entry["n_fixations"])

words, fixations = sps.load_eyegenbench("data/EyeGenBench", dataset="Provo")
```

`load_eyegenbench` returns normalized `(words, fixations)` frames — the same
pipeline the app uses — so everything in the [Python API](api.md) applies
unchanged. Per-reader metadata is a separate table
(`eyegenbench.load_eyegenbench_participants`), never broadcast onto the word or
fixation rows.

## Caveats

- **Check the geometry tier before you make a claim about positions.** Most of
  the catalogue is reconstructed or synthesized. Reading order, fixation
  durations and word-level measures are the corpus's own data; pixel coordinates
  on a non-`real` corpus are a rendering.
- **Licences are mostly unstated.** Twenty-four corpora record
  *unknown — consult the corpus*. Check the publisher's terms before
  redistributing data or figures.
- **Word boxes are laid out monospaced** on most reconstructed and synthesized
  corpora, because that is what the published display parameters describe. Four
  (GGTG, IITBHGC, ZuCo1, ZuCo2) are proportional. The flag is not recorded for a
  corpus with real geometry, where it would describe a layout that was never
  built.
- **A prepared corpus is not a substitute for the publisher's release.** It is a
  re-derivation, harmonised for comparison. Cite the original corpus, using the
  citation the manifest carries where it has one.
