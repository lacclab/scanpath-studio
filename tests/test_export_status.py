"""EXP-6 shared export stages, signatures, durable UI state, and cleanup."""

from __future__ import annotations

import threading
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

    with pytest.raises(animation_export.AnimationExportError) as excinfo:
        animation_export.render_png_frames(fig, frame_indices=[0])
    assert str(excinfo.value) == animation_export.CHROME_INSTALL_HINT


def _kaleido_lock_free_elsewhere() -> bool:
    """Whether another thread could take the warm-server lock right now."""
    seen = []

    def probe():
        got = animation_export.KALEIDO_LOCK.acquire(blocking=False)
        if got:
            animation_export.KALEIDO_LOCK.release()
        seen.append(got)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return seen[0]


def _fake_warm_kaleido(monkeypatch, on_render=lambda: None):
    import kaleido

    def calc_fig_sync(*args, **kwargs):
        on_render()
        return b"rendered"

    monkeypatch.setattr(animation_export, "chromium_browser_path", lambda: "/chrome")
    monkeypatch.setattr(kaleido, "start_sync_server", lambda **kwargs: None)
    monkeypatch.setattr(kaleido, "calc_fig_sync", calc_fig_sync)
    monkeypatch.setattr(kaleido, "stop_sync_server", lambda **kwargs: None)


def test_warm_kaleido_server_is_held_under_the_process_lock(monkeypatch):
    """UX-150: a download on a worker thread must not share the server mid-export."""
    _fake_warm_kaleido(monkeypatch)

    with export._figure_renderer(True):
        assert not _kaleido_lock_free_elsewhere()
    assert _kaleido_lock_free_elsewhere()
    with export._figure_renderer(False):
        assert _kaleido_lock_free_elsewhere(), "a table-only export has no server"


def test_animation_frames_render_under_the_process_lock(monkeypatch):
    held = []
    _fake_warm_kaleido(
        monkeypatch, on_render=lambda: held.append(not _kaleido_lock_free_elsewhere())
    )
    fig = _figure()
    fig.frames = [
        go.Frame(name=str(k), data=[go.Scatter(x=[0, k], y=[0, k])], traces=[0])
        for k in (1, 2)
    ]

    animation_export.render_png_frames(fig, show_elapsed=False)

    assert held == [True, True]
    assert _kaleido_lock_free_elsewhere()


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


def _download_buttons(at):
    return [element.proto for element in at.get("download_button")]


def _record_image_downloads(monkeypatch) -> list[dict]:
    """Stand in for the browser-side image button, keeping what it was given."""
    from scanpath_studio import tabs

    calls: list[dict] = []

    def factory():
        return lambda **kwargs: calls.append(kwargs)

    monkeypatch.setattr(tabs, "_image_download_component", factory)
    return calls


def _static_export_run(fmt: str):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    at = AppTest.from_function(_static_export_app)
    at.session_state["test_static_save_format"] = fmt
    return at.run(timeout=30)


@pytest.mark.parametrize(("fmt", "scale"), [("PNG", 3), ("SVG", 1)])
def test_png_and_svg_are_saved_by_the_browser(monkeypatch, fmt, scale):
    """UX-152: drawn from the plot on screen — no server render, no Chrome needed."""
    from scanpath_studio import tabs

    def must_not_render(*args, **kwargs):
        raise AssertionError("the figure rendered on the server")

    monkeypatch.setattr(tabs, "render_static_figure_bytes", must_not_render)
    monkeypatch.setattr(tabs, "chrome_available", lambda: False)
    calls = _record_image_downloads(monkeypatch)
    at = _static_export_run(fmt)

    assert not at.exception, at.exception
    assert not _download_buttons(at), "PNG/SVG went back to the server"
    assert not [warning.value for warning in at.warning], "PNG/SVG need no Chrome"
    (call,) = calls
    assert call["key"] == "test_static_save_image"
    assert call["data"] == {
        "plot_id": tabs._true_scale_plot_id("single"),
        "format": fmt.lower(),
        "filename": f"scanpath_p1-t1.{fmt.lower()}",
        "width": 640,
        "height": 480,
        "scale": scale,
        "label": f"⬇ Download {fmt}",
    }


