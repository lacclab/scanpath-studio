"""Runtime measurements for the manuscript (Section: Performance and robustness).

Measures, per input format (CSV / TSV / Parquet / Feather):
  load+normalize of the bundled OneStop demo (words + fixations), and
  build+save of one trial's interactive-HTML scanpath figure.
Plus: the animated-replay build + HTML export, and a "large trial" case from
PoTeC (one reader x one long textbook text, loaded from a local clone).

Times are the median of REPEATS runs on whatever machine this executes on;
record the machine spec alongside the numbers.

Run from the app repo:  cd app && uv run python paper/paper_timings.py
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

import pandas as pd

import scanpath_studio as sps
from scanpath_studio import data as _data

REPEATS = 3
POTEC_ROOT = Path("data/PoTeC")  # relative to the app repo


def timed(fn):
    runs = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        out = fn()
        runs.append(time.perf_counter() - t0)
    return statistics.median(runs), out


def main() -> None:
    sample_dir = Path(_data.__file__).parent / "sample_data"
    tmp = Path(tempfile.mkdtemp(prefix="sps_timings_"))

    # Materialize the bundled demo in all four formats.
    ia = pd.read_csv(sample_dir / "ia.csv", low_memory=False)
    fx = pd.read_csv(sample_dir / "fixations.csv", low_memory=False)
    paths = {
        "CSV": (sample_dir / "ia.csv", sample_dir / "fixations.csv"),
        "Parquet": (sample_dir / "ia.parquet", sample_dir / "fixations.parquet"),
        "TSV": (tmp / "ia.tsv", tmp / "fixations.tsv"),
        "Feather": (tmp / "ia.feather", tmp / "fixations.feather"),
    }
    ia.to_csv(paths["TSV"][0], sep="\t", index=False)
    fx.to_csv(paths["TSV"][1], sep="\t", index=False)
    ia.to_feather(paths["Feather"][0])
    fx.to_feather(paths["Feather"][1])

    print(f"== Bundled OneStop demo ({len(ia)} word rows, {len(fx)} fixation rows) ==")
    print(f"median of {REPEATS} runs")
    for fmt, (wp, fp) in paths.items():
        t_load, (words, fixations) = timed(
            lambda: sps.load_scanpath_data(str(wp), str(fp))
        )
        combos = sps.list_trials(words, fixations)
        pid, tid = combos.iloc[0]["participant_id"], combos.iloc[0]["trial_id"]

        def render():
            fig = sps.plot_scanpath(words, fixations, pid, tid)
            sps.save_figure(fig, str(tmp / f"fig_{fmt}.html"))
            return fig

        t_render, _ = timed(render)
        n_fix = len(
            fixations[(fixations.participant_id == pid) & (fixations.trial_id == tid)]
        )
        print(
            f"{fmt:8s} load+normalize {t_load:6.2f} s   figure+save-HTML {t_render:5.2f} s"
            f"   (trial: {n_fix} fixations)"
        )

    def animate():
        fig = sps.animate_scanpath(words, fixations, pid, tid)
        sps.save_figure(fig, str(tmp / "replay.html"))

    t_anim, _ = timed(animate)
    print(f"\nanimated replay build + save-HTML: {t_anim:.2f} s (same trial)")

    if POTEC_ROOT.exists():
        t_potec_load, (pw, pf) = timed(
            lambda: sps.load_potec(POTEC_ROOT, readers=[0], texts=["b0"])
        )
        combos = sps.list_trials(pw, pf)
        pid, tid = combos.iloc[0]["participant_id"], combos.iloc[0]["trial_id"]
        n_fix = len(pf[(pf.participant_id == pid) & (pf.trial_id == tid)])

        def render_potec():
            fig = sps.plot_scanpath(pw, pf, pid, tid, canvas_size=(1680, 1050))
            sps.save_figure(fig, str(tmp / "potec.html"))

        t_potec_render, _ = timed(render_potec)
        print(f"\n== PoTeC large trial (reader 0, text b0: {n_fix} fixations) ==")
        print(
            f"load+normalize {t_potec_load:.2f} s   figure+save-HTML {t_potec_render:.2f} s"
        )
    else:
        print(f"\n(PoTeC skipped: {POTEC_ROOT} not found)")

    print(f"\nscratch dir: {tmp}")


if __name__ == "__main__":
    main()
