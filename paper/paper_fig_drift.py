"""Render the drift-correction figure (fig_drift) for the manuscript.

One PoTeC trial with the `warp` line-assignment algorithm applied in place,
exactly as the app's Fixations -> Drift correction control does: each fixation
snaps to the vertical center of its assigned text line, fixations are colored
by assigned line, and grey connectors show the displacement from each original
position.

Run from the app repo:  cd app && uv run python paper/paper_fig_drift.py
"""

from __future__ import annotations

import os
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio import alignment, constants, plots
from scanpath_studio.api import save_figure

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


OUT = _figures_dir() / "fig_drift.png"
READER, TEXT, ALGORITHM = 0, "b0", "warp"


def main() -> None:
    words, fixations = sps.load_potec(POTEC_ROOT, readers=[READER], texts=[TEXT])
    combos = sps.list_trials(words, fixations)
    pid, tid = combos.iloc[0]["participant_id"], combos.iloc[0]["trial_id"]
    tw = words[(words.participant_id == pid) & (words.trial_id == tid)]
    tf = fixations[(fixations.participant_id == pid) & (fixations.trial_id == tid)]

    corrected, _line = alignment.correct(tf, tw, ALGORITHM, snap=True)
    fig = plots.make_scanpath_figure(
        tw,
        corrected,
        canvas_width=1680,
        canvas_height=1050,
        base_font_size=16,
        font_family=constants.FONT_FAMILY,
        x_field="x",
        y_field="y",
        show_words=False,
        show_word_labels=True,
        show_fixations=True,
        show_order=False,
        show_saccades=True,
        show_heatmap=False,
        color_by="duration_ms",
        heatmap_metric=None,
        marker_size_range=constants.DEFAULT_MARKER_SIZE_RANGE,
        order_font_size=16,
        order_font_color=constants.DEFAULT_ORDER_FONT_COLOR,
        show_colorbars=False,
        fixation_color_range=None,
        heatmap_range=None,
        color_by_line=True,
        show_connectors=True,
        connector_y=tf["y"].to_numpy(),
    )
    fig.update_layout(showlegend=False)  # line colors are self-explanatory in print
    save_figure(fig, str(OUT))
    print(f"wrote {OUT}  ({len(tf)} fixations, algorithm={ALGORITHM})")


if __name__ == "__main__":
    main()
