"""Screen geometry for EyeGenBench corpora.

EyeGenBench's harmonised output records *which* interest area each fixation
landed on and *where within it* (a 0-1 offset), but no pixel coordinates and no
word boxes. Scanpath Studio needs boxes. This module recovers them at the best
fidelity available -- see `resolve_geometry` for the three tiers.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DisplaySpec:
    """How one corpus presented its text, in pixels.

    ``source`` cites where the numbers came from (e.g. ``"pymovements:potec"``),
    so a reconstructed layout can always be traced back to its evidence.
    """

    width_px: int
    height_px: int
    font_px: float
    char_width_px: float
    line_pitch_px: float
    monospaced: bool
    margin_px: int
    source: str


# Provisional -- DATA-27 open decision. A synthesized layout needs *some*
# screen; this is the one used when nothing at all is published for a corpus.
DEFAULT_SPEC = DisplaySpec(
    width_px=1920,
    height_px=1080,
    font_px=20,
    char_width_px=12.0,  # Courier-family advance width at 20px.
    line_pitch_px=60.0,  # Double-spaced, the reading-study norm.
    monospaced=True,
    margin_px=100,
    source="default",
)


def layout_words(ia_list: list[str], spec: DisplaySpec) -> pd.DataFrame:
    """Lay ``ia_list`` out as word boxes on ``spec``'s screen.

    Greedy left-to-right wrapping with one space between words. Shared by the
    reconstructed and synthesized tiers -- same code, different ``spec``.
    """
    if not len(ia_list):
        raise ValueError("layout_words needs at least one interest area")

    usable = spec.width_px - 2 * spec.margin_px
    space = spec.char_width_px
    rows = []
    x, line = spec.margin_px, 0
    for word_id, text in enumerate(ia_list):
        width = max(len(str(text)), 1) * spec.char_width_px
        if x > spec.margin_px and (x + width) > (spec.margin_px + usable):
            x, line = spec.margin_px, line + 1
        top = spec.margin_px + line * spec.line_pitch_px
        rows.append(
            {
                "word_id": word_id,
                "text": str(text),
                "line": line,
                "start_x": x,
                "end_x": x + width,
                "start_y": top,
                "end_y": top + spec.font_px,
            }
        )
        x += width + space
    return pd.DataFrame(rows)
