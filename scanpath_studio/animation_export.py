"""Render a Plotly scanpath animation to a shareable GIF or MP4 clip.

The **Animate** toggle (in the Scanpath Visualization control rail) builds a Plotly
``go.Figure`` with one frame per fixation onset (see
:func:`scanpath_studio.plots.make_scanpath_animation`). The
interactive **HTML** export keeps that figure verbatim — play button, slider and
all. This module is the non-interactive counterpart: it rasterizes the very same
frames and encodes them into a GIF or MP4 you can drop into a slide deck, a paper,
or a chat without needing a browser to replay it.

How it stays faithful to what the user sees on screen:

* **Same frames.** Each ``go.Frame`` is applied onto a frameless copy of the base
  figure and rendered to PNG, so word boxes, true-to-scale labels, saccades,
  order numbers and the orange current-fixation highlight all match the live view.
* **Same clock.** The on-screen Play button advances every frame at one average
  duration (``plots._anim_timeline``); we reproduce that exactly, so the clip's
  runtime equals the playback time quoted on screen (``animation_playback_ms``).
* **Same readout.** The slider's "Elapsed: X.Xs" value is re-drawn as a static
  annotation per frame, since the interactive slider can't survive rasterization.

Rendering goes through Kaleido (headless Chrome), the same engine the PNG/SVG/PDF
exports use. A *single* browser is kept warm across all frames
(``start_sync_server`` → ``calc_fig_sync`` → ``stop_sync_server``): the per-call
``fig.to_image`` cold-starts Chrome every time (~10 s/frame), whereas a warm
browser renders each frame in a fraction of a second.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Iterable
from time import perf_counter

import numpy as np
import plotly.graph_objects as go

from .export_status import ExportStage, StatusCallback, emit_status

# The interactive formats live elsewhere; these are the rasterized clip formats.
VIDEO_FORMATS: tuple[str, ...] = ("gif", "mp4")

# SEC1 (BUG-74): a GIF's cost grows with its raster pixels — every frame is
# decoded, palette-quantized and written whole (``disposal=2`` stores full frames,
# not deltas), and the finished file is held in memory for the download. The
# encoder streams since BUG-74, so a frame no longer costs its decoded size for the
# whole encode, but the rendered PNGs and the output still scale with
# frames × width × height × scale². So a GIF over this budget is refused before
# Kaleido starts. A server other machines can reach gets the lower figure: it is
# shared, and one visitor's 2000-frame, 2× clip is everyone's outage. Locally the
# budget only catches the absurd — the rail's own ceiling (2000 frames at 2× of a
# display-capped figure, ~6 Gpx) fits under it. MP4 is not budgeted: its frames go
# straight through ffmpeg and H.264 keeps the file small, which is also why the
# refusal points at it.
GIF_PIXEL_BUDGET_LOCAL = 8_000_000_000
GIF_PIXEL_BUDGET_HOSTED = 800_000_000

_MIME = {"gif": "image/gif", "mp4": "video/mp4"}

# make_scanpath_animation reserves this many px of top margin for the play/slider
# controls. With the controls stripped we reclaim it down to a slim band that
# still fits the "Elapsed" annotation.
_CONTROL_BAND_PX = 80
_STATIC_TOP_MARGIN_PX = 28

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

    The most common cause is a missing Chrome/Chromium for Kaleido; the message
    is surfaced to the user with a hint to fall back to the HTML export.
    """


class AnimationBudgetError(AnimationExportError):
    """The requested GIF is over this server's pixel budget (SEC1 / BUG-74).

    Raised before anything is rendered. A subclass so a caller that already
    handles :class:`AnimationExportError` keeps working, and one that wants to can
    tell "too big" apart from "Chrome is missing" — the message says what to change,
    and the browser-install hint would be the wrong advice.
    """


