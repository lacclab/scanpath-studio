"""Tests for the headless programmatic API (scanpath_studio.api)."""

import inspect
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest
import streamlit

import scanpath_studio as sps
from scanpath_studio import alignment, api, constants, controls, plots, tabs
from scanpath_studio import data as data_module
from tests.synthetic_data import (
    EXPECTED,
    make_synthetic_fixations,
    make_synthetic_words,
)


@pytest.fixture(scope="module")
def sample():
    """Normalized bundled demo data, loaded once per module."""
    return sps.load_sample_data()


def test_load_sample_data_is_normalized(sample):
    words, fixations = sample
    for col in ("participant_id", "trial_id", "x", "y", "text"):
        assert col in words.columns
    for col in ("participant_id", "trial_id", "x", "y", "duration_ms"):
        assert col in fixations.columns


def test_top_level_exports():
    for name in (
        "load_scanpath_data",
        "load_sample_data",
        "list_trials",
        "compute_word_metrics",
        "plot_scanpath",
        "animate_scanpath",
        "save_figure",
        "save_figure_layers",
    ):
        assert callable(getattr(sps, name))
    with pytest.raises(AttributeError):
        sps.does_not_exist


def test_list_trials(sample):
    combos = sps.list_trials(*sample)
    assert list(combos.columns) == ["participant_id", "trial_id"]
    assert len(combos) > 1
    assert not combos.duplicated().any()


def test_load_scanpath_data_from_files(tmp_path):
    words_raw, fix_raw = data_module.load_sample_data()
    words_path = tmp_path / "ia.csv"
    fix_path = tmp_path / "fixations.csv"
    words_raw.to_csv(words_path, index=False)
    fix_raw.to_csv(fix_path, index=False)

    words, fixations = sps.load_scanpath_data(words_path, fix_path)
    assert "trial_id" in words.columns
    assert "duration_ms" in fixations.columns


def test_load_scanpath_data_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        sps.load_scanpath_data(tmp_path / "nope.csv", tmp_path / "nope2.csv")


def test_load_scanpath_data_bad_schema():
    junk = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(ValueError, match="schema problems"):
        sps.load_scanpath_data(junk, junk)


# --------------------------------------------------------------------------
# ENG-18: an un-inferrable table has to say WHICH canonical field failed, which
# column names were tried, and what to pass instead.
# --------------------------------------------------------------------------


def test_words_schema_error_names_field_candidates_and_columns():
    words = pd.DataFrame(
        {"subject": ["s1"], "para": [1], "word": ["the"], "start_x": [10]}
    )
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(words=words)
    message = str(excinfo.value)

    # The canonical field, its schema key, and the exact candidates tried.
    assert "Trial ID (word_schema key 'trial'): no column matched" in message
    assert "Looked for: unique_trial_id, trial_id" in message
    assert "Word/IA ID (word_schema key 'word_id')" in message
    # The either/or box requirement names which keys each convention still needs
    # (`start_x` already resolved `left`, so only right/top/bottom are missing).
    assert (
        "need either (x, y, width, height) or (left, right, top, bottom) — "
        "(x, y, width, height) is missing x, y, width, height; "
        "(left, right, top, bottom) is missing right, top, bottom." in message
    )
    # What auto-detection *did* find, and the table it was looking at.
    assert "Fields that did resolve: text='word', left='start_x'" in message
    assert (
        "Columns present in the words/IA table (4): subject, para, word, start_x"
        in message
    )
    # A copy-pasteable override that keeps the columns already resolved.
    assert (
        "word_schema={'trial': '<column>', 'word_id': '<column>', "
        "'left': 'start_x', 'right': '<column>', 'top': '<column>', "
        "'bottom': '<column>'}" in message
    )
    assert "api.propose_schema(df, 'words')" in message


