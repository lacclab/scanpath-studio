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
    fig = sps.plot_scanpath(words, fixations, pid, tid)
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
        show_fixations=False,
        show_saccades=False,
    )
    return locals()


def _text_lines() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(words, fixations, pid, tid, color_by_line=True)
    return locals()


def _saccade_types() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
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
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        fixation_snap_to_line=True,
        saccade_render_mode="Arc",
        fix_index_range=(124, 139),
    )
    return locals()


def _comparison() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.compare_scanpaths(
        words,
        fixations,
        (pid, tid),
        ("l7_1090", "l7_1090_2_1_1_Ele_r0"),
        fix_index_range=(1, 50),
        show_legend=True,
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
        fixation_opacity=0.35,
        show_saccades=False,
    )
    return locals()


def _replay() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.animate_scanpath(words, fixations, pid, tid, fix_index_range=(1, 40))
    return locals()


def _word_profile() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    # The demo's word table carries EyeLink's own measures (IA_DWELL_TIME, …).
    one_text = words[words["unique_paragraph_id"] == "2_1_1_Ele"]
    profile = (
        one_text.groupby("IA_ID")
        .agg(
            value=("IA_DWELL_TIME", "mean"),
            sd=("IA_DWELL_TIME", "std"),
            word_text=("IA_LABEL", "first"),
        )
        .rename_axis("word_id")  # the column plot_corpus_figure reads
        .reset_index()
        .assign(lo=lambda d: d.value - d.sd, hi=lambda d: d.value + d.sd)
    )
    fig = sps.plot_corpus_figure(
        profile, kind="profile", measure_label="Total fixation duration (ms)"
    )
    return locals()


def _time_course() -> dict:
    words, fixations = sps.load_sample_data()
    pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, x_field="timestamp_ms", y_field="x"
    )
    return locals()


EXAMPLES = (
    Example("scanpath", "Scanpath", "Fixations and saccades over the text.", _scanpath),
    Example("heatmap", "Heatmap", "Where fixation time concentrates.", _heatmap),
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
        "Snapped fixations and arced saccades; an illustration of the reading.",
        _illustration,
    ),
    Example(
        "comparison",
        "Two readers",
        "Two readings of one text on the same canvas.",
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
        "word-profile",
        "Word profile",
        "Mean total fixation duration across readers, with a standard-deviation band.",
        _word_profile,
    ),
    Example(
        "time-course",
        "Time course",
        "Horizontal gaze position against fixation onset time.",
        _time_course,
    ),
)
BY_SLUG = {example.slug: example for example in EXAMPLES}


@cache
def _build(slug: str, preview: bool = False) -> dict:
    if preview and slug == "replay":
        words, fixations = sps.load_sample_data()
        fig = sps.plot_scanpath(
            words,
            fixations,
            "l37_1129",
            "l37_1129_2_1_1_Ele_r0",
            fix_index_range=(1, 40),
        )
        return {"fig": fig}
    return BY_SLUG[slug].build()


def gallery_cards() -> str:
    """Compact links with static previews of the same example figures."""
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
    """The CLI's ready-to-render example table, downloadable beside its page."""
    target = site / "gallery" / "word-profile" / "word-profile.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    _build("word-profile")["profile"].to_csv(target, index=False)
