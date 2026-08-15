"""ENG-22: drift correction (PRE-3) on the `render` CLI surface.

`api.plot_scanpath` has taken `drift_correction=` / `drift_connectors=` since
PRE-3 and the app exposes them under Fixations ⚙️ → Drift correction, but the
CLI had no matching flags. These tests pin the flags, their mapping onto the
API call, the validation of the algorithm name, and the fact that leaving them
off reproduces the uncorrected figure exactly.
"""

from __future__ import annotations

import pytest

from scanpath_studio import cli
from scanpath_studio.alignment import ALGORITHMS


def _spy_static(monkeypatch, *, wrap_real: bool = False) -> dict:
    """Capture the kwargs (and optionally the figure) of `api.plot_scanpath`."""
    from scanpath_studio import api

    captured: dict = {}
    real_plot = api.plot_scanpath

    def spy(words, fixations, participant=None, trial=None, **kwargs):
        captured["kwargs"] = kwargs
        if wrap_real:
            captured["fig"] = real_plot(words, fixations, participant, trial, **kwargs)
            return captured["fig"]
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", spy)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    return captured


def _marker_ys(fig) -> list:
    """Every y of the figure's fixation marker traces (skipping the connectors)."""
    ys: list = []
    for trace in fig.data:
        mode = getattr(trace, "mode", None) or ""
        if "markers" in mode and trace.name != "drift":
            values = trace.y if trace.y is not None else ()
            ys.extend(v for v in values if v is not None and v == v)
    return ys


def test_render_forwards_drift_correction(tmp_path, monkeypatch):
    """--drift-correction / --drift-connectors reach plot_scanpath verbatim."""
    captured = _spy_static(monkeypatch)
    cli.main(
        [
            "render",
            "--sample",
            "--drift-correction",
            "warp",
            "--drift-connectors",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["kwargs"]["drift_correction"] == "warp"
    assert captured["kwargs"]["drift_connectors"] is True


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_render_accepts_every_algorithm(tmp_path, monkeypatch, algorithm):
    captured = _spy_static(monkeypatch)
    cli.main(
        [
            "render",
            "--sample",
            "--drift-correction",
            algorithm,
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["kwargs"]["drift_correction"] == algorithm


def test_render_drift_algorithm_is_case_insensitive(tmp_path, monkeypatch):
    """The app title-cases the names in its picker; accept that spelling too."""
    captured = _spy_static(monkeypatch)
    cli.main(
        [
            "render",
            "--sample",
            "--drift-correction",
            "Warp",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["kwargs"]["drift_correction"] == "warp"


def test_render_without_drift_flags_keeps_api_defaults(tmp_path, monkeypatch):
    """Backward compat: no flags → the API's own no-correction defaults."""
    captured = _spy_static(monkeypatch)
    cli.main(["render", "--sample", "-o", str(tmp_path / "x.html")])
    assert captured["kwargs"]["drift_correction"] is None
    assert captured["kwargs"]["drift_connectors"] is False


def test_render_rejects_unknown_drift_algorithm(tmp_path, monkeypatch, capsys):
    """An unknown name never reaches the API; argparse exits non-zero."""
    captured = _spy_static(monkeypatch)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--sample",
                "--drift-correction",
                "nonsense",
                "-o",
                str(tmp_path / "x.html"),
            ]
        )
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "nonsense" in err
    # The message names every valid algorithm.
    for name in ALGORITHMS:
        assert name in err
    assert "kwargs" not in captured  # never got as far as the builder


def test_render_help_lists_every_algorithm(capsys):
    """Pin the help text's spelled-out list to alignment.ALGORITHMS."""
    with pytest.raises(SystemExit):
        cli.main(["render", "--help"])
    flat = " ".join(capsys.readouterr().out.split())
    assert "--drift-correction ALGORITHM" in flat
    assert "--drift-connectors" in flat
    assert ", ".join(ALGORITHMS) in flat


def test_render_drift_connectors_without_algorithm_warns(tmp_path, monkeypatch, capsys):
    """Connectors need something to connect to — warn, don't fail."""
    captured = _spy_static(monkeypatch)
    cli.main(
        ["render", "--sample", "--drift-connectors", "-o", str(tmp_path / "x.html")]
    )
    err = capsys.readouterr().err
    assert "--drift-connectors has no effect" in err
    assert captured["kwargs"]["drift_correction"] is None


def test_render_animate_warns_drift_is_ignored(tmp_path, monkeypatch, capsys):
    """animate_scanpath takes no drift parameters — say so instead of silently
    dropping them (the VIZ-21 table: PRE-3 is static-only)."""
    from scanpath_studio import api

    captured: dict = {}

    def fake_anim(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "animate_scanpath", fake_anim)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--drift-correction",
            "warp",
            "--drift-connectors",
            "-o",
            str(tmp_path / "a.html"),
        ]
    )
    err = capsys.readouterr().err
    assert "ignoring" in err
    assert "drift_correction" in err and "drift_connectors" in err
    assert "drift_correction" not in captured and "drift_connectors" not in captured


def test_render_drift_correction_snaps_fixations(tmp_path, monkeypatch):
    """End to end: the corrected figure's fixations sit on the line centers, and
    --drift-connectors adds the single original→corrected connector trace."""
    captured = _spy_static(monkeypatch, wrap_real=True)
    cli.main(["render", "--sample", "-o", str(tmp_path / "raw.html")])
    raw_ys = _marker_ys(captured["fig"])
    assert not any(trace.name == "drift" for trace in captured["fig"].data)

    cli.main(
        [
            "render",
            "--sample",
            "--drift-correction",
            "attach",
            "--drift-connectors",
            "-o",
            str(tmp_path / "fixed.html"),
        ]
    )
    fixed_fig = captured["fig"]
    fixed_ys = _marker_ys(fixed_fig)
    assert len(fixed_ys) == len(raw_ys)
    # Snapping collapses the y spread onto a handful of line centers.
    assert 0 < len(set(fixed_ys)) < len(set(raw_ys))
    # Connectors: a SINGLE trace with None separators, not one per fixation.
    connectors = [trace for trace in fixed_fig.data if trace.name == "drift"]
    assert len(connectors) == 1
    assert None in tuple(connectors[0].y)
