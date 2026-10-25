# -*- coding: utf-8 -*-
"""Desktop app: a pywebview window (Edge WebView2 on Windows) showing ui/index.html, plus the Python API it calls."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

from . import config, sources, tools
from .config import Settings
from .jobqueue import JobQueue, done_key

log = logging.getLogger(config.APP_ID)


class EventPump:
    """Collects backend events and hands them to the page in batches (max ~6 per second),
    so a fast transcription never floods the UI."""

    def __init__(self):
        self.window = None
        self.lock = threading.Lock()
        self.items: list[dict] = []
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def push(self, ev: str, **data) -> None:
        with self.lock:
            # only the newest progress/draft/queue state matters
            if ev in ("queue", "progress"):
                self.items = [x for x in self.items if x["ev"] != ev]
            self.items.append({"ev": ev, **data})

    def _run(self) -> None:
        while True:
            time.sleep(0.16)
            with self.lock:
                batch, self.items = self.items, []
            if batch and self.window:
                try:
                    payload = json.dumps(batch, ensure_ascii=False, default=str)
                    self.window.evaluate_js(f"window.BS && BS.onEvents({payload})")
                except Exception as e:  # noqa: BLE001
                    log.debug("evaluate_js failed: %s", e)


def _open(path: str) -> None:
    if config.IS_WIN:
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class Api:
    """Everything the page can call (window.pywebview.api.<name>). Every method returns plain JSON data;
    errors come back as {"error": code, "detail": text} instead of exceptions."""

    def __init__(self, settings: Settings, pump: EventPump):
        self._settings = settings
        self._pump = pump
        self._window = None
        self._last_clip = None
        self._chrome = None
        self._queue = JobQueue(settings, pump.push)

    # ------------------------------------------------------------ helpers
    def _w(self):
        return self._window

    @staticmethod
    def _safe(fn):
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except sources.SourceError as e:
                return {"error": e.code, "detail": e.detail}
            except Exception as e:  # noqa: BLE001
                log.error("api error: %s", traceback.format_exc())
                return {"error": "internal", "detail": str(e)[-800:]}
        wrap.__name__ = fn.__name__
        return wrap

    # ------------------------------------------------------------ start-up
    def init(self):
        return {
            "app": {"name": config.APP_NAME, "version": config.VERSION, "author": config.AUTHOR,
                    "coffee": config.COFFEE_URL, "repo": config.REPO_URL},
            "settings": self._settings.all(),
            "models": config.MODELS, "formats": config.FORMATS,
            "state": self._queue.state(),
            "jobs": self._queue.jobs(),
            "history_count": len(self._queue.jobs(history=True)),
            "missing_tools": tools.missing(),
            "data_dir": str(config.DATA_DIR),
            "open_speakers": self._speaker_intro(),
        }

    def _speaker_intro(self) -> bool:
        """Chosen in the installer and installed, but no access key yet: show the 2nd step of the guide once."""
        from . import diarize, setup
        try:
            return bool(setup.install_options().get("speakers") and not self._settings.get("speaker_intro")
                        and diarize.installed() and not diarize.token_get())
        except Exception:  # noqa: BLE001
            return False

    def tool_versions(self):
        g = tools.gpu_info()
        out = {n: tools.version(n) for n in tools.REQUIRED}
        out["gpu"] = g
        try:
            import faster_whisper
            out["faster_whisper"] = faster_whisper.__version__
        except Exception:  # noqa: BLE001
            out["faster_whisper"] = None
        return out

    def install_tools(self):
        def run():
            for name in tools.missing():
                self._pump.push("tools", status="downloading", name=name)
                try:
                    tools.install(name, lambda got, total, n=name: self._pump.push(
                        "tools", status="progress", name=n, got=got, total=total))
                except Exception as e:  # noqa: BLE001
                    self._pump.push("tools", status="error", name=name, detail=str(e))
                    return
            self._pump.push("tools", status="done", missing=tools.missing())
        threading.Thread(target=run, daemon=True).start()
        return True

    def update_ytdlp(self):
        return {"version": tools.update_ytdlp()}

    def usage(self):
        return tools.usage()

    # ------------------------------------------------------------ settings
    def save_settings(self, changes):
        return self._settings.update(changes or {})

    # ------------------------------------------------------------ loading sources
    def _annotate(self, entries: list[dict]) -> list[dict]:
        done, active = self._queue.done_keys(), self._queue.active_keys()
        for e in entries:
            k = done_key(e["kind"], e["source"], e.get("video_id"))
            e["done_before"] = k in done
            e["in_queue"] = k in active
        return entries

    def load_input(self, text: str, as_video: bool = False):
        """Several lines allowed (one link per line). Returns {"collections": [...], "errors": [...]}."""
        cols, errors = [], []
        for line in [x.strip() for x in str(text or "").splitlines() if x.strip()]:
            p = sources.parse_input(line)
            try:
                if p["kind"] == "file":
                    it = sources.probe_file(p["path"])
                    cols.append({"type": "files", "id": None, "title": Path(p["path"]).name,
                                 "entries": self._annotate([it])})
                    continue
                if p["kind"] == "invalid":
                    errors.append({"input": line, "error": "invalid"})
                    continue
                url = p["url"]
                if p.get("both") and not as_video:
                    url = f"https://www.youtube.com/playlist?list={p['list_id']}"
                col = sources.load_url(url, self._settings, as_video=as_video and bool(p.get("video_id")))
                col["both"] = bool(p.get("both")) and not as_video
                col["input"] = line
                col["entries"] = self._annotate(col["entries"])
                cols.append(col)
            except sources.SourceError as e:
                errors.append({"input": line, "error": e.code, "detail": e.detail})
        return {"collections": cols, "errors": errors}

    def _media_filter(self):
        exts = ";".join("*" + e for e in sorted(sources.MEDIA_EXT))
        # pywebview accepts only letters, digits and spaces in the description
        return (f"Audio and video files ({exts})", "All files (*.*)")

    def pick_files(self):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        res = self._w().create_file_dialog(kind, allow_multiple=True, file_types=self._media_filter())
        return self.files_to_items(list(res or []))

    def files_to_items(self, paths):
        items, errors = [], []
        for p in list(paths or []):
            pp = Path(p)
            if not pp.is_dir() and pp.suffix.lower() not in sources.MEDIA_EXT:
                errors.append({"input": pp.name, "error": "file_type"})
        for p in sources.expand_paths(list(paths or [])):
            try:
                items.append(sources.probe_file(p))
            except sources.SourceError as e:
                errors.append({"input": p, "error": e.code})
        return {"collections": [{"type": "files", "id": None, "title": None, "entries": self._annotate(items)}]
                if items else [], "errors": errors}

    def pick_folder(self, start: str = ""):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = self._w().create_file_dialog(kind, directory=start or str(self._settings.output_dir()))
        if not res:
            return None
        return res[0] if isinstance(res, (list, tuple)) else res

    def pick_cookie_file(self):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        res = self._w().create_file_dialog(kind, file_types=("Cookies file (*.txt)", "All files (*.*)"))
        return res[0] if res else None

    # ------------------------------------------------------------ queue
    def enqueue(self, items, collection=None, start=False):
        ids = self._queue.add(list(items or []), collection or None)
        if start:
            self._queue.start()
        return {"ids": ids, "jobs": self._queue.jobs(), "state": self._queue.state()}

    def start(self):
        self._queue.start()
        return self._queue.state()

    def pause(self, now=True):
        self._queue.pause_all(now=bool(now))
        return self._queue.state()

    def job_pause(self, job_id):
        self._queue.pause_job(int(job_id))
        return True

    def job_resume(self, job_id):
        self._queue.resume_job(int(job_id))
        return True

    def job_remove(self, ids):
        self._queue.remove([int(i) for i in (ids if isinstance(ids, list) else [ids])])
        return True

    def job_move(self, job_id, to_index):
        self._queue.move(int(job_id), int(to_index))
        return [j["id"] for j in self._queue.jobs()]

    def retry_errors(self):
        n = 0
        for j in self._queue.jobs():
            if j["status"] == "error":
                self._queue.retry(j["id"])
                n += 1
        return n

    def jobs(self):
        return {"jobs": self._queue.jobs(), "state": self._queue.state()}

    def job_text(self, job_id):
        """Text accepted so far (for the preview when a job is selected / resumed)."""
        segs = self._queue.segments(int(job_id))
        return [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segs]

    # ------------------------------------------------------------ history
    def history(self):
        return self._queue.jobs(history=True)

    def delete_history(self, ids=None):
        return self._queue.delete_history([int(i) for i in ids] if ids else None)

    def reexport(self, job_id, formats):
        return self._queue.reexport(int(job_id), list(formats or []))

    # ------------------------------------------------------------ speaker add-on (pyannote)
    def diar_status(self):
        from . import diarize
        return diarize.status()

    def diar_install(self):
        from . import diarize
        if getattr(self, "_diar_installing", False):
            return True
        self._diar_installing = True

        def run():
            try:
                diarize.install(lambda i, n, label, line: self._pump.push(
                    "addon", status="progress", step=i, steps=n, label=label, line=line))
                self._pump.push("addon", status="done", state=diarize.status())
            except Exception as e:  # noqa: BLE001
                log.error("add-on install failed: %s", e)
                self._pump.push("addon", status="error", detail=str(e)[-800:])
            finally:
                self._diar_installing = False
        threading.Thread(target=run, daemon=True).start()
        return True

    def diar_token(self, token):
        from . import diarize
        res = diarize.check_token(str(token or ""))
        res["saved"] = bool(diarize.token_get())
        return res

    # ------------------------------------------------------------ clipboard
    def clipboard_get(self):
        return tools.clipboard_get()

    def clipboard_set(self, text):
        return tools.clipboard_set(str(text or ""))

    def clipboard_link(self):
        """A YouTube link that has appeared on the clipboard since the last call (else None)."""
        text = (tools.clipboard_get() or "").strip()
        if not text or text == self._last_clip or len(text) > 4000:
            return None
        self._last_clip = text
        links = []
        for line in text.splitlines():
            p = sources.parse_input(line.strip())
            if p["kind"] == "youtube":
                links.append(line.strip())
        return "\n".join(links) if links else None

    # ------------------------------------------------------------ opening things
    def open_path(self, path):
        if path and Path(path).exists():
            _open(str(path))
            return True
        return False

    def open_folder(self, path=None):
        p = Path(path) if path else self._settings.output_dir()
        if p.is_file():
            if config.IS_WIN:
                subprocess.Popen(["explorer", "/select,", str(p)])
                return True
            p = p.parent
        p.mkdir(parents=True, exist_ok=True)
        _open(str(p))
        return True

    def open_url(self, url):
        if str(url).startswith(("https://", "http://")):
            webbrowser.open(url)
            return True
        return False

    # ------------------------------------------------------------ window (own title area and buttons)
    def win_drag(self):
        if self._chrome:
            self._chrome.drag()
        return True

    def win_resize(self, edge):
        if self._chrome:
            self._chrome.resize(str(edge))
        return True

    def win_max(self):
        return self._chrome.toggle_max() if self._chrome else False

    def win_min(self):
        if self._chrome:
            self._chrome.minimize()
        return True

    def win_close(self):
        self._w().destroy()
        return True

    def win_state(self):
        return {"custom": bool(self._chrome and self._chrome.ok), "max": bool(self._chrome and self._chrome.maximized())}

    def _shutdown(self):
        self._queue.close()


# api methods are wrapped so the page always gets data back, never a Python traceback
for _name in [n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))]:
    setattr(Api, _name, Api._safe(getattr(Api, _name)))


def _bind_drop(window, api: Api, pump: EventPump) -> None:
    """Files dropped on the window: pywebview gives their full paths (pywebviewFullPath)."""
    try:
        from webview.dom import DOMEventHandler

        def on_drop(e):
            files = (e.get("dataTransfer") or {}).get("files") or []
            paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
            if paths:
                pump.push("dropped", result=api.files_to_items(paths))

        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
        window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
    except Exception as e:  # noqa: BLE001
        log.warning("drag and drop not available: %s", e)


def _attach_chrome(window):
    """Removes the Windows title bar (the page draws its own). Returns the Chrome object (or None)."""
    if not config.IS_WIN:
        return None
    from .chrome import Chrome
    ico = config.UI_DIR / "logo.ico"
    ch = Chrome(window, str(ico) if ico.exists() else None)
    ch.install()
    return ch


def _window_geometry(settings) -> dict:
    g = settings.get("window") or {}
    out = {"width": 1500, "height": 920}
    try:
        w, h = int(g.get("w", 0)), int(g.get("h", 0))
        if w >= 1100 and h >= 680:
            out.update(width=w, height=h)
        if "x" in g and "y" in g and -50 < int(g["x"]) < 6000 and -50 < int(g["y"]) < 4000:
            out.update(x=int(g["x"]), y=int(g["y"]))
        if g.get("max"):
            out["maximized"] = True
    except (TypeError, ValueError):
        pass
    return out


def main() -> None:
    tools.setup_logging()
    log.info("%s %s starting (data: %s)", config.APP_NAME, config.VERSION, config.DATA_DIR)
    import webview
    from . import setup
    if config.IS_WIN and not _single_instance():
        return
    if config.IS_WIN:                                   # own taskbar button and icon (not Python's)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{config.AUTHOR}.{config.APP_NAME}")
        except Exception:  # noqa: BLE001
            pass
    settings = Settings()
    pump = EventPump()
    holder: dict = {}

    def open_main():
        api = Api(settings, pump)
        geo = _window_geometry(settings)
        window = webview.create_window(
            config.APP_NAME, url=str(config.UI_DIR / "index.html"), js_api=api, min_size=(1100, 680),
            background_color="#121418", text_select=True, **geo)
        api._window = window
        pump.window = window
        holder["api"] = api

        def before_show():
            api._chrome = _attach_chrome(window)

        def closing():
            try:
                if api._chrome:
                    pl = api._chrome.placement()
                    if pl:
                        settings.update({"window": pl})
            except Exception as e:  # noqa: BLE001
                log.debug("window placement not saved: %s", e)

        _on(window, ("before_show", "shown"), before_show)
        window.events.closing += closing
        window.events.loaded += lambda: _bind_drop(window, api, pump)
        return window

    need = [] if os.environ.get("BEESCRIBER_SKIP_SETUP") else setup.needed(settings)
    if need:
        log.info("first start setup: %s", [n["id"] for n in need])
        box: dict = {}

        def done():
            time.sleep(0.8)                                  # let "Ready!" show for a moment
            open_main()
            box["w"].destroy()

        def cancel():
            box["w"].destroy()                               # partial model files are resumed next time

        sapi = setup.SetupApi(settings, need, done, cancel)
        sw = webview.create_window(config.APP_NAME, url=str(config.UI_DIR / "setup.html"), js_api=sapi,
                                   width=560, height=500, resizable=False, background_color="#141619")
        sapi._window = sw
        box["w"] = sw

        def setup_chrome():
            sapi._chrome = _attach_chrome(sw)
        _on(sw, ("before_show", "shown"), setup_chrome)
    else:
        open_main()
    # private mode: no browser cache kept between starts, so an update always shows its new interface files
    # (with a kept cache WebView2 could serve the previous version's style.css / app.js). The app keeps nothing
    # in browser storage - settings and history are in its own files.
    shutil.rmtree(config.DATA_DIR / "webview", ignore_errors=True)        # cache folder of earlier versions
    webview.start(gui="edgechromium" if config.IS_WIN else None, private_mode=True,
                  debug=bool(os.environ.get("BEESCRIBER_DEBUG")))
    if "api" in holder:
        holder["api"]._shutdown()            # the running job keeps its progress and continues at the next start


_MUTEX = None


def _single_instance() -> bool:
    """Only one BeeScriber at a time (two would share the queue). A second start brings the first to the front."""
    global _MUTEX
    import ctypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX = k32.CreateMutexW(None, False, f"Local\\{config.APP_ID}-single-instance")
    if k32.GetLastError() != 183:                       # ERROR_ALREADY_EXISTS
        return True
    hwnd = u32.FindWindowW(None, config.APP_NAME)
    if hwnd:
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)                     # SW_RESTORE (only if minimised)
        u32.SetForegroundWindow(hwnd)
    log.info("already running - brought the open window to the front")
    return False


def _on(window, names, fn) -> None:
    """Subscribe fn to the first existing event of `names` (older pywebview has no before_show); runs once."""
    done = {"v": False}

    def once():
        if not done["v"]:
            done["v"] = True
            fn()
    for n in names:
        ev = getattr(window.events, n, None)
        if ev is not None:
            ev += once


if __name__ == "__main__":
    main()
