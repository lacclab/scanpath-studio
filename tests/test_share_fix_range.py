"""UX-135: VIZ-7's fixation-index window on the deep-link / Share surface.

The window reached the UI, ``render --fix-index-range`` and ``api``'s
``fix_index_range``, but not a link — so a shared "fixations 5–20" view opened
as the whole trial and nothing said so. The awkward half is the *write* side:
``single_fix_range`` is set to the trial's own full range the moment the slider
renders, so a generic range emitter would stamp ``fix_range`` onto every link
ever copied and re-window every recipient. Two conditions gate it, and both are
driven here alongside the reader.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _link_app():
    """Apply whatever deep link the test seeded into ``query_params``."""
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_window"] = st.session_state.get("single_fix_range")


def _share_app():
    """Build a Share link from the window + flags the test seeded."""
    from urllib.parse import parse_qs

    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    query, _caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_params"] = parse_qs(query)


def _share(*, window, user_set, full=None):
    at = AppTest.from_function(_share_app)
    at.session_state["single_fix_range"] = window
    at.session_state["single_fix_range_user_set"] = user_set
    selection = {"participant_id": "p1", "trial_id": "t1"}
    if full is not None:
        selection["full_fix_range"] = full
    at.session_state["_share_selection"] = selection
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at.session_state["_params"]


class TestTheReader:
    def test_a_linked_window_seeds_the_slider(self):
        at = AppTest.from_function(_link_app)
        at.query_params["fix_range"] = "5,20"
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_window"] == (5, 20)

    def test_a_reversed_window_is_ordered_not_rejected(self):
        """`_parse_int_range` sorts the pair, so a hand-typed link still opens."""
        at = AppTest.from_function(_link_app)
        at.query_params["fix_range"] = "20,5"
        at.run(timeout=30)
        assert at.session_state["_window"] == (5, 20)

    def test_a_link_without_the_param_leaves_the_window_alone(self):
        at = AppTest.from_function(_link_app)
        at.run(timeout=30)
        assert at.session_state["_window"] is None

    def test_the_slider_treats_a_linked_window_as_deliberate(self):
        """The value arrives before the widget renders, and must survive it.

        `controls._render_fix_range_slider` re-expands an *auto* window to the
        trial's full range on every run; only the `user_set` flag stops that, and
        a deep link never gets to click anything.
        """
        import pandas as pd
        import streamlit as st

        from scanpath_studio.controls import _render_fix_range_slider

        fixations = pd.DataFrame({"order_in_trial": list(range(1, 31))})
        st.session_state.clear()
        st.session_state["single_fix_range"] = (5, 20)
        _render_fix_range_slider(fixations)
        assert st.session_state["single_fix_range"] == (5, 20)
        assert st.session_state["single_fix_range_user_set"] is True


class TestTheWriter:
    def test_a_chosen_window_travels(self):
        params = _share(window=(5, 20), user_set=True, full=(1, 30))
        assert params["fix_range"] == ["5,20"]

    def test_an_untouched_window_does_not(self):
        """The default *is* the full range, so every link would carry one."""
        params = _share(window=(1, 30), user_set=False, full=(1, 30))
        assert "fix_range" not in params

    def test_a_window_dragged_back_out_to_both_ends_does_not(self):
        """It restores nothing, and would truncate a longer copy of the trial."""
        params = _share(window=(1, 30), user_set=True, full=(1, 30))
        assert "fix_range" not in params

    def test_a_multipart_screens_own_full_range_is_respected(self):
        """BUG-47: `order_in_trial` is parent-global, so a later screen's full
        range starts at 509 — the published range, not a hard-coded 1."""
        params = _share(window=(509, 578), user_set=True, full=(509, 578))
        assert "fix_range" not in params
        params = _share(window=(509, 540), user_set=True, full=(509, 578))
        assert params["fix_range"] == ["509,540"]

    def test_without_a_published_full_range_the_flag_alone_decides(self):
        """A trial with no `order_in_trial` publishes none; a dragged window
        still has to travel."""
        params = _share(window=(5, 20), user_set=True)
        assert params["fix_range"] == ["5,20"]
        assert "fix_range" not in _share(window=(5, 20), user_set=False)


class TestTheContract:
    def test_the_param_is_pinned_as_optional(self):
        """It is emitted only sometimes, so it belongs in `URL_OPTIONAL_PARAMS`
        rather than in the set every populated session emits."""
        from scanpath_studio import session_keys as sk

        assert sk.FIX_RANGE_PARAM in sk.URL_OPTIONAL_PARAMS
        assert sk.FIX_RANGE_PARAM in sk.URL_PRESET_PARAMS
        assert sk.FIX_RANGE_PARAM not in sk.SHARE_QUERY_PARAMS
        assert sk.SHARE_INT_RANGE_PARAMS[sk.FIX_RANGE_PARAM] == sk.SINGLE_FIX_RANGE

    def test_the_window_now_reaches_every_surface(self):
        """The four-surface rule: UI slider · link · CLI flag · API argument."""
        import inspect

        from scanpath_studio import api, cli
        from scanpath_studio.controls import _render_fix_range_slider
        from scanpath_studio.url_state import _SHARE_INT_RANGE_PARAMS

        assert "single_fix_range" in inspect.getsource(_render_fix_range_slider)
        assert "fix_range" in _SHARE_INT_RANGE_PARAMS
        assert "--fix-index-range" in inspect.getsource(cli)
        assert "fix_index_range" in inspect.signature(api.plot_scanpath).parameters
