# Tutorial: analyse a corpus

Use this workflow to move from individual scanpaths to a text, reader, condition,
or group-level result.

Corpus Analysis shows the reading measures your interest-area table brings
(mapped under **Reading measures** when you add or edit a dataset); it computes
none itself. The bundled demo has them. With fixations alone, compute the
measures with your own pipeline (EyeLink Data Viewer's interest-area report, for
example), join them onto your AOI table by participant, trial and word ID, and
load that; EyeLink's `IA_*` names map themselves.

## 1. Define the analysis pool

Load the corpus and narrow the trial pool, with the Scanpath view's filter or
**Edit filters** at the top of Corpus Analysis. The line beside the dataset
picker there counts the trials and readers left and names each active filter;
**Clear** resets them. The participant, text, and trial counts under
**What's in … → Stats** on the :material/database: **Data Management** page
follow the filters too. A text ID must identify the same stimulus across
readers; a trial ID identifies one reading.

## 2. Open Corpus Analysis

Select **:material/bar_chart: Corpus Analysis** in the navigation, then choose the view that
matches the question:

| Question | View |
| --- | --- |
| How was one text read? | **Per text** |
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
the second cohort and read **Group means & difference**. It compares the two
cohorts' per-reader means and is descriptive: there is no significance test.
The caption says how many readers are in each cohort and how many are in both;
a reader in both contributes to both means, and then the standardized
difference is not shown — see
[how it is computed](../computations.md#agg-effect-size).

Use a scanpath view to investigate surprising cases.

## 5. Download the table

Select **Download this table (CSV)** beside the relevant result, and
**Download the recipe (JSON)** beside it. The recipe records how the table was
made: the app version, the dataset's name, the trial filters, the view's text,
screen, measure, aggregation, normalization, spread, minimum readers and group
definitions, and the trial and reader counts. It names the dataset rather than
copying it, and holds no figure settings: a **:material/share: Share → File**
settings file keeps those and the trial selection, but no trial filters. A
Share link carries neither the filters nor the Corpus Analysis choices.

**Done:** you have a scoped corpus result, its contributing counts, the table
used for downstream statistics or reporting, and the recipe that made it.
