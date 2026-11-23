"""The Corpus Analysis landing view and its links into the detailed analyses."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

import pandas as pd
import streamlit as st

from .aggregation import (
    MEASURES,
    Measure,
    available_measures,
    corpus_overview,
    corpus_text_column,
)
from .analysis_recipe import OVERVIEW_VIEW
from .column_names import active_all
from .computations import measure_description
from .constants import ICONS, PLOTLY_CONFIG, plural
from .controls import _drop_stale
from .data import AOI_TRIAL_ID, carries_mapped_text, frame_fingerprint
from .plots import OVERVIEW_VISIBLE_ROWS, make_corpus_overview_figure
from .session_keys import CORPUS_GROUP_BY, CORPUS_MEASURE, CORPUS_SUBTAB

PENDING_TEXT = "_corpus_overview_open_text"
GROUP_MEANS_VIEW = "Group means & difference"


@st.cache_data(show_spinner=False)
def _summary(
    _words: pd.DataFrame, words_key, measure_key: str, group_by: str
) -> pd.DataFrame:
    return corpus_overview(_words, MEASURES[measure_key], group_by)


def _open_profile(group_by: str, identifier, measure_label: str) -> None:
    state = st.session_state
    if group_by == "text":
        state[CORPUS_SUBTAB] = "Per text"
        state[PENDING_TEXT] = identifier
        state["ptext_view"] = "Cohort profile"
        state["ptext_measure"] = measure_label
    else:
        state[CORPUS_SUBTAB] = "Per participant"
        state["prdr_pid"] = str(identifier)
        state["prdr_view"] = "Distribution vs cohort"
        state["prdr_measure"] = measure_label


def keep_first_group() -> None:
    """Carry the first group's definition across the one- and two-group controls."""
    state = st.session_state
    adding = state["groups_compare"]
    source, target = ("pgrp", "cmp") if adding else ("cmp", "pgrp")
    mode = state.get(f"{source}_mode")
    if mode is None:
        return
    state[f"{target}_mode"] = mode
    if mode == "Split a field":
        field = state.get(f"{source}_field")
        if field is None:
            return
        if adding and field != state.get("cmp_field"):
            state.pop("cmp_b", None)
        state[f"{target}_field"] = field
        old_values, new_values = ("pgrp_g", "cmp_a") if adding else ("cmp_a", "pgrp_g")
        state[new_values] = state.get(old_values, [])
    else:
        old, new = (
            ("pgrp_set0_", "cmp_setA_") if adding else ("cmp_setA_", "pgrp_set0_")
        )
        for key in state:
            if key.startswith(old):
                state[new + key.removeprefix(old)] = state[key]


def _open_groups(measure_label: str) -> None:
    st.session_state[CORPUS_SUBTAB] = "Groups"
    if not st.session_state.get("groups_compare"):
        st.session_state["groups_compare"] = True
        keep_first_group()
    st.session_state["cmp_view"] = GROUP_MEANS_VIEW
    st.session_state["cmp_measure"] = measure_label


def _format_value(value: float, measure: Measure) -> str:
    if pd.isna(value):
        return "—"
    if measure.is_rate:
        return f"{value:.1%}"
    number = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {measure.unit}" if measure.unit else number


def _inspector(table: pd.DataFrame, field: str, group_by: str, measure: Measure):
    st.markdown(
        "#### Inspect a text" if group_by == "text" else "#### Inspect a participant"
    )
    ids = table[field].tolist()
    key = f"corpus_inspect_{group_by}"
    _drop_stale(key, ids)
    identifier = st.selectbox(
        group_by.capitalize(),
        ids,
        key=key,
        persist_state="session",
        label_visibility="collapsed",
    )
    row = table.loc[table[field].eq(identifier)].iloc[0]
    by_text = group_by == "text"
    st.metric(
        "Mean across participants" if by_text else "Mean across readings",
        _format_value(row["value"], measure),
        help=(
            "Each reading is one participant’s trial. First, average the measured words "
            "within each reading. "
            + (
                "Repeated readings of this text are averaged for each participant, "
                "then each participant contributes equally."
                if by_text
                else "Each reading then contributes equally to this participant’s mean."
            )
        ),
    )
    if pd.notna(row["hi"]) and row["hi"] > row["lo"]:
        unit = "Participant means" if group_by == "text" else "Reading means"
        st.write(
            f"{unit} ranged from **{_format_value(row['lo'], measure)}** to **{_format_value(row['hi'], measure)}**."
        )
    if row["n_values"]:
        contributors = plural(int(row["n_readings"]), "reading")
        if by_text:
            contributors += f" from {plural(int(row['n_participants']), 'participant')}"
        st.caption(
            f"{contributors} contributed. {int(row['n_values']):,} of "
            f"{int(row['n_word_rows']):,} word observations had a recorded value."
        )
    else:
        st.caption(
            f"This {group_by} has no recorded values for this measure. "
            f"Choose another {group_by} or reading measure."
        )
    st.button(
        "Open word profile" if group_by == "text" else "Open participant profile",
        icon=ICONS["open"],
        key="corpus_open_profile",
        on_click=_open_profile,
        args=(group_by, identifier, measure.label),
    )
    return identifier


def _inspect_point(chart_key: str, group_by: str, plotted_ids: list) -> None:
    # A deselection can arrive after changing tabs or replacing the chart.
    chart = st.session_state.get(chart_key)
    points = chart["selection"]["points"] if chart is not None else []
    if points:
        position = points[-1]["point_index"]
        if 0 <= position < len(plotted_ids):
            st.session_state[f"corpus_inspect_{group_by}"] = plotted_ids[position]


