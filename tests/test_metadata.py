"""DATA-20 milestone 1 — the participant-level metadata table.

The acceptance check the item names: a categorical field, a numeric one, and a
participant the table forgot must prove that the field filters, projects onto
the trial path, and round-trips — and that an unmatched participant is
*reported* rather than dropped or guessed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import metadata as md


@pytest.fixture
def raw_table() -> pd.DataFrame:
    """Three readers; the data also contains a fourth (``p4``) with no row."""
    return pd.DataFrame(
        {
            "subject": ["p1", "p2", "p3"],
            "native_language": ["Hebrew", "English", "Hebrew"],
            "age": [24, 31, 19],
        }
    )


@pytest.fixture
def meta(raw_table) -> md.ParticipantMetadata:
    return md.build_participant_metadata(
        raw_table, "subject", source_name="readers.csv", participants=["p1", "p2", "p4"]
    )


class TestIngestion:
    def test_id_column_is_inferred_from_common_spellings(self, raw_table):
        assert md.infer_participant_id_column(raw_table) == "subject"
        assert (
            md.infer_participant_id_column(
                pd.DataFrame({"RECORDING_SESSION_LABEL": []})
            )
            is None  # empty frame: nothing to infer from
        )
        assert (
            md.infer_participant_id_column(
                pd.DataFrame({"RECORDING_SESSION_LABEL": ["a"], "x": [1]})
            )
            == "RECORDING_SESSION_LABEL"
        )
        assert md.infer_participant_id_column(pd.DataFrame({"x": [1]})) is None

    def test_fields_are_registered_with_grain_and_dtype(self, meta):
        assert meta.names == ("native_language", "age")
        assert meta.field("native_language").dtype == "categorical"
        assert meta.field("native_language").label == "Native language"
        assert meta.field("age").is_numeric
        assert all(field.grain == md.GRAIN_PARTICIPANT for field in meta.fields)
        assert all(field.source == "readers.csv" for field in meta.fields)

    def test_numeric_strings_count_as_numeric(self):
        frame = pd.DataFrame({"participant_id": ["p1", "p2"], "score": ["0.8", "0.6"]})
        built = md.build_participant_metadata(frame, "participant_id")
        assert built.field("score").is_numeric
        assert built.frame["score"].tolist() == [0.8, 0.6]

    def test_the_id_column_is_never_registered_as_a_field(self, meta):
        assert "subject" not in meta.names
        assert "participant_id" not in meta.names


class TestValidationNeverGuesses:
    def test_unmatched_ids_are_reported_on_both_sides(self, meta):
        assert meta.report.matched == ("p1", "p2")
        # p3 has a row but was not loaded; p4 was loaded but has no row.
        assert meta.report.only_in_table == ("p3",)
        assert meta.report.only_in_data == ("p4",)
        assert not meta.report.is_clean

    def test_a_duplicate_row_that_agrees_collapses_quietly(self):
        frame = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "native_language": ["Hebrew", "Hebrew"]}
        )
        built = md.build_participant_metadata(frame, "participant_id")
        assert built.report.duplicated == ("p1",)
        assert built.report.conflicting == ()
        assert built.values_for("p1") == {"native_language": "Hebrew"}

    def test_a_duplicate_row_that_disagrees_is_dropped_and_named(self):
        frame = pd.DataFrame(
            {"participant_id": ["p1", "p1"], "native_language": ["Hebrew", "English"]}
        )
        built = md.build_participant_metadata(frame, "participant_id")
        assert built.report.conflicting == ("p1",)
        # No groupby.first()-style winner: the reader has no value at all.
        assert built.values_for("p1") == {}

    def test_a_clean_join_says_so(self):
        frame = pd.DataFrame({"participant_id": ["p1"], "age": [30]})
        built = md.build_participant_metadata(
            frame, "participant_id", participants=["p1"]
        )
        assert built.report.is_clean

    def test_an_empty_or_unmapped_table_is_inert(self):
        empty = md.build_participant_metadata(pd.DataFrame(), "participant_id")
        assert empty.fields == ()
        assert md.participants_matching(empty, {"x": ["y"]}) is None
        assert md.options_for(empty, "x") == []


class TestFilteringIsParticipantFiltering:
    def test_a_categorical_selection_resolves_to_reader_ids(self, meta):
        assert md.participants_matching(meta, {"native_language": ["Hebrew"]}) == {
            "p1",
            "p3",
        }

    def test_no_constraint_means_no_narrowing_not_the_listed_readers(self, meta):
        """``None``, not the table's own ids — else readers the table forgot
        would silently vanish the moment a metadata table was attached."""
        assert md.participants_matching(meta, {}) is None
        assert md.participants_matching(meta, {"native_language": []}) is None
        assert md.participants_matching(meta, None, None) is None

    def test_a_numeric_range_keeps_readers_with_no_value(self):
        frame = pd.DataFrame(
            {"participant_id": ["p1", "p2", "p3"], "age": [20, 40, None]}
        )
        built = md.build_participant_metadata(frame, "participant_id")
        # p3 is unmeasured; a narrowing control must not exclude it.
        assert md.participants_matching(built, ranges={"age": (18.0, 25.0)}) == {
            "p1",
            "p3",
        }

    def test_constraints_combine(self, meta):
        assert md.participants_matching(
            meta, {"native_language": ["Hebrew"]}, {"age": (20.0, 30.0)}
        ) == {"p1"}

    def test_option_and_bound_helpers_drive_the_controls(self, meta):
        # Loaded readers only — see TestControlsOnlyOfferLoadedReaders. p3 is in
        # the table but not in the data, so its age (19) is not a bound.
        assert md.options_for(meta, "native_language") == ["English", "Hebrew"]
        assert md.bounds_for(meta, "age") == (24.0, 31.0)
        # A constant column offers no useful range.
        constant = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "p2"], "age": [30, 30]}),
            "participant_id",
        )
        assert md.bounds_for(constant, "age") is None


class TestProjectionOntoTheTrialPath:
    def test_columns_land_on_a_per_trial_frame(self, meta):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p2", "p4"],
                "trial_id": ["t1", "t2", "t3"],
            }
        )
        out = md.project(meta, combos)
        assert out["native_language"].tolist()[:2] == ["Hebrew", "English"]
        # p4 has no row: missing, not guessed.
        assert pd.isna(out["native_language"].iloc[2])
        assert out.loc[out["participant_id"] == "p1", "age"].item() == 24
        # The source frame is not mutated.
        assert "native_language" not in combos.columns

    def test_a_real_recorded_column_is_never_shadowed(self, meta):
        combos = pd.DataFrame(
            {"participant_id": ["p1"], "trial_id": ["t1"], "age": ["recorded"]}
        )
        assert md.project(meta, combos)["age"].tolist() == ["recorded"]

    def test_projection_is_a_no_op_without_a_participant_key(self, meta):
        frame = pd.DataFrame({"text_id": ["a"]})
        assert md.project(meta, frame) is frame


class TestRoundTrip:
    def test_payload_survives_json_shaped_serialization(self, meta):
        payload = md.to_payload(meta)
        assert payload["grain"] == md.GRAIN_PARTICIPANT
        restored = md.from_payload(payload)
        assert restored is not None
        assert restored.names == meta.names
        assert restored.values_for("p1") == meta.values_for("p1")
        assert restored.field("age").is_numeric

    def test_nothing_serializes_to_nothing(self):
        assert md.to_payload(None) is None
        assert md.from_payload(None) is None
        assert md.from_payload({"records": []}) is None

    def test_rejoin_refreshes_the_report_against_new_participants(self, meta):
        again = md.rejoin(meta, ["p1", "p2", "p3"])
        assert again.report.only_in_table == ()
        assert again.report.only_in_data == ()
        assert again.names == meta.names


# -----------------------------------------------------------------------------
# End to end in the running app. DATA-20's acceptance check is that a field
# works "with no code change per surface", so these assert the *effect* — the
# pool narrows, the field is offered as a chip, the value reaches the trial
# frame — rather than that some particular helper was called.
# -----------------------------------------------------------------------------


def _attach(at, ids, languages):
    """Attach a participant table the way the Data page's uploader would."""
    frame = pd.DataFrame(
        {
            "participant_id": list(ids),
            "native_language": list(languages),
            "age": [20 + 5 * i for i in range(len(ids))],
        }
    )
    built = md.build_participant_metadata(
        frame, "participant_id", source_name="readers.csv", participants=ids
    )
    at.session_state[md.SESSION_KEY] = built
    at.session_state[md.RAW_SESSION_KEY] = frame
    return built


