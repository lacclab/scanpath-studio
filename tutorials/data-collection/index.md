# Tutorial: check data collection

Use this workflow during piloting, experimenter training, or session review. The result is a short record of which trials need attention and why.

## 1. Load a pilot session

On the **Data Management** page select **Add dataset → Import files**, upload the Words (interest areas) and Fixations tables, then check the proposed columns and the **Recording setup** (the actual monitor resolution) before selecting **Add dataset**. If the dataset is already loaded, click its row in the list of datasets.

## 2. Check the setup on one trial

Keep the default visualization first. Confirm that:

- word boxes match the displayed text;
- fixations fall on or near words rather than off-canvas;
- the first and last fixations look plausible.

If every trial is shifted in the same way, check the monitor size and coordinate system before judging participants.

## 3. Replay the recording

Turn on **Animate**. Look for long missing periods, repeated points out of bounds, frequent interruptions, or a vertical shift that grows during the trial.

Use **Filters & highlights → Fixations** in the plot rail to **Highlight** short, long, or out-of-bounds fixations. Highlighting keeps the full trial visible; **Discard** is better reserved for a later, documented filtering decision.

## 4. Record the decision

Open **Annotations** for the selected trial:

- star a good example;
- add a tag such as `calibration`, `blink`, `setup`, or `review`;
- write one sentence describing the evidence and action.

Move through the participant's trials with the trial picker.

## 5. Save the review

Open **Data Management → Annotations** and select **Export**. The file keeps your favorites, tags and notes for later review; **Share → File** keeps the view settings beside it. To return to a trial from its note, select **Open** on its row there; a screen annotation opens that screen.

**Done:** you have checked geometry and timing, marked suspicious trials, and saved the review. For a formal retained/excluded pool, continue with [Data filtering](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/index.md).
