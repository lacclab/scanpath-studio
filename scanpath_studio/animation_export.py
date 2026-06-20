"""Render a scanpath animation to a shareable GIF or MP4 clip.

The **Animate** toggle (in the Scanpath Visualization control rail) builds a
:class:`scanpath_studio.plots.ScanpathAnimation` with one frame per fixation onset.
The interactive **HTML** export embeds its ``to_jshtml`` player. This module is the
non-interactive counterpart: it rasterizes the very same frames and encodes them
into a GIF or MP4 you can drop into a slide deck, a paper, or a chat.

How it stays faithful to what the user sees on screen:

* **Same frames.** Each frame is drawn by ``anim.draw_frame(k)`` (the exact closure
  the on-screen player uses) and saved to PNG, so word boxes, true-to-scale labels,
  saccades, order numbers and the orange current-fixation highlight all match.
* **Same clock.** The player advances every frame at one average duration
  (``plots._anim_timeline``); we reproduce that exactly, so the clip's runtime
  equals the playback time quoted on screen (``animation_playback_ms``).
* **Same readout.** The "Elapsed: X.Xs" readout is part of the animation figure and
  updates per frame, so it rasterizes for free.

Rendering is fully in-process — matplotlib ``savefig`` per frame, no headless
browser — so it's fast and needs no Chrome/Chromium. Only the encode half differs
by format: Pillow for GIF, imageio-ffmpeg for MP4 (which still needs an ffmpeg
binary, bundled via the ``imageio[ffmpeg]`` extra).
"""

from __future__ import annotations

import io
from typing import Callable, List, Optional, Tuple

import numpy as np

from . import mpl_render as mr

# The interactive formats live elsewhere; these are the rasterized clip formats.
VIDEO_FORMATS: Tuple[str, ...] = ("gif", "mp4")

_MIME = {"gif": "image/gif", "mp4": "video/mp4"}

# Floor on a GIF frame delay: the format stores delays in centiseconds and many
# viewers silently promote sub-20 ms delays to ~100 ms, so clamp here to keep
# fast playback honest. MP4 has no such quirk.
_GIF_MIN_FRAME_MS = 20
# MP4 plays at one constant rate, but animation frames have durations spanning
# ~16 ms (fast/×8 playback) to several hundred ms (slow/×0.25, or downsampled long
# trials). We encode at a fixed, universally-playable rate and hold each animation
# frame for the right number of video frames (repeats compress to ~nothing in
# H.264), so the clip's runtime tracks the on-screen Play across that whole range.
_MP4_FPS = 60.0

ProgressCallback = Callable[[int, int], None]


class AnimationExportError(RuntimeError):
    """Frame rendering or encoding failed.

    For MP4 the usual cause is a missing ffmpeg binary; the message is surfaced to
    the user with a hint to fall back to GIF or the HTML export.
    """


def mime_for(fmt: str) -> str:
    return _MIME[fmt.lower()]


def _select_frames(n: int, max_frames: Optional[int]) -> List[int]:
    """Indices of frames to render, evenly downsampled to ``max_frames``.

    Returns ``range(n)`` unchanged when no cap applies. Downsampling keeps the
    first and last frames (so the clip still starts empty and ends on the full
    scanpath) and spreads the rest evenly; callers scale the frame duration by
    ``n / len(selected)`` to preserve the overall runtime.
    """
    if max_frames is None or max_frames <= 0 or n <= max_frames:
        return list(range(n))
    return sorted(set(int(round(i)) for i in np.linspace(0, n - 1, max_frames)))


