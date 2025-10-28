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
import requests

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


def fetch_weather(latitude: float, longitude: float) -> tuple[Optional[str], Optional[float]]:
    """Fetch weather from Open-Meteo API"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current': 'temperature_2m,weather_code',
        'temperature_unit': 'fahrenheit',
        'timezone': 'auto'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current = data.get('current', {})
        temp = current.get('temperature_2m', 0)
        weather_code = current.get('weather_code', 0)
        
        # Convert WMO weather code to simple condition
        condition = weather_code_to_condition(weather_code)
        
        return condition, temp
        
    except Exception as e:
        LOGGER.warning(f"Error fetching weather: {e}")
        return None, None


def weather_code_to_condition(code: int) -> str:
    """Convert WMO weather code to simple condition string"""
    if code == 0:
        return "Clear"
    elif code in [1, 2, 3]:
        return "Partly Cloudy"
    elif code in [45, 48]:
        return "Foggy"
    elif code in [51, 53, 55, 56, 57]:
        return "Drizzle"
    elif code in [61, 63, 65, 66, 67]:
        return "Rainy"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "Snowy"
    elif code in [80, 81, 82]:
        return "Showers"
    elif code in [95, 96, 99]:
        return "Thunderstorm"
    else:
        return "Unknown"


def update_dashboard_weather(api_client, condition: str, temperature: float) -> bool:
    """Update weather on the dashboard"""
    try:
        result = api_client._make_request('POST', '/weather', json={
            'condition': condition,
            'temperature': temperature
        })
        return result is not None
    except Exception as e:
        LOGGER.warning(f"Failed to update weather: {e}")
        return False
    