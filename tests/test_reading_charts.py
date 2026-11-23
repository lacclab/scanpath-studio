"""Regression cases for reading charts and the mode switches around them."""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import api, chart_axes, data
from scanpath_studio.constants import SUBTAB_EXPORT
from scanpath_studio.controls import (
    BOX_FORMAT_EDGES,
    BOX_FORMAT_ORIGIN,
    _default_box_format,
    numeric_field_options,
)
from scanpath_studio.export import ExportOptions, bulk_export
from scanpath_studio.plots import make_scanpath_figure, split_scanpath_layers
from scanpath_studio.synthetic import (
    example_import_tables,
    make_multipart_synthetic_data,
)
from tests.conftest import APP_SCRIPT


def _trace(figure, name):
    return next(trace for trace in figure.data if trace.name == name)


def test_samples_keep_their_own_axes_during_tracking_loss_and_without_a_clock():
    source = pd.DataFrame(
        {
            "trial_id": "t",
            "x": [np.nan, np.nan],
            "y": np.nan,
            "Time": [100, 101],
            "diameter from tracker": [2.1, 2.3],
        }
    )
    schema = {
        "trial": "trial_id",
        "x": "x",
        "y": "y",
        "timestamp": "Time",
        "pupil_diameter": "diameter from tracker",
    }
    samples = api.load_raw_gaze(source, raw_gaze_schema=schema)
    assert not any(
        t.name == "Raw gaze" for t in api.plot_scanpath(raw_gaze=samples).data
    )
    fig = api.plot_scanpath(
        raw_gaze=samples, x_field="Time", y_field="diameter from tracker"
    )
    assert list(_trace(fig, "Raw gaze").x) == [100, 101]
    assert list(_trace(fig, "Raw gaze").y) == [2.1, 2.3]
    assert fig.layout.yaxis.title.text == "diameter from tracker"
    untimed = api.load_raw_gaze(source, raw_gaze_schema={**schema, "timestamp": None})
    chart = api.plot_scanpath(
        raw_gaze=untimed, x_field="sample_index", y_field="pupil_diameter"
    )
    assert list(_trace(chart, "Raw gaze").x) == [1, 2]
    assert "ms" not in _trace(chart, "Raw gaze").hovertemplate


def test_fixation_and_sample_clocks_can_have_different_source_names():
    words, events = example_import_tables()
    events = events.rename(columns={"timestamp_ms": "Fix onset"})
    schema = {**data.propose_fix_schema(events), "timestamp": "Fix onset"}
    words, events = api.load_scanpath_data(words, events, fix_schema=schema)
    key = api.list_trials(words, events).iloc[0]
    source = pd.DataFrame(
        {
            "participant_id": key.participant_id,
            "trial_id": key.trial_id,
            "x": [10, 11],
            "y": [20, 21],
            "Sample clock": [123, 124],
            "Area recording": [340, 341],
        }
    )
    samples = api.load_raw_gaze(
        source,
        raw_gaze_schema={
            **data.propose_raw_gaze_schema(source),
            "timestamp": "Sample clock",
            "pupil_area": "Area recording",
        },
    )
    fig = api.plot_scanpath(
        words,
        events,
        raw_gaze=samples,
        x_field="Sample clock",
        y_field="Area recording",
    )
    trace = _trace(fig, "Raw gaze")
    assert list(trace.x) == [123, 124]
    assert list(trace.y) == [340, 341]
    assert fig.layout.xaxis.title.text == "Time (ms)"
    assert fig.layout.yaxis.title.text == "Area recording"


