"""Seven design choices the user makes about the figure.

Heatmap opacity, the title's and caption's text, the plot frame, the saccade
arrowheads, the fixation markers' outline, the coordinate grid's labels and
each colour bar's thickness and length. Each default is the value the figure
draws with when nothing is set; the link, the settings file, the CLI and the
snippet carry them through the shared contract tests
(`test_session_key_contract`, `test_render_every_option`).
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import plots
from scanpath_studio.export import annotate_figure, figure_text_style
from tests.test_rail_mode_choices import _frames, _rail, _static


def _kwargs(**over) -> dict:
    return dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        duration_size_legend=False,
        **over,
    )


def _static_fig(**over):
    words, fixations = _frames()
    return plots.make_scanpath_figure(words, fixations, **_kwargs(**over))


def _heatmap_shapes(fig) -> list:
    return [s for s in fig.layout.shapes or () if s.name and s.name.endswith("heatmap")]


def _frame_shapes(fig) -> list:
    return [s for s in fig.layout.shapes or () if s.name and s.name.endswith("frame")]


def _marker_trace(fig):
    return next(t for t in fig.data if t.name == "Fixations")


# --- heatmap opacity -----------------------------------------------------------


def test_each_heatmap_style_keeps_its_own_opacity_until_one_is_set():
    boxes = _heatmap_shapes(_static_fig(show_heatmap=True))
    assert boxes and {s.opacity for s in boxes} == {0.5}
    interpolated = _static_fig(show_heatmap=True, heatmap_style="Smoothed")
    (grid,) = [t for t in interpolated.data if t.type == "heatmap"]
    assert grid.opacity == 0.45

    set_boxes = _heatmap_shapes(_static_fig(show_heatmap=True, heatmap_opacity=0.8))
    assert {s.opacity for s in set_boxes} == {0.8}
    set_grid = _static_fig(
        show_heatmap=True, heatmap_style="Smoothed", heatmap_opacity=0.8
    )
    assert [t.opacity for t in set_grid.data if t.type == "heatmap"] == [0.8]


def test_a_comparison_heatmap_matches_the_single_figure():
    """Its word boxes take the single figure's 0.5, not an opacity of their own."""
    words, fixations = _frames()
    fig = plots.make_comparison_figure(
        pd.concat([words, words.assign(participant_id="q")]),
        pd.concat([fixations, fixations.assign(participant_id="q")]),
        ("p", "t"),
        ("q", "t"),
        settings=plots.FigureSettings(**_kwargs(show_heatmap=True)),
    )
    assert {s.opacity for s in _heatmap_shapes(fig)} == {0.5}


# --- the frame, the arrowheads, the outline, the grid -----------------------------


def test_the_frame_can_be_recoloured_or_left_out():
    (frame,) = _frame_shapes(_static_fig())
    assert frame.line.color == "#000000"
    (grey,) = _frame_shapes(_static_fig(plot_frame_color="#999999"))
    assert grey.line.color == "#999999"
    assert _frame_shapes(_static_fig(show_plot_frame=False)) == []


def test_the_replay_and_compare_take_the_frame_too():
    import scanpath_studio as sps

    words, fixations = _frames()
    pid, tid = fixations[["participant_id", "trial_id"]].iloc[0]
    figs = {
        "replay": lambda **o: sps.animate_scanpath(words, fixations, pid, tid, **o),
        "compare": lambda **o: sps.compare_scanpaths(
            words, fixations, (pid, tid), (pid, tid), **o
        ),
        "side by side": lambda **o: sps.compare_scanpaths(
            words, fixations, (pid, tid), (pid, tid), layout="side_by_side", **o
        ),
    }
    for name, build in figs.items():
        drawn = _frame_shapes(build(plot_frame_color="#999999"))
        assert drawn and {s.line.color for s in drawn} == {"#999999"}, name
        assert _frame_shapes(build(show_plot_frame=False)) == [], name


