"""Compare + Animate wears the per-scanpath styles the static comparison does.

The rail's A/B style rows (fixation colour, size range, opacity, and the
saccade line's colour, dash and width) stayed live while both modes were on,
but the co-animation drew fixed palette colours and the figure-wide marker and
saccade settings. These pin every one of those controls to the replay — through
the builder, the app, the API and the CLI — and the static comparison's styles
coming back when Animate is turned off.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import api, cli, plots, tabs
from scanpath_studio.constants import COMPARE_FIXATION_OPACITY, COMPARISON_PALETTE
from tests.conftest import APP_SCRIPT

STYLE_A = dict(
    fix_color="#00ff00",
    marker_size_range=(4, 10),
    opacity=0.2,
    saccade_color="#112233",
    saccade_style="dot",
    saccade_width=1.5,
)
STYLE_B = dict(
    fix_color="#ff00ff",
    marker_size_range=(20, 40),
    opacity=0.9,
    saccade_color="#445566",
    saccade_style="dash",
    saccade_width=6.0,
)


def _frames(pid: str):
    words = pd.DataFrame(
        {
            "participant_id": [pid] * 3,
            "trial_id": ["t"] * 3,
            "text_id": ["text"] * 3,
            "word_id": [1, 2, 3],
            "text": ["One", "Two", "Three"],
            "x": [100.0, 200.0, 300.0],
            "y": [100.0] * 3,
            "width": [50.0] * 3,
            "height": [20.0] * 3,
            "line_idx": [0] * 3,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": [pid] * 3,
            "trial_id": ["t"] * 3,
            "text_id": ["text"] * 3,
            "x": [110.0, 210.0, 310.0],
            "y": [110.0] * 3,
            "duration_ms": [100.0, 200.0, 300.0],
            "timestamp_ms": [1000.0, 1200.0, 1500.0],
            "fixation_id": [1, 2, 3],
            "order_in_trial": [1, 2, 3],
            "word_id": [1, 2, 3],
        }
    )
    return words, fixations


def _settings(**overrides) -> plots.FigureSettings:
    options = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        duration_size_legend=False,
        show_saccades=True,
    )
    return plots.FigureSettings(**{**options, **overrides})


def _co_animation(**overrides):
    words, fixations = _frames("p")
    words_b, fixations_b = _frames("q")
    return plots.make_scanpath_animation(
        words,
        fixations,
        fixations_b=fixations_b,
        words_b=words_b,
        settings=_settings(**overrides),
    )


def _trail(fig, name: str):
    return next(t for t in fig.data if t.name == name and t.mode == "markers")


def _saccade_lines(fig) -> list:
    return [t.line for t in fig.data if t.mode == "lines"]


def _replay_look(fig) -> dict:
    """Each scanpath's fixation colour / sizes / opacity and saccade line."""
    lines = _saccade_lines(fig)
    look = {}
    for idx, name in enumerate(("Scanpath A", "Scanpath B")):
        marker = _trail(fig, name).marker
        look[name] = dict(
            color=marker.color,
            sizes=[round(float(v), 6) for v in marker.size],
            opacity=float(marker.opacity),
            saccade=(lines[idx].color, lines[idx].dash, float(lines[idx].width)),
        )
    return look


def _static_look(fig) -> dict:
    """:func:`_replay_look` for the static comparison, A's traces first."""
    markers = [t for t in fig.data if t.mode in ("markers", "markers+text")]
    lines = _saccade_lines(fig)
    return {
        name: dict(
            color=trace.marker.color,
            sizes=[round(float(v), 6) for v in trace.marker.size],
            opacity=float(trace.marker.opacity),
            saccade=(line.color, line.dash, float(line.width)),
        )
        for name, trace, line in zip(
            ("Scanpath A", "Scanpath B"), markers, lines, strict=True
        )
    }


def _static_comparison(**overrides):
    words, fixations = _frames("p")
    words_b, fixations_b = _frames("q")
    return plots.make_comparison_figure(
        pd.concat([words, words_b], ignore_index=True),
        pd.concat([fixations, fixations_b], ignore_index=True),
        ("p", "t"),
        ("q", "t"),
        settings=_settings(label_a="Scanpath A", label_b="Scanpath B", **overrides),
    )


# --- the builder ---------------------------------------------------------------


def test_unstyled_co_animation_keeps_the_comparison_palette():
    look = _replay_look(_co_animation())
    assert look["Scanpath A"]["color"] == COMPARISON_PALETTE[0]
    assert look["Scanpath B"]["color"] == COMPARISON_PALETTE[1]
    assert look["Scanpath A"]["opacity"] == COMPARE_FIXATION_OPACITY
    # One shared range: equal durations draw equal sizes on either side.
    assert look["Scanpath A"]["sizes"] == look["Scanpath B"]["sizes"]


