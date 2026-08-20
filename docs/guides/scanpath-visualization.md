# Scanpath visualization

The Scanpath view shows one selected reading on the stimulus coordinate system.
Start with the default view, then change only controls needed for the question.

## Choose a trial

Use the participant and trial pickers above the plot. Trial filters define which
readings are available; ordering helps surface long, short, early, or late
trials. The detail popover shows the active trial's summary fields.

When a trial contains ordered screens, a second navigator appears below the
trial picker. The plot always shows one screen in its own recorded canvas; use
the previous/next buttons or screen menu to move between them. Figure links and
saved configurations retain the active screen, and **Annotations** lets you
choose parent-trial or current-screen scope.

## Control the layers

The **Plot controls** rail beside the plot starts with four **Quick views** and
a **Palette** — often all you need — followed by five collapsible sections:

Scanpath, Heatmap, and Illustration are presets. **Custom** remembers the last
settings you changed by hand and restores them after you visit another preset.

| Section | Layers | Use it for |
| --- | --- | --- |
| 👁️ Fixations | Fixations | location, order, duration and colour field |
| ↗️ Saccades | Saccades | movement direction, reading type, regressions and return sweeps |
| 📄 Stimulus | Text, Bounding boxes, Stimulus image | verify stimulus geometry and fixation-to-word alignment; compare against the original display |
| 🔥 Overlays | Heatmap, Raw gaze | spatial concentration by count or duration; millisecond-level gaze samples |
| 📐 Figure & canvas | — | monitor geometry, fonts, plot background, full-monitor framing, colour bars, axes, title and labels |

Each layer section opens the same way: the **on/off toggle** first, then
**⚙️ style** and **🧹 filter** — appearance and visibility kept apart, so
"colour the regressions red" and "show only the regressions" don't sit in the
same list. Fixations is open by default; the rest start collapsed, and a layer's
settings appear only while that layer is on. Marker size already encodes duration
by default, so uniform fixation color is usually the clearest starting point.

**📐 Figure & canvas** has no layer to switch on, so it keeps **Show full
monitor** in view and groups the rest the same way: **🖥️ Screen & geometry**
(monitor pixels, physical size, viewing distance, DPI), **🔤 Text & fonts** (text
scaling, font size and typeface, text and background colour), **📊 Axes & grid**
(coordinate grid, colour bars, axis fields) and **🏷️ Title & labels**
(Illustration label, figure title and caption).

### Show screen coordinates

Open **📐 Figure & canvas → 📊 Axes & grid** and turn on **Coordinate grid** to
read the stimulus in monitor pixels. Automatic spacing chooses a readable
1/2/5×10ⁿ interval for the current range; turn it off to enter an exact major
interval. Ticks stay anchored to screen-coordinate zero even when the visible
range is cropped or negative.
The grid is off by default and does not shrink or rescale the spatial data area.

## Filter fixations and saccades

**Fixations → 🧹 Filter** contains duration thresholds, out-of-bounds handling, and
the fixation-index range. Marking preserves context; discarding removes points
from the rendered scanpath.

**Saccades → 🧹 Filter** picks which reading classes are drawn at all — forward,
skip, refixation, return sweep, regression. Hidden classes lose their line
*and* their direction arrow, which is how you get a regressions-only figure.
Classes come from the same split as Saccades → ⚙️ Style → **By type**, so the two
always agree on what a regression is; clearing the list means *no filter*, not
an empty plot. Both filters show a badge on the popover button while they are
active, so a thinned figure never looks like missing data.

These are visualization choices, not edits to the source data or reading-measure
computation.

## Replay and compare

- **Animate** replays the selected trial. **⚙ Playback** controls speed,
  autoplay, and frame quality.
- **Compare** adds a second reading beside the selected one.
- **Comparisons** shows trials whose chosen field matches the selected trial.
  Choosing text id finds other readings of the text; choosing participant id
  finds that reader's other trials.

### Comparing across datasets

**Compare with** (the first control on scanpath B's line, directly under the
dataset picker on your own) chooses which dataset scanpath B comes from. It
defaults to *This dataset*; pick another and the candidate list, the 🔎 filters
at the end of B's line, and the trial's screen geometry all come from that
dataset instead.

