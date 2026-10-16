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

Each command takes `--help`, and `scanpath-studio --version` prints the version. A word that is not a command is an error naming the closest one, rather than an argument passed on to Streamlit.

## Launch the app

```
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
scanpath-studio --download-dir D:\corpora  # where ⬇ Download saves public datasets
```

`scanpath-studio run …` is the same. Any other launch flag is passed on to `streamlit run`.

The app listens on this computer only (`127.0.0.1`). It has no login, so serving it to other machines is a deliberate step. Pass `--server.address 0.0.0.0` (or set `server.address` in a Streamlit `config.toml`, or `STREAMLIT_SERVER_ADDRESS`), and only on a network you trust:

```
scanpath-studio --server.address 0.0.0.0
```

Served on a network, the app also turns off everything that reads or writes the server's own folders, since any visitor could use them: the *Data directory* box, the folder picker, and ⬇ Download for the public corpora and stimulus-image folders. On a lab server you trust, turn them back on with `SCANPATH_LOCAL_FS=1` (`SCANPATH_LOCAL_FS=1 scanpath-studio --server.address 0.0.0.0`).

## render

`render` writes one trial to a file without opening the app. The extension picks the format: `.html` is interactive and needs nothing else, while `.png`, `.svg` and `.pdf` need Chrome, Chromium or Edge (or run `plotly_get_chrome -y` once; see the [FAQ](https://lacclab.github.io/scanpath-studio/faq/#export-fails)). The figure is the app's Scanpath design unless a flag changes it, and every [figure option](https://lacclab.github.io/scanpath-studio/figure-options/index.md) has a flag.

```
# The trials there are to pick from
scanpath-studio render --sample --list-trials

# The bundled demo
scanpath-studio render --sample -o scanpath.html

# Your own data (replace p1 / t3 with ids from --list-trials)
scanpath-studio render \
  --words ia.csv --fixations fixations.csv \
  --participant p1 --trial t3 --output scanpath.svg

# An authoring file saved from the app's Author a scanpath screen
scanpath-studio render --authoring authored-scanpath.json -o authored.html

# A public corpus, loaded the way the app loads it (PoTeC downloads on first use)
scanpath-studio render --potec ./potec --list-trials
scanpath-studio render --onestop ./onestop --onestop-variant public \
  --onestop-regime ordinary --onestop-part Paragraph --list-trials
```

The Python API loads the same corpora with load_potec and load_onestop.

### Common tasks

| Goal                       | Flags                                                                                                                                                                                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| add a layer                | `--word-boxes`, `--fixation-index`, `--heatmap`                                                                                                                                                                                               |
| hide a layer               | `--no-text`, `--no-fixations`, `--no-saccades`                                                                                                                                                                                                |
| animate                    | `--animate`, optionally `--playback-speed X`. Every styling flag the replay can draw is honored; the rest are named in a warning                                                                                                              |
| set the display geometry   | `--canvas WIDTHxHEIGHT`. `--crop-to-data` frames the data instead of the whole monitor, with `--crop-margin PX` around it (default: 5% of its extent, at least 20 px)                                                                         |
| color fixations            | `--color-by FIELD`, including a column of your own once `--keep-columns COLUMN…` carries it through loading                                                                                                                                   |
| size fixations by duration | `--marker-size-scale sqrt\|linear\|log\|relative` (default `sqrt`), `--marker-duration-range LO HI` (ms, default `50 600`), `--marker-size-range MIN MAX` (px), `--no-duration-size-legend`                                                   |
| draw only part of a trial  | `--fix-index-range START:END` (1-based, both inclusive; `--animate` and `--compare-with` honor it too)                                                                                                                                        |
| draw the stimulus          | `--stimulus-image PATH` for one image. `--show-stimulus-image` draws each trial's own page, the `image_path` its rows carry (`--sample` ships its pages). `--image-root DIR --image-pattern '{text_id}.png'` fills `image_path` from a folder |
| smooth the heatmap         | `--heatmap-style interpolated --heatmap-sigma 20` (σ in px; leave it out for an automatic σ)                                                                                                                                                  |
| style the word boxes       | `--word-box-color`, `--word-box-line-opacity`, `--word-box-fill-color`, `--word-box-fill-opacity` (0 draws outlines only, or fill only)                                                                                                       |
| size the figure            | `--width`, `--height`, `--scale`. For print, `--width-mm MM` or `--width-in IN` with `--dpi N` (default 300)                                                                                                                                  |
| title and caption it       | `--title`, `--caption`                                                                                                                                                                                                                        |
| export editable layers     | `--separable-layers`                                                                                                                                                                                                                          |
| print the equivalent code  | `--print-code python` (or `cli` / `both`), plus `--print-code-explicit`                                                                                                                                                                       |

### Compare two scanpaths

`--compare-with PARTICIPANT:TRIAL` draws a second trial, B, beside or over the first. It is the headless form of the app's **Compare** mode.

```
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

| Goal                                         | Flags                                                                                                                |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| pick B                                       | `--compare-with PARTICIPANT:TRIAL`                                                                                   |
| pick each screen of a multipart trial        | `--screen ID` (A), `--compare-screen ID` (B); each defaults to its trial's first screen                              |
| arrange the panels                           | `--compare-layout {overlay,side-by-side,stacked}` (default `overlay`)                                                |
| choose whose stimulus an overlay draws       | `--compare-stimulus {both,a,b}` (default `both`)                                                                     |
| name the two scanpaths                       | `--label-a TEXT --label-b TEXT` (both or neither)                                                                    |
| style each scanpath                          | `--style-a SPEC`, `--style-b SPEC` ([keys below](#style-keys))                                                       |
| leave out the A/B legend                     | `--no-compare-legend`                                                                                                |
| give B its own stimulus page (split layouts) | `--stimulus-image-b PATH`, with `--stimulus-image-size-b WxH` / `--stimulus-image-origin-b X,Y`                      |
| take B from another dataset                  | `--compare-words PATH… --compare-fixations PATH…`, plus `--compare-raw-gaze PATH…` and `--compare-dataset-name NAME` |
| declare the screens                          | `--canvas WxH`, `--compare-canvas WxH`                                                                               |
| replay both on one clock                     | add `--animate` (HTML output)                                                                                        |

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

- `--compare-with` cannot be combined with `--all-screens` or `--screens`. A comparison is one figure of two trials, each drawn from one screen. B's `--compare-screen` is looked up in B's own trial, so it can be a later page, or a page of the second dataset.
- **An overlay of two datasets needs matching canvases.** On two different canvases, `--compare-layout overlay` fails rather than falling back, and so does `--animate`, which replays both scanpaths in one coordinate space. Use `--compare-layout side-by-side` or `stacked`, without `--animate`. Two screens of one dataset whose canvases differ are refused the same way. Nothing is rescaled.
- Without `--compare-canvas`, the second dataset's screen is read off its data, as A's is when neither `--canvas` nor a built-in source gives one. That extent rarely spans the whole screen, so state both screens when you know them.
- A second dataset is loaded from **files only**. Any corpus you can load in Python can still be B through compare_scanpaths, which takes B's frames directly.

### Raw gaze

`--raw-gaze PATH…` reads a third table, with its columns auto-detected like `--fixations`, and draws the plotted trial's samples under the fixations. With `--compare-with` it covers both scanpaths, each in its own color, and `--compare-raw-gaze PATH…` is B's when B comes from another dataset. `--animate` ignores it with a warning.

```
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
  --sample-raw-gaze --raw-gaze-opacity 0.4 -o raw_gaze.html
```

On its own, with no other input, `--raw-gaze` is the dataset: `--list-trials` lists its trials and `render` draws the chosen trial's samples as recorded. No fixations are detected from them, so `--animate` and `--compare-with` exit with that reason instead.

```
scanpath-studio render --raw-gaze gaze_samples.csv --list-trials
scanpath-studio render --raw-gaze gaze_samples.csv -t t3 -o samples.png
```

### Multipart trials and many trials

`render` writes one trial per run. For many figures, use the [Python batch recipe](https://lacclab.github.io/scanpath-studio/guides/exporting/#batch-pattern) or the app's **Export → Export bundle**.

A multipart trial is the exception. `--all-screens` writes one `__screen-001-<id>` file per screen of the selected trial, and `--screens Title,Paragraph` writes only the screens named, each still numbered by its place in the trial. `--trial-parts-manifest manifest.json` assigns arbitrary source rows to screens.

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

Every `render` flag, generated from the parser the command uses, so the defaults and help are the ones `--help` prints. The figure flags are grouped like the [figure options](https://lacclab.github.io/scanpath-studio/figure-options/index.md) they set.

### Trial and output

| Option                | Value                 | Default   | Description                                                                                                                              |
| --------------------- | --------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `-p` `--participant`  | `PARTICIPANT`         | —         | Participant id (default: first available).                                                                                               |
| `-t` `--trial`        | `TRIAL`               | —         | Trial id (default: first for the participant).                                                                                           |
| `--screen`            | `SCREEN`              | —         | Screen/part id inside a multipart trial (default: first screen).                                                                         |
| `--list-trials`       | switch                | —         | Print every trial (participant, trial and text id) and exit; pass the trial id to -t.                                                    |
| `--list-parts`        | switch                | —         | Print ordered multipart screens, optionally narrowed by -p/-t, and exit.                                                                 |
| `--all-screens`       | switch                | —         | Render every screen of the selected parent trial. Screen ids are inserted before the output extension.                                   |
| `--screens`           | `ID[,ID...]`          | —         | Like `--all-screens`, but only these screens of the parent trial (comma-separated screen ids, e.g. Title,Paragraph); see `--list-parts`. |
| `--screen-transition` | `instant`, `recorded` | `instant` | For `--all-screens` `--animate`, record zero or observed inter-screen delay in each output's metadata (default: instant).                |
| `-o` `--output`       | `PATH`                | —         | Output file; format from extension (.html/.png/.svg/.pdf).                                                                               |
| `--animate`           | switch                | —         | Render the animated replay instead of the static figure (HTML only).                                                                     |

### Input

| Option                                                                 | Value                                                                              | Default         | Description                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--sample`                                                             | switch                                                                             | —               | Use the bundled OneStop demo: 2 participants, 12 trials each (`--list-trials` shows them).                                                                                                                                                                                                                                                                      |
| `--authoring`                                                          | `PATH`                                                                             | —               | An authoring file from the app's Author a scanpath screen.                                                                                                                                                                                                                                                                                                      |
| `--words`                                                              | `PATH [PATH ...]`                                                                  | —               | Words table(s) (csv/tsv/txt/tab/parquet/feather/xlsx/xls, or a .zip of them); columns are auto-detected from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and snake_case names. Multiple paths or a quoted glob pattern concatenate multi-file datasets.                                                                                                          |
| `--fixations`                                                          | `PATH [PATH ...]`                                                                  | —               | Fixations table(s) (csv/tsv/txt/tab/parquet/feather/xlsx/xls, or a .zip of them), auto-detected like `--words`. Multiple paths or a quoted glob pattern concatenate multi-file datasets (e.g. one file per participant).                                                                                                                                        |
| `--image-root`                                                         | `DIR`                                                                              | —               | Local stimulus-image folder. Files are matched per row using `--image-pattern` and fill its image_path; add `--show-stimulus-image` to draw them. Works with every input, `--sample` and the corpora included.                                                                                                                                                  |
| `--image-pattern`                                                      | `PATTERN`                                                                          | `{text_id}.png` | Relative filename pattern with row placeholders, for example '{text_id}.png' or '{participant_id}/{trial_id}.png'.                                                                                                                                                                                                                                              |
| `--trial-parts-manifest`                                               | `PATH`                                                                             | —               | JSON manifest that assigns arbitrary source rows to ordered screens inside each logical trial. Use with `--words`/`--fixations` when the source tables have no explicit screen columns.                                                                                                                                                                         |
| `--word-schema`                                                        | `JSON`                                                                             | —               | Column mapping for the `--words` table, replacing auto-detection: a JSON object (or a path to a .json file holding one) from each field to a column name, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}' — the same dict api.load_scanpath_data takes. Needed only when a column isn't recognized; the error then prints a mapping to start from.     |
| `--fix-schema`                                                         | `JSON`                                                                             | —               | Column mapping for the `--fixations` table, replacing auto-detection: a JSON object (or a path to a .json file holding one) from each field to a column name, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}' — the same dict api.load_scanpath_data takes. Needed only when a column isn't recognized; the error then prints a mapping to start from. |
| `--keep-columns`                                                       | `COLUMN [COLUMN ...]`                                                              | —               | Further columns of your own to carry through loading under their own names (e.g. a pupil size), from whichever table has them — otherwise loading keeps only the mapped and recognized fields. A kept fixation column can then be `--color-by`, an axis or a hover field. The keep_columns= of api.load_scanpath_data.                                          |
| `--potec`                                                              | `DIR`                                                                              | —               | Load the PoTeC corpus (DiLi-Lab/PoTeC) from DIR, downloading the needed files (~45 MB) on first use. Participants are the corpus's 75 ids (sparse within 0–105; `--list-trials` shows them); a trial is one participant reading one text, <participant>\_<text> (0_b0), with texts b0–b5 and p0–p5.                                                             |
| `--onestop`                                                            | `DIR`                                                                              | —               | Load the OneStop corpus from DIR. For the public variant the chosen regime + parts' reports are downloaded from OSF on first use (tens–hundreds MB each); the lacclab variant reads a local export. Tune with `--onestop-regime` / `--onestop-part` / `--onestop-variant`.                                                                                      |
| `--onestop-regime`                                                     | `ordinary`, `information_seeking`, `repeated`, `information_seeking_repeated`      | `ordinary`      | OneStop reading regime for `--onestop` (default: ordinary).                                                                                                                                                                                                                                                                                                     |
| `--onestop-part`                                                       | `Title`, `Question_Preview`, `Paragraph`, `Questions`, `Answers`, `QA`, `Feedback` | —               | OneStop trial part(s) for `--onestop`; repeatable (default: Paragraph). Loading several makes each part its own trial.                                                                                                                                                                                                                                          |
| `--onestop-variant`                                                    | `public`, `lacclab`                                                                | `public`        | OneStop source variant for `--onestop`: 'public' (OSF download) or 'lacclab' (a local lab-processed export; no download).                                                                                                                                                                                                                                       |
| `--participant-metadata`                                               | `FILE [FILE ...]`                                                                  | —               | Participant-level metadata table: one row per participant, an id column plus anything known about them. Several files (or a glob) are stacked into one table. The join is validated and reported against the loaded participants, and the fields are added to `--list-trials` output.                                                                           |
| `--trial-metadata`                                                     | `FILE [FILE ...]`                                                                  | —               | Trial-level metadata table: one row per trial, a trial-id column plus anything known about it. Several files (or a glob) are stacked into one table. Validated and reported the same way, and its fields are added to `--list-trials` output.                                                                                                                   |
| `--trial-metadata-participant-column` `--trial-metadata-reader-column` | `COLUMN`                                                                           | —               | Key the `--trial-metadata` table by participant AND trial, using this column as the participant id. Without it the table is keyed by trial id alone: a row describes a text, and every trial of it inherits that row. Never inferred: nothing in the file says which of the two a corpus means.                                                                 |
| `--text-metadata`                                                      | `FILE [FILE ...]`                                                                  | —               | Text-level metadata table: one row per text, a text-id column plus anything known about it. Several files (or a glob) are stacked into one table. Validated and reported the same way, and its fields are added to `--list-trials` output. Never keyed by participant: a text is a stimulus, not something one participant owns.                                |

