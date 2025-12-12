# HEDGE-2 SCI Board - Sensor Interface

import time
from machine import SPI, Pin
import lib.calibration as calibration
from lib.drivers import MAX31856, ADS1118


class SensorManager:
    def __init__(self):
        self.spi = SPI(0, baudrate=2_000_000, polarity=0, phase=1, sck=Pin(2), mosi=Pin(3), miso=Pin(16))
        
        self.thermocouples = [
            MAX31856(self.spi, cs_pin=12),
            MAX31856(self.spi, cs_pin=13),
            MAX31856(self.spi, cs_pin=14),
            MAX31856(self.spi, cs_pin=15),
        ]
        
        self.pressure_adc = ADS1118(self.spi, cs_pin=17)
    
    def read_all_temperatures(self):
        return [self.read_temperature(i) for i in range(len(self.thermocouples))]
    
    def read_temperature(self, channel):
        return self.thermocouples[channel].read_temperature() + calibration.TEMP_OFFSETS[channel]
    
    def read_all_pressures(self):
        return [self.read_pressure(channel) for channel in range(4)]
    
    def read_pressure(self, channel):
        voltage = (calibration.PRESSURE_SLOPES[channel] * self.pressure_adc.read_pressure(channel) +
                   calibration.PRESSURE_OFFSETS[channel])

        # M3021-000005-10KPG: 0-100mV = 0-10,000 PSI
        psi = (voltage / 0.1) * 10000.0
        kpa = psi * 6.89476
        return kpa

    def read_sensors(self):
        timestamp = time.ticks_ms() & 0xFFFFFFFF
        temperatures = self.read_all_temperatures()
        pressures = self.read_all_pressures()
        return timestamp, temperatures, pressures
