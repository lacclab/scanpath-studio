# Narrow the trial pool

Load the dataset, then open the **filter funnel** beside the trial picker: it
holds the text and participant pickers together with the condition and annotation
filters. Start with broad dataset fields such as participant, condition,
correctness, or repeated-reading status. Use the ⇅ trial-ordering popover to
surface unusually short or long trials.

A condition filter decides each trial as a whole, from whichever table holds
the field: a difficulty level recorded only in your Words table narrows the
fixations too. A trial whose Words and Fixations tables give it different
values is left out, and a warning above the plot names it.

## Select participants by a field

To select participants by something your data does not record per trial —
native language, age, a questionnaire score — attach a participants table, one
row per participant: under **Metadata → Participants** when you add the dataset,
or later in **:material/database: Data Management → Edit dataset → Data tables &
column mapping**. Its columns then appear under **By participant** in the same
filter funnel, so you can keep, for example, the native speakers of one language
and then [review their calibration](review-candidates.md).

If the pool becomes empty, the app names the filter that emptied it and offers
to clear just that one.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/trial-filtering_poster.webp" data-autoplay
       aria-label="Narrowing the trials by condition and participant">
  <source src="../../../assets/workflows/trial-filtering.mp4" type="video/mp4">
</video>

*Stepping through the trials, then narrowing them to one condition and one participant: from 24 trials to 6.*

**Next:** [review the candidate trials](review-candidates.md).
