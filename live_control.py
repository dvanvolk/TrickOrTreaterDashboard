"""In-process live-mode state for the Flask server.

Tracks whether the dashboard is in "live" mode (counter visible, stats polling active).
Imported by app.py; state lives in module-level globals for the lifetime of a worker process.
Note: in multi-worker production (gunicorn), live_mode.json is the authoritative source —
always call load_live_mode_from_file() rather than trusting these in-memory values directly.

Can also be run as a CLI to toggle live mode via the local API:
  python live_control.py --Enable
  python live_control.py --Disable
"""
import argparse
import requests

_live_status = False
_live_start_time = None
from datetime import datetime

def is_live():
    """Return the current live status"""
    return _live_status

def set_live(status):
    """Set the live status"""
    global _live_status
    global _live_start_time
    _live_status = status
    if status:
        # Start or resume live session start time
        if _live_start_time is None:
            _live_start_time = datetime.utcnow()
        print("Live status enabled. Counter is now visible.")
    else:
        _live_start_time = None
        print("Live status disabled. Counter is now hidden.")

def toggle_live():
    """Toggle the live status and return the new status"""
    global _live_status
    global _live_start_time
    _live_status = not _live_status
    if _live_status:
        if _live_start_time is None:
            _live_start_time = datetime.utcnow()
        print("Live status enabled. Counter is now visible.")
    else:
        _live_start_time = None
        print("Live status disabled. Counter is now hidden.")
    return _live_status

def get_elapsed_seconds():
    """Return elapsed live seconds if live, otherwise 0"""
    if not _live_status or _live_start_time is None:
        return 0
    delta = datetime.utcnow() - _live_start_time
    return int(delta.total_seconds())

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enable or disable live status")
    parser.add_argument('--Enable', action='store_true')
    parser.add_argument('--Disable', dest='Enable', action='store_false')
    
    arg = parser.parse_args()

    requests.post('http://127.0.0.1:5000/set_live', json={'live': arg.Enable})
    print(f"Initial status: {is_live()}")
    