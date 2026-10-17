# Check a session

Inspect a recording and save the trials that need attention.

## 1. Open the session

[Import your tables](https://lacclab.github.io/scanpath-studio/guides/loading-data/#add-your-own-data), or select a loaded dataset. Check its Recording setup against the screen used in the experiment.

## 2. Inspect a trial

Select a participant and trial in Scanpath. Turn on Word boxes and inspect:

- whether the boxes match the stimulus screenshot, if available;
- how fixations sit relative to the words;
- unexpected gaps, shifts or off-screen positions.

For a consistent offset, check [coordinate units and screen setup](https://lacclab.github.io/scanpath-studio/faq/#the-fixations-dont-line-up-with-the-text).

## 3. Replay the recording

Turn on Animate to inspect fixation order and timing. To mark short or long fixations, or fixations outside the text, use Plot controls → Filters & highlights → Fixations and choose Highlight. Gaps and unusual scanpaths alone do not establish their cause.

\[!\[

\](../../../assets/workflows/replay_poster.webp)\](../../../assets/workflows/replay.mp4)

## 4. Record the review

In Annotations, tag a trial `review` and note what you observed. Use the trial picker's arrows to continue through the session.

## 5. Save the review

Export stars, tags and notes from Data Management → Annotations → Export. The record includes participant and trial IDs. Use Open on an annotation row to return to that trial.

For exclusion decisions, follow [Exclude unsuitable trials](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/exclude-unsuitable-trials/index.md).
