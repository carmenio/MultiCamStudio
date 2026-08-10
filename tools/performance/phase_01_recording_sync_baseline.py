"""Benchmark the complete recording-synchronization task on fixed production media."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tools.performance import BenchmarkObservation, BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import _commit_identity, _repository_revision


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_01_recording_sync/phase_01_recording_sync_baseline.json"
)
SHARED_STORAGE_ROOT = Path(r"E:\Shared_Folder\Golf_AI\MultiCamStudio")
RUNTIME_RELATIVE_ROOT = Path(".performance/recording-sync/run-current")
CONTAINER_STORAGE_ROOT = "/Storage"
CONTAINER_RUNTIME_ROOT = "/Storage/.performance/recording-sync/run-current"
BACKEND_CONTAINER = "multicam-pc-backend-1"
RECORDING_SET_ID = 178
SESSION_ID = 49
WARMUP_RUNS = 3
MEASURED_RUNS = 10
TARGET_DURATION_SECONDS = 191.07
CAMERA_SECONDS_PER_RUN = 3 * TARGET_DURATION_SECONDS
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class RecordingSyncSource:
    """Freeze one production input by path, size, and full byte identity."""

    recording_id: int
    name: str
    relative_path: str
    size_bytes: int
    sha256: str


PRODUCTION_SOURCES = (
    RecordingSyncSource(
        649,
        "chris",
        "RawVideos/chris.mov",
        450_821_959,
        "7aff77ba7c03e94d637223b3ae21166ac3d238c4f4501651053119d062f73cf7",
    ),
    RecordingSyncSource(
        650,
        "dom",
        "RawVideos/dom.mp4",
        445_290_517,
        "dc504f7daa87744c8e5f6b1301f9cb67c40c55e0afb3b0dc45187b7ea01c8e51",
    ),
    RecordingSyncSource(
        651,
        "anna",
        "RawVideos/anna.mov",
        448_855_126,
        "642a2fafbd3a366c05296c28eaf928ef3bc9baba534f39e0569818e92ebab44f",
    ),
)


@dataclass(frozen=True)
class RecordingSyncConfig:
    """Control the fixed fixture, isolated output, and repetition counts."""

    output_path: Path = OUTPUT_PATH
    shared_storage_root: Path = SHARED_STORAGE_ROOT
    runtime_relative_root: Path = RUNTIME_RELATIVE_ROOT
    sources: tuple[RecordingSyncSource, ...] = PRODUCTION_SOURCES
    container_name: str = BACKEND_CONTAINER
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    target_duration_seconds: float = TARGET_DURATION_SECONDS


WorkloadExecutor = Callable[[], dict[str, Any]]
SourceProbe = Callable[[Path], dict[str, Any]]


def _sha256_file(path: Path) -> str:
    """Hash immutable source bytes outside every timed operation."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_identity(value: Any) -> str:
    """Hash normalized workload evidence for cross-sample equivalence."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class _ContainerSyncExecutor:
    """Run one complete task-handler workload in the deployed backend container."""

    def __init__(self, container_name: str) -> None:
        self.container_name = container_name
        inspection = subprocess.run(
            ["docker", "inspect", container_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if inspection.returncode != 0:
            raise RuntimeError(
                f"backend container {container_name!r} is unavailable; start only the backend service before benchmarking"
            )
        payload = json.loads(inspection.stdout)[0]
        if not bool((payload.get("State") or {}).get("Running")):
            raise RuntimeError(f"backend container {container_name!r} is not running")
        self.container_image_id = str(payload.get("Image") or "unknown")
        self.compose_project = str(
            ((payload.get("Config") or {}).get("Labels") or {}).get("com.docker.compose.project") or "unknown"
        )
        self.python_version = self._version(["python", "--version"])
        self.ffmpeg_version = self._version(["ffmpeg", "-version"], first_line=True)
        self.ffprobe_version = self._version(["ffprobe", "-version"], first_line=True)

    def _version(self, command: list[str], *, first_line: bool = False) -> str:
        completed = subprocess.run(
            ["docker", "exec", self.container_name, *command],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        value = (completed.stdout or completed.stderr).strip()
        return value.splitlines()[0] if first_line and value else value

    def probe_source(self, host_path: Path, storage_root: Path) -> dict[str, Any]:
        """Probe source media through the exact container ffprobe binary."""

        try:
            relative = host_path.resolve().relative_to(storage_root.resolve())
        except ValueError as exc:
            raise RuntimeError(f"sync source is outside the mounted storage root: {host_path}") from exc
        container_path = f"{CONTAINER_STORAGE_ROOT}/{relative.as_posix()}"
        completed = subprocess.run(
            [
                "docker",
                "exec",
                self.container_name,
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                "-of",
                "json",
                container_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return json.loads(completed.stdout)

    def __call__(self) -> dict[str, Any]:
        completed = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                f"PHASE_01_SYNC_OUTPUT_ROOT={CONTAINER_RUNTIME_ROOT}",
                self.container_name,
                "python",
                "scripts/phase_01_recording_sync_workload.py",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30 * 60,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "recording synchronization workload failed: "
                + (completed.stderr or completed.stdout or "unknown container error").strip()
            )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("recording synchronization workload returned no JSON evidence")
        return json.loads(lines[-1])


class _SyncBenchmarkEnvironment:
    """Own isolated cleanup and compare every execution with the reference output."""

    def __init__(
        self,
        config: RecordingSyncConfig,
        executor: WorkloadExecutor,
    ) -> None:
        self.config = config
        self.executor = executor
        self.marker_root = (
            config.shared_storage_root / config.runtime_relative_root.parent
        ).resolve()
        self.runtime_root = (
            config.shared_storage_root / config.runtime_relative_root
        ).resolve()
        self.expected_contract_identity: str | None = None
        self.expected_media_identity: str | None = None
        self.last_evidence: dict[str, Any] | None = None

    def prepare(self) -> None:
        """Delete only the recognized benchmark output before an untimed/timed run."""

        if not _is_within(self.runtime_root, self.marker_root) or self.runtime_root.name != "run-current":
            raise RuntimeError("refusing to clean an unrecognized recording-sync output root")
        if self.runtime_root.exists():
            shutil.rmtree(self.runtime_root)
        self.runtime_root.mkdir(parents=True, exist_ok=False)
        self.last_evidence = None

    def run(self) -> BenchmarkObservation:
        """Execute one sample and reject task or media identity drift immediately."""

        evidence = self.executor()
        contract_identity = str(evidence.get("contract_identity") or "")
        media_identity = str(evidence.get("media_identity") or "")
        if len(contract_identity) != 64 or len(media_identity) != 64:
            raise RuntimeError("recording synchronization workload returned invalid identities")
        if self.expected_contract_identity and contract_identity != self.expected_contract_identity:
            raise RuntimeError("recording synchronization task contract changed between samples")
        if self.expected_media_identity and media_identity != self.expected_media_identity:
            raise RuntimeError("recording synchronization media output changed between samples")
        self.last_evidence = evidence
        camera_seconds = len(self.config.sources) * self.config.target_duration_seconds
        return BenchmarkObservation(camera_seconds, "camera_seconds")

    def cleanup(self) -> None:
        """Remove the isolated result after all evidence has been retained."""

        if self.runtime_root.exists():
            if not _is_within(self.runtime_root, self.marker_root) or self.runtime_root.name != "run-current":
                raise RuntimeError("refusing to remove an unrecognized recording-sync output root")
            shutil.rmtree(self.runtime_root)


def _validate_sources(
    config: RecordingSyncConfig,
    source_probe: SourceProbe,
) -> list[dict[str, Any]]:
    """Reject missing or changed media before creating benchmark output."""

    evidence = []
    storage_root = config.shared_storage_root.resolve()
    for source in config.sources:
        path = (storage_root / source.relative_path).resolve()
        if not _is_within(path, storage_root) or not path.is_file():
            raise RuntimeError(f"recording synchronization source is unavailable: {path}")
        size_bytes = path.stat().st_size
        sha256 = _sha256_file(path)
        if size_bytes != source.size_bytes or sha256 != source.sha256:
            raise RuntimeError(f"recording synchronization source identity changed: {path.name}")
        evidence.append(
            {
                "recording_id": source.recording_id,
                "name": source.name,
                "relative_path": source.relative_path,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "probe": source_probe(path),
            }
        )
    return evidence


def _command_version(command: tuple[str, ...]) -> str:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return "unavailable"


def build_recording_sync_baseline(
    config: RecordingSyncConfig = RecordingSyncConfig(),
    *,
    workload_executor: WorkloadExecutor | None = None,
    source_probe: SourceProbe | None = None,
) -> dict[str, object]:
    """Capture complete synchronization latency, throughput, and equivalence."""

    container_executor = None
    if workload_executor is None or source_probe is None:
        container_executor = _ContainerSyncExecutor(config.container_name)
    executor = workload_executor or container_executor
    assert executor is not None
    if source_probe is None:
        assert container_executor is not None
        source_probe = lambda path: container_executor.probe_source(path, config.shared_storage_root)
    source_evidence = _validate_sources(config, source_probe)
    environment = _SyncBenchmarkEnvironment(config, executor)
    try:
        environment.prepare()
        environment.run()
        assert environment.last_evidence is not None
        reference_evidence = environment.last_evidence
        environment.expected_contract_identity = str(reference_evidence["contract_identity"])
        environment.expected_media_identity = str(reference_evidence["media_identity"])

        result = BenchmarkRunner().run(
            BenchmarkScenario(
                name="recording_sync_set_178_three_camera",
                cache_state="warm",
                operation=environment.run,
                before_each=environment.prepare,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
            )
        )
        if result.failures or result.warmup_failures or environment.last_evidence is None:
            raise RuntimeError(
                "recording synchronization benchmark did not complete every run: "
                f"warmup={list(result.warmup_failures)} measured={list(result.failures)}"
            )

        final_evidence = environment.last_evidence
        output_bytes = int(final_evidence.get("output_bytes") or 0)
        aggregate_seconds = sum(result.durations_ms) / 1000.0
        backend_image = getattr(container_executor, "container_image_id", "injected test execution")
        metadata = {
            "commit": _commit_identity(),
            "source_revisions": {
                "pc": _repository_revision("pc"),
                "laptop": _repository_revision("laptop"),
            },
            "platform": platform.platform(),
            "python": platform.python_version(),
            "node": _command_version(("node", "--version")),
            "dependency_versions": {
                "backend_python": getattr(container_executor, "python_version", "injected test execution"),
                "ffmpeg": getattr(container_executor, "ffmpeg_version", "injected test execution"),
                "ffprobe": getattr(container_executor, "ffprobe_version", "injected test execution"),
            },
            "hardware": HARDWARE,
            "power_mode": POWER_MODE,
            "network_route": "none; one docker exec per complete production task-handler execution",
            "database_snapshot": "set-178 source media with deterministic persistence/task adapters",
            "build_mode": "bind-mounted production backend module in the backend container",
            "compose_configuration": "pc/docker-compose.yml; backend service only",
            "service_images": {"backend": backend_image},
            "cache_preparation": "warm filesystem; one untimed reference, three warmups, isolated output reset per sample",
            "fixture": {
                "session_id": SESSION_ID,
                "recording_set_id": RECORDING_SET_ID,
                "camera_count": len(config.sources),
                "target_duration_seconds": config.target_duration_seconds,
                "camera_seconds_per_run": len(config.sources) * config.target_duration_seconds,
                "sources": source_evidence,
            },
            "camera_count": len(config.sources),
            "recording_duration_seconds": config.target_duration_seconds,
            "media_sizes_bytes": [source.size_bytes for source in config.sources],
            "expected_output_identity": {
                "task_contract": environment.expected_contract_identity,
                "media": environment.expected_media_identity,
            },
            "reference_evidence": reference_evidence,
            "bytes_throughput": {
                "output_bytes_per_run": output_bytes,
                "aggregate_output_bytes": output_bytes * len(result.durations_ms),
                "output_bytes_per_second": (
                    output_bytes * len(result.durations_ms) / aggregate_seconds
                    if aggregate_seconds > 0
                    else None
                ),
            },
            "evidence_scope": "complete _sync_task_handler with production automatic audio correlation, normalization, trimming, audio attach, CFR validation, offsets/debug metadata, persistence projections, preview enqueue, and isolated filesystem output",
            "compose_project": getattr(container_executor, "compose_project", "injected test execution"),
        }
        write_report(config.output_path, [result], metadata)
        return {"results": (result,), "metadata": metadata}
    finally:
        environment.cleanup()


if __name__ == "__main__":
    outcome = build_recording_sync_baseline()
    measured = outcome["results"][0]
    print(
        f"{measured.name}: median={measured.median_ms:.3f} ms "
        f"p95={measured.p95_ms:.3f} ms "
        f"throughput={measured.throughput_per_second:.3f} camera_seconds/s"
    )
