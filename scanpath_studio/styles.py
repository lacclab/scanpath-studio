"""CSS styles for the Scanpath Studio Streamlit app."""

from __future__ import annotations

from scanpath_studio.constants import (
    SELECTOR_ROW_FLOOR_CAPS,
    SELECTOR_ROW_FLOORS_REM,
    SELECTOR_ROW_WRAP_REM,
    SELECTOR_SCREEN_FLOOR_REM,
    SELECTOR_SCREEN_PICKER_REM,
    SELECTOR_STEPS_FLOOR_REM,
)


def get_app_css() -> str:
    """Return custom CSS to reduce whitespace and disable animations."""
    css = """
    <style>
    /* Force LTR regardless of the browser's own OS/locale default direction.
       Every plot, coordinate, and reading-order concept in this app is
       physical left-to-right, but nothing here ever states that — so a
       browser whose UI language is a RTL one (Hebrew, Arabic, ...) inherits
       `direction: rtl` onto the page, and BaseWeb (the component library
       Streamlit's own widgets are built on) styles several of them with CSS
       *logical* properties that flip under it. The clearest case is the
       select-slider: its thumb is positioned with a physical `left: X%` (so
       it still lands at the right spot), but its filled track segment uses a
       logical inset that flips to the *other* end — the fill looks
       nowhere near the thumb it is supposed to lead up to. Rather than only
       patching the slider, force ltr globally: anything else BaseWeb draws
       with a logical property would drift the same way, silently.
       Bug reported with a Hebrew-locale browser (screenshot: thumb correct,
       fill anchored to the wrong end). */
    html, body, [data-testid="stApp"] {
        direction: ltr !important;
        /* UX-129: the page itself must never grow a side-to-side scrollbar —
           whatever pushes past the viewport (a too-wide row, a tooltip that
           escapes its column) should be clipped, not turned into a reason to
           scroll the whole app sideways. Elements that legitimately need
           horizontal scroll (a wide dataframe) already carry their own,
           narrower `overflow-x: auto` and are unaffected by clipping here. */
        overflow-x: hidden;
    }
    /* UX-99: the page's side gutters. Streamlit's wide layout reserves ~5rem
       either side, which on this app is ~10rem of nothing beside the widest
       things it draws — the scanpath canvas plus its rail, the Corpus tables,
       the dataset table. Trimmed to a gutter that still keeps text off the
       window edge. `!important` because Streamlit's own padding rule carries
       higher specificity than a bare class selector. */
    .stMainBlockContainer,
    section.main > div.block-container {
        padding-top: 3rem;
        padding-bottom: 0 !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }
    @media (max-width: 640px) {
        .stMainBlockContainer,
        section.main > div.block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
    }
    .stMainBlockContainer > [data-testid="stVerticalBlock"] > :last-child,
    section.main > div.block-container > [data-testid="stVerticalBlock"] > :last-child {
        margin-bottom: 0 !important;
    }
    /* Remove all whitespace around plotly charts */
    div[data-testid="stPlotlyChart"] {margin: 0 !important; padding: 0 !important; line-height: 0 !important;}
    div[data-testid="stPlotlyChart"] > div {margin: 0 !important; padding: 0 !important;}
    div[data-testid="stPlotlyChart"] iframe {display: block !important; margin: 0 !important; padding: 0 !important;}
    /* UX-188: an inline iframe sits on the text baseline, leaving a descender's
       gap under it that its overflow:auto container turned into a scrollbar
       with nothing to scroll (8px under the plot, 25px under each script-only
       embed). */
    iframe[data-testid="stIFrame"] {display: block;}
    .stPlotlyChart {margin: 0 !important; padding: 0 !important;}
    /* Target parent containers */
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stPlotlyChart"]) {padding: 0 !important; margin: 0 !important; gap: 0 !important;}
    div[data-testid="element-container"]:has(> div[data-testid="stPlotlyChart"]) {margin: 0 !important; padding: 0 !important;}
    /* Reduce gap in vertical blocks globally */
    div[data-testid="stVerticalBlock"] {gap: 0rem !important;}
    div[data-testid="stVerticalBlock"] > div {margin-bottom: 0.25rem !important;}
    /* Target the js-plotly-plot container */
    .js-plotly-plot, .plot-container, .plotly {margin: 0 !important; padding: 0 !important;}
    .main-svg {display: block !important;}
    /* Remove extra spacing from streamlit elements near charts */
    div[data-testid="stMarkdown"] + div[data-testid="element-container"]:has(div[data-testid="stPlotlyChart"]) {margin-top: 0 !important;}
    div[data-testid="element-container"]:has(div[data-testid="stPlotlyChart"]) + div[data-testid="stExpander"] {margin-top: 0.5rem !important;}
    /* Reduce spacing around dataframes */
    div[data-testid="stDataFrame"] {margin-bottom: 0 !important;}
    div[data-testid="element-container"]:has(div[data-testid="stDataFrame"]) {margin-bottom: 0.25rem !important;}
    /* Reduce multiselect spacing */
    div[data-testid="stMultiSelect"] {margin-bottom: 0.25rem !important;}
    /* Disable fade in/out animations on element updates */
    div[data-testid="stPlotlyChart"], div[data-testid="element-container"], .stMarkdown, .element-container {
        animation: none !important;
        transition: none !important;
    }
    div[data-testid="stPlotlyChart"] * {
        animation: none !important;
        transition: none !important;
    }
    /* Disable Streamlit's stale element fade effect */
    [data-stale="true"] {
        opacity: 1 !important;
    }
    /* Navigation (Scanpath ⇄ Corpus Analysis) is Streamlit's own top nav —
       `st.navigation(position="top")`, rendered into the header strip. It needs
       no CSS from us: it is platform chrome, it costs no page height, and
       styling it would just make it look less like the rest of Streamlit. The
       old right-aligned `.st-key-header_buttons` rule went with the single
       toggle button it aligned. */
    /* === The top menu bar ====================================================
       Replaced the left sidebar: every group that used to be an
       `st.sidebar` section is a popover in this one row (see menu.py).

       UX-38 got it down to two triggers (❓ Help · 💾 Session, plus 🐛 Debug),
       at which point a whole page row for two buttons was the wrong trade — so
       it now shares the **title row**, right-aligned over where the Scanpath
       view's control rail begins. That is plain `st.columns`, not CSS: there is
       no supported way to put widgets in Streamlit's own header strip, and
       positioning them into it means `position: fixed` against an internal test
       id whose width depends on which toolbar buttons that deployment shows.

       So all this rule does now is stop the buttons stretching to fill their
       column; the alignment is the container's own `horizontal_alignment`.

       (UX-8's sidebar collapse/expand styling lived here. It is gone with the
       sidebar: there is no longer any chrome to collapse.) */

    /* === The Data page, off-screen ===========================================
       DATA-26. The setup widgets — the loaders' directory input and ⬇ Download
       button, the source options, the column-mapping selectboxes — *drive*
       `prepare_data` on every rerun, and Streamlit drops the key of a widget
       that did not render. So `app.main` builds the page every run and switches
       only its key: visible under `data_setup_page`, hidden under this one.

       `display: none` (not `visibility`/`opacity`/off-viewport): the widgets
       must keep executing but must contribute no layout, and the tour's
       `findVisible()` picks targets by their layout rect, so a hidden copy of a
       spotlight target has to measure zero rather than sit off to one side. */
    .st-key-data_setup_page_offscreen { display: none !important; }

    /* DATA-35 — the Data page's two screens: the overview (the dataset table +
       what's in the open dataset) and the ✏️ Edit dataset screen. Same
       mechanism and same reason as the page above, one level in: the editor is
       *made* of the widgets that drive `prepare_data`, so it renders every run
       and is hidden by key rather than skipped. */
    .st-key-data_overview_offscreen { display: none !important; }
    .st-key-data_dataset_editor_offscreen { display: none !important; }

    /* UX-174 — 📂 Available datasets as a focused table, built from keyed
       containers (`app.render_dataset_table`): `dsrow_head` + one
       `dsrow_<slug>` line per dataset (`dsrow_current_<slug>` for the open
       one), each cell a fixed-width `dsc_<column>_<slug>` / `dsh_<column>` box
       so the columns line up down the list. The grid scrolls sideways on its
       own when it is wider than the page, with the name held in view. */
    .st-key-dataset_table_grid {
        overflow-x: auto;
        gap: 0 !important;
    }
    /* The page title sits straight above the table (UX-177): give the header
       row a little air so the title does not read as part of it. */
    .st-key-dataset_table {
        margin-top: 0.75rem;
    }
    .st-key-dataset_table_grid > div { margin-bottom: 0 !important; }
    .st-key-dataset_table_grid [class*="st-key-dsrow_"] {
        min-width: max-content;
        padding: 0.45rem 0.5rem;
        border-bottom: 1px solid var(--sps-border);
    }
    .st-key-dataset_table_grid .st-key-dsrow_head {
        padding-top: 0.1rem;
        padding-bottom: 0.1rem;
        border-bottom-color: rgba(128, 128, 128, 0.45);
    }
    /* The open dataset: a tint *and* the Current badge — never color alone. */
    .st-key-dataset_table_grid [class*="st-key-dsrow_current_"] {
        background: var(--sps-accent-soft);
    }
    /* A keyed container's class sits on its inner block; the flex item that
       takes the width is the `stLayoutWrapper` around it — so the cell rules
       below select that wrapper, by what it holds. Every cell but the name
       keeps its width; the name gives way first, down to its minimum, and past
       that the grid scrolls instead. */
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_"]),
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsh_"]) {
        flex-shrink: 0 !important;
    }
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]),
    [data-testid="stLayoutWrapper"]:has(> .st-key-dsh_name) {
        flex-shrink: 1 !important;
        min-width: 15rem;
        position: sticky;
        left: 0;
        z-index: 1;
    }
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]) {
        background: var(--sps-page-bg);
    }
    /* Opaque (it scrolls over the counts), in the open row's tint. */
    [class*="st-key-dsrow_current_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]) {
        background:
            linear-gradient(var(--sps-accent-soft), var(--sps-accent-soft)),
            var(--sps-page-bg);
    }
    /* UX-174 r2 — the whole row opens its dataset. Its first child is the
       row's own button, stretched over the row; every cell is drawn above it
       and lets a click fall through to it, except the one holding Remove. The
       button's label ("Open <name>") is for screen readers — the name is
       drawn in its cell. */
    .st-key-dataset_table_grid [class*="st-key-dsrow_"] { position: relative; }
    [class*="st-key-dsrow_"] > [class*="st-key-dataset_open_"] {
        position: absolute !important;
        inset: 0;
        width: auto !important;
        margin: 0 !important;
        z-index: 0;
    }
    [class*="st-key-dataset_open_"] .stButton,
    [class*="st-key-dataset_open_"] button {
        width: 100%;
        height: 100%;
    }
    [class*="st-key-dataset_open_"] button {
        border: 0;
        border-radius: 0;
        background: transparent;
        cursor: pointer;
    }
    [class*="st-key-dataset_open_"] button [data-testid="stMarkdownContainer"] {
        position: absolute !important; width: 1px; height: 1px;
        overflow: hidden; clip-path: inset(50%); white-space: nowrap;
    }
    [class*="st-key-dsrow_current_"] > [class*="st-key-dataset_open_"] button {
        cursor: default;
    }
    [class*="st-key-dsrow_"] > [data-testid="stLayoutWrapper"] {
        position: relative;
        z-index: 1;
        pointer-events: none;
    }
    [class*="st-key-dsrow_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]) {
        position: sticky;
    }
    [class*="st-key-dsrow_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_actions_"]),
    [class*="st-key-dsc_name_"] [data-testid="stTooltipHoverTarget"] {
        pointer-events: auto;
    }
    .st-key-dataset_table_grid [class*="st-key-dsrow_"]:not(.st-key-dsrow_head):not([class*="st-key-dsrow_current_"]):hover,
    .st-key-dataset_table_grid [class*="st-key-dsrow_"]:not(.st-key-dsrow_head):not([class*="st-key-dsrow_current_"]):hover > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]) {
        background:
            linear-gradient(var(--sps-hover-soft), var(--sps-hover-soft)),
            var(--sps-page-bg);
    }
    .st-key-dataset_table_grid [class*="st-key-dsrow_"]:has([class*="st-key-dataset_open_"] button:focus-visible) {
        outline: 2px solid var(--sps-accent);
        outline-offset: -2px;
    }
    .sps-ds-name { font-weight: 600; }
    /* Streamlit pulls each block up by a negative bottom margin and gives a
       paragraph its own, which in one-line cells puts their text at different
       heights. */
    [class*="st-key-dsc_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
    [class*="st-key-dsc_"] [data-testid="stMarkdownContainer"] p { margin: 0; }
    [class*="st-key-dsc_"] > div { margin-bottom: 0 !important; }
    .st-key-dataset_table_grid [class*="st-key-dsrow_"]:not(.st-key-dsrow_head) {
        min-height: 2.75rem;
    }
    .sps-ds-num {
        display: block;
        text-align: right;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .sps-ds-gap { opacity: 0.6; font-size: 0.85rem; }
    .sps-ds-status { white-space: nowrap; font-size: 0.9rem; }
    /* Header labels are sort buttons; keep them quiet and on one line. */
    .st-key-dsrow_head button {
        padding: 0 !important;
        min-height: 0;
        font-size: 0.875rem;
    }
    .st-key-dsrow_head button p { white-space: nowrap; font-size: 0.875rem; }
    /* Edit and Remove are their icons; each label names the dataset for
       screen readers. */
    [class*="st-key-dataset_row_edit_"] button,
    [class*="st-key-dataset_row_remove_"] button {
        padding: 0 0.35rem !important;
        min-height: 0;
    }
    [class*="st-key-dataset_row_edit_"] button [data-testid="stMarkdownContainer"],
    [class*="st-key-dataset_row_remove_"] button [data-testid="stMarkdownContainer"] {
        position: absolute !important; width: 1px; height: 1px;
        overflow: hidden; clip-path: inset(50%); white-space: nowrap;
    }
    .st-key-dataset_table_grid [class*="st-key-dataset_row_edit_"] button:focus-visible,
    .st-key-dataset_table_grid [class*="st-key-dataset_row_remove_"] button:focus-visible,
    .st-key-dsrow_head button:focus-visible {
        outline: 2px solid var(--sps-accent);
        outline-offset: 2px;
        border-radius: 0.25rem;
    }
    /* Phone width: the name, its Current badge, the key count and Remove.
       Everything else is in *What's in the dataset*, once it is open. */
    @media (max-width: 640px) {
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_"]):not(:has(> [class*="st-key-dsc_name_"])):not(:has(> [class*="st-key-dsc_participants_"])):not(:has(> [class*="st-key-dsc_actions_"])),
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsh_"]):not(:has(> .st-key-dsh_name)):not(:has(> .st-key-dsh_participants)):not(:has(> .st-key-dsh_actions)) {
            display: none !important;
        }
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]),
        [data-testid="stLayoutWrapper"]:has(> .st-key-dsh_name) {
            min-width: 0;
        }
        [class*="st-key-dsrow_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_name_"]),
        [class*="st-key-dsrow_"] > [data-testid="stLayoutWrapper"]:has(> .st-key-dsh_name) {
            position: relative;
        }
        .st-key-dataset_table_grid [class*="st-key-dsrow_"] { min-width: 0; }
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-dsc_participants_"]),
        [data-testid="stLayoutWrapper"]:has(> .st-key-dsh_participants) {
            width: auto !important;
            min-width: 3.5rem;
        }
    }

    /* UX-53 — the 🗂️ Data page was "too much space and text, and text too
       small". Scoped to the page's own key so the plot rail and the analysis
       views keep the metrics they were tuned against (#UX-51 sized the rail
       deliberately, and a global type change would move it).

       Two levers, both conservative: close the vertical gap Streamlit puts
       between every block, and lift the *smallest* type — captions carry most
       of this page's prose, and they were the part that read as too small. */
    .st-key-data_setup_page [data-testid="stVerticalBlock"] { gap: 0.55rem; }
    .st-key-data_setup_page [data-testid="stCaptionContainer"],
    .st-key-data_setup_page [data-testid="stCaptionContainer"] p {
        font-size: 0.86rem;
        line-height: 1.45;
    }
    /* The dividers between the page's four stages were doing the spacing job
       twice — a rule plus a margin either side of it. */
    .st-key-data_setup_page hr { margin: 0.7rem 0; }
    .st-key-data_setup_page [data-testid="stExpander"] { margin-bottom: 0.35rem; }

    div[data-testid="stPopover"] button { border-radius: 999px; }
    div[data-testid="stPopover"] button p { white-space: nowrap; }
    /* BUG-89 — a click on a popover's ▾ must land on the button, not the
       chevron glyph. Opening swaps that glyph (expand_more → expand_less), so
       the span the pointer hit is detached by the time the click bubbles to
       `document`. There Streamlit's own outside-click handler ignores the
       opening click only within 50 ms of it; if the popover takes longer to
       render (the rail's big ones often do), the detached target fails its
       "inside the trigger?" test and the popover closes itself 2 ms after
       opening. The next click then closes an already-closed popover, which is
       why it took 2–3 clicks. With the glyph transparent to the pointer the
       target is always an element that survives the re-render. The chevron is
       the one `aria-hidden` child of the trigger; its label and icon keep
       their nodes. */
    [data-testid="stPopoverButton"] [aria-hidden="true"],
    [data-testid="stPopoverButton"] [aria-hidden="true"] * {
        pointer-events: none;
    }
    /* BUG-108: a mode or rail-section trigger is named ("Fixation settings")
       so a screen reader can tell them apart, but only its chevron is drawn
       (UX-80 r2): the label stays in the accessibility tree, clipped to
       nothing, as `.sps-sr-only` does.
       UX-200 named the other icon-only popovers the same way: the + menu,
       the table previews, the chip-field editor and the ⇅ sorts, each keyed
       `iconpop_*` (the + menu kept its own key). A plain label, so the
       popover's dialog, which takes the label as its `aria-label`, is named
       the same. */
    .st-key-add_dataset_menu [data-testid="stPopoverButton"]
        [data-testid="stMarkdownContainer"],
    [class*="st-key-iconpop_"] [data-testid="stPopoverButton"]
        [data-testid="stMarkdownContainer"],
    [class*="st-key-split_mode_"] [data-testid="stPopoverButton"]
        [data-testid="stMarkdownContainer"] {
        position: absolute !important; width: 1px; height: 1px;
        margin: -1px; padding: 0; border: 0; overflow: hidden;
        clip-path: inset(50%); white-space: nowrap;
    }
    /* …and ⇅ is a typographic glyph, not an icon `icon=` can take, so the
       sorts draw it here. The second `content` gives it empty alt text, which
       keeps it out of the accessible name; a browser that does not know the
       syntax drops that line and keeps the first. */
    [class*="st-key-iconpop_sort_"] [data-testid="stPopoverButton"]::before {
        content: "⇅";
        content: "⇅" / "";
    }
    /* UX-200: an icon-only *button* names itself with `constants.spoken`, an
       `<em>` in its label clipped the same way, so the glyph or icon stays
       all that is drawn. No button label uses emphasis for anything else
       (`tests/test_popover_names.py`). */
    button [data-testid="stMarkdownContainer"] em {
        position: absolute !important; width: 1px; height: 1px;
        margin: -1px; padding: 0; border: 0; overflow: hidden;
        clip-path: inset(50%); white-space: nowrap;
    }
    div[data-testid="stPopoverBody"] {
        min-width: min(28rem, 90vw);
    }
    /* The wizard's *Setup help* is a two-row menu, not a panel of controls:
       as wide as its rows, like the nav's own ❓ Help menu, rather than 28rem
       of empty popover to the right of two short labels. The body is
       portalled out of the wizard, so it is found by the row it holds. */
    div[data-testid="stPopoverBody"]:has(.st-key-wizard_guide_replay) {
        min-width: 0;
    }
    div[data-testid="stPopoverBody"] p { line-height: 1.45; }

    /* === Streamlit's spinners (UX-165) ======================================
       The cache_data spinners and st.spinner — calm and inline now. They used
       to be a pulsing blue banner; the long waits have loading cards
       (loading.py) since UX-165, and what is left is short enough that a
       banner shouted louder than the wait deserved. */
    div[data-testid="stSpinner"] {
        width: fit-content;
        padding: 0.35rem 0.75rem !important;
        margin: 0.3rem 0 !important;
        border: 1px solid var(--sps-border);
        border-radius: 999px;
        background: var(--sps-page-bg);
    }
    div[data-testid="stSpinner"] p { font-size: 0.9rem; margin: 0; }

    /* === UX-165 · loading states =============================================
       One card for every long wait (loading.py): hidden for its first
       loading.DELAY_S, then revealed by a timer thread writing `.sps-reveal`
       into it. A region card sits over a size box that holds its area at the
       height the content will take; the page card sits over a skeleton of the
       view. Nothing here animates for readers who ask for reduced motion. */
    [class*="st-key-sps_cardbody_"] { display: none !important; }
    /* A card opens hidden — the page card on every run — so until it shows,
       its slot is out of the layout: an empty slot still takes a gap, and the
       page card's margins would push the whole view down and back on each
       rerun. A size box keeps it in: holding the area is that box's job. */
    /* Flat on purpose: `:has()` may not nest inside `:has()`, and a browser
       drops a rule that tries. The wrapper holds only its card, so "no
       .sps-reveal in the wrapper" is "the card isn't showing". */
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_card_"]):not(:has(.sps-reveal)):not(:has(.sps-size-box)) { display: none !important; }
    [class*="st-key-sps_card_"]:has(.sps-reveal) [class*="st-key-sps_cardbody_"] {
        display: flex !important;
        flex-direction: column;
        gap: 0.4rem !important;
        width: 100%;
        box-sizing: border-box;
        padding: 0.8rem 1rem 0.6rem;
        border: 1px solid var(--sps-border);
        border-radius: 12px;
        background: var(--sps-page-bg);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
    }
    /* One track, as wide as the card's container — which the size box's own
       rule caps at the figure's width (loading.size_box_html) — so "center"
       means over the figure, and every width resolves from the column down: a
       track sized by its content would grow past a narrow column, or collapse
       to the card. */
    [class*="st-key-sps_card_"]:not(.st-key-sps_card_page) {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr);
    }
    [class*="st-key-sps_card_"]:not(.st-key-sps_card_page) > * { grid-area: 1 / 1; }
    /* Streamlit stretches a block's wrapper to the full width, and no
       `justify-self` moves a stretched box — so it takes the card's width. */
    [class*="st-key-sps_card_"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_cardbody_"]) {
        width: min(24rem, 100%) !important;
        align-self: center;
        justify-self: center;
        z-index: 2;
    }
    /* A card with no area to hold sits where it is written, like its neighbours. */
    [class*="st-key-sps_card_"]:not(.st-key-sps_card_page):not(:has(.sps-size-box)) > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-sps_cardbody_"]) { justify-self: start; }
    /* The reveal marker is an empty element in the body's flex column; hidden, it
       still counts for the gap, leaving a blank strip under the last row. It
       stays in the DOM, so the `:has(.sps-reveal)` rules keep matching. */
    [class*="st-key-sps_cardbody_"] > [data-testid="stElementContainer"]:has(.sps-reveal) { display: none !important; }
    .sps-size-box { width: 100%; pointer-events: none; }
    [class*="st-key-sps_card_"]:has(.sps-reveal) .sps-size-box {
        border-radius: 8px;
        background:
            linear-gradient(rgba(128, 128, 128, 0.10), rgba(128, 128, 128, 0.10)),
            color-mix(in srgb, var(--sps-page-bg) 60%, transparent);
        animation: sps-sk-pulse 1.6s ease-in-out infinite;
    }
    /* Streamlit pulls every markdown block 1rem up (margin-bottom: -1rem on its
       container), so the head and the step list add it back to keep a gap. */
    .sps-card-head { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 1.2rem; }
    .sps-card-title { font-weight: 600; flex: 1; min-width: 0; }
    /* Spoken, not drawn: the current step in the card's live region, which the
       detail line or step list already shows (loading.head_html). */
    .sps-sr-only {
        position: absolute !important; width: 1px; height: 1px;
        margin: -1px; padding: 0; border: 0; overflow: hidden;
        clip-path: inset(50%); white-space: nowrap;
    }
    .sps-card-time {
        font-size: 0.8rem; opacity: 0.7; white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }
    .sps-card-detail, .sps-step-count, .sps-step-time {
        font-size: 0.85rem; opacity: 0.8; font-variant-numeric: tabular-nums;
    }
    .sps-ring {
        display: inline-block; flex: none;
        width: 0.95rem; height: 0.95rem; box-sizing: border-box;
        border-radius: 50%;
        border: 2px solid var(--sps-accent-border);
        border-top-color: var(--sps-accent);
        animation: sps-spin 0.8s linear infinite;
    }
    .sps-steps {
        list-style: none; margin: 0 0 1.3rem; padding: 0;
        display: flex; flex-direction: column; gap: 0.3rem;
    }
    .sps-step { display: flex; align-items: center; gap: 0.5rem; font-size: 0.88rem; margin: 0 !important; }
    .sps-step .sps-icon { font-size: 1rem; }
    .sps-step-done .sps-icon { color: #2e9d5b; }
    .sps-step-todo { opacity: 0.5; }
    .sps-step-label { flex: 1; min-width: 0; }
    .sps-bar { height: 4px; border-radius: 2px; overflow: hidden; background: var(--sps-accent-soft); }
    .sps-bar > span { display: block; height: 100%; background: var(--sps-accent); transition: width 0.25s ease; }
    .sps-bar-indeterminate > span { width: 35%; animation: sps-slide 1.3s ease-in-out infinite; }
    /* Breathing room between the bar and the card's Cancel button. */
    [class*="st-key-sps_cancel_"] { margin-top: 0.75rem; }
    /* The page card: a skeleton of the view with the card over it. While it
       shows, everything else in the view's area — the previous page, or the
       new one being laid out underneath — stays hidden. */
    .st-key-sps_view:has(.sps-reveal-page) > :not(:first-child) { display: none !important; }
    /* On the Data view the area holds only the last view's leftovers (the Data page draws outside it). */
    .st-key-sps_view:has(.sps-view-hidden) > :not(:first-child) { display: none !important; }
    .st-key-sps_card_page { display: grid !important; grid-template-columns: minmax(0, 1fr); }
    .st-key-sps_card_page > * { grid-area: 1 / 1; }
    .st-key-sps_card_page:has(.sps-reveal) > [data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {
        align-self: start; justify-self: center; margin-top: 7rem;
    }
    .st-key-sps_card_page:has(.sps-sk-scanpath) > [data-testid="stLayoutWrapper"]:has(> .st-key-sps_cardbody_page) {
        justify-self: start; margin-left: max(0px, calc(40% - 12rem));
    }
    .sps-page-skeleton { pointer-events: none; }
    .sps-sk {
        border-radius: 0.5rem; background: rgba(128, 128, 128, 0.12);
        animation: sps-sk-pulse 1.6s ease-in-out infinite;
    }
    .sps-sk-scanpath { display: grid; grid-template-columns: 4fr 1fr; gap: 3rem; }
    .sps-sk-main { display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; }
    .sps-sk-selectors { display: grid; gap: 1rem; }
    .sps-sk-field { height: 2.5rem; }
    .sps-sk-chips { display: flex; gap: 0.45rem; flex-wrap: wrap; }
    .sps-sk-chip { width: 7.5rem; height: 1.7rem; border-radius: 999px; }
    .sps-sk-rail {
        display: flex; flex-direction: column; gap: 0.5rem;
        padding-left: 1rem; border-left: 1px solid var(--sps-border);
    }
    .sps-sk-row { height: 2.3rem; }
    .sps-sk-corpus { display: flex; flex-direction: column; gap: 1rem; }
    .sps-sk-tabs { height: 2.4rem; width: 60%; }
    .sps-sk-chart { height: 22rem; }
    .sps-sk-table { display: flex; flex-direction: column; gap: 0.4rem; }
    .sps-sk-table .sps-sk-row { height: 2rem; }
    /* UX-167 — the Scanpath plot area is a stage: its first child (the loading
       card) and its second (the figure) share one cell, so a card can open over
       a figure already on screen without moving it. Notes written after the
       figure flow into the rows below. */
    .st-key-tour_grp_plot { display: grid !important; grid-template-columns: minmax(0, 1fr); }
    .st-key-tour_grp_plot > :nth-child(-n + 2) { grid-area: 1 / 1; }
    .st-key-tour_grp_plot > :first-child { z-index: 3; }
    /* A card already says what the app is waiting on. */
    .stApp:has(.sps-reveal) div[data-testid="stSpinner"] { display: none !important; }
    @keyframes sps-spin { to { transform: rotate(360deg); } }
    @keyframes sps-sk-pulse { 50% { opacity: 0.55; } }
    @keyframes sps-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(290%); } }
    @media (prefers-reduced-motion: reduce) {
        .sps-ring, .sps-sk, .sps-bar-indeterminate > span,
        [class*="st-key-sps_card_"]:has(.sps-reveal) .sps-size-box { animation: none !important; }
        .sps-bar > span { transition: none !important; }
    }

    /* === Visual polish ==========================================================
       Tasteful, theme-robust chrome styling (header, tabs, chips, cards, buttons).
       Colors are either the brand blue (which reads on both the light and dark
       themes) or translucent neutrals (gray/blue at low alpha) that tint whatever
       background sits behind them, so a single rule set works in both themes
       without depending on a theme class Streamlit doesn't expose. The scientific
       scanpath plot itself is untouched — only the surrounding UI is styled. */
    .stApp {
        --sps-accent: #1f77b4;
        --sps-accent-soft: rgba(31, 119, 180, 0.10);
        --sps-accent-border: rgba(31, 119, 180, 0.22);
        --sps-border: rgba(128, 128, 128, 0.22);
        /* UX-174 r2 — a row under the pointer (the dataset table). */
        --sps-hover-soft: rgba(128, 128, 128, 0.08);
        --sps-code-fg: #15639c;
        --sps-shadow-hover: 0 6px 18px rgba(31, 119, 180, 0.16);
        /* UX-145 — the page background, for the few surfaces that must be
           opaque (a sticky bar content scrolls under). Streamlit exposes no
           CSS variable for it on the main page, and prefers-color-scheme is
           the OS preference, not the theme picked in ⋮ → Settings. But
           Streamlit does set `color-scheme` on `.stApp` to match the active
           theme, and `light-dark()` resolves against it — so this follows a
           theme switch instantly, without a rerun. The two colors are
           `constants.APP_THEME` / `APP_THEME_DARK`'s backgroundColor, pinned
           by tests/test_theme.py. */
        --sps-page-bg: light-dark(#ffffff, #0e1117);
    }
    /* In dark mode the brand blue is too dark for badge text; brighten it.
       The app's theme is "Auto" (follows the OS) in the common case, so the OS
       preference and prefers-color-scheme agree here. */
    @media (prefers-color-scheme: dark) {
        .stApp { --sps-code-fg: #8fc7f5; }
    }

    /* UX-7 empty-state panels — "no trials match" and "this corpus isn't here
       yet". Both used to be a warning banner + a caption + a body paragraph +
       a button: four blocks, three background colors, one message. They are now
       a single amber-tinted card, so the diagnosis visibly belongs to the
       headline above it. Amber (not red) on purpose: nothing is broken, the user
       just has to choose something. */
    .st-key-empty_state_panel,
    .st-key-dataset_unavailable_panel {
        background: rgba(240, 173, 78, 0.09);
        border-color: rgba(240, 173, 78, 0.42) !important;
        border-radius: 0.6rem;
    }
    .st-key-empty_state_panel [data-testid="stHeading"] h4,
    .st-key-dataset_unavailable_panel [data-testid="stHeading"] h4 {
        margin-top: 0;
        padding-top: 0;
        font-weight: 700;
    }
    /* The per-filter Clear buttons sit in a right-hand column; keep them quiet
       so the primary "Clear all filters" stays the obvious escape hatch. */
    .st-key-empty_state_panel div[class*="st-key-clear_one_filter_"] button {
        padding: 0.15rem 0.5rem;
        min-height: 1.9rem;
        font-size: 0.8rem;
    }

    /* Page title: a restrained brand-blue gradient + tighter tracking. One <h1>
       exists (st.title in the header), so this scopes cleanly to it. */
    [data-testid="stHeading"] h1 {
        background: linear-gradient(95deg, #1f77b4 0%, #4a9fd4 70%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
        font-weight: 800;
        letter-spacing: -0.015em;
    }
    /* Section headings (### / st.subheader) — a touch heavier and tighter. */
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3 { font-weight: 700; letter-spacing: -0.005em; }

    /* Tabs: hover affordance, bolder labels, brand-tinted active label. */
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0.25rem; }
    [data-testid="stTab"] {
        padding: 0.45rem 0.85rem;
        border-radius: 8px 8px 0 0;
        transition: background 0.15s ease, color 0.15s ease;
    }
    [data-testid="stTab"]:hover { background: var(--sps-accent-soft); }
    [data-testid="stTab"] p { font-weight: 600; }
    [data-testid="stTab"][aria-selected="true"] p { color: var(--sps-accent); }

    /* Inline code chips (Trial / Participant / Text ids, etc.) -> clean pill
       badges. `:not(pre code)` leaves multi-line code blocks (e.g. the BibTeX in
       the About popover) alone. */
    [data-testid="stMarkdownContainer"] code:not(pre code) {
        background: var(--sps-accent-soft);
        border: 1px solid var(--sps-accent-border);
        border-radius: 6px;
        padding: 0.05rem 0.4rem;
        font-weight: 600;
        color: var(--sps-code-fg);
    }

    /* Expander / bordered-container cards: rounder corners + a subtle hover lift.
       Covers the in-page expanders (Annotations, Trial metadata, Export) and the
       rail's grouped layer sections. The former sidebar group cards are gone —
       those groups are menu popovers now. */
    [data-testid="stExpander"] details {
        border: 1px solid var(--sps-border);
        border-radius: 10px;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    [data-testid="stExpander"] details:hover {
        border-color: var(--sps-accent-border);
        box-shadow: var(--sps-shadow-hover);
    }
    [data-testid="stExpander"] summary { font-weight: 600; border-radius: 10px; }

    /* Buttons: smooth hover with a slight lift + brand-blue glow. Scoped to real
       buttons, so the app-wide "animation: none" rules (which target plot/element
       containers, not buttons) don't apply. */
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"] {
        transition: transform 0.12s ease, box-shadow 0.15s ease,
                    border-color 0.15s ease, background 0.15s ease;
    }
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        transform: translateY(-1px);
        box-shadow: var(--sps-shadow-hover);
    }

    /* === Scanpath screen: condition chips + control rail ====================
       The viz controls moved out of the sidebar into a rail beside the plot, so
       the trial's key experiment conditions ride above the plot as a compact
       chip table and the rail reads as a tidy inspector panel. */
    /* UX-190 / UX-195 — the chips as a table, in place of the wrapping chip
       strip (UX-11): one column per field and one row per reading — Compare's
       A above B, with a value they share written in both rows, quieter, so
       what differs stands out. A header label, and a text value at its
       spaces, wrap only once the table would otherwise be wider than its
       column; past that the table scrolls sideways (with a scrollbar that
       stays drawn) rather than push the plot down. The selectors are long on purpose — they must
       beat the table styles Streamlit's markdown gives every table. */
    .sps-chip-table-wrap {
        overflow-x: auto;
        margin: 0.1rem 0 0.5rem;
    }
    /* macOS hides an overlay scrollbar until you scroll, so a table wider than
       its column read as clipped columns, not as one to scroll. Styling the
       scrollbar keeps it drawn whenever the table overflows. */
    .sps-chip-table-wrap::-webkit-scrollbar,
    .st-key-dataset_table_grid::-webkit-scrollbar {
        height: 6px;
    }
    .sps-chip-table-wrap::-webkit-scrollbar-thumb,
    .st-key-dataset_table_grid::-webkit-scrollbar-thumb {
        background: color-mix(in srgb, currentColor 30%, transparent);
        border-radius: 3px;
    }
    .sps-chip-table-wrap::-webkit-scrollbar-track,
    .st-key-dataset_table_grid::-webkit-scrollbar-track {
        background: transparent;
    }
    /* Firefox has no ::-webkit-scrollbar (and Chrome ignores those rules once
       the standard properties are set, hence the guard). */
    @supports not selector(::-webkit-scrollbar) {
        .sps-chip-table-wrap,
        .st-key-dataset_table_grid {
            scrollbar-width: thin;
        }
    }
    /* #374 F11 — and an edge shadow on the side that has more, so a cut
       column reads as "scroll" even where scrollbars are hidden. The two
       `local` covers scroll with the content and hide each shadow at its
       end; the two `scroll` shadows stay at the edges. */
    .sps-chip-table-wrap,
    .st-key-dataset_table_grid {
        background:
            linear-gradient(to right, var(--sps-page-bg) 40%, transparent) left / 2rem 100% no-repeat local,
            linear-gradient(to left, var(--sps-page-bg) 40%, transparent) right / 2rem 100% no-repeat local,
            radial-gradient(farthest-side at 0 50%, rgba(128, 128, 128, 0.35), transparent) left / 0.7rem 100% no-repeat scroll,
            radial-gradient(farthest-side at 100% 50%, rgba(128, 128, 128, 0.35), transparent) right / 0.7rem 100% no-repeat scroll;
    }
    /* The table spans its column, like the trial rows above it, rather than
       ending a third of the way across a wide window; the browser shares the
       extra width out between the columns. Its text is the selectors' size,
       and its headers their labels' (2026-10-07). */
    .sps-chip-table-wrap table.sps-chip-table {
        width: 100%;
        margin: 0;
        border: none;
        border-collapse: collapse;
        font-size: 0.875rem;
        line-height: 1.45;
        color: inherit;
    }
    .sps-chip-table-wrap table.sps-chip-table th,
    .sps-chip-table-wrap table.sps-chip-table td {
        padding: 0.28rem 0.55rem;
        border: none;
        border-bottom: 1px solid var(--sps-border);
        background: transparent;
        text-align: left;
        vertical-align: middle;
        white-space: nowrap;
        font-weight: 500;
    }
    .sps-chip-table-wrap table.sps-chip-table thead th {
        padding-top: 0;
        vertical-align: bottom;
        white-space: normal;
        font-size: 0.8125rem;
        font-weight: 600;
        line-height: 1.25;
        color: color-mix(in srgb, currentColor 62%, transparent);
    }
    /* Values never wrap: each reading is one line (2026-10-07), so a long
       trial id ("l37_1129 · 2_2_1_Adv") no longer doubles its row's height.
       A table too wide for its column scrolls sideways instead. */
    .sps-ct-tint {
        white-space: nowrap;
        display: inline-block;
        padding: 0 0.45rem;
        border-radius: 999px;
    }
    .sps-chip-table-wrap table.sps-chip-table tbody tr:last-child > * {
        border-bottom: none;
    }
    .sps-chip-table-wrap table.sps-chip-table th.sps-ct-side {
        padding-left: 0;
        font-weight: 700;
    }
    .sps-chip-table-wrap table.sps-chip-table .sps-ct-num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .sps-chip-table-wrap table.sps-chip-table td.sps-ct-same,
    .sps-chip-table-wrap table.sps-chip-table td.sps-ct-missing {
        font-weight: 400;
        color: color-mix(in srgb, currentColor 62%, transparent);
    }
    .sps-ct-dot {
        display: inline-block;
        width: 0.6rem;
        height: 0.6rem;
        margin-right: 0.4rem;
        border-radius: 50%;
        vertical-align: 0.02em;
    }
    /* UX-42: Data source and Filter by share a row but are separate tasks (and
       separate tour targets). A quiet rule makes that boundary legible; the
       inset keeps the Filter-by label from sitting directly against it. */
    .st-key-tour_grp_narrow_by {
        box-sizing: border-box;
        border-left: 1px solid var(--sps-border);
        padding-left: 0.7rem;
    }
    /* UX-68 — the Animate / Compare split buttons. Python puts the mode toggle
       and its ▾ settings trigger on one row (`tabs.render_single_trial_tab`);
       these rules are what make the two read as ONE control rather than as a
       switch that happens to have a button parked beside it.

       The outline goes on the row, not on either half, because the halves are
       different kinds of thing: Streamlit's toggle is a bare switch + label with
       no chrome of its own, and only the popover trigger arrives as a bordered
       button. So the row draws the border and the radius, `overflow: hidden`
       clips the button's square corners back to it, and the button gives up
       everything that would read as a second control — its own border, its
       radius, its background — keeping only a 1px left edge as the divider
       between the halves. That divider is the whole visual claim: one control,
       two things you can press.

       `align-items: stretch` is what makes the divider span the full height
       instead of floating as a short dash beside the switch; it overrides the
       `vertical_alignment="center"` the container is built with, which is still
       right for the no-CSS fallback.

       Shrinking the button is not cosmetic. Streamlit's default popover trigger
       is ~55px wide around a 16px glyph, and the widest of the two toggles is
       ~137px against a ~195px rail — with the default the row fits by about
       3px, and anything that nudges either half (a longer label, a wider rail
       font) wraps the ▾ onto its own line. At a glyph's width there is room to
       spare. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"] {
        width: 100%;
        max-width: 100%;
        min-height: 2.7rem;
        align-items: stretch !important;
        border: 1px solid var(--sps-border);
        /* A rounded rectangle, not a pill — it is what the Zoom control being
           copied actually is, and a 999px radius on the wrapped two-line state
           turns into a lozenge. */
        border-radius: 0.6rem;
        padding-left: 0.55rem;
    }
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stElementContainer"] {
        display: flex;
        align-items: center;
    }
    /* ENG-43: Streamlit 1.62's native `wrap=False` now owns the one-line
       contract. CSS only allocates the flexible and fixed halves. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:not(:has([data-testid="stPopover"])) {
        min-width: 0;
        flex: 1 1 auto;
        padding-right: 0.35rem;
    }
    /* UX-153 — a rail row with no switch (Filters & highlights, 📐 Figure & canvas) is
       one control, so its name opens the popover. The ▾ trigger's click target
       is stretched over the whole row by an `::after` overlay, which keeps the
       row's look, and the popover still anchors on the ▾ itself. The row is
       the overlay's containing block, so nothing between it and the button
       may be positioned. `transform: none` matters for the same reason:
       the app-wide hover lift (`translateY(-1px)`) would make the button
       the containing block mid-hover, shrinking the overlay out from under
       the pointer. The rows with a switch don't get this: their name is the
       switch's label and flips it, as on Animate and Compare. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_rail_"]:not(
            :has([data-testid="stCheckbox"])
        ) {
        position: relative;
    }
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_rail_"]:not(
            :has([data-testid="stCheckbox"])
        ) [data-testid="stPopover"] button {
        position: static !important;
        transform: none !important;
    }
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_rail_"]:not(
            :has([data-testid="stCheckbox"])
        ) [data-testid="stPopover"] button::after {
        content: "";
        position: absolute;
        inset: 0;
    }
    /* ...and the whole row lights up on hover, not only the ▾ half, since
       the whole row is what a click opens. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_rail_"]:not(
            :has([data-testid="stCheckbox"])
        ):has([data-testid="stPopover"] button:hover:enabled) {
        background: var(--sps-accent-soft);
    }
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stWidgetLabel"] p,
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stMarkdownContainer"] p {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* #374 F19 — the picker and rail-switch names are bold here, not as `**`
       in the label string: Streamlit reads a label verbatim as the widget's
       accessible name, so the markdown was announced. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p,
    .st-key-data_source_picker [data-testid="stWidgetLabel"] p,
    .st-key-single_trial_id [data-testid="stWidgetLabel"] p,
    .st-key-single_compare_trial [data-testid="stWidgetLabel"] p,
    .st-key-cmp_dataset [data-testid="stWidgetLabel"] p {
        font-weight: 600;
    }
    /* UX-153 — every toggle in these rows takes `wrap=True`, which switches
       off Streamlit's truncate mode (and the native `title=` tooltip it
       stamps), and with it the `min-width: 0` chain that let the label
       shrink to an ellipsis. Both are put back here. The `p *` arm is for a
       bold label's <strong>, which must not wrap "Raw gaze" onto two lines in
       a row that is one line by contract. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stWidgetLabel"] p * {
        white-space: nowrap;
    }
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stCheckbox"],
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stCheckbox"] label,
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stWidgetLabel"],
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stWidgetLabel"] [data-testid="stMarkdownContainer"] {
        min-width: 0;
        max-width: 100%;
    }
    /* UX-102 — and the same `p` must give up its bottom margin, or the row
       grows a scrollbar. Streamlit 1.62 gives every `wrap=False` horizontal
       container `overflow-x: auto`, and CSS then promotes `overflow-y` from
       `visible` to `auto` along with it: each row is a scroll box, so anything
       that overhangs it by a pixel shows a scrollbar on hover. A markdown `p`
       carries `margin-bottom: 1rem` that Streamlit cancels with a matching
       negative margin on `stMarkdownContainer` — which fixes the layout but not
       `scrollHeight`, and the margin still counts there. So exactly the three
       name-only sections (📄 Stimulus · Filters & highlights · 📐 Figure & canvas, the ones
       drawn with a name instead of a switch) scrolled 8px and lost 11px of
       width to the scrollbar's gutter, while the five with a toggle did not.
       Zeroing both margins is the fix rather than `overflow: visible`, because
       it removes the overhang instead of hiding it — the row keeps the
       horizontal clipping Streamlit put there. Nothing moves: the label is
       centerd by the flex row either way. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stMarkdownContainer"],
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stMarkdownContainer"] p {
        margin-bottom: 0;
    }
    /* The divider is drawn on the popover's SLOT — the row's own child — and not
       on the button, which is the obvious place and does not work. A trigger
       given `help=` is wrapped by Streamlit in a tooltip chain
       (stPopover > div > div > stTooltipIcon > stTooltipHoverTarget > button),
       every link of which sizes to the glyph, so a border on the button renders
       as an 18px dash floating in a 24px row rather than as a seam. Stretching
       that whole chain means naming emotion classes; the slot is already
       full-height because it is a flex child of the row. `:has()` picks it out
       without depending on `stLayoutWrapper` being the wrapper's name. */
    /* The corner rounding is on the slot rather than clipped off the row with
       `overflow: hidden`, and the row is left free to WRAP. Both were tried the
       other way and both are traps: the switch will not shrink below about
       131px (its own min-content), so on a 142px rail a non-wrapping row put the
       ▾ 38px past the right edge, where `overflow: hidden` deleted it — a
       control that silently cannot be reached. Wrapping costs a rounded box with
       the ▾ tucked under the switch, which reads more like a card than a split
       button; that is the right way to lose. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"]) {
        display: flex;
        align-items: center;
        justify-content: stretch;
        /* 2.6rem, not 2.8: at a 1280px window the rail's longest layer name,
           "Word boxes", missed by 2px (round 9) — the ▾ needs no more. */
        flex: 0 0 2.6rem;
        min-width: 2.6rem;
        border-left: 1px solid var(--sps-border);
        border-radius: 0 0.6rem 0.6rem 0;
    }
    /* Streamlit wraps a helped popover trigger in several glyph-sized divs.
       Stretch that chain too; widening only the outer slot leaves the actual
       click target at the chevron's width. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"]) [data-testid="stPopover"],
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"]) [data-testid="stPopover"] > div,
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"]) [data-testid="stTooltipIcon"],
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"]) [data-testid="stTooltipHoverTarget"] {
        display: flex;
        width: 100%;
        height: 100%;
    }
    /* Target the popover's own button, never `… button`: the toggle's label
       carries Streamlit's `?` help icon, which is also a button and would
       otherwise be restyled along with it. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stPopover"] button {
        min-width: 100% !important;
        min-height: 100% !important;
        height: 100% !important;
        width: 100% !important;
        padding: 0 0.65rem !important;
        border: 0 !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    /* UX-200: `box-shadow: none` above also took Streamlit's focus ring, so a
       keyboard user tabbing along the rail lost track of which ▾ was focused.
       An outline instead, inset because the row is a scroll box (UX-102) that
       would clip one drawn outside the button, in the accent the dataset
       table's rows already focus with. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        [data-testid="stPopover"] button:focus-visible {
        outline: 2px solid var(--sps-accent);
        outline-offset: -2px;
    }
    /* The hover tint goes on the slot too, so the whole half lights up to the
       seam instead of only the glyph's own box. `:has(button:hover:enabled)`
       rather than `:hover` keeps a disabled ▾ inert — it is disabled exactly
       when its mode is off, and a hover response would promise a menu that,
       while it does open, is entirely grayed. */
    [data-testid="stHorizontalBlock"][class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"] button:hover:enabled) {
        background: var(--sps-accent-soft);
    }
    /* UX-27 / CMP-10 — ONE button shape for the control rows stacked above the
       plot. They are built in three different functions across two modules
       (the Narrow-by/More row and the chip strip's Details/✏️ in tabs.py, the
       comparison picker's ◀ ▶ ⇅ in tabs.py, and the main trial picker's ◀ ▶ ⇅
       in utils.py), each with its own `st.columns` and its own width unit, so
       they used to render at different heights and two different shapes —
       square icon buttons beside pill-shaped labeled ones.
       Rather than hand-tuning each call site, every trigger in the block goes in
       a container keyed `railbtn_*` and takes its geometry from here.

       The shape is the chip pill (it was already tuned to sit against the chip
       strip, and it is the smallest of the three, so adopting it shrinks the
       cluster rather than growing it). `min-width` is what squares up the
       icon-only buttons: without it ◀, ▶ and ⇅ each collapse to their own glyph
       width. */
    [class*="st-key-railbtn_"] button {
        min-height: 0 !important;
        min-width: 2.3rem;
        padding: 0.1rem 0.65rem !important;
        border-radius: 999px !important;
        font-size: 0.9rem !important;
        line-height: 1.55 !important;
        white-space: nowrap;
    }
    /* Right-pack every cluster, at one spacing. Each row ends in a trailing
       column that already stops at the container's right edge, but a Streamlit
       vertical block is a flex COLUMN of full-width children, so a content-width
       button sat at the LEFT of its slot: the three rows' ends were ragged by up
       to 43px, and once the right-most three were flushed the *second* control
       in each row (◀ ▶, "Summary stats") was still adrift — one full column gutter in
       from its neighbour, at a different offset per row.

       So a row's trailing controls now share ONE `railbtn_*` container and this
       rule makes every such container a right-packed flex row. "More" alone,
       both ◀ ▶ ⇅ picker clusters, and the chip row's ✏️ therefore all end on the
       same edge with the same 3px between neighbours, whatever each row's own
       column split is. Nesting is intentional (`_trail` > `_step`): the outer cluster
       fixes the display order, and the inner containers let a trigger be *filled*
       out of order — the sort popover has to run before the ◀ ▶ it precedes in
       the DOM. */
    [class*="st-key-railbtn_"] {
        flex-direction: row;
        justify-content: flex-end;
        align-items: center;
    }
    /* Streamlit gives each child of a vertical block `width: 100%`, so in a flex
       ROW every child claims the container's full width and the group overflows
       to the LEFT instead of packing to the right — `width: auto` is what makes
       each one content-sized. The 3px between neighbours is a margin, not the
       container's `gap`: Streamlit's own two-class `.stVerticalBlock.st-emotion-*`
       gap rule outranks a single attribute selector, so `gap` here computes to
       0 and the pill outlines butt into one double-thick line. */
    [class*="st-key-railbtn_"] > div {
        flex: 0 0 auto !important;
        width: auto !important;
    }
    [class*="st-key-railbtn_"] > div + div { margin-left: 3px !important; }
    /* UX-181: the floors under the `SELECTOR_ROW_GRID` tracks
       (`SELECTOR_ROW_FLOORS_REM`). A row of this grid is a column row whose
       last column holds a `railbtn_*` cluster directly (◀ ▶ ⇅ 🔎 on the trial
       rows, ◀ ▶ on the screen navigator, ✏️ on the chip strip). The nested
       `_step` / `_sort` containers don't count.
       - Every column gets `min-width: 0` first. Otherwise a column's automatic
         minimum is its content, and A's dataset cell (dropdown + "+") stopped
         at a different width than B's, so the two rows drifted apart.
       - Then each track gets the same floor on every row: the dataset track on
         any row of three or four columns, the trial track on four-column rows
         only (on a three-column row the second column is trial + scrubber
         merged), and the actions track wherever it is. A column holding its
         floor leaves the rest of the shrinking to the columns beside it, so
         the tracks still share their edges.
       - The row stays on one line, compressing (the scrubber gives first,
         down to `SELECTOR_SCRUB_MIN_REM`), while its own width holds every
         floor (`SELECTOR_ROW_WRAP_REM`). Narrower than that — the
         plot-controls rail open beside a small window — it wraps: the tracks
         that no longer fit (the screen picker with ⇅ 🔎 ✏️, then ◀ ▶) move to
         a line of their own under the rest. It used to be held on one line at
         any width, and then ran past its column into the rail, over
         *Animate*. The test is a container query on the row's own wrapper, not
         the window: the rail takes a share of the window, and a flex wrap
         alone would break the line before shrinking the scrubber. A's row and
         B's have the same floors, so they wrap at the same width.
       On the column rules, `:where()` keeps the row match at zero specificity,
       so each floor outranks the `min-width: 0`. The `flex-wrap` rules keep
       their specificity, since they have to outrank Streamlit's own. */
    @media (min-width: 640px) {
        [data-testid="stLayoutWrapper"]:has(> [data-testid="stHorizontalBlock"]
            > [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > [class*="st-key-railbtn_"]) {
            container-type: inline-size;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]
            > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
            > [class*="st-key-railbtn_"]) {
            flex-wrap: nowrap;
        }
        @container (max-width: __SELECTOR_ROW_WRAP__) {
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]
                > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
                > [class*="st-key-railbtn_"]) {
                flex-wrap: wrap;
                row-gap: 0.5rem;
            }
            /* On a line of its own, the screen tail is never wider than the
               row: its floor gives way, and the screen picker and ⇅ 🔎 ✏️
               inside it wrap too. Doubled class match, so it outranks the
               tail's own one-line rule below. */
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(
                > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
                > [class*="_row_tail"]) {
                min-width: min(__SELECTOR_SCREEN_FLOOR__, 100%);
            }
            [class*="_row_tail"][class*="_row_tail"] {
                flex-wrap: wrap !important;
                row-gap: 0.5rem;
            }
        }
        :where([data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]
            > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
            > [class*="st-key-railbtn_"])) > [data-testid="stColumn"] {
            min-width: 0;
        }
        :where([data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]
            > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
            > [class*="st-key-railbtn_"])):has(> [data-testid="stColumn"]:nth-child(3))
            > [data-testid="stColumn"]:first-child {
            min-width: __SELECTOR_FLOOR_0__;
        }
        :where([data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]
            > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
            > [class*="st-key-railbtn_"])):has(> [data-testid="stColumn"]:nth-child(4))
            > [data-testid="stColumn"]:nth-child(2) {
            min-width: __SELECTOR_FLOOR_1__;
        }
        [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > [class*="st-key-railbtn_"]) {
            min-width: __SELECTOR_FLOOR_3__;
        }
        /* A trial row with a screen cell splits its actions: ◀ ▶ stay by the
           slider on a narrow track of their own, and the row's last track
           (`SELECTOR_SCREEN_TRACK`) holds the screen dropdown + ◀ ▶ followed by
           ⇅ 🔎 ✏️ (`utils.row_tail`). Both tracks keep the same floor on A's
           row and B's, so the two rows line up. Later than the actions floor
           above, which they override. */
        [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > [class*="_trail_steps"]) {
            min-width: __SELECTOR_STEPS_FLOOR__;
        }
        [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > [class*="_row_tail"]) {
            min-width: __SELECTOR_SCREEN_FLOOR__;
        }
    }
    [class*="_row_tail"] {
        flex-wrap: nowrap !important;
    }
    /* One width on both rows (`SELECTOR_SCREEN_PICKER_REM`), so B's screen
       picker lines up under A's and its ⇅ 🔎 under A's; it only gives way
       when the track is narrower than that. */
    [class*="_row_tail"] > [data-testid="stLayoutWrapper"]:has([class*="screen_picker"]) {
        flex: 0 1 __SELECTOR_SCREEN_PICKER__ !important;
        min-width: 0 !important;
    }
    /* Its own control keeps the label and value on one line; the value
       ellipsises rather than wrapping the cell taller. */
    [class*="_screen_cell"] {
        flex-wrap: nowrap !important;
    }
    [class*="_screen_cell"] > [data-testid="stElementContainer"] {
        flex: 1 1 0 !important;
        width: auto !important;
        min-width: 0 !important;
    }
    /* UX-181: a slider's end labels stay on one line. The trial scrubber's
       labels are `1/24 · <trial id>`, and a long id used to wrap onto a second
       line under the slider, where the chip strip below covered it. Each label
       takes at most half the bar and ellipsises past that. The thumb's own
       value above the track still shows the full id, and so does the
       dropdown. */
    [data-testid="stSliderTickBar"] > [data-testid="stMarkdownContainer"] {
        min-width: 0;
        max-width: 50%;
    }
    [data-testid="stSliderTickBar"] > [data-testid="stMarkdownContainer"] p {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* UX-9: the number box paired with each slider (`<key>__num`, `__num_lo`,
       `__num_hi`) exists for typing an *exact* value — the slider beside it
       already handles stepping. It holds a number, not a sentence, so drop the
       +/- buttons, cap its width and tighten its padding: it sits on the same
       line as the slider and must not steal the row. */
    div[class*="st-key-"][class*="__num"] [data-testid="stNumberInputStepUp"],
    div[class*="st-key-"][class*="__num"] [data-testid="stNumberInputStepDown"] {
        display: none !important;
    }
    div[class*="st-key-"][class*="__num"] [data-testid="stNumberInputContainer"] {
        min-width: 0;
        max-width: 5rem;
    }
    div[class*="st-key-"][class*="__num"] input {
        padding-left: 0.4rem !important;
        padding-right: 0.2rem !important;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }

    /* UX-51 — the rail's `label | field` rows. Every control in the rail and in
       its ⚙️/🧹 popovers used to stack its title ABOVE its field, so one style
       panel ran well past a screen. The title now sits in a column to the LEFT
       of the field. The split itself is built in Python (controls._labeled, one
       `st.columns` per row) precisely so it does not depend on Streamlit's own
       label DOM; all this rule set owns is how the title TEXT behaves inside the
       column we made for it.
       It must never wrap — a two-line title would push its own field down and
       undo the compaction — so it truncates instead, and hands the full text to
       the browser's native hover title. That title is also where the `?` tooltip
       went: the help text is appended to it, which buys back the icon's width on
       every row. Scoped to our own class name, so it cannot reach any other
       widget label in the app. */
    /* UX-53: a wizard topic heading. It replaced a per-topic expander, so it has
       to read as a divider *and* cost about one line — hence the rule above it
       rather than padding around it. Not an `<h4>`: the Data page keeps its four
       stage headings as the only h3/h4s (#UX-52). */
    .sps-wiz-section {
        /* UX-90: the bottom margin was 0.15rem, which Streamlit's own negative
           block gap ate entirely — the heading and the first control's label
           overlapped. A heading has to clear what it names. */
        margin: 0.85rem 0 0.6rem;
        padding-top: 0.55rem;
        border-top: 1px solid rgba(128, 128, 128, 0.22);
        font-weight: 600;
        font-size: 0.95rem;
        line-height: 1.4;
    }
    .sps-flabel {
        display: block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        /* Match the widget labels this replaced (see the VIZ-2 block below). */
        font-size: 0.92rem;
        line-height: 1.4;
    }
    /* A row whose title carries help. The dotted underline is the only remaining
       hint that there is something to hover, now that the `?` icon is folded
       into the title itself. */
    /* UX-158 — a row's caption inside a titled group of rows (`controls._sub_row`):
       the group's title leads the first row, and each row's own caption is
       quieter so the title still reads as the heading of the run. */
    .sps-fsub {
        font-size: 0.85rem;
        opacity: 0.72;
    }
    /* UX-158/159 — a rail popover's rows (`controls._popover_rows`), a little
       further apart than the app-wide gap:0 (the later rule wins the tie). */
    div[class*="st-key-rail_rows_"] { gap: 0.5rem !important; }
    .sps-flabel-help {
        text-decoration: underline dotted;
        text-decoration-color: rgba(128, 128, 128, 0.6);
        text-underline-offset: 3px;
        cursor: help;
    }
    /* UX-113 — a title that should stand out among plainer field titles on the
       same screen (the upload wizard's own table titles: Fixations, Words/IA,
       Raw gaze, Participant/Trial metadata). Bolder and a touch larger than
       the ordinary `.sps-flabel`, short of a full heading. */
    .sps-flabel-emph {
        font-weight: 700;
        font-size: 1.05rem;
    }
    /* UX-129 — the wizard's "Metadata" sub-heading (over the Participants /
       Trials / Texts rows) shares `.sps-flabel-emph` with the Fixations /
       AOI / Raw gaze table titles above it, which made it read as a fourth
       table name rather than the section label for the three below it.
       Confined to the left (name) column in wizard.py and centered within
       it here, rather than the full row — this heading belongs with the
       titles underneath it, not the wide mapping side. Bolder and a size up
       from `.sps-flabel-emph` itself (not down) and in the app's accent
       color: it introduces three titles at once, so it reads as *more*
       prominent than any one of them, not less. The tooltip re-centers with
       it so it still opens under the (now centered) text. */
       A prefix match, not the exact class: the ✏️ Edit dataset screen draws the
       same three rows under the same heading (`wiz_map_meta_heading_edit` — a
       key may be used once per run, and the offscreen editor is built even
       while the wizard is open). */
    [class*="st-key-wiz_map_meta_heading"] .sps-flabel-emph {
        font-weight: 800;
        font-size: 1.2rem;
        letter-spacing: 0.02em;
        color: var(--sps-accent);
    }
    [class*="st-key-wiz_map_meta_heading"] .sps-fhelp,
    [class*="st-key-wiz_map_meta_heading"] .sps-flabel {
        text-align: center;
    }
    [class*="st-key-wiz_map_meta_heading"] .sps-fhelp::after {
        left: 50%;
        transform: translateX(-50%);
    }
    /* …and the tooltip it opens. Deliberately NOT the browser's native `title=`
       (UX-51 shipped that first): a native tooltip waits about a second, which
       reads as broken when every row in a dense form keeps its description
       there. This one opens in 120 ms — the same feel as the `?` icons
       Streamlit draws elsewhere, which sit on Base Web's 200 ms default.
       The wrapper is what carries `position: relative`, because `.sps-flabel`
       itself is `overflow: hidden` for the ellipsis and would clip its own
       tooltip. Painted below-left of the title, non-interactive, and animated on
       `opacity` alone so it never takes part in layout or intercepts a click. */
    .sps-fhelp {
        position: relative;
        display: block;
        max-width: 100%;
    }
    /* BUG-91: the box exists only while it is shown. It used to sit there at
       `opacity: 0` all the time, and an absolutely-positioned box still counts
       towards its scroll container's overflow — so a long tooltip on a popover's
       last rows let the popover scroll down into empty space. `content: none`
       removes the box outright; the fade is an animation that starts once it is
       created, not an opacity transition on a box that is always there. */
    .sps-fhelp::after {
        content: none;
        position: absolute;
        top: calc(100% + 0.3rem);
        left: 0;
        z-index: 1000;
        width: max-content;
        max-width: 17rem;
        padding: 0.35rem 0.55rem;
        border-radius: 0.5rem;
        background: rgba(38, 39, 48, 0.96);
        color: #fafafa;
        font-size: 0.78rem;
        font-weight: 400;
        line-height: 1.35;
        white-space: normal;
        text-align: left;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28);
        pointer-events: none;
    }
    .sps-fhelp:hover::after,
    .sps-fhelp:focus-within::after {
        content: attr(data-tip);
        animation: sps-tip-in 80ms linear 120ms both;
    }
    @keyframes sps-tip-in {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* UX-53 round 3 — the wizard's descriptive prose is hover-only, so it reuses
       the tooltip above. Two adjustments for this context: the carrier is a
       heading or a short chip rather than a full-width field label, so it hugs
       its text instead of filling the row; and it needs a visible cue that
       something is there, which in the rail is supplied by the neighbouring `?`
       affordance and here is not. */
    .sps-wiz-section .sps-fhelp,
    .sps-wiz-part .sps-fhelp,
    .sps-wiz-note .sps-fhelp {
        display: inline-block;
        max-width: none;
        text-decoration: underline dotted;
        text-decoration-color: rgba(128, 128, 128, 0.55);
        text-underline-offset: 3px;
        cursor: help;
    }
    .sps-wiz-note {
        margin: 0.1rem 0 0.5rem;  /* UX-90 */
        font-size: 0.86rem;
        opacity: 0.85;
    }
    .sps-wiz-note a { text-decoration: none; }

    /* UX-53 round 8 — a wizard part's headline. The two parts are linear, so
       this labels rather than navigates: one line, a numbered chip, and a rule
       to separate it from the part above. Heavier than `.sps-wiz-section` (its
       topics sit *inside* a part) and lighter than a real heading, since the
       page already has its own. */
    .sps-wiz-part {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin: 1rem 0 0.6rem;  /* UX-90 — same collision as the section rule */
        padding-top: 0.6rem;
        border-top: 2px solid rgba(128, 128, 128, 0.28);
        font-weight: 700;
        font-size: 1.02rem;
        letter-spacing: 0.01em;
    }
    .sps-wiz-part-n {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.35rem;
        height: 1.35rem;
        border-radius: 999px;
        background: rgba(128, 128, 128, 0.22);
        font-size: 0.8rem;
        font-weight: 700;
    }
    /* UX-113 — `_FOOTER_ROW_W`'s compact desktop ratio (1.4 : 1.4 : 8 rest,
       matching the ✕ Cancel width elsewhere) gives each button column too few
       pixels to keep "Download setup file" / "Add dataset" on one line, at any width
       (not only a mobile one — the ratio itself is the problem). Streamlit
       sets each `stColumn`'s own `flex: 1 1 calc(<share>% - Npx)` via a real
       stylesheet class (not inline), so a bare `min-width` floor doesn't just
       clamp the final size — the flex-grow redistribution the browser then
       runs (still 1 for every column) hands the two button columns most of
       the row instead. Pinning the button columns to a fixed,
       ungrowing/unshrinking `flex-basis` sidesteps that fight, but leaving
       the empty third (`_rest`) column flexible then wraps it onto an
       invisible second line (an empty flex item, `flex-wrap`'s default) —
       harmless (zero height) but it pads the row with dead space below the
       buttons. Collapsing `_rest` to zero instead avoids that: three fixed
       widths always fit the first line, so nothing wraps. `!important`
       because these override Streamlit's own stylesheet `flex`. */
       A prefix match, not `.st-key-wizard_footer_row`: the ✏️ Edit dataset
       screen wears this same footer under its own key
       (`wizard_footer_row_edit`, since the offscreen editor and an open wizard
       can both exist in one run and two containers may not share a key), and
       the two screens' last rows have to line up to the pixel. */
    [class*="st-key-wizard_footer_row"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }
    [class*="st-key-wizard_footer_row"] [data-testid="stColumn"]:nth-of-type(1),
    [class*="st-key-wizard_footer_row"] [data-testid="stColumn"]:nth-of-type(2) {
        flex: 0 0 12.5rem !important;
        width: 12.5rem !important;
        min-width: 12.5rem !important;
    }
    [class*="st-key-wizard_footer_row"] [data-testid="stColumn"]:nth-of-type(3) {
        flex: 0 0 0 !important;
        width: 0 !important;
        min-width: 0 !important;
        padding: 0 !important;
    }
    /* UX-113 — real breathing room around the footer's own divider, on both
       sides: Streamlit's default `st.divider()` margin reads as barely more
       than the mapping blocks' own tight `.sps-wiz-blockgap` hairline, which
       undersells that this line is the boundary before the page's one commit,
       not another block gap. */
    [class*="st-key-wizard_footer_divider"] hr {
        margin-top: 1.25rem !important;
        margin-bottom: 1.5rem !important;
    }

    /* The dataset name leads the wizard and names the whole thing, so it is set
       larger than an ordinary field rather than looking like the first of them.
       Its label is the part's own title, so the box gets the room under that
       title a label would have taken — it sat pressed against it. */
    .st-key-wiz_name_box { margin-top: 1rem; }
    .st-key-wiz_name_box input {
        font-size: 1.05rem;
        font-weight: 600;
        padding-top: 0.55rem;
        padding-bottom: 0.55rem;
    }
    .st-key-wiz_name_box label p { font-weight: 700; }

    /* UX-119 — a wizard table upload's "👁️ Preview" trigger + its row/column
       count caption pack together with no gap, the same trick `railbtn_*`
       uses: turn the container into a packed flex ROW and let the trigger
       hug its own content instead of Streamlit's default one-child-per-row,
       full-width stacking. `st.columns` was tried first and rejected — a
       ratio-based column reserves its ratio's share of the row regardless of
       its content's own `width="content"` sizing, which is what left a gap
       between an icon-sized button and the caption a whole column over.
       UX-123: this container is now also the narrow `wiz_map_upload_*` name
       column (UX-122), so the count caption — the last child, whether or not
       the trigger rendered before it — wraps onto its own line(s) instead of
       overflowing: `flex: 1 1 auto; min-width: 0` lets it shrink below its
       one-line width, which is what lets it wrap at all. */
    [class*="st-key-wiz_upload_stats_"] {
        flex-direction: row;
        flex-wrap: wrap;
        align-items: flex-start;
    }
    [class*="st-key-wiz_upload_stats_"] > div:first-child {
        flex: 0 0 auto !important;
        width: auto !important;
    }
    [class*="st-key-wiz_upload_stats_"] > div:last-child {
        flex: 1 1 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    [class*="st-key-wiz_upload_stats_"] > div:last-child p {
        white-space: normal !important;
    }
    [class*="st-key-wiz_upload_stats_"] > div + div {
        margin-left: 0.35rem !important;
    }

    /* UX-122 — each Fixations/AOI/Raw gaze row's own uploader sits where the
       row's plain name label used to; a thin rule (not the full column gap
       either side of it) marks it off from the field-mapping pickers that
       follow. UX-125: `st.columns(vertical_alignment="center")` centers the
       *column*, not the stack of title/uploader/caption inside it against
       the block's full height — and that column is only row 1's own height,
       shorter than the uploader itself, so centering it was a no-op. The
       uploader now floats free of row 1 entirely: `wiz_map_block_*`
       (`fix_block`/`words_block`/raw gaze's own `s3`, wrapping row 1 + row 2
       + the keep-picker) is the positioning parent, and the upload column is
       an absolutely-positioned overlay spanning and centering against that
       *whole* block — row 1's own first cell stays reserved (unchanged
       width, so the pickers beside it don't move) but empty, since its
       content now lives in the overlay instead. The border-right rides
       along for the full block height as a side effect, reading as one
       continuous divider rather than just row 1's own short one. */
    /* UX-127: before any file is uploaded, row 1's remaining cells (the
       picker columns — nothing to map yet) are empty, and the uploader that
       used to hold row 1's own height now lives in an absolutely-positioned
       overlay (see below) that contributes nothing to normal flow. Left
       alone the block collapsed to a few px of padding, and the overlay's
       `overflow: hidden` then clipped the title + Browse-files button down
       to that same sliver — the "looks awful when closed" bug. A min-height
       covering the title + collapsed dropzone (measured ~54px) keeps the
       block, and so the overlay it sizes itself against, tall enough to
       show the uploader whole even with nothing uploaded yet — measured at
       ~92px (title + the collapsed-instructions dropzone), rounded up with
       a little breathing room.
       UX-129: 104px -> 128px — the overlay centers its content
       (`justify-content: center`) against the *whole* block height, and the
       title + collapsed dropzone measure ~96px on their own, so 104px left
       only ~2px above the title and ~6px below the button: close enough to
       read as the title being cut off at the top of its block, not merely
       "close to the edge". 128px leaves a real ~16px on each side. */
    [class*="st-key-wiz_map_block_"] {
        position: relative;
        min-height: 128px;
    }
    [class*="st-key-wiz_map_upload_"] {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        /* UX-127: widened from 9% to match `_MAP_ROW_W`/`_META_ROW_W`'s own
           widened first cell in wizard.py (0.09 -> 0.135) — the Browse-files
           button didn't fit at 9%. */
        width: 13.5%;
        border-right: 1px solid rgba(128, 128, 128, 0.3);
        /* UX-129: 0.5rem -> 0.65rem, paired with wizard.py's `_MAP_ROW_W`
           (and its row-2/meta siblings) widening from 0.135 to 0.155 — that
           gives the divider room on the picker side, this gives it room on
           the upload side, so the line no longer reads as glued to either
           the Browse-files button or the first mapping field. */
        padding-right: 0.65rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        overflow: hidden;
    }
    /* UX-129 — the title's own `.sps-fhelp` tooltip (the row's `emphasis=True`
       title, e.g. "Fixations") lives inside this same `overflow: hidden` box,
       so its `::after` popup got clipped to the ~13.5%-wide column the
       moment it tried to render past that edge — cut off mid-sentence
       instead of floating over the mapping fields like every other tooltip
       on the page. `overflow: hidden` still has to stay the *default* here
       (it is what keeps the native dropzone/Browse-files button from
       spilling into the mapping columns at this width — see UX-127 above),
       so this only lifts it while the tooltip itself is open, via `:has()`,
       rather than removing it outright. */
    [class*="st-key-wiz_map_upload_"]:has(.sps-fhelp:hover),
    [class*="st-key-wiz_map_upload_"]:has(.sps-fhelp:focus-within) {
        overflow: visible;
    }
    /* UX-147 — a metadata row (Participants / Trials / Texts, on ➕ Add and
       ✏️ Edit alike) is one row, so its upload column needs no overlay to
       span the block: it is the row's own first column. Left absolute, the
       column was only as tall as the id + keep pickers beside it, and an
       attached file (chip + preview + row counts) outgrew it — centering then
       pushed the title above the top edge, where `overflow: hidden` cut it
       off. In normal flow the row grows to fit instead. `overflow-x: clip`
       keeps UX-127's guard against the dropzone spilling sideways without
       clipping vertically (`hidden` on one axis would force the other to
       scroll); the column stretches so the divider still runs the row's full
       height. */
    [class*="st-key-wiz_map_upload_meta_"] {
        position: static;
        width: auto;
        height: 100%;
        overflow-x: clip;
        overflow-y: visible;
    }
    [data-testid="stColumn"]:has([class*="st-key-wiz_map_upload_meta_"]) {
        align-self: stretch;
    }
    /* UX-124 — the "5GB per file • CSV, TSV, …" line `st.file_uploader`
       prints under its own dropzone doesn't fit this width; the same
       information now reaches the title's hover tooltip instead (appended to
       `help_text` in wizard.py). */
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileUploaderDropzoneInstructions"] {
        display: none;
    }
    /* UX-124 — the uploaded-file chip is sized for a full-width column; in
       this ~9%-wide one it clipped outright rather than shrinking (its
       `stFileChips` wrapper has its own `overflow: hidden`, so the chip's
       natural ~140px width just got cut, delete button and all). Shrink the
       icon and the delete button, tighten the chip's own padding, and let it
       use the column's full width instead of a fixed one — the filename
       stays truncated with an ellipsis (`stFileChipName` already carries the
       untruncated name as a native `title=`, so hovering shows it in full,
       no extra work needed there). */
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChips"] {
        width: 100%;
        overflow: visible;
    }
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChip"] {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        padding: 0.15rem 0.25rem !important;
        gap: 0.25rem !important;
        box-sizing: border-box !important;
    }
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChip"] svg {
        width: 11px !important;
        height: 11px !important;
    }
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChipName"] {
        font-size: 0.7rem !important;
        max-width: 100% !important;
    }
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChipDeleteBtn"] button {
        width: 1rem !important;
        min-width: 1rem !important;
        height: 1rem !important;
        padding: 0 !important;
    }
    [class*="st-key-wiz_map_upload_"] [data-testid="stFileChipDeleteBtn"] svg {
        width: 10px !important;
        height: 10px !important;
    }

    /* UX-62 r2 — the header wordmark. `st.logo`'s only sizing control is
       small/medium/large, and even `large` leaves it small beside the nav, in a
       link that carries its own padding. So the height is set here instead, and
       the wrapper's spacing zeroed — "get rid of the white margins around it".

       The other half of that margin was baked into the PNG (36 px either side,
       24% of the canvas) and was cropped out of the file itself; CSS cannot
       reach inside an image. Sized in `rem` so it tracks the browser's text
       size rather than pinning to one display. */
    [data-testid="stLogo"] {
        height: 2.75rem !important;
        max-height: none !important;
        width: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        object-fit: contain;
    }
    [data-testid="stLogoLink"] {
        margin: 0 !important;
        padding: 0 !important;
        display: inline-flex;
        align-items: center;
    }
    /* The spacer Streamlit reserves beside the logo assumes the default height;
       with a taller mark it leaves a gap the nav then starts after. */
    [data-testid="stLogoSpacer"] { display: none !important; }

    /* UX-66 — the add-dataset screen's one permanent row: title, guide, docs
       link, cancel. It stays put while the page scrolls.

       `top` clears Streamlit's own header strip, which occupies the top of the
       viewport — without it the row slides *under* the nav rather than resting
       below it. The background is opaque so the fields scrolling beneath do not
       show through, and the z-index keeps it over them.

       Scoped to this container's key: only the wizard gets a sticky bar, not
       every page.

       The sticky element is the bar's `stLayoutWrapper`, not the keyed block
       itself: a sticky box only travels inside its parent, and the wrapper is
       exactly the bar's height, so a sticky *bar* scrolled away with the page. */
    /* DATA-35 — the ✏️ Edit dataset screen wears the add-dataset screen's bar,
       because the ask was that the two look the same. Same rule, two keys. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-dataset_editor_bar),
    [data-testid="stLayoutWrapper"]:has(> .st-key-wiz_sticky_bar) {
        position: sticky;
        top: 3.2rem;
        z-index: 60;
    }
    .st-key-dataset_editor_bar,
    .st-key-wiz_sticky_bar {
        background: var(--sps-page-bg);
        padding: 0.35rem 0 0.4rem;
        margin-bottom: 0.2rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.25);
    }
    .sps-wiz-title {
        font-size: 1.35rem;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* "get rid of all white spaces and margins at the top and bottom" — the
       page's own padding, and the gap Streamlit leaves under the last block. */
    .st-key-data_setup_page > div:first-child { margin-top: 0 !important; }
    .st-key-data_setup_page > div:last-child { margin-bottom: 0 !important; }

    /* UX-55 — a sub-group heading inside a wizard section (AOI features, Raw
       gaze features). Lighter and tighter than the bold markdown it replaced:
       the section above it already carries the weight, and these only need to
       separate one table's fields from the next. */
    .sps-wiz-subhead {
        margin: 0.5rem 0 0.1rem;
        padding-top: 0.35rem;
        border-top: 1px solid rgba(128, 128, 128, 0.18);
        font-weight: 600;
        font-size: 0.88rem;
        opacity: 0.85;
    }

    /* UX-57 — the Word box heading. It labels a group (a format radio plus a
       row of four coordinates), so it is set like the other group headings
       rather than like a field label, and its description is on hover. */
    .sps-box-title {
        font-weight: 600;
        font-size: 0.95rem;
        margin: 0.2rem 0 0.15rem;
    }

    /* UX-53 r15 — the table name at the head of an identity row. It labels the
       line once so the three field titles beside it need not each repeat it,
       and it sits on the titles' baseline rather than the controls'. */
    .sps-id-row-name {
        padding-bottom: 0.3rem;  /* UX-90 — clear of the fields it names */
        font-weight: 700;
        font-size: 0.9rem;
        opacity: 0.85;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* UX-55 r2 — the same name column on the geometry rows, sitting on the
       selects' baseline (their own titles are stacked above them). */
    .sps-geo-row-name { padding-bottom: 0.45rem; }

    /* UX-92 — the ✨ flag is a button while its row is amber (pressing it is
       the "I chose this" that a same-value re-pick cannot report). It has to
       keep reading as the icon it replaced: no chrome, no button box, no width
       of its own — only the pointer and a lift on hover say it is pressable. */
    [class*="st-key-"][class*="_cell_confirm"] button {
        min-height: 0;
        padding: 0;
        border: none;
        background: none;
        line-height: 1.2;
    }
    [class*="st-key-"][class*="_cell_confirm"] button:hover {
        background: none;
        transform: translateY(-1px);
    }
    [class*="st-key-"][class*="_cell_confirm"] button p { font-size: 0.95rem; }

    /* UX-89 — the hairline between the Fixations block and the AOI block (and,
       since UX-113, every other block boundary in stage 3: filename-derive vs.
       Fixations, Raw gaze vs. whatever sits above it). The mapping is grouped
       by *table* now (each table's identity row and its feature row together),
       so the only thing separating two blocks is this: one line, deliberately
       fainter and far tighter than `st.divider`, whose margins would
       reintroduce the vertical cost the page keeps fighting. UX-113 gave it
       more room underneath, so the line reads as a clear break between blocks
       rather than sitting glued to the one below it. */
    .sps-wiz-blockgap {
        border-top: 1px solid var(--sps-line, rgba(128, 128, 128, 0.22));
        margin: 0.55rem 0 1rem;
    }

    /* AN-32 — the Corpus Analysis page with no reading measures to show: its
       sections, drawn as a grayed tab strip so what it offers stays visible. */
    .sps-corpus-off {
        display: flex;
        gap: 1.5rem;
        margin-top: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--sps-line, rgba(128, 128, 128, 0.22));
        opacity: 0.45;
        pointer-events: none;
        user-select: none;
    }

    /* UX-113 — the filename-derive row's Apply button: a gentle tint of the
       app's own accent (the same tokens the code chips and tab hover use),
       not the loud filled `primary` blue reserved for the page's one commit
       (✅ Add dataset). */
    .st-key-wizard_filename_apply button {
        background: var(--sps-accent-soft);
        border-color: var(--sps-accent-border);
        color: var(--sps-accent);
    }
    .st-key-wizard_filename_apply button:hover {
        background: var(--sps-accent-border);
        border-color: var(--sps-accent);
        color: var(--sps-accent);
    }

    /* UX-72 — the two halves of the rail's Filters & highlights section. A rule and a
       small label: enough to group, cheap in height. (UX-74 briefly used this
       for every section's contents and was reverted — the sections read better
       with their `⚙️ …` popovers.) */
    .sps-rail-subhead {
        /* UX-191: above the rows' 0.9rem labels, so a block's title outranks
           its own fields instead of reading as a footnote to them. */
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        opacity: 0.8;
        /* More room above than below, so the label still reads as belonging to
           the block under it — but 0.15rem below put "🖥️ Screen & framing"
           almost on the baseline of the "Show full monitor" switch, which made
           the two look like one control. */
        margin: 0.8rem 0 0.45rem;
        padding-top: 0.4rem;
        border-top: 1px solid rgba(128, 128, 128, 0.28);
    }
    /* The first block in a section needs no rule — the expander's own header is
       the boundary. */
    [data-testid="stExpander"] [data-testid="stVerticalBlock"]
        > div:first-child .sps-rail-subhead {
        border-top: none;
        padding-top: 0;
        margin-top: 0.1rem;
    }

    /* UX-71 — see `mapping_menu_css()` below: the option list is widened only
       on the two mapping surfaces, so this global sheet leaves dropdowns alone. */

    /* UX-138 — `constants.icon_html`: a Material Symbols glyph inside raw HTML,
       where a `:material/…:` shortcode is inert. Same font Streamlit loads for
       its own icons; the span's text is the ligature (the icon's name). */
    .sps-icon {
        font-family: "Material Symbols Rounded";
        font-weight: normal;
        font-style: normal;
        font-size: 1.2em;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        white-space: nowrap;
        direction: ltr;
        font-feature-settings: "liga";
        vertical-align: -0.2em;
        user-select: none;
    }
    /* UX-53 round 4 — the auto-detection flag beside a mapping row is the ✨ and
       nothing else; which column was detected is on its tooltip. The old inline
       sentence ("✨ auto-detected `CURRENT_FIX_INDEX`") ran wider than the
       select it annotated, on every row. */
    .sps-map-flag {
        display: inline-block;
        font-size: 0.85rem;
        line-height: 1;
        opacity: 0.75;
        cursor: help;
    }
    .sps-map-flag:hover { opacity: 1; }
    /* The tooltip is anchored to a one-glyph carrier at the right-hand edge of
       the row, so it opens leftwards rather than off the panel. */
    .sps-map-flag.sps-fhelp::after { left: auto; right: 0; }

    /* Data Management's read-only mappings use the same label-over-control
       grammar as Add dataset. The value is intentionally select-like without
       being a disabled widget: built-in schemas are informative, not editable. */
    .sps-readonly-map-table {
        margin: 0.65rem 0 0.2rem;
        padding-top: 0.35rem;
        border-top: 1px solid rgba(128, 128, 128, 0.18);
        font-weight: 700;
        font-size: 0.9rem;
        opacity: 0.85;
    }
    .sps-readonly-map-label {
        min-height: 1.35rem;
        margin-bottom: 0.2rem;
        font-size: 0.82rem;
        font-weight: 600;
        opacity: 0.88;
    }
    .sps-readonly-map-value {
        min-height: 2.4rem;
        display: flex;
        align-items: center;
        padding: 0.45rem 0.65rem;
        border: 1px solid var(--sps-border);
        border-radius: 0.5rem;
        background: rgba(128, 128, 128, 0.07);
        font-family: var(--sps-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
        font-size: 0.82rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .sps-readonly-map-note {
        margin-top: 0.2rem;
        font-size: 0.76rem;
        opacity: 0.72;
    }

    /* Control rail: set off from the plot by one hairline on its left edge, on
       the page's own background — UX-151 retired the tinted, bordered card,
       whose fill put a second surface behind rows that already carry their own
       outline. A hair more breathing room between the stacked toggles than the
       app-wide gap:0 rule. UX-173 keeps the controls in page flow, beside both
       the plot and its subtabs, so every control can use the space below the
       figure without a nested scrollbar. */
    .st-key-scanpath_rail {
        border-left: 1px solid var(--sps-border);
        padding: 0.1rem 0.35rem 1.5rem 1rem;
        box-sizing: border-box;
        /* UX-29: lets the Quick-view rule below query the rail's own rendered
           width, not the viewport's — the rail is a fraction of the row, so its
           width changes with the window without necessarily crossing a viewport
           breakpoint. (It used to swing with the sidebar opening and closing
           too; that is gone, but querying the rail is still the right test.) */
        container-type: inline-size;
        container-name: sps-rail;
    }
    .st-key-scanpath_rail div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    .st-key-scanpath_rail h5 { margin: 0.15rem 0 0.1rem; }
    /* Section dividers default to 32px top+bottom margin — far too airy for the
       narrow rail. Tighten them so the sections sit close together. */
    .st-key-scanpath_rail hr { margin: 0.5rem 0 !important; }
    /* The palette divider meets the first bordered layer card; leave a small
       extra pause so the rule and the Fixations border do not crowd together. */
    .st-key-scanpath_rail .st-key-palette_layers_divider {
        margin-bottom: 0.4rem !important;
    }
    /* Plot-rail triggers need enough height for their labels and switch tracks;
       the app-wide compact button treatment otherwise leaves them cramped. */
    .st-key-scanpath_rail .st-key-viz_view_scanpath button,
    .st-key-scanpath_rail .st-key-viz_view_heatmap button,
    .st-key-scanpath_rail .st-key-viz_view_illustration button,
    .st-key-scanpath_rail .st-key-viz_view_custom button {
        min-height: 2.6rem;
        padding-top: 0.25rem;
        padding-bottom: 0.25rem;
    }
    .st-key-scanpath_rail .st-key-reset_viz_settings_btn button {
        min-height: 3rem;
    }
    /* The rail is deliberately narrow — keep its short headers + toggle labels on
       one line so they don't break mid-word (e.g. "Anima\nte") when it's tight. */
    .st-key-scanpath_rail h5,
    .st-key-scanpath_rail [data-testid="stWidgetLabel"] p { white-space: nowrap; }
    /* Per-layer styling popovers + the comparison-styling expander: full-width,
       left-aligned triggers so the rail stays a clean single column. */
    .st-key-scanpath_rail [data-testid="stPopover"] button {
        width: 100%;
        justify-content: flex-start;
    }
    /* VIZ-31 layer groups (👁️ Scanpath / 📄 Stimulus / 🔥 Overlays / 🖥️ Canvas &
       text / 📐 Figure & canvas). Streamlit gives the expander label
       `word-break: break-word`, which in a rail this narrow snaps the header
       mid-word ("Scanpa\nth") — the same defect the nowrap rule above prevents
       for toggle labels. Break at spaces only, and give the label the row's
       spare width (the chevron is a fixed-size flex sibling, so the label needs
       `min-width: 0` to be allowed to use it). Trimmed side padding buys back
       ~16px, which is what keeps these headers on one line at real rail widths. */
    .st-key-scanpath_rail [data-testid="stExpander"] summary {
        padding-left: 0.35rem;
        padding-right: 0.35rem;
    }
    .st-key-scanpath_rail [data-testid="stExpander"] summary p {
        word-break: normal;
        overflow-wrap: normal;
        flex: 1 1 auto;
        min-width: 0;
    }
    /* A group's contents are inset 16px per side by default. Nesting the layer
       toggles one level deeper means that inset now comes out of an already
       narrow column — enough to clip the full-width popover triggers ("⚙️
       Fixation styl…") against the card edge. Give it back most of the width;
       the group's own border still reads as the grouping. */
    .st-key-scanpath_rail [data-testid="stExpanderDetails"] {
        padding-left: 0.4rem;
        padding-right: 0.4rem;
        padding-top: 0.1rem;
    }
    /* Design presets and Palette use the same quietly muted label treatment. */
    .sps-control-label {
        color: inherit;
        opacity: 0.72;
        font-size: 0.875rem;
        line-height: 1.4;
        margin-bottom: 0;
    }
    .st-key-scanpath_rail .st-key-global_palette [data-testid="stWidgetLabel"] {
        opacity: 0.72;
    }
    /* Give the heading a small breathing space, while keeping the 2×2 grid
       itself tighter than ordinary Streamlit column rows. */
    .st-key-scanpath_rail .st-key-quick_views_grid {
        margin-top: 0;
        padding-top: 0.45rem;
        margin-bottom: 0.05rem;
    }
    .st-key-scanpath_rail .st-key-quick_views_grid > [data-testid="stVerticalBlock"] {
        gap: 0.15rem !important;
    }
    /* VIZ-39 — 🎨 My designs. 💾 Save is drawn *into* the expander's own title
       bar: `design_shell` is the positioning context, and the header row's
       right-hand side is empty (the chevron sits left), so the list underneath
       keeps the full width of the rail instead of losing a fifth of it to one
       icon in a column of its own. */
    .st-key-scanpath_rail .st-key-design_shell {
        position: relative;
    }
    .st-key-scanpath_rail .st-key-design_save {
        position: absolute;
        top: 0.3rem;
        right: 0.4rem;
        width: auto !important;
        z-index: 3;
    }
    .st-key-scanpath_rail .st-key-design_save button {
        min-height: 1.9rem;
        padding: 0 0.4rem;
    }
    /* Keep the title itself clear of the button it now shares a line with. */
    .st-key-scanpath_rail .st-key-design_shell summary {
        padding-right: 2.4rem;
    }
    /* One saved design is one bordered card, not three loose buttons: the row's
       own container carries the border, and the controls inside it are borderless
       so the card reads as a single object. */
    .st-key-scanpath_rail [class*="st-key-design_row_"] {
        padding: 0.15rem 0.3rem;
        margin-bottom: 0.3rem;
        border-radius: 0.5rem;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stHorizontalBlock"] {
        gap: 0.1rem !important;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] button {
        min-height: 1.9rem;
        padding: 0.1rem 0.3rem;
        justify-content: center;
    }
    /* An icon-only button still carries the label's right margin, which is what
       pushes these two off-center. */
    .st-key-scanpath_rail [class*="st-key-design_row_"] button [data-testid="stIconMaterial"] {
        margin: 0 !important;
        font-size: 1.1rem;
    }
    /* ✏️ swaps the name for a field in the same slot, so the field has to end up
       the height of the button it replaces — otherwise the card grows by a
       third the moment you click, and the list shuffles under the cursor. The
       field is wrapped in a form (for ⏎), and every layer of that wrapping
       brings its own margin; measured in the browser, zeroing these four brings
       the editing card to 46px against the resting card's 45. */
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stForm"] {
        border: 0;
        padding: 0;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] > [data-testid="stLayoutWrapper"],
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stForm"] [data-testid="stElementContainer"],
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stForm"] [data-testid="stLayoutWrapper"] {
        margin-bottom: 0 !important;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stForm"] [data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stTextInput"] input {
        padding: 0.1rem 0.4rem;
        min-height: 1.9rem;
    }
    .st-key-scanpath_rail [class*="st-key-design_row_"] [data-testid="stTextInputRootElement"] {
        height: 2.1rem;
        min-height: 0;
    }
    /* The 2×2 Quick-view grid keeps full labels at ordinary rail widths and
       falls back to icons only at the narrowest size. UX-138: the label's own
       Material icon is what stays — the text collapses around it — so the
       fallback no longer re-draws each glyph from a `content:` rule.
       UX-194: the rail is a fifth of the row, and these queries measure its
       *content* box — 191px on a 1280px laptop — so the old 320px cut-off hid
       the names on any window narrower than ~1800px. The full-size label
       needs ~240px ("✎ Illustration", the longest, is 84px at 14px plus 12px
       padding a side); under that the buttons tighten (padding, gap, a point
       smaller: 75px), which holds one line down to ~175px. The icon fallback
       starts at 178px, a few pixels of slack for other platforms' fonts — a
       window under ~1220px. */
    @container sps-rail (max-width: 240px) {
        .st-key-quick_views_grid [data-testid="stHorizontalBlock"] {
            gap: 0.4rem !important;
        }
        .st-key-viz_view_scanpath button,
        .st-key-viz_view_heatmap button,
        .st-key-viz_view_illustration button,
        .st-key-viz_view_custom button {
            padding-left: 0.25rem;
            padding-right: 0.25rem;
        }
        .st-key-viz_view_scanpath button p,
        .st-key-viz_view_heatmap button p,
        .st-key-viz_view_illustration button p,
        .st-key-viz_view_custom button p {
            font-size: 0.8125rem;
            white-space: nowrap;
        }
    }
    @container sps-rail (max-width: 178px) {
        .st-key-viz_view_scanpath button p,
        .st-key-viz_view_heatmap button p,
        .st-key-viz_view_illustration button p,
        .st-key-viz_view_custom button p {
            font-size: 0;
        }
        /* A markdown `:material/…:` renders as `span[role="img"]` — the
           `stIconMaterial` test id is only on the `icon=` slot. */
        .st-key-viz_view_scanpath button p span[role="img"],
        .st-key-viz_view_heatmap button p span[role="img"],
        .st-key-viz_view_illustration button p span[role="img"],
        .st-key-viz_view_custom button p span[role="img"] {
            font-size: 1.1rem;
        }
    }
    /* BUG-24: the rail's heading row holds nothing but the heading. UX-44 put a
       compact Reset pill beside it in a second column, which did not fit — the
       rail is ~150px wide inside at ordinary desktop widths — so a container
       query stacked the two below 240px. That rule set `flex-direction: column`
       without clearing Streamlit's `flex-wrap: wrap`, making the header a
       column-WRAPPING flex container: the Reset column wrapped into a second
       track ~100px to the RIGHT of the rail, which the rail's `overflow-y: auto`
       (`overflow-x` computes to `auto` with it) then clipped. Reset was
       invisible at every width but a zoomed-out one. It now sits at the foot of
       the rail (`plot_reset_footer`), full width like every other trigger there,
       so neither the two-column header nor the query that patched it remains.
       Keep the heading a single element: a second column here is what broke. */
    .st-key-plot_reset_footer { margin-top: 0.35rem; }

    /* ── Accessibility (WCAG AA) ──────────────────────────────────────────
       Streamlit renders captions as theme-text-color at opacity 0.6, which on
       the #f5f7fa panels measures 4.07:1 — below the 4.5:1 AA threshold. Lift
       to 0.72 (~5.5:1 in light, still well-clear in dark). Theme-safe: the
       underlying color is each theme's own text color, so dark mode stays
       readable rather than getting a hardcoded gray. */
    div[data-testid="stCaptionContainer"] { opacity: 0.72 !important; }

    /* Multiselect placeholder text ("All texts", "Choose options", …) is
       BaseWeb's theme-text at 0.6 alpha → 4.07:1, same sub-AA problem as the
       caption. Fix it the same theme-agnostic way: take the full-strength theme
       text color (`inherit`) and mute it with opacity to 0.72 (~5.5:1) — works
       in whichever theme is active, unlike a hardcoded color. The selector
       hits only the placeholder (the div following the search input); once
       chips replace it there's no match, so selected tags keep their color. */
    [data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input) + div {
        color: inherit !important;
        opacity: 0.72 !important;
    }

    /* Section headers now use proper heading levels so screen-reader users get
       a valid outline (no h1→h5 jump): the rail/export sections are <h2>, their
       sub-sections <h3>. Pin the visual size back to the original compact look
       (by Streamlit's stable text-derived ids) so the layout is unchanged.
       BUG-88: the rail's heading is pinned by its container key instead. The
       text-derived id folds an icon's name into it, so UX-138's Material icon
       turned the id `plot-controls` into `tune-plot-controls` — the pin stopped
       matching and the heading fell back to Streamlit's 36px h2, which the
       narrow rail wraps onto two lines. A heading that carries an icon has to
       be pinned by a key. */
    .st-key-plot_controls_header h2, #scope, #figures, #also-include {
        font-size: 20px !important; line-height: 24px !important;
        font-weight: 600 !important; padding: 6px 0 16px !important;
        /* In the narrow plot-side rail these can wrap; only ever break at a
           space, never mid-word ("Visualizatio↵n"). */
        word-break: normal !important; overflow-wrap: normal !important;
    }
    .st-key-plot_controls_header h2 {
        margin: 2.4px 0 1.6px !important;
        white-space: nowrap;
    }
    #this-trial, #multiple-trials {
        font-size: 24px !important; line-height: 28.8px !important;
        font-weight: 600 !important; padding: 8px 0 16px !important;
    }

    /* ── VIZ-2: nudge the smallest UI text up a little for readability ──────
       A gentle, uniform lift on the smallest *native* Streamlit text — captions,
       widget labels, radio / checkbox / toggle option labels, and help tooltips
       (the app's tiniest fonts). Kept modest (~+5-10%) and scoped to small text
       only, so the pinned header sizes and the dense-layout spacing rules above
       are untouched and no panel reflows. */
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        font-size: 0.92rem !important;
    }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {
        font-size: 0.92rem !important;
    }
    [data-baseweb="radio"] label,
    [data-testid="stCheckbox"] label,
    [data-testid="stExpander"] summary p,
    div[data-testid="stTooltipContent"] p {
        font-size: 0.92rem !important;
    }
    /* BUG-48 — a `help=` tooltip must never intercept a click. Streamlit's
       tooltip is a portalled panel whose open state lives in React, so it can
       outlive the hover that opened it; being an ordinary positioned element it
       then ate the next click that landed on whatever it covered, which is the
       likeliest reason a rail's ▾ sometimes did nothing on the first press.
       Safe because no `help=` in this app contains a link — every tooltip is
       read, never clicked. */
    div[data-testid="stTooltipContent"] {
        pointer-events: none;
    }
    /* BUG-86 — …and it is shown only while *its own* trigger is under the
       pointer or holds *keyboard* focus. Streamlit 1.64's trigger will not
       close on pointer-leave while focus is inside it, clicking a button puts
       focus there, and it can leave several panels in the page at once (some
       stuck half-closed) — so every button or popover with `help=` that was
       clicked (the ◀ ▶ ⇅ funnel row, the rail's ▾, the presets) kept its panel
       floating after the pointer moved on. `:hover` and `:focus-visible` are
       the browser's own bookkeeping, right even when no event reached React,
       and `:focus-visible` is what tells a keyboard user's focus, which should
       keep its tooltip, from the focus a click leaves behind, which should not.
       Two selectors, because CSS cannot relate a portalled panel to the
       trigger that owns it:
       · once `app._TOOLTIP_OWNER_SCRIPT` is running (its flag on `<html>`),
         a panel shows only while marked `[data-sps-tooltip-owned]` — its own
         trigger (the element whose `aria-describedby` names it) is hovered or
         keyboard-focused. That is what stops a hover on one button reviving
         every other stale panel, and a panel is judged before it is painted;
       · `body:not(:has(…))` hides every panel while no trigger at all is, the
         floor if that script cannot run.
       The hide is immediate: a delayed one (for a fade that Streamlit's own
       entrance animation, holding opacity at 1, never let run) flashed a stale
       panel for 100 ms. This replaced BUG-48/51's JavaScript sweeper, which
       waited for a Base Web `[data-baseweb="tooltip"]` layer that Streamlit no
       longer renders and so never closed anything;
       `tests/test_tooltip_visibility.py` fails if the DOM named here leaves
       Streamlit's bundle. */
    html[data-sps-tooltip-owners] [role="tooltip"]:not([data-sps-tooltip-owned]) :is([data-testid="stTooltipContent"], [data-testid="stTooltipErrorContent"]),
    body:not(:has(
        [data-testid="stTooltipHoverTarget"]:hover,
        [data-testid="stTooltipHoverTarget"] :focus-visible,
        [data-testid="stTooltipErrorHoverTarget"]:hover,
        [data-testid="stTooltipErrorHoverTarget"] :focus-visible
    )) :is([data-testid="stTooltipContent"], [data-testid="stTooltipErrorContent"]) {
        visibility: hidden;
    }

    /* ── UX-19: width breakpoints ────────────────────────────────────────────
       Every layout decision above was fixed-width — the only @media rule in this
       file was `prefers-color-scheme` — so on an ordinary laptop (a 13" screen,
       or a half-width window on a big display) the controls, chips and plot
       column crowded or overlapped. These target ≥1280px down to ~1024px.

       The scanpath plot itself needs nothing here: `tabs._render_true_scale_chart`
       renders at the figure's exact pixel size and CSS-scales the whole block
       *uniformly* to the column, capped at 1×. It only ever shrinks, and a
       uniform transform can't distort — so the true-to-scale guarantee holds at
       every width by construction. What actually broke is chrome: the chip strip
       (fixed by UX-11's wrapping strip), the rail's no-wrap labels, the header
       nav, and the page's generous side padding. */

    /* First: reclaim the page's horizontal padding, which is the cheapest way to
       give the plot + rail split more room before anything has to reflow. */
    @media (max-width: 1400px) {
        .stMainBlockContainer,
        section.main > div.block-container {
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        /* The pinned section-header sizes (see the heading-level rules above)
           are what push the narrow rail's headers to two lines first. */
        .st-key-plot_controls_header h2, #scope, #figures, #also-include {
            font-size: 18px !important; line-height: 22px !important;
        }
    }

    /* #374 F11 — the rail keeps a floor of 260px; the figure takes the rest
       (it scales uniformly, so a narrower plot column costs nothing but
       size). At a ⅕ share the rail fell to ~170px at 1024px, and its one-line
       rows (UX-153) cut every name to "An…", "Fi…". Only side by side: below
       640px Streamlit stacks the columns, and the rail is full width anyway.
       This replaces a ≤1200px rule that let rail labels wrap, which never
       took effect on the switch rows — UX-153 keeps those on one line. */
    @media (min-width: 640px) {
        [data-testid="stHorizontalBlock"]:has(
            > [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > .st-key-scanpath_rail
        ) {
            /* The floor would otherwise wrap the rail under the figure: the
               two flex bases (⅘ + 260px) no longer fit one line. */
            flex-wrap: nowrap;
        }
        [data-testid="stHorizontalBlock"]:has(
            > [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > .st-key-scanpath_rail
        ) > [data-testid="stColumn"]:first-child {
            min-width: 0;
        }
        [data-testid="stColumn"]:has(
            > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
            > .st-key-scanpath_rail
        ) {
            min-width: 260px;
        }
    }
    /* ...and where the floor bites, the 4rem gutter beside it gives 2.5rem
       back to the picker row above the figure. */
    @media (min-width: 640px) and (max-width: 1300px) {
        [data-testid="stHorizontalBlock"]:has(
            > [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
            > [data-testid="stLayoutWrapper"] > .st-key-scanpath_rail
        ) {
            column-gap: 1.5rem !important;
        }
    }
    @media (max-width: 1200px) {
        .st-key-scanpath_rail { padding-left: 0.6rem; padding-right: 0.6rem; }
        /* A button label must never break mid-word ("Scanp/ath"). */
        .st-key-scanpath_rail button p {
            word-break: normal;
            overflow-wrap: normal;
        }
        /* The typed boxes beside each slider (UX-9) give up width first — the
           slider is the primary control. */
        div[class*="st-key-"][class*="__num"] [data-testid="stNumberInputContainer"] {
            max-width: 4rem;
        }
    }

    /* Last resort at the bottom of the target range: nothing may overflow its
       container, even a long unbroken id or a translated label. */
    @media (max-width: 1024px) {
        .stMainBlockContainer,
        section.main > div.block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        .st-key-scanpath_rail [data-testid="stWidgetLabel"] p { overflow-wrap: anywhere; }
        /* A figure that somehow can't scale down far enough scrolls rather than
           being squeezed out of true scale (the one guarantee that must hold). */
        /* Match both iframe titles: Streamlit titles these "st.iframe" now,
           "components.html" on historical builds. */
        [data-testid="stElementContainer"]:has(iframe[title*="components.html"]),
        [data-testid="stElementContainer"]:has(iframe[title*="st.iframe"]) {
            overflow-x: auto;
            /* Without this, overflow-x alone makes the y axis auto as well. */
            overflow-y: hidden;
        }
    }
    </style>
    """
    for i in (0, 1, 3):
        css = css.replace(f"__SELECTOR_FLOOR_{i}__", selector_track_floor(i))
    css = (
        css.replace("__SELECTOR_SCREEN_FLOOR__", f"{SELECTOR_SCREEN_FLOOR_REM}rem")
        .replace("__SELECTOR_STEPS_FLOOR__", f"{SELECTOR_STEPS_FLOOR_REM}rem")
        .replace("__SELECTOR_SCREEN_PICKER__", f"{SELECTOR_SCREEN_PICKER_REM}rem")
        .replace("__SELECTOR_ROW_WRAP__", f"{SELECTOR_ROW_WRAP_REM:g}rem")
    )
    return css


