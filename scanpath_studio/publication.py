"""Portable publication figures. The app, offline editor and CLI use one renderer."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import math
import sys
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import plotly.io as pio

from . import file_citation
from .citation import file_metadata

SCHEMA = "scanpath-studio/publication/1"
FORMATS = (".html", ".json", ".svg", ".pdf", ".png", ".tiff", ".mp4")
PRESETS = {
    "Paper column": 85,
    "Full-width paper": 170,
    "Full slide": 338.666667,
    "Half slide": 169.333333,
}


def source(
    figure,
    title: str,
    *,
    description: str = "",
    kind: str = "chart",
    settings=None,
    references=(),
) -> dict:
    """Capture the figure as drawn, including its axes, reading clock and disclosures."""
    raw = pio.to_json(figure, validate=False, remove_uids=False, engine="json")
    content = json.loads(raw)
    from .plots import replay_page_box

    _, page_height, toolbar = replay_page_box(content)
    entry = dict(title=title, description=description, kind=kind, figure=content)
    if references:
        entry["references"] = list(references)
    if toolbar:
        entry["transport"] = content["layout"]["height"] - page_height
    if settings is not None:
        entry["settings"] = settings
    identity = json.dumps(
        {
            **entry,
            "settings": {
                k: v
                for k, v in (settings or {}).items()
                if k not in {"exported_at", "export"}
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    entry["id"] = hashlib.sha256(
        identity.encode("utf-8", errors="backslashreplace")
    ).hexdigest()
    return entry


def new_panel(entry: dict) -> dict:
    return {"source": entry["id"], "title": entry["title"], "labels": []}


def project(sources, *, name="Untitled figure", width_mm=170, layout="stack") -> dict:
    """Create a publication project with one panel for each source."""
    sources = list(sources)
    doc = {
        "schema": SCHEMA,
        "name": name,
        "width": width_mm,
        "layout": layout,
        "destination": next(
            (k for k, v in PRESETS.items() if math.isclose(width_mm, v, abs_tol=0.001)),
            "Custom paper",
        ),
        "dpi": 300,
        "minimum": 6,
        "maxHeight": 230,
        "sources": list({s["id"]: s for s in sources}.values()),
        "panels": [new_panel(s) for s in sources],
        "caption": None,
        "alt": None,
        "captionPlacement": "Manuscript",
        "gap": 8,
        "citation": file_metadata(),
    }
    validate_project(doc)
    return doc


def _finite_number(value) -> bool:
    """A number the browser can represent as a finite JavaScript Number."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and abs(value) <= sys.float_info.max
    )


def _validate_figure_images(figure: dict) -> None:
    layout = figure.get("layout", {})
    if not isinstance(layout, dict) or not isinstance(layout.get("images", []), list):
        raise ValueError("The source figure has an invalid layout or image layer.")
    images = list(layout.get("images", []))
    for trace in figure["data"]:
        if not isinstance(trace, dict):
            raise ValueError("A source figure contains an invalid plot trace.")
        if trace.get("type") == "image":
            images.append(trace)
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("The source figure has an invalid image layer.")
        src = image.get("source")
        if (
            src
            and image.get("visible") not in (False, "legendonly")
            and (not isinstance(src, str) or src[:11].lower() != "data:image/")
        ):
            raise ValueError(
                "Embed the source image in the Plotly figure before exporting. "
                "An offline publication figure cannot load an image from a URL or file path."
            )


