"""Redraw the architecture diagram (fig1_architecture.pdf) for the manuscript.

Same layout as the original hand-drawn figure, updated for the current app:
the front end is described as three views (not tabs) and the pipeline's last
stage now includes corpus-level aggregation.

Run from the app repo:  cd app && uv run python paper/paper_fig_architecture.py
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


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


OUT = _figures_dir() / "fig1_architecture.pdf"

BLUE_EDGE, BLUE_FILL = "#2f6db3", "#eaf1fa"
ORANGE_EDGE, ORANGE_FILL = "#e08a2e", "#fdf3e3"
GRAY = "#707070"


def box(ax, cx, cy, w, h, text, edge, fill, fs=11):
    ax.add_patch(
        FancyBboxPatch(
            (cx - w / 2, cy - h / 2),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            linewidth=1.6,
            edgecolor=edge,
            facecolor=fill,
        )
    )
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color="#1a1a1a")


def arrow(ax, xy_from, xy_to):
    ax.add_patch(
        FancyArrowPatch(
            xy_from,
            xy_to,
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=1.6,
            color=GRAY,
            shrinkA=2,
            shrinkB=2,
        )
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    row_y, h = 2.1, 0.82
    stages = [
        (1.02, 1.72, "Data\nsources\n(CSV/TSV/\nParquet/Feather)"),
        (2.72, 1.45, "Schema\ninference"),
        (4.45, 1.72, "Normalization\n(canonical\ncolumns)"),
        (6.12, 1.30, "Trial\nfiltering"),
        (8.30, 2.55, "Renderers / Measures /\nAggregation / Export"),
    ]
    for cx, w, label in stages:
        box(
            ax,
            cx,
            row_y,
            w,
            h + (0.28 if "\n" in label and label.count("\n") > 1 else 0),
            label,
            BLUE_EDGE,
            BLUE_FILL,
            fs=10.5,
        )
    for (cx1, w1, _), (cx2, w2, _) in itertools.pairwise(stages):
        arrow(ax, (cx1 + w1 / 2, row_y), (cx2 - w2 / 2, row_y))

    app_y, cli_y = 3.55, 0.62
    box(
        ax,
        3.6,
        app_y,
        3.5,
        0.62,
        "Streamlit interactive app  (three views)",
        ORANGE_EDGE,
        ORANGE_FILL,
    )
    box(
        ax,
        3.6,
        cli_y,
        3.3,
        0.62,
        "Headless Python API  +  CLI",
        ORANGE_EDGE,
        ORANGE_FILL,
    )
    arrow(ax, (3.6, app_y - 0.33), (3.6, row_y + 0.62))
    arrow(ax, (3.6, row_y - 0.62), (3.6, cli_y + 0.33))

    ax.text(
        8.3,
        3.55,
        "same pipeline,\nidentical figures",
        fontsize=10.5,
        style="italic",
        color=GRAY,
        ha="center",
        va="center",
    )

    fig.savefig(OUT, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
