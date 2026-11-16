"""Робот в видимом окне браузера: открывает поиск на Яндекс Картах в нужном квадрате,
листает список и забирает организации из ответов, которые сайт сам получает."""
import json
import random
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "data" / "browser-profile"  # отдельный чистый профиль, без вашего аккаунта


def pause(a, b):
    time.sleep(random.uniform(a, b))


def beep():
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(1200, 300)
            time.sleep(0.15)
    except Exception:
        print("\a", end="", flush=True)


def _find_search(node):
    """Ищет в JSON блок с результатами поиска (items + totalResultCount)."""
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            if isinstance(n.get("items"), list) and "totalResultCount" in n:
                return n
            stack.extend(n.values())
        elif isinstance(n, list):
            stack.extend(n)
    return None


class Browser:
    def __init__(self):
        self._pw = sync_playwright().start()
        try:
            self.ctx = self._pw.chromium.launch_persistent_context(
                str(PROFILE), headless=False, locale="ru-RU",
                viewport={"width": 1300, "height": 900},
            )
        except Exception:
            self._pw.stop()
            raise SystemExit(
                "\nНе удалось открыть браузер: похоже, программа уже запущена в другом окне.\n"
                "Дождитесь, пока она закончит, или остановите её (Ctrl+C) и запустите заново."
            )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self._batches = []
        self.page.on("response", self._on_response)

    def _on_response(self, r):
        if "/maps/api/search" not in r.url:
            return
        try:
            block = _find_search(r.json())
        except Exception:
            return
        if block:
            self._batches.append(block)

    def close(self):
        self.ctx.close()
        self._pw.stop()

    # --- капча: не обходим, ждём человека ---
    def _captcha(self):
        url = self.page.url
        if "showcaptcha" in url or "captcha" in url.split("?")[0]:
            return True
        try:
            return self.page.locator(".CheckboxCaptcha, .AdvancedCaptcha, form#checkbox-captcha-form").count() > 0
        except Exception:
            return False

    def wait_captcha(self):
        if not self._captcha():
            return False
        print("\n  ⚠ Яндекс спрашивает «Вы не робот?». Нажмите галочку в окне браузера — сбор продолжится сам.")
        beep()
        last = time.time()
        while self._captcha():
            time.sleep(2)
            if time.time() - last > 60:
                beep()
                last = time.time()
        print("  ✓ Продолжаю.")
        pause(3, 5)
        return True

    def search_cell(self, query, lon, lat, zoom, split_at=None):
        """Собирает все организации в квадрате. Возвращает (items, total).
        Если total > split_at — не листает, а сразу возвращает, чтобы квадрат разделили."""
        url = f"https://yandex.ru/maps/213/moscow/search/{quote(query)}/?ll={lon:.6f}%2C{lat:.6f}&z={zoom}"
        for attempt in range(3):
            self._batches = []
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            pause(3, 5)
            if self.wait_captcha():
                continue
            break

        found = {}
        total = None
        # первая страница лежит прямо в коде страницы
        try:
            raw = self.page.locator("script.state-view").first.text_content(timeout=15000)
            block = _find_search(json.loads(raw))
        except Exception:
            block = None
        if block:
            total = block.get("totalResultCount")
            for it in block["items"]:
                if it.get("type") == "business" and it.get("id"):
                    found[it["id"]] = it
        if total is None:
            # бывает, что список приходит отдельным запросом
            for _ in range(10):
                if self._batches:
                    break
                time.sleep(1)
        for b in self._batches:
            total = total if total is not None else b.get("totalResultCount")
            for it in b["items"]:
                if it.get("type") == "business" and it.get("id"):
                    found[it["id"]] = it
        total = total or 0

        if split_at and total > split_at:
            return list(found.values()), total

        # листаем список слева, пока не соберём всё
        idle = 0
        while len(found) < total and idle < 4:
            seen = len(self._batches)
            before = len(found)
            self.page.mouse.move(random.randint(150, 330), random.randint(350, 750))
            for _ in range(random.randint(3, 5)):
                self.page.mouse.wheel(0, random.randint(700, 1200))
                pause(0.2, 0.5)
            pause(2.0, 3.5)
            if self.wait_captcha():
                idle += 1
                continue
            for b in self._batches[seen:]:
                for it in b["items"]:
                    if it.get("type") == "business" and it.get("id"):
                        found[it["id"]] = it
            idle = idle + 1 if len(found) == before else 0
        return list(found.values()), total


def to_row(it):
    """Нужные поля из ответа Яндекса."""
    phones = ", ".join(p.get("number") or p.get("value") or "" for p in (it.get("phones") or []))
    seo = it.get("seoname") or "org"
    site = (it.get("urls") or [""])[0] if isinstance(it.get("urls"), list) else ""
    cats = ", ".join(c.get("name", "") for c in (it.get("categories") or []))
    lon, lat = (it.get("coordinates") or [0, 0])[:2]
    return {
        "id": str(it["id"]),
        "title": it.get("title", ""),
        "phones": phones,
        "address": it.get("address") or it.get("fullAddress") or "",
        "url": f"https://yandex.ru/maps/org/{seo}/{it['id']}/",
        "site": site,
        "categories": cats,
        "lon": lon,
        "lat": lat,
    }
