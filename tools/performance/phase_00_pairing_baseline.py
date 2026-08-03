"""Benchmark PC pairing-token issue and resolve through production routes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask

from tools.performance import BenchmarkObservation, BenchmarkRunner, BenchmarkScenario, write_report
from tools.performance.phase_00_live_baseline import _commit_identity, _repository_revision

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "pc" / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from Controllers.SessionCamerasController import SessionCamerasController  # noqa: E402
from Model.Runtime.pairing_token import PairingTokenService  # noqa: E402


# SDK-style fixed benchmark configuration.
OUTPUT_PATH = Path("tools/performance/results/phase_00_pairing/phase_00_pairing_baseline.json")
SESSION_ID = 49
CAMERA_ID = "phase-00-camera"
CAMERA_LABEL = "Phase 00 Camera"
ROOM_ID = "phase-00-room"
SIGNAL_URL = "wss://phase-00.invalid:8089"
PAIRING_SECRET = b"multicam-phase-zero-pairing-benchmark-secret"
WARMUP_RUNS = 3
MEASURED_RUNS = 10
HARDWARE = "11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM"
POWER_MODE = "Balanced"


@dataclass(frozen=True)
class PairingBenchmarkConfig:
    """Controls the fixed PC pairing workload and report path."""

    output_path: Path = OUTPUT_PATH
    warmup_runs: int = WARMUP_RUNS
    measured_runs: int = MEASURED_RUNS


class _SessionCameraDatabase:
    """Returns one immutable WebRTC camera for issue and drift-safe resolve."""

    def get_session_camera(self, *, session_id: int, camera_id: str):
        """Return production adapter-shaped camera rows for the fixed identity."""

        if session_id != SESSION_ID or camera_id != CAMERA_ID:
            return []
        return [
            {
                "session_id": SESSION_ID,
                "camera_id": CAMERA_ID,
                "label": CAMERA_LABEL,
                "room_id": ROOM_ID,
                "transport": "webrtc",
            }
        ]


class _SessionDatabase:
    """Returns the stable session label embedded in resolve responses."""

    def get_session_name(self, session_id: int):
        """Return the production adapter's list response for session 49."""

        return [{"id": SESSION_ID, "name": "Phase 00 Session"}] if session_id == SESSION_ID else []


def _canonical_identity(payload: Any) -> str:
    """Hash normalized token claims or complete resolve responses."""

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


