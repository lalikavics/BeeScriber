# -*- coding: utf-8 -*-
"""Whisper models: where they are, and downloading them with real progress (resumable, cancellable).
Models are stored in <data>/models/<name>. A copy already in the Hugging Face cache is used as well."""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

from . import config

log = logging.getLogger(config.APP_ID)

HF = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
FALLBACK_REPOS = {
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v2": "Systran/faster-whisper-large-v2",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base",
    "tiny": "Systran/faster-whisper-tiny",
}
PATTERNS = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
APPROX_MB = {"large-v3-turbo": 1620, "turbo": 1620, "large-v3": 3090, "large-v2": 3090, "medium": 1530,
             "small": 486, "base": 148, "tiny": 78}
MODELS_DIR = config.DATA_DIR / "models"


class Cancelled(Exception):
    pass


def repo_of(name: str) -> str:
    try:
        from faster_whisper.utils import _MODELS
        if name in _MODELS:
            return _MODELS[name]
    except Exception:  # noqa: BLE001
        pass
    return FALLBACK_REPOS.get(name, name)


def local_path(name: str) -> str | None:
    """A ready model folder for `name` (a path to a folder also counts), or None."""
    p = Path(name)
    if p.is_dir() and (p / "model.bin").exists():
        return str(p)
    own = MODELS_DIR / name
    if (own / ".complete").exists():
        return str(own)
    try:                                                     # Hugging Face cache (e.g. from the dev test)
        from faster_whisper.utils import download_model
        return download_model(name, local_files_only=True)
    except Exception:  # noqa: BLE001
        return None


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": f"{config.APP_NAME}/{config.VERSION}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def file_list(name: str) -> list[tuple[str, int]]:
    repo = repo_of(name)
    tree = _get_json(f"{HF}/api/models/{repo}/tree/main")
    out = []
    for f in tree:
        if f.get("type") != "file":
            continue
        path = f["path"]
        if any(fnmatch.fnmatch(path, pat) for pat in PATTERNS):
            size = (f.get("lfs") or {}).get("size") or f.get("size") or 0
            out.append((path, int(size)))
    if not any(p == "model.bin" for p, _ in out):
        raise RuntimeError(f"model.bin not found in {repo}")
    return out


def download(name: str, progress=None, cancelled=None) -> str:
    """progress(done_bytes, total_bytes, file) ; cancelled() -> True stops (partial files are kept and resumed)."""
    repo = repo_of(name)
    dest = MODELS_DIR / name
    dest.mkdir(parents=True, exist_ok=True)
    files = file_list(name)
    total = sum(s for _, s in files)
    done_before = 0
    for path, size in files:
        target = dest / path
        part = target.with_name(target.name + ".part")
        if target.exists() and (not size or target.stat().st_size == size):
            done_before += size
            continue
        have = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(f"{HF}/{repo}/resolve/main/{path}",
                                     headers={"User-Agent": f"{config.APP_NAME}/{config.VERSION}",
                                              **({"Range": f"bytes={have}-"} if have else {})})
        with urllib.request.urlopen(req, timeout=60) as r:
            if have and r.status != 206:                     # server ignored the range: start over
                have = 0
            with open(part, "ab" if have else "wb") as f:
                got, last = have, 0.0
                while True:
                    if cancelled and cancelled():
                        raise Cancelled()
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if progress and time.time() - last > 0.25:
                        last = time.time()
                        progress(done_before + got, total, path)
        if size and part.stat().st_size != size:
            raise RuntimeError(f"{path}: incomplete download ({part.stat().st_size} / {size} bytes)")
        part.replace(target)
        done_before += size or target.stat().st_size
        if progress:
            progress(done_before, total, path)
    (dest / ".complete").write_text(repo, encoding="utf-8")
    log.info("model %s downloaded to %s", name, dest)
    return str(dest)