def test_co_animation_matches_the_static_comparison_styles():
    styles = dict(style_a=STYLE_A, style_b=STYLE_B)
    assert _replay_look(_co_animation(**styles)) == _static_look(
        _static_comparison(**styles)
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("fix_color", "#123456"),
        ("marker_size_range", (30, 40)),
        ("opacity", 0.3),
        ("saccade_color", "#654321"),
        ("saccade_style", "dashdot"),
        ("saccade_width", 7.0),
    ],
)
@pytest.mark.parametrize("side", ["style_a", "style_b"])
def test_every_style_control_changes_the_co_animation(side, key, value):
    name = "Scanpath A" if side == "style_a" else "Scanpath B"
    other = "Scanpath B" if side == "style_a" else "Scanpath A"
    before = _replay_look(_co_animation())
    after = _replay_look(_co_animation(**{side: {key: value}}))
    assert after[name] != before[name]
    assert after[other] == before[other]


def test_hollow_style_reaches_the_co_animation():
    marker = _trail(_co_animation(style_b={"hollow": True}), "Scanpath B").marker
    assert marker.color == "rgba(0,0,0,0)"
    assert _trail(_co_animation(), "Scanpath B").marker.color != "rgba(0,0,0,0)"


def test_frames_carry_the_per_scanpath_saccade_line():
    fig = _co_animation(style_a=STYLE_A, style_b=STYLE_B)
    frame_lines = {
        (trace.line.color, trace.line.dash, float(trace.line.width))
        for frame in fig.frames
        for trace in frame.data
        if trace.mode == "lines"
    }
    assert frame_lines == {("#112233", "dot", 1.5), ("#445566", "dash", 6.0)}


def test_order_numbers_take_the_scanpath_colour():
    fig = _co_animation(style_a=STYLE_A, style_b=STYLE_B, show_order=True)
    colours = [
        t.textfont.color for t in fig.data if t.mode == "text" and t.name is None
    ]
    assert colours == ["#00ff00", "#ff00ff"]


def test_size_ranges_share_one_duration_scale():
    """Equal durations take the same fraction of each scanpath's own range —
    under the relative scale too, which spans both readings' durations."""
    for scale in ("sqrt", "relative"):
        look = _replay_look(
            _co_animation(
                style_a={"marker_size_range": (4, 10)},
                style_b={"marker_size_range": (20, 40)},
                marker_size_scale=scale,
            )
        )
        frac_a = (np.array(look["Scanpath A"]["sizes"]) - 4) / 6
        frac_b = (np.array(look["Scanpath B"]["sizes"]) - 20) / 20
        np.testing.assert_allclose(frac_a, frac_b, atol=1e-6)


def test_duration_key_only_while_the_ranges_agree():
    shared = _co_animation(
        duration_size_legend=True,
        style_a={"marker_size_range": (6, 12)},
        style_b={"marker_size_range": (6, 12)},
    )
    split = _co_animation(
        duration_size_legend=True,
        style_a={"marker_size_range": (4, 10)},
        style_b={"marker_size_range": (20, 40)},
    )

    def has_key(fig):
        return any(a.name == plots._SIZE_KEY_NAME for a in fig.layout.annotations or ())

    assert has_key(shared)
    assert not has_key(split)


def test_lone_replay_ignores_the_per_scanpath_styles():
    words, fixations = _frames("p")
    cfg = _settings(fixation_opacity=0.55, saccade_width=3.0)
    plain = plots.make_scanpath_animation(words, fixations, settings=cfg)
    styled = plots.make_scanpath_animation(
        words, fixations, settings=cfg.with_overrides(style_a=STYLE_A)
    )
    assert plain.to_json() == styled.to_json()


def test_style_b_flags_apply_when_no_b_flags_are_given():
    words, fixations = _frames("p")
    words_b, fixations_b = _frames("q")
    discard = {"short": {"mode": "Discard", "threshold_ms": 150}}
    fig = plots.make_scanpath_animation(
        words,
        fixations,
        fixations_b=fixations_b,
        words_b=words_b,
        settings=_settings(style_b={"fixation_flags": discard}),
    )
    assert len(_trail(fig, "Scanpath A").x) == 3
    assert len(_trail(fig, "Scanpath B").x) == 2


# --- the API and the CLI -------------------------------------------------------


def test_api_co_animation_takes_style_a_and_style_b():
    assert {"style_a", "style_b"} <= set(api.figure_options("animation"))
    words, fixations = _frames("p")
    words_b, fixations_b = _frames("q")
    fig = api.animate_scanpath(
        pd.concat([words, words_b], ignore_index=True),
        pd.concat([fixations, fixations_b], ignore_index=True),
        "p",
        "t",
        trial_b=("q", "t"),
        style_a=STYLE_A,
        style_b=STYLE_B,
    )
    assert _trail(fig, "Scanpath A").marker.color == "#00ff00"
    assert _trail(fig, "Scanpath B").marker.color == "#ff00ff"