class TestTheAppSurfaces:
    """One attached table; every consumer picks it up from the registry."""

    def _booted(self):
        from streamlit.testing.v1 import AppTest

        from tests.conftest import APP_SCRIPT

        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        readers = list(at.multiselect(key="filter_participants").options)
        assert len(readers) >= 2, f"demo should have several readers: {readers}"
        return at, readers

    def test_a_metadata_field_narrows_the_trial_pool(self):
        at, readers = self._booted()
        before = len(at.session_state["_trial_filters"].get("participants") or readers)

        # First reader speaks Hebrew, everyone else English.
        languages = ["Hebrew"] + ["English"] * (len(readers) - 1)
        _attach(at, readers, languages)
        at.run(timeout=90)
        assert not at.exception, at.exception

        at.session_state["filter_meta_native_language"] = ["Hebrew"]
        at.run(timeout=90)
        assert not at.exception, at.exception
        narrowed = at.session_state["_trial_filters"]["participants"]
        assert narrowed == [readers[0]], narrowed
        assert len(narrowed) < before

    def test_no_selection_does_not_narrow_to_the_listed_readers(self):
        """A table that forgets a reader must not silently exclude them."""
        at, readers = self._booted()
        # Deliberately omit the last reader from the table entirely.
        kept = readers[:-1]
        _attach(at, kept, ["Hebrew"] * len(kept))
        at.run(timeout=90)
        assert not at.exception, at.exception
        chosen = at.session_state["_trial_filters"].get("participants")
        assert chosen is None or set(chosen) == set(readers), chosen

    def test_the_field_is_offered_as_a_chip_and_drawn_with_its_value(self):
        at, readers = self._booted()
        attached = _attach(at, readers, ["Hebrew"] * len(readers))
        at.run(timeout=90)
        assert not at.exception, at.exception

        # The ✏️ Edit chips picker prunes `trial_chip_fields` to the fields it
        # offers, so surviving the round trip *is* being offered. (The picker
        # itself is a `sort_items` component, which AppTest cannot introspect.)
        at.session_state["trial_chip_fields"] = ["participant_id", "native_language"]
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert "native_language" in at.session_state["trial_chip_fields"]

        # And it is drawn in the strip above the plot, with the reader's value.
        strip = " ".join(m.value for m in at.markdown)
        assert "Native language = Hebrew" in strip, strip[:400]

        # Projection: the per-trial frame carries the value for each reader.
        combos = pd.DataFrame({"participant_id": readers, "trial_id": list(readers)})
        projected = md.project(attached, combos)
        assert projected["native_language"].tolist() == ["Hebrew"] * len(readers)

    def test_it_round_trips_through_save_and_restore(self):
        """The saved session carries the table, so restored `filter_meta_*`
        selections land on fields that exist."""
        import json

        from scanpath_studio import url_state

        at, readers = self._booted()
        _attach(at, readers, ["Hebrew"] * len(readers))
        at.run(timeout=90)

        payload = md.to_payload(at.session_state[md.SESSION_KEY])
        # Must survive a real JSON round trip, not just a dict copy.
        revived = md.from_payload(json.loads(json.dumps(payload, default=str)))
        assert revived is not None
        assert revived.names == ("native_language", "age")
        assert url_state is not None


