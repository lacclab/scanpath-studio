"""Scanpath Studio Streamlit app.

This is the main entry point for the Streamlit application that visualizes
eye-tracking scanpaths over text.

Architecture:
    - Entry point: main() function configures Streamlit and orchestrates the UI
    - Data flow: CSV upload → schema inference → normalization → filtering → plotting
    - UI structure: Sidebar controls + views (Scanpath Visualization [with
      Comparisons + Line assignment subtabs], Corpus Analysis, Data Inspection)

Data Pipeline:
    1. Load raw CSVs (words + fixations + optional raw gaze)
    2. Infer schema via candidate column matching
    3. Normalize to canonical column names
    4. Apply participant/trial/text filters
    5. Build trial combinations for selection
    6. Render visualizations with user-controlled settings

Usage:
    # Development mode (watch for changes):
    $ streamlit run scanpath_studio/app.py

    # Package mode:
    $ python -m scanpath_studio
    # or
    $ scanpath-studio
"""

from __future__ import annotations

import html
import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running via `streamlit run scanpath_studio/app.py` by adding the
# repository root to sys.path when executed as a script instead of a package.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scanpath_studio import metadata as metadata_mod
from scanpath_studio.annotations import (
    filter_keys,
)
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    AUTHOR_CHOICE,
    BACKGROUND_PRESETS,
    BENCHMARK_LABEL_SUFFIX,
    BENCHMARK_SETUP_CHOICE,
    BENCHMARK_SHORT_SUFFIX,
    BENCHMARK_WIP_SUFFIX,
    CITATION,
    DATA_EDITOR_KEY,
    DATA_EDITOR_OFFSCREEN_KEY,
    DATA_OVERVIEW_KEY,
    DATA_OVERVIEW_OFFSCREEN_KEY,
    DATA_PAGE_KEY,
    DATA_PAGE_OFFSCREEN_KEY,
    DATASET_COUNTS_STORE_KEY,
    DATASET_EDITOR_OPEN_KEY,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIGURE_SIZE,
    DEFAULT_LINE_SPACING,
    DEMO_CHOICE,
    EYEGENBENCH_DEFAULT_DIR,
    FOCUS_MAPPING_KEY,
    FONT_FAMILY,
    MULTIPLEYE_BUNDLE_CHOICE,
    MULTIPLEYE_DEFAULT_DIR,
    ONESTOP_CHOICE,
    ONESTOP_LACCLAB_DEFAULT_DIR,
    ONESTOP_PART_LABELS,
    ONESTOP_PUBLIC_CHOICE,
    ONESTOP_PUBLIC_DEFAULT_DIR,
    ONESTOP_REGIME_LABELS,
    ONESTOP_VARIANT_LABELS,
    POTEC_DEFAULT_DIR,
    PUBLIC_DATASETS_CHOICE,
    SYNTHETIC_CHOICE,
    TRIAL_IDENTITY_FULL_KEY,
    UPLOAD_CHOICE,
    WIZARD_LEAVE_KEY,
    WIZARD_STAY_KEY,
    WORD_LABEL_COLOR,
    language_display,
    preprocessing_enabled,
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    WORD_FIELD_SPECS,
    _labeled,
    _pin,
    clear_trial_filter,
    clear_trial_filters,
    column_mapping_ui,
    has_active_trial_filters,
    read_trial_filters,
    viz_settings_from_state,
)
from scanpath_studio.data import (
    FIX_OPTIONAL_FIELDS,
    TRIAL_IDENTITY_SAMPLE,
    WORD_OPTIONAL_FIELDS,
    ReadPlan,
    compute_canvas_size,
    count_trials,
    default_filters,
    diagnose_filters,
    diagnose_trial_identity,
    empty_fixations_frame,
    empty_words_frame,
    filter_data,
    filter_frame_to_keys,
    filter_raw_gaze,
    filter_to_keys,
    clear_frame_cache,
    filter_trials,
    frame_cache,
    frame_fingerprint,
    harmonize_frames,
    infer_raw_gaze_schema,
    load_onestop_server_bundle,
    load_sample_data,
    load_sample_raw_gaze,
    normalize_fixations,
    normalize_raw_gaze,
    normalize_words,
    onestop_data_dir,
    onestop_full_bundle_exists,
    plan_table_read,
    preprocess_fixation_stage,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    read_table,
    read_table_columns,
    read_tables,
    reset_fingerprint_memo,
    resolve_stimulus_image_paths,
    trial_identity_warning,
    trial_keys,
    trial_mapping_columns,
    upload_exceeds_limit,
    uploaded_files_total_bytes,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from scanpath_studio.datasets import (
    load_multipleye_server_bundle,
    multipleye_bundle_dir,
)
from scanpath_studio.debug_log import (
    debug_enabled,
    install_log_capture,
    log_state_change,
    seed_debug_mode,
    timed,
)
from scanpath_studio.easter_egg import render_easter_egg
from scanpath_studio.experimental_setup import (
    Provenance,
    SetupSnapshot,
    font_pt_to_px,
    pixels_per_degree,
)
from scanpath_studio.menu import (
    close_open_popovers,
    render_nav,
    render_top_menu,
    view_label,
)
from scanpath_studio.multipart import SCREEN_ID, extract_part, part_catalog
from scanpath_studio.persistence import (
    PERSIST_ENV_VAR,
    STATE_DIR_ENV_VAR,
    cache_status,
    clear_local_state,
    human_size,
    is_loopback_url,
    persistence_paused,
    restore_local_state,
    restored_from_cache,
    save_local_state,
    set_persistence_paused,
    skip_next_local_save,
)
from scanpath_studio.session_keys import COLUMN_MAPPING_PREFIX, PARAM_CORPUS
from scanpath_studio.styles import get_app_css
from scanpath_studio.tabs import (
    _build_figure_settings,
    _render_column_mapping_section,
    _render_save_restore_expander,
    render_corpus_analysis_tab,
    render_data_inspection_tab,
    render_participant_metadata_section,
    render_single_trial_tab,
    render_trial_identity_section,
    render_trial_metadata_section,
)
from scanpath_studio.tour import (
    build_tutorial_context,
    maybe_show_faq,
    maybe_show_tutorial_library,
    maybe_show_welcome_tour,
    render_spotlight_tour,
    render_use_case_tutorial,
    stash_tutorial_context,
)
from scanpath_studio.url_state import (
    CORPUS_SOURCE_TOKEN,
    _apply_pending_trial_selection,
    _apply_uploaded_plot_config,
    _apply_url_preset,
    _apply_url_trial_selection,
    _build_share_query,  # noqa: F401  re-exported for tests
    _go_data,
    _render_share_body,
    corpus_choice_for_slug,
)

# NOTE: ``scanpath_studio.wizard`` is imported lazily inside the two functions
# that use it (resolve_data_source, main), not here. wizard does
# ``from . import app`` at module top, so a top-level import here forms a cycle:
# under ``streamlit run app.py`` the script isn't registered as
# ``scanpath_studio.app``, so wizard's ``from . import app`` re-imports app fresh,
# re-entering this import while wizard is still half-loaded → ImportError.
# Deferring it lets app finish loading before wizard is ever imported.
from scanpath_studio.utils import build_combo_options, extract_trial

# Re-exported under a private alias so tests can import them from `app`; keep the
# F401 silence (they're not used by app.py itself).
from scanpath_studio.utils import (  # noqa: F401
    build_comparison_options as _build_comparison_options,
)
from scanpath_studio.utils import (  # noqa: F401
    friendly_trial_label as _friendly_trial_label,
)


def __getattr__(name):
    """Lazily re-export the wizard helpers from ``app`` for back-compat.

    ``scanpath_studio.wizard`` can't be imported at module load (it imports
    ``app`` back, forming a cycle — see the note above the utils import), but
    ``from scanpath_studio.app import _render_data_setup`` (and the other wizard
    helpers) was a supported entry point used by tests. Resolving it here, on
    attribute access, defers the wizard import until app is fully loaded."""
    if name in ("_enter_add_data_wizard", "_remove_dataset", "_render_data_setup"):
        from scanpath_studio import wizard

        return getattr(wizard, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def public_datasets_enabled() -> bool:
    """Whether the "Public datasets" source (PoTeC, MultiplEYE) is offered.

    Enabled by default; set ``SCANPATH_PUBLIC_DATASETS=0`` (or ``false`` / ``no``)
    to hide it. Read at call time so tests can toggle the env var."""
    raw = os.environ.get("SCANPATH_PUBLIC_DATASETS", "").strip().lower()
    return raw not in ("0", "false", "no")


def configure_page() -> None:
    """Streamlit page config + custom CSS.

    No ``initial_sidebar_state``: nothing writes to ``st.sidebar`` any more (the
    former sidebar groups are popovers on the top menu bar — see
    :mod:`scanpath_studio.menu`), so Streamlit renders no sidebar chrome to
    collapse. Embeds and welcome-tour sessions used to ask for it explicitly;
    both now get a page with no sidebar at all, which is what they wanted.
    """
    st.set_page_config(
        page_title="Scanpath Studio - Visualization of Eye Movements in Reading",
        page_icon="👀",
        layout="wide",
    )
    st.markdown(get_app_css(), unsafe_allow_html=True)


#: The app's wordmark, shown in Streamlit's own header (UX-62). Inside the
#: package so it ships with a pip install — see `pyproject.toml`'s
#: `package-data`, and `desktop/scanpath_studio.spec` for the frozen build.
LOGO_PATH = Path(__file__).parent / "assets" / "scanpath_studio_title_logo.png"


def render_app_logo() -> None:
    """Put the wordmark in the top-left of Streamlit's header (UX-62).

    ``st.logo`` is the only way into that strip: the nav is drawn there by
    Streamlit itself (``st.navigation(position="top")``), and the page body —
    where the title used to live, a row below — cannot reach up into it.

    Must run **before** the nav, and is cheap enough to run on every rerun.
    Falls back silently to nothing when the file is missing: a wordmark is
    chrome, and an editable checkout that has not been reinstalled should still
    open rather than raise on a decoration.
    """
    if not LOGO_PATH.is_file():
        logging.getLogger(__name__).warning(
            "App logo not found at %s; header left bare.", LOGO_PATH
        )
        return
    st.logo(str(LOGO_PATH), size="large", link=CITATION["docs_url"])


def _render_about_panel(host=None) -> None:
    """The page heading — now only what the header cannot carry.

    UX-62 moved the title into Streamlit's header as the wordmark
    (:func:`render_app_logo`), so this no longer prints "Scanpath Studio" or its
    one-line description; both would then appear twice, a row apart. The
    description survives in **About** (a dialog off the ❓ Help menu) and in the
    README.

    ``host`` is ``menu.TopMenu.title`` — the left side of the row the settings
    triggers share. The container is still created, and deliberately: ❓ Help and
    💾 Session are laid out against it (see ``menu.render_top_menu``), and it is
    where anything page-level would go.
    """
    (host if host is not None else st).container(key="about_header")


# Base URL for the DiLi Lab (UZH) people pages — three co-author links hang off
# it, so it's factored out rather than repeated in the About markdown.
_DILI = "https://www.cl.uzh.ch/en/research-groups/digital-linguistics/people"


# Human labels for the trial-filter groups, used by the UX-7 empty-state report.
_FILTER_GROUP_LABELS = {
    "participants": "Participant",
    "favorites": "★ Favorites only",
    "required_tags": "Required tags",
    "excluded_tags": "Excluded tags",
}


def _filter_diagnosis_steps(trial_filters: dict) -> list:
    """``(label, apply)`` pairs for :func:`data.diagnose_filters` — one per
    *active* trial filter, each applying only itself (UX-7).

    Condition filters get one step each (named by the column) rather than being
    lumped together, since "which of my six narrowings emptied this?" is exactly
    the question the blanket warning used to leave unanswered.
    """
    steps: list = []
    if trial_filters.get("participants") is not None:
        chosen = trial_filters["participants"]
        # DATA-20: a participant-grain metadata constraint resolves into this
        # same slot, so the step has to name *and clear* whichever widgets
        # actually produced the narrowing — otherwise the report blamed
        # "Participant" and its Clear button popped `filter_participants`, a
        # no-op against a `filter_meta_*` selection.
        meta_keys = tuple(trial_filters.get("participant_filter_keys") or ())
        label = f"{_FILTER_GROUP_LABELS['participants']} ({len(chosen)} selected)"
        if meta_keys:
            label = (
                "By reader"
                if not st.session_state.get("filter_participants")
                else f"{label} + by reader"
            )
        steps.append(
            (
                label,
                lambda w, f, p=chosen: filter_trials(w, f, participants=p),
                ("filter_participants", *meta_keys),
            )
        )
    keys_by_col = trial_filters.get("metadata_keys") or {}
    for col, allowed in (trial_filters.get("metadata") or {}).items():
        label = f"{col.replace('_', ' ').capitalize()} = {', '.join(sorted(map(str, allowed))[:4])}"
        if len(allowed) > 4:
            label += ", …"
        steps.append(
            (
                label,
                lambda w, f, c=col, a=allowed: filter_trials(w, f, metadata={c: a}),
                (keys_by_col.get(col, f"filter_{col}"),),
            )
        )
    # UX-49: a range narrows too, so it is one of the things that can empty the
    # pool and has to be named in the diagnosis alongside the categorical ones.
    for col, bounds in (trial_filters.get("ranges") or {}).items():
        steps.append(
            (
                f"{col.replace('_', ' ').capitalize()} between "
                f"{bounds[0]:g} and {bounds[1]:g}",
                lambda w, f, c=col, b=bounds: filter_trials(w, f, ranges={c: b}),
                (keys_by_col.get(col, f"filter_{col}_range"),),
            )
        )

    def _annotation_step(name: str, keys: tuple, **kwargs):
        def _apply(w, f):
            frame = w if f.empty else f
            if frame.empty:
                return w, f
            present = {
                (str(p), str(t))
                for p, t in zip(frame["participant_id"], frame["trial_id"])
            }
            return filter_to_keys(w, f, set(filter_keys(list(present), **kwargs)))

        steps.append((name, _apply, keys))

    if trial_filters.get("favorites_only"):
        _annotation_step(
            _FILTER_GROUP_LABELS["favorites"],
            ("filter_favorites",),
            favorites_only=True,
        )
    if trial_filters.get("required_tags"):
        tags = trial_filters["required_tags"]
        _annotation_step(
            f"{_FILTER_GROUP_LABELS['required_tags']}: {', '.join(tags)}",
            ("filter_req_tags",),
            required_tags=tags,
        )
    if trial_filters.get("excluded_tags"):
        tags = trial_filters["excluded_tags"]
        _annotation_step(
            f"{_FILTER_GROUP_LABELS['excluded_tags']}: {', '.join(tags)}",
            ("filter_exc_tags",),
            excluded_tags=tags,
        )
    return steps


def _render_empty_after_filtering(
    words_all: pd.DataFrame, fixations_all: pd.DataFrame, trial_filters: dict
) -> None:
    """UX-7(a): say *which* filter emptied the pool, and offer a way out.

    The old message was one blanket "No data after filtering" for every cause,
    which left the user to bisect their own filters by hand. This measures each
    active filter against the unfiltered dataset, names the one(s) that leave
    nothing on their own (or reports the combination when each is individually
    fine), and offers to clear **that filter alone** as well as all of them.

    Rendered as one bordered panel: the previous version stacked an `st.warning`
    banner, a markdown list and a button as three visually unrelated blocks, so
    the diagnosis didn't read as belonging to the message above it.
    """
    total = count_trials(words_all, fixations_all)
    if not has_active_trial_filters():
        # Nothing is filtering, so the dataset itself is empty — a different
        # problem, and telling the user to loosen filters would be a wild goose
        # chase.
        with st.container(border=True, key="empty_state_panel"):
            st.markdown("#### This dataset has no trials to show")
            st.markdown(
                "Pick another **Data source**, or check the column mapping on "
                "the 🗂️ **Data** page."
            )
        return

    report = diagnose_filters(
        words_all, fixations_all, _filter_diagnosis_steps(trial_filters)
    )
    culprits = [row for row in report if row["empties"]]
    with st.container(border=True, key="empty_state_panel"):
        st.markdown(
            f"#### No trials match your filters\n"
            f"**0** of the **{total:,} trials** in this dataset get through."
        )
        rows = culprits or report
        if culprits:
            st.markdown(
                "On its own, this leaves nothing:"
                if len(culprits) == 1
                else "Each of these leaves nothing on its own:"
            )
        elif report:
            st.markdown(
                "Every filter keeps something on its own — it's the "
                "**combination** that leaves nothing:"
            )
        for i, row in enumerate(rows):
            text_col, clear_col = st.columns([5, 1], vertical_alignment="center")
            kept = "" if row["empties"] else f" — keeps {row['kept']:,} of {total:,}"
            text_col.markdown(f"{row['label']}{kept}")
            if row["keys"]:
                clear_col.button(
                    "Clear",
                    key=f"clear_one_filter_{i}",
                    on_click=clear_trial_filter,
                    args=tuple(row["keys"]),
                    help=f"Reset only this filter — {row['label']}.",
                    width="stretch",
                )
        st.button(
            "✕ Clear all filters",
            key="clear_all_trial_filters",
            type="primary",
            on_click=clear_trial_filters,
            help="Reset every Narrow-by, condition and annotation filter.",
        )


def _forget_recovery_cache() -> None:
    """Delete the on-device copy without changing automatic saving.

    The confirmation triggers a full rerun, whose normal epilogue would write
    the still-open session straight back to disk. Suppress only that one write;
    the user's saving toggle is left exactly as it was and later changes save
    normally.
    """
    clear_local_state(st.session_state)
    skip_next_local_save(st.session_state)
    st.session_state["_recovery_cache_forgotten"] = True


#: BUG-36 — the Clear recovery cache button's confirmation flag.
_FORGET_CACHE_PENDING_KEY = "_forget_cache_pending"


def _reopen_session_dialog() -> None:
    """Whole-app rerun that leaves the 💾 Session modal open behind it (UX-100).

    An `st.rerun(scope="app")` closes the dialog it is called from — right, when
    the answer was *reset everything*, and wrong for a confirm/cancel pair that
    the user expects to land back on the panel that asked. Re-arming before the
    rerun is what puts it back. Never call it from ``_reset_everything``'s path:
    that one clears session state, so there is no session left to show.
    """
    st.session_state[_SESSION_DIALOG_KEY] = True
    st.rerun(scope="app")


def _forget_cache_confirmation(host) -> None:
    """The "are you sure" row — BUG-36. Drawn by ``_render_recovery_cache_panel``.

    **UX-100 unwrapped it from an ``st.dialog``.** The panel it belongs to is
    itself the 💾 Session modal now, and Streamlit allows no dialog inside a
    dialog — so the question is asked in place, right under the button that
    raised it, which on a panel this short is where it reads best anyway.

    Handled by each button's *return value*, not ``on_click`` — a dialog body is
    a fragment, and an ``on_click`` inside one reruns only the fragment (see
    ``_delete_confirmation_dialog``, which learned that as BUG-36).
    """
    host.warning(
        "Delete the recovery copy from this computer? Your open session and "
        "automatic-saving setting stay unchanged.",
        icon="⚠️",
    )
    yes, no = host.columns(2)
    if yes.button(
        "🗑 Clear cache", key="forget_cache_confirm", type="primary", width="stretch"
    ):
        _forget_recovery_cache()
        st.session_state.pop(_FORGET_CACHE_PENDING_KEY, None)
        _reopen_session_dialog()
    if no.button("Keep it", key="forget_cache_cancel", width="stretch"):
        st.session_state.pop(_FORGET_CACHE_PENDING_KEY, None)
        _reopen_session_dialog()


def _toggle_recovery_saving() -> None:
    """Mirror the panel's saving toggle into the persistence pause flag."""
    set_persistence_paused(
        st.session_state, not bool(st.session_state.get("persist_local_saving", True))
    )
    st.session_state.pop("_recovery_cache_forgotten", None)


def _render_recovery_cache_panel(app_url: str, *, slot=None) -> None:
    """Render the "🗄️ Recovery cache" menu panel (ENG-30).

    Show the current store, its saving toggle and its clear action. On a hosted
    deployment, explain only that automatic recovery is unavailable.

    ``slot`` is the 🗄️ Recovery cache block of the 💾 Session popover ``main``
    reserves on the top menu bar (UX-38), so the panel can render *after* this run's ``save_local_state`` and
    still sit in its own menu group. ``cache_status`` re-reads the manifest each
    run (a few ``stat`` calls plus a small JSON) rather than being cached — a
    status panel that lags the thing it reports is worse than no panel.

    Renders **bare** into ``slot``: the popover trigger is the disclosure, so
    the old ``expander("🗄️ Recovery cache")`` would only repeat the label (and a
    popover nests no expander anyway). See :mod:`scanpath_studio.menu`.
    """
    container = slot if slot is not None else st.container()
    status = cache_status(url=app_url)
    with container:
        if not status["enabled"]:
            st.caption(
                "**Not available here.** This deployment keeps your work in "
                "memory only — closing or refreshing the tab loses the datasets "
                "you uploaded, their column mappings and your annotations. Use "
                "the JSON backup below to keep your settings and annotations; "
                "it does not include the dataset files themselves."
            )
            if status["override"] == "off":
                st.caption(f"Turned off by `{PERSIST_ENV_VAR}=0`.")
            return

        # UX-99: say what this panel *is* before showing its status line. The
        # numbers and the folder path underneath only make sense once the reader
        # knows a copy is being kept and that it never leaves the machine — the
        # old panel opened straight into "Saved: 0 datasets · 5.9 KB" and left
        # both questions to a tooltip full of environment variables.
        st.caption(
            "Your uploaded datasets, their column mappings, your settings and "
            "your annotations are saved on **this computer** as you work, and "
            "reopened for you next time. Nothing is uploaded anywhere."
        )

        if restored_from_cache(st.session_state):
            st.success("Recovered when the app opened.", icon="↩️")
        if status["exists"] and status["readable"]:
            n_sets = len(status["datasets"])
            st.markdown(
                f"**Saved:** {n_sets} dataset{'s' if n_sets != 1 else ''} · "
                f"{status['annotations']} annotation"
                f"{'s' if status['annotations'] != 1 else ''} · "
                f"{human_size(status['bytes'])}"
            )
        elif status["exists"]:
            st.warning(
                "The stored session can't be read (written by a different "
                "version, or incomplete). It is ignored; saving over it is "
                "safe.",
                icon="⚠️",
            )
        elif st.session_state.get("_recovery_cache_forgotten"):
            st.caption("Cleared. Nothing is stored on this computer.")
        else:
            st.caption("Nothing saved yet. The first change creates the cache.")

        # Seed rather than pass `value=`: the Forget callback writes this key via
        # the session-state API, and a widget carrying both logs Streamlit's
        # "default value but also had its value set via the Session State API"
        # warning on every run (same fix as the 0.27.1 restored-value pass).
        st.session_state.setdefault(
            "persist_local_saving", not persistence_paused(st.session_state)
        )
        st.toggle(
            "Save changes automatically",
            key="persist_local_saving",
            on_change=_toggle_recovery_saving,
            help="On: your work is written to the folder below as you go, so a "
            "refresh, a crash or a restart picks up where you left off. Off: "
            "this session stays in memory only and closing the tab loses it. "
            "Turning it off does not delete what is already saved — use "
            "**Clear recovery cache** for that.",
        )
        if st.button(
            "🗑 Clear recovery cache",
            key="forget_recovery_cache_btn",
            width="stretch",
            disabled=not status["exists"],
            help="Delete the saved copy from this computer. What you have open "
            "right now is untouched, and saving stays on unless you turn the "
            "toggle above off.",
        ):
            st.session_state[_FORGET_CACHE_PENDING_KEY] = True
        if st.session_state.get(_FORGET_CACHE_PENDING_KEY):
            # Right under the button that raised it — see the function's own
            # note on why this is no longer a modal of its own.
            _forget_cache_confirmation(container)
        st.caption(f"Saved in this folder on your computer: `{status['directory']}`")
        # The environment-variable escape hatches, spelled out rather than
        # listed. They used to be the panel's only explanation of itself, packed
        # into one tooltip on the folder path (UX-99).
        st.caption(
            "Prefer to set this outside the app? Start it with "
            f"`{PERSIST_ENV_VAR}=0` to never save, or "
            f"`{STATE_DIR_ENV_VAR}=/your/folder` to save somewhere else. "
            "`scanpath-studio cache` reports the same details from a terminal."
        )


_RESET_EVERYTHING_PENDING_KEY = "_reset_everything_pending"


def _reset_everything() -> None:
    """Remove all user-owned session state and restart on the bundled demo."""
    clear_local_state(st.session_state)
    st.query_params.clear()
    st.session_state.clear()


def _reset_everything_confirmation(host) -> None:
    """The "are you sure" row for ♻️ Reset everything.

    Inline rather than an ``st.dialog`` for the same reason as
    :func:`_forget_cache_confirmation`: it is raised from inside the 💾 Session
    modal, and Streamlit allows no dialog inside a dialog (UX-100).
    """
    host.warning(
        "Remove uploaded datasets, annotations, mappings and settings, then "
        "return to the bundled demo?",
        icon="⚠️",
    )
    yes, no = host.columns(2)
    if yes.button(
        "♻️ Reset everything",
        key="reset_everything_confirm",
        type="primary",
        width="stretch",
    ):
        _reset_everything()
        st.rerun(scope="app")
    if no.button("Cancel", key="reset_everything_cancel", width="stretch"):
        st.session_state.pop(_RESET_EVERYTHING_PENDING_KEY, None)
        _reopen_session_dialog()


def _render_reset_everything_panel(*, slot=None) -> None:
    """Render Session's always-reachable full reset action."""
    container = slot if slot is not None else st.container()
    if container.button(
        "♻️ Reset everything",
        key="session_reset_everything",
        width="stretch",
        help="Remove uploaded datasets and all session settings, then return to "
        "the bundled demo.",
    ):
        st.session_state[_RESET_EVERYTHING_PENDING_KEY] = True
    if st.session_state.get(_RESET_EVERYTHING_PENDING_KEY):
        _reset_everything_confirmation(container)


#: UX-100 — the 💾 Session nav entry's request flag. Same arm-then-serve shape as
#: ❓ Help's three entries: a nav selection cannot open a dialog itself (the
#: router reruns), so `menu._arm_help_action` sets this and `main` serves it.
_SESSION_DIALOG_KEY = "_session_dialog_requested"


def _arm_session() -> None:
    """Request the 💾 Session dialog. Called by the nav entry (``menu.py``)."""
    st.session_state[_SESSION_DIALOG_KEY] = True


@st.dialog("💾 Session", width="large")
def _session_dialog(app_url: str, backup_renderer=None) -> None:
    """The 💾 Session modal: what this session is holding, and how to keep it.

    Four blocks, in the order UX-96 settled on. Recovery and a JSON backup are
    deliberately separate and deliberately in that order: recovery contains the
    local dataset tables and happens automatically, while the portable JSON is
    user-triggered and intentionally omits those tables — a distinction that is
    the panel's hierarchy rather than a tooltip-only caveat.

    ``backup_renderer`` fills the ⬇️ JSON backup block. It is a closure rather
    than data because the panel needs the live figure settings and trial
    selection, which only exist near the end of ``main`` — and ``main`` returns
    early on every path where the dataset can't be drawn (the wizard mid-flight,
    a rejected mapping, an empty pool). Those paths pass ``None``, and the block
    says why rather than rendering an empty heading, which is what BUG-28 saw.

    **A dialog body is a fragment.** It runs only while the modal is open, so
    every widget in here either re-seeds from a durable value each render (the
    persistence pause toggle, the 🐛 Debug gate) or holds nothing worth keeping.
    An interaction in here reruns *this*, not ``main`` — hence the explicit
    ``st.rerun(scope="app")`` after a restored backup, and the two inline
    confirmations (Streamlit allows no dialog inside a dialog).
    """
    from scanpath_studio.debug_log import (
        debug_enabled,
        render_debug_panel,
        render_debug_toggle,
    )

    recovery = st.container(key="session_auto_recovery")
    recovery.markdown("#### 🗄️ Automatic recovery")
    _render_recovery_cache_panel(app_url, slot=recovery.container())

    backup = st.container(key="session_json_backup")
    backup.markdown("#### ⬇️ JSON backup")
    if backup_renderer is not None:
        backup_renderer(backup.container())
    else:
        backup.caption(
            "Available once a dataset is loaded and drawable — a backup records "
            "the figure's settings and your annotations, and there is no figure "
            "to record yet."
        )

    reset = st.container(key="session_reset")
    reset.markdown("#### ♻️ Reset")
    _render_reset_everything_panel(slot=reset.container())

    debug_tools = st.container(key="session_debug_tools")
    debug_tools.markdown("#### 🐛 Debug tools")
    render_debug_toggle(debug_tools.container())
    if debug_enabled():
        render_debug_panel(debug_tools.container())


def maybe_show_session(app_url: str, backup_renderer=None) -> None:
    """Open the 💾 Session dialog if the nav entry armed it.

    Unlike ``maybe_show_about`` this is served **late**, at whichever point of
    ``main`` the backup renderer exists — the panel reports what this run just
    persisted and offers a backup of the live figure, neither of which is known
    early. Exactly one call runs per script run (each early return has its own),
    which is what keeps the widgets inside single widgets.
    """
    if st.session_state.pop(_SESSION_DIALOG_KEY, False):
        _session_dialog(app_url, backup_renderer)


def _arm_about() -> None:
    """``on_click`` callback for the About button: request the dialog.

    Same shape as ``tour._arm_faq`` — a dialog can't be opened from a callback,
    so this only sets a flag :func:`maybe_show_about` serves early in ``main``.
    """
    st.session_state["_about_dialog_requested"] = True


def maybe_show_about() -> None:
    """Open the About dialog if the ❓ Help menu button armed it.

    Call from ``main()`` beside ``maybe_show_faq``, BEFORE the heavy data / plot
    work: the button renders at the very *bottom* of ``main()``, so serving the
    dialog from its return value would leave the modal waiting on the whole
    rerun (including the ~10 s plot embeds).
    """
    if st.session_state.pop("_about_dialog_requested", False):
        _about_dialog()


def render_about_button(host=None) -> None:
    """Render the **ℹ️ About** button in the top menu's ❓ Help popover.

    A dialog rather than the popover it used to be: a popover nests no popover,
    and About is long (authors, links, BibTeX, the AI-assistance note) — inline
    in Help it would bury the tour and tutorial buttons above it. It is also
    pure display, so unlike ⚙️ Configure it loses nothing by only rendering while
    open (see :mod:`scanpath_studio.menu`).
    """
    (host if host is not None else st).button(
        "ℹ️ About",
        key="about_open",
        width="stretch",
        help="Version, authors, licence, and how to cite Scanpath Studio.",
        on_click=_arm_about,
    )


@st.dialog("ℹ️ About Scanpath Studio", width="large")
def _about_dialog() -> None:
    """The About modal: version, authors, links, citation, AI-assistance note."""
    from scanpath_studio import __version__

    # The button that opened this sits inside the ❓ Help popover, whose open
    # state is client-side — without this it floats on top of the modal.
    close_open_popovers()

    bibtex = (
        "@software{Shubi_Scanpath_Studio_2026,\n"
        "author = {Shubi, Omer and Gruteke Klein, Keren and Grossman, Maya and "
        "Lion, Ella and "
        'Jakobi, Deborah N. and Reich, David R. and J{\\"a}ger, Lena and '
        "Berzak, Yevgeni},\n"
        "license = {MIT},\n"
        "month = jun,\n"
        "title = {{Scanpath Studio}},\n"
        f"url = {{{CITATION['url']}}},\n"
        f"version = {{{__version__}}},\n"
        "year = {2026}\n"
        "}"
    )
    st.markdown(
        f"""
**Scanpath Studio** v{__version__} — interactive visualization of eye
movements in reading.

Developed by [Omer Shubi](https://omershubi.github.io/)¹,
[Keren Gruteke Klein](https://kerengruteke.github.io/)¹,
Maya Grossman¹,
[Ella Lion](https://ella-lion.github.io/)¹,
[Deborah N. Jakobi]({_DILI}/lab-members/jakobi.html)²,
[David R. Reich]({_DILI}/lab-members/reich.html)²,
[Lena Jäger]({_DILI}/group-leader/jaeger.html)², and
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/)¹.

¹ [Data and Decision Sciences]({CITATION["lab_url"]}), Technion ·
² [Department of Computational Linguistics](https://www.cl.uzh.ch/en/research-groups/digital-linguistics.html),
University of Zurich

📚 [Documentation]({CITATION["docs_url"]}) ↗ ·
💻 [Code]({CITATION["url"]}) ↗ (MIT)

🔒 [Privacy]({CITATION["docs_url"]}privacy/) ↗ — where your data goes (and doesn't)

🧪 [ACL 2025 Tutorial: Eye Tracking and NLP](https://acl2025-eyetracking-and-nlp.github.io/) ↗
"""
    )
    # UX-16: the BibTeX block is tall enough to push everything above it out
    # of view, so it opens on demand — but it stays a named section of its
    # own (divider + bold label) rather than a footnote, since "how do I cite
    # this?" is the single most common reason to open About.
    st.divider()
    st.markdown("**📖 Citing Scanpath Studio** — a paper is in preparation.")
    with st.expander("Show BibTeX", expanded=False):
        st.code(bibtex, language="bibtex", wrap_lines=True)
        st.markdown(
            """
If you use the bundled demo data, also cite
[OneStop Eye Movements](https://doi.org/10.1038/s41597-025-06272-2)
(Berzak et al., 2025, *Scientific Data*).
"""
        )
    # UX-20. A bare "built with AI, there may be bugs" is unfalsifiable, so
    # this points at what the reader can verify — not at how much effort went
    # in, which they have no way to check. Deliberately not a liability
    # disclaimer either: MIT already carries that.
    st.divider()
    st.markdown("**🤖 Built with AI assistance**")
    st.markdown(
        f"""
Scanpath Studio was built with AI assistance. Cross-check results before
publishing. If something looks wrong,
[open an issue]({CITATION["url"]}/issues) ↗ with your **💾 Session** JSON.
"""
    )


# --- Public-dataset access UI (directory + expected files + download) --------
# Shared by the per-corpus loaders below. Each corpus shows the on-disk layout
# it expects (so a user who already downloaded the data knows what to drop
# where) and a found-vs-missing status; downloadable corpora also get a Download
# button. The per-source participant/text narrowing was removed — every loader
# now reads the whole corpus and the global **Narrow by** trial filters scope it.

_POTEC_STRUCTURE_MD = """\
**Expected layout** — a clone of
[DiLi-Lab/PoTeC](https://github.com/DiLi-Lab/PoTeC) with its data files, or any
folder you let **Download** populate:
```
<dir>/
├─ eyetracking_data/
│  └─ scanpaths/              # per-trial fixation TSVs (or fixations/)
│     └─ *.tsv
└─ stimuli/
   ├─ word_aoi_texts/         # word boxes, one file per text
   │  └─ word_aoi_<text>.tsv   (texts b0–b5, p0–p5)
   └─ aoi_texts/              # character AOIs, one file per text
      └─ <text>.ias
```
"""

_MULTIPLEYE_STRUCTURE_MD = """\
**Expected layout** — a MultiplEYE session set (e.g. the read-only ZH-CH-Zurich
sample). Identity is read from the folder + file names, so there are no id
columns to map:
```
<dir>/
├─ scanpaths/                 # or fixations/
│  └─ <session>/              # one folder per reader session
│     └─ *.csv                 (one per stimulus page)
└─ stimuli_<lang>_<…>/
   ├─ aoi_stimuli_<…>/        # character AOIs: <stimulus>_aoi.csv
   ├─ config/config_*.py      # font size + family (optional)
   ├─ stimuli_images_<lang>_* # page images (optional)
   └─ …_comprehension_questions_*.xlsx   (optional)
```
`reading_measures/` and `participant_data.csv` (optional) enrich the load.
"""

_EYEGENBENCH_STRUCTURE_MD = """\
**Expected layout** — a bundle built by
`python scripts/prepare_eyegenbench.py --all` (or any subset of corpora). No
download here: build the bundle locally, then point this at where it wrote
the files.
```
<dir>/
├─ manifest.json              # one entry per prepared corpus
└─ <corpus name>/              # e.g. PoTeC, Provo, …
   ├─ words.parquet
   ├─ fixations.parquet
   └─ participants.parquet
```
"""


def _onestop_structure_md(regime: str, parts: list, variant: str) -> str:
    """Expected-files note for the OneStop public source (regime/parts/variant)."""
    from scanpath_studio import datasets

    lines = []
    for part in parts or ["Paragraph"]:
        for kind in ("ia", "fixations"):
            path = datasets._onestop_part_paths(
                Path("<dir>"), kind, regime, part, variant
            )
            lines.append(f"├─ {path.name}")
    listing = "\n".join(lines)
    if variant == "lacclab":
        return f"""\
**Expected files** — a LaCC lab OneStop export folder holding the chosen parts'
reports (per-part `ia_*` / `fixations_*` CSV.zip, no regime suffix). No download —
point at your local export:
```
<dir>/
{listing}
```
"""
    return f"""\
**Expected files** — the OSF reports for the chosen regime + parts, placed
directly in the folder (or fetched by **Download**). Only *Paragraph* is
regime-split on OSF; the other parts come from the all-regimes full release:
```
<dir>/
{listing}
```
Switch **Reading regime** / **Parts** above to load different ones (each is a
separate download).
"""


def _project_root() -> Path:
    """Repo/install root — the parent of the ``scanpath_studio`` package.

    Used to anchor the *relative* default data dirs (``data/OneStop`` etc.) and
    relative user-entered paths, so the "found vs. download" status resolves
    regardless of the process cwd (the server may run from anywhere). Computed
    from this module's location, not ``os.getcwd()``."""
    return Path(__file__).resolve().parent.parent


# DATA-16 (security audit S2). The corpus **Data directory** box takes a
# free-text path from the browser, stats it, reports the result back into the
# page, and — via ⬇ Download — writes into it. On a local run that's just a file
# picker. On anything another person can reach it's a path-existence oracle plus
# an arbitrary-directory write, and the app has no authentication on any
# deployment.
#
# Default is LOCAL, because that's how this is overwhelmingly run and flipping it
# would break every existing install on upgrade. A shared deployment sets
# `SCANPATH_LOCAL_FS=0`, which hides the path box, the folder picker and the
# download button; `SCANPATH_DATA_ROOT` then supplies the corpus location
# server-side. Setting `SCANPATH_DATA_ROOT` alone is also useful locally: it
# confines every entered path to that subtree.
LOCAL_FS_ENV = "SCANPATH_LOCAL_FS"
DATA_ROOT_ENV = "SCANPATH_DATA_ROOT"


def local_filesystem_enabled() -> bool:
    """Whether the user may point the app at an arbitrary local directory.

    True unless ``SCANPATH_LOCAL_FS`` is ``0`` / ``false`` / ``no``. Read at call
    time so tests can toggle it."""
    raw = os.environ.get(LOCAL_FS_ENV, "").strip().lower()
    return raw not in ("0", "false", "no")


def data_root() -> Path | None:
    """The configured allow-root for corpus paths, or ``None`` if unset."""
    raw = os.environ.get(DATA_ROOT_ENV, "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def _resolve_data_dir(root: str) -> str:
    """Resolve a possibly-relative data dir against the project root.

    Absolute paths (and ``~``) are used verbatim; a relative path is joined to
    the project root so it resolves no matter where the server was launched from
    (fixes the "No data found" false-negative when cwd != repo root). A blank
    stays blank (the loader then shows its missing-data note).

    When ``SCANPATH_DATA_ROOT`` is set, the result is confined to that subtree
    (S2): a path resolving outside it — including via ``..`` or a symlink, since
    the comparison is on the *resolved* path — collapses to the root itself
    rather than being passed through to a stat or a download."""
    text = (root or "").strip()
    if not text:
        return text
    expanded = Path(text).expanduser()
    # Unchanged when no allow-root is configured: absolute paths pass through
    # verbatim (resolving them would rewrite a symlinked data dir in the "Found
    # in `…`" line), relative ones anchor to the project root.
    literal = expanded if expanded.is_absolute() else (_project_root() / expanded)
    allow_root = data_root()
    if allow_root is None:
        return str(literal if expanded.is_absolute() else literal.resolve())
    # The containment test is on the *resolved* path, so `..` and symlinks are
    # caught rather than string-matched.
    if not literal.resolve().is_relative_to(allow_root):
        return str(allow_root)
    return str(literal)


def _pick_directory_dialog() -> str | None:
    """Open a native folder picker and return the chosen path, or None.

    Only works when the app runs on a machine with a display + tkinter (a
    locally-run app). Returns None — and never raises — on a headless host
    (Streamlit Cloud), a missing tkinter, or a cancelled dialog, so the text
    input stays the portable fallback.

    S2: refuses outright on a shared deployment. Degrading to None on a headless
    host was never the guarantee — on a host that *does* have a display, a remote
    visitor clicking 📁 pops a modal dialog on the server's own desktop and blocks
    the thread until someone there dismisses it."""
    if not local_filesystem_enabled():
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        chosen = filedialog.askdirectory()
        root.destroy()
    except Exception:
        return None
    return chosen or None


def _dataset_dir_input(
    cfg, *, default_dir: str, dir_help: str, structure_md: str, key_prefix: str
) -> str:
    """Data-location input + a native **Browse…** button + an Expected-files note.

    Returns the *resolved* directory (relative paths anchored to the project
    root, so the found/download status is correct regardless of cwd). A
    "📁 Browse…" button opens a native folder dialog when available (local app)
    and writes the pick back into the text input; it's silently skipped on a
    headless host, where the text box is the only control."""
    dir_key = f"{key_prefix}_dir"
    # S2: on a shared deployment the path box is a path-existence oracle, so it
    # isn't rendered at all — the location comes from the server's environment.
    if not local_filesystem_enabled():
        configured = str(data_root()) if data_root() else _resolve_data_dir(default_dir)
        cfg.caption(
            f"Reading from the server's configured data location: `{configured}`"
        )
        with cfg.expander("Expected files", expanded=False):
            st.markdown(structure_md)
        return configured
    # A prior Browse pick is applied before the widget instantiates (assigning a
    # widget-backed key inline after render is unreliable — see the source picker).
    picked = st.session_state.pop(f"{dir_key}_picked", None)
    if picked:
        st.session_state[dir_key] = picked
    text_col, browse_col = cfg.columns([4, 1])
    raw = text_col.text_input(
        "Data directory",
        value=st.session_state.get(dir_key, default_dir),
        help=dir_help,
        key=dir_key,
        # A typed path must survive a run in which this input doesn't render —
        # Streamlit drops an unrendered widget's key at end of run (BUG-15 /
        # ENG-36), and *every* one of these inputs renders only while its own
        # corpus is the selected source. The benchmark bootstrap entry made that
        # fatal (it vanishes the moment the path it was given succeeds, so the
        # path was lost and the corpora disappeared again on the next run — R39
        # shipped non-functional); for the other corpora it silently forgot a
        # hand-typed location as soon as the user looked at another source. One
        # rule here rather than one call site remembering and three forgetting.
        persist_state="session",
    )
    # Vertical-align the button with the input (past its label).
    browse_col.markdown("<div style='height:1.7em'></div>", unsafe_allow_html=True)
    if browse_col.button("📁", key=f"{key_prefix}_browse", help="Browse for a folder"):
        chosen = _pick_directory_dialog()
        if chosen:
            st.session_state[f"{dir_key}_picked"] = chosen
            st.rerun()
        else:
            cfg.caption("Folder picker unavailable here — type or paste the path.")
    with cfg.expander("Expected files", expanded=False):
        st.markdown(structure_md)
    return _resolve_data_dir(raw)


# UX-7(b): session slot describing a data source the user selected but that
# isn't available locally. Written by `_dataset_access_status` (and the bundle
# sources) on the run it happens, read + cleared by `_render_dataset_unavailable`
# in the main area. Kept out of the loader return value so the loaders can keep
# falling back to the demo corpus and the app stays usable.
_UNAVAILABLE_KEY = "_dataset_unavailable"


def _note_dataset_unavailable(
    *,
    label: str,
    reason: str,
    action: str,
    root: str | None = None,
    size_hint: str = "",
    download: Callable[[str], None] | None = None,
    key_prefix: str = "",
) -> None:
    """Record that ``label`` couldn't be loaded, for the main-area empty state."""
    st.session_state[_UNAVAILABLE_KEY] = dict(
        label=label,
        reason=reason,
        action=action,
        root=root,
        size_hint=size_hint,
        download=download,
        key_prefix=key_prefix,
    )


def _render_dataset_unavailable() -> None:
    """UX-7(b): a first-class "this corpus isn't here yet" state in the main area.

    Picking a download-on-demand corpus whose files aren't present used to change
    nothing visible except a line in the data-location panel — the loaders quietly
    fall back to the bundled demo, so the plot showed *demo* scanpaths as though
    the choice had taken effect. This names the dataset, says what's missing and how big the
    download is, offers the action inline, and states plainly that the demo is
    what's on screen meanwhile.
    """
    note = st.session_state.pop(_UNAVAILABLE_KEY, None)
    if not note:
        return
    download = note["download"]
    size = f" · {note['size_hint']}" if note["size_hint"] else ""
    # One panel, not four stacked blocks. The first version was an st.warning
    # banner + an st.caption + a body paragraph + a button — three type colours
    # and three background colours for what is a single message.
    with st.container(border=True, key="dataset_unavailable_panel"):
        st.markdown(
            f"#### 📦 {note['label']} isn't here yet\n"
            f"{note['reason'].rstrip('.')} — **showing the bundled demo corpus** "
            f"meanwhile."
        )
        details = [f"{note['action'].rstrip('.')}{size}"]
        if note["root"]:
            details.append(f"Looking in `{note['root']}`")
        st.markdown("\n".join(f"- {line}" for line in details))
        if download is None:
            return
        if st.button(
            "⬇ Download now",
            key=f"{note['key_prefix']}_download_main",
            type="primary",
        ):
            try:
                with st.spinner(f"Downloading into {note['root']} …"):
                    download(note["root"])
            except (OSError, ValueError) as exc:
                st.error(
                    f"Download failed: {exc}\n\nIf you're offline, download the "
                    "files on another machine and point the folder above at them."
                )
                return
            st.rerun()


def _dataset_access_status(
    cfg,
    *,
    root: str,
    present: bool,
    download: Callable[[str], None] | None = None,
    size_hint: str = "",
    key_prefix: str = "",
    label: str = "This dataset",
) -> bool:
    """Found / missing status + an optional **Download** button.

    Returns ``True`` when the corpus is present on disk (ready to load). When
    it's missing and ``download`` is given, renders a Download button that
    fetches the files then reruns — the next run loads from disk with no
    re-download (replaces the old always-on "Download if missing" checkbox, so
    an already-downloaded corpus never re-checks the network).

    A missing corpus is also recorded for the main-area empty state (UX-7): the
    data-location line alone is easy to miss when the plot keeps rendering demo
    data.
    """
    if present:
        cfg.success(f"Found in `{root}`")
        return True
    if download is None:
        cfg.warning(
            f"No data found in `{root}` — point at a folder with the files above."
        )
        _note_dataset_unavailable(
            label=label,
            reason="its files aren't in the folder you pointed at.",
            action="Set **Data location** on the 🗂️ Data page to a folder "
            "holding the files listed under **Expected files**.",
            root=root,
        )
        return False
    cfg.info(f"Not downloaded yet{f' ({size_hint})' if size_hint else ''}.")
    # S2: fetching writes tens-to-hundreds of MB into a browser-supplied path. On
    # a shared deployment that's a remote visitor filling the server's disk, so
    # the corpus has to be placed by whoever runs it.
    if not local_filesystem_enabled():
        cfg.caption(
            "Downloading is disabled on this deployment — ask whoever runs it to "
            "place the corpus in the configured data location."
        )
        _note_dataset_unavailable(
            label=label,
            reason="it isn't present in the server's data location.",
            action="This deployment can't fetch corpora itself — ask whoever runs "
            "it to place the files listed under **Expected files**",
            root=root,
        )
        return False
    _note_dataset_unavailable(
        label=label,
        reason="it hasn't been downloaded yet.",
        action="Fetch it once and it's cached on disk for every later load",
        root=root,
        size_hint=size_hint,
        download=download,
        key_prefix=key_prefix,
    )
    if cfg.button("⬇ Download", key=f"{key_prefix}_download", type="primary"):
        try:
            with st.spinner(f"Downloading into {root} …"):
                download(root)
        except (OSError, ValueError) as exc:
            cfg.error(f"Download failed: {exc}")
            return False
        st.rerun()
    return False


@st.cache_data(show_spinner="Loading PoTeC…")
def _cached_potec_raw_frames(root: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw PoTeC frames (pre-normalization) — the full corpus.

    Returns the same shape as an upload: raw frames the normal
    auto-detect → normalize → harmonize pipeline then handles. Cached on the
    directory so re-runs (toggling viz controls) don't re-read the files. Loads
    every reader × text (75 × 12); narrow the trial pool with **Narrow by**."""
    from scanpath_studio.datasets import potec_raw_frames

    return potec_raw_frames(root)


def _load_potec_source(
    options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the PoTeC corpus data source.

    PoTeC can't be loaded through the generic Upload flow (trial/word ids live
    in filenames, fixation coordinates come from a separate character-AoI
    file), so this dedicated source wraps ``datasets.potec_raw_frames``. The
    returned raw frames go through the same normalization as an upload, so the
    Column-mapping panels still appear and stay overridable. The whole
    corpus loads — narrow it with the **Narrow by** trial filters.

    ``options_host`` / ``location_host`` are the DATA-9 sub-slots; PoTeC
    has no source options, so only the data-location slot is used (defaults to a
    standalone expander when called without slots).
    """
    from scanpath_studio import datasets

    loc = location_host if location_host is not None else st.container()
    root = _dataset_dir_input(
        loc,
        default_dir=POTEC_DEFAULT_DIR,
        dir_help="Folder holding (or to download) the PoTeC files. A clone of "
        "github.com/DiLi-Lab/PoTeC works, or any empty folder with Download.",
        structure_md=_POTEC_STRUCTURE_MD,
        key_prefix="potec",
    )
    ready = _dataset_access_status(
        loc,
        root=root,
        present=datasets.potec_present(root),
        download=datasets.download_potec,
        size_hint="~45 MB",
        key_prefix="potec",
        label="PoTeC — Potsdam Textbook Corpus",
    )
    if not ready:
        return load_sample_data()
    try:
        return _cached_potec_raw_frames(root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        loc.error(f"Couldn't load PoTeC from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(show_spinner="Loading MultiplEYE…")
def _cached_multipleye_raw_frames(
    root: str, fixation_source: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw MultiplEYE frames (pre-normalization) — the full session set.

    Same shape as an upload — the normal auto-detect → normalize → harmonize
    pipeline then handles them — cached on the selection so re-runs (toggling
    viz controls) don't re-read the files. Loads every session × stimulus;
    narrow the trial pool with **Narrow by**."""
    from scanpath_studio.datasets import multipleye_raw_frames

    return multipleye_raw_frames(root, fixation_source=fixation_source)


@st.cache_data(show_spinner=False)
def _cached_multipleye_inventory(
    root: str, fixation_source: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from scanpath_studio.datasets import multipleye_inventory

    return multipleye_inventory(root, fixation_source=fixation_source)


def _load_multipleye_source(
    options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the MultiplEYE corpus data source.

    MultiplEYE can't be loaded through the generic Upload flow (participant /
    trial / stimulus live only in the folder + file names), so this dedicated
    source wraps ``datasets.multipleye_raw_frames``. The returned raw frames go
    through the same normalization as an upload, so the Column-mapping
    panels still appear and stay overridable. The whole session set loads —
    narrow it with the **Narrow by** trial filters.

    ``options_host`` / ``location_host`` are the DATA-9 sub-slots (the
    fixation-source radio above, the data location below); default to their own
    expanders when called standalone.
    """
    opt = options_host if options_host is not None else st.container()
    loc = location_host if location_host is not None else st.container()
    fixation_source = opt.radio(
        "Fixation source",
        options=["scanpaths", "fixations"],
        key="multipleye_fixation_source",
        help="scanpaths/ fixations are pre-tagged with page + word index "
        "(richer); fixations/ are raw onset/duration/x/y with no word linkage.",
    )
    root = _dataset_dir_input(
        loc,
        default_dir=MULTIPLEYE_DEFAULT_DIR,
        dir_help="Folder holding a MultiplEYE session set, e.g. the read-only "
        "ZH-CH-Zurich sample.",
        structure_md=_MULTIPLEYE_STRUCTURE_MD,
        key_prefix="multipleye",
    )
    try:
        sessions_all, _ = _cached_multipleye_inventory(root, fixation_source)
    except (FileNotFoundError, OSError):
        sessions_all = ()
    # MultiplEYE ships no public download URL — present means the local folder
    # holds a recognizable session set, otherwise fall back to the demo.
    ready = _dataset_access_status(
        loc,
        root=root,
        present=bool(sessions_all),
        key_prefix="multipleye",
        label="MultiplEYE — multilingual reading",
    )
    if not ready:
        return load_sample_data()
    try:
        return _cached_multipleye_raw_frames(root, fixation_source)
    except (FileNotFoundError, ValueError, OSError) as exc:
        loc.error(f"Couldn't load MultiplEYE from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(show_spinner="Loading OneStop…")
def _cached_onestop_raw_frames(
    root: str, regime: str, parts: tuple[str, ...], variant: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw OneStop frames (pre-normalization) for a regime + parts + variant.

    Cached on (root, regime, parts, variant) so toggling viz controls doesn't
    re-read the reports. The reports are present by the time this runs (the
    loader's Download button fetched them, or the lacclab export is local), so
    it never touches the network."""
    from scanpath_studio.datasets import onestop_raw_frames

    return onestop_raw_frames(root, regime=regime, parts=list(parts), variant=variant)


def _onestop_env_default_dir(variant: str) -> str:
    """Default OneStop data dir for a variant (env-overridable for the lacclab one)."""
    if variant == "lacclab":
        return os.environ.get("ONESTOP_LACCLAB_DIR", "").strip() or (
            ONESTOP_LACCLAB_DEFAULT_DIR
        )
    return ONESTOP_PUBLIC_DEFAULT_DIR


def _load_onestop_public_source(
    options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the OneStop corpus (OSF or LaCC lab).

    OneStop's interest-area + fixation reports share the bundled demo's schema
    across every trial part, so this fetches (public variant) or reads (lacclab
    variant) the chosen reading regime + parts and hands the raw frames to the
    normal normalization pipeline — the Column-mapping panels still appear and
    stay overridable. Distinct from the env-var "OneStop server bundle" source,
    which serves a lacclab export (and per-pid shards for deep links).

    ``options_host`` / ``location_host`` are the DATA-9 sub-slots (source
    options above, data location below); default to their own expanders so the
    loader still works standalone.
    """
    from scanpath_studio import datasets

    opt = options_host if options_host is not None else st.container()
    loc = location_host if location_host is not None else st.container()
    variant = opt.selectbox(
        "Variant",
        options=list(ONESTOP_VARIANT_LABELS),
        format_func=lambda v: ONESTOP_VARIANT_LABELS[v],
        key="onestop_variant",
        persist_state="session",
        help="Public downloads the reports from OSF on demand; LaCC lab reads a "
        "local lab-processed export (extra derived columns, no download).",
    )
    regime = opt.selectbox(
        "Reading regime",
        options=list(ONESTOP_REGIME_LABELS),
        format_func=lambda r: ONESTOP_REGIME_LABELS[r],
        key="onestop_regime",
        persist_state="session",
        help="Which OneStop reading regime to load. For the public variant each "
        "is a separate OSF download of the paragraph reports.",
    )
    # Seeded rather than `default=`-ed: a deep link seeds `onestop_parts`
    # pre-widget (`url_state._apply_url_preset`), and passing both makes
    # Streamlit warn about the collision (BUG-17). This picker renders only while
    # the OneStop public source is selected, so it can first mount on a later run —
    # `persist_state="session"` on the widget is what makes it come up carrying the
    # seeded/deep-linked value rather than empty (BUG-15 / ENG-36).
    _pin("onestop_parts", list(datasets.ONESTOP_DEFAULT_PARTS))
    parts = opt.multiselect(
        "Parts",
        options=list(ONESTOP_PART_LABELS),
        format_func=lambda p: ONESTOP_PART_LABELS[p],
        key="onestop_parts",
        persist_state="session",
        help="Which trial screens to load. Paragraph is the reading passage; the "
        "others are the surrounding screens (title / question / answers / "
        "feedback). Loading several makes each part its own trial.",
    )
    parts = parts or list(datasets.ONESTOP_DEFAULT_PARTS)
    default_dir = _onestop_env_default_dir(variant)
    root = _dataset_dir_input(
        loc,
        default_dir=default_dir,
        dir_help=(
            "Folder holding a LaCC lab OneStop export."
            if variant == "lacclab"
            else "Folder to download the OneStop reports into (cached on disk, "
            "so only the first load fetches them)."
        ),
        structure_md=_onestop_structure_md(regime, parts, variant),
        key_prefix=f"onestop_{variant}",
    )
    present = datasets.onestop_present(
        root, regime=regime, parts=parts, variant=variant
    )
    ready = _dataset_access_status(
        loc,
        root=root,
        present=present,
        # Only the public variant can download; the lacclab export is local.
        download=(
            (lambda r: datasets.download_onestop(r, regime=regime, parts=parts))
            if variant == "public"
            else None
        ),
        size_hint="OSF reports, tens–hundreds MB per part",
        key_prefix=f"onestop_{variant}",
        label=f"OneStop Eye Movements ({ONESTOP_VARIANT_LABELS[variant]})",
    )
    if not ready:
        return load_sample_data()
    try:
        return _cached_onestop_raw_frames(root, regime, tuple(parts), variant)
    except (FileNotFoundError, ValueError, OSError) as exc:
        loc.error(f"Couldn't load OneStop from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(show_spinner="Loading EyeGenBench…")
def _cached_eyegenbench_raw_frames(
    root: str, dataset: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw ``(words, fixations)`` for one EyeGenBench corpus.

    Cached on ``(root, dataset)`` so re-runs (toggling viz controls) don't
    re-read the Parquet files. Keyed on plain strings, not the manifest entry
    dict, so the cache survives an unrelated manifest re-read."""
    from scanpath_studio.eyegenbench import eyegenbench_raw_frames

    return eyegenbench_raw_frames(root, dataset=dataset)


# A malformed manifest (an entry with no `name`, a `datasets` value that isn't a
# list of objects) must degrade to "no corpora discovered", not crash the app:
# `KeyError` is in here because it escapes the usual IO triple and every
# discovery site reads entry keys (M7).
_MANIFEST_ERRORS = (FileNotFoundError, ValueError, OSError, KeyError)


@st.cache_data(show_spinner=False)
def _cached_eyegenbench_datasets(root: str) -> tuple:
    """Cached manifest entries for a bundle directory (M8).

    Discovery now runs on **every** picker build and every `compare_source`
    enumeration, once per corpus in the bundle — where the old single-source
    shape read the manifest only while that one source was selected. Same
    convention as `_cached_multipleye_inventory`: keyed on the resolved root, so
    pointing the directory input somewhere else busts it.
    """
    from scanpath_studio.eyegenbench import eyegenbench_datasets

    return tuple(eyegenbench_datasets(root))


def discovered_benchmark_datasets() -> tuple:
    """Manifest entries for the prepared bundle, or ``()`` when there is none.

    Never raises: the picker calls this while building its option list, long
    before anything is in a position to report a load failure to the user (the
    corpus' own loader does that, with the directory input right beside it).
    """
    from scanpath_studio.eyegenbench import entry_name

    try:
        entries = _cached_eyegenbench_datasets(_eyegenbench_root_from_state())
    except _MANIFEST_ERRORS:
        return ()
    # `entry_name` owns the "a row with no usable name is skipped" rule (N5);
    # spelling it again here is how the two would drift.
    return tuple(entry for entry in entries if entry_name(entry))


# geometry_source values are eyegenbench_geometry.py's GEOMETRY_REAL /
# _RECONSTRUCTED / _SYNTHESIZED (that module owns the tiering; not touched
# here). Surfaced on each corpus' entry so a user can tell which they're looking
# at rather than trusting a blanket claim in the description.
_EYEGENBENCH_GEOMETRY_BADGES = {
    "real": "✅ **Real** screen geometry — measured word boxes.",
    "reconstructed": "🛠️ **Reconstructed** geometry — no measured boxes for "
    "this corpus; derived from its documented display setup.",
    "synthesized": "🧪 **Synthesized** geometry — no measured boxes or "
    "documented display setup; a default layout was assumed.",
}


def _geometry_coverage_note(entry) -> str:
    """How much of a ``real`` corpus is actually measured, or ``""`` (R34).

    The single source for that qualifier: the badge and the picker description
    print it in the same panel, one line apart, so two spellings of the rule is
    how one of them ends up claiming uniform geometry the other has just denied
    (M8). Empty when the corpus is uniform, or when the tier is one that already
    says *no* measured boxes.

    ``n_texts`` is missing from no real manifest, but when it is the note goes
    vague rather than silent (M11): "some texts aren't measured" is worse copy
    than a count and a better claim than a confident, possibly-wrong "Real".

    The counts are read through `eyegenbench.entry_count`, which is also what
    keeps a hand-mangled manifest from raising out of the *picker build* — this
    runs for every discovered corpus via `_benchmark_description` (N1). An
    unreadable count lands in the same vaguer wording as an absent one: it is
    the R34-honest answer either way, and it is never worth taking the source
    list down over a typo in a number.
    """
    from scanpath_studio.eyegenbench import entry_count

    if str(entry.get("geometry_source") or "").strip() != "real":
        return ""
    missing = entry_count(entry, "paragraphs_without_real_boxes")
    if missing is not None and missing <= 0:
        return ""
    total = entry_count(entry, "n_texts")
    covered = (
        f"measured word boxes for {max(total - missing, 0)} of {total} texts"
        if missing is not None and total
        else "measured word boxes for some but not all texts"
    )
    return f"{covered}; the rest fall back to reconstructed layout"


def geometry_badge(entry) -> str:
    """The one-line geometry-provenance badge for a manifest entry (R34).

    `eyegenbench_geometry.py` promotes a whole corpus to ``real`` when **any**
    paragraph has measured word boxes — the scalar means *best tier achieved*,
    and it keeps that meaning (the per-word column already refines it, and
    changing it would ripple into the manifest contract, the CLI and the API).
    What must not happen is a *rendering* that implies uniformity: a corpus with
    one measured text in a thousand would otherwise read as "✅ Real — measured
    word boxes". So whenever ``paragraphs_without_real_boxes`` is non-zero the
    real badge says how many texts it actually covers, and plain "Real" is
    reserved for full coverage.

    The reconstructed / synthesized badges need no such qualifier: they already
    say *no* measured boxes, which is exactly what a non-zero count means there.
    """
    source = str(entry.get("geometry_source") or "").strip()
    if not source:
        return ""
    badge = _EYEGENBENCH_GEOMETRY_BADGES.get(source)
    if badge is None:
        return f"Screen geometry: {source}"
    if note := _geometry_coverage_note(entry):
        badge = f"✅ **Real** screen geometry — {note}."
    try:
        recorded_y = float(entry.get("recorded_fixation_y_fraction", 0.0))
    except (TypeError, ValueError):
        recorded_y = 0.0
    if recorded_y >= 0.9995:
        y_note = "Recorded fixation y."
    elif recorded_y > 0:
        y_note = (
            f"Recorded fixation y for {recorded_y:.0%}; other y positions use "
            "word-box centres."
        )
    else:
        y_note = "Fixation y uses word-box centres."
    return f"{badge} {y_note}"


def benchmark_corpus_label(name: str) -> str:
    """The registry key for a prepared corpus named ``name``."""
    return f"{name}{BENCHMARK_LABEL_SUFFIX}"


def picker_name_for(choice: str, registry: dict | None = None) -> str:
    """Exactly the name the **Data source** picker renders for ``choice``.

    Anything that tells a user to "select X" must quote this, not the registry
    key. The two differ: the picker shows the entry's `short`, and now a (WIP)
    marker on top of it, so the bootstrap entry's key reads *"Harmonised
    benchmark corpora — set up a local bundle"* while the list actually offers
    *"Harmonised benchmark corpora — set up (WIP)"*. A remedy naming a string
    that appears nowhere in the list is worse than no remedy — the reader hunts
    for it and concludes the app is broken.

    Pass ``registry`` when formatting a list of options: discovery depends on a
    directory the user can change, so one run must format every option against
    **one** snapshot (M6). Re-resolving per option lets an option's rendered text
    change underneath a widget mid-run, and Streamlit finds the selected value's
    formatted form no longer among its own options.
    """
    spec = (registry if registry is not None else public_dataset_registry()).get(choice)
    if spec is None:
        return choice
    name = str(spec.get("short") or choice)
    return f"{name}{BENCHMARK_WIP_SUFFIX}" if spec_is_benchmark(spec) else name


def mark_wip_if_benchmark(choice: str) -> str:
    """``choice`` with the (WIP) marker when it names a harmonised corpus.

    The marker has to reach **every** picker that offers these corpora, not just
    the data-source one: Comparisons' *Compare with* selectbox can load a corpus
    as scanpath B, and a user who only ever meets it there would publish a
    comparison against an unfinished feature without being told. Display-only in
    both places, and the same predicate decides both.
    """
    spec = public_dataset_registry().get(choice)
    return f"{choice}{BENCHMARK_WIP_SUFFIX}" if spec_is_benchmark(spec) else choice


def spec_is_benchmark(spec) -> bool:
    """True for a registry entry this feature owns: a prepared corpus or the
    bootstrap placeholder.

    Dispatches on the entry's own fields — `benchmark_dataset` (set by
    `_benchmark_registry_entries`) and `setup_only` — the same discriminator
    `compare_source.secondary_dataset_options` uses, and deliberately **not** on
    the label's text: PoTeC and OneStop each ship natively *and* harmonised, so a
    substring test on the label would sweep the native entries in too.
    """
    if not isinstance(spec, dict):
        return False
    return bool(spec.get("benchmark_dataset") or spec.get("setup_only"))


def _benchmark_short_name(name: str) -> str:
    """The picker's display name for a prepared corpus.

    PoTeC and OneStop ship **both** natively in this app and in the benchmark
    set, and the user wants both kept: the harmonised versions are what make
    cross-corpus comparison possible, which is the point of a harmonised suite.
    They are distinguished by the property that actually differs — one is the
    publisher's own release, the other a re-derived harmonisation — rather than
    by naming the pipeline (which is being extracted into its own repository, so
    anything user-visible carrying its name would need renaming later).

    The overlap is computed against the static built-ins rather than hard-coded,
    so adding a native corpus that a bundle also carries disambiguates itself.
    """
    natives = {
        str(spec.get("short") or "").lower()
        for spec in PUBLIC_DATASET_REGISTRY.values()
    }
    if name.lower() in natives:
        return f"{name}{BENCHMARK_SHORT_SUFFIX}"
    return name


def _benchmark_size_caption(entry) -> str:
    """``"84 readers · 55 texts · 219,556 fixations"`` from a manifest entry.

    Counts that don't parse are simply left out of the caption — via the same
    `entry_count` the geometry note reads, rather than a second hand-rolled
    ``try`` (N1).
    """
    from scanpath_studio.eyegenbench import entry_count

    parts = []
    for key, singular in (
        ("n_readers", "reader"),
        ("n_texts", "text"),
        ("n_fixations", "fixation"),
    ):
        if count := entry_count(entry, key):
            parts.append(f"{count:,} {singular}{'' if count == 1 else 's'}")
    return " · ".join(parts)


def _benchmark_description(entry, *, harmonised_overlap: bool) -> str:
    """The one-line description under a prepared corpus' picker entry.

    Carries the provenance ("EyeGenBench" belongs here, not in the label) and —
    for a corpus this app also ships natively — the fidelity difference, which is
    the whole reason both are offered.
    """
    from scanpath_studio.eyegenbench import entry_name

    name = entry_name(entry)
    lead = (
        f"{name}, re-derived by the EyeGenBench pipeline into the benchmark's "
        f"common schema — the same corpus as this app's own {name} entry, "
        "prepared for cross-corpus comparison rather than for the publisher's "
        "own geometry."
        if harmonised_overlap
        else f"{name} — a public reading corpus harmonised by the EyeGenBench "
        "pipeline to one common schema and prepared locally."
    )
    tail = []
    if source := str(entry.get("geometry_source") or "").strip():
        # Same qualifier as the badge rendered beside this (M8) — a bare
        # "Screen geometry: real" next to "measured word boxes for 9 of 12
        # texts" is the overclaim R34 exists to prevent, one line away from
        # the fix.
        note = _geometry_coverage_note(entry)
        tail.append(f"Screen geometry: {source}" + (f" — {note}" if note else ""))
    if license_ := str(entry.get("license") or "").strip():
        tail.append(f"License: {license_}")
    if citation := str(entry.get("citation") or "").strip():
        tail.append(citation)
    return lead + (" " + ". ".join(tail) + "." if tail else "")


def _benchmark_dir_input(loc) -> str:
    """The shared bundle-directory input, rendered by every benchmark entry.

    One session key (`eyegenbench_dir`) across all of them: the corpora live in
    one prepared bundle, so pointing any entry somewhere else moves them all —
    and it is what keeps the location changeable once the bootstrap entry has
    disappeared.
    """
    return _dataset_dir_input(
        loc,
        default_dir=EYEGENBENCH_DEFAULT_DIR,
        dir_help="Folder holding a prepared benchmark bundle. Build one with "
        "`python scripts/prepare_eyegenbench.py --all` — there is no download "
        "from here.",
        structure_md=_EYEGENBENCH_STRUCTURE_MD,
        key_prefix="eyegenbench",
    )


def _load_benchmark_setup_source(
    options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The bootstrap entry, offered only while **zero** corpora are discovered.

    Without it the setup is unreachable: discovery reads a directory the user can
    change at runtime, so a bundle at a non-default path yields no corpora, no
    entries — and therefore nowhere to type the path. This one placeholder
    renders the same directory input and *Expected files* note every corpus entry
    does, and disappears as soon as the manifest resolves.
    """
    opt = options_host if options_host is not None else st.container()
    loc = location_host if location_host is not None else st.container()
    root = _benchmark_dir_input(loc)
    _dataset_access_status(
        loc,
        root=root,
        present=False,
        key_prefix="eyegenbench",
        label="Harmonised benchmark corpora",
    )
    opt.info(
        "No prepared corpora found here yet. Build a bundle with "
        "`python scripts/prepare_eyegenbench.py --all`, then point the folder "
        "below at it — each prepared corpus then appears as its own data source."
    )
    return load_sample_data()


def _load_benchmark_source(
    options_host=None, location_host=None, *, dataset: str = ""
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Location controls + loader for **one** prepared benchmark corpus.

    A peer of `_load_potec_source` / `_load_multipleye_source`: one entry, one
    corpus, no sub-picker. The returned raw frames go through the same
    normalization as an upload, so the Column-mapping panels still appear.
    """
    from scanpath_studio.eyegenbench import entry_name, eyegenbench_present

    opt = options_host if options_host is not None else st.container()
    loc = location_host if location_host is not None else st.container()
    root = _benchmark_dir_input(loc)
    try:
        present = eyegenbench_present(root, dataset)
    except _MANIFEST_ERRORS:
        present = False
    ready = _dataset_access_status(
        loc,
        root=root,
        present=present,
        key_prefix="eyegenbench",
        # The name the picker shows for this corpus, not a hand-built one. The
        # "(harmonised benchmark)" suffix is added only when a native entry of
        # the same name exists (`_benchmark_short_name`), so hardcoding it here
        # made the empty-state call Provo "Provo (harmonised benchmark)" while
        # the picker called it "Provo (WIP)" — two names, neither matching.
        label=picker_name_for(benchmark_corpus_label(dataset)),
    )
    if not ready:
        return load_sample_data()
    entry = next(
        (e for e in discovered_benchmark_datasets() if entry_name(e) == dataset),
        None,
    )
    if entry and (badge := geometry_badge(entry)):
        opt.caption(badge)
    try:
        return _cached_eyegenbench_raw_frames(root, dataset)
    except _MANIFEST_ERRORS as exc:
        loc.error(f"Couldn't load '{dataset}' from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


# Registry behind the "Public datasets" source: label → loader (renders its own
# source options and returns raw, pre-normalization frames), the corpus'
# presentation-monitor size (canvas default for true-to-scale rendering; None to
# estimate from data extents), and a little presentation metadata (a short name
# for the picker, plus language / size / description / home link shown as a
# caption). To add a corpus: write a loader in datasets.py, wrap it in a
# `_load_*_source` function above, and add one entry here — the
# searchable picker scales as the catalogue grows.
PUBLIC_DATASET_REGISTRY: dict = {
    "PoTeC — Potsdam Textbook Corpus": dict(
        loader=_load_potec_source,
        monitor=(1680, 1050),  # DELL P2210
        short="PoTeC",
        language="German",
        size="75 readers · 12 texts",
        description="Potsdam Textbook Corpus — German reading of biology & "
        "physics textbook passages (expert/novice readers).",
        link="https://github.com/DiLi-Lab/PoTeC",
        # DATA-36: what the row shows before anyone opens it.
        published_counts={
            "Participants": 75,
            "Texts": 12,
            "Trials": 900,
            "Words": 142125,
            "Fixations": 404420,
        },
        published_counts_source=(
            "PoTeC's own README: 75 participants each reading all 12 texts, and "
            "“900 trials (75 participants * 12 trials)” in the data formats this "
            "loader reads. The word and fixation totals were measured from the "
            "released corpus with this app's loader — the fixation total agrees "
            "with the harmonised bundle's manifest to the row."
        ),
        # Word boxes come from the corpus' own `.ias` character files, but the
        # release discards the recorded screen (x, y) — `datasets._potec_fixations`
        # places each fixation at the centre of the character it names.
        geometry="🛠️ **Reconstructed** fixation coordinates — the release keeps "
        "no recorded (x, y), so each fixation sits at the centre of the "
        "character it names, from the corpus' own `.ias` boxes. The word boxes "
        "themselves are the corpus'.",
    ),
    "MultiplEYE — multilingual reading (ZH-CH sample)": dict(
        loader=_load_multipleye_source,
        monitor=(1920, 1080),  # MultiplEYE physical screen (coords offset to it)
        short="MultiplEYE",
        language="Multilingual (ZH-CH sample)",
        size="local session set",
        description="MultiplEYE multilingual eye-tracking-while-reading — the "
        "read-only Zurich Chinese sample, loaded from a local folder.",
        link="https://multipleye.eu/",
        # DATA-36: no published figures on purpose. This source reads whichever
        # session folders are on the machine it runs on, so there is no corpus-
        # wide number that would be true of the next person's copy — the row
        # fills in the moment it is opened, which is the honest answer.
        geometry="✅ **Real** — recorded fixation coordinates, with word boxes "
        "aggregated from the corpus' own character AOI files.",
    ),
    ONESTOP_PUBLIC_CHOICE: dict(
        loader=_load_onestop_public_source,
        # OneStop presentation monitor (full-screen px coords). Sourced in
        # `eyegenbench_geometry.DISPLAY_SPECS["onestop"]` — Berzak et al. 2025,
        # Sci Data 12:1995, Methods → Apparatus, which states the Dell U2715H
        # at 2560 px × 1440 px over a 597 mm × 336 mm display area.
        monitor=(2560, 1440),
        short="OneStop",
        language="English (L1)",
        # Verified against the OneStop docs (lacclab.github.io/OneStop-Eye-Movements
        # / Berzak et al. 2025): 360 participants, 30 Guardian articles = 162
        # paragraphs (each in Advanced + Elementary), ~19.4k regular trials.
        size="360 readers · 30 articles (162 paragraphs) · ~19.4k trials",
        description="OneStop Eye Movements — English L1 reading of Guardian "
        "articles across four regimes (ordinary / information-seeking, each also "
        "repeated) and seven trial parts (title / question / paragraph / answers "
        "/ feedback). Downloaded from OSF, or read from a LaCC lab export.",
        link="https://github.com/lacclab/OneStop-Eye-Movements",
        # DATA-36. **Texts** counts one paragraph at one difficulty level: the
        # composed `unique_paragraph_id` (BUG-43) makes Advanced and Elementary
        # two texts rather than two renderings of one, exactly as the bundled
        # demo's ids do. Before that fix `text_id` mapped to `paragraph_id` —
        # the index *within* an article — and the whole corpus read as seven
        # texts, which is why this figure was left unpublished until now.
        published_counts={
            "Participants": 360,
            "Texts": 330,
            "Trials": 24046,
            "Words": 2632159,
            "Fixations": 2400788,
        },
        published_counts_source=(
            "360 readers is the corpus' own figure (Berzak et al. 2025). The "
            "text, trial, word and fixation totals were measured from the public "
            "OSF release's Paragraph reports across all four regimes — one regime "
            "is what this source loads at a time, so a single load holds a "
            "fraction of them. 330 texts is 165 paragraphs at two difficulty "
            "levels, and matches the distinct `unique_paragraph_id` count in the "
            "lab export, which composes that id a different way."
        ),
        geometry="✅ **Real** — recorded fixation coordinates and EyeLink's own "
        "interest-area boxes (DATA-30 recovers the measured boxes from the raw "
        "export; DATA-31 keeps the recorded fixation y with them).",
    ),
}


#: The same presentation metadata for the sources that are **not** registry
#: entries — the packaged demo, the synthetic trial, the authoring canvas — so
#: the dataset table's ℹ️ dialog can answer the same questions about every row.
#: Uploads are absent on purpose: nothing here knows anything about them that
#: their own row does not already show.
_BUILTIN_DATASET_ABOUT: dict[str, dict] = {
    DEMO_CHOICE: dict(
        language="English (L1)",
        description="A packaged subset of OneStop Eye Movements, so the app has "
        "something real to open with. Regenerated by "
        "`python -m scanpath_studio.update_sample_data`.",
        link="https://github.com/lacclab/OneStop-Eye-Movements",
        # DATA-36: this corpus ships *inside* the package, so its figures are
        # checked against the files themselves — the DATA-36 tests recount
        # them, so regenerating the subset fails a test rather than quietly
        # leaving a stale number in the table.
        published_counts={
            "Participants": 3,
            "Texts": 12,
            "Trials": 36,
            "Words": 3922,
            "Fixations": 3209,
            "Gaze points": 2233,
        },
        published_counts_source=(
            "Counted from the files bundled with this release of the package."
        ),
        geometry="✅ **Real** — OneStop's recorded fixations and interest-area "
        "boxes. The raw-gaze overlay is the one exception: it is **synthesized** "
        "from the fixations, because OneStop publishes no raw samples.",
    ),
    ONESTOP_CHOICE: dict(
        language="English (L1)",
        description="OneStop Eye Movements, read from the lab export this "
        "machine points `$ONESTOP_DATA_DIR` at — the same corpus as the public "
        "source, in the lab's superset schema.",
        link="https://github.com/lacclab/OneStop-Eye-Movements",
        # DATA-36: seeded from the *public* release, because that is the only
        # figure that can be known before the export on this machine is read.
        # A lab export is a superset — it carries cohorts the public release
        # does not — so this row is the one where loading more than was
        # published is expected rather than alarming; the ⚠️ is then saying
        # "your export is bigger than the public corpus", which is true.
        published_counts={"Participants": 360},
        published_counts_source=(
            "The public release's own figure (Berzak et al. 2025). A lab export "
            "can hold more than the public corpus — the L2 cohort is not in the "
            "public release — so treat this as a floor until it is opened."
        ),
    ),
    SYNTHETIC_CHOICE: dict(
        language="English",
        description="A hand-built trial with every measure traced by hand — the "
        "same fixture the test suite asserts against. Use it to check what a "
        "measure or a plot option does against a known answer.",
        published_counts={
            "Participants": 1,
            "Texts": 1,
            "Trials": 1,
            "Words": 6,
            "Fixations": 9,
        },
        published_counts_source=(
            "The fixture's own specification — six words on two lines, nine "
            "fixations, one of them out of text (`synthetic.py`)."
        ),
        geometry="🧪 **Synthesized** — the layout and the fixations are both "
        "hand-specified, not recorded.",
    ),
    AUTHOR_CHOICE: dict(
        description="Type a text and place fixations on it yourself, for "
        "figures that illustrate a pattern rather than report a recording.",
        geometry="🧪 **Synthesized** — you draw it; the app lays the text out "
        "deterministically and marks the figure as an illustration.",
    ),
}


def dataset_about(token: str, registry: dict | None = None) -> dict:
    """What the dataset table knows about one row beyond its counts.

    One lookup for both halves of the catalogue — a public corpus' registry
    entry and the packaged sources' table above — so neither the row nor the
    ℹ️ dialog has to care which kind of row it was opened from. ``language``
    and ``link`` become cells; ``description`` and ``geometry`` are the two
    sentences the dialog shows. Returns ``{}`` for an upload, which is the
    honest answer: nothing here knows anything about it that its own row does
    not already show.
    """
    spec = (registry if registry is not None else public_dataset_registry()).get(token)
    if spec:
        # `published_counts` is a dict living in the registry, so it is copied
        # on the way out — everything else here is an immutable string, and a
        # caller that edited this one in place would be editing the catalogue.
        return {
            key: dict(spec[key]) if key == "published_counts" else spec[key]
            for key in (
                "language",
                "description",
                "link",
                "geometry",
                # DATA-36: the published figures ride this same lookup rather
                # than a second one, so a public corpus, a packaged source and a
                # prepared benchmark corpus all answer for themselves the same
                # way — and an upload answers `{}`.
                "published_counts",
                "published_counts_source",
            )
            if spec.get(key)
        }
    about = dict(_BUILTIN_DATASET_ABOUT.get(token) or {})
    if "published_counts" in about:
        about["published_counts"] = dict(about["published_counts"])
    return about


def _benchmark_registry_entries() -> dict:
    """One registry entry per prepared benchmark corpus (R36).

    Built from the local bundle's manifest, so it varies with the directory the
    user points at — which is why the registry as a whole had to become a
    function. Each entry has the same shape as the static built-ins above
    (`short` / `language` / `size` / `description` / `link` / `monitor`) and is
    presented identically: one 🌐 entry in the flat picker, nothing nested.

    ``monitor`` is **omitted** when the manifest's ``monitor_source`` is
    ``default`` — that value is `eyegenbench_geometry.py`'s generic guess for a
    corpus that documents no screen, and declaring it here would make the canvas
    snap to it as though it were measured (the registry has no "declared but not
    authoritative" tier — a declared monitor *is* the authoritative one). Without
    it the canvas falls back to data extents, which is the honest answer. The
    condition itself is `eyegenbench.declared_monitor`, which the CLI reads too.
    """
    from scanpath_studio.eyegenbench import declared_monitor, entry_name

    entries: dict = {}
    for entry in discovered_benchmark_datasets():
        name = entry_name(entry)
        short = _benchmark_short_name(name)
        spec = dict(
            loader=partial(_load_benchmark_source, dataset=name),
            short=short,
            language=language_display(entry.get("language")),
            size=_benchmark_size_caption(entry),
            description=_benchmark_description(entry, harmonised_overlap=short != name),
            # R34's badge, resolved once here rather than only inside the loader,
            # so the dataset table's ℹ️ dialog can show it without opening the
            # corpus.
            geometry=geometry_badge(entry),
            link="https://github.com/EyeBench/EyeGenBench",
            # DATA-36: the manifest already counts each corpus, so a prepared
            # row arrives with its figures — the same numbers `size` renders as
            # a caption, one column each.
            published_counts=benchmark_published_counts(entry),
            published_counts_source=(
                "The prepared bundle's own manifest, written when the corpus "
                "was prepared. Its readers and fixations are counted from what "
                "was actually written; its texts count distinct texts, so a "
                "corpus with repeated readings publishes fewer texts than the "
                "app counts reading instances."
            ),
            # Marks the entry as coming from a prepared bundle, and names the
            # corpus inside it. `compare_source` dispatches on this rather than
            # sniffing the label, and it is the natural slug for Task 12's wire
            # format.
            benchmark_dataset=name,
        )
        # The one screen-honesty rule, shared with the CLI (`cli.render
        # --eyegenbench`) so the same corpus can't render at an invented
        # 1920×1080 on one surface and at data extents on the other — I3.
        if monitor := declared_monitor(entry):
            spec["monitor"] = monitor
        entries[benchmark_corpus_label(name)] = spec
    return entries


def public_dataset_registry() -> dict:
    """Every public corpus on offer: the static built-ins ∪ discovered corpora.

    `PUBLIC_DATASET_REGISTRY` stays the literal home of the three built-ins, whose
    entries are fixed at import time. The prepared benchmark corpora can't be:
    they depend on a bundle directory the user can change mid-session, so they
    are composed in here and every consumer calls this instead of reading the
    dict. Discovery is cached (`_cached_eyegenbench_datasets`), so calling it
    several times a run costs one manifest read.
    """
    registry = dict(PUBLIC_DATASET_REGISTRY)
    discovered = _benchmark_registry_entries()
    registry.update(discovered)
    if not discovered:
        # R39: with nothing discovered there is no entry, so there would be
        # nowhere to type the bundle's path. Exactly one placeholder carries the
        # directory input until a corpus exists.
        registry[BENCHMARK_SETUP_CHOICE] = dict(
            loader=_load_benchmark_setup_source,
            short="Harmonised benchmark corpora — set up",
            language="Multilingual",
            size="not set up yet",
            description="Public reading corpora harmonised to one schema by the "
            "EyeGenBench pipeline. Build a bundle locally and point this at it; "
            "each prepared corpus then appears as its own data source.",
            link="https://github.com/EyeBench/EyeGenBench",
            setup_only=True,
        )
    return registry


def _load_public_dataset(
    description_host=None, options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dispatch for a "Public datasets" source.

    The corpus is chosen in the flat source picker (DATA-9) and rides
    ``public_dataset_choice``. The selected corpus' compact language · size
    caption, one-line description, and home link render into
    ``description_host``; the loader's source options + data-location controls
    render into ``options_host`` / ``location_host`` (the DATA-9 ordered group).
    Returns raw, pre-normalization frames.
    """
    registry = public_dataset_registry()
    chosen = st.session_state.get("public_dataset_choice")
    if chosen not in registry:
        chosen = next(iter(registry))
        st.session_state["public_dataset_choice"] = chosen
    spec = registry[chosen]
    desc = description_host if description_host is not None else st.container()
    facts = " · ".join(f for f in (spec.get("language"), spec.get("size")) if f)
    if facts:
        desc.caption(facts)
    if spec.get("description"):
        desc.caption(spec["description"])
    if spec.get("link"):
        desc.markdown(f"[Dataset home ↗]({spec['link']})")
    return spec["loader"](options_host, location_host)


def _public_dataset_monitor(data_choice: str) -> tuple[int, int] | None:
    """The selected public corpus' real monitor size, or None.

    None when another data source is active, or when the selected dataset
    doesn't declare a monitor (canvas then defaults to data extents)."""
    if data_choice != PUBLIC_DATASETS_CHOICE:
        return None
    spec = public_dataset_registry().get(
        st.session_state.get("public_dataset_choice", "")
    )
    return spec.get("monitor") if spec else None


def _eyegenbench_root_from_state() -> str:
    """The prepared-bundle directory the picker is currently pointed at.

    Mirrors `_dataset_dir_input`'s own resolution (the S2 branch included) so
    discovery agrees with what a corpus' loader reads later in the same run,
    without threading the resolved root through session state as a second copy
    of the truth."""
    if not local_filesystem_enabled():
        return (
            str(data_root())
            if data_root()
            else _resolve_data_dir(EYEGENBENCH_DEFAULT_DIR)
        )
    return _resolve_data_dir(
        st.session_state.get("eyegenbench_dir", EYEGENBENCH_DEFAULT_DIR)
    )


def _dataset_font(words: pd.DataFrame) -> tuple[float | None, str | None]:
    """The stimulus typeface ``(font_px, css_family)`` a dataset declares, or
    ``(None, None)``.

    MultiplEYE stamps ``stimulus_font_px`` / ``stimulus_font_family`` (the real
    ``FONT_SIZE`` + font from its stimulus config) onto every word; the app snaps
    its font controls to them so the reading text matches the stimulus exactly."""
    if words is None or words.empty or "stimulus_font_px" not in words.columns:
        return None, None
    px = pd.to_numeric(words["stimulus_font_px"], errors="coerce").dropna()
    if px.empty:
        return None, None
    family = None
    if "stimulus_font_family" in words.columns:
        fams = words["stimulus_font_family"].dropna().astype(str)
        fams = fams[fams.str.strip() != ""]
        family = fams.iloc[0] if not fams.empty else None
    return float(px.iloc[0]), family


def _stimulus_font_install_hint(css_family: str | None) -> tuple[str, str] | None:
    """``(primary font name, download URL)`` for a stimulus font's CSS stack.

    The overlaid reading text only matches the stimulus image when the exact
    experiment font is installed (we don't bundle it) — the browser otherwise
    falls back per-script, so CJK lands but the half-width Latin in a CJK font
    drifts (URLs/digits render too wide). Returns the human-readable family name
    (first quoted entry of the stack) + a best-effort download link, or None when
    the stack names no specific (quoted) family — a bare CSS generic like
    ``monospace`` has nothing to install."""
    if not css_family:
        return None
    match = re.search(r"'([^']+)'", css_family)
    if match is None:
        return None
    name = match.group(1)
    # Best-effort source: the experiment fonts are from Google's Noto project.
    url = (
        "https://github.com/notofonts/noto-cjk"
        if "cjk" in name.lower() or "noto" in name.lower()
        else f"https://fonts.google.com/?query={name.replace(' ', '+')}"
    )
    return name, url


@st.cache_data(show_spinner=False)
def _cached_trial_identity_report(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key, sample_trials=None
) -> dict:
    """VAL-7's diagnosis, memoized on the two frames' fingerprints.

    It groups the whole corpus by trial several times over, so it must not run
    on every rerun — but it also must not be skipped, since the failure it
    catches is invisible in the figure. PERF-6: on a corpus larger than
    ``sample_trials`` it screens a deterministic sample instead (4.23 s → 1.15 s
    on full OneStop); the 🗂️ Data page's *Check every trial* button asks for the
    census by passing ``None``, and lands on its own cache entry.
    """
    return diagnose_trial_identity(_words, _fixations, sample_trials=sample_trials)


@st.cache_data(show_spinner="Loading MultiplEYE server bundle…")
def _cached_multipleye_server_bundle(
    participant: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_multipleye_server_bundle(participant)


def load_words_and_fixations(
    data_choice: str,
    participant: str | None = None,
    *,
    description_host=None,
    options_host=None,
    location_host=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw word + fixation frames for the **non-upload** data sources.

    The Upload source is handled separately by the setup wizard
    (``_render_data_setup``), which groups each table's upload box with its
    mapping; this covers the bundled demo, synthetic trial, public datasets, and
    the OneStop server bundle.

    ``description_host`` / ``options_host`` / ``location_host`` are the DATA-9
    sub-slots a public dataset's caption / source options / data-location
    controls render into (ignored by the other sources).

    Args:
        data_choice: ``DEMO_CHOICE`` ("Bundled Demo") / ``SYNTHETIC_CHOICE`` /
            ``PUBLIC_DATASETS_CHOICE`` / ``ONESTOP_CHOICE`` /
            ``MULTIPLEYE_BUNDLE_CHOICE``. The Upload source and stored uploaded
            datasets are handled by ``main`` directly, not here.
        participant: Lowercased participant_id from the URL deep link. When set
            AND `data_choice` is ``ONESTOP_CHOICE`` / ``MULTIPLEYE_BUNDLE_CHOICE``,
            the loader fast-paths to just that pid's shard/session — sub-second
            instead of loading the whole corpus. Ignored for the other sources.

    Returns:
        Tuple of (words_df, fixations_df) as raw DataFrames before normalization.
    """
    if data_choice == SYNTHETIC_CHOICE:
        from scanpath_studio.synthetic import load_synthetic_data

        return load_synthetic_data()
    if data_choice == PUBLIC_DATASETS_CHOICE:
        return _load_public_dataset(description_host, options_host, location_host)
    # The Upload source is handled separately by the setup wizard
    # (`_render_data_setup`), which renders each table's upload + mapping; see main().
    if data_choice == ONESTOP_CHOICE:
        words, fixations = load_onestop_server_bundle(participant=participant)
        if words.empty or fixations.empty:
            _note_dataset_unavailable(
                label="OneStop server bundle",
                reason=(
                    "`$ONESTOP_DATA_DIR` isn't set."
                    if onestop_data_dir() is None
                    else "the export files aren't in `$ONESTOP_DATA_DIR`."
                ),
                action="Point the `ONESTOP_DATA_DIR` environment variable at a "
                "OneStop export folder and restart the app, or pick **Public "
                "datasets → OneStop** to download the reports instead.",
                root=str(onestop_data_dir() or ""),
            )
            return load_sample_data()
        return words, fixations
    if data_choice == MULTIPLEYE_BUNDLE_CHOICE:
        try:
            words, fixations = _cached_multipleye_server_bundle(participant=participant)
        except (FileNotFoundError, ValueError, OSError) as exc:
            st.error(f"Couldn't load the MultiplEYE bundle: {exc}")
            st.stop()
        if words.empty or fixations.empty:
            _note_dataset_unavailable(
                label="MultiplEYE bundle",
                reason="its session folders weren't found.",
                action="Point `MULTIPLEYE_DATA_DIR` at a MultiplEYE session set "
                "and restart the app, or load it from **Public datasets → "
                "MultiplEYE**.",
                root=str(multipleye_bundle_dir() or ""),
            )
            return load_sample_data()
        return words, fixations
    return load_sample_data()


def _schema_key(schema: dict | None) -> tuple | None:
    """Hashable, stable representation of a column-mapping schema dict.

    Values may be strings, ``None``, or a list of column names (composite trial
    id). Used as part of the normalization cache key so an override that changes
    the mapping (without changing the raw frame) correctly busts the cache.
    """
    if schema is None:
        return None
    return tuple(
        (k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(schema.items())
    )


def _normalize_pair_uncached(
    _words_df: pd.DataFrame,
    _word_schema: dict | None,
    _fixations_df: pd.DataFrame,
    _fix_schema: dict | None,
    cache_key,
    _keep_words: set | None = None,
    _keep_fix: set | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pure normalize + harmonize, cached on a cheap fingerprint of the inputs.

    ``cache_key`` carries a ``frame_fingerprint`` + schema signature + the
    keep-column selection, so a trial change (which re-runs the script but feeds
    byte-identical raw frames) hits the cache and skips re-normalizing the whole
    corpus, while changing the kept columns correctly busts it.

    PERF-6: deliberately **not** ``@st.cache_data``. That would store a copy of
    its own and hand out another on every hit, so the frames would sit in memory
    twice — measured at ~1.2 GB of avoidable resident memory at OneStop scale,
    against the 0.69 s per rerun the copy was costing. `frame_cache` keeps
    exactly one, which is why `clear_computation_cache` clears it too.
    """
    # UX-37: logged because a cache *miss* is exactly what a "why was that slow?"
    # question is about, and a hit is silent — the line only appears when the
    # work actually ran.
    with timed(
        "normalize + harmonize (cache miss)",
        word_rows=len(_words_df),
        fixation_rows=len(_fixations_df),
    ):
        words_norm = (
            normalize_words(_words_df, _word_schema, keep_columns=_keep_words)
            if _word_schema is not None
            else empty_words_frame()
        )
        fixations_norm = (
            normalize_fixations(_fixations_df, _fix_schema, keep_columns=_keep_fix)
            if _fix_schema is not None
            else empty_fixations_frame()
        )
        return harmonize_frames(words_norm, fixations_norm)


def _normalize_pair(
    words_df: pd.DataFrame,
    word_schema: dict | None,
    fixations_df: pd.DataFrame,
    fix_schema: dict | None,
    keep_words: set | None = None,
    keep_fix: set | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize a *validated* (words, fixations) pair to canonical columns and
    run the cross-frame fixups (``harmonize_frames``).

    A ``None`` schema means that table is absent (single-report dataset) → a
    canonical empty frame. Records the composite-trial component columns (when
    the trial id is built from several columns) so the trial picker can offer one
    cascading selector per component. Shared by the upload and non-upload paths.

    The heavy normalization is delegated to the cached ``_normalize_pair_cached``
    so it doesn't re-run on every rerun (e.g. selecting a different trial); only
    the lightweight session-state bookkeeping below runs each time.
    """
    trial_mapping = (word_schema or fix_schema)["trial"]
    trial_cols = trial_mapping_columns(trial_mapping)
    st.session_state["_composite_trial_columns"] = (
        trial_cols if len(trial_cols) > 1 else None
    )
    cache_key = (
        frame_fingerprint(words_df),
        _schema_key(word_schema),
        frame_fingerprint(fixations_df),
        _schema_key(fix_schema),
        tuple(sorted(keep_words)) if keep_words is not None else None,
        tuple(sorted(keep_fix)) if keep_fix is not None else None,
    )
    # PERF-6: the normalized frames are cached *only* here. `st.cache_data`
    # hands back a deep copy on every hit — ~0.69 s and ~0.7 GB of churn per
    # rerun at OneStop scale, for frames the app already has and never writes to
    # (audited by tests/test_frame_immutability.py) — and keeping both caches
    # would hold two copies of the corpus at rest, which is the worse of the two
    # costs. `frame_cache` keeps one and returns the object itself.
    # PERF-6: the spinner says how much data is being normalized, because on a
    # real corpus this is a ~20 s wait and "Normalizing data…" gives no sense of
    # whether that is expected. `show_spinner=False` on the cached function, so
    # there is one spinner rather than two nested ones.
    notice = st.spinner(
        f"Normalizing {len(words_df):,} word rows and {len(fixations_df):,} fixations…"
    )
    return frame_cache(
        "normalized_pair",
        cache_key,
        lambda: _with_spinner(
            notice,
            _normalize_pair_uncached,
            words_df,
            word_schema,
            fixations_df,
            fix_schema,
            cache_key,
            _keep_words=keep_words,
            _keep_fix=keep_fix,
        ),
    )


def _with_spinner(notice, func, *args, **kwargs):
    """Run ``func`` under ``notice``, so the spinner only shows on real work.

    The message is built before the cache lookup (it needs the input sizes), but
    must not *render* on a cache hit — a spinner that flashes on every rerun is
    noise. Entering the context here means it opens only when the work actually
    runs.
    """
    with notice:
        return func(*args, **kwargs)


def _reset_active_mapping() -> None:
    """Clear the stashed column mapping at the start of each data load, so a new
    source doesn't inherit the previous one's mapping in the Data Inspection tab."""
    st.session_state["_active_column_mapping"] = {}


def _stash_active_mapping(table: str, schema: dict | None) -> None:
    """Record the schema (field → source column) actually used for ``table`` so
    ``tabs.render_data_inspection_tab`` can show how columns were mapped. ``table``
    is one of ``"words" / "fixations" / "raw_gaze"``."""
    mapping = st.session_state.setdefault("_active_column_mapping", {})
    mapping[table] = dict(schema) if schema else None


#: Lead of the ``problems`` entry a **rejected** mapping produces, as opposed to
#: an **incomplete** one. ``_render_unmapped_view`` branches on it to say the
#: right thing, so keep the two in step.
MAPPING_FAILURE_LEAD = "This column mapping doesn't work with this data"


def mapping_failure_problem(exc: Exception) -> str:
    """Turn a normalization failure into one more recovery ``problems`` entry.

    Everything the normalize → harmonize pipeline raises is a statement about
    the column mapping in force — a ``multipart`` identity rule (screen id in
    only one report, orphan screens, a conflicting canvas), a non-numeric
    coordinate column, a duplicated trial key. None of them is a reason to stop
    rendering, and letting one propagate is actively a trap: the panels that
    would fix the mapping are written *during* the run that dies, and the Data
    page they live on is hidden while another view is active — so the user is
    left with a traceback and nothing to click, which is how the app used to
    wedge on a mapping it had auto-detected itself.

    The exception is logged with its traceback (🐛 Debug panel + terminal) and
    handed back as a string, so the existing incomplete-mapping recovery path —
    raw tables, still-editable mapping panels, off-page signpost — carries it.
    """
    logging.getLogger("scanpath_studio").exception(
        "Normalizing with the current column mapping failed."
    )
    return f"{MAPPING_FAILURE_LEAD}: {exc}"


def reset_column_mapping() -> None:
    """Drop every ``col_map_*`` key, so the mapping falls back to auto-detection.

    Used both when the monitor-defining source changes (a mapping is keyed to
    the columns it was made for) and as the escape hatch under a rejected
    mapping. Safe from an ``on_click`` callback: it runs before the script that
    re-creates the widgets.
    """
    for key in [
        k
        for k in list(st.session_state)
        if isinstance(k, str) and k.startswith(COLUMN_MAPPING_PREFIX)
    ]:
        del st.session_state[key]


#: Label + tooltip of the "known-good state" button, shared by the off-page
#: signpost and the 💾 Session menu so the two read as the same action.
DEMO_RESET_LABEL = "🧪 Load the bundled demo"
DEMO_RESET_HELP = (
    "Switches to the demo corpus and re-detects its column mapping. Your "
    "uploaded datasets stay in the source list."
)


def load_bundled_demo() -> None:
    """``on_click``: return to the bundled demo with a freshly detected mapping.

    The one button that reaches a known-good state from anywhere, for a session
    wedged on a dataset it cannot normalize. Three things together, because any
    two of them leave a way to stay stuck: the source switch (through the
    pre-widget ``_pending_source_choice`` seam — assigning the picker's value
    inline is reconciled away by the browser), leaving the wizard the way its
    own ✕ Cancel does, and dropping the column mapping — which a source *change*
    already does, but the wedged source is often the demo itself, and then
    nothing would change without this.
    """
    st.session_state["_pending_source_choice"] = DEMO_CHOICE
    st.session_state["_show_upload_wizard"] = False
    st.session_state["setup_complete"] = True
    st.session_state.pop(WIZARD_LEAVE_KEY, None)
    st.session_state.pop(WIZARD_STAY_KEY, None)
    reset_column_mapping()


def clear_computation_cache() -> None:
    """``on_click``: drop every ``@st.cache_data`` entry for this process.

    Used after deleting a dataset so derived values cannot retain its frames.
    It does not touch the recovery cache or live session state, except for
    DATA-32's remembered dataset counts, which are derived too.
    """
    st.cache_data.clear()
    # PERF-6: the normalized frames live in `frame_cache`, not `st.cache_data`,
    # so clearing only the latter would leave the deleted dataset's frames
    # behind — which is exactly what this function exists to prevent.
    clear_frame_cache()
    forget_dataset_counts()


def _apply_declared_schema(proposed: dict, declared: dict | None) -> dict:
    """Auto-detection, overridden by whatever the source *declares* it knows.

    Auto-detection guesses a mapping from column names, which is right for an
    upload and wrong for a corpus whose schema is a published contract. The
    declared mapping wins for every field it names — including a field it names
    as ``None``, which is a positive statement that the source has no such
    column and is what clears a leftover the detector would otherwise seize on.
    Fields the source says nothing about keep their detected value, so optional
    passthroughs (linguistic features, EyeLink measures) still arrive.
    """
    if not declared:
        return proposed
    return {**proposed, **declared}


def declared_schemas_for(data_choice: str) -> tuple[dict | None, dict | None]:
    """The ``(word, fix)`` schemas the selected source publishes, or ``(None, None)``.

    A prepared benchmark corpus has a **known** schema — the prep script wrote
    it — and every other surface already loads one through it
    (`eyegenbench.load_eyegenbench`, so `render --eyegenbench`, the headless API
    and Comparisons' dataset B all agree). The app was the one surface that
    re-guessed instead, and the guess is wrong on real bundles: the prepared
    frames carry the publisher's ~190 leftover columns through, so EMTeC's
    fixations detect `trial="TRIAL_ID"` against the words' `unique_paragraph_id`
    and broadcast **zero** word boxes — silently, since only the words frame
    ends up empty and the empty-pool guard never fires.
    """
    if data_choice != PUBLIC_DATASETS_CHOICE:
        return None, None
    spec = public_dataset_registry().get(
        st.session_state.get("public_dataset_choice", "")
    )
    if not spec or not spec.get("benchmark_dataset"):
        return None, None
    from scanpath_studio.eyegenbench import (
        EYEGENBENCH_FIX_SCHEMA,
        EYEGENBENCH_WORD_SCHEMA,
    )

    return dict(EYEGENBENCH_WORD_SCHEMA), dict(EYEGENBENCH_FIX_SCHEMA)


def prepare_data(
    words_df: pd.DataFrame,
    fixations_df: pd.DataFrame,
    allow_override: bool,
    mapping_host=None,
    declared_word_schema: dict | None = None,
    declared_fix_schema: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Infer schemas and normalize incoming dataframes to canonical column names.

    When ``allow_override`` is True, render the mapping expanders that let the
    user pick the exact column names for each field (pre-filled with auto-detection).
    Otherwise just auto-detect.

    Returns ``(words_norm, fixations_norm, problems)``. ``problems`` is a list
    of human-readable strings; when it's non-empty the column mapping isn't
    usable yet (a required field is unmapped) — the normalized frames come back
    empty and the caller shows the raw uploaded data so the user can pick the
    right columns instead of the whole app halting (which used to hide the very
    data needed to decide the mapping).

    Either frame may arrive empty (single-report datasets: only an IA report,
    or only a fixation report) — the missing side becomes a canonical empty
    frame and its mapping UI is skipped. Cross-frame fixups (stimulus-level
    words broadcast across participants, AOI-only fixations placed at word-box
    centers) run at the end via ``harmonize_frames``.
    """
    has_words = not words_df.empty
    has_fixations = not fixations_df.empty
    word_schema = None
    fix_schema = None
    problems: list = []

    if has_words:
        word_proposed = _apply_declared_schema(
            propose_word_schema(words_df), declared_word_schema
        )
        if allow_override:
            word_schema = column_mapping_ui(
                words_df,
                table_label="Words/IA",
                state_key_prefix="col_map_words",
                field_specs=WORD_FIELD_SPECS,
                proposed=word_proposed,
                problems=validate_word_schema(word_proposed),
                container=mapping_host,
                # The host is the ⚙️ Configure menu popover, which nests no
                # expander — render the panel inline with its own bold header.
                use_expander=False,
                # Match the add-dataset screen's compact field grid instead of
                # stretching every mapping across a full row.
                columns_per_row=4,
                stack_labels=True,
            )
        else:
            word_schema = word_proposed
        word_problems = validate_word_schema(word_schema)
        if word_problems:
            problems.append("Words/IA: " + "; ".join(word_problems))

    if has_fixations:
        fix_proposed = _apply_declared_schema(
            propose_fix_schema(fixations_df), declared_fix_schema
        )
        if allow_override:
            fix_schema = column_mapping_ui(
                fixations_df,
                table_label="Fixations",
                state_key_prefix="col_map_fix",
                field_specs=FIX_FIELD_SPECS,
                proposed=fix_proposed,
                problems=validate_fix_schema(fix_proposed),
                container=mapping_host,
                use_expander=False,
                columns_per_row=4,
                stack_labels=True,
            )
        else:
            fix_schema = fix_proposed
        fix_problems = validate_fix_schema(fix_schema)
        if fix_problems:
            problems.append("Fixations: " + "; ".join(fix_problems))

    if problems:
        # Mapping not ready — let the caller surface the raw data instead of
        # plotting. Clear any stale composite-trial state so the picker doesn't
        # reference columns from a previous, valid dataset.
        st.session_state["_composite_trial_columns"] = None
        return empty_words_frame(), empty_fixations_frame(), problems

    # Record the mapping actually used so the Data Inspection tab can show it.
    _stash_active_mapping("words", word_schema if has_words else None)
    _stash_active_mapping("fixations", fix_schema if has_fixations else None)

    try:
        words_norm, fixations_norm = _normalize_pair(
            words_df, word_schema, fixations_df, fix_schema
        )
    except Exception as exc:
        # A mapping the pipeline *rejects* recovers the same way as one that is
        # merely incomplete. See `mapping_failure_problem`.
        st.session_state["_composite_trial_columns"] = None
        return (
            empty_words_frame(),
            empty_fixations_frame(),
            [mapping_failure_problem(exc)],
        )
    return words_norm, fixations_norm, problems


# Labels of the top-level tab strip, shared by the real tabs, the
# unmapped-data placeholder view, and the tab-persistence script so they can't
# drift apart.
# Bulk export is no longer a top-level tab — it's folded into the Scanpath
# Visualization tab's "Export" subtab (see tabs._render_export_panel).
# The two top-level views. Scanpath is the default page; Corpus Analysis is
# reached via the header button (``_render_about_panel``). Data Inspection and
# Share are now subtabs of the Scanpath view (tabs.render_single_trial_tab),
# not standalone views. ``main_nav`` (session state) holds the active view.


def _render_raw_preview(label: str, df: pd.DataFrame) -> None:
    """Show one uploaded table's columns + a sample so the user can map it."""
    if df is None or df.empty:
        return
    st.markdown(f"#### {label} — {len(df):,} rows × {df.shape[1]} columns")
    st.caption("Columns: " + ", ".join(str(c) for c in df.columns))
    st.dataframe(df.head(200), width="stretch", height=320)


def _render_unmapped_view(
    raw_words_df: pd.DataFrame,
    raw_fixations_df: pd.DataFrame,
    problems: list,
) -> None:
    """Show the raw uploaded data while the column mapping isn't usable.

    Two different failures land here, and they need different words. A mapping
    that is **incomplete** asks the user to fill a field in; one the pipeline
    **rejected** (``MAPPING_FAILURE_LEAD``) already names what is wrong with the
    combination they have — so it gets the error, the reason, and a one-click
    way back to the auto-detected mapping, for when the offending pick came from
    a restored session and editing the panel field by field is a scavenger hunt.

    Either way the uploaded tables (unmodified) are shown below, so the user can
    inspect column names and values while choosing.
    """
    rejected = [p for p in problems if p.startswith(MAPPING_FAILURE_LEAD)]
    if rejected:
        for problem in rejected:
            st.error(problem, icon="🚫")
        st.caption(
            "Change the field it names in the **Column mapping** section above, "
            "or start again from what auto-detection proposes."
        )
        st.button(
            "↩️ Reset to the auto-detected mapping",
            key="reset_column_mapping",
            on_click=reset_column_mapping,
        )
    else:
        st.warning(
            "**Finish the column mapping to draw scanpaths.** Map the missing "
            "field(s) in the **Column mapping** section above — the raw data is "
            "shown below to help you choose. "
            "Still needed:\n\n" + "\n".join(f"- {p}" for p in problems)
        )
    if (raw_words_df is None or raw_words_df.empty) and (
        raw_fixations_df is None or raw_fixations_df.empty
    ):
        st.info("No data loaded yet.")
    _render_raw_preview("Words / IA", raw_words_df)
    _render_raw_preview("Fixations", raw_fixations_df)


@st.cache_data(show_spinner=False)
def _cached_participant_ids(_words, _fixations, cache_key) -> list:
    """Every reader id in the dataset (DATA-20), memoized per frame pair.

    Underscore-prefixed frames + an explicit `frame_fingerprint` key, the house
    convention: this is a `.unique()` over the *unfiltered* corpus, which is
    hundreds of milliseconds on a full-size one.
    """
    del cache_key
    return metadata_mod.participant_ids(_words, _fixations)


def _refresh_participant_metadata(participants) -> None:
    """Re-report an attached participant table against the loaded readers.

    The table outlives a data-source switch (it is session state, like the
    annotations), so the join it was validated against can go stale the moment
    a different corpus loads. Recomputing the report — not the fields — keeps
    "no row for these readers" honest without asking the user to re-upload.
    """
    from scanpath_studio import metadata as md

    attached = st.session_state.get(md.SESSION_KEY)
    if attached is None:
        return
    st.session_state[md.SESSION_KEY] = md.rejoin(attached, participants)


def _render_offpage_setup_notice(data_view: bool) -> None:
    """Point at the **Data** page when setup is unfinished and we're elsewhere.

    DATA-26: an unfinished dataset (a wizard mid-flight, or a required column
    still unmapped) leaves the analysis views with nothing to draw — `main`
    returns before them, exactly as it did before the page existed. What it used
    to leave behind was a blank screen; the setup UI now lives on a page that is
    rendered but hidden, so say where it went and offer one click to get there.

    Deliberately *not* a forced `switch_to_view`: bouncing the user back every
    run would make the other two views unreachable until the mapping is fixed,
    and that is a worse trap than an empty page with a signpost.

    The second button is the way out that does **not** go through the page:
    finishing the setup is the right answer when the dataset is nearly there,
    but a dataset the pipeline rejects can leave the user with nothing to plot
    and no appetite for the mapping — and the source picker itself lives on the
    page they'd rather not visit. See :func:`load_bundled_demo`.
    """
    if data_view:
        return
    st.info(
        "**This dataset isn't set up yet**, so there's nothing to plot. "
        "Finish it on the 🗂️ **Data** page — or start over from the demo.",
        icon="🗂️",
    )
    finish, demo = st.columns(2)
    finish.button(
        "🗂️ Go to Data setup",
        on_click=_go_data,
        type="primary",
        width="stretch",
        key="offpage_go_to_setup",
    )
    demo.button(
        DEMO_RESET_LABEL,
        on_click=load_bundled_demo,
        width="stretch",
        key="offpage_load_demo",
        help=DEMO_RESET_HELP,
    )


# File types accepted by every upload box. ``zip`` covers single-member
# archives wrapping any of the others (e.g. ``data.csv.zip``).
_UPLOAD_TYPES = ["csv", "tsv", "parquet", "feather", "zip", "xlsx", "xls"]


def _uploaded_file_key(uploaded) -> tuple:
    """Stable cache key for an uploaded file across reruns.

    ``st.file_uploader`` keeps the same ``UploadedFile`` (and ``file_id``) for a
    given upload until it's replaced, so keying on it lets us parse the file
    *once* instead of on every rerun."""
    return (
        getattr(uploaded, "file_id", None),
        getattr(uploaded, "name", None),
        getattr(uploaded, "size", None),
    )


@st.cache_data(show_spinner="Reading uploaded data…")
def _read_uploaded_table_cached(
    _uploaded, file_key, kind=None, chosen=()
) -> pd.DataFrame:
    try:
        _uploaded.seek(0)
    except Exception:
        pass
    if kind is None:
        return read_table(_uploaded)
    # PERF-6: parse only the columns the mapping, the registry and the user's
    # own picks need. `kind` and `chosen` are part of the cache key, so naming
    # a new column simply re-reads the file under the new plan.
    header = read_table_columns(_uploaded)
    return read_table(_uploaded, plan=upload_read_plan(header, kind, chosen=chosen))


@st.cache_data(show_spinner="Reading uploaded data…")
def _read_uploaded_tables_cached(
    _uploaded_list, file_keys, kind=None, chosen=()
) -> pd.DataFrame:
    for f in _uploaded_list:
        try:
            f.seek(0)
        except Exception:
            pass
    plan_for = None
    if kind is not None:

        def plan_for(header):
            return upload_read_plan(header, kind, chosen=chosen)

    return read_tables(list(_uploaded_list), plan_for=plan_for)


#: Session keys naming a source column the user has picked: every mapping
#: dropdown (``col_map_<table>_<field>``) and the wizard's extra-keeps picker.
#: A composite trial id stores a *list*, so both shapes are read.
_CHOSEN_COLUMN_KEYS = ("col_map_",)
_CHOSEN_COLUMN_EXTRA = "wizard_keep_extra"


def _columns_chosen_in_state(state, header) -> set:
    """Source columns of ``header`` the user has already named (PERF-6).

    Swept out of session state rather than read field by field: the mapping
    keys are per-table *and* per-field, and a composite trial id stores a list,
    so matching names against the header is both simpler and robust to a key
    this function has never heard of. Names belonging to the *other* upload box
    — or left over from a previous dataset — aren't columns of this table, so
    the header filter drops them.
    """
    columns = set(header)
    chosen: set = set()
    for key, value in state.items():
        if not (
            str(key).startswith(_CHOSEN_COLUMN_KEYS) or key == _CHOSEN_COLUMN_EXTRA
        ):
            continue
        values = value if isinstance(value, (list, tuple, set)) else [value]
        chosen.update(v for v in values if isinstance(v, str) and v in columns)
    return chosen


def upload_read_plan(header, kind: str, *, chosen=()) -> ReadPlan:
    """Plan an uploaded table's read from its header (PERF-6, decision 2a).

    The mapping is auto-proposed from the column names, so the plan exists
    before the user has touched anything; ``chosen`` folds back in the columns
    they *have* named, which is what keeps a hand-picked mapping or a kept extra
    from being dropped. A column named later simply changes the plan, and the
    read runs again against the new one.
    """
    propose = propose_word_schema if kind == "words" else propose_fix_schema
    registry = WORD_OPTIONAL_FIELDS if kind == "words" else FIX_OPTIONAL_FIELDS
    names = list(header)
    return plan_table_read(
        names,
        propose(pd.DataFrame(columns=names)),
        registry,
        keep_columns=set(chosen),
    )


def _upload_header(uploaded, *, multi: bool) -> list:
    """Every column name across an upload, in first-seen order (PERF-6).

    The *union*, not the first file's: one upload is commonly one file per
    participant, and an export can gain or lose a column between them
    (``read_tables``: "fields absent from a file become NaN"). Resolving the
    user's chosen columns against only the first header would silently drop a
    column that lives in a later file, and the mapping dropdowns would not
    offer it at all.
    """
    sources = list(uploaded) if multi else [uploaded]
    header: list = []
    for source in sources:
        header.extend(c for c in read_table_columns(source) if c not in header)
    return header


def _uploaded_header(state_prefix: str) -> list:
    """The full column list of the table uploaded under ``state_prefix``.

    PERF-6 narrows the *rows* an upload parses, never the column names: the
    mapping dropdowns and the wizard's "Additional fields to keep" picker still
    offer every column in the file, and naming one adds it to the plan. Empty
    when nothing is uploaded, or on a path that reads the table whole.
    """
    return list(st.session_state.get(f"{state_prefix}_header") or [])


def _read_uploaded_frame(
    *,
    uploader_label: str,
    upload_help: str,
    state_prefix: str,
    multi: bool,
    container=None,
    kind: str | None = None,
) -> pd.DataFrame:
    """Render one upload box and return its (concatenated) frame.

    Renders into ``container`` — the setup wizard's own step, or the 🗂️ Data
    page's upload slot. Empty frame when nothing is
    uploaded. The file parse is cached on the upload's identity (see
    ``_uploaded_file_key``) so a large uploaded table is read once, not re-parsed
    on every rerun. Isolated from the mapping render so tests can inject frames
    without a real upload (AppTest can't drive ``st.file_uploader``)."""
    host = container if container is not None else st.container()
    uploaded = host.file_uploader(
        uploader_label,
        type=_UPLOAD_TYPES,
        accept_multiple_files=multi,
        key=f"{state_prefix}_upload",
        help=upload_help,
    )
    if not uploaded:
        return pd.DataFrame()
    # BUG-5: a large upload parses/normalizes into several in-memory copies that
    # can OOM-kill the ~1 GB hosted demo (no traceback). Warn and require an
    # explicit opt-in before parsing.
    #
    # DATA-22 review: only on the *hosted* demo. Running locally there is no such
    # ceiling — the warning was pure noise, and the "Load it anyway" tick was a
    # step between the user and their own data on their own machine. Same
    # loopback test the wizard's "run locally" tip uses.
    if upload_exceeds_limit(uploaded) and not is_loopback_url(
        str(getattr(st.context, "url", "") or "")
    ):
        mb = uploaded_files_total_bytes(uploaded) / (1024 * 1024)
        host.warning(
            f"This upload is **{mb:.0f} MB**. On the hosted demo (~1 GB RAM), "
            "parsing a corpus this large can exhaust memory and crash the app. "
            "For big corpora, run locally (`pip install scanpath-studio`) or "
            "upload a subset (e.g. a few participants)."
        )
        if not host.checkbox(
            "Load it anyway",
            key=f"{state_prefix}_load_large",
            help="Parse this large upload regardless. Safe on a local machine "
            "with enough RAM; may crash the memory-limited hosted demo.",
        ):
            return pd.DataFrame()
    # PERF-6: the header pass is cheap and its answer is what both the plan and
    # the wizard's column pickers are built from, so it happens first and is
    # stashed for `_uploaded_header`. `chosen` is sorted into a tuple because it
    # rides in the cache key.
    header: list = []
    chosen: tuple = ()
    if kind is not None:
        header = _upload_header(uploaded, multi=multi)
        chosen = tuple(sorted(_columns_chosen_in_state(st.session_state, header)))
    st.session_state[f"{state_prefix}_header"] = header
    if multi:
        return _read_uploaded_tables_cached(
            uploaded,
            tuple(_uploaded_file_key(f) for f in uploaded),
            kind=kind,
            chosen=chosen,
        )
    return _read_uploaded_table_cached(
        uploaded, _uploaded_file_key(uploaded), kind=kind, chosen=chosen
    )


def load_raw_gaze_data(data_choice: str, *, host=None, notices=None) -> pd.DataFrame:
    """Load and normalize optional raw gaze data (millisecond-level eye positions).

    Raw gaze data provides finer temporal resolution than fixation-level data
    and enables overlay visualizations showing continuous gaze paths.

    Args:
        data_choice: The selected data source (e.g. ``DEMO_CHOICE`` loads the
            bundled sample gaze; other built-in sources have none). The Upload
            source and stored datasets carry their own raw gaze, so ``main``
            doesn't call this for them.
        host: Where the optional uploader + its column mapping render — the
            *Data location* section of the 🗂️ Data page (DATA-26).
        notices: Where the "raw gaze ignored" warnings render. Deliberately the
            strip under the menu bar, not ``host``: a warning on a page the user
            isn't looking at is invisible, and that strip is on every page.

    Returns:
        Normalized raw gaze DataFrame with canonical columns, or empty DataFrame
        if not available or schema inference fails

    Canonical Columns (raw gaze):
        participant_id, trial_id, x, y, timestamp_ms (optional: text)

    UI Effects:
        - Renders optional file uploader for "Upload csv tables" mode
        - Shows warning if schema inference fails
        - Shows info message if sample data unavailable
    """
    raw_gaze_df = pd.DataFrame()
    cfg = host if host is not None else st.container()
    warn = notices if notices is not None else st.container()

    if data_choice in (SYNTHETIC_CHOICE, PUBLIC_DATASETS_CHOICE):
        # Neither the synthetic trial nor the public corpora ship raw gaze;
        # skip the uploader entirely.
        return raw_gaze_df

    if data_choice == DEMO_CHOICE:
        raw_gaze_df = load_sample_raw_gaze()
        if not raw_gaze_df.empty:
            raw_gaze_schema = infer_raw_gaze_schema(raw_gaze_df)
            if raw_gaze_schema:
                _stash_active_mapping("raw_gaze", raw_gaze_schema)
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)
            else:
                warn.warning("Could not infer raw gaze schema from sample data")
                raw_gaze_df = pd.DataFrame()
    else:
        uploaded_raw_gaze = cfg.file_uploader(
            "Raw gaze table (optional)",
            type=["csv", "parquet", "feather", "zip"],
            help="Optional: millisecond-level gaze with participant_id, trial_id, x, y.",
        )
        if uploaded_raw_gaze:
            raw_gaze_df = read_table(uploaded_raw_gaze)
            proposed = propose_raw_gaze_schema(raw_gaze_df)
            initial_problems = validate_raw_gaze_schema(proposed)
            with cfg:
                raw_gaze_schema = column_mapping_ui(
                    raw_gaze_df,
                    table_label="Raw gaze",
                    state_key_prefix="col_map_raw_gaze",
                    field_specs=RAW_GAZE_FIELD_SPECS,
                    proposed=proposed,
                    problems=initial_problems,
                )
            problems = validate_raw_gaze_schema(raw_gaze_schema)
            if problems:
                warn.warning("Raw gaze ignored — " + "; ".join(problems))
                raw_gaze_df = pd.DataFrame()
            else:
                _stash_active_mapping("raw_gaze", raw_gaze_schema)
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)

    return raw_gaze_df


# -----------------------------------------------------------------------------
# Data-source resolution + the panels the top menu bar hosts
#
# `_sidebar_group` is gone with the sidebar (UX-38): each former group is its own
# popover on the menu bar (see `menu.render_top_menu`), and the popover's trigger
# label is the group heading. Nothing left to title.
# -----------------------------------------------------------------------------


def resolve_data_source(host=None) -> str:
    """Resolve the active data source (renders no picker widget — UX-25).

    Returns the selected source: ``DEMO_CHOICE`` ("Bundled Demo"), a stored
    uploaded dataset's name, ``ONESTOP_CHOICE`` / ``PUBLIC_DATASETS_CHOICE`` when
    available, ``SYNTHETIC_CHOICE`` if already selected, or ``UPLOAD_CHOICE``
    while the "➕ Add data" wizard is active. Switching to a stored dataset reloads
    it from session (no re-upload); the synthetic source is no longer offered
    fresh and "Public Datasets" shows grayed-out until the feature flag is on.

    **UX-25** moved the *visible* picker out of the sidebar and onto the main
    view's "Filter by" row (:func:`render_data_source_picker`). The picker has to
    render inside the tab, i.e. long after the data is loaded, so this function
    keeps its position at the top of ``main`` and stays the resolver: it applies
    the pre-widget ``_pending_source_choice`` seam, heals a stale selection, and
    publishes the entry list the picker renders from (``_data_source_entries``).
    ``data_source_choice`` remains the canonical key (``?source=…`` deep links and
    the wizard's finalize / cancel path both write it).

    ``host`` is the Data page's *Data source* slot (DATA-26). The one thing this
    function *does* render — the wizard's "✕ Cancel" bar, which stands in for the
    picker while an upload is being added — goes there, so it takes the picker's
    place on the page rather than appearing above it in the bare main area.
    """
    # Apply a programmatic source switch (the wizard's finalize / Cancel, or the
    # main-view picker's on_change) BEFORE anything reads data_source_choice. It
    # rides a plain key, not a widget value, so the browser never reconciles it
    # away — assigning data_source_choice inline and rerunning is unreliable
    # because the widget's frontend value can overwrite it on the rerun (works in
    # AppTest, not in a real browser). Callbacks run before the script body, so a
    # pick made in the tab still takes effect on the very next run.
    pending = st.session_state.pop("_pending_source_choice", None)
    if pending is not None:
        st.session_state["data_source_choice"] = pending
        # A real source was chosen (finalize / cancel) → leave the wizard.
        st.session_state["_show_upload_wizard"] = False

    # The upload wizard is tracked by a plain flag, not by parking UPLOAD_CHOICE
    # in the radio key (which Streamlit would garbage-collect mid-wizard — see
    # _enter_add_data_wizard). The legacy ``data_source_choice == UPLOAD_CHOICE``
    # is still honoured so AppTests / `?source=upload` deep links can open the
    # wizard directly. While it's open the wizard owns the page (the "Filter by"
    # row never renders), so the way out is rendered here, at the top of it.
    if (
        st.session_state.get("_show_upload_wizard")
        or st.session_state.get("data_source_choice") == UPLOAD_CHOICE
    ):
        # UX-66: the caption is gone (the sticky bar's title says where you are)
        # and ✕ Cancel rides that bar — `wizard._render_data_setup` reserves the
        # slot, and the wizard renders *after* this, so on the very first run of
        # a fresh wizard the slot does not exist yet and it falls back to here.
        # UX-66: ✕ Cancel moved onto the wizard's sticky bar, which is the one
        # row that stays on screen — the way out used to scroll away with the
        # page. It is rendered by `wizard._render_data_setup` via
        # `leave_add_data_wizard` below; nothing is drawn here, because this
        # function runs *before* the wizard and a container reserved now would
        # belong to the previous run.
        return UPLOAD_CHOICE

    # DATA-9: one **flat** source picker. Every source is a single entry tagged by
    # kind — 🧪 demo · 🔒 private (your uploads + local env bundles) · 🌐 public —
    # instead of a "Public datasets" category that then needed a second selectbox.
    # `data_source_choice` stays the canonical key, but for a public corpus the
    # entry's token IS the registry label; the return value resolves it back to
    # PUBLIC_DATASETS_CHOICE (+ public_dataset_choice) so the load path is unchanged.
    uploaded = list(st.session_state.get("_datasets", {}).keys())
    entries: list[str] = []
    kinds: dict[str, str] = {}
    if onestop_data_dir() is not None:
        entries.append(ONESTOP_CHOICE)
        kinds[ONESTOP_CHOICE] = "🔒"
    if multipleye_bundle_dir() is not None:
        entries.append(MULTIPLEYE_BUNDLE_CHOICE)
        kinds[MULTIPLEYE_BUNDLE_CHOICE] = "🔒"
    entries.append(DEMO_CHOICE)
    kinds[DEMO_CHOICE] = "🧪"
    entries.append(AUTHOR_CHOICE)
    kinds[AUTHOR_CHOICE] = "✏️"
    for name in uploaded:
        entries.append(name)
        kinds[name] = "🔒"
    # DATA-27 (Task 11R): every prepared benchmark corpus is in here as its own
    # 🌐 entry, exactly like the built-ins — `public_dataset_registry()` composes
    # the two. Resolved once and reused below so the whole run agrees on one
    # snapshot of a registry that depends on a directory the user can change.
    registry = public_dataset_registry() if public_datasets_enabled() else {}
    for label in registry:
        entries.append(label)
        kinds[label] = "🌐"
    # UX-37: the ground-truth trial is offered **while debug mode is on** (the
    # ❓ Help toggle), rather than only via `?source=synthetic` — a URL the About
    # note and the docs had to spell out, which is the hidden-behind-a-param
    # problem this item exists to remove. It is a six-word verification fixture,
    # not a corpus, so it sits with the other developer affordances instead of
    # in every user's source list. Still selectable when something already chose
    # it, so a `?source=synthetic` link and the AppTests keep working.
    if (
        debug_enabled()
        or st.session_state.get("data_source_choice") == SYNTHETIC_CHOICE
    ):
        entries.append(SYNTHETIC_CHOICE)
        kinds[SYNTHETIC_CHOICE] = "🧪"

    # Removing an app-owned/public source means removing it from this session's
    # available list, not deleting packaged files or a public corpus. Keep the
    # stable token intact for links and loader dispatch; the ordinary stale-
    # selection healing below moves away from a source that was just hidden.
    hidden = set(st.session_state.get(HIDDEN_DATASETS_KEY) or [])
    entries = [token for token in entries if token not in hidden]
    kinds = {token: kind for token, kind in kinds.items() if token in entries}
    if not entries:
        # Never strand the app without a loadable source. This can only happen
        # after the user has removed every row one by one in the same session.
        hidden.discard(DEMO_CHOICE)
        st.session_state[HIDDEN_DATASETS_KEY] = sorted(hidden)
        entries = [DEMO_CHOICE]
        kinds = {DEMO_CHOICE: "🧪"}

    # Migrate a legacy `PUBLIC_DATASETS_CHOICE` selection (old saved state / deep
    # link / the former category radio) to the concrete corpus token so it lands on
    # the right entry. Falls back to the first public corpus (not the demo) when no
    # corpus was remembered, preserving the old "Public datasets → first corpus".
    if st.session_state.get("data_source_choice") == PUBLIC_DATASETS_CHOICE:
        corpus = st.session_state.get("public_dataset_choice")
        if corpus not in registry:
            corpus = next(iter(registry), None)
        st.session_state["data_source_choice"] = corpus or entries[0]

    # Heal a stale/invalid selection (e.g. a removed dataset) so the picker never
    # errors on an option that is no longer in the list. Anything that *was* a
    # benchmark entry gets its own landing, in preference to `entries[0]` (the
    # demo): the bootstrap placeholder disappears precisely *because* it
    # succeeded, so sending the user who just supplied a bundle path somewhere
    # else entirely answers them with a non-answer — and, the demo rendering no
    # directory input, drops them straight back out of the corpora they found.
    # The same reasoning covers a stale *corpus* label (the bundle directory was
    # repointed, or that corpus was removed from it): another prepared corpus is
    # a better answer than the demo whenever one is reachable (N2).
    stale = str(st.session_state.get("data_source_choice") or "")
    if stale not in entries:
        was_benchmark = stale == BENCHMARK_SETUP_CHOICE or stale.endswith(
            BENCHMARK_LABEL_SUFFIX
        )
        healed = ""
        if was_benchmark:
            healed = next(
                (
                    label
                    for label, spec in registry.items()
                    if spec.get("benchmark_dataset")
                ),
                "",
            )
        st.session_state["data_source_choice"] = healed or entries[0]
    choice = st.session_state["data_source_choice"]

    # Publish what the main-view picker renders from. It runs inside the tab,
    # after this; recomputing the list there would duplicate the registry /
    # stored-dataset logic above (and could disagree with the healed selection).
    st.session_state["_data_source_entries"] = entries
    st.session_state["_data_source_kinds"] = kinds
    st.session_state["_data_source_uploaded"] = uploaded

    # Resolve a public-corpus token back to the canonical PUBLIC_DATASETS_CHOICE so
    # every downstream consumer (load dispatch, monitor, filter/col-map reset keys)
    # is unchanged; the chosen corpus rides public_dataset_choice as before.
    if choice in registry:
        st.session_state["public_dataset_choice"] = choice
        return PUBLIC_DATASETS_CHOICE
    return choice


def _on_data_source_pick() -> None:
    """Route the main-view picker's choice through the pre-widget seam (UX-25).

    An ``on_change`` callback: it runs before the rerun's script body, so
    ``resolve_data_source`` — which pops ``_pending_source_choice`` at the
    top of ``main`` — applies the new source on the *same* run that renders it.
    The picker rides its own widget key (``data_source_picker``) rather than
    writing ``data_source_choice`` directly, so a deep link / saved config can
    keep assigning the canonical key without the widget reconciling it away.
    """
    picked = st.session_state.get("data_source_picker")
    if picked:
        st.session_state["_pending_source_choice"] = picked


def leave_add_data_wizard() -> None:
    """Abandon the add-dataset wizard and go back to the previous source.

    Split out of the picker for UX-66, which moved ✕ Cancel onto the wizard's
    sticky bar. Writes through the pre-widget ``_pending_source_choice`` seam
    (assigning the picker's value inline is reconciled away by the browser), so
    it is safe as an ``on_click``.
    """
    st.session_state["_pending_source_choice"] = st.session_state.get(
        "_prev_source", DEMO_CHOICE
    )
    st.session_state["_show_upload_wizard"] = False
    st.session_state["setup_complete"] = True


def stay_in_wizard() -> None:
    """Dismiss BUG-31's leave prompt and carry on setting the dataset up.

    Records *which* view was declined rather than just clearing the prompt: the
    nav is still sitting on that view (nothing here navigates — see the note in
    ``main``), so a bare clear would re-raise the same question on the next
    rerun. Clicking a different view asks again, which is right.
    """
    st.session_state[WIZARD_STAY_KEY] = st.session_state.pop(WIZARD_LEAVE_KEY, None)


def discard_and_leave_wizard() -> None:
    """Abandon the half-built dataset and let the trip finish (BUG-31).

    :func:`leave_add_data_wizard` restores the source the wizard was opened
    *from*. For a **nav-triggered** prompt nothing here needs to navigate: the
    nav has been sitting on the requested view the whole time the prompt was
    up, so closing the wizard is all it takes for the next run to render it.

    **BUG-36 follow-up:** that assumption breaks for ✕ Cancel, whose prompt
    always names 🗂️ Data as the destination regardless of where the nav
    actually is — click Session, click Keep setting up, then Cancel, and the
    nav is still genuinely on Session throughout; closing the wizard alone
    left it there instead of on Data as promised. Requesting the recorded
    destination through the same ``main_nav`` seam :func:`url_state._go_data`
    and friends use is a no-op for the nav-triggered case (the router is
    already sitting on it, so this just re-affirms the same value) and is
    what actually moves it for Cancel's fixed one.
    """
    destination = st.session_state.pop(WIZARD_LEAVE_KEY, None)
    st.session_state.pop(WIZARD_STAY_KEY, None)
    leave_add_data_wizard()
    if destination:
        st.session_state["main_nav"] = destination


def render_data_source_picker(host=None) -> None:
    """Render the data-source picker in the main view (UX-25).

    Sits on the "Filter by" row, left of the label, so the top of the page reads
    left-to-right as *which dataset → how to narrow it → which trial* — the app is
    built to be read straight down the page. Renders from the entry list
    :func:`resolve_data_source` published earlier this run; a pick is
    applied on the next run via :func:`_on_data_source_pick`.

    UX-64 reduced it to the selectbox alone. Adding a dataset, removing one and
    the contribute link were behind a ➕ popover here; the 🗂️ Data page owns all
    three now, and the width it frees is what lets the dataset picker keep its
    size on the single control line.
    """
    entries = list(st.session_state.get("_data_source_entries") or [])
    if not entries:
        return
    kinds: dict[str, str] = dict(st.session_state.get("_data_source_kinds") or {})
    uploaded = list(st.session_state.get("_data_source_uploaded") or [])

    registry = public_dataset_registry()

    def _entry_label(token: str) -> str:
        # Reads the `registry` snapshot resolved just above rather than calling
        # `public_dataset_registry()` per token: discovery depends on a directory
        # the user can change, so one run must format its options against one
        # snapshot (which is also why the old `_public_dataset_label` helper,
        # which built its own, had no business being called from here — M6).
        tag = kinds.get(token, "")
        if token in registry:
            # `picker_name_for` is the single definition of what this list shows
            # — the entry's `short` plus, while DATA-27 is unfinished on main, a
            # (WIP) marker. Formatting only: the entry's key, its `short` and
            # its share slug are untouched, so dropping the marker later
            # invalidates no link and no saved config. Anything that tells the
            # user to "select X" reads it too, so the two cannot drift. The
            # snapshot is passed in for the M6 reason above it.
            name = _dataset_display_name(token, registry)
        elif token in uploaded:
            name = f"{_dataset_display_name(token, registry)} (yours)"
        else:
            name = _dataset_display_name(token, registry)
        return f"{tag} {name}".strip()

    # Keyed wrapper → stable `.st-key-…` selector for the spotlight tour.
    box = (host if host is not None else st).container(key="tour_grp_data_source")
    # UX-64: the picker is the whole control now. The ➕ popover that sat beside
    # it — Add data, remove-an-upload, the contribute link — is gone: the 🗂️ Data
    # page is the only way to add a dataset, which is where the wizard renders
    # anyway, and removing one moves there too (#UX-54's dataset table). Dropping
    # it is also what frees the width for the single control line, since the
    # dataset picker itself must **not** shrink — you may be comparing two.
    #
    # Mirror the canonical key onto the widget key before it instantiates, so a
    # deep link / restore / wizard finalize shows up in the picker.
    current = st.session_state.get("data_source_choice")
    if current in entries:
        st.session_state["data_source_picker"] = current
    box.selectbox(
        "**Select Dataset**",
        entries,
        format_func=_entry_label,
        help=(
            "Which dataset the app is showing. Add, rename or remove one on "
            "the 🗂️ Data page."
        ),
        key="data_source_picker",
        on_change=_on_data_source_pick,
    )


#: Cell text of the dataset table's action buttons. `st.column_config.ButtonColumn`
#: takes each button's label from the cell *value*, which is what lets a row that
#: cannot be edited or deleted (a built-in corpus) simply carry no label — and,
#: since UX-78, what lets the **Dataset** column be both the name and the control
#: that opens it.
_DATASET_EDIT_LABEL = ":material/edit: Edit"
_DATASET_RENAME_LABEL = ":material/drive_file_rename_outline: Rename"
_DATASET_REMOVE_LABEL = ":material/delete: Remove"
_DATASET_ABOUT_LABEL = ":material/info: About"

#: DATA-36 — what the **Counts** cell says about the numbers beside it. A row
#: shows either what it loaded or what its corpus publishes, and which one it is
#: changes how to read every other cell: "Published · 360 participants" is a
#: claim about the corpus, "Loaded · 180" a fact about this session.
_COUNTS_BADGES = {"loaded": "Loaded", "published": "Published", "": ""}

# Built-in and public dataset tokens are load-path identifiers, so changing
# them would break deep links and loader dispatch. Their table rename is a
# display alias; removing one hides it from this browser session. Uploaded
# datasets keep using the real store re-key/delete operations in `wizard.py`.
DATASET_ALIASES_KEY = "_dataset_display_aliases"
HIDDEN_DATASETS_KEY = "_hidden_dataset_tokens"
PENDING_RENAME_KEY = "_dataset_pending_rename"
#: DATA-35 — the row whose ℹ️ About dialog is open. Same arm-then-read shape as
#: the rename and delete flags above: a table callback sets it, the next run
#: opens the dialog.
PENDING_ABOUT_KEY = "_dataset_pending_about"

#: UX-78 — the open dataset's row tint. A Styler writes inline CSS and so cannot
#: read the theme's variables; a translucent blue reads as "selected" on both the
#: light and the dark grid without being opaque enough to fight the text.
_DATASET_ACTIVE_TINT = "rgba(59, 130, 246, 0.18)"


def _dataset_display_name(token: str, registry: dict | None = None) -> str:
    """User-facing dataset name without changing the source's stable token."""
    alias = (st.session_state.get(DATASET_ALIASES_KEY) or {}).get(token)
    if alias:
        return str(alias)
    registry = public_dataset_registry() if registry is None else registry
    return picker_name_for(token, registry) if token in registry else token


#: The dataset table's count columns, in display order — and the only field
#: names a catalogue entry may publish figures under (DATA-36). A typo would
#: otherwise be dropped in silence; `tests/test_dataset_published_counts.py`
#: checks every declaration against this tuple.
DATASET_COUNT_FIELDS: tuple[str, ...] = (
    "Participants",
    "Texts",
    "Trials",
    "Screens",
    "Words",
    "Fixations",
    "Gaze points",
)


@dataclass(frozen=True)
class DatasetRowCounts:
    """What one row of the dataset table puts in its count columns (DATA-36).

    ``source`` says which of the two the row is showing — ``"loaded"`` (counted
    from rows this session holds) or ``"published"`` (the figures the corpus'
    own documentation, or a bundle manifest, states) — and it is one or the
    other, never a mixture: back-filling a measured row's gaps from the
    catalogue would make it read as one set of measurements while being two.

    ``differences`` is the check the whole item exists for. It holds every field
    both sides know and disagree on, as ``(published, loaded)``.
    """

    counts: Mapping[str, int | None]
    source: str
    differences: Mapping[str, tuple[int, int]]

    @property
    def exceeds_published(self) -> tuple[str, ...]:
        """Fields where **more** was loaded than the catalogue publishes.

        The one unambiguous signal that a published figure is wrong: a session
        cannot hold more of a corpus than the corpus has. The opposite — loading
        less — is the ordinary case (one OneStop regime, one part, a filtered
        export) and says nothing at all, which is why it is not flagged.
        """
        return tuple(
            field
            for field, (published, loaded) in self.differences.items()
            if loaded > published
        )


def dataset_row_counts(
    *,
    measured: Mapping[str, int | None] | None,
    published: Mapping[str, int] | None,
) -> DatasetRowCounts:
    """Resolve one row's counts from what was measured and what is published.

    ``measured`` is `remembered_dataset_counts`' answer, which is ``{}`` for a
    dataset the session has never held frames for and can carry ``None`` for a
    field that does not apply (no raw gaze, single-screen trials). A dict of
    nothing but ``None`` is *unknown*, not zero, and so does not count as a
    measurement.
    """
    measured = {k: v for k, v in (measured or {}).items() if v is not None}
    published = dict(published or {})
    if not measured:
        return DatasetRowCounts(published, "published" if published else "", {})
    differences = {
        field: (published[field], measured[field])
        for field in DATASET_COUNT_FIELDS
        if field in published
        and field in measured
        and published[field] != measured[field]
    }
    return DatasetRowCounts(measured, "loaded", differences)


def published_comparison_rows(
    published: Mapping[str, int], loaded: Mapping[str, int | None]
) -> list[dict[str, str]]:
    """The ℹ️ dialog's published-vs-loaded table, as already-formatted cells.

    Formatted here rather than by a Styler because a published field can be one
    this session did not measure — the demo publishes a gaze-point total, and a
    session that never loaded the raw-gaze overlay has none — and a number
    format applied to that blank is a crash in a dialog, on a path no test would
    naturally walk. A seven-row table needs no numeric sorting.
    """
    rows = []
    for field in DATASET_COUNT_FIELDS:
        if field not in published:
            continue
        here = loaded.get(field)
        rows.append(
            {
                "": field,
                "Published": f"{published[field]:,}",
                "This session": "—" if here is None else f"{here:,}",
            }
        )
    return rows


def published_dataset_counts(token: str, registry: dict | None = None) -> dict:
    """The figures this catalogue publishes for a dataset, or ``{}``.

    Reached through `dataset_about`, so a public corpus, a packaged source and a
    prepared benchmark corpus all answer the same way — and an upload answers
    ``{}``, which is the honest answer: nothing here knows anything about it.
    """
    return dict(dataset_about(token, registry).get("published_counts") or {})


def published_counts_source(token: str, registry: dict | None = None) -> str:
    """Where a dataset's published figures came from, as a sentence."""
    return str(dataset_about(token, registry).get("published_counts_source") or "")


def benchmark_published_counts(entry) -> dict:
    """A prepared corpus' manifest counts, as dataset-table fields (DATA-36).

    The bundle already records `n_readers` / `n_texts` / `n_fixations` per
    corpus — the same numbers this table wants, one column each instead of the
    one sentence `_benchmark_size_caption` renders them as.

    A count `entry_count` cannot read comes back ``None``, and an absent one
    ``0``; **neither is published**. Publishing either would assert a corpus with
    no readers, which is exactly the overclaim `entry_count` warns against.
    """
    from scanpath_studio.eyegenbench import entry_count

    fields = (
        ("Participants", "n_readers"),
        ("Texts", "n_texts"),
        ("Fixations", "n_fixations"),
    )
    return {field: count for field, key in fields if (count := entry_count(entry, key))}


def _counts_store() -> dict:
    store = st.session_state.get(DATASET_COUNTS_STORE_KEY)
    if not isinstance(store, dict):
        store = {}
        st.session_state[DATASET_COUNTS_STORE_KEY] = store
    return store


def remembered_dataset_counts(
    token: str,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    raw_gaze: pd.DataFrame | None = None,
) -> dict:
    """This dataset's headline counts, computed at most once per version of it.

    **DATA-32.** Three cases, in order:

    1. **Frames in memory** (the open dataset, and every stored upload) — the
       counts are keyed on the frames' fingerprints, so a remembered entry is
       reused only while it still describes *these* rows. A remap, a re-upload
       or any other edit changes the fingerprint and the counts are recomputed;
       staleness is therefore not possible, which is what makes remembering them
       safe at all.
    2. **Frames not loaded, but counted before** — the remembered row is shown.
       This is the case the item is for: a public corpus you opened last week no
       longer costs minutes to list.
    3. **Never counted** — blank, as before. Nothing is read from disk to fill a
       table.

    The store is pruned by :func:`forget_dataset_counts` when a dataset leaves
    the session, and cleared with the recovery cache.
    """
    store = _counts_store()
    entry = store.get(token)
    if words is None and fixations is None and raw_gaze is None:
        counts = entry.get("counts") if isinstance(entry, dict) else None
        remembered = dict(counts) if isinstance(counts, dict) else {}
        # Recovery manifests written before this table matched the inspection
        # summary called the same value Readers. Preserve it without loading the
        # dataset merely to refresh a label.
        if "Participants" not in remembered and "Readers" in remembered:
            remembered["Participants"] = remembered.pop("Readers")
        return remembered
    key = [
        frame_fingerprint(words),
        frame_fingerprint(fixations),
        frame_fingerprint(raw_gaze),
    ]
    if isinstance(entry, dict) and entry.get("key") == key:
        return dict(entry.get("counts") or {})
    counts = _dataset_counts(words, fixations, raw_gaze, tuple(key))
    store[token] = {"key": key, "counts": dict(counts)}
    return dict(counts)


def forget_dataset_counts(keep: set | None = None) -> None:
    """Drop remembered counts for datasets that are no longer listed (DATA-32).

    ``keep=None`` forgets all of them — used by recovery-cache clearing and by
    the dataset-removal cache invalidation path.
    """
    store = _counts_store()
    for token in [t for t in store if keep is None or t not in keep]:
        store.pop(token, None)


@st.cache_data(show_spinner=False)
def _dataset_counts(
    _words: pd.DataFrame,
    _fixations: pd.DataFrame,
    _raw_gaze: pd.DataFrame,
    key,
) -> dict:
    """Cheap headline counts for every field in the dataset summary row.

    Two ``nunique`` calls and two lengths — UX-54 asked for "measurements that
    are easy to calculate", and anything needing the measures pipeline would make
    *listing* the datasets as expensive as opening them. Cached on the frames'
    fingerprints (``key``), since this runs for every listed dataset on every
    rerun of the page.

    **``key`` has no leading underscore, and that is the whole point.**
    ``@st.cache_data`` skips underscore-prefixed arguments when it builds its
    cache key — that is how the frames are passed without being hashed — so the
    fingerprint argument was being skipped too (DATA-32 found it): the cache had
    exactly *one* entry, and every dataset after the first was served the first
    one's counts. UX-54 r2 had hidden it by counting only the open dataset.
    """

    def _n_unique(frame, column):
        if frame is None or frame.empty or column not in frame.columns:
            return None
        return int(frame[column].nunique())

    words = _words if _words is not None else pd.DataFrame()
    fixations = _fixations if _fixations is not None else pd.DataFrame()
    raw_gaze = _raw_gaze if _raw_gaze is not None else pd.DataFrame()
    frames = (fixations, words, raw_gaze)

    def _union_unique(column: str):
        values = set()
        found = False
        for frame in frames:
            if frame is None or frame.empty or column not in frame.columns:
                continue
            found = True
            values.update(frame[column].dropna().astype(str).tolist())
        return len(values) if found else None

    text_column = "unique_text_id" if "unique_text_id" in words else "text_id"
    screens = len(part_catalog(words, fixations, raw_gaze)) or None
    # DATA-36: a trial is a **(participant, trial_id) pair** — the row the trial
    # picker lists, since `utils.build_combo_options` de-duplicates on exactly
    # that — not a distinct `trial_id`. The two coincide only where a corpus
    # numbers its trials globally. PoTeC names them after the text, so all 75
    # readers share the same twelve ids and counting ids reported **12 trials**
    # for a corpus whose own README says 900 (75 participants × 12 texts). It is
    # also the cheaper count: the union it replaces materialized every trial id
    # in the frame as a Python string (2.4 M of them on OneStop) to de-duplicate
    # what `drop_duplicates` had already reduced to a few thousand rows.
    trials = (
        len(trial_keys(words) | trial_keys(fixations) | trial_keys(raw_gaze)) or None
    )
    return {
        "Participants": _union_unique("participant_id"),
        "Texts": _n_unique(words, text_column),
        "Trials": trials,
        "Screens": screens,
        "Words": len(words) or None,
        "Fixations": len(fixations) or None,
        "Gaze points": len(raw_gaze) or None,
    }


def _select_dataset(name: str) -> None:
    """Switch to a dataset from the UX-54 table, as the picker's callback does.

    Goes through the same ``_pending_source_choice`` seam the rename and the
    wizard finalize use: ``data_source_choice`` is a widget key elsewhere, so
    this is the one way an assignment lands before the widgets instantiate.
    """
    st.session_state["_pending_source_choice"] = name
    st.session_state["data_source_choice"] = name


#: UX-54 r2 — the upload the ✕ Delete button asked about, awaiting confirmation.
#: A plain session value, not a widget key: it is armed by a table callback and
#: read by the row of buttons the next run draws.
PENDING_DELETE_KEY = "_dataset_pending_delete"


@st.dialog("Remove this dataset?")
def _delete_confirmation_dialog(
    token: str, *, uploaded: set[str], available: list[str]
) -> None:
    """The modal body — UX-79. Opened by ``_render_delete_confirmation``.

    **BUG-36:** handled by the button's *return value*, not ``on_click`` — an
    ``st.dialog`` body is a fragment, so an ``on_click`` callback here reran
    only the dialog: the deletion happened, but ``main()`` never re-executed,
    so the modal sat there looking inert. ``st.rerun(scope="app")`` both closes
    the modal and re-renders the page underneath (see ``tour.py``'s
    ``_tutorial_library_dialog``, which hit the same trap first).
    """
    owned = token in uploaded
    if owned:
        st.warning(
            f"Remove **{_dataset_display_name(token)}**? Its tables, column "
            "mapping and annotations leave this session — there is no undo."
        )
    else:
        st.caption(
            f"Remove **{_dataset_display_name(token)}** from Available datasets "
            "for this session? The packaged or public source data is not deleted."
        )
    remaining = [entry for entry in available if entry != token]
    yes, no = st.columns(2)
    if yes.button(
        "Remove",
        key="dataset_delete_confirm",
        type="primary",
        width="stretch",
        disabled=not remaining,
    ):
        pending = st.session_state.pop(PENDING_DELETE_KEY, None)
        if owned:
            # Local import, like `_enter_add_data_wizard` above: `wizard`
            # imports `app` back, so it cannot be imported at module load.
            from scanpath_studio.wizard import _remove_dataset

            _remove_dataset(pending)
        else:
            hidden = set(st.session_state.get(HIDDEN_DATASETS_KEY) or [])
            hidden.add(pending)
            st.session_state[HIDDEN_DATASETS_KEY] = sorted(hidden)
            if st.session_state.get("data_source_choice") == pending:
                st.session_state["_pending_source_choice"] = remaining[0]
        st.rerun(scope="app")
    if not remaining:
        st.caption("At least one dataset must remain available.")
    if no.button(
        "Keep it",
        key="dataset_delete_cancel",
        width="stretch",
    ):
        st.session_state.pop(PENDING_DELETE_KEY, None)
        st.rerun(scope="app")


def _render_delete_confirmation(host, tokens: list, uploaded: set[str]) -> None:
    """The confirm step between ✕ Delete and the dataset actually going away.

    Deleting an upload drops its frames, its mapping and its annotations from
    the session with no undo, and the button that starts it is one cell away
    from ✏️ Edit in a table row — so the click arms this, and this asks.

    **UX-79** made it a modal rather than a block under the table: the question
    is raised by a click *in* the table, and on a long list of datasets a
    container below it can be off-screen from the row that asked. The arming
    flag is unchanged — a dialog is opened by calling it, so what moved is where
    the flag is read. A token that has since disappeared (the dataset was
    removed another way) disarms itself instead of opening a dialog about
    nothing.
    """
    token = st.session_state.get(PENDING_DELETE_KEY)
    if token is None:
        return
    if token not in tokens:
        st.session_state.pop(PENDING_DELETE_KEY, None)
        return
    _delete_confirmation_dialog(token, uploaded=uploaded, available=tokens)


def _unique_dataset_alias(requested: str, token: str, tokens: list[str]) -> str:
    """A non-empty display name that does not duplicate another table row."""
    base = requested.strip() or _dataset_display_name(token)
    used = {
        _dataset_display_name(other).casefold() for other in tokens if other != token
    }
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


@st.dialog("Rename dataset")
def _rename_dataset_dialog(
    token: str, *, uploaded: set[str], tokens: list[str]
) -> None:
    """Rename any row while keeping app-owned source tokens stable."""
    current = _dataset_display_name(token)
    requested = st.text_input(
        "Dataset name",
        value=current,
        key=f"dataset_table_rename_{token}",
        persist_state="session",
    )
    apply_col, cancel_col = st.columns(2)
    if apply_col.button(
        "Rename",
        key="dataset_table_rename_confirm",
        type="primary",
        width="stretch",
    ):
        requested = requested.strip()
        if not requested:
            st.warning("Enter a dataset name.")
            return
        if token in uploaded:
            from scanpath_studio.wizard import rename_dataset

            renamed = rename_dataset(token, requested)
            final_name = renamed or token
        else:
            final_name = _unique_dataset_alias(requested, token, tokens)
            aliases = dict(st.session_state.get(DATASET_ALIASES_KEY) or {})
            aliases[token] = final_name
            st.session_state[DATASET_ALIASES_KEY] = aliases
        st.session_state.pop(PENDING_RENAME_KEY, None)
        st.session_state["_dataset_table_note"] = f"Renamed to {final_name}."
        st.rerun(scope="app")
    if cancel_col.button("Cancel", key="dataset_table_rename_cancel", width="stretch"):
        st.session_state.pop(PENDING_RENAME_KEY, None)
        st.rerun(scope="app")


def _render_published_figures(token: str, registry: dict) -> None:
    """The dataset's published figures, and how this session compares (DATA-36).

    Nothing at all for a dataset that publishes none — an upload, or a source
    whose contents depend on the machine it runs on. When it does publish, the
    basis for the numbers is always shown; the side-by-side appears only once
    the dataset has actually been loaded, since before that the row *is* the
    published figures and the dialog would just be repeating it (DATA-35 r2).
    """
    published = published_dataset_counts(token, registry)
    if not published:
        return
    st.markdown(f"**Published figures.** {published_counts_source(token, registry)}")
    # No frames: this reads the remembered entry, which the table filled in for
    # every dataset the session has held — so it answers for a corpus opened
    # earlier as well as for the open one.
    row = dataset_row_counts(
        measured=remembered_dataset_counts(token, None, None, None),
        published=published,
    )
    if row.source != "loaded":
        return
    st.dataframe(
        pd.DataFrame(published_comparison_rows(published, row.counts)),
        hide_index=True,
        width="stretch",
    )
    if fields := row.exceeds_published:
        st.warning(
            f"This session holds **more** than the published figure for "
            f"{', '.join(fields)} — a corpus cannot be larger when loaded than "
            "it is, so the published figure is the one to update."
        )
    else:
        st.caption(
            "Loading less than the corpus publishes is the ordinary case — one "
            "regime, one part, one session folder, or an export that was "
            "narrowed before it got here."
        )


@st.dialog("About this dataset")
def _dataset_about_dialog(token: str, *, registry: dict) -> None:
    """DATA-35 — the row's description and coordinate provenance, nothing else.

    A dialog rather than two more columns: both are sentences, and the table
    already carries nine numeric columns plus its actions. It deliberately
    repeats **nothing** the row shows — the counts, the language and the home
    link are all cells, so restating them here was just noise (DATA-35 r2).
    What is left is the prose that could never fit a cell, which is what the
    ask meant by "a field that opens up".
    """
    about = dataset_about(token, registry)
    st.markdown(f"### {_dataset_display_name(token, registry)}")
    if about.get("description"):
        st.write(about["description"])
    if about.get("geometry"):
        # The provenance of the coordinates everything downstream is measured
        # from — real / reconstructed / synthesized. `geometry_badge` already
        # writes it as a sentence, so it is shown as one.
        st.markdown(f"**Where the coordinates come from.** {about['geometry']}")
    _render_published_figures(token, registry)
    if not about.get("description") and not about.get("geometry"):
        st.caption(
            "This is a dataset you added, so the app knows only what its own "
            "row shows. Its column mapping and recording setup are under "
            "✏️ Edit."
        )
    if st.button("Close", key="dataset_about_close", width="stretch"):
        st.session_state.pop(PENDING_ABOUT_KEY, None)
        st.rerun(scope="app")


def _render_about_dialog(tokens: list[str], registry: dict) -> None:
    token = st.session_state.get(PENDING_ABOUT_KEY)
    if token is None:
        return
    if token not in tokens:
        st.session_state.pop(PENDING_ABOUT_KEY, None)
        return
    _dataset_about_dialog(token, registry=registry)


def _render_rename_dialog(tokens: list[str], uploaded: set[str]) -> None:
    token = st.session_state.get(PENDING_RENAME_KEY)
    if token is None:
        return
    if token not in tokens:
        st.session_state.pop(PENDING_RENAME_KEY, None)
        return
    _rename_dataset_dialog(token, uploaded=uploaded, tokens=tokens)


def _close_dataset_editor() -> None:
    """``on_click`` for the editor's way out — back to 📂 Available datasets."""
    st.session_state.pop(DATASET_EDITOR_OPEN_KEY, None)
    st.session_state.pop(FOCUS_MAPPING_KEY, None)


def _render_dataset_editor_bar(host, data_choice: str) -> None:
    """DATA-35 — the ✏️ Edit dataset screen's sticky header.

    Deliberately the add-dataset screen's bar, down to the CSS class: the ask
    was that "the Add Dataset and Edit Dataset screens should be very similar",
    and the two screens ask the same questions of the same dataset — one before
    it exists and one after. The difference is the title (this one names the
    dataset) and the way out, which here is a return rather than a cancel: an
    edit is applied by its own section's button, so leaving discards nothing and
    needs no confirmation.
    """
    name = _dataset_display_name(
        str(st.session_state.get("data_source_choice") or data_choice)
    )
    bar = host.container(key="dataset_editor_bar")
    title_col, back_col = bar.columns([8, 2], vertical_alignment="center")
    title_col.markdown(
        f'<div class="sps-wiz-title">✏️ Edit {html.escape(name)}</div>',
        unsafe_allow_html=True,
    )
    back_col.button(
        "← Back to datasets",
        key="dataset_editor_close",
        on_click=_close_dataset_editor,
        width="stretch",
        help="Return to 📂 Available datasets. Changes you have already applied "
        "are kept.",
    )
    bar.caption(
        "How this dataset is read and measured — where its files are, how its "
        "columns map onto the app's fields, the screen it was recorded on, and "
        "any metadata tables attached to it. The same questions the "
        "add-dataset screen asks, for a dataset that already exists."
    )


#: DATA-35 — set by a row action that genuinely changes what the app is showing
#: (opening a dataset, opening the editor), read at the top of the table
#: fragment. A widget callback may not call ``st.rerun``, and a *fragment* rerun
#: would redraw the table alone while the page under it still showed the old
#: dataset — so the callback asks and the fragment body does it.
_TABLE_NEEDS_APP_RERUN = "_dataset_table_needs_app_rerun"


@st.fragment
def render_dataset_table(
    host=None,
    *,
    active: str | None = None,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
) -> None:
    """The 🗂️ Data page's dataset list, as a table (UX-54).

    One row per dataset — the same entries the picker offers — carrying the
    full summary counts and the actions belonging to that dataset: **Open** it,
    **Edit** its column mapping, **Rename** it, or **Remove** it. Sortable and
    scrollable by virtue of being an ``st.dataframe``, which is what a column of
    cards could not be.

    **Counts are only shown for data already in memory** — the open dataset
    (whose frames are passed in) and every stored upload. A public corpus is not
    read until it is opened, and loading eight of them to fill a table would cost
    minutes; those rows stay blank.

    Args:
        host: Container to render into. Defaults to the page.
        active: The open dataset's entry token, marked in the table.
        words: The open dataset's word frame, for its counts.
        fixations: Its fixation frame.
    """
    # DATA-35: a row action that only opens a dialog — About, Rename, Remove —
    # costs a *fragment* rerun, not a whole-app one. Renaming a dataset used to
    # take two full page renders (one to open the modal, one to apply it) on a
    # page that draws a forty-row table, the whole column mapping and three
    # upload widgets; the first of those is now this box redrawing itself.
    if st.session_state.pop(_TABLE_NEEDS_APP_RERUN, False):
        st.rerun(scope="app")
    entries = list(st.session_state.get("_data_source_entries") or [])
    if not entries:
        return
    kinds = dict(st.session_state.get("_data_source_kinds") or {})
    uploaded = set(st.session_state.get("_data_source_uploaded") or [])
    stored_uploads = dict(st.session_state.get("_datasets") or {})
    registry = public_dataset_registry()
    # DATA-32: a dataset that has left the list takes its remembered counts with
    # it — deleted, renamed, or a public corpus whose location was unset.
    forget_dataset_counts(keep={t for t in entries if t != UPLOAD_CHOICE})

    kind_labels = {
        "🧪": "Demo",
        "✏️": "Manual",
        "🔒": "Private",
        "🌐": "Public",
    }
    rows = []
    for token in entries:
        if token == UPLOAD_CHOICE:
            continue  # the wizard, not a dataset
        own = token in uploaded
        name = _dataset_display_name(token, registry)
        # DATA-32: counted once per version of a dataset and remembered, so a
        # row keeps its numbers without the frames being in memory. UX-54 r2 had
        # narrowed this to the open dataset because counting meant *loading*;
        # with a store that argument only applies to a corpus nobody has opened
        # yet, and those rows are still blank rather than guessed at.
        if token == active:
            frames = (words, fixations, raw_gaze)
        elif token in stored_uploads:
            entry = stored_uploads.get(token) or {}
            frames = (
                entry.get("words"),
                entry.get("fixations"),
                entry.get("raw_gaze"),
            )
        else:
            frames = (None, None, None)
        about = dataset_about(token, registry)
        # DATA-36: a row that has never been opened shows the figures the corpus
        # publishes rather than nothing at all; the moment it is loaded, what
        # loaded takes over. `Counts` says which of the two is on screen.
        row_counts = dataset_row_counts(
            measured=remembered_dataset_counts(token, *frames),
            published=about.get("published_counts"),
        )
        counts = row_counts.counts
        rows.append(
            {
                # UX-78: the name *is* the button. `ButtonColumn` takes its label
                # from the cell value, so the column that says which dataset a
                # row is can also be the control that opens it — which retires
                # both the ▶ marker column and the separate Open column. The open
                # dataset is the coloured row instead (see the Styler below).
                "Dataset": name,
                "Kind": (
                    f"{kinds[token]} {kind_labels.get(kinds[token], '')}".strip()
                    if kinds.get(token)
                    else ("🔒 Private" if own else "")
                ),
                # DATA-35: the two facts about a corpus that fit in a cell. The
                # description and the coordinate provenance are sentences, so
                # they live one click away in the ℹ️ About dialog instead.
                "Language": about.get("language") or "",
                "Home": about.get("link") or None,
                "Counts": _COUNTS_BADGES.get(row_counts.source, "")
                + (" ⚠️" if row_counts.exceeds_published else ""),
                "Participants": counts.get("Participants"),
                "Texts": counts.get("Texts"),
                "Trials": counts.get("Trials"),
                "Screens": counts.get("Screens"),
                "Fixations": counts.get("Fixations"),
                "Words": counts.get("Words"),
                "Gaze points": counts.get("Gaze points"),
                "About": _DATASET_ABOUT_LABEL,
                "Edit": _DATASET_EDIT_LABEL,
                "Rename": _DATASET_RENAME_LABEL,
                "Remove": _DATASET_REMOVE_LABEL,
                "_token": token,
                "_active": token == active,
            }
        )
    if not rows:
        return
    frame = pd.DataFrame(rows)
    tokens = frame.pop("_token").tolist()
    # A blank count is still legitimate — an upload nobody has opened, a source
    # that publishes no figures, a field that does not apply (no raw gaze).
    # Pandas would normally upcast those columns to float (and Streamlit would
    # display e.g. ``24.0``), so keep them as nullable integers explicitly.
    for column in DATASET_COUNT_FIELDS:
        frame[column] = pd.array(frame[column], dtype="Int64")

    def _clicked(state_key):
        """The token of the row whose button was clicked, or ``None``.

        ``click["row"]`` is a position in the frame handed to ``st.dataframe``,
        not in whatever order the user sorted the columns into — the same
        source-position semantics dataframe selections have — so this parallel
        list stays correct under client-side sorting (the ENG-36 pattern).
        """
        click = st.session_state.get(state_key)
        row = click["row"] if click else None
        if row is not None and 0 <= row < len(tokens):
            return tokens[row]
        return None

    def _on_open() -> None:
        # UX-78: raised by a click on the dataset's *name*.
        token = _clicked("dataset_table_name")
        if token is not None:
            _select_dataset(token)
            st.session_state[_TABLE_NEEDS_APP_RERUN] = True

    def _on_edit() -> None:
        # DATA-35: "a screen similar to add-dataset" is now literally a screen.
        # Edit opens the dataset and raises the ✏️ Edit dataset screen over the
        # overview — the column mapping, the recording setup, the source's
        # options and location, the identity check and the metadata tables are
        # all on it. `FOCUS_MAPPING_KEY` still rides along for the mapping
        # editor's "editing <name>" line.
        token = _clicked("dataset_table_edit")
        if token is not None:
            _select_dataset(token)
            st.session_state[FOCUS_MAPPING_KEY] = token
            st.session_state[DATASET_EDITOR_OPEN_KEY] = True
            st.session_state[_TABLE_NEEDS_APP_RERUN] = True

    def _on_delete() -> None:
        # UX-54 r2: arm, don't delete. The click lands on a row of a table — one
        # cell away from ✏️ Edit — and an upload is not recoverable from the
        # session once dropped, so the button asks and the confirmation below
        # does the work.
        token = _clicked("dataset_table_delete")
        if token is not None:
            st.session_state[PENDING_DELETE_KEY] = token

    def _on_rename() -> None:
        token = _clicked("dataset_table_rename")
        if token is not None:
            st.session_state[PENDING_RENAME_KEY] = token

    def _on_about() -> None:
        token = _clicked("dataset_table_about")
        if token is not None:
            st.session_state[PENDING_ABOUT_KEY] = token

    box = host if host is not None else st
    # UX-78: the open dataset is a tinted row rather than a ▶ in a column of its
    # own. A Styler is the only per-row colour `st.dataframe` takes, and it is
    # applied to the whole row so the tint reads as "this one" rather than as a
    # highlighted cell. The colour is `color-mix`-free on purpose — a Styler
    # emits inline CSS, which cannot see the theme's variables — so it is a
    # translucent accent that sits legibly on both the light and the dark grid.
    active_row = next((i for i, row in enumerate(rows) if row["_active"]), None)
    frame = frame.drop(columns=["_active"])
    # A Styler is required for the active-row tint; the underlying nullable
    # integer dtypes remain intact for numeric display and sorting.
    display = frame.style
    if active_row is not None:
        display = display.apply(
            lambda row: (
                [
                    f"background-color: {_DATASET_ACTIVE_TINT}"
                    if row.name == active_row
                    else ""
                ]
                * len(row)
            ),
            axis=1,
        )
    box.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Dataset": st.column_config.ButtonColumn(
                "Dataset",
                width="medium",
                type="tertiary",
                help="Open this dataset.",
                on_click=_on_open,
                key="dataset_table_name",
            ),
            "Kind": st.column_config.TextColumn("Kind", width="small"),
            "Language": st.column_config.TextColumn("Language", width="small"),
            "Home": st.column_config.LinkColumn(
                "Home",
                width="small",
                display_text="Open ↗",
                help="The corpus' own home page or repository.",
            ),
            "Counts": st.column_config.TextColumn(
                "Counts",
                width="small",
                help="Where the numbers to the right come from. **Loaded** — "
                "counted from the rows this session holds. **Published** — the "
                "figures this corpus states for itself, shown until it is "
                "opened; ℹ️ About says where they came from. A ⚠️ means this "
                "session loaded *more* than was published, so the published "
                "figure is the one to fix.",
            ),
            "Participants": st.column_config.NumberColumn(
                "Participants", width="small", format="%d"
            ),
            "Texts": st.column_config.NumberColumn("Texts", width="small", format="%d"),
            "Trials": st.column_config.NumberColumn(
                "Trials", width="small", format="%d"
            ),
            "Screens": st.column_config.NumberColumn(
                "Screens", width="small", format="%d"
            ),
            "Fixations": st.column_config.NumberColumn(
                "Fixations", width="small", format="%d"
            ),
            "Words": st.column_config.NumberColumn("Words", width="small", format="%d"),
            "Gaze points": st.column_config.NumberColumn(
                "Gaze points", width="small", format="%d"
            ),
            "About": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="What this dataset is, and where its coordinates come from.",
                on_click=_on_about,
                key="dataset_table_about",
            ),
            "Edit": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="Open it and edit its column mapping and recording setup.",
                on_click=_on_edit,
                key="dataset_table_edit",
            ),
            "Rename": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="Rename this dataset.",
                on_click=_on_rename,
                key="dataset_table_rename",
            ),
            "Remove": st.column_config.ButtonColumn(
                "",
                type="tertiary",
                width="small",
                help="Remove this dataset from the session.",
                on_click=_on_delete,
                key="dataset_table_delete",
            ),
        },
    )
    _render_about_dialog(tokens, registry)
    _render_rename_dialog(tokens, uploaded)
    _render_delete_confirmation(box, tokens, uploaded)
    if note := st.session_state.pop("_dataset_table_note", None):
        box.success(note)


def resolve_source_monitor(
    data_choice: str | None,
    words: pd.DataFrame,
    fixations: pd.DataFrame,
) -> tuple[int, int, bool]:
    """The presentation monitor for a data source: ``(width, height, authoritative)``.

    Lifted out of `seed_canvas_state` by **CMP-8 §1** so there is *one* source →
    monitor table rather than two. `authoritative` keeps its meaning: the source
    declares a real presentation monitor, so the canvas should snap to it rather
    than to data-derived extents (which undershoot, because text rarely fills the
    screen).

    A **stored upload** now answers for itself when it recorded a setup snapshot
    — before CMP-8 it declared nothing, so switching to one silently left the
    canvas on the *previous* source's monitor.
    """
    # OneStop server bundle + bundled demo share the same experimental setup
    # (Dell U2715H, 2560x1440) — cited once in
    # `eyegenbench_geometry.DISPLAY_SPECS["onestop"]`.
    if data_choice in (ONESTOP_CHOICE, DEMO_CHOICE):
        return 2560, 1440, True
    if (monitor := _public_dataset_monitor(data_choice)) is not None:
        return monitor[0], monitor[1], True
    # A public corpus reached by its own registry *label* rather than through the
    # `Public datasets` picker still declares a monitor — `_public_dataset_monitor`
    # only answers for `PUBLIC_DATASETS_CHOICE`, but `data_source_choice` holds the
    # label (DATA-9's flat picker) and `compare_source` names B by label too.
    # `active_setup_snapshot` already compensates; without the same fallback here a
    # public corpus fell through to `compute_canvas_size` and reported its rounded
    # data extents as an ESTIMATED canvas. Cosmetic before CMP-11 (only the split
    # panels' `canvas_b` read it); load-bearing now that `setups_comparable` gates
    # the overlay on the canvas, since it refused the very pairs CMP-11 exists to
    # allow — and it also made A's resolution scan the whole corpus per rerun.
    if declared := (public_dataset_registry().get(data_choice) or {}).get("monitor"):
        return int(declared[0]), int(declared[1]), True
    if data_choice == MULTIPLEYE_BUNDLE_CHOICE:
        # MultiplEYE server bundle = the same native MultiplEYE export as the
        # public source; coordinates are offset onto the centered stimulus on
        # the real 1920x1080 monitor, so snap the canvas to it (true-to-scale),
        # exactly like the public MultiplEYE registry entry's monitor.
        from scanpath_studio.datasets import MULTIPLEYE_MONITOR

        return MULTIPLEYE_MONITOR[0], MULTIPLEYE_MONITOR[1], True
    stored = (st.session_state.get("_datasets") or {}).get(data_choice)
    if isinstance(stored, dict) and isinstance(stored.get("setup"), dict):
        snapshot = SetupSnapshot.from_dict(stored["setup"], fallback=SetupSnapshot())
        # Authoritative only when the screen was actually *known*: an assumed or
        # estimated canvas must not snap over a canvas the user has since tuned.
        return (
            snapshot.canvas_width,
            snapshot.canvas_height,
            snapshot.screen_provenance is Provenance.MEASURED,
        )
    if data_choice is None or data_choice == UPLOAD_CHOICE:
        # Uploaded data (the setup wizard passes data_choice=None) defaults to a
        # common 1440p monitor until the Recording-setup step says otherwise.
        return DEFAULT_FIGURE_SIZE[0], DEFAULT_FIGURE_SIZE[1], False
    derived_w, derived_h = compute_canvas_size(words, fixations)
    return derived_w, derived_h, False


def capture_setup_snapshot(
    provenance: Mapping[str, Provenance] | None = None,
) -> SetupSnapshot:
    """The resolved ``global_*`` geometry as a `SetupSnapshot` (CMP-8 §1).

    Reads the same keys `seed_canvas_state` resolves, so there is no second list
    of key names to keep in sync. ``provenance`` overrides the per-group
    provenance — the wizard passes what the user answered; a built-in corpus that
    declares its own monitor passes ``MEASURED``.
    """
    ss = st.session_state
    base = SetupSnapshot()
    groups = dict(base.provenance)
    groups.update(provenance or {})
    return SetupSnapshot(
        canvas_width=int(ss.get("global_canvas_width", base.canvas_width)),
        canvas_height=int(ss.get("global_canvas_height", base.canvas_height)),
        monitor_width_mm=float(
            ss.get("global_monitor_width_mm", base.monitor_width_mm)
        ),
        viewing_distance_mm=float(
            ss.get("global_viewing_distance_mm", base.viewing_distance_mm)
        ),
        base_font_size=int(ss.get("global_base_font_size", base.base_font_size)),
        font_family=str(ss.get("global_font_family", base.font_family)),
        line_spacing=float(ss.get("global_line_spacing", base.line_spacing)),
        scale_text_to_boxes=bool(
            ss.get("global_scale_text_to_boxes", base.scale_text_to_boxes)
        ),
        screen_provenance=groups["screen"],
        geometry_provenance=groups["geometry"],
        text_provenance=groups["text"],
    )


def active_setup_snapshot(
    data_choice: str | None = None,
) -> SetupSnapshot | None:
    """A source's recorded setup, or ``None`` when it has none.

    A stored upload carries the snapshot the wizard captured; a built-in corpus
    that declares a monitor reports it as ``MEASURED``; anything else has nothing
    to say, and saying nothing is the honest answer (a caller must not print
    "assumed 2560x1440" for a corpus that never claimed one).

    ``data_choice`` defaults to the active source, but callers that already know
    which source they are describing — `_build_share_query` is handed one —
    should pass it rather than re-reading session state.
    """
    choice = (
        data_choice
        if data_choice is not None
        else st.session_state.get("data_source_choice")
    )
    stored = (st.session_state.get("_datasets") or {}).get(choice)
    if isinstance(stored, dict) and isinstance(stored.get("setup"), dict):
        return SetupSnapshot.from_dict(stored["setup"], fallback=SetupSnapshot())
    declared = (
        choice in (ONESTOP_CHOICE, DEMO_CHOICE, MULTIPLEYE_BUNDLE_CHOICE)
        or _public_dataset_monitor(choice) is not None
        # A public corpus reached by its own label (the DATA-3 OneStop source)
        # rather than through the `Public datasets` picker still declares a
        # monitor in the registry.
        or bool((public_dataset_registry().get(choice) or {}).get("monitor"))
    )
    if declared:
        return capture_setup_snapshot(
            {
                # The corpus declares its presentation monitor, so the screen is
                # measured. The physical size / viewing distance are *not* — no
                # registry entry records them, so they stay honestly "assumed".
                "screen": Provenance.MEASURED,
                "geometry": Provenance.ASSUMED,
                "text": Provenance.MEASURED,
            }
        )
    payload = st.session_state.get("_wizard_setup_snapshot")
    if isinstance(payload, dict):
        return SetupSnapshot.from_dict(payload, fallback=SetupSnapshot())
    return None


def seed_canvas_state(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    data_choice: str | None = None,
) -> tuple[int, int, int, str, float, bool]:
    """Resolve the canvas / typography settings without rendering any widget.

    Split out of `render_canvas_controls` by **VIZ-31**, which moved that
    panel from the sidebar into the Scanpath rail. The rail renders inside
    `tabs.render_single_trial_tab`, i.e. *after* `main` has to know the canvas
    size and font in order to build `viz_settings` and dispatch a view — and the
    Corpus view has no rail at all. This function does every session-state write
    the panel used to do on its way past (source-driven monitor/font snapping and
    the default seeding), then reads the resolved values back out, so both
    callers agree and neither has to render to learn them.

    Seeding is `controls._pin` (a plain default-if-absent); what keeps these
    keys alive on a view that never renders their widgets is the widgets' own
    `persist_state="session"` — see the comment on that block.

    Returns:
        Tuple of (canvas_width, canvas_height, base_font_size, font_family,
        line_spacing, scale_text_to_boxes). The text-sizing pair keeps the reading
        text true-to-scale: see `plots._word_label_font_px`.
    """
    # OneStop server bundle + bundled demo share the same experimental setup
    # (Dell U2715H, 2560x1440 — cited in
    # `eyegenbench_geometry.DISPLAY_SPECS["onestop"]`). Data-derived extents
    # undershoot — text only fills part of the screen — so hard-default to the
    # real monitor here.
    # ``monitor_is_authoritative`` = the source declares a real presentation
    # monitor (OneStop/demo or a public-dataset registry entry), so the canvas
    # should snap to it rather than to data-derived extents.
    default_canvas_w, default_canvas_h, monitor_is_authoritative = (
        resolve_source_monitor(data_choice, words_filtered, fixations_filtered)
    )
    canvas_width = min(max(default_canvas_w, 100), 10000)
    canvas_height = min(max(default_canvas_h, 100), 10000)
    # Seed the data-derived defaults so the inputs render without a `value=`
    # argument — that keeps the keys assignable by the plot-config restore
    # (app._restore_plot_config) without Streamlit's "default value but also set
    # via Session State API" warning.
    #
    # For a source with an authoritative monitor, snap the canvas to it whenever
    # that source *changes* (selecting a public dataset, switching PoTeC↔MultiplEYE,
    # or a public dataset whose registered monitor was updated): a plain
    # ``setdefault`` would let a previously-seeded canvas stick, so a returning
    # session would keep the old monitor and render the corpus off-scale. Manual
    # canvas edits and plot-config restores within the same source are preserved
    # (the key is unchanged, so the snap doesn't re-fire).
    #
    # DATA-27 (Task 11R): `public_dataset_choice` is a correct per-corpus key on
    # its own again, now that every prepared benchmark corpus is its own registry
    # entry — the extra `eyegenbench_dataset` component R30 needed (when one
    # source fronted many corpora and this key never changed between them) is
    # gone with the source that made it necessary.
    source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    if monitor_is_authoritative and st.session_state.get("_canvas_seeded_for") != (
        source_key
    ):
        st.session_state["global_canvas_width"] = canvas_width
        st.session_state["global_canvas_height"] = canvas_height
        st.session_state["_canvas_seeded_for"] = source_key
    # The canvas pair itself is pinned with the rest of the defaults below.

    # Authoritative reading font: MultiplEYE stamps the stimulus FONT_SIZE + family
    # from its config onto the words. Snap the font controls to it when the source
    # changes (same gate as the canvas), so the reading text renders at the exact
    # size and (CJK) typeface the stimulus images were drawn with. We also turn off
    # "scale text to boxes" since the precise px is known — box geometry can only
    # approximate it. Manual edits within a source stick (the key is unchanged, so
    # the snap doesn't re-fire); a returning source re-snaps to the known font.
    font_px, font_css = _dataset_font(words_filtered)
    if font_px is not None and st.session_state.get("_font_seeded_for") != source_key:
        st.session_state["global_base_font_size"] = int(min(max(round(font_px), 6), 72))
        if font_css:
            st.session_state["global_font_family"] = font_css
        st.session_state["global_scale_text_to_boxes"] = False
        st.session_state["_font_seeded_for"] = source_key

    # The remaining widget defaults. Each of these used to be `setdefault`ed
    # inline, immediately above its own widget; seeding them here is what lets a
    # caller resolve the settings without rendering the panel.
    #
    # Seeding alone is NOT what keeps these alive. Since VIZ-31 these widgets
    # render only in the Scanpath rail, and Streamlit drops a widget's key from
    # session state at the end of any run in which the widget did not render — so
    # one trip through **Corpus Analysis** (no rail) would prune all fourteen and
    # the next run would seed the factory default over the user's canvas, font,
    # text colour and background, permanently. What prevents that is
    # `persist_state="session"` on each of those widgets (ENG-36; it replaced a
    # hand-rolled re-assert-every-run workaround). Six of the fourteen are
    # share-link / saved-config wire format, so this is not cosmetic. Pinned by
    # `test_canvas_settings_survive_a_corpus_analysis_round_trip`.
    ss = st.session_state
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    if ss.get("global_bg_choice") not in bg_options:
        ss.pop("global_bg_choice", None)
    # One table drives both the pin and the read-back. `_pin` swallows the
    # StreamlitAPIException raised when a key's widget was already built earlier
    # in the run, so a pinned key is *not* guaranteed to land — every read below
    # therefore goes through `_resolved`, never `ss[...]`, or a swallowed write
    # would surface as a KeyError that takes the whole app down.
    defaults = {
        "global_canvas_width": canvas_width,
        "global_canvas_height": canvas_height,
        "global_monitor_width_mm": 597.0,
        "global_viewing_distance_mm": 800.0,
        "global_scale_text_to_boxes": True,
        "global_line_spacing": float(DEFAULT_LINE_SPACING),
        "global_base_font_size": 16,
        "global_stimulus_font_pt": 12.0,
        "global_use_stimulus_font_pt": False,
        "global_font_family": FONT_FAMILY,
        "global_text_color": WORD_LABEL_COLOR,
        "global_bg_choice": bg_options[0],
        # Pinned here as well as in the render path: its picker exists only while
        # the choice is "Custom…", so it is the one key with no other keeper —
        # without this a custom background is lost the first time the user opens
        # Corpus Analysis and the choice silently falls back to a preset.
        "global_bg_custom": DEFAULT_BACKGROUND_COLOR,
    }

    def _resolved(key):
        return ss.get(key, defaults[key])

    for key, default in defaults.items():
        _pin(key, default)
    # Derived from the two above it, so it is pinned after them.
    _pin(
        "global_display_dpi",
        round(
            float(_resolved("global_canvas_width"))
            / (float(_resolved("global_monitor_width_mm")) / 25.4),
            2,
        ),
    )
    # Point-specified stimulus typography converts to px through the DPI above.
    # The rendering path recomputes this from its own widget values (which is
    # what makes an edit apply the same run); this keeps the non-rendering
    # callers on the same number.
    if not _resolved("global_scale_text_to_boxes") and _resolved(
        "global_use_stimulus_font_pt"
    ):
        ss["global_base_font_size"] = int(
            min(
                max(
                    round(
                        font_pt_to_px(
                            float(_resolved("global_stimulus_font_pt")),
                            float(ss.get("global_display_dpi", 96.0)),
                        )
                    ),
                    6,
                ),
                72,
            )
        )
    return (
        int(_resolved("global_canvas_width")),
        int(_resolved("global_canvas_height")),
        int(_resolved("global_base_font_size")),
        str(_resolved("global_font_family")),
        float(_resolved("global_line_spacing")),
        bool(_resolved("global_scale_text_to_boxes")),
    )


def render_canvas_controls(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    data_choice: str | None = None,
    slot=None,
    expanded: bool = False,
    title: str = "Experimental Setup",
    bare: bool = False,
    text_host=None,
    render_text: bool = True,
) -> tuple[int, int, int, str, float, bool]:
    """Render the canvas-geometry, typography and background panel.

    These controls let the user match the visualization to the experimental
    display, which is what keeps coordinates and word boxes spatially accurate.

    The panel normally renders into ``slot`` as its own collapsible expander.
    Pass ``bare=True`` when ``slot`` is already the disclosure container, as the
    compact Scanpath rail does. The setup wizard keeps the standalone expander.
    `seed_canvas_state` does the state work and is called first here, so rendering
    and not-rendering resolve identically.

    **UX-80/81 — ``text_host`` is where the typography half goes.** The two
    halves answer different questions and, in the rail, now live in different
    sections: the **screen** half (the monitor the figure is framed on) is drawn
    into ``slot`` for 📐 Figure & canvas, and the **text** half (how the reading
    text is drawn) into ``text_host`` for 📄 Stimulus → *Text*, beside the layer
    it describes. One call renders both — a widget drawn twice is a duplicate-key
    error, and one not drawn at all loses its key at the end of the run. The
    wizard passes neither and gets both, flat, in one expander: that step *is*
    the setup form, and hiding half of it behind buttons would be a step you
    cannot read at a glance.

    **The physical-geometry controls are not drawn in ``bare`` mode** (UX-81).
    Monitor physical width, viewing distance and display DPI are experiment
    facts, and the 🗂️ Data page's **Recording setup** (#DATA-22) already asks for
    them with a provenance; a second set in the rail could disagree with it. The
    *values* are unaffected — ``seed_canvas_state`` still pins them, and every
    consumer (px/degree for saccade amplitude in degrees, the point-to-pixel
    stimulus font conversion) reads them from state exactly as before, which is
    also what keeps a share link carrying them working.

    Returns:
        Tuple of (canvas_width, canvas_height, base_font_size, font_family,
        line_spacing, scale_text_to_boxes).
    """
    seeded = seed_canvas_state(words_filtered, fixations_filtered, data_choice)
    _, font_css = _dataset_font(words_filtered)
    host = slot if slot is not None else st.container()
    display = host if bare else host.expander(title, expanded=expanded)

    def field(host, kind: str, label: str, **kwargs):
        """One control, `label | field` in the rail and label-above in the wizard.

        UX-51 made the rail read as a compact form; the wizard's flat expander
        keeps the label above its field, for the same reason it stays flat — that
        step *is* the setup form, laid out across the page rather than inside a
        28rem popover, so there is no height to buy back.
        """
        if bare:
            return _labeled(host, kind, label, **kwargs)
        kwargs.pop("display", None)
        return getattr(host, kind)(label, **kwargs)

    # UX-80: no sub-popovers any more — each half is drawn straight into the
    # section that owns it, and the caller has already opened the one disclosure.
    screen = display
    text = text_host if (bare and text_host is not None) else display
    canvas_width = field(
        screen,
        "number_input",
        "Monitor width (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor width in pixels to keep coordinates true to scale.",
        key="global_canvas_width",
        persist_state="session",
    )
    canvas_height = field(
        screen,
        "number_input",
        "Monitor height (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor height in pixels to keep coordinates true to scale.",
        key="global_canvas_height",
        persist_state="session",
    )
    # DATA-2: physical setup values live beside the pixel canvas they explain.
    # They are persisted with the plot config and immediately yield a px/degree
    # scale for downstream saccade/reporting work.
    #
    # **UX-81 — in the rail these three are not drawn at all.** They are
    # experiment facts, and the 🗂️ Data page's Recording setup (#DATA-22) already
    # asks for them *with a provenance*; a second set here could disagree with
    # it, and did. Not rendering a widget normally loses its key — but these keys
    # are not widget-owned any more: `seed_canvas_state` pins all three on every
    # run (including the derived DPI), so a share link or saved config still
    # restores them and every consumer reads the same numbers as before.
    # The wizard's standalone form still shows them: that *is* where they are set.
    if bare:
        monitor_width_mm = float(st.session_state.get("global_monitor_width_mm", 597.0))
        viewing_distance_mm = float(
            st.session_state.get("global_viewing_distance_mm", 800.0)
        )
        display_dpi = float(st.session_state.get("global_display_dpi", 96.0))
    else:
        monitor_width_mm = field(
            screen,
            "number_input",
            "Monitor physical width (mm)",
            display="Physical width (mm)",
            min_value=100.0,
            max_value=3000.0,
            step=1.0,
            key="global_monitor_width_mm",
            persist_state="session",
            help="Width of the visible display area, not the diagonal size.",
        )
        viewing_distance_mm = field(
            screen,
            "number_input",
            "Viewing distance (mm)",
            min_value=100.0,
            max_value=3000.0,
            step=10.0,
            key="global_viewing_distance_mm",
            persist_state="session",
            help="Eye-to-screen distance during the experiment.",
        )
        derived_dpi = float(canvas_width) / (float(monitor_width_mm) / 25.4)
        display_dpi = field(
            screen,
            "number_input",
            "Display DPI",
            min_value=20.0,
            max_value=1000.0,
            step=1.0,
            key="global_display_dpi",
            persist_state="session",
            help="Used for point-to-pixel stimulus font conversion. The physical "
            f"width above implies {derived_dpi:.1f} DPI.",
        )
    px_per_degree = pixels_per_degree(
        float(viewing_distance_mm), float(canvas_width), float(monitor_width_mm)
    )
    # Still said, because it is the one number the framing controls imply and
    # cannot be read off them: where the geometry came from is the Data page's
    # to explain, but what it *means* for this figure belongs beside the canvas.
    screen.caption(
        f"Geometry: **{px_per_degree:.1f} px/degree** · "
        f"{1.0 / px_per_degree:.4f}° per pixel."
        + ("  ·  set in 🗂️ Data → Recording setup." if bare else "")
    )

    # Text can be switched off while this function still supplies the screen
    # half to 📐 Figure & canvas. Before BUG-38, the caller passed an undefined
    # text container in that state and the whole Scanpath view crashed. Do not
    # move the typography controls into the Figure popover as a fallback: they
    # belong to Stimulus → Text, and their session-persistent keys already keep
    # the last values while that layer is hidden.
    if not render_text:
        return (
            int(canvas_width),
            int(canvas_height),
            int(seeded[2]),
            str(seeded[3]),
            float(seeded[4]),
            bool(seeded[5]),
        )

    # --- 🔤 Text & fonts (sub-group in bare mode) -------------------------
    # Reading text is true-to-scale by default: it auto-sizes to the word boxes
    # (text height = box_height / line_spacing) and scales with the figure, so it
    # always fills the real line slot. Untick to fall back to a fixed font size.
    # Keyed (+ seeded) so the Save & restore panel can capture/reapply them.
    scale_text_to_boxes = field(
        text,
        "checkbox",
        "Scale text to boxes",
        key="global_scale_text_to_boxes",
        persist_state="session",
        help="Size text from word-box height. Without boxes, the plot font size "
        "is used instead.",
    )
    line_spacing = float(st.session_state.get("global_line_spacing", seeded[4]))
    use_stimulus_font_pt = bool(
        st.session_state.get("global_use_stimulus_font_pt", False)
    )
    stimulus_font_pt = float(st.session_state.get("global_stimulus_font_pt", 12.0))
    if scale_text_to_boxes:
        line_spacing = field(
            text,
            "number_input",
            "Line spacing",
            min_value=1.0,
            max_value=10.0,
            step=0.5,
            key="global_line_spacing",
            persist_state="session",
            help="Line slots represented by each word box. OneStop uses 3.",
        )
    else:
        use_stimulus_font_pt = field(
            text,
            "segmented_control",
            "Font unit",
            options=[False, True],
            format_func=lambda use_pt: "Points (pt)" if use_pt else "Pixels (px)",
            key="global_use_stimulus_font_pt",
            persist_state="session",
            help="Choose the original stimulus unit. Points are converted with "
            "the dataset DPI: px = pt × DPI ÷ 72.",
        )
        if use_stimulus_font_pt:
            stimulus_font_pt = field(
                text,
                "number_input",
                "Font size (pt)",
                min_value=4.0,
                max_value=144.0,
                step=0.5,
                key="global_stimulus_font_pt",
                persist_state="session",
            )
            st.session_state["global_base_font_size"] = int(
                min(max(round(font_pt_to_px(stimulus_font_pt, display_dpi)), 6), 72)
            )

    if not scale_text_to_boxes and use_stimulus_font_pt:
        base_font_size = int(st.session_state["global_base_font_size"])
    else:
        base_font_size = field(
            text,
            "number_input",
            "Plot font size (px)" if scale_text_to_boxes else "Font size (px)",
            min_value=6,
            max_value=72,
            step=1,
            help=(
                "Axis, legend, and fallback text size."
                if scale_text_to_boxes
                else "Reading-text, axis, and legend size in monitor pixels."
            ),
            key="global_base_font_size",
            persist_state="session",
        )
    text.button(
        "Use multilingual font stack",
        on_click=lambda: st.session_state.update(
            global_font_family=(
                "'Noto Sans', 'Noto Sans Hebrew', 'Noto Sans Arabic', "
                "'Noto Sans CJK SC', 'Arial Unicode MS', sans-serif"
            )
        ),
        help="A CJK/Hebrew/Arabic-capable CSS fallback stack (PRE-6).",
    )
    font_family = field(
        text,
        "text_input",
        "Text font",
        key="global_font_family",
        persist_state="session",
        help="Font for the word labels. Use the exact font from your experiment "
        "(e.g. 'Courier New') or a CSS fallback stack.",
    )
    if "right_to_left" in words_filtered and words_filtered["right_to_left"].any():
        text.caption(
            "↔ RTL script detected. Landing positions are measured from the "
            "logical word start; browser bidi shaping is used for labels."
        )
    # When the dataset declares its stimulus typeface (MultiplEYE), the overlaid
    # text only lines up with the stimulus image if that exact font is installed
    # on the viewer's machine — we don't bundle it, and the browser otherwise
    # falls back per-script (CJK lands, but half-width Latin in a CJK font drifts,
    # e.g. URLs render too wide). Tell the user the font + how to get it.
    hint = _stimulus_font_install_hint(font_css)
    if hint is not None:
        font_name, font_url = hint
        text.caption(
            f"ℹ️ This corpus was rendered in **{font_name}**. For the overlaid text "
            "to match the stimulus image exactly, install that font on this "
            "computer (it isn't bundled), then reload — otherwise the browser "
            "substitutes a fallback and labels (especially URLs / Latin) can "
            f"drift. [Download]({font_url}); install via Font Book (macOS), "
            "right-click → Install (Windows), or `~/.local/share/fonts` + "
            "`fc-cache -f` (Linux). Or just turn on the **stimulus image** to read "
            "the original text."
        )

    # Base reading-text colour (highlighted-text colour lives in Visualization
    # controls). Read back into viz_settings by controls.render_plot_controls.
    field(
        text,
        "color_picker",
        "Text color",
        key="global_text_color",
        persist_state="session",
        help="Colour of the reading text drawn over the stimulus.",
    )

    # Plot background lives here (Experimental Setup) rather than under
    # Visualization; render_plot_controls reads the chosen value from session state.
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    field(
        text,
        "selectbox",
        "Plot background",
        options=bg_options,
        key="global_bg_choice",
        persist_state="session",
        help="Background of the plotting area (and exported figures).",
    )
    if st.session_state.get("global_bg_choice") == "Custom…":
        # Seed rather than pass `value=`: this key is restored pre-widget by a
        # deep link / saved config, and a keyed widget given both logs Streamlit's
        # "default value but also had its value set" warning (BUG-17).
        # This picker exists only while the choice is "Custom…", so it typically
        # FIRST mounts on a later run — the BUG-15 case, now handled by the
        # widget's own `persist_state="session"` (ENG-36) rather than by
        # re-asserting the value from Python on every run.
        _pin("global_bg_custom", DEFAULT_BACKGROUND_COLOR)
        field(
            text,
            "color_picker",
            "Custom background color",
            display="Custom colour",
            key="global_bg_custom",
            persist_state="session",
        )

    return (
        int(canvas_width),
        int(canvas_height),
        int(base_font_size),
        font_family,
        float(line_spacing),
        bool(scale_text_to_boxes),
    )


# -----------------------------------------------------------------------------
# Setup wizard (hybrid: main-area on first load → collapsed panel afterward)
# -----------------------------------------------------------------------------


def _render_authoring_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Standalone editor whose result joins the ordinary plot/export pipeline."""
    from scanpath_studio.authoring import (
        DEFAULT_LAYOUT,
        apply_authoring_event,
        authored_fixations,
        authoring_json,
        default_events,
        event_problems,
        layout_problems,
        layout_text,
        parse_authoring_document,
        reconcile_event_table,
        unusable_event_rows,
    )
    from scanpath_studio.authoring_component import render_authoring_canvas

    st.subheader("✏️ Author a scanpath")
    st.caption(
        "Write the stimulus, then click or drag directly on the canvas. X/Y are "
        "the primary authored values; the optional target word is useful for "
        "measures but does not constrain where a fixation can be placed. The "
        "numeric table remains a complete keyboard-accessible editor."
    )
    restored = st.file_uploader(
        "Restore authoring file",
        type=["json"],
        key="author_restore_upload",
        help="Load a JSON file previously saved from this editor.",
    )
    if restored is not None:
        identity = (restored.name, restored.size)
        if st.session_state.get("_author_restore_identity") != identity:
            try:
                document = parse_authoring_document(restored.getvalue().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                st.error(str(exc))
            else:
                st.session_state["author_text"] = document.text
                st.session_state["_author_layout"] = document.layout
                st.session_state["_authored_events_frame"] = document.events
                st.session_state["_author_text_for_events"] = document.text
                st.session_state["_author_selected_fixation"] = None
                st.session_state["_author_events_editor_revision"] = (
                    int(st.session_state.get("_author_events_editor_revision", 0)) + 1
                )
                st.session_state["_author_restore_identity"] = identity

    text = st.text_area(
        "Stimulus text",
        value="Reading unfolds through a sequence of careful eye movements.",
        key="author_text",
        height=100,
    )
    layout = {**DEFAULT_LAYOUT, **st.session_state.get("_author_layout", {})}
    words = layout_text(text, **layout)
    with st.expander("Parsed word geometry", expanded=False):
        if words.empty:
            st.info(
                "Enter stimulus text to create word boxes. The empty canvas is still valid."
            )
        else:
            line_count = int(words["line_idx"].max()) + 1
            st.caption(
                f"{len(words)} {'word' if len(words) == 1 else 'words'} across "
                f"{line_count} {'line' if line_count == 1 else 'lines'} · word ids are "
                "1-based; line indices are 0-based. Explicit blank lines are retained."
            )
            st.dataframe(
                words[["text", "word_id", "line_idx", "x", "y", "width", "height"]],
                hide_index=True,
                width="stretch",
            )
    for problem in layout_problems(
        words, canvas_width=layout["canvas_width"], margin=layout["margin"]
    ):
        st.warning(problem)

    if st.session_state.get("_author_text_for_events") != text:
        st.session_state["_authored_events_frame"] = default_events(words)
        st.session_state["_author_events_editor_revision"] = (
            int(st.session_state.get("_author_events_editor_revision", 0)) + 1
        )
        st.session_state["_author_text_for_events"] = text
        st.session_state["_author_selected_fixation"] = None
    seed = st.session_state.get("_authored_events_frame", default_events(words))
    last_word = int(words["word_id"].max()) if not words.empty else 1
    canvas_panel = st.container()
    fixation_table = st.expander("Fixation table", expanded=False)
    fixation_table.caption(
        "One row per fixation. **Fixation id** is stable; **Order** controls the "
        "reading sequence. X/Y place the marker in screen pixels. **Target word** "
        f"is optional (1–{last_word}) and may be edited independently; blank X/Y "
        "fall back to that word's centre."
    )
    # BUG-19: the editor's own key holds the edits as a delta against `seed`, so
    # `seed` must stay the STABLE base — it is reseeded only when the stimulus
    # text changes or a file is restored. Writing the returned frame back into it
    # applies that delta twice, and after a row deletion leaves a gapped index,
    # which `num_rows="dynamic"` cannot add rows to: from there edits land on the
    # wrong rows and rows disappear. Read the edits from the return value only.
    editor_revision = int(st.session_state.get("_author_events_editor_revision", 0))
    events = fixation_table.data_editor(
        seed,
        key=f"author_events_editor_{editor_revision}",
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "fixation_id": st.column_config.NumberColumn(
                "Fixation id",
                disabled=True,
                help="Stable marker identity used to synchronize canvas and table edits.",
            ),
            "order_in_trial": st.column_config.NumberColumn(
                "Order",
                min_value=1,
                step=1,
                help="Reading order. Each fixation needs a unique whole number.",
            ),
            "word_id": st.column_config.NumberColumn(
                "Target word (optional)",
                min_value=1,
                max_value=last_word,
                step=1,
                help=(
                    "Optional measure target, counting from 1. It does not move "
                    "the marker or change X/Y."
                ),
            ),
            "x": st.column_config.NumberColumn(
                "X (px)",
                help="Horizontal screen coordinate; independent of target word.",
            ),
            "y": st.column_config.NumberColumn(
                "Y (px)", help="Vertical screen coordinate; independent of target word."
            ),
            "duration_ms": st.column_config.NumberColumn(
                "Duration (ms)",
                min_value=1,
                help="How long the fixation lasts. It also sets the marker size.",
            ),
        },
        width="stretch",
    )
    selected = st.session_state.get("_author_selected_fixation")
    try:
        effective_events, selected = reconcile_event_table(events, selected)
    except ValueError as exc:
        st.error(f"Fix the event table before these edits can be drawn or saved: {exc}")
        effective_events, selected = reconcile_event_table(seed, selected)
        events_valid = False
    else:
        events_valid = True
    st.session_state["_author_selected_fixation"] = selected

    for problem in event_problems(words, events):
        if not problem.startswith(("Fixation id", "Order")):
            st.warning(problem)
    dropped = unusable_event_rows(words, events)
    if dropped:
        st.caption(
            "Rows without finite X/Y or a valid target are not drawn until corrected."
        )

    canvas_height = max(
        480,
        int(words["y"].max() + words["height"].max() + layout["margin"])
        if not words.empty
        else 480,
    )
    with canvas_panel:
        canvas_event = render_authoring_canvas(
            words,
            effective_events,
            canvas_width=layout["canvas_width"],
            canvas_height=canvas_height,
            selected_fixation_id=selected,
        )
    if canvas_event:
        try:
            updated, selected = apply_authoring_event(
                effective_events,
                canvas_event,
                selected_fixation_id=selected,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["_authored_events_frame"] = updated
            st.session_state["_author_selected_fixation"] = selected
            # A data editor's browser delta is keyed against the frame it first
            # mounted with. Give canvas-authored data a fresh key so the visible
            # table mounts from the new coordinates instead of retaining its old
            # client-side base (the same invariant as BUG-19, in the other
            # direction).
            st.session_state["_author_events_editor_revision"] = editor_revision + 1
            st.rerun()

    st.download_button(
        "💾 Save authoring file",
        data=authoring_json(text, effective_events, layout=layout),
        file_name="authored-scanpath.json",
        mime="application/json",
        disabled=not events_valid,
    )
    return words, authored_fixations(words, effective_events)


#: PRE-1 control defaults. These keys are a wire format — a deep link or a saved
#: config writes them into session state via `url_state` *before* the widgets
#: render, so the widgets must NOT also pass `value=`: Streamlit warns when a
#: keyed widget is given both (BUG-17). A plain `setdefault` is enough here (the
#: expander's contents render every run, so these never mount late — unlike the
#: `persist_state` cases above); see `controls._pin` for that distinction.
#: Keep in sync with the fallbacks in `url_state._restore_plot_config` and
#: `tabs._build_studio_config`.
_PREPROC_DEFAULTS: dict = {
    "global_preproc_enabled": False,
    "global_preproc_short_policy": "Off",
    "global_preproc_short_threshold_ms": 80.0,
    "global_preproc_merge_distance_chars": 1.0,
    "global_preproc_blink_adjacent": True,
}

#: PRE-22 — what `_preprocessing_settings` answers while the feature is hidden:
#: the shape every caller expects, with the pipeline off. Mirrors
#: ``_PREPROC_DEFAULTS`` in values, but keyed the way the settings dict is.
_PREPROC_SETTINGS_OFF = {
    "enabled": False,
    "short_policy": "Off",
    "short_threshold_ms": 80.0,
    "merge_distance_chars": 1.0,
    "discard_blink_adjacent": True,
}


def _preprocessing_settings(host=None) -> dict:
    """Render the PRE-1 controls and return their cache-key-safe settings.

    ``host`` is the 🧹 Preprocessing section of the Data page (DATA-26). Renders
    bare into it — the section heading is the page's, written into the slot above
    these widgets by ``main``.

    It belongs on the page rather than in the Scanpath rail (where UX-38 floated
    putting it) because ``app._preprocessing_settings`` reshapes the frames
    *every* view reads, including Corpus Analysis, which has no rail: a
    dataset-wide control must not be unreachable from one of the views it
    changes.

    **PRE-22**: while the feature is held back from the release, nothing renders
    and the returned settings are the "off" ones — whatever session state holds.
    A saved config or share link from a build that *did* show the panel carries
    `global_preproc_*` values, and honouring them would run a pipeline with no
    control anywhere to see it, undo it, or explain the changed numbers. They are
    ignored rather than cleared, so re-enabling the panel finds them intact.
    """
    if not preprocessing_enabled():
        return dict(_PREPROC_SETTINGS_OFF)
    for key, default in _PREPROC_DEFAULTS.items():
        st.session_state.setdefault(key, default)
    with host if host is not None else st.container():
        enabled = st.toggle(
            "Enable preprocessing",
            key="global_preproc_enabled",
            persist_state="session",
            help="Optional and off by default. Original rows remain available; "
            "excluded rows are soft-marked with a reason.",
        )
        policy = st.selectbox(
            "Short fixations",
            ["Off", "Merge", "Merge then discard", "Discard"],
            key="global_preproc_short_policy",
            persist_state="session",
            disabled=not enabled,
        )
        threshold = st.number_input(
            "Short threshold (ms)",
            min_value=1.0,
            max_value=500.0,
            key="global_preproc_short_threshold_ms",
            persist_state="session",
            disabled=not enabled or policy == "Off",
        )
        distance = st.number_input(
            "Merge distance (characters)",
            min_value=0.25,
            max_value=10.0,
            step=0.25,
            key="global_preproc_merge_distance_chars",
            persist_state="session",
            disabled=not enabled or "Merge" not in policy,
        )
        blink = st.toggle(
            "Exclude blink-adjacent fixations",
            key="global_preproc_blink_adjacent",
            persist_state="session",
            disabled=not enabled,
        )
        if st.button("Recompute preprocessing", disabled=not enabled):
            st.cache_data.clear()
        return {
            "enabled": enabled,
            "short_policy": policy,
            "short_threshold_ms": threshold,
            "merge_distance_chars": distance,
            "discard_blink_adjacent": blink,
        }


def _activate_data_source(data_choice: str, *, preproc_host=None) -> dict:
    """Reset source-scoped state and return the active preprocessing settings.

    ``preproc_host`` is the 🧹 Preprocessing section of the Data page (DATA-26 —
    it was a popover on the top menu bar until the page took it).
    """
    st.session_state["_active_data_source"] = data_choice
    preprocessing = _preprocessing_settings(preproc_host)
    if st.session_state.get("_share_selection_source") != data_choice:
        st.session_state.pop("_share_selection", None)
        st.session_state["_share_selection_source"] = data_choice

    # The trial-filter stash is keyed per *corpus*: a filter narrowed to a value
    # only one corpus has (a text id, a reader) must not ride into the next one,
    # where no trial can satisfy it and nothing says why the pool went empty.
    # `public_dataset_choice` alone is enough for that again — every corpus,
    # prepared benchmark ones included, is its own registry entry — so the extra
    # `eyegenbench_dataset` component R31 needed is gone (DATA-27 Task 11R).
    source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    if st.session_state.get("_filters_for") == source_key:
        return preprocessing

    previous = st.session_state.get("_filters_for")
    stash = st.session_state.setdefault("_filter_stash", {})
    if previous is not None:
        stash[previous] = dict(st.session_state.get("_trial_filters_raw", {}))
    stale_keys = [
        key
        for key in st.session_state
        if isinstance(key, str) and key.startswith("filter_")
    ]
    for key in stale_keys:
        del st.session_state[key]
    st.session_state.pop("_trial_filters", None)
    restored = stash.get(source_key)
    st.session_state["_trial_filters_raw"] = dict(restored) if restored else {}
    st.session_state["_filters_for"] = source_key
    return preprocessing


def main() -> None:
    """Main application entry point.

    Orchestrates the full application workflow:
        1. Configure Streamlit page and custom CSS
        2. Render title and caption
        3. Load and normalize data (words, fixations, optional raw gaze)
        4. Apply user-selected filters (participants, trials, texts)
        5. Render the plot controls (canvas, fonts, visualization settings)
        6. Render the active view (Scanpath Visualization / Corpus Analysis / Data Inspection)

    Data Flow:
        CSV upload → schema inference → normalization → filtering →
        trial combination building → visualization rendering

    UI Structure:
        Sidebar: Data source, filters, canvas settings, viz controls
        Main area: 4 tabs for different views of the data

    Error Handling:
        - Stops execution if schema inference fails
        - Shows warning if filtering eliminates all data
        - Handles missing raw gaze data gracefully
    """
    configure_page()
    # PERF-3: the cache-key memo is scoped to ONE script run — drop last run's
    # entries before anything fingerprints a frame, so a frame rebuilt this run
    # is hashed afresh and last run's frames stop being kept alive.
    reset_fingerprint_memo()
    # Start capturing log records into the in-app debug buffer before any data
    # or plot work runs, so the debug panel (?debug=1) sees this run's logs.
    install_log_capture()
    # Apply deep-link presets BEFORE any widget renders — see _apply_url_preset
    # for the full URL schema. External tools can deep-link into this app with
    # `?source=...&participant=...&trial=...&...` to land on a specific trial
    # with the reviewer's preferred viz settings.
    url_source = _apply_url_preset()
    # ENG-26: desktop/localhost installs remember uploaded datasets, annotations,
    # mappings and view settings across browser refreshes and process restarts.
    # Public deployments never opt in implicitly (there is no user identity with
    # which to isolate the cache). URL presets are applied first and therefore
    # win over restored settings; an explicit ?source= also wins over the stored
    # data-source choice.
    app_url = str(getattr(st.context, "url", "") or "")
    if restore_local_state(
        st.session_state, app_url, protect_data_source=url_source is not None
    ):
        # ENG-30: say it once, where the user is looking. Silently repopulating a
        # session reads as "the app kept my data somewhere" without saying where;
        # the toast points at the menu panel that answers that.
        st.toast(
            "Recovered your last session from this computer — see 💾 Session → "
            "Automatic recovery.",
            icon="↩️",
        )
    if url_source == "onestop" and onestop_data_dir() is not None:
        st.session_state.setdefault("data_source_choice", ONESTOP_CHOICE)
    elif url_source == "multipleye" and multipleye_bundle_dir() is not None:
        st.session_state.setdefault("data_source_choice", MULTIPLEYE_BUNDLE_CHOICE)
    elif url_source == "demo":
        st.session_state.setdefault("data_source_choice", DEMO_CHOICE)
    elif url_source == "synthetic":
        st.session_state.setdefault("data_source_choice", SYNTHETIC_CHOICE)
    elif url_source == "author":
        st.session_state.setdefault("data_source_choice", AUTHOR_CHOICE)
    elif url_source == "onestop_public" and public_datasets_enabled():
        # DATA-3: the public OneStop corpus is shareable. Land on it in the flat
        # picker; _apply_url_preset already seeded onestop_variant/regime/parts.
        st.session_state.setdefault("data_source_choice", ONESTOP_PUBLIC_CHOICE)
    elif url_source == CORPUS_SOURCE_TOKEN:
        # DATA-27 (Task 12): `?source=corpus&corpus=<slug>` names ONE entry of
        # `public_dataset_registry()` — a built-in public corpus or a locally
        # prepared one, identically. Writing the registry label into
        # `data_source_choice` is all the picker's healing path needs: it accepts
        # the label as an entry and collapses it back to PUBLIC_DATASETS_CHOICE,
        # re-stashing it on `public_dataset_choice` itself. Seeding that key here
        # as well would be a second copy of the same answer — and a `setdefault`
        # of it is dead anyway, since a recovery-cached value (the only case
        # where seeding could matter) is exactly what `setdefault` won't replace.
        #
        # The resolution is gated on the feature flag, but the *message* is not:
        # a build with public datasets switched off can't open the corpus either,
        # and saying nothing at all would leave the recipient with a link that
        # silently did nothing.
        slug = str(st.query_params.get(PARAM_CORPUS) or "")
        corpus_choice = (
            corpus_choice_for_slug(slug) if public_datasets_enabled() else None
        )
        if corpus_choice:
            st.session_state.setdefault("data_source_choice", corpus_choice)
        elif slug:
            # The common case, not an edge case: the recipient has no prepared
            # bundle, or a different subset of one. Say which corpus was named
            # and leave the picker exactly where it was — never wedge it, and
            # never silently open a different corpus. The remedy names what is
            # actually clickable: the bundle directory input renders *inside* a
            # benchmark corpus entry, so it can only be reached by selecting one
            # of those entries first (with no bundle at all, that is the single
            # "set up a local bundle" entry the registry offers in their place).
            st.warning(
                f"This link opens the corpus `{slug}`, which isn't available "
                "here. To get it, open **Data source** and select a harmonised "
                f"benchmark corpus — or **{picker_name_for(BENCHMARK_SETUP_CHOICE)}** "
                "if you have "
                "none yet — then point its *Data directory* at a prepared bundle "
                "containing this corpus. The link's view settings still apply to "
                "whatever you open."
            )
    elif url_source == "upload":
        st.session_state.setdefault("_show_upload_wizard", True)

    # Chrome first, page heading second: Streamlit's native top nav, then the
    # settings menu bar, then the title.
    #
    # AFTER `restore_local_state`, deliberately: `render_nav` resolves the active
    # view and writes `main_nav`, so running it earlier would pin the view to the
    # router's default before the recovery cache could restore the one the user
    # was last on. BEFORE any data loading, equally deliberately: the loaders'
    # directory inputs, download buttons and column-mapping panels fill the bar's
    # popovers by `host=`, so those slots have to exist first — the same
    # reserve-then-fill discipline the former sidebar containers had.
    seed_debug_mode()  # UX-37: a legacy ?debug=1 link pre-arms the Help toggle.
    # UX-62: before the nav — `st.logo` writes into the same header strip
    # `st.navigation` draws into, and has to be there when it renders.
    render_app_logo()
    # Active top-level view, resolved BEFORE `render_top_menu` so the BUG-31
    # wizard hold-override below can land before that call rather than after it
    # (see the note there — it used to also gate the 💾 Session *page*, which
    # UX-100 turned back into a popover).
    active_view = render_nav()

    # BUG-31 — navigating away mid-wizard used to land the user on the *half-built*
    # dataset: `resolve_data_source` reports `UPLOAD_CHOICE` for the whole
    # run while the wizard is open, whatever the view, so `main` returned early
    # with "this dataset isn't set up yet" over a session that still held every
    # finished dataset. It read as data loss; it was an unfinished wizard.
    #
    # While the wizard is open the 🗂️ Data page is what renders, wherever the nav
    # says the user is — and the wizard asks whether to discard. It has to keep
    # **rendering** for the question to be worth asking: Streamlit drops a
    # widget's key at the end of any run in which it did not render, and
    # `st.file_uploader` is the one widget `persist_state="session"` cannot cover
    # (ENG-36), so a single run spent drawing Scanpath throws the uploaded files
    # away before the user can be asked about them.
    #
    # Deliberately **no navigation of our own** — not a `switch_to_view`, not a
    # `main_nav` write. Both end in `st.switch_page`, which aborts the run where
    # it is called, and an aborted run renders no wizard: the fix would destroy
    # exactly what it exists to protect. So the nav highlight is simply allowed to
    # sit on the view the user picked while the page under it asks the question,
    # and *Discard* then needs no navigation at all — the router is already there.
    #
    # BUG-36 follow-up: this block used to run *after* `render_top_menu`, so
    # choosing "Keep setting up" correctly held the `if/elif` dispatch below on
    # Data but did nothing for the 💾 Session *page*, which `render_top_menu`
    # drew itself from the *raw* nav click, earlier in the run. Resolving the
    # override here and handing it in as `active_view=` closed that gap.
    # UX-100 retired that page — Session is a popover, which never becomes the
    # active view — but the ordering still matters for the dispatch below.
    if st.session_state.get("_show_upload_wizard"):
        if (
            active_view != _VIEW_DATA
            and st.session_state.get(WIZARD_STAY_KEY) != active_view
        ):
            st.session_state[WIZARD_LEAVE_KEY] = active_view
        else:
            st.session_state.pop(WIZARD_LEAVE_KEY, None)
        active_view = _VIEW_DATA

    menu = render_top_menu(show_debug=debug_enabled(), active_view=active_view)
    _render_about_panel(menu.title)

    def _fill_recovery_cache_panel(backup_renderer=None) -> None:
        """Serve the 💾 Session dialog, once, on whichever path we leave by.

        The name is the panel it used to fill; UX-100 turned that panel into the
        modal that now holds all four blocks. The *timing* is unchanged and is
        the reason this is a closure rather than one call in the epilogue:
        🗄️ Automatic recovery reports what **this run** just persisted, so it has
        to come after `save_local_state` — which the early returns never reach.
        Each of them calls this instead, and the epilogue calls it for the
        ordinary path, so exactly one runs per script run. That is what keeps the
        widgets inside single widgets.

        BUG-28 is the reason ``backup_renderer`` is optional: `main` returns
        early on every path where the dataset can't be drawn — the wizard
        mid-flight, a mapping that is incomplete or rejected, an empty pool — and
        those are exactly the states someone opens Session *in*. They get the
        recovery cache, the reset and the debug tools; only the JSON backup,
        which needs a figure to describe, says why it is not there.
        """
        maybe_show_session(app_url, backup_renderer)

    # First-visit welcome tour. After the URL presets, so embeds and
    # deep-linked sessions can suppress it — but BEFORE the heavy data/plot
    # work, so the welcome streams to the browser immediately instead of
    # after the full first render. Replay clicks arm the tour in the button's
    # on_click callback, which runs before this point in the rerun.
    maybe_show_welcome_tour()
    render_spotlight_tour()
    # UX-40: task-oriented tutorials share the spotlight mechanism but keep
    # their own progress and do not inherit the welcome tour's opt-out.
    render_use_case_tutorial()
    # UX-39: arm the title's easter egg. After the tour/tutorial renders, because
    # its suppression reads the `tour_mode` / `tutorial_active` those set — and it
    # doesn't care about DOM order, being a height-0 script that retries until the
    # heading has hydrated.
    render_easter_egg()
    # UX-15: same deal for the FAQ dialog — the ❓ Help menu button that arms it
    # renders at the bottom of this function, so serving it here is what keeps
    # the modal from waiting out the whole rerun. Ditto ℹ️ About, a dialog since
    # the menu bar made it a popover inside a popover.
    maybe_show_faq()
    maybe_show_about()
    maybe_show_tutorial_library()

    # `active_view` was already resolved above, before `render_top_menu` drew
    # its Session-page panel from it (including the BUG-31 wizard hold-override
    # — see the note there); the dispatch below reuses the same value.

    # Switching view is a full rerun — data load, filters, then a page of fresh
    # figures — and Streamlit leaves the OLD view painted until the new run
    # overwrites each element. So a click on "Corpus Analysis" left the scanpath
    # sitting there, looking like nothing had happened. Paint a bridge the
    # moment we know the view changed: it lands high on the page, before the
    # slow work, so the click gets an immediate answer. Cleared just before the
    # real view renders. Same pattern (and reasoning) as `_finalizing_bridge`
    # above — see ENG-36 for why the message keeps its own line above the
    # skeleton rather than relying on a bare skeleton to explain itself.
    #
    # The container is created on EVERY run, not only on a switch, and only
    # *filled* on a switch. Streamlit reconciles the element tree by position:
    # a run that skipped creating it left the previous run's banner + skeleton
    # sitting there unclaimed, so the "Loading…" never went away. Always
    # claiming the slot means the next run overwrites it with an empty
    # container, which is what clears it.
    #
    # It has to be an `st.empty()` placeholder, not a plain container:
    # `container.empty()` *appends* an empty child, it does not drop the
    # children already written into it, so the banner and skeleton survived the
    # clear below and sat above the finished page until some later rerun
    # happened to redraw the slot. A placeholder holds exactly one element — a
    # child container when there is something to say, nothing after `.empty()`.
    _view_bridge = st.empty()
    if st.session_state.get("_last_rendered_view") not in (None, active_view):
        _bridge_box = _view_bridge.container()
        _bridge_box.info(f"Loading {view_label(active_view)}…", icon="⏳")
        _bridge_box.skeleton(height=420)
    else:
        _view_bridge = None
    st.session_state["_last_rendered_view"] = active_view

    # DATA-26 — the **Data** page ("Data Management"). One place for
    # everything about the dataset itself, instead of a ⚙️ Configure menu group
    # at the top and a 🔎 Data Inspection subtab on the far side of the Scanpath
    # view asking the same questions at two points in the pipeline.
    #
    # The page is built on EVERY run and merely hidden when another view is
    # active (`DATA_PAGE_OFFSCREEN_KEY` → `display: none` in styles.py). That is
    # not laziness: the slots below are filled by the loaders' directory input,
    # ⬇ Download button, source options and column-mapping selectboxes, all of
    # which *drive* `prepare_data` on every rerun — and Streamlit drops the key
    # of a widget that did not render. Rendering-then-hiding keeps the popovers'
    # every-run semantics exactly, so this stays a re-host rather than a rewrite
    # of every loader into a render/resolve pair.
    #
    # DATA-35 split it into **two screens**, both built every run and switched by
    # key for the same reason the page itself is (above):
    #
    #   Overview  📂 Available datasets (the table + ➕ Add dataset)
    #             🔎 What's in the open dataset
    #   Editor    ✏️ Edit dataset — everything that *configures* the dataset:
    #             description / options / data location, column mapping,
    #             recording setup, trial identity, stimulus images, the two
    #             metadata tables, preprocessing.
    #
    # The overview used to carry all of it in one scroll, which put a forty-row
    # table, twenty mapping selectboxes and three uploaders on the screen you
    # visit to answer "which datasets do I have?". Sub-slots are reserved in
    # page order and filled at whatever point of the load reaches them
    # (Streamlit lays containers out in creation order).
    data_view = active_view == _VIEW_DATA
    setup_page = st.container(
        key=DATA_PAGE_KEY if data_view else DATA_PAGE_OFFSCREEN_KEY
    )
    # UX-66: while the add-dataset wizard is up it owns the page and carries its
    # own sticky title, so the page's header and its stage subheading would be a
    # second and third title above it.
    wizard_owns_page = bool(st.session_state.get("_show_upload_wizard"))
    editing = (
        bool(st.session_state.get(DATASET_EDITOR_OPEN_KEY)) and not wizard_owns_page
    )
    overview_page = setup_page.container(
        key=DATA_OVERVIEW_OFFSCREEN_KEY if editing else DATA_OVERVIEW_KEY
    )
    editor_page = setup_page.container(
        key=DATA_EDITOR_KEY if editing else DATA_EDITOR_OFFSCREEN_KEY
    )
    if data_view and not wizard_owns_page:
        overview_page.header("Data Management")
        # UX-52 — peer sections, one heading level, one divider between each.
        overview_page.divider()
        # UX-77: the section lists every dataset (#UX-54 made it a table), so it
        # is named for that rather than for the one *source* it used to pick.
        # DATA-35 moved ➕ Add dataset off the heading's line and under the
        # table, on the user's call: it is the action you reach for *after*
        # reading the list and not finding what you wanted, so it belongs at the
        # end of the list rather than above it. Its slot is reserved beside the
        # table below; the button itself is filled once `data_choice` is known.
        overview_page.subheader("📂 Available datasets")
    setup_source_slot = overview_page.container()
    # The editor's own header bar — the ✏️ Edit dataset screen's title and its
    # way back, filled below once the dataset's display name is known.
    editor_head_slot = editor_page.container()
    description_slot = editor_page.container()
    source_options_slot = editor_page.container()
    data_location_slot = editor_page.container()
    # The add-dataset wizard takes the whole page, so its slot is the page's,
    # not either screen's.
    setup_wizard_slot = setup_page.container()
    # UX-52 round 2 — "what's in this dataset" comes **before** the mapping, on
    # the user's call. It breaks pipeline order deliberately: the counts are the
    # first thing you want after choosing a source ("did it load, and is it the
    # right size?"), and the mapping is what you scroll to when the answer looks
    # wrong. DATA-35 kept that order across the split: the counts are the
    # overview's second half, and the mapping opens the editor.
    setup_body_slot = overview_page.container()
    # Keyed → the stable `.st-key-…` selectors the "Load and verify a dataset"
    # tutorial spotlights (UX-40), alongside `tutorial_data_inspection` above.
    column_mapping_slot = editor_page.container(key="tutorial_column_mapping")
    # The heading belongs to the *section*, not to any one of its three modes —
    # mode A's panels are written into the body by `prepare_data` during the
    # load, long before the dispatch below picks a mode, so the title needs a
    # slot of its own above them (see tabs._render_column_mapping_section).
    mapping_head_slot = column_mapping_slot.container()
    mapping_body_slot = column_mapping_slot.container()
    # Raw tables for a dataset whose mapping is still broken. Its own slot,
    # *below* the mapping editor, which is the control that fixes them.
    unmapped_slot = editor_page.container()
    # UX-52 round 3 — the VAL-7 trial-identity verdict is its own section, not a
    # `#####` item inside "What's in this dataset" (the user's call). It carries
    # a *verdict* — sometimes a warning — and the fix it names is a change to the
    # Trial ID mapping directly above it, so it belongs at the same level as the
    # thing it judges rather than buried under the counts.
    # Keyed → the `.st-key-…` selector the "Load and verify a dataset" tutorial
    # spotlights, alongside its siblings above and below.
    setup_identity_slot = editor_page.container(key="tutorial_trial_identity")
    # VIZ-14: local stimulus-image paths sit beside the other optional attached
    # metadata, immediately before the participant table.
    setup_stimulus_slot = editor_page.container(key="tutorial_stimulus_images")
    # DATA-20 §1 — the participant-level metadata table. After the mapping (it
    # joins on the reader id the mapping just settled).
    setup_metadata_slot = editor_page.container(key="tutorial_participant_metadata")
    setup_preproc_slot = editor_page.container(key="tutorial_preprocessing")

    # Data source selection. UX-25: only the *resolution* happens here (it must
    # precede the load); the picker itself renders in the main view — on the
    # Scanpath "Filter by" row, at the top of the Corpus view, or (DATA-26) in
    # the page slot above. The resolver takes the same slot because while the
    # add-dataset wizard is open it renders a "✕ Cancel" bar *instead of* a
    # picker, and rendering both would duplicate the `tour_grp_data_source` key.
    from scanpath_studio.wizard import _enter_add_data_wizard

    data_choice = resolve_data_source(host=setup_source_slot)
    # UX-54: the page lists every dataset as a *table* — one row each, sortable,
    # with the counts beside the name and the per-row actions in the row they
    # belong to. Reserved here (so it keeps its place at the top of the page)
    # and filled after the load, which is the first point this run's counts for
    # the open dataset exist.
    dataset_table_slot = setup_source_slot.container()
    # DATA-35: under the table, not on the heading's line. Left-aligned in a
    # narrow column so a stretched button doesn't run the width of the page.
    add_dataset_slot = None
    if data_view and not wizard_owns_page:
        add_dataset_slot, _ = setup_source_slot.columns([1, 4])
    if data_view and add_dataset_slot is not None and data_choice != UPLOAD_CHOICE:
        # UX-64 took ➕ Add data off the Scanpath row and made this page the only
        # way in — so the way in has to *be* here. Without this button
        # `_enter_add_data_wizard` would have no trigger at all and uploading
        # would be unreachable. An `on_click` callback, not an inline handler:
        # it reassigns `data_source_choice`, which only lands before the widgets
        # instantiate. UX-77 put it on the section heading's line; DATA-35 moved
        # it under the table.
        add_dataset_slot.button(
            "➕ Add dataset",
            key="add_data_btn",
            on_click=_enter_add_data_wizard,
            help="Upload your own eye-tracking tables.",
            width="stretch",
            type="primary",
        )
    if data_view and editing:
        _render_dataset_editor_bar(editor_head_slot, data_choice)
    # PRE-22: the section is held back from this release — heading, caption and
    # controls all come from behind the same gate, so the page has no gap where
    # a hidden stage used to be.
    if data_view and preprocessing_enabled():
        setup_preproc_slot.divider()
        setup_preproc_slot.subheader("🧹 Preprocessing")
        setup_preproc_slot.caption(
            "Optional soft exclusion and merging of short fixations, applied to "
            "every view. Off by default; original rows remain available."
        )

    preproc_settings = _activate_data_source(
        data_choice, preproc_host=setup_preproc_slot
    )
    # Just-finalized upload: paint a "loading" bridge into the main area now so it
    # repaints over the wizard (instead of the wizard lingering until the slow
    # first figure finishes). Cleared just before the tabs render below.
    #
    # ENG-36: the message keeps its own line — a bare skeleton says "loading" but
    # not *what*, and the wizard has just closed under the user — while
    # `st.skeleton` (1.59) reserves the height the plot is about to take, so the
    # page doesn't reflow when the figure lands. Standalone mode, not the `with`
    # form: the wait spans everything between here and the tab render below, not
    # one block.
    # An `st.empty()` placeholder for the same reason as the view bridge above:
    # `.empty()` on a plain container adds a child instead of clearing one.
    _finalizing_bridge = None
    if st.session_state.pop("_wizard_finalizing", False):
        _finalizing_bridge = st.empty()
        _finalizing_box = _finalizing_bridge.container()
        _finalizing_box.info("✅ Dataset added — loading your scanpaths…", icon="⏳")
        _finalizing_box.skeleton(height=420)
    # (DATA-9's ordered source-config group — description · options · data
    # location · column mapping — is now the top of the Data page reserved
    # above. VIZ-31 had already moved "Experimental Setup" out of it: monitor
    # geometry, fonts, text colour and plot background are figure settings, and
    # they render in the Scanpath rail beside the layers they restyle.)

    # Load + map core data. The **Upload** source renders each table as an
    # [upload box → mapping] group on the 🗂️ Data page (words, fixations, raw gaze) and
    # normalizes inline; every other source auto-detects (or, for public datasets,
    # renders standalone mapping panels) via prepare_data. Keep the raw frames
    # around so we can show them if the mapping isn't ready.
    #
    # Decide which participant (if any) the OneStop loader should fast-path to.
    #   1. A URL deep link (?participant=) → load just that pid's shard (embedded
    #      review use case); captured once so the live selector can't change it.
    #   2. Otherwise, if the full CSV bundle exists → load the whole corpus once
    #      (participant=None) and let in-app participant switching just *filter*
    #      it — so changing participant is instant instead of re-invoking the
    #      loader on every change.
    #   3. Shards-only setup with no full bundle → fall back to lazy per-pid
    #      loading driven by the selector (the ~60 GB corpus can't be held whole).
    deeplink_pid = st.session_state.get("_deeplink_participant")
    if deeplink_pid:
        deep_link_pid = deeplink_pid
    elif data_choice == ONESTOP_CHOICE and not onestop_full_bundle_exists():
        deep_link_pid = st.session_state.get("single_participant")
    elif data_choice == MULTIPLEYE_BUNDLE_CHOICE:
        # MultiplEYE has no full-corpus bundle: each session is its own shard, so
        # the live participant selector fast-paths to one session's shards too.
        deep_link_pid = st.session_state.get("single_participant")
    else:
        deep_link_pid = None
    raw_gaze_df: pd.DataFrame | None = None
    # Did this load already draw the editable pre-normalization mapping panels
    # into the page's Column mapping section? (Mode A — see the dispatch below.)
    mapping_editor_rendered = False
    # Start each load with a clean column-mapping stash; each branch below
    # records the schema it used for the Data page's mapping section.
    _reset_active_mapping()
    if data_choice == UPLOAD_CHOICE:
        # Hybrid setup wizard: a guided flow on first load, then a compact
        # collapsed "Data & mapping" panel. DATA-26 made it the **Data page's
        # add-a-dataset mode** — adding a dataset *is* setup, and a wizard that
        # lived anywhere else would re-create the two-places-for-one-job problem
        # the page exists to fix. It still owns the page while active: there is
        # nothing for the other views to draw until it finishes, so `main`
        # returns here exactly as before. `_enter_add_data_wizard` requests the
        # Data view when the ➕ button is clicked, so the user is already here.
        wizard_active = not st.session_state.get("setup_complete", False)
        # Imported lazily (not at module top) to avoid the app⇄wizard import cycle.
        from scanpath_studio.wizard import _render_data_setup

        with setup_wizard_slot:
            setup = _render_data_setup(active=wizard_active)
        words_df, fixations_df = setup.words, setup.fixations
        raw_gaze_df = setup.raw_gaze
        raw_words_df, raw_fixations_df = setup.raw_words, setup.raw_fixations
        mapping_problems = setup.problems
        if wizard_active:
            _render_offpage_setup_notice(data_view)
            _fill_recovery_cache_panel()
            return
    elif data_choice == AUTHOR_CHOICE:
        words_df, fixations_df = _render_authoring_source()
        raw_words_df, raw_fixations_df = words_df, fixations_df
        raw_gaze_df = pd.DataFrame()
        mapping_problems = []
    elif data_choice in st.session_state.get("_datasets", {}):
        # A dataset the user uploaded earlier and named — its frames were
        # normalized once by the wizard and stored in session, so switching back
        # to it is instant (no re-upload, no re-mapping). See _render_data_setup's
        # finalize and resolve_data_source.
        stored = st.session_state["_datasets"][data_choice]
        words_df, fixations_df = stored["words"], stored["fixations"]
        raw_gaze_df = stored["raw_gaze"]
        raw_words_df, raw_fixations_df = words_df, fixations_df
        mapping_problems = []
        # Re-publish this dataset's chosen filter fields so the trial-filter
        # funnel offers the same dynamic conditions.
        st.session_state["wizard_filter_fields"] = list(stored.get("filter_fields", []))
        # Restore the composite trial-id components (session-only state) so the
        # trial picker renders its Participant/Text cascade — every other load
        # path sets this, but the stored branch doesn't re-normalize. Without it
        # the picker would inherit whatever source was loaded last.
        composite = list(stored.get("composite_trial_columns") or [])
        st.session_state["_composite_trial_columns"] = composite or None
        # Re-publish the stored column mapping so the Data Inspection tab shows
        # how this dataset's columns were mapped (the wizard isn't re-run here).
        for table, schema in (stored.get("schemas") or {}).items():
            _stash_active_mapping(table, schema)
    else:
        # Built-in sources (demo / synthetic / OneStop / public) auto-detect
        # their mapping, so they skip the wizard entirely. Drop any wizard filter
        # fields left over from a prior upload so the funnel falls back to the
        # built-in default conditions for these sources.
        st.session_state.pop("wizard_filter_fields", None)
        # Re-propose the column mapping when the monitor-defining source changes.
        # The `col_map_*` widget keys persist across reruns, so a previous corpus'
        # mapping sticks to the next one — e.g. PoTeC maps Trial → `text_id`, and
        # since MultiplEYE *also* has a `text_id` column the stale-column reset
        # (which only fires when a mapped column vanishes) wouldn't catch it, so
        # MultiplEYE's per-page `trial_id` was ignored and every page collapsed
        # into one stimulus-level trial. Clearing on source change lets each
        # corpus auto-detect its own mapping; same-source reruns (and restores)
        # keep their keys. Mirrors the canvas re-seed in render_canvas_controls.
        #
        # Two harmonised benchmark corpora share one schema, so switching between
        # them re-proposes a mapping that auto-detects to the same thing — the
        # cost of one key covering every corpus, and the same trade every other
        # pair of sources already makes.
        source_key = (data_choice, st.session_state.get("public_dataset_choice"))
        if st.session_state.get("_colmap_seeded_for") != source_key:
            reset_column_mapping()
            st.session_state["_colmap_seeded_for"] = source_key
        raw_words_df, raw_fixations_df = load_words_and_fixations(
            data_choice,
            participant=deep_link_pid,
            # DATA-9 ordered group: a public dataset renders its caption / source
            # options / data-location controls into these reserved sub-slots.
            description_host=description_slot,
            options_host=source_options_slot,
            location_host=data_location_slot,
        )
        declared_word_schema, declared_fix_schema = declared_schemas_for(data_choice)
        words_df, fixations_df, mapping_problems = prepare_data(
            raw_words_df,
            raw_fixations_df,
            # Show the Column-mapping panels for public datasets AND the Bundled
            # Demo (DATA-8) so the re-mapping capability is discoverable on the
            # default first-load source; pre-filled with auto-detection, so an
            # untouched mapping normalizes identically.
            allow_override=(data_choice in (PUBLIC_DATASETS_CHOICE, DEMO_CHOICE)),
            # Mode A of the Data page's one Column mapping section (DATA-26).
            mapping_host=mapping_body_slot,
            # A prepared benchmark corpus publishes its schema; auto-detection
            # must not re-guess it from the publisher's leftover columns. The
            # panels stay editable — this only changes what they start at.
            declared_word_schema=declared_word_schema,
            declared_fix_schema=declared_fix_schema,
        )
        mapping_editor_rendered = data_choice in (PUBLIC_DATASETS_CHOICE, DEMO_CHOICE)
    if mapping_problems:
        # A required column is still unmapped. Rather than halt the whole app
        # (which hid the data the user needs to choose the mapping), show the
        # raw tables on the Data page, right under the still-editable Column
        # mapping section — and, from any other view, say where that page is.
        with unmapped_slot:
            _render_unmapped_view(raw_words_df, raw_fixations_df, mapping_problems)
        _render_offpage_setup_notice(data_view)
        _fill_recovery_cache_panel()
        return

    # VIZ-14: local/desktop users can attach stimulus screenshots without
    # adding an image_path column to their data. This intentionally stays out
    # of public deployments and share links because it contains machine-local
    # filesystem information; the same resolver is available through the API
    # and CLI for reproducible headless renders.
    if local_filesystem_enabled():
        with setup_stimulus_slot:
            st.divider()
            st.subheader("🖼️ Stimulus images")
            image_root = st.text_input(
                "Image folder",
                key="stimulus_image_root",
                placeholder="/path/to/stimulus-images",
                help="Local folder containing one image per text or trial.",
            ).strip()
            image_pattern = st.text_input(
                "Filename pattern",
                key="stimulus_image_pattern",
                value="{text_id}.png",
                help="Use table fields such as {text_id}, {trial_id}, or "
                "{participant_id}; subfolders are supported.",
            ).strip()
            if image_root:
                try:
                    words_df = resolve_stimulus_image_paths(
                        words_df, image_root, image_pattern
                    )
                    fixations_df = resolve_stimulus_image_paths(
                        fixations_df, image_root, image_pattern
                    )
                    found = sum(
                        frame.get("image_path", pd.Series(dtype=object))
                        .dropna()
                        .astype(str)
                        .map(os.path.isfile)
                        .sum()
                        for frame in (words_df, fixations_df)
                    )
                    st.caption(f"Matched {int(found):,} table rows to local images.")
                except ValueError as exc:
                    st.error(str(exc))

    # Optional raw gaze: the Upload source already mapped + normalized it above;
    # every other source loads it here (bundled demo sample, OneStop uploader).
    if raw_gaze_df is None:
        raw_gaze_df = load_raw_gaze_data(
            data_choice, host=data_location_slot, notices=menu.notices
        )

    if preproc_settings["enabled"]:
        fixations_df, preproc_report = preprocess_fixation_stage(
            words_df, fixations_df, preproc_settings
        )
        st.session_state["_preprocessing_report"] = preproc_report
        st.session_state["_preprocessing_settings"] = dict(preproc_settings)
        suspicious = (
            preproc_report[
                preproc_report["suspicious_word_load"].fillna(False).astype(bool)
            ]
            if "suspicious_word_load" in preproc_report
            else preproc_report.iloc[0:0]
        )
        if not suspicious.empty:
            st.warning(
                f"Data quality: {len(suspicious)} trial(s) put at least 12 "
                "fixations on one word. Check stimulus alignment or line assignment."
            )
    else:
        st.session_state["_preprocessing_report"] = pd.DataFrame()
        st.session_state["_preprocessing_settings"] = dict(preproc_settings)

    # UX-7(b): if the selected corpus isn't on disk, say so here — in the main
    # area, where the (demo) plot the user is actually looking at is — rather than
    # leaving it to a line on the 🗂️ Data page they may never open.
    _render_dataset_unavailable()

    # Whole-dataset frames, captured BEFORE the trial-filter funnel —
    # the Bulk Export tab's "Export the whole dataset" option exports these,
    # ignoring the current filters.
    words_all, fixations_all = words_df, fixations_df
    # DATA-20: every reader in the dataset, before any narrowing — what the
    # participant-metadata join is reported against.
    #
    # Gated and cached, both deliberately. `participant_ids` is a `.unique()`
    # over *both unfiltered corpus frames* — ~0.5 s on full OneStop — and on
    # the default path (no table attached, not on the Data page) the answer is
    # thrown away, so an unconditional call put half a second on every rail
    # toggle and every ◀ ▶ step for nothing. The fingerprints are the ones
    # computed just below for the identity report, so the cache key is free.
    participants_all: list = []
    if data_view or metadata_mod.active() is not None:
        participants_all = _cached_participant_ids(
            words_all,
            fixations_all,
            cache_key=(
                frame_fingerprint(words_all),
                frame_fingerprint(fixations_all),
            ),
        )
        _refresh_participant_metadata(participants_all)

    # UX-37: the dataset is loaded and normalized — one line saying *what*, and
    # only when it changes. A rerun re-executes all of this, so an unconditional
    # log here would print on every widget touch anywhere in the app.
    log_state_change(
        "dataset",
        (str(data_choice), len(words_all), len(fixations_all)),
        "Dataset ready",
        source=data_choice,
        words=len(words_all),
        fixations=len(fixations_all),
    )

    # VAL-7: does one `trial_id` actually cover several readings? A Trial ID
    # mapping that under-specifies concatenates them, and the figure renders as
    # an ordinary scanpath with a lot of regressions — nothing looks wrong. Run
    # on the *unfiltered* frames: this is a property of the mapping, not of the
    # current filter. The full evidence table is in 🔎 Data Inspection; here it
    # gets one line, because the column name is the remedy.
    # PERF-6: screen a sample by default; the Data page's "Check every trial"
    # button sets this flag, which is what asks for the full census.
    identity_sample = (
        None if st.session_state.get(TRIAL_IDENTITY_FULL_KEY) else TRIAL_IDENTITY_SAMPLE
    )
    identity_report = _cached_trial_identity_report(
        words_all,
        fixations_all,
        cache_key=(frame_fingerprint(words_all), frame_fingerprint(fixations_all)),
        sample_trials=identity_sample,
    )
    st.session_state["_trial_identity_report"] = identity_report
    identity_warning = trial_identity_warning(identity_report)
    if identity_warning:
        menu.notices.warning(
            f"{identity_warning} The evidence is on the 🗂️ **Data** page, "
            "under **Trial identity**.",
            icon="⚠️",
        )

    # Trial-level filtering / grouping: narrow by participant, by condition
    # (Hunting/Gathering, difficulty, first/repeated reading, correctness), and by
    # annotation state (favorites / tags) before anything downstream sees the
    # data. The controls now live in the Scanpath tab's Trial Selection panel
    # (rendered there via render_trial_filters); here we just read the last
    # selection from session_state so filtering stays global across every view.
    trial_filters = read_trial_filters()
    words_df, fixations_df = filter_trials(
        words_df,
        fixations_df,
        participants=trial_filters["participants"],
        metadata=trial_filters["metadata"],
        ranges=trial_filters.get("ranges"),
    )
    # DATA-29: a trial-grain metadata narrowing is already `(participant_id,
    # trial_id)` keys, so it applies through `filter_to_keys` rather than
    # `filter_trials` — the table is never broadcast onto the frames, which is
    # DATA-20's rule and the reason this design holds at either grain. `None`
    # means no constraint; an empty set legitimately narrows to nothing.
    trialmeta_keys = trial_filters.get("trial_keys")
    if trialmeta_keys is not None:
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, trialmeta_keys)
        raw_gaze_df = filter_frame_to_keys(raw_gaze_df, trialmeta_keys)
    # BUG-12: the raw-gaze samples table has to travel through the same
    # annotation filter as words + fixations, or a sample row for an unstarred
    # trial survives "⭐ Favorites only" — which also kept the all-three-empty
    # guard below from ever firing, leaving the UX-7 guidance panel unreachable.
    raw_gaze_scoped = raw_gaze_df
    if (
        trial_filters["favorites_only"]
        or trial_filters["required_tags"]
        or trial_filters["excluded_tags"]
    ) and not (fixations_df.empty and words_df.empty and raw_gaze_scoped.empty):
        # Trials live in fixations normally; for words-only datasets the words
        # frame carries them, and for raw-gaze-only ones the samples table —
        # union all three so every frame's trials get judged by the filter.
        present_keys = (
            trial_keys(words_df)
            | trial_keys(fixations_df)
            | trial_keys(raw_gaze_scoped)
        )
        kept = set(
            filter_keys(
                list(present_keys),
                favorites_only=trial_filters["favorites_only"],
                required_tags=trial_filters["required_tags"],
                excluded_tags=trial_filters["excluded_tags"],
            )
        )
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, kept)
        raw_gaze_scoped = filter_frame_to_keys(raw_gaze_scoped, kept)

    # Apply filters (participant/trial/text selection). For a raw-gaze-only
    # dataset (no words/fixations) derive the participant/trial options from the
    # raw gaze so it isn't filtered away (filter_raw_gaze drops on empty lists).
    filters = default_filters(
        words_df, fixations_df if not fixations_df.empty else raw_gaze_scoped
    )
    words_filtered, fixations_filtered = filter_data(words_df, fixations_df, filters)

    # Filter raw gaze data to match selected participants/trials
    if not raw_gaze_scoped.empty:
        raw_gaze_filtered = filter_raw_gaze(
            raw_gaze_scoped,
            filters.get("participants", []),
            filters.get("trials", []),
        )
        if raw_gaze_filtered.empty:
            # Informational, not an error: the loaded raw-gaze samples just
            # don't cover any trial in the current filter (raw gaze typically
            # exists for only a subset of trials). The overlay is optional.
            menu.notices.caption(
                f"ℹ️ The loaded raw-gaze samples ({len(raw_gaze_df):,} rows) don't "
                "overlap the current trial filter, so the raw-gaze overlay is "
                "unavailable here."
            )
    else:
        raw_gaze_filtered = pd.DataFrame()

    # Check for empty data after filtering. A single empty frame is fine
    # (words-only / fixations-only / raw-gaze-only datasets); all empty means the
    # filters removed everything.
    if words_filtered.empty and fixations_filtered.empty and raw_gaze_filtered.empty:
        _render_empty_after_filtering(words_all, fixations_all, trial_filters)
        _fill_recovery_cache_panel()
        return

    # Build trial combinations for selection UI — from fixations normally, then
    # words (words-only datasets), then raw gaze (raw-gaze-only datasets).
    combos, _, _ = build_combo_options(
        fixations_filtered
        if not fixations_filtered.empty
        else words_filtered
        if not words_filtered.empty
        else raw_gaze_filtered
    )
    # DATA-20 §3 — the *one* place the participant table is joined onto anything.
    # `combos` is one row per trial (tens to thousands), so this is the cheap
    # projection the item asks for rather than a broadcast across every fixation
    # — and it is enough: trial sorting, the trial labels and everything else
    # downstream discovers its columns from this frame, with no allowlist to
    # extend per surface.
    combos = metadata_mod.project(metadata_mod.active(), combos)
    # DATA-29 §3 — and the one place the *trial* table is joined, onto the same
    # small frame. Everything downstream (the chip picker, trial sorting, Data
    # Inspection, export) discovers its columns from `combos`, so this single
    # left-join is what makes a trial field behave like a field in the data —
    # again without broadcasting the table onto words or fixations.
    combos = metadata_mod.project_trials(metadata_mod.active_trials(), combos)

    # Land a shared/deep link on its exact `?trial_id=` (once) now that combos
    # exist — see _apply_url_trial_selection. Runs before the rail/tab widgets
    # render so the seeded selection is picked up as their initial value.
    _apply_url_trial_selection(combos)
    # Same hop, from inside the app: a "go to this trial" button in a Corpus
    # Analysis table parks its request in a callback (before combos exist) and
    # it is applied here — see url_state.request_trial (ENG-36).
    _apply_pending_trial_selection(combos)

    # Restore settings + annotations from an uploaded config JSON BEFORE the
    # rail widgets render, so they pick up the saved values (see
    # _apply_url_preset for the same preset-then-render mechanism). The uploader
    # lives in the "💾 Save & restore" panel below; its file persists across reruns.
    _apply_uploaded_plot_config(combos, fixations_filtered)

    # Canvas and visualization controls (the Scanpath rail). For a raw-gaze-only dataset,
    # size the canvas from the gaze extent and default the raw-gaze overlay on —
    # it's the only layer there, so the plot would otherwise be blank.
    raw_gaze_only = words_filtered.empty and fixations_filtered.empty
    if raw_gaze_only and "global_show_raw_gaze" not in st.session_state:
        st.session_state["global_show_raw_gaze"] = True
    # VIZ-31: the monitor/font/background panel moved out of the sidebar into the
    # Scanpath rail, so it is *resolved* here (no widgets) and *rendered* later,
    # inside the rail, via the `canvas_renderer` below. Resolving first is what
    # keeps the Corpus view — which has no rail — on the same canvas + typography.
    canvas_geometry_frame = (
        fixations_filtered if not fixations_filtered.empty else raw_gaze_filtered
    )
    (
        canvas_width,
        canvas_height,
        base_font_size,
        font_family,
        line_spacing,
        scale_text_to_boxes,
    ) = seed_canvas_state(words_filtered, canvas_geometry_frame, data_choice)

    def canvas_renderer(slot, text_host=None, *, render_text: bool = True) -> None:
        """Render the canvas/text controls into the rail, in two places.

        UX-81 split the panel between two sections: the screen half into
        ``slot`` (📐 Figure & canvas) and the typography half into ``text_host``
        (📄 Stimulus → Text). One call, so each widget is created exactly once.
        """
        render_canvas_controls(
            words_filtered,
            canvas_geometry_frame,
            data_choice,
            slot=slot,
            bare=True,
            text_host=text_host,
            render_text=render_text,
        )

    # The visualization controls moved out of the sidebar into the Scanpath
    # screen's right-hand rail (tabs.render_single_trial_tab renders them via
    # controls.render_plot_controls with host=rail). The other views — and the Save &
    # restore panel below — still need the resolved settings, so read them from
    # session_state without rendering any widgets; the rail's widgets are the
    # source of truth and write the same keys.
    viz_settings = viz_settings_from_state(
        fixations_filtered, base_font_size, words=words_filtered
    )

    # Whole-dataset combos for the Bulk Export tab's "Export the whole dataset"
    # option, mirroring how `combos` is built from the filtered frames.
    combos_all, _, _ = build_combo_options(
        fixations_all
        if not fixations_all.empty
        else words_all
        if not words_all.empty
        else raw_gaze_df
    )

    # Clear the "loading" bridges now that the real content is about to render
    # in their place — the post-finalize one, and the view-switch one.
    if _finalizing_bridge is not None:
        _finalizing_bridge.empty()
    if _view_bridge is not None:
        _view_bridge.empty()

    # Render tabbed interface. Animation is now a checkbox inside the Scanpath
    # Visualization tab (no separate Animated Scanpath tab); Bulk Export has its
    # own tab. Raw Data + Data Statistics are merged into Data Inspection.
    # Dispatch the active view (top nav). Only one view body renders per run
    # — the keyed nav widget persists the selection across reruns, so no JS hack
    # is needed (unlike st.tabs). render_single_trial_tab writes _share_selection
    # and fills the Save & restore slot when it's the active view.
    # UX-37: the three things a log reader wants to correlate a slow rerun with
    # — which view, which trial, how narrow the pool is. One line each, only on
    # change (see `log_state_change`).
    log_state_change("view", active_view, "View", view=active_view)
    log_state_change(
        "filters",
        (len(words_filtered), len(fixations_filtered), len(combos)),
        "Filters applied",
        trials=len(combos),
        words=len(words_filtered),
        fixations=len(fixations_filtered),
    )

    if data_view:
        # DATA-26 — fill the page reserved before the load. Everything above the
        # dispatch already landed in its slot (source picker · description ·
        # options · data location · wizard · mode-A mapping panels); what is left
        # needs the loaded frames, so it renders here.
        #
        # UX-54's dataset table is the first of those: its counts for the open
        # dataset are this run's frames, which do not exist until the load has
        # happened. Unfiltered on purpose — the table describes the *dataset*,
        # not what the current Narrow-by left standing.
        if not wizard_owns_page:
            render_dataset_table(
                host=dataset_table_slot,
                # Public corpora load through the historical category token,
                # while the table rows use concrete registry labels. Preserve
                # that concrete canonical selection so the active row and its
                # remembered counts are keyed to the row the user can revisit.
                active=str(st.session_state.get("data_source_choice") or data_choice),
                words=words_all,
                fixations=fixations_all,
                raw_gaze=raw_gaze_df,
            )
        mapping_head_slot.divider()
        mapping_head_slot.subheader("🔤 Column mapping")
        mapping_head_slot.caption(
            "How each source column maps onto the app's canonical fields — the "
            "one thing that decides what every measure downstream is computed "
            "from."
        )
        with mapping_body_slot:
            _render_column_mapping_section(editor_rendered=mapping_editor_rendered)
        with setup_identity_slot:
            st.divider()
            st.subheader("🧾 Trial identity")
            st.caption(
                "Whether the Trial ID above actually identifies one reading — "
                "checked on the whole dataset, before any filtering."
            )
            render_trial_identity_section()
        # ``setup_stimulus_slot`` is filled earlier because its values resolve
        # image paths before filtering and plotting. Its reserved position puts
        # it immediately before participant metadata on the Data page.
        with setup_metadata_slot:
            st.divider()
            st.subheader("👤 Participant metadata")
            # The *unfiltered* readers: the join report describes the dataset,
            # not whatever the current Narrow-by left standing.
            render_participant_metadata_section(participants_all)
            st.divider()
            st.subheader("🗂️ Trial metadata")
            # DATA-29: same reasoning one grain down — the report describes the
            # dataset's trials, so it is built from the *unfiltered* combos.
            render_trial_metadata_section(combos_all)
        with setup_body_slot:
            st.divider()
            dataset_label = str(
                st.session_state.get("data_source_choice") or data_choice
            )
            dataset_label = _dataset_display_name(dataset_label).replace("`", "'")
            st.subheader(f"🔎 What's in the `{dataset_label}` dataset")
            # Keyed wrapper → the stable `.st-key-…` selector the "Load and
            # verify a dataset" tutorial spotlights (it kept its name across the
            # move off the Scanpath subtab bar).
            with st.container(key="tutorial_data_inspection"):
                render_data_inspection_tab(
                    words_filtered,
                    fixations_filtered,
                    raw_gaze_filtered,
                )
    elif active_view == _VIEW_CORPUS:
        # UX-25: Corpus Analysis has no "Filter by" row, so the picker gets its
        # own compact row at the top of the page — it stays reachable on every
        # view.
        _ds_col, _ = st.columns([2, 5])
        render_data_source_picker(host=_ds_col)
        with st.container(key="tutorial_corpus_analysis"):
            render_corpus_analysis_tab(
                words_filtered,
                fixations_filtered,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                base_font_size=base_font_size,
                font_family=font_family,
                viz_settings=viz_settings,
                line_spacing=line_spacing,
                scale_text_to_boxes=scale_text_to_boxes,
                canvas_renderer=canvas_renderer,
            )
    else:
        # The Scanpath view renders the viz controls itself (right rail) and
        # writes the global_* keys; re-read them below so Save & restore captures
        # any edits the user just made in the rail. Data Inspection + Share are
        # subtabs of this view now — passed in as renderers so the page owns its
        # subtab bar (Data Inspection renders inline; Share builds the deep link).
        render_single_trial_tab(
            words_filtered,
            fixations_filtered,
            combos,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_font_size=base_font_size,
            font_family=font_family,
            raw_gaze=raw_gaze_filtered,
            line_spacing=line_spacing,
            scale_text_to_boxes=scale_text_to_boxes,
            combos_all=combos_all,
            words_all=words_all,
            fixations_all=fixations_all,
            share_renderer=lambda: _render_share_body(data_choice),
            data_source_renderer=render_data_source_picker,
            canvas_renderer=canvas_renderer,
        )

    # Re-resolve viz settings from session_state AFTER the dispatch so the Save &
    # restore panel reflects any edits made in the Scanpath rail this run (the
    # widgets there write the global_* keys during render).
    viz_settings = viz_settings_from_state(
        fixations_filtered, base_font_size, words=words_filtered
    )

    # Save & restore (plot config + annotations) renders on EVERY view so it stays
    # reachable when a non-Scanpath view is active (it's a menu panel). The
    # trial selection comes from _share_selection (written by the Scanpath view;
    # blank before any trial has been resolved this session).
    _sr_sel = st.session_state.get("_share_selection") or {}
    _sr_pid = str(_sr_sel.get("participant_id") or "")
    _sr_trial = str(_sr_sel.get("trial_id") or "")
    _sr_screen = _sr_sel.get("screen_id")
    _sr_raw_gaze = (
        (
            extract_part(raw_gaze_filtered, _sr_pid, _sr_trial, _sr_screen)
            if _sr_screen is not None and SCREEN_ID in raw_gaze_filtered.columns
            else extract_trial(raw_gaze_filtered, _sr_pid, _sr_trial)
        )
        if _sr_pid and _sr_trial and not raw_gaze_filtered.empty
        else pd.DataFrame()
    )
    _sr_figure_settings = _build_figure_settings(viz_settings, not _sr_raw_gaze.empty)
    _sr_figure_settings["raw_gaze"] = _sr_raw_gaze if not _sr_raw_gaze.empty else None
    _sr_figure_settings["line_spacing"] = line_spacing
    _sr_figure_settings["scale_text_to_boxes"] = scale_text_to_boxes

    def _render_session_backup_block(slot) -> None:
        """The ⬇️ JSON backup block of the 💾 Session dialog (UX-100).

        A closure, because the panel needs the live trial selection and figure
        settings resolved just above — and the dialog is served a few lines
        below, after `save_local_state`, so 🗄️ Automatic recovery can report the
        write that just happened rather than the previous run's. This single
        panel merges the former Plot-configuration and Annotations panels; it is
        a session-wide feature, not part of any one source's setup.
        """
        _render_save_restore_expander(
            _sr_pid,
            _sr_trial,
            canvas_width,
            canvas_height,
            viz_settings["x_field"],
            viz_settings["y_field"],
            _sr_figure_settings,
            viz_settings,
            base_font_size,
            _sr_raw_gaze,
            font_family=font_family,
            slot=slot,
        )
        # A dialog body is a fragment: uploading a backup in here reruns the
        # dialog, not `main`, and `_apply_uploaded_plot_config` runs in `main`.
        # So a file the app has not applied yet asks for a whole-app rerun —
        # which is also what closes the modal onto the restored figure. The
        # applied-signature marker is the importer's own (it dedupes by
        # `(name, size)`), so this cannot loop.
        pending = st.session_state.get("plot_config_upload")
        if pending is not None and st.session_state.get("_plot_config_last_import") != (
            pending.name,
            pending.size,
        ):
            st.rerun(scope="app")

    # Share now lives in the Scanpath view's "🔗 Share" subtab (rendered via the
    # share_renderer passed into render_single_trial_tab), so it builds its deep
    # link from the resolved trial + live viz settings right where it's shown.

    # UX-65 — ❓ Help is a *menu* in the nav now, not a page of buttons: each
    # entry arms the same dialog its button used to (menu._arm_help_action), and
    # the dialogs themselves are untouched. Nothing to fill here anymore — only
    # the tutorial chooser's context, which is data, not a widget, and has to be
    # stashed on every run so the dialog can open over any view.
    #
    # 📚 Documentation left with the buttons: `st.Page` cannot be a URL, and the
    # UX-62 wordmark beside the nav already opens the docs site.
    stash_tutorial_context(
        build_tutorial_context(words_filtered, fixations_filtered, combos)
    )
    # UX-100: the 🐛 Debug toggle and panel moved inside the Session dialog with
    # the rest of the group (`_session_dialog`), so there is nothing to fill here.

    # Persist after all view/menu widgets have written their current values.
    # The helper fingerprints the session and is a no-op on unchanged reruns.
    save_local_state(st.session_state, app_url)
    # …then serve 💾 Session, if the nav asked for it, so 🗄️ Automatic recovery
    # reports the write that just happened rather than the previous run's.
    _fill_recovery_cache_panel(_render_session_backup_block)


if __name__ == "__main__":
    main()
