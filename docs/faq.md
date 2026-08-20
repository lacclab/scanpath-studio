# FAQ

## Why is the plot empty or misaligned?

Check the 🗂️ **Data** page. The words and fixations must share trial IDs and the
same pixel coordinate system. Also set the monitor size used in the experiment;
the app cannot infer it from an export. See [Loading data](guides/loading-data.md).

## Why do the measures differ from EyeLink or my pipeline?

Recognized EyeLink IA measures are preserved. Otherwise the app assigns
fixations using your word boxes and computes its own measures. AOI padding,
fixation exclusions, and definitions can differ between pipelines. Cross-check
values used in a publication.

## Does Fixations → Filter change the measures?

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
same dataset. Share links include the current participant and trial; see
[Outputs and sharing](guides/outputs-sharing.md).

## Does a refresh erase my work?

Local and desktop installs restore completed datasets and session state from an
on-device recovery cache. The hosted demo is memory-only. Download a **JSON
backup** from **Session** when settings and annotations must be portable.

**Session → Automatic recovery** shows what the cache holds, where it is saved,
and lets you pause or clear it; `scanpath-studio cache` does the same from a terminal. See
[Privacy](privacy.md#what-happens-to-a-file-you-upload).

## I edited the code and nothing changed?

Streamlit re-runs only the top-level script — it does not reload already-imported
modules, and `st.cache_data` does not hash the helper functions a cached loader
calls. Restart the server process after editing code; a rerun or "Clear cache"
isn't enough. This is unrelated to **Automatic recovery**, which stores your
data and settings, not code. See
[Contributing](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md#if-a-code-change-doesnt-show-up).

## Where does my data go?

Local and desktop use stays on your machine. The hosted demo runs on a third-party
Streamlit server, so do not upload identifiable participant data there. See
[Privacy](privacy.md).

## How do I cite the app?

Use the repository's
[`CITATION.cff`](https://github.com/lacclab/scanpath-studio/blob/main/CITATION.cff)
and cite any public corpus or drift-correction method used.