### Fixations

| Option                             | Value                                                                                  | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------- | -------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-fixations`                   | switch                                                                                 | —       | Hide fixation markers.                                                                                                                                                                                                                                                                                                                                                                                                              |
| `--fixation-index`                 | switch                                                                                 | —       | Number the fixations in reading order.                                                                                                                                                                                                                                                                                                                                                                                              |
| `--no-fixation-index` `--no-order` | switch                                                                                 | —       | Hide the fixation numbers (the default).                                                                                                                                                                                                                                                                                                                                                                                            |
| `--fix-index-range`                | `START:END`                                                                            | —       | Draw only fixations START through END of the trial (1-based, both inclusive), e.g. `--fix-index-range` 1:40. Honored by `--animate` too, which then replays only that window, and by `--compare-with`, which windows both scanpaths (unless `--compare-fix-index-range` gives B its own).                                                                                                                                           |
| `--fixation-flag`                  | `SPEC`                                                                                 | —       | The app's Filters & highlights for fixations, repeatable. SPEC is CATEGORY=MODE[,threshold_ms=N][,symbol=S][,color=#RRGGBB] with CATEGORY one of short, long, oob (outside every word box), blink and MODE one of off, highlight, discard — e.g. `--fixation-flag` short=discard,threshold_ms=80. discard drops those fixations from the drawing only; measures and exports are untouched. threshold_ms applies to short/long only. |
| `--snap-fixations`                 | switch                                                                                 | —       | Move each fixation up or down onto its text line (its word's, else the nearest); it keeps its x. `--snap-position` says where on the line.                                                                                                                                                                                                                                                                                          |
| `--snap-position`                  | `LINES`                                                                                | —       | Where on its line a snapped fixation sits, in line heights from the line's middle: 0 centers it, -0.5 is the top edge, 0.5 the bottom edge (default: -0.5). Used with `--snap-fixations`.                                                                                                                                                                                                                                           |
| `--palette`                        | `{default,print,high-contrast}`                                                        | —       | Color palette for the marks (the app's Palette): default (colorblind-safe, Okabe–Ito), print (grayscale, survives a B&W print) or high-contrast. The app's own names work too. Individual --\*-color flags override it.                                                                                                                                                                                                             |
| `--color-by`                       | `FIELD`                                                                                | —       | Fixation column to color by, e.g. duration_ms, or 'line' to color each fixation by its text line (same as `--color-by-line`). Default: '(uniform)', one flat color, since marker size already shows duration.                                                                                                                                                                                                                       |
| `--fixation-color`                 | `COLOR`                                                                                | —       | Flat fixation marker color used when `--color-by` is (uniform) (default: #0072B2).                                                                                                                                                                                                                                                                                                                                                  |
| `--fixation-symbol`                | `circle`, `square`, `diamond`, `triangle-up`, `cross`, `x`, `star`, `hexagon`, `heart` | —       | Fixation marker shape. Unlike color, shape survives a grayscale print (default: circle).                                                                                                                                                                                                                                                                                                                                            |
| `--fixation-colorscale`            | `NAME`                                                                                 | —       | Color scale for `--color-by`, e.g. Viridis (default: Blues).                                                                                                                                                                                                                                                                                                                                                                        |
| `--marker-size-range`              | `MIN MAX`                                                                              | —       | Min/max fixation marker size in px, e.g. 4 12 (default: 8 24). Smaller ranges suit small thumbnails.                                                                                                                                                                                                                                                                                                                                |
| `--marker-size-scale`              | `sqrt`, `linear`, `log`, `relative`                                                    | —       | How duration sets marker size (default: sqrt). sqrt / linear / log map `--marker-duration-range` onto `--marker-size-range` the same way for every figure, so one duration is one size across trials, comparisons and replays; sqrt makes marker area grow with duration. relative stretches each figure from its own shortest to longest fixation.                                                                                 |
| `--marker-duration-range`          | `LO HI`                                                                                | —       | Durations in ms given the smallest and largest marker on a fixed scale (default: 50 600). Shorter and longer fixations clamp to them.                                                                                                                                                                                                                                                                                               |
| `--fixation-opacity`               | `O`                                                                                    | —       | Fixation marker opacity, 0.1–1.0 (default: 0.7, so overlapping fixations show through).                                                                                                                                                                                                                                                                                                                                             |
| `--fixation-outline-width`         | `PX`                                                                                   | —       | Outline round each filled fixation marker, 0–5 px; 0 draws none (default: 0.5).                                                                                                                                                                                                                                                                                                                                                     |
| `--fixation-outline-color`         | `COLOR`                                                                                | —       | Color of that outline (default: #111111).                                                                                                                                                                                                                                                                                                                                                                                           |
| `--hollow-fixations`               | switch                                                                                 | —       | Draw the fixations as outlines instead of filled markers.                                                                                                                                                                                                                                                                                                                                                                           |
| `--color-by-line`                  | switch                                                                                 | —       | Color each fixation by the text line it lands on (lines inferred from the word boxes); overrides `--color-by`. Same as `--color-by` line.                                                                                                                                                                                                                                                                                           |
| `--fixation-color-range`           | `LO HI`                                                                                | —       | Pin the `--color-by` color scale to LO..HI instead of the trial's own range, so several figures share one scale.                                                                                                                                                                                                                                                                                                                    |
| `--order-font-size`                | `PX`                                                                                   | —       | Fixation index label size (default: 10).                                                                                                                                                                                                                                                                                                                                                                                            |
| `--order-font-color`               | `COLOR`                                                                                | —       | Fixation index label color (default: #111111).                                                                                                                                                                                                                                                                                                                                                                                      |

### Saccades

| Option                         | Value                             | Default | Description                                                                                                                                                                                                                                                                                                            |
| ------------------------------ | --------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-saccades`                | switch                            | —       | Hide saccade lines.                                                                                                                                                                                                                                                                                                    |
| `--saccade-arrows`             | switch                            | —       | Draw saccade direction arrowheads.                                                                                                                                                                                                                                                                                     |
| `--saccade-color`              | `COLOR`                           | —       | Saccade line/arrow color, hex or CSS name (default: #CC79A7).                                                                                                                                                                                                                                                          |
| `--saccade-style`              | `solid`, `dash`, `dot`, `dashdot` | —       | Saccade line dash style (default: solid).                                                                                                                                                                                                                                                                              |
| `--saccade-width`              | `PX`                              | —       | Saccade line width in px, 0.5–10 (default: 2).                                                                                                                                                                                                                                                                         |
| `--saccade-opacity`            | `O`                               | —       | Opacity of the saccade lines and direction arrows, 0.1–1.0 (default: 1). A comparison's two scanpaths share it.                                                                                                                                                                                                        |
| `--saccade-arrow-size`         | `PX`                              | —       | Size of the `--saccade-arrows` arrowheads, 4–40 px (default: 12).                                                                                                                                                                                                                                                      |
| `--saccade-color-by-type`      | switch                            | —       | Color each saccade by its reading type (forward / skip / refixation / return sweep / regression) instead of one uniform color.                                                                                                                                                                                         |
| `--saccade-color-by-direction` | switch                            | —       | Color saccades forward vs. regression only — the two-way split between one uniform color and the full `--saccade-color-by-type` breakdown.                                                                                                                                                                             |
| `--saccade-type-color`         | `CLASS=COLOR`                     | —       | Override a reading-type color, e.g. `--saccade-type-color` regression=#000000 (repeatable; classes: forward, skip, refixation, return_sweep, regression). Implies `--saccade-color-by-type`, unless `--saccade-color-by-direction` is given — then it recolors that two-way split (its forward and regression colors). |
| `--saccade-classes`            | `CLASSES`                         | —       | Draw only these reading classes, comma-separated, e.g. `--saccade-classes` regression,return_sweep (classes: forward, skip, refixation, return_sweep, regression, other). Hidden classes lose their line and their direction arrow. Default: all.                                                                      |
| `--saccade-arcs`               | switch                            | —       | Draw saccades as upward arcs (the linear-reading diagram) instead of straight connectors.                                                                                                                                                                                                                              |

### Text and stimulus

| Option                     | Value                              | Default | Description                                                                                                                                                                                                                                  |
| -------------------------- | ---------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-text` `--no-labels`  | switch                             | —       | Hide the reading text.                                                                                                                                                                                                                       |
| `--highlight-column`       | `COLUMN`                           | —       | Boolean words column marking the text to highlight — the critical span (default: is_in_aspan, OneStop's answer span). Pass `--highlight-column` '' to highlight nothing. How it is drawn is `--critical-span-style`.                         |
| `--critical-span-style`    | `mark-text`, `mark-border`, `none` | —       | How the `--highlight-column` words are marked: mark-text recolors them, mark-border outlines their boxes, none draws neither (default: mark-text).                                                                                           |
| `--stimulus-image`         | `PATH`                             | —       | Draw an image (PNG/JPG) as the stimulus background under the scanpath. By default it's stretched to the image's own pixel size (PNG) or the canvas; set `--stimulus-image-size` / -origin to place a crop precisely in fixation coordinates. |
| `--stimulus-image-size`    | `WxH`                              | —       | Stimulus-image size in px, e.g. 1310x991 (default: the PNG's own pixel size, else the canvas). Use with `--stimulus-image`.                                                                                                                  |
| `--stimulus-image-origin`  | `X,Y`                              | —       | Top-left of the stimulus image in monitor px, e.g. 305,44 (default: 0,0). Use with `--stimulus-image` to align a centered crop to the fixation coordinates.                                                                                  |
| `--stimulus-image-opacity` | `O`                                | —       | Stimulus-image opacity 0.1–1.0 (default: 1.0 = opaque). Lower it to dim a busy image so the fixations / saccades / word boxes read over it.                                                                                                  |
| `--show-stimulus-image`    | switch                             | —       | Draw each trial's own stimulus page under the scanpath: the image_path its rows carry (from `--image-root`, or a dataset that ships its pages, like `--sample`), placed at its image_x / image_y. `--stimulus-image` PATH wins.              |
| `--text-color`             | `COLOR`                            | —       | Reading-text color (default: #000000).                                                                                                                                                                                                       |
| `--highlight-text-color`   | `COLOR`                            | —       | Color of the `--highlight-column` words under `--critical-span-style` mark-text (default: #D55E00).                                                                                                                                          |
| `--span-border-color`      | `COLOR`                            | —       | Box color under `--critical-span-style` mark-border (default: #000000).                                                                                                                                                                      |
| `--line-spacing`           | `N`                                | —       | How far apart the lines are, in font sizes: the reading text is the distance between lines ÷ N (default: 3, a blank line above and below).                                                                                                   |
| `--no-scale-text-to-boxes` | switch                             | —       | Draw the reading text at `--font-size` instead of sizing it from the word boxes.                                                                                                                                                             |
| `--font-size`              | `PX`                               | `16`    | Base figure font size (default: 16).                                                                                                                                                                                                         |
| `--font-family`            | `NAME`                             | —       | Font for all figure text (default: monospace).                                                                                                                                                                                               |

### Word boxes

| Option                         | Value   | Default | Description                                                                                                                         |
| ------------------------------ | ------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `--word-boxes`                 | switch  | —       | Draw the word boxes.                                                                                                                |
| `--no-word-boxes` `--no-words` | switch  | —       | Hide the word boxes (the default).                                                                                                  |
| `--word-box-color`             | `COLOR` | —       | Word-box outline color (default: #6c757d). A comparison outlines each scanpath's boxes in its own color instead.                    |
| `--word-box-line-opacity`      | `O`     | —       | Word-box outline opacity, 0–1; 0 draws the fill only (default: 1). Below 1 the outline color must be #rrggbb, #rgb or rgb(r, g, b). |
| `--word-box-fill-color`        | `COLOR` | —       | Word-box fill color, drawn at `--word-box-fill-opacity`: #rrggbb, #rgb or rgb(r, g, b) (default: #646464).                          |
| `--word-box-fill-opacity`      | `O`     | —       | Word-box fill opacity, 0–1; 0 draws outlines only (default: 0.05).                                                                  |

### Heatmap

| Option                 | Value                        | Default | Description                                                                                                                                 |
| ---------------------- | ---------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `--heatmap`            | switch                       | —       | Draw the heatmap.                                                                                                                           |
| `--no-heatmap`         | switch                       | —       | Hide the heatmap (the default).                                                                                                             |
| `--heatmap-metric`     | `COLUMN`                     | —       | Heatmap weighting: the fixation duration column — under your file's name or as duration_ms (the default) — or counts.                       |
| `--heatmap-style`      | `word-boxes`, `interpolated` | —       | Heatmap geometry (default: word-boxes).                                                                                                     |
| `--heatmap-sigma`      | `PX`                         | —       | Gaussian σ in px for `--heatmap-style` interpolated (default: 2% of the data's larger span, at least 8 px).                                 |
| `--heatmap-colorscale` | `NAME`                       | —       | Heatmap color scale, e.g. Greens (default: Blues).                                                                                          |
| `--heatmap-norm`       | `linear`, `log`              | —       | Heatmap color scaling: linear (default) or log — log compresses heavy-tailed dwell times so a few hot words don't wash out the rest.        |
| `--heatmap-opacity`    | `O`                          | —       | Heatmap opacity, 0.05–1.0 (default: each style's own — word boxes 0.5, or 0.35 with no word boxes; interpolated 0.45).                      |
| `--heatmap-range`      | `LO HI`                      | —       | Pin the heatmap's color scale to LO..HI instead of the trial's own range.                                                                   |
| `--word-heatmap-col`   | `COLUMN`                     | —       | For a words-only dataset (no fixations): tint each word box by this numeric words column — e.g. gpt2_surprisal — instead of its dwell time. |
| `--word-heatmap-title` | `TEXT`                       | —       | Color-bar title for `--word-heatmap-col` (default: Value).                                                                                  |

### Raw gaze

| Option                   | Value             | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------ | ----------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--raw-gaze`             | `PATH [PATH ...]` | —       | Raw (sample-level) gaze table(s) to draw under the fixations, columns auto-detected like `--fixations` (same formats; several paths or a quoted glob concatenate). Static figures and `--compare-with` comparisons, where each scanpath's samples take its color (not `--animate`). On its own (no other input) it is the dataset: its trials are listed and drawn as recorded — no fixations are detected from the samples. |
| `--no-raw-gaze`          | switch            | —       | Load the `--raw-gaze` table but hide its layer — the app's 🔵 Raw gaze switch turned off. With raw gaze as the only input the figure then draws no gaze.                                                                                                                                                                                                                                                                     |
| `--sample-raw-gaze`      | switch            | —       | With `--sample`: draw the bundled demo's raw gaze (synthesized, for one trial — the one the app overlays it on).                                                                                                                                                                                                                                                                                                             |
| `--raw-gaze-schema`      | `JSON`            | —       | Column mapping for the `--raw-gaze` table, replacing auto-detection (same shape as `--fix-schema`); needed only when a column isn't recognized.                                                                                                                                                                                                                                                                              |
| `--raw-gaze-color`       | `COLOR`           | —       | Raw-gaze sample color (default: #888888). A comparison draws each scanpath's samples in its own color instead.                                                                                                                                                                                                                                                                                                               |
| `--raw-gaze-marker-size` | `PX`              | —       | Raw-gaze sample size, 1–12 (default: 4).                                                                                                                                                                                                                                                                                                                                                                                     |
| `--raw-gaze-opacity`     | `O`               | —       | Raw-gaze sample opacity, 0.1–1.0 (default: 0.6).                                                                                                                                                                                                                                                                                                                                                                             |

### Legends and color bars

| Option                              | Value                    | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------------------------- | ------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--no-highlight-legend`             | switch                   | —       | Hide the note naming the highlighted words (the words stay marked). Shows by default; `--legend` highlight=SPEC places it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `--no-color-legend`                 | switch                   | —       | Hide the fixation-colour legend: the categories of a categorical `--color-by` and the highlighted fixations' entries (the markers still draw). Shows by default.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `--no-saccade-type-legend`          | switch                   | —       | With `--saccade-color-by-type`: hide the saccade-type color key on the figure (the colored lines still draw). Legend shows by default.                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `--legend`                          | `SPEC`                   | —       | Place one legend, repeatable. SPEC is KIND=POSITION[,ARRANGEMENT][,SIZE] with KIND one of compare, saccades, colors (the fixation colour categories), size-key, highlight (the highlighted-words note); POSITION auto or SPOT-outside / SPOT-inside with SPOT one of top-left, top-center, top-right, left, right, bottom-left, bottom-center, bottom-right (outside grows the figure; left and right run down the side); ARRANGEMENT stacked or side-by-side; SIZE the text size in px — e.g. `--legend` saccades=right-outside,stacked,14. Whether a legend is drawn at all is still its own switch. |
| `--no-duration-size-legend`         | switch                   | —       | Hide the duration-size key (reference circles labelled in ms) drawn on a fixed `--marker-size-scale`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `--no-fixation-colorbar`            | switch                   | —       | Leave out `--color-by`'s color bar.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `--fixation-colorbar-orientation`   | `vertical`, `horizontal` | —       | Fixation color bar: beside the plot (vertical, default) or below it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `--fixation-colorbar-tickangle`     | `DEG`                    | —       | Fixation color bar: tick-label angle, -90–90 (default: 0).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `--fixation-colorbar-tickfont-size` | `PX`                     | —       | Fixation color bar: tick-label size (default: 12).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `--fixation-colorbar-thickness`     | `PX`                     | —       | Fixation color bar: thickness, 4–40 px (default: 14).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `--fixation-colorbar-length`        | `F`                      | —       | Fixation color bar: length as a share of the plot's side, 0.1–1.0 (default: a third of its height upright, 0.6 of its width lying down).                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `--no-heatmap-colorbar`             | switch                   | —       | Leave out the heatmap's color bar.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `--heatmap-colorbar-orientation`    | `vertical`, `horizontal` | —       | Heatmap color bar: beside the plot (vertical, default) or below it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `--heatmap-colorbar-tickangle`      | `DEG`                    | —       | Heatmap color bar: tick-label angle, -90–90 (default: 0).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `--heatmap-colorbar-tickfont-size`  | `PX`                     | —       | Heatmap color bar: tick-label size (default: 12).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `--heatmap-colorbar-thickness`      | `PX`                     | —       | Heatmap color bar: thickness, 4–40 px (default: 14).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `--heatmap-colorbar-length`         | `F`                      | —       | Heatmap color bar: length as a share of the plot's side, 0.1–1.0 (default: a third of its height upright, 0.6 of its width lying down).                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

### Figure and canvas

| Option                               | Value   | Default | Description                                                                                                                                                       |
| ------------------------------------ | ------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--canvas`                           | `WxH`   | —       | Monitor size in px, e.g. 2560x1440 (default: the source's screen — 2560x1440 for `--sample`/`--onestop`, 1680x1050 for `--potec` — else estimated from the data). |
| `--coordinate-grid`                  | switch  | —       | Overlay a monitor-pixel X/Y grid on the scanpath.                                                                                                                 |
| `--coordinate-grid-spacing`          | `PX`    | —       | Pin the major coordinate-grid interval in pixels. Implies `--coordinate-grid`; omit for automatic 1/2/5×10ⁿ spacing.                                              |
| `--coordinate-grid-font-size`        | `PX`    | —       | Size of the coordinate grid's labels, 6–36 px (default: 18).                                                                                                      |
| `--background-color`                 | `COLOR` | —       | Plot background color (default: #ffffff).                                                                                                                         |
| `--no-plot-frame`                    | switch  | —       | Leave out the border round the plot area.                                                                                                                         |
| `--plot-frame-color`                 | `COLOR` | —       | Color of the border round the plot area (default: #000000).                                                                                                       |
| `--x-field`                          | `FIELD` | —       | Fixation column on the x axis (default: x). A non-spatial one draws a chart of the fixations instead of the scanpath.                                             |
| `--y-field`                          | `FIELD` | —       | Fixation column on the y axis (default: y).                                                                                                                       |
| `--crop-to-data` `--no-full-monitor` | switch  | —       | Frame the axes on the data instead of the whole `--canvas` monitor (the app's Crop to data).                                                                      |
| `--crop-margin`                      | `PX`    | —       | The margin around the data, in screen px, when cropping to it (default: 5% of the data's extent, at least 20 px). Implies `--crop-to-data`.                       |

### Title and caption

| Option            | Value   | Default | Description                                                                                                     |
| ----------------- | ------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| `--title`         | `TEXT`  | —       | Title band stamped on the figure; off by default. The figure grows to make room rather than shrinking the plot. |
| `--caption`       | `TEXT`  | —       | Caption band stamped on the figure; off by default.                                                             |
| `--title-size`    | `PX`    | —       | Size of the `--title` text, 8–48 px (default: 20).                                                              |
| `--caption-size`  | `PX`    | —       | Size of the `--caption` text, 6–36 px (default: 13).                                                            |
| `--caption-color` | `COLOR` | —       | Color of the `--caption` text (default: #555555).                                                               |

### Hover

| Option                    | Value    | Default | Description                                                                                  |
| ------------------------- | -------- | ------- | -------------------------------------------------------------------------------------------- |
| `--word-hover-fields`     | `FIELDS` | —       | Comma-separated word columns shown on hover (e.g. text,word_id,gpt2_surprisal).              |
| `--fixation-hover-fields` | `FIELDS` | —       | Comma-separated fixation columns shown on hover (e.g. order_in_trial,duration_ms,eye).       |
| `--word-hover-measure`    | `FIELD`  | —       | The reading measure a word's hover shows (default: total_fixation_duration_ms; '' for none). |

### Illustration

| Option                 | Value                  | Default | Description                                                                                                      |
| ---------------------- | ---------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| `--illustration`       | switch                 | —       | Apply the clean schematic preset: snapped fixations, arced saccades, uniform colors, and no analytical overlays. |
| `--illustration-label` | `auto`, `show`, `hide` | `auto`  | Auto-label transformed/schematic figures, force the label, or explicitly hide it (default: auto).                |
| `--illustration-text`  | `TEXT`                 | —       | The Illustration label's text (default: "Illustration · <reasons>").                                             |

### Replay

| Option                | Value  | Default | Description                                                                                                                                               |
| --------------------- | ------ | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--playback-speed`    | `X`    | `1.0`   | Animation speed multiplier for `--animate` (default: 1.0 = real time).                                                                                    |
| `--no-autoplay`       | switch | —       | With `--animate`: start the replay paused (press ▶ Play to run it). By default the saved HTML autoplays on load at the playback speed.                    |
| `--anim-grid-step-ms` | `MS`   | —       | With `--animate`: emit a frame every MS of reading time (default: 100). Smaller is smoother and larger to export.                                         |
| `--anim-max-frames`   | `N`    | —       | With `--animate`: at most N frames, the first included (default: 360). A trial too long for that many at `--anim-grid-step-ms` gets a wider step instead. |

### Size and export

| Option                  | Value                   | Default | Description                                                                                                                                                                                                                                                                                       |
| ----------------------- | ----------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--width`               | `PX`                    | —       | Image width in px for PNG/SVG/PDF (default: the figure's own size). Use with `--height` for fixed-size thumbnails.                                                                                                                                                                                |
| `--height`              | `PX`                    | —       | Image height in px for PNG/SVG/PDF (default: the figure's own size).                                                                                                                                                                                                                              |
| `--scale`               | `X`                     | `2.0`   | Raster pixel-density multiplier (PNG/SVG/PDF; default: 2.0).                                                                                                                                                                                                                                      |
| `--width-mm`            | `MM`                    | —       | Print width of a PNG in mm, drawn at `--dpi` (replaces `--scale`).                                                                                                                                                                                                                                |
| `--width-in`            | `IN`                    | —       | Print width of a PNG in inches, drawn at `--dpi`.                                                                                                                                                                                                                                                 |
| `--dpi`                 | `N`                     | —       | Resolution of `--width-mm` / `--width-in` (default: 300).                                                                                                                                                                                                                                         |
| `--separable-layers`    | switch                  | —       | Also write the figure split into one file per layer (word boxes / fixations / saccades / heatmap / labels / stimulus image) in a `&lt;output&gt;_layers/` folder, so each can be restyled in Illustrator / Inkscape. Static image output only (.svg/.pdf/.png); the layers register when stacked. |
| `--print-code`          | `python`, `cli`, `both` | —       | Print the API / CLI code that reproduces this figure to stdout (python                                                                                                                                                                                                                            |
| `--print-code-explicit` | switch                  | —       | With `--print-code`: write every figure option at its current value instead of only the non-defaults.                                                                                                                                                                                             |

### Comparison

| Option                                   | Value                                | Default     | Description                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------------------- | ------------------------------------ | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--compare-with`                         | `PARTICIPANT:TRIAL`                  | —           | Compare against a second scanpath, named as participant:trial. Taken from the loaded dataset unless `--compare-words`/`--compare-fixations` name a second one.                                                                                                                                                                                       |
| `--compare-screen`                       | `SCREEN_ID`                          | —           | Screen of the second scanpath's multipart trial (default: its first screen), looked up in its own trial. `--screen` picks the first scanpath's. Each scanpath is drawn from one screen.                                                                                                                                                              |
| `--compare-layout`                       | `overlay`, `side-by-side`, `stacked` | `overlay`   | How the two scanpaths are arranged (default: overlay). Across two datasets, overlay needs both canvases to be the same size — two different canvases are refused rather than silently split, so pass side-by-side or stacked for them. Matching canvases that a dataset never recorded still overlay, with a warning.                                |
| `--compare-stimulus`                     | `both`, `a`, `b`                     | `both`      | On an overlay, whose word boxes and text to draw (default: both). Two datasets' word boxes coincide only when the text is identical.                                                                                                                                                                                                                 |
| `--label-a`                              | `TEXT`                               | —           | Name for the FIRST scanpath in the legend and hover, instead of the default. Applies to the comparison figure and the `--animate` co-animation. Requires `--label-b`.                                                                                                                                                                                |
| `--label-b`                              | `TEXT`                               | —           | Name for the SECOND scanpath in the legend and hover, instead of the default. Requires `--label-a`.                                                                                                                                                                                                                                                  |
| `--compare-legend` `--no-compare-legend` | switch                               | —           | Draw the legend naming the two scanpaths (the app's A/B legend; on by default, as in the app). Applies to the `--animate` co-animation too.                                                                                                                                                                                                          |
| `--style-a`                              | `SPEC`                               | —           | Styling for the FIRST scanpath, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid  |
| `--style-b`                              | `SPEC`                               | —           | Styling for the SECOND scanpath, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid |
| `--compare-fixation-flag`                | `SPEC`                               | —           | Filters & highlights for the SECOND scanpath only, repeatable; same SPEC as `--fixation-flag`, e.g. `--compare-fixation-flag` short=discard,threshold_ms=80. Replaces `--fixation-flag` for B.                                                                                                                                                       |
| `--compare-saccade-classes`              | `CLASSES`                            | —           | The reading classes the SECOND scanpath draws, comma-separated (same names as `--saccade-classes`). Replaces `--saccade-classes` for B. Not with `--animate`, which draws every class.                                                                                                                                                               |
| `--compare-fix-index-range`              | `START:END`                          | —           | Draw only fixations START through END of the SECOND scanpath (1-based, inclusive). Replaces `--fix-index-range` for B.                                                                                                                                                                                                                               |
| `--stimulus-image-b`                     | `PATH`                               | —           | The SECOND scanpath's stimulus image, for a side-by-side or stacked comparison across two datasets (each panel draws its own page). Sized and placed like `--stimulus-image`.                                                                                                                                                                        |
| `--stimulus-image-size-b`                | `WxH`                                | —           | Size of `--stimulus-image-b` in px (default: the PNG's own size, else `--compare-canvas`, else `--canvas`).                                                                                                                                                                                                                                          |
| `--stimulus-image-origin-b`              | `X,Y`                                | —           | Top-left of `--stimulus-image-b` in the second screen's px (default: 0,0).                                                                                                                                                                                                                                                                           |
| `--compare-words`                        | `PATH [PATH ...]`                    | —           | Words table(s) for the SECOND dataset. Same formats and globbing as `--words`.                                                                                                                                                                                                                                                                       |
| `--compare-fixations`                    | `PATH [PATH ...]`                    | —           | Fixations table(s) for the SECOND dataset. Same formats and globbing as `--fixations`.                                                                                                                                                                                                                                                               |
| `--compare-raw-gaze`                     | `PATH [PATH ...]`                    | —           | Raw gaze table(s) for the SECOND dataset, drawn under B's scanpath. Same formats as `--raw-gaze`; with no second dataset, `--raw-gaze` already covers both scanpaths.                                                                                                                                                                                |
| `--compare-dataset-name`                 | `NAME`                               | `Dataset B` | Label for the second dataset, used in the trace names (default: 'Dataset B').                                                                                                                                                                                                                                                                        |
| `--compare-canvas`                       | `WxH`                                | —           | Second dataset's monitor size in px, e.g. 1680x1050. Read off its data when omitted. An overlay, or an `--animate` co-animation, compares this against `--canvas`.                                                                                                                                                                                   |

## corpus

`corpus` goes the other way from `render`: it reads a tidy CSV you already have and renders a styled corpus figure, as plot_corpus_figure does. For `--kind profile` the CSV needs `word_id` and `value` columns.

```
scanpath-studio corpus --input profile.csv --kind profile --output profile.svg
```

| Option              | Value                                   | Default   | Description                                                                                                                              |
| ------------------- | --------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `--input`           | `PATH`                                  | required  | The CSV. profile reads word_id plus the value column (and optional lo / hi), distribution the value column, difference word_id and diff. |
| `--kind`            | `profile`, `distribution`, `difference` | required  | A per-word profile, a distribution, or a difference profile.                                                                             |
| `-o` `--output`     | `PATH`                                  | required  | Output file; any extension save_figure writes (.html, .png, .svg, .pdf).                                                                 |
| `--measure-label`   | `MEASURE_LABEL`                         | `Value`   | Axis / legend label for the value (default: Value).                                                                                      |
| `--series-col`      | `SERIES_COL`                            | `series`  | Column naming the overlaid series, when present (default: series).                                                                       |
| `--value-col`       | `VALUE_COL`                             | `value`   | The value column (default: value).                                                                                                       |
| `--primary-color`   | `PRIMARY_COLOR`                         | `#1f77b4` | First series color (default: #1f77b4).                                                                                                   |
| `--secondary-color` | `SECONDARY_COLOR`                       | `#e45756` | Second series color (default: #e45756).                                                                                                  |

## check

`check` runs the **Data Management** page's **Data checks** on your tables without opening the app. It looks for:

- fixations lasting 0 ms or less, or with an infinite duration or onset;
- fixations and raw-gaze samples with no finite position;
- word boxes with no area or no finite position;
- per-screen screen sizes that are not finite and positive.

Each finding gives the rows and trials affected, a few example rows, and what the app does with them. `check` changes nothing and exits 0 whatever it finds. `--json` prints the table check_data_health returns.

```
scanpath-studio check --words ia.csv --fixations fixations.csv
scanpath-studio check --raw-gaze gaze_samples.csv --json
```

| Option                   | Value                 | Default | Description                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------ | --------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--sample`               | switch                | —       | Check the bundled OneStop demo instead of your own tables.                                                                                                                                                                                                                                                                                                      |
| `--words`                | `PATH [PATH ...]`     | —       | Words table(s), as for render.                                                                                                                                                                                                                                                                                                                                  |
| `--fixations`            | `PATH [PATH ...]`     | —       | Fixations table(s), as for render.                                                                                                                                                                                                                                                                                                                              |
| `--raw-gaze`             | `PATH [PATH ...]`     | —       | Raw (sample-level) gaze table(s), as for render.                                                                                                                                                                                                                                                                                                                |
| `--raw-gaze-schema`      | `JSON`                | —       | Column mapping for the `--raw-gaze` table, replacing auto-detection (same shape as `--fix-schema`).                                                                                                                                                                                                                                                             |
| `--trial-parts-manifest` | `PATH`                | —       | JSON manifest assigning source rows to ordered screens.                                                                                                                                                                                                                                                                                                         |
| `--json`                 | switch                | —       | Print the findings as JSON (the rows api.check_data_health returns).                                                                                                                                                                                                                                                                                            |
| `--word-schema`          | `JSON`                | —       | Column mapping for the `--words` table, replacing auto-detection: a JSON object (or a path to a .json file holding one) from each field to a column name, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}' — the same dict api.load_scanpath_data takes. Needed only when a column isn't recognized; the error then prints a mapping to start from.     |
| `--fix-schema`           | `JSON`                | —       | Column mapping for the `--fixations` table, replacing auto-detection: a JSON object (or a path to a .json file holding one) from each field to a column name, e.g. '{"trial": "TRIAL_INDEX", "word_id": "IA_ID", ...}' — the same dict api.load_scanpath_data takes. Needed only when a column isn't recognized; the error then prints a mapping to start from. |
| `--keep-columns`         | `COLUMN [COLUMN ...]` | —       | Further columns of your own to carry through loading under their own names (e.g. a pupil size), from whichever table has them — otherwise loading keeps only the mapped and recognized fields. A kept fixation column can then be `--color-by`, an axis or a hover field. The keep_columns= of api.load_scanpath_data.                                          |

## cache

A local or desktop run caches your session on your own machine, so a refresh or a restart resumes where you left off: uploaded datasets, column mappings, view settings, saved designs, metadata tables and annotations. `cache` shows what is stored and removes it.

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

`version` says which build this is and how it was installed. `--check` also asks GitHub whether a newer release is out and prints the command that updates your install. It is the only time the command uses the network.

```
scanpath-studio version           # the build, and how it was installed
scanpath-studio version --check   # …and whether a newer release is out
```

| Option      | Value     | Default | Description                                                           |
| ----------- | --------- | ------- | --------------------------------------------------------------------- |
| `--check`   | switch    | —       | Ask GitHub for the latest release and say how to update this install. |
| `--timeout` | `SECONDS` | `5.0`   | How long to wait for GitHub (default 5).                              |

Between releases the version names the build: `0.35.0.post3+g8f18219` is three commits after 0.35.0, at commit `8f18219`. The same check is **Help → About → Check for updates** in the app, and check_for_updates in Python.
