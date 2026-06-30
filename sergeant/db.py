import sqlite3
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def close_open_sessions():
    """Cierra sesiones que quedaron abiertas de un run anterior (crash o cierre forzado)."""
    conn = get_conn()
    conn.execute("UPDATE sessions SET end_time = start_time WHERE end_time IS NULL")
    conn.commit()
    conn.close()


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            window_title TEXT,
            process_name TEXT,
            status TEXT,
            goal TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_session(start_time, window_title, process_name, status, goal):
    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO sessions (start_time, window_title, process_name, status, goal) VALUES (?,?,?,?,?)",
        (start_time, window_title, process_name, status, goal)
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def close_session(row_id, end_time):
    conn = get_conn()
    conn.execute("UPDATE sessions SET end_time=? WHERE id=?", (end_time, row_id))
    conn.commit()
    conn.close()


def log_event(timestamp, event_type, detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO events (timestamp, event_type, detail) VALUES (?,?,?)",
        (timestamp, event_type, detail)
    )
    conn.commit()
    conn.close()


def get_today_sessions(date_str):
    """date_str: 'YYYY-MM-DD'"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT window_title, process_name, status, start_time, end_time FROM sessions WHERE start_time LIKE ?",
        (f"{date_str}%",)
    ).fetchall()
    conn.close()
    return rows


def get_metrics(date_str):
    """Retorna {app: segundos} para el día dado."""
    rows = get_today_sessions(date_str)
    metrics = {}
    for title, process, status, start, end in rows:
        if not end:
            continue
        fmt = "%Y-%m-%d %H:%M:%S"
        try:
            delta = int((datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds())
        except Exception:
            delta = 0
        key = process or title[:30]
        metrics[key] = metrics.get(key, 0) + delta
    return metrics
