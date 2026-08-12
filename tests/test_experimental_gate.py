"""PRE-21: the default build hides drift correction and NLD similarity.

Both features work and both stay in the codebase — this is a *visibility* gate
ahead of publication, because shipping a half-wired control invites users to
lean on it. The rest of the suite runs with ``SCANPATH_EXPERIMENTAL=1`` (see
``tests/conftest.py``) so their coverage is unchanged; this file is the other
half: what a user of the default build must **not** be offered.

Every gate reads the env var at call time, which is what lets one process assert
both builds.
"""

from __future__ import annotations

import argparse

import pandas as pd
import pytest

from scanpath_studio import api, constants, controls, tabs, tour
from tests.conftest import APP_SCRIPT, SUBTAB_KEY

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
        # which is what makes an old link degrade silently and consistently.
        assert settings["align_algorithm"] == "Off"
        assert settings["align_connectors"] is False
        st.session_state.clear()


class TestTheHeadlessSurfacesRefuseRatherThanIgnore:
    """A share link degrades silently because a human can see the figure. A
    script cannot, so returning uncorrected fixations under a stated
    ``drift_correction=`` would be a wrong result with no signal."""

    def test_plot_scanpath_raises(self, normalized_words_df, normalized_fixations_df):
        with pytest.raises(ValueError, match="not available in this build"):
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
        with pytest.raises(ValueError, match="not available in this build"):
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

        parser = (
            cli._build_render_parser() if hasattr(cli, "_build_render_parser") else None
        )
        if parser is None:
            pytest.skip("render parser is built inline")
        args = parser.parse_args(["--sample", "-o", "x.html"])
        assert isinstance(args, argparse.Namespace)
        assert args.drift_correction is None
        assert args.drift_connectors is False


class TestTheDeepLinkIsIgnoredSilently:
    def test_an_align_algorithm_param_does_not_reach_the_state(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["align_algorithm"] = "warp"
        at.run(timeout=90)
        assert not at.exception, at.exception
        # Silently, per the settled call — no "unavailable in this build" warning.
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
        labels = {t.proto.label for t in at.get("tab")}
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
        assert "Other scanpaths" in headings, "the generations grid must stay"
        assert "Similarity to the selected scanpath" not in headings
        assert "Metric convergence" not in headings

    def test_the_grid_says_how_it_is_ordered(self):
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state[SUBTAB_KEY] = tabs.SUBTAB_COMPARISONS
        at.run(timeout=120)
        captions = " ".join(str(c.value) for c in at.caption)
        assert "alphabetical order" in captions
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
    keeps them reachable for us and keeps the rest of the suite honest."""
    from scanpath_studio import alignment, similarity

    assert alignment.ALGORITHMS
    assert similarity.METRICS
    assert similarity.normalized_levenshtein([1, 2, 3], [1, 2, 3]) == 0.0
    assert isinstance(pd.DataFrame(), pd.DataFrame)
