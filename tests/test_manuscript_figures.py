"""The published OneStop panels retain the complete reading and each frame."""

from __future__ import annotations

from PIL import Image


def test_manuscript_replay_preserves_all_fixations_and_panel_edges(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PAPER_FIGURES_DIR", str(tmp_path))
    from paper import paper_figs

    def save_panel(fig, path):
        left, right = fig.layout.xaxis.range
        bottom, top = fig.layout.yaxis.range
        markers = next(trace for trace in fig.data if trace.name == "Fixations")
        assert all(left <= x <= right for x in markers.x)
        assert all(top <= y <= bottom for y in markers.y)
        image = Image.new("RGB", (120, 100), "white")
        image.putpixel((0, image.height - 1), (255, 0, 0))
        image.save(path)

    monkeypatch.setattr(paper_figs, "FIGS", tmp_path)
    monkeypatch.setattr(paper_figs, "save_figure", save_panel)
    words, fixations = paper_figs.paragraph_demo()
    paper_figs.scanpath_fig(words, fixations)
    paper_figs.replay_fig(words, fixations)
    with Image.open(tmp_path / "fig_replay.png") as montage:
        assert (
            sum(montage.getpixel((0, y)) == (255, 0, 0) for y in range(montage.height))
            == 3
        )
