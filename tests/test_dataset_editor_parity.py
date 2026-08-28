"""UX-135: the ✏️ Edit dataset screen draws like the ➕ Add dataset screen.

DATA-35 split the 🗂️ Data page into an overview and an editor, and gave the
editor the add screen's sticky bar and its two-button footer. What it kept was a
stack of ``st.divider()`` + ``st.subheader("🔤 …")`` + ``st.caption(…)`` section
headers grown one at a time, against an add screen whose parts are numbered
one-line headlines with hover-only prose. The two screens ask the same questions
of the same dataset — one before it exists and one after — so this round made the
chrome the same too: the same `wizard_shell.part` headline, the same order
(tables & mapping → metadata → recording setup), and Recording setup lifted out
of the mapping form into a numbered part, as it already is on the add screen.
"""

from __future__ import annotations

import inspect

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


class TestTheStepRegistry:
    def test_the_first_two_parts_mirror_the_add_screens(self):
        """Editing a dataset's tables is the same question as uploading them,
        and Recording setup is literally the same renderer."""
        from scanpath_studio.wizard_shell import EDITOR_STEPS, STEPS_BY_ID

        ids = [s.id for s in EDITOR_STEPS]
        assert ids[:2] == ["edit_data", "edit_setup"]
        titles = {s.id: s.title for s in EDITOR_STEPS}
        assert titles["edit_setup"] == STEPS_BY_ID["setup"].title

    def test_editor_ids_cannot_collide_with_the_wizards(self):
        """`part_key` makes them container keys, a key may be used once per run,
        and the editor screen is built on every run — including while the add
        wizard is open."""
        from scanpath_studio.wizard_shell import EDITOR_STEPS, STEPS, part_key

        wizard = {part_key(s.id) for s in STEPS}
        editor = {part_key(s.id) for s in EDITOR_STEPS}
        assert not wizard & editor

    def test_numbering_closes_over_the_parts_that_render(self):
        from scanpath_studio.wizard_shell import EDITOR_STEPS, numbered

        every = numbered(EDITOR_STEPS, {s.id for s in EDITOR_STEPS})
        assert [every[s.id].number for s in EDITOR_STEPS] == [1, 2, 3, 4, 5]

        # Stimulus images need a local filesystem and preprocessing is behind
        # PRE-22's flag; a screen reading 1 · 2 · 3 · 5 looks like a section that
        # failed to render rather than one that does not apply here.
        some = numbered(EDITOR_STEPS, {"edit_data", "edit_setup", "edit_identity"})
        assert [step.number for step in some.values()] == [1, 2, 3]
        assert "edit_stimulus" not in some

    def test_numbering_keeps_page_order_whatever_the_caller_asks_for(self):
        from scanpath_studio.wizard_shell import EDITOR_STEPS, numbered

        out = numbered(EDITOR_STEPS, {"edit_preproc", "edit_data"})
        assert list(out) == ["edit_data", "edit_preproc"]
        assert [s.number for s in out.values()] == [1, 2]


class TestThePartHeadline:
    def test_a_note_becomes_the_wizards_own_hover_tooltip(self):
        """Not an `st.caption` under the title — the add screen's prose is
        hover-only, and a caption line under every part is what this replaces."""
        import streamlit as st

        from scanpath_studio.wizard_shell import EDITOR_STEPS_BY_ID, part

        st.session_state.clear()
        step = EDITOR_STEPS_BY_ID["edit_identity"]
        rendered: list[str] = []

        class _Host:
            def container(self, key=None):
                return self

            def markdown(self, body, **kwargs):
                rendered.append(str(body))

        part(_Host(), step, note=step.caption)
        html = " ".join(rendered)
        assert 'class="sps-fhelp"' in html
        assert "data-tip=" in html
        assert "sps-wiz-part-n" in html

    def test_the_add_screens_own_parts_stay_plain(self):
        """`note` is opt-in: "Dataset name" needs no explanation, and a dotted
        underline under a self-evident title is noise."""
        source = " ".join(inspect.getsource(_render_data_setup_source()).split())
        assert "note=" not in source

    def test_the_hover_carrier_is_styled_inside_a_part(self):
        """`.sps-fhelp` only gets its dotted-underline cue in the contexts named
        in `styles.py`; a part was not one of them."""
        from scanpath_studio.styles import get_app_css

        assert ".sps-wiz-part .sps-fhelp" in get_app_css()


def _render_data_setup_source():
    from scanpath_studio.wizard import _render_data_setup

    return _render_data_setup


