# CLI reference

`scanpath-studio` launches the app by default. Its `render` subcommand writes
one trial without opening the UI.

## Launch

```bash
scanpath-studio
scanpath-studio --server.port 8600
scanpath-studio --no-persist          # don't cache the session on this computer
```

Additional launch flags are forwarded to Streamlit.

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
  --eyegenbench-dataset Provo -p 1 -t 1 -o provo.svg

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
# Two readings from the same dataset
scanpath-studio render --sample -p p1 -t t1 \
  --compare-with p2:t5 -o compare.html

# Side by side, showing only B's word boxes and text
scanpath-studio render --sample -p p1 -t t1 \
  --compare-with p2:t5 \
  --compare-layout side-by-side --compare-stimulus b -o compare.svg

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
| B from another dataset | `--compare-words PATH… --compare-fixations PATH…` |
| name that dataset | `--compare-dataset-name NAME` |
| declare the screens | `--canvas WxH`, `--compare-canvas WxH` |
| co-animate both readings | add `--animate` (HTML output) |

`--animate --compare-with` replays **both** readings on one clock, the same dual
co-animation the app renders with Animate and Compare both on. That is an
overlay, so it needs one shared screen on the same terms as `--compare-layout
overlay`. `--compare-with` cannot be combined with `--all-screens`: a comparison
is a single figure of two readings, so render one screen at a time with
`--screen`.

**Overlay across two datasets requires matching canvases.** Overlaying pools both
readings into one set of pixel coordinates, so `--compare-layout overlay` on two
different screens **fails** rather than quietly falling back:

```console
$ scanpath-studio render … --canvas 2560x1440 --compare-canvas 1680x1050
These readings were recorded on different screens — 2560x1440 and 1680x1050. …
Pass layout='side_by_side' (or 'stacked') to compare them anyway, each panel
drawn to its own screen.
```

The app resolves that case to Side by side because a user can see what they got;
a script cannot, so the CLI refuses instead of returning a differently-shaped
figure. Nothing is ever rescaled to force an overlay.

Matching canvases that neither dataset actually *recorded* (most public corpora
report a default) still overlay — you get a warning on stderr rather than an
error, since the app can't prove the two displays matched but you usually can.

A second dataset is loaded from **files only**. Any corpus reachable from Python
can still be scanpath B via
[`compare_scanpaths`](api.md#scanpath_studio.api.compare_scanpaths), which takes
B's frames directly.

`--monitor-mm` / `--viewing-distance` (and their `--compare-*` twins) record
physical display geometry on each side's setup. Nothing in the comparison reads
them today — the overlay rule is about pixels, not degrees — but they complete
the recorded setup.

## Common options

| Goal | Option |
| --- | --- |
| hide a layer | `--no-words`, `--no-labels`, `--no-fixations`, `--no-saccades`, `--no-heatmap` |
| animate | `--animate` and optionally `--playback-speed X` |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| show monitor-pixel axes | `--coordinate-grid` and optionally `--coordinate-grid-spacing PX` |
| color fixations | `--color-by FIELD` |
| draw only part of a trial | `--fix-index-range START:END` (1-based, both inclusive; honoured by `--animate` too) |
| mark the critical span | `--highlight-column COLUMN` (`''` for none) with `--critical-span-style mark-text\|mark-border\|none` |
| flag short / long / off-text / blink fixations | `--fixation-flag CATEGORY=MODE[,threshold_ms=N][,symbol=S][,color=#RRGGBB]`, repeatable |
| classify saccades | `--saccade-color-by-type` |
| correct vertical drift (needs `SCANPATH_EXPERIMENTAL=1`) | `--drift-correction ALGORITHM` |
| add the stimulus image | `--stimulus-image PATH` |
| resolve per-trial images | `--image-root DIR --image-pattern '{text_id}.png'` |
| use Gaussian duration mass | `--heatmap-style 'Duration mass' --duration-mass-sigma 1.0` |
| mark a schematic | `--illustration` or `--illustration-label MODE` |
| render an authored trial | `--authoring PATH` |
| select or inspect a child screen | `--screen ID`, `--list-parts` |
| render every ordered screen | `--all-screens`, optionally `--screen-transition instant|recorded` |
| map arbitrary source rows to screens | `--trial-parts-manifest manifest.json` |
| attach participant metadata | `--participant-metadata readers.csv` |
| attach trial metadata | `--trial-metadata readings.csv`, `--trial-metadata-reader-column` to key it by reader **and** trial |
| export editable layers | `--separable-layers` |
| style the fixations | `--fixation-color`, `--fixation-symbol`, `--fixation-colorscale`, `--marker-size-range` |
| style the saccades | `--saccade-style`, `--saccade-width`, `--saccade-arcs`, `--saccade-arrows`, `--saccade-classes` |
| pick a palette | `--palette` |
| size the figure | `--width`, `--height`, `--scale` |
| title and caption it | `--title`, `--caption` |
| tune the heatmap | `--heatmap-metric`, `--heatmap-colorscale`, `--heatmap-norm` |
| print the equivalent Python | `--print-code python` (or `cli` / `both`, plus `--print-code-explicit`) |

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
and run-configuration files. `scanpath-studio corpus` produces a tidy
corpus-analysis table for scripting. The `render` command still renders one
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
