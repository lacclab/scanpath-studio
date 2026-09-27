"""UX-166 … UX-169 in the running app, via AppTest.

A run freezes with ``st.stop()`` inside the step under test, so the tree keeps
the card that step is showing — with ``loading._KEEP_ON_STOP`` set, since a
stopped run otherwise clears its cards. ``_KEEP_ON_STOP`` also switches off the
run's own end-of-run clear, which is how a test pins that a *release* path took
a card down. ``loading.DELAY_S = 0`` reveals cards on the script thread, so what
AppTest sees does not depend on timing; ``DELAY_S = 30`` makes sure nothing but
an explicit ``reveal_now`` can show one.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import pandas as pd
import pytest

from scanpath_studio import (
    api,
    app,
    compare_source,
    data,
    datasets,
    loading,
    progress,
    tabs,
    utils,
)
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_EDITOR_KEY,
    DATA_OVERVIEW_OFFSCREEN_KEY,
    DATASET_EDITOR_OPEN_KEY,
)
from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY
from scanpath_studio.synthetic import load_synthetic_data, make_multipart_synthetic_data
from tests.conftest import APP_SCRIPT, pin_view

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
SYNTHETIC = "Synthetic test trial"


def _stop(*_args, **_kwargs):
    import streamlit as st

    st.stop()


def _markdown(at) -> str:
    """Every markdown element's source except the app's stylesheets.

    The injected ``<style>`` sheet names every loading class (``.sps-card-head``,
    ``.sps-page-skeleton``, ``.sps-step-done`` …), so leaving it in would make
    each "is it on the page?" check true on every run, and each "is it gone?"
    check false.
    """
    return "\n".join(
        m.value for m in at.markdown if not m.value.lstrip().startswith("<style")
    )


def _markdown_in(block) -> str:
    return "\n".join(m.value for m in block.markdown)


def _loading_an_unavailable_corpus(monkeypatch, download=None):
    """The loader records the corpus as missing — the demo, here the synthetic
    trial, stands in — exactly as `_dataset_access_status` does for a corpus
    that hasn't been downloaded."""
    real_load = app.load_words_and_fixations

    def _load(*args, **kwargs):
        app._note_dataset_unavailable(
            label="A corpus",
            reason="it hasn't been downloaded yet.",
            action="Fetch it once",
            root="/nowhere",
            download=download,
            key_prefix="t6",
        )
        return real_load(*args, **kwargs)

    monkeypatch.setattr(app, "load_words_and_fixations", _load)


@pytest.fixture
def at():
    test = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    test.session_state["data_source_choice"] = SYNTHETIC
    return test


def test_a_finished_load_leaves_no_card_and_no_skeleton(at, monkeypatch):
    """The card showed (``DELAY_S = 0``) and the run's own clear is off, so only
    the release after the dispatch can have taken it and the skeleton down."""
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text
    assert at.session_state[app.LAST_LOADED_SOURCE_KEY] == SYNTHETIC


def test_the_data_page_takes_its_card_down_before_drawing_its_table(at, monkeypatch):
    """The Data branch releases the page first thing: frozen as the table is
    drawn, the card that showed is already gone."""
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "render_dataset_table", _stop)
    pin_view(at, _VIEW_DATA)
    at.run()
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text


def test_a_slow_load_shows_the_skeleton_and_its_step_list(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.session_state["_pending_source_choice"] = "Bundled Demo"
    at.run()
    text = _markdown(at)
    assert "sps-sk-scanpath" in text and "sps-reveal-page" in text
    assert "sps-step-done" in text  # Reading files ✓
    assert "word rows and" in text  # the current step, with the row counts


def test_switching_view_shows_the_target_skeleton_at_once(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 30)  # only `reveal_now` can show it
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "render_corpus_analysis_tab", _stop)
    pin_view(at, _VIEW_CORPUS)
    at.run()
    text = _markdown(at)
    assert "Opening Corpus Analysis" in text
    assert "sps-sk-corpus" in text


def test_a_view_switch_card_has_a_task_of_its_own(at, monkeypatch):
    """The switch card and a load card never join each other's task, while
    ``DATASET_TASK_KEY`` still names the dataset: a switch is not a new load.

    UX-168/Ruling T6-8: the switch card opens with no explicit ``task_key``, so
    it gets ``Card``'s own implicit one (``"card", session, PAGE_CARD_KEY``) —
    a fresh task every time, never the dataset's and never a stale switch's."""
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 30)
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    begun = _hold_every_task(monkeypatch)
    pin_view(at, _VIEW_CORPUS)
    at.run()
    kind, session, token = at.session_state[app.DATASET_TASK_KEY]
    assert (kind, token) == ("dataset", SYNTHETIC)
    view_task = begun[("card", session, loading.PAGE_CARD_KEY)]
    assert view_task.snapshot().title == "Opening Corpus Analysis"


