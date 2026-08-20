"""Utility functions for trial selection, statistics, and labelling."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
import streamlit as st

from .annotations import get_entry
from .constants import SELECTOR_ROW_GRID, SELECTOR_ROW_TRIO
from .data import frame_fingerprint
from .fields import labeled

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
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    """Build participant/trial/text combinations for selection UI.

    Returns:
        Tuple of (combos DataFrame, label list, label-to-combo mapping).

    Cached on a cheap fingerprint of the frame + the composite-trial columns, so
    the full-frame ``drop_duplicates`` + label build don't re-run on every rerun
    (e.g. selecting a different trial). The session-state read happens here, in
    the un-cached wrapper, and is threaded into the cached core as an argument.
    """
    composite_cols = tuple(st.session_state.get("_composite_trial_columns") or [])
    return build_combo_options_for(fixations, composite_cols)


def build_combo_options_for(
    fixations: pd.DataFrame,
    composite_cols: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    """`build_combo_options` for a frame that is **not** the active dataset.

    CMP-8 §2: a comparison source has its own composite-trial columns, so the
    session-state read in `build_combo_options` would answer for the wrong
    dataset. Everything else — the cache key, the cached core — is shared.
    """
    composite_cols = tuple(composite_cols or ())
    return _build_combo_options_cached(
        fixations,
        composite_cols,
        cache_key=(frame_fingerprint(fixations), composite_cols),
    )


@st.cache_data(show_spinner="Building trial list…")
def _build_combo_options_cached(
    _fixations: pd.DataFrame,
    composite_cols: tuple[str, ...],
    cache_key,
) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
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
    # picker can detect a composite id and cascade on identity (see select_trial).
    for col in composite_cols:
        if col in fixations.columns and col not in combo_cols:
            combo_cols.append(col)

    # UX-24: preserve each trial's first appearance before the historical
    # participant/id sort. The visible pool may still default to Trial ID, but
    # the ⇅ menu can now reconstruct source-file order exactly.
    combos = fixations[combo_cols].drop_duplicates().copy()
    combos["_data_order"] = np.arange(len(combos), dtype=int)
    combos = combos.rename(columns={trial_col: "trial_id"})
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
def _trial_positions(_frame: pd.DataFrame, cache_key) -> dict[tuple[str, str], object]:
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
    "Min timestamp in trial": ("fixations", "timestamp_min"),
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

# Event/geometry fields can occasionally be constant by accident (for example a
# one-fixation trial), but that does not make them trial metadata. Keep them out
# of the generic metadata tail; computed timing/count keys above are the useful
# sortable representation of those event columns.
_TRIAL_SORT_EXCLUDED_COLS = {
    "trial_id",
    "unique_trial_id",
    "word",
    "token",
    "text",
    "sentence",
    "question",
    "answer",
    "response",
    "x",
    "y",
    "x_start",
    "x_end",
    "y_start",
    "y_end",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "width",
    "height",
    "timestamp",
    "timestamp_ms",
    "duration",
    "duration_ms",
    "order_in_trial",
    "fixation_index",
    "word_index",
    "word_id",
    "ia_id",
    "char_index",
    "line_index",
    "source_file",
}
_TRIAL_SORT_PRIVATE_NAME_PARTS = (
    "path",
    "filepath",
    "filename",
    "directory",
    "folder",
    "url",
    "uri",
)
_TRIAL_SORT_GEOMETRY_SUFFIXES = (
    "_x",
    "_y",
    "_xmin",
    "_xmax",
    "_ymin",
    "_ymax",
    "_x_start",
    "_x_end",
    "_y_start",
    "_y_end",
    "_width",
    "_height",
)


def _trial_sort_column_allowed(column: object) -> bool:
    """Whether ``column`` can be discovered as generic trial metadata."""
    name = str(column)
    lower = name.lower()
    if name.startswith("_") or lower in _TRIAL_SORT_EXCLUDED_COLS:
        return False
    if lower.endswith(_TRIAL_SORT_GEOMETRY_SUFFIXES):
        return False
    return not any(part in lower for part in _TRIAL_SORT_PRIVATE_NAME_PARTS)


def _effective_trial_field(
    frame: pd.DataFrame | None, trial_field: str, picker_ids: set[str]
) -> str | None:
    """Find the frame column that names the picker's effective trial ids."""
    if frame is None or frame.empty:
        return None
    for field in (trial_field, "unique_trial_id", "trial_id"):
        if field not in frame.columns:
            continue
        values = set(frame[field].dropna().astype(str).unique())
        if values & picker_ids:
            return field
    return None


