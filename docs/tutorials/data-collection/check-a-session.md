# Check a session

Check a pilot or completed session for setup, calibration and recording
problems, and leave a record of which trials need attention and why.

## 1. Load the session

On the :material/database: **Data Management** page select
**:material/add: Add dataset → Import files**, upload the Words (interest areas)
and Fixations tables, then check the proposed columns and the **Recording
setup** — the monitor resolution the session was actually recorded at — before
selecting **:material/check: Add dataset**. If the dataset is already loaded,
click its row in the list of datasets.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/add-your-data_poster.webp" data-autoplay
       aria-label="Adding a dataset from EyeLink fixation and interest-area reports">
  <source src="../../../assets/workflows/add-your-data.mp4" type="video/mp4">
</video>

*Adding the bundled demo's EyeLink fixation and interest-area reports: the columns are detected, and the recording setup arrives filled in.*

## 2. Check the setup on one trial

Keep the default view first, then turn on :material/crop_square: **Word boxes**
and confirm that:

- the word boxes match the original stimulus, if you have a screenshot;
- fixations fall on or near words rather than off the screen;
- the first and last fixations look plausible.

If fixations are consistently shifted, check the coordinate units and origin.

## 3. Replay the recording

Turn on **Animate** to inspect timing and changes in fixation position.
Gaps alone do not identify blinks or their cause.

To make these stand out, open **:material/filter_list: Filters & highlights →
:material/blur_on: Fixations** in the plot rail and **Highlight** short, long or
out-of-bounds fixations. Highlighting keeps the whole trial visible; keep
**Discard** for a later, documented filtering decision.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/replay_poster.webp" data-autoplay
       aria-label="Replaying a reading, sped up to four times real time">
  <source src="../../../assets/workflows/replay.mp4" type="video/mp4">
</video>

*Replaying a trial fixation by fixation, then at four times real time.*

## 4. Record what you find

Open **Annotations** under the plot: star a good example, add a tag such as
`calibration`, `blink`, `setup` or `review`, and write one sentence describing
the evidence and the action. Move through the participant's trials with the
trial picker.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/favorites_poster.webp" data-autoplay
       aria-label="Starring and tagging trials, then showing only the starred ones">
  <source src="../../../assets/workflows/favorites.mp4" type="video/mp4">
</video>

*Starring a trial and tagging it, starring another, then showing only the starred ones.*

## 5. Save the review

Open :material/database: **Data Management → Annotations** and select
**Export**. The file keeps your stars, tags and notes; **:material/share: Share →
File** keeps the view settings beside it. To return to a trial from its note,
select **Open** on its row there.

To exclude tagged trials, continue with [Filter data](../data-filtering/index.md).
