# -----------------------------------------------------------
# Dashboard Serial Integration
# Integrates the serial interface with the dashboard to add trick-or-treaters
# when the button is pressed on the serial device
#
# (C) 2023 Daniel VanVolkinburg 
# Released under GNU Public License (GPL)
# email dvanvolk@ieee.org
# -----------------------------------------------------------

import json
import threading
import time
from datetime import datetime
# Import RadioInterface robustly so this module can be imported either as
# a package (package-relative imports) or run directly as a script from the
# `local_application` folder (plain imports). This mirrors patterns used
# elsewhere in the project to avoid "attempted relative import with no
# known parent package" errors.
try:
    from .serial_interface import RadioInterface
except Exception:
    try:
        from serial_interface import RadioInterface
    except Exception:
        RadioInterface = None

class DashboardSerialIntegration:
    def __init__(self, serial_port="COM7"):
        """Initialize the serial integration with the dashboard"""
        self.serial_port = serial_port
        self.serial_radio = RadioInterface()
        self.current_data = []
        self.data_lock = threading.Lock()
        
        # Set up button callbacks
        button_callbacks = [
            self.__count_btn_callback,  # Button 1: Add trick-or-treater
            None,                       # Button 2: Not used
            self.__undo_btn_callback    # Button 3: Undo last entry
        ]
        
        # Start the serial interface
        if RadioInterface is None:
            raise RuntimeError("RadioInterface could not be imported; cannot start serial integration")

        self.serial_radio.start(self.serial_port, button_callbacks=button_callbacks)
        print(f"Serial interface started on {self.serial_port}")
        
    def __count_btn_callback(self):
        """Callback when the count button is pressed - add a new trick-or-treater"""
        now = datetime.now()
        timestamp = now.isoformat(timespec='microseconds')  # Local time with timezone info
        new_entry = {
            "timestamp": timestamp,
            "count": 1,
            "year": now.year
        }
        
        with self.data_lock:
            self.current_data.append(new_entry)
            self.__save_current_data()
        
        print(f"{datetime.now()} New Trick-or-Treater added via button press")
        
    def __undo_btn_callback(self):
        """Callback when the undo button is pressed - remove the last entry"""
        with self.data_lock:
            if self.current_data:
                removed_entry = self.current_data.pop()
                self.__save_current_data()
                print(f"{datetime.now()} Removed last trick-or-treater entry")
            else:
                print(f"{datetime.now()} No entries to remove")
    
    def __save_current_data(self):
        """Save the current data to the JSON file"""
        try:
            with open('data/trickortreat_data.json', 'w') as f:
                json.dump(self.current_data, f, indent=2)
        except Exception as e:
            print(f"Error saving current data: {e}")
    
    def load_current_data(self):
        """Load existing current data from the JSON file"""
        try:
            with open('data/trickortreat_data.json', 'r') as f:
                self.current_data = json.load(f)
            print(f"Loaded {len(self.current_data)} existing entries")
        except FileNotFoundError:
            self.current_data = []
            print("No existing data found, starting fresh")
        except Exception as e:
            print(f"Error loading current data: {e}")
            self.current_data = []
    
    def get_current_data(self):
        """Get a copy of the current data"""
        with self.data_lock:
            return self.current_data.copy()
    
    def get_total_count(self):
        """Get the total count of trick-or-treaters"""
        with self.data_lock:
            return sum(entry['count'] for entry in self.current_data)
    
    def get_recent_count(self, minutes=5):
        """Get the count from the last N minutes"""
        cutoff_time = datetime.now().timestamp() - (minutes * 60)
        with self.data_lock:
            recent_entries = [
                entry for entry in self.current_data
                if datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')).timestamp() > cutoff_time
            ]
            return sum(entry['count'] for entry in recent_entries)
    
    def cleanup(self):
        """Clean up the serial interface"""
        if hasattr(self, 'serial_radio'):
            self.serial_radio.exit()
        print("Serial interface cleaned up")

# Global instance for the dashboard
dashboard_serial = None

def initialize_serial_integration(serial_port="COM7"):
    """Initialize the serial integration for the dashboard"""
    global dashboard_serial
    dashboard_serial = DashboardSerialIntegration(serial_port)
    dashboard_serial.load_current_data()
    return dashboard_serial

def get_serial_integration():
    """Get the global serial integration instance"""
    return dashboard_serial
