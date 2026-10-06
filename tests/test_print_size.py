"""#374 F28 — Export → Current figure's Width (mm or in) + DPI, on every
surface: the app's PNG, `save_figure`, `render`, Share → Code and the link."""

from __future__ import annotations

import re
import shlex
from urllib.parse import parse_qs

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

import scanpath_studio as sps
from scanpath_studio import api, cli, export, tabs, url_state
from scanpath_studio import code_snippet as cs
from scanpath_studio.animation_export import chrome_available


def test_a_print_width_is_its_pixel_width():
    assert export.print_width_px(180, "mm", 600) == 4252
    assert export.print_width_px(3.5, "in", 300) == 1050
    with pytest.raises(ValueError, match="mm' or 'in"):
        export.print_width_px(10, "cm", 300)


def test_the_save_keywords_follow_the_export_subtab():
    assert export.png_save_kwargs(None) == {"scale": export.SCREEN_PNG_SCALE}
    assert export.png_save_kwargs(180, "mm", 600) == {"width_mm": 180.0, "dpi": 600}
    assert export.png_save_kwargs(3.5, "in", None) == {"width_in": 3.5, "dpi": 300}


def test_the_app_png_and_the_code_write_the_same_pixel_width(monkeypatch):
    monkeypatch.setattr(
        streamlit,
        "session_state",
        {
            "export_figure_width": 180.0,
            "export_figure_width_unit": "mm",
            "export_figure_dpi": 600,
        },
    )
    assert round(960 * tabs._png_scale(960)) == 4252
    kwargs = url_state._snippet_save_kwargs()
    assert kwargs == {"width_mm": 180.0, "dpi": 600}
    monkeypatch.setattr(streamlit, "session_state", {})
    assert tabs._png_scale(960) == tabs._PNG_EXPORT_SCALE == export.SCREEN_PNG_SCALE
    assert url_state._snippet_save_kwargs() == {"scale": 3}


def test_save_figure_refuses_a_dpi_without_a_width(tmp_path):
    fig = sps.plot_scanpath(
        *sps.load_sample_data(), "l37_1129", "l37_1129_2_1_1_Ele_r0"
    )
    with pytest.raises(ValueError, match="width_mm or width_in"):
        api.save_figure(fig, tmp_path / "a.png", dpi=600)
    with pytest.raises(ValueError, match="size a PNG"):
        api.save_figure(fig, tmp_path / "a.svg", width_mm=180)
    with pytest.raises(ValueError, match="not both"):
        api.save_figure(fig, tmp_path / "a.png", width_mm=180, width_in=7)


@pytest.mark.skipif(not chrome_available(), reason="needs Chrome for Kaleido")
def test_save_figure_writes_the_print_size(tmp_path):
    from PIL import Image

    fig = sps.plot_scanpath(
        *sps.load_sample_data(), "l37_1129", "l37_1129_2_1_1_Ele_r0"
    )
    path = api.save_figure(fig, tmp_path / "a.png", width_mm=180, dpi=600)
    with Image.open(path) as image:
        assert image.size[0] == 4252
        assert round(image.info["dpi"][0]) == 600


def test_render_takes_the_print_size_and_prints_it(monkeypatch, capsys, tmp_path):
    seen = {}

    def fake_save(fig, path, **kwargs):
        seen.update(kwargs)
        return path

    monkeypatch.setattr(api, "save_figure", fake_save)
    cli.main(
        [
            "render",
            "--sample",
            "--width-mm",
            "180",
            "--dpi",
            "600",
            "--print-code",
            "both",
            "-o",
            str(tmp_path / "a.png"),
        ]
    )
    assert seen["width_mm"] == 180.0 and seen["dpi"] == 600
    printed = capsys.readouterr().out
    assert "width_mm=180.0, dpi=600" in printed
    assert "--width-mm 180 --dpi 600" in printed
    command = next(line for line in printed.splitlines() if "render" in line)
    assert "--scale" not in command


def test_the_snippet_cli_reparses():
    state = cs.FigureState(
        kind="static", settings=api.figure_options("static"), participant="p", trial="t"
    )
    command, _ = cs.cli_snippet(
        cs.SnippetSource(kind=cs.SOURCE_DEMO),
        state,
        save_kwargs={"width_in": 3.5, "dpi": 300},
    )
    argv = shlex.split(command.replace(" \\\n", " "))
    args = cli._render_parser().parse_args(argv[2:])
    assert (args.width_in, args.dpi) == (3.5, 300)


def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _build_share_query

    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    st.session_state["export_figure_width_unit"] = "mm"
    st.session_state["export_figure_dpi"] = 600
    st.session_state["_without"] = _build_share_query("Bundled Demo")[0]
    st.session_state["export_figure_width"] = 180.0
    st.session_state["_with"] = _build_share_query("Bundled Demo")[0]


def test_the_link_carries_the_print_size_only_while_a_width_is_set():
    at = AppTest.from_function(_link_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    without = parse_qs(at.session_state["_without"])
    assert not {"export_width", "export_width_unit", "export_dpi"} & set(without)
    with_width = parse_qs(at.session_state["_with"])
    assert with_width["export_width"] == ["180.0"]
    assert with_width["export_dpi"] == ["600"]
    assert with_width["export_width_unit"] == ["mm"]


def test_the_bundle_readme_says_its_local_time_and_offset():
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \(UTC[+-]\d\d:\d\d\)", export._local_stamp()
    )


@pytest.mark.parametrize(
    ("width", "dpi"), [(0.5, 300), (2500.0, 300), (180.0, 10), (180.0, 10000)]
)
def test_a_print_size_outside_the_links_bounds_is_refused(width, dpi):
    """#374: render / save_figure accept what a link or the Width box accepts."""
    from scanpath_studio.export import print_width_px

    with pytest.raises(ValueError):
        print_width_px(width, "mm", dpi)
