# CMP-11 · Overlay two scanpaths from different datasets

> **Status: design, 2026-08-12** — spec for the
> [improvements tracker](../tracker/index.html) → **CMP-11** ("Overlay two
> scanpaths from different datasets on a common scale"), split out of **CMP-8**.
> It also delivers **CMP-9** ("Compare mode has no CLI or headless-API surface"),
> which the four-surface rule makes unavoidable here.
>
> **The item was scoped down before implementation.** CMP-11 as filed asked for an
> **Align by** control with three modes — *Screen pixels*, *Visual angle*
> (px/degree rescaling per corpus), *Text box* (fit B's text bounding box onto
> A's). On 2026-08-12 the user withdrew that: **overlay two datasets only when
> they already share a screen, and never rescale.** What ships is a gate, not a
> transform. §9 records what was dropped and why, so the rescaling half isn't
> lost silently.

## Context

`plots._render_comparison_figure`'s overlay branch
([plots.py:5129](../scanpath_studio/plots.py:5129)) computes ONE
`_compute_axis_ranges` over both trials' fixations + word frames. Across two
monitors that is the union of two unrelated pixel spaces — well-defined and
scientifically wrong — so CMP-8 blocked the layout outright: a cross-dataset pair
resolves to *Side by side* ([tabs.py:3688](../scanpath_studio/tabs.py:3688)), and
a dual animation (an overlay on one clock) is refused the same way
([tabs.py:3992](../scanpath_studio/tabs.py:3992)).

The block is unconditional, and that is the bug this item fixes. Two corpora
recorded on the *same* screen pool into one honest coordinate space — no
transform required, because the pixels already mean the same thing. CMP-8's own
caption already special-cases that pair ("…which happen to share a 2560×1440
screen", [tabs.py:4581](../scanpath_studio/tabs.py:4581)) while still refusing to
overlay it.

**The user's stated main use case is exactly that pair**: two datasets from the
same lab, on the same monitor. So the whole item reduces to: recognise the case,
and let it through.

## Scope

**In:**

1. A pure `setups_comparable` predicate (§1) and symmetric snapshot resolution
   for A and B (§2).
2. The overlay gate and the dual-animation gate, both consulting that one
   predicate (§3).
3. A *Stimulus from* picker — `Both | A only | B only` (§4). Even on one screen,
   two datasets' word boxes only coincide if the text is identical.
4. Compare mode's headless surface — `api.compare_scanpaths` (§6) and
   `render --compare-*` (§7). This is **CMP-9**.
5. The share link + saved config (§8).

**Out:**

- Any coordinate transform: no px/degree rescaling, no text-box fitting, no
  translation. See §9.
- Recording real physical geometry for the bundled corpora (§1 note).
- Overlaying two datasets whose screens differ. That stays *Side by side*.

## 1. The predicate

New in `experimental_setup.py` — the module that owns `SetupSnapshot`, is pure
(no Streamlit, no pandas), and is already reachable from `api.py`:

```python
def setups_comparable(a: SetupSnapshot, b: SetupSnapshot) -> tuple[bool, str]:
    """Whether two datasets' readings can share one set of pixel coordinates.

    `(True, "")`, or `(False, reason)` where `reason` is a complete
    user-facing sentence — the UI caption, the CLI error and the API
    exception all print it verbatim rather than composing their own.
    """
```

Two conditions, both required:

| condition | why |
| --- | --- |
| `a.canvas == b.canvas` | the overlay pools raw pixel coordinates; different screens make that a category error |
| `screen_provenance` is `MEASURED` or `ESTIMATED` on **both** | `ASSUMED` means the 2560×1440 default was taken. Two defaults are two unknowns, not a known-equal, and letting them through would overlay on a coincidence of defaults |

**`monitor_width_mm` and `viewing_distance_mm` are deliberately not checked.**
With the transform dropped, nothing in the overlay path converts to degrees, so
the physical figures are never read. Requiring them would gate the feature on a
quantity it does not use — and, as the note below shows, would make it inert.

> **Why not the stricter rule.** The first draft required physical geometry to be
> recorded and equal. Every built-in corpus hard-codes `geometry: ASSUMED`
> ([app.py:2253](../scanpath_studio/app.py:2253),
> [wizard.py:1563](../scanpath_studio/wizard.py:1563),
> [compare_source.py:276](../scanpath_studio/compare_source.py:276)); only the
> wizard's "I know my monitor" branch ever reaches `MEASURED`. Under that rule no
> pair involving the demo, synthetic, PoTeC, MultiplEYE or OneStop could **ever**
> overlay — the feature would ship inert for every bundled corpus. Settled
> 2026-08-12: gate on the canvas.
>
> The residual cost is stated plainly, not hidden: two corpora at 1920×1080 on a
> 24″ and a 32″ monitor overlay as if identical. The figure claims only pixel
> positions, and the caption names both screens.

`screen_provenance` is `MEASURED`/`ESTIMATED`/`ASSUMED` only — the docstring on
`SETUP_GROUPS` notes geometry is the sole group that may be `SKIPPED` — so no
`SKIPPED` branch is needed for the screen.

## 2. Resolving A's and B's snapshots symmetrically

The gate compares provenance, so A and B must be resolved **the same way**. They
are not today:

- B goes through `compare_source._snapshot_for(name, words, fixations)`, which
  falls back to `app.resolve_source_monitor` and always yields `MEASURED` or
  `ESTIMATED`.
- A would go through `app.active_setup_snapshot()`, which returns `None` for an
  undeclared source and never consults `resolve_source_monitor`.

Using one for each would make the same corpus report different provenance
depending on which side of the comparison it landed on — a gate that says yes one
way round and no the other.

**Fix:** promote `compare_source._snapshot_for` to a public
`snapshot_for(name, words, fixations)` and use it for **both** sides. It is
already name-driven rather than B-specific.

**A's canvas is the rendered one.** The user can override A's screen in the
rail's 🖥️ *Screen & geometry* panel, and the figure is drawn to
`settings.canvas_width/height`. The gate must test what is actually rendered, so
the call site passes A's snapshot through `dataclasses.replace` with the live
canvas before calling the predicate. B's is `compare_meta["setup"].canvas`, which
is already what `_make_split_comparison_figure` draws B's panel to.

## 3. The gates

### 3.1 Overlay

Today the layout is resolved in the rail
([tabs.py:3678-3689](../scanpath_studio/tabs.py:3678)), before
`_render_compare_selector` has run and therefore before B's snapshot exists. It
**moves down** to after `_build_compare_meta`
([tabs.py:3764](../scanpath_studio/tabs.py:3764)), which is the first point B's
setup is known. Nothing between the two sites reads `compare_layout`; its only
consumers are the `_render_comparison_figure(layout=…)` call and §3.2.

```text
overlay + cross-dataset:
    setups_comparable(setup_a, setup_b) -> overlay renders, raw pixels
    otherwise                           -> resolve to side_by_side + reason
```

**Resolve, never rewrite.** `single_compare_layout` is left alone, exactly as
CMP-8 established, so switching back to a same-dataset pair restores the user's
Overlay.

The ⚙️ Compare options popover keeps a short generic note (it still cannot see
B). The authoritative explanation stays in the caption under the figure
([tabs.py:4564-4585](../scanpath_studio/tabs.py:4564)), which already knows both
screens and now also prints `reason` when the layout resolved away.

### 3.2 Dual animation

`dual_anim` currently reads `… and not cross_dataset`
([tabs.py:3992](../scanpath_studio/tabs.py:3992)). A co-animation is an overlay
on one clock, so it becomes `… and (not cross_dataset or comparable)` — the same
predicate, computed once and shared. The warning at
[tabs.py:4057](../scanpath_studio/tabs.py:4057) fires only when the pair is
genuinely incomparable, and prints `reason`.

## 4. *Stimulus from* — `Both | A only | B only`

New `FigureSettings.compare_stimulus: str = "both"` (`"both" | "a" | "b"`).
Consumed in the overlay branch of `_render_comparison_figure` and in
`make_scanpath_animation`'s dual path (it takes `words_b`, so the same question
applies): skip `build_word_boxes` + `_add_word_label_trace` for the unselected
side.

Added to the exclusion sets in **both** `STATIC_FIGURE_OPTIONS` and
`ANIMATION_FIGURE_OPTIONS` alongside `layout` / `style_a` / `canvas_b`, so
`api.figure_options()` stays honest about which builder takes it.

- Widget: `st.segmented_control` in ⚙️ Compare options, key
  `single_compare_stimulus`, `persist_state="session"`, rendered only when the
  resolved layout is overlay (each panel owns its own stimulus in a split
  layout, where hiding one is meaningless).
- **Default `both`**, so every existing same-dataset overlay is byte-identical.
- No resolve-away. Which stimulus to show is a judgement about the texts, which
  only the user can make.
- The word-box heatmap keeps using `reference_words` (the first non-empty word
  frame, i.e. A's), unchanged.

## 5. Merge helpers move to `utils.py`

`api.py` and `cli.py` now build cross-dataset comparisons, so they need the
participant-namespacing rule. Re-deriving it is exactly the bug
`tests/test_compare_cross_dataset.py` exists to catch: two corpora can hold the
same `(participant_id, trial_id)`, `make_comparison_figure` slices by exactly
that pair, and un-namespaced **both panels draw both scanpaths** and look
entirely plausible.

So four helpers are promoted out of `tabs.py` into `utils.py` — which
[AGENTS.md](../AGENTS.md) already names as the home for "comparison helpers" —
and lose their leading underscore:

| from | to |
| --- | --- |
| `tabs._qualify_for_compare` | `utils.qualify_for_compare` |
| `tabs._qualified_participant` | `utils.qualified_participant` |
| `tabs._unqualify_for_export` | `utils.unqualify_for_export` |
| `tabs._align_compare_columns` | `utils.align_compare_columns` |

`tabs.py` keeps module-level aliases under the old private names so existing test
references and call sites resolve unchanged. No behaviour change; the existing
cross-dataset tests are the guard.

No new module. `experimental_setup.py` takes the predicate, `utils.py` takes the
merge helpers, and the alignment module the first draft proposed is not needed
now the transform is gone.

## 6. Headless API (CMP-9)

```python
def compare_scanpaths(
    words, fixations,
    trial_a: tuple[str, str],
    trial_b: tuple[str, str],
    *,
    words_b=None, fixations_b=None,        # B from a different dataset
    layout="overlay",                       # overlay | side_by_side | stacked
    compare_stimulus="both",
    setup=None, setup_b=None,               # SetupSnapshot; canvas_size shorthand kept
    canvas_size=None, canvas_size_b=None,
    style_a=None, style_b=None,
    labels=None,
    base_font_size=16, font_family=FONT_FAMILY,
    fix_index_range=None,
    drift_correction=None, drift_connectors=False,
    title="", caption="",
    **figure_overrides,
) -> go.Figure
```

- Passing `words_b`/`fixations_b` makes it cross-dataset: B is namespaced through
  `utils.qualify_for_compare` and the two frames are column-aligned through
  `utils.align_compare_columns`, exactly as the app does.
- `SetupSnapshot` becomes part of the public API surface. `experimental_setup.py`
  is already pure and importable without `app`, so this needs no restructuring —
  its own module docstring anticipated it.
- **`layout="overlay"` on an incomparable pair raises `ValueError(reason)`.** It
  does not silently resolve to side-by-side the way the UI does: returning a
  differently-shaped figure than the one a script asked for is the wrong failure
  mode headlessly. A caller who wants the UI's behaviour asks for
  `layout="side_by_side"`.
- Unknown keywords go through the existing `_reject_unknown_options` against the
  comparison builder's option set, so a typo names the closest valid options.
- Re-exported lazily from the package root like the rest of `api.py`.

## 7. CLI (CMP-9)

A new `comparison` argument group on `render`
([cli.py:139](../scanpath_studio/cli.py:139)):

| flag | meaning |
| --- | --- |
| `--compare-with PID:TRIAL` | scanpath B. Required to enable compare mode. |
| `--compare-layout {overlay,side-by-side,stacked}` | default `overlay` |
| `--compare-stimulus {both,a,b}` | default `both` |
| `--compare-words PATH...` / `--compare-fixations PATH...` | B from a **second** dataset (files only) |
| `--compare-canvas WxH` | B's screen |
| `--monitor-mm` / `--viewing-distance` | A's physical geometry (`render` has `--canvas` but no physical geometry today) |
| `--compare-monitor-mm` / `--compare-viewing-distance` | B's |

The physical-geometry flags are accepted and stored on the snapshots but are not
read by this item's render path (§1). They are added because `SetupSnapshot` is
now on the CLI surface and a half-populated one is worse than a complete one.

B's second dataset is **files only** — `--compare-words/--compare-fixations`
through the same `data.read_tables` path A uses. Twinning every source flag
(`--compare-potec`, `--compare-onestop` + its regime/part/variant,
`--compare-multipleye`, `--compare-sample`, `--compare-authoring`) would roughly
double the render parser for a narrow case. Python callers have no such
restriction: `api.compare_scanpaths` takes B's frames directly, so any loader
works. Settled 2026-08-12.

Reuses the existing `--canvas` parser (`_parse_canvas`) for `--compare-canvas`.

## 8. Share link and saved config

| key | wire |
| --- | --- |
| `single_compare_stimulus` | `?cmp_stimulus=both\|a\|b` |
| `single_compare_layout` | `?cmp_layout=overlay\|side-by-side\|stacked` |

CMP-8 put `compare=<pid>:<trial>` and `cmp_source` on the link but **not** the
layout, so a shared comparison always reopened as Overlay (or, cross-dataset,
resolved to Side by side). Adding `cmp_layout` here closes that: it is the same
gap `cmp_stimulus` would otherwise re-open, and it costs one entry.

Wiring, per [AGENTS.md](../AGENTS.md) → *Exposing a feature on every surface*:

- Constants in `session_keys.py` (`SINGLE_COMPARE_STIMULUS`,
  `SINGLE_COMPARE_LAYOUT`, `COMPARE_STIMULUS_PARAM`, `COMPARE_LAYOUT_PARAM`),
  added to `SHARE_PARAMS`, `URL_SEEDED_STATE_KEYS` and `PLOT_CONFIG_STATE_KEYS`.
  `tests/test_session_key_contract.py` fails until they are pinned — that is the
  gate working.
- `url_state._SHARE_VALUE_PARAMS` (write) + `_URL_PRESETS` (read). Both are
  closed vocabularies, so an unknown value raises and the reader's "Ignored bad
  URL param" warning fires rather than the widget wedging — the same contract
  `_parse_align_algorithm` follows.
- Saved config: both ride in the existing compare section of
  `tabs._build_studio_config`. Adding optional keys does **not** bump
  `PLOT_CONFIG_SCHEMA_VERSION` — the reader already tolerates absent sections, so
  there is nothing for a migration to do (the same call ENG-23 made).

No illustration disclosure is needed. `illustration.illustration_reasons`
reports *geometry-changing* views; with the transform dropped, an aligned overlay
draws both readings in their own untouched pixel coordinates. Nothing is altered,
so labelling it as a schematic would be false.

## 9. What was dropped, and what would bring it back

CMP-11 as filed asked for an **Align by** control:

- **Visual angle** — scale each reading through its own monitor-mm + viewing
  distance so one degree is one degree on both.
- **Text box** — translate + scale so the two texts' bounding boxes coincide,
  for a corpus that never recorded its physical setup.

Both are dropped (2026-08-12, user's call): overlay only what already shares a
screen, and never rescale. The reasoning is that a rescaled overlay makes a
physical claim the data often can't support — and, per §1's note, **no bundled
corpus records the geometry a visual-angle mode would need**, so the mode would
have been unreachable for every built-in dataset on day one.

What would make it worth revisiting, in order:

1. Real `monitor_mm` / `viewing_distance` for the public corpora, sourced from
   each corpus's published methods, so `geometry_provenance` becomes `MEASURED`
   rather than `ASSUMED`. That is a research task, not a coding one.
2. Then a scale factor is computable, and *Visual angle* becomes a genuine option
   rather than a control that greys itself out everywhere.

A follow-up tracker item records this so the intent isn't lost. Anchors for
whoever picks it up: the transform would be a uniform affine applied to B only,
anchored on the text bounding-box top-left via `measures.word_box_bounds` (never
raw `x/y/width/height`), keeping the figure in **A's** pixel space so
`fit_to_monitor`, the VIZ-34 coordinate grid and A's word boxes need no rework.

## 10. Testing

New `tests/test_setup_comparable.py` — the predicate in isolation:

- equal canvas + `MEASURED`/`MEASURED` → comparable
- equal canvas + `MEASURED`/`ESTIMATED` → comparable
- equal canvas + `ASSUMED` on either side → not comparable, reason names it
- differing canvas → not comparable, reason names both screens
- differing `monitor_mm` / `viewing_distance` → **still comparable** (the
  regression guard for §1's deliberate omission)

`tests/test_compare_cross_dataset.py` extensions:

- a same-screen cross-dataset pair renders **one** overlay figure, and the
  assertions are on **per-scanpath trace** coordinates, not "both values appear
  somewhere in the figure" — the shape of check CMP-8 established, because the
  namespacing bug passes the weaker one
- a differing-screen pair still resolves to side-by-side
- `compare_stimulus="a"` drops B's word-box shapes and label trace while leaving
  B's fixation and saccade traces intact; `"b"` the mirror; `"both"` is
  byte-identical to the pre-CMP-11 figure

`tests/test_apptest.py` (or a compare-specific AppTest): the gate in both
directions through the real app, and `single_compare_layout` unchanged after a
resolve.

API + CLI: `compare_scanpaths` same-dataset and cross-dataset; the `ValueError`
on an incomparable overlay; `render --compare-with` end to end against the
bundled sample; `render --compare-words/--compare-fixations` for a second
dataset.

Contract tests that will fail until updated, by design:
`test_session_key_contract.py` (two new pinned keys) and
`test_widget_value_sync.py::test_every_wire_format_widget_declares_persist_state`
(the new widget must declare `persist_state`).

Live check: the bundled demo against the synthetic trial. Both resolve through
`resolve_source_monitor`, so it is a real pair reachable in a checkout with no
external corpora — but the demo declares OneStop's 2560×1440 while the synthetic
trial's canvas is inferred from its extents, so the pair most likely exercises
the **refusal** branch. Confirm which branch it hits and, if it refuses, drive
the accepting branch from two stored uploads given the same canvas in the wizard.
Both branches must be seen in the browser, not only under AppTest.

## 11. Docs, changelog, tracker

- `docs/` compare-mode page: when a cross-dataset overlay is allowed and why,
  what *Stimulus from* does, and the new CLI/API surface.
- `docs/` API reference picks up `compare_scanpaths` from its docstring
  (mkdocstrings) — keep that docstring complete.
- `CHANGELOG.md` `[Unreleased]`, two-tier shape: headline list first, then
  `### Details` with a short paragraph per item.
- `tracker/data.js`: **CMP-11** → `Review` with the four-paragraph write-up
  (*Request* naming the scope-down, *What was done*, *What's left* = the user's
  review, *Background* pointing at this doc). **CMP-9** → `Review`, delivered by
  §6 + §7. A new Backlog item for §9's dropped rescaling.
- Run `surface-parity-reviewer` and `perf-reviewer` before flipping either item
  to *Review*.

## 12. Build order

1. §1 predicate + §2 symmetric snapshots, with `tests/test_setup_comparable.py`.
   Pure, no UI, lands alone.
2. §5 helper promotion — a no-op refactor with the existing cross-dataset tests
   as its guard. Before anything that consumes it, so the diff that adds the
   headless surface stays small.
3. §3 the two gates. The feature is live in the UI at this point.
4. §4 `compare_stimulus` through `FigureSettings` → both builders → the widget.
5. §8 share link + saved config.
6. §6 `api.compare_scanpaths`.
7. §7 the CLI flags.
8. §11 docs, changelog, tracker.

## Critical files

`experimental_setup.py` (`SetupSnapshot`, `SETUP_GROUPS`) ·
`compare_source.py` (252 `_snapshot_for` → public) ·
`utils.py` (comparison helpers) ·
`tabs.py` (3678 layout resolution → moves below 3764 `_build_compare_meta`, 3591
the ⚙️ Compare options popover, 3992 `dual_anim`, 4421 `_render_comparison_figure`,
4564 the cross-dataset caption, 2365-2431 the helpers that move) ·
`plots.py` (55 `FigureSettings` — 154 `canvas_b`, 4949/5129 the comparison builders, 6448/6467
the option exclusion sets, 6530 `make_scanpath_animation`) ·
`api.py` (1138 `plot_scanpath` as the shape to follow, 1059 `figure_options`) ·
`cli.py` (139 `_render_parser`, 685 `_parse_canvas`, 809 `render`) ·
`url_state.py` (213 `_SHARE_VALUE_PARAMS`, 507 the compare read side, 1661 the
compare write side) · `session_keys.py`
