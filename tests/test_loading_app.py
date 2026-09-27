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

import pytest

from scanpath_studio import app, loading, progress, tabs
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_EDITOR_KEY,
    DATA_OVERVIEW_OFFSCREEN_KEY,
    DATASET_EDITOR_OPEN_KEY,
)
from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY
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
    pin_view(at, _VIEW_CORPUS)
    at.run()
    kind, session, token = at.session_state[app.DATASET_TASK_KEY]
    assert (kind, token) == ("dataset", SYNTHETIC)
    view_task = progress._REGISTRY[("card", session, loading.PAGE_CARD_KEY)]
    assert view_task.snapshot().title == "Opening Corpus Analysis"


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
    card must come down first, or it hides the panel and its spinner behind a
    step that isn't what is running."""
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
    assert seen == {"page_up": False, "covered": False}


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
