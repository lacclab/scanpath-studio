"""The first-visit invitation, task guides and optional dataset setup guide."""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _wizard_guide_app():
    import streamlit as st

    from scanpath_studio.tour import _arm_wizard_guide, render_spotlight_wizard_guide

    if not st.session_state.get("started"):
        st.session_state["started"] = True
        _arm_wizard_guide()
    render_spotlight_wizard_guide()


def _welcome_tour_app():
    import streamlit as st

    from scanpath_studio.tour import (
        _arm_tour,
        render_spotlight_tour,
        restore_sample_on_rerun,
    )

    restore_sample_on_rerun()
    if not st.session_state.get("started"):
        st.session_state["started"] = True
        st.session_state["_tutorial_context"] = {
            "n_trials": 1,
            "selected_has_fixations": True,
        }
        _arm_tour()
    render_spotlight_tour()


def _fresh_demo():
    import streamlit as st

    from scanpath_studio.tour import (
        maybe_show_welcome_tour,
        render_spotlight_tour,
        restore_sample_on_rerun,
    )

    restore_sample_on_rerun()
    st.session_state.setdefault(
        "_tutorial_context", {"n_trials": 1, "selected_has_fixations": True}
    )
    maybe_show_welcome_tour()
    render_spotlight_tour()


class TestSampleInvitation:
    def test_inline_offer_is_dismissible(self):
        at = AppTest.from_function(_fresh_demo).run()
        assert not at.exception, at.exception
        assert any(m.value == "A sample reading is open." for m in at.markdown)
        assert not at.progress
        assert {b.label for b in at.button} == {
            "Import my data",
            "Replay this reading",
            "Dismiss",
        }
        at.button(key="sample_invitation_dismiss").click().run()
        assert at.session_state["_tour_dismissed"]
        assert any(
            "sps_tour_optout=1" in iframe.proto.srcdoc for iframe in at.get("iframe")
        )
        at.run()
        assert not at.button

    @pytest.mark.parametrize(
        "params",
        [
            {"source": "demo"},
            {"participant": "p"},
            {"tab": "animation"},
            {"palette": "Set2"},
            {"debug": "1"},
        ],
    )
    def test_a_deep_link_skips_the_invitation(self, params):
        at = AppTest.from_function(_fresh_demo)
        at.query_params.update(params)
        at.run()
        assert not at.exception, at.exception
        assert not at.button

    @pytest.mark.parametrize("already_seen", [True, False])
    def test_a_returning_browser_or_an_embed_is_not_greeted(self, already_seen):
        from unittest.mock import PropertyMock, patch

        import streamlit as st

        from scanpath_studio.tour import TOUR_OPTOUT_COOKIE

        with (
            patch.object(
                type(st.context),
                "cookies",
                new_callable=PropertyMock,
                return_value={TOUR_OPTOUT_COOKIE: "1"} if already_seen else {},
            ),
            patch.object(
                type(st.context),
                "is_embedded",
                new_callable=PropertyMock,
                return_value=not already_seen,
            ),
        ):
            at = AppTest.from_function(_fresh_demo).run()
        assert not at.exception, at.exception
        assert not at.button

    def test_no_offer_in_a_restored_session(self):
        from scanpath_studio.persistence import _RESTORED_PAYLOAD_KEY

        at = AppTest.from_function(_fresh_demo)
        at.session_state[_RESTORED_PAYLOAD_KEY] = {}
        at.run()
        assert not at.button

    def test_a_finished_import_does_not_carry_its_guide_into_the_next_one(self):
        at = AppTest.from_function(_fresh_demo)
        at.session_state["tour_mode"] = "wizard"
        at.session_state["tour_seen"] = True
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["tour_mode"] is None

    @pytest.mark.parametrize("mode", ["essentials", "full"])
    def test_guide_replays_and_returns_to_the_previous_figure_in_either_mode(
        self, mode
    ):
        from scanpath_studio.constants import _VIEW_SCANPATH, GUIDE_RETURN_KEY
        from scanpath_studio.session_keys import SINGLE_ANIMATE, SINGLE_COMPARE_TOGGLE

        at = AppTest.from_function(_fresh_demo)
        at.session_state["ui_mode"] = mode
        at.session_state[SINGLE_ANIMATE] = False
        at.session_state[SINGLE_COMPARE_TOGGLE] = True
        at.session_state["global_anim_autoplay"] = False
        at.run()
        at.button(key="sample_invitation_replay").click().run()
        assert not at.exception, at.exception
        assert at.session_state["ui_mode"] == mode
        assert (
            at.session_state[SINGLE_ANIMATE]
            and not at.session_state[SINGLE_COMPARE_TOGGLE]
        )
        assert at.session_state["global_anim_autoplay"]
        assert at.session_state[GUIDE_RETURN_KEY] == {
            "main_nav": _VIEW_SCANPATH,
            SINGLE_ANIMATE: False,
            SINGLE_COMPARE_TOGGLE: True,
            "global_anim_autoplay": False,
        }
        assert any("milliseconds" in m.value for m in at.markdown)
        at.button(key="tour_sp_next").click().run()
        assert at.progress[0].text == "Step 2 of 2"
        at.button(key="tour_sp_done").click().run()
        assert not at.exception, at.exception
        assert (
            not at.session_state[SINGLE_ANIMATE]
            and at.session_state[SINGLE_COMPARE_TOGGLE]
        )
        assert not at.session_state["global_anim_autoplay"]
        assert GUIDE_RETURN_KEY not in at.session_state
        assert not at.button

    def test_a_guide_cannot_replace_the_open_dataset_or_escape_an_upload(self):
        from unittest.mock import patch

        from scanpath_studio import tour

        for state in (
            {"data_source_choice": "My study"},
            {"_pending_source_choice": "My study"},
            {"_show_upload_wizard": True},
            {"_tutorial_context": {"n_trials": 0}},
        ):
            before = dict(state)
            with patch.object(tour.st, "session_state", state):
                assert not tour.sample_reading_available()
                tour._arm_tour()
            assert state == before


