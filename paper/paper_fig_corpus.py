"""Render the corpus-level analysis figure (fig_corpus) for the manuscript.

A three-panel montage from the *Per text* view of Corpus Analysis, run on the
full OneStop corpus (ordinary reading regime) rather than the 3-reader demo, so
the cohort views are populated:

  A  word x reader heatmap of total dwell time (AN-2)
  B  cohort word profile with a spread band (AN-3)
  C  per-word skipping and regression-in rates (AN-6)

Run from the app repo:  cd app && uv run python paper/paper_fig_corpus.py

Needs the full OneStop reports under ``ONESTOP_ROOT`` (see datasets.download_onestop).
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scanpath_studio import aggregation, constants, datasets, plots
from scanpath_studio.api import save_figure


def _figures_dir() -> Path:
    """Where rendered figures land.

    Defaults to ``paper/figures/`` inside the software repo so an archived
    release is self-contained; set ``PAPER_FIGURES_DIR`` to write straight into
    the manuscript tree (e.g. ``PAPER_FIGURES_DIR=../../overleaf/figures``).
    """
    env = os.environ.get("PAPER_FIGURES_DIR")
    out = Path(env) if env else Path(__file__).resolve().parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    return out


FIGS = _figures_dir()
ONESTOP_ROOT = "data/OneStop"

WIDTH = 1180  # panel canvas width, px
FONT = constants.FONT_FAMILY
BASE_FONT = 15
# A paragraph with many readers; picked as the most-read text in the loaded slice.
MEASURE = aggregation.MEASURES["tfd"]
# Short, so the y-axis title fits the panel's left margin.
MEASURE_LABEL = "Total dwell time (ms)"
MAX_READERS = 24  # keep the heatmap rows legible in print


PASSAGE = "passage_id"
# OneStop's `text_id` is the paragraph NUMBER within an article, so on the full
# corpus it pools different passages (and both difficulty versions) under one
# label. A passage is only identified by batch + article + paragraph +
# difficulty — the same key the bundled demo spells "2_1_1_Ele".
PASSAGE_PARTS = ("article_batch", "article_id", "text_id", "difficulty_level")


def _add_passage_id(words):
    missing = [c for c in PASSAGE_PARTS if c not in words.columns]
    if missing:
        raise SystemExit(f"cannot build a passage id, missing: {missing}")
    out = words.copy()
    out[PASSAGE] = (
        out[list(PASSAGE_PARTS)].astype(str).agg("_".join, axis=1).astype("string")
    )
    return out


def _panel_font(size: int):
    """A real font for the A/B/C panel labels — PIL's built-in default is ~11 px."""
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _busiest_text(words, text_col):
    counts = (
        words[[text_col, "participant_id"]]
        .drop_duplicates()
        .groupby(text_col)["participant_id"]
        .size()
        .sort_values(ascending=False)
    )
    return counts.index[0], int(counts.iloc[0])


def _drop_boundary_words(words, text_col, text_id):
    """Drop the passage's first and last word.

    The first word absorbs the reader's arrival on the screen (its mean TFD is
    several times any other word's) and the last absorbs the wrap-up before the
    trial ends. Both are standard exclusions in reading research, and leaving
    them in would let two boundary artefacts set the colour scale and the
    y-range for the whole figure.
    """
    ids = words.loc[words[text_col] == text_id, "word_id"]
    lo, hi = ids.min(), ids.max()
    keep = ~((words[text_col] == text_id) & words["word_id"].isin([lo, hi]))
    return words[keep], (lo, hi)


def main():
    words, _ = datasets.load_onestop(ONESTOP_ROOT, regime="ordinary")
    words = _add_passage_id(words)
    text_col = PASSAGE
    text_id, n_readers = _busiest_text(words, text_col)
    n_words = words.loc[words[text_col] == text_id, "word_id"].nunique()
    words, (lo, hi) = _drop_boundary_words(words, text_col, text_id)
    print(
        f"passage {text_id!r} — {n_readers} readers, {n_words} words "
        f"(word {lo} and {hi} excluded as boundary artefacts)"
    )

    per_reader = aggregation.per_reader_word_measure(words, text_col, text_id, MEASURE)
    keep = sorted(per_reader["participant_id"].unique())[:MAX_READERS]
    per_reader_capped = per_reader[per_reader["participant_id"].isin(keep)]
    cohort = aggregation.cohort_word_profile(
        words, text_col, text_id, MEASURE, spread="SD", min_readers=5
    )
    rates = aggregation.word_rate_profile(words, text_col, text_id, min_readers=5)

    panels = [
        (
            "A",
            plots.make_word_matrix_heatmap(
                per_reader_capped,
                row_col="participant_id",
                measure_label=MEASURE_LABEL,
                canvas_width=WIDTH,
                base_font_size=BASE_FONT,
                font_family=FONT,
                height=360,
            ),
        ),
        (
            "B",
            plots.make_word_profile_figure(
                {"Cohort mean": cohort},
                measure_label=MEASURE_LABEL,
                canvas_width=WIDTH,
                base_font_size=BASE_FONT,
                font_family=FONT,
                spread_label="SD",
                height=320,
            ),
        ),
        (
            "C",
            plots.make_word_rate_figure(
                rates,
                canvas_width=WIDTH,
                base_font_size=BASE_FONT,
                font_family=FONT,
                height=320,
            ),
        ),
    ]

    paths = []
    for tag, fig in panels:
        png = FIGS / f"_corpus_{tag}.png"
        save_figure(fig, str(png))
        paths.append((tag, png))

    imgs = [(tag, Image.open(p).convert("RGBA")) for tag, p in paths]
    w = max(im.width for _, im in imgs)
    label_font = _panel_font(34)
    gap, pad = 18, 46
    total_h = sum(im.height for _, im in imgs) + gap * (len(imgs) - 1) + pad * len(imgs)
    montage = Image.new("RGBA", (w, total_h), "white")
    draw = ImageDraw.Draw(montage)
    y = 0
    for tag, im in imgs:
        draw.text((14, y + 4), tag, fill="black", font=label_font)
        montage.paste(im, (0, y + pad), im)
        y += im.height + pad + gap
    montage.convert("RGB").save(FIGS / "fig_corpus.png")
    for _, p in paths:
        p.unlink(missing_ok=True)
    print(
        f"fig_corpus: 3 panels, text {text_id}, {n_readers} readers "
        f"({len(keep)} shown in panel A)"
    )


if __name__ == "__main__":
    main()
