"""Executable gallery examples shared by the visual index and detail pages."""

from __future__ import annotations

import html
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from textwrap import dedent

from docs_support import embed, saccade_class_legend

import scanpath_studio as sps


@dataclass(frozen=True)
class Example:
    slug: str
    title: str
    caption: str
    build: Callable[[], dict]


def _scanpath() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(words, fixations, pid, tid, highlight_column=None)
    return locals()


def _heatmap() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_heatmap=True,
        heatmap_style="Interpolated",
        highlight_column=None,
        show_fixations=False,
        show_saccades=False,
    )
    return locals()


def _text_lines() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, color_by_line=True, highlight_column=None
    )
    return locals()


def _saccade_types() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        highlight_column=None,
        saccade_color_mode="By type",
        saccade_type_legend=False,
    )
    return locals()


def _illustration() -> dict:
    from scanpath_studio.measures import fixation_in_text_mask
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = load_synthetic_data()
    fixations = fixations[fixation_in_text_mask(fixations, words)].copy()
    pid, tid = "synthetic", "synthetic_2line_demo"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        highlight_column=None,
        canvas_size=(450, 340),
        fixation_snap_to_line=True,
        saccade_render_mode="Arc",
        illustration_text="Illustration · hand-drawn",
        show_order=True,
        duration_size_legend=False,
    )
    return locals()


def _comparison() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_2_4_Ele_r0"
    fig = sps.compare_scanpaths(
        words,
        fixations,
        (pid, tid),
        ("l7_1090", "l7_1090_2_2_4_Ele_r0"),
        highlight_column=None,
        labels=("Reader A", "Reader B"),
        fit_to_monitor=False,
        crop_margin=50,
        show_legend=True,
        duration_size_legend=False,
        legend_layout={
            "compare": {
                "position": "top-center-outside",
                "arrangement": "side-by-side",
                "size": 24,
            }
        },
    )
    return locals()


def _raw_gaze() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    raw_gaze = sps.load_sample_raw_gaze()
    fig = sps.plot_scanpath(
        words,
        fixations,
        "l37_1129",
        "l37_1129_2_2_2_Adv_r0",
        raw_gaze=raw_gaze,
        highlight_column=None,
        fixation_opacity=0.35,
        show_saccades=False,
    )
    return locals()


def _replay() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.animate_scanpath(
        words,
        fixations,
        pid,
        tid,
        fix_index_range=(1, 40),
        highlight_column=None,
        playback_speed=2.0,
    )
    return locals()


def _word_boxes() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        highlight_column=None,
        show_heatmap=True,
        heatmap_style="Word boxes",
        show_fixations=False,
        show_saccades=False,
    )
    return locals()


def _highlighted_text() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        highlight_column="is_in_aspan",
        critical_span_style="Mark text",
        show_saccades=False,
    )
    return locals()


def _across_experiment() -> dict:
    from scanpath_studio.aggregation import metric_by_trial_index
    from scanpath_studio.data import derive_trial_index
    from scanpath_studio.plots import make_trend_figure

    words, fixations = sps.load_sample_data(names="canonical")
    reader = words[words["participant_id"] == "l37_1129"].copy()
    reader["trial_index"] = derive_trial_index(reader)
    trend = metric_by_trial_index(reader, "total_fixation_duration_ms")
    fig = make_trend_figure(
        trend,
        x_col="trial_index",
        x_label="Recorded trial order",
        y_label="Mean total fixation duration per word (ms)",
        title="Across the experiment · Reader A",
        canvas_width=1000,
        base_font_size=18,
        font_family="Arial",
        height=450,
        break_gaps=True,
    )
    return locals()


EXAMPLES = (
    Example("scanpath", "Scanpath", "Fixations and saccades over the text.", _scanpath),
    Example("heatmap", "Gaze heatmap", "Where fixation time concentrates.", _heatmap),
    Example(
        "word-boxes",
        "Word-box heatmap",
        "Fixation time within each word’s bounding box.",
        _word_boxes,
    ),
    Example(
        "text-lines",
        "Fixations by line",
        "Color each fixation by its text line.",
        _text_lines,
    ),
    Example(
        "saccade-types",
        "Saccade types",
        "Forward movements, skips, refixations, return sweeps and regressions.",
        _saccade_types,
    ),
    Example(
        "illustration",
        "Reading schematic",
        "A hand-drawn, two-line reading with snapped fixations and arced saccades.",
        _illustration,
    ),
    Example(
        "comparison",
        "Two readers",
        "Two complete readings of a shorter text, labeled Reader A and Reader B.",
        _comparison,
    ),
    Example(
        "raw-gaze",
        "Raw gaze",
        "Samples under translucent fixations. The demo samples are synthetic.",
        _raw_gaze,
    ),
    Example(
        "replay",
        "Replay",
        "The first forty fixations, played in reading order.",
        _replay,
    ),
    Example(
        "highlighted-text",
        "Highlighted text",
        "Mark a selected text span alongside its fixations.",
        _highlighted_text,
    ),
    Example(
        "across-experiment",
        "Across the experiment",
        "Mean reading time per word across one reader’s recorded trials.",
        _across_experiment,
    ),
)
BY_SLUG = {example.slug: example for example in EXAMPLES}


@cache
def _build(slug: str, preview: bool = False) -> dict:
    return BY_SLUG[slug].build()


def gallery_cards() -> str:
    """Compact links with previews of the same example figures, including replay."""
    cards = []
    for example in EXAMPLES:
        figure = embed(_build(example.slug, preview=True)["fig"], preview=True)
        cards.append(
            f'<a class="sps-gallery-card" href="{example.slug}/">'
            f'<div aria-hidden="true">{figure}</div>'
            f"<strong>{html.escape(example.title)}</strong>"
            f"<span>{html.escape(example.caption)}</span></a>"
        )
    return '<div class="sps-gallery-grid">' + "".join(cards) + "</div>"


def gallery_figure(slug: str) -> str:
    """The full interactive figure, including the replay player when needed."""
    legend = saccade_class_legend() if slug == "saccade-types" else None
    return embed(_build(slug)["fig"], legend=legend)


def gallery_python(slug: str) -> str:
    """A standalone script using exactly the recipe that draws the figure."""
    source = inspect.getsource(BY_SLUG[slug].build)
    body = dedent("\n".join(source.splitlines()[1:-1])).strip()
    code = "import scanpath_studio as sps\n\n" + body
    code += f'\n\nsps.save_figure(fig, "{slug}.html")'
    return "```python\n" + code + "\n```"


def write_gallery_assets(site: Path) -> None:
    """Downloadable data and scripts used by the gallery’s shell recipes."""
    target = site / "gallery" / "illustration"
    target.mkdir(parents=True, exist_ok=True)
    example = _build("illustration")
    example["words"].to_csv(target / "words.csv", index=False)
    example["fixations"].to_csv(target / "fixations.csv", index=False)
    target = site / "gallery" / "across-experiment"
    target.mkdir(parents=True, exist_ok=True)
    code = (
        gallery_python("across-experiment")
        .removeprefix("```python\n")
        .removesuffix("\n```")
    )
    (target / "across-experiment.py").write_text(code + "\n", encoding="utf-8")
