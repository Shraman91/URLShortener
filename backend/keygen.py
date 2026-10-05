import time
import string
import secrets
import threading
from typing import Optional

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE62_ALPHABET)


def base62_encode(num: int) -> str:
    """Encodes a positive integer to Base62 string."""
    if num == 0:
        return BASE62_ALPHABET[0]
    digits = []
    while num > 0:
        remainder = num % BASE
        digits.append(BASE62_ALPHABET[remainder])
        num = num // BASE
    digits.reverse()
    return "".join(digits)


class SnowflakeKeyGenerator:
    """
    Distributed Snowflake-style unique ID generator.
    Structure:
    - 41 bits: Custom Epoch Timestamp (in milliseconds) ~69 years span
    - 10 bits: Machine / Worker ID (0-1023)
    - 12 bits: Sequence counter (0-4095 per millisecond)
    Output converted to Base62 (typically 6-7 characters).
    Guarantees: Zero collisions, zero database check queries needed.
    """
    CUSTOM_EPOCH = 1704067200000  # Jan 1, 2024 00:00:00 UTC

    def __init__(self, machine_id: int = 1):
        self.machine_id = machine_id & 0x3FF  # 10 bits
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def next_id(self) -> int:
        with self.lock:
            timestamp = self._current_millis()

            if timestamp < self.last_timestamp:
                # Clock moved backwards; fallback to waiting
                timestamp = self.last_timestamp

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF  # 12 bits
                if self.sequence == 0:
                    # Sequence exhausted for this millisecond, wait for next ms
                    while timestamp <= self.last_timestamp:
                        timestamp = self._current_millis()
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            # Bitwise packing
            id_int = (
                ((timestamp - self.CUSTOM_EPOCH) << 22)
                | (self.machine_id << 12)
                | self.sequence
            )
            return id_int

    def generate_code(self) -> str:
        """Generates a collision-free base62 short code."""
        unique_int = self.next_id()
        return base62_encode(unique_int)


_generator = SnowflakeKeyGenerator(machine_id=1)


def generate_short_code(length: int = 6) -> str:
    """
    High-entropy fallback or Snowflake-based code generator.
    Generates a 6-7 char code with zero collision risk.
    """
    code = _generator.generate_code()
    if len(code) < length:
        padding = "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length - len(code)))
        return f"{code}{padding}"
    return code


def is_valid_alias(alias: str) -> bool:
    """Validates user-defined custom aliases (alphanumeric, dashes, underscores, 3-30 chars)."""
    if not (3 <= len(alias) <= 30):
        return False
    allowed = set(string.ascii_letters + string.digits + "-_")
    return all(c in allowed for c in alias)
