"""Один раз скачивает границы округов Москвы из OpenStreetMap (Nominatim)
и сохраняет в districts.geojson. Запускать заново не нужно — файл лежит в репо."""
import json
import time
from pathlib import Path

import requests

OKRUGS = {
    "ЦАО": "Центральный административный округ",
    "САО": "Северный административный округ",
    "СВАО": "Северо-Восточный административный округ",
    "СЗАО": "Северо-Западный административный округ",
    "ВАО": "Восточный административный округ",
    "ЮВАО": "Юго-Восточный административный округ",
    "ЮАО": "Южный административный округ",
    "ЮЗАО": "Юго-Западный административный округ",
    "ЗАО": "Западный административный округ",
    "ЗелАО": "Зеленоградский административный округ",
    "НАО": "Новомосковский административный округ",
    "ТАО": "Троицкий административный округ",
}

features = []
for short, full in OKRUGS.items():
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": full + ", Москва", "format": "json", "polygon_geojson": 1, "limit": 3},
        headers={"User-Agent": "okrug-boundaries-fetcher/1.0"},
        timeout=60,
    )
    r.raise_for_status()
    hit = next((x for x in r.json() if x.get("geojson", {}).get("type") in ("Polygon", "MultiPolygon")), None)
    if not hit:
        raise SystemExit(f"не найден полигон: {full}")
    features.append({"type": "Feature", "properties": {"okrug": short, "name": full}, "geometry": hit["geojson"]})
    print(short, hit["geojson"]["type"], hit.get("display_name", "")[:60])
    time.sleep(1.2)

out = Path(__file__).resolve().parent.parent / "districts.geojson"
out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
print("сохранено", out)
