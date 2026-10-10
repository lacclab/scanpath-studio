"""End-to-end smoke tests against the bundled sample data."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
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
    make_scanpath_animation,
    make_scanpath_figure,
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

    def test_every_reader_and_trial_with_word_boxes_has_fixations(self):
        """DATA-43: the demo shipped a reader (`l25_1042`) with word boxes and
        no fixations — counted on the 🗂️ Data page, unreachable in the trial
        picker. Checked on the raw files, both formats, before any join."""
        from scanpath_studio.update_sample_data import (
            DEFAULT_OUTPUT_DIR,
            check_fixations_cover_words,
        )

        for suffix in ("csv", "parquet"):
            read = pd.read_csv if suffix == "csv" else pd.read_parquet
            ia = read(DEFAULT_OUTPUT_DIR / f"ia.{suffix}")
            fixations = read(DEFAULT_OUTPUT_DIR / f"fixations.{suffix}")
            assert set(ia["participant_id"]) == set(fixations["participant_id"])
            check_fixations_cover_words(ia, fixations)

    def test_the_build_refuses_a_trial_without_fixations(self):
        from scanpath_studio.update_sample_data import check_fixations_cover_words

        ia = pd.DataFrame(
            {"participant_id": ["a", "b"], "unique_trial_id": ["a_t1", "b_t1"]}
        )
        fixations = ia.iloc[:1]
        with pytest.raises(RuntimeError, match="no fixations"):
            check_fixations_cover_words(ia, fixations)
        check_fixations_cover_words(ia.iloc[:1], fixations)

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
            show_fixation_colorbar=False,
            show_heatmap_colorbar=False,
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
            show_fixation_colorbar=False,
            show_heatmap_colorbar=False,
            fixation_color_range=None,
            heatmap_range=None,
        )
        # Expect (in any order): saccades trace (1) + fixations trace (1) + optional word labels.
        # Never one-per-saccade.
        assert len(fig.data) <= 5, f"Too many traces: {len(fig.data)}"

    @pytest.mark.parametrize("compare", [False, True])
    def test_layout_shapes_are_validated_about_once(
        self, normalized_demo, monkeypatch, compare
    ):
        """#422: Plotly re-validates every layout shape on each addition — an
        `add_shape`, or `update_layout(shapes=existing + new)`, which also
        merges each existing shape into itself — so adding the word boxes, the
        heatmap rects, the frame and the size key one after another built each
        shape five or six times: 1.3 s for a PoTeC page with both layers on,
        5 s for a comparison. The builders now set them in one go; the size
        key, added after the figure is laid out, costs one more pass."""
        words, fixations = normalized_demo
        trials = list(
            fixations.groupby(["participant_id", "trial_id"]).size().index[:2]
        )
        built = 0
        real_init = go.layout.Shape.__init__

        def counting_init(self, *args, **kwargs):
            nonlocal built
            built += 1
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(go.layout.Shape, "__init__", counting_init)
        settings = dict(
            canvas_width=1024,
            canvas_height=600,
            base_font_size=14,
            show_words=True,
            show_heatmap=True,
        )
        if compare:
            fig = make_comparison_figure(
                words, fixations, *trials, layout="overlay", **settings
            )
        else:
            pid, tid = trials[0]
            fig = make_scanpath_figure(
                words[(words["participant_id"] == pid) & (words["trial_id"] == tid)],
                fixations[
                    (fixations["participant_id"] == pid)
                    & (fixations["trial_id"] == tid)
                ],
                **settings,
            )
        shapes = len(fig.layout.shapes)
        assert shapes > 100, "need boxes and heatmap rects for this to mean much"
        assert built <= 2 * shapes + 10, (built, shapes)

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
        assert 1 <= len(fig.frames) <= 360, "Animation should have grid frames"

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

    @staticmethod
    def _paged_words(readers=("p1",), **extra):
        import pandas as pd

        # Page 2 is listed first and its id sorts after page 10's would: only
        # `screen_index` says which page comes first. Word ids and lines start
        # again on every page.
        one = pd.DataFrame(
            {
                "trial_id": ["t1"] * 4,
                "text_id": ["text-1"] * 4,
                "screen_id": ["page-2", "page-2", "page-10", "page-10"],
                "screen_index": [2, 2, 1, 1],
                "word_id": [1, 2, 1, 2],
                "line_idx": [0, 0, 0, 0],
                "text": ["Second", "page", "First", "page"],
                **extra,
            }
        )
        return pd.concat(
            [one.assign(participant_id=reader) for reader in readers],
            ignore_index=True,
        )

    def test_pages_whose_word_ids_restart_are_all_kept_in_screen_order(self):
        table = self._build(self._paged_words())
        assert len(table) == 1
        row = table.iloc[0]
        assert row["# Words"] == 4
        assert row["# Screens"] == 2
        assert row["Text"] == "[page-10] First page [page-2] Second page"

    def test_repeated_readers_do_not_repeat_the_text(self):
        table = self._build(self._paged_words(readers=("p1", "p2", "p3")))
        row = table.iloc[0]
        assert row["# Words"] == 4
        assert row["Text"] == "[page-10] First page [page-2] Second page"

    def test_each_reader_s_earliest_screen_position_orders_the_pages(self):
        import pandas as pd

        # A second reader saw the pages the other way round (MultiplEYE
        # shuffles question screens per reader): the earliest position wins.
        base = self._paged_words()
        # p1: page-10 at 2, page-2 at 3; p2: page-2 at 1, page-10 at 2.
        words = base.assign(screen_index=base["screen_index"].map({1: 2, 2: 3}))
        other = base.assign(
            participant_id="p2", screen_index=base["screen_index"].map({1: 2, 2: 1})
        )
        table = self._build(pd.concat([words, other], ignore_index=True))
        assert table.iloc[0]["Text"] == "[page-2] Second page [page-10] First page"

    def test_a_question_screen_is_marked_as_one(self):
        words = self._paged_words(
            screen_kind=["question", "question", "reading", "reading"]
        )
        text = self._build(words).iloc[0]["Text"]
        assert text == "[page-10 · reading] First page [page-2 · question] Second page"

    def test_single_screen_texts_have_no_markers_or_screen_column(
        self, normalized_demo
    ):
        words, _ = normalized_demo
        table = self._build(words)
        assert "# Screens" not in table.columns
        assert not table["Text"].str.startswith("[").any()

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

    Correct origin for the OneStop demo is ``(image_x=368, image_y=186)`` — where
    the experiment's own Experiment Builder drew the paragraph image (its
    ``.vcl`` view commands, BUG-97). Each word box is then centred on its
    word: half a space of margin on each side, and the line centers coincide.
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

            # Horizontal: the boxes are centred on their words (BUG-97), so the
            # page's left ink edge sits half a space inside the leftmost box —
            # image_x + first-ink-col ≈ min box x + advance / 2. The old,
            # flush-left origin (358) lands ~10 px off and fails.
            first = boxes.loc[boxes["x"].idxmin()]
            half_space = float(first["width"]) / (len(str(first["text"])) + 1) / 2
            left_edge = image_x + _png_first_ink_col(image_path)
            expected = float(boxes["x"].min()) + half_space
            assert abs(left_edge - expected) < 5.0, (
                f"{os.path.basename(image_path)}: stimulus image misaligned "
                f"horizontally (left edge {left_edge:.1f}, expected {expected:.1f})"
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


def test_true_scale_html_offers_fullscreen() -> None:
    """VIZ-37 — the control has to live in this embed, not on the chart wrapper.

    Streamlit 1.61 adds a fullscreen button to `st.plotly_chart`, but the
    spatial figures deliberately do not go through it: a responsive re-layout
    is exactly what breaks the data-to-pixel scale this embed exists to hold.
    """
    from scanpath_studio import tabs

    html, _ = tabs._true_scale_html(
        '<div id="truescale-single"></div>',
        key="single",
        width=900,
        height=600,
        max_height=None,
        zoomable=True,
    )
    assert 'id="fsbtn-single"' in html
    # Fullscreen fits *both* dimensions to the screen; in the column the
    # figure fits the width, growing past 1x only while it fits the window.
    assert "Math.min(avail / W, availH / H)" in html
    assert "Math.min(avail / W, growCap())" in html
    # Two ways up, because `st.iframe` exposes no `allowfullscreen` and a
    # permissions policy may refuse — silently, hence the timeout fallback.
    assert "requestFullscreen" in html and "overlayOn" in html
    # Escape leaves the overlay; native fullscreen's own Escape arrives as
    # `fullscreenchange` on the parent document.
    assert '"Escape"' in html and "fullscreenchange" in html


def test_true_scale_html_small_multiples_have_no_fullscreen() -> None:
    """Fullscreen follows zoom: standalone figures get both, grid cells neither.

    The shared renderer serves the main scanpath, the animation, the comparison
    and the stimulus figure (all `max_height=None`), plus the line-assignment
    and Multiple Comparison panels (capped). A per-cell fullscreen button in a
    grid is chrome on every tile for a figure sized to a cell, so the capped
    call sites keep the plain fit-to-cell behaviour — one predicate, not two.
    """
    from scanpath_studio import tabs

    html, _ = tabs._true_scale_html(
        '<div id="truescale-grid"></div>',
        key="grid",
        width=900,
        height=600,
        max_height=240,
        zoomable=False,
    )
    assert 'id="fsbtn-grid"' not in html
