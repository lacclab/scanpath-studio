"""Compare mode warns when the two readings are of **different texts**.

The overlay draws both scanpaths over one set of word boxes, so a mismatched
pair is not merely uninformative — it is misleading. The note used to exist for
the animated co-replay only, and only inside the rail's Playback popover; these
pin both the wording split and the fact that a matching pair stays quiet.
"""

from __future__ import annotations

import pytest

from scanpath_studio.tabs import _different_texts_note


class TestDifferentTextsNote:
    def test_matching_texts_say_nothing(self):
        assert _different_texts_note("t1", "t1", overlaid=True) is None
        assert _different_texts_note("t1", "t1", overlaid=False) is None

    @pytest.mark.parametrize("missing", [None, ""])
    def test_an_unknown_text_id_is_never_nagged(self, missing):
        """A dataset with no text column cannot answer the question, so it is
        not asked it."""
        assert _different_texts_note(missing, "t2", overlaid=True) is None
        assert _different_texts_note("t1", missing, overlaid=True) is None

    def test_an_overlay_says_the_boxes_are_shared(self):
        note = _different_texts_note("t1", "t2", overlaid=True)
        assert note is not None
        assert "t1" in note and "t2" in note
        assert "one set of word boxes" in note

    def test_a_split_layout_says_the_panels_do_not_compare(self):
        note = _different_texts_note("t1", "t2", overlaid=False)
        assert note is not None
        assert "its own stimulus" in note
        # The overlay's stronger claim must not leak into the split wording.
        assert "one set of word boxes" not in note

    def test_ids_are_compared_as_strings(self):
        """`text_id` arrives as whatever the frame held — int on one side and
        str on the other is the same text, not a mismatch."""
        assert _different_texts_note("7", "7", overlaid=True) is None
