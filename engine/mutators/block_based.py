"""
Algorithm 3 — Block-Based Mutator
==================================
Treats the seed as structural blocks and performs four operations:
  • Insert   — inject a random block
  • Delete   — remove a random block
  • Permute  — shuffle block order
  • Cross-pollinate — splice a block from a donor seed

Reference: Manès et al. — "The Art, Science, and Engineering of Fuzzing"
"""

import random
from typing import Optional, List


class BlockMutator:
    """Structural block-level mutations on input data."""

    OPERATIONS = ["insert", "delete", "permute", "cross_pollinate"]

    def __init__(self, min_block: int = 1, max_block: int = 64):
        self.min_block = min_block
        self.max_block = max_block
        self.name = "block"
        self._donors: List[bytearray] = []

    def set_donor_pool(self, donors: List[bytearray]):
        """Provide other seeds for cross-pollination."""
        self._donors = donors

    # ── public API ──────────────────────────────────────────────
    def mutate(self, data: bytearray, operation: Optional[str] = None) -> bytearray:
        if len(data) == 0:
            return bytearray(random.randbytes(random.randint(1, self.max_block)))

        op = operation or random.choice(self.OPERATIONS)
        dispatch = {
            "insert": self._insert,
            "delete": self._delete,
            "permute": self._permute,
            "cross_pollinate": self._cross_pollinate,
        }
        return dispatch.get(op, self._insert)(data)

    # ── private operations ──────────────────────────────────────
    def _block_size(self, data_len: int) -> int:
        return random.randint(self.min_block, min(self.max_block, max(self.min_block, data_len)))

    def _insert(self, data: bytearray) -> bytearray:
        result = bytearray(data)
        bsz = self._block_size(len(data))
        block = bytearray(random.randbytes(bsz))
        pos = random.randint(0, len(result))
        result[pos:pos] = block
        return result

    def _delete(self, data: bytearray) -> bytearray:
        if len(data) <= 1:
            return bytearray(data)
        result = bytearray(data)
        bsz = min(self._block_size(len(data)), len(result) - 1)
        pos = random.randint(0, len(result) - bsz)
        del result[pos : pos + bsz]
        return result

    def _permute(self, data: bytearray) -> bytearray:
        if len(data) < 4:
            return bytearray(data)
        result = bytearray(data)
        bsz = self._block_size(len(data) // 2)
        n_blocks = len(result) // bsz
        if n_blocks < 2:
            return result
        blocks = [result[i * bsz : (i + 1) * bsz] for i in range(n_blocks)]
        remainder = result[n_blocks * bsz :]
        random.shuffle(blocks)
        out = bytearray()
        for b in blocks:
            out.extend(b)
        out.extend(remainder)
        return out

    def _cross_pollinate(self, data: bytearray) -> bytearray:
        if not self._donors:
            return self._insert(data)
        donor = random.choice(self._donors)
        if len(donor) == 0:
            return self._insert(data)
        bsz = min(self._block_size(len(donor)), len(donor))
        d_pos = random.randint(0, len(donor) - bsz)
        block = donor[d_pos : d_pos + bsz]
        result = bytearray(data)
        pos = random.randint(0, len(result))
        result[pos:pos] = block
        return result
