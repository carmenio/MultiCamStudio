"""Characterization tests for benchmark execution, reporting, and comparison."""

from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from math import nan
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from tools.performance import (
    BenchmarkObservation,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkScenario,
    compare_report_files,
    compare_reports,
    read_report,
    write_report,
)
from tools.performance.run_http_benchmarks import HttpScenario, _request


class SequenceClock:
    """Supplies deterministic start/end timestamps to benchmark tests."""

    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def complete_result(
    name: str,
    cache_state: str,
    durations_ms: tuple[float, ...],
    *,
    failures: tuple[str, ...] = (),
    work_units: tuple[float, ...] = (),
    unit_name: str | None = None,
    maximum_p95_ms: float | None = None,
) -> BenchmarkResult:
    """Build complete protocol evidence for comparison-focused unit tests."""

    return BenchmarkResult(
        name,
        cache_state,
        durations_ms,
        failures=failures,
        work_units=work_units,
        unit_name=unit_name,
        measured_runs=len(durations_ms) + len(failures),
        warmup_runs=3,
        maximum_p95_ms=maximum_p95_ms,
    )


class BenchmarkRunnerTests(unittest.TestCase):
    """Verify metrics through the package's supported public interface."""

    def test_runner_reports_latency_throughput_and_cache_state(self) -> None:
        clock_values = [value for index in range(10) for value in (index, index + 0.01)]
        clock = SequenceClock(clock_values)
        scenario = BenchmarkScenario(
            name="segment-read",
            cache_state="warm",
            operation=lambda: BenchmarkObservation(2.0, "segments"),
        )

        result = BenchmarkRunner(clock=clock).run(scenario)

        for actual in result.durations_ms:
            self.assertAlmostEqual(actual, 10.0)
        self.assertAlmostEqual(result.median_ms or 0.0, 10.0)
        self.assertAlmostEqual(result.p50_ms or 0.0, 10.0)
        self.assertAlmostEqual(result.p95_ms or 0.0, 10.0)
        self.assertAlmostEqual(result.minimum_ms or 0.0, 10.0)
        self.assertAlmostEqual(result.maximum_ms or 0.0, 10.0)
        self.assertAlmostEqual(result.throughput_per_second or 0.0, 200.0)
        self.assertEqual(result.cache_state, "warm")
        self.assertEqual(result.measured_runs, 10)
        self.assertEqual(result.warmup_runs, 3)

    def test_runner_records_warmup_and_measured_failures(self) -> None:
        calls = 0

        def fail() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError(f"failure {calls}")

        scenario = BenchmarkScenario(
            name="failed-request",
            cache_state="cold",
            operation=fail,
        )

        clock_values = [value for index in range(10) for value in (index, index + 0.1)]
        result = BenchmarkRunner(clock=SequenceClock(clock_values)).run(scenario)

        self.assertEqual(len(result.warmup_failures), 3)
        self.assertEqual(len(result.failures), 10)
        self.assertIsNone(result.median_ms)

    def test_runner_continues_after_preparation_failure(self) -> None:
        preparations = 0

        def prepare() -> None:
            nonlocal preparations
            preparations += 1
            if preparations == 4:
                raise OSError("cache reset failed")

        scenario = BenchmarkScenario(
            name="prepared-request",
            cache_state="cold",
            operation=lambda: None,
            before_each=prepare,
        )

        clock_values = [value for index in range(9) for value in (index, index + 0.1)]
        result = BenchmarkRunner(clock=SequenceClock(clock_values)).run(scenario)

        self.assertEqual(result.failures, ("OSError: cache reset failed",))
        self.assertEqual(len(result.durations_ms), 9)

    def test_scenario_rejects_an_uncontrolled_cache_label(self) -> None:
        with self.assertRaisesRegex(ValueError, "cache_state"):
            BenchmarkScenario("request", "sometimes", lambda: None)

    def test_result_rejects_non_finite_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            BenchmarkResult("request", "warm", (nan,))

    def test_five_runs_require_explicit_long_workflow_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 10"):
            BenchmarkScenario("calibration", "warm", lambda: None, measured_runs=5)

        scenario = BenchmarkScenario(
            "calibration",
            "warm",
            lambda: None,
            measured_runs=5,
            approved_long_workflow=True,
        )

        self.assertTrue(scenario.approved_long_workflow)


