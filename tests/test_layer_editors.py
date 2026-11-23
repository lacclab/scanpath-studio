"""The layer menus keep common controls visible and group the detailed settings."""

from __future__ import annotations

from plotly.colors import get_colorscale
from streamlit.testing.v1 import AppTest

from scanpath_studio import tabs
from scanpath_studio.code_snippet import SNIPPET_STATE_KEY
from scanpath_studio.constants import CUSTOM_PALETTE, DEFAULT_PALETTE, palette_settings
from tests.conftest import APP_SCRIPT


def _app(source: str = "synthetic"):
    app = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    app.query_params.update({"ui": "full", "source": source})
    return app.run()


def _menu(app, layer):
    return next(m for m in app.get("popover") if m.key == f"plot_menu_{layer}")


def _previews(app, layer):
    return [
        item.value for item in _menu(app, layer).html if "linear-gradient" in item.value
    ]


def test_each_layer_exposes_its_common_controls_before_the_details():
    app = _app()
    assert not app.exception
    menus = {menu.key: menu for menu in app.get("popover")}
    for layer, common, details in (
        (
            "fix",
            ("global_color_by", "global_marker_size_range", "global_show_order"),
            (
                "plot_detail_fix_marker",
                "plot_detail_fix_duration",
                "plot_detail_fix_colors",
                "plot_detail_fix_position",
            ),
        ),
        (
            "sac",
            ("global_saccade_width", "global_show_saccade_arrows"),
            ("plot_detail_sac_line",),
        ),
        (
            "stim",
            ("global_show_labels", "global_redact_text"),
            (
                "plot_detail_stim_text",
                "plot_detail_stim_highlight",
                "plot_detail_stim_image",
            ),
        ),
        (
            "heatmap",
            ("global_heatmap_metric", "global_heatmap_style", "global_heatmap_opacity"),
            ("plot_detail_heat_scale", "plot_detail_heat_bar"),
        ),
        (
            "rawgaze",
            ("global_raw_gaze_marker_size", "global_raw_gaze_opacity"),
            ("plot_detail_raw_color",),
        ),
        ("boxes", ("global_word_box_color", "global_word_box_fill_color"), ()),
    ):
        menu = menus[f"plot_menu_{layer}"]
        sections = list(menu.expander)
        assert tuple(section.key for section in sections) == details
        controls = {element.key for element in menu}
        nested = {element.key for section in sections for element in section}
        assert set(common) <= controls - nested


def test_undo_restores_marker_shape_inside_its_disclosure():
    app = _app()
    shape = "global_fixation_symbol"
    app.selectbox(key=shape).set_value("diamond").run()
    assert app.session_state[shape] == "diamond"
    app.button(key="viz_undo").click().run()
    assert app.selectbox(key=shape).value == "circle"
    app.button(key="viz_redo").click().run()
    assert app.selectbox(key=shape).value == "diamond"
    assert not app.exception


def test_saccade_style_previews_keep_the_same_choices_for_both_readings():
    app = _app("demo")
    style = app.selectbox(key="global_saccade_style")
    previews = style.options
    assert previews == ["━━━━ Solid", "━ ━ ━ Dashed", "······ Dotted", "━·━·━ Dash-dot"]
    style.set_value("Dotted").run()
    assert app.session_state["global_saccade_style"] == "Dotted"
    app.toggle(key="single_compare_toggle").set_value(True).run()
    for idx in (0, 1):
        assert app.selectbox(key=f"cmp{idx}_saccade_style").options == previews
    app.selectbox(key="cmp1_saccade_style").set_value("Dash-dot").run()
    assert app.session_state["cmp1_saccade_style"] == "Dash-dot"
    assert not app.exception


