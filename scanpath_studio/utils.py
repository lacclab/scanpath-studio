"""Utility functions for trial selection, statistics, and labelling."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from .annotations import get_entry
from .data import frame_fingerprint

# Annotation markers shown beside a trial in the pickers (UX-6). Independent of
# the same-text/same-participant markers (UX-4) and of each other — a trial can
# carry any combination, so they compose. ★ favorite · 🏷️ tagged · 📝 noted.
FAVORITE_MARKER = "★"
TAGGED_MARKER = "🏷️"
NOTE_MARKER = "📝"


def annotation_markers(participant_id, trial_id) -> str:
    """Composable annotation markers (★ favorite · 🏷️ tagged · 📝 noted) for a
    trial, or ``""`` when it carries no annotations. Reads the session store."""
    if participant_id is None or trial_id is None:
        return ""
    entry = get_entry(str(participant_id), str(trial_id))
    marks = ""
    if entry.get("star"):
        marks += FAVORITE_MARKER
    if entry.get("tags"):
        marks += TAGGED_MARKER
    if str(entry.get("note") or "").strip():
        marks += NOTE_MARKER
    return marks


# -----------------------------------------------------------------------------
# Trial combo building
# -----------------------------------------------------------------------------


def build_combo_options(
    fixations: pd.DataFrame,
) -> Tuple[pd.DataFrame, list[str], Dict[str, Tuple[str, str]]]:
    """Build participant/trial/text combinations for selection UI.

    Returns:
        Tuple of (combos DataFrame, label list, label-to-combo mapping).

    Cached on a cheap fingerprint of the frame + the composite-trial columns, so
    the full-frame ``drop_duplicates`` + label build don't re-run on every rerun
    (e.g. selecting a different trial). The session-state read happens here, in
    the un-cached wrapper, and is threaded into the cached core as an argument.
    """
    composite_cols = tuple(st.session_state.get("_composite_trial_columns") or [])
    return _build_combo_options_cached(
        fixations,
        composite_cols,
        cache_key=(frame_fingerprint(fixations), composite_cols),
    )


@st.cache_data(show_spinner="Building trial list…")
def _build_combo_options_cached(
    _fixations: pd.DataFrame,
    composite_cols: Tuple[str, ...],
    cache_key,
) -> Tuple[pd.DataFrame, list[str], Dict[str, Tuple[str, str]]]:
    fixations = _fixations
    trial_col = (
        "unique_trial_id" if "unique_trial_id" in fixations.columns else "trial_id"
    )
    # The text/passage column is optional. Normalized frames carry a text_id (it
    # falls back to trial_id when no text is mapped), but a frame may arrive with
    # only the source name (e.g. unique_paragraph_id — the pre-rename text id, and
    # which can also be a composite-trial component). Detect it via the same
    # priority list normalization uses, and *copy* it to text_id rather than
    # renaming so a shared composite component column survives for the picker.
    text_col = next(
        (
            c
            for c in (
                "unique_text_id",
                "text_id",
                "unique_paragraph_id",
                "paragraph_id",
            )
            if c in fixations.columns
        ),
        None,
    )
    combo_cols = ["participant_id", trial_col]
    if text_col is not None and text_col not in combo_cols:
        combo_cols.append(text_col)
    for col in ["unique_trial_id", "unique_text_id", "TRIAL_INDEX", "trial_index"]:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)
    # Carry the composite trial id's component columns through, so the trial
    # picker can offer one cascading selector per part (see select_trial).
    for col in composite_cols:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)

    combos = (
        fixations[combo_cols].drop_duplicates().rename(columns={trial_col: "trial_id"})
    )
    if "text_id" not in combos.columns:
        combos["text_id"] = (
            combos[text_col] if text_col is not None else combos["trial_id"]
        )
    if trial_col == "unique_trial_id" and "unique_trial_id" not in combos.columns:
        combos["unique_trial_id"] = combos["trial_id"]
    if text_col == "unique_text_id" and "unique_text_id" not in combos.columns:
        combos["unique_text_id"] = combos["text_id"]
    sort_cols = ["participant_id"]
    if "TRIAL_INDEX" in combos.columns:
        sort_cols.append("TRIAL_INDEX")
    elif "trial_index" in combos.columns:
        sort_cols.append("trial_index")
    sort_cols.append("trial_id")
    combos = combos.sort_values(sort_cols)

    combo_labels = [
        f"{row.participant_id} / {row.trial_id} · {row.text_id}"
        for row in combos.itertuples()
    ]
    label_to_combo = dict(
        zip(
            combo_labels,
            combos[["participant_id", "trial_id"]].itertuples(index=False, name=None),
        )
    )
    return combos, combo_labels, label_to_combo


@st.cache_data(show_spinner=False)
def _trial_positions(_frame: pd.DataFrame, cache_key) -> Dict[Tuple[str, str], object]:
    """Map ``(participant_id, trial_id)`` → positional row indices.

    Built once per frame (cached on its fingerprint) so extracting a single
    trial is an O(trial) ``iloc`` rather than an O(corpus) boolean mask on every
    rerun — and shared across the tabs, which all slice the same filtered frames.
    """
    if _frame is None or _frame.empty:
        return {}
    grouped = _frame.groupby(["participant_id", "trial_id"], sort=False).indices
    # Normalise keys to (str, str) so lookups match the picker's string values.
    return {(str(p), str(t)): idx for (p, t), idx in grouped.items()}


def extract_trial(frame: pd.DataFrame, participant_id, trial_id) -> pd.DataFrame:
    """Rows of one (participant, trial), sliced via the cached position index.

    Equivalent to ``frame[(frame.participant_id == p) & (frame.trial_id == t)]``
    but O(trial) instead of O(corpus) once the index is built — the per-rerun win
    on large datasets, where every tab extracts the selected trial."""
    if frame is None or getattr(frame, "empty", True):
        return frame
    positions = _trial_positions(frame, cache_key=frame_fingerprint(frame))
    pos = positions.get((str(participant_id), str(trial_id)))
    if pos is None or len(pos) == 0:
        return frame.iloc[0:0]
    return frame.iloc[pos]


# -----------------------------------------------------------------------------
# Trial selection UI
# -----------------------------------------------------------------------------

# UX-10 · sorting the trial pool.
#
# The picker listed trials in data order, so finding "the slowest reader", "the
# one with the most fixations" or "the trials this reader got wrong" meant
# scrolling the whole list. These build a sort key per trial from three sources:
# computed per-trial stats, reader/text properties, and any trial-level column
# the dataset carries. Pure and frame-driven, so they're testable without the UI.
TRIAL_SORT_DEFAULT = "Trial ID"
# Computed stat label → (frame it needs, how to aggregate it per trial).
# "fixations" / "words" name which frame the aggregation runs on.
_TRIAL_SORT_STATS = {
    "Fixations (n)": ("fixations", "size"),
    "Reading time (s)": ("fixations", "duration_sum_s"),
    "Mean fixation (ms)": ("fixations", "duration_mean"),
    "Words (n)": ("words", "size"),
}
# Columns worth offering as a sort key when the dataset carries them, in the
# order they're shown. Reader properties first, then text, then behaviour.
_TRIAL_SORT_PREFERRED_COLS = (
    "participant_id",
    "text_id",
    "unique_text_id",
    "paragraph_id",
    "difficulty_level",
    "question_preview",
    "repeated_reading_trial",
    "is_correct",
    "genre",
    "session",
    "pp_age",
    "pp_gender",
    "TRIAL_INDEX",
    "trial_index",
)


def _per_trial_stat(frame: pd.DataFrame, trial_field: str, how: str) -> pd.Series:
    """One computed stat per trial id, as a Series indexed by that id."""
    if frame is None or frame.empty or trial_field not in frame.columns:
        return pd.Series(dtype=float)
    grouped = frame.groupby(frame[trial_field].astype(str), sort=False)
    if how == "size":
        return grouped.size().astype(float)
    if "duration_ms" not in frame.columns:
        return pd.Series(dtype=float)
    durations = grouped["duration_ms"].agg("sum" if "sum" in how else "mean")
    return (durations / 1000.0) if how.endswith("_s") else durations.astype(float)


def trial_sort_keys(
    combos: pd.DataFrame,
    trial_field: str,
    *,
    words: Optional[pd.DataFrame] = None,
    fixations: Optional[pd.DataFrame] = None,
) -> Dict[str, pd.Series]:
    """Available sort keys (UX-10): label → Series indexed by trial id.

    Offers a computed stat only when the frame it needs is present, and a column
    only when it's actually *trial-level* in ``combos`` (one value per trial) —
    a column that varies within a trial can't order the pool meaningfully.
    """
    keys: Dict[str, pd.Series] = {}
    for label, (which, how) in _TRIAL_SORT_STATS.items():
        frame = fixations if which == "fixations" else words
        # The stat is keyed by the *plain* trial id on the data frames; combos may
        # be keyed by unique_trial_id, so fall back when the field is absent.
        field = (
            trial_field
            if (frame is not None and trial_field in frame.columns)
            else "trial_id"
        )
        series = _per_trial_stat(frame, field, how)
        if not series.empty:
            keys[label] = series
    if combos is None or combos.empty or trial_field not in combos.columns:
        return keys
    ids = combos[trial_field].astype(str)
    for col in _TRIAL_SORT_PREFERRED_COLS:
        if col not in combos.columns or col == trial_field:
            continue
        if (combos.groupby(ids, sort=False)[col].nunique(dropna=False) > 1).any():
            continue  # varies within a trial — can't order the pool by it
        # Build the id→value Series from the deduplicated rows explicitly: an
        # Arrow-backed `ids.unique()` isn't accepted as a `set_index` key, and
        # pairing the two `.to_numpy()`s keeps id and value on the same row.
        deduped = combos.drop_duplicates(subset=[trial_field])
        keys[col.replace("_", " ").capitalize()] = pd.Series(
            deduped[col].to_numpy(),
            index=deduped[trial_field].astype(str).to_numpy(),
        )
    return keys


def sort_trial_options(
    options: List[str],
    key_series: Optional[pd.Series],
    *,
    descending: bool = False,
) -> List[str]:
    """Order ``options`` (trial ids) by ``key_series``, ties broken by id.

    Trials the key doesn't cover sort last regardless of direction — an unranked
    trial is missing information, not an extreme value, so it shouldn't lead.
    """
    if key_series is None or key_series.empty:
        return sorted(options)
    lookup = key_series.to_dict()
    ranked = [o for o in options if o in lookup and pd.notna(lookup[o])]
    unranked = sorted(o for o in options if o not in ranked)
    ranked.sort(key=lambda o: (_sort_scalar(lookup[o]), o), reverse=descending)
    return ranked + unranked


def _sort_scalar(value):
    """A comparable key for a cell that may be numeric, boolean or text."""
    if isinstance(value, bool):
        return (0, float(value))
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value))


def format_sort_value(value) -> str:
    """A sort key's value, short enough to ride along in a picker option.

    Sorting the pool is only useful if you can *see* what you sorted by — an
    ordering with the ordering key hidden just looks shuffled. Integers keep a
    thousands separator, floats get one decimal, booleans read Yes/No.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, (bool, np.bool_)):
        return "Yes" if value else "No"
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return f"{number:,.0f}" if number == int(number) else f"{number:,.1f}"
    return str(value)


