"""The replay's growing current fixation and fading earlier ones."""

from __future__ import annotations

import pytest

from scanpath_studio import plots, replay_frames
from scanpath_studio.constants import DEFAULT_FADE_OPACITY, DEFAULT_GROW_START
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
        expected = full[i] * min(1.0, max(DEFAULT_GROW_START, share))
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
        assert shown[:i] == pytest.approx([opacity * DEFAULT_FADE_OPACITY] * i)
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
        assert faded.opacity == pytest.approx(full.opacity * DEFAULT_FADE_OPACITY)
    faded_color, full_color = run["order_colors"]
    assert faded_color.endswith(f",{DEFAULT_FADE_OPACITY})")
    for k in range(len(fig.frames)):
        i, _ = _current(fig, run, k)
        colors = list(fig.frames[k].data[run["order"]].textfont.color)
        assert colors[:i] == [faded_color] * i
        assert set(colors[i:]) == {full_color}


def test_a_named_number_colour_keeps_its_numbers_unfaded():
    fig, run = _replay(fade_fixations=True, order_font_color="black")
    assert "order" not in run
    assert fig.frames


@pytest.mark.parametrize(("grow_start", "fade_opacity"), [(0.5, 0.0), (1.0, 0.75)])
def test_the_start_size_and_faded_opacity_are_the_ones_asked_for(
    grow_start, fade_opacity
):
    fig, run = _replay(
        grow_fixations=True,
        fade_fixations=True,
        grow_start=grow_start,
        fade_opacity=fade_opacity,
    )
    full = list(_base_trail(fig, run).marker.size)
    opacity = _base_trail(fig, run).marker.opacity
    onsets = fig.layout.meta["scanpath_frame_times_ms"]
    k = next(k for k, ms in enumerate(onsets) if ms == run["times"][1])
    i, trail = _current(fig, run, k)
    assert i == 1
    assert trail.marker.size[1] == pytest.approx(full[1] * grow_start)
    assert trail.marker.opacity[0] == pytest.approx(opacity * fade_opacity)


@pytest.mark.parametrize(
    ("name", "value"),
    [("grow_start", 0.0), ("grow_start", 1.5), ("fade_opacity", -0.1)],
)
def test_a_share_outside_its_range_is_refused(name, value):
    from scanpath_studio import api

    words, fixations = load_synthetic_data()
    with pytest.raises(ValueError, match=name):
        api.animate_scanpath(words, fixations, **{name: value})


def test_a_flag_highlight_grows_and_fades_with_its_marker():
    flags = {"short": {"mode": "Highlight", "threshold_ms": 10_000}}
    fig, run = _replay(grow_fixations=True, fade_fixations=True, fixation_flags=flags)
    ring_slot = run["trails"][-1]
    assert ring_slot != run["points"][0]
    onsets = fig.layout.meta["scanpath_frame_times_ms"]
    k = next(k for k, ms in enumerate(onsets) if ms == run["times"][2])
    ring = fig.frames[k].data[ring_slot]
    assert ring.marker.size[2] == pytest.approx(13 * DEFAULT_GROW_START)
    assert list(ring.marker.size[:2]) == [13, 13]
    assert ring.marker.opacity[0] == pytest.approx(DEFAULT_FADE_OPACITY)
    assert ring.marker.opacity[2] == 1.0
