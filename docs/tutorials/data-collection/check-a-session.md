---
description: "Inspect an eye-tracking recording trial by trial — fixations against raw gaze and word boxes — tag the trials that need attention, and save the review."
---

# Check a session

Inspect a recording and save the trials that need attention.

## 1. Open the session { #1-load-the-session }

[Import your tables](../../guides/loading-data/index.md#add-your-own-data), or
select a loaded dataset. Check its Recording setup against the screen used in
the experiment.

## 2. Inspect a trial

Select a participant and trial in Scanpath. Turn on Word boxes and inspect:

- whether the boxes match the stimulus screenshot, if available;
- how fixations sit relative to the words;
- unexpected gaps, shifts or off-screen positions.

For a consistent offset, check [coordinate units and screen setup](../../faq.md#the-fixations-dont-line-up-with-the-text).

## 3. Replay the recording { #3-replay-the-recording }

Turn on Animate to inspect fixation order and timing. To mark short or long
fixations, or fixations outside the text, use Plot controls → Filters & highlights → Fixations
and choose Highlight. Gaps and unusual scanpaths alone do not establish their cause.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/replay_poster.webp" data-autoplay
       aria-label="Replaying a reading, sped up to four times real time">
  <source src="../../../assets/workflows/replay.mp4" type="video/mp4">
</video>

## 4. Record the review

In Annotations, tag a trial `review` and note what you observed. Use the trial
picker's arrows to continue through the session.

## 5. Save the review { #5-save-the-review }

Export stars, tags and notes from Data Management → Annotations → Export.
The record includes participant and trial IDs. Use Open on an annotation row
to return to that trial.

For exclusion decisions, follow [Exclude unsuitable trials](../data-filtering/exclude-unsuitable-trials.md).
