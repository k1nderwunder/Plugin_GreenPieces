import json
import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

BASE = os.getenv("AGROSIGNAL_BASE_URL", "https://mir.agrosignal.com").rstrip("/")
API_KEY = os.getenv("AGROSIGNAL_API_KEY")

TIMEOUT = 60
SLEEP_SEC = 0.1
OUTPUT_FILE = "cleaned_fields.json"


def get_json(url: str) -> dict:
    response = requests.get(url, params={"apiKey": API_KEY}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def extract_outer_boundary(data: dict):
    geom = data.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")

    if not coords:
        return None

    if gtype == "Polygon":
        return coords[0]

    if gtype == "MultiPolygon":
        return coords[0][0]

    return None


def main():
    if not API_KEY:
        raise ValueError("Не найден AGROSIGNAL_API_KEY в .env")

    # 1) Берем список всех геозон
    payload = get_json(f"{BASE}/geoZones")
    zones = payload["data"]

    # 2) Оставляем только поля
    fields = [z for z in zones if z.get("zoneType") == "field"]
    print("Total geozones:", len(zones))
    print("Total fields:", len(fields))

    out = []
    errors = 0
    skipped = 0

    for i, z in enumerate(fields, 1):
        zid = int(z["id"])

        try:
            # 3) Берем полную геометрию поля
            detail_payload = get_json(f"{BASE}/fullGeoZone/{zid}")
            data = detail_payload["data"]

            name = data.get("title") or z.get("title") or str(zid)
            outer = extract_outer_boundary(data)

            if not outer:
                skipped += 1
                print(f"[{i}/{len(fields)}] SKIP id={zid} name={name}: geometry not found")
                continue

            out.append({
                "name": name,
                "outerBoundary": outer
            })

        except Exception as e:
            errors += 1
            print(f"[{i}/{len(fields)}] ERROR id={zid}: {e}")

        if i % 25 == 0:
            print(f"Processed {i}/{len(fields)} | ok={len(out)} | skipped={skipped} | errors={errors}")

        time.sleep(SLEEP_SEC)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Saved: {OUTPUT_FILE}")
    print(f"Objects: {len(out)} | skipped: {skipped} | errors: {errors}")


if __name__ == "__main__":
    main()