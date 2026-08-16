"""Detection policy for schematic/altered scanpath labels (VIZ-22)."""

from __future__ import annotations

from collections.abc import Sequence


def illustration_reasons(
    settings: dict,
    *,
    data_source: str | None = None,
    fix_index_range: Sequence[int] | None = None,
    full_fixation_range: Sequence[int] | None = None,
    synthetic: bool = False,
    raw_gaze_only: bool = False,
) -> list[str]:
    """Return visible, substantive transformations; ignore cosmetic styling."""
    reasons: list[str] = []
    if settings.get("fixation_snap_to_word"):
        reasons.append("fixations snapped to words")
    if settings.get("saccade_render_mode") == "Arc":
        reasons.append("schematic saccade arcs")
    algorithm = settings.get("align_algorithm", "Off")
    if algorithm and algorithm != "Off":
        reasons.append(f"drift correction: {algorithm}")
    flags = settings.get("fixation_flags") or {}
    if any((value or {}).get("mode") == "Discard" for value in flags.values()):
        reasons.append("flagged fixations hidden")
    if (
        fix_index_range is not None
        and full_fixation_range is not None
        and tuple(fix_index_range) != tuple(full_fixation_range)
    ):
        reasons.append("fixation subset")
    source_name = str(data_source or "").lower()
    if synthetic or "synthetic" in source_name or "author" in source_name:
        reasons.append("synthetic source")
    if raw_gaze_only:
        reasons.append("derived from raw gaze")
    return reasons


def resolve_label_reasons(mode: str, reasons: Sequence[str]) -> list[str]:
    """Apply the Auto / Show / Hide manual override contract."""
    if mode == "Hide":
        return []
    if mode == "Show" and not reasons:
        return ["manual label"]
    return list(reasons)
