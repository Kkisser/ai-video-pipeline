"""Локальная веб-панель сборщика референсов (дизайн из Claude Design). Только 127.0.0.1.

  APIFY_TOKEN=... python3 -m refcollector.web
"""
from __future__ import annotations
import hashlib, html, os, threading, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import db, collect as collect_mod, download as dl_mod, suggested, keys

PORT = 8770
ACCENT = "#6d5cf0"


def apify_tok():
    return keys.get("apify", "APIFY_TOKEN")

# --- иконки (SVG) ---
def _svg(inner, size=22, sw=1.7):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')

IC = {
    "logo": '<path d="M6.5 3.5h11v17l-5.5-3.8-5.5 3.8z"/>',
    "tiktok": '<circle cx="8" cy="17" r="3.2"/><path d="M11.2 17V4.5l8 2.6v3.2l-8-2.6"/>',
    "reels": '<rect x="3.5" y="3.5" width="17" height="17" rx="5.5"/><path d="M10 9.2 15 12l-5 2.8z"/>',
    "youtube": '<rect x="2.5" y="5.5" width="19" height="13" rx="4.5"/><path d="M10.5 9.6 15 12l-4.5 2.4z"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.6 4.6"/>',
    "views": '<path d="M2.5 12S6 6.2 12 6.2 21.5 12 21.5 12 18 17.8 12 17.8 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
    "likes": '<path d="M12 20.2S4.3 15.4 4.3 10.4A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7.7 2.4c0 5-7.7 9.8-7.7 9.8Z"/>',
    "clock": '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.2V12l3.2 1.9"/>',
    "cal": '<rect x="3.4" y="5.2" width="17.2" height="15.4" rx="3.4"/><path d="M3.4 10.2h17.2M8.6 3v4M15.4 3v4"/>',
    "open": '<path d="M14 4.5h5.5V10M19.5 4.5 11 13"/><path d="M18 14v4.6a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 18.6V7.8a1.6 1.6 0 0 1 1.6-1.6H10"/>',
    "dl": '<path d="M12 4v10m0 0 4.2-4.2M12 14l-4.2-4.2M5 19h14"/>',
    "parse": '<path d="M12 3.6 13.8 9l5.4 1.9-5.4 1.9-1.8 5.4-1.8-5.4L4.8 10.9 10.2 9z"/>',
    "xls": '<rect x="3.4" y="4.4" width="17.2" height="15.2" rx="3.4"/><path d="M3.4 10h17.2M9.6 10v9.6"/>',
    "play": '<circle cx="12" cy="12" r="9"/><path d="M10.3 8.6 15.5 12l-5.2 3.4z"/>',
    "check": '<path d="M5 12.6 9.8 17.2 19 7"/>',
}

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#f6f6f4;--surface:#fff;--surface2:#f0f0ec;--text:#15151a;--muted:#70707a;--line:#e5e5e0;
 --stripe:rgba(20,20,30,.055);--shadow:0 1px 2px rgba(20,20,30,.04),0 10px 30px rgba(20,20,30,.06);--accent:#6d5cf0}
:root[data-theme=dark]{--bg:#0e0e12;--surface:#17171d;--surface2:#202028;--text:#f3f3f1;--muted:#9a9aa6;--line:#2a2a33;
 --stripe:rgba(255,255,255,.06);--shadow:0 1px 2px rgba(0,0,0,.4),0 12px 34px rgba(0,0,0,.36)}