def test_the_arrowheads_take_their_size():
    def arrow_size(**over):
        fig = _static_fig(show_saccade_arrows=True, **over)
        (arrows,) = [t for t in fig.data if t.name == "saccade direction"]
        return arrows.marker.size

    assert arrow_size() == 12
    assert arrow_size(saccade_arrow_size=20.0) == 20


def test_the_marker_outline_takes_its_width_and_colour():
    plain = _marker_trace(_static_fig()).marker.line
    assert (plain.width, plain.color) == (0.5, "#111111")
    line = _marker_trace(
        _static_fig(fixation_outline_width=2.0, fixation_outline_color="#336699")
    ).marker.line
    assert (line.width, line.color) == (2.0, "#336699")
    assert _marker_trace(_static_fig(fixation_outline_width=0.0)).marker.line.width == 0


def test_the_grid_labels_take_their_size_and_the_margin_grows_with_them():
    plain = _static_fig(show_coordinate_grid=True)
    big = _static_fig(show_coordinate_grid=True, coordinate_grid_font_size=30)
    assert plain.layout.xaxis.tickfont.size == 18
    assert big.layout.xaxis.tickfont.size == 30
    assert big.layout.margin.l > plain.layout.margin.l
    # A smaller label keeps the default's room.
    small = _static_fig(show_coordinate_grid=True, coordinate_grid_font_size=10)
    assert small.layout.margin.l == plain.layout.margin.l


# --- colour bars -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("orientation", "auto_length"), [("Vertical", 0.33), ("Horizontal", 0.6)]
)
def test_a_colour_bar_takes_its_thickness_and_length(orientation, auto_length):
    def bar(**over):
        fig = _static_fig(
            color_by="duration_ms", fixation_colorbar_orientation=orientation, **over
        )
        return _marker_trace(fig).marker.colorbar

    plain = bar()
    assert (plain.thickness, plain.len) == (14, auto_length)
    sized = bar(fixation_colorbar_thickness=24, fixation_colorbar_length=0.8)
    assert (sized.thickness, sized.len) == (24, 0.8)


def test_the_heatmap_bar_is_styled_apart():
    fig = _static_fig(
        show_heatmap=True, heatmap_colorbar_thickness=30, heatmap_colorbar_length=0.9
    )
    bars = [t.marker.colorbar for t in fig.data if t.marker and t.marker.showscale]
    assert [(b.thickness, b.len) for b in bars] == [(30, 0.9)]


# --- title and caption ---------------------------------------------------------------


def test_the_title_and_caption_take_their_size_and_colour():
    def stamped(**style):
        fig = _static_fig()
        height = fig.layout.height
        annotate_figure(fig, title="T", caption="C", **style)
        (caption,) = [a for a in fig.layout.annotations if a.text == "C"]
        return fig, caption, fig.layout.height - height

    fig, caption, grown = stamped()
    assert fig.layout.title.font.size == 20
    assert (caption.font.size, caption.font.color) == (13, "#555555")
    # The bands the defaults take: 46 px for the title, 22 + 12 for
    # one caption line.
    assert grown == 46 + 22 + 12

    fig, caption, bigger = stamped(
        title_font_size=32, caption_font_size=20, caption_color="#222222"
    )
    assert fig.layout.title.font.size == 32
    assert (caption.font.size, caption.font.color) == (20, "#222222")
    assert bigger > grown


def test_the_text_style_reads_settings_or_the_apps_dict():
    settings = plots.FigureSettings(**_kwargs(title_font_size=30))
    assert figure_text_style(settings)["title_font_size"] == 30
    assert figure_text_style({"caption_color": "#123456"}) == {
        "title_font_size": 20,
        "caption_font_size": 13,
        "caption_color": "#123456",
        "show_credit": False,
    }


# --- the rail ------------------------------------------------------------------------


def test_the_rail_rows_drive_the_figure():
    at = _rail(
        global_show_saccade_arrows=True,
        global_saccade_arrow_size=20.0,
        global_fixation_outline_width=2.0,
        global_fixation_outline_color="#336699",
        global_show_plot_frame=False,
        global_title_font_size=28,
        global_caption_color="#222222",
    )
    viz = at.session_state["_viz"]
    assert viz["saccade_arrow_size"] == 20.0
    assert viz["title_font_size"] == 28 and viz["caption_color"] == "#222222"
    fig = _static(at)
    assert _frame_shapes(fig) == []
    line = _marker_trace(fig).marker.line
    assert (line.width, line.color) == (2.0, "#336699")


