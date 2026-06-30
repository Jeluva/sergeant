import tkinter as tk
import threading
import time
import os
from datetime import datetime, timedelta

try:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
    from config import PRODUCTIVE_PROCESSES as _PROD_PROCESSES
    import webcam as _webcam_mod
except Exception:
    _PROD_PROCESSES = {"code.exe", "windowsterminal.exe", "python3.12.exe", "python.exe"}
    _webcam_mod = None

_root = None
_stop_event = threading.Event()
_blink_state = [True]

G_BG    = "#0a0a0a"
G_GREEN = "#00ff41"
G_DIM   = "#1a6b30"
G_WHITE = "#cccccc"
G_ORANGE= "#ff8800"
G_RED   = "#ff3333"

D_BG    = "#0d0000"
D_RED   = "#ff2222"
D_ORANGE= "#ff6600"
D_DIM   = "#4a0a0a"
D_WHITE = "#ffaaaa"

FONT       = ("Courier New", 11)
FONT_BOLD  = ("Courier New", 11, "bold")
FONT_TITLE = ("Courier New", 15, "bold")
FONT_SMALL = ("Courier New", 9)
FONT_BIG   = ("Courier New", 18, "bold")
FONT_TAB   = ("Courier New", 10, "bold")


def _seconds_to_hms(s):
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


class _DarkScrollbar(tk.Canvas):
    """Scrollbar custom que respeta la estética terminal (evita el scrollbar nativo de Windows)."""
    def __init__(self, parent, command=None, **kw):
        kw.setdefault("width", 8)
        kw.setdefault("bg", "#0d0d0d")
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("cursor", "arrow")
        super().__init__(parent, **kw)
        self._command    = command
        self._first      = 0.0
        self._last       = 1.0
        self._drag_y     = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>",  self._on_click)
        self.bind("<B1-Motion>", self._on_drag)

    def set(self, first, last):
        self._first = float(first)
        self._last  = float(last)
        self._redraw()

    def _redraw(self):
        self.delete("all")
        h  = self.winfo_height() or 200
        w  = self.winfo_width()  or 8
        y1 = int(self._first * h)
        y2 = max(int(self._last * h), y1 + 16)
        self.create_rectangle(0, 0, w, h, fill="#0d0d0d", outline="")
        self.create_rectangle(1, y1, w - 1, y2, fill=G_DIM, outline="")

    def _on_click(self, event):
        h     = self.winfo_height() or 1
        frac  = event.y / h
        thumb = self._last - self._first
        if self._command:
            self._command("moveto", str(frac - thumb / 2))
        self._drag_y = event.y

    def _on_drag(self, event):
        if self._drag_y is None:
            return
        h     = self.winfo_height() or 1
        delta = (event.y - self._drag_y) / h
        self._drag_y = event.y
        if self._command:
            self._command("moveto", str(self._first + delta))


def _set_bg_recursive(widget, bg):
    try:
        widget.configure(bg=bg)
    except Exception:
        pass
    for child in widget.winfo_children():
        _set_bg_recursive(child, bg)