class TestWizardGuideSpotlight:
    def test_closing_and_finishing_each_end_the_guide(self):
        from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

        at = AppTest.from_function(_wizard_guide_app).run()
        assert not at.exception, at.exception
        at.button(key="wizard_sp_exit").click().run()
        assert not at.progress
        at = AppTest.from_function(_wizard_guide_app).run()
        at.session_state["wizard_guide_step"] = len(_WIZARD_GUIDE_STEPS) - 1
        at.run()
        at.button(key="wizard_sp_done").click().run()
        assert not at.progress


def _surface_open_probe_app():
    """Verdicts of ``_tutorial_surface_is_open`` from each of the three views.

    Runs as its own app because the function reads ``st.session_state``, which
    needs a script run context. Order: a Data-page step seen from Data /
    Corpus / Scanpath, then a Scanpath step seen from the Data page.
    """
    import streamlit as st

    from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH
    from scanpath_studio.tour import TUTORIALS, TutorialStep, _tutorial_surface_is_open

    data_step = next(
        s for tutorial in TUTORIALS for s in tutorial.steps if s.view == _VIEW_DATA
    )
    st.session_state["data_workspace"] = data_step.data_section
    verdicts = []
    for view in (_VIEW_DATA, _VIEW_CORPUS, _VIEW_SCANPATH):
        st.session_state["main_nav"] = view
        verdicts.append(_tutorial_surface_is_open(data_step))
    st.session_state["main_nav"] = _VIEW_DATA
    verdicts.append(
        _tutorial_surface_is_open(TutorialStep("t", "b", ".x", view=_VIEW_SCANPATH))
    )
    st.markdown(",".join(str(v) for v in verdicts))


def _use_case_tutorial_app():
    import streamlit as st

    from scanpath_studio.constants import _VIEW_CORPUS, SUBTAB_ANNOTATIONS
    from scanpath_studio.tour import _start_use_case, render_use_case_tutorial

    st.session_state.setdefault(
        "_tutorial_context",
        {
            "n_trials": 3,
        },
    )
    st.session_state.setdefault("main_nav", _VIEW_CORPUS)
    st.session_state.setdefault("single_subtab", SUBTAB_ANNOTATIONS)
    if not st.session_state.get("_tutorial_armed_once"):
        st.session_state["_tutorial_armed_once"] = True
        _start_use_case("filter_annotate")
    render_use_case_tutorial()


def _choose_help_entry(at, entry: str) -> None:
    """Pick a ❓ Help nav entry the way ``menu.render_nav`` does, then rerun.

    An action entry only arms its dialog (``menu._arm_help_action``); the next
    run's early ``maybe_show_*`` call serves it. The arming writes through
    ``st.session_state``, which outside a script run is not this AppTest's
    state — so point it at the right one.
    """
    from unittest.mock import patch

    import streamlit as st

    from scanpath_studio import menu

    with patch.object(st, "session_state", at.session_state):
        menu._arm_help_action(entry)
    at.run()


def _tutorial_library_app():
    """Open the chooser from the same capability snapshot as the app."""
    import streamlit as st

    from scanpath_studio.tour import maybe_show_tutorial_library, stash_tutorial_context

    st.session_state["tour_seen"] = True
    stash_tutorial_context(
        {
            "n_trials": 2,
            "has_fixations": True,
            "selected_has_fixations": True,
            "has_word_measures": True,
        }
    )
    maybe_show_tutorial_library()


