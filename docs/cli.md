# CLI reference

`scanpath-studio` launches the app by default. Its `render` subcommand writes
one trial without opening the UI.

## Launch

```bash
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
scanpath-studio --download-dir D:\corpora  # where ⬇ Download saves public datasets
```

The app listens on this computer only (`127.0.0.1`). It has no login, so
serving it to other machines is a deliberate step — pass
`--server.address 0.0.0.0` (or set `server.address` in a Streamlit
`config.toml`, or `STREAMLIT_SERVER_ADDRESS`), and only on a network you trust:

```bash
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app also turns off everything that reads or writes the
server's own folders — the *Data directory* box, the :material/folder_open: folder picker, ⬇ Download
for the public corpora and stimulus-image folders — since any visitor could use
them. On a lab server you trust, turn them back on with `SCANPATH_LOCAL_FS=1`
(`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

Additional launch flags are forwarded to Streamlit. A word that is not one of
the commands (`run`, `render`, `corpus`, `check`, `cache`) is an error that
names the closest one, rather than an argument handed to Streamlit.

## Render

```bash
# Inspect available IDs
scanpath-studio render --sample --list-trials

# Render the bundled demo
scanpath-studio render --sample -o scanpath.html

# Render your data (replace p1 / t3 with ids from --list-trials)
scanpath-studio render \
  --words ia.csv --fixations fixations.csv \
  --participant p1 --trial t3 --output scanpath.svg

# Render an authoring file saved from the app's Author a scanpath screen
scanpath-studio render --authoring authored-scanpath.json -o authored.html

# Inspect and render an ordered multipart trial
scanpath-studio render --words ia.csv --fixations fix.csv --list-parts
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --screen question -o question.svg
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --all-screens --animate --screen-transition recorded \
  -o replay.html
```

HTML is interactive and needs no browser. PNG, SVG and PDF need Chrome,
Chromium or Edge installed (or run `plotly_get_chrome -y` once).

### When a column isn't recognized

Column names are auto-detected (EyeLink, Tobii, SMI, Pupil Labs, Gazepoint and
snake_case spellings). When one isn't, `render` stops and prints which field it
could not find, the names it looked for, the columns your table has, and a
mapping to start from. Pass that mapping back as JSON — inline, or as a path to
a `.json` file — with `--word-schema` (the `--words` table) and/or
`--fix-schema` (the `--fixations` table). `check` takes the same two flags.

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

`--compare-with PARTICIPANT:TRIAL` draws a second trial beside or over the
first — the headless form of the app's **Compare** mode.

```bash
# Two participants on the same paragraph, overlaid
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 -o compare.html

# The same overlay, drawing only B's word boxes and text
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --compare-stimulus b \
  -o compare_b.html

# Side by side — each panel draws its own trial's stimulus
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
| pick each screen of a multipart trial | `--screen ID` (A), `--compare-screen ID` (B); each defaults to its trial's first screen |
| arrange the panels | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`) |
| whose stimulus an overlay draws | `--compare-stimulus {both,a,b}` (default `both`) |
| name the two scanpaths | `--label-a TEXT --label-b TEXT` (both or neither) |
| style each scanpath | `--style-a SPEC`, `--style-b SPEC` (below) |
| the A/B legend (on by default) | `--no-compare-legend` to leave it off |
| B's own stimulus page (split layouts) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y` |
| B from another dataset | `--compare-words PATH… --compare-fixations PATH…` |
| that dataset's raw gaze | `--compare-raw-gaze PATH…` |
| name that dataset | `--compare-dataset-name NAME` |
| declare the screens | `--canvas WxH`, `--compare-canvas WxH` |
| co-animate both scanpaths | add `--animate` (HTML output) |

`--label-a` / `--label-b` also label the `--animate` co-animation, and
`--style-a` / `--style-b` (below) style it as they style the comparison.

