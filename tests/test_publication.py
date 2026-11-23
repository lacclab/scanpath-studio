"""Portable publication figures keep their sources, physical size and annotations."""

from __future__ import annotations

import asyncio
import io
import json

import plotly.graph_objects as go
import pytest
from PIL import Image

import scanpath_studio as sps
from scanpath_studio import cli, publication
from scanpath_studio.export import ExportOptions, _bundle_image


def test_recipe_round_trip_and_embedded_text(tmp_path):
    chart = go.Figure(go.Bar(x=["a"], y=[1]))
    src = publication.source(chart, "</script> word", settings={"exported_at": "first"})
    assert (
        src["id"]
        == publication.source(chart, src["title"], settings={"exported_at": "second"})[
            "id"
        ]
    )
    doc = publication.project([src, src], width_mm=85, layout="row")
    doc["panels"][1].update(
        crop=[0, 0, 150, 100], labels=[dict(x=10, y=15, dx=3, dy=0, text="Target")]
    )
    assert len(doc["sources"]) == 1
    path = sps.save_publication(doc, tmp_path / "test.json")
    assert json.loads(path.read_bytes()) == doc
    html = publication.editor_html(doc, plotly_script="")
    assert "</script> word" not in html
    assert r"\u003c/script> word" in html


def test_invalid_recipe_preserves_existing_file(tmp_path):
    path = tmp_path / "figure.json"
    path.write_text("keep")
    doc = publication.project([])
    doc["panels"] = [{"source": "missing", "labels": []}]
    with pytest.raises(ValueError, match="source"):
        publication.save(doc, path)
    assert path.read_text() == "keep"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"labels": [{"text": "Target", "x": "10", "y": 2, "dx": 0, "dy": 0}]},
            "pinned label",
        ),
        (
            {"labels": [dict(text="Return", x=3, y=2, dx=0, dy=1, segment=[1, 2])]},
            "saccade",
        ),
        ({"crop": [True, 0, 400, 300]}, "crop"),
    ],
)
def test_invalid_geometry_cannot_replace_an_editable_file(tmp_path, change, message):
    doc = sps.publication_figure(go.Figure(go.Bar(y=[1])))
    target = publication.save(doc, tmp_path / "figure.json")
    original = target.read_bytes()
    doc["panels"][0].update(change)
    with pytest.raises(ValueError, match=message):
        publication.save(doc, target)
    assert target.read_bytes() == original


def test_invalid_shared_heatmap_limits_cannot_be_saved():
    doc = publication.project([])
    doc["heat"] = {"min": 3, "max": 1, "scale": [[0, "white"], [1, "black"]]}
    with pytest.raises(ValueError, match="heatmap scale"):
        publication.render(doc, "json")


def test_recipe_requires_citation_for_artwork_and_caption_exports():
    doc = publication.project([])
    del doc["citation"]["Comment"]
    with pytest.raises(ValueError, match="software citation"):
        publication.editor_html(doc, plotly_script="")


@pytest.mark.parametrize("layer", ["layout", "trace"])
def test_portable_figure_requires_embedded_visible_images(layer):
    fig = go.Figure()
    url = "https://example.org/stimulus.png"
    if layer == "layout":
        fig.add_layout_image(source=url, sizex=1, sizey=1)
        image = fig.layout.images[0]
    else:
        fig.add_trace(go.Image(source=url))
        image = fig.data[0]

    with pytest.raises(ValueError, match="Embed the source image"):
        sps.publication_figure(fig)
    image.visible = False
    assert sps.publication_figure(fig)["panels"]
    image.visible = True
    image.source = go.layout.Image(source=Image.new("RGB", (1, 1))).source
    assert sps.publication_figure(fig)["panels"]


