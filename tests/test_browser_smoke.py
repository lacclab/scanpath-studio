"""A real browser on the running app: it loads, the figure draws, a popover opens.

Most tests open the app in Full (``?ui=full``), which draws every
control; one opens it as a first visit does, in Essentials.

``AppTest`` runs no frontend, so nothing else in the suite sees what the app's
CSS and page scripts do to Streamlit's page: the true-scale plot iframe, the
rail's popovers, the scripts that reach into the parent document. A Streamlit
release that changes the markup those rely on breaks the app without failing
any other test, and the package pins no upper bound on Streamlit.

Needs Playwright and its Chromium (``pip install playwright`` then
``playwright install chromium``); skipped without them. CI runs it in its own
job (``ci.yml`` → *Browser smoke test*).
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.timeout(300)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def app_url():
    """The app on a free loopback port, saving nothing to the recovery cache."""
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "streamlit_app.py"),
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=ROOT,
        env={**os.environ, "SCANPATH_STUDIO_PERSIST": "0"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 120
    while True:
        if proc.poll() is not None:
            pytest.fail(f"the app exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2):
                break
        except OSError:
            if time.time() > deadline:
                proc.terminate()
                pytest.fail("the app did not answer its health check in 120 s")
            time.sleep(0.5)
    yield url
    proc.terminate()
    proc.wait(timeout=30)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except sync_api.Error as exc:
            pytest.skip(f"no Chromium for Playwright ({exc.message.splitlines()[0]})")
        yield browser
        browser.close()


def _open(browser, url: str):
    """A fresh browser context's page on ``url``, its uncaught errors collected,
    settled and with the first-visit tour closed."""
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(url)
    _settle(page)
    _close_tour(page)
    return page


@pytest.fixture(scope="module")
def page(app_url, browser):
    """One page on the app's first visit in Full, which draws every control
    the tests below reach for (a first visit opens in Essentials)."""
    page = _open(browser, f"{app_url}/?ui=full")
    yield page
    page.context.close()


@pytest.fixture(scope="module")
def simple_page(app_url, browser):
    """One page on the app's first visit, which opens in Essentials."""
    page = _open(browser, app_url)
    yield page
    page.context.close()


def _settle(page, quiet_ms: int = 1500, timeout_s: float = 150) -> None:
    """Wait until Streamlit has stopped running the script for ``quiet_ms``."""
    page.locator('[data-testid="stApp"]').wait_for(timeout=timeout_s * 1000)
    status = page.locator('[data-testid="stStatusWidget"]')
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not status.count():
            page.wait_for_timeout(quiet_ms)
            if not status.count():
                return
        page.wait_for_timeout(250)
    pytest.fail("the app never stopped running")


def _close_tour(page) -> None:
    """Dismiss the first-visit tour card, which covers the page."""
    for _ in range(3):
        buttons = [
            button
            for button in page.locator(
                '.st-key-tour_sp_close button, .st-key-tour_card button:has-text("Skip")'
            ).all()
            if button.is_visible()
        ]
        if not buttons:
            return
        buttons[0].click()
        _settle(page)


def _plot_frame(page, key: str):
    """The iframe holding the true-scale plot drawn under ``key``."""
    deadline = time.time() + 60
    while time.time() < deadline:
        for frame in page.frames:
            try:
                if frame.locator(f"#truescale-{key}").count():
                    return frame
            except sync_api.Error:
                continue
        page.wait_for_timeout(500)
    pytest.fail(f"no plot iframe holds #truescale-{key}")


@pytest.mark.parametrize("path", ["data", "corpus-analysis", "help-faq"])
def test_first_visit_respects_the_requested_page(app_url, browser, path):
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(f"{app_url}/{path}")
        if path == "help-faq":
            page.get_by_role("dialog").wait_for()
        else:
            target = (
                ".st-key-dataset_table_grid"
                if path == "data"
                else ".st-key-corpus_pool_bar"
            )
            page.locator(target).wait_for()
        _settle(page)
        assert not page.locator(".st-key-tour_sp_close button:visible").count()
        if path != "help-faq":
            assert page.url.split("?")[0] == f"{app_url}/{path}"