def test_the_browser_image_button_mounts():
    """The real v2 component registers and mounts in a script run."""
    at = _static_export_run("PNG")
    assert not at.exception, at.exception
    assert not _download_buttons(at)


def test_pdf_downloads_in_one_click(monkeypatch):
    """UX-150: one download button, no Render step, and nothing renders per rerun."""
    from scanpath_studio import tabs

    def must_not_render(*args, **kwargs):
        raise AssertionError("the figure rendered during a script run")

    monkeypatch.setattr(tabs, "render_static_figure_bytes", must_not_render)
    monkeypatch.setattr(tabs, "chrome_available", lambda: True)
    at = _static_export_run("PDF")

    assert not at.exception, at.exception
    assert not [button.label for button in at.button], "a Render step is back"
    (button,) = _download_buttons(at)
    assert button.label == "⬇ Download PDF"
    assert not button.disabled

    at = at.run(timeout=30)
    assert not at.exception, at.exception
    assert len(_download_buttons(at)) == 1


def _true_scale_chart_app():
    import plotly.graph_objects as go

    from scanpath_studio import tabs

    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(width=640, height=480)
    tabs._render_true_scale_chart(fig, key="single", download_name="scanpath_p1__t1")


def test_the_plot_camera_saves_the_export_png(monkeypatch):
    """UX-152: the modebar's camera gives the Export PNG, not a 1× newplot.png."""
    import json
    import re

    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    embedded: list[str] = []
    monkeypatch.setattr(
        tabs, "_embed_html_iframe", lambda html, height: embedded.append(html)
    )
    at = AppTest.from_function(_true_scale_chart_app).run(timeout=30)

    assert not at.exception, at.exception
    (html,) = embedded
    assert f'id="{tabs._true_scale_plot_id("single")}"' in html
    options = re.search(r'"toImageButtonOptions":\s*(\{[^}]*\})', html)
    assert options, "the camera is unconfigured"
    assert json.loads(options.group(1)) == {
        "format": "png",
        "filename": "scanpath_p1__t1",
        "width": 640,
        "height": 480,
        "scale": 3,
    }


def _unnamed_true_scale_chart_app():
    import plotly.graph_objects as go

    from scanpath_studio import tabs

    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(width=640, height=480)
    tabs._render_true_scale_chart(fig, key="ptext_stimulus")


def test_an_unnamed_chart_keeps_plotlys_file_name(monkeypatch):
    """Only the Scanpath view's figures are scanpaths; the rest stay newplot.png."""
    import json
    import re

    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    embedded: list[str] = []
    monkeypatch.setattr(
        tabs, "_embed_html_iframe", lambda html, height: embedded.append(html)
    )
    at = AppTest.from_function(_unnamed_true_scale_chart_app).run(timeout=30)

    assert not at.exception, at.exception
    (html,) = embedded
    options = re.search(r'"toImageButtonOptions":\s*(\{[^}]*\})', html)
    assert json.loads(options.group(1)) == {
        "format": "png",
        "width": 640,
        "height": 480,
        "scale": 3,
    }


@pytest.mark.parametrize(
    ("fmt", "scale"), [("PNG", 3), ("SVG", 1), ("PDF", 1)], ids=["png", "svg", "pdf"]
)
def test_static_download_data_renders_on_call(monkeypatch, fmt, scale):
    from scanpath_studio import tabs

    calls = []

    def fake_render(fig, **kwargs):
        calls.append(kwargs)
        return b"image-bytes"

    monkeypatch.setattr(tabs, "render_static_figure_bytes", fake_render)
    fig = _figure()
    fig.update_layout(width=None)
    data = tabs._figure_download_data(fig, fmt, canvas_width=900, canvas_height=700)

    assert calls == [], "building the callable must not render"
    assert data() == b"image-bytes"
    assert calls == [{"fmt": fmt.lower(), "width": 900, "height": 480, "scale": scale}]