def test_api_co_animation_refuses_a_saccade_class_style():
    words, fixations = _frames("p")
    words_b, fixations_b = _frames("q")
    with pytest.raises(ValueError, match="saccade-class"):
        api.animate_scanpath(
            pd.concat([words, words_b], ignore_index=True),
            pd.concat([fixations, fixations_b], ignore_index=True),
            "p",
            "t",
            trial_b=("q", "t"),
            style_b={"saccade_classes": ["forward"]},
        )


def test_cli_animate_compare_forwards_the_styles(tmp_path, monkeypatch):
    seen = {}
    real = api.animate_scanpath

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "animate_scanpath", spy)
    participant = "l37_1129"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            participant,
            "-t",
            "l37_1129_2_1_1_Ele_r0",
            "--compare-with",
            f"{participant}:l37_1129_2_1_3_Adv_r0",
            "--animate",
            "--style-a",
            "fix_color=#00ff00,opacity=0.2",
            "--style-b",
            "fix_color=#ff00ff,marker_size_range=20:40",
            "-o",
            str(tmp_path / "co.html"),
        ]
    )
    assert seen["style_a"]["fix_color"] == "#00ff00"
    assert seen["style_b"]["marker_size_range"] == (20, 40)


# --- the app ---------------------------------------------------------------------

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_app_co_animation_wears_the_rail_styles_and_static_gets_them_back(
    monkeypatch,
):
    """Through the real rail: the A/B rows reach the co-animation, stay enabled,
    and the static comparison draws the same styles once Animate is off."""
    seen: dict[str, list] = {"anim": [], "compare": []}
    real_anim = plots.build_scanpath_replay
    real_compare = plots.make_comparison_figure

    def anim(words, fixations, settings, fixations_b, words_b, anim_key):
        seen["anim"].append(settings)
        return real_anim(
            words,
            fixations,
            settings=settings,
            fixations_b=fixations_b,
            words_b=words_b,
        )

    def compare(words, fixations, trial_a, trial_b, **kwargs):
        fig = real_compare(words, fixations, trial_a, trial_b, **kwargs)
        seen["compare"].append(fig)
        return fig

    monkeypatch.setattr(tabs, "_cached_scanpath_animation", anim)
    tabs._cached_replay_view.clear()
    monkeypatch.setattr(tabs, "make_comparison_figure", compare)

    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    assert not at.exception, at.exception
    at.session_state["single_compare_toggle"] = True
    at.session_state["single_animate"] = True
    at.session_state["cmp0_fix_color"] = "#00ff00"
    at.session_state["cmp1_fix_color"] = "#ff00ff"
    at.session_state["cmp0_marker_size_range"] = (4, 10)
    at.session_state["cmp1_marker_size_range"] = (20, 40)
    at.session_state["cmp0_opacity"] = 0.2
    at.session_state["cmp1_opacity"] = 0.9
    at.session_state["cmp1_saccade_color"] = "#445566"
    at.session_state["cmp1_saccade_style"] = "Dashed"
    at.session_state["cmp1_saccade_width"] = 6.0
    at.run(timeout=90)
    assert not at.exception, at.exception

    assert seen["anim"], "Compare + Animate did not build a replay"
    settings = seen["anim"][-1]
    assert settings.style_a["fix_color"] == "#00ff00"
    assert tuple(settings.style_a["marker_size_range"]) == (4, 10)
    assert settings.style_a["opacity"] == pytest.approx(0.2)
    assert settings.style_b["fix_color"] == "#ff00ff"
    assert tuple(settings.style_b["marker_size_range"]) == (20, 40)
    assert settings.style_b["opacity"] == pytest.approx(0.9)
    assert settings.style_b["saccade_color"] == "#445566"
    assert settings.style_b["saccade_style"] == "dash"
    assert settings.style_b["saccade_width"] == pytest.approx(6.0)
    # The filters travel as `fixation_flags_b`, not inside the style.
    assert not set(settings.style_b) & plots.COMPARE_FILTER_STYLE_KEYS
    # Every A/B style row is live under Compare + Animate.
    for key in ("cmp0_fix_color", "cmp1_fix_color"):
        assert not at.color_picker(key=key).proto.disabled

    # Animate off: the static comparison draws the same, stored, styles.
    at.session_state["single_animate"] = False
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert seen["compare"], "Compare without Animate did not build a comparison"
    static = seen["compare"][-1]
    markers = [t for t in static.data if t.mode in ("markers", "markers+text")]
    assert [m.marker.color for m in markers][:2] == ["#00ff00", "#ff00ff"]
    assert [float(m.marker.opacity) for m in markers][:2] == pytest.approx([0.2, 0.9])
    assert at.session_state["cmp1_marker_size_range"] == (20, 40)
