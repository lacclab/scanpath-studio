"""Comparing more than two scanpaths: A, B and up to two more (C, D).

The figure builders take the readings after B as ``extra_trials`` (the static
comparison) or ``fixations_extra`` / ``words_extra`` (the co-animation), and
each scanpath after B reads its settings from the ``*_extra`` fields of
``FigureSettings`` exactly as B reads its ``*_b`` ones.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.constants import COMPARISON_PALETTE, MAX_COMPARE_SCANPATHS
from scanpath_studio.plots import make_comparison_figure, make_scanpath_animation

READERS = ("p1", "p2", "p3", "p4")


def _words(participant: str, *, x0: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [0, 1, 2],
            "x": [x0, x0 + 100.0, x0 + 200.0],
            "y": [50.0] * 3,
            "width": [90.0] * 3,
            "height": [40.0] * 3,
            "text": ["alpha", "beta", "gamma"],
            "text_id": ["para1"] * 3,
        }
    )


def _fixations(participant: str, *, shift: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 3,
            "trial_id": ["t1"] * 3,
            "x": [120.0 + shift, 220.0 + shift, 320.0 + shift],
            "y": [70.0] * 3,
            "duration_ms": [200.0, 250.0, 180.0],
            "timestamp_ms": [0.0, 300.0, 700.0],
            "order_in_trial": [1, 2, 3],
            "word_id": [0, 1, 2],
        }
    )


def _frames(n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    readers = READERS[:n]
    words = pd.concat([_words(p) for p in readers], ignore_index=True)
    fixations = pd.concat(
        [_fixations(p, shift=5.0 * i) for i, p in enumerate(readers)],
        ignore_index=True,
    )
    return words, fixations


def _compare(n: int, **overrides):
    words, fixations = _frames(n)
    trials = [(p, "t1") for p in READERS[:n]]
    kwargs = dict(canvas_width=800, canvas_height=400, base_font_size=12)
    kwargs.update(overrides)
    return make_comparison_figure(
        words, fixations, trials[0], trials[1], extra_trials=trials[2:], **kwargs
    )


def _markers(fig):
    return [t for t in fig.data if t.mode and t.mode.startswith("markers")]


@pytest.mark.parametrize("n", [3, 4])
def test_overlay_draws_one_scanpath_per_reading_in_its_palette_colour(n):
    markers = _markers(_compare(n))
    assert [m.marker.color for m in markers] == COMPARISON_PALETTE[:n]


@pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
@pytest.mark.parametrize("n", [3, 4])
def test_split_layouts_give_each_reading_its_own_titled_panel(layout, n):
    fig = _compare(n, layout=layout)
    axes = [key for key in fig.layout.to_plotly_json() if key.startswith("xaxis")]
    assert len(axes) == n
    titles = [a.text for a in fig.layout.annotations if " · " in (a.text or "")]
    assert [title.split(" · ")[0] for title in titles] == list("ABCD"[:n])
    assert len(_markers(fig)) == n


def test_side_by_side_panels_sit_in_one_row_and_stacked_in_one_column():
    row = _compare(3, layout="side_by_side")
    column = _compare(3, layout="stacked")
    # Both fit the same monitor width; the column is the taller.
    assert column.layout.height > row.layout.height
    domains = [row.layout[f"xaxis{s}"].domain for s in ("", "2", "3")]
    assert [d[0] for d in domains] == sorted(d[0] for d in domains)


def test_overlay_heatmap_splits_each_word_box_into_one_strip_per_reading():
    fig = _compare(3, show_heatmap=True, heatmap_style="Word boxes")
    strips = [s for s in fig.layout.shapes if (s.name or "").endswith("heatmap")]
    # Three readings × three fixated words, each a third of its 90 px box.
    assert len(strips) == 9
    widths = {round(s.x1 - s.x0, 6) for s in strips}
    assert widths == {30.0}
    first_box = sorted((s.x0, s.x1) for s in strips if 100.0 <= s.x0 < 190.0)
    assert first_box == [(100.0, 130.0), (130.0, 160.0), (160.0, 190.0)]


def test_two_readings_keep_their_halves():
    fig = _compare(2, show_heatmap=True, heatmap_style="Word boxes")
    strips = [s for s in fig.layout.shapes if (s.name or "").endswith("heatmap")]
    first_box = sorted((s.x0, s.x1) for s in strips if 100.0 <= s.x0 < 190.0)
    assert first_box == [(100.0, 145.0), (145.0, 190.0)]


@pytest.mark.parametrize("side, reader", [("c", "p3"), ("d", "p4")])
def test_compare_stimulus_can_name_a_later_scanpath(side, reader):
    words, fixations = _frames(4)
    # Each reader's words sit in their own place, so the drawn boxes say whose.
    words = pd.concat(
        [_words(p, x0=100.0 + 1000.0 * i) for i, p in enumerate(READERS)],
        ignore_index=True,
    )
    fig = make_comparison_figure(
        words,
        fixations,
        ("p1", "t1"),
        ("p2", "t1"),
        extra_trials=[("p3", "t1"), ("p4", "t1")],
        canvas_width=6000,
        canvas_height=400,
        base_font_size=12,
        compare_stimulus=side,
    )
    boxes = [s.x0 for s in fig.layout.shapes if s.name.endswith("word_boxes")]
    # Only the named reading's boxes: its three words, and no one else's.
    expected = 100.0 + 1000.0 * READERS.index(reader)
    assert sorted(boxes) == [expected, expected + 100.0, expected + 200.0]


def test_more_than_the_maximum_is_refused():
    words, fixations = _frames(4)
    extra = [(p, "t1") for p in READERS[2:]] + [("p5", "t1")]
    with pytest.raises(ValueError, match=str(MAX_COMPARE_SCANPATHS)):
        make_comparison_figure(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t1"),
            extra_trials=extra,
            canvas_width=800,
            canvas_height=400,
            base_font_size=12,
        )


def test_each_later_scanpath_wears_its_own_style():
    fig = _compare(3, styles_extra=({"fix_color": "#123456"},))
    assert [m.marker.color for m in _markers(fig)] == [
        *COMPARISON_PALETTE[:2],
        "#123456",
    ]


def test_a_later_panel_on_its_own_screen_is_framed_on_that_screen():
    shared = _compare(3, layout="side_by_side", fit_to_monitor=True)
    own = _compare(
        3,
        layout="side_by_side",
        fit_to_monitor=True,
        canvases_extra=((1600, 400),),
    )
    assert list(shared.layout.xaxis3.range) == list(shared.layout.xaxis.range)
    assert own.layout.xaxis3.range[1] > own.layout.xaxis.range[1]


def test_co_animation_replays_every_scanpath_on_one_clock():
    words, _ = _frames(1)
    fig = make_scanpath_animation(
        words,
        _fixations("p1"),
        fixations_b=_fixations("p2", shift=5.0),
        fixations_extra=[_fixations("p3", shift=10.0)],
        labels_extra=("Third reader",),
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
    )
    names = ("Scanpath A", "Scanpath B", "Third reader")
    trails = [t for t in fig.data if t.name in names]
    assert [t.name for t in trails] == list(names)
    assert [t.marker.color for t in trails] == COMPARISON_PALETTE[:3]


def test_co_animation_names_an_unlabelled_later_scanpath_by_its_letter():
    words, _ = _frames(1)
    fig = make_scanpath_animation(
        words,
        _fixations("p1"),
        fixations_b=_fixations("p2"),
        fixations_extra=[_fixations("p3"), _fixations("p4")],
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
    )
    names = {t.name for t in fig.data}
    assert {"Scanpath C", "Scanpath D"} <= names


def test_co_animation_filters_a_later_scanpath_by_its_own_flags():
    words, _ = _frames(1)
    stray = _fixations("p3")
    stray.loc[1, "y"] = 390.0  # far below the text
    flags = {"oob": {"mode": "Hide"}}
    kept = make_scanpath_animation(
        words,
        _fixations("p1"),
        fixations_b=_fixations("p2"),
        fixations_extra=[stray],
        words_extra=[_words("p3")],
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
    )
    hidden = make_scanpath_animation(
        words,
        _fixations("p1"),
        fixations_b=_fixations("p2"),
        fixations_extra=[stray],
        words_extra=[_words("p3")],
        fixation_flags_extra=(flags,),
        canvas_width=800,
        canvas_height=400,
        base_font_size=12,
    )

    def c_points(fig):
        trail = next(t for t in fig.data if t.name == "Scanpath C")
        return len(trail.x)

    assert c_points(hidden) == c_points(kept) - 1
