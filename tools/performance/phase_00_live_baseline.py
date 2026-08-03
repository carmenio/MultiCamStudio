"""Read-only live baseline runner for currently available MultiCamStudio workflows.

The runner never clears server caches or invokes workflow mutations. A
"header-bypass" sample uses standard cache-bypass request headers; a "warm"
sample primes the same read-only URL before measurements. Header bypass is not
cold-cache evidence. Scenarios that cannot be safely derived from the selected
fixture remain explicit in the manifest.
"""

from __future__ import annotations

import hashlib
import json
import platform
import ssl
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from tools.performance import (
    BenchmarkObservation,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkScenario,
    write_report,
)

# SDK-style configuration. Change these constants for a controlled local run.
PC_BASE_URL = "https://127.0.0.1:5000"
LAPTOP_BASE_URL = "https://127.0.0.1:9443"
OUTPUT_DIRECTORY = Path("tools/performance/results/phase_00_live")
REQUEST_TIMEOUT_SECONDS = 15.0
VERIFY_TLS = False
FIXTURE_SESSION_ID: int | None = 49
FIXTURE_RECORDING_SET_ID: int | None = 178
FIXTURE_RECORDING_ID: int | None = 649
FIXTURE_RECORDING_IDS: tuple[int, ...] = (649, 650, 651)
FIXTURE_CALIBRATION_BATCH_ID: int | None = 114
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"
NETWORK_ROUTE = "PC https://127.0.0.1:5000; laptop proxy https://127.0.0.1:9443"
DATABASE_SNAPSHOT = "live fixture observed 2026-08-03; session 49; recording set 178"
BUILD_MODE = "bind-mounted Docker services and production-built operator frontend"
DEPENDENCY_VERSIONS = {
    "backend": "tools/performance/environments/phase_01_backend_pip_freeze.txt",
    "operator_lockfile": "laptop/package-lock.json",
}
COMPOSE_CONFIGURATION = "3f3fc93872540702653310569ed6a7bd5e4933151bfc6e1207db05b14e591251"
SERVICE_IMAGES = {
    "backend": "sha256:55ddc0be147281760c667d996685c8b5eb3daa3efc52cdf456919c50a56320f7"
}
CAMERA_COUNT = 3
RECORDING_DURATION_SECONDS = (196.1, 195.8, 195.766666666667)
MEDIA_SIZES_BYTES = (450821959, 445290517, 448855126)


@dataclass(frozen=True)
class LiveBaselineConfig:
    """Holds controlled targets, fixture overrides, and evidence destinations."""

    pc_base_url: str = PC_BASE_URL
    laptop_base_url: str = LAPTOP_BASE_URL
    output_directory: Path = OUTPUT_DIRECTORY
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    verify_tls: bool = VERIFY_TLS
    fixture_session_id: int | None = FIXTURE_SESSION_ID
    fixture_recording_set_id: int | None = FIXTURE_RECORDING_SET_ID
    fixture_recording_id: int | None = FIXTURE_RECORDING_ID
    fixture_recording_ids: tuple[int, ...] = FIXTURE_RECORDING_IDS
    fixture_calibration_batch_id: int | None = FIXTURE_CALIBRATION_BATCH_ID
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS


@dataclass(frozen=True)
class ReadOnlyResponse:
    """Contains the status, body, and headers needed for validation evidence."""

    status: int
    body: bytes
    headers: Mapping[str, str]


class ReadOnlyClient(Protocol):
    """Restricts live-baseline transport adapters to side-effect-free GETs."""

    def get(
        self, url: str, headers: dict[str, str] | None = None
    ) -> ReadOnlyResponse:
        """Read one resource without mutating application state."""


