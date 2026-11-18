"""Compare on chart axes: X / Y fields other than screen x / y.

A reading whose screen position is reconstructed is still worth comparing by
*which word* each fixation landed on and for how long — fixation index against
word ID, marker size the duration. On such axes the comparison (overlay or two
panels) and the single-trial figure draw a chart: markers sized as the spatial
figures size them, straight saccade lines, value axes both readings share, and
a word-ID axis labelled with the words. Nothing spatial is drawn.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api, plots
from scanpath_studio.constants import compare_palette_color

CHART = dict(x_field="order_in_trial", y_field="word_id")
LAYOUTS = ["overlay", "side_by_side", "stacked"]


def _reading(participant: str, text: list[str], word_ids: list[int], durations):
    """One reading: the words of ``text`` on a line, and fixations on
    ``word_ids`` with ``durations``."""
    n = len(word_ids)
    words = pd.DataFrame(
        {
            "participant_id": participant,
            "trial_id": "t",
            "text_id": "text",
            "word_id": range(len(text)),
            "text": text,
            "line_idx": 0,
            "x": [100.0 + 60 * i for i in range(len(text))],
            "y": 100.0,
            "width": 50.0,
            "height": 20.0,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": participant,
            "trial_id": "t",
            "text_id": "text",
            "x": [110.0 + 60 * w for w in word_ids],
            "y": 110.0,
            "duration_ms": durations,
            "timestamp_ms": [100 * i for i in range(n)],
            "order_in_trial": range(1, n + 1),
            "fixation_id": range(1, n + 1),
            "word_id": word_ids,
        }
    )
    return words, fixations


TEXT = ["The", "cat", "sat", "on", "a", "mat"]


def _pair(text_b: list[str] | None = None):
    """A real reading (with a regression) and a model's reading of the same text,
    or of ``text_b``."""
    words_a, fix_a = _reading(
        "real", TEXT, [0, 1, 3, 2, 4, 5], [180, 220, 150, 300, 90, 260]
    )
    words_b, fix_b = _reading(
        "model", text_b or TEXT, [0, 1, 2, 3, 5], [200, 200, 200, 200, 200]
    )
    return (
        pd.concat([words_a, words_b], ignore_index=True),
        pd.concat([fix_a, fix_b], ignore_index=True),
    )


def _figure(layout: str, text_b: list[str] | None = None, **overrides):
    words, fixations = _pair(text_b)
    return plots.make_comparison_figure(
        words,
        fixations,
        ("real", "t"),
        ("model", "t"),
        canvas_width=1280,
        canvas_height=720,
        base_font_size=16,
        layout=layout,
        trial_labels=("Real", "Model"),
        **{**CHART, **overrides},
    )


def _markers(fig) -> list:
    return [
        t
        for t in fig.data
        if t.mode and "markers" in t.mode and t.customdata is not None
    ]


def _data_shapes(fig) -> list:
    """Shapes placed on the data — word boxes, heatmap tints, the frame — as
    against the duration key's swatches, which sit on the paper."""
    return [s for s in fig.layout.shapes or () if s.yref != "paper"]


def _lines(fig) -> list:
    return [t for t in fig.data if t.mode == "lines"]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_each_reading_is_drawn_in_fixation_order_on_the_chart_axes(layout):
    fig = _figure(layout)
    real, model = _markers(fig)
    assert list(real.x) == [1, 2, 3, 4, 5, 6]
    assert list(real.y) == [0, 1, 3, 2, 4, 5]
    assert list(model.y) == [0, 1, 2, 3, 5]
    # Each in its own Compare colour, sized as every figure sizes a duration.
    assert real.marker.color == compare_palette_color(0)
    assert model.marker.color == compare_palette_color(1)
    expected = plots._compute_marker_sizes(
        pd.Series([180, 220, 150, 300, 90, 260]), plots.DEFAULT_MARKER_SIZE_RANGE
    )
    assert list(real.marker.size) == list(expected)
    # Nothing spatial: no word boxes, frame, heatmap or stimulus image.
    assert not _data_shapes(fig)
    assert not fig.layout.images
    assert fig.layout.xaxis.title.text == plots._column_title("order_in_trial")
    assert fig.layout.yaxis.title.text == plots._column_title("word_id")
    assert fig.layout.yaxis.scaleanchor is None


