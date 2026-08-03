"""Benchmark All-page five-stage dispatch through the production Flask route."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from flask import Flask

from tools.performance import (
    BenchmarkObservation,
    BenchmarkRunner,
    BenchmarkScenario,
    write_report,
)
from tools.performance.phase_00_live_baseline import (
    _command_version,
    _commit_identity,
    _repository_revision,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Controllers.AllTabController import AllTabController  # noqa: E402


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_pipeline_dispatch/phase_00_pipeline_dispatch_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 10
RECORDING_SET_COUNT = 10
SESSION_ID = 49
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class PipelineDispatchConfig:
    """Controls the fixed route workload and report destination."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    recording_set_count: int = RECORDING_SET_COUNT


class _RecordingDatabase:
    """Provides deterministic recording-set rows and captures link writes."""

    def __init__(self, rows: dict[int, dict[str, Any]]) -> None:
        self.rows = rows
        self.link_updates: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear writes while retaining the immutable fixture rows."""

        self.link_updates.clear()

    def get_recording_set_minimal(self, recording_set_id: int):
        """Return the production adapter's list-shaped minimal response."""

        row = self.rows.get(int(recording_set_id))
        return [dict(row)] if row else []

    def update_recording_set_link(self, **values) -> None:
        """Capture the exact link update issued by the controller."""

        self.link_updates.append(dict(values))


class _SyncDatabase:
    """Reject unexpected sync-readiness reads in the sync-enabled fixture."""

    def get_synced_recordings_by_ids(self, _recording_ids):
        """Return no rows; this method must not affect a sync-enabled dispatch."""

        return {}


class _CalibrationDatabase:
    """Creates deterministic calibration batch identifiers."""

    def __init__(self) -> None:
        self.batches: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset generated batch identifiers before each benchmark sample."""

        self.batches.clear()

    def has_successful_calibration(self, _recording_set_id: int) -> bool:
        """Keep cross-set compatibility validation available if the fixture changes."""

        return True

    def create_batch(self, **values):
        """Create the list-order-stable batch returned to task construction."""

        row = {"id": len(self.batches) + 1, **values}
        self.batches.append(row)
        return dict(row)


class _TaskDatabase:
    """Captures deterministic task chains without a live queue or worker."""

    def __init__(self) -> None:
        self.tasks: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset task identifiers before each benchmark sample."""

        self.tasks.clear()

    def find_active_duplicate(self, *_args, **_kwargs):
        """Force creation of the full canonical five-stage chain."""

        return None

    def create_task(self, **values):
        """Return the task shape consumed by the production controller."""

        row = {"id": len(self.tasks) + 1, **values}
        self.tasks.append(row)
        return {"id": row["id"], "task_type": row["task_type"]}


def _canonical_identity(payload: Any) -> str:
    """Hash complete route output outside the measured interval."""

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


