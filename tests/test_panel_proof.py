from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from scanpath_studio import api, cli, export, panel_proof
from tests.test_split_label_scale import _figure, _frames


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
def test_compatible_panels_keep_print_labels_and_common_limits_in_a_restorable_recipe(
    layout, monkeypatch, tmp_path
):
    fig = _figure(
        layout,
        (800, 600),
        color_by="duration_ms",
        show_heatmap=True,
        heatmap_norm="Log",
        heatmap_range=(0, 500),
        fixation_color_range=(20, 300),
    )
    proof = panel_proof.describe(fig, 170)
    assert proof["labels"][0].startswith("A · ") and proof["labels"][1].startswith(
        "B · "
    )
    assert proof["heatmap_range"] == pytest.approx([0, 500])
    assert proof["fixation_range"] == pytest.approx([20, 300])
    small = panel_proof.describe(fig, 85)
    assert small["label_points"]["Stimulus words"][0] == pytest.approx(
        proof["label_points"]["Stimulus words"][0] / 2, abs=0.01
    )
    config = {
        "selected_trial": "t",
        "compare": {"participant": "q", "layout": layout},
        "coloring": {},
    }
    pinned = panel_proof.settings(config, proof, keep_limits=True)
    assert pinned["export"] == {"width": 170, "unit": "mm"}
    assert (
        pinned["coloring"]["fixation_range"] == [20, 300]
        and pinned["compare"] == config["compare"]
    )
    assert (
        panel_proof.settings(config, proof, keep_limits=False)["coloring"][
            "heatmap_range"
        ]
        is None
    )
    assert config["coloring"] == {}
    monkeypatch.setattr(
        export,
        "render_static_figure_bytes",
        lambda fig, **kw: (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{kw["width"]}" height="{kw["height"]}" viewBox="0 0 {kw["width"]} {kw["height"]}"><metadata>credit</metadata></svg>'.encode()
        ),
    )
    target = api.save_panel_proof(fig, tmp_path / "paper.svg", width_mm=170)
    root = ET.parse(target).getroot()
    assert root.get("width") == "170mm"
    assert float(root.get("height")[:-2]) == pytest.approx(proof["height_mm"])
    assert (
        root.get("viewBox")
        == f"0 0 {round(fig.layout.width)} {round(fig.layout.height)}"
    )


def test_incompatible_screens_reject_a_shared_proof_and_preserve_a_previous_file(
    tmp_path,
):
    fig = _figure("side_by_side", (500, 850))
    target = tmp_path / "paper.svg"
    target.write_text("previous")
    with pytest.raises(ValueError, match="matching screen dimensions"):
        api.save_panel_proof(fig, target, width_mm=85)
    assert target.read_text() == "previous"


def test_cli_prints_and_writes_the_requested_manuscript_width(
    tmp_path, monkeypatch, capsys
):
    a, b = _frames("p"), _frames("q")
    words, fixations = tmp_path / "words.csv", tmp_path / "fixations.csv"
    pd.concat([a[0], b[0]], ignore_index=True).to_csv(words, index=False)
    pd.concat([a[1], b[1]], ignore_index=True).to_csv(fixations, index=False)
    monkeypatch.setattr(
        export,
        "render_static_figure_bytes",
        lambda fig, **kw: (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
        ),
    )
    target = tmp_path / "proof.svg"
    cli.render(
        [
            "--words",
            str(words),
            "--fixations",
            str(fixations),
            "--participant",
            "p",
            "--trial",
            "t",
            "--compare-with",
            "q:t",
            "--compare-layout",
            "side-by-side",
            "--proof-width-mm",
            "170",
            "--print-code",
            "both",
            "-o",
            str(target),
        ]
    )
    output = capsys.readouterr()
    assert "--proof-width-mm 170" in output.out and "proof_width_mm=170" in output.out
    assert ET.parse(target).getroot().get("width") == "170mm"