def test_the_hover_names_the_fixation_its_word_and_duration():
    real = _markers(_figure("overlay"))[0]
    template = real.hovertemplate
    first = [str(v) for v in real.customdata[0]]
    assert "Real" in template
    lead = " ".join(first)
    assert "1" in lead and "180" in lead and "The" in lead


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
def test_split_panels_share_their_ranges_and_carry_their_titles(layout):
    fig = _figure(layout)
    assert fig.layout.xaxis.range == fig.layout.xaxis2.range
    assert fig.layout.yaxis.range == fig.layout.yaxis2.range
    # Both readings fit: fixation 1..6, words 0..5 (the whole text).
    x0, x1 = fig.layout.xaxis.range
    y0, y1 = fig.layout.yaxis.range
    assert x0 < 1 and x1 > 6 and y0 < 0 and y1 > 5
    titles = [a.text for a in fig.layout.annotations if a.name == plots._PANEL_NAME]
    assert titles == ["A · Real", "B · Model"]
    real, model = _markers(fig)
    assert (real.xaxis, model.xaxis) == ("x", "x2")


def test_the_overlay_is_one_axes():
    fig = _figure("overlay")
    assert "xaxis2" not in fig.layout.to_plotly_json()
    assert {t.xaxis for t in _markers(fig)} == {None}


@pytest.mark.parametrize("layout", LAYOUTS)
def test_saccades_join_consecutive_fixations_in_each_readings_colour(layout):
    lines = _lines(_figure(layout))
    assert len(lines) == 2
    real, model = lines
    assert real.line.color == compare_palette_color(0)
    assert model.line.color == compare_palette_color(1)
    # Fixation i to i + 1, None between segments.
    assert list(real.x[:6]) == [1, 2, None, 2, 3, None]
    assert list(real.y[:6]) == [0, 1, None, 1, 3, None]
    assert not _lines(_figure(layout, show_saccades=False))


def test_no_arrowheads_on_a_chart():
    """An arrowhead's angle is measured in data units, which a chart's two axes
    do not share."""
    fig = _figure("overlay", show_saccade_arrows=True)
    assert not [t for t in fig.data if t.marker and t.marker.symbol == "arrow"]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_a_word_id_axis_names_the_words(layout):
    fig = _figure(layout)
    expected = ["0 The", "1 cat", "2 sat", "3 on", "4 a", "5 mat"]
    assert list(fig.layout.yaxis.ticktext) == expected
    assert list(fig.layout.yaxis.tickvals) == [0, 1, 2, 3, 4, 5]
    # The fixation-index axis keeps its numbers.
    assert fig.layout.xaxis.ticktext is None
    if layout != "overlay":
        assert list(fig.layout.yaxis2.ticktext) == expected


def test_two_texts_label_each_panel_from_its_own_words():
    other = ["A", "dog", "ran", "up", "the", "hill"]
    fig = _figure("side_by_side", text_b=other)
    assert fig.layout.yaxis.ticktext[1] == "1 cat"
    assert fig.layout.yaxis2.ticktext[1] == "1 dog"
    # An overlay names the text it would draw: B's for compare_stimulus="b".
    overlay = _figure("overlay", text_b=other, compare_stimulus="b")
    assert overlay.layout.yaxis.ticktext[1] == "1 dog"


def test_a_long_text_labels_every_nth_word():
    words = pd.DataFrame({"word_id": range(300), "text": [f"w{i}" for i in range(300)]})
    ticks = plots._word_axis_ticks(words, "word_id", 600)
    assert len(ticks["tickvals"]) <= 600 / plots._WORD_TICK_PX + 1
    assert ticks["tickvals"][:2] == [0, 8]
    assert plots._word_axis_ticks(words, "duration_ms", 600) == {}
    assert plots._word_axis_ticks(words.drop(columns="text"), "word_id", 600) == {}


