"""One screen per scanpath in a comparison.

Every screen of a multipart trial is its own coordinate space. A comparison
that handed a whole parent trial to the builder drew every page in one
scanpath, with a saccade from the last fixation on page 1 to the first on
page 2 that nobody made. Each side now resolves one screen in its own frames.
"""

from __future__ import annotations

from itertools import pairwise

import pandas as pd
import pytest

from scanpath_studio import api, cli
from scanpath_studio.plots import make_comparison_figure

#: Page 1 fixations sit near x 100–200 and page 2's near 1100–1200, so a
#: segment between the two ranges is a cross-page saccade.
_PAGE_OFFSET = {"page1": 0.0, "page2": 1000.0}


def _multipart(participant: str = "p", trials=("t1", "t2")):
    base_words, base_fix = api.build_authored_scanpath("First page")
    words, fixations = [], []
    for trial in trials:
        for index, (screen, offset) in enumerate(_PAGE_OFFSET.items(), start=1):
            common = dict(
                participant_id=participant,
                trial_id=trial,
                screen_id=screen,
                screen_index=index,
            )
            words.append(base_words.assign(**common, x=base_words.x + offset))
            fixations.append(
                base_fix.assign(
                    **common,
                    x=base_fix.x + offset,
                    timestamp_ms=base_fix.timestamp_ms + (index - 1) * 1000,
                )
            )
    return pd.concat(words, ignore_index=True), pd.concat(fixations, ignore_index=True)


def _marker_xs(fig) -> list[list[float]]:
    return [
        [float(x) for x in trace.x]
        for trace in fig.data
        if trace.mode and "markers" in trace.mode and trace.x is not None
    ]


def _saccade_segments(fig) -> list[tuple[float, float]]:
    segments = []
    for trace in fig.data:
        if trace.mode != "lines" or trace.x is None:
            continue
        xs = list(trace.x)
        for start, end in pairwise(xs):
            if start is not None and end is not None:
                segments.append((float(start), float(end)))
    return segments


def _on_page(xs, page: str) -> bool:
    low = _PAGE_OFFSET[page]
    return all(low <= x < low + 1000 for x in xs)


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_each_scanpath_defaults_to_its_first_screen(layout):
    words, fixations = _multipart()
    fig = api.compare_scanpaths(
        words, fixations, ("p", "t1"), ("p", "t2"), layout=layout
    )
    markers = _marker_xs(fig)
    assert len(markers) == 2
    assert all(_on_page(xs, "page1") for xs in markers)
    # No segment crosses into the other page's coordinate range.
    assert all(_on_page([start, end], "page1") for start, end in _saccade_segments(fig))


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_each_side_picks_its_own_screen(layout):
    words, fixations = _multipart()
    fig = api.compare_scanpaths(
        words,
        fixations,
        ("p", "t1"),
        ("p", "t2"),
        screen="page1",
        screen_b="page2",
        layout="side_by_side" if layout == "side_by_side" else "overlay",
    )
    first, second = _marker_xs(fig)
    assert _on_page(first, "page1")
    assert _on_page(second, "page2")


def test_a_trial_compared_with_its_own_later_page():
    words, fixations = _multipart()
    fig = api.compare_scanpaths(
        words,
        fixations,
        ("p", "t1"),
        ("p", "t1"),
        screen="page1",
        screen_b="page2",
        layout="side_by_side",
    )
    first, second = _marker_xs(fig)
    assert _on_page(first, "page1") and _on_page(second, "page2")


def test_b_from_another_dataset_picks_a_later_page():
    words, fixations = _multipart()
    words_b, fixations_b = _multipart(participant="q", trials=("u1",))
    fig = api.compare_scanpaths(
        words,
        fixations,
        ("p", "t1"),
        ("q", "u1"),
        screen_b="page2",
        words_b=words_b,
        fixations_b=fixations_b,
        dataset_b="Other",
        layout="side_by_side",
    )
    first, second = _marker_xs(fig)
    assert _on_page(first, "page1") and _on_page(second, "page2")
    assert all(
        _on_page([start, end], "page1") or _on_page([start, end], "page2")
        for start, end in _saccade_segments(fig)
    )


def test_an_unknown_screen_b_names_the_parameter_and_the_choices():
    words, fixations = _multipart()
    with pytest.raises(ValueError, match="screen_b='page9'.*'page1', 'page2'"):
        api.compare_scanpaths(
            words, fixations, ("p", "t1"), ("p", "t2"), screen_b="page9"
        )


def test_a_screen_for_a_single_screen_trial_is_refused():
    words, fixations = api.build_authored_scanpath("One page")
    words = words.assign(participant_id="p", trial_id="t1")
    fixations = fixations.assign(participant_id="p", trial_id="t1")
    with pytest.raises(ValueError, match="screen_b= was supplied"):
        api.compare_scanpaths(
            words, fixations, ("p", "t1"), ("p", "t1"), screen_b="page1"
        )


