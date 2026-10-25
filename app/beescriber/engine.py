# -*- coding: utf-8 -*-
"""Speech-to-text engines. WhisperEngine = faster-whisper (CTranslate2, CUDA). FakeEngine = tests without a GPU."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from . import config, tools

log = logging.getLogger(config.APP_ID)


class Stop(Exception):
    """Raised when the user pauses / cancels / the app closes. reason: pause | cancel | shutdown"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class EngineError(Exception):
    pass


def _rest(seconds: float, should_stop) -> None:
    end = time.time() + min(seconds, 5.0)
    while time.time() < end:
        _check(should_stop)
        time.sleep(min(0.05, max(0.0, end - time.time())))


def _check(should_stop) -> None:
    r = should_stop() if should_stop else None
    if r:
        raise Stop(r)


class WhisperEngine:
    name = "faster-whisper"

    def __init__(self, model: str, device: str = "auto", compute: str = "auto", status=None, cancelled=None):
        tools.add_nvidia_dll_dirs()
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise EngineError(f"faster-whisper is not installed: {e}") from e
        self.model_ref = model
        if device == "auto":
            try:
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:  # noqa: BLE001
                device = "cpu"
        from . import models
        path = models.local_path(model)
        if not path:                                    # a model name that is not downloaded yet
            if Path(model).exists():
                raise EngineError(f"not a CTranslate2 Whisper model folder: {model}")
            log.info("downloading model %s", model)

            def prog(done, total, _f):
                if status:
                    status("model_download", model=model, done=done, total=total)
            prog(0, 0, "")
            path = models.download(model, prog, cancelled)
        if status:
            status("model_load", model=model, device=device)
        t = time.time()
        self.fallback = None
        try:
            self.model = WhisperModel(path, device=device,
                                      compute_type=compute if compute != "auto" else
                                      ("float16" if device == "cuda" else "int8"))
        except Exception as e:  # noqa: BLE001
            if device != "cuda":
                raise EngineError(str(e)) from e
            log.warning("CUDA load failed, falling back to CPU: %s", e)
            self.fallback = str(e)
            device = "cpu"
            self.model = WhisperModel(path, device="cpu", compute_type="int8")
        self.device = device
        self.compute = compute if compute != "auto" else ("float16" if device == "cuda" else "int8")
        self.load_s = time.time() - t
        log.info("model %s loaded on %s/%s in %.1fs", model, self.device, self.compute, self.load_s)

    def detect(self, pcm: bytes):
        """Language of the speech in pcm (uses up to the first 60 s of speech) -> (code, probability) or None."""
        import numpy as np
        try:
            audio = np.frombuffer(pcm[:60 * 32000], dtype=np.int16).astype(np.float32) / 32768.0
            lang, prob, _all = self.model.detect_language(audio, vad_filter=True, language_detection_segments=2)
            return lang, float(prob)
        except Exception as e:  # noqa: BLE001  (older faster-whisper / no speech found)
            log.info("language detection skipped: %s", e)
            return None

    def transcribe(self, pcm: bytes, prompt: str, lang: str | None, should_stop=None, on_segment=None,
                   careful: bool = False, offset: float = 0.0, gpu_limit: int = 100, words: bool = False):
        """-> (segments [{start, end, text}] relative to the window, detected language, probability)
        words=True adds per-word times ("words": [[start, end, word], ...]) - needed to split by speaker.
        gpu_limit < 100: after each piece of GPU work, rest for a proportional moment, so on average the GPU
        works only that share of the time and the rest of the PC stays responsive."""
        import numpy as np
        _check(should_stop)
        rest = max(0.0, 100.0 / max(10, min(100, int(gpu_limit or 100))) - 1.0)
        t = time.time()
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segs_iter, info = self.model.transcribe(
            audio, language=lang or None, beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=careful, initial_prompt=prompt or None, word_timestamps=words)
        out = []
        it = iter(segs_iter)
        while True:
            try:
                s = next(it)                            # decoding happens lazily, a fraction of a second each
            except StopIteration:
                break
            if rest:
                _rest((time.time() - t) * rest, should_stop)
            seg = {"start": float(s.start), "end": float(s.end), "text": s.text}
            if words and getattr(s, "words", None):
                seg["words"] = [[round(float(w.start), 3), round(float(w.end), 3), w.word] for w in s.words]
            out.append(seg)
            if on_segment:
                on_segment(seg)
            _check(should_stop)
            t = time.time()
        return out, info.language, float(info.language_probability or 0)


class FakeEngine:
    """Self-test engine: one segment per `step` seconds, text 'T<abs second>.'
    unpunct=True -> plain mode returns text without punctuation, careful mode returns punctuated text."""
    name = "fake"
    device = "none"
    compute = "none"
    load_s = 0.0
    fallback = None

    def __init__(self, step: float = 10.0, delay: float = 0.0, unpunct: bool = False, lang: str = "en"):
        self.step, self.delay, self.unpunct, self.lang = step, delay, unpunct, lang
        self.calls = 0

    def detect(self, pcm: bytes):
        return (self.lang, 1.0) if self.lang else None

    def transcribe(self, pcm: bytes, prompt: str, lang: str | None, should_stop=None, on_segment=None,
                   careful: bool = False, offset: float = 0.0, gpu_limit: int = 100, words: bool = False):
        self.calls += 1
        d = len(pcm) / 32000.0
        out, k = [], 0
        while k * self.step < d - 0.01:
            _check(should_stop)
            if self.delay:
                time.sleep(self.delay)
            t = int(round(offset + k * self.step))
            if self.unpunct and not careful:
                text = f"word{t} alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma"
            elif self.unpunct:
                text = f"Word{t}, alpha beta gamma. Delta epsilon zeta, eta theta iota. Kappa lambda mu nu. Xi omicron pi rho sigma."
            else:
                text = f"T{t}."
            seg = {"start": k * self.step, "end": min(k * self.step + self.step, d), "text": text}
            if words:
                ws = text.split()
                span = (seg["end"] - seg["start"]) / max(1, len(ws))
                seg["words"] = [[seg["start"] + i * span, seg["start"] + (i + 1) * span, " " + w] for i, w in enumerate(ws)]
            out.append(seg)
            if on_segment:
                on_segment(seg)
            k += 1
        _check(should_stop)
        return out, lang or self.lang, 1.0
