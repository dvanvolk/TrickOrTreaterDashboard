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

# Try package-relative imports (when run as a module), but fall back to
# plain imports so this file can also be executed directly as a script
# (e.g. `python local_app.py -h`) from the `local_application` folder.
try:
    from .local_serial_monitor import LocalSerialMonitor
    from .dashboard_serial_integration import DashboardSerialIntegration
except Exception:
    # Fallback for direct script execution
    from local_serial_monitor import LocalSerialMonitor
    from dashboard_serial_integration import DashboardSerialIntegration

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

    def _signal_handler(sig, frame):
        nonlocal should_stop
        LOGGER.info("Received signal to stop (%s)", sig)
        should_stop = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
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