# Audit an experimenter

When several people run sessions, check each experimenter's work: whether their participants are calibrated well, and whether problems recur in their sessions.

You need to know which experimenter ran each session. Keep that as a column in your data (under **Extra fields to keep** when you add the dataset), or as a column of a participants table (**Metadata → Participants**). Either way it becomes a filter in the trial picker's filter funnel — a data column among the conditions, a participants-table column under **By participant**.

## Review one experimenter's sessions

1. Open the filter funnel beside the trial picker and pick the experimenter.
1. Step through their trials with ◀ ▶, and [replay](https://lacclab.github.io/scanpath-studio/tutorials/data-collection/check-a-session/#3-replay-the-recording) the ones that look wrong.
1. In **Annotations**, tag what you find, such as `calibration` or `blink`, with the experimenter's name in the note, so the review is one export away.

\[!\[

\](../../../assets/workflows/trial-filtering_poster.webp)\](../../../assets/workflows/trial-filtering.mp4)

*Narrowing the trial list by a condition and one participant — the same funnel narrows it to one experimenter.*

## Compare two experimenters

1. Turn on **Compare**.
1. Narrow scanpath A's trials to one experimenter, and scanpath B's — with the filter funnel on B's own row — to the other.
1. Pick trials of the same text, marked 📄, and compare how the two sets of recordings look: precision, missing stretches, drift.

Save what you found as in [Check a session](https://lacclab.github.io/scanpath-studio/tutorials/data-collection/check-a-session/#5-save-the-review).
