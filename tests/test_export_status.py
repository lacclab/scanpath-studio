"""EXP-6 shared export stages, signatures, durable UI state, and cleanup."""

from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio import animation_export, export
from scanpath_studio.export import ExportOptions
from scanpath_studio.export_status import (
    ExportStage,
    ExportStatus,
    emit_status,
    static_export_signature,
)


def _figure(value: int = 1) -> go.Figure:
    fig = go.Figure(go.Scatter(x=[0, value], y=[0, value]))
    fig.update_layout(width=640, height=480)
    return fig


def test_static_signature_covers_figure_format_dimensions_scale_and_version():
    base = static_export_signature(_figure(), fmt="png", width=640, height=480, scale=3)
    assert base == static_export_signature(
        _figure(), fmt="png", width=640, height=480, scale=3
    )
    variants = {
        static_export_signature(_figure(2), fmt="png", width=640, height=480, scale=3),
        static_export_signature(_figure(), fmt="svg", width=640, height=480, scale=3),
        static_export_signature(_figure(), fmt="png", width=641, height=480, scale=3),
        static_export_signature(_figure(), fmt="png", width=640, height=481, scale=3),
        static_export_signature(_figure(), fmt="png", width=640, height=480, scale=2),
        static_export_signature(
            _figure(),
            fmt="png",
            width=640,
            height=480,
            scale=3,
            exporter_version="next",
        ),
    }
    assert base not in variants
    assert len(variants) == 6


def test_status_rejects_fabricated_or_invalid_counts():
    with pytest.raises(ValueError, match="together"):
        emit_status(None, ExportStage.RASTERIZING, "bad", completed=1)
    with pytest.raises(ValueError, match="exceed"):
        emit_status(None, ExportStage.RASTERIZING, "bad", completed=2, total=1)
    indeterminate = emit_status(None, ExportStage.RASTERIZING, "opaque operation")
    assert indeterminate.fraction is None


def test_browser_preflight_uses_choreographers_complete_discovery(monkeypatch):
    from choreographer.browsers.chromium import Chromium

    expected = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    calls = []

    def fake_find_browser(cls, *, skip_local):
        calls.append(skip_local)
        return expected

    monkeypatch.setattr(Chromium, "find_browser", classmethod(fake_find_browser))

    assert animation_export.chromium_browser_path() == expected
    assert animation_export.chrome_available()
    assert calls == [True, True]


def test_browser_preflight_falls_back_to_managed_chrome(monkeypatch):
    from choreographer.browsers.chromium import Chromium

    managed = "/managed/Google Chrome for Testing"
    calls = []

    def fake_find_browser(cls, *, skip_local):
        calls.append(skip_local)
        return None if skip_local else managed

    monkeypatch.setattr(Chromium, "find_browser", classmethod(fake_find_browser))

    assert animation_export.chromium_browser_path() == managed
    assert calls == [True, False]


def test_shared_renderer_receives_the_discovered_browser_path(monkeypatch):
    import kaleido

    expected = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    calls = []
    monkeypatch.setattr(animation_export, "chromium_browser_path", lambda: expected)
    monkeypatch.setattr(
        kaleido,
        "start_sync_server",
        lambda **kwargs: calls.append(("start", kwargs)),
    )
    monkeypatch.setattr(kaleido, "calc_fig_sync", lambda *args, **kwargs: b"rendered")
    monkeypatch.setattr(
        kaleido,
        "stop_sync_server",
        lambda **kwargs: calls.append(("stop", kwargs)),
    )

    with export._figure_renderer(True) as render:
        assert render(_figure(), "png", 640, 480, 1) == b"rendered"

    assert calls[0] == (
        "start",
        {"path": expected, "silence_warnings": True},
    )
    assert calls[-1][0] == "stop"


def test_animation_missing_browser_fails_before_starting_kaleido(monkeypatch):
    import kaleido

    fig = _figure()
    fig.frames = [go.Frame(name="0")]
    monkeypatch.setattr(animation_export, "chromium_browser_path", lambda: None)

    def unexpected_start(**kwargs):
        pytest.fail("Kaleido must not start without a resolved browser")

    monkeypatch.setattr(kaleido, "start_sync_server", unexpected_start)

    with pytest.raises(
        animation_export.AnimationExportError,
        match="No Chrome/Chromium",
    ):
        animation_export.render_png_frames(fig, frame_indices=[0])


def test_static_render_emits_stage_sequence(monkeypatch):
    monkeypatch.setattr(animation_export, "chrome_available", lambda: True)

    @contextmanager
    def fake_renderer(enabled):
        assert enabled is True
        yield lambda fig, fmt, width, height, scale: b"rendered"

    monkeypatch.setattr(export, "_figure_renderer", fake_renderer)
    seen: list[ExportStatus] = []
    data = export.render_static_figure_bytes(
        _figure(),
        fmt="png",
        width=640,
        height=480,
        scale=3,
        status_callback=seen.append,
    )
    assert data == b"rendered"
    assert [status.stage for status in seen] == [
        ExportStage.PREPARING,
        ExportStage.STARTING_RENDERER,
        ExportStage.RASTERIZING,
        ExportStage.FINALIZING,
        ExportStage.READY,
    ]
    assert all(status.fraction is None for status in seen)


