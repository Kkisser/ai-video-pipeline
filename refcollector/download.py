"""Скачивание отмеченных роликов через yt-dlp в data/downloads/<профиль>/."""
from __future__ import annotations
import re, subprocess
from pathlib import Path

from . import db

YTDLP = str(Path(__file__).resolve().parent.parent / "flowbatch" / ".venv" / "bin" / "yt-dlp")
FMT = "best[ext=mp4]/best"


def _safe(s: str) -> str:
    return re.sub(r"[^\w.-]+", "_", (s or "")).strip("_")[:40] or "ref"


def download_ref(c, row) -> str | None:
    """Скачать один ролик; вернуть путь к файлу или None."""
    prof_dir = db.DOWNLOADS_DIR / _safe(row["profile"] or "default")
    prof_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{row['id']:04d}_{row['platform']}_{_safe(row['author'])}"
    out = prof_dir / (stem + ".%(ext)s")
    r = subprocess.run([YTDLP, row["url"], "-f", FMT, "-o", str(out)],
                       capture_output=True, text=True)
    files = list(prof_dir.glob(stem + ".*"))
    if not files:
        return None
    path = str(files[0])
    db.set_status(c, row["id"], "downloaded")
    c.execute("UPDATE refs SET file=? WHERE id=?", (path, row["id"]))
    c.commit()
    return path


def download_picked(profile: str | None = None) -> dict:
    """Скачать все отмеченные (status=picked)."""
    c = db.conn()
    rows = db.list_refs(c, profile=profile, status="picked", limit=1000)
    ok = fail = 0
    for row in rows:
        try:
            ok += 1 if download_ref(c, row) else 0
        except Exception:
            fail += 1
    c.close()
    return {"picked": len(rows), "downloaded": ok, "failed": fail + (len(rows) - ok)}
