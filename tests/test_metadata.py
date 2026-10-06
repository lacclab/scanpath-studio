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
        assert meta.field("native_language").label == "native_language"
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


class TestZeroPaddedReaderIds:
    """BUG-59: a CSV reads reader `007` as 7; the data kept "007"."""

    def test_the_table_joins_to_the_zero_padded_readers(self):
        table = pd.DataFrame({"participant_id": [7, 12], "age": [24, 31]})
        built = md.build_participant_metadata(
            table, "participant_id", participants=["007", "012"]
        )
        assert built.report.matched == ("007", "012")
        assert built.values_for("007") == {"age": 24}

    def test_a_rejoin_after_the_data_changed_matches_them_too(self):
        table = pd.DataFrame({"participant_id": [7, 12], "age": [24, 31]})
        built = md.build_participant_metadata(table, "participant_id")
        assert md.rejoin(built, ["007", "012"]).report.matched == ("007", "012")


class TestABlankRowIsNoOne:
    """BUG-60: the blank row a spreadsheet leaves at the end became a reader,
    trial or text named "nan" — pandas 3 keeps a missing id as NaN, and the
    `!= ""` guard let it through."""

    def test_participant_table(self, tmp_path):
        path = tmp_path / "readers.csv"
        path.write_text("participant_id,age\np01,24\np02,31\n,\n")
        built = md.build_participant_metadata(
            pd.read_csv(path), "participant_id", participants=["p01", "p02"]
        )
        assert built.frame["participant_id"].tolist() == ["p01", "p02"]
        assert built.report.only_in_table == ()

    def test_trial_table_keyed_by_reader_and_trial(self):
        table = pd.DataFrame(
            {
                "pid": ["p1", None, "p1"],
                "trial": ["t1", "t2", None],
                "list": list("ABC"),
            }
        )
        built = md.build_trial_metadata(table, "trial", participant_column="pid")
        assert built.frame["trial_id"].tolist() == ["t1"]

    def test_text_table_with_a_composite_id(self):
        """A missing part used to raise inside the join, not just leak."""
        table = pd.DataFrame(
            {
                "article": ["a1", "a1", None],
                "level": ["Adv", None, "Ele"],
                "n": [1, 2, 3],
            }
        )
        built = md.build_text_metadata(table, ["article", "level"])
        assert built.frame["text_id"].tolist() == ["a1_Adv"]


class TestAnInfiniteValueIsUnknown:
    """Round 10, finding 3: one ``inf`` in a numeric field became a slider end,
    which Streamlit refuses — the whole filter panel failed. It is now no value,
    at every grain, and the range covers the finite records."""

    SCORES = [1.0, float("inf"), -float("inf"), 4.0]

    def _built(self, grain):
        if grain == "participant":
            table = pd.DataFrame({"pid": list("abcd"), "score": self.SCORES})
            return md.build_participant_metadata(
                table, "pid", participants=list("abcd")
            )
        if grain == "trial":
            table = pd.DataFrame({"trial": list("abcd"), "score": self.SCORES})
            return md.build_trial_metadata(table, "trial")
        table = pd.DataFrame({"text": list("abcd"), "score": self.SCORES})
        return md.build_text_metadata(table, "text")

    @pytest.mark.parametrize("grain", ["participant", "trial", "text"])
    def test_the_extent_is_finite_and_the_rest_unknown(self, grain):
        built = self._built(grain)
        assert md.numeric_extent(built, "score") == (1.0, 4.0)
        (field,) = [f for f in built.fields if f.name == "score"]
        assert field.dtype == "numeric" and field.n_missing == 2

    def test_an_integer_field_stays_integer(self, meta):
        assert pd.api.types.is_integer_dtype(meta.frame["age"])


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

        # And it is drawn in the chip table above the plot, with the reader's value.
        table = " ".join(m.value for m in at.markdown)
        assert ">native_language</th>" in table and ">Hebrew</td>" in table, table[:400]

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


