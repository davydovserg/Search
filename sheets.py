"""Запись в Google Таблицу через ваш Apps Script (см. apps-script/Code.gs) и в CSV."""
import csv
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
HEADER = ["Сегмент", "Округ", "Название", "Телефон", "Адрес", "Ссылка", "Сайт", "Категории", "ID"]


def load_config():
    p = ROOT / "config.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_csv(query, rows):
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    path = out / (safe_name(query) + ".csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(HEADER)
        w.writerows(rows)
    return path


def safe_name(s):
    return "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in s).strip()[:90] or "query"


def send(cfg, rows, sheet_name=None, gid=None, batch=300):
    """Отправляет строки пачками. Возвращает список ID, которые таблица приняла."""
    url, token = cfg.get("webapp_url"), cfg.get("token")
    if not url or not token:
        raise RuntimeError("Нет webapp_url/token в config.json — см. README, раздел «Google Таблица».")
    accepted = []
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        r = requests.post(url, data=json.dumps({
            "token": token,
            "spreadsheetId": cfg.get("spreadsheet_id"),
            "gid": gid,
            "sheet": sheet_name,
            "header": HEADER,
            "rows": [list(x) for x in part],
        }, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=120)
        r.raise_for_status()
        res = r.json()
        if not res.get("ok"):
            raise RuntimeError("Таблица ответила ошибкой: " + str(res.get("error")))
        accepted += [x[-1] for x in part]
    return accepted
