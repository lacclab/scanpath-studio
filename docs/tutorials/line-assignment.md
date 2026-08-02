# Tutorial 5 — Correct vertical drift (line assignment)

**Goal:** decide, for one trial, which text line each fixation belongs to — and
see how much that decision depends on the algorithm you pick.

**You need:** the bundled demo. No browser needed: everything here renders to
HTML or prints numbers.

---

## 1. What the correction does

Vertical drift is the slow downward (or upward) creep of recorded gaze over a
long trial, until fixations sit between lines or on the wrong one. The fix is
**line assignment**: give each fixation the index of the text line it most
likely belongs to, then snap its `y` onto that line's centre.

Scanpath Studio ships a native port of the ten algorithms surveyed by
[Carr et al. (2021)](https://doi.org/10.3758/s13428-021-01554-0) — `attach`,
`chain`, `cluster`, `compare`, `merge`, `regress`, `segment`, `split`,
`stretch`, `warp`.

What it does **not** do:

- It never changes `x`.
- It never writes to your data. The correction is applied to the figure you're
  looking at; your loaded tables keep their recorded coordinates.
- It is not the **Snap fixations above words** control, which sits nearby under
  Fixations. That one redraws every fixation at the top-centre of the word it
  landed on — a schematic layout (the fixation half of the linear-reading mode,
  whose partner is *Saccade style → Line shape → Arc*), not a correction.

---

## 2. Compare the ten before picking one

The algorithms are heuristics, and they disagree most exactly where the data is
worst. Look at all of them on *your* trial before committing to one.

=== "In the app"

    Open the **📐 Line assignment** subtab (below the plot) and turn on **Show
    comparison grid**. You get eleven panels — the uncorrected original plus one
    per algorithm — each snapping fixations to their assigned line and colouring
    by line.

    - **Panels per row** (2–4) controls the grid width.
    - **Show drift connectors** draws a faint line from each fixation's original
      position to its corrected one, so the size of every shift stays visible.
    - Each panel's caption reads `<algorithm> · N lines · M moved` — *M* is how
      many fixations that algorithm assigns differently from the naive
      nearest-line baseline the plot's "colour by line" uses.

    The grid is off by default because building eleven true-scale figures is
    slow; the toggle persists, so it stays on while you browse trials.

=== "Python"

    `alignment.correct` returns the corrected fixations *and* the per-fixation
    line assignment, so the same comparison is a table:

    ```python
    import pandas as pd
    import scanpath_studio as sps
    from scanpath_studio import alignment
    from scanpath_studio.measures import assign_fixation_lines
    from scanpath_studio.utils import extract_trial

    words, fixations = sps.load_sample_data()
    combos = sps.list_trials(words, fixations)
    pid, tid = combos.iloc[0][["participant_id", "trial_id"]]

    trial_words = extract_trial(words, pid, tid)
    trial_fix = extract_trial(fixations, pid, tid)
    baseline = assign_fixation_lines(trial_fix, trial_words)   # nearest line

    rows = []
    for method in alignment.ALGORITHMS:
        corrected, line = alignment.correct(trial_fix, trial_words, method=method)
        rows.append({
            "algorithm": method,
            "lines_used": int(line.dropna().nunique()),
            "moved": int((line.fillna(-1) != baseline.fillna(-1)).sum()),
            "max_shift_px": float((corrected["y"] - trial_fix["y"]).abs().max()),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    ```

    On `l37_1129_2_1_1_Ele_r0` (154 fixations over 8 lines):

    ```text
    algorithm  lines_used  moved  max_shift_px
       attach           8      0          57.0
        chain           8      0          57.0
      cluster           8     27         154.5
      compare           6     59         228.0
        merge           8      6         128.5
      regress           8      1          57.0
      segment           8     67         369.5
        split           7     27         217.0
      stretch           8      2          74.0
         warp           8     29         369.5
    ```

=== "CLI"

    There is no grid on the command line, but one figure per algorithm is a
    three-line loop — HTML, so no Chrome needed:

    ```bash
    for algo in attach chain cluster compare merge regress segment split stretch warp; do
        scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
            --drift-correction "$algo" --drift-connectors -o "aligned_$algo.html"
    done
    ```

!!! warning "`moved` is a disagreement count, not an error count"
    It says how far an algorithm departs from nearest-line, not how often it is
    right. A `0` (here: `attach`, `chain`) means *this trial has little drift to
    correct* — which is itself the useful answer. A large number means the
    algorithm is making strong claims; go look at the panel before you accept
    them.

---

## 3. Apply one

=== "In the app"

    In the control rail, **Fixations ⚙️ → Drift correction** picks one algorithm
    (or **Off**, the default) and applies it in place on the main plot. The
    fixations are coloured by their assigned line so a misassignment is visible
    rather than merely plausible.

    **Show drift connectors** appears once an algorithm is selected. It is a
    static-figure control, so it is greyed out (with the reason) while
    animating or comparing — a full-length "original position" layer drawn from
    frame zero would read as part of the replay's trail. The *algorithm* itself
    applies on all three render paths: static, animation and comparison, where
    both scanpaths are corrected.

=== "Python"

    ```python
    fig = sps.plot_scanpath(
        words, fixations, pid, tid,
        canvas_size=(2560, 1440),
        drift_correction="warp",      # any of alignment.ALGORITHMS
        drift_connectors=True,        # faint original → corrected line
    )
    sps.save_figure(fig, "aligned.html")
    ```

    For the assignment as data rather than as a picture, use
    `alignment.correct(...)` (§2) — it returns a float Series of 0-based line
    indices aligned to the fixation frame, `NaN` where a fixation could not be
    mapped. `alignment.assign_lines` is the array-level core underneath it if
    you are working outside pandas.

=== "CLI"

    ```bash
    scanpath-studio render --sample --drift-correction warp --drift-connectors \
        -o fixed.html
    ```

    Static figures only: with `--animate` the two flags are ignored and the CLI
    says so. Full flag list in the [CLI reference](../cli.md).

---

## 4. What the correction reaches

This is the part worth being precise about:

| Surface | Honours drift correction |
| --- | --- |
| The on-screen figure (static, animation, comparison) | **Yes** |
| **Export → This trial** (it saves the figure on screen) | **Yes** |
| **Export → Multiple trials** — the *figures* | **Yes** — each trial is corrected with the same algorithm before its figure is rebuilt (coloured by line, like the on-screen figure), and `plot_config.json` records which one (`coloring.drift_correction`) |
| `plot_scanpath(..., drift_correction=…)` / `render --drift-correction` | **Yes** |
| Reading measures (`compute_word_metrics`) and the exported *tables* (fixations, measures, mega-table — bulk export included) | **No** — computed from the recorded coordinates |

So a corrected figure and an exported measures table can disagree, by design:
the correction is a *view* on the data, not a preprocessing step that rewrites
it. If you want measures computed from corrected coordinates, do the correction
yourself and pass the result on:

```python
corrected, _ = alignment.correct(trial_fix, trial_words, method="warp")
measures = sps.compute_word_metrics(trial_words, corrected)
```

---

## 5. Choosing, and saying what you chose

- **Start with the grid, not with a default.** Which algorithm wins depends on
  the stimulus layout (line spacing, number of lines) and on how bad the drift
  is. Carr et al. report no universal winner.
- **`warp` and `compare` use the word positions**, not just line centres, so
  they are the ones most sensitive to a wrong monitor resolution — set the
  recording resolution before judging them
  ([true-to-scale rendering](../rendering.md)).
- **Report the algorithm by name** in the paper, alongside how many fixations it
  reassigned. "Drift-corrected" on its own is not reproducible.
- **Cite the source.** If you use these algorithms, cite
  [Carr et al. (2021)](https://doi.org/10.3758/s13428-021-01554-0); the
  reference implementation is [jwcarr/drift](https://github.com/jwcarr/drift)
  (CC BY 4.0). See the [FAQ → Citing](../faq.md#citing).

---

## Next

- Export a corrected figure properly →
  **[Produce a figure for a paper](figure-for-a-paper.md)**
- Do it for a whole corpus → **[Export a batch](batch-export.md)**
- Why the text is that size → **[True-to-scale rendering](../rendering.md)**