class UrllibReadOnlyClient:
    """Performs local GET requests with explicit TLS and timeout controls."""

    def __init__(self, timeout_seconds: float, verify_tls: bool) -> None:
        self._timeout_seconds = timeout_seconds
        self._context = None if verify_tls else ssl._create_unverified_context()

    def get(
        self, url: str, headers: dict[str, str] | None = None
    ) -> ReadOnlyResponse:
        """Return both successful and HTTP-error responses for availability checks."""

        request = Request(url, headers=dict(headers or {}), method="GET")
        try:
            response = urlopen(
                request,
                timeout=self._timeout_seconds,
                context=self._context,
            )
        except HTTPError as error:
            response = error
        with response:
            return ReadOnlyResponse(
                int(response.status),
                response.read(),
                dict(response.headers.items()),
            )


@dataclass(frozen=True)
class _ScenarioDefinition:
    """Describes one validated read-only request before benchmark adaptation."""

    name: str
    url: str
    cache_state: str
    expected_statuses: tuple[int, ...] = (200,)
    headers: Mapping[str, str] | None = None
    unit_name: str | None = None
    maximum_p95_ms: float | None = None


class _StableResponseOperation:
    """Rejects response changes so timing samples retain output equivalence proof."""

    def __init__(
        self,
        client: ReadOnlyClient,
        definition: _ScenarioDefinition,
    ) -> None:
        self._client = client
        self._definition = definition
        self._expected_identity: str | None = None

    @property
    def expected_identity(self) -> str | None:
        """Expose the stable digest captured by the first successful request."""

        return self._expected_identity

    def __call__(self) -> BenchmarkObservation | None:
        """Read the resource and validate status plus canonical response identity."""

        response = self._client.get(
            self._definition.url,
            _request_headers(self._definition),
        )
        if response.status not in self._definition.expected_statuses:
            raise RuntimeError(
                f"expected HTTP {self._definition.expected_statuses}, received {response.status}"
            )
        identity = _response_identity(response)
        if self._expected_identity is None:
            self._expected_identity = identity
        elif identity != self._expected_identity:
            raise RuntimeError(
                "response identity changed during repeated measurement: "
                f"{self._expected_identity} -> {identity}"
            )
        if self._definition.unit_name is None:
            return None
        return BenchmarkObservation(float(len(response.body)), self._definition.unit_name)


def _request_headers(definition: _ScenarioDefinition) -> dict[str, str]:
    """Build observable cache-state evidence without issuing cache mutations."""

    headers = dict(definition.headers or {})
    headers["X-MCS-Benchmark-Cache"] = definition.cache_state
    if definition.cache_state == "header-bypass":
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
    return headers