def menu_width_css(widget_key: str, labels) -> str:
    """Open ``widget_key``'s dropdown as wide as its longest option.

    The menu is portalled to ``<body>`` and virtualized (see
    `mapping_menu_css`), so it cannot size itself to its content; it is given
    a width from the labels instead, never narrower than the control and never
    wider than the window. The rule keys on the open combobox: one menu is open
    at a time, and while this widget's input is expanded the menu is its own.
    """
    longest = max((len(str(label)) for label in labels), default=0)
    if not longest:
        return ""
    # ~0.58em a character in the app's sans, plus the menu's padding.
    want = f"{longest * 0.58 + 2.5:.1f}em"
    scope = f'body:has(.st-key-{widget_key} [aria-expanded="true"])'
    menu = 'div:has(> [role="listbox"])'
    return (
        f"<style>{scope} {menu} {{"
        f" width: max(var(--trigger-width, 0px), min({want}, 92vw)) !important;"
        " max-width: 92vw !important; }"
        f' {scope} {menu} [role="option"] {{ white-space: nowrap; }}</style>'
    )


def widen_menu(widget_key: str, labels) -> None:
    """Inject `menu_width_css` for ``widget_key`` (a style-only `st.html`,
    which takes no room in the layout)."""
    import streamlit as st

    css = menu_width_css(widget_key, labels)
    if css:
        st.html(css)