class TestThePageItDraws:
    """Drive the real app on the 🗂️ Data view and read what it rendered."""

    @staticmethod
    def _data_page():
        from scanpath_studio.constants import _VIEW_DATA

        at = AppTest.from_file(APP_SCRIPT, default_timeout=600)
        at.session_state["main_nav"] = _VIEW_DATA
        at.run()
        assert not at.exception, at.exception
        assert [e.value for e in at.error] == []
        return at

    @staticmethod
    def _parts(at):
        out = []
        for md in at.markdown:
            body = str(md.value)
            if body.startswith('<div class="sps-wiz-part"'):
                out.append(body)
        return out

    def test_the_editor_sections_render_as_numbered_parts(self):
        at = self._data_page()
        parts = self._parts(at)
        # Tables & mapping · Recording setup · Trial identity, plus Stimulus
        # images wherever a local filesystem is allowed.
        assert len(parts) >= 3
        numbers = [
            body.split('class="sps-wiz-part-n">')[1].split("<")[0] for body in parts
        ]
        assert numbers == [str(i + 1) for i in range(len(parts))]
        assert "Recording setup" in parts[1]
        assert "Trial identity" in parts[2]

    def test_the_old_subheaders_are_gone(self):
        """Only the overview screen keeps `st.subheader` sections; every heading
        the editor owned is a part now."""
        at = self._data_page()
        headings = {s.value for s in at.subheader}
        assert not any(h.startswith(("🔤 ", "🧾 ", "🖼️ ", "🧹 ")) for h in headings), (
            headings
        )

    def test_recording_setup_is_not_titled_twice(self):
        """It renders into its own part, so the `##### ` heading it used to carry
        inside the mapping form has to go — not stack under the part's title."""
        at = self._data_page()
        assert [
            m.value
            for m in at.markdown
            if str(m.value).strip().startswith("##### Recording setup")
        ] == []

    def test_the_recording_setup_body_still_renders(self):
        """Re-hosting it must not drop it: the provenance summary is the read-only
        mode's whole content."""
        at = self._data_page()
        cells = [
            m.value for m in at.markdown if "sps-readonly-map-label" in str(m.value)
        ]
        assert len(cells) >= 3


class TestTheSlotOrder:
    """Creation order is screen order, so the reservations *are* the layout."""

    @staticmethod
    def _positions(*names):
        from scanpath_studio import app

        source = inspect.getsource(app.main)
        found = {}
        for name in names:
            marker = f"{name} = editor_page.container("
            assert marker in source, name
            found[name] = source.index(marker)
        return found

    def test_metadata_sits_with_the_mapping_ahead_of_recording_setup(self):
        """The add screen's order: every upload and its mapping, the metadata
        tables under the same heading, then Recording setup."""
        pos = self._positions(
            "editor_part_data_slot",
            "setup_metadata_slot",
            "setup_recording_slot",
            "setup_identity_slot",
            "setup_stimulus_slot",
            "setup_preproc_slot",
            "editor_footer_slot",
        )
        assert (
            pos["editor_part_data_slot"]
            < pos["setup_metadata_slot"]
            < pos["setup_recording_slot"]
            < pos["setup_identity_slot"]
            < pos["setup_stimulus_slot"]
            < pos["setup_preproc_slot"]
            < pos["editor_footer_slot"]
        )


class TestTheRehostedRenderer:
    def test_the_setup_host_is_optional(self):
        """The collapsed / legacy call sites still want it inline, heading and
        all — only the editor passes a host."""
        from scanpath_studio.tabs import (
            _render_column_mapping_section,
            _render_remap_editor,
            _render_setup_provenance_note,
        )

        for func in (
            _render_column_mapping_section,
            _render_remap_editor,
            _render_setup_provenance_note,
        ):
            params = inspect.signature(func).parameters
            name = "setup_host" if "setup_host" in params else "host"
            assert params[name].default is None, func.__name__

    def test_a_hosted_provenance_note_drops_its_heading(self):
        source = " ".join(
            inspect.getsource(_render_setup_provenance_note_source()).split()
        )
        assert "box = st if host is None else host" in source
        assert 'if host is None: box.markdown("##### Recording setup")' in source


def _render_setup_provenance_note_source():
    from scanpath_studio.tabs import _render_setup_provenance_note

    return _render_setup_provenance_note


class TestNoNumberedPartIsLeftEmpty:
    """A headline standing over nothing reads as a section that failed to
    render — the very thing contiguous numbering exists to prevent. Two of
    `_render_column_mapping_section`'s three modes could produce exactly that
    for **Recording setup**, which UX-135 promoted to a part of its own."""

    def test_a_source_with_no_recorded_setup_says_so(self, monkeypatch):
        """`active_setup_snapshot()` is None for a source that claims no screen
        (the synthetic trial; a benchmark corpus whose manifest invents one)."""
        from scanpath_studio import tabs

        monkeypatch.setattr(tabs, "active_setup_snapshot", lambda: None, raising=False)
        monkeypatch.setattr(
            "scanpath_studio.app.active_setup_snapshot", lambda *a, **k: None
        )
        captions: list[str] = []

        class _Host:
            def caption(self, body, **kwargs):
                captions.append(str(body))

        tabs._render_setup_provenance_note(host=_Host())
        assert captions, "the part was left empty"
        assert "doesn't state the screen" in captions[0]

    def test_inline_it_stays_silent(self, monkeypatch):
        """Without a host there is no headline to strand, and the note has
        always said nothing rather than invent a monitor."""
        from scanpath_studio import tabs

        monkeypatch.setattr(
            "scanpath_studio.app.active_setup_snapshot", lambda *a, **k: None
        )
        written: list[str] = []
        monkeypatch.setattr(
            tabs.st, "caption", lambda body, **kw: written.append(str(body))
        )
        monkeypatch.setattr(
            tabs.st, "markdown", lambda body, **kw: written.append(str(body))
        )

        tabs._render_setup_provenance_note()
        assert written == []

    def test_no_mapping_available_does_not_skip_the_setup_part(self):
        """Mode C used to `return` on that branch, stranding the part below it."""
        source = " ".join(
            inspect.getsource(_render_column_mapping_section_source()).split()
        )
        head, _, tail = source.partition(
            'st.info("No column mapping available for the current data source.")'
        )
        assert tail, "the no-mapping branch moved — re-check this assertion"
        assert "_render_setup_provenance_note(host=setup_host)" in tail


def _render_column_mapping_section_source():
    from scanpath_studio.tabs import _render_column_mapping_section

    return _render_column_mapping_section