def _response_identity(response: ReadOnlyResponse) -> str:
    """Hash canonical body plus representation headers relevant to immutable media."""

    body = response.body
    try:
        parsed = json.loads(body.decode("utf-8"))
        body = json.dumps(
            parsed, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    normalized_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
    representation_headers = {
        key: normalized_headers[key]
        for key in ("content-range", "etag", "last-modified", "content-encoding")
        if key in normalized_headers
    }
    evidence = (
        str(response.status).encode("ascii")
        + b"\0"
        + json.dumps(representation_headers, sort_keys=True).encode("utf-8")
        + b"\0"
        + body
    )
    return hashlib.sha256(evidence).hexdigest()


def _json_object(response: ReadOnlyResponse) -> dict[str, Any] | None:
    """Return an object response only when it is successful, JSON, and object-shaped."""

    if response.status != 200:
        return None
    try:
        value = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_json_if_available(
    client: ReadOnlyClient,
    url: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Make optional fixture discovery tolerant of unavailable live services."""

    try:
        return _json_object(client.get(url, headers))
    except Exception:
        return None


def _url(base_url: str, path: str) -> str:
    """Join controlled service origins and route paths without losing base ports."""

    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _as_positive_int(value: object) -> int | None:
    """Normalize fixture identifiers while rejecting booleans and invalid values."""

    if isinstance(value, bool):
        return None
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _discover_fixture(
    sessions_payload: dict[str, Any] | None,
    config: LiveBaselineConfig,
) -> dict[str, Any]:
    """Select explicit fixture IDs first, then the first coherent read-only session set."""

    session_id = config.fixture_session_id
    set_id = config.fixture_recording_set_id
    recording_id = config.fixture_recording_id
    recording_ids = list(config.fixture_recording_ids)
    calibration_id: int | None = None
    sessions = (sessions_payload or {}).get("data")
    if not isinstance(sessions, dict):
        sessions = {}

    if session_id is None:
        session_id = next(
            (_as_positive_int(key) for key in sessions if _as_positive_int(key)), None
        )
    selected_session = sessions.get(str(session_id), sessions.get(session_id))
    if not isinstance(selected_session, dict):
        selected_session = {}

    recording_sets = selected_session.get("Recording_Sets")
    if not isinstance(recording_sets, dict):
        recording_sets = {}
    if set_id is None:
        set_id = next(
            (_as_positive_int(key) for key in recording_sets if _as_positive_int(key)),
            None,
        )
    selected_set = recording_sets.get(str(set_id), recording_sets.get(set_id))
    if not isinstance(selected_set, dict):
        selected_set = {}
    if recording_id is None:
        for key, row in selected_set.items():
            if isinstance(row, dict):
                recording_id = _as_positive_int(row.get("id")) or _as_positive_int(key)
                if recording_id is not None:
                    break
    if not recording_ids:
        recording_ids = [
            normalized
            for key, row in selected_set.items()
            if isinstance(row, dict)
            for normalized in (_as_positive_int(row.get("id")) or _as_positive_int(key),)
            if normalized is not None
        ]
    if recording_id is not None and recording_id not in recording_ids:
        recording_ids.insert(0, recording_id)

    calibrations = selected_session.get("Calibrations")
    if isinstance(calibrations, list):
        calibration_id = next(
            (
                _as_positive_int(row.get("id"))
                for row in calibrations
                if isinstance(row, dict) and _as_positive_int(row.get("id"))
            ),
            None,
        )
    return {
        "session_id": session_id,
        "recording_set_id": set_id,
        "recording_id": recording_id,
        "recording_ids": recording_ids,
        "calibration_id": calibration_id,
        "calibration_batch_id": config.fixture_calibration_batch_id,
    }


def _find_variant_key(value: object) -> str | None:
    """Find the first concrete point-detection variant in summary-shaped JSON."""

    if isinstance(value, dict):
        direct = value.get("variant_key")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        for nested in value.values():
            found = _find_variant_key(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_variant_key(nested)
            if found:
                return found
    return None


def _find_completed_triangulation_run_id(value: object) -> int | None:
    """Find the first completed run identifier in the lightweight runs response."""

    if isinstance(value, dict):
        status = str(value.get("status") or "").strip().lower()
        run_id = _as_positive_int(value.get("id"))
        if status == "done" and run_id is not None:
            return run_id
        for nested in value.values():
            found = _find_completed_triangulation_run_id(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_completed_triangulation_run_id(nested)
            if found is not None:
                return found
    return None


def _discover_playback_media_url(
    payload: dict[str, Any] | None, pc_base_url: str
) -> str | None:
    """Resolve the current playback URL without guessing a storage path."""

    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        return None
    for key in ("url", "playback_url", "fallback_url", "file_path"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return _url(pc_base_url, value.strip())
    return None


def _probe(
    client: ReadOnlyClient,
    definition: _ScenarioDefinition,
) -> tuple[bool, ReadOnlyResponse | None, str | None]:
    """Check availability once and retain concrete reasons without fabricated samples."""

    try:
        response = client.get(definition.url, _request_headers(definition))
    except Exception as error:
        return False, None, f"{type(error).__name__}: {error}"
    if response.status not in definition.expected_statuses:
        return (
            False,
            response,
            f"expected HTTP {definition.expected_statuses}, received {response.status}",
        )
    return True, response, None


def _benchmark_definitions(
    config: LiveBaselineConfig,
    fixture: Mapping[str, Any],
    playback_media_url: str | None,
    variant_key: str | None,
    triangulation_run_id: int | None,
) -> tuple[list[_ScenarioDefinition], list[dict[str, Any]]]:
    """Build available candidates and explicit unavailable optional workflow records."""

    pc = config.pc_base_url
    laptop = config.laptop_base_url
    definitions = [
        _ScenarioDefinition("pc_sessions_ui", _url(pc, "/api/sessions-info?profile=ui"), "header-bypass"),
        _ScenarioDefinition("pc_sessions_ui", _url(pc, "/api/sessions-info?profile=ui"), "warm"),
        _ScenarioDefinition("pc_sessions_overview_full", _url(pc, "/api/sessions-info?profile=full"), "warm"),
        _ScenarioDefinition("laptop_health", _url(laptop, "/health"), "warm"),
        _ScenarioDefinition("operator_frontend", _url(laptop, "/"), "header-bypass"),
        _ScenarioDefinition("operator_frontend", _url(laptop, "/"), "warm"),
        _ScenarioDefinition("laptop_proxy_sessions_ui", _url(laptop, "/api/sessions-info?profile=ui"), "warm"),
    ]
    unavailable: list[dict[str, Any]] = []

    session_id = fixture.get("session_id")
    set_id = fixture.get("recording_set_id")
    recording_id = fixture.get("recording_id")
    recording_ids = fixture.get("recording_ids")
    calibration_id = fixture.get("calibration_id")
    calibration_batch_id = fixture.get("calibration_batch_id")

    if recording_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "recording_playback_source",
                _url(pc, f"/api/recordings/{recording_id}/playback-source"),
                "warm",
            )
        )
    else:
        unavailable.append(_unavailable("recording_playback_source", "no recording fixture was discovered"))
    if playback_media_url:
        definitions.append(
            _ScenarioDefinition(
                "recording_media_readiness",
                playback_media_url,
                "warm",
                expected_statuses=(200, 206),
                headers={"Range": "bytes=0-0"},
                unit_name="bytes",
            )
        )
    else:
        unavailable.append(_unavailable("recording_media_readiness", "playback source did not expose a media URL"))

    if set_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "detection_summary",
                _url(pc, f"/api/recording-sets/{set_id}/point-detection/summary"),
                "warm",
                maximum_p95_ms=500.0,
            )
        )
        definitions.append(
            _ScenarioDefinition(
                "triangulation_runs_metadata",
                _url(pc, f"/api/3d/recording-sets/{set_id}/triangulations/runs-lite"),
                "warm",
            )
        )
    else:
        unavailable.extend(
            [
                _unavailable("detection_summary", "no recording-set fixture was discovered"),
                _unavailable("triangulation_runs_metadata", "no recording-set fixture was discovered"),
            ]
        )
    if set_id is not None and variant_key:
        query_items: list[tuple[str, object]] = [
            ("variant_key", variant_key),
            ("segment_index", 0),
        ]
        if isinstance(recording_ids, list):
            query_items.extend(
                ("recording_ids", item)
                for item in recording_ids
                if _as_positive_int(item) is not None
            )
        segment_url = _url(
            pc,
            f"/api/recording-sets/{set_id}/point-detection/segments?{urlencode(query_items)}",
        )
        definitions.extend(
            [
                _ScenarioDefinition(
                    "detection_first_segment",
                    segment_url,
                    "warm",
                    maximum_p95_ms=500.0,
                    unit_name="bytes",
                ),
                _ScenarioDefinition(
                    "detection_uncached_seek_segment",
                    segment_url.replace("segment_index=0", "segment_index=1"),
                    "header-bypass",
                    maximum_p95_ms=500.0,
                    unit_name="bytes",
                ),
                _ScenarioDefinition(
                    "detection_sequential_segment",
                    segment_url.replace("segment_index=0", "segment_index=2"),
                    "warm",
                    maximum_p95_ms=500.0,
                    unit_name="bytes",
                ),
            ]
        )
    else:
        reason = "no stored detection variant was discovered"
        unavailable.extend(
            _unavailable(name, reason)
            for name in (
                "detection_first_segment",
                "detection_uncached_seek_segment",
                "detection_sequential_segment",
            )
        )

    if session_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "triangulation_session_status",
                _url(pc, f"/api/sessions/{session_id}/3d/triangulations/statuses"),
                "warm",
            )
        )
    else:
        unavailable.append(_unavailable("triangulation_session_status", "no session fixture was discovered"))
    if calibration_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "calibration_viewer_metadata",
                _url(pc, f"/api/calibrations/{calibration_id}/viewer"),
                "warm",
            )
        )
    else:
        unavailable.append(_unavailable("calibration_viewer_metadata", "no calibration fixture was discovered"))
    if calibration_batch_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "calibration_batch_status",
                _url(pc, f"/api/calibrations/batches/{calibration_batch_id}/status"),
                "warm",
            )
        )
    else:
        unavailable.append(_unavailable("calibration_batch_status", "no calibration batch fixture was configured"))
    if triangulation_run_id is not None:
        definitions.append(
            _ScenarioDefinition(
                "triangulation_result_retrieval",
                _url(pc, f"/api/3d/triangulation-runs/{triangulation_run_id}/result"),
                "warm",
                unit_name="bytes",
            )
        )
    else:
        unavailable.append(
            _unavailable(
                "triangulation_result_retrieval",
                "no completed triangulation run was discovered",
            )
        )
    return definitions, unavailable


def _unavailable(name: str, reason: str) -> dict[str, Any]:
    """Create a uniform no-evidence record for a safely skipped scenario."""

    return {
        "name": name,
        "cache_state": None,
        "status": "unavailable",
        "reason": reason,
        "failure_count": 0,
        "failures": [],
        "expected_output_identity": None,
    }


def _result_manifest_item(
    result: BenchmarkResult,
    expected_identity: str | None,
) -> dict[str, Any]:
    """Summarize benchmark evidence without hiding failed measurements."""

    return {
        "name": result.name,
        "cache_state": result.cache_state,
        "status": "available" if not result.failures and not result.warmup_failures else "failed",
        "reason": None,
        "failure_count": len(result.failures),
        "failures": list(result.failures),
        "warmup_failures": list(result.warmup_failures),
        "successful_runs": len(result.durations_ms),
        "expected_output_identity": expected_identity,
    }


def _write_atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Persist a manifest atomically so interrupted runs cannot look complete."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _commit_identity() -> str:
    """Capture the source revision used for the live evidence."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def _repository_revision(path: str) -> str:
    """Capture a subrepository revision whose runtime code participates in a run."""

    result = subprocess.run(
        ["git", "-C", path, "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def _command_version(command: list[str]) -> str:
    """Return a controlled tool version without making the benchmark depend on it."""

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        return f"unavailable: {error}"
    return result.stdout.strip() or result.stderr.strip() or "unknown"


def build_live_baseline(
    config: LiveBaselineConfig = LiveBaselineConfig(),
    *,
    client: ReadOnlyClient | None = None,
) -> dict[str, Any]:
    """Discover safe fixtures, benchmark available GET workflows, and write evidence."""

    transport = client or UrllibReadOnlyClient(
        config.request_timeout_seconds, config.verify_tls
    )
    ui_sessions_url = _url(config.pc_base_url, "/api/sessions-info?profile=ui")
    sessions_payload = _read_json_if_available(
        transport,
        ui_sessions_url,
        {"Cache-Control": "no-cache", "Pragma": "no-cache", "X-MCS-Benchmark-Cache": "header-bypass"},
    )
    fixture = _discover_fixture(sessions_payload, config)

    playback_payload: dict[str, Any] | None = None
    recording_id = fixture.get("recording_id")
    if recording_id is not None:
        playback_payload = _read_json_if_available(
            transport,
            _url(config.pc_base_url, f"/api/recordings/{recording_id}/playback-source"),
        )
    playback_media_url = _discover_playback_media_url(
        playback_payload, config.pc_base_url
    )

    detection_payload: dict[str, Any] | None = None
    set_id = fixture.get("recording_set_id")
    if set_id is not None:
        detection_payload = _read_json_if_available(
            transport,
            _url(
                config.pc_base_url,
                f"/api/recording-sets/{set_id}/point-detection/summary",
            ),
        )
    variant_key = _find_variant_key(detection_payload)
    triangulation_runs_payload: dict[str, Any] | None = None
    if set_id is not None:
        triangulation_runs_payload = _read_json_if_available(
            transport,
            _url(
                config.pc_base_url,
                f"/api/3d/recording-sets/{set_id}/triangulations/runs-lite",
            ),
        )
    triangulation_run_id = _find_completed_triangulation_run_id(
        triangulation_runs_payload
    )
    fixture = {
        **fixture,
        "variant_key": variant_key,
        "triangulation_run_id": triangulation_run_id,
    }
    definitions, manifest_items = _benchmark_definitions(
        config,
        fixture,
        playback_media_url,
        variant_key,
        triangulation_run_id,
    )

    available_definitions: list[_ScenarioDefinition] = []
    for definition in definitions:
        available, _, reason = _probe(transport, definition)
        if available:
            available_definitions.append(definition)
        else:
            manifest_items.append(_unavailable(definition.name, reason or "availability probe failed"))

    operations: list[_StableResponseOperation] = []
    scenarios: list[BenchmarkScenario] = []
    for definition in available_definitions:
        operation = _StableResponseOperation(transport, definition)
        operations.append(operation)
        scenarios.append(
            BenchmarkScenario(
                name=definition.name,
                cache_state=definition.cache_state,
                operation=operation,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
                maximum_p95_ms=definition.maximum_p95_ms,
            )
        )

    results = BenchmarkRunner().run_suite(scenarios)
    identity_by_key = {
        f"{definition.name}::{definition.cache_state}": operation.expected_identity
        for definition, operation in zip(available_definitions, operations)
    }
    manifest_items.extend(
        _result_manifest_item(result, identity_by_key.get(result.key))
        for result in results
    )
    manifest_items.sort(key=lambda item: (str(item["name"]), str(item["cache_state"])))

    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node": _command_version(["node", "--version"]),
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": NETWORK_ROUTE,
        "database_snapshot": DATABASE_SNAPSHOT,
        "build_mode": BUILD_MODE,
        "dependency_versions": DEPENDENCY_VERSIONS,
        "compose_configuration": COMPOSE_CONFIGURATION,
        "service_images": SERVICE_IMAGES,
        "camera_count": CAMERA_COUNT,
        "recording_duration_seconds": RECORDING_DURATION_SECONDS,
        "media_sizes_bytes": MEDIA_SIZES_BYTES,
        "pc_base_url": config.pc_base_url,
        "laptop_base_url": config.laptop_base_url,
        "cache_preparation": {
            "header-bypass": "GET with Cache-Control: no-cache and Pragma: no-cache; no cache deletion",
            "warm": "read-only availability probe and three warm-up GETs",
        },
        "fixture": fixture,
        "expected_output_identity": identity_by_key,
        "read_only_methods": ["GET"],
    }
    report_path = config.output_directory / "phase_00_live_benchmark.json"
    write_report(report_path, results, metadata)
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_report": str(report_path),
        "fixture": fixture,
        "safety": {
            "http_methods": ["GET"],
            "server_cache_mutations": False,
            "header_bypass_preparation": metadata["cache_preparation"]["header-bypass"],
            "warm_preparation": metadata["cache_preparation"]["warm"],
        },
        "scenarios": manifest_items,
    }
    _write_atomic_json(
        config.output_directory / "phase_00_live_manifest.json", manifest
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_live_baseline(), indent=2))
