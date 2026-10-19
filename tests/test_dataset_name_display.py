"""A dataset's name is the user's own text: drawn literally, and kept short.

Streamlit renders labels, captions, alerts, toasts and help text as markdown —
bold, links, ``:red[…]`` colour, ``$…$`` math, ``:material/…:`` icons — so a
name typed with any of those must reach the screen as the characters typed.
The name fields stop at `DATASET_NAME_MAX_CHARS`, and a name stored before
that limit is clamped by the table's CSS, not cut in storage.
"""

from __future__ import annotations

import html
import re

import pandas as pd
import pytest

from scanpath_studio.constants import DATASET_NAME_MAX_CHARS, md_literal
from tests.conftest import APP_SCRIPT, pin_data_view

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

HOSTILE = "**bold** [link](javascript:alert(1)) :red[x] $x^2$"
SHORTCODES = "a :smile: b :material/home: c :red-background[y] _u_ ~s~ `c` # h"
MARKUP = "<b>x</b> R&amp;D x\\y | z"
NAMES = [HOSTILE, SHORTCODES, MARKUP, "1. Intro", "- list", "+ plus"]

#: What markdown acts on in a line; none of it may survive `md_literal`.
_ACTIVE = re.compile(r"[\\`*_\[\]<>#|~$:&]")


def _markdown_left(text: str) -> re.Match | None:
    """The first character markdown would act on, outside a character reference."""
    return _ACTIVE.search(re.sub(r"&#\d+;", "", text))


@pytest.mark.parametrize("name", NAMES)
def test_md_literal_leaves_nothing_for_markdown_to_act_on(name):
    shown = md_literal(name)
    assert not _markdown_left(shown), shown
    # And it is the same text once the references are read back.
    assert html.unescape(shown) == name


def test_md_literal_on_the_reported_name():
    assert md_literal(HOSTILE) == (
        "&#42;&#42;bold&#42;&#42; &#91;link&#93;(javascript&#58;alert(1)) "
        "&#58;red&#91;x&#93; &#36;x^2&#36;"
    )


def test_md_literal_leaves_a_plain_name_alone():
    for name in ("Dataset 1", "OneStop (L1)", "My corpus v1.2"):
        assert md_literal(name) == name


def test_a_leading_list_marker_is_not_a_list():
    assert md_literal("1. Intro") == "1&#46; Intro"
    assert md_literal("- list") == "&#45; list"
    assert md_literal("a - b") == "a - b"


def test_the_added_toast_names_the_dataset_literally():
    from scanpath_studio.app import dataset_added_message

    message = dataset_added_message(HOSTILE, None, None)
    assert message == f"**{md_literal(HOSTILE)}** added."


def test_a_missing_link_dataset_is_named_literally():
    from scanpath_studio.url_state import missing_dataset_message

    message = missing_dataset_message(HOSTILE, "p:1", "$t$")
    assert md_literal(HOSTILE) in message
    assert "p&#58;1" in message
    assert "&#36;t&#36;" in message
    assert "**bold**" not in message


def test_short_name():
    from scanpath_studio.dataset_table import short_name

    assert short_name("Dataset 1") == "Dataset 1"
    long = "x" * 5000
    cut = short_name(long)
    assert len(cut) == DATASET_NAME_MAX_CHARS
    assert cut.endswith("…")


def _dataset(words: pd.DataFrame, fixations: pd.DataFrame) -> dict:
    return {
        "words": words,
        "fixations": fixations,
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
    }


def _name_cells(at) -> list[str]:
    return [m.value for m in at.markdown if 'class="sps-ds-name"' in str(m.value)]


@pytest.mark.timeout(180)
def test_the_dataset_table_shows_a_name_as_typed():
    """A name stored with markdown in it, and one 5,000 characters long from
    before the limit, both load and are drawn as their own text."""
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = load_synthetic_data()
    long_name = "L" * 5000
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {
        HOSTILE: _dataset(words, fixations),
        long_name: _dataset(words, fixations),
    }
    at.session_state["data_source_choice"] = HOSTILE
    pin_data_view(at)
    at.run()
    assert not at.exception, at.exception

    cells = _name_cells(at)
    hostile = next(c for c in cells if md_literal(HOSTILE) in c)
    # The cell's text is the name, character for character, with nothing left
    # for markdown to read; its tooltip is the whole name.
    text = re.search(r">(.*)</span>", hostile).group(1)
    assert html.unescape(text) == HOSTILE
    assert not _markdown_left(text)
    assert f'title="{html.escape(HOSTILE)}"' in hostile
    # The open dataset's heading names it literally too.
    assert any(md_literal(HOSTILE) in h.value for h in at.subheader)
    assert not any("**bold**" in h.value for h in at.subheader)

    # The long name is still a row; the CSS clamps it, its tooltip holds it.
    long_cell = next(c for c in cells if long_name in c)
    assert f'title="{long_name}"' in long_cell
    long_row = next(
        b
        for b in at.button
        if b.key and b.key.startswith("dataset_row_edit_") and "L" * 100 in b.label
    )
    assert len(long_row.help) < 300


@pytest.mark.timeout(180)
def test_the_name_fields_stop_at_the_limit():
    from scanpath_studio import app

    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    pin_data_view(at)
    at.session_state[app.DATASET_EDITOR_OPEN_KEY] = True
    at.run()
    assert not at.exception, at.exception
    name = at.text_input(key=app.EDITOR_NAME_FIELD_KEY)
    assert name.proto.max_chars == DATASET_NAME_MAX_CHARS
