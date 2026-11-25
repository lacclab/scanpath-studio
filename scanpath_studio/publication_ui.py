"""Prepare the current scanpath, replay or corpus chart for export."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile

import streamlit as st

from . import dataset_credit, loading, publication, ui_mode
from .crash_report import guarded
from .html_embed import plotlyjs_src
from .reruns import rerun

_BRIDGE = """
export default function({data,parentElement,setTriggerValue}){
  const frame=parentElement.querySelector('iframe');
  const listener=e=>{
    if(e.source!==frame.contentWindow || e.data?.key!==data.session)return;
    if(e.data.height){frame.style.height=Math.max(280,Math.ceil(e.data.height))+'px';}
    if(e.data.action)setTriggerValue('action',{type:e.data.action,value:e.data.value});
  };
  window.addEventListener('message',listener);
  if(frame.dataset.rev!==data.rev){frame.dataset.rev=data.rev;frame.srcdoc=data.html;}
  return ()=>window.removeEventListener('message',listener);
}
"""


#: How many workspaces' editor pages a session keeps between reruns.
_MARKUP_PAGES = 4


@st.fragment
@guarded()
def workspace(key: str, doc: dict, revision: str, *, plot_id: str = "") -> None:
    # The page keeps edits per figure. A different trial, source chart or file
    # starts with its own artwork, including when two figures have the same name.
    session = st.session_state.setdefault("_publication_session", uuid.uuid4().hex)
    batch = key == "scanpath" and not ui_mode.is_simple()
    rev = json.dumps([key, revision, doc["width"], doc["dpi"], plot_id, batch])
    # Each workspace keeps its own editor page, most recently drawn last, so two
    # open on one page don't rebuild each other's on every rerun.
    pages = st.session_state.setdefault("_publication_markup", {})
    cached = pages.pop(key, None)
    if cached is None or cached["rev"] != rev:
        cached = {
            "rev": rev,
            "html": publication.editor_html(
                doc,
                plotly_script=f'<script src="{plotlyjs_src()}"></script>',
                session=session,
                plot_id=plot_id,
                import_id=json.dumps([key, revision]),
                batch=batch,
            ),
        }
    pages[key] = cached
    while len(pages) > _MARKUP_PAGES:
        del pages[next(iter(pages))]
    widget = st.components.v2.component(
        "publication_workspace",
        html='<iframe title="Publication figure workspace" style="display:block;width:100%;height:460px;border:0"></iframe>',
        js=_BRIDGE,
    )
    result = widget(
        key="publication_" + key,
        data={**cached, "session": session},
        on_action_change=lambda: None,
        height="content",
    )
    action = getattr(result, "action", None)
    if action and action.get("type") in {"pdf", "html"}:
        fmt = action["type"]
        try:
            with loading.card(
                st.empty(),
                key="publication_" + fmt,
                title="Preparing the PDF"
                if fmt == "pdf"
                else "Preparing the offline editor",
            ):
                data = publication.render(action["value"], fmt)
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
        else:
            st.download_button(
                "Download prepared PDF" if fmt == "pdf" else "Save offline editor",
                data,
                file_name="figure." + fmt,
                mime="application/pdf" if fmt == "pdf" else "text/html",
                key=key + "_" + fmt,
                on_click="ignore",
            )
    if action and action.get("type") == "video":
        try:
            project = action["value"]
            with loading.card(
                st.empty(), key="publication_movie", title="Rendering clip and poster"
            ):
                movie = publication.render(project, "mp4")
                poster = publication.replay_poster(project)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("clip.mp4", movie)
                z.writestr("poster.png", poster)
                z.writestr("figure.json", publication.render(project, "json"))
            st.download_button(
                "Download prepared clip and poster",
                buf.getvalue(),
                file_name="replay.zip",
                mime="application/zip",
                key=key + "_clip",
                on_click="ignore",
            )
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            st.error(str(exc))
    if action and action.get("type") == "batch":
        st.session_state["_publication_batch"] = action["value"]
        rerun()


def chart_key(figure) -> str:
    """The export workspace key of a Corpus Analysis chart.

    It names the open section and what the chart shows (its title, axis titles
    and kinds of marks), never the chart's position on the page, so a note
    drawn above the chart keeps its workspace open with its draft.
    """
    from .session_keys import CORPUS_SUBTAB

    layout = figure.layout
    identity = [
        st.session_state.get(CORPUS_SUBTAB),
        layout.title.text,
        layout.xaxis.title.text,
        layout.yaxis.title.text,
        sorted({trace.type for trace in figure.data}),
    ]
    digest = hashlib.sha256(json.dumps(identity, default=str).encode()).hexdigest()
    return "chart_" + digest[:16]


def _capture(figure, replay, *, title, kind, description, settings, references) -> dict:
    kwargs = dict(
        kind=kind, description=description, settings=settings, references=references
    )
    if replay is None:
        return publication.source(figure, title, **kwargs)
    # A replay can contain thousands of frames. Reuse the captured source when
    # an unrelated app control reruns the page with the same clip and provenance.
    key = (
        replay.signature,
        title,
        kind,
        description,
        references,
        {k: v for k, v in (settings or {}).items() if k != "exported_at"},
    )
    cached = st.session_state.get("_publication_replay")
    if cached is None or cached[0] != key:
        cached = (key, publication.source(replay.figure_dict(), title, **kwargs))
        st.session_state["_publication_replay"] = cached
    return cached[1]


def render(
    figure=None,
    *,
    title="",
    kind="scanpath",
    description="",
    settings_for=None,
    plot_id="",
    replay=None,
    key="scanpath",
) -> bool:
    library = key == "saved"
    group = st.expander(
        "Saved figures" if library else "Prepare figure for export",
        key=f"prepare_figure_{key}",
        expanded=key == "scanpath" and st.session_state.get("_publication_open", False),
        on_change="rerun",
    )
    if not group.open:
        return False
    with group:
        imported = (
            st.session_state.get("_publication_imported") if key == "scanpath" else None
        )
        if imported and st.button(
            "Return to current reading", key="publication_return_to_view"
        ):
            del st.session_state["_publication_imported"]
            imported = None
        if imported:
            workspace(key, imported["project"], imported["id"])
        elif figure is not None or replay is not None:
            settings = settings_for() if settings_for else None
            refs = [
                dataset_credit.reference_text(ref, "credit")
                for ref in dataset_credit.references(st.session_state)
                if kind != "chart" or ref["side"] == "A"
            ]
            src = _capture(
                figure,
                replay,
                title=title,
                kind=kind,
                description=description,
                settings=settings,
                references=refs,
            )
            doc = publication.project([src], name=title)
            if width := st.session_state.get("export_figure_width"):
                doc["width"] = max(
                    10,
                    min(
                        1000,
                        float(width)
                        * (
                            25.4
                            if st.session_state.get("export_figure_width_unit") == "in"
                            else 1
                        ),
                    ),
                )
                doc["destination"] = "Custom paper"
            doc["dpi"] = max(
                50, min(1200, st.session_state.get("export_figure_dpi") or 300)
            )
            workspace(key, doc, src["id"], plot_id=plot_id)
        elif library:
            workspace(key, publication.project([]), "library")
        else:
            st.caption("Choose a reading to prepare its figure.")
    return True


def apply_pending() -> None:
    """Apply workspace requests before Streamlit mounts the affected widgets."""
    from .session_keys import PARAM_PREPARE
    from .tabs import SUBTAB_EXPORT

    ss = st.session_state
    if st.query_params.get(PARAM_PREPARE) == "1" and not ss.get(
        "_publication_link_read"
    ):
        ss["_publication_link_read"] = True
        ss["_publication_open"] = True
        ss["single_subtab"] = SUBTAB_EXPORT
    if batch := ss.pop("_publication_batch", None):
        try:
            width = float(batch["width"])
            dpi = int(batch["dpi"])
        except (ValueError, TypeError, KeyError):
            return
        if 1 <= width <= 1000 and 50 <= dpi <= 1200:
            ss["bulk_export_print_width"] = width
            ss["bulk_export_print_dpi"] = dpi
            ss["publication_bundle"] = True


def restore(doc: dict) -> None:
    """Open an uploaded publication recipe in the Scanpath export tab."""
    from .tabs import SUBTAB_EXPORT

    publication.validate_project(doc)
    st.session_state["_publication_imported"] = {"id": uuid.uuid4().hex, "project": doc}
    st.session_state["_publication_open"] = True
    st.session_state["prepare_figure_scanpath"] = True
    st.session_state["single_subtab"] = SUBTAB_EXPORT
