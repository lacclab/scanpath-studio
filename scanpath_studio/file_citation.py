"""Write the app's citation into an exported file's own metadata.

Every figure, replay and page the app, the API and the CLI write carries
``citation.file_metadata`` — the tool and release, the DOI, the full reference —
where that format keeps such text, so a file found later on its own still says
how to cite it. Nothing is drawn: the pixels, paths and pages are untouched.

Each format is stamped by editing its bytes, never by re-encoding them:

- **PNG** — ``iTXt`` chunks (UTF-8) before the first ``IDAT``;
- **SVG** — a ``<metadata>`` element as the root's first child;
- **PDF** — an incremental update whose new document-info dictionary keeps the
  old one's entries and adds ``Creator`` / ``Subject`` / ``Keywords``;
- **HTML** — ``<meta name="generator">`` and a citation comment in ``<head>``;
- **GIF** — a comment extension after the global colour table.

MP4 has no byte-level stamp here: ``animation_export`` passes the same text to
ffmpeg as the container's ``comment`` while it encodes.

A file this cannot parse is returned unchanged — the citation is a courtesy and
never the reason an export fails.
"""

from __future__ import annotations

import re
import struct
import zlib
from html import escape

from scanpath_studio.citation import file_metadata

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def stamp(data: bytes, fmt: str) -> bytes:
    """``data`` with the citation written into its metadata, for ``fmt``
    (``png``, ``svg``, ``pdf``, ``html``, ``gif``; anything else is returned
    as is)."""
    stamper = _STAMPERS.get(fmt.lower().lstrip("."))
    if stamper is None:
        return data
    try:
        return stamper(data, file_metadata())
    except (ValueError, IndexError, struct.error, UnicodeDecodeError):
        return data


def stamp_file(path, fmt: str | None = None) -> None:
    """Stamp the file at ``path`` in place (its format from the suffix)."""
    from pathlib import Path

    path = Path(path)
    fmt = fmt or path.suffix
    if fmt.lower().lstrip(".") not in _STAMPERS:
        return
    try:
        data = path.read_bytes()
    except OSError:  # nothing was written there to stamp
        return
    stamped = stamp(data, fmt)
    if stamped is not data:
        path.write_bytes(stamped)


def stamp_html(page: str) -> str:
    """An HTML page (as text) with the citation in its ``<head>``."""
    return stamp(page.encode("utf-8"), "html").decode("utf-8")


def mp4_metadata_args() -> list[str]:
    """ffmpeg output arguments that write the citation into an MP4's tags."""
    meta = file_metadata()
    return [
        "-metadata",
        f"comment={meta['Comment']}",
        "-metadata",
        f"description={meta['Source']}",
    ]


# --- PNG ----------------------------------------------------------------------


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def png_text_chunks(meta: dict[str, str] | None = None) -> bytes:
    """The citation as PNG ``iTXt`` chunks, ready to splice in before ``IDAT``
    (the browser-side save in ``tabs`` splices these same bytes)."""
    return b"".join(
        # keyword NUL, compression flag + method, empty language and
        # translated keyword, then the UTF-8 text.
        _png_chunk(b"iTXt", key.encode("latin-1") + b"\0\0\0\0\0" + text.encode())
        for key, text in (meta or file_metadata()).items()
    )


def _stamp_png(data: bytes, meta: dict[str, str]) -> bytes:
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("not a PNG")
    idat = data.find(b"IDAT")
    if idat < 12:
        raise ValueError("no IDAT chunk")
    start = idat - 4  # the IDAT chunk's length field
    return data[:start] + png_text_chunks(meta) + data[start:]


# --- SVG ----------------------------------------------------------------------


def svg_metadata(meta: dict[str, str] | None = None) -> str:
    """The citation as an SVG ``<metadata>`` element, the root's first child
    (the browser-side save in ``tabs`` inserts this same text)."""
    lines = "\n".join(
        f"{key}: {escape(value)}" for key, value in (meta or file_metadata()).items()
    )
    return f"<metadata>\n{lines}\n</metadata>"


def _stamp_svg(data: bytes, meta: dict[str, str]) -> bytes:
    text = data.decode("utf-8")
    root = re.search(r"<svg\b[^>]*?(/?)>", text)
    if root is None or root.group(1):
        raise ValueError("no <svg> root with children")
    block = svg_metadata(meta)
    return (text[: root.end()] + block + text[root.end() :]).encode("utf-8")


