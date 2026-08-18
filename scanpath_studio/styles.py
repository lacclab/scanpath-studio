"""CSS styles for the Scanpath Studio Streamlit app."""

from __future__ import annotations


def get_app_css() -> str:
    """Return custom CSS to reduce whitespace and disable animations."""
    return """
    <style>
    section.main > div.block-container {padding-top: 0.25rem; padding-bottom: 0.25rem;}
    /* Remove all whitespace around plotly charts */
    div[data-testid="stPlotlyChart"] {margin: 0 !important; padding: 0 !important; line-height: 0 !important;}
    div[data-testid="stPlotlyChart"] > div {margin: 0 !important; padding: 0 !important;}
    div[data-testid="stPlotlyChart"] iframe {display: block !important; margin: 0 !important; padding: 0 !important;}
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
    .st-key-top_menu {
        flex-wrap: wrap;
    }

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

    /* UX-63 — the Session and Help pages, when they are not the active entry.
       Same reasoning and same mechanism as the Data page above: the widgets
       inside must keep executing (the 🐛 Debug toggle *is* the debug gate, and
       the persistence pause toggle governs what is written to disk), and
       Streamlit drops the key of a widget that did not render. `display: none`,
       so they contribute no layout and the tour's `findVisible()` cannot aim at
       a hidden copy. */
    .st-key-session_menu_page_offscreen { display: none !important; }

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
    div[data-testid="stPopoverBody"] {
        min-width: min(28rem, 90vw);
        max-width: min(32rem, 95vw);
    }
    div[data-testid="stPopoverBody"] p { line-height: 1.45; }

    /* === Emphasised loading spinner ============================================
       The cache_data spinners ("Reading uploaded data…", "Normalizing data…", …)
       can run for a while on a large upload, so make them an unmissable pulsing
       banner instead of a small inline spinner. Blue tint + border reads on both
       the light and dark themes; the keyframes are scoped so the app-wide
       "animation: none" rules above don't kill the pulse or the spin. */
    div[data-testid="stSpinner"] {
        display: flex !important;
        align-items: center;
        gap: 0.9rem;
        width: 100%;
        box-sizing: border-box;
        padding: 1.2rem 1.5rem !important;
        margin: 0.7rem 0 !important;
        border-radius: 14px;
        border: 1px solid #185fa5;
        background: linear-gradient(90deg, #1f77b4, #3a8fd0 55%, #5aa9e6);
        box-shadow: 0 8px 24px rgba(31, 119, 180, 0.38);
        animation: sps-spinner-pulse 1.6s ease-in-out infinite !important;
    }
    /* white message text on the filled blue banner */
    div[data-testid="stSpinner"] p,
    div[data-testid="stSpinner"] div {
        font-size: 1.45rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.2px;
        color: #ffffff !important;
    }
    /* enlarge the spinning Material icon (sized by font-size; it spins natively) */
    div[data-testid="stSpinner"] [data-testid="stIconMaterial"] {
        font-size: 2.5rem !important;
        width: 2.5rem !important;
        height: 2.5rem !important;
        color: #ffffff !important;
    }
    @keyframes sps-spinner-pulse {
        0%   { box-shadow: 0 0 0 0 rgba(90, 169, 230, 0.6), 0 8px 24px rgba(31,119,180,0.38); }
        70%  { box-shadow: 0 0 0 16px rgba(90, 169, 230, 0.0), 0 8px 24px rgba(31,119,180,0.38); }
        100% { box-shadow: 0 0 0 0 rgba(90, 169, 230, 0.0), 0 8px 24px rgba(31,119,180,0.38); }
    }

    /* === Visual polish ==========================================================
       Tasteful, theme-robust chrome styling (header, tabs, chips, cards, buttons).
       Colors are either the brand blue (which reads on both the light and dark
       themes) or translucent neutrals (grey/blue at low alpha) that tint whatever
       background sits behind them, so a single rule set works in both themes
       without depending on a theme class Streamlit doesn't expose. The scientific
       scanpath plot itself is untouched — only the surrounding UI is styled. */
    .stApp {
        --sps-accent: #1f77b4;
        --sps-accent-soft: rgba(31, 119, 180, 0.10);
        --sps-accent-border: rgba(31, 119, 180, 0.22);
        --sps-border: rgba(128, 128, 128, 0.22);
        --sps-code-fg: #15639c;
        --sps-shadow-hover: 0 6px 18px rgba(31, 119, 180, 0.16);
    }
    /* In dark mode the brand blue is too dark for badge text; brighten it.
       The app's theme is "Auto" (follows the OS) in the common case, so the OS
       preference and prefers-color-scheme agree here. */
    @media (prefers-color-scheme: dark) {
        .stApp { --sps-code-fg: #8fc7f5; }
    }

    /* UX-7 empty-state panels — "no trials match" and "this corpus isn't here
       yet". Both used to be a warning banner + a caption + a body paragraph +
       a button: four blocks, three background colours, one message. They are now
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
       chip strip and the rail reads as a tidy inspector panel. */
    /* UX-11: the chip strip WRAPS. It used to be pinned to one line, clipping
       whatever didn't fit, with a "More" disclosure that re-listed every chip so
       the clipped ones stayed reachable — the same facts twice, because which
       chips fit is a live-width question Python can't answer. Wrapping means
       nothing is ever cut at any window width, so the duplicate list
       (and the whole floating-dropdown mechanism) is gone; the derived summary
       stats live in a real "Details" popover beside the strip instead. This is
       also the first half of UX-19 — the strip was what broke first on a narrow
       laptop. */
    .sps-trial-chips {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.35rem;
        margin: 0.1rem 0 0.5rem;
    }
    .sps-trial-chips .sps-chip { flex: 0 0 auto; }
    .sps-stat {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1.5rem;
        padding: 0.32rem 0;
        font-size: 0.9rem;
        line-height: 1.25;
        white-space: nowrap;
    }
    .sps-stat + .sps-stat { border-top: 1px solid rgba(0, 0, 0, 0.07); }
    .sps-stat-name { color: #6c757d; }
    .sps-stat-val { font-weight: 700; color: #212529; }
    .sps-chip {
        display: inline-flex;
        align-items: center;
        padding: 0.12rem 0.6rem;
        border-radius: 999px;
        font-size: 0.9rem;
        font-weight: 600;
        line-height: 1.55;
        /* Chip backgrounds are always light (set inline), so pin dark text so it
           stays readable in dark mode too. */
        color: #212529;
        border: 1px solid rgba(0, 0, 0, 0.06);
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
    [class*="st-key-split_mode_"] {
        width: fit-content;
        max-width: 100%;
        align-items: stretch !important;
        border: 1px solid var(--sps-border);
        /* A rounded rectangle, not a pill — it is what the Zoom control being
           copied actually is, and a 999px radius on the wrapped two-line state
           turns into a lozenge. */
        border-radius: 0.6rem;
        padding-left: 0.55rem;
    }
    [class*="st-key-split_mode_"] [data-testid="stElementContainer"] {
        display: flex;
        align-items: center;
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
    [class*="st-key-split_mode_"] > div:has([data-testid="stPopover"]) {
        display: flex;
        align-items: center;
        flex: 0 0 auto;
        border-left: 1px solid var(--sps-border);
        border-radius: 0 0.6rem 0.6rem 0;
    }
    /* Target the popover's own button, never `… button`: the toggle's label
       carries Streamlit's `?` help icon, which is also a button and would
       otherwise be restyled along with it. */
    [class*="st-key-split_mode_"] [data-testid="stPopover"] button {
        min-width: 0 !important;
        min-height: 0 !important;
        width: auto !important;
        padding: 0 0.3rem !important;
        border: 0 !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    /* The hover tint goes on the slot too, so the whole half lights up to the
       seam instead of only the glyph's own box. `:has(button:hover:enabled)`
       rather than `:hover` keeps a disabled ▾ inert — it is disabled exactly
       when its mode is off, and a hover response would promise a menu that,
       while it does open, is entirely greyed. */
    [class*="st-key-split_mode_"]
        > div:has([data-testid="stPopover"] button:hover:enabled) {
        background: var(--sps-accent-soft);
    }
    /* UX-27 / CMP-10 — ONE button shape for the control rows stacked above the
       plot. They are built in three different functions across two modules
       (the Narrow-by/More row and the chip strip's Details/✏️ in tabs.py, the
       comparison picker's ◀ ▶ ⇅ in tabs.py, and the main trial picker's ◀ ▶ ⇅
       in utils.py), each with its own `st.columns` and its own width unit, so
       they used to render at different heights and two different shapes —
       square icon buttons beside pill-shaped labelled ones.
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
       in each row (◀ ▶, "Details") was still adrift — one full column gutter in
       from its neighbour, at a different offset per row.

       So a row's trailing controls now share ONE `railbtn_*` container and this
       rule makes every such container a right-packed flex row. "More" alone,
       both ◀ ▶ ⇅ picker clusters, and Details + ✏️ therefore all end on the same
       edge with the same 3px between neighbours, whatever each row's own column
       split is. Nesting is intentional (`_trail` > `_step`): the outer cluster
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
    /* The two chip-strip controls — "Details" (summary stats) and ✏️ (edit
       chips) — are additionally nudged down onto the first chip row's baseline:
       the strip wraps, so the columns are TOP-aligned (a centred control would
       drift to the middle of a tall strip), and this offset is the strip's own
       top margin. (UX-11 also fixed the ✏️ sitting visibly high, when it was
       centred against a one-line strip. Its sideways `margin-left: -0.6rem` is
       gone as of UX-27 — it was the reason the pencil landed 9.6px short of the
       other two rows' right edges.) */
    .st-key-railbtn_chip_trail { margin-top: 0.1rem; }
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
        margin: 0.85rem 0 0.15rem;
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
    .sps-flabel-help {
        text-decoration: underline dotted;
        text-decoration-color: rgba(128, 128, 128, 0.6);
        text-underline-offset: 3px;
        cursor: help;
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
    .sps-fhelp::after {
        content: attr(data-tip);
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
        opacity: 0;
        transition: opacity 80ms linear;
    }
    .sps-fhelp:hover::after,
    .sps-fhelp:focus-within::after {
        opacity: 1;
        transition-delay: 120ms;
    }

    /* UX-53 round 3 — the wizard's descriptive prose is hover-only, so it reuses
       the tooltip above. Two adjustments for this context: the carrier is a
       heading or a short chip rather than a full-width field label, so it hugs
       its text instead of filling the row; and it needs a visible cue that
       something is there, which in the rail is supplied by the neighbouring `?`
       affordance and here is not. */
    .sps-wiz-section .sps-fhelp,
    .sps-wiz-note .sps-fhelp {
        display: inline-block;
        max-width: none;
        text-decoration: underline dotted;
        text-decoration-color: rgba(128, 128, 128, 0.55);
        text-underline-offset: 3px;
        cursor: help;
    }
    .sps-wiz-note {
        margin: 0.1rem 0 0.35rem;
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
        margin: 1rem 0 0.3rem;
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
    /* The dataset name leads the wizard and names the whole thing, so it is set
       larger than an ordinary field rather than looking like the first of them. */
    .st-key-wiz_name_box input {
        font-size: 1.05rem;
        font-weight: 600;
        padding-top: 0.55rem;
        padding-bottom: 0.55rem;
    }
    .st-key-wiz_name_box label p { font-weight: 700; }

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
       every page. */
    .st-key-wiz_sticky_bar {
        position: sticky;
        top: 3.2rem;
        z-index: 60;
        background: var(--background-color, #fff);
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

    /* UX-75 — the chip line's title cell: the reading this strip belongs to,
       on the strip's own first line. Bold but not loud, and clipped rather than
       wrapped — the title shares its row with a strip that wraps, and a title
       growing to two lines would push the chips down for no gain. */
    .sps-chip-title {
        font-weight: 700;
        font-size: 0.9rem;
        line-height: 1.6;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* UX-74 — a block inside a rail section, where a `⚙️ …` popover used to be.
       A rule and a small caps-ish label: enough to group, cheap in height (the
       rail is narrow and every section now shows its whole contents). */
    .sps-rail-subhead {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        opacity: 0.72;
        margin: 0.55rem 0 0.15rem;
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

    /* Control rail: a subtle card so it reads as a panel, with a hair more
       breathing room between the stacked toggles than the app-wide gap:0 rule.
       UX-43 gives it its own scroll area exactly as tall as the plot row: the
       subtabs live in the next row and can grow without stretching the rail. */
    .st-key-scanpath_rail {
        border: 1px solid var(--sps-border);
        border-radius: 12px;
        padding: 0.55rem 0.85rem 0.35rem;
        background: var(--sps-accent-soft);
        box-sizing: border-box;
        height: 100%;
        max-height: 100%;
        overflow-y: auto;
        /* Chain to the page once the rail hits either end (UX-43 shipped this as
           `contain`, which stopped the scroll dead there). Browsers latch a
           gesture to the element it started in, so the hand-off lands on the
           next wheel/flick rather than mid-gesture. */
        overscroll-behavior-y: auto;
        scrollbar-gutter: stable;
        /* UX-29: lets the Quick-view rule below query the rail's own rendered
           width, not the viewport's — the rail is a fraction of the row, so its
           width changes with the window without necessarily crossing a viewport
           breakpoint. (It used to swing with the sidebar opening and closing
           too; that is gone, but querying the rail is still the right test.) */
        container-type: inline-size;
        container-name: sps-rail;
    }
    /* Remove the rail from the row's intrinsic height calculation, then stretch
       it through the right column. The left (plot) column alone determines the
       row height; Streamlit's flex row gives the right column that same height. */
    [data-testid="stColumn"]:has(.st-key-scanpath_rail) {
        position: relative;
    }
    [data-testid="stColumn"]:has(.st-key-scanpath_rail)
        > [data-testid="stVerticalBlock"] {
        position: absolute;
        inset: 0;
    }
    [data-testid="stLayoutWrapper"]:has(> .st-key-scanpath_rail) {
        height: 100%;
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
    /* UX-29: the three Quick-view buttons ("👁️ Scanpath" / "🔥 Heatmap" / "✏️
       Illustration") wrap to 2-3 lines once the rail column narrows on a small
       window. Rather than
       widen the rail (shrinks the plot column) or drop to a 2×2 grid, fall back
       to the emoji alone: the label text is collapsed to zero size (so it takes
       no layout space) and a `::before` re-adds just the emoji at normal size —
       the row stays the same three-button layout at every width. */
    @container sps-rail (max-width: 320px) {
        .st-key-viz_view_scanpath button p,
        .st-key-viz_view_heatmap button p,
        .st-key-viz_view_illustration button p {
            font-size: 0;
        }
        .st-key-viz_view_scanpath button p::before,
        .st-key-viz_view_heatmap button p::before,
        .st-key-viz_view_illustration button p::before {
            font-size: 1rem;
        }
        .st-key-viz_view_scanpath button p::before { content: "👁️"; }
        .st-key-viz_view_heatmap button p::before { content: "🔥"; }
        .st-key-viz_view_illustration button p::before { content: "✏️"; }
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
       text colour (`inherit`) and mute it with opacity to 0.72 (~5.5:1) — works
       in whichever theme is active, unlike a hardcoded colour. The selector
       hits only the placeholder (the div following the search input); once
       chips replace it there's no match, so selected tags keep their colour. */
    [data-testid="stMultiSelect"] [data-baseweb="select"] div:has(> input) + div {
        color: inherit !important;
        opacity: 0.72 !important;
    }

    /* Section headers now use proper heading levels so screen-reader users get
       a valid outline (no h1→h5 jump): the rail/export sections are <h2>, their
       sub-sections <h3>. Pin the visual size back to the original compact look
       (by Streamlit's stable text-derived ids) so the layout is unchanged. */
    #plot-controls, #scope, #figures, #also-include {
        font-size: 20px !important; line-height: 24px !important;
        font-weight: 600 !important; padding: 6px 0 16px !important;
        /* In the narrow plot-side rail these can wrap; only ever break at a
           space, never mid-word ("Visualizatio↵n"). */
        word-break: normal !important; overflow-wrap: normal !important;
    }
    #plot-controls {
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
        #plot-controls, #scope, #figures, #also-include {
            font-size: 18px !important; line-height: 22px !important;
        }
    }

    /* Then: let the rail's labels wrap. They are `nowrap` above so short labels
       don't break mid-word in the rail's normal width — but below ~1200px the
       rail is narrow enough that no-wrap means the text simply runs out of the
       card. Wrapping at spaces (never mid-word) is the lesser evil, and is what
       keeps the AC's "no overlap or clipping" true. */
    @media (max-width: 1200px) {
        /* The `p *` arm matters: a bolded toggle label ("**Animate**") puts the
           text in a <strong> that Streamlit gives `overflow-wrap: anywhere`,
           which beats what this rule sets on the parent <p> — so without it the
           rail still broke "Anima/te" and "Com/pare" mid-word here. */
        .st-key-scanpath_rail h5,
        .st-key-scanpath_rail [data-testid="stWidgetLabel"] p,
        .st-key-scanpath_rail [data-testid="stWidgetLabel"] p * {
            white-space: normal;
            word-break: normal;
            overflow-wrap: normal;
        }
        .st-key-scanpath_rail { padding-left: 0.6rem; padding-right: 0.6rem; }
        /* A button label must never break mid-word ("Scanp/ath"). */
        .st-key-scanpath_rail button p {
            word-break: normal;
            overflow-wrap: normal;
        }
        /* Which leaves the two side-by-side Quick-view buttons: "Scanpath" and
           "Heatmap" are single words that can't wrap, and at half of a ~170px
           rail they don't fit — so that row stacks. Scoped to *that* row via
           :has(), NOT to every column row in the rail: the per-layer popovers'
           contents are rail DOM children even while closed, so a blanket rule
           would also stack UX-9's slider + number box back onto two lines. */
        .st-key-scanpath_rail
            [data-testid="stHorizontalBlock"]:has(.st-key-viz_view_scanpath) {
            flex-wrap: wrap;
        }
        .st-key-scanpath_rail
            [data-testid="stHorizontalBlock"]:has(.st-key-viz_view_scanpath)
            > [data-testid="stColumn"] {
            min-width: 100%;
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
        .st-key-scanpath_rail [data-testid="stWidgetLabel"] p,
        .sps-chip { overflow-wrap: anywhere; }
        /* A figure that somehow can't scale down far enough scrolls rather than
           being squeezed out of true scale (the one guarantee that must hold). */
        /* Match both iframe titles: Streamlit titles these "st.iframe" now,
           "components.html" on historical builds. */
        [data-testid="stElementContainer"]:has(iframe[title*="components.html"]),
        [data-testid="stElementContainer"]:has(iframe[title*="st.iframe"]) {
            overflow-x: auto;
        }
    }
    /* Once the layout is narrow enough to stack/reflow, a nested vertical
       scroller is more awkward than useful. Return the rail to document flow. */
    @media (max-width: 900px) {
        [data-testid="stColumn"]:has(.st-key-scanpath_rail) {
            position: static;
        }
        [data-testid="stColumn"]:has(.st-key-scanpath_rail)
            > [data-testid="stVerticalBlock"] {
            position: static;
        }
        [data-testid="stLayoutWrapper"]:has(> .st-key-scanpath_rail) {
            height: auto;
        }
        .st-key-scanpath_rail {
            height: auto;
            max-height: none;
            overflow-y: visible;
            overscroll-behavior-y: auto;
            scrollbar-gutter: auto;
        }
    }
    </style>
    """


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
    </style>
    """