def test_phone_dataset_list_sorts_by_participant_count(app_url, browser):
    with browser.new_context(viewport={"width": 390, "height": 844}) as context:
        page = context.new_page()
        page.goto(f"{app_url}/data")
        grid = page.locator(".st-key-dataset_table_grid")
        counts = grid.locator(
            '[class*="st-key-dsc_participants_"] .sps-ds-num:not(.sps-ds-gap)'
        )
        counts.first.wait_for()
        _settle(page)
        largest = max(
            counts.all_text_contents(), key=lambda text: int(text.replace(",", ""))
        )
        grid.get_by_role("button", name="Participants", exact=True).click()
        sync_api.expect(counts.first).to_have_text(largest)


def test_phone_view_choices_stay_with_figure_in_both_modes(app_url, browser):
    with browser.new_context(viewport={"width": 390, "height": 844}) as context:
        page = context.new_page()
        page.goto(f"{app_url}/?source=demo&ui=essentials&animate=0")
        _plot_frame(page, "single").locator(".scatterlayer .trace").first.wait_for()
        _settle(page)
        _close_tour(page)

        def box(key):
            return page.locator(f".st-key-{key}").bounding_box()

        def below(lower, upper):
            a, b = box(lower), box(upper)
            assert a["y"] >= b["y"] + b["height"] - 1

        below("tour_grp_views", "tour_grp_plot")
        below("tour_grp_subtabs", "tour_grp_views")
        below("global_palette", "tour_grp_views")
        below("tour_grp_subtabs", "global_palette")
        views = box("tour_grp_views")
        assert views["y"] + views["height"] <= 844
        page.get_by_role("button", name="Heatmap", exact=True).click()
        _settle(page)
        page.locator(".st-key-ui_mode_switch").get_by_text("Full", exact=True).click()
        _settle(page)
        below("tour_grp_view_modes", "tour_grp_plot")
        below("global_palette", "tour_grp_views")
        below("tour_grp_subtabs", "global_palette")
        assert box("tour_grp_viz_controls")["height"] > 0
        page.set_viewport_size({"width": 1440, "height": 900})
        plot = box("tour_grp_plot")
        assert box("scanpath_rail")["x"] >= plot["x"] + plot["width"]
        assert abs(box("tour_grp_subtabs")["x"] - plot["x"]) < 1