def _trial_display_label(trial_id) -> str:
    """Human-readable label for a trial id in the pickers.

    MultiplEYE per-page ids read cleanly — ``Lit_Alchemist_4__page_07`` →
    ``Lit_Alchemist_4 · page 7`` (the id stays zero-padded so it sorts
    numerically; only the display drops the padding). Any other id passes
    through unchanged, so this is a no-op for every other corpus."""
    text = str(trial_id)
    stim, sep, page = text.rpartition("__page_")
    if sep and page.isdigit():
        return f"{stim} · page {int(page)}"
    return text


def _render_trial_sort_popover(
    host,
    combos: pd.DataFrame,
    trial_field: str,
    key_prefix: str,
    *,
    words: Optional[pd.DataFrame],
    fixations: Optional[pd.DataFrame],
) -> Tuple[Optional[pd.Series], bool, str]:
    """The ⇅ sort control beside the trial picker (UX-10).

    Lives in a popover rather than inline: the picker row is already a selectbox,
    a slider and two step buttons wide, and sorting is a "set it once" choice, not
    a per-trial one. Returns ``(key_series, descending, choice)`` for
    :func:`sort_trial_options` — ``(None, False, TRIAL_SORT_DEFAULT)`` for the
    default id order. The chosen key's *name* comes back too, because the picker
    labels the ordering it's showing.
    """
    keys = trial_sort_keys(combos, trial_field, words=words, fixations=fixations)
    if not keys:
        return None, False, TRIAL_SORT_DEFAULT
    options = [TRIAL_SORT_DEFAULT, *keys]
    state_key = f"{key_prefix}_trial_sort"
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = TRIAL_SORT_DEFAULT
    with host.popover("⇅", width="content", help="Sort the trial list"):
        choice = st.selectbox(
            "Sort trials by",
            options=options,
            key=state_key,
            help="Reorder the picker so outliers surface without scrolling — by a "
            "computed stat (fixation count, reading time) or a reader / text / "
            "condition property.",
        )
        descending = st.checkbox("Descending", key=f"{key_prefix}_trial_sort_desc")
    if choice == TRIAL_SORT_DEFAULT:
        return None, False, TRIAL_SORT_DEFAULT
    return keys[choice], bool(descending), choice


