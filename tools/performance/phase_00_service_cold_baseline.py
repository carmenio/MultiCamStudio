"""Measure first-request latency after a controlled backend service restart."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from tools.performance import BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import (
    ReadOnlyClient,
    UrllibReadOnlyClient,
    _commit_identity,
    _repository_revision,
    _response_identity,
)

# SDK-style configuration for the controlled local Compose environment.
PC_COMPOSE_DIRECTORY = Path("pc")
BACKEND_SERVICE_NAME = "backend"
HEALTH_URL = "https://127.0.0.1:5000/health"
TARGET_URL = "https://127.0.0.1:5000/api/sessions-info?profile=ui"
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_service_cold/phase_00_service_cold_baseline.json"
)
REQUEST_TIMEOUT_SECONDS = 15.0
READINESS_TIMEOUT_SECONDS = 30.0
READINESS_POLL_SECONDS = 0.2
VERIFY_TLS = False
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"
DATABASE_SNAPSHOT = "live fixture observed 2026-08-03; session 49; recording set 178"


class BackendRestarter(Protocol):
    """Restarts only the backend service while leaving dependencies running."""

    def restart(self) -> None:
        """Return after Compose accepts and completes the backend restart."""


class ComposeBackendRestarter:
    """Uses the checked-in PC Compose project to restart its backend service."""

    def __init__(self, compose_directory: Path, service_name: str) -> None:
        self._compose_directory = compose_directory
        self._service_name = service_name

    def restart(self) -> None:
        """Restart the exact configured service or fail the current sample."""

        subprocess.run(
            ["docker", "compose", "restart", self._service_name],
            cwd=self._compose_directory,
            check=True,
            capture_output=True,
            text=True,
        )


@dataclass(frozen=True)
class ServiceColdConfig:
    """Controls service restart, readiness, target, and evidence output."""

    health_url: str = HEALTH_URL
    target_url: str = TARGET_URL
    output_path: Path = OUTPUT_PATH
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    readiness_timeout_seconds: float = READINESS_TIMEOUT_SECONDS
    readiness_poll_seconds: float = READINESS_POLL_SECONDS
    verify_tls: bool = VERIFY_TLS
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS


class _ServiceColdPreparation:
    """Restarts the backend and proves readiness before a first target request."""

    def __init__(
        self,
        restarter: BackendRestarter,
        client: ReadOnlyClient,
        config: ServiceColdConfig,
    ) -> None:
        self._restarter = restarter
        self._client = client
        self._config = config
        self.restart_durations_ms: list[float] = []

    def __call__(self) -> None:
        started_at = time.perf_counter()
        self._restarter.restart()
        deadline = time.monotonic() + self._config.readiness_timeout_seconds
        last_status: int | None = None
        while time.monotonic() < deadline:
            try:
                response = self._client.get(self._config.health_url)
                last_status = response.status
                if response.status == 200:
                    self.restart_durations_ms.append(
                        (time.perf_counter() - started_at) * 1000.0
                    )
                    return
            except Exception:
                pass
            time.sleep(self._config.readiness_poll_seconds)
        raise TimeoutError(
            "backend did not become healthy within "
            f"{self._config.readiness_timeout_seconds:.1f}s; last status={last_status}"
        )


class _StableFirstRequest:
    """Times the first session request and rejects output drift between restarts."""

    def __init__(self, client: ReadOnlyClient, target_url: str) -> None:
        self._client = client
        self._target_url = target_url
        self.identity: str | None = None

    def __call__(self):
        response = self._client.get(
            self._target_url,
            {"X-MCS-Benchmark-Cache": "service-cold"},
        )
        if response.status != 200:
            raise RuntimeError(f"expected HTTP 200, received {response.status}")
        identity = _response_identity(response)
        if self.identity is None:
            self.identity = identity
        elif identity != self.identity:
            raise RuntimeError(
                f"response identity changed between restarts: {self.identity} -> {identity}"
            )
        return None


def build_service_cold_baseline(
    config: ServiceColdConfig = ServiceColdConfig(),
    *,
    client: ReadOnlyClient | None = None,
    restarter: BackendRestarter | None = None,
) -> dict[str, object]:
    """Restart, wait for health, measure the first query, and persist raw evidence."""

    transport = client or UrllibReadOnlyClient(
        config.request_timeout_seconds, config.verify_tls
    )
    backend_restarter = restarter or ComposeBackendRestarter(
        PC_COMPOSE_DIRECTORY, BACKEND_SERVICE_NAME
    )
    preparation = _ServiceColdPreparation(backend_restarter, transport, config)
    operation = _StableFirstRequest(transport, config.target_url)
    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="pc_sessions_ui_first_request_after_backend_restart",
            cache_state="cold",
            operation=operation,
            before_each=preparation,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
        )
    )
    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "database_snapshot": DATABASE_SNAPSHOT,
        "compose_directory": str(PC_COMPOSE_DIRECTORY),
        "compose_service": BACKEND_SERVICE_NAME,
        "health_url": config.health_url,
        "target_url": config.target_url,
        "cache_preparation": "docker compose restart backend; health-only readiness polling",
        "restart_readiness_durations_ms": preparation.restart_durations_ms,
        "expected_output_identity": operation.identity,
        "configuration_hash": hashlib.sha256(
            json.dumps(
                {
                    "health_url": config.health_url,
                    "target_url": config.target_url,
                    "warmup_runs": config.warmup_runs,
                    "measured_runs": config.measured_runs,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_service_cold_baseline()
    result = outcome["result"]
    print(
        json.dumps(
            {
                "name": result.name,
                "median_ms": result.median_ms,
                "p95_ms": result.p95_ms,
                "failures": list(result.failures),
                "warmup_failures": list(result.warmup_failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
