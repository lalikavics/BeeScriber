# -*- coding: utf-8 -*-
"""Writing the finished transcript: TXT, SRT, VTT, HTML, PDF, DOCX. File names come from templates."""
from __future__ import annotations

import html
import re
import textwrap
import time
from pathlib import Path

from . import config, textfmt

RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
FORMAT_EXT = {"txt": ".txt", "srt": ".srt", "vtt": ".vtt", "html": ".html", "pdf": ".pdf", "docx": ".docx"}


# ---------------------------------------------------------------- names

def safe_name(s: str, limit: int = 150) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(s))
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    if not s:
        s = "untitled"
    if s.split(".")[0].upper() in RESERVED:
        s = "_" + s
    return s[:limit].rstrip(". ")


class _Safe(dict):
    def __missing__(self, key):
        return ""


def file_stem(job: dict, settings) -> str:
    tpl = settings.get("playlist_name_template") if job.get("playlist_id") else settings.get("name_template")
    vals = _Safe(title=job.get("title") or "", id=job.get("video_id") or "", index=int(job.get("pl_index") or 0),
                 channel=job.get("channel") or "", playlist=job.get("playlist_title") or "",
                 date=time.strftime("%Y-%m-%d"))
    try:
        name = (tpl or "{title}").format_map(vals)
    except (ValueError, IndexError, KeyError):
        name = vals["title"]
    return safe_name(name or vals["title"] or vals["id"])


def output_folder(job: dict, settings) -> Path:
    base = Path(job.get("output_dir") or settings.output_dir())
    if job.get("playlist_id") and settings.get("playlist_subfolder"):
        base = base / safe_name(job.get("playlist_title") or job["playlist_id"], 100)
    return base


# ---------------------------------------------------------------- captions

def _ts(t: float, sep: str) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def cues(segs: list[dict], max_chars: int = 84, line: int = 42, name=None) -> list[tuple[float, float, str]]:
    """Whisper segments -> subtitle cues of at most two lines; long segments are split at word borders,
    their time is shared in proportion to the text length. With speakers, a cue starts with [Speaker n]
    whenever the speaker changes."""
    out = []
    prev_spk = None
    for s0 in segs:
        if not str(s0["text"]).strip():
            continue
        s = {"start": s0["start"], "end": s0["end"], "text": " ".join(str(s0["text"]).split())}
        spk = s0.get("speaker") if name else None
        if spk and spk != prev_spk:
            s["text"] = f"[{name(spk)}] " + s["text"]
        prev_spk = spk or prev_spk
        text, st, en = s["text"], float(s["start"]), float(s["end"])
        if len(text) <= max_chars:
            parts = [text]
        else:
            parts, cur = [], ""
            for w in text.split():
                if cur and len(cur) + 1 + len(w) > max_chars:
                    parts.append(cur)
                    cur = w
                else:
                    cur = f"{cur} {w}".strip()
            if cur:
                parts.append(cur)
        total = sum(len(p) for p in parts) or 1
        t = st
        for p in parts:
            d = (en - st) * len(p) / total
            wrapped = "\n".join(textwrap.wrap(p, line)[:3]) if len(p) > line else p
            out.append((t, t + d, wrapped))
            t += d
    return out


def to_srt(segs: list[dict], name=None) -> str:
    return "\n".join(f"{i}\n{_ts(a, ',')} --> {_ts(b, ',')}\n{t}\n" for i, (a, b, t) in enumerate(cues(segs, name=name), 1))


def to_vtt(segs: list[dict], name=None) -> str:
    return "WEBVTT\n\n" + "\n".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{t}\n" for a, b, t in cues(segs, name=name))


# ---------------------------------------------------------------- documents

def speaker_namer(settings):
    hu = (settings.get("ui_lang") or "en") == "hu"
    return (lambda n: f"{n}. beszélő") if hu else (lambda n: f"Speaker {n}")


