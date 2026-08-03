"""Benchmark the complete recording-cut task with real container ffmpeg execution."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from tools.performance import BenchmarkObservation, BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import _commit_identity, _repository_revision

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Controllers.RecordingsController import RecordingsController  # noqa: E402
from Model.PointDetection.PointDetectionService import PointDetectionService  # noqa: E402


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_recording_cut/phase_00_recording_cut_baseline.json"
)
SHARED_STORAGE_ROOT = Path(r"E:\Shared_Folder\Golf_AI\MultiCamStudio")
SOURCE_RECORDING_SET_ID = 178
SESSION_ID = 49
CUT_START_SECONDS = 60.0
CUT_END_SECONDS = 65.0
WARMUP_RUNS = 3
MEASURED_RUNS = 10
BACKEND_CONTAINER = "multicam-pc-backend-1"
CONTAINER_STORAGE_ROOT = "/Storage"
FFMPEG_PRESET = "veryfast"
AUDIO_BITRATE_KBPS = 96
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class RecordingCutSource:
    """Freezes one synchronized production source and its media identity."""

    recording_id: int
    name: str
    relative_path: str
    size_bytes: int
    sha256: str
    frame_count: int
    measured_fps: float
    duration_seconds: float
    width: int
    height: int


PRODUCTION_SOURCES = (
    RecordingCutSource(
        649,
        "chris",
        "SyncedVideos/set-178/synced_chris.mp4",
        158_557_268,
        "4e3c94e63cb08ef6fc163e3a05f5410c368caad34cf6e3c3f2adf716e772f2b5",
        11_464,
        60.0,
        191.06666666666666,
        1_080,
        1_920,
    ),
    RecordingCutSource(
        650,
        "dom",
        "SyncedVideos/set-178/synced_dom.mp4",
        311_410_416,
        "d0e8e8447ae9451ca7f867f12e811f23410c76edc466b8266ad7062e5cd00c04",
        11_465,
        60.0,
        191.08333333333334,
        1_920,
        1_080,
    ),
    RecordingCutSource(
        651,
        "anna",
        "SyncedVideos/set-178/synced_anna.mp4",
        154_844_460,
        "aa34b03c8226cf7de137a595c95588e312037f236bb17dda3e607307aff7e528",
        11_465,
        60.0,
        191.08333333333334,
        1_920,
        1_080,
    ),
)


@dataclass(frozen=True)
class RecordingCutConfig:
    """Controls the fixed cut fixture, repetitions, and isolated output root."""

    output_path: Path = OUTPUT_PATH
    shared_storage_root: Path = SHARED_STORAGE_ROOT
    sources: tuple[RecordingCutSource, ...] = PRODUCTION_SOURCES
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    backend_container: str = BACKEND_CONTAINER
    cut_start_seconds: float = CUT_START_SECONDS
    cut_end_seconds: float = CUT_END_SECONDS


CutExecution = Callable[..., None]
TimingProbe = Callable[[int, Path], dict[str, Any]]


def _sha256_file(path: Path) -> str:
    """Hash a fixture or result without placing hashing inside benchmark timing."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_identity(value: Any) -> str:
    """Return a stable identity for task, progress, and persistence contracts."""

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _probe_summary(path: Path) -> dict[str, Any]:
    """Normalize the production timing probe to fields required for equivalence."""

    probe = PointDetectionService.probe_video_timing(os.fspath(path))
    return {
        "frame_count": probe.get("frame_count"),
        "measured_fps": probe.get("measured_fps"),
        "duration_seconds": probe.get("duration_seconds"),
        "source_frame_width": probe.get("source_frame_width"),
        "source_frame_height": probe.get("source_frame_height"),
    }


