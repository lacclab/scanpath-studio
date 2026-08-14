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


def _spec(
    width_px,
    height_px,
    font_px,
    *,
    source,
    mono=True,
    chars_per_deg=None,
    double_spaced=False,
    distance_cm=None,
    width_cm=None,
    margin_px=100,
) -> DisplaySpec:
    """Build a DisplaySpec from what a corpus actually reported.

    ``chars_per_deg`` + ``distance_cm`` + ``width_cm`` gives a measured
    character width; otherwise fall back to the monospace advance ratio.
    """
    if chars_per_deg and distance_cm and width_cm:
        px_per_cm = width_px / width_cm
        cm_per_deg = 2 * distance_cm * 0.00872686779  # tan(0.5 deg)
        char_width = (cm_per_deg * px_per_cm) / chars_per_deg
    else:
        char_width = font_px * 0.6
    return DisplaySpec(
        width_px=width_px,
        height_px=height_px,
        font_px=font_px,
        char_width_px=char_width,
        line_pitch_px=font_px * (2.0 if double_spaced else 1.5),
        monospaced=mono,
        margin_px=margin_px,
        source=source,
    )


# Published display parameters, best source first: pymovements dataset YAMLs ->
# the UZH dataset review table -> the corpus' own paper. Anything not listed
# here falls back to DEFAULT_SPEC and is stamped `synthesized`.
DISPLAY_SPECS: dict[str, DisplaySpec] = {
    "potec": _spec(
        1680, 1050, 20, source="pymovements:potec", width_cm=47.5, distance_cm=65
    ),
    "copco": _spec(
        1920,
        1080,
        14,
        source="pymovements:copco + paper:Hollenstein2022",
        double_spaced=True,
        width_cm=59.0,
        distance_cm=85,
    ),
    "emtec": _spec(
        1280,
        1024,
        14,
        source="pymovements:emtec + uzh",
        chars_per_deg=2.86,
        width_cm=38.2,
        distance_cm=60,
    ),
    "colagaze": _spec(
        1280,
        1024,
        17,
        source="pymovements:colagaze + uzh",
        chars_per_deg=2.0,
        width_cm=54.37,
        distance_cm=60,
    ),
    "interead": _spec(
        1920,
        1080,
        16,
        source="pymovements:interead + uzh",
        width_cm=52.8,
        distance_cm=57,
    ),
    "ggtg": _spec(
        1100,
        900,
        20,
        source="pymovements:ggtg + uzh",
        mono=False,
        double_spaced=True,
        width_cm=31.2,
        distance_cm=66,
    ),
    "etdd70": _spec(
        1680,
        1050,
        20,
        source="pymovements:etdd70 + uzh",
        mono=False,
        distance_cm=65,
    ),
    "gaze4hate": _spec(
        2560,
        1440,
        20,
        source="pymovements:gaze4hate",
        width_cm=59.8,
        distance_cm=78.0,
    ),
    "raccoons": _spec(
        1920,
        1080,
        20,
        source="pymovements:raccoons",
        width_cm=56.8,
        distance_cm=105.5,
    ),
    "sbsat": _spec(
        1024,
        768,
        20,
        source="pymovements:sb_sat",
        width_cm=44.5,
        distance_cm=70,
    ),
    "provo": _spec(
        1600,
        900,
        20,
        source="paper:LukeChristianson2018",
        chars_per_deg=3.0,
        width_cm=40.0,
        distance_cm=60,
    ),
    "psr": _spec(
        1024,
        768,
        18,
        source="uzh",
        chars_per_deg=2.38,
        distance_cm=73,
        width_cm=47.0,
    ),
    "eyevoicespan": _spec(
        1280,
        960,
        24,
        source="uzh",
        chars_per_deg=2.22,
        distance_cm=60,
        width_cm=40.0,
    ),
    "iitbhgc": _spec(
        1920,
        1080,
        20,
        source="uzh",
        mono=False,
        distance_cm=70,
    ),
    "bsc": _spec(
        1024,
        768,
        20,
        source="uzh",
        chars_per_deg=0.75,
        distance_cm=43,
        width_cm=36.0,
    ),
    "chinesereading": _spec(1024, 768, 20, source="uzh", distance_cm=58),
    "cuentos": _spec(1920, 1080, 24, source="uzh", distance_cm=55),
    "zuco1": _spec(1920, 1080, 20, source="paper:Hollenstein2018", mono=False),
    "zuco2": _spec(1920, 1080, 20, source="paper:Hollenstein2020", mono=False),
    "mecol2w2": _spec(1920, 1080, 21, source="uzh + paper:MECO-L2-W2"),
}


def display_spec_for(dataset: str) -> DisplaySpec:
    """The published screen for ``dataset``, or ``DEFAULT_SPEC`` if none is known."""
    return DISPLAY_SPECS.get(str(dataset).lower(), DEFAULT_SPEC)