def test_auto_leaves_the_heatmap_opacity_and_bar_length_unset():
    at = _rail()
    viz = at.session_state["_viz"]
    assert viz["heatmap_opacity"] is None
    assert viz["fixation_colorbar_length"] is None
    at = _rail(
        global_show_heatmap=True,
        global_heatmap_opacity_auto=False,
        global_heatmap_opacity=0.8,
        global_heatmap_colorbar_length_auto=False,
        global_heatmap_colorbar_length=0.5,
    )
    viz = at.session_state["_viz"]
    assert viz["heatmap_opacity"] == pytest.approx(0.8)
    assert viz["heatmap_colorbar_length"] == pytest.approx(0.5)
    # The box keeps its number while Auto is ticked again.
    at.checkbox(key="global_heatmap_opacity_auto").check().run(timeout=60)
    assert at.session_state["_viz"]["heatmap_opacity"] is None
    assert at.session_state["global_heatmap_opacity"] == pytest.approx(0.8)


def test_the_replay_key_ignores_what_no_frame_draws():
    """The heatmap's opacity and the title/caption styling (and credit) never reach a
    replay frame, so changing one rebuilds none."""
    from scanpath_studio import tabs

    words, fixations = _frames()

    def key(**figure):
        return tabs._plan_replay(
            words,
            fixations,
            None,
            None,
            "p",
            "t",
            None,
            None,
            settings=plots.FigureSettings.from_mapping(
                figure, canvas_width=800, canvas_height=600, base_font_size=16
            ),
            viz_settings={"critical_span_style": "None"},
            playback_speed=1.0,
        ).key

    assert (
        key(
            heatmap_opacity=0.8,
            title_font_size=30,
            show_credit=True,
            caption_font_size=18,
            caption_color="#222222",
        )
        == key()
    )
    # The arrowheads are drawn by the replay, so they are part of it.
    assert key(saccade_arrow_size=20.0) != key()


def test_the_credit_line_grows_the_figure_below_the_caption():
    import plotly.graph_objects as go

    from scanpath_studio.citation import CREDIT_LINE
    from scanpath_studio.export import annotate_figure

    fig = go.Figure(layout=dict(height=400, margin=dict(b=20)))
    annotate_figure(fig, caption="A caption", show_credit=True)
    caption, credit = fig.layout.annotations
    assert credit.text == CREDIT_LINE
    assert credit.xanchor == "right"
    # Its own band, below the caption's.
    assert credit.yshift < caption.yshift
    plain = go.Figure(layout=dict(height=400, margin=dict(b=20)))
    annotate_figure(plain, caption="A caption")
    assert fig.layout.height - plain.layout.height == fig.layout.margin.b - (
        plain.layout.margin.b
    )
    assert fig.layout.height > plain.layout.height


@pytest.mark.parametrize("builder", ["static", "animation", "overlay", "side_by_side"])
def test_every_api_builder_draws_the_credit_only_when_asked(builder):
    from scanpath_studio import api
    from scanpath_studio.citation import CREDIT_LINE

    data = api.load_sample_data(names="canonical")
    trials = api.list_trials(data.words, data.fixations)
    a = tuple(trials.iloc[0])
    b = tuple(trials.iloc[1])

    def texts(**kw):
        if builder == "static":
            fig = api.plot_scanpath(data.words, data.fixations, *a, **kw)
        elif builder == "animation":
            fig = api.animate_scanpath(data.words, data.fixations, *a, **kw)
        else:
            fig = api.compare_scanpaths(
                data.words, data.fixations, a, b, layout=builder, **kw
            )
        return [annotation.text for annotation in fig.layout.annotations]

    assert CREDIT_LINE not in texts()
    assert CREDIT_LINE in texts(show_credit=True)