def test_static_render_error_ends_in_error_and_returns_no_bytes(monkeypatch):
    monkeypatch.setattr(animation_export, "chrome_available", lambda: True)

    @contextmanager
    def broken_renderer(enabled):
        def fail(*args):
            raise RuntimeError("renderer crashed")

        yield fail

    monkeypatch.setattr(export, "_figure_renderer", broken_renderer)
    seen: list[ExportStatus] = []
    with pytest.raises(RuntimeError, match="renderer crashed"):
        export.render_static_figure_bytes(
            _figure(),
            fmt="png",
            width=640,
            height=480,
            scale=3,
            status_callback=seen.append,
        )
    assert seen[-1].stage == ExportStage.ERROR
    assert seen[-1].error == "renderer crashed"


def test_animation_adapts_frame_counts_then_reports_encoding_and_ready(monkeypatch):
    fig = go.Figure()
    fig.frames = [go.Frame(name="0"), go.Frame(name="1")]

    def fake_frames(fig, *, scale, show_elapsed, frame_indices, progress_callback=None):
        progress_callback(1, 2)
        progress_callback(2, 2)
        return [b"a", b"b"], (10, 10)

    monkeypatch.setattr(animation_export, "render_png_frames", fake_frames)
    monkeypatch.setattr(animation_export, "encode_gif", lambda pngs, duration: b"gif")
    seen: list[ExportStatus] = []
    result = animation_export.export_animation(
        fig,
        fmt="gif",
        frame_duration_ms=40,
        status_callback=seen.append,
    )
    assert result == b"gif"
    stages = [status.stage for status in seen]
    assert stages == [
        ExportStage.PREPARING,
        ExportStage.STARTING_RENDERER,
        ExportStage.RASTERIZING,
        ExportStage.RASTERIZING,
        ExportStage.ENCODING_WRITING,
        ExportStage.FINALIZING,
        ExportStage.READY,
    ]
    counts = [status.completed for status in seen if status.completed is not None]
    assert counts == sorted(counts)


def test_bulk_status_includes_invisible_zip_finalization():
    combos = pd.DataFrame({"participant_id": ["p1", "p1"], "trial_id": ["t1", "t2"]})
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t2"],
            "word_id": [1, 1],
            "text": ["one", "two"],
            "x": [10.0, 10.0],
            "y": [10.0, 10.0],
            "width": [30.0, 30.0],
            "height": [20.0, 20.0],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t2"],
            "x": [20.0, 20.0],
            "y": [20.0, 20.0],
            "duration_ms": [100.0, 100.0],
            "timestamp_ms": [0.0, 0.0],
            "word_id": [1, 1],
            "order_in_trial": [1, 1],
        }
    )
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_plot_config=True,
    )
    seen: list[ExportStatus] = []
    data, progress = export.bulk_export(
        combos,
        words,
        fixations,
        canvas_width=800,
        canvas_height=600,
        base_font_size=14,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings={},
        options=options,
        status_callback=seen.append,
    )
    assert data.startswith(b"PK")
    assert progress.finished_trials == 2
    assert [status.stage for status in seen][-2:] == [
        ExportStage.FINALIZING,
        ExportStage.READY,
    ]
    counts = [status.completed for status in seen if status.completed is not None]
    assert counts == sorted(counts)


def _static_export_app():
    import plotly.graph_objects as go

    from scanpath_studio.tabs import _render_save_plot_button

    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(width=640, height=480)
    _render_save_plot_button(
        fig,
        canvas_width=640,
        canvas_height=480,
        slug="p1-t1",
        key_prefix="test_static",
    )


def test_static_result_stays_ready_across_rerun(monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    def fake_render(*args, status_callback=None, **kwargs):
        if status_callback:
            status_callback(
                ExportStatus(ExportStage.READY, "Ready to download.", elapsed_s=0.1)
            )
        return b"png-bytes"

    monkeypatch.setattr(tabs, "render_static_figure_bytes", fake_render)
    at = AppTest.from_function(_static_export_app).run(timeout=30)
    render = next(button for button in at.button if button.label == "Render PNG")
    at = render.click().run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_test_static_static_export_cache"]["data"] == b"png-bytes"
    assert any("PNG ready" in success.value for success in at.success)
    assert at.get("download_button"), "ready result has no download control"

    at = at.run(timeout=30)
    assert not at.exception, at.exception
    assert any("PNG ready" in success.value for success in at.success)
    assert at.get("download_button")


def test_static_missing_browser_hint_is_not_duplicated(monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    def missing_browser(*args, **kwargs):
        raise RuntimeError(animation_export.CHROME_INSTALL_HINT)

    monkeypatch.setattr(tabs, "render_static_figure_bytes", missing_browser)
    monkeypatch.setattr(tabs, "chrome_available", lambda: False)
    at = AppTest.from_function(_static_export_app).run(timeout=30)
    render = next(button for button in at.button if button.label == "Render PNG")
    at = render.click().run(timeout=30)

    assert not at.exception, at.exception
    warnings = "\n".join(warning.value for warning in at.warning)
    assert warnings.count(animation_export.CHROME_INSTALL_HINT) == 1
