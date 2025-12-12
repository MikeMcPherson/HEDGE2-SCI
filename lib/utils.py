# Auto-detect USB connection for CLI
import io
import sys
from machine import Pin


def is_usb_connected():
    """Check if USB is physically connected."""
    try:
        vbus = Pin(24, Pin.IN)
        val = vbus.value()
        return val == 1
    except Exception as e:
        return False


def buffer_crc16(buffer_data):
    """Append CRC16 to buffer data."""
    if not buffer_data:
        return None
    combined = b"".join(buffer_data)
    crc = crc16(combined)
    return combined + crc.to_bytes(2, 'little')


def crc16(data: bytes, poly=0xA001, initial=0xFFFF):
    crc = initial
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    return crc & 0xFFFF
