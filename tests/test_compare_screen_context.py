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
        assert f"{width_a}×900" in reason and f"{width_b}×900" in reason


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


def _image_app(folder: str, scenario: str) -> None:
    import io
    import zipfile

    import pandas as pd
    import streamlit as st
    from PIL import Image

    from scanpath_studio import api, tabs
    from scanpath_studio.export import ComparisonSide, ExportOptions, pair_export
    from scanpath_studio.plots import FigureSettings, _background_image_spec
    from scanpath_studio.utils import separate_self_compare

    def png(name, color):
        path = f"{folder}/{name}.png"
        Image.new("RGB", (800, 900), color).save(path)
        return path

    def source(path):
        return _background_image_spec(path, (800, 900), (0, 0))["source"]

    red, blue = png("red", "red"), png("blue", "blue")

    def reading(participant, trial, text, screen, index, image):
        words, fixations = api.build_authored_scanpath("First page")
        common = dict(
            participant_id=participant,
            trial_id=trial,
            screen_id=screen,
            screen_index=index,
        )
        words = words.assign(**common, text_id=text)
        if image is not None:
            words = words.assign(image_path=image)
        return words, fixations.assign(**common)

    upload = None
    if scenario == "different_text":
        b = ("p", "t2", "text2", "page1", 1, blue)
    elif scenario == "later_page":
        b = ("p", "t1", "text1", "page2", 2, blue)
    elif scenario == "b_without_image":
        b = ("p", "t2", "text2", "page1", 1, None)
    elif scenario == "upload_same_page":
        b = ("q", "t1", "text1", "page1", 1, blue)
        upload = source(blue)
    else:  # upload_other_text
        b = ("p", "t2", "text2", "page1", 1, blue)
        upload = source(red)
    wa, fa = reading("p", "t1", "text1", "page1", 1, red)
    wb, fb = reading(*b)
    combos = pd.concat([wa, wb])[
        ["participant_id", "trial_id", "text_id"]
    ].drop_duplicates()
    meta = tabs._build_compare_meta(
        pd.concat([wa, wb]),
        pd.concat([fa, fb]),
        "p",
        "t1",
        b[0],
        b[1],
        compare_screen=b[3],
    )
    figure_b = None
    fig_wb, fig_fb = meta["words"], meta["fixations"]
    if b[:2] == ("p", "t1"):  # A's own trial, renamed apart as the app does
        fig_wb = separate_self_compare(fig_wb, "p")
        fig_fb = separate_self_compare(fig_fb, "p")
        figure_b = str(fig_fb["participant_id"].iloc[0])
    viz = {"show_stimulus_image": True}
    a_image = red
    if upload is not None:
        viz["stimulus_image_upload_uri"] = upload
        a_image = upload

    def capture(fig, **kwargs):
        st.session_state["drawn"] = fig

    original = tabs._render_true_scale_chart
    tabs._render_true_scale_chart = capture
    try:
        fig = tabs._render_comparison_figure(
            combos,
            pd.concat([wa, fig_wb]),
            pd.concat([fa, fig_fb]),
            "p",
            "t1",
            "text1",
            b[0],
            b[1],
            FigureSettings(
                canvas_width=800,
                canvas_height=900,
                base_font_size=16,
                background_image=a_image,
                background_image_size=(800.0, 900.0),
                background_image_origin=(0.0, 0.0),
            ),
            viz,
            layout="side_by_side",
            compare_meta=meta,
            figure_participant_b=figure_b,
        )
    finally:
        tabs._render_true_scale_chart = original
    sources = {"red": source(red), "blue": source(blue)}
    st.session_state["same_figure"] = fig is st.session_state["drawn"]
    st.session_state["panels"] = {
        image.xref: next((n for n, s in sources.items() if s == image.source), "?")
        for image in fig.layout.images
    }
    bundle = pair_export(
        fig,
        ComparisonSide("p", "t1", wa, fa),
        ComparisonSide(b[0], b[1], wb, fb),
        canvas_width=800,
        canvas_height=900,
        x_field="x",
        y_field="y",
        settings={},
        options=ExportOptions(include_png=False, include_svg=False, include_html=True),
    )
    with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
        # The page's JSON escapes "/" — undone so a data URI reads as itself.
        html = next(
            zf.read(name).decode() for name in zf.namelist() if name.endswith(".html")
        ).replace("\\u002f", "/")
    st.session_state["exported"] = {
        name: value in html for name, value in sources.items()
    }


def _images(tmp_path, scenario: str):
    at = AppTest.from_function(
        _image_app, args=(str(tmp_path), scenario), default_timeout=60
    ).run()
    assert not at.exception, [e.message for e in at.exception]
    return at.session_state


def test_each_split_panel_shows_its_own_texts_image(tmp_path):
    state = _images(tmp_path, "different_text")
    assert state["panels"] == {"x": "red", "x2": "blue"}
    # The bundle's figure is the one drawn, B's page included.
    assert state["same_figure"]
    assert state["exported"] == {"red": True, "blue": True}


def test_a_later_page_of_the_same_trial_shows_that_pages_image(tmp_path):
    state = _images(tmp_path, "later_page")
    assert state["panels"] == {"x": "red", "x2": "blue"}


def test_a_b_without_an_image_is_left_blank(tmp_path):
    state = _images(tmp_path, "b_without_image")
    assert state["panels"] == {"x": "red"}
    assert state["exported"] == {"red": True, "blue": False}


def test_an_uploaded_image_is_shared_only_with_the_same_page(tmp_path):
    state = _images(tmp_path, "upload_same_page")
    assert state["panels"] == {"x": "blue", "x2": "blue"}
    # Another text: the upload is A's page alone, and B shows its own.
    state = _images(tmp_path, "upload_other_text")
    assert state["panels"] == {"x": "red", "x2": "blue"}
