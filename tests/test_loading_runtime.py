"""UX-165: loading cards at runtime — hidden, revealed, cancelled, released."""

from __future__ import annotations

import gc
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


def test_a_cancelled_run_ends_with_no_error_on_the_page():
    at = AppTest.from_function(_cancelled_script).run()
    assert not at.exception


def _cancelled_mid_card_script():
    import streamlit as st
    from streamlit.runtime.scriptrunner import StopException

    from scanpath_studio import loading, progress

    surfaced = None
    try:
        with loading.run_scope():
            card = loading.Card(st.empty(), key="cut", title="Cut short").open(
                reveal_now=True
            )
            st.session_state["card"] = card
            st.session_state["armed"] = card._ticker is not None
            raise progress.Cancelled("abandoned")
    except StopException:
        surfaced = "StopException"
    st.session_state["surfaced"] = surfaced
    st.session_state["halted"] = st.session_state["card"]._ticker is None


def test_a_cancelled_run_ends_as_a_stopped_one_and_still_clears_its_card(
    monkeypatch,
):
    """`run_scope` turns a `Cancelled` into Streamlit's own `StopException`, so
    the run ends as a premature stop — and its `finally` still halts and
    clears every card the run left open."""
    monkeypatch.setattr(loading, "DELAY_S", 30)  # shown at once, its timer armed
    at = AppTest.from_function(_cancelled_mid_card_script).run()
    assert not at.exception, at.exception
    assert at.session_state["surfaced"] == "StopException"
    assert at.session_state["armed"] is True
    assert at.session_state["halted"] is True
    assert "Cut short" not in _markdown(at)


def _cancelled_before_a_widget_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        if st.session_state.get("cancel_now"):
            raise progress.Cancelled("abandoned")
        st.text_input("Below the cancel point", key="later_field")


def test_a_cancelled_run_keeps_the_widgets_it_never_reached():
    """A run cut short that ends as a normal finish gets Streamlit's
    stale-widget sweep, which drops the state of every widget it never reached;
    only a premature stop (`StopException`) is spared it."""
    at = AppTest.from_function(_cancelled_before_a_widget_script).run()
    at.text_input(key="later_field").input("kept").run()
    assert at.session_state["later_field"] == "kept"
    at.session_state["cancel_now"] = True
    at.run()
    assert not at.exception, at.exception
    assert "later_field" in at.session_state
    assert at.session_state["later_field"] == "kept"


def _page_script():
    import time

    import streamlit as st

    from scanpath_studio import loading

    mode = st.session_state.get("page_mode", "slow")
    with loading.run_scope():
        area = st.container(key=loading.VIEW_AREA_KEY)
        page = loading.page(area.empty(), view="scanpath", plot_height=300)
        dataset = page.open_card(
            title="Loading Demo", steps=("Reading files",), reveal_now=mode != "slow"
        )
        if mode == "slow":  # a slow load: the page's own timer reveals it
            deadline = time.monotonic() + 3.0
            while not dataset.revealed and time.monotonic() < deadline:
                time.sleep(0.01)
        elif mode == "lingering":  # shown at once, then up for a while
            time.sleep(loading.DELAY_S * 1.5)
        dataset.finish()
        dataset.close(keep=True)
        with area:
            with loading.card(st.empty(), key="plot", title="Drawing") as plot:
                st.session_state["plot_revealed_at_once"] = plot.revealed
                st.stop()


@pytest.mark.parametrize("mode", ["slow", "lingering"])
def test_a_region_card_releases_the_page_and_inherits_a_seen_reveal(monkeypatch, mode):
    """A page the user saw — revealed by its timer, or up for at least DELAY_S —
    hands its reveal on: the plot card shows at once, long before its own timer
    could have revealed it."""
    monkeypatch.setattr(loading, "DELAY_S", 0.2)
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    # The script stops mid-plot-card; this test inspects the frozen card, so
    # it opts out of the production off-thread clear that `st.stop()` now
    # triggers (see test_a_stopped_card_clears_off_thread_unless_kept).
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_page_script)
    at.session_state["page_mode"] = mode
    at.run()
    assert not at.exception
    text = _markdown(at)
    assert "sps-sk-scanpath" not in text  # the page skeleton is gone
    assert "Drawing" in text  # the plot card took over, already revealed
    assert at.session_state["plot_revealed_at_once"] is True


