"""In the desktop app's window, a download opens a Save-as dialog.

The hook runs under node against a stand-in page: a ``display-mode`` the test
picks, a fake ``showSaveFilePicker`` and ``fetch``, and an ``<a>`` whose own
``click`` records that the browser's download ran.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scanpath_studio import save_dialog

NODE = shutil.which("node")

HARNESS = r"""
const scenario = __SCENARIO__;
const log = { native: 0, picked: [], written: 0, toasts: [] };
class Anchor {
  constructor() { this.attrs = {}; this.href = ""; }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }
  click() { log.native += 1; }
}
globalThis.HTMLAnchorElement = Anchor;
globalThis.setTimeout = () => 0;
globalThis.document = {
  createElement: () => ({ style: {}, setAttribute() {}, remove() {} }),
  body: { appendChild: (el) => log.toasts.push(el.textContent) },
};
globalThis.window = {
  location: { href: "http://127.0.0.1:8501/", origin: "http://127.0.0.1:8501" },
  matchMedia: (q) => ({ matches: q.includes(scenario.mode) }),
  showSaveFilePicker: async ({ suggestedName }) => {
    log.picked.push(suggestedName);
    if (scenario.picker) throw Object.assign(new Error("x"), { name: scenario.picker });
    return {
      name: suggestedName,
      createWritable: async () => new WritableStream({ write: (c) => { log.written += c.length; } }),
    };
  },
};
globalThis.fetch = async (url, opts) => {
  if (opts && opts.method === "HEAD") {
    return { headers: { get: () => 'attachment; filename="clip.gif"' } };
  }
  return { ok: true, body: new Blob([new Uint8Array(scenario.bytes)]).stream() };
};
// The hook's own source, from save_dialog._PARENT_JS — run as the page would.
eval(__SCRIPT__);
(async () => {
  const a = new Anchor();
  a.href = scenario.href;
  if (scenario.download !== null) a.setAttribute("download", scenario.download);
  a.click();
  for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));
  console.log(JSON.stringify(log));
})();
"""


def _run(tmp_path: Path, **scenario) -> dict:
    scenario = {
        "mode": "standalone",
        "picker": None,
        "href": "/media/abc.gif",
        "download": "",
        "bytes": 1000,
        **scenario,
    }
    script = HARNESS.replace("__SCENARIO__", json.dumps(scenario)).replace(
        "__SCRIPT__", json.dumps(save_dialog._PARENT_JS)
    )
    path = tmp_path / "harness.js"
    path.write_text(script)
    out = subprocess.run(
        [NODE, str(path)], capture_output=True, text=True, timeout=60, check=True
    )
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(NODE is None, reason="needs node to run the hook")


@needs_node
def test_the_app_window_saves_through_the_dialog(tmp_path):
    log = _run(tmp_path)
    assert log["picked"] == ["clip.gif"]  # named by the server's Content-Disposition
    assert log["written"] == 1000
    assert log["native"] == 0
    assert log["toasts"] == ["Saved clip.gif"]


@needs_node
def test_a_named_link_keeps_its_name(tmp_path):
    log = _run(tmp_path, href="blob:http://127.0.0.1:8501/x", download="fig.png")
    assert log["picked"] == ["fig.png"]
    assert log["native"] == 0


@needs_node
def test_an_ordinary_tab_downloads_as_before(tmp_path):
    log = _run(tmp_path, mode="browser")
    assert log["picked"] == []
    assert log["native"] == 1


@needs_node
def test_a_cancelled_dialog_saves_nothing(tmp_path):
    log = _run(tmp_path, picker="AbortError")
    assert log["native"] == 0
    assert log["written"] == 0


@needs_node
def test_a_dialog_that_cannot_open_falls_back_to_the_download(tmp_path):
    log = _run(tmp_path, picker="SecurityError")
    assert log["native"] == 1


@needs_node
def test_a_link_that_is_no_download_is_left_alone(tmp_path):
    log = _run(tmp_path, download=None, href="/somewhere")
    assert log["picked"] == []
    assert log["native"] == 1


def test_the_app_installs_the_hook():
    source = (Path(save_dialog.__file__).parent / "app.py").read_text()
    assert "render_save_dialog()" in source
    assert save_dialog.SCRIPT_ID in save_dialog.save_dialog_script()
