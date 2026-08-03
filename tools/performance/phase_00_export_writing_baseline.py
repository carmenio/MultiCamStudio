"""Benchmark deterministic dataset writing and atomic export finalization."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from tools.performance import (
    BenchmarkObservation,
    BenchmarkRunner,
    BenchmarkScenario,
    write_report,
)
from tools.performance.phase_00_live_baseline import (
    _commit_identity,
    _repository_revision,
)

# The production export modules are loaded exactly as they are inside the backend.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.Export.DatasetExportCoordinator import DatasetExportCoordinator


# SDK-style fixed fixture and report configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_export_writing/phase_00_export_writing_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 5
FRAME_COUNT = 1_800
POINT_COUNT = 33
FPS = 30.0
SESSION_ID = 9_001
RECORDING_SET_ID = 9_002
TRIANGULATION_RUN_ID = 9_003
EXPORT_ID = "phase-00-fixed-export"
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class ExportWritingConfig:
    """Controls the fixed production-code export fixture and result destination."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    frame_count: int = FRAME_COUNT
    point_count: int = POINT_COUNT
    fps: float = FPS


class _RecordingFixtureDatabase:
    """Provides the minimal recording rows required by the production coordinator."""

    def __init__(self, detection_results: list[dict[str, Any]]) -> None:
        self._detection_results = detection_results

    def get_recording_sets_for_session(self, session_id, recording_set_ids=None):
        return SimpleNamespace(data=[{"id": RECORDING_SET_ID, "session_id": session_id}])

    def get_recordings_by_set(self, recording_set_id):
        return SimpleNamespace(
            data=[
                {
                    "id": row["recording_id"],
                    "name": f"Fixed benchmark camera {index + 1}",
                    "size_bytes": 0,
                }
                for index, row in enumerate(self._detection_results)
            ]
        )

    def list_point_detection_result_metadata_for_recordings(self, recording_ids):
        return [
            {
                "id": row["id"],
                "recording_id": row["recording_id"],
                "variant": "raw",
                "variant_key": "raw:phase-00-fixed",
                "run_id": "phase-00-fixed",
                "created_at": "2026-08-03T00:00:00Z",
                "updated_at": "2026-08-03T00:00:00Z",
            }
            for row in self._detection_results
        ]

    def list_point_detection_results_for_set_variant(self, recording_set_id, variant_key):
        return self._detection_results


class _SyncFixtureDatabase:
    """Supplies the empty sync fingerprint used by point-only preflight."""

    def get_synced_recordings_by_ids(self, recording_ids):
        return {}


class _TriangulationFixtureDatabase:
    """Returns one immutable completed 3D result for every benchmark execution."""

    def __init__(self, result_json: dict[str, Any]) -> None:
        self._run = {
            "id": TRIANGULATION_RUN_ID,
            "recording_set_id": RECORDING_SET_ID,
            "status": "done",
            "created_at": "2026-08-03T00:00:00Z",
            "updated_at": "2026-08-03T00:00:00Z",
            "result_json": result_json,
        }

    def list_runs_lite_for_set(self, recording_set_id):
        return [
            {
                "id": TRIANGULATION_RUN_ID,
                "status": "done",
                "created_at": "2026-08-03T00:00:00Z",
            }
        ]

    def get_run_by_id(self, run_id):
        return self._run

    def list_training_segments(self, recording_set_id):
        return []


def _build_result(frame_count: int, point_count: int, fps: float) -> dict[str, Any]:
    """Build repeatable golf-scale coordinates without random fixture variation."""

    labels = [f"point_{index:02d}" for index in range(point_count)]
    frames = []
    for frame_number in range(frame_count):
        frames.append(
            {
                "frame": frame_number,
                "points": [
                    {
                        "label": label,
                        "x": frame_number * 0.001 + point_index * 0.01,
                        "y": point_index * 0.02,
                        "z": frame_number * 0.0005 - point_index * 0.005,
                        "confidence": 0.95 - (point_index % 5) * 0.01,
                    }
                    for point_index, label in enumerate(labels)
                ],
            }
        )
    return {
        "fps": fps,
        "units": "m",
        "input_meta": {"point_detection_variant_key": "raw:phase-00-fixed"},
        "connections": [
            [labels[index], labels[index + 1]] for index in range(len(labels) - 1)
        ],
        "frames": frames,
    }


def _build_detection_result(
    frame_count: int, point_count: int, camera_index: int, fps: float
) -> dict[str, Any]:
    """Build one deterministic normalized 2D camera result with source dimensions."""

    labels = [f"point_{index:02d}" for index in range(point_count)]
    return {
        "target_fps": fps,
        "source_frame_width": 1_920,
        "source_frame_height": 1_080,
        "predictions": [
            {
                "frame": frame_number,
                "keypoints": [
                    {
                        "label": label,
                        "x": 0.1 + point_index * 0.01 + camera_index * 0.001,
                        "y": 0.2 + point_index * 0.005,
                        "confidence": 0.95 - (point_index % 5) * 0.01,
                    }
                    for point_index, label in enumerate(labels)
                ],
            }
            for frame_number in range(frame_count)
        ],
    }


def _specification(point_count: int) -> dict[str, Any]:
    """Return the reviewed specification shared by every warmup and measurement."""

    return {
        "recipe": "two_d_3d",
        "sets": [
            {
                "session_id": SESSION_ID,
                "recording_set_id": RECORDING_SET_ID,
                "point_detection_variant_key": "raw:phase-00-fixed",
                "triangulation_run_id": TRIANGULATION_RUN_ID,
            }
        ],
        "formats": ["npy", "csv", "jsonl"],
        "range": {"base": "full", "quality_enabled": False},
        "point_schema": {
            "labels": [f"point_{index:02d}" for index in range(point_count)],
            "target_point_count": point_count,
            "skeleton_connections": [],
        },
        "export_name": "Phase 0 writer benchmark",
        "destination_subfolder": "",
    }