# Actionable remediation when Kaleido can't find a Chrome/Chromium binary — the
# usual cause of a failed GIF/MP4 (or static PNG/SVG/PDF) export (ENG-10).
# BUG-85: worded for both installs. The frozen desktop bundle has no
# `kaleido_get_chrome` / `plotly_get_chrome` and no Python prompt, but
# `chromium_browser_path` finds an installed Chrome, Chromium or Edge there too.
CHROME_INSTALL_HINT = (
    "Image export needs Chrome, Chromium or Edge, and none was found. Install one "
    "of them and try again — a pip install can instead run `plotly_get_chrome -y`. "
    "The **HTML** export needs no browser."
)


def chromium_browser_path() -> str | None:
    """Return the browser path Kaleido would use, without launching it.

    ``Chromium.find_browser`` is Choreographer's complete discovery path: it
    honours ``BROWSER_PATH``, searches ``PATH``, checks platform-specific
    locations for Chrome, Chromium, Edge, Brave, and Vivaldi, and can fall back
    to Choreographer's managed Chrome download. We prefer a system browser: a
    stale managed download must not shadow a working installed Edge/Chrome.

    Passing the browser-info mapping to ``get_browser_path`` only searches for
    the mapping's *keys* (``chrome``, ``edge``, …), which misses both managed
    downloads and standard macOS app locations.
    """
    try:
        from choreographer.browsers.chromium import Chromium
    except Exception:
        return None
    for skip_local in (True, False):
        try:
            path = Chromium.find_browser(skip_local=skip_local)
        except Exception:
            continue
        if path:
            return str(path)
    return None


def chrome_available() -> bool:
    """Whether Kaleido can find a compatible Chromium-family browser."""
    return chromium_browser_path() is not None


def mime_for(fmt: str) -> str:
    return _MIME[fmt.lower()]


def _elapsed_labels(fig: go.Figure, n_frames: int) -> list[str]:
    """Per-frame "elapsed reading time" labels, lifted from the slider steps.

    ``_animation_time_slider`` already computes one ``"X.Xs"`` label per frame, so
    we reuse them verbatim rather than recomputing onsets. Falls back to blanks if
    the figure has no slider (e.g. an empty animation).
    """
    sliders = fig.layout.sliders
    if sliders and sliders[0].steps:
        labels = [step.label or "" for step in sliders[0].steps]
        if len(labels) >= n_frames:
            return list(labels[:n_frames])
        return list(labels) + [""] * (n_frames - len(labels))
    return [""] * n_frames


def _static_base(fig: go.Figure) -> go.Figure:
    """A frameless deep copy of ``fig`` with interactive controls removed.

    The play/pause/restart buttons and the slider are meaningless in a rasterized
    clip — and worse, they'd be burnt into every frame. ``update_layout`` can't
    clear array layout properties (passing ``None`` is a no-op and ``[]`` doesn't
    truncate the existing entries), so we assign the attributes directly. The
    reserved control band is then reclaimed so the clip isn't topped by an empty
    strip; a slim margin remains for the "Elapsed" annotation.
    """
    base = go.Figure(fig)
    base.frames = ()
    base.layout.updatemenus = []
    base.layout.sliders = []
    base.update_layout(
        margin=dict(l=0, r=0, t=_STATIC_TOP_MARGIN_PX, b=0),
        height=_static_height(fig),
    )
    return base


def _static_height(fig: go.Figure) -> int:
    """The rasterized clip's height: the figure's, less the reclaimed control band.

    Its own function so the pixel budget can size a clip without deep-copying
    the figure (and every one of its frames) the way :func:`_static_base` must.
    """
    height = int(fig.layout.height or 600)
    return max(
        height - (_CONTROL_BAND_PX - _STATIC_TOP_MARGIN_PX), _STATIC_TOP_MARGIN_PX + 1
    )


def _served_to_other_machines() -> bool:
    """Whether this export runs inside a Streamlit server others can reach.

    Outside a Streamlit runtime (a script, the CLI) the caller is on their own
    machine. Inside one, the answer is the server's own bind address — never the
    URL the browser reports, which the browser controls (see
    ``persistence.server_bound_to_loopback``).
    """
    try:
        from streamlit import runtime
    except Exception:  # pragma: no cover - streamlit is a hard dependency
        return False
    if not runtime.exists():
        return False
    from .persistence import server_bound_to_loopback

    return not server_bound_to_loopback()


