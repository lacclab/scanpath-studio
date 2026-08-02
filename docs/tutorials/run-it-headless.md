# Tutorial 4 — Run it headless from a script

**Goal:** get the app's output — figures, replays, reading measures — out of a
script instead of a browser, so a corpus can be re-rendered with one command
and a paper's figures are reproducible from source.

**You need:** the bundled demo works for everything here.

!!! tip "Static image export needs a browser"
    HTML, CSV and Parquet output is browser-free. **PNG / SVG / PDF** and
    **GIF / MP4** go through [Kaleido](https://github.com/plotly/Kaleido),
    which drives a headless Chrome — run `plotly_get_chrome -y` once.

---

## 1. The whole pipeline in ten lines

Everything the app draws is reachable through the package's public functions,
and they follow one pipeline:

```text
load_scanpath_data / load_sample_data   →   (words, fixations)
        list_trials             →  which (participant, trial) combos exist
        compute_word_metrics    →  per-word measures (FFD/FPRT/RPD/TFD …)
        plot_scanpath           →  a static Plotly figure
        animate_scanpath        →  an animated replay figure
        save_figure             →  .html / .png / .svg / .pdf on disk
        save_figure_layers      →  one file per layer
```

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()          # or load_scanpath_data(...)
combos = sps.list_trials(words, fixations)
pid, tid = combos.iloc[0][["participant_id", "trial_id"]]

fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
sps.save_figure(fig, "scanpath.html")

measures = sps.compute_word_metrics(words, fixations)
```

!!! note "The first call is the slow one"
    `import scanpath_studio` stays cheap — pandas / plotly / streamlit are
    pulled in lazily on the first API call, which pays a one-time import cost.

---

## 2. One command, no Python

For a single figure, the CLI is shorter than a script:

```bash
scanpath-studio render --sample --list-trials                 # what's available
scanpath-studio render --sample -o scanpath.html              # interactive HTML
scanpath-studio render --sample --animate -o replay.html      # animated replay
scanpath-studio render --words ia.csv --fixations fix.csv \
    -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o figure.png
```

`--words` / `--fixations` accept several paths or a quoted glob, so a corpus
split one-file-per-participant loads without a merge step. Full flag list:
[CLI reference](../cli.md).

---

## 3. Render a whole corpus

Save this as `render_corpus.py`:

```python
"""Render every trial in a corpus + dump the reading measures."""

from __future__ import annotations

import argparse
from pathlib import Path

import scanpath_studio as sps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words")
    parser.add_argument("--fixations")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("build"))
    parser.add_argument("--format", default="html")
    args = parser.parse_args()

    if args.sample:
        words, fixations = sps.load_sample_data()
    else:
        words, fixations = sps.load_scanpath_data(args.words, args.fixations)

    args.out.mkdir(parents=True, exist_ok=True)
    combos = sps.list_trials(words, fixations)
    print(f"{len(combos)} trials → {args.out}/")

    for i, row in enumerate(combos.itertuples(index=False), start=1):
        fig = sps.plot_scanpath(
            words, fixations, row.participant_id, row.trial_id,
            canvas_size=(2560, 1440), show_heatmap=False,
        )
        path = args.out / f"{row.participant_id}__{row.trial_id}.{args.format}"
        sps.save_figure(fig, path)
        print(f"  [{i}/{len(combos)}] {path.name}")

    measures = sps.compute_word_metrics(words, fixations)
    measures.to_parquet(args.out / "word_measures.parquet", index=False)
    print(f"{len(measures):,} word rows → {args.out}/word_measures.parquet")


if __name__ == "__main__":
    main()
```

```bash
python render_corpus.py --sample --out build
```

```text
24 trials → build/
  [1/24] l37_1129__l37_1129_2_1_1_Ele_r0.html
  ...
  [24/24] l7_1090__l7_1090_2_2_6_Ele_r0.html
3,922 word rows → build/word_measures.parquet
```

Two things to know before you point it at a real corpus:

- **Stick to `--format html` for a first pass.** Every PNG/SVG/PDF cold-starts a
  headless Chrome, so a few hundred trials take a while. (The app's bulk
  exporter keeps *one* warm Kaleido browser across trials; the loop above
  doesn't.)
- **`list_trials` is the intersection.** A trial present in only one of the two
  tables isn't in the list. On the bundled sample, the words table carries 3
  participants but only 2 have fixations — so it returns 24 trials, not 36.

---

## 4. The measures table is the deliverable

For most analyses the figures are a by-product and this is the thing you want:

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
measures = sps.compute_word_metrics(words, fixations)

by_reader = measures.groupby("participant_id").agg(
    n_trials=("trial_id", "nunique"),
    mean_ffd_ms=("first_fixation_ms", "mean"),
    mean_tfd_ms=("total_fixation_duration_ms", "mean"),
    skip_rate=("skip_flag", "mean"),
    regression_rate=("regression_in_flag", "mean"),
).round(3)
print(by_reader.to_string())
```

