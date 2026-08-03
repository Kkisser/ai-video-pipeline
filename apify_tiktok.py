#!/usr/bin/env python3
"""apify_tiktok.py — поиск трендовых TikTok-роликов через Apify (вариант 2).

Дискавери именно в TikTok (то, что yt-dlp не умеет). Использует готовый актор
маркетплейса Apify. Нужен бесплатный API-токен (apify.com → Settings → API).

Запуск:
  APIFY_TOKEN=apify_api_xxx .venv/bin/python apify_tiktok.py "стоматолог" --n 20 --max-sec 60 --vertical

Расход: в пределах бесплатных $5/мес (~$0.30 за 1000 роликов). Скачивание видео
выключено (shouldDownloadVideos=False), чтобы не жечь кредиты.
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request

ACTOR = "clockworks~tiktok-scraper"   # популярный актор; можно сменить на apidojo~tiktok-scraper
API = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items?token={}"


def run(token: str, query: str, n: int) -> list[dict]:
    payload = {
        "searchQueries": [query],
        "resultsPerPage": n,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    req = urllib.request.Request(
        API.format(ACTOR, token),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def g(d: dict, *keys, default=0):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--max-sec", type=int, default=0)
    ap.add_argument("--days", type=int, default=0, help="только за последние N дней")
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        sys.exit("НЕТ ТОКЕНА. Запусти:  APIFY_TOKEN=apify_api_xxx python apify_tiktok.py ...")

    print(f"🔎 Apify · TikTok · «{args.query}» (n={args.n})…")
    items = run(token, args.query, args.n)

    rows = []
    for it in items:
        meta = it.get("videoMeta") or {}
        rows.append({
            "views": g(it, "playCount"),
            "likes": g(it, "diggCount"),
            "duration": g(meta, "duration"),
            "width": g(meta, "width"),
            "height": g(meta, "height"),
            "date": (g(it, "createTimeISO", default="") or "")[:10],
            "title": (g(it, "text", default="") or "")[:64],
            "url": g(it, "webVideoUrl", default=""),
        })
    if args.days:
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=args.days)).isoformat()
        rows = [r for r in rows if r["date"] and r["date"] >= cutoff]
    if args.max_sec:
        rows = [r for r in rows if 0 < r["duration"] <= args.max_sec]
    if args.vertical:
        rows = [r for r in rows if r["height"] > r["width"] > 0]
    rows.sort(key=lambda r: r["views"] or 0, reverse=True)
    rows = rows[: args.top]

    print(f"\n{'просмотры':>12}  {'лайки':>9}  {'сек':>4}  {'дата':>10}  ссылка")
    print("-" * 96)
    for r in rows:
        print(f"{r['views']:>12,}  {r['likes']:>9,}  {r['duration']:>4}  {r['date']:>10}  {r['url']}")
        print(f"{'':>16}{r['title']}")
    json.dump(rows, open("refs_tiktok.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n💾 Сохранено: refs_tiktok.json ({len(rows)} шт.)")


if __name__ == "__main__":
    main()
