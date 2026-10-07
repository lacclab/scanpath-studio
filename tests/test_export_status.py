"""EXP-6 shared export stages, signatures, durable UI state, and cleanup."""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio import animation_export, export
from scanpath_studio.export import HTML_SELF_CONTAINED_KEY, ExportOptions
from scanpath_studio.export_status import (
    ExportStage,
    ExportStatus,
    emit_status,
    export_signature,
)


def _figure(value: int = 1) -> go.Figure:
    fig = go.Figure(go.Scatter(x=[0, value], y=[0, value]))
    fig.update_layout(width=640, height=480)
    return fig


def test_signature_covers_content_format_dimensions_scale_and_version():
    def sign(content="replay-1", **overrides):
        options = dict(fmt="png", width=640, height=480, scale=3) | overrides
        return export_signature(content, **options)

    base = sign()
    assert base == sign()
    variants = {
        sign("replay-2"),
        sign(fmt="svg"),
        sign(width=641),
        sign(height=481),
        sign(scale=2),
        sign(exporter_version="next"),
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
        "dpi": None,  # no print width is set
        "label": f"⬇ Download {fmt}",
    }


@pytest.mark.parametrize(
    ("fmt", "shown"), [("PNG", False), ("PDF", False), ("HTML", True)]
)
def test_self_contained_html_is_asked_only_for_html(monkeypatch, fmt, shown):
    """The *Self-contained HTML* checkbox sits under the format, only for HTML."""
    from scanpath_studio import tabs

    _record_image_downloads(monkeypatch)
    monkeypatch.setattr(tabs, "chrome_available", lambda: True)
    at = _static_export_run(fmt)

    assert not at.exception, at.exception
    keys = [checkbox.key for checkbox in at.checkbox]
    assert (HTML_SELF_CONTAINED_KEY in keys) is shown


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
        tabs, "_embed_html_iframe", lambda html, height, **_: embedded.append(html)
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
        tabs, "_embed_html_iframe", lambda html, height, **_: embedded.append(html)
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


def test_self_contained_html_embeds_the_library_and_requests_no_host():
    from scanpath_studio import tabs

    html = tabs._figure_download_data(
        _figure(), "HTML", canvas_width=640, canvas_height=480, self_contained=True
    )()
    # No script loaded from a host (the library's own text names one, for
    # geo maps a scanpath never draws).
    assert not re.search(r'<script[^>]*\ssrc="https?://', html)
    assert "plotly.js v" in html  # the library's own banner, inline


def test_pdf_without_a_browser_warns_once_and_disables_download(monkeypatch):
    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "chrome_available", lambda: False)
    at = _static_export_run("PDF")

    assert not at.exception, at.exception
    warnings = "\n".join(warning.value for warning in at.warning)
    assert warnings.count("PDF export needs Chrome, Chromium or Edge") == 1
    (button,) = _download_buttons(at)
    assert button.disabled


def _animation_export_app():
    import plotly.graph_objects as go

    from scanpath_studio.tabs import _render_animation_export, _ReplayView

    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[go.Frame(name="0", data=[go.Scatter(x=[0], y=[0])], traces=[0])],
    )
    view = _ReplayView.from_figure(
        fig, plot_key="anim", download_name="anim", signature="sig"
    )
    _render_animation_export(view, file_stem="anim")


def _animation_clip_app():
    import plotly.graph_objects as go

    from scanpath_studio.tabs import _render_animation_export, _ReplayView

    # Three frames whose clock says the replay lasts 10 s of reading at ×2 —
    # what `make_scanpath_animation` stamps (BUG-93).
    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[
            go.Frame(name=str(k), data=[go.Scatter(x=[k], y=[k])], traces=[0])
            for k in range(3)
        ],
        layout={
            "meta": {
                "scanpath_autoplay": False,
                "scanpath_frame_times_ms": [0.0, 5000.0, 10000.0],
                "scanpath_playback_speed": 2.0,
            }
        },
    )
    view = _ReplayView.from_figure(
        fig, plot_key="anim", download_name="anim", signature="sig"
    )
    _render_animation_export(view, file_stem="anim")


def _unloaded_replay_export_app():
    import dataclasses

    import plotly.graph_objects as go

    from scanpath_studio.tabs import _render_animation_export, _ReplayView

    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[
            go.Frame(name=str(k), data=[go.Scatter(x=[k], y=[k])], traces=[0])
            for k in range(3)
        ],
        layout={
            "width": 400,
            "height": 300,
            "meta": {
                "scanpath_autoplay": False,
                "scanpath_frame_times_ms": [0.0, 5000.0, 10000.0],
                "scanpath_playback_speed": 2.0,
            },
        },
    )
    view = _ReplayView.from_figure(
        fig, plot_key="anim", download_name="anim", signature="sig"
    )

    class Unloaded(_ReplayView):
        def figure(self):
            raise AssertionError("the replay's figure was loaded during a script run")

    fields = {
        field.name: getattr(view, field.name) for field in dataclasses.fields(view)
    }
    _render_animation_export(Unloaded(**fields), file_stem="anim")


@pytest.mark.parametrize("fmt", ["HTML", "GIF", "MP4"])
def test_the_export_panel_does_not_load_the_replay_on_a_rerun(monkeypatch, fmt):
    # PERF-16: unpickling the replay costs 9 s at 2,000 frames, so the panel
    # works from the cached view — frame count, clip length, size, signature —
    # and loads the figure only on a click that exports it.
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "chrome_available", lambda: True)
    at = AppTest.from_function(_unloaded_replay_export_app)
    at.session_state["anim_export_format"] = fmt
    at = at.run(timeout=30)

    assert not at.exception, at.exception


def test_the_clip_lasts_what_the_figures_own_replay_does(monkeypatch):
    # BUG-93: the GIF/MP4 took a playback time the tab measured on its own, from
    # fixations the builder's Discard flags had not dropped yet, so a clip could
    # outlast the replay it was made from. It reads the figure's clock now.
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from scanpath_studio import tabs

    monkeypatch.setattr(tabs, "chrome_available", lambda: True)
    at = AppTest.from_function(_animation_clip_app)
    at.session_state["anim_export_format"] = "MP4"
    at = at.run(timeout=30)

    assert not at.exception, at.exception
    assert "clip ≈ 5.0s" in " ".join(caption.value for caption in at.caption)


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


def test_animation_html_carries_the_replay_player():
    from scanpath_studio import tabs

    fig = go.Figure(
        go.Scatter(x=[0, 1], y=[0, 1]),
        frames=[go.Frame(name="0", data=[go.Scatter(x=[0], y=[0])], traces=[0])],
    )
    bare = tabs._animation_html(fig)
    # BUG-93: a replay built by `make_scanpath_animation` stamps its clock, and
    # the download keeps time with the same wall-clock player as the app.
    fig.update_layout(
        meta={
            "scanpath_autoplay": True,
            "scanpath_frame_times_ms": [0.0],
            "scanpath_playback_speed": 1.0,
        }
    )
    replay = tabs._animation_html(fig)

    assert "plotly_buttonclicked" not in bare
    assert "plotly_buttonclicked" in replay
    # Plotly's own auto_play is off either way: it ignores the configured speed.
    assert "Plotly.animate('" not in bare
    assert "Plotly.animate('" not in replay
