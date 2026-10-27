"""``redact_text``: a block over each word's letters, and no word anywhere."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.constants import WORD_KEY
from scanpath_studio.measures import assign_fixations_to_words, word_glyph_span
from scanpath_studio.plots import (
    make_comparison_figure,
    make_scanpath_animation,
    make_scanpath_figure,
    redact_word_text,
)

#: The figure's canvas: the builders take it with every call.
CANVAS = dict(canvas_width=500, canvas_height=300, base_font_size=12)

#: Words no figure would otherwise spell, so finding one in the JSON is a leak.
SECRET = ["Zebrafish", "Quokkas", "Xylophone", "Marzipan", "Jukebox", "Fjords"]


@pytest.fixture
def words(synthetic_words_df) -> pd.DataFrame:
    out = synthetic_words_df.copy()
    out["text"] = SECRET
    out["is_in_aspan"] = [False, False, False, True, True, False]
    return out


@pytest.fixture
def fixations(synthetic_fixations_df, words) -> pd.DataFrame:
    return assign_fixations_to_words(synthetic_fixations_df, words, overwrite=True)


def _leaks(fig) -> list[str]:
    payload = fig.to_json()
    return [word for word in SECRET if word in payload]


def _extents(trace) -> list[tuple[float, float, float, float]]:
    """``(x0, x1, y0, y1)`` of each block in a block trace."""
    out, xs, ys = [], [], []
    for x, y in zip(trace.x, trace.y, strict=True):
        if x is None:
            out.append((min(xs), max(xs), min(ys), max(ys)))
            xs, ys = [], []
        else:
            xs.append(float(x))
            ys.append(float(y))
    return out


def _blocks(fig) -> list:
    return [t for t in fig.data if t.name == "words" and t.fill == "toself"]


def test_redact_word_text_keeps_length_direction_and_gaps():
    words = pd.DataFrame({"text": ["שלום", "abc", None, "中文"]})
    out = redact_word_text(words)
    assert out["text"].iloc[0] == "████"
    assert out["text"].iloc[1] == "███"
    assert pd.isna(out["text"].iloc[2])
    assert out["text"].iloc[3] == "〓〓"
    assert out["right_to_left"].tolist() == [True, False, False, False]
    # The caller's frame is untouched.
    assert words["text"].iloc[1] == "abc"


def test_static_figure_draws_blocks_and_no_words(words, fixations):
    plain = make_scanpath_figure(words, fixations, show_word_labels=True, **CANVAS)
    assert set(_leaks(plain)) == set(SECRET)

    fig = make_scanpath_figure(
        words,
        fixations,
        show_word_labels=True,
        redact_text=True,
        highlight_column=None,
        word_hover_fields=["text", "word_id"],
        fixation_hover_fields=["order_in_trial", "word_id"],
        **CANVAS,
    )
    assert _leaks(fig) == []
    blocks = _blocks(fig)
    assert len(blocks) == 1
    _, run = word_glyph_span(words)
    assert np.allclose([x1 - x0 for x0, x1, _, _ in _extents(blocks[0])], run)
    # 0.7 em of the label font tall, whatever the word's width.
    heights = {round(y1 - y0, 6) for _, _, y0, y1 in _extents(blocks[0])}
    assert len(heights) == 1
    # The hover marker stays, on each word, invisible.
    hover = next(t for t in fig.data if t.name == "words" and t.mode == "markers")
    assert hover.marker.opacity == 0
    assert len(hover.x) == len(words)


def test_highlighted_words_get_their_own_block_colour(words, fixations):
    fig = make_scanpath_figure(
        words,
        fixations,
        show_word_labels=True,
        redact_text=True,
        highlight_column="is_in_aspan",
        critical_span_style="Mark text",
        text_color="#000000",
        highlight_text_color="#D55E00",
        **CANVAS,
    )
    assert {t.fillcolor for t in _blocks(fig)} == {"#000000", "#D55E00"}


def test_off_by_default_draws_the_words(words, fixations):
    fig = make_scanpath_figure(words, fixations, show_word_labels=True, **CANVAS)
    assert _blocks(fig) == []


def test_animation_and_comparison_redact_too(words, fixations):
    anim = make_scanpath_animation(
        words, fixations, show_word_labels=True, redact_text=True, **CANVAS
    )
    assert _leaks(anim) == [] and _blocks(anim)

    reading = ("synthetic", "synthetic_2line_demo")
    for layout in ("overlay", "side_by_side"):
        cmp = make_comparison_figure(
            words,
            fixations,
            reading,
            reading,
            show_word_labels=True,
            redact_text=True,
            layout=layout,
            **CANVAS,
        )
        assert _leaks(cmp) == [] and _blocks(cmp), layout


def test_api_takes_the_option(words, fixations):
    assert api.figure_options()["redact_text"] is False
    for kind in ("animation", "comparison"):
        assert "redact_text" in api.figure_options(kind)
    fig = api.plot_scanpath(
        words, fixations, "synthetic", "synthetic_2line_demo", redact_text=True
    )
    assert _leaks(fig) == [] and _blocks(fig)


def test_text_word_ids_that_spell_the_words_are_redacted_too(words, fixations):
    """A text Word ID (`Zebrafish_0`) spells its word, in both tables: a
    hover field that names it must not bring the word back."""
    keys = {
        wid: f"{text}_{i}"
        for i, (wid, text) in enumerate(zip(words["word_id"], words["text"]))
    }
    words = words.assign(**{WORD_KEY: words["word_id"].map(keys)})
    fixations = fixations.assign(**{WORD_KEY: fixations["word_id"].map(keys)})
    hovers = dict(
        word_hover_fields=["text", "word_id", WORD_KEY],
        fixation_hover_fields=["order_in_trial", "duration_ms", "word_id", WORD_KEY],
    )
    plain = make_scanpath_figure(words, fixations, **hovers, **CANVAS)
    assert _leaks(plain), "the keys were never drawn, so this proves nothing"

    fig = make_scanpath_figure(words, fixations, redact_text=True, **hovers, **CANVAS)
    assert _leaks(fig) == []
    anim = make_scanpath_animation(
        words,
        fixations,
        fixations_b=fixations,
        words_b=words,
        redact_text=True,
        **hovers,
        **CANVAS,
    )
    assert _leaks(anim) == []
    reading = ("synthetic", "synthetic_2line_demo")
    for layout in ("overlay", "side_by_side"):
        cmp = make_comparison_figure(
            words,
            fixations,
            reading,
            reading,
            redact_text=True,
            layout=layout,
            **hovers,
            **CANVAS,
        )
        assert _leaks(cmp) == [], layout
    via_api = api.plot_scanpath(
        words,
        fixations,
        "synthetic",
        "synthetic_2line_demo",
        redact_text=True,
        **hovers,
    )
    assert _leaks(via_api) == []