def check_gif_budget(
    n_frames: int, width: int, height: int, scale: float, *, budget: int | None = None
) -> None:
    """Refuse a GIF whose frames would exceed the pixel budget (SEC1 / BUG-74).

    ``width``/``height`` are the clip's pixels at 1×; Kaleido multiplies both by
    ``scale``. ``budget`` defaults to :data:`GIF_PIXEL_BUDGET_HOSTED` inside a
    server other machines can reach and :data:`GIF_PIXEL_BUDGET_LOCAL` anywhere
    else. Raises :class:`AnimationBudgetError` naming the ways back under — MP4,
    fewer frames, a lower resolution — with the frame count that would fit at
    this scale, so the message is something to act on.
    """
    shared = budget is None and _served_to_other_machines()
    if budget is None:
        budget = GIF_PIXEL_BUDGET_HOSTED if shared else GIF_PIXEL_BUDGET_LOCAL
    per_frame = max(round(width * scale), 1) * max(round(height * scale), 1)
    total = int(n_frames) * per_frame
    if total <= budget:
        return
    fits = int(budget) // per_frame
    shorter = f"cap it at {fits} frames or fewer, " if fits >= 1 else ""
    raise AnimationBudgetError(
        f"a {n_frames}-frame GIF at {width}×{height} px and {scale:g}× comes to "
        f"{total / 1e6:,.0f} megapixels of frames, over the "
        f"{budget / 1e6:,.0f}-megapixel limit for one GIF"
        f"{' on this shared server' if shared else ''}. Export **MP4** instead — "
        f"its frames stream straight to the encoder and the file stays small — or "
        f"{shorter}or lower the resolution."
    )


def _select_frames(n: int, max_frames: int | None) -> list[int]:
    """Indices of frames to render, evenly downsampled to ``max_frames``.

    Returns ``range(n)`` unchanged when no cap applies. Downsampling keeps the
    first and last frames (so the clip still starts empty and ends on the full
    scanpath) and spreads the rest evenly; callers scale the frame duration by
    ``n / len(selected)`` to preserve the overall runtime.
    """
    if max_frames is None or max_frames <= 0 or n <= max_frames:
        return list(range(n))
    return sorted({round(i) for i in np.linspace(0, n - 1, max_frames)})


def render_png_frames(
    fig: go.Figure,
    *,
    scale: float = 1.0,
    show_elapsed: bool = True,
    frame_indices: list[int] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[bytes], tuple[int, int]]:
    """Rasterize the animation's frames to PNG bytes via one persistent Kaleido browser.

    Returns ``(png_bytes_per_frame, (width, height))``. ``frame_indices`` selects a
    subset (for downsampling); defaults to every frame. ``progress_callback`` is
    called ``(done, total)`` after each frame so the UI can drive a progress bar.

    Raises :class:`AnimationExportError` if the figure has no frames, Kaleido is
    missing, the browser won't start, or a frame fails to render (e.g. no Chrome).
    """
    try:
        import kaleido
    except Exception as exc:  # pragma: no cover - import guard
        raise AnimationExportError(
            "Kaleido is not installed, so the animation can't be rasterized to "
            "GIF/MP4. Use the HTML export instead, or `pip install kaleido`."
        ) from exc

    frames = list(fig.frames or ())
    if not frames:
        raise AnimationExportError("This animation has no frames to export.")

    indices = frame_indices if frame_indices is not None else list(range(len(frames)))
    base = _static_base(fig)
    width = int(fig.layout.width or 900)
    height = int(base.layout.height)
    elapsed = _elapsed_labels(fig, len(frames)) if show_elapsed else None

    # A single warm browser renders every frame fast; if it won't start, fall back
    # to per-frame cold `to_image` (slow, ~10 s/frame) ONLY when Chrome is actually
    # present (a transient/port/profile issue), mirroring export._figure_renderer.
    # When Chrome is genuinely missing, abort early with the actionable hint.
    cold_fallback = False
    browser_path = chromium_browser_path()
    if browser_path is None:
        raise AnimationExportError(CHROME_INSTALL_HINT)
    try:
        kaleido.start_sync_server(path=browser_path, silence_warnings=True)
    except Exception:
        cold_fallback = True

    pngs: list[bytes] = []
    try:
        for done, k in enumerate(indices, start=1):
            frame = frames[k]
            for data_obj, trace_idx in zip(frame.data, frame.traces):
                base.data[trace_idx].update(data_obj)
            if elapsed is not None:
                base.update_layout(
                    annotations=[
                        dict(
                            text=f"Elapsed: {elapsed[k]}",
                            x=0.99,
                            y=1.0,
                            xref="paper",
                            yref="paper",
                            xanchor="right",
                            yanchor="bottom",
                            showarrow=False,
                            font=dict(size=14, color="#444"),
                        )
                    ]
                )
            try:
                if cold_fallback:
                    png = base.to_image(
                        format="png", width=width, height=height, scale=scale
                    )
                else:
                    png = kaleido.calc_fig_sync(
                        base,
                        opts={
                            "format": "png",
                            "width": width,
                            "height": height,
                            "scale": scale,
                        },
                    )
            except Exception as exc:
                raise AnimationExportError(
                    CHROME_INSTALL_HINT
                    if not chrome_available()
                    else f"Rendering frame {k + 1}/{len(frames)} failed: {exc}."
                ) from exc
            pngs.append(bytes(png))
            if progress_callback is not None:
                progress_callback(done, len(indices))
    finally:
        if not cold_fallback:
            try:
                kaleido.stop_sync_server(silence_warnings=True)
            except Exception:  # pragma: no cover - best-effort teardown
                pass

    return pngs, (width, height)