class TestUseCaseTutorials:
    def test_registry_is_unique_concise_and_outcome_oriented(self):
        from scanpath_studio.tour import TUTORIALS

        assert len({tutorial.id for tutorial in TUTORIALS}) == len(TUTORIALS)
        for tutorial in TUTORIALS:
            assert tutorial.docs_url.startswith("https://")
            assert tutorial.steps
            assert all(len(step.body) <= 300 for step in tutorial.steps)

    def test_availability_follows_the_frames_each_workspace_uses(self):
        import pandas as pd

        from scanpath_studio.tour import (
            _TUTORIAL_BY_ID,
            build_tutorial_context,
            tutorial_availability,
        )

        combos = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "trial_id": ["t1", "t2"]}
        )
        empty = pd.DataFrame()
        raw_only = build_tutorial_context(empty, empty, combos)
        fix_only = build_tutorial_context(empty, combos, combos)
        words_only = build_tutorial_context(
            combos.assign(first_fixation_ms=[80, 150]), empty, combos
        )
        for context, corpus, compare in (
            (raw_only, False, False),
            (fix_only, False, True),
            (words_only, True, False),
        ):
            assert tutorial_availability(
                _TUTORIAL_BY_ID["publication_figure"], context
            )[0]
            assert (
                tutorial_availability(_TUTORIAL_BY_ID["explore_corpus"], context)[0]
                is corpus
            )
            assert (
                tutorial_availability(_TUTORIAL_BY_ID["compare_readings"], context)[0]
                is compare
            )
        no_trials = build_tutorial_context(empty, empty, empty)
        assert not tutorial_availability(
            _TUTORIAL_BY_ID["publication_figure"], no_trials
        )[0]
        assert tutorial_availability(_TUTORIAL_BY_ID["load_inspect"], no_trials)[0]

    def test_the_filter_is_named_when_it_hides_all_fixation_readings(self):
        import pandas as pd

        from scanpath_studio.tour import (
            _TUTORIAL_BY_ID,
            build_tutorial_context,
            filtered_reason,
        )

        one = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
        empty = one.iloc[:0]
        compare = _TUTORIAL_BY_ID["compare_readings"]
        narrowed = build_tutorial_context(None, empty, one)
        assert filtered_reason(compare, narrowed) is None
        narrowed["unfiltered"] = build_tutorial_context(None, one, one)
        assert "include a reading with fixations" in filtered_reason(compare, narrowed)
        narrowed["unfiltered"] = build_tutorial_context(None, empty, one)
        assert filtered_reason(compare, narrowed) is None

    def test_one_primary_reading_can_follow_the_comparison_with_dataset_b(self):
        from pathlib import Path

        from scanpath_studio.constants import DEMO_CHOICE, SYNTHETIC_CHOICE
        from scanpath_studio.session_keys import (
            COMPARE_SOURCE_STATE_KEY,
            SINGLE_COMPARE_TOGGLE,
        )

        script = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        at = AppTest.from_file(str(script), default_timeout=60)
        at.session_state["data_source_choice"] = SYNTHETIC_CHOICE
        at.session_state[SINGLE_COMPARE_TOGGLE] = True
        at.session_state[COMPARE_SOURCE_STATE_KEY] = DEMO_CHOICE
        at.session_state["_tutorial_library_requested"] = True
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["_tutorial_context"]["n_trials"] == 1
        assert at.session_state["_share_selection"]["compare"]["source"] == DEMO_CHOICE
        at.button(key="tutorial_start_compare_readings").click().run()
        at.button(key="tutorial_next").click().run()
        assert not at.exception, at.exception
        assert any(
            "another dataset under **Dataset B**" in item.value for item in at.markdown
        )
        assert at.session_state["_share_selection"]["compare"]["source"] == DEMO_CHOICE

    def test_navigation_opens_panels_and_exit_restores_the_start_location(self):
        """Starting a tutorial navigates to its first step's view right
        away, instead of leaving the card on the page you were already on and
        offering a "Show me / Open this panel" button to get there."""
        from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH

        at = AppTest.from_function(_use_case_tutorial_app).run()
        assert not at.exception, at.exception
        # "filter_annotate"'s first step is on Scanpath — the app started on
        # Corpus Analysis (the fixture's seed), so starting it should have
        # moved it already, with no click needed and no "Show me" button offered.
        assert at.session_state["main_nav"] == _VIEW_SCANPATH
        assert not [b for b in at.button if b.key == "tutorial_open_surface"]
        assert at.button(key="tutorial_next")

        at.button(key="tutorial_exit").click().run()
        assert at.session_state["tutorial_active"] is None
        assert at.session_state["main_nav"] == _VIEW_CORPUS

    def test_progress_and_completion_are_per_tutorial(self):
        from scanpath_studio.tour import TUTORIALS

        at = AppTest.from_function(_use_case_tutorial_app).run()
        last = len(next(t for t in TUTORIALS if t.id == "filter_annotate").steps) - 1
        at.session_state["tutorial_progress"] = {"filter_annotate": last}
        at.run()
        at.button(key="tutorial_done").click().run()
        assert at.session_state["tutorial_completed"]["filter_annotate"] is True
        assert "load_inspect" not in at.session_state["tutorial_completed"]

    def test_the_card_links_to_its_own_docs_page(self):
        from scanpath_studio.tour import TUTORIALS

        tutorial = next(t for t in TUTORIALS if t.id == "filter_annotate")
        at = AppTest.from_function(_use_case_tutorial_app).run()
        assert not at.exception, at.exception
        assert any(tutorial.docs_url in item.value for item in at.markdown)

    def test_a_data_page_step_counts_as_open_on_the_data_page(self):
        """The surface check knows all three top-level views.

        Treating anything that is not Corpus Analysis as Scanpath would make a
        ``view=_VIEW_DATA`` step report "not open" *while the user stands on
        the Data page* — the card would offer to open the panel already on
        screen, and withhold the spotlight that belongs on it.
        """
        at = AppTest.from_function(_surface_open_probe_app).run()
        assert not at.exception, at.exception
        assert at.markdown[0].value == "True,False,False,False"

    def test_six_readable_topics_are_offered_in_the_chooser(self):
        at = AppTest.from_function(_tutorial_library_app).run()
        assert not at.exception, at.exception
        # Picking Help → Task guides in the nav
        # arms the dialog the next run serves.
        _choose_help_entry(at, "help_tutorials")
        assert not at.exception, at.exception
        keys = {button.key for button in at.button if button.key}
        assert "tutorial_start_load_inspect" in keys
        assert "tutorial_start_explore_corpus" in keys
        assert [topic.label for topic in at.expander] == [
            "Replay a sample reading",
            "Import and check a recording",
            "Filter and mark trials",
            "Compare readings",
            "Analyze a corpus",
            "Export or reproduce a figure",
        ]
        assert at.button(key="tutorial_start_filter_annotate").label == "Open in Full"
        assert (
            at.button(key="tutorial_start_explore_corpus").label == "Show me in the app"
        )

    def test_cold_start_uses_this_dataset_and_returns_to_the_original_corpus_view(self):
        from pathlib import Path

        from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH

        script = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        at = AppTest.from_file(str(script), default_timeout=60)
        at.query_params["ui"] = "essentials"
        at.query_params["embed"] = "true"
        at.session_state["_tutorial_library_requested"] = True
        at.session_state["main_nav"] = _VIEW_CORPUS
        at.session_state["corpus_subtab"] = "Groups"
        at.run()
        assert not at.exception
        assert at.query_params["corpus_subtab"] == "Groups"
        assert at.button(key="tutorial_start_explore_corpus")
        at.button(key="tutorial_start_filter_annotate").click().run()
        assert not at.exception
        assert at.session_state["main_nav"] == _VIEW_SCANPATH
        assert at.session_state["ui_mode"] == "full"
        assert "corpus_subtab" not in at.query_params
        assert at.query_params["embed"] == "true"
        at.button(key="tutorial_next").click().run()
        at.button(key="tutorial_exit").click().run()
        assert not at.exception
        assert at.session_state["main_nav"] == _VIEW_CORPUS
        assert at.session_state["corpus_subtab"] == "Groups"
        assert at.session_state["ui_mode"] == "essentials"
        assert at.query_params["corpus_subtab"] == "Groups"
        assert at.query_params["embed"] == "true"

    def test_import_visits_the_library_editor_and_overview_then_returns_to_saved_work(
        self, experimental_off
    ):
        from scanpath_studio.constants import (
            DATA_CURRENT,
            DATA_INSPECTION_KEY,
            DATA_LIBRARY,
            DATA_STORAGE,
            DATA_WORKSPACE_KEY,
            DATASET_EDITOR_OPEN_KEY,
        )
        from tests.conftest import APP_SCRIPT, pin_data_view

        at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
        at.query_params["ui"] = "essentials"
        pin_data_view(at, section=DATA_STORAGE)
        at.session_state["_tutorial_library_requested"] = True
        at.run()
        assert at.session_state[DATA_WORKSPACE_KEY] == DATA_STORAGE
        at.button(key="tutorial_start_load_inspect").click().run()
        assert at.session_state[DATA_WORKSPACE_KEY] == DATA_LIBRARY
        at.button(key="tutorial_next").click().run()
        assert at.session_state[DATA_WORKSPACE_KEY] == DATA_CURRENT
        assert at.session_state[DATASET_EDITOR_OPEN_KEY]
        at.button(key="tutorial_back").click().run()
        assert at.session_state[DATA_WORKSPACE_KEY] == DATA_LIBRARY
        assert at.button(key="add_data_btn")
        at.button(key="tutorial_next").click().run()
        at.button(key="tutorial_next").click().run()
        assert at.session_state[DATA_INSPECTION_KEY] == "Overview"
        assert DATASET_EDITOR_OPEN_KEY not in at.session_state
        at.button(key="tutorial_done").click().run()
        assert not at.exception, at.exception
        assert at.session_state[DATA_WORKSPACE_KEY] == DATA_STORAGE
        assert at.session_state["ui_mode"] == "essentials"

    @pytest.mark.parametrize(
        ("section", "panel", "editing", "guide"),
        [
            ("Dataset library", "Overview", False, "filter_annotate"),
            ("Current dataset", "Tables", False, "welcome"),
            ("Current dataset", "Data checks", False, "load_inspect"),
            ("Current dataset", "Tables", True, "filter_annotate"),
        ],
    )
    def test_exit_restores_the_data_workspace_panel_and_editor(
        self, section, panel, editing, guide
    ):
        from scanpath_studio.constants import (
            _VIEW_DATA,
            DATA_INSPECTION_KEY,
            DATA_WORKSPACE_KEY,
            DATASET_EDITOR_OPEN_KEY,
        )
        from scanpath_studio.tabs import EDITOR_NAME_FIELD_KEY
        from tests.conftest import APP_SCRIPT, pin_data_view

        at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
        at.query_params["ui"] = "essentials"
        pin_data_view(at, section=section)
        at.session_state[DATA_INSPECTION_KEY] = panel
        at.session_state[DATASET_EDITOR_OPEN_KEY] = editing
        if editing:
            at.session_state[EDITOR_NAME_FIELD_KEY] = "Unfinished edit"
        at.session_state["_tutorial_library_requested"] = True
        at.run()
        assert not at.exception, at.exception
        if editing:
            assert not any(b.key == "tutorial_start_load_inspect" for b in at.button)
            assert any(
                "save or cancel your open edit" in item.value for item in at.caption
            )
        at.button(key=f"tutorial_start_{guide}").click().run()
        at.button(
            key="tour_sp_close" if guide == "welcome" else "tutorial_exit"
        ).click().run()
        assert not at.exception, at.exception
        assert at.session_state["main_nav"] == _VIEW_DATA
        assert at.session_state[DATA_WORKSPACE_KEY] == section
        assert at.session_state[DATA_INSPECTION_KEY] == panel
        assert at.session_state[DATASET_EDITOR_OPEN_KEY] is editing
        if editing:
            assert at.text_input(key=EDITOR_NAME_FIELD_KEY).value == "Unfinished edit"
        assert at.session_state["ui_mode"] == "essentials"

    def test_paused_guide_can_exit_and_restore_mode(self):
        from scanpath_studio.constants import _VIEW_CORPUS

        at = AppTest.from_function(_use_case_tutorial_app).run()
        at.session_state["_tutorial_context"] = {"n_trials": 0}
        at.run()
        assert "is paused" in at.info[0].value
        at.button(key="tutorial_exit").click().run()
        assert at.session_state["main_nav"] == _VIEW_CORPUS
        assert at.session_state["ui_mode"] == "essentials"

    def test_starting_again_after_done_returns_to_first_step(self):
        from unittest.mock import patch

        from scanpath_studio import tour

        state = {
            "_tutorial_context": {"n_trials": 2},
            "tutorial_progress": {"publication_figure": 2},
            "tutorial_completed": {"publication_figure": True},
            "ui_mode": "essentials",
        }
        with patch.object(tour.st, "session_state", state):
            tour._start_use_case("publication_figure")
        assert state["tutorial_progress"]["publication_figure"] == 0
        assert not state["tutorial_completed"]
        assert state["ui_mode"] == "essentials"


