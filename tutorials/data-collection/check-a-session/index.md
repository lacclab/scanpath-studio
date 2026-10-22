# Check a session

Inspect a recording and save the trials that need attention.

These steps use the **Full** mode: switch to it in the top bar of the **Scanpath** view, or add `ui=full` to the app's address ([Essentials and Full](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#essentials-and-full)).

## 1. Open the session

[Import your tables](https://lacclab.github.io/scanpath-studio/guides/loading-data/#add-your-own-data), or select a loaded dataset. Check that its **Recording setup** matches the screen used in the experiment.

## 2. Inspect a trial

In the **Scanpath** view, pick a trial in **Select trial**. Turn on **Word boxes** and check:

- whether the boxes match the stimulus image, if you have one;
- where the fixations sit relative to the words;
- unexpected gaps, shifts or off-screen positions.

For a consistent offset, check [coordinate units and screen setup](https://lacclab.github.io/scanpath-studio/faq/#the-fixations-dont-line-up-with-the-text).

## 3. Replay the recording

Turn on **Animate** to follow the fixation order and timing. To mark short or long fixations, or fixations outside the text, open **Filters & highlights** ▾ → **Fixations** and set **Short**, **Long** or **Outside the text** to **Highlight**. A gap or an unusual scanpath does not tell you its cause.

\[!\[

\](../../../assets/workflows/replay_poster.webp)\](../../../assets/workflows/replay.mp4)

## 4. Record the review

In **Annotations**, tag the trial `review` and write what you observed in **Notes**. Use ◀ ▶ beside **Select trial** to move through the session.

## 5. Save the review

Export favorites, tags and notes from **Data Management** → **Annotations** → **Export**. The file includes participant and trial IDs. **Open** on an annotation row returns to that trial.

For exclusion decisions, follow [Exclude unsuitable trials](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/exclude-unsuitable-trials/index.md).
