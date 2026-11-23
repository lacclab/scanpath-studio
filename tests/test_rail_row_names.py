"""A layer's settings button and visibility switch are independent controls."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from tests.conftest import APP_SCRIPT


def test_layers_pair_named_menus_with_their_own_visibility_switches():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    assert not at.exception
    layers = next(tab for tab in at.tabs if tab.label == "Layers")
    menus = {menu.key: menu.proto.popover.label for menu in layers.get("popover")}
    for slug, key, label in (
        ("fix", "global_show_fix", "Fixations"),
        ("sac", "global_show_saccades", "Saccades"),
        ("stim", "global_show_stimulus", "Stimulus"),
        ("boxes", "global_show_words", "Word boxes"),
        ("heatmap", "global_show_heatmap", "Heatmap"),
        ("rawgaze", "global_show_raw_gaze", "Raw gaze"),
    ):
        switch = layers.toggle(key=key)
        assert menus[f"plot_menu_{slug}"] == label
        assert switch.label == label
    assert menus["plot_menu_filter"] == "Filters & highlights"


def test_filter_status_tracks_the_window_of_either_reading():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.toggle(key="single_compare_toggle").set_value(True).run()

    def active():
        row = next(
            block
            for block in at.get("flex_container")
            if block.key == "plot_filter_row"
        )
        return any(label.value == "Active" for label in row.caption)

    assert not active()
    for label in ("Fixation index range", "B fixation index range"):
        slider = next(widget for widget in at.slider if widget.label == label)
        lo, hi = slider.value
        slider.set_range(lo + 1, hi).run()
        assert active()
        next(widget for widget in at.slider if widget.label == label).set_range(
            lo, hi
        ).run()
        assert not active()