*{box-sizing:border-box} html,body{margin:0;padding:0}
body{font-family:Manrope,"Helvetica Neue",sans-serif;-webkit-font-smoothing:antialiased;background:var(--bg);color:var(--text);transition:background .25s,color .25s}
.mono{font-family:'JetBrains Mono',monospace}
.wrap{max-width:1220px;margin:0 auto;padding:20px 20px 160px}
a{color:var(--accent);text-decoration:none}
button{font-family:inherit;cursor:pointer}
/* header */
.head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:12px 0 22px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:14px}
.logo{width:46px;height:46px;border-radius:15px;background:var(--accent);color:#fff;display:grid;place-items:center}
.brand h1{font-size:22px;font-weight:800;letter-spacing:-.03em;margin:0}
.brand .s{font-size:13px;color:var(--muted);font-weight:500}
.hbtns{display:flex;align-items:center;gap:10px}
select,.icobtn{height:46px;border-radius:14px;border:1px solid var(--line);background:var(--surface);color:var(--text);font-size:14px;font-weight:600;outline:none}
select{padding:0 14px} .icobtn{width:46px;display:grid;place-items:center}
.icobtn:hover{border-color:var(--accent);color:var(--accent)}
/* search card */
.card2{margin-top:28px;background:var(--surface);border:1px solid var(--line);border-radius:26px;padding:26px;box-shadow:var(--shadow)}
.plats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.platwrap input,.typewrap input,.chipwrap input{position:absolute;opacity:0;pointer-events:none}
.plat{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:22px 12px;border-radius:18px;
 border:1.5px solid var(--line);background:transparent;color:var(--text);transition:all .18s;font-size:15px;font-weight:700}
.platwrap input:checked + .plat{border-color:var(--accent);background:color-mix(in oklab,var(--accent) 10%,transparent);color:var(--accent)}
.row2{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
.seg{display:flex;padding:4px;gap:4px;background:var(--surface2);border-radius:14px}
.typ{height:50px;padding:0 18px;border-radius:11px;border:none;font-size:15px;font-weight:700;background:transparent;color:var(--muted)}
.typewrap input:checked + .typ{background:var(--surface);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.qbox{flex:1 1 280px;display:flex;align-items:center;gap:12px;height:58px;padding:0 18px;border:1px solid var(--line);border-radius:16px;background:var(--bg)}
.qbox input{flex:1;min-width:0;border:none;outline:none;background:transparent;color:var(--text);font-size:17px;font-weight:600;font-family:inherit}
.qbox svg{color:var(--muted);flex:none}
.find{height:58px;padding:0 30px;border:none;border-radius:16px;background:var(--accent);color:#fff;font-size:17px;font-weight:700;display:flex;align-items:center;gap:10px}
.find:hover{filter:brightness(1.08)}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px;align-items:center}
.platwrap,.typewrap,.chipwrap{display:inline-flex}
.chip{display:inline-flex;align-items:center;line-height:1;padding:10px 16px;border-radius:999px;font-size:14px;font-weight:600;border:1px solid var(--line);background:transparent;color:var(--muted);transition:all .16s;white-space:nowrap}
.clbl{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-right:2px}
.mainrow{display:flex;gap:24px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.mgroup{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.chips.inline{margin-top:0}
.nichebtn{width:100%;justify-content:center;height:58px;font-size:17px}
.adv{margin-top:18px;border-top:1px dashed var(--line)}
.adv>summary{cursor:pointer;font-size:14px;font-weight:700;color:var(--muted);padding:14px 0 6px;list-style:none}
.adv>summary::-webkit-details-marker{display:none}
.adv>summary:hover{color:var(--text)}
.advbody{padding-top:6px}
.platrow{display:flex;justify-content:center;margin-bottom:18px}
.btnrow{display:flex;gap:12px;flex-wrap:wrap}
.nichebtn{flex:1 1 340px}
.nichebtn2{flex:0 1 260px;height:58px;background:var(--surface2);color:var(--text);border:1px solid var(--line);justify-content:center}
.nichebtn2:hover{filter:none;border-color:var(--accent);color:var(--accent)}
.clearbtn{font-size:13px;font-weight:700;color:#d64545;border:1px solid var(--line);border-radius:11px;padding:9px 14px;background:transparent}
.clearbtn:hover{border-color:#d64545}
.chipwrap input:checked + .chip{border-color:var(--accent);background:color-mix(in oklab,var(--accent) 12%,transparent);color:var(--accent)}
/* results */
.reshd{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:40px 0 18px}
.reshd h2{margin:0;font-size:30px;font-weight:800;letter-spacing:-.035em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px}
.card{background:var(--surface);border-radius:22px;overflow:hidden;border:1.5px solid var(--line);box-shadow:var(--shadow);transition:border-color .16s,box-shadow .16s}
.card:has(.chk:checked){border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in oklab,var(--accent) 16%,transparent)}
.thumb{position:relative;aspect-ratio:9/16;background:var(--surface2);background-image:repeating-linear-gradient(135deg,var(--stripe) 0 10px,transparent 10px 20px);display:grid;place-items:center;cursor:pointer}
.thumb img{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}
.ph{display:flex;flex-direction:column;align-items:center;gap:10px;color:var(--muted);z-index:0}
.chk{display:none}
.box{position:absolute;left:10px;top:10px;z-index:2;width:36px;height:36px;display:grid;place-items:center;border-radius:11px;
 border:1.5px solid rgba(255,255,255,.75);background:rgba(10,10,16,.4);color:rgba(255,255,255,.8);backdrop-filter:blur(6px);transition:all .12s}
.chk:checked + .box{border-color:var(--accent);background:var(--accent);color:#fff}
/* пул предложенных источников */
.sugg{margin-top:16px;padding-top:16px;border-top:1px dashed var(--line);display:flex;flex-direction:column;gap:10px}
.sgroup{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.slabel{font-size:12px;font-weight:700;color:var(--muted);min-width:70px;text-transform:uppercase;letter-spacing:.04em}
.schip{padding:7px 13px;border-radius:999px;font-size:13px;font-weight:600;border:1px solid var(--line);background:var(--surface2);color:var(--text)}
.schip:hover{border-color:var(--accent);color:var(--accent)}
.schip.au{border-color:color-mix(in oklab,var(--accent) 30%,var(--line))}
.poolbtn{padding:9px 16px;border-radius:999px;font-size:13px;font-weight:700;background:var(--accent);color:#fff;display:inline-flex;align-items:center;gap:8px}
.poolbtn:hover{filter:brightness(1.08);color:#fff}
.status{position:absolute;right:10px;top:10px;padding:5px 11px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;z-index:2}
.dur{position:absolute;right:10px;bottom:10px;padding:4px 9px;border-radius:9px;background:rgba(10,10,16,.72);color:#fff;font-size:12px;font-weight:700}
.body{padding:16px;display:flex;flex-direction:column;gap:12px}
.auth{color:var(--muted);font-size:13px;font-weight:600}
.ttl{font-size:15px;font-weight:700;line-height:1.35;letter-spacing:-.015em}
.mx{display:grid;grid-template-columns:1fr 1fr;gap:10px 8px}
.m{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700}
.m svg{flex:none} .m.a svg{color:var(--accent)} .m.d{color:var(--muted);font-weight:600}
.acts{display:flex;gap:8px;margin-top:4px}
.ico{width:44px;height:44px;flex:none;display:grid;place-items:center;border-radius:13px;border:1px solid var(--line);background:transparent;color:var(--text)}
.ico:hover{border-color:var(--accent);color:var(--accent)}
.parse{flex:1;height:44px;display:flex;align-items:center;justify-content:center;gap:8px;border-radius:13px;border:none;
 background:color-mix(in oklab,var(--accent) 12%,transparent);color:var(--accent);font-size:14px;font-weight:700}
.parse:hover{background:var(--accent);color:#fff}
/* empty */
.empty{margin-top:60px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:18px;padding:70px 20px}
.empty .big{width:128px;height:128px;border-radius:40px;display:grid;place-items:center;background:color-mix(in oklab,var(--accent) 10%,transparent);color:var(--accent)}
.empty h3{font-size:32px;font-weight:800;letter-spacing:-.035em;margin:0}
.empty p{font-size:17px;color:var(--muted);max-width:460px;line-height:1.5;font-weight:500;margin:0}
/* sticky bar */
.bar{position:fixed;left:0;right:0;bottom:0;z-index:5;padding:0 20px 20px;pointer-events:none}
.barin{max-width:1180px;margin:0 auto;pointer-events:auto;display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:14px 18px;
 border-radius:22px;border:1px solid var(--line);background:var(--surface);box-shadow:var(--shadow)}
.barin .n{font-size:15px;font-weight:700;margin-right:auto}
.act{height:52px;padding:0 20px;border-radius:15px;font-size:15px;font-weight:700;display:flex;align-items:center;gap:10px;border:1px solid var(--line);background:transparent;color:var(--text)}
.act.p{border:none;background:var(--accent);color:#fff}
.toast{position:fixed;left:50%;bottom:110px;transform:translateX(-50%);z-index:20;padding:12px 20px;border-radius:14px;
 background:var(--text);color:var(--bg);font-size:14px;font-weight:700;box-shadow:0 10px 30px rgba(0,0,0,.28)}
.warnp{padding:4px 10px;border-radius:8px;background:#5a2a2a;color:#f5b;font-size:12px;font-weight:700}
/* панель ключей */
.keysbar{margin-top:16px;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:14px 18px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:10px}
.keyrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.kname{font-weight:700;font-size:14px;min-width:110px}
.klink{font-size:13px;font-weight:600;white-space:nowrap}
.keyrow input{flex:1 1 260px;min-width:180px;height:40px;padding:0 12px;border:1px solid var(--line);border-radius:11px;background:var(--bg);color:var(--text);font-size:13px;font-family:'JetBrains Mono',monospace}
.kstat{font-size:13px;font-weight:600;color:var(--muted);white-space:nowrap}
.ksave{align-self:flex-start;height:40px;padding:0 18px;border:none;border-radius:11px;background:var(--accent);color:#fff;font-size:14px;font-weight:700}
"""

JS = r"""
(function(){
 var root=document.documentElement;
 var saved=localStorage.getItem('rc_theme');
 if(saved) root.setAttribute('data-theme',saved);
 window.toggleTheme=function(){var d=root.getAttribute('data-theme')==='dark'?'light':'dark';
   root.setAttribute('data-theme',d);localStorage.setItem('rc_theme',d);};
 window.go=function(k,v){var u=new URL(location.href);u.searchParams.set(k,v);u.searchParams.delete('msg');location=u;};
 var t=document.querySelector('.toast'); if(t){setTimeout(function(){t.style.display='none';},2600);}
 window.pick=function(el){var c=el.querySelector('.chk'); if(c) c.checked=!c.checked;};
 window.suggest=function(pl,tp,val){
   var q=document.querySelector('input[name=value]'); if(q){q.value=val;q.focus();}
   var p=document.querySelector('input[name=platform][value="'+pl+'"]'); if(p) p.checked=true;
   var ty=document.querySelector('input[name=type][value="'+tp+'"]'); if(ty) ty.checked=true;
 };
})();
"""

_pool = {"running": False}


def _pool_worker(profile, days):
    """Собрать свежие видео всех авторов пула (в фоне, чтобы не блокировать браузер)."""
    _pool["running"] = True
    tok = apify_tok()
    try:
        for pl, h in suggested.AUTHORS:
            plat = "reels" if pl == "instagram" else "tiktok"
            try:
                collect_mod.collect(plat, "author", h, token=tok, profile=profile,
                                    n=20, days=days, max_sec=60)
            except Exception:
                pass
    finally:
        _pool["running"] = False


_niche = {"running": False}


def _niche_worker(profile, platform, n, days, max_sec, vertical, min_views):
    """Найти популярное в нише: TikTok — по ядру хэштегов, Reels — по авторам-инста."""
    _niche["running"] = True
    tok = apify_tok()
    try:
        if platform == "all":
            sources = ([("tiktok", "hashtag", t) for t in suggested.NICHE]
                       + [("youtube", "keyword", t) for t in suggested.NICHE])
        elif platform == "youtube":
            sources = [("youtube", "keyword", t) for t in suggested.NICHE]
        elif platform == "reels":
            sources = [("reels", "author", h) for pl, h in suggested.AUTHORS if pl == "instagram"]
        else:
            sources = [("tiktok", "hashtag", t) for t in suggested.NICHE]
        for plat, typ, val in sources:
            try:
                collect_mod.collect(plat, typ, val, token=tok, profile=profile, n=n,
                                    days=days, max_sec=max_sec, vertical=vertical, min_views=min_views)
            except Exception:
                pass
    finally:
        _niche["running"] = False


STATUS_COLORS = {"new": "#8a8a95", "picked": ACCENT, "downloaded": "#2f9e6a", "analyzed": "#c48a1c"}
STATUS_LABEL = {"new": "новый", "picked": "выбран", "downloaded": "скачан", "analyzed": "разобран"}


def _fmt(n):
    n = n or 0
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}".replace(".", ",").replace(",0", "") + " млн"
    if n >= 1000:
        return f"{round(n/1000)} тыс"
    return str(n)


def _fmt_dur(s):
    s = int(s or 0)
    return f"{s//60}:{s%60:02d}"


def _radio(name, value, cur, cls, label_html, wrapcls):
    ch = " checked" if str(value) == str(cur) else ""
    return (f'<label class="{wrapcls}"><input type="radio" name="{name}" value="{value}"{ch}>'
            f'<span class="{cls}">{label_html}</span></label>')


def render(profile, sort="views", msg=""):
    c = db.conn()
    rows = db.db_all(c, profile)
    cnt = db.counts(c)
    c.close()
    if sort == "likes":
        rows = sorted(rows, key=lambda r: r["likes"] or 0, reverse=True)
    elif sort == "date":
        rows = sorted(rows, key=lambda r: r["date"] or "", reverse=True)
    else:
        rows = sorted(rows, key=lambda r: r["views"] or 0, reverse=True)

    # компактная платформа (сегменты с иконкой)
    plats = "".join(_radio("platform", v, "tiktok", "typ", _svg(IC[v], 18) + " " + lbl, "typewrap")
                    for v, lbl in [("tiktok", "TikTok"), ("youtube", "Shorts"), ("reels", "Reels")])
    types = "".join(_radio("type", v, "keyword", "typ", lbl, "typewrap")
                    for v, lbl in [("keyword", "Фраза"), ("hashtag", "Хэштег"), ("author", "Автор")])
    dayschips = "".join(_radio("days", v, "30", "chip", lbl, "chipwrap")
                        for v, lbl in [("7", "7 дней"), ("30", "30 дней"), ("90", "90 дней"), ("0", "неважно")])
    minchips = "".join(_radio("min_views", v, "500000", "chip", lbl, "chipwrap")
                       for v, lbl in [("0", "любые"), ("100000", "от 100к"),
                                      ("500000", "от 500к"), ("1000000", "от 1 млн")])
    filterchips = "".join(_radio("max_sec", v, "60", "chip", lbl, "chipwrap")
                          for v, lbl in [("15", "≤ 15 сек"), ("30", "≤ 30 сек"), ("60", "≤ 60 сек")])
    filterchips += ('<label class="chipwrap"><input type="checkbox" name="vertical" value="1" checked>'
                    '<span class="chip">только вертикальные</span></label>')

    # пул предложенных источников
    def _schip(onclick, label, cls=""):
        return f'<button type="button" class="schip {cls}" onclick="{onclick}">{html.escape(label)}</button>'
    au = "".join(_schip(f"suggest('{pl}','author','{h}')", "@" + h, "au") for pl, h in suggested.AUTHORS)
    tg = "".join(_schip(f"suggest('tiktok','hashtag','{t}')", "#" + t) for t in suggested.HASHTAGS)
    ph = "".join(_schip(f"suggest('tiktok','keyword','{p}')", p) for p in suggested.PHRASES)
    pfq = urllib.parse.quote(profile or "default")
    sugg = (f'<div class="sugg">'
            f'<div class="sgroup"><a class="poolbtn" href="/collect_pool?profile={pfq}">⚡ За последнюю неделю — все авторы</a>'
            f'<span class="slabel" style="min-width:auto;text-transform:none">свежие ролики всех авторов пула одним кликом</span></div>'
            f'<div class="sgroup"><span class="slabel">Авторы</span>{au}</div>'
            f'<div class="sgroup"><span class="slabel">Хэштеги</span>{tg}</div>'
            f'<div class="sgroup"><span class="slabel">Фразы</span>{ph}</div></div>')

    # выбор количества роликов за раз (отдельная строка)
    countchips = "".join(_radio("n", v, "30", "chip", lbl, "chipwrap")
                         for v, lbl in [("10", "10 видео"), ("20", "20"), ("30", "30"), ("50", "50")])

    # панель ключей + остаток
    tok = apify_tok()
    rem = keys.apify_remaining(tok) if tok else None
    if rem:
        ap_stat = f'✓ осталось ≈ {rem["videos"]:,} видео  (${rem["remaining_usd"]:.2f} из ${rem["limit"]:.0f}/мес)'
    elif tok:
        ap_stat = '✓ ключ задан'
    else:
        ap_stat = '— не задан'
    ed_stat = '✓ задан (лимит смотри в кабинете)' if keys.get("ensembledata") else '— не задан'
    keysbar = (
        f'<form class="keysbar" method="post" action="/save_key">'
        f'<input type="hidden" name="profile" value="{html.escape(profile or "default")}">'
        f'<div class="keyrow"><span class="kname">Apify</span>'
        f'<a class="klink" href="{keys.LINKS["apify"]}" target="_blank">получить ключ ↗</a>'
        f'<input name="apify_key" placeholder="apify_api_… (вставь, чтобы задать/сменить)">'
        f'<span class="kstat">{ap_stat}</span></div>'
        f'<div class="keyrow"><span class="kname">EnsembleData</span>'
        f'<a class="klink" href="{keys.LINKS["ensembledata"]}" target="_blank">получить ключ ↗</a>'
        f'<input name="eddata_key" placeholder="ключ EnsembleData">'
        f'<span class="kstat">{ed_stat}</span></div>'
        f'<button class="ksave" type="submit">Сохранить ключи</button></form>')

    # карточки
    cards = []
    for r in rows:
        st = r["status"] or "new"
        color = STATUS_COLORS.get(st, "#8a8a95")
        cover = r["cover"] if "cover" in r.keys() else None
        thumb_inner = (f'<img loading="lazy" src="/thumb?url={urllib.parse.quote(cover)}">' if cover
                       else f'<div class=ph>{_svg(IC["play"], 42, 1.5)}<span class="mono" style="font-size:11px">превью 9:16</span></div>')
        dl_link = f'/download_one?id={r["id"]}&profile={urllib.parse.quote(profile or "default")}'
        parse_link = f'/parse_one?id={r["id"]}&profile={urllib.parse.quote(profile or "default")}'
        cards.append(f'''<div class="card">
 <div class="thumb" onclick="pick(this)" title="Клик — выбрать ролик">{thumb_inner}
   <input type="checkbox" class="chk" name="ids" value="{r["id"]}">
   <span class="box">{_svg(IC["check"],20,2.4)}</span>
   <span class="status" style="background:{color}">{STATUS_LABEL.get(st, st)}</span>
   <span class="dur mono">{_fmt_dur(r["duration"])}</span>
 </div>
 <div class="body">
   <div class="auth mono">{html.escape(r["author"] or "")}</div>
   <div class="ttl">{html.escape((r["text"] or "")[:90]) or "—"}</div>
   <div class="mx">
     <div class="m a">{_svg(IC["views"])}{_fmt(r["views"])}</div>
     <div class="m a">{_svg(IC["likes"])}{_fmt(r["likes"])}</div>
     <div class="m d">{_svg(IC["clock"])}{_fmt_dur(r["duration"])}</div>
     <div class="m d">{_svg(IC["cal"])}{html.escape(r["date"] or "")}</div>
   </div>
   <div class="acts">
     <a class="ico" href="{html.escape(r["url"])}" target="_blank" title="Открыть оригинал">{_svg(IC["open"],21,1.8)}</a>
     <a class="ico" href="{dl_link}" title="Скачать">{_svg(IC["dl"],21,1.8)}</a>
     <a class="parse" href="{parse_link}">{_svg(IC["parse"],20,1.8)}Разобрать</a>
   </div>
 </div>
</div>''')

    body_results = f'''<div class="reshd">
   <h2>{len(rows)} роликов · профиль {html.escape(profile or "default")}</h2>
   <div style="display:flex;gap:10px;align-items:center">
   <a class="clearbtn" href="/clear_base?profile={pfq}" onclick="return confirm('Удалить все ролики из базы этого профиля?')">Очистить базу</a>
   <select onchange="go('sort',this.value)">
     <option value="views"{" selected" if sort=="views" else ""}>Сортировка: просмотры</option>
     <option value="likes"{" selected" if sort=="likes" else ""}>Сортировка: лайки</option>
     <option value="date"{" selected" if sort=="date" else ""}>Сортировка: дата</option>
   </select></div></div>
 <div class="grid">{"".join(cards)}</div>''' if rows else f'''<div class="empty">
   <div class="big">{_svg(IC["search"],66,1.5)}</div>
   <h3>Найди первые референсы</h3>
   <p>Выбери площадку, введи ключевик, хэштег или автора — и собери вирусные вертикалки за последний месяц.</p></div>'''

    bar = f'''<form method="post" class="bar"><div class="barin">
   <input type="hidden" name="profile" value="{html.escape(profile or "default")}">
   <span class="n">Отметь ролики галочкой</span>
   <button class="act" formaction="/export" formmethod="get">{_svg(IC["xls"])}Экспорт в Excel</button>
   <button class="act" formaction="/download">{_svg(IC["dl"])}Скачать выбранные</button>
   <button class="act p" formaction="/parse">{_svg(IC["parse"])}Разобрать выбранные</button>
 </div></form>''' if rows else ""

    warn = "" if apify_tok() else '<span class="warnp">ключ Apify не задан</span>'
    toast = f'<div class="toast">{html.escape(msg)}</div>' if msg else ""
    pf = html.escape(profile or "default")

    return f'''<!doctype html><html lang=ru><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Сборщик референсов</title><style>{CSS}</style></head><body><div class="wrap">
 <div class="head">
   <div class="brand"><div class="logo">{_svg(IC["logo"],26,1.8)}</div>
     <div><h1>Сборщик референсов</h1><div class="s">локальная база вирусных вертикалок · {cnt or "пусто"} {warn}</div></div></div>
   <div class="hbtns">
     <select onchange="go('profile',this.value)">
       <option{" selected" if pf=="revyline" else ""} value="revyline">revyline</option>
       <option{" selected" if pf=="default" else ""} value="default">default</option>
       <option{" selected" if pf=="test" else ""} value="test">test</option>
     </select>
     <button class="icobtn" onclick="toggleTheme()" title="Сменить тему">◐</button>
   </div>
 </div>
 {keysbar}
 <form class="card2" method="post" action="/collect">
   <input type="hidden" name="profile" value="{pf}">
   <div class="platrow"><div class="seg">{plats}</div></div>
   <div class="mainrow">
     <div class="mgroup"><span class="clbl">Кол-во</span><div class="chips inline">{countchips}</div></div>
     <div class="mgroup"><span class="clbl">Период</span><div class="chips inline">{dayschips}</div></div>
     <div class="mgroup"><span class="clbl">Просмотры</span><div class="chips inline">{minchips}</div></div>
   </div>
   <div class="btnrow">
     <button class="find nichebtn" type="submit" formaction="/collect_niche">{_svg(IC["search"],22,2)}Найти популярное в нише</button>
     <button class="find nichebtn2" type="submit" formaction="/collect_niche" name="mode" value="all">TikTok + Shorts · вся ниша</button>
   </div>
   <details class="adv">
     <summary>Расширенный поиск и источники ▾</summary>
     <div class="advbody">
       <div class="row2">
         <div class="seg">{types}</div>
         <div class="qbox">{_svg(IC["search"],24,1.8)}<input name="value" placeholder="стоматолог, зубная щётка, @автор…"></div>
         <button class="find" type="submit">{_svg(IC["search"],20,2)}Найти по запросу</button>
       </div>
       <div class="chips">{filterchips}</div>
       {sugg}
     </div>
   </details>
 </form>
 {body_results}
 </div>
 {bar}
 {toast}
 <script>{JS}</script></body></html>'''


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _html(self, s):
        b = s.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _redirect(self, profile, msg="", sort="views"):
        loc = f"/?profile={urllib.parse.quote(profile)}&sort={sort}&msg={urllib.parse.quote(msg)}"
        self.send_response(303); self.send_header("Location", loc); self.end_headers()

    def _form(self):
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n).decode()
        multi = urllib.parse.parse_qs(data, keep_blank_values=True)
        flat = {k: v[0] for k, v in multi.items()}
        return flat, multi

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        profile = q.get("profile", ["revyline"])[0]
        if u.path == "/export":
            path = db.export_csv(profile if profile != "all" else None)
            b = path.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path == "/thumb":
            src = urllib.parse.unquote(q.get("url", [""])[0])
            if not src:
                self.send_response(404); self.end_headers(); return
            cache = db.DATA_DIR / "thumbs"; cache.mkdir(exist_ok=True)
            fn = cache / hashlib.md5(src.encode()).hexdigest()
            data = fn.read_bytes() if fn.exists() else None
            if data is None:
                try:
                    req = urllib.request.Request(src, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Referer": "https://www.tiktok.com/"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = resp.read()
                    fn.write_bytes(data)  # кэш на диск — обложка больше не «протухнет»
                except Exception:
                    data = None
            if not data:
                self.send_response(404); self.end_headers(); return
            ctype = ("image/webp" if data[:4] == b"RIFF" else
                     "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg")
            self.send_response(200); self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "max-age=604800")
            self.send_header("Content-Length", str(len(data))); self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/clear_base":
            c = db.conn(); nrem = db.clear_all(c, profile); c.close()
            return self._redirect(profile, f"База очищена — удалено {nrem}")
        if u.path == "/file":
            from pathlib import Path
            p = Path(urllib.parse.unquote(q.get("path", [""])[0])).resolve()
            if db.DOWNLOADS_DIR.resolve() in p.parents and p.exists():
                b = p.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            else:
                self.send_response(403); self.end_headers()
            return
        if u.path == "/download_one":
            c = db.conn()
            row = c.execute("SELECT * FROM refs WHERE id=?", (int(q["id"][0]),)).fetchone()
            msg = "Скачано" if (row and dl_mod.download_ref(c, row)) else "Не удалось скачать"
            c.close(); return self._redirect(profile, msg)
        if u.path == "/collect_pool":
            if not apify_tok():
                return self._redirect(profile, "Нет APIFY_TOKEN")
            if _pool["running"]:
                return self._redirect(profile, "Сбор пула уже идёт — обнови через минуту")
            threading.Thread(target=_pool_worker, args=(profile, 7), daemon=True).start()
            return self._redirect(profile, f"Собираю свежие видео {len(suggested.AUTHORS)} авторов за неделю — обнови через 2–3 мин")
        if u.path == "/parse_one":
            return self._redirect(profile, "Разбор (whisper+LLM) — следующий шаг, пока не подключён")
        self._html(render(profile, q.get("sort", ["views"])[0], q.get("msg", [""])[0]))

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        flat, multi = self._form()
        profile = flat.get("profile", "revyline")
        if u.path == "/save_key":
            ak = flat.get("apify_key", "").strip()
            ek = flat.get("eddata_key", "").strip()
            if ak:
                keys.save("apify", ak)
            if ek:
                keys.save("ensembledata", ek)
            return self._redirect(profile, "Ключи сохранены" if (ak or ek) else "Пусто — вставь ключ")
        if u.path == "/collect_niche":
            if not apify_tok():
                return self._redirect(profile, "Нет ключа Apify — задай его выше")
            if _niche["running"]:
                return self._redirect(profile, "Поиск по нише уже идёт — обнови через минуту")
            platform = "all" if flat.get("mode") == "all" else flat.get("platform", "tiktok")
            threading.Thread(target=_niche_worker, args=(
                profile, platform, int(flat.get("n", 30)), int(flat.get("days", 0)),
                int(flat.get("max_sec", 60)), "vertical" in flat, int(flat.get("min_views", 0))
            ), daemon=True).start()
            return self._redirect(profile, f"Ищу популярное в нише ({platform}) — обнови через 1–2 мин")
        if u.path == "/collect":
            if not apify_tok():
                return self._redirect(profile, "Нет APIFY_TOKEN")
            try:
                r = collect_mod.collect(
                    flat.get("platform", "tiktok"), flat.get("type", "keyword"), flat["value"],
                    token=apify_tok(), profile=profile, n=int(flat.get("n", 30)),
                    days=int(flat.get("days", 0)), max_sec=int(flat.get("max_sec", 0)),
                    vertical="vertical" in flat, min_views=int(flat.get("min_views", 0)))
                msg = f"Собрано: {r['got']} → фильтры → {r['kept']} → новых {r['new']}"
            except Exception as e:
                msg = f"Ошибка: {e}"
            return self._redirect(profile, msg)
        if u.path == "/download":
            ids = multi.get("ids", [])
            c = db.conn()
            for i in ids:
                db.set_status(c, int(i), "picked")
            c.close()
            if not ids:
                return self._redirect(profile, "Сначала отметь ролики")
            r = dl_mod.download_picked(profile)
            return self._redirect(profile, f"Скачано {r['downloaded']} из {r['picked']}")
        if u.path == "/parse":
            ids = multi.get("ids", [])
            return self._redirect(profile, f"Разбор {len(ids)} шт. — следующий шаг (whisper+LLM), пока не подключён")
        self.send_response(404); self.end_headers()


def run():
    db.conn().close()
    srv = HTTPServer(("127.0.0.1", PORT), H)
    print(f"Панель: http://127.0.0.1:{PORT}  (Ctrl+C — стоп)")
    if not apify_tok():
        print("ВНИМАНИЕ: ключ Apify не задан (env APIFY_TOKEN или в панели) — сбор не будет работать.")
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    except Exception:
        pass
    srv.serve_forever()


if __name__ == "__main__":
    run()
