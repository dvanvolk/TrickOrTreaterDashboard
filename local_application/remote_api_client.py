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
import time

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
        """Make HTTP request with error handling, retries and backoff.

        Retries are applied for transient errors like timeouts, connection
        failures and server (5xx) responses. 429 (Too Many Requests) is
        honored by checking the Retry-After header when present.
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        max_retries = kwargs.pop('retries', 3)
        backoff_factor = kwargs.pop('backoff_factor', 0.3)

        attempt = 1
        while attempt <= max_retries:
            try:
                # Avoid logging potentially large bodies; show helpful debug info
                safe_kwargs = {k: v for k, v in kwargs.items() if k not in ('data', 'json')}
                logger.debug("HTTP %s %s (attempt %d) %s", method, url, attempt, safe_kwargs)

                response = self.session.request(method, url, **kwargs)

                # Handle 429 Too Many Requests specifically
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    delay = backoff_factor * (2 ** (attempt - 1))
                    if retry_after:
                        try:
                            ra = int(retry_after)
                            delay = max(delay, ra)
                        except Exception:
                            # non-integer Retry-After (HTTP-date) - ignore parse error
                            pass
                    logger.warning("Received 429 for %s %s; backing off %.1fs (Retry-After=%s)", method, endpoint, delay, retry_after)
                    # consume body for debugging if small
                    try:
                        body = response.text
                        logger.debug("429 body: %s", body[:400])
                    except Exception:
                        pass
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Retry on 5xx server errors
                if 500 <= response.status_code < 600:
                    logger.warning("Server error %d for %s %s", response.status_code, method, endpoint)
                    if attempt < max_retries:
                        time.sleep(backoff_factor * (2 ** (attempt - 1)))
                        attempt += 1
                        continue
                    # else fall through and raise

                response.raise_for_status()

                # Parse JSON safely
                try:
                    return response.json()
                except ValueError:
                    logger.warning("Non-JSON response for %s %s: %s", method, url, (response.text or '')[:400])
                    return None

            except requests.exceptions.Timeout as e:
                logger.warning("Timeout on attempt %d for %s %s: %s", attempt, method, endpoint, e)
                if attempt >= max_retries:
                    logger.exception("Request timeout (final) for %s %s", method, endpoint)
                    return None
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                attempt += 1
                continue
            except requests.exceptions.ConnectionError as e:
                logger.warning("Connection error on attempt %d for %s %s: %s", attempt, method, endpoint, e)
                if attempt >= max_retries:
                    logger.exception("Connection error (final) for %s %s", method, endpoint)
                    return None
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
                attempt += 1
                continue
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 'unknown'
                logger.error("HTTP error %s for %s %s: %s", status, method, endpoint, e)
                return None
            except Exception as e:
                logger.exception("Unexpected error for %s %s: %s", method, endpoint, e)
                return None

        logger.error("Exceeded max retries (%d) for %s %s", max_retries, method, endpoint)
        return None
    
    def set_live(self, live: bool, owner: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Enable/disable live mode on dashboard
        
        Args:
            live: True to enable live mode, False to disable
            
        Returns:
            Response dict with 'live' and 'elapsed_seconds' keys, or None on error
        """
        logger.info(f"Setting live mode to: {live} (owner={owner})")
        body = {'live': live}
        if owner:
            body['owner'] = owner
        return self._make_request('POST', '/set_live', json=body)
    
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
            logger.debug("Health check: contacting %s", f"{self.base_url}/live_status")
            response = self.session.get(f"{self.base_url}/live_status", timeout=5)
            if response.status_code == 429:
                logger.warning("Health check: server returned 429 Too Many Requests")
                return False
            response.raise_for_status()
            # Prefer to check JSON if possible, else accept 200 OK
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    _ = response.json()
                    return True
                except Exception:
                    logger.warning("Health check returned non-JSON body despite content-type header")
                    return False
            return response.status_code == 200
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            logger.debug("Health check exception", exc_info=True)
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