def _is_missing_scalar(value) -> bool:
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def _same_sort_value(left, right) -> bool:
    """Scalar equality for reconciling the words and fixations tables."""
    if _is_missing_scalar(left) or _is_missing_scalar(right):
        # Partial missingness is not a conflict; the table carrying a value wins.
        return True
    try:
        equal = left == right
    except (TypeError, ValueError):
        return False
    return bool(equal) if isinstance(equal, (bool, np.bool_)) else False


def _looks_like_free_text(series: pd.Series) -> bool:
    """Reject prose-like cells while retaining ordinary categorical metadata."""
    values = [str(v).strip() for v in series if not _is_missing_scalar(v)]
    return bool(values) and any(len(v) > 200 or len(v.split()) > 24 for v in values)


def _trial_level_columns_from_frame(
    frame: pd.DataFrame | None,
    trial_field: str,
    picker_ids: set[str],
    participants: set[str],
) -> dict[str, pd.Series]:
    """Discover one scalar value per active trial directly from one source table.

    Grouping includes participant identity, preventing repeated plain trial ids
    from being merged before the active picker scope is applied. The returned
    Series uses the picker's effective id because that is what
    ``sort_trial_options`` consumes.
    """
    identity = _effective_trial_field(frame, trial_field, picker_ids)
    if frame is None or frame.empty or identity is None:
        return {}

    scoped = frame
    if participants and "participant_id" in scoped.columns:
        scoped = scoped[scoped["participant_id"].astype(str).isin(participants)]
    scoped = scoped[scoped[identity].astype(str).isin(picker_ids)]
    if scoped.empty:
        return {}

    group_cols = [identity]
    if "participant_id" in scoped.columns and identity != "participant_id":
        group_cols.insert(0, "participant_id")
    grouped = scoped.groupby(group_cols, sort=False, dropna=False)
    discovered: dict[str, pd.Series] = {}
    for col in scoped.columns:
        if col == identity or not _trial_sort_column_allowed(col):
            continue
        try:
            if (grouped[col].nunique(dropna=False) > 1).any():
                continue
            if col in group_cols:
                values = scoped[group_cols].drop_duplicates().copy()
            else:
                values = grouped[col].agg(lambda cells: cells.iloc[0]).reset_index()
            # If the same effective id survives for multiple participants, it is
            # usable only when those rows agree. A participant-narrowed picker
            # naturally has one row here; a global ambiguous picker is not
            # allowed to choose one participant silently.
            by_id = values.groupby(values[identity].astype(str), sort=False)[col]
            if (by_id.nunique(dropna=False) > 1).any():
                continue
            deduped = values.drop_duplicates(subset=[identity])
        except (TypeError, ValueError):
            # Nested/list-like event payloads are not sortable scalar metadata.
            continue
        series = pd.Series(
            deduped[col].to_numpy(),
            index=deduped[identity].astype(str).to_numpy(),
        )
        if series.dropna().empty or _looks_like_free_text(series):
            continue
        discovered[str(col)] = series
    return discovered


def _merge_trial_level_sources(
    sources: Iterable[dict[str, pd.Series]],
) -> dict[str, pd.Series]:
    """Merge compatible metadata sources; omit cross-table disagreements."""
    by_column: dict[str, list[pd.Series]] = {}
    for source in sources:
        for col, series in source.items():
            by_column.setdefault(col, []).append(series)

    merged: dict[str, pd.Series] = {}
    for col, series_list in by_column.items():
        combined = pd.Series(dtype=object)
        conflict = False
        for series in series_list:
            current = series.copy()
            current.index = current.index.astype(str)
            for trial_id in combined.index.intersection(current.index):
                if not _same_sort_value(combined[trial_id], current[trial_id]):
                    conflict = True
                    break
            if conflict:
                break
            # pandas warns when concatenation/combine_first has to infer a
            # dtype from an empty object Series. The first real source needs no
            # merge at all; starting from it also preserves its native dtype.
            combined = current if combined.empty else combined.combine_first(current)
        if not conflict and not combined.empty:
            merged[col] = combined
    return merged


