"""Tests for rasterizing the scanpath animation to GIF / MP4.

Rendering is now fully in-process — matplotlib ``savefig`` per frame, no headless
browser — so the real-render end-to-end can ALWAYS run (no Kaleido/Chrome skip).
``make_scanpath_animation`` returns a :class:`ScanpathAnimation` dataclass whose
``.frames`` is one entry per fixation onset and whose ``.figure`` is a plain
matplotlib :class:`~matplotlib.figure.Figure`. The encode tests still synthesize
PNG frames with Pillow (they never touched the figure builder).
"""

from __future__ import annotations

import io
import os
import tempfile

import imageio.v3 as iio
import pytest
from matplotlib.figure import Figure
from PIL import Image

from scanpath_studio import animation_export as ae
from scanpath_studio.animation_export import (
    AnimationExportError,
    encode_gif,
    encode_mp4,
    export_animation,
    mime_for,
)
from scanpath_studio.plots import (
    ScanpathAnimation,
    animation_playback_ms,
    make_scanpath_animation,
)

_MP4_DT_MS = 1000.0 / 60.0  # the module's fixed MP4 timebase


def _png(color, size=(48, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _solid_frames(n: int) -> list[bytes]:
    # Distinct colours so the encoders see genuinely different frames.
    return [_png((10 * i % 256, 20 * i % 256, 30 * i % 256)) for i in range(n)]


def _mp4_frame_count(data: bytes) -> int:
    path = tempfile.mktemp(suffix=".mp4")
    with open(path, "wb") as fh:
        fh.write(data)
    try:
        return sum(1 for _ in iio.imiter(path))
    finally:
        os.unlink(path)


@pytest.fixture
def anim_fig(normalized_words_df, normalized_fixations_df):
    return make_scanpath_animation(
        normalized_words_df,
        normalized_fixations_df,
        canvas_width=800,
        canvas_height=600,
        base_font_size=12,
        font_family="Arial",
        playback_speed=1.0,
        show_words=True,
        show_word_labels=True,
        show_saccades=True,
        show_order=True,
        marker_size_range=(8, 24),
        order_font_size=10,
        order_font_color="#000000",
    )


@pytest.fixture
def empty_anim(normalized_words_df, normalized_fixations_df):
    """A ScanpathAnimation built from zero fixations -> zero frames."""
    return make_scanpath_animation(
        normalized_words_df,
        normalized_fixations_df.iloc[0:0],
        canvas_width=800,
        canvas_height=600,
        base_font_size=12,
        font_family="Arial",
        playback_speed=1.0,
    )


class TestMimeFor:
    def test_known_formats(self):
        assert mime_for("gif") == "image/gif"
        assert mime_for("mp4") == "video/mp4"
        assert mime_for("MP4") == "video/mp4"


class TestSelectFrames:
    def test_no_cap_returns_all(self):
        assert ae._select_frames(10, None) == list(range(10))

    def test_cap_above_count_returns_all(self):
        assert ae._select_frames(5, 100) == list(range(5))

    def test_cap_downsamples_and_keeps_endpoints(self):
        idx = ae._select_frames(100, 10)
        assert len(idx) <= 10
        assert idx[0] == 0
        assert idx[-1] == 99
        assert idx == sorted(set(idx))  # sorted & de-duplicated

    def test_nonpositive_cap_returns_all(self):
        assert ae._select_frames(7, 0) == list(range(7))


class TestStaticBase:
    """The animation is a matplotlib figure with no in-figure interactive widgets:
    the transport (play/pause/scrub) comes from the external ``to_jshtml`` player
    chrome, not from extra axes baked into the figure. Rasterizing must not mutate
    the frame count either."""

    def test_no_widget_axes_in_figure(self, anim_fig):
        assert isinstance(anim_fig, ScanpathAnimation)
        assert isinstance(anim_fig.figure, Figure)
        # No slider/updatemenu axes are reserved inside the figure: just the data
        # axes (a colorbar/legend would be an extra axes, but this fixture has
        # neither), so the figure carries exactly one Axes.
        assert len(anim_fig.figure.axes) == 1

    def test_render_does_not_mutate_frame_count(self, anim_fig):
        # The same anim is reused for the interactive HTML export, so the GIF/MP4
        # render path must leave the frame list intact.
        n_frames = len(anim_fig.frames)
        assert n_frames >= 1
        pngs, _size = ae.render_png_frames(anim_fig, scale=0.5)
        assert len(pngs) == n_frames
        assert len(anim_fig.frames) == n_frames


class TestElapsedLabels:
    def test_one_label_per_frame(self, anim_fig):
        labels = anim_fig.elapsed_labels
        assert len(labels) == len(anim_fig.frames)
        assert all(lbl.endswith("s") for lbl in labels)

    def test_empty_animation_has_no_labels(self, empty_anim):
        assert empty_anim.elapsed_labels == []
        assert len(empty_anim.frames) == 0


class TestEncodeGif:
    def test_produces_valid_multiframe_gif(self):
        frames = _solid_frames(4)
        data = encode_gif(frames, 100.0)
        assert data[:6] == b"GIF89a"
        img = Image.open(io.BytesIO(data))
        assert getattr(img, "n_frames", 1) == 4

    def test_empty_raises(self):
        with pytest.raises(AnimationExportError):
            encode_gif([], 100.0)


class TestEncodeMp4:
    def test_produces_valid_mp4(self):
        data = encode_mp4(_solid_frames(3), 100.0)
        assert b"ftyp" in data[:64]
        assert len(data) > 0

    def test_frame_count_tracks_duration_exactly(self):
        # 60 fps timebase + error diffusion => round(n * dur / dt) video frames.
        n, dur = 4, 250.0
        data = encode_mp4(_solid_frames(n), dur)
        assert _mp4_frame_count(data) == round(n * dur / _MP4_DT_MS)

    def test_odd_dimensions_are_padded(self):
        # 47x31 is odd on both axes; yuv420p requires even dims, so the encoder
        # must pad rather than crash.
        odd = [_png((200, 0, 0), size=(47, 31)), _png((0, 200, 0), size=(47, 31))]
        data = encode_mp4(odd, 100.0)
        assert b"ftyp" in data[:64]

    def test_empty_raises(self):
        with pytest.raises(AnimationExportError):
            encode_mp4([], 100.0)


class TestExportAnimationValidation:
    def test_unknown_format_raises_valueerror(self, anim_fig):
        with pytest.raises(ValueError):
            export_animation(anim_fig, fmt="webm", frame_duration_ms=50.0)

    def test_no_frames_raises_export_error(self, empty_anim):
        assert len(empty_anim.frames) == 0
        with pytest.raises(AnimationExportError):
            export_animation(empty_anim, fmt="mp4", frame_duration_ms=50.0)


class TestDownsampleDurationPreserved:
    """Downsampling renders fewer frames but holds each longer, so total runtime
    is unchanged. This tests the orchestration math with the renderer stubbed."""

    def test_runtime_preserved_when_capped(self, monkeypatch, anim_fig):
        captured = {}

        def fake_render(
            anim, *, scale, show_elapsed, frame_indices, progress_callback=None
        ):
            return [_png((0, 0, 0))] * len(frame_indices), (48, 32)

        def fake_gif(pngs, duration_ms, **kwargs):
            captured["n"] = len(pngs)
            captured["dur"] = duration_ms
            return b"GIF89a-stub"

        monkeypatch.setattr(ae, "render_png_frames", fake_render)
        monkeypatch.setattr(ae, "encode_gif", fake_gif)

        n = len(anim_fig.frames)
        assert n >= 2
        cap = max(2, n // 2)
        export_animation(anim_fig, fmt="gif", frame_duration_ms=40.0, max_frames=cap)

        assert captured["n"] <= cap
        # n_selected * scaled_duration == original n * original duration
        assert captured["n"] * captured["dur"] == pytest.approx(n * 40.0)

    def test_no_cap_keeps_duration(self, monkeypatch, anim_fig):
        captured = {}

        def fake_render(
            anim, *, scale, show_elapsed, frame_indices, progress_callback=None
        ):
            return [_png((1, 2, 3))] * len(frame_indices), (48, 32)

        monkeypatch.setattr(ae, "render_png_frames", fake_render)
        monkeypatch.setattr(
            ae,
            "encode_mp4",
            lambda pngs, dur: captured.update(n=len(pngs), dur=dur) or b"ftyp-stub",
        )

        n = len(anim_fig.frames)
        export_animation(anim_fig, fmt="mp4", frame_duration_ms=33.0)
        assert captured["n"] == n
        assert captured["dur"] == pytest.approx(33.0)


class TestEndToEnd:
    """Real in-process matplotlib render — no browser, so it always runs."""

    def test_mp4_end_to_end(self, anim_fig):
        data = export_animation(anim_fig, fmt="mp4", frame_duration_ms=60.0, scale=0.5)
        assert b"ftyp" in data[:64]
        count = _mp4_frame_count(data)
        assert count >= len(anim_fig.frames)

    def test_gif_end_to_end(self, anim_fig):
        data = export_animation(anim_fig, fmt="gif", frame_duration_ms=60.0, scale=0.5)
        assert data[:6] in (b"GIF87a", b"GIF89a")
        img = Image.open(io.BytesIO(data))
        assert getattr(img, "n_frames", 1) == len(anim_fig.frames)

    def test_runtime_matches_quoted_playback(
        self, normalized_words_df, normalized_fixations_df
    ):
        # The clip's runtime must equal the playback time the tab quotes, so it
        # must be exported with that same per-frame duration (not the helper's).
        speed = 1.0
        anim = make_scanpath_animation(
            normalized_words_df,
            normalized_fixations_df,
            canvas_width=800,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            playback_speed=speed,
        )
        n = len(anim.frames)
        _span, playback_ms = animation_playback_ms([normalized_fixations_df], speed)
        frame_ms = playback_ms / n
        data = export_animation(anim, fmt="mp4", frame_duration_ms=frame_ms, scale=0.5)
        # 60 fps timebase + error diffusion => round(total playback / dt) frames.
        expected_video_frames = round(n * frame_ms / _MP4_DT_MS)
        count = _mp4_frame_count(data)
        assert count == expected_video_frames
