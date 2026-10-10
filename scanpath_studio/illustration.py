"""Detection policy for schematic/altered scanpath labels (VIZ-22)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .constants import AUTHOR_CHOICE, SYNTHETIC_CHOICE

#: The reason recorded when *Show* labels a figure nothing was detected on; the
#: figure draws "Illustration" alone for it (#374).
MANUAL_LABEL_REASON = "manual label"


def illustration_reasons(
    settings: dict,
    *,
    data_source: str | None = None,
    fix_index_range: Sequence[int] | None = None,
    full_fixation_range: Sequence[int] | None = None,
    synthetic: bool = False,
    fixation_flags_b: dict | None = None,
    fix_index_range_b: Sequence[int] | None = None,
    full_fixation_range_b: Sequence[int] | None = None,
) -> list[str]:
    """Return visible, substantive transformations; ignore cosmetic styling.

    CMP-24: in Compare, scanpath B has filters of its own —
    ``fixation_flags_b`` and a window ``fix_index_range_b`` against B's
    ``full_fixation_range_b`` — and either one alters the figure as much as A's
    does, so it discloses the same way.

    VIZ-45: raw gaze is never a reason. The samples are drawn as recorded —
    nothing in the app derives fixations (or anything else) from them — so a
    figure of raw gaze alone is the least transformed figure there is, and the
    "derived from raw gaze" reason it used to carry named a derivation that
    never happened."""
    reasons: list[str] = []
    if settings.get("fixation_snap_to_line"):
        reasons.append("fixations snapped to lines")
    if settings.get("saccade_render_mode") == "Arc":
        reasons.append("schematic saccade arcs")
    algorithm = settings.get("align_algorithm", "Off")
    if algorithm and algorithm != "Off":
        reasons.append(f"drift correction: {algorithm}")
    flag_sets = [settings.get("fixation_flags") or {}, fixation_flags_b or {}]
    if any(
        (value or {}).get("mode") == "Discard"
        for flags in flag_sets
        for value in flags.values()
    ):
        reasons.append("flagged fixations hidden")
    windows = [
        (fix_index_range, full_fixation_range),
        (fix_index_range_b, full_fixation_range_b),
    ]
    if any(
        window is not None and full is not None and tuple(window) != tuple(full)
        for window, full in windows
    ):
        reasons.append("fixation subset")
    # #374: the app's own made-up sources only, never a user's dataset whose
    # name happens to contain "synthetic" or "author".
    if synthetic or data_source in (SYNTHETIC_CHOICE, AUTHOR_CHOICE):
        reasons.append("synthetic source")
    playback_speed = settings.get("playback_speed", 1.0)
    try:
        playback_speed = float(playback_speed)
    except (TypeError, ValueError):
        playback_speed = 1.0
    if not math.isclose(playback_speed, 1.0):
        reasons.append(f"playback speed ×{playback_speed:g}")
    return reasons


def resolve_label_reasons(mode: str, reasons: Sequence[str]) -> list[str]:
    """Apply the Auto / Show / Hide manual override contract."""
    if mode == "Hide":
        return []
    if mode == "Show" and not reasons:
        return [MANUAL_LABEL_REASON]
    return list(reasons)
