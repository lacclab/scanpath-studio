"""What an upload box says about a file it cannot use.

An empty file, a header with no rows, an image renamed ``.csv``, text named
``.parquet``, and a ``;`` table with one row that has a field too many — each
is said in plain words, with the reader's own message kept as detail, and no
sentence ends in two periods.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio.data import (
    READ_NOTES_ATTR,
    ReadPlan,
    TableReadError,
    explain_read_error,
    header_only_error,
    pop_read_notes,
    read_table,
    read_table_columns,
    read_tables,
)

HEADER = ["participant", "trial", "x", "y", "duration"]
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x07\x80" + bytes(64)


def _upload(name: str, body: bytes) -> io.BytesIO:
    buf = io.BytesIO(body)
    buf.name = name
    return buf


def _semicolon_table(bad_line: str | None = None, at: int = 8) -> bytes:
    rows = [";".join(HEADER)]
    rows += [f"p1;t{i % 3};{100 + i};{200 + i};{150 + i}" for i in range(12)]
    if bad_line is not None:
        rows.insert(at, bad_line)
    return ("\n".join(rows) + "\n").encode()


def _plan() -> ReadPlan:
    return ReadPlan(columns=("participant", "trial", "x", "y", "duration"))


def _plain(message: str) -> None:
    assert ".." not in message
    assert "Error tokenizing" not in message
    assert "C error" not in message


class TestExplainReadError:
    def test_a_row_with_an_extra_field_names_its_line(self):
        exc = pd.errors.ParserError(
            "Error tokenizing data. C error: Expected 5 fields in line 10, saw 6\n"
        )
        error = explain_read_error("fix.csv", exc)
        assert error.name == "fix.csv"
        assert "line 10 has 6, the header 5" in str(error)
        assert "Expected 5 fields" in error.detail
        _plain(error.sentence("**fix.csv**"))

    def test_other_parser_errors_say_it_is_not_a_text_table(self):
        error = explain_read_error("x.csv", pd.errors.ParserError("EOF inside string"))
        assert "doesn't look like a text table (CSV/TSV)" in str(error)
        assert error.detail == "EOF inside string"

    def test_text_named_parquet(self):
        upload = _upload("text.parquet", b"just some text\nnot parquet\n")
        with pytest.raises(Exception) as raised:
            read_table(upload)
        error = explain_read_error("text.parquet", raised.value)
        assert str(error).startswith(
            "'text.parquet' isn't a Parquet file that can be read."
        )
        assert "magic bytes" in error.detail
        _plain(error.sentence())

    def test_a_bad_zip(self):
        error = explain_read_error(
            "a.zip", zipfile.BadZipFile("File is not a zip file")
        )
        assert "isn't a zip archive that can be opened" in str(error)

    def test_the_packages_own_plain_errors_keep_their_words(self):
        error = explain_read_error("a.zip", ValueError("the zip holds no table file."))
        assert str(error) == "'a.zip' couldn't be read: the zip holds no table file."
        assert error.detail == ""

    def test_an_error_already_explained_is_itself(self):
        error = header_only_error("h.csv")
        assert explain_read_error("other.csv", error) is error

    def test_the_empty_file_message_ends_once(self):
        with pytest.raises(TableReadError) as raised:
            read_table(_upload("empty.csv", b""))
        message = raised.value.sentence("**empty.csv**")
        assert message == (
            "**empty.csv** is empty and has no header row. Check that the export "
            "finished writing, then upload it again."
        )


class TestBinaryRenamedCsv:
    def test_a_png_named_csv_is_refused_as_not_text(self):
        for read in (read_table_columns, read_table):
            with pytest.raises(TableReadError) as raised:
                read(_upload("png_as.csv", PNG))
            assert "png_as.csv" in str(raised.value)
            assert "doesn't look like a text table (CSV/TSV)" in str(raised.value)
            assert "looks like a PNG image" in str(raised.value)
            _plain(str(raised.value))

    def test_a_utf16_export_with_its_byte_order_mark_still_reads(self):
        body = "a\tb\n1\t2\n".encode("utf-16")
        assert b"\x00" in body
        assert read_table(_upload("ia.txt", body))["b"].tolist() == [2]


class TestHeaderOnly:
    def test_reads_as_columns_and_no_rows(self):
        frame = read_table(_upload("h.csv", b"participant;trial;x;y;duration\n"))
        assert frame.empty
        assert list(frame.columns) == HEADER

    def test_the_message(self):
        assert header_only_error("h.csv").sentence("**h.csv**") == (
            "**h.csv** has a header but no rows. Upload a file with data."
        )


class TestRowsWithMoreFieldsThanTheHeader:
    def test_a_planned_read_skips_the_row_and_says_so(self):
        # The extra field sits early, so every value after it is shifted: kept,
        # the row would invent a trial "999".
        body = _semicolon_table("p1;999;t1;105;205;155", at=9)
        frame = read_table(_upload("bad.csv", body), plan=_plan())
        assert len(frame) == 12
        assert "999" not in frame["trial"].astype(str).tolist()
        assert list(frame.columns) == HEADER
        notes = pop_read_notes(frame)
        assert notes == [
            "Skipped 1 row with more fields than the header (line 10). A "
            "delimiter inside a value that isn't quoted does this."
        ]
        assert READ_NOTES_ATTR not in frame.attrs

    def test_numbers_stay_numbers_on_the_kept_rows(self):
        frame = read_table(
            _upload("bad.csv", _semicolon_table("p1;t1;abc;1;2;3")), plan=_plan()
        )
        assert pd.api.types.is_numeric_dtype(frame["x"])

    def test_a_clean_file_has_no_notes_and_no_extra_column(self):
        frame = read_table(_upload("ok.csv", _semicolon_table()), plan=_plan())
        assert len(frame) == 12
        assert list(frame.columns) == HEADER
        assert pop_read_notes(frame) == []

    def test_a_trailing_delimiter_on_every_row_is_not_an_extra_field(self):
        rows = [";".join(HEADER)] + [f"p1;t1;{i};{i};{i};" for i in range(3)]
        body = ("\n".join(rows) + "\n").encode()
        frame = read_table(_upload("trailing.csv", body), plan=_plan())
        assert len(frame) == 3
        assert pop_read_notes(frame) == []

    def test_many_bad_rows_are_counted_and_the_lines_shortened(self):
        rows = [";".join(HEADER)] + ["p1;t1;1;2;3;x"] * 7 + ["p1;t1;1;2;3"]
        body = ("\n".join(rows) + "\n").encode()
        frame = read_table(_upload("bad.csv", body), plan=_plan())
        assert len(frame) == 1
        (note,) = pop_read_notes(frame)
        assert note.startswith("Skipped 7 rows with more fields than the header")
        assert "(lines 2, 3, 4, 5, 6 …)" in note

    def test_blank_lines_at_the_end_do_not_hide_a_long_row(self):
        body = _semicolon_table("p1;t1;1;2;3;4") + b"\n\n\n"
        frame = read_table(_upload("bad.csv", body), plan=_plan())
        assert len(frame) == 12
        assert len(pop_read_notes(frame)) == 1

    def test_a_blank_line_above_does_not_shift_the_line_number(self):
        rows = [";".join(HEADER), "p1;t1;1;2;3", "", "p1;t1;1;2;3;4", "p1;t2;1;2;3"]
        frame = read_table(_upload("bad.csv", "\n".join(rows).encode()), plan=_plan())
        assert frame["trial"].tolist() == ["t1", "t2"]
        assert "(line 4)" in pop_read_notes(frame)[0]

    def test_quoted_values_are_read_as_before(self):
        """A quoted value may hold the delimiter as data, which counting bytes
        cannot tell from a field too many."""
        rows = [";".join(HEADER), 'p1;"t;1";1;2;3', "p1;t2;1;2;3"]
        frame = read_table(_upload("q.csv", "\n".join(rows).encode()), plan=_plan())
        assert frame["trial"].tolist() == ["t;1", "t2"]
        assert pop_read_notes(frame) == []

    def test_several_files_name_the_one_the_note_is_about(self):
        files = [
            _upload("a.csv", _semicolon_table()),
            _upload("b.csv", _semicolon_table("p1;t1;1;2;3;4")),
        ]
        frame = read_tables(files, plan_for=lambda header: _plan())
        (note,) = pop_read_notes(frame)
        assert note.startswith("b.csv: Skipped 1 row")

    def test_several_files_name_the_one_that_failed(self):
        files = [_upload("a.csv", _semicolon_table()), _upload("pic.csv", PNG)]
        with pytest.raises(TableReadError) as raised:
            read_tables(files, plan_for=lambda header: _plan())
        assert raised.value.name == "pic.csv"

    def test_an_unplanned_read_refuses_the_file_and_names_the_line(self):
        with pytest.raises(pd.errors.ParserError) as raised:
            read_table(_upload("bad.csv", _semicolon_table("p1;t1;1;2;3;4")))
        error = explain_read_error("bad.csv", raised.value)
        assert "line 9 has 6, the header 5" in str(error)


class TestTheUploadBoxSaysIt:
    """`app._read_uploaded_frame` over a stand-in uploader (AppTest cannot
    drive `st.file_uploader`)."""

    @staticmethod
    def _run(name: str, body: bytes):
        from streamlit.testing.v1 import AppTest

        def script(name: str, body: bytes):
            import io

            import streamlit as st

            from scanpath_studio import app

            class Upload(io.BytesIO):
                size = len(body)
                file_id = name

            Upload.name = name

            class Host:
                def file_uploader(self, *args, **kwargs):
                    return Upload(body)

                def error(self, text):
                    st.error(text)

                def warning(self, text):
                    st.warning(text)

                def expander(self, label):
                    return st.expander(label)

            frame = app._read_uploaded_frame(
                uploader_label="Fixations",
                upload_help="",
                state_prefix="col_map_fix",
                multi=False,
                container=Host(),
                kind="fixations",
            )
            st.write(f"rows={len(frame)}")

        at = AppTest.from_function(script, args=(name, body)).run(timeout=60)
        assert not at.exception
        return at

    def test_png_as_csv(self):
        at = self._run("png_as.csv", PNG)
        (message,) = [e.value for e in at.error]
        assert message.startswith(
            "**png_as.csv** doesn't look like a text table (CSV/TSV): it looks "
            "like a PNG image."
        )
        assert message.endswith("To remove the file, click the ✕ next to its name.")
        _plain(message)

    def test_text_named_parquet_keeps_the_detail_folded_away(self):
        at = self._run("text.parquet", b"just some text\nnot parquet\n")
        (message,) = [e.value for e in at.error]
        assert message.startswith(
            "**text.parquet** isn't a Parquet file that can be read."
        )
        _plain(message)
        assert [x.label for x in at.expander] == ["Technical detail"]
        assert "magic bytes" in at.expander[0].code[0].value

    def test_header_only(self):
        at = self._run("h.csv", b"participant;trial;x;y;duration\n")
        assert not at.error
        (message,) = [w.value for w in at.warning]
        assert message.startswith("**h.csv** has a header but no rows.")

    def test_a_skipped_row(self):
        at = self._run("bad.csv", _semicolon_table("p1;999;t1;105;205;155", at=9))
        (message,) = [w.value for w in at.warning]
        assert message.startswith("**bad.csv**: Skipped 1 row with more fields")
        assert "rows=12" in at.markdown[-1].value


class TestMetadataSlotsSayItTheSameWay:
    def test_an_unreadable_file(self):
        from scanpath_studio.tabs import _MetadataReadError, _read_metadata_uploads

        with pytest.raises(_MetadataReadError) as raised:
            _read_metadata_uploads([_upload("broken.parquet", b"not parquet")])
        assert str(raised.value).startswith(
            "broken.parquet isn't a Parquet file that can be read."
        )

    def test_a_header_only_file(self):
        from scanpath_studio.tabs import _MetadataReadError, _read_metadata_uploads

        with pytest.raises(_MetadataReadError) as raised:
            _read_metadata_uploads([_upload("p.csv", b"participant_id,age\n")])
        assert str(raised.value) == (
            "p.csv has a header but no rows. Upload a file with data."
        )


class TestAddDatasetSaysWhyItIsOff:
    """Files attached that give no rows leave ✅ Add dataset disabled — with
    the reason above it, not "upload a table to get started"."""

    def test_header_only_uploads(self, monkeypatch):
        from streamlit.testing.v1 import AppTest

        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        header_only = pd.DataFrame(columns=HEADER)
        monkeypatch.setattr(
            app,
            "_read_uploaded_frame",
            lambda **kw: (
                header_only.copy()
                if kw["state_prefix"] == "col_map_fix"
                else pd.DataFrame()
            ),
        )
        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        # Stands in for the uploader's own state: a file is attached.
        at.session_state["col_map_fix_upload"] = ["h.csv"]
        at.run(timeout=120)
        assert not at.exception
        (finalize,) = [b for b in at.button if b.key == "wizard_finalize"]
        assert finalize.disabled
        assert finalize.help.startswith("None of the uploaded tables has any rows")
        assert any(
            "Add dataset** is off: None of the uploaded tables has any rows" in w.value
            for w in at.warning
        )


class TestWizardWording:
    """The labels and the setup guide name the same things the same way."""

    def test_every_recording_setup_line_says_i_know_it(self):
        from scanpath_studio.wizard import (
            _FONT_KNOW,
            _GEOM_KNOW,
            _SCREEN_KNOW,
            _SETUP_CHOICE_LABELS,
            _TEXT_FONT,
        )

        for answer in (_SCREEN_KNOW, _GEOM_KNOW, _TEXT_FONT, _FONT_KNOW):
            assert _SETUP_CHOICE_LABELS[answer] == "I know it"

    def test_the_guide_names_the_fields_as_the_screen_does(self):
        from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

        bodies = " ".join(step["body"] for step in _WIZARD_GUIDE_STEPS)
        assert "**Name**" in bodies
        assert "**Extra fields to keep**" in bodies
        assert "*I know it*" in bodies
        assert "**Skip guide**" in bodies

    def test_the_guide_and_the_start_from_line_say_it_literally(self):
        """Read by people with intermediate English: no idioms."""
        import inspect

        from scanpath_studio import app, wizard
        from scanpath_studio.tour import _WIZARD_GUIDE_STEPS

        bodies = " ".join(step["body"] for step in _WIZARD_GUIDE_STEPS)
        for idiom in ("dive in", "Follow along", "Say how you know", "drawn to"):
            assert idiom not in bodies
        assert wizard._START_SCRATCH == "An empty form"
        reminder = inspect.getsource(app._render_backup_reminder)
        assert "What to back up" not in reminder
        assert "How to keep copies of your work" in reminder

    def test_the_guide_button_is_not_the_skip_field(self):
        """The Words mapping has a field called *Skip* (``IA_SKIP``)."""
        import inspect

        from scanpath_studio import tour
        from scanpath_studio.data import READING_MEASURE_FIELDS

        assert any(label == "Skip" for _k, _c, label, *_ in READING_MEASURE_FIELDS)
        source = inspect.getsource(tour._wizard_guide_buttons)
        assert '"Skip guide"' in source
        assert '"Skip",' not in source

    def test_the_add_screen_titles_the_name_field(self):
        from streamlit.testing.v1 import AppTest

        from scanpath_studio import app
        from tests.conftest import APP_SCRIPT

        at = AppTest.from_file(APP_SCRIPT)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run(timeout=120)
        assert not at.exception
        (name,) = [t for t in at.text_input if t.key == "wizard_dataset_name"]
        assert name.label == "Name"
        assert any(">Name<" in m.value for m in at.markdown)


class TestEditShowsWhereAnEdgesBoxCameFrom:
    def test_a_box_added_from_edges(self):
        from scanpath_studio.column_names import from_schema
        from scanpath_studio.tabs import box_edges_note

        schema = {
            "trial": "TRIAL",
            "word_id": "IA_ID",
            "left": "IA_LEFT",
            "right": "IA_RIGHT",
            "top": "IA_TOP",
            "bottom": "IA_BOTTOM",
        }
        names = from_schema("words", schema, list(schema.values()))
        note = box_edges_note({"column_names": {"words": names.to_payload()}})
        assert note == (
            "Added from each box's edges (IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM). "
            "It is stored, and edited here, as its top-left corner and size: Box "
            "width is IA_RIGHT − IA_LEFT, Box height IA_BOTTOM − IA_TOP."
        )

    def test_a_box_added_as_origin_and_size_says_nothing(self):
        from scanpath_studio.column_names import from_schema
        from scanpath_studio.tabs import box_edges_note

        schema = {
            "trial": "TRIAL",
            "word_id": "IA_ID",
            "x": "X",
            "y": "Y",
            "width": "W",
            "height": "H",
        }
        names = from_schema("words", schema, list(schema.values()))
        assert box_edges_note({"column_names": {"words": names.to_payload()}}) is None
        assert box_edges_note({}) is None
