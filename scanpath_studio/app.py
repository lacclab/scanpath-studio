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

import os
import re
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Tuple

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
    CITATION,
    DATA_PAGE_KEY,
    DATA_PAGE_OFFSCREEN_KEY,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIGURE_SIZE,
    DEFAULT_LINE_SPACING,
    DEMO_CHOICE,
    EYEGENBENCH_DEFAULT_DIR,
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
    UPLOAD_CHOICE,
    WORD_LABEL_COLOR,
    language_display,
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
    data_dictionary_help_text,
    has_active_trial_filters,
    read_trial_filters,
    viz_settings_from_state,
)
from scanpath_studio.data import (
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
    filter_trials,
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
    preprocess_fixation_stage,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    read_table,
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
    render_debug_panel,
    render_debug_toggle,
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
from scanpath_studio import metadata as metadata_mod
from scanpath_studio.menu import (
    close_open_popovers,
    render_top_menu,
    view_label,
)
from scanpath_studio.multipart import SCREEN_ID, extract_part
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
)
from scanpath_studio.session_keys import PARAM_CORPUS
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
)
from scanpath_studio.tour import (
    build_tutorial_context,
    maybe_show_faq,
    maybe_show_tutorial_library,
    maybe_show_welcome_tour,
    render_faq_button,
    render_spotlight_tour,
    render_tour_replay_button,
    render_tutorial_library,
    render_use_case_tutorial,
)
from scanpath_studio.url_state import (
    CORPUS_SOURCE_TOKEN,
    _active_view,
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
# that use it (render_sidebar_data_source, main), not here. wizard does
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


def _render_about_panel(host=None) -> None:
    """The page heading: title + caption.

    Sits below Streamlit's own top nav, so navigation is the first thing on the
    page. ``host`` is ``menu.TopMenu.title`` — the left side of the row the
    settings triggers share, so ❓ Help and 💾 Session sit at the title's height
    instead of costing a page row of their own (see ``menu.render_top_menu``).
    **About** is a dialog off the ❓ Help menu group.
    """
    header = (host if host is not None else st).container(key="about_header")
    with header:
        st.title("Scanpath Studio")
        st.caption("Interactive visualization of eye movements in reading.")


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
    """Delete the on-device cache and stop re-writing it this session.

    An ``on_click`` callback, not inline button handling: it writes the
    ``persist_local_saving`` toggle's key, which Streamlit forbids once that
    widget has rendered in the current run. Pausing is what makes Forget stick —
    ``main`` saves at the end of every run, so deleting alone would hand the
    same session straight back to disk.
    """
    clear_local_state(st.session_state)
    set_persistence_paused(st.session_state, True)
    st.session_state["persist_local_saving"] = False
    st.session_state["_recovery_cache_forgotten"] = True


def _toggle_recovery_saving() -> None:
    """Mirror the panel's saving toggle into the persistence pause flag."""
    set_persistence_paused(
        st.session_state, not bool(st.session_state.get("persist_local_saving", True))
    )
    st.session_state.pop("_recovery_cache_forgotten", None)


def _render_recovery_cache_panel(app_url: str, *, slot=None) -> None:
    """Render the "🗄️ Recovery cache" menu panel (ENG-30).

    ENG-26 made a local session survive a refresh or a restart, but silently:
    nothing in the app said that a copy of the loaded tables was being written
    to the user's disk, where it lived, or how to get rid of it. This panel is
    that disclosure plus its controls — what is stored, how big it is, when it
    was last written, pause saving, and forget it. On a hosted deployment (where
    `persistence.persistence_enabled` is False) it explains that nothing is
    stored instead of hiding, so the difference between deployments is visible
    from the same place.

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
                "**Off here.** A refresh loses your session — save it above.",
                help="This deployment keeps your session in memory only, so a "
                "refresh or a restart loses uploaded datasets, mappings and "
                "annotations. Run Scanpath Studio locally (or as the desktop "
                "app) and it is restored automatically.",
            )
            if status["override"] == "off":
                st.caption(f"Disabled by `{PERSIST_ENV_VAR}=0`.")
            return

        # UX-53: what is cached and that it never leaves the machine is the
        # group caption's tooltip in `menu.py`; this panel shows the *state* of
        # the cache — restored, size, when — and its two controls.
        if restored_from_cache(st.session_state):
            st.success("Restored when the app opened.", icon="↩️")
        if status["exists"] and status["readable"]:
            n_sets = len(status["datasets"])
            bits = [f"**{n_sets}** dataset{'s' if n_sets != 1 else ''}"]
            # None = stored before the manifest carried row counts; the next
            # save backfills it. Saying "0 rows" would be worse than silence.
            if status["rows"] is not None:
                bits.append(f"**{status['rows']:,}** rows")
            bits += [
                f"**{status['annotations']}** annotated trial"
                f"{'s' if status['annotations'] != 1 else ''}",
                f"**{human_size(status['bytes'])}** on disk",
            ]
            st.markdown(" · ".join(bits))
            # One line, not three: which datasets and when, together.
            line = []
            if status["datasets"]:
                line.append(", ".join(d["name"] for d in status["datasets"]))
            saved_at = str(status["saved_at"] or "").replace("T", " ")
            if saved_at:
                line.append(f"saved {saved_at}")
            if line:
                st.caption(" · ".join(line))
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
            st.caption("Nothing stored yet — the session is saved as you work.")

        # Seed rather than pass `value=`: the Forget callback writes this key via
        # the session-state API, and a widget carrying both logs Streamlit's
        # "default value but also had its value set via the Session State API"
        # warning on every run (same fix as the 0.27.1 restored-value pass).
        st.session_state.setdefault(
            "persist_local_saving", not persistence_paused(st.session_state)
        )
        st.toggle(
            "Keep saving here",
            key="persist_local_saving",
            on_change=_toggle_recovery_saving,
            help="Turn off to stop writing to the cache for the rest of this "
            "session. Your work stays loaded either way.",
        )
        st.button(
            "🗑 Forget saved session",
            on_click=_forget_recovery_cache,
            width="stretch",
            disabled=not status["exists"],
            help="Delete the stored copy from this computer and pause saving. "
            "The data you have loaded stays open.",
        )
        # The folder is the one detail worth a line of its own (it is what you
        # go and look at); the env-var switches live in its tooltip.
        st.caption(
            f"Folder: `{status['directory']}`",
            help=f"Always off: `{PERSIST_ENV_VAR}=0` · move the folder: "
            f"`{STATE_DIR_ENV_VAR}=…` · same info from a terminal: "
            "`scanpath-studio cache`.",
        )


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
        "author = {Shubi, Omer and Gruteke Klein, Keren and Lion, Ella and "
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


def data_root() -> Optional[Path]:
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


def _pick_directory_dialog() -> Optional[str]:
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
    root: Optional[str] = None,
    size_hint: str = "",
    download: Optional[Callable[[str], None]] = None,
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
    nothing visible except a sidebar line — the loaders quietly fall back to the
    bundled demo, so the plot showed *demo* scanpaths as though the choice had
    taken effect. This names the dataset, says what's missing and how big the
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
    download: Optional[Callable[[str], None]] = None,
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
    sidebar line alone is easy to miss when the plot keeps rendering demo data.
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
            action="Set **Data location** in the sidebar to a folder holding the "
            "files listed under **Expected files**.",
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
def _cached_potec_raw_frames(root: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw PoTeC frames (pre-normalization) — the full corpus.

    Returns the same shape as an upload: raw frames the normal
    auto-detect → normalize → harmonize pipeline then handles. Cached on the
    directory so re-runs (toggling viz controls) don't re-read the files. Loads
    every reader × text (75 × 12); narrow the trial pool with **Narrow by**."""
    from scanpath_studio.datasets import potec_raw_frames

    return potec_raw_frames(root)


def _load_potec_source(
    options_host=None, location_host=None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the PoTeC corpus data source.

    PoTeC can't be loaded through the generic Upload flow (trial/word ids live
    in filenames, fixation coordinates come from a separate character-AoI
    file), so this dedicated source wraps ``datasets.potec_raw_frames``. The
    returned raw frames go through the same normalization as an upload, so the
    sidebar Column-mapping panels still appear and stay overridable. The whole
    corpus loads — narrow it with the **Narrow by** trial filters.

    ``options_host`` / ``location_host`` are the DATA-9 sidebar sub-slots; PoTeC
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    from scanpath_studio.datasets import multipleye_inventory

    return multipleye_inventory(root, fixation_source=fixation_source)


def _load_multipleye_source(
    options_host=None, location_host=None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the MultiplEYE corpus data source.

    MultiplEYE can't be loaded through the generic Upload flow (participant /
    trial / stimulus live only in the folder + file names), so this dedicated
    source wraps ``datasets.multipleye_raw_frames``. The returned raw frames go
    through the same normalization as an upload, so the sidebar Column-mapping
    panels still appear and stay overridable. The whole session set loads —
    narrow it with the **Narrow by** trial filters.

    ``options_host`` / ``location_host`` are the DATA-9 sidebar sub-slots (the
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
    root: str, regime: str, parts: Tuple[str, ...], variant: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Sidebar controls + loader for the OneStop corpus (OSF or LaCC lab).

    OneStop's interest-area + fixation reports share the bundled demo's schema
    across every trial part, so this fetches (public variant) or reads (lacclab
    variant) the chosen reading regime + parts and hands the raw frames to the
    normal normalization pipeline — the Column-mapping panels still appear and
    stay overridable. Distinct from the env-var "OneStop server bundle" source,
    which serves a lacclab export (and per-pid shards for deep links).

    ``options_host`` / ``location_host`` are the DATA-9 sidebar sub-slots (source
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
        return f"✅ **Real** screen geometry — {note}."
    return badge


def benchmark_corpus_label(name: str) -> str:
    """The registry key for a prepared corpus named ``name``."""
    return f"{name}{BENCHMARK_LABEL_SUFFIX}"


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
    name = str(entry["name"])
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Location controls + loader for **one** prepared benchmark corpus.

    A peer of `_load_potec_source` / `_load_multipleye_source`: one entry, one
    corpus, no sub-picker. The returned raw frames go through the same
    normalization as an upload, so the Column-mapping panels still appear.
    """
    from scanpath_studio.eyegenbench import eyegenbench_present

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
        label=f"{dataset} (harmonised benchmark)",
    )
    if not ready:
        return load_sample_data()
    entry = next(
        (e for e in discovered_benchmark_datasets() if e["name"] == dataset), None
    )
    if entry and (badge := geometry_badge(entry)):
        opt.caption(badge)
    try:
        return _cached_eyegenbench_raw_frames(root, dataset)
    except _MANIFEST_ERRORS as exc:
        loc.error(f"Couldn't load '{dataset}' from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


# Registry behind the "Public datasets" source: label → loader (renders its own
# sidebar options and returns raw, pre-normalization frames), the corpus'
# presentation-monitor size (canvas default for true-to-scale rendering; None to
# estimate from data extents), and a little presentation metadata (a short name
# for the picker, plus language / size / description / home link shown as a
# caption). To add a corpus: write a loader in datasets.py, wrap it in a
# `_load_*_source` sidebar function above, and add one entry here — the
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
    ),
    ONESTOP_PUBLIC_CHOICE: dict(
        loader=_load_onestop_public_source,
        monitor=(2560, 1440),  # OneStop presentation monitor (full-screen px coords)
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
    ),
}


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
    from scanpath_studio.eyegenbench import declared_monitor

    entries: dict = {}
    for entry in discovered_benchmark_datasets():
        name = str(entry["name"])
        short = _benchmark_short_name(name)
        spec = dict(
            loader=partial(_load_benchmark_source, dataset=name),
            short=short,
            language=language_display(entry.get("language")),
            size=_benchmark_size_caption(entry),
            description=_benchmark_description(entry, harmonised_overlap=short != name),
            link="https://github.com/EyeBench/EyeGenBench",
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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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


def _public_dataset_monitor(data_choice: str) -> Optional[Tuple[int, int]]:
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


def _dataset_font(words: pd.DataFrame) -> Tuple[Optional[float], Optional[str]]:
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


def _stimulus_font_install_hint(css_family: Optional[str]) -> Optional[Tuple[str, str]]:
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
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> Dict:
    """VAL-7's diagnosis, memoized on the two frames' fingerprints.

    It groups the whole corpus by trial several times over, so it must not run
    on every rerun — but it also must not be skipped, since the failure it
    catches is invisible in the figure.
    """
    return diagnose_trial_identity(_words, _fixations)


@st.cache_data(show_spinner="Loading MultiplEYE server bundle…")
def _cached_multipleye_server_bundle(
    participant: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return load_multipleye_server_bundle(participant)


def load_words_and_fixations(
    data_choice: str,
    participant: Optional[str] = None,
    *,
    description_host=None,
    options_host=None,
    location_host=None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw word + fixation frames for the **non-upload** data sources.

    The Upload source is handled separately by the setup wizard
    (``_render_data_setup``), which groups each table's upload box with its
    mapping; this covers the bundled demo, synthetic trial, public datasets, and
    the OneStop server bundle.

    ``description_host`` / ``options_host`` / ``location_host`` are the DATA-9
    sidebar sub-slots a public dataset's caption / source options / data-location
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


def _schema_key(schema: Optional[Dict]) -> Optional[tuple]:
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


@st.cache_data(show_spinner="Normalizing data…")
def _normalize_pair_cached(
    _words_df: pd.DataFrame,
    _word_schema: Optional[Dict],
    _fixations_df: pd.DataFrame,
    _fix_schema: Optional[Dict],
    cache_key,
    _keep_words: Optional[set] = None,
    _keep_fix: Optional[set] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Pure normalize + harmonize, cached on a cheap fingerprint of the inputs.

    The raw frames are passed un-hashed (underscore args); ``cache_key`` carries
    a ``frame_fingerprint`` + schema signature + the keep-column selection
    instead, so a trial change (which re-runs the script but feeds byte-identical
    raw frames) hits the cache and skips re-normalizing the whole corpus, while
    changing the kept columns correctly busts it.
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
    word_schema: Optional[Dict],
    fixations_df: pd.DataFrame,
    fix_schema: Optional[Dict],
    keep_words: Optional[set] = None,
    keep_fix: Optional[set] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
    return _normalize_pair_cached(
        words_df,
        word_schema,
        fixations_df,
        fix_schema,
        cache_key,
        _keep_words=keep_words,
        _keep_fix=keep_fix,
    )


def _reset_active_mapping() -> None:
    """Clear the stashed column mapping at the start of each data load, so a new
    source doesn't inherit the previous one's mapping in the Data Inspection tab."""
    st.session_state["_active_column_mapping"] = {}


def _stash_active_mapping(table: str, schema: Optional[Dict]) -> None:
    """Record the schema (field → source column) actually used for ``table`` so
    ``tabs.render_data_inspection_tab`` can show how columns were mapped. ``table``
    is one of ``"words" / "fixations" / "raw_gaze"``."""
    mapping = st.session_state.setdefault("_active_column_mapping", {})
    mapping[table] = dict(schema) if schema else None


def prepare_data(
    words_df: pd.DataFrame,
    fixations_df: pd.DataFrame,
    allow_override: bool,
    mapping_host=None,
) -> Tuple[pd.DataFrame, pd.DataFrame, list]:
    """Infer schemas and normalize incoming dataframes to canonical column names.

    When ``allow_override`` is True, render sidebar expanders that let the user
    pick the exact column names for each field (pre-filled with auto-detection).
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
        word_proposed = propose_word_schema(words_df)
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
            )
        else:
            word_schema = word_proposed
        word_problems = validate_word_schema(word_schema)
        if word_problems:
            problems.append("Words/IA: " + "; ".join(word_problems))

    if has_fixations:
        fix_proposed = propose_fix_schema(fixations_df)
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

    words_norm, fixations_norm = _normalize_pair(
        words_df, word_schema, fixations_df, fix_schema
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
    """Show the raw uploaded data while the column mapping is incomplete.

    The uploaded tables (unmodified) are shown so the user can inspect column
    names and values to fill in the *Column mapping* panels without the app
    halting.
    """
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
    """
    if data_view:
        return
    st.info(
        "**This dataset isn't set up yet**, so there's nothing to plot. "
        "Finish it on the 🗂️ **Data** page.",
        icon="🗂️",
    )
    st.button("🗂️ Go to Data setup", on_click=_go_data, type="primary")


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
def _read_uploaded_table_cached(_uploaded, file_key) -> pd.DataFrame:
    try:
        _uploaded.seek(0)
    except Exception:
        pass
    return read_table(_uploaded)


@st.cache_data(show_spinner="Reading uploaded data…")
def _read_uploaded_tables_cached(_uploaded_list, file_keys) -> pd.DataFrame:
    for f in _uploaded_list:
        try:
            f.seek(0)
        except Exception:
            pass
    return read_tables(list(_uploaded_list))


def _read_uploaded_frame(
    *,
    uploader_label: str,
    upload_help: str,
    state_prefix: str,
    multi: bool,
    container=None,
) -> pd.DataFrame:
    """Render one upload box and return its (concatenated) frame.

    Renders in the sidebar by default; pass ``container`` (the setup wizard's
    main-area container) to render it there. Empty frame when nothing is
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
    if multi:
        return _read_uploaded_tables_cached(
            uploaded, tuple(_uploaded_file_key(f) for f in uploaded)
        )
    return _read_uploaded_table_cached(uploaded, _uploaded_file_key(uploaded))


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
            isn't looking at is invisible, which the always-visible sidebar
            never was.

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
# `_sidebar_group` is gone with the sidebar: each former group is now its own
# popover on the menu bar (see `menu.render_top_menu`), and the popover's trigger
# label is the group heading. Nothing left to title.
# -----------------------------------------------------------------------------


def render_sidebar_data_source(host=None) -> str:
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
        source = (host if host is not None else st).container(
            key="tour_grp_data_source"
        )
        source.caption("➕ Adding a dataset — fill in the setup wizard below.")
        if source.button("✕ Cancel", key="cancel_add_data"):
            st.session_state["_pending_source_choice"] = st.session_state.get(
                "_prev_source", DEMO_CHOICE
            )
            st.session_state["_show_upload_wizard"] = False
            st.session_state["setup_complete"] = True
            st.rerun()
        return UPLOAD_CHOICE

    # DATA-9: one **flat** source picker. Every source is a single entry tagged by
    # kind — 🧪 demo · 🔒 private (your uploads + local env bundles) · 🌐 public —
    # instead of a "Public datasets" category that then needed a second selectbox.
    # `data_source_choice` stays the canonical key, but for a public corpus the
    # entry's token IS the registry label; the return value resolves it back to
    # PUBLIC_DATASETS_CHOICE (+ public_dataset_choice) so the load path is unchanged.
    uploaded = list(st.session_state.get("_datasets", {}).keys())
    entries: list[str] = []
    kinds: Dict[str, str] = {}
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
    ``render_sidebar_data_source`` — which pops ``_pending_source_choice`` at the
    top of ``main`` — applies the new source on the *same* run that renders it.
    The picker rides its own widget key (``data_source_picker``) rather than
    writing ``data_source_choice`` directly, so a deep link / saved config can
    keep assigning the canonical key without the widget reconciling it away.
    """
    picked = st.session_state.get("data_source_picker")
    if picked:
        st.session_state["_pending_source_choice"] = picked


def render_data_source_picker(host=None) -> None:
    """Render the data-source picker in the main view (UX-25).

    Sits on the "Filter by" row, left of the label, so the top of the page reads
    left-to-right as *which dataset → how to narrow it → which trial* — the app is
    built to be used with the sidebar closed. Renders from the entry list
    :func:`render_sidebar_data_source` published earlier this run; a pick is
    applied on the next run via :func:`_on_data_source_pick`.

    The compact row holds the selectbox only; managing sources (➕ Add data,
    removing an uploaded dataset, contributing a corpus) lives behind the ➕
    popover beside it.
    """
    # Imported lazily (not at module top) to avoid the app⇄wizard import cycle.
    from scanpath_studio.wizard import _enter_add_data_wizard, _remove_dataset

    entries = list(st.session_state.get("_data_source_entries") or [])
    if not entries:
        return
    kinds: Dict[str, str] = dict(st.session_state.get("_data_source_kinds") or {})
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
            name = registry[token].get("short", token)
        elif token in uploaded:
            name = f"{token} (yours)"
        else:
            name = token
        return f"{tag} {name}".strip()

    # Keyed wrapper → stable `.st-key-…` selector for the spotlight tour.
    box = (host if host is not None else st).container(key="tour_grp_data_source")
    pick_col, add_col = box.columns([5.6, 1], vertical_alignment="center")
    # Mirror the canonical key onto the widget key before it instantiates, so a
    # deep link / restore / wizard finalize shows up in the picker.
    current = st.session_state.get("data_source_choice")
    if current in entries:
        st.session_state["data_source_picker"] = current
    pick_col.selectbox(
        "Data source",
        entries,
        format_func=_entry_label,
        help=data_dictionary_help_text(),
        key="data_source_picker",
        on_change=_on_data_source_pick,
        label_visibility="collapsed",
    )
    # UX-47: `railbtn_*`, like every other trigger on the four control rows above
    # the plot. It was the one that never joined UX-27's shared shape, and it
    # showed: a 40 px-tall stretched rectangle beside 27 px pills, which also made
    # this row the tallest of the four for no reason.
    manage = add_col.container(key="railbtn_data_add").popover(
        "➕", width="content", help="Add or remove datasets."
    )
    # The state change runs in an on_click callback (before widgets instantiate)
    # so it can reassign the data_source_choice key — see _enter_add_data_wizard.
    # The callback fires, then Streamlit reruns into the wizard branch.
    manage.button(
        "➕ Add data",
        key="add_data_btn",
        on_click=_enter_add_data_wizard,
        help="Upload your own eye-tracking tables.",
        width="stretch",
    )
    # Let the user remove datasets they added earlier (✕ next to each). Selecting
    # the removed one falls back to the demo (see _remove_dataset).
    if uploaded:
        manage.caption("Remove an added dataset")
        for name in uploaded:
            name_col, x_col = manage.columns([5, 1])
            name_col.write(name)
            x_col.button(
                "✕",
                key=f"remove_dataset_{name}",
                on_click=_remove_dataset,
                args=(name,),
                help=f"Remove '{name}'",
            )
    manage.caption(
        "Have a public corpus? "
        f"[Get it built in ↗]({CITATION['docs_url']}contributing-a-dataset/)"
    )


def resolve_source_monitor(
    data_choice: Optional[str],
    words: pd.DataFrame,
    fixations: pd.DataFrame,
) -> Tuple[int, int, bool]:
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
    # (Dell U2715H, 2560x1440).
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
    provenance: Optional[Mapping[str, Provenance]] = None,
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
    data_choice: Optional[str] = None,
) -> Optional[SetupSnapshot]:
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
    data_choice: Optional[str] = None,
) -> Tuple[int, int, int, str, float, bool]:
    """Resolve the canvas / typography settings without rendering any widget.

    Split out of `render_sidebar_canvas_controls` by **VIZ-31**, which moved that
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
    # (Dell U2715H, 2560x1440). Data-derived extents undershoot — text only
    # fills part of the screen — so hard-default to the real monitor here.
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


def render_sidebar_canvas_controls(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    data_choice: Optional[str] = None,
    slot=None,
    expanded: bool = False,
    title: str = "Experimental Setup",
    bare: bool = False,
) -> Tuple[int, int, int, str, float, bool]:
    """Render the canvas-geometry, typography and background panel.

    These controls let the user match the visualization to the experimental
    display, which is what keeps coordinates and word boxes spatially accurate.

    The panel normally renders into ``slot`` as its own collapsible expander.
    Pass ``bare=True`` when ``slot`` is already the disclosure container, as the
    compact Scanpath rail does. The setup wizard keeps the standalone expander.
    `seed_canvas_state` does the state work and is called first here, so rendering
    and not-rendering resolve identically.

    **UX-48 sub-grouping.** In ``bare`` mode these ~19 controls share the rail's
    "📐 Figure & canvas" disclosure with the axes/label controls, which made one
    ~26-row scroll with no internal structure. So the compact form splits them
    into two popovers — **🖥️ Screen & geometry** (the monitor the experiment ran
    on) and **🔤 Text & fonts** (how the reading text is drawn, plus the two
    colours) — the same `expander → popover` shape every layer group uses. The
    wizard's standalone expander stays flat: that step *is* the setup form, and
    hiding half of it behind buttons would be a step you can't read at a glance.

    Returns:
        Tuple of (canvas_width, canvas_height, base_font_size, font_family,
        line_spacing, scale_text_to_boxes).
    """
    seed_canvas_state(words_filtered, fixations_filtered, data_choice)
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

    # Both sub-groups are created up front (Streamlit lays containers out in
    # creation order), so the code below keeps its order while landing in the
    # right group. Flat mode points both names at the one container.
    screen = (
        display.popover("🖥️ Screen & geometry", width="stretch") if bare else display
    )
    text = display.popover("🔤 Text & fonts", width="stretch") if bare else display
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
    screen.caption(
        f"Geometry: **{px_per_degree:.1f} px/degree** · "
        f"{1.0 / px_per_degree:.4f}° per pixel."
    )

    # --- 🔤 Text & fonts (sub-group in bare mode) -------------------------
    # Reading text is true-to-scale by default: it auto-sizes to the word boxes
    # (text height = box_height / line_spacing) and scales with the figure, so it
    # always fills the real line slot. Untick to fall back to a fixed font size.
    # Keyed (+ seeded) so the Save & restore panel can capture/reapply them.
    scale_text_to_boxes = text.checkbox(
        "Scale text to boxes",
        key="global_scale_text_to_boxes",
        persist_state="session",
        help="Size the reading text from the word boxes (height = box height ÷ "
        "line spacing) so it stays true to the real experiment at any zoom. "
        "Untick to use the fixed 'Figure font size' below instead.",
    )
    line_spacing = field(
        text,
        "number_input",
        "Line spacing",
        min_value=1.0,
        max_value=10.0,
        step=0.5,
        disabled=not scale_text_to_boxes,
        key="global_line_spacing",
        persist_state="session",
        help="Line slots per line of text. OneStop rendered one blank line above "
        "and one below each text line, so the box spans 3 line heights → 3.",
    )
    use_stimulus_font_pt = text.checkbox(
        "Use stimulus font size in points",
        key="global_use_stimulus_font_pt",
        persist_state="session",
        disabled=scale_text_to_boxes,
        help="Convert the original stimulus point size with the DPI above. "
        "Scale-to-boxes still takes precedence when enabled.",
    )
    stimulus_font_pt = field(
        text,
        "number_input",
        "Stimulus font size (pt)",
        display="Font size (pt)",
        min_value=4.0,
        max_value=144.0,
        step=0.5,
        key="global_stimulus_font_pt",
        persist_state="session",
        disabled=scale_text_to_boxes or not use_stimulus_font_pt,
    )
    if not scale_text_to_boxes and use_stimulus_font_pt:
        st.session_state["global_base_font_size"] = int(
            min(max(round(font_pt_to_px(stimulus_font_pt, display_dpi)), 6), 72)
        )
    base_font_size = field(
        text,
        "number_input",
        "Figure font size (px)",
        min_value=6,
        max_value=72,
        step=1,
        help="Real (monitor-pixel) font size, scaled true-to-scale with the "
        "figure. Used for the reading text when 'Scale text to boxes' is off or "
        "the data has no word boxes, and always for axis/legend chrome.",
        key="global_base_font_size",
        persist_state="session",
        disabled=not scale_text_to_boxes and use_stimulus_font_pt,
    )
    # VIZ-1: every font-size control here is in pixels, but stimulus typography
    # is usually specified in points. Spell out the difference + the conversion.
    text.caption(
        "ℹ️ Font sizes here are in **pixels (px)**, but stimuli are usually "
        "specified in **points (pt)**. To match the original, convert via the "
        "experiment's DPI: `px = pt × DPI ÷ 72` (e.g. 12 pt ≈ 16 px at 96 DPI). "
        "Prefer **Scale text to boxes** when the data ships word boxes — it sizes "
        "the text from the real geometry and sidesteps the conversion."
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
    # controls). Read back into viz_settings by controls.sidebar_controls.
    field(
        text,
        "color_picker",
        "Text color",
        key="global_text_color",
        persist_state="session",
        help="Colour of the reading text drawn over the stimulus.",
    )

    # Plot background lives here (Experimental Setup) rather than under
    # Visualization; sidebar_controls reads the chosen value from session state.
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
        layout_text,
        layout_problems,
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
    """
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
        5. Render sidebar controls (canvas, fonts, visualization settings)
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
            "Restored your last session from this computer — see 💾 Session → "
            "🗄️ Recovery cache, beside the title.",
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
    elif url_source == CORPUS_SOURCE_TOKEN and public_datasets_enabled():
        # DATA-27 (Task 12): `?source=corpus&corpus=<slug>` names ONE entry of
        # `public_dataset_registry()` — a built-in public corpus or a locally
        # prepared one, identically. Writing the registry label into
        # `data_source_choice` is what the picker's healing path expects; it
        # collapses the label back to PUBLIC_DATASETS_CHOICE and re-stashes it on
        # `public_dataset_choice`, which is seeded here too so the corpus is
        # already resolved for anything that reads it before the picker runs.
        slug = str(st.query_params.get(PARAM_CORPUS) or "")
        corpus_choice = corpus_choice_for_slug(slug)
        if corpus_choice:
            st.session_state.setdefault("data_source_choice", corpus_choice)
            st.session_state.setdefault("public_dataset_choice", corpus_choice)
        elif slug:
            # The common case, not an edge case: the recipient has no prepared
            # bundle, or a different subset of one. Say which corpus was named
            # and leave the picker exactly where it was — never wedge it, and
            # never silently open a different corpus.
            st.warning(
                f"This link opens the corpus `{slug}`, which isn't available "
                "here. If it is a harmonised benchmark corpus, prepare a local "
                "bundle containing it and point the benchmark data directory "
                "(⚙️ Configure → the corpus' *Data directory*) at it; otherwise "
                "pick the corpus in **Data source**. The link's view settings "
                "still apply to whatever you open."
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
    # reserve-then-fill discipline the sidebar containers had.
    seed_debug_mode()  # UX-37: a legacy ?debug=1 link pre-arms the Help toggle.
    menu = render_top_menu(show_debug=debug_enabled())
    _render_about_panel(menu.title)

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

    # Active top-level view (set by the nav switch). Read here so the dispatch
    # below renders only the active page.
    active_view = _active_view()

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

    # DATA-26 — the **Data** page ("Set up your dataset"). One place for
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
    # Sub-slots are reserved in page order and filled at whatever point of the
    # load reaches them (Streamlit lays containers out in creation order):
    #     Data source     (picker + ➕ manage)
    #     Description     (public-dataset caption / home link)
    #     Options         (source-specific: OneStop regime + parts + variant, …)
    #     Data location   (path input + Expected files + found/download status)
    #     Add a dataset   (the upload wizard, while one is being added)
    #     What's in it    (name + counts + raw tables + stats + trial identity)
    #     Column mapping  (ONE section, three modes — see _render_setup_mapping)
    #     Participant metadata (DATA-20)
    #     Preprocessing
    data_view = active_view == _VIEW_DATA
    setup_page = st.container(
        key=DATA_PAGE_KEY if data_view else DATA_PAGE_OFFSCREEN_KEY
    )
    if data_view:
        setup_page.header("Set up your dataset")
        setup_page.caption(
            "Where the data comes from, what is actually in it, how its columns "
            "map onto the app's canonical fields, what you know about the "
            "readers, and the optional preprocessing applied before anything is "
            "measured."
        )
        # UX-52 — four peer sections, one heading level, one divider between
        # each. The source block used to open with no heading at all, which
        # made the three headings below it read as the whole page rather than
        # as three of its four stages. Written straight into `setup_page`
        # before the slots are created, so it lands above them (Streamlit lays
        # containers out in creation order).
        setup_page.divider()
        setup_page.subheader("📂 Data source")
        setup_page.caption(
            "Which dataset, where its files are, and any options that source offers."
        )
    setup_source_slot = setup_page.container()
    description_slot = setup_page.container()
    source_options_slot = setup_page.container()
    data_location_slot = setup_page.container()
    setup_wizard_slot = setup_page.container()
    # UX-52 round 2 — "what's in this dataset" comes **before** the mapping, on
    # the user's call. It breaks pipeline order deliberately: the counts are the
    # first thing you want after choosing a source ("did it load, and is it the
    # right size?"), and the mapping is what you scroll to when the answer looks
    # wrong. Reserving the slots in this order is the whole change — Streamlit
    # lays containers out in creation order, so *when* each is filled during the
    # load is unaffected.
    setup_body_slot = setup_page.container()
    # Keyed → the stable `.st-key-…` selectors the "Load and verify a dataset"
    # tutorial spotlights (UX-40), alongside `tutorial_data_inspection` above.
    column_mapping_slot = setup_page.container(key="tutorial_column_mapping")
    # The heading belongs to the *section*, not to any one of its three modes —
    # mode A's panels are written into the body by `prepare_data` during the
    # load, long before the dispatch below picks a mode, so the title needs a
    # slot of its own above them (see tabs._render_column_mapping_section).
    mapping_head_slot = column_mapping_slot.container()
    mapping_body_slot = column_mapping_slot.container()
    # Raw tables for a dataset whose mapping is still broken. Its own slot,
    # *below* the editor: with "what's in it" moved above, filling that one
    # would put the tables above the controls that fix them.
    unmapped_slot = setup_page.container()
    # UX-52 round 3 — the VAL-7 trial-identity verdict is its own section, not a
    # `#####` item inside "What's in this dataset" (the user's call). It carries
    # a *verdict* — sometimes a warning — and the fix it names is a change to the
    # Trial ID mapping directly above it, so it belongs at the same level as the
    # thing it judges rather than buried under the counts.
    # Keyed → the `.st-key-…` selector the "Load and verify a dataset" tutorial
    # spotlights, alongside its siblings above and below.
    setup_identity_slot = setup_page.container(key="tutorial_trial_identity")
    # DATA-20 §1 — the participant-level metadata table. After the mapping (it
    # joins on the reader id the mapping just settled).
    setup_metadata_slot = setup_page.container(key="tutorial_participant_metadata")
    setup_preproc_slot = setup_page.container(key="tutorial_preprocessing")

    # Data source selection. UX-25: only the *resolution* happens here (it must
    # precede the load); the picker itself renders in the main view — on the
    # Scanpath "Filter by" row, at the top of the Corpus view, or (DATA-26) in
    # the page slot above. The resolver takes the same slot because while the
    # add-dataset wizard is open it renders a "✕ Cancel" bar *instead of* a
    # picker, and rendering both would duplicate the `tour_grp_data_source` key.
    data_choice = render_sidebar_data_source(host=setup_source_slot)
    if data_view and data_choice != UPLOAD_CHOICE:
        render_data_source_picker(host=setup_source_slot)
    if data_view:
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
    # [upload box → mapping] group in the sidebar (words, fixations, raw gaze) and
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
    raw_gaze_df: Optional[pd.DataFrame] = None
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
        # finalize and render_sidebar_data_source.
        stored = st.session_state["_datasets"][data_choice]
        words_df, fixations_df = stored["words"], stored["fixations"]
        raw_gaze_df = stored["raw_gaze"]
        raw_words_df, raw_fixations_df = words_df, fixations_df
        mapping_problems = []
        # Re-publish this dataset's chosen filter fields so the sidebar
        # "Filter trials" panel offers the same dynamic conditions.
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
        # fields left over from a prior upload so the sidebar falls back to the
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
        # keep their keys. Mirrors the canvas re-seed in render_sidebar_canvas_controls.
        #
        # Two harmonised benchmark corpora share one schema, so switching between
        # them re-proposes a mapping that auto-detects to the same thing — the
        # cost of one key covering every corpus, and the same trade every other
        # pair of sources already makes.
        source_key = (data_choice, st.session_state.get("public_dataset_choice"))
        if st.session_state.get("_colmap_seeded_for") != source_key:
            for stale in [
                k
                for k in list(st.session_state)
                if isinstance(k, str) and k.startswith("col_map_")
            ]:
                del st.session_state[stale]
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
        return

    # VIZ-14: local/desktop users can attach stimulus screenshots without
    # adding an image_path column to their data. This intentionally stays out
    # of public deployments and share links because it contains machine-local
    # filesystem information; the same resolver is available through the API
    # and CLI for reproducible headless renders.
    if local_filesystem_enabled():
        with data_location_slot.expander("Stimulus images", expanded=False):
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
    # leaving it to a sidebar line they've likely scrolled past.
    _render_dataset_unavailable()

    # Whole-dataset frames, captured BEFORE the sidebar "Filter trials" panel —
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
    identity_report = _cached_trial_identity_report(
        words_all,
        fixations_all,
        cache_key=(frame_fingerprint(words_all), frame_fingerprint(fixations_all)),
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

    # Land a shared/deep link on its exact `?trial_id=` (once) now that combos
    # exist — see _apply_url_trial_selection. Runs before the sidebar/tab widgets
    # render so the seeded selection is picked up as their initial value.
    _apply_url_trial_selection(combos)
    # Same hop, from inside the app: a "go to this trial" button in a Corpus
    # Analysis table parks its request in a callback (before combos exist) and
    # it is applied here — see url_state.request_trial (ENG-36).
    _apply_pending_trial_selection(combos)

    # Restore settings + annotations from an uploaded config JSON BEFORE the
    # sidebar widgets render, so they pick up the saved values (see
    # _apply_url_preset for the same preset-then-render mechanism). The uploader
    # lives in the "💾 Save & restore" panel below; its file persists across reruns.
    _apply_uploaded_plot_config(combos, fixations_filtered)

    # Canvas and visualization controls (sidebar). For a raw-gaze-only dataset,
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

    def canvas_renderer(slot) -> None:
        """Render canvas/text controls into the rail's figure disclosure."""
        render_sidebar_canvas_controls(
            words_filtered,
            canvas_geometry_frame,
            data_choice,
            slot=slot,
            bare=True,
        )

    # The visualization controls moved out of the sidebar into the Scanpath
    # screen's right-hand rail (tabs.render_single_trial_tab renders them via
    # controls.sidebar_controls with host=rail). The other views — and the Save &
    # restore panel below — still need the resolved settings, so read them from
    # session_state without rendering any widgets; the rail's widgets are the
    # source of truth and write the same keys.
    viz_settings = viz_settings_from_state(
        fixations_filtered, base_font_size, words=words_filtered
    )

    # The "💾 Save & restore" slot is its own popover on the menu bar (keyed
    # `tour_grp_save_restore`, which the spotlight tour and the annotations
    # panel's "jump here" affordance both target). The active view fills it later
    # — it needs the live selection + figure settings for the download. See
    # tabs._render_save_restore_expander. This single panel merges the former
    # Plot-configuration and Annotations panels; it is a top-level menu group of
    # its own, since saving/restoring plot config + annotations is a global
    # session feature, not part of any one source's setup.
    save_restore_slot = menu.save_restore

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
    # Dispatch the active view (sidebar nav). Only one view body renders per run
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
        with setup_metadata_slot:
            st.divider()
            st.subheader("👤 Participant metadata")
            # The *unfiltered* readers: the join report describes the dataset,
            # not whatever the current Narrow-by left standing.
            render_participant_metadata_section(participants_all)
        with setup_body_slot:
            st.divider()
            st.subheader("🔎 What's in this dataset")
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
        # view without reopening the sidebar.
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
    # reachable when a non-Scanpath view is active (it's a sidebar panel). The
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
        slot=save_restore_slot,
    )
    # ENG-30: the automatic counterpart to the portable JSON above — what the app
    # is keeping on this machine, and the controls for it. It is FILLED after
    # this run's save_local_state, or it would report the previous run's cache
    # and read "nothing stored yet" on the run that first stores something —
    # which is exactly why the slot has to be a popover reserved up front rather
    # than something rendered in place down here.
    recovery_cache_slot = menu.recovery_cache

    # Share now lives in the Scanpath view's "🔗 Share" subtab (rendered via the
    # share_renderer passed into render_single_trial_tab), so it builds its deep
    # link from the resolved trial + live viz settings right where it's shown.

    # The ❓ Help menu group: replay the welcome tour (the tour itself renders
    # early in this function — see the maybe_show_welcome_tour call), the task
    # tutorials, the FAQ, the docs, and About.
    help_menu = menu.help
    render_tour_replay_button(help_menu)
    render_tutorial_library(
        build_tutorial_context(words_filtered, fixations_filtered, combos),
        host=help_menu,
    )
    # UX-15: a handful of recurring questions answered in-app, linking out to the
    # full FAQ / tutorials on the docs site for anything longer. Like the tour
    # button it only arms the dialog; maybe_show_faq (above) opens it.
    render_faq_button(help_menu)
    # UX-17: the docs site is the full reference — link it directly here, not
    # only from inside the About dialog.
    # The "↗" marks it as leaving the app — a link_button opens a new browser tab,
    # unlike every other control on the menu bar.
    help_menu.link_button(
        "📚 Documentation ↗",
        CITATION["docs_url"],
        width="stretch",
        help="Guides, the column-mapping reference, and the Python API. Opens in "
        "a new tab.",
    )
    render_about_button(help_menu)
    # UX-37: the way *in* to debug mode. It used to be a `?debug=1` URL param,
    # which meant only someone who already knew about it could find it — the
    # same "hidden behind a URL" problem as the synthetic trial. The toggle sits
    # at the foot of ❓ Help, below the user-facing entries, because it is a
    # developer/bug-report affordance rather than something to reach for daily.
    help_menu.divider()
    render_debug_toggle(help_menu)

    # Developer debug panel — hidden unless that toggle is on, which is also
    # what put the 🐛 Debug popover on the menu bar to host it.
    render_debug_panel(menu.debug)

    # Persist after all view/menu widgets have written their current values.
    # The helper fingerprints the session and is a no-op on unchanged reruns.
    save_local_state(st.session_state, app_url)
    # …then report on what that just wrote, into the slot reserved above.
    _render_recovery_cache_panel(app_url, slot=recovery_cache_slot)


if __name__ == "__main__":
    main()
