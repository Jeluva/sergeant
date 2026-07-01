import sys
import time
import psutil
import threading
from ui.countdown import show_countdown, dismiss_countdown
from ui.toast import show_warning_toast, dismiss_toast
from db import log_event
from datetime import datetime
from config import BROWSER_PROCESSES

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32gui
    import win32process
    import win32api
    import win32con
    import winsound

    def _beep():
        try:
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_NODEFAULT)
        except Exception:
            try:
                winsound.Beep(880, 200)
                winsound.Beep(660, 200)
            except Exception:
                pass

    def _get_foreground():
        return win32gui.GetForegroundWindow()

    def _get_window_text(h):
        return win32gui.GetWindowText(h) if h else ""

    def _find_window_for_pid(pid: int):
        result = [None]
        def _cb(h, _):
            if not win32gui.IsWindowVisible(h):
                return True
            try:
                _, wpid = win32process.GetWindowThreadProcessId(h)
            except Exception:
                return True
            if wpid == pid:
                result[0] = h
                return False
            return True
        win32gui.EnumWindows(_cb, None)
        return result[0]

    def _focus_window(h):
        try:
            win32gui.SetForegroundWindow(h)
        except Exception:
            pass

    def _show_window(h):
        try:
            win32gui.ShowWindow(h, 5)  # SW_SHOW
        except Exception:
            pass

    def _send_ctrl_w():
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord('W'), 0, 0, 0)
        win32api.keybd_event(ord('W'), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

else:
    from ewmh import EWMH
    from pynput.keyboard import Controller, Key

    _ewmh = EWMH()
    _kb = Controller()

    def _beep():
        print("\a", end="", flush=True)

    def _get_foreground():
        try:
            return _ewmh.getActiveWindow()
        except Exception:
            return None

    def _get_window_text(h):
        if not h:
            return ""
        try:
            name = _ewmh.getWmName(h)
            return name.decode("utf-8", "ignore") if isinstance(name, bytes) else (name or "")
        except Exception:
            return ""

    def _find_window_for_pid(pid: int):
        try:
            for w in _ewmh.getClientList():
                try:
                    if _ewmh.getWmPid(w) == pid:
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _focus_window(h):
        try:
            _ewmh.setActiveWindow(h)
            _ewmh.display.flush()
        except Exception:
            pass

    def _show_window(h):
        pass  # setActiveWindow ya trae la ventana al frente en X11

    def _send_ctrl_w():
        _kb.press(Key.ctrl)
        _kb.press('w')
        _kb.release('w')
        _kb.release(Key.ctrl)


def _alert_sound():
    threading.Thread(target=_beep, daemon=True).start()


def fmt_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def warn_before_close(pid: int, title: str, process_name: str, warn_seconds: int = 10, on_close=None):
    """Muestra toast de aviso. Llama on_close() cuando expira el countdown."""
    _alert_sound()
    short = title[:35]
    show_warning_toast(
        key=f"warn_{pid}",
        title=title,
        app_name=short,
        seconds=warn_seconds,
        on_expire=on_close,
    )
    log_event(fmt_now(), "WARNED", f"pid={pid} title={title} secs={warn_seconds}")
    print(f"[ENFORCER] aviso: cerrando '{short}' en {warn_seconds}s")


def close_window(pid: int, title: str, process_name: str):
    """
    Cierra browsers con Ctrl+W (solo la pestaña activa).
    Otros procesos: terminate().
    """
    dismiss_toast(f"warn_{pid}")
    time.sleep(0.15)  # dar tiempo al thread del toast para terminar limpio

    if process_name.lower() in BROWSER_PROCESSES:
        _close_browser_tab(pid, title)
    else:
        _terminate_process(pid, title)


def cancel_warning(pid: int):
    """Cancela el aviso activo sin cerrar nada (usuario volvió a ser productivo)."""
    dismiss_toast(f"warn_{pid}")
    print(f"[ENFORCER] aviso cancelado — usuario retomó el trabajo (pid {pid})")


def _close_browser_tab(pid: int, title: str):
    """Manda Ctrl+W al browser para cerrar solo la pestaña activa.
    Verifica que el browser sea realmente el foreground antes de enviar Ctrl+W."""
    try:
        hwnd = _find_window_for_pid(pid)
        if not hwnd:
            print(f"[ENFORCER] ventana no encontrada para pid {pid}, skip Ctrl+W")
            return

        _focus_window(hwnd)
        time.sleep(0.3)  # esperar foco

        # Verificar que el foreground sea realmente el browser antes de enviar keys
        fg = _get_foreground()
        if fg != hwnd:
            # Intentar de nuevo con foco forzado
            _show_window(hwnd)
            _focus_window(hwnd)
            time.sleep(0.2)
            fg = _get_foreground()

        if fg == hwnd:
            _send_ctrl_w()
            log_event(fmt_now(), "TAB_CLOSED", f"pid={pid} title={title}")
            print(f"[ENFORCER] pestaña cerrada (Ctrl+W): {title}")
        else:
            # Fallback: terminar proceso si no se puede obtener foco
            fg_title = _get_window_text(fg)
            print(f"[ENFORCER] no se pudo enfocar el browser (fg='{fg_title}'), terminando proceso")
            _terminate_process(pid, title)
    except Exception as e:
        print(f"[ENFORCER] no se pudo cerrar pestaña: {e}")


def _terminate_process(pid: int, title: str):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        log_event(fmt_now(), "CLOSED", f"pid={pid} title={title}")
        print(f"[ENFORCER] proceso cerrado: {title} (pid {pid})")
    except Exception as e:
        print(f"[ENFORCER] no se pudo cerrar {title}: {e}")


def trigger_countdown(seconds: int = 60, distraction: str = ""):
    log_event(fmt_now(), "COUNTDOWN_START", f"seconds={seconds}")
    show_countdown(seconds=seconds, distraction=distraction,
                   on_close_cb=lambda: log_event(fmt_now(), "COUNTDOWN_END", ""))
    print(f"[ENFORCER] countdown iniciado ({seconds}s)")


def dismiss(warned_pid: int = None, countdown_was_active: bool = False):
    """Cancela countdown y toast activos."""
    dismiss_countdown()
    if warned_pid is not None:
        dismiss_toast(f"warn_{warned_pid}")
    if countdown_was_active:
        log_event(fmt_now(), "COUNTDOWN_DISMISSED", "")