def test_html_download_data_is_a_standalone_page():
    from scanpath_studio import tabs

    html = tabs._figure_download_data(
        _figure(), "HTML", canvas_width=640, canvas_height=480
    )()
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "cdn.plot.ly" in html


def test_pdf_without_a_browser_warns_once_and_disables_download(monkeypatch):
    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "chrome_available", lambda: False)
    at = _static_export_run("PDF")

    assert not at.exception, at.exception
    warnings = "\n".join(warning.value for warning in at.warning)
    assert warnings.count(animation_export.CHROME_INSTALL_HINT) == 1
    (button,) = _download_buttons(at)
    assert button.disabled


def _pair_export_app():
    import plotly.graph_objects as go

    from scanpath_studio.controls import viz_settings_from_state
    from scanpath_studio.export import ComparisonSide
    from scanpath_studio.synthetic import load_synthetic_data
    from scanpath_studio.tabs import _render_pair_export

    words, fixations = load_synthetic_data()
    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(width=640, height=480)
    side = ComparisonSide("p1", "t1", words, fixations)
    _render_pair_export(
        fig,
        (side, side),
        canvas_width=640,
        canvas_height=480,
        viz_settings=viz_settings_from_state(fixations, 14, words),
        line_spacing=3.0,
        scale_text_to_boxes=True,
    )


def test_pair_bundle_downloads_in_one_click(monkeypatch):
    """UX-150: the Compare pair bundle lost its Build step too."""
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    def must_not_build(*args, **kwargs):
        raise AssertionError("the bundle was built during a script run")

    monkeypatch.setattr(tabs, "pair_export", must_not_build)
    monkeypatch.setattr(tabs, "chrome_available", lambda: True)
    at = AppTest.from_function(_pair_export_app).run(timeout=30)

    assert not at.exception, at.exception
    assert not [button.label for button in at.button], "a Build step is back"
    (button,) = _download_buttons(at)
    assert button.label == "⬇ Download bundle (zip)"
    assert not button.disabled


@pytest.mark.parametrize(("fmt", "blocked"), [("png", True), ("html", False)])
def test_pair_bundle_without_a_browser(monkeypatch, fmt, blocked):
    """A figure format that needs Chrome is refused up front; HTML still works."""
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "chrome_available", lambda: False)
    at = AppTest.from_function(_pair_export_app)
    at.session_state["cmp_pair_export_format"] = fmt
    at = at.run(timeout=30)

    assert not at.exception, at.exception
    warnings = "\n".join(warning.value for warning in at.warning)
    assert warnings.count(animation_export.CHROME_INSTALL_HINT) == int(blocked)
    (button,) = _download_buttons(at)
    assert button.disabled is blocked


def _animation_export_app():
    import plotly.graph_objects as go

    from scanpath_studio.tabs import _render_animation_export

    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[go.Frame(name="0", data=[go.Scatter(x=[0], y=[0])], traces=[0])],
    )
    _render_animation_export(fig, file_stem="anim", playback_ms=1000.0)


def test_animation_html_is_built_on_click_not_per_rerun(monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    def must_not_serialize(fig):
        raise AssertionError("the animation HTML was built during a script run")

    monkeypatch.setattr(tabs, "_animation_html", must_not_serialize)
    at = AppTest.from_function(_animation_export_app).run(timeout=30)

    assert not at.exception, at.exception
    (button,) = _download_buttons(at)
    assert button.label == "⬇ Download HTML"


def test_animation_html_autoplays_at_the_configured_speed():
    from scanpath_studio import plots, tabs

    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[go.Frame(name="0", data=[go.Scatter(x=[0], y=[0])], traces=[0])],
    )
    paused = tabs._animation_html(fig)
    fig.update_layout(
        meta={plots._AUTOPLAY_META_FLAG: True, plots._AUTOPLAY_META_DURATION: 123}
    )
    autoplaying = tabs._animation_html(fig)

    # Plotly fills the kickoff's `{plot_id}` in, so match its frame duration.
    assert "frame:{duration:123" in plots.animation_autoplay_post_script(123)
    assert "frame:{duration:123" not in paused
    assert "frame:{duration:123" in autoplaying
