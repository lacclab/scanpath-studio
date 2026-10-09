"""EXP-1 / EXP-2 — export path patterns, and titles/captions on the figure."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from scanpath_studio.export import (
    DEFAULT_CAPTION_PATTERN,
    DEFAULT_PATH_PATTERN,
    DEFAULT_TITLE_PATTERN,
    ArchiveNames,
    ExportOptions,
    annotate_figure,
    bundle_member_names,
    path_structure_error,
    pattern_error,
    pattern_fields,
    render_pattern,
    resolve_export_path,
)


@pytest.fixture
def fields() -> dict:
    return pattern_fields(
        "p1",
        "t1",
        pd.DataFrame({"word_id": [0, 1, 2]}),
        pd.DataFrame({"duration_ms": [100.0, 250.0]}),
        {"show_fixations": True, "show_saccades": True, "color_by": "(uniform)"},
        combo_row={"participant_id": "p1", "trial_id": "t1", "text_id": "story-3"},
    )


class TestPatternFields:
    def test_carries_the_combo_row_and_the_counts(self, fields):
        assert fields["text_id"] == "story-3"
        assert fields["n_words"] == 3
        assert fields["n_fixations"] == 2
        # Rounded to 1 dp — it's a caption/filename value, not a measure.
        assert fields["reading_time_s"] == pytest.approx(0.3)

    def test_settings_summary_lists_the_visible_layers(self, fields):
        assert "fixations" in fields["settings"]
        assert "saccades" in fields["settings"]
        assert "heatmap" not in fields["settings"]

    def test_uniform_colour_is_not_reported_as_a_colour_mapping(self, fields):
        assert "colour by" not in fields["settings"]

    def test_text_id_falls_back_to_the_trial(self):
        fields = pattern_fields("p1", "t9", pd.DataFrame(), pd.DataFrame(), {})
        assert fields["text_id"] == "t9"


class TestPatternValidation:
    def test_a_valid_pattern_has_no_error(self, fields):
        assert pattern_error(DEFAULT_PATH_PATTERN, fields) is None
        assert pattern_error(DEFAULT_TITLE_PATTERN, fields) is None
        assert pattern_error(DEFAULT_CAPTION_PATTERN, fields) is None

    def test_an_unknown_field_is_named_along_with_what_is_available(self, fields):
        error = pattern_error("{participant_id}/{nope}.png", fields)
        assert "{nope}" in error
        assert "{trial_id}" in error

    def test_every_unknown_field_is_reported_not_just_the_first(self, fields):
        error = pattern_error("{a}{b}", fields)
        assert "{a}" in error and "{b}" in error


class TestPathResolution:
    def test_the_default_reproduces_the_historical_layout(self, fields):
        path = resolve_export_path(
            DEFAULT_PATH_PATTERN,
            fields,
            artifact="figure",
            ext="png",
            used=ArchiveNames(),
        )
        assert path == "per_trial/p1__t1/figure.png"

    def test_a_custom_pattern_builds_the_requested_tree(self, fields):
        path = resolve_export_path(
            "{participant_id}/{trial_id}_{artifact}.{ext}",
            fields,
            artifact="figure",
            ext="svg",
            used=ArchiveNames(),
        )
        assert path == "p1/t1_figure.svg"

    def test_the_artifact_may_span_folders_but_data_values_may_not(self):
        """`layers/fixations` is tool-controlled; a trial id is not."""
        fields = pattern_fields("p1", "a/b", pd.DataFrame(), pd.DataFrame(), {})
        path = resolve_export_path(
            DEFAULT_PATH_PATTERN,
            fields,
            artifact="layers/fixations",
            ext="svg",
            used=ArchiveNames(),
        )
        assert path == "per_trial/p1__a_b/layers/fixations.svg"

    def test_a_traversing_value_cannot_escape_the_folder(self):
        """A `..` inside a value is flattened into its segment, never a segment
        of its own — so the zip entry stays under the folder the pattern names."""
        fields = pattern_fields("..", "../..", pd.DataFrame(), pd.DataFrame(), {})
        path = resolve_export_path(
            DEFAULT_PATH_PATTERN,
            fields,
            artifact="figure",
            ext="png",
            used=ArchiveNames(),
        )
        assert path.startswith("per_trial/")
        assert not any(part in (".", "..") for part in path.split("/"))

    def test_colliding_paths_are_disambiguated_not_silently_overwritten(self):
        """Two zip entries at one name loses a file, so the second is suffixed."""
        used = ArchiveNames()
        pattern = "figures/{artifact}.{ext}"
        first = resolve_export_path(
            pattern,
            pattern_fields("p1", "t1", pd.DataFrame(), pd.DataFrame(), {}),
            artifact="figure",
            ext="png",
            used=used,
        )
        second = resolve_export_path(
            pattern,
            pattern_fields("p2", "t2", pd.DataFrame(), pd.DataFrame(), {}),
            artifact="figure",
            ext="png",
            used=used,
        )
        assert first == "figures/figure.png"
        assert second == "figures/figure-2.png"

    def test_a_missing_field_value_becomes_a_placeholder_not_a_crash(self):
        fields = pattern_fields("p1", "t1", pd.DataFrame(), pd.DataFrame(), {})
        fields["difficulty_level"] = None
        path = resolve_export_path(
            "{difficulty_level}/{artifact}.{ext}",
            fields,
            artifact="figure",
            ext="png",
            used=ArchiveNames(),
        )
        assert path == "na/figure.png"

    def test_titles_keep_readable_values_while_paths_sanitize(self, fields):
        assert render_pattern("{text_id}", fields) == "story-3"
        assert render_pattern("{settings}", fields).startswith("layers:")


class TestTheBundlesOwnNames:
    """#412 — a pattern that names a trial's file like one of the bundle's own
    files gets the next free name; the bundle's file keeps its own."""

    @pytest.mark.parametrize(
        ("pattern", "expected"),
        [
            ("README.md", "README-2.md"),
            ("index.csv", "index-2.csv"),
            ("columns.json", "columns-2.json"),
            ("run_config.json", "run_config-2.json"),
            ("annotations.json", "annotations-2.json"),
            ("metadata/participants.csv", "metadata/participants-2.csv"),
            ("metadata/texts.parquet", "metadata/texts-2.parquet"),
            ("aggregate/all_fixations.csv", "aggregate/all_fixations-2.csv"),
            ("aggregate/all_reader_summary.csv", "aggregate/all_reader_summary-2.csv"),
            # Unpacked on macOS or Windows, these would be the README.
            ("readme.md", "readme-2.md"),
            ("Index.CSV", "Index-2.CSV"),
            # A file cannot have a folder's name, nor a folder a file's.
            ("metadata", "metadata-2"),
            ("README.md/{artifact}.{ext}", "README-2.md/figure.png"),
            # An ordinary pattern is left alone.
            ("{artifact}.{ext}", "figure.png"),
            ("metadata/{artifact}.{ext}", "metadata/figure.png"),
        ],
    )
    def test_a_trial_file_never_takes_a_bundle_name(self, fields, pattern, expected):
        used = ArchiveNames(bundle_member_names())
        path = resolve_export_path(
            pattern, fields, artifact="figure", ext="png", used=used
        )
        assert path == expected

    def test_the_bundle_keeps_its_names_and_gives_each_out_once(self):
        used = ArchiveNames(["README.md", "metadata/participants.csv"])
        assert used.claim("README.md") == "README-2.md"
        assert used.own("README.md") == "README.md"
        # Written twice by mistake, it would still not be a second member.
        assert used.own("README.md") == "README-3.md"
        # One the reservation missed is claimed like any other name.
        assert used.claim("columns.json") == "columns.json"
        assert used.own("columns.json") == "columns-2.json"

    def test_a_name_that_is_only_asked_about_stays_free(self):
        used = ArchiveNames()
        assert used.claim("figures/figure.png", record=False) == "figures/figure.png"
        assert used.claim("figures/figure.png") == "figures/figure.png"
        assert used.claim("figures/figure.png", record=False) == "figures/figure-2.png"
        assert used.claim("figures/figure.png") == "figures/figure-2.png"

    def test_the_suffix_goes_on_the_file_not_a_dotted_folder(self):
        used = ArchiveNames()
        assert used.claim("v1.2/figure") == "v1.2/figure"
        assert used.claim("v1.2/figure") == "v1.2/figure-2"

    def test_a_run_reserves_only_the_combined_tables_it_can_write(self):
        plain = bundle_member_names(ExportOptions(include_fixations=True))
        assert "README.md" in plain and "metadata/participants.csv" in plain
        assert not any(name.startswith("aggregate/") for name in plain)
        family = bundle_member_names(ExportOptions(include_analysis_family=True))
        assert [n for n in family if n.startswith("aggregate/")] == [
            "aggregate/all_reader_summary.csv"
        ]
        combined = bundle_member_names(
            ExportOptions(
                include_fixations=True, combine_trials=True, table_format="both"
            )
        )
        assert {
            "aggregate/all_fixations.csv",
            "aggregate/all_fixations.parquet",
        } <= set(combined)