`--style-a` / `--style-b` are the app's per-scanpath styling (the Compare rows
under :material/blur_on: Fixations, :material/arrow_outward: Saccades, the
word boxes, heatmap and raw gaze — their *Scanpath A* / *Scanpath B* groups), `compare_scanpaths`'s `style_a` / `style_b`:
a comma-separated `KEY=VALUE` list, repeatable, with `fix_color`,
`saccade_color`, `box_color`, `box_fill_color` and `raw_gaze_color` (`#RRGGBB`;
`box_color` outlines that scanpath's word boxes, its `fix_color` when left out,
`box_fill_color` fills them, `--word-box-fill-color` when left out, and
`raw_gaze_color` colors its raw-gaze samples, its `fix_color` when left out —
all three static comparison only, the `--animate` co-animation draws one set of
boxes and no raw gaze), `heatmap_colorscale` (a Plotly color scale for that
scanpath's heatmap, `--heatmap-colorscale` when left out; the range stays shared,
and two different scales get a color bar each), `saccade_style` (`solid`, `dash`,
`dot`, `dashdot`), `saccade_width` (px), `marker_size_range` (`MIN:MAX`),
`opacity` (0.1–1) and `hollow` (`true` / `false`). A key left out keeps that
scanpath's default.

```bash
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 \
  --style-a fix_color=#D55E00,opacity=0.5 --style-b saccade_style=dash \
  -o compare_styled.html
```

`--animate --compare-with` replays **both** scanpaths on one clock, the same dual
co-animation the app renders with Animate and Compare both on.
`--compare-with` cannot be combined with `--all-screens`: a comparison
is a single figure of two trials, each drawn from one screen. Pick A's with
`--screen` and B's with `--compare-screen`; B's is looked up in B's own trial,
so it can be a later page, or a page of the second dataset.

**Overlay across two datasets requires matching canvases.** On two different
canvases `--compare-layout overlay` fails rather than falling back, and so does
`--animate`, which replays both scanpaths in one coordinate space; pass
`--compare-layout side-by-side` or `stacked`, without `--animate`. Without
`--compare-canvas` the second dataset's screen is read off its data, as A's is
when neither `--canvas` nor a built-in source gives one. That extent rarely
spans the whole screen, so state both screens when you know them. Within one
dataset, two screens whose own canvases differ are refused the same way.
Nothing is rescaled.