def test_a_page_shown_and_released_at_once_hands_nothing_on(monkeypatch):
    """A quick view switch reveals the page at once and releases it a moment
    later; the view's first card must not inherit that and flash for a frame."""
    monkeypatch.setattr(loading, "DELAY_S", 30)
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_page_script)
    at.session_state["page_mode"] = "instant"
    at.run()
    assert not at.exception
    assert at.session_state["plot_revealed_at_once"] is False
    assert "Drawing" not in _markdown(at)


def _inherit_script():
    """A seen page, then one region card per ``plan`` entry, in order:
    ``"plain"`` (ungated), ``"gated_silent"`` (gated, reports nothing — a cache
    hit) or ``"gated_reports"`` (gated, reports at once — a miss)."""
    import time

    import streamlit as st

    from scanpath_studio import loading, progress

    seen = []
    with loading.run_scope():
        area = st.container(key=loading.VIEW_AREA_KEY)
        page = loading.page(area.empty(), view="scanpath", plot_height=300)
        dataset = page.open_card(title="Loading Demo", steps=("Reading files",))
        deadline = time.monotonic() + 3.0
        while not dataset.revealed and time.monotonic() < deadline:
            time.sleep(0.01)  # a slow load: the page's own timer reveals it
        dataset.finish()
        dataset.close(keep=True)
        with area:
            for index, kind in enumerate(st.session_state["plan"]):
                with loading.card(
                    st.empty(),
                    key=f"c{index}",
                    title=f"Card {index}",
                    reveal_on_work=kind != "plain",
                ) as opened:
                    record = {"at_open": opened.revealed}
                    if kind == "gated_reports":
                        reported = time.monotonic()
                        progress.report()  # a miss: real work starts
                        deadline = reported + 3.0
                        while not opened.revealed and time.monotonic() < deadline:
                            time.sleep(0.005)
                        record["shown_after"] = time.monotonic() - reported
                    elif kind == "gated_silent":
                        # Several refreshes, and past the card's own delay too.
                        time.sleep(max(6 * loading.REFRESH_S, 1.5 * loading.DELAY_S))
                    record["at_close"] = opened.revealed
                seen.append(record)
    st.session_state["seen"] = seen


@pytest.fixture
def after_a_seen_wait(monkeypatch):
    """Run `_inherit_script` with ``plan``; the delay is real (> 0), so only the
    carried wait can show a card the moment it opens."""
    monkeypatch.setattr(loading, "DELAY_S", 0.5)
    monkeypatch.setattr(loading, "REFRESH_S", 0.02)

    def run(*plan: str) -> list[dict]:
        at = AppTest.from_function(_inherit_script, default_timeout=20)
        at.session_state["plan"] = list(plan)
        at.run()
        assert not at.exception, at.exception
        return at.session_state["seen"]

    return run


def test_a_gated_card_carries_a_seen_wait_on_to_the_figures_card(after_a_seen_wait):
    """After a slow dataset switch the user saw, Compare's B card (gated) opens
    first. On a cache hit it must neither flash nor use up the page's reveal —
    or the figure card waits its own delay with the previous dataset's figure
    unveiled under the new controls."""
    b_card, figure = after_a_seen_wait("gated_silent", "plain")
    assert b_card == {"at_open": False, "at_close": False}
    assert figure["at_open"] is True


def test_a_gated_card_that_works_after_a_seen_wait_shows_without_the_delay(
    after_a_seen_wait,
):
    """Through its gate, but with no delay: the moment its task reports — a
    real load of B — it shows, within about one refresh; and the figure card
    after it still shows at once."""
    b_card, figure = after_a_seen_wait("gated_reports", "plain")
    assert b_card["at_open"] is False
    assert b_card["at_close"] is True
    assert b_card["shown_after"] < loading.DELAY_S / 2
    assert figure["at_open"] is True


def test_a_seen_wait_is_carried_on_to_one_card_only(after_a_seen_wait):
    """The first ungated card uses the carried wait up; one after it waits its
    own delay like any other, rather than flashing for a frame."""
    _, first, second = after_a_seen_wait("gated_silent", "plain", "plain")
    assert first["at_open"] is True
    assert second["at_open"] is False


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
        with loading.card(
            st.empty(), key="p", title="t", task_key=("k", "run")
        ) as opened:
            st.session_state["active_inside"] = progress.active() is not None
            st.session_state["task"] = opened.task  # held past the run
        st.session_state["active_after"] = progress.active() is not None


def test_a_card_activates_its_task_and_finishes_it_on_a_clean_exit():
    at = AppTest.from_function(_task_script).run()
    assert not at.exception
    assert at.session_state["active_inside"] is True
    assert at.session_state["active_after"] is False
    assert at.session_state["task"].finished is True


def _finished_card_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        with loading.card(st.empty(), key="gone", title="t", task_key=("k", "gone")):
            pass


