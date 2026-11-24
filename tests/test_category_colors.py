"""A category wears one colour in every figure of a dataset, on every surface,
and the categories of one figure stay clearly apart.

The colours are assigned over every label the coloured column takes in the
dataset (`plots.category_vocabulary` → `FigureSettings.color_categories`), not
over the labels one figure happens to show.
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from itertools import combinations

import pandas as pd
import pytest

from scanpath_studio import api, export, plots, tabs
from scanpath_studio.export import ExportOptions, bulk_export
from tests.conftest import APP_SCRIPT

_KEYS = ["participant_id", "trial_id", "word_id"]
#: Every pair of palette colours is at least this far apart (ΔE*ab).
_PALETTE_GAP = 23


@pytest.fixture(scope="module")
def demo() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The demo's paragraph screens, each fixation carrying its word's
    part-of-speech tags so the figure can be coloured by them (31 Penn Treebank
    tags, more than the palette; 15 universal ones). One screen per reading, so
    every reading's figure draws all of its fixations and a word ID names one
    word."""
    words, fixations = api.load_sample_data(names="canonical")
    words, fixations = (f[f["screen_id"] == "Paragraph"] for f in (words, fixations))
    tags = words[[*_KEYS, "universal_pos", "ptb_pos"]].drop_duplicates(_KEYS)
    return words, fixations.merge(tags, on=_KEYS, how="left")


def _readings(fixations: pd.DataFrame) -> list[tuple[str, str]]:
    pairs = fixations[["participant_id", "trial_id"]].drop_duplicates()
    return list(pairs.itertuples(index=False, name=None))


def _closest(colors) -> float:
    labs = [plots._color_lab(color) for color in colors]
    return min(plots._delta_e(a, b) for a, b in combinations(labs, 2))


def _marker_colors(fig, trial: pd.DataFrame, column: str) -> dict[str, set[str]]:
    """Each label of ``column`` → the colours its fixations wear in ``fig``.

    The fixation trace draws the trial's fixations in time order."""
    trace = next(t for t in fig.data if t.name == "Fixations")
    labels = trial.sort_values("timestamp_ms", kind="stable")[column]
    assert len(labels) == len(trace.marker.color)
    seen: dict[str, set[str]] = {}
    for label, color in zip(labels, trace.marker.color):
        if pd.notna(label):
            seen.setdefault(str(label), set()).add(color)
    return seen


def _legend(fig) -> dict[str, str]:
    """The figure's category legend, label → colour (its first entries)."""
    return {
        t.name.split(": ", 1)[1]: t.marker.color
        for t in fig.data
        if t.showlegend and t.name and ": " in t.name
    }


@pytest.mark.parametrize("column", ["universal_pos", "ptb_pos"])
def test_plot_scanpath_gives_each_category_one_colour_in_every_reading(demo, column):
    words, fixations = demo
    across: dict[str, set[str]] = {}
    for pid, tid in _readings(fixations):
        fig = api.plot_scanpath(
            words,
            fixations,
            pid,
            tid,
            color_by=column,
            show_words=False,
            show_word_labels=False,
            show_saccades=False,
        )
        trial = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        own = _marker_colors(fig, trial, column)
        assert all(len(colors) == 1 for colors in own.values())
        colors = [next(iter(c)) for c in own.values()]
        # Distinct within the figure: palette-far apart while the dataset's
        # labels fit the palette, and past it no closer than the fallback gap.
        gap = (
            _PALETTE_GAP
            if fixations[column].nunique() <= len(plots._CATEGORY_PALETTE)
            else plots._CATEGORY_FALLBACK_DELTA_E
        )
        assert _closest(colors) >= gap
        for label, color in own.items():
            across.setdefault(label, set()).update(color)
    assert len(across) == fixations[column].nunique()
    assert {label: c for label, c in across.items() if len(c) > 1} == {}


def test_the_replay_colours_a_category_as_the_static_figure_does(demo):
    words, fixations = demo
    for pid, tid in _readings(fixations)[:3]:
        static = api.plot_scanpath(words, fixations, pid, tid, color_by="ptb_pos")
        replay = api.animate_scanpath(words, fixations, pid, tid, color_by="ptb_pos")
        assert _legend(replay) == _legend(static) != {}


def test_comparisons_share_one_map_and_keep_it_from_pair_to_pair(demo):
    words, fixations = demo
    readings = _readings(fixations)
    across: dict[str, set[str]] = {}
    for a, b in zip(readings[:4], readings[4:8]):
        fig = api.compare_scanpaths(words, fixations, a, b, color_by="universal_pos")
        for label, color in _legend(fig).items():
            across.setdefault(label, set()).add(color)
    assert across
    assert {label: c for label, c in across.items() if len(c) > 1} == {}


def test_a_cross_dataset_comparison_colours_over_both_datasets_labels(demo):
    words, fixations = demo
    # Scanpath B's corpus names one tag its own way.
    fixations_b = fixations.assign(
        universal_pos=fixations["universal_pos"].replace({"NOUN": "NOUN-B"})
    )
    readings = _readings(fixations)
    expected = plots.category_vocabulary("universal_pos", fixations, fixations_b)
    assert "NOUN" in expected and "NOUN-B" in expected
    seen = []
    real = plots._category_color_map

    def spy(labels, avoid=(), vocabulary=None):
        mapping = real(labels, avoid, vocabulary)
        seen.append((vocabulary, mapping))
        return mapping

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(plots, "_category_color_map", spy)
        api.compare_scanpaths(
            words,
            fixations,
            readings[0],
            readings[1],
            words_b=words,
            fixations_b=fixations_b,
            color_by="universal_pos",
        )
    assert len(seen) == 1
    vocabulary, mapping = seen[0]
    assert tuple(vocabulary) == expected
    # A on A's tag, B on its own: one map, two colours.
    assert mapping["NOUN"] != mapping["NOUN-B"]


