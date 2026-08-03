"""Benchmark deterministic production FreeMoCap calibration processing."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import cv2
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

# Load the exact production adapter used by calibration task execution.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Model.Calibration.FreeMoCapCalibrationRunner import (  # noqa: E402
    FreeMoCapArtifacts,
    FreeMoCapCalibrationRunner,
    FreeMoCapConfig,
)


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_calibration_processing/phase_00_calibration_processing_baseline.json"
)
SOURCE_DIRECTORY = Path(r"E:\Shared_Folder\Golf_AI\MultiCamStudio\SyncedVideos\set-201")
SOURCE_FILES = (
    "synced_anna-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20.mp4",
    "synced_chris-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-16-17-18-19-20.mp4",
)
SOURCE_IDENTITIES = (
    "60f3749cf04c184a004a6657d1e290b4932c8b9bcb0b8e1ced92c0c5ecc4520a",
    "c7214f135ef25bb73004c9ffd646353185eb84acf0daf8554778d6689b3e6de7",
)
SOURCE_SIZES = (54_977_672, 41_709_022)
CLIP_IDENTITIES = (
    "ecc573054bcf88b64f6bbc007ba95cba53a76d10ac0876878fa54b5b6c1b8859",
    "4924b4cd1e728da03914200ccdba72e69ea2ccce72b8825e0902546e9a7f960d",
)
CLIP_SIZES = (4_086_441, 5_781_290)
EXPECTED_TOML_IDENTITY = (
    "3dad317eb5f84ec023039fd66d3f9f4c8dccad5dddf1c1200d2823ed544a24fc"
)
EXPECTED_RESULT_IDENTITY = (
    "ea1e323dadcb542be992c041de43f8806c1a7a5d0585596d39325cb10000035e"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 5
START_FRAME = 500
CLIP_FRAME_COUNT = 120
CAMERA_NAMES = ("anna", "chris")
RANDOM_SEED = 20_260_803
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


class CalibrationRunner(Protocol):
    """Describes the production runner boundary used by the benchmark."""

    def run(self) -> tuple[dict[str, Any], FreeMoCapArtifacts]: ...


@dataclass(frozen=True)
class CalibrationProcessingConfig:
    """Controls the fixed real-media calibration fixture and result destination."""

    output_path: Path = OUTPUT_PATH
    source_directory: Path = SOURCE_DIRECTORY
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    start_frame: int = START_FRAME
    clip_frame_count: int = CLIP_FRAME_COUNT
    random_seed: int = RANDOM_SEED
    source_files: tuple[str, str] = SOURCE_FILES
    source_identities: tuple[str, str] = SOURCE_IDENTITIES
    source_sizes: tuple[int, int] = SOURCE_SIZES
    clip_identities: tuple[str, str] = CLIP_IDENTITIES
    clip_sizes: tuple[int, int] = CLIP_SIZES
    expected_toml_identity: str = EXPECTED_TOML_IDENTITY
    expected_result_identity: str = EXPECTED_RESULT_IDENTITY


@dataclass(frozen=True)
class PreparedCalibrationFixture:
    """Identifies verified clips prepared outside benchmark timing."""

    temporary_root: Path
    video_inputs: tuple[Path, Path]
    clip_identities: tuple[str, str]
    clip_sizes: tuple[int, int]


def _file_identity(path: Path) -> str:
    """Hash a complete media or calibration artifact in bounded chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Any) -> Any:
    """Normalize non-finite solver values before stable JSON serialization."""

    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _result_identity(result: dict[str, Any]) -> str:
    """Hash the complete canonical calibration result without float rounding."""

    payload = json.dumps(
        _canonical(result),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _verify_file(
    path: Path, expected_size: int, expected_identity: str, label: str
) -> None:
    """Fail clearly when a production source or generated clip has drifted."""

    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(
            f"{label} size changed: expected {expected_size}, got {actual_size}: {path}"
        )
    actual_identity = _file_identity(path)
    if actual_identity != expected_identity:
        raise RuntimeError(
            f"{label} SHA256 changed: expected {expected_identity}, "
            f"got {actual_identity}: {path}"
        )


def _prepare_video_clips(
    config: CalibrationProcessingConfig,
    temporary_root: Path,
) -> PreparedCalibrationFixture:
    """Decode fixed source frames into deterministic clips outside timed execution."""

    clips: list[Path] = []
    for camera_index, source_name in enumerate(config.source_files):
        source = config.source_directory / source_name
        _verify_file(
            source,
            config.source_sizes[camera_index],
            config.source_identities[camera_index],
            f"camera {camera_index} source",
        )

        capture = cv2.VideoCapture(str(source))
        writer: cv2.VideoWriter | None = None
        clip = temporary_root / f"camera_{camera_index}.mp4"
        try:
            if not capture.isOpened():
                raise RuntimeError(
                    f"OpenCV could not open calibration source: {source}"
                )
            capture.set(cv2.CAP_PROP_POS_FRAMES, config.start_frame)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if width < 1 or height < 1 or fps <= 0:
                raise RuntimeError(
                    f"invalid calibration source geometry {width}x{height} at {fps} fps: {source}"
                )
            writer = cv2.VideoWriter(
                str(clip),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                raise RuntimeError(f"OpenCV could not create calibration clip: {clip}")
            written_frames = 0
            while written_frames < config.clip_frame_count:
                ok, frame = capture.read()
                if not ok:
                    break
                writer.write(frame)
                written_frames += 1
            if written_frames != config.clip_frame_count:
                raise RuntimeError(
                    f"camera {camera_index} clip ended after {written_frames} frames; "
                    f"expected {config.clip_frame_count}"
                )
        finally:
            if writer is not None:
                writer.release()
            capture.release()

        _verify_file(
            clip,
            config.clip_sizes[camera_index],
            config.clip_identities[camera_index],
            f"camera {camera_index} prepared clip",
        )
        clips.append(clip)

    return PreparedCalibrationFixture(
        temporary_root=temporary_root,
        video_inputs=(clips[0], clips[1]),
        clip_identities=config.clip_identities,
        clip_sizes=config.clip_sizes,
    )


def _clear_verified_output_dir(output_dir: Path, temporary_root: Path) -> None:
    """Clear only the benchmark-owned output child beneath its temporary root."""

    resolved_root = temporary_root.resolve()
    resolved_output = output_dir.resolve()
    if resolved_output == resolved_root or resolved_root not in resolved_output.parents:
        raise ValueError(
            f"refusing to clear output outside benchmark temporary root: {resolved_output}"
        )
    if resolved_output.exists():
        shutil.rmtree(resolved_output)
    resolved_output.mkdir(parents=True, exist_ok=True)


class _CalibrationOperation:
    """Runs the real solver and retains its latest result and artifacts for verification."""

    def __init__(
        self,
        config: CalibrationProcessingConfig,
        fixture: PreparedCalibrationFixture,
        output_dir: Path,
        runner_factory: Callable[[FreeMoCapConfig], CalibrationRunner],
    ) -> None:
        self._config = config
        self._fixture = fixture
        self._output_dir = output_dir
        self._runner_factory = runner_factory
        self.last_result: dict[str, Any] | None = None
        self.last_artifacts: FreeMoCapArtifacts | None = None

    def prepare(self) -> None:
        """Reset output and global solver randomness immediately before each run."""

        _clear_verified_output_dir(self._output_dir, self._fixture.temporary_root)
        np.random.seed(self._config.random_seed)

    def __call__(self) -> BenchmarkObservation:
        runner_config = FreeMoCapConfig(
            video_inputs=list(self._fixture.video_inputs),
            camera_names=list(CAMERA_NAMES),
            output_dir=self._output_dir,
            charuco_squares_x=7,
            charuco_squares_y=5,
            charuco_square_size_mm=77.0,
            charuco_marker_size_mm=58.0,
            charuco_dictionary="DICT_4X4_50",
            debug=False,
            debug_sample_rate=20,
            pin_camera_0_to_origin=True,
            use_charuco_as_groundplane=False,
        )
        result, artifacts = self._runner_factory(runner_config).run()
        if set(result.get("intrinsics") or {}) != set(CAMERA_NAMES):
            raise RuntimeError("calibration intrinsics camera ownership changed")
        if set(result.get("extrinsics") or {}) != set(CAMERA_NAMES):
            raise RuntimeError("calibration extrinsics camera ownership changed")
        if not artifacts.calibration_toml_path.is_file():
            raise RuntimeError(
                "calibration runner did not write camera_calibration.toml"
            )
        if not artifacts.calibration_yaml_path.is_file():
            raise RuntimeError(
                "calibration runner did not write camera_calibration.yaml"
            )
        self.last_result = result
        self.last_artifacts = artifacts
        return BenchmarkObservation(
            float(len(CAMERA_NAMES) * self._config.clip_frame_count),
            "camera_frames",
        )


def _benchmark_prepared_fixture(
    config: CalibrationProcessingConfig,
    fixture: PreparedCalibrationFixture,
    runner_factory: Callable[[FreeMoCapConfig], CalibrationRunner],
) -> dict[str, object]:
    """Measure an already verified fixture, allowing fast fake-runner tests."""

    run_output_dir = fixture.temporary_root / "calibration_output"
    operation = _CalibrationOperation(config, fixture, run_output_dir, runner_factory)
    result = BenchmarkRunner().run(
        BenchmarkScenario(
            name="calibration_freemocap_two_camera_fixed_fixture",
            cache_state="warm",
            operation=operation,
            before_each=operation.prepare,
            warmup_runs=config.warmup_runs,
            measured_runs=config.measured_runs,
            approved_long_workflow=True,
        )
    )

    if result.failures or result.warmup_failures:
        details = [*result.warmup_failures, *result.failures]
        raise RuntimeError(
            "calibration benchmark execution failed: " + " | ".join(details)
        )
    if operation.last_result is None or operation.last_artifacts is None:
        raise RuntimeError("calibration benchmark produced no successful result")

    actual_toml_identity = _file_identity(
        operation.last_artifacts.calibration_toml_path
    )
    actual_result_identity = _result_identity(operation.last_result)
    if actual_toml_identity != config.expected_toml_identity:
        raise RuntimeError(
            "seeded calibration TOML changed: "
            f"expected {config.expected_toml_identity}, got {actual_toml_identity}"
        )
    if actual_result_identity != config.expected_result_identity:
        raise RuntimeError(
            "seeded canonical calibration result changed: "
            f"expected {config.expected_result_identity}, got {actual_result_identity}"
        )

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
            "numpy": np.__version__,
            "aniposelib": importlib.metadata.version("aniposelib"),
        },
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; local fixed host media and in-process production runner",
        "database_snapshot": "none; fixed host media fixture",
        "build_mode": "local Python production module",
        "cache_preparation": (
            "clips decoded once outside timing; output cleared and NumPy seed reset "
            "before every run; three solver warmups"
        ),
        "camera_count": len(CAMERA_NAMES),
        "recording_duration_seconds": config.clip_frame_count / 60.0,
        "fixture": {
            "source_directory": str(config.source_directory),
            "source_files": list(config.source_files),
            "source_sizes": list(config.source_sizes),
            "source_identities": list(config.source_identities),
            "clip_names": [path.name for path in fixture.video_inputs],
            "clip_sizes": list(fixture.clip_sizes),
            "clip_identities": list(fixture.clip_identities),
            "source_frame_range_inclusive": [
                config.start_frame,
                config.start_frame + config.clip_frame_count - 1,
            ],
            "clip_frame_count": config.clip_frame_count,
            "camera_names": list(CAMERA_NAMES),
            "board": {
                "columns": 7,
                "rows": 5,
                "checker_size_mm": 77.0,
                "marker_size_mm": 58.0,
                "dictionary": "DICT_4X4_50",
            },
            "pin_camera_0_to_origin": True,
            "use_charuco_as_groundplane": False,
            "random_seed": config.random_seed,
        },
        "expected_toml_identity": actual_toml_identity,
        "expected_result_identity": actual_result_identity,
        "output_artifacts": ["camera_calibration.toml", "camera_calibration.yaml"],
        "side_effects": "temporary clips and solver output removed after report creation",
    }
    write_report(config.output_path, (result,), metadata)
    return {"result": result, "metadata": metadata}


def build_calibration_processing_baseline(
    config: CalibrationProcessingConfig = CalibrationProcessingConfig(),
    runner_factory: Callable[
        [FreeMoCapConfig], CalibrationRunner
    ] = FreeMoCapCalibrationRunner,
) -> dict[str, object]:
    """Prepare fixed clips, measure production calibration, and persist evidence."""

    with tempfile.TemporaryDirectory(
        prefix="multicam_calibration_benchmark_"
    ) as directory:
        fixture = _prepare_video_clips(config, Path(directory))
        return _benchmark_prepared_fixture(config, fixture, runner_factory)


if __name__ == "__main__":
    outcome = build_calibration_processing_baseline()
    benchmark_result = outcome["result"]
    print(
        json.dumps(
            {
                "name": benchmark_result.name,
                "median_ms": benchmark_result.median_ms,
                "p95_ms": benchmark_result.p95_ms,
                "minimum_ms": benchmark_result.minimum_ms,
                "maximum_ms": benchmark_result.maximum_ms,
                "throughput_camera_frames_per_second": benchmark_result.throughput_per_second,
                "failures": list(benchmark_result.failures),
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
