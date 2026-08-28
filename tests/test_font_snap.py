"""BUG-50: a corpus' declared typeface must not outlive the corpus.

MultiplEYE stamps the stimulus `FONT_SIZE` + family onto its words, and
`app.seed_canvas_state` snaps the font controls to them so the reading text
matches the stimulus exactly. The snap was one-way: it was gated on the *new*
source declaring a font, so a source that declares none — the demo, OneStop,
PoTeC, every upload — skipped the block and silently inherited the previous
corpus' answer. Demo → MultiplEYE → Demo came back with MultiplEYE's px, its CJK
stack and **scale-to-boxes off**, so the demo's reading text rendered visibly
smaller with nothing on screen saying why.

The general shape is worth pinning, not just the symptom: a source-switch snap
writes *session*-scoped state to express a *source*-scoped fact, and that only
stays consistent if leaving the source undoes it.
"""

from __future__ import annotations

import pandas as pd
import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

_WORDS = pd.DataFrame(
    {
        "participant_id": ["p1"],
        "trial_id": ["t1"],
        "x": [0.0],
        "y": [0.0],
        "width": [10.0],
        "height": [10.0],
        "text": ["a"],
        "word_id": [0],
    }
)
_FIXATIONS = pd.DataFrame(
    {
        "participant_id": ["p1"],
        "trial_id": ["t1"],
        "x": [1.0],
        "y": [1.0],
        "duration_ms": [100],
    }
)
#: What a corpus that declares its stimulus typeface looks like on the way in.
_WORDS_WITH_FONT = _WORDS.assign(
    stimulus_font_px=[22.0],
    stimulus_font_family=["'Noto Sans Mono CJK SC', monospace"],
)

_FONT_STATE = (
    "global_base_font_size",
    "global_font_family",
    "global_scale_text_to_boxes",
)


@pytest.fixture
def session(monkeypatch):
    """A bare `st.session_state`, cleared between tests."""
    import streamlit as st

    st.session_state.clear()
    yield st.session_state
    st.session_state.clear()


def _seed(choice, words):
    from scanpath_studio import app
    import streamlit as st

    st.session_state["data_source_choice"] = choice
    st.session_state["public_dataset_choice"] = choice
    app.seed_canvas_state(words, _FIXATIONS, data_choice=choice)


def _font(session):
    return tuple(session.get(key) for key in _FONT_STATE)


class TestTheRoundTrip:
    def test_a_declared_font_is_snapped_to(self, session):
        _seed("MultiplEYE", _WORDS_WITH_FONT)

        size, family, scale = _font(session)
        assert size == 22
        assert "Noto Sans Mono CJK SC" in family
        # The precise px is known, so box geometry can only approximate it.
        assert scale is False

    def test_leaving_that_corpus_puts_the_controls_back(self, session):
        """The bug: this used to come back as (22, CJK, False)."""
        _seed("Bundled Demo", _WORDS)
        before = _font(session)

        _seed("MultiplEYE", _WORDS_WITH_FONT)
        assert _font(session) != before

        _seed("Bundled Demo", _WORDS)
        assert _font(session) == before

    def test_a_hand_tuned_font_survives_the_detour(self, session):
        """Restoring the stashed values rather than the factory defaults is what
        makes "look at that corpus and come back" non-destructive."""
        _seed("Bundled Demo", _WORDS)
        session["global_base_font_size"] = 29
        tuned = _font(session)

        _seed("MultiplEYE", _WORDS_WITH_FONT)
        _seed("Bundled Demo", _WORDS)

        assert _font(session) == tuned

    def test_two_font_declaring_corpora_in_a_row_restore_the_original(self, session):
        """The stash is taken on the *first* snap of a run of them, so the third
        source gets the pre-MultiplEYE state and not MultiplEYE's."""
        _seed("Bundled Demo", _WORDS)
        before = _font(session)

        _seed("MultiplEYE", _WORDS_WITH_FONT)
        _seed(
            "Another corpus",
            _WORDS.assign(stimulus_font_px=[31.0], stimulus_font_family=["serif"]),
        )
        assert _font(session)[0] == 31

        _seed("Bundled Demo", _WORDS)
        assert _font(session) == before

    def test_staying_on_one_source_does_not_re_snap(self, session):
        """Manual edits within a source stick — the key is unchanged, so the
        snap must not re-fire over them."""
        _seed("MultiplEYE", _WORDS_WITH_FONT)
        session["global_base_font_size"] = 40

        _seed("MultiplEYE", _WORDS_WITH_FONT)

        assert session["global_base_font_size"] == 40


class TestWhatMustNotBeTouched:
    def test_a_deep_link_on_a_font_less_source_is_left_alone(self, session):
        """Nothing overwrote these, so there is nothing to undo — the restore
        must not fire on a source that was never snapped away from."""
        session["global_base_font_size"] = 27
        session["global_font_family"] = "Georgia, serif"
        session["global_scale_text_to_boxes"] = False
        linked = _font(session)

        _seed("Bundled Demo", _WORDS)

        assert _font(session) == linked

    def test_a_key_absent_before_the_snap_returns_to_its_factory_value(self, session):
        """Popping it lets the `defaults` pin restore the factory value in the
        same run, rather than freezing whatever the last corpus left."""
        _seed("MultiplEYE", _WORDS_WITH_FONT)
        _seed("Bundled Demo", _WORDS)

        assert session["global_base_font_size"] == 16
        assert session["global_scale_text_to_boxes"] is True


class TestTheSnapIsWireFormat:
    def test_every_key_the_snap_writes_is_a_saved_setting(self):
        """Why the leak outlived the session that caused it: all three keys ride
        the share link and the saved config, so a leaked font was persisted."""
        from scanpath_studio import session_keys as sk
        from scanpath_studio.app import _FONT_SNAP_KEYS

        wire = set(sk.SHARE_PARAMS.values()) | set(sk.PLOT_CONFIG_STATE_KEYS)
        assert set(_FONT_SNAP_KEYS) <= wire, set(_FONT_SNAP_KEYS) - wire

    def test_the_stash_key_is_not(self):
        """It is bookkeeping about a snap, not a setting — it must never travel."""
        from scanpath_studio import session_keys as sk
        from scanpath_studio.app import _FONT_SNAP_RESTORE_KEY

        assert _FONT_SNAP_RESTORE_KEY.startswith("_")
        assert _FONT_SNAP_RESTORE_KEY not in set(sk.SHARE_PARAMS.values())
        assert _FONT_SNAP_RESTORE_KEY not in set(sk.PLOT_CONFIG_STATE_KEYS)