def test_captions_and_charts_require_drawable_samples_and_a_measured_elapsed_origin():
    raw = api.load_raw_gaze(
        pd.DataFrame(
            {
                "trial_id": "t",
                "x": [1e8],
                "y": 10,
                "pupil_area": 130,
                "timestamp_ms": 28,
            }
        ),
        names="canonical",
    )
    for axes in (("x", "y"), (chart_axes.ELAPSED, "pupil_area")):
        assert not chart_axes.drawable_raw_samples(
            axes, raw, data.empty_fixations_frame()
        )
        fig = api.plot_scanpath(raw_gaze=raw, x_field=axes[0], y_field=axes[1])
        assert not any(t.name == "Raw gaze" for t in fig.data)
    assert chart_axes.drawable_raw_samples(("timestamp_ms", "pupil_area"), raw)


def test_pupil_preset_enables_recorded_samples_and_round_trips_through_settings(
    monkeypatch,
):
    from scanpath_studio import url_state

    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    next(box for box in at.selectbox if box.label == "Axis preset").set_value(
        "Pupil area over recorded time"
    ).run()
    assert not at.exception
    assert at.session_state["global_show_raw_gaze"]
    assert (at.session_state["global_x_field"], at.session_state["global_y_field"]) == (
        "timestamp_ms",
        "pupil_area",
    )

    samples = api.load_sample_raw_gaze(names="canonical")
    restored = {}
    monkeypatch.setattr(url_state.st, "session_state", restored)
    _, skipped = url_state._restore_plot_config(
        {"axes": {"x_field": "timestamp_ms", "y_field": "pupil_area"}},
        pd.DataFrame(),
        data.empty_fixations_frame(),
        samples,
    )
    assert not skipped
    assert (restored["global_x_field"], restored["global_y_field"]) == (
        "timestamp_ms",
        "pupil_area",
    )


def test_fixations_say_why_they_grey_on_axes_they_lack():
    """Fixations carry no pupil area: the switch greys with the reason, and its
    menu gives the same one rather than asking to turn the layer on."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.toggle(key="single_animate").set_value(False).run()
    at.selectbox(key="_plot_axis_preset").set_value(
        "Pupil area over recorded time"
    ).run()
    assert not at.exception
    reason = "Both axes must be fields available in the fixations."
    switch = at.toggle(key="global_show_fix")
    assert switch.disabled
    assert switch.help == reason
    menu = next(p for p in at.get("popover") if p.key == "plot_menu_fix")
    captions = [caption.value for caption in menu.caption]
    assert captions[0] == reason
    assert not any("Turn the layer on" in caption for caption in captions)


def test_gaze_over_time_keeps_its_small_onset_markers_in_compare():
    """Each reading draws its own marker size in Compare, so the view sets
    both: a large duration-scaled marker would hide a short fixation's bar."""
    from scanpath_studio.code_snippet import SNIPPET_STATE_KEY

    def sizes():
        figure = at.session_state[SNIPPET_STATE_KEY]
        assert figure.kind == "comparison"
        return [
            tuple(figure.settings[style]["marker_size_range"])
            for style in ("style_a", "style_b")
        ]

    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.toggle(key="single_animate").set_value(False).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    at.button(key="viz_view_gaze_over_time").click().run()
    assert not at.exception
    assert sizes() == [(4, 4), (4, 4)]
    at.button(key="viz_view_scanpath").click().run()
    assert sizes() == [(8, 24), (8, 24)]


def test_missing_timestamps_never_supply_elapsed_seconds():
    w, f = example_import_tables()
    f = f.iloc[:3].copy()
    f["timestamp_ms"] = [10_000, np.nan, 11_000]
    w, f = api.load_scanpath_data(w, f, names="canonical")
    assert data.shareable_frame(f)["timestamp_ms"].isna().sum() == 1
    figure = api.plot_scanpath(w, f, x_field=chart_axes.ELAPSED, y_field="y")
    values = np.asarray(_trace(figure, "Fixations").x)
    assert values[np.isfinite(values)].tolist() == [0, 1]
    assert figure.layout.yaxis.range[0] > figure.layout.yaxis.range[1]
    assert figure.layout.width <= 1000


