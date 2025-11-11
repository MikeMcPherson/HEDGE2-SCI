# MAX6634 Constants

# Register Addresses
MAX6634_REG_TEMP = 0x00
MAX6634_REG_CONFIG = 0x01

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
        # Returns the temperature in Celsius (°C).
        # Read 2 bytes from TEMP_REGISTER (0x00)
        data = self.i2c.readfrom_mem(self.address, MAX6634_REG_TEMP, 2)

        # Combine bytes (MSB first)
        raw_16bit = (data[0] << 8) | data[1]

        # Temperature data is D[15:4] (12 bits)
        temp_value = raw_16bit >> 4

        # Handle two's complement for negative numbers (12-bit value)
        if temp_value & 0x800:
            signed_value = temp_value - 4096  # 4096 = 2^12
        else:
            signed_value = temp_value

        # Apply LSB: 0.0625 °C
        temperature = signed_value * MAX6634_TEMP_LSB
        return temperature
