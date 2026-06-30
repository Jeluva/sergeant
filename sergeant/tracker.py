from datetime import datetime
from db import insert_session, close_session, get_metrics, get_today_sessions
from config import PRODUCTIVE_PROCESSES

_current_session_id = None
_current_window = None
_session_start = None


def fmt_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def on_window_change(window_title, process_name, status, goal):
    global _current_session_id, _current_window, _session_start

    now = fmt_now()
    if _current_session_id is not None:
        close_session(_current_session_id, now)
    _current_session_id = insert_session(now, window_title, process_name, status, goal)
    _current_window = window_title
    _session_start = datetime.now()


def get_today_metrics():
    return get_metrics(today_str())


def get_today_calendar():
    return get_today_sessions(today_str())


def seconds_to_hms(s):
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def format_metrics_table(metrics: dict) -> list:
    """
    Retorna lista de (app, bar_str, time_str, pct, is_productive).
    El dashboard colorea según is_productive.
    """
    if not metrics:
        return []
    total = sum(metrics.values())
    rows = []
    for app, secs in sorted(metrics.items(), key=lambda x: -x[1]):
        bar_len = int((secs / total) * 22) if total else 0
        bar = "█" * bar_len + "░" * (22 - bar_len)
        pct = int(secs / total * 100) if total else 0
        is_prod = app.lower() in PRODUCTIVE_PROCESSES
        rows.append((app, bar, seconds_to_hms(secs), pct, is_prod))
    return rows
