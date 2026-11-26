"""The replay's growing current fixation and fading earlier ones."""

from __future__ import annotations

import pytest

from scanpath_studio import plots, replay_frames
from scanpath_studio.synthetic import load_synthetic_data


def _replay(**options):
    words, fixations = load_synthetic_data()
    fig, _ = plots.build_scanpath_replay(
        words,
        fixations,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        anim_grid_step_ms=10,
        **options,
    )
    run = fig.layout.meta[replay_frames.READINGS][0]
    return fig, run


def _base_trail(fig, run):
    """The trail as the figure's own trace, before any frame restyles it."""
    return fig.data[fig.frames[0].traces[run["points"][0]]]


def _current(fig, run, k):
    """The index of the fixation frame ``k`` shows as current, and the trail."""
    trail = fig.frames[k].data[run["points"][0]]
    return sum(x is not None for x in trail.x) - 1, trail


def test_off_by_default_every_frame_keeps_the_full_marker():
    fig, run = _replay()
    full = list(_base_trail(fig, run).marker.size)
    for k in range(len(fig.frames)):
        _, trail = _current(fig, run, k)
        assert list(trail.marker.size) == full
        assert not isinstance(trail.marker.opacity, tuple | list)


def test_the_current_fixation_grows_to_its_full_size_over_its_duration():
    fig, run = _replay(grow_fixations=True)
    full = list(_base_trail(fig, run).marker.size)
    times = fig.layout.meta["scanpath_frame_times_ms"]
    for k, ms in enumerate(times):
        i, trail = _current(fig, run, k)
        share = (ms - run["times"][i]) / run["durations"][i]
        expected = full[i] * min(1.0, max(replay_frames.GROW_FLOOR, share))
        assert trail.marker.size[i] == pytest.approx(expected)
        # Earlier fixations are already full grown.
        assert list(trail.marker.size[:i]) == full[:i]
    # A fixation is small at its onset.
    first = next(k for k, ms in enumerate(times) if ms == run["times"][1])
    assert _current(fig, run, first)[1].marker.size[1] < full[1]


def test_earlier_fixations_fade_and_the_current_one_does_not():
    fig, run = _replay(fade_fixations=True)
    opacity = _base_trail(fig, run).marker.opacity
    for k in range(len(fig.frames)):
        i, trail = _current(fig, run, k)
        shown = list(trail.marker.opacity)
        assert shown[:i] == pytest.approx([opacity * replay_frames.FADE_FACTOR] * i)
        assert shown[i] == pytest.approx(opacity)


def test_a_glyph_trail_neither_grows_nor_fades():
    fig, run = _replay(
        grow_fixations=True, fade_fixations=True, fixation_symbol="heart"
    )
    assert fig.frames  # builds, and leaves the text layers untouched
    for k in range(len(fig.frames)):
        for slot in run["trails"]:
            assert fig.frames[k].data[slot].mode == "text"


def test_the_static_builder_refuses_the_replay_options():
    words, fixations = load_synthetic_data()
    with pytest.raises(TypeError):
        from scanpath_studio import api

        api.plot_scanpath(words, fixations, grow_fixations=True)


@pytest.mark.parametrize(
    ("state", "greyed"),
    [
        ({}, False),
        ({"global_show_fix": False}, True),
        ({"global_fixation_symbol": "heart"}, True),
    ],
    ids=["markers", "no-fixations", "glyph"],
)
def test_the_playback_checkboxes_grey_when_they_would_do_nothing(state, greyed):
    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.query_params["ui"] = "full"
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    at.toggle(key="single_animate").set_value(True).run()
    assert not at.exception
    for key in ("global_anim_grow_fixations", "global_anim_fade_fixations"):
        assert at.checkbox(key=key).disabled is greyed


def test_fading_dims_the_earlier_numbers_and_every_saccade():
    plain, _ = _replay(show_saccade_arrows=True)
    fig, run = _replay(fade_fixations=True, show_saccade_arrows=True)
    saccade_traces = [t for t in fig.data if t.meta == "saccades"]
    assert saccade_traces
    for faded, full in zip(
        saccade_traces, [t for t in plain.data if t.meta == "saccades"], strict=True
    ):
        assert faded.opacity == pytest.approx(full.opacity * replay_frames.FADE_FACTOR)
    faded_color, full_color = run["order_colors"]
    assert faded_color.endswith(f",{replay_frames.FADE_FACTOR})")
    for k in range(len(fig.frames)):
        i, _ = _current(fig, run, k)
        colors = list(fig.frames[k].data[run["order"]].textfont.color)
        assert colors[:i] == [faded_color] * i
        assert set(colors[i:]) == {full_color}


def test_a_named_number_colour_keeps_its_numbers_unfaded():
    fig, run = _replay(fade_fixations=True, order_font_color="black")
    assert "order" not in run
    assert fig.frames