```text
                n_trials  mean_ffd_ms  mean_tfd_ms  skip_rate  regression_rate
participant_id
l25_1042              12      127.139      232.504      0.743            0.208
l37_1129              12      185.612      331.972      0.306            0.200
l7_1090               12       97.082      158.068      0.646            0.215
```

One row per (participant, trial, word), with `first_fixation_ms` (FFD),
`first_pass_gaze_duration_ms` (FPRT / gaze duration),
`regression_path_duration_ms` (RPD / go-past),
`total_fixation_duration_ms` (TFD / dwell), `n_fixations`, `skip_flag`,
`regression_in_flag` and `regression_out_flag` — plus whatever linguistic
features your data shipped:

```python
print(measures[["gpt2_surprisal", "total_fixation_duration_ms"]].corr().round(3))
```

```text
                            gpt2_surprisal  total_fixation_duration_ms
gpt2_surprisal                       1.000                       0.217
total_fixation_duration_ms           0.217                       1.000
```

!!! warning "Where the numbers come from"
    Pre-computed EyeLink `IA_*` columns on the words table **take precedence**
    over anything the app would compute — so on a normal EyeLink export the
    numbers are your eye-tracker's. That is also why `l25_1042` has measures
    above despite contributing no fixation rows: its dwell times came straight
    from the words table. When no such columns exist, the measures are computed
    natively from the fixations.

---

## 5. Replays

```python
anim = sps.animate_scanpath(words, fixations, pid, tid,
                            canvas_size=(2560, 1440), playback_speed=4.0)
sps.save_figure(anim, "replay.html")                  # autoplays on load

paused = sps.animate_scanpath(words, fixations, pid, tid, autoplay=False)
sps.save_figure(paused, "replay_paused.html")         # opens paused
```

For GIF / MP4 (Chrome required; ffmpeg is bundled):

```python
from scanpath_studio.animation_export import export_animation

export_animation(anim, "replay.mp4")     # or replay.gif
```

The CLI's `--animate` writes interactive HTML only.

---

## 6. Make it reproducible

Wire the script into whatever already builds your paper:

```makefile
build/word_measures.parquet: data/ia.csv data/fixations.csv render_corpus.py
	python render_corpus.py --words data/ia.csv --fixations data/fixations.csv --out build

figures/scanpath_main.pdf: data/ia.csv data/fixations.csv
	scanpath-studio render --words data/ia.csv --fixations data/fixations.csv \
	    -p P07 -t P07_item12 --no-heatmap --no-order \
	    --canvas 2560x1440 --font-size 18 -o $@
```

Three habits that pay off later:

- **Pin the version.** `scanpath-studio --version` in the log, and
  `scanpath-studio==X.Y.Z` in `requirements.txt`.
- **Pass `canvas_size` explicitly.** Without it the monitor size is *estimated
  from the data*, so a filtered subset can silently change your figure's scale.
- **Keep the schema in the script** if auto-detection needed help — a
  `word_schema` / `fix_schema` dict in source beats a mapping clicked in a
  wizard six months ago. (`💾 Save & restore` in the app exports the same
  mapping as JSON if you'd rather start from there.)

---

## 7. Other corpora, one call

Three public corpora load without any column mapping at all:

```python
import scanpath_studio as sps

# PoTeC — pass download=True to fetch it into `root` on first use (~45 MB).
words, fixations = sps.load_potec("data/PoTeC", download=True)

# Subset while loading, instead of filtering afterwards.
words, fixations = sps.load_potec("data/PoTeC", readers=[0, 1], texts=["b0"])
```

`load_multipleye(root, …)` and `load_onestop(root, …)` are the other two — all
three are importable straight from the package root and return the same
`(words, fixations)` pair as everything else on this page. See
[OneStop](../onestop.md), [MultiplEYE](../multipleye.md), and `--potec DIR` in
the [CLI reference](../cli.md).

---

## Next

- Figures *and* tables for many trials in one zip →
  **[Export a batch](batch-export.md)**
- Every function signature → **[Python API](../api.md)**
- Every `render` flag → **[CLI reference](../cli.md)**
- Working *with* a coding agent on this repo → **[For coding agents](../agents.md)**
- Chrome / ffmpeg problems → **[Export & troubleshooting](../export-troubleshooting.md)**
