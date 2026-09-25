---
description: The eye-tracking and app terms these docs use.
---

# Glossary

The terms the app and these docs use. A measure links to its entry in
[Computations & methodology](computations.md), which gives the exact formula,
its edge cases, and how far it has been verified.

## Eye movements

Fixation
:   A pause of the eyes on one spot. Each row of the fixation table is one; the
    figure draws it as a marker sized by duration.

Saccade
:   The jump from one fixation to the next, drawn as a line between them. The
    app classes each one by its role in reading — forward, skip, refixation,
    return sweep or regression
    ([`assign.saccade_class`](computations.md#assign-saccade-class)).

Regression
:   A saccade back to an earlier word
    ([`assign.progression`](computations.md#assign-progression)).

Return sweep
:   A saccade down to a later line — normally from the end of one line to the
    start of the next.

Scanpath
:   One reading's fixations in order, with the saccades between them.

Raw gaze
:   The tracker's sample-by-sample gaze positions, from before fixations were
    detected. An optional third table, drawn under the fixations.

Run, pass
:   Consecutive fixations on one word form a run; a word's first run is its
    first pass, its second run its second pass
    ([`assign.runs`](computations.md#assign-runs)).

## Words and the screen

Word box
:   The rectangle a word occupied on screen — its area of interest (AOI), or
    interest area (IA) in EyeLink's terms. It is taken from the data exactly as
    given, never recomputed
    ([`geom.word_box_bounds`](computations.md#geom-word-box-bounds)). A
    fixation counts for the word its data names (an imported word/IA id), else
    the word whose box contains it, else the word with the nearest centre
    within 50 px
    ([`assign.fixation_to_word`](computations.md#assign-fixation-to-word)).

Canvas
:   The recorded screen in pixels, such as 2560 × 1440 — the coordinate
    system every figure is drawn in.

True to scale
:   Text and fixations drawn at their recorded on-screen positions, with each
    word label sized from the word boxes
    ([`disp.true_scale`](computations.md#disp-true-scale)).

Recording setup
:   The monitor's physical size and the viewing distance. Together with the
    canvas they give pixels per degree of visual angle
    ([`geom.pixels_per_degree`](computations.md#geom-pixels-per-degree)).

Screen
:   One of several displays a single trial was read over — the pages of a
    long text, or its comprehension-question screens. Each screen keeps its
    own coordinate space and is never merged with another
    ([Data format](data-format.md)).

Critical span
:   A marked stretch of the text — in OneStop, the words that answer the
    trial's question (`is_in_aspan`) — highlighted in the figure.

## Reading measures

First fixation duration (FFD)
:   How long the first fixation on a word lasted, whenever it came
    ([`measure.ffd`](computations.md#measure-ffd)).

First-pass reading time (FPRT)
:   Also called gaze duration: the sum of the fixations in the word's first
    run, before the eyes first leave it
    ([`measure.fprt`](computations.md#measure-fprt)).

Regression-path duration (RPD)
:   Also called go-past time: from the word's first fixation until the first
    fixation on a later word, every regression in between included
    ([`measure.rpd`](computations.md#measure-rpd)).

Total fixation duration (TFD)
:   Every fixation on the word, in any pass
    ([`measure.tfd`](computations.md#measure-tfd)).

Single-fixation duration
:   The first fixation's duration, for a word whose first run was exactly one
    fixation ([`measure.single_fix`](computations.md#measure-single-fix)).

Second-pass duration
:   The sum of the fixations in the word's second run
    ([`measure.second_pass`](computations.md#measure-second-pass)).

Skip
:   A word not fixated before the eyes first moved past it; a word first reached
    by a regression still counts as skipped
    ([`measure.skip`](computations.md#measure-skip)).

Initial landing position
:   Where in the word the first fixation landed, in letters from its start
    ([`measure.landing_position`](computations.md#measure-landing-position)).

## The app's own terms

Trial
:   One reading: a participant and a trial id together. The same text read by
    two people is two trials.

Text
:   The stimulus (`text_id`) — what two trials of the same text share.

Dataset
:   One loaded corpus: the bundled demo, a public corpus, or tables you
    uploaded, each listed under 🗂️ **Data**.

Participant metadata
:   An optional table with one row per reader, whose columns become trial
    filters without being copied onto the words or fixations.

Illustration
:   A label the app puts on any figure that no longer shows the data exactly
    as recorded — snapped fixations, arced saccades, a subset of the fixations,
    a replay not at real time
    ([`disp.illustration`](computations.md#disp-illustration)).
