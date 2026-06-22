"""CSS styles for the Scanpath Studio Streamlit app."""

from __future__ import annotations


def get_app_css() -> str:
    """Return custom CSS to reduce whitespace and disable animations."""
    return """
    <style>
    section.main > div.block-container {padding-top: 0.5rem; padding-bottom: 0.5rem;}
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
    /* "About" popover in the header: pill-shaped trigger + readable body width */
    /* The button is content-sized (width="content") and sits in a narrow column;
       align it to the column's right edge so it lines up with the right edge of
       the page content. The `about_btn` wrapper is a flex column, so this only
       moves the About button — no other popover (e.g. the plot toolbar). */
    .st-key-about_btn, .st-key-share_btn { align-items: flex-end; }
    /* Lay Share + About side by side, right-aligned, with a small gap so the
       Share trigger sits just beside About instead of a column apart. */
    .st-key-header_buttons {
        flex-direction: row;
        justify-content: flex-end;
        align-items: center;
        gap: 0.5rem;
    }
    .st-key-header_buttons .st-key-share_btn,
    .st-key-header_buttons .st-key-about_btn { width: auto; }
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
       Covers the side-panel expanders (Annotations, Trial metadata, Export) and
       the sidebar group cards (Data source, Experimental Setup, Filter trials). */
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
    /* The chip strip stays on ONE line: it never wraps; the primary
       identity/condition chips clip at the row edge while the "?" help marker and
       the "More" disclosure are pinned and always visible. */
    .sps-trial-chips {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        gap: 0.35rem;
        margin: 0.1rem 0 0.5rem;
    }
    .sps-chips-primary {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        gap: 0.35rem;
        min-width: 0;
        flex: 0 1 auto;
        overflow: hidden;
    }
    .sps-chips-primary .sps-chip { flex: 0 0 auto; }
    .sps-chip-help, .sps-chip-more { flex: 0 0 auto; }
    /* "?" help marker → small round badge with a native hover tooltip. */
    .sps-chip-help {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.05rem;
        height: 1.05rem;
        border-radius: 50%;
        border: 1px solid rgba(0, 0, 0, 0.18);
        font-size: 0.72rem;
        font-weight: 700;
        color: #555;
        cursor: help;
    }
    /* Inline "More" disclosure: the chip-styled summary stays on the one-line
       strip; its body (the not-already-shown summary stats) opens as a floating
       dropdown so expanding it never reflows the chip row. */
    .sps-chip-more { display: inline-block; position: relative; }
    .sps-chip-more-summary {
        list-style: none;
        cursor: pointer;
        user-select: none;
        font-weight: 600;
    }
    .sps-chip-more-summary::-webkit-details-marker { display: none; }
    .sps-chip-more-summary::after { content: " ▾"; font-size: 0.7rem; }
    .sps-chip-more[open] .sps-chip-more-summary::after { content: " ▴"; }
    /* The "More" panel: a tidy key→value list of the summary stats, opened as a
       floating card so it never reflows the chip row. */
    .sps-chip-more-body {
        position: absolute;
        top: calc(100% + 0.3rem);
        right: 0;
        z-index: 20;
        display: flex;
        flex-direction: column;
        min-width: 13rem;
        padding: 0.3rem 0.65rem;
        background: var(--background-color, #fff);
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 0.6rem;
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16);
    }
    .sps-stat {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1.5rem;
        padding: 0.32rem 0;
        font-size: 0.82rem;
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
        font-size: 0.82rem;
        font-weight: 600;
        line-height: 1.55;
        /* Chip backgrounds are always light (set inline), so pin dark text so it
           stays readable in dark mode too. */
        color: #212529;
        border: 1px solid rgba(0, 0, 0, 0.06);
    }
    /* Control rail: a subtle card so it reads as a panel, with a hair more
       breathing room between the stacked toggles than the app-wide gap:0 rule. */
    .st-key-scanpath_rail {
        border: 1px solid var(--sps-border);
        border-radius: 12px;
        padding: 0.55rem 0.85rem 0.35rem;
        background: var(--sps-accent-soft);
    }
    .st-key-scanpath_rail div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    .st-key-scanpath_rail h5 { margin: 0.15rem 0 0.1rem; }
    /* Section dividers default to 32px top+bottom margin — far too airy for the
       narrow rail. Tighten them so the sections sit close together. */
    .st-key-scanpath_rail hr { margin: 0.5rem 0 !important; }
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

    /* === Sidebar navigation as menu buttons =================================
       The primary nav is a keyed radio (`main_nav`) — restyle its options into
       full-width menu buttons (the radio dot hidden, the active item a filled
       brand pill) without changing the widget, so deep-links / AppTest still see
       a radio. `:has(input:checked)` flags the active option. */
    .st-key-tour_grp_nav div[role="radiogroup"] { gap: 0.35rem; }
    .st-key-tour_grp_nav div[role="radiogroup"] > label {
        width: 100%;
        margin: 0;
        padding: 0.5rem 0.8rem;
        border: 1px solid var(--sps-border);
        border-radius: 10px;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease;
    }
    .st-key-tour_grp_nav div[role="radiogroup"] > label:hover {
        background: var(--sps-accent-soft);
        border-color: var(--sps-accent-border);
    }
    /* Hide the radio circle (first child of each option label). */
    .st-key-tour_grp_nav div[role="radiogroup"] > label > div:first-child {
        display: none;
    }
    .st-key-tour_grp_nav div[role="radiogroup"] > label p { font-weight: 600; }
    /* Active item → filled brand pill. */
    .st-key-tour_grp_nav div[role="radiogroup"] > label:has(input:checked) {
        background: var(--sps-accent-soft);
        border-color: var(--sps-accent);
    }
    .st-key-tour_grp_nav div[role="radiogroup"] > label:has(input:checked) p {
        color: var(--sps-accent);
        font-weight: 700;
    }
    </style>
    """
