# Analyze texts and groups

Select **:material/bar_chart: Corpus Analysis** in the navigation, then choose
the view that matches the question:

| Question | View |
| --- | --- |
| How was one text read? | **Per text** |
| How does one participant behave across trials? | **Per participant** |
| How do conditions or populations differ? | **Groups** |

Start with one familiar measure: total fixation duration for overall attention,
first-pass reading time for initial processing, or regression rate for
rereading. For a word profile, set a minimum number of participants per word so
isolated observations do not appear as stable estimates.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/corpus-analysis_poster.webp" data-autoplay
       aria-label="Corpus Analysis: a measure on the stimulus, against surprisal, and between two groups">
  <source src="../../../assets/workflows/corpus-analysis.mp4" type="video/mp4">
</video>

*One text's total fixation duration on the stimulus and against GPT-2 surprisal, then its distribution in two groups, the Adv and Ele texts.*

## Read the result with its denominator

Check how many participants, trials, or observations contribute to the chart. In
**Groups**, turn on comparison only after one cohort looks correct; then define
the second cohort and read **Group means & difference**. It compares the two
cohorts' per-participant means and is descriptive: there is no significance test.
The caption says how many participants are in each cohort and how many are in
both; a participant in both contributes to both means, and then the standardized
difference is not shown — see
[how it is computed](../../computations.md#agg-effect-size).

Use a scanpath view to investigate surprising cases.
