"""Local application entrypoint to manage serial port and send API calls.

This script wires the serial monitor to the Dashboard API client.
It provides a small CLI and reads configuration from environment variables.

It uses the existing `LocalSerialMonitor` in this folder which expects
an `api_client.DashboardAPIClient` to be importable. A lightweight
`api_client.py` wrapper is provided in this folder to re-export the
implementation from `remote_api_client.py`.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from typing import Optional
import json
import threading

# Try package-relative imports (when run as a module), but fall back to
# plain imports so this file can also be executed directly as a script
# (e.g. `python local_app.py -h`) from the `local_application` folder.
try:
    from .local_serial_monitor import LocalSerialMonitor
    from .dashboard_serial_integration import DashboardSerialIntegration
    from .fetch_weather_api import fetch_weather, update_dashboard_weather
except Exception:
    # Fallback for direct script execution
    from local_serial_monitor import LocalSerialMonitor
    from dashboard_serial_integration import DashboardSerialIntegration
    from fetch_weather_api import fetch_weather, update_dashboard_weather

LOGGER = logging.getLogger("local_app")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Local app: serial -> dashboard API bridge")
    p.add_argument("--config", help="Path to a JSON config file to load defaults from", default=None)

    # We'll set defaults after optionally loading a config file in main().
    p.add_argument("--port", help="Serial port (e.g. COM3 or loop://)")
    p.add_argument("--api-url", help="Dashboard API base URL")
    p.add_argument("--api-key", help="Dashboard API key")
    p.add_argument("--baudrate", type=int)
    p.add_argument("--mode", choices=["monitor", "integration"],
                   help="Run mode: 'monitor' uses LocalSerialMonitor (sends API calls). 'integration' uses DashboardSerialIntegration (local JSON integration).")
    return p.parse_args()


def start_weather_updates(api_client, config: dict, should_stop) -> None:
    """Run weather updates in a background thread with better rate limit handling"""
    LOGGER.info("Starting weather update thread")
    
    latitude = config.get('latitude')
    longitude = config.get('longitude')
    
    if not latitude or not longitude:
        LOGGER.error("Weather updates disabled: Missing latitude/longitude in config")
        return
    
    def weather_update_loop():
        # Track consecutive failures to implement exponential backoff
        consecutive_failures = 0
        max_failures_before_backoff = 3
        
        while not should_stop:
            try:
                condition, temperature = fetch_weather(latitude, longitude)
                
                if condition is not None and temperature is not None:
                    # Try to send to dashboard
                    if update_dashboard_weather(api_client, condition, temperature):
                        LOGGER.info(f"Weather updated: {condition}, {temperature}°F")
                        consecutive_failures = 0  # Reset on success
                    else:
                        consecutive_failures += 1
                        LOGGER.warning(f"Failed to send weather update to dashboard (failure {consecutive_failures})")
                        
                        # If we've had too many failures, back off more aggressively
                        if consecutive_failures >= max_failures_before_backoff:
                            backoff_minutes = min(consecutive_failures * 5, 30)  # Cap at 30 minutes
                            LOGGER.warning(f"Multiple failures detected, backing off for {backoff_minutes} minutes")
                            for _ in range(backoff_minutes * 2):  # Check every 30 seconds
                                if should_stop:
                                    break
                                time.sleep(30)
                            continue
                else:
                    LOGGER.warning("Failed to fetch weather from API")
                    consecutive_failures += 1
                
                # Normal sleep interval: 15 minutes
                # But check should_stop every 30 seconds for clean shutdown
                for _ in range(30):  # 15 minutes = 30 * 30 seconds
                    if should_stop:
                        break
                    time.sleep(30)
                    
            except Exception as e:
                consecutive_failures += 1
                LOGGER.error(f"Error in weather update loop: {e}")
                
                # Exponential backoff on errors
                backoff_seconds = min(60 * consecutive_failures, 300)  # Cap at 5 minutes
                LOGGER.info(f"Backing off for {backoff_seconds} seconds after error")
                for _ in range(backoff_seconds // 30):
                    if should_stop:
                        break
                    time.sleep(30)
    
    weather_thread = threading.Thread(target=weather_update_loop, daemon=True)
    weather_thread.start()
    return weather_thread

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = parse_args()

    # Load config file if provided or if a default exists in this folder
    config = {}
    # If CLI specified a config path, use it first
    config_path_candidates = []
    if args.config:
        config_path_candidates.append(args.config)
    # local_application/config.json
    config_dir = os.path.dirname(__file__)
    config_path_candidates.append(os.path.join(config_dir, 'config.json'))
    # project root config.json
    config_path_candidates.append(os.path.join(os.path.dirname(config_dir), 'config.json'))

    for cfg_path in config_path_candidates:
        try:
            if cfg_path and os.path.exists(cfg_path):
                with open(cfg_path, 'r') as cf:
                    config = json.load(cf)
                LOGGER.info("Loaded config from %s", cfg_path)
                break
        except Exception:
            LOGGER.debug("Failed to load config from %s", cfg_path, exc_info=True)

    # Normalize config keys (support older names like 'serial_port')
    cfg = {}
    cfg['port'] = config.get('port') or config.get('serial_port') or config.get('serial')
    cfg['api_url'] = config.get('api_url') or config.get('base_url')
    cfg['api_key'] = config.get('api_key') or config.get('apiKey')
    cfg['baudrate'] = config.get('baudrate') or config.get('baud_rate')
    cfg['mode'] = config.get('mode')

    # Determine final runtime values with precedence: CLI > config.json > env > hardcoded default
    port = args.port or cfg.get('port') or os.environ.get('SERIAL_PORT', 'COM3')
    api_url = args.api_url or cfg.get('api_url') or os.environ.get('DASHBOARD_API_URL', 'https://yourdomain.com')
    api_key = args.api_key or cfg.get('api_key') or os.environ.get('DASHBOARD_API_KEY', '')
    baudrate = args.baudrate or cfg.get('baudrate') or int(os.environ.get('SERIAL_BAUD', '115200'))
    mode = args.mode or cfg.get('mode') or os.environ.get('LOCAL_APP_MODE', 'monitor')

    LOGGER.info("Starting local_app in '%s' mode", mode)

    # Initialize API client (used by LocalSerialMonitor).
    # Import here to avoid requiring network-related dependencies when
    # the module is only imported for help/inspection.
    try:
        from .api_client import DashboardAPIClient
    except Exception:
        from api_client import DashboardAPIClient

    # Use the resolved values (CLI > config > env > defaults) when creating the client
    api_client = DashboardAPIClient(base_url=api_url, api_key=api_key)

    should_stop = False
    monitor = None

    def _signal_handler(sig, frame):
        nonlocal should_stop
        LOGGER.info("Received signal to stop (%s)", sig)
        should_stop = True
        # If the monitor is running, request it to exit cleanly
        try:
            if monitor is not None:
                LOGGER.info("Requesting monitor to exit")
                monitor.exit_app()
        except Exception:
            LOGGER.debug("Monitor exit request failed", exc_info=True)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    weather_thread = None
    try:
        # Start weather updates in both monitor and integration modes
        weather_thread = start_weather_updates(api_client, config, should_stop)
        
        if mode == "monitor":
            monitor = LocalSerialMonitor(port=port, api_client=api_client, baudrate=baudrate, local_backup=True)
            # Try to sync any pending data left from previous runs
            monitor.sync_pending_data()

            # Run until stopped
            monitor.run()

        else:  # integration mode (local JSON file + radio interface)
            # DashboardSerialIntegration currently writes to local JSON when buttons pressed.
            # If you want to forward those events to the remote API, extend DashboardSerialIntegration
            # to accept an api_client and call it from __count_btn_callback / __undo_btn_callback.
            integration = DashboardSerialIntegration(serial_port=port)
            LOGGER.info("Dashboard serial integration running (press Ctrl+C to exit)")

            # Wait until signaled. Use a portable sleep loop for Windows compatibility.
            try:
                while not should_stop:
                    time.sleep(0.5)
                # If a monitor was created elsewhere, request it to exit.
                if monitor is not None:
                    monitor.exit_app()
            finally:
                integration.cleanup()

    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    except Exception:
        LOGGER.exception("Unexpected error in local_app")
        return 2

    LOGGER.info("local_app exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())