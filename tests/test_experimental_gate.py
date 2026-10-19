"""The default build hides drift correction and NLD similarity.

Both features work and both stay in the codebase — this is a *visibility* gate,
because shipping a half-wired control invites users to lean on it. The rest of
the suite runs with ``SCANPATH_EXPERIMENTAL=1`` (see ``tests/conftest.py``) so
it keeps its coverage; this file is the other half: what a user of the default
build must **not** be offered.

Every gate reads the env var at call time, which is what lets one process assert
both builds.
"""

from __future__ import annotations

import argparse

import pandas as pd
import pytest

from scanpath_studio import api, constants, controls, tabs, tour
from tests.conftest import APP_SCRIPT, SUBTAB_KEY, pin_view

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


pytestmark = pytest.mark.usefixtures("experimental_off")


class TestTheFlagItself:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        assert constants.experimental_features_enabled() is False
        assert constants.drift_correction_enabled() is False
        assert constants.similarity_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_the_env_var_turns_it_on(self, monkeypatch, value):
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, value)
        assert constants.experimental_features_enabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
    def test_anything_else_leaves_it_off(self, monkeypatch, value):
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, value)
        assert constants.experimental_features_enabled() is False

    def test_it_is_read_at_call_time(self, monkeypatch):
        """Not at import. A gate that cached the value would make one surface
        disagree with another depending on import order."""
        assert constants.drift_correction_enabled() is False
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        assert constants.drift_correction_enabled() is True


class TestTheRenderContractResolvesToOff:
    def test_viz_settings_report_no_correction(self):
        import streamlit as st

        st.session_state.clear()
        st.session_state["global_align_algorithm"] = "warp"
        st.session_state["global_align_connectors"] = True
        settings = controls.viz_settings_from_state(pd.DataFrame(), 14)
        # Resolved once, here, rather than each consumer gating separately —
        # which is what makes a link naming it degrade silently and consistently.
        assert settings["align_algorithm"] == "Off"
        assert settings["align_connectors"] is False
        st.session_state.clear()


