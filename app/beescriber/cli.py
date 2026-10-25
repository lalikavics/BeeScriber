# -*- coding: utf-8 -*-
"""Command line for tests and power users (the app itself uses the same queue and engine).

    python -m beescriber.cli selftest
    python -m beescriber.cli info
    python -m beescriber.cli load URL
    python -m beescriber.cli transcribe URL|FILE [--items 1,3-5] [--formats txt,srt] [--out DIR] [--pause-at 30]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import config, sources, textfmt, tools


def _items(spec: str | None, n: int) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out |= set(range(int(a), int(b) + 1))
        elif part.strip():
            out.add(int(part))
    return {i for i in out if 1 <= i <= n}


def cmd_info(_a) -> int:
    print(f"{config.APP_NAME} {config.VERSION}")
    print(f"adatmappa : {config.DATA_DIR}")
    print(f"eszközök  : {config.BIN_DIR}")
    for n in tools.REQUIRED:
        print(f"{n:<10}: {tools.version(n) or 'HIÁNYZIK'}")
    g = tools.gpu_info()
    print("GPU       : " + (f"{g['name']} ({g['used_mb']}/{g['total_mb']} MB)" if g else "nincs NVIDIA GPU"))
    try:
        import ctranslate2
        import faster_whisper
        print(f"motor     : faster-whisper {faster_whisper.__version__}, ctranslate2 {ctranslate2.__version__}, "
              f"CUDA eszközök: {ctranslate2.get_cuda_device_count()}")
    except Exception as e:  # noqa: BLE001
        print(f"motor     : HIÁNYZIK ({e})")
    tools.usage()
    time.sleep(1)
    u = tools.usage()
    print(f"terhelés  : GPU {u['gpu']}%, VRAM {u['vram_used']}/{u['vram_total']} MB, CPU {u['cpu']}%")
    from . import diarize
    st = diarize.status()
    print(f"beszélők  : kiegészítő {'telepítve' if st['installed'] else 'nincs telepítve'}, "
          f"kulcs {'mentve' if st['has_token'] else 'nincs'}")
    try:
        clip = tools.clipboard_get()
        print(f"vágólap   : olvasható ({len(clip)} karakter)")
    except Exception as e:  # noqa: BLE001
        print(f"vágólap   : HIBA ({e})")
    for mod in ("webview", "reportlab", "docx"):
        try:
            __import__(mod)
            print(f"{mod:<10}: ok")
        except Exception as e:  # noqa: BLE001
            print(f"{mod:<10}: HIÁNYZIK ({e})")
    return 0


def _settings(a) -> config.Settings:
    data = Path(a.data) if a.data else config.DATA_DIR / "cli"
    s = config.Settings(data / "settings.json")
    ch = {}
    for k in ("model", "language", "txt_mode", "device", "compute", "first_pass"):
        v = getattr(a, k, None)
        if v:
            ch[k] = v
    if getattr(a, "formats", None):
        ch["formats"] = [f.strip() for f in a.formats.split(",") if f.strip()]
    if getattr(a, "out", None):
        ch["output_dir"] = a.out
    if getattr(a, "timestamps", False):
        ch["timestamps"] = True
    if getattr(a, "no_guard", False):
        ch["punct_guard"] = False
    if getattr(a, "diarize", False):
        ch.update(diarize=True, speakers=int(getattr(a, "speakers", 0) or 0))
    if getattr(a, "browser_cookies", None):
        ch.update(cookies_mode="browser", cookies_browser=a.browser_cookies)
    s.update(ch)
    return s


def _resolve(a, settings) -> tuple[list[dict], dict | None]:
    p = sources.parse_input(a.source)
    if p["kind"] == "file":
        return [sources.probe_file(p["path"])], None
    if p["kind"] == "invalid":
        sys.exit(f"Nem értelmezhető: {a.source}")
    url = p["url"]
    if p.get("both") and not getattr(a, "video_only", False):
        url = f"https://www.youtube.com/playlist?list={p['list_id']}"
    col = sources.load_url(url, settings)
    return col["entries"], col


def cmd_load(a) -> int:
    s = _settings(a)
    try:
        items, col = _resolve(a, s)
    except sources.SourceError as e:
        print(f"HIBA [{e.code}]\n{e.detail}")
        return 1
    if col:
        print(f"{col['type']}: {col['title']}  ({col['id']}) – {len(items)} db, betöltés {col['load_s']} mp")
    total = 0.0
    for it in items:
        total += it["duration"] or 0
        flag = "" if it["status"] == "ok" else f"  [{it['status']}]"
        print(f"{it['index']:>4}. {textfmt.hms(it['duration'] or 0):>8}  {it['title']}{flag}")
    print(f"összesen: {textfmt.hms(total)}")
    return 0


def cmd_transcribe(a) -> int:
    from .jobqueue import JobQueue
    s = _settings(a)
    data = Path(a.data) if a.data else config.DATA_DIR / "cli"
    try:
        items, col = _resolve(a, s)
    except sources.SourceError as e:
        print(f"HIBA [{e.code}]\n{e.detail}")
        return 1
    pick = _items(a.items, len(items))
    items = [it for it in items if (pick is None or it["index"] in pick) and it["status"] == "ok"]
    if a.fresh:
        import shutil
        shutil.rmtree(data / "jobs", ignore_errors=True)
        (data / "cli.db").unlink(missing_ok=True)
    stats = {"redo": 0, "redo_kept": 0, "windows": 0, "engine": None, "jobs": {}}
    t_start = time.time()

    def emit(ev: str, **d):
        if ev == "engine":
            if d.get("status") == "ready":
                stats["engine"] = d.get("info")
                print(f"motor kész: {d.get('info')} ({d.get('load_s')} s)", flush=True)
            elif d.get("status") == "error":
                print(f"MOTOR HIBA: {d.get('error')}", flush=True)
            else:
                print(f"motor: {d.get('status')} {d.get('model', '')}", flush=True)
        elif ev == "redo":
            stats["redo"] += 1
            print(f"    írásjel-őr: {d['words']} szó írásjel nélkül {textfmt.hms(d['pos'])}-nál, újra...", flush=True)
        elif ev == "redo_result":
            print(f"    írásjel-őr eredmény: {d['before']} -> {d['after']} ({'javított megtartva' if d['kept'] else 'eredeti marad'})",
                  flush=True)
        elif ev == "accepted":
            stats["windows"] += 1
            stats["redo_kept"] += 1 if d.get("redone") else 0
            print(f"    ablak kész: {textfmt.hms(d['pos'])}  {d.get('speed')}x" +
                  ("  (javított)" if d.get("redone") else ""), flush=True)
        elif ev == "speakers":
            print(f"    beszélők: {d.get('status')} {d.get('count', '')} {d.get('error', '')}", flush=True)
        elif ev == "language":
            print(f"    nyelv: {d['lang']} ({d['prob']:.0%})", flush=True)
        elif ev == "resumed":
            print(f"    folytatás innen: {textfmt.hms(d['pos'])} ({len(d['segs'])} szegmens megvolt)", flush=True)
        elif ev == "job":
            j = d["job"]
            if j["status"] in ("running", "done", "error", "paused"):
                extra = ""
                if j["status"] == "done":
                    extra = f" – {j['speed']}x, {len(j['outputs'])} fájl"
                    stats["jobs"][j["id"]] = {"title": j["title"], "speed": j["speed"], "wall": j["wall"],
                                              "duration": j["duration"], "lang": j["lang"], "outputs": j["outputs"]}
                if j["status"] == "error":
                    extra = f" – [{j['error_code']}] {(j['error'] or '')[-300:]}"
                    stats["jobs"][j["id"]] = {"title": j["title"], "error": j["error_code"]}
                print(f"[{j['status']}] {j['title']}{extra}", flush=True)

    q = JobQueue(s, emit, db_path=data / "cli.db", jobs_dir=data / "jobs")
    ids = q.add(items, col)
    for j in q.jobs():
        if j["status"] in ("error", "paused"):
            q.resume_job(j["id"])
    print(f"{len(ids)} új elem a sorban; kimenet: {s.output_dir()}", flush=True)
    q.start()
    paused_once = False
    try:
        while q.state()["running"] or q.current is not None:
            time.sleep(0.25)
            if a.pause_at and not paused_once and time.time() - t_start > a.pause_at:
                paused_once = True
                print(f"\n>>> SZÜNET ({a.pause_at} mp után) – 3 mp múlva folytatom\n", flush=True)
                q.pause_all(now=True)
                while q.current is not None:
                    time.sleep(0.1)
                time.sleep(3)
                q.start()
    except KeyboardInterrupt:
        print("\nMegszakítva – a sor állapota mentve, újraindítva folytatja.")
        q.close()
        return 130
    q.close()
    stats["wall_total"] = round(time.time() - t_start, 1)
    stats["pause_tested"] = paused_once
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKész: {stats['wall_total']} mp, írásjel-javítás: {stats['redo']} ablak ({stats['redo_kept']} megtartva)")
    return 0 if all("error" not in v for v in stats["jobs"].values()) else 2


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    tools.setup_logging()
    ap = argparse.ArgumentParser(prog=f"{config.APP_ID}.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("info")
    for name in ("load", "transcribe"):
        p = sub.add_parser(name)
        p.add_argument("source")
        p.add_argument("--data", default=None, help="külön adatmappa (alap: <adatmappa>/cli)")
        p.add_argument("--browser-cookies", default=None, help="pl. firefox")
        p.add_argument("--video-only", action="store_true", help="video+lista linknél csak a videó")
        if name == "transcribe":
            p.add_argument("--items", default=None, help="pl. 1,3-5 (a lista sorszámai)")
            p.add_argument("--formats", default=None, help="txt,srt,vtt,html,pdf,docx")
            p.add_argument("--txt-mode", dest="txt_mode", default=None, choices=config.TXT_MODES)
            p.add_argument("--timestamps", action="store_true")
            p.add_argument("--out", default=None)
            p.add_argument("--model", default=None)
            p.add_argument("--language", default=None)
            p.add_argument("--device", default=None)
            p.add_argument("--compute", default=None)
            p.add_argument("--no-guard", action="store_true", help="írásjel-őr kikapcsolva (összehasonlításhoz)")
            p.add_argument("--first-pass", dest="first_pass", default=None, choices=["careful", "plain"])
            p.add_argument("--diarize", action="store_true", help="beszélők megkülönböztetése (kiegészítő kell)")
            p.add_argument("--speakers", type=int, default=0, help="beszélők száma (0 = automatikus)")
            p.add_argument("--pause-at", type=float, default=0, help="teszt: ennyi mp után szünet, majd folytatás")
            p.add_argument("--fresh", action="store_true", help="a CLI sorát és naplóit törli előtte")
            p.add_argument("--report", default=None, help="mérések JSON fájlba")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        from . import selftest
        return selftest.main()
    return {"info": cmd_info, "load": cmd_load, "transcribe": cmd_transcribe}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
