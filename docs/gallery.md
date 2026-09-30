---
description: Figures Scanpath Studio draws, each built from the bundled demo when the docs are built, with the code that makes it.
hide:
  - navigation
---

# Gallery

Every figure on this page is drawn from the bundled demo while the docs are
built, by the code shown under it, so what you see is what the current release
renders. Hover a fixation or a word for its values. The app draws the same
figures from its plot controls, and its 🔗 **Share** subtab prints the code that
reproduces whichever one is on screen.

All of them start from the demo and one of its trials:

```python exec="true" source="above" session="gallery"
import scanpath_studio as sps
from docs_support import embed, saccade_class_legend  # markdown-exec: hide

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
```

## A reading

The full figure, as `plot_scanpath` draws it by default: each fixation where
it landed, sized by its duration and numbered in order, the saccades between
them, and every word tinted by the time spent on it, over the text at its
recorded position. The orange words are the answer to the trial's question.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(words, fixations, pid, tid)
print(embed(fig))  # markdown-exec: hide
```

## Where the reader dwelt

The heatmap on its own, here as a smooth duration-weighted density rather than
one tint per word; the app's **🔥 Heatmap** controls offer both.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    heatmap_style="Interpolated",
    show_fixations=False,
    show_saccades=False,
)
print(embed(fig))  # markdown-exec: hide
```

## Fixations by text line

Each fixation coloured by the line of text it was assigned to: a quick check
for vertical drift, which shows up as one line's colour creeping onto the next.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words, fixations, pid, tid, color_by_line=True, show_heatmap=False
)
print(embed(fig))  # markdown-exec: hide
```

## Saccades by reading class

Each saccade coloured by its role in reading: forward, skip, refixation, return
sweep, or regression.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    saccade_color_mode="By type",
    saccade_type_legend=False,
    show_heatmap=False,
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
    show_heatmap=False,
)
print(embed(fig))  # markdown-exec: hide
```

## Two readers, one text

The first fifty fixations of two readings of the same paragraph, on one canvas
in two colours. The readings can also sit side by side, or come from two
different datasets.

```python exec="true" html="true" source="below" session="gallery"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_1090", "l7_1090_2_1_1_Ele_r0"),
    fix_index_range=(1, 50),
    show_heatmap=False,
    show_legend=True,
)
print(embed(fig))  # markdown-exec: hide
```

## Raw gaze under the fixations

Gaze samples, coloured by time, under the fixations, which are drawn hollow so
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
    show_heatmap=False,
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
averaged over the demo's readers, with ± one standard deviation as a band. The
app's 📊 **Corpus Analysis** view draws this and more.

```python exec="true" html="true" source="below" session="gallery"
measures = sps.compute_word_metrics(words, fixations)
one_text = measures[measures["text_id"] == "2_1_1_Ele"]
profile = (
    one_text.groupby("word_id")
    .agg(
        value=("total_fixation_duration_ms", "mean"),
        sd=("total_fixation_duration_ms", "std"),
        word_text=("text", "first"),
    )
    .reset_index()
    .assign(lo=lambda d: d.value - d.sd, hi=lambda d: d.value + d.sd)
)
fig = sps.plot_corpus_figure(
    profile, kind="profile", measure_label="Total fixation duration (ms)"
)
print(embed(fig))  # markdown-exec: hide
```
