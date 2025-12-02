import struct
import pytest

from lib.comms.cli import CLI
from lib.core.buffer import Buffer


class FakeSensors:
	def read_sensors(self):
		return 123, [1.0, 2.0, 3.0, 4.0], [0.1, 0.2, 0.3, 0.4]


class FakeHousekeeping:
	def read_all_housekeeping_data(self):
		# timestamp, ina_data, max_temps
		ina = [(3.3, 0.01, 0.033, 25.0)] * 5
		max_temps = [30.0] * 5
		return 123, ina, max_temps


def test_help_and_version(capsys):
	buf = Buffer(capacity=4)
	cli = CLI(FakeSensors(), FakeHousekeeping(), buf)

	cli.cmd_help([])
	captured = capsys.readouterr()
	assert "Available commands" in captured.out

	cli.cmd_version([])
	captured = capsys.readouterr()
	assert "Firmware" in captured.out


def test_buffer_dump_and_erase(capsys):
	buf = Buffer(capacity=4)
	cli = CLI(FakeSensors(), FakeHousekeeping(), buf)

	# buffer empty -> dump prints empty message
	cli.cmd_dump([])
	captured = capsys.readouterr()
	assert "Buffer is empty" in captured.out

	# add a sample and test dump
	added = buf.add_sample()
	assert added is True
	assert buf.size() == 1

	cli.cmd_buffer([])
	captured = capsys.readouterr()
	assert "Capacity" in captured.out

	cli.cmd_dump([])
	captured = capsys.readouterr()
	assert "Science Data Dump" in captured.out

	# erase buffer
	cli.cmd_erase([])
	assert buf.size() == 0


def test_cli_buffer_full_and_dump_multiple(capsys):
	buf = Buffer(capacity=3)
	cli = CLI(FakeSensors(), FakeHousekeeping(), buf)

	# fill buffer
	for _ in range(3):
		buf.add_sample()

	# buffer should be full
	assert buf.is_full()

	# cmd_buffer should report capacity and size
	cli.cmd_buffer([])
	captured = capsys.readouterr()
	assert "Capacity" in captured.out
	assert "Size" in captured.out or "Samples" in captured.out

	# cmd_dump should show the dump header and at least one sample
	cli.cmd_dump([])
	captured = capsys.readouterr()
	assert "Science Data Dump" in captured.out

	# Erase should clear buffer
	cli.cmd_erase([])
	assert buf.size() == 0