def _hold_every_task(monkeypatch) -> dict:
    """Keep every task `progress.begin` hands out, by key, past its run.

    The registry keeps a task only while something holds it, and a run's cards
    are gone once it ends; this is how a test reads a task a run began.
    """
    begun: dict = {}
    real_begin = progress.begin

    def _begin(key, **kwargs):
        begun[key] = real_begin(key, **kwargs)
        return begun[key]

    monkeypatch.setattr(progress, "begin", _begin)
    return begun


# UX-166 — a card over work that is cheap on a cache hit shows only for real work.


def _slowed(real, seconds: float):
    """``real`` behind a wait that reports nothing: what a plain rerun's cache
    checks cost on a big corpus (hashing the frames each cache hit hands back),
    with no work behind them."""

    def _slow(*args, **kwargs):
        time.sleep(seconds)
        return real(*args, **kwargs)

    return _slow


def _slow_pipeline_frozen_before_the_view(monkeypatch) -> None:
    """A pipeline that outlasts the card's delay many times over, frozen before
    the view releases the page — with the run's own clear off, a page card that
    had shown would still be on the page."""
    monkeypatch.setattr(loading, "DELAY_S", 0.05)
    monkeypatch.setattr(loading, "REFRESH_S", 0.02)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "read_trial_filters", _slowed(app.read_trial_filters, 0.4))
    monkeypatch.setattr(app, "render_single_trial_tab", _stop)


def test_a_plain_rerun_shows_no_page_card_however_long_it_takes(at, monkeypatch):
    """On a big corpus a plain rerun's pipeline — every build a cache hit — can
    outlast the delay, and the card then blanked the view to the skeleton on
    every widget touch. A hit reports nothing, so the card stays hidden."""
    at.run()  # the load itself
    _slow_pipeline_frozen_before_the_view(monkeypatch)
    at.run()  # a plain rerun of the same dataset
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-reveal-page" not in text and "sps-card-head" not in text


def test_the_same_slow_rerun_that_loads_a_dataset_shows_the_page_card(at, monkeypatch):
    """The control: switching dataset normalizes it — a miss, which reports —
    so the same slow pipeline does show the card."""
    at.run()
    _slow_pipeline_frozen_before_the_view(monkeypatch)
    at.session_state["_pending_source_choice"] = app.DEMO_CHOICE
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-reveal-page" in text
    assert f"Loading {app._dataset_display_name(app.DEMO_CHOICE)}" in text


def _reports_on_a_miss(build: Callable[[], object]) -> bool:
    """Run ``build`` under a task of its own, and say whether it reported."""
    task = progress.Task(("t", "gated-miss"), title="Loading")
    token = progress.activate(task)
    try:
        build()
    finally:
        progress.deactivate(token)
    return task.worked


def _normalized_synthetic() -> tuple[pd.DataFrame, pd.DataFrame]:
    return api.load_scanpath_data(*load_synthetic_data())


def test_the_server_bundles_report_on_a_miss(monkeypatch):
    """A gated card opens on a report, so a build under one that reports nothing
    on a miss would never show it, however slow. The file readers and
    normalization report from their loops; these report once, first thing."""
    empty = (pd.DataFrame(), pd.DataFrame())
    monkeypatch.delenv(data.ONESTOP_DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(app, "load_multipleye_server_bundle", lambda _pid: empty)
    for cached in (
        data.load_onestop_server_bundle,
        app._cached_multipleye_server_bundle,
    ):
        cached.clear()
        try:
            assert _reports_on_a_miss(cached), cached.__name__
        finally:
            cached.clear()  # nothing stubbed stays cached for later tests


def test_the_trial_list_and_the_identity_check_report_on_a_miss():
    words, fixations = _normalized_synthetic()
    fresh = ("t", "gated-miss", uuid.uuid4().hex)  # a key nothing has cached
    assert _reports_on_a_miss(
        lambda: utils._build_combo_options_cached(fixations, (), cache_key=fresh)
    )
    assert _reports_on_a_miss(
        lambda: app._cached_trial_identity_report(words, fixations, cache_key=fresh)
    )


def test_a_filter_changes_default_filters_report_on_a_miss():
    """Keyed on the *filtered* pair, so it misses on every filter change while
    everything upstream of it hits: its report is what shows the dataset card
    while the new pool is worked out, rather than only at the trial list. (The
    filtering itself, `data.filter_trials`, is uncached and runs every run —
    a report there would mark every run as work.)"""
    words, fixations = _normalized_synthetic()
    fresh = ("t", "gated-miss", uuid.uuid4().hex)  # a key nothing has cached
    assert _reports_on_a_miss(
        lambda: data._default_filters_cached(words, fixations, cache_key=fresh)
    )


def test_compares_second_dataset_and_the_corpus_measures_report_on_a_miss():
    compare_source._load_builtin_frames.clear()
    assert _reports_on_a_miss(lambda: compare_source._load_builtin_frames(SYNTHETIC))
    words, fixations = _normalized_synthetic()
    assert _reports_on_a_miss(lambda: tabs._corpus_word_measures(words, fixations))


def test_a_just_added_dataset_shows_its_card_at_once(at, monkeypatch):
    """✅ Add dataset closes the wizard on this run, so the card answers at once
    rather than after the delay — the only way it can show under a 30 s one."""
    pin_view(at, _VIEW_DATA)
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 30)
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.session_state["_wizard_finalizing"] = True
    pin_view(at, _VIEW_DATA)
    at.run()
    text = _markdown(at)
    assert "Loading Synthetic test trial" in text and "sps-reveal-page" in text


