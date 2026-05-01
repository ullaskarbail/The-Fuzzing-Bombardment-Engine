"""
Algorithm 4 — Dictionary-Based (Semantic) Mutator
===================================================
Injects predefined values with heavy "semantic weight" — boundary
integers, format-string exploits, and overflow payloads — into the
seed at random positions or by replacing existing tokens.

Reference: Manès et al. — "The Art, Science, and Engineering of Fuzzing"
"""

import random
import struct
from typing import Optional


class DictionaryMutator:
    """Inject known-dangerous values into the input."""

    # ── payload dictionaries ────────────────────────────────────
    INTEGER_PAYLOADS = [
        0, 1, -1,
        0x7F, 0x80, 0xFF,
        0x7FFF, 0x8000, 0xFFFF,
        0x7FFFFFFF, 0x80000000, 0xFFFFFFFF,
        0x100, 0x1000, 0x10000,
    ]

    FORMAT_STRING_PAYLOADS = [
        b"%s", b"%n", b"%x", b"%p", b"%d",
        b"%s" * 10,
        b"%n" * 10,
        b"%x" * 10,
        b"%.9999999s",
        b"AAAA" + b"%08x." * 10 + b"%n",
    ]

    OVERFLOW_PAYLOADS = [
        b"A" * 64,
        b"A" * 128,
        b"A" * 256,
        b"A" * 512,
        b"A" * 1024,
        b"\x00" * 256,
        b"\xff" * 256,
        b"../" * 64,
    ]

    SPECIAL_PAYLOADS = [
        b"\x00",
        b"\n" * 64,
        b"\r\n" * 64,
        b"\t" * 64,
        b"\\" * 128,
    ]

    def __init__(self):
        self.name = "dictionary"
        self._all_payloads = (
            self.FORMAT_STRING_PAYLOADS
            + self.OVERFLOW_PAYLOADS
            + self.SPECIAL_PAYLOADS
        )

    def mutate(self, data: bytearray, strategy: Optional[str] = None) -> bytearray:
        """
        Apply a dictionary mutation.

        Strategies:
            'replace'  — overwrite a random slice with a payload
            'inject'   — insert a payload at a random position
            'integer'  — overwrite 4 bytes with a boundary integer
        """
        strat = strategy or random.choice(["replace", "inject", "integer"])

        if strat == "integer":
            return self._inject_integer(data)
        elif strat == "inject":
            return self._inject_payload(data)
        else:
            return self._replace_payload(data)

    def _inject_payload(self, data: bytearray) -> bytearray:
        result = bytearray(data)
        payload = random.choice(self._all_payloads)
        pos = random.randint(0, max(0, len(result)))
        result[pos:pos] = payload
        return result

    def _replace_payload(self, data: bytearray) -> bytearray:
        if len(data) == 0:
            return bytearray(random.choice(self._all_payloads))
        result = bytearray(data)
        payload = random.choice(self._all_payloads)
        pos = random.randint(0, max(0, len(result) - 1))
        end = min(pos + len(payload), len(result))
        result[pos:end] = payload
        return result

    def _inject_integer(self, data: bytearray) -> bytearray:
        val = random.choice(self.INTEGER_PAYLOADS)
        packed = struct.pack(">I", val & 0xFFFFFFFF)  # always unsigned, always safe
        if len(data) < 4:
            return bytearray(data) + packed
        result = bytearray(data)
        pos = random.randint(0, len(result) - 4)
        result[pos : pos + 4] = packed
        return result
