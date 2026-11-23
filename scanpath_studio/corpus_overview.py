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
from .constants import ICONS, PLOTLY_CONFIG, plural
from .controls import _drop_stale
from .data import AOI_TRIAL_ID, carries_mapped_text, frame_fingerprint
from .plots import make_corpus_overview_figure
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


def _open_groups(measure_label: str) -> None:
    st.session_state[CORPUS_SUBTAB] = "Groups"
    st.session_state["groups_compare"] = True
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
    st.metric("Mean", _format_value(row["value"], measure))
    if pd.notna(row["hi"]) and row["hi"] > row["lo"]:
        unit = "Participant means" if group_by == "text" else "Reading means"
        st.write(
            f"{unit} ranged from **{_format_value(row['lo'], measure)}** to **{_format_value(row['hi'], measure)}**."
        )
    contributors = plural(int(row["n_readings"]), "reading")
    if group_by == "text":
        contributors += f" from {plural(int(row['n_participants']), 'participant')}"
    st.caption(
        f"{contributors} contributed. {int(row['n_values']):,} of "
        f"{int(row['n_word_rows']):,} word rows have a value."
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
        st.markdown(f"#### Mean by {group_by}")
        if group_by == "text":
            explanation = "Dots show text means. Lines span the lowest to highest participant mean."
        else:
            explanation = "Dots show participant means. Lines span the lowest to highest reading mean."
        st.caption(
            explanation
            + (" Rates are plotted from 0 to 1." if measure.is_rate else "")
            + " Select a point to inspect it."
        )
        if table["value"].notna().any():
            fig = make_corpus_overview_figure(
                table,
                group_col=field,
                measure_label=measure.axis_label,
                colors=colors,
                canvas_width=canvas_width,
                base_font_size=base_font_size,
                font_family=font_family,
            )
            # The chart shows the first measured rows of the ranked table. Keep
            # their typed IDs for the picker; Plotly uses strings for display.
            ids = table[field].iloc[: len(fig.data[0].x)].tolist()
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
            _show_table(table, field, grouped)
    st.caption(
        "Each reading contributes its mean across word rows with a finite value. "
        + (
            "When someone reads a text more than once, their readings are averaged first. Each participant then has equal weight."
            if group_by == "text"
            else "Each contributing reading has equal weight in its participant’s mean."
        )
    )
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


def _show_table(table: pd.DataFrame, field: str, grouped: str) -> None:
    names = active_all(st.session_state)
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            field: st.column_config.Column(grouped, help=names.display(field)),
            "value": "Mean",
            "lo": "Minimum",
            "hi": "Maximum",
            "n_readings": "Contributing readings",
            "n_participants": "Contributing participants",
            "n_values": "Word rows with values",
            "n_word_rows": "Word rows",
        },
    )
