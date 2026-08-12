"""Tests for the welcome tour + the dataset-setup guide spotlight card.

The setup guide is now a bottom-right floating card (``tour_mode == "wizard"``)
rather than a modal, so the user can follow along while filling in the wizard.
These exercise the arming + rendering + dismissal without booting the whole app.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _wizard_guide_app():
    from scanpath_studio.tour import (
        maybe_show_wizard_guide,
        render_spotlight_wizard_guide,
    )

    maybe_show_wizard_guide()
    render_spotlight_wizard_guide()


def _wizard_guide_replay_app():
    import streamlit as st

    from scanpath_studio.tour import _arm_wizard_guide, render_spotlight_wizard_guide

    # Simulate a session that already saw the guide, then a replay-button arm.
    st.session_state["wizard_guide_seen"] = True
    if not st.session_state.get("_armed_once"):
        st.session_state["_armed_once"] = True
        _arm_wizard_guide()
    render_spotlight_wizard_guide()


class TestWizardGuideSpotlight:
    def test_auto_arms_and_renders_card(self):
        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["tour_mode"] == "wizard"
        assert at.session_state["wizard_guide_seen"] is True
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_next" in keys
        assert "wizard_sp_back" in keys

    def test_skip_dismisses(self):
        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        at.button(key="wizard_sp_exit").click()
        at.run()
        assert at.session_state["tour_mode"] is None
        assert not any(b.key == "wizard_sp_next" for b in at.button)

    def test_last_step_shows_done(self):
        from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

        at = AppTest.from_function(_wizard_guide_app)
        at.run()
        at.session_state["wizard_guide_step"] = len(_WIZARD_GUIDE_STEPS) - 1
        at.run()
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_done" in keys

    def test_replay_button_re_arms_after_seen(self):
        at = AppTest.from_function(_wizard_guide_replay_app)
        at.run()
        assert at.session_state["tour_mode"] == "wizard"
        keys = {b.key for b in at.button if b.key}
        assert "wizard_sp_next" in keys


def _welcome_tour_app():
    from scanpath_studio.tour import maybe_show_welcome_tour, render_spotlight_tour

    maybe_show_welcome_tour()
    render_spotlight_tour()


def _welcome_tour_replay_app():
    import streamlit as st

    from scanpath_studio.tour import _arm_tour, render_spotlight_tour

    st.session_state["tour_seen"] = True
    if not st.session_state.get("_armed_once"):
        st.session_state["_armed_once"] = True
        _arm_tour()
    render_spotlight_tour()


class TestTourOptOut:
    """UX-12: "Don't show this again", persisted in the ``sps_tour_optout`` cookie."""

    def test_checkbox_on_welcome_step_defaults_off(self):
        at = AppTest.from_function(_welcome_tour_app)
        at.run()
        assert not at.exception, at.exception
        box = at.checkbox(key="tour_dont_show")
        assert box.value is False

    def test_ticking_suppresses_a_later_session(self):
        at = AppTest.from_function(_welcome_tour_app)
        at.run()
        at.checkbox(key="tour_dont_show").check().run()
        # Within the session the checkbox state is authoritative, so the gates
        # that decide whether to auto-open the tour both close.
        from scanpath_studio import tour

        assert at.session_state["tour_dont_show"] is True
        # A fresh session whose browser sends the cookie back never opens it.
        assert tour._tour_optout_script(True).count("max-age=0") == 0
        assert "sps_tour_optout=1" in tour._tour_optout_script(True)
        assert "max-age=0" in tour._tour_optout_script(False)

    def test_replay_ignores_the_opt_out(self):
        """ "Don't show again" stops the greeting, it doesn't remove the tutorial."""
        at = AppTest.from_function(_welcome_tour_replay_app)
        at.run()
        assert at.session_state["tour_mode"] == "spotlight"
        assert any(b.key == "tour_sp_next" for b in at.button)

    def test_opted_out_is_false_without_a_request_context(self):
        """Bare-mode / headless imports have no cookies — must not raise."""
        from scanpath_studio.tour import tour_opted_out

        assert tour_opted_out() is False