def _keys_built_inside_a_popover() -> set[str]:
    """Container keys created off a ``st.popover(...)`` handle.

    A closed popover renders no body, so these keys are absent from the DOM
    until their trigger is clicked. Found by reading the source rather
    than listed by hand: the point is to notice the *next* control that moves
    into a popover.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "scanpath_studio"
    keys: set[str] = set()
    for module in ("tabs", "app", "controls", "annotations", "menu"):
        tree = ast.parse((root / f"{module}.py").read_text(encoding="utf-8"))
        for scope in ast.walk(tree):
            handles = {
                node.targets[0].id
                for node in ast.walk(scope)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "popover"
            }
            if not handles:
                continue
            for node in ast.walk(scope):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "container"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in handles
                ):
                    keys |= {
                        kw.value.value
                        for kw in node.keywords
                        if kw.arg == "key" and isinstance(kw.value, ast.Constant)
                    }
    return keys


class TestSpotlightSelectorsResolve:
    """Every spotlight step must point at a container that actually exists.

    ``AGENTS.md`` says to keep ``_SPOTLIGHT_STEPS`` in sync with the
    ``tour_grp_*`` wrappers, and this enforces it: a renamed or removed
    container leaves the step silently un-highlighted — the card still advances,
    it just points at nothing, which no other test would notice.
    """

    def _keyed_containers(self) -> set[str]:
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "scanpath_studio"
        source = "".join(
            (root / f"{module}.py").read_text(encoding="utf-8")
            for module in ("tabs", "app", "controls", "annotations", "menu")
        )
        return set(re.findall(r'key="([\w]+)"', source))

    def _unresolved(self, selectors) -> list[str]:
        keys = self._keyed_containers()
        return [
            selector
            for selector in selectors
            if selector and selector.removeprefix(".st-key-") not in keys
        ]

    def test_every_selector_has_a_container(self):
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        missing = self._unresolved(step.get("selector") for step in _SPOTLIGHT_STEPS)
        assert not missing, (
            "these tour steps point at containers that no longer exist — the step "
            f"will highlight nothing: {missing}"
        )

    def test_every_use_case_selector_has_a_container(self):
        from scanpath_studio.tour import TUTORIALS

        missing = self._unresolved(
            step.selector for tutorial in TUTORIALS for step in tutorial.steps
        )
        assert not missing, (
            "these use-case tutorial steps point at containers that no longer "
            f"exist: {missing}"
        )

    def test_every_step_names_a_real_subtab(self):
        """A step's ``subtab`` is the tab's real label ("📤 Export", not
        "Export"), or no tab opens, the card claims it has, and the spotlight
        aims at a panel that never renders. The selector test above cannot see
        this — the container exists, just never on screen."""
        from scanpath_studio import tabs
        from scanpath_studio.tour import TUTORIALS

        scanpath = {
            tabs.SUBTAB_ANNOTATIONS,
            tabs.SUBTAB_STIMULUS,
            tabs.SUBTAB_COMPARISONS,
            tabs.SUBTAB_LINE_ASSIGNMENT,
            tabs.SUBTAB_EXPORT,
            tabs.SUBTAB_SHARE,
        }
        steps = [step for tutorial in TUTORIALS for step in tutorial.steps]
        assert {s.subtab for s in steps if s.subtab} <= scanpath
        assert {s.corpus_subtab for s in steps if s.corpus_subtab} <= set(
            tabs.CORPUS_SUBTABS
        )

    def test_the_first_import_step_highlights_the_control_that_imports_files(self):
        from scanpath_studio.constants import DATA_LIBRARY
        from scanpath_studio.tour import _TUTORIAL_BY_ID
        from tests.conftest import APP_SCRIPT, pin_data_view

        at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
        pin_data_view(at, section=DATA_LIBRARY)
        at.run()
        assert not at.exception, at.exception
        step = _TUTORIAL_BY_ID["load_inspect"].steps[0]
        label = (
            at.container(key=step.selector.removeprefix(".st-key-"))
            .button(key="add_data_btn")
            .label
        )
        assert label == "Import files"

    def test_no_two_steps_spotlight_the_same_area(self):
        """Two steps sharing a selector would light up both areas at once.

        Were the "narrow the pool" and "pick a trial" steps both to target a
        wrapper around *both* rows, each would highlight the other's subject.
        """
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        selectors = [s["selector"] for s in _SPOTLIGHT_STEPS if s.get("selector")]
        duplicates = {s for s in selectors if selectors.count(s) > 1}
        assert not duplicates, f"steps share a spotlight target: {duplicates}"

    def test_a_target_inside_a_popover_says_so(self):
        """A closed Streamlit popover renders **no body**.

        The trial filters sit in one funnel popover, so ``tour_grp_narrow_by``
        only exists while the funnel is open. A step aimed at it without
        opening it makes the spotlight's find-and-scroll retry for 30 s and then
        return silently: no highlight, no error, and the card still advances.

        So every step whose target is built off a popover handle has to declare
        the trigger that opens it. The containment is read out of the source,
        not listed here, so the next control that moves into a popover fails
        this instead of going quiet in the browser.
        """
        from scanpath_studio.tour import _SPOTLIGHT_STEPS, TUTORIALS

        inside = _keys_built_inside_a_popover()
        assert "tour_grp_narrow_by" in inside, (
            "the scan found no popover-contained container at all — it has "
            "stopped seeing what it is meant to police"
        )
        undeclared = [
            step["title"]
            for step in _SPOTLIGHT_STEPS
            if (step.get("selector") or "").removeprefix(".st-key-") in inside
            and not step.get("popover")
        ] + [
            step.title
            for tutorial in TUTORIALS
            for step in tutorial.steps
            if step.selector.removeprefix(".st-key-") in inside and not step.popover
        ]
        assert not undeclared, (
            "these steps point inside a popover but don't say which one to "
            f"open, so they will spotlight nothing: {undeclared}"
        )

    def test_the_funnel_steps_open_the_funnel(self):
        """Both narrow-the-pool steps name the funnel trigger — in both of the
        layouts the picker row has (a pool of one drops the slider and puts the
        funnel in its own trailing column)."""
        from scanpath_studio.tour import _SPOTLIGHT_STEPS, FUNNEL_TRIGGER, TUTORIALS

        assert ".st-key-railbtn_single_filter " in FUNNEL_TRIGGER
        assert ".st-key-railbtn_single_filter_solo " in FUNNEL_TRIGGER
        declared = [
            step.get("popover")
            for step in _SPOTLIGHT_STEPS
            if step["selector"] == ".st-key-tour_grp_narrow_by"
        ] + [
            step.popover
            for tutorial in TUTORIALS
            for step in tutorial.steps
            if step.selector == ".st-key-tour_grp_narrow_by"
        ]
        assert declared == [FUNNEL_TRIGGER]

    def test_the_open_script_only_clicks_a_closed_trigger(self):
        """Opening is idempotent: a funnel the user already opened is left as
        it is, because a second click would close it."""
        from scanpath_studio.tour import FUNNEL_TRIGGER, _popover_script

        script = _popover_script(FUNNEL_TRIGGER)
        assert "aria-expanded" in script
        assert FUNNEL_TRIGGER in script
        # …and only a trigger that is really on screen: Streamlit keeps a 0x0
        # twin of the picker row, so clicking the first match would toggle a
        # popover nobody can see (observed live at 1440x900).
        assert "getBoundingClientRect" in script
        assert "find(visible)" in script

    def test_the_card_rises_above_the_panel_it_opened(self):
        """Streamlit draws a popover's panel above the card, so an opened funnel
        covers the card's left edge and cuts the first word off every line
        (measured live at 1440x900). The card outranks it on those steps only."""
        from scanpath_studio.tour import _CARD_OVER_POPOVER_CSS

        assert "z-index: 1000070" in _CARD_OVER_POPOVER_CSS
        import inspect

        from scanpath_studio.tour import render_use_case_tutorial

        assert "_CARD_OVER_POPOVER_CSS" in inspect.getsource(render_use_case_tutorial)

    def test_a_step_without_a_popover_closes_the_one_before_it(self):
        """The panel the previous step opened must not sit over this step's
        target, so every step's script knows every trigger the tour opens."""
        from scanpath_studio.tour import FUNNEL_TRIGGER, _popover_script

        script = _popover_script("")
        assert FUNNEL_TRIGGER in script

    def test_data_source_sits_outside_the_filter_spotlight(self):
        """Adjacent targets must not be nested inside one highlight."""
        import inspect

        from scanpath_studio.tabs import render_single_trial_tab

        source = inspect.getsource(render_single_trial_tab)
        # The source picker is the picker row's lead cell and the filters sit
        # inside a 🔎 popover. The two spotlight targets are *siblings*, never
        # one inside the other. `tour_grp_data_source` is made
        # by `app.render_data_source_picker` (a second one here would be a
        # duplicate key), so what this pins is that the dataset cell gets the
        # renderer straight and the filter group is built somewhere else.
        assert "def _render_dataset_cell(host)" in source
        assert "data_source_renderer(host)" in source
        assert 'box = pop.container(key="tour_grp_narrow_by")' in source
        assert "leading_renderer=_render_dataset_cell" in source

    def test_filter_group_has_a_dataset_divider(self):
        """The sibling groups retain a visible boundary between them."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert ".st-key-tour_grp_narrow_by {" in css
        assert "border-left: 1px solid var(--sps-border);" in css
        assert "padding-left: 0.7rem;" in css

    def test_the_app_forces_ltr_regardless_of_browser_locale(self):
        """A browser whose OS/UI language is RTL (Hebrew, Arabic, ...) inherits
        `direction: rtl`, which BaseWeb's select-slider styles with a logical
        inset that flips under it — the thumb (positioned with a physical
        `left: X%`) lands correctly, but the filled track segment leading up to
        it does not, so the two visibly disagree."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert 'html, body, [data-testid="stApp"] {' in css
        assert "direction: ltr !important;" in css

    def test_page_top_inset_clears_the_fixed_header(self):
        """The first Scanpath row must sit fully below Streamlit's fixed chrome.

        Asserted per declaration rather than on one packed line: the same rule
        sets the side gutters, so the block is multi-line. The
        bottom gap is the theme's own `paddingBottom` (Streamlit 1.66).
        """
        from scanpath_studio.constants import APP_THEME
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert "padding-top: 3rem;" in css
        assert APP_THEME["paddingBottom"] == "0"

    def test_plot_control_rows_are_tall_and_have_one_outline(self):
        """The popover key shares the row prefix; never style both as rows."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        row = '[data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]'
        assert f"{row} {{" in css
        assert "min-height: 2.7rem;" in css
        assert "flex: 0 0 2.6rem;" in css
        assert "width: 100% !important;" in css
        assert '\n    [class*="st-key-split_mode_"] {' not in css
        assert ".st-key-reset_viz_settings_btn button" in css

    def test_mapping_confirm_css_does_not_hide_dialog_buttons(self):
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert '[class*="_cell_confirm"] button {' in css
        assert '[class*="_confirm"] button {' not in css

    def test_subtabs_stay_in_the_plot_column(self):
        """A tall rail cannot push the panels away from a short plot."""
        import inspect

        from scanpath_studio.tabs import render_single_trial_tab

        source = inspect.getsource(render_single_trial_tab)
        assert 'plot_col, rail_col = st.columns([4, 1], gap="large")' in source
        assert 'subtabs_col, _ = st.columns([4, 1], gap="large")' not in source
        assert '        subtabs_slot = st.container(key="tour_grp_subtabs")' in source
        assert "with subtabs_slot:" in source

    def test_visualization_rail_uses_page_flow(self):
        """Controls are neither capped at plot height nor faded out."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert ".st-key-scanpath_rail {" in css
        rail_rule = css.split(".st-key-scanpath_rail {", 1)[1].split("}", 1)[0]
        assert "height:" not in rail_rule
        assert "overflow" not in rail_rule
        assert "mask-image" not in rail_rule
        assert '[data-testid="stColumn"]:has(.st-key-scanpath_rail)' not in css

    def test_plot_rail_uses_one_compact_control_header(self):
        """Modes and visualization settings share one rail heading."""
        import inspect

        from scanpath_studio import controls
        from scanpath_studio.tabs import render_single_trial_tab

        tab_source = inspect.getsource(render_single_trial_tab)
        control_source = inspect.getsource(controls.render_plot_controls)

        assert (
            "st.markdown(f\"## {ICONS['plot_controls']} Plot controls\")" in tab_source
        )
        assert 'st.markdown("## 🎛️ View modes")' not in tab_source
        assert 'st.markdown("## 🎨 Visualization")' not in tab_source
        assert "_render_view_controls(" in control_source
        assert (
            '_render_saved_designs(advanced_only(viz, "rail_designs"))'
            in control_source
        )

    def test_corpus_canvas_controls_stay_inside_the_style_expander(self):
        """The collapsed Corpus style row must own every canvas/font field."""
        import inspect

        from scanpath_studio import controls

        source = inspect.getsource(controls.corpus_style_controls)
        assert "as style_panel" in source
        assert "canvas_renderer(style_panel)" in source
        assert "canvas_renderer(target)" not in source

    def test_reset_closes_the_rail_below_every_control_it_resets(self):
        """Reset is the last thing in the rail, at full width.

        The rail is only ~150px wide inside at ordinary desktop widths, not
        enough for the heading and a compact Reset pill side by side. A
        container query that stacks the two by flipping ``flex-direction``
        without clearing Streamlit's ``flex-wrap: wrap`` turns the header into a
        *column-wrapping* flex container whose second track lands ~100px right
        of the rail, where its own ``overflow`` clips it — Reset is then
        invisible unless the browser is zoomed far out.

        Two things keep that from happening: the heading row holds a single
        element, and the reset renders after ``render_plot_controls`` (creation
        order is what puts it at the foot of the rail's scroll area).
        """
        import inspect

        from scanpath_studio import controls
        from scanpath_studio.styles import get_app_css
        from scanpath_studio.tabs import render_single_trial_tab

        tab_source = inspect.getsource(render_single_trial_tab)
        assert (
            "st.markdown(f\"## {ICONS['plot_controls']} Plot controls\")" in tab_source
        )
        assert 'st.container(key="plot_reset_footer")' in tab_source
        assert "render_viz_reset(plot_footer)" in tab_source
        # No second column in the heading row, and no reset above the controls.
        assert "rail_heading, rail_reset = st.columns(" not in tab_source
        assert tab_source.index("render_plot_controls(") < tab_source.index(
            "render_viz_reset(plot_footer)"
        )

        # Full width, one label, no compact pill.
        reset_source = inspect.getsource(controls.render_viz_reset)
        assert 'width="stretch"' in reset_source
        assert "compact" not in reset_source.split('"""')[0]

        # No rail container query may re-stack a row: the preset tiers query
        # the same container (one at 240px) but only resize their buttons;
        # none of them may change a row's direction.
        css = get_app_css()
        for block in css.split("@container sps-rail")[1:]:
            body = block[: block.find("\n    }")]
            assert "flex-direction" not in body, block[:120]
        assert ".st-key-railbtn_plot_reset" not in css


def test_spotlight_helpers_are_plain_functions_that_return_their_css():
    """The spotlight helpers must not steal `render_spotlight_tour`'s
    `@st.fragment`.

    Inserting `_highlight_css` / `_scroll_into_view_script` directly above the
    decorated function leaves the decorator attached to the *helper* — which
    makes it return `None` (a fragment has no return value), silently dropping
    the highlight outline from both the sample replay and the setup guide, and
    costs the tour its fragment so every Back/Next waits on a full app rerun.
    """
    import inspect

    from scanpath_studio import tour

    for helper in (tour._highlight_css, tour._scroll_into_view_script):
        assert not inspect.getsource(helper).lstrip().startswith("@"), (
            f"{helper.__name__} must stay an undecorated pure helper"
        )

    css = tour._highlight_css(".st-key-wiz_part_setup", "#1f77b4")
    assert "tour-pulse" in css and "outline: 3px solid #1f77b4" in css
    assert tour._highlight_css("", "#1f77b4") == ""

    # Both spotlight renderers must still be fragments (see the module docstring:
    # navigation must never wait for the ~10 s full-app rerun).
    for fn in (tour.render_spotlight_tour, tour.render_spotlight_wizard_guide):
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} lost its @st.fragment"