def test_the_builder_refuses_a_reading_that_spans_several_screens():
    """The low-level guard: a future caller that forgets to cut a reading to one
    screen gets an error, not a cross-page saccade."""
    words, fixations = _multipart()
    with pytest.raises(ValueError, match="Scanpath A .* spans 2 screens"):
        make_comparison_figure(
            words,
            fixations,
            ("p", "t1"),
            ("p", "t2"),
            canvas_width=2200,
            canvas_height=900,
            base_font_size=16,
        )


def test_the_co_animation_takes_bs_screen():
    words, fixations = _multipart()
    fig = api.animate_scanpath(
        words, fixations, "p", "t1", trial_b=("p", "t2"), screen_b="page2"
    )
    xs = [
        float(x)
        for frame in fig.frames
        for trace in frame.data
        if getattr(trace, "x", None) is not None
        for x in trace.x
        if x is not None
    ]
    assert any(x >= 1000 for x in xs)
    with pytest.raises(ValueError, match="Unknown screen_b"):
        api.animate_scanpath(
            words, fixations, "p", "t1", trial_b=("p", "t2"), screen_b="nope"
        )


def test_render_forwards_both_screens(tmp_path, monkeypatch):
    words, fixations = _multipart()
    words_path, fix_path = tmp_path / "w.csv", tmp_path / "f.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)
    seen: dict = {}
    real = api.compare_scanpaths

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "compare_scanpaths", spy)
    out = tmp_path / "cmp.html"
    cli.main(
        [
            "render",
            "--words",
            str(words_path),
            "--fixations",
            str(fix_path),
            "-p",
            "p",
            "-t",
            "t1",
            "--screen",
            "page2",
            "--compare-with",
            "p:t2",
            "--compare-screen",
            "page1",
            "--compare-layout",
            "side-by-side",
            "-o",
            str(out),
        ]
    )
    assert (seen["screen"], seen["screen_b"]) == ("page2", "page1")
    assert out.exists()


def test_render_refuses_compare_screen_without_compare_with(tmp_path):
    with pytest.raises(SystemExit, match="--compare-screen"):
        cli.main(
            [
                "render",
                "--sample",
                "--compare-screen",
                "page1",
                "-o",
                str(tmp_path / "x.html"),
            ]
        )


def _sized_pair(width_a: int, width_b: int):
    """Two readings of one dataset, each on a screen with its own canvas."""
    words, fixations = [], []
    for trial, width in (("t1", width_a), ("t2", width_b)):
        w, f = api.build_authored_scanpath("First page")
        common = dict(
            participant_id="p",
            trial_id=trial,
            screen_id="page1",
            screen_index=1,
            canvas_width=width,
            canvas_height=900,
        )
        words.append(w.assign(**common))
        fixations.append(f.assign(**common))
    return pd.concat(words, ignore_index=True), pd.concat(fixations, ignore_index=True)


@pytest.mark.parametrize(("width_a", "width_b"), [(800, 1600), (1600, 800)])
def test_one_datasets_two_screen_sizes_refuse_an_overlay(width_a, width_b):
    from scanpath_studio.experimental_setup import IncomparableScreensError

    words, fixations = _sized_pair(width_a, width_b)
    with pytest.raises(IncomparableScreensError, match="different screens"):
        api.compare_scanpaths(words, fixations, ("p", "t1"), ("p", "t2"))


@pytest.mark.parametrize(("width_a", "width_b"), [(800, 1600), (1600, 800)])
@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
def test_each_panel_is_drawn_to_its_own_screen(width_a, width_b, layout):
    words, fixations = _sized_pair(width_a, width_b)
    fig = api.compare_scanpaths(
        words,
        fixations,
        ("p", "t1"),
        ("p", "t2"),
        layout=layout,
        fit_to_monitor=True,
    )
    assert list(fig.layout.xaxis.range) == [0, width_a]
    assert list(fig.layout.xaxis2.range) == [0, width_b]


def test_one_screen_size_still_overlays():
    words, fixations = _sized_pair(800, 800)
    fig = api.compare_scanpaths(
        words, fixations, ("p", "t1"), ("p", "t2"), fit_to_monitor=True
    )
    assert list(fig.layout.xaxis.range) == [0, 800]


def test_a_co_animation_of_two_screen_sizes_in_one_dataset_is_refused():
    from scanpath_studio.experimental_setup import IncomparableScreensError

    words, fixations = _sized_pair(800, 1600)
    with pytest.raises(IncomparableScreensError, match="different screens"):
        api.animate_scanpath(words, fixations, "p", "t1", trial_b=("p", "t2"))
    words, fixations = _sized_pair(800, 800)
    api.animate_scanpath(words, fixations, "p", "t1", trial_b=("p", "t2"))