def test_a_runs_task_leaves_the_registry_once_the_run_is_over():
    """UX-165: every task key carries the session id, so a registry that kept
    each task for the life of the server grew with every session. A task stays
    registered exactly while something holds it — during the run, its card."""
    at = AppTest.from_function(_finished_card_script).run()
    assert not at.exception
    gc.collect()
    assert ("k", "gone") not in progress._REGISTRY


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


def _released_mid_load_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        page = loading.page(st.empty(), view="scanpath")
        card = page.open_card(
            title="Loading",
            steps=("Reading files", "Normalizing"),
            task_key=("k", "released-mid-load"),
            duration_key=("d", "released-mid-load"),
        )
        card.step(1)
        progress.report()  # real work, so only the retire can stop the record
        page.release()  # an inline download interrupts the load
        task = progress._REGISTRY[("k", "released-mid-load")]
        st.session_state["retired"] = task.finished
        card.finish()  # the pipeline carries on after a failed download
        st.session_state["recorded"] = progress.last_duration(
            ("d", "released-mid-load")
        )


def test_releasing_the_page_mid_load_retires_its_task(monkeypatch):
    """The next run must start that load's card afresh, not join a task stopped
    mid-step — and the load it interrupted is no "last load" to quote."""
    monkeypatch.setattr(loading, "DELAY_S", 0)  # any wait would count
    monkeypatch.delitem(progress._DURATIONS, ("d", "released-mid-load"), raising=False)
    at = AppTest.from_function(_released_mid_load_script).run()
    assert not at.exception
    assert at.session_state["retired"] is True
    assert at.session_state["recorded"] is None


def _aborted_release_script():
    import streamlit as st
    from streamlit.runtime.scriptrunner import StopException

    from scanpath_studio import loading, progress

    class _StoppedSlot:  # a stopped run: Streamlit raises instead of sending
        def empty(self):
            raise StopException()

    with loading.run_scope():
        page = loading.page(st.empty(), view="scanpath")
        page.open_card(title="Loading", task_key=("k", "aborted-release"))
        page._slot = _StoppedSlot()
        try:
            page.release()
        except StopException:
            pass
        task = progress._REGISTRY[("k", "aborted-release")]
        st.session_state["retired"] = task.finished


def test_a_release_streamlit_aborts_leaves_the_task_joinable():
    at = AppTest.from_function(_aborted_release_script).run()
    assert not at.exception
    assert at.session_state["retired"] is False


def _waiting_card_script():
    import threading
    import time

    import streamlit as st
    from streamlit.runtime.scriptrunner import add_script_run_ctx

    from scanpath_studio import data, loading

    building, release = threading.Event(), threading.Event()

    def earlier_runs_build():
        building.set()
        release.wait(timeout=5)
        return "measures"

    with loading.run_scope():
        # An earlier run of this session, still computing: its thread owns the
        # build and reports into a task of its own, never this run's.
        earlier = threading.Thread(
            target=lambda: data.frame_cache("t_waiter", "key", earlier_runs_build),
            daemon=True,
        )
        add_script_run_ctx(earlier)
        earlier.start()
        building.wait(timeout=5)
        with loading.card(
            st.empty(),
            key="waiting",
            title="Computing reading measures",
            reveal_on_work=True,
        ) as card:

            def release_once_shown():
                deadline = time.monotonic() + 1.5
                while not card.revealed and time.monotonic() < deadline:
                    time.sleep(0.01)
                release.set()

            threading.Thread(target=release_once_shown, daemon=True).start()
            st.session_state["waited_for"] = data.frame_cache(
                "t_waiter", "key", lambda: "rebuilt"
            )
            st.session_state["waiter_revealed"] = card.revealed
        earlier.join(timeout=5)


def test_a_gated_card_over_a_build_another_run_owns_shows(monkeypatch):
    """A click that leaves the Corpus pool unchanged lands on the measures the
    last run is still computing: this run's card begins a fresh task and waits
    in `frame_cache` for that build. The wait is this run's work, so the card
    shows for it."""
    monkeypatch.setattr(loading, "DELAY_S", 0.05)
    monkeypatch.setattr(loading, "REFRESH_S", 0.02)
    at = AppTest.from_function(_waiting_card_script, default_timeout=10).run()
    assert not at.exception, at.exception
    assert at.session_state["waited_for"] == "measures"  # the earlier run's build
    assert at.session_state["waiter_revealed"] is True


def _timed_card_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        with loading.card(
            st.empty(), key="timed", title="Quick", duration_key=("d", "timed")
        ):
            progress.report()  # real work: a quick one


