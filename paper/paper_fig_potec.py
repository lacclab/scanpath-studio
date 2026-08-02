"""Render the PoTeC case-study figure for the manuscript (fig_potec).

Loads one reader's reading of one PoTeC textbook text from a local PoTeC clone
(pass download=True on first use to fetch ~45 MB), computes the reading
measures from raw fixations, and renders the scanpath over the German text at
PoTeC's 1680x1050 presentation size.

Run from the app repo:  cd app && uv run python paper/paper_fig_potec.py
"""

from __future__ import annotations

import os
from pathlib import Path

import scanpath_studio as sps

POTEC_ROOT = Path("data/PoTeC")


def _figures_dir() -> Path:
    """Where rendered figures land.

    Defaults to ``paper/figures/`` inside the software repo so an archived
    release is self-contained; set ``PAPER_FIGURES_DIR`` to write straight into
    the manuscript tree (e.g. ``PAPER_FIGURES_DIR=../../overleaf/figures``).
    """
    env = os.environ.get("PAPER_FIGURES_DIR")
    out = Path(env) if env else Path(__file__).resolve().parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    return out


OUT = _figures_dir() / "fig_potec.png"
READER, TEXT = 0, "b0"


def main() -> None:
    words, fixations = sps.load_potec(POTEC_ROOT, readers=[READER], texts=[TEXT])
    combos = sps.list_trials(words, fixations)
    pid, tid = combos.iloc[0]["participant_id"], combos.iloc[0]["trial_id"]
    n_fix = len(
        fixations[(fixations.participant_id == pid) & (fixations.trial_id == tid)]
    )
    print(f"rendering participant={pid} trial={tid} ({n_fix} fixations)")
    # A ~400-fixation textbook reading: keep the core layers, drop the
    # per-fixation order labels and the heatmap that would clutter at this scale.
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=(1680, 1050),
        show_order=False,
        show_heatmap=False,
    )
    try:
        sps.save_figure(fig, str(OUT), scale=2)
    except TypeError:
        sps.save_figure(fig, str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