def test_loader_bookkeeping_is_not_registered_as_a_field():
    """`data.read_tables` tags rows with `source_file`; that is not metadata.

    Caught on the CLI, where the table goes through the multi-file reader: the
    column showed up as a field called "Source file", offered as a filter and a
    chip, with one distinct value.
    """
    frame = pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "native_language": ["Hebrew", "English"],
            "source_file": ["readers", "readers"],
        }
    )
    built = md.build_participant_metadata(frame, "participant_id")
    assert built.names == ("native_language",)
    assert "source_file" not in built.frame.columns


class TestControlsOnlyOfferLoadedReaders:
    """A value belonging to a reader the report calls "not loaded — ignored"
    must not reach a filter: it can only ever empty the pool."""

    def test_options_exclude_unloaded_readers(self, meta):
        # `meta` joins a p1/p2/p3 table against loaded p1, p2, p4.
        assert meta.report.only_in_table == ("p3",)
        # p3 is the only Hebrew speaker besides p1, and holds the min age (19).
        assert md.options_for(meta, "native_language") == ["English", "Hebrew"]
        assert md.bounds_for(meta, "age") == (24.0, 31.0)

    def test_an_unjoined_table_still_offers_everything(self, raw_table):
        """With no participant list there is nothing to hide behind."""
        built = md.build_participant_metadata(raw_table, "subject")
        assert md.bounds_for(built, "age") == (19.0, 31.0)


