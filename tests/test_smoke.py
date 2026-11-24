"""End-to-end smoke tests against the bundled sample data."""

from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from PIL import Image

from scanpath_studio.aggregation import MEASURES, corpus_overview
from scanpath_studio.api import plot_corpus_figure
from scanpath_studio.data import (
    compute_word_metrics,
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)
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


@pytest.fixture(scope="module")
def paragraph_demo(normalized_demo):
    """The demo's Paragraph screens: one coordinate space per reading, as a
    comparison draws each scanpath."""
    return tuple(frame[frame["screen_id"] == "Paragraph"] for frame in normalized_demo)


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
        """A demo reader with word boxes and no fixations would be counted on
        the 🗂️ Data page but unreachable in the trial picker. Checked on the raw
        files, both formats, before any join."""
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
    def test_overview_plots_observed_reading_ranges(self, normalized_demo):
        words, _ = normalized_demo
        measure = MEASURES["ffd"]
        table = corpus_overview(words, measure, "participant")
        fig = plot_corpus_figure(
            table,
            kind="overview",
            series_col="participant_id",
            measure_label=measure.axis_label,
        )
        trace = fig.data[0]
        readings = words.groupby(["participant_id", "trial_id"])[measure.column].mean()
        for point, label in enumerate(fig.layout.yaxis.ticktext):
            values = readings.loc[label]
            assert trace.x[point] == pytest.approx(values.mean())
            assert trace.x[point] - trace.error_x.arrayminus[point] == pytest.approx(
                values.min()
            )
            assert trace.x[point] + trace.error_x.array[point] == pytest.approx(
                values.max()
            )

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
        """Saccades are never one trace per saccade: a trial with N fixations
        yields at most a small constant number of traces, not O(N)."""
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
        self, paragraph_demo, monkeypatch, compare
    ):
        """Plotly re-validates every layout shape on each addition — an
        `add_shape`, or `update_layout(shapes=existing + new)`, which also
        merges each existing shape into itself — so adding the word boxes, the
        heatmap rects, the frame and the size key one after another would build
        each shape five or six times: 1.3 s for a PoTeC page with both layers
        on, 5 s for a comparison. The builders set them in one go; the size
        key, added after the figure is laid out, costs one more pass."""
        words, fixations = paragraph_demo
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
        # Frames sit on a uniform time grid (not one per fixation), so a
        # long reading is bounded to the grid cap rather than the fixation count.
        assert 1 <= len(fig.frames) <= 360, "Animation should have grid frames"

    def test_comparison_figure(self, paragraph_demo):
        words, fixations = paragraph_demo
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
        # Each screen opens with its marker, in the order the reader saw them,
        # and holds the text column joined in line and word order. A screen the
        # two readers saw differently is shown once per reader.
        src = words[words["text_id"] == first_id].sort_values(
            ["screen_index", "line_idx", "word_id"]
        )
        pieces = []
        for screen, page in src.groupby("screen_id", sort=False):
            seen = {
                reader: " ".join(own["text"].astype(str))
                for reader, own in page.groupby("participant_id")
            }
            if len(set(seen.values())) == 1:
                pieces.append(f"[{screen}] {next(iter(seen.values()))}")
            else:
                pieces += [f"[{screen} · seen by {r}] {t}" for r, t in seen.items()]
        row = table[table["Text ID"] == first_id].iloc[0]
        assert row["Text"] == " ".join(pieces)
        assert re.findall(r"\[(\w+)[\] ]", row["Text"]) == [
            "Title",
            "Question_Preview",
            "Paragraph",
            "Questions",
            "Answers",
            "Answers",
            "Feedback",
        ]
        assert row["# Screens"] == 6
        assert row["# Words"] == len(src.drop_duplicates(["screen_id", "word_id"]))

    def test_readers_answers_and_feedback_are_shown_as_each_saw_them(
        self, normalized_demo
    ):
        words, _ = normalized_demo
        table = self._build(words).set_index("Text ID")
        # Each reader saw this text's four answers in their own order, and one
        # of them answered wrong: the same word ids name different words.
        row = table.loc["2_1_3_Adv"]
        assert row["Differs by reader"] == "Answers (2 versions), Feedback (2 versions)"
        text = row["Text"]
        assert text.count("[Paragraph]") == 1
        assert "[Feedback · seen by l37_273] INCORRECT" in text
        assert "[Feedback · seen by l7_183] CORRECT" in text
        for reader in ("l37_273", "l7_183"):
            answers = words[
                (words["text_id"] == "2_1_3_Adv")
                & (words["screen_id"] == "Answers")
                & (words["participant_id"] == reader)
            ].sort_values(["line_idx", "word_id"])
            seen = " ".join(answers["text"].astype(str))
            assert f"[Answers · seen by {reader}] {seen}" in text
        # The demo's two readers disagree on 15 of its 62 text screens.
        assert table["Differs by reader"].str.count("versions").sum() == 15

    def test_readers_who_agree_share_one_version_and_the_most_seen_comes_first(
        self,
    ):
        words = self._paged_words(readers=("p1", "p2", "p3"))
        # p2 saw page-2 with its words the other way round.
        swapped = (words["participant_id"] == "p2") & (words["screen_id"] == "page-2")
        words.loc[swapped, "text"] = words.loc[swapped, "text"].iloc[::-1].to_numpy()
        row = self._build(words).iloc[0]
        assert row["Text"] == (
            "[page-10] First page "
            "[page-2 · seen by p1, p3] Second page "
            "[page-2 · seen by p2] page Second"
        )
        assert row["Differs by reader"] == "page-2 (2 versions)"
        # The words of the text as most readers saw it.
        assert row["# Words"] == 4

    def test_a_reader_with_an_extra_word_saw_another_version(self):
        import pandas as pd

        words = self._paged_words(readers=("p1", "p2"))
        extra = words.iloc[[0]].assign(participant_id="p2", word_id=3, text="too")
        row = self._build(pd.concat([words, extra], ignore_index=True)).iloc[0]
        assert row["Text"] == (
            "[page-10] First page "
            "[page-2 · seen by p1] Second page "
            "[page-2 · seen by p2] Second page too"
        )

    def test_a_single_screen_text_names_who_saw_each_version(self):
        import pandas as pd

        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3 + ["p2"] * 3,
                "trial_id": ["t1"] * 6,
                "text_id": ["a"] * 6,
                "word_id": [1, 2, 3] * 2,
                "line_idx": [0] * 6,
                "text": ["The", "cat", "sat", "The", "dog", "sat"],
            }
        )
        row = self._build(words).iloc[0]
        assert row["Text"] == "[seen by p1] The cat sat [seen by p2] The dog sat"
        assert row["Differs by reader"] == "2 versions"
        assert row["# Words"] == 3

    @staticmethod
    def _one_text(readings, texts):
        import pandas as pd

        # One single-screen text "a" of three words; `readings` are
        # (participant, trial) pairs and `texts` their middle words.
        return pd.DataFrame(
            [
                {
                    "participant_id": reader,
                    "trial_id": trial,
                    "text_id": "a",
                    "word_id": position,
                    "line_idx": 0,
                    "text": word,
                }
                for (reader, trial), middle in zip(readings, texts, strict=True)
                for position, word in enumerate(["The", middle, "sat"], start=1)
            ]
        )

    def test_a_reader_who_saw_two_versions_is_named_with_each_trial(self):
        words = self._one_text(
            [("p1", "t1"), ("p1", "t2"), ("p2", "t3")], ["cat", "dog", "cat"]
        )
        expected = "[seen by p1 (t1), p2] The cat sat [seen by p1 (t2)] The dog sat"
        assert self._build(words).iloc[0]["Text"] == expected
        # Two versions with one reading each come in the same order either way.
        tied = self._one_text([("p1", "t1"), ("p1", "t2")], ["dog", "cat"])
        backwards = tied.iloc[::-1].reset_index(drop=True)
        for frame in (tied, backwards):
            row = self._build(frame).iloc[0]
            assert row["Text"] == (
                "[seen by p1 (t1)] The dog sat [seen by p1 (t2)] The cat sat"
            )

    def test_the_version_most_participants_saw_comes_first(self):
        # p1 saw "cat" twice; "dog" was seen by p1 once and by p2.
        words = self._one_text(
            [("p1", "t1"), ("p1", "t2"), ("p1", "t3"), ("p2", "t4")],
            ["cat", "cat", "dog", "dog"],
        )
        assert self._build(words).iloc[0]["Text"] == (
            "[seen by p1 (t3), p2] The dog sat [seen by p1 (t1), p1 (t2)] The cat sat"
        )

    def test_a_words_only_table_names_each_reading_by_its_trial(self):
        from scanpath_studio.data import STIMULUS_PARTICIPANT

        words = self._one_text(
            [(STIMULUS_PARTICIPANT, "t1"), (STIMULUS_PARTICIPANT, "t2")],
            ["cat", "dog"],
        )
        assert self._build(words).iloc[0]["Text"] == (
            "[seen by t1] The cat sat [seen by t2] The dog sat"
        )

    def test_versions_alike_but_for_their_word_ids_are_called_so(self):
        words = self._one_text([("p1", "t1"), ("p2", "t2")], ["cat", "cat"])
        # p2's words are numbered from 2.
        words.loc[words["participant_id"] == "p2", "word_id"] += 1
        row = self._build(words).iloc[0]
        assert row["Differs by reader"] == "2 versions; some differ only in word ids"

    def test_versions_differ_only_in_the_words_the_passage_shows(self):
        import pandas as pd

        words = self._one_text([("p1", "t1"), ("p2", "t2")], ["cat", "cat"])
        # p2's table also lists a blank word and a second word under id 2.
        extra = pd.DataFrame(
            {
                "participant_id": ["p2", "p2"],
                "trial_id": ["t2", "t2"],
                "text_id": ["a", "a"],
                "word_id": [4, 2],
                "line_idx": [0, 0],
                "text": ["", "dog"],
            }
        )
        row = self._build(pd.concat([words, extra], ignore_index=True)).iloc[0]
        assert row["Text"] == "The cat sat"
        assert "Differs by reader" not in row.index

    def test_a_screen_without_an_id_is_named_in_the_version_column(self):
        words = self._paged_words(readers=("p1", "p2"))
        words["screen_id"] = words["screen_id"].replace("page-2", "")
        swapped = (words["participant_id"] == "p2") & (words["screen_id"] == "")
        words.loc[swapped, "text"] = "Other"
        row = self._build(words).iloc[0]
        assert row["Differs by reader"] == "(no screen id) (2 versions)"
        assert "[(no screen id) · seen by p2] Other Other" in row["Text"]

    def test_a_text_without_word_text_is_an_empty_passage(self):
        words = self._paged_words(text=["", "", "nan", ""])
        row = self._build(words).iloc[0]
        assert row["Text"] == "[page-10] [page-2]"
        assert row["# Words"] == 0

    def test_texts_every_reader_saw_alike_have_no_version_column(self):
        table = self._build(self._paged_words(readers=("p1", "p2")))
        assert "Differs by reader" not in table.columns
        assert "seen by" not in table.iloc[0]["Text"]

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

    def test_single_screen_texts_have_no_markers_or_screen_column(self, paragraph_demo):
        words, _ = paragraph_demo
        table = self._build(words.drop(columns=["screen_id", "screen_index"]))
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


