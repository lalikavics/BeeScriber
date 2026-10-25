# -*- coding: utf-8 -*-
"""What the user typed or dropped -> a list of things to transcribe (YouTube videos/playlists, local files)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import tools

MEDIA_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif",
             ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts"}
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be",
            "www.youtube-nocookie.com", "youtube-nocookie.com"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# yt-dlp messages -> short error codes (the UI translates the codes). Order matters: first match wins.
ERROR_RULES = [
    ("bot", ["sign in to confirm", "not a bot"]),
    ("private", ["private video", "this video is private"]),
    ("members", ["members-only", "join this channel", "available to this channel's members"]),
    ("age", ["confirm your age", "age-restricted", "inappropriate for some users"]),
    ("live", ["live event will begin", "premieres in", "this live event", "is_upcoming"]),
    ("js", ["javascript runtime", "no supported javascript", "n challenge", "signature solving"]),
    ("forbidden", ["http error 403"]),
    ("cookies", ["could not copy", "failed to decrypt", "cookies database", "could not find firefox",
                 "could not find chrome", "cookie file", "netscape format"]),
    ("unavailable", ["video unavailable", "has been removed", "does not exist", "is not available",
                     "no longer available", "account associated with this video has been terminated"]),
    ("network", ["timed out", "getaddrinfo", "temporary failure", "unable to download webpage",
                 "connection reset", "network is unreachable", "failed to resolve", "remote end closed"]),
]


class SourceError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail[-600:]}")
        self.code = code
        self.detail = detail[-1500:]


def classify_error(text: str) -> str:
    low = (text or "").lower()
    for code, keys in ERROR_RULES:
        if any(k in low for k in keys):
            return code
    return "unknown"


def cookie_args(settings) -> list[str]:
    mode = settings.get("cookies_mode")
    if mode == "browser" and settings.get("cookies_browser"):
        return ["--cookies-from-browser", str(settings.get("cookies_browser"))]
    if mode == "file" and settings.get("cookies_file"):
        return ["--cookies", str(settings.get("cookies_file"))]
    return []


# ---------------------------------------------------------------- input parsing

def parse_input(text: str) -> dict:
    """One line of user input -> {"kind": "file"|"youtube"|"url"|"invalid", ...}"""
    s = (text or "").strip().strip('"').strip("'")
    if not s:
        return {"kind": "invalid", "input": text}
    p = Path(s)
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I) and p.suffix.lower() in MEDIA_EXT:
        return {"kind": "file", "path": str(p), "exists": p.exists(), "input": s}
    if VIDEO_ID.match(s):
        return {"kind": "youtube", "video_id": s, "list_id": None, "url": f"https://www.youtube.com/watch?v={s}",
                "input": s}
    if re.match(r"^(PL|UU|OL|FL|RD|LL)[A-Za-z0-9_-]{8,}$", s):
        return {"kind": "youtube", "video_id": None, "list_id": s,
                "url": f"https://www.youtube.com/playlist?list={s}", "input": s}
    if not re.match(r"^https?://", s, re.I):
        if re.match(r"^(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", s, re.I):
            s = "https://" + s
        else:
            return {"kind": "invalid", "input": text}
    u = urlparse(s)
    host = (u.hostname or "").lower()
    if host not in YT_HOSTS:
        return {"kind": "url", "url": s, "input": s}          # other sites: let yt-dlp decide
    q = parse_qs(u.query)
    vid = (q.get("v") or [None])[0]
    lst = (q.get("list") or [None])[0]
    parts = [x for x in u.path.split("/") if x]
    if host == "youtu.be" and parts:
        vid = parts[0]
    elif parts and parts[0] in ("shorts", "live", "embed", "v") and len(parts) > 1:
        vid = parts[1]
    channel = None
    if parts and (parts[0].startswith("@") or parts[0] in ("channel", "c", "user")):
        base = "/".join(parts[:2] if parts[0] in ("channel", "c", "user") else parts[:1])
        tab = parts[2 if parts[0] in ("channel", "c", "user") else 1:]
        channel = f"https://www.youtube.com/{base}/" + (tab[0] if tab else "videos")
    if vid and not VIDEO_ID.match(vid):
        vid = None
    if channel and not vid and not lst:
        return {"kind": "youtube", "video_id": None, "list_id": None, "channel_url": channel, "url": channel,
                "input": s}
    if not vid and not lst:
        return {"kind": "invalid", "input": text}
    url = (f"https://www.youtube.com/playlist?list={lst}" if lst and not vid
           else f"https://www.youtube.com/watch?v={vid}")
    return {"kind": "youtube", "video_id": vid, "list_id": lst, "url": url, "input": s,
            "both": bool(vid and lst)}


# ---------------------------------------------------------------- loading

def _ytdlp_json(args: list[str], settings) -> dict:
    exe = tools.tool("yt-dlp")
    if not exe:
        raise SourceError("tools", "yt-dlp missing")
    r = tools.run([exe, "--encoding", "utf-8", "--dump-single-json", "--no-warnings"] + cookie_args(settings) + args,
                  timeout=600)
    if r.returncode != 0 or not r.stdout.strip().startswith("{"):
        err = (r.stderr or r.stdout or "").strip()
        raise SourceError(classify_error(err), err)
    return json.loads(r.stdout)


def _entry_status(e: dict) -> str:
    title = e.get("title") or ""
    if title in ("[Private video]", "[Deleted video]") or e.get("availability") in ("private", "needs_auth"):
        return "unavailable"
    if e.get("availability") in ("subscriber_only", "premium_only"):
        return "members"
    if e.get("live_status") in ("is_upcoming", "is_live"):
        return "live"
    return "ok"


def _item(e: dict, index: int, channel: str | None) -> dict:
    vid = e.get("id")
    url = e.get("webpage_url") or e.get("url") or ""
    if vid and (not url.startswith("http") or "youtube.com" in url or "youtu.be" in url):
        if VIDEO_ID.match(str(vid)):
            url = f"https://www.youtube.com/watch?v={vid}"
    return {"kind": "url", "source": url, "video_id": vid, "title": e.get("title") or vid or "?",
            "duration": float(e["duration"]) if e.get("duration") else None,
            "channel": e.get("channel") or e.get("uploader") or channel,
            "index": index, "status": _entry_status(e)}


def load_url(url: str, settings, as_video: bool = False) -> dict:
    """URL -> {"type": "playlist"|"video", "id", "title", "channel", "url", "entries": [...], "load_s"}"""
    t0 = time.time()
    args = ["--no-playlist", url] if as_video else ["--yes-playlist", "--flat-playlist", url]
    data = _ytdlp_json(args, settings)
    if data.get("_type") == "playlist":
        entries = data.get("entries") or []
        # channel pages can return nested playlists (Videos / Shorts tabs): flatten one level
        if entries and all(isinstance(e, dict) and e.get("_type") == "playlist" for e in entries if e):
            flat = []
            for sub in entries:
                flat += [x for x in (sub.get("entries") or []) if x]
            entries = flat
        ch = data.get("channel") or data.get("uploader")
        items = [_item(e, i, ch) for i, e in enumerate([e for e in entries if e], 1)]
        return {"type": "playlist", "id": data.get("id"), "title": data.get("title") or data.get("id"),
                "channel": ch, "url": url, "entries": items, "load_s": round(time.time() - t0, 1)}
    it = _item(data, 1, None)
    return {"type": "video", "id": data.get("id"), "title": it["title"], "channel": it["channel"], "url": url,
            "entries": [it], "load_s": round(time.time() - t0, 1)}


def probe_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SourceError("file_missing", path)
    if p.suffix.lower() not in MEDIA_EXT:
        raise SourceError("file_type", path)
    dur = None
    ff = tools.tool("ffmpeg")
    if ff:
        r = tools.run([ff, "-hide_banner", "-i", str(p)], timeout=60)
        m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
        if m:
            dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        if "Audio:" not in (r.stderr or ""):
            raise SourceError("no_audio", path)
    return {"kind": "file", "source": str(p.resolve()), "video_id": None, "title": p.stem, "duration": dur,
            "channel": None, "index": 1, "status": "ok"}


def expand_paths(paths: list[str]) -> list[str]:
    """Dropped files and folders -> media files (folders: non-recursive, sorted by name)."""
    out: list[str] = []
    for s in paths:
        p = Path(s)
        if p.is_dir():
            out += [str(x) for x in sorted(p.iterdir(), key=lambda x: x.name.lower())
                    if x.is_file() and x.suffix.lower() in MEDIA_EXT]
        elif p.suffix.lower() in MEDIA_EXT:
            out.append(str(p))
    return out