@st.cache_data(show_spinner=False)
def _trial_level_sort_columns_cached(
    _combos: pd.DataFrame,
    _words: pd.DataFrame | None,
    _fixations: pd.DataFrame | None,
    trial_field: str,
    cache_key,
) -> dict[str, pd.Series]:
    """Cached metadata discovery over the participant-scoped picker frames."""
    del cache_key  # explicit hash input for the underscore-prefixed frames
    if _combos is None or _combos.empty or trial_field not in _combos.columns:
        return {}
    picker_ids = set(_combos[trial_field].dropna().astype(str).unique())
    participants = (
        set(_combos["participant_id"].dropna().astype(str).unique())
        if "participant_id" in _combos.columns
        else set()
    )
    return _merge_trial_level_sources(
        (
            _trial_level_columns_from_frame(
                _combos, trial_field, picker_ids, participants
            ),
            _trial_level_columns_from_frame(
                _words, trial_field, picker_ids, participants
            ),
            _trial_level_columns_from_frame(
                _fixations, trial_field, picker_ids, participants
            ),
        )
    )


def _trial_level_sort_columns(
    combos: pd.DataFrame,
    trial_field: str,
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
) -> dict[str, pd.Series]:
    return _trial_level_sort_columns_cached(
        combos,
        words,
        fixations,
        trial_field,
        cache_key=(
            frame_fingerprint(combos),
            frame_fingerprint(words),
            frame_fingerprint(fixations),
            trial_field,
        ),
    )


def _per_trial_stat(frame: pd.DataFrame, trial_field: str, how: str) -> pd.Series:
    """One computed stat per trial id, as a Series indexed by that id."""
    if frame is None or frame.empty or trial_field not in frame.columns:
        return pd.Series(dtype=float)
    grouped = frame.groupby(frame[trial_field].astype(str), sort=False)
    if how == "size":
        return grouped.size().astype(float)
    if how == "timestamp_min":
        if "timestamp_ms" not in frame.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(grouped["timestamp_ms"].min(), errors="coerce").astype(
            float
        )
    if "duration_ms" not in frame.columns:
        return pd.Series(dtype=float)
    durations = grouped["duration_ms"].agg("sum" if "sum" in how else "mean")
    return (durations / 1000.0) if how.endswith("_s") else durations.astype(float)


def trial_sort_keys(
    combos: pd.DataFrame,
    trial_field: str,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
) -> dict[str, pd.Series]:
    """Available sort keys (UX-10): label → Series indexed by trial id.

    Offers a computed stat only when the frame it needs is present, and a column
    only when it is actually trial-level in the active participant-scoped words,
    fixations, or combo frame. This deliberately discovers metadata before the
    lossy combo projection can discard it.
    """
    keys: dict[str, pd.Series] = {}
    # This rank was captured before build_combo_options' canonical sort.
    if (
        combos is not None
        and not combos.empty
        and trial_field in combos.columns
        and "_data_order" in combos.columns
    ):
        deduped = combos.drop_duplicates(subset=[trial_field])
        keys["Data order"] = pd.Series(
            deduped["_data_order"].to_numpy(),
            index=deduped[trial_field].astype(str).to_numpy(),
        )
    for label, (which, how) in _TRIAL_SORT_STATS.items():
        frame = fixations if which == "fixations" else words
        picker_ids = (
            set(combos[trial_field].dropna().astype(str).unique())
            if combos is not None and not combos.empty and trial_field in combos.columns
            else set()
        )
        field = _effective_trial_field(frame, trial_field, picker_ids)
        series = _per_trial_stat(frame, field or trial_field, how)
        if not series.empty:
            keys[label] = series
    if combos is None or combos.empty or trial_field not in combos.columns:
        return keys
    discovered = _trial_level_sort_columns(combos, trial_field, words, fixations)
    ordered_cols = [c for c in _TRIAL_SORT_PREFERRED_COLS if c in discovered]
    ordered_cols.extend(sorted(set(discovered) - set(ordered_cols), key=str.casefold))
    for col in ordered_cols:
        if col == trial_field:
            continue
        keys[col.replace("_", " ").capitalize()] = discovered[col]
    return keys


