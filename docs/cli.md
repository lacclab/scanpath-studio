# CLI reference

`scanpath-studio` launches the app by default. Its `render` subcommand writes
one trial without opening the UI.

## Launch

```bash
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
```

The app listens on this computer only (`127.0.0.1`). It has no login, so
serving it to other machines is a deliberate step — pass
`--server.address 0.0.0.0` (or set `server.address` in a Streamlit
`config.toml`, or `STREAMLIT_SERVER_ADDRESS`), and only on a network you trust:

```bash
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app also turns off everything that reads or writes the
server's own folders — the data-location box, the 📁 folder picker, ⬇ Download
for the public corpora and stimulus-image folders — since any visitor could use
them. On a lab server you trust, turn them back on with `SCANPATH_LOCAL_FS=1`
(`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

Additional launch flags are forwarded to Streamlit. A word that is not one of
the commands (`run`, `render`, `analyze`, `corpus`, `cache`) is an error that
names the closest one, rather than an argument handed to Streamlit.

## Render

```bash
# Inspect available IDs
scanpath-studio render --sample --list-trials

# Render the bundled sample
scanpath-studio render --sample -o scanpath.html

# Render your data
scanpath-studio render \
  --words ia.csv --fixations fixations.csv \
  --participant p1 --trial t3 --output scanpath.svg

# Render a portable file saved by the in-app scanpath author
scanpath-studio render --authoring authored-scanpath.json -o authored.html

# Inspect and render an ordered multipart trial
scanpath-studio render --words ia.csv --fixations fix.csv --list-parts
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --screen question -o question.svg
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --all-screens --animate --screen-transition recorded \
  -o replay.html
```

HTML is interactive and browser-free. PNG, SVG, and PDF require
Chrome/Chromium (`plotly_get_chrome -y`).

### When a column isn't recognised

Column names are auto-detected (EyeLink, Tobii, SMI, Pupil Labs, Gazepoint and
snake_case spellings). When one isn't, `render` stops and prints which field it
could not find, the names it looked for, the columns your table has, and a
mapping to start from. Pass that mapping back as JSON — inline, or as a path to
a `.json` file — with `--word-schema` (the `--words` table) and/or
`--fix-schema` (the `--fixations` table). `analyze` takes the same two flags.

```bash
scanpath-studio render --words ia.csv --fixations fix.csv \
  --word-schema '{"trial": "TRIAL_LABEL", "word_id": "IA_ID", "text": "IA_LABEL",
                  "left": "IA_LEFT", "right": "IA_RIGHT", "top": "IA_TOP", "bottom": "IA_BOTTOM"}' \
  --fix-schema fix_schema.json -o scanpath.html
```

A mapping replaces auto-detection for that table, so it has to name every
required field, not only the one that failed. It is the same dict
`load_scanpath_data(word_schema=…, fix_schema=…)` takes in Python.

## Public corpora

A public corpus loads headlessly the same way the app loads it — no export step
in between:

```bash
# PoTeC, downloaded on first use
scanpath-studio render --potec ./potec --list-trials

# OneStop, choosing the variant, regime and part
scanpath-studio render --onestop ./onestop --onestop-variant public \
  --onestop-regime ordinary --onestop-part Paragraph --list-trials
```

The Python API takes the same corpora through `load_potec` and
`load_onestop`.

## Compare two scanpaths

`--compare-with PARTICIPANT:TRIAL` draws a second reading beside or over the
first — the headless form of the app's **Compare** mode.

```bash
# Two readers of the same paragraph, overlaid
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 -o compare.html

# The same overlay, drawing only B's word boxes and text
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --compare-stimulus b \
  -o compare_b.html

# Side by side — each panel draws its own reading's stimulus
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 \
  --compare-layout side-by-side -o compare.svg

# B from a second dataset
scanpath-studio render --words ia.csv --fixations fix.csv -p p1 -t t1 \
  --compare-with p1:t1 \
  --compare-words other/ia.csv --compare-fixations other/fix.csv \
  --compare-dataset-name "Our lab" \
  --canvas 1680x1050 --compare-canvas 1680x1050 \
  -o cross.html
```

| Goal | Option |
| --- | --- |
| pick B | `--compare-with PARTICIPANT:TRIAL` |
| arrange the panels | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`) |
| whose stimulus an overlay draws | `--compare-stimulus {both,a,b}` (default `both`) |
| name the two traces | `--label-a TEXT --label-b TEXT` (both or neither) |
| style each scanpath | `--style-a SPEC`, `--style-b SPEC` (below) |
| the A/B legend | `--compare-legend` |
| B's own stimulus page (split layouts) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y` |
| B from another dataset | `--compare-words PATH… --compare-fixations PATH…` |
| name that dataset | `--compare-dataset-name NAME` |
| declare the screens | `--canvas WxH`, `--compare-canvas WxH` |
| co-animate both readings | add `--animate` (HTML output) |

`--label-a` / `--label-b` also label the `--animate` co-animation.

`--style-a` / `--style-b` are the app's per-scanpath styling (the Compare rows
under 👁️ Fixations and ↗️ Saccades), `compare_scanpaths`'s `style_a` / `style_b`:
a comma-separated `KEY=VALUE` list, repeatable, with `fix_color` and
`saccade_color` (`#RRGGBB`), `saccade_style` (`solid`, `dash`, `dot`,
`dashdot`), `saccade_width` (px), `marker_size_range` (`MIN:MAX`), `opacity`
(0.1–1) and `hollow` (`true` / `false`). A key left out keeps that scanpath's
default.

