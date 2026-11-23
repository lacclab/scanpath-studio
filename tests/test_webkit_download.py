"""WebKit's native download fallback and a self-contained offline reading."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import pytest

from tests import test_browser_smoke as smoke

local_app_url = smoke.app_url

pytestmark = pytest.mark.skipif(
    not os.getenv("SCANPATH_WEBKIT"), reason="The browser CI job installs WebKit"
)


def test_webkit_saves_and_reopens_the_standalone_figure(tmp_path):
    from playwright.sync_api import sync_playwright

    from scanpath_studio import api
    from scanpath_studio.save_dialog import _PARENT_JS
    from scanpath_studio.tabs import _figure_download_data

    words, fix = api.build_authored_scanpath("Read this")
    participant, trial = api.list_trials(words, fix).iloc[0]
    fig = api.plot_scanpath(words, fix, participant, trial)
    fig.update_layout(title_text=f"Review · {trial}", meta={"trial": str(trial)})
    payload = _figure_download_data(
        fig, "HTML", canvas_width=800, canvas_height=400, self_contained=True
    )()
    filename = "קריאה-é.html"
    # Exercise the same anchor that a download button creates, inside a
    # browser without showSaveFilePicker. Its payload is the app's actual HTML.
    with sync_playwright() as playwright, playwright.webkit.launch() as browser:
        context = browser.new_context(accept_downloads=True)
        # WebKit's simulated offline mode also refuses file:// navigations.
        # Deny network requests while allowing the saved local file to open.
        context.route(re.compile(r"^https?://"), lambda route: route.abort())
        page = context.new_page()
        page.set_content("<button>Download HTML</button>")
        page.evaluate(_PARENT_JS)
        page.evaluate(
            """([html, filename]) => {
            document.querySelector("button").onclick = () => {
                const link = document.createElement("a");
                link.href = URL.createObjectURL(new Blob([html], {type: "text/html"}));
                link.download = filename;
                document.body.append(link);
                link.click();
            };
        }""",
            [payload, filename],
        )
        with page.expect_download() as pending:
            page.get_by_role("button", name="Download HTML").click()
        suggested = pending.value.suggested_filename
        assert unicodedata.normalize("NFC", suggested) == filename
        destination = Path(tmp_path) / suggested
        pending.value.save_as(destination)
        assert destination.read_bytes() == payload.encode()
        page.goto(destination.as_uri())
        page.wait_for_function(
            "document.querySelector('.js-plotly-plot')?._fullLayout?.meta?.trial"
        )
        assert page.locator(".gtitle").text_content() == f"Review · {trial}"
        assert page.locator(".js-plotly-plot").evaluate(
            "plot => plot.layout.meta.trial"
        ) == str(trial)


@pytest.mark.parametrize(
    ("index", "target"),
    [
        (0, ".st-key-tour_grp_narrow_by"),
        (1, ".st-key-single_trial_sort"),
        (2, ".st-key-single_trial_pos"),
        (3, ".st-key-single_show_chips"),
    ],
)
def test_keyboard_picker_opens_and_focuses_the_selected_full_tool(
    local_app_url, index, target
):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright, playwright.webkit.launch() as browser:
        page = smoke._open(browser, f"{local_app_url}/?ui=essentials")
        more = page.locator(".st-key-iconpop_more_picker button:visible").first
        more.focus()
        page.keyboard.press("Enter")
        page.get_by_role("button", name="Filter trials", exact=True).wait_for()
        page.keyboard.press("Escape")
        page.wait_for_function(
            "document.activeElement.closest('.st-key-iconpop_more_picker')"
        )
        page.keyboard.press("Enter")
        action = page.locator(f".st-key-more_picker_tool_{index} button:visible").first
        action.focus()
        page.keyboard.press("Enter")
        try:
            page.wait_for_function(
                "target => document.activeElement.closest(target)",
                arg=target,
                timeout=8000,
            )
        except PlaywrightTimeoutError:
            pytest.fail(
                str(
                    page.evaluate(
                        """target => ({
                focused: document.activeElement.outerHTML.slice(0, 120),
                controls: [...document.querySelectorAll(target)].map(el => el.innerHTML.slice(0, 2200))
            })""",
                        target,
                    )
                )
            )
        assert not action.is_visible()


@pytest.mark.parametrize("width,height", [(390, 844), (640, 400)])
def test_import_guide_keeps_the_focused_field_visible(local_app_url, width, height):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright, playwright.webkit.launch() as browser:
        page = browser.new_context(
            viewport={"width": width, "height": height}
        ).new_page()
        page.goto(local_app_url)
        page.get_by_role("button", name="Import my data", exact=True).click(
            timeout=90000
        )
        field = page.locator(".st-key-wizard_dataset_name input:visible").first
        field.focus()
        assert not page.locator(".st-key-tour_card:visible").count()
        assert field.evaluate("""el => {
            const r = el.getBoundingClientRect();
            return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }""")
        upload = page.locator("button[aria-label='Upload fixations']:visible").first
        upload.focus()
        with page.expect_file_chooser() as event:
            page.keyboard.press("Enter")
        event.value.set_files([])
        assert upload.evaluate("""el => {
            const r = el.getBoundingClientRect();
            return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }""")
        page.get_by_role("button", name="Setup help").click()
        page.get_by_role("button", name="Show setup guide").click()
        smoke._settle(page)
        card = page.locator(".st-key-tour_card:visible").first
        assert card.is_visible()
        assert card.evaluate("card => getComputedStyle(card).position") in {
            "relative",
            "static",
        }
        assert page.locator(".st-key-wizard_sp_next button:visible").first.is_visible()
