"""Streamlit AppTest integration: spin up the app and assert key surfaces render.

Companion file: ``tests/test_apptest_flows.py`` (ENG-4) drives multi-step
*flows* through the same harness — overriding a column mapping and checking the
re-derived data, narrowing the trial pool with the condition/annotation filters
(incl. the UX-7 empty state), and building the bulk-export zip from the Export
subtab. Add render-level checks here; add "change a control, assert the next
render" checks there.
"""

from __future__ import annotations

from unittest import mock

import pytest

from scanpath_studio import controls
from scanpath_studio import menu as menu_mod
from scanpath_studio.wizard import _SCREEN_KNOW, _SETUP_MODE_KEYS
from tests.conftest import (
    APP_SCRIPT,
    SUBTAB_COMPARISONS,
    SUBTAB_EXPORT,
    SUBTAB_KEY,
    SUBTAB_LINE_ASSIGNMENT,
    _write_benchmark_corpus,
    _write_benchmark_manifest,
    answer_setup_step,
    open_data_view,
    pin_data_view,
    pin_view,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


SYNTHETIC_SOURCE = "Synthetic test trial"


def _make_apptest(*, synthetic: bool = False) -> AppTest:
    """Build an AppTest for the app.

    Booting the bundled demo renders every tab over a large dataset (~5s).
    ``synthetic=True`` pre-seeds the "Synthetic test trial" source *before* the
    first ``run()``, so the app boots straight into the tiny synthetic trial
    (6 words / 9 fixations) — the same surfaces render ~10x faster and there's
    no throwaway demo render. Use it for tests that don't assert on the demo's
    specific richness; a few launch/multi-trial tests stay on the demo as the
    real-default-experience guardrails.
    """
    at = AppTest.from_file(APP_SCRIPT)
    if synthetic:
        at.session_state["data_source_choice"] = SYNTHETIC_SOURCE
    return at


def _replay_tour(at: AppTest) -> None:
    """Replay the tour through the compatibility action used by tests.

    The visible entry now lives in Tutorials; this bypasses the dialog so tests
    focused on the tour itself do not also test the tutorial library.
    """
    from unittest.mock import patch

    import streamlit as st

    from scanpath_studio import menu

    # `_arm_help_action` writes through `st.session_state`, which outside a
    # script run is not this AppTest's state — point it at the right one rather
    # than restating which keys arming a tour sets.
    with patch.object(st, "session_state", at.session_state):
        menu._arm_help_action("help_tour")
    at.run(timeout=30)


def _enter_add_data(at: AppTest) -> None:
    """Click the Add-dataset button, wherever the app currently keeps it.

    UX-64 moved it off the Scanpath control row onto the Data page, which is
    now the only way in — so reaching it means switching views first.
    """
    open_data_view(at)
    add = [b for b in at.button if b.key == "add_data_btn"]
    assert add, "Add data button not rendered on the Data page"
    add[0].click()


@pytest.mark.timeout(60)
class TestAppLaunches:
    def test_app_launches_with_bundled_demo(self):
        # The bundled demo must boot the full five-tab UI cleanly: no Python
        # exceptions and no st.error surfaced on the default render.
        at = _make_apptest()
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_wordmark_ships_and_does_not_double_up_in_the_page(self):
        """UX-62: the name is the header wordmark, and *only* that.

        Two things worth failing on. The image must **exist inside the
        package** — it is declared in `pyproject.toml`'s `package-data`, and a
        logo that slipped back outside it would leave every pip install with an
        empty header while a source checkout looked fine. And the page body must
        not print the title or its one-line description any more, or the app
        says its own name twice, a row apart.

        `st.logo` writes into Streamlit's header strip, which `AppTest` does not
        expose (it has no `.logo`), so the element itself is browser-verified.
        """
        from scanpath_studio import app as app_mod

        assert app_mod.LOGO_PATH.is_file(), (
            f"the wordmark must live inside the package (looked in "
            f"{app_mod.LOGO_PATH}); see pyproject.toml package-data"
        )

        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert not [t for t in at.title if "Scanpath Studio" in t.value], (
            "the title is the header wordmark now; printing it again duplicates it"
        )
        assert not [
            c for c in at.caption if "Interactive visualization of eye" in c.value
        ], "the one-line description lives in About, not in the page chrome"

    def test_nothing_renders_into_the_sidebar(self):
        """The sidebar is gone — every group it held is a top-menu popover now.

        Streamlit only draws sidebar chrome when something is written there, so
        one stray ``st.sidebar.*`` call anywhere in the render path brings the
        whole panel back, half-populated. Assert the container is empty rather
        than trusting a grep: the call could be behind any branch.
        """
        at = _make_apptest()
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        stray = [
            name
            for name in ("button", "selectbox", "toggle", "expander", "markdown")
            if len(getattr(at.sidebar, name))
        ]
        assert not stray, f"these still render into the sidebar: {stray}"

    def test_a_panel_cannot_default_back_into_the_sidebar(self):
        """ENG-44: ``render_trial_filters`` used to fall back to ``st.sidebar``
        when given no host — a default that would have drawn the whole filter
        panel into chrome the app has not rendered since UX-38. The host is now
        required, so forgetting it is a TypeError rather than a panel nobody can
        see."""
        import inspect

        from scanpath_studio import controls

        host = inspect.signature(controls.render_trial_filters).parameters["host"]
        assert host.default is inspect.Parameter.empty
        assert host.kind is inspect.Parameter.KEYWORD_ONLY

    def test_the_session_dialog_holds_all_four_blocks(self):
        """UX-100: 💾 Session is a nav entry that opens a modal, like ❓ Help's.

        The four blocks live in the dialog body, so they render when — and only
        when — it has been armed. Armed the way the nav arms it
        (`menu._arm_help_action` → `app._arm_session`), so this covers the wire
        between the entry and the modal rather than just the modal.
        """
        from scanpath_studio import app

        at = _make_apptest()
        at.session_state[app._SESSION_DIALOG_KEY] = True
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        body = " ".join(m.value for m in at.markdown)
        for expected in (
            "#### 🗄️ Automatic recovery",
            "#### ⬇️ JSON backup",
            "#### ♻️ Reset",
            "#### 🐛 Debug tools",
        ):
            assert expected in body, f"{expected} missing from the Session dialog"
        # Neither group is a popover any more — not the merged one UX-38 made,
        # and not the two it merged.
        labels = {p.proto.popover.label for p in at.get("popover")}
        for gone in ("💾 Session", "❓ Help", "💾 Save & restore", "🗄️ Recovery cache"):
            assert gone not in labels, labels

    def test_the_session_blocks_stay_out_of_the_page_until_asked_for(self):
        """The counterpart: unarmed, none of it is on the page.

        Session used to be a whole nav page (#UX-63) and then a popover, both of
        which rendered their widgets on every run. The dialog does not, which is
        why the two widgets in there that hold real state — the persistence
        pause toggle and the 🐛 Debug gate — each re-seed from a durable value
        rather than *being* it (`debug_log._DEBUG_TOGGLE_KEY`).
        """
        at = _make_apptest()
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        body = " ".join(m.value for m in at.markdown)
        assert "#### 🗄️ Automatic recovery" not in body
        assert "#### ⬇️ JSON backup" not in body

    def test_debug_mode_survives_the_dialog_closing(self):
        """UX-100: the 🐛 Debug gate is not the toggle's own widget key.

        A dialog body is a fragment: it runs only while the modal is open, and
        Streamlit drops a widget's key at the end of any run in which it did not
        render. With `key=DEBUG_STATE_KEY` — which is how it was written while
        the panel rendered every run — dismissing the modal turned debug mode
        back off.
        """
        from scanpath_studio import app
        from scanpath_studio.debug_log import DEBUG_STATE_KEY

        at = _make_apptest()
        at.session_state[DEBUG_STATE_KEY] = True
        at.session_state[app._SESSION_DIALOG_KEY] = True
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # A run with the dialog closed must leave the durable gate alone.
        at.run(timeout=30)
        assert at.session_state[DEBUG_STATE_KEY] is True

    def test_configure_and_preprocessing_left_the_menu_bar(self):
        """DATA-26: the two setup groups are the Data page's, not the bar's.

        Leaving a stale trigger behind would give one job two doors again, which
        is the whole complaint the page exists to answer.
        """
        at = _make_apptest()
        at.run(timeout=30)
        labels = {p.proto.popover.label for p in at.get("popover")}
        assert "⚙️ Configure" not in labels
        assert "🧹 Preprocessing" not in labels

    def test_synthetic_data_source_renders(self):
        # The "Synthetic test trial" source should load + render without error.
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_multiple_comparison_tab_renders(self):
        # Exercise the Comparisons subtab (ENG-8). The bundled demo has several
        # readers of each paragraph, so grouping the same text by participant_id
        # yields real comparison scanpaths to score against the selected trial.
        # Change the grid columns; confirm no exceptions / errors.
        at = _make_apptest()
        at.session_state["multi_n_cols"] = 2
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_stimulus_image_with_manual_alignment_renders(self):
        # VIZ-4: the bundled demo ships a per-trial stimulus image. Turning it on
        # and applying a manual origin nudge + scale (the "Align to text"
        # controls) must render without exceptions / errors.
        at = _make_apptest()
        at.session_state["global_show_stimulus_image"] = True
        at.session_state["global_stimulus_image_offset_x"] = 30.0
        at.session_state["global_stimulus_image_offset_y"] = -20.0
        at.session_state["global_stimulus_image_scale"] = 1.25
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_animation_export_controls_render(self):
        # Animation is now a checkbox in the Scanpath Visualization tab; with it
        # on, the Export toggle offers the HTML/GIF/MP4 selector. Selecting a
        # rasterized format must render its options + Render button without
        # crashing (and without triggering the expensive Kaleido render).
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.session_state["single_animate"] = True
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT  # PERF-3: open it to load it
        at.run(timeout=30)
        fmt_radios = [r for r in at.radio if list(r.options) == ["HTML", "GIF", "MP4"]]
        assert fmt_radios, "animation export-format radio not found"
        at.session_state["anim_export_format"] = "MP4"
        # Re-pin the subtab: the tab bar is itself a widget, so any *other*
        # programmatic change lets it fall back to its default and the panel
        # under test silently doesn't render — the assertions below would then
        # pass without ever reaching the rasterized branch (ENG-37).
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        # The rasterized branch really rendered: its options and Render button.
        assert [s for s in at.select_slider if s.key == "anim_export_scale"]
        assert [b for b in at.button if b.key == "anim_export_generate"]

    def test_single_trial_picker_degrades_without_slider(self):
        # The mode pills are gone — there is just one trial picker now. With a
        # single trial (synthetic source) it must NOT instantiate a one-option
        # st.select_slider (that crashes the browser with `RangeError`); the
        # selectbox alone resolves it.
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        slider_keys = [s.key for s in at.select_slider]
        assert "single_trial_pos" not in slider_keys, (
            "single-option select_slider rendered — this crashes the browser"
        )
        # The lone synthetic trial still resolves (its id surfaces in a picker /
        # the chips).
        markdown = " ".join(m.value for m in at.markdown)
        options = " ".join(
            str(list(w.options))
            for w in [*at.selectbox, *at.select_slider]
            if getattr(w, "options", None) is not None
        )
        assert "synthetic_2line_demo" in (markdown + " " + options)

    def test_multi_trial_picker_has_slider_and_arrows(self):
        # With several trials (bundled demo) the picker shows the scrubbing slider
        # plus ◀ ▶ step buttons.
        at = _make_apptest()
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "single_trial_pos" in [s.key for s in at.select_slider]
        btn_keys = {b.key for b in at.button if b.key}
        assert {"single_prev_trial", "single_next_trial"} <= btn_keys, (
            "trial ◀ ▶ step buttons missing"
        )

    def test_new_viz_toggles_build_without_error(self):
        # Flip the new plot options (color-by-line — now the "line" option in the
        # color-by selector — the PRE-2 out-of-bounds highlight, gray background)
        # and confirm those code paths build without error. These pre-set values
        # mimic a Save & restore: the widgets must honour them (no inline
        # value=/index= override — see _VIZ_WIDGET_DEFAULTS) rather than reset.
        at = _make_apptest(synthetic=True)
        at.session_state["global_color_by"] = "line"
        at.session_state["global_fixclass_oob_mode"] = "Highlight"
        at.session_state["global_critical_span_style"] = "Mark border"
        at.session_state["global_bg_choice"] = "Gray"
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        radios = {r.key: r.value for r in at.radio if r.key}
        assert radios.get("global_fixclass_oob_mode") == "Highlight", (
            "restored fixation-classification value was overridden by an inline default"
        )

    def test_drift_correction_in_place_builds(self):
        # PRE-3: picking a drift-correction algorithm snaps fixations to their
        # assigned line on the main plot. Pre-seed the picker (mimics a restore)
        # and confirm the corrected figure builds and the setting is collected.
        at = _make_apptest(synthetic=True)
        at.session_state["global_align_algorithm"] = "Attach"
        at.session_state["global_align_connectors"] = True
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert at.session_state["global_align_algorithm"] == "Attach"

    def test_line_assignment_comparison_grid_builds(self):
        # PRE-3: the "📐 Line assignment" subtab builds its 11-panel comparison
        # grid (original + 10 algorithms) once the toggle is on, without error.
        at = _make_apptest(synthetic=True)
        at.session_state["align_grid_show"] = True
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_single_fixation_opacity_builds_without_error(self):
        # VIZ-6: the fixation opacity slider replaced the "Hollow circles"
        # checkbox. A restored opacity < 1.0 must survive and the figure build.
        at = _make_apptest(synthetic=True)
        at.session_state["global_fixation_opacity"] = 0.5
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert at.session_state["global_fixation_opacity"] == 0.5

    def test_single_fixation_index_window(self):
        # VIZ-7: narrow the main plot's fixation-index window and confirm the
        # slice path rebuilds the figure without exceptions (bundled demo trials
        # have enough fixations for the range slider to render).
        at = _make_apptest()
        at.session_state["single_fix_range"] = (2, 5)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        lo, hi = at.session_state["single_fix_range"]
        assert 1 <= lo <= hi

    def test_single_fix_range_clamped_when_max_shrinks(self):
        # A persisted window far past the trial's fixation count must clamp on
        # boot rather than crash the range slider.
        at = _make_apptest()
        at.session_state["single_fix_range"] = (900, 1000)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_compare_styles_collected_from_popover_keys(self):
        # Per-scanpath comparison styling now lives inside the Fixation/Saccade
        # popovers. With Compare on, controls._collect_compare_styles reads the
        # cmp{idx}_* widget keys and threads them into the comparison figure (it
        # runs whenever single_compare_toggle is truthy, even single-trial). The
        # seeded values must survive (no inline default reset) and build cleanly.
        at = _make_apptest(synthetic=True)
        at.session_state["single_compare_toggle"] = True
        at.session_state["cmp0_fix_color"] = "#123456"
        at.session_state["cmp0_hollow"] = True
        at.session_state["cmp1_saccade_color"] = "#abcdef"
        at.session_state["cmp1_saccade_style"] = "Dashed"
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        # The per-scanpath keys render in the layer popovers and keep their value.
        assert at.session_state["cmp0_fix_color"] == "#123456"
        assert at.session_state["cmp1_saccade_style"] == "Dashed"

    def test_animate_checkbox_renders_animation(self):
        # The Scanpath Visualization tab's Animate checkbox folds the former
        # animation tab in: the playback-speed slider must appear without error.
        at = _make_apptest(synthetic=True)
        at.session_state["single_animate"] = True
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert "single_playback_speed" in [s.key for s in at.select_slider]

    def test_bulk_export_whole_dataset_option(self):
        # The bundle scope includes the current trial, the whole dataset, and
        # the active filtered subset.
        at = _make_apptest()  # bundled 3-pid demo
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT  # PERF-3: open it to load it
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        scope_radios = [r for r in at.radio if r.key == "bulk_export_scope"]
        assert scope_radios, "bulk-export scope radio missing"
        assert scope_radios[0].options[:3] == [
            "This trial",
            "All",
            "All filtered trials",
        ], f"unexpected scope options: {scope_radios[0].options}"

        # Narrow to a single participant, pick "All" (whole dataset), build clean.
        sel = [m for m in at.multiselect if m.key == "filter_participants"]
        assert sel, "participant filter missing"
        sel[0].set_value([sel[0].options[0]])
        at.session_state["bulk_export_scope"] = "All"
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_narrow_by_text_participant_multiselects_render(self):
        # The former Browse-by Text/Participant modes are now inline "Narrow by"
        # multiselects (filter_text_id / filter_participants) that narrow the pool.
        at = _make_apptest()  # bundled 3-pid demo
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        ms_keys = {m.key for m in at.multiselect if m.key}
        assert "filter_participants" in ms_keys, (
            "Narrow-by participant multiselect missing"
        )
        assert "filter_text_id" in ms_keys, "Narrow-by text multiselect missing"

        def _trial_option_count(app):
            box = [s for s in app.selectbox if s.key == "single_trial_id"]
            return len(box[0].options) if box else 0

        total = _trial_option_count(at)
        assert total > 1, "expected several trials in the demo"

        # Narrowing by participant shrinks the trial pool feeding the picker.
        part = next(m for m in at.multiselect if m.key == "filter_participants")
        part.set_value([part.options[0]])
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert _trial_option_count(at) < total, (
            "participant narrowing didn't shrink pool"
        )

    def test_narrow_by_text_shrinks_pool(self):
        # The new text-narrowing path: picking a single text in the "Narrow by →
        # Text" multiselect leaves only that text's trials in the picker.
        at = _make_apptest()  # bundled 3-pid demo
        at.run(timeout=30)
        text_ms = [m for m in at.multiselect if m.key == "filter_text_id"]
        assert text_ms, "Narrow-by text multiselect missing"
        trial_box = next(s for s in at.selectbox if s.key == "single_trial_id")
        total = len(trial_box.options)
        text_ms[0].set_value([text_ms[0].options[0]])
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        narrowed = len(
            next(s for s in at.selectbox if s.key == "single_trial_id").options
        )
        assert 0 < narrowed < total, (
            f"text narrowing didn't shrink pool ({narrowed}/{total})"
        )


@pytest.mark.timeout(90)
class TestSingleReportDatasets:
    """The whole app pipeline (load → normalize → filter → all five tabs)
    must run when a dataset ships only one of the two reports."""

    def _run_with_demo_override(self, monkeypatch, make_frames):
        import pandas as pd

        from scanpath_studio import app, data

        words_raw, fix_raw = data.load_sample_data()
        words_raw = words_raw[words_raw["participant_id"] == "l37_1129"]
        fix_raw = fix_raw[fix_raw["participant_id"] == "l37_1129"]
        override = make_frames(words_raw, fix_raw, pd.DataFrame())
        monkeypatch.setattr(app, "load_sample_data", lambda *a, **k: override)

        at = _make_apptest()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_fixations_only_dataset(self, monkeypatch):
        self._run_with_demo_override(
            monkeypatch, lambda words, fix, empty: (empty, fix)
        )

    def test_words_only_dataset(self, monkeypatch):
        self._run_with_demo_override(
            monkeypatch, lambda words, fix, empty: (words, empty)
        )


class TestLazySubtabs:
    """PERF-3 — a per-trial subtab's body runs only when that tab is open.

    ``st.tabs`` executes every tab's body on every run; only the display is
    client-side. That made four expensive panels a fixed tax on every rail
    tweak. Streamlit 1.61's keyed tabs expose ``tab.open``, so the bodies are
    now gated on it — which is only correct if opening a tab really does load
    it, and if the closed ones really are skipped.
    """

    def test_closed_subtabs_do_not_run_their_bodies(self, monkeypatch):
        from scanpath_studio import tabs as tabs_module

        ran: list[str] = []
        for name in (
            "render_multiple_comparison_tab",
            "render_alignment_comparison_tab",
            "render_data_inspection_tab",
            "_render_export_panel",
        ):
            real = getattr(tabs_module, name)

            def spy(*a, _n=name, _r=real, **k):
                ran.append(_n)
                return _r(*a, **k)

            monkeypatch.setattr(tabs_module, name, spy)

        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Annotations is the default tab, so none of the four should have run.
        assert ran == [], f"a closed subtab still rendered: {ran}"

    def test_opening_a_subtab_loads_it(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        assert not [r for r in at.radio if r.key == "bulk_export_scope"]

        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert [r for r in at.radio if r.key == "bulk_export_scope"], (
            "opening the Export subtab did not load its body"
        )


@pytest.mark.timeout(90)
class TestDataInspectionTab:
    """The 🗂️ Data page's lower half — the former Raw Data + Data Statistics
    tabs merged into one panel: headline counts, raw tables, the summary-stats
    table, and (as its own section above them since DATA-26) the column-mapping
    table — while dropping the second stats row, the fixation histogram, and the
    per-word measure section."""

    def test_merged_sections_present_and_old_removed(self):
        at = _make_apptest(synthetic=True)
        pin_data_view(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # UX-52 gave the page one heading level. UX-135 then split that level in
        # two along the DATA-35 screen split: the *overview* keeps its
        # subheaders, and every section of the ✏️ Edit screen is one of the add
        # screen's numbered parts, so its headings are `.sps-wiz-part` markdown.
        subheaders = [s.value for s in at.subheader]
        for section in (
            "📂 Available datasets",
            "🔎 What's in the `Synthetic test trial` dataset",
        ):
            assert section in subheaders, f"missing stage {section}: {subheaders}"
        parts = " ".join(
            str(m.value)
            for m in at.markdown
            if str(m.value).startswith('<div class="sps-wiz-part"')
        )
        # `SCANPATH_EXPERIMENTAL=1` in conftest, so Preprocessing renders here
        # even though PRE-22 holds it back from the release build.
        for section in ("column mapping", "Recording setup", "Preprocessing"):
            assert section in parts, f"missing part {section}: {parts}"
        # The raw tables and the stats share ONE tab bar now — the collapsed
        # "📋 Raw data" expander over a tab bar, and the separate
        # "📊 Summary statistics" expander below it, are both gone.
        folded = [e.label for e in at.expander]
        assert not any("Raw data" in label for label in folded), folded
        assert not any("Summary statistics" in label for label in folded), folded
        tab_labels = [t.label for t in at.tabs]
        for tab in ("📊 Stats", "Fixations", "AOIs", "Raw gaze"):
            assert tab in tab_labels, f"missing tab {tab}: {tab_labels}"
        # The counts are the section's opening answer, so they kept no heading.
        assert "Dataset statistics" not in subheaders

        metric_labels = [m.label for m in at.metric]
        for headline in ("Participants", "Texts", "Trials", "Fixations", "Words"):
            assert headline in metric_labels, f"missing headline metric {headline}"
        # The second statistics row is gone.
        for dropped in ("Mean fixation dur (ms)", "Reading speed (wpm)"):
            assert dropped not in metric_labels, f"{dropped} should be removed"

        # The histogram + per-word measure sections are gone.
        text = " ".join(subheaders)
        assert "Fixation duration distribution" not in text
        assert "Per-word measure" not in text

        # The filtering note stays under the summary-stats table.
        # UX-137 moved that caveat onto each spread metric's own ❔ — it was the
        # only prose on the tab, read once and then never again.
        assert not any("computed after filtering" in c.value for c in at.caption)
        spread = [m for m in at.metric if m.label.endswith("per trial")]
        assert spread, [m.label for m in at.metric]
        assert all("Computed after the current filters" in m.help for m in spread)

    def test_column_mapping_uses_the_setup_field_grid(self):
        at = _make_apptest(synthetic=True)
        pin_data_view(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        mapping_cells = [
            m.value for m in at.markdown if "sps-readonly-map-value" in (m.value or "")
        ]
        assert mapping_cells, "column-mapping field grid not rendered"
        assert any("participant_id" in cell for cell in mapping_cells)
        assert any("trial_id" in cell for cell in mapping_cells)

    def test_top_level_nav_views(self):
        # Top-level navigation is Streamlit's own top nav — `st.navigation(
        # position="top")` — not a sidebar radio, and not the single toggling
        # header button it replaced. `main_nav` survives as the mirror every
        # other reader (the tour, persistence, `_active_view`) still consults.
        # Data Inspection and Share are subtabs of the Scanpath view.
        from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH

        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # No main_nav radio anymore.
        assert not [r for r in at.radio if r.key == "main_nav"], (
            "top-level nav should no longer be a radio"
        )
        # The router lands on the default page, and `main_nav` mirrors it.
        assert at.session_state["main_nav"] == _VIEW_SCANPATH

        # A view *requested* by writing `main_nav` (what `_go_corpus` and the
        # tour do from `on_click` callbacks, where `st.switch_page` is illegal)
        # is honoured: `render_nav` reconciles the router to it.
        at.session_state["main_nav"] = _VIEW_CORPUS
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["main_nav"] == _VIEW_CORPUS

    def test_nav_click_is_not_bounced_back_by_the_reconciler(self):
        """Clicking the nav must stick — it must not read as "go back".

        `render_nav` reconciles a programmatically-requested view (written to
        `main_nav` from a callback, where `st.switch_page` is illegal) against
        the router's selection. The first cut compared `main_nav` to the
        selection directly, so a user's click — which moves the router while
        `main_nav` still holds last run's view — looked exactly like a request
        to return, and the nav bounced straight back. The fix compares against
        what the reconciler itself last mirrored; this pins it.
        """
        from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH
        from scanpath_studio.menu import _MIRROR_KEY, _NAV_PAGES, _PAGES, render_nav

        class _FakePage:
            def __init__(self, title):
                self.title = title

        state = {"main_nav": _VIEW_SCANPATH, _MIRROR_KEY: _VIEW_SCANPATH}
        switched: list[str] = []

        # Stand in for the router: the user just clicked "Corpus Analysis".
        clicked = _FakePage(_NAV_PAGES[_VIEW_CORPUS][0])
        with (
            mock.patch.object(menu_mod.st, "session_state", state),
            mock.patch.object(
                menu_mod.st, "Page", lambda *a, **k: _FakePage(k["title"])
            ),
            mock.patch.object(menu_mod.st, "navigation", lambda *a, **k: clicked),
        ):
            _PAGES.clear()
            with mock.patch.object(
                menu_mod, "switch_to_view", lambda view: switched.append(view)
            ):
                active = render_nav()

        assert active == _VIEW_CORPUS, "the click must land on Corpus Analysis"
        assert switched == [], f"the click was bounced back to {switched}"
        assert state["main_nav"] == _VIEW_CORPUS

    def test_nav_pages_cover_every_view(self):
        """The nav offers every top-level entry, in order.

        `_PAGES` is what `switch_to_view` navigates through, so a missing entry
        is a view nothing can reach programmatically. DATA-26 added 🗂️ Data
        **last** of the analysis views: setup comes first in time, but the two
        analysis views are where the work happens and moving them would cost
        every user their aim.

        Neither ❓ Help nor 💾 Session is here. UX-65 made Help a collapsible nav
        *section* of dialog-openers (`_HELP_PAGES`), which are actions rather
        than views — nothing navigates to one and stays — and UX-100 made
        Session a popover on the title row, for the same reason: you dip into it
        and carry on, rather than travelling to it.
        """
        from scanpath_studio.constants import (
            _VIEW_CORPUS,
            _VIEW_DATA,
            _VIEW_SCANPATH,
        )
        from scanpath_studio.menu import _HELP_PAGES, _NAV_PAGES

        assert list(_NAV_PAGES) == [
            _VIEW_SCANPATH,
            _VIEW_CORPUS,
            _VIEW_DATA,
        ]
        assert list(_HELP_PAGES) == [
            "help_tutorials",
            "help_faq",
            "help_about",
        ]


@pytest.mark.timeout(120)
class TestLeavingTheWizard:
    """BUG-31: navigating away mid-wizard must not switch the app onto the
    half-built dataset."""

    def _in_wizard(self):
        """An app with the add-dataset wizard open and rendering.

        `main_nav` is deliberately not asserted: it mirrors Streamlit's own
        router, and AppTest's router does not follow the `st.switch_page` that
        `menu.render_nav` issues, so it reports the default page here whatever
        the app asked for. What matters — and what is checked — is that the
        wizard is open and its widgets are on screen.
        """
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        _enter_add_data(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["_show_upload_wizard"] is True
        assert "cancel_add_data" in {b.key for b in at.button}
        return at

    def test_navigating_away_holds_the_page_and_asks(self):
        """The wizard keeps rendering and asks, instead of the app switching onto
        the unfinished upload and reporting "no data" over a session that still
        holds every finished dataset.

        Nothing here navigates — see the note in `app.main`: every way to move
        the router ends in `st.switch_page`, which aborts the run it is called
        in, and an aborted run renders no wizard, so `st.file_uploader` (the one
        widget `persist_state` cannot save) would lose its files before the
        question could be asked. The nav highlight is therefore allowed to sit on
        the view the user clicked while the page under it asks."""
        from scanpath_studio.constants import _VIEW_SCANPATH

        at = self._in_wizard()
        at.session_state["main_nav"] = _VIEW_SCANPATH
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["_wizard_leave_requested"] == _VIEW_SCANPATH
        assert at.session_state["_show_upload_wizard"] is True
        keys = {b.key for b in at.button}
        assert {"wizard_leave_stay", "wizard_leave_discard"} <= keys
        # The wizard is still on screen — its own bar, not a "nothing to plot".
        assert "cancel_add_data" in keys

    def test_keep_setting_up_dismisses_the_prompt(self):
        """…and *stays* dismissed. Nothing navigated, so the nav is still on the
        view the user declined; clearing the prompt without recording which view
        that was would re-ask it on every rerun.

        **BUG-36 follow-up:** the click-processing run is deliberately *not*
        re-pinned. `render_nav`'s reconciliation (which `pin_view` drives by
        clearing its mirror) calls `st.switch_page` when it fires — a real
        rerun, early in the script, well before the dialog's own button is
        reached — and a button's "just clicked" value is one-shot: valid only
        for the script execution immediately following the actual click, not
        for one a same-run `st.rerun()` restarts from scratch. Pin_view'ing
        the same run as the click would silently drop it before the return
        value ever reads `True` — a race that can't happen in a real browser,
        since nothing about clicking a dialog button asks the router to
        switch pages, but very much can here since `pin_view` is a test-only
        stand-in for the router remembering its page across runs at all. Left
        unpinned, the run instead resolves the *default* page (Scanpath) —
        AppTest's router forgets the previous switch between separate `.run()`
        calls the same way it forgets everything else — so that is also what
        `WIZARD_STAY_KEY` ends up recording, and the two checks below follow
        that: an unpinned rerun (same, default page) must not re-ask, while
        pinning to a genuinely different view (Corpus Analysis) must."""
        at = self._in_wizard()
        pin_view(at, "Corpus Analysis")
        at.run(timeout=60)
        next(b for b in at.button if b.key == "wizard_leave_stay").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "_wizard_leave_requested" not in at.session_state
        assert at.session_state["_show_upload_wizard"] is True
        at.run(timeout=60)
        assert not [b for b in at.button if b.key == "wizard_leave_stay"]
        # A *different* view is a new question.
        pin_view(at, "Corpus Analysis")
        at.run(timeout=60)
        assert [b for b in at.button if b.key == "wizard_leave_stay"]

    def test_discard_closes_the_wizard_and_restores_the_source(self):
        """Discarding leaves the wizard and puts the previous dataset back.

        The *destination* half — that the nav then completes the trip the user
        started — is browser-verified only: the callback requests it by writing
        `main_nav` (an `on_click` may not call `st.switch_page`), and AppTest's
        router does not follow the `switch_page` the reconciler then issues, so
        it reports the default page instead. What is asserted here is everything
        that lives in session state, including the part that actually caused the
        bug: the app must not be left pointing at the half-built upload."""
        at = self._in_wizard()
        previous = at.session_state["_prev_source"]
        pin_view(at, "Corpus Analysis")
        at.run(timeout=60)
        next(b for b in at.button if b.key == "wizard_leave_discard").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["_show_upload_wizard"] is False
        assert "_wizard_leave_requested" not in at.session_state
        # Back on the dataset the wizard was opened from, not the half-built one
        # — the symptom that made this read as data loss.
        assert at.session_state["data_source_choice"] == previous


@pytest.mark.timeout(120)
class TestDatasetTable:
    """UX-54: the 🗂️ Data page lists datasets as a table, with the per-row
    actions in the row they belong to."""

    NAME = "My corpus"

    def _at(self):
        import pandas as pd

        from scanpath_studio import api
        from scanpath_studio.data import load_sample_data

        words, fixations = api.load_scanpath_data(*load_sample_data())
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["_datasets"] = {
            self.NAME: {
                "words": words,
                "fixations": fixations,
                "raw_gaze": pd.DataFrame(),
                "filter_fields": [],
                "composite_trial_columns": [],
            }
        }
        at.session_state["data_source_choice"] = self.NAME
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        return at

    def _table(self, at):
        for element in at.dataframe:
            frame = element.value
            if frame is not None and "Dataset" in getattr(frame, "columns", []):
                return frame
        raise AssertionError("dataset table not rendered on the Data page")

    def test_the_table_lists_datasets_with_counts_and_row_actions(self):
        at = self._at()
        frame = self._table(at)
        row = frame[frame["Dataset"] == self.NAME]
        assert not row.empty, f"{self.NAME} missing from {list(frame['Dataset'])}"
        # Counts come from the frames already in memory, not from a reload.
        assert int(row["Participants"].iloc[0]) > 0
        assert int(row["Fixations"].iloc[0]) > 0
        for column in (
            "Participants",
            "Texts",
            "Trials",
            "Screens",
            "Fixations",
            "Words",
            "Gaze points",
        ):
            assert str(frame[column].dtype) == "Int64", (
                f"{column} should stay integer even when unopened datasets are blank"
            )
        assert row["Kind"].iloc[0] == "🔒 Private"
        for icon, word in {
            "🧪": "Demo",
            "✏️": "Manual",
            "🔒": "Private",
            "🌐": "Public",
        }.items():
            matching = frame[frame["Kind"].astype(str).str.startswith(icon)]
            if not matching.empty:
                assert matching["Kind"].astype(str).str.contains(word).all()
        # DATA-35: every row carries every action. Edit used to be an upload's
        # alone, back when it only opened the mapping editor a stored upload
        # has; it now opens the Edit dataset screen, which every source has.
        for column in ("About", "Edit", "Rename", "Remove"):
            assert row[column].iloc[0], f"{column} missing from an upload's row"
        demo = frame[frame["Dataset"].str.contains("demo", case=False)]
        if not demo.empty:
            for column in ("About", "Edit", "Rename", "Remove"):
                assert demo[column].iloc[0], f"{column} missing from the demo's row"
            # DATA-35's language cell: the demo is a OneStop subset, so it knows
            # its language. Its **home link** used to be a column here too; it
            # moved into the ℹ️ About body, which is asserted below.
            assert demo["Language"].iloc[0]
            assert "Home" not in frame.columns

    def test_about_body_carries_the_home_link(self):
        """The corpus home link moved out of the table into ℹ️ About.

        A column of "Open ↗" cells next to nothing saying what opens was the
        thing being paid for; the link belongs with the description of the
        corpus it leads to. Checked at the source level for the same reason
        `test_delete_is_wired_to_the_remover` is: what matters is that the body
        still writes it somewhere, not how Streamlit lays it out.
        """
        import inspect

        from scanpath_studio.app import _render_dataset_about_body

        source = inspect.getsource(_render_dataset_about_body)
        assert 'about.get("link")' in source
        assert "about['link']" in source

    def test_delete_is_wired_to_the_remover(self):
        """Regression: UX-64 dropped the ➕ popover that held *Remove a dataset*,
        leaving `wizard._remove_dataset` with **no caller at all** — deleting an
        upload was unreachable until this table's ✕ put it back.

        AppTest cannot click a `ButtonColumn` cell, and the remover itself is
        covered by `tests/test_wizard_helpers.py`; what is untested without this
        is that anything still calls it. That is a source-level fact, so it is
        checked as one."""
        import inspect

        from scanpath_studio.app import (
            _delete_confirmation_dialog,
            _render_delete_confirmation,
            render_dataset_table,
        )

        # UX-54 r2 put a confirmation between the two: the table's ✕ arms the
        # pending token, and the confirm button is what calls the remover. UX-79
        # then made that confirmation a modal, so the chain is one link longer —
        # the invariant this test exists for is unchanged: something still calls
        # the remover.
        table_source = inspect.getsource(render_dataset_table)
        assert '_clicked("dataset_table_delete")' in table_source
        assert "PENDING_DELETE_KEY" in table_source
        gate_source = inspect.getsource(_render_delete_confirmation)
        assert "_delete_confirmation_dialog(" in gate_source
        dialog_source = inspect.getsource(_delete_confirmation_dialog)
        assert "from scanpath_studio.wizard import _remove_dataset" in dialog_source
        assert "_remove_dataset(" in dialog_source


@pytest.mark.timeout(90)
class TestDatasetRename:
    """DATA-23: a dataset the user added can be renamed after the fact.

    The name is the key into the ``_datasets`` store, so these are really about
    everything that key had to drag along with it. ``wizard.rename_dataset`` is
    the whole of that, and it touches only session state — so it is exercised
    directly rather than through a 90-second AppTest boot.

    The rename now lives in exactly **one** place: the row's ✏️ Rename in
    📂 Available datasets. The duplicate inline popover inside "What's in this
    dataset" is gone; the last two tests pin both halves of that.
    """

    NAME = "My corpus"

    @pytest.fixture(autouse=True)
    def _session(self):
        """A clean ``st.session_state`` per test.

        Bare mode (no ``streamlit run``) gives a real, writable session state
        that persists for the process, so it has to be cleared between tests.
        """
        import streamlit as st

        st.session_state.clear()
        yield st.session_state
        st.session_state.clear()

    def _store(self, _session, *names):
        _session["_datasets"] = {name: {"words": name} for name in names}
        _session["data_source_choice"] = names[0]

    def test_rename_rekeys_the_store_and_follows_the_selection(self, _session):
        from scanpath_studio import wizard

        self._store(_session, self.NAME)
        assert wizard.rename_dataset(self.NAME, "Reading study 2026") == (
            "Reading study 2026"
        )

        assert set(_session["_datasets"]) == {"Reading study 2026"}
        # The selection followed, so the app is still showing the same data
        # rather than falling back to the demo (the healing branch in
        # resolve_data_source drops a name that is no longer an entry). It is
        # applied through the pre-widget seam, not by assigning the widget key.
        assert _session["_pending_source_choice"] == "Reading study 2026"

    def test_a_taken_name_is_suffixed(self, _session):
        from scanpath_studio import wizard

        self._store(_session, self.NAME, "Other corpus")
        assert wizard.rename_dataset(self.NAME, "Other corpus") == "Other corpus (2)"

        assert "Other corpus (2)" in _session["_datasets"]
        # Both datasets survive — a rename must never overwrite another entry's
        # frames, which is what an un-suffixed re-key would do.
        assert _session["_datasets"]["Other corpus"] == {"words": "Other corpus"}

    def test_the_compare_dataset_follows_the_rename(self, _session):
        """CMP-8's scanpath B names its corpus by the same string."""
        from scanpath_studio import wizard
        from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY

        self._store(_session, self.NAME)
        _session[COMPARE_SOURCE_STATE_KEY] = self.NAME
        wizard.rename_dataset(self.NAME, "Renamed corpus")

        assert _session[COMPARE_SOURCE_STATE_KEY] == "Renamed corpus"

    def test_a_built_in_source_label_cannot_be_shadowed(self, _session):
        """A stored dataset named exactly like a built-in source would put a
        duplicate option in the picker and hijack that source's load branch."""
        from scanpath_studio import wizard
        from scanpath_studio.constants import DEMO_CHOICE

        self._store(_session, self.NAME)
        wizard.rename_dataset(self.NAME, DEMO_CHOICE)

        assert DEMO_CHOICE not in _session["_datasets"]
        assert f"{DEMO_CHOICE} (uploaded)" in _session["_datasets"]

    def test_the_row_dialog_is_the_one_way_in(self):
        """The table's ✏️ Rename arms a pending token that opens the dialog, and
        the dialog is what calls the renamer.

        Source-level for the same reason ``test_delete_is_wired_to_the_remover``
        is: AppTest cannot click a ``ButtonColumn`` cell, and a dialog rendered
        from inside an ``@st.fragment`` does not take AppTest clicks either.
        What must not silently break is the chain."""
        import inspect

        from scanpath_studio.app import (
            _rename_dataset_dialog,
            _render_rename_dialog,
            render_dataset_table,
        )

        assert '_clicked("dataset_table_rename")' in inspect.getsource(
            render_dataset_table
        )
        assert "_rename_dataset_dialog(" in inspect.getsource(_render_rename_dialog)
        dialog_source = inspect.getsource(_rename_dataset_dialog)
        assert "from scanpath_studio.wizard import rename_dataset" in dialog_source
        assert "rename_dataset(token, requested)" in dialog_source

    def test_the_inspection_section_carries_no_rename_of_its_own(self):
        """ "What's in this dataset" used to repeat the rename as a
        ``Dataset: <name>`` line with its own ✏️ Rename popover, one section
        below the table that already offers it."""
        import pandas as pd

        from scanpath_studio import api
        from scanpath_studio.data import load_sample_data

        words, fixations = api.load_scanpath_data(*load_sample_data())
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["_datasets"] = {
            self.NAME: {
                "words": words,
                "fixations": fixations,
                "raw_gaze": pd.DataFrame(),
                "filter_fields": [],
                "composite_trial_columns": [],
            }
        }
        at.session_state["data_source_choice"] = self.NAME
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert not [
            t for t in at.text_input if str(t.key).startswith("dataset_rename_")
        ]
        assert not [b for b in at.button if str(b.key).startswith("dataset_rename_")]


@pytest.mark.timeout(90)
class TestUnmappedRawDataView:
    """When a required column is unmapped, the app must show the raw uploaded
    data (so the user can pick the mapping) instead of halting."""

    def test_raw_data_shown_when_mapping_incomplete(self, monkeypatch):
        import pandas as pd

        from scanpath_studio import app

        # A words table whose columns match neither a word/IA id nor box
        # coordinates — exactly the screenshot's failure. Injected through the
        # per-table upload seam (AppTest can't drive st.file_uploader); the
        # Words/IA group gets it, the others stay empty.
        raw_words = pd.DataFrame(
            {"reader": ["r0", "r0"], "stim": ["b0", "b0"], "token": ["Um", "das"]}
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_words if kw["state_prefix"] == "col_map_words" else pd.DataFrame()
            ),
        )

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        # Past the setup wizard (collapsed "Data & mapping" panel), an incomplete
        # mapping still surfaces the raw data so the user can fix it. The raw
        # tables show in the Data Inspection view.
        at.session_state["setup_complete"] = True
        pin_data_view(at)
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The guidance banner names the missing field…
        warnings = " ".join(w.value for w in at.warning)
        assert "column mapping" in warnings.lower()
        assert "Word/IA ID" in warnings
        # …and the raw uploaded table is rendered so the user can inspect it.
        frames = [df.value for df in at.dataframe]
        assert any(list(f.columns) == ["reader", "stim", "token"] for f in frames), (
            "raw uploaded columns should be visible in the Raw Data tab"
        )

    def test_public_datasets_shown_by_default(self, monkeypatch):
        """The Public datasets corpora are offered by default in the flat source
        picker (DATA-9: each corpus is its own tagged entry, not a category)."""
        from scanpath_studio import app

        monkeypatch.delenv("SCANPATH_PUBLIC_DATASETS", raising=False)
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        source = [s for s in at.selectbox if s.key == "data_source_picker"]
        assert source, "data source picker not found"
        shorts = [spec["short"] for spec in app.public_dataset_registry().values()]
        # Options are formatted labels like "🌐 PoTeC".
        assert any(any(s in o for s in shorts) for o in source[0].options)

    def test_public_datasets_hidden_when_disabled(self, monkeypatch):
        """Setting SCANPATH_PUBLIC_DATASETS=0 hides the public corpora."""
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "0")
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        source = [s for s in at.selectbox if s.key == "data_source_picker"]
        assert source, "data source picker not found"
        shorts = [spec["short"] for spec in app.public_dataset_registry().values()]
        assert not any(any(s in o for s in shorts) for o in source[0].options)

    def test_potec_source_renders(self, monkeypatch):
        """Public datasets → PoTeC loads through the same pipeline as an upload.

        The source is behind the SCANPATH_PUBLIC_DATASETS flag until release —
        enabled here so the whole path stays tested."""
        import pandas as pd

        from scanpath_studio import app, datasets

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        words = pd.DataFrame(
            {
                "aoi": [1, 2],
                "start_x": [80.0, 115.0],
                "start_y": [21.0, 21.0],
                "end_x": [115.0, 189.0],
                "end_y": [99.0, 99.0],
                "word": ["Um", "null"],
                "text_id": ["b0", "b0"],
                "line": [1, 1],
            }
        )
        fixations = pd.DataFrame(
            {
                "reader_id": [0, 0],
                "text_id": ["b0", "b0"],
                "fixation_duration": [210, 190],
                "fixation_index": [1, 2],
                "word_index_in_text": [1, 2],
                "x": [97.5, 152.0],
                "y": [60.0, 60.0],
            }
        )
        monkeypatch.setattr(
            datasets, "potec_raw_frames", lambda *a, **k: (words, fixations)
        )
        # Pretend the corpus is already on disk so the loader takes the real load
        # path (no Download button) instead of falling back to the demo.
        monkeypatch.setattr(datasets, "potec_present", lambda *a, **k: True)

        at = _make_apptest()
        # DATA-9: each public corpus is a first-class entry in the flat source
        # picker — select PoTeC by its registry label (the option token).
        potec_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k)
        at.session_state["data_source_choice"] = potec_key
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        # The flat picker carries the corpus token; selecting it resolves to the
        # public source with the corpus on public_dataset_choice.
        source = next(s for s in at.selectbox if s.key == "data_source_picker")
        assert source.value == potec_key
        assert at.session_state["public_dataset_choice"] == potec_key

    def test_each_public_dataset_loader_ui_renders(self, monkeypatch, tmp_path):
        """Every corpus loader's access UI renders without error when its data
        directory is absent: a Data-directory input, an Expected-files expander,
        and a found/missing status (Download for the downloadable corpora), then
        a graceful fall back to the demo. Exercises the real loaders (not the
        monkeypatched ones the other tests use)."""
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        # Point every corpus' default data directory at an empty tmp path so the
        # "directory is absent" premise holds regardless of local cache. Without
        # this, a dev machine that has already downloaded a corpus (e.g. OneStop
        # to data/OneStop) would load the full report — tens–hundreds of MB — and
        # blow the class timeout, since the loader reads the real default dir.
        for const in (
            "ONESTOP_PUBLIC_DEFAULT_DIR",
            "POTEC_DEFAULT_DIR",
            "MULTIPLEYE_DEFAULT_DIR",
            "EYEGENBENCH_DEFAULT_DIR",
        ):
            monkeypatch.setattr(app, const, str(tmp_path / const.lower()))
        for label in app.public_dataset_registry():
            at = _make_apptest()
            at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
            at.session_state["public_dataset_choice"] = label
            at.run(timeout=60)

            assert not at.exception, f"{label}: {at.exception}"
            assert at.error == [], f"{label}: {[e.value for e in at.error]}"
            dir_inputs = [t for t in at.text_input if t.label == "Data directory"]
            assert dir_inputs, f"{label}: expected a Data directory input"
        # PoTeC + OneStop are downloadable → a Download button is offered when the
        # files are absent; MultiplEYE (no public URL) shows a missing-data note.
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
        at.session_state["public_dataset_choice"] = next(
            k for k in app.public_dataset_registry() if "PoTeC" in k
        )
        at.run(timeout=60)
        assert any("Download" in b.label for b in at.button), (
            "expected a Download button"
        )

    def test_a_publisher_leftover_column_does_not_hijack_the_benchmark_schema(
        self, tmp_path, monkeypatch
    ):
        """A prepared corpus loads by its DECLARED schema, not by auto-detection.

        The bug this pins shipped through a whole branch review because every
        fixture wrote an idealized frame carrying only the harmonised columns.
        Real prepared frames carry the publisher's ~190 columns through, and the
        detector prefers some of them:

        * EMTeC ships `TRIAL_ID`, which outranks `unique_paragraph_id` on the
          fixations. The words still key on `unique_paragraph_id`, so
          `broadcast_stimulus_words` joins **nothing** — zero word boxes, no
          stimulus, no word-level measure, and **no error**, because only the
          words frame ends up empty and `main`'s empty-pool guard needs all
          three. The figure still draws 400k fixations over blank space.
        * Provo and SBSAT ship `page`, which reads as a multipart screen id on
          the fixations only, and `multipart.validate_matching_parts` then
          rejects the pair outright.

        Both are app-only: `load_eyegenbench` passes the explicit schemas, so
        the CLI, the headless API and Comparisons' dataset B were always right —
        which is the tell. Two surfaces disagreeing about one corpus is the
        signature this plan has now hit five times.
        """
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "bundle"
        # Both real hijackers at once, on one corpus.
        _write_benchmark_corpus(
            root,
            "Provo",
            paragraphs=("Provo_a", "Provo_b"),
            fix_leftovers={"TRIAL_ID": "hijack", "page": 1},
        )
        _write_benchmark_manifest(
            root, [{"name": "Provo", "language": "en", "monitor": [1600, 900]}]
        )
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(root))

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("Provo")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The loud half: `page` must not be read as a screen id.
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert not any(
            "column mapping doesn't work" in str(w.value) for w in at.warning
        )

        # The silent half, and the one that matters. "No exception" passes on the
        # zero-boxes bug — that is exactly how it survived a review — so assert on
        # the mapping actually used, which is the mechanism itself.
        mapping = at.session_state["_active_column_mapping"] or {}
        fix_map = mapping.get("fixations") or {}
        word_map = mapping.get("words") or {}
        assert fix_map.get("trial") == "unique_paragraph_id", (
            "the fixations' leftover TRIAL_ID hijacked the trial mapping; the "
            "words key on unique_paragraph_id, so the broadcast joins NOTHING "
            f"and the corpus draws with zero word boxes. Got: {fix_map.get('trial')!r}"
        )
        assert fix_map.get("trial") == word_map.get("trial"), (
            "words and fixations must key on the same trial column or they cannot join"
        )
        # `page` is a leftover, not a screen: this bundle is single-screen by
        # contract, and a screen id on one frame only is rejected outright.
        assert not fix_map.get("screen_id"), fix_map.get("screen_id")
        assert not word_map.get("screen_id"), word_map.get("screen_id")

        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}

    def test_each_prepared_benchmark_corpus_is_its_own_picker_entry(
        self, monkeypatch, tmp_path
    ):
        """DATA-27 R36/R37: every prepared corpus is a top-level source.

        The first cut of this feature offered ONE "EyeGenBench" entry with a
        Language/Corpus sub-picker nested inside it; the user's call is that each
        dataset appears separately, and that the pipeline's name is provenance
        rather than a source (it is being extracted into its own repository, so
        anything user-visible carrying it would need renaming later). So: one 🌐
        entry per corpus, indistinguishable in kind from PoTeC / MultiplEYE /
        OneStop, and no entry label naming the pipeline.

        `PoTeC` ships **both** natively here and in the benchmark set, and both
        are kept — the harmonised copy is what makes cross-corpus comparison
        possible. They are told apart by the property that differs (R37), and the
        geometry badge is per corpus and must not overclaim uniformity (R34).
        """
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "bundle"
        # Two texts each: the **Narrow by** Text multiselect only renders when
        # it would offer more than one choice (`controls.render_narrow_by`), and
        # it is how this test proves the *selected* corpus is what loaded.
        _write_benchmark_corpus(root, "PoTeC", paragraphs=("PoTeC_a", "PoTeC_b"))
        _write_benchmark_corpus(root, "Provo", paragraphs=("Provo_a", "Provo_b"))
        _write_benchmark_manifest(
            root,
            [
                # `language` is an ISO code in the real manifest, never a name
                # (verified: BSC → 'zh', CopCo → 'da', Provo → 'en').
                {
                    "name": "PoTeC",
                    "language": "de",
                    "monitor": [1680, 1050],
                    "monitor_source": "published",
                    "n_readers": 75,
                    "n_texts": 12,
                    "n_fixations": 250000,
                    "geometry_source": "real",
                    # Mixed: measured boxes for 9 of the 12 texts.
                    "paragraphs_without_real_boxes": 3,
                },
                {
                    "name": "Provo",
                    "language": "en",
                    "monitor": [1600, 900],
                    "monitor_source": "published",
                    "n_readers": 84,
                    "n_texts": 55,
                    "n_fixations": 219556,
                    "geometry_source": "real",
                    "paragraphs_without_real_boxes": 0,
                },
            ],
        )
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(root))

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("Provo")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

        picker = next(s for s in at.selectbox if s.key == "data_source_picker")
        options = list(picker.options)
        # Each corpus is its own entry, tagged 🌐 like every other public corpus,
        # and — while DATA-27 is on main unfinished — marked (WIP).
        assert "🌐 Provo (WIP)" in options
        # …and the one that also ships natively keeps both, distinguished by the
        # property that differs rather than by the pipeline's name.
        assert "🌐 PoTeC (harmonised benchmark) (WIP)" in options
        # The control case, and the reason the marker is keyed on the entry's
        # `benchmark_dataset` rather than on its label: the NATIVE PoTeC is
        # finished work and must stay unmarked. A substring test on the label
        # would mark it too, and this assertion is what would catch that.
        assert "🌐 PoTeC" in options
        assert "🌐 PoTeC (WIP)" not in options
        assert not any("EyeGenBench" in option for option in options), (
            "the pipeline's name is provenance, not a source — it must not "
            f"appear in an entry label: {options}"
        )
        # Selecting one loads that corpus (its trials, not another's).
        assert at.session_state["public_dataset_choice"] == app.benchmark_corpus_label(
            "Provo"
        )
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}
        captions = " ".join(c.value for c in at.caption)
        # R35: the manifest's ISO code renders as a display name.
        assert "English" in captions
        assert "84 readers" in captions
        # R34: full coverage → the plain badge.
        assert "measured word boxes." in captions
        assert "of 55 texts" not in captions

        # Switching to the other corpus is an ordinary source switch.
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("PoTeC")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["public_dataset_choice"] == app.benchmark_corpus_label(
            "PoTeC"
        )
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"PoTeC_a", "PoTeC_b"}
        captions = " ".join(c.value for c in at.caption)
        assert "German" in captions
        # R34: `geometry_source` is the *best tier achieved*, so a corpus with
        # three unmeasured texts still reads "real" — the rendering must say how
        # many texts that actually covers rather than implying all of them.
        assert "measured word boxes for 9 of 12 texts" in captions

    def test_benchmark_canvas_snaps_to_each_corpus_own_monitor(
        self, monkeypatch, tmp_path
    ):
        """R40: each corpus resolves its own monitor from its own manifest row.

        This was R30's defect — one source fronting many corpora meant the
        registry's single declared monitor stood in for all of them, and the
        canvas had to be re-snapped from a second session key. With one entry per
        corpus the registry entry *is* per corpus, so the plain
        `public_dataset_choice` key carries it.

        The honesty tier survives the simplification: a `monitor_source` of
        `default` is `eyegenbench_geometry.py`'s generic guess for a corpus that
        documents no screen, so that entry declares no monitor at all rather than
        snapping the canvas to an invented one.
        """
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "bundle"
        for name in ("PoTeC", "Provo", "Guessed"):
            _write_benchmark_corpus(root, name)
        _write_benchmark_manifest(
            root,
            [
                {
                    "name": "PoTeC",
                    "language": "de",
                    "monitor": [1680, 1050],
                    "monitor_source": "published",
                },
                {
                    "name": "Provo",
                    "language": "en",
                    "monitor": [1920, 1200],
                    "monitor_source": "derived-from-boxes",
                },
                {
                    "name": "Guessed",
                    "language": "fr",
                    "monitor": [1920, 1080],
                    "monitor_source": "default",
                },
            ],
        )
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(root))

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("PoTeC")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert (
            at.session_state["global_canvas_width"],
            at.session_state["global_canvas_height"],
        ) == (1680, 1050)

        # Switching corpus re-snaps the canvas — for free, from
        # `public_dataset_choice` alone.
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("Provo")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert (
            at.session_state["global_canvas_width"],
            at.session_state["global_canvas_height"],
        ) == (1920, 1200)

        # An invented ("default") screen must NOT snap the canvas the way the
        # published / derived-from-boxes ones above do.
        at2 = _make_apptest()
        at2.session_state["global_canvas_width"] = 1234
        at2.session_state["global_canvas_height"] = 999
        at2.session_state["_canvas_seeded_for"] = ("something", "else")
        at2.session_state["data_source_choice"] = app.benchmark_corpus_label("Guessed")
        at2.run(timeout=60)
        assert not at2.exception, f"Streamlit exceptions: {at2.exception}"
        assert (
            at2.session_state["global_canvas_width"],
            at2.session_state["global_canvas_height"],
        ) == (1234, 999)

    def test_benchmark_corpus_switch_resets_trial_filters(self, monkeypatch, tmp_path):
        """R40: switching corpus clears the trial filters and restores them back.

        R31 needed an extra `eyegenbench_dataset` component in
        `_activate_data_source`'s source key, because `public_dataset_choice` was
        the same constant for every corpus behind the one source — so a filter
        narrowed to a PoTeC-only text rode straight into Provo, where no trial
        could satisfy it and nothing said why the pool went empty. One entry per
        corpus makes that key correct on its own; this test is R31's, kept, so it
        proves the simplification is safe rather than a regression.
        """
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "bundle"
        _write_benchmark_corpus(root, "PoTeC", paragraphs=("PoTeC_a", "PoTeC_b"))
        _write_benchmark_corpus(root, "Provo", paragraphs=("Provo_a", "Provo_b"))
        _write_benchmark_manifest(
            root,
            [
                {"name": "PoTeC", "language": "de", "monitor": [1680, 1050]},
                {"name": "Provo", "language": "en", "monitor": [1920, 1080]},
            ],
        )
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(root))

        potec = app.benchmark_corpus_label("PoTeC")
        provo = app.benchmark_corpus_label("Provo")

        at = _make_apptest()
        at.session_state["data_source_choice"] = potec
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # R32 canary (M13/N4): the app path must auto-detect a benchmark
        # corpus' schema. The pre-Task-11R test compared the mapping before and
        # after the switch, which `_colmap_seeded_for` made obsolete (both
        # corpora share one schema, so there is nothing to re-seed); the
        # seeding assertion that replaced it asserted only that *some*
        # `col_map_words_*` key existed, which `column_mapping_ui` creates
        # (index 0, `persist_state="session"`) whenever the panel renders at
        # all — so it pinned "the mapping panel rendered", not "detection
        # resolved". The three fields R32 is actually about are on the
        # fixations side, and what matters is the *value*: unresolved, each
        # falls back to `(none)` and every reader collapses into one synthetic
        # id, with no error anywhere to say so.
        assert {
            k: v
            for k, v in at.session_state.filtered_state.items()
            if k
            in (
                "col_map_fix_participant",
                "col_map_fix_fixation_id",
                "col_map_fix_word_id",
            )
        } == {
            "col_map_fix_participant": "unique_participant_id",
            "col_map_fix_fixation_id": "fix_index",
            "col_map_fix_word_id": "ia_index",
        }

        # Narrow to one PoTeC-only text.
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"PoTeC_a", "PoTeC_b"}
        text_ms.set_value(["PoTeC_a"])
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["filter_text_id"] == ["PoTeC_a"]

        # 1. Switching corpus clears the (now-impossible-for-Provo) filter.
        at.session_state["data_source_choice"] = provo
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["filter_text_id"] == []
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}

        # 2. Switching back restores PoTeC's own stashed filter.
        at.session_state["data_source_choice"] = potec
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["filter_text_id"] == ["PoTeC_a"]

    def test_a_bundle_at_a_non_default_path_becomes_reachable_and_stays(
        self, monkeypatch, tmp_path
    ):
        """R39 end to end: type a path, pick the corpus, keep it.

        The bootstrap entry exists for exactly one job — a bundle that is *not*
        at `EYEGENBENCH_DEFAULT_DIR` must be reachable, since discovery reads a
        directory the user can change at runtime and an undiscovered bundle
        yields no entries and so nowhere to type its path. The first cut of the
        entry shipped non-functional and passed its test anyway, because the
        test asserted the directory input *existed* and never typed into it
        (C1): the typed path survived exactly one run. Discovery then succeeded,
        the placeholder dropped out of the registry, the healing step sent the
        user to the bundled demo, the demo renders no directory input — so
        Streamlit dropped the `eyegenbench_dir` key at end of run and the next
        run rediscovered nothing. The corpora flickered in for one rerun,
        forever.

        So this drives the whole flow: type → the corpus appears → **select
        it** → it is still selected, still loaded, and still there after a
        detour to another source. Everything before the last step passes on the
        bug in at least one of its halves; the run *after* each selection is
        what fails on it.
        """
        from scanpath_studio import app
        from scanpath_studio.constants import AUTHOR_CHOICE

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        # The premise: the app's default location is empty and the bundle is
        # somewhere else entirely. Nothing is discoverable until it is typed in.
        default_dir = tmp_path / "default-location"
        default_dir.mkdir()
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(default_dir))
        root = tmp_path / "elsewhere" / "bundle"
        _write_benchmark_corpus(root, "Provo", paragraphs=("Provo_a", "Provo_b"))
        _write_benchmark_manifest(
            root, [{"name": "Provo", "language": "en", "monitor": [1600, 900]}]
        )
        label = app.benchmark_corpus_label("Provo")

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.BENCHMARK_SETUP_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        picker = next(s for s in at.selectbox if s.key == "data_source_picker")
        assert "🌐 Harmonised benchmark corpora — set up (WIP)" in picker.options
        # The *marked* form, deliberately: asserting "🌐 Provo" is absent would
        # now pass whether or not the corpus is listed, since a listed one reads
        # "🌐 Provo (WIP)".
        assert "🌐 Provo (WIP)" not in picker.options

        # 1. The user types the bundle's real path into the placeholder's input.
        dir_inputs = [t for t in at.text_input if t.key == "eyegenbench_dir"]
        assert dir_inputs, "expected the bundle directory input"
        dir_inputs[0].set_value(str(root)).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        picker = next(s for s in at.selectbox if s.key == "data_source_picker")
        assert "🌐 Provo (WIP)" in picker.options, "the corpus must appear once found"
        # The placeholder disappears *because it succeeded*, so healing must not
        # bounce the user out to the demo — that answers "here is my bundle"
        # with somewhere else entirely, and (the demo drawing no directory
        # input) throws the bundle location away on the way out.
        assert at.session_state["data_source_choice"] == label

        # 2. The user picks the corpus in the picker, through the real widget.
        picker.set_value(label).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # 3. The run after the selection — the one that used to lose the path.
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["eyegenbench_dir"] == str(root)
        assert at.session_state["data_source_choice"] == label
        picker = next(s for s in at.selectbox if s.key == "data_source_picker")
        assert "🌐 Provo (WIP)" in picker.options
        # The placeholder is offered only while nothing is discovered, and the
        # options are checked rather than `public_dataset_registry()` because
        # the bundle's location lives in *this app run's* session state — a
        # registry built out here, outside the run, cannot see it.
        assert not any("set up" in option for option in picker.options)
        # …and the corpus is genuinely loaded, not merely named in the picker.
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}

        # 4. A detour to another source and back. The directory input renders
        # only while a benchmark corpus is selected, so this is the run on which
        # Streamlit drops an ordinary widget key — `persist_state="session"` on
        # the shared `_dataset_dir_input` is what keeps the bundle findable.
        picker.set_value(AUTHOR_CHOICE).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert not [t for t in at.text_input if t.key == "eyegenbench_dir"], (
            "premise: another source renders no bundle directory input"
        )
        picker = next(s for s in at.selectbox if s.key == "data_source_picker")
        assert "🌐 Provo (WIP)" in picker.options, "the bundle location must survive"
        picker.set_value(label).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["data_source_choice"] == label
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}

    def test_repointing_the_bundle_lands_on_a_corpus_not_on_the_demo(
        self, monkeypatch, tmp_path
    ):
        """N2: healing a stale *corpus* label, not just the placeholder.

        The selected corpus can stop existing without anything going wrong —
        the user points the directory input at a second bundle, or rebuilds one
        without that corpus. The selection is then invalid and the generic
        healing sends it to `entries[0]`, the bundled demo. That is the same
        non-answer C1's second half exists to prevent: the user asked for a
        different bundle and got the demo, when a prepared corpus from the
        bundle they just named was right there.
        """
        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        first = tmp_path / "first-bundle"
        _write_benchmark_corpus(first, "PoTeC", paragraphs=("PoTeC_a", "PoTeC_b"))
        _write_benchmark_manifest(
            first, [{"name": "PoTeC", "language": "de", "monitor": [1680, 1050]}]
        )
        second = tmp_path / "second-bundle"
        _write_benchmark_corpus(second, "Provo", paragraphs=("Provo_a", "Provo_b"))
        _write_benchmark_manifest(
            second, [{"name": "Provo", "language": "en", "monitor": [1600, 900]}]
        )
        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(first))

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("PoTeC")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # Repoint at the other bundle: "PoTeC — harmonised…" is now a label for
        # a corpus that isn't there.
        dir_input = next(t for t in at.text_input if t.key == "eyegenbench_dir")
        dir_input.set_value(str(second)).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["data_source_choice"] == app.benchmark_corpus_label(
            "Provo"
        )
        text_ms = next(m for m in at.multiselect if m.key == "filter_text_id")
        assert set(text_ms.options) == {"Provo_a", "Provo_b"}

    def test_benchmark_reader_count_matches_the_headless_loader(
        self, monkeypatch, tmp_path
    ):
        """DATA-27 R32 — the headline regression pin.

        A benchmark corpus' loader returns *raw, pre-normalization* frames per the
        registry contract, and `prepare_data` then auto-detects a schema for them
        with `data.py`'s candidate lists — `eyegenbench.load_eyegenbench` (the
        headless API/CLI path) instead uses the explicit `EYEGENBENCH_FIX_SCHEMA`.
        Before R32 those two paths disagreed on three fields
        (`participant`/`fixation_id`/`word_id`), and with `participant`
        unresolved every reader collapsed into one synthetic id — so the *same
        bundle* loaded as N readers headlessly but just 1 in the app, with no
        error anywhere to say so.
        """
        from scanpath_studio import app, eyegenbench

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "bundle"
        readers = ["r1", "r2", "r3"]
        _write_benchmark_corpus(root, "BSC", readers=readers, paragraphs=("p1", "p2"))
        _write_benchmark_manifest(
            root, [{"name": "BSC", "language": "zh", "monitor": [1024, 768]}]
        )

        # Headless path: eyegenbench.load_eyegenbench uses EYEGENBENCH_FIX_SCHEMA
        # directly, so this is the ground truth the app must match.
        _, headless_fixations = eyegenbench.load_eyegenbench(root, dataset="BSC")
        headless_reader_count = headless_fixations["participant_id"].nunique()
        assert headless_reader_count == 3

        monkeypatch.setattr(app, "EYEGENBENCH_DEFAULT_DIR", str(root))
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.benchmark_corpus_label("BSC")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # `render_narrow_by` only renders the Participant multiselect when it
        # would offer more than one choice (`controls.py`: `if len(parts) >
        # 1`) — so a widget lookup that assumes it always renders would raise
        # `IndexError` on the very failure this test exists to catch, instead
        # of reporting it. Absent means "the app resolved exactly 1 reader".
        participant_matches = [
            m for m in at.multiselect if m.key == "filter_participants"
        ]
        if participant_matches:
            app_reader_count = len(participant_matches[0].options)
            app_readers = set(participant_matches[0].options)
        else:
            app_reader_count = 1
            app_readers = None
        assert app_reader_count == headless_reader_count, (
            f"app auto-detected {app_reader_count} reader(s) but the headless "
            f"loader (the ground-truth explicit schema) resolves {headless_reader_count} "
            "— the app's auto-detection disagrees with EYEGENBENCH_FIX_SCHEMA"
        )
        assert app_readers == set(readers)

    def test_switching_public_dataset_sources_still_clears_filters(self, monkeypatch):
        """R31 pin: ordinary cross-source switching (not within one EyeGenBench
        source) must behave exactly as before the fix — a filter set under one
        registry corpus does not survive a switch to a different one."""
        import pandas as pd

        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        words = pd.DataFrame(
            {
                "trial_id": ["t1", "t1"],
                "text_id": ["t1", "t1"],
                "word_idx": [0, 1],
                "word": ["a", "b"],
                "left": [100.0, 140.0],
                "right": [140.0, 180.0],
                "top": [50.0, 50.0],
                "bottom": [80.0, 80.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "t1", "t1"],
                "x": [110.0, 150.0, 110.0, 150.0],
                "y": [60.0, 60.0, 60.0, 60.0],
                "duration": [200.0, 180.0, 200.0, 180.0],
                "word_idx": [0, 1, 0, 1],
            }
        )
        potec_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k)
        mpe_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "MultiplEYE" in k)
        for key in (potec_key, mpe_key):
            monkeypatch.setitem(
                app.PUBLIC_DATASET_REGISTRY[key],
                "loader",
                lambda *_slots: (words, fixations),
            )

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
        at.session_state["public_dataset_choice"] = potec_key
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        part = next(m for m in at.multiselect if m.key == "filter_participants")
        part.set_value(["p1"])
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["filter_participants"] == ["p1"]

        # Mirrors a real click on the flat source picker: `data_source_choice`
        # carries the concrete registry label directly (DATA-9), not
        # `PUBLIC_DATASETS_CHOICE` — that constant only appears pre-healing, on
        # a legacy/first-ever selection, which the first run above already
        # resolved away. Leaving it unset here would let `resolve_data_source`'s
        # healing step re-publish the *old* `public_dataset_choice` from the
        # stale `data_source_choice`, masking the switch entirely.
        at.session_state["data_source_choice"] = mpe_key
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["public_dataset_choice"] == mpe_key
        assert at.session_state["filter_participants"] == []

    def test_public_dataset_canvas_snaps_to_its_monitor(self, monkeypatch):
        """Selecting a public dataset snaps the canvas to its registered monitor,
        even when a previous source left a stale canvas in session state.

        Regression: ``setdefault`` let a returning session keep an old canvas, so
        a corpus' monitor update (e.g. MultiplEYE → 1920x1080) never showed and the
        scanpath rendered off-scale."""
        import pandas as pd

        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        words = pd.DataFrame(
            {
                "trial_id": ["Lit_X_1__page_01", "Lit_X_1__page_01"],
                "text_id": ["Lit_X_1", "Lit_X_1"],
                "word_idx": [0, 1],
                "word": ["a", "b"],
                "left": [100.0, 140.0],
                "right": [140.0, 180.0],
                "top": [50.0, 50.0],
                "bottom": [80.0, 80.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["001_ZH_CH_1_ET1"] * 2,
                "trial_id": ["Lit_X_1__page_01"] * 2,
                "location_x": [110.0, 150.0],
                "location_y": [60.0, 60.0],
                "duration": [200.0, 180.0],
                "onset": [0.0, 200.0],
                "word_idx": [0, 1],
            }
        )
        mpe_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "MultiplEYE" in k)
        monkeypatch.setitem(
            app.PUBLIC_DATASET_REGISTRY[mpe_key],
            "loader",
            # Loaders take (options_host, location_host) DATA-9 sub-slots now.
            lambda *_slots: (words, fixations),
        )
        monitor = app.PUBLIC_DATASET_REGISTRY[mpe_key]["monitor"]

        at = _make_apptest()
        # Simulate a returning session: a stale canvas seeded by a *different* source.
        at.session_state["global_canvas_width"] = 1310
        at.session_state["global_canvas_height"] = 991
        at.session_state["_canvas_seeded_for"] = (app.PUBLIC_DATASETS_CHOICE, "other")
        at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
        at.session_state["public_dataset_choice"] = mpe_key
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert (
            at.session_state["global_canvas_width"],
            at.session_state["global_canvas_height"],
        ) == monitor

    def test_switching_public_datasets_re_proposes_mapping(self, monkeypatch):
        """Switching PoTeC → MultiplEYE must re-propose each corpus' mapping.

        Regression: the `col_map_*` widget keys persisted across the source
        switch, so PoTeC's Trial → `text_id` stuck to MultiplEYE (which also has a
        `text_id` column, so the stale-column reset didn't catch it). MultiplEYE's
        per-page `trial_id` was then ignored and every page collapsed into one
        stimulus-level trial."""
        import pandas as pd

        from scanpath_studio import app

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        # PoTeC-shaped frames: trial == text_id (so its auto-mapping picks text_id).
        potec_w = pd.DataFrame(
            {
                "aoi": [1, 2],
                "start_x": [80.0, 115.0],
                "start_y": [21.0, 21.0],
                "end_x": [115.0, 189.0],
                "end_y": [99.0, 99.0],
                "word": ["Um", "null"],
                "text_id": ["b0", "b0"],
                "line": [1, 1],
            }
        )
        potec_f = pd.DataFrame(
            {
                "reader_id": [0, 0],
                "text_id": ["b0", "b0"],
                "fixation_duration": [210, 190],
                "fixation_index": [1, 2],
                "word_index_in_text": [1, 2],
                "x": [97.5, 152.0],
                "y": [60.0, 60.0],
            }
        )
        # MultiplEYE-shaped frames: trial is the per-page id; text_id is the stimulus.
        mpe_w = pd.DataFrame(
            {
                "trial_id": ["X__page_01", "X__page_02"],
                "text_id": ["X", "X"],
                "word_idx": [0, 0],
                "word": ["a", "b"],
                "left": [100.0, 100.0],
                "right": [140.0, 140.0],
                "top": [50.0, 50.0],
                "bottom": [80.0, 80.0],
            }
        )
        mpe_f = pd.DataFrame(
            {
                "participant_id": ["001_ZH_CH_1_ET1"] * 2,
                "trial_id": ["X__page_01", "X__page_02"],
                "text_id": ["X", "X"],
                "location_x": [110.0, 110.0],
                "location_y": [60.0, 60.0],
                "duration": [200.0, 180.0],
                "onset": [0.0, 200.0],
                "word_idx": [0, 0],
            }
        )
        potec_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k)
        mpe_key = next(k for k in app.PUBLIC_DATASET_REGISTRY if "MultiplEYE" in k)
        monkeypatch.setitem(
            app.PUBLIC_DATASET_REGISTRY[potec_key],
            "loader",
            lambda *_slots: (potec_w, potec_f),
        )
        monkeypatch.setitem(
            app.PUBLIC_DATASET_REGISTRY[mpe_key],
            "loader",
            lambda *_slots: (mpe_w, mpe_f),
        )

        at = _make_apptest()
        at.run(timeout=120)  # bundled demo
        # DATA-9: each corpus is a first-class entry in the flat picker — switch by
        # setting the corpus token directly (no separate Public/Dataset two-step).
        at.session_state["data_source_choice"] = potec_key
        at.run(timeout=120)  # PoTeC maps Trial → text_id
        at.session_state["data_source_choice"] = mpe_key
        at.run(timeout=120)  # switch to MultiplEYE

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The picker's label carries the active sort key (UX-10), so match the
        # stem rather than the whole string.
        picker = next(
            (s for s in at.selectbox if s.label.startswith("**Select Trial**")), None
        )
        opts = list(picker.options) if picker is not None else []
        # Two per-page trials, not collapsed into one stimulus-level trial.
        assert len(opts) == 2, f"expected 2 per-page trials, got {opts}"
        assert all("· page" in o for o in opts), opts


