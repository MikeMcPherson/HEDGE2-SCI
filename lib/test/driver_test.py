import struct
import pytest

from lib.drivers import ads1118, ina238, max31856, max6634


class FakePin:
	OUT = 0

	def __init__(self, *args, **kwargs):
		self._val = 1

	def value(self, v=None):
		if v is None:
			return self._val
		self._val = v


class FakeSPI:
	def __init__(self):
		self._last_written = b''
		self._to_read = b''

	def write(self, data):
		# remember last write
		self._last_written = data

	def write_readinto(self, out_bytes, in_buffer):
		# fill in_buffer with pre-specified data or echo
		if not self._to_read:
			# default: put zero
			for i in range(len(in_buffer)):
				in_buffer[i] = 0
		else:
			for i, b in enumerate(self._to_read[: len(in_buffer)]):
				in_buffer[i] = b

	def read(self, length):
		if not self._to_read:
			return bytes([0] * length)
		return self._to_read[:length]


class FakeI2C:
	def __init__(self, present_addrs=None, reg_map=None):
		self._addrs = present_addrs or []
		self._reg_map = reg_map or {}

	def scan(self):
		return list(self._addrs)

	def writeto_mem(self, addr, reg, data):
		# store last written
		self._reg_map[(addr, reg)] = data

	def readfrom_mem(self, addr, reg, nbytes):
		val = self._reg_map.get((addr, reg), None)
		if val is None:
			return bytes([0] * nbytes)
		if isinstance(val, int):
			# pack into two bytes big-endian
			return val.to_bytes(2, 'big')
		return val


def test_ads1118_read_channel(monkeypatch):
	fake_spi = FakeSPI()
	# Prepare returned raw value: signed 16-bit = 1000
	raw = 1000
	packed = struct.pack('>h', raw)
	fake_spi._to_read = packed

	monkeypatch.setattr(ads1118, 'Pin', FakePin)
	adc = ads1118.ADS1118(fake_spi, cs_pin=5)
	voltage = adc.read_channel(0)
	expected = raw * 0.256 / 32768.0
	assert abs(voltage - expected) < 1e-9


def test_ads1118_various_inputs(monkeypatch):
	fake_spi = FakeSPI()
	monkeypatch.setattr(ads1118, 'Pin', FakePin)
	adc = ads1118.ADS1118(fake_spi, cs_pin=2)

	# invalid channel -> None
	assert adc.read_channel(-1) is None
	assert adc.read_channel(4) is None

	# zero raw -> zero voltage
	fake_spi._to_read = struct.pack('>h', 0)
	assert abs(adc.read_channel(1) - 0.0) < 1e-12

	# negative raw -> negative voltage
	fake_spi._to_read = struct.pack('>h', -1000)
	v = adc.read_channel(2)
	assert v < 0

	# alias read_pressure
	fake_spi._to_read = struct.pack('>h', 500)
	assert abs(adc.read_pressure(0) - (500 * 0.256 / 32768.0)) < 1e-9


def test_ina238_readings():
	# Create fake register map values
	addr = 0x40
	reg_map = {}
	# VBUS raw = 1000 -> voltage
	reg_map[(addr, ina238.INA238_REG_VBUS)] = 1000
	# CURRENT raw signed = 2000
	reg_map[(addr, ina238.INA238_REG_CURRENT)] = (2000).to_bytes(2, 'big', signed=False)
	# POWER raw unsigned = 50
	reg_map[(addr, ina238.INA238_REG_POWER)] = 50
	# DIE TEMP raw signed = 400
	reg_map[(addr, ina238.INA238_REG_DIETEMP)] = (400).to_bytes(2, 'big', signed=True)

	fake_i2c = FakeI2C(present_addrs=[addr], reg_map=reg_map)
	dev = ina238.INA238(fake_i2c, addr)

	v = dev.read_bus_voltage()
	assert abs(v - (1000 * ina238.INA238_VBUS_LSB)) < 1e-9

	# current uses signed read; ensure returns float
	c = dev.read_current()
	assert isinstance(c, float)

	p = dev.read_power()
	assert isinstance(p, float)

	t = dev.read_die_temperature()
	assert isinstance(t, float)