class TestAnImpossibleNarrowingEmptiesThePool:
    """The highest-severity defect this feature surfaced, in *existing* code.

    `data.filter_trials` gated on `if participants:`, so an empty list — which
    only a set intersection can produce — read as "no constraint" and showed
    the whole corpus. A filter that matches nobody must show nobody.
    """

    def _frames(self):
        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t1", "t2"],
                "word_id": [1, 1],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t1", "t2"],
                "duration_ms": [200, 200],
            }
        )
        return words, fixations

    def test_none_means_no_constraint(self):
        from scanpath_studio.data import filter_trials

        words, fixations = self._frames()
        w, f = filter_trials(words, fixations, participants=None)
        assert len(w) == 2 and len(f) == 2

    def test_empty_means_nobody(self):
        from scanpath_studio.data import filter_trials

        words, fixations = self._frames()
        w, f = filter_trials(words, fixations, participants=[])
        assert w.empty and f.empty

    def test_an_impossible_metadata_combination_narrows_to_nothing(self, meta):
        # Hebrew speakers aged 40-50: p1 is Hebrew but 24, p3 is Hebrew but 19.
        assert (
            md.participants_matching(
                meta, {"native_language": ["Hebrew"]}, {"age": (40.0, 50.0)}
            )
            == set()
        )

    def test_a_range_only_filter_still_keeps_readers_with_no_row(self, meta):
        """p4 is loaded but has no row — as unmeasured as a NaN value."""
        assert "p4" in meta.report.only_in_data
        matched = md.participants_matching(meta, ranges={"age": (24.0, 26.0)})
        assert matched == {"p1", "p4"}
        # A *categorical* selection still excludes the unknown, like every
        # other membership filter in the app.
        assert "p4" not in md.participants_matching(
            meta, {"native_language": ["Hebrew"]}
        )

    def test_the_join_count_does_not_drift_on_a_rerun(self):
        """`rejoin` and `build` must agree on `matched`.

        A conflicting reader is in the table but carries no values, so it is
        neither matched nor "only in the data". Counting it as matched made
        "Joined to N readers" grow on the first rerun after attaching.
        """
        frame = pd.DataFrame(
            {
                "participant_id": ["p1", "p2", "p2"],
                "native_language": ["Hebrew", "English", "Arabic"],
            }
        )
        built = md.build_participant_metadata(
            frame, "participant_id", participants=["p1", "p2"]
        )
        again = md.rejoin(built, ["p1", "p2"])
        assert built.report.conflicting == ("p2",)
        assert built.report.matched == again.report.matched == ("p1",)
        assert again.report.only_in_data == ()