def test_wizard_guide_steps_are_anchored_to_real_wizard_steps():
    """The guide drives the wizard instead of narrating beside it."""
    from scanpath_studio import wizard_shell
    from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

    known = {s.id for s in wizard_shell.STEPS}
    anchored = [s for s in _WIZARD_GUIDE_STEPS if s["step_id"]]
    assert len(anchored) == len(wizard_shell.STEPS), (
        "every wizard step should have a guide step pointing at it"
    )
    for step in anchored:
        assert step["step_id"] in known
        # The parts are linear labels, not keyed expanders, so the
        # selector comes from their own container key.
        assert step["selector"] == f".st-key-{wizard_shell.part_key(step['step_id'])}"


def test_the_setup_guide_counts_the_parts_it_names(monkeypatch):
    """Each part card is headed "1 ·", "2 ·", "3 ·" — so the guide counts
    parts, not cards ("Step 3 of 4" under "2 · Data tables & column mapping" would
    contradict both). The fourth, Stimulus images, is a card only where the
    add screen draws that part, and the overview names no count, which
    would be wrong on one install or the other."""
    from scanpath_studio import tour

    for local, expected in (("1", 4), ("0", 3)):
        monkeypatch.setenv("SCANPATH_LOCAL_FS", local)
        intro, *parts, save = tour._wizard_guide_steps()
        assert "parts" not in intro["body"]
        assert len(parts) == expected
        for number, part in enumerate(parts, start=1):
            assert part["title"].startswith(f"{number} · ")
            assert part["step_id"]
        assert tour._wizard_guide_progress(0, intro) == f"Overview · {expected} parts"
    # The closing card is not a fourth part: no number, no wizard part to open.
    assert save["step_id"] is None
    assert not save["title"][0].isdigit()
    import inspect

    source = inspect.getsource(tour._wizard_guide_progress)
    assert 'f"Part {step_idx} of {n_parts}"' in source


