"""Physical print dimensions and reusable color scales for a two-panel comparison."""

from __future__ import annotations

import math
import re
from copy import deepcopy


def describe(figure, width_mm: float) -> dict:
    """Measure the existing layout after uniform scaling to the total print width."""
    if not math.isfinite(width_mm) or not 1 <= width_mm <= 2000:
        raise ValueError("Choose a total print width between 1 and 2000 mm.")
    panels = (figure.layout.meta or {}).get("scanpath_panels")
    if not panels:
        raise ValueError(
            "Choose a side-by-side or stacked comparison to proof two panels."
        )
    if tuple(panels["canvases"][0]) != tuple(panels["canvases"][1]):
        raise ValueError(
            "The two panels need matching screen dimensions for a shared print proof."
        )
    width, height = round(figure.layout.width), round(figure.layout.height)
    factor = (width_mm / 25.4) * 72 / width
    font_sizes = {}
    for trace in figure.data:
        if "text" not in (getattr(trace, "mode", "") or ""):
            continue
        if trace.name != "words" and trace.mode == "text" and trace.hoverinfo != "skip":
            continue  # A heart marker is drawn as a text glyph.
        size = trace.textfont.size
        if not isinstance(size, (int, float)) or not size:
            continue
        name = "Stimulus words" if trace.name == "words" else "Fixation labels"
        font_sizes.setdefault(name, set()).add(round(size * factor, 2))
    for annotation in figure.layout.annotations[:2]:
        size = annotation.font.size or figure.layout.font.size or 12
        font_sizes.setdefault("Panel headings", set()).add(round(size * factor, 2))
    if figure.layout.showlegend is not False and any(t.showlegend for t in figure.data):
        size = figure.layout.legend.font.size or figure.layout.font.size or 12
        font_sizes["Legend"] = {round(size * factor, 2)}
    return {
        **panels,
        "width_mm": width_mm,
        "height_mm": width_mm * height / width,
        "label_points": {k: sorted(v) for k, v in font_sizes.items()},
    }


def settings(config: dict, proof: dict, *, keep_limits: bool) -> dict:
    """Use the standard restorable settings format for both panel order and print width."""
    out = deepcopy(config)
    out.setdefault("export", {}).update(width=proof["width_mm"], unit="mm")
    for key in ("fixation_range", "heatmap_range"):
        value = proof.get(key)
        out["coloring"][key] = (
            list(value) if keep_limits and value is not None else None
        )
    return out


def svg(figure, width_mm: float) -> bytes:
    """Render the comparison once and give the vector its physical viewport."""
    from .export import render_static_figure_bytes

    proof = describe(figure, width_mm)
    payload = render_static_figure_bytes(
        figure,
        fmt="svg",
        width=round(figure.layout.width),
        height=round(figure.layout.height),
        scale=1,
    )
    return size_svg(
        payload,
        round(figure.layout.width),
        round(figure.layout.height),
        proof["width_mm"],
    )


def size_svg(payload: bytes, width: int, height: int, width_mm: float) -> bytes:
    """Keep native vector coordinates and set their physical dimensions."""
    proof = {"width_mm": width_mm, "height_mm": width_mm * height / width}
    root = re.search(rb"<svg\b[^>]*>", payload)
    if root is None:
        raise ValueError("The renderer did not return an SVG document.")
    tag = root.group()
    for dimension in ("width", "height"):
        value = f"{proof[dimension + '_mm']:.8g}mm".encode("ascii")
        tag = re.sub(
            rb"\s" + dimension.encode() + rb'="[^"]*"',
            b" " + dimension.encode() + b'="' + value + b'"',
            tag,
            count=1,
        )
    if b"viewBox=" not in tag:
        tag = tag[:-1] + f' viewBox="0 0 {width} {height}">'.encode("ascii")
    return payload[: root.start()] + tag + payload[root.end() :]
