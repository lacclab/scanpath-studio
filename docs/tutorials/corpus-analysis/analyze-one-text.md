---
description: "Compare how participants read the words of one text using the reading measures in your data."
---

# Analyze one text

1. [Select the trials](index.md#before-you-start), then open
   :material/bar_chart: **Corpus Analysis** and choose a **Reading measure**.
   In the bundled demo, try **Total fixation duration — TFD**.
2. In **Overview**, summarize by **Text**. Choose a text and select **Open
   word profile**. The **Cohort profile** shows a point for each word with
   enough observations. Hover over a point to read the word and its value.
3. Open **Readings behind a word** to check which participants supplied a
   value. A blank cell means that reading had no recorded value for the
   selected measure. In **Analysis settings**, **Aggregate** sets how the
   profile combines values, **Spread** controls the shaded band, and **Min
   participants per word** sets how many readers must contribute.
4. Use **View** to explore the same text. **Measure on the stimulus** colors
   the words in their original positions. **Measure vs feature** compares the
   reading measure with a feature in the Words table, such as surprisal.
5. [Download the table and recipe](index.md#keep-the-result).

If your data has no mapped **Text ID**, open **Per text** to inspect a
single reading by its trial ID. To compare several readings, map the Words
column that identifies the same passage across participants. If the page
asks for reading measures, **Map reading measures** opens the column
mapping for an editable dataset. For an upload that contains only fixations
or gaze samples, **Add a Words table** opens the editor where you can attach
the report.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/corpus-analysis_poster.webp" data-autoplay
       aria-label="Corpus Analysis: a measure on the stimulus, against surprisal, and between two groups">
  <source src="../../../assets/workflows/corpus-analysis.mp4" type="video/mp4">
</video>

*The recording shows total fixation duration on a text, against GPT-2 surprisal,
and between two groups.*
