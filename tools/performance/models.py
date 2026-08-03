"""Data contracts shared by benchmark execution and report comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, isfinite
from statistics import median
from typing import Any, Callable, Mapping, Optional

from .config import (
    DEFAULT_MEASURED_RUNS,
    DEFAULT_WARMUP_RUNS,
    LONG_WORKFLOW_MEASURED_RUNS,
    SUPPORTED_CACHE_STATES,
)


@dataclass(frozen=True)
class BenchmarkObservation:
    """Describes useful work completed by one successful measured operation."""

    work_units: float
    unit_name: str

    def __post_init__(self) -> None:
        if not isfinite(self.work_units) or self.work_units < 0:
            raise ValueError("work_units must be finite and zero or greater")
        if not self.unit_name.strip():
            raise ValueError("unit_name must not be empty")


BenchmarkOperation = Callable[[], Optional[BenchmarkObservation]]
PreparationHook = Callable[[], None]


@dataclass(frozen=True)
class BenchmarkScenario:
    """Configures one repeatable operation and its controlled cache state."""

    name: str
    cache_state: str
    operation: BenchmarkOperation
    warmup_runs: int = DEFAULT_WARMUP_RUNS
    measured_runs: int = DEFAULT_MEASURED_RUNS
    before_each: Optional[PreparationHook] = None
    approved_long_workflow: bool = False
    maximum_p95_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.cache_state not in SUPPORTED_CACHE_STATES:
            raise ValueError("cache_state must be either 'cold' or 'warm'")
        if self.warmup_runs < DEFAULT_WARMUP_RUNS:
            raise ValueError(f"warmup_runs must be at least {DEFAULT_WARMUP_RUNS}")
        minimum_runs = (
            LONG_WORKFLOW_MEASURED_RUNS
            if self.approved_long_workflow
            else DEFAULT_MEASURED_RUNS
        )
        if self.measured_runs < minimum_runs:
            raise ValueError(f"measured_runs must be at least {minimum_runs}")
        if self.maximum_p95_ms is not None and (
            not isfinite(self.maximum_p95_ms) or self.maximum_p95_ms <= 0
        ):
            raise ValueError("maximum_p95_ms must be finite and greater than zero")


def _nearest_rank_percentile(values: tuple[float, ...], percentile: float) -> float:
    """Return a deterministic nearest-rank percentile for small benchmark sets."""

    if not values:
        raise ValueError("at least one value is required")
    ordered = sorted(values)
    rank = max(1, ceil((percentile / 100.0) * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class BenchmarkResult:
    """Stores raw samples and derives comparable latency and throughput metrics."""

    name: str
    cache_state: str
    durations_ms: tuple[float, ...]
    failures: tuple[str, ...] = field(default_factory=tuple)
    warmup_failures: tuple[str, ...] = field(default_factory=tuple)
    work_units: tuple[float, ...] = field(default_factory=tuple)
    unit_name: Optional[str] = None
    measured_runs: Optional[int] = None
    warmup_runs: Optional[int] = None
    minimum_measured_runs: int = DEFAULT_MEASURED_RUNS
    minimum_warmup_runs: int = DEFAULT_WARMUP_RUNS
    maximum_p95_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.cache_state not in SUPPORTED_CACHE_STATES:
            raise ValueError("cache_state must be either 'cold' or 'warm'")
        if any(not isfinite(duration) or duration < 0 for duration in self.durations_ms):
            raise ValueError("durations_ms must contain finite, non-negative values")
        if any(not isfinite(item) or item < 0 for item in self.work_units):
            raise ValueError("work_units must contain finite, non-negative values")
        if self.work_units and len(self.work_units) != len(self.durations_ms):
            raise ValueError("work_units must have one value per successful duration")
        if bool(self.work_units) != bool(self.unit_name):
            raise ValueError("work_units and unit_name must be supplied together")
        measured_runs = self.measured_runs
        if measured_runs is None:
            measured_runs = len(self.durations_ms) + len(self.failures)
            object.__setattr__(self, "measured_runs", measured_runs)
        if measured_runs != len(self.durations_ms) + len(self.failures):
            raise ValueError("measured_runs must equal successful runs plus failures")
        warmup_runs = self.warmup_runs
        if warmup_runs is None:
            warmup_runs = len(self.warmup_failures)
            object.__setattr__(self, "warmup_runs", warmup_runs)
        if warmup_runs < len(self.warmup_failures):
            raise ValueError("warmup_runs cannot be less than warmup failures")
        if self.minimum_measured_runs < LONG_WORKFLOW_MEASURED_RUNS:
            raise ValueError(
                f"minimum_measured_runs must be at least {LONG_WORKFLOW_MEASURED_RUNS}"
            )
        if self.minimum_warmup_runs < DEFAULT_WARMUP_RUNS:
            raise ValueError(
                f"minimum_warmup_runs must be at least {DEFAULT_WARMUP_RUNS}"
            )
        if self.maximum_p95_ms is not None and (
            not isfinite(self.maximum_p95_ms) or self.maximum_p95_ms <= 0
        ):
            raise ValueError("maximum_p95_ms must be finite and greater than zero")

    @property
    def key(self) -> str:
        """Return the stable identity used to match baseline and candidate runs."""

        return f"{self.name}::{self.cache_state}"

    @property
    def median_ms(self) -> Optional[float]:
        """Return sample median, or None when every measured operation failed."""

        return median(self.durations_ms) if self.durations_ms else None

    @property
    def p50_ms(self) -> Optional[float]:
        """Expose the median under the percentile name used in result tables."""

        return self.median_ms

    @property
    def p95_ms(self) -> Optional[float]:
        """Return nearest-rank p95, or None when no successful sample exists."""

        return (
            _nearest_rank_percentile(self.durations_ms, 95.0)
            if self.durations_ms
            else None
        )

    @property
    def minimum_ms(self) -> Optional[float]:
        """Return the fastest successful sample."""

        return min(self.durations_ms) if self.durations_ms else None

    @property
    def maximum_ms(self) -> Optional[float]:
        """Return the slowest successful sample."""

        return max(self.durations_ms) if self.durations_ms else None

    @property
    def throughput_per_second(self) -> Optional[float]:
        """Return aggregate work divided by aggregate successful runtime."""

        total_seconds = sum(self.durations_ms) / 1000.0
        if not self.work_units or total_seconds <= 0:
            return None
        return sum(self.work_units) / total_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize raw evidence and derived statistics into the report schema."""

        return {
            "name": self.name,
            "cache_state": self.cache_state,
            "samples_ms": list(self.durations_ms),
            "successful_runs": len(self.durations_ms),
            "measured_runs": self.measured_runs,
            "warmup_runs": self.warmup_runs,
            "minimum_measured_runs": self.minimum_measured_runs,
            "minimum_warmup_runs": self.minimum_warmup_runs,
            "maximum_p95_ms": self.maximum_p95_ms,
            "failures": list(self.failures),
            "failure_count": len(self.failures),
            "warmup_failures": list(self.warmup_failures),
            "median_ms": self.median_ms,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "minimum_ms": self.minimum_ms,
            "maximum_ms": self.maximum_ms,
            "work_units": list(self.work_units),
            "unit_name": self.unit_name,
            "throughput_per_second": self.throughput_per_second,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkResult":
        """Restore a result from the stable JSON representation."""

        return cls(
            name=str(value["name"]),
            cache_state=str(value["cache_state"]),
            durations_ms=tuple(float(item) for item in value["samples_ms"]),
            failures=tuple(str(item) for item in value.get("failures", ())),
            warmup_failures=tuple(
                str(item) for item in value.get("warmup_failures", ())
            ),
            work_units=tuple(float(item) for item in value.get("work_units", ())),
            unit_name=(
                str(value["unit_name"]) if value.get("unit_name") is not None else None
            ),
            measured_runs=int(value.get("measured_runs", len(value["samples_ms"]) + len(value.get("failures", ())))),
            warmup_runs=int(value.get("warmup_runs", len(value.get("warmup_failures", ())))),
            minimum_measured_runs=int(
                value.get("minimum_measured_runs", DEFAULT_MEASURED_RUNS)
            ),
            minimum_warmup_runs=int(
                value.get("minimum_warmup_runs", DEFAULT_WARMUP_RUNS)
            ),
            maximum_p95_ms=(
                float(value["maximum_p95_ms"])
                if value.get("maximum_p95_ms") is not None
                else None
            ),
        )
