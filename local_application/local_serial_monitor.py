# local_serial_monitor.py
"""
Local script that monitors COM port and sends data to remote dashboard
This runs on your local computer with serial port access
"""

import serial
import time
import json
import os
from datetime import datetime
from typing import Optional, TYPE_CHECKING

# Defer importing the API client at runtime to avoid requiring network-related
# dependencies (like `requests`) when this module is imported for help or
# inspection. Only import for type checking / IDEs.
if TYPE_CHECKING:
    from .api_client import DashboardAPIClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalSerialMonitor:
    """Monitors local serial port and sends data to remote dashboard"""
    
    def __init__(self, port: str, api_client: 'DashboardAPIClient', 
                 baudrate: int = 9600, local_backup: bool = True):
        """
        Initialize serial monitor
        
        Args:
            port: Serial port (e.g., 'COM3')
            api_client: DashboardAPIClient instance
            baudrate: Serial communication speed
            local_backup: Whether to save data locally as backup
        """
        self.port = port
        self.api_client = api_client
        self.baudrate = baudrate
        self.local_backup = local_backup
        self.serial_conn: Optional[serial.Serial] = None
        self.is_running = False
        self.local_data_file = 'data/trickortreat_data_backup.json'
        
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
    
    def connect_serial(self) -> bool:
        """Connect to serial port"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            logger.info(f"✓ Connected to {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"✗ Failed to connect to {self.port}: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error connecting to serial: {e}")
            return False
    
    def disconnect_serial(self):
        """Disconnect from serial port"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Serial port closed")
    
    def save_local_backup(self, data: dict):
        """Save data locally as backup"""
        if not self.local_backup:
            return
        
        try:
            # Load existing data
            if os.path.exists(self.local_data_file):
                with open(self.local_data_file, 'r') as f:
                    all_data = json.load(f)
            else:
                all_data = []
            
            # Append new data
            all_data.append(data)
            
            # Save back to file
            with open(self.local_data_file, 'w') as f:
                json.dump(all_data, f, indent=2)
            
            logger.debug(f"Saved backup to {self.local_data_file}")
        except Exception as e:
            logger.error(f"Failed to save local backup: {e}")
    
    def handle_button_press(self, button_type: str):
        """Handle button press from serial input"""
        if button_type == 'COUNT':
            # Add trick-or-treater
            result = self.api_client.add_trick_or_treater()
            
            if result:
                logger.info("✓ Trick-or-treater counted successfully")
                
                # Save local backup
                if self.local_backup:
                    data = {
                        'timestamp': datetime.now().isoformat(),
                        'count': 1,
                        'year': datetime.now().year
                    }
                    self.save_local_backup(data)
            else:
                logger.error("✗ Failed to send count to server (saved locally)")
                # Still save locally if server is unreachable
                if self.local_backup:
                    data = {
                        'timestamp': datetime.now().isoformat(),
                        'count': 1,
                        'year': datetime.now().year,
                        'pending_upload': True
                    }
                    self.save_local_backup(data)
        
        elif button_type == 'UNDO':
            # Undo last entry
            result = self.api_client.undo_last_entry()
            if result:
                logger.info("✓ Last entry undone successfully")
            else:
                logger.error("✗ Failed to undo on server")
    
    def read_serial(self):
        """Read data from serial port"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        try:
            if self.serial_conn.in_waiting > 0:
                line = self.serial_conn.readline().decode('utf-8').strip()
                return line
        except Exception as e:
            logger.error(f"Error reading serial: {e}")
        
        return None
    
    def run(self):
        """Main monitoring loop"""
        if not self.connect_serial():
            logger.error("Cannot start - serial connection failed")
            return
        
        # Check server connectivity
        if not self.api_client.health_check():
            logger.warning("⚠ Server is not reachable - will retry periodically")
        else:
            logger.info("✓ Server is reachable")
        
        self.is_running = True
        logger.info("Starting serial monitor... Press Ctrl+C to stop")
        
        last_health_check = time.time()
        health_check_interval = 60  # Check every 60 seconds
        
        # Enable live mode
        result = self.api_client.set_live(True)
        if result:
            logger.info("✓ Live mode enabled")
        else:
            logger.error("✗ Failed to enable live mode")

        try:
            while self.is_running:
                # Periodic health check
                if time.time() - last_health_check > health_check_interval:
                    if self.api_client.health_check():
                        logger.debug("Server health check: OK")
                    else:
                        logger.warning("Server health check: FAILED")
                    last_health_check = time.time()
                
                # Read serial data
                data = self.read_serial()
                if data:
                    logger.info(f"Received: {data}")
                    self.handle_button_press(data)
                
                time.sleep(0.1)  # Small delay to prevent CPU spinning
        
        except KeyboardInterrupt:
            logger.info("\nStopping serial monitor...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.is_running = False
            self.disconnect_serial()
            logger.info("Serial monitor stopped")

            # Disable live mode
            result = self.api_client.set_live(False)
            if result:
                logger.info("✓ Live mode disabled")
            else:
                logger.error("✗ Failed to disable live mode")
    
    def sync_pending_data(self):
        """Upload any pending local data to server"""
        if not self.local_backup or not os.path.exists(self.local_data_file):
            return
        
        try:
            with open(self.local_data_file, 'r') as f:
                all_data = json.load(f)
            
            # Find pending entries
            pending = [d for d in all_data if d.get('pending_upload')]
            
            if pending:
                logger.info(f"Found {len(pending)} pending entries to upload")
                result = self.api_client.upload_data_batch(pending)
                
                if result:
                    logger.info("✓ Pending data uploaded successfully")
                    # Remove pending flag from uploaded entries
                    for entry in all_data:
                        if entry.get('pending_upload'):
                            entry['pending_upload'] = False
                    
                    with open(self.local_data_file, 'w') as f:
                        json.dump(all_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to sync pending data: {e}")
    
    def exit_app(self):
        self.is_running = False


# Example usage
if __name__ == "__main__":
    # Load configuration from environment or config file
    API_BASE_URL = os.environ.get('DASHBOARD_API_URL', 'https://yourdomain.com')
    API_KEY = os.environ.get('DASHBOARD_API_KEY', 'your-secure-api-key-here')
    SERIAL_PORT = os.environ.get('SERIAL_PORT', 'COM3')
    
    # Initialize API client
    api_client = DashboardAPIClient(
        base_url=API_BASE_URL,
        api_key=API_KEY
    )
    
    # Initialize serial monitor
    monitor = LocalSerialMonitor(
        port=SERIAL_PORT,
        api_client=api_client,
        local_backup=True  # Save data locally as backup
    )
    
    # Try to sync any pending data from previous runs
    monitor.sync_pending_data()
    
    # Start monitoring
    monitor.run()