def render_png_frames(
    anim,
    *,
    scale: float = 1.0,
    show_elapsed: bool = True,
    frame_indices: Optional[List[int]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Tuple[List[bytes], Tuple[int, int]]:
    """Rasterize the animation's frames to PNG bytes with matplotlib (no browser).

    ``anim`` is a :class:`scanpath_studio.plots.ScanpathAnimation`. Each frame is
    drawn by ``anim.draw_frame(k)`` and saved at the figure's pixel size × ``scale``
    (a retina/poster multiplier). Returns ``(png_bytes_per_frame, (width, height))``;
    ``frame_indices`` selects a subset (for downsampling). ``progress_callback`` is
    called ``(done, total)`` after each frame. The "Elapsed" readout is part of the
    figure and rasterizes for free.

    Raises :class:`AnimationExportError` if the animation has no frames.
    """
    frames = list(anim.frames or [])
    if not frames:
        raise AnimationExportError("This animation has no frames to export.")

    indices = frame_indices if frame_indices is not None else list(range(len(frames)))
    fig = anim.figure
    base_w, base_h = mr.figure_px_size(fig)
    out_w = int(round(base_w * scale))
    out_h = int(round(base_h * scale))

    pngs: List[bytes] = []
    for done, k in enumerate(indices, start=1):
        anim.draw_frame(k)
        try:
            pngs.append(mr.save_to_buffer(fig, "png", scale=scale))
        except Exception as exc:  # pragma: no cover - render guard
            raise AnimationExportError(
                f"Rendering frame {k + 1}/{len(frames)} failed: {exc}."
            ) from exc
        if progress_callback is not None:
            progress_callback(done, len(indices))

    return pngs, (out_w, out_h)


def _load_rgb_frames(pngs: List[bytes]) -> List["np.ndarray"]:
    from PIL import Image

    return [np.asarray(Image.open(io.BytesIO(b)).convert("RGB")) for b in pngs]


def encode_gif(pngs: List[bytes], frame_duration_ms: float, *, loop: int = 0) -> bytes:
    """Encode PNG frames into an animated GIF with a uniform per-frame delay."""
    from PIL import Image

    if not pngs:
        raise AnimationExportError("No frames to encode.")
    imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in pngs]
    duration = max(int(round(frame_duration_ms)), _GIF_MIN_FRAME_MS)
    buf = io.BytesIO()
    imgs[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=loop,
        disposal=2,
        optimize=True,
    )
    return buf.getvalue()


def encode_mp4(pngs: List[bytes], frame_duration_ms: float) -> bytes:
    """Encode PNG frames into an H.264 MP4 whose runtime matches the on-screen Play.

    The on-screen Play shows every frame for ``frame_duration_ms``. An MP4 plays at
    one constant rate, so we encode at a fixed 60 fps and hold each animation frame
    for ``round(frame_duration_ms / (1000/60))`` video frames (at least one). That
    reproduces durations from ~16 ms to several hundred ms accurately — the repeated
    frames are identical, so H.264 compresses them to near-nothing. Frames stream
    through the writer one at a time (repeats reuse the same array), so memory stays
    flat regardless of clip length. H.264 ``yuv420p`` needs even dimensions, so each
    frame is edge-padded to even width/height.
    """
    import os
    import tempfile

    import imageio

    if not pngs:
        raise AnimationExportError("No frames to encode.")

    dt_ms = 1000.0 / _MP4_FPS

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    try:
        writer = imageio.get_writer(
            tmp.name,
            format="FFMPEG",
            mode="I",
            fps=_MP4_FPS,
            codec="libx264",
            pixelformat="yuv420p",
            macro_block_size=1,
        )
        try:
            pad = None
            # Error-diffuse the per-frame repeat count against the cumulative
            # target time so rounding never accumulates into runtime drift: the
            # clip lands on round(n * frame_duration / dt) video frames exactly.
            emitted = 0
            for i, b in enumerate(pngs):
                arr = _load_rgb_frames([b])[0]
                if pad is None:
                    h, w = arr.shape[:2]
                    pad = (h % 2, w % 2)
                if pad[0] or pad[1]:
                    arr = np.pad(arr, ((0, pad[0]), (0, pad[1]), (0, 0)), mode="edge")
                target_total = int(round((i + 1) * frame_duration_ms / dt_ms))
                reps = max(1, target_total - emitted)
                emitted += reps
                for _ in range(reps):
                    writer.append_data(arr)
        finally:
            writer.close()
        with open(tmp.name, "rb") as fh:
            return fh.read()
    except AnimationExportError:
        raise
    except Exception as exc:
        raise AnimationExportError(
            f"MP4 encoding failed: {exc}. Try the GIF format, or check that "
            "imageio-ffmpeg is installed."
        ) from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:  # pragma: no cover - best-effort cleanup
            pass


def export_animation(
    anim,
    *,
    fmt: str,
    frame_duration_ms: float,
    scale: float = 1.0,
    show_elapsed: bool = True,
    max_frames: Optional[int] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> bytes:
    """Render a scanpath animation to GIF or MP4 bytes.

    Args:
        anim: a :class:`scanpath_studio.plots.ScanpathAnimation` (must have frames).
        fmt: ``"gif"`` or ``"mp4"``.
        frame_duration_ms: uniform per-frame duration — pass the same average the
            tab quotes (``animation_playback_ms(...) / n_frames``) so the clip's
            runtime matches the on-screen Play.
        scale: render scale (1.0 = on-screen px; <1 is faster/smaller, >1 crisper).
        show_elapsed: accepted for API compatibility; the readout is drawn by the
            animation figure itself.
        max_frames: cap the number of rendered frames by even downsampling; the
            frame duration is scaled up to keep the total runtime unchanged.
        progress_callback: ``(done, total)`` after each rendered frame.

    Raises:
        ValueError: unknown ``fmt``.
        AnimationExportError: rendering or encoding failed.
    """
    fmt = fmt.lower()
    if fmt not in VIDEO_FORMATS:
        raise ValueError(
            f"Unsupported format {fmt!r}; expected one of {VIDEO_FORMATS}."
        )

    n_total = len(anim.frames or [])
    indices = _select_frames(n_total, max_frames)
    # Preserve total runtime when downsampling: fewer frames, each held longer.
    effective_duration = frame_duration_ms
    if indices and len(indices) < n_total:
        effective_duration = frame_duration_ms * n_total / len(indices)

    pngs, _size = render_png_frames(
        anim,
        scale=scale,
        show_elapsed=show_elapsed,
        frame_indices=indices,
        progress_callback=progress_callback,
    )
    if fmt == "gif":
        return encode_gif(pngs, effective_duration)
    return encode_mp4(pngs, effective_duration)
