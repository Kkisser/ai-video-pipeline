"""Визуальные модели (Ollama) для «Разобрать»: реестр, готовность, установка.

whisper для реплик у пользователя уже есть — тут только VLM-часть (Ollama + Qwen2.5-VL).
Ollama на Apple Silicon ставится через brew в /opt/homebrew — без пароля.
"""
from __future__ import annotations
import json, shutil, subprocess, time, urllib.request

OLLAMA_URL = "http://localhost:11434"

# Сменный «мозг». По умолчанию — 7B (рекомендованная).
MODELS = [
    {"tag": "qwen2.5vl:3b", "label": "Qwen2.5-VL 3B", "size": "~2.5 ГБ", "rec": False,
     "note": "легче и быстрее, качество ниже"},
    {"tag": "qwen2.5vl:7b", "label": "Qwen2.5-VL 7B", "size": "~5 ГБ", "rec": True,
     "note": "рекомендуется — баланс для Mac M4"},
    {"tag": "qwen2.5vl:32b", "label": "Qwen2.5-VL 32B", "size": "~20 ГБ", "rec": False,
     "note": "точнее, но тяжёлая (нужно много RAM/диска)"},
]
DEFAULT_TAG = "qwen2.5vl:7b"

# Прогресс установки для показа в панели.
INSTALL = {"running": False, "tag": "", "msg": ""}


def ollama_ready() -> bool:
    return shutil.which("ollama") is not None


def _serving() -> bool:
    try:
        urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


def ensure_serving() -> bool:
    """Поднять `ollama serve` в фоне, если ещё не запущен."""
    if _serving():
        return True
    if not ollama_ready():
        return False
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.5)
        if _serving():
            return True
    return False


def installed_tags() -> list[str]:
    if not ensure_serving():
        return []
    try:
        data = json.load(urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5))
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def model_ready(tag: str = DEFAULT_TAG) -> bool:
    tags = installed_tags()
    return any(t == tag or t.startswith(tag) for t in tags)


def ensure_stack(tag: str = DEFAULT_TAG) -> None:
    """Доустановить всё для разбора: Ollama (если нет) → serve → pull модели. Блокирующе."""
    INSTALL.update(running=True, tag=tag, msg="Проверяю Ollama…")
    try:
        if not ollama_ready():
            INSTALL["msg"] = "Устанавливаю Ollama (brew)…"
            subprocess.run(["brew", "install", "ollama"], capture_output=True, text=True, timeout=1200)
        if not ensure_serving():
            INSTALL["msg"] = "Не удалось запустить Ollama"
            return
        if model_ready(tag):
            INSTALL["msg"] = "Модель уже установлена"
            return
        INSTALL["msg"] = f"Скачиваю модель {tag} (может занять несколько минут)…"
        # ollama pull печатает прогресс в stderr — стримим последнюю строку в статус
        p = subprocess.Popen(["ollama", "pull", tag], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:  # type: ignore
            line = line.strip()
            if line:
                INSTALL["msg"] = f"{tag}: {line[:80]}"
        p.wait()
        INSTALL["msg"] = "Модель установлена" if model_ready(tag) else "Ошибка установки модели"
    except Exception as e:  # noqa: BLE001
        INSTALL["msg"] = f"Ошибка установки: {e}"
    finally:
        INSTALL["running"] = False
