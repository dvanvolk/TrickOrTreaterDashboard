# Trick-or-Treater Dashboard

A web application that tracks and displays live Halloween visitor counts. An Arduino-connected laptop sends button-press events to a remote Flask server; the dashboard displays real-time stats, charts, and a year-over-year comparison.

## Architecture

```
Arduino (serial) → local_app.py → HTTP API → app.py (Flask) → data/dashboard.db
                                                                      ↓
                                                            Browser (polls every 2s)
```

Two separate runtime components:

- **Remote server** (`app.py`) — Flask app running in Docker on a cloud host behind a Cloudflare tunnel. Owns all persistent data.
- **Local application** (`local_application/`) — runs on a laptop physically connected to the Arduino. Bridges the serial port to the remote API. See [`local_application/README.md`](local_application/README.md).

## Project Structure

```
├── app.py                        # Flask server entrypoint
├── db.py                         # SQLite layer (WAL mode, schema)
├── archive_script.py             # Aggregates a year's events into historical_data
├── validate_data.py              # Data integrity checks
├── backup_data.sh                # Server-side DB backup to git
├── simple_grpah.py               # Local graph generation for social media
├── requirements.txt              # Server dependencies
├── docker-compose.yml            # Production deployment
├── Dockerfile
├── .env.example                  # Copy to .env and fill in values
├── data/
│   ├── dashboard.db              # SQLite database (gitignored)
│   ├── dashboard_backup.sql      # SQL dump committed by backup_data.sh
│   ├── historical_data.json      # Hand-entered 2019-2023 data + legacy reference
│   └── weather.json              # Current weather (written by local app)
├── templates/
│   └── trickortreat_dashboard.html
├── static/
│   ├── css/dashboard.css
│   └── js/
│       ├── dashboard.js
│       └── chart-helpers.js
└── local_application/            # Serial-to-API bridge (see its own README)
```

## Server Setup

1. **Clone the repository and configure:**
   ```bash
   git clone <repository-url>
   cd TrickOrTreaterDashboard
   cp .env.example .env
   # Edit .env — set DASHBOARD_API_KEY and TUNNEL_TOKEN
   ```

2. **Run in production (Docker):**
   ```bash
   docker compose up -d
   ```

3. **Run in development:**
   ```bash
   pip install -r requirements.txt
   python app.py
   # Visit http://localhost:5000
   ```

The server requires `DASHBOARD_API_KEY` in the environment — it refuses to start without it.

## Halloween Night Workflow

### During the night
- Start the local application on the laptop connected to the Arduino (see `local_application/README.md`)
- Enable live mode from the dashboard controls
- Button 1 on the Arduino adds a visitor; Button 3 undoes the last entry

### End-of-night backup (on the server)
```bash
bash backup_data.sh
```
This dumps `data/dashboard.db` to `data/dashboard_backup.sql`, commits it, and pushes to git. The data volume is mounted so no Docker commands are needed.

### End-of-night graph generation (locally on Windows)
```bash
python simple_grpah.py
```
Queries the live API and generates two social-media-ready PNGs in the project root:
- `trickortreat_by_year.png` — all-time year-over-year bar chart
- `trickortreat_tonight.png` — 15-minute interval timeline for the current evening

Requires `local_application/config.json` with `api_url` and `api_key`.

## Post-Season Archiving

After Halloween, aggregate raw events into the historical data (used for year-over-year charts):

1. Validate data integrity:
   ```bash
   python validate_data.py
   ```

2. Archive the year (requires `DASHBOARD_API_KEY` in environment):
   ```bash
   python archive_script.py 2025
   ```
   This is idempotent — re-run with `--force` to overwrite an existing year.

3. Run the backup again to capture the archived data:
   ```bash
   bash backup_data.sh
   ```

Raw events in `dashboard.db` are never deleted — archiving only writes to the `historical_buckets` table.

## Configuration

| Variable | Where | Purpose |
|----------|-------|---------|
| `DASHBOARD_API_KEY` | `.env` / environment | Required. Authenticates all mutating API calls. |
| `TUNNEL_TOKEN` | `.env` | Cloudflare tunnel token for public HTTPS access. |

Generate a key: `python -c "import secrets; print(secrets.token_hex(32))"`