def test_fixations_schema_error_names_field_candidates_and_columns():
    fixations = pd.DataFrame({"participant_id": ["s1"], "fix_dur": [210]})
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(fixations=fixations)
    message = str(excinfo.value)

    assert "Fixations schema problems: missing Trial ID; missing Duration" in message
    assert "Duration (fix_schema key 'duration'): no column matched" in message
    assert "Looked for: duration_ms, CURRENT_FIX_DURATION" in message
    assert (
        "Fixation location (fix_schema keys): need either (x, y) or (word_id)"
        in message
    )
    assert "Fields that did resolve: participant='participant_id'" in message
    assert "fix_schema={'trial': '<column>', 'duration': '<column>'" in message


def test_schema_error_truncates_a_wide_table():
    wide = pd.DataFrame({f"col{i}": [0] for i in range(45)})
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(words=wide)
    message = str(excinfo.value)
    assert "Columns present in the words/IA table (45): col0, " in message
    assert "col39, … (+5 more)" in message
    assert "col40" not in message


def test_words_schema_rejects_a_column_the_table_does_not_have():
    """A typo'd explicit mapping used to be *silently ignored*: normalize_words
    prefers a literal `unique_trial_id` column over the mapped one, so the frame
    came back keyed on a column the caller never named."""
    words_raw, fix_raw = data_module.load_sample_data()
    assert "unique_trial_id" in words_raw.columns  # the column that masked it
    schema = api.propose_schema(words_raw, "words")
    schema["trial"] = "TRIAL_LABEL"  # a plausible-looking EyeLink name that isn't there
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(words=words_raw, fixations=fix_raw, word_schema=schema)
    message = str(excinfo.value)
    assert (
        "Words/IA schema maps 1 column name the words/IA table doesn't have" in message
    )
    assert "word_schema['trial'] = 'TRIAL_LABEL': no such column" in message
    assert "closest: 'IA_LABEL'" in message
    assert "Columns present in the words/IA table (60): participant_id" in message
    assert "api.propose_schema(table, 'words')" in message


def test_fixations_schema_rejects_mapped_columns_and_reports_every_one():
    """Two bad keys → both named (this path used to be a bare KeyError)."""
    _, fix_raw = data_module.load_sample_data()
    schema = api.propose_schema(fix_raw, "fixations")
    schema["x"] = "GAZE_X"
    schema["y"] = "GAZE_Y"
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(fixations=fix_raw, fix_schema=schema)
    message = str(excinfo.value)
    assert "maps 2 column names the fixations table doesn't have" in message
    assert "fix_schema['x'] = 'GAZE_X': no such column" in message
    assert "fix_schema['y'] = 'GAZE_Y': no such column" in message


def test_schema_column_check_accepts_a_composite_trial_mapping():
    """A multi-column (composite) trial id is a list — every element is checked,
    and a valid one loads."""
    words_raw, fix_raw = data_module.load_sample_data()
    schema = api.propose_schema(words_raw, "words")
    schema["trial"] = ["participant_id", "TRIAL_INDEX"]
    words, fixations = sps.load_scanpath_data(
        words=words_raw, fixations=fix_raw, word_schema=schema
    )
    assert (
        words["trial_id"].iloc[0].startswith(str(words_raw["participant_id"].iloc[0]))
    )
    schema["trial"] = ["participant_id", "TRIAL_NUMBER"]
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(words=words_raw, word_schema=schema)
    assert "word_schema['trial'] = 'TRIAL_NUMBER': no such column" in str(excinfo.value)


def test_explicit_schema_error_points_at_the_mapping_not_at_detection():
    """With a caller-supplied schema nothing was auto-detected, so the message
    must not claim a column search failed."""
    words_raw, _ = data_module.load_sample_data()
    with pytest.raises(ValueError) as excinfo:
        sps.load_scanpath_data(
            words=words_raw,
            word_schema={
                "word_id": "IA_ID",
                "left": "IA_LEFT",
                "right": "IA_RIGHT",
                "top": "IA_TOP",
                "bottom": "IA_BOTTOM",
            },
        )
    message = str(excinfo.value)
    assert "Words/IA schema problems: missing Trial ID" in message
    assert "Missing from the word_schema you passed:" in message
    assert (
        "Trial ID (word_schema key 'trial'): not set in the word_schema you passed. "
        "Auto-detection (used when word_schema is omitted) looks for: "
        "unique_trial_id, trial_id" in message
    )
    assert "no column matched" not in message
    assert "Fields the word_schema does set: word_id='IA_ID'" in message
    assert "An explicit word_schema replaces auto-detection wholesale" in message


