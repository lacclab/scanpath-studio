"""#420: the headless stimulus-image folder draws.

`load_scanpath_data(image_root=…)` and `render --image-root` filled each row's
`image_path`, and no API or CLI figure drew it: only the app's 📄 Stimulus →
image did, through `tabs._reading_stimulus_image`. `show_stimulus_image` is
the figure option that draws it now, through the one resolver the app uses
too (`plots.reading_stimulus_image`), and `attach_stimulus_images` gives the
corpus loaders the folder `load_scanpath_data` takes.
"""

from __future__ import annotations

import collections
import io
import warnings
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd
import pytest

import scanpath_studio as sps
from scanpath_studio import api, cli, plots, tabs
from scanpath_studio import code_snippet as cs
from scanpath_studio.plots import _image_to_data_uri, _png_pixel_size
from tests.conftest import APP_SCRIPT

#: Two demo readings of different texts — so of different pages.
TRIAL = ("l37_1129", "l37_1129_2_2_1_Adv_r0")
OTHER = ("l37_1129", "l37_1129_2_2_2_Adv_r0")
#: Where the demo's pages sat on OneStop's screen (BUG-97).
DEMO_ORIGIN = (368.0, 186.0)


@pytest.fixture(scope="module")
def demo():
    return api.load_sample_data(names="canonical")


def _page(words: pd.DataFrame, reading: tuple[str, str]) -> str:
    rows = words[
        (words["participant_id"] == reading[0]) & (words["trial_id"] == reading[1])
    ]
    return str(rows["image_path"].dropna().iloc[0])


def _sources(fig) -> list[str]:
    return [image.source for image in fig.layout.images]


