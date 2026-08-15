"""Render the OneStop case-study figures for the manuscript, headless via the app pipeline.

Produces (into paper/figures, or $PAPER_FIGURES_DIR):
  fig_scanpath.png   — one clean layered scanpath, fixations numbered + sized/coloured by duration
  fig_comparison.png — two readers of the same paragraph, overlaid on one canvas (blue/red)
  fig_replay.png     — three replay frames (a montage) at increasing reading time

Run from the app repo:  cd app && uv run python paper/paper_figs.py
"""

from __future__ import annotations

import os
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio import constants, plots
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
CANVAS = (1280, 320)  # OneStop demo paragraph text-area extent (wide, few lines)

SCAN_TRIAL = ("l7_1090", "l7_1090_2_2_4_Ele_r0")  # 35 fixations, short + clean
CMP_TEXT = "2_1_1_Ele"  # read by two demo participants


def _trial_fix(fixations, pid, tid):
    return fixations[(fixations.participant_id == pid) & (fixations.trial_id == tid)]


def scanpath_fig(words, fixations):
    pid, tid = SCAN_TRIAL
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=CANVAS,
        show_order=True,
        show_heatmap=False,
        show_words=False,  # no AOI grid; keep just text + fixations + saccades
        color_by="duration_ms",
    )
    save_figure(fig, str(FIGS / "fig_scanpath.png"))
    print(f"fig_scanpath: {pid} / {tid} ({len(_trial_fix(fixations, pid, tid))} fix)")


def comparison_fig(words, fixations):
    combos = sps.list_trials(words, fixations)
    tx = words[["participant_id", "trial_id", "text_id"]].drop_duplicates()
    combos = combos.merge(tx, on=["participant_id", "trial_id"])
    pair = combos[combos.text_id == CMP_TEXT].drop_duplicates("participant_id").head(2)
    (pa, ta), (pb, tb) = (
        (pair.iloc[0].participant_id, pair.iloc[0].trial_id),
        (pair.iloc[1].participant_id, pair.iloc[1].trial_id),
    )
    fig = plots.make_comparison_figure(
        words,
        fixations,
        (pa, ta),
        (pb, tb),
        canvas_width=CANVAS[0],
        canvas_height=CANVAS[1],
        font_family=constants.FONT_FAMILY,
        base_font_size=16,
        show_words=False,
        show_word_labels=True,
        layout="overlay",
        show_legend=True,
        trial_labels=(f"Reader {pa}", f"Reader {pb}"),
    )
    save_figure(fig, str(FIGS / "fig_comparison.png"))
    print(f"fig_comparison: {pa}/{ta} vs {pb}/{tb} on text {CMP_TEXT}")


def replay_fig(words, fixations):
    """Three frames of the scanpath at increasing reading time, montaged."""
    from PIL import Image, ImageDraw

    pid, tid = SCAN_TRIAL
    tf = _trial_fix(fixations, pid, tid).sort_values("order_in_trial")
    n = len(tf)
    t0 = tf["timestamp_ms"].iloc[0]
    frames = []
    for frac in (0.33, 0.66, 1.0):
        k = max(2, round(n * frac))
        keep = set(tf["order_in_trial"].iloc[:k])
        sub = fixations[
            ~((fixations.participant_id == pid) & (fixations.trial_id == tid))
            | (fixations["order_in_trial"].isin(keep))
        ]
        fig = sps.plot_scanpath(
            words,
            sub,
            pid,
            tid,
            canvas_size=CANVAS,
            show_order=True,
            show_heatmap=False,
            show_words=False,
            color_by="duration_ms",
        )
        png = FIGS / f"_replay_{k}.png"
        save_figure(fig, str(png))
        elapsed = (tf["timestamp_ms"].iloc[k - 1] - t0) / 1000.0
        frames.append((png, elapsed))

    imgs = [Image.open(p).convert("RGBA") for p, _ in frames]
    w = max(i.width for i in imgs)
    gap = 18
    montage = Image.new(
        "RGBA", (w, sum(i.height for i in imgs) + gap * len(imgs) + 30), "white"
    )
    draw = ImageDraw.Draw(montage)
    y = 0
    for (p, elapsed), im in zip(frames, imgs):
        draw.text((10, y + 4), f"{elapsed:.1f} s", fill="black")
        montage.paste(im, (0, y + 26), im)
        y += im.height + gap + 26
    montage.convert("RGB").save(FIGS / "fig_replay.png")
    for p, _ in frames:
        p.unlink(missing_ok=True)
    print(f"fig_replay: 3 frames of {pid} / {tid}")


def main():
    words, fixations = sps.load_sample_data()
    scanpath_fig(words, fixations)
    comparison_fig(words, fixations)
    replay_fig(words, fixations)


if __name__ == "__main__":
    main()
