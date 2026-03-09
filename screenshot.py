import json
import os
import time
from io import BytesIO
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from PIL import Image


load_dotenv()

HOST = "127.0.0.1"
PORT = 8000

INPUT_FILE = "cleaned_fields.json"
CURRENT_FIELD_FILE = "current_field.json"
TEMPLATE_FILE = "index.template.html"
INDEX_FILE = "index.html"
OUTPUT_DIR = "screenshots"
BOUNDS_OUTPUT_FILE = "screenshot_bounds.json"

VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

FINAL_WIDTH = 1280
FINAL_HEIGHT = 720
JPEG_QUALITY = 90

WAIT_TIMEOUT_MS = 60000
WAIT_AFTER_READY_SEC = 1.5


def start_server():
    project_dir = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(project_dir))
    server = ThreadingHTTPServer((HOST, PORT), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def sanitize_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name)
    safe = "_".join(safe.split())
    return safe[:120] or "field"


def load_fields() -> list[dict]:
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(f"Не найден файл {INPUT_FILE}")

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{INPUT_FILE} должен содержать список объектов")

    fields = []
    for item in data:
        if not isinstance(item, dict):
            continue

        name = item.get("name")
        outer = item.get("outerBoundary")

        if isinstance(name, str) and isinstance(outer, list) and outer:
            fields.append({
                "name": name,
                "outerBoundary": outer
            })

    return fields


def write_current_field(field: dict):
    Path(CURRENT_FIELD_FILE).write_text(
        json.dumps(field, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def remove_current_field():
    Path(CURRENT_FIELD_FILE).unlink(missing_ok=True)


def render_index_html():
    api_key = os.getenv("YANDEX_MAPS_API_KEY")
    if not api_key:
        raise ValueError("В .env не найден YANDEX_MAPS_API_KEY")

    template_path = Path(TEMPLATE_FILE)
    if not template_path.exists():
        raise FileNotFoundError(f"Не найден шаблон {TEMPLATE_FILE}")

    template = template_path.read_text(encoding="utf-8")
    html = template.replace("{{YANDEX_MAPS_API_KEY}}", api_key)

    Path(INDEX_FILE).write_text(html, encoding="utf-8")


def save_jpeg_from_png_bytes(png_bytes: bytes, output_path: Path):
    image = Image.open(BytesIO(png_bytes)).convert("RGB")
    image = image.resize((FINAL_WIDTH, FINAL_HEIGHT), Image.LANCZOS)
    image.save(output_path, "JPEG", quality=JPEG_QUALITY)


def main():
    render_index_html()

    fields = load_fields()
    if not fields:
        raise ValueError("В cleaned_fields.json нет полей для обработки")

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    bounds_dict = {}

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

            total = len(fields)
            success = 0
            errors = 0

            for index, field in enumerate(fields, start=1):
                try:
                    write_current_field(field)

                    page.goto(f"http://{HOST}:{PORT}/index.html", wait_until="domcontentloaded")
                    page.wait_for_function("window.mapReady === true", timeout=WAIT_TIMEOUT_MS)
                    time.sleep(WAIT_AFTER_READY_SEC)

                    screenshot_bounds = page.evaluate("window.screenshotBounds")
                    if not screenshot_bounds:
                        raise ValueError("Не удалось получить screenshotBounds со страницы")

                    bounds_dict[field["name"]] = screenshot_bounds

                    screenshot_bytes = page.locator("#map").screenshot(type="png")

                    filename = f"{index:04d}_{sanitize_filename(field['name'])}.jpg"
                    output_path = output_dir / filename
                    save_jpeg_from_png_bytes(screenshot_bytes, output_path)

                    success += 1
                    print(f"[{index}/{total}] OK -> {output_path}")

                except Exception as e:
                    errors += 1
                    print(f"[{index}/{total}] ERROR {field.get('name', 'unknown')}: {e}")

            browser.close()

        Path(BOUNDS_OUTPUT_FILE).write_text(
            json.dumps(bounds_dict, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print(f"Готово. Успешно: {success}, ошибок: {errors}")
        print(f"Папка со скринами: {output_dir.resolve()}")
        print(f"Словарь границ сохранен в: {Path(BOUNDS_OUTPUT_FILE).resolve()}")

    finally:
        remove_current_field()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()