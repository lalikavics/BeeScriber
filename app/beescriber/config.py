# -*- coding: utf-8 -*-
"""Central configuration. Rename the app here (APP_NAME) - nothing else hard-codes the name."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

APP_NAME = "BeeScriber"
APP_ID = "beescriber"                 # folder / file names, never shown to the user
VERSION = "1.0.0"
AUTHOR = "Lalikavics"
COFFEE_URL = "https://buymeacoffee.com/lalikavics"
REPO_URL = "https://github.com/lalikavics/BeeScriber"

IS_WIN = os.name == "nt"
EXE = ".exe" if IS_WIN else ""

# ---------------------------------------------------------------- folders
PKG_DIR = Path(__file__).resolve().parent                 # .../app/beescriber
if getattr(sys, "frozen", False):                          # PyInstaller build
    RES_DIR = Path(getattr(sys, "_MEIPASS", PKG_DIR))
    ROOT = Path(sys.executable).resolve().parent
else:
    RES_DIR = PKG_DIR
    ROOT = PKG_DIR.parent.parent                           # the source folder (development)
UI_DIR = RES_DIR / "ui"


OLD_NAMES = [("BeeScribe", "beescribe")]               # earlier names of the app: their data is taken over once


def _data_dir() -> Path:
    env = os.environ.get("BEESCRIBER_DATA") or os.environ.get("BEESCRIBE_DATA")
    if env:
        return Path(env)
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return _migrate(base, APP_NAME, 0)
    return _migrate(Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"), APP_ID, 1)


def _migrate(base: Path, name: str, k: int) -> Path:
    """First start after the rename: move the old data folder (history, settings, model, add-on) to the new name."""
    new = base / name
    if new.exists():
        return new
    for old_names in OLD_NAMES:
        old = base / old_names[k]
        if not old.is_dir():
            continue
        try:
            old.rename(new)
        except OSError:
            return old                                     # in use or not allowed: keep working from the old folder
        for suffix in ("db", "db-wal", "db-shm", "log"):
            f = new / f"{old_names[1]}.{suffix}"
            if f.exists():
                try:
                    f.rename(new / f"{APP_ID}.{suffix}")
                except OSError:
                    pass
        return new
    return new


DATA_DIR = _data_dir()
# Development: reuse the tools already downloaded by devtest (ROOT\tools). Installed app: data folder.
TOOLS_DIR = ROOT / "tools" if (ROOT / "tools" / "bin").exists() else DATA_DIR / "tools"
BIN_DIR = TOOLS_DIR / "bin"
DB_PATH = DATA_DIR / f"{APP_ID}.db"
JOBS_DIR = DATA_DIR / "jobs"                               # per-job segment journals (resume data)
SETTINGS_PATH = DATA_DIR / "settings.json"
LOG_PATH = DATA_DIR / f"{APP_ID}.log"


def default_output_dir() -> str:
    docs = Path.home() / "Documents"
    base = docs if docs.exists() else Path.home()
    new = base / APP_NAME
    for old_name, _ in OLD_NAMES:                          # transcripts made under an earlier name stay where they are
        if not new.exists() and (base / old_name).is_dir():
            return str(base / old_name)
    return str(new)


# ---------------------------------------------------------------- settings
MODELS = ["large-v3-turbo", "large-v3", "medium", "small", "base"]
FORMATS = ["txt", "srt", "vtt", "html", "pdf", "docx"]
TXT_MODES = ["paragraphs", "sentences", "plain"]

DEFAULTS: dict = {
    "ui_lang": "en",
    "model": "large-v3-turbo",
    "custom_model": "",              # path to a CTranslate2 model folder (overrides "model")
    "device": "auto",                # auto | cuda | cpu
    "compute": "auto",
    "language": "auto",              # auto | en | hu | ...
    "formats": ["txt"],
    "txt_mode": "paragraphs",
    "timestamps": False,
    "output_dir": "",                # "" -> default_output_dir()
    "playlist_subfolder": True,
    "name_template": "{title}",
    "playlist_name_template": "{index:03} - {title}",
    "skip_done": True,
    "punct_guard": True,
    "first_pass": "careful",         # careful = conditioned decoding with a punctuated prompt; plain = independent chunks
    "cookies_mode": "none",          # none | browser | file
    "cookies_browser": "firefox",
    "cookies_file": "",
    "pause_after_video": False,
    "clipboard_watch": True,         # load YouTube links copied to the clipboard automatically
    "txt_header": True,              # title + details at the top of TXT files
    "gpu_limit": 90,
    "speaker_intro": False,          # the add-on guide was shown once after the installer
    "diarize": False,                # mark who speaks (optional pyannote add-on)
    "speakers": 0,                   # number of speakers, 0 = automatic                 # % of the time the GPU may work (leaves room for the rest of the PC)
    "window": {},                    # last window position / size
    "window_seconds": 300,
    "tail_seconds": 15,
}


class Settings:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.data = dict(DEFAULTS)
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def get(self, key: str):
        with self.lock:
            return self.data.get(key, DEFAULTS.get(key))

    def all(self) -> dict:
        with self.lock:
            d = dict(self.data)
        d["output_dir_effective"] = d["output_dir"] or default_output_dir()
        return d

    def update(self, changes: dict) -> dict:
        with self.lock:
            for k, v in (changes or {}).items():
                if k in DEFAULTS:
                    self.data[k] = v
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        return self.all()

    def output_dir(self) -> Path:
        return Path(self.get("output_dir") or default_output_dir())
