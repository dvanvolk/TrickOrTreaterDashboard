#!/usr/bin/env python3
"""
Script to archive a year's data to historical data
Run this after Halloween to prepare for next year
"""

import requests
import sys
import os
from datetime import datetime

# Configuration - update these or set environment variables
API_BASE_URL = os.environ.get('DASHBOARD_API_URL', 'https://yourdomain.com')
API_KEY = os.environ.get('DASHBOARD_API_KEY', 'your-secure-api-key-here')

def archive_year(year: int):
    """Archive data for a specific year"""
    url = f"{API_BASE_URL}/archive_year"
    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {'year': year}
    
    try:
        print(f"Archiving data for year {year}...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Success: {result.get('message')}")
            print(f"  Intervals archived: {result.get('intervals_archived')}")
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

def main():
    if len(sys.argv) > 1:
        try:
            year = int(sys.argv[1])
        except ValueError:
            print("Error: Year must be a number")
            print("Usage: python archive_year.py [YEAR]")
            print("Example: python archive_year.py 2024")
            sys.exit(1)
    else:
        # Default to current year
        year = datetime.now().year
        print(f"No year specified, using current year: {year}")
    
    success = archive_year(year)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
