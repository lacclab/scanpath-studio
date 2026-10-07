"""The shared iframe helper's document check (`html_embed.embed_html_iframe`)."""

from __future__ import annotations

import pytest

from scanpath_studio import html_embed


@pytest.fixture
def embedded(monkeypatch):
    sources = []
    monkeypatch.setattr(
        html_embed.st, "iframe", lambda source, **kwargs: sources.append(source)
    )
    return sources


def test_a_fragment_gets_a_document_around_it(embedded):
    html_embed.embed_html_iframe("<script>1</script>", height=0)
    assert embedded == ["<!doctype html><html><body><script>1</script></body></html>"]


@pytest.mark.parametrize(
    "document",
    [
        "<!DOCTYPE html><html><body>x</body></html>",
        "\n  <html><head></head><body>x</body></html>",
    ],
)
def test_a_whole_document_goes_in_as_it_is(embedded, document):
    html_embed.embed_html_iframe(document, height=10)
    assert embedded == [document]


def test_text_deep_inside_a_fragment_does_not_make_it_a_document(embedded):
    # PERF-16: the check reads the first bytes, not the whole string — a replay's
    # markup runs to 55 MB, and lower-casing all of it took 0.2 s a rerun. It
    # also stops a "<body" in the figure's own text from dropping the wrapper.
    fragment = "<div>" + "x" * 100_000 + "<body>" + "</div>"
    html_embed.embed_html_iframe(fragment, height=10)
    assert embedded == [f"<!doctype html><html><body>{fragment}</body></html>"]


def test_alt_reaches_the_iframe(monkeypatch):
    # Streamlit 1.65's `alt` names a visible embed for assistive technology; the
    # script carriers leave it unset.
    calls = []
    monkeypatch.setattr(html_embed.st, "iframe", lambda source, **kw: calls.append(kw))
    html_embed.embed_html_iframe("<div>fig</div>", height=10, alt="Scanpath figure")
    html_embed.embed_html_iframe("<script>1</script>", height=0)
    assert [c["alt"] for c in calls] == ["Scanpath figure", None]
