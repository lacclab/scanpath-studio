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

import contextlib
import copy
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st
from streamlit import runtime
from streamlit.errors import StreamlitAPIException

# Allow running via `streamlit run scanpath_studio/app.py` by adding the
# repository root to sys.path when executed as a script instead of a package.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scanpath_studio import dataset_table, loading, progress, wizard_shell
from scanpath_studio import metadata as metadata_mod
from scanpath_studio.annotations import (
    filter_keys,
)
from scanpath_studio.column_names import (
    ACTIVE_COLUMN_NAMES_KEY,
    ColumnNames,
    active_all,
    from_schema,
)
from scanpath_studio.column_names import active as active_names
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    AUTHOR_CHOICE,
    BACKGROUND_PRESETS,
    BENCHMARK_LABEL_SUFFIX,
    BENCHMARK_SHORT_SUFFIX,
    BENCHMARK_WIP_SUFFIX,
    CITATION,
    DATA_EDITOR_KEY,
    DATA_EDITOR_OFFSCREEN_KEY,
    DATA_OVERVIEW_KEY,
    DATA_PAGE_KEY,
    DATA_PAGE_OFFSCREEN_KEY,
    DATASET_COUNTS_STORE_KEY,
    DATASET_DESCRIPTIONS_KEY,
    DATASET_EDITOR_OPEN_KEY,
    DATASET_SETUP_OVERRIDES_KEY,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIGURE_SIZE,
    DEFAULT_LINE_SPACING,
    DEMO_CHOICE,
    DOWNLOAD_DIR_ENV,
    DOWNLOAD_DIR_KEY,
    EYEGENBENCH_DEFAULT_DIR,
    FOCUS_MAPPING_KEY,
    FONT_FAMILY,
    ICONS,
    MANUAL_SAMPLE_CHOICE,
    MULTIPLEYE_BUNDLE_CHOICE,
    MULTIPLEYE_DEFAULT_DIR,
    ONESTOP_CHOICE,
    ONESTOP_LEGACY_SOURCE_TOKEN,
    ONESTOP_PUBLIC_DEFAULT_DIR,
    ONESTOP_REGIME_CHOICES,
    ONESTOP_REGIME_LABELS,
    ONESTOP_REGIME_SOURCE_TOKENS,
    POTEC_DEFAULT_DIR,
    PUBLIC_DATASETS_CHOICE,
    RAW_GAZE_LINK_FOR_KEY,
    RAW_GAZE_SEEDED_FOR_KEY,
    RAW_GAZE_SNAP_RESTORE_KEY,
    SETUP_OVERRIDE_FOR_KEY,
    SETUP_OVERRIDE_RESTORE_KEY,
    SETUP_OVERRIDE_SESSION_KEYS,
    SYNTHETIC_CHOICE,
    TRIAL_IDENTITY_CHECK_KEY,
    TRIAL_IDENTITY_FULL_KEY,
    UPLOAD_CHOICE,
    UPLOAD_FILE_TYPES,
    WIZARD_LEAVE_KEY,
    WIZARD_STAY_KEY,
    WORD_LABEL_COLOR,
    benchmark_corpora_enabled,
    icon_html,
    language_display,
    multipleye_enabled,
    plural,
    preprocessing_enabled,
    spoken,
    upload_limit_mb,
)
from scanpath_studio.controls import (
    _LABEL_GAP,
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    WORD_FIELD_SPECS,
    _label_w,
    _labeled,
    _pin,
    _row_label,
    _sub_caption,
    _sub_row,
    clear_trial_filter,
    clear_trial_filters,
    column_mapping_ui,
    has_active_trial_filters,
    read_trial_filters,
    unique_field_labels,
    viz_settings_from_state,
)
from scanpath_studio.data import (
    FIX_OPTIONAL_FIELDS,
    IDENTITY_SCHEMA_FIELDS,
    STIMULUS_WORDS_FLAG,
    TRIAL_IDENTITY_SAMPLE,
    WORD_OPTIONAL_FIELDS,
    ReadPlan,
    StimulusJoin,
    adopt_source,
    assign_derived,
    clear_frame_cache,
    compute_canvas_size,
    count_trials,
    default_filters,
    diagnose_filters,
    diagnose_trial_identity,
    empty_fixations_frame,
    empty_words_frame,
    filter_data,
    filter_frame_to_keys,
    filter_to_keys,
    filter_trials,
    frame_cache,
    frame_fingerprint,
    harmonize_frames_reporting,
    hashable_key,
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
    raw_gaze_in_pool,
    read_table,
    read_table_columns,
    read_tables,
    repair_stranded_stimulus_words,
    reset_fingerprint_memo,
    resolve_stimulus_image_paths,
    stamp_source,
    text_ids,
    trial_identity_warning,
    trial_keys,
    trial_mapping_columns,
    upload_exceeds_limit,
    uploaded_files_total_bytes,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
    vouch_for_frames,
)
from scanpath_studio.dataset_table import DATASET_COUNT_FIELDS, DatasetRow
from scanpath_studio.datasets import (
    POTEC_FIX_SCHEMA,
    POTEC_WORD_SCHEMA,
    load_multipleye_server_bundle,
    multipleye_bundle_dir,
)
from scanpath_studio.debug_log import (
    debug_enabled,
    install_log_capture,
    log_state_change,
    maybe_show_debug,
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
from scanpath_studio.html_embed import embed_html_iframe
from scanpath_studio.menu import (
    close_open_popovers,
    render_nav,
    render_top_menu,
    view_label,
)
from scanpath_studio.multipart import SCREEN_ID, extract_part, part_catalog
from scanpath_studio.persistence import (
    PERSIST_ENV_VAR,
    cache_failure,
    cache_status,
    clear_local_state,
    consume_restore_skipped,
    discard_failed_dataset,
    failed_datasets,
    human_size,
    is_loopback_url,
    local_state_restored,
    persistence_enabled,
    persistence_paused,
    restore_local_state,
    restored_from_cache,
    restored_summary,
    retry_cache_restore,
    retry_failed_datasets,
    save_local_state,
    server_bound_to_loopback,
)
from scanpath_studio.session_keys import COLUMN_MAPPING_PREFIX, PARAM_CORPUS
from scanpath_studio.styles import get_app_css
from scanpath_studio.tabs import (
    _EDITOR_KEY_NOISE,
    _REMAP_DIRTY_KEY,
    _TABLE_LABELS,
    EDITOR_NAME_FIELD_KEY,
    EDITOR_PENDING_NAME_KEY,
    STIMULUS_JOIN_NOTICE_KEY,
    _build_figure_settings,
    _render_column_mapping_section,
    commit_builtin_setup,
    data_scope_text,
    dataset_editor_is_dirty,
    discard_editor_widgets,
    pool_filter_frames,
    render_analysis_pool_bar,
    render_corpus_analysis_tab,
    render_data_health,
    render_data_inspection_tab,
    render_dataset_capabilities,
    render_dataset_editor_footer,
    render_participant_metadata_section,
    render_settings_file,
    render_single_trial_tab,
    render_text_metadata_section,
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
from scanpath_studio.truncation_tooltip import render_truncation_tooltips
from scanpath_studio.url_state import (
    CORPUS_SOURCE_TOKEN,
    _apply_pending_trial_selection,
    _apply_uploaded_plot_config,
    _apply_url_preset,
    _apply_url_trial_selection,
    _build_share_query,  # noqa: F401  re-exported for tests
    _go_data,
    _render_share_body,
    apply_pending_preprocessing,
    corpus_choice_for_slug,
    link_sets,
    link_setup_keys_for,
    scope_link_setup,
)

# NOTE: ``scanpath_studio.wizard`` is imported lazily inside the two functions
# that use it (resolve_data_source, main), not here. wizard does
# ``from . import app`` at module top, so a top-level import here forms a cycle:
# under ``streamlit run app.py`` the script isn't registered as
# ``scanpath_studio.app``, so wizard's ``from . import app`` re-imports app fresh,
# re-entering this import while wizard is still half-loaded → ImportError.
# Deferring it lets app finish loading before wizard is ever imported.
from scanpath_studio.utils import build_combo_options, combo_source, extract_trial

# Re-exported under a private alias so tests can import it from `app`; keep the
# F401 silence (it's not used by app.py itself).
from scanpath_studio.utils import (  # noqa: F401
    build_comparison_options as _build_comparison_options,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from streamlit.delta_generator import DeltaGenerator


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


#: UX-109 follow-up. The CSS `direction: ltr` rule in `get_app_css` does not
#: reach this: Streamlit's own widgets (the trial-position slider among them)
#: are built on react-aria, whose `useLocale()` decides RTL straight from
#: `navigator.language` — never from the page's CSS `direction` or a
#: `dir="rtl"` attribute — confirmed by reading Streamlit's own shipped
#: `Slider.*.js`, which flips its thumb's percentage (`B = 1 - B`) whenever
#: that locale reads as RTL. A Hebrew-locale browser therefore renders the
#: thumb at the *mirrored* position while the surrounding markup (this app's
#: own CSS, the filled-track gradient) stays physically left-to-right,
#: producing exactly the reported screenshot: thumb correct for a mirrored
#: scale, fill correct for a normal one, agreeing nowhere except the ends.
#: This app has no RTL content of its own to get right, so the fix is to make
#: every react-aria consumer see a LTR locale regardless of the browser's:
#: override `navigator.language`/`languages` on the *parent* window (this
#: embed is same-origin, so it is the same `Navigator` object React reads,
#: not a copy) and fire `languagechange`, which is the event react-aria's own
#: locale cache listens for to invalidate itself and re-render every mounted
#: consumer — needed because Streamlit's own chrome (top nav, main menu) can
#: easily have already read+cached the browser's real locale before this
#: script ever gets a chance to run.
_FORCE_LTR_LOCALE_SCRIPT = """
<script>
(function () {
    try {
        var nav = window.parent.navigator;
        Object.defineProperty(nav, "language", {
            get: function () { return "en-US"; },
            configurable: true,
        });
        Object.defineProperty(nav, "languages", {
            get: function () { return ["en-US"]; },
            configurable: true,
        });
        window.parent.dispatchEvent(new Event("languagechange"));
    } catch (e) {
        /* A browser that refuses the redefinition leaves the page as it
           found it — no worse than before this ran. */
    }
})();
</script>
"""


#: BUG-86. Streamlit's `help=` tooltip keeps its panel open for as long as
#: focus is inside the trigger, and it can leave several panels in the page at
#: once — some still open, some stuck half-closed (`data-exiting`) with no
#: owner at all; a clicked ▶ left "Next trial." behind through reruns. CSS alone
#: can only ask "is *some* trigger hovered?", so hovering any tooltip button
#: brought every stale panel back. This marks a panel *owned* while its **own**
#: trigger — the element whose `aria-describedby` names the panel's id — is
#: `:hover` or holds `:focus-visible`, and `styles.get_app_css` hides every
#: panel that is not, once this is running (the `data-sps-tooltip-owners` flag
#: on `<html>`). It reads only the browser's own hover/focus state and never
#: touches React's, so it cannot fight the component.
#:
#: A panel is judged the moment it appears — synchronously in a
#: `MutationObserver`, which runs before the browser paints — so a stale one
#: is never shown for a frame; pointer and focus moves re-judge at most once a
#: frame. The code runs in the *parent* page's realm (a `<script>` added to its
#: head, once per page load), not as closures from this iframe's: an iframe's
#: listeners die with it, which is what BUG-51 had to hand-roll a heartbeat for.
_TOOLTIP_OWNER_SCRIPT = """
<script>
(function () {
    function install() {
        var OWNED = "data-sps-tooltip-owned";
        var PANEL = '[data-testid="stTooltipContent"], '
            + '[data-testid="stTooltipErrorContent"]';
        var pending = false;
        function ownerIsActive(tip) {
            if (!tip.id) { return false; }
            var owner = document.querySelector(
                '[aria-describedby~="' + CSS.escape(tip.id) + '"]'
            );
            return !!owner && (
                owner.matches(":hover")
                || owner.matches(":focus-visible")
                || !!owner.querySelector(":focus-visible")
            );
        }
        function update() {
            pending = false;
            var tips = document.querySelectorAll('[role="tooltip"]');
            for (var i = 0; i < tips.length; i++) {
                var tip = tips[i];
                if (!tip.querySelector(PANEL)) { continue; }
                var owned = ownerIsActive(tip);
                if (owned !== tip.hasAttribute(OWNED)) {
                    tip.toggleAttribute(OWNED, owned);
                }
            }
        }
        function schedule() {
            if (pending) { return; }
            pending = true;
            requestAnimationFrame(update);
        }
        ["pointerover", "pointerout", "focusin", "focusout", "keydown"].forEach(
            function (type) { document.addEventListener(type, schedule, true); }
        );
        new MutationObserver(update).observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["aria-describedby"],
        });
        update();
        document.documentElement.setAttribute("data-sps-tooltip-owners", "");
    }
    try {
        var host = window.parent;
        if (host.__spsTooltipOwnerInstalled) { return; }
        var script = host.document.createElement("script");
        script.textContent = "(" + install.toString() + ")();";
        host.document.head.appendChild(script);
        host.__spsTooltipOwnerInstalled = true;
    } catch (e) {
        /* The CSS floor in styles.get_app_css still hides every panel while
           no trigger is hovered or keyboard-focused. */
    }
})();
</script>
"""

#: UX-193: a click on an embedded iframe — the scanpath plot above all, which
#: spans the whole main column — never closed an open popover. Streamlit
#: dismisses one on a `click` on the *page's* document, and a click inside an
#: iframe lands in that iframe's document instead. What the page does see is
#: its window losing focus to the frame, so on `blur` with an `<iframe>` now
#: active (and not one inside a popover) this clicks every expanded popover
#: trigger, which toggles it shut — the same move as `menu.close_open_popovers`.
#: Installed in the parent's realm once per page load, like the script above.
_IFRAME_CLICK_CLOSES_POPOVER_SCRIPT = """
<script>
(function () {
    function install() {
        window.addEventListener("blur", function () {
            setTimeout(function () {
                var active = document.activeElement;
                if (!active || active.tagName !== "IFRAME") { return; }
                if (active.closest('[data-st-overlay-root="true"]')) { return; }
                document.querySelectorAll(
                    '[data-testid="stPopover"] button[aria-expanded="true"]'
                ).forEach(function (trigger) { trigger.click(); });
            }, 0);
        });
    }
    try {
        var host = window.parent;
        if (host.__spsIframePopoverCloseInstalled) { return; }
        var script = host.document.createElement("script");
        script.textContent = "(" + install.toString() + ")();";
        host.document.head.appendChild(script);
        host.__spsIframePopoverCloseInstalled = true;
    } catch (e) {
        /* Not same-origin: clicks outside the iframes still close popovers. */
    }
})();
</script>
"""


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
        # UX-138 left the favicon an emoji on purpose: Streamlit draws an emoji
        # page icon as an inline SVG, but turns a `:material/…:` one into a
        # fonts.gstatic.com URL — a request to Google on every page load, and no
        # icon at all offline or in the desktop bundle.
        page_icon="👀",
        layout="wide",
    )
    st.markdown(get_app_css(), unsafe_allow_html=True)
    embed_html_iframe(_FORCE_LTR_LOCALE_SCRIPT, height=0)
    embed_html_iframe(_TOOLTIP_OWNER_SCRIPT, height=0)
    embed_html_iframe(_IFRAME_CLICK_CLOSES_POPOVER_SCRIPT, height=0)


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
    triggers share. The container is still created, and deliberately: it is
    where anything page-level would go (see ``menu.render_top_menu``).
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
    # DATA-66: each filter by the dataset's own name for its column, as the
    # filter panel titles it; UX-149: no two share a label.
    names = unique_field_labels(
        [
            *(trial_filters.get("metadata") or {}),
            *(trial_filters.get("ranges") or {}),
        ],
        active_all(st.session_state).label,
    )
    for col, allowed in (trial_filters.get("metadata") or {}).items():
        label = f"{names[col]} = {', '.join(sorted(map(str, allowed))[:4])}"
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
    dropping = set(trial_filters.get("ranges_drop_unknown") or ())
    for col, bounds in (trial_filters.get("ranges") or {}).items():
        label = f"{names[col]} between {bounds[0]:g} and {bounds[1]:g}"
        if col in dropping:
            label += " (unknown values excluded)"
        steps.append(
            (
                label,
                lambda w, f, c=col, b=bounds, d=col in dropping: filter_trials(
                    w, f, ranges={c: b}, drop_unknown=(c,) if d else None
                ),
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
    words_all: pd.DataFrame,
    fixations_all: pd.DataFrame,
    trial_filters: dict,
    filter_frames: tuple,
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
                f"the {ICONS['view_data']} **Data Management** page."
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
                    # BUG-115: the funnel is not drawn beside this panel, so the
                    # other filters are re-derived from the frames it filters.
                    kwargs={"frames": filter_frames},
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


#: UX-136 — the kinds `persistence.restored_summary` counts, in the order the
#: *Saved on this computer* section lists them, with their singular/plural nouns.
#: DATA-38 added the attached metadata tables.
_RESTORED_KIND_NOUNS = (
    ("datasets", "dataset", "datasets"),
    ("annotations", "annotation", "annotations"),
    ("designs", "design", "designs"),
    ("metadata", "metadata table", "metadata tables"),
)


def _restored_recap(session=None) -> str:
    """What came back from the recovery cache, as a phrase for the toast.

    "2 datasets and 3 annotations" — only the kinds that actually restored, so
    the sentence never pads itself with the zeros the panel legitimately shows.
    Falls back to "your last session" if it is somehow called with nothing to
    report, which keeps the toast a sentence rather than a hole.
    """
    summary = restored_summary(st.session_state if session is None else session)
    parts = [
        f"{summary[key]:,} {singular if summary[key] == 1 else plural}"
        for key, singular, plural in _RESTORED_KIND_NOUNS
        if summary.get(key)
    ]
    if not parts:
        return "your last session"
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _pick_download_folder() -> None:
    """📁 beside the Download folder box: a native picker, applied next run."""
    chosen = _pick_directory_dialog()
    if chosen:
        st.session_state[f"{DOWNLOAD_DIR_KEY}_picked"] = chosen
    else:
        st.session_state[f"{DOWNLOAD_DIR_KEY}_no_picker"] = True


def _render_download_folder_section(host) -> None:
    """🗂️ Data → **Download folder** (UX-184).

    One folder for every ⬇ Download, so a user chooses where the corpora go once
    rather than per dataset — the per-dataset Data directory box still
    overrides it. Before this the folder was implicit (the checkout's ``data/``,
    or the per-user data home: ``%LOCALAPPDATA%`` on Windows) and the page only
    ever said ``data/PoTeC``. Not drawn where the app may not touch local
    folders (S2) — there the server's configuration decides.
    """
    if not local_filesystem_enabled():
        return
    picked = st.session_state.pop(f"{DOWNLOAD_DIR_KEY}_picked", None)
    if picked:
        st.session_state[DOWNLOAD_DIR_KEY] = picked
    st.session_state.setdefault(DOWNLOAD_DIR_KEY, "")
    host.divider()
    host.subheader(f"{ICONS['download']} Download folder")
    host.caption(
        "Where **Download** saves a public dataset, each in its own subfolder. "
        "Leave it blank for the default. A dataset's own *Data directory* box "
        "overrides it."
    )
    text_col, browse_col = host.columns([4, 1])
    text_col.text_input(
        "Download folder",
        key=DOWNLOAD_DIR_KEY,
        placeholder=str(_default_download_folder()),
        label_visibility="collapsed",
        # Rendered only on the Data page's overview; without this the choice
        # would be dropped the first run another view is open (BUG-15).
        persist_state="session",
    )
    browse_col.button(
        # UX-200: named for screen readers; the folder icon is all that shows.
        f"{ICONS['folder']} {spoken('Choose the download folder')}",
        wrap=True,
        key=f"{DOWNLOAD_DIR_KEY}_browse",
        help="Browse for a folder",
        on_click=_pick_download_folder,
    )
    if st.session_state.pop(f"{DOWNLOAD_DIR_KEY}_no_picker", False):
        host.caption("Folder picker unavailable here — type or paste the path.")
    host.markdown(f"**Saving to:** `{download_folder()}`")


def _retry_cached_datasets() -> None:
    """``on_click``: read the held-back cached datasets again."""
    retry_failed_datasets(st.session_state)


def _remove_cached_dataset(name: str) -> None:
    """``on_click``: delete one held-back dataset's entry and files from the cache."""
    discard_failed_dataset(st.session_state, name)


def _retry_unreadable_cache(app_url: str) -> None:
    """``on_click``: try the whole cache again, as a reload would."""
    retry_cache_restore(st.session_state, app_url)


def _clear_unreadable_cache() -> None:
    """``on_click``: delete a cache that cannot be read; saving resumes."""
    clear_local_state(st.session_state)


def render_cache_recovery_notice(host, app_url: str, *, key: str) -> bool:
    """What of the recovery cache this session could not restore, with actions.

    Drawn where the recovery notices go (the page's notices) and again in
    🗂️ Data → *Saved on this computer*, with ``key`` keeping the two sets of
    buttons apart. Two cases, never the third — a cache that is absent, or was
    cleared on purpose, is not a failure and says nothing:

    - **a dataset** whose files are missing or unreadable. The rest restored;
      this one is held back, and kept in the cache — every save writes it back
      as it was — so **Retry** can read it once its file is back, and **Remove
      from cache** deletes it.
    - **the cache as a whole** (a manifest that cannot be read). Saving is
      paused so this session cannot replace it; **Retry** reads it again and
      **Clear the cache** deletes it, after which saving resumes.

    Returns whether anything was drawn.
    """
    failure = cache_failure(st.session_state)
    failed = failed_datasets(st.session_state)
    if not failure and not failed:
        return False
    box = host.container(border=True)
    if failure:
        box.warning(
            f"The recovery cache on this computer couldn't be read — {failure}. "
            "Nothing was restored from it, and saving is paused so it stays as it "
            "is.",
            icon=ICONS["warning"],
        )
        row = box.container(horizontal=True)
        row.button(
            "Retry",
            icon=ICONS["refresh"],
            key=f"{key}_retry_cache",
            on_click=_retry_unreadable_cache,
            args=(app_url,),
        )
        row.button(
            "Clear the cache",
            icon=ICONS["delete"],
            key=f"{key}_clear_cache",
            on_click=_clear_unreadable_cache,
            help="Delete the stored session. Saving resumes.",
        )
        return True
    box.warning(
        f"{len(failed)} dataset{'s' if len(failed) != 1 else ''} saved on this "
        "computer couldn't be restored. Everything else came back. "
        f"{'They are' if len(failed) != 1 else 'It is'} kept in the cache until "
        "you retry or remove it.",
        icon=ICONS["warning"],
    )
    for index, (name, reason) in enumerate(sorted(failed.items())):
        row = box.container(horizontal=True, vertical_alignment="center")
        row.markdown(f"**{name}** — {reason}")
        row.button(
            "Retry",
            icon=ICONS["refresh"],
            key=f"{key}_retry_{index}",
            on_click=_retry_cached_datasets,
        )
        row.button(
            "Remove from cache",
            icon=ICONS["delete"],
            key=f"{key}_remove_{index}",
            on_click=_remove_cached_dataset,
            args=(name,),
            help="Delete this dataset's stored copy. Its annotations are kept.",
        )
    return True


def _render_saved_here_section(app_url: str, host) -> None:
    """🗂️ Data → **Saved on this computer** (UX-179; ENG-30 underneath).

    The foot of the Data page's overview, and a read-out only: what the
    recovery cache holds and the folder it is in. It was the retired 💾 Session
    dialog's first block; it lives here because its count is "datasets **you
    added**", which is the table above it.

    UX-179 left it no controls. The *Save changes automatically* toggle, *Clear
    recovery cache* and *Reset everything* are gone: opting out is a launch
    choice (``run --no-persist`` / ``SCANPATH_STUDIO_PERSIST=0``, in the FAQ),
    and clearing is ``scanpath-studio cache --clear`` or ``api.clear_cache``.
    The one in-session pause left is BUG-71's, after a restore that crashed,
    which the section names.

    Drawn *after* this run's ``save_local_state`` (``main``'s
    ``_finish_page``), so the status line reports the write that just happened.
    ``cache_status`` re-reads the manifest each run — a few ``stat`` calls and a
    small JSON — rather than being cached: a status line that lags what it
    reports is worse than none.
    """
    status = cache_status(url=app_url)
    host.divider()
    host.subheader(f"{ICONS['recovery']} Saved on this computer")
    if not status["enabled"]:
        host.caption(
            "**Not available here.** This deployment keeps your work in memory "
            "only — closing or refreshing the tab loses the datasets you "
            "uploaded, their column mappings and your annotations. Export the "
            "annotations from **Annotations** above, and the figure's settings "
            f"from {ICONS['view_scanpath']} Scanpath → {ICONS['share']} Share → **File**."
            + (
                f" Turned off by `{PERSIST_ENV_VAR}=0`."
                if status["override"] == "off"
                else ""
            )
        )
        return

    host.caption(
        "Saved as you work, and reopened next time. Nothing is uploaded anywhere."
    )
    if restored_from_cache(st.session_state):
        host.success("Recovered when the app opened.", icon=ICONS["recovery"])
    if status["exists"] and status["readable"]:
        n_sets = len(status["datasets"])
        # "datasets **you added**", not "datasets": only an upload is copied
        # here — the bundled demo and the public corpora reload from their own
        # source — so the count reads 0 while one of those is open, which looked
        # like a bug until the line said which datasets it was counting.
        host.markdown(
            f"**Saved here:** {n_sets} dataset{'s' if n_sets != 1 else ''} "
            f"you added · {status['annotations']} annotation"
            f"{'s' if status['annotations'] != 1 else ''} · "
            f"{status['designs']} design"
            f"{'s' if status['designs'] != 1 else ''} · "
            # DATA-38 — named only when there are any, so the common line keeps
            # its length.
            + (
                f"{status['metadata']} metadata table"
                f"{'s' if status['metadata'] != 1 else ''} · "
                if status.get("metadata")
                else ""
            )
            + f"{human_size(status['bytes'])}"
        )
    elif status["exists"] and not cache_failure(st.session_state):
        host.warning(
            "The stored session can't be read (written by a different version, "
            "or incomplete).",
            icon=ICONS["warning"],
        )
    elif not status["exists"]:
        host.caption("Nothing saved yet. The first change creates the cache.")
    render_cache_recovery_notice(host, app_url, key="saved_here_recovery")
    host.markdown(f"**Folder:** `{status['directory']}`")
    if persistence_paused(st.session_state) and not cache_failure(st.session_state):
        # BUG-71 — the only pause left: the last launch never finished opening
        # with this cache, so this session neither restored nor overwrites it.
        host.caption(
            "Saving is paused for this session, so the copy above stays as it "
            "was. Reload to try restoring it again, or delete it with "
            "`scanpath-studio cache --clear`."
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


@st.dialog(f"{ICONS['about']} About Scanpath Studio", width="large")
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
        f"doi = {{{CITATION['doi']}}},\n"
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

Developed by [Omer Shubi](https://omershubi.github.io/),
[Keren Gruteke Klein](https://kerengruteke.github.io/),
[Maya Grossman](https://www.linkedin.com/in/maya-harram-32b547292/),
[Ella Lion](https://ella-lion.github.io/),
[Deborah N. Jakobi]({_DILI}/lab-members/jakobi.html),
[David R. Reich]({_DILI}/lab-members/reich.html),
[Lena Jäger]({_DILI}/group-leader/jaeger.html), and
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/).

{ICONS["docs"]} [Documentation]({CITATION["docs_url"]}) ↗ ·
{ICONS["code"]} [Code]({CITATION["url"]}) ↗ ·
{ICONS["doi"]} [DOI](https://doi.org/{CITATION["doi"]}) ↗
"""
    )
    # UX-16: the BibTeX block is tall enough to push everything above it out
    # of view, so it opens on demand — but it stays a named section of its
    # own (a bold label) rather than a footnote, since "how do I cite this?" is
    # the single most common reason to open About. The dividers that used to
    # separate the three blocks are gone (the user's call): on a modal this
    # short the bold headings already carry the split, and three rules in half a
    # screen read as clutter.
    st.markdown(
        f"**{ICONS['docs']} Citing Scanpath Studio** — a paper is in preparation."
    )
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
    # disclaimer either: MIT already carries that. The heading says the
    # "built with AI assistance" half, so the prose no longer repeats it.
    st.markdown(f"**{ICONS['ai']} Built with AI assistance**")
    st.markdown(
        f"""
Cross-check results before publishing.

If something looks wrong — or if you have a feature request or suggestion —
[open an issue]({CITATION["url"]}/issues) ↗.
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


def _onestop_structure_md(regime: str) -> str:
    """Expected-files note for one OneStop regime's dataset (DATA-63)."""
    from scanpath_studio import datasets

    listing = "\n".join(
        f"├─ {datasets._onestop_report_path(Path('<dir>'), kind, regime, part).name}"
        for part in datasets.onestop_regime_parts(regime)
        for kind in ("ia", "fixations")
    )
    return f"""\
**Expected files** — the OSF reports for every part of this regime, placed
directly in the folder (or fetched by **Download**). Only *Paragraph* is
regime-split on OSF; the other parts come from the all-regimes full release,
which the four OneStop datasets share, and are cut to this regime when read:
```
<dir>/
{listing}
```
"""


def _project_root() -> Path:
    """Where the *relative* data dirs (``data/OneStop`` etc.) resolve.

    Used to anchor the relative default data dirs and relative user-entered
    paths, so the "found vs. download" status resolves regardless of the
    process cwd (the server may run from anywhere). Computed from this module's
    location, not ``os.getcwd()``.

    ENG-59: that location is only a *project* in a source checkout. In an
    installed copy the folder above the package is ``site-packages`` (or the
    desktop bundle's ``_internal/``), so ⬇ Download wrote the corpora into the
    environment — orphaned by ``pip uninstall``, lost with the venv, refused on
    a read-only install. There they resolve under a per-user data directory
    instead (``SCANPATH_STUDIO_DATA_HOME`` overrides it).
    """
    checkout = Path(__file__).resolve().parent.parent
    if (checkout / "pyproject.toml").is_file():
        return checkout
    return _user_data_home()


def _user_data_home() -> Path:
    """Per-user home for downloaded corpora in an installed copy (ENG-59)."""
    override = os.environ.get("SCANPATH_STUDIO_DATA_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "scanpath-studio"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "scanpath-studio"


def _default_download_folder() -> Path:
    """Where downloads go when nobody chose: ``SCANPATH_STUDIO_DOWNLOAD_DIR``,
    else ``data/`` under :func:`_project_root` (UX-184)."""
    configured = os.environ.get(DOWNLOAD_DIR_ENV, "").strip()
    if configured:
        return Path(_resolve_data_dir(configured))
    return (_project_root() / "data").resolve()


def download_folder() -> Path:
    """The folder every downloadable corpus goes into, one subfolder each (UX-184).

    The 🗂️ Data page's *Download folder* (a blank box means the default), else
    :func:`_default_download_folder`. A relative entry anchors like a Data
    directory does, and ``SCANPATH_DATA_ROOT`` confines it the same way."""
    chosen = str(st.session_state.get(DOWNLOAD_DIR_KEY) or "").strip()
    if chosen and local_filesystem_enabled():
        return Path(_resolve_data_dir(chosen))
    return _default_download_folder()


def _download_target(default_dir: str) -> str:
    """A downloadable corpus' default Data directory under :func:`download_folder`.

    The built-in defaults are ``data/<corpus>``; that ``data/`` is the download
    folder, so ``data/PoTeC`` becomes ``<folder>/PoTeC``. Anything else (an
    absolute path a test or a deployment pinned) is left as it is."""
    rel = Path(default_dir)
    if not default_dir or rel.is_absolute() or rel.parts[:1] != ("data",):
        return default_dir
    return str(download_folder().joinpath(*rel.parts[1:]))


# DATA-16 (security audit S2). The corpus **Data directory** box takes a
# free-text path from the browser, stats it, reports the result back into the
# page, and — via ⬇ Download — writes into it. On a local run that's just a file
# picker. On anything another person can reach it's a path-existence oracle plus
# an arbitrary-directory write, and the app has no authentication on any
# deployment.
#
# ENG-66: unset, it follows the server's bind address — on for a server that
# listens on loopback only (`scanpath-studio run`, the desktop app), off for one
# other machines can reach (a bare `streamlit run`, a hosted demo), the same rule
# as the recovery cache. `SCANPATH_LOCAL_FS=1` turns it on for a trusted lab
# server and `=0` forces it off. Off hides the path box, the folder picker and
# the download button; `SCANPATH_DATA_ROOT` then supplies the corpus location
# server-side. Setting `SCANPATH_DATA_ROOT` alone is also useful locally: it
# confines every entered path to that subtree.
LOCAL_FS_ENV = "SCANPATH_LOCAL_FS"
_LOCAL_FS_ON = frozenset({"1", "true", "yes", "on"})
_LOCAL_FS_OFF = frozenset({"0", "false", "no", "off"})
DATA_ROOT_ENV = "SCANPATH_DATA_ROOT"


def local_filesystem_enabled() -> bool:
    """Whether the user may point the app at an arbitrary local directory.

    ``SCANPATH_LOCAL_FS`` set to ``1``/``true``/``yes``/``on`` or
    ``0``/``false``/``no``/``off`` decides. Otherwise, inside a Streamlit server,
    it is on only when that server listens on loopback alone
    (:func:`persistence.server_bound_to_loopback`, ENG-66) — so a hosted
    deployment is safe without remembering to set anything — and outside one
    (the API, the CLI) it is on. Read at call time so tests can toggle it."""
    raw = os.environ.get(LOCAL_FS_ENV, "").strip().lower()
    if raw in _LOCAL_FS_ON:
        return True
    if raw in _LOCAL_FS_OFF:
        return False
    return server_bound_to_loopback() if runtime.exists() else True


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


#: BUG-98 — how long a 📁 click may wait for the user to pick a folder.
_FOLDER_PICKER_TIMEOUT_S = 600

_MACOS_PICKER = 'POSIX path of (choose folder with prompt "Choose a folder")'
# STA + a TopMost owner form, or the dialog opens behind the browser; UTF-8 so a
# folder name outside the console's code page comes back intact.
_WINDOWS_PICKER = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
    "$o = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; "
    "if ($d.ShowDialog($o) -eq 'OK') { [Console]::Out.Write($d.SelectedPath) }"
)
_TK_PICKER = (
    "import tkinter as tk; from tkinter import filedialog; "
    "r = tk.Tk(); r.withdraw(); r.wm_attributes('-topmost', 1); "
    "print(filedialog.askdirectory() or '', end='')"
)


def _folder_picker_command() -> list[str] | None:
    """The command that shows this OS's folder dialog and prints the pick (BUG-98).

    The dialog runs in a child process. In-process tkinter ran on Streamlit's
    script thread, and macOS refuses to open a window off the main thread — it
    aborts the whole server (``NSWindow should only be instantiated on the main
    thread``), so one 📁 click took the app down. A child has its own main
    thread, and whatever it does cannot reach the server. The OS's own dialog
    comes first; tkinter is the fallback for a Linux desktop without zenity or
    kdialog, and never in the desktop bundle, which ships no tkinter and whose
    ``sys.executable`` is the app itself. ``None`` when there is none."""
    if sys.platform == "darwin":
        return ["osascript", "-e", _MACOS_PICKER] if shutil.which("osascript") else None
    if sys.platform == "win32":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell:
            return [shell, "-NoProfile", "-STA", "-Command", _WINDOWS_PICKER]
    elif shutil.which("zenity"):
        return ["zenity", "--file-selection", "--directory"]
    elif shutil.which("kdialog"):
        return ["kdialog", "--getexistingdirectory"]
    if getattr(sys, "frozen", False):
        return None
    return [sys.executable, "-c", _TK_PICKER]


def _pick_directory_dialog() -> str | None:
    """Open a native folder picker and return the chosen path, or None.

    Only works when the app runs on a machine with a display (a locally-run
    app). Returns None — and never raises — on a headless host, with no dialog
    to run, or on a cancelled dialog, so the text input stays the portable
    fallback. The dialog is a child process (:func:`_folder_picker_command`,
    BUG-98); this blocks until it closes, as the in-process one did.

    S2: refuses outright on a shared deployment. Degrading to None on a headless
    host was never the guarantee — on a host that *does* have a display, a remote
    visitor clicking 📁 pops a modal dialog on the server's own desktop and blocks
    the thread until someone there dismisses it."""
    if not local_filesystem_enabled():
        return None
    command = _folder_picker_command()
    if command is None:
        return None
    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_FOLDER_PICKER_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # A cancel exits non-zero (osascript, zenity, kdialog) or prints nothing.
    chosen = done.stdout.strip() if done.returncode == 0 else ""
    # osascript's POSIX path ends in "/"; keep a bare root as it is.
    return (chosen.rstrip("/\\") or chosen) if chosen else None


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
    # UX-184: a box still showing the default it was given follows a new
    # Download folder; one the user edited keeps what they typed.
    seeded_key = f"{dir_key}_default"
    seeded = st.session_state.get(seeded_key)
    if (
        seeded is not None
        and seeded != default_dir
        and st.session_state.get(dir_key) == seeded
    ):
        st.session_state[dir_key] = default_dir
    st.session_state[seeded_key] = default_dir
    # Seeded rather than `value=`-ed: the two writes above go through session
    # state, and passing both makes Streamlit warn (as for BUG-17).
    st.session_state.setdefault(dir_key, default_dir)
    text_col, browse_col = cfg.columns([4, 1])
    raw = text_col.text_input(
        "Data directory",
        help=dir_help,
        key=dir_key,
        # A typed path must survive a run in which this input doesn't render —
        # Streamlit drops an unrendered widget's key at end of run (BUG-15 /
        # ENG-36), and *every* one of these inputs renders only while its own
        # corpus is the selected source, so without this it silently forgot a
        # hand-typed location as soon as the user looked at another source. One
        # rule here rather than one call site remembering and three forgetting.
        persist_state="session",
    )
    # Vertical-align the button with the input (past its label).
    browse_col.markdown("<div style='height:1.7em'></div>", unsafe_allow_html=True)
    if browse_col.button(
        # UX-200: named for screen readers; the folder icon is all that shows.
        f"{ICONS['folder']} {spoken('Choose the data folder')}",
        wrap=True,
        key=f"{key_prefix}_browse",
        help="Browse for a folder",
    ):
        chosen = _pick_directory_dialog()
        if chosen:
            st.session_state[f"{dir_key}_picked"] = chosen
            st.rerun()
        else:
            cfg.caption("Folder picker unavailable here — type or paste the path.")
    resolved = _resolve_data_dir(raw)
    # UX-184: a relative entry such as the default `data/PoTeC` resolves against
    # the checkout, or in an installed copy against the per-user data home
    # (ENG-59) — on Windows `%LOCALAPPDATA%`, a folder the box never named, so a
    # finished download looked lost. Name the folder it actually means.
    if resolved and resolved != raw.strip():
        cfg.caption(f"Full path: `{resolved}`")
    with cfg.expander("Expected files", expanded=False):
        st.markdown(structure_md)
    return resolved


def _dataset_folder(key_prefix: str, default_dir: str) -> str:
    """The folder :func:`_dataset_dir_input` would resolve, without drawing it.

    BUG-113: the dataset table states every row's status, and a corpus that is
    not open has no loader running to draw its location box. This reads the
    same state the box keeps — a typed path, else the default, which a box still
    showing its old seeded default follows (UX-184) — and resolves it the same
    way, so the row and the loader can never disagree about where the files are.
    """
    if not local_filesystem_enabled():
        return str(data_root()) if data_root() else _resolve_data_dir(default_dir)
    dir_key = f"{key_prefix}_dir"
    typed = str(st.session_state.get(dir_key) or "").strip()
    if not typed or typed == st.session_state.get(f"{dir_key}_default"):
        typed = default_dir
    return _resolve_data_dir(typed)


def _potec_files_present() -> bool:
    from scanpath_studio import datasets

    root = _dataset_folder("potec", _download_target(POTEC_DEFAULT_DIR))
    return datasets.potec_present(root)


def _onestop_files_present(regime: str) -> bool:
    from scanpath_studio import datasets

    root = _dataset_folder(
        "onestop_public", _download_target(ONESTOP_PUBLIC_DEFAULT_DIR)
    )
    parts = datasets.onestop_regime_parts(regime)
    return datasets.onestop_present(root, regime=regime, parts=parts)


def _multipleye_files_present() -> bool:
    root = _dataset_folder("multipleye", MULTIPLEYE_DEFAULT_DIR)
    source = st.session_state.get("multipleye_fixation_source") or "scanpaths"
    sessions, _ = _cached_multipleye_inventory(root, source)
    return bool(sessions)


def _benchmark_files_present(dataset: str) -> bool:
    from scanpath_studio.eyegenbench import eyegenbench_present

    root = _dataset_folder("eyegenbench", EYEGENBENCH_DEFAULT_DIR)
    return eyegenbench_present(root, dataset)


# UX-7(b): session slot describing a data source the user selected but that
# isn't available locally. Written by `_dataset_access_status` (and the bundle
# sources) on the run it happens, read + cleared by `_render_dataset_unavailable`
# in the main area — and dropped at the start of every full run (BUG-96), so a
# run that returns early never passes it on. Kept out of the loader return
# value so the loaders can keep falling back to the demo corpus and the app
# stays usable.
_UNAVAILABLE_KEY = "_dataset_unavailable"
#: UX-174: whether this run is showing the demo *in place of* the selected
#: corpus. Cleared at the start of every full run and set with the note above
#: (which is consumed before the dataset table draws), so it describes this run
#: on every path, early returns included; a fragment rerun of the table reads
#: the last full run's answer. The table reads it so the demo's rows are never
#: counted as that corpus' "loaded" figures.
_PLACEHOLDER_SHOWN_KEY = "_dataset_placeholder_shown"
#: DATA-48 — the corpus the bundled demo last stood in for. While it does, that
#: corpus' annotations are filed under the demo's name: the trials on screen are
#: the demo's, so a star made on them is the demo's, and must not wait under a
#: corpus whose own trials (once it is set up) merely share their ids.
_ANNOTATIONS_STANDIN_KEY = "_annotations_standin_for"


def annotations_owner(dataset: str) -> str:
    """The dataset whose annotations ``dataset``'s screen shows (DATA-48)."""
    if st.session_state.get(_ANNOTATIONS_STANDIN_KEY) == dataset:
        return DEMO_CHOICE
    return dataset


def _annotations_dataset(token: str) -> str:
    """The dataset the annotation store belongs to now, else ``token``."""
    import scanpath_studio.annotations as _annotations

    return _annotations.current_dataset(st.session_state) or token


def _file_annotations_under_shown_dataset(dataset: str) -> None:
    """After the load: point the annotation store at what is actually shown.

    ``annotations.activate_dataset`` runs before the load, when nobody knows
    yet whether ``dataset`` is on disk; the loader then reports the demo
    standing in (:data:`_PLACEHOLDER_SHOWN_KEY`). Remembering which corpus it
    stood in for lets the next run's first activation pick the demo straight
    away — one swap, not a swap and back on every run.
    """
    import scanpath_studio.annotations as _annotations

    if st.session_state.get(_PLACEHOLDER_SHOWN_KEY):
        st.session_state[_ANNOTATIONS_STANDIN_KEY] = dataset
        _annotations.activate_dataset(st.session_state, DEMO_CHOICE, adopt=False)
    elif st.session_state.get(_ANNOTATIONS_STANDIN_KEY) == dataset:
        st.session_state.pop(_ANNOTATIONS_STANDIN_KEY, None)
        _annotations.activate_dataset(st.session_state, dataset, adopt=False)
    # Only now is it known which dataset is shown, so only now may it adopt an
    # old cache's unassigned entries — which are on a built-in or public
    # corpus' trials, since every restored upload was already asked for its own.
    _annotations.adopt_unassigned(st.session_state)


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
    st.session_state[_PLACEHOLDER_SHOWN_KEY] = True
    st.session_state[_UNAVAILABLE_KEY] = dict(
        label=label,
        reason=reason,
        action=action,
        root=root,
        size_hint=size_hint,
        download=download,
        key_prefix=key_prefix,
    )


def _stop_download(task_key: tuple) -> None:
    """UX-168: Stop on a download card — the transfer ends at its next chunk."""
    progress.cancel(task_key)


def _download_with_card(
    slot: DeltaGenerator,
    download: Callable[[str], None],
    root: str,
    *,
    label: str,
    key: str,
) -> None:
    """Run ``download(root)`` under a card with a Stop button (UX-168)."""
    task_key = ("download", loading.session_id(), key)
    with loading.card(
        slot,
        key=f"download_{key}",
        title=f"Downloading {label}",
        task_key=task_key,
        cancel=loading.Cancel("Stop download", _stop_download, args=(task_key,)),
    ):
        download(root)


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
            f"#### {ICONS['missing_bundle']} {note['label']} isn't here yet\n"
            f"{note['reason'].rstrip('.')} — **showing the bundled demo corpus** "
            f"meanwhile."
        )
        details = [f"{note['action'].rstrip('.')}{size}"]
        if note["root"]:
            # UX-184: say where a download will land, not only where it looked.
            verb = "Downloads to" if download is not None else "Looking in"
            details.append(f"{verb} `{note['root']}`")
        st.markdown("\n".join(f"- {line}" for line in details))
        if download is None:
            return
        clicked = st.button(
            "⬇ Download now",
            key=f"{note['key_prefix']}_download_main",
            type="primary",
        )
        download_slot = st.empty()
        if clicked:
            # UX-166: the download is a wait of its own. Take the dataset card
            # and the skeleton down first, or they hide this panel and its
            # spinner while describing a step that isn't what is running.
            loading.release_page()
            try:
                _download_with_card(
                    download_slot,
                    download,
                    note["root"],
                    label=note["label"],
                    key=f"{note['key_prefix']}_main",
                )
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
            action=f"Set **Data location** on the {ICONS['view_data']} Data Management page to a folder "
            "holding the files listed under **Expected files**.",
            root=root,
        )
        return False
    cfg.info(
        f"Not downloaded yet{f' ({size_hint})' if size_hint else ''}. "
        f"**Download** saves it to `{root}`."
    )
    # S2: fetching writes tens-to-hundreds of MB into a browser-supplied path. On
    # a shared deployment that's a remote visitor filling the server's disk, so
    # the corpus has to be placed by whoever runs it.
    if not local_filesystem_enabled():
        cfg.caption(
            "Downloading is disabled on this deployment — ask whoever runs it to "
            "place the corpus in the configured data location, or, on a trusted "
            "network, to start it with `SCANPATH_LOCAL_FS=1`."
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
    clicked = cfg.button("⬇ Download", key=f"{key_prefix}_download", type="primary")
    download_slot = cfg.empty()
    if clicked:
        # UX-166: as for the main area's ⬇ Download now — the dataset card must
        # not cover the download with a step that isn't what is running.
        loading.release_page()
        try:
            _download_with_card(
                download_slot, download, root, label=label, key=key_prefix
            )
        except (OSError, ValueError) as exc:
            cfg.error(f"Download failed: {exc}")
            return False
        st.rerun()
    return False


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _cached_potec_raw_frames(root: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw PoTeC frames (pre-normalization) — the full corpus.

    Returns the same shape as an upload: raw frames the normal
    auto-detect → normalize → harmonize pipeline then handles. Cached on the
    directory so re-runs (toggling viz controls) don't re-read the files. Loads
    every reader × text (75 × 12); narrow the trial pool with **Narrow by**."""
    from scanpath_studio.datasets import potec_raw_frames

    return stamp_source(potec_raw_frames(root))


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
        default_dir=_download_target(POTEC_DEFAULT_DIR),
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


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _cached_multipleye_raw_frames(
    root: str, fixation_source: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw MultiplEYE frames (pre-normalization) — the full session set.

    Same shape as an upload — the normal auto-detect → normalize → harmonize
    pipeline then handles them — cached on the selection so re-runs (toggling
    viz controls) don't re-read the files. Loads every session × stimulus;
    narrow the trial pool with **Narrow by**."""
    from scanpath_studio.datasets import multipleye_raw_frames

    return stamp_source(multipleye_raw_frames(root, fixation_source=fixation_source))


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


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _cached_onestop_raw_frames(
    root: str, regime: str, parts: tuple[str, ...], variant: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw OneStop frames (pre-normalization) for a regime + parts + variant.

    Cached on (root, regime, parts, variant) so toggling viz controls doesn't
    re-read the reports. The reports are present by the time this runs (the
    loader's Download button fetched them, or the lacclab export is local), so
    it never touches the network."""
    from scanpath_studio.datasets import onestop_raw_frames

    return stamp_source(
        onestop_raw_frames(root, regime=regime, parts=list(parts), variant=variant)
    )


def _load_onestop_regime_source(
    options_host=None, location_host=None, *, regime: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loader for one OneStop regime's dataset — every part, from OSF (DATA-63).

    Each reading regime is its own entry in the dataset table, so there are no
    source options to pick: the regime is the dataset, and it holds all of that
    regime's parts (`datasets.onestop_regime_parts`), each part its own trial.
    The reports are the public OSF release, downloaded once into one folder the
    four regimes share (the parts other than Paragraph are the same files for
    all of them). They share the bundled demo's schema, so the raw frames go
    through the normal normalization pipeline and the Column-mapping panels
    still appear. Distinct from the env-var "OneStop server bundle" source.

    ``options_host`` is unused (kept for the registry's loader signature);
    ``location_host`` is the DATA-9 data-location sub-slot.
    """
    from scanpath_studio import datasets

    loc = location_host if location_host is not None else st.container()
    parts = datasets.onestop_regime_parts(regime)
    root = _dataset_dir_input(
        loc,
        # UX-184: under the one Download folder every public corpus shares.
        default_dir=_download_target(ONESTOP_PUBLIC_DEFAULT_DIR),
        dir_help="Folder to download the OneStop reports into (cached on disk, so "
        "only the first load fetches them). The four OneStop datasets can share it.",
        structure_md=_onestop_structure_md(regime),
        key_prefix="onestop_public",
    )
    present = datasets.onestop_present(root, regime=regime, parts=parts)
    ready = _dataset_access_status(
        loc,
        root=root,
        present=present,
        download=lambda r: datasets.download_onestop(r, regime=regime, parts=parts),
        size_hint=f"{2 * len(parts)} OSF reports, hundreds of MB each",
        # Per regime: two regimes' Download buttons must not share a key.
        key_prefix=f"onestop_{regime}",
        label=ONESTOP_REGIME_CHOICES[regime],
    )
    if not ready:
        return load_sample_data()
    try:
        return _cached_onestop_raw_frames(root, regime, tuple(parts), "public")
    except (FileNotFoundError, ValueError, OSError) as exc:
        loc.error(f"Couldn't load OneStop from `{root}`: {exc}")
        return pd.DataFrame(), pd.DataFrame()


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _cached_eyegenbench_raw_frames(
    root: str, dataset: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached raw ``(words, fixations)`` for one EyeGenBench corpus.

    Cached on ``(root, dataset)`` so re-runs (toggling viz controls) don't
    re-read the Parquet files. Keyed on plain strings, not the manifest entry
    dict, so the cache survives an unrelated manifest re-read."""
    from scanpath_studio.eyegenbench import eyegenbench_raw_frames

    return stamp_source(eyegenbench_raw_frames(root, dataset=dataset))


# A malformed manifest (an entry with no `name`, a `datasets` value that isn't a
# list of objects) must degrade to a load error, not crash the app: `KeyError`
# is in here because it escapes the usual IO triple and every reader of a
# manifest reads entry keys (M7).
_MANIFEST_ERRORS = (FileNotFoundError, ValueError, OSError, KeyError)


def added_benchmark_datasets() -> tuple:
    """Manifest entries for the benchmark corpora the user added — none yet.

    DATA-55 retired automatic discovery. The app used to list every corpus in a
    bundle it found on disk (``data/EyeGenBench``, or a folder typed into a
    "set up" entry), which put data in the picker that nobody had chosen, so a
    corpus is now listed only because someone added it. The flow that adds one —
    choose a folder, scan it, pick the corpora — is DATA-56. Until it lands this
    is empty, and the per-corpus machinery it feeds (the registry entry, the
    loader, the geometry badge, the share-link slug, Compare and the code
    snippet) is reached only by tests, which replace this function.
    """
    return ()


# geometry_source values are eyegenbench_geometry.py's GEOMETRY_REAL /
# _RECONSTRUCTED / _SYNTHESIZED (that module owns the tiering; not touched
# here). Surfaced on each corpus' entry so a user can tell which they're looking
# at rather than trusting a blanket claim in the description.
_EYEGENBENCH_GEOMETRY_BADGES = {
    "real": f"{ICONS['geometry_real']} **Real** screen geometry — measured word boxes.",
    "reconstructed": f"{ICONS['geometry_reconstructed']} **Reconstructed** geometry — no measured boxes for "
    "this corpus; derived from its documented display setup.",
    "synthesized": f"{ICONS['geometry_synthesized']} **Synthesized** geometry — no measured boxes or "
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
    runs for every added corpus via `_benchmark_description` (N1). An
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
        badge = f"{ICONS['geometry_real']} **Real** screen geometry — {note}."
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
    key. The two differ: the picker shows the entry's `short`, with a (WIP)
    marker on top of it for a benchmark corpus, so *"Provo — harmonised benchmark
    corpus"* is offered as *"Provo (WIP)"*. A remedy naming a string that appears
    nowhere in the list is worse than no remedy — the reader hunts for it and
    concludes the app is broken.

    Pass ``registry`` when formatting a list of options: the added corpora can
    change at runtime, so one run must format every option against
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
    """True for a registry entry this feature owns: a prepared benchmark corpus.

    Dispatches on the entry's own `benchmark_dataset` field (set by
    `_benchmark_registry_entries`) — the same discriminator `compare_source`
    uses, and deliberately **not** on the label's text: PoTeC and OneStop each
    ship natively *and* harmonised, so a substring test on the label would sweep
    the native entries in too.
    """
    if not isinstance(spec, dict):
        return False
    return bool(spec.get("benchmark_dataset"))


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
        f"{name}, re-derived by EyeGenBench into the benchmark's common "
        f"schema — the same corpus as this app's own {name} entry, prepared for "
        "cross-corpus comparison rather than the publisher's own geometry."
        if harmonised_overlap
        else f"{name} — a public reading corpus, harmonised by EyeGenBench to "
        "one common schema."
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
    one prepared bundle, so pointing any entry somewhere else moves them all.
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
        (e for e in added_benchmark_datasets() if entry_name(e) == dataset),
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
#: The MultiplEYE entry's registry label, named because DATA-54's beta gate
#: (`constants.multipleye_enabled`) has to find it.
MULTIPLEYE_PUBLIC_CHOICE = "MultiplEYE — multilingual reading (ZH-CH sample)"

#: DATA-63 — a regime dataset's ``?source=`` token → its registry label.
ONESTOP_REGIME_TOKEN_CHOICES = {
    token: ONESTOP_REGIME_CHOICES[regime]
    for regime, token in ONESTOP_REGIME_SOURCE_TOKENS.items()
}

#: DATA-63 — what each OneStop regime's dataset says about itself.
_ONESTOP_REGIME_DESCRIPTIONS = {
    "ordinary": "native English speakers reading Guardian articles for "
    "comprehension, without seeing the question first.",
    "information_seeking": "native English speakers reading Guardian articles "
    "after seeing the question they will answer.",
    "repeated": "native English speakers reading a paragraph for the second "
    "time, without seeing the question first.",
    "information_seeking_repeated": "native English speakers reading a "
    "paragraph for the second time, after seeing the question.",
}


#: DATA-65 — each regime's figures, counted from the reports at the OSF version
#: `datasets` pins, through this app's own load (every part, as the regime's
#: dataset loads them) and `_dataset_counts`, on 2026-10-02. The corpus
#: publishes figures for the whole release only, so these are measured, not
#: quoted; the pin is what makes them stay true. A regime not listed has not been
#: counted yet and fills in once it is opened. Recount after a pipeline change
#: that moves trials, texts or screens (DATA-63 did: it made each part a screen).
_ONESTOP_REGIME_COUNTS: dict[str, dict[str, int]] = {
    "ordinary": {
        "Participants": 180,
        "Texts": 330,
        "Trials": 10078,
        "Screens": 52369,
        "Words": 2096092,
        "Fixations": 2085412,
    },
    "information_seeking": {
        "Participants": 180,
        "Texts": 330,
        "Trials": 10080,
        "Screens": 62459,
        "Words": 2191989,
        "Fixations": 1944158,
    },
    "repeated": {
        "Participants": 180,
        "Texts": 324,
        "Trials": 1944,
        "Screens": 10080,
        "Words": 399394,
        "Fixations": 296202,
    },
    "information_seeking_repeated": {
        "Participants": 180,
        "Texts": 324,
        "Trials": 1944,
        "Screens": 12023,
        "Words": 416956,
        "Fixations": 260190,
    },
}


def _onestop_regime_entry(regime: str) -> dict:
    """The registry entry for one OneStop regime's dataset (DATA-63).

    ``published_counts`` are this regime's own, measured (DATA-65,
    :data:`_ONESTOP_REGIME_COUNTS`) — never the whole release's, which no single
    regime holds.
    """
    label = ONESTOP_REGIME_LABELS[regime]
    counts = _ONESTOP_REGIME_COUNTS.get(regime)
    extra = (
        dict(
            published_counts=counts,
            published_counts_source=(
                "Counted from the OSF reports at the version this release pins, "
                "by this app's own load of every part of the regime."
            ),
        )
        if counts
        else {}
    )
    return dict(
        **extra,
        loader=partial(_load_onestop_regime_source, regime=regime),
        # BUG-113: the dataset table's Status, for a row that is not open.
        files_present=partial(_onestop_files_present, regime),
        downloadable=True,
        # OneStop presentation monitor (full-screen px coords). Sourced in
        # `eyegenbench_geometry.DISPLAY_SPECS["onestop"]` — Berzak et al. 2025,
        # Sci Data 12:1995, Methods → Apparatus, which states the Dell U2715H
        # at 2560 px × 1440 px over a 597 mm × 336 mm display area.
        monitor=(2560, 1440),
        # Distinct per regime: `short` is the stable identifier a Share link's
        # corpus slug and the code snippet are derived from.
        short=f"OneStop · {label}",
        onestop_regime=regime,
        language="English (L1)",
        size=f"{label} · every trial part, from the OSF release",
        description=f"OneStop Eye Movements, {label.lower()} — "
        f"{_ONESTOP_REGIME_DESCRIPTIONS[regime]}",
        link="https://github.com/lacclab/OneStop-Eye-Movements",
    )


PUBLIC_DATASET_REGISTRY: dict = {
    "PoTeC — Potsdam Textbook Corpus": dict(
        loader=_load_potec_source,
        files_present=_potec_files_present,  # BUG-113
        downloadable=True,
        # The schema `load_potec` uses, so the app's Trial ID is the headless
        # one: reader + text, not the text name every reader shares.
        declared_schemas=(POTEC_WORD_SCHEMA, POTEC_FIX_SCHEMA),
        monitor=(1680, 1050),  # DELL P2210
        short="PoTeC",
        language="German",
        size="75 readers · 12 texts",
        description="Potsdam Textbook Corpus — German readers, experts and "
        "novices, reading biology and physics textbook passages.",
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
            "PoTeC's own README for readers, texts and trials. Words and "
            "fixations were measured from the released corpus; the fixation "
            "total agrees with the harmonised bundle's manifest to the row."
        ),
        # Word boxes come from the corpus' own `.ias` character files, but the
        # release discards the recorded screen (x, y) — `datasets._potec_fixations`
        # places each fixation at the centre of the character it names. UX-177:
        # the one provenance fact that changes how a figure is read, so it is
        # the one said on the Data page.
        reading_note="Fixation positions are reconstructed, not recorded: "
        "PoTeC's release keeps no screen coordinates, so each fixation is drawn "
        "at the centre of the character it landed on.",
    ),
    MULTIPLEYE_PUBLIC_CHOICE: dict(
        loader=_load_multipleye_source,
        # BUG-113. No download: MultiplEYE is read from a local session set.
        files_present=_multipleye_files_present,
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
    ),
    # DATA-63: one dataset per reading regime, each holding every part.
    **{
        ONESTOP_REGIME_CHOICES[regime]: _onestop_regime_entry(regime)
        for regime in ONESTOP_REGIME_CHOICES
    },
}


#: The same presentation metadata for the sources that are **not** registry
#: entries — the packaged demo, the synthetic trial, the authoring canvas — so
#: the Data page can answer the same questions about every dataset.
#: Uploads are absent on purpose: nothing here knows anything about them that
#: their own row does not already show.
_BUILTIN_DATASET_ABOUT: dict[str, dict] = {
    DEMO_CHOICE: dict(
        language="English (L1)",
        # Regenerated by `python -m scanpath_studio.update_sample_data`.
        description="A small part of OneStop Eye Movements — native English "
        "speakers reading Guardian articles — bundled so the app opens with "
        "real data.",
        link="https://github.com/lacclab/OneStop-Eye-Movements",
        # DATA-36: this corpus ships *inside* the package, so its figures are
        # checked against the files themselves — the DATA-36 tests recount
        # them, so regenerating the subset fails a test rather than quietly
        # leaving a stale number in the table.
        published_counts={
            "Participants": 2,
            "Texts": 12,
            "Trials": 24,
            "Words": 2614,
            "Fixations": 3209,
            "Gaze points": 2233,
        },
        published_counts_source=(
            "Counted from the files bundled with this release of the package."
        ),
        # UX-177: OneStop publishes no raw samples, so the raw-gaze layer is
        # made up — which changes how that layer is read, so it is said.
        # VIZ-50: the flag says it at the figure too, and in its exports
        # (`synthesized_raw_gaze_note`), in this same sentence.
        reading_note="The raw-gaze samples are synthesized: OneStop publishes "
        "no raw gaze.",
        raw_gaze_synthesized=True,
    ),
    ONESTOP_CHOICE: dict(
        language="English (L1)",
        description="OneStop Eye Movements — native English speakers reading "
        "Guardian articles — read from the lab export at `$ONESTOP_DATA_DIR`.",
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
            "can hold more — the L2 cohort is not in the public release — so "
            "treat this as a floor."
        ),
    ),
    MANUAL_SAMPLE_CHOICE: dict(
        language="English",
        description="A scanpath drawn by hand over a short English text, "
        "yours to edit.",
    ),
    SYNTHETIC_CHOICE: dict(
        language="English",
        description="A hand-built six-word English trial whose every reading "
        "measure is known, for checking what a measure or plot option does.",
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
    ),
    AUTHOR_CHOICE: dict(
        description="Type a text and place fixations on it yourself, for "
        "figures that illustrate a pattern rather than report a recording.",
    ),
}


def dataset_about(token: str, registry: dict | None = None) -> dict:
    """What the dataset table knows about one row beyond its counts.

    One lookup for both halves of the catalogue — a public corpus' registry
    entry and the packaged sources' table above — so neither the table's row nor
    the open dataset's section has to care which kind of dataset it is.
    ``language`` feeds the table's filter; ``description``, ``link`` and
    ``reading_note`` are the lines under *What's in the dataset* (UX-177). Returns ``{}`` for an upload, which is the
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
                "reading_note",
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


def synthesized_raw_gaze_note(token: str | None) -> str:
    """The catalogue's sentence for a dataset whose raw gaze is made up, else ``""``.

    VIZ-50: the 🗂️ Data page says the demo's samples are synthesized, but the
    🔵 Raw gaze layer is switched on from Scanpath, where that page is out of
    sight — so the plot repeats the note while the layer is drawn, and the
    Share → File settings and the bundle's ``plot_config.json`` record it. One
    flag (``raw_gaze_synthesized``) and one sentence (``reading_note``), read
    from the packaged sources' table directly: no public corpus or upload sets
    it, so the registry is never built to answer.
    """
    about = _BUILTIN_DATASET_ABOUT.get(str(token or "")) or {}
    if not about.get("raw_gaze_synthesized"):
        return ""
    return str(about.get("reading_note") or "")


def _benchmark_registry_entries() -> dict:
    """One registry entry per benchmark corpus the user added (R36, DATA-55).

    Built from those corpora's manifest entries (`added_benchmark_datasets`),
    so it varies at runtime — which is why the registry as a whole had to become
    a function. Each entry has the same shape as the static built-ins above
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
    for entry in added_benchmark_datasets():
        # `entry_name` owns the "a row with no usable name is skipped" rule (N5).
        if not (name := entry_name(entry)):
            continue
        short = _benchmark_short_name(name)
        spec = dict(
            loader=partial(_load_benchmark_source, dataset=name),
            # BUG-113. No download: a bundle is prepared by a script.
            files_present=partial(_benchmark_files_present, name),
            short=short,
            language=language_display(entry.get("language")),
            size=_benchmark_size_caption(entry),
            description=_benchmark_description(entry, harmonised_overlap=short != name),
            # R34's badge, resolved once here rather than only inside the loader,
            # so the Data page can show it without re-reading the manifest.
            reading_note=geometry_badge(entry),
            link="https://github.com/EyeBench/EyeGenBench",
            # DATA-36: the manifest already counts each corpus, so a prepared
            # row arrives with its figures — the same numbers `size` renders as
            # a caption, one column each.
            published_counts=benchmark_published_counts(entry),
            published_counts_source=(
                "The prepared bundle's own manifest. Texts counts *distinct* "
                "texts, so a corpus with repeated readings publishes fewer than "
                "the app counts reading instances."
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
    """Every public corpus on offer: the static built-ins ∪ the added corpora.

    `PUBLIC_DATASET_REGISTRY` stays the literal home of the three built-ins, whose
    entries are fixed at import time. The benchmark corpora a user adds can't be,
    so they are composed in here and every consumer calls this instead of reading
    the dict. Nothing is discovered: a corpus is here only because someone added
    it (DATA-55; the flow that adds one is DATA-56).

    DATA-54 and DATA-55 hold MultiplEYE and the harmonised benchmark corpora back
    for the beta unless ``SCANPATH_EXPERIMENTAL`` is on. Gating here, the one
    place every consumer reads, is what hides them from the picker, the 🗂️ Data
    page, Compare's second dataset and share links at once.
    """
    registry = dict(PUBLIC_DATASET_REGISTRY)
    if not multipleye_enabled():
        registry.pop(MULTIPLEYE_PUBLIC_CHOICE, None)
    if benchmark_corpora_enabled():
        registry.update(_benchmark_registry_entries())
    return registry


def _load_public_dataset(
    description_host=None, options_host=None, location_host=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dispatch for a "Public datasets" source.

    The corpus is chosen in the flat source picker (DATA-9) and rides
    ``public_dataset_choice``. The selected corpus' compact language · size
    caption and home link render into ``description_host``, under the editable
    description (UX-174 r2); the loader's source options + data-location controls
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


#: The recording-setup values a fresh session pins before anything declares
#: otherwise (`seed_canvas_state`'s `defaults`). The canvas is absent because it
#: is the source's own (`resolve_source_monitor`), and the DPI because it is
#: derived from the canvas and the physical width. EXP-19's share link reads the
#: same table to leave a setting off while it still equals it
#: (`url_state._link_defaults`).
SETUP_DEFAULTS = {
    "global_monitor_width_mm": 597.0,
    "global_viewing_distance_mm": 800.0,
    "global_base_font_size": 16,
    "global_stimulus_font_pt": 12.0,
    "global_use_stimulus_font_pt": False,
}

#: BUG-50 — the font controls a declared stimulus typeface overwrites, and where
#: `seed_canvas_state` parks their pre-snap values so leaving that corpus can put
#: them back. All three are wire format (share link + saved config), which is why
#: leaking one across a source switch outlives the session that caused it.
_FONT_SNAP_KEYS = (
    "global_base_font_size",
    "global_font_family",
    "global_scale_text_to_boxes",
)
_FONT_SNAP_RESTORE_KEY = "_font_snap_restore"

#: VIZ-45 — the raw-gaze layer's per-dataset default follows the font snap's
#: shape (BUG-50): `controls.RAW_GAZE_SEEDED_FOR_KEY` records the dataset it was
#: last decided for, and `controls.RAW_GAZE_SNAP_RESTORE_KEY` the value it
#: overwrote, so leaving that dataset can put it back. Both are recovery-cache
#: session keys (`persistence._SESSION_KEYS`), so a relaunch onto the same
#: dataset does not decide again over the user's own choice.
_RAW_GAZE_LAYER_KEY = "global_show_raw_gaze"
#: `RAW_GAZE_LINK_FOR_KEY` once the link's visit is over — not None, so the
#: same link, still on the URL, cannot claim another dataset.
_RAW_GAZE_LINK_SPENT = "\x00spent"


def _narrowed_raw_gaze(
    raw_gaze: pd.DataFrame,
    *,
    participants,
    metadata,
    ranges,
    trial_keys,
    drop_unknown=None,
) -> pd.DataFrame:
    """The samples table narrowed by the trial filters that apply to it (VIZ-45).

    The participant filter always, the condition filters only when the caller
    passes them (a raw-gaze-only dataset), and the trial-metadata keys. With no
    filter set it is ``raw_gaze`` itself; otherwise it is built once per filter
    change in a `frame_cache` and the same object is handed back on every rerun
    after that, rather than re-masking every sample each time."""
    if raw_gaze is None or raw_gaze.empty:
        return raw_gaze
    if participants is None and not metadata and not ranges and trial_keys is None:
        return raw_gaze

    def _build() -> pd.DataFrame:
        _, narrowed = filter_trials(
            _EMPTY_WORDS,
            raw_gaze,
            participants=participants,
            metadata=metadata,
            ranges=ranges,
            drop_unknown=drop_unknown,
        )
        if trial_keys is not None:
            narrowed = filter_frame_to_keys(narrowed, trial_keys)
        return narrowed

    key = (
        frame_fingerprint(raw_gaze),
        hashable_key(participants),
        hashable_key(metadata or {}),
        hashable_key(ranges or {}),
        hashable_key(trial_keys),
        hashable_key(tuple(drop_unknown or ())),
    )
    return frame_cache("raw_gaze_narrowed", key, _build)


#: The words frame `filter_trials` is handed beside the samples — built once.
_EMPTY_WORDS = empty_words_frame()


def seed_raw_gaze_default(
    session,
    source_key: tuple,
    *,
    samples_only: bool,
    link_names_layer: Callable[[], bool] | bool = False,
) -> None:
    """Turn the 🔵 Raw gaze layer on for a dataset whose only gaze is samples.

    VIZ-45: a dataset with raw gaze and no fixations opened as a blank plot,
    because the layer defaults off — the only data it had was hidden. So the
    default is **the dataset's**, not the app's: opening a dataset that has raw
    gaze and no fixations (``samples_only``, decided on the unfiltered frames)
    turns the layer on; opening any other dataset leaves it where it was.

    It is decided **once per dataset** (``source_key``, `seed_canvas_state`'s
    key), the way the canvas and font snaps are, which is what lets an explicit
    choice win: switching the layer off on that dataset sticks for as long as it
    stays open, because nothing decides again until the dataset changes. The
    value it overwrote is kept and put back on the way out, so the fixation
    dataset opened next keeps whatever the user had there rather than inheriting
    the raw-gaze one's.

    A share link that named the layer (``link_names_layer``, a callable so it
    is asked only when a decision is due) is the sender's explicit choice **for
    the dataset it was opened on** — the first one decided while the link is on
    the URL (`constants.RAW_GAZE_LINK_FOR_KEY`). There the link's value stands:
    nothing is stashed, and a stash an earlier visit left (the recovery cache
    keeps it) is dropped rather than written back over the link. Another
    raw-gaze-only dataset the user opens afterwards gets its own default.

    A built-in design preset or *Reset* forgets the decision
    (`controls._forget_raw_gaze_default`), so they come back to the dataset's
    default rather than the factory one — a raw-gaze-only dataset with the layer
    off shows no gaze whatever the preset's name. A saved design does not: it is
    the user's own record, its raw-gaze switch included.
    """
    token = "\x1f".join(str(part) for part in source_key)
    if session.get(RAW_GAZE_SEEDED_FOR_KEY) == token:
        return
    link_for = session.get(RAW_GAZE_LINK_FOR_KEY)
    if link_for is None and (
        link_names_layer() if callable(link_names_layer) else link_names_layer
    ):
        link_for = session[RAW_GAZE_LINK_FOR_KEY] = token
    elif link_for is not None and link_for != token:
        # A link is one visit: the first other dataset decided spends it, so
        # coming back to the linked dataset later is an ordinary visit — its
        # value would otherwise drop the stash the dataset in between made.
        link_for = session[RAW_GAZE_LINK_FOR_KEY] = _RAW_GAZE_LINK_SPENT
    from_link = link_for == token
    if from_link:
        # The link's value overwrote nothing, and a stash from before the link
        # must not overwrite it either.
        session.pop(RAW_GAZE_SNAP_RESTORE_KEY, None)
    elif samples_only:
        if RAW_GAZE_SNAP_RESTORE_KEY not in session:
            # Stashed on the first of a run of raw-gaze datasets only, so
            # raw-gaze → raw-gaze → fixations restores the pre-raw-gaze value.
            # `None` = absent: leaving restores the factory default.
            session[RAW_GAZE_SNAP_RESTORE_KEY] = {
                "value": session.get(_RAW_GAZE_LAYER_KEY)
            }
        session[_RAW_GAZE_LAYER_KEY] = True
    else:
        stashed = session.get(RAW_GAZE_SNAP_RESTORE_KEY)
        if isinstance(stashed, dict):
            session.pop(RAW_GAZE_SNAP_RESTORE_KEY, None)
            prior = stashed.get("value")
            if prior is None:
                session.pop(_RAW_GAZE_LAYER_KEY, None)
            else:
                session[_RAW_GAZE_LAYER_KEY] = bool(prior)
    session[RAW_GAZE_SEEDED_FOR_KEY] = token


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
def _cached_words_join_nothing(
    _words: pd.DataFrame, _fixations: pd.DataFrame, cache_key
) -> bool:
    """Whether a loaded words table shares no (participant, trial) with the
    fixations (BUG-32) — memoized, since it dedups both whole frames."""
    if _fixations.empty:
        return False
    return not trial_keys(_words) & trial_keys(_fixations)


#: BUG-32 — said once per page, in the notices strip, while it holds.
WORDS_JOIN_NOTHING_WARNING = (
    f"{ICONS['warning']} **No fixation has word boxes.** A words / AOI table was loaded, but none "
    "of its participant + trial pairs is in the fixations, so every trial draws "
    "without its text or its word-level measures. The usual cause is a **Trial "
    "ID** or **Participant ID** mapping that names different trials in the two "
    "tables — for instance one carried over from another dataset with the same "
    f"columns. Check it on {ICONS['view_data']} **Data Management → Column mapping**, or start again from "
    "**↩️ Reset to the auto-detected mapping**."
)


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
    # UX-166: only a miss gets here — the report is what shows the gated
    # dataset card for the census's seconds.
    progress.report()
    return diagnose_trial_identity(_words, _fixations, sample_trials=sample_trials)


# UX-166: the dataset card lists this step.
@st.cache_data(show_spinner=False)
def _cached_multipleye_server_bundle(
    participant: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    progress.report()  # a miss: real work, so the gated dataset card may show
    return stamp_source(load_multipleye_server_bundle(participant))


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


#: How the last normalized pair's stimulus-level AOI table attached to its
#: readings (a ``data.StimulusJoin``, or ``None``), written by `_normalize_pair`
#: for the add-dataset wizard (DATA-49). Scratch state, not wire format.
STIMULUS_JOIN_KEY = "_stimulus_join"

#: DATA-66: the columns the last `_normalize_pair` changed the values of
#: (``data.Rewrite``s), which `_stash_active_mapping` marks converted in the
#: column-name map. Scratch state, cleared with the map each load.
HARMONIZE_REWRITES_KEY = "_harmonize_rewrites"


def _normalize_pair_uncached(
    _words_df: pd.DataFrame,
    _word_schema: dict | None,
    _fixations_df: pd.DataFrame,
    _fix_schema: dict | None,
    cache_key,
    _keep_words: set | None = None,
    _keep_fix: set | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, StimulusJoin | None, tuple]:
    """Pure normalize + harmonize, cached on a cheap fingerprint of the inputs.

    Also returns how a stimulus-level AOI table attached to the readings
    (the one ``data.harmonize_frames_with_join`` made, DATA-49) — ``None`` for a per-reader one —
    which ``_normalize_pair`` publishes for the add-dataset wizard to state.

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
        # UX-166 (T5-3): three reportable parts, so a cancel checkpoint exists
        # partway through instead of only at the very end — on a real corpus
        # this stage alone is the ~20 s wait the spinner above describes.
        progress.report(0, 3, detail="words")
        words_norm = (
            normalize_words(_words_df, _word_schema, keep_columns=_keep_words)
            if _word_schema is not None
            else empty_words_frame()
        )
        progress.report(1, 3, detail="fixations")
        fixations_norm = (
            normalize_fixations(_fixations_df, _fix_schema, keep_columns=_keep_fix)
            if _fix_schema is not None
            else empty_fixations_frame()
        )
        progress.report(2, 3, detail="cross-checks")
        # The join the fixups actually made, after BUG-59's zero padding — never
        # a plan of the frames before it, which can disagree. DATA-66: and the
        # columns whose values they changed, for the column-name map.
        words_norm, fixations_norm, join, rewrites = harmonize_frames_reporting(
            words_norm, fixations_norm
        )
        progress.report(3, 3)
        return words_norm, fixations_norm, join, rewrites


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

    The heavy normalization is ``_normalize_pair_uncached``, cached through
    ``frame_cache`` on a fingerprint key (PERF-6) so it doesn't re-run on every
    rerun (e.g. selecting a different trial); only the lightweight session-state
    bookkeeping below runs each time.
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
    # whether that is expected. UX-166 moved it *outside* the cache: a spinner's
    # exit is a yield point, and inside `build` an abandoned run raised there
    # and threw the finished normalization away. `st.spinner` shows only after
    # 0.5 s, so a cache hit still never flashes it, and `loading.spinner` stays
    # silent under the dataset card, which lists normalization as a step.
    with loading.spinner(
        f"Normalizing {len(words_df):,} word rows and {len(fixations_df):,} fixations…"
    ):
        words_norm, fixations_norm, join, rewrites = frame_cache(
            "normalized_pair",
            cache_key,
            lambda: _normalize_pair_uncached(
                words_df,
                word_schema,
                fixations_df,
                fix_schema,
                cache_key,
                _keep_words=keep_words,
                _keep_fix=keep_fix,
            ),
            # PERF-18: the dataset before this one stays normalized, so
            # switching back to it is instant.
            keep=2,
        )
    # DATA-49: which key a stimulus-level AOI table joined through, for the
    # add-dataset wizard to say — bookkeeping like `_composite_trial_columns`
    # above, written on a cache hit too so it always describes this pair.
    st.session_state[STIMULUS_JOIN_KEY] = join
    st.session_state[HARMONIZE_REWRITES_KEY] = rewrites
    return words_norm, fixations_norm


def _reset_active_mapping() -> None:
    """Clear the stashed column mapping at the start of each data load, so a new
    source doesn't inherit the previous one's mapping in the Data Inspection tab."""
    st.session_state["_active_column_mapping"] = {}
    st.session_state[ACTIVE_COLUMN_NAMES_KEY] = {}
    st.session_state.pop(HARMONIZE_REWRITES_KEY, None)


def _stash_active_mapping(
    table: str,
    schema: dict | None,
    columns: Iterable[str] | None = None,
    *,
    keep_columns: Iterable[str] | None = None,
    names: ColumnNames | None = None,
) -> None:
    """Record the schema (field → source column) actually used for ``table`` so
    ``tabs.render_data_inspection_tab`` can show how columns were mapped. ``table``
    is one of ``"words" / "fixations" / "raw_gaze"``.

    DATA-66: also the column-name map the schema implies — ``names`` when the
    caller already holds one (a stored upload), else built from the raw table's
    ``columns``. Neither: the table's map is dropped, never left stale."""
    mapping = st.session_state.setdefault("_active_column_mapping", {})
    mapping[table] = dict(schema) if schema else None
    stash = st.session_state.setdefault(ACTIVE_COLUMN_NAMES_KEY, {})
    if names is None and schema and columns is not None:
        names = from_schema(
            table, schema, columns, keep_columns=keep_columns
        ).with_rewrites(table, st.session_state.get(HARMONIZE_REWRITES_KEY))
    if names is None:
        stash.pop(table, None)
    else:
        stash[table] = names.to_payload()


def active_column_names(table: str) -> ColumnNames:
    """The open dataset's column-name map for ``table`` (DATA-66)."""
    return active_names(st.session_state, table)


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


#: A built-in source (the demo, a public corpus) maps its columns with the
#: `col_map_*` panels themselves, which apply as they change. While ✏️ Edit
#: dataset is open they are a draft instead, like an upload's editor: the
#: dataset keeps the mapping it had when the editor opened (held here, with the
#: `col_map_*` keys that produced it) until ✅ Save changes adopts the draft, and
#: ✕ Cancel puts the keys back.
BUILTIN_MAPPING_HELD_KEY = "_builtin_mapping_held"
#: The panels' current picks, ``{"words": schema, "fixations": schema}``,
#: written by `prepare_data` on every run that draws them.
BUILTIN_MAPPING_PENDING_KEY = "_builtin_mapping_pending"
#: Set by ✅ Save changes for the success line on the screen it returns to.
BUILTIN_MAPPING_SAVED_KEY = "_builtin_mapping_saved"
#: ✕ Cancel's restore, parked for the next run to apply before the panels draw:
#: the Leave confirmation is a dialog, whose click runs inside the dialog's own
#: rerun rather than ahead of the page's widgets.
BUILTIN_MAPPING_RESTORE_KEY = "_builtin_mapping_restore"
#: The panels a built-in source draws (`prepare_data`). Only their field
#: values are held: not the per-cell confirm buttons (`*_cell_confirm`, whose
#: value Streamlit refuses to have set), the add wizard's `*_upload` files or
#: its stashed `*_header` — the scaffolding `tabs._EDITOR_KEY_NOISE` names.
_BUILTIN_PANEL_PREFIXES = ("col_map_words_", "col_map_fix_")


def _is_builtin_panel_key(key) -> bool:
    return (
        isinstance(key, str)
        and key.startswith(_BUILTIN_PANEL_PREFIXES)
        and not any(noise in key for noise in _EDITOR_KEY_NOISE)
    )


def _mapping_signature(schemas: dict | None) -> str:
    """A comparable rendering of a ``{"words", "fixations"}`` mapping — lists
    (a composite Trial ID) come back from the widgets as new objects."""
    return json.dumps(schemas or {}, sort_keys=True, default=str)


def held_builtin_mapping(source_key) -> dict | None:
    """The mapping a built-in source keeps while its editor is open, or None."""
    held = st.session_state.get(BUILTIN_MAPPING_HELD_KEY)
    if not held or held.get("source") != source_key:
        return None
    return held.get("schemas")


def hold_builtin_mapping(source_key) -> None:
    """Record the mapping this run applied, and the keys behind it, as what an
    editor opened on the next run starts from and what its ✕ Cancel restores."""
    st.session_state[BUILTIN_MAPPING_HELD_KEY] = {
        "source": source_key,
        "schemas": copy.deepcopy(st.session_state.get(BUILTIN_MAPPING_PENDING_KEY)),
        "keys": {
            key: copy.deepcopy(value)
            for key, value in st.session_state.items()
            if _is_builtin_panel_key(key)
        },
    }


def builtin_mapping_is_dirty(source_key) -> bool:
    """Whether the open editor's mapping panels differ from the held mapping."""
    held = held_builtin_mapping(source_key)
    if held is None:
        return False
    return _mapping_signature(
        st.session_state.get(BUILTIN_MAPPING_PENDING_KEY)
    ) != _mapping_signature(held)


def _discard_builtin_mapping_edit() -> None:
    """Ask the next run to put the panels back as they were when the editor
    opened (`restore_builtin_mapping`)."""
    held = st.session_state.pop(BUILTIN_MAPPING_HELD_KEY, None)
    if held:
        st.session_state[BUILTIN_MAPPING_RESTORE_KEY] = held


def restore_builtin_mapping(source_key) -> None:
    """Apply a parked ✕ Cancel to ``source_key``'s panels, before they draw.

    A restore parked for another source is dropped: its keys describe columns
    this source does not have."""
    held = st.session_state.pop(BUILTIN_MAPPING_RESTORE_KEY, None)
    if not held or held.get("source") != source_key:
        return
    saved = held.get("keys") or {}
    for key in [k for k in list(st.session_state) if _is_builtin_panel_key(k)]:
        if key not in saved:
            del st.session_state[key]
    for key, value in saved.items():
        st.session_state[key] = value


def _save_builtin_mapping(mapping: bool = True) -> None:
    """✅ Save changes for a built-in source: adopt the draft mapping, name,
    description and metadata tables.

    A draft that leaves a required field empty is refused here, with the
    reasons shown above the button, rather than applied and then failing.
    ``mapping=False`` is a source with no mapping panels to adopt."""
    pending = (
        (st.session_state.get(BUILTIN_MAPPING_PENDING_KEY) or {}) if mapping else {}
    )
    problems: dict = {}
    for table_key, validate in (
        ("words", validate_word_schema),
        ("fixations", validate_fix_schema),
    ):
        schema = pending.get(table_key)
        if schema is not None and (found := validate(schema)):
            problems[table_key] = found
    if problems:
        st.session_state["_remap_problems"] = problems
        return
    # Dropped first, so closing the editor does not restore the held keys.
    st.session_state.pop(BUILTIN_MAPPING_HELD_KEY, None)
    # …and the Recording setup, before closing sweeps the form's state away.
    commit_builtin_setup()
    saved = str(st.session_state.get("data_source_choice") or "")
    commit_editor_staging(saved)
    _close_dataset_editor()
    st.session_state[BUILTIN_MAPPING_SAVED_KEY] = saved


def _render_builtin_editor_footer(host, *, mapping: bool = True) -> None:
    """✅ Save changes at the foot of a built-in source's ✏️ Edit dataset screen.

    `tabs.render_dataset_editor_footer`'s row, for a dataset with no stored
    entry: the same divider, the same blockers, the button in the same column.
    There is no ⬇️ Save setup beside it — the corpus' own loader is the setup.
    ``mapping=False``: a source with no mapping panels, whose Save holds the
    name, description and metadata tables.
    """
    from scanpath_studio.wizard import _FOOTER_ROW_W

    box = host.container()
    box.container(key="wizard_footer_divider_edit").divider()
    for table_key, messages in (st.session_state.get("_remap_problems") or {}).items():
        label = _TABLE_LABELS.get(table_key, table_key)
        for message in messages:
            box.error(f"**{label}** — {message}", icon=ICONS["error"])
    row = box.container(key="wizard_footer_row_edit")
    _setup_col, apply_col, _rest = row.columns(
        _FOOTER_ROW_W, gap="small", vertical_alignment="center"
    )
    apply_col.button(
        f"{ICONS['confirm']} Save changes",
        type="primary",
        key="builtin_mapping_save",
        on_click=_save_builtin_mapping,
        args=(mapping,),
        width="stretch",
        help="Save the name, description, column mapping, recording setup and "
        "metadata tables above."
        if mapping
        else "Save the name, description and metadata tables above.",
    )


#: Label + tooltip of the off-page signpost's "known-good state" button.
DEMO_RESET_LABEL = f"{ICONS['demo']} Load the bundled demo"
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

    A native corpus whose identity is a published contract declares its schema
    on its registry entry (``declared_schemas``): PoTeC's Trial ID is the reader
    *and* the text, which no column name says and detection would guess as the
    text alone.
    """
    if data_choice != PUBLIC_DATASETS_CHOICE:
        return None, None
    # The corpus isn't here and the demo stands in for it: its frames are the
    # demo's, which the corpus' schema does not describe.
    if st.session_state.get(_PLACEHOLDER_SHOWN_KEY):
        return None, None
    spec = public_dataset_registry().get(
        st.session_state.get("public_dataset_choice", "")
    )
    if spec and spec.get("declared_schemas"):
        word_schema, fix_schema = spec["declared_schemas"]
        return dict(word_schema), dict(fix_schema)
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
    mapping_dataset: object = None,
    held_schemas: dict | None = None,
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

    ``mapping_dataset`` identifies the source these tables came from, so a
    column pick made for another dataset — the add-dataset wizard shares these
    ``col_map_*`` keys — is dropped rather than inherited because the headers
    happen to match (BUG-32; ``controls.forget_mapping_for_other_table``).

    ``held_schemas`` (``{"words": …, "fixations": …}``) is the mapping the
    dataset keeps while ✏️ Edit dataset is open: the panels still render and
    their picks are published as the draft (``BUILTIN_MAPPING_PENDING_KEY``),
    but the frames are normalized under the held mapping until ✅ Save changes.
    """
    has_words = not words_df.empty
    has_fixations = not fixations_df.empty
    word_schema = None
    fix_schema = None
    problems: list = []
    pending: dict = {}

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
                dataset=mapping_dataset,
            )
            pending["words"] = word_schema
            if held_schemas and held_schemas.get("words") is not None:
                word_schema = held_schemas["words"]
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
                dataset=mapping_dataset,
            )
            pending["fixations"] = fix_schema
            if held_schemas and held_schemas.get("fixations") is not None:
                fix_schema = held_schemas["fixations"]
        else:
            fix_schema = fix_proposed
        fix_problems = validate_fix_schema(fix_schema)
        if fix_problems:
            problems.append("Fixations: " + "; ".join(fix_problems))

    if allow_override:
        st.session_state[BUILTIN_MAPPING_PENDING_KEY] = pending

    if problems:
        # Mapping not ready — let the caller surface the raw data instead of
        # plotting. Clear any stale composite-trial state so the picker doesn't
        # reference columns from a previous, valid dataset.
        st.session_state["_composite_trial_columns"] = None
        return empty_words_frame(), empty_fixations_frame(), problems

    # Record the mapping actually used so the Data Inspection tab can show it.
    _stash_active_mapping("words", word_schema if has_words else None, words_df.columns)
    _stash_active_mapping(
        "fixations", fix_schema if has_fixations else None, fixations_df.columns
    )

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
            st.error(problem, icon=ICONS["error"])
        st.caption(
            "Change the field it names in **2 · Data tables & column mapping** above, "
            "or start again from what auto-detection proposes."
        )
        st.button(
            f"{ICONS['undo']} Reset to the auto-detected mapping",
            key="reset_column_mapping",
            on_click=reset_column_mapping,
        )
    else:
        st.warning(
            "**Finish the column mapping to draw scanpaths.** Map the missing "
            "field(s) in **2 · Data tables & column mapping** above — the raw data is "
            "shown below to help you choose. "
            "Still needed:\n\n" + "\n".join(f"- {p}" for p in problems)
        )
    if (raw_words_df is None or raw_words_df.empty) and (
        raw_fixations_df is None or raw_fixations_df.empty
    ):
        st.info("No data loaded yet.")
    _render_raw_preview("Words / IA", raw_words_df)
    _render_raw_preview("Fixations", raw_fixations_df)


def _render_dataset_load_failure(name: str, problems: list) -> None:
    """BUG-100: say on the Data overview that the dataset didn't load, and why.

    :func:`_render_unmapped_view` draws into the ✏️ Edit dataset screen, which
    is hidden until it is opened — so a corpus the pipeline rejected (OneStop ·
    Ordinary reading's orphan screens, before DATA-63) left the overview with a
    "Not loaded" row and no other trace. This is the overview's half: the
    dataset's name, the reason, and the two ways on — the editor that can fix
    the mapping, or back to the demo.
    """
    rejected = [p for p in problems if p.startswith(MAPPING_FAILURE_LEAD)]
    with st.container(border=True, key="dataset_load_failure_panel"):
        if rejected:
            for problem in rejected:
                reason = problem.removeprefix(MAPPING_FAILURE_LEAD).lstrip(": ")
                st.error(
                    f"**{name} didn't load.** Normalizing its tables failed: {reason}",
                    icon=ICONS["error"],
                )
        else:
            st.warning(
                f"**{name} isn't loaded yet** — its column mapping is "
                "incomplete:\n\n" + "\n".join(f"- {p}" for p in problems)
            )
        edit, demo = st.columns(2)
        edit.button(
            f"{ICONS['edit']} Edit dataset",
            key="dataset_load_failure_edit",
            on_click=_open_mapping_editor,
            type="primary",
            width="stretch",
        )
        demo.button(
            DEMO_RESET_LABEL,
            key="dataset_load_failure_demo",
            on_click=load_bundled_demo,
            width="stretch",
            help=DEMO_RESET_HELP,
        )


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
        f"Finish it on the {ICONS['view_data']} **Data Management** page — or start over from the demo.",
        icon=ICONS["view_data"],
    )
    finish, demo = st.columns(2)
    finish.button(
        f"{ICONS['view_data']} Go to Data Management",
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
# archives wrapping any of the others (e.g. ``data.csv.zip``). ``txt`` is the
# tab-separated report many exporters write (DATA-41); a text file's delimiter
# is read off its header line, and an ``.xls`` that is really text (EyeLink
# Data Viewer's "Excel" export) is read as text (BUG-55).
_UPLOAD_TYPES = list(UPLOAD_FILE_TYPES)


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


@st.cache_data(show_spinner="Reading uploaded data…", show_time=True)
def _read_uploaded_table_cached(
    _uploaded, file_key, kind=None, chosen=(), text_column=None, identity=()
) -> pd.DataFrame:
    try:
        _uploaded.seek(0)
    except Exception:
        pass
    if kind is None:
        return stamp_source(read_table(_uploaded))
    # PERF-6: parse only the columns the mapping, the registry and the user's
    # own picks need. `kind` and `chosen` are part of the cache key, so naming
    # a new column simply re-reads the file under the new plan.
    header = read_table_columns(_uploaded)
    plan = upload_read_plan(
        header, kind, chosen=chosen, text_column=text_column, identity=identity
    )
    return stamp_source(read_table(_uploaded, plan=plan))


@st.cache_data(show_spinner="Reading uploaded data…", show_time=True)
def _read_uploaded_tables_cached(
    _uploaded_list, file_keys, kind=None, chosen=(), text_column=None, identity=()
) -> pd.DataFrame:
    for f in _uploaded_list:
        try:
            f.seek(0)
        except Exception:
            pass
    plan_for = None
    if kind is not None:

        def plan_for(header):
            return upload_read_plan(
                header, kind, chosen=chosen, text_column=text_column, identity=identity
            )

    return stamp_source(read_tables(list(_uploaded_list), plan_for=plan_for))


#: Session keys naming a source column the user has picked: every mapping
#: dropdown (``col_map_<table>_<field>``) and the wizard's per-table
#: extra-keeps pickers (``wizard_keep_<prefix>`` — UX-114; was one cross-table
#: ``wizard_keep_extra`` key before). A composite trial id stores a *list*, so
#: both shapes are read.
_CHOSEN_COLUMN_KEYS = ("col_map_", "wizard_keep_")


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
        if not str(key).startswith(_CHOSEN_COLUMN_KEYS):
            continue
        values = value if isinstance(value, (list, tuple, set)) else [value]
        chosen.update(v for v in values if isinstance(v, str) and v in columns)
    return chosen


def upload_read_plan(
    header, kind: str, *, chosen=(), text_column: str | None = None, identity=()
) -> ReadPlan:
    """Plan an uploaded table's read from its header (PERF-6, decision 2a).

    The mapping is auto-proposed from the column names, so the plan exists
    before the user has touched anything; ``chosen`` folds back in the columns
    they *have* named, which is what keeps a hand-picked mapping or a kept extra
    from being dropped. A column named later simply changes the plan, and the
    read runs again against the new one. ``text_column`` is the user's own
    word-text pick, read verbatim in place of the proposed one (BUG-53), and
    ``identity`` their own id-column picks, read as text (BUG-59).
    """
    propose = propose_word_schema if kind == "words" else propose_fix_schema
    registry = WORD_OPTIONAL_FIELDS if kind == "words" else FIX_OPTIONAL_FIELDS
    names = list(header)
    return plan_table_read(
        names,
        propose(pd.DataFrame(columns=names)),
        registry,
        keep_columns=set(chosen),
        text_column=text_column,
        identity_columns=identity,
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
        columns = _upload_columns_cached(source, _uploaded_file_key(source))
        header.extend(c for c in columns if c not in header)
    return header


@st.cache_data(show_spinner=False, max_entries=64)
def _upload_columns_cached(_uploaded, file_key) -> list:
    """One uploaded file's column names, read once per file (PERF-6's header pass).

    Keyed like the planned read. A delimited file's header is cheap, but a
    workbook or a zipped Parquet / Feather / Excel member has no header-only
    read — :func:`data.read_table_columns` parses it whole — so an uncached pass
    re-parsed the file on every rerun of the wizard: 1.4 s a click on a full
    ``.xls`` sheet, and a second decompressed copy of a large zip held at once.
    """
    return read_table_columns(_uploaded)


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
    label_visibility: str = "visible",
) -> pd.DataFrame:
    """Render one upload box and return its (concatenated) frame.

    Renders into ``container`` — the setup wizard's own step, or the 🗂️ Data
    page's upload slot. Empty frame when nothing is
    uploaded. The file parse is cached on the upload's identity (see
    ``_uploaded_file_key``) so a large uploaded table is read once, not re-parsed
    on every rerun. Isolated from the mapping render so tests can inject frames
    without a real upload (AppTest can't drive ``st.file_uploader``).

    ``label_visibility="collapsed"`` (UX-113) lets a caller draw its own title
    above the box — e.g. via ``controls.inline_field_label``'s dotted-underline
    hover format, matching the mapping steps' field titles — instead of
    Streamlit's own label + native (~1s) help tooltip. The widget still gets the
    real ``uploader_label``/``upload_help`` as its accessible name and help; only
    where they are drawn changes.
    """
    host = container if container is not None else st.container()
    uploaded = host.file_uploader(
        uploader_label,
        type=_UPLOAD_TYPES,
        accept_multiple_files=multi,
        key=f"{state_prefix}_upload",
        help=upload_help,
        label_visibility=label_visibility,
        max_upload_size=upload_limit_mb(),
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
    # BUG-55: a file the readers refuse — an empty file, a corrupt archive or
    # workbook — is the user's to fix, so it is said in the box
    # that took it, the way the metadata uploaders already do, instead of a
    # traceback over the whole page.
    try:
        frame = _read_upload(uploaded, state_prefix, multi=multi, kind=kind)
    except Exception as exc:  # unreadable file — say so, keep the page
        logging.getLogger(__name__).warning(
            "Could not read upload %s", state_prefix, exc_info=True
        )
        st.session_state.pop(f"{state_prefix}_header", None)
        files = uploaded if multi else [uploaded]
        names = ", ".join(str(getattr(f, "name", "the file")) for f in files)
        host.error(f"Couldn't read **{names}**: {exc}")
        return pd.DataFrame()
    # BUG-103: this upload's own ID, before the wizard derives anything from it.
    adopt_source(frame)
    return frame


def _read_upload(uploaded, state_prefix: str, *, multi: bool, kind) -> pd.DataFrame:
    """The header pass and the (cached) planned read behind one upload box."""
    header: list = []
    chosen: tuple = ()
    text_column = None
    identity: tuple = ()
    if kind is not None:
        header = _upload_header(uploaded, multi=multi)
        chosen = tuple(sorted(_columns_chosen_in_state(st.session_state, header)))
        # BUG-53: the word-text column the user mapped by hand (the mapping
        # widget's own key) is the one to read verbatim, not the proposed one.
        picked = st.session_state.get(f"{state_prefix}_text")
        if kind == "words" and isinstance(picked, str) and picked in header:
            text_column = picked
        # BUG-59: likewise the id columns picked by hand, read as text so a
        # zero-padded id keeps its zeros.
        identity = _picked_columns(state_prefix, IDENTITY_SCHEMA_FIELDS, header)
    st.session_state[f"{state_prefix}_header"] = header
    if multi:
        return _read_uploaded_tables_cached(
            uploaded,
            tuple(_uploaded_file_key(f) for f in uploaded),
            kind=kind,
            chosen=chosen,
            text_column=text_column,
            identity=identity,
        )
    return _read_uploaded_table_cached(
        uploaded,
        _uploaded_file_key(uploaded),
        kind=kind,
        chosen=chosen,
        text_column=text_column,
        identity=identity,
    )


def _picked_columns(state_prefix: str, fields, header) -> tuple:
    """The header columns the mapping widgets for ``fields`` currently name."""
    columns = set(header)
    picked: list = []
    for name in fields:
        value = st.session_state.get(f"{state_prefix}_{name}")
        values = value if isinstance(value, (list, tuple)) else [value]
        picked += [v for v in values if isinstance(v, str) and v in columns]
    return tuple(sorted(set(picked)))


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

    # PERF-11: raw gaze is recorded at up to 1000 Hz, so a real table is
    # millions of rows — and both branches below re-read and re-normalized it on
    # every rerun (~1.4 s per click at 1M rows). `frame_cache` keeps the result
    # while its inputs hold and hands back the same object, as for the corpus.
    if data_choice == DEMO_CHOICE:

        def _demo_raw_gaze() -> tuple[pd.DataFrame, dict | None, bool]:
            sample = load_sample_raw_gaze()
            if sample.empty:
                return sample, None, False
            schema = infer_raw_gaze_schema(sample)
            if not schema:
                return pd.DataFrame(), None, True
            return normalize_raw_gaze(sample, schema), schema, False

        raw_gaze_df, raw_gaze_schema, unmappable = frame_cache(
            "raw_gaze", ("demo",), _demo_raw_gaze
        )
        if raw_gaze_schema:
            # The raw sample is read inside the cached builder; its loader is
            # cached too, so asking it again costs a copy of a 2k-row sample.
            _stash_active_mapping(
                "raw_gaze", raw_gaze_schema, load_sample_raw_gaze().columns
            )
        elif unmappable:
            warn.warning("Could not infer raw gaze schema from sample data")
    else:
        uploaded_raw_gaze = cfg.file_uploader(
            "Raw gaze table (optional)",
            type=["csv", "parquet", "feather", "zip"],
            help=(
                "Optional: one row per gaze sample with participant_id, trial_id, "
                "x, y and, if recorded, a timestamp."
            ),
            max_upload_size=upload_limit_mb(),
        )
        if uploaded_raw_gaze:
            upload_key = (uploaded_raw_gaze.file_id, uploaded_raw_gaze.size)
            try:
                raw_gaze_df = frame_cache(
                    "raw_gaze_upload",
                    upload_key,
                    lambda: read_table(uploaded_raw_gaze),
                )
            except Exception as exc:  # unreadable file — say so, keep the page
                cfg.error(f"Couldn't read **{uploaded_raw_gaze.name}**: {exc}")
                return pd.DataFrame()
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
                    # BUG-32: the same source key `main` scopes the tables by.
                    dataset=(
                        data_choice,
                        st.session_state.get("public_dataset_choice"),
                    ),
                )
            problems = validate_raw_gaze_schema(raw_gaze_schema)
            if problems:
                warn.warning("Raw gaze ignored — " + "; ".join(problems))
                raw_gaze_df = pd.DataFrame()
            else:
                _stash_active_mapping("raw_gaze", raw_gaze_schema, raw_gaze_df.columns)
                source = raw_gaze_df
                raw_gaze_df = frame_cache(
                    "raw_gaze",
                    (upload_key, _schema_key(raw_gaze_schema)),
                    lambda: normalize_raw_gaze(source, raw_gaze_schema),
                )

    return raw_gaze_df


# -----------------------------------------------------------------------------
# Data-source resolution + the panels the top menu bar hosts
#
# `_sidebar_group` is gone with the sidebar (UX-38): each former group is its own
# popover on the menu bar (see `menu.render_top_menu`), and the popover's trigger
# label is the group heading. Nothing left to title.
# -----------------------------------------------------------------------------


#: Every built-in token :func:`resolve_data_source` can put in the picker,
#: whatever this run's gates — the ones a user's dataset may never be named
#: (:func:`reserved_source_names`). A name that shadows one gives the picker a
#: duplicate option, hijacks the built-in's load branch, and (DATA-47/48) shares
#: its metadata tables and annotations.
BUILTIN_SOURCE_CHOICES = (
    ONESTOP_CHOICE,
    MULTIPLEYE_BUNDLE_CHOICE,
    DEMO_CHOICE,
    MANUAL_SAMPLE_CHOICE,
    SYNTHETIC_CHOICE,
    AUTHOR_CHOICE,
    UPLOAD_CHOICE,
    PUBLIC_DATASETS_CHOICE,
)


def reserved_source_names() -> frozenset[str]:
    """Every built-in data-source label: the fixed tokens and every corpus."""
    return (
        frozenset(BUILTIN_SOURCE_CHOICES)
        | frozenset(PUBLIC_DATASET_REGISTRY)
        | frozenset(public_dataset_registry())
    )


def resolve_data_source(host=None) -> str:
    """Resolve the active data source (renders no picker widget — UX-25).

    Returns the selected source: ``DEMO_CHOICE`` ("Bundled Demo"), a stored
    uploaded dataset's name, ``ONESTOP_CHOICE`` / ``PUBLIC_DATASETS_CHOICE`` when
    available, ``SYNTHETIC_CHOICE``, or ``UPLOAD_CHOICE``
    while the "➕ Add data" wizard is active. Switching to a stored dataset reloads
    it from session (no re-upload). Manual authoring is opened by the + menu;
    its draft joins the list once opened, including through an old deep link.

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
    entries.append(MANUAL_SAMPLE_CHOICE)
    kinds[MANUAL_SAMPLE_CHOICE] = "✏️"
    if (
        debug_enabled()
        or st.session_state.get("data_source_choice") == SYNTHETIC_CHOICE
    ):
        entries.append(SYNTHETIC_CHOICE)
        kinds[SYNTHETIC_CHOICE] = "🧪"
    if st.session_state.get(
        "data_source_choice"
    ) == AUTHOR_CHOICE or AUTHOR_CHOICE in st.session_state.get(
        "_manual_scanpath_drafts", {}
    ):
        entries.append(AUTHOR_CHOICE)
        kinds[AUTHOR_CHOICE] = "✏️"
    for name in uploaded:
        entries.append(name)
        kinds[name] = (
            "✏️" if st.session_state["_datasets"][name].get("authoring") else "🔒"
        )
    # DATA-27 (Task 11R): every prepared benchmark corpus is in here as its own
    # 🌐 entry, exactly like the built-ins — `public_dataset_registry()` composes
    # the two. Resolved once and reused below so the whole run agrees on one
    # snapshot of a registry that depends on a directory the user can change.
    registry = public_dataset_registry() if public_datasets_enabled() else {}
    for label in registry:
        entries.append(label)
        kinds[label] = "🌐"
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
    # errors on an option that is no longer in the list. A stale benchmark
    # *corpus* label (the bundle directory was repointed, or that corpus was
    # removed from it) lands on another added corpus in preference to
    # `entries[0]` (the demo) whenever one is reachable (N2).
    stale = str(st.session_state.get("data_source_choice") or "")
    if stale not in entries:
        healed = ""
        if stale.endswith(BENCHMARK_LABEL_SUFFIX):
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


# Picker-only sentinel: never a dataset, a comparison source or a share token.
_MORE_DATASETS_PLACEHOLDER = "__more_datasets_coming_soon__"


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
    if picked == _MORE_DATASETS_PLACEHOLDER:
        st.session_state["data_source_picker"] = st.session_state["data_source_choice"]
        return
    if picked:
        if picked == AUTHOR_CHOICE:
            _remember_authoring_return()
        st.session_state["_pending_source_choice"] = picked


def _remember_authoring_return() -> None:
    source = st.session_state.get("data_source_choice", DEMO_CHOICE)
    if source not in (AUTHOR_CHOICE, MANUAL_SAMPLE_CHOICE):
        st.session_state["_author_return_source"] = source


#: The authoring source whose editor is open. ``AUTHOR_CHOICE`` is always an
#: editor; the synthetic sample is a dataset that is *shown* like any other until
#: its ✏️ Edit button arms this key. It is dropped as soon as another source is
#: active, so coming back to the sample shows it rather than reopening the editor.
_AUTHOR_EDITING_KEY = "_author_editing"

#: The synthetic sample's stimulus until it has been edited.
_MANUAL_SAMPLE_TEXT = "The cat sat\non the mat."


def _authoring_editor_open(data_choice: str) -> bool:
    """Whether ``data_choice`` renders the authoring editor instead of a view."""
    return data_choice == AUTHOR_CHOICE or (
        data_choice == MANUAL_SAMPLE_CHOICE
        and st.session_state.get(_AUTHOR_EDITING_KEY) == MANUAL_SAMPLE_CHOICE
    )


def _edit_manual_sample() -> None:
    """Open the authoring editor on the synthetic sample (its ✏️ Edit button)."""
    st.session_state[_AUTHOR_EDITING_KEY] = MANUAL_SAMPLE_CHOICE
    st.session_state["main_nav"] = _VIEW_SCANPATH


def _manual_sample_document() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The synthetic sample's ``(words, events, layout)``, drawn from its draft.

    The seed text until it has been edited, the draft afterwards — the same
    document the editor shows, so viewing the sample never needs the editor.
    """
    from scanpath_studio.authoring import DEFAULT_LAYOUT, default_events, layout_text

    draft = st.session_state.get("_manual_scanpath_drafts", {}).get(
        MANUAL_SAMPLE_CHOICE
    )
    if draft is None:
        layout = dict(DEFAULT_LAYOUT)
        words = layout_text(_MANUAL_SAMPLE_TEXT, **layout)
        return words, default_events(words), layout
    text, layout, events = draft
    layout = {**DEFAULT_LAYOUT, **layout}
    return layout_text(text, **layout), events, layout


def _manual_sample_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The synthetic sample's words and fixations (see `_manual_sample_document`)."""
    from scanpath_studio.authoring import authored_fixations

    words, events, _layout = _manual_sample_document()
    return words, authored_fixations(words, events)


def _manual_sample_canvas() -> tuple[int, int]:
    """The canvas the authoring editor draws the sample on, as a figure size.

    The sample declares its own screen: without it the figure inherits the
    previous source's (the demo's 2560 × 1440) and six words sit in a corner.
    """
    words, _events, layout = _manual_sample_document()
    height = 480
    if not words.empty:
        height = max(
            height,
            int(words["y"].max() + words["height"].max() + layout["margin"]),
        )
    return int(layout["canvas_width"]), height


def _cancel_authoring() -> None:
    if st.session_state.get(_AUTHOR_EDITING_KEY) == MANUAL_SAMPLE_CHOICE:
        # Back out of the sample's editor to the sample itself.
        st.session_state.pop(_AUTHOR_EDITING_KEY, None)
        st.session_state["main_nav"] = _VIEW_SCANPATH
        return
    st.session_state["_pending_source_choice"] = st.session_state.get(
        "_author_return_source", DEMO_CHOICE
    )
    st.session_state["main_nav"] = _VIEW_SCANPATH


#: ``{source: {fixation_id: (word_id, word)}}`` — target words a stimulus edit
#: left out of date (`authoring.stale_target_words`). Flagged on the editor,
#: never rewritten.
_AUTHOR_STALE_TARGETS_KEY = "_author_stale_targets"
#: ``{source: (text, layout, events)}`` — the draft before the last change that
#: removed, moved or retimed fixations (`authoring.destructive_change`). One
#: step, swapped with the current draft by **Restore previous draft**.
_AUTHOR_PREVIOUS_DRAFT_KEY = "_author_previous_drafts"
#: What the downloaded authoring file is called — the name Share → Code's
#: snippet reads it by (`url_state._snippet_source`).
AUTHORING_FILE_NAME = "scanpath.json"


def _load_author_draft(source: str, draft: tuple) -> None:
    """Put ``draft`` — ``(text, layout, events)`` — on the authoring screen.

    Written before the widgets render (a callback), and the table remounts from
    the new events rather than replaying its old edits over them (BUG-19)."""
    text, layout, events = draft
    st.session_state["author_text"] = text
    st.session_state["_author_layout"] = dict(layout)
    st.session_state["_authored_events_frame"] = events.copy()
    st.session_state["_author_text_for_events"] = text
    st.session_state["_author_selected_fixation"] = None
    st.session_state["_author_events_editor_revision"] = (
        int(st.session_state.get("_author_events_editor_revision", 0)) + 1
    )
    st.session_state.setdefault(_AUTHOR_STALE_TARGETS_KEY, {}).pop(source, None)


def _restore_previous_author_draft(source: str) -> None:
    """Swap the current draft with the one before the last destructive edit.

    Pressing it again swaps back, so a restore is never itself a loss."""
    previous = st.session_state.get(_AUTHOR_PREVIOUS_DRAFT_KEY, {}).get(source)
    drafts = st.session_state.setdefault("_manual_scanpath_drafts", {})
    if previous is None:
        return
    current = drafts.get(source)
    _load_author_draft(source, previous)
    drafts[source] = previous
    if current is not None:
        st.session_state[_AUTHOR_PREVIOUS_DRAFT_KEY][source] = current


def _reset_author_fixations(source: str, words: pd.DataFrame) -> None:
    """Replace the fixations with one per word — the explicit regeneration.

    The draft it replaces becomes the previous draft at the end of the run
    (a destructive change), so **Restore previous draft** brings it back."""
    from scanpath_studio.authoring import default_events

    st.session_state["_authored_events_frame"] = default_events(words)
    st.session_state["_author_selected_fixation"] = None
    st.session_state["_author_events_editor_revision"] = (
        int(st.session_state.get("_author_events_editor_revision", 0)) + 1
    )
    st.session_state.setdefault(_AUTHOR_STALE_TARGETS_KEY, {}).pop(source, None)


def _save_authored_dataset(name_key: str) -> None:
    from scanpath_studio.wizard import _safe_dataset_name

    payload = st.session_state.pop("_author_save_payload", None)
    if payload is None:
        return
    requested = str(st.session_state.get(name_key) or "My scanpath").strip()
    if requested in (AUTHOR_CHOICE, MANUAL_SAMPLE_CHOICE):
        requested += " (authored)"
    name = _safe_dataset_name(requested)
    st.session_state.setdefault("_datasets", {})[name] = payload
    # DATA-48: the draft's annotations were made on the scanpath being saved,
    # so they become the saved dataset's. The name is safe, so it holds none.
    if st.session_state.get("data_source_choice") == AUTHOR_CHOICE:
        import scanpath_studio.annotations as _annotations

        _annotations.rename_dataset(st.session_state, AUTHOR_CHOICE, name)
    st.session_state["_pending_source_choice"] = name
    st.session_state["main_nav"] = _VIEW_SCANPATH
    st.session_state["setup_complete"] = True


def _enter_manual_dataset() -> None:
    """Open (or resume) the manual editor through the ordinary source switch."""
    _remember_authoring_return()
    hidden = list(st.session_state.get(HIDDEN_DATASETS_KEY) or [])
    if AUTHOR_CHOICE in hidden:
        hidden.remove(AUTHOR_CHOICE)
        st.session_state[HIDDEN_DATASETS_KEY] = hidden
    st.session_state["_pending_source_choice"] = AUTHOR_CHOICE
    st.session_state["main_nav"] = _VIEW_SCANPATH


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
    actually is — click Corpus Analysis, click Keep setting up, then Cancel, and
    the nav is still genuinely on Corpus Analysis throughout; closing the wizard alone
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
    """Render the dataset picker and its + creation menu (UX-143).

    The menu sits between the dataset and trial selectors. Creation uses the
    existing manual editor or file wizard; the placeholder is picker-only.
    """
    from scanpath_studio.wizard import _enter_add_data_wizard

    entries = list(st.session_state.get("_data_source_entries") or [])
    if not entries:
        return
    kinds: dict[str, str] = dict(st.session_state.get("_data_source_kinds") or {})
    uploaded = list(st.session_state.get("_data_source_uploaded") or [])

    registry = public_dataset_registry()

    def _entry_label(token: str) -> str:
        if token == _MORE_DATASETS_PLACEHOLDER:
            return "More coming soon!"
        # Reads the `registry` snapshot resolved just above rather than calling
        # `public_dataset_registry()` per token: the added corpora can change at
        # runtime, so one run must format its options against one
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
    box = (host if host is not None else st).container(
        key="tour_grp_data_source",
        horizontal=True,
        vertical_alignment="bottom",
        gap="xsmall",
        wrap=False,
    )
    # Mirror the canonical key onto the widget key before it instantiates, so a
    # deep link / restore / wizard finalize shows up in the picker.
    current = st.session_state.get("data_source_choice")
    if current in entries:
        st.session_state["data_source_picker"] = current
    box.selectbox(
        "**Select Dataset**",
        [*entries, _MORE_DATASETS_PLACEHOLDER],
        format_func=_entry_label,
        key="data_source_picker",
        on_change=_on_data_source_pick,
    )
    # The help icon sits in the label row, right-aligned over +, not beside the
    # label: the bottom-aligned row keeps + level with the picker, so the icon
    # lands on the label's line.
    add_col = box.container(width="content", horizontal_alignment="right", gap=None)
    add_col.markdown(
        "",
        width="content",
        help=(
            "Which dataset the app is showing. Use + to create a scanpath or "
            f"import files. Rename or remove datasets on the {ICONS['view_data']} Data Management page. "
            "More coming soon! is a preview of future datasets."
        ),
    )
    # UX-200: named for screen readers; `styles.py` clips the name, so + is
    # still all that is drawn.
    with add_col.popover(
        "Add dataset",
        icon=ICONS["add"],
        help="Add dataset",
        wrap=True,
        key="add_dataset_menu",
    ):
        st.button(
            "Create manually",
            icon=ICONS["author"],
            key="add_manual_dataset_btn",
            help="Write a text and place its fixations, or resume your manual scanpath.",
            on_click=_enter_manual_dataset,
            width="stretch",
        )
        st.button(
            "Import files",
            icon=ICONS["upload"],
            key="import_dataset_btn",
            help="Add your fixation and word/AOI tables with the setup wizard.",
            on_click=_enter_add_data_wizard,
            width="stretch",
        )


#: UX-174 — each dataset kind's word in the table, keyed by the picker's glyph,
#: and the Material Symbol the table draws beside it (the picker keeps its emoji,
#: since a selectbox option is plain text).
_DATASET_KIND_LABELS = {"🧪": "Demo", "✏️": "Manual", "🔒": "Private", "🌐": "Public"}
_DATASET_KIND_ICONS = {
    "Demo": ICONS["demo"],
    "Manual": ICONS["author"],
    "Private": ICONS["private"],
    "Public": ICONS["public"],
}

# Built-in and public dataset tokens are load-path identifiers, so changing
# them would break deep links and loader dispatch. Their table rename is a
# display alias; removing one hides it from this browser session. Uploaded
# datasets keep using the real store re-key/delete operations in `wizard.py`.
DATASET_ALIASES_KEY = "_dataset_display_aliases"
HIDDEN_DATASETS_KEY = "_hidden_dataset_tokens"


def _dataset_display_name(token: str, registry: dict | None = None) -> str:
    """User-facing dataset name without changing the source's stable token."""
    alias = (st.session_state.get(DATASET_ALIASES_KEY) or {}).get(token)
    if alias:
        return str(alias)
    if token == AUTHOR_CHOICE:
        return "My scanpath"
    registry = public_dataset_registry() if registry is None else registry
    return picker_name_for(token, registry) if token in registry else token


# `DATASET_COUNT_FIELDS` — the table's count columns and the only names a
# catalogue entry may publish under — lives in `dataset_table` (UX-174).


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


def published_dataset_counts(token: str, registry: dict | None = None) -> dict:
    """The figures this catalogue publishes for a dataset, or ``{}``.

    Reached through `dataset_about`, so a public corpus, a packaged source and a
    prepared benchmark corpus all answer the same way — and an upload answers
    ``{}``, which is the honest answer: nothing here knows anything about it.
    """
    return dict(dataset_about(token, registry).get("published_counts") or {})


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

    A few distinct-id unions and lengths — UX-54 asked for "measurements that
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

    # BUG-79: a count must not take the page down. `part_catalog` validates as
    # it counts and raises on screen metadata that disagrees across tables —
    # which is worth reporting where the figure is built, not by blanking the
    # whole 🗂️ Data page (and with it the way to switch to another dataset).
    try:
        screens = len(part_catalog(words, fixations, raw_gaze)) or None
    except ValueError as exc:
        logging.getLogger(__name__).warning("Screen count unavailable: %s", exc)
        screens = None
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
        # DATA-50: from every table that names a text, not the words alone.
        "Texts": len(text_ids(words, fixations, raw_gaze)) or None,
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
    if name == AUTHOR_CHOICE:
        _remember_authoring_return()
    st.session_state["_pending_source_choice"] = name
    st.session_state["data_source_choice"] = name


#: UX-54 r2 — the upload the ✕ Delete button asked about, awaiting confirmation.
#: A plain session value, not a widget key: it is armed by a table callback and
#: read by the row of buttons the next run draws.
PENDING_DELETE_KEY = "_dataset_pending_delete"


def _dismiss_delete_confirmation() -> None:
    """``on_dismiss`` for the Remove dialog — the native ✕/Escape path.

    Without this, closing the dialog any way other than its own **Remove** /
    **Keep it** buttons left `PENDING_DELETE_KEY` armed: the fragment reopened
    the same confirmation on its very next rerun, however that rerun was
    triggered, and — since only one Streamlit dialog can show at a time — it
    then also *shadowed* any other row action clicked afterward. Same bug as
    ``_dismiss_dataset_about`` below, same fix.
    """
    st.session_state.pop(PENDING_DELETE_KEY, None)


@st.dialog("Remove this dataset?", on_dismiss=_dismiss_delete_confirmation)
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
        # BUG-95: said "and annotations" while removing none. The count is the
        # dataset's own annotations, which since DATA-48 it alone holds.
        from scanpath_studio.wizard import upload_annotations

        count = len(upload_annotations(token))
        taken = (
            f", column mapping and its {count:,} annotation{'' if count == 1 else 's'}"
            if count
            else " and column mapping"
        )
        st.warning(
            f"Remove **{_dataset_display_name(token)}**? Its tables{taken} "
            "leave this session — there is no undo."
        )
        if count:
            st.caption(
                "To keep a copy, **Export** from the dataset's **Annotations** "
                "tab first."
            )
    else:
        st.caption(
            f"Remove **{_dataset_display_name(token)}** from the list of datasets "
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

    Deleting an upload drops its frames, its mapping and its annotations
    (BUG-95, DATA-48) from the session with no undo, and the button that starts it sits on a row that
    opens the dataset when clicked anywhere else — so the click arms this, and
    this asks.

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


def _overview_sentence(text: str) -> tuple[str, str]:
    """Split a dataset description into its opening sentence and the rest.

    UX-137: the 🗂️ Data page shows the first sentence as the overview under
    "What's in this dataset". UX-177 made every catalogue description one
    sentence, so this only trims a prepared benchmark corpus', whose tail is
    its geometry, license and citation.

    A boundary inside a `code span` does not count. Several descriptions end on
    a module path (``python -m scanpath_studio.update_sample_data``), and cutting
    one at its first dot reads as a typo rather than as a summary.
    """
    body = str(text or "").strip()
    in_code = False
    for index, char in enumerate(body):
        if char == "`":
            in_code = not in_code
            continue
        if char not in ".!?" or in_code:
            continue
        rest = body[index + 1 :]
        if not rest.strip():
            break
        # A real boundary: whitespace, then something that starts a sentence.
        if rest[:1].isspace() and rest.lstrip()[:1].isupper():
            return body[: index + 1], rest.strip()
    return body, ""


def dataset_description(token: str, registry: dict | None = None) -> tuple[str, bool]:
    """The dataset's description, and whether the user wrote it.

    The user's own text (`DATASET_DESCRIPTIONS_KEY`, from the add wizard or
    ✏️ Edit dataset) wins, and the catalogue's (`dataset_about`) is the
    fallback. An empty string the user saved counts as theirs: they cleared it.
    """
    own = st.session_state.get(DATASET_DESCRIPTIONS_KEY) or {}
    if token in own:
        return str(own[token]), True
    return str(dataset_about(token, registry).get("description") or ""), False


def set_dataset_description(token: str, text: str) -> None:
    """Store ``text`` as the dataset's own description."""
    own = dict(st.session_state.get(DATASET_DESCRIPTIONS_KEY) or {})
    own[token] = str(text or "").strip()
    st.session_state[DATASET_DESCRIPTIONS_KEY] = own


def _description_field_key(token: str) -> str:
    return f"dataset_description_{_dataset_row_slug(token)}"


def _description_draft(token: str) -> str | None:
    """The description typed on the open editor, if it differs from the saved
    one (``None`` when it does not, or the field has not drawn)."""
    key = _description_field_key(token)
    if key not in st.session_state:
        return None
    text = str(st.session_state.get(key) or "").strip()
    return None if text == dataset_description(token)[0].strip() else text


def render_description_field(host, token: str) -> None:
    """✏️ Edit dataset's **Description** — the sentence under its name.

    Held, like everything else on the screen, until ✅ Save changes
    (`commit_editor_staging`); ✕ Cancel drops it with the rest of the edit.
    The catalogue's own text is only adopted as the user's when they change it.
    """
    key = _description_field_key(token)
    if key not in st.session_state:
        st.session_state[key] = dataset_description(token)[0]
    host.text_area(
        "Description",
        key=key,
        placeholder="What this dataset is — the readers, the texts, the language.",
        help=f"Shown under the dataset's name on the {ICONS['view_data']} Data "
        f"Management page. Saved with **{ICONS['confirm']} Save changes**.",
        height=80,
        # A draft outlives a visit to another view while the editor is open.
        persist_state="session",
    )


def _render_dataset_overview(token: str, *, registry: dict) -> None:
    """The open dataset in a sentence, and its home page.

    UX-177 cut this to what we stand behind and a new reader can use: the
    description (its first sentence, unless the user wrote it), the corpus'
    home page on the same line, and — only where it changes how a figure is
    read — one ``reading_note`` (PoTeC's reconstructed positions, the demo's
    synthesized raw gaze). The ❔ *About this dataset* popover it replaces
    carried maintainer provenance: how each published figure was counted, a
    published-vs-loaded table, and a coordinate badge for every dataset. The
    table's Status already says whether its numbers are published or loaded.

    Editing it is ✏️ **Edit dataset** on the heading's line (UX-178).
    """
    about = dataset_about(token, registry)
    text, own = dataset_description(token, registry)
    overview = text if own else _overview_sentence(text)[0]
    line = st.container(
        key="dataset_overview_line",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    )
    if link := about.get("link"):
        overview = f"{overview} [Home page ↗]({link})".strip()
    if overview:
        line.caption(overview, width="content")
    if note := about.get("reading_note"):
        st.caption(f"{ICONS['info']} {note}")


@st.cache_data(show_spinner=False)
def _c_annotation_trials(_combos: pd.DataFrame, key) -> frozenset[tuple[str, str]]:
    """The ``(participant, trial)`` pairs of ``_combos``, as strings.

    Cached on the frame's fingerprint (``key``): the Data page asks on every
    rerun — a row ticked in the Annotations table is one — and the answer only
    changes with the dataset.
    """
    if not {"participant_id", "trial_id"} <= set(_combos.columns):
        return frozenset()
    pairs = _combos[["participant_id", "trial_id"]].drop_duplicates()
    return frozenset(
        zip(pairs["participant_id"].astype(str), pairs["trial_id"].astype(str))
    )


def _annotation_trials(combos: pd.DataFrame | None) -> frozenset[tuple[str, str]]:
    """The open dataset's ``(participant, trial)`` pairs, for its Annotations tab."""
    if combos is None or combos.empty:
        return frozenset()
    return _c_annotation_trials(combos, frame_fingerprint(combos))


def render_dataset_inspection_head(token: str) -> None:
    """*What's in the `<name>` dataset*, with ✏️ **Edit dataset** at its end.

    UX-178: the section's one action is a button of its own on the heading's
    line, not a link-weight one beside the description, so it reads as editing
    the whole dataset — its name, its description and its setup, all on the
    screen it opens. It does not apply to the add-dataset wizard's pending
    dataset or to the authoring canvas, which are not rows of the table.
    """
    label = _dataset_display_name(token).replace("`", "'")
    head = st.container(
        key="dataset_inspection_head",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    )
    head.subheader(
        f"{ICONS['search']} What's in the `{label}` dataset", width="stretch"
    )
    if token not in (UPLOAD_CHOICE, AUTHOR_CHOICE):
        head.button(
            "Edit dataset",
            icon=ICONS["edit"],
            key="dataset_edit_btn",
            on_click=_edit_open_dataset,
            args=(token,),
            help="Open the authoring editor — change the text, drag fixations, "
            "or edit their timing."
            if token == MANUAL_SAMPLE_CHOICE
            else "Its name, description, column mapping, recording setup, "
            "location and metadata tables.",
        )
    _render_dataset_overview(token, registry=public_dataset_registry())


def _builtin_name_draft(token: str) -> str | None:
    """The name typed for a dataset that is not an upload, if it is a new one."""
    if EDITOR_NAME_FIELD_KEY not in st.session_state:
        return None
    requested = str(st.session_state.get(EDITOR_NAME_FIELD_KEY) or "").strip()
    if not requested or requested == _dataset_display_name(token):
        return None
    return requested


def _apply_builtin_name(token: str) -> None:
    """✅ Save changes' rename of a dataset that is not an upload.

    A built-in or public source's token is a load-path identifier (deep links,
    loader dispatch), so its name is a display alias — nothing to re-key.
    """
    requested = _builtin_name_draft(token)
    if requested is None:
        return
    tokens = list(st.session_state.get("_data_source_entries") or [])
    final = _unique_dataset_alias(requested, token, tokens)
    aliases = dict(st.session_state.get(DATASET_ALIASES_KEY) or {})
    aliases[token] = final
    st.session_state[DATASET_ALIASES_KEY] = aliases


def _stage_upload_name() -> None:
    """``on_change`` of **Name** for an upload: hold it for ✅ Save changes.

    Kept in a plain ``_remap_`` key rather than read back off the widget, so it
    survives whatever the widget's own state does between runs, and is swept
    with the rest of the edit on Cancel or Save.
    """
    st.session_state[EDITOR_PENDING_NAME_KEY] = str(
        st.session_state.get(EDITOR_NAME_FIELD_KEY) or ""
    ).strip()


def render_name_field(host, token: str) -> None:
    """✏️ Edit dataset's **Name** (UX-178; renaming used to be a dialog).

    Applied by ✅ Save changes with the rest of the edit, and an unsaved change
    until then. An upload's name is the key its every editor widget is filed
    under, so `tabs._apply_remap` re-keys it last; any other dataset's name is
    a display alias (`_apply_builtin_name`).
    """
    uploaded = token in (st.session_state.get("_datasets") or {})
    if EDITOR_NAME_FIELD_KEY not in st.session_state:
        st.session_state[EDITOR_NAME_FIELD_KEY] = st.session_state.get(
            EDITOR_PENDING_NAME_KEY
        ) or _dataset_display_name(token)
    host.text_input(
        "Name",
        key=EDITOR_NAME_FIELD_KEY,
        on_change=_stage_upload_name if uploaded else None,
        help="Shown in the list of datasets and the dataset picker. Saved with "
        f"**{ICONS['confirm']} Save changes**.",
        # A draft outlives a visit to another view while the editor is open.
        persist_state="session",
    )


def _open_mapping_editor() -> None:
    """Raise ✏️ Edit dataset on the open dataset, focused on its mapping."""
    token = str(st.session_state.get("data_source_choice") or "")
    if token:
        st.session_state[FOCUS_MAPPING_KEY] = token
    st.session_state[DATASET_EDITOR_OPEN_KEY] = True
    st.session_state[_EDITOR_SCROLL_KEY] = True


@st.dialog(f"{ICONS['warning']} Check the Trial ID mapping")
def _trial_identity_alert_dialog(asked_by: str, warning: str) -> None:
    """VAL-9 — VAL-7's verdict, raised where the Trial ID was just chosen.

    Opened by ``main`` on the run *after* ✅ Add dataset or ✅ Save changes, from
    the report those buttons' frames produced — so the check runs on the finished
    dataset (it is the sampled one, PERF-6, which is what keeps it cheap enough
    to sit in the commit path at all) rather than as a permanent page-wide
    banner about a decision made twice.

    Two answers, and both are real: **keep it** for a corpus where several
    readings of one text genuinely are one trial, and **edit the mapping** for
    the far commoner case where a column was simply left out of the Trial ID.
    Buttons are handled by their return value, never ``on_click`` — a dialog
    body is a fragment (see ``_leave_dataset_editor_dialog``).
    """
    st.warning(warning, icon=ICONS["warning"])
    st.caption(
        "A Trial ID that doesn't fully identify one reading concatenates several "
        "into one scanpath — which renders perfectly happily, as an ordinary "
        "scanpath with a lot of regressions. The full evidence is on the "
        f"{ICONS['view_data']} Data Management page, under **4 · Trial identity**."
    )
    edit_col, keep_col = st.columns(2, gap="small")
    if edit_col.button(
        f"{ICONS['edit']} Edit the mapping",
        key="trial_identity_alert_edit",
        type="primary",
        width="stretch",
        help=f"Open {ICONS['edit']} Edit dataset on the Trial ID mapping this verdict is about.",
    ):
        _open_mapping_editor()
        st.rerun(scope="app")
    if keep_col.button(
        "Keep it as is",
        key="trial_identity_alert_keep",
        width="stretch",
        help=f"Dismiss. Nothing changes, and the verdict stays on the {ICONS['view_data']} Data Management "
        "page under 4 · Trial identity.",
    ):
        st.rerun(scope="app")
    if asked_by == "add":
        st.caption(
            "Checked automatically because the dataset was just added. It is "
            f"already on the {ICONS['view_data']} Data Management page's list either way."
        )


#: UX-106 — whether the editor's ✕ Cancel confirmation is open. A pending
#: flag rather than a button return value, the house pattern: a callback may not
#: open a dialog, and a dialog opened from a return value is lost on the next
#: full rerun.
_EDITOR_LEAVE_PENDING_KEY = "_dataset_editor_leave_pending"
#: UX-197 — the dataset a row click asked for while the editor had unsaved
#: changes. The table stays on screen above the editor now, so a click on
#: another row is a way out of the editor too, and goes through the same
#: confirmation; ✕ Leave then opens this dataset.
_EDITOR_LEAVE_TARGET_KEY = "_dataset_editor_leave_target"
#: UX-197 — set by whatever opens the editor, popped by its bar: the editor
#: opens under the table, so the page is brought down to it once.
_EDITOR_SCROLL_KEY = "_dataset_editor_scroll"

#: Bring the editor's top under the app's header — in its own scroller, never
#: by `scrollIntoView` (which moves the document; see `tour.py`). Waits while
#: Streamlit is still laying the editor out, then keeps the editor's top in
#: place for a second, because the page above it is still settling and a
#: single scroll lands wherever the layout happened to be at that moment.
_SCROLL_TO_EDITOR_SCRIPT = """<script>
(function () {
  const doc = window.parent.document;
  const win = doc.defaultView;
  let tries = 0, aligned = 0;
  (function attempt() {
    const el = doc.querySelector(".st-key-data_dataset_editor");
    const r = el && el.getBoundingClientRect();
    if (!r || r.height === 0) {
      if (++tries < 20) setTimeout(attempt, 150);
      return;
    }
    for (let box = el.parentElement; box; box = box.parentElement) {
      const cs = win.getComputedStyle(box);
      if (/(auto|scroll|overlay)/.test(cs.overflowY)
          && box.scrollHeight > box.clientHeight + 4) {
        const b = box.getBoundingClientRect();
        box.scrollTop += r.top - b.top - 56;
        break;
      }
    }
    if (++aligned < 8) setTimeout(attempt, 150);
  })();
})();
</script>"""


#: ✏️ Edit dataset's record of the metadata tables as the edit found them.
#: The three metadata sections are the add screen's, and attach a table as its
#: file is read — so rather than stage them, the editor notes what was attached
#: when it opened, ✕ Cancel puts that back, and ✅ Save changes keeps what is
#: there. Taken by `hold_editor_staging` on the editor's first run.
_EDITOR_SNAPSHOT_KEY = "_dataset_editor_snapshot"
#: ✕ Cancel's metadata restore, parked for the next run to apply before the
#: metadata sections draw (`apply_editor_restore`) — the Leave confirmation is
#: a dialog, whose click runs after the page's widgets.
_EDITOR_RESTORE_KEY = "_dataset_editor_restore"


def _metadata_grain_state(grain: str) -> dict:
    """One metadata grain's attached table and the read behind it."""
    key, raw, file = metadata_mod.grain_keys(grain)
    table = st.session_state.get(key)
    frame = getattr(table, "frame", None)
    # Its content, not its identity: the sections rebuild the table every run.
    # Small (one row per reader, trial or text), so hashing it is cheap.
    digest = None
    if isinstance(frame, pd.DataFrame):
        try:
            cells = pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes()
        except (TypeError, ValueError):  # unhashable cells — hash their text
            cells = frame.to_csv(index=False).encode("utf-8")
        digest = (tuple(map(str, frame.columns)), hashlib.sha256(cells).hexdigest())
    return {
        "table": table,
        "raw": st.session_state.get(raw),
        "file": st.session_state.get(file),
        "name": st.session_state.get(f"_{grain}_metadata_name"),
        "content": digest,
    }


def _metadata_grains_changed(snapshot: dict) -> list[str]:
    """The grains whose attached table differs from the editor's snapshot."""
    changed = []
    for grain, before in (snapshot.get("grains") or {}).items():
        now = _metadata_grain_state(grain)
        if (
            (now["table"] is None) != (before["table"] is None)
            or now["raw"] is not before["raw"]
            or now["file"] != before["file"]
            or now["content"] != before["content"]
        ):
            changed.append(grain)
    return changed


def hold_editor_staging(token: str) -> None:
    """Note the metadata tables as this edit finds them (once per edit)."""
    held = st.session_state.get(_EDITOR_SNAPSHOT_KEY)
    if isinstance(held, dict) and held.get("token") == token:
        return
    st.session_state[_EDITOR_SNAPSHOT_KEY] = {
        "token": token,
        "owner": st.session_state.get(metadata_mod.OWNER_KEY),
        "grains": {
            grain: _metadata_grain_state(grain)
            for grain in (metadata_mod.GRAIN_PARTICIPANT, "trial", "text")
        },
    }


def editor_staging_dirty() -> bool:
    """Whether the open editor's name, description or metadata tables differ
    from what it opened on — the part of an edit `tabs.dataset_editor_is_dirty`
    does not see."""
    snapshot = st.session_state.get(_EDITOR_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return False
    token = str(snapshot.get("token") or "")
    return bool(
        _description_draft(token) is not None
        or _builtin_name_draft(token) is not None
        or _metadata_grains_changed(snapshot)
    )


def _editor_is_dirty() -> bool:
    """Whether ✕ Cancel would lose anything (UX-107): the mapping, setup and
    uploads (`tabs.dataset_editor_is_dirty`), or the name, description and
    metadata tables."""
    return dataset_editor_is_dirty() or editor_staging_dirty()


def commit_editor_staging(token: str) -> None:
    """✅ Save changes' share of the edit: the description, a built-in's name,
    and the metadata tables as they now stand.

    Called by both Saves — an upload's (`tabs._apply_remap`, before it re-keys
    the dataset under a new name) and a built-in's — once they know the save
    goes ahead.
    """
    if (text := _description_draft(token)) is not None:
        set_dataset_description(token, text)
    if token not in (st.session_state.get("_datasets") or {}):
        _apply_builtin_name(token)
    _drop_description_drafts()
    # Kept, not restored: what is attached now is what was saved.
    st.session_state.pop(_EDITOR_SNAPSHOT_KEY, None)


def _drop_description_drafts() -> None:
    for key in [
        k
        for k in list(st.session_state)
        if isinstance(k, str) and k.startswith("dataset_description_")
    ]:
        st.session_state.pop(key, None)


def apply_editor_restore() -> None:
    """Put back the metadata tables a cancelled edit changed (`_EDITOR_RESTORE_KEY`).

    Runs before `metadata.activate_dataset` and before the sections draw, so
    the tables go back to the dataset they were taken from. A table the edit
    replaced or detached returns as a *restored* one — its file is no longer in
    the uploader, so it is re-attached the way the recovery cache re-attaches
    a table (`metadata.mark_restored`) rather than read again.
    """
    snapshot = st.session_state.pop(_EDITOR_RESTORE_KEY, None)
    if not isinstance(snapshot, dict):
        return
    if snapshot.get("owner") != st.session_state.get(metadata_mod.OWNER_KEY):
        return
    for grain in _metadata_grains_changed(snapshot):
        before = snapshot["grains"][grain]
        key, raw, file = metadata_mod.grain_keys(grain)
        for name in (
            f"{grain}_metadata_upload",
            f"{grain}_metadata_id_column",
            f"{grain}_metadata_keep_fields",
        ):
            st.session_state.pop(name, None)
        if before["table"] is None:
            for name in (key, raw, file, f"_{grain}_metadata_name"):
                st.session_state.pop(name, None)
            continue
        metadata_mod.mark_restored(st.session_state, grain, before["table"])
        if before["name"] is not None:
            st.session_state[f"_{grain}_metadata_name"] = before["name"]


def _close_dataset_editor() -> None:
    """``on_click`` for the editor's way out — back to 📂 Available datasets."""
    st.session_state.pop(DATASET_EDITOR_OPEN_KEY, None)
    st.session_state.pop(FOCUS_MAPPING_KEY, None)
    st.session_state.pop(_EDITOR_LEAVE_PENDING_KEY, None)
    st.session_state.pop(_EDITOR_LEAVE_TARGET_KEY, None)
    # Anything typed into the editor and not saved goes with it — including a
    # table uploaded to fill a missing half, which is only a *pending* attach
    # until ✅ Save changes runs.
    for key in [k for k in st.session_state if str(k).startswith("_remap_")]:
        st.session_state.pop(key, None)
    # …and the mapping widgets' own answers, which outlive the screen.
    discard_editor_widgets()
    st.session_state.pop(EDITOR_NAME_FIELD_KEY, None)
    # DATA-46: "use the current estimate" is a choice for one editing session.
    for key in [k for k in st.session_state if str(k).endswith("_setup_reestimate")]:
        st.session_state.pop(key, None)
    # A built-in source's unsaved mapping goes too (✅ Save changes has already
    # dropped what it would restore).
    _discard_builtin_mapping_edit()
    # The name and description typed into it, and the metadata tables it
    # changed (✅ Save changes has already dropped the snapshot it would
    # restore them from).
    _discard_editor_staging()


def _discard_editor_staging() -> None:
    """Drop the editor's description drafts; park its metadata restore."""
    _drop_description_drafts()
    snapshot = st.session_state.pop(_EDITOR_SNAPSHOT_KEY, None)
    if isinstance(snapshot, dict) and _metadata_grains_changed(snapshot):
        st.session_state[_EDITOR_RESTORE_KEY] = snapshot


def _ask_leave_dataset_editor() -> None:
    """✕ Cancel: confirm only when there is something to lose (UX-106/UX-107).

    An editor nobody has typed into is a screen you are simply leaving, and a
    modal asking whether you are sure is friction for a decision with no
    consequence. `tabs.dataset_editor_is_dirty` answers the question and errs
    towards *dirty*, so the confirmation is skipped only when the mapping, the
    recording setup and the uploads are all exactly as the editor opened.
    """
    if not _editor_is_dirty():
        _close_dataset_editor()
        return
    st.session_state[_EDITOR_LEAVE_PENDING_KEY] = True


def _dismiss_leave_dataset_editor() -> None:
    st.session_state.pop(_EDITOR_LEAVE_PENDING_KEY, None)
    st.session_state.pop(_EDITOR_LEAVE_TARGET_KEY, None)


@st.dialog("Leave without saving?", on_dismiss=_dismiss_leave_dataset_editor)
def _leave_dataset_editor_dialog() -> None:
    """Confirm discarding an in-progress edit — the add screen's ✕ Cancel.

    The add screen has always confirmed (`_render_leave_prompt`), because
    leaving it throws away an upload. This screen used to leave straight away
    on the reasoning that "an edit is applied by its own button, so leaving
    discards nothing" — which stopped being true once a *table* could be
    uploaded here and be waiting on Save.

    **BUG-49 — both buttons are handled by their return value, never by
    ``on_click``.**
    A dialog body is a fragment, so a callback in here reruns *the dialog* — ✕
    Leave popped the editor's open flag and then sat there with the modal still
    up, and the next click ("Keep editing") ran the whole-app rerun that finally
    acted on it. The screen therefore left on *Keep editing* and did nothing on
    *Leave*. Same lesson as ``_delete_confirmation_dialog``.
    """
    st.caption(
        "Changes you have already saved are kept. Anything edited since — the "
        "name and description, the mapping, the recording setup, the metadata "
        "tables, and any table uploaded to fill a missing one — is discarded."
    )
    leave, stay = st.columns(2, gap="small")
    if leave.button(
        "✕ Leave",
        key="dataset_editor_leave_confirm",
        type="primary",
        width="stretch",
    ):
        target = st.session_state.get(_EDITOR_LEAVE_TARGET_KEY)
        _close_dataset_editor()
        if target:
            # Through the pre-widget seam only: this is a button's return
            # value, after the picker has instantiated in this run.
            st.session_state["_pending_source_choice"] = target
        st.rerun(scope="app")
    if stay.button("Keep editing", key="dataset_editor_leave_cancel", width="stretch"):
        _dismiss_leave_dataset_editor()
        st.rerun(scope="app")


def _render_dataset_editor_bar(host, data_choice: str) -> None:
    """DATA-35 — the ✏️ Edit dataset screen's sticky header.

    Deliberately the add-dataset screen's bar, down to the CSS class: the ask
    was that "the Add Dataset and Edit Dataset screens should be very similar",
    and the two screens ask the same questions of the same dataset — one before
    it exists and one after. The only difference left is the title, which names
    the dataset; UX-106 made the way out the add screen's ✕ Cancel, with the
    same confirmation, because a table uploaded here to fill a missing half is
    pending until ✅ Save changes runs and leaving would drop it in silence.
    """
    name = _dataset_display_name(
        str(st.session_state.get("data_source_choice") or data_choice)
    )
    bar = host.container(key="dataset_editor_bar")
    title_col, back_col = bar.columns([8, 2], vertical_alignment="center")
    title_col.markdown(
        f'<div class="sps-wiz-title">{icon_html("edit")} Edit {html.escape(name)}</div>',
        unsafe_allow_html=True,
    )
    back_col.button(
        # UX-106: the add screen's ✕ Cancel, in the same filled blue and the
        # same corner — the two screens are the same screen, before and after.
        "✕ Cancel",
        key="dataset_editor_close",
        type="primary",
        on_click=_ask_leave_dataset_editor,
        width="stretch",
        help="Leave the editor. Changes you have already saved are kept; "
        "anything unsaved is discarded, after a confirmation.",
    )
    if st.session_state.get(_EDITOR_LEAVE_PENDING_KEY):
        _leave_dataset_editor_dialog()
    if st.session_state.pop(_EDITOR_SCROLL_KEY, False):
        with bar:
            embed_html_iframe(_SCROLL_TO_EDITOR_SCRIPT, height=0)
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


#: UX-174 — the table's inspection seam: `dataset_table.row_record` per row, in
#: list order, rewritten every time the table draws.
DATASET_TABLE_ROWS_KEY = "_dataset_table_rows_current"
#: ``(column, descending)`` or absent (the list's own order). Plain state, not a
#: widget: it is written by the header buttons' callbacks.
_DATASET_TABLE_SORT_KEY = "_dataset_table_sort"
_DATASET_SEARCH_KEY = "dataset_table_search"
_DATASET_KIND_FILTER_KEY = "dataset_table_kinds"
_DATASET_LANGUAGE_FILTER_KEY = "dataset_table_languages"
#: Search and the Kind / Language filters appear only past this many rows — on
#: the short default list they would be controls with nothing to narrow. Ten,
#: since DATA-63 made OneStop four rows: the default list is eight.
_DATASET_FILTER_MIN_ROWS = 10
_DATASET_SORTABLE = ("Kind", "Dataset", *DATASET_COUNT_FIELDS, "Status")
#: Cell widths, in px, shared by the header and every row so the columns line
#: up. The name takes whatever is left (`width="stretch"`, with a CSS minimum).
_DATASET_KIND_W = 92
#: UX-178 — the name has a width of its own, so Status sits right after it and
#: the free space goes between Status and the counts (`_row_gap`).
_DATASET_NAME_W = 280
_DATASET_COUNT_W = 96
_DATASET_STATUS_W = 156  # BUG-113: fits the "Needs download" badge
_DATASET_ACTIONS_W = 40


def _dataset_row_slug(token: str) -> str:
    """A key-safe, stable id for one dataset's row widgets.

    Tokens are display names (spaces, punctuation, em dashes), and a widget key
    is also a CSS class, so the row's keys use a digest of the token instead —
    the same on every run and after any sort, which is what makes a click land
    on the dataset it was drawn for.
    """
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:12]


def _dataset_table_rows(
    *,
    active: str | None,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    raw_gaze: pd.DataFrame | None,
) -> list[DatasetRow]:
    """One `DatasetRow` per listed dataset, in the order they are offered."""
    entries = list(st.session_state.get("_data_source_entries") or [])
    kinds = dict(st.session_state.get("_data_source_kinds") or {})
    uploaded = set(st.session_state.get("_data_source_uploaded") or [])
    stored_uploads = dict(st.session_state.get("_datasets") or {})
    registry = public_dataset_registry()
    # DATA-32: a dataset that has left the list takes its remembered counts with
    # it — deleted, renamed, or a public corpus whose location was unset.
    forget_dataset_counts(keep={t for t in entries if t != UPLOAD_CHOICE})
    # The open corpus is not on disk and the demo is standing in for it: its
    # frames are the demo's, so they are not counted for it. An entry
    # remembered under its name *from these very frames* (counted that way
    # before this guard existed) is dropped; counts remembered from a load of
    # the real corpus have other fingerprints and are kept.
    placeholder = bool(st.session_state.get(_PLACEHOLDER_SHOWN_KEY))
    if placeholder and active:
        store = _counts_store()
        entry = store.get(active)
        stand_in = [frame_fingerprint(f) for f in (words, fixations, raw_gaze)]
        if isinstance(entry, dict) and entry.get("key") == stand_in:
            store.pop(active, None)
    rows: list[DatasetRow] = []
    for token in entries:
        if token in (UPLOAD_CHOICE, AUTHOR_CHOICE):
            continue  # creation flows have their own buttons by the heading
        # DATA-32: counted once per version of a dataset and remembered, so a
        # row keeps its numbers without the frames being in memory. A corpus
        # nobody has opened yet is never loaded to fill its row.
        if token == active and placeholder:
            frames = (None, None, None)
        elif token == active:
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
        measured = remembered_dataset_counts(token, *frames)
        # DATA-36: a row that has never been opened shows the figures the corpus
        # publishes; the moment it is loaded, what loaded takes over.
        row_counts = dataset_row_counts(
            measured=measured, published=about.get("published_counts")
        )
        kind = _DATASET_KIND_LABELS.get(kinds.get(token, ""), "")
        if not kind and token in uploaded:
            kind = "Private"
        rows.append(
            DatasetRow(
                token=token,
                name=_dataset_display_name(token, registry),
                kind=kind,
                language=str(about.get("language") or ""),
                source=row_counts.source,
                counts=dict(row_counts.counts),
                exceeds_published=row_counts.exceeds_published,
                active=token == active,
                measured=bool(measured),
                status=_dataset_status(
                    registry.get(token),
                    stood_in_for=token == active and placeholder,
                ),
                order=len(rows),
            )
        )
    return rows


def _dataset_status(spec: Mapping | None, *, stood_in_for: bool = False) -> str:
    """One row's **Status** — ``""`` (Ready) or what is missing (BUG-113).

    Asked the same way of every row, open or not: a corpus with files on disk
    has a ``files_present`` check in its registry entry — path stats only, never
    a read — and a missing set reads *Needs download* where the app can fetch
    it and *Needs setup* where it cannot. Bundled datasets and stored uploads
    have no check and are always here. The open row whose loader fell back to
    the demo (``stood_in_for``) is not here either, whatever the check says.
    """
    check = (spec or {}).get("files_present")
    if check is None:
        return dataset_table.NEEDS_SETUP if stood_in_for else ""
    try:
        present = bool(check())
    except _MANIFEST_ERRORS:
        present = False
    if present:
        return dataset_table.NEEDS_SETUP if stood_in_for else ""
    if (spec or {}).get("downloadable"):
        return dataset_table.NEEDS_DOWNLOAD
    return dataset_table.NEEDS_SETUP


def _open_dataset_row(token: str) -> None:
    """UX-78 — a click anywhere on a dataset's row opens it.

    UX-197: the table stays above ✏️ Edit dataset, and the editor edits the
    open dataset, so opening another one closes it — at once when nothing is
    unsaved, else through the editor's own *Leave without saving?*.
    """
    if token == st.session_state.get("data_source_choice"):
        return
    st.session_state[_TABLE_NEEDS_APP_RERUN] = True
    if st.session_state.get(DATASET_EDITOR_OPEN_KEY):
        if _editor_is_dirty():
            st.session_state[_EDITOR_LEAVE_PENDING_KEY] = True
            st.session_state[_EDITOR_LEAVE_TARGET_KEY] = token
            return
        _close_dataset_editor()
    _select_dataset(token)


def _edit_open_dataset(token: str) -> None:
    """✏️ **Edit dataset**, at the end of the open dataset's heading (UX-178).

    Raises ✏️ Edit dataset on it — the description, the column mapping, the
    recording setup, the source's options and location, the identity check and
    the metadata tables are all on that screen. `FOCUS_MAPPING_KEY` rides along
    for the mapping editor's "editing <name>". The manual sample has no mapping
    to edit: its editor is the authoring canvas.
    """
    if token == MANUAL_SAMPLE_CHOICE:
        _edit_manual_sample()
        return
    if not st.session_state.get(DATASET_EDITOR_OPEN_KEY):
        # UX-178 — the Name and Description fields are seeded on open; whatever
        # an editor left behind without Cancel or Save (a switch of dataset,
        # say) is not this edit's. An edit already open keeps its drafts.
        st.session_state.pop(EDITOR_NAME_FIELD_KEY, None)
        st.session_state.pop(EDITOR_PENDING_NAME_KEY, None)
        _drop_description_drafts()
    st.session_state[FOCUS_MAPPING_KEY] = token
    st.session_state[DATASET_EDITOR_OPEN_KEY] = True
    st.session_state[_EDITOR_SCROLL_KEY] = True


def _arm_dataset_row(pending_key: str, token: str) -> None:
    """Remove: arm the confirmation; the next run opens it.

    Remove in particular only *arms* (UX-54 r2, UX-79): an upload is not
    recoverable once dropped, so the confirmation does the work.
    """
    st.session_state[pending_key] = token


def _cycle_dataset_sort(column: str) -> None:
    current = st.session_state.get(_DATASET_TABLE_SORT_KEY)
    current = tuple(current) if isinstance(current, tuple | list) else None
    st.session_state[_DATASET_TABLE_SORT_KEY] = dataset_table.next_sort(current, column)


def _render_dataset_table_tools(box, rows: list[DatasetRow]) -> list[DatasetRow]:
    """Search and the Kind / Language filters, for a long list only.

    Returns the rows they leave. Nothing is drawn until the list is long enough
    to need narrowing, and each filter only when it has more than one value to
    choose between.
    """
    if len(rows) <= _DATASET_FILTER_MIN_ROWS:
        return rows
    tools = box.container(
        key="dataset_table_tools",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    )
    query = tools.text_input(
        "Search datasets",
        key=_DATASET_SEARCH_KEY,
        placeholder="Search by name",
        icon=ICONS["search"],
        label_visibility="collapsed",
        width=240,
    )
    kinds = sorted(
        {row.kind for row in rows if row.kind},
        key=dataset_table.KIND_ORDER.index,
    )
    picked_kinds = (
        tools.pills(
            "Kind",
            kinds,
            selection_mode="multi",
            key=_DATASET_KIND_FILTER_KEY,
            label_visibility="collapsed",
        )
        if len(kinds) > 1
        else []
    )
    languages = sorted({row.language for row in rows if row.language})
    picked_languages = (
        tools.multiselect(
            "Language",
            languages,
            key=_DATASET_LANGUAGE_FILTER_KEY,
            placeholder="Any language",
            label_visibility="collapsed",
            width=220,
        )
        if len(languages) > 1
        else []
    )
    return dataset_table.filter_rows(
        rows,
        query=query or "",
        kinds=picked_kinds or (),
        languages=picked_languages or (),
    )


def _render_dataset_table_head(grid, sort) -> None:
    """The header line — each sortable column's name is its sort button."""
    head = grid.container(
        key="dsrow_head",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
        wrap=False,
    )

    def _sort_button(cell, column: str, help_text: str) -> None:
        icon = None
        if sort and sort[0] == column:
            icon = ICONS["sort_desc"] if sort[1] else ICONS["sort_asc"]
        cell.button(
            column,
            key=f"dataset_sort_{_field_slug(column)}",
            type="tertiary",
            icon=icon,
            icon_position="right",
            on_click=_cycle_dataset_sort,
            args=(column,),
            help=help_text,
        )

    _sort_button(
        head.container(key="dsh_kind", width=_DATASET_KIND_W),
        "Kind",
        "Sort by kind — Demo, Manual, Private, Public.",
    )
    _sort_button(
        head.container(key="dsh_name", width=_DATASET_NAME_W),
        "Dataset",
        "Sort by name. Click a row to open that dataset.",
    )
    _sort_button(
        head.container(key="dsh_status", width=_DATASET_STATUS_W),
        "Status",
        " ".join(
            f"**{label}** — {text}"
            for label, text in dataset_table.STATUS_EXPLANATIONS.items()
        ),
    )
    head.space("stretch")
    gaps = " ".join(
        f"**{label}** — {dataset_table.GAP_EXPLANATIONS[label]}"
        for label in (
            dataset_table.NOT_LOADED,
            dataset_table.NOT_REPORTED,
            dataset_table.UNKNOWN,
        )
    )
    for count_field in dataset_table.TABLE_COUNT_FIELDS:
        cell = head.container(
            key=f"dsh_{_field_slug(count_field)}",
            width=_DATASET_COUNT_W,
            horizontal=True,
            horizontal_alignment="right",
        )
        _sort_button(
            cell,
            count_field,
            f"Sort by {count_field.lower()}, largest first. Datasets without a "
            f"count sort last either way.\n\n{dataset_table.COUNTS_EXPLANATION}"
            f"\n\n{gaps}",
        )
    # The actions column has no title: its one button says what it does. The
    # cell is still drawn — an empty container is not — so the columns line up.
    head.container(key="dsh_actions", width=_DATASET_ACTIONS_W).markdown(
        '<span aria-hidden="true">&nbsp;</span>', unsafe_allow_html=True
    )


def _field_slug(count_field: str) -> str:
    return count_field.lower().replace(" ", "_")


def _dataset_count_cell_html(row: DatasetRow, count_field: str) -> str:
    """One count cell: the grouped number, or its reason in a muted voice."""
    value = row.value(count_field)
    if value is not None:
        return f'<span class="sps-ds-num">{dataset_table.format_count(value)}</span>'
    return (
        f'<span class="sps-ds-num sps-ds-gap">{html.escape(row.gap(count_field))}'
        "</span>"
    )


def _render_dataset_table_row(grid, row: DatasetRow) -> None:
    """One dataset's line of the table.

    The whole line opens the dataset: its first child is a button stretched
    over the row by CSS (`styles.py`, *UX-174 r2*), and the cells drawn above it
    let a click through, except the one holding **Remove**.
    """
    slug = _dataset_row_slug(row.token)
    line = grid.container(
        # The open row's key carries `current`, which is what the tint keys on.
        key=f"dsrow_current_{slug}" if row.active else f"dsrow_{slug}",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
        wrap=False,
    )
    line.button(
        f"Open {row.name}",
        key=f"dataset_open_{slug}",
        type="tertiary",
        on_click=_open_dataset_row,
        args=(row.token,),
    )
    kind = line.container(key=f"dsc_kind_{slug}", width=_DATASET_KIND_W)
    if row.kind:
        kind.markdown(f"{_DATASET_KIND_ICONS[row.kind]} {row.kind}")

    name = line.container(
        key=f"dsc_name_{slug}",
        width=_DATASET_NAME_W,
        horizontal=True,
        vertical_alignment="center",
        gap="xsmall",
        wrap=True,
    )
    name.markdown(
        f'<span class="sps-ds-name">{html.escape(row.name)}</span>',
        unsafe_allow_html=True,
        width="content",
    )
    if row.active:
        # A word, not only a colour: the badge says it, the tint repeats it.
        name.badge("Current", icon=ICONS["current"], color="blue")
    if row.exceeds_published:
        # DATA-36's discrepancy warning, kept — it is rare, and it is the one
        # thing on a row that says a number elsewhere is wrong.
        name.badge(
            "More than published",
            icon=ICONS["warning"],
            color="orange",
            help="This session loaded **more** than the corpus publishes for "
            f"{', '.join(row.exceeds_published)} — a corpus cannot be larger "
            "when loaded than it is, so the published figure is the one to fix.",
        )

    status = line.container(key=f"dsc_status_{slug}", width=_DATASET_STATUS_W)
    if row.status:
        # Something is missing before the dataset can open (BUG-113).
        status.badge(row.status, icon=ICONS["warning"], color="orange")
    else:
        status.markdown(
            f'<span class="sps-ds-status">{row.status_label}</span>',
            unsafe_allow_html=True,
        )

    line.space("stretch")
    for count_field in dataset_table.TABLE_COUNT_FIELDS:
        cell = line.container(
            key=f"dsc_{_field_slug(count_field)}_{slug}", width=_DATASET_COUNT_W
        )
        cell.markdown(
            _dataset_count_cell_html(row, count_field), unsafe_allow_html=True
        )

    actions = line.container(
        key=f"dsc_actions_{slug}",
        width=_DATASET_ACTIONS_W,
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
    )
    actions.button(
        f"Remove {row.name}",
        icon=ICONS["delete"],
        key=f"dataset_row_remove_{slug}",
        type="tertiary",
        on_click=_arm_dataset_row,
        args=(PENDING_DELETE_KEY, row.token),
        help=f"Remove {row.name} from this session, after a confirmation.",
    )


def dataset_table_scope_note(*, filtered: bool, stand_in_for: str | None) -> str | None:
    """The line under 📂 Available datasets when 📊 Stats counts something else
    (UX-203): a trial-filtered pool, or the bundled demo standing in for
    ``stand_in_for``, a corpus that isn't on disk. ``None`` when the row and
    Stats count the same thing.
    """
    if stand_in_for:
        return (
            f"Rows count whole datasets. {stand_in_for} isn't loaded, so Stats "
            "below counts the bundled demo shown in its place"
            + (", narrowed by the trial filters." if filtered else ".")
        )
    if filtered:
        return (
            "Whole datasets, before the trial filters — Stats below counts the "
            "filtered trials."
        )
    return None


@st.fragment
def render_dataset_table(
    host=None,
    *,
    active: str | None = None,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    raw_gaze: pd.DataFrame | None = None,
    scope_note: str | None = None,
) -> None:
    """📂 Available datasets — one focused row per dataset (UX-54 → UX-174).

    **Kind · Dataset · Status · Participants · Texts · Trials · Fixations ·
    Remove** (UX-178 moved Status beside the name it qualifies). A click anywhere on a row opens that dataset (UX-78); the open one
    carries a **Current** badge and a tint, and never moves. **Status** is
    whether the dataset can be opened now — *Ready*, *Needs download* or
    *Needs setup* — asked the same way of every row (BUG-113; see
    `_dataset_status`). Everything else about a dataset —
    Screens, Words and Gaze points, its description, renaming it, editing its
    setup — is in *What's in the dataset* under the table, for the open one.

    Built from widgets rather than an ``st.dataframe``: a grid cannot say *Not
    loaded* in a numeric column without sorting it as text. Sorting is ours
    instead (`dataset_table.sort_rows`, on the integers, missing values last),
    so it is numeric by construction; and every control is a real button keyed
    by its dataset, so a click after any sort acts on the row it was drawn in.

    **Counts are only shown for data already in memory, remembered, or
    published** — the open dataset (whose frames are passed in), every stored
    upload, anything counted earlier (DATA-32), and a corpus' published figures.
    Nothing is read from disk to fill a row.

    Args:
        host: Container to render into. Defaults to the fragment's own.
        active: The open dataset's entry token, marked in the table.
        words: The open dataset's word frame, for its counts.
        fixations: Its fixation frame.
        raw_gaze: Its raw-gaze frame.
        scope_note: A line under the rows saying the counts are whole
            datasets, given while 📊 Stats counts something else
            (`dataset_table_scope_note`, UX-203).
    """
    # DATA-35: Remove only opens a dialog, which costs a *fragment* rerun, not a
    # whole-app one. Opening a dataset asks for the app rerun here, because a
    # callback may not.
    if st.session_state.pop(_TABLE_NEEDS_APP_RERUN, False):
        st.rerun(scope="app")
    rows = _dataset_table_rows(
        active=active, words=words, fixations=fixations, raw_gaze=raw_gaze
    )
    # Inspection seam (tests, the debug panel): what each row says, by value.
    st.session_state[DATASET_TABLE_ROWS_KEY] = [
        dataset_table.row_record(row) for row in rows
    ]
    if not rows:
        return
    uploaded = set(st.session_state.get("_data_source_uploaded") or [])
    tokens = [row.token for row in rows]
    box = (host if host is not None else st).container(key="dataset_table")

    shown = _render_dataset_table_tools(box, rows)
    sort = st.session_state.get(_DATASET_TABLE_SORT_KEY)
    if not (
        isinstance(sort, tuple | list)
        and len(sort) == 2
        and sort[0] in _DATASET_SORTABLE
    ):
        sort = None
    grid = box.container(key="dataset_table_grid")
    _render_dataset_table_head(grid, sort)
    ordered = dataset_table.sort_rows(
        shown, sort[0] if sort else None, descending=bool(sort and sort[1])
    )
    for row in ordered:
        _render_dataset_table_row(grid, row)
    if not ordered:
        box.caption("No dataset matches the search and filters.")
    if scope_note:
        box.container(key="dataset_table_scope").caption(
            f"{ICONS['trial_filter']} {scope_note}"
        )

    _render_delete_confirmation(box, tokens, uploaded)
    if note := st.session_state.pop("_dataset_table_note", None):
        box.success(note)


def _rows_with_local_images(frame: pd.DataFrame) -> int:
    """How many rows of ``frame`` name a stimulus image that exists on disk.

    One ``os.path.isfile`` per **distinct** path rather than per row. The whole
    point of `data.resolve_stimulus_image_paths` probing once per placeholder
    tuple is lost if the caption it feeds then re-stats every row of a
    multi-million-row corpus.
    """
    paths = None if frame is None else frame.get("image_path")
    if paths is None or paths.empty:
        return 0
    counts = paths.dropna().astype(str).value_counts()
    return int(sum(rows for path, rows in counts.items() if os.path.isfile(path)))


def resolve_source_monitor(
    data_choice: str | None,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    *,
    own_setup: bool = True,
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

    ``words`` / ``fixations`` are read by the **last** branch alone, which
    estimates a canvas from data extents when nothing else declared one. Pass
    ``None`` for both to say "don't estimate": the answer degrades to
    `DEFAULT_FIGURE_SIZE`, still non-authoritative, and the row scan is skipped.
    Only a caller that will discard a non-authoritative size may do that.

    A built-in or public dataset whose recording setup the user saved on
    ✏️ Edit dataset answers with that screen, authoritatively — it is this
    dataset's setup now (`dataset_setup_override`). ``own_setup=False`` asks
    for what the source itself declares instead: the share link's elision
    (`url_state._link_defaults`) needs what a *recipient* resolves, and the
    recipient has no override.
    """
    if own_setup and (
        override := dataset_setup_override(setup_override_token(data_choice))
    ):
        return override.canvas_width, override.canvas_height, True
    # OneStop server bundle + bundled demo share the same experimental setup
    # (Dell U2715H, 2560x1440) — cited once in
    # `eyegenbench_geometry.DISPLAY_SPECS["onestop"]`.
    if data_choice in (ONESTOP_CHOICE, DEMO_CHOICE):
        return 2560, 1440, True
    if data_choice == MANUAL_SAMPLE_CHOICE:
        return (*_manual_sample_canvas(), True)
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


def setup_override_token(data_choice: str | None) -> str | None:
    """The dataset a recording-setup override is filed under: the public
    corpus' label behind ``PUBLIC_DATASETS_CHOICE``, else the choice itself."""
    if data_choice == PUBLIC_DATASETS_CHOICE:
        return st.session_state.get("public_dataset_choice") or None
    return data_choice


def dataset_setup_override(token: str | None) -> SetupSnapshot | None:
    """The recording setup the user saved for a built-in or public dataset, or
    ``None`` when they saved none (the corpus' own declaration stands).

    An upload's setup lives on its own ``_datasets`` entry, so a name that is an
    upload never answers here, even if an override was once filed under it.
    """
    if not token or token in (st.session_state.get("_datasets") or {}):
        return None
    payload = (st.session_state.get(DATASET_SETUP_OVERRIDES_KEY) or {}).get(token)
    if not isinstance(payload, dict):
        return None
    return SetupSnapshot.from_dict(payload, fallback=SetupSnapshot())


def setup_override_session_values(snapshot: SetupSnapshot) -> dict:
    """The ``global_*`` values a saved setup puts on the figure — the keys the
    add flow publishes, plus the DPI those imply."""
    return {
        "global_canvas_width": int(snapshot.canvas_width),
        "global_canvas_height": int(snapshot.canvas_height),
        "global_monitor_width_mm": float(snapshot.monitor_width_mm),
        "global_viewing_distance_mm": float(snapshot.viewing_distance_mm),
        "global_display_dpi": round(
            float(snapshot.canvas_width) / (float(snapshot.monitor_width_mm) / 25.4),
            2,
        ),
        "global_base_font_size": int(snapshot.base_font_size),
        "global_font_family": str(snapshot.font_family),
        "global_line_spacing": float(snapshot.line_spacing),
        "global_scale_text_to_boxes": bool(snapshot.scale_text_to_boxes),
    }


def _restore_setup_override_stash() -> None:
    """Put back what the ``global_*`` keys held before an override was applied."""
    st.session_state.pop(SETUP_OVERRIDE_FOR_KEY, None)
    stashed = st.session_state.pop(SETUP_OVERRIDE_RESTORE_KEY, None)
    for key, value in (stashed or {}).items():
        if value is None:
            st.session_state.pop(key, None)
        else:
            st.session_state[key] = value


def _apply_setup_override(
    token: str, snapshot: SetupSnapshot, skip: frozenset = frozenset()
) -> None:
    """Write ``snapshot`` onto the figure as ``token``'s setup, remembering what
    it replaced. ``skip`` — keys a share link just seeded, which win."""
    if st.session_state.get(SETUP_OVERRIDE_FOR_KEY) != token:
        # The first override of a run of them keeps the pre-override state.
        st.session_state.setdefault(
            SETUP_OVERRIDE_RESTORE_KEY,
            {
                key: None if key in skip else st.session_state.get(key)
                for key in SETUP_OVERRIDE_SESSION_KEYS
            },
        )
    for key, value in setup_override_session_values(snapshot).items():
        if key not in skip:
            st.session_state[key] = value
    st.session_state[SETUP_OVERRIDE_FOR_KEY] = token


def save_dataset_setup_override(token: str, payload: dict | None) -> None:
    """✅ Save changes for a built-in or public dataset's Recording setup.

    ``payload`` (a ``SetupSnapshot.to_dict()``) becomes the dataset's own setup
    and applies to the figure at once, as an upload's saved setup does;
    ``None`` drops it — *Reset to source setup* — and puts back what the figure
    showed before it, so the corpus' declared screen snaps in again. Only this
    dataset's entry changes: another dataset's override is never touched.
    """
    overrides = dict(st.session_state.get(DATASET_SETUP_OVERRIDES_KEY) or {})
    if payload is None:
        overrides.pop(token, None)
        st.session_state[DATASET_SETUP_OVERRIDES_KEY] = overrides
        if st.session_state.get(SETUP_OVERRIDE_FOR_KEY) == token:
            _restore_setup_override_stash()
        # Re-snap the canvas to what the source itself declares.
        st.session_state.pop("_canvas_seeded_for", None)
        return
    snapshot = SetupSnapshot.from_dict(payload, fallback=SetupSnapshot())
    overrides[token] = snapshot.to_dict()
    st.session_state[DATASET_SETUP_OVERRIDES_KEY] = overrides
    _apply_setup_override(token, snapshot)


def _declared_setup_snapshot(choice: str | None) -> SetupSnapshot | None:
    """What a built-in source itself declares (``active_setup_snapshot``'s
    answer before overrides existed), or ``None`` when it declares nothing."""
    declared = (
        choice in (ONESTOP_CHOICE, DEMO_CHOICE, MULTIPLEYE_BUNDLE_CHOICE)
        or _public_dataset_monitor(choice) is not None
        # A public corpus reached by its own label (the DATA-3 OneStop source)
        # rather than through the `Public datasets` picker still declares a
        # monitor in the registry.
        or bool((public_dataset_registry().get(choice) or {}).get("monitor"))
    )
    if not declared:
        return None
    snapshot = capture_setup_snapshot(
        {
            # The corpus declares its presentation monitor, so the screen is
            # measured. The physical size / viewing distance are *not* — no
            # registry entry records them, so they stay honestly "assumed".
            "screen": Provenance.MEASURED,
            "geometry": Provenance.ASSUMED,
            "text": Provenance.MEASURED,
        }
    )
    token = setup_override_token(choice)
    if token and st.session_state.get(SETUP_OVERRIDE_FOR_KEY) == token:
        # The live keys hold this dataset's override: the source's own values
        # are the ones it replaced, and its screen the one it declares.
        stashed = st.session_state.get(SETUP_OVERRIDE_RESTORE_KEY) or {}
        width, height, _ = resolve_source_monitor(choice, None, None, own_setup=False)
        fields = {"canvas_width": int(width), "canvas_height": int(height)}
        for key, name, cast in (
            ("global_monitor_width_mm", "monitor_width_mm", float),
            ("global_viewing_distance_mm", "viewing_distance_mm", float),
            ("global_base_font_size", "base_font_size", int),
            ("global_font_family", "font_family", str),
            ("global_line_spacing", "line_spacing", float),
            ("global_scale_text_to_boxes", "scale_text_to_boxes", bool),
        ):
            value = stashed.get(key)
            fields[name] = (
                cast(value) if value is not None else getattr(SetupSnapshot(), name)
            )
        snapshot = replace(snapshot, **fields)
    return snapshot


@st.cache_data(show_spinner=False, max_entries=8)
def _c_canvas_size(_words, _fixations, fingerprints: tuple) -> tuple[int, int]:
    """`compute_canvas_size`, cached on the frames' fingerprints."""
    return compute_canvas_size(_words, _fixations)


def cached_canvas_size(
    words: pd.DataFrame | None, fixations: pd.DataFrame | None
) -> tuple[int, int]:
    """The data-extent screen estimate, without rescanning every row per rerun
    — ✏️ Edit dataset asks it on every render while its form is open."""
    return _c_canvas_size(
        words, fixations, (frame_fingerprint(words), frame_fingerprint(fixations))
    )


def source_setup_snapshot(
    data_choice: str | None,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
) -> SetupSnapshot:
    """A built-in or public dataset's setup **as its source states it** — what
    ✏️ Edit dataset's *Reset to source setup* returns to.

    A corpus that declares its monitor reports it as measured; one that does
    not (a prepared benchmark corpus whose manifest invents its screen) gets
    the extent of its data, estimated, as `compare_source.snapshot_for` does.
    """
    declared = _declared_setup_snapshot(data_choice)
    if declared is not None:
        return declared
    width, height, authoritative = resolve_source_monitor(
        data_choice, None, None, own_setup=False
    )
    if not authoritative and (words is not None or fixations is not None):
        width, height = cached_canvas_size(words, fixations)
    return SetupSnapshot(
        canvas_width=int(width),
        canvas_height=int(height),
        screen_provenance=(
            Provenance.MEASURED if authoritative else Provenance.ESTIMATED
        ),
        geometry_provenance=Provenance.ASSUMED,
        text_provenance=Provenance.ASSUMED,
    )


def active_setup_snapshot(
    data_choice: str | None = None,
) -> SetupSnapshot | None:
    """A source's recorded setup, or ``None`` when it has none.

    A stored upload carries the snapshot the wizard captured; a built-in or
    public dataset whose setup the user saved on ✏️ Edit dataset reports that
    (`dataset_setup_override`); a built-in corpus that declares a monitor
    reports it as ``MEASURED``; anything else has nothing to say, and saying
    nothing is the honest answer (a caller must not print "assumed 2560x1440"
    for a corpus that never claimed one).

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
    if (override := dataset_setup_override(setup_override_token(choice))) is not None:
        return override
    if (declared := _declared_setup_snapshot(choice)) is not None:
        return declared
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
    #
    # The frames are withheld once the canvas keys exist, because that is the
    # only thing they are read for. `resolve_source_monitor`'s last-resort
    # branch scans every row of both to *estimate* a canvas from data extents —
    # tens of milliseconds per rerun on a full corpus — and a source that needs
    # estimating is by definition not authoritative, so the number it returns
    # reaches only `defaults` below, where `_pin` is a setdefault and `_resolved`
    # prefers the stored key. First run derives it; every rerun after that was
    # paying for a value it threw away. `tabs._compare_setups` withheld the same
    # scan from B's side for the same reason (CMP-11).
    canvas_seeded = {"global_canvas_width", "global_canvas_height"} <= set(
        st.session_state
    )
    # The source's own screen: a recording setup the user saved for it is
    # applied after these snaps (below), so what it replaces — and puts back on
    # leaving — is the source's canvas, not its own.
    default_canvas_w, default_canvas_h, monitor_is_authoritative = (
        resolve_source_monitor(
            data_choice,
            None if canvas_seeded else words_filtered,
            None if canvas_seeded else fixations_filtered,
            own_setup=False,
        )
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
    #
    # EXP-19 — except where a share link has just said otherwise. A link seeds
    # these keys before this first run gets here, and carries the canvas / font
    # only when the sender's differs from the corpus', so snapping over them
    # would undo exactly the part of the link that was worth sending. The link
    # names what it seeded *and for which source*; the first seeding consumes
    # that, and honours it only for the linked source — a link that fell back to
    # another corpus, or a first run that never got this far, must not leave the
    # next source opened without its own monitor.
    source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    from_link = link_setup_keys_for(source_key)
    # A recording setup the user saved for a built-in or public dataset is that
    # dataset's alone: leaving it puts back what the figure held before — first,
    # so the snaps below then answer for the next source as they always have.
    override_token = setup_override_token(data_choice)
    applied_for = st.session_state.get(SETUP_OVERRIDE_FOR_KEY)
    if applied_for is not None and applied_for != override_token:
        _restore_setup_override_stash()
    if monitor_is_authoritative and st.session_state.get("_canvas_seeded_for") != (
        source_key
    ):
        for key, value in (
            ("global_canvas_width", canvas_width),
            ("global_canvas_height", canvas_height),
        ):
            if key not in from_link:
                st.session_state[key] = value
        st.session_state["_canvas_seeded_for"] = source_key
    # The canvas pair itself is pinned with the rest of the defaults below.

    # Authoritative reading font: MultiplEYE stamps the stimulus FONT_SIZE + family
    # from its config onto the words. Snap the font controls to it when the source
    # changes (same gate as the canvas), so the reading text renders at the exact
    # size and (CJK) typeface the stimulus images were drawn with. We also turn off
    # "scale text to boxes" since the precise px is known — box geometry can only
    # approximate it. Manual edits within a source stick (the key is unchanged, so
    # the snap doesn't re-fire); a returning source re-snaps to the known font.
    #
    # BUG-50 — **and the snap is undone on the way out.** It used to be gated on
    # ``font_px is not None``, so a source that declares no typeface skipped the
    # whole block and simply inherited the previous corpus'. Demo → MultiplEYE →
    # Demo therefore came back with MultiplEYE's px, its CJK stack, and
    # *scale-to-boxes off* — the demo's reading text visibly smaller than it had
    # been, with nothing on screen saying why, and it stayed that way for the
    # rest of the session (and into the recovery cache, and into any link or
    # config saved from it).
    #
    # The general shape, worth stating because the other two source-switch snaps
    # in this file share it: a snap writes **session**-scoped state to express a
    # **source**-scoped fact. That only stays consistent if every source answers
    # the question. The canvas one does (`resolve_source_monitor` always returns
    # a canvas) and so is self-correcting by luck rather than by design; this one
    # cannot, because most corpora ship no typeface — so it has to remember what
    # it overwrote and put it back.
    #
    # Restoring the *stashed* values rather than the factory defaults is what
    # keeps a hand-tuned font across a detour: tune the demo, look at MultiplEYE,
    # come back, and your own size is still there. Stashed only on the **first**
    # snap of a run of them, so MultiplEYE → another font-declaring corpus →
    # Demo restores the pre-MultiplEYE state and not MultiplEYE's.
    if st.session_state.get("_font_seeded_for") != source_key:
        # Read only when the snap can fire: on a font-declaring corpus it is a
        # numeric parse over every word row, and every other run discards it.
        font_px, font_css = _dataset_font(words_filtered)
        if font_px is not None:
            # A value a link seeded is this source's own, not something to put
            # back on the way out — so it is stashed as absent, and leaving the
            # corpus restores the factory value rather than the corpus' font.
            st.session_state.setdefault(
                _FONT_SNAP_RESTORE_KEY,
                {
                    key: None if key in from_link else st.session_state.get(key)
                    for key in _FONT_SNAP_KEYS
                },
            )
            snapped = {
                "global_base_font_size": int(min(max(round(font_px), 6), 72)),
                "global_scale_text_to_boxes": False,
            }
            if font_css:
                snapped["global_font_family"] = font_css
            for key, value in snapped.items():
                if key not in from_link:
                    st.session_state[key] = value
        elif (
            stashed := st.session_state.pop(_FONT_SNAP_RESTORE_KEY, None)
        ) is not None:
            for key, value in stashed.items():
                if value is None:
                    # Absent before the snap — drop it so the `defaults` pin a
                    # few lines down restores the factory value this same run,
                    # rather than freezing whatever the last corpus left.
                    st.session_state.pop(key, None)
                else:
                    st.session_state[key] = value
        # Not in the `font_px is None` + never-snapped case: a fresh session, a
        # deep link or a restored config may have set these keys deliberately,
        # and nothing has overwritten them, so there is nothing to undo.
        st.session_state["_font_seeded_for"] = source_key

    # …and entering a dataset with a saved setup applies it, after the canvas
    # and font snaps so it is what the figure shows. Once per visit: a value
    # tuned on the rail afterwards stays until the dataset is left.
    if (
        override_token
        and st.session_state.get(SETUP_OVERRIDE_FOR_KEY) != override_token
        and (override := dataset_setup_override(override_token)) is not None
    ):
        _apply_setup_override(override_token, override, frozenset(from_link))

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
        **SETUP_DEFAULTS,
        "global_scale_text_to_boxes": True,
        "global_line_spacing": float(DEFAULT_LINE_SPACING),
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


#: The CSS stack UX-163's *Multilingual* button writes into the text font — a
#: CJK / Hebrew / Arabic-capable fallback (PRE-6).
_MULTILINGUAL_FONT_STACK = (
    "'Noto Sans', 'Noto Sans Hebrew', 'Noto Sans Arabic', "
    "'Noto Sans CJK SC', 'Arial Unicode MS', sans-serif"
)


def _rail_monitor_row(host) -> tuple[int, int]:
    """The monitor's pixel size as one ``Monitor | W × H px`` row (UX-163)."""
    label_w = _label_w()
    rest = 1.0 - label_w
    label_col, width_col, times_col, height_col, unit_col = host.columns(
        [label_w, rest * 0.4, rest * 0.08, rest * 0.4, rest * 0.12],
        gap=_LABEL_GAP,
        vertical_alignment="center",
    )
    _row_label(
        label_col,
        "Monitor",
        "The presentation monitor's width × height in pixels. Keep it true to the "
        "experiment's screen so coordinates and word boxes stay to scale.",
    )
    width = width_col.number_input(
        "Monitor width (px)",
        min_value=100,
        max_value=10000,
        step=10,
        key="global_canvas_width",
        persist_state="session",
        label_visibility="collapsed",
    )
    _sub_caption(times_col, "×")
    height = height_col.number_input(
        "Monitor height (px)",
        min_value=100,
        max_value=10000,
        step=10,
        key="global_canvas_height",
        persist_state="session",
        label_visibility="collapsed",
    )
    _sub_caption(unit_col, "px")
    return int(width), int(height)


def _rail_text_rows(
    host,
    *,
    seeded: tuple,
    display_dpi: float,
    words_filtered: pd.DataFrame,
    font_css,
    disabled: bool,
    section: str | None,
) -> tuple[int, str, float, bool]:
    """The rail's typography rows, under 📄 Stimulus → *Text* (UX-163).

    Four captioned rows (`_sub_row`) instead of up to nine that came and went:

    * *Fit* — **Scale to boxes** and the line spacing it divides a box by
      (greyed while it is off);
    * *Size* — the unit (px / pt) and the size. While the text is fitted to the
      boxes the size is the axis, legend and fallback text's, in px, so the unit
      greys; otherwise it is the reading text's, and a size in points is
      converted with the dataset DPI (px = pt × DPI ÷ 72);
    * *Font* — the font family and the *Multilingual* stack;
    * *Color* — the text colour, then the plot background (and its custom
      colour, greyed unless *Custom…* is picked).

    ``disabled`` greys every row while the Text layer is off (UX-97's contract:
    the settings stay readable, and their stored values are untouched).
    Returns ``(base_font_size, font_family, line_spacing, scale_text_to_boxes)``.
    """
    off_reason = (
        f"{ICONS['warning']} **Text** is off — turn it on to change this. Your "
        "settings are kept either way."
        if disabled
        else ""
    )

    def tip(text: str) -> str:
        return f"{off_reason}\n\n{text}" if off_reason else text

    with host:
        fit = _sub_row(
            "Fit",
            section=section,
            section_help="How the reading text is drawn.",
            caption_help=tip(
                "**Scale to boxes** sizes the text from the word-box height "
                "(text height = box height ÷ line spacing), so it fills the real "
                "line slot and scales with the figure. The spacing beside it is "
                "how many line slots one box spans — OneStop uses 3. Untick to "
                "set a fixed size below."
            ),
        )
        fit_col, spacing_cap_col, spacing_col = fit.columns(
            [0.55, 0.2, 0.25], gap=_LABEL_GAP, vertical_alignment="center"
        )
        scale_text_to_boxes = fit_col.checkbox(
            "Scale to boxes",
            key="global_scale_text_to_boxes",
            persist_state="session",
            disabled=disabled,
        )
        _sub_caption(spacing_cap_col, "Spacing")
        line_spacing = spacing_col.number_input(
            "Line spacing",
            min_value=1.0,
            max_value=10.0,
            step=0.5,
            key="global_line_spacing",
            persist_state="session",
            disabled=disabled or not scale_text_to_boxes,
            label_visibility="collapsed",
        )

        size = _sub_row(
            "Size",
            caption_help=tip(
                "With **Scale to boxes** on, this is the axis, legend and "
                "fallback text size in px. Off, it is the reading text's size — "
                "in px, or in points converted with the dataset DPI "
                "(px = pt × DPI ÷ 72)."
            ),
        )
        unit_col, size_col = size.columns(
            [0.5, 0.5], gap=_LABEL_GAP, vertical_alignment="center"
        )
        use_pt = unit_col.segmented_control(
            "Font unit",
            options=[False, True],
            format_func=lambda use_pt: "pt" if use_pt else "px",
            key="global_use_stimulus_font_pt",
            persist_state="session",
            disabled=disabled or scale_text_to_boxes,
            label_visibility="collapsed",
        )
        if not scale_text_to_boxes and use_pt:
            stimulus_font_pt = size_col.number_input(
                "Font size (pt)",
                min_value=4.0,
                max_value=144.0,
                step=0.5,
                key="global_stimulus_font_pt",
                persist_state="session",
                disabled=disabled,
                label_visibility="collapsed",
            )
            st.session_state["global_base_font_size"] = int(
                min(max(round(font_pt_to_px(stimulus_font_pt, display_dpi)), 6), 72)
            )
            base_font_size = int(st.session_state["global_base_font_size"])
        else:
            base_font_size = size_col.number_input(
                "Plot font size (px)" if scale_text_to_boxes else "Font size (px)",
                min_value=6,
                max_value=72,
                step=1,
                key="global_base_font_size",
                persist_state="session",
                disabled=disabled,
                label_visibility="collapsed",
            )

        font = _sub_row(
            "Font",
            caption_help=tip(
                "The font for the word labels — the exact font from your "
                "experiment (e.g. 'Courier New') or a CSS fallback stack. "
                "**Multilingual** fills in a CJK / Hebrew / Arabic-capable stack "
                "(PRE-6)."
            ),
        )
        family_col, stack_col = font.columns(
            [0.6, 0.4], gap=_LABEL_GAP, vertical_alignment="center"
        )
        font_family = family_col.text_input(
            "Text font",
            key="global_font_family",
            persist_state="session",
            disabled=disabled,
            label_visibility="collapsed",
        )
        stack_col.button(
            "Multilingual",
            on_click=lambda: st.session_state.update(
                global_font_family=_MULTILINGUAL_FONT_STACK
            ),
            disabled=disabled,
            width="stretch",
        )

        # Seeded rather than given a `value=`: restored pre-widget by a deep
        # link / saved config (BUG-17). `seed_canvas_state` pins it too, so a
        # custom background survives the runs this picker is greyed.
        _pin("global_bg_custom", DEFAULT_BACKGROUND_COLOR)
        color = _sub_row(
            "Color",
            caption_help=tip(
                "The reading text's colour, then the background of the plotting "
                "area (and of exported figures) — with its own colour when "
                "*Custom…* is picked."
            ),
        )
        text_color_col, bg_cap_col, bg_col, bg_custom_col = color.columns(
            [0.17, 0.33, 0.33, 0.17], gap=_LABEL_GAP, vertical_alignment="center"
        )
        text_color_col.color_picker(
            "Text color",
            key="global_text_color",
            persist_state="session",
            disabled=disabled,
            label_visibility="collapsed",
        )
        _sub_caption(bg_cap_col, "Background")
        bg_choice = bg_col.selectbox(
            "Plot background",
            options=list(BACKGROUND_PRESETS.keys()) + ["Custom…"],
            key="global_bg_choice",
            persist_state="session",
            disabled=disabled,
            label_visibility="collapsed",
        )
        bg_custom_col.color_picker(
            "Custom background color",
            key="global_bg_custom",
            persist_state="session",
            disabled=disabled or bg_choice != "Custom…",
            label_visibility="collapsed",
        )

        if "right_to_left" in words_filtered and words_filtered["right_to_left"].any():
            st.caption(
                "↔ RTL script detected. Landing positions are measured from the "
                "logical word start; browser bidi shaping is used for labels."
            )
        hint = _stimulus_font_install_hint(font_css)
        if hint is not None:
            font_name, font_url = hint
            st.caption(
                f"{ICONS['info']} This corpus was rendered in **{font_name}**. For "
                "the overlaid text to match the stimulus image exactly, install "
                "that font (it isn't bundled), then reload — otherwise labels "
                f"(especially URLs / Latin) can drift. [Download]({font_url}). Or "
                "turn on the stimulus **Image** to read the original text."
            )
    line_spacing_value = (
        float(line_spacing)
        if line_spacing is not None
        else float(st.session_state.get("global_line_spacing", seeded[4]))
    )
    return (
        int(base_font_size),
        str(font_family),
        line_spacing_value,
        bool(scale_text_to_boxes),
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
    text_disabled: bool = False,
    text_section: str | None = None,
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

    **UX-163/164 — in ``bare`` mode the rows take the rail popovers' shape.**
    The monitor's width and height share one ``Monitor | W × H px`` row, and the
    typography is four captioned rows — *Fit*, *Size*, *Font*, *Color* — under
    the 📄 Stimulus popover's *Text* row (`_rail_text_rows`). ``text_disabled``
    greys them while the Text layer is off, rather than leaving them undrawn;
    ``text_section`` titles the group where no *Text* row precedes it (the
    Corpus figure-style panel). The wizard's standalone form is unchanged.

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
    if bare:
        canvas_width, canvas_height = _rail_monitor_row(screen)
    else:
        canvas_width = field(
            screen,
            "number_input",
            "Monitor width (px)",
            min_value=100,
            max_value=10000,
            step=10,
            help="Use the real monitor width in pixels to keep coordinates true "
            "to scale.",
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
            help="Use the real monitor height in pixels to keep coordinates true "
            "to scale.",
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
        + (
            f"  ·  set in {ICONS['view_data']} Data Management → Recording setup."
            if bare
            else ""
        )
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

    if bare:
        base_font_size, font_family, line_spacing, scale_text_to_boxes = (
            _rail_text_rows(
                text,
                seeded=seeded,
                display_dpi=float(display_dpi),
                words_filtered=words_filtered,
                font_css=font_css,
                disabled=text_disabled,
                section=text_section,
            )
        )
        return (
            int(canvas_width),
            int(canvas_height),
            int(base_font_size),
            font_family,
            float(line_spacing),
            bool(scale_text_to_boxes),
        )

    # --- 🔤 Text & fonts (the wizard's flat form) -------------------------
    # Reading text is true-to-scale by default: it auto-sizes to the word boxes
    # (text height = box_height / line_spacing) and scales with the figure, so it
    # always fills the real line slot. Untick to fall back to a fixed font size.
    # Keyed (+ seeded) so the settings file can capture/reapply them.
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
            f"{ICONS['info']} This corpus was rendered in **{font_name}**. For the overlaid text "
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
        destructive_change,
        event_problems,
        layout_problems,
        layout_text,
        parse_authoring_document,
        reconcile_event_table,
        stale_target_words,
        unresolved_targets,
        unusable_event_rows,
    )
    from scanpath_studio.authoring_component import render_authoring_canvas

    source = st.session_state.get("data_source_choice", AUTHOR_CHOICE)
    drafts = st.session_state.setdefault("_manual_scanpath_drafts", {})
    previous = st.session_state.get("_author_editor_source")
    if previous != source:
        document = drafts.get(source)
        if document is None and (
            source == MANUAL_SAMPLE_CHOICE or previous is not None
        ):
            seed_text = (
                _MANUAL_SAMPLE_TEXT
                if source == MANUAL_SAMPLE_CHOICE
                else "Reading unfolds through a sequence of careful eye movements."
            )
            document = (
                seed_text,
                dict(DEFAULT_LAYOUT),
                default_events(layout_text(seed_text)),
            )
        if document is not None:
            seed_text, seed_layout, seed_events = document
            st.session_state["author_text"] = seed_text
            st.session_state["_author_layout"] = seed_layout
            st.session_state["_authored_events_frame"] = seed_events
            st.session_state["_author_text_for_events"] = seed_text
            st.session_state["_author_selected_fixation"] = None
            st.session_state["_author_events_editor_revision"] = (
                int(st.session_state.get("_author_events_editor_revision", 0)) + 1
            )
        st.session_state["_author_editor_source"] = source
    header = st.container(horizontal=True, vertical_alignment="center")
    header.subheader(
        f"{ICONS['author']} "
        + (
            "Edit synthetic sample"
            if source == MANUAL_SAMPLE_CHOICE
            else "Author a scanpath"
        )
    )
    header.button("Cancel", key="cancel_authoring", on_click=_cancel_authoring)
    st.caption(
        "Write the stimulus, then click or drag directly on the canvas. X/Y are "
        "the primary authored values; the optional target word is useful for "
        "measures but does not constrain where a fixation can be placed. The "
        "numeric table remains a complete keyboard-accessible editor."
    )
    restored = st.file_uploader(
        "Restore authoring file",
        type=["json"],
        key=f"author_restore_upload_{source}",
        help="Load a JSON file previously saved from this editor.",
        max_upload_size=upload_limit_mb(),
    )
    if restored is not None:
        identity = (source, restored.name, restored.size)
        if st.session_state.get("_author_restore_identity") != identity:
            try:
                document = parse_authoring_document(restored.getvalue().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                st.error(str(exc))
            else:
                # The draft it replaces becomes the previous draft at the end
                # of this run, so Restore previous draft brings it back.
                _load_author_draft(
                    source, (document.text, document.layout, document.events)
                )
                st.session_state["_author_restore_identity"] = identity

    st.session_state.setdefault(
        "author_text", "Reading unfolds through a sequence of careful eye movements."
    )
    text = st.text_area(
        "Stimulus text",
        key="author_text",
        persist_state="session",
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

    events_text = st.session_state.get("_author_text_for_events")
    if events_text is None:
        # A fresh editor: one fixation per word to start from.
        st.session_state.setdefault("_authored_events_frame", default_events(words))
        st.session_state.setdefault("_author_events_editor_revision", 0)
        st.session_state["_author_text_for_events"] = text
    elif events_text != text:
        # Editing the text keeps every authored fixation — id, X/Y, order and
        # duration. Only a target word can go out of date, and that is flagged
        # below rather than regenerated. The current table is the base for the
        # flag: `_authored_events_frame` lags behind the table's own edits.
        previous_draft = drafts.get(source)
        current = previous_draft[2] if previous_draft else None
        stale = st.session_state.setdefault(_AUTHOR_STALE_TARGETS_KEY, {}).setdefault(
            source, {}
        )
        found = stale_target_words(layout_text(events_text, **layout), words, current)
        # An entry already flagged keeps the word it named first, so undoing
        # the edit (or fixing it in two steps) resolves it.
        for fixation_id, entry in found.items():
            stale.setdefault(fixation_id, entry)
        st.session_state["_author_text_for_events"] = text
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
    stale_entries = st.session_state.get(_AUTHOR_STALE_TARGETS_KEY, {}).get(source, {})
    stale = unresolved_targets(stale_entries, words, effective_events)
    if stale_entries and len(stale) < len(stale_entries):
        # Resolved ones (target changed, fixation deleted, text put back) go.
        st.session_state[_AUTHOR_STALE_TARGETS_KEY][source] = {
            fixation_id: stale_entries[fixation_id] for fixation_id in stale
        }
    if stale:
        listed = ", ".join(
            f"fixation {fixation_id} → word {word_id}"
            for fixation_id, word_id in sorted(stale.items())[:8]
        )
        more = f" (+{len(stale) - 8} more)" if len(stale) > 8 else ""
        st.warning(
            f"The text edit changed or removed the target word of "
            f"{len(stale)} {'fixation' if len(stale) == 1 else 'fixations'}: "
            f"{listed}{more}. Their position, timing and order are unchanged. "
            "Set each **Target word** in the Fixation table, or clear them.",
            icon=ICONS["warning"],
        )
        if st.button("Clear those target words", key=f"author_clear_stale_{source}"):
            cleared = effective_events.copy()
            mask = cleared["fixation_id"].map(int).isin(stale)
            cleared["word_id"] = cleared["word_id"].astype(object)
            cleared.loc[mask, "word_id"] = None
            st.session_state["_authored_events_frame"] = cleared
            st.session_state["_author_events_editor_revision"] = editor_revision + 1
            st.session_state[_AUTHOR_STALE_TARGETS_KEY].pop(source, None)
            st.rerun()

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

    fixations = authored_fixations(words, effective_events)
    name_key = f"author_dataset_name_{source}"
    st.text_input(
        "Dataset name",
        value="Synthetic sample (edited)"
        if source == MANUAL_SAMPLE_CHOICE
        else "My scanpath",
        key=name_key,
    )
    can_save = events_valid and not words.empty and not fixations.empty and not dropped
    if can_save:
        st.session_state["_author_save_payload"] = {
            "words": words,
            "fixations": fixations,
            "raw_gaze": pd.DataFrame(),
            "authoring": authoring_json(text, effective_events, layout=layout),
        }
    else:
        st.session_state.pop("_author_save_payload", None)
    actions = st.container(horizontal=True, vertical_alignment="center")
    actions.button(
        "Save dataset",
        icon=ICONS["save"],
        key="save_authored_dataset",
        type="primary",
        disabled=not can_save,
        on_click=_save_authored_dataset,
        args=(name_key,),
    )
    actions.download_button(
        "Download authoring file",
        data=authoring_json(text, effective_events, layout=layout),
        file_name=AUTHORING_FILE_NAME,
        mime="application/json",
        icon=ICONS["download"],
        key=f"author_download_{source}",
        on_click="ignore",
        disabled=not events_valid,
        help=(
            "The editable draft — text, layout and every fixation with its id, "
            "position, order and duration. Load it again with **Restore "
            "authoring file**, or from a script with `load_authored_scanpath`."
        ),
    )
    previous = st.session_state.get(_AUTHOR_PREVIOUS_DRAFT_KEY, {}).get(source)
    actions.button(
        "Restore previous draft",
        icon=ICONS["undo"],
        key=f"author_restore_previous_{source}",
        disabled=previous is None,
        on_click=_restore_previous_author_draft,
        args=(source,),
        help=(
            "Go back to the draft before the last change that removed, moved or "
            "retimed fixations — one step. Press again to return."
        ),
    )
    actions.button(
        "Reset fixations to the text",
        key=f"author_reset_fixations_{source}",
        disabled=words.empty,
        on_click=_reset_author_fixations,
        args=(source, words),
        help=(
            "Replace every fixation with one per word, 220 ms each. "
            "**Restore previous draft** brings the current ones back."
        ),
    )
    draft = (text, dict(layout), effective_events.copy())
    last = drafts.get(source)
    if events_valid and last is not None and destructive_change(last[2], draft[2]):
        st.session_state.setdefault(_AUTHOR_PREVIOUS_DRAFT_KEY, {})[source] = last
    drafts[source] = draft
    return words, fixations


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
    apply_pending_preprocessing()
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
    if st.session_state.get(_AUTHOR_EDITING_KEY) != data_choice:
        st.session_state.pop(_AUTHOR_EDITING_KEY, None)
    if not _authoring_editor_open(data_choice):
        st.session_state.pop("_author_editor_source", None)
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


#: UX-168: the last dataset a run left on screen — where Cancel goes back to
#: (`_remember_open_dataset`). Not the wizard's `_prev_source`, which only
#: records where leaving the add-dataset wizard returns to.
LAST_LOADED_SOURCE_KEY = "_sps_last_loaded_source"
#: UX-166: the dataset task this session's pipeline is running, set when the
#: card opens and cleared when it ends; found still set by the next run, it
#: means that run was abandoned mid-load.
DATASET_TASK_KEY = "_sps_dataset_task"
#: UX-168: set by Cancel on the dataset card, read once by the next run's notice.
CANCELLED_LOAD_KEY = "_sps_cancelled_load"


def _dataset_cancel(token: str, task_key: tuple) -> loading.Cancel | None:
    """The dataset card's Cancel: only for a load the user started — cold, or
    by switching away from what was already on screen.

    **T8-2:** the last dataset a run left on screen (`_remember_open_dataset`)
    is where Cancel goes back to, but a rerun of **that same dataset** (a filter
    change, a re-normalization, a slow step on ✏️ Edit dataset) must offer none
    at all — there is nothing the user asked to leave, and clicking it would
    abandon the dataset they are looking at. The Bundled demo is the fallback
    only when no dataset has been on screen yet this session, never back to
    `token` itself either way.

    **T8-5:** `back` must also be a dataset this run can actually open —
    `resolve_data_source` heals a stale/hidden/removed selection to
    `entries[0]` (published as `_data_source_entries`, before this runs), so a
    button still reading "Back to <back>" could silently reopen something else.
    Falls back to the demo when it is offered and isn't `token`, else no
    Cancel.
    """
    last = st.session_state.get(LAST_LOADED_SOURCE_KEY)
    if last == token:
        return None
    back = last or DEMO_CHOICE
    if back == token:
        return None
    entries = st.session_state.get("_data_source_entries") or ()
    if back not in entries:
        if DEMO_CHOICE not in entries or DEMO_CHOICE == token:
            return None
        back = DEMO_CHOICE
    return loading.Cancel(
        f"Back to {_dataset_display_name(back)}",
        _cancel_dataset_load,
        args=(task_key, token, _dataset_display_name(token), back),
    )


def _cancel_dataset_load(task_key: tuple, token: str, name: str, back: str) -> None:
    """UX-168: Cancel on the dataset card — stop the load, reopen ``back``."""
    progress.cancel(task_key)
    st.session_state["_pending_source_choice"] = back
    st.session_state[CANCELLED_LOAD_KEY] = {"token": token, "name": name}


def _retry_load(token: str) -> None:
    st.session_state["_pending_source_choice"] = token


def _render_cancelled_load_notice(host) -> None:
    """UX-168: "Stopped loading X · Try again", once, where the notices go."""
    note = st.session_state.pop(CANCELLED_LOAD_KEY, None)
    if not note:
        return
    row = host.container(
        key="sps_cancelled_notice", horizontal=True, vertical_alignment="center"
    )
    # As wide as its words, so Try again sits beside them, not across the page.
    row.caption(f"Stopped loading **{note['name']}**.", width="content")
    row.button(
        "Try again",
        key="sps_try_again",
        on_click=_retry_load,
        args=(note["token"],),
        type="tertiary",
    )


#: UX-199: ``"show"`` once the first upload lands on a deployment that keeps
#: nothing, ``"dismissed"`` once the user closes the reminder — which keeps it
#: down for the rest of the session, later uploads included. UI-only, so it is
#: not wire format and no link or saved file carries it.
BACKUP_REMINDER_KEY = "_sps_backup_reminder"

#: Where the docs list what to download, and from where, to keep your work.
BACKUP_GUIDE_URL = f"{CITATION['docs_url']}guides/outputs-sharing/#back-up-your-work"


def arm_backup_reminder() -> None:
    """Ask for the backup reminder after an upload, where nothing is saved (UX-199).

    Called from the wizard's ✅ Add dataset callback. *Saved on this computer*
    says the same thing at the foot of the 🗂️ Data page, where a hosted user
    working in Scanpath may never look — so the first upload, the moment there
    is something to lose, says it in the notices strip on every view.
    """
    if st.session_state.get(BACKUP_REMINDER_KEY) == "dismissed":
        return
    if persistence_enabled(str(getattr(st.context, "url", "") or "")):
        return
    st.session_state[BACKUP_REMINDER_KEY] = "show"


def _dismiss_backup_reminder() -> None:
    st.session_state[BACKUP_REMINDER_KEY] = "dismissed"


def _render_backup_reminder(host, active_view: str) -> None:
    """UX-199: the dismissible "nothing is saved here" reminder, in the notices."""
    if st.session_state.get(BACKUP_REMINDER_KEY) != "show":
        return
    box = host.container(key="sps_backup_reminder", border=True)
    box.markdown(
        f"{ICONS['warning']} **This deployment saves nothing.** Closing or "
        "refreshing the tab loses the datasets you added, their column mappings "
        "and your annotations. Keep the files you uploaded, and export your "
        f"annotations from {ICONS['view_data']} **Data Management → Annotations** and each "
        "dataset's mapping from "
        f"{ICONS['edit']} **Edit dataset → Save setup**. "
        f"[What to back up ↗]({BACKUP_GUIDE_URL})"
    )
    row = box.container(horizontal=True, gap="small")
    if active_view != _VIEW_DATA:
        row.button(
            "Open Data Management",
            key="sps_backup_reminder_go",
            icon=ICONS["view_data"],
            on_click=_go_data,
            type="tertiary",
        )
    row.button(
        "Dismiss",
        key="sps_backup_reminder_dismiss",
        icon=ICONS["close"],
        on_click=_dismiss_backup_reminder,
        type="tertiary",
    )


def _open_dataset_card(
    page: loading.Page,
    data_choice: str,
    *,
    view: str,
    view_switched: bool,
    finalizing: bool,
) -> loading.Card | None:
    """UX-166: this run's dataset card, or ``None`` when there is no load to wait on.

    A switch to ``view`` opens the task-less "Opening <view>" card at once,
    titled for the view and without steps, **only when no load was already in
    flight** (``in_flight`` below): the dataset is loaded already, so the
    skeleton is what answers the click, and each switch's task is its own
    (never joined by a load's task, nor joining one — nor a later switch to the
    same view, which must never join a stale one either). **T8-3:** a view
    switch that instead lands on an in-flight load — the previous run's, or one
    a dataset pick in the same click just started — opens the ordinary dataset
    card instead (steps, Cancel, the explicit `task_key`, so it joins that
    load), revealed at once rather than task-less: a load's own progress and
    Cancel must never be hidden behind the view-switch skeleton. `DATASET_TASK_KEY`
    still names the dataset's either way — a view switch in the middle of a
    load is not "another dataset".

    **In flight** means a live, unfinished task still holds the key
    (`progress.running`), not just that the key is set: a run that ended by
    ``st.stop()``, an exception or ``st.rerun()`` mid-pipeline leaves
    `DATASET_TASK_KEY` behind with nothing computing it, and a view switch after
    that would otherwise show a load's card — steps, Cancel, revealed at once —
    for no load at all.

    **UX-168:** a run that finds *another* dataset's task still marked running
    under `DATASET_TASK_KEY` was started by picking this one mid-load (directly,
    or via Cancel) — the user changed their mind, so the abandoned load is
    cancelled here, at its next checkpoint, instead of competing for the CPU.
    Checked before the early return below too: switching to Upload or Author
    mid-load cancels a load left running just the same, and that branch has no
    load of its own to name `DATASET_TASK_KEY` after, so it clears the key
    rather than replacing it.

    **The load card is gated** (``reveal_on_work``): it opens on every run, and
    a plain rerun — every build a cache hit — can outlast the delay on a big
    corpus, re-hashing the frames each hit hands back; shown, it blanked the
    view to the skeleton on every widget touch. So it shows only once one of
    its builds has reported, i.e. missed. ``reveal_now`` still shows it at once.

    **A rerun of the dataset on screen is an update:** "Updating <dataset>",
    with no Cancel, no "last load" hint and no duration recorded — a filter
    change's re-run is not how long the dataset takes to open.
    """
    if data_choice == UPLOAD_CHOICE or _authoring_editor_open(data_choice):
        previous = st.session_state.pop(DATASET_TASK_KEY, None)
        if previous is not None:
            progress.cancel(tuple(previous))
        return None
    token = str(st.session_state.get("data_source_choice") or data_choice)
    session = loading.session_id()
    task_key = ("dataset", session, token)
    previous = st.session_state.get(DATASET_TASK_KEY)
    in_flight = previous is not None and progress.running(tuple(previous))
    if previous is not None and tuple(previous) != task_key:
        progress.cancel(tuple(previous))
    st.session_state[DATASET_TASK_KEY] = task_key
    if view_switched and not in_flight:
        return page.open_card(
            title=f"Opening {view_label(view)}",
            reveal_now=True,
        )
    stored = data_choice in st.session_state.get("_datasets", {})
    steps = (
        ("Building the trial list",)
        if stored
        else ("Reading files", "Normalizing", "Building the trial list")
    )
    # UX-166: the dataset already on screen, run again — a filter change on a
    # big corpus, a re-normalization — is an update, not a load: titled so, with
    # no "last load" hint and no duration of its own, since an update's time
    # must never stand in for how long the dataset took to open. (It offers no
    # Cancel either — `_dataset_cancel`'s T8-2 rule, the same test.) A dataset
    # just added is always a load: the wizard, not a dataset, was on screen.
    updating = not finalizing and st.session_state.get(LAST_LOADED_SOURCE_KEY) == token
    return page.open_card(
        title=f"{'Updating' if updating else 'Loading'} {_dataset_display_name(token)}",
        steps=steps,
        cancel=_dataset_cancel(token, task_key),
        task_key=task_key,
        duration_key=None if updating else ("dataset", token),
        reveal_now=finalizing or view_switched,
        reveal_on_work=True,
    )


def _remember_open_dataset(data_choice: str) -> None:
    """UX-168: the dataset this run leaves on screen is where Cancel goes back to.

    Recorded on every path that leaves a dataset showing, not only a finished
    pipeline: the ✏️ Author editor (which opens no card), a dataset whose
    mapping still needs fixing, one whose filters left no trials — "Back to"
    must name the dataset you had open, not one further back. Never for the
    add-dataset wizard (``UPLOAD_CHOICE``), which shows no dataset and has its
    own way back (`_prev_source`). The value is the dataset card's own token.
    """
    if data_choice == UPLOAD_CHOICE:
        return
    st.session_state[LAST_LOADED_SOURCE_KEY] = str(
        st.session_state.get("data_source_choice") or data_choice
    )


def _finish_dataset_card(card: loading.Card | None, data_choice: str) -> None:
    """UX-166: the pipeline finished — every step ✓, the skeleton left up — and
    the dataset is on screen (`_remember_open_dataset`), card or none."""
    if card is not None:
        card.finish()
        card.close(keep=True)
        st.session_state.pop(DATASET_TASK_KEY, None)
    _remember_open_dataset(data_choice)


def main() -> None:
    """Main application entry point: one script run, inside a loading scope.

    UX-165: ``loading.run_scope`` guarantees that no loading card's timer thread
    outlives the run that started it — whether the run ends normally, returns
    early, raises, or is abandoned by a click — and ends a run whose work was
    cancelled as a stopped one, which keeps the state of the widgets it never
    reached. The run itself is `_run_app`.
    """
    with loading.run_scope():
        _run_app()


def _run_app() -> None:
    """One script run, top to bottom (``main`` wraps it in a loading scope).

    1. Page setup: config and CSS, the URL presets, and the recovery-cache
       restore — under a card of its own until the session has restored.
    2. Chrome: the top nav resolves the active view; then the menu bar, the
       title and the tours and dialogs.
    3. Reserved slots, in screen order: the view area the Scanpath and Corpus
       views render into, then the 🗂️ Data page's overview and editor slots.
    4. The dataset pipeline, under the dataset card: load → normalize →
       filter → the trial list. It returns early, through ``_end_loading``, for
       an open add-dataset wizard, a mapping that can't be satisfied, or a
       filter that empties the pool.
    5. The active view: 🗺️ Scanpath or 📊 Corpus Analysis inside the view
       area, or the Data page's slots filled.
    6. The epilogue: the recovery-cache save, then the Data page's *Saved on
       this computer* section.
    """
    configure_page()
    # PERF-3: the cache-key memo is scoped to ONE script run — drop last run's
    # entries before anything fingerprints a frame, so a frame rebuilt this run
    # is hashed afresh and last run's frames stop being kept alive.
    reset_fingerprint_memo()
    # BUG-103: every stored dataset's tables, open or not — the Data page counts
    # them all — are held run after run and never written into, so each is
    # hashed once rather than on every rerun, however it entered the store
    # (the wizard, ✏️ Edit dataset, the recovery cache, a repair).
    for stored in (st.session_state.get("_datasets") or {}).values():
        if isinstance(stored, dict):
            vouch_for_frames(
                tuple(stored.get(t) for t in ("words", "fixations", "raw_gaze"))
            )
    st.session_state[_PLACEHOLDER_SHOWN_KEY] = False
    # BUG-96: the missing-corpus note describes the run that wrote it. It is
    # consumed later in that run, but a run that leaves before then — a mapping
    # the demo stand-in can't satisfy, a stopped or abandoned run — used to hand
    # it to the next run, which showed it over another dataset and hid the
    # dataset card's row counts.
    st.session_state.pop(_UNAVAILABLE_KEY, None)
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
    # UX-166: restoring large uploads reads their Parquet files before even the
    # title is drawn, so it gets a card of its own at the very top of the page —
    # only while there is something to restore: once the session has had its
    # one attempt the call returns at once, and a card around it would cost
    # every run a timer thread and a task for nothing. Its slot is held on every
    # run either way (UX-167: one element fewer here would shift the view).
    restore_slot = st.empty()
    restoring = (
        contextlib.nullcontext()
        if local_state_restored(st.session_state)
        else loading.card(
            restore_slot,
            key="restore",
            title="Restoring your datasets from this computer",
        )
    )
    with restoring:
        restored = restore_local_state(
            st.session_state, app_url, protect_data_source=url_source is not None
        )
    # UX-167: Streamlit matches a rerun's elements to the last run's by position,
    # so a notice that shows on one run only (the unavailable-link warning below)
    # must not move the page under it — it writes into this container, drawn on
    # every run. The toasts need no slot: `st.toast` draws in Streamlit's event
    # container, outside the page.
    page_notices = st.container()
    if restored:
        # ENG-30: say it once, where the user is looking. Silently repopulating a
        # session reads as "the app kept my data somewhere" without saying where;
        # the toast points at the menu panel that answers that.
        #
        # UX-136: `restore_local_state` is true only when something the user
        # would *recognise* came back — a dataset, an annotation, a saved design.
        # Every rerun writes the cache, so a session that only ever changed view
        # settings still leaves a manifest, and announcing that as "your last
        # session" was wrong in the one case where it is most alarming: right
        # after the user cleared the cache by hand. Naming the counts is what
        # makes the claim checkable against the panel it points at.
        st.toast(
            f"Recovered {_restored_recap()} from this computer — see {ICONS['view_data']} Data Management → "
            "Saved on this computer.",
            icon=ICONS["recovery"],
        )
    elif consume_restore_skipped(st.session_state):
        # BUG-71: the last launch that restored the cache never finished, so this
        # one opened without it rather than failing the same way again.
        st.toast(
            "Your last session didn't finish opening, so it wasn't restored this "
            "time. It is still saved on this computer and saving is paused, so it "
            "stays that way: reload to try again, or delete it with "
            "`scanpath-studio cache --clear`.",
            icon=ICONS["warning"],
            duration="long",
        )
    # A cache that is there but did not all come back says so on every run
    # until it is retried or removed — never silently, and never by replacing
    # it (the held-back parts are kept by every save).
    render_cache_recovery_notice(page_notices, app_url, key="cache_recovery")
    linked_choice = None
    if url_source == "onestop" and onestop_data_dir() is not None:
        linked_choice = st.session_state.setdefault(
            "data_source_choice", ONESTOP_CHOICE
        )
    elif url_source == "multipleye" and multipleye_bundle_dir() is not None:
        linked_choice = st.session_state.setdefault(
            "data_source_choice", MULTIPLEYE_BUNDLE_CHOICE
        )
    elif url_source == "demo":
        linked_choice = st.session_state.setdefault("data_source_choice", DEMO_CHOICE)
    elif url_source == "synthetic":
        linked_choice = st.session_state.setdefault(
            "data_source_choice", SYNTHETIC_CHOICE
        )
    elif url_source == "author":
        linked_choice = st.session_state.setdefault("data_source_choice", AUTHOR_CHOICE)
    elif (
        url_source in ONESTOP_REGIME_TOKEN_CHOICES
        or url_source == ONESTOP_LEGACY_SOURCE_TOKEN
    ) and public_datasets_enabled():
        # DATA-3: the public OneStop corpus is shareable. DATA-63: one dataset
        # per regime, each its own token; a DATA-3 link's `onestop_public` names
        # its regime in `onestop_regime` (seeded by _apply_url_preset).
        regime = st.session_state.get("onestop_regime")
        linked_choice = st.session_state.setdefault(
            "data_source_choice",
            ONESTOP_REGIME_TOKEN_CHOICES.get(url_source)
            or ONESTOP_REGIME_CHOICES.get(regime, ONESTOP_REGIME_CHOICES["ordinary"]),
        )
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
            linked_choice = st.session_state.setdefault(
                "data_source_choice", corpus_choice
            )
        elif slug:
            # The common case, not an edge case: the recipient has no prepared
            # bundle, or a different subset of one. Say which corpus was named
            # and leave the picker exactly where it was — never wedge it, and
            # never silently open a different corpus. There is no remedy to name
            # (DATA-55): the app no longer discovers corpora, and until DATA-56's
            # add-from-a-folder flow nothing in it adds one.
            page_notices.warning(
                f"This link opens the corpus `{slug}`, which isn't available "
                "here. The link's view settings still apply to whatever you open."
            )
    elif url_source == "upload":
        st.session_state.setdefault("_show_upload_wizard", True)
    # EXP-19: the canvas / font a link seeded belong to the source it names.
    # Scope their protection from the source snap to that source — or drop it
    # when the link named none this app can open, so the fallback source still
    # snaps to its own monitor rather than wearing another corpus' canvas.
    scope_link_setup(linked_choice)

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
    # wizard hold-override below can land before that call rather than after it.
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
    # BUG-36 follow-up: resolved here, before `render_top_menu`, and handed in
    # as `active_view=`, so everything drawn after it agrees on the view.
    if st.session_state.get("_show_upload_wizard"):
        if (
            active_view != _VIEW_DATA
            and st.session_state.get(WIZARD_STAY_KEY) != active_view
        ):
            st.session_state[WIZARD_LEAVE_KEY] = active_view
        else:
            st.session_state.pop(WIZARD_LEAVE_KEY, None)
        active_view = _VIEW_DATA

    menu = render_top_menu(active_view=active_view)
    _render_about_panel(menu.title)
    _render_cancelled_load_notice(menu.notices)
    _render_backup_reminder(menu.notices, active_view)

    def _finish_page() -> None:
        """The run's last UI, once, on whichever path ``main`` leaves by.

        🗂️ Data → *Saved on this computer* reports what **this run** just
        persisted, so it has to come after `save_local_state` — which the early
        returns never reach. Each of them calls this instead, and the epilogue
        calls it for the ordinary path, so exactly one runs per script run.
        That is what keeps its widgets single.

        The section is drawn only while the overview is on screen: not on the
        other views, not under ✏️ Edit dataset, and not while the add-dataset
        wizard owns the page.
        """
        if data_view and not editing and not wizard_owns_page:
            _render_download_folder_section(download_folder_slot)
            _render_saved_here_section(app_url, saved_here_slot)

    # First-visit welcome tour. After the URL presets, so embeds and
    # deep-linked sessions can suppress it — but BEFORE the heavy data/plot
    # work, so the welcome streams to the browser immediately instead of
    # after the full first render. Replay clicks arm the tour in the button's
    # on_click callback, which runs before this point in the rerun.
    #
    # UX-167: one container for the whole block, so it always holds exactly one
    # index below it — `render_easter_egg()` is the case that bit: it draws a
    # bare iframe except while a tour or tutorial is active, so the first run
    # after one closes used to insert an element above the view and shift it.
    # See scanpath_studio/CLAUDE.md → Gotchas.
    with st.container():
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
        # UX-196: a cut-off dropdown label shows in full on hover. Unconditional,
        # so it never moves the view's index (UX-167).
        render_truncation_tooltips()
        # UX-15: same deal for the FAQ dialog — the ❓ Help menu button that arms it
        # renders at the bottom of this function, so serving it here is what keeps
        # the modal from waiting out the whole rerun. Ditto ℹ️ About, a dialog since
        # the menu bar made it a popover inside a popover.
        maybe_show_faq()
        maybe_show_about()
        maybe_show_tutorial_library()
        # UX-179 — ❓ Help → Debug, served early like its siblings.
        maybe_show_debug()

    # `active_view` was already resolved above (including the BUG-31 wizard
    # hold-override — see the note there); the dispatch below reuses it.

    # UX-166 — the Scanpath and Corpus views render inside one reserved area.
    # Its first child is the page slot: `loading.Page` fills it with a skeleton
    # of the view and the dataset card while a load is slow, and CSS hides the
    # rest of the area meanwhile — the previous page, or the new one being laid
    # out under it. It replaces the old "Loading <view>…" bridge, which a view
    # switch now shows at once as that view's skeleton. The slot is recreated
    # empty on every run, so nothing it held can outlive the run (BUG-81).
    view_area = st.container(key=loading.VIEW_AREA_KEY)
    view_first_slot = view_area.empty()
    # UX-167: reserved right after the page slot — creation order is screen
    # order, so this is always the view area's second child — and given to the
    # conditional notices below (`view_notices`) so the view's own blocks after
    # them keep their place whether or not a notice draws this run.
    view_notices_slot = view_area.container()
    if active_view == _VIEW_DATA:
        # UX-166: the Data page draws outside the area, so on that view it only
        # ever holds what the previous view left there — until this run ends,
        # the old page, above the new one. This marker hides it (styles.py) for
        # the whole run; it is not the page card's, which the Data page outlives.
        view_first_slot.markdown(
            '<span class="sps-view-hidden" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
    view_switched = st.session_state.get("_last_rendered_view") not in (
        None,
        active_view,
    )
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
    # key for the same reason the page itself is (above). UX-197 made them two
    # *parts* of one page: the overview always shows, and the editor opens
    # under it:
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
    # UX-197: the overview stays on screen while the editor is open, and the
    # editor opens under it, set apart — beta testers lost the dataset's counts
    # and tables the moment they started editing it. Only the editor is
    # switched by key now.
    overview_page = setup_page.container(key=DATA_OVERVIEW_KEY)
    editor_page = setup_page.container(
        key=DATA_EDITOR_KEY if editing else DATA_EDITOR_OFFSCREEN_KEY
    )
    # UX-177 — the page title, then the table of datasets straight under it:
    # no "Available datasets" subheading and no rule between the two, since the
    # page is about nothing else until *What's in the dataset* below.
    if data_view and not wizard_owns_page:
        overview_page.header("Data Management")
    setup_source_slot = overview_page.container()
    # The editor's own header bar — the ✏️ Edit dataset screen's title and its
    # way back, filled below once the dataset's display name is known.
    editor_head_slot = editor_page.container()
    # UX-166: the dataset card's slot on the ✏️ Edit dataset screen, directly
    # under its header bar: opening the editor scrolls the page down to it
    # (UX-197), so that is where the user is looking.
    editor_loading_slot = editor_page.empty()
    # UX-135 — the editor's sections are the add screen's numbered *parts*, not
    # a `st.divider()` + `st.subheader()` + `st.caption()` stack. `_editor_part`
    # below draws one headline into each of the slots reserved here; the
    # registry, the numbering and the hover note are `wizard_shell.EDITOR_STEPS`.
    #
    # Part 2 (Data tables & column mapping) opens above the public loader's
    # captions because everything down to the metadata tables belongs to it —
    # where the files are, how their columns map, and what is attached to them
    # — exactly as the add screen's part 2 holds every upload and mapping row.
    # UX-178 — part 1 is the add screen's: Name & description.
    editor_part_name_slot = editor_page.container()
    editor_part_data_slot = editor_page.container()
    description_slot = editor_page.container()
    source_options_slot = editor_page.container()
    data_location_slot = editor_page.container()
    # UX-106 — "add the AOI/fixations table this dataset was created without"
    # is an *upload*, and the add screen puts every upload above the mapping.
    # Reserved here so it renders there; filled from `_render_remap_editor`,
    # which runs much later (creation order is screen order, so the two need
    # not agree).
    editor_uploads_slot = editor_page.container()
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
    # UX-179 — *Saved on this computer*, the overview's last section: the
    # recovery cache and the two ways to throw work away. Filled by
    # `_finish_page`, after this run's `save_local_state`.
    download_folder_slot = overview_page.container(key="data_download_folder")
    saved_here_slot = overview_page.container(key="data_saved_here")
    # Keyed → the stable `.st-key-…` selectors the "Load and verify a dataset"
    # tutorial spotlights (UX-40), alongside `tutorial_data_inspection` above.
    column_mapping_slot = editor_page.container(key="tutorial_column_mapping")
    mapping_body_slot = column_mapping_slot.container()
    # Raw tables for a dataset whose mapping is still broken. Its own slot,
    # *below* the mapping editor, which is the control that fixes them.
    unmapped_slot = editor_page.container()
    # DATA-20 §1 — the participant/trial/text metadata tables. After the mapping
    # (they join on the reader id the mapping just settled), and — UX-135 —
    # *inside* part 1 with it, under their own small **Metadata** heading, which
    # is exactly where the add screen puts the same three uploaders.
    setup_metadata_slot = editor_page.container(key="tutorial_participant_metadata")
    # UX-135 — Recording setup is the add screen's part 3, so it is the editor's
    # own numbered part too rather than a `##### ` heading buried at the end of
    # the mapping form. Filled from `tabs._render_column_mapping_section`, which
    # is handed this slot: it is the same renderer either way, only re-hosted.
    setup_recording_slot = editor_page.container(key="tutorial_recording_setup")
    # UX-52 round 3 — the VAL-7 trial-identity verdict is its own section, not a
    # `#####` item inside "What's in this dataset" (the user's call). It carries
    # a *verdict* — sometimes a warning — and the fix it names is a change to the
    # Trial ID mapping directly above it, so it belongs at the same level as the
    # thing it judges rather than buried under the counts.
    # Keyed → the `.st-key-…` selector the "Load and verify a dataset" tutorial
    # spotlights, alongside its siblings above and below.
    setup_identity_slot = editor_page.container(key="tutorial_trial_identity")
    # VIZ-14: local stimulus-image paths, after the questions that describe the
    # data itself.
    setup_stimulus_slot = editor_page.container(key="tutorial_stimulus_images")
    setup_preproc_slot = editor_page.container(key="tutorial_preprocessing")
    # UX-106 — the editor's own foot: ✅ Save changes, under everything it
    # saves, the way ✅ Add dataset sits under the whole add screen. Reserved
    # last so it lands after preprocessing; filled at the end of the run.
    editor_footer_slot = editor_page.container(key="dataset_editor_footer")

    # UX-135 — which of the editor's five parts are on screen this run, and so
    # what each one is numbered. Two are conditional (stimulus images need a
    # local filesystem; preprocessing is behind PRE-22's flag), and a screen
    # reading 1 · 2 · 3 · 5 looks like a section that failed to render rather
    # than one that does not apply here.
    _editor_shown = {"edit_name", "edit_data", "edit_setup", "edit_identity"}
    if local_filesystem_enabled():
        _editor_shown.add("edit_stimulus")
    if preprocessing_enabled():
        _editor_shown.add("edit_preproc")
    editor_parts = wizard_shell.numbered(wizard_shell.EDITOR_STEPS, _editor_shown)

    def _editor_part(host, step_id: str):
        """One numbered editor part's headline; returns the body to fill.

        The add screen's `wizard_shell.part`, verbatim — same chip, same rule
        above it, same hover note — so the two screens read as one screen before
        and after the dataset exists.
        """
        step = editor_parts[step_id]
        return wizard_shell.part(host, step, note=step.caption)

    # Data source selection. UX-25: only the *resolution* happens here (it must
    # precede the load); the picker itself renders in the main view — on the
    # Scanpath "Filter by" row, at the top of the Corpus view, or (DATA-26) in
    # the page slot above. The resolver takes the same slot because while the
    # add-dataset wizard is open it renders a "✕ Cancel" bar *instead of* a
    # picker, and rendering both would duplicate the `tour_grp_data_source` key.
    from scanpath_studio.wizard import _enter_add_data_wizard

    data_choice = resolve_data_source(host=setup_source_slot)
    # DATA-47 — the metadata tables belong to a dataset. Swap the selected one's
    # onto the session keys every consumer reads (`metadata.active()` & co.),
    # filing the previous dataset's away. Keyed by the concrete canonical choice
    # the dataset table uses, not `data_choice` — every public corpus loads
    # through one category token, and they must not share a table. The add
    # wizard's dataset has no name yet, so it gets the pending slot.
    # DATA-48 — and so do the annotations, swapped by the same key.
    import scanpath_studio.annotations as _annotations
    from scanpath_studio import metadata as _metadata

    _dataset_owner = (
        _metadata.PENDING_DATASET
        if data_choice == UPLOAD_CHOICE
        else str(st.session_state.get("data_source_choice") or data_choice)
    )
    # A cancelled edit's metadata tables go back first, to the dataset they
    # were taken from, before the swap below files them away.
    apply_editor_restore()
    _metadata.activate_dataset(st.session_state, _dataset_owner)
    # Adoption of an old cache's unassigned entries waits for the load, which
    # says what is really shown (`_file_annotations_under_shown_dataset`).
    _annotations.activate_dataset(
        st.session_state, annotations_owner(_dataset_owner), adopt=False
    )
    # UX-166: on the Data page the dataset card sits above the table.
    data_page_slot = setup_source_slot.empty()
    # UX-54: the page lists every dataset as a *table* — one row each, sortable,
    # with the counts beside the name and the per-row actions in the row they
    # belong to. Reserved here (so it keeps its place at the top of the page)
    # and filled after the load, which is the first point this run's counts for
    # the open dataset exist.
    # Keyed: the "Load and verify a dataset" tutorial spotlights it — the data
    # source picker it used to aim at is not on this page (only Scanpath and
    # Corpus Analysis draw one), so the step outlined nothing.
    dataset_table_slot = setup_source_slot.container(key="tutorial_available_datasets")
    # UX-174 r2 → UX-177 — the two ways to make a dataset are one **+ Add
    # dataset** menu (the Scanpath picker's + with its name spelled out), under
    # the list it adds to. Filled once `data_choice` is known.
    add_dataset_slot = (
        setup_source_slot.container(key="data_page_add")
        if data_view and not wizard_owns_page
        else None
    )
    # UX-166: this run's page — the slot the skeleton and the dataset card draw
    # into while a load is slow: the view area's first child on Scanpath and
    # Corpus Analysis; on the Data page, the slot above the table, or the one
    # under the ✏️ Edit dataset header while the editor is open.
    if not data_view:
        page_slot = view_first_slot
    elif editing:
        page_slot = editor_loading_slot
    else:
        page_slot = data_page_slot
    page = loading.page(
        page_slot,
        view="data"
        if data_view
        else "corpus"
        if active_view == _VIEW_CORPUS
        else "scanpath",
        plot_height=loading.recorded_plot_height("single", 480),
    )
    if data_view and add_dataset_slot is not None and data_choice != UPLOAD_CHOICE:
        # UX-64 took ➕ Add data off the Scanpath row and made this page the only
        # way in — so the way in has to *be* here. Without this menu
        # `_enter_add_data_wizard` would have no trigger at all and uploading
        # would be unreachable. `on_click` callbacks, not inline handlers: they
        # reassign `data_source_choice`, which only lands before the widgets
        # instantiate.
        with add_dataset_slot.popover(
            "Add dataset", icon=ICONS["add"], type="primary", key="data_add_menu"
        ):
            st.button(
                "Create manually",
                icon=ICONS["author"],
                key="create_manual_scanpath_btn",
                on_click=_enter_manual_dataset,
                help="Write a text and place its fixations by hand. Saved "
                "scanpaths are listed below like any other dataset.",
                width="stretch",
            )
            st.button(
                "Import files",
                icon=ICONS["upload"],
                key="add_data_btn",
                on_click=_enter_add_data_wizard,
                help="Add your fixation and word/AOI tables with the setup wizard.",
                width="stretch",
            )
    # UX-178 — part 1's headline on every run, like the other parts (the editor
    # is built hidden); its two fields only while it is open, since they are
    # seeded from whichever dataset is open and must not outlive it.
    editor_name_body = (
        _editor_part(editor_part_name_slot, "edit_name") if data_view else None
    )
    if data_view and editing:
        _render_dataset_editor_bar(editor_head_slot, data_choice)
        # UX-174 r2 — the description is edited here, with the rest of the
        # dataset, at the top of part 1 (the add screen asks for it beside the
        # name). The public loader's own caption lands under it, in this slot.
        editing_token = str(st.session_state.get("data_source_choice") or data_choice)
        hold_editor_staging(editing_token)
        render_name_field(editor_name_body, editing_token)
        render_description_field(editor_name_body, editing_token)
    # PRE-22: the section is held back from this release — heading, caption and
    # controls all come from behind the same gate, so the page has no gap where
    # a hidden stage used to be.
    if data_view and preprocessing_enabled():
        _editor_part(setup_preproc_slot, "edit_preproc")

    preproc_settings = _activate_data_source(
        data_choice, preproc_host=setup_preproc_slot
    )
    # UX-166 — one card over the dataset pipeline, drawn in the page slot. The
    # post-wizard "Dataset added — loading your scanpaths…" bridge it replaces
    # is this card shown at once.
    dataset_card = _open_dataset_card(
        page,
        data_choice,
        view=active_view,
        view_switched=view_switched,
        finalizing=bool(st.session_state.pop("_wizard_finalizing", False)),
    )

    def _end_loading(*, showing_dataset: bool = True) -> None:
        """Take the dataset card and the page skeleton down on an early return.

        BUG-81: only the normal path cleared the old loading banners, so every
        early return (the wizard, a mapping that can't be satisfied, a filter
        that empties the pool) left one above the real content until the next
        click — on the very page the warning had just sent the user to.

        ``showing_dataset``: the run leaves the dataset on screen — a mapping
        still to fix, a filter that emptied the pool — so it is where Cancel
        goes back to (UX-168); the add-dataset wizard's return shows none.
        """
        if dataset_card is not None:
            dataset_card.close()
        st.session_state.pop(DATASET_TASK_KEY, None)
        page.release()
        if showing_dataset:
            _remember_open_dataset(data_choice)

    def _render_datasets_table(
        words, fixations, raw_gaze, *, scope_note: str | None = None
    ) -> None:
        """📂 Available datasets, whenever the Data page is showing its overview.

        BUG-81: this used to render only after a successful load, so a dataset
        whose mapping can't be satisfied — or a filter that empties the pool —
        left the heading with no table under it, and no way to switch to
        another dataset short of ♻️ Reset.
        """
        if not data_view or wizard_owns_page:
            return
        # UX-107 — ✅ Save changes closes the editor, so its success line
        # belongs here, on the screen it returns to.
        saved = st.session_state.pop("_remap_applied", None)
        join_notices = st.session_state.pop(STIMULUS_JOIN_NOTICE_KEY, None)
        builtin_saved = st.session_state.pop(BUILTIN_MAPPING_SAVED_KEY, None)
        if builtin_saved is not None:
            dataset_table_slot.success(
                f"**{_dataset_display_name(str(builtin_saved))}** updated — "
                "your changes are saved.",
                icon=ICONS["success"],
            )
        if saved:
            dataset_table_slot.success(
                f"**{_dataset_display_name(str(saved))}** updated — mapping, "
                "recording setup and any table you added are saved.",
                icon=ICONS["success"],
            )
            # DATA-49: a save whose word boxes reached only some readings says
            # so here — its warning was raised inside the button's callback.
            for notice in join_notices or []:
                dataset_table_slot.warning(notice, icon=ICONS["warning"])
        # Rendered *inside* the slot rather than handed it: the table is a
        # fragment, and a fragment rerun may only draw widgets into its own
        # containers.
        with dataset_table_slot:
            render_dataset_table(
                # Public corpora load through the historical category token,
                # while the table rows use concrete registry labels. Preserve
                # that concrete canonical selection so the active row and its
                # remembered counts are keyed to the row the user can revisit.
                active=str(st.session_state.get("data_source_choice") or data_choice),
                words=words,
                fixations=fixations,
                raw_gaze=raw_gaze,
                scope_note=scope_note,
            )

    # (DATA-9's ordered source-config group — description · options · data
    # location · column mapping — is now the top of the Data page reserved
    # above. VIZ-31 had already moved "Experimental Setup" out of it: monitor
    # geometry, fonts, text colour and plot background are figure settings, and
    # they render in the Scanpath rail beside the layers they restyle.)

    # UX-166: what the pipeline draws on its way to the view belongs *above* it —
    # the ✏️ Author editor (the view's input), the data-quality warning and
    # UX-7(b)'s missing-corpus panel (notes on it). The Scanpath and Corpus
    # views render inside `view_area`, created before all of this, so on those
    # views these go into it too (after the page slot, so they wait under a
    # skeleton with the rest of the new page); the Data page keeps them where
    # they always were. UX-167: `view_notices_slot` is its own container, held
    # on every run, so the view's blocks below it keep their place whether or
    # not a notice draws this run.
    view_notices = contextlib.nullcontext() if data_view else view_notices_slot

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
            _finish_page()
            _end_loading(showing_dataset=False)
            return
    elif data_choice == MANUAL_SAMPLE_CHOICE and not _authoring_editor_open(
        data_choice
    ):
        # The example is shown like any stored dataset; ✏️ Edit opens its editor.
        words_df, fixations_df = _manual_sample_frames()
        raw_words_df, raw_fixations_df = words_df, fixations_df
        raw_gaze_df = pd.DataFrame()
        mapping_problems = []
    elif data_choice in (AUTHOR_CHOICE, MANUAL_SAMPLE_CHOICE):
        with view_notices:
            words_df, fixations_df = _render_authoring_source()
        if active_view == _VIEW_SCANPATH:
            # The authoring canvas is this screen's visualization.
            _finish_page()
            _end_loading()
            return
        raw_words_df, raw_fixations_df = words_df, fixations_df
        raw_gaze_df = pd.DataFrame()
        mapping_problems = []
    elif data_choice in st.session_state.get("_datasets", {}):
        # A dataset the user uploaded earlier and named — its frames were
        # normalized once by the wizard and stored in session, so switching back
        # to it is instant (no re-upload, no re-mapping). See _render_data_setup's
        # finalize and resolve_data_source.
        stored = st.session_state["_datasets"][data_choice]
        # DATA-39 — a dataset saved on ✏️ Edit dataset before that fix has its
        # AOI table stranded on the placeholder reader, so every scanpath drew
        # without its boxes and text. Repair it once, in the store itself, so
        # the recovery cache writes the repaired frames and it stays fixed.
        # A repair that cannot be made is not retried while the frames are the
        # same: the diagnosis is only "the flag is still set", so a failed
        # attempt would otherwise redo the whole harmonize on every rerun.
        failed = st.session_state.setdefault("_data39_repair_failed", {})
        attempt = frame_fingerprint(stored["words"])
        if failed.get(data_choice) != attempt:
            repaired = repair_stranded_stimulus_words(
                stored["words"], stored["fixations"]
            )
            if repaired is not None:
                stored = {**stored, "words": repaired[0], "fixations": repaired[1]}
                st.session_state["_datasets"][data_choice] = stored
                failed.pop(data_choice, None)
            elif STIMULUS_WORDS_FLAG in stored["words"].columns:
                failed[data_choice] = attempt
        words_df, fixations_df = stored["words"], stored["fixations"]
        raw_gaze_df = stored["raw_gaze"]
        # BUG-103: held run after run and never written into, so each is hashed
        # once — not on every rerun — even when it was read back from disk.
        vouch_for_frames((words_df, fixations_df, raw_gaze_df))
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
        # DATA-66: and its column-name map, which only the stored entry holds —
        # the raw tables it was built from are gone.
        stored_names = stored.get("column_names") or {}
        for table, schema in (stored.get("schemas") or {}).items():
            _stash_active_mapping(
                table,
                schema,
                names=ColumnNames.from_payload(stored_names[table])
                if table in stored_names
                else None,
            )
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
        restore_builtin_mapping(source_key)
        raw_words_df, raw_fixations_df = load_words_and_fixations(
            data_choice,
            participant=deep_link_pid,
            # DATA-9 ordered group: a public dataset renders its caption / source
            # options / data-location controls into these reserved sub-slots.
            description_host=description_slot,
            options_host=source_options_slot,
            location_host=data_location_slot,
        )
        # BUG-103: the loader's own ID for these tables, so the normalization
        # below is keyed on which load they came from rather than re-hashed.
        adopt_source(raw_words_df, raw_fixations_df)
        # DATA-48: the demo may have stood in for a corpus that isn't here.
        _file_annotations_under_shown_dataset(_dataset_owner)
        if dataset_card is not None and len(dataset_card.steps) == 3:
            if st.session_state.get(_UNAVAILABLE_KEY):
                # UX-166: the corpus isn't here, so the rows just read are the
                # bundled demo's stand-in — not counts for the corpus the card
                # names. The step moves on under its plain label.
                dataset_card.step(1)
            else:
                dataset_card.step(
                    1,
                    f"Normalizing {len(raw_words_df):,} word rows and "
                    f"{len(raw_fixations_df):,} fixations",
                )
        declared_word_schema, declared_fix_schema = declared_schemas_for(data_choice)
        mapping_editor_rendered = data_choice in (PUBLIC_DATASETS_CHOICE, DEMO_CHOICE)
        words_df, fixations_df, mapping_problems = prepare_data(
            raw_words_df,
            raw_fixations_df,
            # Show the Column-mapping panels for public datasets AND the Bundled
            # Demo (DATA-8) so the re-mapping capability is discoverable on the
            # default first-load source; pre-filled with auto-detection, so an
            # untouched mapping normalizes identically.
            allow_override=mapping_editor_rendered,
            # Mode A of the Data page's one Column mapping section (DATA-26).
            mapping_host=mapping_body_slot,
            # A prepared benchmark corpus publishes its schema; auto-detection
            # must not re-guess it from the publisher's leftover columns. The
            # panels stay editable — this only changes what they start at.
            declared_word_schema=declared_word_schema,
            declared_fix_schema=declared_fix_schema,
            # BUG-32: the add-dataset wizard writes these same `col_map_*` keys
            # and its field widgets persist, so coming back here from it would
            # otherwise inherit its picks whenever the headers match.
            mapping_dataset=source_key,
            # While ✏️ Edit dataset is open the panels are a draft and the
            # dataset keeps its mapping until ✅ Save changes.
            held_schemas=(
                held_builtin_mapping(source_key)
                if editing and mapping_editor_rendered
                else None
            ),
        )
        if mapping_editor_rendered:
            if editing:
                st.session_state[_REMAP_DIRTY_KEY] = builtin_mapping_is_dirty(
                    source_key
                )
            else:
                hold_builtin_mapping(source_key)
    if not mapping_editor_rendered:
        # Another kind of source is open: no built-in snapshot may be restored
        # over the mapping keys it (or the add wizard) shares.
        st.session_state.pop(BUILTIN_MAPPING_HELD_KEY, None)
        st.session_state.pop(BUILTIN_MAPPING_RESTORE_KEY, None)
    if mapping_problems:
        # A required column is still unmapped. Rather than halt the whole app
        # (which hid the data the user needs to choose the mapping), show the
        # raw tables on the Data page, right under the still-editable Column
        # mapping section — and, from any other view, say where that page is.
        with unmapped_slot:
            _render_unmapped_view(raw_words_df, raw_fixations_df, mapping_problems)
        # BUG-100: the slot above is on the ✏️ Edit dataset screen, hidden until
        # it is opened — the overview needs its own word, where *What's in the
        # dataset* would have been — open editor or not, since UX-197 keeps
        # the overview on screen above it.
        if data_view and not wizard_owns_page:
            with setup_body_slot:
                _render_dataset_load_failure(
                    _dataset_display_name(_dataset_owner), mapping_problems
                )
        _render_offpage_setup_notice(data_view)
        _finish_page()
        _render_datasets_table(None, None, None)
        _end_loading()
        return

    # VIZ-14: local/desktop users can attach stimulus screenshots without
    # adding an image_path column to their data. This intentionally stays out
    # of public deployments and share links because it contains machine-local
    # filesystem information; the same resolver is available through the API
    # and CLI for reproducible headless renders.
    if local_filesystem_enabled():
        with _editor_part(setup_stimulus_slot, "edit_stimulus"):
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
                        _rows_with_local_images(frame)
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
            with view_notices:
                st.warning(
                    f"Data quality: {plural(len(suspicious), 'trial')} put at least 12 "
                    "fixations on one word. Check stimulus alignment or line "
                    "assignment."
                )
    else:
        st.session_state["_preprocessing_report"] = pd.DataFrame()
        st.session_state["_preprocessing_settings"] = dict(preproc_settings)

    # UX-7(b): if the selected corpus isn't on disk, say so here — in the main
    # area, where the (demo) plot the user is actually looking at is — rather than
    # leaving it to a line on the 🗂️ Data page they may never open.
    with view_notices:
        _render_dataset_unavailable()

    # Whole-dataset frames, captured BEFORE the trial-filter funnel —
    # the Bulk Export tab's "Export the whole dataset" option exports these,
    # ignoring the current filters.
    words_all, fixations_all = words_df, fixations_df
    raw_gaze_all = raw_gaze_df
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
    # BUG-32: an empty (or unjoinable) words frame beside healthy fixations is
    # a legitimate *fixations-only* dataset only when no words table was loaded
    # at all — otherwise it is a mapping that joins on nothing, and the figure
    # just draws without text. A warning, not an error: the fixations are still
    # worth drawing, but the silence has to go.
    if (st.session_state.get("_active_column_mapping") or {}).get(
        "words"
    ) and _cached_words_join_nothing(
        words_all,
        fixations_all,
        cache_key=(frame_fingerprint(words_all), frame_fingerprint(fixations_all)),
    ):
        menu.notices.warning(WORDS_JOIN_NOTHING_WARNING)
    # The verdict is raised **once, where the mapping was chosen** — right after
    # ✅ Add dataset or ✅ Save changes — rather than as a page-wide banner that
    # stood above every view for as long as the dataset was loaded. Both flows
    # set `TRIAL_IDENTITY_CHECK_KEY`; the report they are asking about is the one
    # just computed above, on the frames those buttons produced.
    asked_by = st.session_state.pop(TRIAL_IDENTITY_CHECK_KEY, None)
    if asked_by and identity_warning:
        try:
            _trial_identity_alert_dialog(str(asked_by), identity_warning)
        except StreamlitAPIException:
            # Streamlit allows one dialog per script run, and ❓ Help's three
            # (FAQ / About / Tutorials) and the welcome tour are served above
            # this point. They cannot normally be armed on the same run as this
            # — the flag is set by a button on a screen with no nav reachable —
            # but a run that returned early with the flag still armed can. Put
            # it back rather than lose the verdict; the next run has no modal
            # ahead of it.
            st.session_state[TRIAL_IDENTITY_CHECK_KEY] = asked_by

    # Trial-level filtering / grouping: narrow by participant, by condition
    # (Hunting/Gathering, difficulty, first/repeated reading, correctness), and by
    # annotation state (favorites / tags) before anything downstream sees the
    # data. The controls now live in the Scanpath tab's Trial Selection panel
    # (rendered there via render_trial_filters); here we just read the last
    # selection from session_state so filtering stays global across every view.
    if dataset_card is not None and dataset_card.steps:
        dataset_card.step(len(dataset_card.steps) - 1)  # Building the trial list
    trial_filters = read_trial_filters()
    # BUG-103: each narrowing below makes new frames every rerun while a filter
    # is on. `assign_derived` names them by their inputs and settings, so the
    # caches downstream are keyed without hashing the whole pool each time.
    pool = (words_df, fixations_df)
    words_df, fixations_df = filter_trials(
        words_df,
        fixations_df,
        participants=trial_filters["participants"],
        metadata=trial_filters["metadata"],
        ranges=trial_filters.get("ranges"),
        drop_unknown=trial_filters.get("ranges_drop_unknown"),
    )
    assign_derived(
        (words_df, fixations_df),
        "filter_trials",
        pool,
        (
            trial_filters["participants"],
            trial_filters["metadata"],
            trial_filters.get("ranges"),
            tuple(trial_filters.get("ranges_drop_unknown") or ()),
        ),
    )
    # DATA-29: a trial-grain metadata narrowing is already `(participant_id,
    # trial_id)` keys, so it applies through `filter_to_keys` rather than
    # `filter_trials` — the table is never broadcast onto the frames, which is
    # DATA-20's rule and the reason this design holds at either grain. `None`
    # means no constraint; an empty set legitimately narrows to nothing.
    # VIZ-45: the samples table is narrowed by participant like the other two.
    # It used to be narrowed only through them (the participant and trial lists
    # the filtered words/fixations still held, below), which did nothing on a
    # raw-gaze-only dataset. The condition filters reach it only when it is the
    # dataset's only table — they are offered from its own columns then
    # (`tabs.render_single_trial_tab` → `_render_filters`); beside fixations
    # they name *their* columns, and a raw-gaze column of the same name (a
    # `text_id` that merely mirrors the trial id) means something else.
    samples_only_dataset = words_all.empty and fixations_all.empty
    trialmeta_keys = trial_filters.get("trial_keys")
    raw_gaze_df = _narrowed_raw_gaze(
        raw_gaze_df,
        participants=trial_filters["participants"],
        metadata=trial_filters["metadata"] if samples_only_dataset else None,
        ranges=trial_filters.get("ranges") if samples_only_dataset else None,
        trial_keys=trialmeta_keys,
        drop_unknown=trial_filters.get("ranges_drop_unknown")
        if samples_only_dataset
        else None,
    )
    if trialmeta_keys is not None:
        pool = (words_df, fixations_df)
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, trialmeta_keys)
        assign_derived((words_df, fixations_df), "filter_to_keys", pool, trialmeta_keys)
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
        pool = (words_df, fixations_df, raw_gaze_scoped)
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, kept)
        raw_gaze_scoped = filter_frame_to_keys(raw_gaze_scoped, kept)
        assign_derived(
            (words_df, fixations_df, raw_gaze_scoped), "filter_to_keys", pool, kept
        )

    # Apply filters (participant/trial/text selection). For a raw-gaze-only
    # dataset (no words/fixations) derive the participant/trial options from the
    # raw gaze so it isn't filtered away (filter_raw_gaze drops on empty lists).
    filters = default_filters(
        words_df, fixations_df if not fixations_df.empty else raw_gaze_scoped
    )
    words_filtered, fixations_filtered = filter_data(words_df, fixations_df, filters)
    assign_derived(
        (words_filtered, fixations_filtered),
        "filter_data",
        (words_df, fixations_df),
        filters,
    )

    # The samples of the trials in the pool — and of every trial only the raw
    # gaze has, which no filter on the other two tables can speak for (VIZ-45;
    # this used to keep only the participants and trials those tables listed,
    # so a samples-only trial was dropped from any dataset with fixations).
    if not raw_gaze_scoped.empty:
        raw_gaze_filtered = raw_gaze_in_pool(
            raw_gaze_scoped,
            words_all,
            fixations_all,
            words_filtered,
            fixations_filtered,
        )
        if raw_gaze_filtered.empty:
            # Informational, not an error: the loaded raw-gaze samples just
            # don't cover any trial in the current filter (raw gaze typically
            # exists for only a subset of trials). The overlay is optional.
            menu.notices.caption(
                f"{ICONS['info']} The loaded raw-gaze samples ({len(raw_gaze_all):,} rows) don't "
                "overlap the current trial filter, so the raw-gaze overlay is "
                "unavailable here."
            )
    else:
        raw_gaze_filtered = pd.DataFrame()

    # Check for empty data after filtering. A single empty frame is fine
    # (words-only / fixations-only / raw-gaze-only datasets); all empty means the
    # filters removed everything.
    if words_filtered.empty and fixations_filtered.empty and raw_gaze_filtered.empty:
        _render_empty_after_filtering(
            words_all,
            fixations_all,
            trial_filters,
            pool_filter_frames(words_all, fixations_all, raw_gaze_all),
        )
        _finish_page()
        _render_datasets_table(words_all, fixations_all, raw_gaze_all)
        _end_loading()
        return

    # Build trial combinations for selection UI — from fixations normally, then
    # words (words-only datasets), then raw gaze (raw-gaze-only datasets), plus
    # any trial only the raw gaze has (VIZ-45, `utils.combo_source`).
    combos, _, _ = build_combo_options(
        combo_source(fixations_filtered, words_filtered, raw_gaze_filtered)
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
    # And the text table, the third grain, onto the same small frame — same
    # reasoning again.
    combos = metadata_mod.project_texts(metadata_mod.active_texts(), combos)

    # Land a shared/deep link on its exact `?trial_id=` (once) now that combos
    # exist — see _apply_url_trial_selection. Runs before the rail/tab widgets
    # render so the seeded selection is picked up as their initial value.
    _apply_url_trial_selection(combos)
    # Same hop, from inside the app: a "go to this trial" button in a Corpus
    # Analysis table parks its request in a callback (before combos exist) and
    # it is applied here — see url_state.request_trial (ENG-36).
    # A reading the pool cannot answer — its reader filtered out, say — is
    # reported, never replaced by another reader's trial of the same name.
    if missed := _apply_pending_trial_selection(combos):
        menu.notices.warning(missed, icon=ICONS["warning"])

    # Restore settings from an uploaded settings file BEFORE the rail widgets
    # render, so they pick up the saved values (see _apply_url_preset for the
    # same preset-then-render mechanism). The uploader is 🔗 Share → File's; its
    # file persists across reruns.
    _apply_uploaded_plot_config(combos, fixations_filtered)

    # Canvas and visualization controls (the Scanpath rail). For a dataset whose
    # only gaze is samples, size the canvas from the gaze extent and turn the
    # raw-gaze layer on — it's the only gaze layer there, so the plot would
    # otherwise show no gaze at all (VIZ-45). Decided once per dataset, on the
    # unfiltered frames; a link that names the layer decides it instead.
    raw_gaze_source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    seed_raw_gaze_default(
        st.session_state,
        raw_gaze_source_key,
        samples_only=fixations_all.empty and not raw_gaze_all.empty,
        link_names_layer=lambda: link_sets(_RAW_GAZE_LAYER_KEY),
    )
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

    def canvas_renderer(
        slot,
        text_host=None,
        *,
        render_text: bool = True,
        text_disabled: bool = False,
    ) -> None:
        """Render the canvas/text controls into the rail, in two places.

        UX-81 split the panel between two sections: the screen half into
        ``slot`` (📐 Figure & canvas) and the typography half into ``text_host``
        (📄 Stimulus → Text). One call, so each widget is created exactly once.
        With no ``text_host`` (the Corpus style panel) the typography rows are
        titled *Text* themselves, since no *Text* row precedes them there.
        """
        render_canvas_controls(
            words_filtered,
            canvas_geometry_frame,
            data_choice,
            slot=slot,
            bare=True,
            text_host=text_host,
            render_text=render_text,
            text_disabled=text_disabled,
            text_section=None if text_host is not None else "Text",
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
        combo_source(fixations_all, words_all, raw_gaze_all)
    )

    # UX-166: the load is done; the skeleton stays until the view has drawn its
    # controls and its first slow region opens (see `loading.card`).
    _finish_dataset_card(dataset_card, data_choice)

    # Render tabbed interface. Animation is now a checkbox inside the Scanpath
    # Visualization tab (no separate Animated Scanpath tab); Bulk Export has its
    # own tab. Raw Data + Data Statistics are merged into Data Inspection.
    # Dispatch the active view (top nav). Only one view body renders per run
    # — the keyed nav widget persists the selection across reruns, so no JS hack
    # is needed (unlike st.tabs). render_single_trial_tab writes _share_selection,
    # which 🔗 Share → File reads for the trial it records.
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
        loading.release_page()  # UX-166: the Data page's card sits above its table
        # DATA-26 — fill the page reserved before the load. Everything above the
        # dispatch already landed in its slot (source picker · description ·
        # options · data location · wizard · mode-A mapping panels); what is left
        # needs the loaded frames, so it renders here.
        #
        # UX-54's dataset table is the first of those: its counts for the open
        # dataset are this run's frames, which do not exist until the load has
        # happened. Unfiltered on purpose — the table describes the *dataset*,
        # not what the current Narrow-by left standing. UX-203: while a trial
        # filter is on, or the demo stands in for the open corpus, the counts
        # below it (📊 Stats) differ from the row's, so both say which they are.
        trials_filtered = has_active_trial_filters()
        _render_datasets_table(
            words_all,
            fixations_all,
            raw_gaze_all,
            scope_note=dataset_table_scope_note(
                filtered=trials_filtered,
                stand_in_for=(
                    _dataset_display_name(
                        str(st.session_state.get("data_source_choice") or data_choice)
                    )
                    if st.session_state.get(_PLACEHOLDER_SHOWN_KEY)
                    else None
                ),
            ),
        )
        # UX-135 — one numbered headline over the whole first part, drawn into
        # the slot reserved above the description. Everything from here to the
        # metadata tables is that part; the mapping no longer titles itself,
        # any more than the add screen's mapping rows do.
        _editor_part(editor_part_data_slot, "edit_data")
        # UX-135 — Recording setup renders into its own numbered part instead of
        # trailing the mapping form. Same renderer, same state, different host.
        recording_body = _editor_part(setup_recording_slot, "edit_setup")
        with mapping_body_slot:
            _render_column_mapping_section(
                editor_rendered=mapping_editor_rendered,
                uploads_host=editor_uploads_slot,
                setup_host=recording_body,
                words=words_all,
                fixations=fixations_all,
            )
        with _editor_part(setup_identity_slot, "edit_identity"):
            render_trial_identity_section()
        # ``setup_stimulus_slot`` is filled earlier because its values resolve
        # image paths before filtering and plotting; its reserved position is
        # what puts it after Trial identity on screen regardless (creation order
        # is screen order, so where a slot is *filled* need not agree).
        with setup_metadata_slot:
            # UX-130 r2: the *add screen's* three metadata rows, not three
            # side-by-side panels. UX-114 put them in one row of three columns
            # (an improvement on the stacked full-width blocks before it) and
            # UX-127 then gave the add screen a different shape again — one
            # "left = upload, right = mapping" row per table, under a small
            # **Metadata** heading, matching the Fixations/AOI/Raw gaze rows
            # above them. The two screens ask the same question of the same
            # dataset, so they draw it the same way; this is the same
            # `render_*_metadata_section` renderers in the same `_META_ROW_W`
            # split, under the same `wiz_map_*` key prefix so `styles.py`'s
            # own `[class*="st-key-wiz_map_…"]` rules apply verbatim — with an
            # `_edit` suffix, since a container key may be used once per run
            # and the offscreen editor is built even while the wizard is open.
            #
            # The *unfiltered* pool feeds every report (participants_all /
            # combos_all): the join describes the dataset, not whatever the
            # current trial filters left standing. `live_join` stays on, unlike
            # the wizard's (UX-116) — here the dataset exists, so the join is a
            # real answer rather than a provisional one.
            from scanpath_studio.controls import inline_field_label
            from scanpath_studio.wizard import _META_ROW_W

            meta_heading_row = st.columns(
                [_META_ROW_W[0], 1 - _META_ROW_W[0]], gap="small"
            )
            inline_field_label(
                meta_heading_row[0].container(key="wiz_map_meta_heading_edit"),
                "Metadata",
                "Optional per-reader, per-trial and per-text tables. Once "
                "attached, their columns behave like fields in the data: "
                "filters, chips, trial sorting, inspection and export.",
                emphasis=True,
            )
            for slug, renderer, ids in (
                ("participant", render_participant_metadata_section, participants_all),
                # DATA-29: same reasoning one grain down, and DATA-TBD one more.
                ("trial", render_trial_metadata_section, combos_all),
                (
                    "text",
                    render_text_metadata_section,
                    metadata_mod.text_keys(combos_all),
                ),
            ):
                block = st.container(key=f"wiz_map_block_meta_{slug}_edit")
                row = block.columns(_META_ROW_W, gap="small")
                renderer(
                    ids,
                    host=row[1],
                    upload_host=row[0].container(
                        key=f"wiz_map_upload_meta_{slug}_edit"
                    ),
                )
                st.markdown(
                    '<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True
                )
        # UX-106 — and the screen's one commit at its foot, in the slot
        # reserved after every section it saves.
        render_dataset_editor_footer(editor_footer_slot)
        if mapping_editor_rendered:
            _render_builtin_editor_footer(editor_footer_slot)
        elif str(st.session_state.get("data_source_choice") or "") not in (
            st.session_state.get("_datasets") or {}
        ) and data_choice not in (UPLOAD_CHOICE, AUTHOR_CHOICE, MANUAL_SAMPLE_CHOICE):
            # A source with no mapping panels (the synthetic trial, a server
            # bundle) still has a name, a description and metadata tables to
            # save — and they wait for Save like everything else.
            _render_builtin_editor_footer(editor_footer_slot, mapping=False)
        with setup_body_slot:
            st.divider()
            active_token = str(
                st.session_state.get("data_source_choice") or data_choice
            )
            # UX-137 — the open dataset's own prose is one sentence under the
            # heading, with the rest behind a ❔. It used to be a full ℹ️ About
            # section *above* this heading: a second subheader, the description,
            # the corpus home link, the coordinate-provenance sentence and a
            # six-row published-vs-loaded table, all standing between the user
            # and the counts they came for. UX-174 r2 put Rename on the heading
            # and Edit on the description line, off the table's rows.
            render_dataset_inspection_head(active_token)
            # DATA-67 — what the dataset supports, before any trial filter:
            # the first thing a newly added dataset's overview answers.
            render_dataset_capabilities(
                words_all, fixations_all, raw_gaze_all, filtered=trials_filtered
            )
            # Values that parsed but cannot be right (negative durations,
            # infinite positions, empty word boxes) — counted, not removed.
            render_data_health(
                words_all, fixations_all, raw_gaze_all, filtered=trials_filtered
            )
            # Keyed wrapper → the stable `.st-key-…` selector the "Load and
            # verify a dataset" tutorial spotlights (it kept its name across the
            # move off the Scanpath subtab bar).
            with st.container(key="tutorial_data_inspection"):
                render_data_inspection_tab(
                    words_filtered,
                    fixations_filtered,
                    raw_gaze_filtered,
                    annotation_trials=_annotation_trials(combos_all),
                    # What the Scanpath picker can open — an annotation row's
                    # Open explains a trial the filters hide.
                    open_trials=_annotation_trials(combos),
                    # DATA-48: the dataset whose annotations these are — the
                    # demo's while it stands in for a missing corpus, as in
                    # the Export bundle.
                    dataset_name=_dataset_display_name(
                        _annotations_dataset(active_token)
                    ),
                    scope=data_scope_text(combos, combos_all, words_all, fixations_all),
                )
    elif active_view == _VIEW_CORPUS:
        with view_area:
            # UX-25: Corpus Analysis has no "Filter by" row, so the picker gets
            # its own compact row at the top of the page — it stays reachable on
            # every view.
            _ds_col, pool_col = st.columns([2, 5], vertical_alignment="bottom")
            render_data_source_picker(host=_ds_col)
            # UX-198: the pool the analysis reads — and the filters behind it —
            # beside the dataset, where Scanpath keeps its own filter funnel.
            pool = render_analysis_pool_bar(
                pool_col,
                words_all=words_all,
                fixations_all=fixations_all,
                raw_gaze_all=raw_gaze_all,
                combos=combos,
                combos_all=combos_all,
            )
            # AN-34: what each table's recipe shares — the dataset by the name
            # the picker shows (and its stable token), and the pool above.
            source_token = str(
                st.session_state.get("data_source_choice") or data_choice
            )
            recipe_context = {
                **pool,
                "dataset": {
                    "name": _dataset_display_name(source_token),
                    "source": source_token,
                },
            }
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
                    has_raw_gaze=not raw_gaze_filtered.empty,
                    recipe_context=recipe_context,
                )
    else:
        # The Scanpath view renders the viz controls itself (right rail) and
        # writes the global_* keys. Share is a subtab of this view — passed in as
        # a renderer so the page owns its subtab bar — and its File section
        # re-reads those keys when it draws, which is after the rail has.

        def _render_share_settings_file() -> None:
            """🔗 Share → File (UX-179): the settings file of the figure on screen.

            Resolved only when the File section is drawn — the trial from
            ``_share_selection`` (written by the Scanpath view before its
            subtabs), the figure settings from the rail's live keys.
            """
            live = viz_settings_from_state(
                fixations_filtered, base_font_size, words=words_filtered
            )
            selection = st.session_state.get("_share_selection") or {}
            pid = str(selection.get("participant_id") or "")
            trial = str(selection.get("trial_id") or "")
            screen = selection.get("screen_id")
            # The trial first (position-indexed), then its screen: `extract_part`
            # compares strings row by row, which over a whole sample-level
            # raw-gaze frame is seconds per call.
            trial_raw_gaze = (
                extract_trial(raw_gaze_filtered, pid, trial)
                if pid and trial and not raw_gaze_filtered.empty
                else pd.DataFrame()
            )
            if screen is not None and SCREEN_ID in trial_raw_gaze.columns:
                trial_raw_gaze = extract_part(trial_raw_gaze, pid, trial, screen)
            figure_settings = _build_figure_settings(live, not trial_raw_gaze.empty)
            figure_settings["raw_gaze"] = (
                trial_raw_gaze if not trial_raw_gaze.empty else None
            )
            figure_settings["line_spacing"] = line_spacing
            figure_settings["scale_text_to_boxes"] = scale_text_to_boxes
            render_settings_file(
                pid,
                trial,
                canvas_width,
                canvas_height,
                live["x_field"],
                live["y_field"],
                figure_settings,
                live,
                base_font_size,
                trial_raw_gaze,
                font_family=font_family,
            )

        with view_area:
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
                raw_gaze_all=raw_gaze_all,
                share_renderer=lambda visible: _render_share_body(
                    data_choice,
                    settings_file=_render_share_settings_file,
                    visible=visible,
                ),
                data_source_renderer=render_data_source_picker,
                canvas_renderer=canvas_renderer,
            )

    # UX-166: a view that never reached a slow region (no trial selected, an
    # empty view) still takes the skeleton down.
    loading.release_page()

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
    # Persist after all view/menu widgets have written their current values.
    # The helper fingerprints the session and is a no-op on unchanged reruns.
    save_local_state(st.session_state, app_url)
    # …then draw *Saved on this computer*, so it reports the write that just
    # happened rather than the previous run's.
    _finish_page()


if __name__ == "__main__":
    main()
