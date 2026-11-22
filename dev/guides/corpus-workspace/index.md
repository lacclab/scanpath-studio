# Corpus Analysis

The **Corpus Analysis** view summarizes reading measures by text, participant or group. It uses the selected dataset and the trials that match your filters.

## Choose a view

Open a tab, then pick a figure in its **View** menu.

| Tab                 | Use it to                                                        |
| ------------------- | ---------------------------------------------------------------- |
| **Per text**        | Compare word-by-word reading across participants                 |
| **Per participant** | Inspect one participant across trials                            |
| **Groups**          | Summarize a group of trials, or compare two groups or conditions |

Choose a **Measure** and use **Aggregate** to choose how values are combined. For views with a shaded band, **Spread** controls what the band shows. For word profiles, **Min participants per word** sets how many participants must have a value for a word to be included.

**Readings behind a word** shows the source measurements and the value each participant contributes after combining repeated readings. A blank or infinite measurement contributes no value. The profile leaves a gap at a word below the participant threshold. When two readings of a text differ in their wording or layout, **Measure on the stimulus** lets you choose which version to tint.

## Include reading measures in your Words table

Word-level views use the [reading measures in your data](https://lacclab.github.io/scanpath-studio/dev/guides/loading-data/#reading-measures), such as first fixation duration or total fixation duration. Map those columns when you import. Views of single fixations, such as **Fixation duration over time**, use the Fixations table.

## Compare groups

Under **Define groups by**, choose **Split a field** to group trials by the values of a column, or **Independent filter sets** to define a group using filters. Turn on **Compare a second group** to define group B. You can then compare the groups side by side, including their means and the difference between them. These views provide descriptive summaries; they do not run significance tests.

For a repeated-measures design, **Within-participant contrast** shows each participant's mean in A and B and the difference A − B. The summary averages only complete pairs. The CSV keeps readers who are missing either condition.

**Study inclusion and exclusions** downloads participant and reading counts for the active pool. The separate per-reading file names all matching exclusion reasons, so a reading that fails two rules counts only once.

## Save results

Under each result, **⬇ Download this table (CSV)** saves the table and **⬇ Download the recipe (JSON)** saves a record of the analysis: the dataset name, trial filters, analysis choices and counts. Keep your source data separately; the recipe contains neither the data nor the figure settings. To inspect individual trials, return to the Scanpath view.

A cohort profile's **Methods draft** records its measure, grouping, normalization, spread, reader threshold, trial filters and software version. **Compare profile revisions** saves a separate snapshot with individual reader IDs and measurements. After correcting a source file, open an earlier snapshot there to see which readings or word values changed.

### Rerun a cohort or group difference profile

Save the recipe alongside the CSV from **Per text → Cohort profile** or **Groups → Difference word profile**. Keep the source tables. For a difference profile, the recipe records each group’s constraints and which group was subtracted. New recipes save the column mappings, filename-derived columns and character-box merges used at import. Supply the original files to reproduce the CSV.

```
scanpath-studio recipe profile.recipe.json --words words.csv --fixations fixations.csv -o profile.csv
```

For the bundled demo, use `--sample` in place of the table paths. If you filtered by participant, trial or text metadata, supply the original table with `--participant-metadata`, `--trial-metadata` or `--text-metadata`. For a star or tag filter, supply the dataset’s exported annotations with `--annotations`. New recipes also record a checksum of the CSV. If the rows or values differ, the command reports the mismatch before writing the output. Older recipes have no checksum. Supply their original mappings if needed, and download a fresh recipe when one of their filter labels is ambiguous. In Python, pass the decoded recipe or its path and the normalized frames to run_analysis_recipe.

## Plot a summary in code

Start from a tidy summary table, such as a **Cohort profile** table downloaded from Corpus Analysis. A word profile needs `word_id` and `value` columns, with optional `lo` and `hi` for a band. The downloaded table names the word ID column as your data does, so rename it to `word_id` if needed. For a trend over trial order, see [Across the experiment](https://lacclab.github.io/scanpath-studio/dev/gallery/across-experiment/index.md).

Python and CLI: word profile

```
import pandas as pd
import scanpath_studio as sps

profile = pd.read_csv("profile.csv")
fig = sps.plot_corpus_figure(
    profile, kind="profile", measure_label="Total fixation duration (ms)"
)
sps.save_figure(fig, "profile.html")
```

```
scanpath-studio corpus --input profile.csv --kind profile \
  --measure-label "Total fixation duration (ms)" -o profile.html
```

[API parameters](https://lacclab.github.io/scanpath-studio/dev/api/#scanpath_studio.api.plot_corpus_figure) · [CLI options](https://lacclab.github.io/scanpath-studio/dev/cli/#corpus)
