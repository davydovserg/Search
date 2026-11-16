"""Округа Москвы, стороны света и сетка квадратов для поиска."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Сторона света для каждого округа. Можно поменять здесь.
SEGMENTS = {
    "ЦАО": "Центр",
    "САО": "Север", "СВАО": "Север", "СЗАО": "Север", "ЗелАО": "Север",
    "ВАО": "Восток", "ЮВАО": "Восток",
    "ЮАО": "Юг", "ЮЗАО": "Юг",
    "ЗАО": "Запад", "НАО": "Запад", "ТАО": "Запад",
}

# Сторона поиска, которую Яндекс берёт вокруг центра карты, в пикселях
# (замерено: ~780 px). Берём чуть меньше, чтобы квадраты перекрывались.
CELL_PX = 720


class Okrug:
    def __init__(self, short, geometry):
        self.short = short
        self.segment = SEGMENTS[short]
        if geometry["type"] == "Polygon":
            self.polys = [geometry["coordinates"]]
        else:
            self.polys = geometry["coordinates"]
        xs = [p[0] for poly in self.polys for p in poly[0]]
        ys = [p[1] for poly in self.polys for p in poly[0]]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def contains(self, lon, lat):
        b = self.bbox
        if not (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]):
            return False
        for poly in self.polys:
            if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
                return True
        return False


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def load_okrugs():
    data = json.loads((ROOT / "districts.geojson").read_text(encoding="utf-8"))
    return [Okrug(f["properties"]["okrug"], f["geometry"]) for f in data["features"]]


def okrug_of(okrugs, lon, lat):
    for o in okrugs:
        if o.contains(lon, lat):
            return o
    return None


def cell_size(zoom, lat):
    lon_per_px = 360.0 / (256 * 2 ** zoom)
    w = CELL_PX * lon_per_px
    h = CELL_PX * lon_per_px * math.cos(math.radians(lat))
    return w, h


def cell_touches(okrugs, lon, lat, zoom):
    """Есть ли в квадрате хоть кусок нужных округов (проверка по 5x5 точкам)."""
    w, h = cell_size(zoom, lat)
    for i in range(5):
        for j in range(5):
            x = lon - w / 2 + w * i / 4
            y = lat - h / 2 + h * j / 4
            if any(o.contains(x, y) for o in okrugs):
                return True
    return False


def grid(okrugs, zoom):
    """Центры квадратов, покрывающих выбранные округа."""
    x0 = min(o.bbox[0] for o in okrugs)
    y0 = min(o.bbox[1] for o in okrugs)
    x1 = max(o.bbox[2] for o in okrugs)
    y1 = max(o.bbox[3] for o in okrugs)
    w, h = cell_size(zoom, (y0 + y1) / 2)
    cells = []
    y = y0 + h / 2
    while y - h / 2 < y1:
        x = x0 + w / 2
        while x - w / 2 < x1:
            if cell_touches(okrugs, x, y, zoom):
                cells.append((round(x, 6), round(y, 6), zoom))
            x += w
        y += h
    return cells


def split(lon, lat, zoom):
    """Делит квадрат на 4 квадрата следующего масштаба."""
    w, h = cell_size(zoom + 1, lat)
    return [
        (round(lon + dx * w / 2, 6), round(lat + dy * h / 2, 6), zoom + 1)
        for dx in (-1, 1) for dy in (-1, 1)
    ]
