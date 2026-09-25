# Tutorials

- **[Data collection](https://lacclab.github.io/scanpath-studio/tutorials/data-collection/index.md)**

  Check a pilot or completed session and record issues.

- **[Data filtering](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/index.md)**

  Review trials, annotate decisions, and define the retained pool.

- **[Exporting figures](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/index.md)**

  Export one polished figure or the same view across many trials.

- **[Corpus analysis](https://lacclab.github.io/scanpath-studio/tutorials/corpus-analysis/index.md)**

  Summarize texts, readers, or groups and download the table.

New here? Complete [Getting started](https://lacclab.github.io/scanpath-studio/getting-started/index.md) first.

## In the app

Five shorter tutorials run inside the app, under ❓ **Help → 🧭 Tutorials**. Each one spotlights the controls it names as you go, keeps its own progress, and never changes your data, filters, annotations, or settings. These are the steps each one walks, as the app shows them:

### Load and verify a dataset

Finish with the parsed words, fixations, and mapping visibly checked. *About 3 min; needs a demo or uploaded dataset.*

1. **Choose the data source.** Everything about the dataset lives on the 🗂️ **Data** page, in the order the pipeline uses it. Start at **📂 Available datasets** — click a name to open it, or ➕ **Add dataset** for your own tables.
1. **Check the column mapping.** ✏️ **Edit** a dataset's row to open its setup screen — the add screen's numbered parts, for a dataset that already exists. Part **1 · Data tables & column mapping** decides what every measure downstream is computed from. Rows marked ✨ were auto-detected; override any that guessed wrong.
1. **Verify what was parsed.** **🔎 What's in the selected dataset** opens on 📊 Stats — the counts and their spread, the quickest check that the mapping worked. The six raw tables are the tabs beside it.
1. **Check one trial id is one reading.** Part **3 · Trial identity** checks the whole dataset, before any filtering, and says so either way. A warning here means the Trial ID above is missing a column — several readings are being drawn as one scanpath, which renders happily as a reading with a lot of regressions.

### Filter and mark trials

Finish with reviewed trials annotated and ready for ID export. *About 4 min; needs at least one trial.*

1. **Narrow the review pool.** The funnel beside the trial picker — opened for you here — holds the text and participant pickers at the top (*All texts* / *All participants* until you narrow), then condition and annotation filters (favorites, tags). This tutorial only points; it never changes a filter.
1. **Review one trial at a time.** One picker for every dataset: the **Select Trial** dropdown, a scrubbing slider showing *index / total*, and ◀ ▶ to step through the pool you just narrowed.
1. **Move between screens.** A multipart trial (one reading spread over several screens) adds a screen navigator under the picker. Each screen is its own coordinate space, so nothing is ever drawn across two of them.
1. **Annotate at the right scope.** Star, tag, or note the parent trial. Multipart data can instead attach a separate annotation to the active screen.
1. **Export the marked result.** Open **Export** and choose the filtered scope and tabular files. Screen identity is retained in multipart exports.

### Build a publication figure

Finish at a ready figure download with a reproducible configuration. *About 4 min; needs words or fixations for a selected trial.*

1. **Choose the visual language.** Use design presets, palette, and the layer controls. Heatmap and scanpath are settings on the same figure, not separate data transformations.
1. **Decide static or animated.** Use **Animate** only when motion is the outcome. Multipart replay keeps screen boundaries explicit and draws no connector between canvases.
1. **Download and preserve settings.** Open **Export** for PNG/SVG/HTML or bulk output. Include the plot config when the figure must be reproducible later.
1. **Keep the figure reproducible.** **🔗 Share** turns the exact configuration into a link, and 💾 **Session** saves it (with your annotations) as JSON. Either one reproduces this figure later — the PNG on its own does not.

### Compare readings of one text

Finish with the other readings of one text side by side, at one scale. *About 3 min; needs two readings sharing a text (and screen for multipart data).*

1. **Choose the reference reading.** Pick the reading that should anchor the comparison. The comparison panel reuses this exact parent trial and active screen.
1. **Compare like with like.** Open **🔬 Comparisons** and set **Match field** to the text id: the grid shows the other trials that share this trial's value in that field — here, the other readings of *this* text — at the same scale, so it compares like with like.

### Explore a corpus question

Finish having answered one worked question — how a reader's average fixation duration moved across the experiment. *About 4 min; needs variation across trials, readers, or texts.*

1. **Switch analysis level.** Open **Corpus Analysis** to aggregate instead of inspecting one trial. Your loaded data and filters stay in place, so whatever you narrowed to on the Scanpath view is what gets aggregated here.
1. **Pick the question, not the chart.** Four subtabs, four shapes of question: **Per text** (one text, many readers), **Per sentence**, **Per reader** (one reader, all their trials) and **Groups** (a cohort, or two compared). Our question — *did this reader speed up over the experiment?* — is **Per reader**.
1. **Choose the reader and the view.** Pick the reader on the left, then set **View** to **Per-trial trend**. That plots one point per trial in presentation order — the whole experiment on one axis, rather than a single trial's dynamics.
1. **Read average fixation duration across the experiment.** Set the measure to **fixation duration**; each point is that trial's mean. A downward slope is the reader settling in — but check the spread and the trial count before believing it, because one short trial moves a mean a long way.
1. **Put it against the cohort.** **Distribution vs cohort** answers the companion question — is this reader unusual, or is the whole cohort like this? Read the sample size with the effect, never the plotted mean on its own.
