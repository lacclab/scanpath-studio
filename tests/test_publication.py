"""Portable publication figures keep their sources, physical size and annotations."""

from __future__ import annotations

import asyncio
import base64
import io
import json

import plotly.graph_objects as go
import pytest
from PIL import Image

import scanpath_studio as sps
from scanpath_studio import cli, publication
from scanpath_studio.animation_export import chrome_available, chromium_browser_path
from scanpath_studio.export import ExportOptions, _bundle_image

needs_chrome = pytest.mark.skipif(
    not chrome_available(), reason="needs Chrome to draw the figure"
)


def _in_editor(doc: dict, *expressions: str, **page) -> list:
    """Evaluate each expression, in order, in the offline editor in Chromium."""
    from choreographer import Browser

    async def run():
        async with Browser(path=chromium_browser_path()) as browser:
            tab = await browser.create_tab()

            async def command(method, params=None):
                reply = await tab.send_command(method, params)
                assert "error" not in reply, reply
                return reply["result"]

            async def evaluate(expression):
                result = await command(
                    "Runtime.evaluate",
                    {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                )
                assert "exceptionDetails" not in result, result
                return result["result"].get("value")

            tree = await command("Page.getFrameTree")
            await command(
                "Page.setDocumentContent",
                {
                    "frameId": tree["frameTree"]["frame"]["id"],
                    "html": publication.editor_html(doc, **page),
                },
            )
            await evaluate("window.publicationReady")
            return [await evaluate(e) for e in expressions]

    return asyncio.run(run())


def _replay_recipe(**kwargs) -> dict:
    words, fixations = sps.load_sample_data(names="canonical")
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    replay = sps.animate_scanpath(words, fixations, pid, tid, fix_index_range=(1, 40))
    return sps.publication_figure(replay, name="Replay", **kwargs)


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


@needs_chrome
def test_replay_clip_keeps_one_size_when_the_caption_time_wraps(tmp_path):
    import imageio.v2 as imageio

    doc = _replay_recipe(width_mm=85)
    doc["captionPlacement"] = "Wrap"
    # A description whose suggested caption changes its line count with the
    # frame's reading time, and the first frame at which it does.
    (found,) = _in_editor(
        doc,
        """(() => {
          const p = doc.panels[0], s = byId(p.source), times = clock(s),
            w = doc.width * PT - 2 * Math.min(10, doc.width * PT * 0.025);
          for (let n = 0; n < 300; n++) {
            s.description = "Replay " + "x".repeat(n);
            const count = times.map(
              (_, i) => lines(draft(false, [{ ...p, frame: i }]), w, 9).length
            );
            const k = count.findIndex((c) => c !== count[0]);
            if (k > 0) return [s.description, k];
          }
        })()""",
    )
    assert found, "no description wraps the caption time within the clip"
    description, k = found
    doc["sources"][0]["description"] = description
    doc["panels"][0].update(start=k - 1, end=k, frame=k - 1)

    def heights(steady):
        return f"""(async () => {{
          const out = [];
          for (const frame of [{k - 1}, {k}])
            out.push((await artwork([{{ ...doc.panels[0], frame }}], {steady})).H);
          return out;
        }})()"""

    still, clip = _in_editor(doc, heights("false"), heights("true"))
    # A still keeps its own frame's caption; every frame of the clip holds
    # the room of the longest one.
    assert still[0] != still[1]
    assert clip == [max(still), max(still)]

    movie = tmp_path / "clip.mp4"
    movie.write_bytes(publication.render(doc, "mp4"))
    with Image.open(io.BytesIO(publication.replay_poster(doc))) as poster:
        reader = imageio.get_reader(movie)
        try:
            frame = reader.get_data(0)
        finally:
            reader.close()
        assert frame.shape[:2] == (poster.height, poster.width)


@needs_chrome
@pytest.mark.parametrize("crop", [None, [0, 0, 300, 200]])
def test_batch_size_is_the_proof_artwork_width(crop):
    doc = sps.publication_figure(
        go.Figure(go.Bar(y=[1, 2]), layout=dict(width=600, height=400)),
        width_mm=85,
    )
    doc["panels"][0]["crop"] = crop
    ((sent, cell, page, shown),) = _in_editor(
        doc,
        """(async () => {
          const sent = [];
          window.postMessage = (message) => sent.push(message);
          tool = "Print settings";
          paintControls();
          const use = [...document.querySelectorAll("#controls button")].find(
            (b) => b.textContent === "Use this size for batch export"
          );
          await use.onclick();
          const cell = currentSheet.positions[0];
          return [
            sent.map((m) => m.value),
            [cell.w / PT, cell.k, cell.art.w],
            currentSheet.W / PT,
            document.querySelector("#controls").textContent,
          ];
        })()""",
        session="test",
        batch=True,
    )
    width, k, figure_width = cell
    assert page == pytest.approx(85)
    assert sent == [{"width": pytest.approx(width, abs=0.005), "dpi": 300}]
    # The sheet's side margins are not part of the artwork.
    assert sent[0]["width"] < 85
    if crop is None:
        # The whole figure prints at the proof's scale, so lettering matches.
        assert sent[0]["width"] / figure_width == pytest.approx(k * 25.4 / 72, rel=1e-3)
    assert "The crop, labels and caption apply only to this figure." in shown


def _corpus_chart_app():
    import plotly.graph_objects as go
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state.setdefault("corpus_subtab", "Per text")
    if st.session_state.get("note"):
        st.info("A note drawn above the chart.")
    for measure in st.session_state.get("measures", ["Skip rate"]):
        tabs._chart(
            go.Figure(
                go.Bar(x=["a", "b"], y=[1, 2]),
                layout=dict(title=measure, xaxis_title="Word", yaxis_title=measure),
            )
        )


def _chart_workspaces(at) -> dict:
    return {
        k: at.session_state[k]
        for k in at.session_state
        if str(k).startswith("prepare_figure_chart_")
    }


def test_corpus_chart_workspace_stays_open_when_a_note_appears_above():
    from streamlit.testing.v1 import AppTest

    workspaces = _chart_workspaces
    at = AppTest.from_function(_corpus_chart_app).run()
    assert not at.exception
    (key,) = workspaces(at)
    at.session_state[key] = True
    at.run()
    at.session_state["note"] = True
    at.run()
    assert not at.exception
    assert workspaces(at) == {key: True}
    (group,) = [e for e in at.expander if e.label == "Prepare figure for export"]
    assert group.proto.expanded

    # Another chart, here another measure, has a workspace of its own.
    at.session_state["measures"] = ["Regression rate"]
    at.run()
    assert set(workspaces(at)) - {key}


def test_open_workspaces_keep_their_own_editor_pages(monkeypatch):
    from streamlit.testing.v1 import AppTest

    built = []
    editor_html = publication.editor_html

    def counted(doc, **kwargs):
        built.append(kwargs["import_id"])
        return editor_html(doc, **kwargs)

    monkeypatch.setattr(publication, "editor_html", counted)
    at = AppTest.from_function(_corpus_chart_app)
    at.session_state["measures"] = ["Skip rate", "Regression rate"]
    at.run()
    for key in _chart_workspaces(at):
        at.session_state[key] = True
    at.run()
    assert len(built) == 2
    at.run()
    at.run()
    assert not at.exception
    assert len(built) == 2, "an open workspace rebuilt its editor page"

    # The pages kept stay bounded however many workspaces were opened.
    measures = [f"Measure {i}" for i in range(6)]
    at.session_state["measures"] = measures
    at.run()
    for key in _chart_workspaces(at):
        at.session_state[key] = True
    at.run()
    assert not at.exception
    assert len(at.session_state["_publication_markup"]) == 4


def test_clip_frames_of_different_sizes_are_refused(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import choreographer

    def png(width):
        buf = io.BytesIO()
        Image.new("RGB", (width, 40), "white").save(buf, "PNG")
        return {"type": "string", "value": base64.b64encode(buf.getvalue()).decode()}

    frames = iter([png(60), png(60), png(80)])

    async def reply(method, params):
        if method == "Page.getFrameTree":
            return {"result": {"frameTree": {"frame": {"id": "main"}}}}
        if method == "Runtime.evaluate":
            expression = params["expression"]
            if expression == "publicationClipDuration()":
                return {"result": {"result": {"type": "number", "value": 125}}}
            if expression.startswith("publicationMovieFrame"):
                return {"result": {"result": next(frames)}}
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
    with pytest.raises(ValueError, match="changed size at frame 3 of the clip"):
        publication.render(publication.project([]), "mp4")