def _record_opened_cards(monkeypatch) -> list[str]:
    """The key of every card a run opens, in order."""
    opened: list[str] = []
    real_open = loading.Card.open

    def _open(self, **kwargs):
        opened.append(self.key)
        return real_open(self, **kwargs)

    monkeypatch.setattr(loading.Card, "open", _open)
    return opened


def test_the_restore_card_opens_only_while_there_is_something_to_restore(
    at, monkeypatch
):
    """The recovery cache is restored once a session, and `restore_local_state`
    returns at once after that — so a card around it on every later run was a
    timer thread and a task for nothing. Its slot is still held on every run
    (UX-167), so the view keeps its place."""
    opened = _record_opened_cards(monkeypatch)
    at.run()
    assert not at.exception, at.exception
    assert "restore" in opened
    view_index = _child_index(at.main, loading.VIEW_AREA_KEY)
    opened.clear()
    at.run()
    assert not at.exception, at.exception
    assert "restore" not in opened
    assert _child_index(at.main, loading.VIEW_AREA_KEY) == view_index


def _unmappable(raw_words, raw_fixations, **_kwargs):
    return raw_words, raw_fixations, ["A required column isn't mapped yet."]


def test_an_early_return_takes_the_card_and_the_skeleton_down(at, monkeypatch):
    """BUG-81, for the card that replaced the loading banners: a run that returns
    early (here, a mapping that can't be satisfied) takes a *showing* card and
    its skeleton down itself — `_KEEP_ON_STOP` switches off the run's own
    safety net, so only the early return can have cleared them."""
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _unmappable)
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text
    assert app.DATASET_TASK_KEY not in at.session_state


def test_the_missing_corpus_notice_stays_above_the_view(at, monkeypatch):
    """UX-7(b)'s panel is drawn on the way to the view. With the view inside the
    reserved area it has to go in there too, or it lands below the whole page."""

    def _notice():
        import streamlit as st

        st.markdown("missing-corpus-notice")

    def _view(*_args, **_kwargs):
        import streamlit as st

        st.markdown("scanpath-view-body")

    monkeypatch.setattr(app, "_render_dataset_unavailable", _notice)
    monkeypatch.setattr(app, "render_single_trial_tab", _view)
    at.run()
    assert not at.exception, at.exception
    order = [m.value for m in at.markdown]
    assert order.index("missing-corpus-notice") < order.index("scanpath-view-body")


def test_the_author_editor_stays_above_the_view(at, monkeypatch):
    """The ✏️ Author editor is the view's input: with the view inside the reserved
    area the editor goes in there too, or it lands below its own output."""
    real_editor = app._render_authoring_source

    def _editor():
        import streamlit as st

        st.markdown("author-editor")
        return real_editor()

    def _view(*_args, **_kwargs):
        import streamlit as st

        st.markdown("scanpath-view-body")

    monkeypatch.setattr(app, "_render_authoring_source", _editor)
    monkeypatch.setattr(app, "render_single_trial_tab", _view)
    at.session_state["data_source_choice"] = app.AUTHOR_CHOICE
    at.run()
    assert not at.exception, at.exception
    order = [m.value for m in at.markdown]
    assert order.index("author-editor") < order.index("scanpath-view-body")


