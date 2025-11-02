# app.py - Remote server version
"""
Flask app for remote dashboard server
Receives data from local serial monitor via API
"""

from flask import Flask, render_template, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
from functools import wraps
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Configuration
API_KEY = os.environ.get('DASHBOARD_API_KEY', 'your-secure-api-key-here')
DATA_FILE = 'data/trickortreat_data.json'
HISTORICAL_DATA_FILE = 'data/historical_data.json'

# Rate limiting to prevent abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Create data directory
os.makedirs('data', exist_ok=True)

# File-backed live mode state (shared across worker processes)
LIVE_MODE_FILE = os.path.join('data', 'live_mode.json')

# In-memory cache (kept for convenience; persistent source of truth is the file)
live_mode = {
    'enabled': False,
    'start_time': None,
    'owner': None
}

def initialize_live_mode():
    """Initialize live mode state from file."""
    try:
        state = load_live_mode_from_file()
        live_mode.clear()
        live_mode.update(state)
        logger.info("Initialized live mode from file: enabled=%s, owner=%s",
                   state.get('enabled'), state.get('owner'))
    except Exception as e:
        logger.error("Failed to initialize live mode state: %s", e)

# Initialize state when module loads - each worker will do this on startup
initialize_live_mode()

def load_live_mode_from_file():
    """Load live mode dict from the JSON file. Returns a dict with keys 'enabled', 'start_time' (ISO str or None), 'owner'."""
    try:
        if os.path.exists(LIVE_MODE_FILE):
            with open(LIVE_MODE_FILE, 'r') as lf:
                data = json.load(lf)
                # Ensure keys exist and types are correct
                state = {
                    'enabled': bool(data.get('enabled', False)),
                    'start_time': data.get('start_time'),
                    'owner': data.get('owner')
                }
                # Validate start_time if present
                if state['start_time']:
                    try:
                        datetime.fromisoformat(state['start_time'])
                    except (ValueError, TypeError):
                        logger.warning("Invalid start_time in live mode file, resetting")
                        state['start_time'] = None
                # If enabled but no start time, add one
                if state['enabled'] and not state['start_time']:
                    state['start_time'] = datetime.now().isoformat()
                    # Re-save to fix the missing start time
                    save_live_mode_to_file(state)
                return state
        else:
            # Create initial state file if it doesn't exist
            initial_state = {
                'enabled': False,
                'start_time': None,
                'owner': None
            }
            save_live_mode_to_file(initial_state)
            return initial_state
    except Exception as e:
        logger.exception('Failed to load live mode file: %s', e)
        # On error, force disabled state for safety
        return {
            'enabled': False,
            'start_time': None,
            'owner': None
        }


def save_live_mode_to_file(state: dict):
    """Atomically save live mode dict to the JSON file."""
    try:
        tmp = LIVE_MODE_FILE + '.tmp'
        with open(tmp, 'w') as lf:
            json.dump({
                'enabled': bool(state.get('enabled', False)),
                'start_time': state.get('start_time'),
                'owner': state.get('owner')
            }, lf)
        # atomic replace
        os.replace(tmp, LIVE_MODE_FILE)
        logger.debug("Saved live mode state to file: enabled=%s, owner=%s",
                   state.get('enabled'), state.get('owner'))
    except Exception as e:
        logger.exception('Failed to save live mode file: %s', e)
        raise  # Re-raise to ensure caller knows save failed


def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == API_KEY:
            return f(*args, **kwargs)
        logger.warning(f"Unauthorized API access attempt from {request.remote_addr}")
        return jsonify({'error': 'Unauthorized - Invalid API key'}), 401
    return decorated_function


def load_data() -> List[Dict[str, Any]]:
    """Load current year data from file"""
    if not os.path.exists(DATA_FILE):
        return []
    
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return []


