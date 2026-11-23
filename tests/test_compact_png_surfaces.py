"""*Smaller PNG files* outside the app: `save_figure`, `save_figure_layers`
and `render --compact-png` compress a PNG losslessly, keeping its pixels, its
print dpi and the citation."""

from __future__ import annotations

import io
import shlex

import plotly.graph_objects as go
import pytest
from PIL import Image

from scanpath_studio import api, cli


def _uncompressed_png(fig, *, fmt, width, height, scale, **_):
    """A stand-in for Kaleido: an image a compressor can shrink, with the
    citation stamped as the real renderer stamps it."""
    from scanpath_studio.file_citation import stamp

    assert fmt == "png"
    size = (round(width * scale), round(height * scale))
    image = Image.new("RGB", size, "white")
    image.paste((40, 90, 160), (0, 0, size[0] // 2, size[1] // 2))
    out = io.BytesIO()
    image.save(out, "PNG", compress_level=0)
    return stamp(out.getvalue(), "png")


@pytest.fixture
def drawn(monkeypatch):
    monkeypatch.setattr(api._export, "render_static_figure_bytes", _uncompressed_png)
    return go.Figure(go.Scatter(x=[1, 2], y=[1, 2]), layout=dict(width=80, height=60))


def _pixels_and_text(path):
    with Image.open(path) as image:
        return image.convert("RGB").tobytes(), dict(image.text), image.info.get("dpi")


@pytest.mark.parametrize("print_width", [False, True])
def test_save_figure_compacts_a_png(drawn, tmp_path, print_width):
    size = {"width_mm": 20.0, "dpi": 150} if print_width else {}
    plain = api.save_figure(drawn, tmp_path / "plain.png", **size)
    small = api.save_figure(drawn, tmp_path / "small.png", compact_png=True, **size)
    assert small.stat().st_size < plain.stat().st_size
    assert _pixels_and_text(small) == _pixels_and_text(plain)
    _, text, dpi = _pixels_and_text(small)
    assert any("Scanpath Studio" in value for value in text.values())
    assert (dpi is not None) == print_width


def test_save_figure_layers_compacts_each_png_layer(drawn, tmp_path):
    plain = api.save_figure_layers(drawn, tmp_path / "plain", fmt="png")
    small = api.save_figure_layers(
        drawn, tmp_path / "small", fmt="png", compact_png=True
    )
    assert plain.keys() == small.keys() and small
    for layer, path in small.items():
        assert path.stat().st_size < plain[layer].stat().st_size
        assert _pixels_and_text(path) == _pixels_and_text(plain[layer])


def test_compact_png_is_refused_for_other_formats(drawn, tmp_path):
    with pytest.raises(ValueError, match=r"\.png"):
        api.save_figure(drawn, tmp_path / "a.svg", compact_png=True)
    with pytest.raises(ValueError, match="fmt='png'"):
        api.save_figure_layers(drawn, tmp_path / "layers", fmt="svg", compact_png=True)


def _render(monkeypatch, argv):
    seen = []

    def capture(fig, path, **kwargs):
        seen.append(kwargs)
        return path

    monkeypatch.setattr(api, "save_figure", capture)
    cli.main(["render", "--sample", *argv])
    return seen


def test_render_passes_compact_png_and_prints_it(monkeypatch, capsys):
    assert _render(monkeypatch, ["--compact-png", "-o", "a.png"])[0]["compact_png"]
    assert "compact_png" not in _render(monkeypatch, ["-o", "a.png"])[0]
    capsys.readouterr()
    _render(monkeypatch, ["--compact-png", "--print-code", "cli", "-o", "a.png"])
    command = capsys.readouterr().out
    assert "--compact-png" in shlex.split(command.replace(" \\\n", " "))
    _render(monkeypatch, ["--compact-png", "--print-code", "python", "-o", "a.png"])
    assert "compact_png=True" in capsys.readouterr().out


def test_render_refuses_compact_png_for_other_outputs(monkeypatch):
    with pytest.raises(SystemExit):
        _render(monkeypatch, ["--compact-png", "-o", "a.svg"])
