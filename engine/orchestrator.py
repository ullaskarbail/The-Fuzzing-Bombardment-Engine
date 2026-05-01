"""
Fuzzing Orchestrator
====================
Central coordinator that drives the bombardment loop:
  1. Select seed → 2. Schedule algorithm → 3. Mutate →
  4. Execute target → 5. Monitor signals → 6. Log crashes →
  7. Broadcast via callback

KEY DESIGN: Structure-Aware Mutation
-------------------------------------
The target binary parses key=value lines. If we mangle the KEY (e.g.
"name=" → garbage) the parser ignores the line and the vulnerable
function (strcpy, printf, etc.) is NEVER called → no crash possible.

Fix: parse out key=value pairs, mutate ONLY the VALUE portion, then
reassemble. All 4 algorithms now attack the actual vulnerable fields.
"""

import asyncio
import subprocess
import time
import random
from typing import Callable, Optional, Awaitable

from .seed_pool import SeedPool
from .crash_handler import CrashHandler
from .mutators import BitFlipper, ArithmeticMutator, BlockMutator, DictionaryMutator


class FuzzStats:
    """Live statistics for the fuzzing session."""

    def __init__(self):
        self.total_iterations = 0
        self.crashes_found = 0
        self.start_time = 0.0
        self.mutation_counts = {
            "bit_flip": 0,
            "arithmetic": 0,
            "block": 0,
            "dictionary": 0,
        }
        self.current_seed = ""
        self.current_algorithm = ""

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time if self.start_time else 0.0

    @property
    def speed(self) -> float:
        up = self.uptime
        return self.total_iterations / up if up > 0 else 0.0

    @property
    def crash_rate(self) -> float:
        return (
            (self.crashes_found / self.total_iterations * 100)
            if self.total_iterations > 0
            else 0.0
        )

    def to_dict(self) -> dict:
        return {
            "total_iterations": self.total_iterations,
            "crashes_found": self.crashes_found,
            "crash_rate": round(self.crash_rate, 4),
            "speed": round(self.speed, 1),
            "uptime_seconds": round(self.uptime, 1),
            "mutation_stats": dict(self.mutation_counts),
            "current_seed": self.current_seed,
            "current_algorithm": self.current_algorithm,
        }


