# Analyze a corpus

Move from single scanpaths to a text, condition or group-level result. Each
page below is one task.

<div class="grid cards" markdown>

- :material-text-box-search-outline:{ .lg .middle } **[Analyze one text](analyze-one-text.md)**

    How one text was read, word by word, across its readers.

- :material-chart-box:{ .lg .middle } **[Compare groups or conditions](compare-groups.md)**

    Two cohorts or conditions side by side, with their difference.

- :material-chart-timeline-variant:{ .lg .middle } **[See progression over time](progression-over-time.md)**

    How reading changes over a session, for a participant or a group.

</div>

## Before you start

Corpus Analysis shows the reading measures your interest-area table brings
(mapped under **Reading measures** when you add or edit a dataset); it computes
none itself. The bundled demo has them. With fixations alone, compute the
measures with your own pipeline (EyeLink Data Viewer's interest-area report, for
example), join them onto your Words (interest areas) table by participant, trial
and word ID, and load that; EyeLink's `IA_*` names map themselves.

**Define the pool.** Narrow the trials with the Scanpath view's filter or
**Edit filters** at the top of Corpus Analysis. The line beside the dataset
picker there counts the trials and participants left and names each active
filter; **Clear** resets them. A text ID must identify the same stimulus across
participants; a trial ID identifies one trial.

## Keep the result

Select **Download this table (CSV)** beside a result, and **Download the recipe
(JSON)** beside it. The recipe records how the table was made: the app version,
the dataset's name, the trial filters, the view's text, screen, measure,
aggregation, normalization, spread, minimum participants and group definitions,
and the trial and participant counts. It names the dataset rather than copying
it, and holds no figure settings. A Share link carries neither the filters nor
the Corpus Analysis choices.
