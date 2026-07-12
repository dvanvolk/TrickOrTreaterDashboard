# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the remote server:**
```
python app.py
# Production (multi-worker):
gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
```

**Run the local application (serial-to-API bridge):**
```
python -m local_application.local_app
# With test mode (button presses send test entries, not real counts):
python -m local_application.local_app --test-mode
# Explicit args:
python -m local_application.local_app --port COM3 --api-url https://cnytrickortreatcounter.com/ --api-key <key>
```

**Archive a year's data after Halloween:**
```
python archive_script.py 2025
```

**Validate data integrity:**
```
python validate_data.py
```

**Install dependencies:**
```
# Server:
pip install -r requirements.txt
# Local application only:
pip install -r requirements-local.txt
```

There are no automated tests.

## Architecture

This project has two separate runtime components that communicate over HTTP:

### 1. Remote Flask Server (`app.py`)
Runs on a cloud/remote host (deployed via Docker + Cloudflare tunnel). Serves the web dashboard and owns all persistent state. Key responsibilities:
- Serves the single-page dashboard at `/`
- Persists trick-or-treater events to `data/trickortreat_data.json`
- Persists 15-min aggregated historical data to `data/historical_data.json`
- Tracks live mode state in `data/live_mode.json` (file-backed to survive multi-worker restarts — always call `load_live_mode_from_file()`, never trust the in-memory `live_mode` dict as authoritative)
- Tracks weather in `data/weather.json`
- `modify_data(fn)` is the safe way to mutate `trickortreat_data.json` — it holds `DATA_LOCK` (a `FileLock`) across the full read-modify-write cycle to prevent concurrent-worker corruption
- All mutating endpoints require `X-API-Key` header (checked with `hmac.compare_digest`); rate limiting via `flask-limiter` keyed on `CF-Connecting-IP`
- Live mode has an ownership model: a client that enables it sets an `owner` field; only the same owner (or an anonymous client) can disable it

**Key endpoints beyond CRUD:**
- `/countdown` — returns `{target, is_halloween}` for the client-side Halloween countdown
- `/add_test_entry` / `/purge_test_entries` — test mode support; test entries are excluded from `/stats` and `/archive_year`
- `/archive_year` — aggregates raw events into 15-min buckets in `historical_data.json`; idempotent (returns 409 if year exists unless `force: true`); skips `test: true` entries

### 2. Local Application (`local_application/`)
Runs on a laptop physically connected to the Arduino hardware. Bridges the serial port to the remote API. Key files:
- `local_app.py` — entrypoint; reads `config.json` or CLI args; spawns a background weather update thread; supports `--test-mode` / `TEST_MODE` env var
- `local_serial_monitor.py` (`LocalSerialMonitor`) — reads raw serial lines, calls the remote API for each button press; in test mode calls `/add_test_entry` instead of `/add_trick_or_treater`
- `serial_interface.py` (`RadioInterface`) — thin pyserial wrapper; parses `Button: N` and `Heart: N` messages from the Arduino
- `remote_api_client.py` (`DashboardAPIClient`) — HTTP client with retry/backoff; re-exported via `api_client.py`
- `fetch_weather_api.py` — fetches weather from Open-Meteo (no API key needed) using lat/lon from config, then POSTs to `/weather`

**Button mapping (Arduino → action):**
- Button 1 → add trick-or-treater (or test entry in test mode)
- Button 2 → unused
- Button 3 → undo last entry

### 3. Frontend (`templates/`, `static/`)
Single HTML page. JavaScript polls the server every 2 seconds while live mode is active. `loadCountdownTarget()` is called once on load to fetch the Halloween target date from `/countdown`; `tickCountdown()` runs every second client-side.

Key polling endpoints:
- `/live_status` — determines whether to show/hide the stats grid and countdown
- `/current_data` — raw entries for the current year (only returned when live)
- `/detailed_historical` — per-entry data for all years (detailed year charts)
- `/historical_data` — 15-min aggregated data (year-over-year chart)
- `/weather` — current weather condition and temperature

`dashboard.js` maintains all chart state. `chart-helpers.js` provides `formatTime()`, `toISOStringLocal()`, and `applyChartDefaults()` (sets global Chart.js dark-theme palette — call before `setupCharts()`). Charts are Chart.js instances in the `charts` object keyed by name (`minute`, `timeline`, `yearComparison`, `yearStats`, `peakActivity`, `detailedYear`, `detailedScatter`). Year colors are generated dynamically via `getYearColor(year)` from `YEAR_COLOR_PALETTE` — no static map to update when a new year is added. CSS custom properties are defined in `:root` in `dashboard.css`; use `var(--accent)`, `var(--accent-teal)`, `var(--card-bg)` etc. throughout.

### Data architecture (critical)
- **`trickortreat_data.json`** — permanent source of truth; one entry per visitor with UTC timestamp (2024+). **Never delete or truncate this file.** It is never cleared after archiving.
- **`historical_data.json`** — derived display data; 15-min bucketed counts for all years. 2019–2023 are hand-entered; 2024+ are derived via `/archive_year`. This file is what the year-over-year chart reads.
- Test entries (`"test": true`) in `trickortreat_data.json` are excluded from stats counts and archiving. Clean them up with `POST /purge_test_entries`.

### Data flow
```
Arduino (serial) → local_app.py → DashboardAPIClient (HTTP) → app.py → data/*.json
                                                                    ↓
                                                          Browser (polls /current_data, etc.)
```

### Configuration
**Server:** `DASHBOARD_API_KEY` environment variable is **required** — the server refuses to start without it. Copy `.env.example` to `.env` and fill in values; `docker-compose` auto-loads `.env`.

**Local app:** `local_application/config.json` holds the API URL, API key, serial port, baud rate, run mode, lat/lon for weather, and optional `test_mode` flag. Config precedence: CLI args > `config.json` > env vars (`DASHBOARD_API_URL`, `DASHBOARD_API_KEY`, `SERIAL_PORT`, `TEST_MODE`) > hardcoded defaults. `python-dotenv` is loaded at startup so a `.env` file in the working directory is also picked up.

### Post-Halloween workflow
1. Run `python validate_data.py` to confirm data integrity.
2. Run `python archive_script.py <YEAR>` to aggregate raw events into 15-min buckets in `historical_data.json`. The script requires `DASHBOARD_API_KEY` in the environment or `.env`.
3. Raw events in `trickortreat_data.json` are preserved — do not delete them.
