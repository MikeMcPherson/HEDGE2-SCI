import gc
import sys
import time
import utils
import _thread
from machine import Pin
from comms import RS485, SpaceCAN, CLI
from core import SensorManager, HousekeepingManager, Buffer

thread_lock = _thread.allocate_lock()
interval_ms = 500  # 2 Hz
power_led = Pin(0, Pin.OUT)
status_led = Pin(11, Pin.OUT)
_exit_requested = False


def sensor_acquisition(sensors, housekeeping, buffer):
    """Sensor + Housekeeping acquisition, stores latest sample."""
    global _exit_requested
    try:
        while not _exit_requested:
            start = time.ticks_ms()
            timestamp1, temperatures, pressures = sensors.read_sensors()
            timestamp2, ina238_data, hk_temperatures = housekeeping.read_all_housekeeping_data()
            voltages, currents, powers, ina_temps = map(list, zip(*ina238_data))

            with thread_lock:
                buffer.add_sample(
                    timestamp=timestamp1,
                    temperatures=temperatures,
                    pressures=pressures,
                    hk_temps=hk_temperatures,
                    hk_voltages=voltages,
                    hk_currents=currents,
                    hk_powers=powers,
                    hk_ina_temps=ina_temps
                )

            gc.collect()

            elapsed = time.ticks_diff(time.ticks_ms(), start)
            sleep_time = max(0, interval_ms - elapsed)
            time.sleep_ms(sleep_time)

    except Exception as e:
        power_led.value(0)
        raise


def communications(sensors, housekeeping, buffer):
    """Reads buffer, sends it, and initializes CLI if USB is plugged in"""
    global _exit_requested

    try:
        comms = RS485(baudrate=115200)
    except Exception as e:
        for _ in range(10):
            print(f"RS485 Initialization Error: {e}")
            status_led.value(not status_led.value())
            time.sleep_ms(1000)
        raise

    try:
        while not _exit_requested:
            usb_state = utils.is_usb_connected()
            if usb_state:
                print("\n=== USB Connected - Starting CLI ===")

                try:
                    cli = CLI(sensors, housekeeping, buffer, thread_lock)
                    cli.run()
                except Exception as e:
                    print(f"CLI error: {e}")
                finally:
                    print("=== CLI Stopped ===")

            sample = None
            with thread_lock:
                samples = buffer.get_all()
                if samples:
                    sample = utils.buffer_crc16(samples)

            if sample:
                status_led.value(1)
                comms.send(sample)
                time.sleep_ms(50)
                status_led.value(0)

    except Exception as e:
        print(f"Communications thread error: {e}")
        while True:
            status_led.value(not status_led.value())
            time.sleep_ms(2000)


def main():
    try:
        power_led.value(1)
        sensors = SensorManager()
        housekeeping = HousekeepingManager()
        buffer = Buffer(capacity=120)

        _thread.start_new_thread(communications, (sensors, housekeeping, buffer))  # Core 1
        sensor_acquisition(sensors, housekeeping, buffer)  # Core 0

    except Exception as e:
        print(f"Fatal error in main: {e}")
        while True:
            power_led.value(not power_led.value())
            status_led.value(not status_led.value())
            time.sleep_ms(500)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. Stopping threads...")
        _exit_requested = True
        power_led.value(0)
        time.sleep(1)
        print("Entering REPL.")
        sys.exit()


