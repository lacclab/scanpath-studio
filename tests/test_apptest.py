"""Streamlit AppTest integration: spin up the app and assert key surfaces render.

Companion file: ``tests/test_apptest_flows.py`` (ENG-4) drives multi-step
*flows* through the same harness — overriding a column mapping and checking the
re-derived data, narrowing the trial pool with the condition/annotation filters
(incl. the UX-7 empty state), and building the bulk-export zip from the Export
subtab. Add render-level checks here; add "change a control, assert the next
render" checks there.
"""

from __future__ import annotations

import pytest

from scanpath_studio import controls
from tests.conftest import (
    APP_SCRIPT,
    SUBTAB_DATA_INSPECTION,
    SUBTAB_EXPORT,
    SUBTAB_KEY,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


SYNTHETIC_SOURCE = "Synthetic test trial"


def _make_apptest(*, synthetic: bool = False) -> "AppTest":
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


@pytest.mark.timeout(60)
class TestAppLaunches:
    def test_app_launches_with_bundled_demo(self):
        # The bundled demo must boot the full five-tab UI cleanly: no Python
        # exceptions and no st.error surfaced on the default render.
        at = _make_apptest()
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

    def test_title_present(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        titles = [t.value for t in at.title]
        assert any("Scanpath Studio" in v for v in titles)

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
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"

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
        # The "Trials to include" scope radio always offers both "All" (every
        # trial, ignoring the sidebar filter) first and "All filtered trials"
        # (the current sidebar selection) second.
        at = _make_apptest()  # bundled 3-pid demo
        at.session_state[SUBTAB_KEY] = SUBTAB_EXPORT  # PERF-3: open it to load it
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        scope_radios = [r for r in at.radio if r.key == "bulk_export_scope"]
        assert scope_radios, "bulk-export scope radio missing"
        assert scope_radios[0].options[:2] == ["All", "All filtered trials"], (
            f"unexpected scope options: {scope_radios[0].options}"
        )

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
        part = [m for m in at.multiselect if m.key == "filter_participants"][0]
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
        trial_box = [s for s in at.selectbox if s.key == "single_trial_id"][0]
        total = len(trial_box.options)
        text_ms[0].set_value([text_ms[0].options[0]])
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        narrowed = len(
            [s for s in at.selectbox if s.key == "single_trial_id"][0].options
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
    """The merged Data Inspection tab folds the former Raw Data + Data Statistics
    tabs into one: headline counts, raw tables, the summary-stats table, and the
    new column-mapping table — while dropping the second stats row, the fixation
    histogram, and the per-word measure section."""

    def test_merged_sections_present_and_old_removed(self):
        at = _make_apptest(synthetic=True)
        at.session_state[SUBTAB_KEY] = SUBTAB_DATA_INSPECTION
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        subheaders = [s.value for s in at.subheader]
        for section in (
            "Dataset statistics",
            "Raw data",
            "Summary statistics",
            "Column mapping",
        ):
            assert section in subheaders, f"missing section {section}: {subheaders}"

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
        assert any("computed after filtering" in c.value for c in at.caption)

    def test_column_mapping_table_renders(self):
        at = _make_apptest(synthetic=True)
        at.session_state[SUBTAB_KEY] = SUBTAB_DATA_INSPECTION
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        mapping_tables = [
            df.value
            for df in at.dataframe
            if list(getattr(df.value, "columns", []))
            == ["Table", "Field", "Mapped column"]
        ]
        assert mapping_tables, "column-mapping table not rendered"
        table = mapping_tables[0]
        assert not table.empty
        # Every mapped row names a real source field.
        assert (table["Mapped column"].astype(str).str.len() > 0).all()

    def test_top_level_nav_views(self):
        # Top-level navigation is now a header button toggling the two views
        # (Scanpath ⇄ Corpus Analysis) — not a sidebar radio. Data Inspection and
        # Share moved to subtabs of the Scanpath view.
        at = _make_apptest(synthetic=True)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # No main_nav radio anymore.
        assert not [r for r in at.radio if r.key == "main_nav"], (
            "top-level nav should no longer be a radio"
        )
        # On the Scanpath page, the header offers the Corpus Analysis toggle.
        btn_keys = {b.key for b in at.button if b.key}
        assert "nav_to_corpus" in btn_keys, "Corpus Analysis header button missing"

        # Switching to Corpus shows the back-to-Scanpath toggle instead.
        at2 = _make_apptest(synthetic=True)
        at2.session_state["main_nav"] = "Corpus Analysis"
        at2.run(timeout=60)
        assert not at2.exception, f"Streamlit exceptions: {at2.exception}"
        btn_keys2 = {b.key for b in at2.button if b.key}
        assert "nav_to_scanpath" in btn_keys2, "back-to-Scanpath header button missing"


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
        at.session_state[SUBTAB_KEY] = SUBTAB_DATA_INSPECTION
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
        shorts = [
            app.PUBLIC_DATASET_REGISTRY[k]["short"] for k in app.PUBLIC_DATASET_REGISTRY
        ]
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
        shorts = [
            app.PUBLIC_DATASET_REGISTRY[k]["short"] for k in app.PUBLIC_DATASET_REGISTRY
        ]
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
        source = [s for s in at.selectbox if s.key == "data_source_picker"][0]
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
        ):
            monkeypatch.setattr(app, const, str(tmp_path / const.lower()))
        for label in app.PUBLIC_DATASET_REGISTRY:
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
            k for k in app.PUBLIC_DATASET_REGISTRY if "PoTeC" in k
        )
        at.run(timeout=60)
        assert any("Download" in b.label for b in at.button), (
            "expected a Download button"
        )

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
        # Words + fixations share one unified Participant picker (a multiselect);
        # raw gaze keeps its own participant mapping (a selectbox). All three
        # present tables get mapped.
        sel_keys = {s.key for s in at.selectbox}
        multi_keys = {m.key for m in at.multiselect}
        assert "col_map_participant_unified" in multi_keys
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
        # The Words/IA mapping renders (unified Participant multiselect + the word
        # column mapping); the (un-uploaded) Fixations table gets no mapping, and
        # the app got past mapping (no unmapped-view warning).
        assert "col_map_participant_unified" in multi_keys
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
        box_radio = [r for r in at.radio if r.key == "col_map_words_box_format"][0]
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
        at.button(key="tour_replay").click()
        at.run(timeout=30)
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
        at.button(key="tour_replay").click()
        at.run(timeout=30)
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
        add = [b for b in at.button if b.key == "add_data_btn"]
        assert add, "Add data button not rendered"
        add[0].click()
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
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Finalize with defaults (keep detected optional fields, drop unclaimed),
        # then confirm the stored frame is actually thinned.
        [b for b in at.button if b.key == "wizard_finalize"][0].click()
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
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        [b for b in at.button if b.key == "wizard_finalize"][0].click()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

        name = at.session_state["data_source_choice"]
        entry = at.session_state["_datasets"][name]
        # The unmapped/unkept column is recorded as dropped (drives the note).
        assert "junk_col" in entry["dropped_columns"]["words"]
        # The remap form lives in the Data Inspection subtab, which since PERF-3
        # renders only when it is the open tab.
        at.session_state[SUBTAB_KEY] = SUBTAB_DATA_INSPECTION
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The editable remap form renders for a stored dataset.
        assert any(b.key == f"remap_apply_{name}" for b in at.button)

        # Remap the word text to a surviving (kept) column and apply.
        text_key = f"remap_{name}_words_text"
        text_box = [s for s in at.selectbox if s.key == text_key]
        assert text_box, "word-text remap selectbox not rendered"
        text_box[0].set_value("difficulty_level")
        at.session_state[SUBTAB_KEY] = SUBTAB_DATA_INSPECTION
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

    def test_unified_trial_picker_and_setup_step(self, monkeypatch):
        """Group A + C: one shared Trial ID picker (not per-table) and the
        inline Experimental Setup controls both render in the active wizard."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # The unified trial multiselect is rendered; per-table trial widgets are
        # not (single shared mapping by default).
        ms_keys = {m.key for m in at.multiselect}
        assert "col_map_trial_unified" in ms_keys
        assert "col_map_fix_trial" not in ms_keys
        assert "col_map_words_trial" not in ms_keys
        # Per-table override toggle is offered (both tables present).
        assert any(t.key == "wizard_trial_per_table" for t in at.toggle)
        # Display calibration moved into the loading flow.
        assert any(n.key == "global_canvas_width" for n in at.number_input)

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
        """The redesigned wizard: dataset name at the top, ONE cross-table Filter
        picker + ONE Keep picker (not duplicated per table), and an 'Add dataset'
        button. difficulty_level → Filter trials by; junk_col → keep extras."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Dataset name moved to the top.
        assert any(t.key == "wizard_dataset_name" for t in at.text_input)
        ms_keys = {m.key for m in at.multiselect if m.key}
        # One cross-table Filter + one Keep picker (the old per-table keys are gone).
        assert "wizard_filter_by" in ms_keys
        assert "wizard_keep_extra" in ms_keys
        assert "col_map_fix_optional" not in ms_keys
        assert "col_map_words_optional" not in ms_keys
        filter_ms = next(m for m in at.multiselect if m.key == "wizard_filter_by")
        assert any("difficulty_level" in o for o in filter_ms.options)
        keep_ms = next(m for m in at.multiselect if m.key == "wizard_keep_extra")
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
        [b for b in at.button if b.key == "add_data_btn"][0].click()
        at.run(timeout=60)
        [b for b in at.button if b.key == "wizard_finalize"][0].click()
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
        at.run(timeout=60)
        [b for b in at.button if b.key == "wizard_finalize"][0].click()
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
        info_text = " ".join(e.value for e in at.info)
        assert "Trial coverage differs" in info_text, info_text

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
        dataset."""
        import pandas as pd

        from scanpath_studio import app

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
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Finalize is shown but disabled; the blocking problem mentions raw gaze.
        finalize = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize and finalize[0].disabled
        warn_text = " ".join(e.value for e in at.warning)
        assert "Raw gaze" in warn_text, warn_text

    def test_composite_trial_dataset_restores_picker_on_switch_back(self, monkeypatch):
        """Regression for the review's HIGH finding: a stored dataset whose trial
        id is composite must restore _composite_trial_columns (and its cascading
        picker) on reselect, overriding whatever source was loaded last."""
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
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert set(at.session_state["_composite_trial_columns"]) == {
            "participant_id",
            "paragraph_id",
        }
        [b for b in at.button if b.key == "wizard_finalize"][0].click()
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
        assert any(k.startswith("single_composite_") for k in keys), keys

    def test_experimental_setup_control_writes_shared_global_key(self, monkeypatch):
        """Group A: the Display & experiment setup controls live inside the wizard
        and write the shared global_* keys the sidebar later reads."""
        app = self._inject(monkeypatch)
        at = _make_apptest()
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        width = [n for n in at.number_input if n.key == "global_canvas_width"]
        assert width, "Experimental Setup monitor-width control not in the wizard"
        width[0].set_value(1999)
        at.run(timeout=60)
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
class TestShareLinkLazy:
    """The Share link builds lazily — frozen until the user presses Refresh."""

    def test_link_frozen_until_refresh(self):
        at = _make_apptest(synthetic=True)
        at.run(timeout=30)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        # Built once on first render so there's always something to copy.
        assert "_share_query_frozen" in at.session_state
        q1, _ = at.session_state["_share_query_frozen"]
        # Flip a viz control WITHOUT pressing Refresh — the link must not change.
        current = (
            at.session_state["global_show_words"]
            if "global_show_words" in at.session_state
            else True
        )
        at.session_state["global_show_words"] = not current
        at.run(timeout=30)
        q2, _ = at.session_state["_share_query_frozen"]
        assert q2 == q1, "link must not rebuild without Refresh"
        # Press Refresh — now the link reflects the new setting.
        at.button(key="share_refresh").click()
        at.run(timeout=30)
        q3, _ = at.session_state["_share_query_frozen"]
        assert q3 != q1, "Refresh must rebuild the link from current settings"
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
        # The Save & restore sidebar panel must be reachable on both top-level
        # views (regression: it only rendered on the Scanpath view after the nav
        # change). Data Inspection is now a subtab of the Scanpath view.
        for view in ("Scanpath Visualization", "Corpus Analysis"):
            at = _make_apptest(synthetic=True)
            at.session_state["main_nav"] = view
            at.run(timeout=60)
            assert not at.exception, f"{view}: {at.exception}"
            captions = " ".join(c.value for c in at.caption)
            assert "Save the full plot configuration" in captions, (
                f"Save & restore panel missing on the {view} view"
            )


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
        # Per-page trials, CamelCase stimulus (case-match worked), boxes joined.
        fixations = payload["fixations"]
        assert set(fixations["trial_id"]) == {
            "Lit_Demo_1__page_01",
            "Lit_Demo_1__page_02",
        }
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
        # The regex-extracted columns are offered to map as ids…
        trial_pick = [m for m in at.multiselect if m.key == "col_map_trial_unified"]
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
        reset[0].click().run(timeout=30)

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
        reset[0].click().run(timeout=30)

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

    def test_a_request_for_an_absent_trial_is_kept_rather_than_dropped(self):
        """A pool that is empty or still loading must not swallow the request."""

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
            st.write(bool(st.session_state.get(PENDING_TRIAL_KEY)))

        from scanpath_studio.url_state import PENDING_TRIAL_KEY

        at = AppTest.from_function(_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state[PENDING_TRIAL_KEY]["trial_id"] == "nope"
