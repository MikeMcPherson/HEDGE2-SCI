from machine import SPI, Pin
import time

CMD_RESET = 0x00
CMD_READ = 0x03
CMD_WRITE = 0x02
REG_CiCON = 0x000
REG_CiTXQCON = 0x050

class SpaceCAN:
    def __init__(self, cs_pin=1, int_pin=4, silent_pin=8, sck=2, mosi=3, miso=16):
        """Initialize SpaceCAN interface."""
        self.spi = SPI(0, baudrate=125_000, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        self.cs = Pin(cs_pin, Pin.OUT, value=1)
        self.int_pin = Pin(int_pin, Pin.IN)
        self.silent_mode = Pin(silent_pin, Pin.OUT, value=0)

        self.reset()
        self.write_reg(REG_CiCON + 3, 0x00)  # Normal mode
        self.write_reg(REG_CiCON + 2, 0x01)  # Enable TXQ
        print("SpaceCAN initialized.")

    def transfer(self, cmd, addr, data=None, read_len=0):
        self.cs.value(0)
        self.spi.write(bytearray([cmd, (addr >> 8) & 0xFF, addr & 0xFF]))
        if data:
            self.spi.write(bytearray(data))
        result = self.spi.read(read_len) if read_len > 0 else None
        self.cs.value(1)
        return result

    def reset(self):
        print("Resetting MCP2518FD")
        self.transfer(CMD_RESET, 0x000)
        time.sleep(0.01)

    def write_reg(self, addr, value):
        self.transfer(CMD_WRITE, addr, [value & 0xFF])

    def read_reg(self, addr):
        return self.transfer(CMD_READ, addr, read_len=1)[0]

    def send_frame(self, tx_id, tx_data):
        if len(tx_id) != 4:
            raise ValueError("tx_id must be 4 bytes")
        if len(tx_data) > 8:
            raise ValueError("tx_data cannot exceed 8 bytes")
        self.transfer(CMD_WRITE, 0x400, tx_id + tx_data)
        self.write_reg(REG_CiTXQCON + 1, 0x01)
        print("CAN Frame queued for transmission.")

    def check_interrupt(self):
        if self.int_pin.value() == 0:
            print("CAN interrupt asserted: message received or event occurred.")
            return True
        return False

    def set_silent_mode(self, enable=True):
        self.silent_mode.value(1 if enable else 0)
        print("Silent mode:", "ON" if enable else "OFF")


if __name__ == '__main__':
    can = SpaceCAN()
    tx_id = [0x00, 0x00, 0x01, 0x23]
    tx_data = [i for i in range(8)]
    can.send_frame(tx_id, tx_data)
    time.sleep(0.1)
    can.check_interrupt()