def test_legacy_counter_stays_estimated_on_a_replay_window_and_later_screen():
    words, fix = example_import_tables()
    words, fix = api.load_scanpath_data(words, fix.iloc[:3].copy(), names="canonical")
    fix = fix.drop(columns=data.TIMESTAMP_SYNTHESIZED).assign(
        timestamp_ms=[0, 1, 2], duration_ms=[100, 200, 300], order_in_trial=[1, 2, 3]
    )
    assert "timestamp_ms" not in data.shareable_frame(fix)
    window = api.animate_scanpath(words, fix, fix_index_range=(2, 3))
    assert window.layout.meta["scanpath_frame_times_ms"][-1] == 500
    fix = fix.assign(screen_id=["first", "next", "next"], screen_index=[1, 2, 2])
    later = api.animate_scanpath(None, fix, screen="next")
    assert later.layout.meta["scanpath_frame_times_ms"][-1] == 500
    assert data.TIMESTAMP_SYNTHESIZED not in fix


def test_sharing_keeps_valid_raw_times_and_masks_invalid_fixation_times():
    raw = pd.DataFrame(
        {"timestamp_ms": [0, 1, np.inf, np.nan], "duration_ms": [100] * 4}
    )
    shown = data.shareable_frame(raw, table="raw_gaze")
    assert shown.timestamp_ms.iloc[:2].tolist() == [0, 1]
    assert shown.timestamp_ms.iloc[2:].isna().all()
    fixed = raw.assign(**{data.TIMESTAMP_SYNTHESIZED: [False, True, False, False]})
    assert data.shareable_frame(fixed).timestamp_ms.notna().tolist() == [
        True,
        False,
        False,
        False,
    ]
    # Metadata columns with these names belong to the lab.
    pd.testing.assert_frame_equal(data.shareable_frame(raw, table="metadata"), raw)


def test_no_recorded_clock_is_excluded_from_the_choices_and_chart():
    w, f = example_import_tables()
    w, f = api.load_scanpath_data(w, f.drop(columns="timestamp_ms"), names="canonical")
    assert set(chart_axes.CLOCK_FIELDS).isdisjoint(numeric_field_options(f))
    for field in chart_axes.CLOCK_FIELDS:
        fig = api.plot_scanpath(w, f, x_field=field, y_field="y")
        assert not any(t.name == "Fixations" for t in fig.data)
        assert any(
            "no recorded fixation onsets" in a.text for a in fig.layout.annotations
        )


def test_elapsed_uses_parent_origin_across_screen_and_window_and_for_samples():
    w, f = make_multipart_synthetic_data()
    later = f.loc[f.screen_id == "question"].iloc[-1]
    order = int(later.order_in_trial)
    samples = f.loc[
        [later.name],
        ["participant_id", "trial_id", "screen_id", "timestamp_ms", "x", "y"],
    ].copy()
    samples["timestamp_ms"] += 10
    fig = api.plot_scanpath(
        w,
        f,
        screen="question",
        x_field=chart_axes.ELAPSED,
        y_field="y",
        fix_index_range=(order, order),
        raw_gaze=samples,
        show_raw_gaze=True,
    )
    elapsed = (later.timestamp_ms - f.timestamp_ms.min()) / 1000
    assert list(_trace(fig, "Fixations").x) == pytest.approx([elapsed])
    assert list(_trace(fig, "Raw gaze").x) == pytest.approx([elapsed + 0.01])
    assert list(_trace(fig, "Fixation duration").x[:2]) == pytest.approx(
        [elapsed, elapsed + later.duration_ms / 1000]
    )
    assert chart_axes.ELAPSED not in f
    empty = chart_axes.with_origin(f).iloc[:0]
    fig = make_scanpath_figure(
        w.iloc[:0],
        empty,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        x_field=chart_axes.ELAPSED,
        y_field="y",
        raw_gaze=samples,
        show_raw_gaze=True,
    )
    assert list(_trace(fig, "Raw gaze").x) == pytest.approx([elapsed + 0.01])