def sort_trial_options(
    options: list[str],
    key_series: pd.Series | None,
    *,
    descending: bool = False,
) -> list[str]:
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

    A per-page trial id reads cleanly — ``Lit_Alchemist_4__page_07`` →
    ``Lit_Alchemist_4 · page 7`` (the id stays zero-padded so it sorts
    numerically; only the display drops the padding). Any other id passes
    through unchanged, so this is a no-op for every other corpus. MultiplEYE
    used to be the one producing those ids; since DATA-24 its pages are screens
    inside one trial, so this is now generic dressing for whatever ships them."""
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
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
) -> tuple[pd.Series | None, bool, str]:
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
        choice = labeled(
            st,
            "selectbox",
            "Sort trials by",
            options=options,
            key=state_key,
            help="Reorder the trial list by a computed statistic or by a reader, "
            "text or condition property.",
        )
        descending = labeled(
            st,
            "checkbox",
            "Descending",
            key=f"{key_prefix}_trial_sort_desc",
            help="Reverse the order.",
        )
    if choice == TRIAL_SORT_DEFAULT:
        return None, False, TRIAL_SORT_DEFAULT
    return keys[choice], bool(descending), choice


# --- CMP-13: one ◀ ▶ that advances both compared trials ----------------------
# The two pickers are built in different modules (A here, B in `tabs.py`), so the
# linked step is a callback on one side writing the *other* side's selection. It
# needs the other list, which is why each picker publishes what it just rendered.
# Both directions clamp independently: per the settled call, a side that has run
# out simply stays put while the other keeps stepping.

#: The ⚙️ Compare options checkbox that arms the link. UI-only — a navigation
#: control, not a render setting, so it is deliberately not on the share link or
#: in a saved config (same call as ``share_identity_mode``).
COMPARE_STEP_LINK_KEY = "single_compare_step_linked"

#: Scanpath B's canonical selection (a *label*; see the snapshot note below).
COMPARE_TRIAL_KEY = "single_compare_trial"

#: What the *Compare To* picker last rendered: ``(label, participant, trial)``
#: per candidate, in display order.
COMPARE_OPTIONS_SNAPSHOT_KEY = "_compare_options_snapshot"


def trial_options_snapshot_key(key_prefix: str) -> str:
    """Session key holding the trial picker's options as it last rendered them."""
    return f"_{key_prefix}_trial_options" if key_prefix else "_trial_options"


def compare_step_linked() -> bool:
    """True when ◀ ▶ should advance scanpath A **and** B (CMP-13).

    Both halves matter: the checkbox only exists while compare mode is on, and
    Streamlit drops an unrendered widget's key, so a stale ``True`` must not
    quietly steer the main picker once the user has left compare mode.
    """
    return bool(
        st.session_state.get("single_compare_toggle")
        and st.session_state.get(COMPARE_STEP_LINK_KEY)
    )


def step_within(options: list[str], state_key: str, delta: int) -> int | None:
    """Move ``state_key``'s selection ``delta`` places within ``options``.

    Clamped to the ends, and clamped *independently* of any other picker — the
    linked step is "advance both", not "keep them aligned": the two pools have
    different sizes (B excludes A, and a cross-dataset B is another corpus
    entirely), so their indices carry no shared meaning.

    Returns the new index, or ``None`` when there was nothing to step.
    """
    opts = list(options or [])
    if not opts:
        return None
    try:
        pos = opts.index(st.session_state.get(state_key))
    except ValueError:
        pos = 0
    new_pos = max(0, min(pos + delta, len(opts) - 1))
    st.session_state[state_key] = opts[new_pos]
    return new_pos


