import sys
import tkinter as tk
import threading
import random

if sys.platform == "win32":
    import winsound

    def _beep(freq, dur_ms):
        winsound.Beep(freq, dur_ms)
else:
    def _beep(freq, dur_ms):
        print("\a", end="", flush=True)

_root = None   # dashboard root (set_root() called from dashboard.py)
_countdown_window  = None
_countdown_running = False
_countdown_paused  = False

FAKE_FILES = [
    r"C:\Windows\System32\ntoskrnl.exe",
    r"C:\Windows\System32\hal.dll",
    r"C:\Windows\System32\winlogon.exe",
    r"C:\Windows\System32\lsass.exe",
    r"C:\Windows\System32\svchost.exe",
    r"C:\Windows\System32\csrss.exe",
    r"C:\Windows\System32\kernel32.dll",
    r"C:\Windows\System32\user32.dll",
    r"C:\Windows\System32\advapi32.dll",
    r"C:\Windows\System32\msvcrt.dll",
]

BOOT_LINES = [
    "> SERGEANT v1.0 -- INFRACTION MODULE",
    "> scanning active processes...",
    "> distraction confirmed: {distraction}",
    "> warning threshold exceeded.",
    "> locating system root...",
    "> C:\\Windows\\System32 found.",
    "> indexing critical files...",
]


def set_root(root):
    global _root
    _root = root


