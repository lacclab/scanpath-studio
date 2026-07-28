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
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

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
    BACKGROUND_PRESETS,
    CITATION,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_FIGURE_SIZE,
    DEFAULT_LINE_SPACING,
    DEMO_CHOICE,
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
)
from scanpath_studio.controls import (
    FIX_FIELD_SPECS,
    RAW_GAZE_FIELD_SPECS,
    WORD_FIELD_SPECS,
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
    empty_fixations_frame,
    empty_words_frame,
    filter_data,
    filter_raw_gaze,
    filter_to_keys,
    filter_trials,
    frame_fingerprint,
    harmonize_frames,
    infer_raw_gaze_schema,
    load_multipleye_server_bundle,
    load_onestop_server_bundle,
    load_sample_data,
    load_sample_raw_gaze,
    multipleye_bundle_dir,
    normalize_fixations,
    normalize_raw_gaze,
    normalize_words,
    onestop_data_dir,
    onestop_full_bundle_exists,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    read_table,
    read_tables,
    trial_mapping_columns,
    upload_exceeds_limit,
    uploaded_files_total_bytes,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from scanpath_studio.debug_log import install_log_capture, render_debug_panel
from scanpath_studio.styles import get_app_css
from scanpath_studio.tabs import (
    _build_figure_settings,
    _render_save_restore_expander,
    render_corpus_analysis_tab,
    render_single_trial_tab,
)
from scanpath_studio.tour import (
    maybe_show_welcome_tour,
    render_spotlight_tour,
    render_tour_replay_button,
    spotlight_tour_pending,
)
from scanpath_studio.url_state import (
    _active_view,
    _apply_uploaded_plot_config,
    _apply_url_preset,
    _apply_url_trial_selection,
    _build_share_query,  # noqa: F401  re-exported for tests
    _go_corpus,
    _go_scanpath,
    _render_share_body,
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

    When loaded from an iframe with `?embed=true`, Streamlit's built-in embed
    mode already hides the header/menu — we additionally collapse the sidebar
    so the iframe is mostly the plot. Welcome-tour sessions also start with
    the sidebar closed: the centered welcome renders over a quiet page, and
    the tour's first sidebar step opens it (see tour.spotlight_tour_pending).
    """
    is_embed = (st.query_params.get("embed") or "").lower() in {"true", "1"}
    st.set_page_config(
        page_title="Scanpath Studio - Visualization of Eye Movements in Reading",
        page_icon="👀",
        layout="wide",
        initial_sidebar_state=(
            "collapsed" if (is_embed or spotlight_tour_pending()) else "auto"
        ),
    )
    st.markdown(get_app_css(), unsafe_allow_html=True)


def _render_about_panel() -> None:
    """Compact header: title + caption + the Corpus Analysis ⇄ Scanpath toggle.

    The header button switches between the two top-level views (it replaced the
    former Share button — Share is now a subtab of the Scanpath view). The
    **About** popover lives in the sidebar Help group (``_render_about_sidebar``),
    keeping the header lean.
    """
    header = st.container(key="about_header")
    # Same ratio + gap as the Scanpath view's plot/control-rail split
    # (`tabs.render_single_trial_tab`: `st.columns([4, 1], gap="large")`), so the
    # full-width nav button lines up exactly with the rail card below it.
    title_col, buttons_col = header.columns(
        [4, 1], gap="large", vertical_alignment="center"
    )
    with title_col:
        st.title("Scanpath Studio")
        st.caption("Interactive visualization of eye movements in reading.")
    # The keyed wrapper right-aligns the content-sized trigger (see
    # `.st-key-header_buttons` in styles.py). It's also the spotlight-tour target.
    #
    # UX-18: this button is the *only* door to the whole Corpus Analysis half of
    # the app, and as a plain secondary button it was routinely missed. Outbound
    # it renders `primary` with a → cue; the return trip stays quiet (secondary,
    # ← cue) so the two don't compete. Still one button, not a second navigation
    # system.
    button_row = buttons_col.container(key="header_buttons")
    with button_row:
        if _active_view() == _VIEW_CORPUS:
            st.button(
                "← Scanpath",
                key="nav_to_scanpath",
                on_click=_go_scanpath,
                width="stretch",
                help="Back to the single-trial scanpath visualization.",
            )
        else:
            st.button(
                "📊 Corpus Analysis →",
                key="nav_to_corpus",
                type="primary",
                on_click=_go_corpus,
                width="stretch",
                help="Switch to the corpus-level half of the app: aggregate "
                "across readers, texts and groups instead of one trial at a time.",
            )


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
    if trial_filters.get("participants"):
        chosen = trial_filters["participants"]
        steps.append(
            (
                f"{_FILTER_GROUP_LABELS['participants']} ({len(chosen)} selected)",
                lambda w, f, p=chosen: filter_trials(w, f, participants=p),
                ("filter_participants",),
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
                "Pick another **Data source** in the sidebar, or check the column "
                "mapping under **Data Inspection**."
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


def _render_about_sidebar() -> None:
    """Render the **About** popover in the sidebar Help group.

    Holds the version, authors, code link, and citation. Lives in the sidebar
    (next to **🎓 Show tutorial**) rather than the header so the header stays
    lean; Share remains in the header because the link it builds is contextual to
    the current trial/view."""
    from scanpath_studio import __version__

    bibtex = (
        "@software{Shubi_Scanpath_Studio_2026,\n"
        "author = {Shubi, Omer and Gruteke Klein, Keren and Lion, Ella and "
        'Jakobi, Deborah and Reich, David and J{\\"a}ger, Lena and '
        "Berzak, Yevgeni},\n"
        "license = {MIT},\n"
        "month = jun,\n"
        "title = {{Scanpath Studio}},\n"
        f"url = {{{CITATION['url']}}},\n"
        f"version = {{{__version__}}},\n"
        "year = {2026}\n"
        "}"
    )
    with st.sidebar.popover("ℹ️ About", width="stretch"):
        st.markdown(
            f"""
**Scanpath Studio** v{__version__} — interactive visualization of eye
movements in reading.

Developed by [Omer Shubi](https://omershubi.github.io/)¹,
[Keren Gruteke Klein](https://kerengruteke.github.io/)¹,
[Ella Lion](https://ella-lion.github.io/)¹,
[Deborah Jakobi]({_DILI}/lab-members/jakobi.html)²,
[David Reich]({_DILI}/lab-members/reich.html)²ʼ³,
[Lena Jäger]({_DILI}/group-leader/jaeger.html)², and
[Yevgeni Berzak](https://dds.technion.ac.il/people/academic-staff/yevgeni-berzak/)¹.

¹ [LaCC Lab]({CITATION["lab_url"]}), Technion ·
² [DiLi Lab](https://www.cl.uzh.ch/en/research-groups/digital-linguistics.html),
University of Zurich · ³ University of Potsdam

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
        # UX-20. A bare "built with AI, there may be bugs" is unfalsifiable and
        # gives the reader nothing to do with it — so this says how the behaviour
        # was checked, what to do before publishing a number, and what makes a
        # bug report actionable. Deliberately not a liability disclaimer; the MIT
        # licence already carries the no-warranty text.
        st.divider()
        st.markdown("**🤖 Built with AI assistance**")
        with st.expander("What that means for your results", expanded=False):
            st.markdown(
                f"""
Much of this code was written with substantial AI assistance. We put real effort
into validating it, and it's worth knowing exactly what that means:

- The reading measures are checked against a **hand-traced trial** whose expected
  values were worked out by hand, measure by measure. You can look at it
  yourself: add `?source=synthetic` to this app's URL.
- Where your export already carries EyeLink `IA_*` measures, **those win** over
  anything this app derives, so on a normal EyeLink report the numbers are your
  eye-tracker's, not ours.
- The full load → normalize → measure → plot pipeline runs against the bundled
  corpus on every change.

That is not the same as being bug-free. **For a number going into a paper,
cross-check it against your own pipeline or the source export** — the same thing
a reviewer would ask.

Found something wrong? [Open an issue]({CITATION["url"]}/issues) ↗ and attach the
JSON from **💾 Save & restore** — it reproduces the exact view you were looking at.
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


def _resolve_data_dir(root: str) -> str:
    """Resolve a possibly-relative data dir against the project root.

    Absolute paths (and ``~``) are used verbatim; a relative path is joined to
    the project root so it resolves no matter where the server was launched from
    (fixes the "No data found" false-negative when cwd != repo root). A blank
    stays blank (the loader then shows its missing-data note)."""
    text = (root or "").strip()
    if not text:
        return text
    expanded = Path(text).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    return str((_project_root() / expanded).resolve())


def _pick_directory_dialog() -> Optional[str]:
    """Open a native folder picker and return the chosen path, or None.

    Only works when the app runs on a machine with a display + tkinter (a
    locally-run app). Returns None — and never raises — on a headless host
    (Streamlit Cloud), a missing tkinter, or a cancelled dialog, so the text
    input stays the portable fallback."""
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

    loc = location_host if location_host is not None else st.sidebar
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
    opt = options_host if options_host is not None else st.sidebar
    loc = location_host if location_host is not None else st.sidebar
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

    opt = options_host if options_host is not None else st.sidebar
    loc = location_host if location_host is not None else st.sidebar
    variant = opt.selectbox(
        "Variant",
        options=list(ONESTOP_VARIANT_LABELS),
        format_func=lambda v: ONESTOP_VARIANT_LABELS[v],
        key="onestop_variant",
        help="Public downloads the reports from OSF on demand; LaCC lab reads a "
        "local lab-processed export (extra derived columns, no download).",
    )
    regime = opt.selectbox(
        "Reading regime",
        options=list(ONESTOP_REGIME_LABELS),
        format_func=lambda r: ONESTOP_REGIME_LABELS[r],
        key="onestop_regime",
        help="Which OneStop reading regime to load. For the public variant each "
        "is a separate OSF download of the paragraph reports.",
    )
    parts = opt.multiselect(
        "Parts",
        options=list(ONESTOP_PART_LABELS),
        format_func=lambda p: ONESTOP_PART_LABELS[p],
        default=list(datasets.ONESTOP_DEFAULT_PARTS),
        key="onestop_parts",
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


def _public_dataset_label(label: str) -> str:
    """The picker display text for a registry entry (its short name, if any)."""
    return PUBLIC_DATASET_REGISTRY.get(label, {}).get("short", label)


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
    chosen = st.session_state.get("public_dataset_choice")
    if chosen not in PUBLIC_DATASET_REGISTRY:
        chosen = next(iter(PUBLIC_DATASET_REGISTRY))
        st.session_state["public_dataset_choice"] = chosen
    spec = PUBLIC_DATASET_REGISTRY[chosen]
    desc = description_host if description_host is not None else st.sidebar
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
    spec = PUBLIC_DATASET_REGISTRY.get(
        st.session_state.get("public_dataset_choice", "")
    )
    return spec.get("monitor") if spec else None


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
        words, fixations = load_multipleye_server_bundle(participant=participant)
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
        "field(s) in the **Column mapping** panel below each upload box in the "
        "sidebar — the raw uploaded data is shown below to help you choose. "
        "Still needed:\n\n" + "\n".join(f"- {p}" for p in problems)
    )
    if (raw_words_df is None or raw_words_df.empty) and (
        raw_fixations_df is None or raw_fixations_df.empty
    ):
        st.info("No data loaded yet.")
    _render_raw_preview("Words / IA", raw_words_df)
    _render_raw_preview("Fixations", raw_fixations_df)


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
    host = container if container is not None else st.sidebar
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
    # explicit opt-in before parsing; local installs confirm in one click.
    if upload_exceeds_limit(uploaded):
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


def load_raw_gaze_data(data_choice: str) -> pd.DataFrame:
    """Load and normalize optional raw gaze data (millisecond-level eye positions).

    Raw gaze data provides finer temporal resolution than fixation-level data
    and enables overlay visualizations showing continuous gaze paths.

    Args:
        data_choice: The selected data source (e.g. ``DEMO_CHOICE`` loads the
            bundled sample gaze; other built-in sources have none). The Upload
            source and stored datasets carry their own raw gaze, so ``main``
            doesn't call this for them.

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
                st.sidebar.warning("Could not infer raw gaze schema from sample data")
                raw_gaze_df = pd.DataFrame()
    else:
        uploaded_raw_gaze = st.sidebar.file_uploader(
            "Raw gaze table (optional)",
            type=["csv", "parquet", "feather", "zip"],
            help="Optional: millisecond-level gaze with participant_id, trial_id, x, y.",
        )
        if uploaded_raw_gaze:
            raw_gaze_df = read_table(uploaded_raw_gaze)
            proposed = propose_raw_gaze_schema(raw_gaze_df)
            initial_problems = validate_raw_gaze_schema(proposed)
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
                st.sidebar.warning("Raw gaze ignored — " + "; ".join(problems))
                raw_gaze_df = pd.DataFrame()
            else:
                _stash_active_mapping("raw_gaze", raw_gaze_schema)
                raw_gaze_df = normalize_raw_gaze(raw_gaze_df, raw_gaze_schema)

    return raw_gaze_df


# -----------------------------------------------------------------------------
# Sidebar controls
# -----------------------------------------------------------------------------


def _sidebar_group(title: str) -> None:
    """Render a section title that groups the toggles below it in the sidebar."""
    st.sidebar.markdown(f"### {title}")


def render_sidebar_data_source() -> str:
    """Render the data-source picker in the sidebar.

    Returns the selected source: ``DEMO_CHOICE`` ("Bundled Demo"), a stored
    uploaded dataset's name, ``ONESTOP_CHOICE`` / ``PUBLIC_DATASETS_CHOICE`` when
    available, ``SYNTHETIC_CHOICE`` if already selected, or ``UPLOAD_CHOICE``
    while the "➕ Add data" wizard is active. Switching to a stored dataset reloads
    it from session (no re-upload); the synthetic source is no longer offered
    fresh and "Public Datasets" shows grayed-out until the feature flag is on.
    """
    # Imported lazily (not at module top) to avoid the app⇄wizard import cycle.
    from scanpath_studio.wizard import _enter_add_data_wizard, _remove_dataset

    # Keyed wrapper → stable `.st-key-…` selector for the spotlight tour.
    source = st.sidebar.container(key="tour_grp_data_source").expander(
        "Data source", expanded=True
    )

    # Apply a programmatic source switch (the wizard's finalize / Cancel) BEFORE
    # any widget reads data_source_choice. It rides a plain key, not the radio's
    # widget value, so the browser never reconciles it away — assigning
    # data_source_choice inline and rerunning is unreliable because the radio's
    # frontend value can overwrite it on the rerun (works in AppTest, not in a
    # real browser). Applying it here, before the radio instantiates, is the safe
    # equivalent of an on_click callback.
    pending = st.session_state.pop("_pending_source_choice", None)
    if pending is not None:
        st.session_state["data_source_choice"] = pending
        # A real source was chosen (finalize / cancel) → leave the wizard.
        st.session_state["_show_upload_wizard"] = False

    # The upload wizard is tracked by a plain flag, not by parking UPLOAD_CHOICE
    # in the radio key (which Streamlit would garbage-collect mid-wizard — see
    # _enter_add_data_wizard). The legacy ``data_source_choice == UPLOAD_CHOICE``
    # is still honoured so AppTests / `?source=upload` deep links can open the
    # wizard directly. While it's open, don't render the radio; offer a way out.
    if (
        st.session_state.get("_show_upload_wizard")
        or st.session_state.get("data_source_choice") == UPLOAD_CHOICE
    ):
        source.caption("➕ Adding a dataset — fill in the setup wizard →")
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
    # `data_source_choice` stays the canonical widget key, but for a public corpus
    # the entry's token IS the registry label; the return value resolves it back to
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
    for name in uploaded:
        entries.append(name)
        kinds[name] = "🔒"
    if public_datasets_enabled():
        for label in PUBLIC_DATASET_REGISTRY:
            entries.append(label)
            kinds[label] = "🌐"
    # The synthetic trial is no longer offered fresh (a tiny demo variant) but
    # stays selectable when something already chose it (e.g. tests).
    if st.session_state.get("data_source_choice") == SYNTHETIC_CHOICE:
        entries.append(SYNTHETIC_CHOICE)
        kinds[SYNTHETIC_CHOICE] = "🧪"

    # Migrate a legacy `PUBLIC_DATASETS_CHOICE` selection (old saved state / deep
    # link / the former category radio) to the concrete corpus token so it lands on
    # the right entry. Falls back to the first public corpus (not the demo) when no
    # corpus was remembered, preserving the old "Public datasets → first corpus".
    if st.session_state.get("data_source_choice") == PUBLIC_DATASETS_CHOICE:
        corpus = st.session_state.get("public_dataset_choice")
        if corpus not in PUBLIC_DATASET_REGISTRY:
            corpus = (
                next(iter(PUBLIC_DATASET_REGISTRY), None)
                if public_datasets_enabled()
                else None
            )
        st.session_state["data_source_choice"] = corpus or entries[0]

    def _entry_label(token: str) -> str:
        tag = kinds.get(token, "")
        if token in PUBLIC_DATASET_REGISTRY:
            name = _public_dataset_label(token)
        elif token in uploaded:
            name = f"{token} (yours)"
        else:
            name = token
        return f"{tag} {name}".strip()

    # Heal a stale/invalid selection (e.g. a removed dataset) so the widget never
    # errors, then let the session value drive it — no `index=`, which would clash
    # with the Session-State-backed key and can ignore a programmatic switch.
    if st.session_state.get("data_source_choice") not in entries:
        st.session_state["data_source_choice"] = entries[0]
    choice = source.selectbox(
        "Data source",
        entries,
        format_func=_entry_label,
        help=data_dictionary_help_text(),
        key="data_source_choice",
        label_visibility="collapsed",
    )
    # Let the user remove datasets they added earlier (✕ next to each). Selecting
    # the removed one falls back to the demo (see _remove_dataset).
    if uploaded:
        source.caption("Remove an added dataset")
        for name in uploaded:
            name_col, x_col = source.columns([5, 1])
            name_col.write(name)
            x_col.button(
                "✕",
                key=f"remove_dataset_{name}",
                on_click=_remove_dataset,
                args=(name,),
                help=f"Remove '{name}'",
            )
    # The state change runs in an on_click callback (before widgets instantiate)
    # so it can reassign the data_source_choice key — see _enter_add_data_wizard.
    # The callback fires, then Streamlit reruns into the wizard branch above.
    source.button(
        "➕ Add data",
        key="add_data_btn",
        on_click=_enter_add_data_wizard,
        help="Upload your own eye-tracking tables.",
    )
    source.caption(
        "Have a public corpus? "
        f"[Get it built in ↗]({CITATION['docs_url']}contributing-a-dataset/)"
    )
    # Resolve a public-corpus token back to the canonical PUBLIC_DATASETS_CHOICE so
    # every downstream consumer (load dispatch, monitor, filter/col-map reset keys)
    # is unchanged; the chosen corpus rides public_dataset_choice as before.
    if public_datasets_enabled() and choice in PUBLIC_DATASET_REGISTRY:
        st.session_state["public_dataset_choice"] = choice
        return PUBLIC_DATASETS_CHOICE
    return choice


def render_sidebar_canvas_controls(
    words_filtered: pd.DataFrame,
    fixations_filtered: pd.DataFrame,
    data_choice: Optional[str] = None,
    slot=None,
    expanded: bool = False,
    title: str = "Experimental Setup",
) -> Tuple[int, int, int, str, float, bool]:
    """Render canvas dimension and font controls in sidebar.

    These controls allow users to match the visualization to their experimental
    display setup, ensuring spatial accuracy and proper word box alignment.

    Args:
        words_filtered: Filtered words dataframe (used to compute default dimensions)
        fixations_filtered: Filtered fixations dataframe (used for coordinate ranges)
        data_choice: Currently selected data source. When it's the OneStop server
            bundle or the bundled demo (a OneStop subset), defaults to the
            OneStop monitor resolution (2560x1440, Dell U2715H — OneStopL1 paper
            §Monitor). Otherwise defaults are derived from data extents.

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
    monitor_is_authoritative = False
    if data_choice in (ONESTOP_CHOICE, DEMO_CHOICE):
        default_canvas_w, default_canvas_h = 2560, 1440
        monitor_is_authoritative = True
    elif (monitor := _public_dataset_monitor(data_choice)) is not None:
        default_canvas_w, default_canvas_h = monitor
        monitor_is_authoritative = True
    elif data_choice == MULTIPLEYE_BUNDLE_CHOICE:
        # MultiplEYE server bundle = the same native MultiplEYE export as the
        # public source; coordinates are offset onto the centered stimulus on
        # the real 1920x1080 monitor, so snap the canvas to it (true-to-scale),
        # exactly like the public MultiplEYE registry entry's monitor.
        from scanpath_studio.datasets import MULTIPLEYE_MONITOR

        default_canvas_w, default_canvas_h = MULTIPLEYE_MONITOR
        monitor_is_authoritative = True
    elif data_choice is None or data_choice == UPLOAD_CHOICE:
        # Uploaded data (the setup wizard passes data_choice=None) defaults to a
        # common 1440p monitor — data-derived extents undershoot the real screen,
        # and the user can fine-tune it right here.
        default_canvas_w, default_canvas_h = DEFAULT_FIGURE_SIZE
    else:
        default_canvas_w, default_canvas_h = compute_canvas_size(
            words_filtered, fixations_filtered
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
    source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    if monitor_is_authoritative and st.session_state.get("_canvas_seeded_for") != (
        source_key
    ):
        st.session_state["global_canvas_width"] = canvas_width
        st.session_state["global_canvas_height"] = canvas_height
        st.session_state["_canvas_seeded_for"] = source_key
    st.session_state.setdefault("global_canvas_width", canvas_width)
    st.session_state.setdefault("global_canvas_height", canvas_height)

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

    # The display-setup panel (``title``, default "Experimental Setup") lives
    # under the 📂 Data group (TODO 5), rendered into a slot reserved there by
    # `main`; falls back to the sidebar when unset. The setup wizard renders the
    # very same controls inline under its own numbered heading (Group A), passing
    # a more specific title so it doesn't echo that heading.
    display = (slot if slot is not None else st.sidebar).expander(
        title, expanded=expanded
    )
    canvas_width = display.number_input(
        "Monitor width (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor width in pixels to keep coordinates true to scale.",
        key="global_canvas_width",
    )
    canvas_height = display.number_input(
        "Monitor height (px)",
        min_value=100,
        max_value=10000,
        step=10,
        help="Use the real monitor height in pixels to keep coordinates true to scale.",
        key="global_canvas_height",
    )
    # Reading text is true-to-scale by default: it auto-sizes to the word boxes
    # (text height = box_height / line_spacing) and scales with the figure, so it
    # always fills the real line slot. Untick to fall back to a fixed font size.
    # Keyed (+ seeded) so the Save & restore panel can capture/reapply them.
    st.session_state.setdefault("global_scale_text_to_boxes", True)
    scale_text_to_boxes = display.checkbox(
        "Scale text to boxes",
        key="global_scale_text_to_boxes",
        help="Size the reading text from the word boxes (height = box height ÷ "
        "line spacing) so it stays true to the real experiment at any zoom. "
        "Untick to use the fixed 'Figure font size' below instead.",
    )
    st.session_state.setdefault("global_line_spacing", float(DEFAULT_LINE_SPACING))
    line_spacing = display.number_input(
        "Line spacing",
        min_value=1.0,
        max_value=10.0,
        step=0.5,
        disabled=not scale_text_to_boxes,
        key="global_line_spacing",
        help="Line slots per line of text. OneStop rendered one blank line above "
        "and one below each text line, so the box spans 3 line heights → 3.",
    )
    st.session_state.setdefault("global_base_font_size", 16)
    base_font_size = display.number_input(
        "Figure font size (px)",
        min_value=6,
        max_value=72,
        step=1,
        help="Real (monitor-pixel) font size, scaled true-to-scale with the "
        "figure. Used for the reading text when 'Scale text to boxes' is off or "
        "the data has no word boxes, and always for axis/legend chrome.",
        key="global_base_font_size",
    )
    # VIZ-1: every font-size control here is in pixels, but stimulus typography
    # is usually specified in points. Spell out the difference + the conversion.
    display.caption(
        "ℹ️ Font sizes here are in **pixels (px)**, but stimuli are usually "
        "specified in **points (pt)**. To match the original, convert via the "
        "experiment's DPI: `px = pt × DPI ÷ 72` (e.g. 12 pt ≈ 16 px at 96 DPI). "
        "Prefer **Scale text to boxes** when the data ships word boxes — it sizes "
        "the text from the real geometry and sidesteps the conversion."
    )
    st.session_state.setdefault("global_font_family", FONT_FAMILY)
    font_family = display.text_input(
        "Text font",
        key="global_font_family",
        help="Font for the word labels. Use the exact font from your experiment "
        "(e.g. 'Courier New') or a CSS fallback stack.",
    )
    # When the dataset declares its stimulus typeface (MultiplEYE), the overlaid
    # text only lines up with the stimulus image if that exact font is installed
    # on the viewer's machine — we don't bundle it, and the browser otherwise
    # falls back per-script (CJK lands, but half-width Latin in a CJK font drifts,
    # e.g. URLs render too wide). Tell the user the font + how to get it.
    hint = _stimulus_font_install_hint(font_css)
    if hint is not None:
        font_name, font_url = hint
        display.caption(
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
    st.session_state.setdefault("global_text_color", WORD_LABEL_COLOR)
    display.color_picker(
        "Text color",
        key="global_text_color",
        help="Colour of the reading text drawn over the stimulus.",
    )

    # Plot background lives here (Experimental Setup) rather than under
    # Visualization; sidebar_controls reads the chosen value from session state.
    bg_options = list(BACKGROUND_PRESETS.keys()) + ["Custom…"]
    if st.session_state.get("global_bg_choice") not in bg_options:
        st.session_state.pop("global_bg_choice", None)
    st.session_state.setdefault("global_bg_choice", bg_options[0])
    display.selectbox(
        "Plot background",
        options=bg_options,
        key="global_bg_choice",
        help="Background of the plotting area (and exported figures).",
    )
    if st.session_state.get("global_bg_choice") == "Custom…":
        display.color_picker(
            "Custom background color",
            value=DEFAULT_BACKGROUND_COLOR,
            key="global_bg_custom",
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
    # Start capturing log records into the in-app debug buffer before any data
    # or plot work runs, so the debug panel (?debug=1) sees this run's logs.
    install_log_capture()
    # The header holds the title + the Corpus Analysis ⇄ Scanpath view toggle.
    _render_about_panel()

    # Apply deep-link presets BEFORE any widget renders — see _apply_url_preset
    # for the full URL schema. External tools can deep-link into this app with
    # `?source=...&participant=...&trial=...&...` to land on a specific trial
    # with the reviewer's preferred viz settings.
    url_source = _apply_url_preset()
    if url_source == "onestop" and onestop_data_dir() is not None:
        st.session_state.setdefault("data_source_choice", ONESTOP_CHOICE)
    elif url_source == "multipleye" and multipleye_bundle_dir() is not None:
        st.session_state.setdefault("data_source_choice", MULTIPLEYE_BUNDLE_CHOICE)
    elif url_source == "demo":
        st.session_state.setdefault("data_source_choice", DEMO_CHOICE)
    elif url_source == "synthetic":
        st.session_state.setdefault("data_source_choice", SYNTHETIC_CHOICE)
    elif url_source == "onestop_public" and public_datasets_enabled():
        # DATA-3: the public OneStop corpus is shareable. Land on it in the flat
        # picker; _apply_url_preset already seeded onestop_variant/regime/parts.
        st.session_state.setdefault("data_source_choice", ONESTOP_PUBLIC_CHOICE)
    elif url_source == "upload":
        st.session_state.setdefault("_show_upload_wizard", True)

    # First-visit welcome tour. After the URL presets, so embeds and
    # deep-linked sessions can suppress it — but BEFORE the heavy data/plot
    # work, so the welcome streams to the browser immediately instead of
    # after the full first render. Replay clicks arm the tour in the button's
    # on_click callback, which runs before this point in the rerun.
    maybe_show_welcome_tour()
    render_spotlight_tour()

    # Active top-level view (set by the header Corpus⇄Scanpath button). Read here
    # so the dispatch below renders only the active page.
    active_view = _active_view()

    # Data source selection (sidebar)
    _sidebar_group("📂 Data")
    data_choice = render_sidebar_data_source()
    # Drop a stale share/save selection when the data source changes — its trial
    # id won't exist in the new dataset, so a Share link or saved config must not
    # carry it over. The active view rewrites _share_selection for the new source.
    if st.session_state.get("_share_selection_source") != data_choice:
        st.session_state.pop("_share_selection", None)
        st.session_state["_share_selection_source"] = data_choice
    # Reset the active trial filter when the data source changes (BUG-1). A filter
    # selection (participant / text id / condition value) from the previous dataset
    # may be meaningless or, worse, silently valid in the new one (e.g. OneStop and
    # MultiplEYE both have a `text_id`), so it must not carry over. Keyed on the
    # same (source, public-corpus) tuple as the col-map reset so switching
    # PoTeC<->MultiplEYE also resets; the previous source's selections are stashed
    # so switching back restores them. Runs before read_trial_filters() below.
    _filter_source_key = (data_choice, st.session_state.get("public_dataset_choice"))
    if st.session_state.get("_filters_for") != _filter_source_key:
        prev_key = st.session_state.get("_filters_for")
        stash = st.session_state.setdefault("_filter_stash", {})
        if prev_key is not None:
            stash[prev_key] = dict(st.session_state.get("_trial_filters_raw", {}))
        for _stale in [
            k
            for k in list(st.session_state)
            if isinstance(k, str) and k.startswith("filter_")
        ]:
            del st.session_state[_stale]
        st.session_state.pop("_trial_filters", None)
        # Restore this source's previously-stashed selections (if any), else clear
        # the mirror so nothing seeds back in. _seed_filter_widget re-seeds the
        # widget keys from _trial_filters_raw; render_trial_filters / render_narrow_by
        # then recompute _trial_filters this run.
        _restored = stash.get(_filter_source_key)
        st.session_state["_trial_filters_raw"] = dict(_restored) if _restored else {}
        st.session_state["_filters_for"] = _filter_source_key
    # Just-finalized upload: paint a "loading" bridge into the main area now so it
    # repaints over the wizard (instead of the wizard lingering until the slow
    # first figure finishes). Cleared just before the tabs render below.
    _finalizing_bridge = None
    if st.session_state.pop("_wizard_finalizing", False):
        _finalizing_bridge = st.empty()
        _finalizing_bridge.info("✅ Dataset added — loading your scanpaths…", icon="⏳")
    # DATA-9: render ALL of a source's config in ONE clean group, in a fixed
    # order, right below the source picker (instead of scattered sibling
    # expanders + a duplicative "<name> options" label). The order — set here by
    # reserving a sub-slot per section, since each fills at a different point
    # downstream — is:
    #     Description      (public-dataset caption / home link)
    #     Options          (source-specific: OneStop regime + parts + variant, …)
    #     Data location    (path input + Expected files + found/download status)
    #     Experimental Setup
    #     Column mapping
    # A neutral "Configure" header replaces the old "<name> options" (the source
    # name is already shown in the picker above). The slot is a plain container so
    # the Experimental Setup / Column mapping panels keep their own expanders
    # (container → expander is fine; only expander-in-expander is not).
    dataset_options_slot = st.sidebar.container()
    # The Upload wizard owns the page (and its own mapping) — no config group.
    if data_choice != UPLOAD_CHOICE:
        dataset_options_slot.markdown("**⚙️ Configure**")
    description_slot = dataset_options_slot.container()
    source_options_slot = dataset_options_slot.container()
    data_location_slot = dataset_options_slot.container()
    experimental_setup_slot = dataset_options_slot.container()
    column_mapping_slot = dataset_options_slot.container()

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
    # Start each load with a clean column-mapping stash; each branch below
    # records the schema it used for the Data Inspection tab.
    _reset_active_mapping()
    if data_choice == UPLOAD_CHOICE:
        # Hybrid setup wizard: a main-area guided flow on first load, then a
        # compact collapsed "Data & mapping" panel. While the wizard is active
        # (setup not finalized) it owns the page — return before rendering tabs.
        wizard_active = not st.session_state.get("setup_complete", False)
        # Imported lazily (not at module top) to avoid the app⇄wizard import cycle.
        from scanpath_studio.wizard import _render_data_setup

        setup = _render_data_setup(active=wizard_active)
        words_df, fixations_df = setup.words, setup.fixations
        raw_gaze_df = setup.raw_gaze
        raw_words_df, raw_fixations_df = setup.raw_words, setup.raw_fixations
        mapping_problems = setup.problems
        if wizard_active:
            return
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
        # trial picker offers one cascading selector per part — every other load
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
            # Nest the panels under the "<dataset> options" group (DATA-9).
            mapping_host=column_mapping_slot,
        )
    if mapping_problems:
        # A required column is still unmapped. Rather than halt the whole app
        # (which hid the data the user needs to choose the mapping), show the
        # raw uploaded tables; the sidebar Column-mapping panels stay editable.
        _render_unmapped_view(raw_words_df, raw_fixations_df, mapping_problems)
        return

    # Optional raw gaze: the Upload source already mapped + normalized it above;
    # every other source loads it here (bundled demo sample, OneStop uploader).
    if raw_gaze_df is None:
        raw_gaze_df = load_raw_gaze_data(data_choice)

    # UX-7(b): if the selected corpus isn't on disk, say so here — in the main
    # area, where the (demo) plot the user is actually looking at is — rather than
    # leaving it to a sidebar line they've likely scrolled past.
    _render_dataset_unavailable()

    # Whole-dataset frames, captured BEFORE the sidebar "Filter trials" panel —
    # the Bulk Export tab's "Export the whole dataset" option exports these,
    # ignoring the current filters (TODO 1.7).
    words_all, fixations_all = words_df, fixations_df

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
    )
    if (
        trial_filters["favorites_only"]
        or trial_filters["required_tags"]
        or trial_filters["excluded_tags"]
    ) and not (fixations_df.empty and words_df.empty):
        # Trials live in fixations normally; for words-only datasets fall back
        # to the words frame.
        keys_frame = words_df if fixations_df.empty else fixations_df
        present_keys = {
            (str(p), str(t))
            for p, t in zip(keys_frame["participant_id"], keys_frame["trial_id"])
        }
        kept = set(
            filter_keys(
                list(present_keys),
                favorites_only=trial_filters["favorites_only"],
                required_tags=trial_filters["required_tags"],
                excluded_tags=trial_filters["excluded_tags"],
            )
        )
        words_df, fixations_df = filter_to_keys(words_df, fixations_df, kept)

    # Apply filters (participant/trial/text selection). For a raw-gaze-only
    # dataset (no words/fixations) derive the participant/trial options from the
    # raw gaze so it isn't filtered away (filter_raw_gaze drops on empty lists).
    filters = default_filters(
        words_df, fixations_df if not fixations_df.empty else raw_gaze_df
    )
    words_filtered, fixations_filtered = filter_data(words_df, fixations_df, filters)

    # Filter raw gaze data to match selected participants/trials
    if not raw_gaze_df.empty:
        raw_gaze_filtered = filter_raw_gaze(
            raw_gaze_df,
            filters.get("participants", []),
            filters.get("trials", []),
        )
        if raw_gaze_filtered.empty:
            # Informational, not an error: the loaded raw-gaze samples just
            # don't cover any trial in the current filter (raw gaze typically
            # exists for only a subset of trials). The overlay is optional.
            st.sidebar.caption(
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

    # Land a shared/deep link on its exact `?trial_id=` (once) now that combos
    # exist — see _apply_url_trial_selection. Runs before the sidebar/tab widgets
    # render so the seeded selection is picked up as their initial value.
    _apply_url_trial_selection(combos)

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
    # "Experimental Setup" (monitor/font/text-scaling) renders into its reserved
    # slot under the 📂 Data group (TODO 5), not under 🎨 Visualization.
    (
        canvas_width,
        canvas_height,
        base_font_size,
        font_family,
        line_spacing,
        scale_text_to_boxes,
    ) = render_sidebar_canvas_controls(
        words_filtered,
        fixations_filtered if not fixations_filtered.empty else raw_gaze_filtered,
        data_choice,
        slot=experimental_setup_slot,
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

    # Reserve the "💾 Save & restore" slot here (a keyed container so the
    # spotlight tour can target it); the active view fills it later (it needs the
    # live selection + figure settings for the download). See
    # tabs._render_save_restore_expander. This single panel merges the former
    # Plot-configuration and Annotations sidebar panels (TODO 1.19). DATA-9: it's
    # its own top-level section (a divider separates it from the data-source
    # config above), since saving/restoring plot config + annotations is a global
    # session feature, not part of any one source's setup.
    st.sidebar.divider()
    save_restore_slot = st.sidebar.container(key="tour_grp_save_restore")

    # Whole-dataset combos for the Bulk Export tab's "Export the whole dataset"
    # option, mirroring how `combos` is built from the filtered frames.
    combos_all, _, _ = build_combo_options(
        fixations_all
        if not fixations_all.empty
        else words_all
        if not words_all.empty
        else raw_gaze_df
    )

    # Clear the post-finalize "loading" bridge now that the real content is about
    # to render in its place.
    if _finalizing_bridge is not None:
        _finalizing_bridge.empty()

    # Render tabbed interface. Animation is now a checkbox inside the Scanpath
    # Visualization tab (no separate Animated Scanpath tab); Bulk Export has its
    # own tab. Raw Data + Data Statistics are merged into Data Inspection.
    # Dispatch the active view (sidebar nav). Only one view body renders per run
    # — the keyed nav widget persists the selection across reruns, so no JS hack
    # is needed (unlike st.tabs). render_single_trial_tab writes _share_selection
    # and fills the Save & restore slot when it's the active view.
    if active_view == _VIEW_CORPUS:
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
    _sr_raw_gaze = (
        extract_trial(raw_gaze_filtered, _sr_pid, _sr_trial)
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

    # Share now lives in the Scanpath view's "🔗 Share" subtab (rendered via the
    # share_renderer passed into render_single_trial_tab), so it builds its deep
    # link from the resolved trial + live viz settings right where it's shown.

    # Sidebar Help group (bottom): replay the welcome tour (the tour itself
    # renders early in this function — see the maybe_show_welcome_tour call) and
    # the About popover (moved here from the header).
    _sidebar_group("❓ Help")
    render_tour_replay_button()
    # UX-17: the docs site is the full reference — link it directly here, not
    # only from inside the About popover.
    # The "↗" marks it as leaving the app — a link_button opens a new browser tab,
    # unlike every other control in the sidebar.
    st.sidebar.link_button(
        "📚 Documentation ↗",
        CITATION["docs_url"],
        width="stretch",
        help="Guides, the column-mapping reference, and the Python API. Opens in "
        "a new tab.",
    )
    _render_about_sidebar()

    # Developer debug panel — hidden unless the URL carries ?debug=1, which
    # reveals a "🐛 Debug mode" toggle that opens the captured-log view.
    render_debug_panel()


if __name__ == "__main__":
    main()
