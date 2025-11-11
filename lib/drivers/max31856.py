# HEDGE-2 SCI Board - MAX31856 Driver

import time
from machine import Pin

# MAX31856 Register Addresses
MAX31856_CR0_REG = 0x00
MAX31856_CR1_REG = 0x01
MAX31856_LTCBH_REG = 0x0C
MAX31856_SR_REG = 0x0F

# MAX31856 Configuration
MAX31856_CR0_AUTOCONVERT = 0x80     # Automatic conversion mode
MAX31856_CR1_AVGSEL1 = 0x00         # 1 sample averaging
MAX31856_CR1_TYPE_K = 0x03          # K-type thermocouple


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
        if temp_raw & 0x40000:  # Check sign bit (bit 18)
            temp_raw -= 0x80000  # Convert to negative

        temperature = temp_raw * 0.0078125
        return temperature

    def check_fault(self):
        data = self._read_registers(MAX31856_SR_REG, 1)
        return data[0]
