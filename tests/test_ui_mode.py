from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import session_keys as sk
from scanpath_studio import tabs, ui_mode
from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view

SWITCH = "ui_mode_switch"
SYNTHETIC_SOURCE = "Synthetic test trial"


@pytest.mark.parametrize(
    ("param", "cookie", "expected"),
    [
        (None, None, "simple"),
        (None, "advanced", "advanced"),
        ("advanced", "simple", "advanced"),
        ("SIMPLE", "advanced", "simple"),
        (" Advanced ", None, "advanced"),
        ("foo", "advanced", "advanced"),
        ("", None, "simple"),
        ("foo", "bar", "simple"),
    ],
)
def test_resolve_mode_precedence(param, cookie, expected):
    assert ui_mode.resolve_mode(param, cookie) == expected


@pytest.mark.parametrize("value", [None, 3, ["advanced"], b"advanced", object()])
def test_parse_mode_never_raises_on_a_non_string(value):
    assert ui_mode.parse_mode(value) is None


def test_seed_mode_reads_the_link_then_the_cookie():
    assert ui_mode.seed_mode({}, {sk.PARAM_UI: "advanced"}, {}) == "advanced"
    cookies = {sk.UI_MODE_COOKIE: "advanced"}
    assert ui_mode.seed_mode({}, {}, cookies) == "advanced"
    assert ui_mode.seed_mode({}, {}, {}) == "simple"


def test_seed_mode_writes_the_session_key():
    session: dict = {}
    ui_mode.seed_mode(session, {sk.PARAM_UI: "advanced"}, {})
    assert session[sk.UI_MODE] == "advanced"


def test_seed_mode_keeps_an_existing_session_choice():
    session = {sk.UI_MODE: "advanced"}
    assert ui_mode.seed_mode(session, {sk.PARAM_UI: "simple"}, {}) == "advanced"


def test_cookie_script_sets_a_year_long_cookie():
    script = ui_mode.cookie_script("advanced")
    assert "sps_ui_mode=advanced" in script
    assert "max-age=31536000" in script and "path=/" in script
    assert "SameSite=Lax" in script


def test_cookie_script_only_embeds_a_valid_mode():
    script = ui_mode.cookie_script('x"; alert(1); "')
    assert "sps_ui_mode=simple" in script and "alert" not in script


def test_seed_mode_replaces_a_junk_session_value():
    session = {sk.UI_MODE: "junk"}
    assert ui_mode.seed_mode(session, {sk.PARAM_UI: "advanced"}, {}) == "advanced"
    assert session[sk.UI_MODE] == "advanced"


def test_ui_param_alone_is_not_a_link():
    assert not ui_mode.has_link_params({"ui": "simple"})
    assert ui_mode.has_link_params({"ui": "simple", "trial": "3"})
    assert not ui_mode.has_link_params({})


def test_mode_css_hides_the_other_mode():
    simple = ui_mode.mode_css("simple")
    assert "st-key-adv_only_" in simple and "st-key-simple_only_" not in simple
    advanced = ui_mode.mode_css("advanced")
    assert "st-key-simple_only_" in advanced and "st-key-adv_only_" not in advanced
    assert "display: none !important" in simple


def _boot(view: str = _VIEW_SCANPATH, mode: str | None = "simple") -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    if mode is None:
        del at.query_params["ui"]  # the conftest pins ?ui=advanced
    else:
        at.query_params["ui"] = mode
    pin_view(at, view)
    at.run()
    assert not at.exception
    return at


def test_fresh_session_is_simple():
    at = _boot(mode=None)
    assert at.session_state["ui_mode"] == "simple"
    assert at.segmented_control(key=SWITCH).value == "simple"


def test_switch_flips_mode_and_keeps_every_value():
    at = _boot()
    assert at.session_state["ui_mode"] == "simple"
    prefixes = ("global_", "single_", "filter_")

    def snapshot() -> dict:
        return {
            k: at.session_state[k] for k in at.session_state if k.startswith(prefixes)
        }

    before = snapshot()
    assert before
    at.segmented_control(key=SWITCH).set_value("advanced").run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["_ui_mode_chosen"] is True
    assert snapshot() == before
    at.segmented_control(key=SWITCH).set_value("simple").run()
    assert at.session_state["ui_mode"] == "simple"


def test_ui_param_does_not_write_the_cookie():
    at = _boot(mode="advanced")
    assert at.session_state["ui_mode"] == "advanced"
    assert "_ui_mode_chosen" not in at.session_state


