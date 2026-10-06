"""#374 F29 — Share → Code writes only options that change the figure, spells
"no marking" as Python's ``None``, and never names a palette the figure's
colours don't match."""

from __future__ import annotations

from scanpath_studio import api
from scanpath_studio import code_snippet as cs
from scanpath_studio.constants import palette_settings

DEMO = cs.SnippetSource(kind=cs.SOURCE_DEMO, label="Bundled Demo")


def _code(**figure) -> cs.ReproductionCode:
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), **figure},
        participant="p1",
        trial="t1",
    )
    return cs.reproduction_code(DEMO, state)


def test_the_reviewed_figure_has_no_option_that_does_nothing():
    """The figure from the review: *High contrast* applied, then two colours
    changed by hand, the highlight off, and the heatmap and boxes off."""
    palette = palette_settings("High contrast")
    figure = {
        **{k: v for k, v in palette.items() if k != "word_label_color"},
        "text_color": palette["word_label_color"],
        "fixation_color": "#0072B2",
        "saccade_color": "#CC79A7",
        "highlight_column": None,
        "critical_span_style": "None",
    }
    code = _code(**figure)
    for inert in (
        "critical_span_style",
        "highlight_text_color",
        "saccade_class_colors",
        "heatmap_colorscale",
        "fixation_colorscale",
    ):
        assert inert not in code.python, inert
    assert "highlight_column=None" in code.python
    assert "--palette" not in code.cli


def test_no_marking_is_written_as_none():
    code = _code(critical_span_style="None")
    assert "critical_span_style=None," in code.python
    assert "'None'" not in code.python
    assert "--critical-span-style none" in code.cli


def test_styling_of_a_layer_that_is_off_is_left_out_and_kept_when_on():
    off = _code(heatmap_colorscale="Greens", order_font_size=20)
    assert "heatmap_colorscale" not in off.python
    assert "order_font_size" not in off.python
    on = _code(
        show_heatmap=True,
        show_order=True,
        heatmap_colorscale="Greens",
        order_font_size=20,
    )
    assert "heatmap_colorscale='Greens'" in on.python
    assert "order_font_size=20" in on.python
    assert "--heatmap-colorscale Greens" in on.cli


def test_explicit_still_writes_everything():
    kwargs = cs.figure_kwargs(
        {**api.figure_options("static"), "heatmap_colorscale": "Greens"},
        "static",
        explicit=True,
    )
    assert kwargs["heatmap_colorscale"] == "Greens"
