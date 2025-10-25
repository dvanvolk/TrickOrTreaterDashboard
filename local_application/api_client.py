"""Compatibility wrapper so modules that import `api_client` find DashboardAPIClient.

This file re-exports the implementation from `remote_api_client.py` which
contains the full HTTP client implementation.
"""
try:
    from .remote_api_client import DashboardAPIClient
except Exception:
    # Fallback for direct script execution
    from remote_api_client import DashboardAPIClient
    
__all__ = ["DashboardAPIClient"]