```bash
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --compare-legend \
  --style-a fix_color=#D55E00,opacity=0.5 --style-b saccade_style=dash \
  -o compare_styled.html
```

`--animate --compare-with` replays **both** readings on one clock, the same dual
co-animation the app renders with Animate and Compare both on.
`--compare-with` cannot be combined with `--all-screens`: a comparison
is a single figure of two readings, so render one screen at a time with
`--screen`.

**Overlay across two datasets requires matching canvases.** On two different
canvases `--compare-layout overlay` fails rather than falling back, and so does
`--animate`, which replays both readings in one coordinate space; pass
`--compare-layout side-by-side` or `stacked`, without `--animate`. Without
`--compare-canvas` the second dataset's screen is read off its data, as A's is
when neither `--canvas` nor a built-in source gives one. That extent rarely
spans the whole screen, so state both screens when you know them. Nothing is
rescaled.

A second dataset is loaded from **files only**. Any corpus reachable from Python
can still be scanpath B via
[`compare_scanpaths`](api.md#scanpath_studio.api.compare_scanpaths), which takes
B's frames directly.

## Common options

| Goal | Option |
| --- | --- |
| hide a layer | `--no-words`, `--no-labels`, `--no-fixations`, `--no-order`, `--no-saccades`, `--no-heatmap` |
| animate | `--animate` and optionally `--playback-speed X`; every styling flag the replay can draw (`api.figure_options("animation")`) is honoured, and the rest are named in a warning |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| color fixations | `--color-by FIELD` |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; honoured by `--animate` and `--compare-with` too) |
| add the stimulus image | `--stimulus-image PATH` |
| resolve per-trial images | `--image-root DIR --image-pattern '{text_id}.png'` |
| use Gaussian duration mass | `--heatmap-style duration-mass --duration-mass-sigma 1.0` |
| map arbitrary source rows to screens | `--trial-parts-manifest manifest.json` |
| export editable layers | `--separable-layers` |
| draw the raw gaze | `--raw-gaze PATH…` (or `--sample-raw-gaze` with `--sample`), `--raw-gaze-schema JSON`, `--raw-gaze-color`, `--raw-gaze-marker-size`, `--raw-gaze-opacity` |
| size the figure | `--width`, `--height`, `--scale` |
| title and caption it | `--title`, `--caption` |
| print the equivalent Python | `--print-code python` (or `cli` / `both`, plus `--print-code-explicit`) |

The [figure options table](api.md#figure-options) gives every figure option's
flag.

Raw gaze is a third table rather than an option: `--raw-gaze` reads it (columns
auto-detected like `--fixations`) and draws the plotted trial's samples under the
fixations. It is a single-trial layer, so `--animate` and `--compare-with`
ignore it with a warning.

```bash
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

## Analyze

The `analyze` command writes the full tabular family without opening the app:

```bash
scanpath-studio analyze --words ia.csv --fixations fixations.csv --output-dir analysis
```

This writes fixation, saccade, word, sentence, trial, reader, character and
cleaning-QA tables as CSV, plus `run_config.json`. It takes the same `--words` / `--fixations`
(several paths each), `--trial-parts-manifest`, `--word-schema` and
`--fix-schema` as `render`, plus the optional preprocessing stage
([`api.preprocess_data`](api.md#scanpath_studio.api.preprocess_data)), which is
off unless a flag below turns it on and never deletes a row — excluded fixations
keep `excluded` / `excluded_reason`:

```python exec="true"
from docs_support import cli_reference

print(cli_reference("analyze"))
```

The preprocessing settings and `--pixels-per-degree` are recorded in
`run_config.json`.

## Corpus figures

`scanpath-studio corpus` goes the other way: it reads a tidy CSV you already
have and renders a styled corpus figure
([`api.plot_corpus_figure`](api.md#scanpath_studio.api.plot_corpus_figure)):

```bash
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("corpus"))
```

## Many trials

The `render` command renders one trial per invocation; use the [Python batch pattern](automation.md#batch-pattern)
or **Export → Export bundle** for many figures.

`--all-screens` is the multipart exception: it writes one deterministic
`__screen-001-<id>` file per screen of the selected parent trial.

## Recovery cache

A local or desktop run caches your session on your own machine — uploaded
datasets, column mappings, view settings, and annotations — so a refresh or a
restart resumes where you left off. `cache` shows what is stored and removes it:

```bash
scanpath-studio cache            # datasets, rows, size, folder, last written
scanpath-studio cache --path     # just the folder
scanpath-studio cache --json     # the same status as JSON
scanpath-studio cache --clear    # delete the stored session
```

The same information and controls are in **Session → Automatic recovery**;
**Clear recovery cache** removes the saved copy without closing the current
app. `SCANPATH_STUDIO_PERSIST=0` turns caching
off permanently, `--no-persist` for one launch, and `SCANPATH_STUDIO_STATE_DIR`
moves the folder. Hosted deployments never cache. See
[Privacy](privacy.md#what-happens-to-a-file-you-upload).

## Full reference

Generated from the parsers the commands themselves use, so every flag is here
with the default and help `--help` prints.

```python exec="true"
from docs_support import cli_help

print(cli_help())
```

??? note "`render` — every flag"

    ```python exec="true"
    from docs_support import cli_reference

    print(cli_reference("render"))
    ```

??? note "`cache` — every flag"

    ```python exec="true"
    from docs_support import cli_reference

    print(cli_reference("cache"))
    ```

`analyze` and `corpus` are listed in full in their own sections above.
