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
scanpath-studio render --potec ./potec -p 12 -t b0 -o potec.html

# OneStop, choosing the variant, regime and part
scanpath-studio render --onestop ./onestop --onestop-variant public \
  --onestop-regime ordinary --onestop-part Paragraph --list-trials

# One corpus out of a prepared harmonised bundle
scanpath-studio render --eyegenbench ./data/EyeGenBench \
  --eyegenbench-dataset Provo -p Provo_Sub01 -t Provo_1 -o provo.svg

# MultiplEYE, from its raw export
scanpath-studio render --source multipleye --export ./multipleye_session \
  --list-trials
```

`--eyegenbench-dataset` names one of the thirty-one
[harmonised benchmark corpora](benchmark-corpora.md) in a bundle you prepared
locally; `--no-question-screens` drops MultiplEYE's comprehension screens. The
Python API takes the same corpora through the loaders re-exported at the package
root (`load_potec`, `load_onestop`, `load_multipleye`, `load_eyegenbench`).

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
scanpath-studio render --potec ./potec -p 12 -t b0 \
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

`--label-a` / `--label-b` replace the composed trace labels — the CLI form of the
app's per-scanpath label pattern. They go together, because `compare_scanpaths`
takes the pair or neither, and they apply to the co-animation below just as they
do to the static comparison.

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

These, `--compare-legend` and the `--stimulus-image-b` trio describe the second
scanpath, so they are refused without `--compare-with`.

`--animate --compare-with` replays **both** readings on one clock, the same dual
co-animation the app renders with Animate and Compare both on. That is an
overlay, so it needs one shared screen on the same terms as `--compare-layout
overlay`. `--compare-with` cannot be combined with `--all-screens`: a comparison
is a single figure of two readings, so render one screen at a time with
`--screen`.

**Overlay across two datasets requires matching canvases.** On two different
canvases `--compare-layout overlay` fails rather than falling back; pass
`--compare-layout side-by-side` or `stacked`. Nothing is rescaled.

A second dataset is loaded from **files only**. Any corpus reachable from Python
can still be scanpath B via
[`compare_scanpaths`](api.md#scanpath_studio.api.compare_scanpaths), which takes
B's frames directly.

## Common options

| Goal | Option |
| --- | --- |
| hide a layer | `--no-words`, `--no-labels`, `--no-fixations`, `--no-saccades`, `--no-heatmap` |
| animate | `--animate` and optionally `--playback-speed X`; every styling flag the replay can draw (`api.figure_options("animation")`) is honoured, and the rest are named in a warning |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| show monitor-pixel axes | `--coordinate-grid` and optionally `--coordinate-grid-spacing PX` |
| color fixations | `--color-by FIELD` |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; honoured by `--animate` and `--compare-with` too) |
| mark the critical span | `--highlight-column COLUMN` (`''` for none) with `--critical-span-style mark-text|mark-border|none` |
| flag short / long / off-text / blink fixations | `--fixation-flag CATEGORY=MODE[,threshold_ms=N][,symbol=S][,color=#RRGGBB]`, repeatable |
| classify saccades | `--saccade-color-by-type` |
| correct vertical drift (needs `SCANPATH_EXPERIMENTAL=1`) | `--drift-correction ALGORITHM` |
| add the stimulus image | `--stimulus-image PATH` |
| resolve per-trial images | `--image-root DIR --image-pattern '{text_id}.png'` |
| use Gaussian duration mass | `--heatmap-style duration-mass --duration-mass-sigma 1.0` |
| mark a schematic | `--illustration` or `--illustration-label MODE` |
| render an authored trial | `--authoring PATH` |
| select or inspect a child screen | `--screen ID`, `--list-parts` |
| render every ordered screen | `--all-screens`, optionally `--screen-transition instant|recorded` |
| map arbitrary source rows to screens | `--trial-parts-manifest manifest.json` |
| attach participant metadata | `--participant-metadata readers.csv` |
| attach trial metadata | `--trial-metadata readings.csv`, `--trial-metadata-reader-column` to key it by reader **and** trial |
| export editable layers | `--separable-layers` |
| style the fixations | `--fixation-color`, `--fixation-symbol`, `--fixation-colorscale`, `--fixation-color-range LO HI`, `--fixation-opacity`, `--hollow-fixations`, `--marker-size-range`, `--color-by-line` |
| style the index labels | `--order-font-size`, `--order-font-color` |
| style the saccades | `--saccade-style`, `--saccade-width`, `--saccade-arcs`, `--saccade-arrows`, `--saccade-classes`, `--saccade-type-color` (also beside `--saccade-color-by-direction`, where it recolours that two-way split) |
| style the text and the page | `--text-color`, `--highlight-text-color`, `--span-border-color`, `--background-color`, `--line-spacing`, `--no-scale-text-to-boxes`, `--word-hover-measure` |
| draw the raw gaze | `--raw-gaze PATH…` (or `--sample-raw-gaze` with `--sample`), `--raw-gaze-schema JSON`, `--raw-gaze-color`, `--raw-gaze-marker-size`, `--raw-gaze-opacity` |
| frame on the data, not the monitor | `--no-full-monitor` |
| plot other fixation columns | `--x-field FIELD`, `--y-field FIELD` |
| show and style the colour bars | `--colorbars`, `--colorbar-orientation`, `--colorbar-tickangle`, `--colorbar-tickfont-size` |
| tint a words-only dataset by a column | `--word-heatmap-col COLUMN`, `--word-heatmap-title TEXT` |
| pick a palette | `--palette` |
| size the figure | `--width`, `--height`, `--scale` |
| title and caption it | `--title`, `--caption` |
| tune the heatmap | `--heatmap-metric`, `--heatmap-colorscale`, `--heatmap-norm`, `--heatmap-range LO HI` |
| print the equivalent Python | `--print-code python` (or `cli` / `both`, plus `--print-code-explicit`) |

Every figure option `api.figure_options()` lists has a flag, spelled after the
option (`fixation_opacity` → `--fixation-opacity`; a switch that defaults on is
turned off with `--no-…`). That is what lets the 🔗 Share subtab's *Reproduce this
figure* block and `--print-code cli` print a command drawing exactly the figure
on screen, rather than a list of settings the CLI could not say.

Raw gaze is a third table rather than an option: `--raw-gaze` reads it (columns
auto-detected like `--fixations`) and draws the plotted trial's samples under the
fixations. It is a single-trial layer, so `--animate` and `--compare-with`
ignore it with a warning.

```bash
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

Use the installed command as the authoritative full reference:

```bash
scanpath-studio --help
scanpath-studio render --help
```

The `analyze` command writes the full tabular family without opening the app:

```bash
scanpath-studio analyze --words ia.csv --fixations fixations.csv --output-dir analysis
```

This creates word, sentence, saccade, trial, reader, character, cleaning-QA,
and run-configuration files. It takes the same `--words` / `--fixations`
(several paths each), `--trial-parts-manifest`, `--word-schema` and
`--fix-schema` as `render`, plus the optional preprocessing stage
([`api.preprocess_data`](api.md#scanpath_studio.api.preprocess_data)), which is
off unless a flag below turns it on and never deletes a row — excluded fixations
keep `excluded` / `excluded_reason`:

| Option | Default | Effect |
| --- | --- | --- |
| `--short-policy {off,merge,merge-then-discard,discard}` | `off` | What to do with fixations shorter than the threshold: `merge` folds each into its nearer neighbour within the merge distance (a short last fixation that cannot merge is excluded), `merge-then-discard` also excludes every other one that cannot merge, and `discard` excludes them all. |
| `--short-threshold-ms MS` | `80` | What counts as short. |
| `--merge-distance-chars N` | `1.0` | How close, in character widths, a neighbour must be to merge into. |
| `--discard-blink-adjacent` | off | Exclude blinks and the fixations either side of one. |
| `--pixels-per-degree PX` | none | Adds degree-valued saccade amplitudes to the saccade table. |

Every value lands in `run_config.json` beside the tables.

`scanpath-studio corpus` goes the other way: it reads a tidy CSV you already
have and renders a styled corpus figure
([`api.plot_corpus_figure`](api.md#scanpath_studio.api.plot_corpus_figure)):

```bash
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

| Option | Default | Effect |
| --- | --- | --- |
| `--input CSV` | required | The table. `profile` reads `word_id` plus the value column (and optional `lo` / `hi`), `distribution` the value column, `difference` `word_id` and `diff`. |
| `--kind {profile,distribution,difference}` | required | A per-word profile, a distribution, or a difference profile. |
| `--output PATH` | required | Any extension `save_figure` writes (`.html`, `.png`, `.svg`, `.pdf`). |
| `--value-col NAME` | `value` | The value column. |
| `--series-col NAME` | `series` | When present, one overlaid series per value. |
| `--measure-label TEXT` | `Value` | Axis / legend label. |
| `--primary-color`, `--secondary-color` | `#1f77b4`, `#e45756` | The series colours. |

The `render` command still renders one
trial per invocation; use the [Python batch pattern](automation.md#batch-pattern)
or **Export → Export bundle** for many figures.

`--all-screens` is the multipart exception: it writes one deterministic
`__screen-001-<id>` file per screen of the selected parent trial. The recorded
transition option stores the observed parent-clock gap in animation metadata;
it does not invent a visual saccade between screens. The same manifest flag is
accepted by `analyze`.

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