def test_only_active_color_scales_show_their_plotly_stops():
    app = _app("demo")
    assert _previews(app, "fix") == _previews(app, "heatmap") == []
    app.selectbox(key="global_color_by").set_value("duration_ms").run()
    app.toggle(key="global_show_heatmap").set_value(True).run()
    next(s for s in _menu(app, "fix").selectbox if s.label == "Colorscale").set_value(
        "Viridis"
    ).run()
    assert len(_previews(app, "fix")) == len(_previews(app, "heatmap")) == 1
    fixation_scale = _previews(app, "fix")[0]
    assert "Viridis color scale, low to high" in fixation_scale
    for position, color in get_colorscale("Viridis"):
        assert f"{color} {position * 100:g}%" in fixation_scale
    assert app.session_state["global_palette"] == CUSTOM_PALETTE
    assert (
        app.session_state[SNIPPET_STATE_KEY].settings["fixation_colorscale"]
        == "Viridis"
    )

    app.selectbox(key="global_color_by").set_value("line").run()
    assert _previews(app, "fix") == []
    assert not app.exception


def test_compare_heatmap_scales_inherit_the_palette_until_a_reading_gets_its_own():
    app = _app("demo")
    app.button(key="viz_view_heatmap").click().run()
    app.toggle(key="single_compare_toggle").set_value(True).run()
    assert app.button(key="viz_view_heatmap").proto.type == "primary"
    assert "cmp0_heatmap_colorscale" not in app.session_state
    assert "cmp1_heatmap_colorscale" not in app.session_state

    def b_picker():
        return next(
            s for s in _menu(app, "heatmap").selectbox if "Scanpath B" in s.label
        )

    b_picker().set_value("Plasma").run()
    both_scales = _previews(app, "heatmap")
    assert len(both_scales) == 2
    assert "Blues color scale" in both_scales[0]
    assert "Plasma color scale" in both_scales[1]
    assert app.button(key="viz_view_custom").proto.type == "primary"
    assert app.session_state["global_palette"] == DEFAULT_PALETTE
    assert "cmp0_heatmap_colorscale" not in app.session_state
    assert (
        app.session_state[SNIPPET_STATE_KEY].settings["style_b"]["heatmap_colorscale"]
        == "Plasma"
    )
    b_picker().set_value("Blues").run()
    assert app.session_state["cmp1_heatmap_colorscale"] == ""
    assert (
        not app.session_state[SNIPPET_STATE_KEY]
        .settings["style_b"]
        .get("heatmap_colorscale")
    )
    app.button(key="viz_palette_high_contrast").click().run()
    inherited = palette_settings("High contrast")["heatmap_colorscale"]
    assert all(
        f"{inherited} color scale" in scale for scale in _previews(app, "heatmap")
    )
    assert not app.exception


def test_heatmap_scale_updates_the_palette_view_and_figure_in_one_rerun(monkeypatch):
    figures = []
    render_chart = tabs._render_true_scale_chart

    def capture_chart(fig, **kwargs):
        figures.append(fig)
        return render_chart(fig, **kwargs)

    monkeypatch.setattr(tabs, "_render_true_scale_chart", capture_chart)
    app = _app("demo")
    app.button(key="viz_view_heatmap").click().run()
    app.selectbox(key="plot_setting_finder").set_value(
        "Heatmap measure, colors and opacity"
    ).run()
    assert app.session_state["plot_menu_heatmap"]

    def picker():
        return next(s for s in _menu(app, "heatmap").selectbox if s.label == "Colors")

    def check(scale, palette, view):
        assert picker().value == scale
        assert app.session_state["global_palette"] == palette
        assert app.button(key=f"viz_view_{view}").proto.type == "primary"
        assert (
            app.session_state[SNIPPET_STATE_KEY].settings["heatmap_colorscale"] == scale
        )
        colorbar = next(t for t in figures[-1].data if t.name == "heatmap colorbar")
        assert [color for _, color in colorbar.marker.colorscale] == [
            color for _, color in get_colorscale(scale)
        ]
        assert not app.exception

    picker().set_value("Hot").run()
    check("Hot", CUSTOM_PALETTE, "custom")
    app.button(key="viz_undo").click().run()
    check("Blues", DEFAULT_PALETTE, "heatmap")
    app.button(key="viz_redo").click().run()
    check("Hot", CUSTOM_PALETTE, "custom")
    app.button(key="viz_palette_high_contrast").click().run()
    check(
        palette_settings("High contrast")["heatmap_colorscale"],
        "High contrast",
        "custom",
    )
    picker().set_value("Hot").run()
    check("Hot", CUSTOM_PALETTE, "custom")