def _switch_style(at: AppTest) -> str:
    """The ``<style>`` the switch's own container draws, which places it."""
    return " ".join(
        str(el.proto.body)
        for el in at.get("html")
        if ui_mode.SWITCH_BOX_KEY in str(el.proto.body)
    )


@pytest.mark.parametrize("view", [_VIEW_SCANPATH, _VIEW_CORPUS, _VIEW_DATA])
def test_switch_is_drawn_on_every_view_but_shown_on_scanpath(view):
    at = _boot(view)
    # Drawn on every run, so nothing above a view shifts with the view.
    assert at.segmented_control(key=SWITCH).value == "simple"
    style = _switch_style(at)
    assert ("position: fixed" in style) == (view == _VIEW_SCANPATH)
    assert ("display: none !important" in style) == (view != _VIEW_SCANPATH)


def test_switch_css_lifts_the_switch_into_the_top_bar():
    css = ui_mode.switch_css(True)
    box = ".st-key-tour_grp_ui_mode"
    assert f"{box} {{ position: fixed;" in css
    assert f"z-index: {ui_mode.SWITCH_Z_INDEX}" in css
    assert 'data-testid="stMainMenu"' in css
    # Bigger than the default control: 1rem text, 2.5rem tall.
    assert "min-height: 2.5rem" in css and "font-size: 1rem" in css
    # The title row that holds it leaves the flow.
    assert "position: absolute" in css and "height: 0" in css
    # Below the fallback width it is an in-flow, right-aligned row.
    assert f"@media (max-width: {ui_mode._SWITCH_FALLBACK_PX}px)" in css
    assert "align-items: flex-end" in css


def test_switch_stacks_between_the_header_and_the_tour():
    """Above Streamlit's header (999990), whose bar it sits in; under the tour's
    card and tab, so a running tour is never covered; under Streamlit's popovers
    and modals (1000060 and up)."""
    from scanpath_studio import tour

    header = 999990
    assert header < ui_mode.SWITCH_Z_INDEX < tour.GUIDE_Z_INDEX < 1000060
    assert f"z-index: {tour.GUIDE_Z_INDEX};" in tour._CARD_CSS
    assert f"z-index: {tour.GUIDE_Z_INDEX};" in tour._GUIDE_MOVE_CSS
    # The welcome step's backdrop stays under the header, as the nav is.
    assert "z-index: 999980;" in tour._WELCOME_CSS


def test_switch_leaves_room_for_the_status_widget():
    """Streamlit's "Running…" widget sits left of the ⋮ menu, where the switch
    would otherwise be: the switch moves left by the widget's slot, and the
    header's menu cell grows by the same amount."""
    css = ui_mode.switch_css(True)
    slot = ui_mode._STATUS_SLOT_REM
    assert f"right: calc(3.75rem + {slot}rem)" in css
    assert f"width: {17.5 + slot}rem !important" in css


def test_switch_css_hidden_still_collapses_the_title_row():
    css = ui_mode.switch_css(False)
    assert "display: none !important" in css
    assert "position: fixed" not in css
    assert "position: absolute" in css


def test_deselecting_the_switch_keeps_the_mode():
    at = _boot()
    at.segmented_control(key=SWITCH).set_value(None).run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "simple"
    assert "_ui_mode_chosen" not in at.session_state


def _has_cookie_embed(at: AppTest) -> bool:
    return any("sps_ui_mode" in str(el.proto) for el in at.get("iframe"))


def test_cookie_iframe_is_drawn_only_after_a_click():
    at = _boot()
    assert not _has_cookie_embed(at)
    at.segmented_control(key=SWITCH).set_value("advanced").run()
    assert _has_cookie_embed(at)


def test_more_lists_cover_the_spec():
    more = ui_mode.MORE_IN_ADVANCED
    assert set(more) == {"picker", "rail", "subtabs"}

    def titles(area: str) -> str:
        return " | ".join(title for title, _ in more[area]).lower()

    for word in ("filter", "sort", "slider", "trial summary table"):
        assert word in titles("picker")
    for word in (
        "replay",
        "compare",
        "layer style",
        "filters & highlights",
        "figure & canvas",
        "saved designs",
    ):
        assert word in titles("rail")
    assert [t.split(" ", 1)[1] for t, _ in more["subtabs"]] == [
        "Annotations",
        "Stimulus & context",
        "Comparisons",
        "Export bundle",
    ]
    assert all(line.strip() for items in more.values() for _, line in items)


