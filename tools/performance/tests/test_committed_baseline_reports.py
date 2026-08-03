"""Validate that every committed benchmark baseline is comparison-ready."""

from pathlib import Path

from tools.performance import compare_report_files


RESULTS_ROOT = Path("tools/performance/results")


def _committed_baseline_reports() -> tuple[Path, ...]:
    """Return benchmark reports while excluding non-report fixture manifests."""

    reports = set(RESULTS_ROOT.glob("**/*baseline*.json"))
    reports.add(RESULTS_ROOT / "phase_00_live" / "phase_00_live_benchmark.json")
    return tuple(sorted(reports))


def test_every_committed_baseline_passes_the_universal_self_gate() -> None:
    """Prevent incomplete provenance or invalid scenarios from entering baseline history."""

    failures: list[str] = []
    for report_path in _committed_baseline_reports():
        comparison = compare_report_files(report_path, report_path)
        if not comparison.passed:
            reasons = (*comparison.context_reasons, *comparison.failure_reasons)
            failures.append(f"{report_path.as_posix()}: {'; '.join(reasons)}")

    assert not failures, "\n".join(failures)