def test_the_setup_guide_ends_on_saving():
    """The guide's last card points at the footer that saves the dataset —
    ✅ Add dataset and ⬇️ Download setup file — not at Recording setup."""
    from scanpath_studio import tour, wizard

    save = tour._WIZARD_GUIDE_STEPS[-1]
    assert save["selector"] == ".st-key-wizard_footer_row"
    assert "Add dataset" in save["body"] and "Download setup file" in save["body"]
    import inspect

    # The selector names the footer's own container key.
    assert 'container(key="wizard_footer_row")' in inspect.getsource(
        wizard._wizard_footer
    )


def test_the_setup_guide_progress_names_the_save_step():
    at = AppTest.from_function(_wizard_guide_app)
    at.run()
    from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

    at.session_state["wizard_guide_step"] = len(_WIZARD_GUIDE_STEPS) - 1
    at.run()
    (bar,) = at.progress
    assert "Last step" in bar.text
    assert "Part 4" not in bar.text


class TestEveryGuideCardFolds:
    """The sample replay, a task walkthrough and the setup guide each fold
    (—) to a tab naming where they are, open again where they were, and are
    dragged by their title (`tour._GUIDE_DRAG_SCRIPT`)."""

    @staticmethod
    def _keys(at) -> set[str]:
        return {b.key for b in at.button if b.key}

    def _folds_and_opens(self, at, kind: str, next_key: str, tab: str) -> None:
        assert not at.exception, at.exception
        at.button(key=f"guide_fold_{kind}").click().run()
        assert not at.exception, at.exception
        assert self._keys(at) == {f"guide_unfold_{kind}", f"guide_close_{kind}"}
        assert any(tab in m.value for m in at.markdown)
        assert not at.progress
        at.button(key=f"guide_unfold_{kind}").click().run()
        assert next_key in self._keys(at)

    def test_the_setup_guide(self):
        at = AppTest.from_function(_wizard_guide_app).run()
        self._folds_and_opens(at, "wizard", "wizard_sp_next", "Setup guide")

    def test_the_welcome_tour(self):
        at = AppTest.from_function(_welcome_tour_app).run()
        self._folds_and_opens(at, "tour", "tour_sp_next", "Replay a sample reading")

    def test_closing_a_folded_sample_guide_returns_to_the_previous_plot(self):
        at = AppTest.from_function(_welcome_tour_app).run()
        at.button(key="guide_fold_tour").click().run()
        at.button(key="guide_close_tour").click().run()
        assert not at.exception, at.exception
        assert not at.session_state["single_animate"]
        assert not self._keys(at)

    def test_a_tutorial(self):
        at = AppTest.from_function(_use_case_tutorial_app).run()
        self._folds_and_opens(at, "tutorial", "tutorial_next", "Step 1 of")

    def test_arming_a_guide_unfolds_it(self):
        at = AppTest.from_function(_wizard_guide_app).run()
        at.button(key="guide_fold_wizard").click().run()
        from unittest.mock import patch

        from scanpath_studio import tour

        with patch.object(tour.st, "session_state", at.session_state):
            tour._arm_wizard_guide()
        at.run()
        assert "wizard_sp_next" in self._keys(at)

    def test_each_kind_remembers_its_own_spot(self):
        from scanpath_studio.tour import _guide_drag_script

        for kind in ("tour", "tutorial", "wizard"):
            script = _guide_drag_script(kind)
            assert f'"sps_guide_pos_{kind}"' in script
            assert f".st-key-guide_pill_{kind}" in script
            assert "__KIND__" not in script