class TestARestoredTableSurvivesTheDataPage:
    """DATA-38 — a table the recovery cache (or a saved config) brings back has
    no file in its uploader, and the Data page reads an empty uploader as "the
    user just removed it" (UX-115). Unmarked, the first visit to that page
    detached exactly what the restore brought back."""

    def _booted_with(self, *, restored: bool):
        from tests.conftest import pin_data_view

        at, readers = TestTheAppSurfaces()._booted()
        built = md.build_participant_metadata(
            pd.DataFrame(
                {
                    "participant_id": readers,
                    "native_language": ["Hebrew"] + ["English"] * (len(readers) - 1),
                }
            ),
            "participant_id",
            source_name="readers.csv",
        )
        if restored:
            md.mark_restored(at.session_state, "participant", built)
        else:
            # A table attached from a file that has since left the uploader.
            at.session_state[md.SESSION_KEY] = built
            at.session_state[md.RAW_SESSION_KEY] = built.frame
            at.session_state[md.FILE_SESSION_KEY] = "some-file-id"
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        self.readers = readers
        return at

    def test_a_restored_table_stays_attached(self):
        from scanpath_studio.constants import _VIEW_SCANPATH
        from tests.conftest import pin_view

        at = self._booted_with(restored=True)
        assert at.session_state[md.SESSION_KEY].names == ("native_language",)
        # … and its field still narrows the pool, which is what the bug took.
        pin_view(at, _VIEW_SCANPATH)
        at.session_state["filter_meta_native_language"] = ["Hebrew"]
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert at.session_state["_trial_filters"]["participants"] == [self.readers[0]]

    def test_a_restored_table_can_still_be_detached(self):
        """No file chip to dismiss, so the ✕ Detach comes back for this case."""
        from tests.conftest import pin_data_view

        at = self._booted_with(restored=True)
        detach = [
            b for b in at.button if b.key == "participant_metadata_detach_restored"
        ]
        assert detach, "no ✕ Detach for a restored table"
        detach[0].click()
        pin_data_view(at)
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert md.SESSION_KEY not in at.session_state
        assert not md.is_restored(at.session_state, "participant")

    def test_removing_an_uploaded_file_still_detaches_it(self):
        """UX-115 unchanged: a table that *did* come from the uploader goes when
        its file does."""
        at = self._booted_with(restored=False)
        assert md.SESSION_KEY not in at.session_state


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
        assert tabs._pretty_col("meta:native_language") == "👤 native_language"

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


