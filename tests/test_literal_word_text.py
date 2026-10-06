"""Stimulus words render as their own characters, never as Plotly markup.

Round-8 review, finding 6: word strings went straight into Plotly's rich-text
fields, so a code or markup stimulus token ``<b>bold</b>`` drew bold with its
tags gone and ``x<br>y`` broke onto two lines, out of its box. Every figure
that draws word labels (static, replay, the three comparison layouts) now
escapes the data — and only the data — where it enters the figure, while the
tables and what is exported from them keep the original strings.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio import plots
from scanpath_studio.export import _write_table

# Mixed-direction punctuation, spelled by codepoint so the source stays plain.
HEBREW = "שלום"  # shalom
RTL_TOKEN = f"{HEBREW}, <{HEBREW}>!"
ISOLATE, POP_ISOLATE = chr(0x2067), chr(0x2069)

SOURCE = ["<b>bold</b>", "x<br>y", "R&D", "a<b", "1 > 0", RTL_TOKEN]
LITERAL = [
    "&lt;b&gt;bold&lt;/b&gt;",
    "x&lt;br&gt;y",
    "R&amp;D",
    "a&lt;b",
    "1 &gt; 0",
    f"{ISOLATE}{HEBREW}, &lt;{HEBREW}&gt;!{POP_ISOLATE}",
]


def _frames(pid: str = "p") -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(SOURCE)
    words = pd.DataFrame(
        {
            "participant_id": [pid] * n,
            "trial_id": ["t"] * n,
            "text_id": ["text"] * n,
            "word_id": list(range(1, n + 1)),
            "text": SOURCE,
            "x": [100.0 + 130.0 * i for i in range(n)],
            "y": [100.0] * n,
            "width": [120.0] * n,
            "height": [20.0] * n,
            "line_idx": [0] * n,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": [pid] * 2,
            "trial_id": ["t"] * 2,
            "text_id": ["text"] * 2,
            "x": [110.0, 240.0],
            "y": [110.0, 110.0],
            "duration_ms": [100.0, 200.0],
            "timestamp_ms": [1000.0, 1100.0],
            "fixation_id": [1, 2],
            "order_in_trial": [1, 2],
            "word_id": [1, 2],
        }
    )
    return words, fixations


def _settings(**overrides) -> plots.FigureSettings:
    return plots.FigureSettings(
        canvas_width=1000,
        canvas_height=600,
        base_font_size=16,
        show_words=True,
        show_word_labels=True,
        duration_size_legend=False,
        **overrides,
    )


def _word_traces(fig) -> list:
    traces = [t for t in fig.data if t.name == "words"]
    for frame in fig.frames or ():
        traces.extend(t for t in frame.data if getattr(t, "name", None) == "words")
    return traces


def _static(words, fixations, **overrides):
    return plots.make_scanpath_figure(words, fixations, settings=_settings(**overrides))


def _replay(words, fixations, **overrides):
    return plots.make_scanpath_animation(
        words, fixations, settings=_settings(**overrides)
    )


def _comparison(layout):
    def build(words, fixations, **overrides):
        words_b, fixations_b = _frames("q")
        for column in words.columns.difference(words_b.columns):
            words_b[column] = words[column].to_numpy()
        return plots.make_comparison_figure(
            pd.concat([words, words_b], ignore_index=True),
            pd.concat([fixations, fixations_b], ignore_index=True),
            ("p", "t"),
            ("q", "t"),
            settings=_settings(layout=layout, **overrides),
        )

    return build


BUILDERS = {
    "static": _static,
    "replay": _replay,
    "overlay": _comparison("overlay"),
    "side_by_side": _comparison("side_by_side"),
    "stacked": _comparison("stacked"),
}


@pytest.mark.parametrize("builder", BUILDERS.values(), ids=BUILDERS.keys())
def test_word_labels_show_the_datas_own_characters(builder):
    words, fixations = _frames()
    source = words.copy()
    fig = builder(words, fixations)
    traces = _word_traces(fig)
    assert traces
    for trace in traces:
        assert list(trace.text) == LITERAL
        # The hover shows the label (`%{text}`), escaped once; the template's
        # own markup is the app's and stays markup.
        assert "%{text}" in trace.hovertemplate
        assert "<br>" in trace.hovertemplate
    # Nothing escaped the table itself.
    pd.testing.assert_frame_equal(words, source)


@pytest.mark.parametrize("builder", BUILDERS.values(), ids=BUILDERS.keys())
def test_hover_fields_show_the_datas_own_characters(builder):
    words, fixations = _frames()
    words["note"] = SOURCE
    fig = builder(words, fixations, word_hover_fields=["text", "note", "word_id"])
    for trace in _word_traces(fig):
        rows = [list(row) for row in trace.customdata]
        literal_plain = [
            text.removeprefix(ISOLATE).removesuffix(POP_ISOLATE) for text in LITERAL
        ]
        assert [row[0] for row in rows] == literal_plain
        assert [row[1] for row in rows] == literal_plain
        # Numbers pass through untouched.
        assert [row[2] for row in rows] == list(range(1, len(SOURCE) + 1))
        assert trace.hovertemplate.count("<br>") == 2


def test_literal_text_is_not_escaped_twice():
    """Source text that already spells an entity draws that entity literally."""
    words, fixations = _frames()
    words.loc[0, "text"] = "&lt;"
    trace = _word_traces(_static(words, fixations))[0]
    assert trace.text[0] == "&amp;lt;"
    assert plots._plotly_literal("&lt;") == "&amp;lt;"


def test_exported_words_keep_the_original_strings():
    words, fixations = _frames()
    _static(words, fixations)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        _write_table(zf, "words.csv", words, "csv")
    with zipfile.ZipFile(buffer) as zf:
        exported = pd.read_csv(zf.open("words.csv"))
    assert exported["text"].tolist() == SOURCE


# Round 9, finding 3: the figure's chrome — title, caption and the names of the
# two compared scanpaths — is user text too, and is drawn as written.
LABELS = ("<b>Scanpath A</b>", "Scanpath<br>B %{x}")
LABELS_LITERAL = ("&lt;b&gt;Scanpath A&lt;/b&gt;", "Scanpath&lt;br&gt;B &#37;{x}")


def test_title_and_caption_are_drawn_as_written():
    from scanpath_studio.export import annotate_figure

    words, fixations = _frames()
    fig = _static(words, fixations)
    annotate_figure(fig, title="Literal <b>study</b>", caption="a<br>b\nR&D")
    assert fig.layout.title.text == "Literal &lt;b&gt;study&lt;/b&gt;"
    # A real newline is still a new line; a typed <br> is not.
    assert fig.layout.annotations[-1].text == "a&lt;br&gt;b<br>R&amp;D"


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_compare_labels_are_drawn_as_written(layout):
    fig = _comparison(layout)(*_frames(), trial_labels=LABELS, show_legend=True)
    names = {t.name for t in fig.data}
    assert set(LABELS_LITERAL) <= names
    templates = [t.hovertemplate or "" for t in fig.data]
    assert not any(label in template for label in LABELS for template in templates)
    assert any(LABELS_LITERAL[1] in template for template in templates)
    if layout != "overlay":
        titles = {a.text for a in fig.layout.annotations}
        assert set(LABELS_LITERAL) <= titles


def test_replay_labels_are_drawn_as_written():
    words, fixations = _frames()
    fig = plots.make_scanpath_animation(
        words,
        fixations,
        fixations_b=fixations,
        settings=_settings(label_a=LABELS[0], label_b=LABELS[1], show_legend=True),
    )
    assert set(LABELS_LITERAL) <= {t.name for t in fig.data}
