"""Хранение API-ключей локально (data/keys.json, вне git) + проверка остатка.

Ключи можно задать в панели или через переменные окружения (APIFY_TOKEN и т.п.).
"""
from __future__ import annotations
import json, os, urllib.request
from .db import DATA_DIR, ensure_dirs

KEYS_FILE = DATA_DIR / "keys.json"

# средняя цена: ~$0.30 за 1000 роликов у Apify TikTok-скрапера
USD_PER_VIDEO = 0.30 / 1000

LINKS = {
    "apify": "https://console.apify.com/settings/integrations",
    "ensembledata": "https://dashboard.ensembledata.com/",
}


def load() -> dict:
    ensure_dirs()
    if KEYS_FILE.exists():
        try:
            return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save(name: str, value: str) -> None:
    d = load()
    d[name] = (value or "").strip()
    ensure_dirs()
    KEYS_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def get(name: str, env: str | None = None) -> str:
    v = load().get(name, "")
    if not v and env:
        v = os.environ.get(env, "")
    return v


def apify_remaining(token: str) -> dict | None:
    """Остаток месячного лимита Apify: сколько $ и ≈ сколько роликов ещё можно."""
    if not token:
        return None
    try:
        req = urllib.request.Request(f"https://api.apify.com/v2/users/me/limits?token={token}")
        d = json.load(urllib.request.urlopen(req, timeout=12)).get("data", {})
        limit = float(d.get("limits", {}).get("maxMonthlyUsageUsd", 0) or 0)
        used = float(d.get("current", {}).get("monthlyUsageUsd", 0) or 0)
        remaining = max(0.0, limit - used)
        return {"remaining_usd": remaining, "limit": limit, "used": used,
                "videos": int(remaining / USD_PER_VIDEO) if USD_PER_VIDEO else 0}
    except Exception:
        return None
