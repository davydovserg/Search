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


# ---- тематика: каждая организация — в лист своей тематики ----
# Порядок важен: срабатывает первое совпадение по категориям с Яндекса.
# Бьюти идёт в основную вкладку (contacts), остальное — в листы по названию (создаются сами).
THEMES = [
    ("beauty", None, r"красот|бьюти|beauty|ногт|маникюр|педикюр|nail|космет|эпиляц|депиляц|шугаринг|"
                     r"барбер|парикмах|стрижк|бров|ресниц|визаж|макияж|стилист|солярий|загар|спа|массаж|"
                     r"перманент|татуаж|тату|пирсинг|lash|brow|эстетик"),
    ("food", "Еда", r"кафе|ресторан|питани|столов|пекарн|кофейн|кофе|пиццер|суши|роллы|шаурм|шаверм|"
                    r"бургер|кондитер|доставка еды|фастфуд|закусочн|блинн|пельмен|хинкал|чайхан|гриль|кулинари"),
    ("auto", "Авто", r"авто|шиномонтаж|шины|диски|кузов|тонировк|детейлинг|эвакуатор|мото|газов.. оборудован"),
    ("sport", "Спорт", r"спорт|фитнес|тренаж|йог|пилатес|танц|бассейн|единоборств|бокс|карате|дзюдо|"
                       r"борьб|тренер|стадион|теннис|скалодром|кроссфит|секци|бойцов"),
    ("med", "Медицина", r"стоматолог|клиник|медицин|поликлиник|больниц|врач|диагност|анализ|ветеринар|"
                        r"ортодонт|офтальмолог|оптик|психолог|лечебн|реабилитац"),
    ("edu", "Обучение и дети", r"школ|курс|обучени|репетитор|детск|развивающ|языков|учебн|образоват|"
                               r"кружок|творческ|студия рисования|логопед"),
    ("serv", "Бытовые услуги", r"ремонт|химчистк|прачечн|ателье|швейн|обув|изготовление ключ|клининг|уборк|"
                               r"мастерск|фотостуди|фотоуслуг|полиграф|копи|бытов|сантехник|электрик|"
                               r"грузоперевоз|переезд|натяжн|окна|двери"),
]
THEMES = [(k, sheet, re.compile(rx, re.I)) for k, sheet, rx in THEMES]
OTHER = ("other", "Другое")

# совсем не нужно — пропускаем (не пишем ни в один лист)
SKIP_CAT_RE = re.compile(
    r"супермаркет|гипермаркет|продуктов|магазин продуктов|минимаркет|пункт выдачи|постамат|"
    r"табак|табачн|вейп|кальян|пив[оаеуы]|пивн|алкогол|винн|вино|ликёр|ликер|паб", re.I)
SKIP_NAME_RE = re.compile(
    r"^\W*(пят[её]рочка|магнит|перекр[её]сток|дикси|ашан|лента|вкусвилл|азбука вкуса|верный|spar|"
    r"окей|о'кей|билла|fix price|фикс прайс|красное.{0,3}белое|бристоль|ozon|озон|wildberries|"
    r"вайлдберриз|яндекс маркет|сбермаркет|самокат|мегамаркет)", re.I)


def theme_of(categories, title=""):
    """Ключ тематики ('beauty', 'food', …, 'other') или None — организацию пропускаем."""
    c = categories or ""
    if SKIP_NAME_RE.search(title or ""):
        return None
    for key, _sheet, rx in THEMES:
        if rx.search(c):
            return key
    if SKIP_CAT_RE.search(c):
        return None
    return OTHER[0]


def sheet_of(theme):
    """Имя листа для тематики (для beauty — None: основная вкладка)."""
    if theme == OTHER[0]:
        return OTHER[1]
    return next(sheet for key, sheet, _ in THEMES if key == theme)


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
