# Housekeeping Sensor Interface Module (MicroPython)

from machine import I2C, Pin
import time

#INA238 Constants and Configuration

# Register Addresses
INA238_REG_CONFIG = 0x00
INA238_REG_ADC_CONFIG = 0x01
INA238_REG_SHUNT_CAL = 0x02
INA238_REG_VSHUNT = 0x04
INA238_REG_VBUS = 0x05
INA238_REG_DIETEMP = 0x07
INA238_REG_CURRENT = 0x08
INA238_REG_POWER = 0x09

# I2C Addresses
INA238_ADDRESSES = [0x40, 0x41, 0x42, 0x43, 0x44]

# Sensor LSBs (from datasheet)
INA238_VBUS_LSB = 0.003125      # 3.125 mV/LSB for Bus Voltage
INA238_TEMP_LSB = 0.0078125     # 0.0078125 °C/LSB for Die Temperature

# TODO
R_SHUNT_OHMS = 0.01             # Example: 10 mOhm (0.01 Ohms)
CURRENT_LSB_AMPS = 0.001        # Example: 1 mA (0.001 Amps) - sets the resolution

# Calculated Constants
INA238_POWER_LSB = 25 * CURRENT_LSB_AMPS
INA238_SHUNT_CAL_VAL = int(0.00512 / (CURRENT_LSB_AMPS * R_SHUNT_OHMS))
if INA238_SHUNT_CAL_VAL > 0xFFFF:
    INA238_SHUNT_CAL_VAL = 0xFFFF


class INA238:
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address
        self.current_lsb = CURRENT_LSB_AMPS
        self.power_lsb = INA238_POWER_LSB

        if self.address not in self.i2c.scan():
            print(f"Warning: INA238 not found at address 0x{address:02x}")
            return 
        
        # 1. Write SHUNT_CAL register (MSB first, 16-bit)
        self.i2c.writeto_mem(self.address, INA238_REG_SHUNT_CAL,
                             INA238_SHUNT_CAL_VAL.to_bytes(2, 'big'))

        # 2. Configure ADC for Continuous VBUS, VSHUNT, and DIETEMP (Mode 0x0F)
        # Register Value: 0b0100_0100_0000_1111 = 0x440F
        adc_config_val = 0x440F
        self.i2c.writeto_mem(self.address, INA238_REG_ADC_CONFIG,
                             adc_config_val.to_bytes(2, 'big'))

    def _read_register_signed(self, reg_addr):
        data = self.i2c.readfrom_mem(self.address, reg_addr, 2)
        return int.from_bytes(data, 'big', True)

    def _read_register_unsigned(self, reg_addr):
        data = self.i2c.readfrom_mem(self.address, reg_addr, 2)
        return int.from_bytes(data, 'big', False)

    def read_bus_voltage(self):
        #Returns bus voltage in Volts (V).
        raw_vbus = self._read_register_unsigned(INA238_REG_VBUS)
        return raw_vbus * INA238_VBUS_LSB

    def read_current(self):
        #Returns current in Amperes (A).
        raw_current = self._read_register_signed(INA238_REG_CURRENT)
        return raw_current * self.current_lsb

    def read_power(self):
        #Returns power in Watts (W).
        raw_power = self._read_register_unsigned(INA238_REG_POWER)
        return raw_power * self.power_lsb

    def read_die_temperature(self):
        #Returns die temperature in Celsius (°C).#
        raw_temp = self._read_register_signed(INA238_REG_DIETEMP)
        return raw_temp * INA238_TEMP_LSB


# MAX6634 Constants

# Register Addresses
MAX6634_REG_TEMP = 0x00
MAX6634_REG_CONFIG = 0x01

# Default I2C Addresses (MAX6634 A0-A3 low, 0x48 through 0x4C)
MAX6634_ADDRESSES = [0x48, 0x49, 0x4A, 0x4B, 0x4C]

# Temperature Resolution
MAX6634_TEMP_LSB = 0.0625  # 0.0625 °C/LSB


class MAX6634:
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address

        if self.address not in self.i2c.scan():
            print(f"Warning: MAX6634 not found at address 0x{address:02x}")
            return

    def read_temperature(self):
        #Returns the temperature in Celsius (°C).
        # Read 2 bytes from TEMP_REGISTER (0x00)
        data = self.i2c.readfrom_mem(self.address, MAX6634_REG_TEMP, 2)
        
        # Combine bytes (MSB first)
        raw_16bit = (data[0] << 8) | data[1]
        
        # Temperature data is D[15:4] (12 bits)
        temp_value = raw_16bit >> 4
        
        # Handle two's complement for negative numbers (12-bit value)
        if temp_value & 0x800:
            signed_value = temp_value - 4096 # 4096 = 2^12
        else:
            signed_value = temp_value
        
        # Apply LSB: 0.0625 °C
        temperature = signed_value * MAX6634_TEMP_LSB
        return temperature


# --- Sensor Manager Class ---

# Default I2C Pins TODO
I2C_SCL_PIN = 9
I2C_SDA_PIN = 8


class HousekeepingSensorManager:
    def __init__(self, i2c_id=0, scl_pin=I2C_SCL_PIN, sda_pin=I2C_SDA_PIN):
        # Initialize I2C bus 0 at 100kHz
        self.i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=100_000)

        # 🚨 IMPORTANT: Ensure these addresses match your hardware configuration.
        print(f"Scanning I2C Bus: {[hex(addr) for addr in self.i2c.scan()]}")
        
        # Instantiate 5 INA238 sensors
        self.ina238_sensors = [
            INA238(self.i2c, address) 
            for address in INA238_ADDRESSES
        ]
        
        # Instantiate 5 MAX6634 sensors
        self.max6634_sensors = [
            MAX6634(self.i2c, address) 
            for address in MAX6634_ADDRESSES
        ]
        
    def read_ina238_data(self, channel):
        #Reads all core data from a specific INA238 power monitor (0-4).
        sensor = self.ina238_sensors[channel]
        # Check if sensor was initialized (i.e., address found on bus)
        if sensor.address not in self.i2c.scan():
            return {"error": f"INA238 (Channel {channel}, Addr 0x{sensor.address:02x}) not accessible"}
            
        return {
            "bus_voltage_V": sensor.read_bus_voltage(),
            "current_A": sensor.read_current(),
            "power_W": sensor.read_power(),
            "die_temp_C": sensor.read_die_temperature(),
        }
    
    def read_all_ina238_data(self):
        #Reads data from all 5 INA238 power monitors.
        return [
            self.read_ina238_data(i) 
            for i in range(len(self.ina238_sensors))
        ]
        
    def read_housekeeping_temperature(self, channel):
        #Reads the temperature from a specific MAX6634 sensor (0-4).
        sensor = self.max6634_sensors[channel]
        if sensor.address not in self.i2c.scan():
            return {"error": f"MAX6634 (Channel {channel}, Addr 0x{sensor.address:02x}) not accessible"}
            
        return sensor.read_temperature()
        
    def read_all_housekeeping_temperatures(self):
        #Reads temperature from all 5 MAX6634 sensors.
        return [
            self.read_housekeeping_temperature(i) 
            for i in range(len(self.max6634_sensors))
        ]
        
    def read_all_housekeeping_data(self):
        #Reads all data from all 10 housekeeping sensors.
        data = {
            "INA238_Data": self.read_all_ina238_data(),
            "MAX6634_Temperatures_C": self.read_all_housekeeping_temperatures(),
        }
        return data
