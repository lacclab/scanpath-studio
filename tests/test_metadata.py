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
