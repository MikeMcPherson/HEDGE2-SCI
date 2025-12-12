# HEDGE-2 SCI Board - INA238 Driver
import time

# You will need to ensure 'machine' and 'Pin' are available in your environment
# from machine import I2C, Pin

# --- Register Addresses ---
INA238_REG_CONFIG = 0x00
INA238_REG_ADC_CONFIG = 0x01
INA238_REG_SHUNT_CAL = 0x02
INA238_REG_VSHUNT = 0x04
INA238_REG_VBUS = 0x05
INA238_REG_DIETEMP = 0x06
INA238_REG_CURRENT = 0x07
INA238_REG_POWER = 0x08

# --- Configuration Constants (Register bits) ---
# Bit 13: 0=+-163.84mV (5uV/LSB), 1=+-40.96mV (1.25uV/LSB)
VSHUNT_FS_MASK = 0b0010000000000000

# Configuration Value: Set VSHUNT_FS=1 (1.25uV/LSB) and MODE=111 (Continuous Shunt/Bus/Temp)
INA238_DEFAULT_CONFIG = VSHUNT_FS_MASK | 0b00100111  # 0x2027

# --- Sensor LSBs (from datasheet and user observation) ---

# Shunt Voltage LSB: Set to 1.25 µV/LSB (0.00000125 V/LSB) by setting VSHUNT_FS=1 in CONFIG.
INA238_VSHUNT_LSB = 0.00000125

# Bus Voltage LSB is 3.125 mV/LSB (0.003125 V/LSB).
INA238_VBUS_LSB = 0.003125

# Die Temperature LSB: The datasheet specifies 0.125 °C/LSB, but the user's raw readings
# only convert to a physical temperature (~24°C) using the common LSB of 1/128 (0.0078125).
# Using 0.0078125 °C/LSB to match observed behavior.
INA238_TEMP_LSB = 0.125

# --- Configuration Constants (Examples) ---
R_SHUNT_OHMS = 0.24
CURRENT_LSB_AMPS = 0.001  # e.g., 1 mA (0.001 Amps)

# --- Calculated Constants ---
# Power LSB = 25 * Current_LSB
INA238_POWER_LSB = 25 * CURRENT_LSB_AMPS

# SHUNT_CAL = 0.00512 / (Current_LSB * R_Shunt)
INA238_SHUNT_CAL_VAL = int(0.00512 / (CURRENT_LSB_AMPS * R_SHUNT_OHMS))

# Check for overflow
if INA238_SHUNT_CAL_VAL > 0xFFFF:
    print(
        f"Warning: SHUNT_CAL value ({INA238_SHUNT_CAL_VAL}) exceeds 16-bit limit (0xFFFF). Current_LSB may be too small.")


class INA238:
    """Driver for the INA238 Precision Digital Current and Power Monitor."""

    def __init__(self, i2c_bus, address, current_lsb=CURRENT_LSB_AMPS, shunt_ohms=R_SHUNT_OHMS):
        self.i2c = i2c_bus
        self.address = address
        self.current_lsb = current_lsb
        self.shunt_ohms = shunt_ohms
        self.power_lsb = 25 * current_lsb

        # Calculate and store the SHUNT_CAL value
        shunt_cal_val = int(0.00512 / (current_lsb * shunt_ohms))
        self.shunt_cal = min(shunt_cal_val, 0xFFFF)

        # --- Device Configuration ---
        # 1. Write the calculated SHUNT_CAL value
        self._write_register(INA238_REG_SHUNT_CAL, self.shunt_cal)

        # 2. Write the CONFIG register to set VSHUNT_FS to 1 (1.25 uV/LSB) and start continuous conversion
        self._write_register(INA238_REG_CONFIG, INA238_DEFAULT_CONFIG)
        print(f"INFO: Configured INA238 at {hex(address)}. Shunt LSB set to 1.25 µV.")

    # --- I2C Helper Methods ---
    def _write_register(self, register_address, value):
        # Writes 2 bytes (MSB first) to a register.
        # Data format: [REG_ADDR, MSB, LSB]
        data = bytearray(3)
        data[0] = register_address
        data[1] = (value >> 8) & 0xFF  # MSB
        data[2] = value & 0xFF  # LSB
        try:
            self.i2c.writeto(self.address, data)
        except Exception:
            # Handle I2C write error silently or log
            pass

    def _read_register_unsigned(self, register_address):
        # Reads 2 bytes (MSB first) and returns an unsigned 16-bit integer.
        try:
            # Assuming a readfrom_mem style function (i2c.readfrom_mem(addr, reg_addr, num_bytes))
            data = self.i2c.readfrom_mem(self.address, register_address, 2)
            # data is bytes: [MSB, LSB]
            return (data[0] << 8) | data[1]
        except Exception:
            return 0

    def _read_register_signed(self, register_address):
        # Reads 2 bytes and interprets as signed 16-bit (two's complement).
        val = self._read_register_unsigned(register_address)

        # Convert 16-bit unsigned to 16-bit two's complement signed
        if val & 0x8000:
            return val - 0x10000
        return val

    # --- Public Read Methods ---
    def read_shunt_voltage(self):
        # Returns shunt voltage in Volts (V) using the 1.25 uV/LSB setting.
        raw_voltage_vshunt = self._read_register_signed(INA238_REG_VSHUNT)
        return raw_voltage_vshunt * INA238_VSHUNT_LSB

    def read_bus_voltage(self):
        # Returns bus voltage in Volts (V).
        raw_voltage = self._read_register_unsigned(INA238_REG_VBUS)
        return raw_voltage * INA238_VBUS_LSB

    def read_current(self):
        # Returns current in Amperes (A).
        raw_voltage_vshunt = self._read_register_signed(INA238_REG_VSHUNT)
        return raw_voltage_vshunt * INA238_VSHUNT_LSB / 0.24

    def read_power(self):
        # Returns power in Watts (W).
        raw_voltage_vbus = self._read_register_unsigned(INA238_REG_VBUS)
        raw_voltage_vshunt = self._read_register_signed(INA238_REG_VSHUNT)
        return raw_voltage_vbus * INA238_VBUS_LSB * raw_voltage_vshunt * INA238_VSHUNT_LSB / 0.24

    def read_die_temperature(self):
        # Returns die temperature in Celsius (°C) using the LSB that matches observed values.
        raw_temp = self._read_register_signed(INA238_REG_DIETEMP) >> 4
        return raw_temp * INA238_TEMP_LSB
