"""SQLite-база референсов. Одна строка = один ролик-кандидат."""
from __future__ import annotations
import sqlite3
from pathlib import Path

# Всё локальное хранилище — в одной структурированной папке data/:
#   data/refs.db            — таблица-база
#   data/downloads/<профиль>/  — скачанные ролики
#   data/exports/           — выгрузки CSV
#   data/transcripts/       — расшифровки (позже)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "refs.db"
DOWNLOADS_DIR = DATA_DIR / "downloads"
EXPORTS_DIR = DATA_DIR / "exports"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"


def ensure_dirs() -> None:
    for d in (DATA_DIR, DOWNLOADS_DIR, EXPORTS_DIR, TRANSCRIPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS refs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  platform   TEXT,            -- tiktok / reels / youtube
  url        TEXT UNIQUE,     -- ключ уникальности
  author     TEXT,
  text       TEXT,
  views      INTEGER,
  likes      INTEGER,
  comments   INTEGER,
  date       TEXT,            -- YYYY-MM-DD
  duration   INTEGER,
  width      INTEGER,
  height     INTEGER,
  hashtags   TEXT,
  sound      TEXT,
  cover      TEXT,            -- URL обложки (превью)
  status     TEXT DEFAULT 'new',  -- new / picked / downloaded / analyzed
  file       TEXT,            -- локальный путь после скачивания
  transcript TEXT,
  analysis   TEXT,
  profile    TEXT,            -- под какой профиль бренда собрано
  source     TEXT,            -- как нашли: keyword:... / hashtag:... / author:...
  added_at   TEXT DEFAULT (datetime('now'))
);
"""


def conn(path: Path = DB_PATH) -> sqlite3.Connection:
    ensure_dirs()
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=8000")  # ждать блокировку, а не падать
    c.executescript(SCHEMA)
    # миграция для старых баз без колонки cover
    try:
        c.execute("ALTER TABLE refs ADD COLUMN cover TEXT")
        c.commit()
    except sqlite3.OperationalError:
        pass
    return c


def upsert(c: sqlite3.Connection, row: dict) -> bool:
    """Вставить ролик; при повторной ссылке — обновить метрики. True если новый."""
    cols = ["platform", "url", "author", "text", "views", "likes", "comments",
            "date", "duration", "width", "height", "hashtags", "sound", "cover",
            "profile", "source"]
    vals = [row.get(k) for k in cols]
    cur = c.execute(
        f"INSERT INTO refs ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
        "ON CONFLICT(url) DO UPDATE SET views=excluded.views, likes=excluded.likes, "
        "comments=excluded.comments, cover=excluded.cover",
        vals,
    )
    c.commit()
    return cur.rowcount == 1 and cur.lastrowid is not None


def list_refs(c: sqlite3.Connection, profile: str | None = None,
              status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    q, args = "SELECT * FROM refs", []
    where = []
    if profile:
        where.append("profile=?"); args.append(profile)
    if status:
        where.append("status=?"); args.append(status)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY views DESC LIMIT ?"; args.append(limit)
    return c.execute(q, args).fetchall()


def clear_all(c: sqlite3.Connection, profile: str | None = None) -> int:
    if profile:
        cur = c.execute("DELETE FROM refs WHERE profile=?", (profile,))
    else:
        cur = c.execute("DELETE FROM refs")
    c.commit()
    return cur.rowcount


def set_status(c: sqlite3.Connection, ref_id: int, status: str) -> None:
    c.execute("UPDATE refs SET status=? WHERE id=?", (status, ref_id))
    c.commit()


def counts(c: sqlite3.Connection) -> dict:
    rows = c.execute("SELECT status, COUNT(*) n FROM refs GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def export_csv(profile: str | None = None) -> Path:
    """Выгрузить базу в CSV (открывается в Excel). Файл — в data/exports/."""
    import csv
    ensure_dirs()
    c = conn()
    rows = db_all(c, profile)
    c.close()
    cols = ["id", "platform", "url", "author", "text", "views", "likes", "comments",
            "date", "duration", "width", "height", "hashtags", "sound", "status",
            "file", "profile", "source", "added_at"]
    path = EXPORTS_DIR / ((profile or "all") + ".csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig — Excel читает кириллицу
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[k] for k in cols])
    return path


def db_all(c: sqlite3.Connection, profile: str | None = None) -> list[sqlite3.Row]:
    if profile:
        return c.execute("SELECT * FROM refs WHERE profile=? ORDER BY views DESC", (profile,)).fetchall()
    return c.execute("SELECT * FROM refs ORDER BY views DESC").fetchall()
