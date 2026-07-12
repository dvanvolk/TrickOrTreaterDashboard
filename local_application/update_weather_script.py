#!/usr/bin/env python3
"""
Script to update weather status on the dashboard
Can be called manually or integrated with a weather API
"""

import requests
import sys
import os
import argparse

# Configuration
API_BASE_URL = os.environ.get('DASHBOARD_API_URL', 'http://localhost:5000')
API_KEY = os.environ.get('DASHBOARD_API_KEY', 'your-secure-api-key-here')

def update_weather(condition: str, temperature: float):
    """Update weather status on the dashboard"""
    url = f"{API_BASE_URL}/weather"
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'condition': condition,
        'temperature': temperature
    }
    
    try:
        print(f"Updating weather: {condition}, {temperature}°F...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Weather updated successfully")
            print(f"  Condition: {result.get('condition')}")
            print(f"  Temperature: {result.get('temperature')}°F")
            return True
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            try:
                error = response.json()
                print(f"  {error.get('error', 'Unknown error')}")
            except:
                print(f"  {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False

def get_weather():
    """Get current weather status from the dashboard"""
    url = f"{API_BASE_URL}/weather"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            weather = response.json()
            print(f"Current weather:")
            print(f"  Condition: {weather.get('condition')}")
            print(f"  Temperature: {weather.get('temperature')}°F")
            print(f"  Last updated: {weather.get('timestamp')}")
            return True
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Update weather status on dashboard")
    parser.add_argument('--get', action='store_true', help='Get current weather status')
    parser.add_argument('--condition', '-c', help='Weather condition (e.g., Clear, Cloudy, Rainy)')
    parser.add_argument('--temperature', '-t', type=float, help='Temperature in Fahrenheit')
    
    args = parser.parse_args()
    
    if args.get:
        success = get_weather()
    elif args.condition and args.temperature is not None:
        success = update_weather(args.condition, args.temperature)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python update_weather.py --condition Clear --temperature 72")
        print("  python update_weather.py -c Rainy -t 65")
        print("  python update_weather.py --get")
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
