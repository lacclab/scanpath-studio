"""Fixation annotations and print-sized bundles preserve the rendered source."""

from __future__ import annotations

import io

import pandas as pd
import pytest
from PIL import Image

from scanpath_studio import api, export
from scanpath_studio.synthetic import (
    PARTICIPANT,
    TRIAL,
    make_synthetic_fixations,
    make_synthetic_words,
)


@pytest.mark.parametrize(
    "fields,spatial", [(("x", "y"), True), (("order_in_trial", "x"), False)]
)
def test_saccade_annotation_requires_spatial_coordinates(fields, spatial):
    words, fix = make_synthetic_words(), make_synthetic_fixations()
    axes = dict(x_field=fields[0], y_field=fields[1], fixation_symbol="heart")
    single = api.plot_scanpath(words, fix, PARTICIPANT, TRIAL, **axes)
    pair = api.compare_scanpaths(
        pd.concat([words, words.assign(participant_id="B")]),
        pd.concat([fix, fix.assign(participant_id="B")]),
        (PARTICIPANT, TRIAL),
        ("B", TRIAL),
        **axes,
    )
    for fig, readings in ((single, [""]), (pair, ["A", "B"])):
        info = [
            trace.meta
            for trace in fig.data
            if isinstance(trace.meta, dict) and "publication_order" in trace.meta
        ]
        assert [event["publication_reading"] for event in info] == readings
        assert all(event["publication_spatial"] is spatial for event in info)


@pytest.mark.parametrize("fmt", ["png", "tiff"])
def test_batch_build_ahead_uses_final_raster_size(fmt):
    reading = export._ExportReading(
        {},
        None,
        (pd.DataFrame({"x": [1]}), pd.DataFrame(), pd.DataFrame()),
        1000,
        1000,
        {},
    )
    options = export.ExportOptions(
        include_png=fmt == "png",
        include_tiff=fmt == "tiff",
        print_width_mm=250,
        print_dpi=600,
    )
    assert not reading.can_build_ahead(options)
    options.print_dpi = 150
    assert reading.can_build_ahead(options)


def test_png_compression_runs_on_finished_png_only(monkeypatch):
    def draw(fig, fmt, width, height, scale):
        assert fmt == "png"
        out = io.BytesIO()
        Image.new("RGB", (round(width * scale), round(height * scale))).save(out, "PNG")
        return out.getvalue()

    seen = []

    def compact(data):
        with Image.open(io.BytesIO(data)) as image:
            seen.append(image.info["dpi"])
        return data

    monkeypatch.setattr(export, "compact_png", compact)
    options = export.ExportOptions(
        print_width_mm=25.4, print_dpi=150, compact_pngs=True
    )
    for fmt in ("tiff", "png"):
        export._bundle_image(draw, None, fmt, 80, 40, options)
    assert len(seen) == 1
    assert seen[0] == pytest.approx((150, 150), abs=0.02)
