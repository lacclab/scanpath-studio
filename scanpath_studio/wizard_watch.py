"""Guard the add-dataset wizard's unsaved work against a lost page or session.

Two browser-side guards share one tiny bidirectional component, drawn on every
run by :func:`render`:

- **A lost connection.** A server keeps a session in memory only. When the
  browser's connection drops and Streamlit reconnects the *same page* to a
  *new* session — the old one expired, or the server restarted — everything the
  wizard held is gone, and the next run draws the 🗂️ Data page as if nothing had
  happened. While the wizard is open the component records this session in the
  tab's ``sessionStorage``, together with an id of the loaded page. On a run
  with the wizard closed it removes that marker, and when the marker came from
  this same page but another session, it reports ``lost``; :func:`note_lost`
  then arms :data:`LOST_MESSAGE`. A marker from an earlier page — a reload, a
  restored or duplicated tab — is dropped without a word, since no connection
  was lost there.
- **Leaving the page.** While the wizard holds work (an uploaded table, or a
  name or description the user typed), a ``beforeunload`` handler makes the
  browser ask *"Leave site?"* before a reload or close. Every run with the
  wizard closed or empty removes it, so finishing, cancelling or leaving the
  wizard never prompts.

The component draws nothing visible; ``styles.py`` hides its slot.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st

from .constants import ICONS

#: The component's widget key. Its element is hidden by ``styles.py``.
WATCH_KEY = "wizard_watch"

#: Set by :func:`note_lost` when a new session finds the marker the previous
#: one left; shown on the 🗂️ Data page until the wizard opens again or the
#: user goes to another view. Session state only.
UPLOAD_LOST_KEY = "_wizard_upload_lost"

#: This session's id as the component knows it. Session state only — never
#: saved, so a new session always has a new one.
_SESSION_TOKEN_KEY = "_wizard_watch_session"

LOST_MESSAGE = (
    "Connection was interrupted and the upload was lost. Please add the file again."
)

#: The wizard's three table uploaders.
_UPLOAD_KEYS = ("col_map_fix_upload", "col_map_words_upload", "col_map_raw_gaze_upload")

#: The marker's ``sessionStorage`` key.
MARKER_KEY = "sps_wizard_open"

JS = r"""
export default function (component) {
  const { data, setTriggerValue } = component;
  const win = window;
  // One id per loaded page: a reconnect keeps the page, a reload replaces it.
  if (!win.__spsWizardPage) {
    win.__spsWizardPage = Date.now().toString(36) + Math.random().toString(36).slice(2);
  }
  if (!win.__spsWizardLeaveGuard) {
    win.__spsWizardLeaveGuard = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
  }
  // Adding the same listener twice is a no-op, so every run states the guard
  // afresh rather than tracking whether it is on.
  if (data.guard) win.addEventListener("beforeunload", win.__spsWizardLeaveGuard);
  else win.removeEventListener("beforeunload", win.__spsWizardLeaveGuard);

  let store = null;
  try { store = win.sessionStorage; } catch (e) { return; }
  if (!store) return;
  const KEY = "__MARKER_KEY__";
  if (data.open) {
    try {
      store.setItem(KEY, JSON.stringify({ page: win.__spsWizardPage, session: data.session }));
    } catch (e) {}
    return;
  }
  let mark = null;
  try { mark = JSON.parse(store.getItem(KEY) || "null"); } catch (e) {}
  try { store.removeItem(KEY); } catch (e) {}
  if (mark && mark.page === win.__spsWizardPage && mark.session !== data.session) {
    setTriggerValue("lost", true);
  }
}
""".replace("__MARKER_KEY__", MARKER_KEY)


def _component() -> Any:
    """Register once per script run (the v2 registry is run-scoped in AppTest)."""
    return st.components.v2.component("scanpath_wizard_watch", html="", js=JS)


def wizard_open() -> bool:
    """Whether the add-dataset wizard owns the page this run."""
    return bool(st.session_state.get("_show_upload_wizard"))


def wizard_holds_work() -> bool:
    """Whether closing the page now would lose something the user did in the
    wizard: an uploaded table, or a name or description they typed."""
    ss = st.session_state
    if not wizard_open():
        return False
    if any(ss.get(key) for key in _UPLOAD_KEYS):
        return True
    if str(ss.get("wizard_dataset_description") or "").strip():
        return True
    from .wizard import _default_dataset_name

    name = str(ss.get("wizard_dataset_name") or "").strip()
    return bool(name) and name != _default_dataset_name()


def note_lost() -> None:
    """``on_lost_change``: the component found the previous session's marker."""
    if not wizard_open():
        st.session_state[UPLOAD_LOST_KEY] = True


def clear_lost() -> None:
    """Retire :data:`LOST_MESSAGE` (the wizard opened again)."""
    st.session_state.pop(UPLOAD_LOST_KEY, None)


def render(host) -> None:
    """Draw the watcher into ``host``. Call on every run, before anything that
    may stop the run, so the browser always hears the wizard's current state."""
    session = st.session_state.setdefault(_SESSION_TOKEN_KEY, uuid.uuid4().hex)
    with host:
        _component()(
            key=WATCH_KEY,
            data={
                "open": wizard_open(),
                "guard": wizard_holds_work(),
                "session": session,
            },
            on_lost_change=note_lost,
        )


def render_lost_notice(host, *, on_data_view: bool) -> bool:
    """Show :data:`LOST_MESSAGE` in ``host`` while it is armed.

    It belongs to the 🗂️ Data page the lost session left the user on: moving to
    another view, or opening the wizard again, retires it. Returns whether it
    was drawn.
    """
    if not st.session_state.get(UPLOAD_LOST_KEY):
        return False
    if wizard_open() or not on_data_view:
        clear_lost()
        return False
    host.warning(LOST_MESSAGE, icon=ICONS["warning"])
    return True