def _create_countdown(seconds: int, distraction: str, on_close_cb=None):
    """Crea la ventana countdown como Toplevel en el thread del dashboard."""
    global _countdown_window, _countdown_running

    print("[COUNTDOWN] _create_countdown iniciado")
    try:
        import ctypes
        SW = ctypes.windll.user32.GetSystemMetrics(0)
        SH = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        SW, SH = 1920, 1080

    try:
        win = tk.Toplevel(_root)
    except Exception as e:
        print(f"[COUNTDOWN] ERROR creando Toplevel: {e}")
        import traceback; traceback.print_exc()
        return
    print(f"[COUNTDOWN] Toplevel creado: {win}")
    _countdown_window = win
    win.title("SERGEANT -- SYSTEM THREAT")
    win.configure(bg="black")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", lambda: None)  # no cerrar manualmente

    W, H = 720, 560
    win.geometry(f"{W}x{H}+{(SW-W)//2}+{(SH-H)//2}")
    win.after(100, lambda: (win.lift(), win.focus_force()))

    tk.Label(win, text="SERGEANT  //  CRITICAL INFRACTION",
             font=("Courier New", 12, "bold"), fg="#ff2222", bg="black").pack(pady=(18, 2))
    tk.Label(win, text="-" * 70, fg="#330000", bg="black",
             font=("Courier New", 9)).pack()

    log_text = tk.Text(win, height=9, bg="black", fg="#cc0000",
                       font=("Courier New", 10), relief=tk.FLAT, bd=0,
                       state=tk.DISABLED, cursor="arrow")
    log_text.pack(fill=tk.X, padx=24, pady=(10, 0))

    tk.Label(win, text="-" * 70, fg="#330000", bg="black",
             font=("Courier New", 9)).pack(pady=(8, 0))

    tk.Label(win, text="C:\\Windows\\System32  sera eliminado en:",
             font=("Courier New", 11), fg="#ff6600", bg="black").pack(pady=(10, 0))

    timer_var = tk.StringVar(value=f"{seconds//60:02d}:{seconds%60:02d}")
    timer_lbl = tk.Label(win, textvariable=timer_var,
                         font=("Courier New", 72, "bold"), fg="#ff0000", bg="black")
    timer_lbl.pack(pady=(0, 2))

    status_var = tk.StringVar(value="[ EN CURSO ]")
    status_lbl = tk.Label(win, textvariable=status_var,
                           font=("Courier New", 10, "bold"), fg="#ff4400", bg="black")
    status_lbl.pack(pady=(0, 4))

    bar_frame = tk.Frame(win, bg="black")
    bar_frame.pack(fill=tk.X, padx=40, pady=(0, 4))
    bar_canvas = tk.Canvas(bar_frame, height=8, bg="#1a0000",
                           highlightthickness=0, relief=tk.FLAT)
    bar_canvas.pack(fill=tk.X)
    bar_fill = bar_canvas.create_rectangle(0, 0, 0, 8, fill="#ff0000", outline="")

    tk.Label(win, text="vos lo instalaste.  vos sabias lo que hacia.",
             font=("Courier New", 9, "italic"), fg="#330000", bg="black").pack(pady=(2, 0))

    remaining = [seconds]
    total = seconds

    def _append_log(line):
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, line + "\n")
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)

    def _type_line(line, delay_ms=0):
        _root.after(delay_ms, lambda: _append_log(line))

    dist_str = distraction[:40] if distraction else "unknown"
    boot = [l.replace("{distraction}", dist_str) for l in BOOT_LINES]
    for i, line in enumerate(boot):
        _type_line(line, delay_ms=i * 280)

    files_delay = len(boot) * 280 + 100
    for i, f in enumerate(FAKE_FILES[:6]):
        size = random.randint(128, 4096)
        _type_line(f"  {f}  [{size} KB]", delay_ms=files_delay + i * 120)

    def _expire_sequence():
        timer_var.set("00:00")
        timer_lbl.config(fg="#ff0000")
        status_var.set("[ EJECUTANDO ]")
        status_lbl.config(fg="#ff0000")
        bar_canvas.update_idletasks()
        w = bar_canvas.winfo_width()
        bar_canvas.coords(bar_fill, 0, 0, w, 8)
        _append_log("")
        _append_log("> rm -rf C:\\Windows\\System32\\*")
        _root.after(800,  lambda: _append_log("> eliminando ntoskrnl.exe... OK"))
        _root.after(1400, lambda: _append_log("> eliminando lsass.exe....... OK"))
        _root.after(2000, lambda: _append_log("> eliminando kernel32.dll.... OK"))
        _root.after(2600, lambda: _append_log("> [done] sistema comprometido."))
        _root.after(3800, lambda: (win.destroy(), on_close_cb() if on_close_cb else None))

    def _abort_sequence():
        timer_lbl.config(fg="#ff6600")
        status_var.set("[ PROCESO INTERRUMPIDO ]")
        status_lbl.config(fg="#ff6600")
        _append_log("")
        _append_log("> PROCESO INTERRUMPIDO.")
        _append_log("> razon: usuario retomo actividad.")
        _root.after(700, _show_aborted)

    def _show_aborted():
        timer_var.set("ABORTADO")
        timer_lbl.config(fg="#00ff41", font=("Courier New", 48, "bold"))
        _root.after(1800, lambda: (win.destroy(), on_close_cb() if on_close_cb else None))

    def tick():
        if not _countdown_running:
            _abort_sequence()
            return

        if _countdown_paused:
            m, s = divmod(remaining[0], 60)
            timer_var.set(f"{m:02d}:{s:02d}")
            timer_lbl.config(fg="#664400")
            status_var.set("[ PAUSADO  --  retomaste el trabajo ]")
            status_lbl.config(fg="#886600")
            _root.after(300, tick)
            return

        status_var.set("[ EN CURSO ]")
        status_lbl.config(fg="#ff4400")

        if remaining[0] <= 0:
            _expire_sequence()
            return

        m, s = divmod(remaining[0], 60)
        timer_var.set(f"{m:02d}:{s:02d}")

        if remaining[0] <= 5:
            threading.Thread(
                target=lambda: _beep(880 + (5 - remaining[0]) * 40, 80),
                daemon=True
            ).start()

        if remaining[0] <= 10:
            color = "#ff0000" if remaining[0] % 2 == 0 else "#ff6600"
        elif remaining[0] <= 30:
            color = "#ff2200"
        else:
            color = "#ff0000"
        timer_lbl.config(fg=color)

        bar_canvas.update_idletasks()
        w = bar_canvas.winfo_width()
        filled = int(w * (1 - remaining[0] / total)) if total > 0 else 0
        bar_canvas.coords(bar_fill, 0, 0, filled, 8)

        remaining[0] -= 1
        _root.after(1000, tick)

    tick()


def _window_alive():
    try:
        return _countdown_window is not None and _countdown_window.winfo_exists()
    except Exception:
        return False


def show_countdown(seconds: int = 60, distraction: str = "", on_close_cb=None):
    global _countdown_running, _countdown_paused
    if _window_alive():
        return
    _countdown_running = True
    _countdown_paused  = False
    if _root is not None:
        _root.after(0, lambda: _create_countdown(seconds, distraction, on_close_cb))
    else:
        print("[COUNTDOWN] no hay root disponible para crear countdown")


def pause_countdown():
    global _countdown_paused
    _countdown_paused = True


def resume_countdown():
    global _countdown_paused
    _countdown_paused = False


def dismiss_countdown():
    global _countdown_running
    _countdown_running = False
