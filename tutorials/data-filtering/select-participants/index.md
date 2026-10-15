# Select participants by a field

Keep the participants an analysis is about — for example, the native speakers of one language whose calibration is good — and export their trial IDs.

## 1. Attach a participants table

Native language, age or a questionnaire score is recorded per participant, not per trial. Attach a participants table, one row per participant: under **Metadata → Participants** when you add the dataset, or later in **Data Management → Edit dataset → Data tables & column mapping**.

## 2. Filter on it

Its columns appear under **By participant** in the filter funnel. Pick the language, and the trial picker keeps only those participants' trials.

\[!\[

\](../../../assets/workflows/trial-filtering_poster.webp)\](../../../assets/workflows/trial-filtering.mp4)

*Narrowing the trials to one condition and one participant: from 24 trials to 6 — participant fields narrow the same way.*

## 3. Check their calibration and mark the trials

Step through the remaining trials and tag the ones to keep, such as `include`, or the ones to drop — see [Exclude unsuitable trials](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/exclude-unsuitable-trials/index.md).

## 4. Export the trial IDs

Export the annotations ( **Data Management → Annotations → Export**): each entry names its participant and trial. Or export the filtered pool as a bundle, whose `index.csv` lists every trial in it.

**Then:** [check and export the pool](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/#every-task-ends-the-same-way).
