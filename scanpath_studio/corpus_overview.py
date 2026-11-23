"""The Corpus Analysis landing view and its links into the detailed analyses."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

import pandas as pd
import streamlit as st

from . import corpus_navigation
from .aggregation import MEASURES, Measure, available_measures, corpus_overview
from .analysis_recipe import OVERVIEW_VIEW
from .column_names import active_all
from .computations import measure_description
from .constants import ICONS, PLOTLY_CONFIG, plural
from .controls import _drop_stale, write_through
from .data import AOI_TRIAL_ID, frame_fingerprint
from .plots import OVERVIEW_VISIBLE_ROWS, make_corpus_overview_figure
from .session_keys import CORPUS_MEASURE

PENDING_TEXT = "_corpus_overview_open_text"
GROUP_MEANS_VIEW = "Group means & difference"


@st.cache_data(show_spinner=False)
def _summary(
    _words: pd.DataFrame, words_key, measure_key: str, group_by: str
) -> pd.DataFrame:
    return corpus_overview(_words, MEASURES[measure_key], group_by)


def _set_popover_choice(key: str, value) -> None:
    # The settings persist after their first render. A new key has no older
    # browser value to reassert against the user's first edit.
    state = st.session_state
    if key not in state or state[key] != value:
        write_through(key, value, shown=state.get(key, value))


def _open_profile(group_by: str, identifier, measure_label: str) -> None:
    state = st.session_state
    corpus_navigation.open_profile(group_by)
    if group_by == "text":
        if identifier is not None:
            state[PENDING_TEXT] = identifier
        _set_popover_choice("ptext_view", "Cohort profile")
        state["ptext_measure"] = measure_label
    else:
        if identifier is not None:
            state["prdr_pid"] = str(identifier)
        _set_popover_choice("prdr_view", "Distribution vs cohort")
        state["prdr_measure"] = measure_label


def keep_first_group() -> None:
    """Carry the first group's definition across the one- and two-group controls."""
    state = st.session_state
    adding = state["groups_compare"]
    source, target = ("pgrp", "cmp") if adding else ("cmp", "pgrp")
    mode = state.get(f"{source}_mode")
    if mode is None:
        return
    _set_popover_choice(f"{target}_mode", mode)
    if mode == "Split a field":
        field = state.get(f"{source}_field")
        if field is None:
            return
        if adding and field != state.get("cmp_field"):
            state.pop("cmp_b", None)
        _set_popover_choice(f"{target}_field", field)
        old_values, new_values = ("pgrp_g", "cmp_a") if adding else ("cmp_a", "pgrp_g")
        _set_popover_choice(new_values, state.get(old_values, []))
    else:
        old, new = (
            ("pgrp_set0_", "cmp_setA_") if adding else ("cmp_setA_", "pgrp_set0_")
        )
        for key in state:
            if key.startswith(old):
                _set_popover_choice(new + key.removeprefix(old), state[key])


def _format_value(value: float, measure: Measure) -> str:
    if pd.isna(value):
        return "—"
    if measure.is_rate:
        return f"{value:.1%}"
    number = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {measure.unit}" if measure.unit else number