def test_more_button_switches_to_advanced():
    at = _boot()
    at.button(key="more_to_advanced_picker").click().run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["_ui_mode_chosen"] is True
    assert at.segmented_control(key=SWITCH).value == "advanced"


def test_simple_picker_keeps_every_widget_alive():
    at = _boot()
    assert at.select_slider(key="single_trial_pos") is not None
    popovers = {p.key for p in at.get("popover")}
    assert {"iconpop_sort_trial_single", "iconpop_filter_trials"} <= popovers
    assert "iconpop_more_picker" in popovers


def test_simple_single_trial_dataset_does_not_crash():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.query_params["ui"] = "simple"
    at.session_state["data_source_choice"] = SYNTHETIC_SOURCE
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception
    assert "iconpop_more_picker" in {p.key for p in at.get("popover")}


def test_simple_css_collapses_the_slider_column():
    css = ui_mode.mode_css("simple")
    assert "stColumn" in css and "st-key-adv_only_trial_slider" in css
    assert "st-key-adv_only_trial_slider" not in ui_mode.mode_css("advanced")


def test_compare_pickers_are_never_hidden_in_simple():
    from scanpath_studio import utils

    class Host:
        def container(self, key):
            return ("container", key)

    host = Host()
    assert utils._advanced_part(host, "trial_sort", "single_compare") is host
    assert utils._advanced_part(host, "trial_sort", "single") == (
        "container",
        "adv_only_trial_sort",
    )


def test_simple_css_drops_the_cell_of_the_hidden_sort():
    css = ui_mode.mode_css("simple")
    assert "st-key-adv_only_trial_sort" in css
    assert ":first-child:has(" in css and "margin-left: 0 !important" in css
    assert "st-key-adv_only_trial_sort" not in ui_mode.mode_css("advanced")


def test_more_triggers_are_muted_by_the_stylesheet():
    from scanpath_studio.styles import get_app_css

    css = " ".join(get_app_css().split())
    rule = css.split(
        '[class*="st-key-iconpop_more_"] [data-testid="stPopoverButton"] {'
    )
    assert len(rule) == 2
    body = rule[1].split("}", 1)[0]
    assert "opacity: 0.72" in body and "var(--sps-border)" in body


def _tile_type(at: AppTest, name: str) -> str:
    return at.button(key=f"simple_view_{name}").proto.type


def test_simple_view_animation_turns_animate_on_with_scanpath_layers():
    at = _boot()
    at.button(key="simple_view_heatmap").click().run()
    assert at.session_state["global_show_heatmap"] is True
    at.button(key="simple_view_animation").click().run()
    assert not at.exception
    assert at.session_state["single_animate"] is True
    assert at.session_state["global_show_heatmap"] is False
    assert at.session_state["global_show_fix"] is True
    assert _tile_type(at, "animation") == "primary"
    assert _tile_type(at, "scanpath") == "secondary"


@pytest.mark.parametrize("name", ["heatmap", "illustration"])
def test_simple_view_static_tiles_turn_animate_off(name):
    at = _boot()
    at.button(key="simple_view_animation").click().run()
    assert at.session_state["single_animate"] is True
    at.button(key=f"simple_view_{name}").click().run()
    assert not at.exception
    assert at.session_state["single_animate"] is False
    if name == "heatmap":
        assert at.session_state["global_show_heatmap"] is True
    else:
        assert at.session_state["global_fixation_snap_to_line"] is True
    assert _tile_type(at, name) == "primary"
    assert _tile_type(at, "animation") == "secondary"


@pytest.mark.parametrize(
    ("active", "animating", "expected"),
    [
        ("scanpath", True, "animation"),
        ("scanpath", False, "scanpath"),
        ("heatmap", False, "heatmap"),
        ("illustration", False, "illustration"),
        ("heatmap", True, None),
        ("illustration", True, None),
        ("custom", False, None),
        ("custom", True, None),
        ("design:mine", False, None),
    ],
)
def test_simple_active_view(monkeypatch, active, animating, expected):
    from scanpath_studio import controls

    monkeypatch.setattr(controls, "_active_quick_view", lambda: active)
    assert controls.simple_active_view(animating=animating) == expected


def test_simple_views_are_the_four_tiles():
    from scanpath_studio import controls

    assert controls.SIMPLE_VIEWS == ("animation", "scanpath", "heatmap", "illustration")


