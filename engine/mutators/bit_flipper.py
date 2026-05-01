"""
Algorithm 1 — Bit-Flipping Mutator
===================================
Flips a configurable number of random bits within the seed data.
The mutation_ratio controls the fraction of total bits flipped per iteration.

Reference: Manès et al. — "The Art, Science, and Engineering of Fuzzing"
"""

import random
from typing import Optional


class BitFlipper:
    """Flip random bits in the input seed."""

    def __init__(self, mutation_ratio: float = 0.01):
        """
        Args:
            mutation_ratio: Fraction of bits to flip (0.0–1.0). Default 1 %.
        """
        self.mutation_ratio = mutation_ratio
        self.name = "bit_flip"

    def mutate(self, data: bytearray, mutation_ratio: Optional[float] = None) -> bytearray:
        if len(data) == 0:
            return bytearray()

        result = bytearray(data)
        ratio = mutation_ratio if mutation_ratio is not None else self.mutation_ratio

        total_bits = len(result) * 8
        num_flips = max(1, int(total_bits * ratio))

        for _ in range(num_flips):
            bit_pos = random.randint(0, total_bits - 1)
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            result[byte_idx] ^= (1 << bit_idx)

        return result
