"""ENG-4 — widget-driven end-to-end flows through ``streamlit.testing.v1.AppTest``.

``tests/test_apptest.py`` boots the app and asserts that surfaces *render*.
``test_column_mapping.py`` / ``test_filters.py`` / ``test_export.py`` cover the
mapping widget, the filtering helpers and ``bulk_export`` as units. Neither
side covers the path in between: the user changing a control and the *next*
render coming back re-derived. That is what this file does — it drives the real
widgets (the column-mapping selectbox, the condition + annotation filters, the
Export subtab's format pills and its Build button) and asserts on the data the
following render actually produced.

Booting is the expensive part (~1.5-3 s for the bundled demo, and every
interaction re-runs the whole script), so each test shares ONE ``AppTest``
across a sequence of interactions instead of booting per assertion.

Facts about the bundled demo used as expectations below:

- 3 readers × 12 word-level trials = **36** trials in the words table; only 2 of
  those readers have fixations, so the trial picker (built from fixations)
  offers **24**. Half of each is ``Adv``, half ``Ele``.
- ``universal_pos`` holds the 15 Universal-POS tags listed in ``_POS_TAGS``.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Optional

import pandas as pd
import pytest

from scanpath_studio.constants import AUTHOR_CHOICE
from scanpath_studio.data import load_sample_data
from tests.conftest import (
    APP_SCRIPT,
    SUBTAB_DATA_INSPECTION,
    SUBTAB_EXPORT,
    SUBTAB_KEY,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

SYNTHETIC_SOURCE = "Synthetic test trial"

DEMO_TRIALS_IN_PICKER = 24  # (participant, trial) pairs that have fixations
DEMO_TRIALS_IN_WORDS = 36  # …incl. the third reader, who has word rows only
DEMO_ADV_TRIALS_IN_PICKER = 12
DEMO_ADV_TRIALS_IN_WORDS = 18

# The Universal-POS values shipped with the demo's word table. Remapping the
# word "text" field onto that column must make every rendered word label one of
# these — i.e. no real word survived the remap.
_POS_TAGS = {
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
}


def _boot(
    *, synthetic: bool = False, timeout: int = 60, subtab: Optional[str] = None
) -> AppTest:
    """Boot the app. ``synthetic=True`` picks the 6-word synthetic trial (one
    trial, no raw gaze) instead of the bundled demo.

    ``subtab`` opens one of the per-trial subtabs: since PERF-3 the expensive
    ones render only when they are the selected tab, so a flow that reads Export
    or Data Inspection content has to open it, exactly as a user does.
    """
    at = AppTest.from_file(APP_SCRIPT)
    if synthetic:
        at.session_state["data_source_choice"] = SYNTHETIC_SOURCE
    if subtab:
        at.session_state[SUBTAB_KEY] = subtab
    at.run(timeout=timeout)
    return at


def _rerun(at: AppTest, subtab: Optional[str] = None, timeout: int = 60) -> AppTest:
    """Rerun, re-asserting the open subtab — a widget interaction can drop it."""
    if subtab:
        at.session_state[SUBTAB_KEY] = subtab
    return at.run(timeout=timeout)


def _clean(at: AppTest, note: str = "") -> None:
    assert not at.exception, f"{note} Streamlit exceptions: {at.exception}"
    assert at.error == [], f"{note} st.error calls: {[e.value for e in at.error]}"


def _trial_ids(at: AppTest) -> list[str]:
    """The trial ids currently offered by the picker (the live trial pool).

    Favorited trials are labelled ``★ <id>``; strip that so the ids compare.
    """
    box = [s for s in at.selectbox if s.key == "single_trial_id"]
    if not box:
        return []
    return [str(o).removeprefix("★ ").strip() for o in box[0].options]


def _metric(at: AppTest, label: str) -> Optional[str]:
    for m in at.metric:
        if m.label == label:
            return m.value
    return None


def _frames_with(at: AppTest, *columns: str) -> list[pd.DataFrame]:
    """Every rendered dataframe holding all of ``columns``."""
    out = []
    for element in at.dataframe:
        value = element.value
        cols = list(getattr(value, "columns", []))
        if all(c in cols for c in columns):
            out.append(value)
    return out


def _fixation_durations(at: AppTest) -> list:
    """``duration_ms`` from the rendered fixation-level table (Data Inspection →
    Raw data → Fixation-level), in render order."""
    frames = _frames_with(at, "duration_ms", "x")
    assert frames, "fixation-level table not rendered"
    return list(frames[0]["duration_ms"])


def _word_labels(at: AppTest) -> set[str]:
    """Distinct ``text`` values on the rendered word-level table (Data
    Inspection → Raw data → Word-level)."""
    frames = _frames_with(at, "word_id", "text")
    assert frames, "word-level table not rendered"
    return set(frames[0]["text"].dropna().astype(str))


@pytest.mark.timeout(120)
class TestColumnMappingOverrideFlow:
    """The Column-mapping panel is editable for the bundled demo (DATA-8).
    Overriding a field there must re-normalize the data the whole app renders,
    not just relabel the mapping table."""

    def test_remapping_word_text_re_derives_every_consumer(self):
        at = _boot(subtab=SUBTAB_DATA_INSPECTION)
        before = _word_labels(at)
        # Auto-detection maps the word label to EyeLink's IA_LABEL — real words,
        # not POS tags.
        assert at.session_state["_active_column_mapping"]["words"]["text"] == "IA_LABEL"
        assert not before <= _POS_TAGS, "demo should start with real word labels"

        at.selectbox(key="col_map_words_text").set_value("universal_pos")
        _rerun(at, SUBTAB_DATA_INSPECTION)
        _clean(at, "after remapping word text:")

        # The mapping the app normalized with — and the read-only table that
        # reports it — both name the new column.
        assert (
            at.session_state["_active_column_mapping"]["words"]["text"]
            == "universal_pos"
        )
        mapping_tables = _frames_with(at, "Table", "Field", "Mapped column")
        assert mapping_tables, "column-mapping table not rendered"
        table = mapping_tables[0]
        row = table[
            (table["Table"] == "Words/IA") & (table["Field"] == "Word text/label")
        ]
        assert list(row["Mapped column"]) == ["universal_pos"]
        # The panel says the auto-detected pick was overridden (ENG-9).
        assert any(
            "IA_LABEL" in c.value and "overridden" in c.value for c in at.caption
        ), "the mapping panel should flag the overridden auto-detection"

        # The frames were re-derived, not just re-labelled: every word label on
        # the word-level table is now a POS tag…
        after = _word_labels(at)
        assert after <= _POS_TAGS, f"non-POS labels survived the remap: {after}"
        assert {"NOUN", "VERB", "DET", "PUNCT"} <= after, after
        # …and the stimulus text, reconstructed downstream from the same column,
        # reads as POS tags too.
        stimuli = _frames_with(at, "Text ID", "# Words", "Text")
        assert stimuli, "stimuli table not rendered"
        passage = str(stimuli[0]["Text"].iloc[0]).split()
        assert passage, "empty reconstructed passage"
        assert set(passage) <= _POS_TAGS, passage[:10]

    def test_remapping_fixation_duration_re_derives_the_fixation_table(self):
        # The other mapping panel: `col_map_fix_*`. Point the required Duration
        # field at a different numeric column (next-saccade amplitude, degrees)
        # and the canonical `duration_ms` must carry that column's values — i.e.
        # the fixations frame was re-normalized, not relabelled.
        raw_fix = load_sample_data()[1]
        before_expected = list(raw_fix["CURRENT_FIX_DURATION"].head(5))
        after_expected = list(raw_fix["NEXT_SAC_AMPLITUDE"].head(5))
        assert before_expected != after_expected  # the remap must be observable

        at = _boot(subtab=SUBTAB_DATA_INSPECTION)
        assert (
            at.session_state["_active_column_mapping"]["fixations"]["duration"]
            == "CURRENT_FIX_DURATION"
        )
        # Normalization preserves row order, so the rendered fixation table's
        # first rows are the sample file's first rows.
        assert _fixation_durations(at)[:5] == before_expected

        at.selectbox(key="col_map_fix_duration").set_value("NEXT_SAC_AMPLITUDE")
        _rerun(at, SUBTAB_DATA_INSPECTION)
        _clean(at, "after remapping the fixation duration:")

        assert (
            at.session_state["_active_column_mapping"]["fixations"]["duration"]
            == "NEXT_SAC_AMPLITUDE"
        )
        assert _fixation_durations(at)[:5] == after_expected
        table = _frames_with(at, "Table", "Field", "Mapped column")[0]
        row = table[
            (table["Table"] == "Fixations") & (table["Field"] == "Duration (ms)")
        ]
        assert list(row["Mapped column"]) == ["NEXT_SAC_AMPLITUDE"]

    def test_clearing_a_required_field_shows_guidance_and_recovers(self):
        # Un-mapping a *required* field must degrade to the guidance view (the
        # raw tables + what's missing), not halt or crash — and re-mapping it
        # must bring the app straight back.
        at = _boot()
        assert len(_trial_ids(at)) == DEMO_TRIALS_IN_PICKER

        at.selectbox(key="col_map_words_word_id").set_value("(none)")
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        warnings = " ".join(w.value for w in at.warning)
        assert "Finish the column mapping" in warnings
        assert "Word/IA ID" in warnings, warnings
        # No plot/picker while the mapping is unusable, but the mapping control
        # itself stays editable so the user can fix it from where they are.
        assert _trial_ids(at) == []
        assert "col_map_words_word_id" in {s.key for s in at.selectbox}
        # The raw (un-normalized) words table is shown to choose the column from.
        assert _frames_with(at, "IA_ID", "IA_LABEL"), "raw words table not shown"

        at.selectbox(key="col_map_words_word_id").set_value("IA_ID")
        at.run(timeout=60)
        _clean(at, "after restoring the mapping:")
        assert [w.value for w in at.warning] == []
        assert len(_trial_ids(at)) == DEMO_TRIALS_IN_PICKER


@pytest.mark.timeout(120)
class TestTrialFilterFlow:
    """Condition + annotation filters, driven through their widgets, must narrow
    the pool every downstream surface sees — and emptying it must land on the
    UX-7 guidance state."""

    def test_condition_then_annotation_filter_narrow_the_pool(self):
        at = _boot(subtab=SUBTAB_DATA_INSPECTION)
        assert len(_trial_ids(at)) == DEMO_TRIALS_IN_PICKER
        assert _metric(at, "Trials") == str(DEMO_TRIALS_IN_WORDS)

        # (1) Condition filter: keep only the advanced-level readings.
        difficulty = at.multiselect(key="filter_difficulty_level")
        assert sorted(difficulty.options) == ["Adv", "Ele"]
        difficulty.set_value(["Adv"])
        at.run(timeout=60)
        _clean(at, "after the difficulty filter:")
        assert at.session_state["_trial_filters"]["metadata"] == {
            "difficulty_level": {"Adv"}
        }
        assert len(_trial_ids(at)) == DEMO_ADV_TRIALS_IN_PICKER
        assert _metric(at, "Trials") == str(DEMO_ADV_TRIALS_IN_WORDS)
        # The narrowing reached the data, not just the picker.
        graded = _frames_with(at, "difficulty_level")
        assert graded, "no rendered frame carries difficulty_level"
        for frame in graded:
            assert set(frame["difficulty_level"].dropna().unique()) == {"Adv"}

        # (2) Annotation: star the selected trial. Starring alone must not filter.
        stars = [
            c for c in at.checkbox if c.key and c.key.startswith("annotrial_star_")
        ]
        assert len(stars) == 1, [c.key for c in stars]
        stars[0].check()
        at.run(timeout=60)
        _clean(at, "after starring the trial:")
        store = at.session_state["trial_annotations"]
        assert len(store) == 1, store
        (_pid, starred_trial), entry = next(iter(store.items()))
        assert entry["star"] is True
        assert len(_trial_ids(at)) == DEMO_ADV_TRIALS_IN_PICKER

        # (3) Favorites-only narrows to exactly the starred trial.
        at.checkbox(key="filter_favorites").check()
        at.run(timeout=60)
        _clean(at, "after the favorites filter:")
        assert at.session_state["_trial_filters"]["favorites_only"] is True
        assert _trial_ids(at) == [starred_trial]
        # NOTE: this run is the last one possible on `at`. The picker's options are
        # now formatted with the ★ marker, and AppTest replays the widget's
        # `format_func` *outside* a script run — where the annotation store isn't
        # readable, so it returns the unmarked label and `Selectbox.index` raises
        # `ValueError: '<id>' is not in list` on the next `at.run()`. Assert here;
        # start a new AppTest for anything further.

    def test_emptying_the_pool_renders_the_guidance_state(self):
        # Favorites-only with nothing starred leaves no trials. The synthetic
        # source is used because it ships no raw-gaze table: annotation filters
        # are applied to the words/fixations frames only, so on the bundled demo
        # the leftover raw-gaze trial keeps the pool non-empty and this state is
        # never reached.
        at = _boot(synthetic=True)
        assert _trial_ids(at) == ["synthetic_2line_demo"]

        at.checkbox(key="filter_favorites").check()
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        # Guidance, not a plot: what happened, which filter did it, and a way out.
        # It is ONE panel now, not a warning banner plus loose markdown — the
        # three-block version read as three unrelated messages.
        assert [w.value for w in at.warning] == []
        body = " ".join(m.value for m in at.markdown)
        assert "No trials match your filters" in body
        # The count has to say what it counts; "(dataset has 1)" did not.
        assert "**0** of the **1 trials** in this dataset get through." in body
        assert "★ Favorites only" in body
        assert _trial_ids(at) == []
        assert [b for b in at.button if b.key == "clear_all_trial_filters"], (
            "the empty state must offer a one-click reset"
        )

        # Clearing just the culprit, rather than everything.
        one = [b for b in at.button if b.key == "clear_one_filter_0"]
        assert one, "each named filter must offer to clear only itself"
        one[0].click()
        at.run(timeout=60)
        _clean(at, "after clearing the one filter:")
        assert at.session_state["filter_favorites"] is False
        assert _trial_ids(at) == ["synthetic_2line_demo"]

    def test_clear_all_filters_resets_every_widget(self):
        at = _boot(synthetic=True)
        at.checkbox(key="filter_favorites").check()
        at.run(timeout=60)
        clear = [b for b in at.button if b.key == "clear_all_trial_filters"]
        assert clear
        clear[0].click()
        at.run(timeout=60)
        _clean(at, "after clearing the filters:")
        assert _trial_ids(at) == ["synthetic_2line_demo"]
        # The reset reaches the widgets themselves (they re-seed to "no
        # constraint"), not just the derived result.
        assert at.session_state["filter_favorites"] is False
        assert at.session_state["_trial_filters"] == {
            "participants": None,
            "metadata": {},
            "metadata_keys": {},
            "favorites_only": False,
            "required_tags": [],
            "excluded_tags": [],
        }


@pytest.mark.timeout(180)
class TestBulkExportFlow:
    """The Export subtab, driven end to end: pick formats, press Build export,
    get a zip whose contents match the trial pool and the live plot settings.

    Streamlit 1.59 made ``st.download_button`` drivable from ``AppTest``, and the
    test clicks the real one — but the bytes it serves still live in Streamlit's
    media-file manager, not in the element tree, so there is no way to *read* the
    zip back from the click. The payload is therefore still captured at the
    ``tabs.bulk_export`` seam by a wrapper that calls the real function.
    Everything up to and including the button press — the options collected from
    the widgets, the scope, the trial pool, the figure settings — is the real UI
    path; only the *inspection* of the bytes is substituted (ENG-36).
    """

    @staticmethod
    def _download_labels(at: AppTest) -> list[str]:
        return [str(getattr(e, "label", "")) for e in at.get("download_button")]

    @staticmethod
    def _zip_names(zip_bytes: bytes) -> set[str]:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            return set(zf.namelist())

    def test_build_export_zips_the_filtered_pool_and_honours_the_scope(
        self, monkeypatch
    ):
        from scanpath_studio import tabs

        calls: list = []
        real_bulk_export = tabs.bulk_export

        def capturing(*args, **kwargs):
            result = real_bulk_export(*args, **kwargs)
            calls.append((kwargs, result[0], result[1]))
            return result

        monkeypatch.setattr(tabs, "bulk_export", capturing)

        at = _boot(subtab=SUBTAB_EXPORT)
        assert self._download_labels(at) == ["⬇ Download (JSON)"], (
            "the zip download button must only appear after a build"
        )

        # Narrow to one reader — the export's default scope is the filtered pool.
        participants = at.multiselect(key="filter_participants")
        participants.set_value(["l7_1090"])
        at.run(timeout=60)
        _clean(at, "after narrowing to one participant:")
        pool = _trial_ids(at)
        assert len(pool) == DEMO_TRIALS_IN_PICKER // 2

        # Figures off (PDF is the default and needs Kaleido/Chrome); one table.
        at.pills(key="bulk_export_figfmts").set_value([])
        at.pills(key="bulk_export_tabular").set_value(["Fixations"])
        # Word boxes on, so the figure settings threaded into the export are
        # demonstrably the live ones rather than a default snapshot.
        at.toggle(key="global_show_words").set_value(True)
        at.run(timeout=60)
        _clean(at, "after choosing export artifacts:")

        build = [b for b in at.button if b.label == "Build export"]
        assert build, "Build export button missing"
        build[0].click()
        at.run(timeout=120)
        _clean(at, "after building the export:")

        assert len(calls) == 1, "Build export should run exactly one export"
        kwargs, zip_bytes, progress = calls[-1]
        assert progress.errors == []
        assert progress.finished_trials == len(pool)
        assert kwargs["settings"]["show_words"] is True
        options = kwargs["options"]
        assert options.figure_formats() == []
        assert options.include_fixations is True
        assert options.export_unfiltered is False

        expected = {"README.md"}
        for trial in pool:
            expected.add(f"per_trial/l7_1090__{trial}/fixations.csv")
            expected.add(f"per_trial/l7_1090__{trial}/plot_config.json")
        assert self._zip_names(zip_bytes) == expected

        # The per-trial config identifies its own trial, and records the live
        # word-box toggle in the file itself (not just in the call kwargs).
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            cfg = json.loads(zf.read(f"per_trial/l7_1090__{pool[0]}/plot_config.json"))
            fix_csv = pd.read_csv(
                io.BytesIO(zf.read(f"per_trial/l7_1090__{pool[0]}/fixations.csv"))
            )
        assert cfg["selection"]["participant_id"] == "l7_1090"
        assert cfg["selection"]["trial_id"] == pool[0]
        assert cfg["layers"]["words"] is True

        # Each per-trial table holds that trial's fixations and nothing else.
        # Expectation comes from the bundled CSV, not from the app's own frames.
        raw_fix = load_sample_data()[1]
        expected_rows = int(
            (
                (raw_fix["participant_id"] == "l7_1090")
                & (raw_fix["unique_trial_id"] == pool[0])
            ).sum()
        )
        assert expected_rows > 0
        assert len(fix_csv) == expected_rows
        assert set(fix_csv["participant_id"].unique()) == {"l7_1090"}
        assert set(fix_csv["trial_id"].unique()) == {pool[0]}
        assert sorted(fix_csv["duration_ms"]) == sorted(
            raw_fix.loc[
                (raw_fix["participant_id"] == "l7_1090")
                & (raw_fix["unique_trial_id"] == pool[0]),
                "CURRENT_FIX_DURATION",
            ]
        )

        # The rendered download button is the real delivery path — and since
        # Streamlit 1.59 it is drivable, so click it rather than only asserting
        # it exists: that is what proves the button is wired to a live payload
        # and that the app survives serving it (ENG-36).
        zip_button = [b for b in at.get("download_button") if b.label == "Download zip"]
        assert zip_button, "the zip download button should render after a build"
        zip_button[0].click()
        at.run(timeout=60)
        _clean(at, "after clicking the zip download button:")

        # Scope "All" ignores the participant filter: the other reader's trials
        # come back, while the picker stays narrowed.
        at.radio(key="bulk_export_scope").set_value("All")
        at.run(timeout=60)
        _clean(at, "after switching the export scope:")
        assert _trial_ids(at) == pool, "the scope radio must not change the pool"
        [b for b in at.button if b.label == "Build export"][0].click()
        at.run(timeout=120)
        _clean(at, "after building the whole-dataset export:")

        assert len(calls) == 2
        kwargs_all, zip_all, progress_all = calls[-1]
        assert kwargs_all["options"].export_unfiltered is True
        assert progress_all.errors == []
        assert progress_all.finished_trials == DEMO_TRIALS_IN_PICKER
        names_all = self._zip_names(zip_all)
        exported = {
            name.split("/")[1].split("__")[0]
            for name in names_all
            if name.startswith("per_trial/")
        }
        assert exported == {"l7_1090", "l37_1129"}
        assert len(names_all) == 1 + 2 * DEMO_TRIALS_IN_PICKER


@pytest.mark.timeout(180)
class TestRecoveryCachePanelFlow:
    """ENG-30 — the sidebar 🗄️ Recovery cache panel is the on-device cache's
    only user-visible surface, so it has to report the real store and its two
    controls have to reach ``persistence`` (pause saving, forget what's saved).
    """

    @staticmethod
    def _boot_local(tmp_path, monkeypatch) -> AppTest:
        """Boot with persistence forced on and pointed at a throwaway folder.

        ``st.context.url`` is empty under AppTest, so the loopback check would
        otherwise report a hosted deployment; the env override is the supported
        way in. ``SCANPATH_STUDIO_STATE_DIR`` keeps the test off the real
        ``~/.cache`` folder.
        """
        monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
        monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
        return _boot(synthetic=True)

    def test_panel_reports_the_store_and_its_controls_drive_persistence(
        self, tmp_path, monkeypatch
    ):
        from scanpath_studio import persistence

        at = self._boot_local(tmp_path, monkeypatch)
        _clean(at, "cache panel:")

        # Working in the app writes the cache — the panel's own claim.
        manifest = tmp_path / "manifest.json"
        assert manifest.is_file()
        assert persistence.cache_status(tmp_path)["settings"] > 0

        toggles = [t for t in at.toggle if t.key == "persist_local_saving"]
        assert toggles, "the saving toggle is missing from the panel"
        assert toggles[0].value is True

        # Off → the pause flag is set and the next run writes nothing new.
        written = manifest.stat().st_mtime_ns
        at = toggles[0].set_value(False).run(timeout=60)
        _clean(at, "after pausing:")
        # AppTest's session-state proxy has no .get, so read the flag directly.
        assert at.session_state["_local_persistence_paused"] is True
        at.session_state["global_show_heatmap"] = not bool(
            at.session_state["global_show_heatmap"]
        )
        at = at.run(timeout=60)
        assert manifest.stat().st_mtime_ns == written

        # Forget deletes the store; saving stays paused, so it does not come
        # straight back on the same run's end-of-run save.
        forget = [b for b in at.button if "Forget" in str(b.label)]
        assert forget, "the Forget button is missing from the panel"
        at = forget[0].click().run(timeout=60)
        _clean(at, "after forgetting:")
        assert not manifest.exists()
        assert not persistence.cache_status(tmp_path)["exists"]

    def test_panel_says_nothing_is_stored_on_a_hosted_deployment(self, monkeypatch):
        # No override and no loopback URL under AppTest == the hosted case.
        monkeypatch.delenv("SCANPATH_STUDIO_PERSIST", raising=False)
        at = _boot(synthetic=True)
        _clean(at, "hosted cache panel:")
        assert not [t for t in at.toggle if t.key == "persist_local_saving"]
        captions = " ".join(str(c.value) for c in at.caption)
        assert "Off here." in captions


class TestAuthoringEditorFlow:
    """BUG-19 — the ✏️ Author a scanpath grid, driven the way a browser drives it.

    ``st.data_editor`` keeps its edits as a *delta* against the frame it was
    handed, and the browser re-sends that delta on every rerun. The editor used
    to feed its own return value back in as the next run's input, so the delta
    was applied twice; after a row deletion the frame also picked up a gapped
    index, which ``num_rows="dynamic"`` cannot add rows to. From there edits
    landed on the wrong rows and rows disappeared — the reported "some rows can't
    be edited". The base frame must stay stable and range-indexed no matter how
    many reruns a live edit survives.
    """

    #: One edit, one added row and one deletion — what the browser holds after a
    #: user has been working in the grid for a moment.
    _DELTA = {
        "edited_rows": {0: {"duration_ms": 999}},
        "added_rows": [{"word_id": 2, "x": 100.0, "y": 100.0, "duration_ms": 300}],
        "deleted_rows": [1],
    }

    def _author(self) -> AppTest:
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = AUTHOR_CHOICE
        at.run(timeout=60)
        return at

    @staticmethod
    def _editor_key(at: AppTest) -> str:
        revision = int(at.session_state["_author_events_editor_revision"])
        return f"author_events_editor_{revision}"

    def test_the_editor_base_survives_repeated_reruns_with_a_live_edit(self):
        at = self._author()
        _clean(at, "authoring source:")
        base = at.session_state["_authored_events_frame"]
        original = base.copy()

        for _ in range(4):
            at.session_state[self._editor_key(at)] = dict(self._DELTA)
            at = at.run(timeout=60)
            _clean(at, "after an authoring edit:")
            base = at.session_state["_authored_events_frame"]
            # A gapped index is the failure mode: it disables row-adding and
            # misaligns every subsequent edit.
            assert list(base.index) == list(range(len(base)))
            pd.testing.assert_frame_equal(base, original)

    def test_a_new_stimulus_reseeds_the_grid(self):
        """The base is stable, but not frozen — new text means new rows."""
        at = self._author()
        before = len(at.session_state["_authored_events_frame"])
        at.session_state["author_text"] = "one two three"
        at = at.run(timeout=60)
        _clean(at, "after changing the stimulus:")
        after = at.session_state["_authored_events_frame"]
        assert len(after) == 3 != before
        assert list(after.index) == [0, 1, 2]
        geometry_tables = [
            frame
            for frame in at.dataframe
            if {"text", "word_id", "line_idx", "x", "y", "width", "height"}
            <= set(frame.value.columns)
        ]
        assert geometry_tables, "parsed word geometry preview is missing"
        assert geometry_tables[0].value["text"].tolist() == ["one", "two", "three"]

    def test_a_row_with_neither_xy_nor_valid_target_is_called_out(self):
        at = self._author()
        at.session_state[self._editor_key(at)] = {
            "edited_rows": {1: {"word_id": 999, "x": None, "y": None}},
            "added_rows": [],
            "deleted_rows": [],
        }
        at = at.run(timeout=60)
        _clean(at, "with an unusable authoring row:")
        warnings = " ".join(str(w.value) for w in at.warning)
        assert "finite X/Y" in warnings, (
            "an undrawable row was dropped without saying so"
        )
        assert "Row 2" in warnings


@pytest.mark.timeout(180)
class TestCrossDatasetCompareFlow:
    """CMP-8 — pick scanpath B out of a *different* dataset and render it.

    Driven through the real widgets: turn Compare on, pick the second dataset,
    and assert the figure builds without an error and the two panels describe
    two different corpora.
    """

    def test_comparing_against_another_dataset_renders(self):
        from scanpath_studio.compare_source import COMPARE_SOURCE_KEY

        at = _boot()
        assert not at.exception, at.exception

        at.session_state["single_compare_toggle"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception

        # The picker offers the other built-in sources; the active one is not
        # offered (that is what "This dataset" already means).
        picker = at.selectbox(key=COMPARE_SOURCE_KEY)
        assert "This dataset" in picker.options
        assert SYNTHETIC_SOURCE in picker.options
        assert "Bundled Demo" not in picker.options

        picker.set_value(SYNTHETIC_SOURCE)
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert [e.value for e in at.error] == []

        # B now comes out of the synthetic corpus, whose single trial is `t1`.
        compare = at.selectbox(key="single_compare_trial")
        assert compare.value is not None
        assert at.session_state["_share_selection"]["compare"]["source"] == (
            SYNTHETIC_SOURCE
        )

    def test_overlay_resolves_to_a_split_layout_without_losing_the_choice(self):
        from scanpath_studio.compare_source import COMPARE_SOURCE_KEY

        at = _boot()
        at.session_state["single_compare_toggle"] = True
        at.session_state["single_compare_layout"] = "Overlay"
        at.session_state[COMPARE_SOURCE_KEY] = SYNTHETIC_SOURCE
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert [e.value for e in at.error] == []
        # §5.3: resolved for this render, but the user's stored choice stands so
        # a same-dataset pair gets Overlay straight back.
        assert at.session_state["single_compare_layout"] == "Overlay"

    def test_bs_filters_do_not_disturb_the_main_pool(self):
        from scanpath_studio.compare_source import COMPARE_SOURCE_KEY

        at = _boot()
        at.session_state["single_compare_toggle"] = True
        at.session_state[COMPARE_SOURCE_KEY] = SYNTHETIC_SOURCE
        at.run(timeout=90)
        assert not at.exception, at.exception

        before = _trial_ids(at)
        # B's filter set lives under the `cmp` prefix; writing one must not
        # touch `_trial_filters`, which scopes the whole app's pool.
        at.session_state["cmpfilter_participants"] = ["nobody"]
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert _trial_ids(at) == before
        # `at.session_state` has no `.get` — membership first (conftest note).
        main_filters = (
            at.session_state["_trial_filters"]
            if "_trial_filters" in at.session_state
            else {}
        )
        assert main_filters.get("participants") is None
