# app.py - Remote server version
"""
Flask app for remote dashboard server
Receives data from local serial monitor via API
"""

from flask import Flask, render_template, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import json
import os
from datetime import datetime, timedelta
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

# Global state for live mode
live_mode = {
    'enabled': False,
    'start_time': None
}


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
    if not live_mode['enabled'] or not live_mode['start_time']:
        return 0
    return int((datetime.now() - live_mode['start_time']).total_seconds())


@app.route('/')
def index():
    """Serve dashboard HTML"""
    return render_template('trickortreat_dashboard.html')


@app.route('/live_status', methods=['GET'])
def get_live_status():
    """Get current live mode status"""
    return jsonify({
        'live': live_mode['enabled'],
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
        
        if desired and not live_mode['enabled']:
            # Turning live mode ON
            live_mode['enabled'] = True
            live_mode['start_time'] = datetime.now()
            logger.info("Live mode ENABLED")
        elif not desired and live_mode['enabled']:
            # Turning live mode OFF
            live_mode['enabled'] = False
            logger.info("Live mode DISABLED")
        
        return jsonify({
            'live': live_mode['enabled'],
            'elapsed_seconds': get_elapsed_seconds()
        })
    except Exception as e:
        logger.error(f"Error setting live mode: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/historical_data')
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
            
            # Fix invalid hours
            import re
            def fix_invalid_hour(match):
                hour = int(match.group(1))
                if hour >= 24:
                    return f"T{hour-24:02d}:"
                return match.group(0)
            
            timestamp_str = re.sub(r'T(\d{2}):', fix_invalid_hour, timestamp_str)
            
            if timestamp_str.endswith('Z'):
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.fromisoformat(timestamp_str)
            time_of_day = timestamp.strftime('%H:%M')
            
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
def get_detailed_historical():
    """Serve detailed per-entry historical data grouped by year.

    Returns a mapping of year -> list of entries (timestamp, count, year).
    This is used by the frontend to render per-arrival charts (minute level).
    """
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


@app.route('/current_data')
def get_current_data():
    """Serve current year's data for live updates"""
    try:
        if not live_mode['enabled']:
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
            'timestamp': datetime.now().isoformat(),
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
def get_stats():
    """Get current statistics"""
    try:
        data = load_data()
        current_year = datetime.now().year
        current_year_data = [e for e in data if e.get('year') == current_year]
        
        # Count recent entries (last 5 minutes)
        recent_time = datetime.now() - timedelta(minutes=5)
        recent_count = sum(1 for e in current_year_data 
                          if datetime.fromisoformat(e['timestamp']) > recent_time)
        
        return jsonify({
            'total_count': len(current_year_data),
            'recent_count': recent_count,
            'serial_connected': True,  # Always true for remote server
            'live_mode': live_mode['enabled']
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'live_mode': live_mode['enabled']
    })


if __name__ == '__main__':
    # For production, use a production WSGI server like gunicorn
    # gunicorn -w 4 -b 0.0.0.0:8000 app:app
    app.run(host='0.0.0.0', port=5000, debug=False)