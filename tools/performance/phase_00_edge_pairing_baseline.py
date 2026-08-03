"""Benchmark EdgeRelay pairing issue and resolve through production routes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

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


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path(
    "tools/performance/results/phase_00_edge_pairing/phase_00_edge_pairing_baseline.json"
)
EDGE_RELAY_PATH = (
    Path(__file__).resolve().parents[2] / "laptop" / "services" / "edge-relay" / "app.py"
)
SESSION_ID = 49
CAMERA_ID = "phase-00-edge-camera"
CAMERA_LABEL = "Phase 00 Edge Camera"
ROOM_ID = "phase-00-edge-room"
REQUEST_HOST = "phase-00-laptop.tailnet.ts.net"
REQUEST_HEADERS = {"Host": REQUEST_HOST, "X-Forwarded-Proto": "https"}
PAIRING_SECRET = "multicam-phase-zero-edge-pairing-secret"
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"

EXPECTED_TOKEN_CLAIMS = {
    "session_id": SESSION_ID,
    "camera_id": CAMERA_ID,
    "camera_label": CAMERA_LABEL,
    "room_id": ROOM_ID,
}
EXPECTED_RESOLVE_RESPONSE = {
    "status_code": 200,
    "body": {
        "data": {
            **EXPECTED_TOKEN_CLAIMS,
            "transport": "webrtc",
            "signal_url": f"wss://{REQUEST_HOST}/ws",
            "upload_url": f"https://{REQUEST_HOST}/upload",
            "api_base": f"https://{REQUEST_HOST}",
            "recording_config": {
                "container": "mp4",
                "mime_type": "video/mp4",
                "extension": "mp4",
            },
        }
    },
}


@dataclass(frozen=True)
class EdgePairingBenchmarkConfig:
    """Controls the isolated EdgeRelay pairing workload and report destination."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS
    temporary_parent: Path | None = None


def _canonical_identity(payload: Any) -> str:
    """Hash a normalized route response using a stable JSON representation."""

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


