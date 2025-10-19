from flask import Flask, render_template, jsonify
import live_control
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('trickortreat_dashboard.html')

@app.route('/live_status', methods=['GET'])
def get_live_status():
    return jsonify({'live': live_control.is_live()})

@app.route('/toggle_live', methods=['POST'])
def toggle_live():
    live_control.toggle_live()
    return jsonify({'live': live_control.is_live()})

@app.route('/historical_data')
def get_historical_data():
    """Serve historical data grouped by year and time of day for proper year-over-year comparison"""
    try:
        with open('data/historical_data.json', 'r') as f:
            data = json.load(f)
        
        # Group data by year and time of day
        grouped_data = {}
        for entry in data:
            year = entry['year']
            # Extract time of day (HH:MM format)
            # Handle both formats: with and without 'Z' suffix
            timestamp_str = entry['timestamp']
            
            # Fix invalid hours (24, 25, etc. should be 00, 01, etc.)
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
                # Assume local time if no timezone info
                timestamp = datetime.fromisoformat(timestamp_str)
            time_of_day = timestamp.strftime('%H:%M')
            
            if year not in grouped_data:
                grouped_data[year] = {}
            
            if time_of_day not in grouped_data[year]:
                grouped_data[year][time_of_day] = []
            
            grouped_data[year][time_of_day].append(entry['count'])
        
        # Calculate averages for each time slot
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
        return jsonify({'error': str(e)}), 500

@app.route('/current_data')
def get_current_data():
    """Serve current year's data for live updates"""
    try:
        with open('data/trickortreat_data.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)