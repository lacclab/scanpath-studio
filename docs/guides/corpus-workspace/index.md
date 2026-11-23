---
description: "Summarize eye-tracking reading measures by text, participant or group, plot them against word features such as surprisal, and compare groups."
---

# Corpus Analysis

Open :material/bar_chart: **Corpus Analysis** to compare a reading measure across
the trials in your current selection. The pool beside the dataset picker shows
how many trials and participants your filters include.

<figure class="sps-screenshot" markdown>
![Total fixation duration across 12 texts, with the selected text’s mean and participant range](../../assets/screenshots/corpus-analysis.webp)
</figure>

## Compare the corpus

In **Overview**, choose a **Reading measure** from your Words table. **Summarize
by** changes what a dot represents.

| Summarize by | Dot | Line |
| --- | --- | --- |
| **Text** | Mean across participants who read the text | Lowest to highest participant mean |
| **Participant** | Mean across that participant’s readings | Lowest to highest reading mean |

Each reading contributes the mean of its finite word values across all its
screens. When a participant reads a text more than once, their reading means
are averaged before they contribute to the text mean.

Comparisons across texts use the Text ID mapped in the Words table. Without
one, the overview opens by participant. The summary needs measurements for
individual readings. It excludes shared stimulus values copied across readers.

Select a dot, or choose an ID in the inspector, to see how many readings and
word rows contributed. **Open word profile** follows a text down to individual
words. **Open participant profile** compares that reader’s distribution with
the other selected readers. Both carry the chosen measure into the profile.
**Compare groups** takes the same measure into a two-group comparison.

The chart shows up to 12 groups with the highest means. The **Summary table**
and CSV include every group with the required IDs, including those with no
finite values. Their counts distinguish missing measurements from recorded zeros.

## Choose a view

You can also open a detailed tab directly and choose a figure from **View**.

| Tab | Use it to |
| --- | --- |
| **Per text** | Compare word-by-word reading across participants |
| **Per participant** | Inspect one participant across trials |
| **Groups** | Summarize a group of trials, or compare two groups or conditions |

In **Per text**, choose a **Measure** and open **Analysis settings** to set
**Aggregate**.
For views with a shaded band, **Spread** controls what the band shows.
For word profiles, **Min participants per word** sets how many participants
must have a value for a word to be included.

**Readings behind a word** shows the source measurements and the value each
participant contributes after combining repeated readings. A blank or infinite
measurement contributes no value. The profile leaves a gap at a word below
the participant threshold. When two readings of a text differ in their wording
or layout, **Measure on the stimulus** lets you choose which version to tint.

## Include reading measures in your Words table { #supply-reading-measures }

Word-level views use the [reading measures in your data](../loading-data/index.md#reading-measures),
such as first fixation duration or total fixation duration. Map those columns
when you import. Views of single fixations, such as **Fixation duration over
time**, use the Fixations table.

## Compare groups

Under **Define groups by**, choose **Split a field** to group trials by the
values of a column, or **Independent filter sets** to define a group using filters.
Turn on **Compare a second group** to define group B. You can then compare
the groups side by side, including their means and the difference between them.
These views provide descriptive summaries; they do not run significance tests.

For a repeated-measures design, **Within-participant contrast** shows each
participant's mean in A and B and the difference A − B. The summary averages
only complete pairs. The CSV keeps readers who are missing either condition.

**Study inclusion and exclusions** downloads participant and reading counts
for the active pool. The separate per-reading file names all matching
exclusion reasons, so a reading that fails two rules counts only once.

## Save results

Use the CSV download below a result to save its values. **⬇ Download the recipe
(JSON)** records the dataset name, trial filters, analysis choices and counts.
Keep the source files with the recipe so you can rerun the analysis.

A cohort profile's **Methods draft** records its measure, grouping,
normalization, spread, reader threshold, trial filters and software version.
**Compare profile revisions** saves a separate snapshot with individual reader
IDs and measurements. After correcting a source file, open an earlier
snapshot there to see which readings or word values changed.

### Rerun an overview or word profile { #rerun-a-cohort-or-group-difference-profile }

Save the recipe alongside the CSV from **Overview**, **Per text → Cohort profile**
or **Groups → Difference word profile**. For a difference profile, the recipe
records each group’s constraints and which group was subtracted.
New recipes save the column mappings, filename-derived columns and character-box
merges used at import. Supply the original files to reproduce the CSV.

```bash
scanpath-studio recipe profile.recipe.json --words words.csv --fixations fixations.csv -o profile.csv
```

For the bundled demo, use `--sample` in place of the table paths. If you
filtered by participant, trial or text metadata, supply the original table with
`--participant-metadata`, `--trial-metadata` or `--text-metadata`. For a star
or tag filter, supply the dataset’s exported annotations with `--annotations`.
New recipes also record a checksum of the CSV. If the rows or values differ,
the command reports the mismatch before writing the output. Older recipes
have no checksum. Supply their original mappings if needed, and download a
fresh recipe when one of their filter labels is ambiguous. In Python, pass
the decoded recipe or its path and the normalized frames to
[`run_analysis_recipe`][scanpath_studio.api.run_analysis_recipe].

## Plot a summary in code

Start from a tidy summary table, such as a **Cohort profile** table downloaded
from Corpus Analysis. A word profile needs `word_id` and `value` columns, with
optional `lo` and `hi` for a band. The downloaded table names the word ID column
as your data does, so rename it to `word_id` if needed.
For a trend over trial order, see [Across the experiment](../../gallery/across-experiment.md).

??? example "Python and CLI: word profile"

    === "Python"

        ```python
        import pandas as pd
        import scanpath_studio as sps

        profile = pd.read_csv("profile.csv")
        fig = sps.plot_corpus_figure(
            profile, kind="profile", measure_label="Total fixation duration (ms)"
        )
        sps.save_figure(fig, "profile.html")
        ```

    === "CLI"

        ```bash
        scanpath-studio corpus --input profile.csv --kind profile \
          --measure-label "Total fixation duration (ms)" -o profile.html
        ```

    [API parameters](../../api.md#scanpath_studio.api.plot_corpus_figure) ·
    [CLI options](../../cli.md#corpus)
