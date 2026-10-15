"""Export the settings and layers a researcher actually chose."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from scanpath_studio import api, export
from scanpath_studio import code_snippet as cs
from scanpath_studio.url_state import PLOT_CONFIG_SCHEMA


def _frames():
    words, fixations = api.build_authored_scanpath("A short test")
    return words.assign(participant_id="p", trial_id="t"), fixations.assign(
        participant_id="p", trial_id="t"
    )


def _bundle(monkeypatch, words, fixations, settings, **kwargs):
    captured = []
    build = export.make_scanpath_figure

    def capture(*args, **kw):
        fig = build(*args, **kw)
        captured.append(fig)
        return fig

    monkeypatch.setattr(export, "make_scanpath_figure", capture)
    data, progress = export.bulk_export(
        pd.DataFrame({"participant_id": ["p"], "trial_id": ["t"]}),
        words,
        fixations,
        canvas_width=1200,
        canvas_height=800,
        base_font_size=18,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=settings,
        options=export.ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=True,
        ),
        **kwargs,
    )
    assert not progress.errors
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        config = json.loads(z.read("per_trial/p__t/plot_config.json"))
    return captured[0], config


@pytest.mark.parametrize(
    "mode,visible", [("Auto", True), ("Show", True), ("Hide", False)]
)
def test_bundle_discloses_its_transformed_geometry(monkeypatch, mode, visible):
    words, fixations = _frames()
    fig, config = _bundle(
        monkeypatch,
        words,
        fixations,
        {
            "fixation_snap_to_line": True,
            "saccade_render_mode": "Arc",
            "illustration_label": mode,
        },
    )
    assert bool((fig.layout.meta or {}).get("illustration")) is visible
    assert bool(config["illustration"]["reasons"]) is visible
    assert config["illustration"]["label_mode"] == mode


def test_bundle_uses_its_own_image_and_manual_placement(monkeypatch, tmp_path):
    path = tmp_path / "page.png"
    Image.new("RGB", (32, 24)).save(path)
    words, fixations = _frames()
    words = words.assign(image_path=str(path), image_x=10, image_y=20)
    fig, config = _bundle(
        monkeypatch,
        words,
        fixations,
        {
            "show_stimulus_image": True,
            "stimulus_image_offset_x": 3,
            "stimulus_image_offset_y": -4,
            "stimulus_image_scale": 2,
            "stimulus_image_opacity": 0.4,
        },
    )
    (image,) = fig.layout.images
    assert (image.x, image.y, image.sizex, image.sizey, image.opacity) == (
        13,
        16,
        64,
        48,
        0.4,
    )
    assert config["layers"]["stimulus_image"] is True
    assert config["coloring"]["stimulus_image_scale"] == 2


def test_app_image_permission_check_also_applies_to_bundle(monkeypatch, tmp_path):
    path = tmp_path / "private.png"
    Image.new("RGB", (32, 24)).save(path)
    words, fixations = _frames()
    words = words.assign(image_path=str(path))
    calls = []

    def refuse(words, fixations):
        calls.append(len(words))

    fig, config = _bundle(
        monkeypatch,
        words,
        fixations,
        {"show_stimulus_image": True},
        stimulus_image_resolver=refuse,
    )
    assert calls
    assert not fig.layout.images
    assert config["layers"]["stimulus_image"] is False


def _restore_bundle():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.url_state import (
        _restore_plot_config,
        apply_pending_preprocessing,
    )

    combos = pd.DataFrame({"participant_id": ["p"], "trial_id": ["t"]})
    fix = pd.DataFrame({"x": [1.0], "y": [1.0], "duration_ms": [200.0]})
    _restore_plot_config(st.session_state["config"], combos, fix)
    apply_pending_preprocessing()


def test_bundle_settings_restore_the_rendered_style(monkeypatch):
    words, fixations = _frames()
    settings = {
        "saccade_opacity": 0.2,
        "saccade_style": "dash",
        "background_color": "#222222",
        "fixation_snap_to_line": True,
        "fixation_snap_position": 0.4,
        "word_box_fill_color": "#ff0000",
        "word_box_fill_opacity": 0.6,
        "fixation_outline_width": 2,
        "heatmap_opacity": 0.3,
        "show_plot_frame": False,
        "fixation_flags": {"long": {"mode": "Discard", "threshold_ms": 500}},
        "preprocessing": {"discard_blink_adjacent": False},
    }
    _, config = _bundle(monkeypatch, words, fixations, settings)
    assert config["schema"] == PLOT_CONFIG_SCHEMA
    assert config["mode"] == {"animate": False, "compare": False}
    at = AppTest.from_function(_restore_bundle)
    at.session_state["config"] = config
    at.run()
    assert not at.exception
    for key, expected in {
        "global_saccade_opacity": 0.2,
        "global_saccade_style": "Dashed",
        "global_bg_custom": "#222222",
        "global_fixation_snap_to_line": True,
        "global_fixation_snap_position": 0.4,
        "global_word_box_fill_color": "#ff0000",
        "global_word_box_fill_opacity": 0.6,
        "global_fixation_outline_width": 2,
        "global_heatmap_opacity": 0.3,
        "global_show_plot_frame": False,
        "global_fixclass_long_mode": "Discard",
        "global_base_font_size": 18,
        "global_font_family": "Arial",
        "global_preproc_blink_adjacent": False,
    }.items():
        assert at.session_state[key] == expected, key


def test_bundle_preserves_raw_gaze_style_with_sample_provenance(monkeypatch):
    words, fixations = _frames()
    raw = pd.DataFrame(
        {"participant_id": ["p"], "trial_id": ["t"], "x": [10.0], "y": [20.0]}
    )
    _, config = _bundle(
        monkeypatch,
        words,
        fixations,
        {
            "raw_gaze_color": "#ff0000",
            "raw_gaze_marker_size": 9,
            "raw_gaze_opacity": 0.25,
            "raw_gaze_synthesized": True,
        },
        raw_gaze=raw,
    )
    assert config["raw_gaze"] == {
        "available": True,
        "points": 1,
        "synthesized": True,
        "color": "#ff0000",
        "marker_size": 9,
        "opacity": 0.25,
    }


def test_share_code_keeps_custom_word_highlight_and_hover(tmp_path):
    words, fixations = _frames()
    words = words.assign(my_span=[True, False, True], my_word_score=[1.1, 2.2, 3.3])
    words_path, fix_path = tmp_path / "words.csv", tmp_path / "fixations.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)
    source = cs.SnippetSource(
        kind=cs.SOURCE_FILES,
        options={
            "words": [str(words_path)],
            "fixations": [str(fix_path)],
        },
    )
    state = cs.FigureState(
        kind="static",
        participant="p",
        trial="t",
        settings={
            **api.figure_options(),
            "highlight_column": "my_span",
            "word_hover_fields": ["text", "my_word_score"],
        },
    )
    namespace = {}
    exec(cs.python_snippet(source, state), namespace)  # noqa: S102 - execute the generated recipe
    assert {"my_span", "my_word_score"} <= set(namespace["words"])
    assert any(
        "my_word_score" in (t.hovertemplate or "") for t in namespace["fig"].data
    )
    assert "--keep-columns" in cs.cli_snippet(source, state)[0]
