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
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(words, fixations, pid, tid)
    return locals()


def _heatmap() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_heatmap=True,
        heatmap_style="Smoothed",
        show_fixations=False,
        show_saccades=False,
    )
    return locals()


def _text_lines() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(words, fixations, pid, tid, color_by_line=True)
    return locals()


def _saccade_types() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        saccade_color_mode="By type",
        saccade_type_legend=False,
    )
    return locals()


def _illustration() -> dict:
    from scanpath_studio.synthetic import make_synthetic_words

    words = make_synthetic_words()
    fixations = words[["participant_id", "trial_id", "text_id", "word_id"]].copy()
    fixations["x"] = words["x"] + words["width"] / 2
    fixations["y"] = words["y"] + words["height"] / 2
    fixations["duration_ms"] = [100, 150, 120, 200, 90, 110]
    fixations["timestamp_ms"] = (
        fixations["duration_ms"].cumsum() - fixations["duration_ms"]
    )
    fixations["order_in_trial"] = range(1, len(fixations) + 1)
    fixations["pass_index"] = 1
    pid, tid = "synthetic", "synthetic_2line_demo"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=(450, 340),
        fixation_snap_to_line=True,
        saccade_render_mode="Arc",
        illustration_text="Illustration · hand-drawn",
        show_order=True,
        duration_size_legend=False,
    )
    return locals()


def _hearts_arrows() -> dict:
    from scanpath_studio.synthetic import make_synthetic_words

    words = make_synthetic_words()
    fixations = words[["participant_id", "trial_id", "text_id", "word_id"]].copy()
    fixations["x"] = words["x"] + words["width"] / 2
    fixations["y"] = words["y"] + words["height"] / 2
    fixations["duration_ms"] = [100, 150, 120, 200, 90, 110]
    fixations["timestamp_ms"] = (
        fixations["duration_ms"].cumsum() - fixations["duration_ms"]
    )
    fixations["order_in_trial"] = range(1, len(fixations) + 1)
    fixations["pass_index"] = 1
    pid, tid = "synthetic", "synthetic_2line_demo"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=(450, 300),
        fixation_symbol="heart",
        fixation_color="#d12d72",
        marker_size_range=(18, 30),
        fixation_opacity=0.85,
        fixation_snap_to_line=True,
        saccade_render_mode="Arc",
        show_saccade_arrows=True,
        saccade_color="#4f46a5",
        saccade_width=2.5,
        saccade_arrow_size=12,
        show_order=False,
        duration_size_legend=False,
        illustration_text="Illustration · hand-drawn",
    )
    return locals()


def _comparison() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_2_4_Ele"
    fig = sps.compare_scanpaths(
        words,
        fixations,
        (pid, tid),
        ("l7_1090", "l7_1090_2_2_4_Ele"),
        labels=("Participant A", "Participant B"),
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
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    raw_gaze = sps.load_sample_raw_gaze()
    fig = sps.plot_scanpath(
        words,
        fixations,
        "l37_1129",
        "l37_1129_2_2_2_Adv",
        raw_gaze=raw_gaze,
        fixation_opacity=0.35,
        show_saccades=False,
    )
    return locals()


def _replay() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.animate_scanpath(
        words,
        fixations,
        pid,
        tid,
        fix_index_range=(1, 40),
        playback_speed=2.0,
    )
    return locals()


def _word_boxes() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_heatmap=True,
        heatmap_style="Word boxes",
        show_fixations=False,
        show_saccades=False,
    )
    return locals()


def _highlighted_text() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
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


def _redacted_text() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(words, fixations, pid, tid, redact_text=True)
    return locals()


def _title_caption_legend() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        saccade_color_mode="By type",
        title="One participant, one article",
        title_font_size=34,
        caption="Marker size: fixation duration. Line color: saccade type.",
        caption_font_size=20,
        legend_layout={
            "saccades": {"position": "right-outside", "size": 18},
            "size_key": {"position": "bottom-right-outside", "size": 18},
        },
        fit_to_monitor=False,
        crop_margin=60,
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
        title="Across the experiment · Participant A",
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
        "Fixation time within each word box.",
        _word_boxes,
    ),
    Example(
        "text-lines",
        "Fixations by line",
        "Fixations colored by their nearest text line.",
        _text_lines,
    ),
    Example(
        "saccade-types",
        "Saccade types",
        "Forward movements, skips, refixations, return sweeps and regressions.",
        _saccade_types,
    ),
    Example(
        "comparison",
        "Two participants",
        "Two complete readings of a shorter text, labeled Participant A and Participant B.",
        _comparison,
    ),
    Example(
        "raw-gaze",
        "Raw gaze",
        "Gaze samples under translucent fixations. The bundled demo's gaze samples are synthetic.",
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
        "redacted-text",
        "Redacted text",
        "A block over each word’s letters keeps the layout and hides the words.",
        _redacted_text,
    ),
    Example(
        "title-caption-legend",
        "Title, caption & legend",
        "A titled, captioned figure with its legends placed around the plot.",
        _title_caption_legend,
    ),
    Example(
        "across-experiment",
        "Across the experiment",
        "Mean reading time per word across one participant’s recorded trials.",
        _across_experiment,
    ),
    Example(
        "illustration",
        "Reading schematic",
        "A hand-drawn, two-line reading with snapped fixations and arced saccades.",
        _illustration,
    ),
    Example(
        "hearts-arrows",
        "Fully customizable",
        "Heart-shaped fixations and curved arrows, in a design of your own.",
        _hearts_arrows,
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
    for slug in ("illustration", "hearts-arrows"):
        target = site / "gallery" / slug
        target.mkdir(parents=True, exist_ok=True)
        example = _build(slug)
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