# -----------------------------------------------------------------------------
# DATA-20 round 2 — the three surfaces the first pass left out.
# -----------------------------------------------------------------------------


class TestCorpusGroupingByAReaderAttribute:
    """Milestone: group cohorts in Corpus Analysis by a metadata field.

    The whole design rests on one translation — a participant-grain constraint
    *is* a participant constraint — so these assert that a metadata group
    arrives at `aggregation.group_mask` as an ordinary `participant_id` spec and
    that the table is never joined onto the frames.
    """

    @staticmethod
    def _attached(languages=("Hebrew", "English", "Hebrew")):
        ids = [f"p{i + 1}" for i in range(len(languages))]
        frame = pd.DataFrame(
            {"participant_id": ids, "native_language": list(languages)}
        )
        return md.build_participant_metadata(
            frame, "participant_id", source_name="readers.csv", participants=ids
        )

    def test_a_metadata_group_becomes_a_participant_spec(self, monkeypatch):
        from scanpath_studio import aggregation, tabs

        attached = self._attached()
        monkeypatch.setattr(md, "active", lambda: attached)

        spec = tabs._group_spec("meta:native_language", ["Hebrew"])
        assert spec == {"participant_id": ["p1", "p3"]}, spec

        # And it selects exactly those readers' rows — no join, no new column.
        frame = pd.DataFrame(
            {"participant_id": ["p1", "p2", "p3"], "duration_ms": [1.0, 2.0, 3.0]}
        )
        selected = aggregation.apply_group(frame, spec)
        assert selected["participant_id"].tolist() == ["p1", "p3"]
        assert "native_language" not in selected.columns

    def test_a_group_matching_nobody_selects_nothing(self, monkeypatch):
        """`group_mask` reads an empty value list as *no constraint*, so an
        unmatched metadata group has to resolve to an impossible id instead —
        otherwise a group that should be empty would quietly select every row."""
        from scanpath_studio import aggregation, tabs

        attached = self._attached()
        monkeypatch.setattr(md, "active", lambda: attached)

        spec = tabs._group_spec("meta:native_language", ["Klingon"])
        frame = pd.DataFrame({"participant_id": ["p1", "p2"], "v": [1.0, 2.0]})
        assert aggregation.apply_group(frame, spec).empty

    def test_a_real_column_is_untouched_by_the_translation(self, monkeypatch):
        from scanpath_studio import tabs

        monkeypatch.setattr(md, "active", lambda: self._attached())
        assert tabs._group_spec("difficulty_level", ["Adv"]) == {
            "difficulty_level": ["Adv"]
        }
        assert tabs._group_spec("difficulty_level", []) == {}

    def test_the_picker_marks_where_a_field_came_from(self, monkeypatch):
        """A trial condition and a reader attribute answer different questions;
        a picker that hid the difference would invite the wrong one."""
        from scanpath_studio import tabs

        monkeypatch.setattr(md, "active", lambda: self._attached())
        assert tabs._metadata_group_fields() == ["meta:native_language"]
        assert tabs._pretty_col("meta:native_language") == "👤 Native language"

    def test_a_single_valued_field_is_not_offered(self, monkeypatch):
        """Nothing to split — and a one-group comparison is not a comparison."""
        from scanpath_studio import tabs

        monkeypatch.setattr(
            md, "active", lambda: self._attached(("Hebrew", "Hebrew", "Hebrew"))
        )
        assert tabs._metadata_group_fields() == []

    def test_the_group_values_come_from_the_table_not_the_frames(self, monkeypatch):
        """Neither frame carries the column, so the value picker has to read the
        attached table — and only the *loaded* readers' values (`joined_frame`),
        or it would offer a group that can only ever be empty."""
        from scanpath_studio import tabs

        ids = ["p1", "p2", "p3"]
        frame = pd.DataFrame(
            {
                "participant_id": ids + ["p9"],
                "native_language": ["Hebrew", "English", "Hebrew", "Klingon"],
            }
        )
        attached = md.build_participant_metadata(
            frame, "participant_id", source_name="readers.csv", participants=ids
        )
        monkeypatch.setattr(md, "active", lambda: attached)
        words = pd.DataFrame({"participant_id": ids})
        assert tabs._both_frame_values(words, words, "meta:native_language") == [
            "English",
            "Hebrew",
        ]


