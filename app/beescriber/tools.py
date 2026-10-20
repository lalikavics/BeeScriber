# -*- coding: utf-8 -*-
"""External programs (yt-dlp, ffmpeg, deno): locating, running without console windows, downloading, updating."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

from . import config
from .config import BIN_DIR, EXE, IS_WIN, TOOLS_DIR

log = logging.getLogger(config.APP_ID)

DOWNLOADS = {
    "yt-dlp": ["https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"],
    "deno": ["https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"],
    "ffmpeg": ["https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
               "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"],
}
ZIP_MEMBER = {"deno": "deno.exe", "ffmpeg": "/bin/ffmpeg.exe"}
REQUIRED = ["yt-dlp", "ffmpeg", "deno"]


def tool(name: str) -> str | None:
    p = BIN_DIR / (name + EXE)
    if p.exists():
        return str(p)
    return shutil.which(name)


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = str(BIN_DIR) + os.pathsep + e.get("PATH", "")
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def no_window() -> dict:
    """subprocess kwargs: never flash a console window from the GUI app."""
    if IS_WIN:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": si}
    return {}


def run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env(), timeout=timeout, **no_window())


def version(name: str) -> str | None:
    exe = tool(name)
    if not exe:
        return None
    try:
        r = run([exe, "-version" if name == "ffmpeg" else "--version"], timeout=30)
        line = ((r.stdout or r.stderr or "").strip().splitlines() or ["?"])[0]
        if name == "ffmpeg":
            parts = line.split()
            return parts[2] if len(parts) > 2 else line
        return line.replace("deno ", "").split(" (")[0]
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def missing() -> list[str]:
    return [n for n in REQUIRED if not tool(n)]


class Cancelled(Exception):
    pass


def _download(url: str, dest: Path, progress=None, cancelled=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": f"{config.APP_NAME}/{config.VERSION}"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0.0
        if progress:
            progress(0, total)
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
                progress(got, total)
    part.replace(dest)


def install(name: str, progress=None, cancelled=None) -> None:
    """Download one tool into BIN_DIR (Windows builds)."""
    if not IS_WIN:
        raise RuntimeError(f"{name}: install it with your package manager")
    dest = BIN_DIR / (name + EXE)
    last_err: Exception | None = None
    for url in DOWNLOADS[name]:
        try:
            if name in ZIP_MEMBER:
                z = TOOLS_DIR / f"{name}.zip"
                _download(url, z, progress, cancelled)
                ok = False
                with zipfile.ZipFile(z) as zf:
                    for n in zf.namelist():
                        if n.lower().endswith(ZIP_MEMBER[name]):
                            with zf.open(n) as src, open(dest, "wb") as out:
                                shutil.copyfileobj(src, out)
                            ok = True
                            break
                z.unlink(missing_ok=True)
                if not ok:
                    raise RuntimeError(f"{ZIP_MEMBER[name]} not found in archive")
            else:
                _download(url, dest, progress, cancelled)
            return
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("download failed %s: %s", url, e)
    raise RuntimeError(f"{name}: download failed ({last_err})")


def update_ytdlp() -> str:
    exe = tool("yt-dlp")
    if not exe:
        install("yt-dlp")
        return version("yt-dlp") or "?"
    r = run([exe, "-U"], timeout=300)
    out = (r.stdout + r.stderr).strip().splitlines()
    log.info("yt-dlp -U: %s", " | ".join(out[-3:]))
    return version("yt-dlp") or "?"


def add_nvidia_dll_dirs() -> None:
    """pip's nvidia-cublas/cudnn packages keep their DLLs in site-packages/nvidia/*/bin."""
    if not IS_WIN:
        return
    import site
    import sys
    dirs: list[str] = []
    roots = list(dict.fromkeys(list(site.getsitepackages()) + [p for p in sys.path if p.endswith("site-packages")]))
    for sp in roots:                                       # venv (development) or the bundled Python (installer)
        base = Path(sp) / "nvidia"
        if base.exists():
            dirs += [str(p) for p in base.glob("*/bin") if str(p) not in dirs]
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:  # noqa: BLE001
            pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


