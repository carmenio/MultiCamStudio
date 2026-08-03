"""SDK-style HTTP benchmark entry point for locally running MultiCamStudio services."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.performance import (
    BenchmarkObservation,
    BenchmarkRunner,
    BenchmarkScenario,
    write_report,
)

# Configure a controlled local target here before running this file directly.
BASE_URL = "https://127.0.0.1"
OUTPUT_PATH = Path("tools/performance/output/http_baseline.json")
REQUEST_TIMEOUT_SECONDS = 30.0
VERIFY_TLS = False
HTTP_SCENARIOS: tuple["HttpScenario", ...] = ()
# Supply every controlled field required by performance_regression.md.
BENCHMARK_METADATA: dict[str, object] = {}


@dataclass(frozen=True)
class HttpScenario:
    """Defines a read-only endpoint benchmark and optional throughput evidence."""

    name: str
    path: str
    cache_state: str
    headers: Optional[Mapping[str, str]] = None
    expected_status: int = 200
    work_units: Optional[float] = None
    unit_name: Optional[str] = None
    before_each: Optional[Callable[[], None]] = None
    approved_long_workflow: bool = False
    maximum_p95_ms: Optional[float] = None


def run_configured_suite() -> Path:
    """Run configured HTTP scenarios and write a versioned JSON baseline report."""

    if not HTTP_SCENARIOS:
        raise RuntimeError("configure HTTP_SCENARIOS before running the HTTP benchmark")

    benchmark_scenarios = tuple(_to_benchmark_scenario(item) for item in HTTP_SCENARIOS)
    results = BenchmarkRunner().run_suite(benchmark_scenarios)
    write_report(OUTPUT_PATH, results, _environment_metadata())
    return OUTPUT_PATH


def _to_benchmark_scenario(configuration: HttpScenario) -> BenchmarkScenario:
    """Adapt an HTTP configuration into the generic callable benchmark contract."""

    return BenchmarkScenario(
        name=configuration.name,
        cache_state=configuration.cache_state,
        operation=lambda: _request(configuration),
        before_each=configuration.before_each,
        approved_long_workflow=configuration.approved_long_workflow,
        maximum_p95_ms=configuration.maximum_p95_ms,
    )


def _request(configuration: HttpScenario) -> Optional[BenchmarkObservation]:
    """Perform one request and reject unexpected status codes as measured failures."""

    request = Request(
        f"{BASE_URL.rstrip('/')}/{configuration.path.lstrip('/')}",
        headers=dict(configuration.headers or {}),
        method="GET",
    )
    context = None
    if not VERIFY_TLS:
        import ssl

        context = ssl._create_unverified_context()  # Controlled local HTTPS only.
    try:
        response = urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=context)
    except HTTPError as error:
        # HTTPError is still a valid response when the scenario expects that status.
        response = error
    with response:
        response.read()
        response_status = int(response.status)
        if response_status != configuration.expected_status:
            raise RuntimeError(
                f"expected HTTP {configuration.expected_status}, received {response_status}"
            )
    if configuration.work_units is None or configuration.unit_name is None:
        return None
    return BenchmarkObservation(configuration.work_units, configuration.unit_name)


def _environment_metadata() -> dict[str, object]:
    """Combine basic runtime identity with workflow-owned comparison controls."""

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        **BENCHMARK_METADATA,
        "commit": commit or "unknown",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "base_url": BASE_URL,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "tls_verification": VERIFY_TLS,
    }


if __name__ == "__main__":
    print(run_configured_suite())