def validate_project(doc: dict) -> None:
    """Check a portable recipe before saving it or handing it to the editor."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError("Choose a Scanpath Studio publication recipe.")
    if not isinstance(doc.get("sources"), list) or not isinstance(
        doc.get("panels"), list
    ):
        raise ValueError("The recipe must contain its panel sources and layout.")
    citation = doc.get("citation")
    if not isinstance(citation, dict) or not all(
        isinstance(citation.get(key), str) and citation[key].strip()
        for key in ("Software", "Comment", "Source")
    ):
        raise ValueError("The publication recipe is missing its software citation.")

    bounds = {
        "width": (10, 1000),
        "dpi": (50, 1200),
        "minimum": (1, 72),
        "gap": (0, 100),
        "maxHeight": (10, 2000),
    }
    for key, (lo, hi) in bounds.items():
        value = doc.get(key)
        if not _finite_number(value) or not lo <= value <= hi:
            raise ValueError(f"Publication {key} must be between {lo} and {hi}.")
    if doc.get("layout") not in ("row", "stack", "grid"):
        raise ValueError("Select row, stack or grid for the panel layout.")
    heat = doc.get("heat")
    if heat is not None and (
        not isinstance(heat, dict)
        or not _finite_number(heat.get("min"))
        or not _finite_number(heat.get("max"))
        or not 0 <= heat["min"] < heat["max"]
        or not isinstance(heat.get("scale"), list)
        or len(heat["scale"]) < 2
        or any(
            not isinstance(stop, (list, tuple))
            or len(stop) != 2
            or not _finite_number(stop[0])
            or not 0 <= stop[0] <= 1
            or not isinstance(stop[1], str)
            for stop in heat["scale"]
        )
    ):
        raise ValueError("The saved heatmap scale has invalid limits or colors.")
    ids = set()
    for src in doc["sources"]:
        if (
            not isinstance(src, dict)
            or not isinstance(src.get("id"), str)
            or src["id"] in ids
            or not isinstance(src.get("figure"), dict)
            or not isinstance(src["figure"].get("data"), list)
        ):
            raise ValueError(
                "The recipe contains an invalid or duplicate figure source."
            )
        _validate_figure_images(src["figure"])
        ids.add(src["id"])
    for panel in doc["panels"]:
        if (
            not isinstance(panel, dict)
            or not isinstance(panel.get("source"), str)
            or panel["source"] not in ids
            or not isinstance(panel.get("labels"), list)
        ):
            raise ValueError(
                "The recipe contains a panel without a valid source or labels."
            )
        crop = panel.get("crop")
        if crop is not None and (
            not isinstance(crop, list)
            or len(crop) != 4
            or not all(map(_finite_number, crop))
            or min(crop[2:]) <= 0
        ):
            raise ValueError("The panel crop must have a position and a positive size.")
        for label in panel["labels"]:
            if (
                not isinstance(label, dict)
                or not isinstance(label.get("text"), str)
                or not all(_finite_number(label.get(k)) for k in ("x", "y", "dx", "dy"))
            ):
                raise ValueError("A pinned label has invalid text or coordinates.")
            segment = label.get("segment")
            if segment is not None and (
                not isinstance(segment, list)
                or len(segment) != 4
                or not all(map(_finite_number, segment))
            ):
                raise ValueError(
                    "A pinned saccade needs two finite endpoint positions."
                )


def editor_html(
    doc: dict,
    *,
    plotly_script: str | None = None,
    session: str = "",
    plot_id: str = "",
    import_id: str = "",
    batch: bool = False,
) -> str:
    """An offline editing document, or the same editor with the app's shared plotly.js."""
    from plotly.offline import get_plotlyjs

    from .replay_frames import FRAME_AT_JS

    validate_project(doc)
    root = files("scanpath_studio").joinpath("publication_assets")
    shell = root.joinpath("editor.html").read_text(encoding="utf-8")
    payload = json.dumps(
        {
            "project": doc,
            "session": session,
            "plotId": plot_id,
            "importId": import_id,
            "batch": batch,
        },
        allow_nan=False,
    ).replace("<", "\\u003c")
    return file_citation.stamp_html(
        shell.replace("<!--STYLE-->", root.joinpath("editor.css").read_text())
        .replace(
            "<!--PLOTLY-->",
            plotly_script
            if plotly_script is not None
            else "<script>" + get_plotlyjs() + "</script>",
        )
        .replace(
            "<!--EDITOR-->",
            "\n".join(
                [
                    FRAME_AT_JS,
                    *(
                        root.joinpath(name).read_text(encoding="utf-8")
                        for name in ("raster.js", "renderer.js", "editor.js")
                    ),
                ]
            ),
        )
        .replace("<!--INPUT-->", payload)
    )