def test_simple_rail_keeps_advanced_widgets_alive():
    at = _boot()
    assert at.toggle(key="single_animate") is not None
    assert at.toggle(key="single_compare_toggle") is not None
    assert at.toggle(key="global_show_fix") is not None
    assert at.button(key="reset_viz_settings_btn") is not None
    assert at.button(key="viz_view_custom") is not None
    assert at.selectbox(key="global_palette") is not None
    assert "iconpop_more_rail" in {p.key for p in at.get("popover")}
    for name in ("animation", "scanpath", "heatmap", "illustration"):
        assert at.button(key=f"simple_view_{name}") is not None


def test_advanced_rail_still_draws_the_simple_tiles_hidden():
    """Both modes draw the same tree; CSS hides the other mode's containers."""
    at = _boot(mode="advanced")
    assert at.button(key="simple_view_scanpath") is not None
    assert at.button(key="viz_view_scanpath") is not None


def test_rail_wrappers_are_keyed_for_the_mode_css():
    """Every Advanced-only rail part sits in an ``adv_only_*`` container, and the
    Simple parts in ``simple_only_*`` ones, so `mode_css` hides them."""
    import inspect
    import re

    from scanpath_studio import controls, tabs

    rail = inspect.getsource(tabs.render_single_trial_tab)
    # The two mode rows share one wrapper, so Simple leaves no empty
    # `tour_grp_view_modes` behind.
    for name in ("rail_modes", "rail_reset"):
        assert re.search(rf'advanced_only\(\s*\w+,\s*"{name}"\s*\)', rail), name
    source = inspect.getsource(controls.render_plot_controls)
    for name in (
        "rail_presets",
        "rail_designs",
        "rail_fix",
        "rail_sac",
        "rail_stim",
        "rail_boxes",
        "rail_heatmap",
        "rail_rawgaze",
        "rail_filter",
        "rail_figure",
    ):
        assert re.search(rf'advanced_only\(\s*viz,\s*"{name}"\s*\)', source), name
    assert 'simple_only(viz, "views")' in source
    assert 'simple_only(viz, "rail_more")' in source


def _open_gaze_dataset(words, fixations, gaze, *, mode: str = "simple") -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["ui"] = mode
    pin_view(at, _VIEW_SCANPATH)
    at.session_state["_datasets"] = {
        "Gaze": {
            "words": words,
            "fixations": fixations,
            "raw_gaze": gaze,
            "filter_fields": [],
            "composite_trial_columns": [],
        }
    }
    at.session_state["data_source_choice"] = "Gaze"
    at.run()
    assert not at.exception, at.exception
    return at


def _assert_animation_keeps_the_static_tile(at: AppTest) -> None:
    """Animation asks for the replay, which a trial without fixations cannot
    draw: the static figure stays, and so does its tile."""
    at.button(key="simple_view_animation").click().run()
    assert not at.exception, at.exception
    assert at.session_state["single_animate"] is True
    assert _tile_type(at, "scanpath") == "primary"
    assert _tile_type(at, "animation") == "secondary"


def test_raw_gaze_only_trial_in_simple_highlights_scanpath():
    import pandas as pd

    import scanpath_studio as sps
    from scanpath_studio import api

    words, fixations = api.load_scanpath_data(
        *sps.load_sample_data(names="canonical"), names="canonical"
    )
    gaze = api.load_sample_raw_gaze(names="canonical")
    extra = gaze.assign(trial_id="samples_only", unique_trial_id="samples_only")
    at = _open_gaze_dataset(words, fixations, pd.concat([gaze, extra]))
    picker = at.selectbox(key="single_trial_id")
    picker.set_value(next(o for o in picker.options if "samples_only" in str(o)))
    at.run()
    assert not at.exception, at.exception
    assert "samples_only" in str(at.session_state["single_trial_id"])
    # The trial has no fixations: the fixation layer greys for it.
    assert at.toggle(key="global_show_fix").disabled
    assert _tile_type(at, "scanpath") == "primary"
    _assert_animation_keeps_the_static_tile(at)


def _open_samples_only(mode: str = "simple") -> AppTest:
    from scanpath_studio import api
    from scanpath_studio.data import empty_fixations_frame, empty_words_frame

    return _open_gaze_dataset(
        empty_words_frame(),
        empty_fixations_frame(),
        api.load_sample_raw_gaze(names="canonical"),
        mode=mode,
    )