def test_shared_controls_keep_their_positions_and_selection(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full&source=demo&animate=0")
    try:
        names = ("animation", "scanpath", "heatmap", "illustration")
        tiles = [
            page.locator(f".st-key-viz_view_{name}").get_by_role("button")
            for name in names
        ]
        palette = page.locator(".st-key-global_palette")

        def positions():
            header = page.locator(".st-key-plot_controls_header").bounding_box()
            boxes = [element.bounding_box() for element in [*tiles, palette]]
            return [
                (
                    box["x"] - header["x"],
                    box["y"] - header["y"],
                    box["width"],
                    box["height"],
                )
                for box in boxes
            ]

        tiles[2].click()
        _settle(page)
        palette.get_by_role("combobox").click()
        page.get_by_role("option", name="High contrast", exact=True).click()
        _settle(page)
        expected = positions()
        x, _, width, _ = expected[-1]
        for left, _, tile_width, _ in expected[:-1]:
            assert x <= left and left + tile_width <= x + width + 1
        for mode in ("Essentials", "Full"):
            page.locator(".st-key-ui_mode_switch").get_by_text(mode, exact=True).click()
            _settle(page)
            assert positions() == expected
            assert tiles[2].get_attribute("kind") == "primary"
            assert palette.get_by_role("combobox").input_value() == "High contrast"
            assert page.locator(".st-key-rail_compare").is_visible() == (mode == "Full")
            assert page.locator(".st-key-adv_only_rail_animation").is_visible() == (
                mode == "Full"
            )
        compare = page.locator(".st-key-single_compare_toggle")
        compare.locator("label").click()
        _settle(page)
        page.locator(".st-key-ui_mode_switch").get_by_text(
            "Essentials", exact=True
        ).click()
        _settle(page)
        assert compare.is_visible() and compare.locator("input").is_checked()
        assert positions() == expected
        compare.locator("label").click()
        _settle(page)
        assert not compare.is_visible()
        assert tiles[2].get_attribute("kind") == "primary"
        assert not page.locator('[data-testid="stException"]').count()
        assert page.errors == []
    finally:
        page.context.close()


def test_phone_corpus_profile_shows_data_above_the_fold(app_url, browser):
    with browser.new_context(viewport={"width": 390, "height": 844}) as context:
        page = context.new_page()
        page.goto(f"{app_url}/corpus-analysis")
        chart = page.locator('[data-testid="stPlotlyChart"]').first
        trace = chart.locator(".scatterlayer .trace").first
        trace.wait_for()
        _settle(page)
        assert trace.bounding_box()["y"] < 844
        box = chart.bounding_box()
        assert (
            page.locator(".st-key-ptext1_overlay").bounding_box()["y"]
            >= box["y"] + box["height"] - 1
        )


def test_the_page_renders_without_an_exception(page):
    assert page.locator('[data-testid="stTopNavLink"]').count() >= 3
    assert not page.locator('[data-testid="stException"]').count()


def test_the_scanpath_figure_draws(page):
    frame = _plot_frame(page, "single")
    frame.locator("#truescale-single.js-plotly-plot").wait_for(timeout=60_000)
    # Plotly has drawn: the figure's own SVG layers and at least one trace.
    assert frame.locator("#truescale-single .main-svg").count() >= 1
    assert frame.locator("#truescale-single .scatterlayer .trace").count() >= 1


def test_fixation_settings_and_visibility_are_independent(page):
    row = page.locator(".st-key-plot_layer_fix")
    switch = row.get_by_role("switch", name="Fixations")
    sync_api.expect(switch).to_be_checked()
    row.get_by_role("button", name="Fixations", exact=True).click()
    body = page.locator('[data-testid="stPopoverBody"]')
    body.first.wait_for(state="visible", timeout=15_000)
    assert "Size" in body.first.inner_text()
    sync_api.expect(switch).to_be_checked()
    page.keyboard.press("Escape")
    for shown in (False, True):
        switch.press("Space")
        _settle(page)
        assert switch.is_checked() == shown
        frame = _plot_frame(page, "single")
        assert (
            frame.locator("#truescale-single").evaluate(
                "plot => plot.data.some(t => t.name === 'Fixations')"
            )
            == shown
        )


def test_figure_and_filter_menus_stay_editable_after_undo(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full&source=synthetic")
    try:
        editor = page.locator(".st-key-plot_editor_tabs")
        editor.get_by_role("tab", name="Figure", exact=True).click()
        labels = editor.get_by_role("button", name="Title & labels")
        labels.click()
        title = page.locator(".st-key-global_show_title")
        title.locator("label").click()
        _settle(page)
        page.keyboard.press("Escape")
        page.get_by_role("button", name=re.compile(r"^Undo title")).click()
        _settle(page)
        labels.click()
        sync_api.expect(title.get_by_role("checkbox")).not_to_be_checked()
        title.locator("label").click()
        _settle(page)
        sync_api.expect(title.get_by_role("checkbox")).to_be_checked()
        page.keyboard.press("Escape")

        editor.get_by_role("tab", name="Layers", exact=True).click()
        row = editor.locator(".st-key-plot_filter_row")
        filters = row.get_by_role("button", name="Filters & highlights")
        button_height = filters.bounding_box()["height"]
        filters.click()
        short = page.locator(".st-key-global_fixclass_short_mode").get_by_role(
            "combobox"
        )
        for mode in ("Hide", "Off"):
            short.click()
            page.get_by_role("option", name=mode, exact=True).click()
            _settle(page)
            sync_api.expect(short).to_be_visible()
            assert row.get_by_text("Active", exact=True).is_visible() == (
                mode == "Hide"
            )
            assert filters.bounding_box()["height"] == button_height
        assert page.errors == []
    finally:
        page.context.close()


def test_a_trial_change_covers_the_figure_until_the_next_one_draws(page):
    """▶ puts the page's own card over the figure at the click — before the
    rerun has even reached the server — and the new figure's draw takes it down."""
    old = _plot_frame(page, "single")
    old.evaluate("window.__previousTrial = true")
    page.locator(".st-key-single_next_trial button").first.click()
    assert page.locator(".sps-trial-loading").count() == 1
    _settle(page)
    page.locator(".sps-trial-loading").wait_for(state="detached", timeout=30_000)
    frame = _plot_frame(page, "single")
    assert not frame.evaluate("!!window.__previousTrial")
    assert frame.locator("#truescale-single .main-svg").count() >= 1


def test_keyboard_steps_trials_from_the_page_and_plot(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full")
    try:
        previous = page.locator(".st-key-single_prev_trial button").first
        next_trial = page.locator(".st-key-single_next_trial button").first
        picker = page.locator(".st-key-single_trial_id input").first
        sync_api.expect(previous).to_be_disabled()

        picker.focus()
        page.keyboard.press("ArrowRight")
        sync_api.expect(previous).to_be_disabled()
        page.keyboard.press("Escape")
        picker.blur()
        page.keyboard.press("ArrowRight")
        sync_api.expect(previous).to_be_enabled(timeout=30_000)
        _settle(page)

        frame = _plot_frame(page, "single")
        frame.locator(".plotly .nsewdrag").first.click()
        page.keyboard.press("ArrowLeft")
        sync_api.expect(previous).to_be_disabled(timeout=30_000)
        _settle(page)
        next_trial.focus()
        page.keyboard.press("ArrowRight")
        sync_api.expect(previous).to_be_enabled(timeout=30_000)
        assert page.errors == []
    finally:
        page.context.close()


def test_keyboard_controls_replay_without_changing_trial(simple_page):
    page = simple_page
    frame = _plot_frame(page, "single_anim")
    timeline = frame.get_by_role("slider", name="Replay time")
    timeline.focus()
    page.keyboard.press("End")
    sync_api.expect(timeline).to_have_value(timeline.get_attribute("max"))
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    sync_api.expect(timeline).to_have_value("1")
    page.keyboard.press("ArrowLeft")
    sync_api.expect(timeline).to_have_value("0")
    page.keyboard.press("Space")
    sync_api.expect(timeline).not_to_have_value("0")
    page.keyboard.press("Space")

    # Space on the page controls this same player without moving focus.
    next_trial = page.locator(".st-key-single_next_trial button").first
    next_trial.focus()
    next_trial.blur()
    paused = timeline.input_value()
    page.keyboard.press("Space")
    sync_api.expect(timeline).not_to_have_value(paused)
    page.keyboard.press("Space")
    sync_api.expect(
        page.locator(".st-key-single_prev_trial button").first
    ).to_be_disabled()
    assert page.errors == []


def test_keyboard_steps_comparison_b_at_a_boundary(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full")
    try:
        page.locator(".st-key-single_compare_toggle label").click()
        _settle(page)
        position = page.locator(".st-key-single_compare_pos").get_by_role("slider")
        position.focus()
        page.keyboard.press("End")
        next_b = page.locator(".st-key-single_compare_next button").first
        sync_api.expect(next_b).to_be_disabled(timeout=30_000)
        _settle(page)
        previous_b = page.locator(".st-key-single_compare_prev button").first
        previous_b.focus()
        page.keyboard.press("Shift+ArrowLeft")
        sync_api.expect(next_b).to_be_enabled(timeout=30_000)
        _settle(page)
        next_b.focus()
        page.keyboard.press("Shift+ArrowRight")
        sync_api.expect(next_b).to_be_disabled(timeout=30_000)
        _settle(page)
        page.keyboard.press("Shift+ArrowLeft")
        sync_api.expect(next_b).to_be_enabled(timeout=30_000)
        sync_api.expect(
            page.locator(".st-key-single_prev_trial button").first
        ).to_be_disabled()
        assert page.errors == []
    finally:
        page.context.close()


def test_the_tour_card_shows_nothing_until_its_stylesheet_applies(page):
    """Streamlit draws a markdown block's raw HTML — the card's stylesheet —
    only once it has fetched its HTML renderer, a script of its own. Without
    it, the card must stay clipped to its 1px slot, not show its text and
    buttons inline at the top of the page."""
    blocked = []

    def block(route):
        blocked.append(route.request.url)
        route.abort()

    context = page.context.browser.new_context(viewport={"width": 1440, "height": 900})
    other = context.new_page()
    try:
        other.route(re.compile(r"/rehype-raw[^/]*\.js"), block)
        other.goto(page.url)
        _settle(other)
        if not blocked:
            pytest.skip("this Streamlit fetches no separate rehype-raw script")
        card = other.locator(".st-key-tour_card")
        card.wait_for(state="attached", timeout=30_000)
        assert card.bounding_box()["height"] <= 1
    finally:
        context.close()


def test_the_app_stylesheet_does_not_wait_for_the_markdown_renderer(page):
    """The app's stylesheet is a style-only `st.html`, so it applies without
    the script a markdown block's raw HTML waits for: with that script never
    arriving, the off-screen Data page is still hidden."""
    blocked = []

    def block(route):
        blocked.append(route.request.url)
        route.abort()

    context = page.context.browser.new_context(viewport={"width": 1440, "height": 900})
    other = context.new_page()
    try:
        other.route(re.compile(r"/rehype-raw[^/]*\.js"), block)
        other.goto(page.url)
        _settle(other)
        if not blocked:
            pytest.skip("this Streamlit fetches no separate rehype-raw script")
        hidden = other.locator(".st-key-data_setup_page_offscreen")
        hidden.wait_for(state="attached", timeout=30_000)
        assert hidden.evaluate("el => getComputedStyle(el).display") == "none"
    finally:
        context.close()


def test_the_app_stylesheet_reaches_the_page_rule_for_rule(page):
    """Compacted and passed through `st.html`'s sanitizer, the stylesheet on
    the page holds every rule of the documented one, unchanged."""
    from scanpath_studio.styles import get_app_css

    source = re.sub(r"^\s*<style>|</style>\s*$", "", get_app_css().strip())
    found = page.evaluate(
        """(source) => {
          const norm = (sheet) =>
            [...sheet.cssRules].map((r) => r.cssText.replace(/\\s+/g, " "));
          const live = [...document.querySelectorAll("style")].find((s) =>
            s.textContent.includes(".st-key-data_setup_page_offscreen"));
          const probe = document.createElement("style");
          probe.textContent = source;
          document.head.appendChild(probe);
          const want = norm(probe.sheet);
          probe.remove();
          return {want, got: live ? norm(live.sheet) : null};
        }""",
        source,
    )
    assert found["got"] is not None, "the app stylesheet is not on the page"
    assert found["got"] == found["want"]


def test_no_script_error_reached_the_page(page):
    assert page.errors == []


def test_chart_controls_survive_navigation_presets_and_reset(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full")

    def click(key):
        page.locator(f".st-key-{key} button").first.click()
        _settle(page)

    def switch(mode):
        page.locator(".st-key-ui_mode_switch").get_by_text(mode, exact=True).click()
        _settle(page)

    def chart():
        frame = _plot_frame(page, "single")
        frame.locator("#truescale-single .main-svg").first.wait_for()
        return frame.locator("#truescale-single").evaluate(
            """plot => {
                const fix = plot._fullData.find(t => t.name === "Fixations");
                return {
                    axes: [plot.layout.xaxis.title?.text, plot.layout.yaxis.title?.text],
                    layers: plot.data.map(t => t.name),
                    points: fix ? Array.from(fix.x, (x, i) => [x, fix.y[i]]) : [],
                    mode: fix?.mode,
                };
            }"""
        )

    try:
        default = chart()
        editor = page.locator(".st-key-plot_editor_tabs")
        editor.get_by_role("tab", name="Axes", exact=True).click()
        page.get_by_role("combobox", name="Axis preset").click()
        page.get_by_role("option", name="Elapsed time by fixation index").click()
        _settle(page)
        editor.get_by_role("tab", name="Layers", exact=True).click()
        click("plot_menu_fix")
        page.locator(".st-key-global_show_order label").click()
        _settle(page)
        page.keyboard.press("Escape")
        first = chart()
        assert first["axes"] == ["Fixation order", "Seconds since first fixation onset"]
        assert first["mode"] == "markers+text"
        click("viz_undo")
        assert chart()["mode"] == "markers"
        click("plot_menu_fix")
        page.locator(".st-key-global_show_order label").click()
        _settle(page)
        page.keyboard.press("Escape")
        assert chart() == first
        assert page.locator(".st-key-viz_redo button").first.is_disabled()

        switch("Essentials")
        assert chart() == first
        click("single_next_trial")
        second = chart()
        assert second["points"] != first["points"]
        click("hidden_note_to_advanced")
        assert chart() == second

        click("viz_view_heatmap")
        heatmap = chart()
        assert "heatmap colorbar" in heatmap["layers"]
        switch("Essentials")
        assert chart() == heatmap
        switch("Full")
        page.locator(".st-key-design_shell summary").click()
        click("viz_view_custom")
        assert chart() == second
        click("single_prev_trial")
        assert chart() == first
        click("reset_viz_settings_btn")
        click("reset_viz_cancel")
        assert chart() == first
        click("reset_viz_settings_btn")
        click("reset_viz_confirm")
        assert chart() == default
        click("viz_undo")
        assert chart() == first
        click("viz_redo")
        assert chart() == default
        switch("Essentials")
        assert chart() == default
        click("viz_view_heatmap")
        assert "heatmap colorbar" in chart()["layers"]
        switch("Full")
        click("viz_view_illustration")
        click("single_next_trial")
        click("reset_viz_settings_btn")
        click("reset_viz_confirm")
        reset_second = chart()
        assert reset_second["layers"] == default["layers"]
        assert len(reset_second["points"]) == len(second["points"])
        click("reset_viz_settings_btn")
        click("reset_viz_confirm")
        assert chart() == reset_second
        assert not page.locator('[data-testid="stException"]').count()
        assert page.errors == []
    finally:
        page.context.close()


def test_simple_opens_on_the_replay_with_its_own_controls(simple_page):
    """A first visit opens in Essentials: the replay draws, the ＋ More list
    opens, the switch shows, and a Full-only rail popover is hidden."""
    page = simple_page
    frame = _plot_frame(page, "single_anim")
    frame.locator("#truescale-single_anim.js-plotly-plot").wait_for(timeout=60_000)
    assert frame.locator("#truescale-single_anim .main-svg").count() >= 1
    assert page.locator(".st-key-tour_grp_ui_mode").first.is_visible()
    assert not page.locator(".st-key-plot_menu_fix").first.is_visible()
    page.locator(".st-key-iconpop_more_picker button").first.click()
    body = page.locator('[data-testid="stPopoverBody"]')
    body.first.wait_for(state="visible", timeout=15_000)
    assert "Switch to Full" in body.first.inner_text()
    page.keyboard.press("Escape")
    assert not page.locator('[data-testid="stException"]').count()
    assert page.errors == []


def test_index_chart_announces_its_visible_fixations_and_axes(app_url, browser):
    url = (
        f"{app_url}/?ui=full&source=synthetic&animate=0&x_field=order_in_trial"
        "&fixclass_short_mode=Hide&fixclass_short_threshold_ms=160"
    )
    page = _open(browser, url)
    try:
        frame = _plot_frame(page, "single")
        iframe = frame.frame_element()
        name = iframe.get_attribute("title") or iframe.get_attribute("aria-label") or ""
        assert "1 fixation shown of 9 recorded" in name
        assert "fixation order" in name.lower() and "vertical" in name.lower()
        assert page.errors == []
    finally:
        page.context.close()


@pytest.mark.parametrize("surface", ["api", "app"])
def test_saved_replay_steps_and_scrubs_between_recorded_onsets(
    browser, tmp_path, surface
):
    """Press the shared transport buttons on a real, self-contained HTML download."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    from scanpath_studio import api, plots, tabs
    from scanpath_studio.synthetic import PARTICIPANT, TRIAL, load_synthetic_data

    words, fixations = load_synthetic_data()
    fixations = fixations.iloc[:4].assign(
        timestamp_ms=[0, 30, 60, 220],
        duration_ms=[10, 18, 100, 50],
        word_id=[0, 0, 1, 2],
    )
    options = dict(autoplay=False, anim_grid_step_ms=100)
    target = tmp_path / "replay.html"
    if surface == "api":
        figure = api.animate_scanpath(words, fixations, PARTICIPANT, TRIAL, **options)
        api.save_figure(figure, target)
    else:
        figure, _ = plots.build_scanpath_replay(
            words,
            fixations,
            compact=True,
            canvas_width=800,
            canvas_height=600,
            base_font_size=16,
            **options,
        )
        view = tabs._ReplayView.from_figure(
            figure, plot_key="browser", download_name="reading", signature="test"
        )
        target.write_text(
            tabs._replay_page_html(view, self_contained=True), encoding="utf-8"
        )
    group = figure.layout.meta["scanpath_fixation_steps"][0]
    current = int(figure.frames[0].traces[group["current"]])
    handler = partial(SimpleHTTPRequestHandler, directory=tmp_path)
    with (
        ThreadingHTTPServer(("127.0.0.1", 0), handler) as server,
        browser.new_context() as context,
    ):
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/replay.html")

            # Compact app pages and full Python figures both seek without retaining
            # a second copy of the replay in Plotly's named frame registry.
            def registered_frames():
                return page.locator(".js-plotly-plot").evaluate(
                    "gd => gd._transitionData?._frames?.length || 0"
                )

            def expect_point(x):
                page.wait_for_function(
                    "([i,x]) => document.querySelector('.js-plotly-plot')._fullData[i].x[0] === x",
                    arg=[current, float(x)],
                    timeout=5000,
                )

            assert registered_frames() == 0
            for button, number, x, duration, word in (
                ("Next fixation", 2, 135, 18, "The"),
                ("Next fixation", 3, 225, 100, "cat"),
                ("Previous fixation", 2, 135, 18, "The"),
            ):
                page.get_by_role("button", name=button).click()
                expect_point(x)
                detail = page.get_by_role("status").inner_text()
                assert (
                    f"Fixation {number}" in detail
                    and f"duration {duration} ms" in detail
                    and word in detail
                )
            page.get_by_role("slider", name="Replay time").press("End")
            expect_point(325)
            page.get_by_role("button", name="Previous fixation").click()
            assert "onset 220 ms" in page.get_by_role("status").inner_text()
            page.get_by_role("slider", name="Replay time").press("Home")
            expect_point(fixations.iloc[0]["x"])
            assert registered_frames() == 0
            assert errors == []
        finally:
            server.shutdown()
            thread.join()


def test_packed_replay_with_native_plotly_controls(browser, tmp_path):
    """The docs keep Plotly's slider and buttons on the packed replay."""
    import plotly.io as pio

    from scanpath_studio import plots
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = load_synthetic_data()
    figure, _ = plots.build_scanpath_replay(
        words,
        fixations,
        autoplay=False,
        anim_grid_step_ms=100,
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
    )
    data, player = plots.replay_page(figure, toolbar=False)
    path = tmp_path / "native.html"
    pio.write_html(data, path, validate=False, post_script=player)
    group = figure.layout.meta["scanpath_fixation_steps"][0]
    current = int(figure.frames[0].traces[group["current"]])
    last = len(figure.frames) - 1
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(path.as_uri())

        def expect_frame(index):
            frame = figure.frames[index]
            x = frame.data[list(frame.traces).index(current)].x[0]
            page.wait_for_function(
                """([index, current, x]) => {
                  const gd = document.querySelector('.js-plotly-plot');
                  return gd.layout.sliders[0].active === index && gd._fullData[current].x[0] === x;
                }""",
                arg=[index, current, float(x)],
            )

        rail = page.locator(".slider-rail-rect")
        box = rail.bounding_box()
        page.mouse.click(box["x"] + box["width"] - 1, box["y"] + box["height"] / 2)
        expect_frame(last)
        page.locator(".updatemenu-button").filter(has_text="Restart").click()
        expect_frame(0)
        page.locator(".updatemenu-button").filter(has_text="Play").click()
        expect_frame(last)
        assert (
            page.locator(".js-plotly-plot").evaluate(
                "gd => gd._transitionData._frames.length"
            )
            == 0
        )


def test_mixed_script_passage_keeps_each_label_in_its_box_in_html_and_svg(
    browser, tmp_path
):
    from scanpath_studio.api import save_figure
    from tests.test_mixed_script_reading import mixed_script_figure

    figure, words, _ = mixed_script_figure()
    labels = words.text.tolist()
    target = tmp_path / "passage.html"
    save_figure(figure, target)
    # Inspect the glyph boxes in the Plotly figure and in the saved, standalone vector.
    inspect = """labels => {
        const boxes = [...document.querySelectorAll('.shapelayer path')]
            .map(p => p.getBoundingClientRect());
        return labels.map(label => {
            const node = [...document.querySelectorAll('.textpoint text')].find(el =>
                el.textContent.replace(/[\u2067\u2069]/g, '') === label);
            if (!node) return false;
            const b = node.getBoundingClientRect();
            return b.width > 0 && b.height > 0 && boxes.some(rect =>
                b.x >= rect.x - 1 && b.right <= rect.right + 1 &&
                b.y >= rect.y - 1 && b.bottom <= rect.bottom + 1);
        });
    }"""
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(target.as_uri())
        page.wait_for_selector(".textpoint text")
        assert dict(zip(labels, page.evaluate(inspect, labels))) == dict.fromkeys(
            labels, True
        )
        vector = page.evaluate("""async () => {
            const gd = document.querySelector('.js-plotly-plot');
            const url = await Plotly.toImage(gd, {format: 'svg', width: gd.layout.width, height: gd.layout.height});
            return decodeURIComponent(url.slice(url.indexOf(',') + 1));
        }""")
        page.set_content(vector)
        assert dict(zip(labels, page.evaluate(inspect, labels))) == dict.fromkeys(
            labels, True
        )


@pytest.mark.parametrize("mode", ["essentials", "full"])
def test_clicking_a_fixation_keeps_the_trial_tabs_available(app_url, browser, mode):
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(f"{app_url}/?ui={mode}&source=synthetic&animate=0")
        _settle(page)
        _close_tour(page)
        assert not page.locator('[data-testid="stException"]').count()
        frame = _plot_frame(page, "single")
        uid = frame.evaluate(
            """document.getElementById('truescale-single')._fullData.find(t => t.name === 'Fixations').uid"""
        )
        frame.locator(f".trace{uid} .point").nth(6).click(force=True)
        _settle(page)
        sync_api.expect(
            page.get_by_text("Inspect a fixation", exact=True)
        ).to_have_count(0)
        sync_api.expect(
            page.get_by_role("tab", name=re.compile("Export"))
        ).to_be_visible()


def test_live_comparison_exports_a_physical_svg_and_reopenable_panel_settings(
    app_url, browser
):
    import json
    import xml.etree.ElementTree as ET

    from scanpath_studio.animation_export import chrome_available

    if not chrome_available():
        pytest.skip("native SVG renderer is unavailable")
    with browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        page.goto(
            f"{app_url}/?ui=full&source=synthetic&compare=synthetic:synthetic_2line_demo&cmp_layout=Side+by+side"
        )
        _settle(page)
        _close_tour(page)
        page.get_by_role("tab", name=re.compile("Export")).click()
        page.get_by_text("Manuscript panel proof", exact=True).click()
        page.get_by_text(re.compile("Stimulus words · .* pt")).wait_for()
        _settle(page)
        assert not page.locator('[data-testid="stException"]').count()
        with page.expect_download() as download:
            page.get_by_role("button", name="Save panel settings", exact=True).click()
        config = json.loads(download.value.path().read_text())
        assert config["selection"]["participant_id"] == "synthetic"
        assert config["selection"]["compare"]["participant_id"] == "synthetic"
        assert config["mode"] == {"animate": False, "compare": True}
        page.get_by_role("button", name="Prepare manuscript SVG", exact=True).click()
        with page.expect_download(timeout=60000) as download:
            page.get_by_role(
                "button", name="Download manuscript SVG", exact=True
            ).click(timeout=60000)
        root = ET.parse(download.value.path()).getroot()
        assert root.get("width") == f"{config['export']['width']:g}mm"
        assert "A · " in "".join(root.itertext()) and "B · " in "".join(root.itertext())


def test_upload_blocker_focuses_duration_then_shows_two_conversions(app_url, browser):
    page = _open(browser, f"{app_url}/?ui=full")
    try:
        upload = page.locator(".st-key-col_map_fix_upload input[type=file]")
        page.locator(".st-key-add_dataset_menu button").first.click()
        page.get_by_role("button", name="Import files", exact=True).click()
        _settle(page)
        upload.set_input_files(
            {
                "name": "pilot.csv",
                "mimeType": "text/csv",
                "buffer": b"participant_id,trial_id,x,y,looking [s]\np1,t1,20,30,0.12\np1,t1,23,35,0.245\n",
            }
        )
        field = page.locator(".st-key-col_map_fix_duration input:not([type=hidden])")
        field.wait_for()
        _settle(page)
        page.get_by_role("button", name="Add dataset", exact=True).click()
        blocker = page.get_by_role("link", name="missing Duration")
        blocker.focus()
        blocker.press("Enter")
        sync_api.expect(field).to_be_focused()
        field.fill("looking")
        page.get_by_role("option", name="looking [s]", exact=True).click()
        page.get_by_text("0.12 → 120 ms, 0.245 → 245 ms", exact=False).wait_for()
        blocker.wait_for(state="detached")
    finally:
        page.context.close()


def test_reduced_motion_keeps_a_steady_tour_target_as_the_keyboard_advances(
    app_url, browser
):
    with browser.new_context(reduced_motion="reduce") as context:
        page = context.new_page()
        page.goto(f"{app_url}/?ui=full")
        advance = page.locator(".st-key-tour_sp_next button")
        for target in ("plot", "data_source", "trial_picker"):
            advance.focus()
            advance.press("Enter")
            page.wait_for_function(
                """selector => {
                    const el = document.querySelector(selector);
                    if (!el || !el.getBoundingClientRect().width) return false;
                    const style = getComputedStyle(el);
                    return style.outlineStyle === "solid"
                        && parseFloat(style.outlineWidth) >= 2
                        && style.animationName === "none";
                }""",
                arg=f".st-key-tour_grp_{target}",
                timeout=60000,
            )
