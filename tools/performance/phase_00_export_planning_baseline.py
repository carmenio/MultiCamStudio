"""Benchmark dataset-export planning through the production HTTP contract."""

from __future__ import annotations

import hashlib
import json
import platform
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.performance import BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import (
    CAMERA_COUNT,
    COMPOSE_CONFIGURATION,
    DEPENDENCY_VERSIONS,
    MEDIA_SIZES_BYTES,
    RECORDING_DURATION_SECONDS,
    SERVICE_IMAGES,
    _command_version,
    _commit_identity,
    _repository_revision,
)

# SDK-style fixed fixture and local production endpoint configuration.
PREFLIGHT_URL = "https://127.0.0.1:5000/api/exports/preflight"
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_export_planning/phase_00_export_planning_baseline.json"
)
REQUEST_TIMEOUT_SECONDS = 30.0
VERIFY_TLS = False
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"
DATABASE_SNAPSHOT = "live fixture observed 2026-08-03; session 49; recording set 178"
EXPORT_SPECIFICATION = {
    "recipe": "three_d_only",
    "sets": [
        {
            "session_id": 49,
            "recording_set_id": 178,
            "triangulation_run_id": 100,
        }
    ],
    "formats": ["npy", "csv", "jsonl"],
    "range": {"base": "full", "quality_enabled": False},
    "point_schema": {
        "labels": [],
        "target_point_count": 0,
        "skeleton_connections": [],
    },
    "export_name": "Phase 0 benchmark",
    "destination_subfolder": "",
}


@dataclass(frozen=True)
class JsonResponse:
    """Contains the status and body required to validate one planning response."""

    status: int
    body: bytes


class PlanningClient(Protocol):
    """Restricts this runner to the non-persisting export-preflight operation."""

    def post_json(self, url: str, payload: Mapping[str, Any]) -> JsonResponse:
        """Post one controlled JSON specification and return its response."""


class UrllibPlanningClient:
    """Sends JSON to the local production API with explicit TLS controls."""

    def __init__(self, timeout_seconds: float, verify_tls: bool) -> None:
        self._timeout_seconds = timeout_seconds
        self._context = None if verify_tls else ssl._create_unverified_context()

    def post_json(self, url: str, payload: Mapping[str, Any]) -> JsonResponse:
        request = Request(
            url,
            data=json.dumps(dict(payload), separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-MCS-Benchmark-Cache": "warm",
            },
            method="POST",
        )
        try:
            response = urlopen(
                request,
                timeout=self._timeout_seconds,
                context=self._context,
            )
        except HTTPError as error:
            response = error
        with response:
            return JsonResponse(int(response.status), response.read())


@dataclass(frozen=True)
class ExportPlanningConfig:
    """Controls the fixed reviewed source and result destination."""

    preflight_url: str = PREFLIGHT_URL
    output_path: Path = OUTPUT_PATH
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    verify_tls: bool = VERIFY_TLS
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    specification: Mapping[str, Any] = field(
        default_factory=lambda: EXPORT_SPECIFICATION
    )


def _semantic_preflight_identity(payload: dict[str, Any]) -> str:
    """Hash the plan while excluding only the environment's changing free-space count."""

    canonical = json.loads(json.dumps(payload))
    data = canonical.get("data")
    if isinstance(data, dict):
        destination = data.get("destination")
        if isinstance(destination, dict):
            destination.pop("free_bytes", None)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class _StableExportPreflight:
    """Rejects status, eligibility, or semantic planning drift between samples."""

    def __init__(
        self,
        client: PlanningClient,
        config: ExportPlanningConfig,
    ) -> None:
        self._client = client
        self._config = config
        self.identity: str | None = None
        self.preflight_hash: str | None = None

    def __call__(self):
        response = self._client.post_json(
            self._config.preflight_url,
            self._config.specification,
        )
        if response.status != 200:
            raise RuntimeError(
                f"expected HTTP 200, received {response.status}: "
                f"{response.body[:500].decode('utf-8', errors='replace')}"
            )
        payload = json.loads(response.body.decode("utf-8"))
        data = payload.get("data")
        if not isinstance(data, dict) or int(data.get("eligible_count") or 0) != 1:
            raise RuntimeError("controlled export specification is not exactly one eligible set")
        preflight_hash = str(data.get("preflight_hash") or "")
        if not preflight_hash:
            raise RuntimeError("export preflight did not return a review hash")
        identity = _semantic_preflight_identity(payload)
        if self.identity is None:
            self.identity = identity
            self.preflight_hash = preflight_hash
        elif identity != self.identity or preflight_hash != self.preflight_hash:
            raise RuntimeError("export preflight plan changed during repeated measurement")
        return None


def build_export_planning_baseline(
    config: ExportPlanningConfig = ExportPlanningConfig(),
    *,
    client: PlanningClient | None = None,
) -> dict[str, object]:
    """Measure non-persisting export planning and write auditable raw samples."""

    transport = client or UrllibPlanningClient(
        config.request_timeout_seconds, config.verify_tls
    )
    operation = _StableExportPreflight(transport, config)
    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="dataset_export_preflight",
            cache_state="warm",
            operation=operation,
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
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node": _command_version(["node", "--version"]),
        "dependency_versions": DEPENDENCY_VERSIONS,
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "database_snapshot": DATABASE_SNAPSHOT,
        "network_route": config.preflight_url,
        "build_mode": "bind-mounted Docker backend",
        "compose_configuration": COMPOSE_CONFIGURATION,
        "service_images": SERVICE_IMAGES,
        "cache_preparation": "same live database snapshot; three warm-up preflights",
        "camera_count": CAMERA_COUNT,
        "recording_duration_seconds": RECORDING_DURATION_SECONDS,
        "media_sizes_bytes": MEDIA_SIZES_BYTES,
        "fixture": config.specification,
        "expected_output_identity": operation.identity,
        "preflight_hash": operation.preflight_hash,
        "side_effects": "none; preflight does not create an export job or write artifacts",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_export_planning_baseline()
    result = outcome["result"]
    print(
        json.dumps(
            {
                "name": result.name,
                "median_ms": result.median_ms,
                "p95_ms": result.p95_ms,
                "failures": list(result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