def save_data(data: List[Dict[str, Any]]):
    """Save data to file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def get_elapsed_seconds() -> int:
    """Get seconds elapsed since live mode was enabled"""
    state = load_live_mode_from_file()
    if not state.get('enabled') or not state.get('start_time'):
        return 0
    try:
        start = datetime.fromisoformat(state.get('start_time'))
        return int((datetime.now() - start).total_seconds())
    except Exception:
        return 0


@app.route('/')
def index():
    """Serve dashboard HTML"""
    return render_template('trickortreat_dashboard.html')


@app.route('/live_status', methods=['GET'])
@limiter.limit("1000 per hour")  # Allow frequent polling - ~16 per minute
def get_live_status():
    """Get current live mode status"""
    state = load_live_mode_from_file()
    return jsonify({
        'live': state.get('enabled', False),
        'elapsed_seconds': get_elapsed_seconds()
    })


@app.route('/set_live', methods=['POST'])
@require_api_key
@limiter.limit("30 per minute")
def set_live():
    """Set live mode on/off"""
    try:
        body = request.get_json(silent=True) or {}
        desired = bool(body.get('live', False))
        # Owner handling: either provided in JSON 'owner' or in header 'X-Client-Id'
        owner = body.get('owner') or request.headers.get('X-Client-Id')
        
        logger.info("Processing set_live request: desired=%s, owner=%s", desired, owner)

        # Load authoritative state from file
        current = load_live_mode_from_file()
        logger.debug("Current state from file: enabled=%s, owner=%s", 
                    current.get('enabled'), current.get('owner'))

        new_state = current.copy()  # Work with a new copy to avoid modifying current

        # If enabling, record owner (if provided)
        if desired and not current.get('enabled'):
            new_state.update({
                'enabled': True,
                'start_time': datetime.now().isoformat(),
                'owner': owner
            })
            logger.info("Live mode will be ENABLED (owner=%s)", owner)
        elif not desired and current.get('enabled'):
            # Only allow disabling if owner matches or no owner set
            current_owner = current.get('owner')
            if current_owner and owner and current_owner != owner:
                logger.warning("Rejecting live disable from owner=%s (current owner=%s)", owner, current_owner)
                return jsonify({
                    'live': current.get('enabled', False),
                    'elapsed_seconds': get_elapsed_seconds(),
                    'error': 'Cannot disable - owned by different client'
                })
            else:
                new_state.update({
                    'enabled': False,
                    'start_time': None,
                    'owner': None
                })
                logger.info("Live mode will be DISABLED (requested by=%s)", owner)
        else:
            # No change needed
            logger.debug("No state change needed (desired=%s, current enabled=%s)", 
                        desired, current.get('enabled'))
            return jsonify({
                'live': current.get('enabled', False),
                'elapsed_seconds': get_elapsed_seconds()
            })

        # Persist new state to file first
        try:
            save_live_mode_to_file(new_state)
        except Exception as e:
            logger.error("Failed to save live mode state: %s", e)
            return jsonify({
                'error': 'Failed to save state',
                'live': current.get('enabled', False),
                'elapsed_seconds': get_elapsed_seconds()
            }), 500

        # Only update in-memory cache after successful file save
        live_mode.clear()
        live_mode.update(new_state)
        
        # Verify the change was saved
        verify = load_live_mode_from_file()
        logger.info("Live mode change completed: enabled=%s, owner=%s", 
                   verify.get('enabled'), verify.get('owner'))
        
        return jsonify({
            'live': verify.get('enabled', False),
            'elapsed_seconds': get_elapsed_seconds()
        })
    except Exception as e:
        logger.error(f"Error setting live mode: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/historical_data')
@limiter.limit("200 per hour")  # Less frequent, but still reasonable
def get_historical_data():
    """Serve historical data grouped by year and time of day"""
    try:
        if not os.path.exists(HISTORICAL_DATA_FILE):
            return jsonify({})
        
        with open(HISTORICAL_DATA_FILE, 'r') as f:
            data = json.load(f)
        
        # Group data by year and time of day
        grouped_data = {}
        for entry in data:
            year = entry['year']
            timestamp_str = entry['timestamp']
            
            # Parse timestamp - handle both UTC and legacy local timestamps
            try:
                if timestamp_str.endswith('Z') or '+' in timestamp_str or timestamp_str.count('-') > 2:
                    # UTC timestamp - parse and convert to local time
                    if timestamp_str.endswith('Z'):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    
                    # Convert UTC to local time (Eastern)
                    # For October 31, use EDT offset (UTC-4)
                    from datetime import timedelta
                    local_offset = timedelta(hours=-4)  # EDT
                    local_time = timestamp + local_offset
                else:
                    # Legacy local timestamp without timezone
                    local_time = datetime.fromisoformat(timestamp_str)
                
                time_of_day = local_time.strftime('%H:%M')
                
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {timestamp_str}: {e}")
                continue
            
            if year not in grouped_data:
                grouped_data[year] = {}
            
            if time_of_day not in grouped_data[year]:
                grouped_data[year][time_of_day] = []
            
            grouped_data[year][time_of_day].append(entry['count'])
        
        # Calculate averages
        processed_data = {}
        for year, time_data in grouped_data.items():
            processed_data[year] = {}
            for time_slot, counts in time_data.items():
                processed_data[year][time_slot] = {
                    'average': sum(counts) / len(counts),
                    'total': sum(counts),
                    'count': len(counts)
                }
        
        return jsonify(processed_data)
    except Exception as e:
        logger.error(f"Error loading historical data: {e}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/detailed_historical')
@limiter.limit("200 per hour")  # Less frequent
def get_detailed_historical():
    """Serve detailed per-entry historical data grouped by year."""
    try:
        if not os.path.exists(DATA_FILE):
            return jsonify({})

        with open(DATA_FILE, 'r') as f:
            data = json.load(f)

        grouped = {}
        for entry in data:
            year = entry.get('year')
            if year not in grouped:
                grouped[year] = []
            grouped[year].append(entry)

        # Sort entries per year by timestamp
        for year, entries in grouped.items():
            try:
                entries.sort(key=lambda e: e.get('timestamp'))
            except Exception:
                pass

        return jsonify(grouped)
    except Exception as e:
        logger.error(f"Error loading detailed historical data: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(RateLimitExceeded)
def handle_rate_limit(e):
    """Return JSON for rate-limited responses instead of HTML so clients can parse errors."""
    # e.description may contain details depending on limiter setup
    return jsonify({'error': 'rate_limited', 'message': str(e)}), 429


@app.route('/current_data')
@limiter.limit("1000 per hour")  # Allow frequent updates during live mode
def get_current_data():
    """Serve current year's data for live updates"""
    try:
        # Use authoritative file state to check live mode
        current = load_live_mode_from_file()
        if not current.get('enabled', False):
            return jsonify([])
        
        data = load_data()
        current_year = datetime.now().year
        current_year_data = [entry for entry in data if entry.get('year') == current_year]
        return jsonify(current_year_data)
    except Exception as e:
        logger.error(f"Error loading current data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/add_trick_or_treater', methods=['POST'])
@require_api_key
@limiter.limit("100 per minute")  # Allow frequent updates during busy times
def add_trick_or_treater():
    """Add a trick-or-treater count"""
    try:
        data = load_data()
        
        new_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'count': 1,
            'year': datetime.now().year
        }
        
        data.append(new_entry)
        save_data(data)
        
        logger.info(f"Trick-or-treater added. Total count: {len(data)}")
        
        return jsonify({
            'success': True,
            'message': 'Trick-or-treater added',
            'total_count': len(data)
        })
    except Exception as e:
        logger.error(f"Error adding trick-or-treater: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/undo_last_entry', methods=['POST'])
@require_api_key
@limiter.limit("30 per minute")
def undo_last_entry():
    """Undo the last trick-or-treater entry"""
    try:
        data = load_data()
        
        if not data:
            return jsonify({'error': 'No entries to undo'}), 400
        
        removed_entry = data.pop()
        save_data(data)
        
        logger.info(f"Last entry removed: {removed_entry}")
        
        return jsonify({
            'success': True,
            'message': 'Last entry removed',
            'removed_entry': removed_entry,
            'total_count': len(data)
        })
    except Exception as e:
        logger.error(f"Error undoing entry: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/upload_batch', methods=['POST'])
@require_api_key
@limiter.limit("10 per hour")  # Limited for batch uploads
def upload_batch():
    """Upload a batch of data (for syncing pending local data)"""
    try:
        body = request.get_json()
        batch_data = body.get('data', [])
        
        if not batch_data:
            return jsonify({'error': 'No data provided'}), 400
        
        existing_data = load_data()
        existing_data.extend(batch_data)
        save_data(existing_data)
        
        logger.info(f"Batch upload: {len(batch_data)} entries added")
        
        return jsonify({
            'success': True,
            'message': f'{len(batch_data)} entries uploaded',
            'total_count': len(existing_data)
        })
    except Exception as e:
        logger.error(f"Error uploading batch: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats')
@limiter.limit("1000 per hour")  # Allow frequent stat checks
def get_stats():
    """Get current statistics"""
    try:
        data = load_data()
        if not data:
            # Return empty stats if no data
            current = load_live_mode_from_file()
            return jsonify({
                'total_count': 0,
                'recent_count': 0,
                'serial_connected': True,
                'live_mode': current.get('enabled', False)
            })
        
        current_year = datetime.now().year
        current_year_data = [e for e in data if e.get('year') == current_year]
        
        # Count recent entries (last 5 minutes)
        recent_time_utc = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent_count = 0
        
        for e in current_year_data:
            timestamp_str = e.get('timestamp')
            if not timestamp_str:
                continue
                
            try:
                # Parse timestamp - handle multiple formats
                if timestamp_str.endswith('Z'):
                    # UTC with Z suffix
                    entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                elif '+' in timestamp_str or timestamp_str.count('-') > 2:
                    # Has timezone offset
                    entry_time = datetime.fromisoformat(timestamp_str)
                else:
                    # No timezone info - assume UTC
                    entry_time = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                
                # Ensure timezone-aware for comparison
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                elif entry_time.tzinfo != timezone.utc:
                    entry_time = entry_time.astimezone(timezone.utc)
                
                if entry_time > recent_time_utc:
                    recent_count += 1
                    
            except (ValueError, AttributeError) as e:
                logger.debug(f"Skipping entry with unparseable timestamp: {timestamp_str}, error: {e}")
                continue
        
        # Get authoritative live mode state from file
        current = load_live_mode_from_file()
        return jsonify({
            'total_count': len(current_year_data),
            'recent_count': recent_count,
            'serial_connected': True,
            'live_mode': current.get('enabled', False)
        })
    except Exception as e:
        logger.exception(f"Error getting stats: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'total_count': 0,
            'recent_count': 0,
            'serial_connected': True,
            'live_mode': False
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    current = load_live_mode_from_file()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'live_mode': current.get('enabled', False)
    })

@app.route('/archive_year', methods=['POST'])
@require_api_key
@limiter.limit("10 per hour")
def archive_year():
    """Archive current year data to historical data (call this after Halloween to prepare for next year)"""
    try:
        body = request.get_json(silent=True) or {}
        year = body.get('year')
        
        if not year:
            return jsonify({'error': 'Year parameter required'}), 400
        
        # Load current data
        current_data = load_data()
        year_data = [entry for entry in current_data if entry.get('year') == year]
        
        if not year_data:
            return jsonify({'error': f'No data found for year {year}'}), 404
        
        # Load historical data
        if os.path.exists(HISTORICAL_DATA_FILE):
            with open(HISTORICAL_DATA_FILE, 'r') as f:
                historical = json.load(f)
        else:
            historical = []
        
        # Group by 15-minute intervals and aggregate
        interval_data = {}
        for entry in year_data:
            timestamp_str = entry['timestamp']
            try:
                # Parse timestamp
                if timestamp_str.endswith('Z'):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.fromisoformat(timestamp_str)
                
                # Convert to local time (EDT for October 31)
                local_offset = timedelta(hours=-4)  # EDT
                local_time = timestamp + local_offset
                
                # Round to 15-minute interval
                minutes = (local_time.minute // 15) * 15
                interval_time = local_time.replace(minute=minutes, second=0, microsecond=0)
                interval_key = interval_time.isoformat()
                
                if interval_key not in interval_data:
                    interval_data[interval_key] = 0
                interval_data[interval_key] += entry.get('count', 1)
                
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {timestamp_str}: {e}")
                continue
        
        # Add aggregated data to historical
        for interval_time, count in interval_data.items():
            historical.append({
                'timestamp': interval_time,
                'count': count,
                'year': year
            })
        
        # Save historical data
        with open(HISTORICAL_DATA_FILE, 'w') as f:
            json.dump(historical, f, indent=2)
        
        logger.info(f"Archived {len(interval_data)} intervals for year {year}")
        
        return jsonify({
            'success': True,
            'message': f'Archived {len(interval_data)} time intervals for year {year}',
            'intervals_archived': len(interval_data)
        })
        
    except Exception as e:
        logger.error(f"Error archiving year: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/current_year_data')
@limiter.limit("1000 per hour")
def get_current_year_data():
    """Get current year's data regardless of live mode status - used for summary generation"""
    try:
        data = load_data()
        current_year = datetime.now().year
        current_year_data = [entry for entry in data if entry.get('year') == current_year]
        return jsonify(current_year_data)
    except Exception as e:
        logger.error(f"Error loading current year data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/weather', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def weather():
    """Get or set weather status for the current session"""
    WEATHER_FILE = os.path.join('data', 'weather.json')
    
    if request.method == 'POST':
        # Only allow setting weather with API key
        api_key = request.headers.get('X-API-Key')
        if not (api_key and api_key == API_KEY):
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            body = request.get_json(silent=True) or {}
            weather_data = {
                'condition': body.get('condition', 'Clear'),
                'temperature': body.get('temperature', 0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            with open(WEATHER_FILE, 'w') as f:
                json.dump(weather_data, f, indent=2)
            
            logger.info(f"Weather updated: {weather_data}")
            return jsonify(weather_data)
        except Exception as e:
            logger.error(f"Error updating weather: {e}")
            return jsonify({'error': str(e)}), 500
    
    else:  # GET
        try:
            if os.path.exists(WEATHER_FILE):
                with open(WEATHER_FILE, 'r') as f:
                    return jsonify(json.load(f))
            else:
                return jsonify({
                    'condition': 'Unknown',
                    'temperature': 0,
                    'timestamp': None
                })
        except Exception as e:
            logger.error(f"Error loading weather: {e}")
            return jsonify({'error': str(e)}), 500


def create_app():
    """Factory function to create the Flask app instance.
    This is useful for gunicorn and other WSGI servers."""
    # Ensure live mode is initialized
    initialize_live_mode()
    return app

if __name__ == '__main__':
    # For production, use a production WSGI server like gunicorn
    # gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
    create_app().run(host='0.0.0.0', port=5000, debug=False)