"""Fetch weather from Home Assistant (or Open-Meteo) and push to the dashboard.

Provides ``fetch_local_weather(config)`` which returns a (condition, temperature_F) tuple,
reading a Home Assistant weather entity when ``ha_url``/``ha_token`` are configured and
falling back to Open-Meteo (``fetch_weather(lat, lon)``) otherwise or on failure.
``update_dashboard_weather(api_client, condition, temperature)`` POSTs to /weather.
Called by ``local_app.py``'s weather background thread.
"""
from __future__ import annotations

import logging
import os
from typing import Optional
import requests

LOGGER = logging.getLogger("local_app")

DEFAULT_HA_WEATHER_ENTITY = "weather.forecast_home"
# Back Yard Fence weather station; overrides the weather entity's (forecast) temperature
DEFAULT_HA_TEMPERATURE_ENTITY = "sensor.cotech_367959_220_temperature"

# Home Assistant weather entity states -> dashboard conditions (see VALID_CONDITIONS in app.py)
HA_CONDITION_MAP = {
    'sunny': 'Clear',
    'clear-night': 'Clear',
    'partlycloudy': 'Partly Cloudy',
    'cloudy': 'Cloudy',
    'fog': 'Fog',
    'rainy': 'Rain',
    'pouring': 'Rain',
    'hail': 'Rain',
    'snowy': 'Snow',
    'snowy-rainy': 'Snow',
    'lightning': 'Thunderstorm',
    'lightning-rainy': 'Thunderstorm',
    'windy': 'Windy',
    'windy-variant': 'Windy',
}


def fetch_local_weather(config: dict) -> tuple[Optional[str], Optional[float]]:
    """Fetch weather from Home Assistant if configured, else (or on failure) from Open-Meteo"""
    ha_url = config.get('ha_url') or os.environ.get('HA_URL')
    ha_token = config.get('ha_token') or os.environ.get('HA_TOKEN')
    if ha_url and ha_token:
        entity_id = config.get('ha_weather_entity') or os.environ.get('HA_WEATHER_ENTITY', DEFAULT_HA_WEATHER_ENTITY)
        temp_entity_id = (config.get('ha_temperature_entity')
                          or os.environ.get('HA_TEMPERATURE_ENTITY', DEFAULT_HA_TEMPERATURE_ENTITY))
        condition, temp = fetch_ha_weather(ha_url, ha_token, entity_id, temp_entity_id)
        if condition is not None and temp is not None:
            return condition, temp
        LOGGER.warning("Home Assistant weather unavailable, falling back to Open-Meteo")

    latitude = config.get('latitude')
    longitude = config.get('longitude')
    if not latitude or not longitude:
        return None, None
    return fetch_weather(latitude, longitude)


def fetch_ha_weather(ha_url: str, ha_token: str, entity_id: str,
                     temp_entity_id: Optional[str] = None) -> tuple[Optional[str], Optional[float]]:
    """Fetch current condition and temperature (°F) from Home Assistant.

    The condition comes from the weather entity. The temperature comes from
    ``temp_entity_id`` (a temperature sensor) when given and available, otherwise
    from the weather entity's own temperature attribute.
    """
    try:
        data = _get_ha_state(ha_url, ha_token, entity_id)
        condition = HA_CONDITION_MAP.get(data.get('state'), 'Unknown')

        temp = None
        if temp_entity_id:
            try:
                sensor = _get_ha_state(ha_url, ha_token, temp_entity_id)
                temp = _to_fahrenheit(float(sensor['state']),
                                      sensor.get('attributes', {}).get('unit_of_measurement'))
            except Exception as e:
                LOGGER.warning(f"{temp_entity_id} unavailable, using {entity_id} temperature: {e}")

        if temp is None:
            attributes = data.get('attributes', {})
            if attributes.get('temperature') is None:
                LOGGER.warning(f"{entity_id} has no temperature (state: {data.get('state')})")
                return None, None
            temp = _to_fahrenheit(float(attributes['temperature']), attributes.get('temperature_unit'))

        return condition, temp

    except Exception as e:
        LOGGER.warning(f"Error fetching weather from Home Assistant: {e}")
        return None, None


def _get_ha_state(ha_url: str, ha_token: str, entity_id: str) -> dict:
    """GET /api/states/<entity_id> from Home Assistant"""
    url = f"{ha_url.rstrip('/')}/api/states/{entity_id}"
    headers = {'Authorization': f'Bearer {ha_token}'}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def _to_fahrenheit(temp: float, unit: Optional[str]) -> float:
    if unit == '°C':
        return round(temp * 9 / 5 + 32, 1)
    return temp


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
        return "Fog"
    elif code in [51, 53, 55, 56, 57]:
        return "Drizzle"
    elif code in [61, 63, 65, 66, 67]:
        return "Rain"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "Snow"
    elif code in [80, 81, 82]:
        return "Rain"
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
    