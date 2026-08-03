# Scanpath visualization

The Scanpath view shows one selected reading on the stimulus coordinate system.
Start with the default view, then change only controls needed for the question.

## Choose a trial

Use the participant and trial pickers above the plot. Trial filters define which
readings are available; ordering helps surface long, short, early, or late
trials. The detail popover shows the active trial's summary fields.

## Control the layers

| Layer | Use it for |
| --- | --- |
| Text and word boxes | verify stimulus geometry and fixation-to-word alignment |
| Fixations | location, order, duration, and optional color field |
| Saccades | movement direction, reading type, regressions, and return sweeps |
| Heatmap | spatial concentration by count or duration |
| Stimulus image | compare the scanpath with the original display |

Layer settings appear only when their layer is active. Marker size already
encodes duration by default, so uniform fixation color is usually the clearest
starting point.

## Filter or mark fixations

**Fixation filter** contains duration thresholds, out-of-bounds handling, and
the fixation-index range. Marking preserves context; discarding removes points
from the rendered scanpath. These are visualization choices, not edits to the
source data or reading-measure computation.

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
