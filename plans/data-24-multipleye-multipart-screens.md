# DATA-24 · MultiplEYE: show all of a trial's screens

> **Status: design, 2026-08-12** — spec for the
> [improvements tracker](../tracker/index.html) → **DATA-24** ("MultiplEYE shows
> one page per trial; expose every screen of a trial"). Depends on the multipart
> / subtrial screen support already on `main`
> ([`multipart.py`](../scanpath_studio/multipart.py)).

## Context

MultiplEYE models **one trial per `(stimulus, page)`**
([datasets.py:717](../scanpath_studio/datasets.py:717)):
`trial_id = "Lit_Alchemist_4__page_01"`, `text_id = "Lit_Alchemist_4"`. The
comment at that line says why — *"One stimulus spans several screens `page_1..
page_N` that all reuse the same on-screen coordinates. Combining them would stack
every page's word boxes and fixations at the same pixels"* — and at the time
that was the only non-overlapping option available.

It is no longer. `multipart.py` gives a trial an ordered set of `screen_id`s,
each its own coordinate space, and every consumer already honours it:
`grouping_columns` keeps measures/saccades/passes from crossing a screen
boundary, `tabs._render_screen_navigator` steps through screens beside the trial
picker, `?screen=` rides the share link, and the CLI has `--screen`,
`--all-screens` and `--list-screens`.

So the corpus's own structure — one *reading* per stimulus, presented as a
sequence of screens — can be modelled directly instead of being shredded into
per-page pseudo-trials. Two things follow that the current shape can't express:
a reader's pages belong to one trial, and the **comprehension-question screens**
(dropped entirely today) can take their place in that sequence.

## Scope

**In.** Reading pages **and** comprehension-question screens, as ordered screens
of one stimulus-level trial, on the directory loader and the browser-upload path,
with the enrichment (reading measures, questions, images, fonts, reader metadata)
following each to the right screen.

**Out.** `familiarity_rating_screen_*` and `subject_difficulty_screen` — the
corpus ships no AOI file for them, so they would be word-box-less screens and
`multipart.validate_matching_parts` rejects those by design. Excluded on the
user's call (2026-08-12); revisit only if that validation rule is ever relaxed.

**Out.** A redirect for old per-page share links (see §7).

## 1. Identity

| | today | after |
| --- | --- | --- |
| `trial_id` | `Lit_Alchemist_4__page_01` | `Lit_Alchemist_4` |
| `text_id` | `Lit_Alchemist_4` | unchanged |
| `participant_id` | `001_ZH_CH_1_ET1` | unchanged |
| `screen_id` | — | `page_1` … `page_5`, `question_4111` … |
| `screen_index` | — | 1..N, from that reader's fixation onsets |
| `screen_kind` | — | `reading` \| `question` |
| `canvas_width/height` | — | 1920 × 1080 on every screen |

`screen_id` is the corpus's own `page` value, **unpadded**. The zero-padding
(`_multipleye_page_label`, `page_1` → `page_01`) existed for exactly one reason —
the per-page `trial_id` was what the trial picker sorted on, so `page_10` had to
not fall between `page_1` and `page_2`. `screen_index` orders screens now, so the
padding goes and `_multipleye_page_label` / `_multipleye_trial_id` /
`_MULTIPLEYE_PAGE_SEP` are deleted.

**`screen_index` must come from the reader's own onsets, not from the screen
name.** Reading pages are presented in page order, but **question order is
shuffled per reader** — `001_ZH_CH_1_ET1` on `Lit_Alchemist_4` saw
`question_4132` before `question_4131`, and on `Lit_Solaris_8` saw
`question_8122` before `question_8121`. So the loader computes
`min(onset)` per `(participant_id, stimulus, page)` from the fixations, ranks it,
and merges the rank onto both frames. Ranking runs over the *included* screens
only, so indices stay contiguous 1..N with the rating/difficulty screens dropped.
(The one exception — a reading-pages-only load, where page order is page-number
order for every reader and the boxes can stay stimulus-level — is in §5.)

`canvas_width` / `canvas_height` are stamped from `MULTIPLEYE_MONITOR` on every
screen, so `multipart.screen_canvas_size` reports the real screen rather than
inferring one.

`trial_id` now equals `text_id`. That is correct — one reading of one stimulus is
one trial — and it collides with nothing: no session in the sample reads the same
stimulus twice (checked across all 30 trial files, including the PRACTICE trial,
whose stimulus is disjoint from that session's real trials).

## 2. Where question screens come from

Only the raw `fixations/` files carry them. The default `fixation_source`
(`scanpaths/`) is pre-filtered to reading pages, and is also a *different row
set* — 116 rows vs. the fixation file's 129 reading rows on
`001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4`, because the scanpath export drops
fixations it could not tag.

**Decision (user, 2026-08-12): always pull question screens from `fixations/`,**
whatever `fixation_source` says. Reading pages keep coming from the chosen
source, so the default load keeps its word-tagged reading fixations. The cost is
mixed provenance inside one trial, and the mitigation is that it is *visible*:
`screen_kind` distinguishes the two, and `docs/multipleye.md` states it plainly.
The two rejected options are recorded in §8.

## 3. Question-screen word boxes

Three joins, all verified against the ZH-CH-Zurich sample.

**(a) Which layout the reader saw.**
`stimuli_*/config/stimulus_order_versions_*.csv` has one row per
`version_number` with an optional `participant_id`; 106 of 250 versions are
assigned. The bare pid (`001` → `1`) resolves to a version number, which names
both the AOI rows (`question_image_version == "question_images_version_<N>"`)
and the image directory. Verified: pid 1 → version 71, pid 14 → 22, pid 46 →
225, and all three image directories exist. Sanity-checked geometrically —
version 71's AOI blocks for `Lit_Alchemist_4_question_04111` sit at
y ∈ {88, 247.75, 436.04, 743.25}, and that reader's `question_4111` fixations
span y ∈ [93.7, 780.0].

Both sessions of a pid (ET1 and ET2) share one version — the file keys on the
participant, not the session.

**(b) Which AOI rows belong to a screen.** The fixation page is
`question_4111`; the AOI `page` values are
`Lit_Alchemist_4_question_04111_{target,distractor_a,distractor_b,distractor_c}`
plus a stem block `question_04111`. The digits differ only in zero-padding of
the stimulus id (`Lit_Alchemist_4` → `04111`; `Arg_PISACowsMilk_10` → `10111`,
already 5 digits), so **match on `int(question_id)`, never on the string.**
Checked across all 30 trials: every question id seen in a fixation file is
present in that stimulus' AOI questions file, and every reader saw all six.

**(c) Word ids within the screen.** `word_idx` restarts in each of the five
blocks, so it cannot be the word id. Re-index: order the blocks by the geometry
of their first character (`top`, then `left`), then run a single counter over
`(block, word_idx)` in that order → `word_idx` unique within the screen, in
reading order. `line_idx` is re-indexed the same way. The block name
(`stem` / `target` / `distractor_a` …) is kept as a word-level `aoi_block`
column — it is genuinely useful as a per-word facet, not just bookkeeping.

Reading-page word boxes are unchanged: `word_idx` is already unique within a
page, which is now a screen.

**Coordinates.** Question AOIs use the same image-relative frame as page AOIs
and shift by the same `_MULTIPLEYE_IMAGE_ORIGIN` (305, 44.5).

## 4. Enrichment, per screen

- **Stimulus image.** Question screens get
  `question_images_zh_ch_1/question_images_version_<N>/<Stim>_id<n>_question_<qid>_<lang>.png`
  — verified present, and **1310 × 991**, the same size as a page image, so
  `image_x`/`image_y` stay `_MULTIPLEYE_IMAGE_ORIGIN` and the underlay lines up
  unchanged. `<qid>` is the **padded** 5-digit form from the AOI file, not the
  fixation's.
- **Reading measures.** Reading pages only — the corpus computes none for
  question screens. Question-screen words carry `NaN` in the `IA_*` columns,
  which is what the app already means by "no pre-aggregated measure".
- **Comprehension questions / reader metadata / font** are stimulus- or
  reader-level and are stamped as they are today; nothing about them is
  per-screen.

## 5. Two robustness rules

**Word boxes go per-reader whenever question screens are included.** They already
do on the default directory path (`reading_measures/` ships, so
`_multipleye_words_per_reader` runs), and question screens make it mandatory:
both the layout version and the `screen_index` are reader-specific.

The stimulus-level `MULTIPLEYE_WORD_SCHEMA` stays, because one case still needs
it — a **reading-pages-only** load (uploads with no versions file, or
`include_question_screens=False` with no `reading_measures/`). There, page order
*is* page-number order for every reader, so `screen_index` can be derived from
the page name and the boxes stay stimulus-level and broadcast as they do today.
Keeping the constant also means `wizard.py`'s MultiplEYE upload branch
([wizard.py:1390](../scanpath_studio/wizard.py:1390)) needs no change.

Both schema dicts gain `screen_id="page"` and `screen_index="screen_index"`;
the fixation schema also gains `canvas_width` / `canvas_height` and an optional
`screen_timestamp` (`onset` re-zeroed per screen — `onset` itself stays the
parent-global clock). `data._copy_screen_fields`
([data.py:1921](../scanpath_studio/data.py:1921)) already accepts all of these
schema keys, so no plumbing is needed in `data.py` for them.

**Word screens are scoped to the screens the reader actually fixated.**
`multipart.validate_matching_parts` raises on a screen present in one table and
absent from the other, and it is called from `data.harmonize_frames`
([data.py:1500](../scanpath_studio/data.py:1500)) on both the app and API paths.
All 30 sample trials match exactly today — every reader fixated every page of
every stimulus, and every question — but a reader who skips a page must degrade,
not crash. So the per-reader word frame is inner-joined to the
`(participant_id, trial_id, screen_id)` set present in that reader's fixations.

## 6. Upload path

`multipleye_frames_from_uploads` recovers identity from `source_file` because
browsers strip folders. It gains the same restructure, and degrades where the
inputs allow:

- Reading pages → screens: works from the uploaded AOI + fixation files alone.
- Question screens: need **both** `*_aoi_questions.csv` **and**
  `stimulus_order_versions_*.csv` uploaded. Without the versions file the reader's
  layout is unknowable, so question screens are skipped with a warning rather
  than guessed — picking an arbitrary version would draw AOI boxes in the wrong
  places and look entirely plausible.
- Question images are directory-only, as page images already are.

## 7. Surfaces

The four-surface rule is satisfied by what multipart already shipped — this
change is loader-side, so every screen-aware surface picks it up with no wiring:

| surface | mechanism | change |
| --- | --- | --- |
| UI | `tabs._render_screen_navigator` beside the trial picker | none |
| Deep link / Share | `?screen=` (`url_state.py:548`, `:1717`) | none |
| CLI | `render --screen` / `--all-screens` / `--list-screens` | none |
| Headless API | `plot_scanpath(screen=…)`, `animate_scanpath`, `list_screens` | none |

The one new knob is a loader kwarg, `include_question_screens: bool = True`, on
`multipleye_raw_frames` and `load_multipleye`. It is not a CLI flag: `render`
takes frames/files, not a corpus root, so the loader kwargs (`sessions`,
`stimuli`, `fixation_source`) have never had CLI surface. The app's MultiplEYE
source panel gains nothing — question screens are on by default.

**Deliberate break.** Share links carrying
`trial_id=Lit_Alchemist_4__page_01` stop resolving; the trial is now
`Lit_Alchemist_4` + `screen=page_1`. No redirect, per the house rule against
back-compat shims (CLAUDE.md → *Building features*). `url_state`'s existing
"Ignored bad URL param" path handles it as an unknown trial id.

## 8. Decisions settled before implementation

All four were put to the user on 2026-08-12 and answered.

1. **Which screens?** → reading pages **and** question screens. (Rejected:
   pages only; every screen incl. rating/difficulty.)
2. **Where do question fixations come from?** → always `fixations/`, with
   `screen_kind` marking the mixed provenance. (Rejected: *only when
   `fixation_source="fixations"`*, which hides questions from the default load;
   and *switch the default source to `fixations/`*, which costs the pre-filtering
   and the corpus's own word linkage on reading pages.)
3. **On by default?** → yes; `include_question_screens=False` opts out.
4. **Word ids?** → unique **within a screen**, keeping the corpus's native
   `word_idx` on reading pages. (Rejected: stimulus-global cumulative ids. They
   would let Corpus Analysis aggregate a whole text without page-1 word 0
   colliding with page-2 word 0 — a real defect, but a **pre-existing** one, since
   `text_id` is already the stimulus today. Fixing it means diverging from the
   corpus's published `word_idx`, so it belongs in its own item, not smuggled in
   here.)

## 9. Testing

Extend [`tests/test_multipleye_enrichment.py`](../tests/test_multipleye_enrichment.py)
and add a `tests/test_multipleye_screens.py`, all against small hand-built
fixtures (the 853 MB corpus is not in CI):

- One stimulus trial carries `screen_id` per page, `screen_index` 1..N, and
  `trial_id == text_id`.
- `screen_index` follows **onsets**, not names: a fixture whose question onsets
  are out of id order must produce the onset order.
- Question AOI selection picks the reader's version and rejects a string match
  on the unpadded id (`4111` vs `04111`).
- Question-screen `word_idx` is unique within the screen and follows the block
  geometry; `aoi_block` is populated.
- A reader missing a page produces no orphan screen — `harmonize_frames`
  succeeds and that screen is simply absent.
- `multipleye_frames_from_uploads` without a versions file yields reading screens
  only, and warns.
- `include_question_screens=False` yields reading screens only.
- Round-trip: `api.plot_scanpath(..., screen="question_4111")` builds, and
  `api.list_screens` returns the ordered set.

## 10. Files

- `scanpath_studio/datasets.py` — the MultiplEYE section (from ~line 703). New:
  version lookup, question-AOI reader, screen-index derivation, `screen_kind`,
  `screen_id`/`screen_index`/canvas keys on both schemas. Deleted:
  `_multipleye_page_label`, `_multipleye_trial_id`, `_MULTIPLEYE_PAGE_SEP`.
- `scanpath_studio/data.py` — register `screen_kind` and `aoi_block` as
  passthrough columns in `WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS`. Nothing
  else: the screen/canvas schema keys are already plumbed.
- `docs/multipleye.md` — rewrite the *Modelling decisions* section; document the
  mixed provenance and the versions-file requirement on upload.
- `scanpath_studio/CLAUDE.md`, `AGENTS.md` — the `datasets.py` MultiplEYE entry
  still says "each stimulus *page* is its own trial".
- `tests/` — as §9.
- `CHANGELOG.md`, `tracker/data.js` — DATA-24.
