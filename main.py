import gc
import time
import utils
import config
import _thread
from comms import RS485, SpaceCAN, CLI
from core import SensorManager, HousekeepingManager, Buffer

thread_lock = _thread.allocate_lock()


def sensor_acquisition(sensors, housekeeping, buffer):
    """Sensor + Housekeeping acquisition, stores latest sample."""
    while True:
        timestamp1, temperatures, pressures = sensors.read_sensors()
        timestamp2, ina238_data, hk_temperatures = housekeeping.read_all_housekeeping_data()
        voltages, currents, powers, ina_temps = map(list, zip(*ina238_data))

        with thread_lock:
            buffer.add_sample(
                timestamp=timestamp1,
                temperatures=temperatures,
                pressures=pressures,
                hk_voltages=voltages,
                hk_currents=currents,
                hk_powers=powers,
                hk_temps=hk_temperatures,
                hk_ina_temps=ina_temps
            )

        gc.collect()

        time.sleep_ms(500)


def communications(sensors, housekeeping, buffer):
    """Reads buffer, sends it, and initializes CLI if USB is plugged in"""
    comms = RS485(baudrate=115200)
    last_usb_state = False

    while True:
        sample = None
        with thread_lock:
            sample = buffer.get_all()

        if sample:
            comms.send(sample)

        time.sleep_ms(10)

        usb_state = utils.is_usb_connected()
        if usb_state and not last_usb_state:
            print("\n=== USB Connected - Starting CLI ===")

            try:
                cli = CLI(sensors, housekeeping, buffer)
                cli.run()
            except Exception as e:
                print(f"CLI error: {e}")
            finally:
                print("=== CLI Stopped ===")

        last_usb_state = usb_state
        time.sleep_ms(10)


def main():
    sensors = SensorManager()
    housekeeping = HousekeepingManager()
    buffer = Buffer(capacity=120)

    _thread.start_new_thread(communications, (sensors, housekeeping, buffer))  # Core 1
    sensor_acquisition(sensors, housekeeping, buffer)  # Core 0


if __name__ == "__main__":
    main()
