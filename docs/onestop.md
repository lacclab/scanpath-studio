# OneStop dataset

[OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) is a
360-participant English eye-tracking-while-reading corpus (Berzak, Malmaud,
Shubi, Meiri, Lion, Levy, *Scientific Data* 2025,
[doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)).
The app's bundled demo is a 3-participant subset of it; this page covers loading
the **full public corpus** from [OSF](https://osf.io/2prdq/) as a public dataset.

!!! note "Two ways to load OneStop"
    - **Public dataset (this page)** — downloads paragraph-level reports from OSF
      on demand, no setup. Pick the reading regime in the sidebar.
    - **OneStop server bundle** — points at a local `lacclab` export via the
      `$ONESTOP_DATA_DIR` environment variable, with per-pid Parquet shards for
      review-app deep links. See
      [Export & troubleshooting](export-troubleshooting.md).

## Loading it

OneStop is exposed as a **Public dataset**. In the app, choose
**Public datasets → OneStop**, then in *OneStop options* pick a **reading
regime** and (optionally) a download folder:

| Regime | What it is |
| --- | --- |
| Ordinary reading | Standard paragraph reading. |
| Information seeking | Reading to answer a known question. |
| Repeated reading | Re-reading the same paragraphs. |
| Information seeking (repeated) | Information seeking during repeated reading. |

Each regime is a separate OSF download of two paragraph-level reports —
the **interest-area report** (one row per word, with bounding boxes and
reading measures) and the **fixation report**. The *OneStop options* panel
lists the **Expected files** for the folder and shows whether the chosen
regime's reports are already present. If they are, the corpus loads with no
network access; if not, click **⬇ Download** to fetch them into the folder
(cached on disk, so only the first load of a regime pays the download — the
reports range from tens to a few hundred MB).

OneStop's reports use the same schema as the bundled demo, so they flow through
the normal auto-detect → normalize pipeline — the sidebar **Column mapping**
panels still appear and stay overridable. Fixation and interest-area
coordinates are full-screen pixels on OneStop's 2560×1440 presentation monitor,
so the canvas renders true-to-scale to that monitor.

## From the Python API

The same loader is available headlessly:

```python
from scanpath_studio.datasets import onestop_raw_frames
from scanpath_studio import data

# Fetch + read the chosen regime's OSF reports (cached under `root`).
words, fixations = onestop_raw_frames(
    "data/OneStop", regime="ordinary", download=True
)

# Normalize like an upload, then plot.
ws, fs = data.propose_word_schema(words), data.propose_fix_schema(fixations)
words = data.normalize_words(words, ws)
fixations = data.normalize_fixations(fixations, fs)
words, fixations = data.harmonize_frames(words, fixations)
```

The implementation lives in
[`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py)
(`onestop_raw_frames` / `download_onestop`); the OSF file ids per regime come
from the OneStop repo's `download_data_files.py`.
