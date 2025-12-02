import sys
import time
import struct
import machine
import lib.calibration as calibration


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
        self.register("cal-show", self.cmd_cal_show, "Show calibration offsets")
        self.register("cal-start", self.cmd_cal_start, "Begin calibration for channel")
        self.register("cal-set", self.cmd_cal_set, "Set calibration point")
        self.register("cal-reset", self.cmd_cal_reset, "Reset calibration")
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
            print("Streaming mode. Press Ctrl+C to stop.\n")
            try:
                while True:
                    timestamp, temperatures, pressures = self.sensors.read_sensors()
                    temps_str = ' '.join([f'{t:.2f}C' for t in temperatures])
                    press_str = ' '.join([f'{p:.3f}' for p in pressures])
                    print(f"\r{timestamp} | T: {temps_str} | P: {press_str}", end='')
                    time.sleep_ms(500)
            except KeyboardInterrupt:
                print("\n\nStreaming stopped.\n")
                return

        timestamp, temperatures, pressures = self.sensors.read_sensors()

        print(f"Timestamp:\t{timestamp}")
        print(f"Temperatures:\t{['{:.2f}C'.format(t) for t in temperatures]}")
        print(f"Pressures:\t{['{:.3f}?'.format(p) for p in pressures]}")
        print("\n=== END STATUS ===\n")

    def cmd_hk(self, args):
        print("\n=== HOUSEKEEPING STATUS ===\n")
        if args and args[0] == "--stream":
            print("Streaming mode. Press Ctrl+C to stop.\n")
            try:
                while True:
                    timestamp, ina238_data, temperatures = self.housekeeping.read_all_housekeeping_data()
                    voltages, currents, powers, ina_temps = map(list, zip(*ina238_data))
                    v_str = ' '.join([f'{v:.2f}V' for v in voltages])
                    i_str = ' '.join([f'{i:.2f}A' for i in currents])
                    print(f"\r{timestamp} | V: {v_str} | I: {i_str}", end='')
                    time.sleep_ms(500)
            except KeyboardInterrupt:
                print("\n\nStreaming stopped.\n")
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

        print("\n=== END DUMP ===\n")

    def cmd_erase(self, args):
        self.buffer.clear()
        print("BUFFER ERASED")

    def cmd_cal_show(self, args):
        """Display current calibration offsets."""
        print("\n=== Current Calibration Offsets ===\n")

        offsets = [("Temperatures", calibration.TEMP_OFFSETS), ("Pressures", calibration.PRESSURE_OFFSETS)]

        for name, values in offsets:
            print(f"{name}:")
            for i, offset in enumerate(values):
                marker = " *" if offset != 0.0 else ""
                print(f"Channel {i}: {offset:+.4f}{marker}")
            print()

        print("(* = non-zero offset)")
        print("\n=== END ===\n")

    def _update_cal(self, var_name, channel, offset):
        """Update calibration.py and reload."""
        with open("lib/calibration.py", "r") as f:
            lines = f.readlines()

        current = list(getattr(calibration, var_name))
        current[channel] = offset

        for i, line in enumerate(lines):
            if line.strip().startswith(f"{var_name} = ["):
                lines[i] = f"{var_name} = [{', '.join([str(v) for v in current])}]\n"
                break

        with open("lib/calibration.py", "w") as f:
            f.writelines(lines)

    def cmd_cal_start(self, args):
        """Interactive calibration walkthrough."""
        print("\n=== Interactive Calibration ===\n")

        timestamp, temperatures, pressures = self.sensors.read_sensors()

        print("--- Temperatures ---")
        for i, temp in enumerate(temperatures):
            while True:
                print(f"Temp[{i}] = {temp:.2f}C (offset: {calibration.TEMP_OFFSETS[i]:+.2f})")
                offset_str = input("New offset [Enter to skip]: ").strip()
                if offset_str:
                    try:
                        self._update_cal("TEMP_OFFSETS", i, float(offset_str))
                        print("Set")
                        break
                    except:
                        print("Invalid")
                else:
                    break

        print("--- Pressures ---")
        for i, pressure in enumerate(pressures):
            while True:
                print(f"Pressure[{i}] = {pressure:.3f} (offset: {calibration.PRESSURE_OFFSETS[i]:+.3f})")
                offset_str = input("New offset [Enter to skip]: ").strip()
                if offset_str:
                    try:
                        self._update_cal("PRESSURE_OFFSETS", i, float(offset_str))
                        print(f"Set")
                        break
                    except:
                        print("Invalid")
                else:
                    break

        print("Done. Rebooting in 2 seconds...")
        time.sleep_ms(2000)
        machine.reset()

    def cmd_cal_set(self, args):
        """Set specific: cal-set <type> <ch> <offset>"""
        if len(args) < 3:
            print("Usage: cal-set <type> <channel> <offset>")
            print("Types: temperature, pressure")
            return

        type_map = {
            "temperature": ("TEMP_OFFSETS", 4),
            "pressure": ("PRESSURE_OFFSETS", 4),
        }

        if args[0] not in type_map:
            print("Invalid type. Valid: temperature, pressure")
            return

        var_name, max_ch = type_map[args[0]]
        ch = int(args[1])
        offset = float(args[2])

        if ch < 0 or ch >= max_ch:
            print(f"Invalid channel. Valid: 0-{max_ch - 1}")
            return

        self._update_cal(var_name, ch, offset)
        print(f"Set {args[0]}[{ch}] = {offset:+.4f}")
        print("Rebooting in 2 seconds...")
        time.sleep_ms(2000)
        machine.reset()

    def cmd_cal_reset(self, args):
        """Reset all calibration offsets to zero."""
        print("WARNING: This will reset ALL calibration offsets to zero.")

        try:
            content = """# HEDGE-2 SCI Board - Calibration Offsets
            # This file is auto-generated and updated by CLI calibration commands

            # Temperature offsets (4 thermocouples)
            TEMP_OFFSETS = [0.0, 0.0, 0.0, 0.0]
    
            # Pressure offsets (4 pressure sensors)
            PRESSURE_OFFSETS = [0.0, 0.0, 0.0, 0.0]
            """

            with open("lib/calibration.py", "w") as f:
                f.write(content)

            print("All calibration offsets reset to zero!")
            print("Rebooting in 2 seconds...")
            time.sleep_ms(2000)
            machine.reset()
        except Exception as e:
            print(f"Error resetting calibration: {e}")

    def cmd_self_test(self, args):
        print("\n=== SELF TEST ===\n")

        passed = 0
        failed = 0

        try:
            timestamp, temperatures, pressures = self.sensors.read_sensors()

            print("Testing temperature sensors...")
            for i, temp in enumerate(temperatures):
                if -100 < temp < 300:
                    print(f"Temp[{i}]: {temp:.2f}C - PASS")
                    passed += 1
                else:
                    print(f"Temp[{i}]: {temp:.2f}C - FAIL (out of range)")
                    failed += 1

            print("\nTesting pressure sensors...")
            for i, pressure in enumerate(pressures):
                if -0.5 < pressure < 5:
                    print(f"Pressure[{i}]: {pressure:.3f} - PASS")
                    passed += 1
                else:
                    print(f"Pressure[{i}]: {pressure:.3f} - FAIL (out of range)")
                    failed += 1
        except Exception as e:
            print(f"All sensors - FAIL: {e}")
            failed += 8

        print("\nTesting housekeeping sensors...")
        try:
            timestamp, ina238_data, hk_temps = self.housekeeping.read_all_housekeeping_data()
            for i, (voltage, current, power, ina_temp) in enumerate(ina238_data):
                v_ok = 0 < voltage < 30
                i_ok = -10 < current < 20
                p_ok = 0 < power < 600
                t_ok = -40 < ina_temp < 125

                if v_ok and i_ok and p_ok and t_ok:
                    print(f"INA238[{i}]: {voltage:.2f}V {current:.2f}A {power:.2f}W {ina_temp:.1f}C - PASS")
                    passed += 1
                else:
                    status = []
                    if not v_ok:
                        status.append("V")
                    if not i_ok:
                        status.append("I")
                    if not p_ok:
                        status.append("P")
                    if not t_ok:
                        status.append("T")
                    print(f"INA238[{i}]: {voltage:.2f}V {current:.2f}A {power:.2f}W {ina_temp:.1f}C - FAIL ({','.join(status)})")
                    failed += 1

            for i, temp in enumerate(hk_temps):
                if -100 < temp < 150:
                    print(f"MAX6634[{i}]: {temp:.1f}C - PASS")
                    passed += 1
                else:
                    print(f"MAX6634[{i}]: {temp:.1f}C - FAIL (out of range)")
                    failed += 1
        except Exception as e:
            print(f"Housekeeping - FAIL: {e}")
            failed += 12

        print("\nTesting buffer...")
        try:
            size = self.buffer.size()
            capacity = self.buffer.capacity
            if capacity > 0:
                print(f"Buffer: {size}/{capacity} - PASS")
                passed += 1
            else:
                print(f"Buffer: Invalid capacity - FAIL")
                failed += 1
        except Exception as e:
            print(f"Buffer - FAIL: {e}")
            failed += 1

        print(f"\n=== RESULTS ===")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Total:  {passed + failed}")

        if failed == 0:
            print("\nALL TESTS PASSED\n")
        else:
            print(f"\n{failed} TEST(S) FAILED\n")

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