A second dataset is loaded from **files only**. Any corpus reachable from Python
can still be scanpath B via
[`compare_scanpaths`](api.md#scanpath_studio.api.compare_scanpaths), which takes
B's frames directly.

## Common options

| Goal | Option |
| --- | --- |
| add a layer | `--word-boxes`, `--fixation-index`, `--heatmap` (the default is the app's Scanpath design) |
| hide a layer | `--no-text`, `--no-fixations`, `--no-saccades` |
| animate | `--animate` and optionally `--playback-speed X`; every styling flag the replay can draw (`api.figure_options("animation")`) is honored, and the rest are named in a warning |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| color fixations | `--color-by FIELD` — a column of your own too, once `--keep-columns COLUMN…` carries it through loading |
| size fixations by duration | `--marker-size-scale sqrt\|linear\|log\|relative` (default `sqrt`), `--marker-duration-range LO HI` (ms, default `50 600`), `--marker-size-range MIN MAX` (px), `--no-duration-size-legend` |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; honored by `--animate` and `--compare-with` too) |
| add the stimulus image | `--stimulus-image PATH` |
| resolve per-trial images | `--image-root DIR --image-pattern '{text_id}.png'` |
| use a smoothed (Gaussian) heatmap | `--heatmap-style interpolated --heatmap-sigma 20` (σ in px; omit it for the automatic σ) |
| map arbitrary source rows to screens | `--trial-parts-manifest manifest.json` |
| export editable layers | `--separable-layers` |
| style the word boxes | `--word-box-color`, `--word-box-line-opacity`, `--word-box-fill-color`, `--word-box-fill-opacity` (0 draws outlines only / fill only) |
| draw the raw gaze | `--raw-gaze PATH…` (or `--sample-raw-gaze` with `--sample`), `--raw-gaze-schema JSON`, `--raw-gaze-color`, `--raw-gaze-marker-size`, `--raw-gaze-opacity`; `--no-raw-gaze` loads the table but hides the layer |
| size the figure | `--width`, `--height`, `--scale` |
| size a PNG for print | `--width-mm MM` or `--width-in IN`, with `--dpi N` (default 300) |
| title and caption it | `--title`, `--caption` |
| print the equivalent Python | `--print-code python` (or `cli` / `both`, plus `--print-code-explicit`) |

The [figure options table](api.md#figure-options) gives every figure option's
flag.

Raw gaze is a third table rather than an option: `--raw-gaze` reads it (columns
auto-detected like `--fixations`) and draws the plotted trial's samples under the
fixations. With `--compare-with` it covers both scanpaths, each drawn in its
own color, and `--compare-raw-gaze PATH…` is B's when B comes from
another dataset. `--animate` ignores it with a warning.

```bash
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

On its own, with no other input, `--raw-gaze` is the dataset: `--list-trials`
lists its trials and `render` draws the chosen trial's samples as recorded.
No fixations are detected from them, so `--animate` and `--compare-with` exit
with that reason instead.

```bash
scanpath-studio render --raw-gaze gaze_samples.csv --list-trials
scanpath-studio render --raw-gaze gaze_samples.csv -t t3 -o samples.png
```

## Corpus figures

`scanpath-studio corpus` goes the other way: it reads a tidy CSV you already
have (for `--kind profile`, columns `word_id` and `value`) and renders a styled
corpus figure
([`api.plot_corpus_figure`](api.md#scanpath_studio.api.plot_corpus_figure)):

```bash
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("corpus"))
```

## Data checks

`check` runs the **:material/database: Data Management** page's **Data checks** on your
tables without opening the app: fixations lasting 0 ms or less or with an
infinite duration or onset, fixations and raw-gaze samples with no finite
position, word boxes with no area or no finite position, and per-screen screen
sizes that are not finite and positive. Each
finding gives the rows and trials affected, a few example rows, and what the
app does with them. It changes nothing, and it exits 0 whatever it finds;
`--json` prints the table
[`api.check_data_health`](api.md#scanpath_studio.api.check_data_health) returns.

```bash
scanpath-studio check --words ia.csv --fixations fixations.csv
scanpath-studio check --raw-gaze gaze_samples.csv --json
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("check"))
```

## Many trials

The `render` command renders one trial per invocation; use the [Python batch pattern](automation.md#batch-pattern)
or **Export → Export bundle** for many figures.

`--all-screens` is the multipart exception: it writes one deterministic
`__screen-001-<id>` file per screen of the selected parent trial.

## Recovery cache

A local or desktop run caches your session on your own machine — uploaded
datasets, column mappings, view settings, saved designs, metadata tables and
annotations — so a refresh or a
restart resumes where you left off. `cache` shows what is stored and removes it:

```bash
scanpath-studio cache            # datasets, rows, size, folder, last written
scanpath-studio cache --path     # just the folder
scanpath-studio cache --json     # the same status as JSON
scanpath-studio cache --clear    # delete the recovery cache
```

The same information is at the foot of the **:material/database: Data Management** page, under **Saved on
this computer**. A running app writes a new copy at its next change, so clear
with the app closed. `SCANPATH_STUDIO_PERSIST=0` turns caching
off wherever it is set, `--no-persist` for one launch, and `SCANPATH_STUDIO_STATE_DIR`
moves the folder. Hosted deployments never cache. See
[Privacy](privacy.md#what-happens-to-a-file-you-upload).

## Version and updates

`scanpath-studio --version` prints the version. `version` says which build it
is and how it was installed; `--check` also asks GitHub whether a newer release
is out and prints the command that updates your install — the only time the
command uses the network:

```bash
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

Between releases the version names the build: `0.35.0.post3+g8f18219` is three
commits after 0.35.0, at commit `8f18219`. The same check is
**:material/help: Help → :material/info: About → :material/update: Check for updates**
in the app, and `check_for_updates()` in the [API](api.md#version-and-updates).

```python exec="true"
from docs_support import cli_reference

print(cli_reference("version"))
```

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

`corpus`, `check` and `version` are listed in full in their own sections above.
