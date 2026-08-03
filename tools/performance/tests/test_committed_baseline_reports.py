"""Validate that every committed benchmark baseline is comparison-ready."""

import json
from pathlib import Path
from typing import Any

from tools.performance import compare_report_files


RESULTS_ROOT = Path("tools/performance/results")


def _committed_baseline_reports() -> tuple[Path, ...]:
    """Return benchmark reports while excluding non-report fixture manifests."""

    reports = set(RESULTS_ROOT.glob("**/*baseline*.json"))
    reports.add(RESULTS_ROOT / "phase_00_live" / "phase_00_live_benchmark.json")
    return tuple(sorted(reports))


def _execution_evidence_failures(report: dict[str, Any]) -> list[str]:
    """Reject measured failures while retaining explicit unavailable scenarios."""

    failures: list[str] = []
    for scenario in report.get("results", []):
        name = scenario.get("name", "unnamed scenario")
        measured_failures = scenario.get("failures", [])
        failure_count = scenario.get("failure_count", 0)
        samples = scenario.get("samples_ms", [])
        successful_runs = scenario.get("successful_runs", len(samples))
        if failure_count != len(measured_failures):
            failures.append(f"{name}: failure count does not match failure details")
        if failure_count != 0 or measured_failures:
            failures.append(f"{name}: measured executions include failures")
        if successful_runs != len(samples):
            failures.append(f"{name}: successful run count does not match committed samples")
        if scenario.get("warmup_failures", []):
            failures.append(f"{name}: warm-up executions include failures")

    for unavailable in report.get("unavailable", []):
        if (
            unavailable.get("status") != "unavailable"
            or not unavailable.get("name")
            or not unavailable.get("reason")
        ):
            failures.append("unavailable scenario lacks name, status, or reason")
    return failures


def test_every_committed_baseline_passes_the_universal_self_gate() -> None:
    """Prevent incomplete provenance or invalid scenarios from entering baseline history."""

    failures: list[str] = []
    for report_path in _committed_baseline_reports():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for reason in _execution_evidence_failures(report):
            failures.append(f"{report_path.as_posix()}: {reason}")
        comparison = compare_report_files(report_path, report_path)
        if not comparison.passed:
            reasons = (*comparison.context_reasons, *comparison.failure_reasons)
            failures.append(f"{report_path.as_posix()}: {'; '.join(reasons)}")

    assert not failures, "\n".join(failures)


def test_execution_evidence_rejects_measured_and_warmup_failures() -> None:
    """Keep the repository-wide gate stricter than a self-comparison."""

    report = {
        "results": [
            {
                "name": "measured",
                "failure_count": 1,
                "failures": ["timeout"],
                "samples_ms": [],
                "successful_runs": 0,
                "warmup_failures": [],
            },
            {
                "name": "warmup",
                "failure_count": 0,
                "failures": [],
                "samples_ms": [],
                "successful_runs": 0,
                "warmup_failures": ["timeout"],
            },
        ],
        "unavailable": [],
    }

    assert _execution_evidence_failures(report) == [
        "measured: measured executions include failures",
        "warmup: warm-up executions include failures",
    ]


def test_execution_evidence_accepts_a_well_formed_unavailable_scenario() -> None:
    """Unavailable work stays visible as a phase blocker, not a timed failure."""

    report = {
        "results": [],
        "unavailable": [
            {"name": "recording_seek_readiness", "status": "unavailable", "reason": "timed out"}
        ],
    }

    assert _execution_evidence_failures(report) == []