def test_index_chart_hides_incompatible_samples_and_uses_recorded_bounds():
    w, f = api.load_scanpath_data(*example_import_tables(), names="canonical")
    f.loc[f.index[7], "x"] = 125
    options = dict(
        raw_gaze=f,
        show_raw_gaze=True,
        fixation_snap_to_line=True,
        fixation_flags={"oob": {"mode": "Highlight"}},
    )
    spatial = api.plot_scanpath(w, f, **options)
    fig = api.plot_scanpath(w, f, x_field="order_in_trial", y_field="y", **options)
    assert (
        len(_trace(spatial, "Outside the text").x)
        == len(_trace(fig, "Outside the text").x)
        > 0
    )
    assert not any(t.name == "Raw gaze" for t in fig.data)
    assert fig.layout.xaxis.dtick == 1
    assert list(_trace(fig, "Fixation sequence").x) == sorted(f.order_in_trial)
    hidden = api.plot_scanpath(
        w, f, x_field="order_in_trial", y_field="y", show_saccades=False
    )
    assert not any(t.name == "Fixation sequence" for t in hidden.data)


def test_private_link_fingerprint_survives_recovery_and_detects_a_changed_nested_value():
    original = pd.DataFrame({"feature": [list(range(1500))]}, index=[17])
    restored = pd.read_parquet(io.BytesIO(original.to_parquet())).reset_index(drop=True)
    digest = data.share_dataset_fingerprint({"words": original})
    assert data.share_dataset_fingerprint({"words": restored}) == digest
    changed = np.arange(1500)
    changed[700] += 1
    assert (
        data.share_dataset_fingerprint({"words": pd.DataFrame({"feature": [changed]})})
        != digest
    )


