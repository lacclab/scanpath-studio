"""Regression tests for the security-audit fixes tracked as DATA-16.

Each class pins one finding from ``docs/security.md`` so the fix can't quietly
regress:

* **S3** — a share link carries the selected participant and trial; lower-level
  callers can still omit either identifier when constructing a URL directly.
* **S7** — stimulus text reaches ``unsafe_allow_html=True`` HTML-escaped.
* **S10** — the debug-log handler is installed once per *process*, not once per
  session, so handlers can't accumulate on the process-wide root logger.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

import pandas as pd
import pytest

from scanpath_studio import debug_log as debug_log_module
from scanpath_studio import tabs as tabs_module
from scanpath_studio import url_state as url_state_module
from scanpath_studio.constants import DEMO_CHOICE
from scanpath_studio.url_state import (
    _build_share_query,
    _restore_selection,
)


class _FakeSt:
    """Minimal ``streamlit`` stand-in: the share helpers only touch dict-likes."""

    def __init__(self) -> None:
        self.session_state: dict = {}
        self.query_params: dict = {}

    def warning(self, *args, **kwargs) -> None:  # pragma: no cover - no-op
        pass


@pytest.fixture
def fake_st(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(url_state_module, "st", fake)
    return fake


def _combos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "trial_id": ["t1", "t3"],
        }
    )


class TestShareLinkIdentity:
    """S3 — the UI's canonical link identifies its selected trial."""

    def test_default_still_carries_both_ids(self, fake_st):
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p2", "trial_id": "t3"},
        }
        query, _ = _build_share_query(DEMO_CHOICE)
        parsed = parse_qs(query)
        assert parsed["participant"] == ["p2"]
        assert parsed["trial_id"] == ["t3"]

    def test_participant_omitted_but_trial_kept(self, fake_st):
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p2", "trial_id": "t3"},
            "global_show_words": True,
        }
        query, _ = _build_share_query(DEMO_CHOICE, include_participant=False)
        parsed = parse_qs(query)
        assert "participant" not in parsed
        assert "p2" not in query  # the id is nowhere in the URL, under any key
        assert parsed["trial_id"] == ["t3"]
        # View settings are unaffected by the identity choice.
        assert parsed["show_words"] == ["1"]

    def test_link_without_participant_still_restores_the_trial(self, fake_st):
        """The trial-id-alone fallback in ``_restore_selection`` carries it."""
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p2", "trial_id": "t3"},
        }
        query, _ = _build_share_query(DEMO_CHOICE, include_participant=False)
        parsed = parse_qs(query)

        # A recipient's session: only what the link carried is known.
        fake_st.session_state = {}
        selection = {
            "participant_id": parsed.get("participant", [None])[0],
            "trial_id": parsed["trial_id"][0],
        }
        assert _restore_selection(selection, _combos()) is True
        assert fake_st.session_state["single_trial_id"] == "t3"
        assert fake_st.session_state["single_select_trial_mode"] == "Trial"

    def test_settings_only_drops_both_ids(self, fake_st):
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p2", "trial_id": "t3"},
            "global_show_words": True,
        }
        query, _ = _build_share_query(
            DEMO_CHOICE, include_participant=False, include_trial=False
        )
        parsed = parse_qs(query)
        assert "participant" not in parsed
        assert "trial_id" not in parsed
        assert parsed["source"] == ["demo"]
        assert parsed["show_words"] == ["1"]


class TestStimulusTextIsEscaped:
    """S7 — corpus text interpolated into raw HTML is escaped first."""

    def test_span_text_is_escaped(self):
        html_out = tabs_module._span_summary_html(
            "critical_span",
            '<script>alert("xss")</script>',
            "#ffd6e7",
            "",
        )
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out
        # quote=True (html.escape's default) — quotes are escaped too, so the
        # value stays inert even if it ever moves into an attribute.
        assert "&quot;xss&quot;" in html_out

    def test_column_name_is_escaped(self):
        html_out = tabs_module._span_summary_html(
            "<img src=x onerror=alert(1)>",
            "the answer span",
            "#ffd6e7",
            "",
        )
        assert "<img" not in html_out
        assert "&lt;img" in html_out

    def test_ordinary_text_renders_unchanged(self):
        html_out = tabs_module._span_summary_html(
            "critical_span", "the quick brown fox", "#ffd6e7", ""
        )
        assert "the quick brown fox" in html_out
        # The palette colour and the tool-generated note stay raw markup.
        assert "background-color:#ffd6e7" in html_out

    def test_note_is_left_raw(self):
        note = ' <span style="color:#dc3545;">— not fixated</span>'
        html_out = tabs_module._span_summary_html("span", "text", "#ffd6e7", note)
        assert note in html_out


class TestDataInspectionDownloadHelperIsGone:
    """S11 — the unreachable download helper (and its latent leak) is deleted."""

    def test_helpers_are_removed(self):
        for name in (
            "_render_download_buttons",
            "_frame_to_csv_bytes",
            "_frame_to_parquet_bytes",
        ):
            assert not hasattr(tabs_module, name), f"{name} is dead code — remove it"

    def test_the_raw_table_renderer_has_no_download_name_param(self):
        import inspect

        params = inspect.signature(tabs_module._render_raw_table).parameters
        assert "download_name" not in params


class TestLogCaptureIsProcessGlobal:
    """S10 — installing twice must not stack handlers on the root logger."""

    @pytest.fixture(autouse=True)
    def _clean_root_logger(self):
        root = logging.getLogger()
        before = list(root.handlers)
        level_before = root.level
        for h in list(root.handlers):
            if isinstance(h, debug_log_module._SessionStateHandler):
                root.removeHandler(h)
        yield
        for h in list(root.handlers):
            if h not in before:
                root.removeHandler(h)
        for h in before:
            if h not in root.handlers:
                root.addHandler(h)
        root.setLevel(level_before)

    def _capture_handlers(self):
        return [
            h
            for h in logging.getLogger().handlers
            if isinstance(h, debug_log_module._SessionStateHandler)
        ]

    def test_second_install_is_a_no_op(self):
        debug_log_module.install_log_capture()
        debug_log_module.install_log_capture()
        assert len(self._capture_handlers()) == 1

    def test_many_sessions_still_add_one_handler(self):
        # Each simulated session used to add its own handler because the guard
        # lived in (per-session) session state while the logger is per-process.
        for _ in range(5):
            debug_log_module.install_log_capture()
        assert len(self._capture_handlers()) == 1

    def test_guard_does_not_read_session_state(self):
        """The flag must not live in session state — that is the whole bug.

        Checked on the compiled code (not the source) so the finding can still
        be *described* in the docstring.
        """
        names = debug_log_module.install_log_capture.__code__.co_names
        assert "session_state" not in names
