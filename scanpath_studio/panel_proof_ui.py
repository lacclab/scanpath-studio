"""Export the current comparison at its physical manuscript size."""

from __future__ import annotations

import json
from collections.abc import Callable

import streamlit as st

from . import panel_proof


def render(figure, print_size: dict, settings_for: Callable[[], dict]) -> None:
    """Offer a vector file and the standard restorable settings for its two panels."""
    group = st.expander("Manuscript panel proof", on_change="rerun")
    if not group.open:
        return
    initial = (print_size["width"] or 0) * (25.4 if print_size["unit"] == "in" else 1)
    width = group.number_input(
        "Total print width (mm)",
        min_value=1.0,
        max_value=2000.0,
        value=float(max(1, min(2000, initial or 170))),
        step=1.0,
    )
    try:
        proof = panel_proof.describe(figure, width)
    except ValueError as exc:
        group.info(str(exc))
        return
    for name, sizes in proof["label_points"].items():
        group.text(f"{name} · {', '.join(f'{v:g}' for v in sizes)} pt")
    limits = [
        f"{name} {proof[k][0]:g}–{proof[k][1]:g}"
        for k, name in (
            ("fixation_range", "Fixation colors"),
            ("heatmap_range", "Heatmap"),
        )
        if proof.get(k) is not None
    ]
    keep_limits = False
    if limits:
        group.text("Common limits · " + " · ".join(limits))
        keep_limits = group.checkbox(
            "Keep these color limits when replacing a reading",
            value=True,
            help="Change the numerical limits under Fixations or Heatmap. Clear this to recalculate them for the replacement pair.",
        )
    recipe = panel_proof.settings(settings_for(), proof, keep_limits=keep_limits)
    group.download_button(
        "Save panel settings",
        data=json.dumps(recipe, indent=2),
        file_name="panel_settings.json",
        mime="application/json",
        on_click="ignore",
        help="Open this file in Share → File to restore the readings, panel order, layout, print width and color settings.",
    )
    if group.button("Prepare manuscript SVG"):
        try:
            svg = panel_proof.svg(figure, width)
        except (OSError, RuntimeError, ValueError) as exc:
            group.error(str(exc))
        else:
            group.download_button(
                "Download manuscript SVG",
                data=svg,
                file_name="panels.svg",
                mime="image/svg+xml",
                on_click="ignore",
            )
