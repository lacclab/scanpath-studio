---
description: "Inspect an eye-tracking recording trial by trial — fixations against raw gaze and word boxes — tag the trials that need attention, and save the review."
---

# Check a session

Inspect a recording and save the trials that need attention.

Before you start, switch to **Full** at the top of the :material/route:
**Scanpath View** ([Essentials and Full](../../guides/scanpath-visualization/index.md#essentials-and-full)).

## 1. Open the session { #1-load-the-session }

[Import your tables](../../guides/loading-data/index.md#add-your-own-data), or
select a loaded dataset. Check that its **Recording setup** matches the screen
used in the experiment.

## 2. Inspect a trial

In the :material/route: **Scanpath View**, pick a trial in **Select trial**.
Turn on :material/crop_square: **Word boxes** and check:

- whether the boxes match the stimulus image, if you have one;
- where the fixations sit relative to the words;
- unexpected gaps, shifts or off-screen positions.

For a consistent offset, check [coordinate units and screen setup](../../faq.md#the-fixations-dont-line-up-with-the-text).

## 3. Replay the recording { #3-replay-the-recording }

Choose :material/movie: **Animation** to follow the fixation order and timing.
To mark short or long fixations, or fixations outside the text, open
:material/filter_list: **Filters & highlights** ▾ → **Fixations** and set
**Short**, **Long** or **Outside the text** to **Highlight**. A gap or an
unusual scanpath does not tell you its cause.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/replay_poster.webp" data-autoplay
       aria-label="Replaying a reading, sped up to four times real time">
  <source src="../../../assets/workflows/replay.mp4" type="video/mp4">
</video>

## 4. Record the review

In :material/edit_note: **Annotations**, tag the trial `review` and write what
you observed in **Notes**. Use ◀ ▶ beside **Select trial** to move through the
session.

## 5. Save the review { #5-save-the-review }

Export favorites, tags and notes from :material/database: **Data Management**
→ **Current dataset → Annotations → Export**. The file includes participant and trial IDs.
**Open** on an annotation row returns to that trial.

To reconcile a second reviewer's notes, choose **Import**. The preview counts
new, identical and differing entries. **Open disputed reading** displays both
entries beside the scanpath for that reading. You can download the differences
for discussion. **Apply import** adds new entries and keeps the current version
of a differing note unless you select the replacement option.

For exclusion decisions, follow [Exclude unsuitable trials](../data-filtering/exclude-unsuitable-trials.md).