SIMPLE_TILES = ("animation", "scanpath", "heatmap", "illustration")


def _lit_tiles(at: AppTest) -> list[str]:
    return [name for name in SIMPLE_TILES if _tile_type(at, name) == "primary"]


def test_samples_only_dataset_opens_simple_on_the_scanpath_tile():
    """The raw-gaze layer the dataset turns on is its default, not a setting
    shaped in Advanced, so a fresh session lights Scanpath."""
    at = _open_samples_only()
    assert at.session_state["global_show_raw_gaze"] is True
    assert _lit_tiles(at) == ["scanpath"]
    _assert_animation_keeps_the_static_tile(at)
    assert at.session_state["global_show_raw_gaze"] is True


def test_samples_only_dataset_keeps_the_advanced_highlight():
    """Only Simple's tiles read through the seed; Advanced's presets still
    highlight Custom, as before."""
    at = _open_samples_only("advanced")
    assert at.button(key="viz_view_custom").proto.type == "primary"
    assert at.button(key="viz_view_scanpath").proto.type == "secondary"


def test_samples_only_dataset_with_the_layer_changed_lights_no_tile():
    at = _open_samples_only()
    at.toggle(key="global_show_raw_gaze").set_value(False).run()
    assert not at.exception, at.exception
    assert _lit_tiles(at) == []


def test_samples_only_dataset_with_another_setting_changed_lights_no_tile():
    at = _open_samples_only()
    at.toggle(key="global_show_stimulus").set_value(False).run()
    assert not at.exception, at.exception
    assert at.session_state["global_show_raw_gaze"] is True
    assert _lit_tiles(at) == []


@pytest.mark.parametrize(
    ("mode", "hidden"), [("simple", "adv_only_"), ("advanced", "simple_only_")]
)
def test_mode_css_drops_the_rail_wrapper_of_a_hidden_part(mode, hidden):
    """A hidden rail part leaves no gap: its wrapper block goes too, in a rule
    of its own so a browser without ``:has()`` still hides the part."""
    css = ui_mode.mode_css(mode)
    wrapper = (
        '.st-key-scanpath_rail [data-testid="stLayoutWrapper"]'
        f':has(> [class*="st-key-{hidden}"]) {{ display: none !important; }}'
    )
    assert wrapper in css
    assert f'<style>[class*="st-key-{hidden}"] {{ display: none !important; }}' in css


def test_rail_mode_wrappers_keep_the_rail_spacing():
    from scanpath_studio.styles import get_app_css

    css = " ".join(get_app_css().split())
    assert (
        '.st-key-scanpath_rail [class*="st-key-adv_only_"] > div:last-child, '
        '.st-key-scanpath_rail [class*="st-key-simple_only_"] > div:last-child '
        "{ margin-bottom: 0 !important; }"
    ) in css
    # The View tiles are drawn like the design presets they stand in for.
    assert '.st-key-scanpath_rail [class*="st-key-simple_view_"] button {' in css
    assert ".st-key-scanpath_rail .st-key-tour_grp_simple_views {" in css


HIGH_CONTRAST = "High contrast"


def _palette_colors(at: AppTest, name: str) -> dict:
    from scanpath_studio import controls

    return {key: at.session_state[key] for key in controls.palette_state(name)}


def test_simple_palette_pick_keeps_the_tile_lit():
    at = _boot()
    at.button(key="simple_view_scanpath").click().run()
    at.selectbox(key="global_palette").set_value(HIGH_CONTRAST).run()
    assert not at.exception
    assert at.session_state["global_palette"] == HIGH_CONTRAST
    assert _lit_tiles(at) == ["scanpath"]
    # Any other plot setting still reads as leaving the view.
    at.toggle(key="global_show_stimulus").set_value(False).run()
    assert _lit_tiles(at) == []


def test_simple_tile_keeps_the_palette():
    from scanpath_studio import controls

    at = _boot()
    at.button(key="simple_view_scanpath").click().run()
    at.selectbox(key="global_palette").set_value(HIGH_CONTRAST).run()
    at.button(key="simple_view_heatmap").click().run()
    assert not at.exception
    assert at.session_state["global_show_heatmap"] is True
    assert at.session_state["global_palette"] == HIGH_CONTRAST
    wanted = controls.palette_state(HIGH_CONTRAST)
    assert {
        k: controls._palette_match_key(v)
        for k, v in _palette_colors(at, HIGH_CONTRAST).items()
    } == {k: controls._palette_match_key(v) for k, v in wanted.items()}
    assert _lit_tiles(at) == ["heatmap"]
    # It holds on the next run too, and through the replay tile.
    at.run()
    assert at.session_state["global_palette"] == HIGH_CONTRAST
    at.button(key="simple_view_animation").click().run()
    assert at.session_state["global_palette"] == HIGH_CONTRAST
    assert _lit_tiles(at) == ["animation"]


