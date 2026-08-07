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
    .st-key-header_buttons button p { white-space: nowrap; }
    /* === UX-8: make leaving the sidebar as easy as entering it ==============
       Streamlit's only exit from an open sidebar is the "«" collapse control,
       and it ships `visibility: hidden` until the pointer is already inside the
       sidebar — so dismissing a sidebar you drifted into means hunting for a
       target that is invisible *and* icon-small. Pin it visible (muted, so it
       isn't shouty) and give it a real hit area; the matching "»" expand control
       in the header gets the same treatment so the pair reads as one toggle. */
    [data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
        opacity: 0.6;
        transition: opacity 0.15s ease, background 0.15s ease;
        border-radius: 8px;
    }
    [data-testid="stSidebarCollapseButton"]:hover { opacity: 1; }
    [data-testid="stSidebarCollapseButton"] button,
    button[data-testid="stExpandSidebarButton"] {
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        min-width: 2.4rem;
        min-height: 2.4rem;
        border-radius: 8px;
        transition: background 0.15s ease;
    }
    [data-testid="stSidebarCollapseButton"] button:hover,
    button[data-testid="stExpandSidebarButton"]:hover {
        background: var(--sps-accent-soft);
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
    /* UX-11: the chip strip WRAPS. It used to be pinned to one line, clipping
       whatever didn't fit, with a "More" disclosure that re-listed every chip so
       the clipped ones stayed reachable — the same facts twice, because which
       chips fit is a live-width question Python can't answer. Wrapping means
       nothing is ever cut at any width or sidebar state, so the duplicate list
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
    /* The two chip-strip controls — "Details" (summary stats) and ✏️ (edit
       chips). Both are shrunk to chip size and nudged down onto the first chip
       row's baseline: the strip now wraps, so the columns are TOP-aligned (a
       centred control would drift to the middle of a tall strip), and this
       offset is the strip's own top margin. UX-11 also fixed the ✏️ sitting
       visibly high — it was pulled sideways with a negative margin and centred
       against a one-line strip. */
    .st-key-chip_edit_box,
    .st-key-chip_details_box { margin-top: 0.1rem; }
    .st-key-chip_edit_box { margin-left: -0.6rem; }
    .st-key-chip_edit_box button,
    .st-key-chip_details_box button {
        min-height: 0 !important;
        padding: 0.1rem 0.65rem !important;
        border-radius: 999px !important;
        font-size: 0.9rem !important;
        line-height: 1.55 !important;
        white-space: nowrap;
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

    /* Control rail: a subtle card so it reads as a panel, with a hair more
       breathing room between the stacked toggles than the app-wide gap:0 rule. */
    .st-key-scanpath_rail {
        border: 1px solid var(--sps-border);
        border-radius: 12px;
        padding: 0.55rem 0.85rem 0.35rem;
        background: var(--sps-accent-soft);
        /* UX-29: lets the Quick-view rule below query the rail's own rendered
           width, not the viewport's — the wrap it reacts to comes from the
           sidebar being open/closed, which changes this column's width without
           necessarily crossing a viewport breakpoint. */
        container-type: inline-size;
        container-name: sps-rail;
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
    /* VIZ-31 layer groups (👁️ Scanpath / 📄 Stimulus / 🔥 Overlays / 🖥️ Canvas &
       text / 📐 Figure & axes). Streamlit gives the expander label
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
       Illustration") wrap to 2-3 lines once the rail column narrows — closing
       the sidebar buys back some width, but not always enough. Rather than
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
        #view-modes, #visualization, #scope, #figures, #also-include {
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
        /* Same for the header nav button, whose label is the longest in the app. */
        .st-key-header_buttons button p { white-space: normal; }
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
    </style>
    """