def test_chart_layer_exports_share_extents_and_keep_chart_fields_out_of_csv():
    w, f = make_multipart_synthetic_data()
    raw = f.assign(timestamp_ms=f.timestamp_ms + 1_000_000)
    fig = api.plot_scanpath(
        w,
        f,
        screen="question",
        x_field=chart_axes.ELAPSED,
        y_field="x",
        raw_gaze=raw,
        show_raw_gaze=True,
    )
    for layer in split_scanpath_layers(fig).values():
        assert layer.layout.xaxis.range == fig.layout.xaxis.range
        assert layer.layout.xaxis.range[1] > 1000

    fig = api.plot_scanpath(
        w,
        f,
        screen="question",
        x_field=chart_axes.ELAPSED,
        y_field="y",
        raw_gaze=raw.drop(columns="screen_id"),
        show_raw_gaze=True,
    )
    assert not any(t.name == "Raw gaze" for t in fig.data)
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_html=True,
        include_fixations=True,
        screens=("question",),
    )
    payload, _ = bulk_export(
        api.list_trials(w, f),
        w,
        f,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        font_family="Arial",
        x_field=chart_axes.ELAPSED,
        y_field="y",
        settings={},
        options=options,
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        csv = next(path for path in bundle.namelist() if path.endswith("fixations.csv"))
        assert chart_axes.ELAPSED not in pd.read_csv(bundle.open(csv)).columns
        html = next(path for path in bundle.namelist() if path.endswith("figure.html"))
        assert chart_axes.ELAPSED_LABEL in bundle.read(html).decode()


def test_synthetic_timestamp_is_also_missing_in_an_explicit_hover():
    w, f = example_import_tables()
    w, f = api.load_scanpath_data(w, f.drop(columns="timestamp_ms"), names="canonical")
    fig = api.plot_scanpath(
        w, f, x_field="order_in_trial", fixation_hover_fields=["timestamp_ms"]
    )
    assert set(_trace(fig, "Fixations").customdata[:, 0]) == {"—"}


def test_private_link_fingerprint_keeps_value_types():
    def digest(values):
        return data.share_dataset_fingerprint(
            {"fixations": pd.DataFrame({"feature": values})}
        )

    assert digest([True, False]) != digest([1, 0])
    assert digest([1.0, 2.0]) != digest([4607182418800017408, 4611686018427387904])


def test_rejected_private_link_keeps_recovered_view_and_settings(tmp_path, monkeypatch):
    from scanpath_studio import persistence
    from scanpath_studio.menu import _VIEW_DATA

    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr(
        persistence, "state_directory", lambda *args, **kwargs: tmp_path
    )
    w, f = example_import_tables()
    session = {
        "main_nav": _VIEW_DATA,
        "tour_seen": True,
        "global_heatmap_colorscale": "Reds",
        "_datasets": {"Mine": {"words": w, "fixations": f}},
    }
    assert persistence.save_state(session, tmp_path)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.query_params.update(
        {
            "dataset": "Mine",
            "dataset_digest": "different",
            "heatmap_colorscale": "Greens",
        }
    )
    at.run()
    assert not at.exception
    assert any("different data" in notice.value for notice in at.warning)
    assert at.session_state["main_nav"] == _VIEW_DATA
    assert at.session_state["global_heatmap_colorscale"] == "Reds"


@pytest.mark.parametrize("legacy", [False, True])
def test_verified_and_legacy_links_open_the_matching_reading(legacy):
    w, f = api.load_scanpath_data(*example_import_tables(), names="canonical")
    entry = {"words": w, "fixations": f, "raw_gaze": pd.DataFrame()}
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.session_state["_datasets"] = {"My reading": entry}
    at.query_params.update({"dataset": "My reading", "x_field": "order_in_trial"})
    if not legacy:
        at.query_params["dataset_digest"] = data.share_dataset_fingerprint(entry)
    at.run()
    at.run()
    assert not at.exception
    assert at.session_state["data_source_choice"] == "My reading"
    assert at.session_state["global_x_field"] == "order_in_trial"
    assert any("by name alone" in notice.value for notice in at.info) == legacy


def test_partial_word_geometry_prefers_the_best_match():
    assert (
        _default_box_format(
            {"x": "left_px", "width": "w", "height": "h", "left": "left_px"}
        )
        == BOX_FORMAT_ORIGIN
    )
    assert _default_box_format({"x": "hpos", "right": "right_edge"}) == BOX_FORMAT_EDGES


def test_mode_round_trip_keeps_export_scope_and_artifacts():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.session_state["single_subtab"] = SUBTAB_EXPORT
    at.run()
    at.radio(key="bulk_export_scope").set_value("This trial")
    at.pills(key="bulk_export_figfmts").set_value(["HTML"])
    at.pills(key="bulk_export_tabular").set_value(["Fixations"])
    at.run()
    at.toggle(key="bulk_export_combine").set_value(True).run()
    for mode in ("essentials", "full"):
        at.segmented_control(key="ui_mode_switch").set_value(mode).run()
        assert not at.exception
        assert at.session_state["bulk_export_scope"] == "This trial"
        assert at.session_state["bulk_export_figfmts"] == ["HTML"]
        assert at.session_state["bulk_export_tabular"] == ["Fixations"]
        assert at.session_state["bulk_export_combine"]


def test_time_view_replay_and_custom_restore():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.button(key="viz_view_custom").click().run()
    assert at.button(key="viz_view_custom").proto.type == "primary"
    at.checkbox(key="global_show_order").check().run()
    initial_palette = at.session_state["global_palette"]
    at.button(key="viz_view_gaze_over_time").click().run()
    assert tuple(at.session_state["global_marker_size_range"]) == (4, 4)
    at.button(key="viz_palette_high_contrast").click().run()
    for mode, animate in (("essentials", True), ("full", False)):
        at.segmented_control(key="ui_mode_switch").set_value(mode).run()
        at.toggle(key="single_animate").set_value(animate).run()
        assert not at.exception
        assert at.button(key="viz_view_gaze_over_time").proto.type == "primary"
        assert (
            at.session_state["global_x_field"],
            at.session_state["global_y_field"],
        ) == chart_axes.GAZE_OVER_TIME
    at.button(key="viz_view_custom").click().run()
    assert at.checkbox(key="global_show_order").value
    assert at.session_state["global_palette"] == initial_palette
    assert at.session_state["global_x_field"] == "x"
    assert at.session_state["global_y_field"] == "y"


def test_time_view_falls_back_to_screen_axes_on_a_dataset_without_onsets():
    w, f = example_import_tables()
    w, f = api.load_scanpath_data(w, f.drop(columns="timestamp_ms"), names="canonical")
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.session_state["_datasets"] = {
        "Untimed": {
            "words": w,
            "fixations": f,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
        }
    }
    at.run()
    at.button(key="viz_view_gaze_over_time").click().run()
    picker = at.selectbox(key="data_source_picker")
    first = picker.index
    picker.select_index(
        next(i for i, label in enumerate(picker.options) if "Untimed" in label)
    ).run()
    assert not at.exception
    assert at.button(key="viz_view_gaze_over_time").disabled
    assert (at.session_state["global_x_field"], at.session_state["global_y_field"]) == (
        "x",
        "y",
    )
    at.selectbox(key="data_source_picker").select_index(first).run()
    at.button(key="viz_view_gaze_over_time").click().run()
    assert (
        at.session_state["global_x_field"],
        at.session_state["global_y_field"],
    ) == chart_axes.GAZE_OVER_TIME


def test_choosing_scanpath_in_compare_replaces_the_underlying_time_chart():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    at.button(key="viz_view_gaze_over_time").click().run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    assert not at.button(key="viz_view_gaze_over_time").disabled
    assert at.button(key="viz_view_gaze_over_time").proto.type == "primary"
    at.button(key="viz_view_scanpath").click().run()
    assert at.toggle(key="single_compare_toggle").value
    at.toggle(key="single_compare_toggle").set_value(False).run()
    assert at.button(key="viz_view_scanpath").proto.type == "primary"
    assert (at.session_state["global_x_field"], at.session_state["global_y_field"]) == (
        "x",
        "y",
    )


def test_time_shortcuts_follow_the_clock_of_the_selected_reading():
    words, fix = api.load_scanpath_data(*example_import_tables(), names="canonical")
    words = pd.concat(
        [words.assign(trial_id="recorded"), words.assign(trial_id="untimed")]
    )
    fix = pd.concat(
        [
            fix.assign(trial_id="recorded"),
            fix.assign(trial_id="untimed", timestamp_ms=np.nan),
        ]
    )
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    at.session_state["_datasets"] = {
        "Mixed": {
            "words": words,
            "fixations": fix,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": [],
        }
    }
    at.session_state["data_source_choice"] = "Mixed"
    at.run()
    at.button(key="viz_view_gaze_over_time").click().run()
    at.selectbox(key="single_trial_id").set_value("untimed").run()
    assert not at.exception
    assert at.button(key="viz_view_gaze_over_time").disabled
    assert (
        "Horizontal position over time"
        not in at.selectbox(key="_plot_axis_preset").options
    )
    at.selectbox(key="single_trial_id").set_value("recorded").run()
    assert at.button(key="viz_view_gaze_over_time").proto.type == "primary"
    assert (
        at.selectbox(key="_plot_axis_preset").value == "Horizontal position over time"
    )


def test_axis_preset_and_compare_survive_mode_switch_until_a_tile_is_selected():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    next(box for box in at.selectbox if box.label == "Axis preset").set_value(
        "Vertical position over time"
    ).run()
    assert (at.session_state["global_x_field"], at.session_state["global_y_field"]) == (
        chart_axes.ELAPSED,
        "y",
    )
    at.toggle(key="single_animate").set_value(True).run()
    assert at.session_state["single_animate"]
    at.toggle(key="single_animate").set_value(False).run()
    assert not at.session_state["single_animate"]
    assert at.session_state["global_x_field"] == chart_axes.ELAPSED
    at.segmented_control(key="ui_mode_switch").set_value("essentials").run()
    assert any(chart_axes.ELAPSED_LABEL in c.value for c in at.caption)
    at.button(key="hidden_note_to_advanced").click().run()
    at.toggle(key="single_compare_toggle").set_value(True).run()
    at.segmented_control(key="ui_mode_switch").set_value("essentials").run()
    assert at.session_state["single_compare_toggle"]
    assert at.button(key="viz_view_custom").proto.type == "primary"
    at.toggle(key="single_compare_toggle").set_value(False).run()
    assert at.session_state["global_x_field"] == chart_axes.ELAPSED
    at.button(key="viz_view_scanpath").click().run()
    assert not at.exception
    assert not at.session_state["single_compare_toggle"]
    assert (at.session_state["global_x_field"], at.session_state["global_y_field"]) == (
        "x",
        "y",
    )


@pytest.mark.parametrize("all_trials", [False, True], ids=["per-trial", "all-trials"])
def test_saved_reading_design_after_trial_mode_changes_and_reset(all_trials):
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60).run()
    next(box for box in at.selectbox if box.label == "Axis preset").set_value(
        "Elapsed time by fixation index"
    ).run()
    at.checkbox(key="global_show_order").check().run()
    if all_trials:
        at.checkbox(key="single_fix_range_all_trials").check().run()
    window = next(
        slider for slider in at.slider if slider.label == "Fixation index range"
    )
    window.set_range(5, 12).run()
    at.button(key="design_save").click().run()
    at.text_input(key="design_new_name").set_value("Reading clock")
    at.button(key="design_save_go").click().run()

    def check_clock():
        assert not at.exception
        assert at.selectbox(key="global_x_field").value == "order_in_trial"
        assert at.selectbox(key="global_y_field").value == chart_axes.ELAPSED
        assert at.checkbox(key="global_show_order").value

    check_clock()
    trial = at.selectbox(key="single_trial_id").value
    at.segmented_control(key="ui_mode_switch").set_value("essentials").run()
    assert tuple(at.session_state["single_fix_range"]) == (5, 12)
    at.button(key="single_next_trial").click().run()
    other_trial = at.selectbox(key="single_trial_id").value
    assert other_trial != trial
    check_clock()
    full_window = (
        1,
        next(s for s in at.slider if s.label == "Fixation index range").max,
    )
    assert tuple(at.session_state["single_fix_range"]) == (
        (5, 12) if all_trials else full_window
    )
    at.button(key="hidden_note_to_advanced").click().run()
    at.button(key="viz_view_illustration").click().run()
    assert at.selectbox(key="global_x_field").value == "x"
    assert at.checkbox(key="global_fixation_snap_to_line").value
    at.button(key="design_apply_Reading clock").click().run()
    check_clock()
    assert tuple(at.session_state["single_fix_range"]) == (5, 12)

    at.button(key="reset_viz_settings_btn").click().run()
    at.button(key="reset_viz_cancel").click().run()
    check_clock()
    assert tuple(at.session_state["single_fix_range"]) == (5, 12)
    at.button(key="reset_viz_settings_btn").click().run()
    at.button(key="reset_viz_confirm").click().run()
    assert not at.exception
    assert at.selectbox(key="single_trial_id").value == other_trial
    assert at.selectbox(key="global_x_field").value == "x"
    assert at.selectbox(key="global_y_field").value == "y"
    assert not at.checkbox(key="global_show_order").value
    assert not at.checkbox(key="single_fix_range_all_trials").value
    assert tuple(at.session_state["single_fix_range"]) == full_window
    at.button(key="design_apply_Reading clock").click().run()
    check_clock()
    assert tuple(at.session_state["single_fix_range"]) == (5, 12)


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_compare_elapsed_axes_keep_each_readings_parent_clock_and_scale(layout):
    words, first = make_multipart_synthetic_data()
    second = first.assign(timestamp_ms=first.timestamp_ms * 2 + 91_000)
    later = first[first.screen_id == "question"]
    a, b = later.iloc[-1], later.iloc[0]
    key = (a.participant_id, a.trial_id)
    fig = api.compare_scanpaths(
        words,
        first,
        key,
        key,
        words_b=words,
        fixations_b=second,
        screen="question",
        screen_b="question",
        layout=layout,
        x_field=chart_axes.ELAPSED,
        y_field="y",
        labels=("First", "Second"),
        fix_index_range=(int(a.order_in_trial), int(a.order_in_trial)),
        fix_index_range_b=(int(b.order_in_trial), int(b.order_in_trial)),
        color_by="(uniform)",
        show_saccade_arrows=True,
    )
    assert list(_trace(fig, "First").x) == pytest.approx(
        [(a.timestamp_ms - first.timestamp_ms.min()) / 1000]
    )
    assert list(_trace(fig, "Second").x) == pytest.approx(
        [(b.timestamp_ms - first.timestamp_ms.min()) / 500]
    )
    assert _trace(fig, "Second").xaxis == "x2"
    assert fig.layout.xaxis.range == fig.layout.xaxis2.range
    assert fig.layout.yaxis.range == fig.layout.yaxis2.range
    assert fig.layout.yaxis.range[0] > fig.layout.yaxis.range[1]
    assert len([t for t in fig.data if t.name == "Fixation duration"]) == 2
    assert all(t.marker.symbol != "arrow" for t in fig.data)
    assert not fig.layout.shapes


