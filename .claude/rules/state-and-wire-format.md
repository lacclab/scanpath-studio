---
paths:
  - "scanpath_studio/app.py"
  - "scanpath_studio/controls.py"
  - "scanpath_studio/url_state.py"
  - "scanpath_studio/session_keys.py"
  - "scanpath_studio/plot_config.py"
  - "scanpath_studio/script_link.py"
  - "scanpath_studio/tabs.py"
  - "scanpath_studio/ui_mode.py"
  - "scanpath_studio/menu.py"
  - "scanpath_studio/fields.py"
  - "scanpath_studio/wizard.py"
  - "scanpath_studio/wizard_shell.py"
  - "scanpath_studio/metadata_editor.py"
  - "scanpath_studio/corpus_overview.py"
  - "scanpath_studio/corpus_navigation.py"
  - "scanpath_studio/publication_ui.py"
  - "scanpath_studio/panel_proof_ui.py"
  - "scanpath_studio/tour.py"
  - "scanpath_studio/reruns.py"
  - "scanpath_studio/viz_history.py"
  - "tests/test_session_key_contract.py"
  - "tests/test_widget_value_sync.py"
  - "tests/test_wire_golden.py"
  - "scanpath_studio/utils.py"
  - "scanpath_studio/export.py"
  - "scanpath_studio/dataset_credit.py"
  - "scanpath_studio/annotations.py"
  - "scanpath_studio/loading.py"
  - "scanpath_studio/styles.py"
---

# State and the wire format

- **Widget keys, URL params and settings keys are a wire format.** Deep-link
  presets are applied before widgets render (`app.py`); renaming one breaks
  links and files already in users' hands (`tests/test_session_key_contract.py`).
  A settings-file shape change bumps `session_keys.PLOT_CONFIG_SCHEMA_VERSION`
  and registers a migration in `url_state._PLOT_CONFIG_MIGRATIONS`.
- **`persist_state="session"` on every persisted widget**, or a control that
  renders only sometimes remounts at its default
  (`tests/test_widget_value_sync.py`).
- **Write a widget key inside a popover with `controls.write_through`** — the
  browser keeps echoing the value it last showed.
- **Never pass `value=` / `index=` to a gated (disabled) widget**; disabling
  must not rewrite what a link or saved file carries.
- **Anything drawn only sometimes above a view goes in a container drawn every
  run.** Streamlit matches elements by position, so one more or fewer above
  `sps_view` redraws the whole view. `st.dialog`, a bare `st.toast` and
  `@st.fragment` are safe; a bare `st.warning`, `st.markdown` or iframe is not.
- **Essentials and Full draw the same widgets.** Essentials is `SIMPLE` /
  `simple_only` in code, Full is `ADVANCED` / `advanced_only`. Mode-only UI
  goes in a `ui_mode.advanced_only(host, name)` (or `simple_only`) container,
  one per item, hidden by `ui_mode.mode_css`; never skip rendering a widget by
  mode. The subtab list is the one structural difference. `?ui=` is read on a
  session's first run; Share never writes it.
- **Never give `st.select_slider` a single option** — the browser throws and
  blanks the tab, invisibly to AppTest.
- **Code changes not showing? Restart the server** (CONTRIBUTING → *If a code
  change doesn't show up*).

The checklist form of these rules — the diff that triggers each, the check, and
the bug behind it — is in [`REVIEW.md`](../../REVIEW.md).
