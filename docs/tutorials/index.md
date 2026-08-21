# Tutorials

Each tutorial follows one research workflow from data to result. Start with the
one that matches your goal; setup details are linked only when needed.

<div class="grid cards" markdown>

- :material-clipboard-pulse:{ .lg .middle } **[Data collection](data-collection.md)**

    Check a pilot or completed session and record issues. *About 5 minutes.*

- :material-filter:{ .lg .middle } **[Data filtering](data-filtering.md)**

    Review trials, annotate decisions, and define the retained pool. *About 7 minutes.*

- :material-file-export:{ .lg .middle } **[Exporting figures](exporting-figures.md)**

    Export one polished figure or the same view across many trials. *About 5 minutes.*

- :material-chart-box:{ .lg .middle } **[Corpus analysis](corpus-analysis.md)**

    Summarize texts, readers, or groups and download the table. *About 7 minutes.*

</div>

New here? Complete [Getting started](../getting-started.md) first.

The same workflows are available inside the app under ❓ **Help → 🧭 Tutorials**
in the navigation. The chooser explains the outcome, prerequisite, and time
before starting. Each tutorial keeps its own progress, can open the relevant view
or subtab with
**Show me / Open this panel**, and never changes data, filters, annotations, or
scientific settings for you.

## Load your own data

**Outcome:** parsed words, fixations, and mappings visibly checked. *About 3
minutes.*

Everything below is on the 🗂️ **Data** page, which is two screens: 📂 **Available
datasets** and ✏️ **Edit dataset**, the second laid out in the order the pipeline
uses it.

1. **📂 Available datasets** — keep the demo, or use **➕ Add dataset** to add
   your own tables. Click a dataset's name to open it, or ✏️ **Edit** to change
   how it was read. Map **Multipart screens** only when one logical trial has
   several coordinate spaces.
2. **🔤 Column mapping** (in ✏️ Edit dataset) — the one thing that decides what
   every measure downstream is computed from. Rows marked ✨ were auto-detected;
   override any that guessed wrong. **Recording setup**, 🖼️ **Stimulus images**
   and the 👤 **Participant** / 🗂️ **Trial metadata** tables are on the same
   screen.
3. **🔎 What's in the dataset** — back on the overview, the counts come first, as
   the quickest check that the mapping worked. The raw and derived tables fold
   open below them (including, when present, the ordered screen catalogue and
   per-screen canvas sizes), and **🧾 Trial identity** says whether one trial id
   really is one reading.

!!! note "Preprocessing is held back in this release (PRE-22)"
    Optional soft exclusion and merging of short fixations is finished and
    shipped — `api.preprocess_data` and `scanpath-studio analyze` work as before
    — but its panel is not shown in this release's app. `SCANPATH_EXPERIMENTAL=1`
    brings it back for a local session. See
    [Data format](../data-format.md#optional-preprocessing-and-derived-tables).

The longer data-collection workflow is in [Data collection](data-collection.md),
and every accepted field is in [Data format](../data-format.md).

## Filter and annotate trials

**Outcome:** reviewed trials marked and ready for ID export. *About 4 minutes;
requires at least one trial.*

1. Open the **filter funnel** beside the trial picker — text and participant
   pickers, then the condition and annotation filters — to define the review
   pool.
2. Step through the trial picker. A multipart trial adds a second navigator for
   its ordered screens.
3. Open **Annotations** and choose parent-trial or current-screen scope before
   starring, tagging, or noting the observation.
4. Open **Export** and include the tabular output needed for the retained pool.

See [Data filtering](data-filtering.md) for a complete review protocol.

## Make a paper-ready figure

**Outcome:** a ready download plus reproducible settings. *About 4 minutes;
requires words or fixations.*

1. Choose a quick view and palette, then keep only layers that answer the
   question.
2. Choose static or animated output. Multipart replay changes screens at an
   explicit boundary and never draws a cross-screen saccade.
3. Open **Export**, download the figure, and include the plot configuration when
   someone else must reproduce it.
4. Optionally open **🔗 Share** for a link that carries the exact configuration,
   or 💾 **Session** to save it (with your annotations) as JSON. The image on its
   own does not reproduce the figure.

See [Exporting figures](exporting-figures.md) for raster, vector, animation, and
bulk-output details.

## Compare two readers

**Outcome:** the other readings of one text side by side, at one scale. *About 3
minutes; requires two readings sharing a text.*

1. Select the reference reading and, for multipart data, the reference screen.
2. Open **🔬 Comparisons** and choose **text id** as the comparison field. The
   grid shows other filtered trials with the same text value. Other fields can
   intentionally select trials from different texts.
3. Record the comparison settings with the figure or configuration export.

## Explore the corpus

**Outcome:** one worked question answered — how a reader's average fixation
duration moved across the experiment. *About 4 minutes; requires variation
across the loaded pool.*

1. Switch to **📊 Corpus Analysis** in the navigation. Your loaded data and
   filters stay in place, so whatever you narrowed to on the Scanpath view is
   what gets aggregated.
2. Pick the *shape* of the question, not the chart. **Per text** — one text,
   many readers. **Per sentence** — one measure combined per text/sentence pair.
   **Per reader** — one reader, all their trials. **Groups** — a cohort, or two
   compared. For "did this reader speed up?", open **Per reader**.
3. Choose the reader on the left, then set **View** to **Per-trial trend** — one
   point per trial in presentation order, the whole experiment on one axis.
4. Set the measure to **fixation duration**. Each point is that trial's mean; a
   downward slope is the reader settling in. Check the spread and the trial
   count before believing it — one short trial moves a mean a long way.
5. Optionally, **Distribution vs cohort** answers the companion question: is
   this reader unusual, or is the whole cohort like this?

With a [participant metadata](../data-format.md#participant-metadata) table
attached, **Groups** can also split the cohort by a reader attribute — the
group **Field** picker lists them marked 👤.

See [Corpus analysis](corpus-analysis.md) for the longer worked workflow.
