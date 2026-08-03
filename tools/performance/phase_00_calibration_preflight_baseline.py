"""Benchmark production OpenCV calibration video preflight on fixed media."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import cv2

from tools.performance import BenchmarkObservation, BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import _commit_identity, _repository_revision

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.Calibration.CalibrationService import CalibrationService  # noqa: E402


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_calibration_preflight/phase_00_calibration_preflight_baseline.json"
)
SOURCE_DIRECTORY = Path(r"E:\Shared_Folder\Golf_AI\MultiCamStudio\SyncedVideos\set-201")
SOURCE_FILES = (
    "synced_anna-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20.mp4",
    "synced_chris-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20.mp4",
    "synced_dom-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20.mp4",
    "synced_tenchris-1-2-3-4-5-6-7-8-9-10-11-12.mp4",
)
SOURCE_SIZES = (54_977_672, 41_709_022, 108_268_584, 214_038_077)
SOURCE_IDENTITIES = (
    "60f3749cf04c184a004a6657d1e290b4932c8b9bcb0b8e1ced92c0c5ecc4520a",
    "c7214f135ef25bb73004c9ffd646353185eb84acf0daf8554778d6689b3e6de7",
    "c22aadaf069e28d32ad38b81ac09f4bc4435fe60c7e1fd5423c9229c58c76140",
    "6735baeb0f6f17ca061e610e83fee5353ae931bb1c2b4002b917503b56b8d0b9",
)
EXPECTED_OUTPUT_IDENTITY = "7790c0e597580ef184976de348736b8605da2b81ad30be2632eb8709807d3283"
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


class VideoProbe(Protocol):
    """Describes the existing private preflight seam being frozen in Phase 0."""

    def _probe_video_metadata(self, path: str) -> dict[str, Any]: ...

    def _probe_video_readability(self, path: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CalibrationPreflightConfig:
    """Controls the immutable four-camera preflight fixture and report path."""

    output_path: Path = OUTPUT_PATH
    source_directory: Path = SOURCE_DIRECTORY
    source_files: tuple[str, ...] = SOURCE_FILES
    source_sizes: tuple[int, ...] = SOURCE_SIZES
    source_identities: tuple[str, ...] = SOURCE_IDENTITIES
    expected_output_identity: str = EXPECTED_OUTPUT_IDENTITY
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS


def _file_identity(path: Path) -> str:
    """Hash a full source file outside timed preflight work."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_identity(payload: Any) -> str:
    """Hash the complete deterministic preflight output."""

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _verify_sources(config: CalibrationPreflightConfig) -> tuple[Path, ...]:
    """Reject missing or drifted production fixtures before timing begins."""

    lengths = {
        len(config.source_files),
        len(config.source_sizes),
        len(config.source_identities),
    }
    if len(lengths) != 1 or not config.source_files:
        raise ValueError("source files, sizes, and identities must be non-empty and aligned")
    if any(len(identity) != 64 for identity in config.source_identities):
        raise ValueError("source identities must be 64-character SHA256 values")
    paths = tuple(config.source_directory / name for name in config.source_files)
    for index, path in enumerate(paths):
        if not path.is_file():
            raise FileNotFoundError(f"calibration preflight source not found: {path}")
        actual_size = path.stat().st_size
        if actual_size != config.source_sizes[index]:
            raise RuntimeError(
                f"calibration preflight source size changed: expected "
                f"{config.source_sizes[index]}, got {actual_size}: {path}"
            )
        actual_identity = _file_identity(path)
        if actual_identity != config.source_identities[index]:
            raise RuntimeError(
                f"calibration preflight source SHA256 changed: expected "
                f"{config.source_identities[index]}, got {actual_identity}: {path}"
            )
    return paths


class _PreflightOperation:
    """Calls the unchanged OpenCV metadata and first-frame probes for every camera."""

    def __init__(
        self,
        paths: tuple[Path, ...],
        service: VideoProbe,
        expected_output_identity: str,
    ) -> None:
        self._paths = paths
        self._service = service
        self._expected_output_identity = expected_output_identity
        self.last_payload: list[dict[str, Any]] | None = None

    def __call__(self) -> BenchmarkObservation:
        """Probe every source and enforce exact semantic equivalence."""

        payload = [
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "metadata": self._service._probe_video_metadata(str(path)),
                "readability": self._service._probe_video_readability(str(path)),
            }
            for path in self._paths
        ]
        actual_identity = _canonical_identity(payload)
        if actual_identity != self._expected_output_identity:
            raise RuntimeError(
                "calibration preflight output changed: expected "
                f"{self._expected_output_identity}, got {actual_identity}"
            )
        if not all(item["readability"] == {"usable": True} for item in payload):
            raise RuntimeError("calibration preflight fixture is no longer fully readable")
        self.last_payload = payload
        return BenchmarkObservation(float(len(payload)), "videos_preflighted")


def build_calibration_preflight_baseline(
    config: CalibrationPreflightConfig = CalibrationPreflightConfig(),
    service_factory: Callable[[], VideoProbe] = lambda: object.__new__(CalibrationService),
) -> dict[str, object]:
    """Measure warm-cache production preflight without constructing database adapters."""

    paths = _verify_sources(config)
    operation = _PreflightOperation(paths, service_factory(), config.expected_output_identity)
    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="calibration_four_camera_video_preflight",
            cache_state="warm",
            operation=operation,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
        )
    )
    if result.failures or result.warmup_failures or operation.last_payload is None:
        failures = [*result.warmup_failures, *result.failures]
        raise RuntimeError("calibration preflight benchmark failed: " + " | ".join(failures))

    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dependency_versions": {
            "opencv": cv2.__version__,
            "numpy": importlib.metadata.version("numpy"),
        },
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; local fixed host media and in-process production probes",
        "database_snapshot": "none; fixed host media fixture",
        "build_mode": "local Python production module",
        "cache_preparation": "source identities read once, followed by three warmups; OS cache not cleared",
        "camera_count": len(paths),
        "recording_duration_seconds": operation.last_payload[0]["metadata"]["duration_seconds"],
        "media_sizes_bytes": list(config.source_sizes),
        "fixture": {
            "recording_set_id": 201,
            "source_directory": str(config.source_directory),
            "source_files": list(config.source_files),
            "source_identities": list(config.source_identities),
            "expected_frame_count": 3_437,
            "expected_fps": 60.0,
        },
        "expected_output_identity": config.expected_output_identity,
        "side_effects": "none",
        "evidence_scope": "metadata plus first decoded frame; not full calibration processing",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_calibration_preflight_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "throughput_videos_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
