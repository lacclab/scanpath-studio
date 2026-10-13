# Filter data

Decide which trials an analysis or a publication should use, and leave a
record anyone can audit — without changing the data itself. Each page below is
one task.

<div class="grid cards" markdown>

- :material-close-octagon-outline:{ .lg .middle } **[Exclude unsuitable trials](exclude-unsuitable-trials.md)**

    Mark poorly calibrated, skimming or non-reading trials and leave them out.

- :material-account-filter-outline:{ .lg .middle } **[Select participants by a field](select-participants.md)**

    Keep, for example, the native speakers of one language with good
    calibration, and export their trial IDs.

- :material-magnify-scan:{ .lg .middle } **[Find the trials an analysis needs](find-trials-for-an-analysis.md)**

    Trials with out-of-bounds, very short or very long fixations, or many
    blinks.

</div>

## How the filters work

Open the **filter funnel** beside the trial picker: it holds the text and
participant pickers together with the condition and annotation filters. A
condition filter decides each trial as a whole, from whichever table holds the
field: a difficulty level recorded only in your Words table narrows the
fixations too. A trial whose Words and Fixations tables give it different
values is left out, and a warning above the plot names it. If the pool becomes
empty, the app names the filter that emptied it and offers to clear just that
one.

## Every task ends the same way

**Check the pool.** Look at one trial from each participant or condition, then
confirm on the :material/database: **Data Management** page that the counts
under **What's in … → Stats** are plausible. They follow the filters; the
dataset table above them counts the whole dataset.

**Export it.** Use **Export → Export bundle** for the active filtered pool, with
the tidy tables, `plot_config.json` and **Annotations (JSON)**. The bundle's
`index.csv` lists the participant and trial of every trial it exported.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

*Building a zip of every trial's figures and tables (the build is fast-forwarded).*

**Keep the record.** Export the annotations from **:material/database: Data
Management → Annotations → Export**: each entry names its participant and trial
with its star, tags and note, including trials a filter now hides. (The
bundle's `annotations.json` covers only the trials it exports.) The original
data stays intact.
