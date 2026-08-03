"""Tests for the read-only Phase 0 live baseline manifest."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_live_baseline import (
    LiveBaselineConfig,
    ReadOnlyResponse,
    _benchmark_definitions,
    _find_completed_triangulation_run_id,
    build_live_baseline,
)


class FakeReadOnlyClient:
    """Returns deterministic fixture responses and records every requested method."""

    def __init__(self, responses: dict[str, ReadOnlyResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    def get(self, url: str, headers: dict[str, str] | None = None) -> ReadOnlyResponse:
        self.requests.append(("GET", url, dict(headers or {})))
        if url not in self.responses:
            return ReadOnlyResponse(404, b'{"error":"missing"}', {})
        return self.responses[url]


def json_response(value: object, status: int = 200) -> ReadOnlyResponse:
    """Build a stable JSON response used by live-runner characterization tests."""

    return ReadOnlyResponse(
        status,
        json.dumps(value, sort_keys=True).encode("utf-8"),
        {"Content-Type": "application/json"},
    )


def discovery_config(
    pc: str,
    laptop: str,
    output: Path,
    *,
    warmup_runs: int = 3,
    measured_runs: int = 10,
) -> LiveBaselineConfig:
    """Build a test configuration that discovers IDs from the supplied fixture."""

    return LiveBaselineConfig(
        pc_base_url=pc,
        laptop_base_url=laptop,
        output_directory=output,
        fixture_session_id=None,
        fixture_recording_set_id=None,
        fixture_recording_id=None,
        fixture_recording_ids=(),
        fixture_calibration_batch_id=None,
        warmup_runs=warmup_runs,
        measured_runs=measured_runs,
    )


class LiveBaselineTests(unittest.TestCase):
    """Characterize discovery, safety, availability, and identity evidence."""

    def test_runner_only_uses_get_and_records_unavailable_optional_scenarios(self) -> None:
        pc = "http://pc"
        laptop = "https://laptop"
        session_payload = {
            "data": {
                "49": {
                    "Recording_Sets": {"177": {"646": {"id": 646}}},
                    "Calibrations": [],
                }
            }
        }
        responses = {
            f"{pc}/api/sessions-info?profile=ui": json_response(session_payload),
            f"{pc}/api/sessions-info?profile=full": json_response(session_payload),
            f"{laptop}/health": json_response({"status": "ok"}),
            f"{laptop}/": ReadOnlyResponse(200, b"<html>operator</html>", {}),
            f"{laptop}/api/sessions-info?profile=ui": json_response(session_payload),
            f"{pc}/api/recordings/646/playback-source": json_response(
                {"data": {"url": "/recordings/clip.mp4"}}
            ),
            f"{pc}/recordings/clip.mp4": ReadOnlyResponse(
                206, b"x", {"Content-Range": "bytes 0-0/100"}
            ),
            f"{pc}/api/recording-sets/177/point-detection/summary": json_response(
                {"data": {"variants": []}}
            ),
            f"{pc}/api/sessions/49/3d/triangulations/statuses": json_response(
                {"data": {"recording_sets": []}}
            ),
            f"{pc}/api/3d/recording-sets/177/triangulations/runs-lite": json_response(
                {"data": {"runs": []}}
            ),
        }
        client = FakeReadOnlyClient(responses)

        with tempfile.TemporaryDirectory() as temporary_directory:
            config = discovery_config(pc, laptop, Path(temporary_directory))
            manifest = build_live_baseline(config, client=client)

        self.assertTrue(all(method == "GET" for method, _, _ in client.requests))
        by_name = {item["name"]: item for item in manifest["scenarios"]}
        self.assertEqual(by_name["detection_first_segment"]["status"], "unavailable")
        self.assertIn("variant", by_name["detection_first_segment"]["reason"])
        self.assertEqual(by_name["calibration_batch_status"]["status"], "unavailable")
        self.assertEqual(manifest["fixture"]["session_id"], 49)
        self.assertEqual(manifest["fixture"]["recording_set_id"], 177)
        self.assertEqual(manifest["fixture"]["recording_id"], 646)

    def test_detection_windows_and_completed_triangulation_result_are_defined(self) -> None:
        config = LiveBaselineConfig(
            pc_base_url="http://pc",
            laptop_base_url="https://laptop",
        )
        run_id = _find_completed_triangulation_run_id(
            {
                "data": {
                    "runs": [
                        {"id": 101, "status": "failed"},
                        {"id": 100, "status": "done"},
                    ]
                }
            }
        )

        definitions, unavailable = _benchmark_definitions(
            config,
            {
                "session_id": 49,
                "recording_set_id": 178,
                "recording_id": 649,
                "recording_ids": [649, 650, 651],
                "calibration_id": None,
                "calibration_batch_id": None,
            },
            None,
            "raw:1053",
            run_id,
        )

        by_name = {definition.name: definition for definition in definitions}
        self.assertEqual(run_id, 100)
        self.assertIn("segment_index=0", by_name["detection_first_segment"].url)
        self.assertIn("segment_index=1", by_name["detection_uncached_seek_segment"].url)
        self.assertEqual(by_name["detection_uncached_seek_segment"].cache_state, "cold")
        self.assertIn("segment_index=2", by_name["detection_sequential_segment"].url)
        self.assertEqual(
            by_name["triangulation_result_retrieval"].url,
            "http://pc/api/3d/triangulation-runs/100/result",
        )
        self.assertFalse(
            any(
                item["name"]
                in {
                    "detection_first_segment",
                    "detection_uncached_seek_segment",
                    "detection_sequential_segment",
                    "triangulation_result_retrieval",
                }
                for item in unavailable
            )
        )

    def test_cold_requests_use_safe_cache_bypass_headers_without_cache_mutation(self) -> None:
        pc = "http://pc"
        laptop = "https://laptop"
        empty_sessions = {"data": {}}
        client = FakeReadOnlyClient(
            {
                f"{pc}/api/sessions-info?profile=ui": json_response(empty_sessions),
                f"{pc}/api/sessions-info?profile=full": json_response(empty_sessions),
                f"{laptop}/health": json_response({"status": "ok"}),
                f"{laptop}/": ReadOnlyResponse(200, b"operator", {}),
                f"{laptop}/api/sessions-info?profile=ui": json_response(empty_sessions),
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            build_live_baseline(
                discovery_config(pc, laptop, Path(temporary_directory)),
                client=client,
            )

        cold_requests = [headers for _, _, headers in client.requests if headers.get("X-MCS-Benchmark-Cache") == "cold"]
        self.assertTrue(cold_requests)
        self.assertTrue(all(item["Cache-Control"] == "no-cache" for item in cold_requests))

    def test_response_identity_change_is_reported_as_a_measurement_failure(self) -> None:
        class ChangingClient(FakeReadOnlyClient):
            count = 0

            def get(self, url: str, headers: dict[str, str] | None = None) -> ReadOnlyResponse:
                if url.endswith("profile=ui") and url.startswith("http://pc"):
                    self.count += 1
                    return json_response({"data": {}, "revision": self.count})
                return super().get(url, headers)

        pc = "http://pc"
        laptop = "https://laptop"
        empty_sessions = json_response({"data": {}})
        client = ChangingClient(
            {
                f"{pc}/api/sessions-info?profile=full": empty_sessions,
                f"{laptop}/health": json_response({"status": "ok"}),
                f"{laptop}/": ReadOnlyResponse(200, b"operator", {}),
                f"{laptop}/api/sessions-info?profile=ui": empty_sessions,
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = build_live_baseline(
                discovery_config(pc, laptop, Path(temporary_directory)),
                client=client,
            )

        scenario = next(
            item for item in manifest["scenarios"] if item["name"] == "pc_sessions_ui"
        )
        self.assertEqual(scenario["status"], "failed")
        self.assertGreater(scenario["failure_count"], 0)
        self.assertIn("identity changed", " ".join(scenario["failures"]))

    def test_manifest_and_benchmark_report_are_written_atomically(self) -> None:
        pc = "http://pc"
        laptop = "https://laptop"
        empty_sessions = json_response({"data": {}})
        client = FakeReadOnlyClient(
            {
                f"{pc}/api/sessions-info?profile=ui": empty_sessions,
                f"{pc}/api/sessions-info?profile=full": empty_sessions,
                f"{laptop}/health": json_response({"status": "ok"}),
                f"{laptop}/": ReadOnlyResponse(200, b"operator", {}),
                f"{laptop}/api/sessions-info?profile=ui": empty_sessions,
            }
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            manifest = build_live_baseline(
                discovery_config(pc, laptop, output), client=client
            )
            saved_manifest = json.loads((output / "phase_00_live_manifest.json").read_text())
            saved_report = json.loads((output / "phase_00_live_benchmark.json").read_text())

        self.assertEqual(saved_manifest, manifest)
        self.assertEqual(saved_report["schema_version"], 1)
        self.assertNotIn("phase_00_live_manifest.json.tmp", saved_manifest)

    def test_unreachable_services_produce_unavailable_manifest_instead_of_crashing(self) -> None:
        class UnreachableClient:
            def get(
                self, url: str, headers: dict[str, str] | None = None
            ) -> ReadOnlyResponse:
                raise ConnectionError(f"unreachable: {url}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = build_live_baseline(
                discovery_config(
                    "http://pc", "https://laptop", Path(temporary_directory)
                ),
                client=UnreachableClient(),
            )

        self.assertTrue(manifest["scenarios"])
        self.assertTrue(
            all(item["status"] == "unavailable" for item in manifest["scenarios"])
        )
        self.assertTrue(
            any("ConnectionError" in str(item["reason"]) for item in manifest["scenarios"])
        )


if __name__ == "__main__":
    unittest.main()