class TestTheExportOptOut:
    """Milestone 10 — per-field control over what leaves in the bundle."""

    @staticmethod
    def _frame():
        return pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "native_language": ["Hebrew", "English"],
                "age": [24, 31],
            }
        )

    def test_none_ships_every_field(self):
        from scanpath_studio.export import _selected_metadata_columns

        frame = self._frame()
        assert _selected_metadata_columns(frame, None) is frame

    def test_a_selection_keeps_the_id_and_those_fields_only(self):
        from scanpath_studio.export import _selected_metadata_columns

        out = _selected_metadata_columns(self._frame(), ("native_language",))
        assert list(out.columns) == ["participant_id", "native_language"]

    def test_clearing_every_field_leaves_the_table_out(self):
        """Not "ship a bare list of reader ids" — that is the one thing an
        opt-out must not do."""
        from scanpath_studio.export import _selected_metadata_columns

        assert _selected_metadata_columns(self._frame(), ()) is None

    def test_an_unknown_field_name_is_ignored_not_an_error(self):
        """A saved selection can outlive the table it named."""
        from scanpath_studio.export import _selected_metadata_columns

        out = _selected_metadata_columns(self._frame(), ("age", "shoe_size"))
        assert list(out.columns) == ["participant_id", "age"]

    def test_the_choice_reaches_the_zip(self, tmp_path):
        import io
        import zipfile

        from scanpath_studio import api
        from scanpath_studio.export import ExportOptions, bulk_export

        words, fixations = api.load_sample_data()[:2]
        combos = (
            fixations[["participant_id", "trial_id"]].drop_duplicates().head(1).copy()
        )
        keep = combos.iloc[0]
        words = words[
            (words.participant_id == keep.participant_id)
            & (words.trial_id == keep.trial_id)
        ]
        fixations = fixations[
            (fixations.participant_id == keep.participant_id)
            & (fixations.trial_id == keep.trial_id)
        ]

        def _names(fields):
            data, _progress = bulk_export(
                combos,
                words,
                fixations,
                canvas_width=1200,
                canvas_height=800,
                base_font_size=12,
                font_family="monospace",
                x_field="x",
                y_field="y",
                options=ExportOptions(
                    include_png=False,
                    include_svg=False,
                    include_plot_config=False,
                    include_fixations=True,
                    metadata_fields=fields,
                ),
                settings={"participant_metadata": self._frame()},
            )
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                members = zf.namelist()
                table = (
                    pd.read_csv(io.BytesIO(zf.read("metadata/participants.csv")))
                    if "metadata/participants.csv" in members
                    else None
                )
            return members, table

        _, full = _names(None)
        assert list(full.columns) == ["participant_id", "native_language", "age"]

        _, narrowed = _names(("age",))
        assert list(narrowed.columns) == ["participant_id", "age"]

        members, _ = _names(())
        assert not any(name.startswith("metadata/") for name in members), members


