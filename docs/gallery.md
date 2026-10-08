---
description: Figures Scanpath Studio draws, each built from the bundled demo when the docs are built, with the code that makes it, and short recordings of the app at work.
hide:
  - navigation
---

# Gallery

Every figure on this page is drawn from the bundled demo while the docs are
built, by the code shown under it, so what you see is what the current release
renders. Hover a fixation or a word for its values. The app draws the same
figures from its plot controls, and its :material/share: **Share** subtab prints the code that
reproduces whichever one is on screen. The recordings at the end,
[The app at work](#the-app-at-work), show the app itself, one task each.

All of them start from the demo and one of its trials:

```python exec="true" source="above" session="gallery"
import scanpath_studio as sps
from docs_support import embed, saccade_class_legend  # markdown-exec: hide

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
```

## A reading

The app's *Scanpath* design, which `plot_scanpath` draws by default: each
fixation where it landed, sized by its duration, and the saccades between
them, over the text at its recorded position. The orange words are the answer
to the trial's question.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(words, fixations, pid, tid)
print(embed(fig))  # markdown-exec: hide
```

## Where the participant dwelt

The heatmap on its own, here as a smooth duration-weighted density rather than
one tint per word; the app's **:material/local_fire_department: Heatmap** controls offer both.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    show_heatmap=True,
    heatmap_style="Interpolated",
    show_fixations=False,
    show_saccades=False,
)
print(embed(fig))  # markdown-exec: hide
```

## Fixations by text line

Each fixation colored by the line of text it was assigned to: a quick check
for vertical drift, which shows up as one line's color creeping onto the next.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(words, fixations, pid, tid, color_by_line=True)
print(embed(fig))  # markdown-exec: hide
```

## Saccades by reading class

Each saccade colored by its role in reading: forward, skip, refixation, return
sweep, or regression.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    saccade_color_mode="By type",
    saccade_type_legend=False,
)
print(embed(fig, legend=saccade_class_legend()))  # markdown-exec: hide
```

## A linear-reading schematic

One sentence's fixations snapped above the words they landed on, with the
saccades arced over the text. It no longer shows exact positions, so the figure
labels itself an *Illustration*.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    fixation_snap_to_word=True,
    saccade_render_mode="Arc",
    fix_index_range=(124, 139),
)
print(embed(fig))  # markdown-exec: hide
```

## Two participants, one text

The first fifty fixations of two trials of the same paragraph, on one canvas
in two colors. The trials can also sit side by side, or come from two
different datasets.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_1090", "l7_1090_2_1_1_Ele_r0"),
    fix_index_range=(1, 50),
    show_legend=True,
)
print(embed(fig))  # markdown-exec: hide
```

## Raw gaze under the fixations

Gaze samples, colored by time, under the fixations, which are drawn hollow so
the samples show through. The demo ships no recorded samples, so this trial's
are synthesized from its fixations: the figure shows the layer, not real data.

```python exec="true" html="true" source="below" session="gallery"
raw_gaze = sps.load_sample_raw_gaze()
fig = sps.plot_scanpath(
    words,
    fixations,
    "l37_1129",
    "l37_1129_2_2_2_Adv_r0",
    raw_gaze=raw_gaze,
    hollow_fixations=True,
    show_saccades=False,
)
print(embed(fig))  # markdown-exec: hide
```

## The replay

