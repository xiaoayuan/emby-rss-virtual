import os
import sqlite3
from typing import List, Dict, Any

DB_PATH = os.getenv("APP_DB", "/data/app.db")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'rss',
              rss_url TEXT,
              platform TEXT,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              target_subdir TEXT NOT NULL,
              source_ids TEXT NOT NULL,
              include_keywords TEXT DEFAULT '',
              exclude_keywords TEXT DEFAULT '',
              max_items INTEGER NOT NULL DEFAULT 100,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
              k TEXT PRIMARY KEY,
              v TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS run_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_at TEXT DEFAULT CURRENT_TIMESTAMP,
              summary TEXT
            )
            """
        )


def list_sources() -> List[Dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT * FROM sources ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def create_source(name: str, kind: str, rss_url: str, platform: str):
    with conn() as c:
        c.execute(
            "INSERT INTO sources(name, kind, rss_url, platform, enabled) VALUES(?,?,?,?,1)",
            (name.strip(), kind.strip() or "rss", (rss_url or "").strip(), (platform or "").strip()),
        )


def toggle_source(source_id: int):
    with conn() as c:
        c.execute("UPDATE sources SET enabled = CASE enabled WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (source_id,))


def delete_source(source_id: int):
    with conn() as c:
        c.execute("DELETE FROM sources WHERE id=?", (source_id,))


def list_rules() -> List[Dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT * FROM rules ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def create_rule(name: str, target_subdir: str, source_ids: str, include_keywords: str, exclude_keywords: str, max_items: int):
    with conn() as c:
        c.execute(
            "INSERT INTO rules(name, target_subdir, source_ids, include_keywords, exclude_keywords, max_items, enabled) VALUES(?,?,?,?,?,?,1)",
            (name.strip(), target_subdir.strip(), source_ids.strip(), include_keywords.strip(), exclude_keywords.strip(), max(1, int(max_items))),
        )


def toggle_rule(rule_id: int):
    with conn() as c:
        c.execute("UPDATE rules SET enabled = CASE enabled WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (rule_id,))


def delete_rule(rule_id: int):
    with conn() as c:
        c.execute("DELETE FROM rules WHERE id=?", (rule_id,))


def get_setting(key: str, default: str = "") -> str:
    with conn() as c:
        row = c.execute("SELECT v FROM app_settings WHERE k=?", (key,)).fetchone()
    return row["v"] if row else default


def set_setting(key: str, value: str):
    with conn() as c:
        c.execute("INSERT INTO app_settings(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value))


def append_run_log(summary: str):
    with conn() as c:
        c.execute("INSERT INTO run_logs(summary) VALUES(?)", (summary,))


def list_run_logs(limit: int = 20):
    with conn() as c:
        rows = c.execute("SELECT * FROM run_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
