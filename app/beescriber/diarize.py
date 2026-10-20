# -*- coding: utf-8 -*-
"""Optional add-on: who speaks when (speaker diarization) with pyannote, fully local.

The add-on is not part of the base install (PyTorch alone is ~2.5 GB). When the user switches it on, the app
offers to download it, and asks for a free Hugging Face access token: the model's authors require every user
to accept its terms once. The token is stored only on this PC (<data>/hf_token).

Diarization runs after the transcript is ready: the audio is streamed once more (into memory only), pyannote
finds the speaker turns, and every Whisper segment gets the speaker it overlaps most."""
from __future__ import annotations

import importlib.util
import json
import logging
import re
import shutil
import sys
import threading
from pathlib import Path

from . import config, tools

log = logging.getLogger(config.APP_ID)

MODEL = "pyannote/speaker-diarization-community-1"
MODEL_URL = f"https://huggingface.co/{MODEL}"
TOKEN_URL = "https://huggingface.co/settings/tokens"
JOIN_URL = "https://huggingface.co/join"
TOKEN_PATH = config.DATA_DIR / "hf_token"
TORCH_INDEX_CUDA = "https://download.pytorch.org/whl/cu128"


# ---------------------------------------------------------------- state
def installed() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "pyannote.audio"))


def can_install() -> bool:
    return not getattr(sys, "frozen", False)          # the installer version will ship it as a separate pack


def token_get() -> str:
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def token_set(token: str) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token.strip(), encoding="utf-8")


def status() -> dict:
    return {"installed": installed(), "can_install": can_install(), "has_token": bool(token_get()),
            "model_url": MODEL_URL, "token_url": TOKEN_URL, "join_url": JOIN_URL}


def check_token(token: str) -> dict:
    """{"ok": True} or {"ok": False, "code": invalid|terms|network|unknown}"""
    token = (token or "").strip() or token_get()      # empty field: check the saved token again
    if len(token) < 20 or re.search(r"\s", token):         # format is checked by Hugging Face itself
        return {"ok": False, "code": "invalid"}
    try:
        from huggingface_hub import HfApi, hf_hub_download
        from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
    except ImportError:
        return {"ok": False, "code": "unknown"}
    try:
        HfApi().whoami(token=token)
    except HfHubHTTPError as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return {"ok": False, "code": "invalid" if code in (401, 403) else "network"}
    except Exception:  # noqa: BLE001
        return {"ok": False, "code": "network"}
    token_set(token)                                   # a working token is kept even if the terms are missing
    try:                                               # a gated file: works only after accepting the terms
        hf_hub_download(MODEL, "config.yaml", token=token)
    except GatedRepoError:
        return {"ok": False, "code": "terms"}
    except HfHubHTTPError as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return {"ok": False, "code": "terms" if code in (401, 403) else "network"}
    except Exception:  # noqa: BLE001
        return {"ok": False, "code": "network"}
    return {"ok": True}


# ---------------------------------------------------------------- installing
TORCH_MB, PYANNOTE_MB = 2900, 250                         # download sizes, for the progress bar


def install(progress=None, cancelled=None, bytes_progress=None) -> None:
    """pip install torch (CUDA build when an NVIDIA GPU is present) + pyannote.audio into this Python.
    progress(step, steps, label, line) for the add-on dialog; bytes_progress(got) for the first-start window."""
    if not can_install():
        raise RuntimeError("not supported in this build")
    torch_args = ["torch", "torchaudio"]
    if shutil.which("nvidia-smi"):
        torch_args += ["--index-url", TORCH_INDEX_CUDA]
    steps = [("PyTorch", torch_args), ("pyannote.audio", ["pyannote.audio"])]
    base = 0.0
    for i, (label, args) in enumerate(steps, 1):
        if progress:
            progress(i, len(steps), label, "")
        got = {"n": 0.0}

        def on_bytes(n, _b=base, _g=got):
            _g["n"] = n
            if bytes_progress:
                bytes_progress(_b + n)
        try:
            tools.pip_install(args, on_bytes, cancelled,
                              (lambda line, i=i, label=label: progress(i, len(steps), label, line)) if progress else None)
        except tools.Cancelled:
            raise RuntimeError("cancelled") from None
        base += got["n"]
    importlib.invalidate_caches()
    log.info("diarization add-on installed")


