import win32gui
import win32process
import psutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    title: str
    process_name: str
    pid: int


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
        try:
            proc = psutil.Process(pid)
            process_name = proc.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"
        return WindowInfo(title=title, process_name=process_name, pid=pid)
    except Exception as e:
        print(f"[MONITOR] error obteniendo ventana activa: {e}")
        return None


