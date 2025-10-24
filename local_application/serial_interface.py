# -----------------------------------------------------------
# Serial Interface to communicate with the Arduino Button
#  Interface.
#
# (C) 2023 Daniel VanVolkinburg 
# Released under GNU Public License (GPL)
# email dvanvolk@ieee.org
# -----------------------------------------------------------
import serial
from serial.threaded import LineReader, ReaderThread
import traceback
import time
import sys
import re

class RadioProtocolHandler(LineReader):
    """This class overrides the LineReader class and is responsible for getting information from the serial interface
    The radio interface does not need to write, but if needed the function write_line can be used
    Class looks for Button or Heart Messages that look like: "Button: 1", "Button: 2", "Button: 3" or "Heart: 1" """
    def __init__(self):
        super().__init__()
        self.event_callback_list = list()
        self.heart_callback = None

    def connection_made(self, transport):
        """Function overrides the base class and reports when the serial port is open"""
        super(RadioProtocolHandler, self).connection_made(transport)
        print('port opened\n')

    def handle_line(self, data):
        """Function overrides the base class and handles incoming data from the serial port, 
           it will check the response and signal what button was pressed.
           Function checks for known string signatures that contain "button", and "heart"
        """
        numeric_data = int(re.search(r'\d+', data).group()) - 1
        if "Button" in data:
            self.__process_button(numeric_data)
        elif "Heart" in data:
            self.__process_heart(numeric_data)
        else:
            print(f"Unexpected Data: {data}")    

    def connection_lost(self, exc):
        """Function overrides the base class and reports when the connection is lost"""
        if exc:
            traceback.print_exc(exc)
        print('Lost Connection\n')

    def set_button_callback(self, button_cb_list):
        """Function sets the callback list of the buttons, The list index should correspond to the button ID"""
        self.event_callback_list = button_cb_list

    def set_heart_callback(self, heart_cb):
        """Function sets the callback of the Heartbeat"""
        self.heart_callback = heart_cb
        
    def __process_button(self, button_index):
        """handle a button receive data by calling a callback if configured"""
        if len(self.event_callback_list) > button_index:
                if self.event_callback_list[button_index] is not None:
                    self.event_callback_list[button_index]()   
        else:
            print(f"Low list index")

    def __process_heart(self, id):
        """handle a heart receive data by calling a callback if configured"""
        print(f"Radio Heart: {id}")  

TEST_PORT = 'loop://'
BAUD_RATE = 115200

class RadioInterface():
    def __init__(self):
        self.protocol = None
        self.transport = None    

    def start(self, port=TEST_PORT, button_callbacks = list(), heart_callback = None):
        """Start the serial interface and reader thread"""
        if port == TEST_PORT:
            # Create a loopback device
            serial_interface = serial.serial_for_url(port, baudrate=BAUD_RATE, timeout=1)
        else:
            serial_interface = serial.Serial(port, baudrate=BAUD_RATE, timeout=1)
        reader_thread = ReaderThread(serial_interface, RadioProtocolHandler )
        reader_thread.start()
        self.transport, self.protocol = reader_thread.connect()
        
        self.protocol.set_button_callback(button_callbacks)
        self.protocol.set_heart_callback(heart_callback)

        print("Start Serial Interface")
        time.sleep(1)

    def exit(self):
        """Close the serial port and reader thread"""
        self.transport.close()

    def send_data(self, write_data):
        """Send Data to the out the interface"""
        self.protocol.write_line(write_data)


def test_button_callback():
    """Function is used for testing only"""
    print(f"Test Button Callback")        

if __name__ == '__main__':
    """Test the Serial Interface"""
    print("Start")
    callbacks = [test_button_callback, test_button_callback, test_button_callback]
    test_interface = RadioInterface()
    test_interface.start(port= "COM7", button_callbacks=callbacks)

    # for button_idx in range(1,4):
    #     test_interface.send_data(f"Button {button_idx}")

    # for heart_idx in range(1,10):
    #     test_interface.send_data(f"Heart: {heart_idx}")

    # time.sleep(1)  # Need to sleep here and allow the RX thread time to run
    # print("exit")
    # test_interface.exit()
    input("Press Enter to end...")
    print("End")
