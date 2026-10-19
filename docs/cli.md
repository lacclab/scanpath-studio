---
description: "Command-line reference for scanpath-studio: launch the app, or render scanpath figures from eye-tracking data headlessly, with every flag listed."
---

# CLI reference

`scanpath-studio` launches the app. Its subcommands do the rest without opening
it:

| Command | What it does |
| --- | --- |
| [`scanpath-studio`](#launch-the-app), `run` | Launch the app |
| [`render`](#render) | Write one trial's scanpath, heatmap or replay to a file |
| [`corpus`](#corpus) | Render a corpus figure from a tidy CSV you already have |
| [`check`](#check) | Run the Data checks on your tables |
| [`cache`](#cache) | Show or clear the recovery cache |
| [`version`](#version) | Show the build, and whether a newer release is out |

Each command takes `--help`, and `scanpath-studio --version` prints the version.
A word that is not a command is an error naming the closest one, rather than
an argument passed on to Streamlit.

## Launch the app

```bash
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
scanpath-studio --download-dir D:\corpora  # where ⬇ Download saves public datasets
```

`scanpath-studio run …` is the same. Any other launch flag is passed on to
`streamlit run`.

The app listens on this computer only (`127.0.0.1`). It has no login, so
serving it to other machines is a deliberate step. Pass
`--server.address 0.0.0.0` (or set `server.address` in a Streamlit
`config.toml`, or `STREAMLIT_SERVER_ADDRESS`), and only on a network you trust:

```bash
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app also turns off everything that reads or writes the
server's own folders, since any visitor could use them: the *Data directory*
box, the :material/folder_open: folder picker, and ⬇ Download for the public
corpora and stimulus-image folders. On a lab server you trust, turn them back
on with `SCANPATH_LOCAL_FS=1`
(`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

## render

`render` writes one trial to a file without opening the app. The extension
picks the format: `.html` is interactive and needs nothing else, while `.png`,
`.svg` and `.pdf` need Chrome, Chromium or Edge (or run `plotly_get_chrome -y`
once; see the [FAQ](faq.md#export-fails)). The figure is the app's Scanpath
design unless a flag changes it, and every [figure option](api.md#figure-options)
has a flag.

```bash
# The trials there are to pick from
scanpath-studio render --sample --list-trials

# The bundled demo
scanpath-studio render --sample -o scanpath.html

# Your own data (replace p1 / t3 with ids from --list-trials)
scanpath-studio render \
  --words ia.csv --fixations fixations.csv \
  --participant p1 --trial t3 --output scanpath.svg

# A draft file saved from the app's Draw a scanpath screen
scanpath-studio render --authoring authored-scanpath.json -o authored.html

# A public corpus, loaded the way the app loads it (PoTeC downloads on first use)
scanpath-studio render --potec ./potec --list-trials
scanpath-studio render --onestop ./onestop --onestop-variant public \
  --onestop-regime ordinary --onestop-part Paragraph --list-trials
```

The Python API loads the same corpora with
[`load_potec`][scanpath_studio.datasets.load_potec] and
[`load_onestop`][scanpath_studio.datasets.load_onestop].

### Common tasks

| Goal | Flags |
| --- | --- |
| add a layer | `--word-boxes`, `--fixation-index`, `--heatmap` |
| hide a layer | `--no-text`, `--no-fixations`, `--no-saccades` |
| animate | `--animate`, optionally `--playback-speed X`. Every styling flag the replay can draw is honored; the rest are named in a warning |
| set the display geometry | `--canvas WIDTHxHEIGHT`. `--crop-to-data` frames the data instead of the whole monitor, with `--crop-margin PX` around it (default: 5% of its extent, at least 20 px) |
| color fixations | `--color-by FIELD`, including a column of your own once `--keep-columns COLUMN…` carries it through loading |
| size fixations by duration | `--marker-size-scale sqrt\|linear\|log\|relative` (default `sqrt`), `--marker-duration-range LO HI` (ms, default `50 600`), `--marker-size-range MIN MAX` (px), `--no-duration-size-legend` |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; `--animate` and `--compare-with` honor it too) |
| draw the stimulus | `--stimulus-image PATH` for one image. `--show-stimulus-image` draws each trial's own page, the `image_path` its rows carry (`--sample` ships its pages). `--image-root DIR --image-pattern '{text_id}.png'` fills `image_path` from a folder |
| smooth the heatmap | `--heatmap-style smoothed --heatmap-sigma 20` (σ in px; leave it out for an automatic σ) |
| style the word boxes | `--word-box-color`, `--word-box-line-opacity`, `--word-box-fill-color`, `--word-box-fill-opacity` (0 draws outlines only, or fill only) |
| size the figure | `--width`, `--height`, `--scale`. For print, `--width-mm MM` or `--width-in IN` with `--dpi N` (default 300) |
| title and caption it | `--title`, `--caption` |
| export editable layers | `--separable-layers` |
| print the equivalent code | `--print-code python` (or `cli` / `both`), plus `--print-code-explicit` |

### Compare two scanpaths

`--compare-with PARTICIPANT:TRIAL` draws a second trial, B, beside or over the
first. It is the headless form of the app's **Compare** mode.

```bash
# Two participants on the same paragraph, overlaid
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 -o compare.html

# The same overlay, drawing only B's word boxes and text
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --compare-stimulus b \
  -o compare_b.html

# Side by side: each panel draws its own trial's stimulus
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 \
  --compare-layout side-by-side -o compare.svg

# Each scanpath styled
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 \
  --style-a fix_color=#D55E00,opacity=0.5 --style-b saccade_style=dash \
  -o compare_styled.html

# B from a second dataset
scanpath-studio render --words ia.csv --fixations fix.csv -p p1 -t t1 \
  --compare-with p1:t1 \
  --compare-words other/ia.csv --compare-fixations other/fix.csv \
  --compare-dataset-name "Our lab" \
  --canvas 1680x1050 --compare-canvas 1680x1050 \
  -o cross.html
```

| Goal | Flags |
| --- | --- |
| pick B | `--compare-with PARTICIPANT:TRIAL` |
| pick each screen of a multipart trial | `--screen ID` (A), `--compare-screen ID` (B); each defaults to its trial's first screen |
| arrange the panels | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`) |
| choose whose stimulus an overlay draws | `--compare-stimulus {both,a,b}` (default `both`) |
| name the two scanpaths | `--label-a TEXT --label-b TEXT` (both or neither) |
| style each scanpath | `--style-a SPEC`, `--style-b SPEC` ([keys below](#style-keys)) |
| leave out the A/B legend | `--no-compare-legend` |
| give B its own stimulus page (split layouts) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y` |
| take B from another dataset | `--compare-words PATH… --compare-fixations PATH…`, plus `--compare-raw-gaze PATH…` and `--compare-dataset-name NAME` |
| declare the screens | `--canvas WxH`, `--compare-canvas WxH` |
| replay both on one clock | add `--animate` (HTML output) |

`--label-a` / `--label-b` and `--style-a` / `--style-b` apply to the
`--animate` replay too.

#### Style keys

`--style-a` and `--style-b` take a comma-separated `KEY=VALUE` list and can be
repeated. They are the app's *Scanpath A* / *Scanpath B* rows and
`compare_scanpaths`'s `style_a` / `style_b`. A key left out keeps that
scanpath's default.

| Key | Value | Left out |
| --- | --- | --- |
| `fix_color` | `#RRGGBB` | that scanpath's default |
| `saccade_color` | `#RRGGBB` | that scanpath's default |
| `box_color` | `#RRGGBB`, the outline of that scanpath's word boxes | its `fix_color` |
| `box_fill_color` | `#RRGGBB`, the boxes' fill | `--word-box-fill-color` |
| `box_line_opacity`, `box_fill_opacity` | 0–1 | `--word-box-line-opacity`, `--word-box-fill-opacity` |
| `raw_gaze_color` | `#RRGGBB`, that scanpath's raw-gaze samples | its `fix_color` |
| `heatmap_colorscale` | a Plotly color scale; the range stays shared, and two different scales get a color bar each | `--heatmap-colorscale` |
| `saccade_style` | `solid`, `dash`, `dot` or `dashdot` | that scanpath's default |
| `saccade_width` | px | that scanpath's default |
| `marker_size_range` | `MIN:MAX` | that scanpath's default |
| `opacity` | 0.1–1 | that scanpath's default |
| `hollow` | `true` or `false` | that scanpath's default |

The `--animate` replay draws one set of word boxes and no raw gaze, so it
ignores the `box_*` keys and `raw_gaze_color`.

#### What a comparison can't combine

- `--compare-with` cannot be combined with `--all-screens` or `--screens`. A
  comparison is one figure of two trials, each drawn from one screen. B's
  `--compare-screen` is looked up in B's own trial, so it can be a later page,
  or a page of the second dataset.
- **An overlay of two datasets needs matching canvases.** On two different
  canvases, `--compare-layout overlay` fails rather than falling back, and so
  does `--animate`, which replays both scanpaths in one coordinate space. Use
  `--compare-layout side-by-side` or `stacked`, without `--animate`. Two
  screens of one dataset whose canvases differ are refused the same way.
  Nothing is rescaled.
- Without `--compare-canvas`, the second dataset's screen is read off its data,
  as A's is when neither `--canvas` nor a built-in source gives one. That
  extent rarely spans the whole screen, so state both screens when you know
  them.
- A second dataset is loaded from **files only**. Any corpus you can load in
  Python can still be B through
  [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths], which takes
  B's frames directly.

### Raw gaze

`--raw-gaze PATH…` reads a third table, with its columns auto-detected like
`--fixations`, and draws the plotted trial's samples under the fixations. With
`--compare-with` it covers both scanpaths, each in its own color, and
`--compare-raw-gaze PATH…` is B's when B comes from another dataset.
`--animate` ignores it with a warning.

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

### Multipart trials and many trials

`render` writes one trial per run. For many figures, use the
[Python batch recipe](guides/exporting/index.md#batch-pattern) or the app's
**Export → Export bundle**.

A multipart trial is the exception. `--all-screens` writes one
`__screen-001-<id>` file per screen of the selected trial, and
`--screens Title,Paragraph` writes only the screens named, each still numbered
by its place in the trial. `--trial-parts-manifest manifest.json` assigns
arbitrary source rows to screens.

```bash
scanpath-studio render --words ia.csv --fixations fix.csv --list-parts
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --screen question -o question.svg
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --all-screens --animate --screen-transition recorded \
  -o replay.html
```

### When a column isn't recognized

Column names are auto-detected (EyeLink, Tobii, SMI, Pupil Labs, Gazepoint and
snake_case spellings). When one isn't, `render` stops and prints which field it
could not find, the names it looked for, the columns your table has, and a
mapping to start from. Pass that mapping back as JSON, inline or as a path to
a `.json` file, with `--word-schema` (the `--words` table) and/or
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

## render flags

Every `render` flag, generated from the parser the command uses, so the
defaults and help are the ones `--help` prints. The figure flags are grouped
like the [figure options](api.md#figure-options) they set.

```python exec="true" idprefix="flags-"
from docs_support import cli_reference

print(cli_reference("render", heading="###"))
```

## corpus

`corpus` goes the other way from `render`: it reads a tidy CSV you already
have and renders a styled corpus figure, as
[`plot_corpus_figure`][scanpath_studio.api.plot_corpus_figure] does. For
`--kind profile` the CSV needs `word_id` and `value` columns.

```bash
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("corpus"))
```

## check

`check` runs the **:material/database: Data Management** page's **Data checks**
on your tables without opening the app. It looks for:

- fixations lasting 0 ms or less, or with an infinite duration or onset;
- fixations and raw-gaze samples with no finite position;
- word boxes with no area or no finite position;
- per-screen screen sizes that are not finite and positive.

Each finding gives the rows and trials affected, a few example rows, and what
the app does with them. `check` changes nothing and exits 0 whatever it finds.
`--json` prints the table
[`check_data_health`][scanpath_studio.api.check_data_health] returns.

```bash
scanpath-studio check --words ia.csv --fixations fixations.csv
scanpath-studio check --raw-gaze gaze_samples.csv --json
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("check"))
```

## cache

A local or desktop run caches your session on your own machine, so a refresh
or a restart resumes where you left off: uploaded datasets, column mappings,
view settings, saved designs, metadata tables and annotations. `cache` shows
what is stored and removes it.

```bash
scanpath-studio cache            # datasets, rows, size, folder, last written
scanpath-studio cache --path     # just the folder
scanpath-studio cache --json     # the same status as JSON
scanpath-studio cache --clear    # delete the recovery cache
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("cache"))
```

The same information is at the foot of the **:material/database: Data
Management** page, under **Saved on this computer**. A running app writes a new
copy at its next change, so clear the cache with the app closed.

| To | Use |
| --- | --- |
| turn caching off for one launch | `scanpath-studio --no-persist` |
| turn it off wherever the variable is set | `SCANPATH_STUDIO_PERSIST=0` |
| move the folder | `SCANPATH_STUDIO_STATE_DIR` |

Hosted deployments do not cache by default.

## version

`version` says which build this is and how it was installed. `--check` also
asks GitHub whether a newer release is out and prints the command that updates
your install. It is the only time the command uses the network.

```bash
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("version"))
```

Between releases the version names the build: `0.35.0.post3+g8f18219` is three
commits after 0.35.0, at commit `8f18219`. The same check is
**:material/help: Help → :material/info: About → :material/update: Check for
updates** in the app, and
[`check_for_updates`][scanpath_studio.api.check_for_updates] in Python.