def test_a_download_takes_the_dataset_card_down_first(at, monkeypatch):
    """UX-7(b)'s ⬇ Download now runs while the dataset card is still open. The
    card must come down first, or it hides the panel behind a step that isn't
    what is running.

    UX-168: downloading now opens its own progress card around the fetch, so
    ``covered()`` is True once the download starts — that card, not the old
    dataset skeleton, is what covers. ``page_up`` is the assertion that
    matters here: the *page* (the skeleton) is what must be gone."""
    seen = {}

    def _download(_root):
        state = loading._RUN.get()
        seen["page_up"] = state is not None and state.page is not None
        seen["covered"] = loading.covered()
        raise OSError("offline")  # the run carries on, no rerun

    monkeypatch.setattr(loading, "DELAY_S", 0)
    _loading_an_unavailable_corpus(monkeypatch, download=_download)
    at.run()
    at.button(key="t6_download_main").click().run()
    assert seen == {"page_up": False, "covered": True}


def test_the_editors_download_releases_the_page_first(at, monkeypatch, tmp_path):
    """Ruling T6-8: the editor's own ⬇ Download (`_dataset_access_status`)
    must release the page before downloading too, exactly like the main-area
    ⬇ Download now above — same fixture shape, driven on PoTeC's editor
    button instead of the main-area empty-state one."""
    seen = {}

    def _download(_root):
        state = loading._RUN.get()
        seen["page_up"] = state is not None and state.page is not None
        seen["covered"] = loading.covered()
        raise OSError("offline")  # the run carries on, no rerun

    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(datasets, "download_potec", _download)
    at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
    at.session_state["public_dataset_choice"] = "PoTeC — Potsdam Textbook Corpus"
    at.session_state["potec_dir"] = str(tmp_path)  # empty dir → not present yet
    at.run()
    assert not at.exception, at.exception
    at.button(key="potec_download").click().run()
    assert seen == {"page_up": False, "covered": True}


def test_an_unavailable_corpus_gets_no_counts_on_its_card(at, monkeypatch):
    """The rows read for a corpus that isn't here are the demo's stand-in, so
    the card moves on to Normalizing without claiming them as the corpus's."""
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    _loading_an_unavailable_corpus(monkeypatch)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.run()
    text = _markdown(at)
    assert "Normalizing" in text and "word rows and" not in text


def test_the_editors_card_sits_on_the_editor_screen(at, monkeypatch):
    """While ✏️ Edit dataset is open the overview is hidden, and a card drawn
    there would be invisible while still silencing every spinner — so the page
    lives in the slot under the editor's header."""
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.session_state[DATASET_EDITOR_OPEN_KEY] = True
    pin_view(at, _VIEW_DATA)
    at.run()
    editor = at.main.get_by_key(DATA_EDITOR_KEY)
    overview = at.main.get_by_key(DATA_OVERVIEW_OFFSCREEN_KEY)
    assert "sps-card-head" in _markdown_in(editor)
    assert "sps-card-head" not in _markdown_in(overview)


def test_only_the_data_view_hides_what_the_view_area_holds(at, monkeypatch):
    """T6-1: on the Data view the reserved area holds only what the previous view
    left there (the Data page draws outside it), so its first slot carries a
    marker the CSS hides the rest of the area by — from the top of the run, before
    any card exists, and never on a view the area actually holds."""
    at.run()  # Scanpath, so the Data run below starts over its leftovers
    monkeypatch.setattr(app, "resolve_data_source", _stop)  # before any card
    pin_view(at, _VIEW_DATA)
    at.run()
    assert "sps-view-hidden" in _markdown(at)
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert "sps-view-hidden" not in _markdown(at)


def test_the_data_views_marker_outlives_its_card(at, monkeypatch):
    """The Data page keeps drawing after its card is released, so the marker
    can't be the card's: here the card shows at once and is gone by the end of
    the run — with the run's own clear off, a release took it — and the marker
    is still there."""
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    pin_view(at, _VIEW_DATA)
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-view-hidden" in text and "sps-card-head" not in text


def test_a_drawn_figure_records_its_embedded_size(at):
    at.run()
    width, height = at.session_state[loading.PLOT_SIZES_KEY]["single"]
    assert width > 0 and height > 12


def test_a_slow_figure_holds_its_area_with_a_size_box(at, monkeypatch):
    at.run()
    expected = at.session_state[loading.PLOT_SIZES_KEY]["single"]
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(tabs, "_cached_scanpath_figure", _stop)
    at.run()
    text = _markdown(at)
    assert f"height:{expected[1]}px" in text
    assert "Drawing the scanpath" in text


# UX-167 — Streamlit matches a rerun's elements to the last run's by position, so
# one element more or fewer above `sps_view` shifts it: the browser lays the new
# view area on the *next* block's slot and inherits its children, dropping the old
# view (rail, pickers, plot) for the whole run. These three pin that every
# once-in-a-while element above the view (the easter egg, the unavailable-link
# warning, the view's own conditional notices) draws inside a container held on
# every run.