def _blocks_sp(segs: list[dict], mode: str, name) -> list[tuple[float, str, str | None]]:
    """Like _blocks, plus the speaker label on the first block of every speaker turn."""
    if not (name and textfmt.has_speakers(segs)):
        return [(t, x, None) for t, x in _blocks(segs, mode)]
    out = []
    for spk, group in textfmt.speaker_turns(segs):
        for k, (t, x) in enumerate(_blocks(group, "paragraphs" if mode == "plain" else mode)):
            out.append((t, x, name(spk) if (k == 0 and spk) else None))
    return out


def _blocks(segs: list[dict], mode: str) -> list[tuple[float, str]]:
    sents = textfmt.split_sentences(segs)
    if mode == "sentences":
        return [(s["start"], s["text"]) for s in sents]
    if mode == "plain":
        return [(sents[0]["start"], " ".join(s["text"] for s in sents))] if sents else []
    return [(p[0]["start"], " ".join(x["text"] for x in p)) for p in textfmt.make_paragraphs(sents)]


def _meta_lines(job: dict) -> list[str]:
    bits = []
    if job.get("channel"):
        bits.append(job["channel"])
    if job.get("duration"):
        bits.append(textfmt.hms(job["duration"]))
    if job.get("lang"):
        bits.append(job["lang"])
    return [" · ".join(bits)] if bits else []


def _yt_link(job: dict, t: float) -> str | None:
    if job.get("video_id") and job.get("kind") != "file":
        return f"https://www.youtube.com/watch?v={job['video_id']}&t={int(t)}s"
    return None


def to_html(job: dict, segs: list[dict], mode: str, timestamps: bool, name=None) -> str:
    title = html.escape(job.get("title") or "")
    src = job.get("source") or ""
    meta = " · ".join(html.escape(x) for x in _meta_lines(job))
    body = []
    for t, text, who in _blocks_sp(segs, mode, name):
        ts = f'<b class="spk">{html.escape(who)}:</b> ' if who else ""
        if timestamps:
            link = _yt_link(job, t)
            ts = (f'<a class="ts" href="{html.escape(link)}">{textfmt.hms(t)}</a> ' if link
                  else f'<span class="ts">{textfmt.hms(t)}</span> ') + ts
        body.append(f"<p>{ts}{html.escape(text)}</p>")
    src_html = (f'<a href="{html.escape(src)}">{html.escape(src)}</a>' if src.startswith("http")
                else html.escape(Path(src).name))
    lang = html.escape((job.get("lang") or "en")[:5])
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1d1f23;--mut:#6b7280;--acc:#2f6fdb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e6e8eb;--mut:#9aa1ab;--acc:#6aa3ff}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:17px/1.65 Georgia,'Times New Roman',serif}}
main{{max-width:720px;margin:0 auto;padding:48px 20px 80px}}
h1{{font:600 28px/1.25 system-ui,'Segoe UI',sans-serif;margin:0 0 6px}}
.meta{{font:14px/1.4 system-ui,'Segoe UI',sans-serif;color:var(--mut);margin-bottom:32px}}
.meta a{{color:var(--mut)}}
p{{margin:0 0 1em}}
.spk{{font-family:system-ui,'Segoe UI',sans-serif;font-weight:650}}
.ts{{font:12px system-ui,'Segoe UI',sans-serif;color:var(--acc);text-decoration:none;margin-right:6px}}
footer{{margin-top:48px;font:12px system-ui,sans-serif;color:var(--mut)}}
</style></head><body><main>
<h1>{title}</h1>
<div class="meta">{meta}{'<br>' if meta else ''}{src_html}</div>
{chr(10).join(body)}
<footer>{config.APP_NAME} {config.VERSION}</footer>
</main></body></html>
"""


def _pdf_font() -> tuple[str, str]:
    """A TTF font with Hungarian accents (ő, ű): Windows fonts first, then common Linux fonts."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    cands = [("Segoe", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
             ("Arial", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
             ("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for name, reg, bold in cands:
        if Path(reg).exists():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, reg))
                pdfmetrics.registerFont(TTFont(name + "-Bold", bold if Path(bold).exists() else reg))
            return name, name + "-Bold"
    return "Helvetica", "Helvetica-Bold"