class _EdgePairingEnvironment:
    """Own an isolated EdgeRelay module, SQLite database, and Flask test client."""

    _ENVIRONMENT = {
        "EDGE_NODE_ID": "phase-00-edge-node",
        "EDGE_SYNC_TOKEN": "phase-00-edge-sync-token",
        "EDGE_PAIRING_SECRET": PAIRING_SECRET,
        "EDGE_PUBLIC_ORIGIN": f"https://{REQUEST_HOST}",
        "PC_API_ORIGIN": "https://phase-00-pc.invalid",
    }

    def __init__(self, temporary_parent: Path | None) -> None:
        parent = temporary_parent.resolve() if temporary_parent is not None else None
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(
            prefix="mcs-edge-pairing-",
            dir=str(parent) if parent is not None else None,
            ignore_cleanup_errors=False,
        )
        self.data_root = Path(self._temporary.name).resolve()
        self._previous_environment = {
            key: os.environ.get(key) for key in (*self._ENVIRONMENT, "EDGE_DATA_DIR")
        }
        os.environ.update(self._ENVIRONMENT)
        os.environ["EDGE_DATA_DIR"] = str(self.data_root)
        self.module_name = f"mcs_phase_00_edge_pairing_{uuid.uuid4().hex}"
        try:
            self.module = self._load_module()
            self.client = self.module.app.test_client()
            self._seed_camera_cache()
        except BaseException:
            self.close()
            raise

    def _load_module(self) -> ModuleType:
        """Load production routes while suppressing only the infinite transfer worker."""

        specification = importlib.util.spec_from_file_location(
            self.module_name, EDGE_RELAY_PATH
        )
        if specification is None or specification.loader is None:
            raise RuntimeError(f"unable to load EdgeRelay module from {EDGE_RELAY_PATH}")
        module = importlib.util.module_from_spec(specification)
        sys.modules[self.module_name] = module
        with patch.object(threading.Thread, "start", return_value=None):
            specification.loader.exec_module(module)
        module.app.testing = True
        return module

    def _seed_camera_cache(self) -> None:
        """Insert the fixed camera directly into EdgeRelay's production cache schema."""

        camera = {
            "session_id": SESSION_ID,
            "camera_id": CAMERA_ID,
            "label": CAMERA_LABEL,
            "room_id": ROOM_ID,
            "transport": "webrtc",
            "ui_settings": {"acquisitionMode": "website"},
        }
        with self.module.db_lock, self.module.connect_db() as database:
            database.execute(
                "insert into cached_sessions(session_id,payload_json,cached_at) values(?,?,?)",
                (
                    SESSION_ID,
                    json.dumps({"id": SESSION_ID, "name": "Phase 00 Session"}),
                    self.module.utc_now(),
                ),
            )
            database.execute(
                "insert into cached_cameras(session_id,camera_id,payload_json,cached_at) "
                "values(?,?,?,?)",
                (
                    SESSION_ID,
                    CAMERA_ID,
                    json.dumps(camera),
                    self.module.utc_now(),
                ),
            )
            database.commit()

    def issue(self) -> BenchmarkObservation:
        """Issue and verify one token through EdgeRelay's canonical public route."""

        with patch.object(
            self.module.requests,
            "request",
            side_effect=RuntimeError("pairing benchmark attempted a PC network request"),
        ):
            response = self.client.post(
                "/api/session-cameras/pairing-token",
                json={"session_id": SESSION_ID, "camera_id": CAMERA_ID},
                headers=REQUEST_HEADERS,
            )
        payload = response.get_json()
        if response.status_code != 200 or not isinstance(payload, dict):
            raise RuntimeError(
                "EdgeRelay pairing issue contract changed: "
                f"{response.status_code} {payload}"
            )
        if set(payload) != {"data"} or not isinstance(payload["data"], dict):
            raise RuntimeError(f"EdgeRelay pairing issue response shape changed: {payload}")
        data = payload["data"]
        if set(data) != {"token", "expires_at"}:
            raise RuntimeError(f"EdgeRelay pairing issue data fields changed: {data}")
        token = data.get("token")
        expires_at = data.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at, str):
            raise RuntimeError(f"EdgeRelay pairing issue value types changed: {data}")
        claims = self.module.serializer.loads(token, max_age=15 * 60)
        if claims != EXPECTED_TOKEN_CLAIMS:
            raise RuntimeError(f"EdgeRelay pairing token claims changed: {claims}")
        expiration = datetime.fromisoformat(expires_at)
        if expiration.tzinfo is None or expiration.utcoffset() != timezone.utc.utcoffset(None):
            raise RuntimeError(f"EdgeRelay pairing expiration is not UTC ISO-8601: {expires_at}")
        self.last_token = token
        return BenchmarkObservation(1.0, "tokens_issued")

    def resolve(self) -> BenchmarkObservation:
        """Resolve the fixed token and compare the complete public response body."""

        with patch.object(
            self.module.requests,
            "request",
            side_effect=RuntimeError("pairing benchmark attempted a PC network request"),
        ):
            response = self.client.post(
                "/api/session-cameras/pairing-resolve",
                json={"token": self.resolve_token},
                headers=REQUEST_HEADERS,
            )
        normalized = {"status_code": response.status_code, "body": response.get_json()}
        if normalized != EXPECTED_RESOLVE_RESPONSE:
            raise RuntimeError(f"EdgeRelay pairing resolve contract changed: {normalized}")
        return BenchmarkObservation(1.0, "tokens_resolved")

    def freeze_reference(self) -> None:
        """Create one valid resolve fixture before warmups and measured operations."""

        self.issue()
        self.resolve_token = self.last_token
        self.resolve()

    def close(self) -> None:
        """Remove the isolated module, restore process environment, and delete SQLite files."""

        sys.modules.pop(getattr(self, "module_name", ""), None)
        for key, previous in getattr(self, "_previous_environment", {}).items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        temporary = getattr(self, "_temporary", None)
        if temporary is not None:
            temporary.cleanup()