def _child_index(block, key: str) -> int:
    """The index, in ``block``, of the child that is — or holds — the keyed block."""
    for index, child in block.children.items():
        if _holds_key(child, key):
            return index
    raise AssertionError(f"no block keyed {key!r}")


def _holds_key(node, key: str) -> bool:
    proto_id = getattr(getattr(node, "proto", None), "id", "") or ""
    if proto_id.endswith(f"-{key}"):
        return True
    return any(
        _holds_key(child, key) for child in getattr(node, "children", {}).values()
    )


def test_the_view_keeps_its_place_when_the_tour_closes(at):
    """render_easter_egg() draws a bare iframe except while a tour is active, so
    the first run after the tour closes inserts one element above the view —
    today that shifts `sps_view` from main child 8 to 9."""
    at.session_state["tour_mode"] = "spotlight"
    at.run()
    assert not at.exception, at.exception
    index_before = _child_index(at.main, loading.VIEW_AREA_KEY)
    del at.session_state["tour_mode"]
    at.run()
    assert not at.exception, at.exception
    index_after = _child_index(at.main, loading.VIEW_AREA_KEY)
    assert index_after == index_before


def test_the_view_keeps_its_place_after_a_link_notice(at, monkeypatch):
    """A link naming a corpus that isn't here warns on its first run only, so
    the next run must not shift the view. (The recovery toasts need no such
    test: ``st.toast`` draws in Streamlit's event container, not the page.)"""
    monkeypatch.setattr(app, "_apply_url_preset", lambda: app.CORPUS_SOURCE_TOKEN)
    monkeypatch.setattr(app, "corpus_choice_for_slug", lambda _slug: None)
    at.query_params[app.PARAM_CORPUS] = "not-a-real-corpus"
    at.run()
    assert not at.exception, at.exception
    index_before = _child_index(at.main, loading.VIEW_AREA_KEY)
    monkeypatch.setattr(app, "_apply_url_preset", lambda: None)
    at.run()
    assert not at.exception, at.exception
    index_after = _child_index(at.main, loading.VIEW_AREA_KEY)
    assert index_after == index_before


def test_the_views_blocks_keep_their_place_when_a_notice_comes_and_goes(
    at, monkeypatch
):
    """A conditional notice written through `view_notices` sits directly before
    the view's own blocks inside `sps_view`, so today it shifts them too — the
    plot/rail columns block would land on the wrong slot and inherit its
    children."""
    calls = {"n": 0}

    def _unavailable_once():
        import streamlit as st

        calls["n"] += 1
        if calls["n"] == 1:
            st.warning("gone after this run")

    monkeypatch.setattr(app, "_render_dataset_unavailable", _unavailable_once)
    at.run()
    assert not at.exception, at.exception
    view_area = at.main.children[_child_index(at.main, loading.VIEW_AREA_KEY)]
    index_before = _child_index(view_area, "scanpath_rail")
    at.run()
    assert not at.exception, at.exception
    view_area = at.main.children[_child_index(at.main, loading.VIEW_AREA_KEY)]
    index_after = _child_index(view_area, "scanpath_rail")
    assert index_after == index_before


# UX-168 — Cancel a dataset load or Compare's second dataset.


def test_cancel_goes_back_to_the_last_dataset_and_try_again_returns(at, monkeypatch):
    # T8-5: Cancel's "back" must be one of this run's own `_data_source_entries`
    # (`resolve_data_source`'s published list) — and the synthetic trial is only
    # ever in that list while debug mode is on or it is the active choice, so
    # once the run below switches away from it, it needs debug mode to still be
    # a reachable "Back to …" target instead of silently offering none.
    monkeypatch.setattr(app, "debug_enabled", lambda: True)
    at.run()  # synthetic finishes: it is the dataset Cancel goes back to
    monkeypatch.setattr(loading, "DELAY_S", 0)
    # Ruling T3-1: freezing with `st.stop()` leaves a stopped run's cards to be
    # cleared unless `_KEEP_ON_STOP` says otherwise — without it, `sps_cancel_page`
    # would be gone before the test can click it. `monkeypatch.undo()` below
    # restores both this and `DELAY_S` together, as intended.
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    demo = app.DEMO_CHOICE
    at.session_state["_pending_source_choice"] = demo
    at.run()
    cancel = at.button(key="sps_cancel_page")
    assert cancel.label.startswith("Back to")
    monkeypatch.undo()
    cancel.click().run()
    assert at.session_state["data_source_choice"] == SYNTHETIC
    at.button(key="sps_try_again").click().run()
    assert at.session_state["data_source_choice"] == demo


