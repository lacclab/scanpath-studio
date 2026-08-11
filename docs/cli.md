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

## Common options

| Goal | Option |
| --- | --- |
| hide a layer | `--no-words`, `--no-labels`, `--no-fixations`, `--no-saccades`, `--no-heatmap` |
| animate | `--animate` and optionally `--playback-speed X` |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| show monitor-pixel axes | `--coordinate-grid` and optionally `--coordinate-grid-spacing PX` |
| color fixations | `--color-by FIELD` |
| classify saccades | `--saccade-color-by-type` |
| correct vertical drift | `--drift-correction ALGORITHM` |
| add the stimulus image | `--stimulus-image PATH` |
| resolve per-trial images | `--image-root DIR --image-pattern '{text_id}.png'` |
| use Gaussian duration mass | `--heatmap-style 'Duration mass' --duration-mass-sigma 1.0` |
| mark a schematic | `--illustration` or `--illustration-label MODE` |
| render an authored trial | `--authoring PATH` |
| select or inspect a child screen | `--screen ID`, `--list-parts` |
| render every ordered screen | `--all-screens`, optionally `--screen-transition instant|recorded` |
| map arbitrary source rows to screens | `--trial-parts-manifest manifest.json` |
| export editable layers | `--separable-layers` |

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
or **Export → Multiple trials** for many figures.

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

The same information (and a **Forget saved session** button) is in the app's
sidebar under **🗄️ Recovery cache**. `SCANPATH_STUDIO_PERSIST=0` turns caching
off permanently, `--no-persist` for one launch, and `SCANPATH_STUDIO_STATE_DIR`
moves the folder. Hosted deployments never cache. See
[Privacy](privacy.md#what-happens-to-a-file-you-upload).
