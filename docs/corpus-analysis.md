# Corpus analysis

The **Corpus Analysis** view answers questions about a *set* of trials rather
than one scanpath: what does this text look like across its readers, what does
this reader look like across their trials, and how do two cohorts differ. Open it
with the **📊 Corpus Analysis →** button in the header; **← Scanpath** goes back.

It has three subtabs, and every one of them follows the same shape — pick a
subject (a text, a reader, a group), pick a **View**, then set whichever of the
shared controls that view exposes (measure, aggregation, spread, normalization,
observation guard) in the row above the plot.

| Subtab | Subject | Views |
| --- | --- | --- |
| **Per text** | one text, all its readers | per-reader profiles · word × reader heatmap · cohort profile · word difficulty on stimulus · measure vs feature · skip / regression rate |
| **Per reader** | one reader, all their trials | distribution vs cohort · reading summary · fixation duration over time · saccade vs fixation duration · progressive vs regressive · landing-position curve · per-trial trend |
| **Groups** | one cohort — or two, behind a toggle | distributions · word profile · reader summary table · group trend — plus overlaid distributions · difference word profile · paired bars · effect size + test · two-group heatmap |

## What's in scope

Every view reads the **filtered** words and fixations frames, so the active trial
filter defines the corpus. Two things are worth knowing before you interpret a
number:

- **The filter controls are not on this screen.** *Narrow by* (Text,
  Participant) and the *More* popover (reading regime, difficulty, repeated
  reading, correctness, favourites, tags) live above the plot in the **Scanpath
  Visualization** view. Set them there, then switch back — the filter is stored
  in the session and applies to both views.
- **Filtering is global, but so is the fallout.** A filter that leaves one reader
  on a text will still draw a "cohort" profile for it: one reader's numbers, with
  a zero-width spread band that looks like certainty rather than *n* = 1. Use
  *Min readers per word* (below) to make that visible.

Two sidebar/rail settings also reach in:

- **Experimental Setup** (sidebar) — monitor size, font, line spacing, text
  scaling. Only the *Word difficulty on stimulus* view is spatial, and it uses
  these exactly as the scanpath plot does. See
  [True-to-scale rendering](rendering.md).