def at_list_end(options: list[str], state_key: str, delta: int) -> bool:
    """True when ``state_key``'s selection cannot move ``delta`` within ``options``.

    Used to decide whether a step button is dead. An unknown list answers
    **False** so the button stays live: a click that turns out to be a no-op is a
    better failure than a button greyed out while the other side could still move.
    """
    opts = list(options or [])
    if not opts:
        return False
    try:
        pos = opts.index(st.session_state.get(state_key))
    except ValueError:
        return False
    return not (0 <= pos + delta < len(opts))


def step_linked_compare(delta: int) -> None:
    """Advance scanpath **B** by ``delta``, resolved against the list A last saw.

    Written as an *identity* rather than an index or a label, because both are
    unstable across this step: ``build_comparison_options`` builds B's pool
    relative to A (📄 same-text first, then 👤 same-participant, A itself
    excluded), so once A moves, B's list is re-ordered *and* re-labelled — the
    same trial can gain or lose its 📄 marker. Parking the identity in the same
    pending slot the ``?compare=`` deep link uses lets the rebuilt picker re-find
    the trial the user was actually looking at.
    """
    from .session_keys import PENDING_COMPARE_STATE_KEY

    snapshot = list(st.session_state.get(COMPARE_OPTIONS_SNAPSHOT_KEY) or [])
    if not snapshot:
        return
    labels = [row[0] for row in snapshot]
    try:
        pos = labels.index(st.session_state.get(COMPARE_TRIAL_KEY))
    except ValueError:
        pos = 0
    _, participant, trial = snapshot[max(0, min(pos + delta, len(snapshot) - 1))]
    st.session_state[PENDING_COMPARE_STATE_KEY] = {
        "participant_id": participant,
        "trial_id": trial,
    }


