# -*- coding: utf-8 -*-
"""Whisper segments -> sentences -> paragraphs. Also the punctuation checks used by the transcriber."""
from __future__ import annotations

import re

ABBR = {"mr.", "mrs.", "ms.", "dr.", "prof.", "st.", "vs.", "etc.", "e.g.", "i.e.", "no.", "jr.", "sr.",
        "pl.", "kb.", "stb.", "ún.", "ill.", "ld.", "sz.", "u.a.", "kft.", "zrt.", "ifj.", "id."}
TERM = re.compile(r'[.!?…]+["”’)\]]*(?=\s|$)')
INITIAL = re.compile(r'^[A-ZÁÉÍÓÖŐÚÜŰ]\.$')
WORD = re.compile(r"\w+", re.UNICODE)


def hms(sec: float) -> str:
    sec = int(round(max(0.0, sec)))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _is_abbr(buf: str, m: re.Match) -> bool:
    w = re.search(r"(\S+)$", buf[:m.end()])
    if not w:
        return False
    raw = w.group(1).lstrip('"“‘([')
    return raw.lower() in ABBR or bool(INITIAL.match(raw))


def split_sentences(segs: list[dict]) -> list[dict]:
    """Whisper segments -> one dict per sentence, with start/end seconds."""
    sents: list[dict] = []
    buf = ""
    marks: list[tuple[int, float, float]] = []   # (char position in buf, seg start, seg end)

    def flush(n: int, end_t: float) -> None:
        nonlocal buf, marks
        head = buf[:n]
        text = head.strip()
        if text:
            first = len(head) - len(head.lstrip())
            st = marks[0][1]
            for pos, s, _e in marks:
                if pos <= first:
                    st = s
                else:
                    break
            sents.append({"start": st, "end": end_t, "text": text})
        shifted = [(p - n, s, e) for p, s, e in marks]
        zero = [m for m in shifted if m[0] <= 0][-1:]
        marks = [(0, m[1], m[2]) for m in zero] + [m for m in shifted if m[0] > 0]
        buf = buf[n:]

    for s in segs:
        t = " ".join(str(s["text"]).split())
        if not t:
            continue
        if buf:
            buf += " "
        marks.append((len(buf), float(s["start"]), float(s["end"])))
        buf += t
        while True:
            m = next((x for x in TERM.finditer(buf) if not _is_abbr(buf, x)), None)
            if not m:
                break
            flush(m.end(), float(s["end"]))
    if buf.strip():
        flush(len(buf), float(segs[-1]["end"]))
    return sents


def make_paragraphs(sents: list[dict], gap=1.4, min_sent=2, max_sent=6, max_chars=650) -> list[list[dict]]:
    paras: list[list[dict]] = []
    cur: list[dict] = []
    for s in sents:
        if cur:
            g = s["start"] - cur[-1]["end"]
            chars = sum(len(x["text"]) + 1 for x in cur)
            if (g >= gap and len(cur) >= min_sent) or g >= 3.0 or len(cur) >= max_sent or chars >= max_chars:
                paras.append(cur)
                cur = []
        cur.append(s)
    if cur:
        paras.append(cur)
    return paras


def speaker_turns(segs: list[dict]) -> list[tuple[object, list[dict]]]:
    """Consecutive segments of the same speaker: [(speaker, [segs])]."""
    out: list[tuple[object, list[dict]]] = []
    for s in segs:
        spk = s.get("speaker")
        if out and out[-1][0] == spk:
            out[-1][1].append(s)
        else:
            out.append((spk, [s]))
    return out


def has_speakers(segs: list[dict]) -> bool:
    return any(s.get("speaker") for s in segs)


def _label_first_line(body: str, label: str) -> str:
    m = re.match(r"^(\[\d+:\d{2}:\d{2}\] )", body)
    return (m.group(1) + label + body[m.end():]) if m else label + body


def render_txt(segs: list[dict], mode: str = "paragraphs", timestamps: bool = False, name=None) -> str:
    """mode: plain | sentences | paragraphs. name(n) -> speaker label; with speakers every turn starts with it."""
    if not segs:
        return ""
    if name and has_speakers(segs):
        parts = []
        for spk, group in speaker_turns(segs):
            body = render_txt(group, mode, timestamps).strip("\n")
            parts.append(_label_first_line(body, f"{name(spk)}: ") if spk else body)
        return "\n\n".join(parts) + "\n"
    sents = split_sentences(segs)
    ts = (lambda t: f"[{hms(t)}] ") if timestamps else (lambda t: "")
    if mode == "sentences":
        return "\n".join(ts(s["start"]) + s["text"] for s in sents) + "\n"
    if mode == "plain":
        if timestamps:
            return "\n".join(ts(s["start"]) + s["text"] for s in segs_clean(segs)) + "\n"
        return " ".join(s["text"] for s in sents) + "\n"
    paras = make_paragraphs(sents)
    return "\n\n".join(ts(p[0]["start"]) + " ".join(x["text"] for x in p) for p in paras) + "\n"


