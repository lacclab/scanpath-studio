# Tutorial: analyse a corpus

Use this workflow to move from individual scanpaths to a text, reader, condition,
or group-level result.

Corpus Analysis shows the reading measures your interest-area table brings
(mapped under **Reading measures** when you add or edit a dataset); it computes
none itself. The bundled demo has them. For fixations alone, compute them with
[`compute_word_metrics`][scanpath_studio.api.compute_word_metrics], join its
columns onto your AOI table by participant, trial and word ID, and load that;
the measures map themselves by name.

## 1. Define the analysis pool

Load the corpus and narrow the trial pool before opening Corpus Analysis. Check
the participant, text, and trial counts under **What's in the … dataset → Stats**
on the :material/database: **Data** page, which follow the filters. A text ID must
identify the same stimulus across readers; a trial ID identifies one reading.

## 2. Open Corpus Analysis

Select **:material/bar_chart: Corpus Analysis** in the navigation, then choose the view that
matches the question:

| Question | View |
| --- | --- |
| How was one text read? | **Per text** |
| How was one sentence read, across readers? | **Per sentence** |
| How does one reader behave across trials? | **Per reader** |
| How do conditions or populations differ? | **Groups** |

## 3. Choose one measure

Start with one familiar measure: total fixation duration for overall attention,
first-pass gaze duration for initial processing, or regression rate for rereading.

For a word profile, set a minimum number of readers per word so isolated
observations do not appear as stable estimates.

## 4. Read the result with its denominator

Check how many readers, trials, or observations contribute to the chart. In
**Groups**, turn on comparison only after one cohort looks correct; then define
the second cohort and inspect the difference/effect-size output. It compares
the two cohorts' per-reader means, so a reader in both cohorts counts on both
sides; the test is exploratory, with no correction for many comparisons — see
[how it is computed](../computations.md#agg-effect-size).

Use a scanpath view to investigate surprising cases.

## 5. Download the table

Select **Download this table (CSV)** beside the relevant result, and note the
trial filters and cohort definitions that produced it beside the file. Neither
travels anywhere else: a **:material/share: Share → File** settings file keeps the figure
settings and trial selection, but not the filter selections or the Corpus
Analysis choices, and a Share link carries neither.

**Done:** you have a scoped corpus result, its contributing counts, and the table
used for downstream statistics or reporting.
