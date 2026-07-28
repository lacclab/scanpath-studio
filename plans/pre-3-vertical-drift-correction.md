# PRE-3 · Visualize vertical alignment (drift-correction) algorithms

> **Status: Implemented 2026-06-28** (design approved 2026-06-23). Pending sign-off.
> Design doc for the [improvements tracker](../tracker/index.html) → **PRE-3** ("Vertical drift correction (`snap_to_lines`) + before/after viz"). It also settles the **PRE-0 ADR** (eyekit vs. reimplement) in favor of a **native port**: eyekit is **GPL-3.0** (incompatible with this MIT project distributed on PyPI), while the canonical `jwcarr/drift` code is **CC BY 4.0** (port with attribution) + `scipy` (BSD-3). This doc serves as the PRE-0 ADR.

## Context

Scanpath Studio shows eye-tracking-while-reading scanpaths, but raw fixation `y` coordinates *drift* vertically over a trial, so fixations don't line up with the text lines they belong to. The eye-tracking field has a standard family of **vertical drift-correction / line-assignment algorithms** — Carr et al. (2021), *Algorithms for the automated correction of vertical drift in eye-tracking data* (Behavior Research Methods): **attach, chain, cluster, compare, merge, regress, segment, split, stretch, warp**. Each maps a fixation sequence onto the text's lines.

Today the app has only the naive baseline (`measures.assign_fixation_lines` = nearest-line-by-y, i.e. *attach*) behind the "color fixations by line" option. This feature adds all 10 algorithms and two ways to see them: a **side-by-side comparison grid** and an **in-place correction** on the main plot. Goal: let researchers compare how each algorithm assigns fixations to lines for a given trial and apply a chosen one live.

> **Algorithm set note:** This is the Carr et al. (2021) set of **10** (the `jwcarr/drift` repo). It does **not** include `slice` (a later addition present in eyekit but outside the 2021 paper) — note that PRE-3's original wording listed `slice` and omitted `attach`/`compare`; this plan supersedes that list.

## Confirmed decisions (with the user)

- **Port natively**, not eyekit. `eyekit` is **GPL-3.0** (copyleft → incompatible with this MIT project distributed on PyPI). The canonical algorithm code (`jwcarr/drift`) is **CC BY 4.0** — port with attribution. `scipy` (BSD-3) is added for the two optimizer-based algorithms + k-means.
- **UI = both**: (a) a comparison-grid subtab, (b) an in-place single-algorithm correction on the main plot.
- **Corrected rendering**: snap each fixation's `y` to its assigned line center + color by assigned line, with a toggle for faint connector lines (original → corrected position).
- **All 10 algorithms.**

## 1. New module `scanpath_studio/alignment.py`

Attribution: module docstring + a top-level `NOTICE` constant crediting Carr et al. (2021), linking CC BY 4.0, noting "adapted/modified". Pure functions, no Streamlit.

**Core dispatch** (operates on numpy arrays):
```python
ALGORITHMS = ("attach","chain","cluster","compare","merge",
              "regress","segment","split","stretch","warp")

def assign_lines(fixation_XY, line_Y, *, word_XY=None, method="attach") -> np.ndarray
    # returns int (n,) array of line indices into line_Y (0..m-1)
```
Port each algorithm verbatim-with-attribution from `jwcarr/drift` (`algorithms.py`). Shapes: `fixation_XY` (n×2 float), `line_Y` (m,) sorted ascending, `word_XY` (k×2 in reading order; required by `warp`/`compare`). Algorithm notes:
- **attach, segment, chain, merge** — pure NumPy. attach = nearest line by |y−line_Y|; chain = split into runs at large Δx/|Δy|, snap run to nearest line; segment = cut at the m−1 largest return-sweeps (negative Δx), assign segments top→bottom; merge = progressive 3-phase sequence merge (paper-default thresholds).
- **warp, compare** — pure-NumPy dynamic programming using `word_XY` (DTW of fixations↔word centers; compare picks the best-matching line via windowed DTW). Paper-default params.
- **cluster, split** — `scipy.cluster.vq.kmeans2` (cluster: k=m on fixation y, order centers→lines; split: k=2 on saccade Δx to detect return-sweeps, then attach segments).
- **regress, stretch** — `scipy.optimize.minimize` (regress: fit m parallel lines (slope/offset/std) maximizing likelihood, bounds from paper; stretch: fit y scaling+offset minimizing distance to nearest line, then attach).

