"""Conversions for display geometry and stimulus typography (DATA-2)."""

from __future__ import annotations

import math


def dpi_from_width(width_px: float, width_mm: float) -> float:
    """Horizontal display DPI from pixel and physical widths."""
    if width_px <= 0 or width_mm <= 0:
        raise ValueError("display widths must be positive")
    return float(width_px) / (float(width_mm) / 25.4)


def font_pt_to_px(font_pt: float, dpi: float) -> float:
    """CSS/monitor pixels corresponding to a point size at ``dpi``."""
    if font_pt <= 0 or dpi <= 0:
        raise ValueError("font size and DPI must be positive")
    return float(font_pt) * float(dpi) / 72.0


def pixels_per_degree(
    viewing_distance_mm: float, width_px: float, width_mm: float
) -> float:
    """Pixels subtending one visual degree at the configured setup."""
    if viewing_distance_mm <= 0:
        raise ValueError("viewing distance must be positive")
    px_per_mm = float(width_px) / float(width_mm)
    mm_per_degree = 2.0 * float(viewing_distance_mm) * math.tan(math.radians(0.5))
    return px_per_mm * mm_per_degree