def build_edge_pairing_baseline(
    config: EdgePairingBenchmarkConfig = EdgePairingBenchmarkConfig(),
) -> dict[str, object]:
    """Measure production EdgeRelay pairing routes with isolated local dependencies."""

    environment = _EdgePairingEnvironment(config.temporary_parent)
    try:
        environment.freeze_reference()
        results = BenchmarkRunner().run_suite(
            (
                BenchmarkScenario(
                    name="edge_pairing_token_issue",
                    cache_state="warm",
                    operation=environment.issue,
                    warmup_runs=config.warmup_runs,
                    measured_runs=config.measured_runs,
                ),
                BenchmarkScenario(
                    name="edge_pairing_token_resolve",
                    cache_state="warm",
                    operation=environment.resolve,
                    warmup_runs=config.warmup_runs,
                    measured_runs=config.measured_runs,
                ),
            )
        )
        expected_output_identity = {
            "issue_normalized": _canonical_identity(
                {
                    "status_code": 200,
                    "body": {
                        "data": {
                            "token_claims": EXPECTED_TOKEN_CLAIMS,
                            "expires_at_shape": "UTC ISO-8601 timestamp",
                        }
                    },
                }
            ),
            "resolve_response": _canonical_identity(EXPECTED_RESOLVE_RESPONSE),
        }
        metadata = {
            "commit": _commit_identity(),
            "source_revisions": {
                "pc": _repository_revision("pc"),
                "laptop": _repository_revision("laptop"),
            },
            "platform": platform.platform(),
            "python": platform.python_version(),
            "node": _command_version(["node", "--version"]),
            "hardware": HARDWARE,
            "power_mode": POWER_MODE,
            "network_route": "none; in-process production EdgeRelay Flask routes",
            "database_snapshot": "isolated SQLite cache with one fixed session and camera",
            "fixture": {
                "session_id": SESSION_ID,
                "camera_id": CAMERA_ID,
                "camera_label": CAMERA_LABEL,
                "room_id": ROOM_ID,
                "request_origin": f"https://{REQUEST_HOST}",
                "transport": "webrtc",
            },
            "build_mode": "local Python production EdgeRelay module",
            "dependency_versions": {
                "flask": importlib.metadata.version("flask"),
                "flask-cors": importlib.metadata.version("flask-cors"),
                "itsdangerous": importlib.metadata.version("itsdangerous"),
            },
            "compose_configuration": "laptop/docker-compose.yml route semantics; isolated process fixture",
            "service_images": {"edge-relay": "local source; no container"},
            "cache_preparation": "fixed SQLite cache and resolve token, then three warmups",
            "camera_count": 1,
            "recording_duration_seconds": 0,
            "media_sizes_bytes": [],
            "expected_output_identity": expected_output_identity,
            "side_effects": "isolated temporary SQLite files removed after the report is written",
            "evidence_scope": "EdgeRelay Flask route, SQLite cache lookup, token signing, token verification, and forwarded-origin URL derivation; not PC network, nginx, QR rendering, WebRTC, or physical-device evidence",
        }
        write_report(config.output_path, results, metadata)
        return {"results": results, "metadata": metadata}
    finally:
        environment.close()


if __name__ == "__main__":
    outcome = build_edge_pairing_baseline()
    print(
        json.dumps(
            {
                "results": [
                    {
                        "name": result.name,
                        "median_ms": result.median_ms,
                        "p95_ms": result.p95_ms,
                        "throughput_per_second": result.throughput_per_second,
                        "failures": list(result.failures),
                    }
                    for result in outcome["results"]
                ],
                "output": str(OUTPUT_PATH),
            },
            indent=2,
        )
    )
