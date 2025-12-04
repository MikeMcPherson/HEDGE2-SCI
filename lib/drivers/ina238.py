# HEDGE-2 SCI Board - INA238 Driver

# Register Addresses
INA238_REG_CONFIG = 0x00
INA238_REG_ADC_CONFIG = 0x01
INA238_REG_SHUNT_CAL = 0x02
INA238_REG_VSHUNT = 0x04
INA238_REG_VBUS = 0x05
INA238_REG_DIETEMP = 0x07
INA238_REG_CURRENT = 0x08
INA238_REG_POWER = 0x09

# Sensor LSBs (from datasheet)
INA238_VBUS_LSB = 0.000005  # 1.25 uV/LSB for Bus Voltage
INA238_TEMP_LSB = 0.0078125  # 0.0078125 °C/LSB for Die Temperature

R_SHUNT_OHMS = 0.24  # Example: 10 mOhm (0.01 Ohms)
CURRENT_LSB_AMPS = 0.001  # Example: 1 mA (0.001 Amps) - sets the resolution

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
        #1
        reg_config_val = 0x0000
        self.i2c.writeto_mem(self.address, INA238_REG_CONFIG,
                             reg_config_val.to_bytes(2, 'big'))

        # 2. Write SHUNT_CAL register (MSB first, 16-bit)
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
        # Returns bus voltage in Volts (V).
        raw_vbus = self._read_register_unsigned(INA238_REG_VBUS)
        return raw_vbus * INA238_VBUS_LSB

    def read_current(self):
        # Returns current in Amperes (A).
        raw_current = self._read_register_signed(INA238_REG_CURRENT)
        return raw_current * self.current_lsb

    def read_power(self):
        # Returns power in Watts (W).
        raw_power = self._read_register_unsigned(INA238_REG_POWER)
        return raw_power * self.power_lsb

    def read_die_temperature(self):
        # Returns die temperature in Celsius (°C).#
        raw_temp = self._read_register_signed(INA238_REG_DIETEMP)
        return raw_temp * INA238_TEMP_LSB