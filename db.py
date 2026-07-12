"""Database layer for the TrickOrTreaterDashboard.

Provides SQLite access (WAL mode) replacing the JSON file + FileLock approach.
Import get_db / teardown_db in app.py; use get_db_direct in standalone scripts.
"""

import os
import sqlite3

from flask import g

DB_PATH = os.path.join('data', 'dashboard.db')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,
    count     INTEGER NOT NULL DEFAULT 1,
    year      INTEGER NOT NULL,
    is_test   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_year        ON events (year);
CREATE INDEX IF NOT EXISTS idx_events_year_istest ON events (year, is_test);

CREATE TABLE IF NOT EXISTS historical_buckets (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,
    count     INTEGER NOT NULL,
    year      INTEGER NOT NULL,
    UNIQUE(year, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_hist_year ON historical_buckets (year);
"""


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables and set WAL mode. Idempotent — safe to call on every startup."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    _configure(conn)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


def get_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Return the per-request connection stored on Flask g."""
    if 'db' not in g:
        g.db = _configure(sqlite3.connect(db_path))
    return g.db


def teardown_db(exception) -> None:
    """Close the per-request connection. Register with app.teardown_appcontext."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_db_direct(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a connection outside a Flask request context (migration / validate scripts)."""
    return _configure(sqlite3.connect(db_path))


def row_to_event_dict(row: sqlite3.Row) -> dict:
    """Convert an events row to the JSON shape the API has always returned.

    The 'test' key is present and True only for test entries — never present as False.
    """
    d = {'timestamp': row['timestamp'], 'count': row['count'], 'year': row['year']}
    if row['is_test']:
        d['test'] = True
    return d