@pytest.mark.parametrize("comparing", [False, True])
def test_index_sequence_without_markers_obeys_window_and_hide(comparing):
    words, fix = api.load_scanpath_data(*example_import_tables(), names="canonical")
    first = fix.iloc[0]
    key = (first.participant_id, first.trial_id)
    fix = fix[(fix.participant_id == key[0]) & (fix.trial_id == key[1])].copy()
    fix["duration_ms"] = np.where(fix.order_in_trial == 3, 1, 200)
    settings = dict(
        x_field="order_in_trial",
        y_field="x",
        show_fixations=False,
        show_order=True,
        show_saccades=True,
        fix_index_range=(2, 5),
        fixation_flags={"short": {"mode": "Hide", "threshold_ms": 50}},
    )
    fig = (
        api.compare_scanpaths(words, fix, key, key, **settings)
        if comparing
        else api.plot_scanpath(words, fix, **settings)
    )
    lines = [t for t in fig.data if t.name == "Fixation sequence"]
    assert len(lines) == 1 + int(comparing)
    assert all(list(t.x) == [2, 4, 5] for t in lines)
    assert all(t.mode == "lines" for t in fig.data if t.x is not None and len(t.x) > 1)


def test_sample_only_comparison_axis_does_not_draw_fixation_keys():
    words, fix = api.load_scanpath_data(*example_import_tables(), names="canonical")
    first = fix.iloc[0]
    key = (first.participant_id, first.trial_id)
    raw = pd.DataFrame(
        {
            "participant_id": key[0],
            "trial_id": key[1],
            "x": [1],
            "y": [2],
            "timestamp_ms": [35.0],
            "pupil_area": [231.0],
        }
    )
    fig = api.compare_scanpaths(
        words,
        fix,
        key,
        key,
        words_b=words,
        fixations_b=fix,
        raw_gaze_b=raw,
        show_raw_gaze=True,
        x_field="timestamp_ms",
        y_field="pupil_area",
        duration_size_legend=True,
        marker_size_scale="linear",
        labels=("First", "Second"),
    )
    assert [t.name for t in fig.data] == ["Second · raw gaze"]
    assert list(fig.data[0].x) == [35]
    assert list(fig.data[0].y) == [231]
    assert sum(a.text == "No data on these axes" for a in fig.layout.annotations) == 1
    assert not fig.layout.shapes
