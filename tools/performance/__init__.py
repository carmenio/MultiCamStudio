"""Stable public interface for MultiCamStudio performance measurements."""

from .comparison import (
    ComparisonReport,
    ScenarioComparison,
    compare_report_files,
    compare_reports,
)
from .models import BenchmarkObservation, BenchmarkResult, BenchmarkScenario
from .reporting import read_report, write_report
from .runner import BenchmarkRunner

__all__ = [
    "BenchmarkObservation",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkScenario",
    "ComparisonReport",
    "ScenarioComparison",
    "compare_report_files",
    "compare_reports",
    "read_report",
    "write_report",
]
