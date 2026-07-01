import sys
import psutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    title: str
    process_name: str
    pid: int


def _process_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "unknown"


if sys.platform == "win32":
    import win32gui
    import win32process

    def get_active_window() -> Optional[WindowInfo]:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid <= 0:
                return None
            return WindowInfo(title=title, process_name=_process_name(pid), pid=pid)
        except Exception as e:
            print(f"[MONITOR] error obteniendo ventana activa: {e}")
            return None

else:
    from ewmh import EWMH

    _ewmh = EWMH()

    def get_active_window() -> Optional[WindowInfo]:
        try:
            win = _ewmh.getActiveWindow()
            if not win:
                return None
            title = _ewmh.getWmName(win)
            if isinstance(title, bytes):
                title = title.decode("utf-8", "ignore")
            if not title:
                return None
            try:
                pid = _ewmh.getWmPid(win)
            except Exception:
                pid = None
            if not pid or pid <= 0:
                return None
            return WindowInfo(title=title, process_name=_process_name(pid), pid=pid)
        except Exception as e:
            print(f"[MONITOR] error obteniendo ventana activa: {e}")
            return None