B's line is the same shape as the trial line above it — dataset, trial, scrub
slider, then ◀ ▶ ⇅ and 🔎 — so the two read down the page as one pair of
controls. B's 🔎 appears only when B has a dataset of its own to narrow;
under *This dataset* the candidates come out of the pool your own 🔎 defines.

Any loaded upload, the bundled demo and the synthetic trial are always
available. A public corpus is offered too, but only loads when its files are
already where you last pointed the app — otherwise it shows *(needs setup)* and
tells you to open that corpus as the main dataset once, because the compare
picker deliberately cannot draw the download and folder controls that would
normally set that up.

Three things behave differently across datasets, each on purpose:

| | Why |
| --- | --- |
| **Overlay needs one shared screen** | Overlay pools both readings into one set of pixel coordinates, so it needs matching canvases — see below. Otherwise Side by side is used, and your Overlay choice is remembered for same-dataset pairs. |
| **Each panel is drawn to its own screen** | In a split layout a caption under the figure names both monitors. Box and text sizes are true-to-scale *within* a panel and **not** comparable across panels. |
| **Only shared metrics can colour it** | A measure one corpus ships and the other doesn't would colour one panel and blank the other, so it falls back with a note. |

B carries its own filters (they never touch the main pool) and never shows 👤
markers — two corpora don't share readers. 📄 still appears when a text id
matches across them.

#### When can two datasets be overlaid?

When the two **canvas sizes match**. That is the only hard requirement: the
overlay draws raw pixel positions, so equal canvases are what make them mean the
same thing. Different screens still fall back to Side by side.

If either dataset never *recorded* its screen — most public corpora don't, so
their canvas is a shared default rather than a measurement — the overlay is
still drawn, with a warning beside it. The app can't prove the two displays
matched; you usually can. A matching canvas is real evidence, just not proof.

Nothing is ever rescaled or reprojected to make an overlay possible. When the
screens match, the pixels already mean the same thing on both sides; when they
don't, the honest answer is two panels. (An earlier design converted each
reading through its own monitor geometry into degrees of visual angle. That was
dropped: no bundled corpus records the physical measurements it would need, so
it would have been a claim the data can't support.)

An animated comparison follows the same rule — a co-animation replays both
readings on one clock, which is an overlay, so it needs the same shared screen.

#### Whose text does an overlay show?

**Stimulus from** (⚙️ *Compare options*, overlay only) picks which reading
supplies the word boxes and text: **Both**, **A**, or **B**. Two datasets' word
boxes line up only when the text, font and wrapping are identical, so across
corpora *Both* often draws two offset sets of rectangles under the two traces.
Pick one side to read the overlay as a comparison of the *fixation traces*
against a single stimulus. It defaults to *Both*, which leaves same-dataset
overlays exactly as they were.

**⚖️ Download this comparison as a bundle** (Export → *Current figure*) writes the
figure plus both scanpaths' tables and a manifest naming each side's dataset,
trial and recording setup. The image alone can't be reproduced; the bundle can.

A share link carries the comparison as `?compare=<participant>:<trial>` plus
`&cmp_source=<dataset>`, `&cmp_layout=` and `&cmp_stimulus=`. An uploaded dataset
lives only in your session, so a link can't rebuild it — the Share panel says so
rather than sending half a comparison.

Compare mode is also available headlessly — see
[`compare_scanpaths`](../api.md#scanpath_studio.api.compare_scanpaths) and
`render --compare-with` in the [CLI reference](../cli.md#compare-two-scanpaths).

## Correct vertical drift

!!! note "Not available by default"
    Vertical drift correction and NLD scanpath similarity are gated off in
    the released app (PRE-21) — they work, but are not fully integrated yet.
    Set `SCANPATH_EXPERIMENTAL=1` to expose them in the app, the CLI and the
    Python API.

Fixations that follow the text horizontally but sit above or below their line
may need line assignment. Choose a drift-correction algorithm in the fixation
controls, or use **Line assignment** to compare algorithms before applying one.
The correction changes the rendered fixation y-position; it does not overwrite
the uploaded table.

Use [Outputs and sharing](outputs-sharing.md) when the view is ready.
