import tkinter as tk
import threading
import time
import ctypes

GREEN  = "#00ff41"
DIM    = "#007a20"
BG     = "#0a0a0a"
ORANGE = "#ff8800"
RED    = "#ff3333"
FONT   = ("Courier New", 12)
FONT_B = ("Courier New", 12, "bold")


def _build_boot_lines(goal: str, twitter_enabled: bool) -> list:
    try:
        from config import POLL_INTERVAL_SECONDS, GRACE_PERIOD_SECONDS, DEMO_MODE
        interval_s = POLL_INTERVAL_SECONDS
        grace_s = GRACE_PERIOD_SECONDS
        demo_tag = "  [DEMO MODE -- timers acelerados]" if DEMO_MODE else ""
    except Exception:
        interval_s = 5
        grace_s = 30
        demo_tag = ""

    tw = "ARMED" if twitter_enabled else "DISABLED"
    return [
        ("", None, 0),
        ("  SERGEANT v1.0  //  PRODUCTIVITY ENFORCER", GREEN, 0),
        (f"  ANTIhackaton edition -- Black Mirror{demo_tag}", DIM, 60),
        ("", None, 100),
        ("  initializing threat monitor...", DIM, 200),
        ("  loading process blacklist............. OK", GREEN, 400),
        ("  loading distraction keywords........... OK", GREEN, 550),
        ("  initializing SQLite session tracker.... OK", GREEN, 700),
        (f"  twitter integration................. {tw}", ORANGE if tw == "DISABLED" else GREEN, 900),
        ("", None, 1100),
        (f"  objective  :  {goal}", GREEN, 1200),
        (f"  interval   :  {interval_s}s", DIM, 1350),
        (f"  grace      :  {grace_s}s before action", DIM, 1500),
        ("  escalation :  warn -> close -> countdown -> tweet", DIM, 1650),
        ("", None, 1800),
        ("  ENFORCER ARMED.", RED, 1900),
        ("  monitoring begins now.", DIM, 2050),
        ("", None, 2100),
    ]


def show_boot(goal: str, twitter_enabled: bool = False, on_done=None):
    """Muestra la secuencia de boot y llama on_done() al terminar."""

    root = tk.Tk()
    root.title("SERGEANT")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    W, H = 680, 360
    try:
        SW = ctypes.windll.user32.GetSystemMetrics(0)
        SH = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        SW = root.winfo_screenwidth()
        SH = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(SW-W)//2}+{(SH-H)//2}")
    root.lift()
    root.focus_force()

    canvas = tk.Text(root, bg=BG, fg=GREEN, font=FONT,
                     relief=tk.FLAT, bd=0, state=tk.DISABLED,
                     cursor="arrow", wrap=tk.WORD)
    canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    cursor_var = tk.StringVar(value="█")
    cursor_lbl = tk.Label(root, textvariable=cursor_var,
                          font=FONT_B, fg=GREEN, bg=BG)
    cursor_lbl.place(x=0, y=0)  # will be moved

    lines = _build_boot_lines(goal, twitter_enabled)

    def append(text, color=None):
        canvas.config(state=tk.NORMAL)
        tag = color or "default"
        canvas.tag_config(tag, foreground=color or GREEN)
        canvas.insert(tk.END, text + "\n", tag)
        canvas.see(tk.END)
        canvas.config(state=tk.DISABLED)

    def run():
        prev = 0
        for text, color, delay in lines:
            time.sleep((delay - prev) / 1000)
            prev = delay
            if text is not None:
                root.after(0, lambda t=text, c=color: append(t, c))

        time.sleep(0.6)
        root.after(0, root.destroy)
        if on_done:
            on_done()

    # Blinking cursor
    def blink():
        if not root.winfo_exists():
            return
        cursor_var.set("█" if cursor_var.get() == " " else " ")
        root.after(500, blink)

    blink()
    threading.Thread(target=run, daemon=True).start()
    root.mainloop()