def _select_trial_none_mode(
    combos: pd.DataFrame,
    trial_field: str,
    text_field: str,
    key_prefix: str,
    picker_host=None,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    leading_renderer=None,
    filter_renderer=None,
) -> tuple[str | None, str | None, str | None]:
    """The trial picker: **dataset + selectbox + scrubbing slider + ◀ ▶ steps + ⇅
    sort + 🔎 filters**, all on one row (UX-64). The slider thumb shows ``index/TOTAL · id``
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
    sort_values: dict[str, str] = {}

    def _option_label(value: str) -> str:
        marks = annotation_markers(trial_to_pid.get(value), value)
        base = _trial_display_label(value)
        label = f"{marks} {base}" if marks else base
        shown = sort_values.get(value)
        return f"{label}  ·  {shown}" if shown else label

    n_trials = len(trial_options)
    picker_label = "**Select Trial**"
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
            step_within(trial_options, trial_id_key, delta)
            # CMP-13: while the link is armed, the same ±1 also moves scanpath B.
            if compare_step_linked():
                step_linked_compare(delta)

        def _slider_label(value: str) -> str:
            # index/TOTAL first, then the id — the slider doubles as the counter,
            # so a separate "Trial X / N" caption is redundant.
            return f"{idx_of.get(value, 0) + 1}/{n_trials}  ·  {_option_label(value)}"

        # UX-64 — ONE row for everything: [dataset] [trial] [slider] [◀ ▶ ⇅ 🔎].
        # The Narrow-by row above it is gone; its filters live in the 🔎 popover
        # at the end of this row. The dataset picker keeps its width on purpose
        # (you may be comparing two datasets, and the label is what tells them
        # apart) — the slider gives up the room instead, and the filter is an
        # icon, which is what makes six controls fit.
        #
        # The three triggers share ONE trailing column as a `railbtn_*` cluster
        # (UX-27), which styles.py packs right at a uniform 3px spacing. A column
        # each put a full gutter between them, so a prev/next *pair* didn't read
        # as a pair.
        lead_col, sel_col, slider_col, trail_col = host.columns(
            SELECTOR_ROW_GRID, vertical_alignment="bottom"
        )
        if leading_renderer is not None:
            leading_renderer(lead_col)
        trail = trail_col.container(key=f"railbtn_{key_prefix}_trail")
        # Created in display order (◀ ▶ then ⇅) but filled out of order: the sort
        # popover has to render first, because the order it returns is what the
        # selectbox, the slider and the ◀ ▶ steps all walk.
        step_col = trail.container(key=f"railbtn_{key_prefix}_step")
        sort_col = trail.container(key=f"railbtn_{key_prefix}_sort")
        filter_col = trail.container(key=f"railbtn_{key_prefix}_filter")
        # Filled by the caller, which owns the filter widgets — but created here,
        # in display order, so 🔎 lands after ⇅ in the cluster (UX-64).
        if filter_renderer is not None:
            filter_renderer(filter_col)
        # UX-10: order the pool *before* the widgets read `trial_options`, so the
        # selectbox, the slider and the ◀ ▶ steps all walk the same order. The
        # canonical selection is a trial *id*, so re-sorting never changes which
        # trial is selected — only where it sits in the list.
        # UX-27: each of the three step/sort triggers goes in a `railbtn_*`
        # container so styles.py can give the whole cluster above the plot one
        # button shape — these were square (each `width="stretch"` inside its own
        # narrow column) beside pill-shaped labelled buttons on the rows above
        # and below.
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
            picker_label = (
                f"**Select Trial**  ·  by {sort_choice} {'↓' if sort_desc else '↑'}"
            )
        current_idx = trial_options.index(current_label)
    else:
        # A one-trial pool has no slider (`st.select_slider` throws on a single
        # option — BUG-23) and nothing to step through, but it still needs the
        # dataset picker and the filters: a pool of one is *usually the result of
        # a filter*, so this is exactly when the user reaches for them. UX-64.
        lead_col, sel_col, trail_col = host.columns(
            SELECTOR_ROW_TRIO, vertical_alignment="bottom"
        )
        if leading_renderer is not None:
            leading_renderer(lead_col)
        if filter_renderer is not None:
            filter_renderer(
                trail_col.container(key=f"railbtn_{key_prefix}_filter_solo")
            )

    # CMP-13: publish the list as rendered (post-sort), so the *Compare To*
    # picker's linked ◀ ▶ can step this picker without rebuilding its ordering.
    if trial_id_key:
        st.session_state[trial_options_snapshot_key(key_prefix)] = list(trial_options)

    # The label is shown so its help "?" icon (the type-to-search hint) is visible
    # — a collapsed label hides it.
    selected_trial_label = sel_col.selectbox(
        picker_label,
        options=trial_options,
        key=trial_id_key,
        format_func=_option_label,
        help="Click this dropdown, then type to narrow the list. "
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
        # Both step buttons in the keyed container reserved above, which styles.py
        # lays out as a flex ROW (a Streamlit vertical block stacks its children
        # by default).
        steps = step_col
        # CMP-13: linked, a button stays live until BOTH sides have run out — a
        # side at the end of its own list just stays put while the other keeps
        # stepping. `at_list_end` answers False for a list it can't see, so the
        # worst case is a click that moves only one scanpath.
        linked = compare_step_linked()
        compare_snapshot = (
            [
                row[0]
                for row in (st.session_state.get(COMPARE_OPTIONS_SNAPSHOT_KEY) or [])
            ]
            if linked
            else []
        )
        step_help = " Linked: also steps the compared trial." if linked else ""
        steps.button(
            "◀",
            key=f"{key_prefix}_prev_trial" if key_prefix else "prev_trial",
            on_click=_step_trial,
            args=(-1,),
            disabled=current_idx == 0
            and (not linked or at_list_end(compare_snapshot, COMPARE_TRIAL_KEY, -1)),
            help="Previous trial." + step_help,
        )
        steps.button(
            "▶",
            key=f"{key_prefix}_next_trial" if key_prefix else "next_trial",
            on_click=_step_trial,
            args=(1,),
            disabled=current_idx == n_trials - 1
            and (not linked or at_list_end(compare_snapshot, COMPARE_TRIAL_KEY, 1)),
            help="Next trial." + step_help,
        )

    if not selected_trial_label:
        return None, None, None

    chosen = available_trials[
        available_trials[trial_field].astype(str) == selected_trial_label
    ].iloc[0]
    selected_text = str(chosen[text_field]) if text_field in chosen.index else None
    return chosen["participant_id"], chosen["trial_id"], selected_text


def select_trial(
    combos: pd.DataFrame,
    key_prefix: str = "",
    picker_host=None,
    *,
    words: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
    leading_renderer=None,
    filter_renderer=None,
) -> tuple[str | None, str | None, str, str | None]:
    """Pick a specific trial from the (already-narrowed) pool.

    There are no Browse-by modes anymore, and no per-mapping variants either: the
    pool is narrowed by the inline **Narrow by** Text / Participant multiselects +
    the **More** filters (``controls.render_narrow_by`` /
    ``render_trial_filters``), and this always picks one trial via the same
    selectbox + slider + ◀ ▶ arrows — whatever the Trial ID mapping looks like.

    BUG-23: a composite trial id (built from several mapped columns) used to get a
    picker of its own — first one selector per mapped component, then a Participant
    → Text cascade. Both made the *shape of the mapping* visible in the UI, and
    neither offered the slider or the step buttons, so stepping through trials
    worked on some datasets and not others. Participant and Text are what **Narrow
    by** is for; the composite flag now only tells the chip strip to spell the
    joined id out (``tabs._render_trial_condition_chips``).

    ``picker_host`` is the container to render into (defaults to the current one);
    the picker builds its own row of columns, so call it where columns are allowed.

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

    participant, trial, text = _select_trial_none_mode(
        combos,
        trial_field,
        text_field,
        key_prefix,
        picker_host=picker_host,
        # UX-64: the row's lead cell (the dataset picker) and its 🔎 filter
        # popover are filled by the caller, which owns those widgets.
        leading_renderer=leading_renderer,
        filter_renderer=filter_renderer,
        words=words,
        fixations=fixations,
    )

    return participant, trial, "Trial", text


