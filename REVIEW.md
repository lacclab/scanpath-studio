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
3. **Trigger:** a new widget on a persisted key.
   **Check:** `persist_state="session"`; no `value=` / `index=` on a gated
   (disabled) widget.
   **Why:** BUG-80 (the trial reset after visiting another view);
   `tests/test_widget_value_sync.py`.
4. **Trigger:** code writes a widget key that lives inside a popover.
   **Check:** it goes through `controls.write_through`.
   **Why:** #485 / #522 (a layer switch flipped back after a design preset).
5. **Trigger:** a new `st.*` element drawn *conditionally* above `sps_view`
   (a warning, markdown, an iframe).
   **Check:** it sits inside a container drawn every run.
   **Why:** an element more or fewer shifts every later element's position, and
   Streamlit redraws the whole view from nothing.
6. **Trigger:** a widget is skipped by `ui_mode` (an `if mode == …:` around a
   widget).
   **Check:** it renders in both modes and is hidden by CSS
   (`advanced_only` / `simple_only`) instead.
   **Why:** a widget not drawn loses its value.
7. **Trigger:** a new `st.select_slider`.
   **Check:** guarded against a single option.
   **Why:** the browser slider throws and blanks the tab; AppTest can't see it.

## Data

8. **Trigger:** a `merge`, `.map(dict)` or lookup keyed on `word_id` or another
   id that can be missing.
   **Check:** missing keys are dropped first.
   **Why:** pandas joins NaN to NaN; #359, #416.
9. **Trigger:** a string column built from mixed values, a `None` sentinel, or
   `astype(str)` on an id.
   **Check:** correct under pandas 3 (string inference turns `None` into NaN);
   ids go through `data.stable_id`.
   **Why:** BUG-36, BUG-53, BUG-60, #524 — each passed locally on pandas 2.
10. **Trigger:** a trial filter or condition applied to one table's rows.
    **Check:** it decides readings `(participant_id, trial_id)` and applies to
    every table, raw gaze included.
11. **Trigger:** code that rewrites a `_datasets[name]` entry.
    **Check:** `column_names` is carried along.
    **Why:** the user's own column names vanish from every surface otherwise.
12. **Trigger:** a metadata table touched outside `metadata.py`.
    **Check:** it is never broadcast onto the word/fixation frames; it stays with
    its dataset (`metadata.activate_dataset`).
    **Why:** DATA-47, #380.

## Performance

13. **Trigger:** a new `@st.cache_data` function, or a new large frame built
    every rerun.
    **Check:** DataFrame params underscore-prefixed with an explicit
    `data.frame_fingerprint` key; no sampling in a fingerprint; no Streamlit
    element created inside the cached function.
    **Why:** BUG-103 / #314 (sampled keys served stale results); #342.
14. **Trigger:** a new slow step (a loop over trials, a file read, a build).
    **Check:** a `loading.card` with `progress.report()`, not `st.spinner`.

## Figures and export

15. **Trigger:** a new figure option (a parameter on a `make_*` builder or
    `FigureSettings`).
    **Check:** all four surfaces — UI, link / settings file, `render` flag,
    `api.py` keyword with a `CANONICAL_FIGURE_DEFAULTS` entry — plus a
    `code_snippet` emitter and a row in AGENTS.md's render-path table.
    **Why:** `tests/test_render_every_option.py`; the `surface-parity-reviewer`.
16. **Trigger:** a spatial figure rendered in a view.
    **Check:** through `tabs._render_true_scale_chart`, never `st.plotly_chart`.
17. **Trigger:** shapes added to a figure.
    **Check:** one `fig.layout.shapes = …` assignment, not `add_shape` in a loop.
18. **Trigger:** a new top-level trace in `make_scanpath_figure`.
    **Check:** named in `plots._trace_layer`.
19. **Trigger:** a new code path that writes a file for the user.
    **Check:** the citation is stamped into it (`file_citation`).
20. **Trigger:** a use of Kaleido.
    **Check:** under `animation_export.KALEIDO_LOCK`.
    **Why:** #440 (export hung on macOS).

## Compare

21. **Trigger:** code that shows or exports a scanpath B id.
    **Check:** it goes through `utils.unqualify_for_export` — the namespaced id
    exists only in the throwaway compare frames.

## Tests and docs

22. **Trigger:** a test changed by adding a `sleep`, a retry, a `skip`, or a
    looser assertion.
    **Check:** the flake's cause is fixed instead — or the test is deleted with
    the reason in the commit message.
23. **Trigger:** a comment or docstring added or edited.
    **Check:** it describes the code as it is now — no issue numbers, dates or
    "used to" history.
24. **Trigger:** a user-visible change.
    **Check:** a `changelog.d/` fragment; `CHANGELOG.md` untouched; a
    `feature-map.md` row in `.claude/skills/verify/` when a feature was added.
