"""ENG-16: render the dual-reader README still + docs GIF from the real pipeline.

Run from the repo root: ``python assets/render_dual_scanpath.py``.

The previous assets were hand-made and didn't correspond to any real reading.
These build the actual figures the app draws — two readers of the same bundled
demo paragraph — so the README and the docs site show what the tool produces.
The GIF needs Kaleido + a system Chrome (``plotly_get_chrome -y``); the still
does not.
"""

from __future__ import annotations

import os
from typing import Tuple

import pandas as pd
from PIL import Image, ImageSequence

from scanpath_studio.animation_export import export_animation
from scanpath_studio.api import CANONICAL_FIGURE_DEFAULTS
from scanpath_studio.constants import HIGHLIGHTED_TEXT_COLOR, WORD_LABEL_COLOR
from scanpath_studio.data import (
    compute_canvas_size,
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)
from scanpath_studio.plots import (
    animation_autoplay_frame_duration,
    make_comparison_figure,
    make_scanpath_animation,
)

# Two readers of the same bundled-demo paragraph, ~150 fixations each.
A = ("l37_1129", "l37_1129_2_1_1_Ele_r0")
B = ("l7_1090", "l7_1090_2_1_1_Ele_r0")
LABEL_A = "Reader A · l37_1129"
LABEL_B = "Reader B · l7_1090"
STILL_OUT = "assets/demo_dual_scanpath.png"
GIF_OUT = "docs/assets/demo_dual_scanpath.gif"

# Boxes off: at README width the 212 AOI outlines are visual noise competing with
# the two scanpaths, which are the point of the picture.
SHARED = dict(
    show_words=False,
    show_legend=True,
    marker_size_range=(6, 20),
    background_color="#ffffff",
)


def load_pair() -> Tuple[pd.DataFrame, pd.DataFrame, Tuple[float, float]]:
    words_raw, fix_raw = load_sample_data()
    words = normalize_words(words_raw, infer_word_schema(words_raw))
    fixations = normalize_fixations(fix_raw, infer_fix_schema(fix_raw))
    trials = [A[1], B[1]]
    words_pair = words[words["trial_id"].isin(trials)]
    fix_pair = fixations[fixations["trial_id"].isin(trials)]
    canvas = compute_canvas_size(words_pair, fix_pair)
    print(f"canvas {canvas} · {len(fix_pair)} fixations · {len(words_pair)} words")
    return words_pair, fix_pair, canvas


def render_still(words_pair, fix_pair, canvas) -> None:
    defaults = CANONICAL_FIGURE_DEFAULTS
    fig = make_comparison_figure(
        words_pair,
        fix_pair,
        A,
        B,
        canvas_width=int(canvas[0]),
        canvas_height=int(canvas[1]),
        font_family=defaults.get("font_family", "monospace"),
        base_font_size=int(defaults.get("base_font_size", 14)),
        show_word_labels=True,
        trial_labels=(LABEL_A, LABEL_B),
        layout="overlay",
        show_saccades=True,
        style_a={"opacity": 0.85, "saccade_width": 1.2},
        style_b={"opacity": 0.85, "saccade_width": 1.2},
        text_color=WORD_LABEL_COLOR,
        highlight_text_color=HIGHLIGHTED_TEXT_COLOR,
        fit_to_monitor=False,
        **SHARED,
    )
    fig.write_image(
        STILL_OUT, width=fig.layout.width, height=fig.layout.height, scale=2
    )
    # 2x for crisp text on a HiDPI screen, then quantized: flat colour over white,
    # so a 256-entry palette is visually lossless and ~5x smaller — which is the
    # whole point of ENG-16 (the README shouldn't be megabytes).
    Image.open(STILL_OUT).convert("RGB").quantize(
        colors=256, method=Image.MEDIANCUT
    ).save(STILL_OUT, optimize=True)
    print(f"wrote {STILL_OUT} ({os.path.getsize(STILL_OUT) / 1_000:.0f} KB)")


def render_gif(words_pair, fix_pair, canvas) -> None:
    defaults = CANONICAL_FIGURE_DEFAULTS
    anim = make_scanpath_animation(
        words_pair[words_pair["trial_id"] == A[1]],
        fix_pair[fix_pair["trial_id"] == A[1]],
        canvas_width=int(canvas[0]),
        canvas_height=int(canvas[1]),
        base_font_size=int(defaults.get("base_font_size", 14)),
        font_family=defaults.get("font_family", "monospace"),
        fixations_b=fix_pair[fix_pair["trial_id"] == B[1]],
        label_a=LABEL_A,
        label_b=LABEL_B,
        show_order=False,
        playback_speed=4.0,
        **SHARED,
    )
    data = export_animation(
        anim,
        fmt="gif",
        frame_duration_ms=animation_autoplay_frame_duration(anim) or 80,
        scale=0.6,
        max_frames=60,
        progress_callback=lambda done, total: print(
            f"  frame {done}/{total}", end="\r"
        ),
    )
    with open(GIF_OUT, "wb") as handle:
        handle.write(data)
    _shrink_gif(GIF_OUT)


def _shrink_gif(path: str, colors: int = 64) -> None:
    """Re-encode with a smaller palette. Flat colour on white, so 64 entries are
    visually indistinguishable from 256 and roughly halve the file — a docs page
    shouldn't ship megabytes of animation either."""
    before = os.path.getsize(path)
    source = Image.open(path)
    frames = [
        frame.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT)
        for frame in ImageSequence.Iterator(source)
    ]
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=source.info.get("duration", 100),
        loop=0,
        optimize=True,
    )
    print(
        f"\nwrote {path} ({os.path.getsize(path) / 1_000_000:.2f} MB, "
        f"was {before / 1_000_000:.2f} MB)"
    )


if __name__ == "__main__":
    pair = load_pair()
    render_still(*pair)
    render_gif(*pair)