async def _draw(doc: dict, fmt: str):
    """Draw in an isolated local Chromium tab at the same dimensions as the proof."""
    from choreographer import Browser

    from . import progress
    from .animation_export import CHROME_INSTALL_HINT, chromium_browser_path

    path = chromium_browser_path()
    if path is None:
        raise RuntimeError(CHROME_INSTALL_HINT)
    progress.report(detail="Starting the browser")
    async with Browser(path=path) as browser:
        tab = await browser.create_tab()
        progress.report(detail="Drawing the figure")

        async def command(method, params=None):
            reply = await tab.send_command(method, params)
            if "error" in reply:
                message = reply["error"].get("message", method)
                raise RuntimeError(f"Chromium could not render the figure: {message}")
            return reply["result"]

        # Keep imported figures offline, including Plotly image layers and fonts.
        await command("Network.enable")
        await command(
            "Network.setBlockedURLs",
            {"urls": ["http://*", "https://*", "file://*", "ftp://*"]},
        )
        tree = await command("Page.getFrameTree")
        frame = tree["frameTree"]["frame"]["id"]
        await command(
            "Page.setDocumentContent", {"frameId": frame, "html": editor_html(doc)}
        )

        async def evaluate(expr):
            result = await command(
                "Runtime.evaluate",
                {"expression": expr, "awaitPromise": True, "returnByValue": True},
            )
            if "exceptionDetails" in result:
                raise ValueError(
                    result["exceptionDetails"]
                    .get("exception", {})
                    .get("description", "Figure could not be rendered.")
                )
            return result["result"].get("value")

        await evaluate("window.publicationReady")
        if fmt == "pdf":
            progress.report(detail="Printing the PDF")
            await evaluate("publicationPrint()")
            result = await command(
                "Page.printToPDF",
                {
                    "preferCSSPageSize": True,
                    "printBackground": True,
                    "displayHeaderFooter": False,
                },
            )
            return base64.b64decode(result["data"])
        if fmt == "poster":
            return base64.b64decode(await evaluate("publicationPoster()"))
        if fmt == "mp4":
            # Draw at the encoder's actual fps; the poster and each video frame
            # share the same crop, panel positions and annotations.
            duration = await evaluate("publicationClipDuration()")
            count = max(1, math.ceil(duration * 24 / 1000))
            if count > 14400:
                raise ValueError("Select a clip of ten minutes or less.")
            with TemporaryDirectory() as directory:
                # Stream frames to ffmpeg instead of retaining every raster in memory.
                import imageio.v2 as imageio
                import numpy as np
                from PIL import Image

                from .file_citation import mp4_metadata_args

                target = Path(directory) / "clip.mp4"
                with imageio.get_writer(
                    target,
                    format="FFMPEG",
                    fps=24,
                    codec="libx264",
                    macro_block_size=1,
                    output_params=[
                        "-vf",
                        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                        *mp4_metadata_args(),
                    ],
                ) as writer:
                    size = None
                    for i in range(count):
                        progress.report(i, count, unit="frames")
                        raw = await evaluate(f"publicationMovieFrame({i * 1000 / 24})")
                        with Image.open(io.BytesIO(base64.b64decode(raw))) as im:
                            size = size or im.size
                            if im.size != size:
                                raise ValueError(
                                    f"The figure changed size at frame {i + 1} of "
                                    f"the clip ({im.size[0]}×{im.size[1]} px, not "
                                    f"{size[0]}×{size[1]} px). Set Caption placement "
                                    "to Keep separate and prepare the clip again."
                                )
                            writer.append_data(np.asarray(im.convert("RGB")))
                return target.read_bytes()
        return base64.b64decode(await evaluate(f"publicationBytes({json.dumps(fmt)})"))


def _render_local(doc: dict, fmt: str) -> bytes:
    # Notebook kernels already own the caller's event loop.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_draw(doc, fmt))
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as worker:
        return worker.submit(asyncio.run, _draw(doc, fmt)).result()


def render(doc: dict, fmt: str) -> bytes:
    """Return publication artwork, its data-bearing recipe, or the offline editor."""
    validate_project(doc)
    fmt = fmt.lower().lstrip(".")
    if "." + fmt not in FORMATS:
        raise ValueError(f"Unknown publication format {fmt!r}.")
    if fmt == "json":
        return json.dumps(doc, allow_nan=False).encode()
    if fmt == "html":
        return editor_html(doc).encode()
    result = _render_local(doc, fmt)
    return file_citation.stamp(result, fmt) if fmt == "pdf" else result


def replay_poster(doc: dict) -> bytes:
    """Draw the selected frame at the pixel dimensions used by the video encoder."""
    validate_project(doc)
    return _render_local(doc, "poster")


def save(doc: dict, path: str | Path) -> Path:
    """Atomically write a rendered publication project."""
    path = Path(path)
    data = render(doc, path.suffix)
    with TemporaryDirectory(dir=path.parent) as stage:
        target = Path(stage) / path.name
        target.write_bytes(data)
        target.replace(path)
    return path
