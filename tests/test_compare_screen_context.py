"""Each side of an app comparison is drawn on its own screen.

One dataset can hold screens of different sizes (a reader who changed display
resolution, a multipart import whose pages differ), so dataset identity never
makes B's screen A's. The app's overlay gate and B's panel canvas both read B's
own selected screen, through the same helpers the Scanpath view calls.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _comparison_app(width_a: int, width_b: int, layout: str) -> None:
    import pandas as pd
    import streamlit as st

    from scanpath_studio import api, tabs
    from scanpath_studio.plots import FigureSettings

    def reading(trial, text, screen, width):
        words, fixations = api.build_authored_scanpath("First page")
        common = dict(
            participant_id="p",
            trial_id=trial,
            screen_id=screen,
            screen_index=1,
            canvas_width=width,
            canvas_height=900,
        )
        return words.assign(**common, text_id=text), fixations.assign(**common)

    wa, fa = reading("t1", "text1", "page1", width_a)
    wb, fb = reading("t2", "text2", "page2", width_b)
    words, fixes = pd.concat([wa, wb]), pd.concat([fa, fb])
    combos = words[["participant_id", "trial_id", "text_id"]].drop_duplicates()
    meta = tabs._build_compare_meta(
        words,
        fixes,
        "p",
        "t1",
        "p",
        "t2",
        compare_screen="page2",
        dataset_canvas=(1920, 1080),
    )
    st.session_state["gate"] = tabs._compare_setups(meta, wa, fa, width_a, 900)

    def capture(fig, **kwargs):
        st.session_state["ranges"] = [
            list(fig.layout.xaxis.range),
            list(fig.layout["xaxis2"].range) if "xaxis2" in fig.layout else None,
        ]

    original = tabs._render_true_scale_chart
    tabs._render_true_scale_chart = capture
    try:
        tabs._render_comparison_figure(
            combos,
            words,
            fixes,
            "p",
            "t1",
            "text1",
            "p",
            "t2",
            FigureSettings(
                canvas_width=width_a,
                canvas_height=900,
                base_font_size=16,
                fit_to_monitor=True,
            ),
            {},
            layout=layout,
            compare_meta=meta,
        )
    finally:
        tabs._render_true_scale_chart = original


def _run(width_a: int, width_b: int, layout: str = "side_by_side") -> AppTest:
    at = AppTest.from_function(
        _comparison_app, args=(width_a, width_b, layout), default_timeout=30
    ).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def test_two_screen_sizes_in_one_dataset_refuse_the_overlay():
    for width_a, width_b in ((800, 1600), (1600, 800)):
        allowed, reason = _run(width_a, width_b).session_state["gate"]
        assert not allowed
        assert f"{width_a}x900" in reason and f"{width_b}x900" in reason


def test_each_split_panel_is_drawn_to_its_own_screen():
    for width_a, width_b in ((800, 1600), (1600, 800)):
        at = _run(width_a, width_b)
        assert at.session_state["ranges"] == [[0, width_a], [0, width_b]]
        assert any(
            f"A {width_a}×900, B {width_b}×900" in caption.value
            for caption in at.caption
        )


def test_one_screen_size_overlays_as_before():
    at = _run(800, 800, layout="overlay")
    assert at.session_state["gate"] == (True, "")
    assert at.session_state["ranges"][0] == [0, 800]
    at = _run(800, 800)
    assert at.session_state["ranges"] == [[0, 800], [0, 800]]


def test_b_on_a_screen_without_its_own_canvas_takes_its_datasets():
    from scanpath_studio import api, tabs

    words, fixations = api.build_authored_scanpath("First page")
    words = words.assign(participant_id="p", trial_id="t2")
    fixations = fixations.assign(participant_id="p", trial_id="t2")
    meta = tabs._build_compare_meta(
        words, fixations, "p", "t1", "p", "t2", dataset_canvas=(1280, 1024)
    )
    assert meta["canvas"] == (1280, 1024)
    with_screen = words.assign(canvas_width=640, canvas_height=480)
    meta = tabs._build_compare_meta(
        with_screen, fixations, "p", "t1", "p", "t2", dataset_canvas=(1280, 1024)
    )
    assert meta["canvas"] == (640, 480)
