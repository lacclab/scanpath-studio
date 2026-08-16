"""Restoring an uploaded plot config seeds the visualization widgets' state.

Exercises ``app._restore_plot_config`` / ``_apply_uploaded_plot_config`` — the
inverse of the config written by ``tabs._render_plot_config_expander`` — covering
the round-trip mapping, data-dependent validation, clamping, and tolerance of a
hand-edited / malformed upload (it should skip bad fields, never crash).
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


# AppTest execs each app function as a standalone script, so anything it needs
# (the fixtures frame below) must be built inline — module-level helpers aren't
# in scope. x/y/duration_ms/pass_index are numeric (axis + color-by options);
# trial_id doubles as unique_trial_id so the none/Trial selection branch runs.
_FIX_COLUMNS = {
    "participant_id": ["p1", "p1", "p2"],
    "trial_id": ["t1", "t2", "t1"],
    "unique_trial_id": ["t1", "t2", "t1"],
    "paragraph_id": ["pA", "pB", "pA"],
    "x": [1.0, 2.0, 3.0],
    "y": [4.0, 5.0, 6.0],
    "duration_ms": [100, 200, 300],
    "pass_index": [1, 1, 2],
}


def _restore_app():
    """Run ``_restore_plot_config`` over the fixed dataset + the seeded config."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _restore_plot_config
    from scanpath_studio.utils import build_combo_options

    fixations = pd.DataFrame(st.session_state["_fix"])
    combos, _, _ = build_combo_options(fixations)
    applied, skipped = _restore_plot_config(
        st.session_state["_config"], combos, fixations
    )
    st.session_state["_applied"] = applied
    st.session_state["_skipped"] = skipped