class TestCorpusGroupingByTrialAndTextAttributes:
    """AN-31: Groups splits and filters by the trial and text tables too.

    The same translation as the reader grain, one and two grains over — a trial
    field resolves to ``(participant_id, trial_id)`` readings and a text field to
    text ids, the way the Scanpath trial filters narrow — so each still arrives
    at `aggregation.group_mask` as a spec over columns the frames already have,
    and neither table is ever joined onto them.
    """

    #: Two readers, each reading two trials; trial t1 is text A, t2 text B.
    FIX = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t2", "t1", "t2"],
            "text_id": ["A", "B", "A", "B"],
            "duration_ms": [1.0, 2.0, 3.0, 4.0],
        }
    )

    @staticmethod
    def _attach(monkeypatch, *, participants=None, trials=None, texts=None):
        monkeypatch.setattr(md, "active", lambda: participants)
        monkeypatch.setattr(md, "active_trials", lambda: trials)
        monkeypatch.setattr(md, "active_texts", lambda: texts)

    @staticmethod
    def _trials(**kwargs):
        frame = pd.DataFrame(
            {"trial_id": ["t1", "t2"], "qa_condition": ["easy", "hard"]}
        )
        return md.build_trial_metadata(
            frame, "trial_id", source_name="trials.csv", **kwargs
        )

    @staticmethod
    def _texts():
        frame = pd.DataFrame({"text_id": ["A", "B"], "genre": ["news", "fiction"]})
        return md.build_text_metadata(
            frame, "text_id", source_name="texts.csv", keys={"A", "B"}
        )

    def test_a_trial_field_becomes_every_reading_of_that_trial(self, monkeypatch):
        from scanpath_studio import aggregation, tabs

        self._attach(monkeypatch, trials=self._trials())
        spec = tabs._group_spec("trialmeta:qa_condition", ["easy"], self.FIX, self.FIX)
        assert spec == {("participant_id", "trial_id"): [("p1", "t1"), ("p2", "t1")]}
        selected = aggregation.apply_group(self.FIX, spec)
        assert selected["duration_ms"].tolist() == [1.0, 3.0]
        assert "qa_condition" not in selected.columns

    def test_a_reader_paired_trial_table_keeps_to_its_reading(self, monkeypatch):
        """The headless-only kind (DATA-29): a row describes one reading."""
        from scanpath_studio import aggregation, tabs

        frame = pd.DataFrame(
            {
                "reader": ["p1", "p2"],
                "trial_id": ["t1", "t2"],
                "qa_condition": ["easy", "easy"],
            }
        )
        paired = md.build_trial_metadata(
            frame, "trial_id", participant_column="reader", source_name="trials.csv"
        )
        self._attach(monkeypatch, trials=paired)
        spec = tabs._group_spec("trialmeta:qa_condition", ["easy"], self.FIX, self.FIX)
        selected = aggregation.apply_group(self.FIX, spec)
        assert selected["duration_ms"].tolist() == [1.0, 4.0]

    def test_a_text_field_becomes_text_ids_on_the_by_text_column(self, monkeypatch):
        from scanpath_studio import aggregation, tabs

        self._attach(monkeypatch, texts=self._texts())
        spec = tabs._group_spec("textmeta:genre", ["fiction"], self.FIX, self.FIX)
        assert spec == {"text_id": ["B"]}
        assert aggregation.apply_group(self.FIX, spec)["duration_ms"].tolist() == [
            2.0,
            4.0,
        ]
        # `unique_text_id` wins where the frames carry it, as in the filters.
        uniq = self.FIX.assign(unique_text_id=["uA", "uB", "uA", "uB"])
        assert tabs._group_text_column(uniq, uniq) == "unique_text_id"

    def test_an_unmatched_or_detached_field_selects_nothing(self, monkeypatch):
        from scanpath_studio import aggregation, tabs

        self._attach(monkeypatch, trials=self._trials(), texts=self._texts())
        for col in ("trialmeta:qa_condition", "textmeta:genre"):
            spec = tabs._group_spec(col, ["Klingon"], self.FIX, self.FIX)
            assert aggregation.apply_group(self.FIX, spec).empty, col
        self._attach(monkeypatch)  # every table detached mid-run
        for col in ("trialmeta:qa_condition", "textmeta:genre"):
            spec = tabs._group_spec(col, ["easy"], self.FIX, self.FIX)
            assert aggregation.apply_group(self.FIX, spec).empty, col

    def test_it_combines_with_a_reader_field_and_a_frame_column(self, monkeypatch):
        """A filter set ANDs its constraints, whichever table each came from."""
        from scanpath_studio import aggregation, tabs

        readers = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "p2"], "l1": ["Hebrew", "English"]}),
            "participant_id",
            participants=["p1", "p2"],
        )
        self._attach(
            monkeypatch,
            participants=readers,
            trials=self._trials(),
            texts=self._texts(),
        )
        spec: dict = {}
        for col, values in (
            ("meta:l1", ["English"]),
            ("trialmeta:qa_condition", ["easy", "hard"]),
            ("textmeta:genre", ["news"]),
            ("text_id", ["A", "B"]),  # an explicit *Texts* pick, intersected
        ):
            for column, allowed in tabs._group_spec(
                col, values, self.FIX, self.FIX
            ).items():
                tabs._merge_spec(spec, column, allowed)
        assert spec["text_id"] == ["A"]
        assert aggregation.apply_group(self.FIX, spec)["duration_ms"].tolist() == [3.0]

        # Two trial constraints that share no reading intersect to nothing,
        # never to `[]` (which `group_mask` would read as "everyone").
        tabs._merge_spec(spec, ("participant_id", "trial_id"), [("p9", "t9")])
        assert aggregation.apply_group(self.FIX, spec).empty

    def test_the_picker_offers_every_grain_and_marks_each(self, monkeypatch):
        from scanpath_studio import tabs

        readers = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "p2"], "l1": ["Hebrew", "English"]}),
            "participant_id",
            participants=["p1", "p2"],
        )
        self._attach(
            monkeypatch,
            participants=readers,
            trials=self._trials(),
            texts=self._texts(),
        )
        assert tabs._metadata_group_fields() == [
            "meta:l1",
            "trialmeta:qa_condition",
            "textmeta:genre",
        ]
        assert tabs._pretty_col("trialmeta:qa_condition") == "📋 qa_condition"
        assert tabs._pretty_col("textmeta:genre") == "📄 genre"
        assert tabs._both_frame_values(None, None, "textmeta:genre") == [
            "fiction",
            "news",
        ]
        assert tabs._both_frame_values(None, None, "trialmeta:qa_condition") == [
            "easy",
            "hard",
        ]

    def test_a_trial_cohort_raises_no_word_only_warning(self):
        """Both key columns are on the fixation table, so nothing is missing."""
        from scanpath_studio import tabs

        class _Host:
            def __init__(self):
                self.warned: list = []

            def warning(self, body):
                self.warned.append(body)

        host = _Host()
        pairs = {("participant_id", "trial_id"): [("p1", "t1")]}
        tabs._warn_word_only_group_fields(host, self.FIX, pairs)
        assert host.warned == []
        tabs._warn_word_only_group_fields(
            host, self.FIX.drop(columns="trial_id"), pairs
        )
        assert host.warned and "Participant × Trial" in host.warned[0]


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

        words, fixations = api.load_sample_data(names="canonical")[:2]
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
                # The exported reader's row, beside one the bundle must not
                # carry: metadata is scoped to the readers exported.
                settings={
                    "participant_metadata": self._frame().assign(
                        participant_id=[str(keep.participant_id), "elsewhere"]
                    )
                },
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
        assert len(full) == 1

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
        # PERF-9: only the open Corpus subtab renders.
        at.session_state["corpus_subtab"] = "Groups"
        at.run(timeout=120)
        assert not at.exception, at.exception

        fields = [s for s in at.selectbox if s.key and s.key.endswith("_field")]
        assert fields, "no group field picker on the Corpus view"
        # `options` are the *rendered* labels (AppTest applies `format_func`),
        # which is the half that matters here: the picker has to say the field
        # describes a reader, not this trial.
        offered = {option for picker in fields for option in picker.options}
        assert "👤 native_language" in offered, sorted(offered)

        # Its own picker is unchanged: a real frame column is still offered
        # under its plain name, so the two provenances sit side by side.
        assert "difficulty_level" in offered, sorted(offered)
        # (Selecting it and reading back the value multiselect is not asserted
        # here: `pin_view` is a one-shot request, and re-pinning it to stay on
        # the Corpus view discards a pending `set_value`. What the selection
        # *does* is covered above, on the pure translation.)

    @pytest.mark.timeout(240)
    @pytest.mark.parametrize("grain", ["trial", "text"])
    def test_a_trial_or_text_attribute_splits_the_cohort(self, grain):
        """AN-31, end to end on the demo: the field is offered, and picking it
        narrows the cohort to exactly the rows the table describes. The
        selection is seeded into session state alongside the view request, in
        the one run, rather than through a `set_value` a re-pin would discard.
        """
        from streamlit.testing.v1 import AppTest

        from scanpath_studio import api
        from scanpath_studio.constants import _VIEW_CORPUS
        from tests.conftest import APP_SCRIPT, pin_view

        _words, fixations = api.load_sample_data(names="canonical")
        if grain == "trial":
            ids = sorted(fixations["trial_id"].astype(str).unique())
            column, field, option = "trial_id", "qa_condition", "trialmeta:qa_condition"
        else:
            ids = sorted(fixations["unique_text_id"].astype(str).unique())
            column, field, option = "unique_text_id", "genre", "textmeta:genre"
        values = ["x" if i % 2 == 0 else "y" for i in range(len(ids))]
        frame = pd.DataFrame({column: ids, field: values})
        expected = int(fixations[column].astype(str).isin(ids[0::2]).sum())
        assert 0 < expected < len(fixations)

        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        if grain == "trial":
            at.session_state[md.TRIAL_SESSION_KEY] = md.build_trial_metadata(
                frame, column, source_name="trials.csv"
            )
            at.session_state[md.TRIAL_RAW_SESSION_KEY] = frame
        else:
            at.session_state[md.TEXT_SESSION_KEY] = md.build_text_metadata(
                frame, column, source_name="texts.csv", keys=set(ids)
            )
            at.session_state[md.TEXT_RAW_SESSION_KEY] = frame
        pin_view(at, _VIEW_CORPUS)
        at.session_state["corpus_subtab"] = "Groups"
        at.session_state["pgrp_field"] = option
        at.session_state["pgrp_g"] = ["x"]
        at.run(timeout=120)
        assert not at.exception, at.exception

        offered = {
            label
            for picker in at.selectbox
            if picker.key == "pgrp_field"
            for label in picker.options
        }
        mark = "📋" if grain == "trial" else "📄"
        assert f"{mark} {md.field_label(field)}" in offered, sorted(offered)
        captions = [c.value for c in at.caption if "fixations in scope" in c.value]
        assert captions and f"{expected} fixations in scope" in captions[0], captions


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

        # UX-53 folded the seven steps into two linear parts; UX-113 unfolded
        # them back to five, flat and same-size; UX-114 folded "Keep extra
        # fields" back into "Map data fields" (per-table pickers now sit
        # directly under each table's own mapping), leaving four; UX-129
        # folded "Map data fields" itself into "Upload data tables" (every
        # table already uploaded and mapped in the same row), leaving three.
        # The participant table stays up beside the uploads — it is an
        # upload, so it belongs with them, under no heading of its own (r6).
        assert [s.number for s in wizard_shell.STEPS] == [1, 2, 3]
        # UX-174 r2 renamed part 1 when it gained the Description field.
        assert [s.title for s in wizard_shell.STEPS] == [
            "Name & description",
            "Upload data tables",
            "Recording setup",
        ]
        assert "readers" not in wizard_shell.STEPS_BY_ID
        assert "fields" not in wizard_shell.STEPS_BY_ID

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


