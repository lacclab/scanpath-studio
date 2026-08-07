"""BUG-18: a number box's ``on_change`` must not crash when its key is gone.

The UX-9 slider+box pairs give the box a shadow ``{key}__num*`` session key and
commit it to the canonical key from an ``on_change`` callback. Streamlit runs
that callback *before* the script that would recreate the widget, and it drops a
widget's key at the end of any run in which the widget did not render — so a
change queued while a slow rerun was in flight could reach a callback whose own
key no longer existed. The reported crash was

    KeyError: st.session_state has no key "global_heatmap_color_range__num_lo"

from the heatmap colour-range pair, which only renders when the current
trial/metric actually has heatmap data.

These tests drive the callbacks directly, because the failure is invisible in
rendered output: they render the widgets against a fake host, capture the
``on_change`` each box was given, then delete the shadow keys the way end-of-run
pruning would and call it.
"""

from __future__ import annotations

import streamlit as st

from scanpath_studio import controls


class _FakeColumn:
    """Records the ``on_change`` each ``number_input`` is handed."""

    def __init__(self, callbacks: dict) -> None:
        self._callbacks = callbacks

    def slider(self, *args, **kwargs) -> None:
        pass

    def number_input(self, *args, **kwargs) -> None:
        self._callbacks[kwargs["key"]] = kwargs["on_change"]


class _FakeHost:
    def __init__(self, callbacks: dict) -> None:
        self._callbacks = callbacks

    def columns(self, spec, **kwargs):
        return [_FakeColumn(self._callbacks) for _ in spec]


def _render(builder, key, **kwargs) -> dict:
    callbacks: dict = {}
    builder(_FakeHost(callbacks), "Label", key=key, **kwargs)
    return callbacks


def test_single_box_commits_its_value() -> None:
    key = "test_bug18_single"
    st.session_state[key] = 5.0
    callbacks = _render(
        controls._numeric_slider, key, min_value=0.0, max_value=10.0, step=0.5
    )
    st.session_state[f"{key}__num"] = 7.5
    callbacks[f"{key}__num"]()
    assert st.session_state[key] == 7.5


def test_single_box_callback_is_a_no_op_without_its_key() -> None:
    key = "test_bug18_single_pruned"
    st.session_state[key] = 5.0
    callbacks = _render(
        controls._numeric_slider, key, min_value=0.0, max_value=10.0, step=0.5
    )
    del st.session_state[f"{key}__num"]  # end-of-run pruning

    callbacks[f"{key}__num"]()  # must not raise

    assert st.session_state[key] == 5.0  # last committed value survives


def test_range_boxes_commit_a_sorted_pair() -> None:
    key = "test_bug18_range"
    st.session_state[key] = (1.0, 9.0)
    callbacks = _render(
        controls._range_slider, key, min_value=0.0, max_value=10.0, step=0.5
    )
    # A min typed above the max is swapped, not rejected.
    st.session_state[f"{key}__num_lo"] = 8.0
    st.session_state[f"{key}__num_hi"] = 2.0
    callbacks[f"{key}__num_lo"]()
    assert st.session_state[key] == (2.0, 8.0)


def test_range_callback_is_a_no_op_when_either_key_is_gone() -> None:
    key = "test_bug18_range_pruned"
    for missing in (f"{key}__num_lo", f"{key}__num_hi"):
        st.session_state[key] = (1.0, 9.0)
        callbacks = _render(
            controls._range_slider, key, min_value=0.0, max_value=10.0, step=0.5
        )
        del st.session_state[missing]

        callbacks[f"{key}__num_lo"]()  # must not raise

        assert st.session_state[key] == (1.0, 9.0)


def test_a_no_op_callback_does_not_run_the_caller_s_on_change() -> None:
    """The knock-on effect matters as much as the KeyError.

    ``on_change`` hooks here recompute derived state (e.g. trial filters). A
    pruned box has no edit to apply, so nothing downstream should be invalidated.
    """
    key = "test_bug18_on_change"
    calls: list[int] = []
    st.session_state[key] = 5.0
    callbacks = _render(
        controls._numeric_slider,
        key,
        min_value=0.0,
        max_value=10.0,
        step=0.5,
        on_change=lambda: calls.append(1),
    )
    del st.session_state[f"{key}__num"]

    callbacks[f"{key}__num"]()

    assert calls == []
