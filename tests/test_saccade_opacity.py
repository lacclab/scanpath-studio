"""The saccade lines' opacity — one setting, on every figure.

↗️ Saccades ▾ → *Opacity* (`global_saccade_opacity` → `saccade_opacity`) fades
the saccade lines and their direction arrows together, on the static figure,
the replay and both scanpaths of a comparison. The link, the settings file,
the CLI and the snippet carry it through the shared contract tests
(`test_session_key_contract`, `test_render_every_option`).
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import plots
from tests.test_rail_mode_choices import _frames, _rail, _static

SACCADE_TRACES = ("saccades", "saccade direction")


def _saccade_opacities(fig) -> dict:
    """``{trace name: opacity}`` for the saccade lines and arrows (an unset
    opacity reads as Plotly's 1)."""
    return {
        t.name: (1.0 if t.opacity is None else t.opacity)
        for t in fig.data
        if t.name in SACCADE_TRACES
    }


def _kwargs(**over) -> dict:
    return dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        show_saccade_arrows=True,
        duration_size_legend=False,
        **over,
    )


def test_the_static_figure_fades_lines_and_arrows():
    words, fixations = _frames()
    plain = plots.make_scanpath_figure(words, fixations, **_kwargs())
    faded = plots.make_scanpath_figure(words, fixations, **_kwargs(saccade_opacity=0.4))
    assert _saccade_opacities(plain) == {"saccades": 1.0, "saccade direction": 1.0}
    assert _saccade_opacities(faded) == {"saccades": 0.4, "saccade direction": 0.4}


def test_each_saccade_type_is_faded_too():
    words, fixations = _frames()
    fig = plots.make_scanpath_figure(
        words,
        fixations,
        **_kwargs(saccade_opacity=0.4, saccade_color_mode="By type"),
    )
    typed = [t for t in fig.data if t.legendgroup == "saccade_type"]
    assert typed and all(t.opacity == 0.4 for t in typed)


def _settings(**over) -> plots.FigureSettings:
    return plots.FigureSettings(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        show_saccade_arrows=True,
        saccade_opacity=0.4,
        **over,
    )


def test_the_replay_keeps_the_opacity_through_its_frames():
    words, fixations = _frames()
    fig = plots.make_scanpath_animation(words, fixations, settings=_settings())
    lines = [t for t in fig.data if t.mode == "lines"]
    arrows = [t for t in fig.data if t.name == "saccade direction"]
    assert lines and all(t.opacity == 0.4 for t in lines)
    assert arrows and all(t.opacity == 0.4 for t in arrows)
    # A frame restates positions and the line's style, never the opacity, so
    # the base trace's holds for the whole replay.
    for frame in fig.frames:
        assert all("opacity" not in trace.to_plotly_json() for trace in frame.data)


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_both_scanpaths_of_a_comparison_share_it(layout):
    words, fixations = _frames()
    fig = plots.make_comparison_figure(
        pd.concat([words, words.assign(participant_id="q")]),
        pd.concat([fixations, fixations.assign(participant_id="q")]),
        ("p", "t"),
        ("q", "t"),
        settings=_settings(layout=layout),
    )
    lines = [t for t in fig.data if t.mode == "lines"]
    arrows = [
        t
        for t in fig.data
        if t.mode == "markers" and t.marker is not None and t.marker.symbol == "arrow"
    ]
    assert len(lines) >= 2 and all(t.opacity == 0.4 for t in lines)
    assert len(arrows) == 2 and all(t.opacity == 0.4 for t in arrows)


def test_the_rail_row_drives_the_figure():
    at = _rail(global_saccade_opacity=0.4, global_show_saccade_arrows=True)
    assert at.slider(key="global_saccade_opacity").value == pytest.approx(0.4)
    assert at.session_state["_viz"]["saccade_opacity"] == pytest.approx(0.4)
    assert set(_saccade_opacities(_static(at)).values()) == {0.4}
    # The typed box writes the same key.
    at.number_input(key="global_saccade_opacity__num").set_value(0.25).run(timeout=60)
    assert at.session_state["global_saccade_opacity"] == pytest.approx(0.25)


@pytest.mark.parametrize("opacity", [0.0, 0.05, 1.0])
def test_api_cli_rail_and_saved_file_support_the_same_opacity_interval(opacity):
    from scanpath_studio import api, cli
    from scanpath_studio.constants import OPACITY_OPTIONS
    from scanpath_studio.url_state import _URL_BOUNDED
    from tests.test_plot_config_restore import _restore_app, _run

    both = {name: opacity for name in OPACITY_OPTIONS}
    args = cli._render_parser().parse_args(
        [x for option in OPACITY_OPTIONS.values() for x in (option.flag, str(opacity))]
    )
    state = _run(_restore_app, _config={"coloring": both}).session_state
    rail = _rail(**{o.state_key: opacity for o in OPACITY_OPTIONS.values()})
    for name, option in OPACITY_OPTIONS.items():
        assert getattr(args, name) == state[option.state_key] == opacity
        assert _URL_BOUNDED[option.state_key] == (0.0, 1.0)
        assert rail.slider(key=option.state_key).value == opacity
    figure = api.plot_scanpath(*_frames(), **both)
    assert set(_saccade_opacities(figure).values()) == {opacity}
    assert (
        next(t for t in figure.data if t.name.lower() == "fixations").marker.opacity
        == opacity
    )


@pytest.mark.parametrize("value", ["-0.01", "1.01", "nan", "inf"])
def test_opacity_rejects_nonfinite_and_out_of_range_values_before_reading(value):
    from scanpath_studio import api, cli

    with pytest.raises(SystemExit):
        cli._render_parser().parse_args(["--fixation-opacity", value])
    with pytest.raises(ValueError, match="saccade_opacity"):
        api.plot_scanpath(*_frames(), saccade_opacity=float(value))
