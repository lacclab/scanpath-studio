# OneStop dataset

[OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) is a
360-participant English eye-tracking-while-reading corpus (Berzak, Malmaud,
Shubi, Meiri, Lion, Levy, *Scientific Data* 2025,
[doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)).
The app's bundled demo is a 3-participant subset of it; this page covers loading
the **full public corpus** from [OSF](https://osf.io/2prdq/) as a public dataset.

!!! note "Two ways to load OneStop"
    - **Public dataset (this page)** — the OneStop reports as a public dataset:
      the **Public** variant downloads from OSF on demand (no setup); the **LaCC
      lab** variant reads a local lab-processed export. Pick the variant, reading
      regime, and trial parts on the 🗂️ **Data** page.
    - **OneStop server bundle** — points at a local `lacclab` export via the
      `$ONESTOP_DATA_DIR` environment variable, with per-pid Parquet shards for
      review-app deep links. See
      [Export & troubleshooting](export-troubleshooting.md).

The corpus is 360 L1-English readers reading 30 Guardian articles (162
paragraphs, each in an Advanced and an Elementary version) — ~19.4k regular
trials.

!!! info "A text is one paragraph at one difficulty level"

    The public reports carry no unique paragraph id, so the loader composes one
    — `{article_batch}_{article_id}_{paragraph_id}_{difficulty_level}`, the same
    id the bundled demo ships, with the reader and the reading folded under it
    for the trial id. Advanced and Elementary are therefore **two texts**, not
    two renderings of one, and the app counts **330** of them across the four
    regimes (the lab export, which composes the id its own way, agrees).

    That 330 is the 162 paragraphs at two levels (324), plus **six** more from
    the practice article — `article_id` 0, two paragraphs, Advanced only,
    repeated in all three batches. The published *30 articles / 162 paragraphs*
    counts experimental material and leaves it out, so both figures are right.

    Before this ([BUG-43](https://github.com/lacclab/scanpath-studio/issues/133))
    `text_id` was the paragraph's index *within its article*, so paragraphs from
    different articles collided and the whole corpus read as **7 texts** —
    affecting the *Per text* analyses, text-based comparisons, and the counts on
    🗂️ Data. A share link made before the fix names a trial by the old id and
    will not resolve.

## Loading it

OneStop is exposed as a **Public dataset**. In the app, open 🗂️ **Data** and
choose **OneStop** as the data source, then in its **Options** pick a
**Variant**, a **Reading regime**, and one or more **Parts**:

**Variant**

| Variant | What it is |
| --- | --- |
| Public (OSF download) | Reports fetched from [OSF](https://osf.io/2prdq/) on demand, cached on disk. |
| LaCC lab (local export) | A lab-processed export with extra derived columns (`unique_paragraph_id`, span indices, normalized dwell, …). No download — point at your local folder (default is the lab OneDrive path, editable / `ONESTOP_LACCLAB_DIR`). |

**Reading regime**

| Regime | What it is |
| --- | --- |
| Ordinary reading | Standard paragraph reading. |
| Information seeking | Reading to answer a known question. |
| Repeated reading | Re-reading the same paragraphs. |
| Information seeking (repeated) | Information seeking during repeated reading. |

**Parts** — which *screen* of a trial to load (default **Paragraph**):

| Part (app label) | CLI / deep-link id | What it is |
| --- | --- | --- |
| Title | `Title` | The article title screen. |
| Question preview | `Question_Preview` | The question shown before reading (information-seeking regimes). |
| Paragraph | `Paragraph` | The reading passage (the default). |
| Question | `Questions` | The question re-shown after reading. |
| Answers | `Answers` | The four answer choices. |
| Question + answers (QA) | `QA` | The combined question-and-answers screen. |
| Feedback | `Feedback` | The one-second correctness notification. |

The first column is what the app's **Parts** picker shows; the second is the
literal id for `--onestop-part` on the [CLI](cli.md) and the
`?onestop_parts=` deep-link parameter.

Every part ships an **interest-area report** (one row per word, with bounding
boxes and reading measures) and a **fixation report**, all in the same schema —
so each part renders as a scanpath. Selecting **several parts** makes each part
its own trial (the part is folded into the trial id, e.g. `Paragraph::1` vs
`Title::1`, so their word boxes don't collide). On OSF only *Paragraph* is
regime-split; the other parts come from the all-regimes full release, so they
load regardless of the chosen regime.

The **Data location** section of the 🗂️ Data page lists the **Expected files** and
shows whether they're already present. For the Public variant, if they're
present the corpus loads with no network access; if not, click **⬇ Download** to
fetch them into the folder (cached on disk, so only the first load pays the
download — reports range from tens to a few hundred MB each).

OneStop's reports use the same schema as the bundled demo, so they flow through
the normal auto-detect → normalize pipeline — the **Column mapping** panels still
appear and stay overridable. Fixation and interest-area coordinates are
full-screen pixels on OneStop's 2560×1440 presentation monitor, so the canvas
renders true-to-scale to that monitor.

## From the Python API

The same loader is available headlessly — `load_onestop` returns normalized,
plot-ready frames:

```python
import scanpath_studio as sps

# Fetch (public variant) + normalize the chosen regime + parts (cached under root).
words, fixations = sps.load_onestop(
    "data/OneStop",
    regime="ordinary",
    parts=["Paragraph"],  # any subset of the seven parts
    variant="public",  # or "lacclab" for a local export
    download=True,  # public variant only
)
fig = sps.plot_scanpath(words, fixations, canvas_size=(2560, 1440))
```

For the raw (pre-normalization) frames, use
`scanpath_studio.datasets.onestop_raw_frames(...)` with the same arguments.

## From the command line

```bash
scanpath-studio render --onestop data/OneStop \
    --onestop-regime ordinary --onestop-part Paragraph \
    -p <participant> -t <trial> -o out.html
```

`--onestop-part` is repeatable; `--onestop-variant` is `public` (default) or
`lacclab`.

The implementation lives in
[`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py)
(`onestop_raw_frames` / `load_onestop` / `download_onestop`); the OSF file ids per
regime + part come from the OneStop repo's `download_data_files.py`.