def test_propose_schema_is_the_documented_repair_path():
    """The mapping the error points at actually loads the renamed table."""
    words_raw, fix_raw = data_module.load_sample_data()
    renamed = words_raw.rename(columns={"IA_ID": "aoi_number"})
    # `IA_ID` was the only Word/IA ID candidate present, so detection now fails…
    with pytest.raises(ValueError, match="missing Word/IA ID"):
        sps.load_scanpath_data(words=renamed, fixations=fix_raw)

    schema = api.propose_schema(renamed, "words")
    assert schema["word_id"] is None
    assert schema["trial"] == "unique_trial_id"
    assert schema["left"] == "IA_LEFT"
    schema["word_id"] = "aoi_number"
    words, fixations = sps.load_scanpath_data(
        words=renamed, fixations=fix_raw, word_schema=schema
    )
    assert "word_id" in words.columns
    assert not sps.list_trials(words, fixations).empty


def test_propose_schema_reads_files_and_rejects_unknown_kind(tmp_path):
    words_raw, _ = data_module.load_sample_data()
    path = tmp_path / "ia.csv"
    words_raw.head(20).to_csv(path, index=False)
    assert api.propose_schema(path, "words")["text"] == "IA_LABEL"
    with pytest.raises(ValueError, match="Unknown kind 'word'"):
        api.propose_schema(path, "word")


def test_plotting_rejects_unnormalized_input(sample):
    words, fixations = sample
    with pytest.raises(TypeError, match="must be the normalized pandas DataFrame"):
        sps.list_trials("ia.csv", fixations)
    raw = words.rename(columns={"participant_id": "pid"})
    with pytest.raises(ValueError) as excinfo:
        sps.plot_scanpath(raw, fixations)
    message = str(excinfo.value)
    assert "words frame is not normalized" in message
    assert "missing the canonical column(s) participant_id" in message
    assert "load_scanpath_data" in message


def test_plot_scanpath_returns_figure(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    trial_words, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, canvas_size=(2560, 1440), show_heatmap=False
    )
    assert isinstance(fig, go.Figure)
    # One box shape per word of the trial, plus the plot-border rect.
    assert len(fig.layout.shapes) == len(trial_words) + 1
    # One marker per fixation, drawn at the fixation coordinates.
    markers = [t for t in fig.data if t.mode and "markers" in t.mode]
    assert len(markers) == 1
    assert list(markers[0].x) == list(trial_fixations["x"])
    assert list(markers[0].y) == list(trial_fixations["y"])
    # Saccades collapse to ONE trace with None separators (perf contract).
    (saccades,) = [t for t in fig.data if t.name == "saccades"]
    assert len(saccades.x) == 3 * len(trial_fixations) - 3


def test_plot_scanpath_overrides(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    default_fig = sps.plot_scanpath(words, fixations, pid, tid)
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_words=False,
        show_heatmap=False,
        heatmap_metric="counts",
    )
    assert isinstance(fig, go.Figure)
    # Word boxes gone: only the canvas border rect remains, vs one shape per
    # word (plus border) in the canonical default.
    assert len(fig.layout.shapes or ()) < len(default_fig.layout.shapes)


def test_plot_scanpath_saccade_color_by_type(sample):
    # VIZ-8: headless "By type" mode splits the saccades into legended class
    # sub-traces (the classification runs inside make_scanpath_figure, so no
    # pipeline pre-enrichment is needed).
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, show_heatmap=False, saccade_color_mode="By type"
    )
    by_type = [t for t in fig.data if t.legendgroup == "saccade_type"]
    assert len(by_type) >= 2
    assert not [t for t in fig.data if t.name == "saccades"]