The reading unfolding fixation by fixation, here its first forty. Press ▶; the
app replays in real time or faster, and exports the replay as HTML, GIF or MP4.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.animate_scanpath(words, fixations, pid, tid, fix_index_range=(1, 40))
print(embed(fig))  # markdown-exec: hide
```

## A text, word by word

Beyond single trials: the total fixation duration on every word of one text,
averaged over the demo's participants, with ± one standard deviation as a band. The
app's :material/bar_chart: **Corpus Analysis** view draws this and more.

```python exec="true" html="true" source="below" session="gallery"
# The demo's word table carries EyeLink's own measures (IA_DWELL_TIME, …).
one_text = words[words["unique_paragraph_id"] == "2_1_1_Ele"]
profile = (
    one_text.groupby("IA_ID")
    .agg(
        value=("IA_DWELL_TIME", "mean"),
        sd=("IA_DWELL_TIME", "std"),
        word_text=("IA_LABEL", "first"),
    )
    .rename_axis("word_id")  # the column plot_corpus_figure reads
    .reset_index()
    .assign(lo=lambda d: d.value - d.sd, hi=lambda d: d.value + d.sd)
)
fig = sps.plot_corpus_figure(
    profile, kind="profile", measure_label="Total fixation duration (ms)"
)
print(embed(fig))  # markdown-exec: hide
```

## The app at work

One task each, recorded in the app on the bundled demo. The bar at the top
counts the clicks as they happen and names each step; the last frame gives
the total.

### Add your own data

Upload a fixation report and an interest-area report, here the demo's own
EyeLink exports: the columns are detected for you, three answers describe the
recording setup, and the scanpaths are ready.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/add-your-data_poster.webp" data-autoplay
       aria-label="Adding a dataset from EyeLink fixation and interest-area
reports">
  <source src="../assets/workflows/add-your-data.mp4" type="video/mp4">
</video>

### Find trials

Step through the trials, then narrow the list to one condition and one
participant: from 24 trials to 6.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/trial-filtering_poster.webp" data-autoplay
       aria-label="Narrowing the trials by condition and participant">
  <source src="../assets/workflows/trial-filtering.mp4" type="video/mp4">
</video>

### Star and tag trials

Star a trial and tag it, star another, then show only the starred ones.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/favorites_poster.webp" data-autoplay
       aria-label="Starring and tagging trials, then showing only the starred
ones">
  <source src="../assets/workflows/favorites.mp4" type="video/mp4">
</video>

### Style the plot

Color regressions apart from forward saccades, add the word boxes and the
reading order, and switch to the high-contrast palette.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/plot-controls_poster.webp" data-autoplay
       aria-label="Coloring regressions apart and adding word boxes, the
reading order and another palette">
  <source src="../assets/workflows/plot-controls.mp4" type="video/mp4">
</video>

### Ready-made designs

One click for each design: Heatmap, Illustration and Scanpath, then a heatmap
added to the scanpath.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/design-presets_poster.webp" data-autoplay
       aria-label="Switching between the Heatmap, Illustration and Scanpath
designs">
  <source src="../assets/workflows/design-presets.mp4" type="video/mp4">
</video>

### Under the figure

The subtabs below the plot: annotations, the stimulus and its context, other
trials that match this one, export and share.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/subtabs_poster.webp" data-autoplay
       aria-label="The subtabs under the figure: annotations, stimulus and
context, comparisons, export and share">
  <source src="../assets/workflows/subtabs.mp4" type="video/mp4">
</video>

### Replay the reading

Animate the trial fixation by fixation, then speed it up to four times real
time.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/replay_poster.webp" data-autoplay
       aria-label="Replaying a reading, sped up to four times real time">
  <source src="../assets/workflows/replay.mp4" type="video/mp4">
</video>

### Save the replay

Render the replay to a GIF and download it; the wait while it renders is fast-
forwarded.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/replay-export_poster.webp" data-autoplay
       aria-label="Rendering the replay to a GIF and downloading it">
  <source src="../assets/workflows/replay-export.mp4" type="video/mp4">
</video>

### Compare two readers

Two participants on the same text, overlaid and then side by side, stepping
through the texts together.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/compare_poster.webp" data-autoplay
       aria-label="Two readers of one text side by side, stepping through the
texts together">
  <source src="../assets/workflows/compare.mp4" type="video/mp4">
</video>

### Corpus Analysis

One text's total fixation duration on the stimulus and against GPT-2 surprisal,
then its distribution in two groups, the Adv and Ele texts.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/corpus-analysis_poster.webp" data-autoplay
       aria-label="Corpus Analysis: a measure on the stimulus, against
surprisal, and between two groups">
  <source src="../assets/workflows/corpus-analysis.mp4" type="video/mp4">
</video>

### Export a figure

Set the width to 180 mm at 300 dpi and download the PNG.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/export-figure_poster.webp" data-autoplay
       aria-label="Exporting the figure 180 mm wide at 300 dpi">
  <source src="../assets/workflows/export-figure.mp4" type="video/mp4">
</video>

### Export every trial

Add PNG to the formats and the fixation and word-measure tables, build a zip of
all 24 trials (the build is fast-forwarded) and download it.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

### Share a link

Look at the code that redraws the figure, then copy a link that reopens the
same trial with the same design, as the recording then does.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../assets/workflows/share-link_poster.webp" data-autoplay
       aria-label="Copying a link that reopens the same trial and design">
  <source src="../assets/workflows/share-link.mp4" type="video/mp4">
</video>
