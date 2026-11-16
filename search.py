"""Сбор организаций Москвы с Яндекс Карт по любому запросу.

Примеры:
    python search.py "салоны красоты"
    python search.py "салоны красоты" --okrug ЦАО
    python search.py "автозапчасти" --segment Север
    python search.py "салоны красоты" --only-send      # только дослать в таблицу
"""
import argparse
import random
import sys
import time
from collections import deque

import db
import geo
import sheets
from yamaps import Browser, pause, to_row

START_ZOOM = 14
MAX_ZOOM = 17
# Яндекс показывает на один участок карты лишь ~60–90 мест. Если их столько или больше,
# значит показали не всё — делим квадрат на 4 помельче.
SPLIT_AT = 50


def main():
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    ap = argparse.ArgumentParser(description="Сбор организаций с Яндекс Карт")
    ap.add_argument("query", help="что искать, например «салоны красоты»")
    ap.add_argument("--okrug", nargs="*", help="только эти округа: ЦАО САО СВАО СЗАО ВАО ЮВАО ЮАО ЮЗАО ЗАО ЗелАО НАО ТАО")
    ap.add_argument("--segment", nargs="*", help="только эти стороны: Центр Север Восток Юг Запад")
    ap.add_argument("--max-cells", type=int, default=0, help="остановиться после N квадратов (для пробы)")
    ap.add_argument("--no-sheet", action="store_true", help="не отправлять в Google Таблицу, только CSV")
    ap.add_argument("--only-send", action="store_true", help="не собирать, только отправить несохранённое")
    ap.add_argument("--gid", help="ID вкладки таблицы (число после gid= в ссылке)")
    ap.add_argument("--sheet", help="имя вкладки (создастся, если нет)")
    a = ap.parse_args()

    query = a.query.strip()
    con = db.connect()
    cfg = sheets.load_config()

    okrugs = geo.load_okrugs()
    if a.okrug:
        want = {x.lower() for x in a.okrug}
        okrugs = [o for o in okrugs if o.short.lower() in want]
    if a.segment:
        want = {x.lower() for x in a.segment}
        okrugs = [o for o in okrugs if o.segment.lower() in want]
    if not okrugs:
        sys.exit("Не нашёл таких округов/сторон. Смотрите список в --help.")
    names = {o.short for o in okrugs}

    if not a.only_send:
        collect(con, query, okrugs, names, a.max_cells)

    rows = db.all_rows(con, query)
    path = sheets.write_csv(query, rows)
    with_phone = sum(1 for r in rows if r[3])
    print(f"\nВсего по запросу «{query}»: {len(rows)} организаций, с телефоном: {with_phone}")
    print(f"CSV: {path}")

    if a.no_sheet:
        return
    if not cfg.get("webapp_url"):
        print("Google Таблица не настроена (config.json) — данные пока только в CSV. См. README.")
        return
    gid = a.gid or (cfg.get("tabs") or {}).get(query.lower())
    sheet_name = a.sheet or (None if gid else query[:1].upper() + query[1:])
    todo = db.unsent(con, query)
    if not todo:
        print("В таблицу отправлять нечего — всё уже там.")
        return
    ids = sheets.send(cfg, todo, sheet_name=sheet_name, gid=gid)
    db.mark_sent(con, query, ids)
    print(f"Отправлено в Google Таблицу: {len(ids)}")


def collect(con, query, okrugs, names, max_cells):
    cells = deque(geo.grid(okrugs, START_ZOOM))
    print(f"Запрос «{query}», округа: {', '.join(sorted(names))}. Квадратов для начала: {len(cells)}")
    br = Browser()
    done_now = 0
    try:
        while cells:
            lon, lat, z = cells.popleft()
            key = db.cell_key(lon, lat, z)
            row = con.execute("SELECT got FROM cells WHERE query=? AND key=?", (query, key)).fetchone()
            if row is not None:
                if row[0] == -1:  # квадрат делили — продолжаем по его частям
                    cells.extendleft(reversed(geo.split(lon, lat, z)))
                continue
            if z > START_ZOOM and not geo.cell_touches(okrugs, lon, lat, z):
                continue

            items, total = br.search_cell(query, lon, lat, z, split_at=SPLIT_AT if z < MAX_ZOOM else None)
            new = 0
            for it in items:
                r = to_row(it)
                o = geo.okrug_of(okrugs, r["lon"], r["lat"])
                if not o or o.short not in names:
                    continue
                r["okrug"], r["segment"] = o.short, o.segment
                new += db.save_org(con, query, r)
            if total > SPLIT_AT and z < MAX_ZOOM:
                db.mark_cell(con, query, key, total, -1)
                cells.extendleft(reversed(geo.split(lon, lat, z)))
                print(f"  квадрат {key}: {total}+ мест, новых {new} — делю на 4 помельче")
                pause(2, 4)
                continue
            db.mark_cell(con, query, key, total, len(items))
            done_now += 1
            n = con.execute("SELECT COUNT(*) FROM orgs WHERE query=?", (query,)).fetchone()[0]
            print(f"  квадрат {key}: в списке {len(items)}/{total}, новых {new}. Всего собрано: {n}. Осталось квадратов: {len(cells)}")
            if max_cells and done_now >= max_cells:
                print("Достигнут лимит --max-cells, останавливаюсь.")
                break
            pause(3, 7)
            if random.random() < 0.08:  # иногда передышка подольше, как у человека
                pause(15, 35)
    except KeyboardInterrupt:
        print("\nОстановлено. Следующий запуск продолжит с этого места.")
    finally:
        br.close()


if __name__ == "__main__":
    main()
