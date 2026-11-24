# REVIEW.md — what to check, triggered by the diff

The reviewer's checklist for this repo. Each item has a **trigger** you can read
off a diff, the **check** to make when it fires, and **why** — the bug or PR it
came from. Check only the items whose trigger matches; a typical change fires
a handful. The `diff-reviewer` agent reads this file **from `origin/main`**, so a
change can't weaken the checks that judge it. Edit it in a PR of its own.

Report each finding as **Important** (breaks something a user has or does),
**Nit**, or **Pre-existing** (it was there before this diff, so it isn't the
author's to fix here). Say which item fired and why it matters.

## Adding an item

An item earns its place when the same mistake shows up in **two or more PRs**
(review comments, reverts, fix commits) **and** its trigger can be read off a
diff. Cite them. Delete an item when its check moves into a test — a test is
cheaper than a reviewer and never forgets.

## State and the wire format

1. **Trigger:** a `global_*` / `single_*` / `filter_*` / `cmp*` key, a URL param
   or a settings-file key is renamed or removed.
   **Check:** old links and saved files still restore — an alias, a migration,
   or a `changed`/`removed` changelog fragment that says what breaks.
   `tests/test_session_key_contract.py` updated on purpose, not to make it pass.
   **Why:** released share links and settings files are in users' hands.
2. **Trigger:** the settings file's shape changes (`plot_config.py`, a section
   or key in `url_state._restore_plot_config`).
   **Check:** `PLOT_CONFIG_SCHEMA` bumped, a migration registered, and the
   migration leaves an annotations-only file without plot sections.
   **Why:** BUG-73 (an annotations backup reset the figure); v6→v7, v7→v8.
3. **Trigger:** code writes a widget key that lives inside a popover.
   **Check:** it goes through `controls.write_through`.
   **Why:** #485 / #522 (a layer switch flipped back after a design preset).
4. **Trigger:** a new `st.*` element drawn *conditionally* above `sps_view`
   (a warning, markdown, an iframe).
   **Check:** it sits inside a container drawn every run.
   **Why:** an element more or fewer shifts every later element's position, and
   Streamlit redraws the whole view from nothing.
5. **Trigger:** a widget is skipped by `ui_mode` (an `if mode == …:` around a
   widget).
   **Check:** it renders in both modes and is hidden by CSS
   (`advanced_only` / `simple_only`) instead.
   **Why:** a widget not drawn loses its value.
6. **Trigger:** a new `st.select_slider`.
   **Check:** guarded against a single option.
   **Why:** the browser slider throws and blanks the tab; AppTest can't see it.

## Data

7. **Trigger:** a `merge`, `.map(dict)` or lookup keyed on `word_id` or another
   id that can be missing.
   **Check:** missing keys are dropped first.
   **Why:** pandas joins NaN to NaN; #416, #523.
8. **Trigger:** a string column built from mixed values, a `None` sentinel, or
   `astype(str)` on an id.
   **Check:** correct under pandas 3 (string inference turns `None` into NaN);
   ids go through `data.stable_id`.
   **Why:** BUG-36, BUG-53, BUG-60, #524 — each passed locally on pandas 2.
9. **Trigger:** a trial filter or condition applied to one table's rows.
   **Check:** it decides readings `(participant_id, trial_id)` and applies to
   every table, raw gaze included.
10. **Trigger:** code that rewrites a `_datasets[name]` entry.
    **Check:** `column_names` is carried along.
    **Why:** the user's own column names vanish from every surface otherwise.
11. **Trigger:** a metadata table touched outside `metadata.py`.
    **Check:** it is never broadcast onto the word/fixation frames; it stays with
    its dataset (`metadata.activate_dataset`).
    **Why:** DATA-47, #380.

## Performance

12. **Trigger:** a new fingerprint, or a new large frame built every rerun.
    **Check:** the frame is hashed in full or named by its source
    (`data.frame_fingerprint`, `data.stamp_source`), never sampled.
    **Why:** BUG-103 / #314 (sampled keys served stale results); #342.
