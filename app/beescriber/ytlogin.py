# -*- coding: utf-8 -*-
"""YouTube confirmation ("Sign in to confirm you're not a bot").

YouTube only accepts the cookies of a signed-in browser as proof. BeeScriber opens YouTube in its own window,
the user signs in there (and does whatever YouTube asks), then the YouTube cookies are saved to a cookies.txt
file in the data folder and yt-dlp uses that file. The window is closed right after saving, so YouTube does not
rotate (invalidate) the saved cookies. Nothing is sent anywhere else."""
from __future__ import annotations

import logging
import threading
import time
from email.utils import parsedate_to_datetime

from . import config

log = logging.getLogger(config.APP_ID)

COOKIES_PATH = config.DATA_DIR / "youtube-cookies.txt"
START_URL = "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
YT_URL = "https://www.youtube.com/"
SIGNED_IN = ("SAPISID", "__Secure-3PAPISID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO")


class YouTubeLogin:
    def __init__(self):
        self.window = None
        self._loaded = threading.Event()

    # ------------------------------------------------------------ window
    def open(self, title: str) -> bool:
        import webview
        if self.window is not None:
            try:
                self.window.show()
                self.window.restore()
            except Exception:  # noqa: BLE001
                pass
            return True
        self._loaded.clear()
        w = webview.create_window(title, url=START_URL, width=1040, height=780, min_size=(640, 520),
                                  background_color="#ffffff")
        w.events.loaded += self._loaded.set
        w.events.closed += self._closed
        self.window = w
        return True

    def _closed(self) -> None:
        self.window = None

    def close(self) -> None:
        w, self.window = self.window, None
        if w is not None:
            try:
                w.destroy()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------ saving
    def save(self) -> dict:
        """{"ok": True, "path": ...} or {"ok": False, "code": "no_window"|"not_signed_in"|"failed"}"""
        w = self.window
        if w is None:
            return {"ok": False, "code": "no_window"}
        try:
            url = (w.get_current_url() or "")
            if "youtube.com" not in url:                   # still on the Google sign-in pages: go to YouTube
                self._loaded.clear()
                w.load_url(YT_URL)
                self._loaded.wait(20)
                time.sleep(1.0)
            cookies = _flatten(w.get_cookies() or [])
        except Exception as e:  # noqa: BLE001
            log.warning("youtube cookies could not be read: %s", e)
            return {"ok": False, "code": "failed"}
        if not any(c["name"] in SIGNED_IN for c in cookies):
            return {"ok": False, "code": "not_signed_in"}
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = COOKIES_PATH.with_suffix(".tmp")
        tmp.write_text(to_netscape(cookies), encoding="utf-8")
        tmp.replace(COOKIES_PATH)
        log.info("youtube cookies saved (%d)", len(cookies))
        self.close()                                         # closing now keeps the saved cookies valid longer
        return {"ok": True, "path": str(COOKIES_PATH)}


def _flatten(simple_cookies) -> list[dict]:
    out = []
    for sc in simple_cookies:
        for name, m in sc.items():
            out.append({"name": name, "value": m.value, "domain": m["domain"] or ".youtube.com",
                        "path": m["path"] or "/", "secure": bool(m["secure"]), "httponly": bool(m["httponly"]),
                        "expires": _expiry(m["expires"])})
    return out


def _expiry(text) -> int:
    """0 = session cookie (yt-dlp keeps those too)."""
    if not text:
        return 0
    try:
        ts = int(parsedate_to_datetime(str(text)).timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0
    return ts if ts > time.time() else 0


def to_netscape(cookies: list[dict]) -> str:
    lines = ["# Netscape HTTP Cookie File", "# Saved by BeeScriber from its YouTube window. Keep it private.", ""]
    for c in cookies:
        dom = c["domain"]
        lines.append("\t".join([
            ("#HttpOnly_" if c.get("httponly") else "") + dom,
            "TRUE" if dom.startswith(".") else "FALSE",
            c.get("path") or "/",
            "TRUE" if c.get("secure") else "FALSE",
            str(int(c.get("expires") or 0)),
            c["name"],
            c.get("value") or "",
        ]))
    return "\n".join(lines) + "\n"
