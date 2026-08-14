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


IA_DATA_COLUMN = "CURRENT_FIX_INTEREST_AREA_DATA"
_BOX_COLUMNS = ["start_x", "start_y", "end_x", "end_y"]


def parse_ia_data(series: pd.Series) -> pd.DataFrame:
    """EyeLink ``[STATIC, RECTANGLE, left, top, right, bottom]`` -> box columns.

    This is the corpus' *real* on-screen word box. EyeGenBench reads it, divides
    it into a normalised landing position, and discards it; we keep it.
    """
    parts = series.astype(str).str.strip("[]").str.split(",", expand=True)
    if parts.shape[1] < 6:
        return pd.DataFrame(
            {c: [float("nan")] * len(series) for c in _BOX_COLUMNS}, index=series.index
        )
    out = pd.DataFrame(index=series.index)
    for name, idx in zip(_BOX_COLUMNS, (2, 3, 4, 5)):
        out[name] = pd.to_numeric(parts[idx].str.strip(), errors="coerce")
    return out


def extract_eyelink_boxes(
    frame: pd.DataFrame,
    *,
    paragraph_col: str = "unique_paragraph_id",
    ia_col: str = "ia_index",
    data_col: str = IA_DATA_COLUMN,
) -> pd.DataFrame:
    """One real box per ``(paragraph, interest area)`` found in ``frame``.

    Only interest areas that were *fixated* appear -- the column rides on
    fixations. `fill_missing_boxes` completes the rest.
    """
    if data_col not in frame.columns:
        return pd.DataFrame(columns=[paragraph_col, ia_col, *_BOX_COLUMNS])
    boxes = pd.concat(
        [
            frame[[paragraph_col, ia_col]].reset_index(drop=True),
            parse_ia_data(frame[data_col]).reset_index(drop=True),
        ],
        axis=1,
    )
    boxes = boxes.dropna(subset=_BOX_COLUMNS)
    boxes = boxes.drop_duplicates(subset=[paragraph_col, ia_col], keep="first")
    return boxes.sort_values([paragraph_col, ia_col]).reset_index(drop=True)


