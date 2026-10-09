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
from scanpath_studio.plots import _image_to_data_uri, _png_pixel_size

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