**Deriving inputs from a words frame** (reuse existing helpers, single-trial frames):
- `line_Y` ← group word y-centers by `measures.cluster_word_lines(words)` (measures.py:257), mean per line — mirrors `measures.assign_fixation_lines` (measures.py:337-345).
- `word_XY` (reading order) ← replicate `model_scanpaths._ordered_word_rows` convention (model_scanpaths.py:118): sort by `word_id` when present+complete else (cluster-line, x); center = (x+width/2, y+height/2). Drop NaN-geometry rows first (cf. model_scanpaths finite_geom guard).

**DataFrame wrapper** (what the UI calls):
```python
def correct(fixations, words, method, *, snap=True) -> tuple[pd.DataFrame, pd.Series]
```
Returns `(corrected_fixations, assigned_line)`: a copy of `fixations` with `y` snapped to `line_Y[assigned]` when `snap=True`, and a float Series (0-based line, NaN where unmappable) **index-aligned to `fixations`** — same shape/semantics as `measures.assign_fixation_lines`, so plots' `color_by_line` path consumes it unchanged. Passthrough (no change) when `len(line_Y) < 2`, words empty, or fixations empty. NaN-coord fixations → dropped from algorithm input via an index map, assigned NaN. Handles RTL/MultiplEYE via the same reading-order logic (word_id-driven when available).

## 2. `plots.py` — connector overlay (minimal)

Corrected panels feed already-snapped fixations + `color_by_line=True`, which already renders discrete "Line N" categories (plots.py:989, `_resolve_marker_colors` plots.py:387) — **no new color path**. Add two kwargs to `make_scanpath_figure` (after `fit_to_monitor`, ~plots.py:719): `show_connectors: bool=False`, `connector_y: Optional[Sequence[float]]=None`. When active + spatial axes, add ONE faint grey `go.Scatter(mode="lines", opacity~0.3, hoverinfo="skip", showlegend=False)` built like `_saccade_segments` (plots.py:425) but each segment = `(x, connector_y[i])`→`(x, fix_y[i])`; draw before the fixation markers. Keep it a Scatter (scales with the true-scale embed; not `layout.shapes`).

## 3. `controls.py` — in-place control

- **Default** (`_VIZ_WIDGET_DEFAULTS`, controls.py:33): `"global_align_algorithm": "Off"`, `"global_align_connectors": False`. `_seed_viz_state` (controls.py:702) already `setdefault`s the whole dict — no extra seeding.
- **Render** inside the Fixations popover (controls.py:968, after "Color fixations by", controls.py:972): a `selectbox` keyed `global_align_algorithm`, options `["Off", *(a.title() for a in alignment.ALGORITHMS)]`, help "snap fixations to their assigned text line"; when ≠ "Off", a `checkbox` keyed `global_align_connectors` ("Show drift connectors").
- **Collect** in `_collect_viz_settings` `return dict(...)` (controls.py:821): add `align_algorithm=ss.get("global_align_algorithm") or "Off"`, `align_connectors=bool(ss.get("global_align_connectors")) and align_algorithm != "Off"`. `viz_settings_from_state` (controls.py:871) reuses `_collect_viz_settings`, so the non-rendering twin stays in sync automatically.

## 4. `tabs.py` — apply in-place + new comparison subtab

