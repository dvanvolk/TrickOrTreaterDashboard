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

# Use package-relative imports so this module can be imported as
# `local_application.local_app` and still resolve sibling modules.
from .local_serial_monitor import LocalSerialMonitor
from .dashboard_serial_integration import DashboardSerialIntegration
from .api_client import DashboardAPIClient

LOGGER = logging.getLogger("local_app")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Local app: serial -> dashboard API bridge")
    p.add_argument("--port", help="Serial port (e.g. COM3 or loop://)", default=os.environ.get("SERIAL_PORT", "COM3"))
    p.add_argument("--api-url", help="Dashboard API base URL", default=os.environ.get("DASHBOARD_API_URL", "https://yourdomain.com"))
    p.add_argument("--api-key", help="Dashboard API key", default=os.environ.get("DASHBOARD_API_KEY", ""))
    p.add_argument("--baudrate", type=int, default=int(os.environ.get("SERIAL_BAUD", "115200")))
    p.add_argument("--mode", choices=["monitor", "integration"], default=os.environ.get("LOCAL_APP_MODE", "monitor"),
                   help="Run mode: 'monitor' uses LocalSerialMonitor (sends API calls). 'integration' uses DashboardSerialIntegration (local JSON integration).")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = parse_args()

    LOGGER.info("Starting local_app in '%s' mode", args.mode)

    # Initialize API client (used by LocalSerialMonitor)
    api_client = DashboardAPIClient(base_url=args.api_url, api_key=args.api_key)

    should_stop = False

    def _signal_handler(sig, frame):
        nonlocal should_stop
        LOGGER.info("Received signal to stop (%s)", sig)
        should_stop = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        if args.mode == "monitor":
            monitor = LocalSerialMonitor(port=args.port, api_client=api_client, baudrate=args.baudrate, local_backup=True)
            # Try to sync any pending data left from previous runs
            monitor.sync_pending_data()

            # Run until stopped
            monitor.run()

        else:  # integration mode (local JSON file + radio interface)
            # DashboardSerialIntegration currently writes to local JSON when buttons pressed.
            # If you want to forward those events to the remote API, extend DashboardSerialIntegration
            # to accept an api_client and call it from __count_btn_callback / __undo_btn_callback.
            integration = DashboardSerialIntegration(serial_port=args.port)
            LOGGER.info("Dashboard serial integration running (press Ctrl+C to exit)")

            # Wait until signaled. Use a portable sleep loop for Windows compatibility.
            try:
                while not should_stop:
                    time.sleep(0.5)
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