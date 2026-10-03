# Scanpath visualization

The Scanpath view draws one reading on the screen it was recorded on.

<figure class="sps-screenshot" markdown>
![The Scanpath view, its regions numbered](../assets/screenshots/scanpath-view.webp)
</figure>

1. Views and :material/help: Help.
2. Dataset and trial pickers, sort (⇅) and filter funnel.
3. The trial's summary.
4. The figure.
5. Plot controls.
6. Annotations, Stimulus & Context, Comparisons, Export and Share.

## Choose a trial

Pick a trial above the plot. The **filter funnel** beside it narrows the list
by text, participant, condition or annotation, and **⇅** sorts it. A trial with
several screens gets a second navigator to move between them.

## Control the layers

The **:material/tune: Plot controls** rail starts with **:material/movie: Animate**, **:material/compare: Compare**, four
design presets and a palette. Below them, each section is one line: a switch,
and a **▾** with its settings.

| Section | What it controls |
| --- | --- |
| :material/blur_on: Fixations | markers: size, colour, order |
| :material/arrow_outward: Saccades | lines and arrows, coloured by direction or reading type |
| :material/article: Stimulus | text, word boxes, stimulus image, font and background |
| :material/local_fire_department: Heatmap | where fixations concentrate, by count or duration |
| :material/grain: Raw gaze | the gaze samples as recorded |
| :material/cleaning_services: Filter | which fixations and saccades are drawn |
| :material/aspect_ratio: Figure & canvas | screen framing, axes and grid, title and labels |

Colour ranges start on **Auto**, scaled to each trial. Pin a range to keep it
fixed as you step through trials and filters, so they stay comparable; its
number boxes take any endpoint, beyond the data shown too. The word-box
heatmap's range is in dwell time per word (ms), the summed duration of the
fixations in each box.

Marker size shows fixation duration on a **fixed scale**: 50–600 ms span the
smallest to the largest marker in every trial, both sides of a comparison, the
replay and every export, so one duration is always one size. Shorter fixations
take the smallest marker and longer ones the largest. Under
**:material/blur_on: Fixations ▾**, **Scale** picks the curve: **√ duration** (the
default) grows marker area with duration, **Linear** grows the diameter with it,
**Log** compresses long fixations. **Durations** sets the two bounds, and
**Size key** draws reference circles labelled in ms in the figure's corner
(in Compare, only while both scanpaths use the same marker size range).
**Relative to this figure** stretches each figure from its own shortest to
longest fixation instead, so its sizes compare only within that figure. Share
links, settings files, saved designs and restored sessions from before the fixed
scale reopen on the relative one, as they were drawn.

## Filter what is drawn

**:material/cleaning_services: Filter** thins the reading on screen (the funnel above the plot chooses
*which* readings you can pick). For fixations, **Highlight** or **Discard**
short, long, out-of-bounds or blink fixations, or show only an index range.
*Out of bounds* means outside every word box, not off the screen; *blink* needs
a blink column in your fixations (`is_blink`, `blink`, `blink_before`,
`blink_after`), and without one nothing is flagged.
For saccades, choose which reading types are drawn: hide everything but
regressions, for example. Filtering changes only the figure, never your data.

## Replay and compare

- **Animate** replays the trial; its **▾** sets the speed.
- **Compare** adds a second reading, overlaid or side by side. **Compare
  with** can take it from another dataset.
- **Comparisons** lists other trials that match this one on a field you
  choose: other readings of the same text, or the same reader's other trials.

Side by side, each panel shows its own reading's stimulus image, or none when
that reading has no image. An uploaded image stands for the first reading's
page, so the second shows it only when it reads the same text on the same
screen.

Two readings can be overlaid only when they were shown on the same screen size,
including two screens of one dataset whose sizes differ; otherwise they are
drawn side by side, each on its own screen. Nothing is rescaled to force an
overlay.

Compare is also available from Python
([`compare_scanpaths`](../api.md#scanpath_studio.api.compare_scanpaths)) and the
[CLI](../cli.md#compare-two-scanpaths).