def _load_rgb_frames(pngs: list[bytes]) -> list[np.ndarray]:
    from PIL import Image

    return [np.asarray(Image.open(io.BytesIO(b)).convert("RGB")) for b in pngs]


def encode_gif(
    pngs: Iterable[bytes], frame_duration_ms: float, *, loop: int = 0
) -> bytes:
    """Encode PNG frames into an animated GIF with a uniform per-frame delay.

    **Streams** (SEC1 / BUG-74): each PNG is decoded, quantized to a 256-colour
    palette and written before the next is read, so memory holds one decoded frame
    and one palette frame, not the whole clip. Pillow's ``save(save_all=True)``
    cannot do that — it keeps every normalized frame until the end to diff them —
    and handing it the decoded list on top cost ~10 MB per frame at 2× (measured
    ~4.6 GB for the default 250-frame cap at a large figure). The bytes written
    are Pillow's own multi-frame layout for this input: the global header comes
    from frame one, every later frame carries its own palette, each is stored
    whole (``disposal=2`` with no transparency never crops to a delta), and a frame
    identical to the one before it is folded into it with the durations summed —
    which is why this holds one frame back before writing it.
    """
    from PIL import GifImagePlugin, Image, ImageChops

    duration = max(round(frame_duration_ms), _GIF_MIN_FRAME_MS)
    buf = io.BytesIO()
    pending: Image.Image | None = None
    pending_ms = 0
    wrote_header = False

    def _flush() -> None:
        nonlocal wrote_header
        info = {"duration": pending_ms, "disposal": 2, "loop": loop, "optimize": True}
        if not wrote_header:
            # `getheader` also normalizes the palette in place, so the frame and
            # the global colour table it writes agree.
            header, _used = GifImagePlugin.getheader(pending, info=dict(info))
            buf.write(b"".join(header))
            wrote_header = True
        else:
            info["include_color_table"] = True
        buf.write(b"".join(GifImagePlugin.getdata(pending, (0, 0), **info)))

    for png in pngs:
        with Image.open(io.BytesIO(png)) as decoded:
            frame = decoded.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE)
        if pending is not None:
            same = pending.getpalette() == frame.getpalette() and (
                ImageChops.subtract_modulo(frame, pending).getbbox() is None
            )
            if same:
                pending_ms += duration
                continue
            _flush()
        pending, pending_ms = frame, duration
    if pending is None:
        raise AnimationExportError("No frames to encode.")
    _flush()
    buf.write(b";")
    return buf.getvalue()