def test_picking_another_dataset_mid_load_cancels_the_first(at):
    at.run()
    stale = ("dataset", "an-abandoned-run", "Other")
    task = progress.begin(stale, title="Loading Other")
    at.session_state[app.DATASET_TASK_KEY] = stale
    at.run()
    assert task.cancelled


@pytest.mark.parametrize("choice", [app.UPLOAD_CHOICE, app.AUTHOR_CHOICE])
def test_switching_to_upload_or_author_cancels_a_stale_load(at, choice):
    """The early return for the Upload wizard / Author source has no load of
    its own, so a task another run left running under ``DATASET_TASK_KEY`` would
    otherwise never be cancelled or cleared — the key would just sit there,
    stale, for as long as the session lasted."""
    stale = ("dataset", "an-abandoned-run", "Other")
    task = progress.begin(stale, title="Loading Other")
    at.session_state[app.DATASET_TASK_KEY] = stale
    at.session_state["data_source_choice"] = choice
    at.run()
    assert not at.exception, at.exception
    assert task.cancelled
    assert app.DATASET_TASK_KEY not in at.session_state


def _compare_cancel_script():
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state.setdefault("cmp_dataset", "Bundled Demo")
    st.button("x", key="c", on_click=tabs._cancel_compare_source, args=(("cmp", "k"),))


def test_the_compare_cancel_goes_back_to_this_dataset():
    at = AppTest.from_function(_compare_cancel_script).run()
    at.button(key="c").click().run()
    assert at.session_state[COMPARE_SOURCE_STATE_KEY] == tabs.THIS_DATASET


def test_compares_cancel_names_a_and_returns_to_this_dataset(at, monkeypatch):
    """T8-4: the full-app wiring — `loading_slot=plot_loading_slot` reaching
    `_resolve_compare_source`, the card it opens, and the callback — pinned
    together rather than only through the isolated script above."""
    at.session_state["single_compare_toggle"] = True
    at.session_state[COMPARE_SOURCE_STATE_KEY] = app.DEMO_CHOICE
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(tabs, "load_secondary_dataset", _stop)
    at.run()
    cancel = at.button(key="sps_cancel_compare_dataset")
    assert cancel.label == f"Compare within {SYNTHETIC}"
    monkeypatch.undo()
    cancel.click().run()
    assert at.session_state[COMPARE_SOURCE_STATE_KEY] == tabs.THIS_DATASET


# UX-168 fix round 1 (task-8-findings-r1.md) — T8-2 … T8-5.


def test_a_slow_rerun_of_the_dataset_on_screen_offers_no_cancel(at, monkeypatch):
    """T8-2: Cancel is for a load the user started — cold, or by switching away
    from what was on screen — never for a slow rerun of the dataset already on
    screen (a filter change, a re-normalization, a slow ✏️ Edit dataset step):
    there is nothing to switch away from, and clicking it must not abandon the
    dataset the user is looking at."""
    at.run()  # synthetic finishes: LAST_LOADED_SOURCE_KEY == SYNTHETIC == token
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.run()  # a rerun of the SAME dataset, now slow
    with pytest.raises(KeyError):
        at.button(key="sps_cancel_page")


def test_the_demos_own_first_load_of_a_session_gets_no_cancel(monkeypatch):
    """T8-4: `_dataset_cancel`'s ``None`` branch — with nothing finished loading
    yet this session, the demo is the fallback ``back``, but never Cancel back
    to the very dataset it would be cancelling."""
    test = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    test.session_state["data_source_choice"] = app.DEMO_CHOICE
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    test.run()
    with pytest.raises(KeyError):
        test.button(key="sps_cancel_page")


def test_a_view_switch_onto_an_in_flight_load_opens_the_loads_own_card(at, monkeypatch):
    """T8-3: a view switch that lands on an in-flight load must not hide it
    behind the task-less "Opening <view>" skeleton — the load's own steps and
    Cancel have to stay visible, and its checkpoints must keep reporting to its
    own task rather than a fresh one a later dataset pick can't find."""
    monkeypatch.setattr(app, "debug_enabled", lambda: True)  # keeps SYNTHETIC
    # in `_data_source_entries` below (T8-5), so Cancel has somewhere to go.
    at.run()  # synthetic finishes: LAST_LOADED_SOURCE_KEY == SYNTHETIC
    monkeypatch.setattr(loading, "DELAY_S", 30)  # only `reveal_now` can show it
    monkeypatch.setattr(loading, "REFRESH_S", 30)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    demo = app.DEMO_CHOICE
    at.session_state["_pending_source_choice"] = demo
    at.run()  # Bundled Demo's load starts and is now in flight
    assert at.session_state[app.DATASET_TASK_KEY][2] == demo
    pin_view(at, _VIEW_CORPUS)
    at.run()  # a view switch landing on that same in-flight load
    text = _markdown(at)
    assert f"Loading {app._dataset_display_name(demo)}" in text
    assert "sps-reveal-page" in text
    assert "sps-step-done" in text  # Reading files ✓ — the in-flight task's own
    cancel = at.button(key="sps_cancel_page")
    assert cancel.label.startswith("Back to")


