"""Создаёт config.json с новым паролем и готовый к вставке скрипт data/Code-для-вставки.gs."""
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg_path = ROOT / "config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else json.loads(
    (ROOT / "config.example.json").read_text(encoding="utf-8"))
if not cfg.get("token") or "пароль" in cfg["token"]:
    cfg["token"] = secrets.token_urlsafe(24)
if "ВАШ_ID" in cfg.get("webapp_url", ""):
    cfg["webapp_url"] = ""
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

code = (ROOT / "apps-script" / "Code.gs").read_text(encoding="utf-8")
code = code.replace("var TOKEN_INLINE = '';", f"var TOKEN_INLINE = '{cfg['token']}';")
(ROOT / "data").mkdir(exist_ok=True)
out = ROOT / "data" / "Code-для-вставки.gs"
out.write_text(code, encoding="utf-8")
print("готово:", out)