def encode_mp4(pngs: list[bytes], frame_duration_ms: float) -> bytes:
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

    # Deliberately not a context manager: `delete=False` plus an immediate
    # close is how you reserve a path for ffmpeg to write. A `with` block
    # would delete the file before the encoder ever opened it.
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
                target_total = round((i + 1) * frame_duration_ms / dt_ms)
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
    fig: go.Figure,
    *,
    fmt: str,
    frame_duration_ms: float,
    scale: float = 1.0,
    show_elapsed: bool = True,
    max_frames: int | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> bytes:
    """Render a scanpath-animation figure to GIF or MP4 bytes.

    Args:
        fig: the figure from :func:`make_scanpath_animation` (must have ``.frames``).
        fmt: ``"gif"`` or ``"mp4"``.
        frame_duration_ms: uniform per-frame duration — pass the same average the
            tab quotes (``animation_playback_ms(...) / n_frames``) so the clip's
            runtime matches the on-screen Play.
        scale: Kaleido render scale (1.0 = on-screen px; <1 is faster/smaller,
            >1 is crisper/larger).
        show_elapsed: draw the "Elapsed: X.Xs" readout in the top margin.
        max_frames: cap the number of rendered frames by even downsampling; the
            frame duration is scaled up to keep the total runtime unchanged. The
            UI uses this to bound render time on very long trials.
        progress_callback: ``(done, total)`` after each rendered frame.

    Raises:
        ValueError: unknown ``fmt``.
        AnimationBudgetError: a GIF over :func:`check_gif_budget`'s pixel budget,
            raised before any frame is rendered.
        AnimationExportError: rendering or encoding failed.
    """
    started = perf_counter()
    fmt = fmt.lower()
    if fmt not in VIDEO_FORMATS:
        raise ValueError(
            f"Unsupported format {fmt!r}; expected one of {VIDEO_FORMATS}."
        )

    n_total = len(fig.frames or ())
    indices = _select_frames(n_total, max_frames)
    # Preserve total runtime when downsampling: fewer frames, each held longer.
    effective_duration = frame_duration_ms
    if indices and len(indices) < n_total:
        effective_duration = frame_duration_ms * n_total / len(indices)

    emit_status(
        status_callback,
        ExportStage.PREPARING,
        f"Preparing {len(indices)} animation frames…",
        started_at=started,
    )
    try:
        if fmt == "gif" and indices:
            # SEC1: refuse before Chrome starts, not after the frames are made.
            check_gif_budget(
                len(indices), int(fig.layout.width or 900), _static_height(fig), scale
            )
        emit_status(
            status_callback,
            ExportStage.STARTING_RENDERER,
            "Starting one shared Chrome/Kaleido renderer…",
            started_at=started,
        )

        def _on_frame(done: int, total: int) -> None:
            if progress_callback is not None:
                progress_callback(done, total)
            emit_status(
                status_callback,
                ExportStage.RASTERIZING,
                f"Rendered frame {done}/{total}…",
                started_at=started,
                completed=done,
                total=total,
            )

        pngs, _size = render_png_frames(
            fig,
            scale=scale,
            show_elapsed=show_elapsed,
            frame_indices=indices,
            progress_callback=_on_frame,
        )
        emit_status(
            status_callback,
            ExportStage.ENCODING_WRITING,
            f"Encoding {fmt.upper()}…",
            started_at=started,
        )
        result = (
            encode_gif(pngs, effective_duration)
            if fmt == "gif"
            else encode_mp4(pngs, effective_duration)
        )
        emit_status(
            status_callback,
            ExportStage.FINALIZING,
            "Finalizing animation bytes…",
            started_at=started,
        )
        result = bytes(result)
        emit_status(
            status_callback,
            ExportStage.READY,
            "Animation is ready to download.",
            started_at=started,
            completed=len(indices),
            total=len(indices),
        )
        return result
    except Exception as exc:
        emit_status(
            status_callback,
            ExportStage.ERROR,
            "Animation export failed.",
            started_at=started,
            error=str(exc),
        )
        raise
