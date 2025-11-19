
from machine import UART, Pin
import time

class RS485:
    def __init__(self, tx_pin=8, rx_pin=5, dir_pin=7, baudrate=1500):
        """Initialize RS485 interface."""
        self.dir_pin = Pin(dir_pin, Pin.OUT)
        self.uart = UART(1, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.dir_pin.value(0)  # Default to receive mode
        print(f"RS485 initialized on TX:{tx_pin}, RX:{rx_pin}, DIR:{dir_pin}, baudrate:{baudrate}")

    def send(self, data):
        """Send data over RS485."""
        if isinstance(data, str):
            data = data.encode()
        self.dir_pin.value(1)  # Enable driver
        self.uart.write(data)
        time.sleep(0.01)
        self.dir_pin.value(0)  # Back to receive mode
        print(f"RS485 Sent: {data}")

    def receive(self):
        """Receive data from RS485."""
        if self.uart.any():
            data = self.uart.read()
            print(f"RS485 Received: {data}")
            return data
        return None
