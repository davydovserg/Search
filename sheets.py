"""Запись в Google Таблицу через ваш Apps Script (см. apps-script/Code.gs) и в CSV.

Формат строк — как во вкладке contacts таблицы «красота»:
key | name | category | address | phones | phone_1 | phone_2 | phone_3 | note | url
В note пишется «Сторона · Округ».
"""
import csv
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
HEADER = ["key", "name", "category", "address", "phones", "phone_1", "phone_2", "phone_3", "note", "url"]


def load_config():
    p = ROOT / "config.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def normalize_phones(phones):
    nums = []
    for p in (phones or "").split(","):
        d = re.sub(r"\D", "", p)
        if len(d) == 11 and d[0] in "78":
            nums.append("+7" + d[1:])
        elif d:
            nums.append("+" + d)
    return nums


def to_contact_row(segment, okrug, title, phones, address, url, site, categories, oid):
    nums = normalize_phones(phones)
    url = url.rstrip("/")
    return [
        url.replace("https://", ""),
        title,
        (categories or "").split(",")[0].strip(),
        f"{address}, Москва" if address else "",
        "; ".join(nums),
        *(nums + ["", "", ""])[:3],
        f"{segment} · {okrug}",
        url,
    ]


# ---- тематика: всё бьюти — в основную вкладку, остальное — в свои листы ----
BEAUTY_RE = re.compile(
    r"красот|бьюти|beauty|ногт|маникюр|педикюр|nail|космет|эпиляц|депиляц|шугаринг|воск|"
    r"барбер|парикмах|стрижк|бров|ресниц|визаж|макияж|стилист|солярий|загар|спа|массаж|"
    r"перманент|татуаж|тату|пирсинг|lash|brow|эстетик", re.I)
FOOD_RE = re.compile(
    r"кафе|ресторан|питани|столов|пекарн|кофейн|кофе|бар|паб|пиццер|суши|роллы|шаурм|шаверм|"
    r"бургер|кондитер|доставка еды|фастфуд|закусочн|блинн|пельмен|хинкал|чайхан|гриль", re.I)
OTHER_SHEETS = {"food": "Еда", "other": "Другое"}


def is_beauty_query(query):
    return bool(BEAUTY_RE.search(query or "")) or "салон" in (query or "").lower()


def theme_of(categories):
    """beauty | food | other — по всем категориям организации с Яндекса."""
    c = categories or ""
    if BEAUTY_RE.search(c):
        return "beauty"
    if FOOD_RE.search(c):
        return "food"
    return "other"


def write_csv(query, rows):
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    path = out / (safe_name(query) + ".csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(HEADER)
        w.writerows(to_contact_row(*r) for r in rows)
    return path


def safe_name(s):
    return "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in s).strip()[:90] or "query"


def send(cfg, rows, sheet_name=None, gid=None, batch=300):
    """Отправляет строки пачками. Возвращает ID отправленных организаций."""
    url, token = cfg.get("webapp_url"), cfg.get("token")
    if not url or not token:
        raise RuntimeError("Нет webapp_url/token в config.json — см. README, раздел «Google Таблица».")
    sent, added = [], 0
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        r = requests.post(url, data=json.dumps({
            "token": token,
            "spreadsheetId": cfg.get("spreadsheet_id"),
            "gid": gid,
            "sheet": sheet_name,
            "rows": [to_contact_row(*x) for x in part],
        }, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=180)
        r.raise_for_status()
        res = r.json()
        if not res.get("ok"):
            raise RuntimeError("Таблица ответила ошибкой: " + str(res.get("error")))
        added += res.get("added", 0)
        sent += [x[-1] for x in part]
    print(f"  добавлено новых строк: {added}, пропущено дублей: {len(sent) - added}")
    return sent
