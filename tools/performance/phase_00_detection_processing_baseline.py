"""Benchmark deterministic point post-processing and five-second segmentation."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

# Load the production backend modules without requiring a running service.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.PointDetection.PointDetectionSegmenter import PointDetectionSegmenter
from Model.PointDetection.PostProcessingPipeline import (
    PointDetectionPostProcessSettings,
    PointDetectionPostProcessingPipeline,
)


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_detection_processing/phase_00_detection_processing_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 5
CAMERA_COUNT = 3
FRAME_COUNT = 1_800
POINT_COUNT = 33
FPS = 30.0
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class DetectionProcessingConfig:
    """Controls the fixed multi-camera point-processing fixture."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    camera_count: int = CAMERA_COUNT
    frame_count: int = FRAME_COUNT
    point_count: int = POINT_COUNT
    fps: float = FPS


def _labels(point_count: int) -> list[str]:
    """Retain named club endpoints while filling the remaining fixed point schema."""

    if point_count < 2:
        raise ValueError("point_count must be at least two")
    return ["club_head", "club_grip"] + [
        f"point_{index:02d}" for index in range(2, point_count)
    ]


def _build_camera_result(
    *, camera_index: int, frame_count: int, point_count: int, fps: float
) -> dict[str, Any]:
    """Create smooth trajectories with deterministic gaps and isolated outliers."""

    labels = _labels(point_count)
    predictions = []
    for frame_number in range(frame_count):
        keypoints = []
        swing_phase = frame_number / max(1.0, fps)
        for point_index, label in enumerate(labels):
            confidence = 0.92 - (point_index % 4) * 0.02
            if (frame_number + point_index * 7) % 113 in {0, 1}:
                confidence = 0.08
            x = (
                420.0
                + point_index * 8.0
                + camera_index * 3.0
                + math.sin(swing_phase * 4.0 + point_index * 0.1) * 14.0
            )
            y = (
                260.0
                + point_index * 4.0
                + math.cos(swing_phase * 3.0 + point_index * 0.08) * 11.0
            )
            if frame_number == 211 and point_index == 7:
                x += 500.0
                y -= 400.0
            keypoints.append(
                {
                    "label": label,
                    "x": x,
                    "y": y,
                    "confidence": confidence,
                }
            )
        predictions.append({"frame": frame_number, "keypoints": keypoints})
    return {
        "target_fps": fps,
        "source_frame_width": 1_920,
        "source_frame_height": 1_080,
        "debug": {"effective_target_fps": fps, "fixture_camera": camera_index},
        "skeleton_snapshot": {
            "connections": [[labels[index], labels[index + 1]] for index in range(len(labels) - 1)]
        },
        "predictions": predictions,
    }


def _settings() -> PointDetectionPostProcessSettings:
    """Enable every ordered stage using one representative production configuration."""

    return PointDetectionPostProcessSettings.from_dict(
        {
            "confidence_filter": {"enabled": True, "min_confidence": 0.25},
            "motion_prediction": {
                "enabled": True,
                "model_type": "constant_velocity",
                "max_gap_frames": 8,
                "predicted_trust_score": 0.35,
            },
            "outlier_rejection": {
                "enabled": True,
                "max_displacement_px": 180.0,
                "max_velocity_px_per_frame": 90.0,
                "max_acceleration_px_per_frame2": 60.0,
                "enable_club_length_ratio_gate": True,
            },
            "gap_fill": {"method": "pchip", "max_gap_frames": 8},
            "smoothing": {
                "method": "confidence_weighted",
                "params": {"alpha_min": 0.08, "alpha_max": 0.65},
            },
            "rigid_body_correction": {
                "enabled": True,
                "stable_confidence_threshold": 0.75,
                "club_head_label": "club_head",
                "club_grip_label": "club_grip",
                "max_fill_frames_from_last_direction": 18,
            },
        }
    )


def _output_identity(payload: Any) -> str:
    """Hash the complete canonical output for post-run equivalence evidence."""

    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