def test_welcome_tour_text_is_concise():
    """Every welcome/spotlight/wizard step body stays short (UI/UX: no walls of
    text). Guards against the steps creeping back to multi-paragraph blurbs."""
    from scanpath_studio.tour import (
        _SPOTLIGHT_STEPS,
        _STEPS,
        _WIZARD_GUIDE_STEPS,
    )

    for _title, body in _STEPS:
        assert len(body) <= 240, f"welcome dialog step too long: {body!r}"
    for step in _SPOTLIGHT_STEPS:
        assert len(step["body"]) <= 240, f"spotlight step too long: {step['body']!r}"
    for step in _WIZARD_GUIDE_STEPS:
        assert len(step["body"]) <= 280, f"wizard guide step too long: {step['body']!r}"


# -----------------------------------------------------------------------------
# Task-oriented tutorials (UX-40)
# -----------------------------------------------------------------------------


def _use_case_tutorial_app():
    import streamlit as st

    from scanpath_studio.constants import _VIEW_CORPUS
    from scanpath_studio.tour import _start_use_case, render_use_case_tutorial

    st.session_state.setdefault(
        "_tutorial_context",
        {
            "n_trials": 3,
            "has_words": True,
            "has_fixations": True,
            "has_comparable_readings": True,
            "has_corpus_variation": True,
        },
    )
    st.session_state.setdefault("main_nav", _VIEW_CORPUS)
    st.session_state.setdefault("single_subtab", "📝 Annotations")
    if not st.session_state.get("_tutorial_armed_once"):
        st.session_state["_tutorial_armed_once"] = True
        _start_use_case("filter_annotate")
    render_use_case_tutorial()


def _tutorial_library_optout_app():
    import streamlit as st

    from scanpath_studio.tour import render_tutorial_library

    st.session_state["tour_dont_show"] = True
    render_tutorial_library(
        {
            "n_trials": 2,
            "has_words": True,
            "has_fixations": True,
            "has_comparable_readings": True,
            "has_corpus_variation": True,
        }
    )


class TestUseCaseTutorials:
    def test_registry_is_unique_concise_and_outcome_oriented(self):
        from scanpath_studio.tour import TUTORIALS

        assert len(TUTORIALS) == 5
        assert len({tutorial.id for tutorial in TUTORIALS}) == len(TUTORIALS)
        for tutorial in TUTORIALS:
            assert tutorial.outcome.startswith("Finish")
            assert tutorial.estimated_time.endswith("min")
            assert tutorial.completion_test
            assert tutorial.docs_url.startswith("https://")
            assert tutorial.steps
            assert all(len(step.body) <= 300 for step in tutorial.steps)

    def test_availability_is_derived_from_loaded_data(self):
        import pandas as pd

        from scanpath_studio.tour import (
            TUTORIALS,
            build_tutorial_context,
            tutorial_availability,
        )

        empty = build_tutorial_context(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        availability = {
            tutorial.id: tutorial_availability(tutorial, empty)[0]
            for tutorial in TUTORIALS
        }
        assert availability == {
            "load_inspect": True,
            "filter_annotate": False,
            "publication_figure": False,
            "compare_readings": False,
            "explore_corpus": False,
        }

        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t1", "t2"],
                "text_id": ["same", "same"],
            }
        )
        ready = build_tutorial_context(
            pd.DataFrame({"word_id": [1]}),
            pd.DataFrame({"fixation_id": [1]}),
            combos,
        )
        assert all(tutorial_availability(tutorial, ready)[0] for tutorial in TUTORIALS)

    def test_navigation_opens_panels_and_exit_restores_the_start_location(self):
        from scanpath_studio.constants import _VIEW_CORPUS, _VIEW_SCANPATH

        at = AppTest.from_function(_use_case_tutorial_app).run()
        assert not at.exception, at.exception
        assert at.session_state["main_nav"] == _VIEW_CORPUS
        assert at.button(key="tutorial_open_surface")

        at.button(key="tutorial_open_surface").click().run()
        assert at.session_state["main_nav"] == _VIEW_SCANPATH
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

    def test_library_remains_available_after_welcome_opt_out(self):
        at = AppTest.from_function(_tutorial_library_optout_app).run()
        assert not at.exception, at.exception
        keys = {button.key for button in at.sidebar.button if button.key}
        assert "tutorial_start_load_inspect" in keys
        assert "tutorial_start_explore_corpus" in keys


