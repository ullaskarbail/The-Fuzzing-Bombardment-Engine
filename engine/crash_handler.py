"""
Crash Handler & Triage
======================
Detects OS-level signals (SIGSEGV, SIGABRT, SIGBUS, etc.),
saves the crash-inducing payload to disk, and prepares
crash event data for WebSocket broadcast.
"""

import os
import signal
import hashlib
import time
from typing import Optional


# Map negative return codes to signal names
SIGNAL_MAP = {
    -signal.SIGSEGV: "SIGSEGV (Segmentation Fault)",
    -signal.SIGABRT: "SIGABRT (Abort)",
    -signal.SIGFPE:  "SIGFPE (Floating-Point Exception)",
    -signal.SIGILL:  "SIGILL (Illegal Instruction)",
}
# SIGBUS value differs between macOS (10) and Linux (7)
if hasattr(signal, "SIGBUS"):
    SIGNAL_MAP[-signal.SIGBUS] = "SIGBUS (Bus Error)"


class CrashHandler:
    """Detect crashes, save payloads, and prepare triage events."""

    # Any of these return codes indicate a fatal crash
    CRASH_SIGNALS = set(SIGNAL_MAP.keys())

    def __init__(self, crash_dir: str):
        self.crash_dir = crash_dir
        os.makedirs(crash_dir, exist_ok=True)
        self._crash_count = 0

    @property
    def total_crashes(self) -> int:
        return self._crash_count

    def is_crash(self, return_code: int) -> bool:
        """Check whether a process return code indicates a crash."""
        return return_code in self.CRASH_SIGNALS

    def triage(
        self,
        return_code: int,
        payload: bytearray,
        seed_name: str,
        algorithm: str,
    ) -> Optional[dict]:
        """
        If return_code is a crash signal, save the payload and return
        a crash event dict for logging / WebSocket broadcast.
        Returns None if not a crash.
        """
        if not self.is_crash(return_code):
            return None

        self._crash_count += 1
        crash_id = f"crash_{self._crash_count:05d}"
        payload_hash = hashlib.sha256(payload).hexdigest()[:16]
        sig_name = SIGNAL_MAP.get(return_code, f"SIG_UNKNOWN({return_code})")

        # Save payload to disk
        log_file = os.path.join(self.crash_dir, f"{crash_id}_{payload_hash}.bin")
        with open(log_file, "wb") as f:
            f.write(payload)

        return {
            "id": crash_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "algorithm": algorithm,
            "signal_code": return_code,
            "signal_name": sig_name,
            "payload_hash": payload_hash,
            "payload_size": len(payload),
            "seed_file": seed_name,
            "log_file": log_file,
        }
