"""DATA-2 display-geometry conversions.

These three functions are small, but they are what turns the sidebar's monitor
setup into the numbers everything else quotes: the DPI behind point-specified
stimulus typography, and the pixels-per-degree behind saccade amplitudes and the
PRE-* visual-angle columns. A silent factor-of-25.4 or degrees/radians slip here
would show up as plausible-looking numbers in a paper, so the expected values are
computed by hand rather than from the implementation.
"""

from __future__ import annotations

import math

import pytest

from scanpath_studio.experimental_setup import (
    dpi_from_width,
    font_pt_to_px,
    pixels_per_degree,
)


def test_dpi_is_pixels_per_inch_of_physical_width():
    # 1920 px across 508 mm == exactly 20 inches → 96 DPI.
    assert dpi_from_width(1920, 508.0) == pytest.approx(96.0)


def test_font_pt_to_px_is_72_points_per_inch():
    # 12 pt at 96 DPI is the canonical 16 px.
    assert font_pt_to_px(12.0, 96.0) == pytest.approx(16.0)


def test_pixels_per_degree_uses_the_tangent_of_half_a_degree():
    # One degree subtends 2·d·tan(0.5°) mm at distance d; convert with px/mm.
    px_per_mm = 1920 / 508.0
    expected = px_per_mm * 2.0 * 800.0 * math.tan(math.radians(0.5))
    assert pixels_per_degree(800.0, 1920, 508.0) == pytest.approx(expected)
    # Sanity anchor: a typical reading setup is a few dozen px per degree.
    assert 30 < pixels_per_degree(800.0, 1920, 508.0) < 80


def test_a_further_screen_subtends_more_pixels_per_degree():
    near = pixels_per_degree(600.0, 1920, 508.0)
    far = pixels_per_degree(1200.0, 1920, 508.0)
    assert far == pytest.approx(2 * near)


@pytest.mark.parametrize(
    ("func", "args"),
    [
        (dpi_from_width, (0, 508.0)),
        (dpi_from_width, (1920, 0)),
        (dpi_from_width, (-1920, 508.0)),
        (font_pt_to_px, (0, 96.0)),
        (font_pt_to_px, (12.0, 0)),
        (pixels_per_degree, (0, 1920, 508.0)),
        (pixels_per_degree, (-800.0, 1920, 508.0)),
    ],
)
def test_nonsense_geometry_raises_instead_of_returning_infinity(func, args):
    """A zero here would otherwise divide to ``inf`` and poison every measure."""
    with pytest.raises(ValueError):
        func(*args)