def test_chromium_print_error_keeps_previous_pdf(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import choreographer

    target = tmp_path / "figure.pdf"
    target.write_bytes(b"existing PDF")
    doc = sps.publication_figure(go.Figure(go.Bar(y=[1])))

    async def reply(method, params):
        if method == "Page.printToPDF":
            return {"error": {"code": -32000, "message": "Printing failed"}}
        if method == "Page.getFrameTree":
            return {"result": {"frameTree": {"frame": {"id": "main"}}}}
        if method == "Runtime.evaluate":
            return {"result": {"result": {"type": "undefined"}}}
        return {"result": {}}

    tab = MagicMock()
    tab.send_command = reply
    browser = MagicMock()
    browser.__aenter__.return_value.create_tab = AsyncMock(return_value=tab)
    monkeypatch.setattr(choreographer, "Browser", lambda **kwargs: browser)
    monkeypatch.setattr(
        "scanpath_studio.animation_export.chromium_browser_path", lambda: "test-browser"
    )
    monkeypatch.setattr(publication, "editor_html", lambda doc: "")
    with pytest.raises(RuntimeError, match="Printing failed"):
        publication.save(doc, target)
    assert target.read_bytes() == b"existing PDF"


def test_cli_print_width_and_source_without_words(tmp_path):
    path = tmp_path / "detail.publication.json"
    cli.main(
        [
            "render",
            "--sample",
            "--no-words",
            "--no-text",
            "--width-mm",
            "85",
            "--dpi",
            "600",
            "-o",
            str(path),
        ]
    )
    doc = json.loads(path.read_bytes())
    assert (doc["width"], doc["dpi"], doc["destination"]) == (85, 600, "Paper column")
    assert doc["sources"][0]["kind"] == "scanpath"
    assert any(
        t.get("meta", {}).get("publication_order")
        for t in doc["sources"][0]["figure"]["data"]
    )
    offline = tmp_path / "study.html"
    cli.main(["publication", str(path), "-o", str(offline)])
    assert 'id="project-data"' in offline.read_text()


def test_notebook_graphical_exports(monkeypatch):
    async def draw(doc, fmt):
        return fmt.encode()

    monkeypatch.setattr(publication, "_draw", draw)
    doc = publication.project([])

    async def in_notebook():
        assert publication.render(doc, "svg") == b"svg"
        assert publication.replay_poster(doc) == b"poster"

    asyncio.run(in_notebook())


@pytest.mark.parametrize("fmt", ["tiff", "png"])
def test_batch_raster_records_measured_physical_size(fmt):
    def renderer(fig, requested, width, height, scale):
        assert requested == "png"
        buf = io.BytesIO()
        Image.new("RGB", (round(width * scale), round(height * scale)), "white").save(
            buf, "PNG"
        )
        return buf.getvalue()

    data = _bundle_image(
        renderer,
        go.Figure(),
        fmt,
        600,
        300,
        ExportOptions(print_width_mm=85, print_dpi=300),
    )
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (1004, 502)
        assert im.info["dpi"] == pytest.approx((300, 300), abs=0.05)


def test_heatmap_without_colorbar_keeps_the_same_units_and_values():
    import pandas as pd

    from scanpath_studio.plots import _draw_word_value_heatmap

    words = pd.DataFrame(
        {"x": [0, 20], "y": [0, 0], "width": [20, 20], "height": [15, 15]}
    )

    def render(visible):
        fig = go.Figure()
        _draw_word_value_heatmap(
            fig,
            words,
            [100, 400],
            heatmap_colorscale="Blues",
            heatmap_range=None,
            show_colorbars=visible,
            heatmap_norm="Log",
            colorbar_title="Dwell",
            unit="ms",
        )
        return fig

    shown, hidden = render(True), render(False)
    assert not hidden.data
    assert (
        hidden.layout.meta["publication_hidden_heatmap"]["meta"] == shown.data[0].meta
    )


def test_single_figure_api_and_legacy_layout():
    figure = go.Figure(go.Bar(x=["before", "after"], y=[4, 6]))
    single = sps.publication_figure(figure, name="Accuracy")
    assert len(single["sources"]) == len(single["panels"]) == 1
    assert single["panels"][0]["title"] == "Accuracy"
    assert single["sources"][0]["figure"]["data"][0]["y"] == [4, 6]

    legacy = sps.publication_figure({"A": figure, "B": figure}, layout="row")
    assert [p["title"] for p in legacy["panels"]] == ["A", "B"]
    assert legacy["layout"] == "row"


def test_quick_download_size_keeps_current_figure_draft_identity():
    def capture(y, width):
        return publication.source(
            go.Figure(go.Bar(y=[y])),
            "Accuracy",
            settings={"export": {"width": width}, "selection": {"trial_id": "1"}},
        )

    original = capture(4, 85)
    resized = capture(4, 170)
    assert original["id"] == resized["id"]
    assert original["settings"] != resized["settings"]
    assert capture(6, 170)["id"] != original["id"]