def _semantic_output_identity(result: dict[str, Any]) -> str:
    """Hash production artifact checksums and stable completion fields only."""

    stable_result = {
        "export_status": result["export_status"],
        "exported_sets": result["exported_sets"],
        "warnings": result["warnings"],
    }
    return hashlib.sha256(
        json.dumps(stable_result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class _AtomicExportOperation:
    """Prepares, executes, and verifies one production coordinator export."""

    def __init__(self, coordinator, specification, export_base_directory: Path) -> None:
        self._coordinator = coordinator
        self._specification = specification
        self._export_base_directory = export_base_directory.resolve()
        frozen_preflight = coordinator.preflight(specification)
        self._preflight_hash = frozen_preflight["preflight_hash"]
        coordinator.preflight = lambda _specification: frozen_preflight
        self.output_identity: str | None = None
        self.output_bytes: int | None = None
        self.last_result: dict[str, Any] | None = None

    def prepare(self) -> None:
        """Remove only prior outputs inside the dedicated temporary benchmark root."""

        for path in self._export_base_directory.iterdir():
            resolved = path.resolve()
            if self._export_base_directory not in resolved.parents:
                raise RuntimeError("refusing to clean an export outside the benchmark root")
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()

    def __call__(self) -> BenchmarkObservation:
        result = self._coordinator.run(
            raw_specification=self._specification,
            expected_preflight_hash=self._preflight_hash,
            export_id=EXPORT_ID,
            progress_callback=lambda **_values: None,
            cancel_requested=lambda: False,
        )
        identity = _semantic_output_identity(result)
        output_bytes = sum(
            int(artifact["size_bytes"])
            for exported_set in result["exported_sets"]
            for artifact in exported_set["artifacts"]
        )
        if self.output_identity is None:
            self.output_identity = identity
            self.output_bytes = output_bytes
        elif identity != self.output_identity or output_bytes != self.output_bytes:
            raise RuntimeError("export output changed between repeated measurements")
        self.last_result = result
        return BenchmarkObservation(float(output_bytes), "bytes")

    def verify_last_output(self) -> None:
        """Validate manifest integrity and atomic layout after timed work is complete."""

        if self.last_result is None:
            raise RuntimeError("export benchmark produced no output to verify")
        export_root = Path(self.last_result["export_root_path"])
        manifest_path = export_root / "manifest.json"
        expected_manifest_hash = self.last_result["manifest_sha256"]
        actual_manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if actual_manifest_hash != expected_manifest_hash:
            raise RuntimeError("final manifest checksum does not match manifest.json")
        artifact_count = sum(
            len(exported_set["artifacts"])
            for exported_set in self.last_result["exported_sets"]
        )
        if artifact_count != 14:
            raise RuntimeError(f"expected 14 export artifacts, found {artifact_count}")
        if any(".tmp-" in path.name for path in self._export_base_directory.iterdir()):
            raise RuntimeError("atomic export left a temporary directory behind")


def build_export_writing_baseline(
    config: ExportWritingConfig = ExportWritingConfig(),
) -> dict[str, object]:
    """Measure real artifact writing and atomic finalization with fixed adapters."""

    result_json = _build_result(config.frame_count, config.point_count, config.fps)
    detection_results = [
        {
            "id": 92_000 + camera_index,
            "recording_id": 91_001 + camera_index,
            "raw_result": _build_detection_result(
                config.frame_count, config.point_count, camera_index, config.fps
            ),
        }
        for camera_index in range(3)
    ]
    specification = _specification(config.point_count)
    with tempfile.TemporaryDirectory(prefix="mcs-export-writing-benchmark-") as temporary:
        export_base_directory = Path(temporary).resolve()
        coordinator = DatasetExportCoordinator(
            recording_database=_RecordingFixtureDatabase(detection_results),
            sync_database=_SyncFixtureDatabase(),
            triangulation_database=_TriangulationFixtureDatabase(result_json),
            export_base_directory=export_base_directory,
            resolve_media_path=lambda _path: None,
        )
        operation = _AtomicExportOperation(
            coordinator, specification, export_base_directory
        )
        result = BenchmarkRunner().run(
            BenchmarkScenario(
                name="dataset_export_write_and_atomic_finalize",
                cache_state="warm",
                operation=operation,
                before_each=operation.prepare,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
                approved_long_workflow=True,
            )
        )
        operation.verify_last_output()
        metadata = {
            "commit": _commit_identity(),
            "source_revisions": {
                "pc": _repository_revision("pc"),
                "laptop": _repository_revision("laptop"),
            },
            "platform": platform.platform(),
            "python": platform.python_version(),
            "dependency_versions": {"numpy": np.__version__},
            "hardware": HARDWARE,
            "power_mode": POWER_MODE,
            "network_route": "none; in-process production coordinator",
            "database_snapshot": "fixed in-memory adapters; no live database reads or writes",
            "build_mode": "local Python production modules",
            "cache_preparation": "prior output removed outside timing; three warm-up exports",
            "fixture": {
                "recipe": "two_d_3d",
                "camera_count": 3,
                "frame_count": config.frame_count,
                "point_count": config.point_count,
                "fps": config.fps,
                "duration_seconds": config.frame_count / config.fps,
                "formats": ["npy", "csv", "jsonl"],
            },
            "expected_output_identity": operation.output_identity,
            "output_bytes_per_export": operation.output_bytes,
            "artifact_count": 14,
            "side_effects": "temporary local files only; removed when the run completes",
        }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_export_writing_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "throughput_bytes_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