def test_last_load_is_recorded_only_for_a_real_wait(monkeypatch):
    """The dataset card opens on every run: a plain rerun's few milliseconds must
    not overwrite the real load's time as "last load". (A run that did no work
    at all records nothing however long it took — the gated card below.)"""
    monkeypatch.delitem(progress._DURATIONS, ("d", "timed"), raising=False)
    monkeypatch.setattr(loading, "DELAY_S", 30)  # far longer than the block
    AppTest.from_function(_timed_card_script).run()
    assert progress.last_duration(("d", "timed")) is None
    monkeypatch.setattr(loading, "DELAY_S", 0)  # every wait counts
    AppTest.from_function(_timed_card_script).run()
    assert progress.last_duration(("d", "timed")) is not None


def _gated_card_script():
    import time

    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        with loading.card(
            st.empty(),
            key="gated",
            title="Checking the cache",
            reveal_on_work=True,
            duration_key=("d", "gated"),
        ) as card:
            # Well past the delay before anything reports, so only the gate can
            # be what holds the card back.
            time.sleep(loading.DELAY_S * 4)
            if st.session_state["gated_reports"]:
                progress.report()  # a cache miss: real work starts
                deadline = time.monotonic() + 3.0
                while not card.revealed and time.monotonic() < deadline:
                    time.sleep(0.01)
            st.session_state["gated_revealed"] = card.revealed


@pytest.mark.parametrize("reports", [False, True])
def test_a_gated_card_shows_only_once_its_task_has_worked(monkeypatch, reports):
    """UX-166: a card over work that is cheap on a cache hit (``reveal_on_work``)
    stays hidden however long its block runs until its task reports — then the
    timer, checking again every ``REFRESH_S``, reveals it. And only such a load
    is a "last load" to quote: a rerun that did no work records nothing."""
    monkeypatch.setattr(loading, "DELAY_S", 0.05)
    monkeypatch.setattr(loading, "REFRESH_S", 0.02)
    monkeypatch.delitem(progress._DURATIONS, ("d", "gated"), raising=False)
    at = AppTest.from_function(_gated_card_script)
    at.session_state["gated_reports"] = reports
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["gated_revealed"] is reports
    assert (progress.last_duration(("d", "gated")) is not None) is reports


def _failing_run_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        page = loading.page(st.empty(), view="scanpath")
        card = page.open_card(title="Loading", task_key=("k", "failed-run"))
        st.session_state["task"] = card.task  # held past the run
        raise ValueError("the pipeline broke")


def test_a_run_that_fails_retires_its_open_cards_tasks():
    """Nothing will resume a load an ordinary error ended, so a later run must
    not join it; the error itself still reaches the page."""
    at = AppTest.from_function(_failing_run_script).run()
    assert at.exception
    assert at.session_state["task"].finished is True


def _stopped_run_script():
    import streamlit as st

    from scanpath_studio import loading

    with loading.run_scope():
        page = loading.page(st.empty(), view="scanpath")
        card = page.open_card(title="Loading", task_key=("k", "stopped-run"))
        # Held past the run, as a superseded run's still-computing thread holds
        # it: the case joining exists for.
        st.session_state["task"] = card.task
        st.stop()


def test_a_stopped_run_leaves_its_open_cards_tasks_joinable():
    at = AppTest.from_function(_stopped_run_script).run()
    assert not at.exception
    task = at.session_state["task"]
    assert task.finished is False
    assert progress.begin(("k", "stopped-run"), title="Loading") is task


def _last_load_script():
    import streamlit as st

    from scanpath_studio import loading, progress

    with loading.run_scope():
        page = loading.page(st.empty(), view="data")
        card = page.open_card(
            title="Loading X",
            steps=("Reading files",),
            task_key=("d", "last-at-open-task"),
            duration_key=("d", "last-at-open"),
        )
        progress.report()  # real work, so `finish` has a duration to record
        card.finish()  # records this load's own (tiny) duration
        card.close(keep=True)  # the kept card's final repaint
        st.stop()


def test_the_last_load_hint_quotes_the_previous_load_not_this_one(monkeypatch):
    """The hint is read once, when the card opens: the final repaint after
    `finish` must not quote the load's own time back as its "last load"."""
    monkeypatch.setitem(progress._DURATIONS, ("d", "last-at-open"), 6.0)
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at = AppTest.from_function(_last_load_script).run()
    assert not at.exception, at.exception
    assert progress.last_duration(("d", "last-at-open")) < 6.0  # its own, recorded
    assert "last load 6.0 s" in _markdown(at)