def _select_trial_none_mode(
    combos: pd.DataFrame,
    trial_field: str,
    text_field: str,
    key_prefix: str,
    picker_host=None,
    *,
    words: Optional[pd.DataFrame] = None,
    fixations: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """The trial picker: a **selectbox + scrubbing slider + ◀ ▶ step buttons + a ⇅
    sort popover**, all on one row. The slider thumb shows ``index/TOTAL · id``
    (index first). The pool is narrowed upstream (the "Narrow by" multiselects +
    the "More" filters), so this just picks one trial from it and orders it.

    Creates its own row of columns, so call it where columns are allowed (the
    Scanpath/Corpus body), not nested inside another column. ``picker_host``
    (when given) is the container to render into; defaults to the current one.
    ``words`` / ``fixations`` (optional) unlock the computed sort keys (UX-10);
    without them only column-based orderings are offered."""
    host = picker_host if picker_host is not None else st
    available_trials = combos.drop_duplicates(subset=[trial_field])
    trial_options = sorted(available_trials[trial_field].dropna().astype(str).unique())
    if not trial_options:
        st.warning("No trials available after filtering.")
        st.stop()

    # Trial id → participant, so the annotation markers (UX-6) can be looked up per
    # option (annotations are keyed by (participant, trial)). Mirrors the selection
    # below, which resolves the participant the same way (first matching row).
    trial_to_pid = {
        str(r[trial_field]): r["participant_id"]
        for r in available_trials.to_dict("records")
    }

    # Populated once the ⇅ popover has rendered (below), and read by the option
    # labels — so an active ordering is *visible* in the picker itself rather than
    # only inside the popover that set it.
    sort_values: Dict[str, str] = {}

    def _option_label(value: str) -> str:
        marks = annotation_markers(trial_to_pid.get(value), value)
        base = _trial_display_label(value)
        label = f"{marks} {base}" if marks else base
        shown = sort_values.get(value)
        return f"{label}  ·  {shown}" if shown else label

    n_trials = len(trial_options)
    picker_label = "Trial ID"
    trial_id_key = f"{key_prefix}_trial_id" if key_prefix else None
    slider_key = f"{key_prefix}_trial_pos" if key_prefix else "trial_pos"

    # The selectbox (`*_trial_id`) is the canonical selection — the deep-link /
    # Save-&-restore code seeds it (`_restore_selection`). The slider mirrors it
    # and ◀ ▶ step it; all stay in sync via the trial id.
    current_label = st.session_state.get(trial_id_key) if trial_id_key else None
    if current_label not in trial_options:
        current_label = trial_options[0]
        if trial_id_key:
            st.session_state[trial_id_key] = current_label

    idx_of = {opt: i for i, opt in enumerate(trial_options)}

    if n_trials > 1:
        # Mirror the slider to the current selection BEFORE it renders, so picking
        # a trial in the dropdown moves the slider too; the drag callback writes
        # the selectbox key, reconciling next run.
        st.session_state[slider_key] = current_label

        def _on_trial_slider() -> None:
            if trial_id_key:
                st.session_state[trial_id_key] = st.session_state[slider_key]

        def _step_trial(delta: int) -> None:
            # ◀ / ▶ : move the canonical selection one trial earlier/later.
            if not trial_id_key:
                return
            try:
                pos = trial_options.index(st.session_state.get(trial_id_key))
            except ValueError:
                pos = 0
            st.session_state[trial_id_key] = trial_options[
                max(0, min(pos + delta, n_trials - 1))
            ]

        def _slider_label(value: str) -> str:
            # index/TOTAL first, then the id — the slider doubles as the counter,
            # so a separate "Trial X / N" caption is redundant.
            return f"{idx_of.get(value, 0) + 1}/{n_trials}  ·  {_option_label(value)}"

        # One row: [selectbox] [slider] [◀][▶][⇅] — arrows adjacent at the end,
        # then the UX-10 sort popover.
        sel_col, slider_col, prev_col, next_col, sort_col = host.columns(
            [3, 5, 0.55, 0.55, 0.55], vertical_alignment="bottom"
        )
        # UX-10: order the pool *before* the widgets read `trial_options`, so the
        # selectbox, the slider and the ◀ ▶ steps all walk the same order. The
        # canonical selection is a trial *id*, so re-sorting never changes which
        # trial is selected — only where it sits in the list.
        sort_key, sort_desc, sort_choice = _render_trial_sort_popover(
            sort_col,
            combos,
            trial_field,
            key_prefix,
            words=words,
            fixations=fixations,
        )
        if sort_key is not None:
            trial_options = sort_trial_options(
                trial_options, sort_key, descending=sort_desc
            )
            idx_of = {opt: i for i, opt in enumerate(trial_options)}
            lookup = sort_key.to_dict()
            sort_values.update(
                {opt: format_sort_value(lookup.get(opt)) for opt in trial_options}
            )
            picker_label = f"Trial ID  ·  by {sort_choice} {'↓' if sort_desc else '↑'}"
        current_idx = trial_options.index(current_label)
    else:
        sel_col = host

    # The label is shown so its help "?" icon (the type-to-search hint) is visible
    # — a collapsed label hides it.
    selected_trial_label = sel_col.selectbox(
        picker_label,
        options=trial_options,
        key=trial_id_key,
        format_func=_option_label,
        help="💡 Click, then start typing to narrow down the trial list. "
        "★ favorite · 🏷️ tagged · 📝 has notes. When a sort key is active, each "
        "option ends with that trial's value for it.",
    )

    if n_trials > 1:
        with slider_col:
            st.select_slider(
                "Trial",
                options=trial_options,
                key=slider_key,
                on_change=_on_trial_slider,
                help=f"Scrub through the {n_trials} trials (index/total · id, "
                "plus the sort value when one is active); the dropdown jumps to "
                "a specific id.",
                label_visibility="collapsed",
                format_func=_slider_label,
            )
        prev_col.button(
            "◀",
            key=f"{key_prefix}_prev_trial" if key_prefix else "prev_trial",
            on_click=_step_trial,
            args=(-1,),
            disabled=current_idx == 0,
            help="Previous trial",
            width="stretch",
        )
        next_col.button(
            "▶",
            key=f"{key_prefix}_next_trial" if key_prefix else "next_trial",
            on_click=_step_trial,
            args=(1,),
            disabled=current_idx == n_trials - 1,
            help="Next trial",
            width="stretch",
        )

    if not selected_trial_label:
        return None, None, None

    chosen = available_trials[
        available_trials[trial_field].astype(str) == selected_trial_label
    ].iloc[0]
    selected_text = str(chosen[text_field]) if text_field in chosen.index else None
    return chosen["participant_id"], chosen["trial_id"], selected_text


_COMPONENT_LABELS = {
    "participant_id": "Participant",
    "unique_text_id": "Text",
    "text_id": "Text",
    "unique_paragraph_id": "Text",
    "paragraph_id": "Text",
}


def _component_label(col: str) -> str:
    return _COMPONENT_LABELS.get(col, col)


def _composite_columns_for(combos: pd.DataFrame) -> list[str]:
    """Composite trial-id component columns that are actually present in
    ``combos`` — empty unless the trial id was built from several columns
    (set in ``app.prepare_data`` / preserved by ``data._preserve_composite_columns``)."""
    cols = st.session_state.get("_composite_trial_columns") or []
    return [c for c in cols if c in combos.columns]


def _select_trial_composite_mode(
    combos: pd.DataFrame,
    component_cols: list[str],
    text_field: str,
    key_prefix: str,
    picker_host=None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Trial selection when the trial id was composed from several columns.

    Renders one cascading selector per component (each narrowed by the previous
    picks), mirroring the Text / Participant modes instead of a single opaque
    ``a_b_c`` dropdown. Selectors render into ``picker_host`` (the column between
    Browse-by and Filter), defaulting to the current container.

    ``component_cols`` is already pruned (in ``select_trial``) to the canonical
    identity components — dataset-specific condition columns (e.g.
    ``repeated_reading_trial``) are dropped so the trial selectors stay the same
    across datasets; those narrow via the **More** filters instead (UX-5). Any
    residual ambiguity falls to the "Reading" selector below."""
    host = picker_host if picker_host is not None else st
    host.caption("Composite trial id — pick each part to narrow to a trial.")
    filtered = combos
    for col in component_cols:
        options = sorted(filtered[col].dropna().astype(str).unique())
        if not options:
            st.warning("No trials available after filtering.")
            return None, None, None
        state_key = (
            f"{key_prefix}_composite_{col}" if key_prefix else f"composite_{col}"
        )
        # A change to an earlier selector can drop the stored value out of this
        # selector's (now narrower) option set — clear it so st.selectbox falls
        # back to the first valid option instead of raising.
        if state_key in st.session_state and st.session_state[state_key] not in options:
            del st.session_state[state_key]
        chosen = host.selectbox(_component_label(col), options=options, key=state_key)
        filtered = filtered[filtered[col].astype(str) == str(chosen)]
        if filtered.empty:
            st.warning("No trial matches the selected combination.")
            return None, None, None

    candidates = filtered.drop_duplicates(subset=["trial_id"]).sort_values("trial_id")
    if candidates.empty:
        return None, None, None
    if len(candidates) > 1:
        # The components didn't fully determine a single trial — offer the
        # remaining ones, like the other modes' "Reading" selector.
        trial_options = candidates["trial_id"].astype(str).tolist()
        trial_to_pid = {
            str(r["trial_id"]): r["participant_id"]
            for r in candidates.to_dict("records")
        }

        def _reading_label(value: str) -> str:
            marks = annotation_markers(trial_to_pid.get(value), value)
            base = _trial_display_label(value)
            return f"{marks} {base}" if marks else base

        selected_trial = host.selectbox(
            "Reading (multiple trials available)",
            options=trial_options,
            key=f"{key_prefix}_composite_reading"
            if key_prefix
            else "composite_reading",
            format_func=_reading_label,
            help="More than one trial shares these values. "
            "★ favorite · 🏷️ tagged · 📝 has notes.",
        )
        row = candidates[
            candidates["trial_id"].astype(str) == str(selected_trial)
        ].iloc[0]
    else:
        row = candidates.iloc[0]
        selected_trial = row["trial_id"]

    text = str(row[text_field]) if text_field in row.index else None
    return row["participant_id"], selected_trial, text


def select_trial(
    combos: pd.DataFrame,
    key_prefix: str = "",
    picker_host=None,
    filter_cols: Optional[Iterable[str]] = None,
    *,
    words: Optional[pd.DataFrame] = None,
    fixations: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
    """Pick a specific trial from the (already-narrowed) pool.

    There are no Browse-by modes anymore: the pool is narrowed by the inline
    **Narrow by** Text / Participant multiselects + the **More** filters
    (``controls.render_narrow_by`` / ``render_trial_filters``), and this picks one
    trial via a selectbox + slider + ◀ ▶ arrows. A composite trial id (built from
    several mapped columns) instead renders one cascading selector per component.

    ``picker_host`` is the container to render into (defaults to the current one);
    the picker builds its own row of columns, so call it where columns are allowed.

    ``filter_cols`` lists the dataset's condition-filter columns (those offered in
    the **More** popover). Composite components that are also filter columns are
    dropped from the cascading selectors so the trial picker stays identical across
    datasets — those columns narrow via **More** instead (UX-5).

    ``words`` / ``fixations`` (optional) are the frames ``combos`` was built from;
    passing them unlocks the UX-10 ⇅ sort popover's computed keys (fixation count,
    reading time). Without them the sort still offers the column-based orderings.

    Returns:
        Tuple of (participant_id, trial_id, selection_mode, selected_text).
        ``selection_mode`` is always ``"Trial"`` (kept for the comparison-options
        builder, which still supports the other modes when called directly).
    """
    if combos.empty:
        st.warning("No trials available after filtering.")
        st.stop()

    trial_field = (
        "unique_trial_id" if "unique_trial_id" in combos.columns else "trial_id"
    )
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"

    composite_cols = _composite_columns_for(combos)
    # Drop condition-filter components (e.g. repeated_reading_trial) — they narrow
    # via the More popover, not a dedicated trial selector, so the picker is the
    # same across datasets (UX-5). What's left is the canonical identity cascade.
    filter_set = set(filter_cols or [])
    display_cols = [c for c in composite_cols if c not in filter_set]
    if len(display_cols) >= 2:
        participant, trial, text = _select_trial_composite_mode(
            combos, display_cols, text_field, key_prefix, picker_host=picker_host
        )
    else:
        participant, trial, text = _select_trial_none_mode(
            combos,
            trial_field,
            text_field,
            key_prefix,
            picker_host=picker_host,
            words=words,
            fixations=fixations,
        )

    return participant, trial, "Trial", text


# -----------------------------------------------------------------------------
# Statistics and metadata
# -----------------------------------------------------------------------------


def compute_trial_stats(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> Dict[str, float]:
    """Compute summary statistics for a single trial."""
    total_time = None
    if "trial_dwell_time_ms" in trial_words.columns:
        dwell_values = (
            pd.to_numeric(trial_words["trial_dwell_time_ms"], errors="coerce")
            .dropna()
            .unique()
        )
        if len(dwell_values):
            total_time = float(dwell_values[0])
    if total_time is None:
        total_time = (
            float(trial_fixations["duration_ms"].sum())
            if not trial_fixations.empty
            else 0.0
        )
    return dict(
        total_reading_time_ms=total_time,
        total_reading_time_s=total_time / 1000.0,
        word_count=int(len(trial_words)),
        fixation_count=int(len(trial_fixations)),
    )


def gather_trial_metadata(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame, fields: Iterable[str]
) -> pd.DataFrame:
    """Gather metadata for selected fields from words and fixations."""
    rows = []
    for field in fields:
        if field in trial_words.columns:
            series = pd.Series(trial_words[field])
        elif field in trial_fixations.columns:
            series = pd.Series(trial_fixations[field])
        else:
            continue

        cleaned = series.dropna()
        if cleaned.empty:
            value = "—"
        else:
            unique_values = cleaned.unique()
            if len(unique_values) == 1:
                value = unique_values[0]
            else:
                numeric_series = pd.to_numeric(cleaned, errors="coerce")
                numeric_values = numeric_series.dropna()
                is_numeric = (
                    not pd.api.types.is_bool_dtype(cleaned)
                    and (
                        pd.api.types.is_numeric_dtype(cleaned)
                        or len(numeric_values) == len(cleaned)
                    )
                    and not numeric_values.empty
                )
                if is_numeric:
                    value = f"mean={numeric_values.mean():.2f}, std={numeric_values.std():.2f}"
                else:
                    modes = cleaned.mode(dropna=True)
                    mode_value = modes.iloc[0] if not modes.empty else "—"
                    value = f"{mode_value} (mode, {len(unique_values)} unique)"
        rows.append({"Field": field, "Value": value})

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Value"] = df["Value"].astype(str)
    return df


def safe_summary(series: pd.Series) -> dict:
    """Compute summary statistics for a series, handling empty data."""
    if series.empty:
        nan_val = float("nan")
        return dict(mean=nan_val, std=nan_val, min=nan_val, max=nan_val, median=nan_val)
    return dict(
        mean=float(series.mean()),
        std=float(series.std(ddof=0)),
        min=float(series.min()),
        max=float(series.max()),
        median=float(series.median()),
    )


# -----------------------------------------------------------------------------
# Comparison helpers
# -----------------------------------------------------------------------------


# Markers shown beside comparison-trial options.
SAME_TEXT_MARKER = (
    "📄"  # same stimulus text as the primary trial (★ reserved for favorites, UX-6)
)
SAME_PARTICIPANT_MARKER = "👤"  # same participant as the primary trial


def _compare_option_label(
    participant_id: str,
    trial_id: str,
    markers: str,
    used_labels: set[str],
) -> str:
    """Selectbox label for a comparison option: ``"<markers> <trial_id>"``.

    De-duplicates on ``trial_id`` (two participants can share one) by appending
    the participant in brackets, so the label stays a unique selectbox option /
    dict key in ``tabs._render_compare_selector``."""
    trial_str = str(trial_id) if trial_id is not None else ""
    prefix = f"{markers} " if markers else ""
    label = f"{prefix}{trial_str}"
    if label in used_labels:
        label = f"{prefix}{trial_str} [{participant_id}]"
    used_labels.add(label)
    return label


def friendly_trial_label(
    participant_id: str,
    trial_id: str,
    text_id: Optional[str],
    existing_labels: set[str],
    prefix: str = "",
) -> str:
    """Create a short, de-duplicated label for comparison dropdowns/legends."""
    trial_str = str(trial_id) if trial_id is not None else ""
    text_str = str(text_id) if text_id is not None else ""
    text_str = text_str.strip()
    trial_contains_text = text_str and text_str.lower() in trial_str.lower()

    if text_str:
        base = f"{text_str} · {participant_id}"
        if not trial_contains_text:
            base = f"{base} (trial {trial_str})" if trial_str else base
        elif trial_str != text_str:
            # Surface any trial_id suffix beyond the text id (e.g. a
            # repeat-reading "_r2" tag added during normalization). Without
            # this the primary and compare titles look identical when a
            # participant re-read the same text.
            extra = trial_str
            if extra.lower().startswith(text_str.lower()):
                extra = extra[len(text_str) :].lstrip("_- ")
            if extra:
                base = f"{text_str} ({extra}) · {participant_id}"
    else:
        base = f"{trial_str} · {participant_id}" if trial_str else participant_id

    label = f"{prefix}{base}"
    if label in existing_labels:
        label = f"{prefix}{base} [{trial_str or 'trial'}]"
    existing_labels.add(label)
    return label


def build_comparison_options(
    combos: pd.DataFrame,
    selection_mode: str,
    primary_participant: str,
    primary_trial: str,
    primary_text: Optional[str],
) -> list[Tuple[str, str, str, str]]:
    """Build a prioritized list of comparison-trial options.

    Returns ``(participant_id, trial_id, label, markers)`` tuples, where
    ``markers`` leads with the relation icons ``"📄"`` (same text) / ``"👤"`` (same
    participant) and then the trial's annotation markers ``★`` (favorite) / ``🏷️``
    (tagged) / ``📝`` (noted) when present (UX-6), and ``label`` is
    ``"<markers> <trial_id>"``. Ordered: same-text (📄) first, then same-participant
    (👤), then the rest. A trial that is BOTH same-text and same-participant sorts
    with the 📄 group (text-matches lead) and shows both markers.
    """
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    uniq = combos.drop_duplicates(subset=["participant_id", "trial_id"])

    rows: list[dict] = []
    for row in uniq.itertuples():
        if (row.participant_id, row.trial_id) == (primary_participant, primary_trial):
            continue
        text_id = getattr(row, text_field, "")
        same_text = bool(primary_text and str(text_id) == str(primary_text))
        same_participant = bool(str(row.participant_id) == str(primary_participant))
        markers = (
            (SAME_TEXT_MARKER if same_text else "")
            + (SAME_PARTICIPANT_MARKER if same_participant else "")
            + annotation_markers(row.participant_id, row.trial_id)
        )
        rows.append(
            {
                "participant_id": row.participant_id,
                "trial_id": row.trial_id,
                "same_text": same_text,
                "same_participant": same_participant,
                "markers": markers,
            }
        )

    # ★ group first, then 👤 group, then the rest. same_text is the primary sort
    # key so a both-★-👤 trial leads the ★ group. Stable sort preserves combos
    # order within a group.
    rows.sort(
        key=lambda r: (0 if r["same_text"] else 1, 0 if r["same_participant"] else 1)
    )

    used_labels: set[str] = set()
    options: list[Tuple[str, str, str, str]] = []
    for r in rows:
        label = _compare_option_label(
            r["participant_id"], r["trial_id"], r["markers"], used_labels
        )
        options.append((r["participant_id"], r["trial_id"], label, r["markers"]))
    return options
