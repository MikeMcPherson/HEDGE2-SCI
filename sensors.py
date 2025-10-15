# HEDGE-2 SCI Board - Sensor Interface Module

from machine import SPI, Pin
import time
import struct

# MAX31856 Register Addresses
MAX31856_CR0_REG = 0x00
MAX31856_CR1_REG = 0x01
MAX31856_LTCBH_REG = 0x0C
MAX31856_SR_REG = 0x0F

# MAX31856 Configuration
MAX31856_CR0_AUTOCONVERT = 0x80  # Automatic conversion mode
MAX31856_CR1_AVGSEL1 = 0x00      # 1 sample averaging
MAX31856_CR1_TYPE_K = 0x03       # K-type thermocouple

class MAX31856:    
    def __init__(self, spi, cs_pin):
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT)
        self.cs.value(1)  # Active low
        self._init_sensor()
        
    def _init_sensor(self):
        # Configure CR0: Auto-conversion, 60Hz filter
        self._write_register(MAX31856_CR0_REG, MAX31856_CR0_AUTOCONVERT)
        time.sleep_ms(10)
        
        # Configure CR1: K-type thermocouple, 1 sample averaging
        self._write_register(MAX31856_CR1_REG, MAX31856_CR1_TYPE_K | MAX31856_CR1_AVGSEL1)
        time.sleep_ms(100)
        
    def _write_register(self, reg, value):
        self.cs.value(0)
        self.spi.write(bytes([reg | 0x80, value]))
        self.cs.value(1)
        
    def _read_registers(self, reg, length):
        self.cs.value(0)
        self.spi.write(bytes([reg & 0x7F]))
        data = self.spi.read(length)
        self.cs.value(1)
        return data
    
    def read_temperature(self):
        data = self._read_registers(MAX31856_LTCBH_REG, 3)
        temp_raw = (data[0] << 16) | (data[1] << 8) | data[2]
        
        # Convert to signed and scale (resolution = 0.0078125°C)
        temp_raw = temp_raw >> 5  # Remove fault bit and reserved bits
        if temp_raw & 0x40000:    # Check sign bit (bit 18)
            temp_raw -= 0x80000   # Convert to negative
        
        temperature = temp_raw * 0.0078125
        return temperature
    
    def check_fault(self):
        data = self._read_registers(MAX31856_SR_REG, 1)
        return data[0]

class SensorManager:
    def __init__(self):
        self.spi = SPI(0, baudrate=2_000_000, polarity=0, phase=1, sck=Pin(2), mosi=Pin(3), miso=Pin(9))
        
        self.thermocouples = [
            MAX31856(self.spi, cs_pin=12),  # TC1
            MAX31856(self.spi, cs_pin=13),  # TC2
            MAX31856(self.spi, cs_pin=14),  # TC3
            MAX31856(self.spi, cs_pin=15),  # TC4
        ]
    
    def read_temperatures(self):
        temps = []
        for i, tc in enumerate(self.thermocouples):
            temp = tc.read_temperature()
            temps.append(temp)
        return temps
    
    def read_sensors(self):
        return {
            'temperatures': self.read_all_temperatures(),
            'timestamp': time.ticks_ms()
        }
        
def test_sensors():
    sensors = SensorManager()
    
    print("Starting sensor test (2 Hz sampling)")
    
    try:
        while True:
            data = sensors.read_all_sensors()
            
            print(f"[{data['timestamp']}ms]")
            print(f"  Temps (°C): {data['temperatures']}")
            print()
            
            time.sleep(0.5)  # 2 Hz = 0.5 second delay
            
    except KeyboardInterrupt:
        print("\nTest stopped")


if __name__ == "__main__":
    test_sensors()