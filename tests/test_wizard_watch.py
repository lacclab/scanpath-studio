"""The add-dataset wizard's guards: the lost-connection notice and the
browser's leave prompt.

The browser half (``wizard_watch.JS``) runs under node against a stand-in
``window``; the server half runs through AppTest.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import wizard_watch
from scanpath_studio.constants import _VIEW_DATA, _VIEW_SCANPATH

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="needs node to run the script")
APP_SCRIPT = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")
SYNTHETIC_SOURCE = "Synthetic test trial"

# Each step calls the component as one run would, with ``fresh_page`` standing
# for a page load (a new `window`, the same tab's `sessionStorage`).
HARNESS = r"""
const steps = __STEPS__;
const storage = new Map();
const sessionStorage = {
  getItem: (k) => (storage.has(k) ? storage.get(k) : null),
  setItem: (k, v) => storage.set(k, String(v)),
  removeItem: (k) => storage.delete(k),
};
const makeWindow = () => {
  const listeners = new Set();
  return {
    sessionStorage,
    listeners,
    addEventListener: (type, fn) => type === "beforeunload" && listeners.add(fn),
    removeEventListener: (type, fn) => type === "beforeunload" && listeners.delete(fn),
  };
};
globalThis.window = makeWindow();
const watch = eval("(" + __SCRIPT__.replace("export default function", "function") + ")");
const out = [];
for (const step of steps) {
  if (step.fresh_page) globalThis.window = makeWindow();
  const triggers = [];
  watch({ data: step.data, setTriggerValue: (k, v) => triggers.push([k, v]) });
  out.push({
    triggers,
    marker: sessionStorage.getItem(__KEY__),
    guarded: globalThis.window.listeners.size,
  });
}
console.log(JSON.stringify(out));
"""


def _run(tmp_path: Path, steps: list[dict]) -> list[dict]:
    script = (
        HARNESS.replace("__STEPS__", json.dumps(steps))
        .replace("__SCRIPT__", json.dumps(wizard_watch.JS))
        .replace("__KEY__", json.dumps(wizard_watch.MARKER_KEY))
    )
    path = tmp_path / "harness.js"
    path.write_text(script)
    out = subprocess.run(
        [NODE, str(path)], capture_output=True, text=True, timeout=60, check=True
    )
    return json.loads(out.stdout)


def _step(open_: bool, session: str, *, guard: bool = False, fresh_page=False):
    return {
        "data": {"open": open_, "guard": guard, "session": session},
        "fresh_page": fresh_page,
    }


@needs_node
def test_a_new_session_on_the_same_page_reports_the_lost_upload(tmp_path):
    out = _run(tmp_path, [_step(True, "a", guard=True), _step(False, "b")])
    assert json.loads(out[0]["marker"])["session"] == "a"
    assert out[1]["triggers"] == [["lost", True]]
    assert out[1]["marker"] is None  # cleared: the notice is shown once


@needs_node
def test_closing_the_wizard_normally_clears_the_marker_silently(tmp_path):
    # Add dataset, Cancel and Discard and leave all end in a run of the same
    # session with the wizard closed.
    out = _run(tmp_path, [_step(True, "a"), _step(False, "a"), _step(False, "b")])
    assert out[1]["triggers"] == [] and out[1]["marker"] is None
    assert out[2]["triggers"] == []


@needs_node
def test_a_reload_is_not_a_lost_connection(tmp_path):
    out = _run(tmp_path, [_step(True, "a"), _step(False, "b", fresh_page=True)])
    assert out[1]["triggers"] == []
    assert out[1]["marker"] is None


@needs_node
def test_no_marker_means_nothing_to_report(tmp_path):
    out = _run(tmp_path, [_step(False, "a"), _step(False, "b")])
    assert all(o["triggers"] == [] and o["marker"] is None for o in out)


@needs_node
def test_the_leave_prompt_follows_the_wizards_work(tmp_path):
    out = _run(
        tmp_path,
        [
            _step(True, "a"),  # open, nothing in it yet
            _step(True, "a", guard=True),  # a file uploaded
            _step(True, "a", guard=True),  # stated again: still one handler
            _step(False, "a"),  # added / cancelled / left
            _step(False, "b"),  # a new session never re-arms it
        ],
    )
    assert [o["guarded"] for o in out] == [0, 1, 1, 0, 0]


def _session(monkeypatch, **state) -> dict:
    ss = {"_show_upload_wizard": True, "wizard_dataset_name": "Dataset 1", **state}
    monkeypatch.setattr(wizard_watch.st, "session_state", ss)
    return ss


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({}, False),
        ({"col_map_fix_upload": object()}, True),
        ({"col_map_raw_gaze_upload": [object()]}, True),
        ({"wizard_dataset_name": "My study"}, True),
        ({"wizard_dataset_description": "  "}, False),
        ({"wizard_dataset_description": "Twelve readers"}, True),
        ({"_show_upload_wizard": False, "col_map_fix_upload": object()}, False),
    ],
)
def test_wizard_holds_work(monkeypatch, state, expected):
    _session(monkeypatch, **state)
    assert wizard_watch.wizard_holds_work() is expected


def test_the_lost_report_is_ignored_while_the_wizard_is_open(monkeypatch):
    ss = _session(monkeypatch)
    wizard_watch.note_lost()
    assert wizard_watch.UPLOAD_LOST_KEY not in ss
    ss["_show_upload_wizard"] = False
    wizard_watch.note_lost()
    assert ss[wizard_watch.UPLOAD_LOST_KEY] is True


def _warnings(at: AppTest) -> list[str]:
    return [w.value for w in at.warning]


def _data_page_app() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = SYNTHETIC_SOURCE
    at.session_state["main_nav"] = _VIEW_DATA
    at.session_state["tour_seen"] = True
    return at


def test_the_notice_stays_on_the_data_page_until_the_user_moves_on():
    at = _data_page_app()
    at.run(timeout=60)
    assert wizard_watch.LOST_MESSAGE not in _warnings(at)
    token = at.session_state["_wizard_watch_session"]

    at.session_state[wizard_watch.UPLOAD_LOST_KEY] = True
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert _warnings(at).count(wizard_watch.LOST_MESSAGE) == 1
    at.run(timeout=60)
    assert _warnings(at).count(wizard_watch.LOST_MESSAGE) == 1
    # One session, one token: a rerun is never mistaken for a new session.
    assert at.session_state["_wizard_watch_session"] == token

    at.session_state["main_nav"] = _VIEW_SCANPATH
    at.run(timeout=60)
    assert wizard_watch.LOST_MESSAGE not in _warnings(at)
    assert wizard_watch.UPLOAD_LOST_KEY not in at.session_state


def test_opening_the_wizard_again_retires_the_notice():
    at = _data_page_app()
    at.session_state[wizard_watch.UPLOAD_LOST_KEY] = True
    at.session_state["_show_upload_wizard"] = True
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert wizard_watch.LOST_MESSAGE not in _warnings(at)
    assert wizard_watch.UPLOAD_LOST_KEY not in at.session_state
