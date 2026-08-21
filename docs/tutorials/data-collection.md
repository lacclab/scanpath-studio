# Tutorial: check data collection

Use this workflow during piloting, experimenter training, or session review. The
result is a short record of which trials need attention and why.

## 1. Load a pilot session

On the 🗂️ **Data** page select **➕ Add dataset**, upload the word/IA and
fixation tables, then check the proposed columns and the **Recording setup**
(the actual monitor resolution) before selecting **✅ Add dataset**. If the
dataset is already loaded, open it from 📂 **Available datasets**.

## 2. Check the setup on one trial

Keep the default visualization first. Confirm that:

- word boxes match the displayed text;
- fixations fall near words rather than between screens or off-canvas;
- the first and last fixations look plausible;
- fixation sizes and saccades do not show obvious recording gaps.

If every trial is shifted in the same way, check the monitor size and coordinate
system before judging participants.

## 3. Replay the recording

Turn on **Animate**. Watch once at the default speed, then slow playback only if
an event is unclear. Look for long missing periods, repeated off-text points,
frequent interruptions, or a vertical shift that grows during the trial.

Use **🧹 Filter → 👁️ Fixations** in the plot rail to *mark* short, long, or
out-of-bounds fixations. Marking keeps the full trial visible; discarding is
better reserved for a later, documented filtering decision.

## 4. Record the decision

Open **Annotations** for the selected trial:

- star a good example;
- add a tag such as `calibration`, `blink`, `setup`, or `review`;
- write one sentence describing the evidence and action.

Move through the participant's trials with the trial picker. If many trials show
the same problem, inspect another participant before deciding whether the cause
is the participant, experimenter, or setup.

## 5. Save the review

Open **Session → JSON backup** and download the file. It preserves the view settings
and annotations for later review. Do not rely on a screenshot as the only record
of an exclusion decision.

**Done:** you have checked geometry and timing, marked suspicious trials, and
saved the review. For a formal retained/excluded pool, continue with
[Data filtering](data-filtering.md).