def test_plot_scanpath_heatmap_log_norm(sample):
    # VIZ-3: log normalization remaps the word-box heatmap tints vs linear.
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]

    def box_colors(norm):
        fig = sps.plot_scanpath(
            words,
            fixations,
            pid,
            tid,
            show_fixations=False,
            show_saccades=False,
            heatmap_norm=norm,
        )
        return [s.fillcolor for s in fig.layout.shapes if s.layer == "below"]

    lin, log = box_colors("Linear"), box_colors("Log")
    assert lin and lin != log


def test_plot_scanpath_snap_fixations(sample):
    # VIZ-9: snapping repositions the fixation markers (fewer distinct y — one per
    # text line — than the raw gaze scatter).
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]

    def marker_ys(snap):
        fig = sps.plot_scanpath(
            words, fixations, pid, tid, show_heatmap=False, fixation_snap_to_word=snap
        )
        m = [t for t in fig.data if t.mode and "markers" in t.mode]
        return list(m[0].y)

    raw, snapped = marker_ys(False), marker_ys(True)
    assert len(set(snapped)) < len(set(raw))


def test_plot_scanpath_axis_field_override(sample):
    # Regression: x_field/y_field used to collide with the explicitly passed
    # kwargs and raise "got multiple values for keyword argument".
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    _, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, x_field="order_in_trial", show_heatmap=False
    )
    (markers,) = [t for t in fig.data if t.mode and "markers" in t.mode]
    # The markers are plotted against the fixation index, not the gaze x.
    assert list(markers.x) == list(trial_fixations["order_in_trial"])
    assert list(markers.y) == list(trial_fixations["y"])


def test_plot_scanpath_filters_raw_gaze(sample):
    # Regression: raw_gaze used to be forwarded unfiltered, overlaying gaze
    # points from every other trial on the single-trial figure.
    words, fixations = sample
    combos = sps.list_trials(words, fixations)
    pid, tid = combos.iloc[0]
    other_pid, other_tid = combos.iloc[1]
    raw_gaze = pd.DataFrame(
        {
            "participant_id": [pid, pid, other_pid],
            "trial_id": [tid, tid, other_tid],
            "x": [100.0, 110.0, 5000.0],
            "y": [100.0, 105.0, 5000.0],
            "timestamp_ms": [0, 1, 0],
        }
    )
    fig = sps.plot_scanpath(words, fixations, pid, tid, raw_gaze=raw_gaze)
    raw_traces = [t for t in fig.data if t.name == "Raw gaze"]
    assert raw_traces and len(raw_traces[0].x) == 2


def test_plot_scanpath_fix_index_range_windows_the_trial(sample):
    """VIZ-7 headless: draw only fixations start..end (1-based, inclusive)."""
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    _, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, show_heatmap=False, fix_index_range=(5, 12)
    )
    (markers,) = [t for t in fig.data if t.mode and "markers" in t.mode]
    window = trial_fixations[trial_fixations["order_in_trial"].between(5, 12)]
    assert len(window) == 8  # both bounds inclusive
    assert list(markers.x) == list(window["x"])
    assert list(markers.y) == list(window["y"])


