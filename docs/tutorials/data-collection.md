# Tutorial: check data collection

Use this workflow during piloting, experimenter training, or session review. The
result is a short record of which trials need attention and why.

## 1. Load a pilot session

On the :material/database: **Data Management** page select **:material/add: Add dataset → Import files**, upload the
Words (interest areas) and Fixations tables, then check the proposed columns and the **Recording setup**
(the actual monitor resolution) before selecting **:material/check: Add dataset**. If the
dataset is already loaded, click its row in the list of datasets.

## 2. Check the setup on one trial

Keep the default visualization first. Confirm that:

- word boxes match the displayed text;
- fixations fall on or near words rather than off-canvas;
- the first and last fixations look plausible.

If every trial is shifted in the same way, check the monitor size and coordinate
system before judging participants.

## 3. Replay the recording

Turn on **Animate**. Look for long missing periods, repeated points out of bounds,
frequent interruptions, or a vertical shift that grows during the trial.

Use **:material/filter_list: Filters & highlights → :material/blur_on: Fixations** in the plot rail to **Highlight** short, long,
or out-of-bounds fixations. Highlighting keeps the full trial visible; **Discard**
is better reserved for a later, documented filtering decision.

## 4. Record the decision

Open **Annotations** for the selected trial:

- star a good example;
- add a tag such as `calibration`, `blink`, `setup`, or `review`;
- write one sentence describing the evidence and action.

Move through the participant's trials with the trial picker.

## 5. Save the review

Open :material/database: **Data Management → Annotations** and select **Export**. The file keeps your
favorites, tags and notes for later review; **:material/share: Share → File** keeps the view
settings beside it. To return to a trial from its note, select **Open** on its
row there; a screen annotation opens that screen.

**Done:** you have checked geometry and timing, marked suspicious trials, and
saved the review. For a formal retained/excluded pool, continue with
[Data filtering](data-filtering.md).

## Compare two eye trackers

Choosing between two eye trackers, or two recording setups, for an experiment?
Record the same text with each and compare the scanpaths side by side.

1. Add each recording as its own dataset (**:material/database: Data Management →
   :material/add: Add dataset → Import files**), each with the **Recording setup**
   of the screen it was recorded on.
2. Open the first tracker's dataset and select a trial.
3. Turn on **Compare**. In scanpath B's row, choose the second tracker's dataset
   under **Dataset B**, then a trial of the same text — trials of the same text
   are marked 📄.
4. Compare the two readings: precision, how fixations sit on the words, missing
   stretches. Two recordings on screens of the same size can be overlaid;
   otherwise each is drawn on its own screen, side by side. Turn on **Animate**
   to replay both on one clock.