def test_redacted_text_stays_redacted_on_the_axis():
    fig = _figure("overlay", redact_text=True)
    assert not any("cat" in str(label) for label in fig.layout.yaxis.ticktext)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_spatial_layer_on_is_inert_on_a_chart(layout):
    fig = _figure(
        layout,
        show_heatmap=True,
        show_words=True,
        show_word_labels=True,
        show_raw_gaze=True,
        show_coordinate_grid=True,
        color_by_line=True,
        show_order=True,
        fixation_flags={"short": {"mode": "Highlight", "threshold_ms": 100.0}},
    )
    assert not _data_shapes(fig)
    assert len(_markers(fig)) >= 2


def test_spatial_axes_still_draw_the_screen():
    fig = _figure("overlay", x_field="x", y_field="y")
    assert _data_shapes(fig)  # the word boxes
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.ticktext is None


# --- the single-trial chart ---------------------------------------------------


def _static(**overrides):
    words, fixations = _reading(
        "real", TEXT, [0, 1, 3, 2, 4, 5], [180, 220, 150, 300, 90, 260]
    )
    return plots.make_scanpath_figure(
        words,
        fixations,
        canvas_width=1280,
        canvas_height=720,
        base_font_size=16,
        **{**CHART, **overrides},
    )


def test_the_static_chart_draws_its_saccades():
    fig = _static(saccade_color="#123456", show_saccade_arrows=True)
    (saccades,) = [t for t in fig.data if t.name == "saccades"]
    assert saccades.line.color == "#123456"
    assert list(saccades.x[:3]) == [1, 2, None]
    assert not [t for t in fig.data if t.marker and t.marker.symbol == "arrow"]
    assert plots._trace_layer(saccades) == "saccades"
    assert not [t for t in _static(show_saccades=False).data if t.name == "saccades"]


def test_the_static_chart_names_the_words_on_a_word_id_axis():
    fig = _static()
    assert fig.layout.yaxis.ticktext[:2] == ("0 The", "1 cat")


# --- the headless API ---------------------------------------------------------


def test_compare_scanpaths_draws_the_chart():
    words, fixations = _pair()
    fig = api.compare_scanpaths(
        words,
        fixations,
        ("real", "t"),
        ("model", "t"),
        layout="side_by_side",
        **CHART,
    )
    assert fig.layout.xaxis.range == fig.layout.xaxis2.range
    assert len(_lines(fig)) == 2
    assert list(fig.layout.yaxis.ticktext)[:2] == ["0 The", "1 cat"]


def test_a_chart_overlay_needs_no_common_screen():
    """Two corpora on different screens cannot share an overlay in screen
    pixels — but a chart places nothing in pixels, so it overlays them."""
    from scanpath_studio.experimental_setup import (
        IncomparableScreensError,
        Provenance,
        SetupSnapshot,
    )

    words, fixations = _pair()
    a = words["participant_id"] == "real"
    fa = fixations["participant_id"] == "real"

    def screen(width: int, height: int) -> SetupSnapshot:
        return SetupSnapshot(
            canvas_width=width,
            canvas_height=height,
            screen_provenance=Provenance.MEASURED,
        )

    kwargs = dict(
        words_b=words[~a],
        fixations_b=fixations[~fa],
        dataset_b="Model",
        layout="overlay",
        setup=screen(1920, 1080),
        setup_b=screen(1680, 1050),
    )
    reading_a, reading_b = ("real", "t"), ("model", "t")
    with pytest.raises(IncomparableScreensError):
        api.compare_scanpaths(words[a], fixations[fa], reading_a, reading_b, **kwargs)
    fig = api.compare_scanpaths(
        words[a], fixations[fa], reading_a, reading_b, **kwargs, **CHART
    )
    assert "xaxis2" not in fig.layout.to_plotly_json()
    assert len(_markers(fig)) == 2
