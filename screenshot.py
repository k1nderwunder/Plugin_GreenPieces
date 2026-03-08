from pathlib import Path
from playwright.sync_api import sync_playwright
import time

html_path = Path("index.html").resolve()
url = html_path.as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 720})

    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_function("window.mapReady === true", timeout=20000)

    time.sleep(3)

    page.locator("#map").screenshot(path="test.jpg")
    browser.close()

print("Скрин сохранен: yandex_satellite.jpg")