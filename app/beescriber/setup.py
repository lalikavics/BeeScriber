# -*- coding: utf-8 -*-
"""First start: a small window that downloads the missing components with one progress bar - yt-dlp, FFmpeg, Deno,
the NVIDIA CUDA libraries (only with an NVIDIA card), the Whisper model and, if it was chosen in the installer, the
speaker recognition add-on. When everything is there, the main window opens."""
from __future__ import annotations

import json
import logging
import threading
import traceback

from . import config, diarize, models, tools

log = logging.getLogger(config.APP_ID)

TOOL_MB = {"yt-dlp": 18, "ffmpeg": 95, "deno": 45}
LABELS = {"yt-dlp": "yt-dlp", "ffmpeg": "FFmpeg", "deno": "Deno"}


CUDA_MB = 1250


def install_options() -> dict:
    """Choices made in the installer (install.json next to the program), e.g. {"speakers": true}."""
    try:
        return json.loads((config.ROOT / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def needed(settings) -> list[dict]:
    out = [{"id": n, "label": LABELS[n], "mb": TOOL_MB[n]} for n in tools.missing()]
    if tools.cuda_libs_needed():
        out.append({"id": "cuda", "label": "NVIDIA CUDA (cuBLAS, cuDNN)", "mb": CUDA_MB})
    model = settings.get("custom_model") or settings.get("model")
    if not settings.get("custom_model") and not models.local_path(model):
        out.append({"id": "model", "label": f"Whisper {model}", "mb": models.APPROX_MB.get(model, 1600),
                    "model": model})
    if install_options().get("speakers") and diarize.can_install() and not diarize.installed():
        out.append({"id": "speakers", "label": "pyannote (speakers)", "mb": diarize.TORCH_MB + diarize.PYANNOTE_MB})
    return out


class SetupApi:
    def __init__(self, settings, items: list[dict], on_done, on_cancel):
        self._settings = settings
        self._items = items
        self._on_done = on_done
        self._on_cancel = on_cancel
        self._window = None
        self._chrome = None
        self._cancel = False
        self._started = False
        self.installed_speakers = False

    def _push(self, data: dict) -> None:
        if self._window:
            try:
                self._window.evaluate_js(f"window.setupEvent && setupEvent({json.dumps(data, ensure_ascii=False)})")
            except Exception:  # noqa: BLE001
                pass

    def info(self):
        return {"app": config.APP_NAME, "version": config.VERSION, "lang": self._settings.get("ui_lang") or "en",
                "items": self._items}

    def start(self):
        if self._started:
            return True
        self._started = True
        self._cancel = False
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def win_drag(self):
        if self._chrome:
            self._chrome.drag()
        return True

    def win_min(self):
        if self._chrome:
            self._chrome.minimize()
        return True

    def cancel(self):
        self._cancel = True
        threading.Thread(target=self._on_cancel, daemon=True).start()
        return True

    def _run(self) -> None:
        sizes = {it["id"]: it["mb"] * 1e6 for it in self._items}
        done_bytes = {it["id"]: 0.0 for it in self._items}

        def report(cur: dict, got: float, total: float) -> None:
            if total:
                sizes[cur["id"]] = total
            done_bytes[cur["id"]] = got
            all_total = sum(sizes.values()) or 1
            self._push({"type": "progress", "id": cur["id"], "label": cur["label"],
                        "pct": min(100.0, 100.0 * sum(done_bytes.values()) / all_total),
                        "got": got, "total": total or sizes[cur["id"]]})

        try:
            for it in self._items:
                if self._cancel:
                    return
                self._push({"type": "item", "id": it["id"], "label": it["label"]})
                if it["id"] == "model":
                    models.download(it["model"], lambda d, t, _f, c=it: report(c, d, t), lambda: self._cancel)
                elif it["id"] == "cuda":
                    tools.pip_install(tools.CUDA_PACKAGES, lambda g, c=it: report(c, min(g, sizes[c["id"]]), 0),
                                      lambda: self._cancel)
                    tools.add_nvidia_dll_dirs()
                elif it["id"] == "speakers":
                    try:
                        diarize.install(cancelled=lambda: self._cancel,
                                        bytes_progress=lambda g, c=it: report(c, min(g, sizes[c["id"]]), 0))
                    except RuntimeError:
                        if self._cancel:
                            return
                        raise
                    self.installed_speakers = True
                else:
                    tools.install(it["id"], lambda g, t, c=it: report(c, g, t), lambda: self._cancel)
                report(it, sizes[it["id"]], sizes[it["id"]])
            self._push({"type": "done"})
            self._on_done()
        except (models.Cancelled, tools.Cancelled):
            return
        except Exception as e:  # noqa: BLE001
            log.error("setup failed: %s", traceback.format_exc())
            self._started = False
            self._push({"type": "error", "detail": str(e)[-600:]})
