# api_client.py
"""
Client for communicating with remote dashboard API
Replace the base_url and api_key with your actual values
"""

import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DashboardAPIClient:
    """Client for sending data to remote dashboard server"""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        """
        Initialize API client
        
        Args:
            base_url: Base URL of your remote server (e.g., 'https://yourdomain.com')
            api_key: Secret API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {endpoint}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code} for {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {e}")
            return None
    
    def set_live(self, live: bool) -> Optional[Dict[str, Any]]:
        """
        Enable/disable live mode on dashboard
        
        Args:
            live: True to enable live mode, False to disable
            
        Returns:
            Response dict with 'live' and 'elapsed_seconds' keys, or None on error
        """
        logger.info(f"Setting live mode to: {live}")
        return self._make_request('POST', '/set_live', json={'live': live})
    
    def add_trick_or_treater(self) -> Optional[Dict[str, Any]]:
        """
        Add a trick-or-treater count
        
        Returns:
            Response dict with success message, or None on error
        """
        logger.info("Adding trick-or-treater")
        return self._make_request('POST', '/add_trick_or_treater')
    
    def undo_last_entry(self) -> Optional[Dict[str, Any]]:
        """
        Undo the last trick-or-treater entry
        
        Returns:
            Response dict with success message, or None on error
        """
        logger.info("Undoing last entry")
        return self._make_request('POST', '/undo_last_entry')
    
    def get_live_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current live mode status
        
        Returns:
            Dict with 'live' (bool) and 'elapsed_seconds' (int), or None on error
        """
        return self._make_request('GET', '/live_status')
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get current statistics
        
        Returns:
            Dict with 'total_count', 'recent_count', 'serial_connected', or None on error
        """
        return self._make_request('GET', '/stats')
    
    def upload_data_batch(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Upload a batch of trick-or-treater data
        
        Args:
            data: List of data entries with 'timestamp', 'count', 'year' keys
            
        Returns:
            Response dict with success info, or None on error
        """
        logger.info(f"Uploading batch of {len(data)} entries")
        return self._make_request('POST', '/upload_batch', json={'data': data})
    
    def health_check(self) -> bool:
        """
        Check if server is reachable
        
        Returns:
            True if server responds, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/live_status", timeout=5)
            return response.status_code == 200
        except:
            return False


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = DashboardAPIClient(
        base_url='https://yourdomain.com',  # Change to your domain
        api_key='your-secure-api-key-here'   # Change to your API key
    )
    
    # Check server health
    if client.health_check():
        print("✓ Server is reachable")
        
        # Enable live mode
        result = client.set_live(True)
        if result:
            print(f"✓ Live mode enabled: {result}")
        
        # Add a trick-or-treater
        result = client.add_trick_or_treater()
        if result:
            print(f"✓ Trick-or-treater added: {result}")
        
        # Get stats
        stats = client.get_stats()
        if stats:
            print(f"✓ Current stats: {stats}")
    else:
        print("✗ Server is not reachable")