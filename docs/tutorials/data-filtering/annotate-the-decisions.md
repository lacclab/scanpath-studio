# Annotate the decisions

In **Annotations**, apply a consistent tag vocabulary—for example `exclude`,
`review`, `poor-calibration`, or `skimming`—and add a brief reason. Star trials
that are useful examples or approved for a figure.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/favorites_poster.webp" data-autoplay
       aria-label="Starring and tagging trials, then showing only the starred ones">
  <source src="../../../assets/workflows/favorites.mp4" type="video/mp4">
</video>

*Starring a trial and tagging it, starring another, then showing only the starred ones.*

## Turn the tags into the pool

Return to the trial filters and, under **By trial annotation**, put `exclude` in
**Excluding tags** — not in **With any of these tags**, which would keep only
the rejected trials. This turns the review decisions into the active pool
without deleting the source data. Before you narrow the pool, save the full
record with **:material/database: Data Management → Annotations → Export**: it
lists every trial you tagged, including the ones the filter now hides.

These filters read the trial's own star and tags. On a dataset with several
screens per trial, a star or tag on a single screen does not keep or hide its
trial, and its tags are not offered in the pickers; find those on
**:material/database: Data Management → Annotations**.

**Next:** [export the retained trials](export-the-retained-trials.md).
