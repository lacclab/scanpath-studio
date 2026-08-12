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
    Provenance,
    SetupSnapshot,
    dpi_from_width,
    font_pt_to_px,
    format_provenance_param,
    parse_provenance_param,
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


# -----------------------------------------------------------------------------
# DATA-22 / CMP-8 — the per-dataset SetupSnapshot and its provenance
# -----------------------------------------------------------------------------


class TestSetupSnapshot:
    """The snapshot is what stops an uploaded corpus silently inheriting a
    2560x1440 / 597 mm / 16 px guess. Its contract is: every value is resolved,
    and every value says how it is known."""

    def test_round_trips_through_a_dict(self):
        snapshot = SetupSnapshot(
            canvas_width=1680,
            canvas_height=1050,
            monitor_width_mm=474.0,
            viewing_distance_mm=650.0,
            base_font_size=21,
            font_family="serif",
            line_spacing=2.0,
            scale_text_to_boxes=False,
            screen_provenance=Provenance.MEASURED,
            geometry_provenance=Provenance.ESTIMATED,
            text_provenance=Provenance.ASSUMED,
        )
        assert SetupSnapshot.from_dict(snapshot.to_dict()) == snapshot

    def test_derived_values_match_the_bare_conversions(self):
        snapshot = SetupSnapshot(
            canvas_width=1920,
            monitor_width_mm=508.0,
            viewing_distance_mm=800.0,
            geometry_provenance=Provenance.MEASURED,
        )
        assert snapshot.dpi == pytest.approx(96.0)
        assert snapshot.px_per_degree == pytest.approx(
            pixels_per_degree(800.0, 1920, 508.0)
        )
        assert snapshot.stimulus_font_px(12.0) == pytest.approx(16.0)

    def test_a_skipped_geometry_hides_what_it_cannot_derive(self):
        """The whole point of SKIPPED: no number is better than an invented one.

        px/degree and pt→px both need the physical width. Under a skipped
        geometry group they must be unavailable, not computed from the default
        597 mm that happens to be sitting in the dataclass.
        """
        snapshot = SetupSnapshot(geometry_provenance=Provenance.SKIPPED)
        assert snapshot.dpi is None
        assert snapshot.px_per_degree is None
        assert snapshot.stimulus_font_px(12.0) is None
        # The canvas is structural and survives — it is not derived from mm.
        assert snapshot.canvas == (2560, 1440)

    def test_from_dict_falls_back_rather_than_raising(self):
        """A stored dataset or recovery cache written before the `setup` key
        existed has no snapshot, and a corpus that cannot state its geometry must
        still open."""
        fallback = SetupSnapshot(
            canvas_width=1234, screen_provenance=Provenance.MEASURED
        )
        assert SetupSnapshot.from_dict(None, fallback=fallback) == fallback
        assert SetupSnapshot.from_dict({}, fallback=fallback) == fallback
        # One unparseable field must not discard the rest of a valid setup.
        degraded = SetupSnapshot.from_dict(
            {"canvas_width": "not-a-number", "canvas_height": 900},
            fallback=fallback,
        )
        assert degraded.canvas_width == 1234
        assert degraded.canvas_height == 900

    def test_is_answered_is_the_add_dataset_gate(self):
        assert not SetupSnapshot(screen_provenance=None).is_answered()
        assert SetupSnapshot().is_answered()


class TestProvenanceParam:
    """The compact `setup_prov` share value (DATA-22 §7 surface 2)."""

    def test_round_trips(self):
        snapshot = SetupSnapshot(
            screen_provenance=Provenance.MEASURED,
            geometry_provenance=Provenance.SKIPPED,
            text_provenance=Provenance.ASSUMED,
        )
        param = format_provenance_param(snapshot)
        assert param == "screen:measured,geom:skipped,text:assumed"
        assert parse_provenance_param(param) == snapshot.provenance

    def test_parsing_a_mangled_link_costs_badges_not_the_link(self):
        """It reads a URL a stranger may have hand-edited, so unknown groups and
        unknown provenance words are dropped rather than raised on."""
        parsed = parse_provenance_param("screen:invented,nosuch:measured,geom:measured")
        assert parsed == {"geometry": Provenance.MEASURED}
        assert parse_provenance_param("") == {}
        assert parse_provenance_param(None) == {}
        assert parse_provenance_param("garbage") == {}
