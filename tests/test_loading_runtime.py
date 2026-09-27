"""UX-165: loading cards at runtime — hidden, revealed, cancelled, released."""

from __future__ import annotations

import threading

import pytest

from scanpath_studio import loading, progress

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _frozen_card_script():
    import streamlit as st

    from scanpath_studio import loading

    def on_cancel():
        st.session_state["cancelled"] = True

    with loading.run_scope():
        slot = st.empty()
        loading.Card(
            slot,
            key="t",
            title="Building the thing",
            steps=("One", "Two"),
            step_list=True,
            cancel=loading.Cancel("Stop it", on_cancel),
        ).open()
        st.stop()


def test_a_revealed_card_shows_its_steps_and_a_working_cancel(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 0)
    # The script stops with the card still open (never explicitly closed);
    # this test inspects that frozen card, so it opts out of the production
    # off-thread clear `run_scope` now runs on any card still open at exit.
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_frozen_card_script).run()
    assert not at.exception
    text = _markdown(at)
    assert "Building the thing" in text and "sps-steps" in text
    assert "sps-reveal" in text
    cancel = at.button(key="sps_cancel_t")
    assert cancel.label == "Stop it"
    cancel.click().run()
    assert at.session_state["cancelled"] is True


def _fast_card_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        slot = st.empty()
        with loading.card(slot, key="fast", title="Quick", size=(400, 300)) as opened:
            st.session_state["covered_inside"] = loading.covered()
        st.session_state["covered_after"] = loading.covered()
        st.session_state["was_revealed"] = opened.revealed
        st.write("after")


def test_a_fast_card_never_shows_and_leaves_nothing_behind(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 30)  # never let the ticker win the race
    at = AppTest.from_function(_fast_card_script).run()
    assert not at.exception
    assert "sps-card-head" not in _markdown(at)
    assert "sps-size-box" not in _markdown(at)
    assert not [b for b in at.button if b.key and b.key.startswith("sps_cancel_")]
    assert at.session_state["covered_inside"] is True
    assert at.session_state["covered_after"] is False
    assert at.session_state["was_revealed"] is False


def _leaky_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        card = loading.Card(st.empty(), key="leak", title="Never closed").open()
        st.session_state["ticker_armed"] = (
            card._ticker is not None and card._ticker.is_alive()
        )


def test_run_scope_stops_every_timer_a_run_leaves_open(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 30)
    before = {t.ident for t in threading.enumerate()}
    at = AppTest.from_function(_leaky_script).run()
    assert not at.exception
    assert at.session_state["ticker_armed"] is True
    leaked = [
        t
        for t in threading.enumerate()
        if t.ident not in before
        and t.name == "scanpath-loading-ticker"
        and t.is_alive()
    ]
    assert not leaked


def _cancelled_script():
    from scanpath_studio import loading, progress

    with loading.run_scope():
        raise progress.Cancelled("abandoned")


def test_run_scope_ends_a_cancelled_run_quietly():
    at = AppTest.from_function(_cancelled_script).run()
    assert not at.exception


def _page_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        area = st.container(key=loading.VIEW_AREA_KEY)
        first = area.empty()
        page = loading.page(first, view="scanpath", plot_height=300)
        dataset = page.open_card(
            title="Loading Demo", steps=("Reading files",), reveal_now=True
        )
        dataset.finish()
        dataset.close(keep=True)
        with area:
            with loading.card(st.empty(), key="plot", title="Drawing") as plot:
                st.session_state["plot_inherited_reveal"] = plot.revealed
                st.stop()


def test_a_region_card_releases_the_page_and_inherits_its_reveal(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 5)
    # The script stops mid-plot-card; this test inspects the frozen card, so
    # it opts out of the production off-thread clear that `st.stop()` now
    # triggers (see test_a_stopped_card_clears_off_thread_unless_kept).
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    text = _markdown(at)
    assert "sps-sk-scanpath" not in text  # the page skeleton is gone
    assert "Drawing" in text  # the plot card took over, already revealed
    assert at.session_state["plot_inherited_reveal"] is True


def _stopped_card_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        with loading.card(st.empty(), key="stopped", title="Stopping"):
            st.stop()


def test_a_stopped_card_clears_off_thread_unless_kept(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 0)  # reveal at once, nothing to race
    at = AppTest.from_function(_stopped_card_script).run()
    assert not at.exception
    assert "Stopping" not in _markdown(at)

    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_stopped_card_script).run()
    assert not at.exception
    assert "Stopping" in _markdown(at)


def _timer_reveal_script():
    import time

    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        card = loading.Card(st.empty(), key="ticking", title="Ticking along").open()
        deadline = time.monotonic() + 3.0
        while not card.revealed and time.monotonic() < deadline:
            time.sleep(0.01)
        st.session_state["revealed_in_time"] = card.revealed
        st.stop()


def test_the_timer_thread_reveals_a_card_after_the_delay(monkeypatch):
    monkeypatch.setattr(loading, "DELAY_S", 0.05)
    # Inspecting the revealed-but-frozen card, same as the region-card test above.
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_timer_reveal_script).run()
    assert not at.exception
    assert at.session_state["revealed_in_time"] is True
    text = _markdown(at)
    assert "Ticking along" in text
    assert "sps-reveal" in text


def test_spinner_is_silent_under_a_card(monkeypatch):
    class _Run:
        cards = [type("C", (), {"is_open": True})()]
        page = None

    monkeypatch.setattr(
        loading, "_RUN", type("V", (), {"get": staticmethod(lambda: _Run())})()
    )
    assert loading.covered() is True
    assert loading.spinner("x").__class__.__name__ == "nullcontext"


def test_spinner_falls_through_to_streamlits_own_outside_a_card():
    cm = loading.spinner("x")
    assert cm.__class__.__name__ != "nullcontext"


def _task_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        with loading.card(st.empty(), key="p", title="t", task_key=("k", "run")):
            st.session_state["active_inside"] = progress.active() is not None
        st.session_state["active_after"] = progress.active() is not None


def test_a_card_activates_its_task_and_finishes_it_on_a_clean_exit():
    at = AppTest.from_function(_task_script).run()
    assert not at.exception
    assert at.session_state["active_inside"] is True
    assert at.session_state["active_after"] is False
    assert progress._REGISTRY[("k", "run")].finished is True


def _failing_card_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        try:
            with loading.card(
                st.empty(), key="boom", title="t", task_key=("k", "boom")
            ):
                raise ValueError("kaboom")
        except ValueError:
            pass
        st.session_state["retired"] = progress._REGISTRY[("k", "boom")].finished


def test_a_failed_card_retires_its_explicit_task_so_a_later_run_does_not_join_it():
    at = AppTest.from_function(_failing_card_script).run()
    assert not at.exception
    assert at.session_state["retired"] is True
