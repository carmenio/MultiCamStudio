"""Benchmark database-backed calibration viewer HTML generation."""

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

# Load the production renderer used by the calibration viewer HTTP route.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.Calibration.CalibrationViewerRenderer import CalibrationViewerRenderer


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_calibration_viewer/phase_00_calibration_viewer_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 10
CAMERA_COUNT = 10
CALIBRATION_ID = 90_001
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class CalibrationViewerConfig:
    """Controls the fixed calibration geometry and result destination."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    camera_count: int = CAMERA_COUNT


def _calibration_data(camera_count: int) -> dict[str, Any]:
    """Build deterministic finite camera poses across a representative volume."""

    if camera_count < 1:
        raise ValueError("camera_count must be at least one")
    extrinsics: dict[str, Any] = {}
    labels: dict[str, str] = {}
    for camera_index in range(camera_count):
        angle = camera_index * (2.0 * math.pi / camera_count)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        key = f"camera_{camera_index}"
        extrinsics[key] = {
            "R": [
                [cosine, 0.0, sine],
                [0.0, 1.0, 0.0],
                [-sine, 0.0, cosine],
            ],
            "t": [cosine * 2_500.0, (camera_index % 3) * 180.0, sine * 2_500.0],
        }
        labels[key] = (
            "Front </script> Camera"
            if camera_index == 0
            else f"Benchmark Camera {camera_index + 1}"
        )
    return {"extrinsics": extrinsics, "camera_labels": labels}


class _ViewerRenderOperation:
    """Renders the complete Plotly document and retains the final exact output."""

    def __init__(self, calibration_data: dict[str, Any], camera_count: int) -> None:
        self._calibration_data = calibration_data
        self._camera_count = camera_count
        self.last_html: str | None = None

    def __call__(self) -> BenchmarkObservation:
        html = CalibrationViewerRenderer.render(CALIBRATION_ID, self._calibration_data)
        if (
            "<!doctype html>" not in html
            or "Plotly.newPlot('root'" not in html
            or f"Calibration Viewer {CALIBRATION_ID}" not in html
            or "Front <\\/script> Camera" not in html
        ):
            raise RuntimeError("calibration viewer output contract changed")
        self.last_html = html
        return BenchmarkObservation(float(self._camera_count), "cameras")


def _html_identity(html: str) -> str:
    """Hash the complete self-contained viewer document outside timing."""

    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def build_calibration_viewer_baseline(
    config: CalibrationViewerConfig = CalibrationViewerConfig(),
) -> dict[str, object]:
    """Measure production viewer rendering and persist exact HTML equivalence."""

    calibration_data = _calibration_data(config.camera_count)
    operation = _ViewerRenderOperation(calibration_data, config.camera_count)
    operation()
    if operation.last_html is None:
        raise RuntimeError("calibration viewer reference output was not produced")
    expected_output_identity = _html_identity(operation.last_html)
    output_bytes = len(operation.last_html.encode("utf-8"))

    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="calibration_viewer_html_generation",
            cache_state="warm",
            operation=operation,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
        )
    )
    if operation.last_html is None or _html_identity(operation.last_html) != expected_output_identity:
        raise RuntimeError("calibration viewer output changed during repeated measurement")

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
        "network_route": "none; in-process production renderer",
        "database_snapshot": "fixed generated calibration row; no database access",
        "build_mode": "local Python production module",
        "cache_preparation": "complete untimed reference render followed by three warmups",
        "camera_count": config.camera_count,
        "fixture": {
            "calibration_id": CALIBRATION_ID,
            "camera_count": config.camera_count,
            "geometry_identity": hashlib.sha256(
                json.dumps(
                    calibration_data, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
        },
        "expected_output_identity": expected_output_identity,
        "output_bytes": output_bytes,
        "side_effects": "none; renderer returns HTML without writing an artifact",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_calibration_viewer_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "throughput_cameras_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