class _PostProcessingOperation:
    """Runs the full ordered pipeline across every fixed camera result."""

    def __init__(self, raw_results: list[dict[str, Any]], settings) -> None:
        self._raw_results = raw_results
        self._pipeline = PointDetectionPostProcessingPipeline(settings)
        self._stage_plan = settings.stage_plan()
        self.last_outputs: list[dict[str, Any]] | None = None

    def execute(self, *, capture_identity: bool = False) -> tuple[list[dict[str, Any]], str | None]:
        """Consume checkpoint iterators stage-major, matching controller execution."""

        iterators = [self._pipeline.iter_stages(raw_result) for raw_result in self._raw_results]
        final_outputs: list[dict[str, Any] | None] = [None] * len(iterators)
        hasher = hashlib.sha256() if capture_identity else None
        for expected_stage in self._stage_plan:
            for camera_index, iterator in enumerate(iterators):
                checkpoint = next(iterator)
                if checkpoint["stage"] != expected_stage["stage"] or checkpoint["method"] != expected_stage["method"]:
                    raise RuntimeError("post-processing stage order changed")
                final_outputs[camera_index] = checkpoint["result"]
                if hasher is not None:
                    payload = json.dumps(
                        checkpoint,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                    hasher.update(len(payload).to_bytes(8, "big"))
                    hasher.update(payload)
        if any(output is None for output in final_outputs):
            raise RuntimeError("post-processing did not produce a final checkpoint")
        concrete_outputs = [output for output in final_outputs if output is not None]
        self.last_outputs = concrete_outputs
        return concrete_outputs, hasher.hexdigest() if hasher is not None else None

    def __call__(self) -> BenchmarkObservation:
        self.execute()
        return BenchmarkObservation(
            float(
                sum(
                    len(frame.get("keypoints") or [])
                    for item in self._raw_results
                    for frame in item["predictions"]
                )
            ),
            "keypoints",
        )


class _SegmentationOperation:
    """Builds immutable five-second windows for every final camera checkpoint."""

    def __init__(self, processed_results: list[dict[str, Any]]) -> None:
        self._processed_results = processed_results
        self.last_outputs: list[list[dict[str, Any]]] | None = None

    def execute(self) -> list[list[dict[str, Any]]]:
        outputs = [
            PointDetectionSegmenter.build_segments(
                point_detection_result_id=80_000 + camera_index,
                recording_set_id=178,
                recording_id=649 + camera_index,
                variant="postprocessed",
                variant_key=f"postprocessed:phase-00:{camera_index}",
                raw_result=result,
            )
            for camera_index, result in enumerate(self._processed_results)
        ]
        if any(any(segment["segment_duration_seconds"] != 5.0 for segment in camera) for camera in outputs):
            raise RuntimeError("segment duration contract changed")
        self.last_outputs = outputs
        return outputs

    def __call__(self) -> BenchmarkObservation:
        self.execute()
        return BenchmarkObservation(
            float(
                sum(
                    len(frame.get("keypoints") or [])
                    for item in self._processed_results
                    for frame in item["predictions"]
                )
            ),
            "keypoints",
        )


def build_detection_processing_baseline(
    config: DetectionProcessingConfig = DetectionProcessingConfig(),
) -> dict[str, object]:
    """Measure production post-processing and segmentation with full output hashes."""

    raw_results = [
        _build_camera_result(
            camera_index=camera_index,
            frame_count=config.frame_count,
            point_count=config.point_count,
            fps=config.fps,
        )
        for camera_index in range(config.camera_count)
    ]
    settings = _settings()
    postprocess = _PostProcessingOperation(raw_results, settings)

    # Full equivalence hashing is intentionally outside the measured operation.
    processed_results, postprocess_identity = postprocess.execute(capture_identity=True)
    if postprocess_identity is None:
        raise RuntimeError("post-processing reference identity was not produced")
    segmentation = _SegmentationOperation(processed_results)
    reference_segments = segmentation.execute()
    segmentation_identity = _output_identity(reference_segments)

    results = BenchmarkRunner().run_suite(
        (
            BenchmarkScenario(
                name="point_detection_postprocessing_three_cameras",
                cache_state="warm",
                operation=postprocess,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
                approved_long_workflow=True,
            ),
            BenchmarkScenario(
                name="point_detection_segment_generation_three_cameras",
                cache_state="warm",
                operation=segmentation,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
                approved_long_workflow=True,
            ),
        )
    )
    _, verification_identity = postprocess.execute(capture_identity=True)
    if verification_identity != postprocess_identity:
        raise RuntimeError("post-processing output changed during repeated measurement")
    if segmentation.last_outputs is None or _output_identity(segmentation.last_outputs) != segmentation_identity:
        raise RuntimeError("segmentation output changed during repeated measurement")

    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; in-process production modules",
        "database_snapshot": "fixed generated fixture; no database access",
        "build_mode": "local Python production modules",
        "cache_preparation": "complete untimed equivalence pass followed by three warmups",
        "camera_count": config.camera_count,
        "recording_duration_seconds": config.frame_count / config.fps,
        "fixture": {
            "camera_count": config.camera_count,
            "frame_count_per_camera": config.frame_count,
            "point_count": config.point_count,
            "fps": config.fps,
            "postprocess_settings": settings.to_dict(),
        },
        "expected_output_identity": {
            "postprocessing": postprocess_identity,
            "segments": segmentation_identity,
        },
        "stage_order": [item["stage"] for item in settings.stage_plan()],
        "segments_per_camera": [len(items) for items in reference_segments],
        "input_keypoints_per_run": (
            config.camera_count * config.frame_count * config.point_count
        ),
        "nominal_point_stage_evaluations": (
            config.camera_count
            * config.frame_count
            * config.point_count
            * len(settings.stage_plan())
        ),
        "side_effects": "none",
    }
    write_report(config.output_path, results, metadata)
    return {"results": results, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_detection_processing_baseline()
    print(
        json.dumps(
            [
                {
                    "name": result.name,
                    "median_ms": result.median_ms,
                    "p95_ms": result.p95_ms,
                    "throughput_frames_per_second": result.throughput_per_second,
                    "failures": list(result.failures),
                }
                for result in outcome["results"]
            ],
            indent=2,
        )
    )