# ─────────────────────────────────────────────
#  HISTORY TAB
# ─────────────────────────────────────────────
def _build_history_tab(parent):
    frame = tk.Frame(parent, bg=G_BG)

    tk.Label(frame, text=f"  HISTORIAL — {datetime.now().strftime('%Y-%m-%d')}",
             font=FONT_BOLD, fg=G_GREEN, bg=G_BG, anchor="w").pack(
             fill=tk.X, padx=10, pady=(10, 0))

    summary_var = tk.StringVar(value="")
    tk.Label(frame, textvariable=summary_var, font=FONT_SMALL,
             fg=G_DIM, bg=G_BG, anchor="w").pack(fill=tk.X, padx=22, pady=(2, 2))

    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(0, 0))

    outer = tk.Frame(frame, bg=G_BG)
    outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))

    sb = _DarkScrollbar(outer, command=None)
    tl = tk.Canvas(outer, bg="#0d0d0d", highlightthickness=0,
                   yscrollcommand=sb.set)
    sb._command = tl.yview
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    tl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tl.bind("<MouseWheel>",
            lambda e: tl.yview_scroll(-1 * (e.delta // 120), "units"))

    PX_PER_MIN = 1.5
    LABEL_W    = 50
    BLOCK_X    = LABEL_W + 8
    PAD_TOP    = 12

    _last_visible = [None]
    _blocks       = []
    _tooltip      = [None]
    _hover_block  = [None]

    def _parse_ts(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _dur_secs(start, end):
        ts = _parse_ts(start)
        te = _parse_ts(end) if end else datetime.now()
        return int((te - ts).total_seconds()) if ts else 0

    def _fmt_dur(s):
        h, m = s // 3600, (s % 3600) // 60
        return f"{h}h{m:02d}m" if h else (f"{m}m" if m else f"{s}s")

    def _hide_tooltip():
        if _tooltip[0]:
            try:
                _tooltip[0].destroy()
            except Exception:
                pass
            _tooltip[0] = None

    def _show_tooltip(info, sx, sy):
        ts = _parse_ts(info["start"])
        te = _parse_ts(info["end"]) if info["end"] else datetime.now()
        dur_s   = int((te - ts).total_seconds()) if ts else 0
        start_s = info["start"][11:16] if info["start"] else "?"
        end_s   = info["end"][11:16]   if info["end"]   else "ahora"
        status_label = {"PRODUCTIVE": "PRODUCTIVO", "DISTRACTION": "DISTRACCION"}.get(
            info["status"], info["status"])
        text = (f"  {status_label}  ·  {start_s} -> {end_s}  ({_fmt_dur(dur_s)})\n"
                f"  {info['title'][:70]}\n"
                f"  {info['proc']}")
        status_fg = {"PRODUCTIVE": G_GREEN, "DISTRACTION": D_RED}.get(info["status"], G_DIM)

        tip = tk.Toplevel(parent)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg="#111111")
        tk.Label(tip, text=text, bg="#111111", fg=status_fg,
                 font=("Courier New", 9), padx=10, pady=6,
                 justify="left",
                 highlightthickness=1, highlightbackground="#333333").pack()
        tip.update_idletasks()
        sh = tip.winfo_screenheight()
        th = tip.winfo_reqheight()
        sy_adj = sy - th - 4 if sy + th + 10 > sh else sy + 10
        tip.geometry(f"+{sx + 15}+{sy_adj}")
        _tooltip[0] = tip

    def _on_motion(event):
        cy = tl.canvasy(event.y)
        found = next((info for y1, y2, info in reversed(_blocks) if y1 <= cy <= y2), None)
        sx = tl.winfo_rootx() + event.x
        sy = tl.winfo_rooty() + event.y
        if found is not _hover_block[0]:
            _hover_block[0] = found
            _hide_tooltip()
            if found:
                _show_tooltip(found, sx, sy)
        elif found and _tooltip[0]:
            sh = tl.winfo_screenheight()
            th = _tooltip[0].winfo_height()
            sy_adj = sy - th - 4 if sy + th + 10 > sh else sy + 10
            _tooltip[0].geometry(f"+{sx + 15}+{sy_adj}")

    def _on_leave(event):
        _hover_block[0] = None
        _hide_tooltip()

    tl.bind("<Motion>", _on_motion)
    tl.bind("<Leave>",  _on_leave)

    def _draw(visible):
        _last_visible[0] = visible
        _blocks.clear()
        _hide_tooltip()
        _hover_block[0] = None
        tl.delete("all")
        tl.update_idletasks()
        cw = max(tl.winfo_width(), 500)

        now     = datetime.now()
        t_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        t_end   = t_start + timedelta(hours=24)
        canvas_h = int(1440 * PX_PER_MIN) + PAD_TOP + 20
        block_w  = cw - BLOCK_X - 6

        def _y(dt):
            return int((dt - t_start).total_seconds() / 60 * PX_PER_MIN) + PAD_TOP

        cur = t_start
        while cur < t_end:
            y       = _y(cur)
            is_hour = cur.minute == 0
            tl.create_line(BLOCK_X, y, cw - 4, y,
                           fill="#262626" if is_hour else "#191919")
            tl.create_text(LABEL_W, y, text=cur.strftime("%H:%M"),
                           fill="#5a9a60" if is_hour else "#2c4a2c",
                           font=("Courier New", 8 if is_hour else 7), anchor="e")
            cur += timedelta(minutes=30)

        if not visible:
            tl.create_text(BLOCK_X + block_w // 2, _y(now) - 20,
                           text="sin sesiones registradas hoy",
                           fill=G_DIM, font=FONT_SMALL, anchor="center")
        else:
            COLORS = {
                "PRODUCTIVE":  (G_GREEN, "#002208"),
                "DISTRACTION": (D_RED,   "#1a0000"),
            }
            for title, proc, status, start, end in visible:
                ts = _parse_ts(start)
                te = _parse_ts(end) if end else now
                if not ts:
                    continue
                y1 = _y(ts)
                y2 = max(_y(te), y1 + 3)

                fill, txt_c = COLORS.get(status, ("#2a2a2a", "#555555"))
                tl.create_rectangle(BLOCK_X + 1, y1, BLOCK_X + block_w, y2,
                                    fill=fill, outline="")
                if y2 - y1 >= 12:
                    dur_str = _fmt_dur(int((te - ts).total_seconds()))
                    label   = f"{title[:46]}  {dur_str}"
                    tl.create_text(BLOCK_X + 6, (y1 + y2) // 2, text=label,
                                   fill=txt_c, font=("Courier New", 8), anchor="w")

                _blocks.append((y1, y2, {
                    "title": title, "proc": proc,
                    "status": status, "start": start, "end": end,
                }))

        yn = _y(now)
        tl.create_line(LABEL_W + 2, yn, cw - 4, yn, fill=G_GREEN, width=1)
        tl.create_oval(LABEL_W - 2, yn - 3, LABEL_W + 4, yn + 3,
                       fill=G_GREEN, outline="")

        tl.configure(scrollregion=(0, 0, cw, canvas_h))
        frac = max(0.0, min((now.hour * 60 + now.minute) / 1440 - 0.05, 0.95))
        tl.yview_moveto(frac)

    tl.bind("<Configure>",
            lambda e: _draw(_last_visible[0]) if _last_visible[0] is not None else None)

    _NOISE = ("sergeant", "c:\\program files\\windowsapps\\python", "seleccionar c:\\")

    def refresh_history():
        try:
            import sys as _s, os as _o
            _s.path.insert(0, _o.path.dirname(_o.path.dirname(__file__)))
            from tracker import get_today_calendar
            sessions = get_today_calendar()
        except Exception:
            sessions = []

        visible = [s for s in sessions
                   if not any(s[0].lower().startswith(n) for n in _NOISE)
                   and _dur_secs(s[3], s[4]) >= 10]

        prod_s = sum(_dur_secs(s[3], s[4]) for s in visible if s[2] == "PRODUCTIVE")
        dist_s = sum(_dur_secs(s[3], s[4]) for s in visible if s[2] == "DISTRACTION")
        summary = (f"  prod {_fmt_dur(prod_s)}  ·  dist {_fmt_dur(dist_s)}"
                   if visible else "")

        def _render():
            summary_var.set(summary)
            _draw(visible)

        parent.after(0, _render)

    return frame, refresh_history


# ─────────────────────────────────────────────
#  MISSION TAB
# ─────────────────────────────────────────────
def _build_mission_tab(parent, get_state_fn, apply_goal_fn):
    frame = tk.Frame(parent, bg=G_BG)

    tk.Label(frame, text="  MISION ACTIVA", font=FONT_BOLD,
             fg=G_GREEN, bg=G_BG, anchor="w").pack(fill=tk.X, padx=10, pady=(14, 0))
    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(2, 6))

    # Objetivo actual (display)
    tk.Label(frame, text="  objetivo actual:", font=FONT_SMALL,
             fg=G_DIM, bg=G_BG, anchor="w").pack(fill=tk.X, padx=20)
    goal_display_var = tk.StringVar(value="")
    tk.Label(frame, textvariable=goal_display_var, font=FONT_BOLD,
             fg=G_GREEN, bg=G_BG, anchor="w",
             wraplength=860, justify="left").pack(fill=tk.X, padx=26, pady=(2, 2))

    # Keywords dinámicas activas
    keywords_var = tk.StringVar(value="  [extrayendo keywords del objetivo...]")
    tk.Label(frame, textvariable=keywords_var, font=("Courier New", 8),
             fg=G_DIM, bg=G_BG, anchor="w", wraplength=860).pack(fill=tk.X, padx=26, pady=(0, 10))

    # Campo de edición
    tk.Label(frame, text="  nuevo objetivo:", font=FONT_SMALL,
             fg=G_DIM, bg=G_BG, anchor="w").pack(fill=tk.X, padx=20)
    goal_entry = tk.Text(frame, height=3, font=FONT, bg="#0d0d0d", fg=G_WHITE,
                         insertbackground=G_GREEN, relief=tk.FLAT, bd=0,
                         highlightthickness=1, highlightcolor=G_DIM,
                         highlightbackground=G_DIM)
    goal_entry.pack(fill=tk.X, padx=26, pady=(2, 0))

    feedback_var = tk.StringVar(value="")
    feedback_lbl = tk.Label(frame, textvariable=feedback_var, font=FONT_SMALL,
                            fg=G_GREEN, bg=G_BG, anchor="w")
    feedback_lbl.pack(fill=tk.X, padx=26, pady=(2, 0))

    # ── Helpers ──────────────────────────────────────────────

    def _do_apply(goal):
        if apply_goal_fn:
            apply_goal_fn(goal)
        goal_entry.delete("1.0", tk.END)
        feedback_var.set(f"  objetivo actualizado: {goal[:60]}")
        feedback_lbl.config(fg=G_GREEN)
        frame.after(4000, lambda: feedback_var.set(""))

    def _show_ambiguity_dialog(original_goal, analysis):
        reason    = analysis.get("reason", "objetivo demasiado vago")
        suggested = analysis.get("suggested", original_goal)

        try:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            sw, sh = 1920, 1080

        dlg = tk.Toplevel(parent)
        dlg.title("SERGEANT — OBJETIVO AMBIGUO")
        dlg.configure(bg="#0d0800")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        W, H = 620, 300
        dlg.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        def _use_original():
            dlg.destroy()
            _do_apply(original_goal)

        def _use_suggested():
            goal_entry.delete("1.0", tk.END)
            goal_entry.insert("1.0", suggested)
            dlg.destroy()
            _do_apply(suggested)

        dlg.protocol("WM_DELETE_WINDOW", _use_original)

        tk.Label(dlg, text="  ⚠  OBJETIVO AMBIGUO", font=("Courier New", 12, "bold"),
                 fg="#ff8800", bg="#0d0800", anchor="w").pack(fill=tk.X, padx=20, pady=(16, 4))
        tk.Label(dlg, text=f"  {reason}", font=("Courier New", 9),
                 fg="#886600", bg="#0d0800", anchor="w",
                 wraplength=580, justify="left").pack(fill=tk.X, padx=20, pady=(0, 12))

        tk.Label(dlg, text="  objetivo actual:", font=("Courier New", 9),
                 fg="#444444", bg="#0d0800", anchor="w").pack(fill=tk.X, padx=20)
        tk.Label(dlg, text=f"  {original_goal[:90]}", font=("Courier New", 10),
                 fg="#666666", bg="#0d0800", anchor="w",
                 wraplength=580).pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(dlg, text="  sugerencia:", font=("Courier New", 9),
                 fg="#005500", bg="#0d0800", anchor="w").pack(fill=tk.X, padx=20)
        tk.Label(dlg, text=f"  {suggested[:90]}", font=("Courier New", 10, "bold"),
                 fg=G_GREEN, bg="#0d0800", anchor="w",
                 wraplength=580).pack(fill=tk.X, padx=20, pady=(0, 18))

        btn_row = tk.Frame(dlg, bg="#0d0800")
        btn_row.pack(fill=tk.X, padx=20)
        tk.Button(btn_row, text="  USAR SUGERENCIA  ", font=FONT_BOLD,
                  fg="#000000", bg=G_GREEN, relief=tk.FLAT, cursor="hand2",
                  command=_use_suggested,
                  activebackground="#00cc33", activeforeground="#000000").pack(side=tk.LEFT, padx=(0, 12))
        tk.Button(btn_row, text="  usar original  ", font=FONT_SMALL,
                  fg="#555555", bg="#111111", relief=tk.FLAT, cursor="hand2",
                  command=_use_original,
                  activebackground="#1a1a1a").pack(side=tk.LEFT)

    def _finish_apply(original_goal, analysis):
        apply_btn.config(text="  APPLY  ", state=tk.NORMAL, bg=G_GREEN)
        if (analysis
                and analysis.get("is_ambiguous")
                and analysis.get("suggested", original_goal) != original_goal):
            _show_ambiguity_dialog(original_goal, analysis)
        else:
            _do_apply(original_goal)

    def on_apply():
        new_goal = goal_entry.get("1.0", tk.END).strip()
        if not new_goal:
            feedback_var.set("  escribe un objetivo antes de aplicar")
            feedback_lbl.config(fg=D_RED)
            return
        apply_btn.config(text="  ANALIZANDO...  ", state=tk.DISABLED, bg="#004400")
        feedback_var.set("  analizando objetivo con IA...")
        feedback_lbl.config(fg=G_DIM)

        def _run_analysis():
            try:
                import sys as _s, os as _o
                _s.path.insert(0, _o.path.dirname(_o.path.dirname(__file__)))
                from classifier import analyze_goal
                result = analyze_goal(new_goal)
            except Exception:
                result = None
            parent.after(0, lambda: _finish_apply(new_goal, result))

        threading.Thread(target=_run_analysis, daemon=True).start()

    apply_btn = tk.Button(frame, text="  APPLY  ", font=FONT_BOLD,
                          fg="#000000", bg=G_GREEN, relief=tk.FLAT,
                          cursor="hand2", command=on_apply,
                          activebackground="#00cc33", activeforeground="#000000")
    apply_btn.pack(anchor="w", padx=26, pady=(8, 0))

    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(20, 6))

    # Estado de sesión / infracciones
    infraction_var = tk.StringVar(value="")
    infraction_lbl = tk.Label(frame, textvariable=infraction_var, font=FONT,
                              fg=G_WHITE, bg=G_BG, anchor="w")
    infraction_lbl.pack(fill=tk.X, padx=20, pady=(0, 2))

    bar_var = tk.StringVar(value="")
    tk.Label(frame, textvariable=bar_var, font=FONT_BOLD,
             fg=G_GREEN, bg=G_BG, anchor="w").pack(fill=tk.X, padx=26, pady=(0, 4))

    def refresh(state):
        goal       = state.get("goal", "")
        count      = state.get("infraction_count", 0)
        limit      = state.get("close_limit", 3)
        persistent = state.get("countdown_persistent", False)

        goal_display_var.set(goal)

        # Keywords display
        kws      = state.get("goal_keywords", {})
        prod_kws = kws.get("productive", [])
        dist_kws = kws.get("distraction", [])
        if prod_kws:
            preview = ", ".join(prod_kws[:10])
            if len(prod_kws) > 10:
                preview += f" +{len(prod_kws) - 10} más"
            keywords_var.set(f"  [{len(prod_kws)} prod / {len(dist_kws)} dist]  {preview}")
        else:
            keywords_var.set("  [extrayendo keywords del objetivo...]")

        if persistent:
            infraction_var.set("  MODO COUNTDOWN ACTIVO")
            infraction_lbl.config(fg=D_RED)
            bar_var.set("  [countdown persistente en curso — retoma el trabajo para pausarlo]")
        else:
            infraction_var.set(f"  infracciones esta sesion:  {count} / {limit}  cierres de pestana")
            infraction_lbl.config(fg=G_WHITE)
            filled = int(count / limit * 20) if limit else 0
            bar = "[" + "|" * filled + " " * (20 - filled) + "]"
            bar_var.set(f"  {bar}  {'proximo: countdown sys32' if count >= limit - 1 else ''}")

    return frame, refresh


# ─────────────────────────────────────────────
#  CONFIG TAB
# ─────────────────────────────────────────────
def _build_config_tab(parent):
    frame = tk.Frame(parent, bg=G_BG)

    tk.Label(frame, text="  CONFIG", font=FONT_BOLD,
             fg=G_GREEN, bg=G_BG, anchor="w").pack(fill=tk.X, padx=10, pady=(14, 0))
    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(2, 6))

    tk.Label(frame, text="  TWITTER / X", font=FONT_BOLD,
             fg=G_DIM, bg=G_BG, anchor="w").pack(fill=tk.X, padx=10, pady=(4, 0))

    info_lbl = tk.Label(frame,
        text=("  Vincular Twitter permite que SERGEANT tweetee tus infracciones en tiempo real.\n"
              "  Necesitas una app en developer.twitter.com con permisos Read + Write."),
        font=FONT_SMALL, fg=G_DIM, bg=G_BG, anchor="w", justify="left")
    info_lbl.pack(fill=tk.X, padx=20, pady=(0, 12))

    # Determinar path del .env
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

    def _read_env_key(key):
        return os.environ.get(key, "")

    FIELDS = [
        ("TWITTER_API_KEY",       "API Key"),
        ("TWITTER_API_SECRET",    "API Secret"),
        ("TWITTER_ACCESS_TOKEN",  "Access Token"),
        ("TWITTER_ACCESS_SECRET", "Access Secret"),
    ]

    entries = {}
    for env_key, label in FIELDS:
        row = tk.Frame(frame, bg=G_BG)
        row.pack(fill=tk.X, padx=20, pady=3)
        tk.Label(row, text=f"  {label:<18}", font=FONT, fg=G_DIM, bg=G_BG,
                 anchor="w", width=22).pack(side=tk.LEFT)
        current = _read_env_key(env_key)
        e = tk.Entry(row, font=FONT, bg="#0d0d0d", fg=G_WHITE,
                     insertbackground=G_GREEN, relief=tk.FLAT,
                     highlightthickness=1, highlightbackground=G_DIM,
                     show="*")
        e.insert(0, current)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Botón ojo para revelar/ocultar
        visible = [False]
        def _toggle(entry=e, state=visible):
            state[0] = not state[0]
            entry.config(show="" if state[0] else "*")
        tk.Button(row, text="ver", font=FONT_SMALL, fg=G_DIM, bg="#111111",
                  relief=tk.FLAT, cursor="hand2", command=_toggle,
                  activebackground="#1a1a1a").pack(side=tk.LEFT, padx=(4, 0))
        entries[env_key] = e

    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(16, 6))

    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(frame, textvariable=status_var, font=FONT_SMALL,
                          fg=G_GREEN, bg=G_BG, anchor="w")
    status_lbl.pack(fill=tk.X, padx=26, pady=(0, 6))

    def _save_env(keys_dict):
        lines = []
        existing = set()
        if os.path.exists(_env_path):
            with open(_env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip()
                    if "=" in line and not line.startswith("#"):
                        k = line.split("=", 1)[0].strip()
                        if k in keys_dict:
                            existing.add(k)
                            lines.append(f"{k}={keys_dict[k]}")
                        else:
                            lines.append(line)
                    else:
                        lines.append(line)
        for k, v in keys_dict.items():
            if k not in existing:
                lines.append(f"{k}={v}")
        with open(_env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def on_save():
        vals = {k: e.get().strip() for k, e in entries.items()}
        if not all(vals.values()):
            status_var.set("  completa todos los campos antes de guardar")
            status_lbl.config(fg=D_RED)
            return
        vals["TWITTER_ENABLED"] = "true"
        # Actualizar os.environ para uso inmediato
        for k, v in vals.items():
            os.environ[k] = v
        _save_env(vals)
        status_var.set("  guardado en .env — reinicia la app para activar tweets")
        status_lbl.config(fg=G_GREEN)

    def on_clear():
        for k in list(entries.keys()) + ["TWITTER_ENABLED"]:
            os.environ.pop(k, None)
        _save_env({k: "" for k in entries})
        for e in entries.values():
            e.delete(0, tk.END)
        status_var.set("  credenciales eliminadas — Twitter desactivado")
        status_lbl.config(fg=G_DIM)

    btn_row = tk.Frame(frame, bg=G_BG)
    btn_row.pack(fill=tk.X, padx=20, pady=(0, 4))

    tk.Button(btn_row, text="  GUARDAR Y ACTIVAR  ", font=FONT_BOLD,
              fg="#000000", bg=G_GREEN, relief=tk.FLAT, cursor="hand2",
              command=on_save, activebackground="#00cc33",
              activeforeground="#000000").pack(side=tk.LEFT, padx=(6, 12))

    tk.Button(btn_row, text="  desactivar  ", font=FONT_SMALL,
              fg=G_DIM, bg="#111111", relief=tk.FLAT, cursor="hand2",
              command=on_clear, activebackground="#1a1a1a").pack(side=tk.LEFT)

    # ── SECCIÓN WEBCAM ──────────────────────────────────────
    tk.Label(frame, text="-" * 95, font=("Courier New", 9),
             fg=G_DIM, bg=G_BG).pack(fill=tk.X, padx=10, pady=(18, 6))

    tk.Label(frame, text="  PRESENCIA (WEBCAM)", font=FONT_BOLD,
             fg=G_GREEN, bg=G_BG, anchor="w").pack(fill=tk.X, padx=10, pady=(4, 0))

    tk.Label(frame,
             text=("  Detecta si estás frente al monitor usando la cámara.\n"
                   "  Si no se detecta presencia, SERGEANT registra una infracción AFK."),
             font=FONT_SMALL, fg=G_DIM, bg=G_BG, anchor="w", justify="left"
             ).pack(fill=tk.X, padx=20, pady=(4, 10))

    cam_status_var = tk.StringVar(value="  INACTIVO")
    cam_status_lbl = tk.Label(frame, textvariable=cam_status_var,
                               font=FONT_SMALL, fg=G_DIM, bg=G_BG, anchor="w")
    cam_status_lbl.pack(fill=tk.X, padx=26, pady=(0, 6))

    def _refresh_cam_status():
        if _webcam_mod is None:
            cam_status_var.set("  ERROR: webcam.py no disponible")
            cam_status_lbl.configure(fg=D_RED)
            return
        if _webcam_mod.is_running():
            present, reason = _webcam_mod.get_presence()
            if present is True:
                cam_status_var.set("  PRESENCIA DETECTADA  ●")
                cam_status_lbl.configure(fg=G_GREEN)
            elif present is False:
                cam_status_var.set("  SIN PRESENCIA  ○")
                cam_status_lbl.configure(fg=D_RED)
            else:
                cam_status_var.set(f"  {reason}")
                cam_status_lbl.configure(fg=G_DIM)
        else:
            cam_status_var.set("  INACTIVO")
            cam_status_lbl.configure(fg=G_DIM)
        frame.after(2000, _refresh_cam_status)

    def _toggle_webcam():
        if _webcam_mod is None:
            cam_status_var.set("  ERROR: módulo webcam no disponible")
            cam_status_lbl.configure(fg=D_RED)
            return
        if _webcam_mod.is_running():
            _webcam_mod.stop()
            cam_toggle_btn.configure(text="  ACTIVAR  ")
            cam_status_var.set("  INACTIVO")
            cam_status_lbl.configure(fg=G_DIM)
        else:
            ok = _webcam_mod.start()
            if ok:
                cam_toggle_btn.configure(text="  DESACTIVAR  ")
                cam_status_var.set("  iniciando...")
                cam_status_lbl.configure(fg=G_DIM)
            else:
                cam_status_var.set("  ERROR: instala opencv-python y mediapipe, o verifica la cámara")
                cam_status_lbl.configure(fg=D_RED)

    cam_btn_row = tk.Frame(frame, bg=G_BG)
    cam_btn_row.pack(fill=tk.X, padx=20, pady=(0, 10))

    _initial_cam_text = "  DESACTIVAR  " if (_webcam_mod and _webcam_mod.is_running()) else "  ACTIVAR  "
    cam_toggle_btn = tk.Button(cam_btn_row, text=_initial_cam_text, font=FONT_BOLD,
                                fg="#000000", bg=G_GREEN, relief=tk.FLAT, cursor="hand2",
                                command=_toggle_webcam, activebackground="#00cc33",
                                activeforeground="#000000")
    cam_toggle_btn.pack(side=tk.LEFT, padx=(6, 0))

    frame.after(2000, _refresh_cam_status)

    return frame


# ─────────────────────────────────────────────
#  MAIN UI
# ─────────────────────────────────────────────
def _build_ui(get_state_fn, apply_goal_fn=None):
    global _root

    root = tk.Tk()
    _root = root

    # Registrar el root en toast y countdown para que usen Toplevel (evita multi-Tk crashes)
    try:
        from ui import toast as _toast_mod, countdown as _cd_mod
        _toast_mod.set_root(root)
        _cd_mod.set_root(root)
    except Exception:
        pass

    root.title("SERGEANT")
    root.configure(bg=G_BG)
    root.resizable(True, True)
    W, H = 980, 700
    try:
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    root.attributes("-topmost", True)
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    root.after(200, lambda: (root.lift(), root.focus_force()))

    def _force_countdown(event=None):
        from ui.countdown import show_countdown
        try:
            from config import COUNTDOWN_DURATION_SECS
        except Exception:
            COUNTDOWN_DURATION_SECS = 20
        show_countdown(seconds=COUNTDOWN_DURATION_SECS, distraction="[DEMO FORZADO]")
    root.bind("<Control-d>", _force_countdown)
    root.bind("<Control-D>", _force_countdown)

    # ── HEADER ──────────────────────────────────────────────
    hdr = tk.Frame(root, bg=G_BG)
    hdr.pack(fill=tk.X)

    try:
        from config import DEMO_MODE as _dm
        _demo_suffix = "  [DEMO]" if _dm else ""
    except Exception:
        _demo_suffix = ""

    title_lbl = tk.Label(hdr, text=f"[ SERGEANT ]{_demo_suffix}",
                         font=FONT_TITLE, fg=G_GREEN, bg=G_BG)
    title_lbl.pack(side=tk.LEFT, padx=20, pady=(12, 4))

    clock_var = tk.StringVar()
    clock_lbl = tk.Label(hdr, textvariable=clock_var, font=FONT_SMALL,
                         fg=G_DIM, bg=G_BG)
    clock_lbl.pack(side=tk.RIGHT, padx=20, pady=(12, 4))

    # ── TAB BAR ─────────────────────────────────────────────
    tab_bar = tk.Frame(root, bg="#111111")
    tab_bar.pack(fill=tk.X)

    _active_tab      = [None]
    _history_refresh = [None]
    _mission_refresh = [None]

    monitor_frame = tk.Frame(root, bg=G_BG)
    history_frame, history_refresh_fn = _build_history_tab(root)
    mission_frame, mission_refresh_fn = _build_mission_tab(root, get_state_fn, apply_goal_fn)
    config_frame = _build_config_tab(root)

    _history_refresh[0] = history_refresh_fn
    _mission_refresh[0] = mission_refresh_fn

    TABS = ["monitor", "history", "mission", "config"]
    ALL_FRAMES = {
        "monitor": monitor_frame,
        "history": history_frame,
        "mission": mission_frame,
        "config":  config_frame,
    }
    BTN_LABELS = {
        "monitor": "  MONITOR  ",
        "history": "  HISTORIAL  ",
        "mission": "  MISION  ",
        "config":  "  CONFIG  ",
    }
    btns = {}

    def _switch(tab_name):
        if _active_tab[0] == tab_name:
            return
        _active_tab[0] = tab_name
        for name, frame in ALL_FRAMES.items():
            if name == tab_name:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        for name, btn in btns.items():
            if name == tab_name:
                btn.configure(fg="#000000", bg=G_GREEN)
            else:
                btn.configure(fg=G_DIM, bg="#111111")
        if tab_name == "history":
            threading.Thread(target=_history_refresh[0], daemon=True).start()

    for tab_name in TABS:
        btn = tk.Button(tab_bar, text=BTN_LABELS[tab_name],
                        font=FONT_TAB, relief=tk.FLAT, bd=0,
                        cursor="hand2",
                        command=lambda n=tab_name: _switch(n))
        btn.pack(side=tk.LEFT)
        btns[tab_name] = btn

    # ── MONITOR TAB CONTENT ──────────────────────────────────
    sep1 = tk.Label(monitor_frame, text="-" * 95, font=("Courier New", 9),
                    fg=G_DIM, bg=G_BG)
    sep1.pack(fill=tk.X, padx=10)

    threat_frame = tk.Frame(monitor_frame, bg=G_BG)
    threat_frame.pack(fill=tk.X, padx=20, pady=(6, 2))
    tk.Label(threat_frame, text="THREAT", font=("Courier New", 9, "bold"),
             fg=G_DIM, bg=G_BG).pack(side=tk.LEFT, padx=(0, 8))
    defcon_canvas = tk.Canvas(threat_frame, height=14, bg=G_BG, highlightthickness=0)
    defcon_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(threat_frame, text="DEFCON", font=("Courier New", 9, "bold"),
             fg=G_DIM, bg=G_BG).pack(side=tk.RIGHT, padx=(8, 0))
    defcon_var = tk.StringVar(value="5")
    defcon_lbl = tk.Label(threat_frame, textvariable=defcon_var,
                          font=("Courier New", 13, "bold"), fg=G_GREEN, bg=G_BG)
    defcon_lbl.pack(side=tk.RIGHT)

    status_frame = tk.Frame(monitor_frame, bg=G_BG)
    status_frame.pack(fill=tk.X, padx=20, pady=(6, 2))
    status_var = tk.StringVar(value="●  WORKING")
    status_lbl = tk.Label(status_frame, textvariable=status_var,
                          font=FONT_BIG, fg=G_GREEN, bg=G_BG, anchor="w")
    status_lbl.pack(side=tk.LEFT)
    danger_var = tk.StringVar(value="")
    danger_lbl = tk.Label(status_frame, textvariable=danger_var,
                          font=FONT_BIG, fg=D_RED, bg=G_BG, anchor="e")
    danger_lbl.pack(side=tk.RIGHT)

    sep2 = tk.Label(monitor_frame, text="-" * 95, font=("Courier New", 9),
                    fg=G_DIM, bg=G_BG)
    sep2.pack(fill=tk.X, padx=10, pady=(4, 0))

    info_frame = tk.Frame(monitor_frame, bg=G_BG)
    info_frame.pack(fill=tk.X, padx=20, pady=(6, 2))
    info_frame.columnconfigure(1, weight=1)
    labels = {}
    for i, (name, fg) in enumerate([
        ("objetivo",   G_WHITE),
        ("ventana",    G_WHITE),
        ("proceso",    G_DIM),
        ("razon",      G_DIM),
        ("productivo", G_GREEN),
        ("infracc.",   G_WHITE),
        ("presencia",  G_GREEN),
    ]):
        tk.Label(info_frame, text=f"{name:<12}", font=FONT, fg=G_DIM, bg=G_BG,
                 anchor="w").grid(row=i, column=0, sticky="w")
        val_var = tk.StringVar()
        val_lbl = tk.Label(info_frame, textvariable=val_var, font=FONT, fg=fg,
                           bg=G_BG, anchor="w", wraplength=580, justify="left")
        val_lbl.grid(row=i, column=1, sticky="w")
        labels[name] = (val_var, val_lbl, fg)

    sep3 = tk.Label(monitor_frame, text="-" * 95, font=("Courier New", 9),
                    fg=G_DIM, bg=G_BG)
    sep3.pack(fill=tk.X, padx=10, pady=(6, 0))

    tk.Label(monitor_frame, text="  METRICAS DEL DIA",
             font=("Courier New", 9, "bold"), fg=G_DIM, bg=G_BG,
             anchor="w").pack(fill=tk.X, padx=20, pady=(4, 0))
    metrics_txt = tk.Text(monitor_frame, height=5, bg=G_BG, fg=G_DIM, font=FONT,
                          relief=tk.FLAT, bd=0, state=tk.DISABLED, cursor="arrow")
    metrics_txt.tag_config("prod_bar", foreground=G_GREEN)
    metrics_txt.tag_config("dist_bar", foreground=G_RED)
    metrics_txt.tag_config("dim_txt",  foreground=G_DIM)
    metrics_txt.pack(fill=tk.X, padx=20)

    sep4 = tk.Label(monitor_frame, text="-" * 95, font=("Courier New", 9),
                    fg=G_DIM, bg=G_BG)
    sep4.pack(fill=tk.X, padx=10, pady=(4, 0))

    tweet_var = tk.StringVar(value="")
    tweet_lbl = tk.Label(monitor_frame, textvariable=tweet_var,
                         font=("Courier New", 9, "italic"),
                         fg="#1d9bf0", bg=G_BG, anchor="w",
                         wraplength=760, justify="left")
    tweet_lbl.pack(fill=tk.X, padx=20, pady=(2, 0))

    tk.Label(monitor_frame, text="  ULTIMAS SESIONES",
             font=("Courier New", 9, "bold"), fg=G_DIM, bg=G_BG,
             anchor="w").pack(fill=tk.X, padx=20, pady=(4, 0))
    sessions_txt = tk.Text(monitor_frame, height=5, bg=G_BG, fg=G_DIM, font=FONT,
                           relief=tk.FLAT, bd=0, state=tk.DISABLED, cursor="arrow")
    sessions_txt.tag_config("prod", foreground=G_GREEN)
    sessions_txt.tag_config("dist", foreground=D_RED)
    sessions_txt.tag_config("unkn", foreground=G_DIM)
    sessions_txt.pack(fill=tk.X, padx=20, pady=(0, 10))

    all_seps = [sep1, sep2, sep3, sep4]

    # ── REFRESH LOOP ─────────────────────────────────────────
    def refresh():
        while not _stop_event.is_set():
            state       = get_state_fn()
            _blink_state[0] = not _blink_state[0]
            on          = _blink_state[0]
            dist_s      = state.get("distracted_seconds", 0)
            is_dist     = state.get("status") == "DISTRACTION"
            bg          = D_BG if is_dist else G_BG
            sep_fg      = D_DIM if is_dist else G_DIM

            if not is_dist or dist_s == 0:
                defcon = 5; dc_fg = G_GREEN
            elif dist_s < 20:
                defcon = 4; dc_fg = "#aaff00"
            elif dist_s < 30:
                defcon = 3; dc_fg = G_ORANGE
            elif dist_s < 45:
                defcon = 2; dc_fg = D_ORANGE
            else:
                defcon = 1; dc_fg = D_RED if on else "#ff6600"

            if is_dist:
                s_text = "⚠  DISTRACCION" if on else "⚠  INFRACCION"
                s_fg   = D_RED
                d_text = _seconds_to_hms(dist_s)
                d_fg   = D_ORANGE if defcon > 1 else (D_RED if on else "#ff6600")
            else:
                s_text = "●  WORKING"; s_fg = G_GREEN
                d_text = ""; d_fg = D_RED

            metrics   = state.get("metrics_raw", {})
            prod_secs = sum(v for k, v in metrics.items() if k in _PROD_PROCESSES)
            total_s   = sum(metrics.values()) if metrics else 0
            prod_str  = (f"{_seconds_to_hms(prod_secs)} productivo  /  {_seconds_to_hms(total_s)} total"
                         if total_s else "sin datos aun")
            now_s = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

            count      = state.get("infraction_count", 0)
            limit      = state.get("close_limit", 3)
            persistent = state.get("countdown_persistent", False)
            if persistent:
                infracc_str = "COUNTDOWN ACTIVO"
                infracc_fg  = D_RED
            else:
                infracc_str = f"{count} / {limit}  cierres"
                infracc_fg  = (G_ORANGE if count >= limit - 1 else G_WHITE)

            cam_present = state.get("webcam_present")
            if cam_present is True:
                cam_str = "DETECTADA  ●"
                cam_fg  = G_GREEN
            elif cam_present is False:
                cam_str = "AUSENTE  ○"
                cam_fg  = D_RED
            else:
                cam_str = "inactivo"
                cam_fg  = G_DIM

            def update_ui(
                bg=bg, is_dist=is_dist, sep_fg=sep_fg, dc_fg=dc_fg, defcon=defcon,
                s_text=s_text, s_fg=s_fg, d_text=d_text, d_fg=d_fg,
                prod_str=prod_str, now_s=now_s, state=state,
                infracc_str=infracc_str, infracc_fg=infracc_fg,
                cam_str=cam_str, cam_fg=cam_fg
            ):
                clock_var.set(now_s)
                title_lbl.configure(fg=(D_RED if is_dist else G_GREEN))
                tab_alert_bg = "#2a0000" if is_dist else "#111111"
                tab_bar.configure(bg=tab_alert_bg)
                if _active_tab[0] != "monitor":
                    # Actualizar tab MISION en background
                    if _mission_refresh[0]:
                        _mission_refresh[0](state)
                    return
                root.configure(bg=bg)
                _set_bg_recursive(monitor_frame, bg)   # solo el frame visible
                tab_bar.configure(bg=tab_alert_bg)
                # Restore tab styles tras recursive bg
                active = _active_tab[0]
                for name, btn in btns.items():
                    if name == active:
                        btn.configure(fg="#000000", bg=G_GREEN)
                    else:
                        btn.configure(fg=G_DIM, bg=tab_alert_bg)

                clock_lbl.configure(fg=sep_fg)
                defcon_lbl.configure(fg=dc_fg)
                for s in all_seps:
                    s.configure(fg=sep_fg)

                defcon_var.set(str(defcon))
                defcon_canvas.update_idletasks()
                w = defcon_canvas.winfo_width() or 400
                fill_w = int(w * (6 - defcon) / 5)
                colors = {5: G_GREEN, 4: "#aaff00", 3: G_ORANGE, 2: D_ORANGE, 1: D_RED}
                defcon_canvas.delete("all")
                defcon_canvas.configure(bg=bg)
                defcon_canvas.create_rectangle(0, 3, w, 11, fill="#1a1a1a", outline="")
                defcon_canvas.create_rectangle(0, 3, fill_w, 11,
                                               fill=colors[defcon], outline="")

                status_var.set(s_text); status_lbl.configure(fg=s_fg, bg=bg)
                danger_var.set(d_text); danger_lbl.configure(fg=d_fg, bg=bg)
                status_frame.configure(bg=bg)

                vals = {
                    "objetivo":   state.get("goal", "-"),
                    "ventana":    state.get("window", "-")[:70],
                    "proceso":    state.get("process", "-"),
                    "razon":      state.get("reason", "-"),
                    "productivo": prod_str,
                    "infracc.":   infracc_str,
                    "presencia":  cam_str,
                }
                for name, (var, lbl, orig_fg) in labels.items():
                    var.set(vals[name])
                    if name == "infracc.":
                        lbl.configure(fg=infracc_fg, bg=bg)
                    elif name == "presencia":
                        lbl.configure(fg=cam_fg, bg=bg)
                    else:
                        lbl.configure(fg=(D_WHITE if is_dist and orig_fg == G_WHITE else orig_fg),
                                      bg=bg)

                metrics_txt.config(state=tk.NORMAL, bg=bg)
                metrics_txt.delete("1.0", tk.END)
                rows = state.get("metrics_rows", [])
                if rows:
                    for app, bar, t_str, pct, is_prod in rows:
                        tag = "prod_bar" if is_prod else "dist_bar"
                        metrics_txt.insert(tk.END, f"  {app[:20]:<20} ", "dim_txt")
                        metrics_txt.insert(tk.END, bar, tag)
                        metrics_txt.insert(tk.END, f" {t_str} ({pct}%)\n", "dim_txt")
                else:
                    metrics_txt.insert(tk.END, "  sin datos todavia", "dim_txt")
                metrics_txt.config(state=tk.DISABLED)

                if state.get("tweet_flash"):
                    tweet_var.set(f"  [TWEET] {state.get('last_tweet', '')}")
                    tweet_lbl.configure(bg=bg)
                else:
                    tweet_var.set("")

                sessions_txt.config(state=tk.NORMAL, bg=bg)
                sessions_txt.delete("1.0", tk.END)
                for row in state.get("recent_sessions", [])[:5]:
                    t_title, proc, st, start, end = row
                    end_s = end[-8:] if end else "       "
                    tag = "prod" if st=="PRODUCTIVE" else ("dist" if st=="DISTRACTION" else "unkn")
                    sessions_txt.insert(tk.END,
                        f"  {start[-8:]} -> {end_s}  [{st[:4]}]  {t_title[:45]}\n", tag)
                sessions_txt.config(state=tk.DISABLED)

            root.after(0, update_ui)
            time.sleep(1)

    _switch("monitor")
    threading.Thread(target=refresh, daemon=True).start()
    root.mainloop()


def _build_ui_safe(get_state_fn, apply_goal_fn=None):
    try:
        _build_ui(get_state_fn, apply_goal_fn)
    except Exception:
        import traceback
        print(f"[DASHBOARD] crash:\n{traceback.format_exc()}", file=__import__("sys").stderr)


def launch_dashboard(get_state_fn, apply_goal_fn=None):
    threading.Thread(target=_build_ui_safe, args=(get_state_fn, apply_goal_fn), daemon=True).start()


def stop_dashboard():
    _stop_event.set()
    if _root:
        try:
            _root.quit()
        except Exception:
            pass
