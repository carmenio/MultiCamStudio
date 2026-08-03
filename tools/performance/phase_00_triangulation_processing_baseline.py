"""Benchmark deterministic multi-camera production triangulation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

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

# Load the same backend module used by task execution without a database adapter.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.Triangulation.TriangulationService import (  # noqa: E402
    POINT_CONNECTIONS,
    TriangulationService,
)


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_triangulation_processing/phase_00_triangulation_processing_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 5
CAMERA_COUNT = 3
FRAME_COUNT = 1_800
POINT_COUNT = 15
FPS = 30
MIN_CONFIDENCE = 0.1
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class TriangulationProcessingConfig:
    """Controls the fixed calibrated multi-camera triangulation fixture."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    frame_count: int = FRAME_COUNT
    point_count: int = POINT_COUNT
    fps: int = FPS
    min_confidence: float = MIN_CONFIDENCE


def _ordered_labels(point_count: int) -> list[str]:
    """Select connected production labels in deterministic first-use order."""

    labels: list[str] = []
    for connection in POINT_CONNECTIONS:
        for label in connection:
            if label not in labels:
                labels.append(label)
    if point_count < 1 or point_count > len(labels):
        raise ValueError(f"point_count must be between 1 and {len(labels)}")
    return labels[:point_count]


def _camera_payload(translation: list[float]) -> dict[str, Any]:
    """Return one calibrated pinhole camera using world-to-camera extrinsics."""

    return {
        "K": [[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]],
        "dist": [],
        "R": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "t": translation,
    }


def _fixture(config: TriangulationProcessingConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project deterministic moving 3D points into three calibrated camera views."""

    labels = _ordered_labels(config.point_count)
    translations = ([0.0, 0.0, 0.0], [-1000.0, 0.0, 0.0], [0.0, -800.0, 0.0])
    recording_ids = (101, 102, 103)
    rows = []
    for camera_index, (recording_id, translation) in enumerate(
        zip(recording_ids, translations)
    ):
        predictions = []
        for frame_number in range(config.frame_count):
            phase = frame_number / max(1.0, float(config.fps))
            keypoints = []
            for label_index, label in enumerate(labels):
                world_x = (label_index - 7) * 42.0 + math.sin(phase * 2.1 + label_index * 0.1) * 95.0
                world_y = (label_index % 5 - 2) * 55.0 + math.cos(phase * 1.7 + label_index * 0.07) * 75.0
                world_z = 4_500.0 + label_index * 18.0 + math.sin(phase * 0.9) * 60.0
                camera_x = world_x + translation[0]
                camera_y = world_y + translation[1]
                camera_z = world_z + translation[2]
                keypoints.append(
                    {
                        "label": label,
                        "x": 1000.0 * camera_x / camera_z + 640.0,
                        "y": 1000.0 * camera_y / camera_z + 360.0,
                        "confidence": 0.86 + ((frame_number + label_index + camera_index) % 7) * 0.01,
                    }
                )
            predictions.append(
                {
                    "frame": frame_number,
                    "width": 1_280,
                    "height": 720,
                    "keypoints": keypoints,
                }
            )
        rows.append(
            {
                "recording_id": recording_id,
                "raw_result": {"target_fps": config.fps, "predictions": predictions},
            }
        )
    calibration_context = {
        "cameras": {
            f"camera_{index}": _camera_payload(list(translation))
            for index, translation in enumerate(translations)
        },
        "recording_camera_map": {
            recording_id: f"camera_{index}"
            for index, recording_id in enumerate(recording_ids)
        },
    }
    return rows, calibration_context


def _canonical_identity(payload: Any) -> str:
    """Hash a complete deterministic input or result outside timed execution."""

    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


class _TriangulationOperation:
    """Runs the production pure triangulation boundary and checks core invariants."""

    def __init__(self, config, point_detection_rows, calibration_context) -> None:
        self._config = config
        self._point_detection_rows = point_detection_rows
        self._calibration_context = calibration_context
        self.last_result: dict[str, Any] | None = None

    def __call__(self) -> BenchmarkObservation:
        result = TriangulationService.build_triangulation_result(
            point_detection_rows=self._point_detection_rows,
            weighting_method="confidence_weighted",
            fps=self._config.fps,
            total_frames=self._config.frame_count,
            calibration_context=self._calibration_context,
            min_confidence=self._config.min_confidence,
        )
        diagnostics = result.get("diagnostics") or {}
        expected_points = self._config.frame_count * self._config.point_count
        invariants = (
            result.get("triangulation_method") == TriangulationService.FIXED_TRIANGULATION_METHOD,
            result.get("units") == "m",
            result.get("fps") == self._config.fps,
            result.get("total_frames") == self._config.frame_count,
            len(result.get("frames") or []) == self._config.frame_count,
            diagnostics.get("points_accepted") == expected_points,
            diagnostics.get("observations_total") == expected_points * CAMERA_COUNT,
            (result.get("coordinate_transform") or {}).get("applied") is True,
        )
        if not all(invariants):
            raise RuntimeError("triangulation fixture invariants changed")
        self.last_result = result
        return BenchmarkObservation(float(expected_points), "accepted_3d_points")


def build_triangulation_processing_baseline(
    config: TriangulationProcessingConfig = TriangulationProcessingConfig(),
) -> dict[str, object]:
    """Measure fixed production triangulation and persist complete equivalence evidence."""

    point_detection_rows, calibration_context = _fixture(config)
    fixture_identity = _canonical_identity(
        {
            "point_detection_rows": point_detection_rows,
            "calibration_context": calibration_context,
        }
    )
    operation = _TriangulationOperation(
        config, point_detection_rows, calibration_context
    )

    # The reference result and full hash are outside benchmark timing.
    operation()
    if operation.last_result is None:
        raise RuntimeError("triangulation reference result was not produced")
    expected_output_identity = _canonical_identity(operation.last_result)

    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="triangulation_three_camera_fixed_fixture",
            cache_state="warm",
            operation=operation,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
            approved_long_workflow=True,
        )
    )
    if operation.last_result is None or _canonical_identity(operation.last_result) != expected_output_identity:
        raise RuntimeError("triangulation output changed during repeated measurement")

    diagnostics = operation.last_result["diagnostics"]
    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node": _command_version(["node", "--version"]),
        "dependency_versions": {"numpy": np.__version__},
        "thread_environment": {
            name: os.getenv(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; in-process production service",
        "database_snapshot": "fixed generated fixture; no database access",
        "build_mode": "local Python production module",
        "compose_configuration": "not used; in-process local source benchmark",
        "service_images": {"backend": "local source; no container"},
        "cache_preparation": "complete untimed reference execution followed by three warmups",
        "camera_count": CAMERA_COUNT,
        "recording_duration_seconds": config.frame_count / config.fps,
        "media_sizes_bytes": [],
        "fixture": {
            "camera_count": CAMERA_COUNT,
            "frame_count": config.frame_count,
            "point_count": config.point_count,
            "fps": config.fps,
            "min_confidence": config.min_confidence,
            "observations": config.frame_count * config.point_count * CAMERA_COUNT,
            "calibration_translation_mm": [[0, 0, 0], [-1000, 0, 0], [0, -800, 0]],
        },
        "fixture_identity": fixture_identity,
        "expected_output_identity": expected_output_identity,
        "accepted_3d_points": diagnostics["points_accepted"],
        "observations_total": diagnostics["observations_total"],
        "coordinate_transform": operation.last_result["coordinate_transform"],
        "per_camera_reprojection": diagnostics["per_camera_reprojection"],
        "side_effects": "none",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_triangulation_processing_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "throughput_accepted_points_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