# --- PDF ----------------------------------------------------------------------


def _pdf_string(text: str) -> bytes:
    """A PDF text string: UTF-16BE with a BOM, as a hex string."""
    return b"<FEFF" + text.encode("utf-16-be").hex().upper().encode() + b">"


def _stamp_pdf(data: bytes, meta: dict[str, str]) -> bytes:
    """Append an incremental update with a new document-info dictionary.

    Only a classic ``xref`` table + ``trailer`` (what Kaleido's Chrome writes) is
    handled; a file with a cross-reference stream is left alone.
    """
    startxref = data.rfind(b"startxref")
    trailer_at = data.rfind(b"trailer", 0, startxref)
    if startxref < 0 or trailer_at < 0:
        raise ValueError("no classic trailer")
    prev = int(data[startxref + len(b"startxref") :].split()[0])
    trailer = data[trailer_at:startxref]
    size = int(re.search(rb"/Size\s+(\d+)", trailer).group(1))
    root = re.search(rb"/Root\s+(\d+\s+\d+\s+R)", trailer).group(1)

    kept = b""
    info_ref = re.search(rb"/Info\s+(\d+)\s+(\d+)\s+R", trailer)
    if info_ref:
        number, generation = info_ref.groups()
        obj = re.search(
            rb"(?<!\d)"
            + number
            + rb"\s+"
            + generation
            + rb"\s+obj\s*<<(.*?)>>\s*endobj",
            data,
            re.DOTALL,
        )
        if obj:
            # Keep the old entries we do not replace (Producer, the dates). The
            # Title is Kaleido's page title, not the figure's, so it goes too.
            kept = re.sub(
                rb"/(Title|Creator|Subject|Keywords)\s*(\((?:\\.|[^\\)])*\)|<[^>]*>)",
                b"",
                obj.group(1),
            ).strip()

    body = (
        b"<<"
        + (kept + b"\n" if kept else b"")
        + b"/Creator "
        + _pdf_string(meta["Software"])
        + b"\n/Subject "
        + _pdf_string(meta["Comment"])
        + b"\n/Keywords "
        + _pdf_string(meta["Source"])
        + b">>"
    )
    base = data if data.endswith(b"\n") else data + b"\n"
    offset = len(base)
    update = b"%d 0 obj\n" % size + body + b"\nendobj\n"
    xref_at = offset + len(update)
    update += (
        b"xref\n0 1\n0000000000 65535 f \n%d 1\n%010d 00000 n \n" % (size, offset)
        + b"trailer\n<</Size %d\n/Root " % (size + 1)
        + root
        + b"\n/Info %d 0 R\n/Prev %d>>\nstartxref\n%d\n%%%%EOF\n"
        % (size, prev, xref_at)
    )
    return base + update


# --- HTML ---------------------------------------------------------------------


def _stamp_html(data: bytes, meta: dict[str, str]) -> bytes:
    text = data.decode("utf-8")
    tags = (
        f'<meta name="generator" content="{escape(meta["Software"])}">\n'
        f"<!-- {meta['Comment'].replace('--', '-')} -->\n"
    )
    head = re.search(r"<head\b[^>]*>", text, re.IGNORECASE)
    if head is None:
        return (tags + text).encode("utf-8")
    return (text[: head.end()] + "\n" + tags + text[head.end() :]).encode("utf-8")


# --- GIF ----------------------------------------------------------------------


def _stamp_gif(data: bytes, meta: dict[str, str]) -> bytes:
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not a GIF")
    flags = data[10]
    at = 13 + (3 * 2 ** ((flags & 0x07) + 1) if flags & 0x80 else 0)
    text = meta["Comment"].encode("latin-1", "replace")
    blocks = b"".join(
        bytes([len(text[i : i + 255])]) + text[i : i + 255]
        for i in range(0, len(text), 255)
    )
    # A comment extension is a GIF89a feature.
    return b"GIF89a" + data[6:at] + b"\x21\xfe" + blocks + b"\x00" + data[at:]


_STAMPERS = {
    "png": _stamp_png,
    "svg": _stamp_svg,
    "pdf": _stamp_pdf,
    "html": _stamp_html,
    "htm": _stamp_html,
    "gif": _stamp_gif,
}