# -----------------------------------------------------------------------------
# FAQ (UX-15)
# -----------------------------------------------------------------------------


def _faq_app():
    """Mirrors app.main's ordering: serve the dialog early, render the button late.

    The button only arms the dialog (``on_click``) so the modal doesn't wait on
    the heavy data/plot work it renders after — see ``tour.maybe_show_faq``.
    """
    from scanpath_studio.tour import maybe_show_faq, render_faq_button

    maybe_show_faq()
    render_faq_button()


class TestFaq:
    """The in-app FAQ dialog (UX-15) and its links out to the docs site."""

    def test_button_opens_a_dialog_with_every_item(self):
        from scanpath_studio.tour import _FAQ_ITEMS

        at = AppTest.from_function(_faq_app)
        at.run()
        assert any(b.key == "faq_open" for b in at.sidebar.button)
        assert not at.error

        at.sidebar.button(key="faq_open").click().run()
        assert not at.error
        assert len(at.expander) == len(_FAQ_ITEMS)

    def test_button_only_arms_the_dialog(self):
        """The click must set a flag, not open the dialog from its return value.

        The button renders at the bottom of ``app.main``; opening the dialog
        there made it wait out the whole rerun (~10 s of plot embeds). Rendering
        the button *alone* must therefore produce no dialog — the early
        ``maybe_show_faq`` call is what serves it.
        """

        def _button_only():
            from scanpath_studio.tour import render_faq_button

            render_faq_button()

        at = AppTest.from_function(_button_only)
        at.run()
        at.sidebar.button(key="faq_open").click().run()
        assert not at.error
        assert not at.expander, "the button opened the dialog itself"
        assert at.session_state["_faq_dialog_requested"] is True

    def test_docs_links_point_at_the_published_pages(self):
        """The FAQ is the app's help-context route into the docs — if these
        drift from the mkdocs nav the buttons 404."""
        from scanpath_studio.constants import CITATION
        from scanpath_studio.tour import DOCS_FAQ_URL, DOCS_TUTORIALS_URL

        assert DOCS_FAQ_URL == f"{CITATION['docs_url']}faq/"
        assert DOCS_TUTORIALS_URL == f"{CITATION['docs_url']}tutorials/"

    def test_answers_stay_short(self):
        """Same rule as the tour steps: the long version lives in docs/faq.md."""
        from scanpath_studio.tour import _FAQ_ITEMS

        assert _FAQ_ITEMS, "the FAQ must not be empty"
        for question, answer in _FAQ_ITEMS:
            assert question.endswith(("?", ".")), f"not a question: {question!r}"
            assert len(answer) <= 480, f"FAQ answer too long: {question!r}"


