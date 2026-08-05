"""Разбор ролика: ffmpeg (кадры) + whisper (реплики) + Qwen2.5-VL (сцены) → JSON.

Локально, бесплатно. whisper переиспользуем существующий (openai-whisper CLI).
"""
from __future__ import annotations
import base64, json, os, subprocess, tempfile, urllib.request
from pathlib import Path

from . import db, models

FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
WHISPER = os.path.expanduser("~/.local/bin/whisper")
ANALYSIS_DIR = db.DATA_DIR / "analysis"

PROMPT = """Ты — аналитик коротких вирусных видео. Тебе даны кадры ролика по порядку и его
транскрипт с таймингом. Разбери ролик и верни СТРОГО JSON на русском по схеме:
{
 "hook": "чем цепляет в первые 2 сек",
 "formula": "структура (обрыв→выбор→байт→реклама и т.п.)",
 "duration_sec": <число>,
 "characters": [{"name":"", "look":"внешний вид", "voice":"голос/тон"}],
 "scenes": [{"n":1, "time":"0-4с", "shot":"общий/крупный/средний",
             "action":"что происходит в кадре", "onscreen_text":"текст на экране, если есть",
             "dialogue":[{"who":"кто", "text":"реплика"}]}],
 "cta": "призыв в конце",
 "why_viral": "почему ролик мог залететь"
}
Только JSON, без пояснений. Реплики бери из транскрипта, действие/визуал — из кадров.

ТРАНСКРИПТ:
"""


def duration_sec(path: str) -> int:
    try:
        out = subprocess.check_output(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path], text=True)
        return int(float(out.strip()))
    except Exception:
        return 0


def frames(video: str, out_dir: Path, cap: int = 16) -> list[Path]:
    """Кадры по 1 в 2 сек (масштаб 384px), максимум cap штук."""
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-i", video, "-vf", "fps=1/2,scale=384:-1",
                    "-frames:v", str(cap), str(out_dir / "f_%02d.jpg")],
                   capture_output=True, text=True)
    return sorted(out_dir.glob("f_*.jpg"))


def transcribe(video: str, work: Path) -> str:
    """Реплики с таймингом через openai-whisper CLI (RU, medium)."""
    subprocess.run([WHISPER, video, "--model", "medium", "--language", "ru",
                    "--output_format", "json", "--output_dir", str(work), "--fp16", "False"],
                   capture_output=True, text=True, timeout=1800)
    js = next(iter(work.glob("*.json")), None)
    if not js:
        return ""
    data = json.loads(js.read_text(encoding="utf-8"))
    lines = []
    for s in data.get("segments", []):
        a, b = int(s.get("start", 0)), int(s.get("end", 0))
        lines.append(f"[{a//60}:{a%60:02d}–{b//60}:{b%60:02d}] {s.get('text','').strip()}")
    return "\n".join(lines)


def vision_json(frame_paths: list[Path], transcript: str, tag: str, dur: int) -> dict:
    """Кадры + транскрипт → JSON-разбор через Ollama Qwen2.5-VL."""
    if not models.ensure_serving():
        raise RuntimeError("Ollama не запущена")
    imgs = [base64.b64encode(p.read_bytes()).decode() for p in frame_paths]
    payload = {"model": tag, "prompt": PROMPT + (transcript or "(речь не распознана)") +
               f"\n\nДлительность ролика: {dur} сек. Кадров: {len(imgs)}.",
               "images": imgs, "stream": False, "format": "json",
               "options": {"temperature": 0.2}}
    req = urllib.request.Request(models.OLLAMA_URL + "/api/generate",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.load(r)
    raw = resp.get("response", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw, "error": "модель вернула не JSON"}


def analyze_video(c, row, tag: str = models.DEFAULT_TAG) -> dict:
    """Полный разбор одного ролика → запись в базу + data/analysis/<id>.json."""
    video = row["file"]
    if not video or not Path(video).exists():
        raise RuntimeError("нет скачанного файла")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    dur = duration_sec(video)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        transcript = transcribe(video, tdp / "w")
        fr = frames(video, tdp / "fr")
        analysis = vision_json(fr, transcript, tag, dur)
    analysis.setdefault("duration_sec", dur)
    out = ANALYSIS_DIR / f"{row['id']:04d}.json"
    out.write_text(json.dumps({"transcript": transcript, "analysis": analysis},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    db.set_analysis(c, row["id"], transcript, json.dumps(analysis, ensure_ascii=False))
    return analysis