def segs_clean(segs: list[dict]) -> list[dict]:
    return [{"start": s["start"], "end": s["end"], "text": " ".join(str(s["text"]).split())}
            for s in segs if str(s["text"]).strip()]


# ---------------------------------------------------------------- punctuation checks

def unpunctuated_runs(segs: list[dict], limit: int = 40) -> int:
    """Words that sit in runs of >= `limit` words without ANY punctuation mark (not even a comma).
    Whisper sometimes drops all punctuation for a while; long sentences full of commas are not counted."""
    bad, run = 0, 0
    for s in segs:
        for tok in str(s["text"]).split():
            if WORD.search(tok):
                run += 1
            if re.search(r"[.,!?;:…]", tok):
                if run >= limit:
                    bad += run
                run = 0
    if run >= limit:
        bad += run
    return bad


def repeated_words(segs: list[dict]) -> int:
    """Words in segments that repeat the previous segment word for word (a Whisper loop)."""
    bad, prev = 0, None
    for s in segs:
        cur = " ".join(str(s["text"]).lower().split())
        if cur and cur == prev and len(cur) > 12:
            bad += len(WORD.findall(cur))
        prev = cur
    return bad


def _norm_tok(t: str) -> str:
    return re.sub(r"[^\w']+", "", t.lower())


def _loops(tokens: list[str]) -> list[tuple[int, int, int]]:
    """Phrases repeated back to back: [(start, phrase length, repeats)]. A single word needs 10 repeats
    (people do say "bah, bah, bah, bah"), a phrase of 2-8 words 4 repeats (speech almost never does that,
    Whisper loops do)."""
    w = [_norm_tok(t) for t in tokens]
    out, i, n_all = [], 0, len(w)
    while i < n_all:
        best = None
        for n in range(1, 9):
            need = 10 if n == 1 else 4
            if i + n * need > n_all:
                break
            unit = w[i:i + n]
            if not all(unit):
                continue
            r = 1
            while w[i + r * n:i + (r + 1) * n] == unit:
                r += 1
            if r >= need and (best is None or r * n > best[1] * best[2]):
                best = (i, n, r)
        if best:
            out.append(best)
            i = best[0] + best[1] * best[2]
        else:
            i += 1
    return out


def loop_words(segs: list[dict]) -> int:
    toks = " ".join(str(s["text"]) for s in segs).split()
    return sum(n * (r - 1) for _i, n, r in _loops(toks))


def collapse_loops(text: str) -> str:
    """Removes Whisper's repetition loops ("to be able to be able to be able ..."). A short repeat keeps one
    copy of the phrase; a long one (8+ repeats, a hallucination) is dropped completely."""
    toks = text.split()
    loops = _loops(toks)
    if not loops:
        return text
    out, pos = [], 0
    for i, n, r in loops:
        out += toks[pos:i]
        if r < (8 if n > 1 else 15):
            out += toks[i:i + n]
        pos = i + n * r
    out += toks[pos:]
    lead = " " if text[:1].isspace() else ""
    return lead + " ".join(out)


def badness(segs: list[dict]) -> int:
    return unpunctuated_runs(segs) + 2 * repeated_words(segs) + 3 * loop_words(segs)


def well_punctuated(text: str) -> bool:
    words = len(WORD.findall(text))
    if words < 8:
        return True
    marks = len(re.findall(r"[.!?…]", text))
    return marks * 30 >= words        # at least one sentence end per ~30 words


STYLE_PROMPTS = {
    "en": "Hello, and welcome. In this talk, we'll look at a few ideas. Let's begin, shall we?",
    "hu": "Sziasztok, üdvözöllek benneteket! Ebben az előadásban néhány gondolatot nézünk meg. Kezdjük is.",
    "de": "Hallo und willkommen. In diesem Vortrag schauen wir uns einige Ideen an. Fangen wir an.",
}
STYLE_DEFAULT = "Hello, and welcome. Let's begin."


def style_prompt(lang: str | None) -> str:
    return STYLE_PROMPTS.get((lang or "")[:2], STYLE_DEFAULT)


def choose_prompt(prev_text: str, lang: str | None) -> str:
    """Prompt for the next window: the previous text if it is well punctuated, else a punctuated style sample,
    so a run of missing punctuation cannot spread from one window to the next."""
    tail = prev_text[-220:]
    if tail and well_punctuated(tail):
        if len(prev_text) > 220:                       # drop the word that was cut in half
            cut = tail.find(" ")
            if 0 <= cut < 40:
                tail = tail[cut + 1:]
        return tail
    return style_prompt(lang)
