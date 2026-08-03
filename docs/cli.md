# CLI reference

`scanpath-studio` launches the app by default. Its `render` subcommand writes
one trial without opening the UI.

## Launch

```bash
scanpath-studio
scanpath-studio --server.port 8600
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
```

HTML is interactive and browser-free. PNG, SVG, and PDF require
Chrome/Chromium (`plotly_get_chrome -y`).

## Common options

| Goal | Option |
| --- | --- |
| hide a layer | `--no-words`, `--no-labels`, `--no-fixations`, `--no-saccades`, `--no-heatmap` |
| animate | `--animate` and optionally `--playback-speed X` |
| set display geometry | `--canvas WIDTHxHEIGHT` |
| color fixations | `--color-by FIELD` |
| classify saccades | `--saccade-color-by-type` |
| correct vertical drift | `--drift-correction ALGORITHM` |
| add the stimulus image | `--stimulus-image PATH` |
| export editable layers | `--separable-layers` |

Use the installed command as the authoritative full reference:

```bash
scanpath-studio --help
scanpath-studio render --help
```

The CLI renders one trial per invocation. Use the [Python batch pattern](automation.md#batch-pattern)
or the app's **Export → Multiple trials** for a corpus.
