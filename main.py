import gc
import time
import config
import _thread
from comms import CommManager
from core import SensorManager, HousekeepingManager, Buffer

thread_lock = _thread.allocate_lock()
latest_sample = None

def sensor_acquisition(sensors, housekeeping, buffer):
    """Sensor + Housekeeping acquisition, stores latest sample."""
    global latest_sample
    
    while True:
        ts, temps, pressures = sensors.read_sensors()
        hk_ts, voltages, currents, powers, ina_temps, board_temps = housekeeping.read_all_housekeeping_data()
        sample = (ts, temps, pressures, voltages, currents, powers, ina_temps, board_temps)
        
        buffer.add_sample(
            temperatures=temps,
            pressures=pressures,
            hk_voltages=voltages,
            hk_currents=currents,
            hk_powers=powers,
            hk_ina_temps=ina_temps,
            hk_board_temps=board_temps,
            timestamp=ts
        )
        
        with thread_lock:
            latest_sample = sample
        
        gc.collect()
        
        time.sleep_ms(500)
        

def communications():
    """Reads latest sample sends via CommManager."""
    comms = CommManager()
    global latest_sample
    
    while True:
        sample = None
        with thread_lock:
            if latest_sample is not None:
                sample = latest_sample
        
        if sample:
            ts, temps, pressures, voltages, currents, powers, ina_temps, board_temps = sample
            comms.send_data(sample)
        
        time.sleep_ms(10)


def cli(buffer, housekeeping, sensors):
    """CLI for debugging, calibration, and self-test."""
    cli = CLIInterface(sensors, housekeeping, buffer)
    cli.run()


def main():
    sensors = SensorManager()
    housekeeping = HousekeepingManager()
    buffer = Buffer(capacity=120)
    
    _thread.start_new_thread(comm_task, ())
    
    if config.ENABLE_CLI:
        _thread.start_new_thread(cli_task, (sensors, housekeeping, buffer))
    
    acquisition_task(sensors, housekeeping, buffer)


if __name__ == "__main__":
    main()
