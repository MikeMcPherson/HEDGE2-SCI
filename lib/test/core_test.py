import pytest

from lib.core.buffer import Buffer


def test_buffer_basic():
	b = Buffer(capacity=3)
	assert b.size() == 0

	assert b.add_sample() is True
	assert b.size() == 1

	latest = b.get_latest()
	assert latest is not None

	all_samples = b.get_all()
	assert len(all_samples) == 1

	b.clear()
	assert b.size() == 0


def test_buffer_wraparound():
	b = Buffer(capacity=2)
	b.add_sample()
	b.add_sample()
	assert b.size() == 2

	# add third -> overwrite oldest
	b.add_sample()
	assert b.size() == 2


def test_buffer_pack_and_unpack():
	import struct

	# prepare custom sample values
	temps = [10.0, 11.5, -5.25, 0.0]
	pressures = [1.0, 2.0, 3.0, 4.0]
	hk_voltages = [3.3] * 6
	hk_currents = [0.01] * 6
	hk_powers = [0.033] * 6
	hk_temps = [25.0] * 6
	hk_ina_temps = [26.0] * 6

	b = Buffer(capacity=4)
	ts = 0x12345678
	added = b.add_sample(timestamp=ts, temperatures=temps, pressures=pressures,
						 hk_voltages=hk_voltages, hk_currents=hk_currents,
						 hk_powers=hk_powers, hk_temps=hk_temps, hk_ina_temps=hk_ina_temps)
	assert added is True

	latest = b.get_latest()
	assert latest is not None

	# verify format: unpack and check some fields
	fmt = "<I4f4f6f6f6f6f6f"
	unpacked = struct.unpack(fmt, latest)
	assert unpacked[0] == ts
	# temperatures start at index 1
	assert abs(unpacked[1] - temps[0]) < 1e-9
	assert abs(unpacked[4] - pressures[0]) < 1e-9


def test_get_all_ordering_on_full_buffer():
	b = Buffer(capacity=3)
	# add 3 distinct samples with different timestamps
	b.add_sample(timestamp=1)
	b.add_sample(timestamp=2)
	b.add_sample(timestamp=3)
	# buffer now full; add one more to force wrap
	b.add_sample(timestamp=4)
	all_samples = b.get_all()
	# should have 3 samples and latest should correspond to timestamp 4
	assert len(all_samples) == 3
	# latest is the most recently written position
	latest = b.get_latest()
	fmt = "<I4f4f6f6f6f6f6f"
	ts_latest = struct.unpack(fmt, latest)[0]
	assert ts_latest == 4


def test_sensors_and_housekeeping_monkeypatched(monkeypatch):
	# Monkeypatch hardware classes used in SensorManager and HousekeepingManager
	# Import inside test to apply monkeypatch properly
	import lib.core.sensors as sensors_mod
	import lib.core.housekeeping as hk_mod

	class FakeMAX:
		def __init__(self, i2c, address):
			self.address = address

		def read_temperature(self):
			return 42.0 + (self.address & 0xF)

	class FakeINA:
		def __init__(self, i2c, address):
			self.address = address

		def read_bus_voltage(self):
			return 3.3

		def read_current(self):
			return 0.01

		def read_power(self):
			return 0.033

		def read_die_temperature(self):
			return 25.0

	class DummyI2C:
		def __init__(self, *args, **kwargs):
			pass

		def scan(self):
			# return addresses expected by housekeeping
			return hk_mod.INA238_ADDRESSES + hk_mod.MAX6634_ADDRESSES

	class DummyPin:
		def __init__(self, *args, **kwargs):
			pass

	# Apply monkeypatches
	monkeypatch.setattr(hk_mod, 'INA238', FakeINA)
	monkeypatch.setattr(hk_mod, 'MAX6634', FakeMAX)
	monkeypatch.setattr(hk_mod, 'I2C', DummyI2C)
	monkeypatch.setattr(hk_mod, 'Pin', DummyPin)

	# Sensors module patches
	class FakeTC:
		def __init__(self, spi, cs_pin):
			self.cs_pin = cs_pin

		def read_temperature(self):
			return 100.0 + self.cs_pin

	class FakeADC:
		def __init__(self, spi, cs_pin):
			pass

		def read_pressure(self, channel):
			return 1.234 * (channel + 1)

	class DummySPI:
		def __init__(self, *args, **kwargs):
			pass

	monkeypatch.setattr(sensors_mod, 'MAX31856', FakeTC)
	monkeypatch.setattr(sensors_mod, 'ADS1118', FakeADC)
	monkeypatch.setattr(sensors_mod, 'SPI', DummySPI)
	monkeypatch.setattr(sensors_mod, 'Pin', DummyPin)

	# Now create managers and call read methods
	sm = sensors_mod.SensorManager()
	ts = sm.read_all_temperatures()
	assert len(ts) == 4
	assert all(isinstance(t, float) for t in ts)

	timestamp, temps, pressures = sm.read_sensors()
	assert isinstance(timestamp, int)
	assert len(temps) == 4
	assert len(pressures) == 4

	hm = hk_mod.HousekeepingManager()
	ts_hk = hm.read_all_housekeeping_temperatures()
	assert len(ts_hk) == len(hk_mod.MAX6634_ADDRESSES)

	ina_all = hm.read_all_ina238_data()
	assert len(ina_all) == len(hk_mod.INA238_ADDRESSES)

