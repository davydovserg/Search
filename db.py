"""Локальная база: найденные организации и пройденные квадраты (для продолжения)."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
(ROOT / "data").mkdir(exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    query TEXT, id TEXT, title TEXT, phones TEXT, address TEXT, url TEXT,
    site TEXT, categories TEXT, lon REAL, lat REAL, okrug TEXT, segment TEXT,
    sent INTEGER DEFAULT 0, PRIMARY KEY (query, id)
);
CREATE TABLE IF NOT EXISTS cells (
    query TEXT, key TEXT, total INTEGER, got INTEGER, PRIMARY KEY (query, key)
);
"""


def connect():
    con = sqlite3.connect(ROOT / "data" / "results.db")
    con.executescript(SCHEMA)
    return con


def cell_key(lon, lat, zoom):
    return f"{zoom}:{lon:.6f}:{lat:.6f}"


def cell_done(con, query, key):
    return con.execute("SELECT 1 FROM cells WHERE query=? AND key=?", (query, key)).fetchone() is not None


def mark_cell(con, query, key, total, got):
    con.execute("INSERT OR REPLACE INTO cells VALUES (?,?,?,?)", (query, key, total, got))
    con.commit()


def save_org(con, query, o):
    """Возвращает True, если организация новая."""
    cur = con.execute(
        "INSERT OR IGNORE INTO orgs (query,id,title,phones,address,url,site,categories,lon,lat,okrug,segment)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (query, o["id"], o["title"], o["phones"], o["address"], o["url"], o["site"],
         o["categories"], o["lon"], o["lat"], o["okrug"], o["segment"]),
    )
    con.commit()
    return cur.rowcount == 1


def unsent(con, query):
    return con.execute(
        "SELECT segment,okrug,title,phones,address,url,site,categories,id FROM orgs"
        " WHERE query=? AND sent=0 ORDER BY segment, okrug, title", (query,)
    ).fetchall()


def all_rows(con, query):
    return con.execute(
        "SELECT segment,okrug,title,phones,address,url,site,categories,id FROM orgs"
        " WHERE query=? ORDER BY segment, okrug, title", (query,)
    ).fetchall()


def mark_sent(con, query, ids):
    con.executemany("UPDATE orgs SET sent=1 WHERE query=? AND id=?", [(query, i) for i in ids])
    con.commit()