# -----------------------------------------------------------------------------
# Statistics and metadata
# -----------------------------------------------------------------------------


def compute_trial_stats(
    trial_words: pd.DataFrame, trial_fixations: pd.DataFrame
) -> dict[str, float]:
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
        word_count=len(trial_words),
        fixation_count=len(trial_fixations),
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
    text_id: str | None,
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
    primary_text: str | None,
    *,
    cross_dataset: bool = False,
) -> list[tuple[str, str, str, str]]:
    """Build a prioritized list of comparison-trial options.

    Returns ``(participant_id, trial_id, label, markers)`` tuples, where
    ``markers`` leads with the relation icons ``"📄"`` (same text) / ``"👤"`` (same
    participant) and then the trial's annotation markers ``★`` (favorite) / ``🏷️``
    (tagged) / ``📝`` (noted) when present (UX-6), and ``label`` is
    ``"<markers> <trial_id>"``. Ordered: same-text (📄) first, then same-participant
    (👤), then the rest. A trial that is BOTH same-text and same-participant sorts
    with the 📄 group (text-matches lead) and shows both markers.

    ``cross_dataset`` (CMP-8 §5.1) says ``combos`` describes a *different*
    dataset, and degrades the three id-based signals that would otherwise lie:
    two corpora do not share readers, so 👤 never fires; the annotation store is
    keyed on the **active** dataset's ids, so a foreign trial must not inherit
    another reader's ★; and the primary trial is not in this pool, so a
    coincidentally identical ``(participant, trial)`` is a real candidate rather
    than the trial being compared. 📄 survives — a text id that matches across
    corpora is exactly the pairing this feature exists for.
    """
    text_field = "unique_text_id" if "unique_text_id" in combos.columns else "text_id"
    uniq = combos.drop_duplicates(subset=["participant_id", "trial_id"])

    rows: list[dict] = []
    for row in uniq.itertuples():
        if not cross_dataset and (row.participant_id, row.trial_id) == (
            primary_participant,
            primary_trial,
        ):
            continue
        text_id = getattr(row, text_field, "")
        same_text = bool(primary_text and str(text_id) == str(primary_text))
        same_participant = not cross_dataset and bool(
            str(row.participant_id) == str(primary_participant)
        )
        markers = (
            (SAME_TEXT_MARKER if same_text else "")
            + (SAME_PARTICIPANT_MARKER if same_participant else "")
            + (
                ""
                if cross_dataset
                else annotation_markers(row.participant_id, row.trial_id)
            )
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
    options: list[tuple[str, str, str, str]] = []
    for r in rows:
        label = _compare_option_label(
            r["participant_id"], r["trial_id"], r["markers"], used_labels
        )
        options.append((r["participant_id"], r["trial_id"], label, r["markers"]))
    return options


# -----------------------------------------------------------------------------
# Cross-dataset comparison frames (CMP-8 · promoted from tabs.py for CMP-9)
# -----------------------------------------------------------------------------
# These live here, not in tabs.py, because three surfaces now build a
# cross-dataset comparison — the app, `api.compare_scanpaths` and
# `cli.render --compare-*` — and the namespacing rule below is the one piece of
# it that must not be re-derived per surface. `tests/test_compare_cross_dataset.py`
# exists because getting it wrong renders a *plausible-looking wrong figure*
# rather than an error.

#: Separator between a dataset name and a participant id in a qualified id.
COMPARE_DATASET_SEP = " · "


def qualify_for_compare(frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """A copy of ``frame`` whose ``participant_id`` is namespaced by ``dataset``.

    Two corpora can hold the same ``(participant_id, trial_id)``, and
    `plots.make_comparison_figure` slices its frame by exactly that pair — so an
    unqualified merge would silently render *the wrong scanpath*, or two.

    Only ever applied to the single-trial frames that feed the comparison
    builder. Nothing the annotations, the export slug, the deep link or Corpus
    Analysis reads goes through here: those key on the real ids, and must.
    """
    if frame.empty:
        return frame
    out = frame.copy()
    out["dataset"] = dataset
    out["participant_id"] = (
        dataset + COMPARE_DATASET_SEP + out["participant_id"].astype(str)
    )
    return out


def qualified_participant(dataset: str, participant: str) -> str:
    """The id `qualify_for_compare` gives ``participant`` inside ``dataset``."""
    return f"{dataset}{COMPARE_DATASET_SEP}{participant}"


def unqualify_for_export(frame: pd.DataFrame, participant: str) -> pd.DataFrame:
    """Undo `qualify_for_compare`'s rename, restoring the corpus' own id.

    The namespace exists so `make_comparison_figure` can slice two colliding
    ``(participant, trial)`` pairs apart. An exported table must carry the id the
    corpus actually uses, or it won't join back to anything (CMP-8 §6). The
    stamped ``dataset`` column is kept — that is what disambiguates the rows.
    """
    if frame is None or frame.empty or "dataset" not in frame.columns:
        return frame
    out = frame.copy()
    out["participant_id"] = str(participant)
    return out


def align_compare_columns(
    a: pd.DataFrame, b: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, frozenset]:
    """Reindex two frames onto their column **union**, and report shared numerics.

    A bare ``pd.concat`` of frames with disjoint columns warns and churns dtypes
    (int columns become float once the other frame's rows fill in as NaN), which
    matters here because two corpora rarely ship the same measure set. Aligning
    first keeps the concat quiet and the dtypes stable.

    The third element is the intersection of *numeric* columns — the metrics a
    cross-dataset figure may legitimately colour by (CMP-8 §5.4). A metric present
    in only one corpus would colour one panel and blank the other.
    """
    union = list(dict.fromkeys([*a.columns, *b.columns]))
    a_aligned = a.reindex(columns=union) if list(a.columns) != union else a
    b_aligned = b.reindex(columns=union) if list(b.columns) != union else b
    shared = frozenset(
        col
        for col in set(a.columns) & set(b.columns)
        if pd.api.types.is_numeric_dtype(a[col])
        and pd.api.types.is_numeric_dtype(b[col])
    )
    return a_aligned, b_aligned, shared
