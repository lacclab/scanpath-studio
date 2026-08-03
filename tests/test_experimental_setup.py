from __future__ import annotations

import pytest

from scanpath_studio.experimental_setup import (
    font_pt_to_px,
    pixels_per_degree,
)


def test_font_points_convert_through_display_dpi():
    assert font_pt_to_px(12, 96) == pytest.approx(16)
    assert font_pt_to_px(12, 144) == pytest.approx(24)


def test_pixels_per_degree_uses_physical_geometry():
    value = pixels_per_degree(
        viewing_distance_mm=600,
        width_px=1920,
        width_mm=531,
    )
    assert value == pytest.approx(37.93, rel=0.01)
