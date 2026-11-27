"""`styles.compact_css`: the app stylesheet as sent, without its comments.

The browser half — that the compacted sheet parses to the same rules as the
documented one, and reaches the page whole through `st.html` — is
``tests/test_browser_smoke.py``.
"""

from __future__ import annotations

from scanpath_studio.styles import compact_css, get_app_css


def test_comments_go_and_whitespace_collapses():
    css = "/* lead */\n.a {\n    color: red; /* why */\n}\n\n.b  .c { margin: 0 }"
    assert compact_css(css) == ".a { color: red; } .b .c { margin: 0 }"


def test_strings_are_kept_whole():
    css = '.a::before { content: "/* not a comment */  two  spaces"; }'
    assert compact_css(css) == css
    escaped = ".a::after { content: 'it\\'s /* still */ a string'; } /* x */"
    assert (
        compact_css(escaped) == ".a::after { content: 'it\\'s /* still */ a string'; }"
    )


def test_a_string_ends_at_a_line_break_as_css_does():
    """An unclosed quote — an apostrophe outside any comment — must not
    swallow the rules after it, any more than it does in a browser."""
    css = ".a { color: red } it's\n.b { /* x */ color: blue }"
    assert compact_css(css) == ".a { color: red } it's .b { color: blue }"


def test_a_comment_between_selectors_joins_them_as_css_does():
    assert compact_css(".a/* x */.b { color: red }") == ".a.b { color: red }"


def test_an_unclosed_comment_ends_the_sheet():
    assert compact_css(".a { color: red } /* never closed") == ".a { color: red }"


def test_the_app_stylesheet_is_sent_without_its_comments():
    css = get_app_css()
    sent = compact_css(css)
    assert sent.startswith("<style>") and sent.endswith("</style>")
    assert "/*" not in sent
    # The comments are most of the sheet; the rules are what is sent.
    assert len(sent) < len(css) / 2
    # A `<` left in a comment would make `st.html`'s sanitizer drop the
    # whole <style>; only the two tags around the sheet may carry one.
    assert sent.count("<") == 2
