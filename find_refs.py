#!/usr/bin/env python3
"""find_refs.py — бесплатный авто-поиск референсов (демо, дорожка API/авто).

Что делает:
  • ищет короткие видео по ключевику на YouTube (yt-dlp, без аккаунта);
  • тянет метрики (просмотры), сортирует по популярности, фильтрует «шортсы»;
  • печатает шорт-лист со ссылками и сохраняет refs_shortlist.csv.

TikTok-дискавери yt-dlp НЕ умеет (см. схему) — для TikTok-трендов нужен
скрапер (Apify/EnsembleData). Зато метрики любого TikTok-ролика по ссылке
он берёт — функция tiktok_metrics() ниже.

Запуск:
  .venv/bin/python find_refs.py "pixar ai cartoon" --n 30 --max-sec 60 --top 12
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from pathlib import Path

YTDLP = str(Path(__file__).with_name("flowbatch") / ".venv" / "bin" / "yt-dlp")


def _has_cyrillic(s: str) -> bool:
    return any("Ѐ" <= c <= "ӿ" for c in s)


def yt_search(query: str, n: int, days: int = 0) -> list[dict]:
    """Полный разбор роликов с YouTube: метрики + размеры кадра + дата.

    days>0 — только загруженные за последние N дней (--dateafter).
    Полный разбор (не flat) нужен, чтобы знать длительность, ширину/высоту
    (вертикальность) и дату — именно по ним фильтруем.
    """
    cmd = [YTDLP, f"ytsearch{n}:{query}", "--no-warnings", "--ignore-errors",
           "--print", "%(view_count)s\t%(duration)s\t%(width)s\t%(height)s\t%(upload_date)s\t%(title)s\t%(webpage_url)s"]
    if days:
        cmd += ["--dateafter", f"today-{days}days"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) != 7:
            continue
        views, dur, w, h, date, title, url = p
        rows.append({
            "views": int(views) if views.isdigit() else 0,
            "duration": int(dur) if dur.isdigit() else 0,
            "width": int(w) if w.isdigit() else 0,
            "height": int(h) if h.isdigit() else 0,
            "date": date.strip(),
            "title": title.strip(),
            "url": url.strip(),
        })
    return rows


def tiktok_metrics(url: str) -> dict:
    """Метрики одного TikTok/YouTube-ролика по ссылке."""
    cmd = [YTDLP, url, "--print",
           "%(view_count)s\t%(like_count)s\t%(comment_count)s\t%(title)s"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    p = (out.split("\t") + ["", "", "", ""])[:4]
    return {"views": p[0], "likes": p[1], "comments": p[2], "title": p[3], "url": url}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=30, help="сколько роликов запросить")
    ap.add_argument("--max-sec", type=int, default=0, help="макс. длительность (0 = без фильтра)")
    ap.add_argument("--days", type=int, default=0, help="только за последние N дней (0 = без фильтра)")
    ap.add_argument("--vertical", action="store_true", help="только вертикальные (высота > ширины)")
    ap.add_argument("--ru", action="store_true", help="только с кириллицей в названии")
    ap.add_argument("--top", type=int, default=12, help="сколько показать")
    ap.add_argument("--out", default="refs_shortlist.csv")
    args = ap.parse_args()

    print(f"🔎 Ищу «{args.query}» (n={args.n}, дней={args.days or '∞'}, "
          f"≤{args.max_sec or '∞'}с, вертик={args.vertical}, ru={args.ru})…")
    rows = yt_search(args.query, args.n, days=args.days)
    total = len(rows)
    if args.max_sec:
        rows = [r for r in rows if 0 < r["duration"] <= args.max_sec]
    if args.vertical:
        rows = [r for r in rows if r["height"] > r["width"] > 0]
    if args.ru:
        rows = [r for r in rows if _has_cyrillic(r["title"])]
    rows.sort(key=lambda r: r["views"], reverse=True)
    rows = rows[: args.top]

    print(f"разобрано {total} → после фильтров {len(rows)}\n")
    print(f"{'просмотры':>12}  {'сек':>4}  {'кадр':>8}  {'дата':>8}  ссылка")
    print("-" * 92)
    for r in rows:
        frame = f"{r['width']}x{r['height']}" if r["width"] else "?"
        print(f"{r['views']:>12,}  {r['duration']:>4}  {frame:>8}  {r['date']:>8}  {r['url']}")
        print(f"{'':>16}{r['title'][:64]}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["views", "duration", "width", "height", "date", "title", "url"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n💾 Сохранено: {args.out}")


if __name__ == "__main__":
    main()
