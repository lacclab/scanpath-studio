"""Previously released downloads and a complete handoff with relative inputs."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import shutil
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

import scanpath_studio.annotations as trial_annotations
from scanpath_studio import cli
from scanpath_studio.utils import reading_key


def _open_settings():
    import json
    from pathlib import Path

    import streamlit as st

    from scanpath_studio import load_scanpath_data
    from scanpath_studio.url_state import _restore_plot_config
    from scanpath_studio.utils import build_combo_options
    from scanpath_studio.wizard import _clean_setup_config

    _, fixes = load_scanpath_data("words.csv", "fixations.csv", names="canonical")
    combos, _, _ = build_combo_options(fixes)
    _restore_plot_config(
        json.loads(Path("figure-settings.json").read_bytes()), combos, fixes
    )
    st.session_state["_import_setup"] = _clean_setup_config(
        json.loads(Path("setup.json").read_bytes())
    )


def _plotly_traces(html):
    # The settings and traces are JSON in the file the recipient actually opens.
    marker = list(re.finditer(r'Plotly\.newPlot\(\s*"[^"]+"\s*,\s*', html))[-1]
    document = html[marker.end() :]
    decoder = json.JSONDecoder()
    traces, end = decoder.raw_decode(document)
    layout, _ = decoder.raw_decode(document[end:].lstrip().removeprefix(",").lstrip())
    return traces, layout


def _plot_values(value):
    if isinstance(value, list):
        return value
    return np.frombuffer(
        base64.b64decode(value["bdata"]), dtype=value["dtype"]
    ).tolist()


def test_released_downloads_and_documented_handoff(tmp_path, monkeypatch):
    source = files("scanpath_studio") / "sample_data" / "coauthor"
    study = tmp_path / "canal-study"
    shutil.copytree(source, study)
    monkeypatch.chdir(study)
    readme = Path("README.md").read_text(encoding="utf-8")
    for command in re.findall(r"^scanpath-studio .+$", readme, flags=re.MULTILINE):
        cli.main(shlex.split(command)[1:])

    csv = Path("profile.csv").read_bytes()
    assert (
        hashlib.sha256(csv).hexdigest() == Path("profile.sha256").read_text().split()[0]
    )
    profile = pd.read_csv("profile.csv")
    assert list(zip(profile["word_text"], profile["value"], profile["n"])) == [
        ("Rain", 160.0, 2),
        ("fell", 220.0, 2),
    ]
    store = trial_annotations.deserialize(Path("annotations.json").read_bytes())
    assert set(store) == {("p03", "run-03")}
    assert store["p03", "run-03"]["tags"] == ["exclude"]

    at = AppTest.from_function(_open_settings).run()
    assert not at.exception, at.exception
    assert at.session_state["single_trial_id"] == reading_key("p02", "run-02")
    setup = at.session_state["_import_setup"]
    assert setup["experimental_setup"]["canvas_width"] == 640
    assert setup["column_mapping"]["col_map_words_measure_tfd"] == "IA_DWELL_TIME"
    assert at.session_state["global_color_by"] == "duration_ms"
    assert at.session_state["global_fixation_opacity"] == 0.5

    traces, layout = _plotly_traces(Path("panel.html").read_text(encoding="utf-8"))
    marker = next(t for t in traces if t.get("name", "").casefold() == "fixations")
    assert marker["mode"] == "markers" and marker["marker"]["opacity"] == 0.5
    assert _plot_values(marker["x"]) == [106, 179]
    assert _plot_values(marker["y"]) == [111, 113]
    assert _plot_values(marker["marker"]["color"]) == [200, 260]
    assert layout["xaxis"]["range"] == [0, 640]
    assert layout["yaxis"]["range"] == [360, 0]
