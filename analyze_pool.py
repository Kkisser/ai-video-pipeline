"""Анализ авторов пула: подписчики, видео за неделю, просмотры, топ-ролик.
Плюс топ хэштегов по суммарным просмотрам. Источник — Apify (TikTok).

  APIFY_TOKEN=... python3 analyze_pool.py
"""
import json, os, urllib.request, collections
from datetime import date, timedelta
from refcollector import suggested

TOKEN = os.environ["APIFY_TOKEN"]
ACTOR = "clockworks~tiktok-scraper"
API = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={TOKEN}"
CUTOFF = (date.today() - timedelta(days=7)).isoformat()


def run(payload):
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


tags = collections.Counter()
rows = []
tiktok_authors = [h for pl, h in suggested.AUTHORS if pl == "tiktok"]

for h in tiktok_authors:
    try:
        items = run({"profiles": [h], "resultsPerPage": 30,
                     "shouldDownloadVideos": False, "shouldDownloadCovers": False})
    except Exception as e:
        print(f"{h}: ошибка {e}")
        continue
    if not items:
        print(f"{h}: пусто")
        continue
    am = items[0].get("authorMeta") or {}
    followers = am.get("fans", 0)
    acc_videos = am.get("video", 0)
    week = [it for it in items if (it.get("createTimeISO") or "")[:10] >= CUTOFF]
    week_views = sum(it.get("playCount", 0) or 0 for it in week)
    best = max(items, key=lambda it: it.get("playCount", 0) or 0)
    for it in items:
        v = it.get("playCount", 0) or 0
        for t in (it.get("hashtags") or []):
            if t.get("name"):
                tags[t["name"]] += v
    rows.append({
        "author": h, "followers": followers, "acc_videos": acc_videos,
        "week_videos": len(week), "week_views": week_views,
        "best_views": best.get("playCount", 0), "best_url": best.get("webVideoUrl", ""),
    })
    print(f"  {h}: подписчиков {followers:,}, за неделю {len(week)} видео / {week_views:,} просмотров")

rows.sort(key=lambda r: r["week_views"], reverse=True)
print("\n================ АВТОРЫ (по просмотрам за неделю) ================")
print(f"{'автор':22} {'подписчики':>12} {'видео_акк':>10} {'нед_видео':>9} {'нед_просм':>13}")
for r in rows:
    print(f"{r['author']:22} {r['followers']:>12,} {r['acc_videos']:>10,} {r['week_videos']:>9} {r['week_views']:>13,}")

print("\n================ ТОП ХЭШТЕГОВ (по сумм. просмотрам) ================")
for name, v in tags.most_common(20):
    print(f"  #{name:28} {v:>13,}")

json.dump({"authors": rows, "hashtags": tags.most_common(30)},
          open("data/pool_analysis.json", "w"), ensure_ascii=False, indent=2)
print("\nСохранено: data/pool_analysis.json")