# ---------------------------------------------------------------- running
class Diarizer:
    _lock = threading.Lock()
    _pipe = None

    @classmethod
    def pipeline(cls):
        with cls._lock:
            if cls._pipe is None:
                tools.add_nvidia_dll_dirs()
                import torch
                from pyannote.audio import Pipeline
                token = token_get()
                try:
                    pipe = Pipeline.from_pretrained(MODEL, token=token)
                except TypeError:                       # pyannote 3.x
                    pipe = Pipeline.from_pretrained(MODEL, use_auth_token=token)
                if pipe is None:
                    raise RuntimeError("terms")
                if torch.cuda.is_available():
                    pipe.to(torch.device("cuda"))
                cls._pipe = pipe
            return cls._pipe

    @classmethod
    def run(cls, pcm: bytes, num_speakers: int | None = None) -> list[tuple[float, float, str]]:
        import numpy as np
        import torch
        audio = torch.from_numpy(np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0)[None, :]
        kw = {"num_speakers": int(num_speakers)} if num_speakers else {}
        out = cls.pipeline()({"waveform": audio, "sample_rate": 16000}, **kw)
        ann = getattr(out, "exclusive_speaker_diarization", None) or getattr(out, "speaker_diarization", None) or out
        return [(float(t.start), float(t.end), str(spk)) for t, _trk, spk in ann.itertracks(yield_label=True)]


def assign(segs: list[dict], turns: list[tuple[float, float, str]]) -> list[int | None]:
    """Speaker number (1, 2, ... in order of first appearance) for every segment, by the largest time overlap."""
    turns = sorted(turns)
    order: dict[str, int] = {}
    out: list[int | None] = []
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        best, best_ov = None, 0.0
        for t0, t1, spk in turns:
            if t1 <= a:
                continue
            if t0 >= b:
                break
            ov = min(b, t1) - max(a, t0)
            if ov > best_ov:
                best, best_ov = spk, ov
        if best is None and out:
            out.append(out[-1])                         # no speech turn under it: same as before
            continue
        if best is None:
            out.append(None)
            continue
        if best not in order:
            order[best] = len(order) + 1
        out.append(order[best])
    return out


def _speaker_at(turns: list, a: float, b: float):
    best, best_ov = None, 0.0
    for t0, t1, spk in turns:
        if t1 <= a:
            continue
        if t0 >= b:
            break
        ov = min(b, t1) - max(a, t0)
        if ov > best_ov:
            best, best_ov = spk, ov
    if best is None:                                    # between turns: the nearest one
        mid = (a + b) / 2
        near = min(turns, key=lambda t: min(abs(mid - t[0]), abs(mid - t[1])), default=None)
        best = near[2] if near else None
    return best


def _units(segs: list[dict]) -> list[dict]:
    """Sentences (from the word times) as the units that get a speaker. Splitting in the middle of a sentence
    because of a few milliseconds of difference between the word times and the speaker turns made the text
    jump between speakers word by word, so a speaker can change only at a sentence end - or, in a very long
    sentence, at a clear pause."""
    units: list[dict] = []
    cur: list = []

    def flush():
        if cur:
            units.append({"start": cur[0][0], "end": cur[-1][1], "text": "".join(w for _a, _b, w in cur)})
            cur.clear()
    for s in segs:
        words = s.get("words")
        if not words:
            flush()
            units.append({"start": s["start"], "end": s["end"], "text": s["text"]})
            continue
        for a, b, w in words:
            if cur and len(cur) >= 25 and a - cur[-1][1] > 0.6:     # long run-on sentence: a pause may split it
                flush()
            cur.append((float(a), float(b), w))
            if re.search(r"[.!?…][\"”’)\]]*$", w.strip()):
                flush()
    flush()
    return units


def split_by_speaker(segs: list[dict], turns: list[tuple[float, float, str]]) -> list[dict]:
    """Segments with a "speaker" number (1, 2, ... in order of first appearance)."""
    turns = sorted(turns)
    order: dict[str, int] = {}
    out: list[dict] = []
    for u in _units(segs):
        spk = _speaker_at(turns, float(u["start"]), float(u["end"]))
        if spk is not None and spk not in order:
            order[spk] = len(order) + 1
        n = order.get(spk) if spk is not None else (out[-1]["speaker"] if out else None)
        if out and out[-1]["speaker"] == n:
            out[-1]["text"] += u["text"] if u["text"].startswith(" ") else " " + u["text"]
            out[-1]["end"] = u["end"]
        else:
            out.append({"start": u["start"], "end": u["end"], "text": u["text"], "speaker": n})
    return [x for x in out if str(x["text"]).strip()]


def save(job_id: int, labels: list, folder: Path = config.JOBS_DIR) -> None:
    (folder / f"{job_id}.speakers.json").write_text(json.dumps(labels), encoding="utf-8")


def load(job_id: int, folder: Path = config.JOBS_DIR) -> list | None:
    try:
        return json.loads((folder / f"{job_id}.speakers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def apply(segs: list[dict], saved: list | None) -> list[dict]:
    """saved = the speaker segments (new format) or one speaker number per segment (first version)."""
    if not saved:
        return segs
    if isinstance(saved[0], dict):
        return saved
    if len(saved) != len(segs):
        return segs
    return [dict(s, speaker=l) for s, l in zip(segs, saved)]
