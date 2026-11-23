"""Collect source figures from the active dataset and open the publication editor."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

import streamlit as st

from . import dataset_credit, publication
from .crash_report import guarded
from .html_embed import plotlyjs_src


def collect(figure, title: str, *, kind="chart", description="", settings=None) -> dict:
    refs = dataset_credit.references(st.session_state)
    src = publication.source(
        figure,
        title,
        kind=kind,
        description=description,
        settings=settings,
        references=[
            dataset_credit.reference_text(ref, "credit")
            for ref in refs
            if kind != "chart" or ref["side"] == "A"
        ],
    )
    st.session_state.setdefault("_publication_sources", {})[src["id"]] = src
    return src


def chart_button(figure, title: str, key: str) -> None:
    if st.button("Add chart to figure workspace", key="publication_chart_" + key):
        collect(figure, title, description=title)
        st.success(
            "Chart added. Open Prepare figure under Scanpath → Export or Data Management → Saved work."
        )


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


@st.fragment
@guarded()
def workspace(
    key: str, plot_id: str = "", last_id: str | None = None, compare: bool = False
) -> None:
    sources = list(st.session_state.get("_publication_sources", {}).values())
    doc = publication.project(sources[-1:])
    doc["sources"] = sources
    width = st.session_state.get("export_figure_width")
    if width:
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
    doc["dpi"] = max(50, min(1200, st.session_state.get("export_figure_dpi") or 300))
    session = st.session_state.setdefault("_publication_session", uuid.uuid4().hex)
    imported = st.session_state.get("_publication_imported")
    if imported:
        doc = {**imported["project"], "sources": sources}
    doc["currentSource"] = last_id
    doc["comparison"] = compare
    widget = st.components.v2.component(
        "publication_workspace",
        html='<iframe title="Publication figure workspace" style="display:block;width:100%;height:760px;border:0"></iframe>',
        js=_BRIDGE,
    )
    replacement = st.session_state.get("_publication_replacement")
    rev = json.dumps(
        [
            session,
            [s["id"] for s in sources],
            last_id,
            doc["width"],
            doc["dpi"],
            compare,
            plot_id,
            replacement,
            imported["id"] if imported else None,
        ]
    )
    cached = st.session_state.get("_publication_markup", {})
    if cached.get("rev") != rev:
        cached = {
            "rev": rev,
            "html": publication.editor_html(
                doc,
                plotly_script=f'<script src="{plotlyjs_src()}"></script>',
                session=session,
                plot_id=plot_id,
                replacement=replacement,
                import_id=imported["id"] if imported else "",
            ),
        }
        st.session_state["_publication_markup"] = cached
    result = widget(
        key=key,
        data={**cached, "session": session},
        on_action_change=lambda: None,
        height="content",
    )
    action = getattr(result, "action", None)
    if action and action.get("type") in {"pdf", "html"}:
        fmt = action["type"]
        try:
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
            from . import loading

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
    if action and action.get("type") == "stack":
        st.session_state["_publication_stack"] = action["value"]
        st.rerun()
    if action and action.get("type") == "batch":
        st.session_state["_publication_batch"] = action["value"]
        st.rerun()


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
    compare=False,
):
    group = st.expander(
        "Prepare figure for a paper or slide",
        expanded=key == "scanpath" and st.session_state.get("_publication_open", False),
        on_change="rerun",
    )
    if not group.open:
        return
    with group:
        current = None
        if figure is not None or replay is not None:
            add = st.button(
                "Use current " + ("replay" if replay else "figure"),
                key=key + "_publication_use",
            )
            replacing = st.session_state.pop("_publication_recapture", None)
            if add or replacing or not st.session_state.get("_publication_sources"):
                src = collect(
                    replay.figure_dict() if replay else figure,
                    title,
                    kind=kind,
                    description=description,
                    settings=settings_for() if settings_for else None,
                )
                if add:
                    st.caption(
                        "Source added. Under Panel layout, add it as a panel or use it to replace a reading."
                    )
                if replacing:
                    st.session_state["_publication_replacement"] = {
                        **replacing,
                        "new": src["id"],
                    }
                st.session_state["_publication_current"] = (title, src["id"])
            record = st.session_state.get("_publication_current")
            if record and record[0] == title:
                current = record[1]
        workspace("publication_" + key, plot_id, current, compare)


def apply_pending() -> None:
    """Apply workspace requests before Streamlit mounts the affected widgets."""
    from .controls import write_through
    from .session_keys import PARAM_PREPARE, SINGLE_COMPARE_LAYOUT
    from .tabs import SUBTAB_EXPORT

    ss = st.session_state
    if st.query_params.get(PARAM_PREPARE) == "1" and not ss.get(
        "_publication_link_read"
    ):
        ss["_publication_link_read"] = True
        ss["_publication_open"] = True
        ss["single_subtab"] = SUBTAB_EXPORT
    if replacing := ss.pop("_publication_stack", None):
        write_through(SINGLE_COMPARE_LAYOUT, "Stacked")
        write_through("global_fit_to_monitor", False)
        write_through("_rail_crop_to_data", True)
        ss["_publication_recapture"] = replacing
    if batch := ss.pop("_publication_batch", None):
        try:
            width = float(batch["width"])
            dpi = int(batch["dpi"])
        except (ValueError, TypeError, KeyError):
            return
        if 1 <= width <= 1000 and 50 <= dpi <= 1200:
            ss["bulk_export_print_width"] = width
            ss["bulk_export_print_dpi"] = dpi


def restore(doc: dict) -> None:
    """Open an uploaded publication recipe, retaining locally collected sources."""
    from .tabs import SUBTAB_EXPORT

    publication.validate_project(doc)
    sources = st.session_state.setdefault("_publication_sources", {})
    sources.update({s["id"]: s for s in doc["sources"]})
    st.session_state["_publication_imported"] = {"id": uuid.uuid4().hex, "project": doc}
    st.session_state["_publication_open"] = True
    st.session_state["single_subtab"] = SUBTAB_EXPORT
