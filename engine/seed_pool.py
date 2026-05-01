"""
Seed Pool Manager
=================
Loads valid seed files, tracks selection history, and provides
seeds to the orchestrator for mutation scheduling.
"""

import os
import random
from typing import List, Optional


class SeedPool:
    """Manage the pool of seed inputs for the fuzzer."""

    def __init__(self, seed_dir: str):
        self.seed_dir = seed_dir
        self._seeds: List[dict] = []
        self._load_seeds()

    def _load_seeds(self):
        """Scan seed_dir and load every file as a seed."""
        if not os.path.isdir(self.seed_dir):
            raise FileNotFoundError(f"Seed directory not found: {self.seed_dir}")

        for fname in sorted(os.listdir(self.seed_dir)):
            fpath = os.path.join(self.seed_dir, fname)
            if os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    data = f.read()
                self._seeds.append({
                    "name": fname,
                    "path": fpath,
                    "data": bytearray(data),
                    "hits": 0,
                    "crashes": 0,
                })

        if not self._seeds:
            raise RuntimeError(f"No seed files found in {self.seed_dir}")

    @property
    def count(self) -> int:
        return len(self._seeds)

    @property
    def all_data(self) -> List[bytearray]:
        """Return raw data of every seed (used as donor pool for cross-pollination)."""
        return [s["data"] for s in self._seeds]

    def select(self) -> dict:
        """Pick a seed (currently uniform random; can be upgraded to coverage-weighted)."""
        seed = random.choice(self._seeds)
        seed["hits"] += 1
        return seed

    def record_crash(self, seed_name: str):
        """Increment crash counter for the given seed."""
        for s in self._seeds:
            if s["name"] == seed_name:
                s["crashes"] += 1
                break

    def add_seed(self, name: str, data: bytearray):
        """Dynamically add a new seed (e.g. an interesting mutant) to the pool."""
        self._seeds.append({
            "name": name,
            "path": None,
            "data": data,
            "hits": 0,
            "crashes": 0,
        })

    def summary(self) -> List[dict]:
        return [
            {"name": s["name"], "size": len(s["data"]), "hits": s["hits"], "crashes": s["crashes"]}
            for s in self._seeds
        ]