- **Visualization controls** (the Scanpath view's right rail) — the heatmap
  colourscale, colour scaling (`Linear` / `Log`), colorbar orientation and font,
  word-label styling, background colour. These feed the *Word difficulty on
  stimulus* view; the *Word × reader heatmap* picks up the colourscale. The other
  figures use fixed palettes.

---

## Per text — one text, many readers

Pick a **Text** and a **View**. The dropdown annotates each text with its reader
count and is sorted by that count, so the most-read text is selected by default.
The count is distinct readers in the **words** table, which can include readers
whose fixations are missing or filtered out.

!!! warning "What counts as one text"
    The text id is the first of `unique_text_id`, `text_id`,
    `unique_paragraph_id`, `paragraph_id` present in the data. In OneStop that id
    **includes the difficulty variant** — `2_2_1_Adv` and `2_2_1_Ele` are two
    different texts here, with different word counts and different `word_id`
    numbering. Anything per-word (profiles, heatmaps, the difference profile) is
    therefore *within* one variant; cross-difficulty comparison belongs in the
    distribution / paired-bar / effect-size views, which pool across texts.

### Per-reader profiles

**Question:** does every reader slow down at the same places, or is the pattern
idiosyncratic?

One stacked panel per reader, X = `word_id` in reading order, Y = the chosen
measure. The **Cohort mean** checkbox draws the same cross-reader centre line
(dotted grey) in every panel, so a reader's deviations from the group read
directly.

Capped at 12 readers; the title then says *showing 12 of N readers* rather than
truncating silently. Those are the first 12 by participant id, not the 12 with
the most data — narrow the participant filter if you need a specific set.
Repeated readings of the same word by the same reader are collapsed by the
**Aggregate** setting before plotting.

### Word × reader heatmap

**Question:** which words were hard for *everyone*, and which readers were slow
*everywhere*?

The same per-(reader, word) table as above, collapsed to a matrix: rows =
readers, columns = `word_id`, colour = measure. A bright vertical stripe is a
word the whole cohort struggled with; a bright row is a uniformly slow reader.

Caveat: one shared colour scale spans all cells, so a single very long fixation
compresses everything else. Switch the measure to a rate, or turn on **Z-score
within reader**, if one reader is washing out the map.

### Cohort profile

**Question:** what does the "average reader of this text" look like, and how much
do readers disagree?

A centre line (the **Aggregate** across readers of each reader's per-word value)
with a shaded band set by **Spread**. This is the view where the spread choice
matters most:

- **SD** — spread of the readers themselves. Widens with reader variability,
  never with sample size.
- **SEM** — precision of the centre line. Shrinks as readers are added.
- **IQR** — 25th/75th percentiles; robust, and the right choice with `median`.
- **Bootstrap CI** — 95 % percentile bootstrap of the aggregate (1000 resamples,
  fixed seed, so re-running gives the same band).

**Min readers per word** drops words backed by fewer readers than the threshold
and captions how many were hidden.

### Word difficulty on stimulus

**Question:** where on the page is the difficulty?

The text is laid out true-to-scale and each word box is tinted by the
cross-reader aggregate of the measure. No fixations are drawn — this is a
corpus-level version of the word heatmap from the scanpath view, so it honours
the same colourscale, `Linear`/`Log` scaling, colorbar and label settings. The
heatmap *style* is fixed to **Word boxes** here; the rail's interpolated and
density styles need fixations, and there are none.

!!! note "No guard on this view"
    **Z-score within reader** is disabled here (there is no reader axis left
    after aggregating) and there is **no min-readers guard** — a word read by one
    reader is tinted exactly as confidently as a word read by all of them. Check
    coverage in the *Cohort profile* view first if the filter is narrow.

The CSV download for this view contains `word_id` and `value` only.

### Measure vs feature

**Question:** does the measure track a lexical property of the word?

Per-word cross-reader aggregate on Y, a bundled linguistic feature on X. A
numeric feature draws a scatter with an OLS trend line and Pearson *r* in the
title; a categorical one (part of speech) draws one box per tag.

Four features can be picked, and only those whose column is in the loaded words
table are listed: **GPT-2 surprisal** (`gpt2_surprisal`), **word frequency**
(`wordfreq_frequency`), **word length** (`word_length`) and **part of speech**
(`universal_pos`). Other columns the OneStop tables ship — `subtlex_frequency`,
`ptb_pos`, `dependency_relation` — are not in the picker. With none of the four
present the view says so instead of drawing.

!!! warning "This is a look, not a model"
    The correlation is computed over the words of a **single text** — around 100
    points for a OneStop paragraph — so *r* is noisy and moves with the text you
    pick. Length, frequency and surprisal are also strongly collinear and nothing
    here partials them out. Export the tidy table and fit the model you actually
    want.

### Skip / regression rate

**Question:** which words got skipped, and which pulled regressions back to them?

Grouped bars per word: `skip_flag` rate and `regression_in_flag` rate, averaged
over every row for that word. This view has no measure picker — the two rates
*are* the measure.

!!! note "The guard counts rows, not readers"
    Everywhere else *Min readers per word* counts distinct readers. Here it
    counts **word rows** — one per reader per reading — so with repeated-reading
    trials in scope a word can clear a threshold of 4 on two readers.

---

## Per reader — one reader, many trials

Pick a **Reader** and a **View**. In *Distribution vs cohort*, "Cohort" means
*the other readers left by the trial filter* — narrowing the filter changes the
comparison, not just the target. (*Reading summary* is the exception: its
percentile pool includes the selected reader. See below.)

Fixation-level views need `is_regression` / `saccade_amplitude` on the fixation
table. When the source ships pre-aggregated EyeLink IA measures on the words
table and never enriches the fixation stream, the app derives them on the fly
from `word_id`. If `word_id` is missing too, the derivation is skipped: *Landing-
position curve* and *Progressive vs regressive* then say what they need, and the
rest fall back to an empty figure whose title ends in *(no data)* — that title is
the signal, not a rendering bug.

### Distribution vs cohort

Violin or box of the measure for **This reader** against **Cohort**. Works for
both word-level and fixation-level measures.

!!! warning "Z-scoring erases exactly what this view compares"
    **Z-score within reader** centres *every* reader at zero, including the one
    you selected. On the bundled demo with reader `l37_1129`, raw mean fixation
    duration is 218 ms for the reader vs 170 ms for the cohort; z-scored, both
    are 0.00. Use the toggle only when you care about the *shape* of the
    distribution (skew, spread, bimodality) and have already accepted that the
    level difference is gone.

### Reading summary

A strip of up to six statistics — reading speed (wpm), mean fixation duration,
fixation count, regression rate, skip rate, mean saccade amplitude — each showing
the reader's **percentile** within the cohort in scope. Statistics whose backing
column is absent are omitted rather than shown as zero.

Reading speed is distinct `(trial, word)` rows divided by total reading time,
where a trial's reading time is *last fixation end − first fixation start*
(falling back to the sum of fixation durations when there are no timestamps).
That counts every word of the text, not just fixated ones.

!!! note "Percentiles need a cohort"
    The percentile is the share of readers in scope scoring strictly below this
    one, and the reader is counted in that pool — so with *k* readers it can only
    take the values 0, 100/*k*, …, 100(*k*−1)/*k*, and the top reader never
    reaches 100. The bundled demo has two readers with fixations, so every
    percentile there is either 0 or 50. The cohort is drawn from the fixation
    table when there is one, so readers present only in the words table are not
    counted. The download button hands you the whole cohort summary table, which
    is the honest thing to look at at small *n*.

### Fixation duration over time

Mean of a **per-fixation** measure against position within the trial, averaged
over this reader's trials, with a ±SEM band. Picking a word-level measure here
prints a prompt instead of a plot.

!!! warning "Use `order in trial`, not `timestamp ms`"
    The X axis groups by *exact* value — there is no binning. `order_in_trial` is
    a small integer, so each point averages across this reader's trials as
    intended (on the bundled demo, 164 points backed by up to 12 trials each).
    `timestamp_ms` is the raw recording clock and is nearly unique per fixation:
    the same reader has 1215 fixations at 1195 distinct timestamps, and 1176 of
    those 1195 points average a single fixation. The "trend" is then a scatter of
    individual fixations with a zero-width band.

### Saccade vs fixation duration

The classic oculomotor plot: a binned 2-D histogram (≈40 × 40 bins) of saccade
amplitude (Y) against fixation duration in ms (X), for this reader's fixations.
Careful reading concentrates at short saccades and moderate durations; skimming
stretches the amplitude axis. The title reports the *n* that survived.

!!! warning "The amplitude axis says px — check what your source actually shipped"
    `saccade_amplitude` is a passthrough whenever the data ships one
    (`saccade_amplitude`, `NEXT_SAC_AMPLITUDE`, `PREVIOUS_SAC_AMPLITUDE`); the
    app computes it — as the pixel distance from the *previous* fixation — only
    when no such column exists. EyeLink reports its `*_SAC_AMPLITUDE` columns in
    **degrees of visual angle**, and the one OneStop ships is
    `NEXT_SAC_AMPLITUDE`, i.e. the *outgoing* saccade. So on the bundled demo the
    axis (and the `mean_saccade_px` column in the *Reading summary* download)
    reads "px" while the values are degrees: they run 0.13–22.3 where the
    matching pixel distances run to 1813, a constant ~78× apart. Take the unit
    and the direction from your source, not from the label.

No CSV download on this view.

### Progressive vs regressive

Per trial: a stacked bar of progressive and regressive counts, with the
regression *share* as a line on a secondary axis.

The flag is `is_regression`, and it is defined **per fixation**: a fixation is
regressive when its `word_id` is behind the furthest word reached so far in that
trial. That is the go-past sense of "in regressed territory", not a saccade
classification — the five-way reading classes (forward / skip / refixation /
return sweep / regression) used for saccade colouring in the scanpath view are a
separate, render-time computation and do not feed this plot.

!!! warning "The bars count fixations, and unassigned ones count as progressive"
    The figure's axis is labelled *Saccade count*, but the stack is a count of
    **fixations** — `regressive` is the number of flagged fixations and
    `progressive` is simply the rest. A fixation with no `word_id` (out of text,
    or a failed assignment) compares false against the running maximum, so it
    lands in the progressive bar. A trial with poor fixation→word assignment
    therefore reads as artificially progressive rather than dropping out. Only a
    fixation table with no `word_id` column at all — where the flag can't be
    derived — replaces the plot with a prompt.

### Landing-position curve

Histogram of where the **first** fixation on each word fell inside that word's
box — 0 = word start, 1 = word end. The preferred-viewing-location curve. The bin
count is requested as 20; Plotly rounds it to a tidy bin width, so expect roughly
that many.

The values come from `first_fix_x` on the words table when present (skipped words
excluded), otherwise from the earliest fixation on each `(participant, trial,
word)` joined to the box.

Caveat: the landing fraction pools all word lengths, so this is not a per-length
PVL curve, and fractions are clipped into `[0, 1]` — fixations that landed before
or past the box pile up on the end bins rather than showing as outliers.

### Per-trial trend

The measure aggregated within each trial, plotted against the trial's position in
the session — does this reader slow down as the session goes on? **Aggregate**
controls only the *within-trial* collapse; the trials sharing a trial index are
then always averaged, and the band is their ±SEM.

!!! note "One reader means no band"
    A single reader normally contributes one trial per trial index, so the SEM is
    0 and the band collapses onto the line. That is not a claim of precision —
    it is *n* = 1. The band only carries information in *Group trend*, where
    several readers share an index.

Trial order uses an explicit `trial_index` / `TRIAL_INDEX` column when the data
has one — the bundled OneStop demo does, which is why its axis does not start at
1: each reader's 12 sampled trials keep their real session positions (13–24,
16–27 and 35–46 for the three demo readers). Otherwise trials are ranked by
earliest `timestamp_ms`, falling back to first-appearance row order when there
are no timestamps, and the view captions *"Trial order derived from fixation
timestamps"* so you know the axis is inferred. Note that a **word-level** measure
reads the words table, which usually carries no timestamps at all — there the
inferred order is row order, whatever the caption says.

---

## Groups — one cohort, or two

The **Groups** subtab profiles a single cohort by default; flipping **Compare a
second group** defines a Group B and swaps in the two-cohort views. A single
group is just the one-group case of a comparison, which is why they share a tab.

### Defining a group

Two modes, both compiling to the same thing — a `{column: [allowed values]}`
spec, AND-ed across columns and OR-ed within one:

- **Split a field** — pick one categorical column and assign its values to A and
  B. The picker offers columns present in **both** tables with 2–60 distinct
  values: difficulty, reading regime (`question_preview`), reading number,
  answer correctness, genre, session, gender, participant, and the text column.
- **Independent filter sets** — build each group from its own participant / text
  / condition multiselects, with its own label. Use this for groups that aren't a
  clean split of one column (specific reader lists, a condition crossed with a
  text subset).

!!! warning "A words-only field can't split the fixation table"
    Groups are applied per frame. If a group is defined on a column present in
    the words table but absent from the fixations table, the fixation frame comes
    back unfiltered and the fixation-level views — distributions for a
    per-fixation measure, paired bars, effect size — would silently compare
    all-vs-all. The app warns and names the offending field; switch to a field
    both tables carry for those views. This can only happen in *Independent
    filter sets*: the *Split a field* picker already restricts itself to columns
    both tables carry.

Read the caption under the definition before reading any plot. One group reports
its reader count **and** its fixation count; two groups report reader counts only
— if a fixation-level view looks wrong, check the fixation counts yourself in the
**Data Inspection** subtab.

### One group

- **Distributions** — one violin/box of the measure pooled across the group.
- **Word profile** — the cohort profile (centre + spread band + min-readers
  guard) computed within the group, for one text. Z-scoring is not offered here.
- **Reader summary table** — one row per reader with the same statistics as the
  *Reading summary* card. Sort it to find outliers; download it as CSV.
- **Group trend** — the trial-index trend pooled over the group, with an optional
  faint per-reader line behind it. The faint lines are the honest way to see
  whether a group-level slope is real or one reader's. As in *Per-trial trend*,
  **Aggregate** applies within a trial; across the trials that share an index the
  combination is always the mean, and the band their ±SEM.

### Comparing two groups

- **Overlaid distributions** — both groups' distributions on shared axes.
- **Difference word profile** — per-word A − B along the text, diverging colour
  scale, zero reference line. *Min/grp* requires that many readers **in each
  group** before a word is kept.
- **Paired summary bars** — several measures at once (fixation duration, saccade
  amplitude and TFD by default), one subplot per measure so differing units keep
  their own scale, error bars from the **Error bars** spread (SEM by default).
  Word measures read the words table, fixation measures the fixation table. Error
  lengths are clamped at zero, so an asymmetric band that falls on the wrong side
  of the centre — `mean` with `IQR` on skewed data — shows as a one-sided bar.
- **Effect size + test** — group means with *n*, the mean difference, Cohen's *d*
  (pooled SD), and Mann–Whitney or Welch's *t*. With fewer than two values in
  either group, *d*, the statistic and *p* come back empty and only the means
  render.
- **Two-group word heatmap** — Group A's row above Group B's on a shared word
  axis and colour scale.

!!! warning "The difference profile needs a field that varies within one text"
    The per-word views fix a text first and split second. If the split field is
    baked into the text id — difficulty in OneStop, where `2_1_1_Ele` is an
    `Ele`-only text — then whichever group holds the other value is empty for
    every word: the profile comes back all-`NaN` with that group's `n` at 0, and
    the two-group heatmap draws a single row. Nothing warns you at the default
    *Min/grp* of 1, because the guard only speaks above 1 — so read the group
    caption and the `n_a` / `n_b` columns of the download. Split on something that
    varies *within* a text (reading regime, reading number, answer correctness,
    participant), or take the difficulty question to the distribution /
    paired-bar / effect-size views instead.

!!! danger "*n* is observations, not readers"
    The test and Cohen's *d* treat every row as an independent observation — that
    is words × readers, or fixations. Words within a reader and readers within a
    group are not independent, so the *p* value is anti-conservative, often
    dramatically so: a few readers can put *n* in the thousands. The app labels
    these views *exploratory, not pre-registered* for exactly this reason. Treat
    the effect size as a screening statistic and fit a mixed-effects model on the
    exported table before claiming anything.

---

## The shared controls

### Measure

Each subtab has one measure picker, shared by every view in it, so switching
views keeps your choice. (The Groups subtab has two: one for the single-group
views and one for the comparison views, so flipping **Compare a second group**
starts a fresh choice.) Only measures whose backing column exists in the loaded
data are listed; views that plot a per-word profile restrict the list to the
word-level measures — *Per text* does so in every view. TFD is the default.

| Picker label | Column | Table |
| --- | --- | --- |
| Total fixation duration — TFD | `total_fixation_duration_ms` | words |
| First fixation duration — FFD | `first_fixation_ms` | words |
| First-pass gaze — FPRT | `first_pass_gaze_duration_ms` | words |
| Regression-path — RPD | `regression_path_duration_ms` | words |
| Fixations per word | `n_fixations` | words |
| Skip rate | `skip_flag` | words (rate) |
| Regression-in rate | `regression_in_flag` | words (rate) |
| Regression-out rate | `regression_out_flag` | words (rate) |
| Fixation duration | `duration_ms` | fixations |
| Saccade amplitude | `saccade_amplitude` | fixations |

Rate measures are 0/1 flags averaged into a proportion. Where the source ships
pre-computed EyeLink IA columns those win over the natively computed values —
see [Data format](data-format.md). The app labels saccade amplitude "px", which
is only right when it computed the column itself; see the caveat under *Saccade
vs fixation duration*.

!!! note "Your measure resets when you cross into a word-only view"
    In **Groups**, some views accept any measure and some accept only word-level
    ones, but they share one picker. Picking a fixation-level measure and then
    switching to *Word profile*, *Difference word profile* or *Two-group word
    heatmap* silently drops the selection back to TFD — and switching back does
    not restore it. Re-pick the measure after moving between those views.

### Aggregate and spread

**Aggregate** (`mean` / `median` / `sum`) means different things in different
views, and the tooltip on each says which: across readers for a per-word profile,
within a trial for the trend views, across a group's rows for the bars.

**Spread** (`SD` / `SEM` / `IQR` / `Bootstrap CI`) sets the band or error bar.
One behaviour is worth knowing: with `sum` as the aggregate, SD and SEM fall back
to a bootstrap, because the spread of individual observations says nothing useful
about a *total*.

### Z-score within reader

Replaces each value with its z-score inside that reader's data, so slow and fast
readers compare on shape rather than level. It is disabled for rate measures
(a 0/1 flag has no meaningful z) and on *Word difficulty on stimulus* (nothing
is left to z after the cross-reader aggregate). A reader with a single row, or
with zero variance, z-scores to 0 rather than to `NaN`.

The scope of the z differs by view and this matters:

- **Per-text views** — z-scored over that reader's rows *in the selected text*,
  before repeated readings are collapsed and before the cross-reader aggregate.
  Every reader's mean over the text is therefore 0, and the cohort band is in SD
  units.
- **Distribution views** — z-scored over everything that reader contributes in
  scope. Between-reader level differences are removed by construction, which is
  the right move when both groups draw on the same readers (Adv vs Ele within
  reader) and the wrong one when the groups *are* different readers.

### Min readers per word

The observation guard. Words backed by fewer than the threshold are dropped and a
caption reports how many were hidden. At the default of 1 nothing is dropped and
no caption appears — the guard only speaks when you ask it to.

### Download this table (CSV)

Most views offer the exact tidy table behind the plot, so you can re-plot or
model elsewhere. Available on all six *Per text* views, on *Reading summary*,
*Fixation duration over time*, *Progressive vs regressive* and *Per-trial trend*,
and on *Word profile*, *Reader summary table*, *Group trend*, *Difference word
profile*, *Paired summary bars* and *Two-group word heatmap*. The distribution,
oculomotor-scatter, landing-curve and effect-size views have no download —
recompute those from the raw tables exported from the Scanpath view's **Export**
subtab.

## Getting the numbers out headlessly

The Corpus Analysis views are UI-only: unlike the single-trial scanpath, they
have no CLI flag or [Python API](api.md) entry point. The tidy-table download is
the supported route.

If you are scripting anyway, the aggregation helpers are plain pandas and take
the same normalized frames the app uses:

```python
import scanpath_studio as sps
from scanpath_studio import aggregation

words, fixations = sps.load_sample_data()
tfd = aggregation.MEASURES["tfd"]

profile = aggregation.cohort_word_profile(
    words, "unique_text_id", "2_1_1_Ele", tfd,
    agg="mean", spread="SD", min_readers=2,
)
print(profile.head(3))
#    word_id       value          lo          hi  n  enough word_text
# 0        0  288.333333   49.598473  527.068193  3    True     There
# 1        1  150.333333   18.969970  281.696697  3    True       are
# 2        2  160.333333  128.250108  192.416558  3    True     about
```

`value` is the cross-reader aggregate, `lo`/`hi` the spread band, `n` the number
of contributing readers and `enough` the min-readers guard — the same columns the
*Cohort profile* view plots and downloads.

!!! note "Internal surface"
    `scanpath_studio.aggregation` is not part of the documented public API
    (`load_scanpath_data`, `plot_scanpath`, `animate_scanpath`, `save_figure`,
    …). Its signatures can change between releases without a deprecation path.

## See also

- [Getting started](getting-started.md) — install, launch, and the first figure.
- [Data format](data-format.md) — which columns feed which measure.
- [OneStop](onestop.md) — the corpus behind the bundled demo, and what its
  condition columns mean.
- [True-to-scale rendering](rendering.md) — how the stimulus view sizes the text.
- [Export & troubleshooting](export-troubleshooting.md) — getting figures out.
