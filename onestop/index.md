# OneStop dataset

[OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) is a 360-participant English eye-tracking-while-reading corpus (Berzak, Malmaud, Shubi, Meiri, Lion, Levy, *Scientific Data* 2025, [doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)). The app's bundled demo is a small subset of it (2 readers, 12 paragraphs each); this page covers loading the **full public corpus** from [OSF](https://osf.io/2prdq/) as a public dataset.

The corpus is 360 L1-English readers reading 30 Guardian articles (162 paragraphs, each in an Advanced and an Elementary version).

A text is one paragraph at one difficulty level

The public reports carry no unique paragraph id, so the loader composes one — `{article_batch}_{article_id}_{paragraph_id}_{difficulty_level}`, the same id the bundled demo ships, with the reader and the reading folded under it for the trial id. Advanced and Elementary are therefore **two texts**, not two renderings of one, and the app counts **330** of them across the four regimes.

That 330 is the 162 paragraphs at two levels (324), plus **six** more from the practice article — `article_id` 0, two paragraphs, Advanced only, repeated in all three batches. The published *30 articles / 162 paragraphs* counts experimental material and leaves it out, so both figures are right.

## Loading it

OneStop is exposed as **four public datasets**, one per reading regime. In the app, open **Data Management** and click the one you want in the list of datasets:

| Dataset                                  | What it is                                                    |
| ---------------------------------------- | ------------------------------------------------------------- |
| OneStop — Ordinary reading               | Reading for comprehension, without seeing the question first. |
| OneStop — Information seeking            | Reading after seeing the question to be answered.             |
| OneStop — Repeated reading               | Reading a paragraph for the second time.                      |
| OneStop — Information seeking (repeated) | A second reading, after seeing the question.                  |

Each holds **every part** of its regime's trials, the reading passage and the screens around it, from the public [OSF](https://osf.io/2prdq/) release:

| Part                    | CLI id             | What it is                                                            |
| ----------------------- | ------------------ | --------------------------------------------------------------------- |
| Title                   | `Title`            | The article title screen.                                             |
| Question preview        | `Question_Preview` | The question shown before reading (information-seeking regimes only). |
| Paragraph               | `Paragraph`        | The reading passage.                                                  |
| Question                | `Questions`        | The question shown after reading.                                     |
| Answers                 | `Answers`          | The four answer choices.                                              |
| Question + answers (QA) | `QA`               | The combined question-and-answers screen.                             |
| Feedback                | `Feedback`         | The correctness feedback screen.                                      |

Every part ships an **interest-area report** (one row per word, with bounding boxes and reading measures) and a **fixation report**, all in the same schema — so each part renders as a scanpath. A trial is one reading of one paragraph, and its parts are that trial's **screens**, in the order they were shown — step through them with the **Screen** picker above the plot. Each screen keeps its own word boxes; not every reading has every part (the title screen opens an article, so only a reading of its first paragraph has one). On OSF only *Paragraph* is split by regime; the other parts come from one all-regimes release, which the four datasets share on disk, and each dataset keeps only its own regime's trials from them (by the reports' `question_preview` and `repeated_reading_trial` columns).

The **Edit dataset** screen's data-location part lists the **Expected files** and shows whether they're already present (until they are, the app shows the bundled demo, with a **⬇ Download now** panel). If they're present the dataset loads with no network access; if not, click **⬇ Download** to fetch them into the folder (cached on disk, so only the first load pays the download — reports range from tens to a few hundred MB each, and a regime has up to fourteen). While it downloads, a card shows how much has arrived; **Stop download** ends it and deletes the partial file.

The folder defaults to the **Data Management** page's **Download folder**, where every public corpus gets its own subfolder (`<folder>/OneStop`). Leave that box blank for the default: `data/` in a source checkout, otherwise the per-user data folder (`~/.local/share/scanpath-studio/data`, or `%LOCALAPPDATA%\scanpath-studio\data` on Windows). `scanpath-studio run --download-dir DIR` or `SCANPATH_STUDIO_DOWNLOAD_DIR` changes the default.

On a server other machines can reach

When the app is served to other machines (the hosted demo, or `--server.address 0.0.0.0`), the *Data directory* box, the folder picker and **⬇ Download** are turned off: the corpus is read from the server's configured data location, and whoever runs it places the files there — or, on a trusted network, starts it with `SCANPATH_LOCAL_FS=1`. See [Launch](https://lacclab.github.io/scanpath-studio/cli/#launch).

Fixation and interest-area coordinates are full-screen pixels on OneStop's 2560×1440 presentation monitor, so the canvas renders true-to-scale to that monitor.

## From the Python API

The same loader is available headlessly — `load_onestop` returns normalized, plot-ready frames:

```
import scanpath_studio as sps

# Fetch + normalize the chosen regime + parts (cached under root).
words, fixations = sps.load_onestop(
    "data/OneStop",
    regime="ordinary",
    parts=["Paragraph"],  # any subset of the seven parts
    download=True,
)
# The app's dataset for a regime is every part of it:
from scanpath_studio.datasets import onestop_regime_parts

parts = onestop_regime_parts("ordinary")
pid, tid = sps.list_trials(words, fixations).iloc[0]  # or any row you want
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
```

## From the command line

```
scanpath-studio render --onestop data/OneStop \
    --onestop-regime ordinary --onestop-part Paragraph \
    -p <participant> -t <trial> -o out.html
```

`--onestop-part` is repeatable. Parts other than Paragraph are cut to `--onestop-regime` here too, as in the app.
