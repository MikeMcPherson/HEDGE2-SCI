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
        """Read single-ended channel 0-3 (AIN0..AIN3 relative to GND).

        Kept for backward-compatibility. Prefer using read_differential(), which
        returns differential readings for pairs (AIN0-AIN1, AIN2-AIN3).
        """
        if channel < 0 or channel > 3:
            return None

        # MUX bits: 0x4000=AIN0, 0x5000=AIN1, 0x6000=AIN2, 0x7000=AIN3
        mux = 0x4000 + (channel << 12)
        config = (ADS1118_SS | mux | ADS1118_PGA_256 | ADS1118_MODE_SINGLE | ADS1118_DR_860SPS | ADS1118_TS_MODE_ADC | ADS1118_NOP)
        config_bytes = struct.pack('>H', config)

        # ----------------------------------------------------------------------
        # FIX: Implement a two-conversion sequence for clean MUX switching
        # ----------------------------------------------------------------------
        
        # 1. Start the first conversion (allows MUX to settle)
        self.cs.value(0)
        self.spi.write(config_bytes)
        self.cs.value(1)

        time.sleep_ms(20) # Wait for conversion 1 to finish

        # 2. Read result of Conversion 1 (Transitional/Corrupted) and start Conversion 2 (Clean)
        # The result is read into a dummy bytearray and discarded.
        dummy_result = bytearray(2)
        self.cs.value(0)
        self.spi.write_readinto(config_bytes, dummy_result)
        self.cs.value(1)

        time.sleep_ms(20) # Wait for conversion 2 to finish

        # 3. Read result of Conversion 2 (Clean/Final Result) and start Conversion 3 (Ignored)
        result = bytearray(2)
        self.cs.value(0)
        self.spi.write_readinto(config_bytes, result)
        self.cs.value(1)
        
        # ----------------------------------------------------------------------
        # End Fix
        # ----------------------------------------------------------------------

        # Convert to signed 16-bit integer
        raw_value = struct.unpack('>h', result)[0]

        # Convert to voltage
        voltage = raw_value * 0.256 / 32768.0
        return voltage

    def read_pressure(self, channel):
        # Historically read_pressure returned single-ended channels 0..3.
        # For systems using differential sensors we prefer two differential
        # channels -- map channel indices 0..1 to differential pairs.
        if channel in (0, 1):
            return self.read_differential(channel)
        return None

    def read_differential(self, index):
        """Read one of two differential pairs:

        index 0 -> AIN0 - AIN1
        index 1 -> AIN2 - AIN3
        """
        if index not in (0, 1):
            return None

        # ADS1118 MUX codes for differential inputs:
        # 0b000 -> AIN0 - AIN1 -> 0x0000
        # 0b011 -> AIN2 - AIN3 -> 0x3000
        mux_codes = [0x0000, 0x3000]
        mux = mux_codes[index]

        config = (ADS1118_SS | mux | ADS1118_PGA_256 | ADS1118_MODE_SINGLE | ADS1118_DR_860SPS | ADS1118_TS_MODE_ADC | ADS1118_NOP)
        config_bytes = struct.pack('>H', config)

        # ----------------------------------------------------------------------
        # FIX: Implement a two-conversion sequence for clean MUX switching
        # ----------------------------------------------------------------------

        # 1. Start the first conversion (allows MUX to settle after channel switch)
        self.cs.value(0)
        self.spi.write(config_bytes)
        self.cs.value(1)

        time.sleep_ms(20) # Wait for conversion 1 to finish (using 20ms delay)

        # 2. Read result of Conversion 1 (Transitional/Corrupted) and start Conversion 2 (Clean)
        # The result is read into a dummy bytearray and discarded.
        dummy_result = bytearray(2)
        self.cs.value(0)
        self.spi.write_readinto(config_bytes, dummy_result)
        self.cs.value(1)

        time.sleep_ms(20) # Wait for conversion 2 to finish

        # 3. Read result of Conversion 2 (Clean/Final Result) and start Conversion 3 (Ignored)
        result = bytearray(2)
        self.cs.value(0)
        self.spi.write_readinto(config_bytes, result)
        self.cs.value(1)

        # ----------------------------------------------------------------------
        # End Fix
        # ----------------------------------------------------------------------

        # Convert to signed 16-bit integer
        raw_value = struct.unpack('>h', result)[0]

        # Convert to voltage
        voltage = raw_value * 0.256 / 32768.0
        return voltage