class Orchestrator:
    """Main fuzzing loop with structure-aware value mutation."""

    ALL_ALGORITHMS = ["bit_flip", "arithmetic", "block", "dictionary"]

    def __init__(
        self,
        target_binary: str,
        seed_dir: str,
        crash_dir: str,
        timeout: float = 2.0,
        active_algorithms: list[str] | None = None,
    ):
        self.target_binary = target_binary
        self.timeout = timeout
        self.running = False
        self.active_algorithms = active_algorithms or self.ALL_ALGORITHMS

        # Components
        self.seed_pool = SeedPool(seed_dir)
        self.crash_handler = CrashHandler(crash_dir)
        self.stats = FuzzStats()

        # Mutators — operate on VALUE bytes only (not keys)
        self._bit_flipper = BitFlipper(mutation_ratio=0.25)
        self._arithmetic  = ArithmeticMutator(max_delta=350, num_operations=4)
        self._block       = BlockMutator(min_block=4, max_block=128)
        self._dictionary  = DictionaryMutator()

        # Donor pool for block cross-pollination
        self._block.set_donor_pool(self.seed_pool.all_data)

        # WebSocket callbacks
        self._on_crash: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_stats: Optional[Callable[[dict], Awaitable[None]]] = None

    def set_callbacks(
        self,
        on_crash: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_stats: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self._on_crash = on_crash
        self._on_stats = on_stats

    # ── structure-aware mutation ────────────────────────────────
    def _apply_to_value(self, value_bytes: bytearray, algorithm: str) -> bytearray:
        """Run the chosen mutator on a VALUE bytearray."""
        if algorithm == "bit_flip":
            return self._bit_flipper.mutate(value_bytes)
        elif algorithm == "arithmetic":
            return self._arithmetic.mutate(value_bytes)
        elif algorithm == "block":
            return self._block.mutate(value_bytes)
        elif algorithm == "dictionary":
            return self._dictionary.mutate(value_bytes)
        return value_bytes

    def _mutate(self, data: bytearray, algorithm: str) -> bytearray:
        """
        Parse key=value lines, mutate ONE randomly chosen VALUE,
        and reassemble. Keys are NEVER touched — the binary parser
        always reaches the vulnerable function for that field.
        """
        try:
            text = data.decode("latin-1")
        except Exception:
            return self._apply_to_value(data, algorithm)

        lines = text.split("\n")

        # Collect indices of parseable key=value lines
        kv_indices = [
            i for i, line in enumerate(lines)
            if "=" in line and not line.startswith("#") and line.strip()
        ]

        if not kv_indices:
            return self._apply_to_value(data, algorithm)

        # Pick one line to mutate
        idx = random.choice(kv_indices)
        line = lines[idx]
        eq_pos = line.index("=")
        key   = line[: eq_pos + 1]   # e.g. "name="
        value = line[eq_pos + 1:]    # e.g. "FuzzTest"

        # Mutate the value bytes only
        mutated_val = self._apply_to_value(
            bytearray(value.encode("latin-1")), algorithm
        )
        new_value = mutated_val.decode("latin-1", errors="replace")

        lines[idx] = key + new_value
        return bytearray("\n".join(lines).encode("latin-1"))

    # ── execute target ──────────────────────────────────────────
    def _execute(self, payload: bytearray) -> int:
        """Spawn the target binary, pipe in the payload, return exit code."""
        try:
            proc = subprocess.run(
                [self.target_binary],
                input=bytes(payload),
                capture_output=True,
                timeout=self.timeout,
            )
            return proc.returncode
        except subprocess.TimeoutExpired:
            return 0
        except FileNotFoundError:
            raise RuntimeError(
                f"Target binary not found: {self.target_binary}. "
                "Compile: clang++ -o target/vulnerable -fno-stack-protector -O0 target/vulnerable.cpp"
            )

    # ── main loop ───────────────────────────────────────────────
    async def run(self):
        """Start the continuous bombardment loop."""
        self.running = True
        self.stats = FuzzStats()
        self.stats.start_time = time.time()

        broadcast_interval = 0.25
        last_broadcast = 0.0

        while self.running:
            seed = self.seed_pool.select()
            algorithm = random.choice(self.active_algorithms)

            self.stats.current_seed = seed["name"]
            self.stats.current_algorithm = algorithm

            mutated = self._mutate(bytearray(seed["data"]), algorithm)

            return_code = await asyncio.get_event_loop().run_in_executor(
                None, self._execute, mutated
            )

            self.stats.total_iterations += 1
            self.stats.mutation_counts[algorithm] += 1

            crash_event = self.crash_handler.triage(
                return_code, mutated, seed["name"], algorithm
            )
            if crash_event:
                self.stats.crashes_found += 1
                self.seed_pool.record_crash(seed["name"])
                if self._on_crash:
                    await self._on_crash(crash_event)
            else:
                # REINFORCEMENT LEARNING:
                # If the payload did not crash the target, we probabilistically 
                # add it back to the seed pool. This allows successful, deep-path 
                # mutations to become the basis for future generations, slowly 
                # evolving highly complex payloads.
                # Use a 5% chance to avoid exploding the seed pool instantly.
                if random.random() < 0.05 and len(mutated) < 1024 * 50:  # limit to 50KB
                    new_seed_name = f"rl_{algorithm}_{self.stats.total_iterations}.txt"
                    self.seed_pool.add_seed(new_seed_name, mutated)

            now = time.time()
            if now - last_broadcast >= broadcast_interval:
                last_broadcast = now
                if self._on_stats:
                    await self._on_stats(self.stats.to_dict())

            await asyncio.sleep(0)

    def stop(self):
        self.running = False