class TestGroupedUploadMapping:
    """Upload source: each table's mapping renders under its own upload box, and
    raw gaze is a first-class peer (its mapping panel is always available)."""

    def test_upload_renders_all_three_mapping_panels(self, monkeypatch):
        import pandas as pd

        from scanpath_studio import app

        # Inject the bundled raw frames through the per-table upload seam.
        sample_words, sample_fix = app.load_sample_data()
        sample_rg = app.load_sample_raw_gaze()
        frames = {
            "col_map_words": sample_words,
            "col_map_fix": sample_fix,
            "col_map_raw_gaze": sample_rg,
        }
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error: {[e.value for e in at.error]}"
        # Each table gets its own Participant picker (a multiselect);
        # raw gaze keeps its own participant mapping (a selectbox). All three
        # present tables get mapped.
        sel_keys = {s.key for s in at.selectbox}
        multi_keys = {m.key for m in at.multiselect}
        assert "col_map_fix_participant" in multi_keys
        assert "col_map_raw_gaze_participant" in sel_keys
        # The shared pick is mirrored into each present table's per-table key.
        assert "col_map_words_participant" in at.session_state
        assert "col_map_fix_participant" in at.session_state
        # Required per-table column mappings render too.
        assert "col_map_fix_duration" in sel_keys
        assert "col_map_words_word_id" in sel_keys

    def test_words_only_upload_renders(self, monkeypatch):
        # Single-report upload: only a Words/IA table — the missing fixations
        # side becomes a canonical empty frame and the app still renders.
        import pandas as pd

        from scanpath_studio import app

        sample_words, _ = app.load_sample_data()
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                sample_words
                if kw["state_prefix"] == "col_map_words"
                else pd.DataFrame()
            ),
        )

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error: {[e.value for e in at.error]}"
        sel_keys = {s.key for s in at.selectbox}
        multi_keys = {m.key for m in at.multiselect}
        # The Words/IA mapping renders (its Participant multiselect + the word
        # column mapping); the (un-uploaded) Fixations table gets no mapping, and
        # the app got past mapping (no unmapped-view warning).
        assert "col_map_words_participant" in multi_keys
        assert "col_map_words_word_id" in sel_keys
        assert "col_map_fix_duration" not in sel_keys
        assert "col_map_fix_participant" not in at.session_state
        warnings = " ".join(w.value for w in at.warning)
        assert "Finish the column mapping" not in warnings

    def test_raw_gaze_only_renders(self, monkeypatch):
        # A raw-gaze-only dataset (no words, no fixations) must load and render
        # the gaze instead of falling back to the demo or halting on "no data".
        import pandas as pd

        from scanpath_studio import app

        sample_rg = app.load_sample_raw_gaze()
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                sample_rg
                if kw["state_prefix"] == "col_map_raw_gaze"
                else pd.DataFrame()
            ),
        )

        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["setup_complete"] = True  # past the setup wizard
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error: {[e.value for e in at.error]}"
        keys = {s.key for s in at.selectbox}
        # Raw-gaze mapping rendered; words/fixations did not; and the app neither
        # halted on "no data" nor fell back to the demo.
        assert "col_map_raw_gaze_participant" in keys
        assert "col_map_words_participant" not in keys
        warnings = " ".join(w.value for w in at.warning)
        assert "No data after filtering" not in warnings
        # The raw-gaze overlay is defaulted on so the Interactive Plot isn't blank.
        assert at.session_state["global_show_raw_gaze"] is True


