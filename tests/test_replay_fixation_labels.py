"""The replay numbers fixations by their index in the trial, like everything else.

The replay built its visible labels as 1..n over whatever reached it, while its
hover and the static figure showed ``order_in_trial``: a later screen of a
multipart trial, a fixation window or a *Discard* renumbered the survivors in
the replay alone. These pin the three surfaces to one number per fixation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.plots import (
    FigureSettings,
    _fixation_order_labels,
    make_comparison_figure,
    make_scanpath_animation,
    make_scanpath_figure,
)


def _frames(pid: str = "p", order=(1, 2, 3), durations=(100, 200, 300)):
    n = len(order)
    words = pd.DataFrame(
        {
            "participant_id": [pid] * n,
            "trial_id": ["t"] * n,
            "text_id": ["text"] * n,
            "word_id": list(range(1, n + 1)),
            "text": [f"w{i}" for i in range(n)],
            "x": [100.0 + 100 * i for i in range(n)],
            "y": [100.0] * n,
            "width": [50.0] * n,
            "height": [20.0] * n,
            "line_idx": [0] * n,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": [pid] * n,
            "trial_id": ["t"] * n,
            "text_id": ["text"] * n,
            "x": [110.0 + 100 * i for i in range(n)],
            "y": [110.0] * n,
            "duration_ms": list(durations),
            "timestamp_ms": [1000.0 + 400 * i for i in range(n)],
            "fixation_id": list(order),
            "order_in_trial": list(order),
            "word_id": list(range(1, n + 1)),
        }
    )
    return words, fixations


def _settings(**overrides) -> FigureSettings:
    options = dict(
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        show_order=True,
        fixation_hover_fields=["order_in_trial"],
        duration_size_legend=False,
    )
    return FigureSettings(**{**options, **overrides})


def _static_labels(fig) -> list[str]:
    trace = next(t for t in fig.data if t.name == "Fixations")
    return [str(int(v)) for v in trace.text]


def _replay_labels(fig) -> list[list[str]]:
    """The order-number text trace(s): text-mode, unnamed (the word labels are
    named), as built — every frame restates the same strings."""
    return [
        list(t.text)
        for t in fig.data
        if t.mode == "text" and t.name is None and t.text is not None
    ]


def _replay_hover(fig, name: str = "Scanpath A") -> list[int]:
    trail = next(t for t in fig.data if t.name == name)
    # #374 F7: the hover's lead line reads "Fixation 41 · …".
    return [
        int(str(row[0]).split(" · ")[0].removeprefix("Fixation "))
        for row in np.asarray(trail.customdata)
    ]


def _frame_labels(fig) -> set[tuple[str, ...]]:
    return {
        tuple(trace["text"])
        for frame in fig.frames
        for trace in frame.data
        if trace.mode == "text" and trace.text is not None
    }


def test_complete_trial_is_numbered_one_to_n():
    words, fixations = _frames()
    replay = make_scanpath_animation(words, fixations, settings=_settings())
    assert _replay_labels(replay) == [["1", "2", "3"]]
    assert _replay_hover(replay) == [1, 2, 3]


def test_later_screen_keeps_its_parent_trial_indices():
    words, fixations = _frames(order=(501, 502, 503))
    cfg = _settings()
    static = make_scanpath_figure(words, fixations, settings=cfg)
    replay = make_scanpath_animation(words, fixations, settings=cfg)
    assert _static_labels(static) == ["501", "502", "503"]
    assert _replay_labels(replay) == [["501", "502", "503"]]
    assert _replay_hover(replay) == [501, 502, 503]
    # Every frame carries the same labels as the base trace.
    assert _frame_labels(replay) == {("501", "502", "503")}


def test_discard_keeps_the_survivors_numbers():
    words, fixations = _frames()
    cfg = _settings(fixation_flags={"short": {"mode": "Discard", "threshold_ms": 150}})
    static = make_scanpath_figure(words, fixations, settings=cfg)
    replay = make_scanpath_animation(words, fixations, settings=cfg)
    assert _static_labels(static) == ["2", "3"]
    assert _replay_labels(replay) == [["2", "3"]]
    assert _replay_hover(replay) == [2, 3]


def test_fixation_window_keeps_its_trial_indices():
    words, fixations = _frames(order=(1, 2, 3, 4), durations=(100, 200, 300, 400))
    kwargs = dict(
        participant="p",
        trial="t",
        fix_index_range=(3, 4),
        show_order=True,
        fixation_hover_fields=["order_in_trial"],
    )
    static = api.plot_scanpath(words, fixations, **kwargs)
    replay = api.animate_scanpath(words, fixations, **kwargs)
    assert _static_labels(static) == ["3", "4"]
    assert _replay_labels(replay) == [["3", "4"]]
    assert _replay_hover(replay) == [3, 4]


def test_later_multipart_screen_through_the_api():
    words, fixations = _frames(order=(1, 2, 3, 4), durations=(100, 200, 300, 400))
    words = words.assign(screen_id=["s1", "s1", "s2", "s2"], screen_index=[1, 1, 2, 2])
    fixations = fixations.assign(
        screen_id=["s1", "s1", "s2", "s2"], screen_index=[1, 1, 2, 2]
    )
    kwargs = dict(
        participant="p",
        trial="t",
        screen="s2",
        show_order=True,
        fixation_hover_fields=["order_in_trial"],
    )
    static = api.plot_scanpath(words, fixations, **kwargs)
    replay = api.animate_scanpath(words, fixations, **kwargs)
    assert _static_labels(static) == ["3", "4"]
    assert _replay_labels(replay) == [["3", "4"]]
    assert _replay_hover(replay) == [3, 4]


def test_frame_without_indices_falls_back_to_ordinals():
    words, fixations = _frames(order=(7, 8, 9))
    replay = make_scanpath_animation(
        words,
        fixations.drop(columns=["order_in_trial"]),
        settings=_settings(fixation_hover_fields=["duration_ms"]),
    )
    assert _replay_labels(replay) == [["1", "2", "3"]]
    # An index column with nothing usable in it falls back the same way.
    assert _fixation_order_labels(fixations.assign(order_in_trial=[np.nan] * 3)) == [
        "1",
        "2",
        "3",
    ]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([501.0, 502.0], ["501", "502"]),
        ([3, np.nan, 5], ["3", "", "5"]),
        ([1.5, 2], ["1.5", "2"]),
    ],
)
def test_order_label_formatting(values, expected):
    assert _fixation_order_labels(pd.DataFrame({"order_in_trial": values})) == (
        expected
    )


def test_co_animation_labels_match_the_static_comparison():
    words, fixations = _frames(order=(501, 502, 503))
    words_b, fixations_b = _frames("q", order=(11, 12, 13))
    cfg = _settings(fixation_flags={"short": {"mode": "Discard", "threshold_ms": 150}})
    replay = make_scanpath_animation(
        words, fixations, fixations_b=fixations_b, words_b=words_b, settings=cfg
    )
    static = make_comparison_figure(
        pd.concat([words, words_b], ignore_index=True),
        pd.concat([fixations, fixations_b], ignore_index=True),
        ("p", "t"),
        ("q", "t"),
        settings=cfg,
    )
    static_labels = [
        [str(int(v)) for v in t.text] for t in static.data if t.mode == "markers+text"
    ]
    assert static_labels == [["502", "503"], ["12", "13"]]
    assert _replay_labels(replay) == static_labels
    assert _replay_hover(replay, "Scanpath A") == [502, 503]
    assert _replay_hover(replay, "Scanpath B") == [12, 13]
