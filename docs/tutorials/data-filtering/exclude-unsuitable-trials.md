---
description: "Apply your exclusion criteria to eye-tracking trials: tag rejected trials in Scanpath Studio and leave them out of the selection and the export."
---

# Exclude unsuitable trials

Apply your exclusion criteria and leave rejected trials out of the selection.

These steps use the **Full** mode: switch to it in the top bar of the
:material/route: **Scanpath** view, or add `ui=full` to the app's
address ([Essentials and Full](../../guides/scanpath-visualization/index.md#essentials-and-full)).

1. [Review the session](../data-collection/check-a-session.md#2-inspect-a-trial).
   Judge each trial against your study's criteria. A scanpath pattern alone
   does not establish skimming or poor calibration.
2. In :material/edit_note: **Annotations**, tag rejected trials `exclude` and
   write a short reason in **Notes**.
3. Open the filter (:material/filter_alt:) beside **Select trial**. Under
   **By trial annotation**, add `exclude` to **Excluding tags**.
4. [Check and export the selection](index.md#every-task-ends-the-same-way).

For a trial with several screens, tag the whole trial. A tag on one screen
does not exclude the trial.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/favorites_poster.webp" data-autoplay
       aria-label="Starring and tagging trials, then showing only the starred ones">
  <source src="../../../assets/workflows/favorites.mp4" type="video/mp4">
</video>

*The recording shows favorites and tags. For the selection above, use the
`exclude` tag and **Excluding tags**.*