def selector_track_floor(index: int) -> str:
    """The CSS `min-width` of one `SELECTOR_ROW_GRID` track (UX-181).

    Shared by the app's rule and the loading skeleton's grid, so the skeleton
    draws the row the page is about to show.
    """
    floor = SELECTOR_ROW_FLOORS_REM[index]
    cap = SELECTOR_ROW_FLOOR_CAPS[index]
    if floor is None:
        return "0"
    if cap is None:
        return f"{floor}rem"
    return f"min({floor}rem, {cap}%)"


def mapping_menu_css() -> str:
    """UX-71 r3 — the option-list widening, for the mapping screens only.

    A mapping row packs four or five selects across, so the *control* is narrow
    by design and its dropdown inherits that width — and a clipped option is
    ambiguous, not just ugly, since two columns routinely share a visible prefix
    (``CURRENT_FIX_INTEREST_AREA_ID`` vs ``…_INDEX``).

    Two earlier attempts (UX-53 r14, UX-71 r1) failed for a reason neither
    recorded: they styled ``div[data-baseweb="popover"]``, and **Streamlit no
    longer renders a selectbox with BaseWeb**. It is a `react-aria` ComboBox
    whose list is portalled to ``<body>`` inside a popover div carrying the
    trigger's width as an *inline* style, next to a ``--trigger-width`` variable.
    Every rule aimed at the old markup matched nothing, which is why "wrap the
    option text" changed nothing on screen.

    Wrapping is also the wrong lever now: the list is **virtualized** (fixed row
    heights, absolutely positioned rows), so a two-line option would overlap its
    neighbour — and for the same reason ``width: max-content`` collapses back to
    the container's own width. The list has to be given a width, and it is
    given one relative to its trigger.

    **Why this is injected per screen rather than added to the global sheet**:
    the popover is portalled out of our DOM, so it cannot be scoped by an
    ancestor selector — a global rule would widen *every* dropdown in the app,
    including the plot rail's, which sits against the right edge of the window
    where a wider menu has nowhere to grow into. The mapping screens have no
    right rail, so there the extra width is free. Emitted by the add-dataset
    wizard and by the 🗂️ Data page's mapping editor, which are the two places a
    column name is the thing being read.
    """
    return """
    <style>
    div:has(> [role="listbox"]) {
        width: min(calc(var(--trigger-width, 12rem) + 9rem), 92vw) !important;
        max-width: 92vw !important;
    }
    div:has(> [role="listbox"]) [role="option"] {
        /* The row is as wide as the menu now, so the label has the room it
           needs; keep it on one line so the virtualizer's row height holds. */
        white-space: nowrap;
    }
    /* #374 F13 — a mapped column's chip wraps instead of being cut to a stub
       ("T…", "RECORDI…"): the mapping cells are a seventh of the row, less
       with the setup guide open, and the chip is the user's one check that the
       detection is right. Hovering still shows the full name (`title`). */
    [class*="st-key-col_map_"][class*="_cell"] {
        container-type: inline-size;
    }
    [class*="st-key-col_map_"][class*="_cell"] [data-tag] {
        height: auto;
        max-width: 100%;
    }
    [class*="st-key-col_map_"][class*="_cell"] [data-tag] > span[title] {
        white-space: normal;
        overflow-wrap: anywhere;
        text-overflow: clip;
        line-height: 1.25;
    }
    /* Narrow (the guide open, or a small window): the clear-all ⊗ goes — each
       chip has its own × — and the caret floats over the corner, so the chips
       get the cell's whole width rather than the third of it left beside two
       buttons. */
    @container (max-width: 190px) {
        [class*="st-key-col_map_"][class*="_cell"] [data-testid="stMultiSelect"]
            button[aria-label="Clear all"] {
            display: none;
        }
        [class*="st-key-col_map_"][class*="_cell"] [data-testid="stMultiSelect"]
            [role="group"] {
            position: relative;
        }
        [class*="st-key-col_map_"][class*="_cell"] [data-testid="stMultiSelect"]
            button[aria-label="Open"] {
            position: absolute;
            right: 0;
            top: 0.25rem;
        }
        [class*="st-key-col_map_"][class*="_cell"]
            [data-testid="stMultiSelectTagsContainer"] {
            flex: 1 1 100%;
            min-width: 0;
            padding-right: 1.1rem;
        }
        [class*="st-key-col_map_"][class*="_cell"] [data-tag] > span[title] {
            font-size: 0.8rem;
        }
    }
    </style>
    """