def test_simple_hand_edited_colour_lights_no_tile():
    """A colour past every palette is shaped in Advanced, and counts."""
    at = _boot()
    at.button(key="simple_view_scanpath").click().run()
    # One run for the preset's held writes to settle (`write_through`).
    at.run()
    at.color_picker(key="global_fixation_color").pick("#123456").run()
    assert not at.exception
    assert at.session_state["global_palette"] == "Custom"
    assert _lit_tiles(at) == []


def test_advanced_palette_pick_still_drops_the_preset_to_custom():
    at = _boot(mode="advanced")
    at.button(key="viz_view_scanpath").click().run()
    at.selectbox(key="global_palette").set_value(HIGH_CONTRAST).run()
    assert at.button(key="viz_view_custom").proto.type == "primary"
    assert at.button(key="viz_view_scanpath").proto.type == "secondary"
    # An Advanced preset starts from the default colours, as before.
    at.button(key="viz_view_heatmap").click().run()
    assert at.session_state["global_palette"] != HIGH_CONTRAST
    assert at.button(key="viz_view_heatmap").proto.type == "primary"


def _subtab_labels(at: AppTest) -> list[str]:
    """The labels of the per-trial subtab bar (the one holding ``Share``)."""
    labels = [t.label for t in at.tabs]
    assert tabs.SUBTAB_SHARE in labels
    return labels


def test_subtab_labels_for_simple():
    assert tabs.subtab_labels_for(True, line_assignment=False) == [
        tabs.SUBTAB_EXPORT,
        tabs.SUBTAB_SHARE,
        tabs.SUBTAB_MORE,
    ]
    # Line assignment is Advanced-only, so the gate changes nothing here.
    assert tabs.subtab_labels_for(True, line_assignment=True) == [
        tabs.SUBTAB_EXPORT,
        tabs.SUBTAB_SHARE,
        tabs.SUBTAB_MORE,
    ]


def test_subtab_labels_for_advanced():
    base = [tabs.SUBTAB_ANNOTATIONS, tabs.SUBTAB_STIMULUS, tabs.SUBTAB_COMPARISONS]
    ends = [tabs.SUBTAB_EXPORT, tabs.SUBTAB_SHARE]
    assert tabs.subtab_labels_for(False, line_assignment=False) == base + ends
    assert tabs.subtab_labels_for(False, line_assignment=True) == (
        base + [tabs.SUBTAB_LINE_ASSIGNMENT] + ends
    )


def test_simple_subtabs_render():
    at = _boot()
    assert _subtab_labels(at) == [
        tabs.SUBTAB_EXPORT,
        tabs.SUBTAB_SHARE,
        tabs.SUBTAB_MORE,
    ]
    assert at.session_state["single_subtab"] == tabs.SUBTAB_EXPORT


def test_switching_to_simple_from_a_hidden_subtab_falls_back():
    at = _boot(mode="advanced")
    at.session_state["single_subtab"] = tabs.SUBTAB_COMPARISONS
    at.run()
    assert not at.exception
    at.segmented_control(key=SWITCH).set_value("simple").run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "simple"
    assert at.session_state["single_subtab"] == tabs.SUBTAB_EXPORT


def test_simple_export_has_no_bundle():
    at = _boot()
    at.run()
    assert not at.exception
    headings = [str(m.value) for m in at.markdown]
    assert any("Current figure" in h for h in headings)
    assert not any("Export bundle" in h for h in headings)
    assert not [r for r in at.radio if r.key == "bulk_export_scope"]


def test_advanced_export_keeps_the_bundle():
    at = _boot(mode="advanced")
    at.session_state["single_subtab"] = tabs.SUBTAB_EXPORT
    at.run()
    assert not at.exception
    assert any("Export bundle" in str(m.value) for m in at.markdown)


