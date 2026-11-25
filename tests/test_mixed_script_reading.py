"""A recorded reading can switch scripts and revisit an earlier word on the same line."""

from __future__ import annotations

from importlib.resources import files

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.measures import assign_fixations_to_words
from scanpath_studio.plots import _word_label_rtl


def mixed_script_figure():
    sample = files("scanpath_studio").joinpath("sample_data")
    words, fixations = api.load_scanpath_data(
        sample.joinpath("mixed_script_words.csv"),
        sample.joinpath("mixed_script_fixations.csv"),
        names="canonical",
    )
    figure = api.plot_scanpath(
        words, fixations, canvas_size=(800, 250), show_word_labels=True, show_words=True
    )
    return figure, words, fixations


def test_passage_order_assignment_and_labels_in_both_directions():
    figure, words, fixations = mixed_script_figure()
    assigned = assign_fixations_to_words(fixations, words).sort_values("timestamp_ms")
    assert list(assigned.word_id) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 8, 10]
    labels = next(trace for trace in figure.data if trace.name == "words")
    isolate, pop = chr(0x2067), chr(0x2069)
    assert [token.strip(isolate + pop) for token in labels.text] == list(words.text)
    assert labels.text[4] == isolate + "ב־Data" + pop
    assert labels.text[8] == "Data"
    assert list(labels.x) == pytest.approx(list(words.x + words.width / 2))


def test_numbers_and_punctuation_take_the_direction_around_them():
    # "42" sits between Hebrew words, and "2025." ends an Arabic line after
    # "Data": both are drawn right to left, so the period lands on the left,
    # where an Arabic sentence ends.
    figure, _words, _fixations = mixed_script_figure()
    labels = next(trace for trace in figure.data if trace.name == "words")
    isolate, pop = chr(0x2067), chr(0x2069)
    assert labels.text[1] == isolate + "42" + pop
    assert labels.text[9] == isolate + "2025." + pop


def _passage(texts, lines=None):
    n = len(texts)
    return pd.DataFrame(
        {
            "participant_id": "p",
            "trial_id": "t",
            "word_id": range(1, n + 1),
            "text": texts,
            "x": [100.0 * i for i in range(n)],
            "y": [40.0 * line for line in (lines or [0] * n)],
            "width": 90.0,
            "height": 20.0,
        }
    )


@pytest.mark.parametrize(
    ("texts", "lines", "expected"),
    [
        # Between two words of one direction: that direction.
        (["hello", "42", "world"], None, [False, False, False]),
        (["שלום", "42", "עולם"], None, [True, True, True]),
        # Between the two directions, or at a line's end: the line's own,
        # from its first strong word.
        (["שלום", "Data", "2025."], None, [True, False, True]),
        (["hello", "שלום", "(3)", "world"], None, [False, True, False, False]),
        # A line of neutrals only: the passage's first strong word's.
        (["אבג", "hello", "42", "—"], [0, 0, 1, 1], [True, False, True, True]),
    ],
)
def test_a_neutral_word_resolves_like_a_neutral_character(texts, lines, expected):
    assert _word_label_rtl(_passage(texts, lines)).tolist() == expected


def test_a_recorded_direction_wins_for_neutral_words():
    words = _passage(["hello", "42", "world"]).assign(
        right_to_left=[False, True, False]
    )
    assert _word_label_rtl(words).tolist() == [False, True, False]
