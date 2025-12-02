# Auto-detect USB connection for CLI
import sys


def is_usb_connected():
    """Check if USB serial is connected."""
    try:
        return sys.stdin is not None and hasattr(sys.stdin, 'read')
    except:
        return False


def buffer_crc16(buffer_data):
    if not buffer_data:
        return None

    # Concatenate all byte strings into one block
    combined = b"".join(buffer_data)

    # Compute CRC16 over the combined data
    return crc16(combined)


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
