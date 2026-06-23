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
    /* Header button row (the Corpus Analysis ⇄ Scanpath view toggle): right-align
       the content-sized trigger so it lines up with the page content's right edge. */
    .st-key-header_buttons {
        flex-direction: row;
        justify-content: flex-end;
        align-items: center;
        gap: 0.5rem;
    }
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
       identity/condition chips clip at the row edge while the "More" disclosure
       is pinned. Chips clipped at the edge are moved into "More" client-side
       (tabs._render_chip_overflow_script). */
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
    .sps-chip-more { flex: 0 0 auto; }
    /* Auto-hide "More" when it would be empty — no summary stats AND no chips
       were pushed into the overflow slot (everything fit on the line). */
    .sps-chip-more:not(:has(.sps-stat)):not(:has(.sps-chip-more-overflow .sps-chip)) {
        display: none;
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
    /* Overflow chips (those that didn't fit the line) sit at the top of the
       dropdown, wrapping freely. The slot collapses to nothing when empty. */
    .sps-chip-more-overflow {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
    }
    .sps-chip-more-overflow:empty { display: none; }
    /* A divider when both overflow chips and summary stats are present. */
    .sps-chip-more-overflow:has(.sps-chip) + .sps-stat {
        margin-top: 0.45rem;
        padding-top: 0.55rem;
        border-top: 1px solid rgba(0, 0, 0, 0.12);
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
    /* Inline ✏️ Edit-chips popover trigger: shrink it to chip size and give it a
       little space from the "More" disclosure to its left. */
    .st-key-chip_edit_box { margin-left: 0.5rem; }
    .st-key-chip_edit_box button {
        min-height: 0 !important;
        padding: 0.1rem 0.5rem !important;
        border-radius: 999px !important;
        font-size: 0.82rem !important;
        line-height: 1.55 !important;
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
    #view-modes, #visualization, #scope, #figures, #also-include {
        font-size: 20px !important; line-height: 24px !important;
        font-weight: 600 !important; padding: 6px 0 16px !important;
        /* In the narrow plot-side rail these can wrap; only ever break at a
           space, never mid-word ("Visualizatio↵n"). */
        word-break: normal !important; overflow-wrap: normal !important;
    }
    #view-modes, #visualization { margin: 2.4px 0 1.6px !important; }
    #this-trial, #multiple-trials {
        font-size: 24px !important; line-height: 28.8px !important;
        font-weight: 600 !important; padding: 8px 0 16px !important;
    }
    </style>
    """
