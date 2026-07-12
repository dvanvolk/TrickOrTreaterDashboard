#!/usr/bin/env python3
"""
One-shot migration: import trickortreat_data.json and historical_data.json
into data/dashboard.db (SQLite, WAL mode).

Usage:
    python migrate_to_sqlite.py [--db PATH] [--force]

Options:
    --db PATH    Path to the SQLite database (default: data/dashboard.db)
    --force      Re-run even if the database already has rows

On success the source JSON files are renamed to .migrated (not deleted).
Safe to re-run with --force; imports nothing from app.py or db.py.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

LIVE_JSON = os.path.join('data', 'trickortreat_data.json')
HIST_JSON = os.path.join('data', 'historical_data.json')
DEFAULT_DB = os.path.join('data', 'dashboard.db')

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


def normalize_ts(ts: str) -> str:
    """Normalize an ISO 8601 timestamp to the canonical '+00:00' form."""
    return datetime.fromisoformat(ts.replace('Z', '+00:00')).isoformat()


def open_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=DEFAULT_DB, help='SQLite database path')
    parser.add_argument('--force', action='store_true',
                        help='Re-migrate even if DB already has rows')
    args = parser.parse_args()

    # ── Preflight ────────────────────────────────────────────────────────────
    for path in (LIVE_JSON, HIST_JSON):
        if not os.path.exists(path):
            sys.exit(f"ERROR: {path} not found")

    with open(LIVE_JSON) as f:
        live_source = json.load(f)
    with open(HIST_JSON) as f:
        hist_source = json.load(f)

    print(f"Source: {len(live_source)} events, {len(hist_source)} historical buckets")

    conn = open_db(args.db)

    existing_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    existing_hist   = conn.execute("SELECT COUNT(*) FROM historical_buckets").fetchone()[0]

    if (existing_events or existing_hist) and not args.force:
        conn.close()
        sys.exit(
            f"ERROR: {args.db} already has {existing_events} events and "
            f"{existing_hist} historical buckets.\n"
            f"Pass --force to re-migrate (existing rows will be deleted first)."
        )

    if args.force and (existing_events or existing_hist):
        print(f"--force: dropping {existing_events} events and {existing_hist} buckets")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM historical_buckets")
        conn.commit()

    # ── Migrate events ────────────────────────────────────────────────────────
    print("\nMigrating events...")
    event_rows = []
    for entry in live_source:
        try:
            ts = normalize_ts(entry['timestamp'])
        except Exception as e:
            print(f"  WARN: skipping entry with bad timestamp {entry.get('timestamp')!r}: {e}")
            continue
        event_rows.append((
            ts,
            int(entry.get('count', 1)),
            int(entry['year']),
            1 if entry.get('test') else 0,
        ))

    conn.executemany(
        "INSERT INTO events (timestamp, count, year, is_test) VALUES (?,?,?,?)",
        event_rows,
    )
    conn.commit()

    migrated_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if migrated_events != len(event_rows):
        print(f"  WARN: inserted {migrated_events} rows but expected {len(event_rows)}")
    else:
        print(f"  OK: {migrated_events} events inserted")

    # ── Migrate historical buckets ────────────────────────────────────────────
    print("\nMigrating historical buckets...")
    hist_rows = []
    for entry in hist_source:
        try:
            ts = normalize_ts(entry['timestamp'])
        except Exception as e:
            print(f"  WARN: skipping bucket with bad timestamp {entry.get('timestamp')!r}: {e}")
            continue
        hist_rows.append((ts, int(entry['count']), int(entry['year'])))

    conn.executemany(
        "INSERT OR IGNORE INTO historical_buckets (timestamp, count, year) VALUES (?,?,?)",
        hist_rows,
    )
    conn.commit()

    migrated_hist = conn.execute("SELECT COUNT(*) FROM historical_buckets").fetchone()[0]
    ignored = len(hist_rows) - migrated_hist
    if ignored:
        print(f"  WARN: {ignored} duplicate bucket(s) ignored (UNIQUE constraint)")
    print(f"  OK: {migrated_hist} historical buckets inserted")

    # ── Per-year summary ──────────────────────────────────────────────────────
    print("\nPer-year summary:")
    events_by_year = defaultdict(int)
    for r in conn.execute("SELECT year, COUNT(*) AS n FROM events GROUP BY year"):
        events_by_year[r['year']] = r['n']
    hist_by_year = defaultdict(int)
    for r in conn.execute(
        "SELECT year, SUM(count) AS total FROM historical_buckets GROUP BY year"
    ):
        hist_by_year[r['year']] = r['total']

    all_years = sorted(set(events_by_year) | set(hist_by_year))
    for yr in all_years:
        ev  = events_by_year.get(yr, 0)
        hv  = hist_by_year.get(yr, '-')
        print(f"  {yr}: {ev} raw events, {hv} historical count total")

    conn.close()

    # ── Rename source files (not delete) ─────────────────────────────────────
    print()
    for path in (LIVE_JSON, HIST_JSON):
        dest = path + '.migrated'
        os.rename(path, dest)
        print(f"Renamed {path} -> {dest}")

    print("\nMigration complete.")


if __name__ == '__main__':
    main()