def test_simple_more_subtab_lists_advanced_and_switches():
    at = _boot()
    at.session_state["single_subtab"] = tabs.SUBTAB_MORE
    at.run()
    assert not at.exception
    assert any("Annotations" in str(m.value) for m in at.markdown)
    at.button(key="more_to_advanced_subtabs").click().run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"


def test_select_share_in_advanced_stays_on_share_in_simple():
    at = _boot(mode="advanced")
    at.session_state["single_subtab"] = tabs.SUBTAB_SHARE
    at.run()
    assert not at.exception
    at.segmented_control(key=SWITCH).set_value("simple").run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "simple"
    assert at.session_state["single_subtab"] == tabs.SUBTAB_SHARE


def test_more_in_simple_falls_back_to_advanceds_first_subtab():
    at = _boot()
    at.session_state["single_subtab"] = tabs.SUBTAB_MORE
    at.run()
    assert not at.exception
    at.button(key="more_to_advanced_subtabs").click().run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["single_subtab"] == tabs.SUBTAB_ANNOTATIONS


# --- Opening on the replay, and the hidden-settings note ----------------------


def test_fresh_simple_session_opens_on_the_replay():
    at = _boot()
    assert at.session_state["single_animate"] is True
    assert _tile_type(at, "animation") == "primary"
    assert _tile_type(at, "scanpath") == "secondary"


def test_advanced_session_keeps_the_static_start():
    at = _boot(mode="advanced")
    assert at.session_state["single_animate"] is False


@pytest.mark.parametrize(
    ("query", "restored", "expected_set"),
    [
        ({}, False, True),
        ({"ui": "simple"}, False, True),
        ({"trial": "3"}, False, False),
        ({"ui": "simple", "trial": "3"}, False, False),
        ({}, True, False),
    ],
)
def test_simple_start_skips_links_and_restores(query, restored, expected_set):
    session = {sk.UI_MODE: "simple"}
    ui_mode.seed_simple_start(session, query, restored=restored)
    assert ("single_animate" in session) is expected_set
    if expected_set:
        assert session["single_animate"] is True


def test_simple_start_keeps_a_value_the_session_already_holds():
    session = {sk.UI_MODE: "simple", "single_animate": False}
    ui_mode.seed_simple_start(session, {}, restored=False)
    assert session["single_animate"] is False


def test_simple_start_runs_once_per_session():
    session = {sk.UI_MODE: "advanced"}
    ui_mode.seed_simple_start(session, {}, restored=False)
    assert "single_animate" not in session
    session[sk.UI_MODE] = "simple"
    ui_mode.seed_simple_start(session, {}, restored=False)
    assert "single_animate" not in session


def test_switch_to_simple_mid_session_does_not_start_animation():
    at = _boot(mode="advanced")
    assert at.session_state["single_animate"] is False
    at.segmented_control(key=SWITCH).set_value("simple").run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "simple"
    assert at.session_state["single_animate"] is False


@pytest.mark.parametrize(
    ("flags", "phrases"),
    [
        ({}, []),
        ({"narrowed": True}, ["a trial filter"]),
        ({"sorted_": True}, ["a sort order"]),
        ({"comparing": True}, ["Compare"]),
        ({"custom_view": True}, ["plot settings from Advanced"]),
        (
            {
                "custom_view": True,
                "comparing": True,
                "sorted_": True,
                "narrowed": True,
            },
            [
                "a trial filter",
                "a sort order",
                "Compare",
                "plot settings from Advanced",
            ],
        ),
    ],
)
def test_hidden_settings_reasons(flags, phrases):
    kwargs = {
        "narrowed": False,
        "sorted_": False,
        "comparing": False,
        "custom_view": False,
    }
    assert ui_mode.hidden_settings_reasons(**{**kwargs, **flags}) == phrases


def _notes(at: AppTest) -> list[str]:
    return [str(c.value) for c in at.caption if "from Advanced" in str(c.value)]


def test_a_plain_simple_session_shows_no_note():
    at = _boot()
    assert _notes(at) == []
    assert not [b for b in at.button if b.key == "hidden_note_to_advanced"]


def test_advanced_never_shows_the_note():
    at = _boot(mode="advanced")
    at.session_state["filter_participants"] = ["l7_1090"]
    at.run()
    at.run()
    assert not at.exception
    assert _notes(at) == []


def _viz_keys(at: AppTest) -> dict:
    return {
        k: at.session_state[k]
        for k in at.session_state
        if k.startswith(("global_", "filter_"))
    }


