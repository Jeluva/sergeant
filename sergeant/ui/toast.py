import tkinter as tk
import threading
import traceback
import ctypes

_active = {}   # key → dismissed_flag list
_lock = threading.Lock()
_root = None   # dashboard root (set_root() called from dashboard.py)


def set_root(root):
    global _root
    _root = root


def _primary_screen_size():
    try:
        u32 = ctypes.windll.user32
        return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
    except Exception:
        return None, None


def show_warning_toast(key: str, title: str, app_name: str, seconds: int, on_expire=None):
    """Toast esquina inferior derecha con countdown. Usa Toplevel en el thread del dashboard."""
    with _lock:
        if key in _active:
            return

    dismissed = [False]
    with _lock:
        _active[key] = dismissed

    if _root is None:
        # Fallback sin UI — solo disparar on_expire tras delay
        def _fallback():
            threading.Event().wait(seconds)
            if not dismissed[0]:
                dismissed[0] = True
                if on_expire:
                    try:
                        on_expire()
                    except Exception:
                        print(f"[TOAST] error en on_expire (fallback):\n{traceback.format_exc()}")
                with _lock:
                    _active.pop(key, None)
        threading.Thread(target=_fallback, daemon=True).start()
        return

    def _create():
        if dismissed[0]:
            with _lock:
                _active.pop(key, None)
            return

        try:
            win = tk.Toplevel(_root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="#1a0000")

            W, H = 360, 90
            SW, SH = _primary_screen_size()
            if SW is None:
                SW = _root.winfo_screenwidth()
                SH = _root.winfo_screenheight()
            win.geometry(f"{W}x{H}+{SW - W - 16}+{SH - H - 60}")

            tk.Label(win, text="⚠  SERGEANT — INFRACCIÓN", font=("Courier New", 9, "bold"),
                     fg="#ff3333", bg="#1a0000").pack(anchor="w", padx=10, pady=(8, 2))
            tk.Label(win, text=f"cerrando: {app_name[:35]}",
                     font=("Courier New", 9), fg="#ff8800", bg="#1a0000").pack(anchor="w", padx=10)

            count_var = tk.StringVar(value=f"en {seconds}s...")
            tk.Label(win, textvariable=count_var,
                     font=("Courier New", 9), fg="#555555", bg="#1a0000").pack(anchor="w", padx=10)

            remaining = [seconds]

            def tick():
                if dismissed[0]:
                    with _lock:
                        _active.pop(key, None)
                    try:
                        win.destroy()
                    except Exception:
                        pass
                    return

                if remaining[0] <= 0:
                    with _lock:
                        _active.pop(key, None)
                    try:
                        win.destroy()
                    except Exception:
                        pass
                    if on_expire:
                        try:
                            on_expire()
                        except Exception:
                            print(f"[TOAST] error en on_expire:\n{traceback.format_exc()}")
                    return

                count_var.set(f"en {remaining[0]}s...")
                remaining[0] -= 1
                _root.after(1000, tick)

            tick()

        except Exception:
            print(f"[TOAST] error creando toast:\n{traceback.format_exc()}")
            with _lock:
                _active.pop(key, None)

    _root.after(0, _create)


def dismiss_toast(key: str):
    """Señala al toast que debe cerrarse. La destrucción ocurre en el thread del dashboard."""
    with _lock:
        dismissed = _active.pop(key, None)
        if dismissed:
            dismissed[0] = True