def _figure() -> go.Figure:
    fig = go.Figure(go.Scatter(x=[0, 1], y=[0, 1]))
    fig.update_layout(width=800, height=600, margin=dict(l=10, r=10, t=20, b=30))
    return fig


class TestAnnotateFigure:
    """EXP-2 must not shrink the equal-aspect plot — that would break the
    true-to-scale word labels, which are sized for the un-shrunk figure."""

    def _plot_height(self, fig) -> float:
        m = fig.layout.margin
        return fig.layout.height - (m.t or 0) - (m.b or 0)

    def test_no_title_or_caption_leaves_the_figure_untouched(self):
        fig = _figure()
        before = fig.to_plotly_json()
        annotate_figure(fig)
        assert fig.to_plotly_json() == before

    def test_a_title_grows_the_figure_instead_of_the_plot_shrinking(self):
        fig = _figure()
        plot_before = self._plot_height(fig)
        annotate_figure(fig, title="p1 · t1")
        assert fig.layout.title.text == "p1 · t1"
        assert fig.layout.height > 600
        assert self._plot_height(fig) == pytest.approx(plot_before)

    def test_a_caption_grows_the_figure_too(self):
        fig = _figure()
        plot_before = self._plot_height(fig)
        annotate_figure(fig, caption="story-3 · 120 fixations")
        assert self._plot_height(fig) == pytest.approx(plot_before)
        assert any("story-3" in a.text for a in fig.layout.annotations)

    def test_both_together_still_preserve_the_plot_region(self):
        fig = _figure()
        plot_before = self._plot_height(fig)
        annotate_figure(fig, title="T", caption="C")
        assert self._plot_height(fig) == pytest.approx(plot_before)

    def test_a_multi_line_caption_reserves_more_room(self):
        one, two = _figure(), _figure()
        annotate_figure(one, caption="a")
        annotate_figure(two, caption="a\nb\nc")
        assert two.layout.height > one.layout.height

    def test_the_caption_sits_below_the_plot_not_over_it(self):
        fig = _figure()
        annotate_figure(fig, caption="below")
        note = fig.layout.annotations[0]
        assert note.y == 0 and note.yanchor == "top" and note.yshift < 0