def _box_mapping_script():
    """Render only the Words/IA column-mapping panel for an edges-format table,
    stashing the resulting mapping in session_state for assertions."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import WORD_FIELD_SPECS, column_mapping_ui
    from scanpath_studio.data import propose_word_schema

    df = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "IA_ID": [1],
            "IA_LEFT": [100],
            "IA_RIGHT": [150],
            "IA_TOP": [50],
            "IA_BOTTOM": [100],
        }
    )
    st.session_state["_box_mapping"] = column_mapping_ui(
        df,
        table_label="Words/IA",
        state_key_prefix="col_map_words",
        field_specs=WORD_FIELD_SPECS,
        proposed=propose_word_schema(df),
    )


class TestColumnMappingBoxWidget:
    """The Words/IA box mapping shows one coordinate-format radio + 4 fields, yet
    still returns all eight box keys (the inactive four set to None)."""

    def test_edges_default_and_full_mapping(self):
        from scanpath_studio.controls import BOX_FORMAT_EDGES

        at = AppTest.from_function(_box_mapping_script).run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        box_radios = [r for r in at.radio if r.key == "col_map_words_box_format"]
        assert box_radios, "box-format radio not rendered"
        assert box_radios[0].value == BOX_FORMAT_EDGES

        mapping = at.session_state["_box_mapping"]
        assert mapping["left"] == "IA_LEFT"
        assert mapping["right"] == "IA_RIGHT"
        assert mapping["top"] == "IA_TOP"
        assert mapping["bottom"] == "IA_BOTTOM"
        assert mapping["x"] is None and mapping["y"] is None
        assert mapping["width"] is None and mapping["height"] is None

    def test_switching_to_origin_drops_edge_columns(self):
        from scanpath_studio.controls import BOX_FORMAT_ORIGIN

        at = AppTest.from_function(_box_mapping_script).run(timeout=30)
        box_radio = next(r for r in at.radio if r.key == "col_map_words_box_format")
        box_radio.set_value(BOX_FORMAT_ORIGIN)
        at.run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        mapping = at.session_state["_box_mapping"]
        # Origin fields are now the active four (None here — this table has no
        # x/y/w/h columns); the edge keys are no longer mapped.
        assert mapping["left"] is None and mapping["right"] is None
        assert mapping["top"] is None and mapping["bottom"] is None


@pytest.mark.timeout(90)
class TestWelcomeTour:
    """Dialog-style tour (TOUR_STYLE="dialog"): opens once per session,
    navigates, and stays out of the way of embeds / deep links."""

    @staticmethod
    def _tour_buttons(at):
        return {b.key for b in at.button if b.key and b.key.startswith("tour_")}

    @pytest.fixture(autouse=True)
    def _dialog_style(self, monkeypatch):
        from scanpath_studio import tour

        monkeypatch.setattr(tour, "TOUR_STYLE", "dialog")

    def test_tour_opens_on_first_run_only(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert at.session_state["tour_seen"] is True
        assert "tour_next" in self._tour_buttons(at)
        # Any later full rerun must NOT reopen the dialog (e.g. after the
        # user dismissed it with X) — only the replay button may.
        at.run(timeout=30)
        assert "tour_next" not in self._tour_buttons(at)

    def test_tour_next_advances_step(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.button(key="tour_next").click()
        at.run(timeout=30)
        assert at.session_state["tour_step"] == 1
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

    def test_tour_suppressed_for_embed_and_deep_link(self):
        # AppTest can't inject query params into st.query_params, so the
        # suppression predicate is tested directly (it takes a mapping).
        from scanpath_studio.tour import tour_suppressed

        assert tour_suppressed({"embed": "true"})
        assert tour_suppressed({"embed": "1"})
        assert tour_suppressed({"participant": "l37_1129"})
        assert tour_suppressed({"source": "onestop"})
        assert tour_suppressed({"trial": "3"})
        assert tour_suppressed({"tab": "animation"})
        assert not tour_suppressed({})
        assert not tour_suppressed({"embed": "false"})

    def test_tour_replay_button_reopens(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)  # first run: auto-open, marks tour_seen
        at.run(timeout=30)  # second run: dialog gone
        at.session_state["tour_step"] = 3
        _replay_tour(at)
        assert "tour_next" in self._tour_buttons(at)
        assert at.session_state["tour_step"] == 0  # replay restarts the tour
        assert not at.exception, f"Streamlit exceptions: {at.exception}"


@pytest.mark.timeout(90)
class TestSpotlightTour:
    """Spotlight-style tour (the default): floating card + per-step highlight,
    armed once per session via tour_mode, dismissed by Exit/Done."""

    @staticmethod
    def _sp_buttons(at):
        return {b.key for b in at.button if b.key and b.key.startswith("tour_sp_")}

    def test_spotlight_arms_on_first_run(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert at.session_state["tour_seen"] is True
        assert at.session_state["tour_mode"] == "spotlight"
        assert "tour_sp_next" in self._sp_buttons(at)
        # The dialog style must NOT also open.
        assert not any(b.key == "tour_next" for b in at.button)
        # The welcome step renders centered with a dimmed backdrop.
        markdown = " ".join(m.value for m in at.markdown)
        assert "tour-backdrop" in markdown

    def test_spotlight_navigates_and_exits(self):
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.button(key="tour_sp_next").click()
        at.run(timeout=30)
        assert at.session_state["tour_step"] == 1
        # From step 2 on, the card drops to the corner: no backdrop.
        markdown = " ".join(m.value for m in at.markdown)
        assert "tour-backdrop" not in markdown
        at.button(key="tour_sp_close").click()
        at.run(timeout=30)
        assert at.session_state["tour_mode"] is None
        assert self._sp_buttons(at) == set(), "card must vanish after close"
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Step list sanity: every selector-bearing step targets a keyed
        # wrapper (.st-key-*) or a stable testid that exists in the app.
        selectors = [s["selector"] for s in _SPOTLIGHT_STEPS if s["selector"]]
        assert all(
            sel.startswith(".st-key-") or "data-testid" in sel for sel in selectors
        )

    def test_spotlight_done_on_last_step(self):
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.session_state["tour_step"] = len(_SPOTLIGHT_STEPS) - 1
        at.run(timeout=30)
        assert "tour_sp_done" in self._sp_buttons(at)
        at.button(key="tour_sp_done").click()
        at.run(timeout=30)
        assert at.session_state["tour_mode"] is None
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

    def test_spotlight_replay(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.button(key="tour_sp_close").click()
        at.run(timeout=30)
        assert self._sp_buttons(at) == set()
        _replay_tour(at)
        assert "tour_sp_next" in self._sp_buttons(at)
        assert at.session_state["tour_step"] == 0
        assert not at.exception, f"Streamlit exceptions: {at.exception}"


class TestSetupWizard:
    """The hybrid setup wizard for the Upload source."""

    @staticmethod
    def _inject(monkeypatch):
        import pandas as pd

        from scanpath_studio import app

        raw_words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2", "p2"],
                "trial_id": ["t1", "t1", "t1", "t1"],
                "word_id": [1, 2, 1, 2],
                "IA_LEFT": [0, 10, 0, 10],
                "IA_RIGHT": [10, 20, 10, 20],
                "IA_TOP": [0, 0, 0, 0],
                "IA_BOTTOM": [10, 10, 10, 10],
                "IA_LABEL": ["a", "b", "a", "b"],
                "difficulty_level": ["Adv", "Adv", "Ele", "Ele"],
                "junk_col": [9, 9, 9, 9],
            }
        )
        raw_fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t1", "t1"],
                "CURRENT_FIX_X": [5.0, 15.0, 5.0],
                "CURRENT_FIX_Y": [5.0, 5.0, 5.0],
                "CURRENT_FIX_DURATION": [100, 120, 90],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_words
                if kw["state_prefix"] == "col_map_words"
                else raw_fix
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        return app

    def test_add_data_button_enters_wizard(self):
        """Clicking '➕ Add data' from a built-in source opens the upload wizard.
        Regression: the handler must run in an on_click callback (Streamlit forbids
        reassigning a widget key inline), and the wizard state rides a plain
        ``_show_upload_wizard`` flag — NOT the data_source_choice radio key, which
        Streamlit garbage-collects while the radio isn't rendered (bouncing the
        user out of the wizard mid-edit, esp. for a composite trial id)."""
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        _enter_add_data(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["_show_upload_wizard"] is True
        assert at.session_state["setup_complete"] is False
        # The wizard owns the page: its sidebar Cancel button shows and the
        # normal data-source radio is gone.
        assert any(b.key == "cancel_add_data" for b in at.button)
        assert not any(r.key == "data_source_picker" for r in at.radio)

    def test_wizard_active_then_finalize_renders_tabs(self, monkeypatch):
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Wizard is active: the finalize button is shown and tabs are not yet up.
        assert any(b.key == "wizard_finalize" for b in at.button)
        assert "single_trial_id" not in {s.key for s in at.selectbox}

        # Finalizing reveals the visualization (collapsed Data & mapping panel +
        # the trial picker), and the kept columns are pruned.
        at.session_state["setup_complete"] = True
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert any(b.key == "wizard_reconfigure" for b in at.button)

    def test_wizard_prunes_unkept_columns(self, monkeypatch):
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Finalize with defaults (keep detected optional fields, drop unclaimed),
        # then confirm the stored frame is actually thinned.
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        words = at.session_state["_datasets"][at.session_state["data_source_choice"]][
            "words"
        ]
        # junk_col is unclaimed and not kept -> pruned; difficulty_level is a
        # detected condition kept by default -> survives.
        assert "junk_col" not in words.columns
        assert "difficulty_level" in words.columns

    def test_stored_dataset_remap_overwrites_in_place(self, monkeypatch):
        """A stored dataset's Column-mapping section is editable: remapping a
        field to a surviving column re-derives the frames and overwrites the
        entry in place, and the columns dropped at import are recorded for the
        note."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        name = at.session_state["data_source_choice"]
        entry = at.session_state["_datasets"][name]
        # The unmapped/unkept column is recorded as dropped (drives the note).
        assert "junk_col" in entry["dropped_columns"]["words"]
        # The remap form lives in the Data Inspection subtab, which since PERF-3
        # renders only when it is the open tab.
        pin_data_view(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The editable remap form renders for a stored dataset.
        assert any(b.key == f"remap_apply_{name}" for b in at.button)

        # Remap the word text to a surviving (kept) column and apply.
        text_key = f"remap_{name}_words_text"
        text_box = [s for s in at.selectbox if s.key == text_key]
        assert text_box, "word-text remap selectbox not rendered"
        text_box[0].set_value("difficulty_level")
        pin_data_view(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        apply_button = [b for b in at.button if b.key == f"remap_apply_{name}"]
        assert apply_button, "remap Apply button not rendered"
        apply_button[0].click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # The entry was overwritten in place: new schema + re-derived frame.
        entry = at.session_state["_datasets"][name]
        assert entry["schemas"]["words"]["text"] == "difficulty_level"
        assert list(entry["words"]["text"]) == ["Adv", "Adv", "Ele", "Ele"]

    def test_per_table_trial_pickers_and_setup_step(self, monkeypatch):
        """Group A + C: a Trial ID picker per table (UX-53 r13 dropped the
        unified picker and its toggle) and the inline Experimental Setup
        controls both render in the active wizard."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # One trial multiselect per present table, and no mode toggle guarding
        # them: naming the column in each table is one pick either way.
        ms_keys = {m.key for m in at.multiselect}
        assert "col_map_fix_trial" in ms_keys
        assert "col_map_words_trial" in ms_keys
        assert "col_map_trial_unified" not in ms_keys
        assert not [t for t in at.toggle if "per table" in (t.label or "")]
        # DATA-22: the recording setup is now step 4, *after* the upload, and
        # asks how each group is known instead of seeding a monitor. Nothing is
        # preselected — a wrong guess here silently rescales every figure.
        modes = {r.key: r.value for r in at.radio}
        assert set(_SETUP_MODE_KEYS.values()) <= set(modes)
        assert all(modes[k] is None for k in _SETUP_MODE_KEYS.values())

    def test_per_table_trial_toggle_reveals_per_table_pickers(self, monkeypatch):
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["wizard_trial_per_table"] = True
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        ms_keys = {m.key for m in at.multiselect}
        assert "col_map_fix_trial" in ms_keys
        assert "col_map_words_trial" in ms_keys

    def test_finalize_button_stores_named_dataset(self, monkeypatch):
        """Group B.4: clicking 'Use this dataset' persists the normalized frames
        under a name and switches the data source to it (no re-upload to switch)."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize, "finalize button not rendered for a valid mapping"
        finalize[0].click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        stored = at.session_state["_datasets"]
        assert stored, "no dataset was stored on finalize"
        name = at.session_state["data_source_choice"]
        assert name in stored
        # The stored entry holds the already-normalized frames, so switching to
        # it later needs no re-upload / re-mapping, and the source switched away
        # from Upload onto the new named dataset.
        assert not stored[name]["fixations"].empty
        assert not stored[name]["words"].empty
        assert name != app.UPLOAD_CHOICE
        assert at.session_state["setup_complete"] is True

    def test_redesigned_wizard_structure(self, monkeypatch):
        """UX-114: dataset name at the top, ONE per-table "fields to keep"
        picker directly under that table's own mapping (not a separate
        cross-table stage), and an 'Add dataset' button. difficulty_level (a
        detected meta condition) and junk_col (unclaimed) both live on the
        AOI/words table, so both are offered by its own keep picker."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Dataset name moved to the top.
        assert any(t.key == "wizard_dataset_name" for t in at.text_input)
        ms_keys = {m.key for m in at.multiselect if m.key}
        # One per-table keep picker (the old cross-table Filter/Keep pair is gone).
        assert "wizard_keep_col_map_words" in ms_keys
        assert "col_map_fix_optional" not in ms_keys
        assert "col_map_words_optional" not in ms_keys
        keep_ms = next(
            m for m in at.multiselect if m.key == "wizard_keep_col_map_words"
        )
        assert any("difficulty_level" in o for o in keep_ms.options)
        assert any("junk_col" in o for o in keep_ms.options)
        # The fixation extras / noise flag are no longer mapping selectboxes.
        sel_keys = {s.key for s in at.selectbox if s.key}
        for gone in ("col_map_fix_noise_flag", "col_map_fix_pass_index"):
            assert gone not in sel_keys
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize and "Add dataset" in finalize[0].label

    def test_finalize_selects_new_dataset_in_sidebar(self, monkeypatch):
        """Regression: after '➕ Add data' → 'Use this dataset', the new dataset
        must appear in the sidebar Data-source picker AND be the selected value.
        The real flow renders the picker first (on a built-in source), so the
        finalize switch must not be lost to the widget's frontend reconciliation."""
        self._inject(monkeypatch)
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        # Real flow: enter the wizard via the button (picker already rendered).
        _enter_add_data(at)
        at.run(timeout=60)
        # Entering the wizard resets its widgets, so the setup step must be
        # answered *after* that click, not before it.
        answer_setup_step(at)
        at.run(timeout=60)
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        name = at.session_state["data_source_choice"]
        assert name in at.session_state["_datasets"]
        # DATA-9: flat source selectbox; an uploaded dataset is tagged private
        # ("🔒 <name> (yours)") but its option token (and the value) is the name.
        pickers = [s for s in at.selectbox if s.key == "data_source_picker"]
        assert pickers, "data-source picker not rendered after finalize"
        assert pickers[0].value == name
        assert any(name in o for o in pickers[0].options), (
            name,
            list(pickers[0].options),
        )

    def test_stored_dataset_loads_full_app_without_wizard(self, monkeypatch):
        """Group B.4: selecting a stored dataset reloads the whole app from the
        persisted frames — no wizard, no re-upload — and renders the trial picker."""
        app = self._inject(monkeypatch)
        # First finalize a dataset to capture its persisted store entry.
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        stored = dict(at.session_state["_datasets"])
        name = at.session_state["data_source_choice"]

        # Fresh session: point straight at the stored dataset (no upload monkeypatch
        # needed — the stored branch never reads uploads).
        at2 = _make_apptest()
        at2.session_state["_datasets"] = stored
        at2.session_state["data_source_choice"] = name
        at2.run(timeout=60)
        assert not at2.exception, f"Streamlit exceptions: {at2.exception}"
        assert not any(b.key == "wizard_finalize" for b in at2.button)
        keys = {w.key for w in list(at2.selectbox) + list(at2.radio) if w.key}
        assert any(k.startswith("single") for k in keys), keys

    def test_differing_trial_counts_are_emphasized(self, monkeypatch):
        """Group C.1c: when the per-table trial coverage differs the wizard says so
        (an info note when the tables still overlap, not a single green count)."""
        import pandas as pd

        from scanpath_studio import app

        # Words cover t1,t2,t3; fixations only t1,t2 — overlapping but unequal.
        raw_words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "trial_id": ["t1", "t2", "t3"],
                "word_id": [1, 1, 1],
                "IA_LEFT": [0, 0, 0],
                "IA_RIGHT": [10, 10, 10],
                "IA_TOP": [0, 0, 0],
                "IA_BOTTOM": [10, 10, 10],
                "IA_LABEL": ["a", "b", "c"],
            }
        )
        raw_fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "CURRENT_FIX_X": [5.0, 5.0],
                "CURRENT_FIX_Y": [5.0, 5.0],
                "CURRENT_FIX_DURATION": [100, 120],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_words
                if kw["state_prefix"] == "col_map_words"
                else raw_fix
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # UX-67 r2: the count is a caption under each table's own picker, so
        # differing coverage reads as two different numbers side by side rather
        # than as a sentence about them in a banner.
        captions = [e.value for e in at.caption]
        assert any("3 trials" in c for c in captions), captions
        assert any("2 trials" in c for c in captions), captions

    def test_disjoint_trial_ids_warn(self, monkeypatch):
        """Group C.1c: when the tables share no trial ids at all (a likely mapping
        error), the wizard warns rather than just noting differing coverage."""
        import pandas as pd

        from scanpath_studio import app

        raw_words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["w1", "w2"],
                "word_id": [1, 1],
                "IA_LEFT": [0, 0],
                "IA_RIGHT": [10, 10],
                "IA_TOP": [0, 0],
                "IA_BOTTOM": [10, 10],
                "IA_LABEL": ["a", "b"],
            }
        )
        raw_fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["f1", "f2"],
                "CURRENT_FIX_X": [5.0, 5.0],
                "CURRENT_FIX_Y": [5.0, 5.0],
                "CURRENT_FIX_DURATION": [100, 120],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_words
                if kw["state_prefix"] == "col_map_words"
                else raw_fix
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        warn_text = " ".join(e.value for e in at.warning)
        assert "No trial ids are shared" in warn_text, warn_text

    def test_raw_gaze_only_incomplete_mapping_blocks_finalize(self, monkeypatch):
        """Bug fix: a raw-gaze-only upload with an unmappable trial id must block
        finalize (raw-gaze problems are folded in) instead of storing an empty
        dataset.

        UX-53 changed *how* it blocks, not whether: the button is now **enabled**
        while incomplete, because a disabled control cannot be pressed and the
        red required-field marking is triggered by the attempt. What must still
        hold — and is what this test is really about — is that pressing it stores
        nothing.
        """
        import pandas as pd

        from scanpath_studio import app, controls

        # No participant/trial/x/y the schema can auto-detect.
        raw_gaze = pd.DataFrame({"foo": [1, 2, 3], "bar": [4, 5, 6]})
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_gaze if kw["state_prefix"] == "col_map_raw_gaze" else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Finalize is shown and pressable; the blocking problem mentions raw gaze.
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize and not finalize[0].disabled
        # UX-88/UX-90: the page says nothing about what is missing until the
        # user tries — so on arrival there is no blocker text to find yet.
        assert not [e for e in at.error if "Raw gaze" in e.value]

        # The guarantee: pressing it stores no dataset, and the wizard stays up.
        finalize[0].click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # ...and pressing it explains itself. This blocker has no required
        # field on screen to turn red, so without this the button is a dead
        # end — press, nothing happens, nothing says why.
        err_text = " ".join(e.value for e in at.error)
        assert "Raw gaze" in err_text, err_text
        # AppTest's session_state is not a dict — no `.get()`.
        stored = (
            at.session_state["_datasets"] if "_datasets" in at.session_state else {}
        )
        assert not stored, stored
        assert at.session_state[controls.ADD_ATTEMPTED_KEY] is True
        assert [b for b in at.button if b.key == "wizard_finalize"]

    def test_composite_trial_dataset_restores_picker_on_switch_back(self, monkeypatch):
        """Regression for the review's HIGH finding: a stored dataset whose trial
        id is composite must restore _composite_trial_columns on reselect,
        overriding whatever source was loaded last. Since BUG-23 the flag no longer
        changes the *picker* (there is one picker for every mapping) — it is what
        lets the trial chips spell the joined id back out."""
        import pandas as pd

        from scanpath_studio import app

        # A participant- and a text-level id present → unified default composes
        # them (a composite trial id).
        raw_words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "paragraph_id": ["A", "A", "B"],
                "text_id": ["1", "1", "1"],
                "word_id": [1, 2, 1],
                "IA_LEFT": [0, 10, 0],
                "IA_RIGHT": [10, 20, 10],
                "IA_TOP": [0, 0, 0],
                "IA_BOTTOM": [10, 10, 10],
                "IA_LABEL": ["a", "b", "a"],
            }
        )
        raw_fix = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p1"],
                "paragraph_id": ["A", "A", "B"],
                "text_id": ["1", "1", "1"],
                "CURRENT_FIX_X": [5.0, 15.0, 5.0],
                "CURRENT_FIX_Y": [5.0, 5.0, 5.0],
                "CURRENT_FIX_DURATION": [100, 120, 90],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                raw_words
                if kw["state_prefix"] == "col_map_words"
                else raw_fix
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert set(at.session_state["_composite_trial_columns"]) == {
            "participant_id",
            "paragraph_id",
        }
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        stored = dict(at.session_state["_datasets"])
        name = at.session_state["data_source_choice"]
        assert set(stored[name]["composite_trial_columns"]) == {
            "participant_id",
            "paragraph_id",
        }

        # Fresh session with STALE composite state (as if Demo was loaded last).
        at2 = _make_apptest()
        at2.session_state["_datasets"] = stored
        at2.session_state["data_source_choice"] = name
        at2.session_state["_composite_trial_columns"] = None
        at2.run(timeout=60)
        assert not at2.exception, f"Streamlit exceptions: {at2.exception}"
        assert set(at2.session_state["_composite_trial_columns"]) == {
            "participant_id",
            "paragraph_id",
        }
        keys = {w.key for w in at2.selectbox if w.key}
        assert "single_trial_id" in keys, keys
        assert not any(k.startswith("single_composite_") for k in keys), keys

    def test_recording_setup_writes_shared_global_key(self, monkeypatch):
        """DATA-22: the Recording-setup step still feeds the shared ``global_*``
        keys the rest of the app reads — but only once the user has said *how*
        they know the screen. Answering "I know the resolution" reveals the
        width/height inputs, and the value they hold is published."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Before answering, the wizard publishes no canvas at all.
        assert not [n for n in at.number_input if n.key == "wizard_setup_screen_w"]

        at.session_state[_SETUP_MODE_KEYS["screen"]] = _SCREEN_KNOW
        at.run(timeout=60)
        width = [n for n in at.number_input if n.key == "wizard_setup_screen_w"]
        assert width, "'I know the resolution' did not reveal the width input"
        width[0].set_value(1999)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["global_canvas_width"] == 1999


@pytest.mark.timeout(120)
class TestCorpusAnalysisTab:
    """The 'Corpus Analysis' tab hosts the question-oriented analysis sections
    (Per text / Per reader / Groups). Generations moved to the Scanpath view's
    Comparisons subtab (ENG-8)."""

    def test_analysis_sections_render(self):
        # Demo source: several participants / trials / texts, so every section
        # has data. AppTest renders all st.tabs bodies, so one run exercises the
        # default view of each section.
        at = _make_apptest()
        at.session_state["main_nav"] = "Corpus Analysis"
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        keys = {s.key for s in at.selectbox}
        # The Groups tab defaults to a single group (compare toggle off), so its
        # single-group view selector (pgrp_view) is present; cmp_view appears only
        # when 'Compare a second group' is on (see test_each_analysis_view_renders).
        for view_key in ("ptext_view", "prdr_view", "pgrp_view"):
            assert view_key in keys, f"{view_key} view selector not found"
        # BUG-26: the Screen picker is offered only by a multipart corpus. The
        # demo has no `screen_id`, so it must not appear — and its absence is
        # what pins that every single-screen dataset is untouched by the fix.
        assert "ptext_screen" not in keys

    @pytest.mark.parametrize(
        ("view_key", "view"),
        [
            ("ptext_view", "Word × reader heatmap"),
            ("ptext_view", "Cohort profile"),
            ("ptext_view", "Word difficulty on stimulus"),
            ("ptext_view", "Measure vs feature"),
            ("ptext_view", "Skip / regression rate"),
            ("prdr_view", "Reading summary"),
            ("prdr_view", "Progressive vs regressive"),
            ("prdr_view", "Landing-position curve"),
            ("prdr_view", "Per-trial trend"),
            ("pgrp_view", "Word profile"),
            ("pgrp_view", "Reader summary table"),
            ("cmp_view", "Difference word profile"),
            ("cmp_view", "Paired summary bars"),
            ("cmp_view", "Effect size + test"),
            ("cmp_view", "Two-group word heatmap"),
        ],
    )
    def test_each_analysis_view_renders(self, view_key, view):
        # Drive each non-default analysis view and confirm it renders cleanly.
        at = _make_apptest()
        at.session_state["main_nav"] = "Corpus Analysis"
        # The two-group comparison views live behind the Groups 'Compare a second
        # group' toggle; the single-group views show with it off.
        at.session_state["groups_compare"] = view_key == "cmp_view"
        at.session_state[view_key] = view
        at.run(timeout=60)
        assert not at.exception, f"{view_key}={view!r}: {at.exception}"
        assert at.error == [], (
            f"{view_key}={view!r} st.error: {[e.value for e in at.error]}"
        )

    def test_group_filter_set_mode_renders(self):
        # The 'Independent filter sets' group-definition mode (the second of the
        # two modes the user asked for) must render for both the single-group
        # (compare off) and two-group (compare on) cases of the Groups tab.
        single = _make_apptest()
        single.session_state["main_nav"] = "Corpus Analysis"
        single.session_state["pgrp_mode"] = "Independent filter sets"
        single.run(timeout=60)
        assert not single.exception, f"Streamlit exceptions: {single.exception}"
        assert single.error == [], f"st.error: {[e.value for e in single.error]}"

        compare = _make_apptest()
        compare.session_state["main_nav"] = "Corpus Analysis"
        compare.session_state["groups_compare"] = True
        compare.session_state["cmp_mode"] = "Independent filter sets"
        compare.run(timeout=60)
        assert not compare.exception, f"Streamlit exceptions: {compare.exception}"
        assert compare.error == [], f"st.error: {[e.value for e in compare.error]}"


@pytest.mark.timeout(90)
class TestShareLinkCurrent:
    """The merged Share action always receives the current view."""

    def test_link_tracks_settings_without_a_second_refresh_button(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "_share_query_current" in at.session_state
        q1, _ = at.session_state["_share_query_current"]
        current = (
            at.session_state["global_show_words"]
            if "global_show_words" in at.session_state
            else True
        )
        at.session_state["global_show_words"] = not current
        at.run(timeout=30)
        q2, _ = at.session_state["_share_query_current"]
        assert q2 != q1, "Refresh & Copy must receive the current settings"
        assert not [button for button in at.button if button.key == "share_refresh"]
        assert not at.exception, f"Streamlit exceptions: {at.exception}"


@pytest.mark.timeout(120)
class TestNavRegressions:
    """Guards for the sidebar-nav + Trial-Selection-panel refactor."""

    def test_participant_filter_applies_same_run(self):
        # The Filter-trials controls live in the Scanpath tab now; changing one
        # must narrow the trial pool on the SAME rerun (regression: it used to lag
        # one rerun because the result was read from the previous run's stash).
        at = _make_apptest()  # bundled 3-participant demo
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        picker = [s for s in at.selectbox if s.key == "single_trial_id"]
        assert picker, "trial picker (single_trial_id) not found"
        n_before = len(picker[0].options)
        fp = [m for m in at.multiselect if m.key == "filter_participants"]
        assert fp, "participant filter not found"
        assert len(fp[0].options) > 1
        # Interact (fires on_change) — not a bare session_state set.
        fp[0].set_value([fp[0].options[0]]).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        picker2 = [s for s in at.selectbox if s.key == "single_trial_id"]
        assert picker2, "trial picker missing after filtering"
        n_after = len(picker2[0].options)
        assert n_after < n_before, (
            f"participant filter did not apply on the same run: {n_before} -> {n_after}"
        )

    def test_save_restore_present_on_every_view(self):
        # The Save & restore panel must be reachable on both top-level views
        # (regression: it only rendered on the Scanpath view after the nav
        # change). UX-100 moved it into the 💾 Session dialog, so the panel is
        # reached by arming that — from whichever view is active.
        from scanpath_studio import app

        for view in ("Scanpath Visualization", "Corpus Analysis"):
            at = _make_apptest(synthetic=True)
            at.session_state["main_nav"] = view
            at.session_state[app._SESSION_DIALOG_KEY] = True
            at.run(timeout=60)
            assert not at.exception, f"{view}: {at.exception}"
            # Anchor on the panel's widgets, not its prose (UX-53 trimmed the
            # copy): the config download + the restore uploader ARE the panel.
            assert [
                d for d in at.get("download_button") if d.key == "plot_config_download"
            ], f"Save & restore panel missing on the {view} view"
            assert [u for u in at.get("file_uploader") if u.key == "plot_config_upload"]


def _mpe_upload_frames():
    """A tiny MultiplEYE upload: scanpath rows (CamelCase filename) + char AOIs
    (lowercase filename), each row tagged with its source_file stem."""
    import pandas as pd

    scan = pd.DataFrame(
        {
            "onset": [1000, 1300, 2000],
            "duration": [200, 180, 210],
            "name": ["fixation"] * 3,
            "location_x": [90, 150, 90],
            "location_y": [65, 65, 65],
            "page": ["page_1", "page_1", "page_2"],
            "word_idx": [0, 1, 0],
        }
    )
    scan["source_file"] = "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath"

    def _chars(page, word_idx, word, x0):
        return [
            dict(
                char_idx=word_idx * 2 + i,
                char=word[i],
                top_left_x=x0 + i * 20,
                top_left_y=50,
                width=20,
                height=30,
                char_idx_in_line=word_idx * 2 + i,
                line_idx=0,
                page=page,
                word_idx=word_idx,
                word_idx_in_line=word_idx,
                word=word,
            )
            for i in range(2)
        ]

    aoi = pd.DataFrame(
        _chars("page_1", 0, "AA", 80)
        + _chars("page_1", 1, "BB", 140)
        + _chars("page_2", 0, "CC", 80)
    )
    aoi["source_file"] = "lit_demo_1_aoi"
    return scan, aoi


@pytest.mark.timeout(60)
class TestMultiplEYEUploadPreset:
    """Add-dataset → MultiplEYE format: filename-keyed browser upload."""

    def _seed_preset(self, at, app, monkeypatch, scan, aoi):
        import pandas as pd

        frames = {"mpe_fix": scan, "mpe_aoi": aoi}
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "MultiplEYE"

    def test_preset_bypasses_generic_mapping(self, monkeypatch):
        from scanpath_studio import app

        scan, aoi = _mpe_upload_frames()
        at = _make_apptest()
        self._seed_preset(at, app, monkeypatch, scan, aoi)
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error: {[e.value for e in at.error]}"
        # The preset assembled a finalize payload — with single-literal trial id
        # (no composite components) and MultiplEYE's filter facets.
        assert "_wizard_finalize_payload" in at.session_state
        payload = at.session_state["_wizard_finalize_payload"]
        assert payload["composite_trial_columns"] == []
        assert payload["filter_fields"] == ["genre", "session", "is_practice"]
        # One trial per stimulus with its pages as screens (DATA-24), CamelCase
        # stimulus (case-match worked), boxes joined.
        fixations = payload["fixations"]
        assert set(fixations["trial_id"]) == {"Lit_Demo_1"}
        assert set(fixations["screen_id"]) == {"page_1", "page_2"}
        assert not payload["words"].empty
        # The generic column-mapping widgets are NOT rendered in this format.
        sel_keys = {s.key for s in at.selectbox}
        assert "col_map_words_word_id" not in sel_keys
        assert "col_map_fix_duration" not in sel_keys

    def test_preset_finalize_stores_dataset(self, monkeypatch):
        from scanpath_studio import app

        scan, aoi = _mpe_upload_frames()
        at = _make_apptest()
        self._seed_preset(at, app, monkeypatch, scan, aoi)
        at.run(timeout=60)
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize, "Add dataset button missing"
        # Finalizing renders the complete app and may build the host's font cache;
        # use the same explicit budget as the initial preset render instead of
        # AppTest's three-second default.
        finalize[0].click().run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The dataset was stored and reselected — it renders without re-mapping.
        assert "_datasets" in at.session_state and at.session_state["_datasets"], (
            "dataset was not stored"
        )
        stored = next(iter(at.session_state["_datasets"].values()))
        assert not stored["fixations"].empty
        assert stored["composite_trial_columns"] == []

    def test_preset_unrecognized_filenames_blocks(self, monkeypatch):
        import pandas as pd

        from scanpath_studio import app

        bad = pd.DataFrame(
            {
                "onset": [1],
                "duration": [1],
                "location_x": [1.0],
                "location_y": [1.0],
                "page": ["page_1"],
                "word_idx": [0],
            }
        )
        bad["source_file"] = "not_a_multipleye_name"
        at = _make_apptest()
        self._seed_preset(at, app, monkeypatch, bad, pd.DataFrame())
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        errors = " ".join(e.value for e in at.error)
        assert "No MultiplEYE-shaped file names" in errors
        # No finalize payload when the upload couldn't be parsed.
        assert "_wizard_finalize_payload" not in at.session_state

    def test_preset_questions_and_participant_metadata(self, monkeypatch):
        import json

        import pandas as pd

        from scanpath_studio import app

        scan, aoi = _mpe_upload_frames()
        questions = pd.DataFrame(
            {
                "stimulus_name": ["Lit_Demo"],
                "stimulus_id": [1],
                "question": ["Why?"],
                "target": ["Because"],
                "condition_name": ["local"],
                "question_no": [1],
                "condition_no": [1],
            }
        )
        participant = pd.DataFrame(
            {"participant_id": [1], "session": ["ET1"], "age": [22], "gender": ["F"]}
        )
        frames = {
            "mpe_fix": scan,
            "mpe_aoi": aoi,
            "mpe_questions": questions,
            "mpe_participant": participant,
        }
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "MultiplEYE"
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        payload = at.session_state["_wizard_finalize_payload"]
        fixations = payload["fixations"]
        assert fixations["pp_age"].dropna().iloc[0] == 22
        assert fixations["pp_gender"].dropna().iloc[0] == "F"
        q = json.loads(fixations["comprehension_questions"].dropna().iloc[0])
        assert q[0]["target"] == "Because"


@pytest.mark.timeout(60)
class TestGenericFilenamePowers:
    """Generic wizard powers reusable beyond MultiplEYE: regex filename → columns
    and the character-AOI aggregation toggle."""

    def test_regex_derive_exposes_columns_and_aggregate_toggle(self, monkeypatch):
        import pandas as pd

        from scanpath_studio import app

        # A char-level words table + fixations, both keyed only by filename.
        words = pd.DataFrame(
            {
                "word_idx": [0, 0],
                "word": ["AA", "AA"],
                "top_left_x": [80, 100],
                "top_left_y": [50, 50],
                "width": [20, 20],
                "height": [30, 30],
                "page": ["page_1", "page_1"],
                "source_file": ["lit_demo_aoi", "lit_demo_aoi"],
            }
        )
        fix = pd.DataFrame(
            {
                "onset": [1, 2],
                "duration": [10, 10],
                "location_x": [1.0, 2.0],
                "location_y": [1.0, 1.0],
                "page": ["page_1", "page_1"],
                "source_file": ["p1_t1_scan", "p1_t1_scan"],
            }
        )
        frames = {"col_map_words": words, "col_map_fix": fix}
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: frames.get(kw["state_prefix"], pd.DataFrame()),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "Generic"
        # Enable filename derivation in regex mode.
        at.session_state["wizard_filename_split"] = True
        at.session_state["wizard_filename_mode"] = "Regex named groups"
        at.session_state["wizard_filename_regex"] = (
            r"(?P<pid>p\d+)_(?P<trial>t\d+)_scan"
        )
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # UX-113: nothing is derived — or offered to map below — until Apply.
        apply_btn = [b for b in at.button if b.key == "wizard_filename_apply"]
        assert apply_btn, "Apply button not rendered"
        apply_btn[0].click().run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The regex-extracted columns are offered to map as ids…
        trial_pick = [m for m in at.multiselect if m.key == "col_map_fix_trial"]
        assert trial_pick, "trial id multiselect not rendered"
        assert "trial" in trial_pick[0].options
        # …and the character-AOI aggregation toggle renders for the words table.
        assert "wizard_aggregate_char_boxes" in {t.key for t in at.toggle}

    def test_aggregate_toggle_finalizes_word_boxes(self, monkeypatch):
        # End-to-end: a char-level words upload + the aggregate toggle → the
        # stored dataset holds one box per word (4 char rows → 2 word boxes).
        import pandas as pd

        from scanpath_studio import app

        words = pd.DataFrame(
            {
                "trial_id": ["t"] * 4,
                "word_idx": [0, 0, 1, 1],
                "word": ["AA", "AA", "BB", "BB"],
                "top_left_x": [80, 100, 140, 160],
                "top_left_y": [50] * 4,
                "width": [20] * 4,
                "height": [30] * 4,
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                words if kw["state_prefix"] == "col_map_words" else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "Generic"
        at.session_state["wizard_aggregate_char_boxes"] = True
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize, "Add dataset button missing (mapping incomplete?)"
        finalize[0].click().run()

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "_datasets" in at.session_state and at.session_state["_datasets"]
        stored = next(iter(at.session_state["_datasets"].values()))
        assert len(stored["words"]) == 2  # aggregated from 4 char rows

    def test_aggregate_toggle_exposes_block_field_and_keeps_blocks_apart(
        self, monkeypatch
    ):
        # UX-113: a "block" column (e.g. a question's stem/target answer
        # blocks) each restarting word_idx at 0 must not collapse into one
        # box per shared word_idx once the "AOI block" field is mapped.
        import pandas as pd

        from scanpath_studio import app

        words = pd.DataFrame(
            {
                "trial_id": ["t"] * 8,
                "block": ["stem"] * 4 + ["target"] * 4,
                "word_idx": [0, 0, 1, 1] * 2,
                "word": ["AA", "AA", "BB", "BB", "CC", "CC", "DD", "DD"],
                "top_left_x": [80, 100, 140, 160] * 2,
                "top_left_y": [50] * 4 + [150] * 4,
                "width": [20] * 8,
                "height": [30] * 8,
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                words if kw["state_prefix"] == "col_map_words" else pd.DataFrame()
            ),
        )
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "Generic"
        at.session_state["wizard_aggregate_char_boxes"] = True
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The block field renders only while the aggregate toggle is on.
        block_pick = [s for s in at.selectbox if s.key == "col_map_words_block"]
        assert block_pick, "AOI block field not rendered"
        block_pick[0].select("block").run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize, "Add dataset button missing (mapping incomplete?)"
        finalize[0].click().run()

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "_datasets" in at.session_state and at.session_state["_datasets"]
        stored = next(iter(at.session_state["_datasets"].values()))
        # 4 distinct boxes survive (not 2 merged across blocks).
        assert len(stored["words"]) == 4


@pytest.mark.timeout(120)
class TestFigureAndCanvasSubGroups:
    """UX-48: the 📐 Figure & canvas group renders as four popover sub-groups.

    The controls moved *containers*, not keys — and every conditional body in
    the group (the title/caption pattern boxes, the manual grid interval, the
    colour-bar styling, the custom background picker) now sits one level deeper
    than before. Streamlit raises on a container it won't nest, so booting with
    all four bodies open is the regression that catches a bad move; the key
    assertions are what pin that no setting was dropped on the way.
    """

    def test_every_sub_group_body_renders_with_its_settings_intact(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        # Open the four conditional bodies at once.
        at.session_state["global_show_title_caption"] = True
        at.session_state["global_title_pattern"] = "{participant_id}"
        at.session_state["global_show_coordinate_grid"] = True
        at.session_state["global_coordinate_grid_auto"] = False
        at.session_state["global_show_colorbars"] = True
        at.session_state["global_bg_choice"] = "Custom…"
        at.run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Widgets from every sub-group: 🖥️ Screen, 🔤 Text, 📊 Axes, 🏷️ Labels.
        keys = {w.key for w in at.number_input} | {w.key for w in at.selectbox}
        assert {
            "global_canvas_width",
            "global_coordinate_grid_spacing",
            "global_bg_choice",
            "global_illustration_label",
            "global_x_field",
        } <= keys
        assert at.session_state["global_title_pattern"] == "{participant_id}"
        assert at.session_state["global_colorbar_orientation"] in (
            "Vertical",
            "Horizontal",
        )

    def test_the_group_keeps_its_named_blocks(self):
        """The shape itself: one disclosure, named blocks, nothing nested.

        UX-80 made the group a ``[name | ▾]`` row and its sub-popovers named
        blocks inside it; UX-81 moved the typography out to 📄 Stimulus → Text
        and dropped the physical-geometry controls, which the 🗂️ Data page's
        Recording setup owns. What this pins is that the group did not collapse
        back into the one flat ~26-row run UX-48 broke up.
        """
        import inspect

        from scanpath_studio import app, controls

        control_source = inspect.getsource(controls.render_plot_controls)
        canvas_source = inspect.getsource(app.render_canvas_controls)

        assert '_rail_subsection(figure_grp, "🖥️ Screen & framing")' in control_source
        assert '_rail_subsection(figure_grp, "📊 Axes & grid")' in control_source
        assert '_rail_subsection(figure_grp, "🏷️ Title & labels")' in control_source
        # The typography half is drawn into the Stimulus section instead.
        assert "text_host" in canvas_source
        assert '_rail_subsection(stim_grp, "🔤 Text")' not in control_source
        # The framing toggle leads the screen block.
        assert 'screen_group.toggle(\n        "**Show full monitor**"' in control_source
        # …and the old flat captions are gone.
        assert 'figure_grp.caption("**Canvas & text**")' not in control_source
        assert 'figure_grp.caption("**Axes & labels**")' not in control_source

    def test_text_can_be_switched_off_without_crashing_the_figure_controls(self):
        """BUG-38: Figure & canvas must not render into a missing Text slot."""
        at = _make_apptest(synthetic=True)
        at.session_state["global_show_labels"] = False
        at.run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["global_show_labels"] is False


@pytest.mark.timeout(120)
class TestResetSettings:
    """UX-26: the rail's Reset settings action puts the visualization back."""

    def test_reset_visualization_restores_defaults(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        # Tweak two viz settings away from their defaults (one layer toggle, one
        # value control), then reset.
        at.session_state["global_show_words"] = True
        at.session_state["global_saccade_width"] = 7.5
        at.run(timeout=30)
        assert at.session_state["global_show_words"] is True

        reset = [b for b in at.button if b.key == "reset_viz_settings_btn"]
        assert reset, "Reset visualization button not rendered"
        at = reset[0].click().run(timeout=30)

        # BUG-36: the click now only opens a confirmation dialog; the reset
        # itself happens on the confirm click, one run later.
        confirm = [b for b in at.button if b.key == "reset_viz_confirm"]
        assert confirm, "Reset confirmation button not rendered"
        assert confirm[0].label == "♻️ Reset it"
        at = confirm[0].click().run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Re-seeded from controls._VIZ_WIDGET_DEFAULTS, not left deleted.
        assert at.session_state["global_show_words"] is False
        assert (
            at.session_state["global_saccade_width"]
            == controls._VIZ_WIDGET_DEFAULTS["global_saccade_width"]
        )

    def test_reset_visualization_keeps_trial_filters(self):
        """Scope check: filters are cleared from their own panel, not from here."""
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.session_state["filter_participants"] = ["nobody"]
        at.run(timeout=30)

        reset = [b for b in at.button if b.key == "reset_viz_settings_btn"]
        assert reset, "Reset visualization button not rendered"
        at = reset[0].click().run(timeout=30)

        # BUG-36: click through the confirmation to actually reset.
        confirm = [b for b in at.button if b.key == "reset_viz_confirm"]
        assert confirm, "Reset confirmation button not rendered"
        at = confirm[0].click().run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["filter_participants"] == ["nobody"]

    def test_clear_all_filters_button_clears_them(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        at.session_state["filter_participants"] = ["nobody"]
        at.run(timeout=30)

        clear = [b for b in at.button if b.key == "clear_all_filters_panel"]
        assert clear, "Clear all filters button not rendered"
        clear[0].click().run(timeout=30)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Either dropped outright or re-seeded empty — both mean "no constraint".
        assert not (
            "filter_participants" in at.session_state
            and at.session_state["filter_participants"]
        )


class TestFingerprintMemoIsPerRun:
    """PERF-3: the cache-key memo must be reset at the top of every script run.

    The memo makes the same frame *object* hash once instead of ~26 times, which
    is safe only because its lifetime is one run: `app.main` clears it before
    anything fingerprints a frame, so a frame rebuilt (or, in principle, mutated)
    between runs is hashed afresh rather than remembered. Losing that call is
    silent — the app keeps working and starts serving pre-change results — so it
    is pinned here rather than left to the one-line call site.
    """

    def test_every_run_resets_the_memo(self, monkeypatch):
        import scanpath_studio.app as app_module
        from scanpath_studio.data import reset_fingerprint_memo

        calls = []

        def counted() -> None:
            calls.append(1)
            reset_fingerprint_memo()

        monkeypatch.setattr(app_module, "reset_fingerprint_memo", counted)
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert len(calls) == 1
        at.run(timeout=30)
        assert len(calls) == 2
        assert not at.exception, f"Streamlit exceptions: {at.exception}"


class TestOpenTrialFromCorpusTable:
    """ENG-36: a per-trial row in Corpus Analysis can open that trial.

    The click arrives as a *callback*, before `main` rebuilds the trial pool, so
    it cannot seed the picker itself — `url_state.request_trial` parks it and
    `_apply_pending_trial_selection` applies it once `combos` exists (the same
    hop a `?trial_id=` deep link takes). This pins the whole hop, since the two
    halves live in different modules and neither is meaningful alone.
    """

    def test_a_parked_request_lands_on_the_trial_and_the_scanpath_view(self):
        from scanpath_studio.url_state import PENDING_TRIAL_KEY

        at = _make_apptest()
        at.run(timeout=60)
        booted_on = at.session_state["single_trial_id"]
        assert booted_on, "no trial selected on boot"

        # Park a request for some *other* trial, exactly as the button's callback
        # does, while sitting on the view the button lives on.
        at.session_state["main_nav"] = "Corpus Analysis"
        at.run(timeout=60)

        target = "l7_1090_2_1_1_Ele_r0"
        assert target != booted_on
        at.session_state[PENDING_TRIAL_KEY] = {
            "participant_id": None,
            "trial_id": target,
        }
        at.session_state["main_nav"] = "Scanpath Visualization"
        at.run(timeout=60)

        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.session_state["single_trial_id"] == target
        # Consumed once it lands, so it can't re-apply over later navigation.
        assert PENDING_TRIAL_KEY not in at.session_state


class TestLazySubtabBodiesStillRender:
    """ENG-37 — the four on-demand panels are exercised, not just gated.

    PERF-3 made Comparisons / Line assignment / Export / Data Inspection render
    only when open, which is right for latency but took ~460 lines of `tabs.py`
    out of every `AppTest` boot. `TestLazySubtabs` above pins the *gating*; these
    open each panel on the bundled demo and drive it far enough that its body
    actually runs — the two heaviest (the ten-algorithm drift grid and the
    same-text generations comparison) are otherwise never executed by any test.

    On the bundled demo rather than the synthetic trial: Comparisons needs a
    column that can distinguish several readings of one text, and the drift
    algorithms need more than two text lines to have anything to assign.
    """

    def test_line_assignment_grid_renders_every_algorithm(self):
        from scanpath_studio.alignment import ALGORITHMS

        at = _make_apptest()
        at.run(timeout=120)
        at.session_state[SUBTAB_KEY] = SUBTAB_LINE_ASSIGNMENT
        at.run(timeout=120)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        # The 11 true-scale figures sit behind a toggle — the panel is expensive
        # even when open, so it doesn't draw until asked. Set it through session
        # state rather than `.set_value().run()`: driving a widget makes the tab
        # bar (itself a widget) fall back to its default, closing the very panel
        # under test, so the subtab has to be re-pinned on the same run anyway.
        grid = [t for t in at.toggle if "grid" in (t.label or "").lower()]
        assert grid, "the comparison-grid toggle should render"
        at.session_state["align_grid_show"] = True
        at.session_state[SUBTAB_KEY] = SUBTAB_LINE_ASSIGNMENT
        at.run(timeout=300)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The panels are Plotly figures embedded as HTML, which AppTest cannot
        # see into — so assert on the two things around them that only exist once
        # the grid body has run: the per-panel layout control, and the
        # sensitivity report, which is computed from real corrections.
        assert [s for s in at.slider if s.key == "align_grid_ncols"]
        reported = [
            df
            for df in (d.value for d in at.dataframe)
            if getattr(df, "columns", None) is not None
            and "average_y_correction" in df.columns
        ]
        assert reported, "the drift sensitivity report should render"
        assert not reported[0].empty
        # Every algorithm is named in the citations list the panel opens with.
        cited = " ".join(m.value for m in at.markdown).lower()
        assert not [a for a in ALGORITHMS if a not in cited]

    def test_comparisons_shows_trials_matching_the_selected_field(self):
        at = _make_apptest()
        at.run(timeout=120)
        at.session_state[SUBTAB_KEY] = SUBTAB_COMPARISONS
        at.run(timeout=300)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        picker = [s for s in at.selectbox if s.key == "multi_gen_col"]
        assert picker, "the comparison-column picker should render"
        text = " ".join(m.value for m in at.markdown)
        assert "Matching trials" in text
        assert "Selected scanpath" not in text

    def test_export_and_data_inspection_bodies_run(self):
        at = _make_apptest()
        at.run(timeout=120)
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT
        at.run(timeout=120)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert [r for r in at.radio if r.key == "bulk_export_scope"]

        pin_data_view(at)
        at.run(timeout=120)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        headings = " ".join(s.value for s in at.subheader)
        assert "What's in the" in headings or at.dataframe


class TestAnimationExportRasterBranch:
    """ENG-37 — the GIF/MP4 export panel, which no test reached before.

    `_render_animation_export` returns early for HTML, so ~100 lines — the
    Chrome pre-flight, the resolution and frame-cap controls, the render-time
    estimate, and the cache that keeps the download button alive across reruns —
    only run once a rasterized format is picked *and* the Export subtab is still
    open on that same run.
    """

    def _panel(self, at, fmt="GIF"):
        at.session_state["single_animate"] = True
        at.session_state["anim_export_format"] = fmt
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT
        return at.run(timeout=60)

    def test_it_warns_before_a_render_that_can_only_fail(self, monkeypatch):
        """ENG-10's pre-flight: no Chrome, no raster export — say so up front."""
        from scanpath_studio import tabs as tabs_module

        monkeypatch.setattr(tabs_module, "chrome_available", lambda: False)
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        self._panel(at)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        warnings = " ".join(w.value for w in at.warning)
        assert "GIF export can't run here" in warnings
        # …and it still offers the controls, so the warning is advice, not a wall.
        assert [s for s in at.select_slider if s.key == "anim_export_scale"]

    def test_a_render_failure_is_reported_rather_than_raised(self, monkeypatch):
        """A Kaleido failure must surface as an app message, not a traceback."""
        from scanpath_studio import tabs as tabs_module
        from scanpath_studio.animation_export import AnimationExportError

        monkeypatch.setattr(tabs_module, "chrome_available", lambda: True)

        def _boom(*a, **k):
            raise AnimationExportError("no browser here")

        monkeypatch.setattr(tabs_module, "export_animation", _boom)
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        self._panel(at, fmt="MP4")
        render = [b for b in at.button if b.key == "anim_export_generate"]
        assert render, "the Render button should be offered"
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT
        render[0].click().run(timeout=120)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        said = " ".join(w.value for w in at.warning) + " ".join(
            e.value for e in at.error
        )
        assert "no browser here" in said or "MP4" in said


class TestPendingTrialRequestDoesNotLinger:
    """ENG-36 — a request the pool has answered "no" must not fire later.

    `_apply_pending_trial_selection` holds a request over while `combos` is
    *empty* (still loading), because dropping it there would lose the click. Once
    the pool exists the answer is final either way: leaving an unmatched request
    parked would silently re-point the trial picker the moment an unrelated
    filter change happened to bring that trial into scope.
    """

    def test_an_unanswerable_request_survives_an_empty_pool(self):
        def _app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.url_state import (
                PENDING_TRIAL_KEY,
                _apply_pending_trial_selection,
            )

            st.session_state[PENDING_TRIAL_KEY] = {
                "participant_id": None,
                "trial_id": "nope",
            }
            _apply_pending_trial_selection(pd.DataFrame())
            st.write("kept")

        from scanpath_studio.url_state import PENDING_TRIAL_KEY

        at = AppTest.from_function(_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state[PENDING_TRIAL_KEY]["trial_id"] == "nope"

    def test_a_populated_pool_clears_the_request_even_when_it_misses(self):
        def _app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.url_state import (
                PENDING_TRIAL_KEY,
                _apply_pending_trial_selection,
            )

            st.session_state[PENDING_TRIAL_KEY] = {
                "participant_id": None,
                "trial_id": "nope",
            }
            combos = pd.DataFrame(
                {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["x"]}
            )
            _apply_pending_trial_selection(combos)
            st.write(PENDING_TRIAL_KEY in st.session_state)

        from scanpath_studio.url_state import PENDING_TRIAL_KEY

        at = AppTest.from_function(_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert PENDING_TRIAL_KEY not in at.session_state


@pytest.mark.timeout(180)
class TestRecordingSetupGate(TestSetupWizard):
    """DATA-22 §3: **Add dataset** is blocked until all three setup groups say
    how they are known.

    The gate is deliberately hard — there is no "decide later" escape — but it
    can never strand anyone: *Estimate from my data* always exists for the screen
    group and always succeeds. What it buys is that no uploaded dataset can
    silently inherit a monitor, viewing distance or font nobody chose.
    """

    def test_finalize_is_disabled_until_every_group_is_answered(self, monkeypatch):
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize, "the finalize button should render (disabled), not vanish"
        assert finalize[0].disabled, "Add dataset must be gated on the setup step"

        # Answering two of three is still not enough.
        at.session_state[_SETUP_MODE_KEYS["screen"]] = _SCREEN_KNOW
        at.session_state[_SETUP_MODE_KEYS["text"]] = "Use a default (16 px)"
        at.run(timeout=60)
        assert next(b for b in at.button if b.key == "wizard_finalize").disabled

        answer_setup_step(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert not next(b for b in at.button if b.key == "wizard_finalize").disabled

    def test_the_answers_ride_into_the_stored_dataset(self, monkeypatch):
        """The provenance travels with the dataset, not just the wizard — that is
        what lets a reader downstream tell an assumed monitor from a measured
        one."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.run(timeout=60)
        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        entry = at.session_state["_datasets"][at.session_state["data_source_choice"]]
        setup = entry["setup"]
        assert setup["provenance"] == {
            "screen": "assumed",
            "geometry": "assumed",
            "text": "assumed",
        }
        # A stored upload now records geometry at all — it recorded none before
        # CMP-8 §1, which is why switching to one left the canvas on the previous
        # source's monitor.
        assert setup["canvas_width"] == 2560

    def test_estimate_from_my_data_is_always_available_and_succeeds(self, monkeypatch):
        """The escape hatch that keeps the hard gate humane."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state[_SETUP_MODE_KEYS["screen"]] = "Estimate from my data"
        at.session_state[_SETUP_MODE_KEYS["geometry"]] = (
            "Skip — I don't need visual-angle units"
        )
        at.session_state[_SETUP_MODE_KEYS["text"]] = "Use a default (16 px)"
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert not next(b for b in at.button if b.key == "wizard_finalize").disabled

        next(b for b in at.button if b.key == "wizard_finalize").click()
        at.run(timeout=60)
        entry = at.session_state["_datasets"][at.session_state["data_source_choice"]]
        assert entry["setup"]["provenance"]["screen"] == "estimated"
        assert entry["setup"]["provenance"]["geometry"] == "skipped"
        # A skipped geometry group must not leave a derived number behind.
        from scanpath_studio.experimental_setup import SetupSnapshot

        assert SetupSnapshot.from_dict(entry["setup"]).px_per_degree is None