def render_corpus_overview(
    words: pd.DataFrame,
    *,
    download: Callable,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    colors: tuple[str, str],
) -> None:
    shared = words[AOI_TRIAL_ID].notna() if AOI_TRIAL_ID in words else None
    if shared is not None and shared.all():
        st.info(
            "The Words table supplies one set of values per stimulus, shared across readings. "
            "To compare readings here, supply word measurements for each participant and trial."
        )
        return
    measure_col, actions_col = st.columns([1, 1], vertical_alignment="bottom")
    actions = actions_col.container(
        horizontal=True, vertical_alignment="bottom", gap="medium"
    )
    keys = [m.key for m in available_measures(words, None, per_word_only=True)]
    _drop_stale(CORPUS_MEASURE, keys)
    key = measure_col.selectbox(
        "Reading measure",
        keys,
        format_func=lambda k: MEASURES[k].label,
        key=CORPUS_MEASURE,
        bind="query-params",
        persist_state="session",
    )
    measure = MEASURES[key]
    has_text = corpus_text_column(words) is not None and carries_mapped_text(words)
    groups = ["Text", "Participant"] if has_text else ["Participant"]
    _drop_stale(CORPUS_GROUP_BY, groups)
    grouped = actions.segmented_control(
        "Summarize by",
        groups,
        default=groups[0],
        required=True,
        key=CORPUS_GROUP_BY,
        bind="query-params",
        persist_state="session",
    )
    actions.button(
        "Compare groups",
        icon=ICONS["compare"],
        key="corpus_open_groups",
        on_click=_open_groups,
        args=(measure.label,),
        help="Compare this measure between two groups in the filtered trial pool.",
    )
    group_by = grouped.lower()
    st.caption(measure_description(measure.column))
    if not has_text:
        st.caption(
            "Map a Text ID in the Words table to compare texts across participants."
        )
    if shared is not None and shared.any():
        st.caption(
            "The summary excludes shared stimulus values copied across readings."
        )
    table = _summary(words, frame_fingerprint(words), key, group_by)
    if table.empty:
        st.info(
            f"No word rows have the IDs needed to summarize by {group_by} in this selection."
        )
        return
    field = table.columns[0]
    plot, detail = st.columns([2, 1], gap="medium")
    with detail.container(border=True, key="corpus_overview_detail"):
        selected = _inspector(table, field, group_by, measure)
    with plot.container(border=True, key="corpus_overview_plot"):
        st.markdown(f"#### {measure.label.partition(' — ')[0]} by {group_by}")
        if group_by == "text":
            explanation = "Each dot is a text’s mean across participants. Its line spans their lowest and highest means."
        else:
            explanation = "Each dot is a participant’s mean across readings. Its line spans their lowest and highest reading means."
        measured = table.loc[table["value"].notna()]
        if not measured.empty:
            st.caption(explanation + " Select a dot to inspect it.")
            # The summary is ranked. Keep the selected ID visible even when
            # the corpus is larger than one page of the chart.
            selected_rank = pd.Index(measured[field]).get_indexer([selected])[0]
            start = (
                max(0, selected_rank) // OVERVIEW_VISIBLE_ROWS * OVERVIEW_VISIBLE_ROWS
            )
            page = measured.iloc[start : start + OVERVIEW_VISIBLE_ROWS]
            if len(measured) > OVERVIEW_VISIBLE_ROWS:
                st.caption(
                    f"Showing ranks {start + 1:,}–{start + len(page):,} of {len(measured):,}. "
                    f"Choose a {group_by} in the inspector to see its rank."
                )
            fig = make_corpus_overview_figure(
                page,
                group_col=field,
                measure_label=measure.axis_label,
                as_percent=measure.is_rate,
                colors=colors,
                canvas_width=canvas_width,
                base_font_size=base_font_size,
                font_family=font_family,
            )
            ids = page[field].tolist()
            fig.update_traces(
                marker_symbol=["diamond" if i == selected else "circle" for i in ids]
            )
            chart_key = f"corpus_overview_chart_{group_by}"
            st.plotly_chart(
                fig,
                key=chart_key,
                width="stretch",
                config=PLOTLY_CONFIG,
                on_select=partial(_inspect_point, chart_key, group_by, ids),
                selection_mode="points",
                alt=f"{measure.axis_label} by {group_by}. {explanation}",
            )
        else:
            st.info("This measure has no recorded values in the selected readings.")
    with st.expander(
        f"Summary table · {plural(len(table), group_by)}",
        key="corpus_summary_table",
        on_change="rerun",
    ) as panel:
        if panel.open:
            _show_table(table, field, grouped, measure)
            if measure.is_rate:
                st.caption("The CSV stores rates as proportions from 0 to 1.")
    download(
        st,
        table,
        name=f"overview_by_{group_by}_{key}.csv",
        key="dl_corpus_overview",
        label="Download summary (CSV)",
        recipe=dict(
            view=OVERVIEW_VIEW, group_by=group_by, measure=measure, aggregation="mean"
        ),
    )


def _show_table(
    table: pd.DataFrame, field: str, grouped: str, measure: Measure
) -> None:
    names = active_all(st.session_state)
    unit = f" ({measure.unit})" if measure.unit else ""
    stats = {
        col: st.column_config.NumberColumn(
            label + unit, format="percent" if measure.is_rate else "%.2f"
        )
        for col, label in (("value", "Mean"), ("lo", "Minimum"), ("hi", "Maximum"))
    }
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            field: st.column_config.Column(grouped, help=names.display(field)),
            **stats,
            "n_readings": "Contributing readings",
            "n_participants": "Contributing participants",
            "n_values": "Words with a value",
            "n_word_rows": "Word observations",
        },
    )
