# HEDGE-2 SCI Board - Buffer Interface

import time
import struct


class Buffer:
    def __init__(self, capacity=120):
        self.capacity = capacity
        self.buffer = [b''] * capacity
        self.write_index = 0
        self.count = 0
        
    def add_sample(self, temperatures=None, pressures=None, hk_voltages=None, hk_currents=None, hk_powers=None, hk_temps=None, hk_ina_temps=None, timestamp=None):
        if timestamp is None:
            timestamp = time.ticks_ms() & 0xFFFFFFFF
            
        temperatures = temperatures or [0.0, 0.0, 0.0, 0.0]
        pressures = pressures or [0.0, 0.0, 0.0, 0.0]
        hk_voltages = hk_voltages or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        hk_currents = hk_currents or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        hk_powers = hk_powers or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        hk_temps = hk_temps or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        hk_ina_temps = hk_ina_temps or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        # Struct format: timestamp + (4 temps + 4 pressures) + (6V + 6I + 6P + 6T + 6INAT)
        fmt = "<I6f12f"  # = 1 uint32 + 18 floats total
        packed = struct.pack(fmt, timestamp, *temperatures, *pressures, *hk_voltages, *hk_currents, *hk_powers, *hk_temps, *hk_ina_temps)

        self.buffer[self.write_index] = packed
        self.write_index = (self.write_index + 1) % self.capacity
        if self.count < self.capacity:
            self.count += 1

        return True
    
    def get_all(self):
        if self.count == 0:
            return []
        if self.count < self.capacity:
            return self.buffer[:self.count]
        else:
            return self.buffer[self.write_index:] + self.buffer[:self.write_index]
    
    def get_latest(self):
        if self.count == 0:
            return None
        index = (self.write_index - 1) % self.capacity
        return self.buffer[index]
    
    def clear(self):
        self.write_index = 0
        self.count = 0
    
    def is_full(self):
        return self.count >= self.capacity
    
    def size(self):
        return self.count