def _apply_app():
    """Drive ``_apply_uploaded_plot_config`` through a fake uploaded file."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import _apply_uploaded_plot_config
    from scanpath_studio.utils import build_combo_options

    class _FakeUpload:
        def __init__(self, data: bytes):
            self._data = data
            self.name = "cfg.json"
            self.size = len(data)

        def getvalue(self) -> bytes:
            return self._data

    fixations = pd.DataFrame(st.session_state["_fix"])
    combos, _, _ = build_combo_options(fixations)
    st.session_state["plot_config_upload"] = _FakeUpload(st.session_state["_bytes"])
    _apply_uploaded_plot_config(combos, fixations)


def _run(app, **state):
    at = AppTest.from_function(app)
    at.session_state["_fix"] = _FIX_COLUMNS
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=20)
    assert not at.exception, at.exception
    return at


def _full_config() -> dict:
    """A config in the shape ``tabs._render_plot_config_expander`` writes."""
    return {
        "selection": {"participant_id": "p1", "trial_id": "t2"},
        "canvas_px": {"width": 1920, "height": 1080},
        "axes": {"x_field": "x", "y_field": "y"},
        "layers": {
            "words": False,
            "word_labels": True,
            "fixations": True,
            "order_labels": False,
            "saccades": True,
            "saccade_arrows": True,
            "heatmap": False,
            "raw_gaze": False,
            "stimulus_image": True,
            "autoplay": False,
        },
        "coloring": {
            "color_by": "pass_index",
            "heatmap_metric": "counts",
            "heatmap_style": "Interpolated",
            "show_colorbars": True,
            "fixation_range": [150.0, 250.0],
            "heatmap_range": [120.0, 280.0],
            "fixation_colorscale": "Viridis",
            "heatmap_colorscale": "Plasma",
        },
        "sizing": {
            "marker_size_range": [10, 30],
            "order_font_size": 40,
            "order_font_color": "#aa0000",
            "base_font_size": 28,
        },
    }


@pytest.mark.timeout(60)
class TestPlotConfigRestore:
    def test_round_trip_sets_all_widget_state(self):
        ss = _run(_restore_app, _config=_full_config()).session_state
        # layers
        assert ss["global_show_words"] is False
        assert ss["global_show_heatmap"] is False
        assert ss["global_show_saccade_arrows"] is True
        assert ss["global_show_order"] is False
        assert ss["global_show_stimulus_image"] is True  # round-trips like raw_gaze
        assert ss["global_anim_autoplay"] is False  # VIZ-10 autoplay round-trips
        # coloring
        assert ss["global_heatmap_style"] == "Interpolated"
        assert ss["global_color_by"] == "pass_index"
        assert ss["global_heatmap_metric"] == "counts"
        assert ss["global_show_colorbars"] is True
        assert ss["global_fixation_colorscale"] == "Viridis"
        assert ss["global_heatmap_colorscale"] == "Plasma"
        assert ss["global_fixation_color_range"] == (150.0, 250.0)
        assert ss["global_heatmap_color_range"] == (120.0, 280.0)
        # sizing
        assert ss["global_marker_size_range"] == (10, 30)
        assert ss["global_order_font_size"] == 40
        assert ss["global_order_font_color"] == "#aa0000"
        assert ss["global_base_font_size"] == 28
        # canvas / axes
        assert ss["global_canvas_width"] == 1920
        assert ss["global_canvas_height"] == 1080
        assert ss["global_x_field"] == "x"
        assert ss["global_y_field"] == "y"
        # selection (none/Trial mode → single_trial_id holds the option value)
        assert ss["single_select_trial_mode"] == "Trial"
        assert ss["single_trial_id"] == "t2"
        assert ss["_skipped"] == []

    def test_restores_and_translates_column_mapping(self):
        config = _full_config()
        config["column_mapping"] = {
            "col_map_fix_x": "CURRENT_FIX_X",
            "col_map_words_paragraph": "unique_paragraph_id",  # legacy key
            "col_map_words_upload": "ignored.csv",  # uploader widget — must skip
        }
        ss = _run(_restore_app, _config=config).session_state
        assert ss["col_map_fix_x"] == "CURRENT_FIX_X"
        # A legacy *_paragraph key is translated to the current *_text_id key.
        assert ss["col_map_words_text_id"] == "unique_paragraph_id"
        assert "col_map_words_paragraph" not in ss
        # Uploader-widget keys are never seeded (not JSON-restorable state).
        assert "col_map_words_upload" not in ss

    def test_restores_text_highlighting_and_annotations(self):
        # The merged "Save & restore" config (schema 2) also carries text
        # sizing, highlighting, and annotations — all re-applied on restore.
        config = dict(_full_config())
        config["schema"] = 2
        config["coloring"] = dict(
            config["coloring"],
            color_by="line",  # synthetic opt
            heatmap_norm="Log",
            stimulus_image_opacity=0.4,
            stimulus_image_offset_x=25.0,
            stimulus_image_offset_y=-40.0,
            stimulus_image_scale=1.5,
            saccade_render_mode="Arc",
            fixation_snap_to_word=True,
            saccade_style="Dashed",
            saccade_width=4.0,
            saccade_color_mode="By type",
            saccade_type_legend=False,
            saccade_class_colors={"regression": "#010203"},
            hollow_fixations=True,
            colorbar_orientation="Horizontal",
            colorbar_tickangle=45,
            colorbar_tickfont_size=14,
        )
        config["text"] = {
            "scale_text_to_boxes": False,
            "line_spacing": 2.5,
            "font_family": "Courier New",
            "text_color": "#010203",
        }
        config["highlighting"] = {
            "critical_span_style": "Mark border",
            "fixation_flags": {
                "short": {
                    "mode": "Discard",
                    "threshold_ms": 70,
                    "symbol": "triangle-up-open",
                    "color": "#ff7f0e",
                },
                "long": {
                    "mode": "Off",
                    "threshold_ms": 900,
                    "symbol": "square-open",
                    "color": "#9467bd",
                },
                "oob": {"mode": "Highlight", "symbol": "star", "color": "#d62728"},
            },
            "highlight_text_color": "#fedcba",
            "background_color": "#222222",
            "span_border_color": "#0a0b0c",
        }
        config["compare"] = [
            {
                "fix_color": "#111111",
                "saccade_color": "#222222",
                "saccade_style": "Dotted",
                "saccade_width": 3.5,
                "marker_size_range": [6, 18],
                "hollow": True,
            },
            {
                "fix_color": "#333333",
                "saccade_color": "#444444",
                "saccade_style": "Solid",
                "saccade_width": 1.5,
                "marker_size_range": [9, 21],
                "hollow": False,
            },
        ]
        config["annotations"] = [
            {
                "participant_id": "p1",
                "trial_id": "t2",
                "star": True,
                "tags": ["Review"],
                "note": "hi",
            }
        ]
        ss = _run(_restore_app, _config=config).session_state
        assert ss["global_color_by"] == "line"  # "line" is a valid option now
        assert ss["global_heatmap_norm"] == "Log"
        assert ss["global_scale_text_to_boxes"] is False
        assert ss["global_line_spacing"] == 2.5
        assert ss["global_font_family"] == "Courier New"
        assert ss["global_critical_span_style"] == "Mark border"
        assert ss["global_fixclass_oob_mode"] == "Highlight"
        assert ss["global_fixclass_short_mode"] == "Discard"
        assert ss["global_fixclass_short_threshold_ms"] == 70
        assert ss["global_saccade_style"] == "Dashed"
        assert ss["global_saccade_width"] == 4.0
        assert ss["global_saccade_render_mode"] == "Arc"
        assert ss["global_fixation_snap_to_word"] is True
        assert ss["global_stimulus_image_opacity"] == 0.4
        assert ss["global_stimulus_image_offset_x"] == 25.0
        assert ss["global_stimulus_image_offset_y"] == -40.0
        assert ss["global_stimulus_image_scale"] == 1.5
        assert ss["global_saccade_color_mode"] == "By type"
        assert ss["global_saccade_type_legend"] is False
        assert ss["global_saccade_class_color_regression"] == "#010203"
        assert ss["global_hollow_fixations"] is True
        assert ss["global_text_color"] == "#010203"
        assert ss["global_highlight_text_color"] == "#fedcba"
        assert ss["global_bg_choice"] == "Custom…"
        assert ss["global_bg_custom"] == "#222222"
        # BATCH A settings round-trip.
        assert ss["global_colorbar_orientation"] == "Horizontal"
        assert ss["global_colorbar_tickangle"] == 45
        assert ss["global_colorbar_tickfont_size"] == 14
        assert ss["global_fixclass_oob_symbol"] == "star"
        assert ss["global_span_border_color"] == "#0a0b0c"
        # Per-scanpath comparison styling round-trips (raw widget values).
        assert ss["cmp0_fix_color"] == "#111111"
        assert ss["cmp0_saccade_color"] == "#222222"
        assert ss["cmp0_saccade_style"] == "Dotted"
        assert ss["cmp0_saccade_width"] == 3.5
        assert ss["cmp0_marker_size_range"] == (6, 18)
        assert ss["cmp0_hollow"] is True
        assert ss["cmp1_fix_color"] == "#333333"
        assert ss["cmp1_saccade_style"] == "Solid"
        assert ss["cmp1_saccade_width"] == 1.5
        assert ss["cmp1_hollow"] is False
        store = ss["trial_annotations"]
        assert ("p1", "t2") in store
        assert store[("p1", "t2")]["star"] is True
        assert store[("p1", "t2")]["tags"] == ["Review"]

    def test_invalid_fields_are_skipped_not_applied(self):
        config = {
            "coloring": {"color_by": "does_not_exist", "heatmap_style": "Bogus"},
            "axes": {"x_field": "nope", "y_field": "y"},
            "selection": {"participant_id": "p9", "trial_id": "missing"},
        }
        ss = _run(_restore_app, _config=config).session_state
        assert "global_color_by" not in ss
        assert "global_heatmap_style" not in ss
        assert "global_x_field" not in ss
        assert ss["global_y_field"] == "y"  # the valid one still applies
        skipped = ss["_skipped"]
        for label in (
            "color-by field",
            "heatmap style",
            "X axis field",
            "trial selection",
        ):
            assert label in skipped

    def test_numeric_values_are_clamped_to_widget_bounds(self):
        config = {
            "canvas_px": {"width": 99999, "height": 1},
            "sizing": {"marker_size_range": [1, 99], "base_font_size": 999},
        }
        ss = _run(_restore_app, _config=config).session_state
        assert ss["global_canvas_width"] == 10000
        assert ss["global_canvas_height"] == 100
        assert ss["global_marker_size_range"] == (4, 40)
        assert ss["global_base_font_size"] == 72

    def test_malformed_numeric_fields_skipped_without_crashing(self):
        # Guards the bug where int("abc") / int(None) raised and surfaced a
        # Streamlit error page instead of skipping the field.
        config = {
            "layers": {"words": False},
            "coloring": {"heatmap_style": "Interpolated", "fixation_range": ["lo", 9]},
            "canvas_px": {"width": "abc", "height": None},
            "sizing": {"base_font_size": "huge", "marker_size_range": ["x", 30]},
        }
        ss = _run(_restore_app, _config=config).session_state  # must not raise
        # good fields still applied
        assert ss["global_show_words"] is False
        assert ss["global_heatmap_style"] == "Interpolated"
        # malformed numerics skipped, not applied
        for key in (
            "global_canvas_width",
            "global_canvas_height",
            "global_base_font_size",
            "global_marker_size_range",
            "global_fixation_color_range",
        ):
            assert key not in ss
        for label in (
            "canvas width",
            "canvas height",
            "figure font size",
            "marker size range",
            "fixation color range",
        ):
            assert label in ss["_skipped"]

    def test_malformed_sections_are_tolerated(self):
        # Sections of the wrong type must coerce to empty, not crash.
        config = {
            "layers": "nope",
            "coloring": [1, 2],
            "sizing": 5,
            "canvas_px": None,
            "axes": "x",
            "selection": [],
        }
        ss = _run(_restore_app, _config=config).session_state  # must not raise
        assert ss["_applied"] == 0


@pytest.mark.timeout(60)
class TestApplyUploadedPlotConfig:
    def test_valid_upload_applies_and_records_skips(self):
        import json

        data = json.dumps(
            {"layers": {"heatmap": False}, "axes": {"x_field": "bogus"}}
        ).encode("utf-8")
        ss = _run(_apply_app, _bytes=data).session_state
        assert ss["global_show_heatmap"] is False
        assert ss["_plot_config_skipped"] == ["X axis field"]

    def test_malformed_json_does_not_crash(self):
        ss = _run(_apply_app, _bytes=b"{not valid json").session_state
        # nothing applied, no widget state written, no exception
        assert "global_show_heatmap" not in ss

    def test_non_object_json_does_not_crash(self):
        ss = _run(_apply_app, _bytes=b"[1, 2, 3]").session_state
        assert "global_show_heatmap" not in ss


def test_build_studio_config_includes_provenance_and_round_trips():
    """The Save & restore config builder records provenance (app version, data
    source, column mapping) + annotations and is JSON-serializable."""
    import json

    import pandas as pd

    from scanpath_studio.tabs import _build_studio_config

    figure_settings = {
        "show_words": True,
        "show_word_labels": True,
        "show_fixations": True,
        "show_order": False,
        "show_saccades": True,
        "show_saccade_arrows": True,
        "show_heatmap": False,
        "show_raw_gaze": False,
        "color_by": "line",
        "heatmap_style": "Word boxes",
        "heatmap_norm": "Log",
        "show_colorbars": False,
        "fixation_color_range": None,
        "heatmap_range": None,
        "fixation_colorscale": "Blues",
        "heatmap_colorscale": "Oranges",
        "marker_size_range": (8, 24),
        "order_font_size": 14,
        "order_font_color": "#111111",
        "scale_text_to_boxes": True,
        "line_spacing": 3.0,
        "critical_span_style": "Mark border",
        "fixation_flags": {
            "short": {"mode": "Off", "threshold_ms": 80},
            "long": {"mode": "Off", "threshold_ms": 800},
            "oob": {"mode": "Highlight", "symbol": "star", "color": "#d62728"},
        },
        "highlight_text_color": "#fedcba",
        "background_color": "#222222",
        "text_color": "#010203",
        "saccade_color": "#6f42c1",
        "span_border_color": "#0a0b0c",
        "colorbar_orientation": "Horizontal",
        "colorbar_tickangle": 30,
        "colorbar_tickfont_size": 14,
    }
    compare_styles = [
        {
            "fix_color": "#111111",
            "saccade_color": "#222222",
            "saccade_style": "Dotted",
            "marker_size_range": [6, 18],
            "hollow": True,
        },
        {
            "fix_color": "#333333",
            "saccade_color": "#444444",
            "saccade_style": "Solid",
            "marker_size_range": [9, 21],
            "hollow": False,
        },
    ]
    cfg = _build_studio_config(
        selected_participant="p1",
        selected_trial="t1",
        canvas_width=2560,
        canvas_height=1440,
        x_field="x",
        y_field="y",
        figure_settings=figure_settings,
        viz_settings={
            "heatmap_metric": "duration_ms",
            "saccade_style": "Dotted",
            "saccade_width": 6.0,
            "saccade_color_mode": "By type",
            "saccade_class_colors": {"regression": "#010203"},
            "saccade_render_mode": "Arc",
            "fixation_snap_to_word": True,
            "hollow_fixations": True,
        },
        base_font_size=16,
        trial_raw_gaze=pd.DataFrame(),
        font_family="Courier New",
        annotation_records=[
            {
                "participant_id": "p1",
                "trial_id": "t1",
                "star": True,
                "tags": [],
                "note": "",
            }
        ],
        column_mapping={"col_map_fix_x": "CURRENT_FIX_X"},
        data_source="Use bundled demo",
        app_version="9.9.9",
        exported_at="2026-06-15T12:00:00",
        compare_styles=compare_styles,
    )
    # ENG-11: the writer stamps the single-source-of-truth schema constant, so
    # writer + reader can't drift when the version is bumped.
    from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

    assert cfg["schema"] == PLOT_CONFIG_SCHEMA
    assert cfg["app"] == {"name": "Scanpath Studio", "version": "9.9.9"}
    assert cfg["exported_at"] == "2026-06-15T12:00:00"
    assert cfg["data_source"] == "Use bundled demo"
    assert cfg["column_mapping"] == {"col_map_fix_x": "CURRENT_FIX_X"}
    assert cfg["selection"] == {"participant_id": "p1", "trial_id": "t1"}
    assert cfg["coloring"]["color_by"] == "line"
    assert cfg["coloring"]["heatmap_norm"] == "Log"
    assert cfg["coloring"]["saccade_style"] == "Dotted"
    assert cfg["coloring"]["saccade_width"] == 6.0
    assert cfg["coloring"]["saccade_color_mode"] == "By type"
    assert cfg["coloring"]["saccade_class_colors"]["regression"] == "#010203"
    assert cfg["coloring"]["saccade_render_mode"] == "Arc"
    assert cfg["coloring"]["fixation_snap_to_word"] is True
    assert cfg["coloring"]["hollow_fixations"] is True
    assert cfg["text"]["font_family"] == "Courier New"
    assert cfg["text"]["text_color"] == "#010203"
    assert cfg["highlighting"]["highlight_text_color"] == "#fedcba"
    assert cfg["highlighting"]["background_color"] == "#222222"
    # BATCH A settings + per-scanpath comparison styling must be captured too.
    assert cfg["coloring"]["colorbar_orientation"] == "Horizontal"
    assert cfg["coloring"]["colorbar_tickangle"] == 30
    assert cfg["coloring"]["colorbar_tickfont_size"] == 14
    assert cfg["highlighting"]["fixation_flags"]["oob"] == {
        "mode": "Highlight",
        "symbol": "star",
        "color": "#d62728",
    }
    assert cfg["highlighting"]["span_border_color"] == "#0a0b0c"
    assert cfg["compare"][0]["fix_color"] == "#111111"
    assert cfg["compare"][0]["hollow"] is True
    assert cfg["compare"][1]["saccade_style"] == "Solid"
    assert len(cfg["annotations"]) == 1
    json.dumps(cfg)  # must be JSON-serializable


def _collect_mapping_app():
    """Seed session_state like an active upload, then collect the mapping."""
    import streamlit as st

    from scanpath_studio.tabs import _collect_column_mapping

    class _FakeUpload:
        name = "data.csv.zip"

    # Real mapping selections.
    st.session_state["col_map_fix_x"] = "CURRENT_FIX_X"
    st.session_state["col_map_words_box_format"] = "edges"
    # File-uploader widgets share the col_map_* prefix — must NOT be collected.
    st.session_state["col_map_fix_upload"] = [_FakeUpload()]
    st.session_state["col_map_words_upload"] = _FakeUpload()
    st.session_state["col_map_raw_gaze_upload"] = None
    # Unrelated key — also excluded.
    st.session_state["other_key"] = "ignored"
    st.session_state["_mapping"] = _collect_column_mapping()


def test_collect_column_mapping_excludes_uploader_widgets():
    """The mapping sweep must drop the upload boxes' file_uploader widgets, whose
    UploadedFile values aren't JSON-serializable (regression: Save & restore
    download crashed with an active upload)."""
    import json

    at = AppTest.from_function(_collect_mapping_app)
    at.run()
    assert not at.exception
    mapping = at.session_state["_mapping"]
    assert mapping == {
        "col_map_fix_x": "CURRENT_FIX_X",
        "col_map_words_box_format": "edges",
    }
    json.dumps(mapping)  # must be JSON-serializable


class TestConfigMigration:
    """ENG-11: the Save & restore JSON is versioned. An older upload is upgraded
    to the current schema before its fields are read; a newer upload restores
    best-effort with a warning. These exercise the pure migration core directly
    (no Streamlit runtime) plus two end-to-end restores."""

    def test_detect_schema_missing_key_is_v1(self):
        from scanpath_studio.url_state import _detect_config_schema

        assert _detect_config_schema({}) == 1  # schema 1 predates the `schema` key

    def test_detect_schema_explicit_value(self):
        from scanpath_studio.url_state import _detect_config_schema

        assert _detect_config_schema({"schema": 2}) == 2

    def test_detect_schema_garbage_or_low_is_v1(self):
        from scanpath_studio.url_state import _detect_config_schema

        assert _detect_config_schema({"schema": "banana"}) == 1
        assert _detect_config_schema({"schema": None}) == 1
        assert _detect_config_schema({"schema": 0}) == 1  # clamped to >= 1

    def test_detect_schema_infinity_is_v1(self):
        # json.loads accepts the non-standard Infinity/NaN literals; int(inf)
        # raises OverflowError, which must degrade to v1, not abort the restore.
        from scanpath_studio.url_state import _detect_config_schema

        assert _detect_config_schema({"schema": float("inf")}) == 1
        assert _detect_config_schema({"schema": float("-inf")}) == 1
        assert _detect_config_schema({"schema": float("nan")}) == 1

    def test_migrate_deep_copies_nested_sections(self):
        # The migration contract is pure dict->dict: editing a nested section of
        # the returned config must not touch the caller's input dict.
        from scanpath_studio.url_state import _migrate_plot_config

        original = {"layers": {"words": False}, "coloring": {"color_by": "line"}}
        migrated, _ = _migrate_plot_config(original)
        assert migrated["layers"] is not original["layers"]
        migrated["layers"]["words"] = True
        migrated["coloring"]["color_by"] = "pass_index"
        assert original["layers"]["words"] is False  # input untouched
        assert original["coloring"]["color_by"] == "line"

    def test_migrate_v1_stamps_current_schema_no_note(self):
        from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA, _migrate_plot_config

        migrated, note = _migrate_plot_config({"layers": {"words": False}})
        assert note is None
        assert migrated["schema"] == PLOT_CONFIG_SCHEMA
        assert migrated["layers"] == {"words": False}  # content preserved
        assert migrated["axes"] == {
            "coordinate_grid": False,
            "coordinate_grid_auto": True,
            "coordinate_grid_spacing": 100.0,
        }

    def test_migrate_does_not_mutate_input(self):
        from scanpath_studio.url_state import _migrate_plot_config

        original = {"layers": {"words": False}}
        _migrate_plot_config(original)
        assert "schema" not in original  # a copy is stamped, not the caller's dict

    def test_migrate_current_schema_is_noop(self):
        from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA, _migrate_plot_config

        migrated, note = _migrate_plot_config({"schema": PLOT_CONFIG_SCHEMA})
        assert note is None
        assert migrated["schema"] == PLOT_CONFIG_SCHEMA

    def test_migrate_newer_schema_warns_and_preserves(self):
        from scanpath_studio.url_state import _migrate_plot_config

        migrated, note = _migrate_plot_config(
            {"schema": 999, "layers": {"words": True}, "future_only": 1}
        )
        assert note is not None and "newer version" in note
        # Best-effort: content is untouched (the reader ignores unknown keys).
        assert migrated["layers"] == {"words": True}
        assert migrated["future_only"] == 1

    def test_migration_chain_walks_each_step(self, monkeypatch):
        # Prove the loop applies migrations in sequence, not just the first step.
        from scanpath_studio import url_state

        calls = []

        def fake_1_to_2(cfg):
            calls.append(1)
            return dict(cfg, _via_1=True)

        def fake_2_to_3(cfg):
            calls.append(2)
            return dict(cfg, _via_2=True)

        monkeypatch.setattr(url_state, "PLOT_CONFIG_SCHEMA", 3)
        monkeypatch.setattr(
            url_state, "_PLOT_CONFIG_MIGRATIONS", {1: fake_1_to_2, 2: fake_2_to_3}
        )
        migrated, note = url_state._migrate_plot_config({})  # detected as v1
        assert calls == [1, 2]
        assert migrated["_via_1"] and migrated["_via_2"]
        assert migrated["schema"] == 3
        assert note is None

    def test_missing_migration_step_warns(self, monkeypatch):
        from scanpath_studio import url_state

        monkeypatch.setattr(url_state, "PLOT_CONFIG_SCHEMA", 5)
        monkeypatch.setattr(url_state, "_PLOT_CONFIG_MIGRATIONS", {})  # no 1->2 step
        migrated, note = url_state._migrate_plot_config({"schema": 1})
        assert note is not None
        assert migrated["schema"] == 1  # couldn't advance past the gap

    def test_schema_constant_is_three(self):
        # Pin the current version so a bump is a deliberate, reviewed change that
        # forces a matching migration + this assertion to move together.
        from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA

        assert PLOT_CONFIG_SCHEMA == 3

    def test_schema1_config_still_restores_end_to_end(self):
        # A schema-1 file (no `schema` key) applies its plot settings through the
        # migration + reader unchanged — nothing regresses for old saved configs.
        config = _full_config()
        assert "schema" not in config
        ss = _run(_restore_app, _config=config).session_state
        assert ss["global_show_words"] is False
        assert ss["global_color_by"] == "pass_index"
        assert ss["_applied"] > 0

    def test_newer_config_restores_known_fields_end_to_end(self):
        config = dict(_full_config())
        config["schema"] = 999
        config["some_future_section"] = {"unknown": True}
        at = _run(_restore_app, _config=config)
        ss = at.session_state
        # Known fields still applied despite the newer schema; unknown ignored.
        assert ss["global_color_by"] == "pass_index"
        assert ss["_applied"] > 0
        # ...and the user is warned their config is from a newer build (this pins
        # the note -> st.toast wiring in _restore_plot_config, not just the return).
        assert any("newer version" in t.value for t in at.toast)

    def test_schema1_config_fires_no_migration_warning(self):
        # The common case (an old/current config) must NOT nag the user.
        at = _run(_restore_app, _config=_full_config())
        assert not any("newer version" in t.value for t in at.toast)
