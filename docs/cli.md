---
description: "Command-line reference for scanpath-studio: launch the app, or render scanpath figures from eye-tracking data headlessly, with every flag listed."
---

# CLI reference

`scanpath-studio` launches the app. Use these commands to create figures,
check data and manage saved work without opening the app:

| Command | What it does |
| --- | --- |
| [`scanpath-studio`](#launch-the-app), `run` | Launch the app |
| [`render`](#render) | Write one trial's scanpath, heatmap or replay to a file |
| [`publication`](#publication) | Export a saved figure recipe or open it as an offline editor |
| [`corpus`](#corpus) | Render a corpus figure from a tidy CSV you already have |
| [`recipe`](#recipe) | Recreate a cohort profile CSV from its saved recipe |
| [`check`](#check) | Run the Data checks on your tables |
| [`add`](#add) | Add your tables to the app's dataset list |
| [`remove`](#remove) | Remove a dataset you added from that list |
| [`annotations`](#annotations) | Read or write a dataset's favorites, tags and notes |
| [`open`](#open) | Open the app on a dataset you added, at a reading and figure |
| [`cache`](#cache) | Show or clear the recovery cache |
| [`version`](#version) | Show the build, and whether a newer release is out |
| [`cite`](#cite) | Print how to cite Scanpath Studio |

Each command takes `--help`, and `scanpath-studio --version` prints the version.
If you mistype a command, the CLI suggests the closest match.

## Publication

Download the editable file under **Save or open** to reproduce the figure with its crop, labels, caption and print settings.

```bash
scanpath-studio render --sample --screen Paragraph --width-mm 85 -o reading.publication.json
scanpath-studio publication reading.publication.json -o reading.html
scanpath-studio publication figure-2.json -o figure-2.pdf
```

Choose SVG, PDF, PNG or TIFF for artwork, or MP4 for a selected replay clip. Rendering these files requires a Chromium browser. The HTML editor is self-contained and can be used offline.

## Launch the app

```bash
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
scanpath-studio --download-dir D:\corpora  # where ⬇ Download saves public datasets
```

`scanpath-studio run …` is the same. Any other launch flag is passed on to
`streamlit run`.

The app listens on this computer only (`127.0.0.1`), and it has no login. To
serve it to other machines on a network you trust, pass
`--server.address 0.0.0.0`, or set `server.address` in a Streamlit
`config.toml` or `STREAMLIT_SERVER_ADDRESS`:

```bash
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app turns off the controls that read or write the
server's folders, because any visitor could use them. These are the *Data
directory* box, the :material/folder_open: folder picker, and ⬇ Download for
the public datasets and stimulus-image folders. On a lab server you trust, turn
them back on with `SCANPATH_LOCAL_FS=1`
(`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

## render

`render` writes one trial to a file without opening the app. The file extension
sets the format: `.html` opens as an interactive figure in your browser, while `.png`,
`.svg` and `.pdf` need Chrome, Chromium or Edge (or run `plotly_get_chrome -y`
once; see the [FAQ](faq.md#export-fails)). The figure is the app's Scanpath
design unless a flag changes it, and every [figure option](api.md#figure-options)
has a flag.

```bash
# List the trials to pick from
scanpath-studio render --sample --list-trials

# The bundled demo: each reading has several screens, so name the one to draw
scanpath-studio render --sample --screen Paragraph -o scanpath.html

# Your own data (replace p1 / t3 with IDs from --list-trials)
scanpath-studio render \
  --words ia.csv --fixations fixations.csv \
  --participant p1 --trial t3 --output scanpath.svg

# A draft file saved from the app's Draw a scanpath screen
scanpath-studio render --authoring authored-scanpath.json -o authored.html

# A public dataset, loaded as the app loads it (downloaded on first use)
scanpath-studio render --potec ./potec --list-trials
scanpath-studio render --onestop ./onestop --onestop-variant public \
  --onestop-regime ordinary --onestop-part Paragraph --list-trials

```

The Python API loads the same datasets with
[`load_potec`][scanpath_studio.datasets.load_potec] and
[`load_onestop`][scanpath_studio.datasets.load_onestop].

### Common tasks

| Goal | Flags |
| --- | --- |
| add a layer | `--word-boxes`, `--fixation-index`, `--heatmap` |
| hide a layer | `--no-text`, `--no-fixations`, `--no-saccades` |
| animate | `--animate`, optionally `--playback-speed X`. The replay uses every styling flag it can draw and names the rest in a warning |
| set the screen size | `--canvas WIDTHxHEIGHT`. `--crop-to-data` frames the data instead of the whole screen, with `--crop-margin PX` around it (default: 5% of the data's extent, at least 20 px) |
| color fixations | `--color-by FIELD`, including a column of your own once `--keep-columns COLUMN…` carries it through loading |
| size fixations by duration | `--marker-size-scale sqrt\|linear\|log\|relative` (default `sqrt`), `--marker-duration-range LO HI` (ms, default `50 600`), `--marker-size-range MIN MAX` (px), `--duration-size-legend` (show the optional size key) |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; `--animate` and `--compare-with` honor it too) |
| draw the stimulus | `--stimulus-image PATH` for one image. `--show-stimulus-image` draws each trial's stimulus image, named in the `image_path` column (`--sample` ships its images). `--image-root DIR --image-pattern '{text_id}.png'` fills `image_path` from a folder |
| smooth the heatmap | `--heatmap-style smoothed --heatmap-sigma 20` (σ in px; leave it out for an automatic σ) |
| style the word boxes | `--word-box-color`, `--word-box-line-opacity`, `--word-box-fill-color`, `--word-box-fill-opacity`. A fill opacity of 0 draws outlines only, and a line opacity of 0 the fill only |
| size the figure | `--width`, `--height`, `--scale`. For print, `--width-mm MM` or `--width-in IN` with `--dpi N` (default 300) |
| add a title and caption | `--title`, `--caption` |
| write each layer to its own file | `--separable-layers` |
| print the equivalent code | `--print-code python` (or `cli` / `both`), plus `--print-code-explicit` |

Hover fields appear in the order you list them. For a column named
`pupil, left`, preserve the comma with
`--keep-columns 'pupil, left' --fixation-hover-fields-json '["duration_ms","pupil, left"]'`.
Use `--fixation-hover-fields-json '[]'` to clear that selection. The Words
layer accepts `--word-hover-fields-json` in the same way.

### Compare two scanpaths

`--compare-participant ID --compare-trial ID` selects the second reading, B.
For example, `--compare-participant B --compare-trial 'round:2'` preserves the
colon in the trial ID. The shorthand `--compare-with PARTICIPANT:TRIAL` splits
at the last colon.

```bash
# Two participants on the same paragraph, overlaid
scanpath-studio render --sample -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --compare-with l7_183:l7_183_2_1_1_Ele --compare-screen Paragraph -o compare.html

# The same overlay, drawing only B's word boxes and text
scanpath-studio render --sample -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --compare-with l7_183:l7_183_2_1_1_Ele --compare-screen Paragraph --compare-stimulus b \
  -o compare_b.html

# Side by side: each panel draws its trial's stimulus
scanpath-studio render --sample -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --compare-with l7_183:l7_183_2_1_1_Ele --compare-screen Paragraph \
  --compare-layout side-by-side -o compare.svg

# A style for each scanpath
scanpath-studio render --sample -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --compare-with l7_183:l7_183_2_1_1_Ele --compare-screen Paragraph \
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
| pick B | `--compare-participant ID --compare-trial ID` |
| pick each screen of a multipart trial | `--screen ID` (A), `--compare-screen ID` (B); each defaults to its trial's first screen |
| arrange the panels | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`) |
| choose whose stimulus an overlay draws | `--compare-stimulus {both,a,b}` (default `both`) |
| name the two scanpaths | `--label-a TEXT --label-b TEXT` (both or neither) |
| style each scanpath | `--style-a SPEC`, `--style-b SPEC` ([keys below](#style-keys)) |
| leave out the A/B legend | `--no-compare-legend` |
| give B a separate stimulus image (side by side or stacked) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y` |
| take B from another dataset | `--compare-words PATH… --compare-fixations PATH…`, plus `--compare-raw-gaze PATH…` and `--compare-dataset-name NAME` |
| map B's columns yourself | `--compare-word-schema JSON`, `--compare-fix-schema JSON`, `--compare-raw-gaze-schema JSON`, as `--word-schema` and its siblings map A's |
| set the two screen sizes | `--canvas WxH`, `--compare-canvas WxH` |
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
| `opacity` | 0–1 | that scanpath's default |
| `hollow` | `true` or `false` | that scanpath's default |

The `--animate` replay draws one set of word boxes and no raw gaze, so it
ignores the `box_*` keys and `raw_gaze_color`.

#### What a comparison can't combine

- `--compare-with` cannot be combined with `--all-screens` or `--screens`. A
  comparison is one figure of two trials, each drawn from one screen. B's
  `--compare-screen` is looked up in B's trial, so it can be a later screen,
  or a screen of the second dataset.
- **An overlay of two datasets needs matching canvases.** On two different
  canvases, `--compare-layout overlay` exits with an error, and so does
  `--animate`, which replays both scanpaths in one coordinate space. Use
  `--compare-layout side-by-side` or `stacked`, without `--animate`. Two
  screens of one dataset with different canvases are refused the same way.
  Nothing is rescaled.
- Without `--compare-canvas`, the second dataset's screen size is estimated
  from its data, as A's is when neither `--canvas` nor a built-in source gives
  one. The data rarely spans the whole screen, so give both screen sizes when
  you know them.
- A second dataset can only be loaded from files. In Python,
  [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] takes B's frames
  directly, so any dataset you can load can be B.

### Raw gaze

`--raw-gaze PATH…` reads a Raw gaze table, with its columns auto-detected like
`--fixations`, and draws the plotted trial's samples under the fixations. With
`--compare-with` it covers both scanpaths, each in its scanpath's color.
`--compare-raw-gaze PATH…` gives B's samples when B comes from another
dataset. With the bundled demo, `--sample-raw-gaze` draws the recorded samples
for the selected reading. `--animate` ignores raw gaze with a warning.

```bash
scanpath-studio render --sample -p l37_273 -t l37_273_2_2_2_Adv --screen Paragraph \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

To plot the same reading's pupil area over its recorded clock, use
`--x-field timestamp_ms --y-field pupil_area` with `--sample-raw-gaze`.
`scanpath-studio check --sample` includes the raw table and reports how many
samples have missing positions.

When `--raw-gaze` is the only input, it is the dataset. `--list-trials` lists
its trials, and `render` draws the chosen trial's samples as recorded. No
fixations are detected from them, so `--animate` and `--compare-with` exit
with an error that says so.

```bash
scanpath-studio render --raw-gaze gaze_samples.csv --list-trials
scanpath-studio render --raw-gaze gaze_samples.csv -t t3 -o samples.png
```

### Multipart trials and many trials

`render` writes one trial per run. For many figures, use the
[Python batch recipe](guides/exporting/index.md#batch-pattern) or the
**Export bundle** on the app's :material/file_export: **Export** tab.

A multipart trial is the exception. `--all-screens` writes one
`__screen-001-<id>` file per screen of the selected trial, and
`--screens Title,Paragraph` writes only the screens named, each still numbered
by its place in the trial. When your tables have no screen column,
`--trial-parts-manifest manifest.json` assigns source rows to screens.

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
`load_scanpath_data(word_schema=…, fix_schema=…)` takes in Python. A second
dataset's tables in a comparison take theirs as `--compare-word-schema`,
`--compare-fix-schema` and `--compare-raw-gaze-schema`.

## render flags

Every `render` flag, generated from the command's parser, with the defaults
and help that `--help` prints. The figure flags are grouped like the
[figure options](api.md#figure-options) they set.

```python exec="true" idprefix="flags-"
from docs_support import cli_reference

print(cli_reference("render", heading="###"))
```

## corpus

`corpus` renders a styled corpus figure from a tidy CSV you already have, as
[`plot_corpus_figure`][scanpath_studio.api.plot_corpus_figure] does. For
`--kind profile` the CSV needs `word_id` and `value` columns.

```bash
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

To draw an overview CSV, pass its grouping column with `--series-col`. For
example, this draws participant means and their observed ranges from a summary
whose ID column is named `reader`.

```bash
scanpath-studio corpus --input overview.csv --kind overview --series-col reader \
  --measure-label "Total fixation duration (ms)" -o overview.html
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("corpus"))
```

## recipe

Recreate an **Overview**, **Cohort profile** or **Difference word profile** CSV
from its downloaded JSON recipe and source tables. Recipes include the original column mappings. If raw gaze
supplied the text IDs used by a metadata filter, pass its files with `--raw-gaze`.
The command identifies any missing metadata or annotation input and verifies
the regenerated CSV against the checksum in the recipe when available.

```bash
scanpath-studio recipe profile.recipe.json --words words.csv --fixations fixations.csv -o profile.csv
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("recipe"))
```

## check

`check` runs the **:material/database: Data Management** page's **Data checks**
on your tables without opening the app. It looks for:

- fixations lasting 0 ms or less, or with an infinite duration or onset;
- fixations and raw gaze samples with no finite position, or one more than a
  million pixels off the screen;
- word boxes with no area, or no finite position or size within a million
  pixels;
- screen sizes that are not finite and positive.

Each finding gives the rows and trials affected, a few example rows, and what
the app does with them. `check` changes nothing and exits 0 whatever it finds.
`--json` prints the table
[`check_data_health`][scanpath_studio.api.check_data_health] returns. In example rows,
missing values are `null` and infinite values are the strings `"Infinity"` or
`"-Infinity"`. To save a QC record, use `--json-report`. Its `tables` object
counts the source rows read, the rows with usable identifiers, and the
normalized rows checked. Stimulus words shared across readings can expand into
more checked rows. The report distinguishes empty tables, blank rows and rows
with missing participant or trial IDs. Its `findings` list matches `--json`.

```bash
scanpath-studio check --words ia.csv --fixations fixations.csv
scanpath-studio check --raw-gaze gaze_samples.csv --json
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("check"))
```

## add

`add` adds your tables to the app's dataset list, as **Add dataset** does,
without opening the app. Run `scanpath-studio` afterwards and the app opens on
the new dataset. If the app is already open, reload its browser tab right away:
changes you make in it before the reload are not saved. It works for an app on
your own computer, not a hosted one.

```bash
scanpath-studio add "Pilot 3" --words ia.csv --fixations fixations.csv --canvas 1920x1080
scanpath-studio add "Pilot 3" --fixations fixations_v2.csv --replace
```

A name that is already saved is an error unless you pass `--replace`, which
swaps the dataset's tables and keeps its annotations, metadata tables, share
links, description and recording setup (unless you give a new description or
`--canvas`). Without `--canvas`, the app uses a screen the data records, or
estimates one from the extent of the data. In Python, use
[`add_dataset`][scanpath_studio.api.add_dataset].

```python exec="true"
from docs_support import cli_reference

print(cli_reference("add"))
```

## remove

`remove` takes a dataset you added, in the app or with `add`, off the app's
dataset list. Its annotations, metadata tables and description go with it, as
its **Remove** on the **:material/database: Data Management** page does. Built-in
and public datasets can't be removed. If the app last had it open, it next
opens on its default dataset.

```bash
scanpath-studio remove "Pilot 3"
scanpath-studio remove "Pilot 3" --missing-ok   # no error if it isn't there
```

In Python, use [`remove_dataset`][scanpath_studio.api.remove_dataset].

```python exec="true"
from docs_support import cli_reference

print(cli_reference("remove"))
```

## open

`open` opens the app on a dataset you added, or one the app has itself (the
bundled demo, a public corpus), at one reading, with the figure set
by the same flags [`render`](#render-flags) takes. If the app is running on this
computer, the link opens in your browser. Otherwise `open` starts the app and
opens the link once it is up. `--print` prints the link instead.

```bash
scanpath-studio open "Pilot 3" -p p07 -t t12
scanpath-studio open "Pilot 3" -p p07 -t t12 --heatmap --saccade-style dash --print
```

The link is the one :material/share: **Share** → **Link** writes for the same view.
Settings it leaves out keep the values the app has. It names the dataset, so a
dataset you added opens only where it was added. A link carries no file: `render`'s
input, output and `--stimulus-image` flags are refused, and
`--show-stimulus-image` draws the dataset's own pages. `--match FIELD` opens the
**Comparisons** tab on that match field, in Full: a column as the dataset names
it, or `same_text` / `same_participant`; `--match-view overlay` opens it
with every match on one figure. In Python, use
[`app_link`][scanpath_studio.api.app_link].

```python exec="true"
from docs_support import cli_reference

print(cli_reference("open"))
```

## annotations

`annotations` reads and writes the favorites, tags and notes on a dataset you
added. `export` writes the same `annotations.json` as **Data Management →
Annotations → Export**, or a CSV table with one row per annotated reading. `import` reads either: a CSV needs `participant_id` and
`trial_id`, optionally `screen_id`, and any of `favorite`, `tags` (separated by
`;`, so a tag can't contain one in a CSV) and `note`. Importing adds a reading's tags to the ones it has, and a
favorite or note in the file replaces its own; a blank stays as it was. This
differs from the app's **Import**, which keeps or swaps a reading's whole entry.
`--replace` makes the dataset's annotations exactly the file's, and is refused
when none of the file's readings is in the dataset. Readings the dataset does not have are listed
and left out. If the app is open, reload its browser tab to see the new ones.

```bash
scanpath-studio annotations import "Pilot 3" qc_flags.csv
scanpath-studio annotations export "Pilot 3" -o annotations.json
```

In Python, use [`write_annotations`][scanpath_studio.api.write_annotations] and
[`read_annotations`][scanpath_studio.api.read_annotations].

### annotations export

```python exec="true"
from docs_support import cli_reference

print(cli_reference("annotations export"))
```

### annotations import

```python exec="true"
from docs_support import cli_reference

print(cli_reference("annotations import"))
```

## cache

A local or desktop run saves your session on your computer, so a refresh or a
restart resumes where you left off. It saves uploaded datasets, column
mappings, view settings, saved designs, metadata tables and annotations.
`cache` shows what is stored and can delete it.

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

Open **:material/database: Data Management → Saved work → Your session** to see the same information. A
running app writes a new copy at its next change, so clear the cache with the
app closed.

| To | Use |
| --- | --- |
| turn caching off for one launch | `scanpath-studio --no-persist` |
| turn it off wherever the variable is set | `SCANPATH_STUDIO_PERSIST=0` |
| move the folder | `SCANPATH_STUDIO_STATE_DIR` |

Hosted deployments do not cache by default.

## version

`version` says which build this is and how it was installed. `--check` also
asks GitHub whether a newer release is out and says how to update your install.
Only `--check` uses the network.

```bash
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("version"))
```

Between releases the version names the build: `0.35.0.post3+g8f18219` is three
commits after 0.35.0, at commit `8f18219`. In a local install or the desktop
app, open **:material/help: Help → :material/info: About & citation → App details →
:material:update: Check for updates**. In Python, call
[`check_for_updates`][scanpath_studio.api.check_for_updates].

## cite

`cite` prints how to cite Scanpath Studio. `--corpus` adds the citation of the
public corpus you used.

```bash
scanpath-studio cite                           # BibTeX
scanpath-studio cite --format apa --corpus onestop
scanpath-studio cite --format credit           # one sentence for a figure caption
```

```python exec="true"
from docs_support import cli_reference

print(cli_reference("cite"))
```

You don't have to add the citation to your files by hand: every figure `render`
writes carries it in its file metadata. The same entries are
[`cite`][scanpath_studio.api.cite] in Python.
