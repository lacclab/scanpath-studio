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

The rail beside the plot groups the layers by what they describe. **Quick
views** and **Palette** sit at the top — often all you need — followed by six
collapsible sections:

| Section | Layers | Use it for |
| --- | --- | --- |
| 👁️ Fixations | Fixations | location, order, duration and colour field |
| ↗️ Saccades | Saccades | movement direction, reading type, regressions and return sweeps |
| 📄 Stimulus | Text, Bounding boxes, Stimulus image | verify stimulus geometry and fixation-to-word alignment; compare against the original display |
| 🔥 Overlays | Heatmap, Raw gaze | spatial concentration by count or duration; millisecond-level gaze samples |
| 🖥️ Canvas & text | — | monitor geometry, viewing distance, fonts, text colour, plot background |
| 📐 Figure & axes | — | full-monitor framing, colour bars, axis fields, illustration label |

Each layer section opens the same way: the **on/off toggle** first, then
**⚙️ style** and **🧹 filter** — appearance and visibility kept apart, so
"colour the regressions red" and "show only the regressions" don't sit in the
same list. The two scanpath sections are open by default; the rest start
collapsed, and a layer's settings appear only while that layer is on. Marker
size already encodes duration by default, so uniform fixation color is usually
the clearest starting point.

### Show screen coordinates

Open **📐 Figure & axes** and turn on **Coordinate grid** to read the stimulus in
monitor pixels. Automatic spacing chooses a readable 1/2/5×10ⁿ interval for the
current range; turn it off to enter an exact major interval. Ticks stay anchored
to screen-coordinate zero even when the visible range is cropped or negative.
The grid is off by default and does not shrink or rescale the spatial data area.

## Filter fixations and saccades

**🧹 Fixation filter** contains duration thresholds, out-of-bounds handling, and
the fixation-index range. Marking preserves context; discarding removes points
from the rendered scanpath.

**🧹 Saccade filter** picks which reading classes are drawn at all — forward,
skip, refixation, return sweep, regression. Hidden classes lose their line
*and* their direction arrow, which is how you get a regressions-only figure.
Classes come from the same split as ⚙️ Saccade style → **By type**, so the two
always agree on what a regression is; clearing the list means *no filter*, not
an empty plot. Both filters show a badge on the popover button while they are
active, so a thinned figure never looks like missing data.

These are visualization choices, not edits to the source data or reading-measure
computation.

## Replay and compare

- **Animate** replays the selected trial. **⚙ Playback** controls speed,
  autoplay, and frame quality.
- **Compare** adds a second reading on the same text and shared canvas.
- **Comparisons** ranks other same-text scanpaths using the selected grouping
  and similarity settings.

## Correct vertical drift

Fixations that follow the text horizontally but sit above or below their line
may need line assignment. Choose a drift-correction algorithm in the fixation
controls, or use **Line assignment** to compare algorithms before applying one.
The correction changes the rendered fixation y-position; it does not overwrite
the uploaded table.

Use [Outputs and sharing](outputs-sharing.md) when the view is ready.
