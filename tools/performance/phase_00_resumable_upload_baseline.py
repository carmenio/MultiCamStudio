"""Benchmark the PC resumable-upload routes with temporary local storage."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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

# Load the production controller without constructing external database clients.
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Controllers.RecordingsController import RecordingsController  # noqa: E402


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_resumable_upload/phase_00_resumable_upload_baseline.json"
)
WARMUP_RUNS = 3
MEASURED_RUNS = 10
TOTAL_BYTES = 16 * 1024 * 1024
CHUNK_COUNT = 4
UPLOAD_ID = "phase-00-resumable-upload"
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class ResumableUploadConfig:
    """Controls the fixed upload payload, route samples, and report destination."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    total_bytes: int = TOTAL_BYTES
    chunk_count: int = CHUNK_COUNT


class _UploadDatabase:
    """Stores upload-session state while production routes own filesystem behavior."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.chunks: dict[tuple[str, int], dict[str, Any]] = {}
        self.metadata_rows: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.sessions.clear()
        self.chunks.clear()
        self.metadata_rows.clear()

    def get_upload_session(self, upload_id):
        row = self.sessions.get(str(upload_id))
        return dict(row) if row else None

    def create_upload_session(self, values):
        row = dict(values)
        self.sessions[str(row["id"])] = row
        return dict(row)

    def update_upload_session(self, upload_id, values):
        self.sessions[str(upload_id)].update(dict(values))
        return dict(self.sessions[str(upload_id)])

    def list_upload_chunks(self, upload_id):
        return [
            dict(row)
            for (stored_upload_id, _), row in self.chunks.items()
            if stored_upload_id == str(upload_id)
        ]

    def get_upload_chunk(self, upload_id, chunk_index):
        row = self.chunks.get((str(upload_id), int(chunk_index)))
        return dict(row) if row else None

    def upsert_upload_chunk(self, values):
        row = dict(values)
        key = (str(row["upload_id"]), int(row["chunk_index"]))
        self.chunks[key] = row
        return dict(row)

    def insert_upload_recording_metadata(self, values):
        self.metadata_rows.append(dict(values))
        return dict(values)


def _payload(total_bytes: int, chunk_count: int) -> tuple[bytes, ...]:
    """Build deterministic equal-sized chunks once, outside measured work."""

    if total_bytes <= 0 or chunk_count < 3 or total_bytes % chunk_count != 0:
        raise ValueError(
            "total_bytes must be positive, evenly divisible, and use at least three chunks"
        )
    chunk_size = total_bytes // chunk_count
    seed = b"MultiCamStudio phase zero upload fixture\x00\xff"
    return tuple(
        ((seed + bytes([index])) * ((chunk_size // (len(seed) + 1)) + 1))[:chunk_size]
        for index in range(chunk_count)
    )


class _UploadEnvironment:
    """Composes production Flask routes with a temporary root and injected state."""

    def __init__(self, storage_root: Path, chunks: tuple[bytes, ...]) -> None:
        self.storage_root = storage_root.resolve()
        self.chunks = chunks
        self.total_bytes = sum(len(chunk) for chunk in chunks)
        self.expected_checksum = hashlib.sha256(b"".join(chunks)).hexdigest()
        self.database = _UploadDatabase()
        app = Flask(__name__)
        controller = RecordingsController.__new__(RecordingsController)
        controller.app = app
        controller.recording_database = self.database
        controller.recordings_dir = self.storage_root
        controller.incoming_upload_dir = self.storage_root / "incoming"
        controller.incoming_upload_dir.mkdir(parents=True, exist_ok=True)
        controller.register_routes()
        app.testing = True
        self.client = app.test_client()
        self.last_completed_path: Path | None = None

    def _clean_storage(self) -> None:
        """Delete only children of the dedicated temporary benchmark directory."""

        for path in self.storage_root.iterdir():
            resolved = path.resolve()
            if self.storage_root not in resolved.parents:
                raise RuntimeError("refusing to clean an upload outside the benchmark root")
            if resolved.is_dir():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        (self.storage_root / "incoming").mkdir(parents=True, exist_ok=True)

    def _session(self, *, status: str = "initialized") -> dict[str, Any]:
        return {
            "id": UPLOAD_ID,
            "session_id": 49,
            "device_id": "phase-00-camera",
            "recording_id": "phase-00-recording",
            "file_name": "phase-00-recording.mp4",
            "total_chunks": len(self.chunks),
            "total_bytes": self.total_bytes,
            "chunk_size": len(self.chunks[0]),
            "status": status,
            "checksum": self.expected_checksum,
            "metadata_json": {
                "requestedFps": 240,
                "actualFps": 240,
                "resolution": "1920x1080",
                "lens": "wide",
            },
        }

    def prepare_empty(self) -> None:
        self._clean_storage()
        self.database.reset()

    def prepare_session(self) -> None:
        self.prepare_empty()
        self.database.create_upload_session(self._session())

    def prepare_interrupted(self) -> None:
        self.prepare_session()
        for chunk_index in (0, 2):
            chunk = self.chunks[chunk_index]
            self.database.upsert_upload_chunk(
                {
                    "upload_id": UPLOAD_ID,
                    "chunk_index": chunk_index,
                    "size_bytes": len(chunk),
                    "checksum": hashlib.sha256(chunk).hexdigest(),
                    "status": "received",
                }
            )
        self.database.update_upload_session(UPLOAD_ID, {"status": "uploading"})

    def prepare_complete(self) -> None:
        self.prepare_session()
        chunk_directory = (
            self.storage_root / "incoming" / "sessions" / UPLOAD_ID / "chunks"
        )
        chunk_directory.mkdir(parents=True, exist_ok=True)
        for chunk_index, chunk in enumerate(self.chunks):
            (chunk_directory / f"{chunk_index:08d}.part").write_bytes(chunk)
            self.database.upsert_upload_chunk(
                {
                    "upload_id": UPLOAD_ID,
                    "chunk_index": chunk_index,
                    "size_bytes": len(chunk),
                    "checksum": hashlib.sha256(chunk).hexdigest(),
                    "status": "received",
                }
            )
        self.database.update_upload_session(UPLOAD_ID, {"status": "uploading"})
        self.last_completed_path = None

    def init_upload(self) -> None:
        response = self.client.post(
            "/upload/init",
            json={
                "uploadId": UPLOAD_ID,
                "recordingId": "phase-00-recording",
                "sessionId": 49,
                "deviceId": "phase-00-camera",
                "fileName": "phase-00-recording.mp4",
                "totalChunks": len(self.chunks),
                "totalBytes": self.total_bytes,
                "chunkSize": len(self.chunks[0]),
                "checksum": self.expected_checksum,
                "requestedFps": 240,
                "actualFps": 240,
                "resolution": "1920x1080",
                "lens": "wide",
            },
        )
        if response.status_code != 201 or response.get_json() != {
            "data": {
                "uploadId": UPLOAD_ID,
                "status": "initialized",
                "uploadedChunkIndices": [],
            }
        }:
            raise RuntimeError(f"upload init contract changed: {response.status_code} {response.get_json()}")
        return None

    def resume_upload(self) -> None:
        response = self.client.post(
            "/upload/init",
            json={
                "uploadId": UPLOAD_ID,
                "recordingId": "phase-00-recording",
                "sessionId": 49,
                "deviceId": "phase-00-camera",
            },
        )
        expected = {
            "data": {
                "uploadId": UPLOAD_ID,
                "status": "uploading",
                "uploadedChunkIndices": [0, 2],
            }
        }
        if response.status_code != 200 or response.get_json() != expected:
            raise RuntimeError(f"upload resume contract changed: {response.status_code} {response.get_json()}")
        return None

    def write_chunks(self) -> BenchmarkObservation:
        for chunk_index, chunk in enumerate(self.chunks):
            response = self.client.put(
                f"/upload/{UPLOAD_ID}/chunk?chunkIndex={chunk_index}",
                data=chunk,
                content_type="application/octet-stream",
            )
            body = response.get_json()
            if response.status_code != 200 or body.get("data", {}).get("sizeBytes") != len(chunk):
                raise RuntimeError(f"upload chunk contract changed: {response.status_code} {body}")
        return BenchmarkObservation(float(self.total_bytes), "bytes")

    def complete_upload(self) -> BenchmarkObservation:
        response = self.client.post(
            f"/upload/{UPLOAD_ID}/complete",
            json={"checksum": self.expected_checksum},
        )
        body = response.get_json()
        data = body.get("data") if isinstance(body, dict) else None
        if (
            response.status_code != 200
            or not isinstance(data, dict)
            or data.get("bytes") != self.total_bytes
            or data.get("checksum") != self.expected_checksum
        ):
            raise RuntimeError(f"upload completion contract changed: {response.status_code} {body}")
        self.last_completed_path = self.storage_root / "phase-00-recording.mp4"
        return BenchmarkObservation(float(self.total_bytes), "bytes")

    def verify_completed_output(self) -> None:
        """Hash the final measured output after timing has stopped."""

        if self.last_completed_path is None or not self.last_completed_path.is_file():
            raise RuntimeError("completed upload output is unavailable")
        actual_checksum = hashlib.sha256(self.last_completed_path.read_bytes()).hexdigest()
        if actual_checksum != self.expected_checksum:
            raise RuntimeError("completed upload bytes do not match the fixed fixture")


def _scenario(
    *,
    name: str,
    operation: Callable[[], BenchmarkObservation | None],
    before_each: Callable[[], None],
    config: ResumableUploadConfig,
    maximum_p95_ms: float | None = None,
) -> BenchmarkScenario:
    """Create one warm server-only route scenario with the universal run count."""

    return BenchmarkScenario(
        name=name,
        cache_state="warm",
        operation=operation,
        before_each=before_each,
        warmup_runs=config.warmup_runs,
        measured_runs=config.measured_runs,
        maximum_p95_ms=maximum_p95_ms,
    )


def build_resumable_upload_baseline(
    config: ResumableUploadConfig = ResumableUploadConfig(),
) -> dict[str, object]:
    """Measure init, resume, chunk persistence, and completion without live state."""

    chunks = _payload(config.total_bytes, config.chunk_count)
    with tempfile.TemporaryDirectory(prefix="mcs-resumable-upload-benchmark-") as temporary:
        environment = _UploadEnvironment(Path(temporary), chunks)
        results = BenchmarkRunner().run_suite(
            (
                _scenario(
                    name="resumable_upload_init",
                    operation=environment.init_upload,
                    before_each=environment.prepare_empty,
                    config=config,
                ),
                _scenario(
                    name="resumable_upload_interrupted_resume",
                    operation=environment.resume_upload,
                    before_each=environment.prepare_interrupted,
                    config=config,
                ),
                _scenario(
                    name="resumable_upload_chunk_write",
                    operation=environment.write_chunks,
                    before_each=environment.prepare_session,
                    config=config,
                ),
                _scenario(
                    name="resumable_upload_assembly_and_checksum",
                    operation=environment.complete_upload,
                    before_each=environment.prepare_complete,
                    config=config,
                ),
            )
        )
        environment.verify_completed_output()
        metadata = {
            "commit": _commit_identity(),
            "source_revisions": {
                "pc": _repository_revision("pc"),
                "laptop": _repository_revision("laptop"),
            },
            "platform": platform.platform(),
            "python": platform.python_version(),
            "node": _command_version(["node", "--version"]),
            "dependency_versions": {"flask": importlib.metadata.version("flask")},
            "hardware": HARDWARE,
            "power_mode": POWER_MODE,
            "network_route": "in-process Flask route adapter; no device or network transport",
            "database_snapshot": "fixed in-memory upload adapter; no database access",
            "build_mode": "local Python production controller routes",
            "compose_configuration": "pc/docker-compose.yml route semantics; isolated process fixture",
            "service_images": {"backend": "local source; no container"},
            "cache_preparation": "dedicated temp root reset before each sample; three warmups",
            "fixture": {
                "upload_id": UPLOAD_ID,
                "total_bytes": config.total_bytes,
                "chunk_count": config.chunk_count,
                "chunk_size": len(chunks[0]),
                "interrupted_uploaded_chunk_indices": [0, 2],
            },
            "expected_output_identity": environment.expected_checksum,
            "camera_count": 1,
            "recording_duration_seconds": 0,
            "media_sizes_bytes": [config.total_bytes],
            "side_effects": "temporary local files only; removed when the run completes",
            "evidence_scope": (
                "PC server route and filesystem only; not physical phone Stop-to-upload-init, "
                "radio/network transport, or device recovery evidence"
            ),
        }
    write_report(config.output_path, results, metadata)
    return {"results": results, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_resumable_upload_baseline()
    print(
        json.dumps(
            [
                {
                    "name": result.name,
                    "median_ms": result.median_ms,
                    "p95_ms": result.p95_ms,
                    "throughput_bytes_per_second": result.throughput_per_second,
                    "failures": list(result.failures),
                }
                for result in outcome["results"]
            ],
            indent=2,
        )
    )