13. **Trigger:** a new slow step (a loop over trials, a file read, a build).
    **Check:** a `loading.card` with `progress.report()`, not `st.spinner`.

## Figures and export

14. **Trigger:** a new figure option (a parameter on a `make_*` builder or
    `FigureSettings`).
    **Check:** all four surfaces — UI, link / settings file, `render` flag,
    `api.py` keyword with a `CANONICAL_FIGURE_DEFAULTS` entry — plus a
    `code_snippet` emitter and a row in `RENDER_PATHS.md`.
    **Why:** `tests/test_render_every_option.py`; the `surface-parity-reviewer`.
15. **Trigger:** a spatial figure rendered outside the Scanpath view's plot
    (Corpus Analysis, a dialog).
    **Check:** through `tabs._render_true_scale_chart`, never `st.plotly_chart`.
16. **Trigger:** a new code path that writes a file for the user.
    **Check:** the citation is stamped into it (`file_citation`).
17. **Trigger:** a use of Kaleido.
    **Check:** under `animation_export.KALEIDO_LOCK`.
    **Why:** #440 (export hung on macOS).

## Compare

18. **Trigger:** code that shows or exports a scanpath B id.
    **Check:** it goes through `utils.unqualify_for_export` — the namespaced id
    exists only in the throwaway compare frames.
19. **Trigger:** a scanpath-B counterpart of something A has: a `cmp*` key, a
    `--compare-*` flag, a `CompareTarget` field, a `*_b` keyword.
    **Check:** B's side carries everything A's does for it — saving and
    restoring, options, mappings and the warnings that go with them.
    **Why:** #428 (B lost on a refresh), #429 (an option only A had), #588 (B's
    filters not cached), #592 (B's mapping and its caveats missing from
    Share → Code).

## Tests and docs

20. **Trigger:** a test changed by adding a `sleep`, a retry, a `skip`, or a
    looser assertion.
    **Check:** the flake's cause is fixed instead — or the test is deleted with
    the reason in the commit message.
21. **Trigger:** a test that checks a rule by scanning the code (an AST walk,
    a spy) or by running every case of something (a matrix, a registry).
    **Check:** a mutation written in the code's most common style fails it, not
    only a hand-picked example; and its expected values come from the inputs or
    stated constants, never from what the code under test produced.
    **Why:** #588 (the `persist_state` scan skipped widgets drawn by helpers),
    #591 (the cache check skipped unannotated parameters), #592 (the shape
    matrix read its expected counts back from the loaded frames).
22. **Trigger:** a comment or docstring added or edited.
    **Check:** it describes the code as it is now — no issue numbers, dates or
    "used to" history.
23. **Trigger:** a user-visible change.
    **Check:** a `changelog.d/` fragment; `CHANGELOG.md` untouched; a
    `feature-map.md` row in `.claude/skills/verify/` when a feature was added.

## Checked by tests, not here

Rules that used to be items, now enforced by a test; no need to check them by
hand.

- A widget on a saved key passes `persist_state="session"` and no `value=` /
  `index=`: `tests/test_widget_value_sync.py`.
- A cached function takes its DataFrames `_`-prefixed and draws nothing:
  `tests/test_cache_conventions.py`.
- The Scanpath view draws its figures at true scale: `tests/test_true_scale_path.py`.
- Shapes go into a figure in one assignment: `tests/test_smoke.py`
  (`test_layout_shapes_are_validated_about_once`).
- Every trace of a scanpath or comparison figure is filed under its layer:
  `tests/test_trace_layers.py`.
- A rail control holds the range a link or settings file is held to, and a
  link reads back every value a menu offers: `tests/test_widget_bounds.py`,
  `tests/test_url_garbage.py`.
- ✏️ Edit dataset gives what ➕ Add dataset gives from the same files and
  mapping: `tests/test_properties.py`.
- What a link carries, a settings file carries, and the recovery cache keeps:
  `tests/test_saved_state_contract.py`.
- Released links, settings files and caches still restore:
  `tests/test_wire_golden.py`.
