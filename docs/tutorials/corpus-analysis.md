# Tutorial: analyse a corpus

Use this workflow to move from individual scanpaths to a text, reader, condition,
or group-level result.

## 1. Define the analysis pool

Load the corpus and apply **Trial filters** before opening Corpus Analysis. Check
the participant, text, and trial counts in **Data Inspection**. A text ID must
identify the same stimulus across readers; a trial ID identifies one reading.

## 2. Open Corpus Analysis

Select **📊 Corpus Analysis →** in the header, then choose the view that matches
the question:

| Question | View |
| --- | --- |
| How was one text read? | **Per text** |
| How does one reader behave across trials? | **Per reader** |
| How do conditions or populations differ? | **Groups** |

## 3. Choose one measure

Start with one familiar measure: total fixation duration for overall attention,
first-pass gaze duration for initial processing, or regression rate for rereading.
Keep the default aggregation and spread display until the result is understood.

For a word profile, set a minimum number of readers per word so isolated
observations do not appear as stable estimates.

## 4. Read the result with its denominator

Check how many readers, trials, or observations contribute to the chart. In
**Groups**, turn on comparison only after one cohort looks correct; then define
the second cohort and inspect the difference/effect-size output.

Use a scanpath view to investigate surprising cases. A corpus summary describes
a pattern; it does not show whether that pattern came from drift, outliers, or a
particular trial.

## 5. Download the table

Select **Download this table (CSV)** beside the relevant result. Save the active
configuration with the analysis so the filters, group definitions, and display
settings can be restored.

**Done:** you have a scoped corpus result, its contributing counts, and the table
used for downstream statistics or reporting.
