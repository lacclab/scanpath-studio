"""Shared MultiplEYE test inputs: a session set's config files, and a tiny upload.

A real session set records its screen in ``stimuli_*/config/config_*.py`` and
``*_lab_configuration.json``; the loader reads it from there and assumes nothing
when they are missing. The test trees use the Zurich sample's geometry, so a
coordinate lands at its image-relative value plus ``(305, 44.5)``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

MONITOR = (1920, 1080)
IMAGE = (1310, 991)
OFF_X = (MONITOR[0] - IMAGE[0]) / 2
OFF_Y = (MONITOR[1] - IMAGE[1]) / 2


def write_screen_config(
    root: Path,
    *,
    stimuli: str = "stimuli_Demo",
    monitor: tuple[int, int] | None = MONITOR,
    image: tuple[int, int] | None = IMAGE,
    font_px: int | None = None,
    font: str | None = None,
    lab_configuration: dict | None = None,
) -> Path:
    """Write ``<root>/<stimuli>/config/config_demo.py`` (and, when given, a lab
    configuration beside it) with the values passed; ``None`` leaves one out."""
    config = root / stimuli / "config"
    config.mkdir(parents=True, exist_ok=True)
    lines = ["# IMAGE ##########"]
    if font_px is not None:
        lines.append(f"FONT_SIZE = {font_px}")
    if font is not None:
        lines.append(f'FONT = "{font}"')
    if image is not None:
        lines += [f"IMAGE_WIDTH_PX = {image[0]}", f"IMAGE_HEIGHT_PX = {image[1]}"]
    lines.append("# SCREEN ##########")
    if monitor is not None:
        lines.append(f"RESOLUTION = ({monitor[0]}, {monitor[1]})")
    path = config / "config_demo.py"
    path.write_text("\n".join(lines) + "\n")
    if lab_configuration is not None:
        (config / "Demo_lab_configuration.json").write_text(
            json.dumps(lab_configuration)
        )
    return path


def mpe_upload_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A tiny MultiplEYE upload: scanpath rows (CamelCase file name) and their
    character AOIs (lowercase file name), each row tagged with its file stem."""
    scan = pd.DataFrame(
        {
            "onset": [1000, 1300, 2000],
            "duration": [200, 180, 210],
            "name": ["fixation"] * 3,
            "location_x": [90, 150, 90],
            "location_y": [65, 65, 65],
            "page": ["page_1", "page_1", "page_2"],
            "word_idx": [0, 1, 0],
        }
    )
    scan["source_file"] = "001_ZH_CH_1_ET1_trial_1_Lit_Demo_1_scanpath"

    def chars(page, word_idx, word, x0):
        return [
            dict(
                char_idx=word_idx * 2 + i,
                char=word[i],
                top_left_x=x0 + i * 20,
                top_left_y=50,
                width=20,
                height=30,
                char_idx_in_line=word_idx * 2 + i,
                line_idx=0,
                page=page,
                word_idx=word_idx,
                word_idx_in_line=word_idx,
                word=word,
            )
            for i in range(2)
        ]

    aoi = pd.DataFrame(
        chars("page_1", 0, "AA", 80)
        + chars("page_1", 1, "BB", 140)
        + chars("page_2", 0, "CC", 80)
    )
    aoi["source_file"] = "lit_demo_1_aoi"
    return scan, aoi