def _validate_source_fixture(config: RecordingCutConfig) -> list[dict[str, Any]]:
    """Reject missing or drifted sources before any output directory is created."""

    evidence: list[dict[str, Any]] = []
    root = config.shared_storage_root.resolve()
    for source in config.sources:
        path = (root / source.relative_path).resolve()
        if not _is_within(path, root) or not path.is_file():
            raise RuntimeError(f"recording-cut source is unavailable: {path}")
        size_bytes = path.stat().st_size
        sha256 = _sha256_file(path)
        probe = _probe_summary(path)
        expected_probe = {
            "frame_count": source.frame_count,
            "measured_fps": source.measured_fps,
            "duration_seconds": source.duration_seconds,
            "source_frame_width": source.width,
            "source_frame_height": source.height,
        }
        if size_bytes != source.size_bytes or sha256 != source.sha256 or probe != expected_probe:
            raise RuntimeError(f"recording-cut source identity changed: {path.name}")
        evidence.append(
            {
                "recording_id": source.recording_id,
                "name": source.name,
                "relative_path": source.relative_path.replace("\\", "/"),
                "size_bytes": size_bytes,
                "sha256": sha256,
                "probe": probe,
            }
        )
    return evidence


class _RecordingDatabase:
    """Captures the handler's persistence writes without contacting production data."""

    OUTPUT_SET_ID = 9_178_001
    OUTPUT_RECORDING_IDS = (9_178_101, 9_178_102, 9_178_103)

    def __init__(self, sources: tuple[RecordingCutSource, ...]) -> None:
        self.sources = sources
        self.reset()

    def reset(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_recording_set(self, recording_set_id):
        return SimpleNamespace(data=[{"id": int(recording_set_id), "session_id": SESSION_ID, "synced": True}])

    def get_recordings_by_set(self, _recording_set_id):
        return SimpleNamespace(
            data=[{"id": item.recording_id, "name": item.name, "file_path": item.relative_path} for item in self.sources]
        )

    def add_recording_set(self, *, session_id, recording_set_name):
        self.calls.append({"operation": "add_recording_set", "session_id": session_id, "name": recording_set_name})
        return SimpleNamespace(data=[{"id": self.OUTPUT_SET_ID}])

    def add_recordings(self, *, recording_set_id, recordings_info):
        normalized = []
        rows = []
        for output_id, info in zip(self.OUTPUT_RECORDING_IDS, recordings_info):
            normalized.append({"name": info["name"], "file_path": info["file_path"], "local_name": Path(info["local_path"]).name})
            rows.append({"id": output_id, "name": info["name"], "file_path": info["file_path"]})
        self.calls.append({"operation": "add_recordings", "recording_set_id": recording_set_id, "rows": normalized})
        return SimpleNamespace(data=rows)

    def get_recording_camera_map_for_recordings(self, recording_ids):
        return [
            {"recording_id": source.recording_id, "camera_id": source.name.lower(), "camera_name": source.name}
            for source in self.sources
            if source.recording_id in recording_ids
        ]

    def upsert_recording_camera_map(self, rows):
        self.calls.append({"operation": "upsert_recording_camera_map", "rows": rows})

    def update_recording_timing(self, recording_id, **values):
        self.calls.append({"operation": "update_recording_timing", "recording_id": recording_id, **values})

    def update_recording_set_synced(self, recording_set_id, synced):
        self.calls.append({"operation": "update_recording_set_synced", "recording_set_id": recording_set_id, "synced": synced})

    def add_recording_set_cut(self, values):
        self.calls.append({"operation": "add_recording_set_cut", **values})


class _SyncDatabase:
    """Supplies immutable synchronized sources and captures new sync rows."""

    def __init__(self, source_paths: dict[int, Path]) -> None:
        self.source_paths = source_paths
        self.reset()

    def reset(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_synced_recordings_by_ids(self, recording_ids):
        return {recording_id: os.fspath(self.source_paths[recording_id]) for recording_id in recording_ids}

    def update_sync(self, recording_set_id, sync_info):
        self.calls.append({"operation": "update_sync", "recording_set_id": recording_set_id, "sync_info": sync_info})

    def upsert_synced_recordings(self, rows):
        self.calls.append({"operation": "upsert_synced_recordings", "rows": rows})


class _TaskDatabase:
    """Records preview task creation and provides a non-cancelled parent task."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def is_cancel_requested(self, _task_id):
        return False

    def create_task(self, **values):
        self.calls.append(dict(values))
        return {"id": 8_000 + len(self.calls), **values}


class _ContainerCutExecution:
    """Runs production ffmpeg in the backend container against its /Storage mount."""

    def __init__(self, *, host_storage_root: Path, container_name: str) -> None:
        self.host_storage_root = host_storage_root.resolve()
        self.container_name = container_name
        probe = subprocess.run(
            ["docker", "exec", container_name, "python", "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0 or not probe.stdout.strip():
            raise RuntimeError(
                f"recording-cut requires running backend container {container_name!r} with imageio-ffmpeg"
            )
        self.ffmpeg_executable = probe.stdout.strip().splitlines()[-1]
        version = subprocess.run(
            ["docker", "exec", container_name, self.ffmpeg_executable, "-version"],
            capture_output=True,
            text=True,
        )
        self.ffmpeg_version = (
            version.stdout.strip().splitlines()[0]
            if version.returncode == 0 and version.stdout.strip()
            else "unavailable"
        )
        image = subprocess.run(
            ["docker", "inspect", "--format", "{{.Image}}", container_name],
            capture_output=True,
            text=True,
        )
        self.container_image_id = (
            image.stdout.strip() if image.returncode == 0 and image.stdout.strip() else "unavailable"
        )

    def _container_path(self, host_path: Path) -> str:
        try:
            relative = host_path.resolve().relative_to(self.host_storage_root)
        except ValueError as exc:
            raise RuntimeError(f"cut path is outside the mounted storage root: {host_path}") from exc
        return f"{CONTAINER_STORAGE_ROOT}/{relative.as_posix()}"

    def __call__(self, *, source_path: Path, output_path: Path, start_seconds: float, end_seconds: float) -> None:
        duration = float(end_seconds) - float(start_seconds)
        command = [
            "docker", "exec", self.container_name, self.ffmpeg_executable,
            "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{float(start_seconds):.6f}", "-i", self._container_path(source_path),
            "-t", f"{duration:.6f}", "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_KBPS}k",
            self._container_path(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"Video cut failed: {(completed.stderr or 'ffmpeg error').strip()}")


class _CutEnvironment:
    """Composes the full production handler around isolated deterministic adapters."""

    def __init__(self, config: RecordingCutConfig, runtime_root: Path, cut_execution: CutExecution, timing_probe: TimingProbe | None) -> None:
        self.config = config
        self.runtime_root = runtime_root.resolve()
        self.source_paths = {
            source.recording_id: (config.shared_storage_root / source.relative_path).resolve()
            for source in config.sources
        }
        self.recording_database = _RecordingDatabase(config.sources)
        self.sync_database = _SyncDatabase(self.source_paths)
        self.task_database = _TaskDatabase()
        self.progress: list[dict[str, Any]] = []
        self.last_result: dict[str, Any] | None = None
        self.last_output_paths: list[Path] = []

        controller = RecordingsController.__new__(RecordingsController)
        controller.recording_database = self.recording_database
        controller.sync_database = self.sync_database
        controller.task_database = self.task_database
        controller.recordings_dir = self.runtime_root / "Recordings"
        controller.synced_recordings_dir = self.runtime_root / "SyncedVideos"
        controller.preview_recordings_dir = self.runtime_root / "PreviewRecordings"
        controller.preview_ffmpeg_preset = FFMPEG_PRESET
        controller.preview_audio_bitrate_kbps = AUDIO_BITRATE_KBPS
        controller._run_ffmpeg_cut = cut_execution
        if timing_probe is not None:
            controller._persist_recording_timing = lambda recording_id, path: self._persist_injected_timing(timing_probe, recording_id, path)
        self.controller = controller

    def _persist_injected_timing(self, timing_probe: TimingProbe, recording_id: int, path: Path) -> None:
        probe = timing_probe(recording_id, path)
        self.recording_database.update_recording_timing(
            recording_id,
            duration_seconds=probe.get("duration_seconds"),
            measured_fps=probe.get("measured_fps"),
            frame_count=probe.get("frame_count"),
        )

    def prepare(self) -> None:
        """Validate the previous output outside timing, then reset only this run root."""

        if self.last_result is not None:
            self.validate_last_output()
        for child in self.runtime_root.iterdir() if self.runtime_root.exists() else ():
            if not _is_within(child, self.runtime_root):
                raise RuntimeError("refusing to clean outside the recording-cut runtime root")
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.recording_database.reset()
        self.sync_database.reset()
        self.task_database.reset()
        self.progress = []
        self.last_result = None
        self.last_output_paths = []

    def run(self) -> BenchmarkObservation:
        task = {
            "id": 7_178_001,
            "session_id": SESSION_ID,
            "recording_set_id": SOURCE_RECORDING_SET_ID,
            "payload": {
                "session_id": SESSION_ID,
                "recording_set_id": SOURCE_RECORDING_SET_ID,
                "cuts": [{"name": "Phase 0 60-65", "start_seconds": self.config.cut_start_seconds, "end_seconds": self.config.cut_end_seconds}],
            },
        }
        self.last_result = self.controller._cut_recording_set_task_handler(task, self._progress_callback)
        output_dir = self.controller._get_synced_output_dir(_RecordingDatabase.OUTPUT_SET_ID)
        self.last_output_paths = sorted(output_dir.glob("*.mp4"))
        if len(self.last_output_paths) != len(self.config.sources):
            raise RuntimeError("recording-cut did not create all camera outputs")
        camera_seconds = len(self.config.sources) * (self.config.cut_end_seconds - self.config.cut_start_seconds)
        return BenchmarkObservation(camera_seconds, "camera_seconds")

    def _progress_callback(self, **values) -> None:
        self.progress.append(values)

    def contract_payload(self) -> dict[str, Any]:
        return {
            "task_result": self.last_result,
            "progress": self.progress,
            "recording_persistence": self.recording_database.calls,
            "sync_persistence": self.sync_database.calls,
            "preview_tasks": self.task_database.calls,
            "output_names": [path.name for path in self.last_output_paths],
        }

    def validate_last_output(self) -> dict[str, Any]:
        if self.last_result is None or len(self.last_output_paths) != len(self.config.sources):
            raise RuntimeError("recording-cut output is incomplete")
        files = []
        for path in self.last_output_paths:
            if not _is_within(path, self.runtime_root) or not path.is_file():
                raise RuntimeError("recording-cut output escaped its isolated runtime root")
            files.append({"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path), "probe": _probe_summary(path)})
        return {"contract": self.contract_payload(), "files": files}

    def cleanup(self) -> None:
        marker_root = (self.config.shared_storage_root / ".performance" / "recording-cut").resolve()
        if not _is_within(self.runtime_root, marker_root) or not self.runtime_root.name.startswith("run-"):
            raise RuntimeError("refusing to remove an unrecognized recording-cut runtime root")
        if self.runtime_root.exists():
            shutil.rmtree(self.runtime_root)


def build_recording_cut_baseline(
    config: RecordingCutConfig = RecordingCutConfig(),
    *,
    cut_execution: CutExecution | None = None,
    timing_probe: TimingProbe | None = None,
) -> dict[str, object]:
    """Measure the full cut handler and persist media plus contract equivalence evidence."""

    source_evidence = _validate_source_fixture(config)
    executor = cut_execution or _ContainerCutExecution(
        host_storage_root=config.shared_storage_root,
        container_name=config.backend_container,
    )
    marker_root = (config.shared_storage_root / ".performance" / "recording-cut").resolve()
    runtime_root = marker_root / f"run-{uuid.uuid4().hex}"
    runtime_root.mkdir(parents=True, exist_ok=False)
    environment = _CutEnvironment(config, runtime_root, executor, timing_probe)
    try:
        # Freeze complete task, persistence, progress, output-name, byte, and probe identities.
        environment.prepare()
        environment.run()
        reference = environment.validate_last_output()
        expected_contract_identity = _canonical_identity(reference["contract"])
        expected_media_identity = _canonical_identity(reference["files"])

        result = BenchmarkRunner().run(
            BenchmarkScenario(
                name="recording_cut_set_178_three_camera_60_65",
                cache_state="warm",
                operation=environment.run,
                before_each=environment.prepare,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
            )
        )
        final_evidence = environment.validate_last_output()
        if _canonical_identity(final_evidence["contract"]) != expected_contract_identity:
            raise RuntimeError("recording-cut task or persistence contract changed during measurement")
        if _canonical_identity(final_evidence["files"]) != expected_media_identity:
            raise RuntimeError("recording-cut media output changed during measurement")

        total_output_bytes = sum(item["size_bytes"] for item in final_evidence["files"])
        aggregate_seconds = sum(result.durations_ms) / 1000.0
        metadata = {
            "commit": _commit_identity(),
            "source_revisions": {"pc": _repository_revision("pc"), "laptop": _repository_revision("laptop")},
            "platform": platform.platform(),
            "python": platform.python_version(),
            "dependency_versions": {
                "ffmpeg": getattr(executor, "ffmpeg_version", "injected test execution"),
                "backend_container_image": getattr(executor, "container_image_id", "injected test execution"),
            },
            "hardware": HARDWARE,
            "power_mode": POWER_MODE,
            "network_route": "none; production ffmpeg reached through docker exec",
            "database_snapshot": "set-178 media snapshot with deterministic in-memory persistence adapters",
            "build_mode": "production backend module and backend-container imageio-ffmpeg binary",
            "cache_preparation": "untimed reference execution, three warmups, isolated output reset per sample",
            "evidence_scope": "complete _cut_recording_set_task_handler including real transcoding, filesystem orchestration, timing probe, naming, progress, preview-task enqueue, and persistence calls; production database and output roots untouched",
            "fixture": {
                "recording_set_id": SOURCE_RECORDING_SET_ID,
                "camera_count": len(config.sources),
                "cut_start_seconds": config.cut_start_seconds,
                "cut_end_seconds": config.cut_end_seconds,
                "camera_seconds_per_run": len(config.sources) * (config.cut_end_seconds - config.cut_start_seconds),
                "frames_per_run": int(len(config.sources) * (config.cut_end_seconds - config.cut_start_seconds) * 60),
                "ffmpeg_preset": FFMPEG_PRESET,
                "audio_bitrate_kbps": AUDIO_BITRATE_KBPS,
                "source_bytes_per_run": sum(source.size_bytes for source in config.sources),
                "sources": source_evidence,
            },
            "expected_contract_identity": expected_contract_identity,
            "expected_media_identity": expected_media_identity,
            "output_files": final_evidence["files"],
            "bytes_throughput": {
                "output_bytes_per_run": total_output_bytes,
                "aggregate_output_bytes": total_output_bytes * len(result.durations_ms),
                "output_bytes_per_second": (total_output_bytes * len(result.durations_ms) / aggregate_seconds) if aggregate_seconds > 0 else None,
            },
        }
        write_report(config.output_path, [result], metadata)
        return {"results": (result,), "metadata": metadata}
    finally:
        environment.cleanup()


if __name__ == "__main__":
    outcome = build_recording_cut_baseline()
    measured = outcome["results"][0]
    print(
        f"{measured.name}: median={measured.median_ms:.3f} ms "
        f"p95={measured.p95_ms:.3f} ms throughput={measured.throughput_per_second:.3f} camera_seconds/s"
    )