**In-place apply** — in the single-figure `else` branch (around the `_cached_scanpath_figure` call, tabs.py:2067): when `viz_settings["align_algorithm"] != "Off"` and `trial_fixations` non-empty, compute `corrected, _ = alignment.correct(trial_fixations, trial_words, method=algo.lower())`; build the figure from `corrected` (not `trial_fixations`) with `build_kwargs` extended by `color_by_line=True`, and if `align_connectors`: `show_connectors=True, connector_y=tuple(trial_fixations["y"])` (a tuple stays hashable in `_figure_input_key`, tabs.py:478; the corrected frame's snapped y already busts the cache). Add `align_algorithm`/`align_connectors` into `build_kwargs` so the key varies. Import `from . import alignment` at the tabs.py import block (~line 63). Animation/Compare branches stay uncorrected (mirrors how `color_by_line` is honored only on the static plot).

**Comparison-grid subtab** — new `render_alignment_comparison_tab(trial_words, trial_fixations, *, canvas_width, canvas_height, base_font_size, font_family, line_spacing, scale_text_to_boxes, selected_participant, selected_trial)`. Reuse the grid pattern from `render_multiple_comparison_tab` (tabs.py:2643, loop 2850-2864) and its per-panel `_make_fig` override (tabs.py:2800-2816, `color_by_line=True`, labels/order/heatmap off):
- Top controls: `n_cols` slider (2-4, default 3) + "Show drift connectors" checkbox.
- Panels = **"Original (uncorrected)"** + 10 algorithms (11 total). Single-line guard (`len(line_Y)<2`) → `st.info(...)` + original only.
- Each panel: `corrected, line = alignment.correct(...)`; caption = `**{Algorithm}** · {n_lines_used} lines · {n_moved} moved` where `n_moved` = fixations whose assigned line differs from the naive `measures.assign_fixation_lines` baseline. Render via `_render_true_scale_chart(fig, key=f"align_{name}", max_height=cell_h)` — never `st.plotly_chart`.
- Wire in: extend the subtab `st.tabs([...])` (tabs.py:2079) with `"📐 Line assignment"`, unpack `tab_align`, add a `with tab_align:` body calling the renderer (all frames/ids already in scope in `render_single_trial_tab`).

## 5. Dependencies (sync BOTH)

- `pyproject.toml` `dependencies` (line ~27): `"scipy>=1.16"` (verify newest minor at implement time).
- `requirements.txt`: `scipy~=1.16.0` + one-line comment. Install before tests (`pip install scipy`).

## 6. Tests

- **`tests/test_alignment.py`** (new) — drives the synthetic 2-line trial (centers 110/210; `synthetic.EXPECTED["fixation_line"]=[0,0,0,0,0,1,1,1,1]`, `word_line=[0,0,0,1,1,1]`). For each of the 10 algorithms: assert `correct(...)` snaps in-text fixation y ∈ {110,210} and the assignment matches the 2-line structure (per-method tolerance for regress/stretch on only 9 fixations). Core-shape tests (`assign_lines` → int ndarray len n, values in [0,m)). Edge cases: single-line passthrough, empty fixations, NaN coords, `snap=False`, warp/compare with reading-order `word_XY`.
- **`tests/test_apptest.py`** (extend) — synthetic-source smoke that the "📐 Line assignment" subtab builds; set `global_align_algorithm="Attach"` and assert the corrected main figure builds and `_collect_viz_settings` reflects it.
- **`tests/test_plots.py`** (optional) — `show_connectors=True` adds exactly one extra Scatter trace.

## 7. Docs / changelog

- `CHANGELOG.md` — concise grouped bullets (Added: 10 drift-correction algorithms + comparison grid + in-place correction; Dependencies: scipy).
- `scanpath_studio/CLAUDE.md` — new `alignment.py` bullet + notes in the plots/controls/tabs bullets.
- `NOTICE` (new) / README acknowledgements — CC BY 4.0 attribution to Carr et al. (2021).
- `AGENTS.md` / `docs/` — one-liner if they enumerate features (verify first).

## 8. Verification

`pip install scipy` → `.venv/bin/python -m pytest tests/test_alignment.py -q` → `tests/test_apptest.py tests/test_plots.py -q` → full `.venv/bin/python -m pytest -q`. Optional live check on a NON-default port (default port may belong to another session): `.venv/bin/streamlit run streamlit_app.py --server.port 8765 --server.headless true`, load "Synthetic test trial", open "📐 Line assignment", and toggle the in-place dropdown + connectors. Per user prefs: don't over-verify live — AppTest is the reliable headless harness.

## Critical files
- `scanpath_studio/alignment.py` — NEW: 10 ported algorithms + `assign_lines` core + `correct()` wrapper (+ NOTICE).
- `scanpath_studio/plots.py` — connector overlay kwargs in `make_scanpath_figure` (~669/719).
- `scanpath_studio/controls.py` — align widget default (33), render (968), collect (821).
- `scanpath_studio/tabs.py` — in-place apply (2067), new subtab (2079), grid renderer (reuse 2643/2800/2850).
- `tests/test_alignment.py` — NEW: correctness on the synthetic 2-line ground truth.
- `pyproject.toml` + `requirements.txt` — add scipy.
- `CHANGELOG.md`, `scanpath_studio/CLAUDE.md`, `NOTICE` — docs/attribution.
