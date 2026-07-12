# Local Application

Runs on a Windows laptop physically connected to the Arduino counter hardware. Bridges the Arduino's serial output to the remote dashboard API.

## How It Works

The Arduino emits serial messages when buttons are pressed:
- `Button: 1` → add a visitor (or test entry in test mode)
- `Button: 3` → undo last entry

`local_app.py` reads these messages and POSTs to the remote API. A background thread also polls Open-Meteo every 15 minutes for current weather and updates the dashboard.

## Files

| File | Purpose |
|------|---------|
| `local_app.py` | Entrypoint — reads config, wires serial monitor to API client |
| `local_serial_monitor.py` | Preferred mode: reads serial, calls remote API per button press |
| `serial_interface.py` | Thin pyserial wrapper; parses `Button: N` and `Heart: N` messages |
| `remote_api_client.py` | HTTP client with retry/backoff |
| `api_client.py` | Re-exports `DashboardAPIClient` from `remote_api_client.py` |
| `fetch_weather_api.py` | Fetches weather from Open-Meteo (no API key), POSTs to `/weather` |
| `update_weather_script.py` | CLI utility to manually override weather on the dashboard |
| `config.json` | Local config file — **not checked into git** (contains API key) |

## Setup

```bash
pip install -r requirements-local.txt
```

## Configuration

Create `local_application/config.json` (copy the example below). This file is gitignored because it contains the API key.

```json
{
  "api_url": "https://cnytrickortreatcounter.com/",
  "api_key": "YOUR_API_KEY_HERE",
  "serial_port": "COM3",
  "baudrate": 115200,
  "mode": "monitor",
  "latitude": 43.0292,
  "longitude": -76.0033
}
```

Config precedence (highest to lowest): CLI args → `config.json` → environment variables → hardcoded defaults.

| Config key | Env var | Default | Description |
|-----------|---------|---------|-------------|
| `api_url` | `DASHBOARD_API_URL` | — | Remote dashboard URL |
| `api_key` | `DASHBOARD_API_KEY` | — | API key for authenticated requests |
| `serial_port` | `SERIAL_PORT` | `COM3` | Arduino serial port |
| `baudrate` | — | `115200` | Serial baud rate |
| `test_mode` | `TEST_MODE` | `false` | If true, button 1 adds test entries (excluded from stats) |
| `latitude` / `longitude` | — | — | Used for weather fetching |

## Running

```bash
# Normal mode — reads from config.json
python -m local_application.local_app

# Test mode — button presses add test entries, not real counts
python -m local_application.local_app --test-mode

# Explicit args
python -m local_application.local_app --port COM3 --api-url https://cnytrickortreatcounter.com/ --api-key <key>
```

Run from the project root, not from inside the `local_application/` folder.

Press `Ctrl+C` to exit cleanly.

## Manually Overriding Weather

If the automatic weather fetch is wrong, you can update it manually:

```bash
# Set via environment variables
set DASHBOARD_API_URL=https://cnytrickortreatcounter.com/
set DASHBOARD_API_KEY=<key>

python local_application/update_weather_script.py --condition Clear --temperature 58
python local_application/update_weather_script.py --get
```

## Button Mapping

| Arduino Button | Action |
|---------------|--------|
| Button 1 | Add trick-or-treater (or test entry in test mode) |
| Button 2 | Unused |
| Button 3 | Undo last entry |
