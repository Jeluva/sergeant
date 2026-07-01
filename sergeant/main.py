import sys
import os
import gc
import time
import threading
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

# ── LOGGING SETUP ────────────────────────────────────────────────────────────
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_log_path = os.path.join(_LOG_DIR, f"sergeant_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

class _Tee:
    def __init__(self, stream, path):
        self._stream = stream
        self._file = open(path, "a", encoding="utf-8", buffering=1)
        self._file.write(f"\n{'='*60}\n[SERGEANT] sesion iniciada {datetime.now()}\n{'='*60}\n")
    def write(self, data):
        try:
            self._stream.write(data)
        except Exception:
            pass
        try:
            self._file.write(data)
        except Exception:
            pass
    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass
        try:
            self._file.flush()
        except Exception:
            pass
    def fileno(self):
        return self._stream.fileno()
    def isatty(self):
        return False

sys.stdout = _Tee(sys.stdout, _log_path)
sys.stderr = _Tee(sys.stderr, _log_path)

def _uncaught_exception(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"\n[SERGEANT] EXCEPCION NO CAPTURADA:\n{msg}", file=sys.stderr)

def _thread_exception(args):
    msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    print(f"\n[SERGEANT] EXCEPCION EN THREAD ({args.thread.name}):\n{msg}", file=sys.stderr)

sys.excepthook = _uncaught_exception
threading.excepthook = _thread_exception
# ─────────────────────────────────────────────────────────────────────────────

from config import (
    CURRENT_GOAL, POLL_INTERVAL_SECONDS,
    GRACE_PERIOD_SECONDS, COUNTDOWN_DURATION_SECS,
    TWEET_THRESHOLD_SECONDS, TWITTER_ENABLED, DEMO_MODE,
    WEBCAM_ENABLED,
)
import webcam
from monitor import get_active_window
from classifier import classify, Status, clear_cache, analyze_goal, set_dynamic_keywords
from tracker import on_window_change, get_today_metrics, get_today_calendar, format_metrics_table
from enforcer import close_window, warn_before_close, trigger_countdown, dismiss, cancel_warning
from ui.countdown import pause_countdown, resume_countdown
from social import tweet_distraction
from db import init_db, close_open_sessions
from ui.dashboard import launch_dashboard
from ui.boot import show_boot
from ui.contract import show_contract

WARN_BEFORE_CLOSE = 10   # segundos de aviso antes de cerrar
CLOSE_LIMIT       = 3    # cierres antes de entrar en modo countdown permanente

state = {
    "goal":                CURRENT_GOAL,
    "window":              "",
    "process":             "",
    "status":              "UNKNOWN",
    "reason":              "",
    "distracted_seconds":  0,
    "metrics_rows":        [],
    "metrics_raw":         {},
    "recent_sessions":     [],
    "last_tweet":          "",
    "tweet_flash":         False,
    "infraction_count":    0,
    "close_limit":         CLOSE_LIMIT,
    "countdown_persistent": False,
    "goal_keywords":       {"productive": [], "distraction": []},
    "webcam_present":      None,
    "webcam_reason":       "inactivo",
}

_last_window_title   = None
_distracted_start    = None
_tweeted_at          = None
_warned              = False
_warned_pid          = None
_warned_title        = None
_countdown_shown     = False
_infraction_count    = 0
_countdown_persistent = False   # countdown de la 4ta infracción (pausa/reanuda, nunca se resetea)
_last_cam_present     = "unset"  # trackea cambios de presencia para loguear solo transiciones


def _do_close(window):
    global _infraction_count, _warned, _warned_pid, _warned_title, _distracted_start
    if state.get("status") == "DISTRACTION":
        close_window(window.pid, window.title, window.process_name)
        _infraction_count += 1
        state["infraction_count"] = _infraction_count
        print(f"[MAIN] infraccion #{_infraction_count}/{CLOSE_LIMIT}")
        # Resetear ciclo de aviso: si el usuario sigue en distracción (otra pestaña),
        # el próximo poll la detecta como nueva distracción y vuelve a avisar.
        _warned           = False
        _warned_pid       = None
        _warned_title     = None
        _distracted_start = None
    else:
        cancel_warning(window.pid)
        print(f"[MAIN] cierre cancelado — usuario retomo el trabajo")


def _update_state(window, status, reason):
    global _last_window_title, _distracted_start, _tweeted_at
    global _warned, _warned_pid, _warned_title, _countdown_shown
    global _countdown_persistent

    state["window"]  = window.title
    state["process"] = window.process_name
    state["status"]  = status.value
    state["reason"]  = reason

    if window.title != _last_window_title:
        on_window_change(window.title, window.process_name, status.value, state["goal"])
        _last_window_title = window.title

    if status == Status.DISTRACTION:
        if _distracted_start is None:
            _distracted_start = datetime.now()
            _warned       = False
            _warned_pid   = None
            _warned_title = None
            if not _countdown_persistent:
                _countdown_shown = False

        # Si cambió pestaña dentro de la distracción (solo en modo close), resetear aviso
        if not _countdown_persistent and _warned and window.title != _warned_title:
            if _warned_pid:
                cancel_warning(_warned_pid)
            _warned       = False
            _warned_pid   = None
            _warned_title = None

        elapsed = int((datetime.now() - _distracted_start).total_seconds())
        state["distracted_seconds"] = elapsed

        if _infraction_count >= CLOSE_LIMIT:
            # --- MODO COUNTDOWN (4ta infracción en adelante) ---
            state["countdown_persistent"] = True
            if not _countdown_persistent:
                trigger_countdown(seconds=COUNTDOWN_DURATION_SECS, distraction=window.title)
                _countdown_persistent = True
                _countdown_shown      = True
            else:
                resume_countdown()   # ya existía pausado, reanudar
        else:
            # --- MODO CLOSE (infracciones 1-3) ---
            warn_at = max(0, GRACE_PERIOD_SECONDS - WARN_BEFORE_CLOSE)
            if elapsed >= warn_at and not _warned:
                _warned       = True
                _warned_pid   = window.pid
                _warned_title = window.title
                actual_warn   = max(2, min(WARN_BEFORE_CLOSE, GRACE_PERIOD_SECONDS - elapsed))
                warn_before_close(
                    pid=window.pid,
                    title=window.title,
                    process_name=window.process_name,
                    warn_seconds=actual_warn,
                    on_close=lambda w=window: threading.Thread(target=lambda: _do_close(w), daemon=True).start(),
                )

        # Tweet (ambos modos)
        if elapsed >= TWEET_THRESHOLD_SECONDS:
            if _tweeted_at is None or int((datetime.now() - _tweeted_at).total_seconds()) >= TWEET_THRESHOLD_SECONDS:
                goal    = state["goal"]
                minutes = elapsed // 60
                tweet_distraction(minutes, window.title[:30], goal)
                _tweeted_at = datetime.now()
                msg = (f"llevo {minutes} min mirando '{window.title[:28]}' "
                       f"en vez de {goal[:40]}. #sergeant")
                state["last_tweet"]  = msg
                state["tweet_flash"] = True
                def _clear_flash():
                    time.sleep(6)
                    state["tweet_flash"] = False
                threading.Thread(target=_clear_flash, daemon=True).start()

    else:
        # Productivo / Desconocido
        if _countdown_persistent:
            pause_countdown()
            if _warned_pid:
                cancel_warning(_warned_pid)
        elif _distracted_start is not None:
            dismiss(warned_pid=_warned_pid, countdown_was_active=_countdown_shown)
            _countdown_shown = False

        _distracted_start = None
        _warned           = False
        _warned_pid       = None
        _warned_title     = None
        _tweeted_at       = None
        state["distracted_seconds"] = 0


def _persist_goal(goal: str):
    """Guarda el objetivo en .env para que sobreviva reinicios."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                if line.startswith("CURRENT_GOAL="):
                    lines.append(f"CURRENT_GOAL={goal}")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"CURRENT_GOAL={goal}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _extract_and_set_keywords(goal: str):
    """Llama a analyze_goal y actualiza keywords dinámicas + state. Corre en background thread."""
    result = analyze_goal(goal)
    if result:
        prod  = result.get("productive_keywords", [])
        dist  = result.get("distraction_keywords", [])
        set_dynamic_keywords(prod, dist)
        state["goal_keywords"] = {"productive": prod, "distraction": dist}


def _apply_goal(new_goal: str):
    """Actualiza el objetivo en caliente sin reiniciar la app."""
    global _last_window_title
    state["goal"]    = new_goal
    _last_window_title = None   # fuerza re-clasificación con el nuevo goal
    clear_cache()
    _persist_goal(new_goal)
    threading.Thread(target=_extract_and_set_keywords, args=(new_goal,), daemon=True).start()
    print(f"[MAIN] objetivo actualizado: {new_goal}")


def _refresh_metrics():
    while True:
        try:
            raw = get_today_metrics()
            state["metrics_raw"]      = raw
            state["metrics_rows"]     = format_metrics_table(raw)
            state["recent_sessions"]  = get_today_calendar()
        except Exception as exc:
            print(f"[SERGEANT] error refrescando metricas: {exc}")
        time.sleep(10)


def _start_monitoring():
    global _last_cam_present
    launch_dashboard(lambda: dict(state), _apply_goal)
    threading.Thread(target=_refresh_metrics, daemon=True).start()
    threading.Thread(target=_extract_and_set_keywords, args=(state["goal"],), daemon=True).start()
    if WEBCAM_ENABLED:
        threading.Thread(target=webcam.start, daemon=True).start()
    print(f"[SERGEANT] objetivo: {state['goal']}")
    print(f"[SERGEANT] monitoreando cada {POLL_INTERVAL_SECONDS}s\n")
    _consecutive_errors = 0
    _null_window_count  = 0
    while True:
        try:
            window = get_active_window()
            if window:
                _null_window_count = 0

                is_sergeant_self = (
                    window.process_name.lower() in ("python3.12.exe", "python.exe")
                    and (
                        "sergeant" in window.title.lower()
                        or window.title.lower() in ("tk", "")   # ventanas Tkinter internas (toast, etc.)
                    )
                )
                if is_sergeant_self:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                status, reason = classify(window, state["goal"])

                # Webcam: si está corriendo y no detecta cara → AFK = DISTRACTION
                if webcam.is_running():
                    cam_present, cam_reason = webcam.get_presence()
                    state["webcam_present"] = cam_present
                    state["webcam_reason"]  = cam_reason
                    if cam_present != _last_cam_present:
                        print(f"[WEBCAM] presente={cam_present} razon='{cam_reason}'")
                        _last_cam_present = cam_present
                    if cam_present is False and status != Status.DISTRACTION:
                        status = Status.DISTRACTION
                        reason = "AFK — sin presencia detectada"
                else:
                    state["webcam_present"] = None
                    state["webcam_reason"]  = "inactivo"
                    if _last_cam_present != "unset" and _last_cam_present is not None:
                        print("[WEBCAM] is_running()=False — override AFK deshabilitado")
                        _last_cam_present = None

                _update_state(window, status, reason)
                print(f"[{status.value:<11}] {window.title[:60]:<60}  |  {reason}")
            else:
                _null_window_count += 1
                if _null_window_count == 1 or _null_window_count % 10 == 0:
                    print(f"[SERGEANT] ventana activa no detectada (x{_null_window_count})")
            _consecutive_errors = 0
        except Exception as exc:
            _consecutive_errors += 1
            print(f"[SERGEANT] error en loop ({_consecutive_errors}): {exc}")
            if _consecutive_errors >= 10:
                print("[SERGEANT] demasiados errores consecutivos — reiniciando conteo tras pausa")
                _consecutive_errors = 0
                time.sleep(5)
        time.sleep(POLL_INTERVAL_SECONDS)


def main():
    print("[SERGEANT] iniciando...")
    init_db()
    close_open_sessions()

    skip_contract = "--skip-contract" in sys.argv

    if not skip_contract:
        _accepted = [False]
        def on_accept():
            _accepted[0] = True
        show_contract(on_accept=on_accept, on_reject=lambda: sys.exit(0))
        if not _accepted[0]:
            sys.exit(0)

    time.sleep(0.15)
    show_boot(state["goal"], TWITTER_ENABLED)
    gc.collect()
    time.sleep(0.3)
    _start_monitoring()


if __name__ == "__main__":
    main()