def _no_pages(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(columns=["image_path", "image_x", "image_y"], errors="ignore")


class TestTheOptionIsAFigureOption:
    @pytest.mark.parametrize("kind", ["static", "animation", "comparison"])
    def test_every_builder_lists_it_off(self, kind):
        assert api.figure_options(kind)["show_stimulus_image"] is False

    def test_the_canonical_default_is_off(self):
        assert api.CANONICAL_FIGURE_DEFAULTS["show_stimulus_image"] is False

    def test_the_app_never_asks_a_builder_for_it(self):
        """The app places the page itself, behind ENG-57's rule on what its
        server may read; a builder resolving `image_path` for it would read an
        uploaded dataset's path on a shared deployment."""
        viz = collections.defaultdict(lambda: None, show_stimulus_image=True)
        assert not tabs._build_figure_settings(viz, False).get("show_stimulus_image")


class TestPlotScanpath:
    def test_off_draws_no_page(self, demo):
        assert len(api.plot_scanpath(*demo, *TRIAL).layout.images) == 0

    def test_on_draws_the_trials_own_page_where_it_sat(self, demo):
        words, _ = demo
        fig = api.plot_scanpath(*demo, *TRIAL, show_stimulus_image=True)
        (image,) = fig.layout.images
        page = _page(words, TRIAL)
        assert image.source == _image_to_data_uri(page)
        assert (image.x, image.y) == DEMO_ORIGIN
        assert (image.sizex, image.sizey) == _png_pixel_size(page)

    def test_it_is_the_page_the_app_places(self, demo, monkeypatch):
        """One resolver: the app's `_reading_stimulus_image` and the builders'
        option agree on path, size and origin."""
        words, fixations = demo
        monkeypatch.setattr(tabs, "_servable_image_path", lambda p, source=None: p)
        rows = [
            frame[
                (frame["participant_id"] == TRIAL[0]) & (frame["trial_id"] == TRIAL[1])
            ]
            for frame in (words, fixations)
        ]
        path, size, origin = tabs._reading_stimulus_image(*rows)
        (image,) = api.plot_scanpath(
            *demo, *TRIAL, show_stimulus_image=True
        ).layout.images
        assert image.source == _image_to_data_uri(path)
        assert (image.sizex, image.sizey) == size
        assert (image.x, image.y) == origin

    def test_a_page_given_explicitly_wins(self, demo, tmp_path):
        other = _page(demo[0], OTHER)
        fig = api.plot_scanpath(
            *demo,
            *TRIAL,
            show_stimulus_image=True,
            background_image=other,
            background_image_size=(100, 50),
        )
        assert _sources(fig) == [_image_to_data_uri(other)]

    def test_frames_under_their_own_names_draw_it_too(self):
        words, fixations = api.load_sample_data()
        fig = api.plot_scanpath(words, fixations, *TRIAL, show_stimulus_image=True)
        assert len(fig.layout.images) == 1

    def test_a_trial_without_a_page_warns_and_draws_none(self, demo):
        words, fixations = (_no_pages(frame) for frame in demo)
        with pytest.warns(UserWarning, match=r"show_stimulus_image: .*l37_1129"):
            fig = api.plot_scanpath(words, fixations, *TRIAL, show_stimulus_image=True)
        assert len(fig.layout.images) == 0

    def test_a_missing_file_warns_too(self, demo):
        words, fixations = (frame.assign(image_path="gone.png") for frame in demo)
        with pytest.warns(UserWarning, match="missing or not a PNG"):
            api.plot_scanpath(words, fixations, *TRIAL, show_stimulus_image=True)

    def test_off_never_warns(self, demo):
        words, fixations = (_no_pages(frame) for frame in demo)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            api.plot_scanpath(words, fixations, *TRIAL)


class TestAnimateScanpath:
    def test_the_replay_draws_the_page(self, demo):
        fig = api.animate_scanpath(*demo, *TRIAL, show_stimulus_image=True)
        assert _sources(fig) == [_image_to_data_uri(_page(demo[0], TRIAL))]

    @pytest.mark.parametrize(("stimulus", "whose"), [("both", TRIAL), ("b", OTHER)])
    def test_a_co_animation_draws_the_page_of_the_text_it_draws(
        self, demo, stimulus, whose
    ):
        fig = api.animate_scanpath(
            *demo,
            *TRIAL,
            trial_b=OTHER,
            compare_stimulus=stimulus,
            show_stimulus_image=True,
        )
        assert _sources(fig) == [_image_to_data_uri(_page(demo[0], whose))]


class TestCompareScanpaths:
    @pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
    def test_each_split_panel_draws_its_own_page(self, demo, layout):
        fig = api.compare_scanpaths(
            *demo, TRIAL, OTHER, layout=layout, show_stimulus_image=True
        )
        assert _sources(fig) == [
            _image_to_data_uri(_page(demo[0], reading)) for reading in (TRIAL, OTHER)
        ]

    @pytest.mark.parametrize(("stimulus", "whose"), [("both", TRIAL), ("b", OTHER)])
    def test_an_overlay_draws_the_page_of_the_text_it_draws(
        self, demo, stimulus, whose
    ):
        fig = api.compare_scanpaths(
            *demo,
            TRIAL,
            OTHER,
            compare_stimulus=stimulus,
            show_stimulus_image=True,
        )
        assert _sources(fig) == [_image_to_data_uri(_page(demo[0], whose))]

    def test_a_b_without_a_page_draws_none_rather_than_as(self, demo):
        words, fixations = demo
        b_rows = (words["trial_id"] == OTHER[1]) & (words["participant_id"] == OTHER[0])
        words = words.assign(image_path=words["image_path"].where(~b_rows))
        fixations = fixations.assign(
            image_path=fixations["image_path"].where(fixations["trial_id"] != OTHER[1])
        )
        with pytest.warns(UserWarning, match="2_2_2_Adv"):
            fig = api.compare_scanpaths(
                words,
                fixations,
                TRIAL,
                OTHER,
                layout="side_by_side",
                show_stimulus_image=True,
            )
        assert _sources(fig) == [_image_to_data_uri(_page(demo[0], TRIAL))]


@pytest.fixture
def pages(tmp_path: Path, demo) -> Path:
    """A folder holding the demo's page for TRIAL's text under `<text_id>.png`."""
    words, _ = demo
    text = words.loc[words["trial_id"] == TRIAL[1], "text_id"].iloc[0]
    folder = tmp_path / "pages"
    folder.mkdir()
    (folder / f"{text}.png").write_bytes(Path(_page(words, TRIAL)).read_bytes())
    return folder


class TestAttachStimulusImages:
    def test_matched_rows_get_the_folders_page(self, demo, pages):
        text = demo[0].loc[demo[0]["trial_id"] == TRIAL[1], "text_id"].iloc[0]
        words, fixations = (_no_pages(frame) for frame in demo)
        words, fixations = api.attach_stimulus_images(words, fixations, pages)
        for frame in (words, fixations):
            # Every reading of that text, whoever read it.
            hit = frame["text_id"] == text
            assert frame.loc[hit, "image_path"].notna().all()
            assert frame.loc[~hit, "image_path"].isna().all()
        fig = api.plot_scanpath(words, fixations, *TRIAL, show_stimulus_image=True)
        assert len(fig.layout.images) == 1

    def test_the_frames_keep_their_own_names(self, pages):
        words, fixations = api.load_sample_data()
        attached = api.attach_stimulus_images(words, fixations, pages)
        assert list(attached.words.columns) == list(words.columns)
        assert set(attached.column_names) == {"words", "fixations"}

    def test_the_frames_passed_in_are_untouched(self, demo, pages):
        words = _no_pages(demo[0])
        api.attach_stimulus_images(words, None, pages)
        assert "image_path" not in words.columns

    def test_either_table_may_be_none(self, demo, pages):
        words, fixations = api.attach_stimulus_images(None, demo[1], pages)
        assert words.empty and not fixations.empty

    def test_is_exported_from_the_package(self):
        assert sps.attach_stimulus_images is api.attach_stimulus_images
        assert "attach_stimulus_images" in sps.__all__

    @pytest.mark.parametrize("make", ["missing", "file"])
    def test_a_folder_that_is_not_one_is_refused(self, demo, tmp_path, make):
        target = tmp_path / "pages"
        if make == "file":
            target.write_text("not a folder")
        with pytest.raises(ValueError, match="is not a folder"):
            api.attach_stimulus_images(*demo, target)

    def test_load_scanpath_data_refuses_it_too(self, sample_words_df, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            api.load_scanpath_data(
                sample_words_df, None, image_root=tmp_path / "nowhere"
            )


_BASE = ["render", "--sample", "-p", TRIAL[0], "-t", TRIAL[1]]


class TestRender:
    def _figure(self, monkeypatch, argv):
        figures = []
        monkeypatch.setattr(
            api, "save_figure", lambda fig, path, **_: figures.append(fig) or path
        )
        cli.main(argv)
        (fig,) = figures
        return fig

    def test_the_flag_draws_the_samples_own_page(self, monkeypatch):
        fig = self._figure(
            monkeypatch, [*_BASE, "--show-stimulus-image", "-o", "x.html"]
        )
        assert len(fig.layout.images) == 1

    def test_image_root_draws_the_folders_page(self, monkeypatch, pages, demo):
        fig = self._figure(
            monkeypatch,
            [
                *_BASE,
                "--image-root",
                str(pages),
                "--show-stimulus-image",
                "-o",
                "x.html",
            ],
        )
        (image,) = fig.layout.images
        text = demo[0].loc[demo[0]["trial_id"] == TRIAL[1], "text_id"].iloc[0]
        assert image.source == _image_to_data_uri(str(pages / f"{text}.png"))

    def test_image_root_alone_says_how_to_draw_it(self, monkeypatch, pages, capsys):
        fig = self._figure(
            monkeypatch, [*_BASE, "--image-root", str(pages), "-o", "x.html"]
        )
        assert len(fig.layout.images) == 0
        assert "--show-stimulus-image" in capsys.readouterr().err

    def test_a_missing_folder_is_a_message(self, tmp_path):
        with pytest.raises(SystemExit, match="is not a folder"):
            cli.main(
                [*_BASE, "--image-root", str(tmp_path / "nowhere"), "-o", "x.html"]
            )

    def _printed(self, monkeypatch, flavor, pages) -> str:
        monkeypatch.setattr(api, "save_figure", lambda fig, path, **_: path)
        out = io.StringIO()
        with redirect_stdout(out):
            cli.main(
                [
                    *_BASE,
                    "--image-root",
                    str(pages),
                    "--image-pattern",
                    "{text_id}.png",
                    "--show-stimulus-image",
                    "--print-code",
                    flavor,
                    "-o",
                    "x.html",
                ]
            )
        return out.getvalue()

    def test_the_printed_command_names_the_folder(self, monkeypatch, pages):
        command = self._printed(monkeypatch, "cli", pages)
        assert f"--image-root {pages}" in command
        assert "--show-stimulus-image" in command
        # The default pattern is left out.
        assert "--image-pattern" not in command

    def test_the_printed_python_draws_the_same_page(self, monkeypatch, pages):
        code = self._printed(monkeypatch, "python", pages)
        assert "sps.attach_stimulus_images(" in code
        figures = []
        monkeypatch.setattr(
            api, "save_figure", lambda fig, path, **_: figures.append(fig) or path
        )
        exec(compile(code, "<snippet>", "exec"), {})  # noqa: S102
        (fig,) = figures
        assert _sources(fig) == [_image_to_data_uri(str(next(pages.glob("*.png"))))]


def test_reading_stimulus_image_lets_the_caller_veto_the_path(demo):
    words, _ = demo
    rows = words[words["trial_id"] == TRIAL[1]]
    assert plots.reading_stimulus_image(rows, None) is not None
    assert plots.reading_stimulus_image(rows, None, allow=lambda path: None) is None


# ---------------------------------------------------------------------------
# The app's side: Share → Code names the page, and B's text gets B's page
# ---------------------------------------------------------------------------
_SLOT = ("background_image", "background_image_size", "background_image_origin")


def _drawn(page, suffix=""):
    path, size, origin = page
    return dict(zip((f"{key}{suffix}" for key in _SLOT), (path, size, origin)))


class TestNameOwnPages:
    PAGE = ("/data/pages/a.png", (1824, 1254), (368.0, 186.0))
    PAGE_B = ("/data/pages/b.png", (800, 600), (0.0, 0.0))

    def test_a_page_drawn_where_it_sat_is_named_by_the_option(self):
        settings = {"show_heatmap": True, **_drawn(self.PAGE)}
        named = cs.name_own_pages(settings, {"": self.PAGE})
        assert named == {"show_heatmap": True, "show_stimulus_image": True}

    @pytest.mark.parametrize(
        "moved",
        [
            {"background_image_origin": (378.0, 186.0)},  # the VIZ-4 offset
            {"background_image_size": (912.0, 627.0)},  # the VIZ-4 scale
            {"background_image": "data:image/png;base64,AAAA"},  # an upload
        ],
    )
    def test_anything_else_keeps_its_path(self, moved):
        settings = {**_drawn(self.PAGE), **moved}
        assert cs.name_own_pages(settings, {"": self.PAGE}) is settings

    def test_each_slot_is_decided_on_its_own(self):
        settings = {
            **_drawn(self.PAGE),
            **_drawn(("/data/pages/b.png", (800, 600), (5.0, 0.0)), "_b"),
        }
        named = cs.name_own_pages(settings, {"": self.PAGE, "_b": self.PAGE_B})
        # A is its own page, B was moved: B's path stays and wins over the option.
        assert named["show_stimulus_image"] is True
        assert "background_image" not in named
        assert named["background_image_b"] == "/data/pages/b.png"

    def test_no_page_of_its_own_names_nothing(self):
        settings = _drawn(self.PAGE)
        assert cs.name_own_pages(settings, {"": None}) is settings

    def test_nothing_is_named_while_a_slot_the_option_fills_draws_none(self):
        """The option fills every empty slot: a split whose B panel the app
        left blank (no page, or ENG-57's veto) must not get one headless."""
        settings = _drawn(self.PAGE)
        slots = ("", "_b")
        assert cs.name_own_pages(settings, {"": self.PAGE}, slots) is settings
        both = {**settings, **_drawn(self.PAGE_B, "_b")}
        named = cs.name_own_pages(both, {"": self.PAGE, "_b": self.PAGE_B}, slots)
        assert named == {"show_stimulus_image": True}

    def test_a_slot_outside_the_figures_is_ignored(self):
        """An overlay draws one page; B's slot does not count there."""
        settings = {**_drawn(self.PAGE), **_drawn(self.PAGE_B, "_b")}
        named = cs.name_own_pages(settings, {"_b": self.PAGE_B})
        assert named is settings


class TestTheImageFolderInTheSnippet:
    """The data half loads the folder only for a page it names from it."""

    def _python(self, folder, page):
        source = cs.SnippetSource(
            kind=cs.SOURCE_DEMO,
            options={"image_root": str(folder), "image_pattern": "{text_id}.png"},
        )
        state = cs.FigureState(
            kind="static",
            settings={**api.figure_options("static"), **_drawn(page)},
            participant=TRIAL[0],
            trial=TRIAL[1],
            own_pages={"": page},
        )
        return cs.python_snippet(source, state)

    def test_a_page_from_the_folder_brings_it(self, tmp_path):
        page = (str(tmp_path / "a.png"), (10, 10), (0.0, 0.0))
        code = self._python(tmp_path, page)
        assert "show_stimulus_image=True" in code
        assert "attach_stimulus_images(" in code

    def test_a_page_from_elsewhere_leaves_it_out(self, tmp_path):
        """A missing, empty or refused folder matched nothing, and the page came
        from the dataset itself: quoting the folder would make the snippet
        raise on a folder the app shrugged off."""
        page = ("/elsewhere/a.png", (10, 10), (0.0, 0.0))
        code = self._python(tmp_path / "missing", page)
        assert "show_stimulus_image=True" in code
        assert "attach_stimulus_images" not in code


def test_bs_page_from_a_second_dataset_keeps_its_path():
    """Its tables load from placeholders that hold no page to find again."""
    meta = {"dataset": "Other", "words": pd.DataFrame(), "fixations": pd.DataFrame()}
    assert tabs._own_page_b({"show_stimulus_image": True}, meta) is None


def _app(**state) -> object:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["global_show_stimulus_image"] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=120)
    assert not at.exception, at.exception
    return at


def _run_snippet(code: str):
    namespace: dict = {}
    exec(compile(code, "<snippet>", "exec"), namespace)  # noqa: S102
    return namespace["fig"]


@pytest.fixture
def every_page(tmp_path: Path) -> Path:
    """The demo's pages, copied into a folder under ``<text_id>.png``."""
    folder = tmp_path / "pages"
    folder.mkdir()
    images = Path(api.__file__).parent / "sample_data" / "images"
    for page in images.glob("*__paragraph.png"):
        text = page.name.removesuffix("__paragraph.png")
        (folder / f"{text}.png").write_bytes(page.read_bytes())
    return folder


def _share_code_panel():
    """The Share subtab's code block, for the bundled demo."""
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _render_code_snippet_body

    _render_code_snippet_body(DEMO_CHOICE)


@pytest.mark.timeout(240)
class TestShareCode:
    def test_the_demos_page_is_named_by_the_option_not_its_path(self):
        state = _app().session_state[cs.SNIPPET_STATE_KEY]
        code = cs.python_snippet(cs.SnippetSource(kind=cs.SOURCE_DEMO), state)
        assert "show_stimulus_image=True" in code
        # The installed package's path is no part of the recipe.
        assert "background_image" not in code
        assert _sources(_run_snippet(code)) == [
            _image_to_data_uri(state.own_pages[""][0])
        ]

    def test_a_moved_page_keeps_its_path(self):
        at = _app(global_stimulus_image_offset_x=10.0)
        state = at.session_state[cs.SNIPPET_STATE_KEY]
        code = cs.python_snippet(cs.SnippetSource(kind=cs.SOURCE_DEMO), state)
        assert "show_stimulus_image" not in code
        assert "background_image=" in code

    def test_a_folders_page_comes_with_the_folder(self, every_page):
        from scanpath_studio.constants import (
            DATASET_STIMULUS_IMAGES_KEY,
            DEFAULT_STIMULUS_IMAGE_PATTERN,
            DEMO_CHOICE,
        )

        # #417: the folder saved with the open dataset (the demo, here).
        saved = {
            DATASET_STIMULUS_IMAGES_KEY: {
                DEMO_CHOICE: {
                    "folder": str(every_page),
                    "pattern": DEFAULT_STIMULUS_IMAGE_PATTERN,
                }
            }
        }
        at = _app(**saved)
        state = at.session_state[cs.SNIPPET_STATE_KEY]
        # The app drew the folder's page…
        assert str(state.settings["background_image"]).startswith(str(every_page))
        # …and the Share panel, reading the same store, loads it with the folder.
        from streamlit.testing.v1 import AppTest

        panel = AppTest.from_function(_share_code_panel)
        panel.session_state[cs.SNIPPET_STATE_KEY] = state
        panel.session_state["data_source_choice"] = DEMO_CHOICE
        for key, value in saved.items():
            panel.session_state[key] = value
        panel.run(timeout=60)
        assert not panel.exception, panel.exception
        code = panel.session_state["_snippet_code_current"]
        assert "sps.attach_stimulus_images(" in code.python
        assert repr(str(every_page)) in code.python
        assert f"--image-root {every_page}" in code.cli
        assert "--show-stimulus-image" in code.cli
        fig = _run_snippet(code.python.split("\nsps.save_figure(")[0])
        assert _sources(fig) == [_image_to_data_uri(state.settings["background_image"])]


def _compare_on_another_text(**state):
    at = _app(
        single_compare_toggle=True,
        single_compare_layout="Overlay",
        single_compare_stimulus="B",
        **state,
    )
    picker = at.selectbox(key="single_compare_trial")
    other = next(option for option in picker.options if "2_2_2_Adv" in str(option))
    picker.set_value(other)
    at.run(timeout=120)
    assert not at.exception, at.exception
    return at.session_state[cs.SNIPPET_STATE_KEY]


@pytest.mark.timeout(240)
class TestBsTextGetsBsPage:
    """An overlay or co-animation that draws B's text draws B's page — as
    `api.compare_scanpaths` / `animate_scanpath` do — never A's."""

    def test_the_overlay(self, demo):
        state = _compare_on_another_text()
        assert (state.kind, state.compare.compare_stimulus) == ("comparison", "b")
        page_b = _page(demo[0], (state.compare.participant, state.compare.trial))
        assert page_b != _page(demo[0], (state.participant, state.trial))
        assert state.settings["background_image"] == page_b
        code = cs.python_snippet(cs.SnippetSource(kind=cs.SOURCE_DEMO), state)
        assert "show_stimulus_image=True" in code
        assert "background_image" not in code
        assert _sources(_run_snippet(code)) == [_image_to_data_uri(page_b)]

    def test_the_co_animation(self, demo):
        state = _compare_on_another_text(single_animate=True)
        assert state.kind == "animation"
        page_b = _page(demo[0], (state.compare.participant, state.compare.trial))
        assert state.settings["background_image"] == page_b

    def test_an_upload_stays_the_users_choice(self):
        settings = plots.FigureSettings(
            canvas_width=10, canvas_height=10, base_font_size=12
        )
        assert (
            tabs._page_under_text_b(
                settings,
                {"show_stimulus_image": True, "stimulus_image_upload_uri": "data:x"},
                {"words": pd.DataFrame(), "fixations": pd.DataFrame()},
            )
            == {}
        )
