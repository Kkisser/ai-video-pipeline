"""Сбор референсов из источников → запись в базу.

Платформы: tiktok (актор clockworks) и reels (Instagram, актор apify/instagram-scraper).
Источники: keyword | hashtag | author.
"""
from __future__ import annotations
import json, urllib.request
from datetime import date, timedelta

from . import db

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
    """platform: tiktok | reels. source_type: keyword | hashtag | author."""
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