def test_shared_link_with_a_filter_shows_the_note():
    def boot(mode: str) -> AppTest:
        at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
        at.query_params["ui"] = mode
        at.query_params["show_raw_gaze"] = "1"
        pin_view(at, _VIEW_SCANPATH)
        at.run()
        at.session_state["filter_participants"] = ["l7_1090"]
        # The panel publishes the filter on one run, `app.main` applies it on
        # the next.
        at.run()
        at.run()
        assert not at.exception
        return at

    simple = boot("simple")
    notes = _notes(simple)
    assert len(notes) == 1
    assert "a trial filter" in notes[0]
    assert "plot settings from Advanced" in notes[0]
    # The note describes; it changes nothing the figure is built from.
    assert _viz_keys(simple) == _viz_keys(boot("advanced"))


def test_simple_sort_order_shows_the_note():
    at = _boot()
    at.selectbox(key="single_trial_sort").set_value("Trial ID").run()
    assert not at.exception
    assert any("a sort order" in n for n in _notes(at))
    at.selectbox(key="single_trial_sort").set_value("Data order").run()
    assert not any("a sort order" in n for n in _notes(at))


def test_simple_compare_from_link_keeps_b_picker():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.query_params["ui"] = "simple"
    at.query_params["compare"] = "l37_1129:l37_1129_2_2_1_Adv"
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    assert not at.exception
    assert at.session_state["single_compare_toggle"] is True
    assert "single_compare_trial" in at.session_state
    notes = _notes(at)
    assert len(notes) == 1 and "Compare" in notes[0]


def test_hidden_note_button_switches_to_advanced():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.query_params["ui"] = "simple"
    at.query_params["show_raw_gaze"] = "1"
    pin_view(at, _VIEW_SCANPATH)
    at.run()
    at.button(key="hidden_note_to_advanced").click().run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["_ui_mode_chosen"] is True


def test_simple_hides_the_trial_summary_table_by_css():
    simple = ui_mode.mode_css("simple")
    assert "st-key-adv_only_chips" in simple
    assert "st-key-adv_only_chips" not in ui_mode.mode_css("advanced")
    # The table is still built in Simple, so a mode switch changes no element.
    at = _boot()
    assert not at.exception


def test_more_picker_describes_the_summary_table():
    lines = dict(ui_mode.MORE_IN_ADVANCED["picker"])
    text = " ".join(lines).lower()
    assert "trial summary table" in text and "chips" not in text
    line = next(v for k, v in lines.items() if "summary" in k.lower())
    assert "condition" in line and "above the plot" in line


def test_simple_view_tiles_are_bigger_than_advanced_presets():
    from scanpath_studio.styles import get_app_css

    css = " ".join(get_app_css().split())
    sel = ".st-key-scanpath_rail .st-key-tour_grp_simple_views button {"
    assert sel in css
    assert "min-height: 4rem" in css.split(sel)[1].split("}")[0]
    assert "font-size: 1.05rem" in css
    # The narrow tiers keep the grid on one line per tile.
    assert "font-size: 0.95rem" in css
    assert ".st-key-quick_views_grid button" not in css.split(sel)[1].split("}")[0]


def test_simple_export_points_to_the_bundle_in_advanced():
    at = _boot()
    at.session_state["single_subtab"] = tabs.SUBTAB_EXPORT
    at.run()
    assert not at.exception
    assert any(b.key == "export_to_advanced" for b in at.button)
    at.button(key="export_to_advanced").click().run()
    assert not at.exception
    assert at.session_state["ui_mode"] == "advanced"
    assert at.session_state["_ui_mode_chosen"] is True
    assert any("Export bundle" in str(m.value) for m in at.markdown)


def test_advanced_export_has_no_pointer():
    at = _boot(mode="advanced")
    at.session_state["single_subtab"] = tabs.SUBTAB_EXPORT
    at.run()
    assert not at.exception
    assert not [b for b in at.button if b.key == "export_to_advanced"]


def test_cookie_follows_the_viewers_choice_not_the_session_mode():
    """A mode the app sets by itself (a tutorial needing Advanced) is not what
    the cookie remembers."""
    from unittest.mock import patch

    import streamlit as st

    state = {sk.UI_MODE: "advanced"}
    with patch.object(st, "session_state", state):
        assert ui_mode.cookie_mode() == "advanced"
        ui_mode._choose_mode("simple")
        state[sk.UI_MODE] = "advanced"
        assert ui_mode.cookie_mode() == "simple"