def _selection_details(host, row: pd.Series, group_by: str, measure: Measure) -> None:
    if row["n_values"]:
        mean = _format_value(row["value"], measure)
        text = f"**{mean}** mean"
        if row["lo"] < row["hi"]:
            text += f" · {_format_value(row['lo'], measure)} to {_format_value(row['hi'], measure)}"
        host.markdown(text)
        counts = plural(int(row["n_readings"]), "reading")
        if group_by == "text":
            counts += f" from {plural(int(row['n_participants']), 'participant')}"
        host.caption(
            f"{counts} · {int(row['n_values']):,} of {int(row['n_word_rows']):,} word observations measured"
        )
    else:
        host.caption(f"This {group_by} has no recorded values for this measure.")


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
    group_by: str,
    profile_host,
    measure_host,
    download: Callable,
    canvas_width: int,
    base_font_size: int,
    font_family: str,
    colors: tuple[str, str],
) -> None:
    shared = words[AOI_TRIAL_ID].notna() if AOI_TRIAL_ID in words else None
    by_text = group_by == "text"
    profile_label = "Open word profile" if by_text else "Open participant profile"
    if shared is not None and shared.all():
        st.info(
            "The Words table supplies one set of values per stimulus, shared across readings. "
            "To compare readings here, supply word measurements for each participant and trial."
        )
        profile_host.button(
            profile_label,
            icon=ICONS["open"],
            on_click=corpus_navigation.open_profile,
            args=(group_by,),
        )
        return
    plot = st.container(key="corpus_overview_plot")
    keys = [m.key for m in available_measures(words, None, per_word_only=True)]
    _drop_stale(CORPUS_MEASURE, keys)
    key = measure_host.selectbox(
        "Reading measure",
        keys,
        format_func=lambda k: MEASURES[k].label,
        key=CORPUS_MEASURE,
        persist_state="session",
    )
    measure = MEASURES[key]
    contributors = "participants" if by_text else "readings"
    weighting = "Words with a recorded value are averaged within each reading. " + (
        "Repeated readings are averaged for each participant, then each participant contributes equally to the text mean."
        if by_text
        else "Each reading contributes equally to the participant mean."
    )
    plot.subheader(
        f"{measure.label.partition(' — ')[0]} by {group_by}",
        help=f"{measure_description(measure.column)}\n\n{weighting}",
        anchor=False,
    )
    if shared is not None and shared.any():
        plot.caption(
            "The summary excludes shared stimulus values copied across readings."
        )
    table = _summary(words, frame_fingerprint(words), key, group_by)
    if table.empty:
        plot.info(
            f"No word rows have the IDs needed to compare {group_by}s in this selection."
        )
        return
    field = table.columns[0]
    chart = plot.container()
    lookup = st.container(horizontal=True, vertical_alignment="center")
    ids = table[field].tolist()
    selection_key = f"corpus_inspect_{group_by}"
    if st.session_state.get(selection_key) is not None:
        _drop_stale(selection_key, ids)
    selected = lookup.selectbox(
        f"Find a {group_by}",
        ids,
        index=None,
        placeholder=f"Find a {group_by}…",
        key=selection_key,
        persist_state="session",
        label_visibility="collapsed",
        width=280,
    )
    profile_host.button(
        profile_label,
        key="corpus_open_profile",
        icon=ICONS["open"],
        on_click=_open_profile,
        args=(group_by, selected, measure.label),
    )
    if selected is not None:
        detail = lookup.container(key="corpus_overview_detail", width="stretch")
        _selection_details(
            detail,
            table.loc[table[field].eq(selected)].iloc[0],
            group_by,
            measure,
        )
    measured = table.loc[table["value"].notna()]
    if measured.empty:
        chart.info("This measure has no recorded values in the selected readings.")
    else:
        explanation = f"Dots show means. Lines show the range across {contributors}."
        rank = (
            pd.Index(measured[field]).get_indexer([selected])[0]
            if selected is not None
            else 0
        )
        start = max(0, rank) // OVERVIEW_VISIBLE_ROWS * OVERVIEW_VISIBLE_ROWS
        page = measured.iloc[start : start + OVERVIEW_VISIBLE_ROWS]
        if len(measured) > OVERVIEW_VISIBLE_ROWS:
            explanation += f" Showing ranks {start + 1:,}–{start + len(page):,} of {len(measured):,}."
        chart.caption(explanation + f" Select a dot to inspect a {group_by}.")
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
        # On touchscreens Plotly keeps its toolbar visible above the first point.
        fig.update_layout(margin_t=32)
        page_ids = page[field].tolist()
        if selected is not None:
            fig.update_traces(
                marker_symbol=[
                    "diamond" if i == selected else "circle" for i in page_ids
                ]
            )
        chart_key = f"corpus_overview_chart_{group_by}"
        chart.plotly_chart(
            fig,
            key=chart_key,
            width="stretch",
            config=PLOTLY_CONFIG,
            on_select=partial(_inspect_point, chart_key, group_by, page_ids),
            selection_mode="points",
            alt=f"{measure.axis_label} by {group_by}. {explanation}",
        )
    with st.expander(
        "Table and downloads", key="corpus_summary_table", on_change="rerun"
    ) as panel:
        if panel.open:
            _show_table(table, field, group_by.capitalize(), measure)
            if measure.is_rate:
                st.caption("The CSV stores rates as proportions from 0 to 1.")
            download(
                st,
                table,
                name=f"overview_by_{group_by}_{key}.csv",
                key="dl_corpus_overview",
                label="Download summary (CSV)",
                in_panel=True,
                recipe=dict(
                    view=OVERVIEW_VIEW,
                    group_by=group_by,
                    measure=measure,
                    aggregation="mean",
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