class TestTutorialsFromSimple:
    """The task tutorials spotlight Full-only controls, so starting one in
    Essentials moves the session to Full (the session only, never the cookie).
    Every start (Start, Resume, Start over) goes through ``_start_use_case``."""

    def test_starting_a_tutorial_in_simple_switches_this_session_to_advanced(self):
        at = AppTest.from_function(_use_case_tutorial_app)
        at.session_state["ui_mode"] = "essentials"
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["tutorial_active"] == "filter_annotate"
        assert at.session_state["ui_mode"] == "full"
        # Not the viewer's own choice: nothing for the cookie to remember.
        assert "_ui_mode_chosen" not in at.session_state
        assert "_ui_mode_cookie" not in at.session_state

    def test_starting_a_tutorial_in_advanced_changes_nothing(self):
        at = AppTest.from_function(_use_case_tutorial_app)
        at.session_state["ui_mode"] = "full"
        at.run()
        assert at.session_state["tutorial_active"] == "filter_annotate"
        assert at.session_state["ui_mode"] == "full"
        assert "_ui_mode_chosen" not in at.session_state

    def test_a_blocked_tutorial_leaves_the_mode_alone(self):
        """A tutorial that cannot start (nothing to compare) changes nothing."""
        from unittest.mock import patch

        from scanpath_studio import tour

        state = {"ui_mode": "essentials", "_tutorial_context": {"n_trials": 0}}
        with patch.object(tour.st, "session_state", state):
            tour._start_use_case("compare_readings")
        assert state["ui_mode"] == "essentials"
        assert "tutorial_active" not in state

    def test_the_return_point_is_taken_before_the_switch(self):
        """Exit returns to the subtab the viewer was on: Essentials' first one."""
        from unittest.mock import patch

        from scanpath_studio import tour
        from scanpath_studio.constants import GUIDE_RETURN_KEY, SUBTAB_EXPORT

        state = {
            "ui_mode": "essentials",
            "_tutorial_context": {
                "n_trials": 2,
            },
        }
        with patch.object(tour.st, "session_state", state):
            tour._start_use_case("filter_annotate")
        assert state[GUIDE_RETURN_KEY]["single_subtab"] == SUBTAB_EXPORT
        assert state["ui_mode"] == "full"

    def test_switching_to_simple_ends_the_running_tutorial(self):
        """Back in Essentials the tutorial would point at hidden controls: choosing
        Essentials leaves it as its Exit does, and the cookie follows the click."""
        at = AppTest.from_function(_tutorial_with_switch_app)
        at.session_state["ui_mode"] = "essentials"
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["tutorial_active"] == "filter_annotate"
        assert at.session_state["ui_mode"] == "full"
        at.segmented_control(key="ui_mode_switch").set_value("essentials").run()
        assert not at.exception, at.exception
        assert not at.session_state["tutorial_active"]
        assert at.session_state["ui_mode"] == "essentials"
        assert at.session_state["_ui_mode_cookie"] == "essentials"
        assert not [b for b in at.button if b.key == "tutorial_exit"]

    def test_a_deselect_in_advanced_keeps_the_tutorial(self):
        """Only choosing Essentials ends a tutorial: a deselected switch (which
        keeps the mode) leaves it running, in Full."""
        at = AppTest.from_function(_tutorial_with_switch_app)
        at.session_state["ui_mode"] = "full"
        at.run()
        assert at.session_state["tutorial_active"] == "filter_annotate"
        at.segmented_control(key="ui_mode_switch").set_value(None).run()
        assert not at.exception, at.exception
        assert at.session_state["ui_mode"] == "full"
        assert at.session_state["tutorial_active"] == "filter_annotate"
        assert [b for b in at.button if b.key == "tutorial_exit"]

    def test_a_tutorial_started_in_simple_never_rewrites_the_cookie(self):
        """A viewer who had chosen Essentials keeps Essentials in the cookie: the
        script that writes it follows their choice, not the session's mode."""
        at = AppTest.from_function(_cookie_after_tutorial_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["cookie_mode"] == "essentials"
        assert at.session_state["ui_mode"] == "full"


def _tutorial_with_switch_app():
    """A tutorial armed once, beside the mode switch (as the header draws it)."""
    import streamlit as st

    from scanpath_studio import ui_mode
    from scanpath_studio.constants import _VIEW_SCANPATH

    st.session_state.setdefault("main_nav", _VIEW_SCANPATH)
    if not st.session_state.get("_tutorial_armed_once"):
        st.session_state["_tutorial_armed_once"] = True
        st.session_state["_tutorial_context"] = {
            "n_trials": 3,
        }
        from scanpath_studio.tour import _start_use_case

        _start_use_case("filter_annotate")
    ui_mode.render_switch(st)
    from scanpath_studio.tour import render_use_case_tutorial

    render_use_case_tutorial()


def _cookie_after_tutorial_app():
    """A viewer who chose Essentials, then started a tutorial in it."""
    import streamlit as st

    from scanpath_studio import tour, ui_mode

    st.session_state["ui_mode"] = ui_mode.SIMPLE
    ui_mode._choose_mode(ui_mode.SIMPLE)
    st.session_state["_tutorial_context"] = {
        "n_trials": 2,
    }
    tour._start_use_case("filter_annotate")
    st.session_state["cookie_mode"] = ui_mode.cookie_mode()