def _ink(path: str) -> np.ndarray:
    """Where a stimulus PNG carries ink: any channel well below its white
    background, so the coloured feedback word counts as well as black text."""
    return np.asarray(Image.open(path).convert("RGB")).min(axis=2) < 128


class TestStimulusImageAlignment:
    """Each demo screen's stimulus PNG sits under its word boxes.

    The builder places each image where the experiment's DataViewer draw list
    drew it (``image_x``, ``image_y``). OneStop's word boxes are centred on
    their words — half a space of margin left and right, the line's leading
    above and below — so on a correctly placed image the ink inside each box
    has about as much margin on one side as on the other. An image placed a
    few pixels off shifts that balance for every box on its screen: a 5 px
    shift sideways or a 36 px shift down, or the flush-left origin (358), fails.
    """

    def test_every_screen_has_its_image(self, normalized_demo):
        words, fixations = normalized_demo
        assert set(words["screen_id"]) == {
            "Title",
            "Question_Preview",
            "Paragraph",
            "Questions",
            "Answers",
            "Feedback",
        }
        for frame in (words, fixations):
            assert frame["image_path"].notna().all()
            assert frame["image_path"].map(os.path.exists).all()

    def test_every_word_sits_centred_on_its_box(self, normalized_demo):
        words, _ = normalized_demo
        skews = []
        for image_path, group in words.groupby("image_path", sort=True):
            ink = _ink(image_path)
            name = os.path.basename(image_path)
            boxes = group.drop_duplicates(subset=["x", "y", "width", "height"])
            for box in boxes.itertuples(index=False):
                x0, y0 = int(box.x - box.image_x), int(box.y - box.image_y)
                x1, y1 = x0 + int(box.width), y0 + int(box.height)
                region = ink[max(y0, 0) : max(y1, 0), max(x0, 0) : max(x1, 0)]
                assert region.any(), f"{name}: no ink under the box of {box.text!r}"
                columns = np.flatnonzero(region.any(axis=0)) + max(x0, 0) - x0
                rows = np.flatnonzero(region.any(axis=1)) + max(y0, 0) - y0
                horizontal = columns[0] - (x1 - x0 - 1 - columns[-1])
                vertical = rows[0] - (y1 - y0 - 1 - rows[-1])
                skews.append((name, box.text, horizontal, vertical))
        table = pd.DataFrame(skews, columns=["image", "word", "horizontal", "vertical"])
        # Glyph shapes tip single words a few pixels either way ('lone-wolf
        # leans right, work. left); a misplaced image moves the whole screen.
        worst = table[["horizontal", "vertical"]].abs()
        assert worst["horizontal"].max() <= 10, table.loc[worst["horizontal"].idxmax()]
        assert worst["vertical"].max() <= 16, table.loc[worst["vertical"].idxmax()]
        medians = table.groupby("image")[["horizontal", "vertical"]].median().abs()
        assert (medians["horizontal"] <= 3).all(), medians.nlargest(3, "horizontal")
        assert (medians["vertical"] <= 6).all(), medians.nlargest(3, "vertical")


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
    """The control has to live in this embed, not on the chart wrapper.

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
