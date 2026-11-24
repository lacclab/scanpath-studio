"""The ✏️ Edit dataset screen draws like the ➕ Add dataset screen.

The two screens ask the same questions of the same dataset — one before it
exists and one after — so their chrome is the same too: the add screen's sticky
bar and two-button footer, the same `wizard_shell.part` numbered one-line
headlines with hover-only prose (not ``st.divider()`` + ``st.subheader("🔤 …")``
+ ``st.caption(…)`` section headers), the same order (tables & mapping →
metadata → recording setup), and Recording setup as a numbered part of its own
rather than inside the mapping form, as on the add screen.
"""

from __future__ import annotations

import inspect

import pytest

from tests.conftest import (
    APP_SCRIPT,
    find_keyed,
    keys_around,
    keys_in_screen_order,
    open_dataset_editor,
    page_nodes,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


class TestTheStepRegistry:
    def test_the_first_three_parts_mirror_the_add_screens(self):
        """Naming it and editing its tables are the add screen's first
        two questions, and Recording setup is literally the same renderer."""
        from scanpath_studio.wizard_shell import EDITOR_STEPS, STEPS_BY_ID

        ids = [s.id for s in EDITOR_STEPS]
        assert ids[:3] == ["edit_name", "edit_data", "edit_setup"]
        titles = {s.id: s.title for s in EDITOR_STEPS}
        assert titles["edit_name"] == STEPS_BY_ID["name"].title
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
        assert [every[s.id].number for s in EDITOR_STEPS] == [1, 2, 3, 4, 5, 6]

        # Stimulus images need a local filesystem and preprocessing is behind
        # the experimental flag; a screen reading 1 · 2 · 3 · 5 looks like a section that
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
        hover-only, not a caption line under every part."""
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
        from scanpath_studio import app

        at = AppTest.from_file(APP_SCRIPT, default_timeout=150)
        at.session_state["data_source_choice"] = app.UPLOAD_CHOICE
        at.run()
        assert not at.exception, at.exception
        parts = TestThePageItDraws._parts(at)
        assert len(parts) >= 3, parts
        assert not [part for part in parts if "sps-fhelp" in part]

    def test_the_hover_carrier_is_styled_inside_a_part(self):
        """`.sps-fhelp` only gets its dotted-underline cue in the contexts named
        in `styles.py`; a part has to be one of them."""
        from scanpath_studio.styles import get_app_css

        assert ".sps-wiz-part .sps-fhelp" in get_app_css()


class TestThePageItDraws:
    """Drive the real app on the 🗂️ Data view and read what it rendered."""

    @staticmethod
    def _data_page():
        at = AppTest.from_file(APP_SCRIPT, default_timeout=600)
        open_dataset_editor(at)
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
        # Name & description · Tables & mapping · Recording setup ·
        # Stimulus images (the tests allow a local filesystem) · Trial
        # identity — the add screen's four parts first.
        assert len(parts) >= 5
        numbers = [
            body.split('class="sps-wiz-part-n">')[1].split("<")[0] for body in parts
        ]
        assert numbers == [str(i + 1) for i in range(len(parts))]
        assert "Name &amp; description" in parts[0] or "Name & description" in parts[0]
        assert "Recording setup" in parts[2]
        assert "Stimulus images" in parts[3]
        assert "Trial identity" in parts[4]

    def test_the_old_subheaders_are_gone(self):
        """Only the overview screen has `st.subheader` sections; every heading
        on the editor is a part."""
        at = self._data_page()
        headings = {s.value for s in at.subheader}
        assert not any(h.startswith(("🔤 ", "🧾 ", "🖼️ ", "🧹 ")) for h in headings), (
            headings
        )

    def test_recording_setup_is_not_titled_twice(self):
        """It renders into its own part, so it carries no `##### ` heading of its
        own to stack under the part's title."""
        at = self._data_page()
        assert [
            m.value
            for m in at.markdown
            if str(m.value).strip().startswith("##### Recording setup")
        ] == []

    def test_the_recording_setup_body_still_renders(self):
        """The demo editor offers the recording setup controls under its heading."""
        at = self._data_page()
        assert any(w.key.endswith("_setup_screen_mode") for w in at.segmented_control)


class TestTheSlotOrder:
    """Creation order is screen order, so the reservations *are* the layout."""

    def test_metadata_sits_with_the_mapping_ahead_of_recording_setup(self):
        """The add screen's order: every upload and its mapping, the metadata
        tables under the same heading, then Recording setup and Stimulus images
        — and only then the parts that need the finished dataset."""
        at = TestThePageItDraws._data_page()
        keys = keys_in_screen_order(at._tree)
        # Each part's headline, in the slot reserved for it.
        for slot, step in (
            ("tutorial_recording_setup", "edit_setup"),
            ("tutorial_stimulus_images", "edit_stimulus"),
            ("tutorial_trial_identity", "edit_identity"),
            ("tutorial_preprocessing", "edit_preproc"),
        ):
            assert slot in keys_around(at, f"wiz_part_{step}"), step
        order = [
            "wiz_part_edit_data",
            "tutorial_column_mapping",
            "tutorial_participant_metadata",
            "wiz_part_edit_setup",
            "wiz_part_edit_stimulus",
            "wiz_part_edit_identity",
            "wiz_part_edit_preproc",
            "dataset_editor_footer",
        ]
        positions = [keys.index(key) for key in order]
        assert positions == sorted(positions), order


class TestTheRehostedRenderer:
    def test_the_setup_host_is_optional(self):
        """Every other call site wants it inline, heading and all — only the
        editor passes a host."""
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

    @pytest.mark.parametrize("hosted", [False, True])
    def test_a_hosted_provenance_note_drops_its_heading(self, hosted):
        """Inline the note titles itself; in a host — the editor's own
        Recording setup part — it draws its summary there, untitled."""
        at = AppTest.from_function(_provenance_note_app)
        at.session_state["hosted"] = hosted
        at.run()
        assert not at.exception, at.exception
        titles = [m for m in at.markdown if m.value.startswith("##### Recording setup")]
        assert len(titles) == (0 if hosted else 1)
        cells = [
            node
            for node, _ in page_nodes(at._tree)
            if node.type == "markdown" and "sps-readonly-map-cell" in node.value
        ]
        assert len(cells) == 3
        if hosted:
            part, _ = find_keyed(at, "setup_part")
            in_part = {id(node) for node, _ in page_nodes(part)}
            assert all(id(cell) in in_part for cell in cells)


def _provenance_note_app():
    """The recording-setup note for a known setup, inline or in a host."""
    import streamlit as st

    from scanpath_studio.experimental_setup import SetupSnapshot
    from scanpath_studio.tabs import _render_setup_provenance_note

    st.session_state["_wizard_setup_snapshot"] = SetupSnapshot().to_dict()
    if st.session_state.get("hosted"):
        _render_setup_provenance_note(host=st.container(key="setup_part"))
    else:
        _render_setup_provenance_note()


def _no_mapping_app():
    """The editor's mapping section for a source with no mapping to show."""
    import streamlit as st

    from scanpath_studio.tabs import _render_column_mapping_section

    _render_column_mapping_section(setup_host=st.container(key="setup_part"))


class TestNoNumberedPartIsLeftEmpty:
    """A headline standing over nothing reads as a section that failed to
    render — the very thing contiguous numbering exists to prevent. Two of
    `_render_column_mapping_section`'s three modes could produce exactly that
    for **Recording setup**, which is a part of its own."""

    def test_a_source_with_no_recorded_setup_says_so(self, monkeypatch):
        """`active_setup_snapshot()` is None for a source that claims no screen
        (the synthetic trial)."""
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
        """Without a host there is no headline to strand, and the note says
        nothing rather than invent a monitor."""
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
        """Mode C (no mapping) must still fill the setup part, or the part's
        headline is stranded over nothing."""
        at = AppTest.from_function(_no_mapping_app).run()
        assert not at.exception, at.exception
        assert [i.value for i in at.info] == [
            "No column mapping available for the current dataset."
        ]
        part, _ = find_keyed(at, "setup_part")
        said = [str(n.value) for n, _ in page_nodes(part) if n.type == "caption"]
        assert any("doesn't state the screen" in s for s in said), said
