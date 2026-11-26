"""
resource_tracking.py — shared wall-clock timing and peak-memory measurement.

Used identically by every method's run.py so execution_time / memory_usage
sub-metrics (CLAUDE.md §5) are measured with the same code and hardware.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Optional

import psutil

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


@dataclass
class Timer:
    """Simple wall-clock stopwatch built on time.perf_counter()."""

    _t0: Optional[float] = field(default=None, repr=False)
    elapsed: float = 0.0

    def start(self) -> "Timer":
        self._t0 = time.perf_counter()
        return self

    def stop(self) -> float:
        assert self._t0 is not None, "Timer.stop() called before start()"
        self.elapsed = time.perf_counter() - self._t0
        self._t0 = None
        return self.elapsed


@contextmanager
def timed():
    """Context manager yielding a Timer; .elapsed is set on exit."""
    t = Timer().start()
    try:
        yield t
    finally:
        t.stop()


def peak_rss_mb() -> float:
    """Peak resident-set-size (RSS) of the current process, in MB.

    Prefers ``resource.getrusage`` (ru_maxrss), which is a true peak on
    Linux/macOS. Falls back to psutil's current RSS if unavailable
    (e.g. on Windows, where ru_maxrss is not implemented).
    """
    try:
        import resource

        ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB, macOS reports bytes.
        import sys

        rss_bytes = ru_maxrss * 1024 if sys.platform != "darwin" else ru_maxrss
        return rss_bytes / (1024 * 1024)
    except Exception:
        proc = psutil.Process()
        return proc.memory_info().rss / (1024 * 1024)


def cuda_peak_mb() -> Optional[float]:
    """Peak CUDA memory allocated (MB), or None if CUDA is unavailable."""
    if torch is None or not torch.cuda.is_available():
        return None
    return torch.cuda.max_memory_allocated() / (1024 * 1024)


def reset_cuda_peak() -> None:
    if torch is not None and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


@dataclass
class RunResourceReport:
    train_time_s: float = 0.0
    inference_time_s: float = 0.0
    total_time_s: float = 0.0
    peak_memory_mb: float = 0.0
    cuda_peak_memory_mb: Optional[float] = None
    diverged: bool = False
    best_epoch: int = 0
    epochs_run: int = 0
    skipped_steps: int = 0

    def status_dict(self) -> Dict[str, object]:
        return {
            "diverged": self.diverged,
            "best_epoch": self.best_epoch,
            "epochs_run": self.epochs_run,
            "skipped_steps": self.skipped_steps,
        }

    def to_dict(self) -> Dict[str, float]:
        d = {
            "train_time_s": round(self.train_time_s, 4),
            "inference_time_s": round(self.inference_time_s, 4),
            "total_time_s": round(self.total_time_s, 4),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
        }
        if self.cuda_peak_memory_mb is not None:
            d["cuda_peak_memory_mb"] = round(self.cuda_peak_memory_mb, 2)
        return d
