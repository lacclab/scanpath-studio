"""Lossless compression for the PNGs the browser draws for bulk export."""

from __future__ import annotations

import io
import struct
import zlib

_PNG = b"\x89PNG\r\n\x1a\n"
# Omit an all-opaque alpha channel only when the other chunks are independent
# of the color type. Preserve these chunks, including the citation, verbatim.
_METADATA = {b"iTXt", b"tEXt", b"zTXt", b"pHYs", b"sRGB", b"gAMA", b"cHRM", b"iCCP"}
# A single decoded RGBA surface at this size takes 64 MiB.
MAX_RGBA_PIXELS = 16 * 1024**2


def compact_png(data: bytes) -> bytes:
    """Re-encode an ordinary 8-bit browser PNG when the result is smaller."""
    if not data.startswith(_PNG + b"\0\0\0\rIHDR") or len(data) < 45:
        return data
    width, height, depth, color = struct.unpack_from(">IIBB", data, 16)
    if depth != 8 or color not in (2, 6) or width * height > MAX_RGBA_PIXELS:
        return data

    # IHDR ends at byte 33. Other PNG layouts (e.g. animated or carrying a
    # suggested background color) keep their original representation.
    offset = 33
    while data[offset + 4 : offset + 8] in _METADATA:
        offset += 12 + int.from_bytes(data[offset : offset + 4], "big")
    image_start = offset
    while data[offset + 4 : offset + 8] == b"IDAT":
        offset += 12 + int.from_bytes(data[offset : offset + 4], "big")
    if (
        offset == image_start
        or offset + 12 != len(data)
        or data[offset + 4 : offset + 8] != b"IEND"
    ):
        return data

    from PIL import Image

    output = io.BytesIO()
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.mode == "RGBA" and image.getchannel("A").getextrema() == (
                255,
                255,
            ):
                image = image.convert("RGB")
            image.info.clear()  # The original metadata is copied below.
            image.save(
                output, "PNG", compress_level=3, compress_type=zlib.Z_DEFAULT_STRATEGY
            )
    except (OSError, ValueError):
        return data
    encoded = output.getvalue()
    if len(encoded) + image_start - 33 >= len(data):
        return data
    return encoded[:33] + data[33:image_start] + encoded[33:]
