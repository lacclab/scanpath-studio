"""A recorded reading can switch scripts and revisit an earlier word on the same line."""

from __future__ import annotations

from importlib.resources import files

import pytest

from scanpath_studio import api
from scanpath_studio.measures import assign_fixations_to_words


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
