"""Scientific values and public artifacts should survive a publication handoff."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from PIL import Image

from scanpath_studio import (
    aggregation,
    animation_export,
    api,
    chart_axes,
    data,
    export,
    measures,
    plot_config,
    plots,
)
from scanpath_studio.synthetic import (
    PARTICIPANT,
    TRIAL,
    load_synthetic_data,
    make_multipart_synthetic_data,
)


def test_save_failure_preserves_the_previous_published_figure(tmp_path, monkeypatch):
    path = tmp_path / "figure.html"
    figure = go.Figure(go.Scatter(x=[0, 1], y=[1, 2]))
    api.save_figure(figure, path)
    original = path.read_bytes()
    assert b"Plotly.newPlot" in original

    def partial_render(self, filename, **kwargs):
        Path(filename).write_bytes(b"partial")
        raise OSError("interrupted renderer")

    with monkeypatch.context() as patch:
        patch.setattr(go.Figure, "write_html", partial_render)
        with pytest.raises(OSError, match="interrupted"):
            api.save_figure(figure, path)
    assert path.read_bytes() == original

    def failed_stamp(staged):
        assert Path(staged).read_bytes()
        raise OSError("interrupted stamp")

    monkeypatch.setattr(api, "stamp_file", failed_stamp)
    with pytest.raises(OSError, match="interrupted"):
        api.save_figure(figure, path)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_layer_revision_removes_only_owned_files_after_a_complete_render(
    tmp_path, monkeypatch
):
    words, fixations = load_synthetic_data()
    fig = api.plot_scanpath(words, fixations, PARTICIPANT, TRIAL)
    revised = api.plot_scanpath(
        words,
        fixations,
        PARTICIPANT,
        TRIAL,
        show_words=False,
        show_word_labels=False,
        show_saccades=False,
    )

    def render(figure, path, **options):
        path.write_text(str(options))

    monkeypatch.setattr(api, "save_figure", render)
    first = api.save_figure_layers(fig, tmp_path, fmt="png", width_mm=85, dpi=300)
    assert len(first) >= 4
    previous = {p: p.read_bytes() for p in first.values()}
    other = tmp_path / "saccades.svg"
    other.write_text("manual artwork")

    def fail_after_one(figure, path, **options):
        path.write_bytes(b"new image")
        if path.name != next(iter(first.values())).name:
            raise OSError("second layer")

    with monkeypatch.context() as patch:
        patch.setattr(api, "save_figure", fail_after_one)
        with pytest.raises(OSError, match="second layer"):
            api.save_figure_layers(fig, tmp_path, fmt="png")
    assert {p: p.read_bytes() for p in previous} == previous
    current = api.save_figure_layers(revised, tmp_path, fmt="png", width_mm=85, dpi=300)
    assert set(tmp_path.glob("*.png")) == set(current.values()) < set(previous)
    assert all(
        "'width_mm': 85" in p.read_text() and "'dpi': 300" in p.read_text()
        for p in current.values()
    )
    assert other.read_text() == "manual artwork"


def test_actual_png_density_and_pixel_size_match_across_all_layers(
    tmp_path, monkeypatch
):
    words, fixations = load_synthetic_data()
    fig = api.plot_scanpath(words, fixations, PARTICIPANT, TRIAL)

    def raster(figure, *, fmt, scale, width, height):
        from io import BytesIO

        layout = figure.layout
        dims = (
            int((width or layout.width) * scale),
            int((height or layout.height) * scale),
        )
        image = BytesIO()
        Image.new("RGB", dims, "white").save(image, "PNG")
        return image.getvalue()

    monkeypatch.setattr("scanpath_studio.export.render_static_figure_bytes", raster)
    opts = dict(width_in=2, dpi=150)
    composite = api.save_figure(fig, tmp_path / "combined.png", **opts)
    layers = api.save_figure_layers(fig, tmp_path / "layers", fmt="png", **opts)

    def dimensions(path):
        with Image.open(path) as image:
            return image.size, image.info["dpi"]

    size, dpi = dimensions(composite)
    assert size[0] == 300
    assert dpi == pytest.approx((150, 150), abs=0.1)
    assert all(dimensions(p) == (size, dpi) for p in layers.values())


def test_category_named_heatmap_stays_with_fixations():
    words, fixations = load_synthetic_data()
    fixations["condition"] = ["heatmap task", "control", "control"] * 3
    fig = api.plot_scanpath(
        words, fixations, PARTICIPANT, TRIAL, color_by="condition", show_heatmap=False
    )
    layers = plots.split_scanpath_layers(fig)
    assert "heatmap" not in layers
    names = [t.name for t in layers["fixations"].data if t.name]
    assert any("heatmap task" in name for name in names)
    assert any("control" in name for name in names)


def test_multipart_catalog_numbers_reach_every_published_screen():
    words, fixations = make_multipart_synthetic_data()
    for frame in (words, fixations):
        frame["screen_index"] = frame.screen_index.map({1: 2, 2: 5})
    args = (words, fixations, PARTICIPANT, "multipart_demo")
    for selection, expected in (
        (None, {"intro": 2, "question": 5}),
        (["question"], {"question": 5}),
    ):
        result = api.render_parent_trial(*args, screens=selection)
        assert {
            name: fig.layout.meta["screen_index"] for name, fig in result.items()
        } == expected


@pytest.mark.parametrize("width", [0, 1, 6])
def test_heart_outline_keeps_the_center_size_and_uses_the_stroke_width(width):
    marker = dict(size=[12], color="blue", line=dict(color="magenta", width=width))
    layers = plots._glyph_layers(marker, "♥", 1)
    fill = 12 * plots.FIXATION_GLYPH_SIZE_SCALE
    assert layers[-1]["textfont"]["size"] == [fill]
    if width:
        assert layers[0]["textfont"]["size"] == [
            fill + 2 * plots.FIXATION_GLYPH_SIZE_SCALE * width
        ]
    else:
        assert len(layers) == 1


@pytest.mark.parametrize("layout", ["overlay", "side_by_side"])
def test_two_readers_share_a_relative_marker_scale(layout):
    words, fixations = load_synthetic_data()
    a = fixations.head(2).assign(duration_ms=[100, 300])
    b = a.assign(participant_id="B", duration_ms=[300, 900])
    fig = api.compare_scanpaths(
        pd.concat([words, words.assign(participant_id="B")]),
        pd.concat([a, b]),
        (PARTICIPANT, TRIAL),
        ("B", TRIAL),
        layout=layout,
        marker_size_scale="relative",
        marker_size_range=(8, 32),
    )
    traces = [
        t
        for t in fig.data
        if t.mode == "markers"
        and np.ndim(t.marker.size) == 1
        and len(t.marker.size) == 2
    ]
    assert [list(t.marker.size) for t in traces] == [[8, 14], [14, 32]]


def test_dwell_uses_recorded_ids_including_blanks_and_batches_the_same_colors(
    monkeypatch,
):
    import plotly.colors

    words, fixations = load_synthetic_data()
    words = words.iloc[:2].copy()
    a, b = words.word_id.tolist()
    fixations = fixations.iloc[:3].assign(
        word_id=[b, a, np.nan],
        duration_ms=[100, 200, 500],
        x=[words.x.iloc[0] + 1, words.x.iloc[1] + 1, words.x.iloc[0] + 1],
        y=words.y.iloc[0] + 1,
    )
    assert plots._word_heatmap_values(words, fixations, fixations.duration_ms) == {
        str(a): 200,
        str(b): 100,
    }
    assert (
        plots._word_heatmap_values(
            words,
            fixations.assign(word_id=np.nan, **{data.FIX_WORD_ID_MAPPED: True}),
            None,
        )
        == {}
    )
    geometric = fixations.drop(columns="word_id")
    assert plots._word_heatmap_values(words, geometric, None) == {str(a): 2, str(b): 1}
    calls = []
    sample = plotly.colors.sample_colorscale

    def spy(cmap, positions, **kwargs):
        calls.append(len(positions))
        return sample(cmap, positions, **kwargs)

    monkeypatch.setattr(plotly.colors, "sample_colorscale", spy)
    static = go.Figure()
    rects = plots._add_word_level_heatmap(
        static,
        words,
        fixations,
        x_field="x",
        y_field="y",
        weights=fixations.duration_ms,
        heatmap_colorscale="Viridis",
        heatmap_range=(0, 200),
        heatmap_norm="Log",
        show_colorbars=True,
    )
    values, low, high, title = plots._comparison_word_heatmap_data(
        [{"trial_words": words, "trial_fix": fixations}],
        metric="duration_ms",
        heatmap_range=(0, 200),
        heatmap_norm="Log",
    )
    compare = plots._comparison_heatmap_shapes(
        words,
        values[0],
        heatmap_colorscale="Viridis",
        heatmap_norm="Log",
        z_min=low,
        z_max=high,
    )
    assert compare == rects
    assert calls == [2, 2]
    bars = (
        static.data[-1].marker.colorbar,
        plots._comparison_heatmap_colorbar_trace(
            colorscale="Viridis",
            z_min=low,
            z_max=high,
            title=title,
            heatmap_norm="Log",
            colorbar_style={},
        ).marker.colorbar,
    )
    for bar in bars:
        assert tuple(bar.ticktext) == ("0", "50", "100", "150", "200")
        np.testing.assert_allclose(bar.tickvals, np.log1p([0, 50, 100, 150, 200]))
    assert plots._heatmap_ticks(0, np.log1p(2), "Log", counts=True)["ticktext"] == [
        "0",
        "1",
        "2",
    ]


@pytest.mark.parametrize(
    ("onsets", "durations", "flag", "expected", "recorded", "end"),
    [
        ([1000, 1200], [80, 800], None, [0, 200], True, 1000),
        ([0, 1, 2], [100, 200, 50], None, [0, 100, 300], False, 350),
        ([0, 1, 2], [100, 200, 50], False, [0, 1, 2], True, 201),
        ([10, np.nan], [80, 800], False, [0, 80], False, 880),
        ([42], [100], None, [0], True, 100),
    ],
)
def test_recorded_or_estimated_time_agrees_in_replay_axis_and_summary(
    onsets, durations, flag, expected, recorded, end
):
    _, fixations = load_synthetic_data()
    frame = (
        fixations.iloc[: len(onsets)]
        .assign(timestamp_ms=onsets, duration_ms=durations)
        .drop(columns=data.TIMESTAMP_SYNTHESIZED, errors="ignore")
    )
    if flag is not None:
        frame[data.TIMESTAMP_SYNTHESIZED] = flag
    times, known = measures.fixation_clock(frame)
    assert bool(known) is recorded
    assert list(times) == expected
    axis = chart_axes.recorded_onsets(frame)
    assert bool(axis.notna().all()) is recorded
    summary = aggregation._trial_reading_time_ms(frame).iloc[0]
    assert summary.reading_time_ms == end
    assert (
        summary.reading_time_source == aggregation.READING_TIME_RECORDED
    ) is recorded
    spec = plots._scanpath_anim_specs([(frame, "red", "A")], (8, 32))[0]
    assert list(spec["onsets"]) == expected
    assert spec["end"] == end


@pytest.mark.parametrize("speed", [1, 2])
def test_capped_gif_paints_no_future_marker_before_ending_on_the_whole_scanpath(
    speed, monkeypatch
):
    words, fixations = load_synthetic_data()
    fixations = fixations.head(3).assign(
        timestamp_ms=[0, 500, 900], duration_ms=[100, 100, 95]
    )
    fig = api.animate_scanpath(
        words, fixations, PARTICIPANT, TRIAL, playback_speed=speed
    )

    def raster(replay, *, frame_indices, **kwargs):
        frames = []
        for index in frame_indices:
            markers = next(
                t
                for t in replay.frames[index].data
                if t.mode == "markers" and len(t.x) == len(fixations)
            )
            img = Image.new("RGB", (3, 1), "white")
            for j, value in enumerate(markers.x):
                if value is not None and np.isfinite(value):
                    img.putpixel((j, 0), (0, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            frames.append(buf.getvalue())
        return frames, (3, 1)

    monkeypatch.setattr(animation_export, "render_png_frames", raster)
    gif = animation_export.export_animation(fig, fmt="gif", max_frames=2)
    elapsed = 0
    with Image.open(io.BytesIO(gif)) as image:
        last = image.n_frames - 1
        for i in range(image.n_frames):
            image.seek(i)
            rgb = image.convert("RGB")
            painted = [rgb.getpixel((j, 0)) == (0, 0, 0) for j in range(3)]
            if i == last:
                # The final image holds until the replay ends: all of it shows.
                assert all(painted)
            else:
                for shown, onset in zip(painted, (0, 500, 900), strict=True):
                    if shown:
                        assert onset <= elapsed * speed
            elapsed += image.info["duration"]
    assert elapsed == pytest.approx(995 / speed, abs=10)


def _config(state, **settings):
    base = asdict(plots.FigureSettings(800, 600, 16))
    return plot_config.build_plot_config(
        selected_participant=PARTICIPANT,
        selected_trial=TRIAL,
        canvas_width=800,
        canvas_height=600,
        x_field="x",
        y_field="y",
        figure_settings=base,
        viz_settings={**base, "heatmap_metric": "counts", **settings},
        base_font_size=16,
        font_family="Arial",
        trial_raw_gaze=pd.DataFrame(),
        data_source="Pilot",
        app_version="test",
        exported_at="now",
        state=state,
    )


def test_reopening_saved_file_keeps_both_windows_and_linguistic_notation():
    from scanpath_studio.url_state import _parse_figure_text
    from tests.test_plot_config_restore import _restore_app, _run

    words, fixations = load_synthetic_data()
    state = {
        "single_compare_toggle": True,
        "_share_selection": {
            "compare": {"participant_id": "B", "trial_id": TRIAL},
            "full_fix_range": (1, 9),
            "compare_full_fix_range": (1, 9),
        },
        "single_fix_range": (2, 4),
        "single_fix_range_user_set": True,
        "single_compare_fix_range": (5, 8),
        "single_compare_fix_range_user_set": True,
        "global_show_title": True,
        "global_show_caption": True,
    }
    label = "Reading the <NP> & סמיכות"
    cfg = json.loads(
        json.dumps(_config(state, title_pattern=label, caption_pattern=label))
    )
    both = pd.concat([fixations, fixations.assign(participant_id="B")])
    restored = _run(_restore_app, _fix=both.to_dict("list"), _config=cfg).session_state
    windows = [restored[k] for k in ("single_fix_range", "single_compare_fix_range")]
    assert windows == [(2, 4), (5, 8)]
    assert (
        _parse_figure_text(label)
        == restored["global_title_pattern"]
        == restored["global_caption_pattern"]
        == label
    )
    fig = api.plot_scanpath(
        words,
        fixations,
        PARTICIPANT,
        TRIAL,
        title=restored["global_title_pattern"],
        fix_index_range=windows[0],
    )
    assert "&lt;NP&gt;" in fig.layout.title.text
    assert len(next(t for t in fig.data if t.name == "Fixations").x) == 3
    for key in ("single_fix_range_user_set", "single_compare_fix_range_user_set"):
        assert restored[key]


def test_headless_settings_writer_never_imports_the_share_ui():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from tests.test_publication_fidelity import _config; _config({}); print('scanpath_studio.url_state' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize(
    ("enabled", "usable", "expected"),
    [(True, True, "raw gaze"), (False, True, "none"), (True, False, "none")],
)
def test_raw_only_export_caption_tracks_the_visible_samples(enabled, usable, expected):
    _, fixations = load_synthetic_data()
    raw = (
        fixations[["participant_id", "trial_id", "x", "y", "timestamp_ms"]]
        .head(3)
        .copy()
    )
    if not usable:
        raw["x"] = np.nan
    settings = dict(
        show_words=False,
        show_word_labels=False,
        show_fixations=False,
        show_saccades=False,
        show_heatmap=False,
        show_raw_gaze=enabled,
        caption_pattern="{settings}",
    )
    blob, _ = export.bulk_export(
        raw[["participant_id", "trial_id"]].drop_duplicates(),
        data.empty_words_frame(),
        data.empty_fixations_frame(),
        canvas_width=800,
        canvas_height=600,
        x_field="x",
        y_field="y",
        base_font_size=16,
        font_family="Arial",
        settings=settings,
        options=export.ExportOptions(
            include_html=True,
            include_svg=False,
            include_png=False,
            caption_pattern="{settings}",
        ),
        raw_gaze=raw,
    )
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        cfg = json.loads(
            archive.read(
                next(p for p in archive.namelist() if p.endswith("plot_config.json"))
            )
        )
        assert f"layers: {expected}" in cfg["figure_text"]["caption"].lower()


def test_categorical_colors_survive_order_subsets_and_a_literal_missing_label():
    values = pd.Series(
        ["verb", "noun", "(missing)", None, *(f"class {i}" for i in range(20))],
        dtype="category",
    )
    forward, key = plots._resolve_marker_colors(values, False)
    reverse, _ = plots._resolve_marker_colors(values[::-1], False)
    assert forward == reverse[::-1]
    # "noun" and "verb" prefer one palette slot; "noun" sorts first and keeps it.
    noun = plots._resolve_marker_colors(values.iloc[[1]], False)[0]
    verb_and_noun = plots._resolve_marker_colors(values.iloc[[0, 1]], False)[0]
    assert verb_and_noun[1] == noun[0] != verb_and_noun[0]
    assert forward[2] != forward[3]
    assert len(set(forward)) == len(values)
    assert {"(missing)", "(missing) (no value)"} <= dict(key).keys()
    # Two scanpaths share the mapping one figure of their labels would give.
    first_four, _ = plots._resolve_marker_colors(values.iloc[:4], False)
    sides, legend = plots._shared_category_colors([values.iloc[:3], values.iloc[1:4]])
    assert sides == [first_four[:3], first_four[1:4]]
    assert dict(legend)["noun"] == first_four[1]


def test_index_connector_styles_the_line_and_gates_only_spatial_controls():
    from tests.test_rail_mode_choices import _rail, _rerun, _static

    at = _rail(
        global_x_field="order_in_trial",
        global_y_field="y",
        global_saccade_style="Dashed",
        global_saccade_width=6.0,
        global_saccade_opacity=0.45,
        global_saccade_color_mode="By type",
        global_saccade_render_mode="Arc",
        global_show_saccade_arrows=True,
    )
    assert not at.selectbox(key="global_saccade_style").disabled
    assert at.selectbox(key="global_saccade_color_mode").disabled
    assert at.checkbox(key="global_show_saccade_arrows").disabled
    trace = next(
        t
        for t in _static(at, x_field="order_in_trial", y_field="y").data
        if t.name == "Fixation sequence"
    )
    assert trace.line.width == 6 and trace.line.dash == "dash" and trace.opacity == 0.45
    at.session_state["global_x_field"] = "x"
    _rerun(at)
    assert (
        at.session_state["global_saccade_render_mode"] == "Arc"
        and at.session_state["global_show_saccade_arrows"]
    )


def test_redaction_lists_selected_free_text_and_omitting_it_removes_the_payload(
    tmp_path,
):
    from scanpath_studio.controls import selected_hover_text

    words, fixations = load_synthetic_data()
    canary = "harmless-lab-wording-47653"
    words = words.assign(wording_for_editor=canary)
    fixations = fixations.assign(condition=["pilot"] * len(fixations))
    fields = ["text", "wording_for_editor", "word_id", "height"]
    assert selected_hover_text(
        words, fixations, fields, ["duration_ms", "condition"]
    ) == ["Words · wording_for_editor", "Fixations · condition"]
    for chosen, retained in ((fields, True), (["text", "word_id", "height"], False)):
        fig = api.plot_scanpath(
            words,
            fixations,
            PARTICIPANT,
            TRIAL,
            redact_text=True,
            word_hover_fields=chosen,
        )
        html = api.save_figure(fig, tmp_path / "redacted.html").read_text()
        assert (canary in html) is retained


def test_screen_reader_summary_counts_visible_marker_or_raw_coordinate_pairs():
    from scanpath_studio import tabs

    words, fixations = load_synthetic_data()
    figure = api.plot_scanpath(
        words,
        fixations,
        PARTICIPANT,
        TRIAL,
        fixation_flags={"short": {"mode": "Hide", "threshold_ms": 160}},
    )
    assert "1 fixation shown of 9 recorded" in tabs._scanpath_alt("A", "T", 9, figure)
    raw = fixations.iloc[:4][
        ["participant_id", "trial_id", "x", "y", "timestamp_ms"]
    ].copy()
    raw.loc[raw.index[1], "x"] = np.nan
    figure = api.plot_scanpath(
        data.empty_words_frame(),
        data.empty_fixations_frame(),
        PARTICIPANT,
        TRIAL,
        raw_gaze=raw,
        show_raw_gaze=True,
    )
    assert "3 raw gaze samples, no fixations recorded" in tabs._scanpath_alt(
        "A", "T", 0, figure
    )
    chart = api.plot_scanpath(
        words,
        fixations,
        PARTICIPANT,
        TRIAL,
        x_field="order_in_trial",
        y_field="y",
        fix_index_range=(2, 4),
    )
    description = tabs._scanpath_alt("A", "T", 9, chart)
    assert (
        chart.layout.xaxis.title.text in description
        and "3 fixations shown of 9 recorded" in description
    )
