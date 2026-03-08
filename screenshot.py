from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from playwright.sync_api import sync_playwright
import time


HOST = "127.0.0.1"
PORT = 8000
OUTPUT_FILE = "field_test.png"
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080


def start_server():
    project_dir = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(project_dir))
    server = ThreadingHTTPServer((HOST, PORT), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    server = start_server()
    time.sleep(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
            )

            page.on("console", lambda msg: print("BROWSER:", msg.text))
            page.on("pageerror", lambda err: print("PAGE ERROR:", err))

            page.goto(f"http://{HOST}:{PORT}/index.html", wait_until="domcontentloaded")
            page.wait_for_function("window.mapReady === true", timeout=60000)

            page.locator("#map").screenshot(path=OUTPUT_FILE)
            browser.close()

        print(f"Скрин сохранен: {OUTPUT_FILE}")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()