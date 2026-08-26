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
    keeps them reachable for us and keeps the rest of the suite honest."""
    from scanpath_studio import alignment, similarity

    assert alignment.ALGORITHMS
    assert similarity.METRICS
    assert similarity.normalized_levenshtein([1, 2, 3], [1, 2, 3]) == 0.0
    assert isinstance(pd.DataFrame(), pd.DataFrame)


class TestPreprocessingGate:
    """PRE-22 — preprocessing is held back from the app, not from the package.

    The distinction is the whole item: a released feature (0.28.0 shipped it
    across app, API, CLI and export) is withdrawn from *this release's UI* and
    picked up in the next one. So the app must not render it, and the API and
    CLI must keep working — a hidden button and a broken function call are
    different promises to a user.
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
        # …and the stored answers survive for the release that shows it again.
        assert st.session_state["global_preproc_enabled"] is True

    def test_the_python_api_still_preprocesses(self, monkeypatch):
        """PRE-21's gate raises; this one must not — the API shipped in 0.28.0."""
        import pandas as pd

        from scanpath_studio import api, constants

        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        words = pd.DataFrame(
            {
                "participant_id": ["p1"] * 2,
                "trial_id": ["t1"] * 2,
                "word_id": [0, 1],
                "text": ["the", "cat"],
                "x": [100.0, 200.0],
                "y": [50.0, 50.0],
                "width": [90.0, 90.0],
                "height": [40.0, 40.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1"] * 3,
                "trial_id": ["t1"] * 3,
                "x": [110.0, 118.0, 210.0],
                "y": [70.0, 70.0, 70.0],
                "duration_ms": [200.0, 30.0, 180.0],
                "timestamp_ms": [0.0, 210.0, 260.0],
                "order_in_trial": [1, 2, 3],
            }
        )
        _words, processed, qa = api.preprocess_data(
            words, fixations, enabled=True, short_policy="Discard"
        )
        assert not processed.empty
        assert "excluded" in processed.columns
        assert not qa.empty

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
        """The whole point of the item: the app must not offer it."""
        from tests.conftest import pin_data_view

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert "🧹 Preprocessing" not in [s.value for s in at.subheader]
        # …including the pipeline's own QA table, which is a preprocessing
        # surface rather than one of the plain analysis tables beside it.
        labels = [e.label for e in at.expander]
        derived = next((label for label in labels if "Derived analysis" in label), "")
        assert derived, labels
        assert "Cleaning QA" not in derived
        for kept in ("Sentences", "Saccades", "Trials", "Readers", "Characters"):
            assert kept in derived, f"{kept} is not a preprocessing surface: {derived}"


class TestMultiplEYEUploadGate:
    """UX-114 — the wizard's "Dataset format" choice + the MultiplEYE upload
    branch it dispatches to are held back this release, the same way PRE-22
    holds back the preprocessing panel: the code stays for a later revival
    (most of what it did by hand is now what the generalized Generic wizard
    can do too), but a default build offers no format *question* at all.
    """

    def test_it_is_hidden_by_default(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.delenv(constants.EXPERIMENTAL_ENV_VAR, raising=False)
        assert constants.multipleye_upload_enabled() is False

    def test_the_experimental_flag_brings_it_back(self, monkeypatch):
        from scanpath_studio import constants

        monkeypatch.setenv(constants.EXPERIMENTAL_ENV_VAR, "1")
        assert constants.multipleye_upload_enabled() is True

    def test_the_wizard_offers_no_format_choice(self, monkeypatch):
        from scanpath_studio import app
        from tests.conftest import answer_setup_step

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert [
            s for s in at.segmented_control if s.key == "wizard_dataset_format"
        ] == []
        assert at.session_state["wizard_dataset_format"] == "Generic"
        # The Generic upload row renders directly — no format question in front
        # of it, on either Add or Edit dataset (this same function backs both).
        uploader_keys = {u.key for u in at.file_uploader}
        assert "col_map_fix_upload" in uploader_keys
        assert "col_map_words_upload" in uploader_keys

    def test_a_stale_multipleye_choice_is_forced_back_to_generic(self, monkeypatch):
        """A session that picked MultiplEYE while the flag was on (or a
        restored setup carrying that choice) must not reach the hidden branch
        once the flag is off again."""
        from scanpath_studio import app
        from tests.conftest import answer_setup_step

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        answer_setup_step(at)
        at.session_state["_show_upload_wizard"] = True
        at.session_state["setup_complete"] = False
        at.session_state["wizard_dataset_format"] = "MultiplEYE"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.session_state["wizard_dataset_format"] == "Generic"
        uploader_keys = {u.key for u in at.file_uploader}
        assert "col_map_fix_upload" in uploader_keys

    def test_the_multipleye_upload_functions_are_untouched(self):
        """A gate, not a deletion — the upload-parsing code stays importable
        and working, reachable directly and ready for a later revival."""
        from scanpath_studio import datasets

        assert callable(datasets.multipleye_frames_from_uploads)
        assert callable(datasets.load_multipleye_uploads)
