"""End-to-end smoke tests against the bundled sample data."""

from __future__ import annotations

import os

import numpy as np
import plotly.graph_objects as go
import pytest
from PIL import Image

from scanpath_studio.data import (
    compute_word_metrics,
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)
from scanpath_studio.measures import cluster_word_lines
from scanpath_studio.plots import (
    make_comparison_figure,
    make_fixation_duration_histogram,
    make_scanpath_animation,
    make_scanpath_figure,
    make_word_measure_bar_figure,
)


@pytest.fixture(scope="module")
def normalized_demo():
    """Load + normalize the bundled OneStop sample data once per test module."""
    words_raw, fixations_raw = load_sample_data()
    assert not words_raw.empty, "Sample IA file missing"
    assert not fixations_raw.empty, "Sample fixations file missing"

    word_schema = infer_word_schema(words_raw)
    fix_schema = infer_fix_schema(fixations_raw)
    assert word_schema is not None, "Schema inference failed for sample IA"
    assert fix_schema is not None, "Schema inference failed for sample fixations"

    words = normalize_words(words_raw, word_schema)
    fixations = normalize_fixations(fixations_raw, fix_schema)
    return words, fixations


class TestSampleDataPipeline:
    def test_required_columns(self, normalized_demo):
        words, fixations = normalized_demo
        for col in [
            "participant_id",
            "trial_id",
            "word_id",
            "x",
            "y",
            "width",
            "height",
        ]:
            assert col in words.columns, f"missing canonical column {col}"
        for col in [
            "participant_id",
            "trial_id",
            "x",
            "y",
            "duration_ms",
            "timestamp_ms",
        ]:
            assert col in fixations.columns, f"missing canonical column {col}"

    def test_has_multiple_participants(self, normalized_demo):
        words, _ = normalized_demo
        assert words["participant_id"].nunique() >= 2, (
            "Demo corpus should bundle multiple participants for the comparison feature"
        )

    def test_has_both_difficulty_levels(self, normalized_demo):
        words, _ = normalized_demo
        if "difficulty_level" in words.columns:
            levels = set(words["difficulty_level"].dropna().unique())
            assert len(levels) >= 2, (
                f"Demo corpus should span both difficulty levels; got {levels}"
            )

    def test_linguistic_features_present(self, normalized_demo):
        words, _ = normalized_demo
        for col in ["gpt2_surprisal", "wordfreq_frequency", "universal_pos"]:
            assert col in words.columns, (
                f"Demo corpus should carry NLP-relevant feature: {col}"
            )


