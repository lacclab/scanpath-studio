# FAQ

## Why is the plot empty or misaligned?

Check **Data Inspection**. The words and fixations must share trial IDs and the
same pixel coordinate system. Also set the monitor size used in the experiment;
the app cannot infer it from an export. See [Loading data](guides/loading-data.md).

## Why do the measures differ from EyeLink or my pipeline?

Recognized EyeLink IA measures are preserved. Otherwise the app assigns
fixations using your word boxes and computes its own measures. AOI padding,
fixation exclusions, and definitions can differ between pipelines. Cross-check
values used in a publication.

## Does Fixation filter change the measures?

No. Its duration, boundary, and index controls affect the rendered scanpath.
They do not edit the source tables or recompute the corpus measures.

## What does drift correction change?

It assigns fixations to likely text lines and changes their rendered y-position.
It does not change x or overwrite uploaded data. Compare algorithms in
**Line assignment** when the choice is uncertain.

## Can I load only one table?

Yes. A words-only table can visualize precomputed word measures; a
fixations-only table can show gaze positions without stimulus text. Most
features work best with both tables.

## Why does HTML export work but PNG/SVG/PDF fail?

Static formats use Kaleido and need Chrome/Chromium. Run:

```bash
plotly_get_chrome -y
```

See [Export troubleshooting](export-troubleshooting.md) for video requirements.

## Can another person open my share link?

Yes, but uploaded data is not embedded in the URL. The recipient must load the
same dataset. The Share panel can omit participant and trial IDs; see
[Outputs and sharing](guides/outputs-sharing.md).

## Does a refresh erase my work?

Local and desktop installs restore completed datasets and session state from an
on-device cache. The hosted demo is memory-only. Download **💾 Save & restore**
JSON when the work must be portable.

## Where does my data go?

Local and desktop use stays on your machine. The hosted demo runs on a third-party
Streamlit server, so do not upload identifiable participant data there. See
[Privacy](privacy.md).

## How do I cite the app?

Use the repository's
[`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)
and cite any public corpus or drift-correction method used.
