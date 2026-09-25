# OneStop dataset

[OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) is a 360-participant English eye-tracking-while-reading corpus (Berzak, Malmaud, Shubi, Meiri, Lion, Levy, *Scientific Data* 2025, [doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)). The app's bundled demo is a small subset of it (word boxes for 3 readers, fixations for 2 of them); this page covers loading the **full public corpus** from [OSF](https://osf.io/2prdq/) as a public dataset.

The corpus is 360 L1-English readers reading 30 Guardian articles (162 paragraphs, each in an Advanced and an Elementary version).

A text is one paragraph at one difficulty level

The public reports carry no unique paragraph id, so the loader composes one — `{article_batch}_{article_id}_{paragraph_id}_{difficulty_level}`, the same id the bundled demo ships, with the reader and the reading folded under it for the trial id. Advanced and Elementary are therefore **two texts**, not two renderings of one, and the app counts **330** of them across the four regimes.

That 330 is the 162 paragraphs at two levels (324), plus **six** more from the practice article — `article_id` 0, two paragraphs, Advanced only, repeated in all three batches. The published *30 articles / 162 paragraphs* counts experimental material and leaves it out, so both figures are right.

## Loading it

OneStop is exposed as a **Public dataset**. In the app, open 🗂️ **Data**, click **OneStop** in **📂 Available datasets**, then **✏️ Edit** it; its **Options** pick a **Variant**, a **Reading regime**, and one or more **Parts**:

**Variant**

| Variant                 | What it is                                                                   |
| ----------------------- | ---------------------------------------------------------------------------- |
| Public (OSF download)   | Reports fetched from [OSF](https://osf.io/2prdq/) on demand, cached on disk. |
| LaCC lab (local export) | LaCC lab's internal export — not publicly distributed.                       |

**Reading regime**

| Regime                         | What it is                                   |
| ------------------------------ | -------------------------------------------- |
| Ordinary reading               | Standard paragraph reading.                  |
| Information seeking            | Reading to answer a known question.          |
| Repeated reading               | Re-reading the same paragraphs.              |
| Information seeking (repeated) | Information seeking during repeated reading. |

**Parts** — which *screen* of a trial to load (default **Paragraph**):

| Part (app label)        | CLI / deep-link id | What it is                                                       |
| ----------------------- | ------------------ | ---------------------------------------------------------------- |
| Title                   | `Title`            | The article title screen.                                        |
| Question preview        | `Question_Preview` | The question shown before reading (information-seeking regimes). |
| Paragraph               | `Paragraph`        | The reading passage (the default).                               |
| Question                | `Questions`        | The question shown after reading.                                |
| Answers                 | `Answers`          | The four answer choices.                                         |
| Question + answers (QA) | `QA`               | The combined question-and-answers screen.                        |
| Feedback                | `Feedback`         | The correctness feedback screen.                                 |

The first column is what the app's **Parts** picker shows; the second is the literal id for `--onestop-part` on the [CLI](https://lacclab.github.io/scanpath-studio/cli/index.md) and the `?onestop_parts=` deep-link parameter.

Every part ships an **interest-area report** (one row per word, with bounding boxes and reading measures) and a **fixation report**, all in the same schema — so each part renders as a scanpath. Selecting **several parts** makes each part its own trial (the part is folded into the trial id, e.g. `Paragraph::1` vs `Title::1`, so their word boxes don't collide). On OSF only *Paragraph* is regime-split; the other parts come from the all-regimes full release, so they are not narrowed to the chosen regime: they hold every regime's trials.

The **✏️ Edit** screen's data-location part lists the **Expected files** and shows whether they're already present (until they are, the app shows the bundled demo, with a **⬇ Download now** panel). For the Public variant, if they're present the corpus loads with no network access; if not, click **⬇ Download** to fetch them into the folder (cached on disk, so only the first load pays the download — reports range from tens to a few hundred MB each).

On a server other machines can reach

When the app is served to other machines (the hosted demo, or `--server.address 0.0.0.0`), the *Data directory* box, the 📁 folder picker and **⬇ Download** are turned off: the corpus is read from the server's configured data location, and whoever runs it places the files there — or, on a trusted network, starts it with `SCANPATH_LOCAL_FS=1`. See [Launch](https://lacclab.github.io/scanpath-studio/cli/#launch).

Fixation and interest-area coordinates are full-screen pixels on OneStop's 2560×1440 presentation monitor, so the canvas renders true-to-scale to that monitor.

## From the Python API

The same loader is available headlessly — `load_onestop` returns normalized, plot-ready frames:

```
import scanpath_studio as sps

# Fetch (public variant) + normalize the chosen regime + parts (cached under root).
words, fixations = sps.load_onestop(
    "data/OneStop",
    regime="ordinary",
    parts=["Paragraph"],  # any subset of the seven parts
    download=True,
)
pid, tid = sps.list_trials(words, fixations).iloc[0]  # or any row you want
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
```

## From the command line

```
scanpath-studio render --onestop data/OneStop \
    --onestop-regime ordinary --onestop-part Paragraph \
    -p <participant> -t <trial> -o out.html
```

`--onestop-part` is repeatable.