class ComparisonTests(unittest.TestCase):
    """Verify the three-percent phase gate and evidence completeness rules."""

    def test_three_percent_or_less_regression_passes(self) -> None:
        baseline = complete_result("summary", "warm", (100.0,) * 10)
        candidate = complete_result("summary", "warm", (103.0,) * 10)

        report = compare_reports((baseline,), (candidate,))

        self.assertTrue(report.passed)
        self.assertAlmostEqual(report.scenarios[0].median_change_percent or 0.0, 3.0)

    def test_regressed_p95_or_additional_failures_blocks_phase(self) -> None:
        baseline = complete_result("summary", "cold", (100.0,) * 10)
        candidate = complete_result(
            "summary",
            "cold",
            (100.0,) * 8 + (104.0,),
            failures=("TimeoutError: request timed out",),
        )

        comparison = compare_reports((baseline,), (candidate,)).scenarios[0]

        self.assertFalse(comparison.passed)
        self.assertAlmostEqual(comparison.p95_change_percent or 0.0, 4.0)
        self.assertEqual(len(comparison.reasons), 2)

    def test_missing_candidate_blocks_phase(self) -> None:
        baseline = complete_result("summary", "warm", (10.0,) * 10)

        report = compare_reports((baseline,), ())

        self.assertFalse(report.passed)
        self.assertEqual(report.scenarios[0].reasons, ("candidate result is missing",))

    def test_fewer_candidate_runs_blocks_phase(self) -> None:
        baseline = complete_result("summary", "warm", (10.0,) * 10)
        candidate = complete_result("summary", "warm", (10.0,) * 5)

        comparison = compare_reports((baseline,), (candidate,)).scenarios[0]

        self.assertFalse(comparison.passed)
        self.assertIn("candidate has fewer measured runs than baseline", comparison.reasons)

    def test_equally_incomplete_reports_cannot_pass(self) -> None:
        baseline = BenchmarkResult(
            "summary", "warm", (10.0,), measured_runs=1, warmup_runs=3
        )
        candidate = BenchmarkResult(
            "summary", "warm", (10.0,), measured_runs=1, warmup_runs=3
        )

        comparison = compare_reports((baseline,), (candidate,)).scenarios[0]

        self.assertFalse(comparison.passed)
        self.assertIn(
            "baseline does not meet its minimum measured-run requirement",
            comparison.reasons,
        )

    def test_duplicate_scenario_blocks_comparison(self) -> None:
        result = complete_result("summary", "warm", (10.0,) * 10)

        with self.assertRaisesRegex(ValueError, "duplicate baseline scenario"):
            compare_reports((result, result), (result,))

    def test_non_finite_gate_threshold_is_rejected(self) -> None:
        result = complete_result("summary", "warm", (10.0,) * 10)

        with self.assertRaisesRegex(ValueError, "finite"):
            compare_reports((result,), (result,), allowed_regression_percent=nan)

    def test_hard_p95_limit_blocks_an_unchanged_but_slow_candidate(self) -> None:
        baseline = complete_result(
            "detection-summary", "warm", (600.0,) * 10, maximum_p95_ms=500.0
        )
        candidate = complete_result(
            "detection-summary", "warm", (600.0,) * 10, maximum_p95_ms=500.0
        )

        comparison = compare_reports((baseline,), (candidate,)).scenarios[0]

        self.assertFalse(comparison.passed)
        self.assertIn("candidate p95 exceeds hard limit of 500.000 ms", comparison.reasons)

    def test_throughput_work_mismatch_and_regression_block_phase(self) -> None:
        baseline = complete_result(
            "upload",
            "warm",
            (100.0,) * 10,
            work_units=(100.0,) * 10,
            unit_name="megabytes",
        )
        different_work = complete_result(
            "upload",
            "warm",
            (100.0,) * 10,
            work_units=(1.0,) * 10,
            unit_name="megabytes",
        )
        slower = complete_result(
            "upload",
            "warm",
            (104.0,) * 10,
            work_units=(100.0,) * 10,
            unit_name="megabytes",
        )

        work_comparison = compare_reports((baseline,), (different_work,)).scenarios[0]
        speed_comparison = compare_reports((baseline,), (slower,)).scenarios[0]

        self.assertIn("candidate work units differ from baseline", work_comparison.reasons)
        self.assertTrue(any("throughput regressed" in item for item in speed_comparison.reasons))


class ReportingTests(unittest.TestCase):
    """Verify JSON files preserve raw evidence through the public API."""

    def test_report_round_trip(self) -> None:
        result = complete_result(
            "upload",
            "cold",
            (10.0,) * 10,
            work_units=(100.0,) * 10,
            unit_name="megabytes",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "baseline.json"

            write_report(
                report_path,
                (result,),
                {"fixture": "recording-set-1", "commit": "baseline-sha"},
            )
            metadata, restored_results = read_report(report_path)

        self.assertEqual(
            metadata,
            {"fixture": "recording-set-1", "commit": "baseline-sha"},
        )
        self.assertEqual(restored_results, (result,))

    def test_file_comparison_rejects_changed_environment(self) -> None:
        result = complete_result("summary", "warm", (10.0,) * 10)
        with tempfile.TemporaryDirectory() as temporary_directory:
            baseline_path = Path(temporary_directory) / "baseline.json"
            candidate_path = Path(temporary_directory) / "candidate.json"
            write_report(
                baseline_path, (result,), {"fixture": "set-1", "commit": "before"}
            )
            write_report(
                candidate_path, (result,), {"fixture": "set-2", "commit": "after"}
            )

            report = compare_report_files(
                baseline_path,
                candidate_path,
                required_metadata_keys=("fixture",),
            )

        self.assertFalse(report.passed)
        self.assertEqual(report.context_reasons, ("comparison metadata differs: fixture",))

    def test_file_comparison_requires_source_commit_evidence(self) -> None:
        result = complete_result("summary", "warm", (10.0,) * 10)
        with tempfile.TemporaryDirectory() as temporary_directory:
            baseline_path = Path(temporary_directory) / "baseline.json"
            candidate_path = Path(temporary_directory) / "candidate.json"
            write_report(baseline_path, (result,), {"fixture": "set-1"})
            write_report(candidate_path, (result,), {"fixture": "set-1"})

            report = compare_report_files(
                baseline_path,
                candidate_path,
                required_metadata_keys=("fixture",),
            )

        self.assertFalse(report.passed)
        self.assertEqual(
            report.context_reasons,
            ("baseline source commit is missing", "candidate source commit is missing"),
        )


class HttpRunnerTests(unittest.TestCase):
    """Verify configured HTTP status contracts without starting a live service."""

    def test_expected_http_error_status_is_a_successful_measurement(self) -> None:
        expected_response = HTTPError(
            "https://127.0.0.1/missing",
            404,
            "not found",
            {},
            BytesIO(b"missing"),
        )

        with patch(
            "tools.performance.run_http_benchmarks.urlopen",
            side_effect=expected_response,
        ):
            observation = _request(
                HttpScenario("missing-route", "/missing", "warm", expected_status=404)
            )

        self.assertIsNone(observation)


if __name__ == "__main__":
    unittest.main()
