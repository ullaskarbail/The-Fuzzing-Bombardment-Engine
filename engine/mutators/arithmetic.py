"""
Algorithm 2 — Arithmetic Mutator
=================================
Isolates byte sequences, interprets them as integers, and applies
small perturbations (i ± r) to hunt for off-by-one errors and
integer overflows.  The bounding rule constrains r to [0, max_delta).

Reference: Manès et al. — "The Art, Science, and Engineering of Fuzzing"
"""

import random
import struct
from typing import Optional


class ArithmeticMutator:
    """Apply small arithmetic perturbations to integer values in the input."""

    # (width_bytes, unsigned_fmt, signed_fmt)
    WIDTHS = [
        (1, "B", "b"),
        (2, ">H", ">h"),
        (4, ">I", ">i"),
    ]

    def __init__(self, max_delta: int = 35, num_operations: int = 1):
        """
        Args:
            max_delta: Upper bound for the perturbation value r.
            num_operations: How many independent mutations per call.
        """
        self.max_delta = max_delta
        self.num_operations = num_operations
        self.name = "arithmetic"

    def mutate(self, data: bytearray, max_delta: Optional[int] = None) -> bytearray:
        if len(data) < 1:
            return bytearray()

        result = bytearray(data)
        delta = max_delta if max_delta is not None else self.max_delta

        for _ in range(self.num_operations):
            valid = [(w, uf) for w, uf, _ in self.WIDTHS if w <= len(result)]
            if not valid:
                continue

            width, fmt = random.choice(valid)
            pos = random.randint(0, len(result) - width)

            current = struct.unpack_from(fmt, result, pos)[0]
            r = random.randint(0, delta - 1)
            new_val = current + r if random.random() < 0.5 else current - r

            max_val = (1 << (width * 8)) - 1
            new_val = max(0, min(new_val, max_val))

            struct.pack_into(fmt, result, pos, new_val)

        return result
