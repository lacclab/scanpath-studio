# CLI reference

`scanpath-studio` launches the app. Its subcommands do the rest without opening it:

| Command                                     | What it does                                            |
| ------------------------------------------- | ------------------------------------------------------- |
| [`scanpath-studio`](#launch-the-app), `run` | Launch the app                                          |
| [`render`](#render)                         | Write one trial's scanpath, heatmap or replay to a file |
| [`corpus`](#corpus)                         | Render a corpus figure from a tidy CSV you already have |
| [`check`](#check)                           | Run the Data checks on your tables                      |
| [`cache`](#cache)                           | Show or clear the recovery cache                        |
| [`version`](#version)                       | Show the build, and whether a newer release is out      |

Each command takes `--help`, and `scanpath-studio --version` prints the version. A word that is not a command is an error that suggests the closest command. It is not passed on to Streamlit.

## Launch the app

```
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
scanpath-studio --download-dir D:\corpora  # where ⬇ Download saves public datasets
```

`scanpath-studio run …` is the same. Any other launch flag is passed on to `streamlit run`.

The app listens on this computer only (`127.0.0.1`), and it has no login. To serve it to other machines on a network you trust, pass `--server.address 0.0.0.0`, or set `server.address` in a Streamlit `config.toml` or `STREAMLIT_SERVER_ADDRESS`:

```
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app turns off the controls that read or write the server's folders, because any visitor could use them. These are the *Data directory* box, the folder picker, and ⬇ Download for the public datasets and stimulus-image folders. On a lab server you trust, turn them back on with `SCANPATH_LOCAL_FS=1` (`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

## render

`render` writes one trial to a file without opening the app. The extension picks the format: `.html` is interactive and needs nothing else, while `.png`, `.svg` and `.pdf` need Chrome, Chromium or Edge (or run `plotly_get_chrome -y` once; see the [FAQ](https://lacclab.github.io/scanpath-studio/faq/#export-fails)). The figure is the app's Scanpath design unless a flag changes it, and every [figure option](https://lacclab.github.io/scanpath-studio/api/#figure-options) has a flag.

```
# List the trials to pick from
scanpath-studio render --sample --list-trials

# The bundled demo
scanpath-studio render --sample -o scanpath.html

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

The Python API loads the same datasets with load_potec and load_onestop.

### Common tasks

| Goal                             | Flags                                                                                                                                                                                                                                                 |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| add a layer                      | `--word-boxes`, `--fixation-index`, `--heatmap`                                                                                                                                                                                                       |
| hide a layer                     | `--no-text`, `--no-fixations`, `--no-saccades`                                                                                                                                                                                                        |
| animate                          | `--animate`, optionally `--playback-speed X`. The replay uses every styling flag it can draw and names the rest in a warning                                                                                                                          |
| set the screen size              | `--canvas WIDTHxHEIGHT`. `--crop-to-data` frames the data instead of the whole screen, with `--crop-margin PX` around it (default: 5% of the data's extent, at least 20 px)                                                                           |
| color fixations                  | `--color-by FIELD`, including a column of your own once `--keep-columns COLUMN…` carries it through loading                                                                                                                                           |
| size fixations by duration       | `--marker-size-scale sqrt\|linear\|log\|relative` (default `sqrt`), `--marker-duration-range LO HI` (ms, default `50 600`), `--marker-size-range MIN MAX` (px), `--no-duration-size-legend`                                                           |
| draw only part of a trial        | `--fix-index-range START:END` (1-based, both inclusive; `--animate` and `--compare-with` honor it too)                                                                                                                                                |
| draw the stimulus                | `--stimulus-image PATH` for one image. `--show-stimulus-image` draws each trial's stimulus image, named in the `image_path` column (`--sample` ships its images). `--image-root DIR --image-pattern '{text_id}.png'` fills `image_path` from a folder |
| smooth the heatmap               | `--heatmap-style smoothed --heatmap-sigma 20` (σ in px; leave it out for an automatic σ)                                                                                                                                                              |
| style the word boxes             | `--word-box-color`, `--word-box-line-opacity`, `--word-box-fill-color`, `--word-box-fill-opacity`. A fill opacity of 0 draws outlines only, and a line opacity of 0 the fill only                                                                     |
| size the figure                  | `--width`, `--height`, `--scale`. For print, `--width-mm MM` or `--width-in IN` with `--dpi N` (default 300)                                                                                                                                          |
| add a title and caption          | `--title`, `--caption`                                                                                                                                                                                                                                |
| write each layer to its own file | `--separable-layers`                                                                                                                                                                                                                                  |
| print the equivalent code        | `--print-code python` (or `cli` / `both`), plus `--print-code-explicit`                                                                                                                                                                               |

### Compare two scanpaths

`--compare-with PARTICIPANT:TRIAL` draws a second trial, B, beside or over the first. It does what the app's **Compare** does.

```
# Two participants on the same paragraph, overlaid
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele \
  --compare-with l7_1090:l7_1090_2_1_1_Ele -o compare.html

# The same overlay, drawing only B's word boxes and text
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele \
  --compare-with l7_1090:l7_1090_2_1_1_Ele --compare-stimulus b \
  -o compare_b.html

# Side by side: each panel draws its trial's stimulus
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele \
  --compare-with l7_1090:l7_1090_2_1_1_Ele \
  --compare-layout side-by-side -o compare.svg

# A style for each scanpath
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele \
  --compare-with l7_1090:l7_1090_2_1_1_Ele \
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

| Goal                                                       | Flags                                                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| pick B                                                     | `--compare-with PARTICIPANT:TRIAL`                                                                                   |
| pick each screen of a multipart trial                      | `--screen ID` (A), `--compare-screen ID` (B); each defaults to its trial's first screen                              |
| arrange the panels                                         | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`)                                                |
| choose whose stimulus an overlay draws                     | `--compare-stimulus {both,a,b}` (default `both`)                                                                     |
| name the two scanpaths                                     | `--label-a TEXT --label-b TEXT` (both or neither)                                                                    |
| style each scanpath                                        | `--style-a SPEC`, `--style-b SPEC` ([keys below](#style-keys))                                                       |
| leave out the A/B legend                                   | `--no-compare-legend`                                                                                                |
| give B a separate stimulus image (side by side or stacked) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y`                      |
| take B from another dataset                                | `--compare-words PATH… --compare-fixations PATH…`, plus `--compare-raw-gaze PATH…` and `--compare-dataset-name NAME` |
| set the two screen sizes                                   | `--canvas WxH`, `--compare-canvas WxH`                                                                               |
| replay both on one clock                                   | add `--animate` (HTML output)                                                                                        |

`--label-a` / `--label-b` and `--style-a` / `--style-b` apply to the `--animate` replay too.

#### Style keys

`--style-a` and `--style-b` take a comma-separated `KEY=VALUE` list and can be repeated. They are the app's *Scanpath A* / *Scanpath B* rows and `compare_scanpaths`'s `style_a` / `style_b`. A key left out keeps that scanpath's default.

| Key                                    | Value                                                                                       | Left out                                             |
| -------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `fix_color`                            | `#RRGGBB`                                                                                   | that scanpath's default                              |
| `saccade_color`                        | `#RRGGBB`                                                                                   | that scanpath's default                              |
| `box_color`                            | `#RRGGBB`, the outline of that scanpath's word boxes                                        | its `fix_color`                                      |
| `box_fill_color`                       | `#RRGGBB`, the boxes' fill                                                                  | `--word-box-fill-color`                              |
| `box_line_opacity`, `box_fill_opacity` | 0–1                                                                                         | `--word-box-line-opacity`, `--word-box-fill-opacity` |
| `raw_gaze_color`                       | `#RRGGBB`, that scanpath's raw-gaze samples                                                 | its `fix_color`                                      |
| `heatmap_colorscale`                   | a Plotly color scale; the range stays shared, and two different scales get a color bar each | `--heatmap-colorscale`                               |
| `saccade_style`                        | `solid`, `dash`, `dot` or `dashdot`                                                         | that scanpath's default                              |
| `saccade_width`                        | px                                                                                          | that scanpath's default                              |
| `marker_size_range`                    | `MIN:MAX`                                                                                   | that scanpath's default                              |
| `opacity`                              | 0.1–1                                                                                       | that scanpath's default                              |
| `hollow`                               | `true` or `false`                                                                           | that scanpath's default                              |

The `--animate` replay draws one set of word boxes and no raw gaze, so it ignores the `box_*` keys and `raw_gaze_color`.

#### What a comparison can't combine

- `--compare-with` cannot be combined with `--all-screens` or `--screens`. A comparison is one figure of two trials, each drawn from one screen. B's `--compare-screen` is looked up in B's trial, so it can be a later screen, or a screen of the second dataset.
- **An overlay of two datasets needs matching canvases.** On two different canvases, `--compare-layout overlay` exits with an error, and so does `--animate`, which replays both scanpaths in one coordinate space. Use `--compare-layout side-by-side` or `stacked`, without `--animate`. Two screens of one dataset with different canvases are refused the same way. Nothing is rescaled.
- Without `--compare-canvas`, the second dataset's screen size is estimated from its data, as A's is when neither `--canvas` nor a built-in source gives one. The data rarely spans the whole screen, so give both screen sizes when you know them.
- A second dataset can only be loaded from files. In Python, compare_scanpaths takes B's frames directly, so any dataset you can load can be B.

### Raw gaze

`--raw-gaze PATH…` reads a Raw gaze table, with its columns auto-detected like `--fixations`, and draws the plotted trial's samples under the fixations. With `--compare-with` it covers both scanpaths, each in its scanpath's color. `--compare-raw-gaze PATH…` gives B's samples when B comes from another dataset. `--animate` ignores raw gaze with a warning.

```
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_2_2_Adv \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

When `--raw-gaze` is the only input, it is the dataset. `--list-trials` lists its trials, and `render` draws the chosen trial's samples as recorded. No fixations are detected from them, so `--animate` and `--compare-with` exit with an error that says so.

```
scanpath-studio render --raw-gaze gaze_samples.csv --list-trials
scanpath-studio render --raw-gaze gaze_samples.csv -t t3 -o samples.png
```

### Multipart trials and many trials

`render` writes one trial per run. For many figures, use the [Python batch recipe](https://lacclab.github.io/scanpath-studio/guides/exporting/#batch-pattern) or the **Export bundle** on the app's **Export** tab.

A multipart trial is the exception. `--all-screens` writes one `__screen-001-<id>` file per screen of the selected trial, and `--screens Title,Paragraph` writes only the screens named, each still numbered by its place in the trial. When your tables have no screen column, `--trial-parts-manifest manifest.json` assigns source rows to screens.

```
scanpath-studio render --words ia.csv --fixations fix.csv --list-parts
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --screen question -o question.svg
scanpath-studio render --words ia.csv --fixations fix.csv \
  -p p1 -t t3 --all-screens --animate --screen-transition recorded \
  -o replay.html
```

### When a column isn't recognized

Column names are auto-detected (EyeLink, Tobii, SMI, Pupil Labs, Gazepoint and snake_case spellings). When one isn't, `render` stops and prints which field it could not find, the names it looked for, the columns your table has, and a mapping to start from. Pass that mapping back as JSON, inline or as a path to a `.json` file, with `--word-schema` (the `--words` table) and/or `--fix-schema` (the `--fixations` table). `check` takes the same two flags.

```
scanpath-studio render --words ia.csv --fixations fix.csv \
  --word-schema '{"trial": "TRIAL_LABEL", "word_id": "IA_ID", "text": "IA_LABEL",
                  "left": "IA_LEFT", "right": "IA_RIGHT", "top": "IA_TOP", "bottom": "IA_BOTTOM"}' \
  --fix-schema fix_schema.json -o scanpath.html
```

A mapping replaces auto-detection for that table, so it has to name every required field, not only the one that failed. It is the same dict `load_scanpath_data(word_schema=…, fix_schema=…)` takes in Python.

## render flags

Every `render` flag, generated from the command's parser, with the defaults and help that `--help` prints. The figure flags are grouped like the [figure options](https://lacclab.github.io/scanpath-studio/api/#figure-options) they set.

### Trial and output

| Option                | Value                 | Default   | Description                                                                                                                                            |
| --------------------- | --------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `-p` `--participant`  | `PARTICIPANT`         | —         | Participant ID (default: the first).                                                                                                                   |
| `-t` `--trial`        | `TRIAL`               | —         | Trial ID (default: the participant's first).                                                                                                           |
| `--screen`            | `SCREEN`              | —         | Screen ID within a multipart trial (default: the first screen).                                                                                        |
| `--list-trials`       | switch                | —         | Print every trial with its participant, trial and text IDs, then exit. Pass a trial ID to -t.                                                          |
| `--list-parts`        | switch                | —         | Print the screens of each multipart trial in order, then exit. -p and -t narrow the list.                                                              |
| `--all-screens`       | switch                | —         | Render every screen of the selected trial, one file each. The screen ID goes before the output's extension.                                            |
| `--screens`           | `ID[,ID...]`          | —         | Like `--all-screens`, for only these screens: comma-separated screen IDs, e.g. Title,Paragraph. See `--list-parts`.                                    |
| `--screen-transition` | `instant`, `recorded` | `instant` | With `--all-screens` `--animate`: record no delay between screens (instant) or the recorded one (recorded) in each file's metadata (default: instant). |
| `-o` `--output`       | `PATH`                | —         | Output file. Its extension sets the format: .html, .png, .svg or .pdf.                                                                                 |
| `--animate`           | switch                | —         | Render the animated replay instead of the static figure (HTML only).                                                                                   |

### Input

| Option                                                                 | Value                                                                              | Default         | Description                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--sample`                                                             | switch                                                                             | —               | Use the bundled demo, from OneStop: 2 participants, 12 trials each (`--list-trials` shows them).                                                                                                                                                                                                                                                                    |
| `--authoring`                                                          | `PATH`                                                                             | —               | A draft file from the app's Draw a scanpath screen.                                                                                                                                                                                                                                                                                                                 |
| `--words`                                                              | `PATH [PATH ...]`                                                                  | —               | The Words table: CSV, TSV, TXT, TAB, Parquet, Feather, XLSX or XLS, or a .zip of them. Columns are auto-detected from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and snake_case names. Several paths, or a quoted glob, are stacked into one table.                                                                                                                 |
| `--fixations`                                                          | `PATH [PATH ...]`                                                                  | —               | The Fixations table, in the formats `--words` reads and auto-detected the same way. Several paths, or a quoted glob, are stacked into one table (e.g. one file per participant).                                                                                                                                                                                    |
| `--image-root`                                                         | `DIR`                                                                              | —               | A folder of stimulus images. Each row's image is found with `--image-pattern` and stored in its image_path column. Add `--show-stimulus-image` to draw them. Works with every input, including `--sample` and the public datasets.                                                                                                                                  |
| `--image-pattern`                                                      | `PATTERN`                                                                          | `{text_id}.png` | File name pattern inside `--image-root`, with column placeholders, e.g. '{text_id}.png' or '{participant_id}/{trial_id}.png'.                                                                                                                                                                                                                                       |
| `--trial-parts-manifest`                                               | `PATH`                                                                             | —               | A JSON manifest that assigns source rows to the screens of each trial, in order. Use it with `--words` / `--fixations` when the tables have no screen column.                                                                                                                                                                                                       |
| `--word-schema`                                                        | `JSON`                                                                             | —               | Column mapping for the `--words` table, replacing auto-detection. A JSON object from each field to a column name, or the path of a JSON file holding one, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}'. It is the dict api.load_scanpath_data takes. Needed only when a column isn't recognized, and the error then prints a mapping to start from.     |
| `--fix-schema`                                                         | `JSON`                                                                             | —               | Column mapping for the `--fixations` table, replacing auto-detection. A JSON object from each field to a column name, or the path of a JSON file holding one, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}'. It is the dict api.load_scanpath_data takes. Needed only when a column isn't recognized, and the error then prints a mapping to start from. |
| `--keep-columns`                                                       | `COLUMN [COLUMN ...]`                                                              | —               | More columns to keep through loading, under the names they have in your files (e.g. a pupil size), from whichever table has them. Without it, loading keeps only the mapped and recognized fields. A kept fixation column can be used by `--color-by`, an axis or a hover. Same as keep_columns= in api.load_scanpath_data.                                         |
| `--potec`                                                              | `DIR`                                                                              | —               | Load the PoTeC corpus (DiLi-Lab/PoTeC) from DIR, downloading the files it needs (~45 MB) on first use. It has 75 participants, with IDs between 0 and 105 (`--list-trials` shows them). A trial is one participant reading one text, named <participant>\_<text> (e.g. 0_b0). The texts are b0–b5 and p0–p5.                                                        |
| `--onestop`                                                            | `DIR`                                                                              | —               | Load the OneStop corpus from DIR. The public variant downloads the reports for the chosen regime and parts from OSF on first use, tens to hundreds of MB each. The lacclab variant reads a local export. Choose with `--onestop-regime`, `--onestop-part` and `--onestop-variant`.                                                                                  |
| `--onestop-regime`                                                     | `ordinary`, `information_seeking`, `repeated`, `information_seeking_repeated`      | `ordinary`      | OneStop reading regime for `--onestop` (default: ordinary).                                                                                                                                                                                                                                                                                                         |
| `--onestop-part`                                                       | `Title`, `Question_Preview`, `Paragraph`, `Questions`, `Answers`, `QA`, `Feedback` | —               | OneStop trial part for `--onestop`. Repeatable (default: Paragraph). With several, each part is a separate trial.                                                                                                                                                                                                                                                   |
| `--onestop-variant`                                                    | `public`, `lacclab`                                                                | `public`        | OneStop source for `--onestop`: public, downloaded from OSF, or lacclab, a local lab-processed export with no download.                                                                                                                                                                                                                                             |
| `--participant-metadata`                                               | `FILE [FILE ...]`                                                                  | —               | A participant metadata table: one row per participant, with a participant ID column and any other fields. Several files, or a glob, are stacked into one table. Its rows are checked against the loaded participants and reported, and its fields are added to the `--list-trials` output.                                                                          |
| `--trial-metadata`                                                     | `FILE [FILE ...]`                                                                  | —               | A trial metadata table: one row per trial, with a trial ID column and any other fields. Several files, or a glob, are stacked into one table. It is checked and reported the same way, and its fields are added to the `--list-trials` output.                                                                                                                      |
| `--trial-metadata-participant-column` `--trial-metadata-reader-column` | `COLUMN`                                                                           | —               | Key the `--trial-metadata` table by participant and trial, with this column as the participant ID. Without it, the table is keyed by trial ID alone, and each row applies to every participant's reading of that trial. This is never guessed from the file.                                                                                                        |
| `--text-metadata`                                                      | `FILE [FILE ...]`                                                                  | —               | A text metadata table: one row per text, with a text ID column and any other fields. Several files, or a glob, are stacked into one table. It is checked and reported the same way, and its fields are added to the `--list-trials` output. It is keyed by text alone, never by participant.                                                                        |

### Fixations

| Option                              | Value                                                                                  | Default | Description                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------- | -------------------------------------------------------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-fixations`                    | switch                                                                                 | —       | Hide the fixations.                                                                                                                                                                                                                                                                                                         |
| `--fixation-index`                  | switch                                                                                 | —       | Number the fixations in order (the app's Fixation index).                                                                                                                                                                                                                                                                   |
| `--no-fixation-index` `--no-order`  | switch                                                                                 | —       | Hide the fixation numbers (the default).                                                                                                                                                                                                                                                                                    |
| `--snap-fixations`                  | switch                                                                                 | —       | Move each fixation up or down onto its text line: its word's line, else the nearest. Its x stays. `--snap-position` sets where on the line.                                                                                                                                                                                 |
| `--snap-position`                   | `LINES`                                                                                | —       | Where on its line a snapped fixation sits, in line heights from the line's middle: 0 centers it, -0.5 is the top edge, 0.5 the bottom edge (default: -0.5). Used with `--snap-fixations`.                                                                                                                                   |
| `--palette`                         | `{default,print,high-contrast}`                                                        | —       | Color palette (the app's Palette): default (colorblind-safe, Okabe–Ito), print (grayscale, for black-and-white printing) or high-contrast. The app's palette names work too. Each --\*-color flag overrides it.                                                                                                             |
| `--color-by`                        | `FIELD`                                                                                | —       | Fixations table column to color the fixations by, e.g. duration_ms, or 'line' for each fixation's text line (same as `--color-by-line`). Default: '(uniform)', one color, since marker size already shows duration.                                                                                                         |
| `--fixation-color`                  | `COLOR`                                                                                | —       | Fixation color when `--color-by` is '(uniform)' (default: #0072B2).                                                                                                                                                                                                                                                         |
| `--fixation-symbol`                 | `circle`, `square`, `diamond`, `triangle-up`, `cross`, `x`, `star`, `hexagon`, `heart` | —       | Fixation marker shape. Unlike color, shape survives a grayscale print (default: circle).                                                                                                                                                                                                                                    |
| `--fixation-colorscale`             | `NAME`                                                                                 | —       | Color scale for `--color-by`, e.g. Viridis (default: Blues).                                                                                                                                                                                                                                                                |
| `--marker-size-range`               | `MIN MAX`                                                                              | —       | Smallest and largest fixation marker size in px, e.g. 4 12 (default: 8 24). A smaller range suits thumbnails.                                                                                                                                                                                                               |
| `--marker-size-scale`               | `sqrt`, `linear`, `log`, `relative`                                                    | —       | How duration sets marker size (default: sqrt). sqrt, linear and log map `--marker-duration-range` onto `--marker-size-range`, so a duration gets the same size in every trial, comparison and replay. With sqrt, marker area grows with duration. relative stretches each figure from its shortest to its longest fixation. |
| `--marker-duration-range`           | `LO HI`                                                                                | —       | The durations in ms that get the smallest and largest marker (default: 50 600). Shorter and longer fixations are clamped to them. Not used by `--marker-size-scale` relative.                                                                                                                                               |
| `--fixation-opacity`                | `O`                                                                                    | —       | Fixation marker opacity, 0.1–1.0 (default: 0.7, so overlapping fixations show through).                                                                                                                                                                                                                                     |
| `--fixation-outline-width`          | `PX`                                                                                   | —       | Outline width around each filled fixation marker, 0–5 px; 0 draws none (default: 0.5).                                                                                                                                                                                                                                      |
| `--fixation-outline-color`          | `COLOR`                                                                                | —       | Color of that outline (default: #111111).                                                                                                                                                                                                                                                                                   |
| `--hollow-fixations`                | switch                                                                                 | —       | Draw the fixations as outlines instead of filled markers.                                                                                                                                                                                                                                                                   |
| `--color-by-line`                   | switch                                                                                 | —       | Color each fixation by the text line it lands on, with the lines found from the word boxes. Overrides `--color-by`. Same as `--color-by` line.                                                                                                                                                                              |
| `--fixation-color-range`            | `LO HI`                                                                                | —       | Fix the `--color-by` color scale to LO..HI instead of the trial's range, so several figures share one scale.                                                                                                                                                                                                                |
| `--order-font-size`                 | `PX`                                                                                   | —       | Size of the fixation index numbers (default: 10).                                                                                                                                                                                                                                                                           |
| `--order-font-color`                | `COLOR`                                                                                | —       | Color of the fixation index numbers (default: #111111).                                                                                                                                                                                                                                                                     |
| `--no-fixation-colorbar`            | switch                                                                                 | —       | Leave out `--color-by`'s color bar.                                                                                                                                                                                                                                                                                         |
| `--fixation-colorbar-orientation`   | `vertical`, `horizontal`                                                               | —       | Fixation color bar: beside the plot (vertical, default) or below it.                                                                                                                                                                                                                                                        |
| `--fixation-colorbar-tickangle`     | `DEG`                                                                                  | —       | Fixation color bar: tick-label angle, -90–90 (default: 0).                                                                                                                                                                                                                                                                  |
| `--fixation-colorbar-tickfont-size` | `PX`                                                                                   | —       | Fixation color bar: tick-label size (default: 12).                                                                                                                                                                                                                                                                          |
| `--fixation-colorbar-thickness`     | `PX`                                                                                   | —       | Fixation color bar: thickness, 4–40 px (default: 14).                                                                                                                                                                                                                                                                       |
| `--fixation-colorbar-length`        | `F`                                                                                    | —       | Fixation color bar: length as a share of the plot's side, 0.1–1.0 (default: a third of its height upright, 0.6 of its width lying down).                                                                                                                                                                                    |

### Saccades

| Option                         | Value                             | Default | Description                                                                                                                                                                                                                                                                      |
| ------------------------------ | --------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-saccades`                | switch                            | —       | Hide the saccades.                                                                                                                                                                                                                                                               |
| `--saccade-arrows`             | switch                            | —       | Draw an arrowhead on each saccade (the app's Direction arrows).                                                                                                                                                                                                                  |
| `--saccade-color`              | `COLOR`                           | —       | Saccade line and arrow color, as hex or a CSS name (default: #CC79A7).                                                                                                                                                                                                           |
| `--saccade-style`              | `solid`, `dash`, `dot`, `dashdot` | —       | Saccade line dash style (default: solid).                                                                                                                                                                                                                                        |
| `--saccade-width`              | `PX`                              | —       | Saccade line width in px, 0.5–10 (default: 2).                                                                                                                                                                                                                                   |
| `--saccade-opacity`            | `O`                               | —       | Opacity of the saccade lines and arrows, 0.1–1.0 (default: 1). In a comparison, both scanpaths share it.                                                                                                                                                                         |
| `--saccade-arrow-size`         | `PX`                              | —       | Size of the `--saccade-arrows` arrowheads, 4–40 px (default: 12).                                                                                                                                                                                                                |
| `--saccade-color-by-type`      | switch                            | —       | Color each saccade by its type: forward, skip, refixation, return sweep or regression (the app's By type).                                                                                                                                                                       |
| `--saccade-color-by-direction` | switch                            | —       | Color each saccade as forward or regression (the app's Forward / regression).                                                                                                                                                                                                    |
| `--saccade-type-color`         | `CLASS=COLOR`                     | —       | Set one saccade type's color, e.g. `--saccade-type-color` regression=#000000. Repeatable. Types: forward, skip, refixation, return_sweep, regression. Implies `--saccade-color-by-type`. With `--saccade-color-by-direction`, it sets the forward and regression colors instead. |
| `--saccade-arcs`               | switch                            | —       | Draw saccades as upward arcs instead of straight lines (the app's Shape: Arc).                                                                                                                                                                                                   |

### Stimulus

| Option                     | Value                              | Default | Description                                                                                                                                                                                                                         |
| -------------------------- | ---------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-text` `--no-labels`  | switch                             | —       | Hide the stimulus text.                                                                                                                                                                                                             |
| `--highlight-column`       | `COLUMN`                           | —       | Boolean Words table column that marks the words to highlight (e.g. is_in_aspan, OneStop's answer span; default: none). `--critical-span-style` sets how they are drawn.                                                             |
| `--critical-span-style`    | `mark-text`, `mark-border`, `none` | —       | How the `--highlight-column` words are marked: mark-text recolors them, mark-border outlines their boxes, none draws neither (default: mark-text).                                                                                  |
| `--stimulus-image`         | `PATH`                             | —       | Draw an image (PNG or JPG) under the scanpath as the stimulus. It is sized to the PNG's pixel size, else to the canvas. Use `--stimulus-image-size` and `--stimulus-image-origin` to place a cropped image in fixation coordinates. |
| `--stimulus-image-size`    | `WxH`                              | —       | Stimulus image size in px, e.g. 1310x991 (default: the PNG's pixel size, else the canvas). Use with `--stimulus-image`.                                                                                                             |
| `--stimulus-image-origin`  | `X,Y`                              | —       | Top-left corner of the stimulus image in screen px, e.g. 305,44 (default: 0,0). Use with `--stimulus-image` to line a centered crop up with the fixations.                                                                          |
| `--stimulus-image-opacity` | `O`                                | —       | Stimulus image opacity, 0.1–1.0 (default: 1.0 = opaque). Lower it so the fixations, saccades and word boxes stand out on a busy image.                                                                                              |
| `--show-stimulus-image`    | switch                             | —       | Draw each trial's stimulus image under the scanpath, from the image_path column of its rows, placed at image_x / image_y. `--image-root` fills that column, and `--sample` ships its images. `--stimulus-image` takes precedence.   |
| `--text-color`             | `COLOR`                            | —       | Stimulus text color (default: #000000).                                                                                                                                                                                             |
| `--redact-text`            | switch                             | —       | Draw a rounded block in the text color in place of each word's letters, and leave the words out of the hovers. The figure keeps the text's layout but not its words (the app's Text → Redact).                                      |
| `--highlight-text-color`   | `COLOR`                            | —       | Color of the `--highlight-column` words under `--critical-span-style` mark-text (default: #D55E00).                                                                                                                                 |
| `--span-border-color`      | `COLOR`                            | —       | Box color under `--critical-span-style` mark-border (default: #000000).                                                                                                                                                             |
| `--background-color`       | `COLOR`                            | —       | Plot background color (default: #ffffff).                                                                                                                                                                                           |
| `--line-spacing`           | `N`                                | —       | Line spacing, in font sizes: the text's font size is the distance between lines ÷ N (default: 3, a blank line above and below).                                                                                                     |
| `--no-scale-text-to-boxes` | switch                             | —       | Draw the text at `--font-size` instead of fitting it to the word boxes (the app's Fit to word boxes).                                                                                                                               |
| `--font-size`              | `PX`                               | `16`    | Base figure font size (default: 16).                                                                                                                                                                                                |
| `--font-family`            | `NAME`                             | —       | Font for all figure text (default: monospace).                                                                                                                                                                                      |

### Word boxes

| Option                         | Value   | Default | Description                                                                                                                         |
| ------------------------------ | ------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `--word-boxes`                 | switch  | —       | Draw the word boxes.                                                                                                                |
| `--no-word-boxes` `--no-words` | switch  | —       | Hide the word boxes (the default).                                                                                                  |
| `--word-box-color`             | `COLOR` | —       | Word-box outline color (default: #6c757d). In a comparison, each scanpath's boxes are outlined in its color instead.                |
| `--word-box-line-opacity`      | `O`     | —       | Word-box outline opacity, 0–1; 0 draws the fill only (default: 1). Below 1 the outline color must be #rrggbb, #rgb or rgb(r, g, b). |
| `--word-box-fill-color`        | `COLOR` | —       | Word-box fill color, drawn at `--word-box-fill-opacity`: #rrggbb, #rgb or rgb(r, g, b) (default: #646464).                          |
| `--word-box-fill-opacity`      | `O`     | —       | Word-box fill opacity, 0–1; 0 draws outlines only (default: 0.05).                                                                  |

### Heatmap

| Option                             | Value                    | Default | Description                                                                                                                                                                        |
| ---------------------------------- | ------------------------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--heatmap`                        | switch                   | —       | Draw the heatmap.                                                                                                                                                                  |
| `--no-heatmap`                     | switch                   | —       | Hide the heatmap (the default).                                                                                                                                                    |
| `--heatmap-metric`                 | `COLUMN`                 | —       | What the heatmap colors by (the app's Color → By): the fixation duration column, under your file's name or as duration_ms, or counts for the fixation count. Default: duration_ms. |
| `--heatmap-style`                  | `word-boxes`, `smoothed` | —       | Heatmap style: word-boxes tints each word box, smoothed blurs the fixations (default: word-boxes).                                                                                 |
| `--heatmap-sigma`                  | `PX`                     | —       | Blur of `--heatmap-style` smoothed, as a Gaussian σ in px (default: 2% of the data's larger span, at least 8 px).                                                                  |
| `--heatmap-colorscale`             | `NAME`                   | —       | Heatmap color scale, e.g. Greens (default: Blues).                                                                                                                                 |
| `--heatmap-norm`                   | `linear`, `log`          | —       | Heatmap color scaling: linear (default) or log. Log keeps a few words with long dwell times from washing out the rest.                                                             |
| `--heatmap-opacity`                | `O`                      | —       | Heatmap opacity, 0.05–1.0 (default: 0.5 for word-boxes, or 0.35 for a trial with no word boxes; 0.45 for smoothed).                                                                |
| `--heatmap-range`                  | `LO HI`                  | —       | Fix the heatmap's color scale to LO..HI instead of the trial's range.                                                                                                              |
| `--word-heatmap-col`               | `COLUMN`                 | —       | With `--heatmap`, for a dataset with no fixations: tint each word box by this numeric Words table column, e.g. gpt2_surprisal, instead of its total fixation duration.             |
| `--word-heatmap-title`             | `TEXT`                   | —       | Color-bar title for `--word-heatmap-col` (default: Value).                                                                                                                         |
| `--no-heatmap-colorbar`            | switch                   | —       | Leave out the heatmap's color bar.                                                                                                                                                 |
| `--heatmap-colorbar-orientation`   | `vertical`, `horizontal` | —       | Heatmap color bar: beside the plot (vertical, default) or below it.                                                                                                                |
| `--heatmap-colorbar-tickangle`     | `DEG`                    | —       | Heatmap color bar: tick-label angle, -90–90 (default: 0).                                                                                                                          |
| `--heatmap-colorbar-tickfont-size` | `PX`                     | —       | Heatmap color bar: tick-label size (default: 12).                                                                                                                                  |
| `--heatmap-colorbar-thickness`     | `PX`                     | —       | Heatmap color bar: thickness, 4–40 px (default: 14).                                                                                                                               |
| `--heatmap-colorbar-length`        | `F`                      | —       | Heatmap color bar: length as a share of the plot's side, 0.1–1.0 (default: a third of its height upright, 0.6 of its width lying down).                                            |

### Raw gaze

| Option                   | Value             | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------ | ----------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--raw-gaze`             | `PATH [PATH ...]` | —       | The Raw gaze table to draw under the fixations, in the formats `--fixations` reads and auto-detected the same way. Several paths, or a quoted glob, are stacked into one table. Drawn on static figures and `--compare-with` comparisons, where each scanpath's samples take its color, but not with `--animate`. As the only input it is the dataset: its trials are listed and drawn as recorded, and no fixations are detected from the samples. |
| `--no-raw-gaze`          | switch            | —       | Load the `--raw-gaze` table but hide its layer, like turning off the app's Raw gaze switch. With raw gaze as the only input, the figure then shows no gaze.                                                                                                                                                                                                                                                                                         |
| `--sample-raw-gaze`      | switch            | —       | With `--sample`: draw the bundled demo's raw gaze. It is synthesized, and covers one trial only.                                                                                                                                                                                                                                                                                                                                                    |
| `--raw-gaze-schema`      | `JSON`            | —       | Column mapping for the `--raw-gaze` table, replacing auto-detection, in the form `--fix-schema` takes. Needed only when a column isn't recognized.                                                                                                                                                                                                                                                                                                  |
| `--raw-gaze-color`       | `COLOR`           | —       | Raw gaze sample color (default: #888888). In a comparison, each scanpath's samples are drawn in its color instead.                                                                                                                                                                                                                                                                                                                                  |
| `--raw-gaze-marker-size` | `PX`              | —       | Raw gaze sample size, 1–12 px (default: 4).                                                                                                                                                                                                                                                                                                                                                                                                         |
| `--raw-gaze-opacity`     | `O`               | —       | Raw gaze sample opacity, 0.1–1.0 (default: 0.6).                                                                                                                                                                                                                                                                                                                                                                                                    |

### Filters & highlights

| Option              | Value       | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------- | ----------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--fix-index-range` | `START:END` | —       | Draw only fixations START to END, counting from 1, both included, e.g. `--fix-index-range` 1:40. `--animate` then replays only that range. With `--compare-with` it applies to both scanpaths, unless `--compare-fix-index-range` sets B's.                                                                                                                                                                                                  |
| `--fixation-flag`   | `SPEC`      | —       | Highlight or hide one kind of fixation, like the app's Filters & highlights. Repeatable. SPEC is CATEGORY=MODE[,threshold_ms=N][,symbol=S][,color=#RRGGBB]. CATEGORY is short, long, oob (outside every word box) or blink. MODE is off, highlight or hide. threshold_ms applies to short and long only. hide removes the fixations from the figure only; measures and exports keep them. E.g. `--fixation-flag` short=hide,threshold_ms=80. |
| `--saccade-classes` | `CLASSES`   | —       | Draw only these saccade types, comma-separated, e.g. `--saccade-classes` regression,return_sweep. Types: forward, skip, refixation, return_sweep, regression, other (off the text). A hidden type loses its line and its arrow. Default: all.                                                                                                                                                                                                |

### Figure & canvas

| Option                               | Value   | Default | Description                                                                                                                                                                    |
| ------------------------------------ | ------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--canvas`                           | `WxH`   | —       | Screen size in px, e.g. 2560x1440 (default: 2560x1440 for `--sample` and `--onestop`, 1680x1050 for `--potec`, 1200x800 for `--authoring`, otherwise estimated from the data). |
| `--coordinate-grid`                  | switch  | —       | Draw a grid in screen pixels over the scanpath (the app's Axes & grid → Grid).                                                                                                 |
| `--coordinate-grid-spacing`          | `PX`    | —       | The grid's major spacing in px. Implies `--coordinate-grid`. Leave it out for an automatic spacing of 1, 2 or 5 × 10ⁿ px.                                                      |
| `--coordinate-grid-font-size`        | `PX`    | —       | Size of the coordinate grid's labels, 6–36 px (default: 18).                                                                                                                   |
| `--no-plot-frame`                    | switch  | —       | Leave out the border around the plot area.                                                                                                                                     |
| `--plot-frame-color`                 | `COLOR` | —       | Color of the border around the plot area (default: #000000).                                                                                                                   |
| `--x-field`                          | `FIELD` | —       | Fixations table column on the x axis (default: x). A non-spatial one draws a chart of the fixations instead of the scanpath.                                                   |
| `--y-field`                          | `FIELD` | —       | Fixations table column on the y axis (default: y).                                                                                                                             |
| `--crop-to-data` `--no-full-monitor` | switch  | —       | Frame the plot on the data instead of the whole `--canvas` screen (the app's Crop to data).                                                                                    |
| `--crop-margin`                      | `PX`    | —       | The margin around the data, in screen px, when cropping to it (default: 5% of the data's extent, at least 20 px). Implies `--crop-to-data`.                                    |

### Title & labels

| Option                 | Value                  | Default | Description                                                                                                                                                                                  |
| ---------------------- | ---------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--illustration`       | switch                 | —       | Apply the app's Illustration design: fixations snapped to their lines, arced saccades, one color for each, and no word boxes, heatmap, fixation index or arrows. A flag you give still wins. |
| `--illustration-label` | `auto`, `show`, `hide` | `auto`  | The Illustration label: auto adds it when the figure changes what the data shows (e.g. snapped fixations or arced saccades), show always adds it, and hide leaves it out (default: auto).    |
| `--illustration-text`  | `TEXT`                 | —       | The Illustration label's text (default: "Illustration · <reasons>").                                                                                                                         |
| `--title`              | `TEXT`                 | —       | A title on the figure. The figure grows to fit it, so the plot keeps its size.                                                                                                               |
| `--caption`            | `TEXT`                 | —       | A caption on the figure.                                                                                                                                                                     |
| `--title-size`         | `PX`                   | —       | Size of the `--title` text, 8–48 px (default: 20).                                                                                                                                           |
| `--caption-size`       | `PX`                   | —       | Size of the `--caption` text, 6–36 px (default: 13).                                                                                                                                         |
| `--caption-color`      | `COLOR`                | —       | Color of the `--caption` text (default: #555555).                                                                                                                                            |

### Hover

| Option                    | Value    | Default | Description                                                                                   |
| ------------------------- | -------- | ------- | --------------------------------------------------------------------------------------------- |
| `--word-hover-fields`     | `FIELDS` | —       | Comma-separated Words table columns shown on hover (e.g. text,word_id,gpt2_surprisal).        |
| `--fixation-hover-fields` | `FIELDS` | —       | Comma-separated Fixations table columns shown on hover (e.g. order_in_trial,duration_ms,eye). |
| `--word-hover-measure`    | `FIELD`  | —       | The reading measure a word's hover shows (default: total_fixation_duration_ms; '' for none).  |

### Legends

| Option                      | Value  | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --------------------------- | ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-highlight-legend`     | switch | —       | Hide the Text highlight legend, which names the highlighted words. The words stay marked. `--legend` highlight=SPEC places it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `--no-color-legend`         | switch | —       | Hide the Fixation colors legend, which lists the categories of a categorical `--color-by` and the highlighted fixations. The markers still draw.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `--no-saccade-type-legend`  | switch | —       | With `--saccade-color-by-type`: hide the Saccade types legend. The colored lines still draw.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `--legend`                  | `SPEC` | —       | Place one legend. Repeatable. SPEC is KIND=POSITION[,ARRANGEMENT][,SIZE]. KIND is compare (Compare (A/B)), saccades (Saccade types), colors (Fixation colors), size-key (Fixation sizes) or highlight (Text highlight). POSITION is auto, or SPOT-outside or SPOT-inside, with SPOT one of top-left, top-center, top-right, left, right, bottom-left, bottom-center, bottom-right. Outside grows the figure, and left and right run down the side. ARRANGEMENT is stacked or side-by-side, and SIZE the text size in px. E.g. `--legend` saccades=right-outside,stacked,14. Each legend's switch still decides whether it is drawn. |
| `--no-duration-size-legend` | switch | —       | Hide the Fixation sizes legend, reference circles labeled in ms. It is drawn when `--marker-size-scale` is sqrt, linear or log.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

### Animate

| Option                | Value  | Default | Description                                                                                                                   |
| --------------------- | ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `--playback-speed`    | `X`    | `1.0`   | Animation speed multiplier for `--animate` (default: 1.0 = real time).                                                        |
| `--no-autoplay`       | switch | —       | With `--animate`: start the replay paused. By default the HTML file starts playing when it opens.                             |
| `--anim-grid-step-ms` | `MS`   | —       | With `--animate`: one frame per MS of reading time (default: 100). A smaller step is smoother and makes a larger file.        |
| `--anim-max-frames`   | `N`    | —       | With `--animate`: at most N frames (default: 360). A trial too long for that many at `--anim-grid-step-ms` gets a wider step. |

### Size and export

| Option                  | Value                   | Default | Description                                                                                                                                                                                                                                                       |
| ----------------------- | ----------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--width`               | `PX`                    | —       | Image width in px for PNG, SVG and PDF (default: the figure's size). Use with `--height` for fixed-size thumbnails.                                                                                                                                               |
| `--height`              | `PX`                    | —       | Image height in px for PNG, SVG and PDF (default: the figure's size).                                                                                                                                                                                             |
| `--scale`               | `X`                     | `2.0`   | Pixel-density multiplier for PNG, SVG and PDF (default: 2.0).                                                                                                                                                                                                     |
| `--width-mm`            | `MM`                    | —       | Print width of a PNG in mm, drawn at `--dpi` (replaces `--scale`).                                                                                                                                                                                                |
| `--width-in`            | `IN`                    | —       | Print width of a PNG in inches, drawn at `--dpi`.                                                                                                                                                                                                                 |
| `--dpi`                 | `N`                     | —       | Resolution of `--width-mm` / `--width-in` (default: 300).                                                                                                                                                                                                         |
| `--separable-layers`    | switch                  | —       | Also write one file per layer (word boxes, fixations, saccades, heatmap, labels, stimulus image) to a `&lt;output&gt;_layers/` folder, to restyle each in Illustrator or Inkscape. The layers line up when stacked. Static image output only: .svg, .pdf or .png. |
| `--print-code`          | `python`, `cli`, `both` | —       | Print the Python or CLI code that reproduces this figure (python, cli or both), then render as usual. The code sets only the options that differ from the defaults.                                                                                               |
| `--print-code-explicit` | switch                  | —       | With `--print-code`: write every figure option, including the ones at their defaults.                                                                                                                                                                             |

### Compare

| Option                                   | Value                                | Default     | Description                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------------- | ------------------------------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--compare-with`                         | `PARTICIPANT:TRIAL`                  | —           | The second scanpath, B, as PARTICIPANT:TRIAL. It comes from the loaded dataset unless `--compare-words` / `--compare-fixations` load a second one.                                                                                                                                                                                        |
| `--compare-screen`                       | `SCREEN_ID`                          | —           | B's screen in a multipart trial, looked up in B's trial (default: its first screen). `--screen` picks A's. Each scanpath is drawn from one screen.                                                                                                                                                                                        |
| `--compare-layout`                       | `overlay`, `side-by-side`, `stacked` | `overlay`   | How A and B are arranged (default: overlay). Across two datasets, overlay needs canvases of the same size. Different canvases are refused, so use side-by-side or stacked for them. Matching canvases that a dataset did not record still overlay, with a warning.                                                                        |
| `--compare-stimulus`                     | `both`, `a`, `b`                     | `both`      | On an overlay, whose word boxes and text to draw (default: both). Two datasets' word boxes line up only when the text is the same.                                                                                                                                                                                                        |
| `--label-a`                              | `TEXT`                               | —           | Name of scanpath A in the legend and hovers. Used by the comparison and by `--animate`. Needs `--label-b`.                                                                                                                                                                                                                                |
| `--label-b`                              | `TEXT`                               | —           | Name of scanpath B in the legend and hovers. Needs `--label-a`.                                                                                                                                                                                                                                                                           |
| `--compare-legend` `--no-compare-legend` | switch                               | —           | Draw the Compare (A/B) legend, which names the two scanpaths. On by default; `--no-compare-legend` hides it. Also applies to `--animate`.                                                                                                                                                                                                 |
| `--style-a`                              | `SPEC`                               | —           | Style for scanpath A, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid |
| `--style-b`                              | `SPEC`                               | —           | Style for scanpath B, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid |
| `--compare-fixation-flag`                | `SPEC`                               | —           | Filters & highlights for scanpath B only. Repeatable. Same SPEC as `--fixation-flag`, e.g. `--compare-fixation-flag` short=hide,threshold_ms=80. Replaces `--fixation-flag` for B.                                                                                                                                                        |
| `--compare-saccade-classes`              | `CLASSES`                            | —           | The saccade types scanpath B draws, comma-separated, named as in `--saccade-classes`. Replaces `--saccade-classes` for B. Not with `--animate`, which draws every type.                                                                                                                                                                   |
| `--compare-fix-index-range`              | `START:END`                          | —           | Draw only fixations START to END of scanpath B, counting from 1, both included. Replaces `--fix-index-range` for B.                                                                                                                                                                                                                       |
| `--stimulus-image-b`                     | `PATH`                               | —           | Scanpath B's stimulus image, for a side-by-side or stacked comparison across two datasets, where each panel draws its image. Sized and placed like `--stimulus-image`.                                                                                                                                                                    |
| `--stimulus-image-size-b`                | `WxH`                                | —           | Size of `--stimulus-image-b` in px (default: the PNG's pixel size, else `--compare-canvas`, else `--canvas`).                                                                                                                                                                                                                             |
| `--stimulus-image-origin-b`              | `X,Y`                                | —           | Top-left corner of `--stimulus-image-b` in B's screen px (default: 0,0).                                                                                                                                                                                                                                                                  |
| `--compare-words`                        | `PATH [PATH ...]`                    | —           | The Words table for a second dataset, B's. Same formats and globbing as `--words`.                                                                                                                                                                                                                                                        |
| `--compare-fixations`                    | `PATH [PATH ...]`                    | —           | The Fixations table for a second dataset, B's. Same formats and globbing as `--fixations`.                                                                                                                                                                                                                                                |
| `--compare-raw-gaze`                     | `PATH [PATH ...]`                    | —           | The Raw gaze table for the second dataset, drawn under B's scanpath. Same formats as `--raw-gaze`. With no second dataset, `--raw-gaze` already covers both scanpaths.                                                                                                                                                                    |
| `--compare-dataset-name`                 | `NAME`                               | `Dataset B` | Name of the second dataset, used in the trace names (default: 'Dataset B').                                                                                                                                                                                                                                                               |
| `--compare-canvas`                       | `WxH`                                | —           | The second dataset's screen size in px, e.g. 1680x1050. Estimated from its data when left out. An overlay, or `--animate` with both scanpaths, checks it against `--canvas`.                                                                                                                                                              |

## corpus

`corpus` renders a styled corpus figure from a tidy CSV you already have, as plot_corpus_figure does. For `--kind profile` the CSV needs `word_id` and `value` columns.

```
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

| Option              | Value                                   | Default   | Description                                                                                                                                           |
| ------------------- | --------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--input`           | `PATH`                                  | required  | The CSV. profile reads word_id and the value column, plus optional lo and hi; distribution reads the value column; difference reads word_id and diff. |
| `--kind`            | `profile`, `distribution`, `difference` | required  | A per-word profile, a distribution, or a difference profile.                                                                                          |
| `-o` `--output`     | `PATH`                                  | required  | Output file; any extension save_figure writes (.html, .png, .svg, .pdf).                                                                              |
| `--measure-label`   | `MEASURE_LABEL`                         | `Value`   | Axis and legend label for the value (default: Value).                                                                                                 |
| `--series-col`      | `SERIES_COL`                            | `series`  | Column naming the overlaid series, when present (default: series).                                                                                    |
| `--value-col`       | `VALUE_COL`                             | `value`   | The value column (default: value).                                                                                                                    |
| `--primary-color`   | `PRIMARY_COLOR`                         | `#1f77b4` | First series color (default: #1f77b4).                                                                                                                |
| `--secondary-color` | `SECONDARY_COLOR`                       | `#e45756` | Second series color (default: #e45756).                                                                                                               |

## check

`check` runs the **Data Management** page's **Data checks** on your tables without opening the app. It looks for:

- fixations lasting 0 ms or less, or with an infinite duration or onset;
- fixations and raw gaze samples with no finite position, or one more than a million pixels off the screen;
- word boxes with no area, or no finite position or size within a million pixels;
- screen sizes that are not finite and positive.

Each finding gives the rows and trials affected, a few example rows, and what the app does with them. `check` changes nothing and exits 0 whatever it finds. `--json` prints the table check_data_health returns.

```
scanpath-studio check --words ia.csv --fixations fixations.csv
scanpath-studio check --raw-gaze gaze_samples.csv --json
```

| Option                   | Value                 | Default | Description                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------ | --------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--sample`               | switch                | —       | Check the bundled demo instead of your own tables.                                                                                                                                                                                                                                                                                                                  |
| `--words`                | `PATH [PATH ...]`     | —       | Words table(s), as for render.                                                                                                                                                                                                                                                                                                                                      |
| `--fixations`            | `PATH [PATH ...]`     | —       | Fixations table(s), as for render.                                                                                                                                                                                                                                                                                                                                  |
| `--raw-gaze`             | `PATH [PATH ...]`     | —       | The Raw gaze table, as for render.                                                                                                                                                                                                                                                                                                                                  |
| `--raw-gaze-schema`      | `JSON`                | —       | Column mapping for the `--raw-gaze` table, replacing auto-detection, in the form `--fix-schema` takes.                                                                                                                                                                                                                                                              |
| `--trial-parts-manifest` | `PATH`                | —       | JSON manifest assigning source rows to ordered screens.                                                                                                                                                                                                                                                                                                             |
| `--json`                 | switch                | —       | Print the findings as JSON (the rows api.check_data_health returns).                                                                                                                                                                                                                                                                                                |
| `--word-schema`          | `JSON`                | —       | Column mapping for the `--words` table, replacing auto-detection. A JSON object from each field to a column name, or the path of a JSON file holding one, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}'. It is the dict api.load_scanpath_data takes. Needed only when a column isn't recognized, and the error then prints a mapping to start from.     |
| `--fix-schema`           | `JSON`                | —       | Column mapping for the `--fixations` table, replacing auto-detection. A JSON object from each field to a column name, or the path of a JSON file holding one, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}'. It is the dict api.load_scanpath_data takes. Needed only when a column isn't recognized, and the error then prints a mapping to start from. |
| `--keep-columns`         | `COLUMN [COLUMN ...]` | —       | More columns to keep through loading, under the names they have in your files (e.g. a pupil size), from whichever table has them. Without it, loading keeps only the mapped and recognized fields. A kept fixation column can be used by `--color-by`, an axis or a hover. Same as keep_columns= in api.load_scanpath_data.                                         |

## cache

A local or desktop run saves your session on your computer, so a refresh or a restart resumes where you left off. It saves uploaded datasets, column mappings, view settings, saved designs, metadata tables and annotations. `cache` shows what is stored and can delete it.

```
scanpath-studio cache            # datasets, rows, size, folder, last written
scanpath-studio cache --path     # just the folder
scanpath-studio cache --json     # the same status as JSON
scanpath-studio cache --clear    # delete the recovery cache
```

| Option    | Value  | Default | Description                      |
| --------- | ------ | ------- | -------------------------------- |
| `--path`  | switch | —       | Print the cache folder and exit. |
| `--json`  | switch | —       | Print the status as JSON.        |
| `--clear` | switch | —       | Delete the recovery cache.       |

The same information is at the foot of the **Data Management** page, under **Saved on this computer**. A running app writes a new copy at its next change, so clear the cache with the app closed.

| To                                       | Use                            |
| ---------------------------------------- | ------------------------------ |
| turn caching off for one launch          | `scanpath-studio --no-persist` |
| turn it off wherever the variable is set | `SCANPATH_STUDIO_PERSIST=0`    |
| move the folder                          | `SCANPATH_STUDIO_STATE_DIR`    |

Hosted deployments do not cache by default.

## version

`version` says which build this is and how it was installed. `--check` also asks GitHub whether a newer release is out and says how to update your install. Only `--check` uses the network.

```
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

| Option      | Value     | Default | Description                                                           |
| ----------- | --------- | ------- | --------------------------------------------------------------------- |
| `--check`   | switch    | —       | Ask GitHub for the latest release and say how to update this install. |
| `--timeout` | `SECONDS` | `5.0`   | How long to wait for GitHub, in seconds (default: 5).                 |

Between releases the version names the build: `0.35.0.post3+g8f18219` is three commits after 0.35.0, at commit `8f18219`. The same check is **Help → About → Check for updates** in the app, and check_for_updates in Python.