@pytest.mark.parametrize(
    "pattern",
    [DEFAULT_PATH_PATTERN, "{artifact}.{ext}", "figs/{trial_id}-{artifact}.{ext}"],
)
def test_ordinary_path_patterns_are_accepted(pattern):
    assert path_structure_error(pattern) is None


def test_a_value_cannot_make_a_path_leave_the_zip(fields):
    """The second layer: a *value* of `..` or `` is one safe segment."""
    path = resolve_export_path(
        "{text_id}/{artifact}.{ext}",
        {**fields, "text_id": ".."},
        artifact="figure",
        ext="png",
        used=ArchiveNames(),
    )
    assert path == "_/figure.png"


def _naming_panel():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.export import render_export_options

    combos = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
    render_export_options(st, combos, key_prefix="bulk")


def test_the_example_shows_the_name_a_clashing_pattern_gets():
    """#412: the pattern is accepted, and its example says what it becomes."""
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    at = streamlit_testing.AppTest.from_function(_naming_panel).run(timeout=30)
    assert not at.exception, at.exception

    def example():
        return next(c.value for c in at.caption if c.value.startswith("Example:"))

    assert example() == "Example: `per_trial/p1__t1/figure.png`"
    at.text_input(key="bulk_path_pattern").set_value("README.md").run(timeout=30)
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert example().startswith("Example: `README-2.md` — `README.md` would clash")
