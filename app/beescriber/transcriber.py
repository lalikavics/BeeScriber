# -*- coding: utf-8 -*-
"""Transcribes one item in windows (default 5 min). After every window the accepted text is saved to a journal,
so a pause, a crash or closing the app loses at most the window in progress (a few seconds of GPU work).

Seams: segments ending in the last `tail` seconds of a window are not accepted; the next window starts right
after the last accepted segment, so sentences are never cut at window borders.
Decoding: 'careful' (default) conditions every 30 s chunk on the previous text and starts from a punctuated
prompt, which keeps Whisper's punctuation; 'plain' decodes the chunks independently.
Punctuation guard: if a window still lacks punctuation or loops, it is redone once in the other mode and the
better result is kept."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from . import config, sources, textfmt
from .audio import SR, SR_BYTES, AudioStream
from .engine import Stop

log = logging.getLogger(config.APP_ID)
FIRST_WINDOW = 60


class TranscribeError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail[-500:]}")
        self.code, self.detail = code, detail[-1500:]


class Journal:
    """jobs/<id>.jsonl - one line per accepted window: {"pos": seconds done, "lang": .., "segs": [...]}"""

    def __init__(self, job_id: int, folder: Path = config.JOBS_DIR):
        self.path = folder / f"{job_id}.jsonl"

    def load(self) -> tuple[float, list[dict], str | None]:
        pos, segs, lang = 0.0, [], None
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        break                              # torn last line after a crash
                    pos = float(d["pos"])
                    segs += d["segs"]
                    lang = d.get("lang") or lang
        except OSError:
            pass
        return pos, segs, lang

    def append(self, pos: float, segs: list[dict], lang: str | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"pos": round(pos, 3), "lang": lang, "segs": segs}, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def reset(self) -> None:
        self.path.unlink(missing_ok=True)


def _words(segs: list[dict]) -> int:
    """Real words (repetition loops do not count)."""
    return sum(len(textfmt.WORD.findall(str(s["text"]))) for s in segs) - textfmt.loop_words(segs)


def transcribe(item: dict, engine, journal: Journal, settings, emit=None, should_stop=None,
               stream_factory=AudioStream) -> dict:
    """item: {"kind": "file"|"url", "source", "duration"}.  emit(event, **data) receives progress events.
    Returns {"segs", "lang", "pos", "duration"}. Raises Stop (pause/cancel) or TranscribeError."""
    emit = emit or (lambda *_a, **_k: None)
    win_s = int(settings.get("window_seconds") or 300)
    tail = float(settings.get("tail_seconds") or 15)
    forced = settings.get("language")
    forced = None if forced in (None, "", "auto") else forced
    guard = bool(settings.get("punct_guard"))
    careful_first = settings.get("first_pass") != "plain"
    gpu_limit = int(settings.get("gpu_limit") or 100)
    want_words = bool(settings.get("diarize"))                # word times let the speaker step split segments
    duration = item.get("duration")
    win_b = win_s * SR_BYTES
    first_b = min(win_s, FIRST_WINDOW) * SR_BYTES       # a short first window: text appears within seconds
    nwin = 0

    pos, segs_all, lang = journal.load()
    lang = forced or lang
    prev_text = " ".join(s["text"].strip() for s in segs_all[-40:])
    prompt = textfmt.choose_prompt(prev_text, lang) if segs_all else ""
    if segs_all:
        emit("resumed", pos=pos, segs=segs_all, lang=lang)
    if duration and pos >= duration - 0.5:
        return {"segs": segs_all, "lang": lang, "pos": pos, "duration": duration}

    attempts = 0
    t_start = time.time()
    audio_done = 0.0
    while True:
        attempts += 1
        emit("stream", pos=pos, attempt=attempts)
        stream = stream_factory(item["kind"], item["source"], pos, settings).start()
        got_audio = False
        attempt_pos = pos
        try:
            buf = stream.buffer
            while True:
                want = first_b if nwin == 0 else win_b
                n, eof = buf.wait_for(want, should_stop)
                if n == 0 or (eof and n < SR_BYTES * 0.3):        # nothing left / less than 0.3 s
                    break
                got_audio = True
                nwin += 1
                take = min(n, want)
                final = eof and n <= want
                pcm = buf.peek(take)
                dur = take / SR_BYTES
                emit("window", pos=pos, seconds=dur)
                base = pos
                t1 = time.time()

                def on_seg(s, _b=base):
                    emit("draft", start=_b + s["start"], end=_b + s["end"], text=s["text"])

                if not lang and careful_first and hasattr(engine, "detect"):
                    found = engine.detect(pcm)                    # the careful pass needs the language first
                    if found:
                        lang = found[0]
                        emit("language", lang=lang, prob=found[1])
                first_careful = careful_first and bool(lang)        # needs the language for the style prompt
                p1 = textfmt.choose_prompt(prev_text, lang) if first_careful else prompt
                segs, det_lang, prob = engine.transcribe(pcm, p1, lang, should_stop, on_seg,
                                                         careful=first_careful, offset=base, gpu_limit=gpu_limit,
                                                         words=want_words)
                if not lang:
                    lang = det_lang
                    emit("language", lang=lang, prob=prob)
                redone = False
                if guard:
                    bad = textfmt.badness(segs)
                    if bad:
                        emit("redo", pos=pos, words=bad)
                        p2 = prompt if first_careful else textfmt.style_prompt(lang)
                        segs2, _l, _p = engine.transcribe(pcm, p2, lang, should_stop, on_seg,
                                                          careful=not first_careful, offset=base,
                                                          gpu_limit=gpu_limit, words=want_words)
                        bad2 = textfmt.badness(segs2)
                        # keep the redo only if it is better and did not lose text
                        if bad2 < bad and _words(segs2) >= 0.85 * _words(segs):
                            segs, redone = segs2, True
                        log.info("punct guard at %.0fs: %d -> %d bad words, %s", pos, bad, bad2,
                                 "redo kept" if redone else "original kept")
                        emit("redo_result", pos=pos, before=bad, after=bad2, kept=redone)
                dt = time.time() - t1
                accepted, cut = segs, dur
                if not final and segs:
                    ok = [s for s in segs if s["end"] <= dur - tail]
                    if ok and ok[-1]["end"] >= 1.0:
                        accepted, cut = ok, ok[-1]["end"]
                cut_b = take if cut >= dur else int(round(cut * SR)) * 2
                acc2 = []
                for s in accepted:
                    text = textfmt.collapse_loops(s["text"])
                    seg = {"start": round(s["start"] + base, 3), "end": round(s["end"] + base, 3), "text": text}
                    if s.get("words") and text == s["text"]:     # word times only when the text is unchanged
                        seg["words"] = [[round(a + base, 3), round(b + base, 3), w] for a, b, w in s["words"]]
                    acc2.append(seg)
                accepted = acc2
                accepted = [s for s in accepted if s["text"].strip()]
                new_pos = pos + cut_b / SR_BYTES
                journal.append(new_pos, accepted, lang)            # saved before anything else moves
                segs_all += accepted
                buf.consume(cut_b)
                pos = new_pos
                audio_done += cut_b / SR_BYTES
                prev_text = " ".join(s["text"].strip() for s in segs_all[-40:])
                prompt = textfmt.choose_prompt(prev_text, lang)
                emit("accepted", pos=pos, segs=accepted, speed=round(dur / dt, 1) if dt > 0 else None,
                     redone=redone, avg_speed=round(audio_done / max(0.001, time.time() - t_start), 1))
                if final:
                    break
        finally:
            errors = stream.errors()
            stream.close()

        nothing_yet = not got_audio and not segs_all and pos == 0
        if nothing_yet:
            code = sources.classify_error(errors)
            if item["kind"] == "file" or code not in ("network", "unknown", "forbidden") or attempts >= 3:
                raise TranscribeError(code if code != "unknown" else "no_audio", errors)
        elif item["kind"] == "file" or not duration or pos >= duration - 5:
            break
        if got_audio and pos > attempt_pos:
            attempts = 0                                          # it progressed: count failures afresh
        if attempts >= 4:
            raise TranscribeError("incomplete", errors)
        log.warning("stream ended early at %.0fs/%.0fs (attempt %d): %s", pos, duration or 0, attempts,
                    errors[-300:])
        for _ in range(int(3 * max(1, attempts) / 0.5)):          # back off, but stay responsive to pause
            r = should_stop() if should_stop else None
            if r:
                raise Stop(r)
            time.sleep(0.5)
    return {"segs": segs_all, "lang": lang, "pos": pos, "duration": duration or pos}