def to_pdf(path: Path, job: dict, segs: list[dict], mode: str, timestamps: bool, name=None) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    reg, bold = _pdf_font()
    st_title = ParagraphStyle("t", fontName=bold, fontSize=17, leading=21, spaceAfter=4)
    st_meta = ParagraphStyle("m", fontName=reg, fontSize=9, leading=12, textColor="#666666", spaceAfter=14)
    st_body = ParagraphStyle("b", fontName=reg, fontSize=11, leading=16, spaceAfter=7)
    esc = lambda s: html.escape(s, quote=False)  # noqa: E731
    story = [Paragraph(esc(job.get("title") or ""), st_title)]
    meta = _meta_lines(job) + [job.get("source") or ""]
    story.append(Paragraph("<br/>".join(esc(m) for m in meta if m), st_meta))
    for t, text, who in _blocks_sp(segs, mode, name):
        ts = f'<font color="#0a8fbf" size="8">{textfmt.hms(t)}</font>  ' if timestamps else ""
        sp = f'<font name="{bold}">{esc(who)}:</font> ' if who else ""
        story.append(Paragraph(ts + sp + esc(text), st_body))
    story.append(Spacer(1, 4 * mm))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=job.get("title") or "",
                            author=job.get("channel") or "", creator=f"{config.APP_NAME} {config.VERSION}")
    doc.build(story)


def to_docx(path: Path, job: dict, segs: list[dict], mode: str, timestamps: bool, name=None) -> None:
    from docx import Document
    from docx.shared import Pt, RGBColor
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    d.core_properties.title = job.get("title") or ""
    d.core_properties.author = job.get("channel") or ""
    d.add_heading(job.get("title") or "", level=1)
    meta = _meta_lines(job) + [job.get("source") or ""]
    mp = d.add_paragraph()
    r = mp.add_run("\n".join(m for m in meta if m))
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    for t, text, who in _blocks_sp(segs, mode, name):
        p = d.add_paragraph()
        if timestamps:
            tr = p.add_run(textfmt.hms(t) + "  ")
            tr.font.size = Pt(8)
            tr.font.color.rgb = RGBColor(0x0A, 0x8F, 0xBF)
        if who:
            p.add_run(who + ": ").bold = True
        p.add_run(text)
    d.save(str(path))


# ---------------------------------------------------------------- all formats

def export(job: dict, segs: list[dict], settings, formats: list[str] | None = None) -> list[str]:
    """Writes every chosen format; returns the written paths. Writes to a temp name first, then renames,
    so a crash never leaves a half-written transcript under the final name."""
    formats = [f for f in (formats or settings.get("formats") or ["txt"]) if f in FORMAT_EXT]
    mode = settings.get("txt_mode") or "paragraphs"
    ts = bool(settings.get("timestamps"))
    folder = output_folder(job, settings)
    folder.mkdir(parents=True, exist_ok=True)
    stem = file_stem(job, settings)
    name = speaker_namer(settings) if textfmt.has_speakers(segs) else None
    written = []
    for fmt in formats:
        path = folder / (stem + FORMAT_EXT[fmt])
        tmp = path.with_name(path.stem + ".part" + path.suffix)
        if fmt == "txt":
            head = ""
            if settings.get("txt_header"):
                src = job.get("source") or ""
                src = src if src.startswith("http") else Path(src).name
                lines = [job.get("title") or ""] + _meta_lines(job) + [src]
                head = "\n".join(x for x in lines if x) + "\n\n"
            tmp.write_text(head + textfmt.render_txt(segs, mode, ts, name), encoding="utf-8")
        elif fmt == "srt":
            tmp.write_text(to_srt(segs, name), encoding="utf-8")
        elif fmt == "vtt":
            tmp.write_text(to_vtt(segs, name), encoding="utf-8")
        elif fmt == "html":
            tmp.write_text(to_html(job, segs, mode, ts, name), encoding="utf-8")
        elif fmt == "pdf":
            to_pdf(tmp, job, segs, mode, ts, name)
        elif fmt == "docx":
            to_docx(tmp, job, segs, mode, ts, name)
        tmp.replace(path)
        written.append(str(path))
    return written
