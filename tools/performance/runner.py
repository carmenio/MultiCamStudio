"""Repeatable benchmark execution with injectable timing for deterministic tests."""

from __future__ import annotations

import time
from typing import Callable, Iterable, Optional

from .models import BenchmarkObservation, BenchmarkResult, BenchmarkScenario
from .config import DEFAULT_MEASURED_RUNS, LONG_WORKFLOW_MEASURED_RUNS


class BenchmarkRunner:
    """Runs warmups and measured operations while retaining raw timing evidence."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock

    def run(self, scenario: BenchmarkScenario) -> BenchmarkResult:
        """Run one scenario without allowing an individual failure to end the suite."""

        warmup_failures = self._run_warmups(scenario)
        durations_ms: list[float] = []
        failures: list[str] = []
        observations: list[Optional[BenchmarkObservation]] = []

        for _ in range(scenario.measured_runs):
            try:
                self._prepare(scenario)
            except Exception as error:  # Preparation failures are measured-run failures.
                failures.append(f"{type(error).__name__}: {error}")
                continue
            started_at = self._clock()
            try:
                observation = scenario.operation()
            except Exception as error:  # Benchmark failures are report evidence.
                failures.append(f"{type(error).__name__}: {error}")
                self._clock()
                continue

            finished_at = self._clock()
            durations_ms.append(max(0.0, (finished_at - started_at) * 1000.0))
            observations.append(observation)

        work_units, unit_name = self._normalize_observations(observations)
        return BenchmarkResult(
            name=scenario.name,
            cache_state=scenario.cache_state,
            durations_ms=tuple(durations_ms),
            failures=tuple(failures),
            warmup_failures=tuple(warmup_failures),
            work_units=work_units,
            unit_name=unit_name,
            measured_runs=scenario.measured_runs,
            warmup_runs=scenario.warmup_runs,
            minimum_measured_runs=(
                LONG_WORKFLOW_MEASURED_RUNS
                if scenario.approved_long_workflow
                else DEFAULT_MEASURED_RUNS
            ),
            maximum_p95_ms=scenario.maximum_p95_ms,
        )

    def run_suite(
        self, scenarios: Iterable[BenchmarkScenario]
    ) -> tuple[BenchmarkResult, ...]:
        """Run scenarios sequentially so they do not distort each other's timings."""

        return tuple(self.run(scenario) for scenario in scenarios)

    def _run_warmups(self, scenario: BenchmarkScenario) -> list[str]:
        """Exercise setup and operation paths before retaining measured samples."""

        failures: list[str] = []
        for _ in range(scenario.warmup_runs):
            try:
                self._prepare(scenario)
                scenario.operation()
            except Exception as error:  # Warmup instability belongs in the report.
                failures.append(f"{type(error).__name__}: {error}")
        return failures

    @staticmethod
    def _prepare(scenario: BenchmarkScenario) -> None:
        """Apply caller-owned cache or fixture preparation immediately before a run."""

        if scenario.before_each is not None:
            scenario.before_each()

    @staticmethod
    def _normalize_observations(
        observations: list[Optional[BenchmarkObservation]],
    ) -> tuple[tuple[float, ...], Optional[str]]:
        """Validate optional throughput evidence is complete and consistently named."""

        if not observations or all(item is None for item in observations):
            return (), None
        if any(item is None for item in observations):
            raise ValueError(
                "every successful operation must return an observation when throughput is used"
            )

        concrete = [item for item in observations if item is not None]
        unit_names = {item.unit_name for item in concrete}
        if len(unit_names) != 1:
            raise ValueError("all observations in a scenario must use the same unit_name")
        return tuple(item.work_units for item in concrete), concrete[0].unit_name
