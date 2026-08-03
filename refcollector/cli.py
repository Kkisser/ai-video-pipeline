"""CLI сборщика референсов.

  collect: собрать из источника в базу
    APIFY_TOKEN=... python -m refcollector.cli collect --type keyword "стоматолог" \
        --profile revyline --days 30 --max-sec 60 --min-views 10000
  list:   показать базу
    python -m refcollector.cli list --profile revyline --status new
"""
from __future__ import annotations
import argparse, os, sys

from . import db, collect as collect_mod


def cmd_collect(a) -> None:
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        sys.exit("НЕТ ТОКЕНА: APIFY_TOKEN=apify_api_xxx ...")
    print(f"Сбор [{a.platform}/{a.type}] «{a.value}» → профиль «{a.profile}»…")
    r = collect_mod.collect(a.platform, a.type, a.value, token=token, profile=a.profile,
                            n=a.n, days=a.days, max_sec=a.max_sec,
                            vertical=a.vertical, min_views=a.min_views)
    print(f"получено {r['got']} → после фильтров {r['kept']} → новых в базе {r['new']}")


def cmd_list(a) -> None:
    c = db.conn()
    rows = db.list_refs(c, profile=a.profile, status=a.status, limit=a.limit)
    print(f"в базе (статусы): {db.counts(c)}")
    print(f"{'id':>4} {'просмотры':>11} {'сек':>4} {'статус':>10}  ссылка")
    print("-" * 90)
    for r in rows:
        print(f"{r['id']:>4} {r['views'] or 0:>11,} {r['duration'] or 0:>4} "
              f"{r['status']:>10}  {r['url']}")
        if r["text"]:
            print(f"{'':>22}{r['text'][:60]}")
    c.close()


def main() -> None:
    ap = argparse.ArgumentParser(prog="refcollector")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("collect")
    p.add_argument("value")
    p.add_argument("--platform", choices=["tiktok", "reels"], default="tiktok")
    p.add_argument("--type", choices=["keyword", "hashtag", "author"], default="keyword")
    p.add_argument("--profile", default="default")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--days", type=int, default=0)
    p.add_argument("--max-sec", type=int, default=0)
    p.add_argument("--vertical", action="store_true")
    p.add_argument("--min-views", type=int, default=0)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("list")
    p.add_argument("--profile", default=None)
    p.add_argument("--status", default=None)
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_list)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
