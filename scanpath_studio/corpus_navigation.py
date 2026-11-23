"""Corpus navigation and the published bookmarks for its summaries and profiles."""

from __future__ import annotations

import streamlit as st

from .aggregation import MEASURES, Measure
from .constants import sentence_analysis_enabled
from .session_keys import CORPUS_GROUP_BY, CORPUS_MEASURE, CORPUS_SUBTAB

DESTINATION_KEY = "corpus_destination"
_KEYS = (CORPUS_SUBTAB, CORPUS_GROUP_BY, CORPUS_MEASURE)
_LAST_ROUTE = "_corpus_navigation_route"
_PROFILE = {"text": "Per text", "participant": "Per participant"}
_DESTINATIONS = {
    "Per text": "Texts",
    "Per participant": "Participants",
    "Groups": "Groups",
    "Per sentence": "Sentences",
}
_MEASURES_BY_LABEL = {measure.label: measure for measure in MEASURES.values()}


def destinations() -> list[str]:
    values = ["Texts", "Participants", "Groups"]
    if sentence_analysis_enabled():
        values.append("Sentences")
    return values


def open_profile(group_by: str) -> None:
    """Open a detail view underneath the selected summary."""
    st.session_state[CORPUS_SUBTAB] = _PROFILE[group_by]
    st.session_state[CORPUS_GROUP_BY] = group_by.capitalize()


def _open_summary(group_by: str) -> None:
    st.session_state[CORPUS_SUBTAB] = "Overview"
    st.session_state[CORPUS_GROUP_BY] = group_by


def _choose_destination(has_text: bool) -> None:
    state = st.session_state
    destination = state[DESTINATION_KEY]
    if destination == "Groups":
        section = state.get(CORPUS_SUBTAB)
        if section in ("Overview", "Per text", "Per participant"):
            detail_key = _detail_measure_key(section)
            measure = (
                _MEASURES_BY_LABEL.get(state.get(detail_key)) if detail_key else None
            )
            measure = measure or MEASURES.get(state.get(CORPUS_MEASURE))
            if measure is not None:
                state["cmp_measure"] = state["pgrp_measure"] = measure.label
        state[CORPUS_SUBTAB] = "Groups"
    elif destination == "Sentences":
        state[CORPUS_SUBTAB] = "Per sentence"
    elif destination == "Texts" and not has_text:
        open_profile("text")
    else:
        _open_summary("Text" if destination == "Texts" else "Participant")


def _detail_measure_key(section: str) -> str | None:
    if section == "Groups":
        return (
            "cmp_measure"
            if st.session_state.get("groups_compare", True)
            else "pgrp_measure"
        )
    return {"Per text": "ptext_measure", "Per participant": "prdr_measure"}.get(section)


def render_chooser(host, *, has_text: bool, measures: list[Measure]) -> tuple[str, str]:
    """Draw one destination control and return the legacy section and summary unit.

    One visible destination can represent a summary or its detail. The public
    link distinguishes them with two parameters, so it cannot be bound to
    just the visible widget. Update the route and its measure together to
    make a single browser history entry.
    """
    state = st.session_state
    query = tuple(st.query_params.get(k) or None for k in _KEYS)
    local = tuple(state.get(k) for k in _KEYS)
    last_address, last_state = state.get(_LAST_ROUTE, (None, None))
    restoring = (
        last_address is not None and query != last_address and local == last_state
    )
    if last_address is None:
        section, group, measure = (q or s for q, s in zip(query, local, strict=True))
    elif restoring:
        # Browser history changed the address; a tutorial or widget callback
        # that changed the local route for this run takes precedence.
        section, group, measure = query
    else:
        section, group, measure = local

    options = destinations()
    if _DESTINATIONS.get(section) not in options:
        section = "Overview"
    if section == "Per text":
        group = "Text"
    elif section == "Per participant" or not has_text or group == "Participant":
        group = "Participant"
    else:
        group = "Text"

    selected = _MEASURES_BY_LABEL.get(measure) or MEASURES.get(measure, measures[0])
    detail_key = _detail_measure_key(section)
    if detail_key and (restoring or (last_address is None and query[2])):
        state[detail_key] = selected.label
    # A profile may use a fixation measure. The word summary keeps its last
    # available word measure for the return trip.
    if selected not in measures:
        remembered = MEASURES.get(state.get(CORPUS_MEASURE))
        selected = remembered if remembered in measures else measures[0]
    for key, value in zip(_KEYS, (section, group, selected.key), strict=True):
        if state.get(key) != value:
            state[key] = value

    destination = _DESTINATIONS.get(
        section, "Texts" if group == "Text" else "Participants"
    )
    if state.get(DESTINATION_KEY) != destination:
        state[DESTINATION_KEY] = destination
    host.segmented_control(
        "Corpus destination",
        options,
        key=DESTINATION_KEY,
        required=True,
        label_visibility="collapsed",
        on_change=_choose_destination,
        args=(has_text,),
        persist_state="session",
    )
    return section, group.lower()


def update_bookmark(*, has_text: bool, measures: list[Measure]) -> None:
    """Publish the measure selected after the view checks its available options."""
    state = st.session_state
    section, group, summary_key = (state[k] for k in _KEYS)
    selected = MEASURES[summary_key]
    detail_key = _detail_measure_key(section)
    if detail_key:
        selected = _MEASURES_BY_LABEL.get(state.get(detail_key), selected)
        if selected in measures:
            state[CORPUS_MEASURE] = selected.key
    address = (
        section if section != "Overview" else None,
        group
        if section == "Overview" and group == "Participant" and has_text
        else None,
        selected.label if selected != measures[0] else None,
    )
    if address != tuple(st.query_params.get(k) or None for k in _KEYS):
        # An empty list removes a key from the encoded URL. Unrelated and
        # repeated parameters retain their values.
        st.query_params.update(
            dict(zip(_KEYS, (v or [] for v in address), strict=True))
        )
    state[_LAST_ROUTE] = (address, tuple(state[k] for k in _KEYS))


def back_to_summary(section: str, *, has_text: bool) -> None:
    if section == "Per participant" or (section == "Per text" and has_text):
        group = "Text" if section == "Per text" else "Participant"
        st.button(
            "Back to texts" if group == "Text" else "Back to participants",
            key="corpus_back_to_summary",
            type="tertiary",
            on_click=_open_summary,
            args=(group,),
        )
