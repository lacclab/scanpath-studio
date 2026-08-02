---
name: new-feature
description: Scaffold a user-facing Scanpath Studio feature the house way — walk the matching AGENTS.md recipe (measure / figure / column / option) and enforce the "every surface" rule (UI + deep link + CLI + headless API) plus tests, docs, and changelog.
---

# New feature — every-surface scaffold

Argument: what's being added, e.g. `measure go-past time`,
`figure heatmap`, `column pupil size`, or `option saccade opacity`.

A user-facing feature is only **done** when it reaches every surface — not
just the UI. Follow the matching recipe, then close out with the checklist.

## Recipes (from AGENTS.md)

**New reading measure**
1. Compute it in `measures.compute_per_word_measures` per trial.
2. Add it to `WORD_OPTIONAL_FIELDS` in `data.py` if it can come
   pre-computed from EyeLink IA columns.
3. Surface it in `controls.color_field_options` (if useful for coloring)
   and register it in `aggregation.MEASURES` (feeds the measure pickers via
   `aggregation.available_measures`).
4. Add a test under `tests/test_measures.py`.

**New figure type**
1. Add a `make_*_figure` function in `plots.py` using the helpers
   `_compute_axis_ranges`, `_compute_marker_sizes`, `_saccade_segments`,
   `_add_word_label_trace`.
2. Wire it into a tab via `tabs.py`.
3. Add a smoke test in `tests/test_smoke.py` building it against the bundled
   sample.

**New column convention**
Update the candidate lists in `data.py` (e.g. `WORD_X_CANDIDATES`,
`FIX_DURATION_CANDIDATES`); `pick_column` picks the first existing column.
Optional passthrough columns go through the `WORD_OPTIONAL_FIELDS` /
`FIX_OPTIONAL_FIELDS` tables instead.

**New toggle / option / parameter** — go straight to the surface checklist.

## The four surfaces (all mandatory for user-facing features)

1. **Visual UI** — `controls.py` widget with a `global_*` / `single_*` /
   `filter_*` session key, read by `_collect_viz_settings`. Never rename
   existing widget keys — deep-link restore depends on them.
2. **Deep link / Share** — `url_state.py`: `_URL_PRESETS` +
   `_apply_url_preset` (read) and `_build_share_query` (write); add to
   `_URL_BOUNDED` if it needs clamping. Without this the Share widget won't
   round-trip it.
3. **CLI** — a `render` flag in `cli.py` (follow the per-layer `--no-*`
   pattern).
4. **Headless API** — a parameter on the relevant `api.py` builder
   (`plot_scanpath` / `animate_scanpath`) plus a default in
   `CANONICAL_FIGURE_DEFAULTS`, so headless output matches the app.

## Close-out checklist (verify each, report each)

- [ ] All four surfaces wired (or explicitly agreed out of scope with the user)
- [ ] Tests added (`tests/`), suite passes: `pytest -n auto`
- [ ] `ruff check --exclude other_vis .` + `ruff format --exclude other_vis .`
- [ ] One-line entry under `[Unreleased]` in `CHANGELOG.md`
- [ ] Docs page updated if user-visible behavior changed (`docs/`)
- [ ] Tracker item updated → `Pending approval` (use the `track` skill)

## Gotchas

- The spatial plot must stay on `tabs._render_true_scale_chart` — never
  switch it to `st.plotly_chart`.
- Verify behavior headlessly with
  `AppTest.from_file("streamlit_app.py")`; the live preview is slow. If a
  code change doesn't show in a running server, restart it — Streamlit
  doesn't reload imported modules, and `st.cache_data` doesn't hash
  transitively-called helpers.