def test_ina238_signed_unsigned_and_missing_address(capsys):
	addr = 0x41
	# Test missing device prints a warning
	fake_i2c_missing = FakeI2C(present_addrs=[])
	ina_missing = ina238.INA238(fake_i2c_missing, addr)
	captured = capsys.readouterr()
	assert "not found" in captured.out.lower()

	# Test signed current negative value
	reg_map = {}
	reg_map[(addr, ina238.INA238_REG_CURRENT)] = (-200).to_bytes(2, 'big', signed=True)
	reg_map[(addr, ina238.INA238_REG_VBUS)] = 0
	reg_map[(addr, ina238.INA238_REG_POWER)] = 0
	reg_map[(addr, ina238.INA238_REG_DIETEMP)] = (0).to_bytes(2, 'big', signed=True)

	fake_i2c = FakeI2C(present_addrs=[addr], reg_map=reg_map)
	dev = ina238.INA238(fake_i2c, addr)

	cur = dev.read_current()
	assert cur < 0
	assert abs(cur - (-200 * dev.current_lsb)) < 1e-12

	# test power and vbus zero
	assert dev.read_power() == 0.0
	assert dev.read_bus_voltage() == 0.0


def test_max31856_temperature_and_fault(monkeypatch):
	fake_spi = FakeSPI()
	# Build a positive raw temperature. Choose shifted value 10000
	shifted = 10000
	raw_full = shifted << 5
	b0 = (raw_full >> 16) & 0xFF
	b1 = (raw_full >> 8) & 0xFF
	b2 = raw_full & 0xFF
	fake_spi._to_read = bytes([b0, b1, b2])

	monkeypatch.setattr(max31856, 'Pin', FakePin)
	monkeypatch.setattr(max31856, 'time', max31856.time)
	tc = max31856.MAX31856(fake_spi, cs_pin=12)
	temp = tc.read_temperature()
	expected = shifted * 0.0078125
	assert abs(temp - expected) < 1e-6


def _mk_max31856_bytes_from_signed_temp(temp_signed):
	# temp_signed is the value after shifting (i.e., signed integer that gets multiplied by 0.0078125)
	# convert to 19-bit two's complement representation (since after >>5 we have 19 bits: bit18 sign)
	if temp_signed < 0:
		temp_raw = (temp_signed + (1 << 19)) & ((1 << 19) - 1)
	else:
		temp_raw = temp_signed & ((1 << 19) - 1)

	# shift back to 24-bit register format
	raw_full = (temp_raw << 5) & 0xFFFFFF
	b0 = (raw_full >> 16) & 0xFF
	b1 = (raw_full >> 8) & 0xFF
	b2 = raw_full & 0xFF
	return bytes([b0, b1, b2])


def test_max31856_negative_temperature(monkeypatch):
	fake_spi = FakeSPI()
	monkeypatch.setattr(max31856, 'Pin', FakePin)
	monkeypatch.setattr(max31856, 'time', max31856.time)
	tc = max31856.MAX31856(fake_spi, cs_pin=6)

	# create a negative temp_signed (e.g., -1000 units)
	neg_signed = -1000
	fake_spi._to_read = _mk_max31856_bytes_from_signed_temp(neg_signed)
	temp = tc.read_temperature()
	assert temp < 0
	assert abs(temp - (neg_signed * 0.0078125)) < 1e-6

	# test fault register read
	fake_spi._to_read = bytes([0xAA])
	assert tc.check_fault() == 0xAA


def test_max6634_temperature():
	addr = 0x48
	# raw_16bit where top 12 bits provide temp (D[15:4])
	temp_value = 250  # signed positive
	raw_16bit = (temp_value << 4) & 0xFFFF
	fake_i2c = FakeI2C(present_addrs=[addr], reg_map={(addr, max6634.MAX6634_REG_TEMP): raw_16bit})
	dev = max6634.MAX6634(fake_i2c, addr)
	t = dev.read_temperature()
	expected = temp_value * max6634.MAX6634_TEMP_LSB
	assert abs(t - expected) < 1e-9


def test_max6634_negative_temperature():
	addr = 0x48
	# create negative 12-bit two's complement: example -10 -> 0xFFF - 9 = 0xFF6? compute properly
	neg = -10
	temp_12bit = neg & 0xFFF
	raw_16bit = (temp_12bit << 4) & 0xFFFF
	fake_i2c = FakeI2C(present_addrs=[addr], reg_map={(addr, max6634.MAX6634_REG_TEMP): raw_16bit})
	dev = max6634.MAX6634(fake_i2c, addr)
	t = dev.read_temperature()
	assert t < 0
	# check correct scaling
	assert abs(t - (neg * max6634.MAX6634_TEMP_LSB)) < 1e-9

