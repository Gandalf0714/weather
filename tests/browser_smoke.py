"""Browser smoke test run against an already-started local server."""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:5000"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts")
OUTPUT.mkdir(parents=True, exist_ok=True)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=str(EDGE))
    desktop = browser.new_page(viewport={"width": 1440, "height": 1000})
    console_errors = []
    failed_resources = []
    desktop.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    desktop.on(
        "response",
        lambda response: failed_resources.append(f"{response.status} {response.url}")
        if response.status >= 400
        else None,
    )
    desktop.goto(BASE_URL, wait_until="networkidle")
    desktop.locator("#current-location").wait_for()
    assert "南京" in desktop.locator("#current-location").inner_text()
    assert desktop.locator("#hourly-strip .hour-card").count() >= 12
    desktop.screenshot(path=OUTPUT / "weather-desktop.png", full_page=True)

    desktop.get_by_role("button", name="历史趋势").click()
    assert desktop.locator("#history-chart svg").count() == 1
    desktop.get_by_role("button", name="ML 预测").click()
    assert desktop.get_by_role("button", name="训练并预测").is_visible()
    desktop.get_by_role("button", name="训练并预测").click()
    desktop.locator("#ml-forecast .forecast-card").first.wait_for(timeout=60_000)
    assert desktop.locator("#ml-forecast .forecast-card").count() == 7
    desktop.screenshot(path=OUTPUT / "weather-model.png", full_page=True)
    desktop.get_by_role("button", name="全国天气").click()
    desktop.locator("#province-grid .province-cell").first.wait_for(timeout=60_000)
    assert desktop.locator("#province-grid .province-cell").count() >= 31
    desktop.locator("#unit-toggle").click()
    assert "°F" in desktop.locator("#unit-toggle .active").inner_text()

    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.goto(BASE_URL, wait_until="networkidle")
    mobile.locator("#current-location").wait_for()
    assert mobile.locator("body").evaluate("el => el.scrollWidth <= window.innerWidth")
    mobile.screenshot(path=OUTPUT / "weather-mobile.png", full_page=True)
    browser.close()

if console_errors:
    filtered = [message for message in console_errors if "favicon" not in message.lower()]
    if filtered:
        raise AssertionError(
            f"browser console errors: {filtered}; failed resources: {failed_resources}"
        )

print(f"Browser smoke test passed. Screenshots: {OUTPUT.resolve()}")
