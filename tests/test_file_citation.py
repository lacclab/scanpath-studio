"""The citation every exported file carries, and the formats it is offered in."""

from __future__ import annotations

import io
import json
import re

import pytest
from PIL import Image

from scanpath_studio import __release__
from scanpath_studio.citation import CORPORA, FORMATS, cite, file_metadata
from scanpath_studio.constants import CITATION
from scanpath_studio.file_citation import stamp

DOI = CITATION["doi"]


@pytest.mark.parametrize("fmt", FORMATS)
def test_every_format_names_the_doi_and_adds_the_corpus(fmt):
    alone = cite(fmt)
    assert DOI in alone
    with_corpus = cite(fmt, "onestop")
    if fmt != "csl-json":
        assert with_corpus.startswith(alone)
    if fmt != "credit":
        assert CORPORA["onestop"].doi in with_corpus
    assert "OneStop" in with_corpus


def test_cite_rejects_unknown_values():
    with pytest.raises(ValueError, match="format"):
        cite("mla")
    with pytest.raises(ValueError, match="corpus"):
        cite("bibtex", "geco")


def test_csl_json_and_ris_are_well_formed():
    records = json.loads(cite("csl-json", "potec"))
    assert [r["type"] for r in records] == ["software", "article-journal"]
    assert records[0]["version"] == __release__
    ris = cite("ris", "potec")
    assert ris.count("TY  - ") == ris.count("ER  - ") == 2


def test_apa_is_plain_text_and_credit_is_one_line():
    assert "*" not in cite("apa", "onestop")
    credit = cite("credit", "potec")
    assert "\n" not in credit
    assert credit.startswith(f"Made with Scanpath Studio {__release__}")
    assert "PoTeC" in credit


def test_corpus_bibtex_compiles_its_accents():
    assert r"J{\"a}ger, Lena A." in CORPORA["potec"].bibtex()


# --- Stamped files -----------------------------------------------------------


@pytest.fixture(scope="module")
def figure():
    import plotly.graph_objects as go

    return go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))


def _png(width=4, height=3) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG", dpi=(300, 300))
    return out.getvalue()


def test_png_gains_text_chunks_and_keeps_pixels_and_dpi():
    stamped = stamp(_png(), "png")
    image = Image.open(io.BytesIO(stamped))
    image.load()
    assert image.text == file_metadata()
    assert image.size == (4, 3)
    assert round(image.info["dpi"][0]) == 300


def test_svg_gains_a_metadata_element():
    import xml.dom.minidom

    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect/></svg>'
    )
    stamped = stamp(svg, "svg")
    doc = xml.dom.minidom.parseString(stamped)
    meta = doc.documentElement.firstChild
    assert meta.tagName == "metadata"
    assert DOI in meta.firstChild.data


def test_html_gains_a_generator_meta(figure):
    page = figure.to_html(include_plotlyjs=False).encode()
    stamped = stamp(page, "html").decode()
    head = stamped[: stamped.index("</head>")]
    assert f'<meta name="generator" content="Scanpath Studio {__release__}">' in head
    assert DOI in head


def test_gif_gains_a_comment_and_keeps_its_frames():
    out = io.BytesIO()
    frames = [Image.new("RGB", (8, 8), color) for color in ("red", "blue")]
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:])
    stamped = Image.open(io.BytesIO(stamp(out.getvalue(), "gif")))
    assert stamped.n_frames == 2
    assert DOI.encode() in stamped.info["comment"]


def _pdf() -> bytes:
    """A minimal classic-xref PDF with an info dictionary, as Chrome writes."""
    objects = [
        b"<</Title (Kaleido-fier) /Producer (Skia/PDF) /Creator (Chrome)>>",
        b"<</Type /Catalog /Pages 3 0 R>>",
        b"<</Type /Pages /Kids [] /Count 0>>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n"
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += (
        b"trailer\n<</Size 4 /Root 2 0 R /Info 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % xref
    )
    return out


def test_pdf_gains_an_info_update_that_keeps_the_producer():
    original = _pdf()
    stamped = stamp(original, "pdf")
    assert stamped.startswith(original)
    update = stamped[len(original) :]
    assert b"/Producer (Skia/PDF)" in update
    assert b"Kaleido-fier" not in update and b"(Chrome)" not in update
    creator = re.search(rb"/Creator <FEFF([0-9A-F]+)>", update).group(1)
    assert bytes.fromhex(creator.decode()).decode("utf-16-be") == (
        f"Scanpath Studio {__release__}"
    )
    xref = int(re.findall(rb"startxref\n(\d+)", stamped)[-1])
    assert stamped[xref:].startswith(b"xref\n")
    assert b"/Prev %d" % (original.rfind(b"\nxref\n") + 1) in update


@pytest.mark.parametrize("fmt", ["png", "pdf", "gif", "svg"])
def test_a_file_it_cannot_parse_is_returned_unchanged(fmt):
    junk = b"not really a file"
    assert stamp(junk, fmt) == junk


def test_an_unknown_format_is_returned_unchanged():
    assert stamp(b"x", "csv") == b"x"


# --- Headless entry points ---------------------------------------------------


def test_the_package_exports_cite():
    import scanpath_studio as sps

    assert "cite" in sps.__all__
    assert sps.cite("ris") == cite("ris")


def test_cli_cite_prints_the_asked_format(capsys):
    from scanpath_studio import cli

    cli.main(["cite", "--format", "credit", "--corpus", "potec"])
    assert capsys.readouterr().out.strip() == cite("credit", "potec")
    with pytest.raises(SystemExit):
        cli.main(["cite", "--format", "mla"])
