import sys
import time
import struct
import machine


class CLI:
    def __init__(self, sensors, housekeeping, buffer):
        self.commands = {}
        self.register_commands()
        self.sensors = sensors
        self.housekeeping = housekeeping
        self.buffer = buffer

    def register(self, name, handler, help_text=""):
        """Register a CLI command."""
        self.commands[name] = (handler, help_text)

    def register_commands(self):
        self.register("help", self.cmd_help, "Show available commands")
        self.register("status", self.cmd_status, "System summary")
        self.register("sensors", self.cmd_sensors, "Read science sensors (use --stream to loop)")
        self.register("hk", self.cmd_hk, "Read housekeeping sensors (use --stream to loop)")
        self.register("buffer", self.cmd_buffer, "Show buffer usage")
        self.register("dump", self.cmd_dump, "Dump all buffer samples")
        self.register("erase", self.cmd_erase, "Erase buffer")
        self.register("cal-start", self.cmd_cal_start, "Begin calibration for channel")
        self.register("cal-set", self.cmd_cal_set, "Set calibration point")
        self.register("cal-save", self.cmd_cal_save, "Save calibration to flash")
        self.register("cal-reset", self.cmd_cal_reset, "Reset calibration")
        self.register("set-rate", self.cmd_set_rate, "Set sampling rates")
        self.register("self-test", self.cmd_self_test, "Run self-test")
        self.register("version", self.cmd_version, "Firmware version")
        self.register("reboot", self.cmd_reboot, "Reboot the board")

    def run(self):
        print("SCIENCE PCB CLI Ready.\nType 'help' for commands.\n")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    continue

                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                cmd = parts[0]
                args = parts[1:]

                if cmd in self.commands:
                    handler, _ = self.commands[cmd]
                    handler(args)
                else:
                    print("Unknown command. Type 'help'.")

            except Exception as e:
                print("Error:", e)

    def cmd_help(self, args):
        print("\nAvailable commands:\n")
        for name, (_, help_text) in self.commands.items():
            print(f"  {name:<15} - {help_text}")
        print()

    def cmd_status(self, args):
        print("\n=== SCIENCE PCB SYSTEM STATUS ===\n")

        # Buffer status
        buf_size = self.buffer.size()
        buf_capacity = self.buffer.capacity
        buf_percent = (buf_size / buf_capacity * 100) if buf_capacity > 0 else 0

        print(f"Buffer: {buf_size}/{buf_capacity} samples ({buf_percent:.1f}%)")

        # Latest sensor readings
        try:
            timestamp, temperatures, pressures = self.sensors.read_sensors()
            print(f"\nScience Sensors (Latest):")
            print(f"Temperatures:\t{['{:.2f}C'.format(t) for t in temperatures]}")
            print(f"Pressures:\t{['{:.3f}?'.format(p) for p in pressures]}")
        except Exception as e:
            print(f"\nScience Sensors: Error - {e}")

        # Latest housekeeping
        try:
            timestamp, ina_data, max_temps = self.housekeeping.read_all_housekeeping_data()
            print(f"\nHousekeeping (Latest):")
            avg_voltage = sum(v for v, _, _, _ in ina_data) / len(ina_data) if ina_data else 0
            total_power = sum(p for _, _, p, _ in ina_data)
            print(f"Avg Voltage:\t{avg_voltage:.2f}V")
            print(f"Total Power:\t{total_power:.2f}W")
            print(f"Temperatures:\t{['{:.1f}C'.format(t) for t in max_temps]}")
        except Exception as e:
            print(f"\nHousekeeping: Error - {e}")

        print("\n=== END STATUS ===\n")

    def cmd_sensors(self, args):
        print("\n=== SENSORS STATUS ===\n")
        if args and args[0] == "--stream":
            print("Streaming mode not implemented yet")
            return

        timestamp, temperatures, pressures = self.sensors.read_sensors()

        print(f"Timestamp:\t{timestamp}")
        print(f"Temperatures:\t{['{:.2f}C'.format(t) for t in temperatures]}")
        print(f"Pressures:\t{['{:.3f}?'.format(p) for p in pressures]}")
        print("\n=== END STATUS ===\n")

    def cmd_hk(self, args):
        print("\n=== HOUSEKEEPING STATUS ===\n")
        if args and args[0] == "--stream":
            print("Streaming mode not implemented yet")
            return

        timestamp, ina238_data, temperatures = self.housekeeping.read_all_housekeeping_data()
        voltages, currents, powers, ina_temps = map(list, zip(*ina238_data))

        print(f"Timestamp:\t{timestamp}")
        print(f"HK Voltages:\t{['{:.3f}V'.format(v) for v in voltages]}")
        print(f"HK Currents:\t{['{:.3f}A'.format(i) for i in currents]}")
        print(f"HK Powers:\t{['{:.3f}W'.format(p) for p in powers]}")
        print(f"HK Temps:\t{['{:.1f}C'.format(t) for t in temperatures]}")
        print(f"HK INA Temps:\t{['{:.1f}C'.format(t) for t in ina_temps]}")
        print("\n=== END STATUS ===\n")

    def cmd_buffer(self, args):
        size = self.buffer.size()
        capacity = self.buffer.capacity
        percentage = (size / capacity * 100) if capacity > 0 else 0
        is_full = self.buffer.is_full()

        print("\n=== Buffer Status ===")
        print(f"Capacity:\t{capacity} samples")
        print(f"Used:\t\t{size} samples")
        print(f"Free:\t\t{capacity - size} samples")
        print(f"Usage:\t\t{percentage:.1f}%")
        print(f"Status:\t\t{'FULL' if is_full else 'OK'}")
        print("\n=== END STATUS ===\n")

    def cmd_dump(self, args):
        samples = self.buffer.get_all()

        if not samples:
            print("Buffer is empty.")
            return

        print(f"\n=== Science Data Dump ({len(samples)} samples) ===\n")

        fmt = "<I4f4f6f6f6f6f6f"

        for idx, packed_data in enumerate(samples):
            if not packed_data:
                continue

            try:
                unpacked = struct.unpack(fmt, packed_data)
                timestamp = unpacked[0]
                temps = unpacked[1:5]
                pressures = unpacked[5:9]
                hk_voltages = unpacked[9:15]
                hk_currents = unpacked[15:21]
                hk_powers = unpacked[21:27]
                hk_temps = unpacked[27:33]
                hk_ina_temps = unpacked[33:39]

                print(f"Sample #{idx} | Timestamp: {timestamp} ms")
                print(f"Temperatures:\t{['{:.2f}'.format(t) for t in temps]}")
                print(f"Pressures:\t{['{:.3f}'.format(p) for p in pressures]}")
                print(f"HK Voltages:\t{['{:.3f}V'.format(v) for v in hk_voltages]}")
                print(f"HK Currents:\t{['{:.3f}A'.format(i) for i in hk_currents]}")
                print(f"HK Powers:\t{['{:.3f}W'.format(p) for p in hk_powers]}")
                print(f"HK Temps:\t{['{:.1f}C'.format(t) for t in hk_temps]}")
                print(f"HK INA Temps:\t{['{:.1f}C'.format(t) for t in hk_ina_temps]}")
                print()

            except Exception as e:
                print(f"Error unpacking sample #{idx}: {e}")

        print("=== END DUMP ===\n")

    def cmd_erase(self, args):
        self.buffer.clear()
        print("BUFFER ERASED")

    def cmd_cal_start(self, args):
        # TODO: implement
        print("Calibration start not implemented")

    def cmd_cal_set(self, args):
        # TODO: implement
        print("Calibration set not implemented")

    def cmd_cal_save(self, args):
        # TODO: implement
        print("Calibration save not implemented")

    def cmd_cal_reset(self, args):
        # TODO: implement
        print("Calibration reset not implemented")

    def cmd_set_rate(self, args):
        # TODO: implement
        print("Set rate not implemented")

    def cmd_self_test(self, args):
        # TODO: implement
        print("Self-test not implemented")

    def cmd_version(self, args):
        print("\n=== Firmware Information ===")
        print("Board:\t\tHEDGE-2 Science PCB")
        print("Firmware:\tv1.0.0")
        print("Build Date:\t2025-11-##")
        print(f"MicroPython:\t{sys.version}")
        print()

    def cmd_reboot(self, args):
        print("Rebooting...")
        time.sleep_ms(200)
        machine.reset()