class TestGroupingEndToEnd:
    """The Groups subtab offers the attached field and splits the cohort by it."""

    @pytest.mark.timeout(180)
    def test_a_reader_attribute_appears_in_the_group_field_picker(self):
        from streamlit.testing.v1 import AppTest

        from scanpath_studio.constants import _VIEW_CORPUS
        from tests.conftest import APP_SCRIPT, pin_view

        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        readers = list(at.multiselect(key="filter_participants").options)
        assert len(readers) >= 2, readers

        # Half the cohort in each language, so the split has two real groups.
        languages = ["Hebrew" if i % 2 == 0 else "English" for i in range(len(readers))]
        _attach(at, readers, languages)
        pin_view(at, _VIEW_CORPUS)
        at.run(timeout=120)
        assert not at.exception, at.exception

        fields = [s for s in at.selectbox if s.key and s.key.endswith("_field")]
        assert fields, "no group field picker on the Corpus view"
        # `options` are the *rendered* labels (AppTest applies `format_func`),
        # which is the half that matters here: the picker has to say the field
        # describes a reader, not this trial.
        offered = {option for picker in fields for option in picker.options}
        assert "👤 Native language" in offered, sorted(offered)

        # Its own picker is unchanged: a real frame column is still offered
        # under its plain name, so the two provenances sit side by side.
        assert "Difficulty" in offered, sorted(offered)
        # (Selecting it and reading back the value multiselect is not asserted
        # here: `pin_view` is a one-shot request, and re-pinning it to stay on
        # the Corpus view discards a pending `set_value`. What the selection
        # *does* is covered above, on the pure translation.)


class TestTheWizardStep:
    """DATA-20 round 2 — *About your readers* is a step of the upload wizard.

    The user's call: the wizard is the **main** home, because a first-time
    uploader is answering exactly this question and would otherwise never meet
    the feature. The Data-page section stays, for the sources the wizard never
    runs for.
    """

    @staticmethod
    def _uploaded(monkeypatch):
        from scanpath_studio import app

        words = pd.DataFrame(
            {
                "reader": ["r0"] * 3,
                "trial": ["t1"] * 3,
                "IA_ID": [0, 1, 2],
                "IA_LABEL": ["the", "cat", "sat"],
                "IA_LEFT": [0, 80, 160],
                "IA_RIGHT": [80, 160, 240],
                "IA_TOP": [0, 0, 0],
                "IA_BOTTOM": [40, 40, 40],
            }
        )
        fixations = pd.DataFrame(
            {
                "reader": ["r0", "r0"],
                "trial": ["t1", "t1"],
                "CURRENT_FIX_X": [20.0, 100.0],
                "CURRENT_FIX_Y": [20.0, 20.0],
                "CURRENT_FIX_DURATION": [200, 220],
                "CURRENT_FIX_START": [0, 200],
            }
        )
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                words
                if kw["state_prefix"] == "col_map_words"
                else fixations
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )

    @pytest.mark.timeout(180)
    def test_the_step_renders_the_attach_panel(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        from scanpath_studio import app, wizard_shell
        from tests.conftest import APP_SCRIPT

        self._uploaded(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["setup_complete"] = False
        at.run(timeout=120)
        assert not at.exception, at.exception

        # The registry gained the step, in its place and optional.
        step = wizard_shell.STEPS_BY_ID["readers"]
        assert (step.number, step.required) == (5, False)
        assert [s.number for s in wizard_shell.STEPS] == [1, 2, 3, 4, 5, 6, 7]

        # …and its body is the participant-table panel: the id-column picker is
        # the widget that only exists once a table is being attached, so the
        # uploader is what proves the step rendered.
        uploader_keys = [u.key for u in at.file_uploader if u.key]
        assert "participant_metadata_upload" in uploader_keys, uploader_keys

    @pytest.mark.timeout(180)
    def test_the_finished_wizard_does_not_render_it_twice(self, monkeypatch):
        """The collapsed *Data & mapping* review panel and the 🗂️ Data page's
        own section would be two widgets on one key — Streamlit raises on that,
        so this is a crash test, not a cosmetic one."""
        from streamlit.testing.v1 import AppTest

        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT, pin_data_view

        self._uploaded(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.session_state["setup_complete"] = True
        pin_data_view(at)
        at.run(timeout=120)
        assert not at.exception, at.exception
        keys = [u.key for u in at.file_uploader if u.key]
        assert keys.count("participant_metadata_upload") == 1, keys