def gpu_info() -> dict | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        r = run([exe, "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=10)
        parts = [p.strip() for p in r.stdout.strip().splitlines()[0].split(",")]
        return {"name": parts[0], "used_mb": int(parts[1]), "total_mb": int(parts[2])}
    except Exception:  # noqa: BLE001
        return None


def setup_logging() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger(config.APP_ID)
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    from logging.handlers import RotatingFileHandler
    h = RotatingFileHandler(config.LOG_PATH, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(h)


# ---------------------------------------------------------------- clipboard (the page cannot use it directly)
_fallback_clip = {"text": ""}          # non-Windows / tests


def clipboard_get() -> str:
    if not IS_WIN:
        return _fallback_clip["text"]
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetClipboardData.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    for _ in range(5):                                    # another program may hold the clipboard briefly
        if u32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return ""
    try:
        h = u32.GetClipboardData(13)                      # CF_UNICODETEXT
        if not h:
            return ""
        p = k32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def clipboard_set(text: str) -> bool:
    if not IS_WIN:
        _fallback_clip["text"] = text
        return True
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = (text or "").encode("utf-16-le") + b"\x00\x00"
    for _ in range(5):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(data))            # GMEM_MOVEABLE
        p = k32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k32.GlobalUnlock(h)
        return bool(u32.SetClipboardData(13, h))
    finally:
        u32.CloseClipboard()


# ---------------------------------------------------------------- load meters (GPU, VRAM, CPU)
_cpu_last: list = []


def _cpu_times() -> tuple[int, int] | None:
    """(idle, total) since boot."""
    if IS_WIN:
        import ctypes
        from ctypes import wintypes
        idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            return None
        f = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime  # noqa: E731
        return f(idle), f(kern) + f(user)                   # kernel time includes idle time
    try:
        vals = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        return vals[3] + (vals[4] if len(vals) > 4 else 0), sum(vals)
    except (OSError, ValueError):
        return None


def usage() -> dict:
    """{"gpu": %, "vram_used": MB, "vram_total": MB, "cpu": %} - values are None when unknown."""
    out = {"gpu": None, "vram_used": None, "vram_total": None, "cpu": None}
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            r = run([exe, "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                    timeout=5)
            g = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
            out.update(gpu=int(g[0]), vram_used=int(g[1]), vram_total=int(g[2]))
        except Exception:  # noqa: BLE001
            pass
    now = _cpu_times()
    if now:
        if _cpu_last:
            di, dt = now[0] - _cpu_last[0][0], now[1] - _cpu_last[0][1]
            if dt > 0:
                out["cpu"] = max(0, min(100, round(100 * (1 - di / dt))))
            _cpu_last[0] = now
        else:
            _cpu_last.append(now)
    return out


# ---------------------------------------------------------------- pip (CUDA libraries, speaker add-on)
class PipError(RuntimeError):
    pass


def pip_python() -> str:
    """The console python.exe next to the running interpreter (pip does not work from pythonw.exe)."""
    import sys
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        alt = exe.with_name("python.exe")
        if alt.exists():
            return str(alt)
    return str(exe)


_SIZE_RE = None


def _size(text: str) -> float:
    global _SIZE_RE
    import re
    _SIZE_RE = _SIZE_RE or re.compile(r"\(([\d.]+)\s*(kB|MB|GB|bytes)\)")
    m = _SIZE_RE.search(text)
    if not m:
        return 0.0
    return float(m.group(1)) * {"bytes": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9}[m.group(2)]


def pip_install(args: list[str], progress=None, cancelled=None, on_line=None) -> None:
    """pip install <args> into this Python. progress(got_bytes) is called while the wheels download."""
    import sys
    cmd = [pip_python(), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
           "--progress-bar", "raw"]
    if list(Path(sys.executable).parent.glob("python3*._pth")):   # the installer's embedded Python: pip's isolated
        cmd.append("--no-build-isolation")                         # build env does not work there (see build.ps1)
    cmd += args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", env=env(), **no_window())
    finished = cur = pending = 0.0
    tail: list[str] = []
    assert p.stdout is not None
    for line in p.stdout:
        line = line.strip()
        if not line:
            continue
        if cancelled and cancelled():
            p.terminate()
            raise Cancelled()
        if line.startswith("Progress ") and " of " in line:
            try:
                a, b = line[9:].split(" of ")
                cur, pending = float(a), float(b)
            except ValueError:
                continue
        else:
            tail = (tail + [line])[-30:]
            if line.startswith(("Downloading ", "Installing ", "Successfully")) and ".metadata" not in line:
                finished += max(cur, pending)
                cur, pending = 0.0, (_size(line) if line.startswith("Downloading ") else 0.0)
                if on_line:
                    on_line(line[:160])
        if progress:
            progress(finished + cur)
    if p.wait() != 0:
        raise PipError("pip failed:\n" + "\n".join(tail[-12:]))
    if progress:
        progress(finished + pending)
    import importlib
    importlib.invalidate_caches()


CUDA_PACKAGES = ["nvidia-cublas-cu12==12.9.2.10", "nvidia-cudnn-cu12==9.27.0.42"]   # as tested with CTranslate2 4.8


def cuda_libs_needed() -> bool:
    """NVIDIA card present, but cuBLAS / cuDNN (needed by CTranslate2 on the GPU) are not installed yet."""
    if not IS_WIN or not shutil.which("nvidia-smi"):
        return False
    import importlib.util
    try:
        return any(importlib.util.find_spec(m) is None for m in ("nvidia.cublas", "nvidia.cudnn"))
    except (ImportError, ValueError):
        return True