class TestSpotlightSelectorsResolve:
    """Every spotlight step must point at a container that actually exists.

    ``scanpath_studio/CLAUDE.md`` says to keep ``_SPOTLIGHT_STEPS`` in sync with
    the ``tour_grp_*`` wrappers, but nothing enforced it: a renamed or removed
    container leaves the step silently un-highlighted — the card still advances,
    it just points at nothing, which no other test would notice.
    """

    def _keyed_containers(self) -> set[str]:
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "scanpath_studio"
        source = "".join(
            (root / f"{module}.py").read_text()
            for module in ("tabs", "app", "controls", "annotations")
        )
        return set(re.findall(r'key="([\w]+)"', source))

    def test_every_selector_has_a_container(self):
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        keys = self._keyed_containers()
        missing = [
            step["selector"]
            for step in _SPOTLIGHT_STEPS
            if step.get("selector")
            and step["selector"].removeprefix(".st-key-") not in keys
        ]
        assert not missing, (
            "these tour steps point at containers that no longer exist — the step "
            f"will highlight nothing: {missing}"
        )

    def test_every_use_case_selector_has_a_container(self):
        from scanpath_studio.tour import TUTORIALS

        keys = self._keyed_containers()
        missing = [
            step.selector
            for tutorial in TUTORIALS
            for step in tutorial.steps
            if step.selector.removeprefix(".st-key-") not in keys
        ]
        assert not missing, (
            "these use-case tutorial steps point at containers that no longer "
            f"exist: {missing}"
        )

    def test_no_two_steps_spotlight_the_same_area(self):
        """UX-34: two steps sharing a selector lit up both areas at once.

        The "narrow the pool" and "pick a trial" steps both targeted the wrapper
        around *both* rows, so each highlighted the other's subject too.
        """
        from scanpath_studio.tour import _SPOTLIGHT_STEPS

        selectors = [s["selector"] for s in _SPOTLIGHT_STEPS if s.get("selector")]
        duplicates = {s for s in selectors if selectors.count(s) > 1}
        assert not duplicates, f"steps share a spotlight target: {duplicates}"

    def test_data_source_sits_outside_the_filter_spotlight(self):
        """UX-42: adjacent targets must not be nested inside one highlight."""
        import inspect

        from scanpath_studio.tabs import render_single_trial_tab

        source = inspect.getsource(render_single_trial_tab)
        assert "nb_source, nb_filters = st.columns(" in source
        assert "data_source_renderer(nb_source)" in source
        assert 'filter_box = nb_filters.container(key="tour_grp_narrow_by")' in source

    def test_filter_group_has_a_dataset_divider(self):
        """UX-42: the sibling groups retain a visible boundary between them."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert ".st-key-tour_grp_narrow_by {" in css
        assert "border-left: 1px solid var(--sps-border);" in css
        assert "padding-left: 0.7rem;" in css

    def test_subtabs_use_a_second_plot_width_row(self):
        """UX-43: open subtab content cannot contribute to the rail-row height."""
        import inspect

        from scanpath_studio.tabs import render_single_trial_tab

        source = inspect.getsource(render_single_trial_tab)
        assert 'plot_col, rail_col = st.columns([4, 1], gap="large")' in source
        assert 'subtabs_col, _ = st.columns([4, 1], gap="large")' in source
        assert 'subtabs_slot = subtabs_col.container(key="tour_grp_subtabs")' in source
        assert "with subtabs_slot:" in source

    def test_visualization_rail_has_responsive_independent_scroll(self):
        """UX-43: desktop scrolls the rail; narrow layouts return to page flow."""
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert ".st-key-scanpath_rail {" in css
        assert '[data-testid="stColumn"]:has(.st-key-scanpath_rail) {' in css
        assert "position: absolute;" in css
        assert "height: 100%;" in css
        assert "max-height: 100%;" in css
        assert "overflow-y: auto;" in css
        assert "@media (max-width: 900px)" in css
        assert "overflow-y: visible;" in css

    def test_plot_rail_uses_one_compact_control_header(self):
        """UX-44: modes and visualization settings share one rail heading."""
        import inspect

        from scanpath_studio import controls
        from scanpath_studio.tabs import render_single_trial_tab

        tab_source = inspect.getsource(render_single_trial_tab)
        control_source = inspect.getsource(controls.sidebar_controls)

        assert 'rail_heading.markdown("## 🎛️ Plot controls")' in tab_source
        assert 'st.markdown("## 🎛️ View modes")' not in tab_source
        assert 'st.markdown("## 🎨 Visualization")' not in tab_source
        assert 'viz.caption("Quick views")' in control_source
        assert 'sac_grp = viz.expander("↗️ Saccades", expanded=False)' in control_source

    def test_plot_rail_merges_figure_and_canvas_without_nested_expander(self):
        """UX-44: four lower groups become three without nesting expanders."""
        import inspect

        from scanpath_studio import app, controls

        control_source = inspect.getsource(controls.sidebar_controls)
        canvas_source = inspect.getsource(app.render_sidebar_canvas_controls)

        assert 'figure_grp = viz.expander("📐 Figure & canvas"' in control_source
        assert "canvas_renderer(figure_grp)" in control_source
        assert "display = host if bare else host.expander" in canvas_source
        assert 'viz.expander("🖥️ Canvas & text"' not in control_source
        assert 'viz.expander("📐 Figure & axes"' not in control_source

    def test_plot_rail_uses_contextual_style_filter_and_header_reset(self):
        """UX-44: repeated labels stay terse and Reset no longer costs a row."""
        import inspect

        from scanpath_studio import controls
        from scanpath_studio.tabs import render_single_trial_tab

        tab_source = inspect.getsource(render_single_trial_tab)
        control_source = inspect.getsource(controls.sidebar_controls)

        assert "render_viz_reset(st, compact=True)" in tab_source
        assert 'popover("⚙️ Style"' in control_source
        assert 'f"🧹 Filter{' in control_source
        assert "Reset settings" not in control_source

        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        assert ".st-key-railbtn_plot_reset button {" in css
        assert "padding-right: 1.25rem !important;" in css
        assert "@container sps-rail (max-width: 240px)" in css

    def test_stacked_rail_header_cannot_wrap_reset_out_of_the_panel(self):
        """BUG-24: the narrow-rail header must stack, not wrap sideways.

        Streamlit ships every ``stHorizontalBlock`` with ``flex-wrap: wrap``.
        Flipping only ``flex-direction`` to ``column`` therefore turns the
        header into a *column-wrapping* flex container, and since the block has
        a definite height the Reset column wraps into a second track to the
        RIGHT — ~100px outside the rail, which clips it (``overflow-y: auto``
        computes ``overflow-x`` to ``auto`` too). The rail is ~150px wide at
        ordinary desktop widths, so this rule is the common case, not the
        exception: Reset was invisible until the user zoomed out far enough for
        the rail to clear 240px and the row layout to take over.
        """
        from scanpath_studio.styles import get_app_css

        css = get_app_css()
        block = css.split("@container sps-rail (max-width: 240px)", 1)[1]
        block = block.split("@", 1)[0]
        assert "flex-direction: column;" in block
        assert "flex-wrap: nowrap;" in block


def test_spotlight_helpers_are_plain_functions_that_return_their_css():
    """Regression: the DATA-22 factoring must not steal `render_spotlight_tour`'s
    `@st.fragment`.

    Inserting `_highlight_css` / `_scroll_into_view_script` directly above the
    decorated function once left the decorator attached to the *helper* — which
    made it return `None` (a fragment has no return value), silently dropping the
    highlight outline from both the welcome tour and the setup guide, and cost
    the tour its fragment so every Back/Next waited on a full app rerun.
    """
    import inspect

    from scanpath_studio import tour

    for helper in (tour._highlight_css, tour._scroll_into_view_script):
        assert not inspect.getsource(helper).lstrip().startswith("@"), (
            f"{helper.__name__} must stay an undecorated pure helper"
        )

    css = tour._highlight_css(".st-key-wiz_open_setup", "#1f77b4")
    assert "tour-pulse" in css and "outline: 3px solid #1f77b4" in css
    assert tour._highlight_css("", "#1f77b4") == ""

    # Both spotlight renderers must still be fragments (see the module docstring:
    # navigation must never wait for the ~10 s full-app rerun).
    for fn in (tour.render_spotlight_tour, tour.render_spotlight_wizard_guide):
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} lost its @st.fragment"


def test_wizard_guide_steps_are_anchored_to_real_wizard_steps():
    """DATA-22 §4: the guide drives the wizard instead of narrating beside it."""
    from scanpath_studio import wizard_shell
    from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

    known = {s.id for s in wizard_shell.STEPS}
    anchored = [s for s in _WIZARD_GUIDE_STEPS if s["step_id"]]
    assert len(anchored) == len(wizard_shell.STEPS), (
        "every wizard step should have a guide step pointing at it"
    )
    for step in anchored:
        assert step["step_id"] in known
        # Keyed expanders supply this selector for free.
        assert step["selector"] == f".st-key-{wizard_shell.open_key(step['step_id'])}"
