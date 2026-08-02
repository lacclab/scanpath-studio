"""Render the MultiplEYE case-study figure (fig_multipleye) for the manuscript.

One page of a Chinese MultiplEYE session (Zurich pilot release), with the
scanpath drawn over the authoritative stimulus-page image at its true on-screen
position on the 1920x1080 presentation monitor. Word boxes come from the
loader's aggregation of the corpus's character-level areas of interest.

NOTE: reproduction of the stimulus page in print is subject to the release's
license; confirm before submission.

Run from the app repo:  cd app && uv run python paper/paper_fig_multipleye.py
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

import scanpath_studio as sps
from scanpath_studio.api import save_figure

ROOT = Path("data/MultiplEYE_ZH_CH_Zurich_1_2025")


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


OUT = _figures_dir() / "fig_multipleye.png"
SESSION, TRIAL = "001_ZH_CH_1_ET1", "Lit_MagicMountain_6__page_04"


def main() -> None:
    words, fixations = sps.load_multipleye(ROOT, sessions=[SESSION])
    tw = words[(words.participant_id == SESSION) & (words.trial_id == TRIAL)]
    tf = fixations[
        (fixations.participant_id == SESSION) & (fixations.trial_id == TRIAL)
    ]
    img_path = tw["image_path"].dropna().iloc[0]
    origin = (float(tw["image_x"].iloc[0]), float(tw["image_y"].iloc[0]))
    size = Image.open(img_path).size
    print(f"{TRIAL}: {len(tf)} fixations, image {img_path} at {origin}, {size}")

    fig = sps.plot_scanpath(
        words,
        fixations,
        SESSION,
        TRIAL,
        canvas_size=(1920, 1080),
        background_image=str(img_path),
        background_image_size=size,
        background_image_origin=origin,
        show_words=True,  # AOI boxes from character-box aggregation
        show_word_labels=False,  # the page image is the authoritative text
        show_order=False,
        show_heatmap=False,
        color_by="duration_ms",
    )
    save_figure(fig, str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
