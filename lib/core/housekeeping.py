# HEDGE-2 SCI Board - Housekeeping Interface

import time
from machine import I2C, Pin
import lib.calibration as calibration
from lib.drivers import INA238, MAX6634

# Default I2C Pins
I2C_SCL_PIN = 21
I2C_SDA_PIN = 20

INA238_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44]
MAX6634_ADDRESSES = [0x48, 0x49, 0x4A, 0x4B, 0x4C]


class HousekeepingManager:
    def __init__(self, i2c_id=0, scl_pin=I2C_SCL_PIN, sda_pin=I2C_SDA_PIN):
        # Initialize I2C bus 0 at 100kHz
        self.i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=100_000)
        
        # Instantiate 5 INA238 sensors
        self.ina238_sensors = [INA238(self.i2c, address) for address in INA238_ADDRESSES]
        
        # Instantiate 5 MAX6634 sensors
        self.max6634_sensors = [MAX6634(self.i2c, address) for address in MAX6634_ADDRESSES]
        
    def read_ina238_data(self, channel):
        # Reads all core data from a specific INA238 power monitor (0-4).
        sensor = self.ina238_sensors[channel]
        # Check if sensor was initialized (i.e., address found on bus)
        if sensor.address not in self.i2c.scan():
            return 0.0, 0.0, 0.0, 0.0

        voltage = sensor.read_bus_voltage()
        current = sensor.read_current()
        power = sensor.read_power()
        temperature = sensor.read_die_temperature()

        return voltage, current, power, temperature
    
    def read_all_ina238_data(self):
        # Reads data from all 5 INA238 power monitors.
        return [self.read_ina238_data(i) for i in range(len(self.ina238_sensors))]
        
    def read_housekeeping_temperature(self, channel):
        # Reads the temperature from a specific MAX6634 sensor (0-4).
        sensor = self.max6634_sensors[channel]
        if sensor.address not in self.i2c.scan():
            return 0.0
            
        return sensor.read_temperature()
        
    def read_all_housekeeping_temperatures(self):
        # Reads temperature from all 5 MAX6634 sensors.
        return [self.read_housekeeping_temperature(i) for i in range(len(self.max6634_sensors))]
        
    def read_all_housekeeping_data(self):
        timestamp = time.ticks_ms() & 0xFFFFFFFF
        ina238_data = self.read_all_ina238_data()
        max6634_temperatures = self.read_all_housekeeping_temperatures()
        return timestamp, ina238_data, max6634_temperatures
