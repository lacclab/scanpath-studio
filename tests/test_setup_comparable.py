"""CMP-11: when may two datasets' readings share one set of pixel coordinates?

The overlay layout pools both trials into ONE `_compute_axis_ranges`. Across two
monitors that is the union of two unrelated pixel spaces, so CMP-8 blocked the
layout for every cross-dataset pair. `setups_comparable` is what unblocks the
case the block was always too coarse for: two corpora recorded on the same
screen, where the pixels already mean the same thing and nothing needs
rescaling.

The interesting assertions here are the two deliberate *omissions* — physical
geometry is not consulted, and `ASSUMED` provenance is not a match — because
both are choices a later reader would otherwise be tempted to "fix".
"""

from __future__ import annotations

from scanpath_studio.experimental_setup import (
    Provenance,
    SetupSnapshot,
    setups_comparable,
)


def _snapshot(
    width: int = 1920,
    height: int = 1080,
    *,
    screen: Provenance = Provenance.MEASURED,
    monitor_width_mm: float = 597.0,
    viewing_distance_mm: float = 800.0,
    geometry: Provenance = Provenance.ASSUMED,
) -> SetupSnapshot:
    return SetupSnapshot(
        canvas_width=width,
        canvas_height=height,
        monitor_width_mm=monitor_width_mm,
        viewing_distance_mm=viewing_distance_mm,
        screen_provenance=screen,
        geometry_provenance=geometry,
    )


def test_same_screen_measured_on_both_sides_is_comparable_and_silent():
    """No note at all — the control case for the caution tests below."""
    ok, reason = setups_comparable(_snapshot(), _snapshot())
    assert ok is True
    assert reason == ""


def test_measured_against_estimated_is_comparable():
    """A corpus whose canvas is inferred from data extents still *knows* a screen.

    `compare_source.snapshot_for` reports ESTIMATED for exactly that case, so
    refusing it would block most built-in pairs for no gain.
    """
    ok, reason = setups_comparable(
        _snapshot(screen=Provenance.MEASURED),
        _snapshot(screen=Provenance.ESTIMATED),
    )
    assert ok is True
    assert reason == ""


def test_differing_canvas_is_not_comparable_and_names_both_screens():
    ok, reason = setups_comparable(_snapshot(2560, 1440), _snapshot(1680, 1050))
    assert ok is False
    assert "2560" in reason and "1440" in reason
    assert "1680" in reason and "1050" in reason


def test_assumed_screen_is_allowed_but_cautioned():
    """A matching canvas nobody recorded warns; it does not refuse.

    Settled 2026-08-12 on the case that motivated it: two OneStop regimes, both
    2560x1440, both ASSUMED because the corpus records no screen. Refusing there
    blocked exactly the comparison the feature exists for. The app cannot prove
    the two displays matched, but the user usually can — so the overlay is drawn
    and the caveat travels with it.
    """
    measured = _snapshot(screen=Provenance.MEASURED)
    assumed = _snapshot(screen=Provenance.ASSUMED)

    for pair in ((measured, assumed), (assumed, measured), (assumed, assumed)):
        allowed, note = setups_comparable(*pair)
        assert allowed is True
        assert note, "an unrecorded screen must still be disclosed"
        assert "1920x1080" in note

    # Grammar differs between one unknown side and two — both are user-facing.
    assert setups_comparable(assumed, assumed)[1].startswith("Neither dataset")
    assert setups_comparable(measured, assumed)[1].startswith("The second dataset")
    assert setups_comparable(assumed, measured)[1].startswith("The first dataset")


def test_a_differing_canvas_is_the_only_hard_refusal():
    """The canvas is the gate; everything else is a caveat."""
    allowed, _ = setups_comparable(
        _snapshot(2560, 1440, screen=Provenance.ASSUMED),
        _snapshot(2560, 1440, screen=Provenance.ASSUMED),
    )
    assert allowed is True
    allowed, _ = setups_comparable(
        _snapshot(2560, 1440, screen=Provenance.MEASURED),
        _snapshot(1680, 1050, screen=Provenance.MEASURED),
    )
    assert allowed is False


def test_physical_geometry_is_not_consulted():
    """Deliberate omission — nothing in the overlay path converts to degrees.

    Requiring `monitor_width_mm` / `viewing_distance_mm` to match would gate the
    feature on quantities it never reads, and every built-in corpus hard-codes
    `geometry: ASSUMED`, so the gate would be inert for the whole bundled
    catalogue. Guarded here so a later "tighten this up" cannot land silently.
    """
    ok, reason = setups_comparable(
        _snapshot(monitor_width_mm=597.0, viewing_distance_mm=800.0),
        _snapshot(monitor_width_mm=474.0, viewing_distance_mm=600.0),
    )
    assert ok is True
    assert reason == ""


def test_skipped_geometry_does_not_block_a_shared_screen():
    """`SKIPPED` geometry hides px/degree, which the overlay never asks for."""
    ok, _ = setups_comparable(
        _snapshot(geometry=Provenance.SKIPPED),
        _snapshot(geometry=Provenance.SKIPPED),
    )
    assert ok is True


def test_reason_is_a_complete_sentence():
    """The UI caption, the CLI error and the API exception all print it verbatim."""
    _, reason = setups_comparable(_snapshot(2560, 1440), _snapshot(1680, 1050))
    assert reason[:1].isupper()
    assert reason.endswith(".")


def test_a_public_corpus_reports_its_declared_monitor_not_its_data_extents():
    """Regression: the gate refused exactly the pairs CMP-11 exists to allow.

    `app.resolve_source_monitor` recognised a public corpus only via
    `PUBLIC_DATASETS_CHOICE`, but `data_source_choice` holds the registry
    *label* (DATA-9's flat picker) and `compare_source` names B by label too.
    So a public corpus fell through to `compute_canvas_size` and reported its
    rounded data extents as an ESTIMATED canvas. Cosmetic before CMP-11 (only
    the split panels' `canvas_b` read it); load-bearing once `setups_comparable`
    gates the overlay on the canvas.
    """
    import pandas as pd

    from scanpath_studio import app

    words = pd.DataFrame(
        {
            "x": [100.0, 200.0],
            "y": [50.0, 50.0],
            "width": [90.0, 90.0],
            "height": [40.0, 40.0],
        }
    )
    fixations = pd.DataFrame({"x": [120.0, 220.0], "y": [70.0, 70.0]})

    declared = {
        label: spec["monitor"]
        for label, spec in app.PUBLIC_DATASET_REGISTRY.items()
        if spec.get("monitor")
    }
    assert declared, "no public corpus declares a monitor — test is vacuous"
    for label, monitor in declared.items():
        width, height, authoritative = app.resolve_source_monitor(
            label, words, fixations
        )
        assert (width, height) == tuple(monitor), label
        assert authoritative is True, label
