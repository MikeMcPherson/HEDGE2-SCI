# HEDGE-2 SCI Board - ADS1118 Driver

import time
import struct
from machine import Pin

# ADS1118 Configuration
ADS1118_SS = 0x8000				# Start single conversion
ADS1118_PGA_256 = 0x0A00		# 0.256V range
ADS1118_MODE_SINGLE = 0x0100	# Single-shot mode
ADS1118_DR_860SPS = 0x00E0		# 860 samples per second
ADS1118_TS_MODE_ADC = 0x0000	# ADC mode
ADS1118_NOP = 0x0002			# Valid data, no operation


class ADS1118:
    def __init__(self, spi, cs_pin):
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT)
        self.cs.value(1)  # Active low

    def read_channel(self, channel):
        if channel < 0 or channel > 3:
            return None

        # MUX bits: 0x4000=AIN0, 0x5000=AIN1, 0x6000=AIN2, 0x7000=AIN3
        mux = 0x4000 + (channel << 12)
        config = (ADS1118_SS | mux | ADS1118_PGA_256 | ADS1118_MODE_SINGLE | ADS1118_DR_860SPS | ADS1118_TS_MODE_ADC | ADS1118_NOP)
        config_bytes = struct.pack('>H', config)

        self.cs.value(0)
        self.spi.write(config_bytes)
        self.cs.value(1)

        time.sleep_ms(2) # Wait for conversion

        result = bytearray(2)
        self.cs.value(0)
        self.spi.write_readinto(config_bytes, result)
        self.cs.value(1)

        # Convert to signed 16-bit integer
        raw_value = struct.unpack('>h', result)[0]

        # Convert to voltage
        voltage = raw_value * 0.256 / 32768.0
        return voltage

    def read_pressure(self, channel):
        return self.read_channel(channel)