"""Persist the parking stop distance in microcontroller NVM.

Layout, 4 bytes total:
    offset 0: magic byte 0x67
    offset 1: format version 0x01
    offset 2-3: stop distance, uint16 little-endian, millimetres
"""

MAGIC = 0x67
VERSION = 0x01
NVM_BYTES = 4


def encode(stop_mm):
    """Return a 4-byte record for stop_mm. Raises ValueError if out of range."""
    if stop_mm < 0 or stop_mm > 0xFFFF:
        raise ValueError("stop_mm out of uint16 range")
    return bytes((MAGIC, VERSION, stop_mm & 0xFF, (stop_mm >> 8) & 0xFF))


def decode(raw):
    """Return the stop distance in mm, or None if the record is absent/unreadable."""
    if raw is None or len(raw) < NVM_BYTES:
        return None
    if raw[0] != MAGIC or raw[1] != VERSION:
        return None
    return raw[2] | (raw[3] << 8)


def load(nvm):
    """Read the stop distance from an NVM-like bytearray, or None if unset."""
    return decode(bytes(nvm[0:NVM_BYTES]))


def save(nvm, stop_mm):
    """Write the stop distance in a single assignment (one flash erase/write)."""
    nvm[0:NVM_BYTES] = encode(stop_mm)