def test_a_hidden_last_loaded_dataset_is_never_offered_as_a_cancel_target(monkeypatch):
    """T8-5: `resolve_data_source` can heal a stale/hidden selection to
    ``entries[0]`` — a Cancel that still read "Back to <hidden dataset>" would
    silently reopen something else instead of what it says, so a dataset no
    longer in this run's `_data_source_entries` must not be offered at all."""
    test = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    test.session_state["data_source_choice"] = app.DEMO_CHOICE
    monkeypatch.setattr(app, "debug_enabled", lambda: True)  # keeps SYNTHETIC
    # selectable below despite not being the active dataset.
    test.run()  # Bundled Demo finishes: LAST_LOADED_SOURCE_KEY == DEMO_CHOICE
    test.session_state[app.HIDDEN_DATASETS_KEY] = [app.DEMO_CHOICE]
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    test.session_state["_pending_source_choice"] = SYNTHETIC
    test.run()  # loading Synthetic, with the demo hidden since it last finished
    with pytest.raises(KeyError):
        test.button(key="sps_cancel_page")


# UX-169 — the animation card's Cancel switches Animate off.


def _animation_cancel_script():
    import streamlit as st

    from scanpath_studio import tabs

    st.session_state.setdefault("single_animate", True)
    st.button("x", key="c", on_click=tabs._cancel_animation, args=(("anim", "k"),))


def test_the_animation_cancel_switches_animate_off():
    at = AppTest.from_function(_animation_cancel_script).run()
    at.button(key="c").click().run()
    assert at.session_state["single_animate"] is False


#: The session's remembered replay task (UX-169) — an ``_sps_*`` internal.
ANIM_TASK = "_sps_anim_task"


def test_stepping_to_another_trial_cancels_the_replay_built_for_the_last(at):
    """A replay's task is keyed by what it is a replay of. A run that opens the
    card for another trial than the one remembered cancels that build — it is
    for a trial no longer on screen — instead of joining it, which interleaved
    two frame loops' counts on one card while the obsolete build ran on."""
    stale = ("anim", "a-superseded-run", "another reader", "another trial")
    task = progress.begin(stale, title="Building the animation")
    at.session_state[ANIM_TASK] = stale
    at.session_state["single_animate"] = True
    at.run()
    assert not at.exception, at.exception
    assert task.cancelled
    assert ANIM_TASK not in at.session_state  # this run's build completed


def test_the_same_trial_joins_the_replay_being_built(at, monkeypatch):
    """A rerun that opens the card for the replay still being built — nothing
    changed that the frames are built from — joins that build's task rather
    than cancelling it."""
    at.session_state["single_animate"] = True
    monkeypatch.setattr(tabs, "_build_and_render_animation", _stop)  # mid-build
    at.run()
    key = tuple(at.session_state[ANIM_TASK])
    shown = at.session_state["_share_selection"]
    assert key[0] == "anim"
    assert key[2:5] == (
        str(shown["participant_id"]),
        str(shown["trial_id"]),
        shown.get("screen_id"),  # None: a single-screen trial
    )
    task = progress.begin(key, title="Building the animation")  # still building
    begun = _hold_every_task(monkeypatch)
    at.run()
    assert not task.cancelled
    assert begun[key] is task


def _a_replay_left_building(at, monkeypatch) -> tuple[tuple, progress.Task]:
    """Animate on, the build frozen mid-way — its task held, so it stays live."""
    at.session_state["single_animate"] = True
    monkeypatch.setattr(tabs, "_build_and_render_animation", _stop)  # mid-build
    at.run()
    assert not at.exception, at.exception
    building = tuple(at.session_state[ANIM_TASK])
    return building, progress.begin(building, title="Building the animation")


def test_a_setting_that_changes_the_frames_cancels_the_replay_being_built(
    at, monkeypatch
):
    """A replay is a replay of its frames: a rail setting that changes them —
    the saccades switched off here — makes the build under way an obsolete one.
    Joined, two frame loops counted into one card, and the old build, which
    nothing could cancel, ran to its end beside the new one at half the speed."""
    building, task = _a_replay_left_building(at, monkeypatch)
    at.session_state["global_show_saccades"] = False
    at.run()
    assert not at.exception, at.exception
    assert task.cancelled
    assert tuple(at.session_state[ANIM_TASK]) != building