class _PipelineDispatchEnvironment:
    """Mount production routes around deterministic persistence adapters."""

    def __init__(self, recording_set_count: int) -> None:
        if recording_set_count <= 0:
            raise ValueError("recording_set_count must be positive")
        self.recording_set_ids = list(range(1_001, 1_001 + recording_set_count))
        rows = {
            recording_set_id: {
                "id": recording_set_id,
                "session_id": SESSION_ID,
                "linked_calibrated_set_id": None,
            }
            for recording_set_id in self.recording_set_ids
        }
        self.recording_database = _RecordingDatabase(rows)
        self.sync_database = _SyncDatabase()
        self.calibration_database = _CalibrationDatabase()
        self.task_database = _TaskDatabase()
        app = Flask(__name__)
        controller = AllTabController.__new__(AllTabController)
        controller.app = app
        controller.overview_service = None
        controller.recording_database = self.recording_database
        controller.sync_database = self.sync_database
        controller.calibration_database = self.calibration_database
        controller.task_database = self.task_database
        controller.register_routes()
        app.testing = True
        self.client = app.test_client()
        self.last_payload: dict[str, Any] | None = None

    def reset(self) -> None:
        """Clear all captured mutations before a timed route dispatch."""

        self.recording_database.reset()
        self.calibration_database.reset()
        self.task_database.reset()
        self.last_payload = None

    def request_body(self) -> dict[str, Any]:
        """Build the explicit canonical five-stage request body."""

        return {
            "selected_set_ids": self.recording_set_ids,
            "enabled_stages": {
                "sync": True,
                "calibration": True,
                "point_detection": True,
                "smoothing": True,
                "triangulation": True,
            },
            "calibration": {
                "linking_mode": "per_set_mapping",
                "per_set_source_map": {
                    str(recording_set_id): recording_set_id
                    for recording_set_id in self.recording_set_ids
                },
                "rows": 7,
                "columns": 5,
                "marker_size_mm": 58,
                "checker_size_mm": 77,
                "dictionary": "DICT_4X4_50",
                "speed_profile": "balanced",
            },
            "point_detection": {
                "model_id": 4,
                "nms_threshold": 0.3,
                "minimum_confidence": 0.6,
            },
            "smoothing": {"method": "butterworth", "params": {"cutoff": 6}},
            "triangulation": {
                "min_confidence": 0.7,
                "weighting_method": "confidence",
                "point_detection_variant_key": "smooth:fixed",
            },
        }

    def dispatch(self) -> BenchmarkObservation:
        """Submit one route request and verify all resulting chains and writes."""

        response = self.client.post("/api/all-tab/run", json=self.request_body())
        payload = response.get_json()
        expected_tasks = len(self.recording_set_ids) * 5
        queued = (payload or {}).get("data", {}).get("queued_by_set", {})
        stage_order = ["sync", "calibration", "point_detection", "smoothing", "triangulation"]
        valid_chains = all(
            [item.get("stage") for item in queued.get(str(recording_set_id), [])]
            == stage_order
            for recording_set_id in self.recording_set_ids
        )
        if (
            response.status_code != 202
            or len(self.task_database.tasks) != expected_tasks
            or len(self.calibration_database.batches) != len(self.recording_set_ids)
            or len(self.recording_database.link_updates) != len(self.recording_set_ids)
            or not valid_chains
        ):
            raise RuntimeError(
                f"pipeline dispatch contract changed: {response.status_code} {payload}"
            )
        self.last_payload = payload
        return BenchmarkObservation(float(expected_tasks), "tasks_dispatched")


def build_pipeline_dispatch_baseline(
    config: PipelineDispatchConfig = PipelineDispatchConfig(),
) -> dict[str, object]:
    """Measure production route composition with deterministic injected adapters."""

    environment = _PipelineDispatchEnvironment(config.recording_set_count)
    environment.reset()
    environment.dispatch()
    if environment.last_payload is None:
        raise RuntimeError("pipeline dispatch reference output was not produced")
    expected_output_identity = _canonical_identity(environment.last_payload)

    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="all_page_five_stage_pipeline_dispatch",
            cache_state="warm",
            operation=environment.dispatch,
            before_each=environment.reset,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
        )
    )
    if (
        environment.last_payload is None
        or _canonical_identity(environment.last_payload) != expected_output_identity
    ):
        raise RuntimeError("pipeline dispatch output changed during repeated measurement")

    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node": _command_version(["node", "--version"]),
        "dependency_versions": {"flask": version("flask")},
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; in-process production Flask route",
        "database_snapshot": "fixed injected adapters; no database access",
        "build_mode": "local Python production controller",
        "compose_configuration": "pc/docker-compose.yml route semantics; isolated process fixture",
        "service_images": {"backend": "local source; no container"},
        "cache_preparation": "adapters reset before every sample",
        "fixture": {
            "session_id": SESSION_ID,
            "recording_set_count": config.recording_set_count,
            "stages_per_set": 5,
            "expected_tasks_per_run": config.recording_set_count * 5,
        },
        "expected_output_identity": expected_output_identity,
        "camera_count": 0,
        "recording_duration_seconds": 0,
        "media_sizes_bytes": [],
        "side_effects": "in-memory adapters only; no workers, database, or filesystem",
        "evidence_scope": "pipeline route validation and task-chain construction lower bound; not worker execution",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_pipeline_dispatch_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "throughput_tasks_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
