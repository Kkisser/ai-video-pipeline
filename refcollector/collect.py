"""Сбор референсов из источников → запись в базу.

Платформы: tiktok (актор clockworks) и reels (Instagram, актор apify/instagram-scraper).
Источники: keyword | hashtag | author.
"""
from __future__ import annotations
import json, subprocess, urllib.request
from datetime import date, timedelta
from pathlib import Path

from . import db

YTDLP = str(Path(__file__).resolve().parent.parent / "flowbatch" / ".venv" / "bin" / "yt-dlp")


def _youtube_rows(value: str, n: int, days: int) -> list[dict]:
    """Поиск на YouTube через yt-dlp (быстро, flat). Превью строим из id ролика.

    days/вертикаль для YouTube не фильтруются (flat не отдаёт дату/размеры) —
    для Shorts ориентируемся на длительность и просмотры.
    """
    cmd = [YTDLP, f"ytsearch{n}:{value}", "--flat-playlist", "--no-warnings", "--ignore-errors",
           "--print", "%(view_count)s\t%(duration)s\t%(uploader)s\t%(id)s\t%(title)s"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) != 5:
            continue
        views, dur, uploader, vid, title = p
        if not vid or vid == "NA":
            continue
        rows.append({
            "platform": "youtube", "url": f"https://www.youtube.com/watch?v={vid}",
            "author": uploader.strip(), "text": title.strip(),
            "views": int(views) if views.isdigit() else 0, "likes": 0, "comments": 0,
            "date": "", "duration": int(dur) if dur.isdigit() else 0,
            "width": 0, "height": 0, "hashtags": "", "sound": "",
            "cover": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        })
    return rows

ACTORS = {
    "tiktok": "clockworks~tiktok-scraper",
    "reels": "apify~instagram-scraper",
}
API = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}"


def _run(actor: str, token: str, payload: dict) -> list[dict]:
    req = urllib.request.Request(
        API.format(actor, token), data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def _g(d: dict, *keys, default=0):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def _tiktok_payload(source_type: str, value: str, n: int) -> dict:
    p = {"resultsPerPage": n, "shouldDownloadVideos": False,
         "shouldDownloadCovers": False, "shouldDownloadSubtitles": False}
    if source_type == "keyword":
        p["searchQueries"] = [value]
    elif source_type == "hashtag":
        p["hashtags"] = [value.lstrip("#")]
    elif source_type == "author":
        p["profiles"] = [value.lstrip("@")]
    return p


def _tiktok_row(it: dict) -> dict:
    meta = it.get("videoMeta") or {}
    hashtags = " ".join("#" + t.get("name", "") for t in (it.get("hashtags") or []))
    return {
        "platform": "tiktok", "url": _g(it, "webVideoUrl", default=""),
        "author": (it.get("authorMeta") or {}).get("name", ""),
        "text": (_g(it, "text", default="") or "")[:500],
        "views": _g(it, "playCount"), "likes": _g(it, "diggCount"),
        "comments": _g(it, "commentCount"),
        "date": (_g(it, "createTimeISO", default="") or "")[:10],
        "duration": int(_g(meta, "duration")), "width": _g(meta, "width"),
        "height": _g(meta, "height"), "hashtags": hashtags,
        "sound": (it.get("musicMeta") or {}).get("musicName", ""),
        "cover": _g(meta, "coverUrl", "originalCoverUrl", default=""),
    }


def _reels_payload(source_type: str, value: str, n: int) -> dict:
    # Instagram: дискавери по хэштегу; по автору — directUrls на профиль.
    if source_type == "author":
        return {"directUrls": [f"https://www.instagram.com/{value.lstrip('@')}/"],
                "resultsType": "posts", "resultsLimit": n, "addParentData": False}
    # keyword и hashtag → страница хэштега через directUrls (работает надёжнее search)
    tag = value.lstrip("#").replace(" ", "")
    return {"directUrls": [f"https://www.instagram.com/explore/tags/{tag}/"],
            "resultsType": "posts", "resultsLimit": n, "addParentData": False}


def _reels_row(it: dict) -> dict:
    hashtags = " ".join("#" + h for h in (it.get("hashtags") or []))
    music = it.get("musicInfo") or {}
    return {
        "platform": "reels", "url": _g(it, "url", default=""),
        "author": _g(it, "ownerUsername", default=""),
        "text": (_g(it, "caption", default="") or "")[:500],
        "views": _g(it, "videoViewCount", "videoPlayCount"),
        "likes": _g(it, "likesCount"), "comments": _g(it, "commentsCount"),
        "date": (_g(it, "timestamp", default="") or "")[:10],
        "duration": int(_g(it, "videoDuration") or 0),
        "width": _g(it, "dimensionsWidth"), "height": _g(it, "dimensionsHeight"),
        "hashtags": hashtags,
        "sound": (music.get("song_name") or music.get("artist_name") or ""),
        "cover": _g(it, "displayUrl", default=""),
    }


def collect(platform: str, source_type: str, value: str, *, token: str,
            profile: str = "default", n: int = 30, days: int = 0, max_sec: int = 0,
            vertical: bool = False, min_views: int = 0) -> dict:
    """platform: tiktok | reels | youtube. source_type: keyword | hashtag | author."""
    if platform == "youtube":
        rows_raw = _youtube_rows(value, n, days)
        c = db.conn()
        kept = new = 0
        for row in rows_raw:
            if max_sec and not (0 < row["duration"] <= max_sec):
                continue
            # вертикаль для YouTube не определяем (flat не отдаёт размеры) — не фильтруем
            if min_views and (row["views"] or 0) < min_views:
                continue
            row["profile"] = profile
            row["source"] = f"youtube/{source_type}:{value}"
            new += int(db.upsert(c, row))
            kept += 1
        c.close()
        return {"got": len(rows_raw), "kept": kept, "new": new}
    if platform not in ACTORS:
        raise ValueError(f"неизвестная платформа: {platform}")
    if platform == "tiktok":
        payload, to_row = _tiktok_payload(source_type, value, n), _tiktok_row
    else:
        payload, to_row = _reels_payload(source_type, value, n), _reels_row

    items = _run(ACTORS[platform], token, payload)
    cutoff = (date.today() - timedelta(days=days)).isoformat() if days else None

    c = db.conn()
    kept = new = 0
    for it in items:
        row = to_row(it)
        # для reels берём только видео (не картинки-посты)
        if platform == "reels" and it.get("type") != "Video":
            continue
        if cutoff and (not row["date"] or row["date"] < cutoff):
            continue
        if max_sec and not (0 < row["duration"] <= max_sec):
            continue
        if vertical and not (row["height"] > row["width"] > 0):
            continue
        if min_views and (row["views"] or 0) < min_views:
            continue
        if not row["url"]:
            continue
        kept += 1
        row["profile"] = profile
        row["source"] = f"{platform}/{source_type}:{value}"
        new += int(db.upsert(c, row))
    c.close()
    return {"got": len(items), "kept": kept, "new": new}
