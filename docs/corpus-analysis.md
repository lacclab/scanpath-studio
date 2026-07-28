# Corpus analysis

The **Corpus Analysis** view answers questions about a *set* of trials rather
than one scanpath: what does this text look like across its readers, what does
this reader look like across their trials, and how do two groups differ. Open it
with **📊 Corpus Analysis →** in the header; **← Scanpath** goes back.

Three subtabs, all the same shape — pick a subject, pick a **View**, then set
whichever [shared controls](#the-shared-controls) that view offers.

| Subtab | Subject | Views |
| --- | --- | --- |
| **Per text** | one text, all its readers | per-reader profiles · word × reader heatmap · cohort profile · word difficulty on stimulus · measure vs feature · skip / regression rate |
| **Per reader** | one reader, all their trials | distribution vs cohort · reading summary · fixation duration over time · saccade vs fixation duration · progressive vs regressive · landing-position curve · per-trial trend |
| **Groups** | one cohort — or two, behind a toggle | distributions · word profile · reader summary · group trend — plus overlaid distributions · difference profile · paired bars · effect size · two-group heatmap |

## Before you read a number

**The trial filter defines the corpus.** Every view reads the filtered frames,
but the filter controls aren't on this screen — *Narrow by* and the *More*
popover live in the **Scanpath Visualization** view. Set them there and switch
back; the filter applies to both views.

**A narrow filter still draws a confident-looking plot.** Leave one reader on a
text and you still get a "cohort" profile: one reader's numbers with a zero-width
band that looks like certainty rather than *n* = 1. Use
[Min readers per word](#min-readers-per-word) to make that visible.

**Two settings from the other view reach in.** *Experimental Setup* (monitor,
font, spacing) drives the one spatial view, *Word difficulty on stimulus* — see
[True-to-scale rendering](rendering.md). The rail's heatmap colourscale, `Linear`/
`Log` scaling and label styling feed that view and the word × reader heatmap; the
rest use fixed palettes.

---

## Per text — one text, many readers

Pick a **Text** and a **View**. The dropdown is sorted by reader count, so the
most-read text is selected by default.

!!! warning "In OneStop, difficulty is part of the text ID"
    `2_2_1_Adv` and `2_2_1_Ele` count as two different texts here, with different
    word counts and different word numbering. So anything per-word — profiles,
    heatmaps, the difference profile — is *within* one difficulty variant. Take
    cross-difficulty questions to the distribution, paired-bar or effect-size
    views, which pool across texts.

**Per-reader profiles** — *does every reader slow down at the same places?* One
panel per reader, word position on X, your measure on Y. **Cohort mean** draws
the same group line in every panel so deviations read directly. Capped at 12
readers, taken in ID order — narrow the participant filter if you need a specific
set.

**Word × reader heatmap** — *which words were hard for everyone, and which readers
were slow everywhere?* Rows are readers, columns are words. A bright vertical
stripe is a word the whole cohort struggled with; a bright row is a uniformly slow
reader. One colour scale spans all cells, so a single very long fixation
compresses everything else — switch to a rate measure or turn on **Z-score within
reader** if one reader is washing out the map.

**Cohort profile** — *what does the average reader look like, and how much do
readers disagree?* A centre line with a band set by **Spread**, which matters more
here than anywhere: **SD** is the spread of the readers (never narrows with more
data), **SEM** is the precision of the line (does), **IQR** is the robust choice
with `median`, and **Bootstrap CI** is a 95% percentile bootstrap with a fixed
seed, so it's reproducible.

**Word difficulty on stimulus** — *where on the page is the difficulty?* The text
laid out true-to-scale with each word box tinted by the cross-reader aggregate. No
fixations are drawn.

!!! note "No guard on this view"
    There is **no min-readers guard** here — a word read by one reader is tinted
    exactly as confidently as a word read by all of them. Check coverage in
    *Cohort profile* first if your filter is narrow. Z-scoring is also disabled
    (there's no reader axis left after aggregating).

**Measure vs feature** — *does the measure track a property of the word?* Your
measure against GPT-2 surprisal, word frequency, word length or part of speech —
whichever of the four your data actually carries. Numeric features get a scatter
with a trend line and Pearson *r*; part of speech gets one box per tag.

!!! warning "This is a look, not a model"
    The correlation runs over the words of a **single text** — about 100 points
    for a OneStop paragraph — so *r* is noisy and moves with the text you pick.
    Length, frequency and surprisal are also strongly collinear and nothing here
    separates them. Export the table and fit the model you actually want.

**Skip / regression rate** — *which words got skipped, and which pulled
regressions back to them?* Grouped bars per word. No measure picker: the two rates
*are* the measure. Note the min-readers guard counts **rows** here rather than
distinct readers, so with repeated readings in scope a word can clear a threshold
of 4 on two readers.

---

## Per reader — one reader, many trials

Pick a **Reader** and a **View**. "Cohort" means *the other readers left by the
trial filter*, so narrowing the filter changes the comparison, not just the
target.

The fixation-level views need saccade and regression information. When your source
only ships per-word EyeLink measures, the app derives them from `word_id`; if that
is missing too, those views say what they need, and the rest render an empty
figure whose title ends in *(no data)* — that title is the signal, not a bug.

**Distribution vs cohort** — violin or box of the measure, this reader against
the cohort.

!!! warning "Z-scoring erases exactly what this view compares"
    **Z-score within reader** centres *every* reader at zero, including the one
    you selected. On the bundled demo, raw mean fixation duration is 218 ms for
    reader `l37_1129` vs 170 ms for the cohort; z-scored, both are 0.00. Use it
    only when you care about the *shape* of the distribution and have accepted
    that the level difference is gone.

**Reading summary** — up to six statistics (reading speed, mean fixation duration,
fixation count, regression rate, skip rate, saccade amplitude), each with this
reader's percentile in the cohort. Statistics whose column is missing are omitted
rather than shown as zero.

!!! note "Percentiles need a cohort"
    The reader is counted in their own pool, so with *k* readers the percentile
    can only take *k* values and the top reader never reaches 100. The bundled
    demo has two readers with fixations, so every percentile there is 0 or 50. At
    small *n*, download the whole cohort table instead.

**Fixation duration over time** — a per-fixation measure against position in the
trial, averaged over this reader's trials, with a ±SEM band.

!!! warning "Use *order in trial*, not *timestamp ms*"
    The X axis groups by exact value, with no binning. `order_in_trial` is a small
    integer, so each point averages across trials as intended. `timestamp_ms` is
    the raw recording clock and is nearly unique per fixation — the same reader has
    1215 fixations at 1195 distinct timestamps — so the "trend" becomes a scatter
    of individual fixations with a zero-width band.

**Saccade vs fixation duration** — the classic oculomotor plot: a binned 2-D
histogram of saccade amplitude against fixation duration. Careful reading
concentrates at short saccades and moderate durations; skimming stretches the
amplitude axis.

!!! warning "The axis says px — check what your source shipped"
    Saccade amplitude is passed through whenever your data has it, and the app
    computes it (as pixel distance) only when it doesn't. EyeLink reports its
    amplitude columns in **degrees of visual angle** — so on the bundled demo the
    axis reads "px" while the values are degrees, a constant ~78× apart. Take the
    unit and the direction from your source, not from the label.

**Progressive vs regressive** — per trial, a stacked bar of progressive and
regressive counts with the regression share as a line.

!!! warning "The bars count fixations, and unassigned ones count as progressive"
    A fixation is regressive when its word is behind the furthest word reached so
    far in that trial. A fixation with **no** word — out of text, or a failed
    assignment — fails that test and lands in the progressive bar, so a trial with
    poor fixation→word assignment reads as artificially progressive rather than
    dropping out.

**Landing-position curve** — where the *first* fixation on each word fell inside
the word box, 0 = start, 1 = end. The preferred-viewing-location curve. It pools
all word lengths, so it isn't a per-length PVL curve, and fractions are clipped
into `[0, 1]`, so fixations landing outside a box pile up on the end bins.

**Per-trial trend** — the measure per trial against the trial's position in the
session: does this reader slow down as the session goes on?

!!! note "One reader means no band"
    A single reader contributes one trial per index, so the band collapses onto
    the line. That's *n* = 1, not precision. The band only carries information in
    *Group trend*, where several readers share an index.

    The axis uses your data's own trial index when it has one — which is why the
    bundled demo doesn't start at 1: each reader's 12 sampled trials keep their
    real session positions. Otherwise trials are ordered by timestamp, and the
    view says so.

---

## Groups — one cohort, or two

Profiles a single cohort by default; flipping **Compare a second group** defines a
Group B and swaps in the two-cohort views.

**Defining a group.** Either **split a field** — pick one categorical column
(difficulty, reading regime, reading number, correctness, genre, session,
participant, text) and assign its values to A and B — or build **independent
filter sets**, each with its own participant / text / condition multiselects. Use
the second for groups that aren't a clean split of one column.

!!! warning "A words-only field can't split the fixation table"
    Groups are applied per table. Define a group on a column the fixations table
    doesn't have and the fixation frame comes back unfiltered, so the
    fixation-level views would silently compare all-vs-all. The app warns and names
    the field. This can only happen with independent filter sets — the split-a-field
    picker already restricts itself to columns both tables carry.

Read the caption under the group definition before reading any plot: one group
reports its reader **and** fixation count, two groups report reader counts only.

**One group:** distributions (pooled violin/box) · word profile (the cohort
profile within the group) · reader summary table (one row per reader, sortable and
downloadable — good for finding outliers) · group trend, with optional faint
per-reader lines behind it, which are the honest way to see whether a group slope
is real or one reader's.

**Two groups:** overlaid distributions · difference word profile (per-word A − B
along the text) · paired summary bars (several measures at once, one subplot each
so differing units keep their scale) · effect size + test (means, mean difference,
Cohen's *d*, Mann–Whitney or Welch's *t*) · two-group word heatmap.

!!! warning "The difference profile needs a field that varies *within* one text"
    The per-word views fix a text first and split second. If your split field is
    baked into the text ID — difficulty in OneStop — then one group is empty for
    every word: the profile comes back all-blank and the heatmap draws a single
    row. Split on something that varies within a text (reading regime, reading
    number, correctness, participant), or take the difficulty question to the
    distribution / paired-bar / effect-size views.

!!! danger "*n* is observations, not readers"
    The test and Cohen's *d* treat every row as independent — that's words ×
    readers, or fixations. Words within a reader and readers within a group are
    not independent, so the *p* value is anti-conservative, often dramatically: a
    handful of readers can put *n* in the thousands. The app labels these views
    *exploratory, not pre-registered* for this reason. Treat the effect size as a
    screening statistic and fit a mixed-effects model on the exported table before
    claiming anything.

---

## The shared controls

**Measure.** One picker per subtab, shared by its views. Only measures whose
column exists in your data are listed, and views that plot a per-word profile
restrict the list to word-level measures. TFD is the default.

| Word-level | Fixation-level |
| --- | --- |
| Total fixation duration (TFD) · first fixation (FFD) · first-pass gaze (FPRT) · regression path (RPD) · fixations per word · skip rate · regression-in rate · regression-out rate | fixation duration · saccade amplitude |

Rate measures are 0/1 flags averaged into a proportion. Pre-computed EyeLink
values win over natively computed ones — see [Data format](data-format.md).

!!! note "Your measure resets when you cross into a word-only view"
    In **Groups**, some views take any measure and some take only word-level ones,
    but they share one picker. Picking a fixation measure and switching to *Word
    profile*, *Difference profile* or *Two-group heatmap* silently drops back to
    TFD — and switching back doesn't restore it.

**Aggregate** (`mean` / `median` / `sum`) means something different per view, and
each tooltip says which: across readers for a per-word profile, within a trial for
the trends, across rows for the bars.

**Spread** (`SD` / `SEM` / `IQR` / `Bootstrap CI`) sets the band or error bar. With
`sum`, SD and SEM fall back to a bootstrap — the spread of individual observations
says nothing useful about a total.

**Z-score within reader** replaces each value with its z-score inside that reader's
data, so fast and slow readers compare on shape rather than level. Disabled for
rate measures. The scope differs by view: per-text views z within the selected
text, distribution views z over everything that reader contributes. That's the
right move when both groups draw on the same readers, and the wrong one when the
groups *are* different readers.

### Min readers per word

The observation guard: words backed by fewer readers than the threshold are
dropped, and a caption says how many. At the default of 1 nothing is dropped and
no caption appears.

### Download this table (CSV)

Most views hand you the exact tidy table behind the plot. The distribution,
oculomotor-scatter, landing-curve and effect-size views have no download —
recompute those from the raw tables in the Scanpath view's **Export** subtab.

## Getting the numbers out headlessly

These views are UI-only — unlike the single-trial scanpath, they have no CLI flag
or [Python API](api.md) entry point, and the CSV download is the supported route.

If you're scripting anyway, the aggregation helpers are plain pandas over the same
normalized frames:

```python
import scanpath_studio as sps
from scanpath_studio import aggregation

words, fixations = sps.load_sample_data()

profile = aggregation.cohort_word_profile(
    words, "unique_text_id", "2_1_1_Ele", aggregation.MEASURES["tfd"],
    agg="mean", spread="SD", min_readers=2,
)
#    word_id       value          lo          hi  n  enough word_text
# 0        0  288.333333   49.598473  527.068193  3    True     There
# 1        1  150.333333   18.969970  281.696697  3    True       are
```

`value` is the cross-reader aggregate, `lo`/`hi` the band, `n` the contributing
readers and `enough` the guard — the same columns *Cohort profile* plots.

!!! note "Internal surface"
    `scanpath_studio.aggregation` is not part of the documented public API. Its
    signatures can change between releases without a deprecation path.

## See also

- [Getting started](getting-started.md) — install, launch, first figure.
- [Data format](data-format.md) — which columns feed which measure.
- [OneStop](onestop.md) — the corpus behind the demo, and what its conditions mean.
- [True-to-scale rendering](rendering.md) — how the stimulus view sizes the text.
- [Export & troubleshooting](export-troubleshooting.md) — getting figures out.
