#!/bin/bash
set -e

DUMP_PATH="data/dashboard_backup.sql"

echo "Dumping SQLite database to $DUMP_PATH..."
sqlite3 data/dashboard.db .dump > "$DUMP_PATH"

echo "Committing backup to Git..."
git add "$DUMP_PATH"
git commit -m "Backup dashboard.db ($(date '+%Y-%m-%d'))"
git push origin main

echo "Backup complete!"
