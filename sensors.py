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
MAX31856_CR0_AUTOCONVERT = 0x80	# Automatic conversion mode
MAX31856_CR1_AVGSEL1 = 0x00		# 1 sample averaging
MAX31856_CR1_TYPE_K = 0x03		# K-type thermocouple

# ADS1118 Configuration
ADS1118_SS = 0x8000				# Start single conversion
ADS1118_PGA_256 = 0x0A00		# 0.256V range
ADS1118_MODE_SINGLE = 0x0100	# Single-shot mode
ADS1118_DR_860SPS = 0x00E0		# 860 samples per second
ADS1118_TS_MODE_ADC = 0x0000	# ADC mode
ADS1118_NOP = 0x0002			# Valid data, no operation


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


class SensorManager:
    def __init__(self):
        self.spi = SPI(0, baudrate=2_000_000, polarity=0, phase=1, sck=Pin(2), mosi=Pin(3), miso=Pin(9))
        
        self.thermocouples = [
            MAX31856(self.spi, cs_pin=12),
            MAX31856(self.spi, cs_pin=13),
            MAX31856(self.spi, cs_pin=14),
            MAX31856(self.spi, cs_pin=15),
        ]
        
        self.pressure_adc = ADS1118(self.spi, cs_pin=17)
    
    def read_all_temperatures(self):
        return [tc.read_temperature() for tc in self.thermocouples]
    
    def read_temperature(self, channel):
        return self.thermocouples[channel].read_temperature()
    
    def read_all_pressures(self):
        return [self.pressure_adc.read_pressure(channel) for channel in range(4)]
    
    def read_pressure(self, channel):
        return self.pressure_adc.read_pressure(channel)
    
    def read_sensors(self):
        return {
            'temperatures': self.read_all_temperatures(),
            'pressures': self.read_all_pressures(),
            'timestamp': time.ticks_ms()
        }