def test_animate_scanpath_fix_index_range_windows_the_replay(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.animate_scanpath(words, fixations, pid, tid, fix_index_range=(5, 12))
    assert len(fig.frames[-1].data[0].x) == 8


def test_fix_index_range_rejects_a_window_that_selects_nothing(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    _, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    n = len(trial_fixations)
    with pytest.raises(ValueError) as excinfo:
        sps.plot_scanpath(words, fixations, pid, tid, fix_index_range=(n + 1, n + 10))
    assert f"has {n} fixations (order_in_trial 1–{n})" in str(excinfo.value)
    with pytest.raises(ValueError, match="start 12 is after end 5"):
        sps.plot_scanpath(words, fixations, pid, tid, fix_index_range=(12, 5))
    with pytest.raises(ValueError, match=r"must be a \(start, end\) pair"):
        sps.plot_scanpath(words, fixations, pid, tid, fix_index_range=20)


def test_plot_scanpath_rejects_unnormalized_raw_gaze(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    raw = pd.DataFrame({"pid": [pid], "x": [1.0], "y": [2.0]})
    with pytest.raises(ValueError, match="raw_gaze frame is not normalized"):
        sps.plot_scanpath(words, fixations, pid, tid, raw_gaze=raw)


def test_animate_scanpath_rejects_static_only_options(sample):
    # Regression: static-only keys used to surface as an opaque TypeError.
    # (color_by no longer qualifies — the replay honours it like the static
    # figure; the heatmap overlay is still static-only.)
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    with pytest.raises(ValueError, match="not supported by the animation"):
        sps.animate_scanpath(words, fixations, pid, tid, show_heatmap=True)


def test_resolve_trial_default_first(sample):
    words, fixations = sample
    combos = sps.list_trials(words, fixations)
    pid, tid = api._resolve_trial(words, fixations, None, None, default_first=True)
    assert (pid, tid) == tuple(combos.iloc[0])
    # default_first never excuses a nonexistent id.
    with pytest.raises(ValueError, match="No trial matches"):
        api._resolve_trial(words, fixations, None, "no_such_trial", default_first=True)


def test_dir_lists_lazy_exports():
    assert "plot_scanpath" in dir(sps)


def test_plot_scanpath_ambiguous_raises(sample):
    with pytest.raises(ValueError, match="Ambiguous"):
        sps.plot_scanpath(*sample)


def test_plot_scanpath_unknown_trial_raises(sample):
    with pytest.raises(ValueError, match="No trial matches"):
        sps.plot_scanpath(*sample, participant="nobody", trial="nothing")


def test_unknown_participant_message_lists_ids_and_close_matches(sample):
    words, fixations = sample
    pid = str(sps.list_trials(words, fixations)["participant_id"].iloc[0])
    with pytest.raises(ValueError) as excinfo:
        sps.plot_scanpath(words, fixations, participant=pid.upper() + "x")
    message = str(excinfo.value)
    assert "that participant id is not in the data" in message
    assert f"Available: {pid!r}" in message
    assert f"Closest: {pid!r}" in message


def test_unknown_trial_within_participant_names_the_participant(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    with pytest.raises(ValueError) as excinfo:
        sps.plot_scanpath(words, fixations, participant=pid, trial="no_such_trial")
    message = str(excinfo.value)
    assert f"participant {str(pid)!r} has " in message
    assert "none of them 'no_such_trial'" in message
    assert f"Available: {str(tid)!r}" in message


def test_ambiguous_message_says_which_argument_is_missing(sample):
    words, fixations = sample
    combos = sps.list_trials(words, fixations)
    pid = combos["participant_id"].iloc[0]
    n_for_pid = int((combos["participant_id"] == pid).sum())
    with pytest.raises(ValueError) as excinfo:
        sps.plot_scanpath(words, fixations, participant=pid)
    message = str(excinfo.value)
    assert f"Ambiguous selection: {n_for_pid} trials match" in message
    assert f"Participant {str(pid)!r} has {n_for_pid} trials — pass trial= too." in (
        message
    )
    assert f"lists all {len(combos)} combos" in message


def test_plot_scanpath_unknown_option_suggests_the_real_one(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    with pytest.raises(TypeError) as excinfo:
        sps.plot_scanpath(words, fixations, pid, tid, show_saccade=True)
    message = str(excinfo.value)
    assert "plot_scanpath() got an unexpected keyword argument" in message
    assert "'show_saccade' (did you mean 'show_saccades'" in message
    assert "api.figure_options()" in message


def test_figure_options_cover_every_builder_keyword():
    """`figure_options` is the parameter reference — it must be complete."""
    static = api.figure_options()
    assert set(static) == set(api._STATIC_FIGURE_PARAMS)
    assert static["show_heatmap"] is True  # canonical override
    assert static["heatmap_style"] == "Word boxes"  # builder default, no override
    animation = api.figure_options("animation")
    assert set(animation) == set(api._ANIMATION_FIGURE_PARAMS)
    # The animation builder has no heatmap; the static one has no second scanpath.
    assert "show_heatmap" not in animation
    assert "fixations_b" in animation
    with pytest.raises(ValueError, match="Unknown kind 'gif'"):
        api.figure_options("gif")


def test_agent_guide_option_tables_match_the_code():
    """docs/agents.md documents every option and default — keep it honest."""
    guide = (Path(__file__).resolve().parents[1] / "docs" / "agents.md").read_text()
    section = guide.split("## Every figure option", 1)[1].split(
        "## Reading measures", 1
    )[0]
    rows = re.findall(r"^\| `(\w+)` \| `(.+?)` \| (yes|no) \|$", section, re.MULTILINE)
    assert rows, "no option table found in docs/agents.md"

    static = api.figure_options()
    animation = set(api.figure_options("animation"))
    documented = {name: (default, anim) for name, default, anim in rows}
    assert len(documented) == len(rows)  # no duplicated row
    assert set(documented) == set(static)
    for name, (default, anim) in documented.items():
        assert default == repr(static[name]), name
        assert anim == ("yes" if name in animation else "no"), name
    # The two-scanpath overlay extras named in the prose are animation-only.
    # (A subset check, not equality: the animation builder also carries
    # replay-only knobs the tables deliberately don't document — the prose sends
    # the reader to figure_options("animation") for those.)
    assert {"words_b", "fixations_b", "label_a", "label_b", "show_legend"} <= (
        animation - set(static)
    )


def test_canonical_defaults_supply_every_required_builder_argument():
    """Any make_scanpath_figure parameter without its own default has to be in
    CANONICAL_FIGURE_DEFAULTS, or plot_scanpath() would raise a TypeError."""
    signature = inspect.signature(plots.make_scanpath_figure)
    required = {
        name
        for name, param in signature.parameters.items()
        if param.default is inspect.Parameter.empty
    } - {"words", "fixations", "canvas_width", "canvas_height", "base_font_size"}
    assert required <= set(api.CANONICAL_FIGURE_DEFAULTS) | {"font_family"}


def _app_figure_defaults(words, fixations, monkeypatch):
    """The figure kwargs the app builds for a fresh session.

    ``_seed_viz_state`` / ``_collect_viz_settings`` / ``_build_figure_settings``
    are pure, so the app's own defaults can be resolved headlessly with a plain
    dict standing in for ``st.session_state``."""
    monkeypatch.setattr(streamlit, "session_state", {})
    controls._seed_viz_state(fixations, 16, words)
    viz = controls._collect_viz_settings(fixations, words)
    settings = tabs._build_figure_settings(viz, viz["show_raw_gaze"])
    # tabs.py passes these four outside _build_figure_settings: the axis fields
    # from viz_settings, and the text-sizing pair from the Experimental-setup
    # canvas controls (app.render_sidebar_canvas_controls, which needs a widget
    # host — these are its `setdefault` values).
    settings["x_field"] = viz["x_field"]
    settings["y_field"] = viz["y_field"]
    settings["line_spacing"] = float(constants.DEFAULT_LINE_SPACING)
    settings["scale_text_to_boxes"] = True
    return settings


def test_headless_defaults_match_the_app_for_every_non_layer_option(
    sample, monkeypatch
):
    """ENG-18 drift audit, exhaustively: a bare `plot_scanpath` must render what
    the app renders, except for the layers it deliberately turns on."""
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    trial_words, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    app_settings = _app_figure_defaults(trial_words, trial_fixations, monkeypatch)
    headless = api._figure_kwargs({})
    headless.setdefault("show_raw_gaze", False)

    builder = inspect.signature(plots.make_scanpath_figure).parameters

    def effective(settings, key):
        """What the builder actually sees: the setting, or its signature default."""
        if key in settings:
            return settings[key]
        fallback = builder[key].default
        return None if fallback is inspect.Parameter.empty else fallback

    # Two settings the app spells out and the API leaves to the builder, which
    # fills in the very same values — assert the equivalence instead of the
    # literal objects.
    assert all(
        cat["mode"] == "Off" for cat in app_settings["fixation_flags"].values()
    )  # ≡ fixation_flags=None
    assert app_settings["saccade_class_colors"] == {
        name: constants.SACCADE_CLASS_COLORS[name]
        for name in app_settings["saccade_class_colors"]
    }  # ≡ saccade_class_colors=None (plots merges over SACCADE_CLASS_COLORS)
    equivalent = {"fixation_flags", "saccade_class_colors"}

    differing = {
        key
        for key in api._STATIC_FIGURE_PARAMS - equivalent
        if effective(app_settings, key) != effective(headless, key)
    }
    # The documented difference, and nothing else: the app opens on the core
    # scanpath, the headless canonical figure draws every layer.
    assert differing == {"show_words", "show_order", "show_heatmap"}
    for key in differing:
        assert effective(app_settings, key) is False
        assert effective(headless, key) is True


def test_fit_to_monitor_default_frames_the_whole_canvas(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, canvas_size=(2560, 1440), show_heatmap=False
    )
    assert tuple(fig.layout.xaxis.range) == (0, 2560)
    assert tuple(fig.layout.yaxis.range) == (1440, 0)
    cropped = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=(2560, 1440),
        show_heatmap=False,
        fit_to_monitor=False,
    )
    assert cropped.layout.xaxis.range[0] > 0


def test_animation_shares_the_static_defaults(sample):
    """The replay is the same picture in motion — same opacity, framing, colour."""
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    anim = sps.animate_scanpath(
        words, fixations, pid, tid, canvas_size=(2560, 1440), show_order=False
    )
    assert tuple(anim.layout.xaxis.range) == (0, 2560)
    trail = [t for t in anim.data if t.name == "Scanpath A"]
    assert trail and trail[0].marker.opacity == pytest.approx(
        api.CANONICAL_FIGURE_DEFAULTS["fixation_opacity"]
    )


def test_plot_scanpath_drift_correction_snaps_to_line_centers(sample):
    # PRE-3 parity: the API applies the same correction as the app's control.
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    trial_words, _ = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    centers = set(alignment._line_centers(trial_words))

    def marker_ys(**kwargs):
        fig = sps.plot_scanpath(
            words, fixations, pid, tid, show_heatmap=False, **kwargs
        )
        return [
            float(y)
            for trace in fig.data
            if trace.mode and "markers" in trace.mode
            for y in trace.y
            if y is not None
        ]

    raw = marker_ys()
    corrected = marker_ys(drift_correction="cluster")
    assert not set(raw) <= centers  # raw gaze sits off the line centers
    assert set(corrected) <= centers
    assert len(corrected) == len(raw)


def test_plot_scanpath_drift_connectors_and_bad_algorithm(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        show_heatmap=False,
        drift_correction="attach",
        drift_connectors=True,
    )
    assert [t for t in fig.data if t.name == "drift"]
    with pytest.raises(ValueError, match="Unknown drift_correction 'slice'"):
        sps.plot_scanpath(words, fixations, pid, tid, drift_correction="slice")


def test_animate_scanpath_returns_frames(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    _, trial_fixations = data_module.filter_data(
        words, fixations, {"participants": [pid], "trials": [tid]}
    )
    fig = sps.animate_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
    assert isinstance(fig, go.Figure)
    assert len(fig.frames) > 1
    # The replay ends on the complete scanpath: the last frame's trail holds
    # every fixation of the trial, in order.
    trail = fig.frames[-1].data[0]
    assert list(trail.x) == list(trial_fixations["x"])
    assert list(trail.y) == list(trial_fixations["y"])


def test_animate_scanpath_autoplay_saves_kickoff(sample, tmp_path):
    # VIZ-10: autoplay on (default) → the saved HTML auto-starts the replay.
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.animate_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
    out = sps.save_figure(fig, tmp_path / "auto.html")
    assert "Plotly.animate" in out.read_text()


def test_animate_scanpath_no_autoplay_saves_paused(sample, tmp_path):
    # VIZ-10: autoplay=False → no kickoff, and the HTML is written paused.
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.animate_scanpath(
        words, fixations, pid, tid, canvas_size=(2560, 1440), autoplay=False
    )
    html = sps.save_figure(fig, tmp_path / "paused.html").read_text()
    assert "Plotly.animate" not in html


def test_compute_word_metrics_matches_the_hand_traced_trial():
    """Every measure the API returns on the synthetic ground-truth trial, against
    the values hand-traced in scanpath_studio/synthetic.py."""
    words = make_synthetic_words()
    fixations = make_synthetic_fixations()
    metrics = sps.compute_word_metrics(words, fixations).set_index("word_id")
    for column in (
        "first_fixation_ms",
        "first_pass_gaze_duration_ms",
        "regression_path_duration_ms",
        "total_fixation_duration_ms",
        "n_fixations",
        "skip_flag",
        "regression_in_flag",
        "regression_out_flag",
    ):
        actual = {int(k): v for k, v in metrics[column].items()}
        assert actual == pytest.approx(EXPECTED[column]), column
    assert len(metrics) == len(words)


def test_compute_word_metrics_keeps_precomputed_ia_measures(sample):
    """On an EyeLink IA export the pre-aggregated columns win (no recompute)."""
    words, fixations = sample
    metrics = sps.compute_word_metrics(words, fixations)
    assert len(metrics) == len(words)
    merged = metrics.merge(
        words[["participant_id", "trial_id", "word_id", "total_fixation_duration_ms"]],
        on=["participant_id", "trial_id", "word_id"],
        suffixes=("", "_source"),
    )
    pd.testing.assert_series_equal(
        merged["total_fixation_duration_ms"],
        merged["total_fixation_duration_ms_source"],
        check_names=False,
    )


def test_save_figure_html(sample, tmp_path):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(words, fixations, pid, tid)
    out = sps.save_figure(fig, tmp_path / "fig.html")
    assert out.is_file()
    assert out.stat().st_size > 0


def test_save_figure_bad_extension(sample, tmp_path):
    fig = go.Figure()
    with pytest.raises(ValueError, match="Unsupported extension"):
        sps.save_figure(fig, tmp_path / "fig.docx")


def test_save_figure_forwards_size(tmp_path, monkeypatch):
    """width/height/scale reach Kaleido for raster output (no Chrome needed)."""
    captured = {}
    fig = go.Figure()
    monkeypatch.setattr(fig, "write_image", lambda path, **kw: captured.update(kw))
    sps.save_figure(fig, tmp_path / "fig.png", scale=1, width=900, height=600)
    assert captured == {"scale": 1, "width": 900, "height": 600}


def test_save_figure_layers_one_file_per_layer(sample, tmp_path, monkeypatch):
    # VIZ-5: split into per-layer files named <layer>.<fmt>. Stub save_figure to
    # avoid Kaleido/Chrome — we're checking the split + naming, not the render.
    from pathlib import Path

    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(words, fixations, pid, tid, show_heatmap=True)

    def fake_save(f, path, **kw):
        Path(path).write_text("x")
        return Path(path)

    monkeypatch.setattr(api, "save_figure", fake_save)
    written = api.save_figure_layers(fig, tmp_path / "layers", fmt="svg")
    # Every layer a full scanpath draws is present, each its own file.
    assert {"word_boxes", "fixations", "saccades", "labels", "frame"} <= set(written)
    for layer, path in written.items():
        assert path.name == f"{layer}.svg"
        assert path.is_file()