class _PairingEnvironment:
    """Mount production pairing routes around fixed database and token adapters."""

    def __init__(self) -> None:
        service = PairingTokenService.__new__(PairingTokenService)
        service._secret = PAIRING_SECRET
        self.service = service
        app = Flask(__name__)
        controller = SessionCamerasController.__new__(SessionCamerasController)
        controller.app = app
        controller.session_camera_database = _SessionCameraDatabase()
        controller.session_database = _SessionDatabase()
        controller.pairing_token_service = service
        controller.register_routes()
        app.testing = True
        self.client = app.test_client()
        self.resolve_token, _ = service.issue_token(
            session_id=SESSION_ID,
            camera_id=CAMERA_ID,
            room_id=ROOM_ID,
            transport="webrtc",
            camera_label=CAMERA_LABEL,
            signal_url=SIGNAL_URL,
        )
        self.last_issue_claims: dict[str, Any] | None = None
        self.last_resolve_payload: dict[str, Any] | None = None

    @staticmethod
    def _stable_claims(claims: dict[str, Any]) -> dict[str, Any]:
        """Remove only the intentionally volatile expiration claim."""

        return {key: value for key, value in claims.items() if key != "expires_at"}

    def issue(self) -> BenchmarkObservation:
        """Issue and cryptographically verify one token through the public route."""

        response = self.client.post(
            "/api/session-cameras/pairing-token",
            json={
                "session_id": SESSION_ID,
                "camera_id": CAMERA_ID,
                "signal_url": SIGNAL_URL,
            },
        )
        payload = response.get_json()
        data = (payload or {}).get("data", {})
        token = data.get("token")
        expires_at = data.get("expires_at")
        if response.status_code != 200 or not isinstance(token, str) or not isinstance(expires_at, int):
            raise RuntimeError(f"pairing issue contract changed: {response.status_code} {payload}")
        claims = self.service.verify_token(token)
        stable_claims = self._stable_claims(claims)
        expected = {
            "session_id": SESSION_ID,
            "camera_id": CAMERA_ID,
            "room_id": ROOM_ID,
            "transport": "webrtc",
            "camera_label": CAMERA_LABEL,
            "signal_url": SIGNAL_URL,
        }
        if stable_claims != expected or claims["expires_at"] != expires_at:
            raise RuntimeError(f"pairing token claims changed: {claims}")
        self.last_issue_claims = stable_claims
        return BenchmarkObservation(1.0, "tokens_issued")

    def resolve(self) -> BenchmarkObservation:
        """Resolve one pre-created token and verify the full production response."""

        response = self.client.post(
            "/api/session-cameras/pairing-resolve",
            json={"token": self.resolve_token},
        )
        payload = response.get_json()
        data = (payload or {}).get("data", {})
        expected_core = {
            "session_id": SESSION_ID,
            "session_name": "Phase 00 Session",
            "camera_id": CAMERA_ID,
            "camera_label": CAMERA_LABEL,
            "room_id": ROOM_ID,
            "transport": "webrtc",
            "signal_url": SIGNAL_URL,
            "upload_url": "https://phase-00.invalid:8089/upload",
        }
        if response.status_code != 200 or any(data.get(key) != value for key, value in expected_core.items()):
            raise RuntimeError(f"pairing resolve contract changed: {response.status_code} {payload}")
        if not isinstance(data.get("recording_config"), dict):
            raise RuntimeError("pairing resolve recording_config is missing")
        self.last_resolve_payload = payload
        return BenchmarkObservation(1.0, "tokens_resolved")


def build_pairing_baseline(
    config: PairingBenchmarkConfig = PairingBenchmarkConfig(),
) -> dict[str, object]:
    """Measure production PC token routes with fixed internal dependencies."""

    environment = _PairingEnvironment()
    environment.issue()
    environment.resolve()
    issue_identity = _canonical_identity(environment.last_issue_claims)
    resolve_identity = _canonical_identity(environment.last_resolve_payload)
    results = BenchmarkRunner().run_suite(
        (
            BenchmarkScenario(
                name="pc_pairing_token_issue",
                cache_state="warm",
                operation=environment.issue,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
            ),
            BenchmarkScenario(
                name="pc_pairing_token_resolve",
                cache_state="warm",
                operation=environment.resolve,
                warmup_runs=config.warmup_runs,
                measured_runs=config.measured_runs,
            ),
        )
    )
    if (
        _canonical_identity(environment.last_issue_claims) != issue_identity
        or _canonical_identity(environment.last_resolve_payload) != resolve_identity
    ):
        raise RuntimeError("pairing output changed during repeated measurement")

    metadata = {
        "commit": _commit_identity(),
        "source_revisions": {
            "pc": _repository_revision("pc"),
            "laptop": _repository_revision("laptop"),
        },
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dependency_versions": {"flask": importlib.metadata.version("flask")},
        "hardware": HARDWARE,
        "power_mode": POWER_MODE,
        "network_route": "none; in-process production Flask routes",
        "database_snapshot": "fixed injected camera/session adapters",
        "build_mode": "local Python production controller and HMAC service",
        "cache_preparation": "pre-created resolve token followed by three warmups",
        "fixture": {
            "session_id": SESSION_ID,
            "camera_id": CAMERA_ID,
            "room_id": ROOM_ID,
            "transport": "webrtc",
            "signal_url": SIGNAL_URL,
        },
        "expected_output_identity": {
            "issue_claims": issue_identity,
            "resolve_response": resolve_identity,
        },
        "expiration_shape": "integer Unix epoch",
        "side_effects": "none",
        "evidence_scope": "PC route/HMAC lower bound; not EdgeRelay, QR, network, WebRTC, or physical device evidence",
    }
    write_report(config.output_path, results, metadata)
    return {"results": results, "metadata": metadata}


if __name__ == "__main__":
    outcome = build_pairing_baseline()
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
