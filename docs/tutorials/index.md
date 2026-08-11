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

The same workflows are available inside the app under **Help → 🧭 Tutorials**.
The chooser explains the outcome, prerequisite, and time before starting. Each
tutorial keeps its own progress, can open the relevant view or subtab with
**Show me / Open this panel**, and never changes data, filters, annotations, or
scientific settings for you.

## Load your own data

**Outcome:** parsed words, fixations, and mappings visibly checked. *About 3
minutes.*

1. Open **Data source → Add data**, upload either or both reports, and check the
   proposed mappings. Map **Multipart screens** only when one logical trial has
   several coordinate spaces.
2. Finish setup, choose a trial, and open **Data Inspection**.
3. Check row and trial counts, coordinate ranges, the active mapping, and—when
   present—the ordered screen catalogue and per-screen canvas sizes.

The longer data-collection workflow is in [Data collection](data-collection.md),
and every accepted field is in [Data format](../data-format.md).

## Filter and annotate trials

**Outcome:** reviewed trials marked and ready for ID export. *About 4 minutes;
requires at least one trial.*

1. Use **Filter by** and **More** to define the review pool.
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

See [Exporting figures](exporting-figures.md) for raster, vector, animation, and
bulk-output details.

## Compare two readers

**Outcome:** comparable same-text scanpaths and similarity scores. *About 3
minutes; requires two readings sharing a text.*

1. Select the reference reading and, for multipart data, the reference screen.
2. Open **Comparisons**, choose the grouping field, and compare the grid and
   ranking. Candidates must share the text and screen, so different coordinate
   spaces are not overlaid.
3. Record the comparison settings with the figure or configuration export.

## Explore the corpus

**Outcome:** a reader-, text-, or group-level question answered. *About 3
minutes; requires variation across the loaded pool.*

1. Switch to **Corpus Analysis** from the header.
2. Choose **Per text**, **Per reader**, or **Groups** to match the unit of the
   question.
3. Interpret the sample size and distribution or effect together, then download
   the displayed table.

See [Corpus analysis](corpus-analysis.md) for the longer worked workflow.