def test_a_label_the_vocabulary_lacks_still_gets_its_own_colour():
    vocabulary = [f"tag {i}" for i in range(25)]
    whole = plots._category_color_map(vocabulary)
    shown = vocabulary[3:9]
    mapping = plots._category_color_map([*shown, "stranger", None], (), vocabulary)
    assert all(mapping[label] == whole[label] for label in shown)
    others = [whole[label] for label in vocabulary]
    stranger = plots._color_lab(mapping["stranger"])
    gap = min(plots._delta_e(stranger, plots._color_lab(c)) for c in others)
    assert gap >= plots._CATEGORY_FALLBACK_DELTA_E


def test_a_figure_built_with_the_vocabulary_matches_the_whole_datasets_map(demo):
    words, fixations = demo
    vocabulary = plots.category_vocabulary("ptb_pos", fixations)
    assert vocabulary == tuple(sorted(fixations["ptb_pos"].dropna().unique()))
    whole = plots._category_color_map(vocabulary)
    pid, tid = _readings(fixations)[5]
    trial = fixations[
        (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
    ]
    fig = plots.make_scanpath_figure(
        words[(words["participant_id"] == pid) & (words["trial_id"] == tid)],
        trial,
        canvas_width=1280,
        canvas_height=720,
        base_font_size=16,
        color_by="ptb_pos",
        color_categories=vocabulary,
    )
    own = _marker_colors(fig, trial, "ptb_pos")
    assert {label: next(iter(c)) for label, c in own.items()} == {
        label: whole[label] for label in own
    }


def test_the_vocabulary_is_none_when_nothing_is_coloured_by_categories(demo):
    _, fixations = demo
    for column in (None, "", "(uniform)", "line", "duration_ms", "no such column"):
        assert plots.category_vocabulary(column, fixations) is None
    assert plots.category_vocabulary("saccade_type", None, fixations) == tuple(
        sorted(fixations["saccade_type"].dropna().unique())
    )


def test_the_bulk_export_colours_over_the_whole_datasets_labels(demo, monkeypatch):
    words, fixations = demo
    vocabulary = plots.category_vocabulary("universal_pos", fixations)
    built = []
    real = export.make_scanpath_figure

    def spy(words, fixations, *, settings, raw_gaze=None):
        built.append(settings.color_categories)
        return real(words, fixations, settings=settings, raw_gaze=raw_gaze)

    monkeypatch.setattr(export, "make_scanpath_figure", spy)
    readings = _readings(fixations)[:2]
    scoped = fixations[
        fixations.set_index(["participant_id", "trial_id"]).index.isin(readings)
    ]
    combos = scoped[["participant_id", "trial_id", "text_id"]].drop_duplicates()
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_html=True,
        include_plot_config=True,
    )
    settings = {"color_by": "universal_pos", "show_words": True}
    common = dict(
        canvas_width=1280,
        canvas_height=720,
        base_font_size=16,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings=settings,
        options=options,
    )
    # Read off the frames it is given…
    bulk_export(combos, words, fixations, **common)
    assert built == [vocabulary] * 2
    # …or, as the app passes it, the whole dataset's for a narrowed pool.
    built.clear()
    zip_bytes, progress = bulk_export(
        combos, words, scoped, color_categories=vocabulary, **common
    )
    assert progress.errors == []
    assert built == [vocabulary] * 2
    # Derived data, never written into the settings file.
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        configs = [n for n in archive.namelist() if n.endswith("plot_config.json")]
        assert configs
        for name in configs:
            assert "color_categories" not in archive.read(name).decode()
            json.loads(archive.read(name))


def test_the_category_vocabulary_is_no_figure_option():
    for kind in ("static", "animation", "comparison"):
        assert "color_categories" not in api.figure_options(kind)


def test_assigning_a_thousand_labels_stays_fast():
    labels = [f"category {i}" for i in range(1000)]
    plots._assigned_category_colors.cache_clear()
    started = time.perf_counter()
    mapping = plots._category_color_map(labels)
    assert time.perf_counter() - started < 2.0
    assert len(mapping) == len(labels) + 1
    # The first labels past the palette are still kept apart.
    first = plots._category_color_map(labels[:40])
    assert _closest([first[label] for label in labels[:40]]) >= (
        plots._CATEGORY_FALLBACK_DELTA_E
    )


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def test_the_app_colours_a_category_over_the_whole_datasets_labels(monkeypatch):
    """The app's figure carries every label of the dataset, so stepping to
    another trial keeps each category's colour."""
    built = []
    real = tabs._cached_scanpath_figure

    def spy(words, fixations, settings, raw_gaze, fig_key):
        fig = real(words, fixations, settings, raw_gaze, fig_key)
        built.append((settings, fig))
        return fig

    monkeypatch.setattr(tabs, "_cached_scanpath_figure", spy)
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.session_state["global_color_by"] = "saccade_type"
    at.run(timeout=90)
    assert not at.exception, at.exception
    _, fixations = api.load_sample_data(names="canonical")
    expected = plots.category_vocabulary("saccade_type", fixations)
    settings, first = built[-1]
    assert settings.color_categories == expected
    at.button(key="single_next_trial").click().run(timeout=90)
    assert not at.exception, at.exception
    settings, second = built[-1]
    assert settings.color_categories == expected
    shared = _legend(first).keys() & _legend(second).keys()
    assert shared
    assert {k: _legend(first)[k] for k in shared} == {
        k: _legend(second)[k] for k in shared
    }