class TestPipelineFigures:
    def test_scanpath_figure_renders(self, normalized_demo):
        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        fig = make_scanpath_figure(
            tw,
            tf,
            canvas_width=1024,
            canvas_height=600,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=True,
            show_order=True,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#111111",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1, "Expected at least one trace"

    def test_saccades_collapsed_into_single_trace(self, normalized_demo):
        """Regression: the per-saccade-trace explosion (one trace per saccade)
        was a known perf bug. A trial with N fixations should now yield at
        most a small constant number of traces, not O(N)."""
        words, fixations = normalized_demo
        biggest = fixations.groupby(["participant_id", "trial_id"]).size().idxmax()
        pid, tid = biggest
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        assert len(tf) >= 10, "need a non-trivial trial for this regression test"
        fig = make_scanpath_figure(
            tw,
            tf,
            canvas_width=1024,
            canvas_height=600,
            base_font_size=14,
            font_family="monospace",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=False,
            show_fixations=True,
            show_order=False,
            show_saccades=True,
            show_heatmap=False,
            color_by="duration_ms",
            heatmap_metric=None,
            marker_size_range=(8, 24),
            order_font_size=10,
            order_font_color="#111111",
            show_colorbars=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        # Expect (in any order): saccades trace (1) + fixations trace (1) + optional word labels.
        # Never one-per-saccade.
        assert len(fig.data) <= 5, f"Too many traces: {len(fig.data)}"

    def test_word_measure_bar(self, normalized_demo):
        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        measures = compute_word_metrics(tw, tf)
        # Pick whatever first-fixation measure is present
        measure = next(
            (
                c
                for c in [
                    "first_fixation_ms",
                    "first_pass_gaze_duration_ms",
                    "total_fixation_duration_ms",
                ]
                if c in measures.columns
            ),
            None,
        )
        assert measure is not None
        fig = make_word_measure_bar_figure(
            measures,
            measure=measure,
            canvas_width=1024,
            base_font_size=14,
            font_family="monospace",
        )
        assert isinstance(fig, go.Figure)

    def test_fixation_duration_histogram(self, normalized_demo):
        _, fixations = normalized_demo
        fig = make_fixation_duration_histogram(
            fixations.head(200),
            canvas_width=800,
            base_font_size=14,
            font_family="monospace",
        )
        assert isinstance(fig, go.Figure)

    def test_animation_has_frames(self, normalized_demo):
        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        fig = make_scanpath_animation(
            tw,
            tf,
            canvas_width=1024,
            canvas_height=600,
            base_font_size=14,
            font_family="monospace",
        )
        # VIZ-11: frames sit on a uniform time grid (not one per fixation), so a
        # long reading is bounded to the grid cap rather than the fixation count.
        assert 1 <= len(fig.frames) <= 361, "Animation should have grid frames"

    def test_comparison_figure(self, normalized_demo):
        words, fixations = normalized_demo
        participants = sorted(words["participant_id"].unique())
        if len(participants) < 2:
            pytest.skip("Need >=2 participants for comparison")
        p1, p2 = participants[:2]
        # Find a trial each participant has
        t1 = words[words["participant_id"] == p1]["trial_id"].iloc[0]
        t2 = words[words["participant_id"] == p2]["trial_id"].iloc[0]
        fig = make_comparison_figure(
            words,
            fixations,
            (p1, t1),
            (p2, t2),
            canvas_width=1024,
            canvas_height=600,
            font_family="monospace",
            base_font_size=14,
            layout="overlay",
        )
        assert isinstance(fig, go.Figure)

    def test_marker_sizes_consistent_across_figure_types(self, normalized_demo):
        """The same fixation should render at the same size in single-trial
        and comparison figures."""
        from scanpath_studio.plots import _compute_marker_sizes

        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        sizes = _compute_marker_sizes(tf["duration_ms"])
        assert sizes.min() >= 8
        assert sizes.max() <= 24


class TestStimuliTable:
    """The Raw Data → Stimuli subtab reconstructs one passage per Text ID from
    the word table (`tabs._build_stimuli_table_cached`)."""

    def _build(self, words):
        from scanpath_studio.data import frame_fingerprint
        from scanpath_studio.tabs import _build_stimuli_table_cached

        # frame_fingerprint keys the cache; pass it explicitly like the app does.
        return _build_stimuli_table_cached(words, cache_key=frame_fingerprint(words))

    def test_one_row_per_text_with_curated_columns(self, normalized_demo):
        words, _ = normalized_demo
        table = self._build(words)
        assert list(table.columns)[:1] == ["Text ID"]
        assert "Text" in table.columns and "# Words" in table.columns
        # One row per unique mapped text id, deduped across participants.
        assert len(table) == words["text_id"].nunique()
        assert table["Text ID"].is_unique

    def test_text_reconstructed_in_reading_order(self, normalized_demo):
        words, _ = normalized_demo
        table = self._build(words)
        first_id = table.iloc[0]["Text ID"]
        # The reconstruction is just the text column joined in word order.
        src = words[words["text_id"] == first_id].drop_duplicates(
            subset=["text_id", "word_id"]
        )
        src = src.sort_values(["line_idx", "word_id"])
        expected = " ".join(w for w in src["text"].astype(str) if w and w != "nan")
        row = table[table["Text ID"] == first_id].iloc[0]
        assert row["Text"] == expected
        assert row["Text"].strip() != ""
        assert row["# Words"] > 0

    def test_empty_words_returns_empty_table(self):
        import pandas as pd

        out = self._build(pd.DataFrame())
        assert out.empty
        assert "Text ID" in out.columns


class TestPerWordMetricsOnSample:
    def test_metrics_computed_on_real_data(self, normalized_demo):
        words, fixations = normalized_demo
        pid = words["participant_id"].iloc[0]
        tid = words["trial_id"].iloc[0]
        tw = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
        tf = fixations[
            (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
        ]
        metrics = compute_word_metrics(tw, tf)
        assert not metrics.empty
        # Should have at least the canonical measures (either from IA columns
        # or computed from first principles).
        canonical_present = any(
            c in metrics.columns
            for c in [
                "first_fixation_ms",
                "first_pass_gaze_duration_ms",
                "total_fixation_duration_ms",
            ]
        )
        assert canonical_present


def _png_text_lines(path: str) -> list[tuple[int, int]]:
    """Vertical (top, bottom) pixel bands of each text line in a paragraph PNG —
    runs of rows that carry ink (dark pixels)."""
    gray = np.asarray(Image.open(path).convert("L"))
    has_ink = (gray < 128).sum(axis=1) > 1
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for row, inked in enumerate(has_ink):
        if inked and start is None:
            start = row
        elif not inked and start is not None:
            bands.append((start, row - 1))
            start = None
    if start is not None:
        bands.append((start, len(has_ink) - 1))
    return bands


def _png_first_ink_col(path: str) -> int:
    """Leftmost column carrying ink (the left edge of the rendered text)."""
    gray = np.asarray(Image.open(path).convert("L"))
    return int(np.argmax((gray < 128).sum(axis=0) > 0))


class TestStimulusImageAlignment:
    """The bundled demo ships per-trial stimulus PNGs placed at data
    (``image_x``, ``image_y``). Those origins are *external* metadata (rendered by
    a separate script, not by ``update_sample_data.py``), so this guards against a
    regenerated origin drifting the page off the AOI boxes / fixations — the
    ``image_y=148`` (~36 px too high) bug. Aligns the PNG's own text lines to the
    word boxes; a wrong origin fails here regardless of which script produced it.

    Correct origin for the OneStop demo is ``(image_x=358, image_y=184)``: the
    text is left-aligned at the box left edge, and the line centers coincide.
    """

    def test_image_origin_aligns_page_to_word_boxes(self, normalized_demo):
        words, _ = normalized_demo
        assert "image_path" in words.columns, "demo lost its stimulus-image columns"

        checked = 0
        for image_path, group in words.groupby("image_path", sort=True):
            if not isinstance(image_path, str) or not os.path.exists(image_path):
                continue
            # One set of boxes per paragraph (identical across readers) → dedupe.
            boxes = group.drop_duplicates(subset=["x", "y", "width", "height"]).copy()
            image_x = float(boxes["image_x"].iloc[0])
            image_y = float(boxes["image_y"].iloc[0])

            # Box line centers (visual lines inferred from box-y clustering).
            boxes["_line"] = cluster_word_lines(boxes)
            box_centers = sorted(
                boxes.groupby("_line")
                .apply(lambda g: float((g["y"] + g["height"] / 2).mean()))
                .tolist()
            )
            # PNG line centers mapped into data coords via the image origin.
            bands = _png_text_lines(image_path)
            png_centers = sorted(image_y + (top + bot) / 2 for top, bot in bands)

            assert len(png_centers) == len(box_centers), (
                f"{os.path.basename(image_path)}: PNG has {len(png_centers)} text "
                f"lines but the boxes cluster into {len(box_centers)}"
            )
            diffs = [abs(p - b) for p, b in zip(png_centers, box_centers)]
            # A correct origin lands every line within a few px; the historical
            # 36 px misplacement (or any future regen drift) blows past this.
            assert max(diffs) < 12.0, (
                f"{os.path.basename(image_path)}: stimulus image misaligned "
                f"vertically (max line-center diff {max(diffs):.1f}px, image_y={image_y})"
            )

            # Horizontal: the page's left ink edge sits at the leftmost box edge
            # (text is left-aligned), so image_x + first-ink-col ≈ min box x.
            left_edge = image_x + _png_first_ink_col(image_path)
            assert abs(left_edge - float(boxes["x"].min())) < 8.0, (
                f"{os.path.basename(image_path)}: stimulus image misaligned "
                f"horizontally (left edge {left_edge:.1f} vs box {boxes['x'].min():.1f})"
            )
            checked += 1

        assert checked >= 1, "no bundled stimulus images were available to check"


def test_true_scale_html_carries_zoom_transform() -> None:
    """The embed magnifies via the fit transform, not a Plotly axis re-layout."""
    from scanpath_studio import tabs

    html, iframe_height = tabs._true_scale_html(
        '<div id="truescale-single"></div>',
        key="single",
        width=900,
        height=600,
        max_height=None,
        zoomable=True,
    )
    assert iframe_height == 612
    # One uniform scale for fit x zoom, so markers/labels/strokes magnify too.
    assert "base * zoom" in html
    assert 'id="zoombar-single"' in html
    # Plotly's own drag-zoom is switched off — it is what breaks the sizing.
    assert "dragmode: false" in html


def test_true_scale_html_small_multiples_have_no_zoom() -> None:
    """Capped grid panels keep the plain fit-to-cell behaviour."""
    from scanpath_studio import tabs

    html, iframe_height = tabs._true_scale_html(
        '<div id="truescale-grid"></div>',
        key="grid",
        width=900,
        height=600,
        max_height=240,
        zoomable=False,
    )
    assert iframe_height == 252
    assert "240 / H" in html
    assert "zoombar" not in html
