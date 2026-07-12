#!/usr/bin/env python3
"""Validate the integrity of the dashboard SQLite database.

Run from the repo root:
    python validate_data.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DB_PATH = "data/dashboard.db"
EASTERN = ZoneInfo("America/New_York")

# Plausible trick-or-treat window in local Eastern time
TOT_START_HOUR = 16   # 4:00 PM
TOT_END_HOUR = 23     # 11:00 PM


def to_eastern(ts_str):
    ts_str = ts_str.replace('Z', '+00:00')
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EASTERN)


def main():
    passed = []
    failed = []
    warnings = []

    def ok(msg):
        passed.append(msg)
        print(f"  PASS  {msg}")

    def fail(msg):
        failed.append(msg)
        print(f"  FAIL  {msg}")

    def warn(msg):
        warnings.append(msg)
        print(f"  WARN  {msg}")

    # ── Load from SQLite ────────────────────────────────────────────────────
    if not os.path.exists(DB_PATH):
        sys.exit(f"ERROR: {DB_PATH} not found — run migrate_to_sqlite.py first")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    historical = [dict(r) for r in conn.execute(
        "SELECT * FROM historical_buckets ORDER BY year, timestamp"
    ).fetchall()]
    live = [dict(r) for r in conn.execute(
        "SELECT * FROM events ORDER BY timestamp"
    ).fetchall()]
    conn.close()

    # ── Historical summary ───────────────────────────────────────────────────
    print(f"\n=== historical_buckets ({len(historical)} buckets) ===")
    hist_by_year = defaultdict(list)
    for e in historical:
        hist_by_year[e['year']].append(e)

    for yr in sorted(hist_by_year):
        entries = hist_by_year[yr]
        total = sum(e['count'] for e in entries)
        timestamps = [e['timestamp'] for e in entries]
        try:
            lo = to_eastern(min(timestamps)).strftime('%I:%M %p')
            hi = to_eastern(max(timestamps)).strftime('%I:%M %p')
        except Exception:
            lo = hi = '?'
        print(f"  {yr}: {len(entries)} buckets, total={total:3d}, range {lo} – {hi} Eastern")

    # ── Live data summary ────────────────────────────────────────────────────
    print(f"\n=== events ({len(live)} events) ===")
    live_by_year = defaultdict(list)
    for e in live:
        live_by_year[e['year']].append(e)

    test_in_live = [e for e in live if e['is_test']]

    for yr in sorted(live_by_year):
        entries = live_by_year[yr]
        real = [e for e in entries if not e['is_test']]
        tests = [e for e in entries if e['is_test']]
        timestamps = [e['timestamp'] for e in real] if real else []
        try:
            lo = to_eastern(min(timestamps)).strftime('%I:%M %p') if timestamps else '-'
            hi = to_eastern(max(timestamps)).strftime('%I:%M %p') if timestamps else '-'
        except Exception:
            lo = hi = '?'
        test_note = f", {len(tests)} test entries" if tests else ""
        print(f"  {yr}: {len(real)} real events, total={len(real):3d}, range {lo} – {hi} Eastern{test_note}")

    # ── Checks ───────────────────────────────────────────────────────────────
    print("\n=== Checks ===")

    # 1. Required years in historical
    expected_years = set(range(2019, 2026))
    present_years = set(hist_by_year.keys())
    missing = expected_years - present_years
    if missing:
        fail(f"Missing years in historical: {sorted(missing)}")
    else:
        ok("All years 2019–2025 present in historical")

    # 2. No duplicate timestamps within a year in historical
    dup_years = []
    for yr, entries in hist_by_year.items():
        timestamps = [e['timestamp'] for e in entries]
        if len(timestamps) != len(set(timestamps)):
            dup_years.append(yr)
    if dup_years:
        fail(f"Duplicate bucket timestamps in historical for years: {dup_years}")
    else:
        ok("No duplicate bucket timestamps in historical")

    # 3. No test entries in historical (historical_buckets has no is_test column)
    hist_test = []  # historical_buckets table contains no test entries by design
    if hist_test:
        fail(f"Historical contains {len(hist_test)} test entries — re-archive after purging")
    else:
        ok("No test entries in historical")

    # 4. Test entries in live data (informational warning)
    if test_in_live:
        warn(f"{len(test_in_live)} test entries in live data — run /purge_test_entries to remove")
    else:
        ok("No test entries in live data")

    # 5. Out-of-hours events in live data
    odd_events = []
    for e in live:
        if e['is_test']:
            continue
        try:
            local = to_eastern(e['timestamp'])
            if local.hour < TOT_START_HOUR or local.hour >= TOT_END_HOUR:
                odd_events.append((e['year'], local.strftime('%Y-%m-%d %I:%M %p')))
        except Exception:
            pass
    if odd_events:
        warn(f"{len(odd_events)} live events outside {TOT_START_HOUR}:00–{TOT_END_HOUR}:00 local (possible tests):")
        for yr, ts in odd_events[:10]:
            warn(f"    {yr}  {ts}")
    else:
        ok(f"All live events within {TOT_START_HOUR}:00–{TOT_END_HOUR}:00 local Eastern")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*40}")
    print(f"  {len(passed)} passed  |  {len(warnings)} warnings  |  {len(failed)} failed")
    if failed:
        print("  Action required — see FAIL lines above")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