class TestTablesBelongToADataset:
    """DATA-47 — metadata tables are per dataset, like every other table.

    They were one slot per grain for the whole session: a new dataset opened
    with the last one's tables, attaching a table to dataset B replaced dataset
    A's, and detaching it anywhere removed it everywhere."""

    @staticmethod
    def _readers(source: str, field: str = "age"):
        return md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p1", "p2"], field: [1, 2]}),
            "participant_id",
            source_name=source,
        )

    def test_switching_datasets_swaps_their_tables(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.activate_dataset(session, "B")
        assert md.SESSION_KEY not in session  # B has none of its own
        session[md.SESSION_KEY] = self._readers("b.csv", "site")
        md.activate_dataset(session, "A")
        assert session[md.SESSION_KEY].source_name == "a.csv"
        assert md.is_restored(session, "participant")
        md.activate_dataset(session, "B")
        assert session[md.SESSION_KEY].source_name == "b.csv"
        assert list(session[md.SESSION_KEY].names) == ["site"]

    def test_a_swap_clears_the_uploader_so_its_file_does_not_reattach(self):
        session = {md.OWNER_KEY: "A", md.SESSION_KEY: self._readers("a.csv")}
        session["participant_metadata_upload"] = object()
        session["participant_metadata_id_column"] = "participant_id"
        session["participant_metadata_keep_fields"] = ["age"]
        session["_participant_metadata_name"] = "a.csv"
        md.activate_dataset(session, "B")
        for key in (
            "participant_metadata_upload",
            "participant_metadata_id_column",
            "participant_metadata_keep_fields",
            "_participant_metadata_name",
        ):
            assert key not in session

    def test_the_first_run_adopts_what_is_attached(self):
        """A session whose tables have no owner yet (its first run) keeps them."""
        session = {md.SESSION_KEY: self._readers("a.csv")}
        md.activate_dataset(session, "A")
        assert session[md.SESSION_KEY].source_name == "a.csv"
        assert session[md.OWNER_KEY] == "A"

    def test_a_new_dataset_starts_empty_and_keeps_what_it_attached(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.begin_pending_dataset(session)
        md.activate_dataset(session, md.PENDING_DATASET)
        assert md.SESSION_KEY not in session
        session[md.SESSION_KEY] = self._readers("new.csv")
        md.adopt_pending_dataset(session, "New")
        assert not md.activate_dataset(session, "New")  # nothing to swap
        assert session[md.SESSION_KEY].source_name == "new.csv"
        md.activate_dataset(session, "A")
        assert session[md.SESSION_KEY].source_name == "a.csv"
        assert md.PENDING_DATASET not in md.dataset_payloads(session)

    def test_a_cancelled_wizard_leaves_nothing_behind(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.begin_pending_dataset(session)
        md.activate_dataset(session, md.PENDING_DATASET)
        session[md.SESSION_KEY] = self._readers("abandoned.csv")
        md.activate_dataset(session, "A")  # ✕ Cancel returns to A
        assert session[md.SESSION_KEY].source_name == "a.csv"
        md.begin_pending_dataset(session)  # the next ➕ Add dataset
        md.activate_dataset(session, md.PENDING_DATASET)
        assert md.SESSION_KEY not in session

    def test_detaching_on_one_dataset_leaves_the_other(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.activate_dataset(session, "B")
        session[md.SESSION_KEY] = self._readers("b.csv")
        session.pop(md.SESSION_KEY)  # detach B's
        md.activate_dataset(session, "A")
        assert session[md.SESSION_KEY].source_name == "a.csv"
        md.activate_dataset(session, "B")
        assert md.SESSION_KEY not in session

    def test_remove_and_rename_follow_the_dataset(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.activate_dataset(session, "B")
        md.rename_dataset(session, "A", "A2")
        md.activate_dataset(session, "A2")
        assert session[md.SESSION_KEY].source_name == "a.csv"
        md.forget_dataset(session, "A2")
        assert md.SESSION_KEY not in session
        assert "A2" not in md.dataset_payloads(session)

    def test_the_cache_payloads_round_trip_per_dataset(self):
        session = {}
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        md.activate_dataset(session, "B")
        session[md.SESSION_KEY] = self._readers("b.csv")
        written = {"datasets": md.dataset_payloads(session)}
        assert set(written["datasets"]) == {"A", "B"}

        restored = {}
        assert md.restore_dataset_payloads(restored, written) == 2
        md.activate_dataset(restored, "B")
        assert restored[md.SESSION_KEY].source_name == "b.csv"
        md.activate_dataset(restored, "A")
        assert restored[md.SESSION_KEY].source_name == "a.csv"

    def test_the_signature_moves_when_a_stored_table_does(self):
        session = {}
        assert md.store_signature(session) == []
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        before = md.store_signature(session)
        md.activate_dataset(session, "B")  # A's table moves into the store
        assert md.store_signature(session) != before
        assert md.store_signature(session)  # still something to write

    def test_compare_b_filters_by_its_own_datasets_table(self, monkeypatch):
        """CMP-8's scanpath B can come from another dataset — its filters must
        then narrow by *that* dataset's table, not the selected one's."""
        import streamlit as st

        session = {}
        md.activate_dataset(session, "B")
        session[md.SESSION_KEY] = self._readers("b.csv", "site")
        md.activate_dataset(session, "A")
        session[md.SESSION_KEY] = self._readers("a.csv")
        monkeypatch.setattr(st, "session_state", session)

        assert md.attached_for("participant").source_name == "a.csv"
        assert md.attached_for("participant", "cmp").source_name == "a.csv"
        session["cmp_dataset"] = "B"
        assert md.attached_for("participant").source_name == "a.csv"
        assert md.attached_for("participant", "cmp").source_name == "b.csv"
        assert md.attached_for("trial", "cmp") is None
        session["cmp_dataset"] = "This dataset"
        assert md.attached_for("participant", "cmp").source_name == "a.csv"
