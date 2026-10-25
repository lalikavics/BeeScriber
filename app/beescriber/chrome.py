# -*- coding: utf-8 -*-
"""Window without the Windows title bar (Windows only). The page draws the title area and the window buttons
(like ArtFlawless Studio); this module removes the system frame and moves / resizes / maximises on request.

How: the window keeps its normal resizable style (so Aero Snap, Win+arrows, the taskbar and the minimise
animation keep working), but a subclassed window procedure answers WM_NCCALCSIZE with "no frame", so the whole
window is page. Dragging and edge resizing start the normal Windows move / size loops (WM_NCLBUTTONDOWN)."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from . import config

log = logging.getLogger(config.APP_ID)

WM_NCCALCSIZE = 0x0083
WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2
HT_EDGES = {"l": 10, "r": 11, "t": 12, "tl": 13, "tr": 14, "b": 15, "bl": 16, "br": 17}
SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE = 3, 6, 9
SWP_FLAGS = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010     # FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE

LRESULT = ctypes.c_ssize_t
SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                  ctypes.c_size_t, ctypes.c_size_t)


class MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


class Chrome:
    def __init__(self, window, icon: str | None = None):
        self.window = window
        self.icon = icon
        self.hwnd = None
        self.ok = False
        self._proc = None                      # keep the callback alive

    # ------------------------------------------------------------ setup (runs on the window's UI thread)
    def _on_ui(self, fn) -> None:
        form = self.window.native
        try:
            from System import Action
            if form.InvokeRequired:
                form.BeginInvoke(Action(fn))
                return
        except Exception:  # noqa: BLE001
            pass
        fn()

    def install(self) -> None:
        if not config.IS_WIN:
            return
        self._on_ui(self._install)

    def _install(self) -> None:
        try:
            u32, cc, dwm = ctypes.windll.user32, ctypes.windll.comctl32, ctypes.windll.dwmapi
            cc.SetWindowSubclass.argtypes = [wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t]
            cc.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            cc.DefSubclassProc.restype = LRESULT
            u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_uint]
            if self.icon:
                try:
                    from System.Drawing import Icon
                    self.window.native.Icon = Icon(self.icon)
                except Exception as e:  # noqa: BLE001
                    log.debug("window icon: %s", e)
            self.hwnd = wintypes.HWND(int(self.window.native.Handle.ToInt64()))
            self._proc = SUBCLASSPROC(self._wndproc)
            if not cc.SetWindowSubclass(self.hwnd, self._proc, 0xBEE5, 0):
                raise OSError("SetWindowSubclass failed")
            one = ctypes.c_int(1)
            for attr in (20, 19):                                  # dark mode for the system parts
                dwm.DwmSetWindowAttribute(self.hwnd, attr, ctypes.byref(one), 4)
            m = MARGINS(0, 0, 0, 1)                                # keeps the drop shadow
            dwm.DwmExtendFrameIntoClientArea(self.hwnd, ctypes.byref(m))
            u32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, SWP_FLAGS)
            self.ok = True
            log.info("custom window frame installed")
        except Exception as e:  # noqa: BLE001
            log.warning("custom window frame not available: %s", e)

    def _wndproc(self, hwnd, msg, wp, lp, _uid, _ref):
        try:
            if msg == WM_NCCALCSIZE and wp:
                if ctypes.windll.user32.IsZoomed(hwnd):            # maximised: exactly the monitor's work area
                    params = ctypes.cast(lp, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
                    u32 = ctypes.windll.user32
                    u32.MonitorFromWindow.restype = ctypes.c_void_p
                    mon = u32.MonitorFromWindow(hwnd, 2)
                    mi = MONITORINFO()
                    mi.cbSize = ctypes.sizeof(MONITORINFO)
                    if u32.GetMonitorInfoW(ctypes.c_void_p(mon), ctypes.byref(mi)):
                        params.rgrc[0] = mi.rcWork
                return 0                                           # no system frame at all
        except Exception:  # noqa: BLE001
            pass
        return ctypes.windll.comctl32.DefSubclassProc(hwnd, msg, wp, lp)

    # ------------------------------------------------------------ actions from the page
    def _nc_drag(self, ht: int) -> None:
        def go():
            u32 = ctypes.windll.user32
            u32.ReleaseCapture()
            u32.SendMessageW(self.hwnd, WM_NCLBUTTONDOWN, ht, 0)
        self._on_ui(go)

    def drag(self) -> None:
        if self.ok:
            self._nc_drag(HTCAPTION)

    def resize(self, edge: str) -> None:
        if self.ok and edge in HT_EDGES and not self.maximized():
            self._nc_drag(HT_EDGES[edge])

    def maximized(self) -> bool:
        return bool(self.hwnd and ctypes.windll.user32.IsZoomed(self.hwnd))

    def toggle_max(self) -> bool:
        if not self.hwnd:
            return False
        want_max = not self.maximized()
        self._on_ui(lambda: ctypes.windll.user32.ShowWindow(self.hwnd, SW_MAXIMIZE if want_max else SW_RESTORE))
        return want_max

    def minimize(self) -> None:
        if self.hwnd:
            self._on_ui(lambda: ctypes.windll.user32.ShowWindow(self.hwnd, SW_MINIMIZE))

    def placement(self) -> dict | None:
        """Normal (not maximised) position and size, for the next start."""
        if not self.hwnd:
            return None

        class WINDOWPLACEMENT(ctypes.Structure):
            _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                        ("ptMin", wintypes.POINT), ("ptMax", wintypes.POINT), ("rc", wintypes.RECT)]
        wp = WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(WINDOWPLACEMENT)
        if not ctypes.windll.user32.GetWindowPlacement(self.hwnd, ctypes.byref(wp)):
            return None
        r = wp.rc
        try:                                                   # pywebview takes sizes in 96-dpi units
            scale = ctypes.windll.user32.GetDpiForWindow(self.hwnd) / 96.0 or 1.0
        except Exception:  # noqa: BLE001
            scale = 1.0
        return {"x": round(r.left / scale), "y": round(r.top / scale), "w": round((r.right - r.left) / scale),
                "h": round((r.bottom - r.top) / scale), "max": self.maximized()}