class TestTheHeadlessSurfacesRefuseRatherThanIgnore:
    """A share link degrades silently because a human can see the figure. A
    script cannot, so returning uncorrected fixations under a stated
    ``drift_correction=`` would be a wrong result with no signal."""

    def test_plot_scanpath_raises(self, normalized_words_df, normalized_fixations_df):
        with pytest.raises(ValueError, match="experimental and off by default"):
            api.plot_scanpath(
                normalized_words_df,
                normalized_fixations_df,
                participant="p1",
                trial="t1",
                drift_correction="warp",
            )

    def test_the_message_names_the_env_var(
        self, normalized_words_df, normalized_fixations_df
    ):
        with pytest.raises(ValueError, match=constants.EXPERIMENTAL_ENV_VAR):
            api.plot_scanpath(
                normalized_words_df,
                normalized_fixations_df,
                participant="p1",
                trial="t1",
                drift_correction="warp",
            )

    def test_no_correction_requested_is_unaffected(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = api.plot_scanpath(
            normalized_words_df,
            normalized_fixations_df,
            participant="p1",
            trial="t1",
        )
        assert fig is not None

    def test_alignment_sensitivity_raises(
        self, normalized_words_df, normalized_fixations_df
    ):
        with pytest.raises(ValueError, match="experimental and off by default"):
            api.alignment_sensitivity(normalized_words_df, normalized_fixations_df)


class TestTheCliDoesNotOfferTheFlags:
    def test_render_help_does_not_mention_drift_correction(self, capsys):
        from scanpath_studio import cli

        with pytest.raises(SystemExit):
            cli.main(["render", "--help"])
        out = capsys.readouterr().out
        assert "--drift-correction" not in out
        assert "--drift-connectors" not in out

    def test_passing_the_flag_is_an_argparse_error(self, capsys):
        """An unrecognized argument, not a silently-ignored one."""
        from scanpath_studio import cli

        with pytest.raises(SystemExit):
            cli.main(
                ["render", "--sample", "--drift-correction", "warp", "-o", "x.html"]
            )
        assert "drift-correction" in capsys.readouterr().err

    def test_the_parser_still_carries_the_attributes(self):
        """Downstream branches read ``args.drift_correction`` unconditionally."""
        from scanpath_studio import cli

        args = cli._render_parser().parse_args(["--sample", "-o", "x.html"])
        assert isinstance(args, argparse.Namespace)
        assert args.drift_correction is None
        assert args.drift_connectors is False


class TestTheDeepLinkIsIgnoredSilently:
    def test_an_align_algorithm_param_does_not_reach_the_state(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["align_algorithm"] = "warp"
        at.run(timeout=90)
        assert not at.exception, at.exception
        # Silently — no "unavailable in this build" warning.
        state = at.session_state
        assert (
            "global_align_algorithm" not in state
            or state["global_align_algorithm"] == "Off"
        )
        assert not [w for w in at.warning if "align" in str(w.value).lower()]


class TestTheUiSurfacesAreAbsent:
    def test_there_is_no_line_assignment_subtab(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        labels = {t.label for t in at.tabs}
        assert tabs.SUBTAB_LINE_ASSIGNMENT not in labels
        # …and the ones that remain are all still there.
        for kept in (tabs.SUBTAB_COMPARISONS, tabs.SUBTAB_EXPORT, tabs.SUBTAB_SHARE):
            assert kept in labels

    def test_there_is_no_drift_correction_control(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not [s for s in at.selectbox if s.key == "global_align_algorithm"]

    def test_the_comparisons_panel_keeps_the_grid_but_drops_the_scoring(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state[SUBTAB_KEY] = tabs.SUBTAB_COMPARISONS
        at.run(timeout=120)
        assert not at.exception, at.exception
        headings = " ".join(str(m.value) for m in at.markdown)
        assert "Matching trials" in headings, "the comparison grid must stay"
        assert "Similarity to the selected scanpath" not in headings
        assert "Metric convergence" not in headings

    def test_the_grid_drops_the_redundant_ordering_caption(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state[SUBTAB_KEY] = tabs.SUBTAB_COMPARISONS
        at.run(timeout=120)
        captions = " ".join(str(c.value) for c in at.caption)
        assert "sorted by trial" not in captions
        assert "Same participant_id" not in captions
        assert "NLD" not in captions


class TestTheGuidanceMatchesTheBuild:
    def test_the_faq_drops_the_drift_correction_entry(self):
        questions = [q for q, _ in tour.faq_items()]
        assert not any("drift correction" in q.lower() for q in questions)

    def test_it_comes_back_with_the_flag_on(self, monkeypatch):
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        questions = [q for q, _ in tour.faq_items()]
        assert any("drift correction" in q.lower() for q in questions)


class TestTheExportManifestDoesNotAdvertiseIt:
    def test_the_settings_json_omits_the_drift_keys(self):
        from scanpath_studio.export import _plot_config_dict

        config = _plot_config_dict(
            "p1", "t1", 100, 100, "x", "y", {"align_algorithm": "warp"}
        )
        assert "drift_correction" not in config["coloring"]
        assert "drift_connectors" not in config["coloring"]

    def test_they_are_present_with_the_flag_on(self, monkeypatch):
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        from scanpath_studio.export import _plot_config_dict

        config = _plot_config_dict(
            "p1", "t1", 100, 100, "x", "y", {"align_algorithm": "warp"}
        )
        assert config["coloring"]["drift_correction"] == "warp"


def test_the_modules_themselves_are_untouched():
    """A gate, not a deletion: both stay importable and working, which is what
    keeps them reachable for development and keeps the rest of the suite
    honest."""
    from scanpath_studio import alignment, similarity

    assert alignment.ALGORITHMS
    assert similarity.METRICS
    assert similarity.normalized_levenshtein([1, 2, 3], [1, 2, 3]) == 0.0
    assert isinstance(pd.DataFrame(), pd.DataFrame)


class TestPreprocessingGate:
    """Preprocessing is hidden from the app unless the experimental flag is set.

    The code stays in the package. The app must not render the panel, and a
    stored setting must not run the pipeline while it is hidden.
    """

    def test_it_is_hidden_by_default(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        assert constants.preprocessing_enabled() is False

    def test_the_experimental_flag_brings_it_back(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        assert constants.preprocessing_enabled() is True

    def test_the_settings_read_off_while_hidden(self, monkeypatch):
        """A share link or saved config cannot run a pipeline with no control."""
        import streamlit as st

        from scanpath_studio import app, constants

        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        st.session_state["global_preproc_enabled"] = True
        st.session_state["global_preproc_short_policy"] = "Discard"
        settings = app._preprocessing_settings()
        assert settings["enabled"] is False
        assert settings["short_policy"] == "Off"
        # …and the stored answers survive, for when it is shown again.
        assert st.session_state["global_preproc_enabled"] is True

    def test_the_tutorial_drops_its_preprocessing_step(self, monkeypatch):
        from scanpath_studio import constants
        from scanpath_studio.tour import TUTORIALS, steps_of

        tutorial = next(t for t in TUTORIALS if any(s.gate for s in t.steps))
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        with_step = steps_of(tutorial)
        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        without_step = steps_of(tutorial)
        assert len(without_step) == len(with_step) - 1
        assert not any(step.gate == "preprocessing" for step in without_step)

    def test_the_data_page_shows_no_preprocessing_section(self):
        """The app must not offer it."""
        from tests.conftest import pin_data_view

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        # Every ✏️ Edit dataset section is a numbered `.sps-wiz-part` headline,
        # so this looks there rather than for an `st.subheader` — nothing in the
        # app emits one with that text, which would make that assertion pass
        # whether or not the gate regressed.
        parts = " ".join(
            str(m.value)
            for m in at.markdown
            if str(m.value).startswith('<div class="sps-wiz-part"')
        )
        assert "Preprocessing" not in parts, parts
        assert "Preprocessing" not in " ".join(s.value for s in at.subheader)
        # With the experimental flag off (this whole file's default),
        # the 🧮 Derived analysis tables section — Cleaning report included — is
        # withheld too, so there's nothing preprocessing-specific left to
        # single out here. See TestDerivedAnalysisTablesGate for that gate.
        labels = [e.label for e in at.expander]
        assert not any("Derived analysis" in label for label in labels), labels


class TestDerivedAnalysisTablesGate:
    """The Data page's 🧮 Derived analysis tables section (Sentences /
    Saccades / Trial summary / Participant summary / Characters / Cleaning
    report) is behind the experimental flag, like preprocessing: the builders
    stay in the codebase, but the app must neither render the section nor run
    the aggregation pipeline that backs it.
    """

    def test_it_is_hidden_by_default(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        assert constants.derived_analysis_tables_enabled() is False

    def test_the_experimental_flag_brings_it_back(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        assert constants.derived_analysis_tables_enabled() is True

    def test_the_data_page_hides_the_section_and_skips_its_computation(
        self, monkeypatch
    ):
        from tests.conftest import pin_data_view

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        pin_data_view(at)

        def _must_not_run(*_a, **_k):
            raise AssertionError(
                "the derived-tables computation ran while the gate is off"
            )

        with monkeypatch.context() as m:
            m.setattr(tabs, "_c_derived_tables", _must_not_run)
            at.run(timeout=90)
        assert not at.exception, at.exception
        labels = [e.label for e in at.expander]
        assert not any("Derived analysis" in label for label in labels), labels

    def test_the_flag_restores_the_section(self, monkeypatch):
        from scanpath_studio import constants
        from tests.conftest import pin_data_view

        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        labels = [e.label for e in at.expander]
        assert any("Derived analysis" in label for label in labels), labels


class TestPerSentenceGate:
    """Per sentence derives its numbers from the fixations, unlike the rest of
    Corpus Analysis, so it is behind the experimental flag."""

    def test_it_is_hidden_by_default(self):
        assert not constants.sentence_analysis_enabled()
        assert "Per sentence" not in tabs.corpus_subtabs()
        assert tabs.corpus_subtabs() == ("Per text", "Per participant", "Groups")

    def test_the_experimental_flag_brings_it_back(self, monkeypatch):
        monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")
        assert tabs.corpus_subtabs() == tabs.CORPUS_SUBTABS

    def test_the_corpus_view_draws_three_subtabs_and_no_sentence_table(
        self, monkeypatch
    ):
        from streamlit.testing.v1 import AppTest

        calls = []
        monkeypatch.setattr(
            tabs, "_render_per_sentence_tab", lambda *a, **k: calls.append(1)
        )
        at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
        pin_view(at, "Corpus Analysis")
        at.session_state["corpus_subtab"] = "Per sentence"
        at.run()
        assert not at.exception, at.exception
        assert [t.label for t in at.tabs][-3:] == [
            "Per text",
            "Per participant",
            "Groups",
        ]
        assert calls == []


class TestComputedMeasuresGate:
    """The numbers the app works out itself are not yet verified by hand, so
    they sit behind the experimental flag: the API refuses them, the CLI does
    not offer `analyze`, and Corpus Analysis drops the views built on them."""

    @pytest.mark.parametrize(
        "name",
        [
            "compute_word_metrics",
            "trial_summary",
            "reader_summary",
            "preprocess_data",
            "analysis_tables",
        ],
    )
    def test_the_api_refuses_naming_the_env_var(
        self, name, normalized_words_df, normalized_fixations_df
    ):
        with pytest.raises(ValueError, match=constants.EXPERIMENTAL_ENV_VAR):
            getattr(api, name)(normalized_words_df, normalized_fixations_df)

    def test_the_flag_brings_the_api_back(
        self, monkeypatch, normalized_words_df, normalized_fixations_df
    ):
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        measured = api.compute_word_metrics(
            normalized_words_df, normalized_fixations_df
        )
        assert "total_fixation_duration_ms" in measured.columns

    def test_the_cli_refuses_analyze(self):
        from scanpath_studio import cli

        with pytest.raises(SystemExit, match=constants.EXPERIMENTAL_ENV_VAR):
            cli.main(["analyze", "--help"])

    def test_the_cli_help_does_not_list_analyze(self, capsys, monkeypatch):
        from scanpath_studio import cli

        cli.main(["--help"])
        assert "analyze" not in capsys.readouterr().out
        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        cli.main(["--help"])
        assert "analyze" in capsys.readouterr().out

    def test_the_export_bundle_offers_no_measure_family(self):
        import inspect

        from scanpath_studio import export

        source = inspect.getsource(export.render_export_options)
        assert '*(["Computed measures"] if computed_measures_enabled() else [])' in (
            source
        )

    @pytest.mark.parametrize(
        ("subtab", "view_key"),
        [("Per participant", "prdr_view"), ("Groups", "pgrp_view")],
    )
    def test_corpus_analysis_drops_the_computed_views(self, subtab, view_key):
        at = AppTest.from_file(APP_SCRIPT)
        pin_view(at, "Corpus Analysis")
        at.session_state["corpus_subtab"] = subtab
        at.run(timeout=60)
        assert not at.exception, at.exception
        views = set(at.selectbox(key=view_key).options)
        assert views, "no views offered"
        assert not views & tabs._COMPUTED_READER_VIEWS

    def test_a_session_on_a_hidden_view_falls_back(self):
        at = AppTest.from_file(APP_SCRIPT)
        pin_view(at, "Corpus Analysis")
        at.session_state["corpus_subtab"] = "Per participant"
        at.session_state["prdr_view"] = "Reading summary"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.selectbox(key="prdr_view").value == "Distribution vs cohort"

    def test_fixation_duration_over_time_opens_on_a_fixation_measure(self):
        at = AppTest.from_file(APP_SCRIPT)
        pin_view(at, "Corpus Analysis")
        at.session_state["corpus_subtab"] = "Per participant"
        at.session_state["prdr_view"] = "Fixation duration over time"
        at.run(timeout=60)
        assert not at.exception, at.exception
        picker = at.selectbox(key="prdr9_measure")
        assert all(
            "fixation" in o.lower() or "saccade" in o.lower() for o in picker.options
        )
        assert not any("per-fixation measure" in i.value for i in at.info)
