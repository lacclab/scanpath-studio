"""Same-origin HTML iframe helper shared by plots, tours, and Share.

Also serves the installed plotly package's own ``plotly.min.js`` from this app's
Streamlit server (ENG-64), so the in-app figures draw without a request to
``cdn.plot.ly`` — offline, in the desktop app, and on the hosted demo alike.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import streamlit as st
from plotly.offline import get_plotlyjs_version
from streamlit.components.v1 import declare_component

PLOTLYJS_FILENAME = "plotly.min.js"


def embed_html_iframe(html: str, *, height: int) -> None:
    """Render script-bearing HTML in an iframe without the deprecated API.

    ``st.iframe`` replaced the old components embed in Streamlit 1.58. Keeping
    this in one module prevents the plot, guided-tour, and Share surfaces from
    drifting onto different embed APIs.  The compatibility import is deliberately
    lazy so current Streamlit runs never import or call the deprecated function.
    """
    # Tiny script-only embeds need an explicit body. Streamlit's srcdoc
    # autosizing observer otherwise races the parser and tries to observe a null
    # body, producing a browser MutationObserver error even with a fixed height.
    # Full Plotly documents already supply their own body.
    source = html
    if "<body" not in html.lower():
        source = f"<!doctype html><html><body>{html}</body></html>"
    st.iframe(source, height=max(1, int(height)), tab_index=-1)


def plotlyjs_dir() -> Path:
    """The installed plotly package's ``package_data`` folder.

    It holds the ``plotly.min.js`` that plotly.py itself inlines for
    ``include_plotlyjs=True`` — the build its figure JSON is written for. On the
    frozen desktop bundle it is under the unpacked ``plotly/`` package, which the
    spec collects with ``collect_data_files("plotly")``.
    """
    return Path(str(resources.files("plotly") / "package_data"))


def plotlyjs_src() -> str:
    """URL of the bundled ``plotly.min.js`` on this app's own server.

    Pass it as ``fig.to_html(include_plotlyjs=plotlyjs_src())``. Streamlit serves
    a registered custom-component directory at ``component/<name>/<file>``
    (``declare_component(path=…)``), so the installed plotly package's own folder
    is registered as one — nothing is copied, and the file is always the one
    matching the installed plotly.py. Registration needs a script run and is
    idempotent, so it happens on every call rather than once at import.

    The URL is **relative on purpose**. The figure is a ``srcdoc`` iframe, which
    resolves URLs against the Streamlit page's own address — the same contract
    Streamlit's ``index.html`` relies on for its ``./static/…`` bundle. A
    root-relative ``/component/…`` would miss both ``server.baseUrlPath`` and a
    proxy prefix such as Community Cloud's ``/~/+/``.

    The plotly.js version is part of the component name, so an upgrade changes
    the URL rather than being served under a cached old one — and the URL keeps
    ending in ``.js``, which is what ``to_html`` needs to treat it as a script
    address.
    """
    component = declare_component(
        f"plotlyjs-{get_plotlyjs_version()}", path=plotlyjs_dir()
    )
    return f"component/{component.name}/{PLOTLYJS_FILENAME}"


# Streamlit's component route answers `Cache-Control: public` with no max-age and
# no validator, so a browser stores the 4.8 MB script but never reuses it: every
# re-drawn figure (a new srcdoc document) downloaded it again, measured at the
# full 1.48 MB gzip body per toggle. The Streamlit page outlives its figure
# iframes, so the first draw leaves a Blob URL of the script on it (read back out
# of the HTTP cache with `force-cache`, not downloaded twice) and later draws load
# that. `document.write` keeps the load parser-blocking, which the figure's own
# inline `Plotly.newPlot` script depends on. The memo is keyed by the URL, which
# carries the plotly.js version, and a page that cannot be reached (not
# same-origin) just falls back to the plain URL.
_PLOTLYJS_LOADER = """<script>
(function () {
  var src = "__SRC__", url = src, host = null;
  try {
    host = window.parent !== window ? window.parent : null;
    if (host) void host.document;
  } catch (err) {
    host = null;
  }
  var memo = host && host.__scanpathPlotlyJs;
  if (memo && memo.src === src) url = memo.url;
  document.write('<script charset="utf-8" src="' + url + '"><\\/script>');
  if (!host || url !== src) return;
  window.addEventListener("load", function () {
    fetch(src, { cache: "force-cache" })
      .then(function (r) { return r.ok ? r.blob() : null; })
      .then(function (blob) {
        var prev = host.__scanpathPlotlyJs;
        if (!blob || (prev && prev.src === src)) return;
        if (prev) host.URL.revokeObjectURL(prev.url);
        var copy = new host.Blob([blob], { type: "application/javascript" });
        host.__scanpathPlotlyJs = { src: src, url: host.URL.createObjectURL(copy) };
      })
      .catch(function () {});
  });
})();
</script>"""


def plotlyjs_script() -> str:
    """The ``<script>`` that loads the bundled plotly.js into a figure iframe.

    Put it ahead of ``fig.to_html(include_plotlyjs=False, …)``. It loads
    :func:`plotlyjs_src` on the first draw and, after that, the copy the
    Streamlit page kept of it — see ``_PLOTLYJS_LOADER`` for why.
    """
    return _PLOTLYJS_LOADER.replace("__SRC__", plotlyjs_src())