def fill_missing_boxes(
    boxes: pd.DataFrame, ia_counts: dict[str, int], spec: DisplaySpec
) -> tuple[pd.DataFrame, float]:
    """Complete ``boxes`` so every interest area of every paragraph has one.

    Real boxes only cover *fixated* areas. Consecutive gaps are filled as runs
    (maximal consecutive stretches of missing indices):

    - Bracketed on both sides, same line: divide the space evenly between them
    - Bracketed across a line break: continue rightward from L on L's line
    - Trailing (L exists, no R): advance rightward from L
    - Leading (no L, R exists): advance leftward from R, preserving order
    - No anchor (neither L nor R): distribute evenly across the screen

    Returns ``(filled, interpolated_fraction)`` so the manifest can report
    how much of the geometry is inferred rather than measured.
    """
    width = spec.char_width_px * 4
    out = []
    n_filled = 0
    n_total = 0

    for paragraph, count in ia_counts.items():
        present = boxes[boxes["unique_paragraph_id"] == paragraph]
        by_index = {int(r.ia_index): r for r in present.itertuples()}
        n_total += count

        # Process all indices, identifying runs of consecutive missing indices
        idx = 0
        while idx < count:
            if idx in by_index:
                # Real box: add it as-is
                row = by_index[idx]
                out.append(
                    {
                        "unique_paragraph_id": paragraph,
                        "ia_index": idx,
                        "start_x": row.start_x,
                        "start_y": row.start_y,
                        "end_x": row.end_x,
                        "end_y": row.end_y,
                    }
                )
                idx += 1
            else:
                # Start of a run of consecutive missing indices
                run_start = idx
                while idx < count and idx not in by_index:
                    idx += 1
                run_end = idx - 1
                k = run_end - run_start + 1

                # Find L (nearest real box before the run)
                L = None
                for i in range(run_start - 1, -1, -1):
                    if i in by_index:
                        L = by_index[i]
                        break

                # Find R (nearest real box after the run)
                R = None
                for i in range(run_end + 1, count):
                    if i in by_index:
                        R = by_index[i]
                        break

                # Fill the run based on anchor availability and line position
                if L is not None and R is not None:
                    if L.start_y == R.start_y:
                        # Bracketed on both sides, same line
                        span = R.start_x - L.end_x
                        if span > 0:
                            slot = span / k
                            for i in range(k):
                                out.append(
                                    {
                                        "unique_paragraph_id": paragraph,
                                        "ia_index": run_start + i,
                                        "start_x": L.end_x + i * slot,
                                        "start_y": L.start_y,
                                        "end_x": L.end_x + (i + 1) * slot,
                                        "end_y": L.end_y,
                                    }
                                )
                        else:
                            # Zero or negative span, use zero-width boxes at L.end_x
                            for i in range(k):
                                out.append(
                                    {
                                        "unique_paragraph_id": paragraph,
                                        "ia_index": run_start + i,
                                        "start_x": L.end_x,
                                        "start_y": L.start_y,
                                        "end_x": L.end_x,
                                        "end_y": L.end_y,
                                    }
                                )
                        n_filled += k
                    else:
                        # Bracketed but across line break, treat as trailing
                        for i in range(k):
                            out.append(
                                {
                                    "unique_paragraph_id": paragraph,
                                    "ia_index": run_start + i,
                                    "start_x": L.end_x
                                    + i * (width + spec.char_width_px)
                                    + spec.char_width_px,
                                    "start_y": L.start_y,
                                    "end_x": L.end_x
                                    + i * (width + spec.char_width_px)
                                    + spec.char_width_px
                                    + width,
                                    "end_y": L.end_y,
                                }
                            )
                        n_filled += k
                elif L is not None:
                    # Trailing run: advance rightward from L
                    for i in range(k):
                        out.append(
                            {
                                "unique_paragraph_id": paragraph,
                                "ia_index": run_start + i,
                                "start_x": L.end_x
                                + i * (width + spec.char_width_px)
                                + spec.char_width_px,
                                "start_y": L.start_y,
                                "end_x": L.end_x
                                + i * (width + spec.char_width_px)
                                + spec.char_width_px
                                + width,
                                "end_y": L.end_y,
                            }
                        )
                    n_filled += k
                elif R is not None:
                    # Leading run: divide space from margin_px to R using bracketed formula
                    available = R.start_x - spec.margin_px
                    if available > 0:
                        slot = available / k
                        for i in range(k):
                            out.append(
                                {
                                    "unique_paragraph_id": paragraph,
                                    "ia_index": run_start + i,
                                    "start_x": spec.margin_px + i * slot,
                                    "start_y": R.start_y,
                                    "end_x": spec.margin_px + (i + 1) * slot,
                                    "end_y": R.end_y,
                                }
                            )
                    else:
                        # No room before R, use zero-width boxes at margin_px
                        for i in range(k):
                            out.append(
                                {
                                    "unique_paragraph_id": paragraph,
                                    "ia_index": run_start + i,
                                    "start_x": spec.margin_px,
                                    "start_y": R.start_y,
                                    "end_x": spec.margin_px,
                                    "end_y": R.end_y,
                                }
                            )
                    n_filled += k
                else:
                    # No anchor: distribute evenly across usable screen width
                    usable_width = spec.width_px - 2 * spec.margin_px
                    slot = usable_width / k if k > 0 else 0
                    for i in range(k):
                        out.append(
                            {
                                "unique_paragraph_id": paragraph,
                                "ia_index": run_start + i,
                                "start_x": spec.margin_px + i * slot,
                                "start_y": spec.margin_px,
                                "end_x": spec.margin_px + (i + 1) * slot,
                                "end_y": spec.margin_px + spec.font_px,
                            }
                        )
                    n_filled += k

    fraction = (n_filled / n_total) if n_total else 0.0
    return pd.DataFrame(out), fraction