def test_a_speed_change_joins_the_replay_being_built(at, monkeypatch):
    """The speed reaches only the player's clock (PERF-15) — the frames are
    built at ×1 whatever it is — so the build under way is the one this run
    wants: the same key, and nothing cancelled."""
    building, task = _a_replay_left_building(at, monkeypatch)
    at.session_state["single_playback_speed"] = 2.0
    at.run()
    assert not at.exception, at.exception
    assert tuple(at.session_state[ANIM_TASK]) == building
    assert not task.cancelled


TWO_SCREENS = "Two screens"


def _store_two_screen_dataset(at) -> None:
    """A stored multipart dataset: one trial read over two screens."""
    words, fixations = make_multipart_synthetic_data()
    at.session_state["_datasets"] = {
        TWO_SCREENS: {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = TWO_SCREENS


def test_stepping_to_another_screen_cancels_the_replay_built_for_the_last(
    monkeypatch,
):
    """A multipart replay covers one screen, so ▶ to the next screen of the same
    trial mid-build must cancel the build for the screen left behind — not join
    it, which interleaved two frame loops' counts on one card."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    _store_two_screen_dataset(at)
    at.session_state["single_animate"] = True
    monkeypatch.setattr(tabs, "_build_and_render_animation", _stop)  # mid-build
    at.run()
    assert not at.exception, at.exception
    first_screen = tuple(at.session_state[ANIM_TASK])
    task = progress.begin(first_screen, title="Building the animation")  # building
    at.button(key="single_screen_next").click().run()
    assert not at.exception, at.exception
    assert at.session_state["single_screen_id"] == "question"
    assert task.cancelled


def test_a_co_replays_key_names_bs_screen_too():
    """In a co-replay B steps through its own screens (UX-112), so B's screen is
    part of what the replay is of, beside B's reader and trial."""
    a = ("synthetic", "multipart_demo", "intro")
    on_bs_intro = tabs._animation_task_key(*a, compare=a)
    on_bs_question = tabs._animation_task_key(
        *a, compare=("synthetic", "multipart_demo", "question")
    )
    assert on_bs_intro != on_bs_question


# UX-169 — a placeholder inside the plot's frame.


def test_the_plot_frame_carries_a_placeholder_removed_on_first_draw():
    html, _ = tabs._true_scale_html(
        '<div id="truescale-k"></div>',
        key="k",
        width=100,
        height=50,
        max_height=None,
        zoomable=True,
    )
    assert 'id="skel-k"' in html
    assert "dropSkeleton" in html
    # It must run for the small multiples too, which return before the zoom code.
    assert html.index("dropSkeleton") < html.index("if (!ZOOMABLE)")
    # Styled before it is parsed: the figure's own markup (megabytes for a
    # replay) comes between them, so a rule after it would leave the
    # placeholder unstyled — invisible — for exactly the wait it is for.
    assert html.index("#skel-k {") < html.index('id="skel-k"')
    assert html.index('id="skel-k"') < html.index('id="truescale-k"')


def test_a_run_that_builds_no_replay_stops_the_one_left_building(at):
    """Animate switched off with its own switch mid-build opens no animation
    card, so nothing else would cancel the build an earlier run left running
    — it would run on beside this run's static figure."""
    stale = ("anim", "an-earlier-run", "p", "t")
    task = progress.begin(stale, title="Building the animation")  # held: stays live
    at.session_state[tabs.ANIM_TASK_KEY] = stale
    at.run()  # Animate is off by default
    assert not at.exception, at.exception
    assert task.cancelled
    assert tabs.ANIM_TASK_KEY not in at.session_state


def test_animate_on_a_trial_with_no_fixations_stops_the_replay_left_building():
    """The other run that builds no replay: Animate is on, but this trial has no
    fixations to animate — so no animation card opens to cancel the build an
    earlier run left running for another trial."""
    words, _ = _normalized_synthetic()
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {
        "Words only": {
            "words": words,
            "fixations": data.empty_fixations_frame(),
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = "Words only"
    stale = ("anim", "an-earlier-run", "p", "t", None)
    task = progress.begin(stale, title="Building the animation")  # held: stays live
    at.session_state[tabs.ANIM_TASK_KEY] = stale
    at.session_state["single_animate"] = True
    at.run()
    assert not at.exception, at.exception
    assert any("nothing to animate" in info.value for info in at.info)
    assert task.cancelled
    assert tabs.ANIM_TASK_KEY not in at.session_state
