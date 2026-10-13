# Export the retained trials

## Check the pool

Check at least one trial from each participant or condition. Then open the
:material/database: **Data Management** page and confirm that the participant,
text, trial, fixation, and word counts under **What's in … → Stats** are
plausible. Those follow the filters; the dataset table above them counts the
whole dataset.

## Export it

Use **Export → Export bundle** for the active filtered pool. Include the tidy
tables, `plot_config.json` and **Annotations (JSON)** — the tags and notes are
the human review record; export figures only if they are part of the analysis
record.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../../../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

*Building a zip of every trial's figures and tables (the build is fast-forwarded).*

For the list of trials you marked, export the annotations
(**:material/database: Data Management → Annotations → Export**): each entry names
its participant and trial with its star, tags and note. The bundle's `index.csv`
lists the participant and trial of every trial it exported.

**Done:** the original data remains intact, the retained trials are in the
export bundle, and each manual decision has a tag and a reason in the
annotations file you exported from the Data Management page. (The bundle's
`annotations.json` covers only the trials it exports.)
