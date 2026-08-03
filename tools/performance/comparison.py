"""Baseline comparison and the repository's performance regression gate."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite
from pathlib import Path
from typing import Iterable, Optional

from .config import (
    DEFAULT_ALLOWED_REGRESSION_PERCENT,
    DEFAULT_COMPARISON_METADATA_KEYS,
)
from .models import BenchmarkResult


def _change_percent(baseline: float, candidate: float) -> float:
    """Calculate signed change while handling a zero-duration synthetic baseline."""

    if baseline == 0:
        return 0.0 if candidate == 0 else inf
    return ((candidate - baseline) / baseline) * 100.0


@dataclass(frozen=True)
class ScenarioComparison:
    """Explains one scenario's median, p95, and failure-count gate outcome."""

    key: str
    passed: bool
    median_change_percent: Optional[float]
    p95_change_percent: Optional[float]
    throughput_change_percent: Optional[float]
    baseline_failures: int
    candidate_failures: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the comparison for CI and Markdown result generation."""

        return {
            "key": self.key,
            "passed": self.passed,
            "median_change_percent": self.median_change_percent,
            "p95_change_percent": self.p95_change_percent,
            "throughput_change_percent": self.throughput_change_percent,
            "baseline_failures": self.baseline_failures,
            "candidate_failures": self.candidate_failures,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ComparisonReport:
    """Aggregates scenario comparisons into one phase-level pass/fail decision."""

    allowed_regression_percent: float
    scenarios: tuple[ScenarioComparison, ...]
    context_reasons: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Pass only when every baseline scenario has acceptable candidate evidence."""

        return (
            bool(self.scenarios)
            and not self.context_reasons
            and all(item.passed for item in self.scenarios)
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the complete gate decision."""

        return {
            "allowed_regression_percent": self.allowed_regression_percent,
            "passed": self.passed,
            "context_reasons": list(self.context_reasons),
            "scenarios": [item.to_dict() for item in self.scenarios],
        }


def compare_reports(
    baseline_results: Iterable[BenchmarkResult],
    candidate_results: Iterable[BenchmarkResult],
    allowed_regression_percent: float = DEFAULT_ALLOWED_REGRESSION_PERCENT,
) -> ComparisonReport:
    """Compare matching cold/warm scenarios using median and nearest-rank p95."""

    if not isfinite(allowed_regression_percent) or allowed_regression_percent < 0:
        raise ValueError("allowed_regression_percent must be finite and zero or greater")

    baselines = _unique_results(baseline_results, "baseline")
    candidates = _unique_results(candidate_results, "candidate")
    comparisons: list[ScenarioComparison] = []
    for baseline in baselines.values():
        candidate = candidates.get(baseline.key)
        comparisons.append(
            _compare_scenario(baseline, candidate, allowed_regression_percent)
        )
    return ComparisonReport(allowed_regression_percent, tuple(comparisons))


def compare_report_files(
    baseline_path: Path,
    candidate_path: Path,
    allowed_regression_percent: float = DEFAULT_ALLOWED_REGRESSION_PERCENT,
    required_metadata_keys: tuple[str, ...] = DEFAULT_COMPARISON_METADATA_KEYS,
) -> ComparisonReport:
    """Gate report files only after their controlled-environment metadata matches."""

    from .reporting import read_report

    baseline_metadata, baseline_results = read_report(baseline_path)
    candidate_metadata, candidate_results = read_report(candidate_path)
    provenance_reasons = tuple(
        reason
        for label, metadata in (
            ("baseline", baseline_metadata),
            ("candidate", candidate_metadata),
        )
        if not str(metadata.get("commit", "")).strip()
        for reason in (f"{label} source commit is missing",)
    )
    context_reasons = provenance_reasons + _compare_metadata(
        baseline_metadata, candidate_metadata, required_metadata_keys
    )
    result_comparison = compare_reports(
        baseline_results, candidate_results, allowed_regression_percent
    )
    return ComparisonReport(
        result_comparison.allowed_regression_percent,
        result_comparison.scenarios,
        context_reasons,
    )


def _unique_results(
    results: Iterable[BenchmarkResult], report_name: str
) -> dict[str, BenchmarkResult]:
    """Reject ambiguous evidence instead of silently replacing duplicate scenarios."""

    unique: dict[str, BenchmarkResult] = {}
    for result in results:
        if result.key in unique:
            raise ValueError(f"duplicate {report_name} scenario: {result.key}")
        unique[result.key] = result
    return unique


def _compare_metadata(
    baseline: dict[str, object],
    candidate: dict[str, object],
    required_keys: tuple[str, ...],
) -> tuple[str, ...]:
    """Identify missing or changed controls that invalidate a timing comparison."""

    reasons: list[str] = []
    for key in required_keys:
        if key not in baseline or key not in candidate:
            reasons.append(f"required comparison metadata is missing: {key}")
        elif baseline[key] != candidate[key]:
            reasons.append(f"comparison metadata differs: {key}")
    return tuple(reasons)


def _compare_scenario(
    baseline: BenchmarkResult,
    candidate: Optional[BenchmarkResult],
    allowed_regression_percent: float,
) -> ScenarioComparison:
    """Apply latency and failure-count rules to a single matched scenario."""

    if candidate is None:
        return ScenarioComparison(
            baseline.key,
            False,
            None,
            None,
            None,
            len(baseline.failures),
            0,
            ("candidate result is missing",),
        )

    reasons: list[str] = []
    median_change = _metric_change(baseline.median_ms, candidate.median_ms)
    p95_change = _metric_change(baseline.p95_ms, candidate.p95_ms)
    throughput_change = _metric_change(
        baseline.throughput_per_second, candidate.throughput_per_second
    )
    if median_change is None or p95_change is None:
        reasons.append("baseline and candidate both require successful measured samples")
    else:
        if median_change > allowed_regression_percent:
            reasons.append(
                f"median regressed by {median_change:.3f}% (limit {allowed_regression_percent:.3f}%)"
            )
        if p95_change > allowed_regression_percent:
            reasons.append(
                f"p95 regressed by {p95_change:.3f}% (limit {allowed_regression_percent:.3f}%)"
            )
    if len(candidate.failures) > len(baseline.failures):
        reasons.append("candidate has more measured failures than baseline")
    if (candidate.measured_runs or 0) < (baseline.measured_runs or 0):
        reasons.append("candidate has fewer measured runs than baseline")
    if (candidate.warmup_runs or 0) < (baseline.warmup_runs or 0):
        reasons.append("candidate has fewer warmup runs than baseline")
    if (baseline.measured_runs or 0) < baseline.minimum_measured_runs:
        reasons.append("baseline does not meet its minimum measured-run requirement")
    if (candidate.measured_runs or 0) < candidate.minimum_measured_runs:
        reasons.append("candidate does not meet its minimum measured-run requirement")
    if (baseline.warmup_runs or 0) < baseline.minimum_warmup_runs:
        reasons.append("baseline does not meet its minimum warmup-run requirement")
    if (candidate.warmup_runs or 0) < candidate.minimum_warmup_runs:
        reasons.append("candidate does not meet its minimum warmup-run requirement")
    if candidate.minimum_measured_runs != baseline.minimum_measured_runs:
        reasons.append("candidate measured-run requirement differs from baseline")
    if candidate.minimum_warmup_runs != baseline.minimum_warmup_runs:
        reasons.append("candidate warmup-run requirement differs from baseline")
    if candidate.maximum_p95_ms != baseline.maximum_p95_ms:
        reasons.append("candidate hard p95 limit differs from baseline")
    if (
        baseline.maximum_p95_ms is not None
        and baseline.p95_ms is not None
        and baseline.p95_ms > baseline.maximum_p95_ms
    ):
        reasons.append(
            f"baseline p95 exceeds hard limit of {baseline.maximum_p95_ms:.3f} ms"
        )
    if (
        baseline.maximum_p95_ms is not None
        and candidate.p95_ms is not None
        and candidate.p95_ms > baseline.maximum_p95_ms
    ):
        reasons.append(
            f"candidate p95 exceeds hard limit of {baseline.maximum_p95_ms:.3f} ms"
        )

    baseline_has_work = bool(baseline.work_units)
    candidate_has_work = bool(candidate.work_units)
    if baseline_has_work != candidate_has_work:
        reasons.append("candidate throughput evidence differs from baseline")
    elif baseline_has_work:
        if baseline.unit_name != candidate.unit_name:
            reasons.append("candidate throughput unit differs from baseline")
        if baseline.work_units != candidate.work_units:
            reasons.append("candidate work units differ from baseline")
        if (
            throughput_change is not None
            and throughput_change < -allowed_regression_percent
        ):
            reasons.append(
                f"throughput regressed by {-throughput_change:.3f}% (limit {allowed_regression_percent:.3f}%)"
            )

    return ScenarioComparison(
        baseline.key,
        not reasons,
        median_change,
        p95_change,
        throughput_change,
        len(baseline.failures),
        len(candidate.failures),
        tuple(reasons),
    )


def _metric_change(
    baseline: Optional[float], candidate: Optional[float]
) -> Optional[float]:
    """Return no comparison when either report lacks successful timing evidence."""

    if baseline is None or candidate is None:
        return None
    return _change_percent(baseline, candidate)
